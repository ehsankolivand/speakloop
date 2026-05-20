# Feature Specification: ASR Accuracy on Persian-L1 Accented Technical English

**Feature Branch**: `003-asr-l2-accent-accuracy`

**Created**: 2026-05-20

**Status**: Draft

**Input**: User description: "Upgrade speakloop's speech-to-text accuracy on Persian-L1 accented technical English so the LLM grammar analyzer operates on a faithful transcript instead of misheard tokens."

## Clarifications

### Session 2026-05-20

- Q: Does SC-A's "≥4 of 5 occurrences" or the "5/5 consecutive attempts" trust requirement govern the pass/fail gate? → A: Two distinct tests — SC-A's 4/5 gates the original noisy reproduction recordings; the 5/5 gates fresh, clearly-pronounced re-recordings of the named terms. Both must pass.
- Q: How is the per-utterance "technical tokens" set (the SC-B WER denominator) determined? → A: Hand-labeled per utterance during fixture creation from what was actually spoken (not derived from the injected lexicon).
- Q: How does the FR-010 reproducibility gate block, given a public repo and the user's own-voice recordings? → A: Manual local gate — must run green on the user's recordings (kept off-repo) before the feature is declared done; skips cleanly in CI when audio is absent.

## User Scenarios & Testing *(mandatory)*

The user is a Persian-L1 software engineer who practices technical interview answers aloud, in English, every day. The tool records each spoken attempt, transcribes it, and feeds that transcript to a grammar analyzer that writes a session report. Today the transcription layer silently mis-hears domain jargon — a recent Kotlin-coroutines session turned "threads" into "trades", "coroutine" into "quarantine", "shared pool" into "shaded pool" — and every grammar issue flagged in that report was a false positive caused by the mis-hearing, not by the speaker. The stories below restore trust in the transcript before the user invests months of daily practice.

### User Story 1 - The transcript reads back what I actually said (Priority: P1)

As a Persian-L1 engineer answering a technical question, when I clearly pronounce domain terms (Kotlin, coroutine, threads, dispatcher, mutex, Jetpack Compose, MVI), I want the transcript to contain those exact words so that the grammar feedback I receive is about my actual grammar, not about words the tool invented.

**Why this priority**: This is the core defect. Without a faithful transcript every downstream feature (grammar feedback, trends, debrief) is built on corrupted input. Fixing this is the entire reason the feature exists; everything else is supporting robustness.

**Independent Test**: Run the reproduction recordings from the Kotlin-coroutines failure session through the upgraded pipeline and confirm the previously-misheard technical tokens now appear correctly. Can be fully validated against the user's own recordings without any other story shipping.

**Acceptance Scenarios**:

