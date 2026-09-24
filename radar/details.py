"""Review localized changed clauses before certifying paragraph equivalence."""

from __future__ import annotations

import re
from difflib import SequenceMatcher


def changed_units(old: str, new: str) -> list[tuple[str, str]]:
    """Use source quotes, retaining condition phrases rather than isolated edits."""
    condition = re.compile(
        r"\b(?:if|unless|provided that|as long as|only when)\b.*?"
        r"(?=,\s|\byou (?:can|may|must|should)\b|\bthen\b|[;]|$)",
        re.I,
    )
    result = []
    before, after = condition.search(old), condition.search(new)
    if before and after and before[0].casefold().split() != after[0].casefold().split():
        result.append((before[0].strip(), after[0].strip()))

    def clauses(text: str) -> list[tuple[int, int]]:
        # Store source spans so a run of edited clauses retains its separators.
        separators = re.finditer(r"[,;]\s+|(?<=[.!?])\s+(?=[A-Z])", text)
        boundaries = [(match.start(), match.end()) for match in separators]
        spans, start = [], 0
        for end, following in boundaries + [(len(text), len(text))]:
            while start < end and text[start].isspace():
                start += 1
            while end > start and text[end - 1].isspace():
                end -= 1
            if start < end:
                spans.append((start, end))
            start = following
        return spans

    left, right = clauses(old), clauses(new)
    if len(left) == len(right) == 1:
        return result  # The existing NLI check already sees this entire sentence.
    for operation, a, b, c, d in SequenceMatcher(
        None, [old[a:b] for a, b in left], [new[a:b] for a, b in right], autojunk=False
    ).get_opcodes():
        if operation == "equal":
            continue
        before = old[left[a][0] : left[b - 1][1]] if a < b else ""
        after = new[right[c][0] : right[d - 1][1]] if c < d else ""
        if re.search(r"\w", before + after) and (before, after) not in result:
            result.append((before, after))
    return result


def verify_details(change: dict, models) -> None:
    """Only downgrade a questionable equivalence to review, never invent a fact."""
    if change["status"] != "reworded" or change["category"] == "Equivalent units":
        return
    checks = changed_units(change["old_text"], change["new_text"])
    if not checks:
        return
    evidence, pairs = [], []
    for before, after in checks:
        if not before or not after:
            evidence.append(
                {
                    "old_quote": before,
                    "new_quote": after,
                    "reason": "A source clause was added or removed; paragraph similarity "
                    "does not establish that this detail is preserved.",
                    "old_entails_new": None,
                    "new_entails_old": None,
                }
            )
            continue
        left_context = "\n".join(change.get("old_context", []))
        right_context = "\n".join(change.get("new_context", []))
        left, right = (
            "\n".join(filter(None, [left_context, before])),
            "\n".join(filter(None, [right_context, after])),
        )
        if not models.fits_nli(left, right) or not models.fits_nli(right, left):
            evidence.append(
                {
                    "old_quote": before,
                    "new_quote": after,
                    "reason": "The detail and its source context exceed the verification "
                    "budget; equivalence remains unresolved.",
                    "old_entails_new": None,
                    "new_entails_old": None,
                }
            )
        else:
            pairs.append((before, after, left, right))
    if pairs:
        results = models.predict_nli(
            [(a, b) for _, _, a, b in pairs] + [(b, a) for _, _, a, b in pairs]
        )
        for k, (before, after, _, _) in enumerate(pairs):
            f, r = results[k]["entailment"], results[k + len(pairs)]["entailment"]
            if min(f, r) < 0.78:
                evidence.append(
                    {
                        "old_quote": before,
                        "new_quote": after,
                        "reason": "The changed clause is not mutually entailed even though "
                        "the full passages appeared equivalent.",
                        "old_entails_new": round(f, 4),
                        "new_entails_old": round(r, 4),
                    }
                )
    if evidence:
        change.update(
            status="uncertain",
            category="Changed detail needs review",
            explanation="Paragraph-level equivalence did not resolve the highlighted "
            "detail. Review its meaning in the source context.",
            localization_evidence=evidence,
        )
