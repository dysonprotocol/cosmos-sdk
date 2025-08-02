# Dyson Protocol – Make Dwapps, Get Paid

**Host Python scripts, serve decentralized websites, and run scheduled tasks with trustless, censorship-resistant execution. Trade names in a dynamic on-chain market, mint custom tokens and NFTs, and store arbitrary data—all fully on-chain.**

---

## What & Why

- **Problem**  
  - Blockchain DApp UIs still load from centralized servers—developers host them off-chain, and end-users can't self-host or audit the code.

- **Solution**  
  - Store HTML/CSS/JS assets in the chain's storage so browsers load UI from the ledger.  
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
  - **A spectrum of security**: from fully trustless script and web UI, to fully centralized, depending on your needs.


## Installation




### 0. Build the dysvm dependencies
Only do this once.


```bash
%%bash
make dysvm 
```

### 1. Build the Dyson Protocol binary



```bash
%%bash
make install
```

    Installing dysond binary...
    build_tags: netgo,app_v1
    commit: 132ac87
    cosmos_sdk_version: v0.53.0
    go: go version go1.24.3 darwin/arm64
    name: dyson
    server_name: dysond
    version: develop
    



```bash
%%bash
dysond version --long | tail

```

    - rsc.io/qr@v0.2.0
    - sigs.k8s.io/yaml@v1.6.0
    build_tags: netgo,app_v1
    commit: 132ac87
    cosmos_sdk_version: v0.53.0
    go: go version go1.24.3 darwin/arm64
    name: dyson
    server_name: dysond
    version: develop
    


### 2. Create new accounts


```bash
%%bash
dysond keys add alice 
```

    


    - address: dys21ldyd2ngz4ttkmvud40pshksz9g0yx9lzjy9py5
      name: alice
      pubkey: '{"@type":"/cosmos.crypto.secp256k1.PubKey","key":"AjenBZPnfrfFQtvFT1KiGI5YFfKAENEfPLOZafBlPwuN"}'
      type: local
    


    
    **Important** write this mnemonic phrase in a safe place.
    It is the only way to recover your account if you ever forget your password.
    
    useful garbage divorce found surface like jump oven bitter maze ranch switch stomach rough head soap front infant camera twin renew casino olive spot


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


Now let's upload the script to the chain using Alice's address:


```bash
%%bash
ALICE_ADDRESS=$(dysond keys show -a alice)
dysond tx script update --from alice -y -o json --gas 500000 --code "$(cat examples/storage_example.py)" |  dysond q wait-tx -o json | jq '{height, txhash, code, gas_wanted, gas_used, "script_version": .events[] | select(.type=="dysonprotocol.script.v1.EventUpdateScript") | .attributes[] | select(.key=="version") | .value}'

```

    Usage:
      dysond tx script update [--code <code> | --code-path <path to source code>] [flags]
    
    Flags:
      -a, --account-number uint         The account number of the signing account (offline mode only)
          --aux                         Generate aux signer data instead of sending a tx
      -b, --broadcast-mode string       Transaction broadcasting mode (sync|async) (default "sync")
          --chain-id string             The network chain ID
          --code string                 Source code as a string
          --code-path string            Path to the source code file
          --dry-run                     ignore the --gas flag and perform a simulation of a transaction, but don't broadcast it (when enabled, the local Keybase is not accessible)
          --fee-granter string          Fee granter grants fees for the transaction
          --fee-payer string            Fee payer pays fees for the transaction instead of deducting from the signer
          --fees string                 Fees to pay along with transaction; eg: 10uatom
          --from string                 Name or address of private key with which to sign
          --gas string                  gas limit to set per-transaction; set to "auto" to calculate sufficient gas automatically. Note: "auto" option doesn't always report accurate results. Set a valid coin value to adjust the result. Can be used instead of "fees". (default 200000)
          --gas-adjustment float        adjustment factor to be multiplied against the estimate returned by the tx simulation; if the gas limit is set manually this flag is ignored  (default 1)
          --gas-prices string           Gas prices in decimal format to determine the transaction fee (e.g. 0.1uatom)
          --generate-only               Build an unsigned transaction and write it to STDOUT (when enabled, the local Keybase only accessed when providing a key name)
      -h, --help                        help for update
          --keyring-backend string      Select keyring's backend (os|file|kwallet|pass|test|memory) (default "os")
          --keyring-dir string          The client Keyring directory; if omitted, the default 'home' directory will be used
          --ledger                      Use a connected Ledger device
          --node string                 <host>:<port> to CometBFT rpc interface for this chain (default "tcp://localhost:26657")
          --note string                 Note to add a description to the transaction (previously --memo)
          --offline                     Offline mode (does not allow any online functionality)
      -o, --output string               Output format (text|json) (default "json")
      -s, --sequence uint               The sequence number of the signing account (offline mode only)
          --sign-mode string            Choose sign mode (direct|amino-json|direct-aux|textual), this is an advanced feature
          --timeout-duration duration   TimeoutDuration is the duration the transaction will be considered valid in the mempool. The transaction's unordered nonce will be set to the time of transaction creation + the duration value passed. If the transaction is still in the mempool, and the block time has passed the time of submission + TimeoutTimestamp, the transaction will be rejected.
          --timeout-height uint         DEPRECATED: Please use --timeout-duration instead. Set a block timeout height to prevent the tx from being committed past a certain height
          --tip string                  Tip is the amount that is going to be transferred to the fee payer on the target chain. This flag is only valid when used with --aux, and is ignored if the target chain didn't enable the TipDecorator
          --unordered                   Enable unordered transaction delivery; must be used in conjunction with --timeout-duration
      -y, --yes                         Skip tx broadcasting prompt confirmation
    
    Global Flags:
          --home string         directory for config and data (default "/Users/user/.dysonprotocol")
          --log_format string   The logging format (json|plain) (default "plain")
          --log_level string    The logging level (trace|debug|info|warn|error|fatal|panic|disabled or '*:<level>,<key>:<level>') (default "info")
          --log_no_color        Disable colored logs
          --trace               print out full stack trace on errors
    
    rpc error: code = NotFound desc = rpc error: code = NotFound desc = account dys21ldyd2ngz4ttkmvud40pshksz9g0yx9lzjy9py5 not found: key not found
    Usage:
      dysond query wait-tx [hash] [flags]
    
    Aliases:
      wait-tx, event-query-tx-for
    
    Examples:
    By providing the transaction hash:
    $ dysond q wait-tx [hash]
    
    Or, by piping a "tx" command:
    $ dysond tx [flags] | dysond q wait-tx
    
    
    Flags:
          --grpc-addr string   the gRPC endpoint to use for this chain
          --grpc-insecure      allow gRPC over insecure channels, if not the server must use TLS
          --height int         Use a specific height to query state at (this can error if the node is pruning state)
      -h, --help               help for wait-tx
          --node string        <host>:<port> to CometBFT RPC interface for this chain (default "tcp://localhost:26657")
      -o, --output string      Output format (text|json) (default "text")
          --timeout duration   The maximum time to wait for the transaction to be included in a block (default 15s)
    
    Global Flags:
          --home string         directory for config and data (default "/Users/user/.dysonprotocol")
          --log_format string   The logging format (json|plain) (default "plain")
          --log_level string    The logging level (trace|debug|info|warn|error|fatal|panic|disabled or '*:<level>,<key>:<level>') (default "info")
          --log_no_color        Disable colored logs
          --trace               print out full stack trace on errors
    
    txhash not found


