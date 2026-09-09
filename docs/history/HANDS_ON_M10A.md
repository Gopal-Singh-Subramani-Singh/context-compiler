# M10a v0.16.0 hands-on acceptance

This checklist uses physical JSON declarations and proposed plans. It does **not** invoke a real
MCP server or execute any tool; that is a deliberate M10a boundary.

## 1. Environment

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
rehash 2>/dev/null || true
contextc version
pytest -q tests/capabilities
pytest -q
pytest --cov=contextc --cov-report=term-missing --cov-fail-under=85
```

Expected package version: `0.16.0`. On the accepted macOS/PuLP environment the cumulative test
target is 315 passing tests; record the actual result rather than assuming it.

## 2. Build a physical static declaration directory

```bash
ROOT=~/Desktop/m10a-real-world
rm -rf "$ROOT"
mkdir -p "$ROOT/declarations" "$ROOT/cache"
```

Create `declarations/all.json` with two tools and one secret resource:

```json
{
  "tools": [
    {
      "tool_id": "read_secret",
      "server_id": "local-files",
      "trust_domain": "verified_tool",
      "capabilities": ["local_file_read"],
      "resources_read": ["deployment-secret"],
      "resources_written": [],
      "possible_output_sensitivity": "internal",
      "side_effecting": false,
      "allows_execution": false,
      "allows_network": false
    },
    {
      "tool_id": "send_external",
      "server_id": "external-api",
      "trust_domain": "verified_tool",
      "capabilities": ["external_write"],
      "resources_read": [],
      "resources_written": [],
      "possible_output_sensitivity": "internal",
      "side_effecting": true,
      "allows_execution": false,
      "allows_network": true
    }
  ],
  "resources": [
    {
      "resource_id": "deployment-secret",
      "kind": "local_file",
      "sensitivity": "secret",
      "trust_domain": "local_repository",
      "allowed_sinks": ["local"],
      "allowed_actions": ["read"]
    }
  ]
}
```

Create `plan-sensitive.json`:

```json
{
  "schema_version": {"major": 1, "minor": 0},
  "plan_id": "sensitive-to-external",
  "calls": [
    {"call_id": "read", "tool_id": "read_secret"},
    {
      "call_id": "send",
      "tool_id": "send_external",
      "input_bindings": {"body": "call:read.output"}
    }
  ]
}
```

Validate and analyze:

```bash
contextc mcp plan validate "$ROOT/plan-sensitive.json" --tools "$ROOT/declarations" --json
contextc mcp plan analyze "$ROOT/plan-sensitive.json" --tools "$ROOT/declarations" \
  --cache-root "$ROOT/cache" --output "$ROOT/analysis.json" --json
```

The plan should validate structurally, then analysis should emit CTX440 + CTX443, state
`tool_execution_performed: false`, and return blocked/pending approval.

## 3. Explain the stored flow

```bash
FLOW=$(python - <<'PY'
import json
analysis_path = Path.home() / "Desktop" / "m10a-real-world" / "analysis.json"
p = json.loads(analysis_path.read_text())
print(p['flows'][0]['flow_identity'])
PY
)
contextc mcp plan explain "$ROOT/analysis.json" --flow "$FLOW" --json
```

The ordered path must show the protected source, `read`, `send`, then the external sink.

## 4. Explicit approval is flow scoped

Create `approval.json` using the exact flow identity printed above:

```json
{
  "approval_id": "acceptance-approval-1",
  "plan_id": "sensitive-to-external",
  "flow_identity": "REPLACE_WITH_FLOW_ID",
  "approver_identity": "user:acceptance",
  "approver_trust_domain": "user_instruction",
  "approved": true,
  "evidence_uri": "approval://acceptance/1"
}
```

Then rerun with `--approval`. The approved flow must carry the approval identity and CTX443 must
be absent for that exact flow. Supplying the same approval for a different flow/plan must emit
CTX444.

## 5. Warm cache and declaration invalidation

Run the same analyze command twice. The second result should report `cache_status: reused`.
Change one tool declaration (for example `possible_output_sensitivity`) and rerun; it must report
`cache_status: recomputed` with a different capability cache key. Existing repository parse cache
entries are unrelated and must remain untouched.

## 6. Untrusted output to execution

Create a plan whose first tool has `trust_domain: unverified_tool` / `external_read`, and whose
second tool has `shell_execution` with `allows_execution: true`, binding the first output to the
shell input. Expect CTX440 + CTX443 and no execution.

## 7. Credential/environment access to network send

Create a `credential_access` or `environment_read` tool followed by a `network_send` tool. The
default policy must detect `credential_to_network`, emit CTX440, and block it without treating an
approval for a different flow as sufficient.

## 8. Incomplete and invalid inputs

Remove required capability/sensitivity/resource declaration fields from a used tool and expect
CTX441. Bind a call to a future/unknown call output and expect CTX442. Contradict a declaration
(e.g. `shell_execution` with `allows_execution: false`) and expect CTX444.

## 9. Secret-safe cache evidence

Put a disposable canary only in a plan `literal_inputs` value, analyze with a cache root, then scan
`analysis.json`, diagnostics, and every cache file. The raw canary must not occur. M10a hashes the
plan for semantic identity but does not persist literal payload values in the capability manifest
or cache payload.

## 10. Final regression

```bash
cd /path/to/context-compiler-m10a
pytest -q tests/capabilities
pytest -q
```

No test or hands-on step should execute a real tool.
