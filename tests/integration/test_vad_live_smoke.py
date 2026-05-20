"""Live smoke test for the REAL VAD stack (silero-vad + torchaudio audio I/O).

Unlike the stubbed VAD tests, this loads a tiny committed WAV through the real
`vad.segment`, so it catches transitive-dependency breakage that mocks can't see
(e.g. torchaudio>=2.11 routing decode through an unbundled torchcodec — see
research.md §KL1). Gated by `@pytest.mark.live_asr` and `importorskip`, so it
skips cleanly when the engine deps are not installed but fails loudly when they
are installed and broken.

Run with:  uv run pytest -m live_asr -v
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.live_asr


def test_vad_segment_loads_real_wav(wav_fixture):
    pytest.importorskip("silero_vad")
    pytest.importorskip("torchaudio")
    pytest.importorskip("onnxruntime")

    from speakloop.asr import vad

    # Real silero model (bundled in the package) + real torchaudio decode.
    regions = vad.segment(wav_fixture("attempt-3s.wav"))

    assert isinstance(regions, list)
    for r in regions:
        assert isinstance(r, vad.SpeechRegion)
        assert 0.0 <= r.start_seconds <= r.end_seconds
