# speakloop v2 Research Brief — ASR Accuracy on Persian-L1 English and a Phoneme/Prosody-Aware Feedback Architecture

> **AS-BUILT NOTE (003-asr-l2-accent-accuracy, shipped).** This is the research
> compass; two proposals below were intentionally narrowed by the spec and did
> NOT ship: (1) `schema_version` STAYS **1** — ASR provenance is an additive
> top-level `asr:` key, not a v2 bump; (2) the conditional **DeepFilterNet
> denoiser is deferred / out of scope** (no `asr/denoise.py`). As built, domain
> biasing also mines the question's *ideal answer* (not just the prompt). See
> `specs/003-asr-l2-accent-accuracy/spec.md` for the authoritative scope.
>
> **LLM-line update (post-2026-05-25).** Every memory-math reference below to
> "Qwen3-8B-4bit ≈4.5 GB" reflects the LLM at the time of this brief. The shipped
> LLM is now **`mlx-community/Qwen3-14B-4bit`** (~8 GB on disk, ~9–10 GB resident
> with KV cache); recompute the resident-RAM totals accordingly. The codified
> M3-Pro-18-GB budget rule lives in `doc/research_llm.md` (Update — 2026-05-25):
> LLM resident ceiling ≈10 GB after subtracting macOS + Python overhead and the
> resident ASR encoder.

## A. Executive Summary

**ASR recommendation.** Replace Parakeet-TDT-0.6b-v3 (the speakloop v1 ASR) with **Whisper-large-v3-turbo via `mlx-whisper`**, kept behind speakloop's existing `ASREngine` Protocol so Parakeet remains as a fallback. The single hardest piece of evidence: in the only published controlled study on L2-ARCTIC accented English that we located, Whisper-large-v3 achieves a mean Match Error Rate of 5.4% across 24 non-native speakers from six L1 backgrounds (Arabic, Chinese, Hindi, Korean, Spanish, Vietnamese) — approaching human accuracy (Goodwin & Lee, arXiv:2503.06924, Mar 2025). Parakeet-TDT has *not* been benchmarked on L2-ARCTIC in any source we located; its strengths (1.69% WER on LibriSpeech test-clean and 3.70% on test-other at RTFx 3380, per NVIDIA's `nvidia/parakeet-tdt-0.6b-v2` HF model card) are on clean, native-English audio. The specific symptoms speakloop is seeing — "coroutines → coroutine permittive", "shared → shaded", "threads → threats" — are consistent with the transducer behaviour of Parakeet on out-of-distribution accents, where the duration head over-commits and downstream substitutions cascade. Whisper's encoder–decoder + `initial_prompt` biasing gives a direct, offline lever to inject technical vocabulary ("coroutines, threads, mutex, async, asyncio, Kubernetes…") that Parakeet does not expose. The latency cost is small on an M3 Pro 18 GB: per llimllib.notes (10-run hyperfine benchmark, Jan 09 2026), `mlx_whisper` with `whisper-large-v3-turbo` transcribed a 1 h MLK speech in **13.135 s ± 0.280 s versus 26.704 s ± 0.625 s for whisper.cpp — a 2.03 ± 0.06× speed-up**, i.e. ≈270× real-time, well inside the 5 s per-attempt budget for the 30–60 s utterances speakloop produces. Pair the engine swap with **Silero VAD pre-segmentation** and a conditional **DeepFilterNet** denoiser (skip when SNR is already high — over-enhancement reduces WER) and an `initial_prompt` containing the interview-domain lexicon plus the literal sentence "The following is technical English spoken with a Persian accent."

**Pronunciation feedback architecture.** Add a parallel, text-dependent pronunciation pass that runs after Whisper but does not block the report: (1) generate the canonical IPA phoneme string from the **reference prompt text** with `g2p_en` (Apache 2.0, CMUdict-based) and **`epitran`** (MIT-Modern-Variant) as a tie-breaker; (2) force-align the user's audio to that canonical sequence using **`facebook/wav2vec2-lv-60-espeak-cv-ft`** (Apache 2.0, ~392 eSpeak/IPA phoneme classes, Xu, Baevski & Auli, arXiv:2109.11680, "Simple and Effective Zero-shot Cross-lingual Phoneme Recognition") via CTC alignment with `torchaudio.functional.forced_align`; (3) compute a **CTC-GOP score per canonical phoneme** as `log p(canonical) − log max p(competing)` at the aligned frames, exactly the segmentation-free GOP formulation of Sudo & Shinoda (arXiv:2507.16838, 2025); (4) overlay Persian-L1 priors — for the 12 highest-impact transfer phonemes (/θ ð w ŋ ɪ æ ʌ ɜː ɑː ɒ ʊ ɹ/), bias the threshold and emit a specific Persian-L1 coaching line. Defer end-to-end MDD models (which need labelled L2 training data) and full Transformer-GOP (which needs Kaldi/HMM senones) to v3. Ship word stress (CMUdict stress marker × realized vowel-duration × RMS ratio) in v2; ship intonation and PVI in v3. This is precisely the layered design ELSA Speak documents publicly in its official Medium post "Discover Your ELSA Score" by ElsaSpeak: "we identified five skills to evaluate with Your ELSA Score. These five skills are key aspects of English speaking proficiency and include: Segmental skills (pronouncing individual phonemes), Prosodic skills (also called suprasegmental features and including intonation, world stress, and fluency)" — beginners get segmental, advanced learners get suprasegmental.

**Trade-offs the engineer must accept.** (1) Whisper is slower per token than Parakeet, but on the M3 Pro 18 GB this still leaves >50× real-time headroom; budget is not the constraint, RAM is (large-v3-turbo fp16 ≈1.5–2 GB plus the wav2vec2 phoneme model ≈1.2 GB plus Qwen3-8B-4bit ≈4.5 GB plus Kokoro ≈300 MB ⇒ ~7.5 GB resident, safely under 18 GB). (2) `wav2vec2-lv-60-espeak-cv-ft` runs on **PyTorch-MPS, not MLX** — Apple Silicon supports it, but it is slower than MLX-native models; expect ~0.3–0.6 s of alignment per 10 s utterance, acceptable. (3) GOP scores are noisy at the phoneme level; per the GOPT paper (Gong, Chen, Chu, Chang & Glass, ICASSP 2022, MIT CSAIL) and Speechocean762 distribution analyses, phoneme-level assessment is the most challenging granularity and labels cluster at the upper end — meaning **GOP should be used for *trend detection and outlier flagging*, not absolute "wrong/right" calls**. (4) `phonemizer` + `espeak-ng` is GPL; do not link it into a redistribution. We deliberately avoid it: `g2p_en` (Apache 2.0) handles English G2P, `misaki` (already shipped with kokoro-mlx) handles G2P inside Kokoro, and `epitran` (MIT-Modern-Variant) handles Persian/IPA conversion if you ever want to display L1 contrasts.

