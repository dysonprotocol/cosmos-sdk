## Long-running Dyslang server (uvicorn) — integration plan

### Goal
- Replace per-exec Python process launches with a single long‑running Python ASGI server (uvicorn).
- Preserve existing Go per‑request RPC server usage so scripts still operate with the correct `sdk.Context` by passing the ephemeral RPC port into each Python request.
- Keep the external Go API surface close to `dysvm.Exec`, `Benchmark`, `Wsgi`, `DysFormat`, and `ExtractFunctionSchema`.

### Constraints we will keep
- Keep per‑request Go RPC context: `keeper.NewRPCServer(...)` still spins up a JSON‑RPC server on an ephemeral port. Python must use that `rpc_port` for `_chain(...)` so gas, events, and state are tied to the correct `sdk.Context`.
- Preserve existing Python behavior (sandbox, gas metering, freeze_time, events, result/exception shapes) and return payloads.
- No server‑side queueing: each Go call blocks on a single HTTP request to the Python server; uvicorn handles concurrency. 

### High‑level architecture
- Start one uvicorn ASGI server once per node.
- Go (dysvm) becomes an HTTP client to this server. Each Go call:
  1) Spawns a per‑request Go RPC server and obtains `rpc_port` (unchanged).
  2) POSTs to the Python server with the payload + `rpc_port`.
  3) Waits for response and returns it (same shapes as today).
- Python server uses `rpc_port` when building the sandbox so `_chain` reaches the right Go `sdk.Context`.

### ASGI endpoints (uvicorn)
- Transport: HTTP; content-type application/json; response is JSON. To preserve existing shapes, we embed actual results in `result` and always return HTTP 200.

- POST `/exec_script`
  - req: { msg_json, script_json, attached_msg_results_json, header_info_json, rpc_port }
  - resp: { ok: true, result: "<exact string returned today by Exec>" }

- POST `/run_wsgi`
  - req: { script_name, script_json, block_info_json, http_request, rpc_port }
  - resp: { ok: true, result: "<base64 http response string>" }

- POST `/run_benchmark`
  - req: { iterations: int, details: bool }
  - resp: { ok: true, result: "<json string of benchmark result>" }

- POST `/dys_format`
  - req: { code: string }
  - resp: { ok: true, result: "<formatted code>" }

- POST `/extract_function_schema`
  - req: { script_json, block_info_json, rpc_port, executor_address, script_name }
  - resp: { ok: true, result: "<json string schema>" }

- GET `/health`
  - resp: { ok: true, version: "<dyslang+build info>" }

- On error for all: { ok: false, error: { class, msg, lineno, col_offset, end_lineno, end_col_offset, context, source_segment } }

### Python server layout
- New: `dysvm/internal/py-dyslang/dyslang/server_asgi.py`
  - Defines `app(scope, receive, send)` (ASGI). Routes by `scope['path']` + method.
  - Handlers:
    - `/exec_script`: call `dysvm_server.eval_script(...)` and return `response` in same stringified shape.
    - `/run_wsgi`: factor the core of `dyswsgi.main(...)` into a function that returns the base64 HTTP response (no stderr streaming), then call that and return.
    - `/run_benchmark`: call `fp_benchmark.detect_fp_differences(...)` and return its JSON string.
    - `/dys_format`: reuse formatter logic from `__main__.py` (validate with `DysEval().validate`, then `black.format_str`).
    - `/extract_function_schema`: extract existing logic from `__main__` into a helper to avoid duplicating code; return the schema JSON string.
  - For each handler, pass `rpc_port` through to `build_sandbox(..., port=rpc_port)` so `_chain` hits the per‑request Go RPC server.

- Update: `dysvm/internal/py-dyslang/dyslang/__main__.py`
  - Add subcommand `serve` that runs uvicorn:
    - `uvicorn.run("dyslang.server_asgi:app", host=os.getenv("DYSLANG_HOST", "127.0.0.1"), port=int(os.getenv("DYSLANG_PORT", 0)) or <default>, log_level="info")`
    - Do not use `reload` in production.

- Dependencies: ensure `uvicorn` (and `h11`) are available in the embedded Python. If not present, vendor them alongside the embedded runtime in `dysvm/internal/py-dyslang` or include in the embedded distribution.

### Go integration
- New: `dysvm/server.go` — Python server supervisor + HTTP client
  - Responsibilities:
    - Start the Python ASGI server with `-m dyslang serve` (same `python.NewEmbeddedPython("dyslang")` setup and `AddPythonPath(...)`).
    - Choose port: either provide one via env or read from a small startup banner/health probe.
    - Health‑check `/health` before first request; restart on crash.
    - `Request(ctx, path string, payload []byte) (json.RawMessage, error)`: POST to `http://127.0.0.1:<port><path>`; parse `{ok,result|error}`; on `ok=false` build an error mirroring current behavior.
    - Restart semantics: if the server is down, start and retry once for read‑only methods. For `exec_script`, do not auto‑retry to avoid double execution.

- Update: `dysvm/exec.go`
  - Migrate exported functions to call the server:
    - `Exec(...)` → POST `/exec_script` with { msg_json, script_json, attached_msg_results_json, header_info_json, rpc_port }.
    - `Wsgi(...)` → POST `/run_wsgi`.
    - `Benchmark(...)` → POST `/run_benchmark`.
    - `DysFormat(...)` → POST `/dys_format`.
    - `ExtractFunctionSchema(...)` → POST `/extract_function_schema`.
  - Preserve function signatures/return formats.
  - Feature flag (env): if `DYSLANG_STANDALONE=0`, use legacy one‑shot code as a fallback during rollout.

