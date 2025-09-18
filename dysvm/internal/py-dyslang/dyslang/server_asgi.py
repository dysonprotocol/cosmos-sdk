import json
import sys
import traceback
from typing import Any, Dict, Callable

from .dysvm_server import (
    eval_script,
    DecimalEncoder,
    build_sandbox,
)


async def _read_json_body(receive: Callable) -> Dict[str, Any]:
    event = await receive()
    body = event.get("body", b"") or b""
    if isinstance(body, str):
        body = body.encode()
    if not body:
        return {}
    try:
        return json.loads(body)
    except Exception:
        return {}


def _json_response(payload: Dict[str, Any]) -> Dict[str, Any]:
    body = json.dumps(payload, separators=(",", ":"))
    return {
        "type": "http.response.start",
        "status": 200,
        "headers": [[b"content-type", b"application/json"]],
    }, {
        "type": "http.response.body",
        "body": body.encode("utf-8"),
    }


def _ok(result: Any) -> Dict[str, Any]:
    return {"ok": True, "result": result}


def _err_from_exc(e: Exception, source_code: str = "") -> Dict[str, Any]:
    lineno = getattr(e, "lineno", 0)
    col_offset = getattr(e, "col_offset", 0)
    end_lineno = getattr(e, "end_lineno", 0)
    end_col_offset = getattr(e, "end_col_offset", 0)
    context = getattr(e, "__class__", type("", (), {})).__name__
    try:
        # Try to pull source segment if node exists
        node = getattr(e, "node", None)
        if node is not None and source_code:
            import ast

            source_segment = ast.get_source_segment(source_code, node) or ""
        else:
            source_segment = ""
    except Exception:
        source_segment = ""
    return {
        "ok": False,
        "error": {
            "class": e.__class__.__name__,
            "msg": str(e),
            "lineno": lineno,
            "col_offset": col_offset,
            "end_lineno": end_lineno,
            "end_col_offset": end_col_offset,
            "context": context,
            "source_segment": source_segment,
        },
    }


async def _handle_exec_script(payload: Dict[str, Any]) -> Dict[str, Any]:
    msg_json = payload.get("msg_json", "{}")
    script_json = payload.get("script_json", "{}")
    attached_msg_results_json = payload.get("attached_msg_results_json", "[]")
    header_info_json = payload.get("header_info_json", "{}")
    rpc_port = int(payload.get("rpc_port", 0))
    try:
        _, response = eval_script(
            rpc_port,
            json.loads(script_json),
            json.loads(msg_json),
            json.loads(attached_msg_results_json),
            json.loads(header_info_json),
        )
        # If the script raised an exception, return ok=false to preserve legacy semantics
        if response.get("exception") is not None:
            return {"ok": False, "error": response}
        return _ok(json.dumps(response, separators=(",", ":"), cls=DecimalEncoder))
    except Exception as e:
        return _err_from_exc(e)


async def _handle_run_benchmark(payload: Dict[str, Any]) -> Dict[str, Any]:
    from . import fp_benchmark

    iterations = int(payload.get("iterations", 100))
    details = bool(payload.get("details", True))
    try:
        result = fp_benchmark.detect_fp_differences(iterations, details)
        return _ok(json.dumps(result, separators=(",", ":")))
    except Exception as e:
        return _err_from_exc(e)


async def _handle_dys_format(payload: Dict[str, Any]) -> Dict[str, Any]:
    import black
    from . import DysEval

    code = payload.get("code", "")
    try:
        DysEval().validate(code)
        formatted = black.format_str(code, mode=black.Mode())
        return _ok(formatted)
    except Exception as e:
        return _err_from_exc(e)


async def _handle_extract_function_schema(payload: Dict[str, Any]) -> Dict[str, Any]:
    import types
    import json as _json
    from function_schema.core import get_function_schema

    script = _json.loads(payload.get("script_json", "{}"))
    block_info = _json.loads(payload.get("block_info_json", "{}"))
    rpc_port = int(payload.get("rpc_port", 0))
    executor_address = payload.get("executor_address", "")
    script_name = payload.get("script_name", "")
    try:
        sandbox = build_sandbox(
            msg={
                "executor_address": executor_address,
                "function_name": "",
                "args": "[]",
                "kwargs": "{}",
                "extra_code": "",
                "attached_messages": [],
                "script_name": script_name,
            },
            script=script,
            attached_msg_results=[],
            block_info=block_info,
            port=rpc_port,
        )
        sandbox.consume_gas()
        try:
            sandbox.eval(script.get("code", ""))
            sandbox.consume_gas()
        except Exception as e:
            return _err_from_exc(e)

        scope = sandbox.scope
        public_scope_all = scope.get(
            "__all__",
            [
                k
                for k, v in scope.items()
                if getattr(v, "__module__", None) == "script"
                and not k.startswith("_")
                and k not in ["wsgi"]
            ],
        )
        result = []
        for name in public_scope_all:
            obj = scope.get(name)
            if (
                isinstance(obj, types.FunctionType)
                and getattr(obj, "__module__", None) == "script"
            ):
                try:
                    result.append(
                        {
                            "function_name": name,
                            "schema": get_function_schema(obj, "openai"),
                        }
                    )
                except Exception as e:
                    result.append({"function_name": name, "error": str(e)})

        return _ok(json.dumps(result, separators=(",", ":"), cls=DecimalEncoder))
    except Exception as e:
        return _err_from_exc(e)


async def _handle_run_wsgi(payload: Dict[str, Any]) -> Dict[str, Any]:
    # Reuse dyswsgi.main by capturing stdout (prints base64 response)
    import io
    from contextlib import redirect_stdout
    from . import dyswsgi

    script_name = payload.get("script_name", "")
    script_json = payload.get("script_json", "{}")
    block_info_json = payload.get("block_info_json", "{}")
    http_request = payload.get("http_request", "")
    rpc_port = int(payload.get("rpc_port", 0))
    try:
        f = io.StringIO()
        with redirect_stdout(f):
            dyswsgi.main(
                str(rpc_port), script_name, script_json, block_info_json, http_request
            )
        out = f.getvalue().strip()
        return _ok(out)
    except Exception as e:
        return _err_from_exc(e)


async def app(scope: Dict[str, Any], receive: Callable, send: Callable) -> None:
    if scope["type"] != "http":
        start, body = _json_response(
            {"ok": False, "error": {"class": "TypeError", "msg": "Unsupported scope"}}
        )
        await send(start)
        await send(body)
        return

    method = scope.get("method", "GET")
    path = scope.get("path", "/")

    if method == "GET" and path == "/health":
        start, body = _json_response({"ok": True, "version": sys.version})
        await send(start)
        await send(body)
        return

    if method == "POST":
        payload = await _read_json_body(receive)
        if path == "/exec_script":
            res = await _handle_exec_script(payload)
        elif path == "/run_benchmark":
            res = await _handle_run_benchmark(payload)
        elif path == "/dys_format":
            res = await _handle_dys_format(payload)
        elif path == "/extract_function_schema":
            res = await _handle_extract_function_schema(payload)
        elif path == "/run_wsgi":
            res = await _handle_run_wsgi(payload)
        else:
            res = {
                "ok": False,
                "error": {"class": "NotFound", "msg": f"Unknown path: {path}"},
            }

        start, body = _json_response(res)
        await send(start)
        await send(body)
        return

    start, body = _json_response(
        {"ok": False, "error": {"class": "NotFound", "msg": "Unsupported route"}}
    )
    await send(start)
    await send(body)
