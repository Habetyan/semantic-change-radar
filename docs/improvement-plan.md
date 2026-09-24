# Structure and detail improvements: experimental contract

Approved scope: preserve source scope, support bounded splits/merges, inspect
changed details before equivalence, measure each addition, and compare an
alternative NLI model without changing the deployment default prematurely.

The original engine is preserved in `artifacts/evaluation/baseline-v1.zip` with
SHA-256 `5daff250ab60962de61403a3d78cf14bfaf80f24b405ad0bba7458dbc165a56f`.
Existing real corpus snapshots, annotation files and historical predictions are
not rewritten. They are development/regression data after inspection.

## Stages and hypotheses

1. `baseline`: feature-disabled comparison, checked against the archived engine.
2. `context`: preserve heading ancestry and list/introduction ownership before
   flattening. Use scope as a soft correspondence signal, and reconsider exact
   text when its scope differs. Hypothesis: fewer cross-topic correspondences.
3. `groups`: refine the singleton assignment with adjacent 1:2 / 2:1 candidates
   in the same structural scope, consuming unmatched neighbors only. Require
   support from both fragments and a fixed 0.04 score improvement, except exact
   combined text. Hypothesis: recover some split/merge groups without absorbing
   unrelated additions. Arbitrary non-adjacent many-to-many edits remain outside
   this first implementation.
4. `verified`: inspect changed conditions and comma/sentence clauses before
   accepting paragraph-level rewording. Disagreement or unresolved additions /
   deletions go to review. Hypothesis: fewer false equivalence decisions, at the
   cost of more review. This step does not claim to determine every clause's
   truth or automatically turn every deletion into a material change.

Models and original body-score weights/thresholds remain fixed. Context scores
use 80% body score and 20% nearest explicit scope similarity when scopes differ;
short named list labels further distinguish ownership. Global matching still
allows moves. Exact matching includes scope. Optional group or context inputs
are never truncated to meet model limits. The existing 80-passage limit remains.

Runtime correction discovered before semantic stage runs: archived int8 NLI
scores materially change with unrelated batch neighbors. NLI now processes one
pair per inference call; embeddings retain batches of eight. Report the archived
original separately from the feature-disabled v2 baseline, which shares this
stable NLI policy with all subsequent stages. This change affects decisions
independently of the new alignment features. The batch experiment does not
isolate padding from dynamic activation quantization as the exact cause.

Gold unit: passage correspondence groups and operational materiality labels.
Primary metrics: changed-correspondence F1/recall and exact material-group F1.
Secondary: split/merge exact recovery, material-as-equivalent misses, review
rate, per-document scores and CPU latency. Successful/failed cases and excluded
uncertain labels are explicit. Each stage is compared on identical inputs.

The historical RST adapter emits new context sidecars with unchanged passage
IDs/text. Its scope information is shared by all stage runs, with baseline
ignoring it. Do not compare altered passage units against the old annotations.

Fresh evaluation: three independently selected, pinned page revisions from
HTTPX, pip and MkDocs, with independently AI-reviewed labels, frozen before any
fresh predictions. These remain a small purposive diagnostic, not a random or
human-validated benchmark. Public pretraining overlap is unknown. Freeze code
before running fresh pages; do not tune on those results. Report regressions.

Alternative model: fixed-threshold, gold-aligned changed-singleton NLI comparison
on the known development corpus, using MiniLM and pinned DeBERTa v3 small CPU
ONNX. Keep alignment and input pair selection identical, report artifact sizes,
latency, errors and abstentions. No training or fine-tuning. Do not silently
replace the deployment model based on a small development-only gain.

Stop after meaningful correctness tests, all stage runs on development and
fresh data, a model comparison, browser checks, an error analysis and a final
code review. Implementation bug fixes may be made with regression tests;
post-evaluation changes and repeated runs must be identified explicitly.
