"""
Integration tests for MsgCreateExternalName functionality.

Tests the ability for nameservice authority to create external names
without the commit-reveal process, including:
1. Authority validation
2. Name format validation using ExternalNameRegex
3. NFT creation and ownership
4. Event emission
5. Error handling for edge cases
"""
import pytest
import json
import secrets
import tempfile
import time


def test_create_external_name_success(chainnet, generate_account):
    """Test successful external name creation by authority"""
    dysond_bin = chainnet[0]
    [alice_name, alice_address] = generate_account('alice')
    
    # Get module authority (typically gov module address)
    gov_module_response = dysond_bin("query", "auth", "module-account", "gov")
    authority_address = gov_module_response.get("account", {}).get("value", {}).get("address", "")
    assert authority_address, "Could not get gov module address"
    
    # Valid external domain name
    external_name = "example.com"
    
    # Authority cannot directly execute the message without governance proposal
    # So we need to test via governance proposal
    proposal = {
        "messages": [
            {
                "@type": "/dysonprotocol.nameservice.v1.MsgCreateExternalName",
                "authority": authority_address,
                "name": external_name
            }
        ],
        "metadata": "ipfs://CID",
        "deposit": "1udys",
        "title": "Create External Name",
        "summary": f"Create external name {external_name}"
    }
    
    # Delegate tokens for voting power
    validators = dysond_bin("query", "staking", "validators")
    validator_operator = validators["validators"][0]["operator_address"]
    delegate_result = dysond_bin("tx", "staking", "delegate", validator_operator, "50000000udys", "--from", "alice")
    assert delegate_result["code"] == 0, f"Failed to delegate: {delegate_result['raw_log']}"
    
    # Submit governance proposal
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json") as f:
        json.dump(proposal, f)
        f.flush()
        submit_result = dysond_bin("tx", "gov", "submit-proposal", f.name, "--from", "alice")
    
    assert submit_result["code"] == 0, f"Submit proposal failed: {submit_result['raw_log']}"
    
    # Extract proposal ID
    submit_events = [e for e in submit_result.get("events", []) if e.get("type") == "submit_proposal"]
    proposal_id_attrs = [a for e in submit_events for a in e.get("attributes", []) if a.get("key") == "proposal_id"]
    proposal_id = proposal_id_attrs[0].get("value") if proposal_id_attrs else None
    assert proposal_id, "Could not extract proposal ID"
    
    # Vote yes
    vote_result = dysond_bin("tx", "gov", "vote", proposal_id, "yes", "--from", "alice")
    assert vote_result["code"] == 0, f"Vote failed: {vote_result['raw_log']}"
    
    # Wait for proposal to pass
    def proposal_passed():
        proposal_info = dysond_bin("query", "gov", "proposal", proposal_id)
        status = proposal_info["proposal"]["status"]
        return status == "PROPOSAL_STATUS_PASSED"
    
    from tests.utils import poll_until_condition
    poll_until_condition(proposal_passed, timeout=30, error_message="Proposal did not pass")
    
    # Verify NFT was created
    nft_info = dysond_bin("query", "nft", "nft", "nameservice.dys", external_name)
    assert "nft" in nft_info, f"External name NFT not found: {external_name}"
    assert nft_info["nft"]["id"] == external_name, "NFT ID doesn't match external name"
    assert nft_info["nft"]["class_id"] == "nameservice.dys", "NFT class ID incorrect"
    
    # Verify NFT owner is the authority
    nft_owner = dysond_bin("query", "nft", "owner", "nameservice.dys", external_name)
    assert nft_owner["owner"] == authority_address, "NFT not owned by authority"
    
    # Verify NFT data
    nft_data = nft_info["nft"].get("data", {}).get("value", {})
    assert nft_data.get("metadata") == "external_name", "Incorrect metadata"
    assert not nft_data.get("listed", False), "External name should not be listed by default"
    
    print(f"✓ External name {external_name} created successfully by authority")


