from decimal import Decimal, ROUND_CEILING


def test_auction_class_policy_values_exact(
    chainnet, generate_account, faucet, register_name
):
    dysond = chainnet[0]
    [seller_name, seller_addr] = generate_account("auc_policy")
    faucet(seller_addr, amount=2_000_000)

    denom = register_name(dysond, seller_name, seller_addr, "200udys")
    params = dysond("query", "nameservice", "params")
    fee_per_unit = Decimal(params["params"]["mint_fee_per_coin"])  # e.g., 0.01
    units = 50
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

    wparams = dysond("query", "whaleswap", "params")["params"]
    class_id = "whaleswap.dys/auction/udys"
    cls = dysond("query", "nft", "class", class_id)
    data = ((cls.get("class", {})).get("data", {})).get("value", {})

    assert data.get("always_listed") is True
    assert data.get("allowed_denoms") == ["udys"]
    assert data.get("valuation_fee_pct") == wparams.get("valuation_fee_pct")
    assert data.get("valuation_period") == wparams.get("valuation_period")
    assert data.get("bid_timeout") == wparams.get("bid_timeout")
    assert data.get("minimum_bid_percent_increase") == wparams.get(
        "minimum_bid_percent_increase"
    )
