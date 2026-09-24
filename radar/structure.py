"""Passage segmentation with explicit heading and list ownership."""

from __future__ import annotations

import re

_HEADING = re.compile(r"^(#{1,6})\s+")
_LIST = re.compile(r"^(?:[-*+]\s|\d+[.)]\s)")


def parse_document(text: str) -> tuple[list[str], list[dict]]:
    """Keep source passage boundaries while recording their structural context.

    Only explicit colon introductions establish prose scope. Indentation owns
    nested list items and continuation paragraphs; an ordinary previous
    paragraph never becomes context merely because it is nearby.
    """
    passages: list[str] = []
    contexts: list[dict] = []
    pending: list[str] = []
    start = end = indentation = 0

    def flush() -> None:
        if pending:
            passage = " ".join(pending)
            passages.append(passage)
            contexts.append(
                {
                    "headings": [],
                    "scope": [],
                    "section": [],
                    "scope_indices": [],
                    "kind": "heading"
                    if _HEADING.match(passage)
                    else ("list" if _LIST.match(passage) else "paragraph"),
                    "line_start": start,
                    "line_end": end,
                    "indent": indentation,
                }
            )
            pending.clear()

    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line:
            flush()
            continue
        if _HEADING.match(line) or _LIST.match(line):
            flush()
        if not pending:
            start = number
            expanded = raw.expandtabs(4)
            indentation = len(expanded) - len(expanded.lstrip())
        end = number
        pending.append(line)
        if _HEADING.match(line):
            flush()
    flush()

    headings: list[tuple[int, int]] = []
    owners: list[tuple[int, int]] = []
    introductions: list[tuple[int, int]] = []
    for index, (passage, context) in enumerate(zip(passages, contexts)):
        indent, kind = context["indent"], context["kind"]
        if kind == "heading":
            level = len(_HEADING.match(passage)[1])
            while headings and headings[-1][0] >= level:
                headings.pop()
            owners.clear()
            introductions.clear()
        else:
            while owners and owners[-1][0] >= indent:
                owners.pop()
            while introductions and (
                introductions[-1][0] > indent
                or (kind == "paragraph" and introductions[-1][0] == indent)
            ):
                introductions.pop()
        context["section"] = [i for _, i in headings]
        context["headings"] = [_HEADING.sub("", passages[i]) for _, i in headings]
        scope = sorted({i for _, i in introductions + owners})
        context["scope_indices"] = scope
        context["scope"] = [passages[i] for i in scope]
        if kind == "heading":
            headings.append((level, index))
        elif kind == "list":
            owners.append((indent, index))
        elif passage.endswith(":"):
            introductions.append((indent, index))
    return passages, contexts
