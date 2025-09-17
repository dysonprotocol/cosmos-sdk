import json
import tempfile
from decimal import Decimal, ROUND_CEILING


def _ceil_dec(x: Decimal) -> Decimal:
    return x.to_integral_value(rounding=ROUND_CEILING)


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


def _deploy_whaleswap_with_root(dysond, from_name, script_addr, root_name):
    with open("whaleswap/script.py", "r") as f:
        original = f.read()
    # Replace DYS_NAME inline to propagate to dependent constants
    updated = original.replace(
        'DYS_NAME = "whaleswap.dys"', f'DYS_NAME = "{root_name}"'
    )
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False)
    tmp.write(updated)
    tmp.flush()
    tx_upd = dysond(
        "tx",
        "script",
        "update",
        "--code-path",
        tmp.name,
        "--note",
        "deploy_whaleswap_amm",
        "--gas",
        "auto",
        "--from",
        from_name,
    )
    assert (
        tx_upd.get("code", 1) == 0
    ), f"Script update failed: {json.dumps(tx_upd, indent=2)}"


def test_amm_create_join_swap_exit(chainnet, generate_account, faucet, dex_dys_name):
    dysond = chainnet[0]

    maker_name, maker_addr = generate_account("maker")
    trader_name, trader_addr = generate_account("trader")
    faucet(maker_addr, denom="udys", amount=10_000_000)
    faucet(trader_addr, denom="udys", amount=10_000_000)

    dex_root = dex_dys_name(dysond, maker_name, maker_addr)
    _deploy_whaleswap_with_root(dysond, maker_name, maker_addr, dex_root)

    a = f"{dex_root}/a"
    b = f"{dex_root}/b"

    # Fund maker with tokens a and b
    assert (
        dysond(
            "tx",
            "nameservice",
            "mint-coins",
            "--amount",
            f"1000{a}",
            "--from",
            maker_name,
            "--mint-fee",
            "100000udys",
            "--note",
            "mint_a",
        ).get("code", 1)
        == 0
    )
    assert (
        dysond(
            "tx",
            "nameservice",
            "mint-coins",
            "--amount",
            f"1000{b}",
            "--from",
            maker_name,
            "--mint-fee",
            "100000udys",
            "--note",
            "mint_b",
        ).get("code", 1)
        == 0
    )

    # Compute fee per for share mint
    params = dysond("query", "nameservice", "params")
    fee_per = Decimal(params["params"]["mint_fee_per_coin"])  # e.g., 0.01

    # Create pool with initial liquidity (requires udys fee for initial share mint)
    create_kwargs = json.dumps(
        {"coin_a": {"denom": a, "amount": 100}, "coin_b": {"denom": b, "amount": 200}}
    )
    initial_shares = Decimal(100000)
    required_udys = _ceil_dec(initial_shares * fee_per)
    attach_fee = json.dumps(
        {
            "@type": "/cosmos.bank.v1beta1.MsgSend",
            "from_address": maker_addr,
            "to_address": maker_addr,
            "amount": [{"denom": "udys", "amount": str(required_udys)}],
        }
    )
    tx_create = _script_exec(
        dysond,
        maker_addr,
        maker_name,
        "create_pool",
        kwargs=create_kwargs,
        attached_messages=[attach_fee],
    )
    create_res = _extract_script_result(tx_create)
    assert (
        "pool_id" in create_res
    ), f"create_pool result: {json.dumps(create_res, indent=2)}"
    pool_id = create_res["pool_id"]

    # Join pool – attach a generous udys fee to cover minted shares
    join_kwargs = json.dumps(
        {
            "pool_id": pool_id,
            "coin1": {"denom": a, "amount": 150},
            "coin2": {"denom": b, "amount": 400},
        }
    )
    generous_udys = str(1_000_000)
    attach_fee2 = json.dumps(
        {
            "@type": "/cosmos.bank.v1beta1.MsgSend",
            "from_address": maker_addr,
            "to_address": maker_addr,
            "amount": [{"denom": "udys", "amount": generous_udys}],
        }
    )
    tx_join = _script_exec(
        dysond,
        maker_addr,
        maker_name,
        "join_pool",
        kwargs=join_kwargs,
        attached_messages=[attach_fee2],
    )
    join_res = _extract_script_result(tx_join)
    assert (
        join_res.get("pool_id") == pool_id and int(join_res.get("shares", 0)) > 0
    ), f"join_pool result: {json.dumps(join_res, indent=2)}"
    share_denom = join_res.get("share_denom")
    assert isinstance(share_denom, str) and share_denom.endswith(f"/pools/{pool_id}")

    # Send trader some token a to perform a swap a->b
    send_a = dysond(
        "tx",
        "bank",
        "send",
        maker_name,
        trader_addr,
        f"50{a}",
        "--note",
        "fund_trader_a",
    )
    assert send_a.get("code", 1) == 0, f"send a failed: {json.dumps(send_a, indent=2)}"

    # Swap a -> b through the single pool
    swap_kwargs = json.dumps(
        {
            "pool_ids_str": str(pool_id),
            "input_coin": {"denom": a, "amount": 10},
            "minimum_out_amount": 1,
            "out_denom": b,
        }
    )
    tx_swap = _script_exec(dysond, maker_addr, trader_name, "swap", kwargs=swap_kwargs)
    swap_res = _extract_script_result(tx_swap)
    assert (
        swap_res.get("denom") == b and int(swap_res.get("amount", 0)) > 0
    ), f"swap result: {json.dumps(swap_res, indent=2)}"

    # Exit part of the shares back to maker
    exit_kwargs = json.dumps(
        {
            "pool_id": pool_id,
            "shares_coin": {"denom": share_denom, "amount": 1000},
        }
    )
    tx_exit = _script_exec(
        dysond, maker_addr, maker_name, "exit_pool", kwargs=exit_kwargs
    )
    exit_res = _extract_script_result(tx_exit)
    assert (
        isinstance(exit_res, list) and len(exit_res) > 0
    ), f"exit result: {json.dumps(exit_res, indent=2)}"
