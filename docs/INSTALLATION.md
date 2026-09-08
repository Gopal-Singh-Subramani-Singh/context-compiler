# Installation

## Requirements

- Python 3.11 is the validated runtime used for the certified v0.18.0 campaign.
- A standard Python package installer: `pipx`, `uv`, or `pip`.
- Optional: Ollama for the local-model demo.
- Optional: MCP SDK/runtime dependencies are included according to the package dependency set used by the v0.18.0 environment.

## Recommended installation model

Context Compiler is a command-line application. For that reason, an isolated tool installer is preferable to installing directly into a global Python environment.

### pipx

```bash
pipx install ./context_compiler-0.18.0-py3-none-any.whl
contextc version
contextc --help
```

### uv

```bash
uv tool install ./context_compiler-0.18.0-py3-none-any.whl
contextc version
```

### pip

Use a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install ./context_compiler-0.18.0-py3-none-any.whl
contextc version
```

## Installing from the source distribution

```bash
python3 -m pip install ./context_compiler-0.18.0.tar.gz
```

The wheel is normally preferred because it is the direct install artifact produced for this release.

## Installing from a GitHub Release

Download both the wheel and its checksum from the release, then verify before installing.

macOS/Linux:

```bash
shasum -a 256 context_compiler-0.18.0-py3-none-any.whl
```

Expected:

```text
dcee2e233f6ea16101581815a3a634ae6eddb56589783908cc6d1bc9dc678ed3
```

Then:

```bash
pipx install ./context_compiler-0.18.0-py3-none-any.whl
```

## Future PyPI install

If v0.18.0 or a later release is published to PyPI under the project name `context-compiler`:

```bash
pipx install context-compiler
```

or:

```bash
uv tool install context-compiler
```

Do not document PyPI availability until the package is actually published.

## Verify the installation

```bash
contextc version
contextc --help
```

Expected version:

```text
0.18.0
```

## Uninstall

pipx:

```bash
pipx uninstall context-compiler
```

uv:

```bash
uv tool uninstall context-compiler
```

pip:

```bash
python3 -m pip uninstall context-compiler
```
