# Resume preparation: execution contract

Approved by the user on 2026-09-24: finish the remaining engineering, evaluation,
publication preparation and portfolio work, with extra attention to Gradio and
visual design. Human annotation review will be done by the user afterward.

## Frozen starting point

Version 2 code, tests, UI and evaluation helpers are preserved in
`artifacts/evaluation/baseline-v2.zip`, SHA-256
`3bacea10cd029a5fff2ca3161fba40d0a4b223c3384540f94e3e4c21fd3e674f`.
All earlier source corpora, annotations, freezes and result artifacts stay intact.
Their source hashes describe those historical versions, not subsequent code.

## Changes and falsifiable expectations

1. Scope policy: avoid marking a child materially modified solely from narrative
   edits in an ancestor. Preserve real scope uncertainty; allow established
   contextual equivalence to survive the identical-body override. Consolidate
   repeated inherited reviews in the UI using physical source-owner IDs. Report
   raw uncertain passages separately from distinct review tasks. A reduced UI
   task count is not a gain in classification accuracy.
2. Details: retain exact source spans and separator punctuation in localized
   evidence. Verify that nonempty evidence excerpts are source substrings.
3. UI: improve visual hierarchy, source navigation, evidence panels, examples,
   responsive layout and keyboard focus, preserving export and stale-result
   behavior. Use native Gradio, CSS and source-derived visuals.
4. Evaluation: collect a bounded new blind corpus under a preregistered selection
   protocol, independently review AI labels, freeze the engine before inference,
   compare archived v2 and current predictions, and report every failure. Earlier
   real/fresh-v2 pages are now known development data. Human validation cannot be
   performed by AI; a separate offline form exports pending review submissions.
5. Release: a short recorded demonstration, architecture/results visuals, concise
   README, interview notes, actual CI checks and a clean publication bundle.
   Hosting must use available authorization and free resources; no paid plan or
   hardware will be purchased. Static recorded examples must not imply live NLP.

## Local LLM experiment, fixed before inference

Task: classify the same 35 gold-aligned changed singleton development passage
pairs used by `evaluation.compare_nli`: 17 modified, 18 reworded. No alignment,
heading context, additions/removals or split/merge scoring is involved. This is
known development data with provisional AI-reviewed labels, not new holdout data.

Candidate: locally cached Ollama `qwen2.5:7b-instruct`, digest
`845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e`.
Use fixed instructions, structured JSON, temperature 0, seed 0, an 8192-token
context, and at most 512 generated tokens. The prompt treats passage content as
data and requests a status, a concise reason, and exact evidence from both sides.
No prompt revisions based on benchmark outcomes. No downloads or hosted API fees.

Compare against preserved MiniLM individual-call predictions and an always-
material baseline. Also simulate replacing only MiniLM's uncertain decisions
with valid LLM decisions. The LLM is evaluated on all pairs to expose its own
errors, although the fallback uses only the predetermined uncertain subset.

Primary metric: material precision/recall/F1 on identical pairs, counting review
as a miss. Secondary: complete status confusion, material-as-equivalent misses,
abstentions, malformed responses, literal evidence validity, latency and token
counts. Literal quote validity checks provenance, not reasoning correctness.
Manually inspect generated explanations for unsupported claims after the run.

Hypothesis: the fallback resolves some uncertain pairs without more material-as-
equivalent misses. Equal/worse F1 or extra false equivalences is evidence against
adoption. Invalid JSON, non-source quotes and incomplete generation are recorded
and become review, never dropped. Report all failures. One pass per pair; no
model/prompt search. Temperature zero does not guarantee bitwise reproducibility
across hardware/runtime versions. Preserve request settings, model digest, raw
responses, code hashes and dataset hashes.

The local LLM may use the RTX 4070 GPU; the production MiniLM baseline uses CPU.
Their timings describe different deployment choices, not an equal-hardware speed
comparison. Local electricity/compute cost is not estimated. The LLM will remain
an experiment unless separate deployment validation justifies integrating it.
