from dys import (
    _query,
    _msg,
    get_script_address,
    get_executor_address,
    get_block_info,
    get_attached_messages,
    DysQueryException,
    get_script_version,
    get_script_name,
)
from datetime import datetime
from decimal import Decimal
import math
import json
import typing
import html
from string import Template
from urllib.parse import parse_qsl
import mimetypes
import re
import hashlib
from typing import Callable, Iterable, List, Tuple

def get_base_domain():
    """Get BASE_DOMAIN from storage settings, with fallback for development."""
    try:
        settings_response = _query({
            "@type": "/dysonprotocol.storage.v1.QueryStorageGetRequest",
            "owner": get_script_address(),
            "index": "settings",
        })
        if "entry" in settings_response and "data" in settings_response["entry"]:
            settings = json.loads(settings_response["entry"]["data"])
            return settings.get("BASE_DOMAIN", "http://localhost:1317")
    except (KeyError, json.JSONDecodeError, TypeError) as e:
        print(f"Failed to load BASE_DOMAIN from settings: {e}")
    # Fallback for development/testing
    return "http://localhost:1317"


WHITELABEL = False
name = get_script_name()
if name and name != "nuance.dys":
    WHITELABEL = True


try:
    import re2 as re  # Only re2 is available onchain
except ImportError as e:
    print(f"re2 not available, falling back to re: {e}")
    import re


# Typing to specify that TEXTAREA is a formatted string, used for content submission
TEXTAREA = typing.Annotated[str, '{"format":"textarea"}']

# Regex to idetify an embedded post as /post_id on it's own line
POST_RE = r"(?:^\n*?|\n+?)/(\d+)(#[^\s]+)?(?:\n*?$|\n+?)"

# The soonest a post rewards can be claimed again for a specific tag
CLAIM_WAIT_SEC = 60 * 60 * 24  # 24hrs


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


def render_posts(
    posts,
    pagination,
    header="",
    load_more_url_base="",
    req_pagination=None,
    container_class="",
    hx_select="main",
    hx_target="this",
    hx_swap="innerHTML",
    use_template=True,
):
    """
    Render a list of posts with pagination and htmx lazy loading.

    Args:
        posts: List of post data
        pagination: Pagination info with potential 'next_key'
        header: Optional header content
        load_more_url_base: Base URL for load more button (e.g. "/recent/")
        req_pagination: Request pagination data for URL construction
        container_class: CSS class for post containers
        hx_select: htmx hx-select attribute
        hx_target: htmx hx-target attribute
        hx_swap: htmx hx-swap attribute
        use_template: Whether to use post_list.html template or return raw HTML
    """
    if pagination.get("next_key") and load_more_url_base and req_pagination:
        # Create the 'load more' placeholder using f-string
        limit = req_pagination["limit"]
        key = pagination["next_key"]
        load_more_url = f"{load_more_url_base}?limit={limit}&key={key}"
        load_more_html = f"""
<div
  hx-get="{load_more_url}"
  hx-trigger="revealed once"
  hx-select="{hx_select}"
  hx-target="{hx_target}"
  hx-swap="{hx_swap}"
>Load more posts... </div>"""
    else:
        load_more_html = "<div>Fin.</div>"

    # Generate HTML for the list of posts
    container_attrs = f'class="{container_class}"' if container_class else ""
    posts_html = "\n".join(
        [
            f"""
<div
  {container_attrs}
  hx-trigger="revealed once"
  hx-get="/{post['post_id']}?depth=0"
  hx-select="article"
  hx-target="this"
  hx-swap="innerHTML ignoreTitle:true"
>
  <article>Loading {post['post_id']}...</article>
</div>
            """
            for post in posts
        ]
    )

    if use_template:
        post_list_template = SafeTemplate(fetch_template("post_list.html"))
        content = post_list_template.substitute(
            {"header": header, "posts": SafeString(posts_html + load_more_html)}
        )
        return content
    else:
        return SafeString(posts_html + load_more_html)


routes = []


def route(pattern):
    def decorator(f):
        routes.append((pattern, f))
        return f

    return decorator

whitelabel_routes = []


def whitelabel_route(pattern, **kwargs):
    def decorator(f):
        whitelabel_routes.append((pattern, f, kwargs))
        return f

    return decorator

def get_coins_sent():
    """Parse coins from attached messages (v2 API replacement for old get_coins_sent)."""
    attached_messages = get_attached_messages()
    coins = []

    for msg in attached_messages:
        if msg.get("@type") == "/cosmos.bank.v1beta1.MsgSend":
            # Extract coins from MsgSend message
            msg_coins = msg.get("amount", [])
            for coin in msg_coins:
                coins.append({"denom": coin["denom"], "amount": coin["amount"]})

    return coins


def get_caller():
    """Alias for get_executor_address() for backward compatibility."""
    return get_executor_address()


def publish_post(content: TEXTAREA, author: str = ""):
    """Publish a post to the blockchain.

    Allows the submission of a post to the blockchain.
    If the post includes replies to other posts, those replies are also stored.

    Args:
        content (TEXTAREA): The content of the post.
        author (str): The `.dys` name of the author.

    Returns:
        int: The ID of the published post.
    """

    author = author.strip()
    if get_caller() and author:
        # query the blockchain to retrieve the owner of the provided name
        name_resp = _query(
            {
                "@type": "/dysonprotocol.nameservice.v1.QueryResolveNameRequest",
                "name_or_address": author,
            }
        )
        destination_address = name_resp["address"]
        assert (
            get_caller() == destination_address
        ), f'[{get_caller()}] is not authorized for "{author}" (destination: {destination_address})'

    # set the author to either the name or the caller or test name for preview
    author = author or get_caller()
    post_id = _get_next_id("posts")  # fetch the next available post id

    # find all replies to other posts in the content using regular expression
    replies_to = {}
    replied_to_posts = re.findall(POST_RE, content)
    if len(replied_to_posts) > 5:
        raise ValueError(
            f"Too many replies, max 5 allowed, you have {len(replied_to_posts)}"
        )
    for replied_to_post_id, anchor_text in replied_to_posts:
        reply = replies_to.get(
            replied_to_post_id,
            {
                "from_post": int(post_id),
                "to_post": int(replied_to_post_id),
                "anchors": [],
            },
        )

        if anchor_text:
            reply["anchors"].append(anchor_text)
        replies_to[replied_to_post_id] = reply

    for k, v in replies_to.items():
        _rate(
            "replies",
            _format_id(v["to_post"]),
            v["from_post"],
            "up",
            1,
            metadata={"anchors": v["anchors"]},
        )

    # create a dictionary with post data
    block_info = get_block_info()
    post_data = {
        "post_id": post_id,
        "author": author,
        "content": content,
        "created_height": block_info["height"],
        "created_time": block_info["time"],
    }

    # store the post data and author-post relationship on the blockchain
    _store_data(_get_post_index(post_id), post_data)
    _store_data(_get_author_post_index(**post_data), {"post_id": post_id})

    # _store_data(_get_reply_rewards_index(post_id), {"available": {}, "claimed": {}})
    return post_id  # return the post id


def append_to_post(post_id: int, content: TEXTAREA):
    post = _get_data(_get_post_index(post_id))  # retrieve the post data
    author = post["author"]

    # ensure that only the post author or the owner of the author's name can delete the post
    if author != get_caller():
        try:
            name_resp = _query(
                {
                    "@type": "/dysonprotocol.nameservice.v1.QueryResolveNameRequest",
                    "name_or_address": author,
                }
            )
            destination_address = name_resp["address"]
            assert get_caller() == destination_address
        except Exception as e:
            raise Exception(
                f'[{get_caller()}] is not the owner or destination of the author "{author}": {e}'
            )

    post["content"] += content
    block_info = get_block_info()
    post["updated_height"] = block_info["height"]
    post["updated_time"] = str(datetime.now())
    _store_data(_get_post_index(post_id), post)


def edit_author_profile(content: TEXTAREA, author: str = ""):

    author = author.strip()
    if get_caller() and author:
        # query the blockchain to retrieve the owner of the provided name
        try:
            name_resp = _query(
                {
                    "@type": "/dysonprotocol.nameservice.v1.QueryResolveNameRequest",
                    "name_or_address": author,
                }
            )
            destination_address = name_resp["address"]
            assert get_caller() == destination_address
        except Exception as e:
            raise Exception(f'[{get_caller()}] is not authorized for "{author}": {e}')

    # set the author to either the name or the caller
    author = author or get_caller()

    profile_data = _get_profile(author)
    profile_data["content"] = content
    _store_data(_get_author_profile_index(author), profile_data)


