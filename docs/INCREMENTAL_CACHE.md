# Incremental Cache and Invalidation

## Goal

Incremental mode reuses valid stage outputs while preserving equivalence with a clean/full build.

## Basic use

```bash
contextc compile ./repo \
  --source-adapter repository \
  --task "Understand checkout_total behavior" \
  --target generic \
  --token-budget 400 \
  --incremental \
  --verify-incremental \
  --cache-root .contextc-cache \
  --output compiled.txt \
  --json > compile.json
```

## Warm reuse

In validated unchanged warm-cache behavior, the second build reused work such as:

- source content
- parse
- security
- token count
- analysis
- supersession

while selection/lowering were recomputed as required by the implementation. Incremental/full equivalence remained true and artifact bytes were identical.

## Selective source invalidation

After a bounded edit to one copied source file, the compiler recomputed that source's content and analysis while reusing unaffected source work such as the README. Restoring the source restored the original artifact exactly.

## Dependency-aware invalidation

Plan an invalidation:

```bash
contextc cache --root .contextc-cache \
  plan-invalidation \
  --source repo:///leaf.py \
  --json
```

Dry run:

```bash
contextc cache --root .contextc-cache \
  invalidate \
  --source repo:///leaf.py \
  --dry-run \
  --json
```

Apply:

```bash
contextc cache --root .contextc-cache \
  invalidate \
  --source repo:///leaf.py \
  --apply \
  --json
```

The output includes root key identities and an affected-key closure.

## Deep dependency adjudication

A real deep-leaf content mutation (`0.10 -> 0.15`) was used to adjudicate the final dependency test. The compiler:

- produced a dependency-aware invalidation closure
- recomputed the changed leaf
- recomputed dependency-sensitive global stages including parse, supersession, security, selection and lowering
- reused unchanged source content
- reported incremental/full equivalence with no differences
- produced a changed incremental artifact byte-identical to a clean changed build
- produced a changed artifact different from the original
- verified the cache as structurally valid

## Verify cache integrity

```bash
contextc cache --root .contextc-cache verify --json
```

A healthy validated cache returned:

```json
{
  "problems": [],
  "valid": true
}
```
