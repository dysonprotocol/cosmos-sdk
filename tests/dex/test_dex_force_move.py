import json
from tests.utils import extract_script_result as _extract_script_result


def _get_balance(dysond_bin, address, denom):
    bal = dysond_bin("query", "bank", "balances", address)
    coins = [c for c in bal.get("balances", []) if c["denom"] == denom]
    return int(coins[0]["amount"]) if coins else 0


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
    assert tx.get("code", 1) == 0, f"Exec failed: {tx}"
    return tx


def test_dex_force_move_flow(
    chainnet, generate_account, faucet, register_name, project_root
):
    dysond = chainnet[0]

    # 1) Create maker (script owner) and fund
    maker_name, maker_addr = generate_account("maker")
    faucet(maker_addr, denom="udys", amount=10000000)

    # 2) Update script on maker's address
    script_path = str(project_root / "demo-dex" / "script.py")
    tx_upd = dysond(
        "tx",
        "script",
        "update",
        "--code-path",
        script_path,
        "--gas",
        "auto",
        "--from",
        maker_name,
    )
    assert tx_upd.get("code", 1) == 0, f"Script update failed: {tx_upd}"

    # 3) Register name (root) under maker
    root = register_name(dysond, maker_name, maker_addr)
    denom_a = f"{root}/a"
    denom_b = f"{root}/b"

    # 4) Mint two custom denoms to maker
    tx_m1 = dysond(
        "tx",
        "nameservice",
        "mint-coins",
        "--amount",
        f"100{denom_a}",
        "--from",
        maker_name,
    )
    assert tx_m1.get("code", 1) == 0, f"Mint A failed: {tx_m1}"
    tx_m2 = dysond(
        "tx",
        "nameservice",
        "mint-coins",
        "--amount",
        f"100{denom_b}",
        "--from",
        maker_name,
    )
    assert tx_m2.get("code", 1) == 0, f"Mint B failed: {tx_m2}"

    # 5) Create two user accounts and distribute coins
    acct1_name, acct1_addr = generate_account("acct1")
    acct2_name, acct2_addr = generate_account("acct2")

    # Send A to acct1, B to acct2
    tx_s1 = dysond(
        "tx", "bank", "send", maker_name, acct1_addr, f"60{denom_a}", "--yes"
    )
    assert tx_s1.get("code", 1) == 0, f"Send A failed: {tx_s1}"
    tx_s2 = dysond(
        "tx", "bank", "send", maker_name, acct2_addr, f"70{denom_b}", "--yes"
    )
    assert tx_s2.get("code", 1) == 0, f"Send B failed: {tx_s2}"

    # Baseline balances
    a1_a0 = _get_balance(dysond, acct1_addr, denom_a)
    a2_b0 = _get_balance(dysond, acct2_addr, denom_b)
    assert a1_a0 == 60, f"acct1 {denom_a} expected 60, got {a1_a0}"
    assert a2_b0 == 70, f"acct2 {denom_b} expected 70, got {a2_b0}"

    # 6) acct1 makes an offer: give 30 A, want 45 B
    make_kwargs = json.dumps(
        {
            "have_coin": {"denom": denom_a, "amount": 30},
            "want_coin": {"denom": denom_b, "amount": 45},
        }
    )
    tx_make = _script_exec(
        dysond,
        maker_addr,
        acct1_name,
        "make",
        kwargs=make_kwargs,
    )
    result_make = _extract_script_result(tx_make)
    offer_id = int(result_make["offer_id"])  # type: ignore[index]

    # 7) acct2 executes take as the taker (new API: take(trades=[{offer_id, take_units?}]))
    take_kwargs = json.dumps({"trades": [{"offer_id": offer_id}]})
    tx_take = _script_exec(dysond, maker_addr, acct2_name, "take", kwargs=take_kwargs)
    result_take = _extract_script_result(tx_take)
    # Expect taker inputs (send) and outputs (receive) aggregated in batched move
    inputs = result_take.get("inputs", [])
    outputs = result_take.get("outputs", [])
    sent_amt = sum(
        int(c.get("amount", 0))
        for e in inputs
        for c in e.get("coins", [])
        if e.get("address") == acct2_addr and c.get("denom") == denom_b
    )
    recv_amt = sum(
        int(c.get("amount", 0))
        for e in outputs
        for c in e.get("coins", [])
        if e.get("address") == acct2_addr and c.get("denom") == denom_a
    )
    assert (
        sent_amt == 45
    ), f"Taker should send 45 {denom_b}. Full: {json.dumps(result_take, indent=2)}"
    assert (
        recv_amt == 30
    ), f"Taker should receive 30 {denom_a}. Full: {json.dumps(result_take, indent=2)}"

    # 8) Final balances
    a1_a = _get_balance(dysond, acct1_addr, denom_a)
    a1_b = _get_balance(dysond, acct1_addr, denom_b)
    a2_a = _get_balance(dysond, acct2_addr, denom_a)
    a2_b = _get_balance(dysond, acct2_addr, denom_b)

    assert a1_a == 30, f"acct1 {denom_a} expected 30, got {a1_a}"
    assert a1_b == 45, f"acct1 {denom_b} expected 45, got {a1_b}"
    assert a2_a == 30, f"acct2 {denom_a} expected 30, got {a2_a}"
    assert a2_b == 25, f"acct2 {denom_b} expected 25, got {a2_b}"
