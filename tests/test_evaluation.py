"""Metrics tests use invented toy predictions, independently of model behavior."""

import unittest
from pathlib import Path

from evaluation.evaluate import aggregate, evaluate_dataset, load_fixtures, score_changes


def event(old, new, status):
    return {"old_index": old, "new_index": new, "status": status}


class EvaluationMetricsTests(unittest.TestCase):
    def test_perfect_mixed_alignment(self):
        expected = [
            event(0, 1, "modified"),
            event(1, 0, "reworded"),
            event(2, None, "removed"),
            event(None, 2, "added"),
        ]
        score = score_changes(
            ["old limit", "same meaning", "obsolete"],
            ["paraphrase", "new limit", "new section"],
            expected,
            expected,
        )
        self.assertEqual(score["alignment"]["f1"], 1)
        self.assertEqual(score["material_change"]["f1"], 1)
        self.assertEqual(score["material_change"]["expected"], 3)
        self.assertEqual(score["prediction_coverage"], 1)
        self.assertEqual(score["risky_misses"], 0)

    def test_wrong_pairing_cannot_get_material_credit(self):
        expected = [event(0, 0, "modified"), event(1, 1, "modified")]
        predicted = [event(0, 1, "modified"), event(1, 0, "modified")]
        score = score_changes(["old A", "old B"], ["new A", "new B"], expected, predicted)
        self.assertEqual(score["alignment"]["f1"], 0)
        self.assertEqual(score["material_change"]["f1"], 0)
        self.assertEqual(score["missed_material_events"], 2)
        self.assertEqual(score["aligned_gold_coverage"], 0)
        self.assertEqual(score["confusion"]["modified"]["no_predicted_correspondence"], 2)

    def test_false_alarms_and_abstentions_have_separate_costs(self):
        expected = [event(0, 0, "modified"), event(1, 1, "modified"), event(2, 2, "reworded")]
        predicted = [event(0, 0, "reworded"), event(1, 1, "uncertain"), event(2, 2, "modified")]
        score = score_changes(["A", "B", "C"], ["D", "E", "F"], expected, predicted)
        self.assertEqual(score["alignment"]["f1"], 1)
        self.assertEqual(score["material_change"]["true_positive"], 0)
        self.assertEqual(score["material_change"]["predicted"], 1)
        self.assertEqual(score["material_change"]["expected"], 2)
        self.assertEqual(score["risky_misses"], 1)
        self.assertEqual(score["material_abstentions"], 1)
        self.assertEqual(score["missed_material_events"], 2)
        self.assertAlmostEqual(score["prediction_coverage"], 2 / 3)

    def test_identical_occurrences_do_not_create_alignment_errors(self):
        expected = [event(0, 0, "unchanged"), event(1, None, "removed")]
        alternate = [event(0, None, "removed"), event(1, 0, "unchanged")]
        score = score_changes(["repeat", "repeat"], ["repeat"], expected, alternate)
        self.assertEqual(score["alignment"]["f1"], 1)
        self.assertEqual(score["material_change"]["f1"], 1)
        self.assertEqual(score["gold_events"], 2)
        self.assertEqual(score["confusion"]["removed"]["removed"], 1)

    def test_aggregation_is_micro_averaged(self):
        first = score_changes(["a"], ["b"], [event(0, 0, "modified")], [event(0, 0, "modified")])
        second = score_changes(
            ["a", "b"],
            ["c", "d"],
            [event(0, 0, "modified"), event(1, 1, "modified")],
            [event(0, 0, "reworded"), event(1, 1, "unchanged")],
        )
        overall = aggregate([first, second])
        self.assertEqual(overall["material_change"]["precision"], 1)
        self.assertAlmostEqual(overall["material_change"]["recall"], 1 / 3)
        self.assertAlmostEqual(overall["material_change"]["f1"], 0.5)
        self.assertEqual(overall["risky_misses"], 2)

    def test_missing_duplicated_and_invalid_indices_are_rejected(self):
        gold = [event(0, 0, "modified")]
        for predicted in (
            [],
            [*gold, *gold],
            [event(True, 0, "modified")],
            [event(0, 1, "modified")],
            [event(0, 0, "added")],
        ):
            with self.subTest(predicted=predicted), self.assertRaises(ValueError):
                score_changes(["old"], ["new"], gold, predicted)

    def test_failed_examples_are_visible_and_mark_run_incomplete(self):
        fixtures = [
            {
                "id": "toy",
                "domain": "toy",
                "tags": ["toy"],
                "old_text": "a",
                "new_text": "b",
                "expected": [event(0, 0, "modified")],
            }
        ]

        def fail(old, new):
            raise RuntimeError("deliberate test failure")

        summary, predictions = evaluate_dataset(fixtures, fail, lambda text: [text])
        self.assertFalse(summary["complete"])
        self.assertEqual(summary["failed_examples"], 1)
        self.assertIn("incomplete", summary["metrics_scope"])
        self.assertIn("RuntimeError", predictions[0]["error"])


class FixtureIntegrityTests(unittest.TestCase):
    def test_splits_are_grouped_disjoint_and_explicitly_synthetic(self):
        root = Path(__file__).resolve().parents[1] / "evaluation"
        dev, test = load_fixtures(root / "dev.jsonl"), load_fixtures(root / "test.jsonl")
        self.assertGreaterEqual(len(test), 10)
        for field in ("id", "domain", "scenario_group"):
            self.assertFalse({item[field] for item in dev} & {item[field] for item in test})
        dev_docs = {text for item in dev for text in (item["old_text"], item["new_text"]) if text}
        test_docs = {text for item in test for text in (item["old_text"], item["new_text"]) if text}
        self.assertFalse(dev_docs & test_docs)
        for item in dev + test:
            self.assertIn("not human validated", item["provenance"])
            # Fixtures intentionally contain one passage per blank-line block.
            old = item["old_text"].split("\n\n") if item["old_text"] else []
            new = item["new_text"].split("\n\n") if item["new_text"] else []
            score_changes(old, new, item["expected"], item["expected"])
            self.assertNotIn("uncertain", {change["status"] for change in item["expected"]})


if __name__ == "__main__":
    unittest.main()
