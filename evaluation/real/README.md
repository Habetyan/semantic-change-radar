# Real documentation revisions

Eight complete historical page comparisons from Flask, pytest and Requests.
Seven have provisional AI-authored annotations independently reviewed by a
different AI agent. Human validation is pending. Requests advanced usage is an
unannotated length/coverage stress case. This is a purposive diagnostic sample,
not a randomly sampled benchmark or a claim about general accuracy.

Start with the [results](../../docs/real-evaluation.md), the
[offline annotation review page](review.html), and the [protocol](PROTOCOL.md).
The review page is a standalone HTML file with document and unchanged-text
filters. It contains no model predictions, so it can support blind human review.

## Layout

- `manifest.json`: exact source revisions, paths, license references and hashes.
- `documents/<case>/{old,new}.rst`: complete upstream source, unchanged bytes.
- `documents/<case>/{old,new}.txt`: complete extracted prose, without code blocks.
- `documents/<case>/{old,new}.passages.json`: zero-based annotation units.
- `documents/<case>/{old,new}.extraction.json`: source-line omission audit.
- `annotations/`: partitioned old/new groups, labels, rationales and review notes.
- `licenses/`: both versions' upstream licenses, plus Requests notices.

Explicit link targets and code blocks are excluded. Implicit Sphinx references
remain as target names when the visible label cannot be resolved. Single-star
emphasis is preserved to avoid damaging literal wildcard names. Text fragments
introducing excluded code remain; raw sources allow inspection of lost context.
The app has not gained RST parsing support; this is an evaluation data adapter.

## Reproduce

Use the repository's installed, pinned environment from the repository root:

```bash
# Regenerate prose from retained sources. No network needed unless a source is missing.
python -m evaluation.acquire_real
# Optional exact-commit re-download (network required):
python -m evaluation.acquire_real --refresh

python -m evaluation.real_evaluate --backend lexical --output artifacts/local/real-lexical
HF_HUB_OFFLINE=1 python -m evaluation.real_evaluate --backend semantic --output artifacts/local/real-semantic
python -m evaluation.review_real
```

Models must already be cached for offline semantic evaluation. Both evaluation
commands intentionally return exit code **1** if any case fails, after writing
every outcome. The frozen app rejects Requests advanced usage for exceeding its
80-passage limit; this is a recorded product limitation, not a harness crash.
Never shorten the page, discard the failure, or compare only favorable examples.

Metrics separate alignment from classification. The latter is conditioned on
correct singleton correspondence and must be read alongside its coverage.
Exact material-event scoring requires the complete annotated correspondence,
including split/merge groups. Headings and added/removed reference-list items
count as passage events. Scores are therefore specific to this operational
definition, not a sentence-level truth or reader-impact measure.

Annotations are frozen before inference. Human corrections should be versioned
and followed by new evaluation outputs; do not silently replace the labels under
the published scores. These pages become development data if used for tuning.
