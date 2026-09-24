"""Passage alignment and conservative, source-grounded change classification."""

from __future__ import annotations

import re
import time
import unicodedata
from collections import Counter, defaultdict, deque
from decimal import Decimal
from difflib import SequenceMatcher
from typing import Any

import numpy as np
from scipy.optimize import linear_sum_assignment

from radar.structure import parse_document

MAX_CHARACTERS = 30_000
MAX_PASSAGES = 80
ALIGNMENT_THRESHOLDS = {"lexical": 0.38, "semantic": 0.55}
EQUIVALENCE_THRESHOLD = 0.78
CONTRADICTION_THRESHOLD = 0.65
PROFILES = {"baseline", "context", "groups", "verified"}

# Exact conversions only. Months/years, currencies, temperatures, and ambiguous
# abbreviations such as "m" deliberately require review.
_UNIT_FACTORS = {
    "seconds": ("seconds", 1),
    "second": ("seconds", 1),
    "sec": ("seconds", 1),
    "minutes": ("seconds", 60),
    "minute": ("seconds", 60),
    "min": ("seconds", 60),
    "hours": ("seconds", 3600),
    "hour": ("seconds", 3600),
    "hr": ("seconds", 3600),
    "days": ("seconds", 86400),
    "day": ("seconds", 86400),
    "weeks": ("seconds", 604800),
    "week": ("seconds", 604800),
    "B": ("bytes", 1),
    "kB": ("bytes", 1000),
    "MB": ("bytes", 1000**2),
    "GB": ("bytes", 1000**3),
    "KiB": ("bytes", 1024),
    "MiB": ("bytes", 1024**2),
    "GiB": ("bytes", 1024**3),
}
_MEASUREMENT = re.compile(
    r"(?<![\w.,])([+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)\s*(" + "|".join(_UNIT_FACTORS) + r")\b"
)


def _canonical_measurements(text: str) -> str:
    def convert(match: re.Match) -> str:
        dimension, factor = _UNIT_FACTORS[match[2]]
        value = Decimal(match[1].replace(",", "")) * factor
        return f"<{value.normalize():f} {dimension}>"

    return _MEASUREMENT.sub(convert, _content(text))


def _normalize(text: str) -> str:
    return " ".join(unicodedata.normalize("NFC", text).split())


def split_passages(text: str) -> list[str]:
    """Split paragraphs and list items; preserve sentences and soft-wrapped lines.

    A blank line, Markdown heading, or list item starts a new passage. Sentence
    splitting would break decimals and detach exceptions from their conditions.
    """
    if not isinstance(text, str):
        raise ValueError("Documents must be text strings.")
    if len(text) > MAX_CHARACTERS:
        raise ValueError(f"Each document must be at most {MAX_CHARACTERS:,} characters.")
    passages, _ = parse_document(text)
    if len(passages) > MAX_PASSAGES:
        raise ValueError(f"Each document must contain at most {MAX_PASSAGES} passages.")
    return passages


def _content(text: str) -> str:
    # Ignore list numbering/Markdown markers for matching, but retain source text.
    return re.sub(r"^(?:#{1,6}\s+|[-*+]\s+(?!\d)|\d+[.)]\s+)", "", _normalize(text))


def _tokens(text: str) -> list[str]:
    return re.findall(r"\w+(?:['’]\w+)?", _content(text).casefold())


def _lexical_similarity(left: str, right: str) -> float:
    a, b = Counter(_tokens(left)), Counter(_tokens(right))
    if not a or not b:
        return float(_normalize(left) == _normalize(right))
    dot = sum(value * b[word] for word, value in a.items())
    cosine = dot / (sum(v * v for v in a.values()) * sum(v * v for v in b.values())) ** 0.5
    order = SequenceMatcher(None, _tokens(left), _tokens(right), autojunk=False).ratio()
    return 0.75 * cosine + 0.25 * order


def _numbers(text: str) -> tuple[str, ...]:
    # This remains conservative outside the small supported unit vocabulary.
    return tuple(
        number.replace(",", "").replace(" ", "")
        for number in re.findall(r"(?<!\w)[+-]?\s*\d+(?:[.,]\d+)*(?:%)?", _content(text))
    )


