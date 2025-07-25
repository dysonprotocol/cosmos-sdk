# PBI 23: Create external names without commit-reveal process

[View Backlog](../backlog.md#user-content-23)

## Task List

| Task ID | Description | Status | Test Criteria |
|---------|------------|---------|---------------|
| 23-1 | [Add MsgCreateExternalName to tx.proto](./23-1.md) | Review | Message defined with authority signer, name field, and proper annotations |
| 23-2 | [Add ExternalNameRegex validation](./23-2.md) | Review | Regex validates domain/subdomain format, rejects invalid names |
| 23-3 | [Implement MsgCreateExternalName handler](./23-3.md) | Review | Handler validates authority, creates NFT directly, no commit-reveal |
| 23-4 | [Add comprehensive tests for MsgCreateExternalName](./23-4.md) | Review | Unit tests cover validation, authorization, and NFT creation |
| 23-5 | [Update protobuf generation and verify build](./23-5.md) | Review | Generated Go code compiles, no build errors, types available |
| 23-6 | [Implement EnsureExternalNamesClassExists for externalnames.dys](./23-6.md) | Review | ExternalNames class created with AlwaysListed=false, keeper function available |

## Task History Log

| Timestamp (YYYYMMDD-HHMMSS) | Task ID | Change Description |
|------------------------------|---------|-------------------|
| 20250725-000100 | 23-1 to 23-5 | Initial task planning for MsgCreateExternalName feature |
| 20250725-000300 | 23-1 | Status to In Progress | Beginning implementation of MsgCreateExternalName protobuf message |
| 20250725-000400 | 23-1 | Status to Review | MsgCreateExternalName implementation complete, protobuf generated successfully |
| 20250725-000500 | 23-2 | Status to In Progress | Starting ExternalNameRegex validation implementation |
| 20250725-000600 | 23-2 | Status to Review | ExternalNameRegex implemented with comprehensive tests, all validations pass |
| 20250725-000700 | 23-3 | Status to In Progress | Starting implementation of MsgCreateExternalName handler |
| 20250725-000800 | 23-3 | Status to Review | MsgCreateExternalName handler updated with ExternalNameRegex validation, build successful |
| 20250725-000900 | 23-4 | Status to In Progress | Starting comprehensive tests for MsgCreateExternalName |
| 20250725-001000 | 23-4 | Status to Review | Comprehensive integration tests completed and passing, covers all validation scenarios |
| 20250725-001100 | 23-5 | Status to In Progress | Starting final protobuf generation and build verification |
| 20250725-001200 | 23-5 | Status to Review | Protobuf generation successful, build completed, external name tests passing |
| 20250725-130000 | 23-6 | Initial task planning | Added task for EnsureExternalNamesClassExists implementation |
| 20250725-130500 | 23-6 | Status to In Progress | Starting implementation of EnsureExternalNamesClassExists function |
| 20250725-130800 | 23-6 | Status to Review | EnsureExternalNamesClassExists implemented with AlwaysListed=false, build successful |
