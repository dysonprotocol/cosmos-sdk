import json


def test_make_offer_normal_escrow(chainnet, generate_account, faucet, register_name):
    dysond = chainnet[0]
    [maker_name, maker_addr] = generate_account("ob_maker")
    faucet(maker_addr, amount=2_000_000)

    # Ensure a second denom exists by registering and minting a small supply
    name = register_name(dysond, maker_name, maker_addr, "1000udys")
    params = dysond("query", "nameservice", "params")
    fee_per_unit = float(params["params"]["mint_fee_per_coin"])  # e.g., 0.01
    units = 200
    required_fee = int(units * fee_per_unit)
    mint = dysond(
        "tx",
        "nameservice",
        "mint-coins",
        "--amount",
        f"{units}{name}",
        "--mint-fee",
        f"{required_fee}udys",
        "--from",
        maker_name,
    )
    assert mint.get("code", 1) == 0, f"mint-coins failed: {json.dumps(mint, indent=2)}"

    # Ensure maker has have denom
    have = "100udys"
    want = f"5{name}"
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


def test_take_offer_closes_offer(chainnet, generate_account, faucet, register_name):
    dysond = chainnet[0]
    # Maker and taker accounts
    [maker_name, maker_addr] = generate_account("ob_maker2")
    faucet(maker_addr, amount=2_000_000)
    [taker_name, taker_addr] = generate_account("ob_taker2")
    faucet(taker_addr, amount=1_000_000)

    # Create a custom solid denom and mint to maker for HAVE side
    name = register_name(dysond, maker_name, maker_addr, "1000udys")
    params = dysond("query", "nameservice", "params")
    fee_per_unit = float(params["params"]["mint_fee_per_coin"])  # e.g., 0.01
    units = 200
    required_fee = int(units * fee_per_unit)
    mint = dysond(
        "tx",
        "nameservice",
        "mint-coins",
        "--amount",
        f"{units}{name}",
        "--mint-fee",
        f"{required_fee}udys",
        "--from",
        maker_name,
    )
    assert mint.get("code", 1) == 0, f"mint-coins failed: {json.dumps(mint, indent=2)}"

    # Maker creates normal offer: have = custom denom, want = udys
    have = f"100{name}"
    want = "50udys"
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
    offer_id = int(oid_attr[0].get("value"))

    # Taker takes the full offer using repeated --trades flags
    take = dysond(
        "tx",
        "whaleswap",
        "take-offer",
        "--trades",
        f"offer_id={offer_id}",
        "--from",
        taker_name,
    )
    assert take.get("code", 1) == 0, f"take-offer failed: {json.dumps(take, indent=2)}"

    # Offer should be closed now
    q = dysond("query", "whaleswap", "offer", str(offer_id))
    offer = q.get("offer")
    assert (
        offer and offer["status"] == "closed"
    ), f"offer not closed: {json.dumps(q, indent=2)}"


