# Local TTS for an M3 MacBook: Best Offline Options for an Android Engineer Practicing Interviews (May 2026)

## TL;DR
- **Top pick: Kokoro-82M** via the `kokoro` (PyTorch+MPS) or `kokoro-mlx`/`mlx-audio` package — Apache 2.0, ~330 MB on disk, ~600 MB resident, 28 English voices (US + British RP), and first-class IPA phoneme override via Misaki G2P (`[Kokoro](/kˈOkəɹO/)`). It is the highest-ranked open-weights model accessible on consumer Macs in the Artificial Analysis Speech Arena (ELO 1056) and the only finalist where Android jargon overrides are a 5-character syntax change.
- **Strong alternative for setup-aversion: Piper (piper1-gpl v1.4.2, GPL-3.0)** — fastest CPU-only inference (~35 ms P50 latency per ~25-phoneme English clause on M-class silicon per the piper-plus comparison table), embedded espeak-ng, native `[[ phonemes ]]` syntax for IPA overrides. Voice quality is a tier below Kokoro but it is rock-stable and deterministic.
- **Strong alternative for maximum naturalness: Chatterbox Turbo via mlx-audio** — MIT license, MLX-accelerated, preferred 63.75% of the time over ElevenLabs in Resemble's vendor-commissioned Podonos blind test (n=30, 8 samples, 80 total ratings), but >1 GB model, no phoneme/IPA hook, and the `mlx-audio` Python entrypoint is finicky (the `generate_audio()` helper silently routes to Kokoro unless you call `load_model("mlx-community/chatterbox-...")` explicitly).

## Key Findings

1. **The Apple-Silicon-optimized local TTS field has consolidated around two runtimes.** Apple's MLX framework (`mlx-audio` 0.4.x by Prince Canuma, `kokoro-mlx` by gabrimatic, `f5-tts-mlx` by Lucas Newman, `csm-mlx` by senstella) and ONNX Runtime on macOS arm64 (Piper, `kokoro-onnx`, `pykokoro`). PyTorch with the MPS backend remains a usable third path (the upstream `kokoro` package and Chatterbox both work this way) but is generally slower per-watt than MLX for the same model size.

2. **The cleanest pre-processing story belongs to dictionary-based G2P stacks (Kokoro/Misaki, Piper/eSpeak-NG).** For Android jargon — *Hilt*, *Koin*, *KMP*, *Jetpack*, *Coroutines* — these let you ship IPA overrides without retraining. Large autoregressive LLM-based TTS (Orpheus, Chatterbox, Fish S2 Pro, Dia, F5) have no equivalent lexicon API; they rely on the LLM's tokenizer plus prompt conditioning, which is unreliable for novel acronyms in repeated practice.

3. **The TTS arena leaderboards as of April 2026 are still dominated by closed-source models** — Vocu V3.0, Inworld TTS MAX, CastleFlow, Hume Octave, ElevenLabs v3 (per HF TTS-Arena V2 historical view, April 2026). Among open-weights local models the order on Artificial Analysis is Fish Audio S2 Pro (ELO 1128) > Step Audio EditX > Magpie-Multilingual > **Kokoro-82M v1.0 (ELO 1056)** > StyleTTS 2. Fish S2 Pro is research-license-only and 4+ GB on disk, so Kokoro wins the "open-and-Mac-friendly" intersection.

4. **License hygiene matters more than the marketing pages suggest.** F5-TTS code is MIT but the upstream weights are CC-BY-NC-4.0 — non-commercial only. Orpheus is split: code Apache 2.0, **weights inherit the Llama 3.2 Community License** (acceptable for personal practice, restrictive for commercial product). Piper v1.3+ is **GPL-3.0** (changelog: "Change license to GPLv3", v1.3.0 released July 10, 2025). Kokoro and Chatterbox are the only permissive (Apache 2.0 / MIT) finalists.

5. **For shadowing-style repeated listening, naturalness compounds.** That argues for Kokoro or Chatterbox over Piper despite Piper's lower setup friction, and against very-large autoregressive models (Orpheus, Dia) which exhibit non-deterministic prosody drift across runs of the same text. Kokoro is also deterministic given fixed inputs, which is valuable when practicing the *same* answer aloud repeatedly.

## Details

### Evidence Table

