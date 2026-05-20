"""Per-session domain-context (Whisper `initial_prompt`) builder (FR-003/FR-004).

Pure, deterministic, offline. Assembles a biasing string from:
  (a) terms mined from the question prompt AND the ideal answer + tags,
  (b) the static seed lexicon (`seed_lexicon.SEED_TERMS`),
  (c) the literal Persian-accent declaration,
and returns a `TranscriptionContext` carrying the prompt + its sha256.

Design note (decision recorded inline per the implement directive): research §(a)
specifies mining "the question prompt". We extend the mined source to include the
question's *ideal answer* as well, because the ideal answer is the richest in-repo
source of the exact technical vocabulary the speaker is expected to use (e.g.
"shared pool", "I/O-bound", "CPU-bound", "primitive"). It is still 100% offline and
deterministic, and it strengthens FR-003/SC-A without biasing toward full ideal-
answer *phrasing* — only individual domain terms are extracted, never the prose.
"""

from __future__ import annotations

import hashlib
import re

from speakloop.asr.interface import TranscriptionContext
from speakloop.asr.seed_lexicon import SEED_TERMS

ACCENT_DECLARATION = "The following is technical English spoken with a Persian accent."

# letter run optionally joined by '/' or '-' to another letter run, e.g.
# "CPU-bound", "I/O-bound", "high-load", "structured-concurrency".
_COMPOUND = re.compile(r"[A-Za-z]+(?:[/-][A-Za-z]+)+")
# all-caps acronym of length >= 2, e.g. "MVI", "OS", "CPU".
_ACRONYM = re.compile(r"\b[A-Z]{2,}\b")
# a single capitalized word, e.g. "Kotlin", "Android".
_CAPWORD = re.compile(r"^[A-Z][a-zA-Z]+$")


def _mine(text: str) -> list[str]:
    """Extract salient technical terms from free text (order-preserving)."""
    terms: list[str] = []
    if not text:
        return terms

    # (1) hyphen/slash compounds; normalize "I/O" -> "IO" so "I/O-bound" reads
    #     as "IO-bound".
    for m in _COMPOUND.finditer(text):
        terms.append(m.group(0).replace("/", ""))

    # (2) all-caps acronyms.
    terms.extend(_ACRONYM.findall(text))

    # (3) capitalized words that are NOT sentence-initial (sentence-initial caps
    #     are usually ordinary words like "Explain"/"You"/"Unlike").
    for sentence in re.split(r"[.!?\n]+", text):
        toks = sentence.split()
        for i, tok in enumerate(toks):
            if i == 0:
                continue
            w = tok.strip(",.;:()[]\"'")
            if _CAPWORD.match(w):
                terms.append(w)

    # (4) any seed term that appears in the text (case-insensitive).
    low = text.lower()
    for s in SEED_TERMS:
        if s.lower() in low:
            terms.append(s)

    return terms


def _dedup_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for it in items:
        key = it.lower()
        if key and key not in seen:
            seen.add(key)
            out.append(it)
    return out


def build_initial_prompt(question) -> str:
    """Assemble the biasing string for one Question (duck-typed: needs
    ``.question``, ``.ideal_answer``, ``.tags``)."""
    mined = _mine(getattr(question, "question", "") or "")
    mined += _mine(getattr(question, "ideal_answer", "") or "")
    tags = list(getattr(question, "tags", None) or [])

    domain_terms = _dedup_preserve_order(mined + tags)
    # Seed lexicon always seeds the bias, even when the question names none of it.
    seed = ", ".join(SEED_TERMS)

    parts = [ACCENT_DECLARATION]
    if domain_terms:
        parts.append("Domain terms: " + ", ".join(domain_terms) + ".")
    parts.append("Common terms: " + seed + ".")
    return " ".join(parts)


def build_context(question) -> TranscriptionContext:
    """Build the per-session `TranscriptionContext` (prompt + sha256, VAD on)."""
    prompt = build_initial_prompt(question)
    digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    return TranscriptionContext(
        initial_prompt=prompt,
        initial_prompt_sha256=digest,
        use_vad=True,
    )
