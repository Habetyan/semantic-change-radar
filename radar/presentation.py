"""Escaped HTML views of comparison reports, independent of Gradio."""

import math
import re
from collections import Counter
from difflib import SequenceMatcher
from html import escape

FILTERS = [
    ("Material + review", "material"),
    ("All passages", "all"),
    ("Needs review", "review"),
    ("Wording & moves", "wording"),
]
STATUS_LABELS = {
    "modified": "Changed meaning",
    "added": "Added",
    "removed": "Removed",
    "uncertain": "Needs review",
    "reworded": "Reworded",
    "unchanged": "Unchanged",
}
MATERIAL = {"modified", "added", "removed"}


def inline_diff(old: str, new: str) -> tuple[str, str]:
    """Highlight token edits while escaping every character supplied by users."""
    old_tokens = re.findall(r"\s+|\w+|[^\w\s]", old)
    new_tokens = re.findall(r"\s+|\w+|[^\w\s]", new)
    before, after = [], []
    for tag, old_start, old_end, new_start, new_end in SequenceMatcher(
        None, old_tokens, new_tokens, autojunk=False
    ).get_opcodes():
        old_fragment = escape("".join(old_tokens[old_start:old_end]))
        new_fragment = escape("".join(new_tokens[new_start:new_end]))
        before.append(
            f"<del>{old_fragment}</del>" if tag != "equal" and old_fragment else old_fragment
        )
        after.append(
            f"<ins>{new_fragment}</ins>" if tag != "equal" and new_fragment else new_fragment
        )
    return "".join(before), "".join(after)


def _scope_key(change: dict) -> tuple | None:
    scope = change.get("scope_review")
    if change.get("status") != "uncertain" or not scope:
        return None
    old = tuple(scope.get("old_owner_indices", []))
    new = tuple(scope.get("new_owner_indices", []))
    return (old, new) if old or new else None


def _review_tasks(changes: list[dict]) -> int:
    reviews = [change for change in changes if change["status"] == "uncertain"]
    return sum(_scope_key(change) is None for change in reviews) + len(
        {_scope_key(change) for change in reviews if _scope_key(change) is not None}
    )


def _source_map(report: dict) -> str:
    rows = []
    for side, label in (("old", "Before"), ("new", "After")):
        passages = {}
        for change in report["changes"]:
            indices = change.get(side + "_indices")
            if indices is None:
                index = change.get(side + "_index")
                indices = [] if index is None else [index]
            status = change["status"] if change["status"] in STATUS_LABELS else "uncertain"
            for index in indices:
                passages[index] = status
        cells = "".join(
            f'<span class="scr-map-cell scr-map-{status}" role="img" '
            f'aria-label="{label} passage {index + 1}: {STATUS_LABELS[status]}" '
            f'title="{label} passage {index + 1}: {STATUS_LABELS[status]}"></span>'
            for index, status in sorted(passages.items())
        )
        rows.append(
            f'<div class="scr-map-row"><span>{label} <b>{len(passages)}</b></span>'
            f'<div class="scr-map-track">{cells}</div></div>'
        )
    return (
        '<div class="scr-source-map"><div class="scr-map-heading"><strong>Passage map</strong>'
        "<span>Source order · one mark per passage</span></div>"
        + "".join(rows)
        + '<div class="scr-map-legend"><span>Teal: added</span><span>Rust: changed / removed</span>'
        "<span>Amber: review</span><span>Gray: reworded / unchanged</span></div></div>"
    )


