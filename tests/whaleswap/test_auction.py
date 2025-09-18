import json
import tempfile
from decimal import Decimal, ROUND_CEILING


def _build_attached_msg_send(from_addr: str, to_addr: str, coins) -> str:
    return json.dumps(
        {
            "@type": "/cosmos.bank.v1beta1.MsgSend",
            "from_address": from_addr,
            "to_address": to_addr,
            "amount": coins,
        }
    )


def _parse_exec_result(tx_result: dict) -> dict:
    events = {e.get("type"): e for e in tx_result.get("events", [])}
    assert (
        "dysonprotocol.script.v1.EventExecScript" in events
    ), f"No EventExecScript found. Full: {json.dumps(tx_result, indent=2)}"
    attrs = {
        a.get("key"): a.get("value")
        for a in events["dysonprotocol.script.v1.EventExecScript"].get("attributes", [])
    }
    assert (
        "response" in attrs
    ), f"No response attr. Full: {json.dumps(tx_result, indent=2)}"
    response_json = attrs["response"]
    response_data = json.loads(response_json)
    parsed = json.loads(response_data.get("result", "{}"))
    return parsed.get("result", {})


def test_open_and_redeem_auction_udys(
    chainnet, generate_account, faucet, register_name
):
    dysond = chainnet[0]

    # Accounts
    [alice_name, alice_addr] = generate_account("alice")
    faucet(alice_addr, denom="udys", amount="10000000")

    # Register a dedicated root name and bake it into the auction code
    root = register_name(dysond, alice_name, alice_addr)

    # Upload whaleswap/auction.py with DYS_NAME replaced
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as tf:
        code_path = tf.name
        with open("whaleswap/auction.py", "r") as fh:
            code = fh.read()
        code = code.replace('DYS_NAME = "whaleswap.dys"', f'DYS_NAME = "{root}"')
        tf.write(code)
        tf.flush()

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
    assert up.get("code", 1) == 0, f"script update failed: {json.dumps(up, indent=2)}"

    # Pre-balance for sanity
    bal_before = dysond("query", "bank", "balances", alice_addr)
    bal_map_before = {
        c["denom"]: int(c["amount"]) for c in bal_before.get("balances", [])
    }

    # Compute required mint fee per-coin (ceil(units * fee_per_coin))
    params = dysond("query", "nameservice", "params")
    fee_per = Decimal(params["params"]["mint_fee_per_coin"])  # e.g., 0.01

    def _ceil_dec(x: Decimal) -> Decimal:
        return x.to_integral_value(rounding=ROUND_CEILING)

    # Mint two bid denoms under the auction root so they have non-zero supply
    bid_a = f"{root}/a"
    bid_b = f"{root}/b"
    req_fee = _ceil_dec(Decimal(1) * fee_per)
    m1 = dysond(
        "tx",
        "nameservice",
        "mint-coins",
        "--amount",
        f"1{bid_a}",
        "--mint-fee",
        f"{req_fee}udys",
        "--from",
        alice_name,
    )
    assert m1.get("code", 1) == 0, f"mint bid_a failed: {json.dumps(m1, indent=2)}"
    m2 = dysond(
        "tx",
        "nameservice",
        "mint-coins",
        "--amount",
        f"1{bid_b}",
        "--mint-fee",
        f"{req_fee}udys",
        "--from",
        alice_name,
    )
    assert m2.get("code", 1) == 0, f"mint bid_b failed: {json.dumps(m2, indent=2)}"

    # Attach 100 udys to the script (script address == alice_addr)
    sell_amount = 100
    attached = _build_attached_msg_send(
        alice_addr, alice_addr, [{"denom": "udys", "amount": str(sell_amount)}]
    )

    # Open auction using bid denom with known non-zero supply
    bid_denom = bid_b
    tx = dysond(
        "tx",
        "script",
        "exec",
        "--script-address",
        alice_addr,
        "--function-name",
        "open_auction",
        "--args",
        json.dumps([bid_denom]),
        "--from",
        alice_name,
        "--attached-message",
        attached,
        "--gas",
        "auto",
    )
    assert tx.get("code", 1) == 0, f"open_auction failed: {json.dumps(tx, indent=2)}"

    result = _parse_exec_result(tx)
    auction_id = int(result.get("auction_id", -1))
    class_id = result.get("class_id")
    nft_id = result.get("nft_id")
    out_amount = str(result.get("amount"))

    assert auction_id >= 0, f"bad auction_id: {result}"
    assert (
        isinstance(class_id, str) and class_id == f"{root}/auction/udys/{bid_denom}"
    ), f"class_id mismatch: {class_id} vs expected {root}/auction/udys/{bid_denom}"
    assert nft_id and len(nft_id) > 0, f"missing nft_id: {result}"
    assert out_amount == str(
        sell_amount
    ), f"amount mismatch: {out_amount} vs {sell_amount}"

    # Owner of NFT should be alice
    q_owner = dysond("query", "nft", "owner", class_id, nft_id)
    assert q_owner.get("owner") == alice_addr, f"unexpected owner: {q_owner}"

    # Index exists
    idx_key = f"auction|id|{auction_id:010d}"
    storage_entry = dysond(
        "query",
        "storage",
        "get",
        alice_addr,
        "--index",
        idx_key,
    )
    assert "entry" in storage_entry, f"missing storage index: {storage_entry}"

    # Redeem should succeed (no bidder yet)
    tx2 = dysond(
        "tx",
        "script",
        "exec",
        "--script-address",
        alice_addr,
        "--function-name",
        "redeem_auction",
        "--args",
        json.dumps([auction_id]),
        "--from",
        alice_name,
        "--gas",
        "auto",
    )
    assert (
        tx2.get("code", 1) == 0
    ), f"redeem_auction failed: {json.dumps(tx2, indent=2)}"

    # Index removed
    storage_after = dysond(
        "query",
        "storage",
        "get",
        alice_addr,
        "--index",
        idx_key,
    )
    assert (
        isinstance(storage_after, str) and "doesn't exist" in storage_after
    ), f"expected not found after redeem, got: {storage_after}"

    # Class supply should be 0 after burn
    q_supply = dysond("query", "nft", "supply", class_id)
    supply_amt = int(q_supply.get("amount", "0"))
    assert supply_amt == 0, f"expected supply 0, got {q_supply}"
