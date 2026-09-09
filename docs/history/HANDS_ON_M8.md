# Hands-on M8 acceptance — v0.15.0

Use an isolated materialization of the real tracked `humanize` checkout plus the real incident directory created during M15 acceptance. Keep outputs and cache roots outside source roots. This avoids the untracked M9 `contextc.toml`, `external-notes/`, and `private/` test files changing M8 cache behavior.

## 1. Install and baseline

```bash
cd ~/Desktop/context-compiler-partial-recovery/context-compiler-m8
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools
python -m pip install -e '.[dev]'
rehash 2>/dev/null || true
contextc version
pytest -q
```

Expected on the Mac environment that already has PuLP 3.3.2: `0.15.0` and 280 passing tests.

## 2. Real repository full -> no-op incremental

Materialize only the tracked bytes from the already-cloned real repository; do not mutate the M9 acceptance checkout itself:

```bash
SOURCE=~/Desktop/m9-real-world/humanize
REAL=~/Desktop/m8-real-world/humanize
rm -rf ~/Desktop/m8-real-world
mkdir -p "$REAL"
git -C "$SOURCE" archive HEAD | tar -x -C "$REAL"
cd "$REAL"

CACHE=../cache
OUT=../outputs
rm -rf "$CACHE" "$OUT"
mkdir -p "$OUT"

contextc compile . \
  --task 'understand number and date humanization behavior' \
  --target generic \
  --token-budget 2500 \
  --time-anchor 2026-09-04T00:00:00Z \
  --output "$OUT/full.txt"

contextc compile . \
  --task 'understand number and date humanization behavior' \
  --target generic \
  --token-budget 2500 \
  --time-anchor 2026-09-04T00:00:00Z \
  --output "$OUT/incremental-1.txt" \
  --incremental --verify-incremental --cache-root "$CACHE" --json \
  | tee "$OUT/incremental-1.json"

contextc compile . \
  --task 'understand number and date humanization behavior' \
  --target generic \
  --token-budget 2500 \
  --time-anchor 2026-09-04T00:00:00Z \
  --output "$OUT/incremental-2.txt" \
  --incremental --verify-incremental --cache-root "$CACHE" --json \
  | tee "$OUT/incremental-2.json"
```

The second incremental JSON must report `incremental_equivalence.equivalent=true` and real reused `parse`, `security`, `supersession`, `token_count`, and `analysis` stages.

## 3. One actual source mutation and selective reuse

```bash
cp src/humanize/number.py "$OUT/number.py.before"
printf '\n# M8 temporary real-source mutation\n' >> src/humanize/number.py

contextc compile . \
  --task 'understand number and date humanization behavior' \
  --target generic --token-budget 2500 \
  --time-anchor 2026-09-04T00:00:00Z \
  --output "$OUT/changed.txt" \
  --incremental --verify-incremental --cache-root "$CACHE" --json \
  | tee "$OUT/changed.json"

cp "$OUT/number.py.before" src/humanize/number.py

contextc compile . \
  --task 'understand number and date humanization behavior' \
  --target generic --token-budget 2500 \
  --time-anchor 2026-09-04T00:00:00Z \
  --output "$OUT/reverted.txt" \
  --incremental --verify-incremental --cache-root "$CACHE" --json \
  | tee "$OUT/reverted.json"
```

Changed build: the edited source-content stage must recompute while unrelated source-content and unchanged per-node analysis/token stages show reuse. Reverted artifact semantics must return to the original.

## 4. Cache CLI dry-run/apply

```bash
contextc cache --root "$CACHE" stats --json
contextc cache --root "$CACHE" verify --json
contextc cache --root "$CACHE" plan-invalidation --source repo:///src/humanize/number.py --json
contextc cache --root "$CACHE" invalidate --source repo:///src/humanize/number.py --dry-run --json
contextc cache --root "$CACHE" invalidate --source repo:///src/humanize/number.py --apply --json
```

Dry-run must say `applied=false`; apply must say `applied=true`.

## 5. Real M15 incident

```bash
cd ~/Desktop/m15-real-incident
CACHE=../m15-real-m8-cache
OUT=../m15-real-m8-output
rm -rf "$CACHE" "$OUT"
mkdir -p "$OUT"

contextc compile . \
  --source-adapter incident \
  --task 'Review retained humanize release evidence and identify the current release procedure' \
  --target structured-json --token-budget 4000 \
  --optimizer relevance_greedy \
  --time-anchor 2026-09-03T19:20:00-07:00 \
  --output "$OUT/incident.json" \
  --incremental --verify-incremental --cache-root "$CACHE" --json \
  | tee "$OUT/incident-build.json"
```

Then change one physical observation, rerun, restore it, and rerun. Every run with `--verify-incremental` must report semantic equivalence and zero CTX704 divergence.

## 6. Reproduction without cache

For any incremental artifact:

```bash
rm -rf "$CACHE"
contextc reproduce "$OUT/incident.json.manifest.json" --verify --json
```

Reproduction must remain valid because cache state is operational, not a manifest dependency.
