# PBI 17: Implement htmx partial loading for all Nuance endpoints

This document tracks the tasks for PBI 17.

[View Backlog](../backlog.md#user-content-17)

## Task List

| Task ID | Description | Status | Test Criteria |
|---|---|---|---|
| 17-1 | **Implement htmx partial loading for main content endpoints:** Update `/`, `/blog`, `/(?P<post_id>\d+)`, `/topics`, `/publish` route handlers to support htmx partial loading pattern. | Done | - Each handler checks for `HTTP_HX_REQUEST` header.<br/>- Returns content wrapped in `<main>` tags for htmx requests.<br/>- Returns full page using `_render_base()` for non-htmx requests.<br/>- Maintains existing functionality and styling. |
| 17-2 | **Implement htmx partial loading for author endpoints:** Update `/authors/(?P<author>[^/]+)` and `/authors/(?P<author>[^/]+)/edit` route handlers to support htmx partial loading pattern. | Done | - Each handler checks for `HTTP_HX_REQUEST` header.<br/>- Returns content wrapped in `<main>` tags for htmx requests.<br/>- Returns full page using `_render_base()` for non-htmx requests.<br/>- Maintains existing functionality and styling. |
| 17-3 | **Implement htmx partial loading for post-specific endpoints:** Update `/(?P<post_id>\d+)/replies`, `/(?P<post_id>\d+)/topics/(?P<tag_name>\w+)`, `/(?P<post_id>\d+)/replies/(?P<reply_post_id>\d+)`, `/(?P<post_id>\d+)/topics` route handlers to support htmx partial loading pattern. | Proposed | - Each handler checks for `HTTP_HX_REQUEST` header.<br/>- Returns content wrapped in `<main>` tags for htmx requests.<br/>- Returns full page using `_render_base()` for non-htmx requests.<br/>- Maintains existing functionality and styling. |
| 17-4 | **Implement htmx partial loading for topic endpoints:** Update `/topics/(?P<tag_name>\w+)`, `/topics/(?P<tag_name>\w+)/(?P<sortby>hot|best)`, `/topics/(?P<tag_name>\w+)/stats` route handlers to support htmx partial loading pattern. | Proposed | - Each handler checks for `HTTP_HX_REQUEST` header.<br/>- Returns content wrapped in `<main>` tags for htmx requests.<br/>- Returns full page using `_render_base()` for non-htmx requests.<br/>- Maintains existing functionality and styling. |
| 17-5 | **Verify test compatibility:** Run test suite to ensure all tests pass with htmx partial loading implementation. | Proposed | - All tests in `tests/nuance/` pass with command `pytest tests/nuance/ --ff --nf -x -s`.<br/>- No regressions in existing functionality.<br/>- Tests properly handle both htmx and non-htmx request scenarios. |

## Task History Log

| Timestamp (YYYYMMDD-HHMMSS) | Task ID | Change Description |
|---|---|---|
| 20250115-170100 | 17-1 | Created task for main content endpoints. |
| 20250115-170100 | 17-2 | Created task for author endpoints. |
| 20250115-170100 | 17-3 | Created task for post-specific endpoints. |
| 20250115-170100 | 17-4 | Created task for topic endpoints. |
| 20250115-170100 | 17-5 | Created task for test verification. |
| 20250115-170200 | 17-1 | Status to In Progress. Started implementing htmx partial loading for main content endpoints. |
| 20250115-170300 | 17-1 | Status to Done. Implemented htmx partial loading for handle_post_detail, handle_topics, and handle_publish endpoints. |
| 20250115-170400 | 17-2 | Status to Done. Implemented htmx partial loading for handle_author_posts and handle_edit_author endpoints. Also fixed HTMX targeting issue that was causing profile display problems. | 