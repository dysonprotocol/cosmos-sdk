import types


def extract_function_schema(
    script, block_info, executor_address, script_name, rpc_port
):
    """Build a sandbox, evaluate script code, and extract public function schemas.

    Returns a list of {"function_name": str, "schema"|"error": any}.
    Raises exceptions from sandbox construction/evaluation to be handled by caller.
    """
    from .dysvm_server import build_sandbox
    from function_schema.core import get_function_schema

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
    # Evaluate script code only to populate scope
    sandbox.consume_gas()
    sandbox.eval(script.get("code", ""))
    sandbox.consume_gas()

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

    return result
