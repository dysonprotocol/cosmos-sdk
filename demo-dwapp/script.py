"""
This is a demo script for the Dyson Protocol.
"""

import re2 as re

import ast
import json
import html
import mimetypes
from string import Template
from dys import (  # type: ignore
    _query,
    _msg,
    get_script_address,
    get_executor_address,
    get_attached_messages,
)
from typing import Dict, Any, Optional, List


def _get_next_id(key):
    """Get the next available message ID, left-padded to 6 digits"""
    # Query the current message counter
    try:
        result = _query(
            {
                "@type": "/dysonprotocol.storage.v1.QueryStorageGetRequest",
                "owner": get_script_address(),
                "index": f"ids/{key}",
            }
        )
        # Get current counter value, default to 0 if not found
        current_id = int(result["entry"]["data"])
    except Exception:
        # Storage entry doesn't exist yet (first message), start from 0
        current_id = 0

    # Increment to get next ID
    next_id = current_id + 1

    # Store the updated counter back
    _msg(
        {
            "@type": "/dysonprotocol.storage.v1.MsgStorageSet",
            "owner": get_script_address(),
            "index": f"ids/{key}",
            "data": str(next_id),
        }
    )

    # Return next ID, left-padded to 6 digits
    return f"{next_id:06d}"


def save_message(message="Hello, world!"):
    """
    Save a message to the storage.
    Args:
        message: the message text

    The message is saved with the following data:
    - greeting: the message text
    - sender: the address of the sender
    - message_id: the ID of the message
    - coins: the coins sent to the script

    Build the attached bank MsgSend to the script with the following format:
     [{
        "@type": "/cosmos.bank.v1beta1.MsgSend",
        "from_address": "MY_ADDRESS",
        "to_address": "SCRIPT_ADDRESS",
        "amount": [{"denom": "udys", "amount": "COINS_AMOUNT"}]
    }]
    """
    caller = get_executor_address()
    script_address = get_script_address()
    message_id = _get_next_id(key="messages")

    # Check for attached bank send messages to this script
    coins = {}
    for msg in get_attached_messages():
        if (
            msg["@type"] == "/cosmos.bank.v1beta1.MsgSend"
            and msg["to_address"] == script_address
        ):
            for coin in msg["amount"]:
                denom = coin["denom"]
                coins[denom] = coins.get(denom, 0) + int(coin["amount"])

    index = f"messages/{coins.get('udys, 0):010d}/{message_id}"

    message_data = {
        "greeting": message,
        "sender": caller,
        "message_id": message_id,
        "coins": coins,
    }

    _msg(
        {
            "@type": "/dysonprotocol.storage.v1.MsgStorageSet",
            "owner": script_address,
            "index": index,
            "data": json.dumps(message_data),
        }
    )

    return index


def delete_message(message_id):
    """Delete a message if the executor is the author"""
    caller = get_executor_address()
    index = f"messages/{message_id}"

    # First, get the message to check ownership
    result = _query(
        {
            "@type": "/dysonprotocol.storage.v1.QueryStorageGetRequest",
            "owner": get_script_address(),
            "index": index,
        }
    )

    # Check if message exists
    if not result.get("entry"):
        return {"error": "Message not found", "message_id": message_id}

    # Parse message data to get the sender
    try:
        message_data = json.loads(result["entry"]["data"])
        message_sender = message_data.get("sender")
    except (json.JSONDecodeError, KeyError):
        return {"error": "Invalid message data", "message_id": message_id}

    # Authenticate: only the sender can delete their message
    if message_sender != caller:
        return {
            "error": "Unauthorized: You can only delete your own messages",
            "message_id": message_id,
            "sender": message_sender,
            "caller": caller,
        }

    # Delete the message
    _msg(
        {
            "@type": "/dysonprotocol.storage.v1.MsgStorageDelete",
            "owner": get_script_address(),
            "indexes": [index],
        }
    )

    return {
        "success": True,
        "message": "Message deleted successfully",
        "message_id": message_id,
        "deleted_index": index,
    }


def list_messages(limit=10, key="", reverse=True):
    pagination = {"limit": str(limit), "reverse": reverse}
    if key:
        pagination["key"] = key

    return _query(
        {
            "@type": "/dysonprotocol.storage.v1.QueryStorageListRequest",
            "owner": get_script_address(),
            "index_prefix": "messages/",
            "pagination": pagination,
        }
    )