def link_page(path: str, post_id: int, author: str, title: str = ""):
    """Link a custom page to a post for an author.
    
    Creates a custom author page that displays the specified post at the given path.
    Only the author or authorized name owner can create links.
    
    Args:
        path (str): The custom path for the page (e.g., "about", "contact")
        post_id (int): The ID of the post to display at this path
        author (str): The author name or address
        title (str): The title of the page (optional)
    Raises:
        Exception: If caller is not authorized for the author
        AssertionError: If post doesn't exist or path is invalid
    """
    path = path.strip().strip("/")
    author = author.strip()
    
    # Validate path
    assert path and len(path) <= 50, "Path must be 1-50 characters"
    # Check if path contains only allowed characters (letters, numbers, hyphens, underscores)
    allowed_chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
    for c in path:
        assert c in allowed_chars, "Path must contain only letters, numbers, hyphens, and underscores"
    
    # Validate author is non-falsey and resolves to caller
    assert author, "Author must be provided and non-empty"
    
    try:
        name_resp = _query(
            {
                "@type": "/dysonprotocol.nameservice.v1.QueryResolveNameRequest",
                "name_or_address": author,
            }
        )
        destination_address = name_resp["address"]
        assert get_caller() == destination_address, f'Author "{author}" does not resolve to caller address'
    except Exception as e:
        raise Exception(f'[{get_caller()}] is not authorized for "{author}": {e}')
    
    # Validate post exists
    try:
        _get_data(_get_post_index(post_id))
    except Exception as e:
        raise AssertionError(f"Post {post_id} not found: {e}")
    
    # Store the page link
    page_data = {
        "post_id": post_id,
        "author": author,
        "title": title,
        "path": path,
        "created_time": get_block_info()["time"]
    }
    
    _store_data(_get_author_page_index(author, path), page_data)


def unlink_page(path: str, author: str = ""):
    """Remove a custom page link for an author.
    
    Removes the custom author page at the specified path.
    Only the author or authorized name owner can remove links.
    
    Args:
        path (str): The custom path to remove
        author (str): The author name or address (defaults to caller)
        
    Raises:
        Exception: If caller is not authorized for the author
        AssertionError: If page doesn't exist
    """
    path = path.strip()
    author = author.strip()
    
    # Validate author authorization
    if get_caller() and author:
        try:
            name_resp = _query(
                {
                    "@type": "/dysonprotocol.nameservice.v1.QueryResolveNameRequest",
                    "name_or_address": author,
                }
            )
            destination_address = name_resp["address"]
            assert get_caller() == destination_address
        except Exception as e:
            raise Exception(f'[{get_caller()}] is not authorized for "{author}": {e}')
    
    # Set author to caller if not specified
    author = author or get_caller()
    
    # Delete the page link
    page_index = _get_author_page_index(author, path)
    
    # Verify page exists before deletion
    try:
        _get_data(page_index)
    except Exception as e:
        raise AssertionError(f"Page '{path}' not found for author '{author}': {e}")
    
    _delete_data(page_index)


def _get_next_id(key: str):
    index = _get_next_id_index(key)
    # Query the blockchain for the current ID and increment it
    try:
        res = _query(
            {
                "@type": "/dysonprotocol.storage.v1.QueryStorageGetRequest",
                "owner": get_script_address(),
                "index": index,
            }
        )
        next_id = int(json.loads(res["entry"]["data"])) if res.get("entry") else 1
    except Exception as e:
        print(f"Failed to get next ID, defaulting to 1: {e}")
        next_id = 1
    _store_data(index, next_id + 1)  # Store the updated ID back on the blockchain
    return next_id


def _store_data(index: str, data):
    _msg(
        {
            "@type": "/dysonprotocol.storage.v1.MsgStorageSet",
            "owner": get_script_address(),
            "index": index,
            "data": json.dumps(data),  # Data is stored in JSON format
        }
    )


def _get_data(index: str):
    result = _query(
        {
            "@type": "/dysonprotocol.storage.v1.QueryStorageGetRequest",
            "owner": get_script_address(),
            "index": index,
        }
    )
    if not result.get("entry"):
        raise AssertionError(
            f"Error retrieving data: entry not found for index {index}"
        )
    return json.loads(result["entry"]["data"])  # Return the parsed JSON data


def _list_data(prefix: str, **kwargs):
    query_params = {
        "@type": "/dysonprotocol.storage.v1.QueryStorageListRequest",
        "owner": get_script_address(),
        "index_prefix": prefix,
        **kwargs,
    }

    # DEBUG: Print the exact query being constructed
    print(f"DEBUG _list_data: Constructing query with params: {json.dumps(query_params, indent=2)}")

    result = _query(query_params)

    # DEBUG: Print the raw result
    print(f"DEBUG _list_data: Raw query result: {json.dumps(result, indent=2)}")


    processed_entries = [
        {"_index": item["index"], **json.loads(item["data"])}
        for item in result.get("entries", [])
    ]

    # DEBUG: Print processed entries
    # print(f"DEBUG _list_data: Processed {len(processed_entries)} entries")
    # for i, entry in enumerate(processed_entries):
    #    print(f"DEBUG _list_data: entry[{i}] = {entry}")

    return (
        processed_entries,
        result.get("pagination", {}),
    )


def _delete_data(index: str):
    _msg(
        {
            "@type": "/dysonprotocol.storage.v1.MsgStorageDelete",
            "owner": get_script_address(),
            "indexes": [index],
        }
    )


def _best_rating(up, down) -> float:
    """Calculate Wilson score with a given confidence level."""

    n = up + down
    if n == 0:
        return 0.0  # No rates, return default score

    z = 1.96  # Z-score for 95% confidence
    p = up / n
    z2 = z**2

    # Wilson score lower bound
    score = (
        p + (z2 / (2 * n)) - z * math.sqrt((p * (1 - p) / n) + (z2 / (4 * n**2)))
    ) / (1 + (z2 / n))

    return round(score, 5)


NEWNESS_BOOST = 2


def _hot_rating(up, down, created_timestamp):

    s = up - down
    order = math.log1p(abs(s))
    sign = (s > 0) - (s < 0)

    time_units = (created_timestamp - 1731932970) / (24 * 60 * 60 * NEWNESS_BOOST)

    return round((sign * order) + time_units, 5)


## Utility functions for generating indexes
def _format_id(id: int) -> str:
    return f"{int(id):015}"


def _get_post_index(post_id: int) -> str:
    return f"posts/{_format_id(post_id)}"


def _get_author_post_prefix(author: str, **kwargs) -> str:
    return f"authors/{author}/posts/"


def _get_author_post_index(author: str, post_id: int, **kwargs) -> str:
    return _get_author_post_prefix(author) + _format_id(post_id)


def _get_author_profile_index(author: str) -> str:
    return f"authors/{author}/profile"


def _get_author_page_index(author: str, path: str) -> str:
    return f"author_page/{author}/{path}"


def _get_author_page_prefix(author: str) -> str:
    return f"author_page/{author}/"


def _get_next_id_index(key: str) -> str:
    return f"next_id/{key}"


################
###  Rating  ###
################


def validate_tag_name(tag_name: str) -> bool:
    """Validate a tag name to ensure it is a single word containing only letters, numbers, and hyphens."""
    return re.match(r"^[a-zA-Z0-9-]+$", tag_name) is not None


def rate_tag(
    tag_name: str,
    post_id: int,
    rate: typing.Literal["up", "down"],
    contributor: str = "",
):

    assert len(tag_name) <= 15, f"Tag is too long (max 15): {len(tag_name)}"
    coins = get_coins_sent()
    assert (
        len(coins) == 1 and coins[0]["denom"] == "udys"
    ), f"Invalid coins, must send udys and only udys, sent: {coins}"
    coins[0]["amount"] = int(coins[0]["amount"])
    amount = coins[0]["amount"]
    rate_amount = amount / 1000000
    try:
        rate_index = _get_rate_index("tags", tag_name, post_id)
        _get_data(rate_index)
    except Exception as e:
        # Post Tag doesn't exist, maybe the author is adding it.
        print(f"Rate index not found: {e}")
        post = _get_data(_get_post_index(post_id))

        author = post["author"]
        # ensure that only the post author or the owner of the author's name can tag the post
        if author != get_caller():
            name_resp = _query(
                {
                    "@type": "/dysonprotocol.nameservice.v1.QueryResolveNameRequest",
                    "name_or_address": author,
                }
            )
            destination_address = name_resp["address"]
            assert get_caller() == destination_address, f"Nonexistant tag[{tag_name}] for post_id[{post_id}] and only the author[{post['author']}] can add new tags not you[{get_caller()}]"
    _rate("tags", tag_name, post_id, rate, rate_amount, contributor=contributor)


