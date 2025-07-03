## Dyson L2 "Rounds & Slots" – **Full Specification v0.2**

---
## § Architecture & Core Concepts

This document specifies the **TewProtocol**, a system for managing Layer 2 (L2) state machines called **Tews** on the Dyson Protocol blockchain.

### Component Overview

| Component | Layer | Description |
|---|---|---|
| **Dyson Protocol** | L1 | A Cosmos-SDK based blockchain that provides the foundation for on-chain logic, state storage, and consensus. It features a Python smart contracting engine. |
| **TewProtocol Script** | L1 | A specific Python script deployed on the Dyson Protocol. Its primary role is to serve as a factory and registry for all Tew instances. It defines the standard interface for creating, managing, and communicating between Tews. |
| **Tew (A Tew Instance)** | L1/L2 | A single, deployed L2 state machine. Each Tew is a self-contained application with its own participants, business rules (`core_logic`), and a state that is composed of both on-chain (L1) and off-chain (L2) components. |
| **TewPacketQueue** | L1/L2 | An abstraction layer responsible for communication between the on-chain and off-chain halves of a single Tew. The TewProtocol script provides the mechanisms for this queue. |

### The TewPacketQueue: Intra-Tew Communication

The TewPacketQueue is the core mechanism that allows a Tew's `core_logic` (running off-chain) to coordinate with its on-chain state and participant actions. It is responsible for managing a reliable, ordered stream of events, which we call **packets**. Its fundamental purpose is to provide a generic and reliable **General Messaging** channel with strict FIFO (First-In, First-Out) ordering guarantees.

This queue is a **private, internal channel**. It is not directly accessible from outside the Tew. External communication is handled by custom, public `@l1` functions defined in the Tew's `core_logic_l1`. These public functions are responsible for validation and then enqueuing internal packets for the `core_logic_l2` to process.

For example, a `deposit` function in `core_logic_l1` would validate the sender and amount, then place a `{ "type": "credit", "amount": 100 }` packet into the L1-to-L2 queue.

This primitive is then used by the application-specific `core_logic` to implement features. For example:

*   **Membership Changes:** The `core_logic` can define specific packet types that, when received by the on-chain component, are interpreted to add or remove participants from the Tew's committee.
*   **Asset Management:** The `core_logic` defines packets to signal the intent to deposit, transfer, or withdraw funds. The on-chain logic reacts to these specific packets to manage the L1 escrow account.

L2-to-L1 communication is achieved by the `core_logic_l2` writing a list of packets to a well-defined `packets_to_l1` field within its state object. When this state is committed on-chain, the TewProtocol invokes the Tew's `core_logic_l1` to process these packets, translating them into on-chain actions.

### The TewPacketQueue Protocol: Guarantees and Handlers

To achieve reliable communication, the TewProtocol enforces a strict set of rules and exposes an event-driven interface to the `core_logic`.

#### Delivery Guarantees

The protocol's guarantees are based on one fundamental rule: **An L2 RoundCommit is only valid if it references a recent and monotonically increasing L1 block.** Specifically, the `l1_block_height` in a RoundCommit for round `N` must be greater than the height referenced by round `N-1`, and no more than 2 blocks older than the current L1 head.

This rule creates the following verifiable guarantees:

1.  **L1-to-L2 Delivery:** When the L1 posts a packet to a Tew's queue, it can be certain that the L2 `core_logic` has "received" and processed that packet after, at most, 2 L1 blocks have passed. If the L2 fails to do so, it will be unable to produce a valid RoundCommit, effectively halting its progress. This provides a strong, time-bound guarantee of reception.
2.  **L2-to-L1 Delivery:** When the L2 includes a packet or state update in a RoundCommit, it can be certain that the L1 has "received" it as soon as that RoundCommit transaction is successfully included in an L1 block.

#### L2-to-L1 Communication: The Ack/Nack Pattern (TCP-style)

While the TewPacketQueue primarily manages L1-to-L2 packets, a reliable response mechanism is needed for actions initiated by the L2. The protocol supports two modes of L2-to-L1 communication on a per-packet basis:

*   **UDP-style (Fire and Forget):** The L2 can send a packet without requiring a response. This is useful for simple, one-way notifications where the L2 does not need to confirm the outcome of the L1 action.
*   **TCP-style (Request and Acknowledge):** The L2 can send a packet and explicitly request a receipt acknowledgement (`ack`/`nack`). The TewProtocol enforces a two-phase commit pattern for these packets.

