# PBI 11: Integrate TewQueue and TewChain into unified queue_chain.py system

[Back to Backlog](../backlog.md#user-content-11) · [View Tasks](./tasks.md)

## Overview

This PBI merges the separate TewQueue and TewChain systems into a unified `queue_chain.py` module that enables automatic L1↔L2 queue communication within blockchain transactions.

## Business Context

The TewProtocol currently has two separate features:
- **TewQueue**: L1↔L2 message passing system with dataclass-based queue management
- **TewChain**: Blockchain processing system with transaction validation and state management

These need to be integrated to enable seamless communication between L1 (DysonProtocol blockchain) and L2 (off-chain memory) through the blockchain transaction processing flow.

## Requirements

### Functional Requirements

1. **Unified Module**: Merge TewQueue and TewChain into single `demo-tew/queue_chain.py` module
2. **Queue State Integration**: L2 queue state stored in TewChain block state with namespaced keys
3. **Automatic Processing**: Queue message processing happens automatically during `on_begin_block`
4. **Chain Logic Callbacks**: Chain_logic supports `on_queue_message` and `on_queue_response` callbacks
5. **Safe Access**: Wrapper functions in chain_logic enable validated queue access from user transaction code
6. **Error Handling**: Queue operation failures are logged but don't fail transactions

### Non-Functional Requirements

1. **Security**: Queue operations must not compromise transaction validation or block integrity
2. **Performance**: Queue processing should add minimal overhead to block processing
3. **Compatibility**: Must maintain dyslang compatibility requirements from TewQueue
4. **Observability**: Queue processing results should be logged for debugging

## Success Criteria

1. TewQueue and TewChain successfully merged into single module
2. L2 queue state persists correctly in TewChain block state
3. Queue processing occurs automatically during block processing
4. Chain_logic can handle queue messages through callbacks
5. User transaction code can call queue functions like `send_greeting_to_l1("good morning")`
6. Integration tests demonstrate L1↔L2 communication within blockchain transactions

## Dependencies

- Existing `demo-tew/queue.py` (preserved as reference)
- Existing `demo-tew/chain.py` (preserved as reference)
- Existing test infrastructure (`tests/tew/test_queue.py`, `tests/tew/test_chain.py`)

## Assumptions

- The TewQueue is limited to L1 and L2 internal message queue
- DysonChain is trusted - if block is valid, queue state is trusted
- L1 stores directly on DysonProtocol blockchain
- L2 stores in memory, persisted between `dysond query script run` calls

## Out of Scope

- Modifying existing test files (`test_queue.py`, `test_chain.py`)
- Public API changes to TewQueue or TewChain interfaces
- Performance optimizations beyond basic integration
- Cross-chain communication beyond L1↔L2 

---

## Addendum: Architecture Simplification (2025-01-02)

The implementation has evolved from the original design. The chain_logic layer has been removed, simplifying the architecture:

### Key Changes:
1. **No chain_logic separation**: All L1 and L2 logic is now directly implemented within the DysonProtocol script (`queue_chain.py`)
2. **No core_logic.py source code**: There is no separate chain_logic code to be stored in the TewBlock state
3. **Direct implementation**: Queue callbacks (`on_queue_message`, `on_queue_response`) are now methods of the L1 and L2 classes within the script
4. **Simplified sandboxing**: TEW transactions run in a minimal sandbox with access to safe wrapper functions only

### Updated Architecture:
- **Before**: User Code → chain_logic → queue_chain
- **After**: User Code → queue_chain (with built-in L1/L2 logic)

This simplification removes a layer of abstraction while maintaining the security model through wrapper functions exposed to user transactions. 