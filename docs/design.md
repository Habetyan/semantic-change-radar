# Semantic Change Radar: current design

Build a local-first English document comparison demo for product documentation,
policies, and specifications. The user approved autonomous implementation of this
project on 2026-09-24. Work stays in this new repository; publishing is deferred.

## User flow

Paste two short documents or load a curated example. Compare them, scan material
changes, and inspect aligned source passages. Separate moved/unchanged text and
wording-only edits from changed meaning. Download an inspectable JSON report.

## Implementation

- Python and Gradio 6.28.0. CPU inference, no API key, no external LLM service.
- Lightweight ONNX MiniLM embeddings align passages independently of position.
  Global assignment includes unmatched passages; exact matches are handled first.
- Bidirectional natural language inference assesses equivalence and asymmetric
  changes. Explicit numeric, negation, modality, and condition changes provide
  conservative review signals. Scores are model outputs, not calibrated certainty.
- A clearly labeled lexical baseline works without model downloads. Never silently
  substitute that baseline when semantic models fail.
- English, plain text/Markdown, at most 30,000 characters and 80 passages per
  document. Heading/list context and bounded adjacent 1:2 / 2:1 grouping extend
  the singleton assignment. Changed clauses can veto equivalence and request
  review. Larger rewrites remain a limitation; nothing is silently truncated.
- Fixed model revisions, small quantized CPU models. No training in the UI.

## Shared API contract

`radar.compare.compare_documents(old_text, new_text, backend="semantic", *,
profile="verified", old_contexts=None, new_contexts=None) -> dict` returns
JSON-safe values. Optional context sidecars preserve frozen evaluation passage
IDs; normal app inputs derive context directly from text. Profiles are cumulative:
`baseline`, `context`, `groups`, `verified`.

```json
{
  "schema_version": 2,
  "engine": "semantic",
  "configuration": {
    "profile": "verified",
    "context": true,
    "groups": true,
    "detail_verification": true,
    "max_group_size": 2
  },
  "old_count": 3,
  "new_count": 3,
  "elapsed_ms": 42.0,
  "warnings": [],
  "models": {},
  "changes": [{
    "id": "change-1",
    "old_index": 0,
    "new_index": 1,
    "old_indices": [0],
    "new_indices": [1],
    "old_text": "Guests can export reports.",
    "new_text": "Only administrators can export reports.",
    "old_parts": [{"index": 0, "text": "Guests can export reports."}],
    "new_parts": [{"index": 1, "text": "Only administrators can export reports."}],
    "old_context": [],
    "new_context": [],
    "context_changed": false,
    "status": "modified",
    "category": "Permission change",
    "explanation": "Access wording changed; review the aligned passages.",
    "moved": true,
    "alignment_score": 0.9,
    "old_entails_new": 0.1,
    "new_entails_old": 0.2,
    "contradiction_score": 0.7,
    "signals": ["Access wording changed"]
  }]
}
```

The JSON above illustrates the shape, not a measured prediction. Canonical index
arrays are zero-based and empty when absent. Scalar indices retain the first
member or null for compatibility; they are insufficient for evaluating groups.
Combined text joins source members with blank lines; `parts` retain each member.
Optional `localization_evidence` records `old_quote`, `new_quote`, `reason`, and
the two directional entailment values (null if no inference fits or a side is
absent). Current excerpts preserve exact contiguous source spans; historical v2
reports may omit separator punctuation. Use `old_parts` / `new_parts` for full
source text. Context fields are present for non-exact paired comparisons.
Unchanged-body inherited reviews may include `scope_review` with physical
`old_owner_indices` / `new_owner_indices`; the UI groups matching owner pairs
without removing individual decisions from the report.

Status is one of `unchanged`, `reworded`,
`modified`, `added`, `removed`, `uncertain`. Scores are null when unavailable.
`moved` means a relative ordering inversion, not a changed index after insertion.
Public `split_passages(text: str) -> list[str]` gives the evaluation index unit.
`ValueError` represents invalid input; model initialization/inference errors are
reported to the user with a suggestion to choose the lexical baseline explicitly.

## Experimental contract

The original synthetic-release protocol below is historical. The implemented
structural follow-up uses the [stage contract](improvement-plan.md), frozen
development and fresh runs, and the [measured tradeoffs](improvements.md).

Task: align passages and distinguish material changes from equivalent rewording.
Hypothesis: embedding alignment plus bidirectional NLI reduces harmless-rewording
false alarms compared with lexical comparison, without hiding material edits.
Falsification: no improvement in held-out material-change F1 or unacceptable
material edits labeled equivalent. Measure alignment F1, material-change precision,
recall/F1, per-status errors, abstention, and latency. Use an independently authored
small synthetic fixture set, grouped by document scenario into development and
test splits. Freeze thresholds before test evaluation. No claim of real-world
accuracy or human annotation. Preserve per-example predictions and errors.

## Completion criteria

Runnable UI and CLI; real semantic-model smoke test; meaningful engine, security,
and evaluation tests; baseline and semantic evaluation artifacts; responsive UI
check; README with exact run commands, model provenance, limitations, and deployment
instructions; final diff review and a concise handoff.
