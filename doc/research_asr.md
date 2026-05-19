# Local ASR for English Interview Practice on M3 Pro 18 GB — May 2026 Decision Report

## TL;DR
- **Top pick: NVIDIA Parakeet-TDT-0.6b-v3 via the `parakeet-mlx` Python package (model released 2025-08-14, package v0.5.1 published 2026-02-21).** It posts ~6.32% average WER on the Open ASR Leaderboard (arXiv:2510.06961 v4, Mar 30 2026) at >3,000× server-GPU RTFx, weighs ~2.4 GB on disk with ~2 GB peak RAM in MLX, has native Apple Silicon support, returns word-level timestamps, and — being an RNN-T/TDT transducer — does not exhibit Whisper's documented hallucination-on-silence pathology.
- **Strongest accuracy alternative: faster-whisper running Whisper-large-v3-turbo** (model 2024-10-01, faster-whisper actively maintained in 2026) with `vad_filter=True`, `hotwords=...` and an `initial_prompt` listing your Android/Kotlin vocabulary. Broader accent coverage from 680,000 hours of training, but CPU-only on Mac (no Metal backend in CTranslate2) and prone to silence hallucinations without VAD.
- **Freshness note:** rankings are confident for May 2026. Parakeet v3 has held the speed-efficiency Pareto frontier since Aug 2025. Canary-Qwen 2.5B (#1 at 5.63% WER) is too memory-hungry without a native MLX port. The next likely disruptor — Cohere-Transcribe-03-2026 (5.42% WER, Apache-2.0) — has no Apple-Silicon Python path yet. Revisit in 60 days.

## Key Findings

1. **The Open ASR Leaderboard has shifted decisively toward NVIDIA NeMo and LLM-backbone architectures in 2025-2026.** Canary-Qwen 2.5B leads at 5.63% avg WER, IBM Granite Speech 3.3 8B at exactly 5.74% (Open ASR Leaderboard live dataset, retrieved May 2026), Parakeet-TDT-0.6b-v3 at 6.32%, Whisper Large-v3 trails at 7.44% (arXiv:2510.06961 v4, Table 3, Mar 30 2026).
2. **For your 18 GB unified-memory M3 Pro, only Parakeet, the Whisper family, and Voxtral-Mini realistically fit with headroom for an IDE.** Canary-Qwen 2.5B (5.12 GB BF16 on disk) and Granite Speech 3.3 8B (~17 GB) blow the budget once you account for macOS + Slack + browser, and neither has a first-class MLX port today.
3. **Apple Silicon native paths in May 2026:** Parakeet ships via `parakeet-mlx` (senstella, Apache-2.0); Whisper ships via `mlx-whisper` (Apple ML-Explore, MIT) and WhisperKit (Argmax, MIT — Swift only, Python access through CLI/HTTP); `faster-whisper` runs CPU-only on Mac with CTranslate2 INT8.
4. **Hallucination on silence is documented across the entire Whisper family** (openai/whisper Discussions #679, #1783, #2378). It is mitigated, not solved, by `vad_filter=True`, `condition_on_previous_text=False`, `hallucination_silence_threshold`, and `initial_prompt`. Parakeet-TDT (RNN-T architecture) does not exhibit this failure mode and is the safer base for interview-practice recording where you will have long thinking pauses.
5. **No public benchmark reports Persian-accented English WER for any of these systems.** Verified against the Open ASR Leaderboard arXiv paper, the Parakeet/Canary tech report (arXiv:2509.14128, Sep 17 2025), the Granite-Speech paper (arXiv:2505.08699), the Voxtral paper (arXiv:2507.13264), and recent Persian-ASR papers (arXiv:2510.09528, arXiv:2505.21230). The closest published Persian-accent ASR work tests only Whisper tiny/base/medium on Persian itself, not Persian-accented English. You must A/B test on your own recordings; treat any "robust to accents" marketing claim as unverified.
6. **Pronunciation/phoneme feedback is a separate pipeline.** None of the SOTA ASR systems above output IPA. The accepted Python stack is `transformers` + `facebook/wav2vec2-lv-60-espeak-cv-ft` (Wav2Vec2Phoneme) for IPA recognition, or `allosaurus` (pip, GPL-3.0) for universal phone recognition across 2,000+ languages, combined with Goodness-of-Pronunciation (GOP) scoring against forced alignment.

## Details

### Evidence Table

| System (sorted recency) | Release | Disk / peak RAM | LibriSpeech-clean WER | AMI / Earnings22 WER (accented) | M3 Pro speed | Python ergonomics | Hot-words / prompt | Word timestamps | Hallucinations on silence | Streaming | Phoneme/IPA | License | Maintenance |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **parakeet-mlx + Parakeet-TDT-0.6b-v3** | pkg 2026-02-21; model 2025-08-14 | 2.4 GB / ~2 GB | 1.93% | 11.31% / 11.42% | ~60× realtime (community) | 5/5 (3-line API) | NeMo word-boosting via PR #14277 (PyTorch only); no first-class hot-word in parakeet-mlx — workaround: post-process or beam decoding | yes (word + sentence) | no (RNN-T) | yes (`transcribe_stream`) | no (bonus via separate pipeline) | model CC-BY-4.0; package Apache-2.0 | Active (v0.5.1 Feb 2026, 26 versions) |
| **mlx-whisper + Whisper-large-v3-turbo** | pkg 0.4.3 active; model 2024-10-01 | 1.6 GB / ~3 GB | 2.7% | ~15.95% / 11.29% | roughly 2× slower than parakeet-mlx on M-series (mac-whisper-speedtest: 1.02 s vs 0.50 s) | 5/5 | `initial_prompt`, `suppress_tokens`, `condition_on_previous_text` | yes (segment + word) | **YES — documented** | no (use whisperlivekit wrapper) | no | MIT (both) | Active (Apple) |
| **WhisperKit (via local OpenAI-compat server from Python)** | active 2026; ANE backend | 1.6 GB / ~2 GB | 2.2% (Argmax ICML 2025) | unverified on accented | 0.46 s/word streaming latency; ~137× RTFx encoder on M3 Max Neural Engine (arXiv:2507.10860v1 Table 1) | 3/5 from Python (subprocess or generated OpenAPI client) | `prompt` (= Whisper `initial_prompt`) on OpenAI endpoint | yes | YES (Whisper family) | yes | no | MIT | Very active (Argmax) |
| **NVIDIA NeMo + Parakeet/Canary** | nemo_toolkit 2.5+ (2026) | Parakeet 0.6B: ~2.4 GB; Canary-Qwen: 5.12 GB | 1.60% (Canary-Qwen) | 10.18% / 10.42% (Canary-Qwen) | CPU/MPS only on Mac — slow; no Metal-optimized NeMo backend | 3/5 (heavy install) | **First-class GPU-PB word boosting (NeMo 2.5, PR #14277, arXiv:2508.07014)** | yes | no (RNN-T/TDT) | yes (FastConformer streaming variants) | no | Parakeet v3 / Canary-Qwen: CC-BY-4.0 | Very active (NVIDIA) |
| **faster-whisper + large-v3-turbo** | v1.2+ (2025); model 2024-10-01 | 1.6–3 GB depending on compute_type | 2.7% | ~15.95% / 11.29% | CPU INT8 only on Mac (~3–5× realtime); no Metal | 5/5 | `initial_prompt`, `hotwords`, `vad_filter`, `hallucination_silence_threshold` | yes | YES — best mitigation tooling in ecosystem | no | no | MIT | Active (SYSTRAN) |

**Bonus phoneme tier** (run alongside, not in place of, the chosen ASR):

| System | Use | Python | License | Status |
|---|---|---|---|---|
| `transformers` + `facebook/wav2vec2-lv-60-espeak-cv-ft` | IPA phoneme transcription | yes | model: CC-BY-NC-4.0 / Apache-2.0 mixed | Maintained in HF transformers |
| `allosaurus` 1.0.2 | universal phone recognition, 2,000+ langs | yes (`pip install allosaurus`) | GPL-3.0 | Older but functional; last release 1.0.2 |
| Custom GOP (CTC posteriors + forced alignment) | pronunciation scoring | yes (NeMo CTC heads or wav2vec2) | depends on backbone | Research-grade, build-your-own |

---

### Per-System Deep Dives

#### 1. Parakeet-TDT-0.6b-v3 via `parakeet-mlx` — RECOMMENDED

**What it is.** NVIDIA's 600M-parameter FastConformer-TDT (Token-and-Duration Transducer) model, released 2025-08-14 as part of the Granary multilingual dataset launch. The `parakeet-mlx` package (senstella, latest v0.5.1 published 2026-02-21 on PyPI, Apache-2.0) is a ground-up MLX reimplementation that runs the model natively on Apple Silicon GPU via Metal. Twenty-six versions shipped — actively maintained.

**Strengths.**
- Open ASR Leaderboard avg WER 6.32% at >3,000× server-GPU RTFx (arXiv:2510.06961 v4, Mar 30 2026, Table 3) — the speed/efficiency Pareto leader.
- ~2 GB peak RAM at inference per the model card's "Hardware Specific Requirements" section — leaves >15 GB headroom on an 18 GB Mac for your IDE, browser, Slack.
- RNN-T/TDT architecture does **not** hallucinate text on silent input the way Whisper does — this matters because interview-practice sessions include thinking pauses.
- Word- and sentence-level timestamps out of the box; built-in streaming via `transcribe_stream(context_size=...)`.
- Confirmed on M3 Pro: an hour of audio transcribed in "just over a minute" on an M3 Pro 36 GB (mikeesto.com blog, 2025).
- CC-BY-4.0 license on the model weights — commercial use allowed with attribution.

**Weaknesses.**
- **No first-class hot-word API in `parakeet-mlx` today.** NVIDIA's NeMo added GPU-accelerated phrase boosting for TDT models in v2.5.0 (PR #14277, late 2025) but the MLX port has not yet implemented context biasing for Parakeet-TDT-v3 — confirmed in NVIDIA-NeMo Issue #14772. Workaround: provide context via beam-decoding configuration and post-process with a Kotlin/Android vocabulary list. If word boosting is critical, run the full NeMo PyTorch stack on CPU/MPS and accept the speed hit.
- Multilingual v3 trades a small amount of English accuracy versus the English-only v2 (6.34% vs ~6.0% avg WER on the leaderboard) — for English-only use, pin `mlx-community/parakeet-tdt-0.6b-v2`.
- No published Persian-accented English WER data — A/B test on your own recordings.

**Minimal Python example (verbatim from the senstella/parakeet-mlx README, 2026):**

```python
from parakeet_mlx import from_pretrained

model = from_pretrained("mlx-community/parakeet-tdt-0.6b-v3")
result = model.transcribe("audio_file.wav")
print(result.text)

# Word- and sentence-level timestamps:
for sentence in result.sentences:
    print(f"[{sentence.start:.2f}s – {sentence.end:.2f}s] {sentence.text}")
```

**Adding Android/Kotlin vocabulary.** Three options, in order of preference:
1. *(Easiest, low quality bias)* Post-process: maintain a Python dict `{"kowin": "Koin", "k m p": "KMP", "jet pack": "Jetpack", "gradel": "Gradle"}` and run regex substitution on the transcript. Crude but reliable for spelling fixes.
2. *(Better)* Run NeMo's GPU-PB word boosting (PR #14277, NeMo 2.5+) by exporting the model to CPU/MPS-PyTorch and using `rnnt_decoding.beam.boosting_tree.key_phrases_file` — accepts a TSV of `phrase\tboost_score` (NVIDIA's `word_boosting.html` docs recommend +20 to +100). Slower but accurate.
3. *(Future)* Watch the parakeet-mlx repo — context biasing is a likely v0.6 feature.

**Verdict.** For an English-conversation-practice tool on M3 Pro, this is the right default. Lowest hallucination risk, best speed, fits the memory budget with room to spare, native MLX. Pair with `transformers` + `wav2vec2-lv-60-espeak-cv-ft` if you want IPA feedback alongside transcription.

---

#### 2. mlx-whisper + Whisper-large-v3-turbo

**What it is.** Apple's official MLX port of Whisper (Apple ML-Explore organization, MIT license). The `mlx-whisper` PyPI package wraps OpenAI's Whisper inference for Metal GPU on Apple Silicon. Ships as part of `mlx-examples`; pinned current LTS in Wyoming/MLX wrappers is `mlx-community/whisper-large-v3-turbo`. Apple released the port in Aug 2024; package still updated through 2026.

**Strengths.**
- 30–40% faster than whisper.cpp on a 14″ M1 Pro per Simon Willison's Aug 13 2024 test (simonwillison.net/2024/Aug/13/mlx-whisper). Large-v3-turbo runs at ~30× realtime on M-series in practice.
- Drop-in `mlx_whisper.transcribe(...)` API, identical to OpenAI Whisper's surface.
- Universal accent coverage from 680,000 hours of weakly-supervised training data, per Radford et al. 2022 ("scaling weakly supervised speech recognition the next order of magnitude to 680,000 hours of labeled audio data," arXiv:2212.04356) — the broadest accent corpus of any model on this list.
- Word timestamps, `initial_prompt`, `suppress_tokens`, full Whisper feature set.

**Weaknesses.**
- **Hallucinates on silence and near-silence.** Extensively documented in openai/whisper Discussions #679, #1783, and #2378. Common mitigations (Silero VAD pre-filter, `condition_on_previous_text=False`, `hallucination_silence_threshold=2.0`, ffmpeg silenceremove) reduce but do not eliminate the issue. Critical when recording yourself thinking between answers.
- Whisper Large-v3 sits at 7.44% avg WER on the leaderboard vs 6.32% for Parakeet (arXiv:2510.06961 v4) — and 15.95% on AMI accented meetings vs Parakeet's 11.31%.
- `mlx-whisper` itself does not bundle VAD; you must add Silero VAD or pre-process with ffmpeg.

**Minimal Python example (verbatim pattern from Apple's mlx-examples / Simon Willison's blog):**

```python
import mlx_whisper

result = mlx_whisper.transcribe(
    "audio.wav",
    path_or_hf_repo="mlx-community/whisper-large-v3-turbo",
    initial_prompt=(
        "Jetpack Compose, KMP, Coroutines, Kotlin, Gradle, MVVM, Koin, "
        "Hilt, Dagger, ViewModel, Flow, StateFlow, suspend, Android."
    ),
    condition_on_previous_text=False,
    word_timestamps=True,
)
print(result["text"])
```

**Adding Android/Kotlin vocabulary.** `initial_prompt` is the canonical mechanism for Whisper. The model treats it as preceding context, which biases tokenization toward those spellings. Limit to ~224 tokens (Whisper's prompt budget). This is the single most effective intervention.

**Verdict.** Strong alternative if your interview answers include unusual proper nouns or you have heavily accented input that Parakeet stumbles on. Worse on speed, memory, and hallucination behavior; better on accent breadth and prompt-engineering control. Use Silero VAD as a preprocessing step.

---

#### 3. WhisperKit (Argmax) — Mac-native Whisper at maximum speed

**What it is.** Argmax's Swift package that compiles Whisper to Core ML and runs the audio encoder on Apple's Neural Engine. Argmax reports "real-time streaming latency of 0.46 s per word while achieving 2.2% WER" on their optimized large-v3-turbo (arXiv:2507.10860v1, ICML 2025); the encoder alone processes 30-second chunks in 218 ms on M3 Max Neural Engine (Table 1, same paper), implying ~137× RTFx for the encoder stage. Actively maintained as of May 2026.

**Strengths.**
- Fastest Whisper on Apple Silicon, period — uses the Neural Engine which is otherwise idle.
- Low peak memory (encoder offloaded from GPU, ~2 GB).
- Built-in streaming transcription with word timestamps.
- Featured by Apple in WWDC sample projects.

**Weaknesses.**
- **Swift-only public API.** Python access is via either (a) `argmax-oss-swift` CLI invoked from subprocess, (b) the bundled OpenAPI server (`Examples/ServeCLIClient`) running locally with a generated Python client, or (c) `whisperkit-bridge` in the anvanvan/mac-whisper-speedtest repo. None is as ergonomic as `parakeet-mlx` or `mlx-whisper`.
- Inherits Whisper-family silence hallucinations.
- Setup complexity is significantly higher than the Python-native options.

**Minimal Python invocation (via the bundled local server's OpenAI-compatible API, from the Examples/ServeCLIClient/Python README):**

```python
from openai import OpenAI

client = OpenAI(base_url="http://localhost:8765/v1", api_key="dummy")
with open("audio.wav", "rb") as f:
    transcription = client.audio.transcriptions.create(
        model="large-v3-turbo",
        file=f,
        prompt="Jetpack Compose, KMP, Coroutines, Kotlin, Gradle, MVVM, Koin.",
    )
print(transcription.text)
```

You launch the local server once with `swift run whisperkit-server`. It's offline — no network calls.

**Adding vocabulary.** `prompt` field on the OpenAI-compatible endpoint maps to Whisper's `initial_prompt`.

**Verdict.** Worth considering only if Parakeet's accent performance on your voice is unacceptable AND you want maximum speed. The Python-ergonomics penalty is real for a senior engineer who values directness.

---

#### 4. NVIDIA NeMo + Parakeet / Canary (PyTorch route)

**What it is.** NVIDIA's official NeMo toolkit (`pip install nemo_toolkit[asr]`) running Parakeet-TDT-0.6b-v3 or Canary-Qwen 2.5B in PyTorch with MPS (Metal Performance Shaders) or CPU on Mac. NeMo 2.5+ added GPU-accelerated phrase boosting (TurboBias / GPU-PB, arXiv:2508.07014) that works with Parakeet TDT models.

**Strengths.**
- **Only path on this list that supports first-class word/phrase boosting for Parakeet-TDT.** You provide a TSV file of `phrase<TAB>boost_score` (NVIDIA's `word_boosting.html` docs recommend +20 to +100), and the decoder rescales token scores at runtime — no retraining needed.
- Access to Canary-Qwen 2.5B (5.63% leaderboard WER, currently #1–#4 depending on Open ASR LB version).
- Full word-level timestamps, beam search, lexicon injection.

**Weaknesses.**
- **No Metal-optimized NeMo path on Mac.** You run on CPU (slow, ~1–2× realtime for Parakeet 0.6B) or PyTorch MPS (faster but with known operator-coverage gaps).
- Canary-Qwen at 5.12 GB BF16 + activations puts you near the memory ceiling on 18 GB once macOS and other apps are running.
- Heavy install: NeMo's dependency tree is large (PyTorch Lightning, Hydra, NVIDIA-specific extensions).

**Minimal Python (from build.nvidia.com/nvidia/parakeet-tdt-0_6b-v3):**

```python
import nemo.collections.asr as nemo_asr

asr_model = nemo_asr.models.ASRModel.from_pretrained(
    model_name="nvidia/parakeet-tdt-0.6b-v3"
)
result = asr_model.transcribe(["audio.wav"])
print(result[0].text)
```

**Adding vocabulary (real example from NeMo docs):**

```python
# boost.tsv:
#   Jetpack Compose<TAB>50
#   KMP<TAB>50
#   Coroutines<TAB>40
#   Koin<TAB>60
#   Gradle<TAB>40
asr_model.change_decoding_strategy({
    "strategy": "malsd_batch",
    "beam": {
        "beam_size": 5,
        "boosting_tree": {"key_phrases_file": "boost.tsv", "context_score": 1.0},
    }
})
```

**Verdict.** Use this if word-boosting on your Android/Kotlin jargon turns out to be essential and `initial_prompt` (Whisper) plus post-processing (Parakeet-MLX) prove insufficient. Otherwise the Mac speed penalty is too steep.

---

#### 5. faster-whisper (with Whisper-large-v3-turbo)

**What it is.** SYSTRAN's CTranslate2-based reimplementation of Whisper. The de facto production Whisper runtime since 2023; v1.2+ adds first-class `hotwords` parameter and `hallucination_silence_threshold`. Actively maintained through 2026.

**Strengths.**
- **Best-in-class hallucination mitigation tooling:** `vad_filter=True` (Silero VAD built-in), `hallucination_silence_threshold`, `condition_on_previous_text`, `log_prob_threshold`, all in one API. Whisper-derivative apps like Superwhisper now ship "anti-hallucination parameters to faster-whisper transcription" (Superwhisper changelog, Feb 23 2026).
- `hotwords="Jetpack Compose, Kotlin, Gradle, Koin"` is a real parameter, not pseudocode.
- Word-level timestamps, batched inference, INT8 quantization for low memory.
- MIT license.

**Weaknesses.**
- **CPU-only on Mac.** CTranslate2 has no Metal GPU backend; on M3 Pro you get ~3–5× realtime for large-v3-turbo at INT8 — fine for interview practice (transcribing 5-minute answers in ~1 minute), terrible for live streaming.
- Inherits all Whisper accuracy ceilings (~7.4% leaderboard WER, 15.95% on AMI).

**Minimal Python (verbatim from SYSTRAN/faster-whisper README, 2025):**

```python
from faster_whisper import WhisperModel

model = WhisperModel("large-v3-turbo", device="cpu", compute_type="int8")
segments, info = model.transcribe(
    "audio.wav",
    beam_size=5,
    language="en",
    vad_filter=True,
    hotwords="Jetpack Compose KMP Coroutines Kotlin Gradle MVVM Koin",
    initial_prompt="Mobile Android engineering interview about Jetpack Compose and KMP.",
    condition_on_previous_text=False,
)
for seg in segments:
    print(f"[{seg.start:.2f}s -> {seg.end:.2f}s] {seg.text}")
```

**Verdict.** The robust, "boring" choice. If Parakeet's lack of hot-word support frustrates you and you don't need real-time streaming, faster-whisper is the most production-tested path to good English transcription with Android-jargon hot-words on a Mac. Accept the CPU speed penalty.

---

### Pronunciation Feedback (Bonus)

Two complementary tools fit your stack:

**Wav2Vec2Phoneme (HF transformers, `facebook/wav2vec2-lv-60-espeak-cv-ft`):**

```python
from transformers import Wav2Vec2Processor, Wav2Vec2ForCTC
import torch, librosa

processor = Wav2Vec2Processor.from_pretrained("facebook/wav2vec2-lv-60-espeak-cv-ft")
model = Wav2Vec2ForCTC.from_pretrained("facebook/wav2vec2-lv-60-espeak-cv-ft")
audio, _ = librosa.load("audio.wav", sr=16000)
ids = processor(audio, sampling_rate=16000, return_tensors="pt").input_values
phonemes = processor.batch_decode(torch.argmax(model(ids).logits, dim=-1))
print(phonemes)  # eSpeak-style IPA sequence
```

Compare against an `espeak-ng` reference phoneme string for the prompt text, compute edit distance per phoneme, and you have a Goodness-of-Pronunciation proxy without training anything.

**Allosaurus (`pip install allosaurus`, GPL-3.0):**

```python
from allosaurus.app import read_recognizer
model = read_recognizer()
print(model.recognize("audio.wav", lang_id="eng"))  # IPA phones
```

Universal — covers 2,000+ languages — but the package is older (last PyPI release 1.0.2). Useful if you want to compare your L1 (Persian/Farsi) phone inventory against your produced English phones.

For real GOP scoring (numerical pronunciation score per phoneme), combine NeMo Citrinet CTC posteriors with a CMU pronunciation dictionary and Viterbi forced alignment, per the open-source brainiall.com pipeline (dev.to writeup, 2026). This is a build-it-yourself project, not a turnkey package.

---

## Recommendations

**Stage 1 (this week).** Install Parakeet-MLX and run 10 of your own recorded interview answers through it:

```bash
uv venv --python 3.11 && source .venv/bin/activate
uv pip install parakeet-mlx
parakeet-mlx my_answer.wav --highlight-words --output-format json
```

Score the transcripts by hand for: (a) accuracy on Android jargon, (b) accuracy on general English, (c) presence of any hallucinated text in your pauses. Threshold to advance: ≤2 jargon errors per minute and zero pause-hallucinations.

**Stage 2 (if Parakeet jargon errors > 2/min).** Add a post-processing substitution dict for common misspellings (e.g., "kowin" → "Koin", "k m p" → "KMP"). Re-test. Threshold to advance: ≤1 jargon error per minute.

**Stage 3 (if Stage 2 still insufficient).** Switch to faster-whisper + large-v3-turbo with `hotwords="Jetpack Compose KMP Coroutines Kotlin Gradle MVVM Koin"` and `vad_filter=True`. Accept ~10× slower transcription for materially better jargon recognition.

**Stage 4 (pronunciation feedback).** Add `facebook/wav2vec2-lv-60-espeak-cv-ft` as a second pass: for each utterance, transcribe text with Parakeet AND extract IPA with wav2vec2-phoneme, then compare to the espeak-ng reference IPA for your text. Surface the worst-mismatched phonemes as a feedback panel.

**Triggers that should change this ranking:**

1. **A Mac-native MLX or CoreML port of Canary-Qwen 2.5B ships** with ≤6 GB RAM footprint. The +0.7 percentage-point WER win over Parakeet would matter for transcript quality.
2. **Cohere-Transcribe-03-2026** (Apache-2.0, 2B params, 5.42% leaderboard WER) gets a maintained MLX/CoreML build. Today only an OpenVINO/Intel build exists.
3. **`parakeet-mlx` adds context-biasing** (likely v0.6) — would eliminate the only reason to consider faster-whisper.
4. **A public benchmark of any of these models on Persian-accented English** is published. Currently this is a literature gap.

---

## Caveats

- **The 18 GB RAM filter excluded otherwise top-ranked models.** Canary-Qwen 2.5B (5.12 GB BF16 on disk, expected ~7–8 GB peak inference) is technically loadable but leaves uncomfortably little headroom for an IDE; Granite Speech 3.3 8B (~17 GB) is excluded outright.
- **No Persian-accented English WER for any of these systems exists in public literature.** The closest published Persian-accent ASR work (arXiv:2510.09528, Oct 2025) tests Whisper tiny/base/medium on Persian itself, not on Persian-accented English. A/B test Parakeet vs faster-whisper on 20–30 of your own recordings before committing — vendor accent claims without benchmarks are unverified.
- **Hallucination behavior is architectural, not configurable.** No amount of prompt engineering removes Whisper's silence-hallucination tendency entirely; only switching to a transducer (Parakeet RNN-T/TDT) does. This is the single most decisive non-WER reason for the top recommendation.
- **WhisperKit's 2.2% WER number** is from Argmax's ICML 2025 paper (arXiv:2507.10860v1) using their proprietary optimized large-v3-turbo on Argmax's internal evaluation set, not directly comparable to the Open ASR Leaderboard 7.83% figure for the same base model. Treat as a vendor-favorable measurement.
- **NeMo word-boosting on Mac is officially unsupported.** It works in PyTorch MPS or CPU mode, but NVIDIA's documentation assumes CUDA — expect rough edges.
- **codesota.com and northflank.com leaderboard summaries** in some search snippets disagreed slightly with arXiv:2510.06961. I prioritized the arXiv paper (which is the leaderboard maintainers' own publication) as primary evidence.
- **The ~50× server-GPU RTFx gap between Parakeet and Whisper-turbo applies only to A100/H100 leaderboard runs.** On Apple Silicon, the practical gap measured by anvanvan/mac-whisper-speedtest is closer to 2× (parakeet-mlx 0.50 s vs mlx-whisper 1.02 s for the same short clip). Plan capacity from the Apple-Silicon number, not the leaderboard number.