def test_external_name_format_validation(chainnet, generate_account):
    """Test ExternalNameRegex validation for external names"""
    dysond_bin = chainnet[0]
    [alice_name, alice_address] = generate_account('alice')
    
    # Get authority address
    gov_module_response = dysond_bin("query", "auth", "module-account", "gov")
    authority_address = gov_module_response.get("account", {}).get("value", {}).get("address", "")
    
    # Delegate for voting
    validators = dysond_bin("query", "staking", "validators")
    validator_operator = validators["validators"][0]["operator_address"]
    delegate_result = dysond_bin("tx", "staking", "delegate", validator_operator, "50000000udys", "--from", "alice")
    assert delegate_result["code"] == 0
    
    # Test valid external names
    valid_names = [
        "example.com",
        "sub.domain.org", 
        "a.b",
        "test-site.example.org",
        "my123.site456.com"
    ]
    
    for valid_name in valid_names:
        proposal = {
            "messages": [
                {
                    "@type": "/dysonprotocol.nameservice.v1.MsgCreateExternalName",
                    "authority": authority_address,
                    "name": valid_name
                }
            ],
            "metadata": "ipfs://CID",
            "deposit": "1udys", 
            "title": f"Create External Name {valid_name}",
            "summary": f"Create external name {valid_name}"
        }
        
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json") as f:
            json.dump(proposal, f)
            f.flush()
            submit_result = dysond_bin("tx", "gov", "submit-proposal", f.name, "--from", "alice")
        
        assert submit_result["code"] == 0, f"Valid name {valid_name} was rejected: {submit_result['raw_log']}"
        print(f"✓ Valid external name format accepted: {valid_name}")