def rate_reply(post_id: int, reply_post_id: int, rate: str):

    reply_post_id = int(reply_post_id)
    post_id = int(post_id)
    coins = get_coins_sent()
    assert (
        len(coins) == 1 and coins[0]["denom"] == "udys"
    ), f"Invalid coins, must send udys and only udys, sent: {coins}"
    coins[0]["amount"] = int(coins[0]["amount"])
    amount = coins[0]["amount"]
    rate_amount = amount / 1000000

    # Check if the reply relationship exists by looking for the reply in the hot list
    try:
        prefix = _get_rating_rate_prefix("replies", _format_id(post_id), "hot")
        hot_replies, _ = _list_data(prefix)
        reply_exists = any([reply["id"] == reply_post_id for reply in hot_replies])
        assert (
            reply_exists
        ), f"Reply post {reply_post_id} not found in replies to post {post_id}"
    except Exception as e:
        raise Exception(
            f"Nonexistant reply for post_id[{post_id}] and reply post_id[{reply_post_id}]: {e}"
        )

    _rate("replies", _format_id(post_id), reply_post_id, rate, rate_amount)


def _rate(
    namespace: str,
    tag_name: str,
    id: int,
    rate: str,
    amount: int = 1,
    metadata=None,
    contributor: str = "",
):
    """Rate on a tag within a namespace and update the score, including reverse indexing.

    Args:
        namespace (str): The namespace within which the tag resides.
        tag_name (str): The tag to rate on.
        id (int): The identifier for the item being rated on.
        rate (str): 'up' for uprate, 'down' for downrate.
        amount (int): The amount to increment the rate by (default is 1).

    Raises:
        ValueError: If rate is not 'up' or 'down'.
    """

    assert amount > 0, "Amount must be greater than 0"
    assert validate_tag_name(tag_name), "Tag must be alphanumeric"

    rate_index = _get_rate_index(namespace, tag_name, id)

    coins = get_coins_sent()
    # Fetch existing rate data or create a new entry
    try:
        rate_data = _get_data(rate_index)
    except Exception as e:
        print(f"Creating new rate data: {e}")
        block_info = get_block_info()
        rate_data = {
            "namespace": namespace,
            "tag_name": tag_name,
            "id": id,
            "up": 0,
            "down": 0,
            "best_rating": 0,
            "hot_rating": 0,
            "created_height": block_info["height"],
            "created_timestamp": int(datetime.now().timestamp()),
            "metadata": {},
        }

    # Remove old score and reverse indexes
    _delete_rating_index(rate_data)
    _delete_reverse_rating_index(rate_data)

    if metadata:
        rate_data["metadata"] = metadata

    # Update rate counts
    if rate == "up":
        rate_data["up"] += amount
    elif rate == "down":
        rate_data["down"] += amount
    else:
        raise ValueError("Rate must be 'up' or 'down'.")

    # Recalculate scores
    rate_data["best_rating"] = _best_rating(rate_data["up"], rate_data["down"])
    rate_data["hot_rating"] = _hot_rating(
        rate_data["up"], rate_data["down"], rate_data["created_timestamp"]
    )

    # Store updated rate data and update indexes
    _store_data(rate_index, rate_data)
    _set_rating_index(rate_data)
    _set_reverse_rating_index(rate_data)
    _add_rewards(tag_name, coins, namespace=namespace, contributor=contributor)


def _track_contributor_rewards(namespace, tag_name, coins, contributor):
    # get the current index
    index = _get_tag_contributor_index(namespace, tag_name, contributor)
    try:
        data = _get_data(index)
    except Exception as e:
        print(f"Contributor data not found, creating new: {e}")
        data = {}

    # delete old reverse index
    for denom, amount in data.items():
        try:
            _delete_data(
                _get_reverse_contributor_index(
                    namespace, tag_name, denom, amount, contributor
                )
            )
        except AssertionError as e:
            print(f"Failed to delete reverse contributor index: {e}")

    for c in coins:
        data[c["denom"]] = data.get(c["denom"], 0) + int(c["amount"])
        # add new reverse index
        _store_data(
            _get_reverse_contributor_index(
                namespace, tag_name, c["denom"], data[c["denom"]], contributor
            ),
            {
                "contributor": contributor,
                "denom": c["denom"],
                "amount": data[c["denom"]],
            },
        )
    _store_data(index, data)


### Indexing Functions ###


def _get_rate_index(namespace: str, tag_name: str, id: int) -> str:
    """Generate the index for storing rates within a namespace."""
    return f"rate_tags/{namespace}/{tag_name}/{_format_id(id)}"


def _get_tag_prefix(namespace: str) -> str:
    return f"tag/{namespace}/"


def _get_tag_index(namespace: str, tag_name: str) -> str:
    if isinstance(tag_name, int):
        tag_name = _format_id(tag_name)
    return _get_tag_prefix(namespace) + tag_name


def _get_reverse_contributor_prefix(namespace: str, tag_name, denom) -> str:
    return f"top_tag_contributor/{namespace}/{tag_name}/{denom}/"


def _get_reverse_contributor_index(namespace, tag_name, denom, amount, contributor):
    return (
        _get_reverse_contributor_prefix(namespace, tag_name, denom)
        + f"{amount:015}/{contributor}"
    )


def _get_tag_contributor_prefix(namespace: str) -> str:
    return f"tag_contributor/{namespace}/"


def _get_tag_contributor_index(namespace, tag_name, contributor):
    return _get_tag_contributor_prefix(namespace) + f"{tag_name}/{contributor}"


def _get_rating_rate_prefix(namespace: str, tag_name: str, rating_type: str) -> str:
    """Index for storing score-based rates, supporting both 'best' and 'hot' types."""
    return f"rate/{namespace}/{tag_name}/{rating_type}/"


def _get_rating_rate_index(
    namespace: str, tag_name: str, rating_type: str, score: float, id: int
) -> str:
    """Index for storing score-based rates, supporting both 'best' and 'hot' types."""
    return (
        _get_rating_rate_prefix(namespace, tag_name, rating_type)
        + f"{score:012.05f}/{_format_id(id)}"
    )


def _get_reverse_rating_prefix(namespace: str, id: int, rating_type: str) -> str:
    """Prefix for reverse indexing of scored tags on a namespaced object ID."""
    return f"reverse_rates/{namespace}/{_format_id(id)}/{rating_type}/"


def _get_reverse_rating_index(
    namespace: str, id: int, tag_name: str, rating_type: str, score: float
) -> str:
    """Index for reverse relationship of scored tag on namespaced object ID."""
    return (
        _get_reverse_rating_prefix(namespace, id, rating_type)
        + f"{score:012.05f}/{tag_name}"
    )


def _delete_rating_index(rate_data):
    """Delete old score indexes for a rate."""
    try:
        _delete_data(
            _get_rating_rate_index(
                rate_data["namespace"],
                rate_data["tag_name"],
                "best",
                rate_data["best_rating"],
                rate_data["id"],
            )
        )
    except Exception as e:
        print(f"Failed to delete best rating index: {e}")
        pass
    try:
        _delete_data(
            _get_rating_rate_index(
                rate_data["namespace"],
                rate_data["tag_name"],
                "hot",
                rate_data["hot_rating"],
                rate_data["id"],
            )
        )
    except Exception as e:
        print(f"Failed to delete hot rating index: {e}")
        pass


def _delete_reverse_rating_index(rate_data):
    """Delete old reverse score indexes for a rate."""
    try:
        _delete_data(
            _get_reverse_rating_index(
                rate_data["namespace"],
                rate_data["id"],
                rate_data["tag_name"],
                "best",
                rate_data["best_rating"],
            )
        )
    except Exception as e:
        print(f"Failed to delete reverse best rating index: {e}")
        pass
    try:
        _delete_data(
            _get_reverse_rating_index(
                rate_data["namespace"],
                rate_data["id"],
                rate_data["tag_name"],
                "hot",
                rate_data["hot_rating"],
            )
        )
    except Exception as e:
        print(f"Failed to delete reverse hot rating index: {e}")
        pass