### Concurrency model (no queue)
- No server‑side queuing. Each Go call blocks until the corresponding HTTP request completes. uvicorn is async and can process multiple requests concurrently if needed.
- Determinism options: run uvicorn with a single worker/thread if desired; sandbox is per‑request and uses its provided `rpc_port`, so contexts do not bleed.

### Timeouts & cancellation
- Go side: pass `context.Context` with per‑method timeouts to the HTTP request.
- On cancel, abort the HTTP request. If needed, supervisor can kill and restart Python; we do not attempt in‑flight cancellation inside Python in phase 1.

### Logging & metrics
- Python: log one line per request with method, duration, ok/error; avoid printing large payloads.
- Go: log server start/stop/restart, health, and per‑request latency. Include `rpc_port` in debug logs where useful.

### Failure modes & recovery
- Python server crash: supervisor restarts; safe methods may be retried once; unsafe (state‑changing) methods return error.
- Invalid `rpc_port` / per‑request Go RPC failure: Python `_chain` returns an error as today; propagate unchanged.

### Security
- The ASGI server listens on localhost only. No external exposure.
- The only chain interaction is via the existing per‑request Go RPC server indicated by `rpc_port`.

### Migration plan
1) Implement Python `serve` mode and `server_asgi.py`; keep existing `__main__` subcommands intact.
2) Add `dysvm/server.go` and wire `dysvm/exec.go` to use it behind a feature flag.
3) Run existing tests (start with `tests/script/test_script.py`) to verify parity; fix discrepancies.
4) Enable server by default; keep legacy path for rollback until stable; then remove fallback.

### Testing notes
- Existing tests under `tests/script/` should pass unchanged.
- Command to run a focused subset:
  - `make test PYTEST_ARGS="tests/script/test_script.py"`

### Open questions
- Packaging: confirm `uvicorn` + deps availability in the embedded Python environment.
- Uvicorn worker mode: we likely want a single worker; if multi‑worker, ensure per‑request `rpc_port` remains independent and consider OS port exhaustion in high concurrency.
- Structured errors: ensure exact parity with current error JSON (class, positions, context) for consumer compatibility.

### Implementation checklist
- [ ] Python: add `dysvm/internal/py-dyslang/dyslang/server_asgi.py` with ASGI `app` and endpoints.
- [ ] Python: add `serve` subcommand in `dysvm/internal/py-dyslang/dyslang/__main__.py` to run uvicorn.
- [ ] Python: refactor `dyswsgi.main` core into callable returning base64 HTTP response string for reuse in ASGI.
- [ ] Python: refactor `extract_function_schema` logic into callable for reuse in ASGI.
- [ ] Python: ensure `_chain` uses provided `rpc_port`; verify gas/event parity.
- [ ] Go: create `dysvm/server.go` (process supervisor, health, HTTP client, restart policy).
- [ ] Go: update `dysvm/exec.go` to delegate to `server.go` endpoints; keep legacy fallback behind `DYSLANG_STANDALONE`.
- [ ] Tests: run `tests/script/test_script.py`; compare outputs and event shapes; fix deviations.
- [ ] Ops: choose default host/port via env (`DYSLANG_HOST`, `DYSLANG_PORT`), default to `127.0.0.1` + an assigned free port.
 - [ ] Packaging: add `uvicorn` and `h11` to `dysvm/internal/requirements.in` and rebuild embedded environment.

### Decisions & Log
- 2025-09-18: Implemented ASGI server scaffolding in `dysvm/internal/py-dyslang/dyslang/server_asgi.py` with endpoints: `/health`, `/exec_script`, `/run_benchmark`, `/dys_format`, `/extract_function_schema`, `/run_wsgi`. No server-side queue; each request handled synchronously via HTTP.
- 2025-09-18: Added `serve` subcommand in `dysvm/internal/py-dyslang/dyslang/__main__.py` to run uvicorn (`dyslang.server_asgi:app`). Default host `127.0.0.1`, default port `8787` (override via `DYSLANG_HOST`/`DYSLANG_PORT`).
- 2025-09-18: Error shape preserved: `{ok: false, error: {class,msg,lineno,col_offset,end_lineno,end_col_offset,context,source_segment}}`. Successful responses return `{ok: true, result: <string>}` matching current return shapes.
- 2025-09-18: Added Go supervisor `dysvm/server.go` to spawn and health-check the Python server; HTTP client wrapper to call endpoints; restart-on-demand semantics; localhost only.
- 2025-09-18: Fixed `dysvm/server.go` to use standard `*exec.Cmd` from the embedded command and set env/start directly (API mismatch with previous assumption about EmbeddedCmd wrapper).
- 2025-09-18: Reduced base gas in `x/script/keeper/msg_server.go` UpdateScript from 1_000_000 to 100_000 to prevent out-of-gas for default CLI tx during script updates; DysFormat cost remains the dominant part.
- 2025-09-18: Gated integration in `dysvm/exec.go` behind `DYSLANG_SERVER=1`. Legacy one-shot path still available for rollback.
- 2025-09-18: Assumption: `uvicorn` (and minimal deps like `h11`) are available in embedded Python. If not, we will vendor or add to the embedded distribution in a follow-up.
- 2025-09-18: Added `uvicorn` and `h11` to `dysvm/internal/requirements.in` for embedding in the dyslang python environment.
- 2025-09-18: Increased server boot health timeout to 20s and routed Python server stdout/stderr to Go stderr for visibility; configured uvicorn workers=1, timeout_keep_alive=5 for deterministic behavior.


