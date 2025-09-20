raise RuntimeError("This file is not used anymore. Use the module instead.")

from typing import Any, Dict, List, Optional, TypedDict
import json
from decimal import Decimal, ROUND_CEILING
import base64

# Dyslang runtime: on-chain Python for Dyson Protocol
from dys import (
    _msg,  # type: ignore
    _query,  # type: ignore
    get_executor_address,  # type: ignore
    get_script_address,  # type: ignore
    get_block_info,  # type: ignore
    emit_event,  # type: ignore
    DysQueryException,  # type: ignore
    get_attached_messages,  # type: ignore
)


DYS_NAME = "whaleswap.dys"

# -----------------------------
# Denom & params constants
# -----------------------------
LIQUID_PREFIX = f"{DYS_NAME}/coins/"
PFAND_DENOM = f"{DYS_NAME}/pfand"
UDYS_DENOM = "udys"


# -----------------------------
# Base64url (no padding) helpers
# -----------------------------
def _b64url_encode_no_pad(value: str) -> str:
    raw = value.encode("utf-8")
    enc = base64.urlsafe_b64encode(raw).decode("ascii")
    return enc.rstrip("=")


def _b64url_decode_no_pad(value: str) -> str:
    # pad to multiple of 4
    pad = "=" * (-len(value) % 4)
    raw = base64.urlsafe_b64decode((value + pad).encode("ascii"))
    return raw.decode("utf-8")


def quote_liquid_denom(base_denom: str) -> str:
    """
    Return the liquid denom L(S) for solid denom S.

    Solid (S) refers to a normal on-ledger denom like `DYS_ROOT/foo`.
    Liquid (L) refers to `DYS_NAME/coins/<base64url(S)>`.
    """
    return LIQUID_PREFIX + _b64url_encode_no_pad(base_denom)


def _is_liquid_denom(denom: str) -> bool:
    return isinstance(denom, str) and denom.startswith(LIQUID_PREFIX)


def decode_liquid_denom(liquid_denom: str) -> str:
    """
    Return the solid denom S from a liquid denom L(S).
    """
    assert _is_liquid_denom(liquid_denom), f"invalid liquid denom: {liquid_denom}"
    tail = liquid_denom[len(LIQUID_PREFIX) :]
    return _b64url_decode_no_pad(tail)


# -----------------------------
# Params helpers (pfand, nameservice fee)
# -----------------------------
def _params_index(key: str) -> str:
    return f"params|{key}"


def _get_pfand_per_offer() -> Decimal:
    # Stored as plain string under a fixed key; default to 1
    entries = _storage_list(_params_index("pfand_per_offer"))
    if entries:
        return Decimal(entries[0]["data"])  # type: ignore[index]
    return Decimal(1)


def _set_pfand_per_offer(value: Decimal) -> Dict[str, Any]:
    return _storage_set(_params_index("pfand_per_offer"), str(value))


def _get_mint_fee_per_coin() -> Decimal:
    # Nameservice params query – returns {"params": {"mint_fee_per_coin": "0.01", ...}}
    res = _query({"@type": "/dysonprotocol.nameservice.v1.QueryParamsRequest"})
    fee_str = res["params"]["mint_fee_per_coin"]
    return Decimal(fee_str)


def _sum_attached_to_script_by_denom() -> Dict[str, Decimal]:
    totals: Dict[str, Decimal] = {}
    for c in _get_attached_coins_to_script() or []:
        d = c["denom"]
        a = Decimal(c["amount"])  # type: ignore[arg-type]
        totals[d] = totals.get(d, Decimal(0)) + a
    return totals


# -----------------------------
# Read-only helper APIs
# -----------------------------
def estimate_mint_fee(amount: int | Decimal | str) -> Decimal:
    """Return the required udys fee (integer string) for minting `amount` units.

    Computes ceil(amount * mint_fee_per_coin).
    """
    amt = Decimal(amount)
    if amt < 0:
        raise ValueError("amount must be >= 0")
    fee_per = _get_mint_fee_per_coin()
    required = (amt * fee_per).to_integral_value(rounding=ROUND_CEILING)
    return required


#############################
# Storage helpers (on-chain)
#############################


