raise RuntimeError("This file is not used anymore. Use the module instead.")


from typing import Any, Dict, List, Optional
import json
from decimal import Decimal

# Dyslang runtime: on-chain Python for Dyson Protocol
from dys import (
    _msg,  # type: ignore
    _query,  # type: ignore
    get_executor_address,  # type: ignore
    get_script_address,  # type: ignore
    get_block_info,  # type: ignore
    emit_event,  # type: ignore
    get_attached_messages,  # type: ignore
    DysQueryException,  # type: ignore
)


DYS_NAME = "whaleswap.dys"
LIQUID_PREFIX = f"{DYS_NAME}/coins/"


# -----------------------------
# Storage helpers (script-owned)
# -----------------------------


def _storage_get(index: str) -> Any:
    res = _query(
        {
            "@type": "/dysonprotocol.storage.v1.QueryStorageGetRequest",
            "owner": get_script_address(),
            "index": index,
        }
    )
    return json.loads(res["entry"]["data"])  # type: ignore[index]


def _storage_set(index: str, data: Any) -> Dict[str, Any]:
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
    return _msg(
        {
            "@type": "/dysonprotocol.storage.v1.MsgStorageDelete",
            "owner": get_script_address(),
            "indexes": indexes,
        }
    )


def _storage_list(prefix: str) -> List[Dict[str, Any]]:
    res = _query(
        {
            "@type": "/dysonprotocol.storage.v1.QueryStorageListRequest",
            "owner": get_script_address(),
            "index_prefix": prefix,
        }
    )
    entries = res["entries"]
    for entry in entries:
        entry["data"] = json.loads(entry["data"])  # type: ignore[index]
    return entries


# -----------------------------
# Params (auction-class policy)
# -----------------------------


def _params_index(key: str) -> str:
    return f"params|auction|{key}"


def _get_param_str(key: str, default: str) -> str:
    entries = _storage_list(_params_index(key))
    return entries[0]["data"] if entries else default


def _set_param_str(key: str, value: str) -> Dict[str, Any]:
    return _storage_set(_params_index(key), value)


def admin_set_auction_params(key: str, value: str) -> Dict[str, Any]:
    caller = get_executor_address()
    assert caller == get_script_address(), "only script owner can set auction params"
    assert key in (
        "valuation_fee_pct",
        "valuation_period",
        "bid_timeout",
        "min_bid_percent_increase",
    ), f"invalid key: {key}"
    _set_param_str(key, value)
    emit_event(key, value)
    return {key: value}


def _get_auction_params() -> Dict[str, str]:
    return {
        "valuation_fee_pct": _get_param_str("valuation_fee_pct", "0.01"),
        "valuation_period": _get_param_str("valuation_period", "24h"),
        "bid_timeout": _get_param_str("bid_timeout", "3600s"),
        "min_bid_percent_increase": _get_param_str("min_bid_percent_increase", "0.01"),
    }


# -----------------------------
# Coins and attachments helpers
# -----------------------------


def _is_liquid_denom(denom: str) -> bool:
    return isinstance(denom, str) and denom.startswith(LIQUID_PREFIX)


def _sum_attached_to_script_by_denom() -> Dict[str, Decimal]:
    totals: Dict[str, Decimal] = {}
    script_addr = get_script_address()
    for msg in get_attached_messages() or []:
        if (
            isinstance(msg, dict)
            and msg.get("@type") == "/cosmos.bank.v1beta1.MsgSend"
            and msg.get("to_address") == script_addr
        ):
            for c in msg.get("amount", []) or []:
                d = c["denom"]
                a = Decimal(c["amount"])  # type: ignore[arg-type]
                totals[d] = totals.get(d, Decimal(0)) + a
    return totals


def _send_coins(
    from_addr: str, to_addr: str, coins: List[Dict[str, Any]]
) -> Dict[str, Any]:
    return _msg(
        {
            "@type": "/cosmos.bank.v1beta1.MsgSend",
            "from_address": from_addr,
            "to_address": to_addr,
            "amount": coins,
        }
    )


def _get_balance(address: str, denom: str) -> Decimal:
    res = _query(
        {
            "@type": "/cosmos.bank.v1beta1.QueryBalanceRequest",
            "address": address,
            "denom": denom,
        }
    )
    return Decimal(res["balance"]["amount"])  # type: ignore[index]


def _get_supply(denom: str) -> Decimal:
    res = _query(
        {
            "@type": "/cosmos.bank.v1beta1.QuerySupplyOfRequest",
            "denom": denom,
        }
    )
    return Decimal(res["amount"]["amount"])  # type: ignore[index]


# -----------------------------
# ID mgmt and indices
# -----------------------------


def _make_counter_index(kind: str) -> str:
    return f"counter|{kind}"


def _get_next_auction_id() -> int:
    idx = _make_counter_index("auctions")
    entries = _storage_list(idx)
    current = entries[0]["data"] if entries else 0
    next_id = current + 1
    _storage_set(idx, next_id)
    return next_id


