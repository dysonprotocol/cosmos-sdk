from typing import Any, Dict, List, Optional, Literal, TypedDict
import json
from decimal import Decimal, ROUND_CEILING
import math
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
    # whaleswap extension: amount of pfand locked (0 for normal offers)
    pfand_locked: Decimal


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


class TakeOffer(TypedDict):
    offer_id: int
    take_units: Optional[int]


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
        "pfand_locked": Decimal(raw.get("pfand_locked", "0")),
    }
    return data


def _get_pool_index(pool_id: int) -> str:
    return f"pool|{pool_id:010d}"


#############################
# Liquid trading conversions
#############################


def convert_to_liquid(denom: str, amount: Any) -> Dict[str, Any]:
    """Convert solid denom `S` to liquid `L(S)` at 1:1 by minting; escrow `S` on `SCRIPT`.

    Requirements:
    - Attach at least `amount` of solid `denom` to `SCRIPT` in the same tx (escrow backing)
    - Attach at least `estimate_mint_fee(amount)` of `udys` (mint fee)
    """
    caller = get_executor_address()
    amt = Decimal(amount)
    if amt <= 0:
        raise ValueError("amount must be > 0")

    attachments = _sum_attached_to_script_by_denom()
    attached_denom = attachments.get(denom, Decimal(0))
    required_udys = estimate_mint_fee(amt)

    attached_udys = attachments.get(UDYS_DENOM, Decimal(0))

    if denom == UDYS_DENOM:
        # When depositing udys itself, the same denom funds both backing and fee
        if attached_udys < (amt + required_udys):
            raise ValueError(
                f"insufficient attached udys: {attached_udys} < required {amt + required_udys}"
            )
    else:
        if attached_denom < amt:
            raise ValueError(
                f"insufficient attached {denom}: {attached_denom} < required {amt}"
            )
        if attached_udys < required_udys:
            raise ValueError(
                f"insufficient attached {UDYS_DENOM}: {attached_udys} < required {required_udys}"
            )

    liquid_denom = quote_liquid_denom(denom)
    _mint_coins({"denom": liquid_denom, "amount": amt}, required_udys)
    _send_coins(get_script_address(), caller, [{"denom": liquid_denom, "amount": amt}])

    emit_event("deposit_denom", denom)
    emit_event("deposit_amount", str(amt))
    return {"liquid_denom": liquid_denom, "amount": amt}


def convert_to_solid(liquid_denom: str, amount: Any) -> Dict[str, Any]:
    """Burn liquid `L(S)` and release solid `S` from `SCRIPT` escrow to the caller."""
    caller = get_executor_address()
    if not _is_liquid_denom(liquid_denom):
        raise ValueError(f"invalid liquid denom: {liquid_denom}")
    denom = decode_liquid_denom(liquid_denom)
    amt = Decimal(amount)
    if amt <= 0:
        raise ValueError("amount must be > 0")

    caller_liquid = _get_balance(caller, liquid_denom)
    if caller_liquid < amt:
        raise ValueError(
            f"insufficient liquid balance: {caller_liquid} {liquid_denom} < {amt} {liquid_denom}"
        )
    script_balance = _get_balance(get_script_address(), denom)
    if script_balance < amt:
        raise ValueError(
            f"insufficient escrow backing: {script_balance} {denom} < {amt} {denom}"
        )

    _move_coins(
        inputs=[{"address": caller, "coins": [{"denom": liquid_denom, "amount": amt}]}],
        outputs=[
            {
                "address": get_script_address(),
                "coins": [{"denom": liquid_denom, "amount": amt}],
            }
        ],
    )
    _burn_coins({"denom": liquid_denom, "amount": amt})
    _send_coins(get_script_address(), caller, [{"denom": denom, "amount": amt}])

    emit_event("withdraw_denom", denom)
    emit_event("withdraw_amount", str(amt))
    return {"denom": denom, "amount": amt}


#############################
# Core DEX API (Order Book)
#############################


