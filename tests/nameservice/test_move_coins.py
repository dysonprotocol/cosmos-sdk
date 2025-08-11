# 1
# 6-2 MoveCoins unit & failure path tests implemented in pytest

import json
import random
import string
import secrets

# Helper to keep coin lists lexicographically sorted by denom

def _sorted_coins(coins):
    return sorted(coins, key=lambda c: c["denom"])

# Fixture-provided helper register_name will be injected via test args

def _get_balance(dysond_bin, address, denom):
    bal_resp = dysond_bin("query", "bank", "balances", address)
    matching_coins = [c for c in bal_resp.get("balances", []) if c["denom"] == denom]
    return int(matching_coins[0]["amount"]) if matching_coins else 0


def _mint_variants(dysond_bin, owner_name, root_denom):
    """Mint multiple denom variants for tests (root, root/foo, root/bar)."""
    variants = [root_denom, f"{root_denom}/foo", f"{root_denom}/bar"]
    for d in variants:
        _mint_custom_coins(dysond_bin, owner_name, d, amount="100")
    return variants


# Local mint helper leveraged by tests
def _mint_custom_coins(dysond_bin, destination_name, denom, amount="100"):
    """Mint <amount><denom> coins to destination_name account."""
    mint_resp = dysond_bin(
        "tx",
        "nameservice",
        "mint-coins",
        "--amount",
        f"{amount}{denom}",
        "--from",
        destination_name,
    )
    assert mint_resp["code"] == 0, mint_resp.get("raw_log")


# ----------------------------- TESTS -----------------------------------

def test_move_coins_success(chainnet, generate_account, faucet, register_name):
    dysond_bin = chainnet[0]

    # Setup accounts
    [destination_name, destination_addr] = generate_account("destination")
    [recipient_name, recipient_addr] = generate_account("recipient")
    faucet(destination_addr, denom="udys", amount="25000")

    # Register name and mint coins under its denom
    root_name = register_name(dysond_bin, destination_name, destination_addr)
    denom = root_name  # custom denom matches root name

    _mint_custom_coins(dysond_bin, destination_name, denom, amount="100")

    # Pre balances
    pre_owner_bal = _get_balance(dysond_bin, destination_addr, denom)
    pre_rec_bal = _get_balance(dysond_bin, recipient_addr, denom)
    assert pre_owner_bal == 100, f"expected 100, got {pre_owner_bal}"
    assert pre_rec_bal == 0, f"recipient should have 0 {denom} prior"

    # Prepare move inputs/outputs JSON
    inputs = json.dumps({"address": destination_addr, "coins": [{"denom": denom, "amount": "50"}]})
    outputs = json.dumps({"address": recipient_addr, "coins": [{"denom": denom, "amount": "50"}]})

    tx_resp = dysond_bin(
        "tx",
        "nameservice",
        "move-coins",
        "--inputs",
        inputs,
        "--outputs",
        outputs,
        "--from",
        destination_name,
    )
    assert tx_resp["code"] == 0, tx_resp.get("raw_log")

    # Post balances
    post_owner_bal = _get_balance(dysond_bin, destination_addr, denom)
    post_rec_bal = _get_balance(dysond_bin, recipient_addr, denom)

    assert post_owner_bal == 50, f"owner balance should be 50, got {post_owner_bal}"
    assert post_rec_bal == 50, f"recipient balance should be 50, got {post_rec_bal}"


def test_move_coins_non_destination_fails(chainnet, generate_account, faucet, register_name):
    dysond_bin = chainnet[0]

    [destination_name, destination_addr] = generate_account("destination")
    [attacker_name, attacker_addr] = generate_account("attacker")
    faucet(destination_addr, denom="udys", amount="25000")
    faucet(attacker_addr, denom="udys", amount="1000")

    root_name = register_name(dysond_bin, destination_name, destination_addr)
    denom = root_name
    _mint_custom_coins(dysond_bin, destination_name, denom, amount="10")

    # Attempt move signed by attacker
    inputs = json.dumps({"address": destination_addr, "coins": [{"denom": denom, "amount": "5"}]})
    outputs = json.dumps({"address": attacker_addr, "coins": [{"denom": denom, "amount": "5"}]})

    tx_resp = dysond_bin(
        "tx",
        "nameservice",
        "move-coins",
        "--inputs",
        inputs,
        "--outputs",
        outputs,
        "--from",
        attacker_name,
    )
    # Expect failure (code != 0)
    assert tx_resp["code"] != 0, "non-destination signer should not be able to move coins"


