# PBI-4: Enable JSON extract & filter on Storage queries

## Overview
This PBI introduces two optional parameters – **extract** and **filter** – to the Storage gRPC query API. These parameters allow callers to:

* **extract**: Return only the sub-portion of the stored JSON value selected by a [GJSON](https://github.com/tidwall/gjson) path, reducing network payloads.
* **filter**: When listing entries, include an entry only if the supplied GJSON path exists in the entry's `data` payload.

## Problem Statement
DApp developers frequently store complex JSON blobs in the Storage module but often need only a small subset of that data or need to search by JSON field. Currently they must download the full value for every entry and post-process client-side, which is bandwidth-wasteful and slow.

## User Stories
| ID | As a | I want | So that |
|----|------|--------|---------|
| U1 | Developer | To retrieve only `profile.name` from `profile/info` | I save bandwidth & parsing costs |
| U2 | Developer | To list entries where `category` field exists | I can efficiently filter large datasets |

## Technical Approach
1. **Proto changes**: Add `string extract = 3` to `QueryStorageGetRequest` and `string filter = 3` to `QueryStorageListRequest` (numbers chosen to avoid existing field tags).
2. **Keeper logic**:
   * `StorageGet`: If `extract` provided & non-empty, apply `gjson.Get(storage.Data, extract)` and replace `Storage.Data` with the resulting JSON fragment (string).
   * `StorageList`: Extend `predicateFunc` – skip entries if `filter` non-empty and `!gjson.Get(val.Data, req.Filter).Exists()`.
   * Apply `extract` inside `transformFunc` when building the result slice, analogous to `StorageGet`.
3. Add unit & integration tests covering:
   * Extraction of nested fields.
   * Filtering within paginated lists.
   * Backwards compatibility (old clients with empty params behave identically).
4. Update CLI & swagger docs (out-of-scope for this initial task).

## UX/UI Considerations
N/A – gRPC / CLI only.

## Acceptance Criteria
1. gRPC proto generates correctly with new fields.
2. `dysond query storage get` supports `--extract` flag and returns subset JSON.
3. `dysond query storage list` supports `--filter` flag, returning only matching entries.
4. All existing tests pass; new tests cover success & edge cases.
5. Documentation updated (`storage_guide.ipynb` and swagger).

## Dependencies
* [tidwall/gjson](https://github.com/tidwall/gjson) (already vendored / required).

## Open Questions
* Should `extract` also support multiple paths? (Out of scope for v1.)

## Related Tasks
* [Tasks for PBI 4](./tasks.md) 