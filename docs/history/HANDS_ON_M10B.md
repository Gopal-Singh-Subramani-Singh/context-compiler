# M10b hands-on acceptance — real local MCP over stdio

This guide is intentionally real MCP: the maintained Python MCP SDK launches the packaged tiny server as a child process and exchanges protocol messages over stdio. The server is bounded to a disposable sandbox and all dangerous sinks are fake local ledgers.

## 1. Clean environment and full baseline

```bash
cd ~/Desktop/context-compiler-partial-recovery/context-compiler-m10b
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools
python -m pip install -e '.[dev,live-mcp]'
rehash 2>/dev/null || true
contextc version
python -c 'import mcp, pulp; print("MCP SDK:", getattr(mcp, "__version__", "installed")); print("PuLP:", pulp.__version__)'
pytest -q tests/live_mcp
pytest -q
```

Expected package version: `0.17.2`. Current cumulative Mac target: **350 passed** before any package-only final checks added after this guide.

## 2. Real MCP protocol inspection

```bash
ROOT=~/Desktop/m10b-real-world
SERVER=~/Desktop/context-compiler-partial-recovery/context-compiler-m10b/contextc/demos/live_mcp/tiny_server.py
SANDBOX="$ROOT/sandbox"
CACHE="$ROOT/cache"
rm -rf "$ROOT"
mkdir -p "$ROOT"

contextc mcp live inspect --server "$SERVER" --sandbox "$SANDBOX" --json | tee "$ROOT/inspect.json"
contextc mcp live tools --server "$SERVER" --sandbox "$SANDBOX" --json > "$ROOT/tools.json"
contextc mcp live resources --server "$SERVER" --sandbox "$SANDBOX" --json > "$ROOT/resources.json"
```

Assert real discovery:

```bash
python - "$ROOT/inspect.json" <<'PY'
import json, sys
p=json.load(open(sys.argv[1]))
print("initialized:", p["initialized"])
print("transport:", p["transport"])
print("tools:", len(p["tools"]))
print("resources:", len(p["resources"]))
print("server declaration:", p["server_declaration_hash"])
assert p["initialized"] is True
assert p["transport"] == "stdio"
assert len(p["tools"]) >= 8
assert len(p["resources"]) == 3
print("REAL MCP DISCOVERY PASS")
PY
```

## 3. Full bounded live validation suite

```bash
contextc mcp live validate \
  --server "$SERVER" \
  --sandbox "$SANDBOX" \
  --cache-root "$CACHE" \
  --json | tee "$ROOT/validation.json"
```

The result must show zero real network/shell/credentials/messages, zero blocked-sink secret leaks, safe scenarios executed, dangerous sinks blocked, and CTX445 correspondence evidence for the intentionally misdeclared tool.

## 4. Safe plan actually executes

```bash
PLANROOT=~/Desktop/context-compiler-partial-recovery/context-compiler-m10b/examples/live_mcp/plans
contextc mcp live plan execute "$PLANROOT/public-to-local.json" \
  --server "$SERVER" --sandbox "$SANDBOX" --cache-root "$CACHE" --json \
  > "$ROOT/public-to-local.json"

test -f "$SANDBOX/copied-public.txt" && echo "SAFE LOCAL EXECUTION PASS"
```

## 5. Secret -> fake external message stops before sink

```bash
set +e
contextc mcp live plan execute "$PLANROOT/secret-to-message.json" \
  --server "$SERVER" --sandbox "$SANDBOX" --cache-root "$CACHE" \
  --audit-output "$ROOT/secret-audit.json" --json \
  > "$ROOT/secret-result.json"
RC=$?
set -e
echo "secret_plan_exit=$RC"
```

Expected `3`. Verify the source ran, sink did not, ledger stayed empty, and audit has no raw secret:

```bash
python - "$ROOT/secret-result.json" "$ROOT/secret-audit.json" "$SANDBOX/outbound-ledger.jsonl" <<'PY'
import json, pathlib, sys
p=json.load(open(sys.argv[1]))
audit=pathlib.Path(sys.argv[2]).read_text()
ledger=pathlib.Path(sys.argv[3]).read_text()
print("decision:", p["decision"])
print("invoked:", p["invoked_call_ids"])
print("blocked:", p["blocked_call_ids"])
assert "read-secret" in p["invoked_call_ids"]
assert "send-message" in p["blocked_call_ids"]
assert ledger == ""
assert "CONTEXTC_TEST_SECRET_7F31" not in audit
assert p["synthetic_secret_reached_sink"] is False
print("PRE-SINK SECRET BLOCK PASS")
PY
```

Explain stored evidence without rerunning tools:

```bash
contextc mcp live explain "$ROOT/secret-result.json" --json | tee "$ROOT/secret-explain.json"
```

## 6. Untrusted -> fake execution and credential -> fake network

```bash
set +e
contextc mcp live plan execute "$PLANROOT/untrusted-to-execution.json" --server "$SERVER" --sandbox "$SANDBOX" --cache-root "$CACHE" --json > "$ROOT/untrusted.json"
U=$?
contextc mcp live plan execute "$PLANROOT/credential-to-network.json" --server "$SERVER" --sandbox "$SANDBOX" --cache-root "$CACHE" --json > "$ROOT/credential.json"
C=$?
set -e
printf 'untrusted_exit=%s credential_exit=%s\n' "$U" "$C"
test ! -s "$SANDBOX/execution-ledger.jsonl" && echo "NO FAKE EXECUTION SINK: PASS"
test ! -s "$SANDBOX/network-ledger.jsonl" && echo "NO FAKE NETWORK SINK: PASS"
```

## 7. Declaration mismatch

```bash
set +e
contextc mcp live plan execute "$PLANROOT/misdeclared-reader.json" --server "$SERVER" --sandbox "$SANDBOX" --cache-root "$CACHE" --json > "$ROOT/mismatch.json"
M=$?
set -e
echo "mismatch_exit=$M"
grep -q CTX445 "$ROOT/mismatch.json" && echo "CTX445 MISMATCH PASS"
```

## 8. Traversal/symlink/timeout/failure are automated against the real SDK

```bash
pytest -q tests/live_mcp/test_m10b_live_sdk.py -vv
```

This covers real stdio lifecycle, discovery/read/call, trusted approval of only fake sinks, traversal refusal, bounded timeout, connection/resource failures, declaration hash stability, and source-level denial of real network/shell APIs.

## 9. Cache and determinism

```bash
contextc cache --root "$CACHE" verify --json
contextc mcp live plan analyze "$PLANROOT/secret-to-message.json" --server "$SERVER" --sandbox "$SANDBOX" --cache-root "$CACHE" --json > "$ROOT/static-1.json" || true
contextc mcp live plan analyze "$PLANROOT/secret-to-message.json" --server "$SERVER" --sandbox "$SANDBOX" --cache-root "$CACHE" --json > "$ROOT/static-2.json" || true
```

The second static manifest should report capability-cache reuse and unchanged semantic declarations.

## 10. Full gate

```bash
cd ~/Desktop/context-compiler-partial-recovery/context-compiler-m10b
pytest -q
pytest --cov=contextc --cov-report=term-missing --cov-fail-under=85
ruff check .
ruff format --check .
mypy --strict contextc
```

Do not declare M10b complete until the real SDK tests and the full gate pass on the Mac.