def _set_rating_index(rate_data):
    """Set new score indexes for a rate."""
    _store_data(
        _get_rating_rate_index(
            rate_data["namespace"],
            rate_data["tag_name"],
            "best",
            rate_data["best_rating"],
            rate_data["id"],
        ),
        {
            "id": rate_data["id"],
            "best_rating": rate_data["best_rating"],
            "metadata": rate_data["metadata"],
        },
    )
    _store_data(
        _get_rating_rate_index(
            rate_data["namespace"],
            rate_data["tag_name"],
            "hot",
            rate_data["hot_rating"],
            rate_data["id"],
        ),
        {
            "id": rate_data["id"],
            "hot_rating": rate_data["hot_rating"],
            "metadata": rate_data["metadata"],
        },
    )


def _set_reverse_rating_index(rate_data):
    """Set reverse score indexes for a rate."""
    _store_data(
        _get_reverse_rating_index(
            rate_data["namespace"],
            rate_data["id"],
            rate_data["tag_name"],
            "best",
            rate_data["best_rating"],
        ),
        {"tag_name": rate_data["tag_name"]},
    )
    _store_data(
        _get_reverse_rating_index(
            rate_data["namespace"],
            rate_data["id"],
            rate_data["tag_name"],
            "hot",
            rate_data["hot_rating"],
        ),
        {"tag_name": rate_data["tag_name"]},
    )


##################
###  Rewards ##
##################
REPLIES = "replies"
TAGS = "tags"


def claim_reply_rewards(post_id: int, hot_index: int):
    return _claim_rewards(_format_id(post_id), hot_index, REPLIES)


def claim_tag_rewards(tag_name: str, hot_index: int):
    return _claim_rewards(tag_name, hot_index, TAGS)


def debug_hot_list(
    tag_name: str, reverse: bool = False, offset: int = 0, limit: int = 10
):
    """Debug function to inspect the hot list contents for a tag."""
    print(f"DEBUG debug_hot_list: reverse={reverse}, offset={offset}, limit={limit}")
    prefix = _get_rating_rate_prefix("tags", tag_name, "hot")
    hot_posts, pagination = _list_data(
        prefix,
        pagination={
            "reverse": reverse,
            "offset": offset,
            "limit": limit,
            "count_total": True,
        },
    )

    debug_info = {
        "tag_name": tag_name,
        "hot_list_count": len(hot_posts),
        "hot_posts": [
            {"id": post["id"], "hot_rating": post.get("hot_rating", "N/A")}
            for post in hot_posts
        ],
        "prefix_used": prefix,
    }

    return debug_info


def _claim_rewards(tag_name: str, hot_index: int, namespace: str):
    prefix = _get_rating_rate_prefix(namespace, tag_name, "hot")

    assert (
        10 > hot_index
    ), f"Only the top 10 hot posts can claim rewards, index [{hot_index}] is too low."

    # Fetch the specific hot post using offset-based pagination
    hot_posts, pagination = _list_data(
        prefix, pagination={"offset": hot_index, "limit": 1, "reverse": True}
    )

    assert (
        len(hot_posts) > 0
    ), f"Index[{hot_index}] hot post for tag[{tag_name}] not found."

    # Get the post at the specific hot_index
    hot_post = hot_posts[0]

    post_index = _get_post_index(hot_post["id"])
    post = _get_data(post_index)  # retrieve the post data

    author = post["author"]

    # ensure that only the post author or the owner of the author's name can claim the rewards
    if author != get_caller():
        try:
            name_resp = _query(
                {
                    "@type": "/dysonprotocol.nameservice.v1.QueryResolveNameRequest",
                    "name_or_address": author,
                }
            )
            destination_address = name_resp["address"]
            assert get_caller() == destination_address
        except Exception as e:
            raise Exception(f'[{get_caller()}] is not authorized for "{author}": {e}')

    reward_index = _get_tag_index(namespace, tag_name)
    try:
        rewards = _get_data(reward_index)
    except AssertionError as e:
        raise Exception(f"no rewards available: {e}")
    _delete_rewards_indexes(namespace, rewards)

    tag_data = _get_post_tag(post["post_id"], tag_name, namespace=namespace)
    assert (
        tag_data is not None
    ), f"Tag data not found for post {post['post_id']}, tag {tag_name}"

    # DEBUG: Print what tag_data we got
    print(
        f"DEBUG _claim_rewards: tag_data for post {post['post_id']}: earliest_claim_time={tag_data['metadata']}"
    )

    tag_data["metadata"]["claimed"] = tag_data["metadata"].get("claimed", {})
    earliest_claim_time = tag_data["metadata"].get("earliest_claim_time", 0)

    now = int(datetime.now().timestamp())

    assert (
        now >= earliest_claim_time
    ), f"You must wait [{earliest_claim_time - now}]seconds to claim rewards for tag[{tag_name}] of post[{post['post_id']}]."

    earliest_claim_time = now + CLAIM_WAIT_SEC
    tag_data["metadata"]["last_claimed"] = now
    tag_data["metadata"]["earliest_claim_time"] = earliest_claim_time

    reward_power = Decimal(1) / (Decimal(2) ** (Decimal(hot_index) + Decimal(1)))
    author_rewards = {}

    profile_data = _get_profile(author)
    profile_data["claimed"] = profile_data.get("claimed", {})
    post["claimed"] = post.get("claimed", {})
    for denom, amount in rewards["available"].items():
        reward_amount = int(Decimal(amount) * reward_power)
        author_rewards[denom] = reward_amount

        _msg(
            {
                "@type": "/cosmos.bank.v1beta1.MsgSend",
                "from_address": get_script_address(),
                "to_address": get_caller(),
                "amount": [{"amount": str(reward_amount), "denom": denom}],
            }
        )

        # update available rewards
        rewards["available"][denom] -= reward_amount
        rewards["claimed"][denom] = rewards["claimed"].get(denom, 0) + reward_amount

        # store on post tag
        tag_data["metadata"]["claimed"][denom] = (
            tag_data["metadata"]["claimed"].get(denom, 0) + reward_amount
        )
        post["claimed"][denom] = post["claimed"].get(denom, 0) + reward_amount
        profile_data["claimed"][denom] = (
            profile_data["claimed"].get(denom, 0) + reward_amount
        )

    _store_data(post_index, post)
    _store_data(_get_author_profile_index(author), profile_data)
    _store_data(_get_rate_index(namespace, tag_name, post["post_id"]), tag_data)
    _store_data(reward_index, rewards)
    _set_rewards_indexes(namespace, rewards)
    if namespace == TAGS:
        block_info = get_block_info()
        _store_data(
            _get_post_tag_historical_rewards_prefix(
                tag_name, post["post_id"], block_info["time"], namespace=namespace
            ),
            {
                "hot_index": hot_index,
                "author_rewards": author_rewards,
                "up": tag_data["up"],
                "down": tag_data["down"],
            },
        )
    return {"reward_power": str(reward_power), "author_rewards": author_rewards}


def _get_post_tag_historical_rewards_prefix(
    tag_name: str | None = None,
    post_id: int | None = None,
    time: str | None = None,
    author: str | None = None,
    namespace=TAGS,
) -> str:
    prefix = "historical_rewards"
    path_parts = [prefix, namespace]

    if tag_name is not None:
        path_parts.append(tag_name)
    if post_id is not None:
        path_parts.append(_format_id(post_id))
    if time is not None:
        path_parts.append(str(time))

    return "/".join(path_parts)


def add_tag_rewards(tag_name: str, contributor: str = ""):
    coins = get_coins_sent()
    _add_rewards(tag_name, coins, TAGS, contributor)


def _add_rewards(tag_name, coins, namespace, contributor):

    if not contributor:
        contributor = get_caller()
    else:
        name_resp = _query(
            {
                "@type": "/dysonprotocol.nameservice.v1.QueryResolveNameRequest",
                "name_or_address": contributor,
            }
        )
        destination_address = name_resp["address"]
        assert get_caller() == destination_address, f"[{get_caller()}] is not authorized for contributor name: {contributor}"
    index = _get_tag_index(namespace, tag_name)

    try:
        rewards = _get_data(index)
    except Exception as e:
        print(f"Tag rewards not found: {e}")
        rewards = {"available": {}, "claimed": {}, "tag_name": tag_name}

    _delete_rewards_indexes(namespace, rewards)

    for coin in coins:
        old_amount = rewards["available"].get(coin["denom"], 0)
        rewards["available"][coin["denom"]] = old_amount + int(coin["amount"])

    _store_data(index, rewards)
    _set_rewards_indexes(namespace, rewards)
    if namespace == TAGS:
        _track_contributor_rewards(namespace, tag_name, coins, contributor=contributor)


