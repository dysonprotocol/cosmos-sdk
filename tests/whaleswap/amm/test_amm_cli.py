import json


def test_create_pool_v2_success(chainnet, generate_account, faucet, register_name):
    dysond = chainnet[0]
    [creator_name, creator_addr] = generate_account("amm_creator")
    faucet(creator_addr, amount=2_000_000)

    # Mint a second denom via nameservice to have two valid reserves
    name = register_name(dysond, creator_name, creator_addr, "1000udys")
    params = dysond("query", "nameservice", "params")
    fee_per_unit = float(params["params"]["mint_fee_per_coin"])  # e.g., 0.01
    units = 1000
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
        creator_name,
    )
    assert mint.get("code", 1) == 0, f"mint-coins failed: {json.dumps(mint, indent=2)}"

    # Create a simple v2 pool (no band)
    tx = dysond(
        "tx",
        "whaleswap",
        "create-pool",
        "--coins",
        "1000udys",
        "--coins",
        f"500{name}",
        "--from",
        creator_name,
    )
    assert tx.get("code", 1) == 0, f"create-pool failed: {json.dumps(tx, indent=2)}"

    # Extract pool_id from events
    pool_events = [
        e
        for e in tx.get("events", [])
        if e.get("type") == "dysonprotocol.whaleswap.v1.EventPoolCreated"
    ]
    assert pool_events, f"EventPoolCreated not found in tx events: {tx}"
    attrs = pool_events[0].get("attributes", [])
    pool_id_attr = [a for a in attrs if a.get("key") == "pool_id"]
    assert pool_id_attr, f"pool_id attribute missing in EventPoolCreated: {pool_events}"
    pool_id_raw = pool_id_attr[0].get("value")
    pool_id = int(str(pool_id_raw).strip('"'))

    # Query pool and validate basics
    q = dysond("query", "whaleswap", "pool", str(pool_id))
    pool = q.get("pool")
    assert pool, f"pool not found: {q}"
    # canonical order: denom_a < denom_b
    assert (
        pool["coin_a"]["denom"] < pool["coin_b"]["denom"]
    ), f"denom order not canonical: {pool}"
    # shares denom shape
    assert pool["shares_denom"].startswith(
        "whaleswap.dys/pools/"
    ), f"invalid shares denom: {pool['shares_denom']}"


def test_pool_swap_v2_single_pool(chainnet, generate_account, faucet, register_name):
    dysond = chainnet[0]
    [creator_name, creator_addr] = generate_account("amm_creator")
    faucet(creator_addr, amount=2_000_000)

    # Create second denom under nameservice and mint supply
    name = register_name(dysond, creator_name, creator_addr, "1000udys")
    params = dysond("query", "nameservice", "params")
    fee_per_unit = float(params["params"]["mint_fee_per_coin"])  # e.g., 0.01
    units = 1000
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
        creator_name,
    )
    assert mint.get("code", 1) == 0, f"mint-coins failed: {json.dumps(mint, indent=2)}"

    # Pool: 1000udys, 500{name}
    tx = dysond(
        "tx",
        "whaleswap",
        "create-pool",
        "--coins",
        "1000udys",
        "--coins",
        f"500{name}",
        "--from",
        creator_name,
    )
    assert tx.get("code", 1) == 0, f"create-pool failed: {json.dumps(tx, indent=2)}"
    evs = [
        e
        for e in tx.get("events", [])
        if e.get("type") == "dysonprotocol.whaleswap.v1.EventPoolCreated"
    ]
    assert evs, f"EventPoolCreated not found: {tx}"
    attrs = evs[0].get("attributes", [])
    pid_attr = [a for a in attrs if a.get("key") == "pool_id"]
    pool_id = int(str(pid_attr[0].get("value")).strip('"'))

    # Trader account and funds
    [trader_name, trader_addr] = generate_account("amm_trader")
    faucet(trader_addr, amount=1_000_000)

    # Execute swap: input 100udys, expect out denom = other side and amount > 0
    swap = dysond(
        "tx",
        "whaleswap",
        "swap",
        "--pool-id",
        str(pool_id),
        "--input",
        "100udys",
        "--minimum-out-amount",
        "1",
        "--out-denom",
        name,
        "--from",
        trader_name,
    )
    assert swap.get("code", 1) == 0, f"swap failed: {json.dumps(swap, indent=2)}"

    # Query pool to assert reserves moved and num_trades incremented
    after = dysond("query", "whaleswap", "pool", str(pool_id))["pool"]
    assert int(after["num_trades"]) >= 1, f"num_trades not incremented: {after}"
    # price remains positive and denoms preserved
    r1 = (
        int(after["coin_a"]["amount"])
        if after["coin_a"]["denom"] == "udys"
        else int(after["coin_b"]["amount"])
    )
    r2 = (
        int(after["coin_b"]["amount"])
        if after["coin_b"]["denom"] == name
        else int(after["coin_a"]["amount"])
    )
    assert (
        r1 > 0 and r2 > 0
    ), f"reserves not positive after swap: {json.dumps(after, indent=2)}"


def test_create_pool_v3_with_band_success(
    chainnet, generate_account, faucet, register_name
):
    dysond = chainnet[0]
    [creator_name, creator_addr] = generate_account("amm_creator")
    faucet(creator_addr, amount=2_000_000)

    # second denom
    name = register_name(dysond, creator_name, creator_addr, "1000udys")

    # mint supply of the second denom
    params = dysond("query", "nameservice", "params")
    fee_per_unit = float(params["params"]["mint_fee_per_coin"])  # e.g., 0.01
    units = 1000
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
        creator_name,
    )
    assert mint.get("code", 1) == 0, f"mint-coins failed: {json.dumps(mint, indent=2)}"

    # Band: min 2udys:1name (ratio 0.5), max 1udys:3name (ratio 3)
    tx = dysond(
        "tx",
        "whaleswap",
        "create-pool",
        "--coins",
        "1000udys",
        "--coins",
        f"500{name}",
        "--min-price",
        "2udys",
        "--min-price",
        f"1{name}",
        "--max-price",
        "1udys",
        "--max-price",
        f"3{name}",
        "--from",
        creator_name,
    )
    assert tx.get("code", 1) == 0, f"create-pool v3 failed: {json.dumps(tx, indent=2)}"


def test_create_pool_reject_zero_width_band(
    chainnet, generate_account, faucet, register_name
):
    dysond = chainnet[0]
    [creator_name, creator_addr] = generate_account("amm_creator")
    faucet(creator_addr, amount=2_000_000)

    name = register_name(dysond, creator_name, creator_addr, "1000udys")

    # mint supply of the second denom
    params = dysond("query", "nameservice", "params")
    fee_per_unit = float(params["params"]["mint_fee_per_coin"])  # e.g., 0.01
    units = 1000
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
        creator_name,
    )
    assert mint.get("code", 1) == 0, f"mint-coins failed: {json.dumps(mint, indent=2)}"

    # Equal min and max should fail
    tx = dysond(
        "tx",
        "whaleswap",
        "create-pool",
        "--coins",
        "1000udys",
        "--coins",
        f"500{name}",
        "--min-price",
        "1udys",
        "--min-price",
        f"2{name}",
        "--max-price",
        "1udys",
        "--max-price",
        f"2{name}",
        "--from",
        creator_name,
    )
    assert (
        tx.get("code", 0) != 0
    ), f"expected failure for zero-width band, got: {json.dumps(tx, indent=2)}"
