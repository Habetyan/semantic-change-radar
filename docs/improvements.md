# Structure, grouping, and detail checks

This report describes the archived v2 release. See [current results](resume-results.md)
for the later scope policy, exact excerpts, UI review tasks and new blind corpus.

Implemented on 2026-09-24. The default `verified` profile preserves heading/list
scope, supports adjacent paragraph splits and merges, and checks changed clauses
before accepting equivalence. The embedding and NLI checkpoints remain unchanged.

The results are mixed. One fresh real paragraph split is recovered, and two
material edits previously accepted as equivalent now require review. Paired
material detection is still 5/7 on those pages. On the earlier development pages,
heading changes produce many extra alerts and slightly worse overall scores.
This is a conservative review tool, not a general accuracy improvement claim.

## What changed

- Source parsing retains heading ancestry, list ownership, explicit introductions,
  and source line spans. Ordinary neighboring prose is not automatically context.
- Exact matches include scope. Remaining passages use the existing global
  assignment, with a soft scope adjustment that still permits document moves.
- A bounded refinement can combine adjacent 1:2 or 2:1 passages within the same
  structural scope. It can absorb an unmatched neighbor, but cannot steal a
  passage from a second match. Both fragments must support the correspondence;
  acceptance requires a fixed score improvement except for exact combined text.
- Before accepting a paraphrase, changed conditions and sentence/comma clauses
  are checked separately. Unresolved additions, deletions, or entailment conflicts
  go to review with normalized clause excerpts. These can join neighboring clauses
  with spaces and omit separator punctuation; they are not guaranteed verbatim
  substrings. Full original text remains in the source parts. The verifier never promotes an uncertain edit
  to a proven material change.
- Reports use schema 2 with canonical group arrays, individual source parts,
  context, and detail evidence. UI cards and exports retain every group member.
- NLI processes one directional pair per call to remove an observed dependency
  on unrelated batch neighbors. Embeddings still use batches of eight.

All candidate context/group inputs are checked against token limits. A contextual
pair that does not fit goes to review; an oversized group candidate is skipped.
Oversized original body input still produces an explicit error. No truncation is
used. The 80-passage and 30,000-character limits are unchanged.

The cumulative CLI profiles are `baseline`, `context`, `groups`, and `verified`.
The UI uses `verified`. It retains the requested checks and favors review when
scope changes; users should expect more flags after section renaming. The CLI
`baseline` profile remains available for a comparison without these features.

## Protocol and data

The [experimental contract](improvement-plan.md) records the scope and thresholds.
The earlier real pages are now development data because their errors were
inspected. Original snapshots, annotations, predictions, and the historical engine
are retained. The engine archive is
[`baseline-v1.zip`](../artifacts/evaluation/baseline-v1.zip), SHA-256
`5daff250ab60962de61403a3d78cf14bfaf80f24b405ad0bba7458dbc165a56f`.

Development uses the original RST passage IDs with new context sidecars. The
adapter reconstructs heading/list structure without changing any scored text.
Seven of eight pages score; Requests advanced remains an explicit failure at
149/158 passages. Every development stage includes that failure in its report.

The fresh diagnostic uses complete pinned page revisions from three repositories
absent from development: HTTPX compatibility, pip caching, and MkDocs deployment.
See the [source manifest](../evaluation/fresh-v2/manifest.json) and
[extraction/annotation notes](../evaluation/fresh-v2/README.md). Raw sources,
licenses, deterministic prose extraction, and omission audits are retained. Code
examples are excluded, consistent with this project's prose-only task.

Fresh data contains 85 old and 163 new passages, annotated as 165 groups:
70 unchanged, 5 reworded, 7 modified, 80 added, and 3 removed. There is one labeled
split. The 12 changed paired groups, including just seven material revisions,
are the most relevant difficult slice. Additions dominate all-event material F1.

Fresh reference labels were prepared without model predictions. See
[annotation provenance](annotation-provenance.md). The
[label freeze](fresh-v2-label-freeze.json) and [code/data freeze](fresh-v2-freeze.json)
precede every fresh prediction. No engine changes or threshold tuning followed
the development stage results or the fresh run. App explanatory copy, browser
checks, and reporting were updated afterward. Public pretraining overlap is
unknown. Three purposively selected pages cannot establish statistical superiority.

## Stage results

