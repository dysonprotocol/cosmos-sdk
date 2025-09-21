import json


def test_add_liquidity_v2(chainnet, generate_account, faucet, register_name):
    dysond = chainnet[0]
    [owner_name, owner_addr] = generate_account("amm_owner2")
    faucet(owner_addr, amount=2_000_000)
    name = register_name(dysond, owner_name, owner_addr, "1000udys")
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
        owner_name,
    )
    assert mint.get("code", 1) == 0, f"mint-coins failed: {json.dumps(mint, indent=2)}"

    tx = dysond(
        "tx",
        "whaleswap",
        "create-pool",
        "--coins",
        "1000udys",
        "--coins",
        f"500{name}",
        "--from",
        owner_name,
    )
    assert tx.get("code", 1) == 0, f"create-pool failed: {json.dumps(tx, indent=2)}"
    pid = int(
        str(
            [
                a
                for e in tx["events"]
                if e["type"] == "dysonprotocol.whaleswap.v1.EventPoolCreated"
                for a in e["attributes"]
                if a["key"] == "pool_id"
            ][0]["value"]
        ).strip('"')
    )

    # Ensure amounts align with pool's (coin_a, coin_b) order
    p_pre = dysond("query", "whaleswap", "pool", str(pid))["pool"]
    denom_a = p_pre["coin_a"]["denom"]
    denom_b = p_pre["coin_b"]["denom"]
    a1 = "300udys" if denom_a == "udys" else f"50{name}"
    a2 = "300udys" if denom_b == "udys" else f"50{name}"
    # First, intentionally misproportional amounts – expect failure (serves as guard)
    bad = dysond(
        "tx",
        "whaleswap",
        "add-liquidity",
        "--pool-id",
        str(pid),
        "--amount1",
        a1,
        "--amount2",
        a2,
        "--from",
        owner_name,
    )
    assert (
        bad.get("code", 0) != 0
    ), f"expected misproportional add-liquidity failure: {json.dumps(bad, indent=2)}"

    # Now add proportionally to current reserves (coin_a:coin_b = 1:2)
    prop_a = f"50{name}" if denom_a == name else "100udys"
    prop_b = f"50{name}" if denom_b == name else "100udys"
    add_ok = dysond(
        "tx",
        "whaleswap",
        "add-liquidity",
        "--pool-id",
        str(pid),
        "--amount1",
        prop_a,
        "--amount2",
        prop_b,
        "--from",
        owner_name,
    )
    assert (
        add_ok.get("code", 1) == 0
    ), f"add-liquidity proportional failed: {json.dumps(add_ok, indent=2)}"
    evs = [
        e
        for e in add_ok.get("events", [])
        if e.get("type") == "dysonprotocol.whaleswap.v1.EventPoolLiquidityAdded"
    ]
    assert evs, f"liquidity-added event missing: {json.dumps(add_ok, indent=2)}"
    shares_attr = [a for a in evs[0].get("attributes", []) if a.get("key") == "shares"]
    assert (
        shares_attr and int(str(shares_attr[0]["value"]).strip('"')) > 0
    ), f"no shares minted: {json.dumps(add_ok, indent=2)}"
