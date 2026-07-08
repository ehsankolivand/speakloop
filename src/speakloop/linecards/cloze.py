"""Anki cloze export for rescue-line cards (018, US1, FR-018).

Turns a card into one Anki cloze-import line, wrapping the CHANGED token(s) in ``{{c1::…}}``
followed by a short rule hint — the exact format the cloud coach already emits (verified in
`openrouter_coach_prompt_default.txt` + real report bodies). The changed span is found by a
word-level diff of the "You said" quote against the "Better:" correction, so the cloze targets
precisely what the correction is about (e.g. a dropped article `a`, a missing `-s`). Pure and
deterministic — stdlib `difflib` only.
"""

from __future__ import annotations

import difflib
import re

from speakloop.linecards.cards import LineCard

_WS = re.compile(r"\s+")


def _tokens(text: str) -> list[str]:
    return [t for t in _WS.split(text.strip()) if t]


def _wrap_all(text: str) -> str:
    body = text.strip()
    return "{{c1::" + body + "}}" if body else ""


def _wrap_spans(tokens: list[str], changed: list[bool]) -> str:
    """Wrap each contiguous run of changed tokens in one ``{{c1::…}}`` (same cloze group)."""
    out: list[str] = []
    i, n = 0, len(tokens)
    while i < n:
        if changed[i]:
            j = i
            while j < n and changed[j]:
                j += 1
            out.append("{{c1::" + " ".join(tokens[i:j]) + "}}")
            i = j
        else:
            out.append(tokens[i])
            i += 1
    return " ".join(out)


def cloze_from_correction(quote: str, corrected: str) -> str:
    """Wrap the span(s) of ``corrected`` that differ from ``quote`` in ``{{c1::…}}``.

    Degenerate cases (no quote, or the change is a pure deletion with nothing new on the
    corrected side) fall back to clozing the whole corrected line, so every card always has a
    non-empty cloze deletion (SC-005)."""
    corr = _tokens(corrected)
    if not corr:
        return ""
    q = _tokens(quote)
    if not q:
        return _wrap_all(corrected)

    matcher = difflib.SequenceMatcher(a=[t.lower() for t in q], b=[t.lower() for t in corr])
    changed = [False] * len(corr)
    any_changed = False
    for tag, _i1, _i2, j1, j2 in matcher.get_opcodes():
        if tag in ("replace", "insert"):
            for j in range(j1, j2):
                changed[j] = True
                any_changed = True
    if not any_changed:
        return _wrap_all(corrected)
    return _wrap_spans(corr, changed)


def _wrap_substring(text: str, span: str) -> str:
    """Wrap the first occurrence of ``span`` in ``text`` (starter cards carry an explicit span)."""
    idx = text.find(span)
    if idx < 0:
        return _wrap_all(text)
    return f"{text[:idx]}{{{{c1::{span}}}}}{text[idx + len(span):]}"


def anki_line(card: LineCard) -> str:
    """One Anki cloze-import line for a card: ``<corrected with cloze> (rule hint)``."""
    if card.source == "starter" and card.cloze:
        body = _wrap_substring(card.corrected, card.cloze)
    else:
        body = cloze_from_correction(card.quote, card.corrected)
    return f"{body} ({card.rule})" if card.rule else body


def to_anki(cards: list[LineCard]) -> str:
    """The whole deck as an Anki cloze-import text (one card per line, deduped by caller)."""
    return "\n".join(anki_line(c) for c in cards)