def _auction_id_index(auction_id: int) -> str:
    return f"auction|id|{auction_id:010d}"


def _auction_sb_index(sell_denom: str, bid_denom: str) -> str:
    return f"auction|s|{sell_denom}|b|{bid_denom}"


def _auction_class(class_id: str, nft_id: str) -> str:
    return f"{class_id}|{nft_id}"


# -----------------------------
# Nameservice/NFT helpers
# -----------------------------


def _auction_class_id(sell_denom: str, bid_denom: str) -> str:
    return f"{DYS_NAME}/auction/{sell_denom}/{bid_denom}"


def _class_created_index(class_id: str) -> str:
    return f"auction|class_created|{class_id}"


def _class_exists(class_id: str) -> bool:
    try:
        res = _query(
            {
                "@type": "/dysonprotocol.nft.v1beta1.QueryClassRequest",
                "class_id": class_id,
            }
        )
        return isinstance(res, dict) and (res.get("class") is not None)
    except DysQueryException as e:
        msg = str(e)
        if (
            ("not found class" in msg)
            or ("class not found" in msg)
            or ("ErrClassNotExists" in msg)
        ):
            return False
        raise e


def _set_class_with_policy(class_id: str, bid_denom: str) -> None:
    params = _get_auction_params()

    # Upsert class basic info
    _msg(
        {
            "@type": "/dysonprotocol.nameservice.v1.MsgSaveClass",
            "name_destination": get_script_address(),
            "class_id": class_id,
            "name": "Whaleswap Auction",
            "symbol": "WSA",
            "description": "Auction class for escrowed solid coins",
            "uri": "",
            "uri_hash": "",
        }
    )

    # Set class policy knobs
    _msg(
        {
            "@type": "/dysonprotocol.nameservice.v1.MsgSetNFTClassAlwaysListed",
            "name_destination": get_script_address(),
            "class_id": class_id,
            "always_listed": True,
        }
    )
    _msg(
        {
            "@type": "/dysonprotocol.nameservice.v1.MsgSetNFTClassValuationFeePct",
            "name_destination": get_script_address(),
            "class_id": class_id,
            "valuation_fee_pct": params["valuation_fee_pct"],
        }
    )
    _msg(
        {
            "@type": "/dysonprotocol.nameservice.v1.MsgSetNFTClassValuationPeriod",
            "name_destination": get_script_address(),
            "class_id": class_id,
            "valuation_period": params["valuation_period"],
        }
    )
    _msg(
        {
            "@type": "/dysonprotocol.nameservice.v1.MsgSetNFTClassBidTimeout",
            "name_destination": get_script_address(),
            "class_id": class_id,
            "bid_timeout": params["bid_timeout"],
        }
    )
    # Only allow setting non-default allowed denoms if the denom has supply to satisfy keeper validation
    if _get_supply(bid_denom) > 0:
        _msg(
            {
                "@type": "/dysonprotocol.nameservice.v1.MsgSetNFTClassAllowedDenoms",
                "name_destination": get_script_address(),
                "class_id": class_id,
                "allowed_denoms": [bid_denom],
            }
        )
    _msg(
        {
            "@type": "/dysonprotocol.nameservice.v1.MsgSetNFTClassMinimumBidPercentIncrease",
            "name_destination": get_script_address(),
            "class_id": class_id,
            "minimum_bid_percent_increase": params["min_bid_percent_increase"],
        }
    )
    # done


def _mint_nft(class_id: str, nft_id: str, owner: str) -> None:
    # Mint to script destination, then standard NFT Send to owner
    _msg(
        {
            "@type": "/dysonprotocol.nameservice.v1.MsgMintNFT",
            "name_destination": get_script_address(),
            "class_id": class_id,
            "nft_id": nft_id,
        }
    )
    _msg(
        {
            "@type": "/dysonprotocol.nft.v1beta1.MsgSend",
            "class_id": class_id,
            "id": nft_id,
            "sender": get_script_address(),
            "receiver": owner,
        }
    )


def _set_nft_metadata(class_id: str, nft_id: str, metadata: Dict[str, Any]) -> None:
    _msg(
        {
            "@type": "/dysonprotocol.nameservice.v1.MsgSetNFTMetadata",
            "name_destination": get_script_address(),
            "class_id": class_id,
            "nft_id": nft_id,
            "metadata": json.dumps(metadata, default=str),
            "uri": "",
            "uri_hash": "",
        }
    )


def _set_valuation(
    owner: str, class_id: str, nft_id: str, bid_denom: str, amount: Decimal
) -> None:
    _msg(
        {
            "@type": "/dysonprotocol.nameservice.v1.MsgSetValuation",
            "owner": owner,
            "nft_class_id": class_id,
            "nft_id": nft_id,
            "valuation": {"denom": bid_denom, "amount": amount},
            "max_valuation_fee_pct": "1.0",  # guard generously; class fee pct is small
        }
    )