def _signals(old: str, new: str) -> tuple[list[str], str]:
    """Return observable text changes, never a generated explanation of intent."""
    quantities_changed = Counter(_MEASUREMENT.findall(old)) != Counter(_MEASUREMENT.findall(new))
    old, new = _content(old).casefold(), _content(new).casefold()
    signals: list[str] = []
    category = "Content change"
    if _numbers(old) != _numbers(new):
        signals.append("Numeric values or their order changed; check quantities, dates, and units.")
        category = "Quantity or date change"
    elif quantities_changed:
        signals.append("Measurement values or units differ.")
        category = "Quantity or date change"
    negation = r"\b(?:not|no|never|cannot|can't|mustn't|without|prohibited|forbidden)\b"
    if bool(re.search(negation, old)) != bool(re.search(negation, new)):
        signals.append("Negation or exclusion wording changed.")
        if category == "Content change":
            category = "Negation change"
    conditions = r"\b(?:only|unless|except|provided that|as long as|whichever|if|until)\b"
    if Counter(re.findall(conditions, old)) != Counter(re.findall(conditions, new)):
        signals.append("A condition, exception, or restriction marker changed.")
        if category == "Content change":
            category = "Condition change"
    obligation = r"\b(?:must|shall|required|mandatory|need to|needs to|has to)\b"
    if bool(re.search(obligation, old)) != bool(re.search(obligation, new)):
        signals.append("Requirement wording changed.")
        if category == "Content change":
            category = "Requirement change"
    roles = r"\b(?:guests?|admins?|administrators?|owners?|members?|visitors?)\b"
    if Counter(re.findall(roles, old)) != Counter(re.findall(roles, new)):
        if re.search(r"\b(?:can|may|allow\w*|permit\w*|access|only)\b", old + " " + new):
            signals.append("Actors in access or permission wording changed.")
            if category in {"Content change", "Condition change"}:
                category = "Permission change"
    # Equal word bags can hide swapped actions, actors, and conditions.
    old_tokens, new_tokens = _tokens(old), _tokens(new)
    if old_tokens != new_tokens and Counter(old_tokens) == Counter(new_tokens):

        def clauses(text: str) -> list[tuple]:
            return sorted(
                tuple(sorted(_tokens(part)))
                for part in re.split(r"\b(?:and|but|while|whereas)\b|;", text)
            )

        def first_content(tokens: list[str]) -> str:
            return next(
                (t for t in tokens if t not in {"the", "a", "an"} and not t.endswith("ly")), ""
            )

        if clauses(old) != clauses(new) or first_content(old_tokens) != first_content(new_tokens):
            signals.append("The same words have different clause or actor assignments.")
            if category == "Content change":
                category = "Actor or scope change"
    return signals, category


def _assign(scores: np.ndarray, threshold: float) -> list[tuple[int, int]]:
    """Global one-to-one matching with explicit zero-benefit unmatched slots."""
    n, m = scores.shape
    if not n or not m:
        return []
    benefits = np.zeros((n + m, n + m))
    benefits[:n, :m] = scores - threshold
    # Stable positional tie-breaking only; it cannot rescue a below-threshold pair.
    for i in range(n):
        for j in range(m):
            benefits[i, j] -= abs(i - j) * 1e-8
    rows, cols = linear_sum_assignment(benefits, maximize=True)
    return [
        (int(i), int(j)) for i, j in zip(rows, cols) if i < n and j < m and scores[i, j] > threshold
    ]


def _base_change(old: list[str], new: list[str], left: tuple, right: tuple) -> dict:
    return {
        "old_index": left[0] if left else None,
        "new_index": right[0] if right else None,
        "old_indices": list(left),
        "new_indices": list(right),
        "old_text": "\n\n".join(old[i] for i in left),
        "new_text": "\n\n".join(new[j] for j in right),
        "old_parts": [{"index": i, "text": old[i]} for i in left],
        "new_parts": [{"index": j, "text": new[j]} for j in right],
        "moved": False,
        "alignment_score": None,
        "old_entails_new": None,
        "new_entails_old": None,
        "contradiction_score": None,
        "signals": [],
    }