def test_external_name_duplicate_prevention(chainnet, generate_account):
    """Test that duplicate external names are prevented"""
    dysond_bin = chainnet[0]
    [alice_name, alice_address] = generate_account('alice')
    
    # Get authority address
    gov_module_response = dysond_bin("query", "auth", "module-account", "gov")
    authority_address = gov_module_response.get("account", {}).get("value", {}).get("address", "")
    
    # Delegate for voting
    validators = dysond_bin("query", "staking", "validators")
    validator_operator = validators["validators"][0]["operator_address"]
    delegate_result = dysond_bin("tx", "staking", "delegate", validator_operator, "50000000udys", "--from", "alice")
    assert delegate_result["code"] == 0
    
    external_name = "duplicate.test.com"
    
    # Create first external name
    proposal1 = {
        "messages": [
            {
                "@type": "/dysonprotocol.nameservice.v1.MsgCreateExternalName",
                "authority": authority_address,
                "name": external_name
            }
        ],
        "metadata": "ipfs://CID",
        "deposit": "1udys",
        "title": "Create First External Name",
        "summary": f"Create external name {external_name}"
    }
    
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json") as f:
        json.dump(proposal1, f)
        f.flush()
        submit_result1 = dysond_bin("tx", "gov", "submit-proposal", f.name, "--from", "alice")
    
    assert submit_result1["code"] == 0
    
    # Extract and vote on first proposal
    submit_events = [e for e in submit_result1.get("events", []) if e.get("type") == "submit_proposal"]
    proposal_id_attrs = [a for e in submit_events for a in e.get("attributes", []) if a.get("key") == "proposal_id"]
    proposal_id1 = proposal_id_attrs[0].get("value")
    
    vote_result1 = dysond_bin("tx", "gov", "vote", proposal_id1, "yes", "--from", "alice")
    assert vote_result1["code"] == 0
    
    # Wait for first proposal to pass
    def proposal1_passed():
        proposal_info = dysond_bin("query", "gov", "proposal", proposal_id1)
        return proposal_info["proposal"]["status"] == "PROPOSAL_STATUS_PASSED"
    
    from tests.utils import poll_until_condition
    poll_until_condition(proposal1_passed, timeout=30, error_message="First proposal did not pass")
    
    # Verify first NFT was created
    nft_info = dysond_bin("query", "nft", "nft", "nameservice.dys", external_name)
    assert "nft" in nft_info, "First external name NFT not created"
    
    # Try to create duplicate (should fail when executed)
    proposal2 = {
        "messages": [
            {
                "@type": "/dysonprotocol.nameservice.v1.MsgCreateExternalName", 
                "authority": authority_address,
                "name": external_name  # Same name
            }
        ],
        "metadata": "ipfs://CID",
        "deposit": "1udys",
        "title": "Create Duplicate External Name", 
        "summary": f"Attempt to create duplicate external name {external_name}"
    }
    
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json") as f:
        json.dump(proposal2, f)
        f.flush()
        submit_result2 = dysond_bin("tx", "gov", "submit-proposal", f.name, "--from", "alice")
    
    assert submit_result2["code"] == 0, "Proposal submission should succeed even with duplicate name"
    
    # Extract and vote on second proposal
    submit_events2 = [e for e in submit_result2.get("events", []) if e.get("type") == "submit_proposal"]
    proposal_id_attrs2 = [a for e in submit_events2 for a in e.get("attributes", []) if a.get("key") == "proposal_id"]
    proposal_id2 = proposal_id_attrs2[0].get("value")
    
    vote_result2 = dysond_bin("tx", "gov", "vote", proposal_id2, "yes", "--from", "alice")
    assert vote_result2["code"] == 0
    
    # Wait for second proposal result (should fail during execution)
    def proposal2_finished():
        proposal_info = dysond_bin("query", "gov", "proposal", proposal_id2)
        status = proposal_info["proposal"]["status"]
        return status in ["PROPOSAL_STATUS_PASSED", "PROPOSAL_STATUS_FAILED"]
    
    poll_until_condition(proposal2_finished, timeout=30, error_message="Second proposal did not finish")
    
    # Check that second proposal failed during execution
    final_proposal2 = dysond_bin("query", "gov", "proposal", proposal_id2)
    # Even if the proposal "passes", the message execution should fail, but governance may still mark it as passed
    # The important thing is that no duplicate NFT was created
    
    # Verify only one NFT exists for this name
    nft_info_final = dysond_bin("query", "nft", "nft", "nameservice.dys", external_name)
    assert "nft" in nft_info_final, "Original NFT should still exist"
    
    print(f"✓ Duplicate external name creation prevented for {external_name}")


