# Tasks for PBI 7: Upgrade DYSVM to CPython 3.12

This document lists all tasks associated with PBI 7.

**Parent PBI**: [PBI 7: Upgrade DYSVM to CPython 3.12](./prd.md)

## Task Summary

| Task ID | Name | Status | Description |
| :------ | :--- | :------ | :----------- |
| 7-1 | [Update CPython sub-module](./7-1.md) | Proposed | Point `dysvm/cpython` to upstream tag `v3.12.11` and sync sub-modules. |
| 7-2 | [Brute-force replace %p format strings](./7-2.md) | Review | Search & edit literals/calls in `dysvm/cpython` so no `%p` reaches user output. |
| 7-3 | [Refactor build scripts & remove header logic](./7-3.md) | Proposed | Ensure build scripts are vanilla; drop CPPFLAGS and header. |
| 7-4 | [Update embed pipeline](./7-4.md) | Proposed | Adjust `dysvm-embed.sh` naming/globbing, regenerate assets. |
| 7-5 | [Regression & CoS tests](./7-5.md) | Proposed | Run and fix `make test`; verify no raw pointers in output. | 