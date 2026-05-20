# Phase 1 Data Model: ASR Accuracy on Persian-L1 Accented Technical English

All additions are **additive**. `schema_version` stays **1**. Existing entities
(`Transcript`, `WordTiming`, `Session`, `Attempt`, …) keep their shape; new fields
are optional and emitted/consumed only when present.

## A. New / changed in-memory types

### A.1 `TranscriptionContext` (new — `asr/interface.py`)

The per-session biasing payload passed into `transcribe`. Frozen dataclass.

| Field | Type | Notes |
|---|---|---|
| `initial_prompt` | `str | None` | the assembled domain prompt; `None` disables biasing |
| `initial_prompt_sha256` | `str` | hex sha256 of `initial_prompt` (`""` when prompt is `None`); recorded in provenance |
| `use_vad` | `bool` (default `True`) | run VAD pre-segmentation in the Whisper path |

Validation: `initial_prompt`, if present, is non-empty after strip; the sha256 is
computed over the exact bytes used so reports are reproducible (FR-007).

### A.2 `ASREngine.transcribe` (changed signature — `asr/interface.py`)

```python
def transcribe(self, wav_path: Path, *, context: TranscriptionContext | None = None) -> Transcript: ...
```

Additive optional keyword; default `None` preserves all existing call sites.
`Transcript` / `WordTiming` are **unchanged**.

### A.3 `SpeechRegion` (new — `asr/vad.py`)

A detected speech span on the original audio timeline.

| Field | Type | Notes |
|---|---|---|
| `start_seconds` | `float` | region start on the original timeline |
| `end_seconds` | `float` | region end on the original timeline |

Invariants: `0 ≤ start < end ≤ audio_duration`; regions are sorted and
non-overlapping after merge (gaps ≤ `merge_gap_ms` already merged). The Whisper
engine transcribes each region and offsets returned word timings by
`start_seconds` so the reassembled `Transcript.words` sit on the original
timeline (preserving pause gaps — research §(b)).

### A.4 `EngineSelection` (new — `asr/selection.py`)

Result of resolving which engine actually runs.

| Field | Type | Notes |
|---|---|---|
| `engine` | `ASREngine` | the resident, ready-to-use engine instance |
| `engine_name` | `str` | `"whisper"` or `"parakeet"` (the one that loaded) |
| `model_id` | `str` | HF repo id of the loaded model |
| `fell_back` | `bool` | `True` if the requested engine failed and we fell back |
| `fallback_reason` | `str | None` | human-readable reason (English), `None` unless `fell_back` |

The CLI prints one English line when `fell_back` is `True` (FR-009, SC-F).

### A.5 `AsrProvenance` (new — `feedback/frontmatter.py`)

Recorded additively per session. Frozen dataclass; serialized as the top-level
`asr:` mapping.

| Field | Type | Frontmatter key | Notes |
|---|---|---|---|
| `engine` | `str` | `engine` | engine that ran (`whisper`/`parakeet`) |
| `model` | `str` | `model` | model id |
| `initial_prompt` | `str | None` | `initial_prompt` | verbatim domain context (debuggability) |
| `initial_prompt_sha256` | `str` | `initial_prompt_sha256` | hash of the above |
| `vad` | `dict | None` | `vad` | tunables that ran, or `null`/omitted when disabled |
| `fell_back` | `bool` | `fell_back` | whether a fallback occurred |

### A.6 `Session.asr` (changed — `feedback/frontmatter.py`)

`Session` gains an additive optional field `asr: AsrProvenance | None = None`.
`dump` emits the top-level `asr:` block **only when present** (byte-identical to
v1 reports otherwise); `parse` reads it back when present, ignores it when absent.

## B. Frontmatter serialization (schema_version stays 1)

`dump` adds, after the existing additive keys, when `session.asr` is set:

```yaml
asr:
  engine: whisper
  model: mlx-community/whisper-large-v3-turbo
  initial_prompt: |
    The following is technical English spoken with a Persian accent.
    Domain: Kotlin coroutines, threads, dispatcher, IO-bound, CPU-bound, mutex,
    shared pool. Common terms: coroutines, async, await, semaphore, deadlock,
    race condition, dependency injection, Jetpack Compose, MVI, clean architecture.
  initial_prompt_sha256: a1b2c3…
  vad:
    engine: silero
    speech_threshold: 0.5
    min_speech_ms: 250
    min_silence_ms: 100
    merge_gap_ms: 300
    speech_pad_ms: 30
  fell_back: false
```

On fallback, `engine: parakeet`, `model:` the Parakeet repo id, `vad:` omitted or
`null` (Parakeet runs no VAD), `fell_back: true`.

**Compatibility guarantee**: `trends/reader.py` requires only `schema_version`,
`attempts`, `generated_by_phase` and reads a fixed key set; `trends/aggregator.py`
reads only `attempts`/`grammar_patterns`. The new `asr:` key is ignored by both —
verified against the current readers. No `schema_version` bump (FR-008).

## C. Static in-repo data

### C.1 Seed lexicon (`asr/seed_lexicon.py`)

A module-level tuple of high-frequency interview/engineering terms (FR-003b),
e.g. `coroutines, threads, mutex, async, await, dispatcher, semaphore, deadlock,
race condition, dependency injection, idempotent, latency, throughput, Jetpack
Compose, MVI, clean architecture, Kubernetes, Redis, Postgres, REST, gRPC`. Pure
constant; no I/O. Source: brief §B.3.7.

### C.2 Accent declaration (`asr/domain_context.py`)

The literal constant: `"The following is technical English spoken with a Persian
accent."` (brief §B.3.7, §B.5).

## D. Reproduction fixture (`tests/fixtures/repro_kotlin_coroutines/`)

| Artifact | Purpose |
|---|---|
| `attempt-*.wav` | original recordings from the failure session (SC-A/SC-B) |
| `hand_transcript.txt` | ground-truth transcription for WER (SC-B) |
| `baseline_parakeet.json` | the previous pipeline's known-bad output (trades/quarantine/…) for the per-token comparison |
| `expected_tokens.yaml` | the tokens that MUST appear ≥4/5 (threads, primitive, IO-bound, CPU-bound, coroutine, shared pool, mutex, dispatcher) |

The repro gate (`@pytest.mark.repro`) skips with a clear message when the `.wav`
files are absent so model-free CI passes; it is only green when run against the
real recordings (FR-010).

## E. State / flow

No new persisted state machine. The session flow is unchanged
(`listening → attempt_n → analyzing → reporting → done`); the only additions are:
(1) building `TranscriptionContext` once at session start, (2) passing it into
each `transcribe`, (3) populating `Session.asr` before `dump`. Engine selection +
load happen once before the loop (research §(c)); replay reuses the resident
engine with no reload.
