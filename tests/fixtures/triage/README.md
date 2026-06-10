# Triage fixtures (010-interview-loop, P4)

Human-labelled transcript spans backing **SC-003** (no ASR hallucination ever
reaches grammar evidence) and **SC-006** (pronunciation mishearings appear only as
pronunciation flags, never as grammar errors).

## Labeling rubric

Each case in `cases.yaml` is authored from real prior session transcripts,
**independently of the triage implementation** (so the checks are external, not
self-graded). A span is labelled exactly one of:

- `hallucination` — transcribed text where the recording has no corresponding
  voice activity (silence), or a known phantom phrase. MUST be dropped before any
  grammar/coverage/metrics work (deterministic filter, no LLM).
- `mishearing` — a low-confidence transcription of a real utterance that is
  phonetically close to a plausible intended word (e.g. "must" → "mouse"). MUST be
  surfaced as a pronunciation flag, never counted as a grammar error.
- `real` — ordinary speech kept for analysis.

Each case carries: `text`, optional `vad_silence` (bool, span falls in a VAD gap),
optional `no_speech_prob` / `avg_logprob` (recorded Whisper segment signals), and
`label`. The deterministic hallucination test (`tests/unit/triage/test_hallucination.py`)
asserts classification from these recorded signals — never a byte-exact golden file.
