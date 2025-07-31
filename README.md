# Dyson Protocol – Make Dwapps, Get Paid

**Host Python scripts, serve decentralized websites, and run scheduled tasks with trustless, censorship-resistant execution. Trade names in a dynamic on-chain market, mint custom tokens and NFTs, and store arbitrary data—all fully on-chain.**

---

## What & Why

- **Problem**  
  - DApp UIs still load from centralized servers—developers host them off-chain, and end-users can’t self-host or audit the code.

- **Solution**  
  - Store HTML/CSS/JS assets in the chain’s storage so browsers load UI from the ledger.  
  - Push application logic on-chain and execute periodic jobs (crontasks) without any off-chain trigger.  
  - Run a dynamic on-chain name market using Harberger-style fees.  
  - Mint custom tokens and NFT classes based on on-chain names.  
  - Store arbitrary data in the chain’s storage module.

- **Key Use Cases**  
  - **Autonomous payouts**: schedule hourly dividend distributions without users having to claim.  
  - **Timed auctions**: start and end bids exactly on-chain, with no external cron.  
  - **Game rounds**: progress players automatically through time-boxed stages.  
  - **Price oracles**: post market data at fixed intervals, fully on-chain.  
  - **Nameservice-driven assets**: register and trade domain-backed NFTs in a live marketplace.

- **Outcome**  
  - DWapp developers host, verify, and update every layer—from UI to scheduling—directly on the chain. No servers, no hidden dependencies, fully trustless.


## Installation

### 1. Build the Dyson Protocol binary




```bash
%%bash
make install
```

    Installing dysond binary...


### 2. Create new accounts
dysond keys add alice 
dysond keys add bob
### 2. Update the On-chain Python Script

This example uploads a Python script that demonstrates storage operations. The full script is available at [examples/storage_example.py](examples/storage_example.py).

**Key Functions in the Script** (excerpt):

```python
def save_message(message):
    # the account that signed the transaction
    caller = get_executor_address()
    _msg({"@type":"/dysonprotocol.storage.v1.MsgStorageSet","owner": get_script_address() ,"index":f"greetings/{caller}","data": json.dumps({"greeting": message})})

def wsgi(environ, start_response):
    # Define response status and headers
    status_code = "200 OK"
    headers = [("Content-Type", "text/html")]
    start_response(status_code, headers)

    # Prepare the query parameters
    query_params = {
        "@type":"/dysonprotocol.storage.v1.QueryStorageListRequest",
        "owner": get_script_address(),
        "index_prefix":"greetings/"
    }
    
# ... more code in the full example ...
```

Let's see the full script:


```bash
%%bash
cat examples/storage_example.py
```

    import json
    from html import escape
    from dys import get_script_address, get_executor_address, _msg, _query
    
    def save_message(message):
        # the account that signed the transaction
        caller = get_executor_address()
        return _msg({"@type":"/dysonprotocol.storage.v1.MsgStorageSet","owner": get_script_address() ,"index":f"greetings/{caller}","data": json.dumps({"greeting": message})})
    
    def wsgi(environ, start_response):
        # Define response status and headers
        status_code = "200 OK"
        headers = [("Content-Type", "text/html")]
        start_response(status_code, headers)
    
        # Prepare the query parameters
        query_params = {"@type":"/dysonprotocol.storage.v1.QueryStorageListRequest","owner": get_script_address() ,"index_prefix":"greetings/"}
        
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
        output += "<pre>" + escape(json.dumps(environ, indent=2, sort_keys=True, default=str)) + "</pre>\n"
        output += "</body></html>"
        
        return [output.encode()]


Now let's upload the script to the chain using Alice's address:


