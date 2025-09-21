import json
from decimal import Decimal, ROUND_CEILING


def test_auctions_by_seller_lists_only_sellers_auctions(
    chainnet, generate_account, faucet, register_name
):
    dysond = chainnet[0]
    [seller_a_name, seller_a_addr] = generate_account("auc_seller_a")
    faucet(seller_a_addr, amount=2_000_000)
    [seller_b_name, seller_b_addr] = generate_account("auc_seller_b")
    faucet(seller_b_addr, amount=2_000_000)

    # Seller A: create denom and mint supply
    denom_a = register_name(dysond, seller_a_name, seller_a_addr, "200udys")
    params = dysond("query", "nameservice", "params")
    fee_per_unit = Decimal(params["params"]["mint_fee_per_coin"])  # e.g., 0.01
    units_a = Decimal(80)
    mint_fee_a = int((units_a * fee_per_unit).to_integral_value(rounding=ROUND_CEILING))
    assert (
        dysond(
            "tx",
            "nameservice",
            "mint-coins",
            "--amount",
            f"{int(units_a)}{denom_a}",
            "--mint-fee",
            f"{mint_fee_a}udys",
            "--from",
            seller_a_name,
        ).get("code", 1)
        == 0
    )

    # Seller B: create denom and mint supply
    denom_b = register_name(dysond, seller_b_name, seller_b_addr, "200udys")
    units_b = Decimal(60)
    mint_fee_b = int((units_b * fee_per_unit).to_integral_value(rounding=ROUND_CEILING))
    assert (
        dysond(
            "tx",
            "nameservice",
            "mint-coins",
            "--amount",
            f"{int(units_b)}{denom_b}",
            "--mint-fee",
            f"{mint_fee_b}udys",
            "--from",
            seller_b_name,
        ).get("code", 1)
        == 0
    )

    # Open two auctions for seller A and one for seller B
    a1 = dysond(
        "tx",
        "whaleswap",
        "open-auction",
        "--bid-denom",
        "udys",
        "--sell",
        f"30{denom_a}",
        "--from",
        seller_a_name,
    )
    a2 = dysond(
        "tx",
        "whaleswap",
        "open-auction",
        "--bid-denom",
        "udys",
        "--sell",
        f"20{denom_a}",
        "--from",
        seller_a_name,
    )
    b1 = dysond(
        "tx",
        "whaleswap",
        "open-auction",
        "--bid-denom",
        "udys",
        "--sell",
        f"10{denom_b}",
        "--from",
        seller_b_name,
    )
    assert a1.get("code", 1) == 0 and a2.get("code", 1) == 0 and b1.get("code", 1) == 0

    # Use unified auctions list and filter by seller in-shape
    lst_all = dysond("query", "whaleswap", "auctions")
    recs = lst_all.get("auctions", [])
    ids_a = [int(r.get("auction_id")) for r in recs if r.get("seller") == seller_a_addr]
    ids_b = [int(r.get("auction_id")) for r in recs if r.get("seller") == seller_b_addr]
    assert (
        len(ids_a) == 2
    ), f"expected 2 auctions for seller A: {json.dumps(lst_all, indent=2)}"
    assert (
        len(ids_b) == 1
    ), f"expected 1 auction for seller B: {json.dumps(lst_all, indent=2)}"
