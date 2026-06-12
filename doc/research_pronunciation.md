# Offline On-Device Pronunciation Assessment for "speakloop" on Apple Silicon M3 Pro

**RECOMMENDATION (build this first): Ship a READ-ALOUD drill mode built on a forced-alignment + Goodness-of-Pronunciation (GOP) pipeline using a wav2vec2 CTC phoneme model, with Praat/Parselmouth for prosody — and treat spontaneous-answer scoring as a lightweight, clearly-labeled "possible mispronunciation" flag only.** Reliable phoneme- and word-level mispronunciation detection on this hardware is feasible ONLY when the target text is known. Reference-free scoring of spontaneous technical-interview answers is not yet reliable enough offline to give learners trustworthy "you mispronounced X" feedback, and should not be the primary capability.

## TL;DR

- **The core ask (detect which phonemes/words are mispronounced, where stress/intonation is wrong, and coach it) is achievable offline on an M3 Pro / 18 GB — but only in a read-aloud drill mode where the target sentence is known.** Segmental scoring there is solid; prosody is partially solid (stress/intonation timing via Praat is reliable; "natural intonation" scoring is weak).
- **Spontaneous-speech pronunciation assessment is the hard case and is not yet offline-reliable**: it requires recognizing accented words first (Whisper errs exactly on the accented words you want to flag), so it can only deliver low-confidence flags, not graded diagnosis. Build it as a secondary, hedged feature.
- **Concrete stack:** Whisper large-v3-turbo (already in place) → canonical phonemes via g2p_en (CMUdict, Apache-2.0) → forced alignment + per-phone GOP via a wav2vec2 phoneme-CTC model (facebook/wav2vec2-lv-60-espeak-cv-ft, Apache-2.0, 1.26 GB) or Charsiu (MIT) → Parselmouth/Praat for pitch/stress/rhythm → rule-based feedback + minimal-pair drill generator. Fits comfortably in 18 GB; all pip/conda-installable; runs on PyTorch-MPS or CPU.

## Key Findings

1. **Read-aloud (known-text) scoring is the only configuration where offline segmental MDD is trustworthy today.** The entire mature literature (GOP, speechocean762, L2-ARCTIC) assumes a known target text. Even the best 2026 systems are evaluated against a canonical reference sequence. (Confidence: high)

2. **The "wrapper → rapper" error is exactly what a read-aloud GOP pipeline catches well, and exactly what a spontaneous pipeline catches badly.** In read-aloud mode you force-align audio to the known phonemes /r æ p ɚ/ vs canonical /w r æ p ɚ/ and score the /w/ phone directly. In spontaneous mode, the ASR will likely just transcribe "rapper" (the wrong word) and you lose the diagnostic signal entirely. (Confidence: high)

3. **Phone-level MDD accuracy on curated L2 benchmarks is moderate, not excellent.** Best reported L2-ARCTIC phone-level MDD F1 is 71.77% (Geng et al., CROTTC-IF, arXiv 2604.22133: "CROTTC-IF achieves a 71.77% F1-score on L2-ARCTIC and 71.70% F1-score on the Iqra'Eval2 leaderboard"), ahead of a training-free retrieval method at 69.60% (Tu et al., arXiv 2511.20107, 25 Nov 2025: "our method achieves a superior F1 score of 69.60% while avoiding the complexity of model training") and a wav2vec2-XLSR baseline at 60.44%. Phoneme-level Pearson correlation on speechocean762 tops out around 0.612 (GOPT) to 0.743 (2025 LoRA multimodal LLM). Diagnosis accuracy across benchmarks is often below 60%. (Confidence: high)

