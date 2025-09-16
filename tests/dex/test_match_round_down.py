import json
from tests.utils import extract_script_result as _extract_script_result


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


def _get_balance(dysond_bin, address, denom):
    bal = dysond_bin("query", "bank", "balances", address)
    coins = [c for c in bal.get("balances", []) if c["denom"] == denom]
    return int(coins[0]["amount"]) if coins else 0


def test_match_round_down_overselects_offer(
    chainnet, generate_account, faucet, register_name, project_root
):
    dysond = chainnet[0]

    # Owner of the script and root name
    maker_name, maker_addr = generate_account("maker")
    faucet(maker_addr, denom="udys", amount=10_000_000)

    # Deploy DEX script at maker address
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

    # Register root and define pair denoms
    root = register_name(dysond, maker_name, maker_addr)
    have_denom = f"{root}/h"  # taker spends this
    want_denom = f"{root}/w"  # taker receives this

    # Mint balances to maker
    tx_mh = dysond(
        "tx",
        "nameservice",
        "mint-coins",
        "--amount",
        f"100{have_denom}",
        "--from",
        maker_name,
    )
    assert tx_mh.get("code", 1) == 0, f"Mint H failed: {tx_mh}"
    tx_mw = dysond(
        "tx",
        "nameservice",
        "mint-coins",
        "--amount",
        f"100{want_denom}",
        "--from",
        maker_name,
    )
    assert tx_mw.get("code", 1) == 0, f"Mint W failed: {tx_mw}"

    # Create taker and fund only 50 have_denom
    taker_name, taker_addr = generate_account("taker")
    tx_send = dysond(
        "tx", "bank", "send", maker_name, taker_addr, f"50{have_denom}", "--yes"
    )
    assert tx_send.get("code", 1) == 0, f"Send have_denom failed: {tx_send}"

    # Maker creates an offer: give 100 want_denom, want 80 have_denom
    make_kwargs = json.dumps(
        {
            "have_coin": {"denom": want_denom, "amount": 100},
            "want_coin": {"denom": have_denom, "amount": 80},
        }
    )
    tx_make = _script_exec(dysond, maker_addr, maker_name, "make", kwargs=make_kwargs)
    result_make = _extract_script_result(tx_make)
    offer_id = int(result_make["offer_id"])  # type: ignore[index]

    # Taker has 50 of have_denom. With offer (100 want_denom for 80 have_denom):
    # lcm(100,80)=400 => unit_have_int=400//80=5, unit_want_int=400//100=4.
    # Max affordable units with 50 have_denom: floor(50/4)=12 units.
    take_kwargs = json.dumps({"offer_id": offer_id, "take_units": 12})
    tx_take = _script_exec(dysond, maker_addr, taker_name, "take", kwargs=take_kwargs)
    result_take = _extract_script_result(tx_take)

    # Expect taker sends 12*4=48 have_denom, receives 12*5=60 want_denom
    assert (
        "sent" in result_take and "received" in result_take
    ), f"Unexpected take result shape: {json.dumps(result_take, indent=2)}"
    assert (
        result_take["sent"]["denom"] == have_denom
        and int(result_take["sent"]["amount"]) == 48
    ), f"Taker should send 48 {have_denom}. Full: {json.dumps(result_take, indent=2)}"
    assert (
        result_take["received"]["denom"] == want_denom
        and int(result_take["received"]["amount"]) == 60
    ), f"Taker should receive 60 {want_denom}. Full: {json.dumps(result_take, indent=2)}"

    # Final balances: taker have_denom 50-48=2; taker want_denom 0+60=60
    # maker have_denom 100-50 (sent) + 48 (received) = 98; maker want_denom 100-60=40
    taker_have = _get_balance(dysond, taker_addr, have_denom)
    taker_want = _get_balance(dysond, taker_addr, want_denom)
    maker_have = _get_balance(dysond, maker_addr, have_denom)
    maker_want = _get_balance(dysond, maker_addr, want_denom)
    assert taker_have == 2, f"taker {have_denom} expected 2, got {taker_have}"
    assert taker_want == 60, f"taker {want_denom} expected 60, got {taker_want}"
    assert maker_have == 98, f"maker {have_denom} expected 98, got {maker_have}"
    assert maker_want == 40, f"maker {want_denom} expected 40, got {maker_want}"
