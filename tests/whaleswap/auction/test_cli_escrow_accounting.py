from decimal import Decimal, ROUND_CEILING


def test_escrow_accounting_open_and_redeem(
    chainnet, generate_account, faucet, register_name
):
    dysond = chainnet[0]
    [seller_name, seller_addr] = generate_account("auc_escrow")
    faucet(seller_addr, amount=2_000_000)

    denom = register_name(dysond, seller_name, seller_addr, "200udys")
    params = dysond("query", "nameservice", "params")
    fee_per_unit = Decimal(params["params"]["mint_fee_per_coin"])  # e.g., 0.01
    units = Decimal(100)
    mint_fee = int((units * fee_per_unit).to_integral_value(rounding=ROUND_CEILING))
    mint = dysond(
        "tx",
        "nameservice",
        "mint-coins",
        "--amount",
        f"{int(units)}{denom}",
        "--mint-fee",
        f"{mint_fee}udys",
        "--from",
        seller_name,
    )
    assert mint.get("code", 1) == 0

    bal_before = dysond("query", "bank", "balances", seller_addr)
    map_before = {b["denom"]: int(b["amount"]) for b in bal_before.get("balances", [])}
    before_solid = map_before.get(denom, 0)
    assert before_solid >= int(units)

    sell_amount = 60
    tx = dysond(
        "tx",
        "whaleswap",
        "open-auction",
        "--bid-denom",
        "udys",
        "--sell",
        f"{sell_amount}{denom}",
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

    bal_after_open = dysond("query", "bank", "balances", seller_addr)
    map_after_open = {
        b["denom"]: int(b["amount"]) for b in bal_after_open.get("balances", [])
    }
    after_open_solid = map_after_open.get(denom, 0)
    assert before_solid - after_open_solid == sell_amount

    redeem = dysond(
        "tx",
        "whaleswap",
        "redeem-auction",
        "--auction-id",
        str(auction_id),
        "--from",
        seller_name,
    )
    assert redeem.get("code", 1) == 0

    bal_after_redeem = dysond("query", "bank", "balances", seller_addr)
    map_after_redeem = {
        b["denom"]: int(b["amount"]) for b in bal_after_redeem.get("balances", [])
    }
    after_redeem_solid = map_after_redeem.get(denom, 0)
    assert after_redeem_solid == before_solid
