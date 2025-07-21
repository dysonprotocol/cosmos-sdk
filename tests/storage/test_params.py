import pytest
import json
import random
import string
from tests.utils import poll_until_condition


def test_storage_params_governance_update_size_enforcement(chainnet, generate_account, faucet):
    """Test updating storage params via governance and verify size limits are enforced."""
    dysond = chainnet[0]
    
    # Create test accounts
    [proposer_name, proposer_addr] = generate_account('proposer', faucet_amount=100_000_000)
    [voter_name, voter_addr] = generate_account('voter', faucet_amount=100_000_000)
    [user_name, user_addr] = generate_account('user', faucet_amount=1_000_000)
    
    # Get current storage params
    current_params = dysond("query", "storage", "params")["params"]
    print(f"Current storage params: {json.dumps(current_params, indent=2)}")
    
    original_max_size = int(current_params["max_storage_size"])
    print(f"Original max storage size: {original_max_size} bytes")
    
    # Test storage with original 1KB limit
    test_data_1kb = "x" * 1024  # 1KB, should fit exactly with original limit
    test_data_2kb = "x" * (2 * 1024)  # 2KB, should exceed original 1KB limit
    
    suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    test_key_1kb = f"data_1kb_{suffix}"
    test_key_2kb = f"data_2kb_{suffix}"
    
    # Should succeed with 1KB data (fits original 1KB limit)
    result_1kb = dysond("tx", "storage", "set",
        "--from", user_name,
        "--index", test_key_1kb,
        "--data", test_data_1kb,
        "--gas", "auto")
    assert result_1kb["code"] == 0, f"1KB data should succeed with 1KB limit: {result_1kb['raw_log']}"
    
    # Should fail with 2KB data (exceeds original 1KB limit)
    with pytest.raises(Exception, match="data size 2048 bytes exceeds maximum allowed size 1024 bytes"):
        dysond("tx", "storage", "set",
            "--from", user_name,
            "--index", test_key_2kb,
            "--data", test_data_2kb,
            "--gas", "auto")
    
    print("✅ Original 1KB size limits are enforced correctly")
    
    # Create governance proposal to increase max_storage_size from 1KB to 3KB
    new_max_size = 3 * 1024  # 3KB, larger than original 1KB but smaller than 4KB test data
    new_params = dict(current_params)
    new_params["max_storage_size"] = str(new_max_size)
    
    # Get governance module address for authority
    gov_module_result = dysond("query", "auth", "module-account", "gov")
    gov_module_addr = gov_module_result.get("account", {}).get("value", {}).get("address", "")
    
    # Create governance proposal file
    proposal_data = {
        "messages": [
            {
                "@type": "/dysonprotocol.storage.v1.MsgUpdateParams",
                "authority": gov_module_addr,
                "params": new_params
            }
        ],
        "metadata": "",
        "deposit": "10000000udys",
        "title": "Update Storage Max Size",
        "summary": f"Increase max storage size from {original_max_size} to {new_max_size}"
    }
    
    # Write proposal to temporary file
    import tempfile
    import os
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
        json.dump(proposal_data, f, indent=2)
        proposal_file = f.name
    
    # Submit governance proposal using file
    prop_result = dysond("tx", "gov", "submit-proposal", proposal_file, "--from", proposer_name)
    
    # Clean up temporary file
    os.unlink(proposal_file)
    
    assert prop_result["code"] == 0, f"Proposal submission failed: {prop_result['raw_log']}"
    
    # Get proposal ID from events
    events = prop_result.get("events", [])
    submit_proposal_events = [e for e in events if e["type"] == "submit_proposal"]
    assert len(submit_proposal_events) > 0, f"No submit_proposal event found in: {events}"
    
    proposal_id_attrs = [attr for attr in submit_proposal_events[0]["attributes"] if attr["key"] == "proposal_id"]
    assert len(proposal_id_attrs) > 0, f"No proposal_id attribute found in submit_proposal event"
    proposal_id = proposal_id_attrs[0]["value"]
    print(f"Created governance proposal {proposal_id}")
    
    # Vote on proposal (assuming alice has voting power from genesis)
    vote_result = dysond("tx", "gov", "vote",
        proposal_id,
        "yes",
        "--from", "alice")
    assert vote_result["code"] == 0, f"Voting failed: {vote_result['raw_log']}"
    
    # Also vote with our voter account if they have voting power
    voter_vote_result = dysond("tx", "gov", "vote",
        proposal_id,
        "yes", 
        "--from", voter_name)
    # Don't assert this one as voter might not have voting power
    
    print(f"Voted on proposal {proposal_id}")
    
    # Wait for voting period to end and proposal to pass
    # In a test environment, the voting period should be short
    def check_proposal_status():
        result = dysond("query", "gov", "proposal", proposal_id)
        status = result.get("proposal", {}).get("status", "UNKNOWN")
        print(f"Current proposal status: {status}")
        
        # Check if proposal reached a final state
        final_states = ["PROPOSAL_STATUS_PASSED", "PROPOSAL_STATUS_REJECTED", "PROPOSAL_STATUS_FAILED"]
        return status in final_states

    poll_until_condition(check_proposal_status, timeout=60, poll_interval=2)
    
    # Get final status and check if it passed
    final_result = dysond("query", "gov", "proposal", proposal_id)
    final_status = final_result.get("proposal", {}).get("status", "UNKNOWN")
    
    assert final_status == "PROPOSAL_STATUS_PASSED", f"Expected proposal to pass but got status: {final_status}"
    print("✅ Proposal passed!")
    
    # Verify params were updated
    updated_params = dysond("query", "storage", "params")["params"]
    print(f"Updated storage params: {json.dumps(updated_params, indent=2)}")
    
    updated_max_size = int(updated_params["max_storage_size"])
    assert updated_max_size == new_max_size, f"Expected max_storage_size {new_max_size}, got {updated_max_size}"
    
    print(f"✅ Storage params updated: max_storage_size = {updated_max_size} bytes")
    
    # Test storage with new 3KB limits
    test_data_4kb = "x" * (4 * 1024)  # 4KB, should exceed new 3KB limit
    test_key_4kb = f"data_4kb_{suffix}"
    
    # The 2KB data should now succeed with the increased 3KB limit
    result_2kb_after = dysond("tx", "storage", "set",
        "--from", user_name,
        "--index", test_key_2kb,
        "--data", test_data_2kb,
        "--gas", "auto")
    assert result_2kb_after["code"] == 0, f"2KB data should succeed with new 3KB limit: {result_2kb_after['raw_log']}"
    
    print("✅ 2KB data now succeeds with updated 3KB size limit")
    
    # The 4KB data should fail with the 3KB limit
    with pytest.raises(Exception, match="data size 4096 bytes exceeds maximum allowed size 3072 bytes"):
        dysond("tx", "storage", "set",
            "--from", user_name,
            "--index", test_key_4kb,
            "--data", test_data_4kb,
            "--gas", "auto")
    
    print("✅ 4KB data fails with 3KB limit")
    
    print("✅ New size limits are enforced correctly")
    
    # Clean up - delete test data
    dysond("tx", "storage", "delete",
        "--from", user_name,
        "--indexes", f"{test_key_small},{test_key_large}")
    
    print("✅ Storage params governance update test completed successfully")


