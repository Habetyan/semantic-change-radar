"""Fixed-classifier NLI diagnostic on known real-document development labels.

Reproduce: python -m evaluation.compare_nli --output artifacts/evaluation/nli-comparison
No alignment, threshold tuning, truncation, or fresh-holdout access is performed.
"""

from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import platform
import statistics
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import onnxruntime
from huggingface_hub import hf_hub_download

from evaluation.evaluate import _prf
from radar.compare import _classify
from radar.models import (
    CPU_THREADS,
    NLI_MODEL,
    NLI_REVISION,
    _nli_labels,
    _OnnxModel,
    _probabilities,
)

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = "cross-encoder/nli-deberta-v3-small"
CANDIDATE_REVISION = "fa2804872c3b4bd748f38c0185cc85775361e735"


def digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def examples() -> tuple[list[dict], dict]:
    manifest_path = ROOT / "evaluation/real/manifest.json"
    sources = {str(manifest_path.relative_to(ROOT)): digest(manifest_path)}
    records = []
    for case in json.loads(manifest_path.read_text())["cases"]:
        if not case.get("annotation_path"):
            continue
        annotation_path = ROOT / case["annotation_path"]
        sources[case["annotation_path"]] = digest(annotation_path)
        passages = {}
        for side in ("old", "new"):
            path = ROOT / case[side]["passages_path"]
            sources[case[side]["passages_path"]] = digest(path)
            passages[side] = json.loads(path.read_text())
        for event in json.loads(annotation_path.read_text())["events"]:
            if event["status"] not in {"modified", "reworded"}:
                continue
            if len(event["old_indices"]) != 1 or len(event["new_indices"]) != 1:
                continue
            old, new = event["old_indices"][0], event["new_indices"][0]
            records.append(
                {
                    "case_id": case["id"],
                    "old_index": old,
                    "new_index": new,
                    "old_text": passages["old"][old],
                    "new_text": passages["new"][new],
                    "expected": event["status"],
                }
            )
    return records, sources


def metrics(records: list[dict]) -> dict:
    confusion = defaultdict(Counter)
    for record in records:
        confusion[record["expected"]][record["status"]] += 1
    return {
        "count": len(records),
        "confusion": {key: dict(value) for key, value in confusion.items()},
        "material": _prf(
            sum(r["expected"] == r["status"] == "modified" for r in records),
            sum(r["status"] == "modified" for r in records),
            sum(r["expected"] == "modified" for r in records),
        ),
        "status_accuracy": sum(r["expected"] == r["status"] for r in records) / len(records)
        if records
        else None,
        "material_as_equivalent_misses": sum(
            r["expected"] == "modified" and r["status"] == "reworded" for r in records
        ),
        "abstentions": sum(r["status"] == "uncertain" for r in records),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--warm-runs", type=int, default=3)
    parser.add_argument("--batch-size", type=int, choices=(1, 8), default=1)
    args = parser.parse_args()
    if args.warm_runs < 1:
        parser.error("--warm-runs must be positive")
    records, sources = examples()
    summary = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "scope": "Known development data; provisional AI-reviewed labels, not a fresh holdout.",
        "unit": "Gold-aligned changed singleton passage pairs; alignment bypassed.",
        "excluded_gold": ["unchanged", "uncertain", "added", "removed", "split/merge"],
        "eligible_count": len(records),
        "class_counts": dict(Counter(r["expected"] for r in records)),
        "source_hashes": sources,
        "classifier_sha256": hashlib.sha256(inspect.getsource(_classify).encode()).hexdigest(),
        "code_hashes": {
            p: digest(ROOT / p)
            for p in ("radar/compare.py", "radar/models.py", "evaluation/compare_nli.py")
        },
        "runtime": {
            "python": platform.python_version(),
            "onnxruntime": onnxruntime.__version__,
            "provider": "CPUExecutionProvider",
            "cpu_threads": CPU_THREADS,
            "inter_op_threads": 1,
            "batch_size": args.batch_size,
            "platform": platform.platform(),
        },
        "models": {},
        "failures": [],
        "token_limit_exclusions": [],
        "limitations": [
            "Fixed production classification guards and thresholds; candidate was not calibrated.",
            "Models trained on SNLI/MultiNLI; documentation is a domain shift.",
            "Deterministic CPU inference; warm repetitions measure timing, not statistical uncertainty.",
            "First initialization includes any cache misses/downloads; warm timing excludes initialization.",
        ],
    }
    loaded = {}
    for name, repo, revision in (
        ("minilm", NLI_MODEL, NLI_REVISION),
        ("deberta", CANDIDATE, CANDIDATE_REVISION),
    ):
        start = time.perf_counter()
        try:
            model = _OnnxModel(repo, revision)
            initialization = time.perf_counter() - start
            artifacts = {}
            for filename in (
                "config.json",
                "tokenizer_config.json",
                "tokenizer.json",
                model.filename,
            ):
                path = Path(
                    hf_hub_download(repo, filename, revision=revision, local_files_only=True)
                )
                artifacts[filename] = {"sha256": digest(path), "bytes": path.stat().st_size}
            summary["models"][name] = {
                **model.metadata(),
                "initialization_seconds": initialization,
                "artifacts": artifacts,
                "labels": _nli_labels(model.config),
            }
            loaded[name] = model
        except Exception as exc:
            summary["failures"].append(
                {"model": name, "stage": "initialization", "error": str(exc)}
            )
    eligible = []
    for record in records:
        invalid = {}
        for name, model in loaded.items():
            lengths = [
                len(model.tokenizer.encode(a, b).ids)
                for a, b in (
                    (record["old_text"], record["new_text"]),
                    (record["new_text"], record["old_text"]),
                )
            ]
            if max(lengths) > model.max_length:
                invalid[name] = {"tokens": lengths, "limit": model.max_length}
        if invalid:
            summary["token_limit_exclusions"].append({**record, "models": invalid})
        else:
            eligible.append(record)
    pairs = [
        (r[a], r[b])
        for r in eligible
        for a, b in (("old_text", "new_text"), ("new_text", "old_text"))
    ]
    outputs = []
    for name, model in loaded.items():
        try:
            timings = []
            predictions = []
            for _ in range(args.warm_runs + 1):
                start = time.perf_counter()
                scores = [
                    row
                    for logits, _ in model.batches(pairs, batch_size=args.batch_size)
                    for row in _probabilities(logits, _nli_labels(model.config))
                ]
                predictions = []
                for index, record in enumerate(eligible):
                    prediction = dict(record)
                    _classify(prediction, scores[index * 2], scores[index * 2 + 1])
                    prediction.update(forward=scores[index * 2], reverse=scores[index * 2 + 1])
                    predictions.append(prediction)
                timings.append(time.perf_counter() - start)
            result = summary["models"][name]
            result.update(
                metrics=metrics(predictions),
                first_inference_seconds=timings[0],
                first_total_seconds=result["initialization_seconds"] + timings[0],
                warm_seconds=timings[1:],
                warm_median_seconds=statistics.median(timings[1:]),
            )
            outputs.extend({"model": name, **p} for p in predictions)
        except Exception as exc:
            summary["failures"].append({"model": name, "stage": "inference", "error": str(exc)})
    summary["common_scored_count"] = len(eligible)
    summary["always_material_baseline"] = metrics([{**r, "status": "modified"} for r in eligible])
    summary["complete"] = not summary["failures"] and len(loaded) == 2
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    (args.output / "predictions.jsonl").write_text("".join(json.dumps(p) + "\n" for p in outputs))
    print(json.dumps(summary, indent=2), flush=True)
    return 0 if summary["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
