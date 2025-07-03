# DysonProtocol L2 – **TewProtocol Specification v0.4**

> **Status:** Draft (supersedes v0.3)
>
> This version introduces a three-layer architecture: TewProtocol (specification), TewFramework (reference implementation), and TewApp (deployed instances). Each TewApp is a standalone DysonProtocol script that incorporates the framework code along with app-specific logic.

---

## 0 · Scope & Purpose

This document specifies the **TewProtocol**, the consensus communication protocol between Layer-1 (L1) and Layer-2 (L2) for building deterministic Proof-of-Authority applications on the Dyson Protocol blockchain. 

The architecture consists of:
- **TewProtocol** (this document): Defines consensus rules and communication patterns
- **TewFramework**: Reference implementation providing generic L2 infrastructure
- **TewApp**: Specific applications deployed as standalone DysonProtocol scripts
- **TewInstance**: A specific L2 instance created within an app

**Key Design Philosophy**: TewInstances are designed to be **ephemeral** - created when needed, used for their purpose, and cleanly terminated when done. This enables use cases like temporary payment channels, real-time auctions, gaming sessions, and other short-lived activities without permanent infrastructure overhead.

---

## 1 · Architecture Overview

### 1.1 Three-Layer Architecture

| Layer | Purpose | Nature |
|-------|---------|--------|
| **TewProtocol** | L1/L2 consensus specification | Document/Standard |
| **TewFramework** | Generic implementation template | Reference code |
| **TewApp** | Deployed application instance | DysonProtocol script |

### 1.2 Deployment Model

Each TewApp is deployed as a standalone DysonProtocol script that:
1. **Incorporates** the TewFramework code (copied/forked)
2. **Implements** app-specific L1 and L2 logic
3. **Manages** its own TEW instances internally
4. **Exposes** standard entry points for TEW operations

```
DysonProtocol Script (e.g., TEW Thunder a payment channel app)
├── TewFramework code (copied)
│   ├── Round management
│   ├── Slot validation
│   ├── Web dashboard
│   └── Peer discovery
└── App-specific code
    ├── L1 logic (deposits, withdrawals)
    └── L2 logic (transfers, settlements)
```

### 1.3 Key Design Principles

1. **Self-Contained Apps** – Each TewApp is a complete, standalone script
2. **No Central Protocol** – No shared protocol script; each app manages itself
3. **Framework as Template** – TewFramework is copied/modified per app
4. **Script as Source of Truth** – The deployed script contains all logic
5. **Ephemeral Instances** – Tew instances are lightweight and designed for temporary use

### 1.4 Ephemeral Instance Lifecycle

TewInstances follow a natural lifecycle:

```
Create → Active Use → Settlement → Termination
```

**Examples of ephemeral use cases:**
- **Payment Channels**: Create for a trading session, close when done
- **Auction Rounds**: Spin up for each auction, terminate after winner determined
- **Voting Sessions**: Create for proposal voting period, archive after decision
- **Gaming Tables**: Create per game session, settle and close when game ends

This ephemeral nature means:
- Low overhead for creating new instances
- No long-term state bloat
- Clean separation between different activities
- Easy to reason about security boundaries

---

## 2 · TewProtocol Specification

### 2.1 Core Protocol Invariants

These rules MUST be followed by all TewApp implementations:

1. **Round Monotonicity** – Rounds progress sequentially without gaps
2. **Committee Consensus** – Valid rounds require participation from all members
3. **State Determinism** – Same inputs produce same state transitions
4. **Timeout Guarantees** – On-chain fallback ensures liveness

### 2.2 Storage Schema

Each TewApp MUST use this storage layout for TewInstances:

```
Storage Key Pattern (within app's namespace):
tew/{instance_id}/l1/state                    # L1 state (JSON)
tew/{instance_id}/l1/meta                     # Instance metadata
tew/{instance_id}/l2/rounds/{round:010d}      # L2 round commits
tew/{instance_id}/l2/latest_round             # Current round
tew/{instance_id}/balances/{denom}            # Escrowed funds
tew/{instance_id}/slots/{round}/{member}/{hash} # Slot submissions
```

### 2.3 Required Entry Points

Each TewApp script MUST implement these public functions:

```python
def create_tew(config: dict) -> dict:
    """Create a new TewInstance within this app"""
    pass

def submit_slot(instance_id: str, signed_slot_tx: str) -> dict:
    """Submit a slot for the next round"""
    pass

def call_l1_function(instance_id: str, func_name: str, *args) -> dict:
    """Execute L1 logic for an instance"""
    pass

def checkpoint_round(instance_id: str, round: int, signed_slots: list) -> dict:
    """Fast-forward checkpoint (off-chain consensus)"""
    pass

def signal_force_onchain(instance_id: str, round: int) -> dict:
    """Signal intent to force on-chain execution"""
    pass

def progress_round(instance_id: str) -> dict:
    """Execute round on-chain (fallback)"""
    pass

def terminate_instance(instance_id: str) -> dict:
    """Cleanly terminate an instance, settling any remaining balances"""
    pass

def wsgi(environ, start_response):
    """Web dashboard (read-only)"""
    pass
```

### 2.4 Instance Termination

TewInstances SHOULD implement clean termination:

1. **Settlement Phase**: Ensure all balances are properly distributed
2. **Archive State**: Move final state to archive storage (optional)
3. **Release Resources**: Clean up active storage to prevent bloat
4. **Emit Events**: Notify participants of termination

Example termination pattern:
```python
def terminate_instance(instance_id: str) -> dict:
    # 1. Verify caller has permission (e.g., all members agree)
    # 2. Process any pending withdrawals
    # 3. Distribute remaining escrow to members
    # 4. Archive final L2 state for audit trail
    # 5. Clear active storage keys
    return {"status": "terminated", "final_round": N}
```

### 2.5 L2 Execution Model (RunScript Queries)

L2 nodes interact with the TewApp through read-only `RunScript` queries, ensuring consistent logic execution without modifying on-chain state:

**Key Principles:**
1. **Read-Only Queries**: L2 nodes use `dysond query script run` to execute L2 logic
2. **Local State Management**: Each L2 node maintains rounds and state locally between queries
3. **Deterministic Execution**: All nodes execute the same logic and reach consensus
4. **No On-Chain Side Effects**: RunScript queries cannot modify blockchain state

**Example L2 Query Pattern:**
```bash
# L2 node queries the script to process a round
dysond query script run \
  --executor-address dys1committee_member... \
  --script-address dys1thunder... \
  --function-name process_l2_round \
  --args '[{
    "instance_id": "channel_001",
    "current_state": {...},
    "slots": {...}
  }]'
```

**Benefits:**
- **Consistency**: All L2 nodes run identical logic from the on-chain script
- **Upgradability**: Script updates automatically apply to all L2 nodes
- **Gas-Free**: Read queries don't consume gas or require fees
- **Isolation**: L2 execution cannot accidentally modify L1 state

This execution model mirrors the test behavior where `_msg` calls in query mode persist only within the specific RunScript context but don't affect the blockchain state.

**Implementation Note**: The `test_query_script.py::test_query_script` test demonstrates this behavior - any state modifications made during a RunScript query (including `_msg` calls) are visible within that execution but don't persist to the blockchain. This isolation is crucial for L2 nodes to safely execute logic without risking accidental state corruption.

**Architecture Benefits**: This RunScript approach ensures that:
- L2 logic is always consistent with the on-chain script
- Script upgrades automatically propagate to all L2 nodes
- L2 execution cannot accidentally corrupt L1 state
- The same script code handles both L1 transactions and L2 queries

---

## 3 · TewFramework Reference Implementation

### 3.1 Framework Components

The TewFramework provides a reference implementation that apps copy and modify:

```python
# tew_framework.py - Reference implementation template

# Core Tew management
def create_tew(config): ...
def submit_slot(instance_id, signed_slot_tx): ...
def checkpoint_round(instance_id, round, signed_slots): ...
# ... other required functions

# Generic utilities
def validate_slot_signature(signed_tx): ...
def verify_round_transition(old_state, new_state): ...
def manage_escrow_balance(instance_id, denom): ...

# Web dashboard
def wsgi(environ, start_response): ...
def render_instance_dashboard(instance_id): ...

# Peer discovery helpers
def register_peer_endpoint(instance_id, endpoint): ...
def discover_committee_peers(instance_id): ...

# App integration points (to be overridden)
def app_l1_logic(instance_id, func_name, *args):
    """Override with app-specific L1 logic"""
    raise NotImplementedError

def app_l2_apply_slots(l2_state, slots):
    """Override with app-specific L2 logic"""
    raise NotImplementedError

# L2 query entry point (called via RunScript)
def process_l2_round(instance_id: str, current_state: dict, slots: dict) -> dict:
    """
    Called by L2 nodes via read-only RunScript queries.
    Returns the new state without modifying blockchain.
    """
    # Load L2 logic and execute deterministically
    new_state = current_state.copy()
    app_l2_apply_slots(new_state, slots)
    return {
        "new_state": new_state,
        "round": current_state.get("round", 0) + 1
    }
```