---

## B. Part A — ASR Upgrade

### B.1 Comparison table

| Engine (model) | Apple Silicon path | License | Word timestamps | Token confidences | L2/accented WER evidence | Latency on M3 Pro 18 GB | Dep footprint |
|---|---|---|---|---|---|---|---|
| **Whisper-large-v3-turbo** (809 M) | `mlx-whisper` (MIT pkg, Apple MLX) | MIT (weights) | yes (segment + `word_timestamps=True` via DTW heads) | per-segment `avg_logprob`, per-token logprobs | **L2-ARCTIC: 5.4% MER for large-v3 across 24 non-native speakers, 6 L1s** (Goodwin & Lee, arXiv:2503.06924, Mar 2025); S&I Corpus 2025 (L2 learners): Whisper-large-v3-turbo fine-tune 5.5% WER (arXiv:2506.04076) | **13.135 s ± 0.280 s for 1 h audio (≈270× RT)** — llimllib.notes hyperfine, 10 runs, Jan 2026 | mlx-whisper, mlx ≥0.22; weights ~1.5 GB |
| Whisper-large-v3 (1.55 B) | `mlx-whisper` | MIT | yes | yes | as above, but slightly slower | ~26 s/h (whisper.cpp baseline) | weights ~2.9 GB |
| **Parakeet-TDT-0.6b-v3** (current) | `parakeet-mlx` (Apache, Senstella) | CC-BY-4.0 (NVIDIA weights) | native, very precise (TDT duration head) | per-token logprobs in beam decoding | No L2-ARCTIC number found; 9.7% WER avg on FLEURS+CoVoST+MLS 24-lang multilingual vs Whisper-large-v3 9.9% (NVIDIA paper arXiv:2509.14128, Sep 2025) | ~53 s for 1 h podcast on M-series (Simon Willison, Nov 14 2025) | weights ~2.5 GB |
| Parakeet-TDT-0.6b-v2 (English-only) | `parakeet-mlx` | CC-BY-4.0 | native | yes | **1.69% WER LibriSpeech test-clean, 3.70% test-other, RTFx 3380 @ batch 128** per `nvidia/parakeet-tdt-0.6b-v2` HF model-index | even faster than v3 (English-only specialist) | ~2.5 GB |
| Canary-1B-v2 (NVIDIA) | NeMo-only currently; no production MLX port | CC-BY-4.0 | NFA segment-level | logprobs | beats whisper-large-v3 on HF Open ASR avg; RTFx 749 (paper) | not deployable in MLX today | NeMo (large), MPS unstable |
| distil-whisper-large-v3 | `mlx-whisper`, `lightning-whisper-mlx` | MIT | yes | yes | English-only. Per `distil-whisper/distil-large-v3` HF model card: **6.3× faster than large-v3**; short-form WER **9.7% vs large-v3 8.4% (+1.3 pp)**; sequential long-form **10.8% vs 10.0%**; chunked long-form **10.9% vs 11.0%** (actually 0.1 pp better). 756 M params | 36× RT on M1 Pro (whisper-bench) | small |
| `lightning-whisper-mlx` (Aljadery) | MLX, batched | MIT | yes | yes | wraps Whisper weights; vendor claims 10× whisper.cpp | 36× RT measured | small |
| WhisperKit (Argmax) | Swift/CoreML — **disqualified** (not Python CLI) | MIT | yes | yes | n/a | Swift only | n/a |
| FluidAudio (Parakeet on Neural Engine) | Swift/CoreML — **disqualified** (not Python CLI) | Apache 2.0 (SDK) | yes | yes | 2.5% vs 6.3% (vendor internal, MacParakeet blog 2026) | NE: ~155× RT M1, ~300× RT M-series | Swift only |
| SenseVoice-Small | ONNX/MLX ports | model card terms | yes | yes | strong multilingual; no Persian-accent number | comparable | medium |

### B.2 Winner and runner-up

**Winner: Whisper-large-v3-turbo via `mlx-whisper`.** The decision rests on four points:
1. The **only direct L2-ARCTIC number we found** is for Whisper-large-v3 at 5.4% MER (Goodwin & Lee 2025).
2. Whisper exposes `initial_prompt`, an officially documented contextual-biasing lever shown to reduce WER on rare/technical vocabulary: "the Whisper model offers an optional parameter, initial-prompt, during decoding to use fictitious prompts that guide model outputs" (Pusateri et al., arXiv:2410.18363, Oct 2024).
3. `mlx-whisper` is the fastest mainstream Whisper port on M-series, measured at **2.03 ± 0.06× whisper.cpp** in a 10-run hyperfine benchmark (llimllib.notes, Jan 2026), with `word_timestamps`, segment confidences, and `initial_prompt` injection all exposed.
4. Whisper's hallucination-on-silence failure mode is well known and is the exact problem WhisperX's Silero-VAD pre-segmentation was designed to mitigate (Bain et al., Interspeech 2023).

**Runner-up: keep Parakeet-TDT-0.6b-v3 behind a runtime flag for clean, native-English benchmarking and as a sanity baseline.** Parakeet's TDT duration head still gives the most precise word boundaries we have, which can complement the pronunciation pipeline's word-level slicing. Keep `parakeet-mlx ≥ 0.5.1`.

### B.3 Concrete migration path

