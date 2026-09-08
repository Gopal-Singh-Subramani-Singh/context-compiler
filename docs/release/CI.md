# CI layout

The M16 workflow defines jobs for quality, unit/integration, baseline demos, package, installed
core, installed UI, release security, and a clean-build regression matrix.

Quality runs Ruff, Ruff format check, and strict mypy. Unit/integration runs the full pytest suite
with the 85% coverage floor. Baseline demos verifies the generated registry and all four packaged
demos.

Package builds wheel and sdist and checks distribution metadata. Installed-core and installed-UI
jobs operate from built wheels rather than the source checkout. The installed-UI job checks the
loopback Streamlit health endpoint and then uses Streamlit AppTest against the installed wheel to
assert that all four release-demo cards render without exceptions. Release-security audits wheel
and sdist contents. Clean-build deletes compiler/build caches before selected predecessor
regressions.

The workflow must not rely on compiler cache state for correctness.
