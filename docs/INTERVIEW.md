# Interview walkthrough

## A short introduction

“I built a document-revision review tool that aligns passages and distinguishes
meaning-preserving rewrites from material edits. It combines pretrained sentence
embeddings, global assignment, bidirectional natural-language inference (NLI),
and conservative checks for changed details and source scope. I implemented the
comparison pipeline, evaluation tooling and Gradio interface. I did not train or
fine-tune the models. The results include documented successes, misses, and
review-workload tradeoffs.”

## Explain the pipeline

1. Parse each document into passages, retaining headings, list ownership and source
   locations. Reject oversized documents or original passages instead of silently
   truncating them. Optional context that exceeds the token budget goes to review;
   oversized optional group candidates are skipped.
2. Match exact text in compatible scope. Embed remaining passages with MiniLM and
   use global one-to-one assignment with unmatched options. This avoids assigning
   several old passages to the same new passage through independent nearest-neighbor
   searches, while still allowing passages to move.
3. Refine eligible matches with adjacent 1:2 or 2:1 groups within the same scope.
   Both fragments must support correspondence; a non-exact candidate must improve
   the existing score by a fixed margin. This is bounded refinement, not arbitrary
   many-to-many alignment or a globally optimal grouped assignment.
4. Run NLI in both directions on aligned candidates. A one-way implication can
   signal added or removed information; high similarity alone cannot establish
   equivalence. Inspect changed quantities, conditions and localized detail spans
   before accepting a rewrite. Unresolved evidence becomes “Needs review.”
5. Show original passages, source context, localized evidence and an exportable
   JSON report in Gradio. The UI helps inspect decisions; it does not verify the
   factual truth of the source documents.

The production models are pinned quantized ONNX checkpoints running on CPU. A
lexical baseline separates the benefit of learned representations from the rest
of the pipeline. Relevant implementation: [comparison](../radar/compare.py),
[group refinement](../radar/grouping.py), [structure](../radar/structure.py),
[detail checks](../radar/details.py), and [presentation](../radar/presentation.py).

## Questions to be ready for

**Why both embeddings and NLI?** Embeddings find plausible correspondence between
rewritten passages. NLI tests directional implication once a correspondence is
proposed. Neither is a truth checker, and both can miss small consequential edits.
A classifier result on the wrong aligned pair is still an end-to-end failure.

**What did context improve, and what went wrong?** The same sentence can mean
something different beneath a different heading or list owner. Context helps
identify that case, but broad ancestor narrative changes also created false
alerts. The current policy does not automatically promote inherited changes to
material edits. Unresolved scope differences remain review decisions, while
established contextual equivalence can survive identical-body handling.

**Is grouping review cards an accuracy improvement?** No. Correspondence groups
model actual splits/merges. UI review-task grouping instead combines repeated
scope alerts using their physical source-owner IDs. Raw uncertain passages remain
in the report. Fewer visible tasks do not mean fewer classification errors.

**How did you evaluate it?** First with 32 synthetic document pairs (18 development,
14 initially held out), then with complete historical documentation revisions.
The original eight real pairs include one intentionally over-limit stress case.
Later corpora add three fresh-v2 pairs and six blind-v3 pairs from three further
repositories. Sources, licenses, extraction omissions, labels and engine versions
are recorded. Once results are inspected, those pages are no longer unseen for
subsequent tuning. [Annotation provenance and author review](annotation-provenance.md)
records how the reference labels were prepared and the author's confirmation.

Use the [current results](resume-results.md) for the final v3 numbers and exact
coverage. The [v2 report](improvements.md) illustrates the tradeoff: one natural
split was recovered and two material edits previously accepted as equivalent
became review, but paired material detection remained 5/7. “Zero material edits
called equivalent” did not mean every edit was detected. Report changed-pair
alignment and exact material-group precision/recall alongside additions, unchanged
regions, uncertainty and every runtime failure. The new six-pair sample is still
addition-heavy and contributes no new split/merge groups.

**Why not use a larger NLI model?** On 35 known development pairs with gold
alignment, fixed thresholds and individual inference calls, DeBERTa v3 small had
material F1 .571 versus MiniLM's .611. Its warm median for 70 directional calls
was 1.634 s versus .957 s, with larger weights. It was not adopted. That is evidence
about this configuration and sample, not a general ranking of model families.
See the [controlled comparison](improvements.md#alternative-nli-model-and-batch-sensitivity).

**What reproducibility issue did you find?** The same quantized NLI input produced
materially different scores with unrelated batch neighbors. One reverse-entailment
score was .8795 in the original document batch, .4986 in a two-direction batch,
and .5413 alone. Archived code reproduced the original behavior. The cause was
not isolated: padding and dynamic quantization are hypotheses. Individual NLI
calls removed the tested neighbor dependence, with a saved check showing zero
probability difference. That does not establish cross-platform determinism or
embedding-batch invariance.

**Did a generative LLM solve the difficult cases?** No. A fixed-prompt, cached
Qwen2.5 7B run on those same 35 known, gold-aligned DEV pairs produced 13 invalid
literal quotations, all retained as review decisions. Standalone material F1 was
.579. Simulated fallback on MiniLM's nine uncertain pairs reached .650 versus
.611 baseline, but resolved two material abstentions while adding two false
alarms. An always-material baseline scored .654 on this deliberately changed-pair
slice. Those numbers do not justify deploying the LLM.

The [separate explanation audit](../artifacts/evaluation/v3-llm-qwen/explanation-audit.json)
classified 18 reasons as supported, 10 as overinterpreting rewrites and seven as
containing unsupported assertions. These are provisional audit judgments. A
supported reason does not necessarily justify the predicted status. For example,
the model correctly classified a Flask passage as modified but falsely said that
iterative template rendering had been added; that phrase appeared on both sides.
Valid source quotations therefore establish provenance, not reasoning correctness.
The CPU NLI and potentially GPU-backed Ollama timings are not equal-hardware
comparisons. Qwen remains an experiment, not a production dependency.

**What would you do next?** Obtain additional independent judgments on correspondence
and meaning, adjudicate disagreements without overwriting historical labels, then
collect new unseen sources for any subsequent tuning. Measure review burden as
well as missed material edits. Broader document genres and larger rewrite/group
samples are needed before making generalization claims.

## Resume wording

Use only claims you can explain and reproduce:

- Built a Python/Gradio document-revision review tool using pretrained MiniLM
  embeddings, global passage alignment and bidirectional NLI, with bounded
  split/merge handling and inspectable source evidence.
- Implemented reproducible evaluation on synthetic fixtures and pinned historical
  documentation revisions, including provenance, grouped metrics, explicit
  failure accounting and an offline annotation-review workflow.
- Compared quantized NLI and a local 7B LLM on 35 development passage pairs;
  documented batching sensitivity, evidence-validation failures and precision,
  recall and review tradeoffs before retaining the smaller production model.

Avoid claiming a trained model, human-validated accuracy, production adoption,
state-of-the-art performance, or a percentage improvement without naming its
corpus, denominator, baseline and annotation limitations.
