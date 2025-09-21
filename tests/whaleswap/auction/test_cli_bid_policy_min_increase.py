from decimal import Decimal, ROUND_CEILING


def test_bid_policy_minimum_increase_enforced(
    chainnet, generate_account, faucet, register_name
):
    dysond = chainnet[0]
    [seller_name, seller_addr] = generate_account("auc_bid_min")
    faucet(seller_addr, amount=2_000_000)
    [bidder_name, bidder_addr] = generate_account("auc_bidder")
    faucet(bidder_addr, amount=2_000_000)

    denom = register_name(dysond, seller_name, seller_addr, "200udys")
    params = dysond("query", "nameservice", "params")
    fee_per_unit = Decimal(params["params"]["mint_fee_per_coin"])  # e.g., 0.01
    units = 20
    mint_fee = int(
        (Decimal(units) * fee_per_unit).to_integral_value(rounding=ROUND_CEILING)
    )
    mint = dysond(
        "tx",
        "nameservice",
        "mint-coins",
        "--amount",
        f"{units}{denom}",
        "--mint-fee",
        f"{mint_fee}udys",
        "--from",
        seller_name,
    )
    assert mint.get("code", 1) == 0

    tx = dysond(
        "tx",
        "whaleswap",
        "open-auction",
        "--bid-denom",
        "udys",
        "--sell",
        f"{units}{denom}",
        "--from",
        seller_name,
    )
    assert tx.get("code", 1) == 0
    evs = [
        e
        for e in tx.get("events", [])
        if e.get("type") == "dysonprotocol.whaleswap.v1.EventAuctionCreated"
    ]
    auction_id = int(
        str(
            [a for a in evs[0].get("attributes", []) if a.get("key") == "auction_id"][
                0
            ]["value"]
        ).strip('"')
    )
    class_id = "whaleswap.dys/auction/udys"
    nft_id = f"{auction_id:010d}"

    b1 = dysond(
        "tx",
        "nameservice",
        "place-bid",
        "--nft-class-id",
        class_id,
        "--nft-id",
        nft_id,
        "--bid-amount",
        "100udys",
        "--from",
        bidder_name,
    )
    assert b1.get("code", 1) == 0

    b2 = dysond(
        "tx",
        "nameservice",
        "place-bid",
        "--nft-class-id",
        class_id,
        "--nft-id",
        nft_id,
        "--bid-amount",
        "100udys",
        "--from",
        bidder_name,
    )
    assert b2.get("code", 0) != 0
