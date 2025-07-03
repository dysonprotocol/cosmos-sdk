# Dyson Protocol Language Module Guide

This notebook provides a comprehensive guide to the Dyson Protocol Language Module (dyslang), which offers a secure and sandboxed Python execution environment on the blockchain. Through practical examples, we'll explore how to interact with the blockchain state, manage gas consumption, and leverage the powerful features of the `dys` module to build robust decentralized applications.

## Introduction to dyslang

The dyslang module serves as the backbone for on-chain Python execution in the Dyson Protocol. It provides a set of functions that enable scripts to:

- **Query Chain State**: Access account balances, contract data, and module parameters
- **Execute Transactions**: Send tokens, create contracts, and interact with other modules
- **Manage Resources**: Monitor gas consumption and execution limits
- **Access Context**: Retrieve information about the current script, executor, and block
- **Emit Events**: Produce blockchain events that can be indexed and monitored
- **Evaluate Code**: Execute dynamic Python code within a controlled environment

Let's dive into these features with practical examples.

## Setting Up

Before we start, let's set up our environment by defining our test accounts:


```python
# Get addresses of our test accounts
[ALICE_ADDRESS] = ! dysond keys show -a alice
[BOB_ADDRESS] = ! dysond keys show -a bob

print(f"Using alice address: {ALICE_ADDRESS}")
print(f"Using bob address: {BOB_ADDRESS}")
```

    Using alice address: dys1tvhkv3gqr90jpycaky02xa5ukhaxllu38wawhz
    Using bob address: dys1fhhxp9xveswc4yhxekr32eqe80rkwpurya0jh0


## Chain Interaction

The dyslang module provides two primary functions for interacting with the blockchain: `_query` and `_msg`.

- `_query`: Used to query the blockchain state (read-only operations)
- `_msg`: Used to submit transactions that modify the blockchain state

Let's explore these functions with practical examples.

### Querying Account Balances

One common operation is to query an account's balance. Let's create a script that queries the balance of an account:


```python
import json
import shlex

# Create a script that queries the account balance
query_script = '''
from dys import _query, get_script_address
import json

def query_balance():
    # Query the script's own balance
    script_address = get_script_address()
    response = _query({
        "@type": "/cosmos.bank.v1beta1.QueryBalanceRequest",
        "address": script_address,
        "denom": "dys"
    })
    return response
'''

# Save the script to a temporary file and execute it
with open('/tmp/query_balance.py', 'w') as f:
    f.write(query_script)

# Execute the script using simulate_exec.py
out = ! ../scripts/simulate_exec.py /tmp/query_balance.py --from alice --script-address $ALICE_ADDRESS --function-name query_balance
out = '\n'.join(out)
result = json.loads(out)

# Extract and display the balance
script_result = result['script_result']['result']
balance_response = script_result['result']
print(json.dumps(balance_response, indent=2))
```

    {
      "@type": "/cosmos.bank.v1beta1.QueryBalanceResponse",
      "balance": {
        "amount": "9999853593",
        "denom": "dys"
      }
    }


### Querying Multiple Account Balances

Let's create a more advanced script that queries the balances of multiple accounts:


```python
# Create a script that queries multiple account balances
query_multi_script = f'''
from dys import _query
import json

def query_multiple_balances():
    # Define the addresses to query
    alice_address = "{ALICE_ADDRESS}"
    bob_address = "{BOB_ADDRESS}"
    
    # Query Alice's balance
    alice_balance = _query({{
        "@type": "/cosmos.bank.v1beta1.QueryBalanceRequest",
        "address": alice_address,
        "denom": "dys"
    }})
    
    # Query Bob's balance
    bob_balance = _query({{
        "@type": "/cosmos.bank.v1beta1.QueryBalanceRequest",
        "address": bob_address,
        "denom": "dys"
    }})
    
    # Return both balances
    return {{
        "alice_balance": alice_balance,
        "bob_balance": bob_balance
    }}
'''

# Save the script to a temporary file and execute it
with open('/tmp/query_multi_balance.py', 'w') as f:
    f.write(query_multi_script)

# Execute the script
out = ! ../scripts/simulate_exec.py /tmp/query_multi_balance.py --from alice --script-address $ALICE_ADDRESS --function-name query_multiple_balances
out = '\n'.join(out)
result = json.loads(out)

# Extract and display the results
script_result = result['script_result']['result']
balances = script_result['result']
print(json.dumps(balances, indent=2))
```

    {
      "alice_balance": {
        "@type": "/cosmos.bank.v1beta1.QueryBalanceResponse",
        "balance": {
          "amount": "9999853593",
          "denom": "dys"
        }
      },
      "bob_balance": {
        "@type": "/cosmos.bank.v1beta1.QueryBalanceResponse",
        "balance": {
          "amount": "10000000000",
          "denom": "dys"
        }
      }
    }


## Gas Management

In blockchain environments, computational resources are metered using a concept called "gas". The dyslang module provides several functions to help you monitor and manage gas consumption in your scripts.

### Monitoring Gas Consumption

Let's create a script that measures the gas consumed by various operations:


```python
# Create a script to benchmark gas consumption
gas_benchmark_script = '''
from dys import _query, get_gas_consumed, get_script_address, get_gas_limit
import json

def benchmark_gas(iterations=5):
    # Start tracking gas
    initial_gas = get_gas_consumed()
    
    # Perform a query that consumes gas
    script_address = get_script_address()
    balance_response = _query({
        "@type": "/cosmos.bank.v1beta1.QueryBalanceRequest",
        "address": script_address,
        "denom": "dys"
    })
    
    # Check gas after query
    after_query_gas = get_gas_consumed()
    
    # Run some iterations to measure their gas cost
    for i in range(iterations):
        print(f"Iteration {i+1} of {iterations}")
    
    # Check final gas consumption
    final_gas = get_gas_consumed()
    
    # Calculate gas used by different operations
    query_gas = after_query_gas - initial_gas
    iterations_gas = final_gas - after_query_gas
    
    return {
        "initial_gas": initial_gas,
        "after_query_gas": after_query_gas,
        "final_gas": final_gas,
        "query_gas": query_gas,
        "iterations_gas": iterations_gas,
        "per_iteration": iterations_gas / iterations
    }
'''

# Save and execute the script
with open('/tmp/gas_benchmark.py', 'w') as f:
    f.write(gas_benchmark_script)

out = ! ../scripts/simulate_exec.py /tmp/gas_benchmark.py --from alice --script-address $ALICE_ADDRESS --function-name benchmark_gas --gas auto
out = '\n'.join(out)
print(out)
result = json.loads(out)

# Extract and display the gas measurements
script_result = result['script_result']['result']
gas_metrics = script_result['result']

print(f"Gas report for benchmark operations:")
print(f"- Initial gas consumed: {gas_metrics['initial_gas']}")
print(f"- Gas after query: {gas_metrics['after_query_gas']}")
print(f"- Gas after iterations: {gas_metrics['final_gas']}")
print(f"- Total gas for query: {gas_metrics['query_gas']}")
print(f"- Total gas for iterations: {gas_metrics['iterations_gas']}")
print(f"- Average gas per iteration: {gas_metrics['per_iteration']}")
```

    {
      "code": 0,
      "script_result": {
        "result": {
          "cumsize": 74811,
          "exception": null,
          "gas_limit": 18446744073709551615,
          "nodes_called": 133,
          "result": {
            "after_query_gas": 59559,
            "final_gas": 103697,
            "initial_gas": 50763,
            "iterations_gas": 44138,
            "per_iteration": 8827.6,
            "query_gas": 8796
          },
          "script_gas_consumed": 49232,
          "stdout": "Iteration 1 of 5\nIteration 2 of 5\nIteration 3 of 5\nIteration 4 of 5\nIteration 5 of 5\n"
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
              "value": "dys1tvhkv3gqr90jpycaky02xa5ukhaxllu38wawhz/70",
              "index": false
            }
          ]
        },
        {
          "type": "tx",
          "attributes": [
            {
              "key": "signature",
              "value": "",
              "index": false
            }
          ]
        },
        {
          "type": "message",
          "attributes": [
            {
              "key": "action",
              "value": "/dysonprotocol.script.v1.MsgExec",
              "index": false
            },
            {
              "key": "sender",
              "value": "dys1tvhkv3gqr90jpycaky02xa5ukhaxllu38wawhz",
              "index": false
            },
            {
              "key": "module",
              "value": "script",
              "index": false
            },
            {
              "key": "msg_index",
              "value": "0",
              "index": false
            }
          ]
        },
        {
          "type": "dysonprotocol.script.v1.EventExecScript",
          "attributes": [
            {
              "key": "request",
              "value": "{\"executor_address\":\"dys1tvhkv3gqr90jpycaky02xa5ukhaxllu38wawhz\",\"script_address\":\"dys1tvhkv3gqr90jpycaky02xa5ukhaxllu38wawhz\",\"extra_code\":\"\\nfrom dys import _query, get_gas_consumed, get_script_address, get_gas_limit\\nimport json\\n\\ndef benchmark_gas(iterations=5):\\n    # Start tracking gas\\n    initial_gas = get_gas_consumed()\\n    \\n    # Perform a query that consumes gas\\n    script_address = get_script_address()\\n    balance_response = _query({\\n        \\\"@type\\\": \\\"/cosmos.bank.v1beta1.QueryBalanceRequest\\\",\\n        \\\"address\\\": script_address,\\n        \\\"denom\\\": \\\"dys\\\"\\n    })\\n    \\n    # Check gas after query\\n    after_query_gas = get_gas_consumed()\\n    \\n    # Run some iterations to measure their gas cost\\n    for i in range(iterations):\\n        print(f\\\"Iteration {i+1} of {iterations}\\\")\\n    \\n    # Check final gas consumption\\n    final_gas = get_gas_consumed()\\n    \\n    # Calculate gas used by different operations\\n    query_gas = after_query_gas - initial_gas\\n    iterations_gas = final_gas - after_query_gas\\n    \\n    return {\\n        \\\"initial_gas\\\": initial_gas,\\n        \\\"after_query_gas\\\": after_query_gas,\\n        \\\"final_gas\\\": final_gas,\\n        \\\"query_gas\\\": query_gas,\\n        \\\"iterations_gas\\\": iterations_gas,\\n        \\\"per_iteration\\\": iterations_gas / iterations\\n    }\\n\",\"function_name\":\"benchmark_gas\",\"args\":\"\",\"kwargs\":\"\",\"attached_messages\":[]}",
              "index": false
            },
            {
              "key": "response",
              "value": "{\"result\":\"{\\\"cumsize\\\":74811,\\\"exception\\\":null,\\\"gas_limit\\\":18446744073709551615,\\\"nodes_called\\\":133,\\\"result\\\":{\\\"after_query_gas\\\":59559,\\\"final_gas\\\":103697,\\\"initial_gas\\\":50763,\\\"iterations_gas\\\":44138,\\\"per_iteration\\\":8827.6,\\\"query_gas\\\":8796},\\\"script_gas_consumed\\\":49232,\\\"stdout\\\":\\\"Iteration 1 of 5\\\\nIteration 2 of 5\\\\nIteration 3 of 5\\\\nIteration 4 of 5\\\\nIteration 5 of 5\\\\n\\\"}\",\"attached_message_results\":[]}",
              "index": false
            },
            {
              "key": "msg_index",
              "value": "0",
              "index": false
            }
          ]
        }
      ]
    }
    Gas report for benchmark operations:
    - Initial gas consumed: 50763
    - Gas after query: 59559
    - Gas after iterations: 103697
    - Total gas for query: 8796
    - Total gas for iterations: 44138
    - Average gas per iteration: 8827.6


### Gas Limits

