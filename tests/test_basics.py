import pytest
import os


def test_address_retrieval(chainnet, generate_account, faucet):
    """Test that we can retrieve addresses for test accounts."""
    dysond_bin = chainnet[0]
    
    [alice_name, alice_address] = generate_account('alice')
    [bob_name, bob_address] = generate_account('bob')
    
    # Test that addresses are valid bech32 addresses
    assert alice_address.startswith('dys2')
    assert bob_address.startswith('dys2')
    
    # Test that addresses are different
    assert alice_address != bob_address 

    assert alice_name.startswith('alice')
    assert bob_name.startswith('bob')

    faucet(alice_address, denom="udys", amount="1000")
    faucet(bob_address, denom="udys", amount="1000")

    assert dysond_bin("query", "bank", "balances", alice_address)["balances"][0]["denom"] == "udys"
    assert dysond_bin("query", "bank", "balances", bob_address)["balances"][0]["denom"] == "udys"