class SafeString(str):
    pass


class SafeTemplate(Template):
    delimiter = "{{"
    pattern = r"\{\{\s*(?P<named>[a-zA-Z_][a-zA-Z_0-9-_]*)\s*\}\}"  # type: ignore

    def escape_substitute(self, mapping):
        safe_map = {}
        for k, v in mapping.items():
            safe_map[k] = v if isinstance(v, SafeString) else SafeString(html.escape(v))
        return SafeTemplate.substitute(self, safe_map)


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


routes = []


def route(pattern):
    def decorator(f):
        routes.append((pattern, f))
        return f

    return decorator


@route(r"^/static/(?P<file_path>.*)$")
def handle_static(environ, start_response, file_path=None):
    q = {
        "@type": "/dysonprotocol.storage.v1.QueryStorageGetRequest",
        "owner": get_script_address(),
        "index": f"static/{file_path}",
    }
    r = _query(q)

    # Explicitly handle JavaScript files
    ctype, encoding = mimetypes.guess_type(file_path or "")
    if not ctype:
        ctype = "application/octet-stream"
    if encoding:
        ctype += f"; charset={encoding}"

    start_response("200 OK", [("Content-Type", ctype)])
    return [r["entry"]["data"].encode()]


@route(r"^/wallet$")
def handle_wallet(environ, start_response):
    start_response("200 OK", [("Content-Type", "text/html; charset=utf-8")])

    data = {}
    messages_template = SafeTemplate(fetch_template("wallet.html"))
    main = messages_template.substitute(data)

    if environ.get("HTTP_HX_REQUEST") == "true":
        return [main.encode()]

    return [_render_base(main)]


@route(r"^/script$")
def handle_script(environ, start_response):
    """Handle the script management page"""
    start_response("200 OK", [("Content-Type", "text/html; charset=utf-8")])

    # Get current script info
    script_address = get_script_address()

    # Prepare script data as JSON
    script_data = {
        "script_address": script_address,
    }

    data = {"script_data_json": json.dumps(script_data)}

    script_template = SafeTemplate(fetch_template("script.html"))
    main = script_template.substitute(data)

    if environ.get("HTTP_HX_REQUEST") == "true":
        return [main.encode()]

    return [_render_base(main)]


@route(r"^/script/functions$")
def handle_script_functions(environ, start_response):
    """Handle the script functions API endpoint"""
    start_response("200 OK", [("Content-Type", "application/json; charset=utf-8")])

    # Get current script info
    script_address = get_script_address()

    try:
        # Query current script info to get the code
        result = _query(
            {
                "@type": "/dysonprotocol.script.v1.QueryScriptInfoRequest",
                "address": script_address,
            }
        )
        script_info = result.get("script", {})
        current_code = script_info.get("code", "")

        if not current_code:
            return [json.dumps({"error": "No script code found"}).encode()]

        # Extract functions from the current script code
        functions_data = extract_functions(current_code)

        return [json.dumps(functions_data, indent=2).encode()]

    except Exception as e:
        error_response = {"error": f"Failed to extract functions: {str(e)}"}
        return [json.dumps(error_response).encode()]


@route(r"^/storage$")
def handle_storage(environ, start_response):
    """Handle the storage management page"""
    start_response("200 OK", [("Content-Type", "text/html; charset=utf-8")])

    data = {}
    storage_template = SafeTemplate(fetch_template("storage.html"))
    main = storage_template.substitute(data)

    if environ.get("HTTP_HX_REQUEST") == "true":
        return [main.encode()]

    return [_render_base(main)]


@route(r"^/tasks$")
def handle_tasks(environ, start_response):
    """Handle the tasks management page"""
    start_response("200 OK", [("Content-Type", "text/html; charset=utf-8")])

    data = {}
    tasks_template = SafeTemplate(fetch_template("tasks.html"))
    main = tasks_template.substitute(data)

    if environ.get("HTTP_HX_REQUEST") == "true":
        return [main.encode()]

    return [_render_base(main)]


