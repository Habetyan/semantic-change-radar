"""Reproduce the bounded, source-audited blind-v3 Markdown corpus."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from urllib.request import urlopen

from evaluation.acquire_fresh import inline
from evaluation.acquire_real import digest, write_json
from radar.compare import split_passages

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "evaluation/blind-v3"


def extract_markdown(text: str) -> tuple[str, dict]:
    """Audited subset: ordinary Markdown, titled fences, MyST warnings, admonitions."""
    lines = text.splitlines()
    references = {m[1].lower() for m in re.finditer(r"^\s*\[([^\]]+)\]:\s*\S", text, re.M)}
    output, omissions, transformations = [], [], []
    fence = None
    skip_blank = False
    indented = []
    for number, line in enumerate(lines, 1):
        stripped = line.strip()
        marker = re.fullmatch(r"(`{3,}|~{3,})(.*)", stripped)
        if fence:
            if (
                marker
                and marker[1][0] == fence["char"]
                and len(marker[1]) >= fence["width"]
                and not marker[2]
            ):
                target = transformations if fence["keep"] else omissions
                target.append(
                    {
                        "start_line": fence["start"],
                        "end_line": number,
                        "reason": "MyST warning fence removed; visible label and prose retained"
                        if fence["keep"]
                        else "fenced code/example; visible title retained when supplied",
                    }
                )
                fence = None
                output.append("")
            elif fence["keep"]:
                output.append(line)
            continue
        if marker:
            info = marker[2].strip()
            if (
                info.startswith("{")
                and info != "{warning}"
                and not info.startswith("{program-output} ")
            ):
                raise ValueError(f"Unsupported directive at line {number}: {info}")
            keep = info == "{warning}"
            fence = {"start": number, "width": len(marker[1]), "char": marker[1][0], "keep": keep}
            title = re.search(r'title="([^"]+)"', info)
            if keep:
                output.append("Warning:")
            elif title:
                output.extend(["", title[1] + ":", ""])
                transformations.append(
                    {
                        "start_line": number,
                        "end_line": number,
                        "reason": "visible code-block title retained as prose label",
                    }
                )
            continue
        if re.match(r"^\s*\[[^\]]+\]:\s*\S", line) or re.fullmatch(r"\([^)]+\)=", stripped):
            omissions.append(
                {
                    "start_line": number,
                    "end_line": number,
                    "reason": "reference destination/target; visible labels retained",
                }
            )
            output.append("")
            continue
        if stripped in {"<details>", "</details>"} or re.fullmatch(r"[-*_]{3,}", stripped):
            omissions.append(
                {
                    "start_line": number,
                    "end_line": number,
                    "reason": "presentation wrapper or horizontal rule",
                }
            )
            output.append("")
            continue
        summary = re.fullmatch(r"<summary>(.*?)</summary>", stripped)
        if summary:
            line = summary[1]
            transformations.append(
                {
                    "start_line": number,
                    "end_line": number,
                    "reason": "HTML summary label retained; tags removed",
                }
            )
        admonition = re.fullmatch(r"!!!\s+(note|tip|warning)", stripped)
        if admonition:
            line = admonition[1].capitalize() + ":"
            skip_blank = True
            transformations.append(
                {
                    "start_line": number,
                    "end_line": number,
                    "reason": "admonition label normalized; body retained",
                }
            )
        elif stripped.startswith(("!!!", "???")):
            raise ValueError(f"Unsupported admonition at line {number}")
        elif skip_blank:
            if not stripped:
                continue
            skip_blank = False
        if line.startswith("    ") and stripped:
            indented.append(number)
        normalized = re.sub(r"\{external:py:obj\}`([^`]+)`", r"\1", line)
        normalized = re.sub(r"<a\s+[^>]*>(.*?)</a>", r"\1", normalized)
        normalized = re.sub(r"</?code>", "", normalized)
        if normalized != line:
            transformations.append(
                {
                    "start_line": number,
                    "end_line": number,
                    "reason": "inline HTML link/code or Python role normalized to visible text",
                }
            )
        output.append(normalized)
    if fence:
        raise ValueError("Unclosed code fence")
    prose = inline("\n".join(output), references)
    prose = re.sub(r"\n{3,}", "\n\n", prose).strip() + "\n"
    return prose, {
        "source_line_count": len(lines),
        "omissions": omissions,
        "transformations": transformations,
        "retained_indented_lines": indented,
        "policy": "Complete page prose, headings, lists and visible code titles. Omit fenced code, reference destinations and presentation wrappers. Preserve admonition bodies; normalize links, inline code, bold and audited Python object roles.",
        "indented_blocks_audit": "For these twelve pinned pages, unfenced indented lines were inspected: admonition bodies or list continuations, retained in full.",
    }


def acquire(*, refresh: bool = False) -> dict:
    selection = json.loads((DATA / "selection.json").read_text())
    manifest = {
        "schema_version": 1,
        "selection": "Six full Markdown revision pairs from three previously unseen repositories; twelve screened pairs; source-only purposive selection.",
        "annotation_status": "ai_authored_pending_independent_review",
        "freeze_path": "docs/blind-v3-freeze.json",
        "prediction_access_during_selection_and_annotation": False,
        "licenses": [],
        "cases": [],
    }
    for spec in selection["candidates"]:
        if spec["decision"] != "selected":
            continue
        case = {key: spec[key] for key in ("id", "repository", "license")}
        case["annotation_path"] = f"evaluation/blind-v3/annotations/{case['id']}.json"
        for side in ("old", "new"):
            revision = spec[side]
            base = f"https://raw.githubusercontent.com/{case['repository']}/{revision['commit']}"
            prefix = DATA / "documents" / case["id"] / side
            raw_path = prefix.with_suffix(".md")
            url = base + "/" + spec["upstream_path"]
            download(raw_path, url, refresh)
            raw = raw_path.read_bytes()
            if digest(raw) != revision["raw_sha256"]:
                raise ValueError(f"Pinned source hash mismatch: {case['id']} {side}")
            text, audit = extract_markdown(raw.decode("utf-8"))
            passages = split_passages(text)
            prefix.with_suffix(".txt").write_text(text, encoding="utf-8")
            write_json(prefix.with_suffix(".passages.json"), passages)
            write_json(prefix.with_suffix(".extraction.json"), audit)
            case[side] = {key: revision[key] for key in ("tag", "commit", "commit_date")}
            case[side].update(
                upstream_path=spec["upstream_path"],
                raw_url=url,
                source_url=f"https://github.com/{case['repository']}/blob/{revision['commit']}/{spec['upstream_path']}",
                raw_sha256=digest(raw),
                text_sha256=digest(text.encode()),
                raw_characters=len(raw.decode()),
                characters=len(text),
                passages=len(passages),
                app_limits_passed=True,
            )
            for field, suffix in [
                ("raw_path", ".md"),
                ("text_path", ".txt"),
                ("passages_path", ".passages.json"),
                ("audit_path", ".extraction.json"),
            ]:
                case[side][field] = str(prefix.with_suffix(suffix).relative_to(ROOT))
            for license_path in spec["license_paths"]:
                local = DATA / "licenses" / f"{case['id']}-{side}-{Path(license_path).name}"
                download(local, base + "/" + license_path, refresh)
                record = {
                    "path": str(local.relative_to(ROOT)),
                    "url": base + "/" + license_path,
                    "sha256": digest(local.read_bytes()),
                }
                if record not in manifest["licenses"]:
                    manifest["licenses"].append(record)
        manifest["cases"].append(case)
    statuses = {
        json.loads((ROOT / c["annotation_path"]).read_text())["review_status"]
        if (ROOT / c["annotation_path"]).exists()
        else manifest["annotation_status"]
        for c in manifest["cases"]
    }
    manifest["annotation_status"] = (
        next(iter(statuses)) if len(statuses) == 1 else "mixed_review_status"
    )
    write_json(DATA / "manifest.json", manifest)
    return manifest


def download(path: Path, url: str, refresh: bool) -> None:
    if path.exists() and not refresh:
        return
    with urlopen(url, timeout=30) as response:
        raw = response.read()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    result = acquire(refresh=args.refresh)
    print(
        json.dumps(
            [
                {"id": c["id"], "passages": [c[s]["passages"] for s in ("old", "new")]}
                for c in result["cases"]
            ],
            indent=2,
        )
    )
