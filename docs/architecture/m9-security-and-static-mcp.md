# M9 Security and Static MCP Architecture

M9 adds deterministic structural security analysis without turning the compiler into a live tool
runtime. Trust, sensitivity, and instruction authority remain immutable source facts on
`ContextNode`; policy interpretation and security decisions live under `contextc.security`.

## Compilation order

Normal repository compilation uses this order:

```text
static parse/index
  -> raw immutable ContextGraph
  -> SecurityService pattern + taint + policy analysis
  -> BLOCK? abort before artifact transaction
  -> apply quote/redact transformations
     (retain excluded nodes structurally)
  -> target-specific task analysis and node token costing
  -> optimizer with security-excluded nodes marked ineligible
  -> dependency closure / selection
  -> target lowering
  -> exact fully-rendered target recount
  -> transactional artifact + manifest commit
```

The raw graph remains the authoritative source/reproduction identity. Security transformations do
not rewrite source evidence; the post-security graph is a derived compilation view. This lets M4
verify current source bytes while M9 records exactly which deterministic transformations were
applied.

## Selection and dependency semantics

`EXCLUDE` does not delete a node from the structural graph. The node remains available to prove a
dependency relationship, but its ID is passed to the optimizer as policy-ineligible. If a
mandatory node requires an excluded dependency, compilation is infeasible rather than silently
reintroducing the excluded source.

`BLOCK_COMPILATION` and `REQUIRE_EXPLICIT_ALLOW` mark the security result blocked. Repository
compilation raises a typed security error before `write_artifact_transaction` is entered, so a
blocked build cannot create a valid artifact/manifest pair.

## Token semantics

Quote and redaction transforms change content. M9 therefore measures the transformed node with the
configured target tokenizer before optimizer selection. The manifest records before/after node
costs for changed nodes. M3's exact fully-rendered recount remains authoritative after lowering;
M9 never replaces it with an estimate.

## Manifest and reproduction evidence

Successful manifests store canonical, secret-safe M9 evidence:

- policy ID, version, and semantic identity;
- security analysis version;
- triggered rule IDs and diagnostic codes;
- decision action/node/rule and optional taint-path summary;
- excluded/blocked node IDs;
- immutable source trust domain, sensitivity, instruction authority, and source URI;
- taint path node/edge IDs;
- transformation identifiers;
- transformed-node token deltas and whether the node survived selection.

The raw matched pattern fragment and raw secret payload are not stored in security evidence.
`reproduce --verify` validates internal security identities and the committed artifact. `reproduce
--rebuild` reconstructs the stored security policy, reruns compilation from source, and requires
semantic-manifest and rendered-byte agreement before committing the fresh pair.

`explain --node` reads only stored manifest evidence. It does not rerun security analysis or the
optimizer.

## Static MCP boundary

The M9 MCP adapter parses retained JSON and creates stable `mcp://...` provenance. It accepts only
`TAINTS` and `ENABLES` flow edges. It performs no live connection, transport, server discovery,
authentication, capability invocation, or tool execution. Tool-result content receives
`instruction_authority = none` by default even when the text claims to be system/developer
instructions.

Capability composition and dangerous multi-tool planning are deliberately deferred to M10a.


## Real repository source-fact rules (v0.14.0)

Repository ingestion now accepts ordered project-local source classification rules from
`contextc.toml` or `[tool.contextc]`. Rules match POSIX repository-relative paths and set immutable
`trust_domain`, `sensitivity`, and (currently only explicit `none`) `instruction_authority` before
security analysis. Last matching rule wins per specified fact.

The project-local rule surface is deliberately monotonic: it can downgrade repository trust to
`external_content`, `retrieved_document`, or `unverified_tool` and raise sensitivity to `sensitive`
or `secret`; it cannot self-promote into system/developer/user/verified trust, declassify to
`public`, or grant instruction authority. This prevents an untrusted checkout from using its own
configuration as a privilege-escalation channel.

Ordered rule semantics are hashed into pipeline identity, stored in the build manifest, replayed
for source verification/rebuild, and exposed through stored evidence. The configuration file itself
is still ordinary repository source, so editing classification config invalidates source identity.
