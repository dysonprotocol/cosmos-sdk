# PBI 16: Refactor Nuance dwapp to use external templates and declarative routing

This document tracks the tasks for PBI 16.

[View Backlog](../backlog.md#user-content-16)

## Task List

| Task ID | Description | Status | Test Criteria |
|---|---|---|---|
| 16-1 | **Setup and Foundation:** Implement foundational components for template loading and routing in `nuance/script.py`. | Done | - `SafeString`, `SafeTemplate`, `fetch_template`, and `route` decorator are present in `nuance/script.py`.<br/>- A new `wsgi` function structure is in place. |
| 16-2 | **Extract HTML Templates to Files:** Extract all inline HTML templates from `nuance/script.py` into individual `.html` files under `nuance/storage/templates/`. | Done | - `nuance/storage/templates/` directory is created.<br/>- All major HTML blocks are moved to appropriately named `.html` files within that directory. |
| 16-3 | **Refactor WSGI Handlers:** Convert the existing `if/elif` routing logic into individual functions decorated with `@route`. | Done | - Each route is handled by a dedicated function.<br/>- Handler functions use `fetch_template` to load HTML.<br/>- A `_render_base` function is implemented and used. |
| 16-4 | **Update Test Suite:** Update tests in `tests/nuance/` to support the new template-loading mechanism. | Done | - Tests successfully upload HTML templates to storage before execution.<br/>- Test assertions are updated to reflect the new architecture.<br/>- `pytest tests/nuance/` passes. |
| 16-5 | **Final Integration and Cleanup:** Remove old template variables and routing logic, and activate the new system. | Done | - Old `_TEMPLATE` variables are removed.<br/>- The old `wsgi` function is replaced by the new one.<br/>- The script is clean of legacy routing and template code. |
| 16-6 | **Extract Remaining Inline Templates:** Extract the remaining 3 inline `Template()` usages to external template files and convert them to use `SafeTemplate` with `{{}}` syntax. | Done | - `post_tag_detail.html`, `post_reply_detail.html`, and `topic_stats.html` templates are created.<br/>- All `Template(` usages are replaced with `SafeTemplate(fetch_template())`.<br/>- Templates use `{{}}` syntax instead of `$` syntax.<br/>- All tests continue to pass. |

## Task History Log

| Timestamp (YYYYMMDD-HHMMSS) | Task ID | Change Description |
|---|---|---|
| 20240710-100000 | 16-1 | Created task. |
| 20240710-101000 | 16-1 | Status to Done. Foundation components implemented. |
| 20240710-101000 | 16-2 | Status to In Progress. Starting template extraction. |
| 20240710-102000 | 16-2 | Status to Done. All templates extracted to separate files. |
| 20240710-103000 | 16-3 | Status to Done. All route handlers converted to declarative system. |
| 20240710-104000 | 16-4 | Status to In Progress. Starting test suite updates. |
| 20240710-105000 | 16-4 | Status to Done. Test infrastructure already supports template loading. |
| 20240710-106000 | 16-5 | Status to In Progress. Starting final cleanup. |
| 20240710-107000 | 16-5 | Status to Done. All legacy code removed and new system active. |
| 20240710-108000 | 16-6 | Created task. Found 3 remaining inline Template() usages to extract. |
| 20240710-109000 | 16-6 | Status to Done. All remaining templates extracted and converted to {{}} syntax. |
| 20240710-100000 | 16-2 | Created task. |
| 20240710-100000 | 16-3 | Created task. |
| 20240710-100000 | 16-4 | Created task. |
| 20240710-100000 | 16-5 | Created task. |
| 20240710-100000 | 16-6 | Created task. | 