"""Bounded split/merge refinement around a global singleton assignment."""

from __future__ import annotations

import re
from typing import Callable

import numpy as np

GROUP_MARGIN = 0.04


def refine_groups(
    old: list[str],
    new: list[str],
    old_contexts: list[dict],
    new_contexts: list[dict],
    old_remaining: list[int],
    new_remaining: list[int],
    matches: list[tuple[tuple[int, ...], tuple[int, ...], float]],
    body_scores: np.ndarray,
    vectors: tuple[np.ndarray, np.ndarray] | None,
    models,
    threshold: float,
    lexical: Callable[[str, str], float],
    contextual: Callable[[float, dict, dict], float],
) -> tuple[list[tuple[tuple[int, ...], tuple[int, ...], float]], int]:
    """Only absorb currently unmatched neighbors; never steal another match.

    Both fragments need distinct lexical support and a plausible body match.
    A merged score must improve on the strongest constituent by a fixed margin.
    This deliberately handles adjacent 1:2 / 2:1, not arbitrary document graphs.
    """
    old_rows = {i: row for row, i in enumerate(old_remaining)}
    new_rows = {j: row for row, j in enumerate(new_remaining)}
    if len(matches) == len(old_remaining) == len(new_remaining):
        return matches, 0  # No unmatched fragment can be absorbed by this refinement.
    skipped = 0

    def adjacent(indices: list[int], contexts: list[dict]) -> list[tuple[int, int]]:
        allowed = set(indices)
        return [
            (i, i + 1)
            for i in indices
            if i + 1 in allowed
            and contexts[i]["kind"] != "heading"
            and contexts[i + 1]["kind"] != "heading"
            and contexts[i]["section"] == contexts[i + 1]["section"]
            and contexts[i]["scope_indices"] == contexts[i + 1]["scope_indices"]
        ]

    groups = [adjacent(old_remaining, old_contexts), adjacent(new_remaining, new_contexts)]
    texts = [{g: "\n\n".join(doc[i] for i in g) for g in gs} for doc, gs in zip((old, new), groups)]
    group_vectors: list[dict] = [{}, {}]
    if models:
        for side in (0, 1):
            usable = [g for g in groups[side] if models.fits_embedding(texts[side][g])]
            skipped += len(groups[side]) - len(usable)
            groups[side] = usable
            if usable:
                group_vectors[side] = dict(
                    zip(usable, models.encode([texts[side][g] for g in usable]))
                )

    stop = {"the", "a", "an", "of", "to", "in", "and", "or", "is", "are", "it", "this", "that"}

    def words(text: str) -> set[str]:
        return set(re.findall(r"\w+", text.casefold())) - stop

    def supported(single: str, first: str, second: str) -> bool:
        target, left, right = words(single), words(first), words(second)
        return bool((left - right) & target) and bool((right - left) & target)

    candidates = []
    for side, singles in ((1, old_remaining), (0, new_remaining)):
        for group in groups[side]:
            for single in singles:
                a, b = ((single,), group) if side == 1 else (group, (single,))
                old_text = old[single] if side == 1 else texts[0][group]
                new_text = texts[1][group] if side == 1 else new[single]
                if (
                    old_contexts[a[0]]["kind"] == "heading"
                    or new_contexts[b[0]]["kind"] == "heading"
                ):
                    continue
                members = [body_scores[old_rows[i], new_rows[j]] for i in a for j in b]
                # Exact concatenations include pure paragraph formatting changes.
                exact = " ".join(old_text.split()) == " ".join(new_text.split())
                fragments = [new[i] for i in group] if side == 1 else [old[i] for i in group]
                if not exact and (
                    min(members) < threshold - 0.10
                    or not supported(old_text if side == 1 else new_text, *fragments)
                ):
                    continue
                score = lexical(old_text, new_text)
                if models:
                    if not models.fits_nli(old_text, new_text) or not models.fits_nli(
                        new_text, old_text
                    ):
                        skipped += 1
                        continue
                    left = vectors[0][old_rows[single]] if side == 1 else group_vectors[0][group]
                    right = group_vectors[1][group] if side == 1 else vectors[1][new_rows[single]]
                    score = 0.85 * float(np.clip(left @ right, 0, 1)) + 0.15 * score
                if exact:
                    score = 1.0
                score = contextual(score, old_contexts[a[0]], new_contexts[b[0]])
                strongest = max(
                    contextual(
                        body_scores[old_rows[i], new_rows[j]], old_contexts[i], new_contexts[j]
                    )
                    for i in a
                    for j in b
                )
                if score > threshold and (exact or score >= strongest + GROUP_MARGIN):
                    candidates.append((score - strongest, score, a, b, exact))

    for _, score, a, b, exact in sorted(candidates, key=lambda c: (-c[0], -c[1], c[2], c[3])):
        conflicts = [m for m in matches if set(m[0]) & set(a) or set(m[1]) & set(b)]
        # At most one singleton partner is displaced. All extra fragments must
        # still be unmatched; consuming a part of another group is forbidden.
        if len(conflicts) > 1 or any(
            not set(m[0]) <= set(a) or not set(m[1]) <= set(b) or len(m[0]) != 1 or len(m[1]) != 1
            for m in conflicts
        ):
            continue
        if conflicts and not exact and score < conflicts[0][2] + GROUP_MARGIN:
            continue
        matches = [m for m in matches if m not in conflicts] + [(a, b, score)]
    return matches, skipped