4. **A clear quality ceiling vs Azure:** Azure Pronunciation Assessment reports Prosodic PCC 0.842 and Total PCC 0.782 on speechocean762 (as benchmarked in arXiv 2509.02915: "the Azure PA service demonstrated superior correlation (Prosodic PCC 0.842, Total PCC 0.782)") and has a production prosody engine (stress, intonation, "unexpected break", "monotone"). An offline stack will trail Azure especially on prosody and on robustness to noise/accent. Azure is cloud-only and therefore out of scope, but defines the bar. (Confidence: high)

5. **All required components are open-source, pip/conda installable, Apple-Silicon-friendly, and commercially usable — with one licensing trap.** g2p_en (Apache-2.0), wav2vec2 phoneme models (Apache-2.0), Charsiu (MIT), SpeechBrain (Apache-2.0), Parselmouth (GPL), openSMILE all run on PyTorch-MPS or CPU. The trap is **espeak-ng / phonemizer, which is GPL-3.0** — viral for distributed commercial software. Avoid it by using CMUdict-based g2p_en or OpenPhonemizer (BSD) for canonical pronunciations. (Confidence: high)

6. **2026 research is moving toward alignment-free GOP**, which removes the brittle forced-alignment step: GOP-SF/GOP-AF (Cao et al., arXiv 2507.16838, updated 5 Feb 2026) achieves state-of-the-art phoneme-level results on speechocean762 with "very low computational cost," and a 2026 paper does GOP without phoneme time alignment at all (Wong & Chen, A*STAR, arXiv 2603.25150, 26 Mar 2026). These are promising but research-grade (no packaged release). (Confidence: medium)

## Details

### A. How audio flows (recommended read-aloud pipeline)

1. **Prompt:** The drill presents a known target sentence (e.g., a sentence containing "wrapper", or a minimal-pair set). The canonical phoneme sequence is computed offline with **g2p_en** (CMUdict + neural fallback for OOV; ARPAbet with stress markers; Apache-2.0, NumPy inference, no GPU needed). For IPA you can map ARPAbet→IPA with a static table.
2. **Record + VAD:** Reuse the existing recorder and Silero VAD to get a clean 16 kHz mono utterance.
3. **Forced alignment + acoustic posteriors:** Run a wav2vec2 phoneme-CTC model to get frame-level phoneme posteriors. Two viable routes:
   - **Charsiu** (`charsiu/en_w2v2_fc_10ms`, wav2vec2-base ~95M params, ~360–380 MB, MIT license) for 10 ms phone-to-audio alignment; or
   - **facebook/wav2vec2-lv-60-espeak-cv-ft** (wav2vec2-large, ~315M params, 1.26 GB on disk, Apache-2.0) which emits IPA phoneme labels directly, combined with CTC forced alignment (torchaudio, ctc-forced-aligner, or SpeechBrain `ctc_segmentation`).
4. **GOP scoring:** Compute per-phone Goodness of Pronunciation from the posteriors (log-posterior of the canonical phone, optionally a likelihood ratio against the best competing phone). Phones below a threshold are flagged; the top competing phone gives the *diagnosis* ("you produced /r/ where /w/ was expected"). Aggregate to word-level scores.
5. **Prosody:** Use **Parselmouth (Praat)** to extract the F0 contour, intensity, and per-syllable duration. Combined with the phone alignment, derive: lexical stress placement (energy/duration/pitch prominence per syllable vs the canonical stressed syllable from CMUdict), sentence-level pitch range/contour, and rhythm/timing.
6. **Feedback + drills:** Rule-based mapping from each flagged phone/word/stress error to (a) a plain-language tip and (b) a generated minimal-pair or targeted drill.

**Memory/latency profile (M3 Pro, 18 GB):** The largest resident model is wav2vec2-large at ~1.26 GB fp32 weights (~0.63 GB fp16); practical peak inference RAM ~2–3 GB fp32. Whisper large-v3-turbo (~1.6 GB) is already loaded. Parselmouth and g2p_en are negligible (<200 MB). Total comfortably under 18 GB even with Whisper resident. On MPS, a single utterance (5–15 s) scores in roughly real-time or faster; Charsiu's base model is faster still. Set `PYTORCH_ENABLE_MPS_FALLBACK=1` for any unsupported ops. (Confidence: high on fit; medium on exact latency, which is a derived estimate.)

