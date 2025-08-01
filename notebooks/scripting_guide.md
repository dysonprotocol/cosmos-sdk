# Dyson Protocol Scripting Guide

This guide provides an end-to-end demonstration of the Dyson Protocol Script Module for developers. It covers script management, execution, data handling, and web access through name resolution in the least number of steps.

## Fetch Your Address

First, we'll retrieve the address associated with the 'alice' account. This address will serve as our identity throughout this guide and will be referenced in subsequent commands.



```python
[address] = ! dysond keys show alice -a
print(address)
```

    dys21tvhkv3gqr90jpycaky02xa5ukhaxllu3jlwnej


## Update Script on Chain
Now, let's deploy our script to the blockchain. We'll create a simple Python script with two functions:
1. An `add` function that performs basic arithmetic
2. A WSGI application that serves a welcome HTML page when accessed via web

This demonstrates how Dyson Protocol enables both computational functions and web hosting capabilities.



```python
import os

code = """
def add(a, b):
    print(f"Adding {a} and {b}")
    return {"a": a, "b": b, "add_result": a + b}

def wsgi(environ, start_response):
    status = '200 OK'
    headers = [('Content-type', 'text/html')]
    start_response(status, headers)
    return [b'''
<html>
    <body>
        <h1>Hello from Dyson Protocol!</h1>
    </body>
</html>''']
"""
import tempfile
import json

with tempfile.NamedTemporaryFile(suffix='.py', delete=True) as tmp:
    tmp.write(code.encode())
    tmp.flush()
    path = tmp.name
    
    tx = ! dysond tx script update --code-path $path \
        --from alice \
        -y | dysond query wait-tx -o json
    
json.loads('\n'.join(tx))
```




    {'height': '214',
     'txhash': '1C5D7242142A0EEC7FBC049CF6B7B5C88200F5707784FED84A1677D3A4D4093F',
     'codespace': '',
     'code': 0,
     'data': '12360A302F6479736F6E70726F746F636F6C2E7363726970742E76312E4D7367557064617465536372697074526573706F6E736512020802',
     'raw_log': '',
     'logs': [],
     'info': '',
     'gas_wanted': '200000',
     'gas_used': '55370',
     'tx': None,
     'timestamp': '',
     'events': [{'type': 'tx',
       'attributes': [{'key': 'acc_seq',
         'value': 'dys21tvhkv3gqr90jpycaky02xa5ukhaxllu3jlwnej/59',
         'index': True}]},
      {'type': 'tx',
       'attributes': [{'key': 'signature',
         'value': 'tGhHYVId8PwtPHfV/1SmVRKBd5sggWyLxlee/f2+FAElk6pXdqsdHQodbdw8zwH3Nb4xx+K2r8LlmLw8KQETZQ==',
         'index': True}]},
      {'type': 'message',
       'attributes': [{'key': 'action',
         'value': '/dysonprotocol.script.v1.MsgUpdateScript',
         'index': True},
        {'key': 'sender',
         'value': 'dys21tvhkv3gqr90jpycaky02xa5ukhaxllu3jlwnej',
         'index': True},
        {'key': 'module', 'value': 'script', 'index': True},
        {'key': 'msg_index', 'value': '0', 'index': True}]},
      {'type': 'dysonprotocol.script.v1.EventUpdateScript',
       'attributes': [{'key': 'version', 'value': '"2"', 'index': True},
        {'key': 'msg_index', 'value': '0', 'index': True}]}]}



## Access Script via Web Interface
Dyson Protocol allows scripts to be accessed as web applications through the WSGI interface. Let's access our script directly using its address. This demonstrates how Dyson Protocol enables decentralized web hosting without traditional servers.

We'll use the script address to construct a URL that points to our deployed application. The format is:
`http://<script_address>.example.com`

For local development, we'll use localhost:8000 as our domain suffix.


