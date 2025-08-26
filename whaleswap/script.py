"""
WhaleSwap.dys - Minimal AMM on Dyson Protocol

Website:  https://whaleswap.dysonprotocol.com/
Twitter:  https://twitter.com/whaleswap_dys
GitHub:   https://github.com/sybilsingleton/whaleswap.dys
"""

import json
import math
import re
import mimetypes
from decimal import Decimal

from dys import (
    get_script_address,
    get_executor_address,
    get_block_info,
    get_attached_messages,
    emit_event,
    _msg,
    _query,
)
from urllib.parse import parse_qs
from string import Template
import html

DYS_NAME = "whaleswap.dys"


def _get_pool_index(pool_id: int) -> str:
    return f"pools/{int(pool_id):015}"


def _json_dumps_decimal(value) -> str:
    def _default(o):
        if isinstance(o, Decimal):
            return str(o)
        raise TypeError(f"Object of type {type(o)} is not JSON serializable")

    return json.dumps(value, default=_default)


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


def _get_next_pool_id():
    index = f"next_pool_id"
    # Use list to avoid exceptions on not-found
    list_res = _query(
        {
            "@type": "/dysonprotocol.storage.v1.QueryStorageListRequest",
            "owner": get_script_address(),
            "index_prefix": index,
            "pagination": {"limit": 1},
        }
    )
    entries = list_res.get("entries", [])
    next_id = 1 if len(entries) == 0 else int(entries[0]["data"])
    _msg(
        {
            "@type": "/dysonprotocol.storage.v1.MsgStorageSet",
            "owner": get_script_address(),
            "index": index,
            "data": str(next_id + 1),
        }
    )
    return next_id


def get_pool(pool_id: int):
    result = _query(
        {
            "@type": "/dysonprotocol.storage.v1.QueryStorageGetRequest",
            "owner": get_script_address(),
            "index": _get_pool_index(pool_id),
        }
    )
    pool = json.loads(
        result["entry"]["data"],
        parse_float=Decimal,
        parse_int=Decimal,
    )
    return pool


def get_shares_denom(pool_id: int):
    # Denom must match ^[a-z]([-a-z0-9]*[a-z0-9])?\.dys(?:/[0-9A-Za-z:_-]+)*$
    # Use root name then a subdenom path segment
    return f"{DYS_NAME}/pool-{int(pool_id):015d}"


def create_pool():
    coins = _get_attached_coins_to_script()
    assert (
        len(coins) == 2
    ), "Both base and quote (udys) must be sent to create the pool"

    # set base and quote coins, the quote is the denominated udys
    if coins[0]["denom"] == "udys":
        base_coin = coins[1]
        quote_coin = coins[0]
    elif coins[1]["denom"] == "udys":
        base_coin = coins[0]
        quote_coin = coins[1]
    else:
        raise Exception("No udys coins sent, cannot create pool.")

    pool_id = _get_next_pool_id()
    pool_index = _get_pool_index(pool_id)

    initial_shares = Decimal("100000")
    shares_denom = get_shares_denom(pool_id)
    block_info = get_block_info()
    pool = {
        "pool_id": pool_id,
        "base": {
            "denom": base_coin["denom"],
            "balance": Decimal(base_coin["amount"]),
            "lent": 0,
            "collateral": 0,
        },
        "quote": {
            "denom": quote_coin["denom"],
            "balance": Decimal(quote_coin["amount"]),
            "lent": 0,
            "collateral": 0,
        },
        "total_shares": initial_shares,
        "shares_denom": shares_denom,
        "block_height": block_info.get("height"),
        "created": block_info.get("time"),
    }
    print("emit", emit_event(key="poolupdate", value=str(pool_id)))
    _msg(
        {
            "@type": "/dysonprotocol.storage.v1.MsgStorageSet",
            "owner": get_script_address(),
            "index": pool_index,
            "data": _json_dumps_decimal(pool),
        }
    )

    _msg(
        {
            "@type": "/dysonprotocol.nameservice.v1.MsgMintCoins",
            "name_destination": get_script_address(),
            "amount": [{"amount": str(initial_shares), "denom": shares_denom}],
        }
    )

    _msg(
        {
            "@type": "/cosmos.bank.v1beta1.MsgSend",
            "from_address": get_script_address(),
            "to_address": get_executor_address(),
            "amount": [{"amount": str(initial_shares), "denom": shares_denom}],
        }
    )

    return pool


