import types


if __name__ == "__main__":
    import sys

    if sys.argv[1] == "exec_script":
        from . import dysvm_server

        dysvm_server.main(*sys.argv[2:])

    elif sys.argv[1] == "run_wsgi":
        from . import dyswsgi

        dyswsgi.main(*sys.argv[2:])

    elif sys.argv[1] == "run_benchmark":
        import json
        from . import fp_benchmark

        iterations = int(sys.argv[2]) if len(sys.argv) > 2 else 100
        details = sys.argv[3].lower() == "true" if len(sys.argv) > 3 else True
        result = fp_benchmark.detect_fp_differences(iterations, details)
        print(json.dumps(result))

    elif sys.argv[1] == "dys_format":
        import black
        from . import DysEval

        code = sys.stdin.read()

        def _pos(exc):
            n = getattr(exc, "lineno", None)
            c = (
                getattr(exc, "offset", None)
                or getattr(exc, "col_offset", None)
                or getattr(exc, "colno", None)
            )
            if n is None:
                node = getattr(exc, "node", None)
                if node is not None:
                    n = getattr(node, "lineno", None)
                    c = getattr(node, "col_offset", None)
            return n, c

        try:
            DysEval().validate(code)
        except Exception as e:
            n, c = _pos(e)
            print(f"Error validating code: {e} line={n} col={c} type={type(e)}")
            sys.exit(1)

        try:
            formatted_code = black.format_str(code, mode=black.Mode())
            print(formatted_code)
        except Exception as e:
            n, c = _pos(e)
            if n is None:
                inner = getattr(e, "exc", None)
                if inner is not None:
                    n, c = _pos(inner)
            print(f"Error formatting code: {e} line={n} col={c}")
            sys.exit(1)

    elif sys.argv[1] == "extract_function_schema":
        import json
        from .dysvm_server import build_sandbox
        from .dysvm_server import get_module_dict  # for completeness
        from function_schema.core import get_function_schema

        # Args: script_json, block_info_json, port
        script = json.loads(sys.argv[2])
        block_info = json.loads(sys.argv[3])
        port = int(sys.argv[4]) if len(sys.argv) > 4 else 0

        # Minimal message context
        msg = {
            "executor_address": sys.argv[5],
            "function_name": "",
            "args": "[]",
            "kwargs": "{}",
            "extra_code": "",
            "attached_messages": [],
            "script_name": sys.argv[6],
        }

        # Build sandbox and evaluate the script code to populate scope
        sandbox = build_sandbox(
            msg=msg,
            script=script,
            attached_msg_results=[],
            block_info=block_info,
            port=port,
        )
        # Evaluate script code only
        sandbox.consume_gas()
        try:
            sandbox.eval(script.get("code", ""))
            sandbox.consume_gas()
        except Exception as e:
            print(
                f"Error evaluating script: {e} line={getattr(e, 'lineno', None)} col={getattr(e, 'col_offset', None)}"
            )
            sys.exit(1)

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
                    # If schema extraction fails for a function, include error string
                    result.append({"function_name": name, "error": str(e)})

        print(json.dumps(result, separators=(",", ":")), end="")
