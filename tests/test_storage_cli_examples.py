import pytest
import json
import random
import string


def test_storage_get_examples(chainnet, generate_account, faucet):
    """Test all the examples from the storage get command documentation."""
    dysond = chainnet[0]
    
    # Create user and fund
    [user_name, user_addr] = generate_account('getter')
    faucet(user_addr)
    
    # Example 1: Basic storage get
    # Set up test data for config/settings
    config_data = {
        "theme": "dark",
        "language": "en",
        "notifications": True
    }
    dysond("tx", "storage", "set",
        "--from", user_name,
        "--index", "config/settings",
        "--data", json.dumps(config_data))
    
    # Test: $ dysond query storage get dys1... --index "config/settings"
    result = dysond("query", "storage", "get",
        user_addr,
        "--index", "config/settings")
    
    assert "entry" in result
    assert json.loads(result["entry"]["data"]) == config_data
    
    # Example 2: Get with JSON output
    # Set up user profile data
    profile_data = {
        "username": "testuser",
        "email": "test@example.com",
        "created": "2024-01-01"
    }
    dysond("tx", "storage", "set",
        "--from", user_name,
        "--index", "user/profile",
        "--data", json.dumps(profile_data))
    
    # Test: $ dysond query storage get dys1... --index "user/profile" --output json
    result = dysond("query", "storage", "get",
        user_addr,
        "--index", "user/profile",
        "--output", "json")
    
    assert "entry" in result
    assert json.loads(result["entry"]["data"]) == profile_data
    
    # Example 3: Extract a specific field
    # Test: $ dysond query storage get dys1... --index "user/profile" --extract "email"
    result = dysond("query", "storage", "get",
        user_addr,
        "--index", "user/profile",
        "--extract", "email")
    
    # The extracted value should be the JSON string "test@example.com"
    assert result["entry"]["data"] == '"test@example.com"'
    
    # Example 4: Extract a nested field
    # Set up nested data
    app_config = {
        "database": {
            "connection": {
                "host": "localhost",
                "port": 5432,
                "username": "dbuser"
            }
        },
        "cache": {
            "enabled": True
        }
    }
    dysond("tx", "storage", "set",
        "--from", user_name,
        "--index", "config/app",
        "--data", json.dumps(app_config))
    
    # Test: $ dysond query storage get dys1... --index "config/app" --extract "database.connection.host"
    result = dysond("query", "storage", "get",
        user_addr,
        "--index", "config/app",
        "--extract", "database.connection.host")
    
    assert result["entry"]["data"] == '"localhost"'