```bash
%%bash
ALICE_ADDRESS=$(dysond keys show -a alice)
dysond tx script update --from $ALICE_ADDRESS -y -o json --gas 500000 --code "$(cat examples/storage_example.py)" |  dysond q wait-tx -o json | jq '{height, txhash, code, gas_wanted, gas_used, "script_version": .events[] | select(.type=="dysonprotocol.script.v1.EventUpdateScript") | .attributes[] | select(.key=="version") | .value}'
```

    {
      "height": "6",
      "txhash": "EC09558601BE2580B407ED27BA24BEEBA9D9B2BBBC7CFB7439AD54B6F4823BA8",
      "code": 0,
      "gas_wanted": "500000",
      "gas_used": "107496",
      "script_version": "\"1\""
    }


### 3. Execute the Script Function

Invoke the `save_message` function using Bob's account, passing `"my name is bob"` as an argument:


```bash
%%bash
ALICE_ADDRESS=$(dysond keys show -a alice)
# Save the message to the storage
dysond tx script exec-script --from bob --script-address $ALICE_ADDRESS --function-name save_message --args '["my name is <b>bob</b>"]' -y  | dysond query wait-tx -o json | ./scripts/parse_exec_script_tx.py | jq 
```

    {
      "code": 0,
      "script_result": {
        "result": {
          "cumsize": 10484,
          "exception": null,
          "gas_limit": 200000,
          "nodes_called": 30,
          "result": {
            "@type": "/dysonprotocol.storage.v1.MsgStorageSetResponse"
          },
          "script_gas_consumed": 62160,
          "stdout": ""
        },
        "attached_message_results": []
      },
      "raw_log": ""
    }


### 4. Query the WSGI Endpoint

Finally, confirm the data is stored and accessible via an HTTP request to the script's WSGI endpoint:


```bash
%%bash
ALICE_ADDRESS=$(dysond keys show -a alice)
DWAPP_SERVER_ADDRESS=$(dysond config get app dwapp.address | tr -d '"')
DWAPP_URL="http://$ALICE_ADDRESS.$DWAPP_SERVER_ADDRESS/some-path?query=some-query"
curl -v $DWAPP_URL
```

    * Host dys1prvefcdgdnh2cpas6rnnval84n0gv2r28tklr4.localhost:8000 was resolved.
    * IPv6: ::1
    * IPv4: 127.0.0.1
      % Total    % Received % Xferd  Average Speed   Time    Time     Time  Current
                                     Dload  Upload   Total   Spent    Left  Speed
      0     0    0     0    0     0      0      0 --:--:-- --:--:-- --:--:--     0*   Trying [::1]:8000...
    * connect to ::1 port 8000 from ::1 port 57385 failed: Connection refused
    *   Trying 127.0.0.1:8000...
    * Connected to dys1prvefcdgdnh2cpas6rnnval84n0gv2r28tklr4.localhost (127.0.0.1) port 8000
    > GET /some-path?query=some-query HTTP/1.1
    > Host: dys1prvefcdgdnh2cpas6rnnval84n0gv2r28tklr4.localhost:8000
    > User-Agent: curl/8.6.0
    > Accept: */*
    > 
    < HTTP/1.1 200 OK
    < Date: Tue, 13 May 2025 16:31:20 GMT
    < Content-Length: 2035
    < Content-Type: text/html; charset=utf-8
    < 
    { [2035 bytes data]
    100  2035  100  2035    0     0  12866      0 --:--:-- --:--:-- --:--:-- 12879
    * Connection #0 to host dys1prvefcdgdnh2cpas6rnnval84n0gv2r28tklr4.localhost left intact


    <html><body>
    <h2>Storage Messages</h2>
    <p>Message from dys18lm54xtj4ar7jmw85zpkvj9gaze3509xvlmls0: my name is &lt;b&gt;bob&lt;/b&gt;</p>
    <p>No messages found</p>
    <h3>Storage Query Result</h3>
    <pre>{
      &quot;@type&quot;: &quot;/dysonprotocol.storage.v1.QueryStorageListResponse&quot;,
      &quot;entries&quot;: [
        {
          &quot;owner&quot;: &quot;dys1prvefcdgdnh2cpas6rnnval84n0gv2r28tklr4&quot;,
          &quot;index&quot;: &quot;greetings/dys18lm54xtj4ar7jmw85zpkvj9gaze3509xvlmls0&quot;,
          &quot;data&quot;: &quot;{\&quot;greeting\&quot;: \&quot;my name is &lt;b&gt;bob&lt;/b&gt;\&quot;}&quot;
        }
      ],
      &quot;pagination&quot;: {
        &quot;next_key&quot;: null,
        &quot;total&quot;: &quot;1&quot;
      }
    }</pre>
    <h3>Environment</h3>
    <pre>{
      &quot;CONTENT_LENGTH&quot;: &quot;&quot;,
      &quot;CONTENT_TYPE&quot;: &quot;text/plain&quot;,
      &quot;GATEWAY_INTERFACE&quot;: &quot;CGI/1.1&quot;,
      &quot;HTTP_ACCEPT&quot;: &quot;*/*&quot;,
      &quot;HTTP_USER_AGENT&quot;: &quot;curl/8.6.0&quot;,
      &quot;PATH_INFO&quot;: &quot;/some-path&quot;,
      &quot;QUERY_STRING&quot;: &quot;query=some-query&quot;,
      &quot;REMOTE_ADDR&quot;: &quot;0.0.0.0&quot;,
      &quot;REMOTE_HOST&quot;: &quot;&quot;,
      &quot;REQUEST_METHOD&quot;: &quot;GET&quot;,
      &quot;SCRIPT_NAME&quot;: &quot;&quot;,
      &quot;SERVER_NAME&quot;: &quot;dysonprotocol&quot;,
      &quot;SERVER_PORT&quot;: &quot;&quot;,
      &quot;SERVER_PROTOCOL&quot;: &quot;HTTP/1.1&quot;,
      &quot;SERVER_SOFTWARE&quot;: &quot;WSGIServer/0.2&quot;,
      &quot;wsgi.errors&quot;: &quot;&lt;_io.TextIOWrapper name=&#x27;&lt;stderr&gt;&#x27; mode=&#x27;w&#x27; encoding=&#x27;utf-8&#x27;&gt;&quot;,
      &quot;wsgi.file_wrapper&quot;: &quot;&lt;class &#x27;wsgiref.util.FileWrapper&#x27;&gt;&quot;,
      &quot;wsgi.input&quot;: &quot;&lt;_io.BytesIO object at 0x1234&gt;&quot;,
      &quot;wsgi.multiprocess&quot;: false,
      &quot;wsgi.multithread&quot;: false,
      &quot;wsgi.run_once&quot;: false,
      &quot;wsgi.url_scheme&quot;: &quot;http&quot;,
      &quot;wsgi.version&quot;: [
        1,
        0
      ]
    }</pre>
    </body></html>

## Notes & Edge Cases
- Always escape user generated content when rendering it in the browser.s
- Ensure that you have a valid account (e.g., `alice`, `bob`) with sufficient balance to pay for gas fees.
- Always verify that you're interacting with the right script address.
- Make sure to provide sufficient gas for script updates (as seen in the example, we used `--gas 500000`).

## Conclusion

This example demonstrates how to:
1. Update on-chain Python code.
2. Execute a function that stores data on the Dyson Protocol.
3. Retrieve data via a WSGI endpoint.

Feel free to adapt the `save_message` function or the WSGI application for more advanced use cases, such as multi-key storage or complex business logic.

## More Documentation

For more detailed information about specific modules, please refer to the following documentation:

- [Script Module](docs/SCRIPT.md): Comprehensive guide to the Script module for on-chain Python execution
- [Storage Module](docs/STORAGE.md): Detailed documentation on the Storage module for on-chain data persistence
- [Crontask Module](docs/CRONTASK.md): Complete guide to the Crontask module for scheduled transaction execution
- [Nameservice Module](docs/NAMESERVICE.md): Guide to the Nameservice module for registering names and creating NFTs

