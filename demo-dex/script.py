from typing import Any, Dict, List, Optional, Tuple, Literal, TypedDict
from decimal import Decimal
import json

# Dyslang runtime: on-chain Python for Dyson Protocol
from dys import (  # type: ignore
    _msg,
    _query,
    get_executor_address,
    get_script_address,
)


# Price keying using simple float formatting


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
    """Delete one or more indexes."""
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


def _get_balance(address: str, denom: str) -> int:
    res = _query(
        {
            "@type": "/cosmos.bank.v1beta1.QueryBalanceRequest",
            "address": address,
            "denom": denom,
        }
    )
    return int(res["balance"]["amount"])


#############################
# Offer ID management
#############################


def _counter_key(kind: str) -> str:
    return f"counter/{kind}"


def _get_next_offer_id() -> int:
    key = _counter_key("offers")
    entries = _storage_list(key)
    current = int(entries[0]["data"]) if entries else 0
    next_id = current + 1
    _storage_set(key, str(next_id))
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
        raise ValueError("offer_amount must be > 0")
    price = receive_amount / offer_amount
    total_width = int_width + 1 + digits
    return f"{price:0{total_width}.{digits}f}"


#############################
# Coin parsing
#############################


def _parse_coin(obj: Any) -> "Coin":
    """Return (amount:int, denom:str) from a JSON coin object {amount, denom}."""
    obj["amount"] = Decimal(obj["amount"])
    return obj


#############################
# TypedDicts for complex types
#############################


class Coin(TypedDict):
    denom: str
    amount: Decimal


class OfferData(TypedDict):
    owner: str
    have: Coin
    want: Coin
    offer_id: int
    status: Literal["open", "filled"]


class TakeResult(TypedDict):
    success: bool
    error: Optional[str]


class MakeResult(TypedDict):
    offer_id: int


def get_offer(offer_id: int) -> OfferData:
    """Return offer by id (JSON-decoded), normalizing Decimal amounts."""
    id_key = f"offer_id|{offer_id:020d}"
    data: OfferData = _storage_get(id_key)  # type: ignore[assignment]
    data["have"]["amount"] = Decimal(str(data["have"]["amount"]))
    data["want"]["amount"] = Decimal(str(data["want"]["amount"]))
    return data


#############################
# Core DEX API
#############################


def make(have: Any, want: Any) -> MakeResult:
    """Create an offer without escrow; validate maker balance and record offer."""
    have_coin = _parse_coin(have)
    want_coin = _parse_coin(want)

    maker = get_executor_address()
    if _get_balance(maker, have_coin["denom"]) < (have_coin["amount"]):
        raise ValueError("insufficient maker balance")
    owner = maker

    offer_id = _get_next_offer_id()

    data: OfferData = {
        "owner": owner,
        "have": {"denom": have_coin["denom"], "amount": have_coin["amount"]},
        "want": {"denom": want_coin["denom"], "amount": want_coin["amount"]},
        "offer_id": offer_id,
        "status": "open",
    }

    id_key = f"offer_id|{offer_id:020d}"
    _storage_set(id_key, data)
    # Want index
    _storage_set(
        f"w|{want_coin['denom']}|h|{have_coin['denom']}|{_price_key(
        receive_amount=(have_coin['amount']),
        offer_amount=(want_coin['amount']),
    )}|wa|{int(want_coin['amount']):020d}|{offer_id:020d}",
        id_key,
    )
    # Have index
    _storage_set(
        f"h|{have_coin['denom']}|w|{want_coin['denom']}|{_price_key(
        receive_amount=(want_coin['amount']),
        offer_amount=(have_coin['amount']),
    )}|ha|{int(have_coin['amount']):020d}|{offer_id:020d}",
        id_key,
    )
    _storage_set(f"owner_offers|{owner}|{offer_id:020d}", id_key)

    return {"offer_id": offer_id}


def take(
    offer_id: int,
) -> TakeResult:
    """Take full offer only; validate balance, move coins, mark as filled."""
    taker = get_executor_address()

    id_key = f"offer_id|{offer_id:020d}"
    data: OfferData = _storage_get(id_key)
    have: Coin = data["have"]
    want: Coin = data["want"]
    have["amount"] = Decimal(str(have["amount"]))
    want["amount"] = Decimal(str(want["amount"]))
    owner = data["owner"]

    if data.get("status") == "filled":
        raise ValueError("offer already filled")

    _msg(
        {
            "@type": "/dysonprotocol.nameservice.v1.MsgMoveCoins",
            "name_destination": get_script_address(),
            "inputs": [
                {
                    "address": owner,
                    "coins": [{"denom": have["denom"], "amount": str(have["amount"])}],
                },
                {
                    "address": taker,
                    "coins": [{"denom": want["denom"], "amount": str(want["amount"])}],
                },
            ],
            "outputs": [
                {
                    "address": taker,
                    "coins": [{"denom": have["denom"], "amount": str(have["amount"])}],
                },
                {
                    "address": owner,
                    "coins": [{"denom": want["denom"], "amount": str(want["amount"])}],
                },
            ],
        }
    )

    data["status"] = "filled"
    _storage_set(id_key, data)

    return {"success": True, "error": None}
