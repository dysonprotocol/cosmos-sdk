# PBI 14 - Write comprehensive tests for nuance web application

[View Backlog](../backlog.md#user-content-14)

## Task List

| Task ID | Description | Status | Test Criteria |
|---------|-------------|--------|---------------|
| 14-1 | [Set up test infrastructure and utilities](./14-1.md) | Done | Test framework configured, mock utilities created, can run `pytest tests/nuance/ --ff --nf -x` |
| 14-2 | [Test core utility functions](./14-2.md) | Agreed | All utility functions (get_post_id, get_author_id, etc.) have unit tests |
| 14-3 | [Test storage operations](./14-3.md) | Proposed | Storage read/write operations tested with proper mocking |
| 14-4 | [Test post management functions](./14-4.md) | Proposed | Post creation, editing, publishing, and retrieval functions tested |
| 14-5 | [Test rating system](./14-5.md) | Proposed | Rating logic, calculations, and constraints properly tested |
| 14-6 | [Test rewards system](./14-6.md) | Proposed | Reward calculations, claiming, and distribution logic tested |
| 14-7 | [Test web application routes](./14-7.md) | Proposed | All HTTP endpoints tested with proper request/response handling |
| 14-8 | [Test author management](./14-8.md) | Proposed | Author profiles, following, and reputation system tested |

## Task History Log

| Timestamp (YYYYMMDD-HHMMSS) | Task ID | Change Description | User |
|---|---|---|---|
| 20250115-150000 | 14-1 to 14-8 | Initial task breakdown created | Agent |
| 20250115-151000 | 14-1 | Status to In Progress | Started work on test infrastructure setup | Agent |
| 20250115-152000 | 14-1 | Status to Done | Completed test infrastructure setup, fixed coding standards violations, updated gas settings | Agent | 


## API Migration Mapping

### Core Functions

| v1 Function | v2 Equivalent | Notes |
|------------|---------------|-------|
| `_chain("module/Query...")` | `_query({@type: "/module.v1.Query..."})` | New typed message format |
| `_chain("module/sendMsg...")` | `_msg({@type: "/module.v1.Msg..."})` | Returns are handled differently |
| `SCRIPT_ADDRESS` | `get_script_address()` | Now a function call |
| `get_caller()` | `get_executor_address()` | Renamed for clarity |
| `BLOCK_INFO.height` | `get_block_info()["Height"]` | Now accessed via function |
| `BLOCK_INFO.time` | `get_block_info()["Time"]` | Now accessed via function |
| `get_coins_sent()` | `get_attached_messages()` + parsing | Need to parse bank send messages |

### Storage Operations

| v1 Pattern | v2 Pattern | Example |
|-----------|------------|---------|
| `_chain("dyson/QueryStorage", index=f"{SCRIPT_ADDRESS}/{index}")` | `_query({"@type": "/dysonprotocol.storage.v1.QueryStorageGetRequest", "owner": get_script_address(), "index": index})` | Query storage |
| `_chain("dyson/sendMsgUpdateStorage", ...)` | `_msg({"@type": "/dysonprotocol.storage.v1.MsgStorageSet", ...})` | Set storage |
| `_chain("dyson/sendMsgDeleteStorage", ...)` | `_msg({"@type": "/dysonprotocol.storage.v1.MsgStorageDelete", ...})` | Delete storage |
| `_chain("dyson/QueryPrefixStorage", ...)` | `_query({"@type": "/dysonprotocol.storage.v1.QueryStorageListRequest", ...})` | List storage |

### Bank Operations

| v1 Pattern | v2 Pattern |
|-----------|------------|
| `_chain("cosmos.bank.v1beta1/sendMsgSend", ...)` | `_msg({"@type": "/cosmos.bank.v1beta1.MsgSend", ...})` |

### Name Service

| v1 Pattern | v2 Pattern |
|-----------|------------|
| `_chain("names/QueryName", name=name)` | `_query({"@type": "/dysonprotocol.nameservice.v1.QueryNameRequest", "name": name})` |

### Key Breaking Changes

1. **Message Format**: All messages now use `@type` field with full proto path
2. **Return Values**: `_msg` operations don't return query results directly
3. **Error Handling**: Errors throw exceptions instead of returning error objects
4. **Coin Handling**: No direct `get_coins_sent()`, must parse attached messages
5. **Storage Keys**: No automatic SCRIPT_ADDRESS prefix in storage operations 

## Implementation Notes

### Key API Differences Discovered

1. **Storage API Changes:**
   - v1: `_chain("dyson/sendMsgUpdateStorage", ...)` 
   - v2: `_msg({"@type": "/dysonprotocol.storage.v1.MsgStorageSet", ...})`
   
2. **Query API Changes:**
   - v1: `_chain("dyson/QueryStorage", ...)` 
   - v2: `_query({"@type": "/dysonprotocol.storage.v1.QueryStorageGetRequest", ...})`

3. **Script Context Changes:**
   - v1: `SCRIPT_ADDRESS` global
   - v2: `get_script_address()` function
   
4. **Coin Handling:**
   - v1: `get_coins_sent()` returns list directly
   - v2: Need to extract from `get_attached_messages()` and parse MsgSend

  dysond tx script exec --script-address <script_address> [--args <input_data>] [--function-name <function_name>] [--extra-code <extra_code> | --extra-code-path <path>] [--kwargs <keyword_args>] [--attached-message <message>] [flags]

   --attached-message  `{
        "@type":"/cosmos.bank.v1beta1.MsgSend",
        "from_address": ALICE_ADDRESS,
        "to_address": BOB_ADDRESS,
        "amount":[{"denom":"udys","amount":"12"}]
    }`




5. **Runtime Limitations Discovered:**
   - Generator expressions not supported (use list comprehensions)
   - `next()` function not available (use loops)
   - Try/except blocks forbidden in tests
   - Functions starting with `test_` have special behavior
   
6. **Storage Response Format:**
   - v2 responses have different structure: `{"entry": {"data": ...}}`
   - Need to handle missing entries gracefully
   - JSON parsing may return non-dict values