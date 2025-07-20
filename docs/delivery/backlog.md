| ID | Actor | User Story | Status | Conditions of Satisfaction (CoS) |
| --- | --- | --- | --- | --- |
| 1 | Developer | Separate SCHEDULED vs PENDING tasks & provide new query endpoints | Done | See PBI details |
| 2 | Developer | Secure ES-Module imports in demo-dwapp with SRI and import maps | Done | [View Details](./2/prd.md) |
| 3 | Developer | Add metadata (updated_height, updated_timestamp, hash) to Storage entries | Done | [View Details](./3/prd.md) |
| 4 | Developer | Enable JSON extract & filter on Storage queries | Done | [View Details](./4/prd.md) |
| 5 | Developer | Manage coins in demo-dwapp (list balances & send funds) | Done | [View Details](./5/prd.md) |
| 6 | Developer | Manage names via demo-dwapp | Done | [View Details](./6/prd.md) |
| 7 | Developer | Upgrade DYSVM to CPython 3.12 with pointer redirection | Done | [View Details](./7/prd.md) |
| 8 | User | List and manage NFTs in demo-dwapp with bidding and listing controls | Done | [View Details](./8/prd.md) |
| 9 | Developer | Update demo-tew/script.py to Dyson L2 "Rounds & Slots" spec v0.2 | Done | [View Details](./9/prd.md) |
| 10 | Developer | Comprehensive TEW L2 testing suite with multi-peer scenarios and edge cases | Done | [View Details](./10/prd.md) |
| 11 | Developer | [Integrate TewQueue and TewChain into unified queue_chain.py system](./tasks/11-tasks.md) | Done | 1. TewQueue and TewChain merged into single queue_chain.py module<br/>2. L2 queue state stored in TewChain block state with namespaced keys<br/>3. Queue message processing happens automatically during on_begin_block<br/>4. Chain logic supports on_queue_message and on_queue_response callbacks<br/>5. Integration tests demonstrate L1↔L2 queue communication within blockchain transactions |
| 12 | User | [Create website with URL only](./tasks/12-tasks.md) | Done | 1. User can enter just URL when clicking 'New website'<br/>2. No validation errors for other fields<br/>3. Website appears immediately in list |
| 13 | Developer | [As a developer, I want to migrate nuance/old-dys1-script.py to nuance/script.py updating to v2 API so that the application works with the new Dyson protocol version](./tasks/13-tasks.md) | Done | 1. Script copied and updated with v2 API calls per migration mapping.<br/>2. No major logic changes, only API adaptations and minor linting.<br/>3. All functions maintain original behavior.<br/>4. Tests updated accordingly if needed.<br/>5. Updated script stored at nuance/script.py |
| 14 | Developer | [Write comprehensive tests for nuance web application](./tasks/14-tasks.md) | Done | 1. All core functions have unit tests with proper mocking<br/>2. Web application routes have integration tests<br/>3. Rating system logic is thoroughly tested<br/>4. Rewards calculation and claiming is tested<br/>5. Tests run successfully with `pytest tests/nuance/ --ff --nf -x` |
| 15 | Developer | [Migrate Wallet Management to dys2 Standard](./delivery/15/15-tasks.md) | Done | 1. A new `dyson.js` module is created in `nuance/storage/static/js/`.<br/>2. The new module provides functionality to connect Keplr, and to create, import, and connect to local (encrypted) CosmJS wallets.<br/>3. The new module can build, sign, and broadcast transactions, including gas estimation via simulation.<br/>4. The `nuance/script.py` `/wallet` endpoint serves a self-contained HTML page that uses the new `dyson.js` and does not rely on Alpine.js.<br/>5. The old `wallet.html` template and `walletStore.js` are removed. |
| 16 | Developer | [Refactor Nuance dwapp to use external templates and declarative routing](./tasks/16-tasks.md) | Done | 1. All large inline HTML templates in `nuance/script.py` are extracted into separate files.<br/>2. `nuance/script.py` is updated to load these templates from on-chain storage at runtime.<br/>3. The routing logic in `nuance/script.py` is refactored from an `if/elif` block to a declarative system with a `@route` decorator.<br/>4. The application's web interface remains functionally unchanged.<br/>5. All tests in `tests/nuance/` pass after the refactoring. |
| 17 | Developer | [Implement htmx partial loading for all Nuance endpoints](./tasks/17-tasks.md) | In Progress | 1. All route handlers check for `HTTP_HX_REQUEST` header.<br/>2. When htmx request detected, handlers return content wrapped in `<main>` tags only.<br/>3. When not an htmx request, handlers return full page using `_render_base()`.<br/>4. `/recent` and `/active` endpoints serve as implementation pattern for remaining endpoints.<br/>5. All tests in `tests/nuance/` continue to pass after implementation. |

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
| 20241015-120000 | 13 | Created | Added PBI for migrating nuance/old-dys1-script.py to v2 API | Agent |
| 20241015-120500 | 13 | Status to Agreed | PBI approved for development | Agent |
| 20241015-121500 | 13 | Status to In Progress | Started work on first task | Agent |
| 20241015-134500 | 13 | Status to In Review | All tasks completed, ready for review | Agent |
| 20250115-150000 | 14 | Created | Added comprehensive testing PBI for nuance web application | Agent |
| 20250115-151000 | 14 | Status to In Progress | Started work on comprehensive testing tasks | Agent |
| 20250115-160000 | 15 | Created | Added PBI for dys2 wallet migration | Agent |
| 20250115-161000 | 15 | Status to Done | Marked as done per user request | Agent |
| 20250115-161000 | 6 | Status to Done | Marked as done per user request | Agent |
| 20250115-161000 | 8 | Status to Done | Marked as done per user request | Agent |
| 20250115-161000 | 9 | Status to Done | Marked as done per user request | Agent |
| 20250115-161000 | 10 | Status to Done | Marked as done per user request | Agent |
| 20250115-161000 | 11 | Status to Done | Marked as done per user request | Agent |
| 20250115-161000 | 12 | Status to Done | Marked as done per user request | Agent |
| 20250115-161000 | 13 | Status to Done | Marked as done per user request | Agent |
| 20250115-161000 | 14 | Status to Done | Marked as done per user request | Agent |
| 20240710-100000 | 16 | Created | Added PBI for Nuance template and routing refactor. | Agent |
| 20240710-100500 | 16 | Status to In Progress | Started work on task 16-1 (Setup and Foundation) | Agent |
| 20250115-170000 | 16 | Status to Done | All tasks completed: Templates extracted, routing refactored, tests passing | Agent |
| 20250115-170100 | 17 | Created | Added PBI for htmx partial loading implementation across all endpoints | Agent |
| 20250115-170200 | 17 | Status to In Progress | Started work on task 17-1 (main content endpoints) | Agent |
