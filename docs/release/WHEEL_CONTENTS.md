# Wheel contents

The 0.18.0 wheel intentionally contains:

- Context Compiler Python packages and `py.typed`;
- Apache-2.0 license metadata;
- default M9 security policy and bounded static security fixtures;
- default M10a capability policy;
- four M16 release-demo resources and deterministic registry metadata;
- public incident data retained for compatibility;
- M10b static plan JSON used by the bounded live-MCP feature;
- Observatory Python modules, with Streamlit itself remaining optional.

The release wheel intentionally excludes:

- the M11 vendored Git bundle and evaluator task labels;
- controlled benchmark fixture trees;
- evaluator-only incident labels and sentinels;
- tests;
- virtual environments and bytecode caches;
- compiler cache and quarantine state;
- coverage/build outputs.