1. `uv add mlx-whisper` (the convenience PyPI distribution; mirrors Apple's `mlx-examples/whisper`). Pin `mlx >= 0.22`. Keep `parakeet-mlx` installed.
2. In `asr/CLAUDE.md`, document that the default engine is now `WhisperMLXEngine` (model: `mlx-community/whisper-large-v3-turbo`), with `ParakeetMLXEngine` as an `--engine parakeet` opt-in.
3. The `ASREngine` Protocol (assumed: `transcribe(audio_path) -> ASRResult` with `text`, `words: List[Word]`, `tokens: List[Token]`, optional `confidences`) is preserved. Add `initial_prompt: str | None = None` and `vad_segments: list[tuple[float,float]] | None = None`.
4. New module `asr/whisper_mlx_engine.py` wraps:
   `mlx_whisper.transcribe(path, path_or_hf_repo="mlx-community/whisper-large-v3-turbo", word_timestamps=True, condition_on_previous_text=False, initial_prompt=<domain_prompt>, language="en")`.
   Set `condition_on_previous_text=False` for short interview-drill clips — this prevents the well-known context-drift failure mode on short utterances.
5. New module `asr/vad.py` wraps `silero-vad` (MIT, ONNX, version 6.2.x confirmed in production stacks per the big-plump-bird ASR pipeline plan, Feb 2026). Resample to 16 kHz mono, run VAD, merge speech regions separated by ≤300 ms, feed only speech to Whisper.
6. New module `asr/denoise.py` wraps DeepFilterNet 0.5.6 (MIT), gated by `SNR_dB < 15` heuristic — apply only when audio is genuinely noisy. The principle is documented in the same big-plump-bird plan: "enhancement must be conditional and conservative, because over-enhancement can reduce ASR accuracy."
7. Domain prompt construction at `Phase-C` session start, joining (a) the 4/3/2 drill's source prompt vocabulary, (b) a static seed lexicon (`coroutines, mutex, threads, async, await, Kubernetes, Redis, Postgres, REST, gRPC, latency, throughput, semaphore, deadlock, race condition, dependency injection, idempotent`), and (c) the literal sentence `The speaker has a Persian accent.` (a Persian analogue of the British-accent example documented in SayToWords' Whisper accuracy guide, 2025).
8. Frontmatter: `asr.engine`, `asr.model`, `asr.initial_prompt_sha256`, `asr.vad`, `asr.denoise`. Bump to `schema_version: 2`.

### B.4 Pre-processing that moves the needle

| Step | Evidence | Effort |
|---|---|---|
| **16 kHz mono** | required by all wav2vec2 / Whisper / Parakeet models | S |
| **Silero VAD segmentation** | "VAD preprocessing, reduces hallucination & batching with no WER degradation" (WhisperX README); Bain et al., Interspeech 2023 | S |
| **Conditional DeepFilterNet** (gate on SNR) | Kinoshita, Ochiai, Delcroix & Nakatani (NTT Communication Science Laboratories), arXiv:2003.03998: "providing more than 30 % relative word error reduction over a strong ASR back-end on the real evaluation data of the single-channel track of the CHiME-4 dataset" — but only when noise is real | M |
| **`initial_prompt` with domain lexicon + accent declaration** | Pusateri et al. arXiv:2410.18363; Ranjan et al. arXiv:2502.11572 (rare-word recognition via Whisper prompting); SayToWords 2025 | S |
| **`condition_on_previous_text=False`** for short clips | known Whisper hallucination mode | S |
| Optional: kNN rescoring for speaker adaptation | "kNN For Whisper And Its Effect On Bias And Speaker Adaptation", arXiv:2410.18850 | L — defer |

### B.5 Open questions the engineer must verify with their own audio

1. Confirm the failure mode is *Parakeet-TDT-specific*: run the same Phase-C audio through `mlx-whisper large-v3-turbo` with and without `initial_prompt`. If Whisper also confuses "shared/shaded", the problem is acoustic (mic/SNR), not the model.
2. Measure WER on a hand-transcribed 20-utterance Phase-C subset before and after the migration. Target: **≥30% relative WER reduction on technical tokens**.
3. Verify large-v3-turbo memory ceiling on M3 Pro 18 GB while Qwen3-8B-4bit is also resident — both share the unified memory pool.
4. Decide whether to keep `language="en"` forced or let Whisper auto-detect (auto-detect can mis-identify heavily accented speech as Persian).

---

## C. Part B — Pronunciation Feedback Architecture

### C.1 Pipeline

```
Phase-C prompt text ──► (1) g2p_en → ARPAbet + stress ──┐
                                                         ├─► (3) canonical IPA phone sequence
                       ───► (2) epitran (en-Latn) → IPA ─┘
                                                                  │
mic ──► (A) 16 kHz mono ──► (B) Silero VAD ──► (C) [Whisper-MLX]──┼──► transcript + word timings
                                                                  │
                                                          (D) wav2vec2-lv-60-espeak-cv-ft
                                                              CTC forced alignment over (3)
                                                                  │
                                                                  ▼
                                                  (E) per-phone log-probs at aligned frames
                                                                  │
                                                                  ▼
                                                  (F) CTC-GOP = log p(canonical) - log max p(competing)
                                                                  │
                                                                  ▼
                                                  (G) Persian-L1 prior overlay (12 priority phones)
                                                                  │
                                                                  ▼
                                                  (H) word-stress check
                                                                  │
                                                                  ▼
                                                  (I) markdown report renderer (schema_version: 2)
```

### C.2 Components — recommended OSS implementations

| Stage | Choice | License | Why |
|---|---|---|---|
| (1) G2P English | `g2p_en` (Park & Kim, 2019) | **Apache 2.0** | Pure Python, CMUdict + neural fallback, fast, English-only |
| (2) IPA fallback / Persian display | `epitran` | **MIT-Modern-Variant** (confirmed in repo) | 61 languages incl. Persian (`fas-Arab`); rule-based deterministic |
| (3) Canonical phone sequence | combine (1) and (2), with `g2p_en` authoritative for English | — | CMUdict supplies 0/1/2 stress markers needed in (H) |
| (D) Forced aligner | **`facebook/wav2vec2-lv-60-espeak-cv-ft`** (Xu, Baevski & Auli, arXiv:2109.11680) | **Apache 2.0** | ~392 IPA/eSpeak phoneme classes (re-verify with `Wav2Vec2ForCTC.from_pretrained(...).config.vocab_size` on install); **zero-shot cross-lingual phoneme recognition** — robust to L2 speech because it was trained on multilingual phonetic labels; runs via `Wav2Vec2ForCTC.from_pretrained()` on PyTorch-MPS |
| (D-alt) | `charsiu/en_w2v2_fc_10ms` (Zhu et al., arXiv:2110.03876) | **MIT** (per repo `LICENSE`; HF page lacks a license tag) | 10 ms frame resolution; English-specific. **Note:** the Charsiu paper does NOT explicitly evaluate L2/accented speech; it is trained on Common Voice English + LibriSpeech, which contain accent diversity but no L2 benchmark is published. |
| Alignment algorithm | `torchaudio.functional.forced_align` | BSD | Already in torchaudio; works on PyTorch-MPS |
| (F) GOP | **CTC-GOP**, segmentation-free formulation (Sudo & Shinoda, arXiv:2507.16838, 2025) | — | Avoids HMM/Kaldi; standard "log-posterior of canonical phone minus max over competitors" computed directly on CTC log-probs |
| (G) L1 prior overlay | hand-coded table in `pronunciation/persian_l1.py` | speakloop code | See Part C |
| (H) Word stress | librosa (ISC) + CMUdict 0/1/2 stress markers | ISC + public domain | computes vowel duration × RMS ratio of stressed:unstressed; no GPL praat required |
| (I) Markdown render | extend existing speakloop report renderer | — | additive only — schema_version 2 |