def test_take_mode_first_executes_only_first_feasible(
    chainnet, generate_account, faucet, register_name
):
    dysond = chainnet[0]
    [maker1_name, maker1_addr] = generate_account("ob_maker_first1")
    faucet(maker1_addr, amount=2_000_000)
    [maker2_name, maker2_addr] = generate_account("ob_maker_first2")
    faucet(maker2_addr, amount=2_000_000)
    [taker_name, taker_addr] = generate_account("ob_taker_first")
    faucet(taker_addr, amount=1_000_000)

    # Register and mint custom denom for maker1 (HAVE side)
    name = register_name(dysond, maker1_name, maker1_addr, "1000udys")
    params = dysond("query", "nameservice", "params")
    fee_per_unit = float(params["params"]["mint_fee_per_coin"])  # e.g., 0.01
    units = 200
    required_fee = int(units * fee_per_unit)
    assert (
        dysond(
            "tx",
            "nameservice",
            "mint-coins",
            "--amount",
            f"{units}{name}",
            "--mint-fee",
            f"{required_fee}udys",
            "--from",
            maker1_name,
        ).get("code", 1)
        == 0
    )

    # Offer A (feasible): maker1 have=name, want=udys
    tx_a = dysond(
        "tx",
        "whaleswap",
        "make-offer",
        "--have",
        f"100{name}",
        "--want",
        "50udys",
        "--from",
        maker1_name,
    )
    assert (
        tx_a.get("code", 1) == 0
    ), f"make-offer A failed: {json.dumps(tx_a, indent=2)}"
    evs_a = [
        e
        for e in tx_a.get("events", [])
        if e.get("type") == "dysonprotocol.whaleswap.v1.EventOfferCreated"
    ]
    offer_a = int(
        [a for a in evs_a[0]["attributes"] if a.get("key") == "offer_id"][0]["value"]
    )

    # Offer B (infeasible for taker): maker2 has udys, but wants custom denom `name` which taker lacks
    tx_b = dysond(
        "tx",
        "whaleswap",
        "make-offer",
        "--have",
        "100udys",
        "--want",
        f"999999{name}",
        "--from",
        maker2_name,
    )
    assert (
        tx_b.get("code", 1) == 0
    ), f"make-offer B failed: {json.dumps(tx_b, indent=2)}"
    evs_b = [
        e
        for e in tx_b.get("events", [])
        if e.get("type") == "dysonprotocol.whaleswap.v1.EventOfferCreated"
    ]
    offer_b = int(
        [a for a in evs_b[0]["attributes"] if a.get("key") == "offer_id"][0]["value"]
    )

    # Without modes, a batch containing an infeasible leg must fail (atomic all-or-nothing)
    take_tx = dysond(
        "tx",
        "whaleswap",
        "take-offer",
        "--trades",
        f"offer_id={offer_b}",
        "--trades",
        f"offer_id={offer_a}",
        "--from",
        taker_name,
    )
    assert (
        take_tx.get("code", 0) != 0
    ), f"batch should fail: {json.dumps(take_tx, indent=2)}"
    qa = dysond("query", "whaleswap", "offer", str(offer_a))
    qb = dysond("query", "whaleswap", "offer", str(offer_b))
    assert (
        qa.get("offer", {}).get("status") == "open"
    ), f"A should remain open: {json.dumps(qa, indent=2)}"
    assert (
        qb.get("offer", {}).get("status") == "open"
    ), f"B should remain open: {json.dumps(qb, indent=2)}"

    # Taking only the feasible A should succeed and close A
    take_a = dysond(
        "tx",
        "whaleswap",
        "take-offer",
        "--trades",
        f"offer_id={offer_a}",
        "--from",
        taker_name,
    )
    assert (
        take_a.get("code", 1) == 0
    ), f"take-offer(A) failed: {json.dumps(take_a, indent=2)}"
    qa = dysond("query", "whaleswap", "offer", str(offer_a))
    qb = dysond("query", "whaleswap", "offer", str(offer_b))
    assert (
        qa.get("offer", {}).get("status") == "closed"
    ), f"A not closed: {json.dumps(qa, indent=2)}"
    assert (
        qb.get("offer", {}).get("status") == "open"
    ), f"B should remain open: {json.dumps(qb, indent=2)}"


def test_take_mode_any_executes_feasible_subset(
    chainnet, generate_account, faucet, register_name
):
    dysond = chainnet[0]
    [maker1_name, maker1_addr] = generate_account("ob_maker_any1")
    faucet(maker1_addr, amount=2_000_000)
    [maker2_name, maker2_addr] = generate_account("ob_maker_any2")
    faucet(maker2_addr, amount=2_000_000)
    [taker_name, taker_addr] = generate_account("ob_taker_any")
    faucet(taker_addr, amount=1_000_000)

    name = register_name(dysond, maker1_name, maker1_addr, "1000udys")
    params = dysond("query", "nameservice", "params")
    fee_per_unit = float(params["params"]["mint_fee_per_coin"])  # e.g., 0.01
    units = 200
    required_fee = int(units * fee_per_unit)
    assert (
        dysond(
            "tx",
            "nameservice",
            "mint-coins",
            "--amount",
            f"{units}{name}",
            "--mint-fee",
            f"{required_fee}udys",
            "--from",
            maker1_name,
        ).get("code", 1)
        == 0
    )

    # A feasible, B infeasible (wants custom denom `name` which taker lacks)
    tx_a = dysond(
        "tx",
        "whaleswap",
        "make-offer",
        "--have",
        f"50{name}",
        "--want",
        "25udys",
        "--from",
        maker1_name,
    )
    tx_b = dysond(
        "tx",
        "whaleswap",
        "make-offer",
        "--have",
        "50udys",
        "--want",
        f"999999{name}",
        "--from",
        maker2_name,
    )
    assert tx_a.get("code", 1) == 0 and tx_b.get("code", 1) == 0
    offer_a = int(
        [
            a
            for e in tx_a.get("events", [])
            if e.get("type") == "dysonprotocol.whaleswap.v1.EventOfferCreated"
            for a in e["attributes"]
            if a.get("key") == "offer_id"
        ][0]["value"]
    )
    offer_b = int(
        [
            a
            for e in tx_b.get("events", [])
            if e.get("type") == "dysonprotocol.whaleswap.v1.EventOfferCreated"
            for a in e["attributes"]
            if a.get("key") == "offer_id"
        ][0]["value"]
    )

    # Batch with infeasible leg must fail; then taking only feasible A should succeed
    take_tx = dysond(
        "tx",
        "whaleswap",
        "take-offer",
        "--trades",
        f"offer_id={offer_b}",
        "--trades",
        f"offer_id={offer_a}",
        "--from",
        taker_name,
    )
    assert (
        take_tx.get("code", 0) != 0
    ), f"batch should fail: {json.dumps(take_tx, indent=2)}"
    qa = dysond("query", "whaleswap", "offer", str(offer_a))
    qb = dysond("query", "whaleswap", "offer", str(offer_b))
    assert (
        qa.get("offer", {}).get("status") == "open"
    ), f"A should remain open: {json.dumps(qa, indent=2)}"
    assert (
        qb.get("offer", {}).get("status") == "open"
    ), f"B should remain open: {json.dumps(qb, indent=2)}"

    take_a = dysond(
        "tx",
        "whaleswap",
        "take-offer",
        "--trades",
        f"offer_id={offer_a}",
        "--from",
        taker_name,
    )
    assert (
        take_a.get("code", 1) == 0
    ), f"take-offer(A) failed: {json.dumps(take_a, indent=2)}"
    qa = dysond("query", "whaleswap", "offer", str(offer_a))
    qb = dysond("query", "whaleswap", "offer", str(offer_b))
    assert (
        qa.get("offer", {}).get("status") == "closed"
    ), f"A not closed: {json.dumps(qa, indent=2)}"
    assert (
        qb.get("offer", {}).get("status") == "open"
    ), f"B should remain open: {json.dumps(qb, indent=2)}"


