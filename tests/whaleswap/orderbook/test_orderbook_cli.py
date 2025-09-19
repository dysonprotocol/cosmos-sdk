import json


def test_make_offer_normal_escrow(chainnet, generate_account, faucet):
    dysond = chainnet[0]
    [maker_name, maker_addr] = generate_account("ob_maker")
    faucet(maker_addr, amount=2_000_000)

    # Ensure maker has have denom
    have = "100udys"
    want = "50ufoo"
    tx = dysond(
        "tx",
        "whaleswap",
        "make-offer",
        "--have",
        have,
        "--want",
        want,
        "--from",
        maker_name,
    )
    assert tx.get("code", 1) == 0, f"make-offer failed: {json.dumps(tx, indent=2)}"

    # Extract offer_id from events
    evs = [
        e
        for e in tx.get("events", [])
        if e.get("type") == "dysonprotocol.whaleswap.v1.EventOfferCreated"
    ]
    assert evs, f"EventOfferCreated not found: {tx}"
    attrs = evs[0].get("attributes", [])
    oid_attr = [a for a in attrs if a.get("key") == "offer_id"]
    assert oid_attr, f"offer_id missing: {evs}"
    offer_id = int(oid_attr[0].get("value"))

    # Query offer and validate open status
    q = dysond("query", "whaleswap", "offer", str(offer_id))
    offer = q.get("offer")
    assert offer, f"offer not found: {q}"
    assert offer["status"] == "open", f"unexpected status: {offer}"