def _storage_get(index: str) -> Any:
    """Get value for index (JSON-decoded)."""
    try:
        res = _query(
            {
                "@type": "/dysonprotocol.storage.v1.QueryStorageGetRequest",
                "owner": get_script_address(),
                "index": index,
            }
        )
    except DysQueryException as e:
        if str(e).endswith("doesn\\'t exist')"):
            raise ValueError(f"NotFound: {index}")
        raise e
    return json.loads(res["entry"]["data"])


def _storage_set(index: str, data: Any) -> Dict[str, Any]:
    """Set data at index; always JSON-encoded with default=str."""
    payload = json.dumps(data, default=str)
    return _msg(
        {
            "@type": "/dysonprotocol.storage.v1.MsgStorageSet",
            "owner": get_script_address(),
            "index": index,
            "data": payload,
        }
    )


def _storage_delete(indexes: List[str]) -> Dict[str, Any]:
    """Delete data at index."""
    return _msg(
        {
            "@type": "/dysonprotocol.storage.v1.MsgStorageDelete",
            "owner": get_script_address(),
            "indexes": indexes,
        }
    )


def _storage_list(prefix: str) -> List[Dict[str, Any]]:
    """List storage entries for prefix; JSON-decode each entry's data."""
    res = _query(
        {
            "@type": "/dysonprotocol.storage.v1.QueryStorageListRequest",
            "owner": get_script_address(),
            "index_prefix": prefix,
        }
    )
    entries = res["entries"]
    del res
    for entry in entries:
        entry["data"] = json.loads(entry["data"])  # type: ignore[index]
    return entries


#############################
# Bank helpers
#############################


def _get_balance(address: str, denom: str) -> Decimal:
    res = _query(
        {
            "@type": "/cosmos.bank.v1beta1.QueryBalanceRequest",
            "address": address,
            "denom": denom,
        }
    )
    return Decimal(res["balance"]["amount"])


def _get_supply(denom: str) -> Decimal:
    res = _query(
        {
            "@type": "/cosmos.bank.v1beta1.QuerySupplyOfRequest",
            "denom": denom,
        }
    )
    return Decimal(res["amount"]["amount"])


#############################
# TypedDicts for complex types
#############################


class Coin(TypedDict):
    denom: str
    amount: Decimal


class PoolBalance(TypedDict):
    denom: str
    balance: Decimal
    lent: Decimal
    collateral: Decimal


class Pool(TypedDict):
    pool_id: int
    coin1: PoolBalance
    coin2: PoolBalance
    total_shares: Decimal
    shares_denom: str
    block_height: int
    created: str
    updated: Optional[str]
    num_trades: Optional[int]


class Input(TypedDict):
    address: str
    coins: List[Coin]


class Output(TypedDict):
    address: str
    coins: List[Coin]


#############################
# Msg helpers
#############################


def _move_coins(inputs: List[Input], outputs: List[Output]) -> Dict[str, Any]:
    """Move coins using nameservice MsgMoveCoins.

    Coerces all coin amounts to decimal strings as required by SDK.
    """

    return _msg(
        {
            "@type": "/dysonprotocol.nameservice.v1.MsgMoveCoins",
            "name_destination": get_script_address(),
            "inputs": inputs,
            "outputs": outputs,
        }
    )


def _mint_coins(coin: Coin, mint_fee: Any) -> Dict[str, Any]:
    """Mint a single coin amount to the script address.

    - Computes required fee = ceil(amount * mint_fee_per_coin)
    - Validates provided mint_fee >= required fee
    - Validates attached UDYS to script >= provided mint_fee
    - Sends MsgMintCoins with explicit mint_fee
    """
    amt = Decimal(coin["amount"])
    required = estimate_mint_fee(amt)
    provided = Decimal(mint_fee)
    if provided < required:
        raise ValueError(
            f"mint_fee provided {provided} < required {required} for amount {amt}"
        )
    attachments = _sum_attached_to_script_by_denom()
    attached_udys = attachments.get(UDYS_DENOM, Decimal(0))
    if attached_udys < provided:
        raise ValueError(
            f"insufficient attached udys for mint_fee: {attached_udys} < {provided}"
        )
    return _msg(
        {
            "@type": "/dysonprotocol.nameservice.v1.MsgMintCoins",
            "name_destination": get_script_address(),
            "amount": [coin],
            "mint_fee": {"denom": UDYS_DENOM, "amount": provided},
        }
    )


