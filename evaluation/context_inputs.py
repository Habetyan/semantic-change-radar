"""Recover context from frozen RST without changing historical passage text.

Run ``python -m evaluation.context_inputs`` to create the versioned manifest.
This deliberately reuses the corpus extractor's omission audit, not a general
RST parser. Every source passage must exactly reproduce its frozen counterpart.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from evaluation.acquire_real import ROOT, digest, extract_rst, inline, write_json
from radar.structure import parse_document


def rst_contexts(source: str, expected: list[str]) -> list[dict]:
    """Return contexts aligned exactly to the original extractor's passages."""
    _, audit = extract_rst(source)
    if audit["passages"] != expected:
        raise ValueError("Frozen passages disagree with the original RST extraction.")
    lines = source.splitlines()
    omissions = {item["start_line"]: item for item in audit["omissions"]}
    heading_lines: dict[int, int] = {}
    styles: list[str] = []
    for item in audit["omissions"]:
        if item["reason"] == "heading underline; heading retained":
            style = lines[item["start_line"] - 1].strip()[0]
            if style not in styles:
                styles.append(style)
            heading_lines[item["start_line"] - 1] = styles.index(style) + 1
    rendered: list[str] = []
    source_lines: list[int] = []

    def emit(text: str, number: int) -> None:
        rendered.append(text)
        source_lines.append(number)

    number = 1
    while number <= len(lines):
        line = lines[number - 1]
        omission = omissions.get(number)
        if omission:
            reason = omission["reason"]
            if reason.startswith("admonition markup"):
                emit("", number)
                argument = re.match(r"\s*\.\. [\w-]+::\s*(.*)", line)[1]
                emit(argument, number)
            elif reason != "RST comment":
                emit("", number)
            number = omission["end_line"] + 1
            continue
        if number in heading_lines:
            emit("", number)
            emit("#" * heading_lines[number] + " " + line.strip(), number)
            emit("", number)
        elif line.strip().endswith("::"):
            if line.strip() != "::":
                emit(line[:-3] if line.endswith(" ::") else line[:-1], number)
        else:
            emit(line, number)
        number += 1
    passages, contexts = parse_document("\n".join(rendered))
    recovered = [re.sub(r"^#{1,6}\s+", "# ", inline(p)) for p in passages]
    if recovered != expected:
        raise ValueError("Context reconstruction changed frozen passage text or order.")
    for context in contexts:
        context["line_start"] = source_lines[context["line_start"] - 1]
        context["line_end"] = source_lines[context["line_end"] - 1]
        context["headings"] = [inline(text) for text in context["headings"]]
        context["scope"] = [expected[i] for i in context["scope_indices"]]
    return contexts


def build_context_inputs(root: Path = ROOT) -> dict:
    """Write only new sidecars and a manifest referring to frozen source files."""
    original = root / "evaluation/real/manifest.json"
    manifest = json.loads(original.read_text(encoding="utf-8"))
    manifest.update(
        schema_version=2,
        context_version=2,
        freeze_path="docs/improvement-freeze.json",
        source_manifest="evaluation/real/manifest.json",
        source_manifest_sha256=digest(original.read_bytes()),
    )
    outputs: list[tuple[Path, list[dict]]] = []
    for case in manifest["cases"]:
        for side in ("old", "new"):
            record = case[side]
            raw = (root / record["raw_path"]).read_bytes()
            if digest(raw) != record["raw_sha256"]:
                raise ValueError(f"Frozen raw source hash changed: {case['id']} {side}")
            passages = json.loads((root / record["passages_path"]).read_text(encoding="utf-8"))
            contexts = rst_contexts(raw.decode("utf-8"), passages)
            path = Path("evaluation/context-v2/documents") / case["id"] / f"{side}.contexts.json"
            record["contexts_path"] = str(path)
            outputs.append((root / path, contexts))
    # Validate every document before producing any versioned output.
    for path, contexts in outputs:
        write_json(path, contexts)
    write_json(root / "evaluation/context-v2/manifest.json", manifest)
    return manifest


if __name__ == "__main__":
    build_context_inputs()
