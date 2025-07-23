# PBI-7: Upgrade DYSVM to CPython 3.12 (pointer-redaction header)

## Overview
Adopt CPython 3.12.11 for the DYSVM component while eliminating the large, version-specific patch.  Instead, add a tiny header that overrides pointer formatting so build artefacts never leak raw memory addresses.  All build scripts must continue to produce platform-specific, PGO/LTO-optimised standalone distributions and embed them via go-embed-python.

## Problem Statement
Maintaining a multi-thousand-line patch against the CPython source creates constant merge pain every time a new Python minor version is released.  The current patch for 3.11 is already impossible to apply to 3.12.  We need a sustainable way to keep the redaction behaviour without touching upstream files.

## User Story
As a Developer, I want DYSVM to run on Python 3.12 with the same pointer-redaction guarantees, so that I can keep the runtime secure and up-to-date without large maintenance overhead.

## Technical Approach (updated)
We will **brute-force replace all human-visible `%p` usages** in CPython's C
sources instead of injecting a runtime shim.

1. Keep the sub-module pinned to `v3.12.11`.
2. Scan every file under `dysvm/cpython` for format strings that contain:
   • `" at %p"`, `"@ %p"`, `"%s at %p"`, etc.
3. Modify those literals so they no longer output the pointer and instead
   embed a deterministic constant:
   • `"at 0x1234"`, `"@0x1234"`, etc.
4. Likewise, any call to `PyUnicode_FromFormat` / `PyUnicode_FromFormatV`
   that uses `%p` will be changed so the `%p` is replaced with `0x1234` and
   the corresponding argument removed.
5. The edits live in the repository (no dynamic patch step required) so the
   build pipeline stays vanilla.
6. Update scripts only for the version bump; no special CPPFLAGS.

## Acceptance Criteria (CoS)
1. `dysvm/cpython` is at tag `v3.12.11` with format-string edits committed.
2. Grep for `%p` in the built binaries' strings returns **zero hits**.
3. A sample call `python - <<<'print(repr(object()))'` prints `'<object at 0x1234>'`.
4. Build passes on all CI platforms and `make test` is green.
5. No additional header or CPPFLAG tricks are required; source edits are explicit.

## Dependencies
* `astral-sh/python-build-standalone` release `20250612`.
* `kluctl/go-embed-python` (used only for code-gen, not the bundled binaries).

## Related Tasks
[Tasks for PBI 7](./tasks.md) 