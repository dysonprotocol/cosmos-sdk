import pytest
import json
import base64
import random
import string



def test_storage_set_get(chainnet, generate_account, faucet):
    """Test setting and retrieving a storage value."""
    dysond = chainnet[0]
    
    # Create Alice account and fund it
    [alice_name, alice_addr] = generate_account('alice')
    faucet(alice_addr)
    
    # Set a storage value for testing with unique suffix
    suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    test_key = f"test_key_{suffix}"
    test_value = "test_value"
    
    # Set the storage value using Alice's account
    tx_result = dysond("tx", "storage", "set",
        "--from", alice_name,
        "--index", test_key,
        "--data", test_value)
    
    # Verify the transaction was successful
    assert tx_result["code"] == 0, f"Transaction failed: {tx_result['raw_log']}"
    
    # Query the storage value
    get_result = dysond("query", "storage", "get",
        alice_addr,
        "--index", test_key)
    
    # Print the result for inspection
    print(f"Storage get result: {json.dumps(get_result, indent=2)}")
    
    # Check that entry exists and contains expected data
    assert "entry" in get_result, f"Expected 'entry' field in result: {get_result}"
    entry = get_result["entry"]
    assert entry["data"] == test_value, f"Retrieved value doesn't match: {entry}"
    assert entry["owner"] == alice_addr, f"Owner doesn't match: {entry}"
    assert entry["index"] == test_key, f"Index doesn't match: {entry}"


def test_storage_list(chainnet, generate_account, faucet):
    """Test listing storage values with a prefix."""
    dysond = chainnet[0]
    
    # Create Alice account and fund it
    [alice_name, alice_addr] = generate_account('alice')
    faucet(alice_addr)
    
    # Set multiple storage values with a common prefix
    suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    prefix = f"list_test_{suffix}_"
    values = {
        f"{prefix}1": "value1",
        f"{prefix}2": "value2",
        f"{prefix}3": "value3"
    }
    
    # Set each value in storage
    for key, value in values.items():
        dysond("tx", "storage", "set",
            "--from", alice_name,
            "--index", key,
            "--data", value)
    
    # List all keys with the given prefix
    list_result = dysond("query", "storage", "list",
        alice_addr,
        "--index-prefix", prefix,
        "-o", "json")
    
    # Print the result for inspection
    print(f"Storage list result: {json.dumps(list_result, indent=2)}")
    
    # Check entries field exists and extract storage items
    assert "entries" in list_result, f"Expected 'entries' field in result: {list_result}"
    storage_items = list_result["entries"]
    
    # Extract the values
    found_items = {}
    for item in storage_items:
        assert isinstance(item, dict), f"Expected dict item, got: {type(item)}"
        assert "index" in item, f"Expected 'index' field in item: {item}"
        assert "data" in item, f"Expected 'data' field in item: {item}"
        found_items[item["index"]] = item["data"]
    
    # Check that all our values were found
    for key, value in values.items():
        assert key in found_items, f"Key {key} not found in storage list"
        assert found_items[key] == value, f"Value mismatch for key {key}: expected {value}, got {found_items[key]}"
    
    # Verify the count
    assert len(storage_items) >= len(values), "Not all values were listed"


def test_storage_delete(chainnet, generate_account, faucet):
    """Test deleting storage values."""
    dysond = chainnet[0]
    
    # Create Alice account and fund it
    [alice_name, alice_addr] = generate_account('alice')
    faucet(alice_addr)
    
    # First set a storage value
    suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    test_key = f"delete_test_key_{suffix}"
    test_value = "delete_test_value"
    
    # Set the storage value
    dysond("tx", "storage", "set",
        "--from", alice_name,
        "--index", test_key,
        "--data", test_value)
    
    # Verify it was set correctly
    get_result = dysond("query", "storage", "get",
        alice_addr,
        "--index", test_key)
    
    assert get_result["entry"]["data"] == test_value, f"Value not set correctly for deletion test: expected {test_value}, got {get_result['entry']['data']}"
    
    # Delete the storage value
    delete_result = dysond("tx", "storage", "delete",
        "--from", alice_name,
        "--indexes", test_key)
    
    # Verify the deletion was successful
    assert delete_result["code"] == 0, f"Delete transaction failed: {delete_result['raw_log']}"
    
    # Query the deleted value - should return error message for deleted entries
    get_result = dysond("query", "storage", "get",
        alice_addr,
        "--index", test_key)
    
    # When a storage entry doesn't exist, the query returns an error string
    assert isinstance(get_result, str), f"Expected string error message for deleted entry, got: {type(get_result)}"
    assert "doesn't exist" in get_result, f"Expected 'doesn't exist' error, got: {get_result}"


