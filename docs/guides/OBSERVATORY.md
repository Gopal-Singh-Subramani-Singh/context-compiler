# Local Observatory

The M16 Observatory is a local Streamlit presentation layer over typed Context Compiler services.
Compiler and static-analysis semantics do not live in Streamlit pages.

Start it with:

```bash
contextc ui
```

The default address is loopback only. The launcher disables Streamlit usage-stat collection and
runs headless. The Observatory has no paid API requirement and the release demos require no
network at runtime.

Views include:

- landing and four packaged demo cards;
- compile evidence with demo, target, strategy, and budget controls where applicable;
- typed graph nodes and edges;
- equal-footing comparison with raw M6 metrics;
- M4 verification and rebuild evidence;
- M9 trust, sensitivity, authority, diagnostics, taint, and transformations;
- M8 incremental cache/equivalence evidence;
- M10a capability flows and approval requirements.

The Observatory does not expose live MCP execution. M10b remains a separate bounded validation
facility outside the M16 release demos.
