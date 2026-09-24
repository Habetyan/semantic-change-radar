"""Behavioral checks for source scope, group accounting and unsafe equivalence."""

import numpy as np
import pytest

from radar.compare import compare_documents
from radar.details import changed_units, verify_details


def assert_coverage(report):
    for side in ("old", "new"):
        assert sorted(i for change in report["changes"] for i in change[f"{side}_indices"]) == list(
            range(report[f"{side}_count"])
        )


@pytest.mark.parametrize("reverse", [False, True])
def test_exact_split_and_merge_keep_all_source_ids(reverse):
    old = "# Accounts\n\nUsers can read reports. Administrators can delete accounts."
    new = "# Accounts\n\nUsers can read reports.\n\nAdministrators can delete accounts."
    if reverse:
        old, new = new, old
    report = compare_documents(old, new, "lexical")
    assert_coverage(report)
    group = next(c for c in report["changes"] if c["status"] == "reworded")
    assert sorted([len(group["old_indices"]), len(group["new_indices"])]) == [1, 2]
    assert group["category"] == "Paragraph layout"
    assert not group["moved"]
    assert not any(c["status"] in {"added", "removed"} for c in report["changes"])


def test_adjacent_unrelated_addition_is_not_swallowed_by_group():
    report = compare_documents(
        "Users can read reports.",
        "Users may read reports.\n\nThe garden contains roses.",
        "lexical",
    )
    assert_coverage(report)
    assert any(c["status"] == "added" and "garden" in c["new_text"] for c in report["changes"])
    assert all(len(c["new_indices"]) <= 1 for c in report["changes"])


def test_same_text_under_changed_access_scope_is_not_unchanged():
    old = "# Access\n\nOnly administrators may:\n\n- Delete records."
    new = "# Access\n\nOnly guests may:\n\n- Delete records."
    report = compare_documents(old, new, "lexical")
    body = next(c for c in report["changes"] if c["old_index"] == 2)
    assert body["status"] != "unchanged"
    assert body["context_changed"]
    assert "administrators" in " ".join(body["old_context"])
    assert_coverage(report)


def test_named_list_context_prevents_cross_mode_match():
    old = "# Import modes\n\n- prepend: Load modules.\n\n  Names must be unique.\n\n- importlib: Load modules.\n\n  Names need not be unique."
    new = "# Import modes\n\n- importlib: Load modules.\n\n  Names do not have to be unique.\n\n- prepend: Load modules.\n\n  Each name must be unique."
    report = compare_documents(old, new, "lexical", profile="context")
    paired = {(tuple(c["old_indices"]), tuple(c["new_indices"])) for c in report["changes"]}
    assert ((2,), (4,)) in paired
    assert ((4,), (2,)) in paired
    assert_coverage(report)


class DetailModel:
    def fits_nli(self, left, right):
        return True

    def predict_nli(self, pairs):
        return [{"entailment": 0.2, "contradiction": 0.2, "neutral": 0.6} for _ in pairs]


def test_removed_detail_cannot_hide_in_high_paragraph_equivalence():
    change = {
        "old_text": "Templates support inheritance, use Unicode for all operations, and allow macros.",
        "new_text": "Templates support inheritance, and allow macros.",
        "status": "reworded",
        "category": "Wording only",
    }
    verify_details(change, DetailModel())
    assert change["status"] == "uncertain"
    assert "Unicode" in change["localization_evidence"][0]["old_quote"]


def test_changed_condition_is_checked_with_its_subject():
    change = {
        "old_text": "If the account is inactive, administrators may delete records.",
        "new_text": "If the account is active, administrators may delete records.",
        "status": "reworded",
        "category": "Wording only",
    }
    verify_details(change, DetailModel())
    assert change["status"] == "uncertain"
    assert change["localization_evidence"][0]["old_quote"] == "If the account is inactive"


def test_condition_paraphrase_does_not_hide_another_removed_clause():
    checks = changed_units(
        "If you are logged in, you may read reports, logs are retained permanently.",
        "If you signed in, you may read reports.",
    )
    assert any("logs are retained permanently" in old for old, _ in checks)


def test_short_removed_predicate_is_still_a_detail():
    checks = changed_units(
        "The service stores customer records, encrypts backups, and generates monthly reports.",
        "The service stores customer records, and generates monthly reports.",
    )
    assert ("encrypts backups", "") in checks