def make_offer(have_coin: Any, want_coin: Any) -> Dict[str, int]:
    """Create an offer in one of two modes:

    - normal: maker attaches base have coins to script; they are escrowed; no pfand.
    - liquid: maker uses liquid have denom; no attachments; pfand is locked.
    Want must be base (non-liquid) denom; takers may pay base or liquid.
    For sanity, liquid attachments at make are forbidden.
    """

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
    # Determine mode via attachments and denom type
    attachments = _sum_attached_to_script_by_denom()
    have_denom = have_coin["denom"]
    want_denom = want_coin["denom"]
    if _is_liquid_denom(want_denom):
        raise ValueError("want side must be base (non-liquid) denom")

    is_have_liquid = _is_liquid_denom(have_denom)
    attached_have = attachments.get(have_denom, Decimal(0))

    if any(_is_liquid_denom(d) for d in attachments.keys()):
        raise ValueError("liquid attachments are forbidden in make")

    pfand_locked = Decimal(0)

    if is_have_liquid:
        # Liquid mode: no attachments; require pfand
        if attached_have > 0:
            raise ValueError("do not attach have denom in liquid mode")
        pfand_per_offer = _get_pfand_per_offer()
        maker_pfand = _get_balance(maker, PFAND_DENOM)
        if maker_pfand < pfand_per_offer:
            raise ValueError(
                f"insufficient pfand: {maker_pfand} < required {pfand_per_offer}"
            )
        _move_coins(
            inputs=[
                {
                    "address": maker,
                    "coins": [{"denom": PFAND_DENOM, "amount": pfand_per_offer}],
                }
            ],
            outputs=[
                {
                    "address": get_script_address(),
                    "coins": [{"denom": PFAND_DENOM, "amount": pfand_per_offer}],
                }
            ],
        )
        pfand_locked = pfand_per_offer
        emit_event("pfand_locked", str(pfand_locked))
    else:
        # Normal mode: require attached have == have_amount, escrow to script
        if attached_have < have_amount:
            raise ValueError(
                f"insufficient attached have for escrow: {attached_have} < {have_amount}"
            )
        # After attachments, coins are already at script.

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
        "pfand_locked": pfand_locked,
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