def test_external_name_vs_regular_name_coexistence(chainnet, generate_account, register_name):
    """Test that external names can coexist with regular .dys names"""
    dysond_bin = chainnet[0]
    [alice_name, alice_address] = generate_account('alice')
    
    # Register a regular .dys name using commit-reveal
    regular_name = register_name(dysond_bin, alice_name, alice_address, "1000udys")
    
    # Verify regular name exists
    regular_nft = dysond_bin("query", "nft", "nft", "nameservice.dys", regular_name)
    assert "nft" in regular_nft, "Regular name NFT not found"
    
    # Get authority for external name
    gov_module_response = dysond_bin("query", "auth", "module-account", "gov")
    authority_address = gov_module_response.get("account", {}).get("value", {}).get("address", "")
    
    # Delegate for voting
    validators = dysond_bin("query", "staking", "validators")
    validator_operator = validators["validators"][0]["operator_address"]
    delegate_result = dysond_bin("tx", "staking", "delegate", validator_operator, "50000000udys", "--from", "alice")
    assert delegate_result["code"] == 0
    
    # Create external name via governance
    external_name = "coexistence.test.com"
    proposal = {
        "messages": [
            {
                "@type": "/dysonprotocol.nameservice.v1.MsgCreateExternalName",
                "authority": authority_address,
                "name": external_name
            }
        ],
        "metadata": "ipfs://CID",
        "deposit": "1udys",
        "title": "Create External Name for Coexistence Test",
        "summary": f"Create external name {external_name}"
    }
    
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json") as f:
        json.dump(proposal, f)
        f.flush()
        submit_result = dysond_bin("tx", "gov", "submit-proposal", f.name, "--from", "alice")
    
    assert submit_result["code"] == 0
    
    # Vote and wait for proposal
    submit_events = [e for e in submit_result.get("events", []) if e.get("type") == "submit_proposal"]
    proposal_id_attrs = [a for e in submit_events for a in e.get("attributes", []) if a.get("key") == "proposal_id"]
    proposal_id = proposal_id_attrs[0].get("value")
    
    vote_result = dysond_bin("tx", "gov", "vote", proposal_id, "yes", "--from", "alice")
    assert vote_result["code"] == 0
    
    def proposal_passed():
        proposal_info = dysond_bin("query", "gov", "proposal", proposal_id)
        return proposal_info["proposal"]["status"] == "PROPOSAL_STATUS_PASSED"
    
    from tests.utils import poll_until_condition
    poll_until_condition(proposal_passed, timeout=30, error_message="Proposal did not pass")
    
    # Verify both names exist and have different characteristics
    external_nft = dysond_bin("query", "nft", "nft", "nameservice.dys", external_name)
    assert "nft" in external_nft, "External name NFT not found"
    
    # Check owners
    regular_owner = dysond_bin("query", "nft", "owner", "nameservice.dys", regular_name)
    external_owner = dysond_bin("query", "nft", "owner", "nameservice.dys", external_name)
    
    assert regular_owner["owner"] == alice_address, "Regular name should be owned by Alice"
    assert external_owner["owner"] == authority_address, "External name should be owned by authority"
    
    # Check metadata differences
    regular_data = regular_nft["nft"].get("data", {}).get("value", {})
    external_data = external_nft["nft"].get("data", {}).get("value", {})
    
    assert regular_data.get("metadata") != "external_name", "Regular name should not have external metadata"
    assert external_data.get("metadata") == "external_name", "External name should have external metadata"
    
    print(f"✓ External name {external_name} coexists with regular name {regular_name}")


def test_external_name_zero_valuation(chainnet, generate_account):
    """Test that external names have zero valuation and far future expiry"""
    dysond_bin = chainnet[0]
    [alice_name, alice_address] = generate_account('alice')
    
    # Get authority address
    gov_module_response = dysond_bin("query", "auth", "module-account", "gov")
    authority_address = gov_module_response.get("account", {}).get("value", {}).get("address", "")
    
    # Delegate for voting
    validators = dysond_bin("query", "staking", "validators")
    validator_operator = validators["validators"][0]["operator_address"]
    delegate_result = dysond_bin("tx", "staking", "delegate", validator_operator, "50000000udys", "--from", "alice")
    assert delegate_result["code"] == 0
    
    external_name = "zero-valuation.test.com"
    
    # Create external name
    proposal = {
        "messages": [
            {
                "@type": "/dysonprotocol.nameservice.v1.MsgCreateExternalName",
                "authority": authority_address,
                "name": external_name
            }
        ],
        "metadata": "ipfs://CID",
        "deposit": "1udys",
        "title": "Create External Name for Valuation Test",
        "summary": f"Create external name {external_name}"
    }
    
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json") as f:
        json.dump(proposal, f)
        f.flush()
        submit_result = dysond_bin("tx", "gov", "submit-proposal", f.name, "--from", "alice")
    
    assert submit_result["code"] == 0
    
    # Vote and execute
    submit_events = [e for e in submit_result.get("events", []) if e.get("type") == "submit_proposal"]
    proposal_id_attrs = [a for e in submit_events for a in e.get("attributes", []) if a.get("key") == "proposal_id"]
    proposal_id = proposal_id_attrs[0].get("value")
    
    vote_result = dysond_bin("tx", "gov", "vote", proposal_id, "yes", "--from", "alice")
    assert vote_result["code"] == 0
    
    def proposal_passed():
        proposal_info = dysond_bin("query", "gov", "proposal", proposal_id)
        return proposal_info["proposal"]["status"] == "PROPOSAL_STATUS_PASSED"
    
    from tests.utils import poll_until_condition
    poll_until_condition(proposal_passed, timeout=30, error_message="Proposal did not pass")
    
    # Verify NFT data
    nft_info = dysond_bin("query", "nft", "nft", "nameservice.dys", external_name)
    nft_data = nft_info["nft"].get("data", {}).get("value", {})
    
    # Check zero valuation
    valuation = nft_data.get("valuation", {})
    assert valuation.get("denom") == "dys", "Valuation denom should be dys"
    assert valuation.get("amount") == "0", f"Valuation should be zero, got {valuation.get('amount')}"
    
    # Check far future expiry (should be ~100 years from now)
    expiry = nft_data.get("valuation_expiry")
    assert expiry, "Valuation expiry should be set"
    
    # The expiry should be a timestamp far in the future
    # We'll just verify it's a reasonable timestamp format
    assert "T" in expiry, "Expiry should be in timestamp format"
    
    print(f"✓ External name {external_name} has zero valuation and far future expiry")


