from dys import (
    _msg,
    _query,
    get_script_address,
    emit_event,
    get_executor_address,
    get_block_info,
)
import json
import base64


def encode_json(json_data):
    return _query(
        {
            "@type": "/dysonprotocol.script.v1.QueryEncodeJsonRequest",
            "json": json.dumps(json_data),
        }
    )


def decode_bytes(type_url, encoded_bytes):
    return _query(
        {
            "@type": "/dysonprotocol.script.v1.QueryDecodeBytesRequest",
            "type_url": type_url,
            "bytes": encoded_bytes,
        }
    )


def decode_msg_module_query_safe_response(encoded_bytes):
    ret = decode_bytes(
        "/ibc.applications.interchain_accounts.host.v1.MsgModuleQuerySafeResponse",
        encoded_bytes,
    )["json"]
    print("Ret", ret)
    b64_response = json.loads(ret)["responses"][0]
    print("B64 Response", b64_response)
    response = base64.b64decode(b64_response)
    print("Response", response)


def save_message(message="Hello, World!", *args, **kwargs):
    # the account that signed the transaction
    caller = get_executor_address()
    block_info = get_block_info()
    height = block_info["height"]
    return _msg(
        {
            "@type": "/dysonprotocol.storage.v1.MsgStorageSet",
            "owner": get_script_address(),
            "index": f"greetings_v2/{height:010d}/{caller}",
            "data": json.dumps({"greeting": message, "args": args, "kwargs": kwargs}),
        }
    )


def create_ica_account(
    connection_id="connection-0", host_connection_id=None, encoding="proto3json"
):
    """
    Create a new Interchain Account (ICA) on the remote chain
    
    Args:
        connection_id: The IBC connection ID to use for the controller side
        host_connection_id: The connection ID on the host side (defaults to same as connection_id)
        encoding: The encoding format to use ("proto3json" or "protobuf")
        
    Returns:
        Dictionary with registration result
        
    Note:
        This is equivalent to:
        dysond tx interchain-accounts controller register connection-0 \\
          --version '{"version":"ics27-1","controller_connection_id":"connection-0",...}'
    """
    if host_connection_id is None:
        host_connection_id = connection_id

    # Construct the version JSON as required by ICA specification
    version_data = {
        "version": "ics27-1",
        "controller_connection_id": connection_id,
        "host_connection_id": host_connection_id,
        "address": "",  # Will be assigned by the host chain
        "encoding": encoding,
        "tx_type": "sdk_multi_msg",
    }

    emit_event(
        "ica_create_account_start",
        json.dumps(
            {
                "connection_id": connection_id,
                "host_connection_id": host_connection_id,
                "encoding": encoding,
                "owner": get_script_address(),
            }
        ),
    )

    try:
        # Send the ICA registration message
        tx_result = _msg(
            {
                "@type": "/ibc.applications.interchain_accounts.controller.v1.MsgRegisterInterchainAccount",
                "owner": get_script_address(),
                "connection_id": connection_id,
                "version": json.dumps(version_data),
            }
        )

        emit_event(
            "ica_create_account_success",
            json.dumps({"connection_id": connection_id, "tx_result": tx_result}),
        )

        return {
            "status": "success",
            "connection_id": connection_id,
            "version": version_data,
            "tx_result": tx_result,
        }

    except Exception as e:
        emit_event(
            "ica_create_account_error",
            json.dumps({"connection_id": connection_id, "error": str(e)}),
        )

        return {"status": "error", "connection_id": connection_id, "message": str(e)}


def query_remote_balances(
    connection_id="connection-0",  # The connection ID between controller and host chains
    target_address="",  # Address on host chain to query the balance of
    token_amount=1,  # Amount of tokens to send in the MsgSend
):
    """
    Query the all balances of an address on a remote chain using Interchain Accounts

    Args:
        connection_id: The IBC connection ID to use
        target_address: Address on host chain to check balance of
        token_amount: Amount of IBC tokens to send (default: "1")

    Returns:
        Dictionary with query results

    Note:
        Acknowledgements are now logged by the ContractKeeper in the Script module.
        This can be extended to store and query acknowledgements directly from on-chain scripts.
    """
    if not target_address:
        raise ValueError("Target address is required")

    ica_info = _query(
        {
            "@type": "/ibc.applications.interchain_accounts.controller.v1.QueryInterchainAccountRequest",
            "owner": get_script_address(),
            "connection_id": connection_id,
        }
    )

    emit_event("get_script_address", get_script_address())
    emit_event("ica_info", json.dumps(ica_info))

    # Construct the request to query the balance
    balance_query_encoded = encode_json(
        {
            "@type": "/cosmos.bank.v1beta1.QueryAllBalancesRequest",
            "address": target_address,
        }
    )

    # Log the balance query response for debugging
    emit_event("balance_query_encoded", json.dumps(balance_query_encoded))

    # Construct the ModuleQuerySafe message
    module_query_safe = {
        "@type": "/ibc.applications.interchain_accounts.host.v1.MsgModuleQuerySafe",
        "signer": ica_info["address"],
        "requests": [
            {
                "path": "/cosmos.bank.v1beta1.Query/AllBalances",
                "data": balance_query_encoded["bytes"],
            }
        ],
    }

    # bank send msg
    bank_send_msg = {
        "@type": "/cosmos.bank.v1beta1.MsgSend",
        "from_address": ica_info["address"],
        "to_address": target_address,
        "amount": [
            {
                "denom": "ibc/3B2294AF63D402DF9B10DA43CEC03677D9041297A1031AB1AFC789C492280D79",
                "amount": str(token_amount),
            }
        ],
    }

    emit_event("module_query_safe", json.dumps(module_query_safe))

    # Get the script's address (controller address)
    controller_address = get_script_address()

    # Get the owner's ICA (assuming it's already established)
    try:
        # Send the transaction with correctly formatted packet data
        tx_result = _msg(
            {
                "@type": "/ibc.applications.interchain_accounts.controller.v1.MsgSendTx",
                "owner": get_script_address(),
                "connection_id": connection_id,
                "packet_data": {
                    "type": "TYPE_EXECUTE_TX",
                    "data": base64.b64encode(
                        json.dumps(
                            {"messages": [module_query_safe, bank_send_msg]}
                        ).encode()
                    ).decode(),
                    "memo": json.dumps(
                        {
                            "src_callback": {
                                "address": get_script_address(),
                                "function_name": "save_message",
                                "kwargs": (
                                    {
                                        "greeting": "Hello, World!",
                                        "another_kwargs": "another kwarg value",
                                        "fooling": "around",
                                    }
                                ),
                                "args": (
                                    [
                                        "arg the first",
                                        "arg the second",
                                        "some other arg",
                                    ]
                                ),
                            }
                        }
                    ),
                },
                "relative_timeout": 10000000000,  # 10 seconds in nanoseconds
            }
        )

        return {"MsgSendTx_result": tx_result}

    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
        }
