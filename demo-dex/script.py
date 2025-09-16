from typing import Any, Dict, List, Optional, Literal, TypedDict
import json
from decimal import Decimal
import math

# Dyslang runtime: on-chain Python for Dyson Protocol
from dys import (  # type: ignore
    _msg,
    _query,
    get_executor_address,
    get_script_address,
    get_block_info,
    emit_event,
)


DYS_NAME = "whaleswap.dys"


def _floor_div(n: Decimal, d: Decimal) -> Decimal:
    return n // d


def _ceil_div(n: Decimal, d: Decimal) -> Decimal:
    return (n + d - 1) // d


#############################
# Storage helpers (on-chain)
#############################


def _storage_get(index: str) -> Any:
    """Get value for index (JSON-decoded)."""
    res = _query(
        {
            "@type": "/dysonprotocol.storage.v1.QueryStorageGetRequest",
            "owner": get_script_address(),
            "index": index,
        }
    )
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


class Trade(TypedDict):
    trade_id: int
    offer_id: int
    taker: str
    height: int
    timestamp: str
    sent: Coin
    received: Coin


class OfferData(TypedDict):
    offer_id: int
    status: Literal["open", "closed", "cancelled"]
    maker: str
    updated_height: int
    updated_timestamp: str
    initial_have: Coin
    initial_want: Coin
    remaining_have: Coin
    remaining_want: Coin
    unit_have_int: Decimal
    unit_want_int: Decimal
    remaining_units: Decimal


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