def _available_reward_prefix(namespace):
    return f"available_rewards/{namespace}/"


def _available_reward_index(namespace, tag_name, denom, available_rewards):
    return (
        _available_reward_prefix(namespace)
        + f"{denom}/{available_rewards:015}/{tag_name}"
    )


def _delete_rewards_indexes(namespace, rewards):
    for denom, amount in rewards["available"].items():
        index = _available_reward_index(namespace, rewards["tag_name"], denom, amount)
        try:
            _delete_data(index)
        except Exception as e:
            print(f"Failed to delete rewards index: {e}")
            pass


def _set_rewards_indexes(namespace, rewards):
    for denom, amount in rewards["available"].items():
        index = _available_reward_index(namespace, rewards["tag_name"], denom, amount)
        _store_data(
            index, {"tag_name": rewards["tag_name"], "denom": denom, "amount": amount}
        )


#############
## Web App ##
#############

# Constants for content type
CONTENT_TYPE_HTML = ("Content-Type", "text/html; charset=UTF-8")
CONTENT_TYPE_JS = ("Content-Type", "application/javascript; charset=utf-8")
HEADERS = [
    ("Access-Control-Allow-Methods", "HEAD, GET, POST, OPTIONS"),
    ("Access-Control-Allow-Headers", "*"),
    #("Cache-Control", "max-age=60, public"),
    ("Service-Worker-Allowed", "/"),
    # /("Content-Security-Policy-Report-Only", "default-src 'none'"),
    (
        "Content-Security-Policy",
        "script-src * 'unsafe-eval' 'unsafe-inline'; worker-src *; img-src 'self' data:",
    ),
    ("X-DysonProtocol-Block-Height", json.dumps(get_block_info()["height"])),
]


def _parse_pagination(environ, reverse=False, default_limit=None):

    pagination = {
        k: v
        for k, v in parse_qsl(environ.get("QUERY_STRING", ""))
        if k in ["reverse", "offset", "limit", "key"]
    }

    if reverse:
        pagination["reverse"] = str(pagination.get("reverse", False)).lower() not in [
            "1",
            "t",
            "true",
        ]

    if "limit" not in pagination and default_limit is not None:
        pagination["limit"] = default_limit

    return pagination


def _get_profile(author_name):
    try:
        profile_index = _get_author_profile_index(author_name)
        profile_data = _get_data(profile_index)
        print(
            f"Successfully retrieved profile for {author_name}: content length = {len(profile_data.get('content', ''))}"
        )
        return profile_data
    except Exception as e:
        print(
            f"Profile not found for {author_name} at index {_get_author_profile_index(author_name)}: {e}"
        )
        return {"content": "", "claimed": {}}


def _get_best_tags_by_post_id(post_id: int, **kwargs):
    prefix = _get_reverse_rating_prefix("tags", post_id, "best")
    return _list_data(prefix, **kwargs)


def _get_post_tag(post_id: int, tag_name: str, namespace="tags"):
    try:
        tag_index = _get_rate_index(namespace, tag_name, post_id)
        return _get_data(tag_index)
    except DysQueryException as e:
        print(f"Could not find tag '{tag_name}' for post {post_id}: {e}")
        return None


def _get_best_replies_by_post_id(post_id: int, **kwargs):
    prefix = _get_rating_rate_prefix("replies", _format_id(post_id), "best")
    return _list_data(prefix, **kwargs)


def _get_post_reply(post_id: int, reply_post_id: int):
    tag_index = _get_rate_index("replies", _format_id(post_id), reply_post_id)
    return _get_data(tag_index)


StartResponse = Callable[[str, List[Tuple[str, str]], tuple | None], Callable]
WSGIApp = Callable[[dict, StartResponse], Iterable[bytes]]


def with_etag(app: WSGIApp) -> WSGIApp:
    """Wrap an existing WSGI app and add automatic ETag + 304 support."""

    def _wrapped(environ: dict, start_response: StartResponse) -> Iterable[bytes]:
        captured: list[bytes] = []

        # 1. Call the wrapped app, intercepting its *write* callable so we can
        #    keep a copy of everything sent.
        status_headers: dict[str, object] = {}

        def _capture_start(
            status: str, headers: List[Tuple[str, str]], exc_info=None
        ) -> Callable[[bytes], None]:
            status_headers["status"] = status
            status_headers["headers"] = headers
            status_headers["exc_info"] = exc_info
            return captured.append

        body_iter = app(environ, _capture_start)

        # 2. Accumulate the body (works for short responses; see notes below).
        for chunk in body_iter:
            captured.append(chunk)
        body = b"".join(captured)

        status: str = status_headers["status"]  # type: ignore
        headers = status_headers["headers"].copy()  # type: ignore

        # 3. Compute & attach ETag only for successful responses that have a body.
        if status.startswith("200") and body:
            etag = '"' + hashlib.sha256(body).hexdigest() + '"'
            headers.append(("ETag", etag))

            if environ.get("HTTP_IF_NONE_MATCH") == etag:
                # 4. Client already has the same version → reply 304.
                #    Remove/overwrite entity headers that no longer apply.
                headers = [
                    (k, v)
                    for k, v in headers
                    if k.lower() not in {"content-length", "content-type"}
                ]
                start_response("304 Not Modified", headers, status_headers["exc_info"])  # type: ignore
                return []

        # 5. Normal 200/other response path.
        headers.append(("Content-Length", str(len(body))))
        start_response(status, headers, status_headers["exc_info"])  # type: ignore
        return [body]

    return _wrapped


# @with_etag
def wsgi(environ, start_response):
    """WSGI Application using declarative routing.

    This is the entry point for serving the website.
    It handles routing and serves data based on the request path.
    """
    if environ['REQUEST_METHOD'] == 'OPTIONS':
        start_response('200 OK', [
            ('Access-Control-Allow-Origin', '*'),
            ('Access-Control-Allow-Methods', 'GET, POST, OPTIONS'),
            ('Access-Control-Allow-Headers', '*'),
        ])
        return [b'']

    path_info = environ["PATH_INFO"]
    if WHITELABEL:
        for pattern, func, kwargs in whitelabel_routes:
            m = re.match(pattern, path_info)
            if m:
                return func(environ, start_response, **m.groupdict(), **kwargs)

    for pattern, func in routes:
        m = re.match(pattern, path_info)
        if m:
            return func(environ, start_response, **m.groupdict())
    start_response("404 Not Found", [("Content-Type", "text/plain; charset=utf-8")])
    return [b"404 Not Found"]


@route(r"^/$")
def handle_root(environ, start_response):
    """Handle root redirect to /recent"""

    start_response("302 Moved", [
        ("Location", "/recent"),
            ('Access-Control-Allow-Origin', '*'),
            ('Access-Control-Allow-Methods', 'GET, POST, OPTIONS'),
            ('Access-Control-Allow-Headers', '*'),
    ])
    return []

@whitelabel_route(r"^/$", name=name)
def handle_whitelabel_root(environ, start_response, name):
    return handle_author_posts(environ, start_response, name, whitelabel=True)

@route(r"^/blog/?$")
def handle_blog(environ, start_response):
    """Handle blog redirect to nuance.dys author page"""
    return handle_author_posts(environ, start_response, "nuance.dys")


