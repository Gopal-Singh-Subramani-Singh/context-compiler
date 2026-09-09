# Packaging and Release

## Distribution format

Context Compiler v0.18.0 is packaged as a standard Python project with:

- a wheel (`.whl`)
- a source distribution (`.tar.gz`)
- the `contextc` CLI entry point

`pip`, `pipx` and `uv` are installers; they are not the package itself.

## Certified artifacts

```text
context_compiler-0.18.0-py3-none-any.whl
SHA-256 dcee2e233f6ea16101581815a3a634ae6eddb56589783908cc6d1bc9dc678ed3

context_compiler-0.18.0.tar.gz
SHA-256 b3835de6c5ca2045475630c3f4130d14d88fd3462809e3ee954341fc8caff2ea
```

The clean source archive:

```text
context-compiler-m16-v0.18.0-FINAL.zip
SHA-256 da73bceb14c265097e8d622af58e8164a77800ae1fe34003aa0efa56f0327f15
```

## GitHub repository

The GitHub repository root should contain the **contents** of the certified clean source tree, not the outer recovery directory and not the production-validation directory.

Typical root:

```text
context-compiler/
├── README.md
├── pyproject.toml
├── uv.lock
├── contextc/
├── tests/
├── examples/
└── docs/
```

Do not commit:

```text
.venv/
__pycache__/
.pytest_cache/
.mypy_cache/
.ruff_cache/
build/
dist/
local validation sandboxes/caches
```

## GitHub Release assets

Attach the wheel and source distribution to the `v0.18.0` GitHub Release rather than placing them at repository root.

Suggested release assets:

```text
context_compiler-0.18.0-py3-none-any.whl
context_compiler-0.18.0.tar.gz
SHA256SUMS.txt
```

## PyPI

Only document `pipx install context-compiler` as a public PyPI workflow after the project is actually published there.
