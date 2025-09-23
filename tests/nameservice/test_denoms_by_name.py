import math
import pytest


def _mint(dysond_bin, owner_name, denom, amount="1"):
    resp = dysond_bin(
        "tx",
        "nameservice",
        "mint-coins",
        "--amount",
        f"{amount}{denom}",
        "--mint-fee",
        f"{math.ceil(int(amount) * 0.01)}udys",
        "--from",
        owner_name,
    )
    assert resp.get("code", 1) == 0, resp.get("raw_log", "")
    return resp


def _burn(dysond_bin, owner_name, denom, amount="1"):
    resp = dysond_bin(
        "tx",
        "nameservice",
        "burn-coins",
        "--amount",
        f"{amount}{denom}",
        "--from",
        owner_name,
    )
    assert resp.get("code", 1) == 0, resp.get("raw_log", "")
    return resp


def _query_denoms_all(dysond_bin, name):
    out = dysond_bin("query", "nameservice", "denoms-by-name", "--name", name)
    return {d.get("denom") for d in out.get("denoms", [])}


def _query_denoms_prefix(dysond_bin, name, subprefix):
    out = dysond_bin(
        "query",
        "nameservice",
        "denoms-by-name",
        "--name",
        name,
        "--subdenom-prefix",
        subprefix,
    )
    return {d.get("denom") for d in out.get("denoms", [])}


def test_denoms_by_name_basic_and_prefix(
    chainnet, generate_account, faucet, register_name
):
    dysond_bin = chainnet[0]

    [owner_name, owner_addr] = generate_account("owner", faucet_amount=10000000)

    root = register_name(dysond_bin, owner_name, owner_addr)

    denoms = [
        f"{root}",
        f"{root}/a",
        f"{root}/foo/bar1",
        f"{root}/foo/bar2",
        f"{root}/foo/bar/baz",
        f"{root}/123123123123",
    ]

    for d in denoms:
        _mint(dysond_bin, owner_name, d, amount="1")

    # No prefix -> all
    got = _query_denoms_all(dysond_bin, root)
    assert set(denoms).issubset(got), got

    # Prefix "/foo" -> only under foo
    got_prefix = _query_denoms_prefix(dysond_bin, root, "/foo")
    expect_prefix = {f"{root}/foo/bar1", f"{root}/foo/bar2", f"{root}/foo/bar/baz"}
    assert expect_prefix.issubset(got_prefix), got_prefix


def test_denoms_removed_when_last_supply_burned(
    chainnet, generate_account, faucet, register_name
):
    dysond_bin = chainnet[0]

    [owner_name, owner_addr] = generate_account("owner")
    faucet(owner_addr, denom="udys", amount="10000000")

    root = register_name(dysond_bin, owner_name, owner_addr)
    doomed = f"{root}/123123123123"

    _mint(dysond_bin, owner_name, doomed, amount="7")
    assert doomed in _query_denoms_all(dysond_bin, root)

    _burn(dysond_bin, owner_name, doomed, amount="7")

    # After supply reaches zero, denom should be removed from reverse index
    got = _query_denoms_all(dysond_bin, root)
    assert doomed not in got, got


def test_root_denom_removed_when_last_supply_burned(
    chainnet, generate_account, faucet, register_name
):
    dysond_bin = chainnet[0]

    [owner_name, owner_addr] = generate_account("owner")
    faucet(owner_addr, denom="udys", amount="10000000")

    root = register_name(dysond_bin, owner_name, owner_addr)

    # Mint the root denom itself (no subpath)
    _mint(dysond_bin, owner_name, root, amount="7")
    assert root in _query_denoms_all(dysond_bin, root)

    # Burn entire supply of the root denom
    _burn(dysond_bin, owner_name, root, amount="7")

    # After supply reaches zero, root denom should be removed from reverse index
    got = _query_denoms_all(dysond_bin, root)
    assert root not in got, got
