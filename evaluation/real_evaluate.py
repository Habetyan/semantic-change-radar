"""Evaluate frozen backends on complete, pinned documentation revisions.

Group annotations support passage splits and merges. Labels remain provisional
until human review; this harness does not treat source authenticity as label truth.
"""

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

from evaluation.evaluate import EQUIVALENT, MATERIAL, ROOT, STATUSES, _prf

JsonDict = dict[str, Any]
Group = tuple[tuple[int, ...], tuple[int, ...]]
COUNT_FIELDS = (
    "gold_events",
    "predicted_events",
    "gold_ambiguous_events",
    "gold_singleton_events",
    "gold_changed_paired_groups",
    "gold_split_merge_groups",
    "conditional_eligible_events",
    "conditional_scored_events",
    "conditional_abstentions",
    "conditional_correct_status",
    "risky_misses",
    "material_abstentions",
    "predicted_material_excluded_ambiguous",
    "predicted_abstentions",
)
METRIC_FIELDS = (
    "alignment_edges",
    "changed_alignment_edges",
    "exact_group_correspondence",
    "end_to_end_material",
    "conditional_material",
)


def validate_events(
    old: list[str],
    new: list[str],
    events: list[JsonDict],
    *,
    annotation: bool = True,
) -> dict[Group, str]:
    """Require a total partition; index identity is retained, even for duplicates."""
    if not isinstance(events, list):
        raise ValueError("Events must be a list.")
    used = [[], []]
    groups = {}
    for event in events:
        status = event.get("status")
        a, b = event.get("old_indices"), event.get("new_indices")
        if not isinstance(a, list) or not isinstance(b, list) or not (a or b):
            raise ValueError("Each event requires nonempty correspondence index lists.")
        if status not in STATUSES:
            raise ValueError("Unknown event status.")
        if (status == "added") != (not a) or (status == "removed") != (not b):
            raise ValueError("Added/removed status does not match absent passage indices.")
        if annotation and not isinstance(event.get("rationale"), str):
            raise ValueError("Annotations require a rationale string.")
        for side, indices, passages in ((0, a, old), (1, b, new)):
            if any(type(i) is not int or not 0 <= i < len(passages) for i in indices):
                raise ValueError("Passage index is out of range or not an integer.")
            used[side].extend(indices)
        groups[(tuple(sorted(a)), tuple(sorted(b)))] = status
    if sorted(used[0]) != list(range(len(old))) or sorted(used[1]) != list(range(len(new))):
        raise ValueError("Every passage must occur exactly once in the event partition.")
    return groups


def _prediction_events(changes: list[JsonDict]) -> list[JsonDict]:
    return [
        {
            "old_indices": c["old_indices"]
            if "old_indices" in c
            else ([] if c["old_index"] is None else [c["old_index"]]),
            "new_indices": c["new_indices"]
            if "new_indices" in c
            else ([] if c["new_index"] is None else [c["new_index"]]),
            "status": c["status"],
        }
        for c in changes
    ]


def _ratios(score: JsonDict) -> None:
    eligible, scored = score["conditional_eligible_events"], score["conditional_scored_events"]
    score["conditional_alignment_coverage"] = scored / eligible if eligible else None
    score["conditional_status_accuracy"] = (
        score["conditional_correct_status"] / scored if scored else None
    )
    score["conditional_decision_coverage"] = (
        1 - score["conditional_abstentions"] / scored if scored else None
    )