### B. Read-aloud vs spontaneous — recommendation

**Build read-aloud first; add spontaneous as a hedged secondary mode; a hybrid is worthwhile but only with honest labeling.**

- **Read-aloud (repeat-the-sentence drills):** Reliable because the target phoneme sequence is known, so alignment is constrained and per-phone scoring is well-posed. This is where the literature's accuracy numbers actually apply. It directly delivers the three required capabilities (segmental, word, stress/intonation). It fits the existing "ideal answer" content model — you can derive drill sentences from the reference answers' vocabulary.
- **Spontaneous (the interview answers):** Reference-free. You must first recognize the words (Whisper), then compare produced phones to the canonical pronunciation of the *recognized* words. The failure mode is fatal for the use case: when the learner says "wrapper" badly, Whisper transcribes "rapper," the canonical lookup is now for the wrong word, and the error is silently accepted. So spontaneous scoring can only support **low-confidence "this word may be mispronounced" flags** (e.g., where the phoneme recognizer and Whisper disagree, or acoustic posteriors are diffuse), never graded diagnosis.
- **Hybrid:** Worthwhile. Run reliable read-aloud drills as the core feature, and on spontaneous answers surface a small number of "possibly mispronounced — try the drill" nudges that route the user into a read-aloud drill for that word. Crucially, label spontaneous flags as tentative.

### C. What feedback it can actually produce, per capability

| Capability | Read-aloud (known text) | Spontaneous (reference-free) |
|---|---|---|
| **Segmental: which phones** | Reliable. Per-phone GOP + top-competitor diagnosis ("/w/→/r/"). | Weak. ASR errors on the exact words of interest. Flags only. |
| **Segmental: which words** | Reliable. Aggregate phone scores to word scores. | Weak/medium. |
| **Lexical stress** | Reliable-ish. Compare measured syllable prominence (duration+energy+pitch) to CMUdict canonical stress. Literature: 87.9% syllable-stress classification (primary/secondary/no stress) for words with ≥3 syllables (Li, Mao, Li, Wu & Meng 2018, Speech Communication; their pitch-accent detector reached 90.2%). | Weak. |
| **Sentence stress / intonation** | Medium. Pitch contour + prominence extractable via Praat; "wrong vs right intonation" scoring is heuristic, not validated. | Weak/experimental. |
| **Rhythm/timing** | Medium. Phone/syllable durations and pause structure are measurable and reusable from existing fluency metrics. | Medium (timing is text-independent). |

**Turning scores into action:**
- *Segmental tip generation* is rule-based and reliable: map (expected phone, produced phone) → articulatory instruction. E.g., /w/→/r/: "Round your lips and don't curl your tongue back — 'wuh', not 'ruh'." Maintain a static table of ~40 English phones × common confusions.
- *Drill generation* is reliable: for each flagged phone contrast, pull minimal pairs from a bundled list (wrapper/rapper, west/rest, wing/ring) and generate a read-aloud drill. This closes the loop into the reliable mode.
- *Prosody tips* are weaker: "Stress the first syllable: WRAP-per, not wrap-PER" is reliable when stress placement is detected; "make your intonation more natural" is not advisable to surface as a hard judgment.

### D. Candidate architectures compared

