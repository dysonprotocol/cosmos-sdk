from decimal import Decimal, ROUND_CEILING


def test_auction_class_reuse_and_id_sequencing(
    chainnet, generate_account, faucet, register_name
):
    dysond = chainnet[0]
    [seller1_name, seller1_addr] = generate_account("auc_seq_1")
    faucet(seller1_addr, amount=2_000_000)
    [seller2_name, seller2_addr] = generate_account("auc_seq_2")
    faucet(seller2_addr, amount=2_000_000)

    # Both sellers use the same bid denom udys, so class whaleswap.dys/auction/udys must be reused
    denom1 = register_name(dysond, seller1_name, seller1_addr, "200udys")
    denom2 = register_name(dysond, seller2_name, seller2_addr, "200udys")
    params = dysond("query", "nameservice", "params")
    fee_per_unit = Decimal(params["params"]["mint_fee_per_coin"])  # e.g., 0.01
    u1 = Decimal(30)
    u2 = Decimal(40)
    f1 = int((u1 * fee_per_unit).to_integral_value(rounding=ROUND_CEILING))
    f2 = int((u2 * fee_per_unit).to_integral_value(rounding=ROUND_CEILING))
    assert (
        dysond(
            "tx",
            "nameservice",
            "mint-coins",
            "--amount",
            f"{int(u1)}{denom1}",
            "--mint-fee",
            f"{f1}udys",
            "--from",
            seller1_name,
        ).get("code", 1)
        == 0
    )
    assert (
        dysond(
            "tx",
            "nameservice",
            "mint-coins",
            "--amount",
            f"{int(u2)}{denom2}",
            "--mint-fee",
            f"{f2}udys",
            "--from",
            seller2_name,
        ).get("code", 1)
        == 0
    )

    tx1 = dysond(
        "tx",
        "whaleswap",
        "open-auction",
        "--bid-denom",
        "udys",
        "--sell",
        f"{int(u1)}{denom1}",
        "--from",
        seller1_name,
    )
    tx2 = dysond(
        "tx",
        "whaleswap",
        "open-auction",
        "--bid-denom",
        "udys",
        "--sell",
        f"{int(u2)}{denom2}",
        "--from",
        seller2_name,
    )
    assert tx1.get("code", 1) == 0 and tx2.get("code", 1) == 0

    evs1 = [
        e
        for e in tx1.get("events", [])
        if e.get("type") == "dysonprotocol.whaleswap.v1.EventAuctionCreated"
    ]
    evs2 = [
        e
        for e in tx2.get("events", [])
        if e.get("type") == "dysonprotocol.whaleswap.v1.EventAuctionCreated"
    ]
    a1 = int(
        str(
            [a for a in evs1[0]["attributes"] if a.get("key") == "auction_id"][0][
                "value"
            ]
        ).strip('"')
    )
    a2 = int(
        str(
            [a for a in evs2[0]["attributes"] if a.get("key") == "auction_id"][0][
                "value"
            ]
        ).strip('"')
    )
    assert a2 > a1

    # Class exists and is the same
    class_id = "whaleswap.dys/auction/udys"
    cls = dysond("query", "nft", "class", class_id)
    assert cls.get("class", {}).get("id") == class_id