| Dimension | Kokoro-82M | Piper (piper1-gpl) | Chatterbox (via mlx-audio) | F5-TTS-MLX | Orpheus 3B (GGUF) |
|---|---|---|---|---|---|
| Architecture | StyleTTS2 text encoder + ISTFTNet decoder, 82 M params | VITS, ONNX-exported, ~25–60 M params per voice | LLaMA-style 0.5 B backbone + S3 token codec (Turbo: 350 M, single-step decoder) | Flow-matching DiT, 335 M params, non-autoregressive | Llama-3.2-3B fine-tune emitting SNAC audio tokens |
| License | Apache 2.0 (weights + code) | **GPL-3.0** (code + embedded espeak-ng) since v1.3.0 (Jul 10, 2025) | MIT (code + weights, all 3 variants) | Code MIT; **weights CC-BY-NC-4.0** | Code Apache 2.0; **weights Llama 3.2 Community License** (maintainer-confirmed in issue #33) |
| Apple Silicon optimization | **MLX native** (kokoro-mlx, mlx-audio) **+ MPS** (kokoro pkg via `PYTORCH_ENABLE_MPS_FALLBACK=1`) | **CPU ONNX** on macOS arm64 wheels (no CoreML/MLX upstream) | **MLX via mlx-audio** (third-party port); community PyTorch+MPS fork also exists | **Native MLX** (lucasnewman/f5-tts-mlx) | **No native MPS path**; CUDA-only vllm; GGUF via llama.cpp/LM Studio Metal only |
| Python package | `pip install kokoro>=0.9.4` or `pip install kokoro-mlx` | `pip install piper-tts` (v1.4.2, Apr 2, 2026) | `pip install mlx-audio` (v0.4.0, Apr 28, 2026) | `pip install f5-tts-mlx` | No first-class pip path; assemble via `llama-cpp-python` or LM Studio HTTP |
| Model size on disk | ~330 MB bf16; ~80 MB int8 | ~25–60 MB per voice ONNX | ~300 MB (4/6-bit) to ~1 GB (fp16 Turbo) | 1.35 GB safetensors (4-bit ≈ 350 MB) | 2.0–3.3 GB (Q4_K_M – Q8_0 GGUF) |
| Resident RAM | ~600 MB (kokoro-tts-mcp README) | <200 MB | ~1.5–2 GB | ~2–3 GB | ~4–6 GB (Q4) |
| Inference speed on M3 | ~1.5 s per request after warm-up (kokoro-tts-mcp); RTF ≈ 0.003–0.01 implied via mlx-audio | ~35 ms P50 latency for ~25-phoneme clause on M2 Max (piper-plus benchmark — upstream Piper not re-measured on M3) | "Fast inference on Apple Silicon (M1/M2/M3/M4) using MLX" (Jimmi42 HF card); exact RTF unverified | ~4 s sample on M3 Max per current GitHub README; HF card still says ~11 s (flag) | ~5–10 audio frames/s; usable but well below real-time for long answers |
| Voice naturalness | **High** — ELO 1056 on Artificial Analysis Speech Arena (top open-weights accessible on consumer Macs) | **Medium** — natural for short utterances, slight synthetic edge on long prose; no published MOS for arm64 builds | **Very high** — 63.75% preference across 8 samples / 80 ratings vs ElevenLabs in Resemble's Podonos blind test | **High** for flow-matching | **High** — community MOS ~4.2 (Inferless 12-model comparison; CodeSOTA 2026 leaderboard) |
| Pronunciation control | **Best-in-class**: IPA override `[word](/IPA/)` via Misaki; phoneme-only input via `KPipeline`; gold+silver dictionary ~170 k entries; eSpeak-NG fallback for OOV | **Good**: `[[ phonemes ]]` inline IPA syntax in v1.3+; eSpeak-NG embedded in wheel; per-voice lexicon files | **None**: no IPA hook; emotion tags `[laugh]` `[sigh]` only; pronunciation = whatever LLM tokenizer produces | **None** in MLX port; reference-audio conditioning only | **None**: emotion tags `<laugh>` `<sigh>` only; relies on Llama BPE for jargon |
| SSML / prosody | `speed=` param; pause/length via Misaki; `pykokoro` adds SSMD pauses + say-as | `length_scale`, `noise_scale`, `noise_w_scale`, `volume` in `SynthesisConfig` | `exaggeration` 0–2 emotion slider; `cfg_weight`; speaker prompt audio | flow-step count, CFG strength; no rate control | tag-based only |
| English voices | 11 F + 9 M American, 4 F + 4 M British (28 total v1.0) | 30+ English voices on HF (`en_US-lessac-medium`, `en_GB-alba-medium`, etc.) | 1 default + zero-shot clone from 5-s reference | 1 default + zero-shot clone | 8 named voices: tara, leah, jess, leo, dan, mia, zac, zoe |
| Maintenance | Active; misaki + kokoro packages updated through 2026 | Active; v1.4.2 released Apr 2, 2026 | Active (Resemble); mlx-audio updates via Blaizzy | Sporadic (single maintainer) | Canopy active for code; no MLX path planned |
| Python ergonomics (1–5) | 5 | 5 | 3 (Kokoro-default bug if `generate_audio` called without `load_model`) | 4 | 2 (assemble GGUF stack yourself) |

### Per-System Deep Dives

#### 1. Kokoro-82M — recommended default

Kokoro is an 82-million-parameter StyleTTS2-derived model released by *hexgrad* on December 25, 2024 and upgraded to v1.0 in late January 2025 (per the hexgrad/Kokoro-82M EVAL.md note: "Screenshots captured February 26, 2025, about 1 month after v1.0 model release"). It is the highest-ranked open-weights TTS model on the Artificial Analysis Speech Arena with ELO 1056 as of 2026, behind only proprietary models from OpenAI, Cartesia, ElevenLabs and the open-weights but research-licensed Fish S2 Pro. Weights and code are Apache 2.0; the model card explicitly invites commercial deployment.

**Strengths.** Three things matter for this user. First, naturalness: arena ELO puts Kokoro well above Piper and at parity with much larger models. Second, **the G2P pipeline is the cleanest of any local TTS**. Kokoro uses Misaki, a dictionary-first phonemizer with ~170 k gold/silver entries plus an eSpeak-NG fallback for OOV words. You can override any pronunciation inline with Markdown-like syntax: `[Hilt](/hˈɪlt/)`, `[Koin](/kˈɔɪn/)`, `[KMP](/kˈeɪɛmpˈi/)`. Third, **Apple Silicon optimization is first-class**: `kokoro-mlx` runs the model with no PyTorch dependency; `mlx-audio` provides an MLX-native pipeline with quantization (`--q-bits 4`, MXFP4); the upstream `kokoro` PyTorch package picks up MPS via `PYTORCH_ENABLE_MPS_FALLBACK=1`.

**Weaknesses.** Single-speaker per generation (no zero-shot cloning) — irrelevant for read-aloud. Max 510 phonemes per chunk, so long answers need splitting (the package does this automatically via `split_pattern`). Python 3.13 has known dependency conflicts (`spacy`/`pydantic`); use Python 3.12.

**Minimal Python inference (verbatim from `hexgrad/kokoro` PyPI README):**

```python
from kokoro import KPipeline
import soundfile as sf

pipeline = KPipeline(lang_code='a')  # 'a'=American, 'b'=British

text = '''
[Hilt](/hˈɪlt/) is a dependency injection library for Android,
built on top of [Dagger](/dˈæɡɚ/).
'''
generator = pipeline(text, voice='af_heart', speed=1.0)
for i, (gs, ps, audio) in enumerate(generator):
    sf.write(f'{i}.wav', audio, 24000)
```

For MLX acceleration on M3, swap the runtime:

```python
from kokoro_mlx import KokoroTTS
tts = KokoroTTS.from_pretrained("mlx-community/Kokoro-82M-bf16")
tts.save("Define MVVM in the context of Jetpack Compose.",
         "out.wav", voice="bm_george")  # British male
```

**Lexicon integration for Android jargon.** Build a Python dict mapping jargon → IPA and rewrite text before pipeline call:

```python
JARGON = {
    "Jetpack":   "/dʒˈɛtpæk/",
    "Compose":   "/kəmpˈoʊz/",
    "Coroutine": "/koʊɹˈuːtiːn/",
    "Retrofit":  "/ɹˈɛtɹoʊfɪt/",
    "Gradle":    "/ɡɹˈeɪdəl/",
    "Hilt":      "/hˈɪlt/",
    "Koin":      "/kˈɔɪn/",
    "Dagger":    "/dˈæɡɚ/",
    "ViewModel": "/vjˈuːmɒdəl/",
}
import re
def annotate(t):
    for w, ipa in JARGON.items():
        t = re.sub(rf'\b{w}\b', f'[{w}]({ipa})', t)
    return t
```

A 10-line preprocessor Misaki will honor verbatim. No retraining, no fine-tuning.

**Verdict.** Best default for this user. Apache 2.0, M3-optimized, professional voice quality (`af_heart`, `af_bella`, `bm_george`, `bf_emma` are graded highest on the official VOICES.md), and the only finalist where Android terms become a dict-update away from correct pronunciation.

#### 2. Piper (piper1-gpl) — recommended fallback

Piper is the production VITS-based TTS originally by Mike Hansen, now hosted at the OHF-Voice org. v1.4.2 (April 2, 2026) ships macOS arm64 wheels with espeak-ng embedded directly in the wheel — no separate `piper-phonemize` step needed.

**Strengths.** Smallest footprint of any finalist (most English voices are 25–60 MB ONNX). Fast on M3 CPU alone — the piper-plus comparison table measures Piper's architecture at P50 ≈ 35 ms for a ~25-phoneme English clause on M2 Max (ONNX Runtime 1.17). Native `[[ … ]]` syntax for raw phoneme injection (added in v1.3.0). Predictable, deterministic prosody — same input produces identical output, which matters for shadowing the *same* answer repeatedly. 30+ English voices including General American (`en_US-lessac-medium`, `en_US-amy-medium`) and British (`en_GB-alba-medium`, `en_GB-jenny_dioco-medium`).

**Weaknesses.** Voice quality is a clear tier below Kokoro — articulate but slightly synthetic on long prose. License changed to **GPL-3.0 in v1.3.0 (released July 10, 2025; changelog: "Change license to GPLv3")**; if you ever vendor the runtime into a commercial Android app, that matters. No native MLX/CoreML acceleration — the piper-plus README explicitly notes piper1-gpl was *not* re-benchmarked on Apple Silicon, only the upstream Piper architecture.

**Minimal Python inference (verbatim from official `piper1-gpl/docs/API_PYTHON.md`):**

```python
import wave
from piper import PiperVoice, SynthesisConfig

voice = PiperVoice.load("./en_US-lessac-medium.onnx")
syn_config = SynthesisConfig(
    volume=1.0,
    length_scale=1.0,    # 1.0 = normal, 1.2 = slower
    noise_scale=0.667,
    noise_w_scale=0.8,
    normalize_audio=True,
)
with wave.open("out.wav", "wb") as f:
    voice.synthesize_wav(
        "[[ dʒˈɛtpæk ]] Compose makes Android UI declarative.",
        f, syn_config=syn_config)
```

**Lexicon integration.** Piper accepts raw phonemes inline with `[[ phonemes ]]`. Same preprocessor as Kokoro but emit eSpeak-NG IPA between double brackets. eSpeak-NG can be queried directly: `phonemizer.phonemize("Hilt", backend="espeak", language="en-us", with_stress=True)`.

**Verdict.** Pick if you want a no-MLX, no-PyTorch, single-binary setup that runs on CPU alone and never surprises you. Use it as the failover when Kokoro has a dependency issue, or for offline travel where you want minimal RAM pressure.

#### 3. Chatterbox (Resemble AI) via mlx-audio — for maximum naturalness

Chatterbox is Resemble AI's MIT-licensed open-source TTS family, with three variants: original 500 M, Multilingual 500 M (23 languages), and **Turbo 350 M** (single-step decoder, paralinguistic tags). Per the Resemble/Podonos page, "63.75% of listener ratings favoured Chatterbox over ElevenLabs across 8 audio samples" (30 evaluators × 8 samples = 80 ratings total; per-sample breakdown public at podonos.com/resembleai/chatterbox).

**Strengths.** Best-in-class naturalness among permissively licensed local models. Built-in `exaggeration` slider (0.0–2.0) for emotion intensity — no SSML required. MLX path is supported through `mlx-audio` and `mlx-community/chatterbox-6bit` / `mlx-community/chatterbox-turbo-fp16`. Optional zero-shot voice cloning from a 5-second reference if you want to use your own interviewer voice (not required for default English).

**Weaknesses.** **No phoneme override path** — pronunciation of Android jargon is whatever Chatterbox's tokenizer + LLM backbone produce, which can vary run-to-run. This is the single biggest issue for the user's domain. Watermark (PerTh) is silently embedded in every output; inaudible, but worth noting. Setup is finicky: the **`generate_audio()` helper in mlx-audio defaults to Kokoro pipeline if called without an explicit model load** — the `Jimmi42/chatterbox-turbo-apple-silicon` HF card flags this verbatim ("The key insight: Use CLI module (python -m mlx_audio.tts.generate) instead of the Python API's generate_audio() function. The CLI properly routes to Chatterbox Turbo pipeline, while the Python function defaults to Kokoro").

**Minimal Python inference (verbatim from `mlx-community/chatterbox-6bit` HF model card):**

```python
from mlx_audio.tts.utils import load_model
from mlx_audio.tts.generate import generate_audio

model = load_model("mlx-community/chatterbox-6bit")
generate_audio(
    model=model,
    text="Explain how Jetpack Compose differs from the View system.",
    file_prefix="answer_01",
)
```

Or via the CLI route (recommended by `Jimmi42/chatterbox-turbo-apple-silicon`):

```bash
python -m mlx_audio.tts.generate \
    --model mlx-community/chatterbox-6bit \
    --text "Define MVVM in the context of Jetpack Compose."
```

**Lexicon integration.** Best you can do is spell-out hacks: replace `KMP` with `K M P` and `Koin` with `Koy-n` in the input string. There is no IPA or G2P override. For an interview-prep loop where the same jargon appears constantly, this is a recurring cost.

**Verdict.** Use if naturalness trumps pronunciation control. For most interview-prep use, the lack of an IPA override is a downgrade vs Kokoro despite Chatterbox's higher absolute voice quality.

#### 4. F5-TTS (via f5-tts-mlx) — high quality but license-restricted

F5-TTS is a flow-matching diffusion-transformer TTS from Yushen Chen et al., with an MLX port by Lucas Newman. The MLX port runs natively on M-series silicon and generates roughly 4 seconds of audio in ~4 seconds on M3 Max per the current GitHub README (the HuggingFace model card and the Swift port still cite ~11 seconds — flag the discrepancy; the GitHub number likely reflects a later optimization).

**Strengths.** Non-autoregressive — predictable wall-clock time per chunk. Good naturalness; the upstream F5 model scored ELO 1339 on the (now-deprecated) TTS Arena legacy leaderboard. Excellent at preserving prosody from a reference audio clip.

**Weaknesses.** **The license is the killer**: the f5-tts-mlx *code* is MIT (per pyproject.toml: `license = {text = "MIT"}`), but the **upstream weights are CC-BY-NC-4.0** — non-commercial use only. For a private interview-practice setup this is fine (personal study is non-commercial), but the user should be aware before publishing anything derived from the audio. The MLX port has no lexicon or IPA override — same gap as Chatterbox for technical jargon. Model is 1.35 GB on disk in fp16 (≈350 MB at 4-bit quantization).

**Minimal Python inference (verbatim from `lucasnewman/f5-tts-mlx` README):**

```bash
python -m f5_tts_mlx.generate --text "How does Koin's service locator differ from Dagger's compile-time DI?"
```

Programmatic:

```python
from f5_tts_mlx.generate import generate
generate(
    generation_text="Discuss the Android lifecycle in Jetpack Compose.",
    output_path="answer.wav",
)
```

**Lexicon integration.** None. Spell-out hacks in input string only.

**Verdict.** Skip unless you specifically want a flow-matching model for its stable timing. Kokoro and Chatterbox both offer better practical ergonomics for this user.

#### 5. Orpheus 3B — high-end output, painful M3 path

Orpheus 3B by Canopy Labs is a Meta Llama-3.2-3B fine-tune that emits SNAC audio tokens, decoded into 24 kHz speech. Outputs are widely regarded as near-human; the codersera.com macOS guide (May 2026) cites: "Orpheus-3b-0.1-ft scores ~4.2 — close to Sesame CSM 1B and within striking distance of ElevenLabs v2 on conversational text" (sourcing Inferless's 2025 12-model comparison and CodeSOTA's 2026 speech leaderboard).

**Strengths.** Most expressive default voices of any finalist (8 named English speakers — tara, leah, jess, leo, dan, mia, zac, zoe). Emotion tags work well: `<laugh>`, `<sigh>`, `<chuckle>`, `<cough>`. Apache 2.0 code license.

**Weaknesses.** **There is no native PyTorch MPS path.** The official `orpheus-speech` Python package depends on `vllm` and requires a CUDA-built PyTorch — on M3 it raises `Torch not compiled with CUDA enabled` (open issue canopyai/Orpheus-TTS#178). Canopy Labs explicitly points Mac users to llama.cpp/GGUF route. Resident memory is 4–6 GB at Q4_K_M. **Weights license is the Llama 3.2 Community License (derivative work)** — *not* Apache 2.0 despite some third-party blogs claiming otherwise. The maintainer (amuvarma13) confirmed this verbatim in GitHub issue canopyai/Orpheus-TTS#33: "the code in this repo is Apache 2 now added, the model weights are the same as the Llama license as they are a derivative work." No phoneme/lexicon override. Generation is autoregressive — usable for batch generation of prepared answers, painful for fast iteration.

**Minimal local inference on M3 (community route — there is no clean pip path):**

```bash
# 1. Install llama.cpp via Homebrew
brew install llama.cpp
# 2. Run the Q8_0 GGUF model directly
llama-cli --hf-repo PkmX/orpheus-3b-0.1-ft-Q8_0-GGUF \
          --hf-file orpheus-3b-0.1-ft-q8_0.gguf \
          -p "<|audio|>tara: Define the Android activity lifecycle."
# 3. Decode emitted custom_token_NNNNN frames through SNAC
```

In practice you run the small Python client `gguf_orpheus.py` from `isaiahbjork/orpheus-tts-local`, which hits an LM Studio HTTP endpoint and pipes the emitted audio tokens through the SNAC codec.

**Lexicon integration.** None.

**Verdict.** Only choose if you have already invested in an LM Studio + GGUF workflow and want the most expressive default voices. For a fresh interview-prep setup the friction is not worth it.

### What we deliberately excluded

- **Sesame CSM 1B**: MLX port exists (`senstella/csm-mlx`, `mlx_audio.tts.generate --model mlx-community/csm-1b`) and runs on M3 with ~8.1 GB resident, but it is a *conversational* model fine-tuned for dialogue, not read-aloud — its prosody assumes turn-taking.
- **Dia 1.6B (Nari Labs)**: dialog/podcast-focused with `[S1]`/`[S2]` speaker tags. MLX-community has a 4-bit conversion (`mlx-community/Dia-1.6B-4bit`), but the model is tuned for two-speaker exchanges, not interview-answer monologue.
- **Fish Audio S2 Pro**: highest open-weights ELO (1128) and MLX-quantized versions exist (`mlx-community/fish-audio-s2-pro-bf16` ~8 GB, `majentik/fishaudio-s2-pro-MLX-8bit` ~4.5 GB), but the license is the "Fish Audio Research License" — research/non-commercial only — and the 4 B-param Slow AR makes it heavy on a baseline M3.
- **XTTS v2 / Coqui**: Coqui AI announced shutdown in December 2023 (servers offline December 11, 2023, company closed by January 2024 per coqui-ai/TTS discussion #3489, where co-founder Josh Meyer posted "Coqui is shutting down"). Community forks exist but the codebase is unmaintained on macOS arm64 and quality now trails Kokoro on English.

## Recommendations

**Stage 1 — Today (M3, any RAM tier).** Install Kokoro via the MLX path:

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install kokoro-mlx soundfile
# OR for the broader mlx-audio toolkit:
pip install mlx-audio
brew install espeak-ng   # for OOV fallback in Misaki
```

Build a 20–50 entry Android jargon lexicon (Hilt, Koin, KMP, Dagger, Retrofit, ViewModel, LiveData, etc.) as a Python dict mapping word→IPA. Run a one-time pass with each entry to listen and adjust. Use voice `af_heart` (warm female American) or `bm_george` (calm male British) for shadowing — both are graded highest on the official Kokoro VOICES.md.

**Stage 2 — Add Piper as a redundancy check.** `pip install piper-tts` and download `en_US-lessac-medium` plus `en_GB-alba-medium`. When you encounter a Kokoro pronunciation you cannot fix with IPA (rare), regenerate the same line with Piper as a sanity check. This also gives you a low-RAM CPU fallback for travel.

**Stage 3 — Optional naturalness upgrade.** If after a week of using Kokoro the voice quality limits you, add Chatterbox Turbo via `mlx-audio` for the *prepared answers* (long-form, polished output) and keep Kokoro for *question generation* (frequent, jargon-heavy short text). This hybrid plays to each model's strength.

**Thresholds that would change the ranking:**

1. **Misaki ships a non-eSpeak fallback model** (TODO listed by the maintainer): Kokoro's lead widens further; reconsider whether you need a second engine at all.
2. **Chatterbox ships an MLX-native G2P / IPA hook**: it would tie or beat Kokoro for this user.
3. **A new model on HF TTS-Arena V2 surpasses Kokoro's 1056 ELO with an MLX port and Apache/MIT license**: re-evaluate. Currently the next nearest open-weights candidate (Fish S2 Pro at 1128 ELO) is research-license-only.
4. **Hardware upgrade to M3 Pro/Max with ≥36 GB**: Orpheus 3B and Fish S2 Pro become comfortable, and Fish S2 Pro becomes the naturalness winner *if* the Fish Audio Research License's non-commercial scope is acceptable (private interview practice qualifies).

## Caveats

- **Subjective benchmarks.** Both Artificial Analysis Speech Arena and HF TTS-Arena V2 are blind-vote ELO systems with self-selecting voter pools; ELO 1056 vs 1128 is a meaningful gap but not a guarantee for any specific listener's preference. Audition `af_heart`, `bm_george`, `bf_emma`, and one Chatterbox voice yourself before committing to a long shadowing block.
- **Vendor-run blind tests.** Resemble's 63.75% Chatterbox-over-ElevenLabs result was a Podonos study commissioned by Resemble, n=30 evaluators across 8 audio samples (80 total ratings). Treat as suggestive, not definitive; the full per-sample breakdown is at podonos.com/resembleai/chatterbox.
- **F5-TTS timing discrepancy.** The `lucasnewman/f5-tts-mlx` GitHub README says "generated in ~4 seconds on an M3 Max MacBook Pro"; the HuggingFace model card and Swift port still say "~11 seconds." Most likely the GitHub number reflects an optimization the HF card has not been updated for. Either way, F5 is slower than Kokoro on M3.
- **License inheritance.** Orpheus weights = Llama 3.2 Community License (acceptable for noncommercial personal practice); F5-TTS weights = CC-BY-NC-4.0 (noncommercial); Fish S2 Pro = Fish Audio Research License (noncommercial). For private interview practice all are fine; if you later publish recordings on a portfolio site, recheck the specific weight licenses.
- **Apple Silicon "supported" vs "optimized."** Piper runs on M3 but uses CPU ONNX, not Metal/MLX. Chatterbox upstream is PyTorch+MPS (community-patched); the MLX route is via the third-party `mlx-audio` port. Kokoro and F5-TTS have *first-party* MLX implementations. Orpheus runs only via llama.cpp Metal (Metal-accelerated but not MLX-native).
- **Python ergonomics warning for mlx-audio.** Multiple HF model cards explicitly note that `mlx_audio.tts.generate.generate_audio()` routes to Kokoro by default unless you `load_model("mlx-community/<other>")` first. If your script "just produces Kokoro voice" when you expected Chatterbox or another model, this is why — verified verbatim on the `Jimmi42/chatterbox-turbo-apple-silicon` HF card.

---

### Plan completion table

| Plan item | Covered |
|---|---|
| 1. Landscape scan (6–10 candidates) | Yes — 9 covered (5 finalists + 4 explicitly excluded with reason) |
| 2. Apple Silicon filter | Yes — MLX vs MPS vs CPU-ONNX vs Metal-via-llama.cpp explicitly distinguished |
| 3. Voice quality evidence | Yes — Artificial Analysis ELO, HF TTS-Arena V2, Podonos blind test, MOS estimates |
| 4. Python integration audit | Yes — verbatim code from official READMEs/HF cards for each finalist |
| 5. Gap search (license, release dates, M3 issues, phonemizer) | Yes — license tier and exact dates surfaced for all 5 |
| 6. Subagent (deepest gap) | Used once on performance numbers + entrypoint verification |
| 7. enrich_draft | Called once with full integrated draft |
| 8. complete_task | This call |