def _burn_coins(coin: Coin) -> Dict[str, Any]:
    """Burn a single coin amount from the script address."""
    return _msg(
        {
            "@type": "/dysonprotocol.nameservice.v1.MsgBurnCoins",
            "name_destination": get_script_address(),
            "amount": [coin],
        }
    )


def _send_coins(
    from_address: str, to_address: str, coins: List[Coin]
) -> Dict[str, Any]:
    """Send coins using bank MsgSend."""
    return _msg(
        {
            "@type": "/cosmos.bank.v1beta1.MsgSend",
            "from_address": from_address,
            "to_address": to_address,
            "amount": coins,
        }
    )


def _get_attached_coins_to_script():
    coins = []
    script_addr = get_script_address()
    for msg in get_attached_messages() or []:
        if (
            isinstance(msg, dict)
            and msg.get("@type") == "/cosmos.bank.v1beta1.MsgSend"
            and msg.get("to_address") == script_addr
        ):
            for c in msg.get("amount", []) or []:
                coins.append({"denom": c["denom"], "amount": c["amount"]})
    return coins


#############################
# Math helpers
#############################


def _floor_div(n: Decimal, d: Decimal) -> Decimal:
    return n // d


def _ceil_div(n: Decimal, d: Decimal) -> Decimal:
    return (n + d - 1) // d


#############################
# ID management
#############################


def _make_counter_index(kind: str) -> str:
    return f"counter|{kind}"


def _get_pool_index(pool_id: int) -> str:
    return f"pools/{pool_id}"


def _get_next_pool_id() -> int:
    counter_index = _make_counter_index("pools")
    entries = _storage_list(counter_index)
    current = entries[0]["data"] if entries else 0
    next_id = current + 1
    _storage_set(counter_index, next_id)
    return next_id


#############################
# Core AMM Primitives
#############################


def get_pool(pool_id: int) -> Pool:
    """Return pool by id (JSON-decoded), normalizing Decimal amounts."""
    pool_index = _get_pool_index(pool_id)
    raw = _storage_get(pool_index)
    data: Pool = {
        "pool_id": raw["pool_id"],
        "coin1": {
            "denom": raw["coin1"]["denom"],
            "balance": Decimal(raw["coin1"]["balance"]),
            "lent": Decimal(raw["coin1"]["lent"]),
            "collateral": Decimal(raw["coin1"]["collateral"]),
        },
        "total_shares": Decimal(raw["total_shares"]),
        "coin2": {
            "denom": raw["coin2"]["denom"],
            "balance": Decimal(raw["coin2"]["balance"]),
            "lent": Decimal(raw["coin2"]["lent"]),
            "collateral": Decimal(raw["coin2"]["collateral"]),
        },
        "shares_denom": raw["shares_denom"],
        "block_height": raw["block_height"],
        "created": raw["created"],
        "updated": raw.get("updated"),
        "num_trades": raw.get("num_trades", 0),
    }
    return data


