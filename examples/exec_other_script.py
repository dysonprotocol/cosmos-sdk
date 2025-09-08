from dys import _msg, get_executor_address
import json


def demo_run_script(target_address="dys2123", function_name="foo", *args, **kwargs):
    """Execute function 'foo' on another script via MsgExec.

    Sends /dysonprotocol.script.v1.MsgExec to target script address with no args/kwargs.
    """
    return _msg(
        {
            "@type": "/dysonprotocol.script.v1.MsgExec",
            "executor_address": get_executor_address(),
            "script_address": target_address,
            "function_name": function_name,
            "args": json.dumps(args),
            "kwargs": json.dumps(kwargs),
        }
    )


