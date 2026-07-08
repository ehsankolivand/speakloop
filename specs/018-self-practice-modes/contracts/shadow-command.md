# Contract — `speakloop shadow` (Mode B, US2)

## CLI surface (`cli/main.py`)

```
speakloop shadow [--question ID] [--limit N] [--slow/--no-slow]
```

- `--question ID` — shadow the question with this id directly; omitted → interactive picker (mirrors `practice._pick_question`).
- `--limit N` — cap the number of sentences drilled this run (default: all sentences of the chosen answer).
- `--slow/--no-slow` — offer a slower first read of each sentence (default off; the trainer cadence is `cfg.pronunciation_tts_speed`; a slower replay is always available via `r`).
- `--help` — must work with **no models present** and load no engine (function-local imports only).

Registered as `@app.command("shadow")` delegating to a function-local import of `cli.shadow` → `shadow.run(...)`.

## `cli/shadow.py` entry point (injectable for tests)

```python
def run(
    *,
    question_id: str | None = None,
    limit: int | None = None,
    slow: bool = False,
    tts_engine=None,          # injected fake; else KokoroEngine(speed=cfg.pronunciation_tts_speed)
    play_fn=None,             # injected; else audio.playback.play
    record_fn=None,           # injected; else audio.recorder.record
    transcribe_fn=None,       # injected fake (wav -> Transcript); else asr.build_engine(...).engine.transcribe
    key_reader=None,          # injected; else sessions.keyboard.make_key_reader()
    qa_file: Path | None = None,       # else config.resolve_qa_file()
    scratch_dir: Path | None = None,
    input_fn=input,
    console: Console | None = None,
) -> None: ...
```

Everything model/mic/tty is injectable (mirrors `cli/pronounce.py`). The ASR seam is a `transcribe_fn(wav_path) -> Transcript` closure so tests inject a fake transcript without a model.

## Behavior

1. Resolve the Q&A file (`config.resolve_qa_file()`); `content.load(...)`. Pick the question by `--question` id or interactive picker. No file / bad id → clean error, exit non-zero.
2. `shadowing.split_sentences(question.ideal_answer)` → sentences (abbreviation-aware). Cap to `--limit`.
3. Provision Phase B (TTS + ASR) via `installer.ensure_models("B")` only when building real engines (skipped when injected). **Do NOT** call `ensure_pronunciation_model` / `build_scorer`. Decline/fail → clean message, return.
4. For each sentence: **hear** (TTS speaks it; `--slow` plays a slower first read; `r` replays slower; `q` quits) → **repeat** (record via `coordinator._record_stage` → scratch wav) → **transcribe** (`transcribe_fn(wav)` → `Transcript`; then **delete the wav**) → **feedback**:
   - `shadowing.judge_completeness(sentence, transcript.text)` → covered X/Y + missed words; flag *strong* at ≥ 0.70; `captured=False` (empty repeat) → "didn't catch that".
   - `metrics.compute_all(transcript)` → pace (`speech_rate_wpm`) + fillers (`filler_words_count`/density).
5. Print a short closing summary. **No report, no store write.** Non-interactive (no TTY) → skip with a notice.

## Invariants asserted by tests

- Sentences from a multi-sentence answer are each spoken then scored (play before feedback).
- A dotted non-boundary token (`API 28`, a decimal, a `camelCase`/dotted identifier) does not split a sentence (unit test on `split_sentences`).
- An empty/whitespace transcript → `captured=False` ("not captured"), not a coverage failure; loop still advances.
- The scratch wav is deleted after transcription (no residual audio); no `.md` report is written anywhere.
- For a fixed injected transcript, completeness + pace + filler output is identical across runs (determinism).
