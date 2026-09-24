# Real document revisions: 2026-09-24

The frozen semantic pipeline did not show a clear overall advantage over the
lexical baseline on this diagnostic sample. It reduced false material alerts,
but lost recall and introduced two incorrect equivalence decisions. Substantial
rewrites exposed weak alignment and the inability to represent paragraph splits
and merges. The earlier synthetic results were too favorable to describe these
cases.

**These are authentic historical source revisions with provisional AI-reviewed
labels, not human-validated ground truth.** Seven annotated pairs completed on
both backends. The eighth, an unannotated long-page stress case, failed the same
input limit on both. No model, threshold or production code was changed in
response to this evaluation.

## Corpus and protocol

The corpus contains complete page snapshots from Flask 1.1.4 to 3.1.0, pytest
6.2.5 to 8.3.5, and Requests 2.25.1 to 2.32.3. The pages were deliberately chosen
before predictions for a mixture of major rewrites, local changes, unchanged
context and available licenses. They span multiple releases. They are not a
random sample of edits or representative of nontechnical documents.

Original RST files, exact commit URLs, checksums and licenses are retained in
the [manifest and corpus](../evaluation/real/README.md). A deterministic adapter
removes code blocks, navigation and some markup, without shortening prose to fit
the app. Source-line omission audits are included. All ordinary prose,
headings and list items remain. References without explicit labels cannot be
fully rendered outside the upstream Sphinx projects; these identifiers and
sentences introducing removed code are an extraction limitation.

One AI agent annotated each page before predictions; a different agent reviewed
it. One correspondence was revised during review: pytest's new explanation of
`sys.modules` was linked to the old assertion it reverses, despite appearing
farther down the page. Two unresolved cases remain `uncertain`. The final labels
were [hashed before inference](real-evaluation-freeze.json), following the
[pre-run protocol](../evaluation/real/PROTOCOL.md). The production code also
matches the [initial engine snapshot](real-evaluation-engine-freeze.json).

The seven annotated pairs contain **256 old and 324 new passages**, partitioned
into 320 revision groups: 204 unchanged, 25 modified, 65 added, six removed,
18 reworded and two uncertain. Eight groups contain splits or merges. There are
260 paired correspondence edges, of which only 56 are in changed groups.

## Results

All scores below use the **seven successful annotated pairs**. Both backends
completed seven of eight requested pages; the observed all-case failure rate
was **12.5%**. This rate is descriptive, since the long page was deliberately
selected as a stress case.

| Metric | Lexical | Semantic |
|---|---:|---:|
| All paired-edge alignment F1 | 0.960 | 0.956 |
| Changed paired-edge alignment F1 | 0.787 | 0.771 |
| Changed paired-edge recall | 37/56 (66.1%) | 37/56 (66.1%) |
| Exact group correspondence recall | 306/320 (95.6%) | 304/320 (95.0%) |
| End-to-end material precision | 86/131 (65.6%) | 80/113 (70.8%) |
| End-to-end material recall | 86/96 (89.6%) | 80/96 (83.3%) |
| End-to-end material F1 | 0.758 | 0.766 |
| Material alerts without exact labeled material correspondence | 45 | 33 |
| Labeled material groups without a correct material prediction | 10 | 16 |
| Total abstentions | 0 | 7 |

The semantic F1 difference is only 0.008 on these labels. This is not evidence
of a general improvement. The precision/recall tradeoff is more informative:
12 fewer incorrect material alerts, but six fewer correctly recovered material
groups. No statistical significance or population confidence claim is made.

Alignment expands a split/merge annotation into all old/new group-member edges.
Exact material credit requires the complete group correspondence and a material
status. This intentionally penalizes a partial match plus spurious additions.
Neither one-to-one backend can exactly recover the eight split/merge groups.
Three lexical and four semantic material predictions touching ambiguous labels
are excluded from precision; ambiguity remains in alignment scoring.

