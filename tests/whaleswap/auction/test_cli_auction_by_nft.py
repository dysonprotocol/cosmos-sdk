import json
from decimal import Decimal, ROUND_CEILING


def test_auction_by_nft_returns_exact_auction(
    chainnet, generate_account, faucet, register_name
):
    dysond = chainnet[0]
    [seller_name, seller_addr] = generate_account("auc_bynft")
    faucet(seller_addr, amount=2_000_000)

    denom = register_name(dysond, seller_name, seller_addr, "200udys")
    params = dysond("query", "nameservice", "params")
    fee_per_unit = Decimal(params["params"]["mint_fee_per_coin"])  # e.g., 0.01
    units = Decimal(40)
    mint_fee = int((units * fee_per_unit).to_integral_value(rounding=ROUND_CEILING))
    assert (
        dysond(
            "tx",
            "nameservice",
            "mint-coins",
            "--amount",
            f"{int(units)}{denom}",
            "--mint-fee",
            f"{mint_fee}udys",
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
        f"{int(units)}{denom}",
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

    q = dysond(
        "query",
        "whaleswap",
        "auction-by-nft",
        "--class-id",
        class_id,
        "--nft-id",
        nft_id,
    )
    rec = q.get("auction")
    assert (
        rec and int(rec.get("auction_id")) == auction_id
    ), f"by-nft mismatch: {json.dumps(q, indent=2)}"
