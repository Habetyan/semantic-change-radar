import json

import numpy as np
import pytest

from radar.compare import MAX_CHARACTERS, _assign, compare_documents, split_passages


def test_paragraphs_keep_conditions_and_soft_wraps_together():
    text = "# Warranty\n\nCoverage lasts eight years\nor 160,000 km, whichever comes first.\n\n- Keep receipts.\n- Submit a claim."
    assert split_passages(text) == [
        "# Warranty",
        "Coverage lasts eight years or 160,000 km, whichever comes first.",
        "- Keep receipts.",
        "- Submit a claim.",
    ]


def test_exact_passages_need_no_models_and_detect_reordering(monkeypatch):
    import radar.models

    monkeypatch.setattr(radar.models, "get_models", lambda: pytest.fail("Unneeded model load"))
    result = compare_documents("Alpha.\n\nBeta.", "Beta.\n\nAlpha.")
    assert [c["status"] for c in result["changes"]] == ["unchanged", "unchanged"]
    assert all(c["moved"] for c in result["changes"])


def test_insertion_does_not_mark_every_later_passage_as_moved():
    result = compare_documents("Alpha.\n\nBeta.", "New section.\n\nAlpha.\n\nBeta.", "lexical")
    assert [c["status"] for c in result["changes"]] == ["added", "unchanged", "unchanged"]
    assert not any(c["moved"] for c in result["changes"])


def test_duplicate_occurrences_are_not_lost():
    result = compare_documents("Keep receipts.\n\nKeep receipts.", "Keep receipts.", "lexical")
    assert sorted(c["status"] for c in result["changes"]) == ["removed", "unchanged"]
    assert {c["old_index"] for c in result["changes"]} == {0, 1}


def test_global_assignment_beats_greedy_and_allows_unmatched():
    assert set(_assign(np.array([[0.91, 0.89], [0.88, 0.2]]), 0.5)) == {(0, 1), (1, 0)}
    assert _assign(np.array([[0.3]]), 0.5) == []


def test_all_additions_removals_and_invalid_input():
    assert compare_documents("", "New requirement.")["changes"][0]["status"] == "added"
    assert compare_documents("Old requirement.", "")["changes"][0]["status"] == "removed"
    for old, new in [("", ""), (None, "valid"), ("x" * (MAX_CHARACTERS + 1), "valid")]:
        with pytest.raises(ValueError):
            compare_documents(old, new)
    with pytest.raises(ValueError, match="80 passages"):
        split_passages("\n\n".join(f"Passage {i}" for i in range(81)))
    with pytest.raises(ValueError, match="backend"):
        compare_documents("a", "b", "unknown")


def test_lexical_report_is_json_serializable_and_every_source_is_accounted_for():
    old = "Export up to 10 reports.\n\nWrite to support.\n\nUse two-factor authentication."
    new = "Export up to 20 reports.\n\nUse two-factor authentication.\n\nThe garden has roses."
    result = compare_documents(old, new, "lexical")
    assert json.loads(json.dumps(result)) == result
    assert sorted(c["old_index"] for c in result["changes"] if c["old_index"] is not None) == [
        0,
        1,
        2,
    ]
    assert sorted(c["new_index"] for c in result["changes"] if c["new_index"] is not None) == [
        0,
        1,
        2,
    ]
    numeric = next(c for c in result["changes"] if "20" in c["new_text"])
    assert numeric["status"] == "modified"
    assert numeric["category"] == "Quantity or date change"
    assert result["models"] == {}


class FakeModels:
    def __init__(self, entailment=0.95, contradiction=0.02):
        self.entailment = entailment
        self.contradiction = contradiction

    def encode(self, texts):
        return np.array([[1.0, 0.0]] * len(texts))

    def predict_nli(self, pairs):
        return [
            {
                "entailment": self.entailment,
                "contradiction": self.contradiction,
                "neutral": 1 - self.entailment - self.contradiction,
            }
            for _ in pairs
        ]

    def metadata(self):
        return {"test": True}

    def fits_embedding(self, text):
        return True

    def fits_nli(self, left, right):
        return True


def test_nli_equivalence_cannot_hide_explicit_numeric_change(monkeypatch):
    import radar.models

    monkeypatch.setattr(radar.models, "get_models", lambda: FakeModels())
    result = compare_documents("Storage is 10 GB.", "Storage is 20 GB.")
    assert result["changes"][0]["status"] == "modified"


def test_semantic_paraphrase_and_abstention(monkeypatch):
    import radar.models

    monkeypatch.setattr(radar.models, "get_models", lambda: FakeModels())
    result = compare_documents("Files stay encrypted.", "Files remain encrypted.")
    assert result["changes"][0]["status"] == "reworded"
    monkeypatch.setattr(radar.models, "get_models", lambda: FakeModels(0.3, 0.2))
    result = compare_documents("Files stay encrypted.", "Files remain encrypted.")
    assert result["changes"][0]["status"] == "uncertain"


def test_model_failure_does_not_silently_switch_to_lexical(monkeypatch):
    import radar.models

    def unavailable():
        raise RuntimeError("Model unavailable")

    monkeypatch.setattr(radar.models, "get_models", unavailable)
    with pytest.raises(RuntimeError, match="unavailable"):
        compare_documents("Export data.", "Download data.")


def test_exact_unit_conversions_and_actual_unit_changes(monkeypatch):
    import radar.models

    monkeypatch.setattr(radar.models, "get_models", lambda: FakeModels(0.01, 0.95))
    result = compare_documents("The timeout is 60 minutes.", "The timeout is 1 hour.")
    assert result["changes"][0]["status"] == "reworded"
    assert result["changes"][0]["category"] == "Equivalent units"
    result = compare_documents("The timeout is 1 minute.", "The timeout is 1 hour.")
    assert result["changes"][0]["status"] == "modified"
    result = compare_documents("Storage is 1 GB.", "Storage is 1000 MB.")
    assert result["changes"][0]["status"] == "reworded"
    result = compare_documents("Storage is 1 GB.", "Storage is 1 GiB.")
    assert result["changes"][0]["status"] == "modified"


def test_numeric_guard_preserves_thousands_and_quantity_bindings(monkeypatch):
    import radar.models

    monkeypatch.setattr(radar.models, "get_models", lambda: FakeModels())
    pairs = [
        ("The timeout is 1,000 seconds.", "The timeout is 1,000 days."),
        ("Storage is 1,000 MB.", "Storage is 1,000 GB."),
        (
            "Logs are retained for 7 days and backups for 30 days.",
            "Logs are retained for 30 days and backups for 7 days.",
        ),
        (
            "Guests may view reports and admins may delete reports.",
            "Guests may delete reports and admins may view reports.",
        ),
        ("The administrator approved the guest.", "The guest approved the administrator."),
    ]
    for old, new in pairs:
        assert compare_documents(old, new)["changes"][0]["status"] == "modified"


def test_compatibility_unicode_and_leading_signs_are_not_treated_as_identical():
    pairs = [
        ("The limit is 10³ requests.", "The limit is 103 requests."),
        ("- 20 degrees is the minimum.", "+ 20 degrees is the minimum."),
    ]
    for old, new in pairs:
        result = compare_documents(old, new, "lexical")
        assert all(c["status"] != "unchanged" for c in result["changes"])