**Tools explicitly rejected / flagged:**
- **Montreal Forced Aligner (MFA)** — works on Apple Silicon via `conda-forge` for arm64, but pulls Kaldi + PostgreSQL/`mfa server init` (per MFA 3.x docs) and adds a heavy operational footprint vs. one HF model. License is MIT but operational tax is wrong for a per-attempt CLI loop. **Reject for v2.**
- **`phonemizer` (Bernard et al.)** — **GPL via `espeak-ng`** dependency. Yellow-flag per the brief's constraints. Reject — `g2p_en` + `epitran` cover the need.
- **`praat-parselmouth`** — **GPL.** Reject for prosody; use librosa (ISC) for F0 (`librosa.yin`), intensity (RMS), duration.
- **NVIDIA NeMo on MPS** — many recipes assume CUDA-only ops. Reject.
- **SpeechBrain GOP recipes** — work in principle on PyTorch-MPS, but the canonical recipe is Kaldi-based. Reject for v2.

### C.3 The feedback shape the user sees

Per-attempt Markdown excerpt (added under existing `## Fluency` / `## Grammar` sections):

```markdown
## Pronunciation (segmental)

Sentence: "I refactored the function into a coroutine to avoid blocking the event loop."

Per-phone score (CTC-GOP; lower is worse; threshold for Persian-L1 priority phones tightened by 0.5):

| Word        | Canonical IPA      | Realized (top alt) | GOP   | Flag                                              |
|-------------|--------------------|--------------------|-------|---------------------------------------------------|
| refactored  | ɹiˈfæktɚd          | ɹiˈfæktɚd          | -0.21 | ok                                                |
| **the**     | ð ə                | **d ə**            | -3.84 | **/ð/ → /d/** — Persian L1 substitution (priority) |
| function    | ˈfʌŋkʃən           | ˈfʌnkʃən           | -1.92 | **/ŋ/ → /n+k/** — Persian L1 (priority)            |
| into        | ˈɪntu              | ˈintu              | -2.10 | /ɪ/ → /i/ — KIT/FLEECE merger (priority)          |
| coroutine   | koʊˈɹuːtin         | koʊˈɹuːtin         | -0.40 | ok                                                |
| event       | ɪˈvɛnt             | eˈvɛnt             | -1.50 | /ɪ/ → /e/                                         |
| loop        | luːp               | lup                | -0.80 | duration short (vowel-length under-shoot)         |

## Pronunciation (word stress)

| Word        | CMU stress  | Realized      | Note                                              |
|-------------|-------------|---------------|---------------------------------------------------|
| refactored  | re-FAC-tored | re-fac-TO-red | **Stress on wrong syllable** (Persian default = final, EN = penultimate) |

## Coaching (Persian-L1, 3 most actionable)

1. **/ð/ in "the", "this", "they"** — Persian has no voiced interdental fricative; you used /d/. Place tongue tip lightly between the teeth, voice it. Drill: "this then that they there those" × 3.
2. **/ŋ/ in "function", "ring", "thing"** — Persian /ŋ/ exists only before /k g/; in English it stands alone. Practice holding the velar nasal without the /k/: "sing-sing-sing" (not "sin-k").
3. **Word stress in "refactored"** — English stress is lexical; Persian stress is largely final and predictable (Yarmohammadi 2005). For 3+-syllable English verbs ending in -ed, stress falls on the syllable before -ed: re-FAC-tored, not re-fac-TORED.
```

### C.4 schema_version: 2 frontmatter additions (additive only)

```yaml
---
schema_version: 2
asr:
  engine: whisper-mlx
  model: mlx-community/whisper-large-v3-turbo
  initial_prompt_sha256: a1b2c3...
  vad: silero-v6.2
  denoise: deepfilternet-0.5.6 (skipped, snr=22.4dB)
pronunciation:
  enabled: true
  aligner_model: facebook/wav2vec2-lv-60-espeak-cv-ft
  g2p: g2p_en==0.4.x
  gop_method: ctc-gop  # per arXiv:2507.16838
  l1_overlay: persian
  per_phone:
    - {word: the, canonical: "ð ə", realized: "d ə", gop: -3.84, flag: th-stopping-voiced}
    - {word: function, canonical: "ˈfʌŋkʃən", realized: "ˈfʌnkʃən", gop: -1.92, flag: ng-cluster}
  stress_errors:
    - {word: refactored, expected: 1, observed: 2}
  utterance_scores:
    accuracy_phone_mean_gop: -1.20
    stress_accuracy_pct: 0.78
    suprasegmental: null  # populated in v3
---
```

All v1 fields are untouched; v1 readers still parse cleanly because new fields live under new top-level keys.

### C.5 Advanced layer — sprint-2 vs v3

- **Sprint 2 (this brief):** segmental CTC-GOP + Persian-L1 overlay + word-stress check. This is the minimum that gives the user something *actionable per attempt*.
- **v3 (deferred):** intonation contour (F0 via `librosa.yin`, normalize per-speaker, compute final-rise vs final-fall), rhythm (Pairwise Variability Index, PVI — Grabe & Low 2002; Persian PVI is intermediate between stress-timed and syllable-timed per Abolhasanizadeh & Zaiim 2015 and follow-on Iranian rhythm literature), and **Transformer-GOP / GOPT-style multi-aspect head** (Gong, Chen, Chu, Chang & Glass, ICASSP 2022, MIT CSAIL) trained on speechocean762 (Mandarin L2 — known mismatch, document the limitation). Cloud-augmented v3 with ELSA-style API would dominate but is out of scope per the brief's constraints.

---

## D. Part C — Persian-L1 Pronunciation Pattern Catalog (seed for speakloop)

