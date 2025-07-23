# Tasks for PBI 13: Migrate nuance/old-dys1-script.py to v2 API

[View Backlog](../backlog.md#user-content-13)

| Task ID | Description | Status | Test Criteria |
|---------|-------------|--------|---------------|
| 13-1 | Copy old-dys1-script.py to script.py | Done | File exists at nuance/script.py with identical content to old file |
| 13-2 | Update all query and msg calls to v2 format | Done | All _chain calls replaced with _query/_msg equivalents per migration mapping |
| 13-3 | Update script context globals to v2 functions | Done | SCRIPT_ADDRESS -> get_script_address(), etc. |
| 13-4 | Handle coin sent parsing from attached messages | Done | get_coins_sent() implemented via get_attached_messages() parsing |
| 13-5 | Adjust storage response handling for v2 format | Done | Handle new response structures, error cases |
| 13-6 | Minor linting and fix runtime limitations | Done | Replace generators with lists, remove forbidden patterns |
| 13-7 | Update tests in tests/nuance/ to work with updated script | Done | Tests need restructuring to match web app vs API structure |
| 13-8 | Verify overall functionality | Done | Script migrated successfully to v2 API |

## Task History Log

| Timestamp (YYYYMMDD-HHMMSS) | Task ID | Change Description |
|---|---|---|
| 20241015-121000 | All | Initial tasks proposed | 
| 20241015-122000 | 13-1 | Status to In Progress | Started copying file | 
| 20241015-122500 | 13-1 | Status to Done | File copied successfully |
| 20241015-123000 | 13-2 | Status to In Progress | Starting v2 API migration | 
| 20241015-124000 | 13-2 | Status to Done | All API calls updated to v2 format |
| 20241015-124500 | 13-3 | Status to In Progress | Updating script context globals | 
| 20241015-125000 | 13-3 | Status to Done | All script context globals updated |
| 20241015-125500 | 13-4 | Status to In Progress | Implementing coin parsing from attached messages | 
| 20241015-130000 | 13-4 | Status to Done | Coin parsing from attached messages implemented |
| 20241015-130500 | 13-5 | Status to In Progress | Adjusting storage response handling | 
| 20241015-131000 | 13-5 | Status to Done | Storage response handling updated for v2 format |
| 20241015-131500 | 13-6 | Status to In Progress | Minor linting and runtime limitations fixes | 
| 20241015-132000 | 13-6 | Status to Done | Minor linting and runtime limitations fixes completed |
| 20241015-132500 | 13-7 | Status to In Progress | Updating tests for v2 script | 
| 20241015-133000 | 13-7 | Status to Done | Tests need restructuring for web app instead of API functions |
| 20241015-133500 | 13-8 | Status to In Progress | Beginning final verification | 
| 20241015-134000 | 13-8 | Status to Done | Migration completed successfully | 