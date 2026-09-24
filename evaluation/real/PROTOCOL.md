# Real revision diagnostic protocol

This evaluation was specified before running either backend on these pages.
Question: does the frozen passage alignment plus NLI pipeline retain useful
alignment and material-change precision on whole, naturally revised prose pages?
The lexical backend is the paired baseline. No training or threshold tuning is
permitted in this pass. This is a diagnostic sample, not a population estimate.

## Sampling and inputs

Eight historical version pairs from three permissively licensed repositories:
Flask 1.1.4 to 3.1.0 (deployment, design, security), pytest 6.2.5 to 8.3.5
(flaky tests, good practices, import paths), Requests 2.25.1 to 2.32.3 (FAQ,
advanced usage). Sources were selected for prose, revision diversity and known
licensing before model predictions were viewed. Comparisons span multiple
releases, not adjacent commits. All are English technical documentation; this
does not establish performance on contracts, policies, news, or other languages.

Keep complete raw source pages, exact commits, URLs, checksums, licenses and
Requests NOTICE. Deterministically exclude code/literal blocks, navigation
toctrees, reference targets, comments and version directives. Retain headings,
lists, ordinary prose and admonition bodies. Strip inline RST roles and explicit
link destinations, retaining explicit labels. Implicit cross-references cannot
be resolved without the surrounding Sphinx project; their target names remain
and can cause markup-only differences. Single-star emphasis and reference
suffixes remain to avoid corrupting literal wildcards. Explicit link-target-only
changes are outside the task. Preserve a source-line omission audit. Do not shorten pages
to satisfy app limits. Extraction is a corpus-specific adapter, not RST input
support in the app. Annotation applies to the complete extracted prose page.
Loss of code and reference context is a limitation and must be reported.

The Requests advanced page is an unannotated coverage stress case, selected
because its complete source is long. Its runtime outcome must be reported,
whether it succeeds or fails. All seven other pages receive annotations.

## Annotation

Annotate before seeing pipeline predictions. Exact equal paragraphs may seed
unchanged groups, but inspect context and relocation. Each passage appears in
exactly one group with old/new index lists; a group may represent 1:1, a split,
a merge, or a complex rewrite. Use the smallest defensible group. Correspondence
means the same discussion or proposition is being revised, not merely similar
vocabulary. Added/removed events normally contain one passage each. Retain
ambiguity as uncertain with rationale rather than forcing a label.

Statuses: unchanged (same prose), reworded (same information with changed
expression), modified (changed assertion, recommendation, scope, or substantive
detail), added, removed, uncertain. Clarification that adds substantive detail
counts as modified. A heading wording change with unchanged subject is reworded.
Groups reflect document editing correspondence, not factual truth of upstream
claims. A prose sentence introducing a removed code sample can remain unchanged;
the excluded code itself is not labeled.

Labels are AI-authored and independently AI-reviewed where recorded. They are
provisional and require human validation. Record rationale, reviewer changes,
and the final pre-prediction annotation hashes. Never describe them as human
ground truth. No dataset split or training is needed for this frozen diagnostic;
future tuning would turn these pages into development data and require new
held-out repositories/revisions. Public model pretraining overlap is unknown.

## Metrics and failures

Report all eight runtime outcomes for each backend. Include validation, input
length and model failures in the failure rate. Do not silently substitute a
shortened page or another backend. Metrics apply only to successful annotated
pages; always show those counts next to metrics.

Alignment edge precision/recall/F1 expands a paired annotation group into the
Cartesian product of its old and new passages. This measures membership of a
shared revision group; complex rewrites may overexpand true fine-grained links.
Exact group correspondence coverage is stricter. One-to-one matching cannot
fully recover split/merge groups, so report their counts and results separately.

End-to-end material group precision/recall/F1 gives credit only when the exact
old/new group and material decision match. Wrong correspondence receives no
material credit. Also report status confusion and material precision/recall
conditional on correctly aligned singleton events, with explicit coverage.
This separates correspondence failures from classification failures, but the
conditional result cannot describe unaligned cases. Unknown gold decisions are
excluded from classification denominators and their counts are visible.

Pool integer counts for micro metrics and also publish per-document results.
Report changed-group alignment separately from exact unchanged matches so
large unchanged regions cannot conceal failure on edits. Report errors and
abstentions, including material changes classified as equivalent. Use one
deterministic run per backend. Timing is descriptive on this machine, not a
hardware benchmark. No inferential significance claim from three repositories.
Stop after both full runs, checks, error analysis and a human-review packet.
