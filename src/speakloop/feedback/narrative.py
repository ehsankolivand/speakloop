"""Deterministic cross-attempt narrative + single Top priority (FR-008).

Both outputs are computed WITHOUT the LLM (research.md §g): the "single most
important thing to fix" must be stable, explainable, and reproducible from the
report file alone, so it is derived from the persisted impact ranking and a
fixed fluency-severity heuristic — never a model guess.

* :func:`build_narrative` — prose describing what improved / stayed the same
  across the 4/3/2 rounds (extends the v1 ``_cross_attempt_paragraph`` logic).
* :func:`select_top_priority` — the single highest-impact item across BOTH
  grammar patterns (scored by ``impact_rank``) and fluency dimensions (scored by
  the documented severity thresholds below). A fluency issue MAY win over grammar
  when it outranks it, and vice versa. Degrades to a sensible default.
"""

from __future__ import annotations

from speakloop.feedback.catalog import OPEN_BUCKET_IMPACT_RANK
from speakloop.feedback.frontmatter import Attempt, GrammarPattern

# --- Fluency severity thresholds (documented; unit-tested) -------------------
# Mapped onto the SAME 1..N impact scale as grammar ``impact_rank`` (1 = most
# impactful) so grammar and fluency candidates compete on one axis. Worst value
# across the (non-silent) attempts is used, since the Top priority is what to fix
# *next* time.
FILLER_SEVERE = 8.0  # fillers / 100 words → rank 1
FILLER_HIGH = 6.0  # → rank 2
FILLER_NOTABLE = 4.0  # → rank 3
RATE_SEVERE = 75.0  # WPM below this → rank 1
RATE_LOW = 90.0  # → rank 2
RATE_NOTABLE = 105.0  # → rank 3

# Exact default strings (asserted by tests / T040).
SILENT_DEFAULT = "No content captured this session — focus on speaking out loud next time."
NOTABLE_DEFAULT = (
    "No single high-impact issue stood out this session — keep practicing under "
    "time pressure to lock in the gains."
)

# Source ordering for deterministic tie-breaks when ranks are equal:
# grammar first, then filler, then speech rate.
_SRC_GRAMMAR = 0
_SRC_FILLER = 1
_SRC_RATE = 2


def _non_silent(attempts: list[Attempt]) -> list[Attempt]:
    return [a for a in attempts if a.metrics.words_total > 0]


def _first_evidence(pattern: GrammarPattern) -> dict:
    """Prefer an evidence item that carries a `corrected` rewrite."""
    for ev in pattern.evidence:
        if ev.get("corrected"):
            return ev
    return pattern.evidence[0] if pattern.evidence else {}


def _grammar_prescription(pattern: GrammarPattern) -> str:
    ev = _first_evidence(pattern)
    quote = (ev.get("quote") or "").strip()
    corrected = (ev.get("corrected") or "").strip()
    if quote and corrected:
        return f'Fix {pattern.label}: say "{corrected}", not "{quote}".'
    if pattern.explanation:
        return f"Fix {pattern.label}: {pattern.explanation.strip()}"
    return f"Fix {pattern.label}."


def _grammar_candidate(patterns: list[GrammarPattern]) -> tuple[int, int, str] | None:
    if not patterns:
        return None
    top = min(patterns, key=lambda p: p.impact_rank if p.impact_rank is not None else OPEN_BUCKET_IMPACT_RANK)
    rank = top.impact_rank if top.impact_rank is not None else OPEN_BUCKET_IMPACT_RANK
    return (rank, _SRC_GRAMMAR, _grammar_prescription(top))


def _fluency_candidates(attempts: list[Attempt]) -> list[tuple[int, int, str]]:
    voiced = _non_silent(attempts)
    if not voiced:
        return []
    out: list[tuple[int, int, str]] = []

    worst_filler = max(a.metrics.filler_density_per_100_words for a in voiced)
    filler_rank = (
        1 if worst_filler >= FILLER_SEVERE
        else 2 if worst_filler >= FILLER_HIGH
        else 3 if worst_filler >= FILLER_NOTABLE
        else None
    )
    if filler_rank is not None:
        out.append(
            (
                filler_rank,
                _SRC_FILLER,
                f"Cut the filler words — you averaged {worst_filler:.1f} per 100 words; "
                "pause silently instead of saying um/uh.",
            )
        )

    worst_rate = min(a.metrics.speech_rate_wpm for a in voiced)
    rate_rank = (
        1 if worst_rate < RATE_SEVERE
        else 2 if worst_rate < RATE_LOW
        else 3 if worst_rate < RATE_NOTABLE
        else None
    )
    if rate_rank is not None:
        out.append(
            (
                rate_rank,
                _SRC_RATE,
                f"Bring your speaking pace up — you dipped to {worst_rate:.0f} WPM; "
                "aim for a steady, unhurried flow rather than long stalls.",
            )
        )
    return out


def select_top_priority(patterns: list[GrammarPattern], attempts: list[Attempt]) -> str:
    """The single most important thing to fix next session (most-impactful-wins).

    Deterministic: scores grammar patterns by ``impact_rank`` and fluency by the
    fixed thresholds above, then returns the lowest-rank (highest-impact) item.
    Ties break toward grammar, then filler, then rate. Degrades to a default.
    """
    if not _non_silent(attempts):
        return SILENT_DEFAULT
    candidates: list[tuple[int, int, str]] = []
    grammar = _grammar_candidate(patterns)
    if grammar is not None:
        candidates.append(grammar)
    candidates.extend(_fluency_candidates(attempts))
    if not candidates:
        return NOTABLE_DEFAULT
    rank, _src, prescription = min(candidates, key=lambda c: (c[0], c[1]))
    return prescription


def _recurring_pattern(patterns: list[GrammarPattern]) -> GrammarPattern | None:
    for p in patterns:
        attempts_seen = {ev.get("attempt_ordinal") for ev in p.evidence}
        if p.occurrence_count >= 2 or len(attempts_seen) >= 2:
            return p
    return None


def build_narrative(attempts: list[Attempt], patterns: list[GrammarPattern]) -> str:
    """Deterministic prose: what improved and what stayed the same across rounds."""
    voiced = _non_silent(attempts)
    if not voiced:
        return "No speech was captured across the attempts this session."

    first, last = voiced[0], voiced[-1]
    wpm1, wpm3 = first.metrics.speech_rate_wpm, last.metrics.speech_rate_wpm
    fill1, fill3 = (
        first.metrics.filler_density_per_100_words,
        last.metrics.filler_density_per_100_words,
    )
    wpm_dir = "climbed" if wpm3 > wpm1 else "dropped" if wpm3 < wpm1 else "held steady at"
    fill_dir = "fell" if fill3 < fill1 else "rose" if fill3 > fill1 else "held steady"

    sentences = [
        f"Across the timed rounds your speech rate {wpm_dir} from {wpm1:.0f} to {wpm3:.0f} "
        f"WPM and filler density {fill_dir} from {fill1:.1f} to {fill3:.1f} per 100 words."
    ]
    if wpm3 > wpm1 and fill3 < fill1:
        sentences.append("Rising pace with fewer fillers is the proceduralization signature.")

    recurring = _recurring_pattern(patterns)
    if recurring is not None:
        sentences.append(
            f"{recurring.label.capitalize()} recurred across rounds — that is the habit to target next."
        )
    elif patterns:
        sentences.append(f"{patterns[0].label.capitalize()} showed up — worth watching next session.")
    else:
        sentences.append("No grammar pattern recurred across the rounds.")
    return " ".join(sentences)
