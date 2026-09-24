# Review the annotations

Download [index.html](index.html) and open it in your browser. It works offline.
On GitHub, use **Download raw file**; GitHub's source view does not run the form.
The generated packet contains nine historical page comparisons and 471 proposed
groups from the fresh-v2 and blind-v3 corpora. No model predictions are included.

1. Enter your reviewer name. Select a document and inspect each proposed old/new
   group. Expand full document context and source links when meaning depends on
   surrounding paragraphs.
2. Judge the correspondence and classification yourself. If the group is wrong,
   supply corrected zero-based passage indices and an explanation. Proposed
   classification and rationale stay hidden until you explicitly reveal them.
3. Add notes for ambiguity. The form records when you revealed the proposed label
   and whether that happened before your first classification.
4. Drafts autosave in this browser's local storage. **Export your JSON submission**
   for a durable copy, especially before switching browser/device. Import restores
   a matching packet's submission. Storage failures are shown visibly.

Labels describe operational document changes: unchanged text/meaning, rewording
with preserved information, modified information, additions, removals, or uncertainty.
Changing a requirement, actor, condition, available behavior, quantity or exception
can be material even when most or all of a passage is identical.

Proposed correspondence groups are already visible. This supports independent
classification and correspondence checking; it is not fully blind alignment from
scratch. Revealing a label is allowed and its timing is preserved. Drafts and
exports are local, with no server submission or automatic repository write.

Exports are marked `review_submission_pending_adjudication`. They do not overwrite
frozen annotations or automatically make the benchmark human-validated. Corrections
need an adjudicated new annotation version and a new scored report. Keep personal
review submissions out of the public repository.

Regenerate the packet with the command in [the current report](../resume-results.md).
To serve locally instead of opening a file:

```bash
python -m http.server 7866 --bind 127.0.0.1 --directory docs/review
```

Then visit http://127.0.0.1:7866. Browser-storage behavior can differ between a
`file://` page and a locally served page, so export before switching.
