# Limitations

M16 adds presentation, packaging, and release validation. It does not change compiler semantics.

The four release demos are deliberately small and are not substitutes for the full M6 benchmark,
M11 development case study, M15 evaluation labels, M8 stress coverage, or M10b live-MCP suite.

Security analysis is structural and policy-based. It does not guarantee prevention of every
prompt-injection, exfiltration, runtime-tool, or malicious-server behavior.

The Observatory is a local single-user viewer. It is not a multi-tenant service, authorization
system, production MCP gateway, hosted dashboard, or remote execution console.

Model-specific Qwen/Llama targets still require their optional tokenizer dependencies and pinned
local model-tokenizer data for exact operation. M16 release demos avoid model downloads.

Package reproducibility is reported from measured distribution comparisons. In the author
environment, repeated 0.18.0 wheel/sdist builds had identical member lists and identical per-member
content hashes but were not byte-identical because archive metadata records build-time timestamps.
Compiler artifact reproduction from M4 is a separate, stronger semantic requirement and remains
mandatory.

Legacy development demo/evaluator commands may require checkout-only benchmark/evaluator resources
that are intentionally excluded from the release wheel. Installed-wheel users should use the four
`contextc demo registry` release demos for the supported packaged demonstrations.