def create_pool(coin_a: Any, coin_b: Any) -> Dict[str, Any]:
    """Create a constant-product pool.

    Decisions:
    - Canonical order: coin1 < coin2 lexicographically for deterministic pool identity.
    - Seed reserves by moving caller coins to the script address.
    - Mint fixed initial shares and send to caller; shares denom: `{DYS_NAME}/pools/{pool_id}`.
    Rationale:
    - Canonical ordering prevents duplicate pools; fixed initial shares simplify join math.
    State/Events:
    - Persist full Pool to storage and emit `poolupdate` for indexers.
    """
    caller = get_executor_address()
    denom_a = coin_a["denom"]
    denom_b = coin_b["denom"]
    amount_a = Decimal(coin_a["amount"])
    amount_b = Decimal(coin_b["amount"])

    if amount_a <= 0 or amount_b <= 0:
        raise ValueError("amounts must be > 0")
    if denom_a == denom_b:
        raise ValueError("denoms must differ")

    # Sort deterministically: coin1 has smaller denom
    if denom_a > denom_b:
        denom_a, denom_b = denom_b, denom_a
        amount_a, amount_b = amount_b, amount_a

    if _get_balance(caller, denom_a) < amount_a:
        raise ValueError(f"insufficient balance for {denom_a}")
    if _get_balance(caller, denom_b) < amount_b:
        raise ValueError(f"insufficient balance for {denom_b}")

    pool_id = _get_next_pool_id()
    pool_index = _get_pool_index(pool_id)
    initial_shares = 100000
    shares_root = DYS_NAME
    shares_denom = f"{shares_root}/pools/{pool_id}"
    block_info = get_block_info()

    pool: Pool = {
        "pool_id": pool_id,
        "coin1": {
            "denom": denom_a,
            "balance": amount_a,
            "lent": Decimal(0),
            "collateral": Decimal(0),
        },
        "coin2": {
            "denom": denom_b,
            "balance": amount_b,
            "lent": Decimal(0),
            "collateral": Decimal(0),
        },
        "total_shares": Decimal(initial_shares),
        "shares_denom": shares_denom,
        "block_height": block_info["height"],
        "created": block_info["time"],
        "updated": block_info["time"],
        "num_trades": 0,
    }

    coin1_dict: Coin = {"denom": denom_a, "amount": Decimal(amount_a)}
    coin2_dict: Coin = {"denom": denom_b, "amount": Decimal(amount_b)}
    _move_coins(
        inputs=[Input(address=caller, coins=[coin1_dict, coin2_dict])],
        outputs=[Output(address=get_script_address(), coins=[coin1_dict, coin2_dict])],
    )

    _storage_set(pool_index, pool)

    # Mint initial shares – requires explicit mint fee and attached udys
    required_udys = estimate_mint_fee(Decimal(initial_shares))
    attachments = _sum_attached_to_script_by_denom()
    attached_udys = attachments.get(UDYS_DENOM, Decimal(0))
    if attached_udys < required_udys:
        raise ValueError(
            f"insufficient attached udys for shares mint: {attached_udys} < {required_udys}"
        )
    _mint_coins(
        {"denom": shares_denom, "amount": Decimal(initial_shares)}, required_udys
    )
    _send_coins(
        get_script_address(),
        caller,
        [{"denom": shares_denom, "amount": Decimal(initial_shares)}],
    )

    emit_event("poolupdate", str(pool_id))
    return {"pool_id": pool_id}


def join_pool(pool_id: int, coin1: Any, coin2: Any) -> Dict[str, Any]:
    """Join a pool proportionally and mint shares.

    Decisions:
    - Move full sent amounts, then refund excess to keep pool ratios.
    - Proportions use current reserves; ceil for required amounts (refund favors pool).
    - Shares = min(floor(added1/ratio1), floor(added2/ratio2)).
    State/Events:
    - Update pool balances/total_shares, write storage, mint/send shares, emit `poolupdate`.
    """
    caller = get_executor_address()
    sent_amount1 = Decimal(coin1["amount"])
    sent_denom1 = coin1["denom"]
    sent_amount2 = Decimal(coin2["amount"])
    sent_denom2 = coin2["denom"]

    if sent_amount1 <= 0 or sent_amount2 <= 0:
        raise ValueError("amounts must be > 0")

    pool = get_pool(pool_id)
    if sent_denom1 != pool["coin1"]["denom"] or sent_denom2 != pool["coin2"]["denom"]:
        raise ValueError("must send coins matching pool coin1 and coin2 denoms")

    if _get_balance(caller, pool["coin1"]["denom"]) < sent_amount1:
        raise ValueError(f"insufficient balance for coin1: {pool['coin1']['denom']}")
    if _get_balance(caller, pool["coin2"]["denom"]) < sent_amount2:
        raise ValueError(f"insufficient balance for coin2: {pool['coin2']['denom']}")

    pool_coin1_bal = pool["coin1"]["balance"]
    pool_coin2_bal = pool["coin2"]["balance"]
    total_shares = pool["total_shares"]

    # proportional join; ceil rounds against joiner → pools are never underfunded
    correct_amount1 = _ceil_div(sent_amount2 * pool_coin1_bal, pool_coin2_bal)
    correct_amount2 = _ceil_div(sent_amount1 * pool_coin2_bal, pool_coin1_bal)

    refund1 = Decimal(0)
    if sent_amount1 > correct_amount1:
        refund1 = sent_amount1 - correct_amount1
    refund2 = Decimal(0)
    if sent_amount2 > correct_amount2:
        refund2 = sent_amount2 - correct_amount2

    added1 = sent_amount1 - refund1
    added2 = sent_amount2 - refund2

    if added1 <= 0 or added2 <= 0:
        raise ValueError("added amounts must be > 0 after refunds")

    sent_coin1: Coin = {
        "denom": pool["coin1"]["denom"],
        "amount": sent_amount1,
    }
    sent_coin2: Coin = {
        "denom": pool["coin2"]["denom"],
        "amount": sent_amount2,
    }
    _move_coins(
        inputs=[Input(address=caller, coins=[sent_coin1, sent_coin2])],
        outputs=[Output(address=get_script_address(), coins=[sent_coin1, sent_coin2])],
    )

    if refund1 > 0:
        _send_coins(
            get_script_address(),
            caller,
            [{"denom": pool["coin1"]["denom"], "amount": refund1}],
        )
    if refund2 > 0:
        _send_coins(
            get_script_address(),
            caller,
            [{"denom": pool["coin2"]["denom"], "amount": refund2}],
        )

    coin1_shares = _floor_div(added1 * total_shares, pool_coin1_bal)
    coin2_shares = _floor_div(added2 * total_shares, pool_coin2_bal)
    shares = min(coin1_shares, coin2_shares)

    if shares <= 0:
        raise ValueError("shares must be > 0")

    pool_index = _get_pool_index(pool_id)
    shares_denom = pool["shares_denom"]
    block_info = get_block_info()

    pool["coin1"]["balance"] += added1
    pool["coin2"]["balance"] += added2
    pool["total_shares"] += shares
    pool["updated"] = block_info["time"]
    _storage_set(pool_index, pool)

    # Mint new shares – requires explicit mint fee and attached udys
    required_udys = estimate_mint_fee(shares)
    attachments = _sum_attached_to_script_by_denom()
    attached_udys = attachments.get(UDYS_DENOM, Decimal(0))
    if attached_udys < required_udys:
        raise ValueError(
            f"insufficient attached udys for shares mint: {attached_udys} < {required_udys}"
        )
    _mint_coins({"denom": shares_denom, "amount": shares}, required_udys)
    _send_coins(
        get_script_address(),
        caller,
        [{"denom": shares_denom, "amount": shares}],
    )

    refund = []
    if refund1 > 0:
        refund.append({"denom": pool["coin1"]["denom"], "amount": refund1})
    if refund2 > 0:
        refund.append({"denom": pool["coin2"]["denom"], "amount": refund2})

    emit_event("pool_id", str(pool_id))
    return {
        "pool_id": pool_id,
        "shares": shares,
        "share_denom": shares_denom,
        "refund": refund,
    }


