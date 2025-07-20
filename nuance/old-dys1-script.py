from dys import _chain, SCRIPT_ADDRESS, get_caller, BLOCK_INFO, get_coins_sent
from datetime import datetime, timedelta
from decimal import Decimal
import math
import json

import typing
import html
from string import Template
from urllib.parse import parse_qsl

try:
    import re2 as re  # Only re2 is available onchain
except:
    import re


# Typing to specify that TEXTAREA is a formatted string, used for content submission
TEXTAREA = typing.Annotated[str, '{"format":"textarea"}']

# Regex to idetify an embedded post as /post_id on it's own line
POST_RE = r"(?:^\n*?|\n+?)/(\d+)(#[^\s]+)?(?:\n*?$|\n+?)"

# The soonest a post rewards can be claimed again for a specific tag
CLAIM_WAIT_SEC = 60 * 60 * 24  # 24hrs


def _get_reply_index(replied_to_post_id: int, post_id: int) -> str:
    return f"replies/{_format_id(replied_to_post_id)}/from/{_format_id(post_id)}"


def _get_replies_prefix(post_id: int) -> str:
    return f"replies/{_format_id(post_id)}/from/"


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
        name_resp = _chain("names/QueryName", name=author)
        assert not name_resp["error"], f"Dys name [{author}] not found."
        name_data = name_resp["result"]["name"]
        assert get_caller() in [
            name_data["owner"],
            name_data["destination"],
        ], f'[{get_caller()}] is not the owner[{name_data["owner"]}] or destination[{name_data["destination"]}] of "{author}"'

    # set the author to either the name or the caller or test name for preview
    author = author or get_caller()
    post_id = _get_next_id("posts")  # fetch the next available post id

    # find all replies to other posts in the content using regular expression
    replies_to = {}
    replied_to_posts = re.findall(POST_RE, content)
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
    post_data = {
        "post_id": post_id,
        "author": author,
        "content": content,
        "created_height": BLOCK_INFO.height,
        "created_time": BLOCK_INFO.time,
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
            name_data = _chain("names/QueryName", name=name)["result"]["name"]
            assert get_caller() in [name_data["owner"], name_data["destination"]]
        except Exception as e:
            raise Exception(
                f'[{get_caller()}] is not the owner or destination of the author "{name}"'
            )

    post["content"] += content
    post["updated_height"] = BLOCK_INFO.height
    post["updated_time"] = str(datetime.now())
    _store_data(_get_post_index(post_id), post_data)


def edit_author_profile(content: TEXTAREA, author: str = ""):

    author = author.strip()
    if author != get_caller():
        # query the blockchain to retrieve the owner of the provided name
        try:
            name_data = _chain("names/QueryName", name=author)["result"]["name"]
            assert get_caller() in [name_data["owner"], name_data["destination"]]
        except Exception as e:
            raise Exception(
                f'[{get_caller()}] is not the owner or destination of "{name}"'
            )

    profile_data = _get_profile(author)
    profile_data["content"] = content
    _store_data(_get_author_profile_index(author), profile_data)


def _get_next_id(key: str):
    index = _get_next_id_index(key)
    # Query the blockchain for the current ID and increment it
    res = _chain("dyson/QueryStorage", index=f"{SCRIPT_ADDRESS}/{index}")
    next_id = int(res["result"]["storage"]["data"]) if res["error"] is None else 1
    _store_data(index, next_id + 1)  # Store the updated ID back on the blockchain
    return next_id


def _store_data(index: str, data):
    result = _chain(
        "dyson/sendMsgUpdateStorage",
        creator=SCRIPT_ADDRESS,
        index=f"{SCRIPT_ADDRESS}/{index}",
        data=json.dumps(data),  # Data is stored in JSON format
        force=True,  # Force ensures that data overwrites any existing entry
    )
    assert result["error"] is None, f"Error storing data: {result['error']}"


def _get_data(index: str):
    result = _chain("dyson/QueryStorage", index=f"{SCRIPT_ADDRESS}/{index}")
    assert result["error"] is None, f"Error retrieving data: {result['error']}"
    return json.loads(
        result["result"]["storage"]["data"]
    )  # Return the parsed JSON data


def _list_data(prefix: str, **kwargs):
    result = _chain(
        "dyson/QueryPrefixStorage", prefix=f"{SCRIPT_ADDRESS}/{prefix}", **kwargs
    )
    assert result["error"] is None, f"Error listing data: {result['error']}"
    return (
        [
            {"_index": item["index"], **json.loads(item["data"])}
            for item in result["result"]["storage"]
        ],
        result["result"]["pagination"],
    )


def _delete_data(index: str):
    result = _chain(
        "dyson/sendMsgDeleteStorage",
        creator=SCRIPT_ADDRESS,
        index=f"{SCRIPT_ADDRESS}/{index}",
    )
    assert result["error"] is None, f"Error deleting data: {result['error']}"


def _best_rating(up: int, down: int, confidence: float = 0.95, **kwargs) -> float:
    """Calculate Wilson score with a given confidence level."""
    n = up + down
    if n == 0:
        return 0.0  # No rates, return default score

    z = 1.96  # Z-score for 95% confidence
    p = up / n
    z2 = z ** 2

    # Wilson score lower bound
    score = (
        p + (z2 / (2 * n)) - z * math.sqrt((p * (1 - p) / n) + (z2 / (4 * n ** 2)))
    ) / (1 + (z2 / n))

    return round(score, 5)


NEWNESS_BOOST = 2


def _hot_rating(up, down, created_timestamp, **kwargs):
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


def _get_next_id_index(key: str) -> str:
    return f"next_id/{key}"


################
###  Rating  ###
################
import typing


def validate_tag_name(tag_name: str) -> bool:
    return tag_name.isalnum()


def rate_tag(
    tag_name: str,
    post_id: int,
    rate: typing.Literal["up", "down"],
    contributor: str = "",
):

    assert len(tag_name) <= 15, f"Tag is too long (max 15): {len(tag_name)}"
    coins = get_coins_sent()
    assert (
        len(coins) == 1 and coins[0]["denom"] == "dys"
    ), f"Invalid coins, must send dys and only dys, sent: {coins}"
    coins[0]["amount"] = int(coins[0]["amount"])
    amount = coins[0]["amount"]

    try:
        rate_index = _get_rate_index("tags", tag_name, post_id)
        rate_data = _get_data(rate_index)
    except AssertionError:
        # Post Tag doesn't exist, maybe the author is adding it.
        post = _get_data(_get_post_index(post_id))

        author = post["author"]
        # ensure that only the post author or the owner of the author's name can tag the post
        if author != get_caller():
            try:
                name_data = _chain("names/QueryName", name=author)["result"]["name"]
                assert get_caller() in [name_data["owner"], name_data["destination"]]
            except Exception as e:
                raise Exception(
                    f"Nonexistant tag[{tag_name}] for post_id[{post_id}] and only the author[{post['author']}] can add new tags not you[{get_caller()}]"
                )
    _rate("tags", tag_name, post_id, rate, amount, contributor=contributor)


def rate_reply(post_id: int, reply_post_id: int, rate: str):

    reply_post_id = int(reply_post_id)
    post_id = int(post_id)
    coins = get_coins_sent()
    assert (
        len(coins) == 1 and coins[0]["denom"] == "dys"
    ), f"Invalid coins, must send dys and only dys, sent: {coins}"
    coins[0]["amount"] = int(coins[0]["amount"])
    amount = coins[0]["amount"]

    try:
        rate_index = _get_rate_index("replies", _format_id(post_id), reply_post_id)
        rate_data = _get_data(rate_index)
    except AssertionError:
        raise Exception(
            f"Nonexistant reply for post_id[{post_id}] and reply post_id[{reply_post_id}]"
        )

    _rate("replies", _format_id(post_id), reply_post_id, rate, amount)


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
    except AssertionError:

        rate_data = {
            "namespace": namespace,
            "tag_name": tag_name,
            "id": id,
            "up": 0,
            "down": 0,
            "best_rating": 0,
            "hot_rating": 0,
            "created_height": BLOCK_INFO.height,
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
    except AssertionError:
        data = {}

    # delete old reverse index
    for denom, amount in data.items():
        try:
            _delete_data(
                _get_reverse_contributor_index(
                    namespace, tag_name, denom, amount, contributor
                )
            )
        except AssertionError:
            pass

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


def _get_available_rate_index(namespace: str, tag_name: str, available: int) -> str:
    return f"/available/{namespace}/{available:012}/{tag_name}"


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
    except AssertionError:
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
    except AssertionError:
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
    except AssertionError:
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
    except AssertionError:
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
            "hot_rating": rate_data["best_rating"],
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


def claim_reply_rewards(post_id: str, hot_index: int):
    return _claim_rewards(_format_id(post_id), hot_index, REPLIES)


def claim_tag_rewards(tag_name: str, hot_index: int):
    return _claim_rewards(tag_name, hot_index, TAGS)


def _claim_rewards(tag_name: str, hot_index: int, namespace: str):
    prefix = _get_rating_rate_prefix(namespace, tag_name, "hot")
    hot_post, pagination = _list_data(
        prefix, pagination={"offset": hot_index, "limit": 1, "reverse": True}
    )
    assert (
        10 > hot_index
    ), f"Only the top 10 hot posts can claim rewards, index [{hot_index}] is too low."
    assert (
        len(hot_post) == 1
    ), f"Index[{hot_index}] hot post for tag[{tag_name}] not found." + json.dumps(
        hot_post, indent=2
    )
    hot_post = hot_post[0]
    post_index = _get_post_index(hot_post["id"])
    post = _get_data(post_index)  # retrieve the post data
    author = post["author"]

    # ensure that only the post author or the owner of the author's name can claim the rewards
    if author != get_caller():
        try:
            name_data = _chain("names/QueryName", name=author)["result"]["name"]
            assert get_caller() in [name_data["owner"], name_data["destination"]]
        except Exception as e:
            raise Exception(
                f'[{get_caller()}] is not the owner or destination or the author "{author}"'
            )

    reward_index = _get_tag_index(namespace, tag_name)
    try:
        rewards = _get_data(reward_index)
    except AssertionError:
        raise Exception("no rewards available")
    _delete_rewards_indexes(namespace, rewards)

    tag_data = _get_post_tag(post["post_id"], tag_name, namespace=namespace)
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

        result = _chain(
            "cosmos.bank.v1beta1/sendMsgSend",
            from_address=SCRIPT_ADDRESS,
            to_address=get_caller(),
            amount=[{"amount": str(reward_amount), "denom": denom}],
        )
        assert result["error"] is None, f"Error sending coins: {result['error']}"

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
        _store_data(
            _get_post_tag_historical_rewards_prefix(
                tag_name, post["post_id"], BLOCK_INFO.time, namespace=namespace
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
    tag_name: str = None,
    post_id: int = None,
    time: str = None,
    author: str = "",
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
        try:
            name_data = _chain("names/QueryName", name=contributor)["result"]["name"]
            assert get_caller() in [
                name_data["owner"],
                name_data["destination"],
                contributor,
            ]
        except Exception as e:
            raise Exception(
                f"[{get_caller()}] is not the owner or destination of the contributor name: {contributor}"
            )
    index = _get_tag_index(namespace, tag_name)

    try:
        rewards = _get_data(index)
    except Exception as e:
        # dict of {denom: amount}
        rewards = {"available": {}, "claimed": {}, "tag_name": tag_name}

    _delete_rewards_indexes(namespace, rewards)
    for coin in coins:
        rewards["available"][coin["denom"]] = rewards["available"].get(
            coin["denom"], 0
        ) + int(coin["amount"])
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
        except AssertionError:
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

from string import Template

# Constants for content type
CONTENT_TYPE_HTML = ("Content-Type", "text/html; charset=UTF-8")
CONTENT_TYPE_JS = ("Content-Type", "application/javascript; charset=utf-8")
HEADERS = [
    ("Cache-Control", "max-age=60, public"),
    ("Service-Worker-Allowed", "/"),
    # /("Content-Security-Policy-Report-Only", "default-src 'none'"),
    (
        "Content-Security-Policy",
        "script-src * 'unsafe-eval' 'unsafe-inline'; worker-src *; img-src 'self' data:",
    ),
]


def _parse_pagination(environ, reverse=False, default_limit=None):

    pagination = {
        k: v
        for k, v in parse_qsl(environ.get("QUERY_STRING", ""))
        if k in ["reverse", "offset", "limit", "key"]
    }

    if reverse:
        pagination["reverse"] = not (
            str(pagination.get("reverse", False)).lower() in ["1", "t", "true"]
        )

    if "limit" not in pagination and default_limit is not None:
        pagination["limit"] = default_limit

    return pagination


# Define HTML templates
BASE_TEMPLATE = Template(
    r"""<!DOCTYPE html>
<html>
<head>
  <title>$title</title>
  <meta name="viewport" content="width=device-width, initial-scale=1" />

  <link rel="stylesheet" href="https://latex.vercel.app/style.min.css" />

  <script
    src="https://unpkg.com/htmx.org@2.0.3"
    integrity="sha384-0895/pl2MU10Hqc6jd4RvrthNlDiE9U1tWmX7WRESftEDRosgxNsQG/Ze9YMRzHq"
    crossorigin="anonymous"
  ></script>
  <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/dompurify/dist/purify.min.js"></script>

  <link
    rel="stylesheet"
    href="https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@11.9.0/build/styles/default.min.css"
  />
  <script src="https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@11.9.0/build/highlight.min.js"></script>
  <link href="https://vjs.zencdn.net/8.16.1/video-js.css" rel="stylesheet" />
  <script src="https://vjs.zencdn.net/8.16.1/video.min.js"></script>

  <script>
    async function setupTorrentLinks(inputString) {
      //var magnetRegex = /magnet:\?xt=urn:btih:([a-zA-Z0-9]+)/g;
      var magnetRegex = /magnet:\?xt=urn:btih:([a-zA-Z0-9&=+%;._-]+)/g;

      // Replace each magnet link with the button
      var replacedString = inputString.replace(magnetRegex, function (match) {
        match = decodeHtml(match);
        const u = URL.parse(match);
        console.log(match, u);
        return `
        <div>
            <a href="$${match}">$${u.searchParams.get("dn") || u.searchParams.get("xt")}</a>
            <button data-magnet="$${match}" onclick="handleDownload(this)">Load metadata</button>
            <label>
            <input type="checkbox" class="auto-save" name="autoDownloadMeta" onclick="if (this.checked) this.parentElement.previousElementSibling.click()" />
                Auto
            </label>
            <div class="filelist"></div>
        </div>

            `;
      });

      return replacedString;
    }
  </script>

  <script>
    const clientOpts = {
      announce: ["wss://tracker.openwebtorrent.com"],
      deselect: true,
      destroyStoreOnDestroy: false,
      alwaysChokeSeeders: false,
      addUID: true,
      skipVerify: false,
      maxWebConns: 4,
    };

    async function getClient() {
      if (!window.WebTorrent) {
        console.log("Loading WebTorrent...");
        window.WebTorrent = (
          await import(
            "https://cdn.jsdelivr.net/gh/webtorrent/webtorrent@d40616f/dist/webtorrent.min.js"
          )
        ).default;
      }
      if (!window.client) {
        window.client = new WebTorrent();
        await registerWorker(window.client);
      }

      return window.client;
    }

    async function registerWorker(client) {
      return new Promise(async function (resolve) {
        if (!window.worker) {
          const reg = await navigator.serviceWorker.register("/sw.min.js", {
            scope: "./",
          });

          window.worker = reg.active || reg.waiting || reg.installing;
          function checkState(worker) {
            console.log("checkState", worker.state, worker);
            return (
              worker.state === "activated" &&
              client.createServer({ controller: reg }) &&
              resolve(window.worker)
            );
          }
          if (!checkState(window.worker)) {
            worker.addEventListener("statechange", ({ target }) =>
              checkState(target),
            );
          }
        }
      });
    }
  </script>
  <script>
    async function handleDownload(el) {
      const button = el.parentElement.parentElement.querySelector("button");
      if (button.disabled) return;
      button.disabled = true;

      button.textContent = "Loading...";
      const holder = el.parentElement.parentElement.querySelector(".filelist");

      const magnetLink = button.getAttribute("data-magnet");
      console.log("handleDownload", magnetLink);

      const client = await getClient();
      if (await client.get(magnetLink)) {
        console.log("not adding dup:", magnetLink);
        return;
      }
      clientOpts.deselect = localStorage.getItem("autoDownload") != "true";

      const torrent = client.add(magnetLink, clientOpts, (torrent) => {
        console.log("Torrent added:", torrent.name);
      });

      // Initialize progress display
      const progressElement = document.createElement("div");
      progressElement.innerHTML = `
          <span class="download-status">Loading metadata...</span> | </strong> <span class="overall-progress">0%</span> | <span class="download-speed">0 bytes/sec</span> <button>Select All</button> 
          <label><input type="checkbox" class="auto-save" name="autoDownload" onclick="if (this.checked) this.parentElement.previousElementSibling.click()" />
            Auto
          </label>

        `;
      holder.appendChild(progressElement);
      initAutoSave(holder);

      const filesContainer = document.createElement("div");
      holder.appendChild(filesContainer);

      progressElement.querySelector("button").onclick = (e) => {
        filesContainer
          .querySelectorAll("input[type=checkbox]")
          .forEach((el) => {
            if (!el.checked) {
              el.click();
            }
          });
      };

      function updateFile(file) {
        const fileClass = encodeURIComponent(file.path);
        const fileElement = filesContainer.getElementsByClassName(fileClass)[0];
        const progress = (file.progress * 100).toFixed(2);
        fileElement.querySelector(".status").textContent =
          `Progress: $${progress}%`;
      }
      function updateProgress() {
        // Update overall progress and download speed
        holder.querySelector(".overall-progress").textContent =
          (torrent.progress * 100).toFixed(0) + "%";
        holder.querySelector(".download-speed").textContent =
          torrent.downloadSpeed.toFixed(0).toLocaleString() + " bytes/sec";
      }

      torrent.on("download", () => {
        updateProgress();
        // Update individual file progress
        torrent.files.forEach(updateFile);
      });

      torrent.on("upload", () => {
        updateProgress();
        // Update individual file progress
        torrent.files.forEach(updateFile);
      });

      torrent.on("metadata", () => {
        updateProgress();
        console.log("Metadata retrieved for:", torrent.name, torrent);

        torrent.files.forEach((file) => {
          const fileClass = encodeURIComponent(file.path);
          console.log("Adding file ui:", file.path);
          const fileElements = filesContainer.getElementsByClassName(fileClass);
          var fileElement
          if (fileElements.length) {
             fileElement = fileElements[0];
          } else {
             fileElement = document.createElement("div");
            fileElement.classList.add(fileClass);

            fileElement.innerHTML = `
          <input type="checkbox"><a href="$${file.streamURL}" target="_blank"> $${file.path} </a> | $${file.type} | $${file.size} bytes
         <span class="status"></status>
          `;
            filesContainer.appendChild(fileElement);
          }
          const toggle = fileElement.querySelector("input");
          if (localStorage.getItem("autoDownload") == "true") {
            toggle.checked = true;
            file.select();
          }
          toggle.onchange = (event) => {
            console.log("Toggled:", file.path, event.target.checked);
            if (event.target.checked) {
              file.select();
            } else {
              file.deselect();
            }
          };

          updateFile(file);

          file.on("done", () => {
            updateProgress();
            updateFile(file);
            console.log("Done:", file.name);

            if (file.type.includes("video/")) {
              const videoElement = document.createElement("video");
              videoElement.setAttribute("controls", "true");
              videoElement.className = "video-js";
              videoElement.dataset.setup = "{}";
              //fileElement.innerHTML = "";
              fileElement.appendChild(videoElement);
              file.streamTo(videoElement);
            } else if (file.type.includes("image/")) {
              const imgElement = document.createElement("img");
              imgElement.style = "max-width: 300px; max-height: 300px;";
              //fileElement.innerHTML = "";
              fileElement.insertBefore(imgElement, fileElement.firstChild);
              file.streamTo(imgElement);
            }
          });
        });
      });

      torrent.on("done", () => {
        console.log("Torrent finished downloading");
        updateProgress();
        holder.querySelector(".download-status").textContent = "Finished";
      });

      torrent.on("warning", (err) => {
        console.error("Torrent warning:", err.message);
      });

      torrent.on("error", (err) => {
        console.error("Torrent error:", err.message);
        holder.querySelector(".download-status").textContent = err.message;
      });

      return torrent;
    }
  </script>
  <script id="mainScript">
    function decodeHtml(html) {
      var txt = document.createElement("textarea");
      txt.innerHTML = html;
      return txt.value;
    }

    // Function to render markdown, LaTeX, and highlight the element
    async function renderMarkdownAndHighlight(el, optionalHash) {
      try {
        // Render markdown if necessary
        if (el.classList.contains("markdown")) {
          el.childNodes.forEach(async function (child) {
            if (child.nodeType === 3) {
              const rawHtml = marked.parse(child.textContent);

              const cleanHtml = DOMPurify.sanitize(rawHtml, {
                ALLOWED_TAGS: [
                  "a",
                  "b",
                  "blockquote",
                  "code",
                  "em",
                  "h1",
                  "h2",
                  "h3",
                  "h4",
                  "h5",
                  "h6",
                  "hr",
                  "i",
                  "li",
                  "ol",
                  "p",
                  "pre",
                  "span", // Allow span for MathJax rendering
                  "strong",
                  "table",
                  "tbody",
                  "td",
                  "th",
                  "thead",
                  "tr",
                  "ul",
                ],
                ALLOWED_ATTR: ["href", "title", "class", "id", "style"],
              });

              const newElement = document.createElement("div");
              newElement.innerHTML = await setupTorrentLinks(cleanHtml);
              child.replaceWith(newElement);
              initAutoSave(newElement);
            }
          });
          el.classList.remove("markdown");

          // Skip the main content but make all other markdown collapsible if too tall
          if (el.parentNode.parentNode.id !== "content") {
            const rect = el.getBoundingClientRect();
            if (rect.height > 300) {
              el.classList.add("small");
              el.addEventListener("click", function (event) {
                el.classList.remove("small");
                el.style.maxHeight = null;
                el.removeEventListener("click", arguments.callee);
              });
            }
          }
        }

        // Highlight the element if data-fragment or optionalHash is provided
        let hash = optionalHash;
        if (!hash) {
          hash = el.getAttribute("data-fragment");
          el.removeAttribute("data-fragment");
        }

        if (hash) {
          const utils = await import(
            "https://unpkg.com/text-fragments-polyfill@5.7.0/src/text-fragment-utils.js"
          );

          const originalParent = el.parentNode;
          const originalNextSibling = el.nextSibling;

          const newDocument =
            document.implementation.createHTMLDocument("New Document");
          newDocument.body.appendChild(el);

          const processedText = utils.processFragmentDirectives(
            utils.parseFragmentDirectives(utils.getFragmentDirectives(hash)),
            newDocument,
          );

          if (originalNextSibling) {
            originalParent.insertBefore(el, originalNextSibling);
          } else {
            originalParent.appendChild(el);
          }

          if (el.classList.contains("small")) {
            const smallElement = el;
            const markElements = smallElement.querySelectorAll("mark");

            if (markElements.length > 0) {
              const firstMarkRect = markElements[0].getBoundingClientRect();
              const lastMarkRect =
                markElements[markElements.length - 1].getBoundingClientRect();
              const smallRect = smallElement.getBoundingClientRect();

              const totalHeightRequired =
                lastMarkRect.bottom - firstMarkRect.top + 100;

              smallElement.style.maxHeight = totalHeightRequired + "px";

              const offset = firstMarkRect.top - smallRect.top - 50;
              smallElement.scrollTop += offset;
            }
          }

          return processedText.text;
        }
      } catch (error) {
        console.error("Error in renderMarkdownAndHighlight:", error);
      }
      hljs.highlightAll();
    }

    function debounce(delay, func, immediate = false) {
      let timeout;

      return function (...args) {
        const context = this;

        const later = () => {
          timeout = null;
          if (!immediate) func.apply(context, args);
        };

        const callNow = immediate && !timeout;

        clearTimeout(timeout);
        timeout = setTimeout(later, delay);

        if (callNow) func.apply(context, args);
      };
    }

    htmx.config.ignoreTitle = true;
  </script>

  <!-- Wallet -->
  <script defer>
        // Load dyson.js only if Keplr wallet is available
        if (!window.script) {
          const script = document.createElement("script");
          script.src = "/_/dyson.js";
          //script.src = "https://crants.dyson.lol/_/dyson.js";
          script.onload = onDysonLoad;
          script.onerror = () => console.error("Error loading dyson.js");
          document.head.appendChild(script);
        } else {
          console.log("Dyson.js already loaded");
        }

        const dysonLoadedEvent = new Event("dysonLoadedEvent");
        function onDysonLoad() {
          console.log("dyson.js loaded successfully");
          attemptAutoReconnect();
          document.dispatchEvent(dysonLoadedEvent);
        }

        const INITIAL_GAS_LIMIT = 10960000;
        let keplrAccount;
        let autoReconnect =
          JSON.parse(localStorage.getItem("autoReconnect")) || false;
        let txPending = false;

        const txSentEvent = new CustomEvent("transactionSent");
        const txFinishedEvent = new CustomEvent("transactionFinished");

        async function connectWallet() {
          try {
            if (!window.keplr)
              throw new Error("Please install and enable Keplr wallet");

            await DysonLoader();
            autoReconnect = true;
            localStorage.setItem("autoReconnect", JSON.stringify(autoReconnect));

            await dysonUseKeplr(accountChanged);
            document.body.classList.add("walletConnected");
          } catch (error) {
            alert("Error connecting wallet: " + error.message);
          }
        }

        function disconnectWallet() {
          accountChanged(null);
          autoReconnect = false;
          localStorage.setItem("autoReconnect", JSON.stringify(autoReconnect));
        }

        function accountChanged(newAccount) {
          keplrAccount = newAccount;
          document.body.classList.toggle("walletConnected", Boolean(newAccount));
          const accountChangedEvent = new CustomEvent("accountChangedEvent", {
            detail: { keplrAccount: keplrAccount },
          });
          document.dispatchEvent(accountChangedEvent);
        }

        async function attemptAutoReconnect() {
          if (autoReconnect && window.keplr) {
            await connectWallet();
          }
        }

        async function runFunction({
          functionName,
          args = [],
          kwargs = {},
          coins = [],
          gasLimit = INITIAL_GAS_LIMIT,
        }) {
          const command = "dyson/sendMsgRun";
          const feeAmount = Math.ceil(gasLimit / 10000).toString();
          const data = {
            value: {
              creator: keplrAccount.bech32Address,
              address: "crants.dys",
              function_name: functionName,
              kwargs: JSON.stringify(kwargs),
              args: JSON.stringify(args),
              coins: coins.map((item) => item.amount + item.denom).join(", "),
            },
            fee: [{ amount: feeAmount, denom: "dys" }],
            gas: gasLimit.toString(),
          };

          try {
            txPending = true;
            document.body.classList.add("txPending");
            document.dispatchEvent(txSentEvent);

            const result = await dispatchTransaction(command, data);

            console.log(result);
            alert("Transaction successful! Hash: " + result.transactionHash);
            return result.result;
          } catch (error) {
            alert("Error executing function: " + error.message);
            throw error;
          } finally {
            txPending = true;
            document.body.classList.remove("txPending");
          }
        }

        async function dispatchTransaction(command, data) {
          try {
            const response = await dysonVueStore.dispatch(command, data);

            if (command.includes("Query")) {
              return response;
            }
            if (response.code !== 0) {
              throw new Error(
                "Execution failed with code " +
                  response.code +
                  ": " +
                  response.rawLog,
              );
            }
            return parseResponse(response);
          } catch (error) {
            if (isOutOfGasError(error)) {
              const lastGas = parseInt(data.gas);
              const newGas = lastGas * 2;
              const retry = confirm(
                "Transaction failed due to insufficient gas. Last gas used: " +
                  lastGas +
                  ". Proposed new gas limit: " +
                  newGas +
                  ". Try again with more gas?",
              );
              if (retry) {
                data.gas = newGas.toString();
                data.fee[0].amount = Math.ceil(newGas / 10000).toString();
                return dispatchTransaction(command, data);
              }
            }
            throw new Error("Dispatch failed: " + error.message);
          }
        }

        function isOutOfGasError(error) {
          return error.message.includes("ErrorOutofGas");
        }

        function parseResponse(response) {
          const rawLog = JSON.parse(response.rawLog)[0];
          let responseKey;

          for (let event of rawLog.events) {
            for (let attribute of event.attributes) {
              if (attribute.key === "response") {
                responseKey = JSON.parse(attribute.value);
                break;
              }
            }
            if (responseKey) break;
          }

          return { transactionHash: response.transactionHash, ...responseKey };
        }

        function formatId(id) {
          return String(id).padStart(15, "0");
        }
        function getRateIndex(namespace, tagName, id) {
          return "rate_tags/" + namespace + "/" + tagName + "/" + formatId(id);
        }
        function getPostIndex(postId) {
          return "posts/" + formatId(postId);
        }
        function getTagRewardsIndex(tagName) {
          return "tag/tags/" + tagName;
        }
        function getReplyRewardsIndex(postId) {
          return "tag/replies/" + formatId(postId);
        }
        function getScoreRatePrefix(namespace, tagName, scoreType) {
          return "rate/" + namespace + "/" + tagName + "/" + scoreType + "/";
        }

        async function getData(index) {
          const response = await fetch(
            DYSON_PROTOCOL.API_COSMOS +
              "/dyson/storage?index=" +
              encodeURIComponent(DYSON_PROTOCOL.SCRIPT_ADDRESS + "/" + index),
          );

          const result = await response.json();

          if (result.error) {
            throw new Error("Error retrieving data: " + result.error);
          }

          return JSON.parse(result.storage.data); // Return the parsed JSON data
        }
        async function listData(prefix, options = {}) {
          const { pagination } = options;

          // Extract pagination parameters and set defaults if they don't exist
          const paginationParams = Object.fromEntries(
            Object.entries({
              "pagination.key": pagination?.key,
              "pagination.offset": pagination?.offset,
              "pagination.limit": pagination?.limit,
              "pagination.count_total": pagination?.count_total,
              "pagination.reverse": pagination?.reverse,
            }).filter(
              ([_, value]) =>
                value !== null && value !== undefined && value !== "",
            ),
          );

          // Create the query string using the pagination parameters
          const queryString = new URLSearchParams(paginationParams).toString();

          const response = await fetch(
            DYSON_PROTOCOL.API_COSMOS +
              "/dyson/storageprefix?prefix=" +
              encodeURIComponent(DYSON_PROTOCOL.SCRIPT_ADDRESS + "/" + prefix) +
              "&" +
              queryString,
          );

          const result = await response.json();

          if (result.error) {
            throw new Error("Error listing data: " + result.error);
          }

          const dataList = result.storage.map((item) => ({
            _index: item.index,
            ...JSON.parse(item.data),
          }));

          return {
            dataList,
            pagination: result.pagination,
          };
        }
        function hotRating(up, down, createdHeight) {
          // Calculate the hot rating
          const s = up - down;
          const order = Math.log1p(Math.abs(s)); // log1p calculates log(1 + s) for better precision
          const sign = Math.sign(s); // Determine the sign of s
          const timeUnits = (createdHeight - 30000000) / (24 * 60 * 60 * """
    + str(NEWNESS_BOOST)
    + """);

          return parseFloat((sign * order + timeUnits).toFixed(5));
        }
        async function resolveName(name) {
          const response = await fetch(
            DYSON_PROTOCOL.API_COSMOS +
              "/org/dyson/names/name?name=" +
              encodeURIComponent(name),
          );

          const result = await response.json();
          if (result.error) {
              return {owner: null, destination: null}
          }

          return result.name;
        }

        async function isWalletAuthor(author) {
          if (!author) {
            return false
          }
          const address = keplrAccount?.bech32Address;
          if (address === author) return true;
          let { owner, destination } = await resolveName(author);
          return address === owner || address === destination;
        }

        async function getPostPositionInHotPosts(postId, tagName) {
          const namespace = "tags";
          const { dataList } = await listData(
            getScoreRatePrefix(namespace, tagName, "hot"),
            { pagination: { reverse: true } },
          );
          const position = dataList.findIndex((post) => post.id == postId);
          return position;
        }
        async function getPostPositionInHotReplies(postId, replyPostId) {
          const namespace = "replies";
          const { dataList } = await listData(
            getScoreRatePrefix(namespace, formatId(postId), "hot"),
            { pagination: { reverse: true } },
          );
          const position = dataList.findIndex((post) => post.id == replyPostId);
          return position;
        }
  </script>

  <script>
    function initAutoSave(container = document) {
      console.log("initAutoSave", container);
      container.querySelectorAll(".auto-save").forEach((el) => {
        console.log("auto-save", el);
        const key = el.name;
        if (!key || el.dataset.autoSaveInitialized) return; // Skip if already initialized

        // Initialize value or checked state
        if (el.type === "checkbox") {
          if (localStorage.getItem(key) === "true") {
            el.click();
          }
          el.addEventListener("change", () => {
            console.log("autosave checkbox", el.name, el.checked);
            localStorage.setItem(key, el.checked);
          });
        } else {
          el.value = localStorage.getItem(key) || "";
          el.addEventListener("change", () => {
            console.log("autosave input", el.name, el.value);
            localStorage.setItem(key, el.value);
          });
        }

        el.dataset.autoSaveInitialized = "true"; // Mark as initialized
      });
    }

    // Run on initial page load
    window.addEventListener("load", () => initAutoSave());

    // Expose function for HTMX or other dynamic contexts
    document.addEventListener("htmx:afterSwap", (event) => {
      initAutoSave(event.target);
    });
  </script>

  <style>
    body {
      max-width: unset;
    }
    article {
      border: 1px solid;
      margin: 1em 0;
      overflow: auto;
      word-wrap: break-word;
      padding: 1em 1.5em;
    }
    article article {
      font-size: 0.9em;
    }
    .post-tag-list {
      display: inline;
      list-style: none;
      padding: 0;
    }

    .post-tag-list > li {
      display: inline;
    }

    .post-tag-list > li + li:before {
      content: ", ";
    }

    .small {
      cursor: pointer;
      max-height: 300px;
      overflow-y: auto;
      scroll-behavior: smooth;
    }
    .author {
      word-break: break-all;
    }
    a:hover {
      cursor: pointer;
    }
    meter {
      width: 100%;
      padding-left: 15px;
      margin-left: -15px;
    }

    #replies details:not([open]) {
      margin-bottom: -1em;
    }

    .active-info {
      margin-bottom: -1em;
    }

    .walletConnected .hideFromWallet {
      display: none;
    }
    body:not(.walletConnected) .showWithWallet {
      display: none;
    }
    header {
      overflow: hidden;
    }
    .logo {
      margin: 0;
      display: inline;
    }
  </style>
</head>

  <body class="latex-dark-auto">
    <header>
      <div>
        <a href="/"><h1 class="logo">Nuance</h1></a>
      </div>
      <div>
        <a href="/recent">Recent Posts</a> | <a href="/active">Active Posts</a> | <a href="/topics">Topics</a> | <a href="/blog">Blog</a>  <br> 
        <a href="/publish">Publish</a> |
        <a
          id="connectWalletButton"
          class="hideFromWallet"
          onclick="connectWallet()"
          >Connect Wallet</a
        >
        <span class="showWithWallet">
          <a id="walletAddressText" href=""></a> |
          <a id="disconnectWalletButton" onclick="disconnectWallet()" disabled>
            Disconnect
          </a>
        </span>
      </div>
    </header>
    <script>
      document.addEventListener("accountChangedEvent", (event) => {
        const address = event.detail.keplrAccount?.bech32Address;
        if (address) {
          document.getElementById("walletAddressText").innerText = address;
          document.getElementById("walletAddressText").href =
            "/authors/" + address;
        }
        document.getElementById("connectWalletButton").disabled = !!address;
        document.getElementById("disconnectWalletButton").disabled = !address;
      });
    </script>

    <main>$body</main>
  </body>
</html>
"""
)

POST_LIST_TEMPLATE = Template(
    """
$header
$posts
""".strip()
)

POST_DETAIL_TEMPLATE = Template(
    """
<div id="content">
  <h1>Post #$post_id</h1>
  <a href="#replies">Go to replies</a>
  <article class="">
    <header>
      <a href="/$post_id">Post #$post_id</a>
      by
      <a class="author" href="/authors/$author">$author</a>
      on
      <time datetime="$created_time">$created_time</time>
      <script>
        {
          let time = document.currentScript.previousElementSibling;
          time.innerText = new Date(
            time.getAttribute("datetime"),
          ).toLocaleString();
        }
      </script>
      has earned $claimed DYS |
      <a href="/$post_id/topics?limit=2">Topics</a>:
      <ol
        class="post-tag-list"
        hx-get="/$post_id/topics?limit=2"
        hx-swap="innerHTML"
        hx-trigger="revealed once"
        hx-select="li"
      >
        Loading tags...
      </ol>
    </header>

    <hr />
    <div class="markdown">$content</div>

    <script>
      renderMarkdownAndHighlight(
        document.currentScript.previousElementSibling,
        document.currentScript
          .closest("[data-fragment]")
          ?.getAttribute("data-fragment"),
      );
    </script>
  </article>
</div>



<div id="replies">
  <h1>Replies</h1>
  <a href="#content">Go to content</a>
  <hr />
  <div
    id="load-replies-${post_id}"
    hx-get="/$post_id/replies/?limit=2"
    hx-trigger="load"
    hx-swap="outerHTML ignoreTitle:true"
    hx-select="#reply-content"
  >
    Loading replies...
  </div>
</div>
""".strip()
)

ERROR_TEMPLATE = Template(
    """
<h1>$message</h1>
""".strip()
)


def _tag_list(environ, start_response):

    featured_tags, _ = _list_data(
        _available_reward_prefix(TAGS) + "dys/"  # hard code dys rewards for now
    )

    tags, pagination = _list_data(
        _get_tag_prefix(TAGS), pagination=_parse_pagination(environ)
    )

    featured_tags_content = (
        "<h2>Featured Topics</h2><ol>"
        + "\n".join(
            [
                f"""<li><a href="/topics/{html.escape(tag['tag_name']) }">{html.escape(tag['tag_name']) }</a> (Available: {tag['amount']} DYS) </li>"""
                for tag in featured_tags
            ]
        )
        + " </ol>"
    )
    tags_content = (
        "<h2>All Topics</h2><ul>"
        + "\n".join(
            [
                f"""<li><a href="/topics/{html.escape(tag['tag_name'])}">{html.escape(tag['tag_name'])}</a></li>"""
                for tag in tags
            ]
        )
        + "</ul>"
    )
    html_content = BASE_TEMPLATE.substitute(
        title="Topics", body=featured_tags_content + tags_content
    )

    start_response("200 OK", [CONTENT_TYPE_HTML] + HEADERS)
    return [html_content.encode()]


def _new_post(environ, start_response):
    body = dict(parse_qsl(environ.get("QUERY_STRING", "")))

    html_content = BASE_TEMPLATE.substitute(
        title="New Post",
        body=r"""
<div>
  <form id="postForm">
    <label>Content:
        <textarea id="post-content" class="auto-save"  name="content" rows="10"></textarea>
    </label>

  </form>
  <h1>Preview</h1>
  <hr />

  <div id="content">
    <article id="article-preview" class="markdown">
      <!-- Preview will be rendered here -->
    </article>

    <label>Author Name (optional):
        <input id="author" class="auto-save"  type="text" name="name" required />
    </label>
    <button type="button" id="postButton" disabled>Post Content</button>
  </div>

  <script>
    document.addEventListener("accountChangedEvent", (e) => {
      document.getElementById("postButton").disabled = !keplrAccount;
    });
    document.getElementById("postButton").addEventListener("click", () => {
      const content = document.getElementById("post-content").value;
      const author = document.getElementById("author").value;
      runFunction({
        functionName: "publish_post",
        kwargs: { content, author },
        gasLimit: 18960000,
      })
        .then((postId) => {
          localStorage.removeItem("content")
          location = postId;
        })
        .catch((e) => console.log("runFunction error", e));
    });

    const embedPosts = (contentText, depth) => {
      return contentText.replace(/(?:^\n*?|\n+?)\/(\d+)(#[^\s]+)?(?:\n*?$|\n+?)/gm, (match, p1, p2) => {
        //<(\d+)\s*(#[^\s]+)?>
        return `
        <div
          hx-trigger="load"
          hx-get="/${p1}?depth=${depth}"
          hx-select="article"
          hx-disinherit="hx-select"
          hx-swap="innerHTML ignoreTitle:true"
          data-fragment="${p2 || ""}"
        >
          Loading: ${p1} ...
        </div>
      `;
      });
    };

    const contentInput = document.getElementById("post-content");
    const previewDiv = document.getElementById("article-preview");

contentInput.addEventListener("input", debounce(800, () => {
    const isSmall = previewDiv.classList.contains("small")
    const content = contentInput.value;
    previewDiv.classList.add("markdown");
    previewDiv.innerHTML = embedPosts(content.replace(/&/g, '&amp;') .replace(/</g, '&lt;') .replace(/>/g, '&gt;'), 1);
    renderMarkdownAndHighlight(previewDiv);
    htmx.process(previewDiv); // Call htmx after rendering
    if (!isSmall) previewDiv.classList.remove("small");
}));

// Load content from local storage when the page loads
window.addEventListener("load", () => {
    previewDiv.innerHTML = embedPosts(contentInput.value, 1); // Update preview
    renderMarkdownAndHighlight(previewDiv); // Render the saved content
    htmx.process(previewDiv); // Call htmx after rendering
});

  </script>
</div>
""",
    )

    start_response("200 OK", [CONTENT_TYPE_HTML] + HEADERS)
    return [html_content.encode()]


def _tag_post_list(environ, start_response, tag_name: str, sortby="hot"):

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
      hx-disinherit="hx-select"
      hx-swap="outerHTML ignoreTitle:true"
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
>Load more posts... </div>"""
    else:
        load_more_html = "<div>Fin.</div>"

    reward_index = _get_tag_index(TAGS, tag_name)

    try:
        rewards = _get_data(reward_index)
    except Exception as e:
        # dict of {denom: amount}
        rewards = {}
    reward_html = f"""
    | Rewards available: <strong>{rewards.get("available", {}).get("dys", 0)} DYS</strong>
    | Rewards claimed: <strong>{rewards.get("claimed", {}).get("dys", 0)} DYS</strong>
     """

    content = POST_LIST_TEMPLATE.substitute(
        header=f'<h1 style="text-transform: capitalize;">{tag_name}</h1>'
        + links
        + reward_html,
        posts=f"""
    <style>
        a[title="{tag_name}"] {{
            font-weight: bold
        }}
    </style>
    """
        + posts_html
        + load_more_html,
    )

    html_content = BASE_TEMPLATE.substitute(
        title=f"Posts tagged: {tag_name}", body=content
    )
    start_response("200 OK", [CONTENT_TYPE_HTML] + HEADERS)
    return [html_content.encode()]


def _get_profile(author_name):
    try:
        return _get_data(_get_author_profile_index(author_name))
    except AssertionError:
        return {"content": "", "claimed": {}}


def _edit_author_profile(environ, start_response, author_name):
    profile_data = _get_profile(author_name)
    html_content = Template(
        """
    <div>
    <input id="author" name="author" value="$author_name" />
    <textarea id="post-content" name="content">$content</textarea>
    <button id="save" disabled>Save</button>
    <script>
      document.addEventListener("accountChangedEvent", (e) => {
        document.getElementById("save").disabled = !keplrAccount;
      });
      document.getElementById("save").addEventListener("click", () => {
        const content = document.getElementById("post-content").value;
        const author = document.getElementById("author").value;
        runFunction({
          functionName: "edit_author_profile",
          kwargs: { content, author },
        })
          .then((postId) => {
              // TODO: show something
          })
          .catch((e) => console.log("runFunction error", e));
      });
    </script>
    </div>
    """
    ).substitute(author_name=author_name, **profile_data)

    html_content = BASE_TEMPLATE.substitute(
        title=f"Edit profile: {author_name}", body=html_content
    )
    start_response("200 OK", [CONTENT_TYPE_HTML] + HEADERS)
    return [html_content.encode()]


def _author_post_list(environ, start_response, author_name):

    profile_data = _get_profile(author_name)

    req_pagination = _parse_pagination(environ, reverse=True, default_limit=2)
    posts, pagination = _list_data(
        _get_author_post_prefix(author_name), pagination=req_pagination
    )

    if pagination.get("next_key"):
        # Create the 'load more' placeholder
        load_more_html = f"""
<div
  hx-get="/authors/{author_name}?limit={req_pagination['limit']}&key={pagination['next_key']}"
  hx-trigger="revealed once"
  hx-swap="outerHTML"
  hx-select=".articleLoader""

>Load more posts... </div>"""
    else:
        load_more_html = "<div>Fin.</div>"

    # Generate HTML for the list of posts
    posts_html = "\n".join(
        [
            f"""
<div
  class="articleLoader"
  hx-trigger="revealed once"
  hx-get="/{post['post_id']}?depth=0"
  hx-select="article"
  hx-disinherit="hx-select"
  hx-swap="innerHTML ignoreTitle:true"
>
  <article>Loading {post['post_id']}...</article>
</div>
            """
            for post in posts
        ]
    )

    content = (
        f"""
        <div class="markdown">{profile_data['content']}</div>
        <script>
            renderMarkdownAndHighlight(document.currentScript.previousElementSibling)
        </script>
        <div>
        <h1>Posts by <span class="author">{author_name}</span></h1>
        <p>Total Earned: <strong>{profile_data.get("claimed", {}).get("dys",0) } DYS</strong></p>
        """
        + posts_html
        + load_more_html
        + "</div>"
    )

    html_content = BASE_TEMPLATE.substitute(title="Author Post List", body=content)
    start_response("200 OK", [CONTENT_TYPE_HTML] + HEADERS)
    return [html_content.encode()]


def _post_list(environ, start_response):

    req_pagination = _parse_pagination(environ, reverse=True, default_limit=2)
    posts, pagination = _list_data("posts/", pagination=req_pagination)

    if pagination.get("next_key"):
        # Create the 'load more' placeholder
        load_more_html = f"""
<div
  hx-get="/recent/?limit={req_pagination['limit']}&key={pagination['next_key']}"
  hx-trigger="revealed once"
  hx-swap="outerHTML"
  hx-select="main > div"
>Load more posts... </div>"""
    else:
        load_more_html = "<div>Fin.</div>"

    # Generate HTML for the list of posts
    posts_html = "\n".join(
        [
            f"""
<div
  hx-trigger="revealed once"
  hx-get="/{post['post_id']}?depth=0"
  hx-select="article"
  hx-disinherit="hx-select"
  hx-swap="innerHTML ignoreTitle:true"
>
  <article>Loading {post['post_id']}...</article>
</div>
            """
            for post in posts
        ]
    )

    content = POST_LIST_TEMPLATE.substitute(
        header="", posts=posts_html + load_more_html
    )

    html_content = BASE_TEMPLATE.substitute(title="Post List", body=content)
    start_response("200 OK", [CONTENT_TYPE_HTML] + HEADERS)
    return [html_content.encode()]


def _post_detail(environ, start_response, post_id):
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
        content = ERROR_TEMPLATE.substitute(message=f"Post {post_id} not found")
        html_content = BASE_TEMPLATE.substitute(title="404 Not Found", body=content)

        return [html_content.encode()]

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
                    hx-disinherit="hx-select"
                    hx-swap="innerHTML ignoreTitle:true"
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
                        hx-disinherit="hx-select"
                        hx-swap="innerHTML ignoreTitle:true"
                        hx-target ="closest div"
                    >
                    /\1\2
                    </a>
            </div>

""",
            content_text,
        )

    content = POST_DETAIL_TEMPLATE.substitute(
        post_id=post_id,
        author=author,
        content=content_text,
        created_time=post["created_time"],
        claimed=post.get("claimed", {}).get("dys", 0),
    )

    html_content = BASE_TEMPLATE.substitute(title=f"Post {post_id}", body=content)

    start_response("200 OK", [CONTENT_TYPE_HTML] + HEADERS)
    return [html_content.encode()]


def _get_tags_by_rating_prefix(post_id: int, rating_type: str) -> str:
    """Get the prefix for tags by score type ('best' or 'hot') for a specific post ID.

    Args:
        post_id (int): The ID of the post.
        rating_type (str): The score type ('best' or 'hot').

    Returns:
        str: The prefix for retrieving tags by score type for the given post ID.
    """
    return f"tags_by_post_id/{_format_id(post_id)}/{rating_type}/"


def _get_best_tags_by_post_id(post_id: int, **kwargs):
    prefix = _get_reverse_rating_prefix("tags", post_id, "best")
    return _list_data(prefix, **kwargs)


def _list_post_tags(environ, start_response, post_id):
    req_pagination = _parse_pagination(environ, reverse=True, default_limit=2)
    tags, pagination = _get_best_tags_by_post_id(post_id, pagination=req_pagination)
    items_html = "".join(
        [
            f"""
<li><a
    title="{tag['tag_name']}"
    href="/{post_id}/topics/{tag['tag_name']}"
    hx-get="/{post_id}/topics/{tag['tag_name']}"
    hx-target="next span"
    hx-select="form"
    hx-swap="innerHTML"
    >{tag['tag_name']}</a
  ><span></span></li>
"""
            for tag in tags
        ]
        or ["<li>none</li>"]
    )
    if pagination.get("next_key"):
        # create the 'load more' placeholder
        load_more_html = f"""
<li
  hx-get="/{post_id}/topics?limit={req_pagination['limit']}&key={pagination['next_key']}"
  hx-trigger="revealed once"
  hx-swap="outerHTML"
  hx-select="li"
>load more tags... </li
>"""
    else:
        load_more_html = ""

    content = (
        f"""
    <h2><a href="/{post_id}"> Post #{post_id}</a> tags</h2>

    <fieldset>
      <span>Note: Only the author of this post can add tags.</span>
      <legend>Add tag</legend>
      <div>
        <label for="tagName">Topic name</label>
        <input name="tagName" />
      </div>
      <div>
        <label for="amount">Amount in DYS</label>
        <input name="amount" type="number"  class="auto-save" />
      </div>
      <div>
        <label for="name" >(optional) Dys Name</label>
        <input name="name"  class="auto-save" />
      </div>
      <p>
      <button
        class="addBtn"
        onclick="rateTag('up',this.closest('fieldset').querySelector('input[name=tagName]').value, '{post_id}', this.closest('fieldset').querySelector('input[name=amount]').value,this.closest('fieldset').querySelector('input[name=name]').value )"
        disabled
      >
        Add tag
      </button>
          </p>
    </fieldset>
    <ol>
    """
        + items_html
        + load_more_html
        + """
        </ol>
        """
        + """
  <script>
    {
      // Set up a listener for account changes to toggle button disabled state across all elements.
      const setButtons = () => {
        const buttons = document.querySelectorAll(".addBtn");
        buttons.forEach((button) => {
          button.disabled = !keplrAccount;
        });
      };

      document.addEventListener("accountChangedEvent", setButtons);
      setButtons();

      function rateTag(rate, tagName, postId, amount, contributor) {
        runFunction({
          functionName: "rate_tag",
          gasLimit: 21920000,
          kwargs: { tag_name: tagName, post_id: postId, rate, contributor },
          coins: [{"denom": "dys", "amount": String(amount)}]
        })
          .then(() => {
            console.log("rated", rate, tagName, postId);
            location = `/${postId}/topics/${tagName}`
          })
          .catch((e) => console.error("runFunction error:", e));
      }
    }
  </script>
        """
    )
    html_content = BASE_TEMPLATE.substitute(title=f"Post {post_id} tags", body=content)
    start_response("200 OK", [CONTENT_TYPE_HTML] + HEADERS)
    return [html_content.encode()]


def _get_post_tag(post_id: int, tag_name: str, namespace="tags"):
    tag_index = _get_rate_index(namespace, tag_name, post_id)
    return _get_data(tag_index)


def _post_tag_detail(environ, start_response, post_id, tag_name):
    tag = _get_post_tag(post_id, tag_name)

    claimed = tag["metadata"].get("claimed", {})
    earliest_claim_time = tag["metadata"].get("earliest_claim_time", 0)
    earned = claimed.get("dys", 0)

    content = Template(
        """
<h3>
  <a href="/${id}">Post #${id}</a> <a href="/${id}/topics">tags</a>: <a href="/topics/$tag_name">${tag_name}</a>
</h3>

<form>
  <script>
    async function claim(tagName, postId, event) {
      event.preventDefault();

      console.log("claim", tagName, postId, event);
      let postPosition = await getPostPositionInHotPosts(postId, tagName);
      if (postPosition === -1) return;
      let results = await runFunction({
        functionName: "claim_tag_rewards",
        args: [tagName, postPosition],
        gasLimit: 15200000,
      });
      console.log("claim results", results);
      htmx.ajax("GET", "/" + postId + "/topics/" + tagName, {
        target: htmx.closest(event.target, "form"),
        swap: "outerHTML",
        select: "form",
      });
    }
  </script>

  <meter value="$best_rating" min="0" max="1" low=".33" high=".66" optimum=".9">
    $up up and $down down
  </meter>
  <ul class="stats">
    <li>Topic: <a href="/topics/$tag_name">${tag_name}</a></li>
    <li>Up: <strong>${up}</strong></li>
    <li>Down: <strong>${down}</strong></li>
    <li>Earned: <strong>$earned DYS</strong></li>
    <li>
      Claimable: <strong class="claimable">Loading...</strong>

      <button
        class="claim-btn"
        disabled
        onclick="claim('$tag_name', $id, event)"
      >
        Claim
      </button>
    </li>

    <li>
      <button
        class="up-btn"
        onclick="rateTag('up', '$tag_name', '$id', this.closest('form').querySelector('input[name=amount]').value, this.closest('form').querySelector('input[name=name]').value,event)"
        disabled
      >
        #$id is <strong>more</strong> $tag_name
      </button>
      <button
        class="down-btn"
        onclick="rateTag('down','$tag_name', '$id', this.closest('form').querySelector('input[name=amount]').value, this.closest('form').querySelector('input[name=name]').value, event)"
        disabled
      >
        #$id is <strong>less</strong> $tag_name
      </button>
      <input
        name="amount"
        type="number"
        min="0"
        placeholder="Amount in DYS"
        class="auto-save"
      />
      <input
        name="name"
        placeholder="(Optional) Your Dys Name"
        size="30"
        class="auto-save"
      />
    </li>
  </ul>

  <script>
    {
      const tagName = "$tag_name";
      const postId = $id;
      let availableRewards = "";
      let timeLeft = 0;
      const earliest_claim_time = $earliest_claim_time;
      var author;

      const claimButton =
        document.currentScript.parentElement.querySelector(".claim-btn");
      const claimableAmountEl =
        document.currentScript.parentElement.querySelector(".claimable");

      function updateClaimButtonState() {
        const hasClaimableAmount = availableRewards > 1; // Check if availableRewards is greater than zero
        const hasAccount = !!keplrAccount; // Check if account address is set

        isWalletAuthor(author).then((isAuthor) => {
          claimButton.disabled = !(hasClaimableAmount && isAuthor && !timeLeft);
        });
      }

      function calculateAvailableRewards(postId, tagName) {
        console.log("calculateAvailableRewards", postId, tagName);
        Promise.all([
          getData(getTagRewardsIndex(tagName)),
          getPostPositionInHotPosts(postId, tagName),
          getData("posts/" + formatId(postId)),
        ]).then(([tagRewards, postPosition, post]) => {
          author = post.author;
          console.log("tagName", tagName);
          console.log("postId", postId);

          if (postPosition === -1) {
            availableRewards = 0;
          } else {
            availableRewards = Math.floor(
              tagRewards.available.dys * (1 / 2) ** (1 + postPosition),
            );
          }
          console.log("postPosition", postPosition);
          console.log("tagRewards", tagRewards);
          console.log("availableRewards", availableRewards);
          claimableAmountEl.innerText = availableRewards + " DYS";
          updateClaimButtonState(); // Check button state after calculating rewards
        });
      }

      try {
        DYSON_PROTOCOL;
        calculateAvailableRewards(postId, tagName);
      } catch (e) {
        if (e instanceof ReferenceError) {
          document.addEventListener("dysonLoadedEvent", () => {
            calculateAvailableRewards(postId, tagName);
          });
        }
      }

      function updateCountdown() {
        const now = Math.floor(Date.now() / 1000);
        timeLeft = Math.max(0, earliest_claim_time - now);

        if (timeLeft <= 0) {
          // Time is up
          updateClaimButtonState(); // Check button state when time is up

          claimButton.textContent = "Claim now";
          clearInterval(countdownInterval); // Stop the interval
        } else {
          // Update button text with the countdown
          const hours = Math.floor((timeLeft % (60 * 60 * 24)) / (60 * 60));
          const minutes = Math.floor((timeLeft % (60 * 60)) / 60);
          const seconds = Math.floor(timeLeft % 60);
          let timeDisplay =
            hours > 0
              ? hours + "h"
              : minutes > 0
                ? minutes + "m"
                : seconds + "s";

          // Update countdown button text
          claimButton.textContent = "Claim in " + timeDisplay;

          updateClaimButtonState(); // Always check button state on countdown update
        }
      }

      // Start the countdown timer
      const countdownInterval = setInterval(updateCountdown, 1000);
      updateCountdown();

      const setButtons = () => {
        const buttons = document.querySelectorAll(".up-btn, .down-btn");
        buttons.forEach((button) => {
          button.disabled = !keplrAccount;
        });
        updateClaimButtonState();
      };

      document.addEventListener("accountChangedEvent", setButtons);
      setButtons();

      function rateTag(rate, tagName, postId, amount, contributor, event) {
        event.preventDefault();
        return runFunction({
          functionName: "rate_tag",
          gasLimit: 21920000,
          kwargs: { tag_name: tagName, post_id: postId, rate, contributor },
          coins: [{ denom: "dys", amount: String(amount) }],
        })
          .then(() => {
            console.log("rated", rate, tagName, postId);
            htmx.ajax("GET", "/" + postId + "/topics/" + tagName, {
              target: htmx.closest(event.target, "form"),
              swap: "outerHTML",
              select: "form",
            });
          })
          .catch((e) => console.error("runFunction error:", e));
      }
    }
  </script>
</form>
        """
    ).substitute(
        tag_json=json.dumps(tag, indent=2),
        meter_max=tag["up"] + tag["down"],
        percent=int(tag["best_rating"] * 100),
        earned=earned,
        earliest_claim_time=earliest_claim_time,
        **tag,
    )

    # history, pagination = _list_data(
    #    _get_post_tag_historical_rewards_prefix(tag_name, post_id)
    # )
    html_content = BASE_TEMPLATE.substitute(
        title=f"Post {post_id} tag: {tag_name}",
        body=content,
    )
    start_response("200 OK", [CONTENT_TYPE_HTML] + HEADERS)

    return [html_content.encode()]


def _get_best_replies_by_post_id(post_id: int, **kwargs):
    prefix = _get_rating_rate_prefix("replies", _format_id(post_id), "best")
    return _list_data(prefix, **kwargs)


def _list_post_replies(environ, start_response, post_id):
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
    hx-select="form"
    hx-trigger="revealed once"
    hx-swap="innerHTML"
  >
    Loading reply: {reply['id']}
  </div>
  <div
    hx-trigger="load"
    hx-get="/{reply['id']}?depth=0"
    hx-select="article"
    hx-disinherit="hx-select"
    hx-swap="innerHTML ignoreTitle:true"
  >
    <div class="card border">Loading: {reply['id']} ...</div>
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
            >
              Loading more replies...
            </div>

        """

    else:
        load_more_html = "<div>Fin.</div>"

    # Return only the replies items and load more element

    html_content = BASE_TEMPLATE.substitute(
        title=f"Post {post_id} replies",
        body=f'<h2>Replies to <a href="/{post_id}"> post {post_id}</a></h2><div id="reply-content">'
        + replies_items_html
        + load_more_html
        + "</div>",
    )
    start_response("200 OK", [CONTENT_TYPE_HTML] + HEADERS)
    return [html_content.encode()]


def _active_posts(environ, start_response):
    req_pagination = _parse_pagination(environ, default_limit=2, reverse=True)
    posts, pagination = _list_data(
        "available_rewards/replies/dys/", pagination=req_pagination
    )

    # Generate placeholders for each replying post with HTMX fetching the full content
    items_html = "\n".join(
        [
            f"""
<div>
  <div class="active-info">
    <a href="/{int(post['tag_name'])}">Post #{int(post['tag_name'])}</a> has
    <strong>{post['amount']} {post['denom'].upper()}</strong> available to be
    claimed by top replies.
  </div>
  <div
    hx-trigger="load"
    hx-get="/{int(post['tag_name'])}?depth=0"
    hx-select="article"
    hx-disinherit="hx-select"
    hx-swap="innerHTML ignoreTitle:true"
  >
    <div class="card border">Loading: ...</div>
  </div>
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
              hx-select="main >  div"
            >
              Loading more posts...
            </div>

        """

    else:
        load_more_html = "<div>Fin.</div>"

    # Return only the replies items and load more element

    html_content = BASE_TEMPLATE.substitute(
        title=f"Active Posts", body=items_html + load_more_html
    )
    start_response("200 OK", [CONTENT_TYPE_HTML] + HEADERS)
    return [html_content.encode()]


def _get_post_reply(post_id: str, reply_post_id: int):
    tag_index = _get_rate_index("replies", _format_id(post_id), reply_post_id)
    return _get_data(tag_index)


def _post_reply_detail(environ, start_response, post_id, reply_post_id):
    reply = _get_post_reply(post_id, reply_post_id)

    claimed = reply["metadata"].get("claimed", {})
    earliest_claim_time = reply["metadata"].get("earliest_claim_time", 0)
    earned = claimed.get("dys", 0)

    post_id = int(reply["tag_name"])
    reply_post_id = reply["id"]
    content = Template(
        """
<h3>
  <a href="/${post_id}">Post #${post_id}</a> <a href="/${post_id}/replies">replies</a>: <a href="/${post_id}/replies/$reply_post_id">#$reply_post_id</a>
</h3>
<form>
  <script>
    async function claimReply(postId, replyPostId, event) {
      event.preventDefault();

      console.log("claimReply", postId, replyPostId, event);
      let postPosition = await getPostPositionInHotReplies(postId, replyPostId);
      let results = await runFunction({
        functionName: "claim_reply_rewards",
        args: [postId, postPosition],
        gasLimit: 8000000,
      });
      console.log("claim results", results);
      htmx.ajax("GET", "/" + postId + "/replies/" + replyPostId, {
        target: htmx.closest(event.target, "form"),
        swap: "outerHTML",
        select: "form",
      });
    }
  </script>

  <details>
  <summary>
  <meter value="$best_rating" min="0" max="1" low=".33" high=".66" optimum=".9">
    $up up and $down down
  </meter>
</summary>
  <ul class="stats">
    <li>Up: <strong>${up}</strong></li>
    <li>Down: <strong>${down}</strong></li>
    <li>Earned: <strong>$earned DYS</strong></li>
    <li>
      Claimable: <strong class="claimable">Loading...</strong>

      <button
        class="claim-btn"
        disabled
        onclick="claimReply($post_id, $reply_post_id , event)"
      >
        Claim
      </button>
    </li>
    <li>
      <input name="amount" type="number" min="0" placeholder="Amount in DYS" />
      <button
        class="up-btn"
        onclick="rateReply('up', $post_id, $reply_post_id, this.closest('form').querySelector('input[name=amount]').value, event)"
        disabled
      >
        #$reply_post_id is <strong>more relevant</strong>
      </button>
      <button
        class="down-btn"
        onclick="rateReply('down', '$post_id', '$reply_post_id', this.closest('form').querySelector('input[name=amount]').value, event)"
        disabled
      >
        #$reply_post_id is <strong>less relevant</strong>
      </button>
    </li>
  </ul>
</details>


  <script>
    {
      const earliestClaimTime = $earliest_claim_time;
      const claimButton =
        document.currentScript.parentElement.querySelector(".claim-btn");
      const claimableAmountEl =
        document.currentScript.parentElement.querySelector(".claimable");

      const postId = $post_id;
      const replyPostId = $reply_post_id;
      let availableRewards = "";
      let timeLeft = 0;

      function updateClaimButtonState() {
        const hasClaimableAmount = availableRewards > 1; // Check if availableRewards is greater than zero
        const hasAccount = !!keplrAccount; // Check if account address is set

        // Enable the claim button only if all conditions are met
        if (hasClaimableAmount && hasAccount && !timeLeft) {
          claimButton.disabled = false;
        } else {
          claimButton.disabled = true;
        }
      }

      function calculateReplyAvailableRewards(postId, replyPostId) {
        Promise.all([
          getData(getReplyRewardsIndex(postId)),
          getPostPositionInHotReplies(postId, replyPostId),
        ]).then(([replyRewards, replyPosition]) => {
          console.log("replyPostId", replyPostId);
          console.log("postId", postId);
          if (replyPosition === -1) {
            availableRewards = 0;
          } else {
            availableRewards = Math.floor(
              (replyRewards.available.dys || 0) *
                (1 / 2) ** (1 + replyPosition),
            );
          }
          console.log("replyPosition", replyPosition);
          console.log("replyRewards", replyRewards);
          console.log("availableRewards", availableRewards);
          claimableAmountEl.innerText = availableRewards + " DYS";
          updateClaimButtonState(); // Check button state after calculating rewards
        });
      }

    try {
        DYSON_PROTOCOL;
        calculateReplyAvailableRewards(postId, replyPostId);
    } catch (e) {
        if (e instanceof ReferenceError) {
          document.addEventListener("dysonLoadedEvent", () => {
        calculateReplyAvailableRewards(postId, replyPostId);
          });
        }
    }

      function updateCountdown() {
        const now = Math.floor(Date.now() / 1000);
        timeLeft = Math.max(0, earliestClaimTime - now);

        if (timeLeft <= 0) {
          // Time is up
          updateClaimButtonState(); // Check button state when time is up

          claimButton.textContent = "Claim now";
          clearInterval(countdownInterval); // Stop the interval
        } else {
          // Update button text with the countdown
          const hours = Math.floor((timeLeft % (60 * 60 * 24)) / (60 * 60));
          const minutes = Math.floor((timeLeft % (60 * 60)) / 60);
          const seconds = Math.floor(timeLeft % 60);
          let timeDisplay =
            hours > 0
              ? hours + "h"
              : minutes > 0
                ? minutes + "m"
                : seconds + "s";

          // Update countdown button text
          claimButton.textContent = "Claim in " + timeDisplay;

          updateClaimButtonState(); // Always check button state on countdown update
        }
      }

      // Start the countdown timer
      const countdownInterval = setInterval(updateCountdown, 1000);
      updateCountdown();

      const setButtons = () => {
        const buttons = document.querySelectorAll(".up-btn, .down-btn");
        buttons.forEach((button) => {
          button.disabled = !keplrAccount;
        });
        updateClaimButtonState();
      };

      document.addEventListener("accountChangedEvent", setButtons);
      setButtons();

      function rateReply(rate, postId, replyPostId, amount, event) {
        event.preventDefault();
        return runFunction({
          functionName: "rate_reply",
          kwargs: { reply_post_id: replyPostId, post_id: postId, rate },
          coins: [{ denom: "dys", amount: String(amount) }],
        })
          .then(() => {
            console.log("rate_reply", rate, postId, replyPostId);
            htmx.ajax("GET", "/" + postId + "/replies/" + replyPostId, {
              target: htmx.closest(event.target, "form"),
              swap: "outerHTML",
              select: "form",
            });
          })
          .catch((e) => console.error("runFunction error:", e));
      }
    }
  </script>
</form>
        """
    ).substitute(
        reply_json=json.dumps(reply, indent=2),
        meter_max=reply["up"] + reply["down"],
        percent=int(reply["best_rating"] * 100),
        post_id=post_id,
        reply_post_id=reply_post_id,
        earned=earned,
        earliest_claim_time=earliest_claim_time,
        **reply,
    )

    # history, pagination = _list_data(
    #    _get_post_tag_historical_rewards_prefix(tag_name, post_id)
    # )
    html_content = BASE_TEMPLATE.substitute(
        title=f"Post {post_id} reply: {reply_post_id}",
        body=content,
    )
    start_response("200 OK", [CONTENT_TYPE_HTML] + HEADERS)
    return [html_content.encode()]


def _tag_stats(environ, start_response, tag_name):
    content = Template(
        r"""
<div>
  <h1 style="text-transform: capitalize">$tag_name</h1>
  <a href="/topics/$tag_name/hot">Hot</a> |
  <a href="/topics/$tag_name/best">Best</a> | Statistics

  <h3>Hot Rankings chart</h3>
  <div id="hot-chart"></div>
  <h3>Cumulative Rewards chart</h3>
  <div id="cumulative-chart"></div>

  <h2>Top Supporters</h2>

  <table style="width: 100%" class="col-1-r">
    <tbody id="table-body">
      <!-- Rows will be dynamically added here -->
    </tbody>
  </table>

  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/moment@^2"></script>
  <script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-moment@^1"></script>

  <script>
    function renderSupporters() {
      listData("top_tag_contributor/tags/$tag_name", {
          pagination: { limit: 100, reverse: true },
      })
        .then((response) => {
          const dataList = response.dataList;

          // Get the table body (assumes it has an id of 'table-body')
          const tableBody = document.getElementById("table-body");

          // Clear any existing rows
          tableBody.innerHTML = "";

          // Populate the table with data
          dataList.forEach((data) => {
            const row = document.createElement("tr"); // Create a table row


            // Create and populate the 'Amount DYS' cell
            const amountCell = document.createElement("td");
            amountCell.textContent = data.amount.toLocaleString() + " DYS"; // Format with commas
            row.appendChild(amountCell);

            // Create and populate the 'Supporter' cell
            const supporterCell = document.createElement("th");
            supporterCell.textContent = data.contributor;
            row.appendChild(supporterCell);

            // Append the row to the table body
            tableBody.appendChild(row);
          });
        })
        .catch((error) => {
          console.error("Error fetching data:", error);
        });
    }
    try {
      DYSON_PROTOCOL;
      renderSupporters();
    } catch (e) {
      if (e instanceof ReferenceError) {
        document.addEventListener("dysonLoadedEvent", () => renderSupporters());
      }
    }
  </script>

  <script>
    // Fetch additional metadata for each post to get claimed data
    const fetchMetadata = (() => {
      const cache = new Map();

      return async (tag, postId) => {
        const key = `${tag}:${postId}`;

        // If there's already a promise or result in the cache, return it
        if (cache.has(key)) {
          return cache.get(key);
        }

        // Create a new promise and store it in the cache
        const promise = getData(getRateIndex("tags", tag, postId))
          .then((metadata) => {
            cache.set(key, metadata); // Cache the resolved result
            return metadata;
          })
          .catch((error) => {
            cache.delete(key); // Remove the promise if it fails
            throw error;
          });

        cache.set(key, promise); // Cache the pending promise
        return promise;
      };
    })();

    async function renderCharts() {
      // Fetch data using the existing listData function
      const { dataList } = await listData(
        "historical_rewards/tags/$tag_name/",
        {
          pagination: { limit: 99, reverse: true },
        },
      );

      // Prepare data by parsing the index and extracting necessary fields
      const parsedData = await Promise.all(
        dataList.map(async (item) => {
          const parts = item._index.split("/");
          const tag = parts[3];
          const postId = parseInt(parts[4]);
          const blockTime = Date.parse(parts[5]);

          // Fetch additional metadata
          const metadata = await fetchMetadata(tag, postId);

          return {
            hotIndex: item.hot_index,
            dysReward: item.author_rewards.dys,
            tag,
            postId,
            blockTime,
            claimedDys: metadata.metadata.claimed.dys,
            lastClaimed: metadata.metadata.last_claimed,
          };
        }),
      );

      // Group data by `tag`
      const groupedData = {};
      parsedData.forEach((point) => {
        if (!groupedData[point.tag]) groupedData[point.tag] = {};
        if (!groupedData[point.tag][point.postId])
          groupedData[point.tag][point.postId] = [];

        groupedData[point.tag][point.postId].push(point);
      });

      // Render charts for each tag in rows with cumulative rewards and hot index side-by-side
      Object.entries(groupedData).forEach(([tag, posts]) => {
        // Create two canvas elements for each tag
        const rewardCanvas = document.createElement("canvas");
        rewardCanvas.id = `rewardsChart-${tag}`;

        const hotIndexCanvas = document.createElement("canvas");
        hotIndexCanvas.id = `hotIndexChart-${tag}`;

        document.querySelector("#hot-chart").appendChild(hotIndexCanvas);
        document.querySelector("#cumulative-chart").appendChild(rewardCanvas);

        // Prepare datasets for cumulative rewards and hot index charts
        const rewardDatasets = [];
        const hotIndexDatasets = [];

        Object.entries(posts).forEach(([postId, points]) => {
          // Sort points by blockTime in reverse order for reverse calculation
          points.sort((a, b) => a.blockTime - b.blockTime);

          // Reverse calculate cumulative dysReward
          let cumulativeReward = 0; // Start from claimed dys
          let cumulativeData = points.map((point) => {
            cumulativeReward += point.dysReward;
            const dataPoint = { x: point.blockTime, y: cumulativeReward };
            return dataPoint;
          });
          const diff =
            points[0].claimedDys - cumulativeData[cumulativeData.length - 1].y;
          if (diff > 0) {
            cumulativeData = cumulativeData.map((p) => {
              p.y += diff;
              return p;
            });
          }

          // Prepare hotIndex data
          const hotIndexData = points.map((point) => ({
            x: point.blockTime,
            y: point.hotIndex + 1,
          }));

          rewardDatasets.push({
            label: `Post #${postId}`,
            data: cumulativeData, // Reverse back for chronological display
            fill: false,
            tension: 0.1,
          });

          hotIndexDatasets.push({
            label: `Post #${postId}`,
            data: hotIndexData,
            fill: false,
            tension: 0.1,
          });
        });

        // Render the cumulative rewards chart for the current tag
        new Chart(rewardCanvas.getContext("2d"), {
          type: "line",
          data: { datasets: rewardDatasets },
          options: {
            responsive: true,
            plugins: {
              title: {
                display: true,
                text: `Topic: ${tag} - Cumulative Rewards`,
              },
              legend: { display: false },
            },
            scales: {
              x: {
                type: "time",
                time: {
                  unit: "day",
                },
                title: { display: true, text: "Date" },
              },
              y: {
                title: { display: true, text: "Cumulative Rewards (DYS)" },
                position: "right",
              },
            },
          },
        });

        // Render the hot index chart for the current tag
        new Chart(hotIndexCanvas.getContext("2d"), {
          type: "line",
          data: { datasets: hotIndexDatasets },
          options: {
            responsive: true,
            plugins: {
              title: { display: true, text: `Topic: ${tag} - Hot Ranking` },
              legend: { display: false },
            },
            scales: {
              x: {
                type: "time",
                time: {
                  unit: "day",
                },
                title: { display: true, text: "Date" },
                position: "right",
              },
              y: {
                title: {
                  display: true,
                  text: "Hot Ranking",
                },
                position: "right",
                reverse: true,
              },
            },
          },
        });
      });
    }

    try {
      DYSON_PROTOCOL;
      renderCharts();
    } catch (e) {
      if (e instanceof ReferenceError) {
        document.addEventListener("dysonLoadedEvent", () => renderCharts());
      }
    }
  </script>
</div>
"""
    ).safe_substitute(tag_name=tag_name)
    html_content = BASE_TEMPLATE.substitute(
        title=f"Topic Stats",
        body=content,
    )
    start_response("200 OK", [CONTENT_TYPE_HTML] + HEADERS)
    return [html_content.encode()]


def _service_worker(environ, start_response):
    start_response("200 OK", [CONTENT_TYPE_JS, ("Cache-Control", "max-age=0, public")])
    return [
        """
(()=>{"use strict";let e=!1;self.addEventListener("install",(()=>{self.skipWaiting()})),self.addEventListener("fetch",(s=>{const t=(s=>{const{url:t}=s.request;return t.includes(self.registration.scope+"webtorrent/")?t.includes(self.registration.scope+"webtorrent/keepalive/")?new Response:t.includes(self.registration.scope+"webtorrent/cancel/")?new Response(new ReadableStream({cancel(){e=!0}})):async function({request:s}){const{url:t,method:n,headers:o,destination:a}=s,l=await clients.matchAll({type:"window",includeUncontrolled:!0}),[r,i]=await new Promise((e=>{for(const s of l){const l=new MessageChannel,{port1:r,port2:i}=l;r.onmessage=({data:s})=>{e([s,r])},s.postMessage({url:t,method:n,headers:Object.fromEntries(o.entries()),scope:self.registration.scope,destination:a,type:"webtorrent"},[i])}}));let c=null;const d=()=>{i.postMessage(!1),clearTimeout(c),i.onmessage=null};return"STREAM"!==r.body?(d(),new Response(r.body,r)):new Response(new ReadableStream({pull:s=>new Promise((t=>{i.onmessage=({data:e})=>{e?s.enqueue(e):(d(),s.close()),t()},e||(clearTimeout(c),"document"!==a&&(c=setTimeout((()=>{d(),t()}),5e3))),i.postMessage(!0)})),cancel(){d()}}),r)}(s):null})(s);t&&s.respondWith(t)})),self.addEventListener("activate",(()=>{self.clients.claim()}))})();

            """.encode()
    ]


def application(environ, start_response):
    """WSGI Application.

    This is the entry point for serving the website.
    It handles routing and serves data based on the request path.

    Args:
        environ (dict): The WSGI environment dictionary.
        start_response (callable): The WSGI start_response callable.

    Returns:
        iterable: An iterable yielding the response body.
    """
    # Get the path from the request
    path_info = environ.get("PATH_INFO", "").strip("/")

    try:
        # Route handling: Serve different content based on the request path
        if path_info == "":
            start_response("302 Moved", [("Location", f"/recent")])
            return []
        elif re.match(r"^blog/?$", path_info):
            start_response("302 Moved", [("Location", f"/authors/nuance.dys")])
            return []
        elif re.match(r"^active/?$", path_info):
            return _active_posts(environ, start_response)
        elif re.match(r"^recent/?$", path_info):
            return _post_list(environ, start_response)
        elif re.match(r"^\d+/?$", path_info):
            post_id = int(path_info)
            return _post_detail(environ, start_response, post_id)
        elif re.match(r"^topics/?$", path_info):
            return _tag_list(environ, start_response)
        elif re.match(r"^publish/?$", path_info):
            return _new_post(environ, start_response)
        elif re.match(r"^authors/[^/]+/?$", path_info):
            match = re.match(r"^authors/([^/]+)/?$", path_info)
            return _author_post_list(environ, start_response, match[1])
        elif re.match(r"^authors/[^/]+/edit/?$", path_info):
            match = re.match(r"^authors/([^/]+)/edit/?$", path_info)
            return _edit_author_profile(environ, start_response, match[1])
        elif re.match(r"^\d+/replies/?$", path_info):
            match = re.match(r"^(\d+)/replies/?$", path_info)
            post_id = int(match[1])
            return _list_post_replies(environ, start_response, post_id)
        elif re.match(r"^\d+/topics/\w+/?$", path_info):
            match = re.match(r"^(\d+)/topics/(\w+)/?$", path_info)
            post_id = int(match[1])
            tag_name = match[2]
            return _post_tag_detail(environ, start_response, post_id, tag_name)
        elif re.match(r"^\d+/replies/\d+/?$", path_info):
            match = re.match(r"^(\d+)/replies/(\d+)/?$", path_info)
            post_id = int(match[1])
            reply_post_id = int(match[2])
            return _post_reply_detail(environ, start_response, post_id, reply_post_id)
        elif re.match(r"^\d+/topics/?$", path_info):
            match = re.match(r"^(\d+)/topics/?$", path_info)
            post_id = int(match[1])
            return _list_post_tags(environ, start_response, post_id)
        elif re.match(r"^topics/\w+/?$", path_info):
            match = re.match(r"^topics/(\w+)/?$", path_info)
            start_response("302 Moved", [("Location", f"/topics/{match[1]}/hot")])
            return []
        elif re.match(r"^topics/\w+/(hot|best|)/?$", path_info):
            match = re.match(r"^topics/(\w+)/(hot|best)/?$", path_info)
            return _tag_post_list(environ, start_response, match[1], match[2])
        elif re.match(r"^topics/\w+/stats/?$", path_info):
            match = re.match(r"^topics/(\w+)/stats/?$", path_info)
            return _tag_stats(environ, start_response, match[1])
        elif re.match(r"^sw.min.js$", path_info):
            return _service_worker(environ, start_response)
        else:
            raise Exception("not found")

    except Exception as e:
        if "not found" in str(e):
            # If the path does not match any route, return a 404 response
            start_response("404 Not Found", [CONTENT_TYPE_HTML])
            content = ERROR_TEMPLATE.substitute(message="404 Not Found")
            html_content = BASE_TEMPLATE.substitute(title="404 Not Found", body=content)
            return [html_content.encode()]
        # Return a 500 error response for any unexpected errors
        start_response("500 Internal Server Error", [CONTENT_TYPE_HTML])
        content = ERROR_TEMPLATE.substitute(
            message=f"Error: {html.escape(str(e))} on line: {e.lineno} col: {e.col}"
        )
        html_content = BASE_TEMPLATE.substitute(title="Error", body=content)
        return [html_content.encode()]