def test_take_mode_all_requires_all_success(
    chainnet, generate_account, faucet, register_name
):
    dysond = chainnet[0]
    [maker1_name, maker1_addr] = generate_account("ob_maker_all1")
    faucet(maker1_addr, amount=2_000_000)
    [maker2_name, maker2_addr] = generate_account("ob_maker_all2")
    faucet(maker2_addr, amount=2_000_000)
    [taker_name, taker_addr] = generate_account("ob_taker_all")
    faucet(taker_addr, amount=1_000_000)

    name = register_name(dysond, maker1_name, maker1_addr, "1000udys")
    params = dysond("query", "nameservice", "params")
    fee_per_unit = float(params["params"]["mint_fee_per_coin"])  # e.g., 0.01
    units = 200
    required_fee = int(units * fee_per_unit)
    assert (
        dysond(
            "tx",
            "nameservice",
            "mint-coins",
            "--amount",
            f"{units}{name}",
            "--mint-fee",
            f"{required_fee}udys",
            "--from",
            maker1_name,
        ).get("code", 1)
        == 0
    )

    tx_a = dysond(
        "tx",
        "whaleswap",
        "make-offer",
        "--have",
        f"50{name}",
        "--want",
        "25udys",
        "--from",
        maker1_name,
    )
    tx_b = dysond(
        "tx",
        "whaleswap",
        "make-offer",
        "--have",
        "50udys",
        "--want",
        f"999999{name}",
        "--from",
        maker2_name,
    )
    assert tx_a.get("code", 1) == 0 and tx_b.get("code", 1) == 0
    offer_a = int(
        [
            a
            for e in tx_a.get("events", [])
            if e.get("type") == "dysonprotocol.whaleswap.v1.EventOfferCreated"
            for a in e["attributes"]
            if a.get("key") == "offer_id"
        ][0]["value"]
    )
    offer_b = int(
        [
            a
            for e in tx_b.get("events", [])
            if e.get("type") == "dysonprotocol.whaleswap.v1.EventOfferCreated"
            for a in e["attributes"]
            if a.get("key") == "offer_id"
        ][0]["value"]
    )

    take_tx = dysond(
        "tx",
        "whaleswap",
        "take-offer",
        "--trades",
        f"offer_id={offer_b}",
        "--trades",
        f"offer_id={offer_a}",
        "--from",
        taker_name,
    )
    assert (
        take_tx.get("code", 1) != 0
    ), f"batch should fail when any trade infeasible: {json.dumps(take_tx, indent=2)}"


