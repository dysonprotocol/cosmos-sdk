import pytest
import secrets
from tests.conftest import poll_until_condition


def test_max_annual_pct_fee(chainnet, generate_account, faucet, register_name):
    """Test that max_annual_pct_fee guards against unexpected annual percentage fees when setting valuation"""
    dysond_bin = chainnet[0]
    
    # Setup accounts
    [alice_name, alice_address] = generate_account('alice')
    faucet(alice_address, denom="udys", amount="10000")
    
    # Register a name with initial valuation using the fixture
    name = register_name(dysond_bin, alice_name, alice_address, valuation="100udys")
    
    # Verify the NFT exists
    nft_info = dysond_bin("query", "nft", "nft", "nameservice.dys", name)
    assert "nft" in nft_info, "NFT not found after registration"
    
    # Check the NFT class data to see annual_pct
    class_info = dysond_bin("query", "nft", "class", "nameservice.dys")
    print(f"NFT class info: {class_info}")
    
    # Get the annual_pct - assume class_data is always a dict
    class_data = class_info.get("class", {}).get("data", {})
    annual_pct = class_data.get("value", {}).get("annual_pct", "0")
    print(f"Annual PCT for nameservice.dys: {annual_pct}")

    # Test 1: Set valuation with sufficient max_annual_pct_fee (should succeed)
    # Increase valuation from 100 to 200 dys
    # The annual_pct is 0.01 (1%), so we set max to 2% to be safe
    success_result = dysond_bin("tx", "nameservice", "set-valuation", 
                               "--class-id", "nameservice.dys", 
                               "--nft-id", name, 
                               "--valuation", "200udys",
                               "--max-annual-pct-fee", "0.02",  # 2% max
                               "--from", alice_name)
    assert success_result["code"] == 0, f"Transaction should have succeeded: {success_result.get('raw_log', '')}"
    print("Successfully set valuation to 200udys with max annual pct fee 2%")
    
    # Verify the valuation was updated
    updated_nft_info = dysond_bin("query", "nft", "nft", "nameservice.dys", name)
    assert "nft" in updated_nft_info, "NFT not found after valuation update"
    
    # Test 2: Set valuation with insufficient max_annual_pct_fee (should fail)
    # Try to increase valuation to 500 dys
    # The annual_pct is 0.01 (1%), so we set max to 0.005 (0.5%) which should fail
    high_valuation = 500
    insufficient_max_pct = "0.005"  # 0.5% - lower than actual 1%
    
    failed_result = dysond_bin("tx", "nameservice", "set-valuation", 
                             "--class-id", "nameservice.dys", 
                             "--nft-id", name, 
                             "--valuation", f"{high_valuation}udys",
                             "--max-annual-pct-fee", insufficient_max_pct,
                             "--from", alice_name)
    
    # Check that the transaction failed with the expected error
    assert failed_result["code"] != 0, "Transaction should have failed with insufficient max annual pct fee"
    assert "exceeds maximum allowed" in failed_result.get("raw_log", ""), "Expected error message about exceeding max annual pct fee"
    print(f"Correctly rejected valuation update with insufficient max annual pct fee: {insufficient_max_pct}")
    
    # Test 3: Set valuation without specifying max_annual_pct_fee (backwards compatible)
    # This should succeed as it maintains backwards compatibility
    compat_result = dysond_bin("tx", "nameservice", "set-valuation", 
                             "--class-id", "nameservice.dys", 
                             "--nft-id", name, 
                             "--valuation", "250udys",
                             "--from", alice_name)
    assert compat_result["code"] == 0, f"Backwards compatible transaction should have succeeded: {compat_result.get('raw_log', '')}"
    print("Successfully set valuation to 250udys without specifying max annual pct fee (backwards compatible)")
    
    print("All max_annual_pct_fee tests passed!")


 