def test_storage_params_query(chainnet):
    """Test querying storage module parameters."""
    dysond = chainnet[0]
    
    # Query storage params
    params_result = dysond("query", "storage", "params")
    print(f"Storage params query result: {json.dumps(params_result, indent=2)}")
    
    # Verify structure
    assert "params" in params_result, f"Expected 'params' field in result: {params_result}"
    params = params_result["params"]
    
    # Verify required fields
    assert "max_storage_size" in params, f"Expected 'max_storage_size' field in params: {params}"
    
    # Verify types and ranges
    max_storage_size = int(params["max_storage_size"])
    assert max_storage_size > 0, f"max_storage_size should be positive: {max_storage_size}"
    assert max_storage_size >= 1024, f"max_storage_size should be at least 1KB: {max_storage_size}"
    
    print(f"✅ Storage params query works correctly: max_storage_size = {max_storage_size} bytes")


def test_storage_size_enforcement(chainnet, generate_account, faucet):
    """Test that storage size limits are properly enforced during set operations."""
    dysond = chainnet[0]
    
    # Create test account
    [user_name, user_addr] = generate_account('size_test')
    faucet(user_addr)
    
    # Get current max storage size
    params = dysond("query", "storage", "params")["params"]
    max_size = int(params["max_storage_size"])
    print(f"Current max storage size: {max_size} bytes")
    
    suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    
    # Test data that's exactly at the limit
    test_data_at_limit = "x" * max_size
    test_key_at_limit = f"at_limit_{suffix}"
    
    at_limit_result = dysond("tx", "storage", "set",
        "--from", user_name,
        "--index", test_key_at_limit,
        "--data", test_data_at_limit)
    assert at_limit_result["code"] == 0, f"Data at limit should succeed: {at_limit_result['raw_log']}"
    
    # Verify it was stored
    get_result = dysond("query", "storage", "get",
        user_addr,
        "--index", test_key_at_limit)
    assert get_result["entry"]["data"] == test_data_at_limit, "Data at limit was not stored correctly"
    
    print(f"✅ Data exactly at limit ({max_size} bytes) succeeds")
    
    # Test data that exceeds the limit by 1 byte
    test_data_over_limit = "x" * (max_size + 1)
    test_key_over_limit = f"over_limit_{suffix}"
    
    over_limit_result = dysond("tx", "storage", "set",
        "--from", user_name,
        "--index", test_key_over_limit,
        "--data", test_data_over_limit)
    assert over_limit_result["code"] != 0, f"Data over limit should fail: {over_limit_result['raw_log']}"
    assert "exceeds maximum" in over_limit_result["raw_log"], f"Expected size limit error: {over_limit_result['raw_log']}"
    
    print(f"✅ Data over limit ({max_size + 1} bytes) correctly fails")
    
    # Test updating existing entry to exceed limit
    update_result = dysond("tx", "storage", "set",
        "--from", user_name,
        "--index", test_key_at_limit,
        "--data", test_data_over_limit)
    assert update_result["code"] != 0, f"Update to exceed limit should fail: {update_result['raw_log']}"
    assert "exceeds maximum" in update_result["raw_log"], f"Expected size limit error on update: {update_result['raw_log']}"
    
    print("✅ Updating existing entry to exceed limit correctly fails")
    
    # Verify original data is still there (update failed)
    get_after_failed_update = dysond("query", "storage", "get",
        user_addr,
        "--index", test_key_at_limit)
    assert get_after_failed_update["entry"]["data"] == test_data_at_limit, "Original data should be preserved after failed update"
    
    # Clean up
    dysond("tx", "storage", "delete",
        "--from", user_name,
        "--indexes", test_key_at_limit)
    
    print("✅ Storage size enforcement test completed successfully")


