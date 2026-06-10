from speakloop.metrics import fillers, pauses, self_corrections, speech_rate

__all__ = ["fillers", "pauses", "self_corrections", "speech_rate"]


def compute_all(transcript, *, vad_regions=None) -> dict[str, float | int]:
    """Compute every per-attempt metric in one call.

    ``vad_regions`` (010-interview-loop, P4): an optional tuple of
    ``(start_seconds, end_seconds)`` real-speech regions. When supplied — i.e. the
    triage step has removed ASR-hallucination/silence spans — speech rate uses the
    summed real-speech duration as its denominator and pauses are counted only
    within real-speech regions, so hallucinated spans affect no metric. When
    ``None`` (default), the result is byte-identical to the pre-feature behaviour.
    """
    real_speech_seconds = None
    if vad_regions:
        real_speech_seconds = sum(max(0.0, end - start) for (start, end) in vad_regions)
    out: dict[str, float | int] = {}
    out.update(speech_rate.compute(transcript, real_speech_seconds=real_speech_seconds))
    out.update(fillers.compute(transcript.text))
    out.update(pauses.compute(transcript.words, vad_regions=vad_regions))
    out.update(self_corrections.compute(transcript.text))
    return out