def test_ring_coincidence_of_wants(chainnet, generate_account, faucet, register_name):
    dysond = chainnet[0]
    [maker_a_name, maker_a_addr] = generate_account("ring_maker_a")
    [maker_b_name, maker_b_addr] = generate_account("ring_maker_b")
    [maker_c_name, maker_c_addr] = generate_account("ring_maker_c")
    [taker_name, taker_addr] = generate_account("ring_taker")
    faucet(maker_a_addr, amount=2_000_000)
    faucet(maker_b_addr, amount=2_000_000)
    faucet(maker_c_addr, amount=2_000_000)
    faucet(taker_addr, amount=1_000_000)

    # Create three custom solid denoms and mint supply
    coin_a = register_name(dysond, maker_a_name, maker_a_addr, "1000udys")
    coin_b = register_name(dysond, maker_b_name, maker_b_addr, "1000udys")
    coin_c = register_name(dysond, maker_c_name, maker_c_addr, "1000udys")
    params = dysond("query", "nameservice", "params")
    fee_per_unit = float(params["params"]["mint_fee_per_coin"])
    units = 200
    required_fee = int(units * fee_per_unit)
    assert (
        dysond(
            "tx",
            "nameservice",
            "mint-coins",
            "--amount",
            f"{units}{coin_a}",
            "--mint-fee",
            f"{required_fee}udys",
            "--from",
            maker_a_name,
        ).get("code", 1)
        == 0
    )
    assert (
        dysond(
            "tx",
            "nameservice",
            "mint-coins",
            "--amount",
            f"{units}{coin_b}",
            "--mint-fee",
            f"{required_fee}udys",
            "--from",
            maker_b_name,
        ).get("code", 1)
        == 0
    )
    assert (
        dysond(
            "tx",
            "nameservice",
            "mint-coins",
            "--amount",
            f"{units}{coin_c}",
            "--mint-fee",
            f"{required_fee}udys",
            "--from",
            maker_c_name,
        ).get("code", 1)
        == 0
    )

    # Offers: A: 2A->1B, B: 2B->1C, C: 2C->1A
    tx_a = dysond(
        "tx",
        "whaleswap",
        "make-offer",
        "--have",
        f"2{coin_a}",
        "--want",
        f"1{coin_b}",
        "--from",
        maker_a_name,
    )
    tx_b = dysond(
        "tx",
        "whaleswap",
        "make-offer",
        "--have",
        f"2{coin_b}",
        "--want",
        f"1{coin_c}",
        "--from",
        maker_b_name,
    )
    tx_c = dysond(
        "tx",
        "whaleswap",
        "make-offer",
        "--have",
        f"2{coin_c}",
        "--want",
        f"1{coin_a}",
        "--from",
        maker_c_name,
    )
    assert (
        tx_a.get("code", 1) == 0
        and tx_b.get("code", 1) == 0
        and tx_c.get("code", 1) == 0
    )

    def _offer_id(tx):
        evs = [
            e
            for e in tx.get("events", [])
            if e.get("type") == "dysonprotocol.whaleswap.v1.EventOfferCreated"
        ]
        attrs = evs[0].get("attributes", [])
        oid_attr = [a for a in attrs if a.get("key") == "offer_id"]
        return int(oid_attr[0].get("value"))

    offer_a = _offer_id(tx_a)
    offer_b = _offer_id(tx_b)
    offer_c = _offer_id(tx_c)

    take_tx = dysond(
        "tx",
        "whaleswap",
        "take-offer",
        "--trades",
        f"offer_id={offer_a}",
        "--trades",
        f"offer_id={offer_b}",
        "--trades",
        f"offer_id={offer_c}",
        "--from",
        taker_name,
    )
    assert (
        take_tx.get("code", 1) == 0
    ), f"ring take failed: {json.dumps(take_tx, indent=2)}"

    # All offers closed
    qa = dysond("query", "whaleswap", "offer", str(offer_a))
    qb = dysond("query", "whaleswap", "offer", str(offer_b))
    qc = dysond("query", "whaleswap", "offer", str(offer_c))
    assert (
        qa.get("offer", {}).get("status") == "closed"
    ), f"A not closed: {json.dumps(qa, indent=2)}"
    assert (
        qb.get("offer", {}).get("status") == "closed"
    ), f"B not closed: {json.dumps(qb, indent=2)}"
    assert (
        qc.get("offer", {}).get("status") == "closed"
    ), f"C not closed: {json.dumps(qc, indent=2)}"

    # Taker net balances: +1 of each custom denom
    bals = dysond("query", "bank", "balances", taker_addr)
    by_denom = {b.get("denom"): int(b.get("amount")) for b in bals.get("balances", [])}
    assert (
        by_denom.get(coin_a, 0) == 1
    ), f"taker coin_a != 1: {json.dumps(bals, indent=2)}"
    assert (
        by_denom.get(coin_b, 0) == 1
    ), f"taker coin_b != 1: {json.dumps(bals, indent=2)}"
    assert (
        by_denom.get(coin_c, 0) == 1
    ), f"taker coin_c != 1: {json.dumps(bals, indent=2)}"


