import json
import pytest


def test_open_auction_reject_liquid_sell(chainnet, generate_account, faucet):
    dysond = chainnet[0]
    [seller_name, seller_addr] = generate_account("auc_bad_liq_sell")
    faucet(seller_addr, amount=2_000_000)

    tx = dysond(
        "tx",
        "whaleswap",
        "open-auction",
        "--bid-denom",
        "udys",
        "--sell",
        "1whaleswap.dys/coins/udys",
        "--from",
        seller_name,
    )
    assert (
        tx.get("code", 0) != 0
    ), f"expected failure for liquid sell: {json.dumps(tx, indent=2)}"


def test_open_auction_reject_liquid_bid(chainnet, generate_account, faucet):
    dysond = chainnet[0]
    [seller_name, seller_addr] = generate_account("auc_bad_liq_bid")
    faucet(seller_addr, amount=2_000_000)

    tx = dysond(
        "tx",
        "whaleswap",
        "open-auction",
        "--bid-denom",
        "whaleswap.dys/coins/udys",
        "--sell",
        "1udys",
        "--from",
        seller_name,
    )
    assert (
        tx.get("code", 0) != 0
    ), f"expected failure for liquid bid: {json.dumps(tx, indent=2)}"


def test_open_auction_reject_equal_denoms(chainnet, generate_account, faucet):
    dysond = chainnet[0]
    [seller_name, seller_addr] = generate_account("auc_bad_equal")
    faucet(seller_addr, amount=2_000_000)

    tx = dysond(
        "tx",
        "whaleswap",
        "open-auction",
        "--bid-denom",
        "udys",
        "--sell",
        "100udys",
        "--from",
        seller_name,
    )
    assert (
        tx.get("code", 0) != 0
    ), f"expected failure for equal denoms: {json.dumps(tx, indent=2)}"


def test_open_auction_reject_invalid_denom(chainnet, generate_account, faucet):
    dysond = chainnet[0]
    [seller_name, seller_addr] = generate_account("auc_bad_denom")
    faucet(seller_addr, amount=2_000_000)

    with pytest.raises(Exception, match="invalid input format"):
        dysond(
            "tx",
            "whaleswap",
            "open-auction",
            "--bid-denom",
            "udys",
            "--sell",
            "1udys!",
            "--from",
            seller_name,
        )