When an L2 state change requires a corresponding L1 action (e.g., a withdrawal from an escrow) and requests an `ack`, the `TewProtocol` script on L1 will attempt the action after the related L2 RoundCommit has been processed. The protocol then guarantees it will post a new packet back to the L1-to-L2 queue indicating the outcome:

*   **On Success (`ack`):** The L1 script posts an acknowledgement packet, which triggers the `on_ack` handler in the L2 `core_logic`. This confirms the action is complete, allowing the L2 to finalize its state (e.g., moving a withdrawal from "pending" to "completed").
*   **On Failure (`nack`):** If the L1 action fails for a predictable reason (e.g., insufficient funds in the escrow, invalid parameters), the L1 script posts a *negative acknowledgement* (`nack`) packet containing a reason for the failure. This triggers the `on_nack` handler, allowing the L2 to gracefully handle the failure without getting stuck in a pending state.

##### Queue flow per round (clarification)

* **Inbound queue (L1 → L2)** – Stored under the key prefix `l2/{tew_id}/inbound/…`. The contents of this queue are *not* embedded in the `RoundCommit`; instead, at the **very start** of every round the TewProtocol dequeues the entire list, in FIFO order, and delivers each item to the off-chain engine:
  1. First, it handles any `ack` / `nack` objects (calling `on_ack` / `on_nack`).
  2. Then it handles the remaining application-level packets (calling `on_packet`).
  After delivery the corresponding storage entries are deleted, guaranteeing **exact-once** semantics. Because this happens before `_apply_slots`, the L2 engine always works against the most recent L1 block and always "sees" every packet that was available when the round began.

* **Outbound queue (L2 → L1)** – The off-chain engine appends objects to `state.data.packets_to_l1` during `_apply_slots`.

  During `progress_round` the protocol iterates over that list *after* the new snapshot has been persisted, invoking `core_logic_l1.on_l1_packet` for each item.  If `pkt.options.require_ack == true` the handler (or the TewProtocol helper it calls) **immediately enqueues** an `ack` or `nack` object to the inbound queue (`l2/{tew_id}/inbound/…`).  As a result, the acknowledgement becomes visible to the L2 engine at the very next round without needing an extra transaction.

* After all packets have been processed the protocol clears `packets_to_l1` inside the stored snapshot, keeping the snapshot immutable while ensuring idempotency.

#### Event Handlers & Timeouts

The TewProtocol manages the queue and timeouts, but delegates the application-specific logic to the Tew's `core_logic` via a set of required event handlers. The execution of these handlers within a round follows a strict, deterministic order.

The Tew's logic is split into two distinct components: an L1 `core_logic` and an L2 `core_logic`. Both operate on the same state, but have different roles and execution environments.

*   **`core_logic_l2` (Off-Chain Engine):** This is the deterministic state transition function (`_apply_slots`). It runs in an off-chain, sandboxed environment to compute `State_N+1` from `State_N` and a set of inputs. It is responsible for the Tew's primary business logic.
*   **`core_logic_l1` (On-Chain Handler):** This is a smaller set of handlers that execute on the L1 chain. Its purpose is to react to on-chain events (like timeouts) and to translate messages from the L2 state into L1 transactions (like asset transfers). It reads from the committed state but does not modify it.

The `TewProtocol` executes the `core_logic` in the following sequence:
1.  **Process Acknowledgements:** It first processes all `ack`/`nack` packets generated by the L1 from the *previous* round's actions, calling `on_ack` or `on_nack` for each. These packets are processed in the strict FIFO order they were enqueued. This finalizes prior-round state.
2.  **Process New Packets:** It then processes all new packets from the L1-to-L2 queue, calling `on_packet` for each, again in strict FIFO order.
3.  **Process Slots:** Finally, it calls the internal `_apply_slots` function with all the submitted slots for the current round.

The `core_logic_l2` for a Tew **must** implement the following functions:

*   `on_packet(state, packet)`: This handler is called by the L2 off-chain engine for each packet from the L1 queue, in order. It takes the current L2 state and the packet as input and is responsible for returning the new, updated L2 state.
*   `on_ack(state, original_packet)`: This handler is called when the L2 receives confirmation that a packet *it sent* in a previous RoundCommit has been successfully acknowledged by the L1. This is crucial for multi-step transfers.
*   `on_nack(state, original_packet, reason)`: This handler is called when the L1 explicitly signals that an L2-initiated action has failed. This allows the L2 to handle the failure cleanly, preventing stuck states.

The `core_logic_l1` for a Tew **must** implement the following handlers:

*   `on_timeout(state, timed_out_packet)`: This handler is called on the **L1 on-chain `core_logic`** by the TewFramework when a packet sent to the L2 has not been acknowledged within the timeout period (e.g., 2 blocks). This allows the Tew to perform compensatory actions, such as refunding an escrowed deposit to the original sender.
*   `on_l1_packet(state, packet)`: This handler is called on L1 for each packet in the `packets_to_l1` queue of a newly committed L2 state. It is responsible for translating the L2's intent into an L1 transaction.

#### Packet timeout semantics (destination-layer clock)
Timeout heights are interpreted on the **destination chain**:
• **L1→L2 packets** time-out relative to the L2 height. A RoundCommit that references an L1 height > `sent_at + timeout` must include proof that the packet is expired, allowing the L1 to run `on_timeout` later.
• **L2→L1 packets** time-out relative to the L1 height. When the L1 itself reaches `sent_at + timeout`, the next RoundCommit must include the expired packet metadata and the TewProtocol automatically invokes the L1‐side `on_timeout` handler.
This matches IBC semantics and lets each side reason about expiry with its own local block clock.

### Design Considerations: UDP vs. TCP for the TewPacketQueue

The design of the TewPacketQueue can be viewed through the lens of network protocols:

*   **A UDP-like (Datagram) Model:** This would involve simple, connectionless packets. The L2 would fire off transactions to the L1 and "hope" they are processed. This is supported by setting `require_ack: false` on an L2-to-L1 packet.
    *   **Pros:** Simpler, less on-chain state to manage for that specific packet.
    *   **Cons:** Unreliable. No built-in guarantees of ordering or delivery. The `core_logic` would need to implement its own complex retry and sequencing logic if reliability is needed.
*   **A TCP-like (Stream) Model:** This involves a connection-oriented, reliable, and ordered queue. This is supported by setting `require_ack: true` on an L2-to-L1 packet.
    *   **Pros:** Highly reliable. Guarantees that packets (deposits, withdrawals, etc.) are processed exactly once and in the correct order, with a confirmed outcome. The complexity is handled at the protocol level, simplifying the `core_logic` for application developers.
    *   **Cons:** Requires more on-chain state to track sequence numbers, channel state, and timeouts.
    *   **Implementation:** The RoundCommit mechanism, with its reliance on `prev_round_hash` and `l1_block_hash`, serves as the sequencing and acknowledgement mechanism for this reliable stream.

---

### 0 · Glossary

| Term            | Meaning                                                                                              |
| --------------- | ---------------------------------------------------------------------------------------------------- |
| **L2 instance** | Independent state-machine created by `genesis()` and identified by a **globally-unique `tew_id`**. |
| **RoundCommit** | A complete and self-contained description of the L2's state at the end of a round. Immutable once stored and identified by its round number. |
| **ForcedRound** | An on-chain placeholder RoundCommit emitted automatically when the timeout for round *N* elapses before the committee commits. It advances liveness without executing any business logic. |
| **Round**       | A deterministic state transition that computes `RoundCommit_N` from `RoundCommit_(N-1)`. Its inputs are the previous commit, a set of slots, the `core_logic` specified by the previous commit, and the state of the L1/L2 packet queues at the time of execution. |
| **Slot**        | Code contribution from one participant for a round.                                                  |
| **Committee**   | An application-level concept, managed by the `core_logic`. It defines which participants are expected to contribute slots for a round. The `TewProtocol` currently requires 100% participation from the committee members listed in the previous state to progress a round. |

---

### 1 · Data formats

*(canonical JSON → `json.dumps(obj, separators=(',', ':'), sort_keys=True)`; hashes are `sha256` of that)*

#### 1.1 `slot_data` — **payload inside ADR-036 `MsgArbitraryData`**

