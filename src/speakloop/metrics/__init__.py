from speakloop.metrics import fillers, pauses, self_corrections, speech_rate

__all__ = ["fillers", "pauses", "self_corrections", "speech_rate"]


def compute_all(transcript) -> dict[str, float | int]:
    """Compute every per-attempt metric in one call."""
    out: dict[str, float | int] = {}
    out.update(speech_rate.compute(transcript))
    out.update(fillers.compute(transcript.text))
    out.update(pauses.compute(transcript.words))
    out.update(self_corrections.compute(transcript.text))
    return out