def test_ring_with_liquid_and_pfand(chainnet, generate_account, faucet, register_name):
    dysond = chainnet[0]
    [maker_a_name, maker_a_addr] = generate_account("ringL_maker_a")
    [maker_b_name, maker_b_addr] = generate_account("ringL_maker_b")
    [maker_c_name, maker_c_addr] = generate_account("ringL_maker_c")
    [taker_name, taker_addr] = generate_account("ringL_taker")
    faucet(maker_a_addr, amount=2_000_000)
    faucet(maker_b_addr, amount=2_000_000)
    faucet(maker_c_addr, amount=2_000_000)
    faucet(taker_addr, amount=1_000_000)

    # Create denoms and mint supply
    coin_a = register_name(dysond, maker_a_name, maker_a_addr, "1000udys")
    coin_b = register_name(dysond, maker_b_name, maker_b_addr, "1000udys")
    coin_c = register_name(dysond, maker_c_name, maker_c_addr, "1000udys")
    params = dysond("query", "nameservice", "params")
    fee_per_unit = float(params["params"]["mint_fee_per_coin"])
    units = 200
    required_fee = int(units * fee_per_unit)
    assert (
        dysond(
            "tx",
            "nameservice",
            "mint-coins",
            "--amount",
            f"{units}{coin_a}",
            "--mint-fee",
            f"{required_fee}udys",
            "--from",
            maker_a_name,
        ).get("code", 1)
        == 0
    )
    assert (
        dysond(
            "tx",
            "nameservice",
            "mint-coins",
            "--amount",
            f"{units}{coin_b}",
            "--mint-fee",
            f"{required_fee}udys",
            "--from",
            maker_b_name,
        ).get("code", 1)
        == 0
    )
    assert (
        dysond(
            "tx",
            "nameservice",
            "mint-coins",
            "--amount",
            f"{units}{coin_c}",
            "--mint-fee",
            f"{required_fee}udys",
            "--from",
            maker_c_name,
        ).get("code", 1)
        == 0
    )

    # Convert makers' haves to liquid and open liquid-have offers (pfand will be locked per params)
    def ldenom(d):
        return f"whaleswap.dys/coins/{d}"

    for mname, denom in [
        (maker_a_name, coin_a),
        (maker_b_name, coin_b),
        (maker_c_name, coin_c),
    ]:
        res = dysond(
            "tx",
            "whaleswap",
            "convert-to-liquid",
            "--denom",
            denom,
            "--amount",
            "2",
            "--from",
            mname,
        )
        assert (
            res.get("code", 1) == 0
        ), f"convert-to-liquid failed: {json.dumps(res, indent=2)}"

    # Offers: use liquid have
    tx_a = dysond(
        "tx",
        "whaleswap",
        "make-offer",
        "--have",
        f"2{ldenom(coin_a)}",
        "--want",
        f"1{coin_b}",
        "--from",
        maker_a_name,
    )
    tx_b = dysond(
        "tx",
        "whaleswap",
        "make-offer",
        "--have",
        f"2{ldenom(coin_b)}",
        "--want",
        f"1{coin_c}",
        "--from",
        maker_b_name,
    )
    tx_c = dysond(
        "tx",
        "whaleswap",
        "make-offer",
        "--have",
        f"2{ldenom(coin_c)}",
        "--want",
        f"1{coin_a}",
        "--from",
        maker_c_name,
    )
    assert (
        tx_a.get("code", 1) == 0
        and tx_b.get("code", 1) == 0
        and tx_c.get("code", 1) == 0
    )

    def _offer_id(tx):
        evs = [
            e
            for e in tx.get("events", [])
            if e.get("type") == "dysonprotocol.whaleswap.v1.EventOfferCreated"
        ]
        attrs = evs[0].get("attributes", [])
        oid_attr = [a for a in attrs if a.get("key") == "offer_id"]
        return int(oid_attr[0].get("value"))

    offer_a = _offer_id(tx_a)
    offer_b = _offer_id(tx_b)
    offer_c = _offer_id(tx_c)

    take_tx = dysond(
        "tx",
        "whaleswap",
        "take-offer",
        "--trades",
        f"offer_id={offer_a}",
        "--trades",
        f"offer_id={offer_b}",
        "--trades",
        f"offer_id={offer_c}",
        "--from",
        taker_name,
    )
    assert (
        take_tx.get("code", 1) == 0
    ), f"ring liquid take failed: {json.dumps(take_tx, indent=2)}"

    # All offers closed; taker gets solid coins and pfand released
    qa = dysond("query", "whaleswap", "offer", str(offer_a))
    qb = dysond("query", "whaleswap", "offer", str(offer_b))
    qc = dysond("query", "whaleswap", "offer", str(offer_c))
    assert qa.get("offer", {}).get("status") == "closed"
    assert qb.get("offer", {}).get("status") == "closed"
    assert qc.get("offer", {}).get("status") == "closed"

    bals = dysond("query", "bank", "balances", taker_addr)
    by_denom = {b.get("denom"): int(b.get("amount")) for b in bals.get("balances", [])}
    assert by_denom.get(coin_a, 0) >= 1
    assert by_denom.get(coin_b, 0) >= 1
    assert by_denom.get(coin_c, 0) >= 1

    # Pfand per liquid offer accumulates to taker on close
    p = dysond("query", "whaleswap", "params")
    pf = p.get("params", {}).get("pfand_per_offer", {})
    pf_denom = pf.get("denom")
    pf_amt = int(pf.get("amount", "0"))
    expected_min = pf_amt * 3
    assert (
        by_denom.get(pf_denom, 0) >= expected_min
    ), f"taker pfand < expected (can be zero if pfand disabled): {json.dumps({'bals':bals,'pf':p}, indent=2)}"


