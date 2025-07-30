import pytest
import json
from utils import poll_until_condition
import tempfile

# Helper: Poll until a governance proposal reaches a final state
# Uses dysond_bin for queries

def poll_until_proposal_passes(dysond_bin, proposal_id: str, timeout: int = 60):
    def has_proposal_reached_final_state():
        proposal_result = dysond_bin("query", "gov", "proposal", proposal_id)
        status = proposal_result["proposal"]["status"]
        print(f"Current proposal status: {status}")
        return status in [
            "PROPOSAL_STATUS_PASSED",
            "PROPOSAL_STATUS_REJECTED",
            "PROPOSAL_STATUS_FAILED"
        ]
    poll_until_condition(
        has_proposal_reached_final_state,
        timeout=timeout,
        error_message="Timeout waiting for proposal to reach final state"
    )
    proposal_result = dysond_bin("query", "gov", "proposal", proposal_id)
    final_status = proposal_result["proposal"]["status"]  # Fixed: get status from proposal object
    return final_status

def register_name(chainnet, generate_account, faucet):
    dysond_bin = chainnet[0]
    [alice_name, alice_address] = generate_account('alice', 1000)
    name = f"testname{alice_address[:10]}.dys"
    salt = "testsalt"
    # Compute hash
    query_result = dysond_bin("query", "nameservice", "compute-hash", "--name", name, "--salt", salt, "--committer", alice_address)
    hex_hash = query_result["hex_hash"]
    print(f"Compute hash result: {hex_hash}")
    # Commit
    commit_result = dysond_bin("tx", "nameservice", "commit", "--commitment", hex_hash, "--valuation", "100udys", "--from", alice_name)
    print(f"Commit result: {commit_result}")
    assert commit_result["code"] == 0, commit_result["raw_log"]
    # Reveal
    reveal_result = dysond_bin("tx", "nameservice", "reveal", "--name", name, "--salt", salt, "--from", alice_name)
    assert reveal_result["code"] == 0, reveal_result["raw_log"]
    return {"name": name, "alice_name": alice_name, "alice_address": alice_address}

def set_bid_timeout_via_gov(dysond_bin, proposer_name, bid_timeout_value: str):
    """Set bid timeout via governance proposal"""
    # Get current params
    current_params = dysond_bin("query", "nameservice", "params")
    current_allowed_denoms = current_params.get("params", {}).get("allowed_denoms", ["udys"])
    current_reject_fee_percent = current_params.get("params", {}).get("reject_bid_valuation_fee_percent", "0.03")
    current_minimum_bid_percent_increase = current_params.get("params", {}).get("minimum_bid_percent_increase", "0.01")
    current_mint_fee_per_coin = current_params.get("params", {}).get("mint_fee_per_coin", "1.0")
    
    # Query gov module account address
    gov_module_response = dysond_bin("query", "auth", "module-account", "gov")
    gov_address = gov_module_response.get("account", {}).get("value", {}).get("address", "")
    assert gov_address

    # Get validator operator address
    validators = dysond_bin("query", "staking", "validators")
    validator_operator = validators["validators"][0]["operator_address"]
    
    # Delegate tokens from Alice to validator so Alice has voting power
    delegate_result = dysond_bin("tx", "staking", "delegate", validator_operator, "50000000udys", "--from", "alice", "--yes")
    assert delegate_result["code"] == 0, f"Failed to delegate: {delegate_result['raw_log']}"

    proposal = {
        "messages": [
            {
                "@type": "/dysonprotocol.nameservice.v1.MsgUpdateParams",
                "authority": gov_address,
                "params": {
                    "bid_timeout": bid_timeout_value,
                    "allowed_denoms": current_allowed_denoms,
                    "reject_bid_valuation_fee_percent": current_reject_fee_percent,
                    "minimum_bid_percent_increase": current_minimum_bid_percent_increase,
                    "mint_fee_per_coin": current_mint_fee_per_coin
                }
            }
        ],
        "metadata": "ipfs://CID",
        "deposit": "1udys",
        "title": "Update Nameservice Parameters",
        "summary": f"Update bid_timeout to {bid_timeout_value} for testing"
    }
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=True) as f:
        json.dump(proposal, f)
        f.flush()
        proposal_file = f.name
        # Submit proposal using Alice (who now has voting power)
        tx_result = dysond_bin("tx", "gov", "submit-proposal", proposal_file, "--from", "alice", "--keyring-backend", "test", "--yes")
        
    print(f"Submit proposal result: {tx_result}")
    tx_result = dysond_bin("query", "wait-tx", tx_result["txhash"])
    print(f"Proposal result: {tx_result}")

    # Extract proposal ID using list comprehensions
    submit_events = [e for e in tx_result.get("events", []) if e.get("type") == "submit_proposal"]
    assert submit_events, "No submit_proposal event found"
    
    proposal_id_attrs = [a for a in submit_events[0].get("attributes", []) if a.get("key") == "proposal_id"]
    assert proposal_id_attrs, "No proposal_id attribute found"
    
    proposal_id = proposal_id_attrs[0].get("value")

    # Vote with Alice (who has voting power through delegation)
    vote_result = dysond_bin("tx", "gov", "vote", proposal_id, "yes", "--from", "alice", "--keyring-backend", "test", "--yes")
    vote_tx_result = dysond_bin("query", "wait-tx", vote_result["txhash"])
    print(f"Vote result: {vote_tx_result}")
    assert vote_tx_result["code"] == 0, vote_tx_result["raw_log"]

    # Wait for proposal to pass
    poll_until_proposal_passes(dysond_bin, proposal_id)
    
    # Check final proposal status
    final_proposal = dysond_bin("query", "gov", "proposal", proposal_id)
    final_status = final_proposal["proposal"]["status"]
    assert final_status == "PROPOSAL_STATUS_PASSED", f"Governance proposal failed with status: {final_status}"

    # Verify params were updated
    params_result = dysond_bin("query", "nameservice", "params")
    print(f"Final nameservice params: {params_result}")
    assert params_result["params"]["bid_timeout"] == bid_timeout_value, f"Bid timeout not updated correctly"