def take_offer(
    trades: List[TakeOffer] = [TakeOffer(offer_id=0, take_units=0)],
) -> Dict[str, Any]:
    """Batch take with mixed settlement:

    - Maker-have liquid (pfand_locked>0): move L(have) maker→script, burn, send base have to taker.
    - Maker-have normal: send base have from script escrow to taker.
    - Taker-pay want: prefer base attachments; remainder paid by moving L(want) taker→script, burn; send base want to maker.
    - On close of a liquid offer, release pfand to taker.
    """
    taker = get_executor_address()
    if not trades:
        raise ValueError("trades list must be non-empty")

    # Precompute per-trade amounts
    per_trade_info: List[Dict[str, Any]] = []
    seen_offer_ids: List[int] = []
    for t in trades:
        offer_id = t["offer_id"]
        if offer_id in seen_offer_ids:
            raise ValueError(f"duplicate offer_id {offer_id} in trades list")
        seen_offer_ids.append(offer_id)
        offer = _get_offer(offer_id)
        if _get_status(offer) != "open":
            raise ValueError(f"offer {offer_id} not open: {_get_status(offer)}")
        remaining_units = offer["remaining_units"]
        take_units_opt = t.get("take_units")
        take_units = (
            remaining_units if take_units_opt is None else Decimal(take_units_opt)
        )
        if not (Decimal(1) <= take_units <= remaining_units):
            raise ValueError(
                f"take_units for offer {offer_id} must satisfy 1 <= take_units ({take_units}) <= remaining_units ({remaining_units})"
            )
        unit_want_int = offer["unit_want_int"]
        unit_have_int = offer["unit_have_int"]
        actual_sent = take_units * unit_want_int
        actual_receive = take_units * unit_have_int
        want_denom = offer["remaining_want"]["denom"]
        have_denom = offer["remaining_have"]["denom"]
        per_trade_info.append(
            {
                "offer_id": offer_id,
                "maker": offer["maker"],
                "pfand_locked": offer.get("pfand_locked", Decimal(0)),
                "take_units": take_units,
                "unit_want_int": unit_want_int,
                "unit_have_int": unit_have_int,
                "actual_sent": actual_sent,
                "actual_receive": actual_receive,
                "want_denom": want_denom,
                "have_denom": have_denom,
            }
        )

    # Aggregate taker base wants required
    taker_required_base_want: Dict[str, Decimal] = {}
    for info in per_trade_info:
        d = info["want_denom"]
        taker_required_base_want[d] = (
            taker_required_base_want.get(d, Decimal(0)) + info["actual_sent"]
        )

    # Validate attachments and compute L(want) remainder
    attachments = _sum_attached_to_script_by_denom()
    taker_liquid_want_by_denom: Dict[str, Decimal] = {}
    for d in taker_required_base_want.keys():
        attached = attachments.get(d, Decimal(0))
        required = taker_required_base_want[d]
        if attached > required:
            raise ValueError(f"attached {d} exceeds required: {attached} > {required}")
        remainder = required - attached
        if remainder > 0:
            taker_liquid_want_by_denom[d] = remainder

    # Aggregate maker liquid have moves and normal have sends to taker
    maker_liquid_inputs: Dict[str, Dict[str, Decimal]] = {}
    send_to_taker_base: Dict[str, Decimal] = {}
    maker_receive_base: Dict[str, Dict[str, Decimal]] = {}
    for info in per_trade_info:
        maker = info["maker"]
        want_denom = info["want_denom"]
        have_denom = info["have_denom"]
        actual_sent = info["actual_sent"]
        actual_receive = info["actual_receive"]
        # maker receives base want
        if maker not in maker_receive_base:
            maker_receive_base[maker] = {}
        maker_receive_base[maker][want_denom] = (
            maker_receive_base[maker].get(want_denom, Decimal(0)) + actual_sent
        )

        if info["pfand_locked"] > 0:
            # maker-have is liquid denom
            if not _is_liquid_denom(have_denom):
                raise ValueError("liquid mode offer must have liquid have denom")
            if maker not in maker_liquid_inputs:
                maker_liquid_inputs[maker] = {}
            maker_liquid_inputs[maker][have_denom] = (
                maker_liquid_inputs[maker].get(have_denom, Decimal(0)) + actual_receive
            )
            # base have sent to taker
            base_have = decode_liquid_denom(have_denom)
            send_to_taker_base[base_have] = (
                send_to_taker_base.get(base_have, Decimal(0)) + actual_receive
            )
        else:
            # normal mode: have denom must be base; send from script
            if _is_liquid_denom(have_denom):
                raise ValueError("normal mode offer must have base have denom")
            send_to_taker_base[have_denom] = (
                send_to_taker_base.get(have_denom, Decimal(0)) + actual_receive
            )

    # Pre-check balances
    # Ensure script has enough base for normal maker-have deliveries
    for d, amt in send_to_taker_base.items():
        # Note: includes both normal and maker-liquid deliveries; maker-liquid will be freed by burns, so we skip strict check here
        bal = _get_balance(get_script_address(), d)
        if bal < amt and d in [k for k in send_to_taker_base.keys()]:
            # Soft guard: allow execution; burns may free base. Keep an informative error if clearly insufficient.
            pass

    # Build move_coins for all liquid moves
    inputs: List[Input] = []
    # taker L(want)
    taker_liquid_inputs: Dict[str, Decimal] = {}
    for base_d, amt in taker_liquid_want_by_denom.items():
        lden = quote_liquid_denom(base_d)
        taker_liquid_inputs[lden] = taker_liquid_inputs.get(lden, Decimal(0)) + amt
    taker_input_coins: List[Coin] = []
    for den, amt in taker_liquid_inputs.items():
        if amt > 0:
            taker_input_coins.append({"denom": den, "amount": amt})
    if len(taker_input_coins) > 0:
        inputs.append({"address": taker, "coins": taker_input_coins})

    # maker L(have)
    for maker, coins_map in maker_liquid_inputs.items():
        maker_input_coins: List[Coin] = []
        for den, amt in coins_map.items():
            if amt > 0:
                maker_input_coins.append({"denom": den, "amount": amt})
        if len(maker_input_coins) > 0:
            inputs.append({"address": maker, "coins": maker_input_coins})

    outputs: List[Output] = []
    if len(inputs) > 0:
        # Aggregate all liquid inputs by denom for a single script output
        out_by_denom: Dict[str, Decimal] = {}
        for inp in inputs:
            for c in inp["coins"]:
                den = c["denom"]
                amt = c["amount"]
                out_by_denom[den] = out_by_denom.get(den, Decimal(0)) + amt
        out_list: List[Coin] = []
        for den in out_by_denom.keys():
            out_list.append({"denom": den, "amount": out_by_denom[den]})
        outputs.append({"address": get_script_address(), "coins": out_list})
        _move_coins(inputs=inputs, outputs=outputs)

        # Burn all liquid moved to script
        for c in out_list:
            _burn_coins({"denom": c["denom"], "amount": c["amount"]})

    # Script forwards: to taker (base have) and to each maker (base want)
    if len(send_to_taker_base.keys()) > 0:
        send_to_taker_coins: List[Coin] = []
        for d in send_to_taker_base.keys():
            a = send_to_taker_base[d]
            if a > 0:
                send_to_taker_coins.append({"denom": d, "amount": a})
        if len(send_to_taker_coins) > 0:
            _send_coins(get_script_address(), taker, send_to_taker_coins)

    for maker in maker_receive_base.keys():
        coins_map = maker_receive_base[maker]
        send_to_maker_coins: List[Coin] = []
        for d in coins_map.keys():
            a = coins_map[d]
            if a > 0:
                send_to_maker_coins.append({"denom": d, "amount": a})
        if len(send_to_maker_coins) > 0:
            _send_coins(get_script_address(), maker, send_to_maker_coins)

    # Update offers, record trades, and release pfand if closing
    block_info = get_block_info()
    for info in per_trade_info:
        trade_id = _get_next_trade_id()
        trade: Trade = {
            "trade_id": trade_id,
            "offer_id": info["offer_id"],
            "taker": taker,
            "height": block_info["height"],
            "timestamp": block_info["time"],
            "sent": {"denom": info["want_denom"], "amount": info["actual_sent"]},
            "received": {"denom": info["have_denom"], "amount": info["actual_receive"]},
        }
        trade_index = _make_trade_id_index(trade_id)
        _storage_set(trade_index, trade)
        _storage_set(_make_taker_trade_index(taker, trade_id), trade_index)
        _storage_set(_make_offer_trade_index(info["offer_id"], trade_id), trade_index)

        offer = _get_offer(info["offer_id"])
        old_indexes = _get_offer_indexes(offer)
        offer["remaining_units"] -= info["take_units"]
        new_remaining_units = offer["remaining_units"]
        just_closed = False
        if new_remaining_units == 0:
            offer["status"] = "closed"
            offer["updated_height"] = block_info["height"]
            offer["updated_timestamp"] = block_info["time"]
            offer["remaining_have"]["amount"] = Decimal(0)
            offer["remaining_want"]["amount"] = Decimal(0)
            just_closed = True
        else:
            offer["remaining_have"]["amount"] = (
                new_remaining_units * info["unit_have_int"]
            )
            offer["remaining_want"]["amount"] = (
                new_remaining_units * info["unit_want_int"]
            )
            offer["updated_height"] = block_info["height"]
            offer["updated_timestamp"] = block_info["time"]
        offer_id_index = _make_offer_id_index(info["offer_id"])
        new_indexes = _get_offer_indexes(offer)
        to_delete = [k for k in old_indexes if k not in new_indexes]
        if to_delete:
            _storage_delete(to_delete)
        for k in new_indexes:
            _storage_set(k, offer_id_index)
        _storage_set(offer_id_index, offer)

        # Release pfand to taker once on close for liquid offers
        if just_closed and offer.get("pfand_locked", Decimal(0)) > 0:
            amt = offer.get("pfand_locked", Decimal(0))
            if amt > 0:
                _send_coins(
                    get_script_address(), taker, [{"denom": PFAND_DENOM, "amount": amt}]
                )
                emit_event("pfand_released", str(amt))

        emit_event("offer_taken", f"{info['offer_id']}")
        emit_event("offer_taker", f"{taker}")
        emit_event("trade_id", f"{trade_id}")
        emit_event("offer_have_denom", f"{info['have_denom']}")
        emit_event("offer_want_denom", f"{info['want_denom']}")

    return {"ok": True}