```jsonc
{
  "tew_id"          : "l2_000123",
  "l1_block_hash"   : "B705943A…", // hash of the L1 block this is built on
  "l1_block_height" : 12345,    // height of the L1 block this is built on
  "prev_round_hash"   : "0x…",   // sha256 of round_commit[r-1]
  "prev_round_height" : 42,
  "participant"       : "dys1…", // signer of the ADR-036 tx
  "slot_logic"        : "python code …"  // executed by _apply_slots()
}
```

*Placed in the `data` field of a **single** `/dysonprotocol.script.v1.MsgArbitraryData` message and signed offline per ADR-036 (`chain_id=""`, `account_number=0`, `sequence=0`). The script queries `VerifyTx` to authenticate the signature.*

#### 1.2 `round_commit`

```jsonc
{
  "meta": {
    "tew_id"          : "l2_000123",
    "round"           : 42,
    "core_logic_l1_hash" : "0x...", // sha256 of the L1 handler code
    "core_logic_l2_hash" : "0x...", // sha256 of the L2 engine code that executed this round
    "timeout"         : 30,
    "started_at"      : 1_725_123_456
  },
  "members": ["dys1..."], // List of active members, managed by core_logic
  "data"       : {
    "packets_to_l1": [
      { "payload": { "...": "..." }, "options": { "require_ack": true } }
    ],
    "..." : "Application-specific state"
  },
  "core_logic_l1" : "python L1 handlers: on_timeout(), on_l1_packet()",
  "core_logic_l2" : "python L2 engine: on_packet(), _apply_slots()"
}
```

---

### 2 · On-chain storage (per `tew_id`)

| key / prefix                        | description             |
| ----------------------------------- | ----------------------- |
| `l2/{id}/latest_round`              | `int` – chain head      |
| `l2/{id}/state/{round:010d}`        | canonical **round_commit**  |
| `l2/{id}/slots/{round:010d}/{addr}` | raw `slot_logic` string |
| `evidence/eqv/{id}/{round:010d}/{addr}/{attempt:03d}` | equivocation evidence |

A global counter `l2/next_id` generates new IDs (`l2_000123`).

---

### 3 · Public API & Execution Layer

#### 3.1 Layer decorators *(no-op, used for documentation + tooling)*

```python
def l1(fn):     fn._layer = "L1"     ; return fn  # parent-chain tx only

def l2(fn):     fn._layer = "L2"     ; return fn  # off-chain / simulate only

def l1_l2(fn):  fn._layer = "L1↔L2"  ; return fn  # on-chain tx that reuses deterministic path
```

#### 3.2 API summary

| function signature                           | decorator | purpose                                                                                                            |
| -------------------------------------------- | --------- | ------------------------------------------------------------------------------------------------------------------ |
| `genesis(initial_genesis)`                   | `@l1`     | Allocate `tew_id`, store round-0 RoundCommit, copy `core_logic`. |
| `submit_slots(tew_id, signed_slot_txs[])`  | `@l1`     | Persist future-round slots (ADR-036 signed). Duplicate `(round, addr)` with different code ⇒ rejection. |
| `next_round(snapshot, slots)`                | `@l2`     | Deterministic transition; simulate-only (executor == script address).                                              |
| `progress_round(tew_id)`                   | `@l1`     | Execute RoundCommit for the next round (verify slots → apply deterministic engine → persist RoundCommit). **Atomic** |
| `checkpoint_round(tew_id, round_height, l1_block_height, l1_block_hash, signed_slot_txs)` | `@l1`     | Fast-forward head if committee signatures are valid and reference the correct L1 block. |

*Layer legend:* **L1** = parent Dyson chain transaction · **L2** = sandbox/off-chain.

---

### 4 · Committee-change semantics

The management of the participant committee is the responsibility of the application-specific `core_logic`. The TewProtocol itself remains un-opinionated about how members are added or removed.

The typical mechanism for managing the committee is by treating membership changes like any other application-level state change, using the standard packet queue:

1.  **L1 Interface:** The developer exposes public `@l1` functions in `core_logic_l1` (e.g., `request_join()`, `propose_expulsion(member)`).
2.  **Packet Creation:** These L1 functions validate the request and then enqueue a corresponding L1-to-L2 packet with a specific payload (e.g., `{ "type": "join_request", "address": "..." }`).
3.  **L2 Logic Execution:** The `core_logic_l2` receives this packet via its `on_packet` handler and updates its internal state according to its own rules (e.g., adding a member to a "pending" list, initiating a vote).
4.  **State Transition:** During `_apply_slots`, the L2 logic reads its internal state and computes the final `members` list for the next RoundCommit. This change is then committed atomically with the rest of the round's state transition.

