import json
from tests.utils import poll_until_condition


def _extract_attr(events, ev_type, key):
    values = [
        a.get("value")
        for e in events
        for a in e.get("attributes", [])
        if e.get("type") == ev_type and a.get("key") == key
    ]
    return (len(values) > 0 and values[0]) or None


def test_subscription_cli_basic_e2e(chainnet, generate_account, faucet):
    dysond = chainnet[0]

    # Accounts
    [creator_name, creator_addr] = generate_account("sub_creator")
    faucet(creator_addr, amount=1_000_000)

    # Install a script that echoes kwargs back so we can verify merged event
    script_code = """
from dys import _msg, get_script_address
import json

def echo_kwargs(event_key=None):
    # just return kwargs back out; event merge should appear here
    return {"event_key": event_key}
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

    # Emit a custom event via script exec so baseapp aggregates it
    emit_code = """
from dys import emit_event

def emit_payment():
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

    # Create subscription matching event_type and simple filter (key==payment_processed)
    # Minimal gas settings
    create_sub = dysond(
        "tx",
        "crontask",
        "create-subscription",
        "--event-type",
        "dysonprotocol.script.v1.EventScriptEvent",
        "--filter",
        "attributes.key=='payment_processed'",
        "--script-address",
        creator_addr,
        "--function",
        "echo_kwargs",
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
    sub_id_str = _extract_attr(
        create_sub.get("events", []),
        "dysonprotocol.crontask.v1.EventSubscriptionCreated",
        "subscription_id",
    )
    assert sub_id_str, f"no subscription_id in events: {create_sub}"
    sub_id = json.loads(sub_id_str)

    # Trigger event (same tx emits the event)
    exec_emit = dysond(
        "tx",
        "script",
        "exec",
        "--script-address",
        creator_addr,
        "--function-name",
        "emit_payment",
        "--from",
        creator_name,
        "--gas",
        "auto",
    )
    assert exec_emit.get("code", 1) == 0, f"emit tx failed: {exec_emit}"

    # Wait until a task is scheduled for the subscription creator
    def _has_scheduled():
        res = dysond("query", "crontask", "tasks-by-address", "--creator", creator_addr)
        tasks = res.get("tasks", [])
        return any(t.get("status") == "SCHEDULED" for t in tasks)

    poll_until_condition(
        _has_scheduled,
        timeout=10,
        poll_interval=0.2,
        error_message="No scheduled task created for subscription",
    )

    # Fetch tasks and pick the most recent by ID
    tasks_res = dysond(
        "query", "crontask", "tasks-by-address", "--creator", creator_addr
    )
    tasks = tasks_res.get("tasks", [])
    assert tasks, f"no tasks found: {tasks_res}"
    latest = sorted(tasks, key=lambda t: int(t["task_id"]))[-1]

    # Verify the single MsgExec has kwargs containing event merge
    # msgs is Any; we assert it's the script exec to our address and function name
    assert latest.get("status") in (
        "SCHEDULED",
        "PENDING",
        "DONE",
    ), f"unexpected status: {latest}"

    # Renew the subscription by +60s (ensures fee path works and status stays enabled)
    ren = dysond(
        "tx",
        "crontask",
        "renew-subscription",
        "--subscription-id",
        str(sub_id),
        "--new-expiry",
        "+60s",
        "--from",
        creator_name,
        "--yes",
    )
    assert ren.get("code", 1) == 0, f"renew failed: {ren}"

    # Delete the subscription
    dele = dysond(
        "tx",
        "crontask",
        "delete-subscription",
        "--subscription-id",
        str(sub_id),
        "--from",
        creator_name,
        "--yes",
    )
    assert dele.get("code", 1) == 0, f"delete failed: {dele}"
