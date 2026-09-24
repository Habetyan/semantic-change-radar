# Fresh blind diagnostic corpus

Three complete English documentation pages were selected from repositories absent
from the earlier corpus. Source selection and initial annotation used the source
prose only, before access to model predictions. This is a purposive diagnostic
sample, not an estimate of performance on arbitrary documents.

The manifest pins full commits, original raw bytes, source links, licenses,
extracted-text hashes, and passage counts. Both versions of each license are
retained. No page was cropped to fit the application limits.

| Page | Historical interval | Raw characters, old/new | Extracted characters, old/new | Passages, old/new |
| --- | --- | ---: | ---: | ---: |
| [HTTPX compatibility, old](https://github.com/encode/httpx/blob/2038919b7e0913f83a6dc5a9f89c25aa3f975fdb/docs/compatibility.md) / [new](https://github.com/encode/httpx/blob/8e36f2bc685dfbe43cd7503bc1c422a6ed6e05a5/docs/compatibility.md) | 2020-01-08 to 2024-10-28 | 2,790 / 9,472 | 2,472 / 7,494 | 30 / 77 |
| [pip caching, old](https://github.com/pypa/pip/blob/d63f06a881a54823fcc4798989d532797e772789/docs/html/topics/caching.md) / [new](https://github.com/pypa/pip/blob/d5e3f0c4b4d6aa4b432cd5480abb234e2e3332fb/docs/html/topics/caching.md) | 2021-06-11 to 2023-09-06 | 3,355 / 4,994 | 3,205 / 4,671 | 25 / 45 |
| [MkDocs deployment, old](https://github.com/mkdocs/mkdocs/blob/a84b5a27df9b0ed90c4718871e4b60d8735c416b/docs/user-guide/deploying-your-docs.md) / [new](https://github.com/mkdocs/mkdocs/blob/53fec50e57f6bad152ad589a83ae83d1cd72b2f5/docs/user-guide/deploying-your-docs.md) | 2019-06-23 to 2024-04-25 | 7,915 / 9,533 | 6,300 / 7,695 | 30 / 41 |

The corresponding licenses are
[HTTPX BSD-3-Clause](https://github.com/encode/httpx/blob/8e36f2bc685dfbe43cd7503bc1c422a6ed6e05a5/LICENSE.md),
[pip MIT](https://github.com/pypa/pip/blob/d5e3f0c4b4d6aa4b432cd5480abb234e2e3332fb/LICENSE.txt), and
[MkDocs BSD-2-Clause](https://github.com/mkdocs/mkdocs/blob/53fec50e57f6bad152ad589a83ae83d1cd72b2f5/LICENSE).

## Extraction

Run from the project root:

```sh
.venv/bin/python -m evaluation.acquire_fresh
# Optionally fetch the same pinned source bytes again:
.venv/bin/python -m evaluation.acquire_fresh --refresh
```

`acquire_fresh.py` is deliberately limited to these audited Markdown pages.
It preserves heading levels, list markers, indentation, and every prose paragraph.
Visible link labels replace destinations; inline code loses its backticks; bold
markers are removed while single-star wildcards remain intact. Literal brackets
inside inline API examples are retained.

MyST version notes and cautions retain both their labels and prose. Tab labels
become fourth-level headings beneath the original Default paths subsection.
Actual fenced examples, including code-formatted paths, are omitted. Both older
Markdown admonitions and newer uppercase callouts retain their prose and are
normalized to the same visible warning/note label. Every omission and structural
transformation has a source-line audit. The only unfenced indented blocks in
these pages are admonition bodies and nested list prose; all are retained.

Example introductions remain even when the corresponding code is omitted. Their
limited standalone meaning is a known consequence of the prose-only task, and
their annotations do not infer information from the excluded code.

## Annotation and limitations

The labels were authored and independently reviewed by separate AI agents before
inference, and remain pending human validation. Review status is recorded in each
annotation file and derived from those files when the manifest is regenerated.
This is not human-validated gold data.
Every saved old and new passage index appears in exactly one event. The annotator
read all extracted passages and did not inspect model predictions.

The source revisions include a natural one-to-two URL paragraph split in HTTPX,
spelling and grammar edits with unchanged meaning, changed API assertions,
qualified caching recommendations, nested local-file configuration prose, and
removed warnings with identical text retained under a different subsection.
The MkDocs pair contains no lexical-only paraphrase after markup normalization;
no reworded label was invented to balance the classes.

Event counts after independent AI review:

| Case | Unchanged | Reworded | Modified | Added | Removed | Uncertain |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| HTTPX | 22 | 3 | 5 | 46 | 0 | 0 |
| pip | 22 | 2 | 1 | 20 | 0 | 0 |
| MkDocs | 26 | 0 | 1 | 14 | 3 | 0 |

This small corpus is dominated by additions and exact matches. Results should
therefore include per-class and per-case counts, and should not be described as
broad generalization evidence. No model output was used to select these cases
or their labels.

## Acquisition verification

All 31 generated raw/license/text/passage/audit/manifest artifacts were
byte-identical after a fresh pinned network acquisition. Raw hashes also matched
the source selection saved before annotation. Source-derived checks confirmed
retention of MyST cache migration prose, nested list indentation, and literal
bracketed API examples. All six documents passed the application's character and
passage limits. The acquisition script passed Ruff and Python compilation.