Primary sources for this catalog: Yarmohammadi (1969, 2002, 2005) "A Contrastive Phonological Analysis of English and Persian"; Moradi & Chen (2018) "A Contrastive Analysis of Persian and English Vowels and Consonants" (lartis.sk archive); IJLTER (2015) "A Study of Consonant Clusters in an EFL Context"; "Optimality Theoretic Account of Acquisition of Consonant Clusters of English Syllables by Persian EFL Learners" (academia.edu); "Difficulties of Persian Learners of English in Pronouncing Some English Consonant Clusters" (ResearchGate); "An Investigation on Pronunciation of Language Learners of English in Persian Background" (Sicola/Yarmohammadi-derived); Wikipedia "Persian phonology" (cites Mahootian, Windfuhr).

Rank order is **frequency × intelligibility impact**, with priority 1 = ship in seed catalog v1.

| # | English target | Persian realization | Transfer reason | Detection in speakloop | Coaching that works |
|---|---|---|---|---|---|
| 1 | **/θ/** (think, three) | → **/t/** or **/s/** | Persian lacks voiceless interdental fricative | CTC-GOP at /θ/ with `realized ∈ {t,s}`; threshold tightened by 0.5 | Tongue tip between teeth, no voicing; minimal pairs "thin/tin", "thick/sick" |
| 2 | **/ð/** (the, this, they, those) | → **/d/** or **/z/** | same — no voiced interdental | same detection logic | "this/dis" minimal pairs; word-initial /ð/ is in 7 of the 100 most frequent English words — high intelligibility impact |
| 3 | **/w/** (we, want, were) | → **/v/** | Per Wikipedia Persian phonology: "the semi-vowel /w/ has a very limited distribution in Persian"; /v/ is the perceived nearest | CTC alignment: /w/ canonical, realized /v/ in top-3 | Round and protrude lips before voicing — no upper-teeth contact |
| 4 | **/ŋ/** in non-cluster position (sing, thing, ring) | → **/n/** or **/n+k/** | Persian /ŋ/ exists only as allophone of /n/ before /k g/ ("The velar nasal [ŋ] is an allophone of /n/" — Wikipedia Persian phonology) | GOP at canonical /ŋ/; detect inserted /k/ | Hold velar nasal while extending — "sing-ing-ing"; tell user /ŋ/ alone is unfamiliar |
| 5 | **Initial consonant clusters** /sk-, sp-, st-, sl-, sw-, sm-, sn-/ → vowel epenthesis ("school" → "eskool", "stress" → "estress") | Persian syllable structure is CV(CC) — no initial clusters; vowel epenthesis or re-syllabification (academia.edu OT account) | Short [e] or [i] inserted before or between cluster consonants | Whisper transcript surfaces extra vowel; cross-check with aligned audio duration before first stop | **Highest impact for accent reduction**: per Yarmohammadi-derived RG paper, epenthesis "did not harm comprehensibility but affected degree of foreign accent highly"; drill "stress/estress", "spring/espring" |
| 6 | **/ɪ/ vs /iː/** (ship/sheep, bit/beat) | merged toward **/i/** (Persian has only /i/) | Persian 6-vowel system has no tense/lax distinction — Moradi & Chen 2018: "Persian has six vowels compared to twelve in English, lacking tense-lax distinctions" | duration of aligned vowel; canonical /ɪ/ realized as long /i/ | length contrast drill; explain English /ɪ/ is shorter AND lower |
| 7 | **/æ/ vs /ɛ/ vs /ʌ/** (bad/bed/bud, man/men/Monday) | collapsed toward **/æ/** or **/e/** | Persian /æ/ exists, /ɛ/ does not; /ʌ/ approximated by /a/ | GOP at /æ ɛ ʌ/ with realized in {/æ e a/} | front-vowel triangle minimal pairs (bad/bed/bud) |
| 8 | **/ɜː/** (bird, work, learn) | → **/e/** or **/o/** + /r/ | Persian lacks rhotacized central vowel | GOP at /ɜː/; almost always low | "schwa with American /ɹ/" drill |
| 9 | **/ɑː/ vs /ɒ/ vs /ʌ/** (father/lot/love) — for AmE /ɑː/ in "father, lock" | merged toward Persian **/ɒ/** | Persian /ɒ/ (low back rounded) is the most prominent low vowel; AmE /ɑː/ is unrounded | acoustic F1/F2 from librosa would help in v3 | "lock/luck", "father/further" |
| 10 | **Dark /ɫ/ (coda L)** ("ball", "feel", "school") | → clear /l/ | Persian /l/ is always clear — Moradi & Chen 2018: "they struggle with… dark [ɫ], substituting them with clearer forms" | GOP /l/ in coda position only | velarize the back of the tongue; "feel/fill" |
| 11 | **Word stress placement on long English words** | stress on **final syllable** (Persian default) instead of English lexical stress | Yarmohammadi (2005, via SciSpace teaching-word-stress paper): "Persian stress system… instead of the first syllable, it is often, the final syllable which receives the primary stress" | compare CMUdict stress with realized syllable duration/intensity ratio | use CMU stress markers in feedback; pair with vowel-reduction drill |
| 12 | **No vowel reduction in unstressed syllables** ("computer" → /kɒm.pju:.tɛr/ instead of /kəm.ˈpjuː.tɚ/) | Iranian Persian is described variously as stress-timed (Wikipedia Isochrony) or syllable-timed (Abolhasanizadeh & Zaiim 2015) but consistently shows **weaker vowel reduction** than English | check if unstressed-vowel duration ≥ 70% of stressed | schwa drills on common function words ("of, a, the, to, for") |
| 13 | **Final obstruent devoicing** (dog → "dok", "studied" → "studit") | Persian allows voiced finals less reliably than English | check /g d b z v ʒ dʒ/ in coda → realized voiceless | minimal pairs bag/back, bed/bet |
| 14 | **/r/ realization** | Persian trill/flap /ɾ/ instead of AmE retroflex/bunched /ɹ/ | Wikipedia Persian phonology: "/ɾ/ has a trilled allophone [r]… An approximant [ɹ] also occurs as an allophone of /ɾ/ before /t, d, s, z, ʃ, ʒ, l/" — speakers have an approximant but use it inconsistently | GOP at /ɹ/ word-initial and post-vocalic | tongue tip curls back, not flap; "car, far, hard" |
| 15 | **Diphthong simplification** (/aɪ/ /eɪ/ /oʊ/ → monophthongs) | Persian has /eɪ/ and /oʊ/ as V+glide but with reduced glide span | check vowel formant trajectory length | exaggerate the second target |

**Seed catalog file `pronunciation/persian_l1_seed.yaml`** ships these 15 entries with structured fields (`id, ipa_target, ipa_l1_realization, transfer_reason, detection_phones, threshold_offset, coaching_short, coaching_long, drill_words[], priority`). This is analogous to the existing seed-5 grammar catalog.