A RoundCommit that results in a change to the committee must be **contiguous** (`new_round == head+1`).

---

### 5 · Equivocation Rule

The protocol must be able to defend against a malicious participant who attempts to fork the L2 state by signing two different `slot_logic` blobs for the same `(tew_id, round, addr)`.

The `submit_slots` function is responsible for detecting this behavior:
1.  When a participant submits a slot for a given round, the function checks if a slot from that participant for that round already exists.
2.  If it does, the function compares the content of the new slot with the existing one.
3.  If the contents are different, this is considered an act of equivocation. The submission is rejected.
4.  Evidence is stored using an incremental approach to capture all equivocation attempts:
    - Each attempt is stored at: `evidence/eqv/{tew_id}/{round}/{addr}/{attempt_number}`
    - The first (accepted) slot is retroactively stored as evidence when equivocation is detected
    - All subsequent conflicting slots are stored with rejection details
5.  This comprehensive on-chain evidence trail can be used by slashing modules or governance mechanisms to penalize the malicious actor.

#### Evidence Format

Each evidence entry contains:
```jsonc
{
    "attempt": 1,  // Incrementing attempt number
    "slot_hash": "sha256_of_slot",
    "slot_logic": "...",  // Full slot code
    "submitted_at": 1234567890,  // Unix timestamp
    "tx_hash": "cosmos_tx_hash",  // Transaction hash for verification
    "rejected": false  // true for all attempts after the first
    "reason": "equivocation"  // Only present if rejected
}
```

---

### 6 · Genesis input (`initial_genesis`)

```jsonc
{
  "meta": {
    "round"   : 0,
    "timeout" : 30,
    "started_at": 0
  },
  "members" : ["dys1…alice", "dys1…bob"],
  "data"         : { … initial state … },
  "core_logic_l1" : "python code defining on_timeout(), etc.",
  "core_logic_l2" : "python code defining inc(), decr(), get(), _apply_slots()"
}
```

---

## ✏️ Reference Python Script

*Keys are automatically namespaced as `l2/{tew_id}/…`.  If you deploy one L2 per script address, you can inline `tew_id`.*