```python
[output] = ! dysond config get app api.address
port = output.split(":")[-1].strip("\"")

dwapp_url = f"http://{address}.localhost:{port}"

print(f"Accessing your DWapp at '{dwapp_url}'")
output = ! curl -s "$dwapp_url/hi" -v
output = "\n".join(output).strip()
print(output)
assert "Hello from Dyson Protocol!" in output, "Expected 'Hello from Dyson Protocol!' in output, got: " + output
```

    Accessing your DWapp at 'http://dys21tvhkv3gqr90jpycaky02xa5ukhaxllu3jlwnej.localhost:5317'


    * Host dys21tvhkv3gqr90jpycaky02xa5ukhaxllu3jlwnej.localhost:5317 was resolved.
    * IPv6: ::1
    * IPv4: 127.0.0.1
    *   Trying [::1]:5317...
    * connect to ::1 port 5317 from ::1 port 55968 failed: Connection refused
    *   Trying 127.0.0.1:5317...
    * Connected to dys21tvhkv3gqr90jpycaky02xa5ukhaxllu3jlwnej.localhost (127.0.0.1) port 5317
    > GET /hi HTTP/1.1
    > Host: dys21tvhkv3gqr90jpycaky02xa5ukhaxllu3jlwnej.localhost:5317
    > User-Agent: curl/8.7.1
    > Accept: */*
    > 
    * Request completely sent off
    < HTTP/1.1 200 OK
    < Content-Length: 82
    < Content-Type: text/html
    < Date: Thu, 31 Jul 2025 21:42:01 GMT
    < Server: WSGIServer/0.2 CPython/3.12.11
    < X-Server-Time: 1753998123
    < 
    { [82 bytes data]
    * Connection #0 to host dys21tvhkv3gqr90jpycaky02xa5ukhaxllu3jlwnej.localhost left intact
    
    <html>
        <body>
            <h1>Hello from Dyson Protocol!</h1>
        </body>
    </html>


## Query Script Information
Let's examine the script we just deployed to the blockchain. This query retrieves the script's metadata and code content, allowing us to verify our update was successful.



```python
import json

output = ! dysond query script script-info --address "$address" -o json 

print("\n".join(output))
script_info = json.loads('\n'.join(output))
print(f"✓ Script query successful for address: {address}")

```

    {"script":{"address":"dys21tvhkv3gqr90jpycaky02xa5ukhaxllu3jlwnej","version":"2","code":"\ndef add(a, b):\n    print(f\"Adding {a} and {b}\")\n    return {\"a\": a, \"b\": b, \"add_result\": a + b}\n\ndef wsgi(environ, start_response):\n    status = '200 OK'\n    headers = [('Content-type', 'text/html')]\n    start_response(status, headers)\n    return [b'''\n\u003chtml\u003e\n    \u003cbody\u003e\n        \u003ch1\u003eHello from Dyson Protocol!\u003c/h1\u003e\n    \u003c/body\u003e\n\u003c/html\u003e''']\n"}}
    ✓ Script query successful for address: dys21tvhkv3gqr90jpycaky02xa5ukhaxllu3jlwnej


## Execute Script
## Execute Script Function
Now we'll invoke the `add` function we deployed in our script. This demonstrates how Dyson Protocol enables 
decentralized computation by executing functions directly on the blockchain. We'll pass the arguments `5` and `7`, 
and observe how the function processes these values and returns the calculated sum of `12` along with additional metadata.


```python
! dysond tx script exec \
    --script-address "$address" \
    --function-name add \
    --args '[5, 7]' \
    --from alice \
    -y \
    -o json  | dysond query wait-tx -o json | python ../scripts/parse_exec_script_tx.py
```

    {
      "code": 0,
      "script_result": {
        "result": {
          "cumsize": 2515,
          "exception": null,
          "gas_limit": 200000,
          "nodes_called": 28,
          "result": {
            "a": 5,
            "add_result": 12,
            "b": 7
          },
          "script_gas_consumed": 32592,
          "stdout": "Adding 5 and 7\n"
        },
        "attached_message_results": []
      },
      "raw_log": "",
      "events": [
        {
          "type": "tx",
          "attributes": [
            {
              "key": "acc_seq",
              "value": "dys21tvhkv3gqr90jpycaky02xa5ukhaxllu3jlwnej/60",
              "index": true
            }
          ]
        },
        {
          "type": "tx",
          "attributes": [
            {
              "key": "signature",
              "value": "jdjupCzsNW5PkTDlylseQEf8jJPBzNPhrUuKwmKtheI+0jzrtmtgZSGLp839fibA8MEwS+kcC9AiCO2atc5g+w==",
              "index": true
            }
          ]
        },
        {
          "type": "message",
          "attributes": [
            {
              "key": "action",
              "value": "/dysonprotocol.script.v1.MsgExec",
              "index": true
            },
            {
              "key": "sender",
              "value": "dys21tvhkv3gqr90jpycaky02xa5ukhaxllu3jlwnej",
              "index": true
            },
            {
              "key": "module",
              "value": "script",
              "index": true
            },
            {
              "key": "msg_index",
              "value": "0",
              "index": true
            }
          ]
        },
        {
          "type": "dysonprotocol.script.v1.EventExecScript",
          "attributes": [
            {
              "key": "request",
              "value": "{\"executor_address\":\"dys21tvhkv3gqr90jpycaky02xa5ukhaxllu3jlwnej\",\"script_address\":\"dys21tvhkv3gqr90jpycaky02xa5ukhaxllu3jlwnej\",\"script_name\":\"\",\"extra_code\":\"\",\"function_name\":\"add\",\"args\":\"[5, 7]\",\"kwargs\":\"\",\"attached_messages\":[]}",
              "index": true
            },
            {
              "key": "response",
              "value": "{\"result\":\"{\\\"cumsize\\\":2515,\\\"exception\\\":null,\\\"gas_limit\\\":200000,\\\"nodes_called\\\":28,\\\"result\\\":{\\\"a\\\":5,\\\"add_result\\\":12,\\\"b\\\":7},\\\"script_gas_consumed\\\":32592,\\\"stdout\\\":\\\"Adding 5 and 7\\\\n\\\"}\",\"attached_message_results\":[]}",
              "index": true
            },
            {
              "key": "msg_index",
              "value": "0",
              "index": true
            }
          ]
        }
      ]
    }


# Encoding JSON for Blockchain Operations
Your project may require converting complex JSON structures into a compact binary format for efficient on-chain storage and transmission. The following example demonstrates how to encode a standard transaction message into its binary representation.


```python
! dysond query script encode-json --json '{\
  "@type": "/cosmos.bank.v1beta1.MsgSend", \
  "from_address": "dys1example1", \
  "to_address": "dys1example2", \
  "amount": [ { "denom": "dys", "amount": "100" } ] \
}' -o json
```

    {
      "bytes": "CgxkeXMxZXhhbXBsZTESDGR5czFleGFtcGxlMhoKCgNkeXMSAzEwMA=="
    }


## Decode Bytes
Decoding Binary Data
In this step, we'll convert the previously encoded binary data back into its original JSON format. This bidirectional conversion capability is essential for working with blockchain data that needs to be both efficiently stored on-chain and human-readable when retrieved.


```python
! dysond query script decode-bytes --bytes "CgxkeXMxZXhhbXBsZTESDGR5czFleGFtcGxlMhoKCgNkeXMSAzEwMA=="  --type-url "/cosmos.bank.v1beta1.MsgSend" -o json | jq
```

    [1;39m{
      [0m[1;34m"json"[0m[1;39m: [0m[0;32m"{\"@type\":\"/cosmos.bank.v1beta1.MsgSend\",\"from_address\":\"dys1example1\",\"to_address\":\"dys1example2\",\"amount\":[{\"denom\":\"dys\",\"amount\":\"100\"}]}"[0m[1;39m
    [1;39m}[0m


## Commit Name Registration
More details on name registration can be found in the Name Service section of the documentation.
Commit to registering a name using a computed hash. First, compute the hash.


```python
import random
import string

def random_string(length=10):
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

name = f"alice-{random_string(5)}.dys"
salt = random_string(10)

[hex_hash] = ! dysond query nameservice compute-hash \
    --name "$name" \
    --salt "$salt" \
    --committer "$address" \
    -o json | jq '.hex_hash' -r

print(f"Name: {name}")
print(f"Salt: {salt}")
print(f"Hex Hash: {hex_hash}")
```

    Name: alice-gkxd4.dys
    Salt: zxffckex9q
    Hex Hash: 713fd2c9185612cd9e2fe1092966ccaf7990a7e8b4a4ed7bf9a33a6e2bed9ed6



```python
valuation = '100udys'
! dysond tx nameservice commit --commitment "$hex_hash" --valuation "$valuation" --from alice -y | dysond query wait-tx -o json | jq -M
```

    {
      "height": "219",
      "txhash": "399AFCF1F74864F91BC0CB89358EF520CD49C99DE9CFCBFA90A31CA84EB19114",
      "codespace": "",
      "code": 0,
      "data": "12310A2F2F6479736F6E70726F746F636F6C2E6E616D65736572766963652E76312E4D7367436F6D6D6974526573706F6E7365",
      "raw_log": "",
      "logs": [],
      "info": "",
      "gas_wanted": "200000",
      "gas_used": "39935",
      "tx": null,
      "timestamp": "",
      "events": [
        {
          "type": "tx",
          "attributes": [
            {
              "key": "acc_seq",
              "value": "dys21tvhkv3gqr90jpycaky02xa5ukhaxllu3jlwnej/61",
              "index": true
            }
          ]
        },
        {
          "type": "tx",
          "attributes": [
            {
              "key": "signature",
              "value": "nGDoLteG6QDXXOkHos8Ldwkz0xMvuZ8VyrNfEL20YllESmhAHGm7e4P4bjtuZ1amF8Sm5WaaRIBYYw8ASGqWNQ==",
              "index": true
            }
          ]
        },
        {
          "type": "message",
          "attributes": [
            {
              "key": "action",
              "value": "/dysonprotocol.nameservice.v1.MsgCommit",
              "index": true
            },
            {
              "key": "sender",
              "value": "dys21tvhkv3gqr90jpycaky02xa5ukhaxllu3jlwnej",
              "index": true
            },
            {
              "key": "module",
              "value": "nameservice",
              "index": true
            },
            {
              "key": "msg_index",
              "value": "0",
              "index": true
            }
          ]
        },
        {
          "type": "dysonprotocol.nameservice.v1.EventCommitmentCreated",
          "attributes": [
            {
              "key": "hexhash",
              "value": "\"713fd2c9185612cd9e2fe1092966ccaf7990a7e8b4a4ed7bf9a33a6e2bed9ed6\"",
              "index": true
            },
            {
              "key": "msg_index",
              "value": "0",
              "index": true
            }
          ]
        }
      ]
    }


## Reveal Name Registration
Reveal the name to complete registration.


```python
! dysond tx nameservice reveal \
    --name "$name" \
    --salt "$salt" \
    --from alice \
    -y | dysond query wait-tx -o json | jq -M
```

    {
      "height": "221",
      "txhash": "C9932502F82C56CD616C1ABCEF9C05A6CA9EA8374403FE7B8974FDF59D29BCE3",
      "codespace": "",
      "code": 0,
      "data": "12310A2F2F6479736F6E70726F746F636F6C2E6E616D65736572766963652E76312E4D736752657665616C526573706F6E7365",
      "raw_log": "",
      "logs": [],
      "info": "",
      "gas_wanted": "200000",
      "gas_used": "84910",
      "tx": null,
      "timestamp": "",
      "events": [
        {
          "type": "tx",
          "attributes": [
            {
              "key": "acc_seq",
              "value": "dys21tvhkv3gqr90jpycaky02xa5ukhaxllu3jlwnej/62",
              "index": true
            }
          ]
        },
        {
          "type": "tx",
          "attributes": [
            {
              "key": "signature",
              "value": "kTfEKulFuFs1PjxpBI7ty2Te2WUxDbfiIt+TySJuYrRgyu1B/ACKqrYaS9KajbdkZF6J4sy6B/OctNhRVYcyZQ==",
              "index": true
            }
          ]
        },
        {
          "type": "message",
          "attributes": [
            {
              "key": "action",
              "value": "/dysonprotocol.nameservice.v1.MsgReveal",
              "index": true
            },
            {
              "key": "sender",
              "value": "dys21tvhkv3gqr90jpycaky02xa5ukhaxllu3jlwnej",
              "index": true
            },
            {
              "key": "module",
              "value": "nameservice",
              "index": true
            },
            {
              "key": "msg_index",
              "value": "0",
              "index": true
            }
          ]
        },
        {
          "type": "coin_spent",
          "attributes": [
            {
              "key": "spender",
              "value": "dys21tvhkv3gqr90jpycaky02xa5ukhaxllu3jlwnej",
              "index": true
            },
            {
              "key": "amount",
              "value": "1udys",
              "index": true
            },
            {
              "key": "msg_index",
              "value": "0",
              "index": true
            }
          ]
        },
        {
          "type": "coin_received",
          "attributes": [
            {
              "key": "receiver",
              "value": "dys21jv65s3grqf6v6jl3dp4t6c9t9rk99cd8d0l2ev",
              "index": true
            },
            {
              "key": "amount",
              "value": "1udys",
              "index": true
            },
            {
              "key": "msg_index",
              "value": "0",
              "index": true
            }
          ]
        },
        {
          "type": "transfer",
          "attributes": [
            {
              "key": "recipient",
              "value": "dys21jv65s3grqf6v6jl3dp4t6c9t9rk99cd8d0l2ev",
              "index": true
            },
            {
              "key": "sender",
              "value": "dys21tvhkv3gqr90jpycaky02xa5ukhaxllu3jlwnej",
              "index": true
            },
            {
              "key": "amount",
              "value": "1udys",
              "index": true
            },
            {
              "key": "msg_index",
              "value": "0",
              "index": true
            }
          ]
        },
        {
          "type": "message",
          "attributes": [
            {
              "key": "sender",
              "value": "dys21tvhkv3gqr90jpycaky02xa5ukhaxllu3jlwnej",
              "index": true
            },
            {
              "key": "msg_index",
              "value": "0",
              "index": true
            }
          ]
        },
        {
          "type": "dysonprotocol.nft.v1beta1.EventMint",
          "attributes": [
            {
              "key": "class_id",
              "value": "\"nameservice.dys\"",
              "index": true
            },
            {
              "key": "id",
              "value": "\"alice-gkxd4.dys\"",
              "index": true
            },
            {
              "key": "owner",
              "value": "\"dys21tvhkv3gqr90jpycaky02xa5ukhaxllu3jlwnej\"",
              "index": true
            },
            {
              "key": "msg_index",
              "value": "0",
              "index": true
            }
          ]
        },
        {
          "type": "dysonprotocol.nameservice.v1.EventNameRegistered",
          "attributes": [
            {
              "key": "fee",
              "value": "[{\"denom\":\"udys\",\"amount\":\"1\"}]",
              "index": true
            },
            {
              "key": "name",
              "value": "\"alice-gkxd4.dys\"",
              "index": true
            },
            {
              "key": "msg_index",
              "value": "0",
              "index": true
            }
          ]
        }
      ]
    }


## Set Destination for Name
Set the destination of the registered name to Alice's address.


```python
! dysond tx nameservice set-destination \
    --name "$name" \
    --destination "$address" \
    --from alice \
    -y \
    -o json | jq -M
```

    {
      "height": "0",
      "txhash": "2EA6F701485ACDF1230E7D05F93E0F14B1F9425681F75B2B93B5DAD7DD5C851D",
      "codespace": "",
      "code": 0,
      "data": "",
      "raw_log": "",
      "logs": [],
      "info": "",
      "gas_wanted": "0",
      "gas_used": "0",
      "tx": null,
      "timestamp": "",
      "events": []
    }


## Access Script via Name
Access the script via the registered name to demonstrate decentralized web hosting.


```python
[output] = ! dysond config get app api.address
port = output.split(":")[-1].strip("\"")

dwapp_url = f"http://{name}.localhost:{port}"

print(f"Accessing your DWapp at '{dwapp_url}'")
output = ! curl -s "$dwapp_url/hi" -v
output = "\n".join(output).strip()
print(output)
assert "Hello from Dyson Protocol!" in output, "Expected 'Hello from Dyson Protocol!' in output, got: " + output
```

    Accessing your DWapp at 'http://alice-gkxd4.dys.localhost:5317'


    * Host alice-gkxd4.dys.localhost:5317 was resolved.
    * IPv6: ::1
    * IPv4: 127.0.0.1
    *   Trying [::1]:5317...
    * connect to ::1 port 5317 from ::1 port 49959 failed: Connection refused
    *   Trying 127.0.0.1:5317...
    * Connected to alice-gkxd4.dys.localhost (127.0.0.1) port 5317
    > GET /hi HTTP/1.1
    > Host: alice-gkxd4.dys.localhost:5317
    > User-Agent: curl/8.7.1
    > Accept: */*
    > 
    * Request completely sent off
    < HTTP/1.1 200 OK
    < Content-Length: 82
    < Content-Type: text/html
    < Date: Thu, 31 Jul 2025 21:42:07 GMT
    < Server: WSGIServer/0.2 CPython/3.12.11
    < X-Server-Time: 1753998128
    < 
    { [82 bytes data]
    * Connection #0 to host alice-gkxd4.dys.localhost left intact
    
    <html>
        <body>
            <h1>Hello from Dyson Protocol!</h1>
        </body>
    </html>

