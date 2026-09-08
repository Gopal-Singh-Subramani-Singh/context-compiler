# M11 Real-Repository Case-Study Architecture

## Boundary

M11 evaluates existing compiler behavior against real historical evidence. It does not add a
second compiler, optimizer, metric implementation, or task-specific relevance signal.

```text
public task.yaml
  -> immutable Git bundle materialization at exact pre-fix revision
  -> one static index and analysis map
  -> equal-footing M5 strategy selections
  -> sealed public compilations
  -> evaluator labels.yaml + approved review.yaml
  -> unchanged M6 raw metrics and SQLite evidence
```

The only evaluator-aware functions live after the sealed compilation boundary. Public task
loading and pre-fix compilation never read `evaluator/`. Task-specific sentinels are checked
against compiler-visible requests, results, and rendered targets.

## Historical source

`contextc/resources/case_study/humanize/humanize.bundle` is a complete offline Git history of the
documented upstream revision. `SOURCE.json` pins its SHA-256, upstream URL, repository identity,
license, and reference tip. Every materialization clones the bundle into a temporary directory,
checks out a full 40-character revision in detached mode, and verifies that exact `HEAD`.

The bundle is treated as immutable. Its identity is checked before and after use. The optional
reverse-order path copies non-Git files into a second temporary tree in descending canonical path
order to test discovery-order independence without mutating the checkout or bundle.

## Labels and approval

Each evaluator label records the single-parent fix revision, exact Git changed-file list,
canonical source spans, justified dependency relations, evidence URL, and sentinel. Validation
checks those claims against the actual bundle and pre-fix files. `review.yaml` must be explicitly
approved and provide one reason for every useful span and dependency relation.

`extract-labels` is deliberately non-authoritative: it emits the real diff, its identity, and
candidate changed files with `approval_required=true` and `writes_ground_truth=false`.

## Equal footing and performance

One repository index, graph, tokenizer analysis, and public request configuration are sealed per
task. Strategy identity is the only allowed selection difference. The shared preparation
identity excludes requested strategy but includes every semantic input that must remain equal.
Each strategy's operational compilation latency includes the common preparation cost so sharing
does not create a misleading timing advantage.

## Metrics and reporting

M11 imports M6 `calculate_raw_metrics` directly. The real repository exposed a floating-point
summation edge where a mathematical ratio of one became `1.0000000000000007`; the shared M6
fraction helper now clamps only drift within `1e-12`, while material out-of-range values still
fail `RawMetrics` validation.

The report keeps all ten raw metrics per task and strategy. Descriptive means are secondary and
cannot replace the raw table. Latency remains operational evidence excluded from semantic run
identity.
