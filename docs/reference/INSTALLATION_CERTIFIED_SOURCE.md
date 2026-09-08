# Installation

Context Compiler 0.18.0 supports a dependency-light core install and optional feature extras.

## Core

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install context_compiler-0.18.0-py3-none-any.whl
contextc version
contextc demo registry verify
```

The core install does not require Streamlit, model downloads, live MCP, network access at runtime,
or paid APIs.

## Observatory

Install the wheel with the `ui` extra:

```bash
python -m pip install 'context-compiler[ui]'
contextc ui
```

The Observatory binds to `127.0.0.1:8501` by default. Override the loopback port with
`contextc ui --port PORT`. Binding to a non-loopback address is an explicit operator choice.

## Other optional features

The `live-mcp`, `ilp`, `tokenizers`, `qwen`, `llama`, and `embeddings` extras remain separate.
M16 release demos do not require them.
