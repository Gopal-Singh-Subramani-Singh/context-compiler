# M16 acceptance report

Status: **candidate; final Mac acceptance not yet complete**.

## Author-environment evidence

- M16 release/CLI/Observatory boundary tests: **13 passed**, with one additional Streamlit AppTest
  skipped because Streamlit is unavailable in the author container;
- four-demo registry integrity and deterministic generated metadata: **PASS**;
- semantic verification and direct execution of all four release demos: **PASS**;
- release demos with Python socket network denied: **PASS**;
- predecessor focused matrix: M4 22 pass, M6 19 pass, M11 9 pass, M9 24 pass, M15 23 pass,
  M8 28 pass, M10a 35 pass, M10b SDK-independent 24 pass with its real-SDK module skipped;
- cumulative author suite after M16: **345 passed, 5 failed, 4 skipped**. The five failures and
  two M5 skips are the inherited unavailable-PuLP outcomes; one skip is the unavailable real MCP
  SDK module; one skip is the unavailable Streamlit AppTest. No runnable M16/predecessor semantic
  regression remains;
- wheel and sdist build through the local setuptools backend: **PASS**;
- wheel and sdist release audit: **PASS**;
- final author-core wheel isolation from an unrelated working directory: **PASS**; version
  0.18.0, registry list/verify, `demo verify --all`, and all four demo runs succeeded with the
  checkout absent from `sys.path`; core-only `contextc ui` returned the expected `[ui]` guidance;
- package reproducibility comparison: repeated builds are **not byte-identical**, but archive
  member lists and all per-member content identities are identical. The measured wheel difference
  is timestamps on six generated `.dist-info` members out of 226 wheel files. The measured sdist
  difference is build-time `mtime`/PAX metadata on 78 of 352 total archive members plus the gzip
  header timestamp; all 282 sdist file contents are identical.
- author `uv lock --check --offline`: **not certifiable** because required registry packages are not
  cached in this network-disabled container; the checked lock is therefore deliberately not claimed
  current for 0.18.0.

## Still required before M16 completion

- install `.[dev,live-mcp,ui]` on the Mac release environment and regenerate/check `uv.lock`;
- run the full dependency-complete suite (expected target **364 passing tests**) and coverage >=85%;
- Ruff, Ruff format, and strict mypy on the exact candidate;
- frozen-lock install proof for 0.18.0;
- installed UI-extra startup, loopback health check, and four-card Streamlit AppTest;
- final clean-build predecessor matrix including the 11 real M10b SDK tests;
- `python -m build`, `twine check`, final release audit, and installed-wheel isolation on the
  Mac-built distributions;
- repeat the twice-built distribution comparison on the final Mac toolchain and record the result
  honestly;
- record final wheel/sdist/source-archive hashes externally after packaging.

M16 introduces no new compiler semantics. Do not create a release tag before the separate final
acceptance prompt passes.

## Final macOS certification

Status: **MILESTONE 16 COMPLETE**

This section supersedes the earlier author-environment limitations and outstanding Mac-gate list
above.

Final release acceptance:

- cumulative dependency-complete tests: **364 passed**;
- coverage: **85.50%**;
- Ruff: **PASS**;
- Ruff formatting: **PASS — 289 files**;
- strict mypy: **PASS — 164 source files**;
- fresh `uv.lock`: **140 packages**, `uv lock --check` PASS;
- external non-editable frozen environment: **PASS**;
- frozen regression/coverage/static-quality gates: **PASS**;
- all four packaged release demos: registry integrity, semantic verification, and direct runs PASS;
- offline/no-execution release-demo constraint: PASS;
- hands-on Observatory views: PASS;
- final core-wheel checkout isolation: PASS;
- core-only optional Streamlit boundary: PASS;
- final `[ui]` wheel checkout isolation: PASS;
- installed Streamlit AppTest: **0 exceptions**, all four demo cards present;
- final wheel/sdist build: PASS;
- Twine checks: PASS;
- distribution release audit: PASS.

Authoritative identities:

- `context_compiler-0.18.0-py3-none-any.whl`
  SHA-256 `dcee2e233f6ea16101581815a3a634ae6eddb56589783908cc6d1bc9dc678ed3`
- `context_compiler-0.18.0.tar.gz`
  SHA-256 `b3835de6c5ca2045475630c3f4130d14d88fd3462809e3ee954341fc8caff2ea`
- `uv.lock`
  SHA-256 `f0635e6673fbf46c3ae67792f65c627c54afb81f5c2f59d9c87fceb8db5b91bd`

Wheel/sdist byte-for-byte reproducibility is not claimed. Independent author builds showed
identical members and per-member content hashes with archive-level timestamp/mtime differences.

Final M16 completion is contingent only on the clean cumulative source-archive inspection.