def test_update_nameservice_params_via_gov(chainnet, generate_account, faucet):
    dysond_bin = chainnet[0]
    [alice_name, alice_address] = generate_account('alice')
    faucet(alice_address, denom="udys", amount="25000")
    
    # Get validator operator address and delegate tokens for voting power
    validators = dysond_bin("query", "staking", "validators")
    validator_operator = validators["validators"][0]["operator_address"]
    delegate_result = dysond_bin("tx", "staking", "delegate", validator_operator, "50000000udys", "--from", alice_name, "--yes")
    assert delegate_result["code"] == 0, f"Failed to delegate: {delegate_result['raw_log']}"
    
    # Get current params
    current_params = dysond_bin("query", "nameservice", "params")
    current_allowed_denoms = current_params.get("params", {}).get("allowed_denoms", ["udys"])
    current_reject_fee_percent = current_params.get("params", {}).get("reject_bid_valuation_fee_percent", "0.03")
    current_minimum_bid_percent_increase = current_params.get("params", {}).get("minimum_bid_percent_increase", "0.01")
    # Query gov module account address
    gov_module_response = dysond_bin("query", "auth", "module-account", "gov")
    gov_address = gov_module_response.get("account", {}).get("value", {}).get("address", "")
    assert gov_address
    proposal = {
        "messages": [
            {
                "@type": "/dysonprotocol.nameservice.v1.MsgUpdateParams",
                "authority": gov_address,
                "params": {
                    "bid_timeout": "1s",
                    "allowed_denoms": current_allowed_denoms,
                    "reject_bid_valuation_fee_percent": current_reject_fee_percent,
                    "minimum_bid_percent_increase": current_minimum_bid_percent_increase
                }
            }
        ],
        "metadata": "ipfs://CID",
        "deposit": "1udys",
        "title": "Update Nameservice Parameters",
        "summary": "Update bid_timeout to 4s for testing"
    }
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=True) as f:
        json.dump(proposal, f)
        f.flush()
        proposal_file = f.name
        tx_result = dysond_bin("tx", "gov", "submit-proposal", proposal_file, "--from", alice_name, "--keyring-backend", "test", "--yes")
    print(f"Submit proposal result: {tx_result}")
    tx_result = dysond_bin("query", "wait-tx", tx_result["txhash"])
    print(f"Proposal result: {tx_result}")
    #assert tx_result["code"] == 0, tx_result["raw_log"]
    # Extract proposal ID using list comprehensions
    submit_events = [e for e in tx_result.get("events", []) if e.get("type") == "submit_proposal"]
    assert submit_events, "No submit_proposal event found"
    
    proposal_id_attrs = [a for a in submit_events[0].get("attributes", []) if a.get("key") == "proposal_id"]
    assert proposal_id_attrs, "No proposal_id attribute found"
    
    proposal_id = proposal_id_attrs[0].get("value")
    # Vote
    tx_result = dysond_bin("tx", "gov", "vote", proposal_id, "yes", "--from", alice_name, "--keyring-backend", "test", "--yes")
    tx_result = dysond_bin("query", "wait-tx", tx_result["txhash"])
    print(f"Vote result: {tx_result}")
    assert tx_result["code"] == 0, tx_result["raw_log"]
    # Wait for proposal to pass
    poll_until_proposal_passes(dysond_bin, proposal_id)
    params_result = dysond_bin("query", "nameservice", "params")
    print(f"Final nameservice params: {params_result}")


