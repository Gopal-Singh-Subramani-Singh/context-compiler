# Contributing

## Development expectations

Changes should preserve the compiler's core invariants:

- deterministic output for deterministic inputs/settings
- provenance preservation
- explicit trust/sensitivity handling
- security before lowering/tool sinks
- incremental/full equivalence
- reproduction verification
- no silent suppression of conflicting evidence

## Recommended local checks

Run the project's configured quality gates from the repository root. The certified v0.18.0 baseline used:

- pytest
- coverage
- Ruff lint
- Ruff formatting check
- strict mypy

Use the exact project commands in `pyproject.toml`/project tooling for the checkout you are modifying.

## Tests

Add or update tests for:

- parsing/IR changes
- optimizer/budget changes
- security diagnostics/transformations
- capability policy behavior
- live MCP correspondence
- incremental cache invalidation
- reproduction/tamper detection

## Security changes

Security behavior should be accompanied by explicit fixtures and assertions for both positive and negative controls. Do not relax a failing acceptance check solely to make a scenario pass; preserve the original failure and adjudicate with a predeclared stronger correctness test when needed.

## Documentation

If a public CLI surface changes, update:

- `README.md`
- `docs/CLI_REFERENCE.md`
- relevant feature document
- release notes