def test_storage_multi_user(chainnet, generate_account, faucet):
    """Test storage with multiple users and access control."""
    dysond = chainnet[0]
    
    # Create accounts for Alice and Bob
    [alice_name, alice_addr] = generate_account('alice')
    [bob_name, bob_addr] = generate_account('bob')
    
    # Fund both accounts for transactions
    faucet(alice_addr)
    faucet(bob_addr)
    
    # Create unique test keys for each user
    suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    alice_key = f"alice_storage_key_{suffix}"
    bob_key = f"bob_storage_key_{suffix}"
    alice_value = "alice_value"
    bob_value = "bob_value"
    
    # Alice sets her storage value
    alice_set_result = dysond("tx", "storage", "set",
        "--from", alice_name,
        "--index", alice_key,
        "--data", alice_value)
    assert alice_set_result["code"] == 0, f"Alice failed to set storage: {alice_set_result['raw_log']}"
    
    # Bob sets his storage value
    bob_set_result = dysond("tx", "storage", "set",
        "--from", bob_name,
        "--index", bob_key,
        "--data", bob_value)
    assert bob_set_result["code"] == 0, f"Bob failed to set storage: {bob_set_result['raw_log']}"
    
    # Verify Alice's value is retrievable
    alice_result = dysond("query", "storage", "get",
        alice_addr,
        "--index", alice_key)
    
    assert alice_result["entry"]["data"] == alice_value, f"Alice's value not set correctly: expected {alice_value}, got {alice_result['entry']['data']}"
    assert alice_result["entry"]["owner"] == alice_addr, f"Alice's owner not correct: expected {alice_addr}, got {alice_result['entry']['owner']}"
    assert alice_result["entry"]["index"] == alice_key, f"Alice's index not correct: expected {alice_key}, got {alice_result['entry']['index']}"
    
    # Verify Bob's value is retrievable
    bob_result = dysond("query", "storage", "get",
        bob_addr,
        "--index", bob_key)
    
    assert bob_result["entry"]["data"] == bob_value, f"Bob's value not set correctly: expected {bob_value}, got {bob_result['entry']['data']}"
    assert bob_result["entry"]["owner"] == bob_addr, f"Bob's owner not correct: expected {bob_addr}, got {bob_result['entry']['owner']}"
    assert bob_result["entry"]["index"] == bob_key, f"Bob's index not correct: expected {bob_key}, got {bob_result['entry']['index']}"
    
    # Verify that Alice cannot delete Bob's value - should fail with error code
    delete_result = dysond("tx", "storage", "delete",
        "--from", alice_name,
        "--indexes", bob_key)
    
    assert delete_result["code"] != 0, f"Alice should not be able to delete Bob's storage, but transaction succeeded: {delete_result}"
    assert "no entries were deleted" in delete_result["raw_log"], f"Expected 'no entries were deleted' error, got: {delete_result['raw_log']}"


def test_storage_binary_data(chainnet, generate_account, faucet):
    """Test storing and retrieving binary data."""
    dysond = chainnet[0]
    
    # Create Alice account and fund it
    [alice_name, alice_addr] = generate_account('alice')
    faucet(alice_addr)
    
    # Create binary data (base64 encoded)
    binary_data = base64.b64encode(b"Binary test data").decode('utf-8')
    suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    test_key = f"binary_data_key_{suffix}"
    
    # Set the binary data
    dysond("tx", "storage", "set",
        "--from", alice_name,
        "--index", test_key,
        "--data", binary_data)
    
    # Retrieve the binary data
    get_result = dysond("query", "storage", "get",
        alice_addr,
        "--index", test_key)
    
    # Print result for inspection
    print(f"Binary data result: {json.dumps(get_result, indent=2)}")
    
    # Get the value from entry
    assert "entry" in get_result, f"Expected 'entry' field in result: {get_result}"
    value = get_result["entry"]["data"]
    
    # Verify the data
    assert value == binary_data, "Binary data not retrieved correctly"
    
    # Verify we can decode it back
    decoded = base64.b64decode(value)
    assert decoded == b"Binary test data", "Binary data corrupted in storage"


