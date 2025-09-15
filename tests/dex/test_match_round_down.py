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
        "2000000",
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
        "2000000",
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
            "have": {"denom": want_denom, "amount": 100},
            "want": {"denom": have_denom, "amount": 80},
        }
    )
    tx_make = _script_exec(dysond, maker_addr, maker_name, "make", kwargs=make_kwargs)
    result_make = _extract_script_result(tx_make)
    offer_id = int(result_make["offer_id"])  # type: ignore[index]

    # Taker asks to match spending only 50 have_denom using round_down
    match_kwargs = json.dumps(
        {
            "have_denom": have_denom,
            "have_amount": 50,
            "want_denom": want_denom,
            "want_amount": None,
            "method": "round_down",
        }
    )
    tx_match = _script_exec(
        dysond, maker_addr, taker_name, "match", kwargs=match_kwargs
    )
    result_match = _extract_script_result(tx_match)

    # Desired behavior: do not include an offer requiring 80 when remaining is 50
    # Current code incorrectly includes it (bug). This assertion should fail until fixed.
    assert (
        result_match == []
    ), f"bug: round_down matched {result_match} but remaining < required (80)"
