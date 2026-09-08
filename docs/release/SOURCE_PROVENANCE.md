# GitHub-ready source provenance

This public repository layout was assembled from the certified Context Compiler v0.18.0 source archive and the public documentation bundle.

Certified source archive:

```text
context-compiler-m16-v0.18.0-FINAL.zip
SHA-256 da73bceb14c265097e8d622af58e8164a77800ae1fe34003aa0efa56f0327f15
```

Documentation bundle:

```text
context-compiler-docs-v0.18.0.zip
SHA-256 8d2a500f66a21511f45bf4bb484fd6aad1889ea71b930abf70c83be7af7f4f9d
```

Assembly changes are documentation/presentation only:

- the top-level directory is renamed from `context-compiler-m16` to `context-compiler` for GitHub publishing;
- the public v0.18.0 README replaces the milestone-oriented root README;
- the certified-source README is preserved as `docs/reference/README_CERTIFIED_SOURCE.md`;
- the original installation guide is preserved as `docs/reference/INSTALLATION_CERTIFIED_SOURCE.md`;
- comprehensive public docs and UI snapshots are added under `docs/`.

The Python package implementation under `contextc/`, the test suite, examples, tooling, `pyproject.toml`, `uv.lock`, `MANIFEST.in`, and CI workflow are copied from the certified source archive without edits.