### 3.2 Framework Extension Pattern

Apps extend the framework by:

1. **Copy** the framework code into their script
2. **Override** the app integration points
3. **Add** app-specific functions and state
4. **Customize** the web dashboard views

Example app structure:
```python
# tew_thunder.py - Payment channel app

# === FRAMEWORK CODE (copied from tew_framework.py) ===
def create_tew(config): ...
def submit_slot(instance_id, signed_slot_tx): ...
# ... all framework functions ...

# === APP-SPECIFIC OVERRIDES ===
def app_l1_logic(instance_id, func_name, *args):
    """Thunder-specific L1 logic"""
    if func_name == "process_deposit":
        return process_deposit(instance_id, *args)
    elif func_name == "execute_withdrawal":
        return execute_withdrawal(instance_id, *args)
    # ...

def app_l2_apply_slots(l2_state, slots):
    """Thunder-specific L2 logic"""
    # Process transfers between members
    # ...

# === THUNDER-SPECIFIC FUNCTIONS ===
def process_deposit(instance_id):
    """Handle incoming funds"""
    # ...

def execute_withdrawal(instance_id, user_address):
    """Process withdrawal requests"""
    # ...
```

---

## 4 · TewApp Development Guide

### 4.1 Creating a TewApp

To create a new TewApp:

1. **Fork/Copy** the TewFramework reference implementation
2. **Implement** your L1 logic in `app_l1_logic()`
3. **Implement** your L2 logic in `app_l2_apply_slots()`
4. **Deploy** as a regular DysonProtocol script
5. **Create** TewInstances by calling your script's `create_tew()`

### 4.2 Instance Configuration

When creating a TewInstance:

```python
config = {
    "instance_id": "payment_channel_001",  # Unique within this app
    "committee": ["dys1...", "dys1..."],   # Committee members
    "timeout": 300,                        # Round timeout (seconds)
    "app_config": {                        # App-specific config
        "min_deposit": 1000000,
        "max_transfer": 100000000,
        # ...
    },
    "l1_state": {},                        # Initial L1 state
    "l2_state": {}                         # Initial L2 state
}

result = dysond.tx.script.exec(
    script_address="dys1myapp...",
    function_name="create_tew",
    args=[config]
)
```

### 4.3 L1/L2 Logic Integration

The script serves as the source of truth for both L1 and L2 logic:

**L1 Logic** (executed on-chain):
- Handles deposits, withdrawals, and other blockchain interactions
- Has access to `_msg()`, `_query()`, and other chain functions
- Updates L1 state stored in `tew/{instance_id}/l1/state`

**L2 Logic** (executed off-chain, verified on-chain):
- Processes slots to produce new L2 states
- Implements `_apply_slots()` for deterministic transitions
- Cannot access blockchain functions directly

---

## 5 · Example: TEW Thunder

### 5.1 Deployment

TEW Thunder is deployed as a single DysonProtocol script:

```bash
# Deploy the Thunder app (includes framework + app logic)
dysond tx script create-new-script \
  --code-path ./tew_thunder.py \
  --from alice

# Script address: dys1thunder...
```

### 5.2 Creating Payment Channels

Users create payment channel instances within the Thunder app:

```bash
# Create a new payment channel instance
dysond tx script exec \
  --script-address dys1thunder... \
  --function-name create_tew \
  --args '[{
    "instance_id": "channel_alice_bob_001",
    "committee": ["dys1alice...", "dys1bob..."],
    "timeout": 300,
    "app_config": {"min_deposit": 1000000}
  }]' \
  --from alice
```

### 5.3 Using the Channel

```bash
# Deposit funds
dysond tx script exec \
  --script-address dys1thunder... \
  --function-name call_l1_function \
  --args '["channel_alice_bob_001", "process_deposit"]' \
  --attached-message '{"@type":"/cosmos.bank.v1beta1.MsgSend",...}' \
  --from alice

# Submit transfer slot (off-chain)
dysond tx script exec \
  --script-address dys1thunder... \
  --function-name submit_slot \
  --args '["channel_alice_bob_001", "...signed_slot..."]' \
  --from alice

# When done, terminate the channel
dysond tx script exec \
  --script-address dys1thunder... \
  --function-name terminate_instance \
  --args '["channel_alice_bob_001"]' \
  --from alice
```

### 5.4 Ephemeral Nature in Practice

The payment channel `channel_alice_bob_001` exists only as long as needed:
- Created when Alice and Bob want to transact
- Used for multiple off-chain transfers
- Terminated when they're done, with final settlement on-chain
- No permanent state remains after termination

This pattern enables thousands of temporary channels without blockchain bloat.

