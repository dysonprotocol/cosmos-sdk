import json
import tempfile
from decimal import Decimal, ROUND_CEILING


def _ceil_dec(x: Decimal) -> Decimal:
    return x.to_integral_value(rounding=ROUND_CEILING)


def _build_msg_send(from_addr: str, to_addr: str, coins) -> str:
    return json.dumps(
        {
            "@type": "/cosmos.bank.v1beta1.MsgSend",
            "from_address": from_addr,
            "to_address": to_addr,
            "amount": coins,
        }
    )


def _update_whaleswap_for_root(dysond, script_owner_name, script_owner_addr, root_name):
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as tf:
        code_path = tf.name
        with open("whaleswap/script.py", "r") as fh:
            code = fh.read()
        code = code.replace('DYS_NAME = "whaleswap.dys"', f'DYS_NAME = "{root_name}"')
        tf.write(code)
        tf.flush()
    up = dysond(
        "tx",
        "script",
        "update",
        "--code-path",
        code_path,
        "--from",
        script_owner_name,
        "--yes",
        "--gas",
        "auto",
    )
    assert up.get("code", 1) == 0, f"update failed: {up}"


def test_make_take_normal(chainnet, generate_account, faucet, register_name):
    dysond = chainnet[0]
    [maker_name, maker_addr] = generate_account("maker")
    [taker_name, taker_addr] = generate_account("taker")
    faucet(maker_addr, denom="udys", amount="1000000")
    faucet(taker_addr, denom="udys", amount="1000000")

    root = register_name(dysond, maker_name, maker_addr)
    _update_whaleswap_for_root(dysond, maker_name, maker_addr, root)

    have = f"{root}/have"
    want = f"{root}/want"

    # Mint maker have and taker want
    dysond(
        "tx",
        "nameservice",
        "mint-coins",
        "--amount",
        f"100{have}",
        "--from",
        maker_name,
        "--mint-fee",
        "100000udys",
        "--gas",
        "auto",
    )
    dysond(
        "tx",
        "nameservice",
        "mint-coins",
        "--amount",
        f"100{want}",
        "--from",
        maker_name,
        "--mint-fee",
        "100000udys",
        "--gas",
        "auto",
    )
    # Send want to taker
    dysond("tx", "bank", "send", maker_name, taker_addr, f"100{want}", "--yes")

    # Maker creates normal offer have 30 have for 45 want; attach 30 have to script
    attached = _build_msg_send(
        maker_addr, maker_addr, [{"denom": have, "amount": "30"}]
    )
    make_args = json.dumps(
        [{"denom": have, "amount": "30"}, {"denom": want, "amount": "45"}]
    )
    mk = dysond(
        "tx",
        "script",
        "exec",
        "--script-address",
        maker_addr,
        "--function-name",
        "make",
        "--args",
        make_args,
        "--from",
        maker_name,
        "--attached-message",
        attached,
        "--gas",
        "auto",
    )
    assert mk.get("code", 1) == 0, f"make failed: {mk}"
    # Parse offer id
    events = {e.get("type"): e for e in mk.get("events", [])}
    attrs = {
        a.get("key"): a.get("value")
        for a in events["dysonprotocol.script.v1.EventExecScript"].get("attributes", [])
    }
    resp = json.loads(attrs["response"])
    offer_id = json.loads(resp.get("result", "{}")).get("result", {}).get("offer_id")
    assert offer_id is not None

    # Taker takes full offer, attaches 45 want
    take_args = json.dumps([[{"offer_id": offer_id, "take_units": None}]])
    attach_t = _build_msg_send(
        taker_addr, maker_addr, [{"denom": want, "amount": "45"}]
    )
    tk = dysond(
        "tx",
        "script",
        "exec",
        "--script-address",
        maker_addr,
        "--function-name",
        "take",
        "--args",
        take_args,
        "--from",
        taker_name,
        "--attached-message",
        attach_t,
        "--gas",
        "auto",
    )
    assert tk.get("code", 1) == 0, f"take failed: {tk}"