@route(r"^/$")
def handle_messages(environ, start_response):
    start_response("200 OK", [("Content-Type", "text/html; charset=utf-8")])

    # Embed the current script address into the messages page so that
    # frontend code can read it without relying on URL parsing.
    script_address = get_script_address()

    data = {
        "messages_config_json": SafeString(
            json.dumps({"scriptAddress": script_address})
        )
    }

    messages_template = SafeTemplate(fetch_template("messages.html"))
    main = messages_template.substitute(data)

    if environ.get("HTTP_HX_REQUEST") == "true":
        return [main.encode()]

    return [_render_base(main)]


def extract_functions(
    code: str = "def hello(name: str, age: int = 20): pass",
) -> Dict[str, Dict[str, Any]]:
    """
    Extract top-level functions with very low per-call overhead:
      - 'args': List[{'name', 'type', 'default'}]
      - 'doc' : Optional[str]
    """
    try:
        tree = ast.parse(code)
        del code

        unp = ast.unparse  # local ref

        def literal_unparse(node):
            """Unparse and literal eval"""
            return ast.literal_eval(ast.unparse(node)) if node else None

        getdoc = ast.get_docstring  # local ref

        result: Dict[str, Dict[str, Any]] = {}
        for node in tree.body:
            if not isinstance(node, ast.FunctionDef) or node.name.startswith("_"):
                continue

            args = node.args
            regular = args.args
            kwonly = args.kwonlyargs
            defaults = args.defaults
            kwdefaults = args.kw_defaults

            n_reg = len(regular)
            n_def = len(defaults)
            split = n_reg - n_def  # index before defaults start

            info: List[Dict[str, Optional[str]]] = []

            # regular args
            for i, a in enumerate(regular):
                default_node = defaults[i - split] if i >= split else None
                info.append(
                    {
                        "name": a.arg,
                        "type": unp(a.annotation) if a.annotation else None,
                        "default": (
                            literal_unparse(default_node) if default_node else None
                        ),
                    }
                )

            # *args
            va = args.vararg
            if va:
                info.append(
                    {
                        "name": f"*{va.arg}",
                        "type": unp(va.annotation) if va.annotation else None,
                        "default": None,
                    }
                )

            # kw-only
            for a, d in zip(kwonly, kwdefaults):
                info.append(
                    {
                        "name": a.arg,
                        "type": unp(a.annotation) if a.annotation else None,
                        "default": literal_unparse(d) if d else None,
                    }
                )

            # **kwargs
            kwa = args.kwarg
            if kwa:
                info.append(
                    {
                        "name": f"**{kwa.arg}",
                        "type": unp(kwa.annotation) if kwa.annotation else None,
                        "default": None,
                    }
                )

            result[node.name] = {"args": info, "doc": getdoc(node), "pretty": unp(args)}

        return result

    except Exception as e:
        return {"error": {"message": f"Failed to parse code: {e}", "args": [], "doc": None, "pretty": ""}}


@route(r"^/demo$")
def handle_demo(environ, start_response):
    start_response("200 OK", [("Content-Type", "text/html; charset=utf-8")])
    data = {}
    messages_template = SafeTemplate(fetch_template("demo.html"))
    main = messages_template.substitute(data)
    return [main.encode()]


@route(r"^/coins$")
def handle_coins(environ, start_response):
    """Handle the coins management page"""
    start_response("200 OK", [("Content-Type", "text/html; charset=utf-8")])

    data = {}
    coins_template = SafeTemplate(fetch_template("coins.html"))
    main = coins_template.substitute(data)

    if environ.get("HTTP_HX_REQUEST") == "true":
        return [main.encode()]

    return [_render_base(main)]


@route(r"^/names$")
def handle_names(environ, start_response):
    """Handle the nameservice management page"""
    start_response("200 OK", [("Content-Type", "text/html; charset=utf-8")])
    data = {}
    names_template = SafeTemplate(fetch_template("names.html"))
    main = names_template.substitute(data)
    if environ.get("HTTP_HX_REQUEST") == "true":
        return [main.encode()]
    return [_render_base(main)]


@route(r"^/nftclasses$")
def handle_nftclasses(environ, start_response):
    """Handle the NFT classes list page"""
    start_response("200 OK", [("Content-Type", "text/html; charset=utf-8")])

    data = {}
    template = SafeTemplate(fetch_template("nftclasses.html"))
    main = template.substitute(data)

    if environ.get("HTTP_HX_REQUEST") == "true":
        return [main.encode()]

    return [_render_base(main)]