def score_changes(
    old: list[str],
    new: list[str],
    expected: list[JsonDict],
    changes: list[JsonDict],
) -> JsonDict:
    gold = validate_events(old, new, expected)
    predicted = validate_events(old, new, _prediction_events(changes), annotation=False)
    # Cartesian edges measure group membership, not a unique sentence alignment.
    gold_edges = {(a, b) for left, right in gold for a in left for b in right}
    predicted_edges = {(a, b) for left, right in predicted for a in left for b in right}
    unchanged_edges = {
        (a, b)
        for (left, right), status in gold.items()
        if status == "unchanged"
        for a in left
        for b in right
    }
    changed_gold_edges = gold_edges - unchanged_edges
    changed_predicted_edges = predicted_edges - unchanged_edges
    exact = gold.keys() & predicted.keys()
    eligible = {
        group
        for group, status in gold.items()
        if max(map(len, group)) == 1 and status != "uncertain"
    }
    scored = exact & eligible
    ambiguous = [group for group, status in gold.items() if status == "uncertain"]
    ambiguous_old = {i for left, _ in ambiguous for i in left}
    ambiguous_new = {i for _, right in ambiguous for i in right}
    gold_material = {group for group, status in gold.items() if status in MATERIAL}
    predicted_material = {group for group, status in predicted.items() if status in MATERIAL}
    excluded = {
        group
        for group in predicted_material
        if ambiguous_old.intersection(group[0]) or ambiguous_new.intersection(group[1])
    }
    predicted_material -= excluded
    confusion: dict[str, Counter] = defaultdict(Counter)
    for group in scored:
        confusion[gold[group]][predicted[group]] += 1
    score = {
        "alignment_edges": _prf(
            len(gold_edges & predicted_edges),
            len(predicted_edges),
            len(gold_edges),
        ),
        "exact_group_correspondence": _prf(len(exact), len(predicted), len(gold)),
        "changed_alignment_edges": _prf(
            len(changed_gold_edges & changed_predicted_edges),
            len(changed_predicted_edges),
            len(changed_gold_edges),
        ),
        "end_to_end_material": _prf(
            len(gold_material & predicted_material),
            len(predicted_material),
            len(gold_material),
        ),
        "conditional_material": _prf(
            len(scored & gold_material & predicted_material),
            len(scored & predicted_material),
            len(scored & gold_material),
        ),
        "gold_events": len(gold),
        "predicted_events": len(predicted),
        "gold_ambiguous_events": len(ambiguous),
        "gold_singleton_events": sum(max(map(len, group)) == 1 for group in gold),
        "gold_changed_paired_groups": sum(
            bool(group[0] and group[1]) and status != "unchanged" for group, status in gold.items()
        ),
        "gold_split_merge_groups": sum(
            bool(left and right) and max(len(left), len(right)) > 1 for left, right in gold
        ),
        "conditional_eligible_events": len(eligible),
        "conditional_scored_events": len(scored),
        "conditional_abstentions": sum(predicted[g] == "uncertain" for g in scored),
        "conditional_correct_status": sum(gold[g] == predicted[g] for g in scored),
        "predicted_abstentions": sum(status == "uncertain" for status in predicted.values()),
        "predicted_material_excluded_ambiguous": len(excluded),
        "risky_misses": sum(gold[g] in MATERIAL and predicted[g] in EQUIVALENT for g in scored),
        "material_abstentions": sum(
            gold[g] in MATERIAL and predicted[g] == "uncertain" for g in scored
        ),
        "conditional_confusion": {
            status: dict(sorted(row.items())) for status, row in sorted(confusion.items())
        },
    }
    _ratios(score)
    return score


def aggregate(scores: list[JsonDict]) -> JsonDict:
    result = {field: sum(score[field] for score in scores) for field in COUNT_FIELDS}
    for metric in METRIC_FIELDS:
        result[metric] = _prf(
            *(
                sum(score[metric][field] for score in scores)
                for field in ("true_positive", "predicted", "expected")
            )
        )
    confusion: dict[str, Counter] = defaultdict(Counter)
    for score in scores:
        for status, row in score["conditional_confusion"].items():
            confusion[status].update(row)
    result["conditional_confusion"] = {
        status: dict(sorted(row.items())) for status, row in sorted(confusion.items())
    }
    _ratios(result)
    return result


def load_manifest(path: Path) -> JsonDict:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    cases = manifest.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("Manifest must contain a nonempty cases list.")
    ids = [case.get("id") for case in cases]
    if any(not isinstance(identifier, str) or not identifier for identifier in ids):
        raise ValueError("Case identifiers must be nonempty strings.")
    if len(ids) != len(set(ids)):
        raise ValueError("Case identifiers must be unique.")
    return manifest


