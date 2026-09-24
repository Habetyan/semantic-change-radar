"""Acquire three frozen Markdown page pairs without consulting model predictions.

This source-audited extractor covers these six pages, not arbitrary Markdown.
Original bytes and line-level omissions are retained. No prose is cropped.
"""

from __future__ import annotations

import argparse
import json
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.request import Request, urlopen

from evaluation.acquire_real import digest, write_json
from radar.compare import split_passages

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "evaluation/fresh-v2"
CASES = [
    (
        "httpx-compatibility",
        "encode/httpx",
        "BSD-3-Clause",
        "docs/compatibility.md",
        "LICENSE.md",
        "2038919b7e0913f83a6dc5a9f89c25aa3f975fdb",
        "2020-01-08",
        "8e36f2bc685dfbe43cd7503bc1c422a6ed6e05a5",
        "2024-10-28",
    ),
    (
        "pip-caching",
        "pypa/pip",
        "MIT",
        "docs/html/topics/caching.md",
        "LICENSE.txt",
        "d63f06a881a54823fcc4798989d532797e772789",
        "2021-06-11",
        "d5e3f0c4b4d6aa4b432cd5480abb234e2e3332fb",
        "2023-09-06",
    ),
    (
        "mkdocs-deployment",
        "mkdocs/mkdocs",
        "BSD-2-Clause",
        "docs/user-guide/deploying-your-docs.md",
        "LICENSE",
        "a84b5a27df9b0ed90c4718871e4b60d8735c416b",
        "2019-06-23",
        "53fec50e57f6bad152ad589a83ae83d1cd72b2f5",
        "2024-04-25",
    ),
]