def test_move_coins_module_account_fails(chainnet, generate_account, faucet, register_name):
    dysond_bin = chainnet[0]

    [destination_name, destination_addr] = generate_account("destination")
    faucet(destination_addr, denom="udys", amount="25000")

    root_name = register_name(dysond_bin, destination_name, destination_addr)
    denom = root_name
    _mint_custom_coins(dysond_bin, destination_name, denom, amount="20")

    # Fetch distribution module account address (non-user)
    dist_mod = dysond_bin("query", "auth", "module-account", "distribution")
    module_addr = dist_mod["account"]["value"]["address"]

    inputs = json.dumps({"address": destination_addr, "coins": [{"denom": denom, "amount": "10"}]})
    outputs = json.dumps({"address": module_addr, "coins": [{"denom": denom, "amount": "10"}]})

    tx_resp = dysond_bin(
        "tx",
        "nameservice",
        "move-coins",
        "--inputs",
        inputs,
        "--outputs",
        outputs,
        "--from",
        destination_name,
    )
    assert tx_resp["code"] != 0, "move to module account should fail"


def test_move_coins_multi_inputs_single_output(chainnet, generate_account, faucet, register_name):
    """Multiple inputs (different denoms) transferred to one destination."""
    dysond_bin = chainnet[0]
    [destination_name, destination_addr] = generate_account("destination_multi1")
    [sender2_name, sender2_addr] = generate_account("sender2")
    [recipient_name, recipient_addr] = generate_account("recipient_multi1")
    faucet(destination_addr, amount="30000", denom="udys")
    faucet(sender2_addr, amount="1000", denom="udys")

    root_name = register_name(dysond_bin, destination_name, destination_addr)
    variants = _mint_variants(dysond_bin, destination_name, root_name)

    # send some coins to sender2 so we have two distinct input addresses
    dysond_bin(
        "tx",
        "bank",
        "send",
        destination_name,
        sender2_addr,
        f"20{variants[1]}",
        "--yes",
    )

    # helper to keep coins sorted by denom (SDK requirement)
    def _sorted_coins(coins):
        return sorted(coins, key=lambda c: c["denom"])

    inputs_flags = [
        "--inputs",
        json.dumps({
            "address": destination_addr,
            "coins": _sorted_coins([
                {"denom": variants[0], "amount": "30"},
                {"denom": variants[2], "amount": "40"},
            ]),
        }),
        "--inputs",
        json.dumps({
            "address": sender2_addr,
            "coins": _sorted_coins([
                {"denom": variants[1], "amount": "20"},
            ]),
        }),
    ]

    output_obj = json.dumps({
        "address": recipient_addr,
        "coins": _sorted_coins([
            {"denom": variants[0], "amount": "30"},
            {"denom": variants[1], "amount": "20"},
            {"denom": variants[2], "amount": "40"},
        ]),
    })

    tx_resp = dysond_bin(
        "tx",
        "nameservice",
        "move-coins",
        *inputs_flags,
        "--outputs",
        output_obj,
        "--from",
        destination_name,
    )
    assert tx_resp["code"] == 0, tx_resp.get("raw_log")


def test_move_coins_single_input_multi_outputs(chainnet, generate_account, faucet, register_name):
    """Single input split across two outputs."""
    dysond_bin = chainnet[0]
    [destination_name, destination_addr] = generate_account("destination_multi2")
    [rec1_name, rec1_addr] = generate_account("rec1")
    [rec2_name, rec2_addr] = generate_account("rec2")
    faucet(destination_addr, amount="20000", denom="udys")

    root_name = register_name(dysond_bin, destination_name, destination_addr)
    _mint_custom_coins(dysond_bin, destination_name, root_name, amount="60")

    inputs_json = json.dumps({"address": destination_addr, "coins": [{"denom": root_name, "amount": "60"}]})

    outputs_flags = [
        "--outputs",
        json.dumps({
            "address": rec1_addr,
            "coins": _sorted_coins([{"denom": root_name, "amount": "25"}]),
        }),
        "--outputs",
        json.dumps({
            "address": rec2_addr,
            "coins": _sorted_coins([{"denom": root_name, "amount": "35"}]),
        }),
    ]

    tx_resp = dysond_bin(
        "tx",
        "nameservice",
        "move-coins",
        "--inputs",
        inputs_json,
        *outputs_flags,
        "--from",
        destination_name,
    )
    assert tx_resp["code"] == 0, tx_resp.get("raw_log")


def test_move_coins_total_mismatch_fails(chainnet, generate_account, faucet, register_name):
    """Validate transaction fails when total inputs ≠ total outputs."""
    dysond_bin = chainnet[0]
    [destination_name, destination_addr] = generate_account("destination_mismatch")
    faucet(destination_addr, denom="udys", amount="15000")

    root_name = register_name(dysond_bin, destination_name, destination_addr)
    _mint_custom_coins(dysond_bin, destination_name, root_name, amount="10")

    inputs = json.dumps({"address": destination_addr, "coins": [{"denom": root_name, "amount": "10"}]})
    outputs = json.dumps({"address": destination_addr, "coins": [{"denom": root_name, "amount": "9"}]})

    tx_resp = dysond_bin(
        "tx",
        "nameservice",
        "move-coins",
        "--inputs",
        inputs,
        "--outputs",
        outputs,
        "--from",
        destination_name,
    )
    assert tx_resp["code"] != 0, "tx with mismatched totals should fail" 