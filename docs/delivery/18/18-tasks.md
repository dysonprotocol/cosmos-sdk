# PBI 18 Tasks: Add QueryMetrics to Storage Module

[View Backlog](../backlog.md#user-content-18)

## Task List

| Task ID | Description | Status | Test Criteria |
|---------|-------------|--------|---------------|
| 18-1 | [Add StorageMetrics message to storage.proto](./18-1.md) | Proposed | StorageMetrics message defined with owner and total_bytes fields, protobuf generation successful |
| 18-2 | [Add QueryMetrics RPC to query.proto and implement endpoint](./18-2.md) | Proposed | QueryMetrics RPC defined, gRPC and REST endpoints accessible, returns storage metrics per address |
| 18-3 | [Implement metrics tracking in msg_server.go](./18-3.md) | Proposed | StorageSet/StorageDelete update metrics correctly, metrics persist in state, accurate byte counting |
| 18-4 | [Add keeper methods for metrics management](./18-4.md) | Proposed | GetStorageMetrics and UpdateStorageMetrics methods implemented, proper error handling |
| 18-5 | [Update CLI and add tests for QueryMetrics functionality](./18-5.md) | Proposed | CLI query command added, comprehensive tests for metrics tracking and querying |

## Task History Log

| Timestamp (YYYYMMDD-HHMMSS) | Task ID | Change Description |
|---|---|---|
| 20250115-180100 | 18-1 | Created initial task breakdown for StorageMetrics feature |
| 20250115-180100 | 18-2 | Created QueryMetrics RPC task |
| 20250115-180100 | 18-3 | Created metrics tracking implementation task |
| 20250115-180100 | 18-4 | Created keeper methods task |
| 20250115-180100 | 18-5 | Created CLI and testing task | 