def test_storage_list_examples(chainnet, generate_account, faucet):
    """Test all the examples from the storage list command documentation."""
    dysond = chainnet[0]
    
    # Create user and fund
    [user_name, user_addr] = generate_account('lister')
    faucet(user_addr)
    
    # Set up test data
    suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    
    # Create various entries for testing
    test_entries = {
        f"test_{suffix}_1": {"status": "active", "count": 5, "name": "First test item"},
        f"test_{suffix}_2": {"status": "inactive", "count": 15, "name": "Second test item"},
        f"test_{suffix}_3": {"status": "active", "count": 20, "name": "Third test entry"},
        f"config/app": {"version": "1.0", "active": True},
        f"config/db": {"host": "localhost", "active": False},
        f"user/alice": {"active": True, "profile": {"username": "alice123"}},
        f"user/bob": {"active": False, "profile": {"username": "bob456"}},
        f"user/charlie": {"active": True, "profile": {"username": "charlie789"}}
    }
    
    # Set all test entries
    for key, value in test_entries.items():
        dysond("tx", "storage", "set",
            "--from", user_name,
            "--index", key,
            "--data", json.dumps(value))
    
    # Example 1: List all storage entries
    # Test: $ dysond query storage list dys1...
    result = dysond("query", "storage", "list", user_addr, "-o", "json")
    assert "entries" in result
    assert len(result["entries"]) >= len(test_entries)
    
    # Example 2: List with specific prefix
    # Test: $ dysond query storage list dys1... --index-prefix "config/"
    result = dysond("query", "storage", "list",
        user_addr,
        "--index-prefix", "config/",
        "-o", "json")
    
    entries = result["entries"]
    assert len(entries) == 2
    for entry in entries:
        assert entry["index"].startswith("config/")
    
    # Example 3: List with pagination
    # Test: $ dysond query storage list dys1... --limit 10 --offset 20
    # (We'll use smaller numbers for our test)
    result = dysond("query", "storage", "list",
        user_addr,
        "--limit", "2",
        "--offset", "1",
        "-o", "json")
    
    assert "entries" in result
    assert len(result["entries"]) <= 2
    
    # Example 4: Filter where status equals "active"
    # Test: $ dysond query storage list dys1... --filter "status==active"
    result = dysond("query", "storage", "list",
        user_addr,
        "--index-prefix", f"test_{suffix}_",
        "--filter", "status==active",
        "-o", "json")
    
    entries = result["entries"]
    assert len(entries) == 2  # Only test_1 and test_3 have status=active
    for entry in entries:
        data = json.loads(entry["data"])
        assert data["status"] == "active"
    
    # Example 5: Filter where count > 10
    # Test: $ dysond query storage list dys1... --filter "count>10"
    result = dysond("query", "storage", "list",
        user_addr,
        "--index-prefix", f"test_{suffix}_",
        "--filter", "count>10",
        "-o", "json")
    
    entries = result["entries"]
    assert len(entries) == 2  # test_2 (15) and test_3 (20)
    for entry in entries:
        data = json.loads(entry["data"])
        assert data["count"] > 10
    
    # Example 6: Extract only the 'name' field
    # Test: $ dysond query storage list dys1... --extract "name"
    result = dysond("query", "storage", "list",
        user_addr,
        "--index-prefix", f"test_{suffix}_",
        "--extract", "name",
        "-o", "json")
    
    entries = result["entries"]
    assert len(entries) == 3
    for entry in entries:
        # The data should now be just the extracted name as a JSON string
        assert entry["data"].startswith('"') and entry["data"].endswith('"')
        name = json.loads(entry["data"])
        assert "test" in name.lower()
    
    # Example 7: Combine prefix, filter, and extract
    # Test: $ dysond query storage list dys1... --index-prefix "user/" --filter "active==true" --extract "profile.username"
    result = dysond("query", "storage", "list",
        user_addr,
        "--index-prefix", "user/",
        "--filter", "active==true",
        "--extract", "profile.username",
        "-o", "json")
    
    entries = result["entries"]
    assert len(entries) == 2  # alice and charlie are active
    usernames = [json.loads(entry["data"]) for entry in entries]
    assert set(usernames) == {"alice123", "charlie789"}
    
    # Example 8: Filter with pattern matching (contains)
    # Test: $ dysond query storage list dys1... --filter 'name%"*test*"'
    result = dysond("query", "storage", "list",
        user_addr,
        "--index-prefix", f"test_{suffix}_",
        "--filter", 'name%"*test*"',
        "-o", "json")
    
    entries = result["entries"]
    assert len(entries) == 2  # "First test item" and "Second test item" contain "test"
    for entry in entries:
        data = json.loads(entry["data"])
        assert "test" in data["name"]