@route(r"^/active/?$")
def handle_active(environ, start_response):
    """Handle active posts page"""
    req_pagination = _parse_pagination(environ, default_limit=2, reverse=True)
    posts, pagination = _list_data(
        "available_rewards/replies/udys/", pagination=req_pagination
    )

    # Generate placeholders for each replying post with HTMX fetching the full content
    items_html = "\n".join(
        [
            f"""
<div>
  <div class="active-info">
    <a href="/{int(post['tag_name'])}">Post #{int(post['tag_name'])}</a> has
    <strong>{post['amount'] // 1000000} DYS</strong> available to be
    claimed by top replies.
  </div>
  <article
    hx-trigger="load"
    hx-get="/{int(post['tag_name'])}?depth=0"
    hx-select="article"
    hx-target="closest article"
    hx-swap="outerHTML ignoreTitle:true"
  >
    <div class="">Loading post: #{int(post['tag_name'])}...</div>
  </article>
</div>
            """
            for post in posts
        ]
    )

    # Check if there are more replies to load
    if pagination.get("next_key"):
        next_key = pagination["next_key"]
        # Create the 'load more' placeholder
        load_more_html = f"""
            <div
              hx-get="/active/?limit={pagination.get('limit', 2)}&key={next_key}"
              hx-trigger="revealed"
              hx-swap="outerHTML ignoreTitle:true"
              hx-target="closest div"
              hx-select="main >  div"
            >
              Loading more posts...
            </div>

        """

    else:
        load_more_html = "<div>Fin.</div>"

    # Return only the replies items and load more element
    start_response("200 OK", [CONTENT_TYPE_HTML] + HEADERS)

    content = items_html + load_more_html

    html_content = _render_base(content, title="Active Posts")

    return [html_content]


@route(r"^/recent/?$")
def handle_recent(environ, start_response):
    """Handle recent posts page"""
    req_pagination = _parse_pagination(environ, reverse=True, default_limit=2)
    posts, pagination = _list_data("posts/", pagination=req_pagination)

    content = render_posts(
        posts=posts,
        pagination=pagination,
        header="",
        load_more_url_base="/recent/",
        req_pagination=req_pagination,
    )

    start_response("200 OK", [CONTENT_TYPE_HTML] + HEADERS)

    html_content = _render_base(content, title="Post List")

    return [html_content]


@route(r"^/(?P<post_id>\d+)$")
def handle_post_detail(environ, start_response, post_id):
    """Handle individual post detail page"""
    post_id = int(post_id)

    """Serve a specific post by post_id.

    Renders the detail view for a specific post.

    Args:
        environ (dict): The WSGI environment dictionary.
        start_response (callable): The WSGI start_response callable.
        post_id (int): The ID of the post to display.

    Returns:
        iterable: An iterable yielding the response body.
    """
    try:
        post = _get_data(_get_post_index(post_id))
    except Exception as e:
        # If the post is not found, return a 404 error
        start_response("404 Not Found", [CONTENT_TYPE_HTML])
        error_template = SafeTemplate(fetch_template("error.html"))
        content = error_template.substitute(
            {"message": f"Post {post_id} not found: {e}"}
        )
        html_content = _render_base(content, title="404 Not Found")

        return [html_content]

    # Escape HTML to prevent injection attacks
    depth = max(
        0,
        min(3, int(dict(parse_qsl(environ.get("QUERY_STRING", ""))).get("depth", 1))),
    )

    post_id = post["post_id"]

    author = html.escape(post["author"])
    content_text = html.escape(post["content"])
    if depth > 0:
        content_text = re.sub(
            POST_RE,
            rf"""

            <div
                    hx-trigger="intersect once"
                    hx-get="/\1?depth={depth - 1}"
                    hx-select="article"
                    hx-swap="innerHTML ignoreTitle:true"
                    hx-target="closest div"
                    data-fragment="\2"
                    >
                        Loading: \1  ...
            </div>

""",
            content_text,
        )
    else:
        content_text = re.sub(
            POST_RE,
            rf"""

            <div class="post" data-fragment="\2">
              <div style="border: 1px solid; margin: 1em 0;
    overflow: auto;
    word-wrap: break-word;
    padding: 1em 1.5em;">
                <header>
                    <button
                        class="btn text-center"
                        hx-trigger="click once"
                        hx-get="/\1?depth={depth}"
                        hx-select="article"
                        hx-swap="innerHTML ignoreTitle:true"
                        hx-target="closest div.post"
                    >
                    Load Post #\1
                    </button>
                    <mark data-render-fragment="\2"></mark>
                </header>
                </div>
            </div>

""",
            content_text,
        )

    post_detail_template = SafeTemplate(fetch_template("post_detail.html"))
    content = post_detail_template.substitute(
        {
            "post_id": post_id,
            "author": SafeString(author),  # Already HTML-escaped
            "content": SafeString(content_text),  # Already HTML-escaped with HTML added
            "created_time": post["created_time"],
            "claimed": post.get("claimed", {}).get("udys", 0) // 1000000,
        }
    )

    html_content = _render_base(content, title=f"Post {post_id}")

    start_response("200 OK", [CONTENT_TYPE_HTML] + HEADERS)

    html_content = _render_base(content, title=f"Post {post_id}")
    return [html_content]


@route(r"^/topics$")
def handle_topics(environ, start_response):
    """Handle topics list page"""
    # Alpine.js will handle data fetching and rendering client-side
    content = fetch_template("topics.html")

    start_response("200 OK", [CONTENT_TYPE_HTML] + HEADERS)

    html_content = _render_base(content, title="Topics")
    return [html_content]


@route(r"^/publish$")
def handle_publish(environ, start_response):
    """Handle new post publishing page"""
    new_post_template = SafeTemplate(fetch_template("new_post.html"))
    content = new_post_template.substitute({})

    start_response("200 OK", [CONTENT_TYPE_HTML] + HEADERS)

    html_content = _render_base(content, title="New Post")
    return [html_content]


@route(r"^/wallet$")
def handle_wallet(environ, start_response):
    """Handle wallet management page"""
    # This function generates the HTML body for the wallet management page.
    wallet_body_template = SafeTemplate(fetch_template("wallet.html"))
    wallet_body_html = wallet_body_template.substitute({})

    start_response("200 OK", [CONTENT_TYPE_HTML] + HEADERS)
    html_content = _render_base(wallet_body_html, title="Wallet Management")
    return [html_content]


@route(r"^/authors/(?P<author>[^/]+)/?$")
def handle_author_posts(environ, start_response, author, whitelabel=False):
    """Handle author posts list page"""
    profile_data = _get_profile(author)

    req_pagination = _parse_pagination(environ, reverse=True, default_limit=2)
    posts, pagination = _list_data(
        _get_author_post_prefix(author), pagination=req_pagination
    )

    posts_html = render_posts(
        posts=posts,
        pagination=pagination,
        header="",
        load_more_url_base=f"/authors/{author}",
        req_pagination=req_pagination,
        container_class="articleLoader",
        hx_select=".articleLoader",
        hx_swap="outerHTML",
        use_template=False,
    )

  
    
    profile_content = html.escape(profile_data.get("content", ""))
    
    profile_content = re.sub(
            POST_RE,
            r"""

            <div
                    hx-trigger="intersect once"
                    hx-get="/\1"
                    hx-select="article"
                    hx-swap="innerHTML ignoreTitle:true"
                    hx-target="closest div"
                    data-fragment="\2"
                    >
                        Loading: \1  ...
            </div>

""",
            profile_content,
        )
    head_extra = ""
    if whitelabel:
        head_extra=SafeString('''
<style>
    body > header {
        display: none;
    }
    .powered-by {
        display: block;
    }
</style>
''')

    # Use the new author_posts.html template
    author_posts_template = SafeTemplate(fetch_template("author_posts.html"))
    content = author_posts_template.substitute({
        "author": author,
        "claimed_dys": profile_data.get("claimed", {}).get("udys", 0) // 1000000,
        "profile_content": SafeString(profile_content),
        "posts_html": SafeString(posts_html),
    })

    start_response("200 OK", [CONTENT_TYPE_HTML] + HEADERS)
    html_content = _render_base(content, title=f"{author}", head_extra=head_extra)
    return [html_content]


@route(r"^/edit-author/(?P<author>[^/]+)/?$")
def handle_edit_author(environ, start_response, author):
    """Handle author profile editing page"""
    profile_data = _get_profile(author)
    
    # Load custom pages for this author
    try:
        custom_pages, _ = _list_data(_get_author_page_prefix(author))
        custom_pages_data = [
            {
                "path": page.get("path", page["_index"].split("/")[-1]),
                "post_id": page["post_id"],
                "title": page.get("title", "")
            }
            for page in custom_pages
        ]
    except Exception as e:
        print(f"No custom pages found for author {author}: {e}")
        custom_pages_data = []
    
    edit_template = SafeTemplate(fetch_template("edit_author_profile.html"))
    content = edit_template.substitute({
        "author_name": author, 
        "custom_pages": SafeString(json.dumps(custom_pages_data)),
        **profile_data
    })

    start_response("200 OK", [CONTENT_TYPE_HTML] + HEADERS)

    html_content = _render_base(content, title=f"Edit profile: {author}")
    return [html_content]