def _mint_coins(coin: Coin) -> Dict[str, Any]:
    """Mint a single coin amount to the script address."""
    return _msg(
        {
            "@type": "/dysonprotocol.nameservice.v1.MsgMintCoins",
            "name_destination": get_script_address(),
            "amount": [coin],
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


#############################
# ID management
#############################


def _make_counter_index(kind: str) -> str:
    return f"counter|{kind}"


def _get_next_offer_id() -> int:
    counter_index = _make_counter_index("offers")
    entries = _storage_list(counter_index)
    current = entries[0]["data"] if entries else 0
    next_id = current + 1
    _storage_set(counter_index, next_id)
    return next_id


def _get_next_trade_id() -> int:
    counter_index = _make_counter_index("trades")
    entries = _storage_list(counter_index)
    current = entries[0]["data"] if entries else 0
    next_id = current + 1
    _storage_set(counter_index, next_id)
    return next_id


def _get_next_pool_id() -> int:
    counter_index = _make_counter_index("pools")
    entries = _storage_list(counter_index)
    current = entries[0]["data"] if entries else 0
    next_id = current + 1
    _storage_set(counter_index, next_id)
    return next_id


#############################
# Price keying (lexicographic)
#############################


def _price_key(
    receive_amount: Decimal,
    offer_amount: Decimal,
    digits: int = 10,
    int_width: int = 10,
) -> str:
    if offer_amount <= 0:
        raise ValueError(f"offer_amount must be > 0: {offer_amount}")
    price = receive_amount / offer_amount
    total_width = int_width + 1 + digits
    return f"{price:0{total_width}.{digits}f}"


def _get_status(offer: OfferData) -> str:
    return offer["status"]


def _make_offer_id_index(offer_id: int) -> str:
    return f"oid|{offer_id:010d}"


def _make_trade_id_index(trade_id: int) -> str:
    return f"tid|{trade_id:010d}"


def _make_taker_trade_index(taker: str, trade_id: int) -> str:
    return f"taker_trade|{taker}|{_make_trade_id_index(trade_id)}"


def _make_offer_trade_index(offer_id: int, trade_id: int) -> str:
    return (
        f"offer_trade|{_make_offer_id_index(offer_id)}|{_make_trade_id_index(trade_id)}"
    )


def _make_owner_index(offer: OfferData) -> str:
    return (
        f"maker|{offer['maker']}|status|{offer['status']}|id|{offer['offer_id']:010d}"
    )


def _make_want_index(offer: OfferData) -> str:
    want = offer["remaining_want"]
    have = offer["remaining_have"]
    price_key = _price_key(receive_amount=have["amount"], offer_amount=want["amount"])
    return f"w|{want['denom']}|h|{have['denom']}|{price_key}|{_make_offer_id_index(offer['offer_id'])}"


def _make_have_index(offer: OfferData) -> str:
    have = offer["remaining_have"]
    want = offer["remaining_want"]
    price_key = _price_key(receive_amount=want["amount"], offer_amount=have["amount"])
    return f"h|{have['denom']}|w|{want['denom']}|{price_key}|{_make_offer_id_index(offer['offer_id'])}"


def _get_offer_indexes(offer: OfferData) -> List[str]:
    keys = [_make_owner_index(offer)]
    if _get_status(offer) == "open":
        keys += [_make_want_index(offer), _make_have_index(offer)]
    return keys


def _make_coin(raw_coin: dict[str, Any]) -> Coin:
    return {
        "denom": raw_coin["denom"],
        "amount": Decimal(raw_coin["amount"]),
    }


def _get_offer(offer_id: int) -> OfferData:
    """Return offer by id (JSON-decoded), normalizing Decimal amounts."""
    offer_id_index = _make_offer_id_index(offer_id)
    raw = _storage_get(offer_id_index)
    data: OfferData = {
        "offer_id": raw["offer_id"],
        "status": raw["status"],
        "maker": raw["maker"],
        "updated_height": raw["updated_height"],
        "updated_timestamp": raw["updated_timestamp"],
        "initial_have": _make_coin(raw["initial_have"]),
        "initial_want": _make_coin(raw["initial_want"]),
        "remaining_have": _make_coin(raw["remaining_have"]),
        "remaining_want": _make_coin(raw["remaining_want"]),
        "unit_have_int": Decimal(raw["unit_have_int"]),
        "unit_want_int": Decimal(raw["unit_want_int"]),
        "remaining_units": Decimal(raw["remaining_units"]),
    }
    return data


def _get_pool_index(pool_id: int) -> str:
    return f"pool|{pool_id:010d}"


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


#############################
# Core DEX API (Order Book)
#############################


def make(have_coin: Any, want_coin: Any) -> Dict[str, int]:
    """Create an offer without escrow; validate maker balance and record offer."""

    maker = get_executor_address()
    have_amount = Decimal(have_coin["amount"])
    want_amount = Decimal(want_coin["amount"])

    # amounts must be positive
    if have_amount <= 0 or want_amount <= 0:
        raise ValueError(
            f"amounts must be > 0, have_amount: {have_amount}, want_amount: {want_amount}"
        )
    if have_coin["denom"] == want_coin["denom"]:
        raise ValueError(
            f"have_coin and want_coin cannot have the same denom: {have_coin['denom']}"
        )
    if _get_balance(maker, have_coin["denom"]) < have_amount:
        raise ValueError(
            f"insufficient balance for {maker}: {_get_balance(maker, have_coin['denom'])} {have_coin['denom']} < {have_amount} {have_coin['denom']}"
        )

    lcm_hw = math.lcm(int(have_amount), int(want_amount))
    unit_have_int = lcm_hw // want_amount
    unit_want_int = lcm_hw // have_amount
    remaining_units = have_amount // unit_have_int

    offer_id = _get_next_offer_id()
    block_info = get_block_info()

    data: OfferData = {
        "offer_id": offer_id,
        "status": "open",
        "maker": maker,
        "updated_height": block_info["height"],
        "updated_timestamp": block_info["time"],
        "initial_have": _make_coin(have_coin),
        "initial_want": _make_coin(want_coin),
        "remaining_have": _make_coin(have_coin),
        "remaining_want": _make_coin(want_coin),
        "unit_have_int": unit_have_int,
        "unit_want_int": unit_want_int,
        "remaining_units": remaining_units,
    }

    offer_id_index = _make_offer_id_index(offer_id)
    _storage_set(offer_id_index, data)
    for idx in _get_offer_indexes(data):
        _storage_set(idx, offer_id_index)

    emit_event("offer_created", f"{offer_id}")
    emit_event("offer_maker", f"{maker}")
    emit_event("offer_have_denom", f"{have_coin['denom']}")
    emit_event("offer_want_denom", f"{want_coin['denom']}")
    return {"offer_id": offer_id}


def take(offer_id: int, take_units: int | Decimal | None = None) -> Dict[str, Any]:
    """Take specified units from an open offer; validate units, balances, move coins, record trade, update offer, and return actual sent/received coins for taker."""
    taker = get_executor_address()

    offer = _get_offer(offer_id)

    if _get_status(offer) != "open":
        raise ValueError(f"offer not open: {_get_status(offer)}")

    remaining_units = Decimal(offer["remaining_units"])
    if take_units is None:
        take_units = remaining_units
    if not (1 <= take_units <= remaining_units):
        raise ValueError(
            f"take_units must satisfy 1 <= take_units ({take_units}) <= remaining_units ({remaining_units})"
        )

    unit_want_int = offer["unit_want_int"]
    unit_have_int = offer["unit_have_int"]
    actual_sent = take_units * unit_want_int
    actual_receive = take_units * unit_have_int

    have_denom = offer["remaining_have"]["denom"]
    want_denom = offer["remaining_want"]["denom"]

    if _get_balance(taker, want_denom) < actual_sent:
        raise ValueError(
            f"insufficient taker balance for {want_denom}: {_get_balance(taker, want_denom)} {want_denom} < {actual_sent} {want_denom}"
        )
    if _get_balance(offer["maker"], have_denom) < actual_receive:
        raise ValueError(
            f"insufficient maker balance for {have_denom}: {_get_balance(offer['maker'], have_denom)} {have_denom} < {actual_receive} {have_denom}"
        )

    have_coin: Coin = {"denom": have_denom, "amount": Decimal(actual_receive)}
    send_coin_actual: Coin = {"denom": want_denom, "amount": Decimal(actual_sent)}

    old_indexes = _get_offer_indexes(offer)

    _move_coins(
        inputs=[
            Input(address=offer["maker"], coins=[have_coin]),
            Input(address=taker, coins=[send_coin_actual]),
        ],
        outputs=[
            Output(address=taker, coins=[have_coin]),
            Output(address=offer["maker"], coins=[send_coin_actual]),
        ],
    )

    # Record trade
    trade_id = _get_next_trade_id()
    block_info = get_block_info()
    trade: Trade = {
        "trade_id": trade_id,
        "offer_id": offer_id,
        "taker": taker,
        "height": block_info["height"],
        "timestamp": block_info["time"],
        "sent": {"denom": want_denom, "amount": Decimal(actual_sent)},
        "received": {"denom": have_denom, "amount": Decimal(actual_receive)},
    }
    trade_index = _make_trade_id_index(trade_id)
    _storage_set(trade_index, trade)

    # Trade lookups
    _storage_set(_make_taker_trade_index(taker, trade_id), trade_index)
    _storage_set(_make_offer_trade_index(offer_id, trade_id), trade_index)

    # Update offer
    offer["remaining_units"] -= take_units
    new_remaining_units = offer["remaining_units"]
    if new_remaining_units == 0:
        offer["status"] = "closed"
        offer["updated_height"] = block_info["height"]
        offer["updated_timestamp"] = block_info["time"]
        offer["remaining_have"]["amount"] = Decimal(0)
        offer["remaining_want"]["amount"] = Decimal(0)
    else:
        offer["remaining_have"]["amount"] = Decimal(new_remaining_units * unit_have_int)
        offer["remaining_want"]["amount"] = Decimal(new_remaining_units * unit_want_int)
        offer["updated_height"] = block_info["height"]
        offer["updated_timestamp"] = block_info["time"]

    offer_id_index = _make_offer_id_index(offer_id)
    new_indexes = _get_offer_indexes(offer)
    to_delete = [k for k in old_indexes if k not in new_indexes]
    if to_delete:
        _storage_delete(to_delete)
    for k in new_indexes:
        _storage_set(k, offer_id_index)
    _storage_set(offer_id_index, offer)

    emit_event("offer_taken", f"{offer_id}")
    emit_event("offer_taker", f"{taker}")
    emit_event("trade_id", f"{trade_id}")
    emit_event("offer_have_denom", f"{have_denom}")
    emit_event("offer_want_denom", f"{want_denom}")

    return {
        "sent": {"denom": want_denom, "amount": int(actual_sent)},
        "received": {"denom": have_denom, "amount": int(actual_receive)},
    }


def cancel(offer_id: int):

    offer = _get_offer(offer_id)
    if get_executor_address() != offer["maker"]:
        raise ValueError(
            f"only the maker can cancel an offer: {get_executor_address()} != {offer['maker']}"
        )

    if _get_status(offer) != "open":
        raise ValueError(f"offer not open: {_get_status(offer)}")

    old_indexes = _get_offer_indexes(offer)

    block_info = get_block_info()
    offer["status"] = "cancelled"
    offer["updated_height"] = block_info["height"]
    offer["updated_timestamp"] = block_info["time"]

    new_indexes = _get_offer_indexes(offer)
    to_delete = [k for k in old_indexes if k not in new_indexes]
    offer_id_index = _make_offer_id_index(offer_id)
    if to_delete:
        _storage_delete(to_delete)
    for k in new_indexes:
        _storage_set(k, offer_id_index)
    _storage_set(offer_id_index, offer)
    emit_event("offer_cancelled", f"{offer_id}")


#############################
# Core AMM Primitives
#############################


def create_pool(coin_a: Any, coin_b: Any) -> Dict[str, Any]:
    """Create a pool; sorts denoms deterministically (coin1 < coin2 lexicographically), moves coins to script, mints initial shares."""
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

    _mint_coins({"denom": shares_denom, "amount": Decimal(initial_shares)})
    _send_coins(
        get_script_address(),
        caller,
        [{"denom": shares_denom, "amount": Decimal(initial_shares)}],
    )

    emit_event("poolupdate", str(pool_id))
    return {"pool_id": pool_id}


def join_pool(pool_id: int, coin1: Any, coin2: Any) -> Dict[str, Any]:
    """Join a pool proportionally; moves full sent coins to script, refunds excess, mints shares."""
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

    _mint_coins({"denom": shares_denom, "amount": shares})
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

    emit_event("poolupdate", str(pool_id))
    return {
        "pool_id": pool_id,
        "shares": shares,
        "share_denom": shares_denom,
        "refund": refund,
    }


def exit_pool(pool_id: int, shares_coin: Any) -> List[Coin]:
    """Exit a pool; moves shares to script, burns, sends proportional coins back."""
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

    emit_event("poolupdate", str(pool_id))
    return amount


def swap(
    pool_ids_str: str, input_coin: Coin, minimum_out_amount: int, out_denom: str
) -> Dict[str, Any]:
    """Perform swap (multi-hop supported); moves input to script, sends output, updates pools."""
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
            output_amount = pool["coin2"]["balance"] - _ceil_div(k, new_in_bal)
            if output_amount <= 0:
                raise ValueError("swap output too small")
            pool["coin2"]["balance"] -= output_amount
            pool["coin1"]["balance"] = new_in_bal
            output_denom = pool["coin2"]["denom"]
        elif current_denom == pool["coin2"]["denom"]:
            new_in_bal = pool["coin2"]["balance"] + current_amount
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
        emit_event("poolupdate", str(pool_id))

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
