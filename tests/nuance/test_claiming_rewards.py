#!/usr/bin/env python3
"""
Backend Tests for Nuance Claiming Rewards
Tests core functionality without frontend dependencies
"""

import pytest
import json
import random
import string
from pathlib import Path

# Import the deployed_demo_script fixture from test_e2e
from tests.nuance.test_e2e import deployed_demo_script


def test_claiming_rewards_flow(chainnet, deployed_demo_script, generate_account):
    """
    Test the complete claiming rewards flow:
    - Create and fund 2 accounts
    - Account1 authors 4 posts
    - Account1 tags all 4 posts with the same tag
    - Account2 rates all 4 posts for that tag
    - Account1 claims rewards for each post of that tag
    """
    dysond = chainnet[0]
    script_address = deployed_demo_script["address"]
    status_result = dysond("status")
    chain_id = status_result["node_info"]["network"]
    
    # Generate unique identifiers for this test
    test_id = random.randint(10000, 99999)
    tag_name = f"testtag{test_id}"
    
    print(f"Starting claiming rewards test with tag: {tag_name}")
    
    # 1. Create and fund account1 (author)
    account1_name = f"author_{test_id}"
    [account1_name, account1_address] = generate_account(account1_name)
    
    fund1_result = dysond(
        "tx", "bank", "send", "alice", account1_address, "20000000udys",  # 20 DYS
        "--from", "alice", "--chain-id", chain_id
    )
    assert fund1_result["code"] == 0, f"Failed to fund account1: {fund1_result}"
    print(f"Created and funded account1: {account1_name} -> {account1_address}")
    
    # 2. Create and fund account2 (rater)
    account2_name = f"rater_{test_id}"
    [account2_name, account2_address] = generate_account(account2_name)
    
    fund2_result = dysond(
        "tx", "bank", "send", "alice", account2_address, "20000000udys",  # 20 DYS
        "--from", "alice", "--chain-id", chain_id
    )
    assert fund2_result["code"] == 0, f"Failed to fund account2: {fund2_result}"
    print(f"Created and funded account2: {account2_name} -> {account2_address}")
    
    # 3. Account1 authors 4 posts
    post_ids = []
    for i in range(4):
        post_content = f"Test post {i+1} for claiming rewards test {test_id}"
        
        post_result = dysond(
            "tx", "script", "exec",
            "--script-address", script_address,
            "--function-name", "publish_post",
            "--args", json.dumps([post_content, ""]),
            "--from", account1_name,
            "--chain-id", chain_id,
            "--gas", "auto", 
            "--gas-adjustment", "2",
            "-y"
        )
        assert post_result["code"] == 0, f"Failed to create post {i+1}: {post_result.get('raw_log', post_result)}"
        
        # Extract post_id
        events_by_type = {event.get("type"): event for event in post_result.get("events", [])}
        exec_event = events_by_type["dysonprotocol.script.v1.EventExecScript"]
        attrs_by_key = {attr.get("key"): attr.get("value") for attr in exec_event.get("attributes", [])}
        response_data = json.loads(attrs_by_key["response"])
        result_data = json.loads(response_data.get("result", "{}"))
        post_id = result_data.get("result")
        assert post_id is not None, f"Could not extract post_id from post {i+1}: {result_data}"
        
        post_ids.append(post_id)
        print(f"Created post {i+1}: {post_id} - {post_content}")
    
    print(f"Created {len(post_ids)} posts: {post_ids}")
    
    # 4. Account1 tags all 4 posts with the same tag
    for i, post_id in enumerate(post_ids):
        tag_result = dysond(
            "tx", "script", "exec",
            "--script-address", script_address,
            "--function-name", "rate_tag",
            "--args", json.dumps([tag_name, post_id, "up", ""]),
            "--attached-message", json.dumps({
                "@type": "/cosmos.bank.v1beta1.MsgSend",
                "from_address": account1_address,
                "to_address": script_address,
                "amount": [{"denom": "udys", "amount": "1000000"}]  # 1 DYS
            }),
            "--from", account1_name,
            "--chain-id", chain_id,
            "--gas", "auto", 
            "--gas-adjustment", "2",
            "-y"
        )
        assert tag_result["code"] == 0, f"Failed to create tag for post {post_id}: {tag_result.get('raw_log', tag_result)}"
        print(f"Tagged post {post_id} with '{tag_name}' (author)")
    
    # 5. Account2 rates all 4 posts for that tag (random amounts)
    rating_amounts = [1000000, 2000000, 1500000, 3000000]  # Different amounts in udys
    for i, (post_id, amount_udys) in reversed(list(enumerate(zip(post_ids, rating_amounts)))):
        rate_result = dysond(
            "tx", "script", "exec",
            "--script-address", script_address,
            "--function-name", "rate_tag",
            "--args", json.dumps([tag_name, post_id, "up", ""]),
            "--attached-message", json.dumps({
                "@type": "/cosmos.bank.v1beta1.MsgSend",
                "from_address": account2_address,
                "to_address": script_address,
                "amount": [{"denom": "udys", "amount": str(amount_udys)}]
            }),
            "--from", account2_name,
            "--chain-id", chain_id,
            "--gas", "auto", 
            "--gas-adjustment", "2",
            "-y"
        )
        assert rate_result["code"] == 0, f"Failed to rate tag for post {post_id}: {rate_result.get('raw_log', rate_result)}"
        amount_dys = amount_udys / 1000000
        print(f"Rated post {post_id} with {amount_dys} DYS (rater)")
    
    # DEBUG: Check what's actually in the hot list
    debug_result = dysond(
        "tx", "script", "exec",
        "--script-address", script_address,
        "--function-name", "debug_hot_list",
        "--args", json.dumps([tag_name]),
        "--from", account1_name,
        "--chain-id", chain_id,
        "--gas", "auto", "-y"
    )
    print(f"DEBUG hot list result: {debug_result}")

    # 6. Account1 claims rewards for each post of that tag
    # Need to check the hot index for each post first
    claim_results = []
    
    for hot_index in reversed(range(4)):
        print(f"Attempting to claim rewards for hot_index {hot_index}")
        
        claim_result = dysond(
            "tx", "script", "exec",
            "--script-address", script_address,
            "--function-name", "claim_tag_rewards",
            "--args", json.dumps([tag_name, hot_index]),
            "--from", account1_name,
            "--chain-id", chain_id,
            "--gas", "auto", 
            "--gas-adjustment", "2",
            "-y"
        )
        
        print(f"Claim result for hot_index {hot_index}: code={claim_result['code']}")
        print(f"Claim details for hot_index {hot_index}: {claim_result.get('raw_log', claim_result)}")
        
        claim_results.append({
            "hot_index": hot_index,
            "success": claim_result["code"] == 0,
            "result": claim_result
        })
    
    # 7. Verify the results
    successful_claims = [r for r in claim_results if r["success"]]
    failed_claims = [r for r in claim_results if not r["success"]]
    
    print(f"\nClaim Results Summary:")
    print(f"  Successful claims: {len(successful_claims)}")
    print(f"  Failed claims: {len(failed_claims)}")
    
    print(f"  All claim results: {[(c['hot_index'], c['success']) for c in claim_results]}")
    
    # All 4 posts should be claimable - if this fails, there's a bug in the script
    assert len(successful_claims) == 4, f"Should be able to claim rewards for all 4 posts but only {len(successful_claims)} succeeded. Failed claims: {[(c['hot_index'], c['result'].get('raw_log', 'No details')[:100]) for c in failed_claims]}"
    
    print(f"\n✅ SUCCESS: Claiming rewards flow completed")
    print(f"   - Created 4 posts: {post_ids}")
    print(f"   - Tagged all posts with '{tag_name}'")
    print(f"   - Rated all posts from different account")
    print(f"   - Successfully claimed rewards for {len(successful_claims)}/{len(claim_results)} posts")
    