### 3. Execute the Script Function

Invoke the `save_message` function using Bob's account, passing `"my name is bob"` as an argument:


```bash
%%bash
ALICE_ADDRESS=$(dysond keys show -a alice)
# Save the message to the storage
dysond tx script exec-script --from bob --script-address $ALICE_ADDRESS --function-name save_message --args '["my name is <b>bob</b>"]' -y  | dysond query wait-tx -o json | ./scripts/parse_exec_script_tx.py | jq 
```

    Usage:
      dysond query wait-tx [hash] [flags]
    
    Aliases:
      wait-tx, event-query-tx-for
    
    Examples:
    By providing the transaction hash:
    $ dysond q wait-tx [hash]
    
    Or, by piping a "tx" command:
    $ dysond tx [flags] | dysond q wait-tx
    
    
    Flags:
          --grpc-addr string   the gRPC endpoint to use for this chain
          --grpc-insecure      allow gRPC over insecure channels, if not the server must use TLS
          --height int         Use a specific height to query state at (this can error if the node is pruning state)
      -h, --help               help for wait-tx
          --node string        <host>:<port> to CometBFT RPC interface for this chain (default "tcp://localhost:26657")
      -o, --output string      Output format (text|json) (default "text")
          --timeout duration   The maximum time to wait for the transaction to be included in a block (default 15s)
    
    Global Flags:
          --home string         directory for config and data (default "/Users/user/.dysonprotocol")
          --log_format string   The logging format (json|plain) (default "plain")
          --log_level string    The logging level (trace|debug|info|warn|error|fatal|panic|disabled or '*:<level>,<key>:<level>') (default "info")
          --log_no_color        Disable colored logs
          --trace               print out full stack trace on errors
    
    dial tcp [::1]:26657: connect: connection refused
    Usage:
      dysond tx script [flags]
      dysond tx script [command]
    
    Available Commands:
      create-new-script Creates a new script with a deterministic address derived from creator and code
      exec              Executes a script at a given address with optional input data and parameters
      grant-exec        Grant a custom ScriptExecAuthorization to a grantee (via authz)
      update            Updates the script at the sender's address with new code and increments the version
    
    Flags:
      -h, --help   help for script
    
    Global Flags:
          --home string         directory for config and data (default "/Users/user/.dysonprotocol")
          --log_format string   The logging format (json|plain) (default "plain")
          --log_level string    The logging level (trace|debug|info|warn|error|fatal|panic|disabled or '*:<level>,<key>:<level>') (default "info")
          --log_no_color        Disable colored logs
          --trace               print out full stack trace on errors
    
    Use "dysond tx script [command] --help" for more information about a command.
    
    unknown command "exec-script" for "script"
    jq: parse error: Invalid numeric literal at line 1, column 6



    ---------------------------------------------------------------------------

    CalledProcessError                        Traceback (most recent call last)

    Cell In[13], line 1
    ----> 1 get_ipython().run_cell_magic('bash', '', 'ALICE_ADDRESS=$(dysond keys show -a alice)\n# Save the message to the storage\ndysond tx script exec-script --from bob --script-address $ALICE_ADDRESS --function-name save_message --args \'["my name is <b>bob</b>"]\' -y  | dysond query wait-tx -o json | ./scripts/parse_exec_script_tx.py | jq \n')


    File ~/.pyenv/versions/3.12.11/lib/python3.12/site-packages/IPython/core/interactiveshell.py:2549, in InteractiveShell.run_cell_magic(self, magic_name, line, cell)
       2547 with self.builtin_trap:
       2548     args = (magic_arg_s, cell)
    -> 2549     result = fn(*args, **kwargs)
       2551 # The code below prevents the output from being displayed
       2552 # when using magics with decorator @output_can_be_silenced
       2553 # when the last Python token in the expression is a ';'.
       2554 if getattr(fn, magic.MAGIC_OUTPUT_CAN_BE_SILENCED, False):


    File ~/.pyenv/versions/3.12.11/lib/python3.12/site-packages/IPython/core/magics/script.py:159, in ScriptMagics._make_script_magic.<locals>.named_script_magic(line, cell)
        157 else:
        158     line = script
    --> 159 return self.shebang(line, cell)


    File ~/.pyenv/versions/3.12.11/lib/python3.12/site-packages/IPython/core/magics/script.py:336, in ScriptMagics.shebang(self, line, cell)
        331 if args.raise_error and p.returncode != 0:
        332     # If we get here and p.returncode is still None, we must have
        333     # killed it but not yet seen its return code. We don't wait for it,
        334     # in case it's stuck in uninterruptible sleep. -9 = SIGKILL
        335     rc = p.returncode or -9
    --> 336     raise CalledProcessError(rc, cell)


    CalledProcessError: Command 'b'ALICE_ADDRESS=$(dysond keys show -a alice)\n# Save the message to the storage\ndysond tx script exec-script --from bob --script-address $ALICE_ADDRESS --function-name save_message --args \'["my name is <b>bob</b>"]\' -y  | dysond query wait-tx -o json | ./scripts/parse_exec_script_tx.py | jq \n'' returned non-zero exit status 5.


