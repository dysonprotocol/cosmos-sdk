# PBI-3: Add Metadata Fields to Storage Entries

## Overview
`x/storage` currently stores arbitrary data strings keyed by `(owner, index)` but lacks any provenance or integrity information. This PBI adds three new fields to every `Storage` record:

1. `updated_height` – the block height at which the entry was last created/modified.
2. `updated_timestamp` – RFC-3339 UTC timestamp of the block header when the entry was last modified.
3. `hash` – SHA-256 (hex) of the `data` field; stored to enable integrity verification without re-hashing large payloads.

## Problem Statement
Applications that consume on-chain storage need to verify freshness and integrity of a stored object. Without metadata they must query block history or recompute hashes, which is inefficient and fragile. Exposing these fields simplifies client logic and unlocks future security features (e.g., notarised files).

## User Stories
| ID | Actor | User Story |
|----|-------|------------|
| 3-A | Developer | *As a developer*, I want to see when a storage value was last updated so I can cache intelligently. |
| 3-B | Auditor | *As an auditor*, I want to check the hash of stored data matches what the client holds to detect tampering. |

## Technical Approach
1. **Proto change** – update `dysonprotocol/storage/v1/storage.proto` to include the 3 fields (uint64, google.protobuf.Timestamp, bytes/string?).
2. Regenerate code via `make proto-gen` (CI or local).
3. **Keeper logic** – when executing `MsgStorageSet`, compute hash of `data` and set `updated_height` & `updated_timestamp` via `ctx.BlockHeight()` & `ctx.BlockTime()`.
4. Update queries, CLI & yml docs.
5. Emit events with new metadata.

## UX/UI Considerations
- API responses include new fields; front-end can display "last updated X ago" and verify hash.

## Acceptance Criteria
- Storage protobuf updated & compiled.
- `MsgStorageSet` populates all three fields on create & update.
- gRPC query returns populated metadata.
- Existing tests updated; new unit test asserts hash is correct.

## Dependencies
None.

## Open Questions
- Should `hash` be stored as raw bytes or hex?  (Proposal: hex string for easier JSON display.)

## Related Tasks
See [tasks list](./tasks.md). 