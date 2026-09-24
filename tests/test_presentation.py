"""Presentation tests focus on input safety and the interpretation of reports."""

import re
from html import unescape

from radar.presentation import inline_diff, render_results, render_summary


def report(*changes: dict) -> dict:
    return {"engine": "lexical", "changes": list(changes), "elapsed_ms": 12, "warnings": []}


def change(status: str = "modified", **overrides) -> dict:
    return {
        "old_index": 0,
        "new_index": 1,
        "old_text": "Guests can export.",
        "new_text": "Admins can export.",
        "status": status,
        "moved": False,
        "category": "Access changed",
        "explanation": "Review the permission change.",
        "signals": [],
        **overrides,
    }


def test_every_user_controlled_field_is_escaped():
    attack = '<img src=x onerror="alert(1)"><script>alert(1)</script>'
    data = report(
        change(
            old_text=attack,
            new_text=attack + " new",
            category=attack,
            explanation=attack,
            signals=[attack],
            status=attack,
        )
    )
    data["warnings"] = [attack]
    html = render_results(data, "all")
    assert "<script>" not in html and "<img" not in html
    assert "&lt;script&gt;" in html and "&lt;img" in html
    assert "scr-badge-uncertain" in html


def test_inline_diff_preserves_whitespace_and_literal_markup():
    old = "Pay  10 €\n<script> & keep it."
    new = "Pay  25 €\n<script> & keep it."
    before, after = inline_diff(old, new)
    assert "<del>10</del>" in before
    assert "<ins>25</ins>" in after
    assert unescape(re.sub(r"</?(?:del|ins)>", "", before)) == old
    assert unescape(re.sub(r"</?(?:del|ins)>", "", after)) == new


def test_group_members_context_and_localized_evidence_are_visible_and_escaped():
    attack = "<script>unsafe()</script>"
    data = report(
        change(
            old_indices=[0, 2],
            new_indices=[1],
            old_parts=[{"index": 0, "text": "First"}, {"index": 2, "text": attack}],
            old_context=["Section", attack],
            localization_evidence=[{"old_quote": attack, "reason": "Scope changed"}],
        )
    )
    html = render_results(data, "all")
    assert "Passages 1, 3" in html
    assert "Group members" in html and "Passage 3</strong>" in html
    assert "Context:" in html and "Localized verification" in html
    assert "<script>" not in html and "&lt;script&gt;" in html
    assert "Material groups" in render_summary(data)


def test_filters_keep_uncertain_visible_and_moves_separate():
    data = report(
        change(), change("uncertain"), change("reworded"), change("unchanged", moved=True)
    )
    assert "2 of 4 aligned entries" in render_results(data, "material")
    assert "1 of 4 aligned entries" in render_results(data, "review")
    assert "2 of 4 aligned entries" in render_results(data, "wording")
    assert "4 of 4 aligned entries" in render_results(data, "all")
    assert "Moved</span>" in render_results(data, "wording")
    assert render_summary(data).count('class="scr-stat-value">1<') == 4


def test_added_removed_and_missing_scores_are_understandable():
    data = report(
        change("added", old_index=None, old_text=""), change("removed", new_index=None, new_text="")
    )
    html = render_results(data)
    assert html.count("No corresponding passage") == 2
    assert "Not available" in html
    assert "nan" not in html
    assert 'class="scr-stat-value">2<' in render_summary(data)


def test_empty_views_do_not_claim_documents_are_equivalent():
    assert "READY WHEN YOU ARE" in render_results(None)
    assert "No passages in this view" in render_results(report(change("reworded")))
    assert "All passages" in render_results(report(change("reworded")))


def test_ui_callback_exports_exact_report_and_cleans_replaced_download():
    import json
    from pathlib import Path

    from app import cleanup_report, run_comparison

    first = run_comparison("The limit is 10.", "The limit is 20.", "lexical", "all", None)
    first_path = Path(first[0]["download_path"])
    assert json.loads(first_path.read_text()) == first[4]
    assert first[3]["visible"] is True
    second = run_comparison("The limit is 10.", "The limit is 10.", "lexical", "all", first[0])
    second_path = Path(second[0]["download_path"])
    try:
        assert not first_path.exists()
        assert second_path.exists()
        assert "lexical baseline" in second[5]
    finally:
        cleanup_report(second[0])
    assert not second_path.exists()


def test_model_failure_offers_explicit_baseline_without_silent_fallback(monkeypatch):
    import gradio as gr
    import pytest

    from app import run_comparison

    def fail(*args, **kwargs):
        raise RuntimeError("Test model load failure")

    monkeypatch.setattr("radar.compare.compare_documents", fail)
    with pytest.raises(gr.Error, match="explicitly select Lexical baseline"):
        run_comparison("Before.", "After.", "semantic", "all", None)


def test_status_checks_current_inputs_after_a_comparison_finishes():
    from app import cleanup_report, mark_stale, run_comparison

    completed = run_comparison("Limit 10.", "Limit 20.", "lexical", "all", None)
    state = completed[0]
    try:
        assert mark_stale(state, "Limit 10.", "Limit 20.", "lexical") == completed[5]
        assert "Inputs changed" in mark_stale(state, "Limit 10.", "Limit 30.", "lexical")
        assert "Inputs changed" in mark_stale(state, "Limit 10.", "Limit 20.", "semantic")
        assert mark_stale(None, "Anything", "Anything", "lexical") == "Ready to compare."
    finally:
        cleanup_report(state)


def test_shared_physical_scope_is_one_task_without_losing_source_entries():
    scope = {"old_owner_indices": [0], "new_owner_indices": [2], "reason": "Owner <changed>"}
    other = {"old_owner_indices": [5], "new_owner_indices": [6], "reason": "Different owner"}
    data = report(
        change("uncertain", scope_review=scope, old_text="First body."),
        change("uncertain", scope_review=scope, old_text="Second body."),
        change("uncertain", scope_review=other),
        change("modified", scope_review=scope),
    )
    html = render_results(data)
    assert html.count('class="scr-scope-task"') == 1
    assert "2 affected entries · 1 review task" in html
    assert "Before scope passage(s) 1 · After scope passage(s) 3" in html
    assert "Owner &lt;changed&gt;" in html
    assert html.count('<article class="scr-card') == 4
    assert "First" in html and "Second" in html
    summary = render_summary(data)
    assert 'class="scr-stat-value">2<' in summary
    assert "3 affected review entries" in summary
    assert "Review tasks" in summary


def test_source_map_uses_real_indices_for_split_groups_and_additions():
    data = report(
        change("uncertain", old_indices=[2], new_indices=[4, 5]),
        change("added", old_indices=[], new_indices=[6]),
    )
    html = render_summary(data)
    assert html.count('class="scr-map-cell ') == 4
    assert 'aria-label="Before passage 3: Needs review"' in html
    assert 'aria-label="After passage 6: Needs review"' in html
    assert 'aria-label="After passage 7: Added"' in html
