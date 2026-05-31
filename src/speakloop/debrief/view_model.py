"""Build the in-memory :class:`DebriefViewModel` from a finished ``Session``.

The report file stays the only on-disk artifact; the debrief renders from this
typed view model (data-model §C). Nothing here is serialised.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from speakloop.feedback import frontmatter
from speakloop.feedback.frontmatter import OPEN_BUCKET_IMPACT_RANK

# First ~N words shown in a collapsed transcript preview (FR-014).
PREVIEW_WORDS = 10
# Tolerance bands for first-vs-baseline trend classification (data-model §C.2).
# Differences within the band read as "flat" rather than a real change.
WPM_BAND = 5.0
FILLER_BAND = 0.5


class TrendDirection(str, Enum):
    IMPROVED = "improved"
    FLAT = "flat"
    WORSENED = "worsened"


class AudioKind(str, Enum):
    NARRATIVE = "narrative"
    TOP_PRIORITY = "top_priority"
    PATTERN = "pattern"


@dataclass(frozen=True)
class AttemptRow:
    ordinal: int
    budget: str  # mm:ss
    used: str  # mm:ss
    wpm: float
    filler_density: float
    pauses: int
    # Trend of THIS attempt relative to attempt 1 (attempt 1 is the baseline →
    # FLAT). The last row therefore equals the overall first-vs-last trend.
    wpm_trend: TrendDirection
    filler_trend: TrendDirection


@dataclass(frozen=True)
class PatternCard:
    label: str
    impact_rank: int
    you_said: str
    better: str
    because: str
    extra_evidence: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class TranscriptPreview:
    ordinal: int
    preview: str
    remaining_words: int
    full_text: str


@dataclass(frozen=True)
class AudioSection:
    kind: AudioKind
    index: int  # 1-based position in the read-aloud sequence (for "X of N")
    speak_text: str
    highlight_ref: str  # which on-screen section to highlight while this plays


@dataclass
class DebriefViewModel:
    is_first_time: bool
    top_priority: str
    narrative: str
    attempt_rows: list[AttemptRow]
    pattern_cards: list[PatternCard]
    transcript_previews: list[TranscriptPreview]
    grammar_available: bool
    audio_sections: list[AudioSection]
    # Mutable: toggled by the menu `t` key; reset to False (collapsed) on entry.
    transcripts_expanded: bool = False

    @property
    def audio_total(self) -> int:
        return len(self.audio_sections)


def _mmss(seconds: float) -> str:
    seconds = max(0, int(seconds))
    return f"{seconds // 60}:{seconds % 60:02d}"


def _trend(first: float, value: float, band: float, *, higher_is_better: bool) -> TrendDirection:
    delta = value - first
    if abs(delta) <= band:
        return TrendDirection.FLAT
    improved = delta > 0 if higher_is_better else delta < 0
    return TrendDirection.IMPROVED if improved else TrendDirection.WORSENED


def _attempt_rows(attempts: list[frontmatter.Attempt]) -> list[AttemptRow]:
    if not attempts:
        return []
    base = attempts[0].metrics
    rows: list[AttemptRow] = []
    for a in attempts:
        m = a.metrics
        rows.append(
            AttemptRow(
                ordinal=a.ordinal,
                budget=_mmss(a.time_budget_seconds),
                used=_mmss(a.actual_duration_seconds),
                wpm=m.speech_rate_wpm,
                filler_density=m.filler_density_per_100_words,
                pauses=m.pauses_count,
                wpm_trend=_trend(
                    base.speech_rate_wpm, m.speech_rate_wpm, WPM_BAND, higher_is_better=True
                ),
                filler_trend=_trend(
                    base.filler_density_per_100_words,
                    m.filler_density_per_100_words,
                    FILLER_BAND,
                    higher_is_better=False,
                ),
            )
        )
    return rows


def _rank(p: frontmatter.GrammarPattern) -> int:
    return p.impact_rank if p.impact_rank is not None else OPEN_BUCKET_IMPACT_RANK


def _pattern_cards(patterns: list[frontmatter.GrammarPattern]) -> list[PatternCard]:
    cards: list[PatternCard] = []
    for p in sorted(patterns, key=lambda x: (_rank(x), -x.occurrence_count)):
        primary = p.evidence[0] if p.evidence else {}
        extra = tuple(
            ((ev.get("quote") or "").strip(), (ev.get("corrected") or "").strip())
            for ev in p.evidence[1:]
        )
        cards.append(
            PatternCard(
                label=p.label,
                impact_rank=_rank(p),
                you_said=(primary.get("quote") or "").strip(),
                better=(primary.get("corrected") or "").strip(),
                because=(p.explanation or "").strip(),
                extra_evidence=extra,
            )
        )
    return cards


def _transcript_previews(attempts: list[frontmatter.Attempt]) -> list[TranscriptPreview]:
    previews: list[TranscriptPreview] = []
    for a in attempts:
        words = a.transcript.split()
        preview = " ".join(words[:PREVIEW_WORDS])
        previews.append(
            TranscriptPreview(
                ordinal=a.ordinal,
                preview=preview,
                remaining_words=max(0, len(words) - PREVIEW_WORDS),
                full_text=a.transcript.strip(),
            )
        )
    return previews


def _pattern_speak_text(card: PatternCard) -> str:
    parts: list[str] = [card.label + "."]
    if card.because:
        parts.append(card.because)
    # FR-009: never read a no-op "fix" where the correction equals the quote.
    has_fix = bool(card.better) and card.better != card.you_said
    if card.you_said and has_fix:
        parts.append(f"Instead of saying, {card.you_said}, say, {card.better}.")
    elif has_fix:
        parts.append(f"Try saying, {card.better}.")
    return " ".join(parts)


def _audio_sections(
    narrative: str, top_priority: str, cards: list[PatternCard]
) -> list[AudioSection]:
    """Educational sections only, ordered narrative → top priority → patterns.

    Transcripts and raw metrics are deliberately excluded (FR-017).
    """
    sections: list[AudioSection] = []
    index = 1
    if narrative:
        sections.append(AudioSection(AudioKind.NARRATIVE, index, narrative, "narrative"))
        index += 1
    if top_priority:
        sections.append(
            AudioSection(AudioKind.TOP_PRIORITY, index, top_priority, "top_priority")
        )
        index += 1
    for i, card in enumerate(cards):
        sections.append(
            AudioSection(AudioKind.PATTERN, index, _pattern_speak_text(card), f"pattern:{i}")
        )
        index += 1
    return sections


def _is_first_time(sessions_dir: Path) -> bool:
    """True when no prior report exists besides this session's own file (FR-030).

    The report has already been written when the debrief runs, so a brand-new
    user has exactly one report file in ``sessions_dir``.
    """
    try:
        reports = list(Path(sessions_dir).glob("*.md"))
    except OSError:
        return True
    return len(reports) <= 1


def build_view_model(
    session: frontmatter.Session, *, sessions_dir: Path
) -> DebriefViewModel:
    narrative = (session.cross_attempt_narrative or "").strip()
    top_priority = (session.top_priority or "").strip()
    cards = _pattern_cards(session.grammar_patterns)
    return DebriefViewModel(
        is_first_time=_is_first_time(sessions_dir),
        top_priority=top_priority,
        narrative=narrative,
        attempt_rows=_attempt_rows(session.attempts),
        pattern_cards=cards,
        transcript_previews=_transcript_previews(session.attempts),
        grammar_available=session.generated_by_phase == "C",
        audio_sections=_audio_sections(narrative, top_priority, cards),
        transcripts_expanded=False,
    )