| Document | Passages old/new | Lexical changed alignment F1 | Semantic changed alignment F1 | Lexical material F1 | Semantic material F1 |
|---|---:|---:|---:|---:|---:|
| Flask deployment | 10/17 | 0.625 | 0.667 | 0.483 | 0.500 |
| Flask design | 32/38 | 0.800 | 1.000 | 0.857 | 0.889 |
| Flask security | 61/65 | 1.000 | 1.000 | 1.000 | 1.000 |
| pytest flaky tests | 54/70 | 1.000 | 0.000 | 0.973 | 0.947 |
| pytest good practices | 47/62 | 0.872 | 0.842 | 0.643 | 0.627 |
| pytest import paths | 31/50 | 0.696 | 0.609 | 0.745 | 0.696 |
| Requests FAQ | 21/22 | 0.857 | 1.000 | 0.727 | 1.000 |
| Requests advanced | 149/158 | Failed | Failed | Not scored | Not scored |

The flaky-tests page has only one changed paired correspondence, so its 0.000
semantic result is one missed edge, not failure on every passage. Most new
content there consists of additions. Requests advanced contains 22,927/25,072
extracted characters but exceeds the **80-passage** limit. It was neither
truncated nor silently excluded. Both commands wrote its failure and returned
exit code 1 after processing the full manifest.

## Classification versus alignment

Conditional scoring includes only exact, correctly aligned singleton groups.
Coverage was 305/310 eligible groups for lexical and 304/310 for semantic.
Overall conditional status accuracy was 95.1%/95.4%, but unchanged text and
additions/removals dominate that number.

Looking only at correctly aligned **changed 1:1 pairs**, semantic classification
was correct on **17/31 (54.8%)**, compared with lexical's 15/30 (50.0%). These are
different aligned subsets, so this is descriptive rather than a controlled
classifier comparison. Semantic classified the 15 matched material revisions
as 11 modified, two reworded and two uncertain. Of 16 matched benign rewrites,
six were reworded, six modified and four uncertain.

Concrete semantic failures, with zero-based passage IDs:

| Case | Expected change | Observed behavior |
|---|---|---|
| Flask design `old[17] → new[17]` | A sentence loses the assertion that Jinja uses Unicode for all operations. | Called reworded, with entailment 0.8820/0.8697. The changed detail is buried in a long feature list. |
| pytest good practices `old[23] → new[29]` | Conditions for running tests change from lacking `setup.py` to lacking an editable install and a `src` layout. | Called reworded, with entailment 0.8738/0.8795 and no guard signal. |
| pytest import paths `old[5] → new[15]` | The old paragraph concerns `prepend`; the new paragraph concerns `importlib`. They are not corresponding revisions. | Matched them and reported a change to the uniqueness requirement. Missing section context produced a false relationship. |
| Flask deployment `old[1] → new[9]` | The old development-server warning corresponds to new paragraphs 1 and 2. | Matched it to a hosting-platform overview and abstained; the actual split was lost. |
| Flask design `old[10] → new[10]` | Factory-function advice is unchanged; an unresolved reference identifier differs. | Reported modified. This is partly an extraction artifact. |

The first two are risky misses on correctly aligned passages, not alignment
errors. The import-path and deployment examples show a separate failure in
choosing the evidence to compare. NLI scores are not calibrated confidence.

## Runtime, verification and next work

Both runs used the existing pinned CPU ONNX models and environment. Median
successful-page time was **4.6 ms lexical / 337.5 ms semantic**. First semantic
call took 939.2 ms; the slowest took 1,168.8 ms. Measurements include file loading
and scoring; both backend processes were launched together, so these are rough
local observations rather than controlled performance comparisons. Downloads
were disabled for semantic inference.

Saved evidence: [lexical summary](../artifacts/evaluation/real-lexical/summary.json),
[semantic summary](../artifacts/evaluation/real-semantic/summary.json),
[lexical predictions](../artifacts/evaluation/real-lexical/predictions.jsonl),
[semantic predictions](../artifacts/evaluation/real-semantic/predictions.jsonl),
and [verification](../artifacts/evaluation/real-verification.json).
All 96 frozen files matched after inference. Tests passed: 44, with one opt-in
model unit test skipped; actual semantic inference ran on the complete corpus.
Ruff checks passed. The standalone annotation page's filters were exercised in
Chrome with no JavaScript errors.

The next engineering priority is section-aware correspondence with explicit
split/merge handling. The next classification question is whether sentence-level
evidence can catch changed details without discarding surrounding conditions.
Those are hypotheses to test, not implemented improvements. Human validation of
the [annotation packet](../evaluation/real/review.html) should precede reliance
on the exact scores. Any tuning on these inspected pages requires new held-out
repositories/revisions for evaluation. Public pretraining overlap is unknown.