def test_storage_list_complex_filters(chainnet, generate_account, faucet):
    """Test more complex filter scenarios with different operators."""
    dysond = chainnet[0]
    
    # Create user and fund
    [user_name, user_addr] = generate_account('filter_test')
    faucet(user_addr)
    
    # Set up test data with various numeric and string values
    products = {
        "product/1": {"name": "Laptop", "price": 999.99, "stock": 5, "category": "electronics"},
        "product/2": {"name": "Mouse", "price": 29.99, "stock": 50, "category": "electronics"},
        "product/3": {"name": "Desk", "price": 199.99, "stock": 10, "category": "furniture"},
        "product/4": {"name": "Chair", "price": 149.99, "stock": 0, "category": "furniture"},
        "product/5": {"name": "Monitor", "price": 299.99, "stock": 15, "category": "electronics"}
    }
    
    for key, value in products.items():
        dysond("tx", "storage", "set",
            "--from", user_name,
            "--index", key,
            "--data", json.dumps(value))
    
    # Test <= operator
    result = dysond("query", "storage", "list",
        user_addr,
        "--index-prefix", "product/",
        "--filter", "price<=200",
        "-o", "json")
    
    entries = result["entries"]
    assert len(entries) == 3  # Mouse, Desk, Chair
    for entry in entries:
        data = json.loads(entry["data"])
        assert data["price"] <= 200
    
    # Test >= operator
    result = dysond("query", "storage", "list",
        user_addr,
        "--index-prefix", "product/",
        "--filter", "stock>=10",
        "-o", "json")
    
    entries = result["entries"]
    assert len(entries) == 3  # Mouse, Desk, Monitor
    for entry in entries:
        data = json.loads(entry["data"])
        assert data["stock"] >= 10
    
    # Test != operator
    result = dysond("query", "storage", "list",
        user_addr,
        "--index-prefix", "product/",
        "--filter", "category!=furniture",
        "-o", "json")
    
    entries = result["entries"]
    assert len(entries) == 3  # All electronics
    for entry in entries:
        data = json.loads(entry["data"])
        assert data["category"] != "furniture"
    
    # Test % operator (contains)
    result = dysond("query", "storage", "list",
        user_addr,
        "--index-prefix", "product/",
        "--filter", 'category%"*tron*"',
        "-o", "json")
    
    entries = result["entries"]
    # Verify all returned entries match the filter
    for entry in entries:
        data = json.loads(entry["data"])
        assert "tron" in data["category"], f"Filter 'category%\"*tron*\"' returned entry with category '{data['category']}' which doesn't contain 'tron'"
    
    # Test combining multiple conditions
    result = dysond("query", "storage", "list",
        user_addr,
        "--index-prefix", "product/",
        "--filter", "stock>0",
        "--extract", "name",
        "-o", "json")
    
    entries = result["entries"]
    # Verify the filter worked by checking the original data
    for entry in entries:
        # Need to get the full entry to verify stock
        full_result = dysond("query", "storage", "get",
            user_addr,
            "--index", entry["index"],
            "-o", "json")
        full_data = json.loads(full_result["entry"]["data"])
        assert full_data["stock"] > 0, f"Filter 'stock>0' returned entry '{entry['index']}' with stock={full_data['stock']}"


def test_storage_extract_arrays_and_edge_cases(chainnet, generate_account, faucet):
    """Test extract functionality with arrays and edge cases."""
    dysond = chainnet[0]
    
    # Create user and fund
    [user_name, user_addr] = generate_account('extract_edge')
    faucet(user_addr)
    
    # Test data with arrays and nested structures
    complex_data = {
        "user_data": {
            "tags": ["python", "golang", "rust"],
            "scores": [85, 92, 78],
            "metadata": {
                "created": "2024-01-01",
                "updated": "2024-01-15"
            }
        }
    }
    
    dysond("tx", "storage", "set",
        "--from", user_name,
        "--index", "complex/1",
        "--data", json.dumps(complex_data))
    
    # Extract array element
    result = dysond("query", "storage", "get",
        user_addr,
        "--index", "complex/1",
        "--extract", "tags.1")
    
    assert result["entry"]["data"] == '"golang"'
    
    # Extract entire array
    result = dysond("query", "storage", "get",
        user_addr,
        "--index", "complex/1",
        "--extract", "tags")
    
    tags = json.loads(result["entry"]["data"])
    assert tags == ["python", "golang", "rust"]
    
    # Test with missing path (should return error)
    result = dysond("query", "storage", "get",
        user_addr,
        "--index", "complex/1",
        "--extract", "nonexistent.path")
    
    assert isinstance(result, str)
    assert "not found" in result.lower() 