def test_make_take_liquid_and_pfand(chainnet, generate_account, faucet, register_name):
    dysond = chainnet[0]
    [owner_name, owner_addr] = generate_account("owner")
    [maker_name, maker_addr] = generate_account("maker")
    [taker_name, taker_addr] = generate_account("taker")
    faucet(owner_addr, denom="udys", amount="1000000")
    faucet(maker_addr, denom="udys", amount="1000000")
    faucet(taker_addr, denom="udys", amount="1000000")

    # Use owner as script owner
    root = register_name(dysond, owner_name, owner_addr)
    _update_whaleswap_for_root(dysond, owner_name, owner_addr, root)

    # Admin: set pfand to 1 and mint pfand to maker
    sp = dysond(
        "tx",
        "script",
        "exec",
        "--script-address",
        owner_addr,
        "--function-name",
        "set_pfand_per_offer",
        "--args",
        json.dumps(["1"]),
        "--from",
        owner_name,
        "--gas",
        "auto",
    )
    assert sp.get("code", 1) == 0, f"set pfand failed: {sp}"

    params = dysond("query", "nameservice", "params")
    fee_per = Decimal(params["params"]["mint_fee_per_coin"])  # e.g., 0.01
    pfand_amt = Decimal(10)
    required_udys = _ceil_dec(pfand_amt * fee_per)
    attached = _build_msg_send(
        owner_addr, owner_addr, [{"denom": "udys", "amount": str(required_udys)}]
    )
    mp = dysond(
        "tx",
        "script",
        "exec",
        "--script-address",
        owner_addr,
        "--function-name",
        "mint_pfand_to",
        "--args",
        json.dumps([maker_addr, str(pfand_amt)]),
        "--from",
        owner_name,
        "--attached-message",
        attached,
        "--gas",
        "auto",
    )
    assert mp.get("code", 1) == 0, f"mint_pfand_to failed: {mp}"

    # Maker deposits base have into liquid and obtains L(have)
    have = f"{root}/Lhave"
    dysond(
        "tx",
        "nameservice",
        "mint-coins",
        "--amount",
        f"100{have}",
        "--from",
        owner_name,
        "--mint-fee",
        "100000udys",
        "--gas",
        "auto",
    )
    dysond("tx", "bank", "send", owner_name, maker_addr, f"100{have}", "--yes")

    params = dysond("query", "nameservice", "params")
    fee_per2 = Decimal(params["params"]["mint_fee_per_coin"])  # 0.01
    dep_amt = Decimal(40)
    req_udys = _ceil_dec(dep_amt * fee_per2)
    attach_dep = _build_msg_send(
        maker_addr, owner_addr, [{"denom": have, "amount": str(dep_amt)}]
    )
    attach_fee = _build_msg_send(
        maker_addr, owner_addr, [{"denom": "udys", "amount": str(req_udys)}]
    )
    dep = dysond(
        "tx",
        "script",
        "exec",
        "--script-address",
        owner_addr,
        "--function-name",
        "deposit",
        "--args",
        json.dumps([have, str(dep_amt)]),
        "--from",
        maker_name,
        "--attached-message",
        attach_dep,
        "--attached-message",
        attach_fee,
        "--gas",
        "auto",
    )
    assert dep.get("code", 1) == 0, f"deposit failed: {dep}"
    events = {e.get("type"): e for e in dep.get("events", [])}
    attrs = {
        a.get("key"): a.get("value")
        for a in events["dysonprotocol.script.v1.EventExecScript"].get("attributes", [])
    }
    resp = json.loads(attrs["response"])
    result = json.loads(resp.get("result", "{}"))
    liquid_have = result.get("result", {}).get("liquid_denom")

    want = f"{root}/want2"
    dysond(
        "tx",
        "nameservice",
        "mint-coins",
        "--amount",
        f"100{want}",
        "--from",
        owner_name,
        "--mint-fee",
        "100000udys",
        "--gas",
        "auto",
    )
    dysond("tx", "bank", "send", owner_name, taker_addr, f"100{want}", "--yes")

    # Maker makes liquid offer: have L(have) 20 for want 30
    mk = dysond(
        "tx",
        "script",
        "exec",
        "--script-address",
        owner_addr,
        "--function-name",
        "make",
        "--args",
        json.dumps(
            [{"denom": liquid_have, "amount": "20"}, {"denom": want, "amount": "30"}]
        ),
        "--from",
        maker_name,
        "--gas",
        "auto",
    )
    assert mk.get("code", 1) == 0, f"make liquid failed: {mk}"
    events = {e.get("type"): e for e in mk.get("events", [])}
    attrs = {
        a.get("key"): a.get("value")
        for a in events["dysonprotocol.script.v1.EventExecScript"].get("attributes", [])
    }
    resp = json.loads(attrs["response"])
    offer_id = json.loads(resp.get("result", "{}")).get("result", {}).get("offer_id")
    assert offer_id is not None

    # Taker takes and attaches want
    attach_pay = _build_msg_send(
        taker_addr, owner_addr, [{"denom": want, "amount": "30"}]
    )
    tk = dysond(
        "tx",
        "script",
        "exec",
        "--script-address",
        owner_addr,
        "--function-name",
        "take",
        "--args",
        json.dumps([[{"offer_id": offer_id, "take_units": None}]]),
        "--from",
        taker_name,
        "--attached-message",
        attach_pay,
        "--gas",
        "auto",
    )
    assert tk.get("code", 1) == 0, f"take liquid failed: {tk}"