@whitelabel_route(r"^/(?P<path>.*[^/])/?$", author=name)
@route(r"^/authors/(?P<author>[^/]+)/(?P<path>.*[^/])/?$")
def handle_author_page(environ, start_response, author, path):
    """Handle custom author page display"""
    try:
        # Load the custom page data
        page_data = _get_data(_get_author_page_index(author, path))
        
        # Load the referenced post
        post = _get_data(_get_post_index(page_data["post_id"]))
        
        # Escape HTML to prevent injection attacks
        depth = max(
            0,
            min(3, int(dict(parse_qsl(environ.get("QUERY_STRING", ""))).get("depth", 1))),
        )

        post_id = post["post_id"]
        content_text = html.escape(post["content"])
        custom_title = html.escape(page_data.get("title", ""))
        
        # Handle post references in content (same as post detail)
        if depth > 0:
            content_text = re.sub(
                POST_RE,
                rf"""
                <div
                        hx-trigger="intersect once"
                        hx-get="/\1?depth={depth - 1}"
                        hx-select="article"
                        hx-swap="innerHTML ignoreTitle:true"
                        hx-target="closest div"
                        data-fragment="\2"
                        >
                            Loading: \1  ...
                </div>
    """,
                content_text,
            )
        else:
            content_text = re.sub(
                POST_RE,
                rf"""
                <div data-fragment="\2">
                        <a
                            hx-trigger="click once"
                            hx-get="/\1?depth={depth}"
                            hx-select="article"
                            hx-swap="innerHTML ignoreTitle:true"
                            hx-target="closest div"
                        >
                        /\1
                        </a>
                </div>
    """,
                content_text,
            )

        # Use the new author_custom_page.html template
        author_custom_page_template = SafeTemplate(fetch_template("author_custom_page.html"))
        content = author_custom_page_template.substitute({
            "custom_title": custom_title,
            "author": author,
            "post_id": post_id,
            "content_text": SafeString(content_text),
            "path": path
        })

        start_response("200 OK", [CONTENT_TYPE_HTML] + HEADERS)
        if WHITELABEL:
            head_extra=SafeString('''
<style>
    body > header {
        display: none;
    }
    .powered-by {
        display: block;
    }
</style>
''')       
        html_content = _render_base(content, title=custom_title, head_extra=head_extra)
        return [html_content]
        
    except Exception as e:
        # If the page is not found, return a 404 error
        start_response("404 Not Found", [CONTENT_TYPE_HTML])
        error_template = SafeTemplate(fetch_template("error.html"))
        content = error_template.substitute(
            {"message": f"Custom page '{path}' not found for author '{author}': {e}"}
        )
        html_content = _render_base(content, title="404 Not Found")
        return [html_content]


@route(r"^/(?P<post_id>\d+)/replies/?$")
def handle_post_replies(environ, start_response, post_id):
    """Handle post replies list page"""
    post_id = int(post_id)

    req_pagination = _parse_pagination(environ, default_limit=2, reverse=True)
    replies, replies_pagination = _get_best_replies_by_post_id(
        post_id, pagination=req_pagination
    )

    # Generate placeholders for each replying post with HTMX fetching the full content
    replies_items_html = "\n".join(
        [
            f"""
<div id="reply-{reply['id']}">
  <div
    href="/{post_id}/replies/{reply['id']}"
    hx-get="/{post_id}/replies/{reply['id']}"
    hx-select=".reply-detail-container"
    hx-trigger="revealed once"
    hx-swap="innerHTML"
    hx-target="this"
  >
    Loading reply: {reply['id']}
  </div>
  <div
    hx-trigger="load"
    hx-get="/{reply['id']}?depth=0"
    hx-select="article"
    hx-swap="innerHTML ignoreTitle:true"
    hx-target="this"
  >
    <div class="">Loading: {reply['id']} ...</div>
  </div>
</div>
            """
            for reply in replies
        ]
    )

    # Check if there are more replies to load
    if replies_pagination.get("next_key"):
        next_key = replies_pagination["next_key"]
        # Create the 'load more' placeholder
        load_more_html = f"""
            <div
              hx-get="/{post_id}/replies/?limit={req_pagination.get('limit', 2)}&key={next_key}"
              hx-trigger="revealed"
              hx-swap="outerHTML ignoreTitle:true"
              hx-select="#reply-content"
              hx-target="this"
            >
              Loading more replies...
            </div>

        """

    else:
        load_more_html = "<div>Fin.</div>"

    # Return only the replies items and load more element

    content = (
        f'<h2 class="text-2xl font-bold text-gray-900 py-4">Replies to <a href="/{post_id}"> Post #{post_id}</a></h2><div id="reply-content">'
        + replies_items_html
        + load_more_html
        + "</div>"
    )
    html_content = _render_base(content, title=f"Post {post_id} replies")
    start_response("200 OK", [CONTENT_TYPE_HTML] + HEADERS)
    return [html_content]


@route(r"^/(?P<post_id>\d+)/topics/(?P<tag_name>[a-zA-Z0-9-]+)/?$")
def handle_post_tag_detail(environ, start_response, post_id, tag_name):
    """Handle post tag detail page"""
    post_id = int(post_id)

    tag = _get_post_tag(post_id, tag_name)
    if tag is None:
        start_response("404 Not Found", [CONTENT_TYPE_HTML])
        error_template = SafeTemplate(fetch_template("error.html"))
        content = error_template.substitute(
            {"message": f"Tag '{tag_name}' on post {post_id} not found."}
        )
        html_content = _render_base(content, title="404 Not Found")
        return [html_content]

    # Get the post data to access the author information
    try:
        post_data = _get_data(_get_post_index(post_id))
        post_author = post_data.get("author", "")
    except Exception as e:
        print(f"Could not find post {post_id}: {e}")
        start_response("404 Not Found", [CONTENT_TYPE_HTML])
        error_template = SafeTemplate(fetch_template("error.html"))
        content = error_template.substitute(
            {"message": f"Post {post_id} not found."}
        )
        html_content = _render_base(content, title="404 Not Found")
        return [html_content]

    claimed = tag["metadata"].get("claimed", {})
    earliest_claim_time = tag["metadata"].get("earliest_claim_time", 0)
    earned = claimed.get("udys", 0)

    post_tag_detail_template = SafeTemplate(fetch_template("post_tag_detail.html"))
    content = post_tag_detail_template.substitute(
        {
            "tag_json": json.dumps(tag, indent=2),
            "meter_max": tag["up"] + tag["down"],
            "percent": int(tag["best_rating"] * 100),
            "earned": earned,
            "earliest_claim_time": earliest_claim_time,
            "post_author": SafeString(post_author),
            **tag,
        }
    )

    # history, pagination = _list_data(
    #    _get_post_tag_historical_rewards_prefix(tag_name, post_id)
    # )
    html_content = _render_base(content, title=f"Post {post_id} tag: {tag_name}")
    start_response("200 OK", [CONTENT_TYPE_HTML] + HEADERS)

    return [html_content]


@route(r"^/(?P<post_id>\d+)/replies/(?P<reply_post_id>\d+)/?$")
def handle_post_reply_detail(environ, start_response, post_id, reply_post_id):
    """Handle post reply detail page"""
    post_id = int(post_id)
    reply_post_id = int(reply_post_id)

    reply = _get_post_reply(post_id, reply_post_id)

    # Get the reply post data to access the author information
    try:
        reply_post_data = _get_data(_get_post_index(reply_post_id))
        reply_author = reply_post_data.get("author", "")
    except Exception as e:
        print(f"Could not find reply post {reply_post_id}: {e}")
        reply_author = ""

    claimed = reply["metadata"].get("claimed", {})
    earliest_claim_time = reply["metadata"].get("earliest_claim_time", 0)
    earned = claimed.get("udys", 0)

    post_id = int(reply["tag_name"])
    reply_post_id = reply["id"]
    post_reply_detail_template = SafeTemplate(fetch_template("post_reply_detail.html"))
    content = post_reply_detail_template.substitute(
        {
            "reply_json": json.dumps(reply, indent=2),
            "meter_max": reply["up"] + reply["down"],
            "percent": int(reply["best_rating"] * 100),
            "post_id": post_id,
            "reply_post_id": reply_post_id,
            "reply_author": reply_author,
            "earned": earned,
            "earliest_claim_time": earliest_claim_time,
            **reply,
        }
    )

    # history, pagination = _list_data(
    #    _get_post_tag_historical_rewards_prefix(tag_name, post_id)
    # )
    html_content = _render_base(content, title=f"Post {post_id} reply: {reply_post_id}")
    start_response("200 OK", [CONTENT_TYPE_HTML] + HEADERS)
    return [html_content]


