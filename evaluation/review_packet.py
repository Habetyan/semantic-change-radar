"""Build an offline human review form without changing frozen annotations."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
STATUSES = {"unchanged", "reworded", "modified", "added", "removed", "uncertain"}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_hash(value: object) -> str:
    return digest(json.dumps(value, sort_keys=True, ensure_ascii=True).encode())


def indices(value: object, count: int) -> bool:
    return (
        isinstance(value, list)
        and all(type(i) is int and 0 <= i < count for i in value)
        and len(value) == len(set(value))
    )


def build_packet(manifests: list[Path], output: Path, *, root: Path = ROOT) -> Path:
    corpus_hashes, annotation_hashes, cases = {}, {}, []
    seen = set()

    def read(path: str, hashes: dict) -> bytes:
        data = (root / path).read_bytes()
        hashes[path] = digest(data)
        return data

    for manifest_path in manifests:
        path = manifest_path if manifest_path.is_absolute() else root / manifest_path
        label = path.resolve().relative_to(root.resolve()).as_posix()
        manifest = json.loads(read(label, corpus_hashes))
        for case in manifest["cases"]:
            uid = digest(f"{label}:{case['id']}".encode())[:16]
            if uid in seen:
                raise ValueError(f"Duplicate case in packet: {case['id']}")
            seen.add(uid)
            record = {"id": uid, "name": str(case["id"]), "manifest": label}
            for side in ("old", "new"):
                source = case[side]
                passages = json.loads(read(source["passages_path"], corpus_hashes))
                if not isinstance(passages, list) or any(not isinstance(p, str) for p in passages):
                    raise ValueError("Passages must be a list of strings.")
                for key in ("raw_path", "text_path"):
                    if source.get(key):
                        read(source[key], corpus_hashes)
                url = source.get("source_url", "")
                if not isinstance(url, str) or urlparse(url).scheme not in {"http", "https"}:
                    url = ""
                record[side] = {
                    "passages": passages,
                    "source_url": url,
                    "revision": str(source.get("tag") or source.get("commit") or "Source revision"),
                }
            annotation_path = case.get("annotation_path")
            annotation = (
                json.loads(read(annotation_path, annotation_hashes)) if annotation_path else {}
            )
            events = []
            for number, event in enumerate(annotation.get("events", [])):
                if event.get("status") not in STATUSES or not isinstance(
                    event.get("rationale"), str
                ):
                    raise ValueError("Invalid proposed classification or rationale.")
                for side in ("old", "new"):
                    if not indices(event.get(f"{side}_indices"), len(record[side]["passages"])):
                        raise ValueError("Invalid proposed correspondence indices.")
                if not event["old_indices"] and not event["new_indices"]:
                    raise ValueError("A proposed group cannot be empty on both sides.")
                events.append(
                    {
                        "id": f"{uid}:{number}",
                        "old_indices": event["old_indices"],
                        "new_indices": event["new_indices"],
                        "proposed_status": event["status"],
                        "proposed_rationale": event["rationale"],
                    }
                )
            record["events"] = events
            cases.append(record)
    template = (Path(__file__).parent / "templates/review_packet.html").read_text()
    packet = {
        "form_template_hash": digest(template.encode()),
        "schema_version": 1,
        "corpus_hash": canonical_hash(corpus_hashes),
        "annotation_hash": canonical_hash(annotation_hashes),
        "corpus_files": corpus_hashes,
        "annotation_files": annotation_hashes,
        "cases": cases,
    }
    packet["packet_hash"] = canonical_hash(packet)
    data = (
        json.dumps(packet, ensure_ascii=True)
        .replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
    )
    page = template.replace("__PACKET_DATA__", data)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(page, encoding="utf-8")
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", action="append", type=Path)
    parser.add_argument("--output", type=Path, default=Path("docs/review/index.html"))
    args = parser.parse_args()
    print(build_packet(args.manifest or [Path("evaluation/fresh-v2/manifest.json")], args.output))


if __name__ == "__main__":
    main()
