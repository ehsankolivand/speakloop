"""Post-session interactive debrief — render + read-aloud + replay menu.

This module renders a finished :class:`speakloop.feedback.frontmatter.Session`
in the terminal, optionally reads the educational parts aloud through the
injected TTS engine, and returns the user's next-step choice so the practice
loop can replay the same question, pick a new one, or quit.

Public surface (Principle IV — single responsibility):

- ``DebriefChoice`` — the terminal menu selection (replay / new / quit).
- ``run(session, *, sessions_dir, tts_engine, play_fn, no_audio=False)`` —
  the ``DebriefRunner`` entry point; ``cli/practice.py`` is the only intended
  caller in v1.

Constitution Principle V (Swappable Engines): this module MUST NOT import any
engine-specific package (``kokoro_mlx``, ``mlx_audio``, ``mlx_lm``,
``parakeet_mlx``). Text-to-speech is consumed ONLY through the injected
``TTSEngine`` Protocol and audio playback through an injected ``play`` callable.

The concrete ``DebriefChoice`` and ``run`` re-exports are wired in here once the
renderer/menu/orchestrator land in US2/US3 (see contracts/debrief-interface.py).
"""

from __future__ import annotations

from speakloop.debrief.debrief import run
from speakloop.debrief.menu import DebriefChoice

__all__ = ["DebriefChoice", "run"]