def render_summary(report: dict | None) -> str:
    """Summarize status counts. Moved passages can also have another status."""
    if report is None:
        values = [None] * 4
    else:
        counts = Counter(change["status"] for change in report["changes"])
        affected = {}
        for side in ("old", "new"):
            affected[side] = len(
                {
                    index
                    for change in report["changes"]
                    if change["status"] == "uncertain"
                    for index in change.get(side + "_indices", [change.get(side + "_index")])
                    if index is not None
                }
            )
        values = [
            sum(counts[status] for status in MATERIAL),
            _review_tasks(report["changes"]),
            counts["reworded"],
            sum(bool(change.get("moved")) for change in report["changes"]),
        ]
    grouped = report is not None and any(
        len(change.get(side + "_indices", [])) > 1
        for change in report["changes"]
        for side in ("old", "new")
    )
    labels = [
        "Material groups" if grouped else "Material edits",
        "Review tasks",
        "Reworded",
        "Moved",
    ]
    return (
        '<div class="scr-summary" aria-label="Comparison summary">'
        + "".join(
            f'<div class="scr-stat"><span class="scr-stat-value">{value if value is not None else "·"}</span>'
            f'<span class="scr-stat-label">{label}</span></div>'
            for label, value in zip(labels, values)
        )
        + "</div>"
        + (
            f'<p class="scr-summary-note">{sum(c["status"] == "uncertain" for c in report["changes"])} '
            f"affected review entries ({affected['old']} before / {affected['new']} after passages). "
            "Shared scope changes count as one review task. "
            "Moved entries also belong to another category.</p>" + _source_map(report)
            if report is not None
            else '<p class="scr-summary-note">Your review summary and passage map appear here after comparison.</p>'
        )
    )


def _score(value: object) -> str:
    if value is None:
        return "Not available"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "Not available"
    return f"{number:.3f}" if math.isfinite(number) else "Not available"


def _passage(fragment: str, change: dict, side: str, label: str) -> str:
    indices = change.get(side + "_indices")
    if indices is None:
        index = change.get(side + "_index")
        indices = [] if index is None else [index]
    position = (
        ("Passage " if len(indices) == 1 else "Passages ")
        + ", ".join(str(index + 1) for index in indices)
        if indices
        else "No match"
    )
    text = (
        f'<p class="scr-passage">{fragment}</p>'
        if fragment
        else '<p class="scr-missing">No corresponding passage</p>'
    )
    if len(indices) > 1 and change.get(side + "_parts"):
        text += (
            '<details class="scr-members"><summary>Group members</summary>'
            + "".join(
                f'<p class="scr-passage"><strong>Passage {part["index"] + 1}</strong>: '
                f"{escape(str(part['text']))}</p>"
                for part in change[side + "_parts"]
            )
            + "</details>"
        )
    contexts = change.get(side + "_context", [])
    if contexts:
        text += (
            '<p class="scr-context"><strong>Context:</strong> '
            + escape(" · ".join(str(context) for context in contexts))
            + "</p>"
        )
    return (
        f'<section class="scr-side"><div class="scr-passage-label">'
        f"<span>{label}</span><span>{position}</span></div>{text}</section>"
    )


def _change_card(change: dict) -> str:
    status = change["status"] if change["status"] in STATUS_LABELS else "uncertain"
    old_fragment, new_fragment = inline_diff(
        change.get("old_text") or "", change.get("new_text") or ""
    )
    moved = '<span class="scr-moved">Moved</span>' if change.get("moved") else ""
    category = escape(str(change.get("category") or STATUS_LABELS[status]))
    explanation = escape(str(change.get("explanation") or "Inspect the aligned passages."))
    signals = "".join(f"<li>{escape(str(signal))}</li>" for signal in change.get("signals", []))
    signal_html = f'<ul class="scr-signals">{signals}</ul>' if signals else ""
    localized = change.get("localization_evidence", [])
    if localized:
        signal_html += (
            '<h4>Localized verification</h4><p class="scr-local-note">Localized source excerpts; read the full passages above for exact text and context.</p><ul class="scr-localized">'
            + "".join(
                '<li><p class="scr-local-reason">'
                + escape(str(item.get("reason", "Inspect the changed wording.")))
                + "</p><div><strong>Before:</strong> "
                + escape(str(item.get("old_quote", "")))
                + "</div><div><strong>After:</strong> "
                + escape(str(item.get("new_quote", "")))
                + "</div></li>"
                for item in localized
            )
            + "</ul>"
        )
    scores = [
        ("Alignment similarity", "alignment_score"),
        ("Old → new entailment", "old_entails_new"),
        ("New → old entailment", "new_entails_old"),
        ("Contradiction", "contradiction_score"),
    ]
    score_html = "".join(
        f"<div><dt>{label}</dt><dd>{_score(change.get(key))}</dd></div>" for label, key in scores
    )
    return (
        f'<article class="scr-card scr-{status}">'
        f'<header class="scr-card-header"><div class="scr-card-title">'
        f'<span class="scr-badge scr-badge-{status}">{STATUS_LABELS[status]}</span>{moved}'
        f"<h3>{category}</h3></div><p>{explanation}</p></header>"
        f'<div class="scr-pair">{_passage(old_fragment, change, "old", "BEFORE")}'
        f"{_passage(new_fragment, change, 'new', 'AFTER')}</div>"
        '<details class="scr-evidence"><summary>Evidence and model scores</summary>'
        f'{signal_html}<dl class="scr-scores">{score_html}</dl>'
        "<p>Scores are model outputs, not calibrated confidence. Inline highlights show literal edits.</p>"
        "</details></article>"
    )


