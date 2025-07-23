# PBI-2: Secure ES-Module Imports with SRI and Import Maps

## Overview
This PBI introduces integrity checks for every JavaScript module loaded by **demo-dwapp**.  We will leverage Sub-resource Integrity (SRI) in combination with browser **Import Maps** (and the `es-module-shims` polyfill where required) so that the browser validates each fetched bundle before execution.

## Problem Statement
Currently, `demo-dwapp` depends on third-party ES-modules that are fetched directly from public CDNs without any authenticity verification.  A malicious actor could tamper with these bundles, spoof the CDN domain, or serve an outdated version, potentially compromising users.  We need a mechanism to guarantee that the exact code we expect is what the browser executes.

## User Stories
| ID | Actor | User Story |
|----|-------|------------|
| 2-A | Developer | *As a developer*, I want to statically import `@cosmjs/encoding` **with an integrity hash** so that I can be confident the bundle hasn't been altered. |
| 2-B | Security-conscious user | *As a security-conscious user*, I want demo-dwapp to refuse to run if the module hash doesn't match, preventing the execution of malicious code. |

## Technical Approach
1. **Generate SRI hashes** for *every* external module referenced in `importmap.json` (initial scope: whatever is present; the Makefile target will iterate automatically).
2. **Publish an `importmap.json`** that maps specifiers to fully-qualified CDN URLs **and** includes the `integrity` and `crossorigin` attributes per entry.
3. **Serve `es-module-shims`** in the HTML so that browsers without native Import-Map integrity support receive seamless polyfill behaviour.
4. **Load the import-map via `<script type="importmap-shim" src="/importmap.json">`**, ensuring the shim verifies the JSON's own SRI and each mapped resource.
5. **Update application code** to perform static imports (e.g. `import { fromBase64 } from "@cosmjs/encoding"`).
6. **Graceful degradation**: if any integrity check fails, surface a clear error UI instead of silently breaking.

## UX/UI Considerations
- Display a user-friendly error banner when the application cannot start due to a failed integrity check.
- Keep loading spinners visible until modules are confirmed valid or an error is shown.

## Acceptance Criteria
- The HTML entry point contains **no `<script src="…">` tags without an `integrity` attribute** (except the trusted shim itself).
- `importmap.json` is fetched with its own SRI hash specified in the HTML.
- **All** mapped module entries include an **exact SHA-384** hash and `crossorigin:"anonymous"`.
- The app successfully boots in recent versions of Chrome, Firefox, and Safari **without network errors** when hashes match.
- Changing any byte in the remote bundle causes the browser (or shim) to block execution and shows the error UI.

## Dependencies
- [`es-module-shims`](https://github.com/guybedford/es-module-shims) ≥1.6.3
- Public CDN that allows deterministic asset URLs (e.g. jsDelivr, unpkg)

## Decisions
1. We will extend the integrity mechanism to **all external modules** in the import map, not just critical ones.
2. A dedicated Makefile target `generate-sri` under `demo-dwapp/` will perform build-time automation for hash generation and import-map updates.

## Open Questions
*(none at this time)*

## Related Tasks
See the [tasks list](./tasks.md) for implementation breakdown. 