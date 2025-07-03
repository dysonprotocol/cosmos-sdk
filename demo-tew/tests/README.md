# Dyson L2 Demo-TEW Test Suite

The TEW (Test Environment for Watchtowers) tests have been moved to the main test suite.

## Running TEW Tests

TEW tests are now integrated with the main test suite and can be run from the project root:

```bash
# Run all TEW tests
pytest tests/tew/

# Run a specific TEW test
pytest tests/tew/test_smoke.py
```

## Test Files

The TEW tests are now located in `tests/tew/`:
- `test_smoke.py` – Minimal tests to verify environment, dysond, script address, and key presence.
- `test_infra.py` – Tests for key balances, script accessibility, and basic script function calls.
- `test_tew.py` – Tests for TEW-specific functionality including genesis and checkpoint operations.
- `tew.smv` – NuSMV model checking specification for TEW protocol verification.

## Notes

- **No mocks:** All tests interact with the real chain and dysond.
- **Chain state:** Tests may reset the L2 state; do not run against production data.
- **Fixtures:** TEW tests use the main project fixtures from `tests/conftest.py` plus TEW-specific fixtures from `tests/tew/conftest.py`.

---

For questions or issues, see the main project README. 