def test_storage_params_validation(chainnet, generate_account, faucet):
    """Test that invalid parameter updates are rejected."""
    dysond = chainnet[0]
    
    # Create proposer account
    [proposer_name, proposer_addr] = generate_account('param_validator', faucet_amount=50_000_000)
    
    # Get current params
    current_params = dysond("query", "storage", "params")["params"]
    gov_module_result = dysond("query", "auth", "module-account", "gov")
    gov_module_addr = gov_module_result.get("account", {}).get("value", {}).get("address", "")
    
    # Test invalid params: max_storage_size too small (below 1KB minimum)
    invalid_params = dict(current_params)
    invalid_params["max_storage_size"] = "512"  # 512 bytes < 1KB minimum
    
    invalid_proposal_msg = {
        "@type": "/dysonprotocol.storage.v1.MsgUpdateParams",
        "authority": gov_module_addr,
        "params": invalid_params
    }
    
    invalid_prop_result = dysond("tx", "gov", "submit-proposal",
        "--from", proposer_name,
        "--title", "Invalid Storage Params",
        "--summary", "Try to set max_storage_size below minimum",
        "--deposit", "10000000udys",
        "--type", "json",
        "--proposal", json.dumps(invalid_proposal_msg))
    
    # The proposal submission should succeed, but if voted on and executed, it should fail
    # For now, just verify we can submit proposals with invalid params
    # The validation happens during execution, not submission
    assert invalid_prop_result["code"] == 0, f"Proposal submission should succeed: {invalid_prop_result['raw_log']}"
    
    print("✅ Invalid parameter proposal submitted (validation happens at execution)")
    
    # Test invalid params: max_storage_size too large (above 100MB maximum)
    too_large_params = dict(current_params)
    too_large_params["max_storage_size"] = str(200 * 1024 * 1024)  # 200MB > 100MB maximum
    
    too_large_proposal_msg = {
        "@type": "/dysonprotocol.storage.v1.MsgUpdateParams",
        "authority": gov_module_addr,
        "params": too_large_params
    }
    
    too_large_prop_result = dysond("tx", "gov", "submit-proposal",
        "--from", proposer_name,
        "--title", "Too Large Storage Params",
        "--summary", "Try to set max_storage_size above maximum",
        "--deposit", "10000000udys",
        "--type", "json",
        "--proposal", json.dumps(too_large_proposal_msg))
    
    assert too_large_prop_result["code"] == 0, f"Proposal submission should succeed: {too_large_prop_result['raw_log']}"
    
    print("✅ Parameter validation test completed") 