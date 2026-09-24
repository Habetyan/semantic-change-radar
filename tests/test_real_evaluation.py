"""Real-revision metric checks use hand-calculated toy correspondences."""

import json
import tempfile
import unittest
from pathlib import Path

from evaluation.real_evaluate import aggregate, evaluate_dataset, score_changes, validate_events


def gold(old, new, status):
    return {"old_indices": old, "new_indices": new, "status": status, "rationale": "Toy label."}


def prediction(old, new, status):
    return {"old_index": old, "new_index": new, "status": status}


class RealMetricsTests(unittest.TestCase):
    def test_grouped_prediction_recovers_merge_and_validates_canonical_indices(self):
        expected = [gold([0, 1], [0], "modified")]
        grouped = {
            "old_indices": [0, 1],
            "new_indices": [0],
            "old_index": 0,
            "new_index": 0,
            "status": "modified",
        }
        score = score_changes(["part one", "part two"], ["merged"], expected, [grouped])
        for metric in ("alignment_edges", "exact_group_correspondence", "end_to_end_material"):
            self.assertEqual(score[metric]["f1"], 1)
        for invalid in (None, "0,1", [0, 0], [True, 1], [0, 2], []):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                score_changes(
                    ["part one", "part two"],
                    ["merged"],
                    expected,
                    [{**grouped, "old_indices": invalid}],
                )

    def test_classification_is_conditioned_on_correct_correspondence(self):
        expected = [gold([0], [0], "modified"), gold([1], [1], "modified")]
        wrong = score_changes(
            ["a", "b"],
            ["c", "d"],
            expected,
            [prediction(0, 1, "modified"), prediction(1, 0, "modified")],
        )
        self.assertEqual(wrong["alignment_edges"]["f1"], 0)
        self.assertEqual(wrong["end_to_end_material"]["true_positive"], 0)
        self.assertEqual(wrong["conditional_scored_events"], 0)
        self.assertEqual(wrong["conditional_alignment_coverage"], 0)
        self.assertIsNone(wrong["conditional_status_accuracy"])
        correct = score_changes(
            ["a", "b"],
            ["c", "d"],
            expected,
            [prediction(0, 0, "reworded"), prediction(1, 1, "modified")],
        )
        self.assertEqual(correct["alignment_edges"]["f1"], 1)
        self.assertEqual(correct["conditional_status_accuracy"], 0.5)
        self.assertEqual(correct["risky_misses"], 1)
        self.assertEqual(correct["end_to_end_material"]["recall"], 0.5)

    def test_split_loses_group_recall_but_gets_partial_edge_credit(self):
        score = score_changes(
            ["combined"],
            ["part one", "part two"],
            [gold([0], [0, 1], "modified")],
            [prediction(0, 0, "modified"), prediction(None, 1, "added")],
        )
        self.assertEqual(score["alignment_edges"]["precision"], 1)
        self.assertEqual(score["alignment_edges"]["recall"], 0.5)
        self.assertEqual(score["exact_group_correspondence"]["recall"], 0)
        self.assertEqual(score["end_to_end_material"]["true_positive"], 0)
        self.assertEqual(score["end_to_end_material"]["predicted"], 2)
        self.assertEqual(score["conditional_eligible_events"], 0)
        self.assertEqual(score["gold_split_merge_groups"], 1)
        self.assertEqual(score["gold_changed_paired_groups"], 1)

    def test_changed_alignment_does_not_hide_errors_under_unchanged_matches(self):
        score = score_changes(
            ["same", "old A", "old B"],
            ["same", "new A", "new B"],
            [gold([0], [0], "unchanged"), gold([1], [1], "modified"), gold([2], [2], "reworded")],
            [
                prediction(0, 0, "unchanged"),
                prediction(1, 2, "modified"),
                prediction(2, 1, "modified"),
            ],
        )
        self.assertAlmostEqual(score["alignment_edges"]["recall"], 1 / 3)
        self.assertEqual(score["changed_alignment_edges"]["true_positive"], 0)
        self.assertEqual(score["changed_alignment_edges"]["predicted"], 2)
        self.assertEqual(score["changed_alignment_edges"]["expected"], 2)
        self.assertEqual(score["gold_changed_paired_groups"], 2)

    def test_ambiguous_gold_and_abstention_are_distinct(self):
        score = score_changes(
            ["a", "b", "c"],
            ["d", "e", "f"],
            [gold([0], [0], "uncertain"), gold([1], [1], "modified"), gold([2], [2], "reworded")],
            [
                prediction(0, 0, "modified"),
                prediction(1, 1, "uncertain"),
                prediction(2, 2, "reworded"),
            ],
        )
        self.assertEqual(score["alignment_edges"]["recall"], 1)
        self.assertEqual(score["gold_ambiguous_events"], 1)
        self.assertEqual(score["conditional_eligible_events"], 2)
        self.assertEqual(score["conditional_scored_events"], 2)
        self.assertEqual(score["predicted_material_excluded_ambiguous"], 1)
        self.assertEqual(score["end_to_end_material"]["predicted"], 0)
        self.assertEqual(score["end_to_end_material"]["expected"], 1)
        self.assertEqual(score["material_abstentions"], 1)
        self.assertEqual(score["conditional_decision_coverage"], 0.5)
        self.assertNotIn("uncertain", score["conditional_confusion"])

    def test_additions_removals_and_micro_aggregation(self):
        first = score_changes(
            ["old"],
            ["new"],
            [gold([0], [], "removed"), gold([], [0], "added")],
            [prediction(0, None, "removed"), prediction(None, 0, "added")],
        )
        second = score_changes(
            ["a"],
            ["b"],
            [gold([0], [0], "modified")],
            [prediction(0, 0, "reworded")],
        )
        total = aggregate([first, second])
        self.assertEqual(total["exact_group_correspondence"]["recall"], 1)
        self.assertEqual(total["conditional_scored_events"], 3)
        self.assertAlmostEqual(total["conditional_status_accuracy"], 2 / 3)
        self.assertAlmostEqual(total["end_to_end_material"]["recall"], 2 / 3)
        self.assertEqual(total["end_to_end_material"]["precision"], 1)

    def test_annotation_must_partition_passages(self):
        for events in (
            [],
            [gold([0, 0], [0], "modified")],
            [gold([True], [0], "modified")],
            [gold([1], [0], "modified")],
            [gold([0], [0], "added")],
            [gold([0], [], "removed"), gold([], [], "added")],
        ):
            with self.subTest(events=events), self.assertRaises(ValueError):
                validate_events(["a"], ["b"], events)

    def test_segmentation_failure_remains_in_all_case_denominator(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cases = []
            for identifier in ("ok", "oversized", "unannotated"):
                text = "too large" if identifier == "oversized" else "text"
                (root / f"{identifier}.txt").write_text(text)
                (root / f"{identifier}.json").write_text(json.dumps([text]))
                annotation_path = (
                    f"{identifier}-labels.json" if identifier != "unannotated" else None
                )
                if annotation_path:
                    (root / annotation_path).write_text(
                        json.dumps(
                            {
                                "case_id": identifier,
                                "review_status": "ai_reviewed_pending_human",
                                "events": [gold([0], [0], "unchanged")],
                            }
                        )
                    )
                side = {"text_path": f"{identifier}.txt", "passages_path": f"{identifier}.json"}
                cases.append(
                    {
                        "id": identifier,
                        "repository": "toy",
                        "old": side,
                        "new": side,
                        "annotation_path": annotation_path,
                    }
                )

            def split(text):
                if text == "too large":
                    raise ValueError("deliberate limit failure")
                return [text]

            summary, outputs = evaluate_dataset(
                cases,
                lambda old, new: {"changes": [prediction(0, 0, "unchanged")]},
                split,
                root=root,
            )
            self.assertFalse(summary["complete"])
            self.assertEqual(summary["requested_cases"], 3)
            self.assertEqual(summary["successful_cases"], 2)
            self.assertAlmostEqual(summary["failure_rate"], 1 / 3)
            self.assertEqual(summary["scored_cases"], 1)
            self.assertEqual(summary["unscored_annotated_cases"], 1)
            self.assertEqual(outputs[1]["error_stage"], "segmentation")
            self.assertIsNone(outputs[1]["metrics"])
            self.assertIsNone(outputs[2]["metrics"])
            self.assertTrue(outputs[2]["success"])

    def test_context_sidecars_are_forwarded_without_changing_passage_ids(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "text.txt").write_text("text")
            (root / "passages.json").write_text(json.dumps(["text"]))
            context = [{"index": 0, "heading_path": ["Section"]}]
            (root / "context.json").write_text(json.dumps(context))
            side = {
                "text_path": "text.txt",
                "passages_path": "passages.json",
                "contexts_path": "context.json",
            }
            received = {}

            def compare(old, new, **contexts):
                received.update(contexts)
                return {"changes": [prediction(0, 0, "unchanged")]}

            summary, _ = evaluate_dataset(
                [{"id": "context", "repository": "toy", "old": side, "new": side}],
                compare,
                lambda text: [text],
                root=root,
            )
            self.assertTrue(summary["complete"])
            self.assertEqual(received, {"old_contexts": context, "new_contexts": context})


if __name__ == "__main__":
    unittest.main()
