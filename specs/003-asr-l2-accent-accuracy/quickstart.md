# Quickstart: ASR Accuracy on Persian-L1 Accented Technical English

Exercise the upgraded transcription pipeline and the mandatory reproducibility
gate locally. Apple Silicon (M3 Pro 18 GB target); offline after model download.

## 1. Install deps + model

```bash
uv sync                       # pulls mlx-whisper, silero-vad, onnxruntime (pinned)
uv run speakloop practice     # first run consents to + downloads the Whisper model
                              # (mlx-community/whisper-large-v3-turbo, ~1.6 GB) via the
                              # existing resumable installer; Parakeet stays installed
```

## 2. Run a Phase-C session on the new default (Whisper)

```bash
uv run speakloop practice     # default ASR is now Whisper-large-v3-turbo
```

Speak the kotlin-coroutines answer. Expected: the report transcript contains
"threads", "coroutine", "dispatcher", "IO-bound", "shared pool" correctly — not
"trades / quarantine / shaded pool" (SC-A). The report frontmatter now carries an
additive `asr:` block (engine, model, the exact domain prompt + its sha256, VAD
settings); `schema_version` is still `1`.

## 3. Power-user engine flag + fallback

```bash
uv run speakloop practice --asr-engine parakeet   # force the previous engine (benchmarking)
uv run speakloop practice --asr-engine whisper    # explicit default
```

Simulate a Whisper load failure (e.g. temporarily move the model dir): the
session still completes on Parakeet, one English line notes the fallback, and the
report's `asr.fell_back` is `true` (SC-F).

## 4. Pause tolerance (VAD)

Record an attempt with a deliberate 3-second silent pause mid-answer. The
transcript must contain no tokens from the silent window (SC-C), and the pause
must still appear in the fluency metrics (`pauses_count` / `mean_pause_ms`) —
silence is dropped before the ASR but the timeline is preserved.

## 5. The reproducibility gate (mandatory acceptance — FR-010)

Place the captured failure-session recordings + hand transcript under
`tests/fixtures/repro_kotlin_coroutines/` (see `data-model.md` §D), then:

```bash
uv run pytest -m repro -v
```

This runs the new pipeline against the original recordings and reports per-token
improvement vs the previous pipeline. Green requires:
- target tokens correct in ≥4/5 occurrences (SC-A);
- ≥30% relative technical-token WER reduction vs Parakeet (SC-B).

Without the recordings the gate **skips with a clear message** (so model-free CI
still passes) — but the feature is not "done" until it has run green on the
user's own audio.

## 6. Full test suite (model-free)

```bash
uv run pytest                 # Whisper/VAD/Parakeet stubbed; no live model calls
uv run ruff check src tests
```

Unit + integration coverage: domain-context mining, seed lexicon, VAD merge
logic, per-region timeline stitching, all-silence → empty transcript,
selection+fallback, `asr:` frontmatter additive round-trip, and that
`ParakeetEngine` ignores `context`.

## 7. Sanity: model loaded once

In a session with replay, the Whisper model loads exactly once (before attempt 1)
and is reused across attempts and the replay — the next "press space to begin
attempt 1" appears in well under the 5 s budget with Qwen co-resident (SC-D,
research §c).
