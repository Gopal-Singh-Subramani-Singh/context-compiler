# ADR 0009: Monotonic repository source-fact rules

## Status

Accepted for cumulative v0.14.0.

## Context

M9 modeled trust domain, sensitivity, and instruction authority as immutable source facts, but the
repository adapter always emitted `local_repository`, `internal`, and `none`. This prevented real
filesystem acceptance of secret redaction and external/retrieved source classification without
constructing nodes in tests.

## Decision

Add ordered `source_rules` to `contextc.toml` / `[tool.contextc]`. Rules match repository-relative
paths and are applied before M9 security analysis. Later matching rules override earlier matching
rules only for facts they explicitly set.

Because repository configuration is itself repository-controlled, the rule surface is monotonic:
trust may remain local or be downgraded to `external_content`, `retrieved_document`, or
`unverified_tool`; sensitivity may remain internal or increase to sensitive/secret; instruction
authority may not be granted. Privileged trust promotion and public declassification are rejected.

The ordered rules participate in pipeline identity and are stored in reproduction build inputs.

## Consequences

Real files can now drive CTX410 redaction and source-domain-specific policies through normal CLI
compilation. A malicious checkout cannot use `contextc.toml` to grant itself privileged authority.
Changing source classification changes the reproducible source semantics and causes verification to
fail until a new build is produced.
