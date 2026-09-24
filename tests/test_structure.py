"""Source accounting and explicit scope, independent of semantic models."""

import json
from pathlib import Path

import pytest

from evaluation.context_inputs import rst_contexts
from radar.structure import parse_document


def test_nested_list_context_and_continuation_paragraphs():
    text = "# Access\n\nOnly administrators may:\n\n- Manage users:\n  - Delete users.\n\n  Keep an audit log.\n- Read reports.\n\nOrdinary paragraph.\n\nAnother paragraph."
    passages, contexts = parse_document(text)
    assert contexts[3]["scope_indices"] == [1, 2]
    assert contexts[4]["scope_indices"] == [1, 2]
    assert contexts[5]["scope_indices"] == [1]
    assert contexts[6]["scope"] == contexts[7]["scope"] == []
    assert contexts[3]["headings"] == ["Access"]
    assert contexts[3]["section"] == [0]
    assert contexts[3]["line_start"] == contexts[3]["line_end"] == 6
    assert passages[3] == "- Delete users."


def test_heading_ancestry_excludes_self_and_changes_identical_body_context():
    old, before = parse_document("# Users\n## Guests\nRead reports.\n## Admins\nDelete reports.")
    new, after = parse_document("# Users\n## Members\nRead reports.\n## Admins\nDelete reports.")
    assert old[2] == new[2]
    assert before[2]["headings"] == ["Users", "Guests"]
    assert after[2]["headings"] == ["Users", "Members"]
    assert before[3]["headings"] == ["Users"]
    assert before[4]["section"] == [0, 3]


def test_segmentation_keeps_soft_wraps_and_does_not_propagate_ordinary_prose():
    passages, contexts = parse_document(
        "Normal prose.\n\n- One\n  continuation.\n- Two\n\nFinal\nparagraph."
    )
    assert passages == ["Normal prose.", "- One continuation.", "- Two", "Final paragraph."]
    assert all(not context["scope"] for context in contexts)
    assert contexts[1]["line_start"] == 3 and contexts[1]["line_end"] == 4


def test_frozen_rst_adapter_retains_all_passages_and_recovers_nested_ownership():
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root / "evaluation/real/manifest.json").read_text())
    for case in manifest["cases"]:
        for side in ("old", "new"):
            record = case[side]
            source = (root / record["raw_path"]).read_text()
            expected = json.loads((root / record["passages_path"]).read_text())
            contexts = rst_contexts(source, expected)
            assert len(contexts) == len(expected)
            assert all(c["line_start"] <= c["line_end"] for c in contexts)
            if case["id"] == "pytest-goodpractices" and side == "old":
                assert contexts[12]["scope_indices"] == [7, 11]
                assert contexts[19]["headings"] == [
                    "Good Integration Practices",
                    "Choosing a test layout / import rules",
                    "Tests outside application code",
                ]
    with pytest.raises(ValueError, match="Frozen passages disagree"):
        rst_contexts("Changed.\n", ["Original."])