Each execution has a gas limit to prevent infinite loops or excessive computation. Let's check the gas limit for our execution:


```python
# Create a script to check the gas limit
gas_limit_script = '''
from dys import get_gas_limit

def check_limit():
    # Check the gas limit for the current execution
    limit = get_gas_limit()
    return {"gas_limit": limit}
'''

# Save and execute the script
with open('/tmp/gas_limit.py', 'w') as f:
    f.write(gas_limit_script)

out = ! ../scripts/simulate_exec.py /tmp/gas_limit.py --from alice --script-address $ALICE_ADDRESS --function-name check_limit
out = '\n'.join(out)
result = json.loads(out)

# Extract and display the gas limit
script_result = result['script_result']['result']
gas_limit = script_result['result']['gas_limit']
print(f"Gas limit for this execution: {gas_limit}")
```

    Gas limit for this execution: 18446744073709551615


### Node Execution Tracking

The dyslang module tracks the execution of Python AST nodes. This is useful for understanding the computational complexity of your scripts:


```python
# Create a script to measure node execution
node_count_script = '''
from dys import _query, get_nodes_called, get_script_address
import json

def count_nodes():
    """
    Demonstrate node counting by performing operations of varying complexity
    """
    # Simple operations
    a = 1 + 2
    
    # More complex operation that will use more nodes
    script_address = get_script_address()
    _query({
        "@type": "/cosmos.bank.v1beta1.QueryBalanceRequest",
        "address": script_address,
        "denom": "dys"
    })
    
    # Complex calculation with loop
    result = 0
    for i in range(10):
        result += i * 2
    
    # Get the count of AST nodes evaluated
    nodes_called = get_nodes_called()
    
    return {
        "nodes_called": nodes_called,
        "calculation_result": result
    }
'''

# Save and execute the script
with open('/tmp/node_count.py', 'w') as f:
    f.write(node_count_script)

out = ! ../scripts/simulate_exec.py /tmp/node_count.py --from alice --script-address $ALICE_ADDRESS --function-name count_nodes
out = '\n'.join(out)
result = json.loads(out)

# Extract and display the node metrics
script_result = result['script_result']['result']
node_metrics = script_result['result']
print(f"Node execution metrics:")
print(f"- Nodes called: {node_metrics['nodes_called']}")
print(f"- Calculation result: {node_metrics['calculation_result']}")
```

    Node execution metrics:
    - Nodes called: 106
    - Calculation result: 90


### Memory Usage Tracking

The dyslang module also tracks memory usage through the `get_cumulative_size()` function:


```python
# Create a script to check memory usage
memory_script = '''
from dys import get_cumulative_size

def check_memory():
    # Check the cumulative memory size used
    size = get_cumulative_size()
    return {"memory_used": size}
'''

# Save and execute the script
with open('/tmp/memory_check.py', 'w') as f:
    f.write(memory_script)

out = ! ../scripts/simulate_exec.py /tmp/memory_check.py --from alice --script-address $ALICE_ADDRESS --function-name check_memory
out = '\n'.join(out)
result = json.loads(out)

# Extract and display the memory usage
script_result = result['script_result']['result']
memory_used = script_result['result']['memory_used']
print(f"Memory usage: {memory_used} bytes")
```

    Memory usage: 403 bytes


## Context Information

The dyslang module provides several functions to access contextual information about the current execution environment, including the script's address, the executor's address, and block information.

### Script and Executor Addresses

Let's create a script that retrieves information about the script's own address and the address of the account executing the script:


```python
# Create a script to get address information
address_script = '''
from dys import get_executor_address, get_script_address

def who_called_me():
    """Returns information about who executed this script"""
    # Get the script's own address
    script_address = get_script_address()
    
    # Get the address of who called this script
    caller_address = get_executor_address()
    
    # Check if the script was called by its owner
    is_self_call = script_address == caller_address
    
    return {
        "script_address": script_address,
        "caller_address": caller_address,
        "is_self_call": is_self_call
    }
'''

# Save and execute the script
with open('/tmp/address_info.py', 'w') as f:
    f.write(address_script)

# Execute with Bob calling Alice's script
out = ! ../scripts/simulate_exec.py /tmp/address_info.py --from bob --script-address $ALICE_ADDRESS --function-name who_called_me
out = '\n'.join(out)
result = json.loads(out)

# Extract and display the address information
script_result = result['script_result']['result']
address_info = script_result['result']
print(f"Script Address: {address_info['script_address']}")
print(f"Executor Address: {address_info['caller_address']}")
print(f"Self-execution: {address_info['is_self_call']}")
```

    Script Address: dys1tvhkv3gqr90jpycaky02xa5ukhaxllu38wawhz
    Executor Address: dys1fhhxp9xveswc4yhxekr32eqe80rkwpurya0jh0
    Self-execution: False


### Block Information

Let's retrieve information about the current block:


```python
# Create a script to get block information
block_info_script = '''
from dys import get_block_info

def show_block_info():
    """Get basic block information"""
    block = get_block_info()
    return {
        "height": block.get("Height"),
        "chain_id": block.get("ChainID"),
        "time": block.get("Time")
    }
'''

# Save and execute the script
with open('/tmp/block_info.py', 'w') as f:
    f.write(block_info_script)

out = ! ../scripts/simulate_exec.py /tmp/block_info.py --from alice --script-address $ALICE_ADDRESS --function-name show_block_info
out = '\n'.join(out)
result = json.loads(out)

# Extract and display the block information
script_result = result['script_result']['result']
block_info = script_result['result']
print(f"Block Information:")
print(f"- Height: {block_info['height']}")
print(f"- Chain ID: {block_info['chain_id']}")
print(f"- Time: {block_info['time']}")
```

    Block Information:
    - Height: None
    - Chain ID: None
    - Time: None


## Transaction Data

The dyslang module allows scripts to access information about attached messages in transactions. This is particularly useful for scripts that need to process multiple operations in a single transaction.

### Attached Messages

Let's create a script that checks for attached messages:


```python
# Create a script to check for attached messages

msg1 = shlex.quote(json.dumps({
        "@type":"/cosmos.bank.v1beta1.MsgSend",
        "from_address": ALICE_ADDRESS,
        "to_address": BOB_ADDRESS,
        "amount":[{"denom":"dys","amount":"12"}]
    }))


msg2 = shlex.quote(json.dumps({
    "@type":"/cosmos.bank.v1beta1.MsgSend",
    "from_address": ALICE_ADDRESS   ,
    "to_address": BOB_ADDRESS,
    "amount":[{"denom":"dys","amount":"34"}]
}))

attached_msgs_script = '''
from dys import get_attached_messages, get_attached_msg_results

def check_messages():
    # Access attached messages
    attached_messages = get_attached_messages()
    attached_msg_results = get_attached_msg_results()
    return {"attached_messages": attached_messages, "attached_msg_results": attached_msg_results}
'''

# Save and execute the script
with open('/tmp/attached_msgs.py', 'w') as f:
    f.write(attached_msgs_script)

out = ! ../scripts/simulate_exec.py /tmp/attached_msgs.py \
    --from alice \
    --script-address $ALICE_ADDRESS \
    --function-name check_messages \
    --attached-message $msg1 \
    --attached-message $msg2 \
    
out = '\n'.join(out)
result = json.loads(out)

# Extract and display the attached messages
script_result = result['script_result']['result']
messages = script_result['result']['attached_messages']
results = script_result['result']['attached_msg_results']
for m, r in zip(messages, results):
    print(f"Message: {m}")
    print(f"Result: {r}")

```

    Message: {'@type': '/cosmos.bank.v1beta1.MsgSend', 'amount': [{'amount': '12', 'denom': 'dys'}], 'from_address': 'dys1tvhkv3gqr90jpycaky02xa5ukhaxllu38wawhz', 'to_address': 'dys1fhhxp9xveswc4yhxekr32eqe80rkwpurya0jh0'}
    Result: {'@type': '/cosmos.bank.v1beta1.MsgSendResponse'}
    Message: {'@type': '/cosmos.bank.v1beta1.MsgSend', 'amount': [{'amount': '34', 'denom': 'dys'}], 'from_address': 'dys1tvhkv3gqr90jpycaky02xa5ukhaxllu38wawhz', 'to_address': 'dys1fhhxp9xveswc4yhxekr32eqe80rkwpurya0jh0'}
    Result: {'@type': '/cosmos.bank.v1beta1.MsgSendResponse'}