| Dimension | **(1) Forced-align + GOP on wav2vec2 (RECOMMENDED)** | **(2) E2E phoneme recognizer + align to canonical (MDD)** | **(3) Read-aloud-only minimal stack (Charsiu + Praat)** |
|---|---|---|---|
| Phone-level MDD quality | Good in read-aloud; mature method | Best diagnosis (produces actual phone string); SOTA ~72% F1 on L2-ARCTIC | Good for alignment+gross errors; weaker fine diagnosis |
| Prosody support | Via Praat (added separately) | Via Praat (added separately) | Via Praat (native to plan) |
| Hardware fit (18 GB) | Excellent (~1.3 GB model) | Good (large model 1.26 GB) | Excellent (base ~0.38 GB) |
| Setup/packaging | Easy: pip (transformers, torch, parselmouth, g2p_en) | Easy-medium: pip; model from HF | Medium: Charsiu is git-clone only (not on PyPI) |
| License | Apache-2.0 (models), Apache (g2p_en), GPL (Parselmouth) | Apache-2.0 | MIT (Charsiu) + GPL (Parselmouth) |
| Integration effort | Low-medium | Medium (decode + alignment of two phone strings via Needleman-Wunsch) | Low |

**Why (1):** GOP is the best-understood, most controllable method; it gives a tunable per-phone score and a natural diagnosis (top competing phone), runs cheaply, and is easy to package. **(2)** gives slightly better diagnosis and is the path if you later want to detect insertions/deletions the learner makes, but adds the complexity of aligning two phone strings and is more sensitive to phoneme-recognizer errors. **(3)** is the fastest thing to ship if packaging simplicity matters most, but Charsiu's lack of a PyPI release is a real friction point for a clean pip/uv install.

**Avoid Kaldi/MFA as the core runtime.** MFA (conda-forge, builds on Kaldi) is powerful and gives the canonical GOP recipe, but it is heavy, conda-only (historically flaky on Apple Silicon — early miniforge installs failed; full Anaconda worked), and clashes with a clean pip/uv path. Use it only offline to validate your scores against the speechocean762 GOP recipe, not in the shipped tool.

### E. Honest limitations and realistic ceiling

- **Benchmark-vs-reality gap (weight heavily):** speechocean762 is 5,000 read-aloud utterances from 250 non-native speakers whose mother tongue is Mandarin (half of them children), held to a 2:1:1 good:medium:poor proficiency ratio and annotated at sentence/word/phoneme level by five experts (Zhang et al. 2021, arXiv 2104.01378); L2-ARCTIC is similarly curated read-aloud L2 speech. Real spontaneous technical English — domain jargon ("Kubernetes", "idempotent"), code-switching, varied L1s, laptop-mic noise — will be **harder than the published F1≈0.7 / PCC≈0.6 numbers**. Treat those as optimistic upper bounds. (Confidence: high)
- **Diagnosis is the weakest link:** even SOTA correctly diagnoses *which wrong phone* well under 60% of the time on hard cases. Lead with detection ("this sounded off") and offer the most-likely diagnosis as a suggestion, not a verdict.
- **Prosody/intonation is the biggest offline gap vs Azure.** You can measure pitch/stress/timing reliably; you cannot reliably judge "natural intonation." Azure's prosody PCC (0.842) reflects a trained engine you cannot match offline with rules.
- **OOV/jargon:** g2p_en's neural fallback handles OOV words but pronunciations for technical terms may be wrong, producing false mispronunciation flags. Curate a custom lexicon for recurring domain terms.
- **Quality ceiling statement:** Expect to deliver maybe ~80–90% of Azure's *segmental* read-aloud usefulness, but only ~50–60% of its *prosody* usefulness, and materially less robustness on noisy spontaneous speech.

### F. Overall confidence and the one finding that would most change the recommendation

**Overall confidence: high** that read-aloud GOP + Praat is the best feasible offline approach and is buildable today within 18 GB; **medium** on the real-world accuracy you'll achieve on spontaneous technical English. **The single finding that would most change the recommendation:** if you can collect and label even a few hours of in-domain technical-interview speech, fine-tuning the phoneme model on it would do more for real-world quality (and would partially unlock graded spontaneous scoring) than any model swap. Secondarily, a packaged, Apple-Silicon-ready **alignment-free GOP** library (per arXiv 2507.16838) would let you drop the brittle forced-alignment step.