def join_pool(pool_id: int):
    coins = _get_attached_coins_to_script()
    assert len(coins) == 2, "Both base and quote (DYS) must be sent to join the pool"

    # set base and quote coins, the quote is the denominated DYS
    if coins[0]["denom"] == "udys":
        base_coin = coins[1]
        quote_coin = coins[0]
    elif coins[1]["denom"] == "udys":
        base_coin = coins[0]
        quote_coin = coins[1]
    else:
        raise Exception("No DYS coins sent, cannot join pool.")

    pool = get_pool(pool_id)

    sent_base_amount = Decimal(base_coin["amount"])
    sent_quote_amount = Decimal(quote_coin["amount"])

    pool_base = pool["base"]
    pool_quote = pool["quote"]

    correct_base_amount = math.ceil(
        (sent_quote_amount * Decimal(pool_base["balance"])) / (pool_quote["balance"])
    )
    correct_quote_amount = math.ceil(
        (sent_base_amount * Decimal(pool_quote["balance"])) / (pool_base["balance"])
    )
    refund = []
    if sent_base_amount > correct_base_amount:
        refund_amount = sent_base_amount - correct_base_amount
        refund_denom = base_coin["denom"]
        _msg(
            {
                "@type": "/cosmos.bank.v1beta1.MsgSend",
                "from_address": get_script_address(),
                "to_address": get_executor_address(),
                "amount": [
                    {"amount": str(refund_amount), "denom": refund_denom}
                ],
            }
        )
        refund += [{"amount": refund_amount, "denom": refund_denom}]

    if sent_quote_amount > correct_quote_amount:
        refund_amount = sent_quote_amount - correct_quote_amount
        refund_denom = quote_coin["denom"]
        _msg(
            {
                "@type": "/cosmos.bank.v1beta1.MsgSend",
                "from_address": get_script_address(),
                "to_address": get_executor_address(),
                "amount": [
                    {"amount": str(refund_amount), "denom": refund_denom}
                ],
            }
        )
        refund += [{"amount": refund_amount, "denom": refund_denom}]

    # update pool balances
    pool["base"]["balance"] = Decimal(pool_base["balance"]) + sent_base_amount
    pool["quote"]["balance"] = Decimal(pool_quote["balance"]) + sent_quote_amount
    pool["updated"] = get_block_info().get("time")
    # calculate shares
    base_shares = (sent_base_amount * Decimal(pool["total_shares"])) // Decimal(
        pool_base["balance"]
    )
    quote_shares = (sent_quote_amount * Decimal(pool["total_shares"])) // Decimal(
        pool_quote["balance"]
    )

    # in case there is a rounding difference, give the smaller share amount
    shares = min(base_shares, quote_shares)

    pool_index = _get_pool_index(pool_id)
    shares_denom = get_shares_denom(pool_id)

    _msg(
        {
            "@type": "/dysonprotocol.nameservice.v1.MsgMintCoins",
            "name_destination": get_script_address(),
            "amount": [{"amount": str(shares), "denom": shares_denom}],
        }
    )
    pool["total_shares"] = Decimal(pool["total_shares"]) + shares
    _msg(
        {
            "@type": "/cosmos.bank.v1beta1.MsgSend",
            "from_address": get_script_address(),
            "to_address": get_executor_address(),
            "amount": [{"amount": str(shares), "denom": shares_denom}],
        }
    )
    print("emit", emit_event(key="poolupdate", value=str(pool_id)))
    _msg(
        {
            "@type": "/dysonprotocol.storage.v1.MsgStorageSet",
            "owner": get_script_address(),
            "index": pool_index,
            "data": _json_dumps_decimal(pool),
        }
    )

    # pool_id, shares, refunded amount and denom
    return {
        "pool_id": pool_id,
        "shares": shares,
        "share_denom": shares_denom,
        "refund": refund,
    }