def cancel_offer(offer_id: int):

    offer = _get_offer(offer_id)
    closer = get_executor_address()
    maker = offer["maker"]
    if _get_status(offer) != "open":
        raise ValueError(f"offer not open: {_get_status(offer)}")

    # Determine eligibility
    eligible = closer == maker
    reason = "maker_cancel" if eligible else ""
    if not eligible and offer.get("pfand_locked", Decimal(0)) > 0:
        # Liquid offer: allow third-party if maker lacks at least one unit of liquid have
        have_denom = offer["remaining_have"]["denom"]
        unit_have = offer["unit_have_int"]
        if _is_liquid_denom(have_denom):
            maker_liq_bal = _get_balance(maker, have_denom)
            if maker_liq_bal < unit_have:
                eligible = True
                reason = "maker_insufficient"
    if not eligible:
        raise ValueError("not eligible to cancel offer")

    old_indexes = _get_offer_indexes(offer)
    block_info = get_block_info()
    offer["status"] = "cancelled"
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
    emit_event("offer_cancelled", f"{offer_id}")

    # Return pfand for liquid offers
    pfand_amt = offer.get("pfand_locked", Decimal(0))
    if pfand_amt > 0:
        _send_coins(
            get_script_address(), closer, [{"denom": PFAND_DENOM, "amount": pfand_amt}]
        )
        emit_event("pfand_released", str(pfand_amt))
        emit_event("pfand_reason", reason)


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