def _classify(change: dict, forward: dict | None, reverse: dict | None) -> None:
    signals, category = _signals(change["old_text"], change["new_text"])
    change["signals"] = signals
    if forward is None or reverse is None:
        change.update(
            status="modified",
            category=category if signals else "Text edit",
            explanation="The lexical baseline flags every non-identical passage as an edit. "
            "It cannot establish whether meaning is preserved.",
        )
        return
    f, r = forward["entailment"], reverse["entailment"]
    contradiction = max(forward["contradiction"], reverse["contradiction"])
    change.update(
        old_entails_new=round(f, 4),
        new_entails_old=round(r, 4),
        contradiction_score=round(contradiction, 4),
    )
    if not change.get("context_changed") and _canonical_measurements(
        change["old_text"]
    ) == _canonical_measurements(change["new_text"]):
        change.update(
            status="reworded",
            category="Equivalent units",
            signals=[],
            explanation="Only numeric formatting or exactly convertible duration/storage "
            "units changed; the remaining text is identical.",
        )
    elif signals:
        change.update(
            status="modified",
            category=category,
            explanation="Explicit wording signals indicate a potentially material edit. "
            "Check the highlighted source passages; these signals can produce false alarms.",
        )
    elif min(f, r) >= EQUIVALENCE_THRESHOLD:
        change.update(
            status="reworded",
            category="Wording only",
            explanation="Both passages imply one another according to the NLI model. "
            "This suggests equivalent wording, not a guarantee of equivalence.",
        )
    elif contradiction >= CONTRADICTION_THRESHOLD:
        change.update(
            status="modified",
            category="Contradiction",
            explanation="The NLI model detects a conflict between the aligned statements.",
        )
    elif max(f, r) >= 0.72 and min(f, r) <= 0.35:
        change.update(
            status="modified",
            category="Scope change",
            explanation="The model finds implication in one direction but not the other. "
            "Information may have been added, removed, or qualified.",
        )
    else:
        change.update(
            status="uncertain",
            category="Needs review",
            explanation="The model cannot confidently distinguish a meaning change from "
            "a paraphrase. Review both passages.",
        )


def _scope(context: dict) -> list[str]:
    headings = [" > ".join(context["headings"])] if context["headings"] else []
    return headings + context["scope"]


def _context_key(context: dict) -> tuple[str, ...]:
    return tuple(_content(part).casefold() for part in _scope(context))


def _scope_review(old: dict, new: dict) -> dict:
    """Identify changed physical owners, retaining source-side passage indices."""
    before = old["headings"] + old["scope"]
    after = new["headings"] + new["scope"]
    old_ids = old["section"] + old["scope_indices"]
    new_ids = new["section"] + new["scope_indices"]
    left, right = [], []
    for operation, a, b, c, d in SequenceMatcher(
        None,
        [_content(x).casefold() for x in before],
        [_content(x).casefold() for x in after],
        autojunk=False,
    ).get_opcodes():
        if operation != "equal":
            left.extend(old_ids[a:b])
            right.extend(new_ids[c:d])
    return {
        "old_owner_indices": left,
        "new_owner_indices": right,
        "reason": "The body text is unchanged, but its governing source context requires review.",
    }


def _scope_signals(before: list[str], after: list[str]) -> list[str]:
    signals, _ = _signals("\n".join(before), "\n".join(after))
    # Short access headings often omit the permission verb present in prose.
    access = r"\b(?:guests?|admins?|administrators?|owners?|members?|visitors?|allowed|forbidden|permitted|denied|free|paid)\b"
    if Counter(re.findall(access, " ".join(before).casefold())) != Counter(
        re.findall(access, " ".join(after).casefold())
    ):
        signals.append("Actors or access labels in source scope changed.")
    return signals


def _context_score(score: float, old: dict, new: dict) -> float:
    """Soft scope evidence preserves moved sections and rewritten headings."""
    a, b = _scope(old), _scope(new)
    if not a or not b:
        return float(score)
    if _context_key(old) == _context_key(new):
        return float(score)
    context_similarity = _lexical_similarity(a[-1], b[-1])
    if old["scope"] and new["scope"]:
        # Named list entries such as 'prepend:' and 'importlib:' share much of
        # their explanatory wording. Their short labels distinguish ownership.
        labels = [_content(c["scope"][-1]).split(":", 1) for c in (old, new)]
        if all(len(parts) == 2 and len(parts[0].split()) <= 8 for parts in labels):
            if _tokens(labels[0][0]) != _tokens(labels[1][0]):
                context_similarity *= _lexical_similarity(labels[0][0], labels[1][0])
    return 0.8 * float(score) + 0.2 * context_similarity


