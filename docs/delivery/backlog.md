| ID | Actor | User Story | Status | Conditions of Satisfaction (CoS) |
| --- | --- | --- | --- | --- |
| 1 | Developer | Separate SCHEDULED vs PENDING tasks & provide new query endpoints | Done | See PBI details |
| 2 | Developer | Secure ES-Module imports in demo-dwapp with SRI and import maps | Done | [View Details](./2/prd.md) |
| 3 | Developer | Add metadata (updated_height, updated_timestamp, hash) to Storage entries | Done | [View Details](./3/prd.md) |
| 4 | Developer | Enable JSON extract & filter on Storage queries | Done | [View Details](./4/prd.md) |
| 5 | Developer | Manage coins in demo-dwapp (list balances & send funds) | Done | [View Details](./5/prd.md) |
| 6 | Developer | Manage names via demo-dwapp | Proposed | [View Details](./6/prd.md) |
| 7 | Developer | Upgrade DYSVM to CPython 3.12 with pointer redirection | Done | [View Details](./7/prd.md) |
| 8 | User | List and manage NFTs in demo-dwapp with bidding and listing controls | In Progress | [View Details](./8/prd.md) |
| 9 | Developer | Update demo-tew/script.py to Dyson L2 "Rounds & Slots" spec v0.2 | In Review | [View Details](./9/prd.md) |
| 10 | Developer | Comprehensive TEW L2 testing suite with multi-peer scenarios and edge cases | Proposed | [View Details](./10/prd.md) |
| 11 | Developer | [Integrate TewQueue and TewChain into unified queue_chain.py system](./tasks/11-tasks.md) | In Progress | 1. TewQueue and TewChain merged into single queue_chain.py module<br/>2. L2 queue state stored in TewChain block state with namespaced keys<br/>3. Queue message processing happens automatically during on_begin_block<br/>4. Chain logic supports on_queue_message and on_queue_response callbacks<br/>5. Integration tests demonstrate L1↔L2 queue communication within blockchain transactions |

## PBI History Log

| Timestamp (YYYYMMDD-HHMMSS) | PBI ID | Event Type | Details | User |
|---|---|---|---|---|
| 20250618-224600 | 7 | Status to Done | All tasks completed: CPython 3.12.11 upgrade with pointer redaction successful | User |
| 20250621-120000 | 8 | Created | Added PBI 8 to backlog | User |
| 20250621-121000 | 8 | Status to In Progress | First task started | User |
| 20250624-000000 | 9 | Created | Added PBI 9 to backlog | User |
| 20250624-000500 | 9 | Status to In Progress | First task started | User |
| 20250624-113600 | 9 | Status to In Review | All tasks completed: script.py conforms to spec v0.2, simulator adapted, VM restrictions fixed | User |
| 20250624-114000 | 10 | Created | Added comprehensive TEW L2 testing suite PBI to backlog | User |
| 20250115-143000 | 11 | Created | Added TewQueue and TewChain integration PBI to backlog | User |
| 20250115-145000 | 11 | Status to Agreed | PBI approved for development | User |
| 20250115-145500 | 11 | Status to In Progress | Started task 11-1 (analysis and design) | Agent |