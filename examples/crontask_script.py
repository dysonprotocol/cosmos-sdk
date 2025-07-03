import datetime
from dys import _chain, get_script_address, get_executor_address


def create_quick_task():
    """
    Create a crontask scheduled to run in 3 seconds.

    This example demonstrates how to programmatically create a scheduled task
    using the crontask module. The task will send 1 dys token from the executor
    address back to itself after 3 seconds.

    Returns:
        dict: A dictionary containing information about the created task
    """
    # Get current time
    now = datetime.datetime.now()

    # Schedule time: 3 seconds from now
    scheduled_time = int((now + datetime.timedelta(seconds=3)).timestamp())

    # Expiry time: 1 day from now (the task will be marked as expired if not executed by this time)
    expiry_time = int((now + datetime.timedelta(days=1)).timestamp())

    # Create a simple message for bank transfer (1 dys token to the same address)
    # This serves as a demonstration, but you could include any valid message type
    msg_json = {
        "@type": "/cosmos.bank.v1beta1.MsgSend",
        "from_address": get_executor_address(),
        "to_address": get_executor_address(),
        "amount": [{"denom": "dys", "amount": "1"}],  # Using dys explicitly
    }

    # Create crontask message
    # This will schedule the above message to be executed at the specified time
    result = _msg(
        {
            "@type": "/dysonprotocol.crontask.v1.MsgCreateTask",
            "creator": get_executor_address(),
            "scheduled_timestamp": str(scheduled_time),
            "expiry_timestamp": str(expiry_time),
            "gas_limit": "200000",  # Set an appropriate gas limit for your transaction
            "gas_price": {"denom": "dys", "amount": "1"},  # Gas price for execution
            "msgs": [msg_json],  # You can include multiple messages in a single task
        }
    )

    # Calculate current timestamp using datetime
    current_time = int(datetime.datetime.now().timestamp())

    # Return useful information about the task
    return {
        "scheduled_time": scheduled_time,
        "current_time": current_time,
        "time_difference_seconds": scheduled_time - current_time,
        "expiry_time": expiry_time,
        "creator": get_executor_address(),
        "result": result,
    }


def _msg(msg):
    """
    Send a message request using _chain with JSON-encoded data.

    Args:
        msg (dict): The message to be sent

    Returns:
        dict: The result of the transaction
    """
    import json

    return _chain("Msg", json_msg=json.dumps(msg))
