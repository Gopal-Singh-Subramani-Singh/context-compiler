# GitHub Release Checklist

## Repository upload

- [ ] Start from the certified clean v0.18.0 source tree.
- [ ] Repository root contains `pyproject.toml`, `README.md`, package source, tests and examples.
- [ ] Add this documentation bundle under `docs/`.
- [ ] Confirm `.venv`, caches, local validation outputs and recovery directories are excluded.
- [ ] Confirm no synthetic secret values or local machine paths appear in public docs/screenshots.

## Version and quality

- [ ] `contextc version` returns `0.18.0`.
- [ ] 364-test certified baseline is recorded.
- [ ] Ruff, formatting and strict mypy status documented.
- [ ] Release notes do not overstate production readiness.

## Release assets

- [ ] Attach `context_compiler-0.18.0-py3-none-any.whl`.
- [ ] Attach `context_compiler-0.18.0.tar.gz`.
- [ ] Publish SHA-256 sums.
- [ ] Tag release `v0.18.0`.

## Recommended screenshots

- [ ] Observatory home / demo gallery.
- [ ] Repository evidence selection.
- [ ] Incident security + supersession.
- [ ] Capability composition blocked pending approval.
- [ ] Incremental cache reuse.
- [ ] Explain/provenance view.
- [ ] One polished hero screenshot.

## Public claims

Use:

> Production-oriented, end-to-end validated release candidate; 20/20 adjudicated validation scenarios passed.

Do not claim:

- universal production readiness
- universal MCP safety
- model accuracy improvement
- latency improvement
- cost reduction without separate measurement
