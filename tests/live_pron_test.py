"""Live correctness harness (017, FR-018/019) — every bundled drill must score clean.

Renders each bundled drill's prompt with the REAL Kokoro TTS, runs it through the REAL
wav2vec2 scorer, and asserts the result is ``scored`` with NO flag on the target. A clean
rendering of the correct words must not be flagged; a drill that flags its own TTS rendering
has a wrong canonical phoneme sequence and must be fixed before shipping.

This is the authoritative pre-ship validation of the hand-authored canonical sequences (the
known correctness-risk surface). It is HEAVY (loads the ~1.3 GB pronunciation model + Kokoro)
and is EXCLUDED from the default suite (``addopts: -m 'not ... and not live_pron'``). Run it
explicitly on a model-equipped machine:

    uv run pytest -m live_pron -v

Mirrors the existing ``live_asr`` / ``live_download`` / ``live_cloud`` self-skipping pattern:
it skips cleanly when the model/TTS are not downloaded, so it never loads a model in CI.
"""

from __future__ import annotations

import pytest

from speakloop.installer import manifest, validator

pytestmark = pytest.mark.live_pron


def _models_ready() -> bool:
    return (
        validator.validate(manifest.WAV2VEC2_PRONUNCIATION).ok
        and validator.validate(manifest.KOKORO_82M).ok
    )


@pytest.mark.skipif(
    not _models_ready(),
    reason="pronunciation model + Kokoro TTS not downloaded — opt into drills first",
)
def test_every_bundled_drill_scores_clean_through_its_own_tts():
    pytest.importorskip("torch")
    pytest.importorskip("transformers")
    pytest.importorskip("kokoro_mlx")

    import json

    from speakloop.pronunciation import build_scorer, load_drill_bank
    from speakloop.tts.kokoro_engine import KokoroEngine

    bank = load_drill_bank()
    tts = KokoroEngine()
    scorer = build_scorer()

    # Vocab coverage: the scorer SILENTLY DROPS any canonical symbol absent from the model
    # vocab, which would make a wrong target phone pass unnoticed. Assert every bank symbol is
    # in the vocab so a typo'd/out-of-vocab symbol fails the harness loudly, not silently.
    vocab_path = manifest.WAV2VEC2_PRONUNCIATION.local_path / "vocab.json"
    vocab = set(json.loads(vocab_path.read_text(encoding="utf-8")).keys())
    missing = {s for s in bank.all_symbols() if s not in vocab}
    assert not missing, f"drill-bank symbols missing from the model vocab (will be silently dropped): {missing}"

    failures: list[str] = []
    for d in bank.drills:
        wav = tts.synthesize(d.prompt)
        c = bank.contrast(d.contrast_id)
        result = scorer.score(
            wav,
            canonical=d.canonical,
            targets=d.targets,
            tip=c.tip if c else "",
            competitors=c.competitors if c else [],
            drill_id=d.id,
            text=d.prompt,
            contrast_id=d.contrast_id,
        )
        if result.status != "scored":
            failures.append(f"{d.id!r} ({d.prompt!r}): status={result.status} {result.detail}")
            continue
        # The scorer only ever flags the `targets`, so any flag on a CLEAN rendering is a
        # false positive caused by a wrong canonical sequence / target index.
        if result.flags:
            flagged = [(fl.expected, fl.word, round(fl.gop, 2)) for fl in result.flags]
            failures.append(f"{d.id!r} ({d.prompt!r}): false flag(s) {flagged}")

    assert not failures, (
        "drills flagged their own clean TTS rendering (fix the canonical sequence / target "
        "index for each):\n  " + "\n  ".join(failures)
    )


# IMP-024: the TRUE-POSITIVE axis. Each pair renders a minimal-pair CONFUSION word (the target
# word with the target phone swapped for a competitor) and scores it against the TARGET word
# drill's canonical — the target phone MUST flag. Together with the false-positive harness above
# this pins BOTH directions: the loosened `_COMPETITOR_FLAG_MARGIN` (0.5→1.5) can no longer drift
# into UNDER-flagging (a real /r/-for-/w/ error scored "clear ✓") without failing on real audio.
_SUBSTITUTIONS = [
    # (target word-drill id, confusion word Kokoro renders with the WRONG phone at the target)
    ("west", "rest"),  # w_r:  /w/ → /ɹ/
    ("vest", "west"),  # v_w:  /v/ → /w/
    ("thin", "sin"),   # th_s: /θ/ → /s/
    ("those", "doze"),  # th_d: /ð/ → /d/
    ("sit", "seat"),   # ih_iy: /ɪ/ → /iː/
]


@pytest.mark.skipif(
    not _models_ready(),
    reason="pronunciation model + Kokoro TTS not downloaded — opt into drills first",
)
def test_a_deliberate_substitution_flags_the_target_phone():
    pytest.importorskip("torch")
    pytest.importorskip("transformers")
    pytest.importorskip("kokoro_mlx")

    from speakloop.pronunciation import build_scorer, load_drill_bank
    from speakloop.tts.kokoro_engine import KokoroEngine

    bank = load_drill_bank()
    tts = KokoroEngine()
    scorer = build_scorer()
    drills = {d.id: d for d in bank.drills}

    misses: list[str] = []
    for drill_id, confusion in _SUBSTITUTIONS:
        d = drills[drill_id]
        c = bank.contrast(d.contrast_id)
        wav = tts.synthesize(confusion)  # render the WRONG (competitor) word
        result = scorer.score(
            wav,
            canonical=d.canonical,
            targets=d.targets,
            tip=c.tip if c else "",
            competitors=c.competitors if c else [],
            drill_id=d.id,
            text=confusion,
            contrast_id=d.contrast_id,
        )
        # A deliberate substitution MUST be caught: scored, with at least one flag on the target.
        if result.status != "scored" or not result.flags:
            misses.append(
                f"{drill_id!r} scored against {confusion!r}: status={result.status} "
                f"flags={[fl.expected for fl in (result.flags or [])]} {result.detail}"
            )

    assert not misses, (
        "a deliberate substitution was NOT flagged (thresholds drifted into UNDER-flagging):\n  "
        + "\n  ".join(misses)
    )