def _contexts(text: str, override: list[dict] | None, count: int) -> list[dict]:
    contexts = parse_document(text)[1] if override is None else override
    if not isinstance(contexts, list) or len(contexts) != count:
        raise ValueError("Context records must cover every passage in source order.")
    for record in contexts:
        if not isinstance(record, dict) or record.get("kind") not in {
            "heading",
            "list",
            "paragraph",
        }:
            raise ValueError("Invalid passage context kind.")
        for key in ("headings", "scope"):
            if not isinstance(record.get(key), list) or any(
                not isinstance(x, str) for x in record[key]
            ):
                raise ValueError(f"Context {key} must be a list of source strings.")
        for key in ("section", "scope_indices"):
            if not isinstance(record.get(key), list) or any(
                type(i) is not int or not 0 <= i < count for i in record[key]
            ):
                raise ValueError(f"Context {key} must contain valid passage indices.")
    return contexts


def compare_documents(
    old_text: str,
    new_text: str,
    backend: str = "semantic",
    *,
    profile: str = "verified",
    old_contexts: list[dict] | None = None,
    new_contexts: list[dict] | None = None,
) -> dict[str, Any]:
    """Compare prose with source scope, bounded groups, and inspectable evidence."""
    started = time.perf_counter()
    if backend not in ALIGNMENT_THRESHOLDS:
        raise ValueError("Choose the 'semantic' or 'lexical' backend.")
    if profile not in PROFILES:
        raise ValueError(f"Unknown profile; choose one of {sorted(PROFILES)}.")
    old, new = split_passages(old_text), split_passages(new_text)
    if not old and not new:
        raise ValueError("Add text to at least one document before comparing.")
    oc, nc = (
        _contexts(old_text, old_contexts, len(old)),
        _contexts(new_text, new_contexts, len(new)),
    )
    use_context = profile != "baseline"
    warnings: list[str] = []
    if backend == "lexical":
        warnings.append(
            "Lexical baseline: wording edits are flagged as changes; no semantic model is used."
        )
    if not old or not new:
        warnings.append("One document is empty; all passages are additions or removals.")

    def key(text: str, context: dict) -> tuple:
        return (_content(text), _context_key(context) if use_context else ())

    def adjust(score: float, a: dict, b: dict) -> float:
        return _context_score(score, a, b) if use_context else float(score)

    new_exact: dict[tuple, deque[int]] = defaultdict(deque)
    for j, passage in enumerate(new):
        new_exact[key(passage, nc[j])].append(j)
    exact: list[tuple[tuple[int, ...], tuple[int, ...], float]] = []
    for i, passage in enumerate(old):
        available = new_exact[key(passage, oc[i])]
        if available:
            exact.append(((i,), (available.popleft(),), 1.0))
    old_used = {i for left, _, _ in exact for i in left}
    new_used = {j for _, right, _ in exact for j in right}
    old_remaining = [i for i in range(len(old)) if i not in old_used]
    new_remaining = [j for j in range(len(new)) if j not in new_used]
    models, metadata, matches = None, {}, []
    threshold = ALIGNMENT_THRESHOLDS[backend]
    if old_remaining and new_remaining:
        body = np.array(
            [[_lexical_similarity(old[i], new[j]) for j in new_remaining] for i in old_remaining]
        )
        vectors = None
        if backend == "semantic":
            from radar.models import get_models

            models = get_models()
            embeddings = models.encode(
                [old[i] for i in old_remaining] + [new[j] for j in new_remaining]
            )
            vectors = (embeddings[: len(old_remaining)], embeddings[len(old_remaining) :])
            body = 0.85 * np.clip(vectors[0] @ vectors[1].T, 0, 1) + 0.15 * body
            metadata = models.metadata()
        scores = np.array(
            [
                [adjust(body[a, b], oc[i], nc[j]) for b, j in enumerate(new_remaining)]
                for a, i in enumerate(old_remaining)
            ]
        )
        assignments = _assign(scores, threshold)
        matches = [
            ((old_remaining[a],), (new_remaining[b],), float(scores[a, b])) for a, b in assignments
        ]
        if profile in {"groups", "verified"}:
            from radar.grouping import refine_groups

            matches, skipped = refine_groups(
                old,
                new,
                oc,
                nc,
                old_remaining,
                new_remaining,
                matches,
                body,
                vectors,
                models,
                threshold,
                _lexical_similarity,
                adjust,
            )
            if skipped:
                warnings.append(
                    f"Skipped {skipped} optional split/merge candidates that exceed model token limits."
                )

    changes = []
    for left, right, score in exact:
        change = _base_change(old, new, left, right)
        change.update(
            status="unchanged",
            category="Unchanged",
            alignment_score=1.0,
            explanation="Text and its explicit source scope are unchanged."
            if use_context
            else "Text is identical after whitespace and list-marker normalization.",
        )
        changes.append(change)

    pending, pairs = [], []
    for left, right, score in matches:
        change = _base_change(old, new, left, right)
        change["alignment_score"] = round(score, 4)
        before, after = _scope(oc[left[0]]), _scope(nc[right[0]])
        changed_context = use_context and _context_key(oc[left[0]]) != _context_key(nc[right[0]])
        change.update(
            old_context=before if use_context else [],
            new_context=after if use_context else [],
            context_changed=changed_context,
        )
        if changed_context and _content(change["old_text"]) == _content(change["new_text"]):
            change["scope_review"] = _scope_review(oc[left[0]], nc[right[0]])
        a, b = change["old_text"], change["new_text"]
        if changed_context:
            a = "\n".join(before + [a])
            b = "\n".join(after + [b])
        over_budget = models and (not models.fits_nli(a, b) or not models.fits_nli(b, a))
        if over_budget and not changed_context:
            # Original singleton passage limits retain their explicit error.
            models.predict_nli([(a, b)])
        if over_budget:
            change.update(
                status="uncertain",
                category="Context exceeds model budget",
                explanation="The source scope and passages exceed the NLI token budget. "
                "Review the complete evidence; no source text was truncated.",
            )
            warnings.append("Some contextual comparisons exceed the NLI budget and require review.")
            changes.append(change)
            continue
        pending.append(change)
        pairs.append((a, b))
    nli = models.predict_nli(pairs + [(b, a) for a, b in pairs]) if models and pairs else []
    for k, change in enumerate(pending):
        _classify(change, nli[k] if nli else None, nli[k + len(pairs)] if nli else None)
        if change["context_changed"]:
            scope_signals = _scope_signals(change["old_context"], change["new_context"])
            same_body = _content(change["old_text"]) == _content(change["new_text"])
            if not change["signals"] and (
                scope_signals or (same_body and change["status"] != "reworded")
            ):
                change.update(
                    status="uncertain",
                    category="Same text, different scope"
                    if same_body
                    else "Source scope needs review",
                    signals=scope_signals,
                    explanation="Changed governing context does not by itself establish a "
                    "material change to this passage. Review the source scope and passage together.",
                )
        if (
            len(change["old_indices"]) + len(change["new_indices"]) > 2
            and not change["context_changed"]
        ):
            if _content(change["old_text"]) == _content(change["new_text"]):
                change.update(
                    status="reworded",
                    category="Paragraph layout",
                    explanation="The same combined text was split or merged across paragraphs.",
                )
        if backend == "semantic" and change["alignment_score"] < threshold + 0.04:
            change.update(
                status="uncertain",
                category="Weak alignment",
                explanation="Passage correspondence is weak. Review whether the source "
                "groups belong together before interpreting this edit.",
            )
        if profile == "verified" and models:
            from radar.details import verify_details

            verify_details(change, models)
        if change["status"] != "uncertain":
            change.pop("scope_review", None)
        changes.append(change)

    all_matches = exact + matches
    old_used = {i for left, _, _ in all_matches for i in left}
    new_used = {j for _, right, _ in all_matches for j in right}
    for index in range(len(old)):
        if index not in old_used:
            change = _base_change(old, new, (index,), ())
            change.update(
                status="removed",
                category="Removed passage",
                explanation="No sufficiently supported counterpart was found in the revised document.",
            )
            changes.append(change)
    for index in range(len(new)):
        if index not in new_used:
            change = _base_change(old, new, (), (index,))
            change.update(
                status="added",
                category="Added passage",
                explanation="No sufficiently supported counterpart was found in the original document.",
            )
            changes.append(change)
    for change in changes:
        left, right = change["old_indices"], change["new_indices"]
        if left and right:
            change["moved"] = any(
                (max(left) < min(a) and min(right) > max(b))
                or (min(left) > max(a) and max(right) < min(b))
                for a, b, _ in all_matches
            )
    changes.sort(
        key=lambda c: (not c["new_indices"], c["new_index"] if c["new_indices"] else c["old_index"])
    )
    for index, change in enumerate(changes, 1):
        change["id"] = f"change-{index}"
    return {
        "schema_version": 2,
        "engine": backend,
        "configuration": {
            "profile": profile,
            "context": use_context,
            "groups": profile in {"groups", "verified"},
            "detail_verification": profile == "verified",
            "max_group_size": 2,
        },
        "old_count": len(old),
        "new_count": len(new),
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
        "warnings": list(dict.fromkeys(warnings)),
        "models": metadata,
        "changes": changes,
    }
