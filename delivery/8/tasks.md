# Tasks for PBI 8: NFT List & Detail View with Bidding

This document lists all tasks associated with PBI 8.

**Parent PBI**: [PBI 8](./prd.md)

## Task Summary

| Task ID | Name | Status | Description |
| :------ | :--------------------------------------------- | :------- | :-------------------------------------------------------------- |
| 8-1 | [Analyse requirements & UX flows](./8-1.md) | Done | Document detailed requirements, API design, UX wireframes, and acceptance tests |
| 8-2 | [Add backend routes in `script.py`](./8-2.md) | Done | Implement `/nftclasses`, `/nfts/class/{class_id}`, `/nfts/owner/{address}` routes |
| 8-3 | [Create templates `nftclasses.html`, `nfts.html`](./8-3.md) | Done | Build HTMX/Alpine enabled templates for class list & NFT detail views |
| 8-4 | [Implement `nftStore.js` Alpine store](./8-4.md) | Done | Client-side logic for fetching classes/NFTs, bidding, accept/reject, listed toggle |
| 8-5 | [Integrate navigation & explanatory notes](./8-5.md) | Done | Add navigation link, ensure note about `nftclass.always_listed` priority |
| 8-6 | [End-to-end tests for bidding & listing](./8-6.md) | Proposed | Write E2E tests validating AC1–AC7, including testing additional ParamsAllowedDenoms and validating success & error scenarios |

## Task History Log

| Timestamp (YYYYMMDD-HHMMSS) | Task ID | Change Description |
|---|---|---| 
| 20250621-121000 | 8-1 | Status to Done | Analysis completed, skeleton doc created | User |
| 20250621-124500 | 8-2 | Status to Done | Backend routes implemented | User |
| 20250621-124500 | 8-3 | Status to Done | Templates completed | User |
| 20250621-123000 | 8-4 | Status to Done | Implementation completed | User |
| 20250621-123000 | 8-5 | Status to Done | Navigation & notes integrated | User |
| 20250621-123000 | 8-6 | Description updated | Added ParamAllowedDenoms success/error test requirement | User | 