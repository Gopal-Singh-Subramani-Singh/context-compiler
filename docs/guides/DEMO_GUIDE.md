# Packaged release demos

M16 ships four bounded offline demonstrations registered as package resources.

```bash
contextc demo registry list
contextc demo registry verify
contextc demo verify --all
contextc demo run repository-bug
contextc demo run incident-response
contextc demo run incremental-rebuild
contextc demo run capability-composition
```

## repository-bug

A reduced pre-fix snapshot for the M11 python-humanize empty `natural_list` task. It preserves the
historical task and source revision needed for the release demonstration without shipping the full
Git history. It exercises compilation, equal-footing strategy comparison with raw M6 metrics, and
M4 verify/rebuild evidence.

## incident-response

A public-only M15-style incident fixture. It exercises typed relationships, supersession,
structural security diagnostics, selection, and M4 reproduction. Evaluator-only labels and
sentinels are not release resources.

## incremental-rebuild

A tiny repository is copied into a temporary directory, compiled cold, changed deterministically,
and compiled incrementally. The demo reports cache reuse/recomputation and verifies that the
incremental result is equivalent to a clean build.

## capability-composition

A static M10a plan reads a sensitive local resource and feeds an external message sink. The demo
reports dangerous-flow and approval evidence. It never invokes either declared tool.

All demos materialize packaged resources into temporary directories before compilation. They do
not mutate wheel resources or depend on the source checkout.
