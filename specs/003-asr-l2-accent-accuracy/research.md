# Phase 0 Research: ASR Accuracy on Persian-L1 Accented Technical English

Compass document: `doc/research_asr_l2_accent.md`. Every engine, model, and
threshold choice below traces to it (Constitution Principle X). This file records
the **integration-layer** decisions the directive asked for — it does not
re-litigate the engine choice (settled in the brief: Whisper-large-v3-turbo via
`mlx-whisper`, Parakeet kept as fallback).

---

## Decision §(a) — Where domain-context mining lives

**Decision**: **Runtime extraction from the question prompt**, in a pure helper
`asr/domain_context.py`, supplemented by the question's existing optional `tags`.
No content-schema change. Per-question curated vocabulary metadata is **deferred**.

> **As-built (inline implementation decision):** mining was extended to also
> include the question's `ideal_answer` text — the richest in-repo source of the
> exact technical vocabulary the speaker should use. Still 100% offline and
> deterministic; only individual domain terms are extracted, never the prose.
> See `src/speakloop/asr/domain_context.py`.

The domain context (the Whisper `initial_prompt`) is built once per session from
three parts (FR-003):
1. **Mined terms** — extracted at runtime from `Question.question` (and
   `Question.tags` when present): proper-noun / CamelCase / capitalized
   multiword spans ("Kotlin coroutines", "Jetpack Compose", "MVI") plus any
   token that matches the static seed lexicon. Pure string work, deterministic,
   testable without models.
2. **Static seed lexicon** — `asr/seed_lexicon.py`, an in-repo constant of
   high-frequency interview/engineering terms (coroutines, threads, mutex,
   async/await, dispatcher, semaphore, deadlock, race condition, dependency
   injection, Jetpack Compose, MVI, clean architecture, …) from brief §B.3.7.
3. **Accent declaration** — the literal sentence "The following is technical
   English spoken with a Persian accent." (brief §B.3.7, §B.5; SayToWords 2025).

**Rationale**: FR-003 mandates vocabulary "mined from the session's question
prompt itself", so runtime extraction is the requirement, not an option. It works
for every existing question with zero authoring burden, and the question text
already names the domain (the spec's own framing). Reusing `tags` (already in the
`Question` dataclass) gives a curated boost path for free without touching the
content schema or its `schema_version`.

**Alternatives considered**:
- *Per-question `domain_terms:` metadata field* — most precise, but requires a
  `Question`-schema addition and editorial effort per question; the loader's
  `_KNOWN_FIELDS` would need extending and every question file curating. Higher
  cost, and unnecessary because the prompt text already carries the domain.
  Deferred as a future enhancement; the helper is structured so a curated list
  can be merged in later without changing the call site.
- *LLM-extracted keywords* — a second model round-trip, nondeterministic, slower,
  and overkill for naming nouns already present in the prompt. Rejected.

**Validation**: unit tests assert the mined set for the kotlin-coroutines prompt
contains {Kotlin, coroutine, threads, dispatcher, IO-bound, CPU-bound, mutex,
shared pool}; the assembled prompt is hashed (sha256) into provenance so the
exact context is reproducible (FR-007).

---

## Decision §(b) — VAD / silence thresholds and merging

**Decision**: Silero VAD (ONNX) with conservative, hallucination-avoiding
tunables, surfaced as named constants in `asr/vad.py`:

| Tunable | Value | Source / reason |
|---|---|---|
| `speech_threshold` | 0.5 | Silero default; balanced precision/recall |
| `min_speech_ms` | 250 | drop sub-250 ms blips (clicks, breaths) — avoids spurious one-token regions |
| `min_silence_ms` | 100 | a gap ≥100 ms ends a speech region |
| `merge_gap_ms` | 300 | merge adjacent speech regions separated by ≤300 ms — brief §B.3.5 ("merge speech regions separated by ≤300 ms") |
| `speech_pad_ms` | 30 | pad each kept region by 30 ms so onsets/offsets aren't clipped |
| sample rate | 16 kHz mono | required by Silero and Whisper (brief §B.4) |