Material precision/recall/F1 requires both the exact gold group and a material
decision. Abstention lowers recall. Changed alignment excludes gold unchanged
edges and keeps incorrect edges. A group contributes its Cartesian alignment
edges. “Risky” counts exactly aligned singleton material edits labeled unchanged
or reworded; it does not count all missing or misaligned material events. “Review”
counts all uncertain predictions. Full definitions are in the evaluator artifacts.

The archived engine uses its original batch-of-eight NLI policy. The v2 baseline
disables new features but uses individual NLI calls, so those are distinct rows.

### Development: seven scored pages, one failed page

| Configuration | Changed alignment F1 | Material P | Material R | Material F1 | Risky | Review |
|---|---:|---:|---:|---:|---:|---:|
| Lexical baseline | .787 | .656 | .896 | .758 | 0 | 0 |
| Archived semantic v1, historical run | .771 | .708 | .833 | .766 | 2 | 7 |
| Semantic baseline, stable NLI | .771 | .705 | .823 | .760 | 1 | 10 |
| + Context | .761 | .664 | .865 | .751 | 1 | 38 |
| + Groups | .761 | .664 | .865 | .751 | 1 | 38 |
| + Detail verification | .761 | .664 | .865 | .751 | 0 | 40 |

Context fixes the specific pytest `prepend`/`importlib` cross-mode match, but
does not improve aggregate alignment. Thirty-two gold-unchanged passages become
uncertain solely from changed heading/scope wording, and three become modified
through inherited signals. For example, a parent introduction dropping “until
recently” can cause an unchanged child sentence to be flagged. This propagation
is too broad and is a known weakness of the current conservative policy.

No development gold group is recovered. Six of eight groups are non-adjacent or
larger than 1:2/2:1. The two eligible groups fail existing gates: the Flask
production warning has constituent similarities below the acceptance floor;
the pytest packaging split does not improve sufficiently over its strongest
singleton. These are limitations, not successful split recovery.

Detail verification catches the removed Flask Unicode clause. It also adds a
false review for harmless RST role spelling changes. The verified median is
670 ms versus 205 ms for stable baseline, from one run per document on this CPU;
these are observations rather than a throughput benchmark.

### Fresh: all three pages scored

| Configuration | Changed alignment F1 | Material P | Material R | Material F1 | Risky | Review |
|---|---:|---:|---:|---:|---:|---:|
| Lexical baseline | .857 | .903 | .933 | .918 | 0 | 0 |
| Archived semantic v1 | .923 | .966 | .956 | .961 | 2 | 2 |
| Semantic baseline, stable NLI | .923 | .966 | .956 | .961 | 1 | 3 |
| + Context | .923 | .956 | .956 | .956 | 1 | 2 |
| + Groups | .963 | .977 | .956 | .966 | 1 | 2 |
| + Detail verification | .963 | .977 | .956 | .966 | 0 | 3 |

Verified credits 86/90 material groups. **Zero risky misses does not mean zero
missed edits.** Two paired material edits require review; one addition and one
removal are lost to an incorrect correspondence. Excluding additions/removals,
paired material P/R/F1 is .714/.714/.714 for both archived v1 and verified.
Context alone gives .625/.714/.667. Correct paired material decisions stay at
5/7 throughout; the benefit is less false reassurance and one recovered split.

Concrete outcomes, using zero-based passage indices:

- HTTPX `old[4] → new[12,13]`: the URL-object explanation and string conversion
  instruction split into two paragraphs. Groups recovers the exact 1:2
  correspondence and labels it rewording. This is the only fresh gold split.
- HTTPX `old[16] → new[42]`: `request.text/content` changes to
  `response.text/content`. Archived v1 accepts equivalence; individual NLI calls
  instead abstain before any structural features are added.
- HTTPX `old[21] → new[56]`: the revised unsupported-arguments list adds `content`.
  Paragraph NLI accepts equivalence; detail entailments .2071/.9848 cause review.
- pip `old[21] → new[17]`: a benign rewrite under a changed heading is falsely
  flagged as material by the context stage.
- MkDocs `old[15] → new[10]`: distinct deployment warnings remain incorrectly
  paired. Structural context does not fix every matching error.

Stable baseline and verified median times are 265 ms and 298 ms on these three
pages, with first calls of 994 ms and 1,207 ms including initialization. Both use
two ONNX CPU threads and cached weights, with Hub network access disabled. The
archived runner times only its comparison call; v2 also includes file loading
and scoring, so those latency scopes should not be equated.