def evaluate_dataset(
    cases: list[JsonDict],
    comparator: Callable[..., JsonDict],
    splitter: Callable[[str], list[str]],
    *,
    root: Path = ROOT,
) -> tuple[JsonDict, list[JsonDict]]:
    outputs, scores, latencies = [], [], []
    for case in cases:
        start = time.perf_counter()
        output = {"id": case["id"], "repository": case["repository"], "metrics": None}
        stage = "input"
        try:
            texts, passages, contexts = [], [], {}
            for side in ("old", "new"):
                texts.append((root / case[side]["text_path"]).read_text(encoding="utf-8"))
                segments = json.loads(
                    (root / case[side]["passages_path"]).read_text(encoding="utf-8")
                )
                if not isinstance(segments, list) or any(not isinstance(p, str) for p in segments):
                    raise ValueError("Passages must be a JSON list of strings.")
                passages.append(segments)
                if case[side].get("contexts_path"):
                    contexts[f"{side}_contexts"] = json.loads(
                        (root / case[side]["contexts_path"]).read_text(encoding="utf-8")
                    )
            output.update(old_count=len(passages[0]), new_count=len(passages[1]))
            annotation = None
            stage = "annotation"
            if case.get("annotation_path"):
                annotation = json.loads(
                    (root / case["annotation_path"]).read_text(encoding="utf-8")
                )
                if annotation["case_id"] != case["id"]:
                    raise ValueError("Annotation case_id does not match manifest.")
                if annotation["review_status"] != "ai_reviewed_pending_human":
                    raise ValueError("Unexpected annotation review status.")
                validate_events(*passages, annotation["events"])
                output.update(
                    review_status=annotation["review_status"],
                    expected=annotation["events"],
                )
            stage = "segmentation"
            # Validate with the frozen production splitter, including input limits.
            for text, saved in zip(texts, passages):
                if splitter(text) != saved:
                    raise ValueError("Saved passages do not match the frozen production splitter.")
            stage = "inference"
            prediction = comparator(*texts, **contexts)
            output["prediction"] = prediction
            stage = "scoring"
            validate_events(*passages, _prediction_events(prediction["changes"]), annotation=False)
            if annotation is not None:
                output["metrics"] = score_changes(
                    *passages, annotation["events"], prediction["changes"]
                )
                scores.append(output["metrics"])
            output["success"] = True
        except Exception as exc:
            output.update(success=False, error_stage=stage, error=f"{type(exc).__name__}: {exc}")
        output["wall_time_ms"] = (time.perf_counter() - start) * 1000
        if output["success"]:
            latencies.append(output["wall_time_ms"])
        outputs.append(output)
    failures = sum(not output["success"] for output in outputs)
    annotated = sum(bool(case.get("annotation_path")) for case in cases)
    summary = {
        "requested_cases": len(cases),
        "successful_cases": len(cases) - failures,
        "failed_cases": failures,
        "failure_rate": failures / len(cases) if cases else None,
        "annotated_cases": annotated,
        "scored_cases": len(scores),
        "unscored_annotated_cases": annotated - len(scores),
        "complete": failures == 0,
        "metrics_scope": "successful annotated cases only; inspect failure rate and scored_cases",
        "metrics": aggregate(scores) if scores else None,
        "failures_by_stage": dict(
            Counter(output["error_stage"] for output in outputs if not output["success"])
        ),
        "latency_ms": {
            "scope": "successful cases, including file loading and scoring",
            "first_successful_case": latencies[0] if latencies else None,
            "mean_including_initialization": statistics.mean(latencies) if latencies else None,
            "median": statistics.median(latencies) if latencies else None,
            "p95_nearest_rank": sorted(latencies)[math.ceil(0.95 * len(latencies)) - 1]
            if latencies
            else None,
        },
    }
    return summary, outputs


def source_hashes(manifest_path: Path, manifest: JsonDict) -> dict[str, str]:
    paths = {manifest_path.resolve(), Path(__file__).resolve(), ROOT / "evaluation/evaluate.py"}
    paths.update((ROOT / "radar").glob("*.py"))
    for name in (
        "pyproject.toml",
        "requirements.txt",
        "requirements.lock",
        "docs/evaluation-freeze.json",
        "docs/real-evaluation-freeze.json",
    ):
        if (ROOT / name).exists():
            paths.add(ROOT / name)
    if manifest.get("freeze_path"):
        paths.add(ROOT / manifest["freeze_path"])
    for case in manifest["cases"]:
        for side in ("old", "new"):
            for field in ("text_path", "passages_path", "raw_path", "contexts_path"):
                if case[side].get(field):
                    paths.add(ROOT / case[side][field])
        if case.get("annotation_path"):
            paths.add(ROOT / case["annotation_path"])
    return {
        str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path): hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
        if path.exists()
        else "MISSING"
        for path in sorted(paths)
    }


