# Contributing

Work on one accepted milestone at a time. Preserve all earlier contracts and record exact
commands and outcomes in `BUILD_STATE.md`.

Every public contract requires tests. Do not weaken tests to make a gate pass, rely on unordered
iteration for semantics, execute indexed repository code, import optional dependencies during
core startup, or place task analysis and selection state on immutable source IR.

Before proposing a change, run the commands documented in the README. Material architectural
choices require an ADR in `docs/adr/`.