---

## 6 · Security Considerations

### 6.1 App Isolation

- Each TewApp is completely isolated
- No shared state between different apps
- Apps cannot interfere with each other

### 6.2 Script Security

- Standard DysonProtocol script security applies
- Scripts can only modify their own storage
- Committee consensus required for L2 state changes

### 6.3 Framework Updates

- Apps must manually update framework code
- No automatic updates (by design)
- Apps can customize security policies

---

## 7 · Benefits of This Architecture

1. **Simplicity** – No complex protocol coordination
2. **Flexibility** – Apps have full control
3. **Isolation** – Apps cannot break each other
4. **Standard Tooling** – Uses existing DysonProtocol infrastructure
5. **Easy Deployment** – Just deploy a script
6. **Customization** – Modify framework as needed

---

## Appendix A · Migration from Earlier Versions

| Version | Architecture | Migration |
|---------|-------------|-----------|
| v0.2 | Monolithic protocol | Full rewrite |
| v0.3 | Separate L1/L2 storage | Update storage keys |
| v0.4 | Standalone apps | Deploy as new script |

---

## Appendix B · Glossary

- **TewProtocol**: Consensus specification (this document)
- **TewFramework**: Reference implementation template
- **TewApp**: Deployed application (e.g., TEW Thunder)
- **Instance**: A specific TewInstance created within an app
- **Committee**: Members authorized to produce L2 rounds
- **Round**: Atomic L2 state transition
- **Slot**: Committee member's input to a round

---

## 8 · Implementation Roadmap

### Phase 1: Core Protocol (TewProtocol)
- [x] Consensus rules specification
- [x] Storage layout definition
- [ ] Reference implementation

### Phase 2: Generic Framework (TewFramework)
- [ ] Web dashboard MVP
- [ ] Basic peer discovery
- [ ] State sync utilities

### Phase 3: Example Apps (TewApp)
- [ ] TEW Thunder (payment channels)
- [ ] TEW DEX (decentralized exchange)
- [ ] TEW DAO (governance)

---

## 9 · Proposed Enhancement: Decorator Pattern

### 9.1 Motivation

The current v0.4 design requires manual routing of L1 functions through `app_l1_logic`, which adds boilerplate and reduces clarity. Using Python decorators would provide a cleaner, more intuitive interface.

### 9.2 Decorator Design

```python
# Decorators mark execution context
def l1(func):
    """Mark function as L1 (on-chain) executable"""
    func._tew_layer = "L1"
    func._tew_callable = True
    return func

def l2(func):
    """Mark function as L2 (off-chain) executable"""
    func._tew_layer = "L2"
    return func

def l1_l2(func):
    """Mark function as callable from both L1 and L2"""
    func._tew_layer = "L1_L2"
    func._tew_callable = True
    return func
```

### 9.3 Usage Example

```python
# tew_thunder.py with decorators

@l1
def process_deposit(instance_id: str):
    """Automatically exposed as L1 function"""
    l1_state = load_l1_state(instance_id)
    # ... process deposit logic
    return {"processed": True}

@l1
def execute_withdrawal(instance_id: str, address: str):
    """Another L1 function"""
    # ... withdrawal logic
    return {"withdrawn": amount}

@l2
def transfer_to(state, author, recipient, amount):
    """L2 function available in slots"""
    # ... transfer logic

# Special decorator for L2 round processing
@l2_round
def process_l2_round(instance_id: str, current_state: dict, slots: dict):
    """Called by L2 nodes via RunScript queries"""
    # Framework handles calling app_l2_apply_slots
    return new_state

@l1_l2
def get_balance(instance_id: str, address: str):
    """Can be called from either layer"""
    # ... balance query logic
```

### 9.4 Framework Integration

The TEW Framework would automatically:
1. Scan for decorated functions
2. Register them in appropriate routing tables
3. Handle `call_l1_function` by looking up `@l1` decorated functions
4. Make `@l2` functions available in slot execution context

### 9.5 Benefits

- **Cleaner Code**: No manual routing functions needed
- **Self-Documenting**: Execution context visible at function definition
- **Validation**: Decorators can enforce signature requirements
- **Discoverability**: Easy to find all L1/L2 functions
- **Backwards Compatible**: Can coexist with manual routing

### 9.6 Migration Path

1. Framework adds decorator support alongside existing pattern
2. Apps can gradually adopt decorators
3. Eventually deprecate manual routing pattern

This enhancement would make TEW apps more Pythonic and reduce the learning curve for developers familiar with Python frameworks like Flask or Django.

---

*End of TewProtocol Specification v0.4*