Predictions and summary provenance are retained in
[`v2-dev-*`](../artifacts/evaluation/) and `v2-fresh-*` directories. Every successful
prediction partitions all source indices exactly once. Independent recomputation
confirmed all per-case and aggregate scores, source hashes, archive members, and
both fresh freezes. No failed comparison was silently dropped.

## Alternative NLI model and batch sensitivity

Tested pinned [cross-encoder/nli-deberta-v3-small](https://huggingface.co/cross-encoder/nli-deberta-v3-small/tree/fa2804872c3b4bd748f38c0185cc85775361e735)
against MiniLM on the same 35 gold-aligned changed singleton development pairs:
17 material and 18 reworded. Alignment is bypassed; production guards and
thresholds are fixed. No training, candidate calibration, or fresh-page model
selection was performed.

| Individual NLI calls | MiniLM | DeBERTa v3 small |
|---|---:|---:|
| Material precision | .579 | .556 |
| Material recall | .647 | .588 |
| Material F1 | .611 | .571 |
| Correct statuses | 17/35 | 18/35 |
| Material edits labeled equivalent | 1 | 1 |
| Abstentions | 9 | 8 |
| Warm median for 70 directional pairs | .957 s | 1.634 s |
| Quantized ONNX weights | 82.8 MB | 172.5 MB |

An always-material classifier has F1 .654 on these pairs, higher than both NLI
configurations, but accepts no benign rewording. This illustrates the precision,
recall, and review tradeoff and the weakness of NLI alone on this domain. The
candidate did not improve primary material F1 and was 1.71 times slower, so it
was not adopted. The experiment does not show that DeBERTa is inherently worse
or that different calibration could not help.

An initial batch-of-eight experiment is preserved separately: MiniLM F1 .667,
DeBERTa .706. During reproduction, the exact same pytest condition pair produced
materially different scores with different unrelated neighbors. Its reverse
entailment changed from .8795 in the original document batch to .4986 in a
two-direction pair batch and .5413 when scored individually. Archived code
reproduced the original score, so this was not a text or implementation mismatch.
Padding and dynamic activation quantization were not isolated as causes.

Production now scores each NLI pair independently. The regression test and saved
stability check found maximum probability difference 0.0 when surrounding a pair
with unrelated inputs. Embedding batching remains unchanged; this experiment
does not establish its invariance. Candidate results were rerun under the same
individual-call policy as production. See
[current comparison](../artifacts/evaluation/nli-comparison-single/summary.json),
[stability check](../artifacts/evaluation/nli-comparison-single/stability-check.json),
and [original batch evidence](../artifacts/evaluation/nli-comparison/batch-check.json).

## Reproduce without overwriting recorded runs

From the repository root with the prepared environment and cached models:

```bash
HF_HUB_OFFLINE=1 .venv/bin/python -m evaluation.evaluate_archive \
  --manifest evaluation/fresh-v2/manifest.json \
  --output artifacts/local/fresh-archived

for profile in baseline context groups verified; do
  HF_HUB_OFFLINE=1 .venv/bin/python -m evaluation.real_evaluate \
    --manifest evaluation/fresh-v2/manifest.json --backend semantic \
    --profile "$profile" --output "artifacts/local/fresh-$profile"
done

HF_HUB_OFFLINE=1 .venv/bin/python -m evaluation.compare_nli \
  --batch-size 1 --warm-runs 3 --output artifacts/local/nli-comparison

HF_HUB_OFFLINE=1 RUN_MODEL_TESTS=1 .venv/bin/python -m pytest -q
.venv/bin/ruff check .
.venv/bin/ruff format --check .
```

Use `evaluation/context-v2/manifest.json` for the development stages; exit status
1 is expected from the retained passage-limit failure. The candidate model must
be downloaded once before running that benchmark offline. Fresh labels and
sources can be regenerated with `evaluation.acquire_fresh`; context sidecars use
`evaluation.context_inputs`. The original synthetic evaluator is singleton-only;
use `evaluation.real_evaluate` for group-aware metrics and the saved historical
artifacts for the original synthetic release numbers.

Next useful work is human adjudication of these labels, a less aggressive scope
policy evaluated on new pages, and more natural split/merge examples. These
fresh pages have now been inspected and must not be treated as an unseen holdout
for further tuning.
