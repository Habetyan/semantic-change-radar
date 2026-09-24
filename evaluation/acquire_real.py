"""Acquire pinned RST pages and extract prose with a source-line audit.

This deliberately limited extractor supports the constructs in this corpus. It
is not a general RST renderer. All raw bytes are retained for manual inspection.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "evaluation/real"
REPOS = {
    "flask": {
        "repository": "pallets/flask",
        "license": "BSD-3-Clause",
        "old": ("1.1.4", "1ca199f9b38b70a4e97cb47a4252ffd7fccc008c", "LICENSE.rst"),
        "new": ("3.1.0", "ab8149664182b662453a563161aa89013c806dc9", "LICENSE.txt"),
    },
    "pytest": {
        "repository": "pytest-dev/pytest",
        "license": "MIT",
        "old": ("6.2.5", "1569fac603d9a50022e1474b494eebf970a2a3af", "LICENSE"),
        "new": ("8.3.5", "b55ab2aabb68c0ce94c3903139b062d0c2790152", "LICENSE"),
    },
    "requests": {
        "repository": "psf/requests",
        "license": "Apache-2.0",
        "old": ("v2.25.1", "c2b307dbefe21177af03f9feb37181a89a799fcc", "LICENSE"),
        "new": ("v2.32.3", "0e322af87745eff34caffe4df68456ebc20d9068", "LICENSE"),
    },
}
CASES = [
    ("flask-deploying", "flask", "docs/deploying/index.rst", "docs/deploying/index.rst"),
    ("flask-design", "flask", "docs/design.rst", "docs/design.rst"),
    ("flask-security", "flask", "docs/security.rst", "docs/web-security.rst"),
    ("pytest-flaky", "pytest", "doc/en/flaky.rst", "doc/en/explanation/flaky.rst"),
    (
        "pytest-goodpractices",
        "pytest",
        "doc/en/goodpractices.rst",
        "doc/en/explanation/goodpractices.rst",
    ),
    ("pytest-pythonpath", "pytest", "doc/en/pythonpath.rst", "doc/en/explanation/pythonpath.rst"),
    ("requests-faq", "requests", "docs/community/faq.rst", "docs/community/faq.rst"),
    ("requests-advanced", "requests", "docs/user/advanced.rst", "docs/user/advanced.rst"),
]


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def inline(text: str) -> str:
    # Keep visible link/role text, excluding destinations and RST syntax.
    def role(match: re.Match) -> str:
        target = match[1]
        if target.startswith("~") and "<" not in target:
            target = target.rsplit(".", 1)[-1]
        return "`" + target.lstrip(".") + "`"

    text = re.sub(r":(?:[\w-]+:)*[\w-]+:`([^`]+)`", role, text)
    text = re.sub(r"`([^`<>]+)\s*<[^`>]+>`_?", lambda m: m[1].strip(), text)
    text = re.sub(r"``([^`]+)``", r"\1", text)
    text = re.sub(r"`([^`]+)`_?", r"\1", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    # Single stars can be bullets, emphasis, or literal wildcards. Keep them.
    return text


def extract_rst(text: str) -> tuple[str, dict]:
    lines = text.splitlines()
    output: list[str] = []
    omitted: list[dict] = []
    i = 0

    def indent(line: str) -> int:
        return len(line) - len(line.lstrip())

    def block_end(start: int, base: int) -> int:
        end = start
        while end < len(lines) and (not lines[end].strip() or indent(lines[end]) > base):
            end += 1
        return end

    def omit(start: int, end: int, reason: str) -> None:
        omitted.append({"start_line": start + 1, "end_line": end, "reason": reason})

    while i < len(lines):
        line, stripped = lines[i], lines[i].strip()
        base = indent(line)
        if stripped.startswith(".. _"):
            end = block_end(i + 1, base)
            omit(i, end, "reference target")
            i = end
            output.append("")
            continue
        directive = re.match(r"\.\. ([\w-]+)::\s*(.*)", stripped)
        if directive:
            kind, argument = directive.groups()
            if kind in {"note", "warning", "admonition", "seealso", "important", "tip"}:
                output.extend(["", argument])
                omit(i, i + 1, "admonition markup only; inline argument and body retained")
                i += 1
                continue
            end = block_end(i + 1, base)
            omit(i, end, f"{kind} directive and body")
            i = end
            output.append("")
            continue
        if stripped.startswith(".."):
            end = block_end(i + 1, base)
            omit(i, end, "RST comment")
            i = end
            continue
        if (
            stripped
            and i + 1 < len(lines)
            and re.fullmatch(r"[=~^\-`:#*+]{3,}", lines[i + 1].strip())
        ):
            output.extend(["", "# " + stripped, ""])
            omit(i + 1, i + 2, "heading underline; heading retained")
            i += 2
            continue
        if stripped.endswith("::"):
            if stripped != "::":
                output.append(line[:-3] if line.endswith(" ::") else line[:-1])
            end = block_end(i + 1, base)
            omit(i + 1, end, "literal/code block")
            output.append("")
            i = end
            continue
        if stripped.startswith(">>>"):
            end = i + 1
            while end < len(lines) and lines[end].strip():
                end += 1
            omit(i, end, "doctest/code block")
            i = end
            output.append("")
            continue
        output.append(line)
        i += 1

    # Resolve multiline inline roles/links before stripping markup. Preserve
    # paragraphs and list boundaries, matching the app's passage segmentation.
    passages: list[str] = []
    pending: list[str] = []

    def flush() -> None:
        if pending:
            passages.append(inline(" ".join(pending)))
            pending.clear()

    for line in output:
        stripped = line.strip()
        if not stripped:
            flush()
        elif re.match(r"^(?:#{1,6}\s|[-*+]\s|\d+[.)]\s)", stripped):
            flush()
            pending.append(stripped)
            if stripped.startswith("#"):
                flush()
        else:
            pending.append(stripped)
    flush()
    prose = "\n\n".join(passages) + "\n"
    return prose, {"source_line_count": len(lines), "omissions": omitted, "passages": passages}


def acquire(*, refresh: bool = False) -> dict:
    jobs: dict[Path, str] = {}
    manifest: dict = {
        "schema_version": 1,
        "selection": "Purposive historical multi-release prose revisions; not a random sample.",
        "annotation_status": "AI-authored, pending human validation; no training or tuning.",
        "freeze_path": "docs/real-evaluation-freeze.json",
        "licenses": [],
        "cases": [],
    }
    for name, repo in REPOS.items():
        for side in ("old", "new"):
            tag, commit, filename = repo[side]
            for resource in [filename, "NOTICE"] if name == "requests" else [filename]:
                local = DATA / "licenses" / f"{name}-{side}-{Path(resource).name}"
                url = f"https://raw.githubusercontent.com/{repo['repository']}/{commit}/{resource}"
                jobs[local] = url
                manifest["licenses"].append({"path": str(local.relative_to(ROOT)), "url": url})
    for case_id, name, old_path, new_path in CASES:
        repo = REPOS[name]
        case = {
            "id": case_id,
            "repository": repo["repository"],
            "license": repo["license"],
            "annotation_path": (
                None
                if case_id == "requests-advanced"
                else f"evaluation/real/annotations/{case_id}.json"
            ),
        }
        for side, path in (("old", old_path), ("new", new_path)):
            tag, commit, _ = repo[side]
            prefix = DATA / "documents" / case_id / side
            raw = prefix.with_suffix(".rst")
            url = f"https://raw.githubusercontent.com/{repo['repository']}/{commit}/{path}"
            jobs[raw] = url
            case[side] = {
                "tag": tag,
                "commit": commit,
                "upstream_path": path,
                "raw_url": url,
                "source_url": f"https://github.com/{repo['repository']}/blob/{commit}/{path}",
                "raw_path": str(raw.relative_to(ROOT)),
                "text_path": str(prefix.with_suffix(".txt").relative_to(ROOT)),
                "passages_path": str(prefix.with_suffix(".passages.json").relative_to(ROOT)),
                "audit_path": str(prefix.with_suffix(".extraction.json").relative_to(ROOT)),
            }
        manifest["cases"].append(case)

    def fetch(job: tuple[Path, str]) -> None:
        local, url = job
        if local.exists() and not refresh:
            return
        with urlopen(
            Request(url, headers={"User-Agent": "SemanticChangeRadar-evaluation"}), timeout=30
        ) as response:
            data = response.read()
        local.parent.mkdir(parents=True, exist_ok=True)
        local.write_bytes(data)

    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(fetch, jobs.items()))
    for license_file in manifest["licenses"]:
        license_file["sha256"] = digest((ROOT / license_file["path"]).read_bytes())
    for case in manifest["cases"]:
        for side in ("old", "new"):
            record = case[side]
            raw = (ROOT / record["raw_path"]).read_bytes()
            prose, audit = extract_rst(raw.decode("utf-8"))
            passages = audit.pop("passages")
            (ROOT / record["text_path"]).write_text(prose, encoding="utf-8")
            write_json(ROOT / record["passages_path"], passages)
            write_json(ROOT / record["audit_path"], audit)
            record.update(
                raw_sha256=digest(raw),
                text_sha256=digest(prose.encode()),
                characters=len(prose),
                passages=len(passages),
            )
    write_json(DATA / "manifest.json", manifest)
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="Re-download pinned raw files.")
    args = parser.parse_args()
    result = acquire(refresh=args.refresh)
    print(
        json.dumps(
            {
                "acquired_at": datetime.now(timezone.utc).isoformat(),
                "cases": [
                    {"id": c["id"], "passages": [c[s]["passages"] for s in ("old", "new")]}
                    for c in result["cases"]
                ],
            },
            indent=2,
        )
    )
