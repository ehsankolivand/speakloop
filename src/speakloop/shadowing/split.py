"""Abbreviation-aware sentence splitter for ideal answers (018, US2, FR-031).

The ideal answers are clean sentence-terminated prose but dense with dotted / camelCase tokens
that are NOT sentence boundaries (version numbers like "API 28", decimals, identifiers such as
"onSaveInstanceState", "System.out"). A naive `.split('.')` over- or under-splits, so this is a
guarded regex splitter: paragraph breaks are hard boundaries, and a `.`/`?`/`!` splits only when
it is not a decimal, not inside a dotted identifier, and not a known abbreviation. Boring,
deterministic, dependency-free — no NLP tokenizer.
"""

from __future__ import annotations

import re

# Known abbreviations (lowercased, dots kept, trailing dot stripped) that do NOT end a sentence.
# Kept small and collision-safe (e.g. no bare "no"/"st" which appear inside common words).
_ABBREV: frozenset[str] = frozenset(
    {"e.g", "i.e", "etc", "vs", "dr", "mr", "mrs", "ms", "prof", "fig", "approx", "cf",
     "a.m", "p.m", "u.s"}
)

# A candidate boundary: sentence punctuation followed by whitespace (so `.`-glued identifiers
# like "System.out" — no following space — can never be a boundary).
_BOUNDARY = re.compile(r"([.!?])(\s+)")
_LAST_TOKEN = re.compile(r"(\S+)$")
_MIN_WORDS = 2  # a fragment below this is merged into its neighbour (no 1-word "sentences")


def _is_abbrev_before(para: str, dot_index: int) -> bool:
    match = _LAST_TOKEN.search(para[:dot_index])
    if not match:
        return False
    token = match.group(1).lower().strip("(\"'").rstrip(".")
    return token in _ABBREV


def _split_paragraph(para: str) -> list[str]:
    out: list[str] = []
    start = 0
    for m in _BOUNDARY.finditer(para):
        dot = m.start()
        punc = m.group(1)
        after = m.end()
        nxt = para[after] if after < len(para) else ""
        prev = para[dot - 1] if dot > 0 else ""

        if punc == ".":
            # decimal / dotted number ("3.14", "v2.0"): digit on both sides of the dot
            if prev.isdigit() and nxt.isdigit():
                continue
            if _is_abbrev_before(para, dot):
                continue
            # a period only ends a sentence when the next sentence starts (uppercase / quote /
            # digit). A following lowercase word means the dot was mid-token punctuation.
            if nxt and not (nxt.isupper() or nxt.isdigit() or nxt in "\"'“('"):
                continue

        sentence = para[start : dot + 1].strip()
        if sentence:
            out.append(sentence)
        start = after
    tail = para[start:].strip()
    if tail:
        out.append(tail)
    return out


def _merge_short(sentences: list[str]) -> list[str]:
    """Fold a sub-`_MIN_WORDS` fragment into the previous sentence so no 1-word 'sentence' ships."""
    merged: list[str] = []
    for s in sentences:
        if merged and len(s.split()) < _MIN_WORDS:
            merged[-1] = f"{merged[-1]} {s}"
        else:
            merged.append(s)
    return merged


def split_sentences(text: str) -> list[str]:
    """Split an ideal answer into sentences (paragraph breaks are hard boundaries)."""
    sentences: list[str] = []
    for paragraph in re.split(r"\n\s*\n", (text or "").strip()):
        collapsed = " ".join(paragraph.split())
        if collapsed:
            sentences.extend(_split_paragraph(collapsed))
    return _merge_short(sentences)