def exit_pool(pool_id: int, shares_coin: Any) -> List[Coin]:
    """Exit a pool proportionally and burn shares.

    Decisions:
    - Require bank supply to match stored `total_shares` (consistency guard).
    - Send shares to script, burn, then compute floor-proportional outputs per reserve.
    - If both outputs floor to 0, reject as dust.
    State/Events:
    - Update pool balances/total_shares, write storage, send outs, emit `poolupdate`.
    """
    caller = get_executor_address()
    shares_amount = Decimal(shares_coin["amount"])
    shares_denom = shares_coin["denom"]

    if shares_amount <= 0:
        raise ValueError("shares amount must be > 0")

    pool = get_pool(pool_id)
    if shares_denom != pool["shares_denom"]:
        raise ValueError(f"invalid shares denom: {shares_denom}")

    if _get_balance(caller, shares_denom) < shares_amount:
        raise ValueError(f"insufficient shares balance: {shares_denom}")

    # defend against drift: stored supply must equal bank supply
    total_shares_supply = _get_supply(shares_denom)
    if total_shares_supply != pool["total_shares"]:
        raise ValueError("total shares mismatch between storage and supply")

    _send_coins(
        get_script_address(),
        caller,
        [{"denom": shares_denom, "amount": shares_amount}],
    )

    _burn_coins({"denom": shares_denom, "amount": shares_amount})

    out1 = _floor_div(shares_amount * pool["coin1"]["balance"], total_shares_supply)
    out2 = _floor_div(shares_amount * pool["coin2"]["balance"], total_shares_supply)

    if out1 <= 0 and out2 <= 0:
        raise ValueError("shares amount too small to exit")

    pool_index = _get_pool_index(pool_id)
    block_info = get_block_info()

    pool["coin1"]["balance"] -= out1
    pool["coin2"]["balance"] -= out2
    pool["total_shares"] -= shares_amount
    pool["updated"] = block_info["time"]
    _storage_set(pool_index, pool)

    amount: List[Coin] = []
    if out1 > 0:
        out1_coin: Coin = {"denom": pool["coin1"]["denom"], "amount": out1}
        amount.append(out1_coin)
        _send_coins(
            get_script_address(),
            caller,
            [{"denom": out1_coin["denom"], "amount": out1}],
        )
    if out2 > 0:
        out2_coin: Coin = {"denom": pool["coin2"]["denom"], "amount": out2}
        amount.append(out2_coin)
        _send_coins(
            get_script_address(),
            caller,
            [{"denom": out2_coin["denom"], "amount": out2}],
        )

    emit_event("pool_id", str(pool_id))
    return amount


