import json
import random
import string


def _unique_prefix(label: str) -> str:
    return f"{label}_" + ''.join(random.choices(string.ascii_lowercase + string.digits, k=8)) + "/"


def test_storage_count_total_no_key(chainnet, generate_account, faucet):
    dysond = chainnet[0]
    [user_name, user_addr] = generate_account('count_total_no_key')
    faucet(user_addr)

    prefix = _unique_prefix("ct_nokey")
    # Create 5 entries
    for i in range(5):
        dysond(
            "tx",
            "storage",
            "set",
            "--from",
            user_name,
            "--index",
            f"{prefix}item_{i}",
            "--data",
            json.dumps({"i": i}),
        )

    # Ask for first page (limit 2) with count-total=true (no page key)
    res = dysond(
        "query",
        "storage",
        "list",
        user_addr,
        "--index-prefix",
        prefix,
        "--limit",
        "2",
        "--count-total",
        "-o",
        "json",
    )

    entries = res.get("entries", [])
    assert len(entries) == 2, f"Expected 2 entries, got {len(entries)}. Full: {json.dumps(res, indent=2)}"

    pag = res.get("pagination", {})
    total_raw = pag.get("total")
    # Treat missing as 0, otherwise convert to int (protobuf may encode as string)
    total_val = int(total_raw) if total_raw is not None else 0
    # BUG REPRO: current keeper incorrectly stops counting after reaching limit
    assert total_val == 5, f"Expected total 5, got {total_val}. Full: {json.dumps(res, indent=2)}"


def test_storage_count_total_with_key_ignored(chainnet, generate_account, faucet):
    dysond = chainnet[0]
    [user_name, user_addr] = generate_account('count_total_with_key')
    faucet(user_addr)

    prefix = _unique_prefix("ct_key")
    # Create 4 entries
    for i in range(4):
        dysond(
            "tx",
            "storage",
            "set",
            "--from",
            user_name,
            "--index",
            f"{prefix}item_{i}",
            "--data",
            json.dumps({"i": i}),
        )

    # Get first page to obtain page-key
    first = dysond(
        "query",
        "storage",
        "list",
        user_addr,
        "--index-prefix",
        prefix,
        "--limit",
        "2",
        "-o",
        "json",
    )

    first_pag = first.get("pagination", {})
    page_key = first_pag.get("next_key")
    assert page_key, f"Expected next_key on first page. Full: {json.dumps(first, indent=2)}"

    # Second page using page-key; request count-total but it must be ignored per SDK
    second = dysond(
        "query",
        "storage",
        "list",
        user_addr,
        "--index-prefix",
        prefix,
        "--limit",
        "2",
        "--page-key",
        page_key,
        "--count-total",
        "-o",
        "json",
    )

    pag = second.get("pagination", {})
    total_raw = pag.get("total")
    total_val = int(total_raw) if total_raw is not None else 0
    # BUG REPRO: current keeper incorrectly sets Total when page-key is provided
    assert total_val == 0, f"Total must be omitted/zero when page-key is used. Got: {json.dumps(pag, indent=2)}"


