# Blind v3 source-selection protocol

Frozen before fetching candidate source pages on 2026-09-24.

Select up to six complete historical Markdown documentation revision pairs from
at least three repositories absent from earlier corpora. Exclude HTTPX, pip,
MkDocs, Flask, pytest, and Requests. Screen at most twelve pairs and retain a
selection ledger, including rejections. Prefer focused prose pages with actual
rewrites rather than mostly additions. Seek at least twenty changed paired groups
in total, but report the observed count without inventing changes or relabeling
unchanged meaning. Selection is purposive, not random or population-representative.

Use only source prose, raw diffs and deterministic extraction while selecting and
annotating. Do not run or inspect comparator/model predictions. Pin complete commit
IDs and retain original source bytes, source URLs, both revisions of licenses and
required notices, SHA-256 hashes, full extracted prose, passage arrays and line-level
omission audits. No truncation or excerpt selection. Reject pages exceeding 30,000
extracted characters or 80 passages per side. Record unsupported-markup rejections
or explicitly audit supported transformations. Excluded code examples and link
URLs are outside the prose comparison task. Preserve headings, lists, admonition
prose and version notes. Changed code alone does not imply a prose change.

Each old/new passage index must occur exactly once in annotation events. Events
use old_indices/new_indices and unchanged, reworded, modified, added, removed, or
uncertain. Unchanged requires identical extracted prose and same relevant scope;
reworded preserves information; modified changes a claim, scope, recommendation or
substantive detail. Use smallest defensible correspondence groups, including
splits/merges when needed. Additions/removals normally use single passages.
Retain uncertainty rather than forcing a class. Read entire extracted pages and
inspect raw source where context or extraction is ambiguous.

Initial AI-authored labels require independent AI review before evaluator use,
and remain pending human review. Never autonomously call labels human-validated.
Freeze sources, labels, extractor, evaluator and engine before inference. Report
all runtime failures, actual label counts, changed-pair metrics, class counts and
per-document outcomes. Once results are inspected this corpus cannot support
future claims of unseen evaluation after tuning. Public pretraining overlap is
unknown; all inputs are English software documentation.