def test_context_budget_abstains_without_truncating(monkeypatch):
    import radar.models

    class BudgetModel(DetailModel):
        def fits_nli(self, left, right):
            return len(left) + len(right) < 60

        def fits_embedding(self, text):
            return True

        def encode(self, texts):
            return np.array([[1.0, 0.0]] * len(texts))

        def metadata(self):
            return {"test": True}

    monkeypatch.setattr(radar.models, "get_models", lambda: BudgetModel())
    old = "# Conditions for members with verified accounts\n\nRead records."
    new = "# Conditions for members without verified accounts\n\nRead records."
    report = compare_documents(old, new, profile="context")
    body = next(c for c in report["changes"] if c["old_index"] == 1)
    assert body["status"] == "uncertain"
    assert body["category"] == "Context exceeds model budget"
    assert body["scope_review"]["old_owner_indices"] == [0]
    assert body["old_text"] == "Read records."
    assert_coverage(report)


class ConfidentModel(DetailModel):
    def encode(self, texts):
        return np.array([[0.0, 1.0] if "Read reports" in text else [1.0, 0.0] for text in texts])

    def metadata(self):
        return {"test": True}

    def fits_embedding(self, text):
        return True

    def predict_nli(self, pairs):
        return [{"entailment": 0.99, "contradiction": 0.005, "neutral": 0.005} for _ in pairs]


def test_confident_contextual_equivalence_survives_same_body_override(monkeypatch):
    import radar.models

    monkeypatch.setattr(radar.models, "get_models", lambda: ConfidentModel())
    report = compare_documents("# Overview\n\nRead reports.", "# Introduction\n\nRead reports.")
    body = next(c for c in report["changes"] if c["old_index"] == 1)
    assert body["status"] == "reworded"
    assert "scope_review" not in body
    assert body["context_changed"]


@pytest.mark.parametrize(
    "before,after",
    [
        ("Guests", "Members"),
        ("Allowed", "Forbidden"),
        ("Free plan", "Paid plan"),
        ("Only administrators may:", "Only guests may:"),
    ],
)
def test_scope_restrictions_require_review_despite_confident_model(monkeypatch, before, after):
    import radar.models

    monkeypatch.setattr(radar.models, "get_models", lambda: ConfidentModel())
    prefix = "" if before.endswith(":") else "# "
    report = compare_documents(
        f"{prefix}{before}\n\n- Read reports.", f"{prefix}{after}\n\n- Read reports."
    )
    body = next(c for c in report["changes"] if c["old_index"] == 1)
    assert body["status"] == "uncertain"
    assert body["scope_review"]["old_owner_indices"] == [0]
    assert body["scope_review"]["new_owner_indices"] == [0]
    assert_coverage(report)


def test_inherited_narrative_signal_does_not_prove_material_child_edit():
    report = compare_documents(
        "# Modes\n\nUntil recently, the options were:\n\n- Read reports.\n- Read logs.",
        "# Modes\n\nThe options are:\n\n- Read reports.\n- Read logs.",
        "lexical",
    )
    children = [c for c in report["changes"] if c["old_index"] in {2, 3}]
    assert all(c["status"] == "uncertain" for c in children)
    assert all(c["scope_review"]["old_owner_indices"] == [1] for c in children)
    assert children[0]["scope_review"] == children[1]["scope_review"]


def test_body_signal_still_marks_material_edit_under_changed_context():
    report = compare_documents(
        "# Guests\n\nKeep reports for 30 days.", "# Members\n\nKeep reports for 60 days.", "lexical"
    )
    body = next(c for c in report["changes"] if c["old_index"] == 1)
    assert body["status"] == "modified"
    assert "scope_review" not in body


def test_localized_multiple_clauses_are_exact_source_spans():
    old = "First stays, encrypt backups; retain logs for 1.5 days, Last stays."
    new = "First stays, compress backups; retain logs for 2.5 days, Last stays."
    checks = changed_units(old, new)
    assert (
        "encrypt backups; retain logs for 1.5 days",
        "compress backups; retain logs for 2.5 days",
    ) in checks
    assert all(before in old and after in new for before, after in checks)
    removed = changed_units(old, "First stays, Last stays.")
    assert ("encrypt backups; retain logs for 1.5 days", "") in removed


@pytest.mark.parametrize("reverse", [False, True])
def test_removed_scope_owner_retains_physical_indices(reverse):
    old, new = "# Access\n\nOnly guests may:\n\n- Read reports.", "# Access\n\n- Read reports."
    if reverse:
        old, new = new, old
    report = compare_documents(old, new, "lexical")
    body = next(c for c in report["changes"] if c["old_text"] == "- Read reports.")
    assert body["status"] == "uncertain"
    assert body["scope_review"]["old_owner_indices"] == ([] if reverse else [1])
    assert body["scope_review"]["new_owner_indices"] == ([1] if reverse else [])
    assert_coverage(report)
