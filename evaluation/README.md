# Evaluation

The [current release report](../docs/resume-results.md) adds the independently
AI-reviewed [blind-v3 corpus](blind-v3/README.md), archived-v2 comparison, review-task
analysis, local LLM verifier experiment, and [human review form](../docs/review/README.md).
The new corpus has now been inspected; preserve it as a frozen result and use new
data for future tuning. Human validation remains pending.

The latest [structure/detail evaluation](../docs/improvements.md) compares four
cumulative profiles on the earlier pages and a [fresh corpus](fresh-v2/README.md)
from HTTPX, pip, and MkDocs. Use `evaluation.real_evaluate` for group-aware metrics:

```bash
HF_HUB_OFFLINE=1 python -m evaluation.real_evaluate \
  --manifest evaluation/fresh-v2/manifest.json --backend semantic \
  --profile verified --output artifacts/local/fresh-verified
```

Use `evaluation/context-v2/manifest.json` for development. The report links the
archived-engine comparison, stage ablations, NLI candidate experiment, and all
frozen predictions. Fresh labels were independently AI-reviewed before inference
and still need human validation. The original synthetic evaluator below assumes
singleton correspondences and should not score grouped outputs.

The separate [real documentation corpus](real/README.md) evaluates complete,
naturally edited pages with split/merge annotations and explicit failure
accounting. See [results and error analysis](../docs/real-evaluation.md).
The original synthetic protocol below remains unchanged.

This is a small integration benchmark of **32 original AI-authored document pairs**:
18 development scenarios and 14 held-out test scenarios. The labels have **not been
validated by human annotators**. Scores measure performance on these fixtures,
not real-world accuracy, production safety, or superiority to other products.

The task is to align passages across two document versions, then identify material
edits while accepting meaning-preserving rewrites. The hypothesis is that embedding
alignment plus bidirectional inference reduces the lexical baseline's rewording
false alarms without hiding material changes. Failure to improve held-out material
F1, or additional material edits labeled equivalent, is evidence against that
hypothesis. A small score increase alone does not establish practical usefulness.

## Data and split discipline

`dev.jsonl` and `test.jsonl` are separate files. A record contains original old/new
text, domain, scenario group, tags, provenance, and gold change records. Gold
indices refer to `radar.compare.split_passages`, starting at zero. An absent side
uses JSON `null`. All supplied documents use blank lines between passage units.
Every input passage must appear exactly once in gold and predicted correspondences.

Domains and scenario groups are disjoint across splits. No train set is supplied:
this release uses pretrained inference and development-only threshold choices.
Shared linguistic phenomena across splits are intentional; the test uses different
scenarios and wording, rather than substituted names or numbers in copied templates.
Fixtures and split membership were authored independently of engine output. Test
content and results were withheld from the implementing agent until defaults were
frozen. Once test results are inspected, further iteration needs a new held-out set.

Development cases cover permissions, quantities, obligations, negation, exceptions,
ordinary and active/passive paraphrases, reordered passages, added and removed
passages, punctuation-only edits, duplicates, empty old/new documents, duration
unit equivalence, and mixed edits. Tags overlap and are descriptive slices, not
independent samples. There are no split/merge annotations or multilingual examples.

Meanings are judged only from the supplied short passages. Dataset coverage is
limited and labels can be debatable, especially scope and unit equivalence. The
project does not claim dataset novelty. A stronger next evaluation needs independently
edited document versions and human-reviewed alignments and change labels.

## Running

Run from the repository root in the project's Python environment:

```bash
python -m evaluation.evaluate --backend lexical --split dev --output artifacts/evaluation/lexical-dev
python -m evaluation.evaluate --backend semantic --split dev --output artifacts/evaluation/semantic-dev
```

Freeze model revisions, thresholds, preprocessing, and source hashes before opening
or evaluating `test.jsonl`. Then run each backend once on the same test set:

```bash
python -m evaluation.evaluate --backend lexical --split test --output artifacts/evaluation/lexical-test
python -m evaluation.evaluate --backend semantic --split test --output artifacts/evaluation/semantic-test
```

The lexical baseline does not download models. Semantic inference needs the pinned
model artifacts documented in the main README. Outputs include `summary.json` and
`predictions.jsonl`. The summary is also printed to stdout; `--output` is optional. Add `--quiet` to
suppress that stdout summary; it requires `--output` so results are still saved.
There is no implicit fallback from semantic to lexical inference.

Each prediction record preserves its fixture ID, expected correspondences, full
engine output, metrics, and measured wall time. Summaries capture Python/package
versions, model metadata, SHA-256 hashes of dataset and engine/evaluator sources,
and creation time. No random seed is used: fixture construction and evaluation are
deterministic. Timings can vary with machine load and model initialization.

## Metric definitions

- **Alignment precision/recall/F1:** micro-averaged overlap of predicted and gold
  `(old passage, new passage)` pairs. Added/removed singletons are excluded from
  this alignment metric and included in material-event scoring.
- **Material precision/recall/F1:** micro-averaged correspondence-level overlap,
  where `modified`, `added`, and `removed` are material. A modified wrong pair
  counts as a false positive and leaves the true pair a false negative. Predicting
  deletion plus insertion instead of a known rewrite does not receive credit.
- **Prediction coverage:** fraction of predicted events not labeled `uncertain`.
  **Aligned gold coverage** additionally requires the correct gold correspondence,
  preventing a misaligned confident output from looking fully covered.
- **Risky misses:** gold material events whose corresponding prediction is
  `unchanged` or `reworded`. **Material abstentions** count gold material events
  labeled `uncertain`. **Missed material events** include both categories and
  missing/misaligned gold correspondences. Abstention still lowers material recall;
  it is not excluded to make scores look better.
- **Confusion:** expected status to predicted status on matched correspondences.
  Missing pairs use `no_predicted_correspondence`; spurious pairs use
  `no_gold_correspondence`. Rows are counts, not percentages.
- **Latency:** wall-clock time around the entire comparison call, including initial
  model loading on the first call. Reports include first successful call, mean,
  median, and nearest-rank p95. These are single-run observations, not throughput
  benchmarks. Download time, if necessary, is also included.

Exact duplicate passage occurrences are interchangeable for scoring, using multiset
counts instead of arbitrary occurrence identity. This avoids penalizing equally
valid duplicate assignments while still counting every occurrence. Under the
operational metric, added/removed duplicate occurrences still count as material
events; it does not model document-wide logical redundancy. Move flags are shown
in engine output but are not part of the primary score.

Precision and recall use zero when their denominator is zero. Consequently a case
with no material events has material F1 zero, not one; aggregate metrics pool counts
before calculating F1. Interpret the aggregate alongside the confusion counts.

An inference error or invalid prediction remains visible in the per-example output,
sets `complete` to false, and produces a nonzero CLI exit code. Any reported metrics
then cover successful examples only and must not be compared as a complete run.
Invalid gold data stops evaluation immediately. Tests verify micro-averaging,
misalignment penalties, duplicate equivalence, abstention, validation, and split
integrity:

```bash
python -m unittest discover -s tests -p test_evaluation.py -v
```