def test_storage_extract_and_filter(chainnet, generate_account, faucet):
    """Test the new --extract and --filter query flags."""
    dysond = chainnet[0]

    # Create user and fund
    [user_name, user_addr] = generate_account('extractor')
    faucet(user_addr)

    # Prepare JSON payloads
    json_entry_1 = {
        "title": "First Post",
        "category": "blog",
        "meta": {"views": 10}
    }
    json_entry_2 = {
        "title": "Second Post",
        "category": "blog",
        "meta": {"views": 20}
    }
    json_entry_3 = {
        "title": "Draft Note",
        "meta": {"views": 0}
    }

    # Helper to set entry
    def set_json(index: str, data: dict):
        dysond(
            "tx",
            "storage",
            "set",
            "--from",
            user_name,
            "--index",
            index,
            "--data",
            json.dumps(data),
        )

    prefix = "posts/"
    set_json(prefix + "1", json_entry_1)
    set_json(prefix + "2", json_entry_2)
    set_json(prefix + "draft", json_entry_3)

    # Test --extract on single get
    get_res = dysond(
        "query",
        "storage",
        "get",
        user_addr,
        "--index",
        prefix + "1",
        "--extract",
        "title",
    )
    # entry.data should now be the string "First Post" (with quotes)
    extracted = get_res["entry"]["data"]
    # The extracted value should be "First Post" already as JSON string
    assert extracted == '"First Post"', f"extract failed: {extracted}"

    # Test --filter when listing
    list_res = dysond(
        "query",
        "storage",
        "list",
        user_addr,
        "--index-prefix",
        prefix,
        "--filter",
        "category",
        "-o",
        "json",
    )
    entries = list_res.get("entries", [])
    # Should contain only 2 items (those with category)
    assert len(entries) == 2, f"filter expected 2 entries, got {len(entries)}"

    # Validate extract works in list too
    list_extract = dysond(
        "query",
        "storage",
        "list",
        user_addr,
        "--index-prefix",
        prefix,
        "--filter",
        "category",
        "--extract",
        "meta.views",
        "-o",
        "json",
    )
    entries_views = list_extract.get("entries", [])
    views_values = [int(e["data"]) for e in entries_views]
    assert set(views_values) == {10, 20}, f"extract in list failed, got {views_values}"


def test_storage_invalid_extract_and_filter(chainnet, generate_account, faucet):
    """Ensure invalid extract path raises error and unmatched filter returns empty list."""
    dysond = chainnet[0]

    [u_name, u_addr] = generate_account('neg')
    faucet(u_addr)

    entry = {"foo": {"bar": 1}}
    dysond("tx", "storage", "set", "--from", u_name, "--index", "neg/1", "--data", json.dumps(entry))

    # Attempt to extract missing path -> expect string error (gRPC NotFound propagated to CLI)
    res = dysond("query", "storage", "get", u_addr, "--index", "neg/1", "--extract", "foo.baz")
    assert isinstance(res, str), "Expected error string when extract path missing"
    assert "not found" in res.lower(), f"Unexpected error message: {res}"

    # Filter that matches nothing should return 0 entries
    list_res = dysond(
        "query", "storage", "list", u_addr, "--index-prefix", "neg/", "--filter", "nonexistent", "-o", "json"
    )
    entries = list_res.get("entries", [])
    assert entries == [] or len(entries) == 0, f"Expected empty list, got {entries}"


def test_storage_extract_filter_too_long(chainnet, generate_account, faucet):
    dysond = chainnet[0]
    [name, addr] = generate_account('toolong')
    faucet(addr)

    long_path = 'a' * 101
    dysond("tx", "storage", "set", "--from", name, "--index", "toolong/1", "--data", "{}")

    res = dysond("query", "storage", "get", addr, "--index", "toolong/1", "--extract", long_path)
    assert isinstance(res, str) and "too long" in res.lower(), f"Expected length error, got {res}"

    list_res = dysond("query", "storage", "list", addr, "--index-prefix", "toolong/", "--filter", long_path, "-o", "json")
    # For list, CLI likely surfaces error string instead of json when InvalidArgument
    assert isinstance(list_res, str), "Expected error string for too long filter"
    assert "too long" in list_res.lower(), f"Expected length error, got {list_res}"


