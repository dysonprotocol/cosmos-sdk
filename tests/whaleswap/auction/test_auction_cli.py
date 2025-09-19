import json


def test_open_auction_basic(chainnet, generate_account, faucet):
    dysond = chainnet[0]
    [seller_name, seller_addr] = generate_account("auc_seller")
    faucet(seller_addr, amount=2_000_000)

    # Open auction: escrow 100 udys for bids in ufoo
    tx = dysond(
        "tx",
        "whaleswap",
        "open-auction",
        "--bid-denom",
        "ufoo",
        "--sell",
        "100udys",
        "--from",
        seller_name,
    )
    assert tx.get("code", 1) == 0, f"open-auction failed: {json.dumps(tx, indent=2)}"

    # Extract auction_id
    evs = [
        e
        for e in tx.get("events", [])
        if e.get("type") == "dysonprotocol.whaleswap.v1.EventAuctionCreated"
    ]
    assert evs, f"EventAuctionCreated not found: {tx}"
    attrs = evs[0].get("attributes", [])
    aid_attr = [a for a in attrs if a.get("key") == "auction_id"]
    assert aid_attr, f"auction_id missing: {evs}"
    auction_id = int(aid_attr[0].get("value"))

    # Query auction
    q = dysond("query", "whaleswap", "auction", str(auction_id))
    auction = q.get("auction")
    assert auction, f"auction not found: {q}"
    assert auction["sell"]["denom"] == "udys", f"unexpected sell denom: {auction}"
    assert auction["bid_denom"] == "ufoo", f"unexpected bid denom: {auction}"
