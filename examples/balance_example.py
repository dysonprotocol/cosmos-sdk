from dys import _chain, get_script_address
import json


def query_balance(denom="dys"):
    address = get_script_address()
    query = {
        "@type": "/cosmos.bank.v1beta1.QueryBalanceRequest",
        "address": address,
        "denom": denom,
    }
    result = _chain("Query", json_query=json.dumps(query))
    return result


def get_my_balance():
    result = query_balance()
    if "result" in result and "balance" in result["result"]:
        balance = result["result"]["balance"]
        return f"Script address: {get_script_address()}\nBalance: {balance['amount']} {balance['denom']}"
    else:
        return f"Failed to get balance for {get_script_address()}: {result}"