### 4. Query the WSGI Endpoint

Finally, confirm the data is stored and accessible via an HTTP request to the script's WSGI endpoint:


```bash
%%bash
ALICE_ADDRESS=$(dysond keys show -a alice)
DWAPP_SERVER_ADDRESS=$(dysond config get app dwapp.address | tr -d '"')
DWAPP_URL="http://$ALICE_ADDRESS.$DWAPP_SERVER_ADDRESS/some-path?query=some-query"
curl -v $DWAPP_URL
```

## Notes & Edge Cases
- Always escape user generated content when rendering it in the browser.
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

### Module Guides

- [Script Module](notebooks/scripting_guide.md): Comprehensive guide to the Script module for on-chain Python execution
- [Storage Module](notebooks/storage_guide.md): Detailed documentation on the Storage module for on-chain data persistence
- [Crontask Module](notebooks/crontask_guide.md): Complete guide to the Crontask module for scheduled transaction execution
- [Nameservice Module](notebooks/nameservice_guide.md): Guide to the Nameservice module for registering names and creating NFTs
- [DysLang Guide](notebooks/dyslang_guide.md): Complete programming reference for the Dyson Language

### Interactive Notebooks

The same guides are also available as interactive Jupyter notebooks in the `notebooks/` directory:

- [Script Module Notebook](notebooks/scripting_guide.ipynb)
- [Storage Module Notebook](notebooks/storage_guide.ipynb)
- [Crontask Module Notebook](notebooks/crontask_guide.ipynb)
- [Nameservice Module Notebook](notebooks/nameservice_guide.ipynb)
- [DysLang Guide Notebook](notebooks/dyslang_guide.ipynb)

### Code Examples

Explore practical examples in the `examples/` directory:

- [Storage Example](examples/storage_example.py): Basic storage operations and WSGI endpoint
- [Crontask Example](examples/crontask_countdown.py): Scheduled task countdown implementation
- [Crontask Script](examples/crontask_script.py): Advanced scheduled transaction execution
- [DysLang Example](examples/dyslang_example.py): Comprehensive language feature demonstration
- [Balance Example](examples/balance_example.py): Account balance querying
- [WSGI Example](examples/simple_wsgi_example.py): Simple web application server
- [AST Explorer](examples/ast_explorer.py): Python Abstract Syntax Tree exploration
- [ICA Example](examples/ica_e2e.py): Inter-Chain Account end-to-end example
- [ICA Module](examples/ica.py): Inter-Chain Account implementation
- [Script Query Height](examples/script_query_height.py): Query blockchain height from scripts

