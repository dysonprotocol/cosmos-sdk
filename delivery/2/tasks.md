# Tasks for PBI 2: Secure ES-Module Imports with SRI and Import Maps

This document lists all tasks associated with PBI 2.

**Parent PBI**: [PBI 2: Secure ES-Module Imports with SRI and Import Maps](./prd.md)

## Task Summary

| Task ID | Name | Status | Description |
| :------ | :--------------------------------------- | :------- | :--------------------------------- |
| 2-1 | [Add Makefile target to generate SRI hashes](./2-1.md) | InProgress | Automate creation of hashes and updating importmap.json |
| 2-2 | [Update importmap + HTML to validate all external modules](./2-2.md) | Proposed | Extend SRI mechanism to every external module and add error UI |
| 2-3 | [Inject SRI hashes for on-chain static JS](./2-3.md) | InProgress | Add template variables and pass storage entry hashes into base.html |
| 2-E2E | [E2E CoS Test](./2-E2E.md) | Proposed | Verify browser blocks tampered resources and app boots with valid hash | 