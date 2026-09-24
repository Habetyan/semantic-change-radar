# Handoff: 2026-09-24

The resume preparation work is published. GitHub CI passed for the implementation
release, and the public recorded showcase passed desktop and mobile browser checks.
Exact commits, URLs and verification results are in
[the publication record](../artifacts/publication.json). The author has confirmed
the measurements; see [the review record](annotation-provenance.md).

## Current application

The polished Gradio workspace includes paired source/evidence panels, literal edit
highlights, a passage map, grouped scope-review tasks, filters, JSON export, stale
result notices, keyboard focus, and mobile layouts. Eight examples include three
complete historical HTTPX, pip, and MkDocs pages with attribution. Editing a real
example explicitly marks its provenance as edited; restoring the original text
restores the historical-source label.

Runtime inference remains pinned, quantized MiniLM embeddings and bidirectional
NLI on CPU. No LLM is integrated, and no model was trained or fine-tuned. Current
localized excerpts preserve exact source punctuation; historical v2 exports are
unchanged and may contain normalized excerpts.

- Live local Gradio: **http://127.0.0.1:7864**
- A temporary public live preview is started separately with `GRADIO_SHARE=1` on
  port 7867. See [its verification record](../artifacts/live-preview.json) for the
  URL and check time. It depends on this machine staying online and expires within
  about one week; the static showcase remains the published recorded companion.
- Local annotation review: **http://127.0.0.1:7866**
- [Silent walkthrough](images/walkthrough.mp4): 59.72 seconds, 2.69 MB of actual UI interaction.
- [Desktop screenshot](images/demo.png) and [mobile screenshot](images/mobile.png).

Restart from `/home/art/Downloads/games/semantic-change-radar`:

```bash
HF_HUB_OFFLINE=1 GRADIO_SERVER_PORT=7864 .venv/bin/python app.py
# In another terminal:
.venv/bin/python -m http.server 7866 --bind 127.0.0.1 --directory docs/review
```

The local environment already has cached model weights. A fresh installation
needs the initial model download before offline semantic inference works.

## Evidence and tradeoffs

Read [resume-results.md](resume-results.md) for definitions, complete comparisons,
failures, and reproduction commands.

- On six newly selected blind revision pairs, current and archived v2 decisions
  are identical: changed alignment F1 .9474 and all-event material F1 .9364.
  Additions dominate that score; only **5/11 paired material edits** are classified
  modified. One material paragraph is incorrectly accepted as unchanged because
  availability changes elsewhere in its document. This is not an accuracy gain.
- On development pages, raw uncertain entries increase from 40 to 45, while the
  UI groups them into 20 review tasks. Three false material alerts become reviews,
  but three genuine material classifications also become reviews. Grouping reduces
  duplicate work, not model errors. Development split recovery remains 0/8.
- The local Qwen 7B experiment returned all 35 responses, but **13 failed literal
  quote validation** and count as uncertain. Its simulated fallback F1 rises from
  .6111 to .6500, below an always-material baseline of .6538. Explanation auditing
  also found unsupported claims. The saved run retains `complete: false`; it is
  not a production candidate.

The [annotation provenance note](annotation-provenance.md) records the author's
review confirmation and the reference labels used for scoring. The offline
[review packet](review/README.md) contains **471 proposed groups across nine cases**,
hides proposed classifications, and supports local drafts and JSON import/export.
Any submitted corrections require adjudication and a new label
version; they do not overwrite frozen labels. The blind set has now been inspected
and cannot serve as an unseen holdout for future tuning.

## Verification and publication

[Portfolio verification](../artifacts/portfolio-verification.json) records **81 tests
passed**, including cached real-model checks, plus Ruff, formatting, dependency,
documentation-link, browser, source-hash, and freeze checks. Browser checks cover
Gradio interactions, exact excerpts, grouped sources, edited provenance, the review
form, and static showcase behavior.

[GitHub CI](https://github.com/Habetyan/semantic-change-radar/actions/runs/36039368224)
also passed installation, dependency checks, lint, formatting, unit tests and actual
CPU inference on a fresh hosted runner. The public showcase passed example selection,
filters, evidence, JSON downloads and mobile checks with no JavaScript errors.

Verified public links:

- Source: <https://github.com/Habetyan/semantic-change-radar>
- Recorded showcase: <https://huggingface.co/spaces/artush-habetyan/semantic-change-radar-demo>

The showcase contains recorded outputs with an explicit no-live-inference disclosure.
Use the local Gradio app above to compare new text. No paid plan or hardware was
purchased. Further annotation corrections should be versioned and adjudicated
through the review packet before recomputing scores.
[INTERVIEW.md](INTERVIEW.md) provides architecture notes and truthful resume wording.
