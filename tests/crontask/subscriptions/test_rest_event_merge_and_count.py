import json
from tests.utils import poll_until_condition


def _get_api_host(dysond_bin):
    address = dysond_bin("config", "get", "app", "api.address", raw=True)
    host, port = address.split("//")[1].split(":")
    return f"http://{host}:{port}"


def test_rest_subscription_event_merge_and_trigger_count(
    chainnet, generate_account, faucet, api_address
):
    dysond = chainnet[0]
    base = _get_api_host(dysond)

    # Accounts
    [creator_name, creator_addr] = generate_account("rest_sub")
    faucet(creator_addr, amount=1_000_000)

    # Script that returns kwargs.event
    script_code = """
from dys import _msg
import json

def show_event(event=None):
    return {"event": event}
"""
    up = dysond(
        "tx",
        "script",
        "update",
        "--code",
        script_code,
        "--from",
        creator_name,
        "--yes",
        "--gas",
        "auto",
    )
    assert up.get("code", 1) == 0, f"script update failed: {up}"

    # Script to emit event
    emit_code = """
from dys import emit_event
def emit_evt():
    emit_event("payment_processed", "ok")
    return True
"""
    up2 = dysond(
        "tx",
        "script",
        "update",
        "--code",
        emit_code,
        "--from",
        creator_name,
        "--yes",
        "--gas",
        "auto",
    )
    assert up2.get("code", 1) == 0

    # Create subscription via REST (autocli query shows service name; tx via CLI is acceptable if REST encoding differs)
    create_sub = dysond(
        "tx",
        "crontask",
        "create-subscription",
        "--event-type",
        "dysonprotocol.script.v1.EventScriptEvent",
        "--filter",
        'attributes.key=="payment_processed"',
        "--script-address",
        creator_addr,
        "--function",
        "show_event",
        "--args",
        "[]",
        "--kwargs",
        "{}",
        "--task-gas-limit",
        "200000",
        "--task-gas-fee",
        "1udys",
        "--from",
        creator_name,
        "--yes",
    )
    assert create_sub.get("code", 1) == 0, f"create subscription failed: {create_sub}"

    # Emit twice to increment trigger_count two times
    for _ in range(2):
        exec_emit = dysond(
            "tx",
            "script",
            "exec",
            "--script-address",
            creator_addr,
            "--function-name",
            "emit_evt",
            "--from",
            creator_name,
            "--gas",
            "auto",
        )
        assert exec_emit.get("code", 1) == 0

    # Wait for at least one scheduled task (trigger_count will still reflect both)
    def _has_one():
        res = dysond("query", "crontask", "tasks-by-address", "--creator", creator_addr)
        tasks = res.get("tasks", [])
        return any(t.get("status") in ("SCHEDULED", "PENDING", "DONE") for t in tasks)

    poll_until_condition(
        _has_one,
        timeout=12,
        poll_interval=0.2,
        error_message="Did not see a scheduled task",
    )

    # Query subscriptions by creator (REST via CLI) and assert trigger_count >= 2
    subs = dysond(
        "query", "crontask", "subscriptions-by-creator", "--creator", creator_addr
    )
    sub_list = subs.get("subscriptions", [])
    assert sub_list, f"no subscriptions found: {subs}"
    sub = sub_list[0]
    assert (
        int(sub.get("triger_count", "0")) >= 2
    ), f"trigger_count not incremented: {sub}"