## Recommendations

**Stage 1 (MVP, build now): Read-aloud segmental drills.**
- Add a "pronunciation drill" mode. Pick/author target sentences (seed from reference answers + minimal-pair lists).
- Pipeline: g2p_en canonical phones → wav2vec2-lv-60-espeak-cv-ft posteriors + CTC forced alignment → per-phone GOP → word/phone flags + articulatory tips → minimal-pair drill loop.
- Ship the /w/–/r/, vowel, and other top-20 confusion tips and drills first.
- **Benchmark to validate before shipping:** reproduce the speechocean762 GOP baseline (target phone-level PCC ≥ 0.5, vs GOPT's 0.612) on your own pipeline; spot-check 20–30 self-recorded "wrapper/rapper"-type errors.

**Stage 2: Prosody (read-aloud).**
- Add Parselmouth-based lexical-stress detection (syllable prominence vs CMUdict) and pitch-contour visualization. Surface stress-placement feedback; show intonation as a *visualization* rather than a hard score.

**Stage 3: Hybrid spontaneous flags.**
- On interview answers, compute cheap per-word confidence (phoneme-recognizer vs Whisper disagreement; diffuse GOP). Surface ≤2–3 tentative "want to drill this word?" nudges. Always labeled as tentative; always route into Stage-1 drills.

**Thresholds that would change the staged plan:**
- If an **alignment-free GOP** implementation (GOP-SF, arXiv 2507.16838) ships as a packaged, Apple-Silicon-friendly library with reproducible speechocean762 numbers, switch the core scorer to it — it removes forced alignment and lowers compute.
- If a packaged **end-to-end MDD model** appears on HF with L2-ARCTIC F1 materially above ~0.72 *and* validated on spontaneous speech, promote spontaneous scoring from "flags" to "graded."

## Caveats

- **Licensing:** Do **not** ship espeak-ng/phonemizer (GPL-3.0, viral) in a closed-source product; use g2p_en (Apache-2.0) or OpenPhonemizer (BSD) for canonical pronunciations. **Parselmouth is GPL** — if that's unacceptable, extract pitch/intensity with a permissive library (librosa/torchaudio + a pYIN/CREPE implementation) or openSMILE, at some accuracy cost. Charsiu is MIT but git-clone-only (vendor it). wav2vec2 models and SpeechBrain are Apache-2.0.
- **Evidence grading:** Accuracy figures come from curated L2 read-aloud corpora and will overstate performance on spontaneous, noisy, jargon-heavy technical English. Confidence is high on architecture/feasibility/licensing, medium on real-world accuracy and exact latency.
- **The 2026 SOTA F1 (71.77%, CROTTC-IF) is a recent preprint** (arXiv 2604.22133), not yet peer-reviewed/independently verified — treat as "best reported," not settled.
- **RAM estimates** for wav2vec2-large are computed from parameter counts, not measured benchmarks; SpeechBrain's k2-based aligner is a known Apple-Silicon install pain point (prefer `ctc_segmentation` or Charsiu).

## Sources

1. Cao et al., "Segmentation-free Goodness of Pronunciation" (GOP-SA/GOP-SF), arXiv 2507.16838, v3 dated 5 Feb 2026 — SOTA phoneme-level on speechocean762, low compute. Tier 1 (primary).
2. Wong & Chen (A*STAR), "Goodness-of-pronunciation without phoneme time alignment," arXiv 2603.25150, 26 Mar 2026 — alignment-free GOP via Whisper + confusion network. Tier 1.
3. Tu et al., "Mispronunciation Detection and Diagnosis Without Model Training: A Retrieval-Based Approach," arXiv 2511.20107, 25 Nov 2025 — L2-ARCTIC F1 69.60%. Tier 1.
4. Geng et al., "Beyond Acoustic Sparsity and Linguistic Bias: A Prompt-Free Paradigm for MDD" (CROTTC-IF), arXiv 2604.22133, 24 Apr 2026 — L2-ARCTIC F1 71.77% (best reported; preprint). Tier 1, lower confidence.
5. Gong et al., "Transformer-Based Multi-Aspect Multi-Granularity Pronunciation Assessment" (GOPT), ICASSP 2022; github.com/YuanGongND/gopt — speechocean762 phone-level PCC 0.612, word 0.549, sentence 0.742. Tier 1.
6. "English Pronunciation Evaluation … LoRA Fine-tuned Speech Multimodal LLM," arXiv 2509.02915, Sep 2025 — accuracy PCC 0.743 (SOTA); benchmarks Azure PA prosody PCC 0.842, total 0.782. Tier 1.
7. Zhang et al., "speechocean762," arXiv 2104.01378; kaldi gop_speechocean762 recipe — benchmark + GOP baseline (5,000 utterances, 250 Mandarin-L1 speakers, label-imbalanced). Tier 1, benchmark caveat applies.
8. facebook/wav2vec2-lv-60-espeak-cv-ft model card, Hugging Face — Apache-2.0, 1.26 GB, ~315M params, IPA phoneme CTC. Tier 1.
9. lingjzhu/charsiu (GitHub) — MIT license, wav2vec2 neural aligner (en_w2v2_fc_10ms, wav2vec2-base ~95M params), git-clone install (no PyPI). Tier 1.
10. vitouphy/wav2vec2-xls-r-300m-timit-phoneme and mrrubino/wav2vec2-large-xlsr-53-l2-arctic-phoneme (HF) — alt phoneme recognizers (L2-ARCTIC fine-tune WER 0.425). Tier 1.
11. g2p_en (PyPI/conda) — Apache-2.0, CMUdict + neural fallback, NumPy inference, no GPU needed. Tier 1.
12. phonemizer (PyPI) GPL-3.0 + espeak-ng GPL-3.0 discussions (espeak-ng #2131, #1868); NeuralVox/OpenPhonemizer (BSD-3-Clear). Tier 1 (licensing).
13. Parselmouth (GitHub/readthedocs) — Praat in Python; pitch/intensity/formants/duration. GPL. Tier 1.
14. Montreal Forced Aligner docs (readthedocs) + issue #372 — conda-forge/Kaldi, Apple-Silicon install friction. Tier 1.
15. WhisperX (github.com/m-bain/whisperX), BSD-4-Clause — wav2vec2 forced alignment for word/phone timestamps (±50 ms). Tier 1.
16. SpeechBrain (GitHub/PyPI) — Apache-2.0, CTC alignment utilities (ctc_segmentation; k2 aligner). Tier 1. (k2 dependency is an Apple-Silicon install risk.)
17. Microsoft Azure Pronunciation Assessment docs (learn.microsoft.com) — cloud-only quality bar; phoneme/syllable/word scores, prosody engine (stress, intonation, unexpected break, monotone), en-US prosody only. Tier 1, out of scope (cloud).
18. Li, Mao, Li, Wu & Meng, "Automatic lexical stress and pitch accent detection … MD-DNN," Speech Communication 96 (2018) — 87.9% syllable-stress accuracy (≥3-syllable words); 90.2% pitch-accent. Tier 1.
19. Shahin et al., "Phonological level wav2vec2-based MDD," Speech Communication 2025 (DOI 10.1016/j.specom.2025.103249) — phonological-feature MDD approaching human expert F1 ~71.4%. Tier 1.
20. Apple Silicon PyTorch MPS references (PyTorch docs; arXiv 2511.05502 "Production-Grade Local LLM Inference on Apple Silicon") — MPS unified-memory inference behavior, fallback flag. Tier 2.

## Implementation decisions (feature 016 — shipped)

The read-aloud drill MVP from the recommendation above shipped in feature 016. The detailed,
primary-source-verified engineering decisions live in
[`specs/016-pronunciation-drills/research.md`](../specs/016-pronunciation-drills/research.md).
Key deltas from the recommendation above (all verified vs HF/PyPI on 2026-06-12):

- **Model**: `facebook/wav2vec2-lv-60-espeak-cv-ft` (Apache-2.0). Confirmed it ships a single
  `pytorch_model.bin` (~1.26 GB, no safetensors index) — the downloader was extended in place
  (`Model.weight_files` + `preprocessor_config.json` in `META_FILES`) to fetch it via the same
  aria2 path. Run on **CPU** (MPS deferred).
- **Canonical phonemes are BUNDLED** in `drill_bank.yaml`, NOT computed at runtime. `g2p_en` is
  Apache-2.0 but fetches NLTK data over the network on first use → it would break offline-first;
  it is kept as an offline authoring aid only (not shipped). Genuine /w/–/r/ minimal pairs
  (west/rest, wing/ring) replace the "wrapper/rapper" example, which are homophones (silent wr-).
- **Alignment + GOP is pure numpy** (`pronunciation/gop.py`) — `ctc_segmentation` (Apache-2.0)
  was rejected because it is sdist-only and compiles Cython against numpy 2.x (install-fragility
  risk vs the "git clone && uv run" promise). `ctc-forced-aligner` (torchcodec/CC-BY-NC) and
  `charsiu` (git-only / undeclared model license) and Parselmouth/espeak/phonemizer (GPL) were
  all rejected on dependency/licensing grounds.
- **Safety gate**: `psutil` (BSD-3) for live available RAM (stdlib can't report *available* RAM
  on darwin); `engine == "local"` is always unsafe.

## Implementation decisions (feature 017 — shipped)

Feature 017 turns the 016 drill block into a **hear → say → see → retry** trainer and makes it a
standalone activity. Decisions (full detail: `specs/017-pronunciation-trainer/research.md`):

- **Hear-first** reuses the existing **Kokoro TTS** + blocking playback already injected into the
  coordinator (question/warm-up/follow-ups path) — no new engine, offline preserved, clip-cached.
  Replay-on-demand polls the existing `KeyReader` for `r`. Degrades to 016 when TTS/interactivity
  is absent (so the default test suite + the 016 byte-identical/concurrency tests stay green).
- **Bounded automatic retry** (not a yes/no prompt): on a flagged target, re-play → re-record →
  re-score up to `pronunciation_retries` (default 1, clamp 0–3), stopping when the target clears;
  "improved" is a detection-level comparison (the previously-flagged target no longer flags),
  consistent with the 016 calibration. Interactive-only, so non-interactive runs behave like 016.
- **Sentence canonical = flat per-word concatenation, no word-separator token** — CTC blanks
  already separate canonical tokens, so word boundaries need no symbol and the bank doesn't depend
  on whether `vocab.json` has a space token. Targets sit sentence-initial for robust alignment.
- **Build-time correctness harness** `tests/live_pron_test.py` (`-m live_pron`, self-skipping,
  excluded from the default suite): TTS-renders every bundled drill through the real scorer and
  asserts it scores clean — the authoritative validation of the hand-authored canonical sequences.
- **Standalone gate** `assess_standalone_safety`: RAM-only (no resident feedback engine), a
  distinct function so the 016 interview rule (`engine=="local"` always unsafe) is unchanged.
- **Loop logic** is a pure, UI-agnostic `pronunciation/drill_runner.py` (injects speak/record/
  scorer) shared by the interview block and `cli/pronounce.py` — no `pronunciation → sessions/tts/
  audio` cycle; unit-tested with fakes.
- **Weak-sound memory**: a rebuildable `pronunciation_contrasts` section in the derived store
  biases `select_drills`; standalone-only history is live (dropped on a manual `rebuild`, like the
  SRS `next_due` placeholder). `STORE_VERSION` + report `schema_version` both stay 1.