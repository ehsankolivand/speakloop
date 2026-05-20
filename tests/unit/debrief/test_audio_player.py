"""T033 — read-aloud player: order, skip, error-swallowing (FR-017–FR-020, FR-029).

The TTS engine and playback are stubbed; no real audio, no real tty. We assert
that only the educational sections are synthesized (transcripts/metrics never
reach the player), they play in narrative → top priority → patterns order, an
injected keypress abandons the remaining audio, and a TTS/playback exception is
swallowed so control returns to the caller (the menu).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from speakloop.debrief import audio_player
from speakloop.debrief.view_model import AudioKind, AudioSection, _audio_sections

pytestmark = pytest.mark.unit


class _StubTTS:
    """Records every text it is asked to synthesize; returns a fake wav path."""

    def __init__(self, *, raise_on=None):
        self.calls: list[str] = []
        self._raise_on = raise_on

    def synthesize(self, text, **_kwargs):
        self.calls.append(text)
        if self._raise_on is not None and self._raise_on in text:
            raise RuntimeError("synth boom")
        return Path(f"/tmp/clip-{len(self.calls)}.wav")


def _play_recorder():
    played: list[Path] = []
    return played, lambda p: played.append(Path(p))


def _sections() -> list[AudioSection]:
    return [
        AudioSection(AudioKind.NARRATIVE, 1, "You spoke more steadily.", "narrative"),
        AudioSection(AudioKind.TOP_PRIORITY, 2, "Focus on plural agreement.", "top_priority"),
        AudioSection(AudioKind.PATTERN, 3, "Plural agreement. Because ...", "pattern:0"),
    ]


def test_plays_all_sections_in_order_when_not_skipped():
    sections = _sections()
    tts = _StubTTS()
    played, play_fn = _play_recorder()
    seen: list[str] = []

    outcome = audio_player.read_aloud(
        sections,
        tts_engine=tts,
        play_fn=play_fn,
        on_section=lambda s: seen.append(s.highlight_ref),
    )

    assert outcome.played == 3
    assert not outcome.skipped and not outcome.errored
    # Synthesized exactly the educational text, narrative → top priority → pattern.
    assert tts.calls == [s.speak_text for s in sections]
    assert len(played) == 3
    # The highlight callback fired once per section, in order.
    assert seen == ["narrative", "top_priority", "pattern:0"]


def test_only_educational_text_is_synthesized_never_transcripts():
    """_audio_sections excludes transcripts/metrics, so the player never sees them."""
    cards = []  # patterns rendered as cards feed pattern sections; none here
    sections = _audio_sections("narrative text", "top priority text", cards)
    tts = _StubTTS()
    _played, play_fn = _play_recorder()

    audio_player.read_aloud(sections, tts_engine=tts, play_fn=play_fn)

    assert tts.calls == ["narrative text", "top priority text"]
    # Only narrative + top priority were emitted as audio; no transcript/metrics text.
    assert "transcript" not in " ".join(tts.calls).lower()


def test_keypress_stops_remaining_audio_and_returns():
    sections = _sections()
    tts = _StubTTS()
    played, play_fn = _play_recorder()

    # Skip requested after the first section plays.
    state = {"n": 0}

    def skip_check() -> bool:
        # False before the first section; True once one has played.
        return state["n"] >= 1

    def on_section(_s) -> None:
        state["n"] += 1

    outcome = audio_player.read_aloud(
        sections,
        tts_engine=tts,
        play_fn=play_fn,
        on_section=on_section,
        skip_check=skip_check,
    )

    assert outcome.skipped is True
    assert outcome.errored is False
    assert outcome.played == 1  # only the first section actually played
    assert len(tts.calls) == 1


def test_immediate_skip_plays_nothing():
    sections = _sections()
    tts = _StubTTS()
    played, play_fn = _play_recorder()

    outcome = audio_player.read_aloud(
        sections,
        tts_engine=tts,
        play_fn=play_fn,
        skip_check=lambda: True,
    )

    assert outcome.skipped is True
    assert outcome.played == 0
    assert tts.calls == []
    assert played == []


def test_tts_exception_is_swallowed_and_returns():
    sections = _sections()
    tts = _StubTTS(raise_on="Focus on plural")  # blow up on the top-priority section
    played, play_fn = _play_recorder()

    outcome = audio_player.read_aloud(sections, tts_engine=tts, play_fn=play_fn)

    assert outcome.errored is True
    assert outcome.skipped is False
    assert outcome.played == 1  # narrative played; top priority raised
    # Control returned rather than propagating — the menu can now appear (FR-029).


def test_playback_exception_is_swallowed_and_returns():
    sections = _sections()
    tts = _StubTTS()

    def boom(_p):
        raise RuntimeError("playback boom")

    outcome = audio_player.read_aloud(sections, tts_engine=tts, play_fn=boom)

    assert outcome.errored is True
    assert outcome.played == 0
