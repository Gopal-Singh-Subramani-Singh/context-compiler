# ADR 0004: Commit the manifest last and rebuild from recorded semantic inputs

- Status: Accepted
- Date: 2026-08-29

## Context

Writing a final artifact and then attempting to create its evidence can leave an unauditable
success-looking file. Conversely, copying an artifact during “reproduction” proves only that
bytes can be copied. M4 needs failure-safe local writes, a stable identity independent of machine
paths, read-only verification, and actual deterministic recompilation.

## Decision

Artifact and manifest form one protocol-level transaction in a shared directory. Both are staged
and flushed; the artifact is replaced first; the manifest is replaced last as the commit marker;
the directory is flushed. Handled failures restore prior bytes and clean the two staging paths.
A pair is valid only when the manifest schema and artifact digest verify.

The manifest uses strict schema 1.0 and separates pretty serialization from canonical semantic
identity. Operational relative source/artifact paths are excluded from `build_id`. Explicit task,
source graph/node, analysis, policy/configuration, tokenizer, budget/trim, selection/optimizer,
compiler, random-seed, diagnostic, and artifact evidence is recorded.

Verify mode never rebuilds. Rebuild mode re-executes the compiler from recorded inputs and source,
compares every semantic field plus bytes/order/count/identities, and commits only an exact fresh
result. Model-target rebuilds require an immutable tokenizer revision.

## Consequences

Failed expected builds cannot replace a previous verified pair or leave a new valid-looking pair.
Moving a pair does not change semantic identity. Rebuild incompatibilities and mismatches fail
before destination commit with typed CTX600, CTX610, CTX710, or CTX720 evidence.

The protocol uses two atomic replacements rather than claiming a nonexistent portable two-file
filesystem syscall. The manifest commit marker and digest check define validity between those
replacements. Arbitrary power-loss recovery and cross-directory transactions are intentionally
outside this milestone.
