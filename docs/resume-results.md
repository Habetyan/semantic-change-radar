# Resume preparation: results and release notes

The Gradio workspace now has clearer source/evidence panels, a source-order passage
map, grouped scope-review tasks, three real historical examples, and a recorded
walkthrough. A separate offline form prepares human annotation review. The runtime
still uses the original pinned MiniLM embedding and NLI models on CPU.

The matching changes **do not improve accuracy on the new blind set**. They make
inherited scope decisions more conservative and reduce duplicate review work.
The local LLM experiment also exposes substantial evidence and explanation errors.
These limitations are part of the release, not omitted unsuccessful experiments.

## Interface and evidence

- Shared uncertainty from the same physical heading/list owner is one expandable
  review task. Each affected card and original source index remains inspectable.
  Raw uncertain entries and before/after passage counts are reported separately.
- The passage map uses actual source indices/statuses. It does not represent
  confidence or model attention.
- Localized excerpts now slice exact original spans, retaining internal commas
  and semicolons. Every nonempty excerpt is tested for source-substring membership.
  Historical v2 exports can contain normalized excerpts and are left unchanged.
- Source provenance accompanies the HTTPX, pip and MkDocs examples. They are
  complete extracted historical pages, not statements about current APIs.
- JSON export, filters, group members, stale-input notices, keyboard focus, and
  mobile layout are preserved and exercised in Chrome.

[Walkthrough](images/walkthrough.mp4) · [Gradio screenshot](images/demo.png)
· [Offline annotation review instructions](review/README.md)

## Scope policy and development tradeoff

The earlier implementation could mark a child modified solely because an ancestor
lost a narrative phrase such as “until recently”. Now inherited markers request
review rather than proving a change to the child. Established strong contextual
equivalence can survive the identical-body override; actor/access-heading guards
retain review for examples such as Guests→Members and Free→Paid. These guards are
finite heuristics, not comprehensive semantic understanding.

The earlier real corpus is development data. Seven annotated cases score; Requests
advanced remains an explicit failure at 149/158 passages, beyond the 80 limit.

| Development measure | Archived v2 | Current |
|---|---:|---:|
| Changed alignment F1 | .7609 | .7609 |
| All-event material precision | .6640 | .6838 |
| All-event material recall | .8646 | .8333 |
| All-event material F1 | .7511 | .7512 |
| Paired material detection | 13/25 | 10/25 |
| Paired material F1 | .4815 | .4348 |
| Raw uncertain entries | 40 | 45 |
| UI review tasks | 40 separate entries | 20 tasks |

Three false material child predictions become reviews, but three genuine material
predictions also become reviews. Raw uncertainty does not decrease. Of 45 current
uncertain entries, 32 share seven physical scope changes; the other 13 remain
individual tasks. Grouping reduces queue duplication, not the underlying error rate.
The current default deliberately avoids treating inherited narrative signals as
proof, with the recall cost shown above. The feature-disabled `baseline` CLI
profile remains available; it is a different tradeoff, not a recommended universal fix.

## New blind diagnostic

Selection rules were fixed before acquisition. Exactly twelve candidates were
screened by source/diff only, yielding six complete Markdown revision pairs from
three repositories absent from earlier evaluations: Starlette, Black, and uv.
The rejection ledger, full commits, original bytes, licenses, deterministic prose
extraction and omission audits are in [blind-v3](../evaluation/blind-v3/README.md).
No page was cropped to pass input limits.

Initial annotation and independent review occurred without predictions. The
reviewer corrected one availability change in Black despite unchanged body text.
Labels and the author's subsequent review are documented in
[annotation provenance](annotation-provenance.md). There are 306 groups:
210 unchanged, eight reworded, eleven modified, 75 added and two removed. These
cover 231 old and 304 new passages. There are 19 changed paired groups and **no
split/merge groups**, so this set cannot establish split/merge generalization.

The [core freeze](v3-engine-freeze.json) preceded access to new corpus content;
the [full freeze](blind-v3-freeze.json) followed independent annotation review and
preceded every new-corpus prediction. The engine was not tuned afterward. All six
cases completed under every compared configuration.

| Configuration | Changed alignment F1 | Material P | Material R | Material F1 | Risky equivalences | Raw reviews |
|---|---:|---:|---:|---:|---:|---:|
| Lexical baseline | .9231 | .8842 | .9545 | .9180 | 1 | 0 |
| Semantic baseline, features disabled | .9231 | .9412 | .9091 | .9249 | 4 | 2 |
| Archived v2 verified | .9474 | .9529 | .9205 | .9364 | 1 | 9 |
| Current verified | .9474 | .9529 | .9205 | .9364 | 1 | 9 |

All-event material scoring requires the exact gold group and includes additions
and removals, which dominate this corpus. Current paired-only precision/recall/F1
is **.8333/.4545/.5882**, correctly classifying **5/11** material revisions.
“Risky equivalences” counts exactly aligned singleton material edits labeled
unchanged/reworded; it is not the number of all missed material edits.

Archived v2 and current v3 produce identical alignment/status decisions on this
set. Three scope-review entries form one task, giving **nine entries in seven
tasks** in the new UI. Median current comparison time was 352 ms, from one run
per case with cached models. Archived timing excludes parent scoring/file loading,
so it is not an exactly equivalent latency measurement.

