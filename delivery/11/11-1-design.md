# TewQueue and TewChain Integration Design Document

## Overview

This document outlines the technical design for merging TewQueue and TewChain into a unified `queue_chain.py` module.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    User Transaction Code                     │
│              (TewTxMsgData.data - Python code)              │
└─────────────────────────────────┬───────────────────────────┘
                                  │ calls
                                  ▼
┌─────────────────────────────────────────────────────────────┐
│                      chain_logic.py                          │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ on_tx() - Exposes validated wrapper functions:         │ │
│  │ • send_greeting_to_l1("good morning")                 │ │
│  │ • send_greeting_to_l2("hello L2")                     │ │
│  └────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ Queue Callbacks:                                       │ │
│  │ • on_queue_message(message) - Process incoming        │ │
│  │ • on_queue_response(response) - Handle responses      │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────┬───────────────────────────┘
                                  │ uses
                                  ▼
┌─────────────────────────────────────────────────────────────┐
│                      queue_chain.py                          │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ TewChain Components:                                   │ │
│  │ • build_next_block() - Main block processing          │ │
│  │ • QueueStateDict - Extended state with queue fields   │ │
│  │ • verify_signed_data() - Transaction validation       │ │
│  └────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ TewQueue Components:                                   │ │
│  │ • L1/L2 dataclasses with queue management             │ │
│  │ • Message/Response dataclasses                        │ │
│  │ • Factory functions (create_l1/l2_from_snapshot)      │ │
│  └────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ Integration Layer:                                     │ │
│  │ • process_queue_messages() - Auto queue processing    │ │
│  │ • Extended tew_module with queue functions           │ │
│  │ • Queue state persistence in block state             │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## Data Flow

### 1. User Transaction Flow
```
User submits TewTx with Python code
    ↓
build_next_block() validates transaction
    ↓
on_tx() callback executes user code in sandboxed dys_eval
    ↓
User code calls send_greeting_to_l1("good morning")
    ↓
Wrapper validates input (string, ≤100 chars)
    ↓
tew.send_l1_message() adds to L1 queue
    ↓
Queue state saved in block post_state
```

### 2. Queue Processing Flow (on_begin_block)
```
New block starts
    ↓
process_queue_messages() runs automatically
    ↓
L1 processes L2's outgoing messages
    ↓
on_queue_message() callback invoked for each message
    ↓
L2 processes L1's outgoing messages
    ↓
on_queue_response() callback invoked for each response
    ↓
Updated queue states saved
    ↓
Normal transaction processing begins
```

## Storage Schema

### Block State (QueueStateDict)
```python
{
    # Existing TewChain state
    "chain_logic": "...",
    "accounts_by_number": {...},
    "account_numbers_by_address": {...},
    "next_account_number": 1,
    
    # NEW: Queue state fields
    "l1_queue_state": {
        "queue_metadata": {"next_message_id": 0, "last_height": 0},
        "outgoing_queue": {},  # msg_id -> Message
        "response_queue": {}   # msg_id -> Response
    },
    "l2_queue_state": {
        "queue_metadata": {"next_message_id": 0, "last_height": 0},
        "outgoing_queue": {},  # msg_id -> Message
        "response_queue": {}   # msg_id -> Response
    }
}
```

### Storage Keys
- L1 state: Persisted to DysonProtocol storage at `tew/{instance_id}/l1`
- L2 state: Stored in block state, persisted across blocks

## Module Structure

### queue_chain.py
```python
# ===== Imports =====
from dys import _query, _msg, get_script_address, get_executor_address, dys_eval
import json
from datetime import datetime
from typing import Any, Dict, Optional, TypedDict
from dataclasses import dataclass, field, asdict

# ===== TewQueue Components =====
@dataclass
class Message: ...
@dataclass 
class Response: ...
@dataclass
class Queueable: ...
@dataclass
class L1(Queueable): ...
@dataclass
class L2(Queueable): ...

# Factory functions
def create_l1_from_snapshot(...): ...
def create_l2_from_snapshot(...): ...

# ===== TewChain Components =====
class TewTxResult(TypedDict): ...
class StateDict(TypedDict): ...
class QueueStateDict(StateDict): ...  # NEW: Extended state
class Metadata(TypedDict): ...

# ===== Integration Functions =====
def process_queue_messages(l1_queue, l2_queue, chain_scope): ...
def build_next_block(block, prev_block_meta, block_hash): ...
```

## Callback Interface

### Required chain_callbacks
```python
{
    "on_begin_block": callable,
    "on_tx": callable,
    "on_end_block": callable,
    "on_queue_message": callable,    # NEW
    "on_queue_response": callable    # NEW  
}
```

### Queue Callback Signatures
```python
def on_queue_message(message: Message) -> Any:
    """Process incoming queue message"""
    
def on_queue_response(response: Response) -> None:
    """Handle queue response/acknowledgment"""
```

## Error Handling Strategy

1. **Queue Processing Errors**: Logged via chain_scope["print"], don't fail block
2. **Validation Errors**: Raised immediately in wrapper functions
3. **State Persistence Errors**: Fail the block (critical)
4. **Callback Errors**: Logged but continue processing

## Migration Path

1. Create `queue_chain.py` by merging both modules
2. Update imports to preserve all APIs
3. Extend StateDict with queue fields
4. Add queue processing to build_next_block
5. Update chain_logic validation
6. Create comprehensive tests
7. Verify backward compatibility 

---

## Addendum: Architecture Simplification (2025-01-02)

The implementation has evolved from the original design. The chain_logic layer has been removed, simplifying the architecture:

### Updated Architecture Diagram:
```
┌─────────────────────────────────────────────────────────────┐
│                    User Transaction Code                     │
│              (TewTxMsgData.data - Python code)              │
└─────────────────────────────────┬───────────────────────────┘
                                  │ calls safe wrapper functions
                                  ▼
┌─────────────────────────────────────────────────────────────┐
│                      queue_chain.py                          │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ L1 and L2 Classes (with built-in logic):              │ │
│  │ • L1.on_message() - Process messages from L2          │ │
│  │ • L2.on_message() - Process messages from L1          │ │
│  │ • Safe wrapper functions exposed to TEW transactions  │ │
│  └────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ TewChain Components:                                   │ │
│  │ • build_next_block() - Main block processing          │ │
│  │ • QueueStateDict - State without chain_logic field    │ │
│  │ • on_tx_wrapper() - Minimal sandbox for TEW tx        │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### Key Changes:
1. **No chain_logic.py**: The intermediate layer has been removed
2. **No chain_logic field**: QueueStateDict no longer contains a `chain_logic` string field
3. **Direct implementation**: Queue callbacks are now methods of L1/L2 classes
4. **Minimal sandbox**: TEW transactions run with only safe wrapper functions:
   - `send_l1_message(text)` - Send text to L1 (max 20 chars)
   - `send_l2_message(text)` - Send text to L2 (max 20 chars)
   - `query_dyson(params)` - Query Dyson storage through L1

### Updated Storage Schema:
```python
{
    # TewChain state (chain_logic field removed)
    "accounts_by_number": {...},
    "account_numbers_by_address": {...},
    "next_account_number": 1,
    
    # Queue state fields (unchanged)
    "l1_queue_state": {...},
    "l2_queue_state": {...}
}
```

This simplification maintains the security model while reducing complexity and removing the need for separate chain_logic source code storage. 