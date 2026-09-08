# Reproduction and Tamper Detection

## Why manifests matter

A compiled artifact is accompanied by a manifest that records enough source/build identity to detect later drift.

## Verify an existing artifact

```bash
contextc reproduce compiled.manifest.json --verify --json
```

A successful verification reports a verified status and the artifact identity.

## Rebuild from the manifest

```bash
contextc reproduce compiled.manifest.json \
  --rebuild \
  --output rebuilt.txt \
  --json
```

The v0.18.0 validation demonstrated byte-identical rebuild output for the tested scenario.

## Artifact tamper detection

If the artifact bytes change after compilation, verification rejects the mismatch with:

```text
CTX610 reproduction mismatch
```

The validated tamper test returned exit code `2` and reported current vs stored artifact identities.

## Source tamper detection

If the underlying source graph changes, verification rejects the source mismatch with:

```text
CTX600 manifest/source mismatch
```

The validated test reported source graph identity and node content identity differences.

## Recommended release workflow

1. Compile and write a manifest.
2. Store artifact + manifest together.
3. Record SHA-256 checksums externally.
4. Before reusing an old artifact, run `contextc reproduce ... --verify`.
5. If verification fails, treat the artifact as stale/untrusted until rebuilt from known source.