def exit_pool(pool_id: int):
    coins = _get_attached_coins_to_script()
    assert len(coins) == 1, "Only the shares denom must be sent to exit the pool"

    shares_denom = coins[0]["denom"]
    sent_shares_amount = Decimal(coins[0]["amount"])

    needed_denom = get_shares_denom(pool_id)
    assert (
        shares_denom == needed_denom
    ), f"Invalid shares denom, sent [{shares_denom}] needed [{needed_denom}] "

    pool = get_pool(pool_id)

    result = _query(
        {"@type": "/cosmos.bank.v1beta1.QuerySupplyOfRequest", "denom": shares_denom}
    )
    total_shares = result["amount"]
    total_shares_amount = Decimal(total_shares["amount"])

    # assert the total shores matches the pool total shares .
    # this shouldn't happen.
    assert (
        total_shares_amount == pool["total_shares"]
    ), f"Total shares mismatch, pool {pool['total_shares']} != total {total_shares_amount}"

    base_amount = (
        sent_shares_amount * Decimal(pool["base"]["balance"])
    ) // total_shares_amount
    quote_amount = (
        sent_shares_amount * Decimal(pool["quote"]["balance"])
    ) // total_shares_amount

    _msg(
        {
            "@type": "/dysonprotocol.nameservice.v1.MsgBurnCoins",
            "name_destination": get_script_address(),
            "amount": [
                {"amount": str(sent_shares_amount), "denom": shares_denom}
            ],
        }
    )
    pool["total_shares"] = Decimal(pool["total_shares"]) - sent_shares_amount

    # update the base and denom on the pool
    pool["base"]["balance"] = Decimal(pool["base"]["balance"]) - base_amount
    pool["quote"]["balance"] = Decimal(pool["quote"]["balance"]) - quote_amount
    pool["updated"] = get_block_info().get("time")

    amount = []

    if base_amount:
        amount += [
            {"amount": str(base_amount), "denom": pool["base"]["denom"]},
        ]
    if quote_amount:
        amount += [
            {"amount": str(quote_amount), "denom": pool["quote"]["denom"]},
        ]

    if not quote_amount and not base_amount:
        raise Exception(
            f"Shares [{sent_shares_amount} {shares_denom}] value to small to exchange"
        )
    amount = sorted(
        amount,
        key=lambda x: x["denom"],
    )
    _msg(
        {
            "@type": "/cosmos.bank.v1beta1.MsgSend",
            "from_address": get_script_address(),
            "to_address": get_executor_address(),
            "amount": amount,
        }
    )
    print("emit", emit_event(key="poolupdate", value=str(pool_id)))
    _msg(
        {
            "@type": "/dysonprotocol.storage.v1.MsgStorageSet",
            "owner": get_script_address(),
            "index": _get_pool_index(pool_id),
            "data": _json_dumps_decimal(pool),
        }
    )

    return amount


def swap(pool_ids: str, minimum_swap_out_amount: int, swap_out_denom: str):
    coins = _get_attached_coins_to_script()
    assert len(coins) == 1, "One and only one coin denom must be sent for swapping"

    pool_ids = str(pool_ids)
    min_out = Decimal(minimum_swap_out_amount)
    input_amount = Decimal(coins[0]["amount"])
    input_denom = coins[0]["denom"]

    for pool_id in pool_ids.split():
        pool = get_pool(int(pool_id))

        K = Decimal(pool["base"]["balance"]) * Decimal(pool["quote"]["balance"])

        if input_denom == pool["base"]["denom"]:
            pool["base"]["balance"] = Decimal(pool["base"]["balance"]) + input_amount
            output_amount = math.floor(
                Decimal(pool["quote"]["balance"]) - (K / Decimal(pool["base"]["balance"]))
            )
            assert output_amount, "Swap size too small"
            pool["quote"]["balance"] = Decimal(pool["quote"]["balance"]) - output_amount
            assert pool["quote"]["balance"] > 0, "Swap size too large"
            output_denom = pool["quote"]["denom"]
        elif input_denom == pool["quote"]["denom"]:
            pool["quote"]["balance"] = Decimal(pool["quote"]["balance"]) + input_amount
            output_amount = math.floor(
                Decimal(pool["base"]["balance"]) - (K / Decimal(pool["quote"]["balance"]))
            )
            assert output_amount, "Swap size too small"
            pool["base"]["balance"] = Decimal(pool["base"]["balance"]) - output_amount
            assert pool["base"]["balance"] > 0, "Swap size too large"
            output_denom = pool["base"]["denom"]
        else:
            raise Exception(
                f'input denom must be one of : [{pool["base"]["denom"]}, {pool["quote"]["denom"]}]'
            )
        input_denom = output_denom
        input_amount = output_amount
        pool["updated"] = get_block_info().get("time")
        pool["num_trades"] = 1 + pool.get("num_trades", 0)

        print("emit", emit_event(key="poolupdate", value=str(pool_id)))
        _msg(
            {
                "@type": "/dysonprotocol.storage.v1.MsgStorageSet",
                "owner": get_script_address(),
                "index": _get_pool_index(int(pool_id)),
                "data": _json_dumps_decimal(pool),
            }
        )

    if output_amount < min_out:
        raise Exception(
            f"Slippage occured, minimum output amount not reached: {output_amount} {output_denom} < {min_out} {output_denom}"
        )
    if swap_out_denom != output_denom:
        raise Exception(
            f"Output denom doesn't match, wanted: {swap_out_denom} got: {output_denom}"
        )

    _msg(
        {
            "@type": "/cosmos.bank.v1beta1.MsgSend",
            "from_address": get_script_address(),
            "to_address": get_executor_address(),
            "amount": [{"amount": str(output_amount), "denom": output_denom}],
        }
    )
    return {"output_amount": output_amount, "output_denom": output_denom}