@route(r"^/(?P<post_id>\d+)/topics/?$")
def handle_post_topics(environ, start_response, post_id):
    """Handle post topics list page"""
    post_id = int(post_id)

    req_pagination = _parse_pagination(environ, reverse=True, default_limit=2)
    tags, pagination = _get_best_tags_by_post_id(post_id, pagination=req_pagination)

    items_html = "".join(
        [
            f"""
<li><a
    title="{tag['tag_name']}"
    href="/{post_id}/topics/{tag['tag_name']}"
    class="text-blue-600 hover:text-blue-800 transition-colors"
    >{tag['tag_name']}</a></li>
"""
            for tag in tags
        ]
    )

    # There is a bug where if the pagination limit is equal to the number of returned items Storage assumes there
    # are more items and returns a key to paginate but the next page is empty. So in this case we only show
    # "No tags found" if there are no tags and no pagination key (which means we're on the first page)
    if not tags and not req_pagination.get("key"):
        items_html = "<li>No tags found</li>"

    if pagination.get("next_key"):
        # create the 'load more' link
        load_more_html = f"""
<li
  hx-get="/{post_id}/topics?limit={req_pagination['limit']}&key={pagination['next_key']}"
  hx-trigger="revealed once"
  hx-swap="outerHTML"
  hx-select="li"
  hx-target="this"
>load more tags... </li>"""
    else:
        load_more_html = ""

    post_topics_template = SafeTemplate(fetch_template("post_topics.html"))
    content = post_topics_template.substitute(
        {
            "post_id": post_id,
            "items_html": SafeString(items_html),
            "load_more_html": SafeString(load_more_html),
        }
    )

    start_response("200 OK", [CONTENT_TYPE_HTML] + HEADERS)

    html_content = _render_base(content, title=f"Post {post_id} tags")
    return [html_content]


@route(r"^/topics/(?P<tag_name>\w+)/?$")
def handle_topic_redirect(environ, start_response, tag_name):
    """Handle topic redirect to hot posts"""
    start_response("302 Moved", [("Location", f"/topics/{tag_name}/hot")])
    return []


@route(r"^/topics/(?P<tag_name>\w+)/(?P<sortby>hot|best)/?$")
def handle_topic_posts(environ, start_response, tag_name, sortby):
    """Handle topic posts list page"""
    req_pagination = _parse_pagination(environ, reverse=True, default_limit=2)
    if sortby == "hot":
        prefix = _get_rating_rate_prefix("tags", tag_name, "hot")
        links = f'<span>Hot</span> | <a href="/topics/{tag_name}/best">Best</a>'
    elif sortby == "best":
        prefix = _get_rating_rate_prefix("tags", tag_name, "best")
        links = f'<a href="/topics/{tag_name}/hot">Hot</a> | <span>Best</span>'
    else:
        raise Exception("not found")

    links += f'| <a href="/topics/{tag_name}/stats">Statistics</a>'

    posts, pagination = _list_data(prefix, pagination=req_pagination)

    # Generate HTML for the list of posts
    posts_html = "\n".join(
        [
            f"""
<div>
  <article
      hx-trigger="revealed once"
      hx-get="/{post['id']}?depth=0"
      hx-select="article"
      hx-swap="outerHTML ignoreTitle:true"
      hx-target="this"
      >Loading {post['id']}...</article>
</div>
            """
            for post in posts
        ]
    )

    if pagination.get("next_key"):
        # Create the 'load more' placeholder
        load_more_html = f"""
<div
  hx-get="?limit={req_pagination['limit']}&key={pagination['next_key']}"
  hx-trigger="revealed once"
  hx-swap="outerHTML"
  hx-select="main > div"
  hx-target="this"
>Load more posts... </div>"""
    else:
        load_more_html = "<div>Fin.</div>"

    reward_index = _get_tag_index(TAGS, tag_name)

    try:
        rewards = _get_data(reward_index)
    except Exception as e:
        # dict of {denom: amount}
        print(f"Tag rewards not found: {e}")
        rewards = {}
    reward_html = f"""
    | Rewards available: <strong>{rewards.get("available", {}).get("udys", 0) // 1000000} DYS</strong>
    | Rewards claimed: <strong>{rewards.get("claimed", {}).get("udys", 0) // 1000000} DYS</strong>
     """

    post_list_template = SafeTemplate(fetch_template("post_list.html"))
    content = post_list_template.substitute(
        {
            "header": SafeString(
                f'<h1 style="text-transform: capitalize;">{tag_name}</h1>'
                + links
                + reward_html
            ),
            "posts": SafeString(
                f"""
    <style>
        a[title="{tag_name}"] {{
            font-weight: bold
        }}
    </style>
    """
                + posts_html
                + load_more_html
            ),
        }
    )
    start_response("200 OK", [CONTENT_TYPE_HTML] + HEADERS)

    html_content = _render_base(content, title=f"Posts tagged: {tag_name}")

    return [html_content]


@route(r"^/topics/(?P<tag_name>\w+)/stats/?$")
def handle_topic_stats(environ, start_response, tag_name):
    """Handle topic statistics page"""
    topic_stats_template = SafeTemplate(fetch_template("topic_stats.html"))
    content = topic_stats_template.substitute({"tag_name": tag_name})
    html_content = _render_base(content, title="Topic Stats")
    start_response("200 OK", [CONTENT_TYPE_HTML] + HEADERS)
    return [html_content]

@whitelabel_route(r"^/static/(?P<file_path>.+)$")
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

# Must be regitsted after statick because is a wildcard route
whitelabel_route(r"^/(?P<path>.*[^/])/?$", author=name)(handle_author_page)


@route(r"^/sw\.min\.js$")
def handle_service_worker(environ, start_response):
    """Handle service worker file"""
    start_response("200 OK", [CONTENT_TYPE_JS, ("Cache-Control", "max-age=0, public")])
    return [
        """
(()=>{"use strict";let e=!1;self.addEventListener("install",(()=>{self.skipWaiting()})),self.addEventListener("fetch",(s=>{const t=(s=>{const{url:t}=s.request;return t.includes(self.registration.scope+"webtorrent/")?t.includes(self.registration.scope+"webtorrent/keepalive/")?new Response:t.includes(self.registration.scope+"webtorrent/cancel/")?new Response(new ReadableStream({cancel(){e=!0}})):async function({request:s}){const{url:t,method:n,headers:o,destination:a}=s,l=await clients.matchAll({type:"window",includeUncontrolled:!0}),[r,i]=await new Promise((e=>{for(const s of l){const l=new MessageChannel,{port1:r,port2:i}=l;r.onmessage=({data:s})=>{e([s,r])},s.postMessage({url:t,method:n,headers:Object.fromEntries(o.entries()),scope:self.registration.scope,destination:a,type:"webtorrent"},[i])}}));let c=null;const d=()=>{i.postMessage(!1),clearTimeout(c),i.onmessage=null};return"STREAM"!==r.body?(d(),new Response(r.body,r)):new Response(new ReadableStream({pull:s=>new Promise((t=>{i.onmessage=({data:e})=>{e?s.enqueue(e):(d(),s.close()),t()},e||(clearTimeout(c),"document"!==a&&(c=setTimeout((()=>{d(),t()}),5e3))),i.postMessage(!0)})),cancel(){d()}}),r)}(s):null})(s);t&&s.respondWith(t)})),self.addEventListener("activate",(()=>{self.clients.claim()}))})();

            """.encode()
    ]


def _render_base(body: str, title: str, head_extra: str = "", **kwargs) -> bytes:
    """Render base.html with integrity context and supplied main HTML."""

    return (
        SafeTemplate(fetch_template("base.html"))
        .substitute(
            {
                "body": SafeString(body),
                "BASE_DOMAIN": get_base_domain(),
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
                "title": title,
                "head_extra": head_extra,
                "script_address": get_script_address(),
                "script_version": get_script_version(),
                **kwargs,
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
    css_res = _query(
        {
            "@type": "/dysonprotocol.storage.v1.QueryStorageGetRequest",
            "owner": get_script_address(),
            "index": "static/css/style.css",
        }
    )
    hash_value = css_res["entry"]["hash"]
    return SafeString(f' integrity="{hash_value}"')