---

## E. Part D — Concrete Sprint Plan

| # | Task | Rationale | Dep | Acceptance | Effort |
|---|---|---|---|---|---|
| 1 | Add `WhisperMLXEngine` implementing existing `ASREngine` Protocol; default model `mlx-community/whisper-large-v3-turbo` | Highest-leverage ASR fix; L2-ARCTIC evidence | `mlx-whisper>=0.4`, `mlx>=0.22` | Phase-C drill on existing audio file produces a transcript with **0 of {coroutines→coroutine permittive, shared→shaded, threads→threats}** failures; `word_timestamps` populated | M |
| 2 | Implement `initial_prompt` builder with (a) seed technical lexicon, (b) drill prompt vocabulary, (c) accent declaration; SHA-256 logged in frontmatter | Contextual biasing without fine-tuning; arXiv:2410.18363 | task 1 | toggling prompt on/off shows ≥1 token recovered on the same audio | S |
| 3 | Add Silero VAD pre-segmentation behind `--vad` (default on); merge gaps ≤300 ms | Reduces hallucination on silence; whisperX baseline | `silero-vad>=6.2`, `onnxruntime>=1.24` | trailing/leading silence in test clip yields no spurious tokens | S |
| 4 | Add conditional DeepFilterNet denoise gated on SNR < 15 dB | "Enhancement must be conditional and conservative" | `deepfilternet>=0.5.6` | clean test audio is *not* denoised; a deliberately noisy version is, and WER improves | M |
| 5 | Bump `schema_version: 2` with new `asr.*` block; keep all v1 fields | Backward-compatible report extension | task 1 | v1 readers still parse; v2 readers see new keys | S |
| 6 | Add `PronunciationEngine`: load `facebook/wav2vec2-lv-60-espeak-cv-ft` on PyTorch-MPS; expose `align(audio, canonical_phones) -> AlignmentResult` | Core of pronunciation pipeline | `torch>=2.4` (MPS), `transformers>=4.45`, `torchaudio>=2.4` | aligning a clean test sentence returns phone-level timestamps within ±50 ms of MFA ground truth | M |
| 7 | Implement CTC-GOP per arXiv:2507.16838: at each aligned canonical-phone frame, compute `log p(canonical) − log max p(competitor)` | The actual score | task 6 | scores correlate non-trivially (>0.3 Spearman) with hand ratings on a 10-utterance pilot | M |
| 8 | Ship `pronunciation/persian_l1_seed.yaml` (15 entries from Part C); priority overlay tightens GOP threshold by 0.5 on listed canonical phones | L1-aware feedback differentiator | tasks 6, 7 | sample audio with deliberate /θ/→/t/ substitution flags the row "th-stopping" | S |
| 9 | Word-stress check: use CMUdict stress markers from `g2p_en`; realized stress = `argmax(vowel duration × vowel RMS)` across syllables of the word | Sprint-2 suprasegmental feature | tasks 1, 6 | "refactored" pronounced with wrong stress is flagged; correct version is not | M |
| 10 | Markdown renderer additions: phoneme table, stress table, top-3 coaching lines | UX surface | tasks 7–9 | report renders cleanly; passes existing renderer tests; new tests cover new fields | S |
| 11 | (Stretch) Add F0 contour capture via `librosa.yin` to frontmatter, no rendering yet | Lays groundwork for v3 intonation | task 1 | F0 array stored as a downsampled list in frontmatter | S |

### E.1 Risk register

| Risk | Early warning | Mitigation |
|---|---|---|
| **Whisper memory pressure with Qwen3-8B-4bit co-resident** on 18 GB | `mlx` OOM in logs during a Phase-C session | Lazy-load Whisper, free after transcript; or use `distil-large-v3` (756 M params, 6.3× faster than large-v3 with ~1.3 pp WER penalty per the distil-whisper HF model card) as fallback |
| **`wav2vec2-lv-60-espeak-cv-ft` IPA labels don't 1:1 match `g2p_en` ARPAbet** — need a phone-set mapping table | KeyErrors in scoring; many GOPs near zero | Build a tested ARPAbet↔eSpeak mapping (`pronunciation/phone_map.py`); validate on 100 random words against CMUdict; confirm class count via `Wav2Vec2ForCTC.from_pretrained(...).config.vocab_size` (third-party report says ~392) |
| **CTC-GOP noise at phoneme level** (per Speechocean762 distribution analysis: >90% of completeness scores are above 8/10, phoneme-level is the worst granularity) | per-phone scores have wide variance across repeats of the same word | Use GOP only as a flag, not a grade; aggregate to word and utterance level; show trend, not absolute |
| **Persian-L1 priors mis-fire** on idiolects (e.g., this user has lived abroad and already mastered /θ/) | repeated false positives on /θ/ /ð/ | Add per-user calibration: after first 50 attempts, auto-relax priors for any phone with mean GOP > corpus mean |
| **mlx-whisper API drift** between releases (word_timestamps signature has changed historically) | unit tests break on `uv lock --upgrade` | Pin `mlx-whisper`, `mlx`, `transformers`, `torch`, `torchaudio` to specific versions in `pyproject.toml`; only bump on a scheduled update window |

---

## F. Sources and Claim Ledger

(Authority codes: **PR**=peer-reviewed / preprint, **V**=vendor docs, **EB**=engineering blog, **GH**=GitHub README, **F**=forum/secondary.)