def test_claim_before_timeout_fails(chainnet, generate_account, faucet):
    dysond_bin = chainnet[0]
    [alice_name, alice_address] = generate_account('alice')
    faucet(alice_address, denom="udys", amount="25000")
    
    # Set bid timeout to 10 seconds via governance proposal
    set_bid_timeout_via_gov(dysond_bin, alice_name, "10s")
    
    [bob_name, bob_address] = generate_account('bob')
    faucet(bob_address, denom="udys", amount="1000")
    registered_name = register_name(chainnet, generate_account, faucet)
    alice_address = registered_name["alice_address"]
    
    # Place a bid from Bob
    bid_amount = "500udys"
    print(f"Placing bid of {bid_amount} from Bob")
    tx_result = dysond_bin("tx", "nameservice", "place-bid", "--nft-class-id", "nameservice.dys", "--nft-id", registered_name["name"], "--bid-amount", bid_amount, "--from", bob_name, "--keyring-backend", "test", "--yes")
    assert tx_result["code"] == 0, tx_result["raw_log"]
    
    print(f"Attempting to claim immediately (should fail)")
    # Attempt to claim immediately (should fail)
    claim_result = dysond_bin("tx", "nameservice", "claim-bid", "--nft-class-id", "nameservice.dys", "--nft-id", registered_name["name"], "--from", bob_name, "--keyring-backend", "test", "--yes")
    print(f"Claim result: {claim_result}")
    
    # Check that the transaction failed with the expected error
    assert claim_result["code"] != 0, "Expected claim transaction to fail, but it succeeded"
    assert "bid timeout has not elapsed" in claim_result["raw_log"], f"Expected 'bid timeout has not elapsed' error, but got: {claim_result['raw_log']}"

    # Verify ownership was not transferred
    nft_info = dysond_bin("query", "nft", "owner", "nameservice.dys", registered_name["name"], "--output", "json")
    assert nft_info["owner"] == alice_address


def test_claim_after_timeout_succeeds(chainnet, generate_account, faucet):
    dysond_bin = chainnet[0]
    [alice_name, alice_address] = generate_account('alice')
    faucet(alice_address, denom="udys", amount="25000")
    
    # Set bid timeout to 100ms via governance proposal for fast test
    set_bid_timeout_via_gov(dysond_bin, alice_name, "100ms")
    
    [bob_name, bob_address] = generate_account('bob')
    faucet(bob_address, denom="udys", amount="1000")
    registered_name = register_name(chainnet, generate_account, faucet)
    alice_address = registered_name["alice_address"]
    
    # Place a bid from Bob
    bid_amount = "500udys"
    print(f"Placing bid of {bid_amount} from Bob")
    bid_result = dysond_bin("tx", "nameservice", "place-bid", "--nft-class-id", "nameservice.dys", "--nft-id", registered_name["name"], "--bid-amount", bid_amount, "--from", bob_name, "--keyring-backend", "test", "--yes")
    assert bid_result["code"] == 0, bid_result["raw_log"]
    
    # Wait for bid timeout to elapse by waiting for blocks to pass
    # With 100ms timeout and ~500ms block time, should pass after 1 block
    def timeout_elapsed():
        status_result = dysond_bin("status")
        current_block = int(status_result["sync_info"]["latest_block_height"])
        bid_block = int(bid_result["height"])
        # Wait for at least 1 block to pass to ensure timeout has elapsed
        return (current_block - bid_block) >= 1

    poll_until_condition(timeout_elapsed, timeout=10, error_message="Bid timeout did not elapse")
    
    print(f"Attempting to claim after timeout (should succeed)")
    # Attempt to claim after timeout (should succeed)
    claim_result = dysond_bin("tx", "nameservice", "claim-bid", "--nft-class-id", "nameservice.dys", "--nft-id", registered_name["name"], "--from", bob_name, "--keyring-backend", "test", "--yes")
    print(f"Claim result: {claim_result}")
    
    # Check that the transaction succeeded
    assert claim_result["code"] == 0, f"Expected claim transaction to succeed, but got error: {claim_result.get('raw_log', 'Unknown error')}"
    
    # Verify that Bob now owns the NFT
    owner_result = dysond_bin("query", "nft", "owner", "nameservice.dys", registered_name["name"], "--output", "json")
    assert owner_result["owner"] == bob_address, f"Expected Bob to own the NFT, but owner is {owner_result['owner']}" 