Observed failures:

- Black changes availability from preview to unstable in surrounding document
  prose while retaining the string-processing paragraph. Both versions incorrectly
  accept that paragraph as unchanged. Local heading/list structure misses this
  document-level dependency.
- Four uv material edits remain uncertain. Localized checks prevent false
  equivalence on three of them compared with the feature-disabled baseline, but
  this capability already existed in v2.
- One Starlette revision is misaligned. Repeated `pyproject.toml:` text also
  produces an addition-index error. Exact duplicate text does not determine its
  correct document occurrence.

The previously inspected HTTPX/pip/MkDocs corpus was rerun only as known regression
data. Alignment/status outcomes remain unchanged: paired material detection 5/7,
material F1 .9663 including additions, and the sole gold split recovered 1/1.
Development split recovery remains 0/8. Neither figure supports broad grouping claims.

## Local LLM verifier experiment

The [fixed experimental contract](resume-plan.md) was written before generation.
Used locally cached Ollama Qwen 2.5 7B Instruct, Q4_K_M, model digest
`845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e`, temperature 0,
seed 0, JSON-schema output, and one pass over the same 35 gold-aligned development
pairs used in the earlier NLI comparison. Seventeen are modified and eighteen
reworded. No headings, alignment, additions, or new blind examples are involved.

Each response must provide a status, explanation, and nonempty literal evidence
from both inputs. Invalid quotes, malformed responses, or incomplete generation
become uncertain and remain in the denominator. No response was silently dropped.

| Configuration | Material P | Material R | Material F1 | Reviews | Material-as-equivalent misses |
|---|---:|---:|---:|---:|---:|
| Preserved MiniLM decisions | .5789 | .6471 | .6111 | 9 | 1 |
| Qwen on every pair | .5238 | .6471 | .5789 | 14 | 0 |
| Qwen only replaces MiniLM uncertainty | .5652 | .7647 | .6500 | 5 | 1 |
| Always predict material | .4857 | 1.0000 | .6538 | 0 | 0 |

All 35 calls returned, but **13/35 failed literal quote validation**. The saved
summary therefore marks `complete: false`, while retaining all 35 scored outcomes.
The fallback uses nine predetermined uncertain pairs: it resolves two material
abstentions and adds two false material alarms. It cannot repair the baseline's
equivalence miss because that pair is not routed. Its F1 remains below the trivial
always-material baseline, although it retains six correct benign rewrites.

A separate explanation audit found 18 supported
reasons, ten overinterpretations and seven unsupported assertions across all raw
responses; its provenance is recorded in the [annotation note](annotation-provenance.md).
Quote validity does not establish explanation correctness. For example,
the Flask Unicode-removal pair received the correct modified label but a false
reason claiming iterative rendering was newly introduced, although it appeared on
both sides. A capitalization-only heading edit had valid quotes but an incorrect
material label.

The run took 122.45 seconds total, with median 2.88 seconds per pair and a 9.04-second
first call including model loading. Ollama reported about 5.34 GB resident in VRAM
on the RTX 4070 laptop GPU. The CPU MiniLM and GPU LLM are different deployment
choices, not an equal-hardware speed comparison. There were no hosted API charges;
electricity/compute cost was not estimated. No model was downloaded or fine-tuned.

The candidate remains an experiment and is not in the Gradio inference path.
[Raw outputs and configuration](../artifacts/evaluation/v3-llm-qwen/)
· [Explanation audit](../artifacts/evaluation/v3-llm-qwen/explanation-audit.json)

## Verification and reproduction

The independent [v3 audit](../artifacts/evaluation/v3-audit.json) recomputed all
six run summaries and per-case metrics, checked every successful source partition
and source text, and verified current source hashes, seven engine-freeze files,
93 blind-freeze files and 31 archived v2 members. No inference failures were hidden.
Historical snapshots/results remain unchanged; their old source hashes describe
the archived code rather than today's files.

```bash
# Current new-corpus result. Write a new output directory.
HF_HUB_OFFLINE=1 python -m evaluation.real_evaluate \
  --manifest evaluation/blind-v3/manifest.json --backend semantic \
  --profile verified --output artifacts/local/v3-blind

# Isolated historical engine, same group metrics.
HF_HUB_OFFLINE=1 python -m evaluation.evaluate_archive \
  --archive artifacts/evaluation/baseline-v2.zip \
  --manifest evaluation/blind-v3/manifest.json --output artifacts/local/v2-blind

# Optional local Ollama experiment, pinned cached model required.
python -m evaluation.compare_llm --output artifacts/local/qwen-comparison

# Combined offline human-review packet.
python -m evaluation.review_packet \
  --manifest evaluation/fresh-v2/manifest.json \
  --manifest evaluation/blind-v3/manifest.json --output docs/review/index.html
```

The [handoff](HANDOFF.md) records final tests, browser checks and publication status.
The current new set has now been inspected and must not be reused as an unseen
holdout for later tuning. The author's confirmation of the measurements is recorded
in [annotation provenance and author review](annotation-provenance.md).
