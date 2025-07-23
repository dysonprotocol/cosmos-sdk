# Tasks for PBI 1: Separate SCHEDULED vs PENDING tasks & new query endpoints

This document lists all tasks associated with PBI 1.

**Parent PBI**: [PBI 1: Separate SCHEDULED vs PENDING tasks & new query endpoints](./prd.md)

## Task Summary

| Task ID | Name | Status | Description |
| :------ | :--------------------------------------- | :------- | :--------------------------------- |
| 1-1 | [Update protobuf & Go constants](./1-1.md) | Agreed | Add SCHEDULED status and execution_timestamp field |
| 1-2 | [Keeper state-machine changes](./1-2.md) | Proposed | Create-task starts SCHEDULED; BeginBlocker moves to PENDING |
| 1-3 | [Manual KV secondary indexes](./1-3.md) | InProgress | Implement i_addr, i_stat_ts, i_stat_gas maintenance |
| 1-4 | [gRPC query handlers & proto routes](./1-4.md) | Review | Implement /all, /address, /scheduled, /pending, /done |
| 1-5 | [Tests](./1-5.md) | Proposed | Unit + integration tests |
| 1-E2E | [E2E CoS Test](./1-E2E.md) | Proposed | Overall acceptance test |
| 1-6 | [Remove Multi indexes, use raw KV prefixes](./1-6.md) | Proposed | Delete indexes.Multi usage and rewrite queries/ABCI to manual prefixes |
| 1-7 | [CLI tests – happy paths](./1-7.md) | Done | Cover tasks-all, scheduled, pending, done endpoints |
| 1-8 | [CLI tests – pagination](./1-8.md) | Review | Verify offset/limit on all new endpoints |
| 1-9 | [CLI tests – edge & error cases](./1-9.md) | Proposed | Non-existent IDs, empty address results, invalid status |
| 1-10 | [Fix orphaned index entries on task deletion](./1-10.md) | Done | Ensure Keeper.RemoveTask also removes secondary index keys |
| 1-11 | [Clean up old crontasks](./1-11.md) | Done | Add CleanUpTime param & removeOldTasks cleanup logic | 