def test_storage_delete_by_prefix_and_filter(chainnet, generate_account, faucet):
    """Test deleting storage values by prefix and optional filter."""
    dysond = chainnet[0]
    
    # Create account and fund it
    [user_name, user_addr] = generate_account('deleter')
    faucet(user_addr)
    
    # Create test data with a common prefix
    suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    prefix = f"delete_test_{suffix}/"
    
    # Set up test data with JSON values
    test_data = {
        f"{prefix}user1": {"name": "Alice", "age": 25, "active": True},
        f"{prefix}user2": {"name": "Bob", "age": 30, "active": False},
        f"{prefix}user3": {"name": "Charlie", "age": 35, "active": True},
        f"{prefix}admin1": {"name": "Admin", "role": "admin", "active": True}
    }
    
    # Set all the test data
    for key, value in test_data.items():
        dysond("tx", "storage", "set",
            "--from", user_name,
            "--index", key,
            "--data", json.dumps(value))
    
    # Test 1: Delete all entries with prefix containing user
    user_prefix = f"{prefix}user"
    delete_result = dysond("tx", "storage", "delete",
        "--from", user_name,
        "--index-prefix", user_prefix)
    
    assert delete_result["code"] == 0, f"Delete by prefix failed: {delete_result['raw_log']}"
    
    # Verify user entries are deleted
    for i in range(1, 4):
        key = f"{user_prefix}{i}"
        get_result = dysond("query", "storage", "get",
            user_addr,
            "--index", key)
        assert isinstance(get_result, str), f"Entry {key} should be deleted but still exists"
        assert "doesn't exist" in get_result, f"Entry {key} should show 'doesn't exist' error"
    
    # Verify admin entry still exists
    admin_key = f"{prefix}admin1"
    admin_result = dysond("query", "storage", "get",
        user_addr,
        "--index", admin_key)
    assert admin_result["entry"]["data"] == json.dumps(test_data[admin_key]), \
        f"Admin entry should still exist"
    
    # Test 2: Set up new data for filter test
    filter_data = {
        f"{prefix}active1": {"name": "User1", "status": "active"},
        f"{prefix}active2": {"name": "User2", "status": "active"},
        f"{prefix}inactive1": {"name": "User3", "status": "inactive"},
        f"{prefix}pending1": {"name": "User4", "status": "pending"}
    }
    
    for key, value in filter_data.items():
        dysond("tx", "storage", "set",
            "--from", user_name,
            "--index", key,
            "--data", json.dumps(value))
    
    # Test 3: Delete entries with specific filter (status == "active")
    delete_filter_result = dysond("tx", "storage", "delete",
        "--from", user_name,
        "--index-prefix", prefix,
        "--filter", 'status == "active"')
    
    assert delete_filter_result["code"] == 0, f"Delete by filter failed: {delete_filter_result['raw_log']}"
    
    # Verify only active entries are deleted
    for key in [f"{prefix}active1", f"{prefix}active2"]:
        get_result = dysond("query", "storage", "get",
            user_addr,
            "--index", key)
        assert isinstance(get_result, str), f"Active entry {key} should be deleted"
        assert "doesn't exist" in get_result, f"Active entry {key} should show 'doesn't exist' error"
    
    # Verify inactive and pending entries still exist
    for key in [f"{prefix}inactive1", f"{prefix}pending1"]:
        get_result = dysond("query", "storage", "get",
            user_addr,
            "--index", key)
        assert "entry" in get_result, f"Entry {key} should still exist"
        
    # Test 4: Verify mutual exclusivity - cannot use both indexes and index-prefix
    # This should fail at the CLI validation level
    invalid_result = dysond("tx", "storage", "delete",
        "--from", user_name,
        "--indexes", f"{prefix}test",
        "--index-prefix", prefix,
        "--offline")  # Use offline mode to get string error instead of exception
    # Check that it failed - CLI returns string error instead of transaction
    assert isinstance(invalid_result, str), "Expected CLI error string for mutual exclusivity"
    assert "cannot specify both" in invalid_result or "mutually exclusive" in invalid_result, \
        f"Expected mutual exclusivity error, got: {invalid_result}"


def test_storage_delete_empty_prefix(chainnet, generate_account, faucet):
    """Test that delete with empty prefix is rejected."""
    dysond = chainnet[0]
    
    [user_name, user_addr] = generate_account('empty_prefix')
    faucet(user_addr)
    
    # Try to delete with empty prefix (dangerous - would delete all user's data)
    delete_result = dysond("tx", "storage", "delete",
        "--from", user_name,
        "--index-prefix", "",
        "--offline")  # Use offline mode to get string error instead of exception
    
    # This should fail with an error at the CLI level
    assert isinstance(delete_result, str), "Expected CLI error string for empty prefix"
    assert "must specify either" in delete_result or "must provide" in delete_result, \
        f"Expected validation error, got: {delete_result}" 