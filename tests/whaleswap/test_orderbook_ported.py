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
    attached_messages=None,
):
    cmd = [
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
    ]
    for m in attached_messages or []:
        cmd += ["--attached-message", m]
    tx = dysond_bin(*cmd)
    assert tx.get("code", 1) == 0, f"Exec failed: {tx}"
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
    ), f"No response attribute. Full event: {json.dumps(exec_events[0], indent=2)}"
    outer = json.loads(responses[0].get("value", "{}"))
    inner = json.loads(outer.get("result", "{}"))
    return inner.get("result")


def test_make_happy_path(chainnet, generate_account, faucet, dex_dys_name):
    dysond = chainnet[0]

    maker_name, maker_addr = generate_account("maker")
    faucet(maker_addr, denom="udys", amount=10_000_000)

    dex_root = dex_dys_name(dysond, maker_name, maker_addr)

    # Deploy whaleswap with DYS_NAME
    with open("whaleswap/script.py", "r") as f:
        original = f.read()
    combined = original + f"\nDYS_NAME='{dex_root}'\n"
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
        "deploy_whaleswap_orderbook",
        "--gas",
        "auto",
        "--from",
        maker_name,
    )
    assert tx_upd.get("code", 1) == 0, f"Script update failed: {tx_upd}"

    # Create two custom denoms under maker's root for order-book
    have = f"{dex_root}/h"
    want = f"{dex_root}/w"
    m1 = dysond(
        "tx",
        "nameservice",
        "mint-coins",
        "--amount",
        f"100{have}",
        "--from",
        maker_name,
        "--mint-fee",
        "100000udys",
        "--note",
        "mint_have",
    )
    assert m1.get("code", 1) == 0, f"Mint have failed: {m1}"
    m2 = dysond(
        "tx",
        "nameservice",
        "mint-coins",
        "--amount",
        f"100{want}",
        "--from",
        maker_name,
        "--mint-fee",
        "100000udys",
        "--note",
        "mint_want",
    )
    assert m2.get("code", 1) == 0, f"Mint want failed: {m2}"

    # Maker posts an offer: give 30 have, want 45 want
    make_kwargs = json.dumps(
        {
            "have_coin": {"denom": have, "amount": 30},
            "want_coin": {"denom": want, "amount": 45},
        }
    )
    # Normal mode requires escrow of have via attached MsgSend to the script address
    attached_have = json.dumps(
        {
            "@type": "/cosmos.bank.v1beta1.MsgSend",
            "from_address": maker_addr,
            "to_address": maker_addr,
            "amount": [{"denom": have, "amount": "30"}],
        }
    )
    tx_make = _script_exec(
        dysond,
        maker_addr,
        maker_name,
        "make_offer",
        kwargs=make_kwargs,
        attached_messages=[attached_have],
    )
    result = _extract_script_result(tx_make)
    assert (
        "offer_id" in result
    ), f"Missing offer_id in result: {json.dumps(result, indent=2)}"
