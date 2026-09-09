# Context Compiler M11 Real-Repository Case Study

## Status and scope

This is a fresh, bounded external-validation case study over eight historical bug fixes from one
real public Python repository. It asks whether Context Compiler can recover genuinely relevant
pre-fix files, spans, and dependency context under constrained budgets. It is not a statistically
significant study and does not establish universal strategy superiority.

## Repository and license

- Repository: [python-humanize/humanize](https://github.com/python-humanize/humanize)
- License: MIT; the upstream license is retained with the packaged reference.
- Packaged reference: an immutable 1,017,637-byte offline Git bundle.
- Bundle SHA-256:
  `5e40e011d2b1f87e45e113475f60d659c529e04b10f04263784cada16e285408`
- Packaged upstream tip:
  `3201e702ed7eae506f793fad0aec204f387aeb4c`

The repository was selected because it is small, understandable, permissively licensed, has tests,
and has identifiable behavioral fixes with usable pre-fix history. Benchmark compilation requires
no network and never imports or executes the repository.

## Methodology

For each task, the public bug description and allowed budget are stored separately from evaluator
labels and manual review. The compiler materializes the exact single-parent pre-fix revision from
the immutable bundle into a temporary directory. All strategy compilations finish before evaluator
labels are loaded. The fix revision, actual changed-file list, canonical 1-based inclusive spans,
dependency relations, evidence URL, rationale, approval, and evaluator sentinel are then validated.

Ground truth comes from the real fix diff and fresh manual review, not compiler output. Label
extraction is review-only: it reports the patch and candidate changed files but cannot write or
approve labels. M11 calls the M5 strategies, M6 equal-footing fingerprint enforcement, and the
same M6 ten-metric function.

The compared strategies are `naive`, `top_k`, `relevance_greedy`, `density_greedy`, and
`graph_closure_greedy`. In this build, semantic embeddings are unavailable, so `top_k` honestly
records a fallback to `density_greedy` rather than relabeling lexical scores as semantic.

## Historical tasks

| Task | Pre-fix | Fix | Required production span | Diversity |
| --- | --- | --- | --- | --- |
| Non-finite `naturaldelta` | `08cf2c3` | `b48b37b` | `time.py:97-248` | large function, numeric edge |
| Fraction rounds to whole | `e1a5c7c` | `08cf2c3` | `number.py:311-377` | rounding boundary |
| `naturalsize` rollover | `7574e0c` | `823ad60` | `filesize.py:38-102` | tight budget |
| `metric` prefix rollover | `c2c410c` | `7574e0c` | `number.py:502-559` | rounding boundary |
| Negative mixed fraction | `976484a` | `c2c410c` | `number.py:309-370` | formatting edge |
| Empty `natural_list` | `013969a` | `0a06a3d` | `lists.py:12-36` | distractor-heavy, small fix |
| Timezone-aware `naturaldate` | `b172d67` | `a47a89e` | `time.py:343-358` plus helpers | dependency-sensitive |
| Nearest-unit `naturaldelta` | `38c9968` | `6d89dfa` | `time.py:95-280` | dependency-sensitive, large function |

All eight task records passed single-parent ancestry, actual changed-file, pre-fix span,
canonical-URI, complete-rationale, approved-review, sentinel-isolation, and bundle-immutability
validation. The set includes two dependency-sensitive tasks, a tight-budget task, a large relevant
function challenge, and a distractor-heavy task.

## Fresh raw results

The following 40 rows were generated locally on Python 3.12.13. Latencies are operational values
from this machine and are deliberately excluded from semantic run identity.

| Task | Requested | Used | Status | File recall | File precision | Span recall | Dependency coverage | Useful ratio | Unsupported ratio | Budget | Compile ms | Optimizer ms |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| humanize-empty-natural-list | top_k | density_greedy | fallback | 0.000 | 0.000 | 0.000 | 1.000 | 0.000 | 1.000 | 0.779 | 2995.328 | 0.000 |
| humanize-empty-natural-list | density_greedy | density_greedy | heuristic | 0.000 | 0.000 | 0.000 | 1.000 | 0.000 | 1.000 | 0.779 | 2992.227 | 0.000 |
| humanize-empty-natural-list | graph_closure_greedy | graph_closure_greedy | heuristic | 0.000 | 0.000 | 0.000 | 1.000 | 0.000 | 1.000 | 0.779 | 2946.800 | 0.000 |
| humanize-empty-natural-list | naive | naive | heuristic | 0.000 | 0.000 | 0.000 | 1.000 | 0.000 | 1.000 | 0.872 | 200.813 | 0.000 |
| humanize-empty-natural-list | relevance_greedy | relevance_greedy | heuristic | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 | 0.830 | 198.650 | 0.000 |
| humanize-fractional-rounds-whole | density_greedy | density_greedy | heuristic | 0.000 | 0.000 | 0.000 | 1.000 | 0.000 | 1.000 | 0.830 | 2786.633 | 0.000 |
| humanize-fractional-rounds-whole | top_k | density_greedy | fallback | 0.000 | 0.000 | 0.000 | 1.000 | 0.000 | 1.000 | 0.830 | 2880.691 | 0.000 |
| humanize-fractional-rounds-whole | graph_closure_greedy | graph_closure_greedy | heuristic | 0.000 | 0.000 | 0.000 | 1.000 | 0.000 | 1.000 | 0.830 | 2780.987 | 0.000 |
| humanize-fractional-rounds-whole | naive | naive | heuristic | 0.000 | 0.000 | 0.000 | 1.000 | 0.000 | 1.000 | 0.826 | 205.273 | 0.000 |
| humanize-fractional-rounds-whole | relevance_greedy | relevance_greedy | heuristic | 1.000 | 0.500 | 0.000 | 1.000 | 0.000 | 1.000 | 0.820 | 204.318 | 0.000 |
| humanize-metric-prefix-rollover | density_greedy | density_greedy | heuristic | 0.000 | 0.000 | 0.000 | 1.000 | 0.000 | 1.000 | 0.825 | 2604.652 | 0.000 |
| humanize-metric-prefix-rollover | top_k | density_greedy | fallback | 0.000 | 0.000 | 0.000 | 1.000 | 0.000 | 1.000 | 0.825 | 2611.733 | 0.000 |
| humanize-metric-prefix-rollover | graph_closure_greedy | graph_closure_greedy | heuristic | 0.000 | 0.000 | 0.000 | 1.000 | 0.000 | 1.000 | 0.825 | 2548.983 | 0.000 |
| humanize-metric-prefix-rollover | naive | naive | heuristic | 0.000 | 0.000 | 0.000 | 1.000 | 0.000 | 1.000 | 0.811 | 210.078 | 0.000 |
| humanize-metric-prefix-rollover | relevance_greedy | relevance_greedy | heuristic | 1.000 | 1.000 | 0.000 | 1.000 | 0.000 | 1.000 | 0.782 | 209.886 | 0.000 |
| humanize-naturaldelta-nearest-unit | top_k | density_greedy | fallback | 1.000 | 0.333 | 0.000 | 0.000 | 0.000 | 1.000 | 0.883 | 1854.455 | 0.000 |
| humanize-naturaldelta-nearest-unit | density_greedy | density_greedy | heuristic | 1.000 | 0.333 | 0.000 | 0.000 | 0.000 | 1.000 | 0.883 | 1853.945 | 0.000 |
| humanize-naturaldelta-nearest-unit | graph_closure_greedy | graph_closure_greedy | heuristic | 1.000 | 0.333 | 0.000 | 0.000 | 0.000 | 1.000 | 0.883 | 1830.675 | 0.000 |
| humanize-naturaldelta-nearest-unit | naive | naive | heuristic | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 1.000 | 0.902 | 221.776 | 0.000 |
| humanize-naturaldelta-nearest-unit | relevance_greedy | relevance_greedy | heuristic | 1.000 | 0.250 | 0.000 | 0.000 | 0.000 | 1.000 | 0.892 | 214.705 | 0.000 |
| humanize-naturalsize-unit-rollover | density_greedy | density_greedy | heuristic | 0.000 | 0.000 | 0.000 | 1.000 | 0.000 | 1.000 | 0.853 | 2724.833 | 0.000 |
| humanize-naturalsize-unit-rollover | top_k | density_greedy | fallback | 0.000 | 0.000 | 0.000 | 1.000 | 0.000 | 1.000 | 0.853 | 2793.433 | 0.000 |
| humanize-naturalsize-unit-rollover | graph_closure_greedy | graph_closure_greedy | heuristic | 0.000 | 0.000 | 0.000 | 1.000 | 0.000 | 1.000 | 0.853 | 2704.132 | 0.000 |
| humanize-naturalsize-unit-rollover | naive | naive | heuristic | 0.000 | 0.000 | 0.000 | 1.000 | 0.000 | 1.000 | 0.874 | 221.088 | 0.000 |
| humanize-naturalsize-unit-rollover | relevance_greedy | relevance_greedy | heuristic | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 | 0.874 | 221.255 | 0.000 |
| humanize-negative-mixed-fraction | top_k | density_greedy | fallback | 0.000 | 0.000 | 0.000 | 1.000 | 0.000 | 1.000 | 0.779 | 2762.082 | 0.000 |
| humanize-negative-mixed-fraction | density_greedy | density_greedy | heuristic | 0.000 | 0.000 | 0.000 | 1.000 | 0.000 | 1.000 | 0.779 | 2736.414 | 0.000 |
| humanize-negative-mixed-fraction | graph_closure_greedy | graph_closure_greedy | heuristic | 0.000 | 0.000 | 0.000 | 1.000 | 0.000 | 1.000 | 0.779 | 2879.219 | 0.000 |
| humanize-negative-mixed-fraction | naive | naive | heuristic | 0.000 | 0.000 | 0.000 | 1.000 | 0.000 | 1.000 | 0.810 | 194.809 | 0.000 |
| humanize-negative-mixed-fraction | relevance_greedy | relevance_greedy | heuristic | 0.000 | 0.000 | 0.000 | 1.000 | 0.000 | 1.000 | 0.778 | 194.277 | 0.000 |
| humanize-nonfinite-naturaldelta | top_k | density_greedy | fallback | 0.000 | 0.000 | 0.000 | 1.000 | 0.000 | 1.000 | 0.892 | 2844.810 | 0.000 |
| humanize-nonfinite-naturaldelta | density_greedy | density_greedy | heuristic | 0.000 | 0.000 | 0.000 | 1.000 | 0.000 | 1.000 | 0.892 | 2756.520 | 0.000 |
| humanize-nonfinite-naturaldelta | graph_closure_greedy | graph_closure_greedy | heuristic | 0.000 | 0.000 | 0.000 | 1.000 | 0.000 | 1.000 | 0.892 | 2736.384 | 0.000 |
| humanize-nonfinite-naturaldelta | naive | naive | heuristic | 0.000 | 0.000 | 0.000 | 1.000 | 0.000 | 1.000 | 0.894 | 231.568 | 0.000 |
| humanize-nonfinite-naturaldelta | relevance_greedy | relevance_greedy | heuristic | 0.000 | 0.000 | 0.000 | 1.000 | 0.000 | 1.000 | 0.881 | 229.259 | 0.000 |
| humanize-timezone-aware-naturaldate | density_greedy | density_greedy | heuristic | 1.000 | 0.250 | 0.000 | 0.000 | 0.150 | 0.850 | 0.855 | 1961.636 | 0.000 |
| humanize-timezone-aware-naturaldate | top_k | density_greedy | fallback | 1.000 | 0.250 | 0.000 | 0.000 | 0.150 | 0.850 | 0.855 | 2022.800 | 0.000 |
| humanize-timezone-aware-naturaldate | graph_closure_greedy | graph_closure_greedy | heuristic | 1.000 | 0.250 | 0.000 | 0.000 | 0.150 | 0.850 | 0.855 | 1966.508 | 0.000 |
| humanize-timezone-aware-naturaldate | naive | naive | heuristic | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 1.000 | 0.833 | 187.876 | 0.000 |
| humanize-timezone-aware-naturaldate | relevance_greedy | relevance_greedy | heuristic | 1.000 | 0.500 | 1.000 | 1.000 | 0.687 | 0.313 | 0.840 | 193.244 | 0.000 |

## Descriptive means

These means summarize the raw table; they are not a composite score or a universal ranking.

| Requested strategy | File recall | Span recall | Dependency coverage | Useful ratio | Unsupported ratio | Budget utilization |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| naive | 0.000 | 0.000 | 0.750 | 0.000 | 1.000 | 0.853 |
| top_k (fallback) | 0.250 | 0.000 | 0.750 | 0.019 | 0.981 | 0.837 |
| density_greedy | 0.250 | 0.000 | 0.750 | 0.019 | 0.981 | 0.837 |
| graph_closure_greedy | 0.250 | 0.000 | 0.750 | 0.019 | 0.981 | 0.837 |
| relevance_greedy | 0.750 | 0.375 | 0.875 | 0.336 | 0.664 | 0.837 |

## Worked example: `naturalsize` unit rollover

Historical task: commit `823ad6096e1e5ba82ea876ce761fc2efebd76157` fixed
`naturalsize()` near unit boundaries. In its parent
`7574e0cc377d80db0d2756fc2c5e0b8799a6f8b4`, the suffix was chosen before formatted rounding,
so 999,999 bytes could become `1000.0 kB` instead of `1.0 MB`. The fix changed
`src/humanize/filesize.py` and added decimal, binary, and GNU regression cases in
`tests/test_filesize.py`.

Ground truth is the pre-fix `naturalsize` function at
`repo://python-humanize/src/humanize/filesize.py:38-102`. The final budget was 760 Generic
tokens, with exactly 560 tokens available for source content. The rendered target function cost
556 source tokens, leaving only four source tokens of allowance.

- `relevance_greedy` selected only the exact 556-token function. It achieved file recall,
  precision, span recall, dependency coverage, and useful-token ratio of 1.0, with zero unsupported
  context and 664/760 final tokens.
- `naive` selected the license, release documentation, and `py.typed`, producing zero file/span
  recall and a 1.0 unsupported-context ratio at 664/760 tokens.
- `top_k` had no embeddings and truthfully fell back to `density_greedy`. Both selected eight
  small distractors totaling the allowance instead of the large relevant function, producing zero
  file/span recall and a 1.0 unsupported-context ratio at 648/760 tokens.
- `graph_closure_greedy` made the same selection because this task has no internal required
  dependency edge capable of changing the density decision.

The supported conclusion is narrow: on this task, exact relevance ranking overcame a severe
large-item density disadvantage. It does not show that relevance greedy is universally superior.
The result also demonstrates why required-span recall and unsupported-context ratio reveal more
than budget utilization alone.

## Dependency-sensitive evidence

The timezone-aware `naturaldate` task labels the real pre-fix calls from `naturaldate` to
`naturalday` and `_abs_timedelta`. Under its budget, `relevance_greedy` selected the required
span and both helpers, reaching dependency coverage 1.0 and span recall 1.0. The other compared
strategies did not cover both endpoints.

The nearest-unit task labels the real `naturaltime -> naturaldelta` call. Its large transitive
closure did not fit the useful selection produced by these bounded heuristics, so dependency
coverage remained 0.0. This negative result is retained rather than hidden.

## Determinism evidence

`contextc case-study verify-determinism --all` ran all five strategies for every task three
ways: normal, repeated, and from a temporary checkout whose files were physically created in
reverse order. All eight tasks reported:

- repeated semantic evidence identical: true;
- reversed-materialization semantic evidence identical: true;
- five stable semantic run IDs.

Measured latency is excluded from semantic identity. Source selection, ordering, metrics,
fingerprints, label identities, and run IDs remain semantic.

## Known limitations

- Eight tasks from one small Python repository are not statistically significant.
- The current analysis is a bounded lexical baseline; no semantic embedding model was installed.
- Top-K results therefore describe an explicit density fallback, not semantic retrieval.
- Several tasks expose failure to select a large relevant span; those negative results are part of
  the evidence.
- Function-level pre-fix spans are used when the correcting branch does not yet exist.
- Test execution is not part of repository indexing or benchmark compilation.
- Latency depends on hardware and filesystem state.

