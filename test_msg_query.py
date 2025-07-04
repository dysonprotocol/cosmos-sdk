from dys import _msg, _query, get_script_address
import json

def test_query_function():
    """Test the _query function by querying our script address balance."""
    query_params = {
        "@type": "/cosmos.bank.v1beta1.QueryBalanceRequest",
        "address": get_script_address(),
        "denom": "udys
    }
    result = _query(query_params)
    print("Query result:", result)
    return result

def test_msg_function():
    """Test the _msg function by setting a storage value."""
    test_key = "test_msg_key"
    test_value = "test_value"
    
    msg_params = {
        "@type": "/dysonprotocol.storage.v1.MsgStorageSet",
        "owner": get_script_address(),
        "index": test_key,
        "data": json.dumps({"test": test_value})
    }
    result = _msg(msg_params)
    print("Message result:", result)
    return result
