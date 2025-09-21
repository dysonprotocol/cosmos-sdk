def test_open_auction_insufficient_funds(
    chainnet, generate_account, faucet, register_name
):
    dysond = chainnet[0]
    [seller_name, seller_addr] = generate_account("auc_insuf_open")
    faucet(seller_addr, amount=2_000_000)

    # Mint only 10 units of a denom, then try to open selling 20
    denom = register_name(dysond, seller_name, seller_addr, "200udys")
    params = dysond("query", "nameservice", "params")
    from decimal import Decimal, ROUND_CEILING

    fee_per_unit = Decimal(params["params"]["mint_fee_per_coin"])  # e.g., 0.01
    units = 10
    required_fee = int(
        (Decimal(units) * fee_per_unit).to_integral_value(rounding=ROUND_CEILING)
    )
    assert (
        dysond(
            "tx",
            "nameservice",
            "mint-coins",
            "--amount",
            f"{units}{denom}",
            "--mint-fee",
            f"{required_fee}udys",
            "--from",
            seller_name,
        ).get("code", 1)
        == 0
    )

    tx = dysond(
        "tx",
        "whaleswap",
        "open-auction",
        "--bid-denom",
        "udys",
        "--sell",
        f"20{denom}",
        "--from",
        seller_name,
    )
    assert tx.get("code", 0) != 0