def test_cancel_liquid_third_party(chainnet, generate_account, faucet, register_name):
    dysond = chainnet[0]
    [owner_name, owner_addr] = generate_account("owner")
    [maker_name, maker_addr] = generate_account("maker")
    [third_name, third_addr] = generate_account("third")
    faucet(owner_addr, denom="udys", amount="1000000")
    faucet(maker_addr, denom="udys", amount="1000000")
    faucet(third_addr, denom="udys", amount="1000000")

    root = register_name(dysond, owner_name, owner_addr)
    _update_whaleswap_for_root(dysond, owner_name, owner_addr, root)

    # Set pfand 1 and mint pfand to maker
    dysond(
        "tx",
        "script",
        "exec",
        "--script-address",
        owner_addr,
        "--function-name",
        "set_pfand_per_offer",
        "--args",
        json.dumps(["1"]),
        "--from",
        owner_name,
        "--gas",
        "auto",
    )
    params = dysond("query", "nameservice", "params")
    fee_per = Decimal(params["params"]["mint_fee_per_coin"])  # e.g. 0.01
    required_udys = _ceil_dec(Decimal(1) * fee_per)
    attach = _build_msg_send(
        owner_addr, owner_addr, [{"denom": "udys", "amount": str(required_udys)}]
    )
    dysond(
        "tx",
        "script",
        "exec",
        "--script-address",
        owner_addr,
        "--function-name",
        "mint_pfand_to",
        "--args",
        json.dumps([maker_addr, "1"]),
        "--from",
        owner_name,
        "--attached-message",
        attach,
        "--gas",
        "auto",
    )

    # Maker: deposit base have to get liquid
    have = f"{root}/H"
    dysond(
        "tx", "nameservice", "mint-coins", "--amount", f"10{have}", "--from", owner_name
    )
    dysond(
        "tx",
        "nameservice",
        "mint-coins",
        "--amount",
        f"10{have}",
        "--from",
        owner_name,
        "--mint-fee",
        "100000udys",
        "--gas",
        "auto",
    )
    dysond("tx", "bank", "send", owner_name, maker_addr, f"10{have}", "--yes")
    dep_amt = Decimal(5)
    req = _ceil_dec(dep_amt * fee_per)
    attach_dep = _build_msg_send(
        maker_addr, owner_addr, [{"denom": have, "amount": str(dep_amt)}]
    )
    attach_fee = _build_msg_send(
        maker_addr, owner_addr, [{"denom": "udys", "amount": str(req)}]
    )
    dep = dysond(
        "tx",
        "script",
        "exec",
        "--script-address",
        owner_addr,
        "--function-name",
        "deposit",
        "--args",
        json.dumps([have, str(dep_amt)]),
        "--from",
        maker_name,
        "--attached-message",
        attach_dep,
        "--attached-message",
        attach_fee,
        "--gas",
        "auto",
    )
    assert dep.get("code", 1) == 0
    events = {e.get("type"): e for e in dep.get("events", [])}
    attrs = {
        a.get("key"): a.get("value")
        for a in events["dysonprotocol.script.v1.EventExecScript"].get("attributes", [])
    }
    resp = json.loads(attrs["response"])
    liquid_have = json.loads(resp.get("result", "{}"))["result"]["liquid_denom"]

    # Make liquid offer consuming 5 units; then drain maker's liquid below 1 unit
    mk = dysond(
        "tx",
        "script",
        "exec",
        "--script-address",
        owner_addr,
        "--function-name",
        "make",
        "--args",
        json.dumps(
            [{"denom": liquid_have, "amount": "5"}, {"denom": have, "amount": "5"}]
        ),
        "--from",
        maker_name,
        "--gas",
        "auto",
    )
    assert mk.get("code", 1) == 0
    # drain L(have)
    dysond("tx", "bank", "send", maker_name, third_addr, f"5{liquid_have}", "--yes")

    # Third party cancels and should receive pfand
    ca = dysond(
        "tx",
        "script",
        "exec",
        "--script-address",
        owner_addr,
        "--function-name",
        "cancel",
        "--args",
        json.dumps([1]),
        "--from",
        third_name,
        "--gas",
        "auto",
    )
    assert ca.get("code", 1) == 0, f"cancel failed: {ca}"
