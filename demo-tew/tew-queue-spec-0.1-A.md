# TEW Queue – Generic Message-Passing Extension  
**Version:** 0.1-A (targets TEW Protocol v0.5)  
**Status:** Draft – implementation reference for Dyslang / Python scripts running in the Dyson VM  

---

## 0 · Scope & Purpose
TEW Queue introduces a *simple, durable, bidirectional* message channel between Layer-1 (the on-chain TEW script) and Layer-2 (the off-chain committee).  

Goals:
1. Allow L1 logic to *request* actions from the committee (e.g. _"new deposit arrived"_).  
2. Allow L2 logic to *signal* outcomes or commands back to L1 (e.g. _"withdrawal approved"_).  
3. Persist messages for the full lifetime of a TEW instance and commit them inside every checkpoint so state agreement is provable off-chain and on-chain.  
4. Keep the design minimal—**no protobuf, no IBC, no extra Cosmos modules**—just Python & Dyslang helpers.

---

## 1 · Key Design Principles
1. **Two Logical Queues** – `l1_to_l2` and `l2_to_l1`, fully independent.  
2. **Origin-Prefixed IDs** – `l1:{instance}:{nonce}` and `l2:{instance}:{nonce}` prevent collisions and make debugging easy.  
3. **Per-Message KV Storage** – every message is its own KV entry; lists of IDs are stored for fast iteration.  
4. **Lightweight Consensus** – each signed-tx includes deterministic hashes of both queues so members sign the _same_ view.  
5. **Timeout Auto-Nack** – messages carry a `timeout` block-height; expiry automatically moves status to `timeout`.

---

## 2 · Data Structures

### 2.1 Message Object
```json
{
  "id": "l1:channel_001:42",        // unique, origin-prefixed
  "type": "deposit_notice",         // free-form string, app-defined
  "payload": { ... },                // arbitrary JSON, app-defined
  "timeout": 123456,                 // L1 block-height by which it must be acked
  "status": "pending",             // pending | ack | nack | timeout
  "result": null,                    // populated on ack/nack
  "created_at": 120000               // L1 block-height when enqueued
}
```

### 2.2 Storage Layout (L1 KV)
```
tew/{instance_id}/queue/l1_to_l2/{msg_id}   → Message JSON
tew/{instance_id}/queue/l2_to_l1/{msg_id}   → Message JSON
```

### 2.3 L2 State Additions
```json
{
  "meta": {
    ...,
    "pending_l2_messages": ["l2:channel_001:7", "l2:channel_001:8"],
    "last_processed_l1_msg": "l1:channel_001:41"
  }
}
```
Only **IDs** live in state; full message bodies stay in L1 KV.

---

## 3 · Signed-Tx Extension (v0.5 Compatible)
Every committee member includes queue fingerprints when they sign a tx:
```json
{
  ...,
  "queue_hashes": {
    "l1_to_l2": "sha256:…",   // hash of concatenated msg IDs still *pending* at L2
    "l2_to_l1": "sha256:…"    // hash of concatenated msg IDs still *pending* at L1
  }
}
```
*Serialization rule:* compact JSON, keys sorted, IDs joined with `,` before hashing.
If any hash mismatch occurs during block computation the tx is **invalid**.

---

## 4 · Helper API (Python / Dyslang)
The following helpers live in **`tew_framework.py`**.

### 4.1 L1-Side
```python
def queue_l1_message(instance_id: str, msg_type: str, payload: dict, timeout: int) -> str:
    """Enqueue a new message for L2 and return msg_id."""

def get_pending_l1_messages(instance_id: str, after_id: str = None) -> list[str]:
    """Query-only. Return pending message IDs newer than `after_id`."""

def ack_l2_message(instance_id: str, msg_id: str, result: dict = None):
    """Mark message from L2 as ack with optional result payload."""

def nack_l2_message(instance_id: str, msg_id: str, reason: str):
    """Mark message from L2 as rejected."""
```

### 4.2 L2-Side (Callable via `dys_eval`)
```python
def l2_enqueue_message(state: dict, msg_type: str, payload: dict, timeout_blocks: int):
    """Add message to `pending_l2_messages` list and KV (status=pending)."""

def l2_process_l1_messages(state: dict, l1_messages: list[dict]):
    """Invoke `_l2_on_message_received` for each new L1 message, update cursor."""
```
Both sides must provide callback stubs that apps can override:
```python
def _l1_on_message_received(instance_id: str, message: dict): ...
def _l2_on_message_received(state: dict, message: dict): ...
```

---

## 5 · Message Lifecycle
1. **Enqueue** – origin side stores KV entry with `status=pending`.  
2. **Checkpoint / Block Compute**  
   •  L2 pulls new L1 messages (`after_id`) during `compute_next_block`.  
   •  L2 may enqueue new messages for L1.  
3. **Commit** – queue hashes included in signed-tx; checkpoint locks them in.  
4. **Ack / Nack** – destination side updates KV entry status & `result`.  
5. **Timeout** – during each block compute, any message whose `timeout < current_height` and still `pending` is auto-nacked (`reason="timeout"`).

---

## 6 · Thunder Integration Example
### 6.1 Deposit Notice (L1 → L2)
```python
# inside process_deposit()
queue_l1_message(instance_id, "deposit_notice", {
    "user": from_address,
    "amount": deposit_amount
}, timeout=get_block_height()+100)
```
`_l2_on_message_received` updates `data.balances` and sets `last_processed_l1_msg`.

### 6.2 Withdrawal Flow (L2 → L1)
```python
# inside request_withdrawal()
l2_enqueue_message(state, "withdrawal_request", {
    "user": author,
    "amount": amount
}, timeout_blocks=50)
```
L1 handles it in `_l1_on_message_received`, executes `execute_withdrawal_internal()`, and then `ack_l2_message()`.

---

## 7 · Security Notes
* **Authenticity** – Only committee can cause L2 messages; only script code can enqueue L1 messages.  
* **Replay Protection** – deterministic IDs + hash inclusion prevent replay.  
* **Denial-of-Service** – per-message timeout and KV garbage collection limit unbounded growth.

---

## 8 · Testing Checklist
- Enqueue → receive path both directions.  
- Ack / nack updates reflected in subsequent queue hashes.  
- Timeout auto-nack after `timeout` height.  
- Signed-tx rejected when queue hash mismatch.

---

*End of TEW Queue Specification v0.1-A* 