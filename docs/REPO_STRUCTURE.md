# Public repository structure

The GitHub repository root is this directory (`context-compiler/`). Do not add another wrapper directory such as `context-compiler-m16/` when publishing.

```text
context-compiler/
├── README.md
├── LICENSE
├── CHANGELOG.md
├── CONTRIBUTING.md
├── SECURITY.md
├── pyproject.toml
├── uv.lock
├── MANIFEST.in
├── .gitignore
├── .github/
│   └── workflows/
├── contextc/                 # installable Python package
├── tests/                    # test suite
├── examples/                 # user-facing examples
├── tools/                    # repository tooling
└── docs/
    ├── README.md
    ├── INSTALLATION.md
    ├── QUICKSTART.md
    ├── ARCHITECTURE.md
    ├── CLI_REFERENCE.md
    ├── SECURITY_MODEL.md
    ├── MCP.md
    ├── INCREMENTAL_CACHE.md
    ├── REPRODUCTION.md
    ├── VALIDATION.md
    ├── OPERATIONS.md
    ├── PACKAGING_RELEASE.md
    ├── GITHUB_RELEASE_CHECKLIST.md
    ├── TROUBLESHOOTING.md
    ├── GLOSSARY.md
    ├── assets/screenshots/
    ├── architecture/
    ├── adr/
    ├── release/
    └── reference/
```

Do not commit local virtual environments, caches, build output, or the production-validation workspace. The project's `.gitignore` already excludes the main local build/cache directories.

Built `.whl` and `.tar.gz` artifacts belong on the GitHub Release page (and later PyPI), not in the normal source tree.