| Claim | Source | URL | Date | Authority | Confidence | Used in |
|---|---|---|---|---|---|---|
| Whisper-large-v3 mean MER = 0.054 on L2-ARCTIC across 24 non-native speakers, 6 L1s | Goodwin & Lee, arXiv:2503.06924 | https://arxiv.org/abs/2503.06924 | Mar 2025 | PR (preprint) | High | A, B.1, B.2 |
| Parakeet-TDT-0.6B-v3 = 9.7% WER on FLEURS+CoVoST+MLS 24-lang avg vs Whisper-large-v3 9.9% | Sekoyan et al. (NVIDIA), arXiv:2509.14128 | https://arxiv.org/abs/2509.14128 | Sep 2025 | PR (preprint) | High | A, B.1 |
| Parakeet-TDT-0.6B-v2: 1.69% WER LibriSpeech test-clean, 3.70% test-other, RTFx 3380 @ batch 128 | NVIDIA HF model card `nvidia/parakeet-tdt-0.6b-v2` (model-index) | https://huggingface.co/nvidia/parakeet-tdt-0.6b-v2 | 2025 | V | High | A, B.1 |
| Whisper-large-v3-turbo fine-tune on S&I Corpus L2 English: 5.5% WER | arXiv:2506.04076 | https://arxiv.org/pdf/2506.04076 | Jun 2025 | PR | High | B.1 |
| `mlx_whisper` large-v3-turbo: 13.135 s ± 0.280 s for 1 h MLK audio vs whisper.cpp 26.704 s ± 0.625 s (10-run hyperfine), ratio 2.03 ± 0.06× | llimllib.notes "updated my mlx_whisper vs whisper.cpp benchmark" | https://notes.billmill.org/dev_blog/2026/01/updated_my_mlx_whisper_vs._whisper.cpp_benchmark.html | Jan 2026 | EB | High | A, B.1, B.2 |
| distil-whisper-large-v3: 6.3× faster than large-v3; short-form WER 9.7% vs 8.4%; sequential long-form 10.8% vs 10.0%; chunked long-form 10.9% vs 11.0%; 756 M params, English-only | `distil-whisper/distil-large-v3` HF model card | https://huggingface.co/distil-whisper/distil-large-v3 | 2024 | V | High | B.1, E.1 |
| Whisper `initial_prompt` accepted as contextual biasing lever | Pusateri et al. arXiv:2410.18363 | https://arxiv.org/html/2410.18363v1 | Oct 2024 | PR | High | B.2, B.3, B.4 |
| Telling Whisper the speaker's accent in `initial_prompt` is an effective tactic | SayToWords "Whisper Accuracy Tips" | https://www.saytowords.com/blogs/Whisper-Accuracy-Tips/ | 2025 | EB | Medium | B.3 |
| `parakeet-mlx 0.5.1` ships TDT 0.6b v3 by default with word timings | senstella/parakeet-mlx repo | https://github.com/senstella/parakeet-mlx | 2025-11 | GH | High | B.1, B.2 |
| Senstella `parakeet-mlx` transcribes 1 h 1 m podcast in 53 s on M-series | Simon Willison mlx tag | https://simonwillison.net/tags/mlx/ | Nov 14 2025 | EB | High | B.1 |
| `lightning-whisper-mlx` claims 10× whisper.cpp and supports distil/large variants | Aljadery GitHub | https://github.com/mustafaaljadery/lightning-whisper-mlx | 2024–25 | GH | Medium | B.1 |
| FluidAudio Parakeet on Neural Engine: 2.5% WER vs 6.3% for parakeet-mlx (vendor internal) | MacParakeet blog | https://macparakeet.com/blog/whisper-to-parakeet-neural-engine/ | 2026 | EB (vendor) | Low–Med | B.1 |
| WhisperX uses VAD + wav2vec2 forced alignment for word timestamps | Bain et al., WhisperX, Interspeech 2023 | https://arxiv.org/pdf/2303.00747 | 2023 | PR | High | B.4, C.1 |
| WhisperX default English aligner = `WAV2VEC2_ASR_BASE_960H` (= `facebook/wav2vec2-base-960h`), character-level CTC (~32 letter tokens), Apache 2.0 | whisperX `alignment.py` + HF model card | https://github.com/m-bain/whisperX/blob/main/whisperx/alignment.py ; https://huggingface.co/facebook/wav2vec2-base-960h | 2026 | GH+V | High | C.2 |
| `facebook/wav2vec2-lv-60-espeak-cv-ft`: Apache 2.0; multilingual phoneme CTC; ~392 phoneme classes; zero-shot cross-lingual phoneme recognition | HF model card; Xu, Baevski & Auli arXiv:2109.11680 | https://huggingface.co/facebook/wav2vec2-lv-60-espeak-cv-ft ; https://arxiv.org/abs/2109.11680 | 2021 model card | V+PR | High (Apache); Med (392 — re-verify) | C.2, E.1 |
| `charsiu/en_w2v2_fc_10ms` — MIT (per repo LICENSE; HF page lacks tag); Common Voice + LibriSpeech training; **L2 not evaluated in paper** | lingjzhu/charsiu LICENSE + arXiv:2110.03876 abstract | https://github.com/lingjzhu/charsiu ; https://arxiv.org/pdf/2110.03876 | 2021–22 | GH+PR | High | C.2 |
| Segmentation-free CTC-GOP formulation | Sudo & Shinoda arXiv:2507.16838 | https://arxiv.org/html/2507.16838v2 | Jul 2025 | PR | High | C.1, C.2 |
| GOPT (Transformer over GOP features), evaluated on Speechocean762 | Gong, Chen, Chu, Chang & Glass, ICASSP 2022, MIT CSAIL | https://groups.csail.mit.edu/sls/publications/2022/YGong2_ICASSP-2022.pdf | 2022 | PR | High | A, C.5 |
| Speechocean762: 5000 utts, Mandarin L2, phoneme/word/utterance scores; phoneme-level is hardest granularity, labels skew high (>90% completeness ≥ 8/10) | Zhang et al. arXiv:2104.01378; Emergent Mind summary | https://arxiv.org/pdf/2104.01378 ; https://www.emergentmind.com/topics/speechocean762-dataset | 2021 (corpus); 2024 analysis | PR | High | C.5, E.1 |
| ELSA Speak public architecture: five-skill model (segmental phonemes, prosodic suprasegmentals incl. intonation/word stress/fluency, listening) | ElsaSpeak official Medium post "Discover Your ELSA Score" (mirror at vn.elsaspeak.com) | https://vn.elsaspeak.com/en/discover-your-elsa-score-an-ai-powered-visualization-of-your-english-speaking-proficiency-in-real-time/ | 2024 | V | High | A, C.5 |
| Duolingo English Test pronunciation scorer outperforms GOP, Whisper-ASR-confidence, and Microsoft Pronunciation Assessment; Spearman ρ = 0.82 with expert ratings | Cai et al., *Language Learning* 2025 | https://onlinelibrary.wiley.com/doi/full/10.1111/lang.70000 | 2025 | PR | High | C.5 |
| Duolingo speaking criteria: intelligibility, individual sounds, word stress, sentence stress, intonation | Duolingo Research blog | https://blog.englishtest.duolingo.com/new-research-in-language-learning-a-pronunciation-scoring-model-built-around-intelligibility-not-imitation/ | 2025 | V/EB | High | C.5 |
| L2-ARCTIC: 24 speakers, 6 L1s (Arabic, Hindi, Korean, Mandarin, Spanish, Vietnamese), 150 utts/speaker manually annotated for substitutions/deletions/additions | Zhao et al., Interspeech 2018; TAMU PSI Lab | https://psi.engr.tamu.edu/l2-arctic-corpus/ ; https://psi.engr.tamu.edu/wp-content/uploads/2018/08/zhao2018interspeech.pdf | 2018 | PR | High | brief background, C |
| Persian phonemic inventory: 23 consonants, 6 vowels, 2 diphthongs | Wikipedia Persian phonology (citing Yarmohammadi 1969 et al.) | https://en.wikipedia.org/wiki/Persian_phonology | (standing) | F (cites PR) | Medium | D |
| Persian /w/ has very limited distribution; /ŋ/ is allophone of /n/ before /k g/ | Wikipedia Persian phonology | https://en.wikipedia.org/wiki/Persian_phonology | (standing) | F (cites PR) | Medium | D |
| Persian speakers replace dental fricatives /θ/, /ð/ with /t/, /d/; struggle with dark /ɫ/; 6 vs 12 vowels, no tense/lax distinction | Moradi & Chen 2018 | https://lartis.sk/wp-content/uploads/2019/01/MoradiChenLArt3.02.2018.pdf | 2018 | PR | High | D |
| Persian syllable structure CV(CC) → onset clusters repaired by vowel epenthesis | IJLTER 2015; academia.edu OT account | https://www.ijlter.org/index.php/ijlter/article/download/278/117 ; https://www.academia.edu/2059182/ | 2015 / earlier | PR | High | D |
| Persian epenthesis "did not harm comprehensibility but affected degree of foreign accent highly" | Yarmohammadi-derived RG paper | https://www.researchgate.net/publication/276226108_Difficulties_of_Persian_Learners_of_English_in_Pronouncing_Some_English_Consonant_Clusters | (standing) | PR (secondary) | Medium | D |
| Persian stress predominantly final, contrasting with English lexical stress (Yarmohammadi 2005) | SciSpace word-stress teaching paper citing Yarmohammadi | https://scispace.com/pdf/teaching-word-stress-patterns-of-english-using-a-musically-1nl709dd8o.pdf | 2005 | PR | High | D |
| Iranian Persian classed as stress-timed or syllable-timed depending on study; weaker vowel reduction than English | Wikipedia Isochrony; "Rhythmic Type of Persian" RG (Abolhasanizadeh & Zaiim 2015) | https://en.wikipedia.org/wiki/Isochrony ; https://www.researchgate.net/publication/355049129 | (standing) | F+PR | Medium | D, C.5 |
| `epitran` MIT-Modern-Variant; 61 languages incl. Persian | dmort27/epitran repo | https://github.com/dmort27/epitran ; https://github.com/dmort27/epitran/releases | 2018+ | GH | High | C.2 |
| `phonemizer` depends on `espeak-ng` (GPL) — yellow flag | (standing knowledge) | https://github.com/bootphon/phonemizer | standing | GH | High | C.2 |
| Silero VAD MIT (ONNX), standard upstream of Whisper | silero-vad GitHub Topics | https://github.com/topics/silero-vad | 2024–26 | GH | High | B.4 |
| DeepFilterNet 0.5.6 + Silero VAD + WPE conditional ASR pipeline guidance | big-plump-bird #13 (production planning doc) | https://github.com/ragaeeb/big-plump-bird/issues/13 | Feb 2026 | EB/GH | Medium | B.3, B.4 |
| Time-domain single-channel denoising can give 30% relative WER reduction on CHiME-4 | Kinoshita, Ochiai, Delcroix & Nakatani (NTT Communication Science Laboratories, Kyoto), arXiv:2003.03998 | https://arxiv.org/pdf/2003.03998 | 2020 | PR | High | B.4 |
| Montreal Forced Aligner: install on Apple Silicon via conda-forge for arm64 supported in current docs | MFA docs | https://montreal-forced-aligner.readthedocs.io/en/latest/installation.html | 2024+ | V | High | C.2 |
| Kokoro-82M weights Apache 2.0; kokoro-mlx inference code MIT; misaki G2P bundled | gabrimatic/kokoro-mlx README | https://github.com/gabrimatic/kokoro-mlx | 2025 | GH | High | stack baseline |

