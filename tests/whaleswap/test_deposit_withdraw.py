import json
import tempfile
import base64
from decimal import Decimal, ROUND_CEILING


def _ceil_dec(x: Decimal) -> Decimal:
    return x.to_integral_value(rounding=ROUND_CEILING)


def _build_attached_msg_send(from_addr: str, to_addr: str, coins) -> str:
    return json.dumps(
        {
            "@type": "/cosmos.bank.v1beta1.MsgSend",
            "from_address": from_addr,
            "to_address": to_addr,
            "amount": coins,
        }
    )


def test_deposit_and_withdraw_udys(chainnet, generate_account, faucet, register_name):
    dysond = chainnet[0]

    # Accounts
    [alice_name, alice_addr] = generate_account("alice")
    faucet(alice_addr, denom="udys", amount="1000000")

    # Register a dedicated root name and bake it into whaleswap code
    root = register_name(dysond, alice_name, alice_addr)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as tf:
        code_path = tf.name
        src = dysond("query", "script", "script-info", "--address", alice_addr)
        # Load on-disk whaleswap script and replace DYS_NAME
        with open("whaleswap/orderbook.py", "r") as fh:
            code = fh.read()
        code = code.replace('DYS_NAME = "whaleswap.dys"', f'DYS_NAME = "{root}"')
        tf.write(code)
        tf.flush()

    # Update script with customized DYS_NAME
    up = dysond(
        "tx",
        "script",
        "update",
        "--code-path",
        code_path,
        "--from",
        alice_name,
        "--gas",
        "auto",
    )
    assert up.get("code", 1) == 0, f"update failed: {up}"

    # Query nameservice mint fee
    params = dysond("query", "nameservice", "params")
    fee_per = Decimal(params["params"]["mint_fee_per_coin"])  # e.g. 0.01

    # Prepare deposit of 100 udys → liquid denom root/coins/base64url(udys)
    deposit_amount = Decimal(100)
    required_fee = _ceil_dec(deposit_amount * fee_per)
    total_udys = deposit_amount + required_fee

    attached = _build_attached_msg_send(
        alice_addr,
        alice_addr,
        [{"denom": "udys", "amount": str(total_udys)}],
    )

    # Execute deposit(denom, amount)
    dep = dysond(
        "tx",
        "script",
        "exec",
        "--script-address",
        alice_addr,
        "--function-name",
        "convert_to_liquid",
        "--args",
        json.dumps(["udys", str(deposit_amount)]),
        "--from",
        alice_name,
        "--attached-message",
        attached,
        "--gas",
        "auto",
    )
    assert dep.get("code", 1) == 0, f"deposit failed: {dep}"

    # Extract result liquid denom from event
    events = {e.get("type"): e for e in dep.get("events", [])}
    assert "dysonprotocol.script.v1.EventExecScript" in events, f"no exec event: {dep}"
    attrs = {
        a.get("key"): a.get("value")
        for a in events["dysonprotocol.script.v1.EventExecScript"].get("attributes", [])
    }
    resp = json.loads(attrs["response"])
    parsed = json.loads(resp.get("result", "{}"))
    liquid = parsed.get("result", {}).get("liquid_denom")
    # Compute expected liquid denom dynamically: {root}/coins/{base64url_no_pad(denom)}
    enc = base64.urlsafe_b64encode(b"udys").decode("ascii").rstrip("=")
    expected = f"{root}/coins/{enc}"
    assert (
        isinstance(liquid, str) and liquid == expected
    ), f"unexpected liquid: {liquid}, expected: {expected}"

    # Withdraw the same amount
    w = dysond(
        "tx",
        "script",
        "exec",
        "--script-address",
        alice_addr,
        "--function-name",
        "convert_to_solid",
        "--args",
        json.dumps([liquid, str(deposit_amount)]),
        "--from",
        alice_name,
        "--gas",
        "auto",
    )
    assert w.get("code", 1) == 0, f"withdraw failed: {w}"
