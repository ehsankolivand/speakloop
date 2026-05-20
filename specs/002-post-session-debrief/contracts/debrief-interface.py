"""
debrief module public interface — proposed STABLE contract.

The `debrief/` module renders a finished session in the terminal, optionally
reads the educational parts aloud, and returns the user's next-step choice.

Constitution Principle V: `debrief/` MUST NOT import any engine-specific package
(no `kokoro_mlx`, `mlx_audio`, `mlx_lm`, `parakeet_mlx`). It consumes text-to-
speech ONLY through the injected `TTSEngine` Protocol (speakloop.tts) and audio
playback through an injected play callable (speakloop.audio.playback.play).

Principle IV: this is the module's single public surface; `cli/practice.py` is
the only intended caller in v1.
"""

from __future__ import annotations

from collections.abc import Callable
from enum import Enum
from pathlib import Path
from typing import Protocol

from speakloop.feedback import frontmatter  # Session, GrammarPattern, Attempt
from speakloop.tts import TTSEngine


class DebriefChoice(str, Enum):
    """The user's terminal menu selection after the debrief (FR-023/FR-024).

    Note: the transcript-toggle key `t` (FR-014/FR-024) is intentionally NOT a
    member here. It is an in-place toggle handled inside the menu loop (flips
    full-transcript expansion and re-renders); the loop keeps running and only
    returns once one of the three terminal choices below is made.
    """

    REPLAY = "replay"   # r / replay  — same question, fresh 4/3/2, no model reload
    NEW = "new"         # n / new     — open the question picker
    QUIT = "quit"       # q / quit    — return to the shell


class DebriefRunner(Protocol):
    """Renders the debrief and returns the user's choice."""

    def run(
        self,
        session: frontmatter.Session,
        *,
        sessions_dir: Path,
        tts_engine: TTSEngine | None,
        play_fn: Callable[[Path], None] | None,
        no_audio: bool = False,
    ) -> DebriefChoice:
        """
        Render the in-place debrief for a completed `session`, then return the
        user's next-step choice.

        Behaviour contract (maps to spec FRs):
          - Renders the report visually in place (FR-010): a bordered Top-priority
            banner above the patterns (FR-011), three-line pattern cards
            "You said / Better / Because" in `impact_rank` order (FR-012, FR-005),
            a trend-coloured attempt table green/yellow/red (FR-013), and
            transcripts collapsed by default with a "+N words" indicator (FR-014).
          - If `session` carries no grammar patterns because the LLM model is
            absent, the grammar area is replaced with the single line
            "Grammar pattern analysis is available when the LLM model is installed."
            (FR-028) and the rest of the debrief still runs.
          - First-time orientation line shown iff no prior report exists in
            `sessions_dir` besides this session's own file (FR-030).
          - Unless `no_audio` (FR-021) or `tts_engine`/`play_fn` is None, shows the
            announcement "🔊 Reading your feedback aloud — press any key to skip."
            (FR-016), then reads aloud ONLY the educational sections in the order
            narrative → top priority → each pattern's explanation + corrected
            version (FR-017, FR-018), highlighting the active section (FR-019) and
            showing "X of N sections" progress (FR-019). Transcripts and raw
            metrics tables are never read aloud (FR-017).
          - Any keypress during the announcement or playback stops remaining audio
            immediately and jumps to the menu with no confirmation (FR-020).
          - If TTS/playback raises for any reason, the visual debrief continues and
            the menu appears immediately — never hangs (FR-029).
          - The menu accepts r/n/q and replay/new/quit, defaults to REPLAY with
            arrow-key navigation, and treats Enter on the default as REPLAY
            (FR-023, FR-024).
          - The menu also accepts a transcript-toggle key `t` (FR-014/FR-024)
            that expands/collapses full transcripts in place and keeps the menu
            open (it is not a DebriefChoice); only replay/new/quit returns.
          - Does NOT write the report (already written by the coordinator) and does
            NOT reload models. Returns promptly so the caller's replay path can
            reach "press space to begin attempt 1" in < 3 s (SC-004).
        """
        ...


# --- Content-side contracts (feedback module additions) -----------------------


class GrammarAnalyzer(Protocol):
    """The redesigned, catalog-aware analyzer (feedback/grammar_analyzer.py).

    Same call shape the coordinator already uses: a callable taking the three
    transcripts and returning verified, ranked GrammarPattern findings. The
    returned patterns carry the additive fields (explanation, impact_rank,
    catalog_id, per-evidence `corrected`) defined in data-model.md §A.
    """

    def __call__(
        self, transcripts: list,  # list[speakloop.asr.Transcript]
    ) -> list[frontmatter.GrammarPattern]:
        """
        Contract:
          - Every returned pattern's `label` matches a catalog entry or is an
            open-bucket label; open-bucket requires occurrence_count >= 2.
          - Every pattern has a non-empty `explanation` (the transfer reason).
          - Every evidence `quote` is a verbatim transcript substring (FR-007)
            AND passes the coherence filter (FR-006); patterns left with no
            coherent evidence are dropped.
          - Each evidence item SHOULD carry a `corrected` that differs from
            `quote`; patterns whose only correction equals the quote are
            suppressed (FR-009).
          - Patterns are returned sorted by `impact_rank` ascending (FR-005).
        """
        ...
