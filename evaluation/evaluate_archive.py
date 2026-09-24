"""Score an archived engine with current group metrics and isolated inference."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import statistics
import subprocess
import sys
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from evaluation.real_evaluate import (
    ROOT,
    cached_model_artifacts,
    evaluate_dataset,
    load_manifest,
    source_hashes,
)
from radar.compare import split_passages

ARCHIVE = ROOT / "artifacts/evaluation/baseline-v1.zip"
WORKER = """
import inspect, json, sys, time
sys.path.insert(0, sys.argv[1])
from radar.compare import compare_documents
assert compare_documents.__code__.co_filename.startswith(sys.argv[1] + "/"), "Expected archived inference module"
outcomes = []
supports_context = "old_contexts" in inspect.signature(compare_documents).parameters
for item in json.load(sys.stdin):
    started = time.perf_counter()
    try:
        contexts = item["contexts"] if supports_context else {}
        result = {"prediction": compare_documents(*item["texts"], backend="semantic", **contexts)}
    except Exception as exc:
        result = {"error": f"{type(exc).__name__}: {exc}"}
    result["wall_time_ms"] = (time.perf_counter() - started) * 1000
    outcomes.append(result)
print(json.dumps(outcomes))
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--archive", type=Path, default=ARCHIVE)
    args = parser.parse_args(argv)
    manifest = load_manifest(args.manifest)
    archive_path = args.archive.resolve()
    inputs, worker_inputs, case_keys = [], [], {}
    for case in manifest["cases"]:
        try:
            texts = tuple(
                (ROOT / case[s]["text_path"]).read_text(encoding="utf-8") for s in ("old", "new")
            )
            contexts = {
                f"{side}_contexts": json.loads((ROOT / case[side]["contexts_path"]).read_text())
                for side in ("old", "new")
                if case[side].get("contexts_path")
            }
        except (OSError, UnicodeError, json.JSONDecodeError):
            continue  # evaluate_dataset reports input failures against the full case denominator.
        case_keys[case["id"]] = texts
        inputs.append(texts)
        worker_inputs.append({"texts": texts, "contexts": contexts})
    started = time.perf_counter()
    worker = subprocess.run(
        [sys.executable, "-c", WORKER, str(archive_path)],
        input=json.dumps(worker_inputs),
        capture_output=True,
        text=True,
        env={**os.environ, "HF_HUB_OFFLINE": "1"},
    )
    worker_seconds = time.perf_counter() - started
    if worker.returncode:
        results = [
            {"error": f"Archive subprocess failed: {worker.stderr}", "wall_time_ms": None}
            for _ in inputs
        ]
    else:
        results = json.loads(worker.stdout)
        if len(results) != len(inputs):
            raise ValueError("Archive subprocess returned an incomplete outcome list.")
    lookup = dict(zip(inputs, results))

    def compare(old: str, new: str, **contexts) -> dict:
        result = lookup[(old, new)]
        if "error" in result:
            raise RuntimeError(result["error"])
        return result["prediction"]

    summary, predictions = evaluate_dataset(manifest["cases"], compare, split_passages)
    latencies = []
    for prediction in predictions:
        key = case_keys.get(prediction["id"])
        outcome = lookup.get(key, {})
        prediction["validation_wall_time_ms"] = prediction.pop("wall_time_ms")
        prediction["wall_time_ms"] = outcome.get("wall_time_ms")
        if prediction["success"]:
            latencies.append(prediction["wall_time_ms"])
    hashes = source_hashes(args.manifest, manifest)
    hashes[str(Path(__file__).relative_to(ROOT))] = hashlib.sha256(
        Path(__file__).read_bytes()
    ).hexdigest()
    with zipfile.ZipFile(archive_path) as archive:
        member_hashes = {
            name: hashlib.sha256(archive.read(name)).hexdigest() for name in archive.namelist()
        }
    summary.update(
        schema_version=2,
        profile=archive_path.stem.replace("baseline-", "archived_"),
        backend="semantic",
        created_at=datetime.now(timezone.utc).isoformat(),
        archive={
            "path": os.path.relpath(archive_path, ROOT),
            "sha256": hashlib.sha256(archive_path.read_bytes()).hexdigest(),
            "members": member_hashes,
        },
        source_hashes=hashes,
        provenance="Archived inference; current group metrics and input validation. Current radar hashes describe validation/provenance, not executed inference. Context sidecars are passed only if the archived API supports them.",
        configured_model_artifacts=cached_model_artifacts("semantic"),
        models=next(
            (
                p["prediction"]["models"]
                for p in predictions
                if p.get("prediction", {}).get("models")
            ),
            {},
        ),
        archive_subprocess_seconds=worker_seconds,
        archive_subprocess_stderr=worker.stderr,
        latency_ms={
            "scope": "Archived subprocess compare_documents calls, including first model initialization; excludes parent lookup/scoring and process startup.",
            "first_successful_case": latencies[0] if latencies else None,
            "mean_including_initialization": statistics.mean(latencies) if latencies else None,
            "median": statistics.median(latencies) if latencies else None,
            "p95_nearest_rank": sorted(latencies)[math.ceil(0.95 * len(latencies)) - 1]
            if latencies
            else None,
        },
    )
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    (args.output / "predictions.jsonl").write_text(
        "".join(json.dumps(p) + "\n" for p in predictions), encoding="utf-8"
    )
    (args.output / "archive-outcomes.json").write_text(
        json.dumps(results, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))
    return 0 if summary["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
