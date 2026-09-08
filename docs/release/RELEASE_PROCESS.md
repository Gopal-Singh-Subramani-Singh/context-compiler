# Release process

1. Regenerate and check release-demo integrity metadata.
2. Run the full quality and regression gates.
3. Regenerate `uv.lock` and require `uv lock --check` to pass.
4. Build wheel and sdist from a clean tree.
5. Run distribution metadata checks and the release audit.
6. Install the core wheel in an unrelated working directory and run all release demos.
7. Install the UI extra from the wheel, start the loopback Observatory, and check local health.
8. Build distributions twice and record byte/member/content comparison results honestly.
9. Record exact hashes and acceptance evidence in the acceptance report and BUILD_STATE.
10. Run the separate final acceptance prompt before creating any release tag.