def test_partial_fill_exact_units(chainnet, generate_account, faucet, register_name):
    dysond = chainnet[0]
    [maker_name, maker_addr] = generate_account("ob_pf_maker")
    faucet(maker_addr, amount=2_000_000)
    [taker_name, taker_addr] = generate_account("ob_pf_taker")
    faucet(taker_addr, amount=1_000_000)

    # Custom denom X for have side; want in udys for taker solvency
    coin_x = register_name(dysond, maker_name, maker_addr, "1000udys")
    params = dysond("query", "nameservice", "params")
    fee_per_unit = float(params["params"]["mint_fee_per_coin"])
    units = 200
    required_fee = int(units * fee_per_unit)
    assert (
        dysond(
            "tx",
            "nameservice",
            "mint-coins",
            "--amount",
            f"{units}{coin_x}",
            "--mint-fee",
            f"{required_fee}udys",
            "--from",
            maker_name,
        ).get("code", 1)
        == 0
    )

    # Offer: have 8X, want 4udys → unit_have=2X, unit_want=1udys (GCD=4)
    have = f"8{coin_x}"
    want = "4udys"
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
    assert tx.get("code", 1) == 0
    offer_id = int(
        [
            a
            for e in tx.get("events", [])
            if e.get("type") == "dysonprotocol.whaleswap.v1.EventOfferCreated"
            for a in e["attributes"]
            if a.get("key") == "offer_id"
        ][0]["value"]
    )

    # Taker takes exactly 2 units → pays 2udys, receives 4X; offer remains open with 4X/2udys
    take = dysond(
        "tx",
        "whaleswap",
        "take-offer",
        "--trades",
        f"offer_id={offer_id},take_units=2",
        "--from",
        taker_name,
    )
    assert (
        take.get("code", 1) == 0
    ), f"partial take failed: {json.dumps(take, indent=2)}"
    q = dysond("query", "whaleswap", "offer", str(offer_id))
    offer = q.get("offer", {})
    assert offer.get("status") == "open", f"offer not open: {json.dumps(q, indent=2)}"
    assert (
        offer.get("remaining_units") == "2"
    ), f"remaining_units != 2: {json.dumps(q, indent=2)}"
    assert offer.get("remaining_have", {}).get("denom") == coin_x
    assert int(offer.get("remaining_have", {}).get("amount", "0")) == 4
    assert offer.get("remaining_want", {}).get("denom") == "udys"
    assert int(offer.get("remaining_want", {}).get("amount", "0")) == 2
    bals = dysond("query", "bank", "balances", taker_addr)
    got = {b.get("denom"): int(b.get("amount")) for b in bals.get("balances", [])}
    assert (
        got.get(coin_x, 0) >= 4
    ), f"taker did not receive 4X: {json.dumps(bals, indent=2)}"


def test_take_units_overflow_fails(chainnet, generate_account, faucet, register_name):
    dysond = chainnet[0]
    [maker_name, maker_addr] = generate_account("ob_over_maker")
    faucet(maker_addr, amount=2_000_000)
    [taker_name, taker_addr] = generate_account("ob_over_taker")
    faucet(taker_addr, amount=1_000_000)

    coin_x = register_name(dysond, maker_name, maker_addr, "1000udys")
    params = dysond("query", "nameservice", "params")
    fee_per_unit = float(params["params"]["mint_fee_per_coin"])
    units = 200
    required_fee = int(units * fee_per_unit)
    assert (
        dysond(
            "tx",
            "nameservice",
            "mint-coins",
            "--amount",
            f"{units}{coin_x}",
            "--mint-fee",
            f"{required_fee}udys",
            "--from",
            maker_name,
        ).get("code", 1)
        == 0
    )
    tx = dysond(
        "tx",
        "whaleswap",
        "make-offer",
        "--have",
        f"4{coin_x}",
        "--want",
        "2udys",
        "--from",
        maker_name,
    )
    assert tx.get("code", 1) == 0
    offer_id = int(
        [
            a
            for e in tx.get("events", [])
            if e.get("type") == "dysonprotocol.whaleswap.v1.EventOfferCreated"
            for a in e["attributes"]
            if a.get("key") == "offer_id"
        ][0]["value"]
    )
    take = dysond(
        "tx",
        "whaleswap",
        "take-offer",
        "--trades",
        f"offer_id={offer_id},take_units=3",
        "--from",
        taker_name,
    )
    assert (
        take.get("code", 0) != 0
    ), f"overflowed take_units should fail: {json.dumps(take, indent=2)}"