def pool_swap(
    pool_ids_str: str, input_coin: Coin, minimum_out_amount: int, out_denom: str
) -> Dict[str, Any]:
    """Multi-hop constant-product swap.

    Decisions:
    - Input is moved to the script first; each hop updates reserves and emits `poolupdate`.
    - Per-hop AMM: out = r_out - ceil(k / (r_in + in)); rounds against trader.
    - Reject zero/negative hop outputs or reserve depletion.
    Post-conditions:
    - Final output must meet `minimum_out_amount` and match `out_denom`; then send to caller.
    Atomicity/Gas:
    - Any failure reverts the tx; multi-hop costs scale with storage writes/events.
    """
    caller = get_executor_address()
    input_amount = Decimal(input_coin["amount"])
    input_denom = input_coin["denom"]

    if input_amount <= 0:
        raise ValueError("input amount must be > 0")

    if _get_balance(caller, input_denom) < input_amount:
        raise ValueError(f"insufficient input balance: {input_denom}")

    pool_ids = [int(pid.strip()) for pid in pool_ids_str.split() if pid.strip()]
    if not pool_ids:
        raise ValueError("at least one pool ID required")

    input_coin_str: Coin = {"denom": input_denom, "amount": input_amount}
    _move_coins(
        inputs=[{"address": caller, "coins": [input_coin_str]}],
        outputs=[{"address": get_script_address(), "coins": [input_coin_str]}],
    )

    current_amount = input_amount
    current_denom = input_denom
    block_info = get_block_info()

    for pool_id in pool_ids:
        pool = get_pool(pool_id)
        k = pool["coin1"]["balance"] * pool["coin2"]["balance"]

        if current_denom == pool["coin1"]["denom"]:
            new_in_bal = pool["coin1"]["balance"] + current_amount
            # constant-product: out = r_out - ceil(k / (r_in + in))
            output_amount = pool["coin2"]["balance"] - _ceil_div(k, new_in_bal)
            if output_amount <= 0:
                raise ValueError("swap output too small")
            pool["coin2"]["balance"] -= output_amount
            pool["coin1"]["balance"] = new_in_bal
            output_denom = pool["coin2"]["denom"]
        elif current_denom == pool["coin2"]["denom"]:
            new_in_bal = pool["coin2"]["balance"] + current_amount
            # constant-product: out = r_out - ceil(k / (r_in + in))
            output_amount = pool["coin1"]["balance"] - _ceil_div(k, new_in_bal)
            if output_amount <= 0:
                raise ValueError("swap output too small")
            pool["coin1"]["balance"] -= output_amount
            pool["coin2"]["balance"] = new_in_bal
            output_denom = pool["coin1"]["denom"]
        else:
            raise ValueError(f"input denom {current_denom} not in pool {pool_id}")

        if pool["coin1"]["balance"] <= 0 or pool["coin2"]["balance"] <= 0:
            raise ValueError("swap depletes pool reserve")

        current_amount = output_amount
        current_denom = output_denom

        pool["updated"] = block_info["time"]
        pool["num_trades"] = (
            pool["num_trades"] + 1 if pool["num_trades"] is not None else 1
        )
        _storage_set(_get_pool_index(pool_id), pool)
        emit_event("pool_id", str(pool_id))

    if current_amount < minimum_out_amount:
        raise ValueError(
            f"output {current_amount} {current_denom} below minimum {minimum_out_amount} {out_denom}"
        )
    if current_denom != out_denom:
        raise ValueError(f"output denom {current_denom} != expected {out_denom}")

    _send_coins(
        get_script_address(),
        caller,
        [{"denom": current_denom, "amount": current_amount}],
    )

    return {"denom": current_denom, "amount": current_amount}
