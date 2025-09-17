import json
import tempfile


def _script_exec(
    dysond_bin,
    script_addr,
    from_name,
    function_name,
    *,
    args="",
    kwargs="",
):
    tx = dysond_bin(
        "tx",
        "script",
        "exec",
        "--script-address",
        script_addr,
        "--function-name",
        function_name,
        "--args",
        args,
        "--kwargs",
        kwargs,
        "--gas",
        "auto",
        "--from",
        from_name,
    )
    assert tx.get("code", 1) == 0, f"Exec failed: {json.dumps(tx, indent=2)}"
    return tx


def _extract_script_result(wait_tx_json):
    events = wait_tx_json.get("events", [])
    exec_events = [
        e for e in events if e.get("type") == "dysonprotocol.script.v1.EventExecScript"
    ]
    assert (
        exec_events
    ), f"No EventExecScript found. Full events: {json.dumps(events, indent=2)}"
    attrs = exec_events[0].get("attributes", [])
    responses = [a for a in attrs if a.get("key") == "response"]
    assert (
        responses
    ), f"No response attribute. Event: {json.dumps(exec_events[0], indent=2)}"
    outer = json.loads(responses[0].get("value", "{}"))
    inner = json.loads(outer.get("result", "{}"))
    return inner.get("result")


def _deploy_with_dys_name(dysond, project_root, from_name, root_name):
    script_path = str(project_root / "demo-dex" / "script.py")
    with open(script_path, "r") as f:
        original = f.read()
    combined = original + f"\nDYS_NAME='{root_name}'\n"
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False)
    tmp.write(combined)
    tmp.flush()
    tx_upd = dysond(
        "tx",
        "script",
        "update",
        "--code-path",
        tmp.name,
        "--note",
        "deploy_demo_dex_take_cancel",
        "--gas",
        "auto",
        "--from",
        from_name,
    )
    assert (
        tx_upd.get("code", 1) == 0
    ), f"Script update failed: {json.dumps(tx_upd, indent=2)}"


def test_take_partial_then_full_and_cancel(
    chainnet, generate_account, faucet, project_root, dex_dys_name
):
    dysond = chainnet[0]

    maker_name, maker_addr = generate_account("maker")
    taker_name, taker_addr = generate_account("taker")
    faucet(maker_addr, denom="udys", amount=10_000_000)
    faucet(taker_addr, denom="udys", amount=10_000_000)

    dex_root = dex_dys_name(dysond, maker_name, maker_addr)

    _deploy_with_dys_name(dysond, project_root, maker_name, dex_root)

    have = f"{dex_root}/h"
    want = f"{dex_root}/w"

    # Fund both sides so make and take can succeed
    assert (
        dysond(
            "tx",
            "nameservice",
            "mint-coins",
            "--amount",
            f"100{have}",
            "--from",
            maker_name,
            "--note",
            "mint_have",
        ).get("code", 1)
        == 0
    )
    # Only the root owner can mint; mint want to maker, then send to taker
    assert (
        dysond(
            "tx",
            "nameservice",
            "mint-coins",
            "--amount",
            f"100{want}",
            "--from",
            maker_name,
            "--note",
            "mint_want_to_maker",
        ).get("code", 1)
        == 0
    )
    send_resp = dysond(
        "tx",
        "bank",
        "send",
        maker_name,
        taker_addr,
        f"100{want}",
        "--note",
        "send_want_to_taker",
    )
    assert (
        send_resp.get("code", 1) == 0
    ), f"bank send failed: {json.dumps(send_resp, indent=2)}"

    # Maker creates offer: give 30 have, want 45 want
    make_kwargs = json.dumps(
        {
            "have_coin": {"denom": have, "amount": 30},
            "want_coin": {"denom": want, "amount": 45},
        }
    )
    tx_make = _script_exec(dysond, maker_addr, maker_name, "make", kwargs=make_kwargs)
    result = _extract_script_result(tx_make)
    offer_id = result["offer_id"]

    # Partial take: 5 units (LCM(30,45)=90 -> unit_have=3, unit_want=2, remaining_units=10)
    # 5 units: taker sends 10 want, receives 15 have
    take_kwargs = json.dumps({"trades": [{"offer_id": offer_id, "take_units": 5}]})
    tx_take1 = _script_exec(dysond, maker_addr, taker_name, "take", kwargs=take_kwargs)
    res1 = _extract_script_result(tx_take1)
    inputs = res1.get("inputs", [])
    outputs = res1.get("outputs", [])
    partial_sent = sum(
        int(c.get("amount", 0))
        for e in inputs
        for c in e.get("coins", [])
        if e.get("address") == taker_addr and c.get("denom") == want
    )
    partial_recv = sum(
        int(c.get("amount", 0))
        for e in outputs
        for c in e.get("coins", [])
        if e.get("address") == taker_addr and c.get("denom") == have
    )
    assert (
        partial_sent == 15
    ), f"Partial take sent mismatch: {json.dumps(res1, indent=2)}"
    assert (
        partial_recv == 10
    ), f"Partial take received mismatch: {json.dumps(res1, indent=2)}"

    # Full remaining: 5 units remaining after first take (original 10 -> now 5)
    take_kwargs2 = json.dumps({"trades": [{"offer_id": offer_id}]})
    tx_take2 = _script_exec(dysond, maker_addr, taker_name, "take", kwargs=take_kwargs2)
    res2 = _extract_script_result(tx_take2)
    inputs = res2.get("inputs", [])
    outputs = res2.get("outputs", [])
    full_sent = sum(
        int(c.get("amount", 0))
        for e in inputs
        for c in e.get("coins", [])
        if e.get("address") == taker_addr and c.get("denom") == want
    )
    full_recv = sum(
        int(c.get("amount", 0))
        for e in outputs
        for c in e.get("coins", [])
        if e.get("address") == taker_addr and c.get("denom") == have
    )
    assert full_sent == 30, f"Full take sent mismatch: {json.dumps(res2, indent=2)}"
    assert full_recv == 20, f"Full take received mismatch: {json.dumps(res2, indent=2)}"

    # Create a second offer and then cancel it
    make_kwargs2 = json.dumps(
        {
            "have_coin": {"denom": have, "amount": 6},
            "want_coin": {"denom": want, "amount": 8},
        }
    )
    tx_make2 = _script_exec(dysond, maker_addr, maker_name, "make", kwargs=make_kwargs2)
    offer_id2 = _extract_script_result(tx_make2)["offer_id"]

    cancel_kwargs = json.dumps({"offer_id": offer_id2})
    tx_cancel = _script_exec(
        dysond, maker_addr, maker_name, "cancel", kwargs=cancel_kwargs
    )
    # cancel returns None; ensure tx success already asserted.
    assert (
        tx_cancel.get("code", 1) == 0
    ), f"Cancel failed: {json.dumps(tx_cancel, indent=2)}"