def test_same_denom_netting_batch(chainnet, generate_account, faucet, register_name):
    dysond = chainnet[0]
    [m1_name, m1_addr] = generate_account("ob_net_m1")
    [m2_name, m2_addr] = generate_account("ob_net_m2")
    [taker_name, taker_addr] = generate_account("ob_net_t")
    faucet(m1_addr, amount=2_000_000)
    faucet(m2_addr, amount=2_000_000)
    faucet(taker_addr, amount=1_000_000)

    # Important: each maker must possess the denom they offer on the HAVE side
    # m1 will offer coin_b, so coin_b must be owned/minted by m1
    # m2 will offer coin_a, so coin_a must be owned/minted by m2
    coin_b = register_name(dysond, m1_name, m1_addr, "1000udys")
    coin_a = register_name(dysond, m2_name, m2_addr, "1000udys")
    params = dysond("query", "nameservice", "params")
    fee_per_unit = float(params["params"]["mint_fee_per_coin"])
    units = 200
    required_fee = int(units * fee_per_unit)
    assert (
        dysond(
            "tx",
            "nameservice",
            "mint-coins",
            "--amount",
            f"{units}{coin_b}",
            "--mint-fee",
            f"{required_fee}udys",
            "--from",
            m1_name,
        ).get("code", 1)
        == 0
    )
    assert (
        dysond(
            "tx",
            "nameservice",
            "mint-coins",
            "--amount",
            f"{units}{coin_a}",
            "--mint-fee",
            f"{required_fee}udys",
            "--from",
            m2_name,
        ).get("code", 1)
        == 0
    )

    tx1 = dysond(
        "tx",
        "whaleswap",
        "make-offer",
        "--have",
        f"2{coin_b}",
        "--want",
        f"1{coin_a}",
        "--from",
        m1_name,
    )
    tx2 = dysond(
        "tx",
        "whaleswap",
        "make-offer",
        "--have",
        f"1{coin_a}",
        "--want",
        f"1{coin_b}",
        "--from",
        m2_name,
    )
    assert tx1.get("code", 1) == 0 and tx2.get("code", 1) == 0
    get_id = lambda tx: int(
        [
            a
            for e in tx.get("events", [])
            if e.get("type") == "dysonprotocol.whaleswap.v1.EventOfferCreated"
            for a in e["attributes"]
            if a.get("key") == "offer_id"
        ][0]["value"]
    )
    o1, o2 = get_id(tx1), get_id(tx2)

    take = dysond(
        "tx",
        "whaleswap",
        "take-offer",
        "--trades",
        f"offer_id={o1}",
        "--trades",
        f"offer_id={o2}",
        "--from",
        taker_name,
    )
    assert (
        take.get("code", 1) == 0
    ), f"netting batch failed: {json.dumps(take, indent=2)}"
    bals = dysond("query", "bank", "balances", taker_addr)
    got = {b.get("denom"): int(b.get("amount")) for b in bals.get("balances", [])}
    assert (
        got.get(coin_a, 0) == 0
    ), f"taker A should net to 0: {json.dumps(bals, indent=2)}"
    assert (
        got.get(coin_b, 0) == 1
    ), f"taker B should net to +1: {json.dumps(bals, indent=2)}"


def test_taker_deficit_funded_by_liquid(
    chainnet, generate_account, faucet, register_name
):
    dysond = chainnet[0]
    [taker_name, taker_addr] = generate_account("ob_liq_t")
    faucet(taker_addr, amount=2_000_000)
    [maker_name, maker_addr] = generate_account("ob_liq_m")
    faucet(maker_addr, amount=2_000_000)

    # Taker owns coin_p; mint 2 to taker and convert all to liquid → module holds solid backing
    coin_p = register_name(dysond, taker_name, taker_addr, "1000udys")
    params = dysond("query", "nameservice", "params")
    fee_per_unit = float(params["params"]["mint_fee_per_coin"])
    units = 2
    required_fee = 1  # ceil(2 * fee_per_unit) → at least 1 when fee_per_unit > 0
    assert (
        dysond(
            "tx",
            "nameservice",
            "mint-coins",
            "--amount",
            f"{units}{coin_p}",
            "--mint-fee",
            f"{required_fee}udys",
            "--from",
            taker_name,
        ).get("code", 1)
        == 0
    )
    res = dysond(
        "tx",
        "whaleswap",
        "convert-to-liquid",
        "--denom",
        coin_p,
        "--amount",
        "2",
        "--from",
        taker_name,
    )
    assert (
        res.get("code", 1) == 0
    ), f"convert-to-liquid failed: {json.dumps(res, indent=2)}"
    ldenom = f"whaleswap.dys/coins/{coin_p}"

    # Maker wants 2 coin_p, offers udys; taker has 0 base coin_p but holds 2 L(coin_p)
    tx = dysond(
        "tx",
        "whaleswap",
        "make-offer",
        "--have",
        "100udys",
        "--want",
        f"2{coin_p}",
        "--from",
        maker_name,
    )
    assert tx.get("code", 1) == 0
    offer_id = int(
        [
            a
            for e in tx.get("events", [])
            if e.get("type") == "dysonprotocol.whaleswap.v1.EventOfferCreated"
            for a in e["attributes"]
            if a.get("key") == "offer_id"
        ][0]["value"]
    )
    take = dysond(
        "tx",
        "whaleswap",
        "take-offer",
        "--trades",
        f"offer_id={offer_id}",
        "--from",
        taker_name,
    )
    assert (
        take.get("code", 1) == 0
    ), f"take with liquid funding failed: {json.dumps(take, indent=2)}"
    tbals = dysond("query", "bank", "balances", taker_addr)
    tgot = {b.get("denom"): int(b.get("amount")) for b in tbals.get("balances", [])}
    assert (
        tgot.get(ldenom, 0) == 0
    ), f"taker liquid should be burned: {json.dumps(tbals, indent=2)}"
    mbals = dysond("query", "bank", "balances", maker_addr)
    mgot = {b.get("denom"): int(b.get("amount")) for b in mbals.get("balances", [])}
    assert (
        mgot.get(coin_p, 0) >= 2
    ), f"maker did not receive coin_p: {json.dumps(mbals, indent=2)}"