1. **Given** the captured Kotlin-coroutines recordings that previously produced "trades/quarantine/shaded pool", **When** transcribed through the upgraded pipeline, **Then** "threads", "primitive", "IO-bound", "CPU-bound", "coroutine", "shared pool", "mutex", and "dispatcher" each appear correctly in at least 4 of 5 occurrences.
2. **Given** a Phase-C session whose question names a domain (e.g. "Kotlin coroutines"), **When** the session starts, **Then** a per-session domain context is built from the question's vocabulary plus a static engineering-term seed plus an explicit Persian-accent declaration, and that context biases every transcription in the session.
3. **Given** five consecutive *fresh* attempts at the same question with clearly-pronounced technical terms, **When** each is transcribed, **Then** those terms appear correctly in all five transcripts. (This is a distinct, stricter gate from SC-A: it runs on clean re-recordings of clearly-pronounced terms, whereas SC-A's ≥4/5 runs on the original noisy reproduction recordings.)
4. **Given** a completed attempt, **When** the report is written, **Then** the frontmatter records — additively — which engine and model ran and the exact domain context used (or a stable hash of it), so the result is reproducible later.

---

### User Story 2 - My thinking pauses don't become phantom words (Priority: P2)

As a speaker who pauses 11–19 times in a 30-second answer to think, I want silent pauses to never insert fabricated text into my transcript so that I am free to think mid-answer without corrupting the record of what I said.

**Why this priority**: Pause-induced hallucination is the second-largest source of false transcript content and directly degrades grammar feedback. It is independent of the jargon problem and independently testable, but it is only worth fixing once the transcript is otherwise faithful (P1).

**Independent Test**: Record attempts that contain deliberate 2–5 second silent pauses and confirm no tokens appear in the silence regions. Testable without the jargon improvements present.

**Acceptance Scenarios**:

1. **Given** an attempt containing a 2–5 second silent thinking pause, **When** it is transcribed, **Then** the transcript contains no tokens attributable to the silent region.
2. **Given** 20 attempts each containing thinking pauses of 2–5 seconds, **When** all are transcribed, **Then** zero transcripts contain hallucinated text in the silence regions.
3. **Given** an attempt that is entirely silence, **When** transcribed, **Then** the transcript is empty and the session still completes without error.

---

### User Story 3 - The tool never silently regresses, and power users can choose the engine (Priority: P3)

As a daily user about to publish this tool, I want a session to always complete — falling back to the previous engine with a visible note if the new one cannot load — and I want a flag to pick the engine for benchmarking, so that I am never silently downgraded and I can compare engines on my own audio.

**Why this priority**: Robustness and benchmarking. Important for trust over months of use and for publishing, but the feature delivers its core value (P1/P2) even before the fallback and the flag exist.

**Independent Test**: Force the new engine to fail to load and confirm the session completes on the previous engine with one visible fallback line and correct frontmatter; separately, pass the engine flag and confirm the selected engine runs and is recorded.

**Acceptance Scenarios**:

1. **Given** the new engine cannot load (model missing, or out-of-memory while the language model is co-resident), **When** a session runs, **Then** the session completes using the previous engine, one visible line states the fallback occurred, and the frontmatter records the engine actually used.
2. **Given** the engine-selection flag set to the previous engine, **When** a session runs, **Then** the previous engine transcribes the attempts and the frontmatter records it.
3. **Given** any session (default, flagged, or fallen-back), **When** the report is read later, **Then** the recorded engine/model/context fields are sufficient to reproduce or debug that transcript.

---

### Edge Cases

- **Question prompt names no minable domain terms**: the domain context still includes the static engineering-term seed and the Persian-accent declaration, so biasing is never empty.
- **VAD removes all audio** (very quiet mic, speaker far away): the attempt yields an empty transcript and the session completes gracefully, identical to the all-silence case.
- **Accent mis-identified as a non-English language** by automatic language detection: transcription is constrained to English so heavily-accented speech is never transcribed as another language.
- **User explicitly selects the previous engine** via the flag: that engine runs and is recorded; no fallback line is shown because no fallback occurred.
- **New engine loads but exceeds the latency budget** on a long attempt: the transcript is still returned (slower is acceptable when accuracy improves materially); only a hard load failure triggers fallback.
- **Reproduction recordings unavailable**: the reproducibility acceptance gate cannot be marked green; the feature is not considered shippable until the gate runs against real recordings.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST transcribe Phase-C spoken attempts using a default ASR engine that has published accuracy on L2-accented English and exposes a documented contextual-biasing mechanism.
- **FR-002**: The system MUST keep the previous ASR engine reachable at runtime via a selection flag (e.g. `--asr-engine`), for benchmarking and as a fallback. The previous engine MUST NOT be removed.
- **FR-003**: At the start of each Phase-C session, the system MUST construct a domain context string combining (a) domain vocabulary mined from the session's question prompt, (b) a static seed of high-frequency interview/engineering terms (e.g. coroutines, threads, mutex, async/await, dispatcher, Jetpack Compose, MVI, clean architecture, dependency injection), and (c) an explicit declaration that the speaker has a Persian accent.
- **FR-004**: The system MUST inject the per-session domain context into every transcription within that session.
- **FR-005**: The system MUST pre-segment recorded audio with voice-activity detection before transcription, dropping detected silence regions so that only detected speech reaches the ASR.
- **FR-006**: The system MUST NOT emit fabricated tokens originating from silent thinking pauses of up to 5 seconds within an attempt.
- **FR-007**: The system MUST record, additively, in the report frontmatter: the engine that ran, the model identifier, the exact domain context used (or a stable hash of it), and the VAD settings applied.
- **FR-008**: All persisted changes MUST be additive; `schema_version` stays `1`; the existing trends reader MUST keep working unchanged against both old and new reports.
- **FR-009**: If the new engine cannot load for any reason (missing model, out-of-memory with the language model co-resident), the system MUST fall back to the previous engine, complete the session, emit exactly one visible line noting the fallback, and record the engine actually used in the frontmatter. No silent regression is permitted.
- **FR-010**: The system MUST provide a reproducibility test built from the captured Kotlin-coroutines failure session that runs the upgraded pipeline against the original recordings and reports per-token improvement versus the previous pipeline. It is a **manual local acceptance gate**: it MUST run green on the user's own recordings (kept off-repo) before the feature is declared done, and MUST skip cleanly with a clear message when the recordings are absent (so model-free CI stays green). The user's voice recordings MUST NOT be committed to the public repository (Privacy by Design).
- **FR-011**: Engine-specific dependencies MUST be imported only inside their respective engine-wrapper files; no engine-specific import may leak into other modules (preserving the existing swappable-engine boundary).
- **FR-012**: The entire transcription pipeline (VAD, biasing, ASR, any pre-processing) MUST operate fully offline with no cloud or remote services.
- **FR-013**: A 60-second attempt MUST be transcribed end-to-end (VAD + ASR + any pre-processing) in under 5 seconds on the target hardware while the 8-bit-equivalent language model is co-resident.
- **FR-014**: The system MUST operate within memory on the target hardware (M3 Pro 18 GB) with the language model, the TTS engine, and the speech engine co-resident.
- **FR-015**: All user-facing strings introduced by this feature MUST be in English.

### Key Entities *(include if feature involves data)*

- **Domain context (per-session biasing string)**: the text assembled at session start from mined question vocabulary, the static engineering-term seed, and the Persian-accent declaration; consumed by the recognizer and recorded (or hashed) in frontmatter for reproducibility.
- **Transcript**: the text plus word timings produced for one attempt; the unit the grammar analyzer consumes. Its trustworthiness is the feature's central outcome.
- **Report frontmatter (ASR provenance block)**: an additive set of fields recording engine, model, domain context (or hash), and VAD settings, nested so that `schema_version` remains `1` and existing readers are unaffected.
- **Reproduction fixture**: the captured Kotlin-coroutines recordings plus a hand transcript and the previous pipeline's known-bad output, used by the mandatory acceptance gate to measure per-token improvement.
- **ASR engine selection**: the runtime choice (default new engine, explicit flag, or fallback) that determines which engine transcribes and is recorded.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-A**: On the original (noisy) Kotlin-coroutines reproduction recordings, the upgraded pipeline correctly transcribes "threads", "primitive", "IO-bound", "CPU-bound", "coroutine", "shared pool", "mutex", and "dispatcher" in at least 4 of 5 occurrences each. The baseline showed 0 correct. (Distinct from the 5/5 fresh-recording gate in User Story 1, scenario 3.)
- **SC-B**: Across a hand-transcribed 20-utterance Phase-C subset, the upgraded pipeline achieves at least a 30% relative reduction in word error rate on technical tokens compared with the previous pipeline. The "technical tokens" set is hand-labeled per utterance during fixture creation from what was actually spoken — not derived from the injected lexicon — so the metric cannot be inflated by the biasing it measures.
- **SC-C**: Across 20 attempts containing thinking pauses of 2–5 seconds, zero transcripts contain hallucinated text in the silence regions.
- **SC-D**: A 60-second attempt's transcript is returned in under 5 seconds end-to-end on the target hardware while the 8-bit-equivalent language model is co-resident.
- **SC-E**: After the upgrade ships, the user reports (subjectively) that they no longer second-guess whether the transcript is accurate when reading a session report.
- **SC-F**: If the new engine fails to load for any reason, 100% of sessions still complete using the fallback engine, with the fallback clearly indicated in the report.

## Assumptions

- The new default engine is the one recommended in `doc/research_asr_l2_accent.md` (Whisper-large-v3-turbo via an Apple-Silicon-native wrapper, with the contextual-biasing lever the brief documents). The spec itself stays engine-agnostic; the concrete selection lives in the plan.
- This spec deliberately keeps `schema_version` at `1` and adds the ASR provenance fields under a new additive key. This narrows the research brief's suggestion to bump to `schema_version: 2`; the bump is out of scope here and the trends reader must keep parsing both old and new reports.
- Voice-activity-detection pre-segmentation is on by default; a flag may disable it for benchmarking.
- Conditional denoising is out of scope and revisited only if reproduction tests show audio quality — not the model — is the bottleneck.
- The Kotlin-coroutines failure recordings are available (or can be re-captured) to build the reproduction fixture; the acceptance gate depends on having real audio and runs locally (recordings stay off-repo).
- The "technical tokens" measured in SC-B are the domain/jargon terms in each utterance (not all words), hand-labeled per utterance during fixture creation from what was actually spoken; ordinary function words are excluded from that WER metric.
- Target hardware is an M3 Pro with 18 GB unified memory; the latency and memory criteria are stated against that machine.
- Pronunciation assessment, phoneme-level feedback, per-user prompt calibration, smaller-model swaps, and cloud ASR are all explicitly out of scope for this feature.
