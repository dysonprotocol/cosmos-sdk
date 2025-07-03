# TEW Protocol Security Model

## Overview

The TEW Protocol implements a multi-layered security sandbox to ensure safe execution of untrusted code. Each layer runs with progressively restricted permissions.

## Security Layers

### 1. TEW Script (Top Level)
- **Access Level**: Full blockchain access
- **Available Functions**: All `dys` module functions
- **Responsibilities**: 
  - Manage all TEW instances
  - Validate and store data
  - Execute sandboxed code

### 2. L1 Core Logic (First Sandbox)
- **Access Level**: READ-ONLY blockchain access
- **Available Functions** (whitelisted only):
  - `_query`: Read blockchain state
  - `get_script_address`: Get TEW script address
  - `get_executor_address`: Get caller address
  - ❌ `_msg`: NOT AVAILABLE (security critical - TEW instances cannot send transactions)
- **Available Modules**:
  - `json`: For data serialization
- **Restrictions**:
  - Cannot send blockchain transactions (_msg not provided)
  - Cannot import `dys` module directly
  - Cannot access filesystem or network
  - Cannot execute arbitrary code
  - Can only modify `l1_state`
  - Has read-only access to `l2_state`

### 3. L2 Core Logic (Second Sandbox)
- **Access Level**: No blockchain access
- **Available Functions**:
  - None from blockchain
- **Available Modules**:
  - `json`: For data serialization
  - `tew`: Virtual module providing `tew_eval`
- **Restrictions**:
  - No blockchain interaction
  - Cannot modify `l1_state` 
  - Can only modify `l2_state`
  - Must implement `_apply_slots()` function

### 4. Slot Logic (Third Sandbox)
- **Access Level**: Extremely restricted
- **Available Functions**:
  - Only what L2 core logic explicitly provides via `tew_eval`
- **Available Modules**:
  - `json`: If L2 provides it
- **Restrictions**:
  - Cannot modify state directly
  - Can only set variables in provided scope
  - Extremely limited execution environment

## Implementation Details

### L1 Core Logic Execution
```python
# L1 executes with READ-ONLY functions in scope
scope = {
    "l1_state": {...},           # Mutable
    "l2_state": {...},           # Read-only
    "_query": _query,            # Read blockchain state
    "get_script_address": ...,   # Get TEW script address
    "get_executor_address": ..., # Get caller address
    # NO _msg - TEW instances cannot send transactions!
}

dys_eval(l1_core_logic, scope=scope, module_dict={
    "json": {"loads": json.loads, "dumps": json.dumps}
})
```

### L2 Core Logic Execution
```python
# L2 executes with no blockchain access
scope = {
    "l2_state": {...},  # Mutable
    "slots": {...},     # Slot submissions
}

dys_eval(l2_core_logic, scope=scope, module_dict={
    "json": {...},
    "tew": {"tew_eval": tew_eval}  # For executing slots
})
```

### Slot Logic Execution
```python
# Slots execute in most restricted environment
slot_scope = {
    "state": {...},     # Read-only view of L2 state
    "author": "...",    # Slot author
    "message": None,    # Variable slots can set
}

# L2 decides what modules to provide
tew_eval(slot_code, scope=slot_scope, module_dict={
    "json": {...}  # Optional, L2's choice
})
```

## Security Principles

1. **Principle of Least Privilege**: Each layer has only the minimum required permissions
2. **Explicit Whitelisting**: Functions must be explicitly provided, no implicit access
3. **Scope Isolation**: Deep copying prevents unintended mutations
4. **No Module Imports**: Lower layers cannot import system modules
5. **Controlled Execution**: All code runs through `dys_eval` with restrictions

## Common Pitfalls to Avoid

1. **Don't import `dys` in L1/L2 logic** - Use provided functions in scope
2. **Don't assume module availability** - Only use explicitly provided modules
3. **Don't try to break out of sandbox** - Security restrictions are enforced
4. **Don't mutate wrong state** - L1 modifies l1_state, L2 modifies l2_state

## Example: Safe L1 Core Logic
```python
# CORRECT - Uses provided READ-ONLY functions
def check_balance(address):
    response = _query({  # _query is provided in scope
        "@type": "/cosmos.bank.v1beta1.QueryBalanceRequest",
        "address": address,
        "denom": "dys"
    })
    return response["balance"]["amount"]

# WRONG - Tries to send transactions
def send_tokens_wrong(recipient, amount):
    _msg({  # This will fail! _msg is NOT provided
        "@type": "/cosmos.bank.v1beta1.MsgSend",
        # ...
    })

# WRONG - Tries to import
def query_wrong(address):
    from dys import _query  # This will fail!
    # ...
```

## Testing Security

Always test your TEW logic in a sandboxed environment first. Verify:

1. L1 logic doesn't try to import `dys`
2. L2 logic doesn't try to access blockchain
3. Slot logic only uses provided variables
4. State mutations happen in correct layer

The multi-layered sandbox ensures that even malicious code cannot compromise the blockchain or other TEW instances. 