```python
import json, time
from typing import Dict, List
from dys import _query, _msg, dys_eval, get_script_address, get_executor_address as _executor

# ───────── layer decorators (no-op) ─────────

def l1(fn): return fn

def l2(fn): return fn

def l1_l2(fn): return fn

# ───────── storage helpers ─────────

def _store(idx, data):
    _msg({"@type": "/dysonprotocol.storage.v1.MsgStorageSet", "owner": get_script_address(), "index": idx, "data": data})

def _delete(idx):
    _msg({"@type": "/dysonprotocol.storage.v1.MsgStorageDelete", "owner": get_script_address(), "indexes": [idx]})

def _load_json(idx, default=None):
    try:
        res = _query({"@type": "/dysonprotocol.storage.v1.QueryStorageGetRequest", "owner": get_script_address(), "index": idx})
        return json.loads(res["entry"]["data"])
    except Exception:
        return default

# ───────── global utils ─────────

def _alloc_id() -> str:
    nxt = int(_load_json("l2/next_id", 0))
    _store("l2/next_id", str(nxt + 1))
    return f"l2_{nxt:06d}"

def _set_add(idx: str, addr: str):
    s = set(_load_json(idx, []))
    s.add(addr)
    _store(idx, json.dumps(sorted(s)))

# ───────── deterministic engine ─────────

def _next_round_state(round_state: dict, slots: Dict[str, str]) -> dict:
    # Execution of core_logic is sandboxed. It has access only to its own state
    # and a limited set of deterministic helpers. It CANNOT call back into the
    # TewProtocol's public API (@l1 or @l1_l2 functions), preventing re-entrancy.
    core_code_l2 = round_state.get("core_logic_l2")
    if not core_code_l2:
        raise ValueError("core_logic_l2 missing from snapshot")

    # The core_logic receives a mutable view of the state, excluding 'meta'.
    # It can modify its own code, the participant list, and application data.
    mutable_state = {
        "members": round_state.get("members", []),
        "data": round_state.get("data", {}),
        "core_logic_l1": round_state.get("core_logic_l1", ""),
        "core_logic_l2": round_state.get("core_logic_l2", ""),
    }

    # The core_logic is now responsible for validating slots and committee membership.
    scope = {}
    dys_eval(core_code_l2, scope=scope)
    apply_fn = scope.get("_apply_slots")
    if apply_fn is None:
        raise ValueError("_apply_slots missing in core_logic_l2")

    # The core_logic can modify its own code for the next round by updating
    # the fields within mutable_state.
    apply_fn(mutable_state, slots)

    # After execution, merge the modified state back into the new snapshot,
    # leaving the 'meta' field untouched.
    round_state.update(mutable_state)

    import hashlib
    # The new snapshot's hash points to the code that was just executed.
    round_state["meta"]["core_logic_l2_hash"] = "0x" + hashlib.sha256(round_state['core_logic_l2'].encode()).hexdigest()
    round_state["meta"]["core_logic_l1_hash"] = "0x" + hashlib.sha256(round_state['core_logic_l1'].encode()).hexdigest()
    
    round_state["meta"]["started_at"] = int(time.time())
    round_state["meta"]["round"] += 1
    return round_state

# ───────── public API ─────────

@l1
def genesis(initial_genesis: dict):
    eid = _alloc_id()
    # The core_logic is stored directly within the snapshot state.
    core_logic_l1 = initial_genesis.get("core_logic_l1")
    core_logic_l2 = initial_genesis.get("core_logic_l2")
    if not core_logic_l1 or not core_logic_l2:
        raise ValueError("genesis snapshot must contain core_logic_l1 and core_logic_l2")

    import hashlib
    l1_hash = "0x" + hashlib.sha256(core_logic_l1.encode()).hexdigest()
    l2_hash = "0x" + hashlib.sha256(core_logic_l2.encode()).hexdigest()
    initial_genesis["meta"].update({
        "started_at": int(time.time()), 
        "tew_id": eid, 
        "core_logic_l1_hash": l1_hash,
        "core_logic_l2_hash": l2_hash
    })

    _store(f"l2/{eid}/state/0000000000", json.dumps(initial_genesis, separators=(',', ':')))
    _store(f"l2/{eid}/latest_round", "0")
    return {"tew_id": eid}

@l1
def submit_slots(tew_id: str, signed_slot_txs: List[str]):
    """Each element is the *JSON string* of a fully-signed MsgArbitraryData tx."""
    if not signed_slot_txs:
        raise ValueError("empty tx list")

    from dys import query  # ABCI query helper
    import hashlib
    head = int(_load_json(f"l2/{tew_id}/latest_round", 0))
    stored = 0
    for tx_json in signed_slot_txs:
        # 1. keeper verifies signature
        query({"@type": "/dysonprotocol.script.v1.QueryVerifyTxRequest", "tx_json": tx_json})

        # 2. extract slot_data from first msg
        tx_obj = json.loads(tx_json)
        slot_data = json.loads(tx_obj["body"]["messages"][0]["data"])
        rnd   = slot_data["prev_round_height"] + 1
        addr  = slot_data["participant"]
        code  = slot_data["slot_logic"]

        if rnd <= head:
            raise ValueError("slot round must be in the future")

        key = f"l2/{tew_id}/slots/{rnd:010d}/{addr}"
        prev = _load_json(key, None)
        
        if prev is not None and prev != code:
            # Equivocation detected! Store evidence incrementally
            evidence_base = f"evidence/eqv/{tew_id}/{rnd:010d}/{addr}"
            
            # Find next attempt number
            attempt_num = 1
            while _load_json(f"{evidence_base}/{attempt_num:03d}", None) is not None:
                attempt_num += 1
            
            # Store evidence for first slot if this is first equivocation
            if attempt_num == 2:
                first_evidence = {
                    "attempt": 1,
                    "slot_hash": hashlib.sha256(prev.encode()).hexdigest(),
                    "slot_logic": prev,
                    "submitted_at": "unknown",  # Would need slot metadata tracking
                    "tx_hash": "unknown",
                    "rejected": False
                }
                _store(f"{evidence_base}/001", json.dumps(first_evidence))
            
            # Store evidence for this equivocation attempt
            new_evidence = {
                "attempt": attempt_num,
                "slot_hash": hashlib.sha256(code.encode()).hexdigest(),
                "slot_logic": code,
                "submitted_at": int(time.time()),
                "tx_hash": tx_obj.get("txhash", "unknown"),
                "rejected": True,
                "reason": "equivocation"
            }
            _store(f"{evidence_base}/{attempt_num:03d}", json.dumps(new_evidence))
            
            raise ValueError(f"Equivocation detected for {addr} at round {rnd}")
        elif prev is not None:
            raise ValueError(f"slot already submitted for {addr} at round {rnd}")
            
        _store(key, code)
        stored += 1
    return {"stored": stored}

# ─────── pure off-chain transition (simulate only) ─────────────
@l2
def next_round(round_state: dict, slots: Dict[str, str]):
    if _executor() != get_script_address():
        raise PermissionError("next_round allowed only under --simulate")
    return _next_round_state(round_state, slots)

# ─────── on-chain progress one round ───────────────────────────
@l1
def progress_round(tew_id: str):
    # Note: This entire function executes atomically. If any step fails,
    # including the execution of the sandboxed core_logic, the entire
    # transaction is reverted, leaving the L1 state unchanged.
    head   = int(_load_json(f"l2/{tew_id}/latest_round", 0))
    snap   = _load_json(f"l2/{tew_id}/state/{head:010d}", None)
    if not snap:
        raise ValueError("snapshot missing")
    if time.time() < snap["meta"]["started_at"] + snap["meta"]["timeout"]:
        raise ValueError("timeout not reached")

    # — gather all available slots for the next round —
    # The protocol requires 100% participation from the committee defined
    # in the previous snapshot.
    slots = {}
    # (Example logic: a query function would scan `l2/{tew_id}/slots/{head+1:010d}/`)
    expected_members = set(snap.get("members", []))
    submitted_members = set(slots.keys())

    if expected_members != submitted_members:
        raise ValueError(f"Participation mismatch. Expected: {sorted(expected_members)}, Got: {sorted(submitted_members)}")

    new_snap = _next_round_state(snap, slots)
    new_round = head + 1
    _store(f"l2/{tew_id}/state/{new_round:010d}", json.dumps(new_snap, separators=(',', ':')))
    _store(f"l2/{tew_id}/latest_round", str(new_round))

    # --- Process L2-to-L1 messages using L1 logic ---
    core_logic_l1 = new_snap.get("core_logic_l1")
    if core_logic_l1:
        # Pass a read-only view of the state to the L1 handlers
        state_view = {
            "members": new_snap.get("members"),
            "data": new_snap.get("data"),
        }
        scope = {}
        dys_eval(core_logic_l1, scope=scope)
        on_l1_packet_fn = scope.get("on_l1_packet")
        if on_l1_packet_fn:
            for pkt in new_snap.get("data", {}).get("packets_to_l1", []):
                # Here the L1 would check pkt['options']['require_ack'] and enqueue
                # an ack/nack packet back to the L1->L2 queue if true.
                on_l1_packet_fn(state_view, pkt)
        # Clear the packet queue after processing
        if "packets_to_l1" in new_snap.get("data", {}):
            new_snap["data"]["packets_to_l1"] = []
            _store(f"l2/{tew_id}/state/{new_round:010d}", json.dumps(new_snap, separators=(',', ':')))

    return {"round": new_round}

# ─────── fast-forward checkpoint --------------------------------
@l1
def checkpoint_round(tew_id: str, round_height: int, l1_block_height: int, l1_block_hash: str, signed_slot_txs: List[str]):
    # Note: the python implementation in this spec is simplified from the real `script.py`
    # for brevity. The real script is the source of truth.
    new_r = round_height
    cur_r = int(_load_json(f"l2/{tew_id}/latest_round", 0))
    if new_r <= cur_r:
        raise ValueError("checkpoint must advance head")

    # ... validation logic ...
    # for each tx in signed_slot_txs:
    #   slot_data = extract(tx)
    #   assert slot_data.l1_block_hash == l1_block_hash
    #   ...
    
    # ... if all checks pass ...
    # new_snap = _next_snapshot(...)
    # _store(f"l2/{tew_id}/state/{new_r:010d}", json.dumps(new_snap, separators=(',', ':')))
    # _store(f"l2/{tew_id}/latest_round", str(new_r))
    return {"checkpointed_to": new_r}
