import datetime
import json
from dys import _msg, _query, get_script_address, get_executor_address


def countdown(count=10):
    """Creates a countdown that repeats every 3 seconds"""
    # Convert to int in case passed as string from CLI
    print(f"Countdown: {count}")
    remaining = int(count)

    # Stop if we've reached zero
    if remaining <= 0:
        return "Countdown complete!"

    # Schedule next countdown for 3 seconds from now
    now = datetime.datetime.now()
    scheduled_time = int((now + datetime.timedelta(microseconds=0)).timestamp())
    expiry_time = int((now + datetime.timedelta(days=1)).timestamp())

    # Create a message to call this script again with count-1
    exec_script_msg = {
        "@type": "/dysonprotocol.script.v1.MsgExec",
        "executor_address": get_executor_address(),
        "script_address": get_script_address(),
        "function_name": "countdown",
        "args": json.dumps([remaining - 1]),
        "kwargs": "{}",
    }

    # Create crontask to execute our script again with decremented count
    result = _msg(
        {
            "@type": "/dysonprotocol.crontask.v1.MsgCreateTask",
            "creator": get_executor_address(),
            "scheduled_timestamp": str(scheduled_time),
            "expiry_timestamp": str(expiry_time),
            "task_gas_limit": "200000",
            "task_gas_fee": {"denom": "udys", "amount": "1"},
            "msgs": [exec_script_msg],
        }
    )

    return {
        "remaining": remaining,
        "next_execution": scheduled_time,
        "task_result": result,
    }