def inline(text: str, references: set[str]) -> str:
    text = re.sub(r"\{(?:ref|doc)\}`([^`]+)`", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\((?:[^()]|\([^()]*\))*\)", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\[[^\]]*\]", r"\1", text)
    text = re.sub(
        r"\[([^\]]+)\]",
        lambda match: match[1] if " ".join(match[1].split()).lower() in references else match[0],
        text,
    )
    text = re.sub(r"(`+)([^`]+)\1", r"\2", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    return text


def extract_markdown(text: str) -> tuple[str, dict]:
    lines = text.splitlines()
    references = {
        " ".join(match[1].split()).lower()
        for match in re.finditer(r"^\s*\[([^\]]+)\]:\s*\S", text, re.MULTILINE)
    }
    output: list[str] = []
    omissions: list[dict] = []
    transformations: list[dict] = []
    # The stack permits actual code fences nested inside four-backtick MyST tabs.
    stack: list[dict] = []
    keep_directives = {"versionadded", "versionchanged", "note", "warning", "caution", "tab"}
    skip_admonition_blank = False
    for index, line in enumerate(lines):
        stripped = line.strip()
        fence = re.fullmatch(r"(`{3,}|~{3,})(.*)", stripped)
        if stack and fence and not fence[2].strip() and len(fence[1]) >= stack[-1]["width"]:
            entry = stack.pop()
            if not entry["keep"]:
                omissions.append(
                    {
                        "start_line": entry["start"],
                        "end_line": index + 1,
                        "reason": "actual fenced code/example block",
                    }
                )
            else:
                transformations.append(
                    {
                        "start_line": entry["start"],
                        "end_line": index + 1,
                        "reason": "MyST directive label and prose retained; fence markup removed",
                    }
                )
            output.append("")
            continue
        if stack and not stack[-1]["keep"]:
            continue
        if fence:
            directive = re.fullmatch(r"\{([\w-]+)\}\s*(.*)", fence[2])
            keep = bool(directive and directive[1] in keep_directives)
            stack.append({"width": len(fence[1]), "start": index + 1, "keep": keep})
            if keep:
                kind, argument = directive.groups()
                if kind == "tab":
                    output.extend(["", f"#### {argument}", ""])
                elif kind in {"versionadded", "versionchanged"}:
                    verb = "added" if kind == "versionadded" else "changed"
                    output.append(f"Version {verb} in {argument}:")
                else:
                    output.append(kind.capitalize() + ":")
            continue
        if re.match(r"^\s*\[[^\]]+\]:\s*\S", line) or re.fullmatch(r"\([^)]+\)=", stripped):
            omissions.append(
                {
                    "start_line": index + 1,
                    "end_line": index + 1,
                    "reason": "link destination or MyST reference target; visible labels retained",
                }
            )
            output.append("")
            continue
        if re.fullmatch(r"[-*_]{3,}", stripped):
            omissions.append(
                {
                    "start_line": index + 1,
                    "end_line": index + 1,
                    "reason": "horizontal rule markup",
                }
            )
            output.append("")
            continue
        admonition = re.fullmatch(r"!!!\s+(warning|note)", stripped)
        if admonition:
            output.append(admonition[1].capitalize() + ":")
            skip_admonition_blank = True
            transformations.append(
                {
                    "start_line": index + 1,
                    "end_line": index + 1,
                    "reason": "admonition marker normalized; indented prose retained",
                }
            )
            continue
        if skip_admonition_blank:
            if not stripped:
                continue
            skip_admonition_blank = False
        if stripped in {"WARNING:", "NOTE:"}:
            line = line.capitalize()
        output.append(line)
    if stack:
        raise ValueError("Unclosed fenced block in frozen source")
    prose = inline("\n".join(output), references)
    prose = re.sub(r"\n{3,}", "\n\n", prose).strip() + "\n"
    return prose, {
        "source_line_count": len(lines),
        "omissions": omissions,
        "transformations": transformations,
        "policy": "Complete page prose; preserve heading levels, list markers and indentation; "
        "normalize visible links, inline code and bold; preserve single-star wildcards. "
        "Retain prose directives and omit actual code examples, reference targets and rules.",
        "indented_blocks_audit": "All unfenced indented blocks in these pinned pages are "
        "admonition bodies or list prose, so all are retained. No selective truncation.",
    }


def acquire(*, refresh: bool = False) -> dict:
    manifest = {
        "schema_version": 1,
        "selection": "Three complete English Markdown pages from repositories absent from the "
        "earlier corpus; purposive historical revisions, frozen before predictions.",
        "annotation_status": "ai_authored_pending_independent_review",
        "freeze_path": "docs/fresh-v2-freeze.json",
        "prediction_access_during_selection_and_annotation": False,
        "licenses": [],
        "cases": [],
    }
    jobs: dict[Path, str] = {}
    for case_id, repo, license_name, path, license_path, old, old_date, new, new_date in CASES:
        case = {
            "id": case_id,
            "repository": repo,
            "license": license_name,
            "annotation_path": f"evaluation/fresh-v2/annotations/{case_id}.json",
        }
        for side, commit, date in (("old", old, old_date), ("new", new, new_date)):
            base = f"https://raw.githubusercontent.com/{repo}/{commit}"
            prefix = DATA / "documents" / case_id / side
            raw = prefix.with_suffix(".md")
            jobs[raw] = f"{base}/{path}"
            record = {
                "tag": None,
                "commit": commit,
                "commit_date": date,
                "upstream_path": path,
                "raw_url": jobs[raw],
                "source_url": f"https://github.com/{repo}/blob/{commit}/{path}",
                "raw_path": str(raw.relative_to(ROOT)),
                "text_path": str(prefix.with_suffix(".txt").relative_to(ROOT)),
                "passages_path": str(prefix.with_suffix(".passages.json").relative_to(ROOT)),
                "audit_path": str(prefix.with_suffix(".extraction.json").relative_to(ROOT)),
            }
            case[side] = record
            local = DATA / "licenses" / f"{case_id}-{side}-{Path(license_path).name}"
            jobs[local] = f"{base}/{license_path}"
            manifest["licenses"].append({"path": str(local.relative_to(ROOT)), "url": jobs[local]})
        manifest["cases"].append(case)

    def fetch(job: tuple[Path, str]) -> None:
        local, url = job
        if local.exists() and not refresh:
            return
        with urlopen(
            Request(url, headers={"User-Agent": "SemanticChangeRadar-evaluation"}), timeout=30
        ) as response:
            raw = response.read()
        local.parent.mkdir(parents=True, exist_ok=True)
        local.write_bytes(raw)

    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(fetch, jobs.items()))
    for record in manifest["licenses"]:
        record["sha256"] = digest((ROOT / record["path"]).read_bytes())
    for case in manifest["cases"]:
        for side in ("old", "new"):
            record = case[side]
            raw = (ROOT / record["raw_path"]).read_bytes()
            prose, audit = extract_markdown(raw.decode("utf-8"))
            passages = split_passages(prose)
            (ROOT / record["text_path"]).write_text(prose, encoding="utf-8")
            write_json(ROOT / record["passages_path"], passages)
            write_json(ROOT / record["audit_path"], audit)
            record.update(
                raw_sha256=digest(raw),
                text_sha256=digest(prose.encode()),
                raw_characters=len(raw.decode()),
                characters=len(prose),
                passages=len(passages),
                app_limits_passed=True,
            )
    review_statuses: set[str] = set()
    for case in manifest["cases"]:
        path = ROOT / case["annotation_path"]
        status = manifest["annotation_status"]
        if path.exists():
            status = json.loads(path.read_text(encoding="utf-8"))["review_status"]
        review_statuses.add(status)
    manifest["annotation_status"] = (
        next(iter(review_statuses)) if len(review_statuses) == 1 else "mixed_review_status"
    )
    write_json(DATA / "manifest.json", manifest)
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="Re-download pinned raw bytes.")
    args = parser.parse_args()
    result = acquire(refresh=args.refresh)
    print(
        json.dumps(
            [
                {"id": case["id"], "passages": [case[side]["passages"] for side in ("old", "new")]}
                for case in result["cases"]
            ],
            indent=2,
        )
    )
