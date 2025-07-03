from dys import _chain, get_script_address, get_executor_address
import json
from urllib.parse import parse_qs


# The main function for Dyson WSGI scripts
def wsgi(environ, start_response):
    """WSGI application for Dyson Protocol."""
    # Parse query string
    query_string = environ.get("QUERY_STRING", "")
    query_params = parse_qs(query_string)

    # Get the request method
    request_method = environ.get("REQUEST_METHOD", "GET")

    # Initialize name variable
    name = "world"

    # Handle GET request - get name from query parameters
    if request_method == "GET":
        name = query_params.get("name", ["world"])[0]

    # Handle POST request - read POST data
    elif request_method == "POST":
        try:
            # Get content length
            content_length = int(environ.get("CONTENT_LENGTH", 0))

            # Read POST data
            if content_length > 0:
                post_data = environ["wsgi.input"].read(content_length)
                post_data = post_data.decode("utf-8")

                # Parse POST data
                if environ.get("CONTENT_TYPE") == "application/x-www-form-urlencoded":
                    post_params = parse_qs(post_data)
                    name = post_params.get("name", ["world"])[0]
                else:
                    # For debugging
                    name = f"POSTUser-{post_data}"
        except Exception as e:
            name = f"Error: {str(e)}"

    # Create response
    status = "200 OK"
    response_body = f"hi {name}"

    # Add some details about the request for debugging
    response_body += f"\n\nRequest Method: {request_method}"
    response_body += f"\nQuery String: {query_string}"
    response_body += f"\nPath Info: {environ.get('PATH_INFO', '')}"
    if request_method == "POST":
        response_body += f"\nContent Type: {environ.get('CONTENT_TYPE', '')}"
        response_body += f"\nContent Length: {environ.get('CONTENT_LENGTH', '')}"

    # Headers
    response_headers = [
        ("Content-Type", "text/plain"),
        ("Content-Length", str(len(response_body))),
    ]

    # Send response
    start_response(status, response_headers)
    return [response_body.encode("utf-8")]


# Functions that can be called directly
def say_hello(name="world"):
    """Return a hello message."""
    return f"Hello, {name}!"