@route(r"^/nfts/class/(?P<class_id>[^/]+)$")
def handle_nfts_by_class(environ, start_response, class_id=None):
    """Handle NFTs by class page"""
    start_response("200 OK", [("Content-Type", "text/html; charset=utf-8")])

    # Pass class_id to the template so the JS store can fetch data
    data = {
        "class_id": class_id or "",
        "owner_address": "",
    }
    template = SafeTemplate(fetch_template("nfts.html"))
    main = template.substitute(data)

    if environ.get("HTTP_HX_REQUEST") == "true":
        return [main.encode()]

    return [_render_base(main)]


@route(r"^/nfts/owner/(?P<address>[^/]+)$")
def handle_nfts_by_owner(environ, start_response, address=None):
    """Handle NFTs by owner page"""
    start_response("200 OK", [("Content-Type", "text/html; charset=utf-8")])

    data = {
        "owner_address": address or "",
        "class_id": "",
    }
    template = SafeTemplate(fetch_template("nfts.html"))
    main = template.substitute(data)

    if environ.get("HTTP_HX_REQUEST") == "true":
        return [main.encode()]

    return [_render_base(main)]


def wsgi(environ, start_response):
    path_info = environ["PATH_INFO"]
    for pattern, func in routes:
        m = re.match(pattern, path_info)
        if m:
            return func(environ, start_response, **m.groupdict())
    start_response("404 Not Found", [("Content-Type", "text/plain; charset=utf-8")])
    return [b"404 Not Found"]


####
# Tests for coverage report
####


def memoize(func):
    """
    Decorator that caches function results to avoid redundant computations
    Used here to demo the improved performance in the coverage report.
    """
    cache = {}

    def wrapper(*args, **kwargs):
        # Create a cache key from arguments
        key = (args, tuple(sorted(kwargs.items())))

        if key not in cache:
            cache[key] = func(*args, **kwargs)
        return cache[key]

    return wrapper


def fib(n: int = 3) -> int:
    if n <= 1:
        return n
    return fib(n - 1) + fib(n - 2) + 1


def test_fib(n: int = 3):
    fib(n)


@memoize
def fib2(n: int = 3) -> int:
    if n <= 1:
        return n
    return fib2(n - 1) + fib2(n - 2) + 1


def test_fib2(n: int = 3):
    fib2(n)


# Legacy functions removed - now using render_script_tags() instead


def _render_base(main: str) -> bytes:
    """Render base.html with integrity context and supplied main HTML."""

    return (
        SafeTemplate(fetch_template("base.html"))
        .substitute(
            {
                "main": SafeString(main),
                "static_scripts": render_script_tags(),
                "importmap_json": SafeString(
                    _query(
                        {
                            "@type": "/dysonprotocol.storage.v1.QueryStorageGetRequest",
                            "owner": get_script_address(),
                            "index": "static/importmap.json",
                        }
                    )["entry"]["data"]
                ),
                "css_integrity": get_css_integrity(),
            }
        )
        .encode()
    )


def render_script_tags() -> SafeString:
    """List all scripts in static/js directory and output script tags with proper integrity hash."""
    # Query all storage entries with prefix "static/js/"
    script_address = get_script_address()
    storage_list = _query(
        {
            "@type": "/dysonprotocol.storage.v1.QueryStorageListRequest",
            "owner": script_address,
            "index_prefix": "static/js/",
            "extract": "false",  # don't extract the data, just list the entries
        }
    )

    # tags = []
    # for entry in storage_list["entries"]:
    #    index = entry["index"]
    #    hash_value = entry["hash"]
    #    tags.append()

    tags = [
        f'<script defer type="module" src="/{entry["index"]}" integrity="{entry["hash"]}"></script>'
        for entry in storage_list["entries"]
    ]
    # Join with newline and indentation for readability
    return SafeString("\n    ".join(tags))


def get_css_integrity() -> SafeString:
    """Get integrity attribute for style.css file."""
    try:
        css_res = _query(
            {
                "@type": "/dysonprotocol.storage.v1.QueryStorageGetRequest",
                "owner": get_script_address(),
                "index": "static/css/style.css",
            }
        )
        hash_value = css_res["entry"]["hash"]
        if isinstance(hash_value, str) and hash_value.startswith("sha256-"):
            return SafeString(f' integrity="{hash_value}"')
    except Exception:
        pass  # No hash available, return empty
    return SafeString("")