DEFAULT_VERSION = "v1.0.0"


def parse_cookies(cookie_str):
    cookies = {}
    for item in cookie_str.split("; "):
        if "=" in item:
            key, value = item.split("=", 1)
            cookies[key] = value
    return cookies




routes = []


def route(pattern):
    def decorator(f):
        routes.append((pattern, f))
        return f

    return decorator


@route(r"^/static/(?P<file_path>.+)$")
def handle_static(environ, start_response, file_path):
    """Handle static file serving"""
    try:
        q = {
            "@type": "/dysonprotocol.storage.v1.QueryStorageGetRequest",
            "owner": get_script_address(),
            "index": f"static/{file_path}",
        }
        r = _query(q)

        if not r.get("entry") or not r["entry"].get("data"):
            raise FileNotFoundError(
                f"Static file not found in storage: static/{file_path}"
            )

        data = r["entry"]["data"]

        # Determine content type
        ctype, encoding = mimetypes.guess_type(file_path or "")
        if not ctype:
            ctype = "application/octet-stream"

        # The data from storage is a string, so we encode it to bytes
        response_body = data.encode("utf-8")

        start_response(
            "200 OK",
            [("Content-Type", ctype), ("Cache-Control", "max-age=3600, public")],
        )
        return [response_body]

    except Exception as e:
        print(f"Error serving static file {file_path}: {e}")
        start_response("404 Not Found", [("Content-Type", "text/plain")])
        return [b"File Not Found"]


@route(r"^/$")
def handle_index(environ, start_response):
    html = _render_template("index.html")
    start_response("200 OK", [("Content-Type", "text/html; charset=utf-8")])
    return [html.encode()]


def wsgi(environ, start_response):
    path = environ.get("PATH_INFO", "/") or "/"
    for pattern, handler in routes:
        m = re.match(pattern, path)
        if m:
            groups = m.groupdict() or {}
            return handler(environ, start_response, **groups)
    # Fallback
    return handle_index(environ, start_response)


def _render_template(path: str, **kwargs) -> str:
    template_src = fetch_template(path)
    context = {"script_address": get_script_address()}
    if kwargs:
        context.update(kwargs)
    return SafeTemplate(template_src).substitute(context)


class SafeString(str):
    pass


class SafeTemplate(Template):
    delimiter = "{{"
    pattern = r"\{\{\s*(?P<named>[a-zA-Z_][a-zA-Z_0-9]*)\s*\}\}"  # type: ignore

    def substitute(self, mapping):
        safe_map = {}
        for k, v in mapping.items():
            safe_map[k] = v if isinstance(v, SafeString) else html.escape(str(v))
        return Template.substitute(self, safe_map)

    def safe_substitute(self, mapping):
        safe_map = {}
        for k, v in mapping.items():
            safe_map[k] = v if isinstance(v, SafeString) else html.escape(str(v))
        return Template.safe_substitute(self, safe_map)


def fetch_template(name):
    q = {
        "@type": "/dysonprotocol.storage.v1.QueryStorageGetRequest",
        "owner": get_script_address(),
        "index": f"templates/{name}",
    }
    r = _query(q)
    entry = r.get("entry")
    if not entry:
        return f"<p>Template not found: {name}</p>"
    return entry.get("data", "")