### F.1 Unverified items that influenced thinking but are not load-bearing

- **Persian-L1 English ASR WER for Whisper or Parakeet specifically — no published number located.** Recommendations rest on Whisper's strong cross-accent performance (L2-ARCTIC's 6 L1s, none of them Iranian) and on Whisper's `initial_prompt` ability to encode the accent. The engineer should collect 30 minutes of their own Persian-accented English with hand transcripts to compute it locally before any further model decision.
- **Exact phoneme class count for `wav2vec2-lv-60-espeak-cv-ft`** reported as ~392 by one third-party project; programmatically reconfirm with `Wav2Vec2ForCTC.from_pretrained(...).config.vocab_size` on first install.
- **Charsiu's specific behaviour on Persian-accented English**: not benchmarked in the published paper; only inferred from CV training data containing accents. If Charsiu is preferred over `wav2vec2-lv-60-espeak-cv-ft` for English-only, run an empirical comparison on 20 utterances.
- **Apple's *Voice Pro* and Argmax WhisperKit private benchmarks**: Swift-only, excluded.

### F.2 Update triggers — what would change these recommendations

- A new `parakeet-mlx` release that **exposes contextual biasing** (initial-prompt-like prompt-token injection) → revisit B.2; Parakeet's word-boundary precision would then make it the better choice.
- A **native MLX port of `wav2vec2-lv-60-espeak-cv-ft`** (or any IPA-phoneme CTC model) → 2–3× speed-up on alignment, simplifies dependencies (drop PyTorch-MPS).
- A **Canary-1B-v2 MLX port** at production quality → consider for the ASR engine; Canary outperforms Whisper-large-v3 on Open ASR avg.
- A **public Persian-L1 English speech corpus with phoneme annotations** (e.g., a Persian extension to L2-ARCTIC, or an EpaDB analog for Iranian English) → swap heuristic priors in `persian_l1_seed.yaml` for a trained classifier.
- ELSA or Speechace publishing a quantitative methodology paper would let us validate our CTC-GOP + L1-prior approach against a documented commercial baseline.
- **Constraint shift**: if cloud APIs become acceptable, a cloud-augmented v3 with Microsoft Azure Pronunciation Assessment or Speechace would dominate per-phoneme accuracy — explicitly out of scope here.