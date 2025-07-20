#!/usr/bin/env python3
"""
Test the public functions of the migrated nuance script.py
Tests basic functionality without mocking, using the actual test chain.
"""

import pytest
import json
from pathlib import Path
from tests.utils import poll_until_condition


@pytest.fixture(scope="session")
def deployed_nuance_script(chainnet, api_address):
    """Deploy the nuance script for testing."""
    import random
    import string
    
    dysond = chainnet[0]
    
    # Get the actual chain-id from the node
    status_result = dysond("status")
    chain_id = status_result["node_info"]["network"]
    print(f"Using chain-id: {chain_id}")
    
    # Generate unique account name directly
    random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    account_name = f"nuance_test_{random_suffix}"
    
    # Create account directly
    account_result = dysond(
        "keys", "add", account_name, 
        "--keyring-backend", "test"
    )
    
    # Get account address
    account_info = dysond("keys", "show", account_name, "--keyring-backend", "test")
    address = account_info["address"]
    print(f"Created account: {account_name} -> {address}")
    
    # Fund account directly (faucet logic)
    fund_result = dysond(
        "tx", "bank", "send", 
        "alice", address, "10000udys",
        "--from", "alice", "--chain-id", chain_id
    )
    assert fund_result["code"] == 0, f"Funding failed: {fund_result}"
    
    # Deploy script using update command (without --script-address, defaults to sender address)
    script_path = Path(__file__).parent.parent.parent / "nuance/script.py"
    
    deploy_result = dysond(
        "tx", "script", "update",
        "--code-path", str(script_path),
        "--from", account_name,
        "--chain-id", chain_id,
        "--gas", "auto", "--gas-adjustment", "1.3"
    )

    print(f"Deploy result: {deploy_result}")
    assert deploy_result["code"] == 0, f"Script deployment failed: {deploy_result}"
    
    return {
        "account_name": account_name,
        "address": address,
        "chain_id": chain_id
    }


def test_validate_tag_name(chainnet, deployed_nuance_script):
    """Test the validate_tag_name function."""
    dysond = chainnet[0]
    account_name = deployed_nuance_script["account_name"]
    address = deployed_nuance_script["address"] 
    chain_id = deployed_nuance_script["chain_id"]

    # Test valid tag name
    result = dysond(
        "tx", "script", "exec",
        "--script-address", address,
        "--function-name", "validate_tag_name",
        "--args", json.dumps(["validtag123"]),
        "--from", account_name,
        "--chain-id", chain_id,
        "--gas", "auto",
        "-y"
    )
    assert result["code"] == 0, f"validate_tag_name call failed: {result.get('raw_log', result)}"
    print(f"validate_tag_name result: {result}")


def test_publish_post_basic(chainnet, deployed_nuance_script):
    """Test the publish_post function with basic content."""
    dysond = chainnet[0]
    account_name = deployed_nuance_script["account_name"]
    address = deployed_nuance_script["address"]
    chain_id = deployed_nuance_script["chain_id"]

    post_content = "This is a test post for the migration test."
    result = dysond(
        "tx", "script", "exec",
        "--script-address", address,
        "--function-name", "publish_post",
        "--args", json.dumps([post_content, ""]),  # content, author (empty means use caller)
        "--from", account_name,
        "--chain-id", chain_id,
        "--gas", "auto",
        "-y"
    )
    assert result["code"] == 0, f"publish_post call failed: {result.get('raw_log', result)}"
    print(f"publish_post result: {result}")


def test_edit_author_profile_basic(chainnet, deployed_nuance_script):
    """Test the edit_author_profile function."""
    dysond = chainnet[0]
    account_name = deployed_nuance_script["account_name"]
    address = deployed_nuance_script["address"]
    chain_id = deployed_nuance_script["chain_id"]

    profile_content = "This is my test profile content."
    result = dysond(
        "tx", "script", "exec",
        "--script-address", address,
        "--function-name", "edit_author_profile",
        "--args", json.dumps([profile_content, ""]),  # content, author (empty means use caller)
        "--from", account_name,
        "--chain-id", chain_id,
        "--gas", "auto",
        "-y"
    )
    assert result["code"] == 0, f"edit_author_profile call failed: {result.get('raw_log', result)}"
    print(f"edit_author_profile result: {result}")


def test_rate_tag_basic(chainnet, deployed_nuance_script):
    """Test the rate_tag function."""
    dysond = chainnet[0]
    account_name = deployed_nuance_script["account_name"]
    address = deployed_nuance_script["address"]
    chain_id = deployed_nuance_script["chain_id"]

    # First publish a post to rate
    post_content = "Post to rate with tags."
    publish_result = dysond(
        "tx", "script", "exec",
        "--script-address", address,
        "--function-name", "publish_post",
        "--args", json.dumps([post_content, ""]),
        "--from", account_name,
        "--chain-id", chain_id,
        "--gas", "auto",
        "-y"
    )
    assert publish_result["code"] == 0, f"Failed to publish post for rating test: {publish_result}"

    # Get the account info to get the from_address for the bank send message
    account_info = dysond("keys", "show", account_name, "--keyring-backend", "test")
    from_address = account_info["address"]

    # Now rate the post with a tag
    bank_send_message = {
        "@type": "/cosmos.bank.v1beta1.MsgSend",
        "from_address": from_address,
        "to_address": address,  # Send to script address
        "amount": [{"denom": "udys", "amount": "100"}]
    }
    
    rate_result = dysond(
        "tx", "script", "exec",
        "--script-address", address,
        "--function-name", "rate_tag",
        "--args", json.dumps(["testtag", 1, "up", ""]),  # tag_name, post_id, rate, contributor
        "--attached-message", json.dumps(bank_send_message),  # Send coins as attached message
        "--from", account_name,
        "--chain-id", chain_id,
        "--gas", "auto",
        "-y"
    )
    assert rate_result["code"] == 0, f"rate_tag call failed: {rate_result.get('raw_log', rate_result)}"
    print(f"rate_tag result: {rate_result}")


def test_add_tag_rewards_basic(chainnet, deployed_nuance_script):
    """Test the add_tag_rewards function."""
    dysond = chainnet[0]
    account_name = deployed_nuance_script["account_name"]
    address = deployed_nuance_script["address"]
    chain_id = deployed_nuance_script["chain_id"]

    # Get the account info to get the from_address for the bank send message
    account_info = dysond("keys", "show", account_name, "--keyring-backend", "test")
    from_address = account_info["address"]

    # Create bank send message for sending rewards
    bank_send_message = {
        "@type": "/cosmos.bank.v1beta1.MsgSend",
        "from_address": from_address,
        "to_address": address,  # Send to script address
        "amount": [{"denom": "udys", "amount": "500"}]
    }

    # Add rewards to a tag
    result = dysond(
        "tx", "script", "exec",
        "--script-address", address,
        "--function-name", "add_tag_rewards",
        "--args", json.dumps(["rewardtag", ""]),  # tag_name, contributor (empty means use caller)
        "--attached-message", json.dumps(bank_send_message),  # Send coins as rewards
        "--from", account_name,
        "--chain-id", chain_id,
        "--gas", "auto",
        "-y"
    )
    assert result["code"] == 0, f"add_tag_rewards call failed: {result.get('raw_log', result)}"
    print(f"add_tag_rewards result: {result}") 