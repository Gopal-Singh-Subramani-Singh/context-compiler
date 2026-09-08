# Glossary

**Artifact** — Final compiled model-input file emitted by Context Compiler.

**Build identity** — Deterministic identity associated with a compilation/rebuild result.

**Capability flow** — A path from a source/resource/tool output through planned calls to a sink, annotated with risk kind, trust, sensitivity and capabilities.

**Compiled context** — The final selected/transformed text sent toward inference.

**Dependency-forced selection** — Evidence retained because graph/dependency correctness requires it, even if it was not selected independently.

**Diagnostic** — Structured code such as `CTX420` or `CTX443` describing a compiler/security/policy condition.

**Flow identity** — Deterministic identity for an enumerated capability flow; approvals are scoped to this value.

**IR** — Intermediate representation used to model normalized source evidence and metadata before lowering.

**Lowering** — Conversion from selected/transformed IR/evidence into final model-input form.

**Manifest** — Reproduction metadata connecting source graph, artifact identity and build information.

**MCP** — Model Context Protocol; used here for discovered tool/resource capabilities and live stdio enforcement.

**Optimizer** — Evidence-selection strategy used to satisfy a token budget and constraints.

**Provenance** — Where an evidence item came from and how it relates to its source.

**Sensitivity** — Classification such as public, internal, sensitive or secret.

**Sink** — Destination such as local, external, message, network or execution path.

**Supersession** — Explicit relationship where newer guidance replaces stale guidance.

**Taint path** — Security-tracked path from an untrusted/sensitive source toward an instruction or external sink.

**Trust domain** — Security classification describing the authority/trust boundary associated with a source or approver.
