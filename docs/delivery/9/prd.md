# PBI 9 – Update demo-tew/script.py to Dyson L2 "Rounds & Slots" spec v0.2

## Scope and Purpose

This PBI updates the existing `demo-tew/script.py` message-board implementation so that it fully complies with the Dyson L2 "Rounds & Slots" specification v0.2 defined in [`demo-tew/spec.md`](../spec.md).  The change lays the foundation for additional modules and unit tests based on the standard L2 execution model.

## Conditions of Satisfaction (CoS)

1. `script.py` exposes all public API functions defined in §3.2 of the spec: `genesis`, `join`, `leave`, `submit_slots`, `next_round`, `progress_round`, `checkpoint`.
2. Storage keys follow §2 table (e.g. `l2/{id}/state/{round}`, `l2/{id}/slots/…`).
3. Deterministic engine (`_next_snapshot`) executes `core_logic`, advances `meta.round`, and updates `meta.started_at`.
4. `progress_round` flushes membership queues, collects slots, enforces timeout, and commits the new snapshot.
5. `submit_slots` detects equivocation and stores proof under `evidence/eqv/…`.
6. Unit tests cover happy-path flows plus error conditions (timeout not reached, equivocation, invalid signature).
7. Existing `simulate.py` script is updated and passes for ≥3 rounds in CI.

## Out of Scope

* BLS aggregate signature verification can be stubbed with a placeholder `_verify_agg_sig` that always returns `True`; full cryptographic validation will be addressed in a separate PBI.

## Dependencies

* None.

## Risks & Mitigations

* **Breaking API change.**  Existing front-end code relies on the old message-board API.  The simulator and any external callers must be updated in task 9-9.
* **State migration.**  Legacy L2 data from the old format is incompatible.  A one-time reset or migration script may be necessary; development environment can simply reset storage.

## Success Metrics

* `make test` passes.
* `python demo-tew/simulate.py --script-address <addr> --rounds 5 --reset` completes 5 rounds without errors.
* All CoS verified by E2E test 9-E2E. 