def render_results(report: dict | None, view: str = "material") -> str:
    """Render a report with a strictly enumerated filter and no raw input HTML."""
    if report is None:
        return (
            '<div class="scr-empty"><span class="scr-empty-label">READY WHEN YOU ARE</span>'
            "<h3>See the meaning behind the edits.</h3>"
            "<p>Load an example or paste two document versions, then select Compare documents.</p></div>"
        )
    changes = report["changes"]
    if view == "material":
        visible = [change for change in changes if change["status"] in MATERIAL | {"uncertain"}]
    elif view == "review":
        visible = [change for change in changes if change["status"] == "uncertain"]
    elif view == "wording":
        visible = [
            change for change in changes if change["status"] == "reworded" or change.get("moved")
        ]
    else:
        visible = changes
    engine = "Semantic models" if report.get("engine") == "semantic" else "Lexical baseline"
    elapsed = _score(float(report.get("elapsed_ms", 0)) / 1000)
    meta = (
        f'<div class="scr-result-meta"><span>{len(visible)} of {len(changes)} aligned entries shown</span>'
        f"<span>{engine} · {elapsed}s</span></div>"
    )
    warnings = "".join(
        f'<p class="scr-warning">{escape(str(warning))}</p>'
        for warning in report.get("warnings", [])
    )
    if not visible:
        label = dict((value, label) for label, value in FILTERS).get(view, "this view")
        cards = (
            '<div class="scr-empty"><h3>No passages in this view.</h3>'
            f"<p>The “{escape(label)}” filter has no matches. Select All passages to inspect the complete comparison.</p></div>"
        )
    else:
        scope_groups: dict[tuple, list[dict]] = {}
        for change in visible:
            key = _scope_key(change)
            if key is not None:
                scope_groups.setdefault(key, []).append(change)
        rendered = set()
        parts = []
        for change in visible:
            key = _scope_key(change)
            if key is None or len(scope_groups[key]) == 1:
                parts.append(_change_card(change))
            elif key not in rendered:
                rendered.add(key)
                group = scope_groups[key]
                reason = escape(
                    str(change["scope_review"].get("reason", "Shared context changed."))
                )
                owners = " · ".join(
                    f"{label} scope passage(s) {', '.join(str(index + 1) for index in indices)}"
                    for label, indices in zip(("Before", "After"), key)
                    if indices
                )
                parts.append(
                    '<details class="scr-scope-task"><summary><span class="scr-badge scr-badge-uncertain">'
                    "Needs review</span><strong>Shared scope change</strong>"
                    f"<span>{len(group)} affected entries · 1 review task</span></summary>"
                    f'<p>{reason}</p><p class="scr-scope-owner">{owners}</p>'
                    "<p>These unchanged passages inherit the same changed context. Expand each entry to inspect its evidence. "
                    'All entries remain in the JSON report.</p><div class="scr-scope-entries">'
                    + "".join(_change_card(member) for member in group)
                    + "</div></details>"
                )
        cards = "".join(parts)
    return f'<div class="scr-results">{meta}{warnings}{cards}</div>'
