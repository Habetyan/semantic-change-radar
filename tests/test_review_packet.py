"""Offline review generation must preserve provenance and untrusted source text."""

import json
import re
from pathlib import Path

import pytest

from evaluation.review_packet import build_packet


def fixture_manifest(root: Path) -> Path:
    for side in ("old", "new"):
        (root / f"{side}.json").write_text(
            json.dumps(["Safe sentence.", "</script><script>window.injected=1</script>"])
        )
    (root / "annotations.json").write_text(
        json.dumps(
            {
                "events": [
                    {
                        "old_indices": [0],
                        "new_indices": [0],
                        "status": "unchanged",
                        "rationale": "HIDDEN_RATIONALE",
                    },
                    {
                        "old_indices": [1],
                        "new_indices": [1],
                        "status": "modified",
                        "rationale": "<img src=x onerror=alert(1)>",
                    },
                ]
            }
        )
    )
    manifest = root / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "id": "<script>case</script>",
                        "annotation_path": "annotations.json",
                        **{
                            side: {
                                "passages_path": f"{side}.json",
                                "tag": None,
                                "commit": "abc123",
                                "source_url": "javascript:alert(1)",
                            }
                            for side in ("old", "new")
                        },
                    }
                ]
            }
        )
    )
    return manifest


def packet_data(path: Path) -> dict:
    text = path.read_text()
    return json.loads(
        re.search(r'<script type="application/json" id="packet-data">(.*?)</script>', text, re.S)[1]
    )


def test_packet_escapes_source_and_hashes_annotation_changes(tmp_path):
    manifest = fixture_manifest(tmp_path)
    output = tmp_path / "review.html"
    original = manifest.read_bytes()
    build_packet([manifest], output, root=tmp_path)
    data = packet_data(output)
    assert data["cases"][0]["old"]["revision"] == "abc123"
    assert data["cases"][0]["old"]["source_url"] == ""
    assert "</script><script>window.injected" not in output.read_text()
    assert data["cases"][0]["old"]["passages"][1].startswith("</script>")
    annotation = tmp_path / "annotations.json"
    annotation.write_text(annotation.read_text().replace("HIDDEN_RATIONALE", "Changed rationale"))
    build_packet([manifest], output, root=tmp_path)
    after = packet_data(output)
    assert after["annotation_hash"] != data["annotation_hash"]
    assert after["packet_hash"] != data["packet_hash"]
    assert after["corpus_hash"] == data["corpus_hash"]
    assert manifest.read_bytes() == original


def test_packet_rejects_duplicate_cases_and_invalid_indices(tmp_path):
    manifest = fixture_manifest(tmp_path)
    with pytest.raises(ValueError, match="Duplicate"):
        build_packet([manifest, manifest], tmp_path / "review.html", root=tmp_path)
    annotation = tmp_path / "annotations.json"
    data = json.loads(annotation.read_text())
    data["events"][0]["old_indices"] = [True]
    annotation.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="indices"):
        build_packet([manifest], tmp_path / "review.html", root=tmp_path)


def test_multiple_manifests_keep_distinct_event_ids(tmp_path):
    manifest = fixture_manifest(tmp_path)
    second = tmp_path / "second.json"
    second.write_bytes(manifest.read_bytes())
    output = tmp_path / "review.html"
    build_packet([manifest, second], output, root=tmp_path)
    cases = packet_data(output)["cases"]
    assert len(cases) == 2
    assert cases[0]["events"][0]["id"] != cases[1]["events"][0]["id"]