**No SNR gating in this feature.** The directive asked about "SNR/silence
thresholds for VAD merging", but SNR thresholding belongs to *conditional
denoising* (DeepFilterNet), which the spec puts **out of scope** (revisit only if
reproduction tests show audio quality, not the model, is the bottleneck — brief
§B.4, §B.5). VAD here is a pure speech/non-speech segmenter; the only thresholds
that ship are the silence/merge tunables above. We record the choice explicitly
so a later denoise sprint has a documented seam (`gate on SNR < 15 dB` per brief
§E task 4) but ships nothing now.

**Pipeline shape — preserve the pause timeline**: VAD yields speech regions on
the *original* timeline. We transcribe **per region** and offset each region's
word timings back to its original start, reassembling one `Transcript` whose word
gaps still reflect the real silences. This is the WhisperX approach (Bain et al.,
Interspeech 2023, brief §B.4) and it satisfies two requirements at once:
- silence audio never reaches the ASR → no hallucinated tokens in pauses
  (FR-006, SC-C);
- the real pauses survive as inter-word gaps → `metrics.pauses_count` /
  `mean_pause_ms` / `speech_rate_wpm` stay accurate (no metric regression).

A naive "concatenate speech-only audio then transcribe once" was **rejected**: it
collapses the pause structure the fluency metrics depend on, even though it would
also prevent hallucination.

