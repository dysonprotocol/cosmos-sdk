import json
import random
from dys import _msg, get_script_address, get_executor_address


def jitter(value, pct=0.1, minimum=1):
    factor = (1.0 - pct) + (2 * pct) * random.random()
    j = int(value * factor)
    if minimum is not None and j < minimum:
        return minimum
    return j


def schedule_self(s="", delay=10, gas_limit=2000000, fee_amount=1):

    delay1 = jitter(delay,pct=0.5, minimum=10)
    delay2 = jitter(delay,pct=0.5, minimum=10)
    gas1 = jitter(gas_limit)
    gas2 = jitter(gas_limit)
    result1 = _msg(
        {
            "@type": "/dysonprotocol.crontask.v1.MsgCreateTask",
            "creator": get_executor_address(),
            "scheduled_timestamp": f"+{delay1}s",
            "expiry_timestamp": "+86400s",
            "task_gas_limit": str(gas1),
            "task_gas_fee": {"denom": "udys", "amount": str(fee_amount)},
            "msgs": [
                {
                    "@type": "/dysonprotocol.script.v1.MsgExec",
                    "executor_address": get_executor_address(),
                    "script_address": get_script_address(),
                    "function_name": "schedule_self",
                    "args": "[]",
                    "kwargs": json.dumps({
                        "s": s + "a",
                        "delay": delay1,
                        "gas_limit": gas1,
                        "fee_amount": fee_amount,
                    }),
                }
            ],
        }
    )

    result2 = _msg(
        {
            "@type": "/dysonprotocol.crontask.v1.MsgCreateTask",
            "creator": get_executor_address(),
            "scheduled_timestamp": f"+{delay2}s",
            "task_gas_limit": str(gas2),
            "task_gas_fee": {"denom": "udys", "amount": str(fee_amount)},
            "msgs": [
                {
                    "@type": "/dysonprotocol.script.v1.MsgExec",
                    "executor_address": get_executor_address(),
                    "script_address": get_script_address(),
                    "function_name": "schedule_self",
                    "args": "[]",
                    "kwargs": json.dumps({
                        "s": s + "b",
                        "delay": delay2,
                        "gas_limit": gas2,
                        "fee_amount": fee_amount,
                    }),
                }
            ],
        }
    )

    return f"s == '{s}' and "