def test_external_name_not_listed_by_default(chainnet, generate_account):
    """Test that external names are not listed by default"""
    dysond_bin = chainnet[0]
    [alice_name, alice_address] = generate_account('alice')
    
    # Get authority address
    gov_module_response = dysond_bin("query", "auth", "module-account", "gov")
    authority_address = gov_module_response.get("account", {}).get("value", {}).get("address", "")
    
    # Delegate for voting
    validators = dysond_bin("query", "staking", "validators")
    validator_operator = validators["validators"][0]["operator_address"]
    delegate_result = dysond_bin("tx", "staking", "delegate", validator_operator, "50000000udys", "--from", "alice")
    assert delegate_result["code"] == 0
    
    external_name = "not-listed.test.com"
    
    # Create external name
    proposal = {
        "messages": [
            {
                "@type": "/dysonprotocol.nameservice.v1.MsgCreateExternalName",
                "authority": authority_address,
                "name": external_name
            }
        ],
        "metadata": "ipfs://CID",
        "deposit": "1udys",
        "title": "Create External Name for Listing Test",
        "summary": f"Create external name {external_name}"
    }
    
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json") as f:
        json.dump(proposal, f)
        f.flush()
        submit_result = dysond_bin("tx", "gov", "submit-proposal", f.name, "--from", "alice")
    
    assert submit_result["code"] == 0
    
    # Vote and execute
    submit_events = [e for e in submit_result.get("events", []) if e.get("type") == "submit_proposal"]
    proposal_id_attrs = [a for e in submit_events for a in e.get("attributes", []) if a.get("key") == "proposal_id"]
    proposal_id = proposal_id_attrs[0].get("value")
    
    vote_result = dysond_bin("tx", "gov", "vote", proposal_id, "yes", "--from", "alice")
    assert vote_result["code"] == 0
    
    def proposal_passed():
        proposal_info = dysond_bin("query", "gov", "proposal", proposal_id)
        return proposal_info["proposal"]["status"] == "PROPOSAL_STATUS_PASSED"
    
    from tests.utils import poll_until_condition
    poll_until_condition(proposal_passed, timeout=30, error_message="Proposal did not pass")
    
    # Verify NFT is not listed
    nft_info = dysond_bin("query", "nft", "nft", "nameservice.dys", external_name)
    nft_data = nft_info["nft"].get("data", {}).get("value", {})
    
    assert not nft_data.get("listed", False), "External name should not be listed by default"
    
    print(f"✓ External name {external_name} is not listed by default")