**Edge cases**: all-silence input → zero regions → empty `Transcript` (matches
the spec's all-silence edge case and the existing empty-transcript path). VAD is
default-on for Whisper; a `--no-vad` style toggle (via `TranscriptionContext`)
exists for benchmarking. Parakeet does not run VAD (RNN-T/TDT does not hallucinate
on silence — `asr/CLAUDE.md`, `doc/research_asr.md`), so VAD is applied in the
Whisper engine path only.

**Rationale**: defaults are conservative (favor keeping speech over aggressive
trimming) because the failure we are fixing is *fabricated* tokens, and the worst
VAD failure mode (clipping real speech) would create new errors. 300 ms merge
matches the brief; 30 ms padding is the standard guard against onset clipping.

**Validation**: silence-padded fixtures (2–5 s pauses) assert zero tokens in the
silence windows across 20 clips (SC-C); a clip with a real mid-sentence pause
asserts the pause still appears in word-gap metrics.

---

## Decision §(c) — Memoizing models across sessions for the 5 s budget under Qwen co-residence

**Decision**: **Construct the engine once and inject it** (the pattern already in
`cli/practice.py`), and have `WhisperMLXEngine` hold its loaded model in instance
state (lazy on first `transcribe`, reused thereafter). VAD's ONNX session is
likewise loaded once into the engine. No reload per attempt, per question, or per
replay.

Concretely:
- `cli/practice.py` calls `asr.build_engine(name)` **before** the practice loop
  and injects the single instance into every `coordinator.run_session(...)` call
  — exactly how `ParakeetEngine` is constructed once today (practice.py:290).
- `WhisperMLXEngine._load()` mirrors `ParakeetEngine._load()`: load once, cache on
  `self._model`, return the cached handle on every later call. `mlx_whisper` also
  keeps its own module-level model cache keyed by repo path, so even an
  accidental second engine instance would not re-read weights from disk; the
  instance cache is the primary mechanism and the module cache is belt-and-braces.
- First load (cold) happens during setup, **before** attempt 1 — outside the
  per-attempt timing the 5 s budget measures. Every timed transcription runs
  against a warm model.

**Why this meets SC-D under Qwen co-residence**:
- Warm large-v3-turbo runs ≈270× real-time on M-series (brief §A, §B.1: 1 h audio
  in ~13 s), so a 60 s clip transcribes in well under 1 s; VAD adds tens of ms.
  The 5 s budget has large headroom even with Qwen resident.
- Memory: Whisper-turbo (~1.6 GB) + Qwen-8B-4bit (~4.6 GB) + Kokoro (~0.2 GB) +
  Silero (tiny) + runtime ≈ ~7 GB resident, safely under 18 GB (brief §A, §E.1).
  Both share the MLX unified-memory pool, so we keep all engines resident rather
  than thrashing load/free between phases.

**Alternatives considered**:
- *Load Whisper per attempt and free after* — guarantees minimal peak RAM but
  blows the 5 s budget (cold load every attempt) and adds latency to every
  replay. Rejected; RAM headroom makes it unnecessary.
- *Preload at import / eager global singleton* — would slow `speakloop --help`
  and any non-practice command (violates Principle VIII, "`--help` model-free").
  Rejected in favor of lazy-on-first-use within a once-constructed instance.
- *Free Whisper before the Qwen grammar pass* — considered as an OOM mitigation
  but unnecessary at ~7 GB; kept as a documented fallback lever in the risk
  register (and the brief's: switch to `distil-large-v3` if OOM ever appears).

**Validation**: an integration test asserts `_load()` is invoked once across
three attempts + one replay (call-count on a stubbed loader); a timing assertion
(warm, stubbed transcription) guards against accidental reloads in the hot path.

---

## Supporting decisions

### S1 — Protocol extension for domain context (Principle V-safe)

`ASREngine.transcribe` gains one **optional keyword**:
`transcribe(self, wav_path, *, context: TranscriptionContext | None = None) -> Transcript`.
`TranscriptionContext` (a frozen dataclass in `asr/interface.py`) carries
`initial_prompt: str | None`, `initial_prompt_sha256: str`, and `use_vad: bool`.
`ParakeetEngine` accepts and ignores it (signature compatibility only);
`WhisperMLXEngine` consumes `initial_prompt` and `use_vad`. This is additive and
backward compatible — existing callers passing no context are unaffected, and the
Protocol shape (one method, `Transcript` return) is preserved. Matches brief §B.3
("Add `initial_prompt` … to the Protocol").

`mlx_whisper.transcribe` is called with
`initial_prompt=<context>, condition_on_previous_text=False, language="en",
word_timestamps=True` (brief §B.3.4): `condition_on_previous_text=False` prevents
the short-clip context-drift hallucination; forced `language="en"` stops accented
speech being mis-detected as Persian (brief §B.5 open question 4 — we resolve it
to *forced English*).

### S2 — Engine selection and graceful fallback (FR-009, SC-F)

`asr/selection.py` exposes `build_engine(name: str | None) -> EngineSelection`.
It constructs the requested engine (default Whisper) and **probes the load
eagerly** (calls the engine's `ensure_loaded()`), so a missing model or OOM is
detected before attempt 1. On failure it returns Parakeet instead, sets
`fell_back=True` and a human-readable reason, and the CLI prints exactly one
English line ("ASR: Whisper unavailable (<reason>); falling back to Parakeet.").
`EngineSelection` also carries the resolved engine name + model id for provenance.
`selection.py` imports the two wrapper classes (both inside `asr/`) but no
third-party engine package itself — Principle V intact.

`--asr-engine {whisper,parakeet}` selects explicitly; an explicit `parakeet`
choice is honored with no fallback line (no fallback occurred — spec edge case).

### S3 — Frontmatter provenance, additive on schema_version 1 (FR-007, FR-008)

A single additive top-level `asr:` mapping is emitted by `frontmatter.dump` only
when present (same pattern as `cross_attempt_narrative`/`top_priority` added in
002). Fields: `engine`, `model`, `initial_prompt_sha256`, `initial_prompt`
(verbatim, for debuggability), `vad` (the tunables that ran, or `disabled`),
`fell_back` (bool). `schema_version` stays **1**. Verified safe: `trends/reader.py`
reads a fixed key set (`schema_version`, `attempts`, `grammar_patterns`,
`generated_by_phase`, …) and ignores unknown keys; `trends/aggregator.py` reads
only `attempts`/`grammar_patterns`. This narrows the brief's suggested
`schema_version: 2` bump (brief §B.3.8, §C.4) per the spec's explicit scope.

### S4 — Installer manifest

Add `WHISPER_LARGE_V3_TURBO = Model(hf_repo_id="mlx-community/whisper-large-v3-turbo",
expected_size_bytes≈1.6 GB)`; include it in `PHASE_C_MODELS` (and Phase-B, since
attempts need ASR). Parakeet stays in the manifest as the fallback. Reuses the
existing resumable downloader + validator (Principle VI). Exact byte size is
confirmed against the HF tree at implementation time.

### S5 — Dependencies (closed set)

`mlx-whisper`, `silero-vad`, `onnxruntime` only (directive constraint). All MIT.
Pin to specific versions in `pyproject.toml` per the brief's API-drift risk
(§E.1): `mlx-whisper`'s `word_timestamps` signature has changed across releases.
`numpy`/`soundfile` (already deps) handle audio I/O and resampling to 16 kHz mono.

---

## Open items the engineer verifies on their own audio (from brief §B.5)

1. Confirm the failure is Parakeet-specific by running the same recordings through
   Whisper with/without `initial_prompt` (the repro gate does exactly this).
2. Measure ≥30% relative technical-token WER reduction on the 20-utterance subset
   (SC-B) — requires hand transcripts in the fixture.
3. Re-confirm peak RAM with Qwen co-resident on the actual M3 Pro (SC-D / risk).
4. (Resolved here) `language` is forced to `"en"`, not auto-detected.

---

## Known limitations

### KL1 — Stub-based tests can't catch transitive-dependency breakage on first live run

The unit/integration suite stubs `silero_vad` / `mlx_whisper` (Development
Guidelines: no live model calls), which is correct for fast deterministic CI but
means the suite cannot see how the *real* engine stack resolves its own
transitive dependencies. This bit us on the first live session: `silero-vad` 6.x
pulls `torchaudio>=2.11`, whose audio I/O now routes through `torchcodec` (an
unbundled native dep), crashing `vad.segment` on the first real VAD call — while
every stubbed test stayed green. Mitigations: (a) `pyproject` pins
`torchaudio<2.9` to keep the in-tree decode path (documented in `asr/vad.py` and
`asr/CLAUDE.md`); (b) a thin `@pytest.mark.live_asr` smoke test
(`tests/integration/test_vad_live_smoke.py`) runs the real silero + real audio
I/O on a tiny committed WAV, skipping when the deps are absent, so this class of
regression is caught next time a dependency is bumped. The general lesson: a
mock-only test boundary leaves the real dependency-resolution path unexercised;
keep at least one opt-in live smoke test per engine that performs real I/O.

### KL2 — Whisper repetition-loop on low-confidence decodes

The first live session hit a known Whisper/mlx-whisper failure mode: attempt 3
(15.8 s of speech) decoded to 245 words that were the token "Come" repeated 250+
times — a low-decoder-confidence repetition loop. Fix (in
`asr/whisper_mlx_engine.py`, both the whole-clip and per-VAD-region paths): pass
the documented anti-hallucination decoding flags to `mlx_whisper.transcribe` —
`temperature=(0.0, 0.2, 0.4, 0.6, 0.8, 1.0)` (temperature fallback retries a
failed decode at the next-higher temperature), `compression_ratio_threshold=2.4`
(the signal that catches repetition specifically — repetitive text compresses far
better than natural speech), `logprob_threshold=-1.0`, and
`no_speech_threshold=0.6` (OpenAI whisper README; discussions in §B.4). As a
post-hoc safety net for the rare case a degenerate decode survives the
temperature fallback, the engine recomputes the gzip compression ratio of the
returned text and, if it exceeds 2.4, drops that transcript (whole clip) or that
speech region (VAD path) and logs a warning rather than feeding garbled
repetition to the grammar analyzer. Covered by
`tests/unit/asr/test_whisper_repetition_guard.py`.
