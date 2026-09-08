# Context Compiler v0.18.0

Context Compiler turns heterogeneous source material into deterministic, policy-enforced, provenance-rich model input before inference.

This documentation bundle is intended to be dropped into the root of the public GitHub repository for the certified v0.18.0 source tree.

## Status

**Release status:** production-oriented, end-to-end validated release candidate.

The v0.18.0 validation campaign covered 20 scenarios across repository context selection, dependency handling, conflict and supersession, security policy, static capability analysis, live MCP enforcement, incremental caching, reproduction, tamper detection, and a local-model A/B evaluation. One original B4-18 harness assertion was preserved as a failure and then adjudicated with a stronger real leaf-content mutation test; the adjudication passed.

This does **not** establish universal production readiness across all operating systems, all MCP servers, fuzz/stress conditions, crash recovery, or every dependency ecosystem.

## Install

### Recommended: pipx from a downloaded wheel

```bash
pipx install ./context_compiler-0.18.0-py3-none-any.whl
contextc version
```

### With uv

```bash
uv tool install ./context_compiler-0.18.0-py3-none-any.whl
contextc version
```

### With pip

```bash
python3 -m pip install ./context_compiler-0.18.0-py3-none-any.whl
contextc version
```

Expected version:

```text
0.18.0
```

If the package is later published to PyPI as `context-compiler`, the install commands become:

```bash
pipx install context-compiler
# or
uv tool install context-compiler
# or
python3 -m pip install context-compiler
```

## First compile

```bash
contextc compile ./repo \
  --source-adapter repository \
  --task "Explain the checkout bug and retain the relevant implementation and tests" \
  --target generic \
  --token-budget 1200 \
  --output compiled-context.txt \
  --manifest compiled-context.manifest.json \
  --json > compile.json
```

Then inspect or reproduce the result:

```bash
contextc reproduce compiled-context.manifest.json --verify --json
```

## Documentation map

- [Installation](docs/INSTALLATION.md)
- [Quickstart](docs/QUICKSTART.md)
- [Architecture](docs/ARCHITECTURE.md)
- [CLI reference](docs/CLI_REFERENCE.md)
- [Security model](docs/SECURITY_MODEL.md)
- [MCP and capability enforcement](docs/MCP.md)
- [Incremental cache and invalidation](docs/INCREMENTAL_CACHE.md)
- [Reproduction and tamper detection](docs/REPRODUCTION.md)
- [Validation evidence](docs/VALIDATION.md)
- [Operations and deployment](docs/OPERATIONS.md)
- [Packaging and release](docs/PACKAGING_RELEASE.md)
- [GitHub release checklist](docs/GITHUB_RELEASE_CHECKLIST.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [Contributing](docs/CONTRIBUTING.md)
- [Glossary](docs/GLOSSARY.md)

## Distribution artifacts

Certified v0.18.0 artifacts:

```text
Wheel:
context_compiler-0.18.0-py3-none-any.whl
SHA-256 dcee2e233f6ea16101581815a3a634ae6eddb56589783908cc6d1bc9dc678ed3

Source distribution:
context_compiler-0.18.0.tar.gz
SHA-256 b3835de6c5ca2045475630c3f4130d14d88fd3462809e3ee954341fc8caff2ea

Clean source archive:
context-compiler-m16-v0.18.0-FINAL.zip
SHA-256 da73bceb14c265097e8d622af58e8164a77800ae1fe34003aa0efa56f0327f15

uv.lock:
SHA-256 f0635e6673fbf46c3ae67792f65c627c54afb81f5c2f59d9c87fceb8db5b91bd
```

## Product claim

A defensible summary for v0.18.0 is:

> Context Compiler is a production-oriented, end-to-end validated compiler prototype/release candidate that deterministically selects, transforms, secures, and records context before inference, with provenance, supersession, security policy, capability analysis, incremental caching, and reproduction evidence.
