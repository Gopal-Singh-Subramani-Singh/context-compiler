# Security

## M1 boundary

M1 repository indexing is static: it reads bytes and uses `ast.parse` for Python. It does not
import modules, execute repository code, invoke tools, contact services, or follow source
symlinks. Size, binary-content, and UTF-8 policies are explicit.

The trust-domain, sensitivity, and instruction-authority fields introduced in M1 remain
immutable source facts. M9 consumes those facts through a separate policy layer; source text
cannot mutate its own trust or authority merely by claiming a higher role.

Report vulnerabilities privately to the project maintainers. Do not include live secrets or
sensitive repository content in a report.


## M9 structural security analysis

M9 adds deterministic, bounded structural trust/policy/taint analysis over retained inputs. It
is a static-analysis boundary, not a complete prompt-injection-prevention system. Static
MCP-shaped results are parsed without transport, authentication, discovery, network access, or
tool execution. Tool output has no instruction authority by default. Security analysis runs
before task analysis and selection. Quote/redact transformations are re-tokenized before
optimization, exclusions remain in the structural graph but are optimizer-ineligible, and a
blocking decision aborts before the artifact transaction begins. Successful manifests retain
secret-safe policy, diagnostic, taint, transformation, exclusion, and token-delta evidence so
verification and rebuild can reproduce the same security semantics. Sensitive transformations
record rule identifiers without retaining raw secret payloads in diagnostic evidence.

## M8 cache safety

Cache metadata stores semantic identities, dependencies, stage names, and source URIs, not raw source content. Source-content cache objects store content identities rather than bytes. Raw adapted graph payloads are not persisted when any source is classified `secret`; reusable security results contain the deterministic transformed/redacted nodes. Corrupt or incompatible cache entries are rejected and quarantined before recomputation. The cache is never an authority for security policy or reproduction.


## M10a static capability analysis

M10a analyzes declared tool/resource capabilities and proposed call composition before runtime.
It never invokes a tool or contacts an MCP server. CTX440-CTX444 evidence is separate from M9
content-flow diagnostics. Incomplete declarations are not assumed safe. Explicit approvals are
trusted, flow-scoped inputs identified by semantic identity; an approval for one flow does not
approve another. Capability cache keys may hash plan semantics, but cached manifests omit literal
input payloads, credentials, and secret resource contents.

## M10b live MCP validation boundary

M10b uses a maintained MCP SDK only when the optional `live-mcp` extra is installed. The supported live mode is deliberately narrow: a marked local fixture server, stdio transport, a disposable sandbox, synthetic secrets, and policy-gated fixture execution. Arbitrary remote MCP servers are not an M10b execution target.

The child process receives a sandbox HOME and only the environment required for the fixture. Fixture file access rejects absolute paths, parent traversal, and resolved symlink escapes. Fixture sink tools simulate external messaging, shell execution, and network sending by writing local ledgers only. No real shell command, external message, network request, or real credential access is permitted by the fixture implementation.

Live declarations do not become trusted instructions. Runtime tool output enters the existing M9 model with ordinary tool-result provenance and `InstructionAuthority.NONE`. M10a static capability analysis runs before dangerous sink invocation. M10b correspondence mismatch emits CTX445 and blocks continuation. Persistent live audit/observation evidence excludes raw synthetic secret values.

Telemetry remains disabled; M10b transmits no validation data externally.

## M16 release-demo boundary

The M16 Observatory and four packaged release demos are read-only presentation/validation paths.
They do not invoke MCP tools, shells, real network sinks, credentials, or external message systems.
The capability-composition demo is static M10a analysis only. The incident demo may contain
malicious-looking fixture text so that M9 diagnostics can be demonstrated, but evaluator-only
sentinels and real secrets are excluded from release distributions.