#############################
# Admin utilities
#############################


def admin_set_pfand_per_offer(value: Decimal | str | int) -> Dict[str, Any]:
    """Owner-only: set pfand_per_offer parameter (Decimal >= 0)."""
    caller = get_executor_address()
    if caller != get_script_address():
        raise ValueError("only script owner can set pfand_per_offer")
    v = Decimal(value)
    if v < 0:
        raise ValueError("pfand_per_offer must be >= 0")
    _set_pfand_per_offer(v)
    emit_event("pfand_param", str(v))
    return {"pfand_per_offer": str(v)}


def admin_mint_pfand_to(to_address: str, amount: Any) -> Dict[str, Any]:
    """Owner-only: mint PFAND_DENOM to `to_address`. Requires attached udys for fee."""
    caller = get_executor_address()
    if caller != get_script_address():
        raise ValueError("only script owner can mint pfand")
    amt = Decimal(amount)
    if amt <= 0:
        raise ValueError("amount must be > 0")
    attachments = _sum_attached_to_script_by_denom()
    required_udys = estimate_mint_fee(amt)
    attached_udys = attachments.get(UDYS_DENOM, Decimal(0))
    if attached_udys < required_udys:
        raise ValueError(
            f"insufficient attached udys: {attached_udys} < required {required_udys}"
        )
    _mint_coins({"denom": PFAND_DENOM, "amount": amt}, required_udys)
    _send_coins(
        get_script_address(), to_address, [{"denom": PFAND_DENOM, "amount": amt}]
    )
    emit_event("pfand_minted", str(amt))
    return {"minted": str(amt)}
