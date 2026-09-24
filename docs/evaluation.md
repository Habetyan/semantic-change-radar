# Pilot evaluation: 2026-09-24

A later [real-revision evaluation](real-evaluation.md) exposes substantially
harder alignment and classification errors. The synthetic results below are
preserved as a separate pilot, not combined with the new corpus.

On 14 held-out synthetic document pairs, the semantic pipeline reduced material-change
false positives from **6 to 3** relative to the lexical baseline. Material-change F1
increased from **0.8125 to 0.8966**. Both detected all 13 labeled material events and
aligned all 32 paired passages. This supports the narrow hypothesis on these fixtures;
it does not establish accuracy on natural documents.

## Protocol and provenance

The benchmark contains **32 synthetic scenarios**:
18 development pairs and 14 test pairs. Domains and scenario groups are disjoint.
Development contains 42 gold events, including 17 material events; test contains 36,
including 13 material events. No model training or fine-tuning was performed.
See [annotation provenance](annotation-provenance.md) for label preparation and author review.

Development evaluation, heuristic safeguards, and regression checks preceded the
[configuration freeze](evaluation-freeze.json) at **07:47:20 UTC**. The first test
runs completed at approximately 07:47:45 UTC. The implementing agent did not inspect
test content/results before the freeze. Alignment thresholds were 0.38 for lexical
and 0.55 for semantic; bidirectional equivalence required 0.78 and contradiction used
0.65. Semantic alignment combined embedding cosine and lexical scores with weights
0.85 and 0.15. The preserved test results did not drive further tuning.

Both backends used the same fixtures, passage units, and scoring. The lexical baseline
aligns similar passages and marks every nonidentical pair as modified. The semantic
pipeline adds embeddings, bidirectional NLI, and conservative wording guards. This
comparison changes several components together, so it does not isolate their effects.

Run IDs were unique and matched between backends; every example completed. Recomputed
pooled counts matched summaries. Core engine and dataset SHA-256 hashes matched the
freeze in all four runs. Summaries preserve runtime versions, pinned model revisions,
and source hashes; JSONL artifacts preserve individual predictions. See the
[metric definitions and reproduction commands](../evaluation/README.md).

## Results

Scores are micro-averaged over passage correspondences. Material events are `modified`,
`added`, and `removed`; a wrong alignment cannot receive material-event credit.

| Split | Backend | Alignment F1 | Material precision | Material recall | Material F1 | False positives |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Development, 18 pairs | Lexical | 0.9851 | 0.7391 | 1.0000 | 0.8500 | 6 |
| Development, 18 pairs | Semantic | 1.0000 | 0.9444 | 1.0000 | 0.9714 | 1 |
| Test, 14 pairs | Lexical | 1.0000 | 0.6842 | 1.0000 | 0.8125 | 6 |
| Test, 14 pairs | Semantic | 1.0000 | 0.8125 | 1.0000 | 0.8966 | 3 |

Both backends returned **zero abstentions and zero observed risky misses** in both
splits. Test prediction coverage and aligned gold coverage were 100%. Zero misses
on 13 authored material events is insufficient evidence for reliable recall. With
no abstentions in the set, these runs do not establish whether uncertainty handling
works on ambiguous documents.

On test, all 17 unchanged events, nine modified events, three additions, and one
removal were correct for both backends. Of six gold wording-only events, the semantic
pipeline accepted three and flagged three; the lexical baseline flagged all six.
There was no alignment advantage on test. Its observed benefit came from classifying
some already-aligned rewrites correctly.

Artifacts: [lexical development](../artifacts/evaluation/lexical-dev/summary.json),
[semantic development](../artifacts/evaluation/semantic-dev/summary.json),
[lexical test](../artifacts/evaluation/lexical-test/summary.json), and
[semantic test](../artifacts/evaluation/semantic-test/summary.json).

## Error analysis

All three semantic test errors were false alarms on benign rewrites:

| Fixture | Equivalent edit incorrectly marked modified | Evidence in prediction |
| --- | --- | --- |
| `test-05`, passage 1 | “Allow the instrument to warm up before taking a measurement” to “Wait until the instrument has warmed up before measuring” | The changed condition marker triggered a guard despite two-way entailment scores above 0.95. |
| `test-09`, passage 0 | “1.0 meters” to “1 meter” | Numeric formatting triggered a guard; reverse entailment was also low, 0.1415. |
| `test-14`, passage 0 | “alarm continues after a reset” to “resetting does not stop the alarm” | A negation guard fired; reverse entailment was 0.5022, below the equivalence threshold. |

The lexical baseline shared those errors and additionally flagged the artifact-link
paraphrase in `test-04`, the cleaning instruction in `test-05`, and punctuation in
`test-09`. Full evidence is in the [semantic test predictions](../artifacts/evaluation/semantic-test/predictions.jsonl)
and [lexical test predictions](../artifacts/evaluation/lexical-test/predictions.jsonl).

The semantic development error was `dev-16`: “every 60 minutes” to “every hour”.
Implicit unit conversion is unsupported. Explicit guard signals prevent some
potentially dangerous equivalence decisions, but these examples show their false-alarm
cost. The observed NLI scores are model outputs, not calibrated probabilities of
correctness. No guard or model change was made in response to these test errors.

## Runtime

These were single CPU runs on a 13th Gen Intel Core i7-13620H host with 16 logical
CPUs and 32 GB RAM, running Linux 6.11 x86_64 and Python 3.12.2. ONNX Runtime 1.23.2
used two inference threads and model batch size eight. Host details were checked
separately after the runs; the saved summaries record runtime and platform versions.
The embedding model was `sentence-transformers/all-MiniLM-L6-v2` and the NLI model
was `cross-encoder/nli-MiniLM2-L6-H768`, using pinned quantized ONNX artifacts.

| Test backend | Median per pair | Mean including initialization | First call | p95, nearest rank |
| --- | ---: | ---: | ---: | ---: |
| Lexical | 0.154 ms | 0.217 ms | 0.842 ms | 0.842 ms |
| Semantic | 16.254 ms | 47.568 ms | 471.892 ms | 471.892 ms |

The first semantic comparison includes model initialization. With only 14 observations,
nearest-rank p95 is the maximum, here that first call. These short fixtures do not
measure full-length document latency, concurrent users, or Hugging Face Space cold
starts. Download time can also enter the first call when the model cache is empty.

A separate post-freeze sanity run used 80 passages with unique service identifiers,
reversed their order, and changed retention from 30 to 60 days in each. All 80
passages aligned and were marked modified in **1.461 seconds**, including model
initialization from the existing cache, with `HF_HUB_OFFLINE=1`. This templated case
exercised the passage limit and reordering. It is a performance/sanity observation,
not part of the held-out accuracy results or evidence of broad robustness.

The [saved runtime check](../artifacts/runtime-check.json) records the observation.
Reproduce the workload after caching models with
`HF_HUB_OFFLINE=1 python -m scripts.stress_check`.

## Limits and next evaluation

The test is small, manually designed by an AI agent, English-only, and dominated by
short passages with explicit edits. Labels may be wrong. Duplicate additions/removals
count as material events under the operational metric even when logically redundant.
The benchmark does not cover passage splits/merges, cross-paragraph dependencies,
long specifications, extraction errors, realistic prevalence, or adversarial phrasing.
The lexical baseline is intentionally simple. There are no component ablations or
comparisons with stronger document-comparison systems.

No bootstrap interval is reported: resampling these 14 authored scenarios would not
quantify uncertainty on natural documents. The fixtures are now an inspected regression
set. Further tuning requires a new held-out evaluation.

A useful next step is 50 independently selected version pairs from at least five
permissively licensed documentation repositories, split by repository before tuning.
Preserve revision identifiers, sample unchanged context as well as edits, have two
people independently label alignments and materiality, and resolve disagreements.
Compare lexical diff, normalized numeric/unit comparison, and the current frozen
pipeline. Add separate development-only ablations for embeddings, NLI, and guards,
then evaluate once on the new holdout and report document-level uncertainty and
reviewer time saved.
