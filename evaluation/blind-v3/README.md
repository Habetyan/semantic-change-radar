# Blind v3 documentation revisions

Six complete historical Markdown revision pairs from three repositories absent
from the earlier corpora. Source selection and initial annotation used source
prose only, without comparator runs or model predictions. These are purposively
selected English software-documentation pages, not a representative sample.

The selection rules in [PROTOCOL.md](PROTOCOL.md) were written before fetching
candidate pages. [selection.json](selection.json) records all twelve screened
pairs, pinned revisions, source hashes and selection/rejection reasons. Missing
paths, unchanged content and pages exceeding the 80-passage limit were rejected.
One other qualifying page was passed over within the six-case budget. Raw rejected
pages were not retained; their available bytes are identified by SHA-256 and can
be retrieved from the pinned repository/path/commit records.

| Case | Revisions | Old/new passages | Unchanged | Reworded | Modified | Added | Removed |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Starlette responses | 0.20.0 to 0.41.0 | 51 / 54 | 48 | 1 | 2 | 3 | 0 |
| Starlette configuration | 0.20.0 to 0.41.0 | 30 / 33 | 25 | 3 | 2 | 3 | 0 |
| Black future style | 22.3.0 to 24.10.0 | 11 / 50 | 6 | 2 | 2 | 40 | 1 |
| uv cache | 0.3.0 to 0.6.0 | 38 / 55 | 32 | 2 | 4 | 17 | 0 |
| Black basics | 22.3.0 to 23.1.0 | 64 / 64 | 62 | 0 | 1 | 1 | 1 |
| Starlette WebSockets | 0.20.0 to 0.41.0 | 37 / 48 | 37 | 0 | 0 | 11 | 0 |

These counts include independent AI review of all source passages, with human
validation still pending. The sample has 19 changed paired groups, below the aspirational target of twenty, and remains
addition-heavy. All reviewed groups remain singletons; it supplies no new split/merge
evidence. The screening budget was not expanded to improve class balance. Some
rewordings are punctuation/typography repairs, not challenging paraphrases.
Visible example filenames count as prose details; excluded code is never used to
infer a label. Repeated bare introductions such as “to:” have weak standalone
meaning after code removal. Human validation remains pending.

## Reproduction

From the project root:

```sh
.venv/bin/python -m evaluation.acquire_blind
.venv/bin/python -m evaluation.acquire_blind --refresh
.venv/bin/pytest -q tests/test_blind_extraction.py
```

The downloader verifies each selected raw source against its screening hash.
The manifest records raw/extracted hashes, exact commits/dates, upstream links,
local paths, licenses and app-limit checks. Both revisions of every license are
retained per case, including both uv MIT and Apache licenses. The pinned root-tree
[license audit](license-audit.json) found no separate root NOTICE files.

The extractor is specific to these twelve audited sources. It preserves complete
prose, headings, lists, ordinary indentation, MyST warnings, note/tip bodies and
visible fenced-code titles. It omits fenced code, generated CLI-output directives,
reference destinations, horizontal rules and HTML details wrappers. HTML summary
labels, inline links/code and Python object roles retain visible text. Inline
Markdown normalization reuses the existing helper without modifying frozen code.
Single-star/underscore emphasis remains to avoid damaging literal identifiers.
Each omission and structural transformation has original source line numbers.
All unfenced indented lines were inspected as admonition bodies/list continuations.

A fresh pinned network acquisition reproduced all 72 then-existing corpus
artifacts byte-for-byte, including raw pages, licenses, extraction audits, text,
passages, annotations, selection ledger and manifest. Focused tests check visible
labels/admonition retention, unsupported directives, exact extraction reproduction
and complete annotation partitions. No model evaluation was performed during
acquisition or annotation.

Independent AI review is complete in `annotations/`, with `ai_reviewed_pending_human`
status. [review-notes.json](review-notes.json) records per-case checks and the one
label correction: Black's identical string-processing paragraph now has changed
availability scope, from preview to unstable. The repeated uv example titles retain
their distinct occurrence alignment. Original label hashes remain in
[initial-label-freeze.json](initial-label-freeze.json). No model predictions or
inference were used in this review. Human validation remains pending. Any subsequent
label change requires a new label freeze before inference.
