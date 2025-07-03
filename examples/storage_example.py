import json
from html import escape
from dys import get_script_address, get_executor_address, _msg, _query


def save_message(message):
    # the account that signed the transaction
    caller = get_executor_address()
    return _msg(
        {
            "@type": "/dysonprotocol.storage.v1.MsgStorageSet",
            "owner": get_script_address(),
            "index": f"greetings/{caller}",
            "data": json.dumps({"greeting": message}),
        }
    )


def wsgi(environ, start_response):
    # Define response status and headers
    status_code = "200 OK"
    headers = [("Content-Type", "text/html")]
    start_response(status_code, headers)

    # Prepare the query parameters
    query_params = {
        "@type": "/dysonprotocol.storage.v1.QueryStorageListRequest",
        "owner": get_script_address(),
        "index_prefix": "greetings/",
    }

    # Get messages from storage
    storage_result = _query(query_params)

    # Start building HTML output
    output = "<html><body>\n"
    output += "<h2>Storage Messages</h2>\n"

    # Process each entry from storage
    for entry in storage_result["entries"]:
        # Parse the JSON data
        data = json.loads(entry["data"])
        # Extract the address from the index (format: greetings/{address})
        sender_address = entry["index"].split("/")[1]
        output += f"<p>Message from {escape(sender_address)}: {escape(data['greeting'])}</p>\n"
    else:
        output += "<p>No messages found</p>\n"

    # Add the full storage query result for debugging
    output += "<h3>Storage Query Result</h3>\n"
    output += "<pre>" + escape(json.dumps(storage_result, indent=2)) + "</pre>\n"
    output += "<h3>Environment</h3>\n"
    output += (
        "<pre>"
        + escape(json.dumps(environ, indent=2, sort_keys=True, default=str))
        + "</pre>\n"
    )
    output += "</body></html>"

    return [output.encode()]