def test_cancel_normal_refunds_escrow(
    chainnet, generate_account, faucet, register_name
):
    dysond = chainnet[0]
    [maker_name, maker_addr] = generate_account("ob_cancel_m")
    faucet(maker_addr, amount=2_000_000)

    coin_x = register_name(dysond, maker_name, maker_addr, "1000udys")
    params = dysond("query", "nameservice", "params")
    fee_per_unit = float(params["params"]["mint_fee_per_coin"])
    units = 200
    required_fee = int(units * fee_per_unit)
    assert (
        dysond(
            "tx",
            "nameservice",
            "mint-coins",
            "--amount",
            f"{units}{coin_x}",
            "--mint-fee",
            f"{required_fee}udys",
            "--from",
            maker_name,
        ).get("code", 1)
        == 0
    )

    # Record starting balance of coin_x
    start = {
        b.get("denom"): int(b.get("amount"))
        for b in dysond("query", "bank", "balances", maker_addr).get("balances", [])
    }.get(coin_x, 0)
    offer_have = 50
    tx = dysond(
        "tx",
        "whaleswap",
        "make-offer",
        "--have",
        f"{offer_have}{coin_x}",
        "--want",
        "25udys",
        "--from",
        maker_name,
    )
    assert tx.get("code", 1) == 0
    mid = {
        b.get("denom"): int(b.get("amount"))
        for b in dysond("query", "bank", "balances", maker_addr).get("balances", [])
    }.get(coin_x, 0)
    assert mid == start - offer_have, f"escrow not deducted: start={start}, mid={mid}"
    offer_id = int(
        [
            a
            for e in tx.get("events", [])
            if e.get("type") == "dysonprotocol.whaleswap.v1.EventOfferCreated"
            for a in e["attributes"]
            if a.get("key") == "offer_id"
        ][0]["value"]
    )
    cancel = dysond(
        "tx",
        "whaleswap",
        "cancel-offer",
        "--offer-id",
        str(offer_id),
        "--from",
        maker_name,
    )
    assert cancel.get("code", 1) == 0, f"cancel failed: {json.dumps(cancel, indent=2)}"
    end = {
        b.get("denom"): int(b.get("amount"))
        for b in dysond("query", "bank", "balances", maker_addr).get("balances", [])
    }.get(coin_x, 0)
    assert end == start, f"escrow not refunded: start={start}, end={end}"


def test_duplicate_offer_id_batch_fails(
    chainnet, generate_account, faucet, register_name
):
    dysond = chainnet[0]
    [maker_name, maker_addr] = generate_account("ob_dup_m")
    faucet(maker_addr, amount=2_000_000)
    [taker_name, taker_addr] = generate_account("ob_dup_t")
    faucet(taker_addr, amount=1_000_000)

    coin_x = register_name(dysond, maker_name, maker_addr, "1000udys")
    params = dysond("query", "nameservice", "params")
    fee_per_unit = float(params["params"]["mint_fee_per_coin"])
    units = 200
    required_fee = int(units * fee_per_unit)
    assert (
        dysond(
            "tx",
            "nameservice",
            "mint-coins",
            "--amount",
            f"{units}{coin_x}",
            "--mint-fee",
            f"{required_fee}udys",
            "--from",
            maker_name,
        ).get("code", 1)
        == 0
    )
    tx = dysond(
        "tx",
        "whaleswap",
        "make-offer",
        "--have",
        f"10{coin_x}",
        "--want",
        "5udys",
        "--from",
        maker_name,
    )
    assert tx.get("code", 1) == 0
    offer_id = int(
        [
            a
            for e in tx.get("events", [])
            if e.get("type") == "dysonprotocol.whaleswap.v1.EventOfferCreated"
            for a in e["attributes"]
            if a.get("key") == "offer_id"
        ][0]["value"]
    )
    take = dysond(
        "tx",
        "whaleswap",
        "take-offer",
        "--trades",
        f"offer_id={offer_id}",
        "--trades",
        f"offer_id={offer_id}",
        "--from",
        taker_name,
    )
    assert (
        take.get("code", 0) != 0
    ), f"duplicate offer_id should fail: {json.dumps(take, indent=2)}"


def test_take_nonexistent_offer_fails(chainnet, generate_account, faucet):
    dysond = chainnet[0]
    [taker_name, taker_addr] = generate_account("ob_noexist_t")
    faucet(taker_addr, amount=1_000_000)
    # Pick a high offer id that won't exist in a fresh chain
    bogus_id = 9999999
    res = dysond(
        "tx",
        "whaleswap",
        "take-offer",
        "--trades",
        f"offer_id={bogus_id}",
        "--from",
        taker_name,
    )
    assert (
        res.get("code", 0) != 0
    ), f"taking nonexistent offer should fail: {json.dumps(res, indent=2)}"