def cached_model_artifacts(backend: str) -> JsonDict:
    """Hash configured local model artifacts without downloading or initializing."""
    if backend != "semantic":
        return {}
    from huggingface_hub import try_to_load_from_cache

    from radar.models import EMBEDDING_MODEL, EMBEDDING_REVISION, NLI_MODEL, NLI_REVISION

    weight_file = (
        "onnx/model_qint8_arm64.onnx"
        if platform.machine().lower() in {"arm64", "aarch64"}
        else "onnx/model_quint8_avx2.onnx"
    )
    artifacts = {}
    for name, repo, revision in (
        ("embedding", EMBEDDING_MODEL, EMBEDDING_REVISION),
        ("nli", NLI_MODEL, NLI_REVISION),
    ):
        files = [weight_file, "config.json", "tokenizer.json", "tokenizer_config.json"]
        if name == "embedding":
            files.append("sentence_bert_config.json")
        hashes = {}
        for filename in files:
            cached = try_to_load_from_cache(repo, filename, revision=revision)
            hashes[filename] = (
                hashlib.sha256(Path(cached).read_bytes()).hexdigest()
                if isinstance(cached, str)
                else "NOT_CACHED"
            )
        artifacts[name] = {"repo": repo, "revision": revision, "file_hashes": hashes}
    return artifacts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=("lexical", "semantic"), required=True)
    parser.add_argument(
        "--profile", choices=("baseline", "context", "groups", "verified"), default="verified"
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, default=ROOT / "evaluation/real/manifest.json")
    args = parser.parse_args(argv)
    from radar.compare import compare_documents, split_passages

    manifest = load_manifest(args.manifest)
    summary, predictions = evaluate_dataset(
        manifest["cases"],
        lambda old, new, **contexts: compare_documents(
            old, new, backend=args.backend, profile=args.profile, **contexts
        ),
        split_passages,
    )
    packages = {}
    for name in ("numpy", "scipy", "onnxruntime", "tokenizers", "huggingface-hub", "gradio"):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            pass
    summary.update(
        schema_version=2,
        backend=args.backend,
        profile=args.profile,
        created_at=datetime.now(timezone.utc).isoformat(),
        provenance="Real source revisions with provisional AI-reviewed labels, not human validated.",
        source_hashes=source_hashes(args.manifest, manifest),
        configured_model_artifacts=cached_model_artifacts(args.backend),
        environment={
            "python": platform.python_version(),
            "platform": platform.platform(),
            "packages": packages,
        },
        models=next(
            (
                output["prediction"]["models"]
                for output in predictions
                if output.get("prediction", {}).get("models")
            ),
            {},
        ),
        metric_notes=[
            "Alignment edges are Cartesian group membership; complex rewrites can overexpand edges.",
            "Changed alignment removes gold unchanged edges from both edge sets; wrong edges remain.",
            "Exact groups retain passage indices; duplicate text occurrences are not interchangeable.",
            "Conditional status scores require exact singleton correspondence, including adds/removes.",
            "Ambiguous gold is excluded from status metrics; alignment still includes it.",
            "Material predictions touching ambiguous gold are excluded from material precision.",
            "End-to-end material credit requires the exact gold group and a material prediction.",
            "PRF is micro-averaged; zero denominators produce 0; empty conditional ratios are null.",
        ],
    )
    args.output.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(summary, indent=2, sort_keys=True)
    (args.output / "summary.json").write_text(rendered + "\n", encoding="utf-8")
    (args.output / "predictions.jsonl").write_text(
        "".join(json.dumps(item, sort_keys=True) + "\n" for item in predictions),
        encoding="utf-8",
    )
    for output in predictions:
        if not output["success"]:
            print(f"{output['id']} [{output['error_stage']}]: {output['error']}", file=sys.stderr)
    print(rendered)
    return 0 if summary["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
