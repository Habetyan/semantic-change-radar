"""Evaluate passage alignment and material edits on original synthetic fixtures."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
import platform
import statistics
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
STATUSES = {"unchanged", "reworded", "modified", "added", "removed", "uncertain"}
MATERIAL = {"modified", "added", "removed"}
EQUIVALENT = {"unchanged", "reworded"}
JsonDict = dict[str, Any]


def load_fixtures(path: Path) -> list[JsonDict]:
    fixtures = [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    if not fixtures or len({item["id"] for item in fixtures}) != len(fixtures):
        raise ValueError("A fixture file must contain examples with unique identifiers.")
    return fixtures


def _events(old: list[str], new: list[str], changes: list[JsonDict]) -> dict[tuple, Counter]:
    """Validate total one-to-one coverage; identical occurrences are interchangeable."""
    events: dict[tuple, Counter] = defaultdict(Counter)
    used_old: list[int] = []
    used_new: list[int] = []
    for change in changes:
        a, b, status = change["old_index"], change["new_index"], change["status"]
        if status not in STATUSES or (a is None and b is None):
            raise ValueError("Invalid change status or empty correspondence.")
        if (status == "added") != (a is None) or (status == "removed") != (b is None):
            raise ValueError("Added/removed status does not match absent passage indices.")
        for index, passages, used in ((a, old, used_old), (b, new, used_new)):
            if index is not None:
                if type(index) is not int or not 0 <= index < len(passages):
                    raise ValueError("Passage index is out of range or not an integer.")
                used.append(index)
        key = (old[a] if a is not None else None, new[b] if b is not None else None)
        events[key][status] += 1
    if sorted(used_old) != list(range(len(old))) or sorted(used_new) != list(range(len(new))):
        raise ValueError("Every passage must occur exactly once in a comparison.")
    return dict(events)


def _prf(tp: int, predicted: int, expected: int) -> JsonDict:
    precision = tp / predicted if predicted else 0.0
    recall = tp / expected if expected else 0.0
    return {
        "true_positive": tp,
        "predicted": predicted,
        "expected": expected,
        "precision": precision,
        "recall": recall,
        "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
    }


def score_changes(
    old: list[str], new: list[str], expected: list[JsonDict], predicted: list[JsonDict]
) -> JsonDict:
    gold, guess = _events(old, new, expected), _events(old, new, predicted)
    gold_pairs = Counter(
        {key: sum(labels.values()) for key, labels in gold.items() if None not in key}
    )
    pred_pairs = Counter(
        {key: sum(labels.values()) for key, labels in guess.items() if None not in key}
    )
    gold_material = Counter(
        {key: sum(v for s, v in labels.items() if s in MATERIAL) for key, labels in gold.items()}
    )
    pred_material = Counter(
        {key: sum(v for s, v in labels.items() if s in MATERIAL) for key, labels in guess.items()}
    )
    confusion: dict[str, Counter] = defaultdict(Counter)
    # Match equal statuses first when repeated identical passages admit equivalent assignments.
    for key in gold.keys() | guess.keys():
        remaining_gold, remaining_pred = (
            gold.get(key, Counter()).copy(),
            guess.get(key, Counter()).copy(),
        )
        for status, count in (remaining_gold & remaining_pred).items():
            confusion[status][status] += count
            remaining_gold[status] -= count
            remaining_pred[status] -= count
        gold_labels = sorted(remaining_gold.elements())
        pred_labels = sorted(remaining_pred.elements())
        for i in range(max(len(gold_labels), len(pred_labels))):
            g = gold_labels[i] if i < len(gold_labels) else "no_gold_correspondence"
            p = pred_labels[i] if i < len(pred_labels) else "no_predicted_correspondence"
            confusion[g][p] += 1
    abstentions = sum(change["status"] == "uncertain" for change in predicted)
    covered_gold = sum(
        count
        for g, row in confusion.items()
        if g in STATUSES
        for p, count in row.items()
        if p in STATUSES - {"uncertain"}
    )
    risky_misses = sum(confusion.get(g, {}).get(p, 0) for g in MATERIAL for p in EQUIVALENT)
    material_abstentions = sum(confusion.get(g, {}).get("uncertain", 0) for g in MATERIAL)
    material_tp = sum((gold_material & pred_material).values())
    return {
        "alignment": _prf(
            sum((gold_pairs & pred_pairs).values()),
            sum(pred_pairs.values()),
            sum(gold_pairs.values()),
        ),
        "material_change": _prf(
            material_tp, sum(pred_material.values()), sum(gold_material.values())
        ),
        "gold_events": len(expected),
        "predicted_events": len(predicted),
        "abstentions": abstentions,
        "prediction_coverage": (len(predicted) - abstentions) / len(predicted)
        if predicted
        else 1.0,
        "covered_gold_events": covered_gold,
        "aligned_gold_coverage": covered_gold / len(expected) if expected else 1.0,
        "risky_misses": risky_misses,
        "material_abstentions": material_abstentions,
        "missed_material_events": sum(gold_material.values()) - material_tp,
        "confusion": {g: dict(sorted(row.items())) for g, row in sorted(confusion.items()) if row},
    }


def aggregate(scores: list[JsonDict]) -> JsonDict:
    totals = {
        name: sum(score[name] for score in scores)
        for name in (
            "gold_events",
            "predicted_events",
            "abstentions",
            "covered_gold_events",
            "risky_misses",
            "material_abstentions",
            "missed_material_events",
        )
    }
    for metric in ("alignment", "material_change"):
        totals[metric] = _prf(
            *(
                sum(score[metric][field] for score in scores)
                for field in ("true_positive", "predicted", "expected")
            )
        )
    totals["prediction_coverage"] = (
        1 - totals["abstentions"] / totals["predicted_events"]
        if totals["predicted_events"]
        else 1.0
    )
    totals["aligned_gold_coverage"] = (
        totals["covered_gold_events"] / totals["gold_events"] if totals["gold_events"] else 1.0
    )
    confusion: dict[str, Counter] = defaultdict(Counter)
    for score in scores:
        for status, row in score["confusion"].items():
            confusion[status].update(row)
    totals["confusion"] = {g: dict(sorted(row.items())) for g, row in sorted(confusion.items())}
    return totals


def evaluate_dataset(
    fixtures: list[JsonDict],
    comparator: Callable[[str, str], JsonDict],
    splitter: Callable[[str], list[str]],
) -> tuple[JsonDict, list[JsonDict]]:
    outputs, scores, latencies = [], [], []
    tagged_scores: dict[str, list] = defaultdict(list)
    for fixture in fixtures:
        old, new = splitter(fixture["old_text"]), splitter(fixture["new_text"])
        _events(old, new, fixture["expected"])  # Invalid ground truth must stop the run.
        start = time.perf_counter()
        output = {
            "id": fixture["id"],
            "domain": fixture["domain"],
            "tags": fixture["tags"],
            "expected": fixture["expected"],
        }
        try:
            prediction = comparator(fixture["old_text"], fixture["new_text"])
            elapsed = (time.perf_counter() - start) * 1000
            score = score_changes(old, new, fixture["expected"], prediction["changes"])
            output.update(prediction=prediction, metrics=score, wall_time_ms=elapsed)
            scores.append(score)
            latencies.append(elapsed)
            for tag in fixture["tags"]:
                tagged_scores[tag].append(score)
        except Exception as exc:
            output.update(
                error=f"{type(exc).__name__}: {exc}",
                wall_time_ms=(time.perf_counter() - start) * 1000,
            )
        outputs.append(output)
    failures = len(outputs) - len(scores)
    summary = {
        "examples": len(fixtures),
        "successful_examples": len(scores),
        "failed_examples": failures,
        "complete": failures == 0,
        "metrics_scope": "all examples"
        if not failures
        else "successful examples only; this run is incomplete",
        "metrics": aggregate(scores),
        "by_tag": {
            tag: {"examples": len(items), **aggregate(items)}
            for tag, items in sorted(tagged_scores.items())
        },
        "latency_ms": {
            "first_successful_example": latencies[0] if latencies else None,
            "mean_including_initialization": statistics.mean(latencies) if latencies else None,
            "median": statistics.median(latencies) if latencies else None,
            "p95_nearest_rank": sorted(latencies)[math.ceil(0.95 * len(latencies)) - 1]
            if latencies
            else None,
        },
    }
    return summary, outputs


def source_hashes(dataset_path: Path) -> dict[str, str]:
    paths = [dataset_path, Path(__file__)] + sorted((ROOT / "radar").glob("*.py"))
    paths += [
        p
        for name in (
            "pyproject.toml",
            "requirements.txt",
            "requirements.lock",
            "uv.lock",
            "docs/evaluation-freeze.json",
        )
        if (p := ROOT / name).exists()
    ]
    return {
        str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=("lexical", "semantic"), required=True)
    parser.add_argument("--split", choices=("dev", "test"), required=True)
    parser.add_argument(
        "--output", type=Path, help="Directory for summary.json and predictions.jsonl."
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress stdout summary; requires --output so results are saved.",
    )
    args = parser.parse_args(argv)
    if args.quiet and args.output is None:
        parser.error("--quiet requires --output so results are saved")
    sys.path.insert(0, str(ROOT))
    from radar.compare import compare_documents, split_passages

    dataset_path = ROOT / "evaluation" / f"{args.split}.jsonl"
    summary, predictions = evaluate_dataset(
        load_fixtures(dataset_path),
        lambda old, new: compare_documents(old, new, backend=args.backend),
        split_passages,
    )
    packages = {}
    for name in ("numpy", "scipy", "onnxruntime", "tokenizers", "huggingface-hub", "gradio"):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            pass
    summary.update(
        schema_version=1,
        backend=args.backend,
        split=args.split,
        created_at=datetime.now(timezone.utc).isoformat(),
        provenance="AI-authored synthetic fixtures, not human validated. No claim of real-world accuracy.",
        source_hashes=source_hashes(dataset_path),
        environment={
            "python": platform.python_version(),
            "platform": platform.platform(),
            "packages": packages,
        },
        models=next(
            (
                item["prediction"].get("models", {})
                for item in predictions
                if item.get("prediction", {}).get("models")
            ),
            {},
        ),
    )
    rendered = json.dumps(summary, indent=2, sort_keys=True)
    if args.output:
        args.output.mkdir(parents=True, exist_ok=True)
        (args.output / "summary.json").write_text(rendered + "\n", encoding="utf-8")
        (args.output / "predictions.jsonl").write_text(
            "".join(json.dumps(item, sort_keys=True) + "\n" for item in predictions),
            encoding="utf-8",
        )
    if not args.quiet:
        print(rendered)
    return 0 if summary["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