def _query_nft_owner(class_id: str, nft_id: str) -> str:
    res = _query(
        {
            "@type": "/dysonprotocol.nft.v1beta1.QueryOwnerRequest",
            "class_id": class_id,
            "id": nft_id,
        }
    )
    return res.get("owner", "")


def _query_nft_data_current_bidder(class_id: str, nft_id: str) -> Optional[str]:
    # Best-effort parse of Any; gateway often expands Any to JSON with fields
    res = _query(
        {
            "@type": "/dysonprotocol.nft.v1beta1.QueryNFTRequest",
            "class_id": class_id,
            "id": nft_id,
        }
    )
    nft = res.get("nft") or {}
    data = nft.get("data") or {}
    # Case 1: expanded Any
    if isinstance(data, dict) and ("current_bidder" in data):
        return data.get("current_bidder") or None
    # Case 2: nested under 'value' not decodable in dyslang → treat as unknown (block redeem)
    return None


# -----------------------------
# Public API
# -----------------------------


def open_auction(
    bid_denom: str,
) -> Dict[str, Any]:
    seller = get_executor_address()
    assert (
        isinstance(bid_denom, str) and len(bid_denom) > 0
    ), f"invalid bid_denom: {bid_denom}"
    assert not _is_liquid_denom(
        bid_denom
    ), f"bid_denom must be solid (non-liquid): {bid_denom}"

    attachments = _sum_attached_to_script_by_denom()
    # Determine exactly one base (non-liquid) sell denom from attachments
    sell_denoms: List[str] = []
    for d in attachments.keys():
        if not _is_liquid_denom(d):
            sell_denoms.append(d)
    assert len(sell_denoms) == 1, "attach exactly one  denom to escrow"
    sell_denom = sell_denoms[0]
    amount = attachments.get(sell_denom, Decimal(0))
    assert amount > 0, f"attach {sell_denom} to escrow"
    assert sell_denom != bid_denom, "sell_denom and bid_denom must differ"

    # Prepare class and NFT ids
    class_id = _auction_class_id(sell_denom, bid_denom)
    if not _class_exists(class_id):
        _set_class_with_policy(class_id, bid_denom)

    auction_id = _get_next_auction_id()
    nft_id = f"{auction_id:010d}"

    # Mint and transfer NFT to seller
    _mint_nft(class_id, nft_id, seller)

    # Record auction metadata on NFT
    block = get_block_info()
    meta = {
        "auction_id": auction_id,
        "sell_denom": sell_denom,
        "bid_denom": bid_denom,
        "amount": str(amount),
        "seller": seller,
        "created_height": block.get("height"),
        "created_time": block.get("time"),
    }
    _set_nft_metadata(class_id, nft_id, meta)

    # Start valuation at 0; owner can adjust later if desired

    # Persist indices
    _storage_set(
        _auction_id_index(auction_id),
        {
            "class_id": class_id,
            "nft_id": nft_id,
            "sell_denom": sell_denom,
            "bid_denom": bid_denom,
            "amount": str(amount),
            "seller": seller,
        },
    )
    _storage_set(
        _auction_sb_index(sell_denom, bid_denom), _auction_class(class_id, nft_id)
    )

    emit_event("auction_created", str(auction_id))
    emit_event("auction_sell", sell_denom)
    emit_event("auction_bid", bid_denom)
    emit_event("auction_amount", str(amount))

    return {
        "auction_id": auction_id,
        "class_id": class_id,
        "nft_id": nft_id,
        "amount": amount,
    }


def redeem_auction(auction_id: int) -> Dict[str, Any]:
    caller = get_executor_address()
    idx = _auction_id_index(auction_id)
    rec = _storage_get(idx)
    class_id = rec["class_id"]
    nft_id = rec["nft_id"]
    sell_denom = rec["sell_denom"]
    amount = Decimal(rec["amount"])  # type: ignore[arg-type]

    # Owner must hold the NFT
    owner = _query_nft_owner(class_id, nft_id)
    assert owner == caller, "only NFT owner can redeem"

    # Only allowed if there is no current bidder
    current_bidder = _query_nft_data_current_bidder(class_id, nft_id)
    assert current_bidder in (None, ""), "cannot redeem while a bid is active"

    # Ensure escrowed funds exist
    script_bal = _get_balance(get_script_address(), sell_denom)
    assert script_bal >= amount, f"insufficient escrow: {script_bal} < {amount}"

    # Payout and close
    _send_coins(get_script_address(), caller, [{"denom": sell_denom, "amount": amount}])

    _msg(
        {
            "@type": "/dysonprotocol.nameservice.v1.MsgBurnNFT",
            "name_destination": get_script_address(),
            "class_id": class_id,
            "nft_id": nft_id,
        }
    )

    # Cleanup indices
    _storage_delete([idx])

    emit_event("auction_redeemed", str(auction_id))
    emit_event("redeem_amount", str(amount))
    emit_event("redeem_denom", sell_denom)
    return {"denom": sell_denom, "amount": amount}