## Events and Evaluation

The dyslang module provides functions to emit blockchain events and evaluate dynamic code at runtime.

### Emitting Events

Let's create a script that emits a custom event to the blockchain:


```python
# Create a script to emit an event
emit_event_script = '''
from dys import emit_event

def emit_test_event():
    # Emit a custom event, none is a success or an exception is raised
    emit_event("payment_processed", "success")
    emit_event("foo", '123123')
    return {"event_emitted": True}
'''

# Save and execute the script
with open('/tmp/emit_event.py', 'w') as f:
    f.write(emit_event_script)

out = ! ../scripts/simulate_exec.py /tmp/emit_event.py --from alice --script-address $ALICE_ADDRESS --function-name emit_test_event
out = '\n'.join(out)

result = json.loads(out)
for event in result['events']:
    if event['type'] == "dysonprotocol.script.v1.EventScriptEvent":
        for attribute in event['attributes']:
            print(f"{attribute['key']}: {attribute['value']}")

```

    address: "dys1tvhkv3gqr90jpycaky02xa5ukhaxllu38wawhz"
    key: "payment_processed"
    value: "success"
    msg_index: 0
    address: "dys1tvhkv3gqr90jpycaky02xa5ukhaxllu38wawhz"
    key: "foo"
    value: "123123"
    msg_index: 0


### Dynamic Code Evaluation

The `dys_eval` function allows you to evaluate Python code dynamically at runtime. This is a powerful feature that enables creating flexible and adaptable scripts:


```python
# Create a script for dynamic code evaluation
dys_eval_script = '''
from dys import dys_eval

def demonstrate_dys_eval():
    """Demonstrate different ways to use dys_eval"""
    results = {}
    
    # Simple arithmetic
    results["arithmetic"] = dys_eval("2 + 3 * 4")
    
    # String operations
    results["string_ops"] = dys_eval("'hello ' + 'world'.upper()")
    
    # Using variables from current scope
    x = 10
    y = 5
    local_scope = {'x': x, 'y': y}
    results["with_variables"] = dys_eval("x * y", scope=local_scope)
    
    # Multiple statements
    results["multi_statement"] = dys_eval("""
a = 5
b = 7
result = a * b
result + 3
""")
    
    return results
'''

# Save and execute the script
with open('/tmp/dys_eval.py', 'w') as f:
    f.write(dys_eval_script)

out = ! ../scripts/simulate_exec.py /tmp/dys_eval.py --from alice --script-address $ALICE_ADDRESS --function-name demonstrate_dys_eval
out = '\n'.join(out)
result = json.loads(out)

# Extract and display the evaluation results
script_result = result['script_result']['result']
eval_results = script_result['result']
print(f"Dynamic evaluation results:")
print(f"- Arithmetic: {eval_results['arithmetic']}")
print(f"- String operations: {eval_results['string_ops']}")
print(f"- With variables: {eval_results['with_variables']}")
print(f"- Multi-statement: {eval_results['multi_statement']}")
```

    Dynamic evaluation results:
    - Arithmetic: 14
    - String operations: hello WORLD
    - With variables: 50
    - Multi-statement: 38


## Testing and Coverage

The dyslang module includes built-in tools for testing and code coverage analysis. By prefixing function names with `test_`, you can enable coverage mode, which provides detailed information about which parts of your code are being executed.

### Code Coverage Analysis

Let's create a script with a test function to demonstrate code coverage analysis:


```python
# Get Charlie's address
[CHARLIE_ADDRESS] = ! dysond keys show -a charlie

# Create a script with test coverage
coverage_script = '''
def a_or_b(a, b):
    if a:
        return a
    if b:
        return b
    return None

def test_a_or_b():
    # Test with different inputs
    a_or_b(1, 0)  # Should return a
    a_or_b(1, 1)  # Should still return a (first condition)
    # Note: We're not testing the b condition or the fallback
'''

# Save and execute the script
with open('/tmp/coverage_test.py', 'w') as f:
    f.write(coverage_script)

out = ! ../scripts/simulate_exec.py /tmp/coverage_test.py --from charlie --script-address $CHARLIE_ADDRESS --function-name test_a_or_b
out = '\n'.join(out)
result = json.loads(out)

# Extract and interpret the coverage data
script_result = result['script_result']['result']
coverage_data = script_result['result']

# Display a simplified analysis of the coverage data
print("Coverage Analysis Results:")
for item in coverage_data:
    if len(item) == 2 and isinstance(item[0], list) and len(item[0]) == 5:
        node_info = item[0]
        count = item[1]
        line = node_info[0]
        node_type = node_info[4]
        
        # Simplify the coverage output for key lines
        if node_type == "FunctionDef" and line == 3:
            print(f"- FunctionDef (a_or_b): executed {count} time{'s' if count != 1 else ''}")
        elif node_type == "If" and line == 4:
            print(f"- If (line {line}): {f'executed {count} times' if count > 0 else 'never executed'}")
        elif node_type == "If" and line == 6:
            print(f"- If (line {line}): {f'executed {count} times' if count > 0 else 'never executed'}")
        elif node_type == "Return" and line == 5:
            print(f"- Return (line {line}): {f'executed {count} times' if count > 0 else 'never executed'}")
        elif node_type == "Return" and line == 7:
            print(f"- Return (line {line}): {f'executed {count} times' if count > 0 else 'never executed'}")
        elif node_type == "Return" and line == 8:
            print(f"- Return (fallback): {f'executed {count} times' if count > 0 else 'never executed'}")
```

    Coverage Analysis Results:


From the coverage analysis, we can see that:

1. The `a_or_b` function was defined (executed once)
2. The first `if` condition (line 4) was evaluated twice and passed both times
3. The first `return` statement (line 5) was executed twice
4. The second `if` condition (line 6) was never evaluated because the first condition always passed
5. The second `return` statement (line 7) was never executed
6. The fallback `return None` (line 8) was never executed

This coverage analysis helps us identify test gaps in our code. In this case, we need to add tests for when the first condition fails to ensure we're testing all code paths.

## Security Constraints

The Dyson Protocol implements several security constraints to ensure safe and reliable execution of scripts:

### Gas Limits

All script executions are bound by gas limits to prevent infinite loops and excessive computation. As we saw earlier, you can query the gas limit for any execution using `get_gas_limit()`.

### Memory Restrictions

The dyslang module enforces limits on string lengths, stack depth, and scope sizes to prevent resource exhaustion. You can monitor memory usage with `get_cumulative_size()`.

### Sandboxed Environment

Scripts run in a carefully controlled environment where only whitelisted functions and modules are available. This prevents access to potentially dangerous system functions.

### Node Calls Tracking

As we've seen, the execution environment tracks AST node evaluations and terminates if limits are exceeded, preventing resource-exhaustion attacks.

## Building a Simple dApp

Let's bring everything together by building a simple counter dApp that demonstrates the integration of dyslang with the Storage module:


```python
import json
import shlex

# Create the counter dApp script
counter_app_script = '''
from dys import _query, _msg, get_script_address
import json
from datetime import datetime

def get_counter():
    """Get the current counter value or initialize it"""
    script_address = get_script_address()
    # Try to query the existing counter
    try:
        response = _query({
            "@type": "/dysonprotocol.storage.v1.QueryStorageGetRequest",
            "owner": script_address,
            "index": "counter"
        })
        counter_data = json.loads(response["entry"]["data"])
        return counter_data["value"]
    except Exception as e:
        if "NotFound" in str(e):
            _msg({
                "@type": "/dysonprotocol.storage.v1.MsgStorageSet",
                "owner": script_address,
                "index": "counter",
                "data": json.dumps({
                    "value": 0, 
                    "updated_at": datetime.now().isoformat()
                })
            })
            return 0
        else:
            raise e



def increment_counter():
    """Increment the counter and store the new value"""
    # Get the current counter value
    current_value = get_counter()
    
    # Increment it
    new_value = current_value + 1
    
    # Store the new value
    script_address = get_script_address()

    _msg({
        "@type": "/dysonprotocol.storage.v1.MsgStorageSet",
        "owner": script_address,
         "index": "counter",
         "data": json.dumps({
            "value": new_value,
            "updated_at": datetime.now().isoformat()
        })
    })

    
    return {
        "previous_value": current_value,
        "new_value": new_value
    }

def reset_counter():
    """Reset the counter to zero"""
    script_address = get_script_address()
    _msg({
        "@type": "/dysonprotocol.storage.v1.MsgStorageDelete",
        "owner": script_address,
        "indexes": ["counter"]
    })
    return {
        "result": "Counter reset to 0"
    }
'''

# Save the counter app script
with open('/tmp/counter_app.py', 'w') as f:
    f.write(counter_app_script)

print(f"Setting up counter dApp for alice...")

# First, upload the script to Alice's account
out = ! dysond tx script update \
    --code-path /tmp/counter_app.py \
    --from alice \
    --output json -y | dysond query wait-tx --output json
out = '\n'.join(out)
result = json.loads(out)

for i in range(3):
    # Now let's test the counter app
    # 1. Get initial counter (should be 0, then set to 1)
    out = ! dysond tx script exec \
        --script-address $ALICE_ADDRESS \
        --function-name increment_counter \
        --from alice \
        --output json -y | dysond query wait-tx --output json | python ../scripts/parse_exec_script_tx.py
    out = '\n'.join(out)
    result = json.loads(out)
    assert result['code'] == 0, f"Error: {result['raw_log']}"
    counter_result = result['script_result']['result']['result']
    print(f"Counter state: {counter_result['previous_value']} -> {counter_result['new_value']}")

# 4. Reset the counter for cleanup
print(f"Cleaning up...")
out = ! dysond tx script exec \
    --script-address $ALICE_ADDRESS \
    --function-name reset_counter \
    --from alice \
    --output json -y | dysond query wait-tx --output json | python ../scripts/parse_exec_script_tx.py
out = '\n'.join(out)
result = json.loads(out)
assert result['code'] == 0, f"Error: {result['raw_log']}"

print(f"Counter dApp demo completed successfully!")
```

    Setting up counter dApp for alice...


    Counter state: 0 -> 1


    Counter state: 1 -> 2


    Counter state: 2 -> 3
    Cleaning up...


    Counter dApp demo completed successfully!


## Summary

In this guide, we've explored the powerful features of the Dyson Protocol Language Module (dyslang). We've seen how to:

1. **Query the Blockchain**: Use `_query` to retrieve blockchain state
2. **Submit Transactions**: Use `_msg` to modify blockchain state
3. **Monitor Gas**: Track and manage computational resources
4. **Access Context**: Retrieve script and block information
5. **Handle Messages**: Work with transaction messages
6. **Emit Events**: Produce blockchain events
7. **Evaluate Code**: Execute dynamic Python code
8. **Test Coverage**: Analyze script execution paths
9. **Build dApps**: Combine these features to create decentralized applications

The dyslang module provides a secure, sandboxed environment for executing Python code on the blockchain, making it possible to build sophisticated decentralized applications with familiar Python syntax and powerful blockchain capabilities.

For more information on building scripts with these functions and integrating with other modules like Storage, check out the [Script Module Documentation](SCRIPT.md) and the other guides in the Dyson Protocol documentation.
