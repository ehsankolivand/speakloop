# Best Local Open-Weight LLMs for a Mock-Interviewer Voice Loop on M3 Pro 18GB (May 2026)

> ## ⚠️ Current state (read this first)
>
> **The shipped LLM is `mlx-community/Qwen3-14B-4bit`** (~8 GB on disk, ~9–10 GB
> resident with KV cache) with **thinking mode ON** — the wrapper
> (`src/speakloop/llm/qwen_engine.py`) strips only the leading
> `<think>...</think>` block. The grammar analyzer calls it at `temperature=0.3`
> with a **free-form prompt** (no Persian-L1 catalog; that catalog and
> `feedback/catalog.py` / `persian_l1_catalog.yaml` were deleted in May 2026).
> Sampler config (top_p 0.8 / top_k 20 / min_p 0; repetition_penalty 1.05 /
> context 40; defensive `<|im_end|>` stop) lives entirely in the wrapper.
>
> The body of this document is the **original** May-2026 survey, which
> recommended Qwen3.5-9B. The model identity then evolved
> Qwen3.5-9B-VLM → Qwen3-8B-4bit → Qwen3-14B-6bit → **Qwen3-14B-4bit**.
> The two "Update — 2026-05-2x" sections at the bottom record each step;
> they supersede the TL;DR below on conflict. Source of truth: the live
> source (`src/speakloop/installer/manifest.py`,
> `src/speakloop/llm/qwen_engine.py`) and the CHANGELOG entries dated
> 2026-05-25.
>
> **Hardware-budget rule (from the 2026-05-25 OOM fix).** Future LLM swaps on
> the M3 Pro 18 GB target MUST sanity-check resident size against ≈10 GB
> (18 GB unified − ~5 GB macOS+Python − ~3 GB resident ASR encoder). 8-bit
> Qwen quant stays out of scope.

## TL;DR

- **Top pick: Qwen3.5-9B at MLX 4-bit** (`mlx-community/Qwen3.5-9B-MLX-4bit`, ~5.1 GB download, model released March 2, 2026). Highest IFEval / IFBench in the size class, native MLX streaming, Apache 2.0, and — critically — Qwen3.5's "small series" ships with thinking mode disabled by default, sidestepping the documented `<think>`-leak bug that disqualifies the base Qwen3-8B.
- **Safest fallback: Llama 3.1 8B Instruct (MLX 4-bit, ~4.5 GB, July 23, 2024).** Verified 62 tok/s and 0.7 s TTFT directly on M3 Pro 18 GB, the strongest first-hand Apple-Silicon datapoint on this list, and the deepest community fine-tune ecosystem if the stock instruct model drifts in persona.
- **Snappy alternative: Gemma 3 4B Instruct QAT Q4_0 (~2.9 GB, March 12, 2025).** Verified 88 tok/s and 0.4 s TTFT on M3 Pro 18 GB via MLX, with QAT preserving near-BF16 quality at Q4. Pick it if you want the absolute lowest TTFT or maximum RAM headroom; deprioritised because the user's stated tilt is toward 8–9 B for persona stability.

## Key Findings

1. **The Qwen3-8B `enable_thinking=False` flag is broken** across llama.cpp, MLX, vLLM, and Ray (confirmed in ggml-org/llama.cpp issues #13189 and #20409, QwenLM/Qwen3 #1625, ray-project/ray #52979). `<think>` blocks leak intermittently — fatal for a 2-second-budget voice loop. The newer **Qwen3.5 small series (0.8 B / 2 B / 4 B / 9 B) ships with thinking DISABLED by default per Unsloth's deployment guide**, which is the single largest reason Qwen3.5-9B wins over Qwen3-8B here.

2. **The 10 GB download cap rules out the strongest 14–35 B contenders.** Qwen3.6-35B-A3B (April 2026), Mistral Small 3.2 24B, and Llama 4 Scout (109 B MoE) are all out at any reasonable quant. The realistic finalists sit in the 3.8–9 B band.

3. **The MLX vs llama.cpp gap narrowed sharply in March 2026.** Ollama's official MLX blog (ollama.com/blog/mlx, March 30, 2026) confirms: "Ollama on Apple silicon is now built on top of Apple's machine learning framework, MLX, to take advantage of its unified memory architecture", with prefill jumping from 1,154 to 1,810 tok/s (+57 %) and decode from 58 to 112 tok/s (+93 %) on M5 Max Qwen3.5-35B-A3B (int4 pushes decode to 134 tok/s, +131 %). Engine choice still matters for TTFT but is no longer decisive on Apple Silicon.

4. **Streaming + TTS pipelining flattens the felt-latency curve.** Between Gemma 3 4B (88 tok/s) and Llama 3.1 8B (62 tok/s) on M3 Pro 18 GB, first audio reaches the speaker in ~0.6–0.9 s either way; the multi-turn persona-stability advantage of the 8–9 B class outweighs the raw tok/s gap for a 30-minute mock interview.

5. **Ministral-3-8B-Instruct-2512 (Dec 4, 2025) is intriguing but Apple-Silicon-unverified.** Apache 2.0, strong IFBench (76.5), but zero published M-series benchmarks as of May 2026 — not safe to commit without in-house testing.

## Details

### Evidence Table

| Dimension | **Qwen3.5-9B (MLX 4-bit)** | **Llama 3.1 8B Instruct (MLX 4-bit)** | **Gemma 3 4B Instruct (QAT Q4_0)** | Ministral-3-8B-Instruct-2512 (Q4_K_M) | Phi-4-mini-instruct (Q4_K_M) |
|---|---|---|---|---|---|
| Model release | **March 2, 2026** | July 23, 2024 | March 12, 2025 | December 4, 2025 | February 26, 2025 |
| Recommended quant release | Mar 2026 (mlx-community) | actively re-uploaded, current MLX-4bit Q1 2026 | April 2025 (Google QAT release) | December 2025 (official GGUF) | March 2025 (bartowski) |
| Download size | **~5.1 GB** | ~4.5 GB MLX / 4.7 GB Q4_K_M | **~2.9 GB** | ~5.0 GB | ~2.5 GB |
| Resident RAM @ 8 K ctx | ~6–7 GB | ~5.5–6.5 GB | ~3.5–4.5 GB | ~6–7 GB | ~3–4 GB |
| M3 Pro tok/s | ~58 (M3 16 GB proxy), ~92 on M4 Pro MLX (LLMCheck) | **62 measured on M3 Pro 18 GB Ollama** (LLMCheck Jan 2026) | **88 measured on M3 Pro 18 GB MLX** (LLMCheck Jan 2026) | unverified on Apple Silicon | ~95 on M3 16 GB MLX (LLMCheck Feb 2026) |
| TTFT @ ~200 tok prompt | ~0.4–0.7 s (proxied) | ~0.7 s | **~0.4 s** | unverified | ~0.3 s |
| IFEval / IFBench | IFBench 76.5 (vendor / techie007) | IFEval 80.4 (Meta) | strong for size; exact public score not surfaced | IFBench 76.5, Arena Hard 50.9 (Mistral) | matches Llama 3.1 8B (~80) per Microsoft |
| Chatbot Arena Elo | not yet on Arena leaderboard | 1,211 (LMArena, rank #116; lmmarketcap.com) | Gemma 3 27B-IT 1,338; 4B not directly listed | not on Arena | not on Arena |
| English conv. fluency | excellent (vendor cites roleplay strength) | excellent, widely-reported natural tone | excellent — Gemini-line distillation | good; vendor cites system-prompt adherence | "very verbose" per Artificial Analysis |
| Persona stability | strong (multi-turn dialogue emphasised by vendor) | very strong; huge roleplay-tune ecosystem | strong but smaller param count limits depth | reported good; thin community evidence | weakest in family |
| Streaming output | yes (`mlx_lm.stream_generate`) | yes (`mlx_lm.stream_generate`) | yes (Ollama / llama.cpp / MLX) | yes (llama.cpp / Ollama) | yes (Ollama / MLX) |
| Context window | 262,144 | 131,072 | 128,000 | 262,144 | 128,000 |
| Engine | **mlx-lm** | **mlx-lm** | Ollama (`gemma3:4b-it-qat`) | llama-cpp-python | mlx-lm / Ollama |
| Python ergonomics (1–5) | 5 | 5 | 4 | 3 | 5 |
| License | **Apache 2.0** | Llama 3.1 Community | Gemma (commercial OK, terms apply) | **Apache 2.0** | MIT |
| Maintenance | very active (Qwen3.6 already shipped) | mature; vast quant coverage | active (Google QAT releases) | active (Mistral edge line) | active (Microsoft) |
| Thinking-mode risk | **none** — disabled by default in small series | n/a | n/a | n/a | n/a |

### Per-Model Deep Dives

---

#### 1. Qwen3.5-9B (MLX 4-bit) — Top Pick

**What it is.** A 9 B-parameter hybrid Gated-DeltaNet + sparse-MoE multimodal model released **March 2, 2026** by Alibaba's Qwen team as part of the Qwen3.5 small series (0.8 B / 2 B / 4 B / 9 B). Apache 2.0, 262 K native context, text-only inference path available. `mlx-community/Qwen3.5-9B-MLX-4bit` ships at ~5.06 bits-per-weight, ~5.1 GB on disk — comfortably inside the 10 GB cap.

**Why it qualifies.** Per Unsloth's deployment guide, "For Qwen3.5 0.8B, 2B, 4B and 9B, reasoning is disabled by default" — the load-bearing fact for a voice loop, because the base Qwen3-8B's `enable_thinking=False` is unreliable across every major inference engine (multiple confirmed GitHub issues). Third-party scores: 81.7 GPQA Diamond, 82.5 MMLU-Pro, 76.5 IFBench — outperforming GPT-OSS-120B on instruction following at 13× smaller.

**Quantization quality cost.** Negligible at 4-bit MLX for chat. The 8-bit MLX (~9.3 GB) is borderline against the cap; stick to 4-bit. Unsloth recommends 2-bit dynamic as a floor, so 4-bit has clear headroom over the quality cliff.

**Strengths.** Apache 2.0, freshest 9 B-class model (10 weeks old as of May 18, 2026), native MLX, vendor explicitly cites multi-turn dialogue and roleplay strength, 262 K context lets you keep the full interview history in scope.

**Weaknesses / risks.** No directly-measured M3 Pro 18 GB tok/s — proxied numbers only (treat ±20 %). The model carries a vision tower; load via `mlx_lm` text-only, not `mlx_vlm`, or you waste RAM on the encoder. Pin to the patched `mlx-community` repo, which fixes MoE gate-quantization predicates.

**Minimal Python (real, from mlx-lm README + Liquid AI docs):**
```python
from mlx_lm import load, stream_generate

model, tokenizer = load("mlx-community/Qwen3.5-9B-MLX-4bit")
messages = [{"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_transcript_from_asr}]
prompt = tokenizer.apply_chat_template(
    messages, tokenize=False, add_generation_prompt=True
)
for chunk in stream_generate(model, tokenizer, prompt=prompt, max_tokens=200):
    tts.feed(chunk.text)   # forward each token to streaming TTS
```

**System-prompt template tuned for Qwen3 family** (concise declarative role + explicit "one question" constraint):
```
You are Priya, a senior Android engineering manager at a remote-first company
conducting a 30-minute technical screen for a Senior Android Engineer role.
Stay strictly in character.

Rules:
- Ask exactly ONE focused question per turn. Never monologue.
- Keep your turns to 2-5 sentences (this is spoken aloud).
- Cover: Kotlin coroutines, Jetpack Compose internals, app architecture
  (MVI/MVVM), performance/memory, and one system-design question.
- After the candidate's answer, briefly acknowledge (one sentence), then
  ask the next probing question.
- If the candidate asks "How was my English?" or "Any feedback on phrasing?",
  switch to a one-sentence grammar note, then return to the interview.
- Never break character. Never list multiple questions. Never produce <think>.
```
Sampling (Qwen non-thinking): `temperature=0.7, top_p=0.8, top_k=20, min_p=0`.

**Verdict.** Best overall — highest quality in the ≤ 10 GB / ≤ 8 GB-RAM envelope, fresh, Apache 2.0, native MLX, free of the Qwen3 thinking trap.

---

#### 2. Llama 3.1 8B Instruct (MLX 4-bit) — Safest Fallback

**What it is.** Meta's 8 B dense instruct model, released July 23, 2024. The Llama 4 herd (Scout / Maverick, April 2025) is MoE and too large for this hardware; Llama 3.1 8B remains the most fine-tuned and most-benchmarked open 8 B base.

**Why it qualifies.** 131 K context, IFEval 80.4, LMArena Elo **1,211, ranked #116** (lmmarketcap.com aggregation, accessed May 2026). **Directly measured at 62 tok/s with 0.7 s TTFT on M3 Pro 18 GB via Ollama** (LLMCheck.net dataset, Jan 2026) — strongest first-hand Apple-Silicon datapoint of any finalist. MLX 4-bit ~4.5 GB; Q4_K_M GGUF ~4.7 GB.

**Quantization quality cost.** Q4_K_M perplexity delta vs FP16 is consistently <2 % on Llama 3.x in llama.cpp community measurements — imperceptible in voice.

**Strengths.** Largest roleplay-tune ecosystem (Stheno, Hermes-Roleplay, Natsumura) as escape hatches if Llama-Instruct drifts in persona; strongest first-party documentation; predictable behaviour under system prompts; best Apple-Silicon benchmark coverage.

**Weaknesses.** 22 months old — fading freshness; flag for re-verification against any Llama 4.X dense small if Meta ships one. License is Llama 3.1 Community, not Apache 2.0 (commercial attribution friction). Slightly lower IFBench than Qwen3.5-9B.

**Minimal Python (from mlx-lm README):**
```python
from mlx_lm import load, stream_generate

model, tokenizer = load("mlx-community/Meta-Llama-3.1-8B-Instruct-4bit")
messages = [{"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_transcript}]
prompt = tokenizer.apply_chat_template(messages, add_generation_prompt=True)
for chunk in stream_generate(model, tokenizer, prompt=prompt, max_tokens=200):
    tts.feed(chunk.text)
```

**System-prompt template tuned for Llama 3.1** (second-person "You are" + numbered rules + format constraint):
```
You are a senior Android engineering manager interviewing a candidate for
a remote Senior Android Engineer role.

1. Ask one focused technical question per turn (Kotlin, Compose, architecture,
   performance, system design).
2. Keep responses to 2-5 spoken sentences. No bullet lists, no markdown.
3. After the candidate answers, give a one-sentence acknowledgement, then
   ask the next question.
4. If the candidate explicitly asks for English feedback, give one concise
   correction, then resume the interview.
5. Never break character. Begin now with your first question.
```
Sampling: `temperature=0.6, top_p=0.9`.

**Verdict.** Safest fallback — pick this if you want maximum predictability, the most M3-Pro benchmark certainty, and the deepest fine-tune ecosystem.

---

#### 3. Gemma 3 4B Instruct QAT Q4_0 — The Snappy Pick

**What it is.** Google's 4 B dense multimodal model, released March 12, 2025. The QAT Q4_0 release (April 2025) uses Quantization-Aware Training; Google reports the perplexity drop reduced by 54 % vs naive Q4_0 (developers.googleblog.com QAT post). On-disk ~2.9 GB.

**Why it qualifies.** **Directly measured at 88 tok/s with 0.4 s TTFT on M3 Pro 18 GB via MLX** (LLMCheck.net, Jan 2026). At ~3.5 GB resident with 8 K context, leaves >8 GB headroom for ASR + Python + TTS.

**Quality cost.** With QAT, near-zero. Google's blog: "similar quality as half precision (BF16)". For reference, Artificial Analysis page (artificialanalysis.ai/models/gemma-3-12b, accessed May 2026) verbatim: "Gemma 3 12B Instruct scores 9 on the Artificial Analysis Intelligence Index, placing it at the lower end among comparable models (averaging 11)" — Gemma 3 4B sits below that but punches well above its parameter count on instruction-following.

**Strengths.** Lowest TTFT and highest tok/s on M3 Pro of any finalist; QAT means Q4 doesn't bite quality; official MLX / Ollama / llama.cpp first-party support; one-command setup via `ollama run gemma3:4b-it-qat`.

**Weaknesses.** Smallest parameter count → least depth on multi-turn persona drift (this fights the user's stated quality tilt). Gemma 3 release is >12 months old → **flag for re-verification before long-term adoption** (QAT weights are newer, but the base model is March 2025). Gemma license is less permissive than Apache 2.0. Requires Ollama 0.6+ for QAT tags.

**Minimal Python (Ollama official Python client):**
```python
from ollama import Client
client = Client()  # default http://localhost:11434
stream = client.chat(
    model="gemma3:4b-it-qat",
    messages=[{"role": "system", "content": SYSTEM_PROMPT},
              {"role": "user",   "content": user_transcript}],
    stream=True,
)
for chunk in stream:
    tts.feed(chunk["message"]["content"])
```

**System-prompt template tuned for Gemma 3** (terse — over-long prompts cause repetition):
```
Role: senior Android engineering manager interviewing for a remote Senior
Android Engineer role.
Style: 2-5 spoken sentences per turn. Plain prose. No lists.
Behavior: one focused question per turn. Acknowledge briefly, then probe deeper.
Topics: Kotlin, Jetpack Compose, app architecture, performance, system design.
If candidate asks for grammar feedback, give one concise correction then continue.
Begin with your first question.
```

**Verdict.** Pick this if latency is paramount, if you want a large RAM cushion for an aggressive ASR/TTS stack, or as a serious A/B test against Qwen3.5-9B.

---

#### 4. Ministral-3-8B-Instruct-2512 (Q4_K_M GGUF) — Promising but Unverified

**What it is.** Mistral's December 4, 2025 release in the Ministral 3 edge family. Apache 2.0, 262 K context, FP8-native with official Q4_K_M GGUF (~5 GB). Mistral: "deployable on a wide range of hardware … capable of fitting in 12 GB of VRAM in FP8".

**Why it qualifies.** Newest 8 B-class instruct in the list; Apache 2.0; strong vendor-reported metrics (IFBench 76.5, MATH 87.6, Arena Hard 50.9 per llm-stats.com).

**Risks.** **No published Apple-Silicon benchmarks as of May 2026** — the subagent's targeted search found zero. The legacy Ministral-8B-Instruct-2410 proxies to 55–72 tok/s on M3/M4 16 GB. Requires `mistral-common >= 1.8.6` tokenizer; llama-cpp-python is the cleanest Python path (MLX support is community-patched).

**Minimal Python (llama-cpp-python README):**
```python
from llama_cpp import Llama
llm = Llama.from_pretrained(
    repo_id="mistralai/Ministral-3-8B-Instruct-2512-GGUF",
    filename="*Q4_K_M.gguf",
    n_ctx=8192, n_gpu_layers=-1,  # full Metal offload
)
for tok in llm.create_chat_completion(
    messages=[{"role": "system", "content": SYSTEM_PROMPT},
              {"role": "user",   "content": user_transcript}],
    stream=True, max_tokens=200, temperature=0.7,
):
    delta = tok["choices"][0]["delta"].get("content", "")
    if delta: tts.feed(delta)
```

**System-prompt template tuned for Mistral family** (labelled `## Instructions` block + explicit persona name):
```
## Persona
You are Priya, a senior Android engineering manager running a 30-minute
technical interview for a Senior Android Engineer role. Remote-first company.

## Instructions
- One focused question per turn. Two to five spoken sentences.
- After each candidate answer: one-sentence acknowledgement, then next question.
- Topics: Kotlin coroutines, Compose, architecture (MVI/MVVM), performance,
  system design.
- If the candidate asks for English/grammar feedback, give one concise
  correction then return to interviewing.
- Stay in character. Never list. Never break role.
```

**Verdict.** Only commit after benchmarking it yourself on the M3 Pro — the lack of community Apple-Silicon data is a real risk for a latency-critical voice loop.

---

#### 5. Phi-4-mini-instruct (Q4_K_M) — Honourable Mention, Not Recommended

3.8 B, MIT licensed, 128 K context, released February 26, 2025; fastest in the list (~95 tok/s on M3 16 GB MLX, ~0.3 s TTFT). Disqualifying problem for a voice loop: Artificial Analysis (artificialanalysis.ai/models/phi-4-mini, accessed May 2026) verbatim: "When evaluating the Intelligence Index, it generated 31M tokens, which is very verbose in comparison to the average of 6.6M." Phi-family also drifts in long-form persona stability. Use only if you specifically need an MIT-licensed sub-3 GB model bundled into an app.

## Recommendations

**Stage 1 — Start here (week 1).** Install mlx-lm in a Python 3.11 venv, pull `mlx-community/Qwen3.5-9B-MLX-4bit`, and wire up the streaming snippet above. Use the Qwen-tuned system prompt with `temperature=0.7, top_p=0.8, top_k=20, min_p=0` and `max_tokens=200`. Measure end-to-end roundtrip TTFT on your actual ASR→LLM→TTS loop.

**Stage 2 — A/B baseline (week 2).** Run the same conversational eval suite (~20 mock-interview turns) against `mlx-community/Meta-Llama-3.1-8B-Instruct-4bit`. Compare persona drift, English fluency, and TTFT. If Qwen3.5-9B's TTFT exceeds 1.2 s consistently or persona breaks within 10 turns, switch to Llama 3.1 8B.

**Stage 3 — Latency-pressure fallback.** If on-device latency creeps above the 2-second target due to ASR or TTS overhead, swap to `gemma3:4b-it-qat` via Ollama. The 26 tok/s decode advantage and 0.3 s TTFT savings buy you back the budget.

**Stage 4 — Re-evaluate quarterly.** Triggers to revisit this ranking:
1. **Qwen3.6 dense 8 B-class release.** Qwen3.6-35B-A3B already shipped April 16, 2026. A dense 8–9 B variant would supersede 3.5-9B; retest within a week of release.
2. **Llama 4.X dense small.** Business Insider reports an internal Llama 4.X / 4.5 push by end of 2025; any dense small variant re-opens the Llama line.
3. **First credible M3 Pro benchmark for Ministral-3-8B-2512.** If community testing lands it at >55 tok/s with <0.8 s TTFT and persona stability ≥ Llama 3.1 8B, it becomes the freshest Apache-2.0 8 B option.
4. **Stable Ollama+MLX backend.** Ollama's official MLX blog (March 30, 2026) reports exact figures on M5 Max running Qwen3.5-35B-A3B: prefill improved from 1,154 to 1,810 tokens/s (+57 %) and decode from 58 to 112 tokens/s (+93 %); int4 quantization pushes decode to 134 tok/s (+131 %). When this lands as the stable Ollama default, retest — these gains may erase Gemma 3 4B's TTFT lead and tilt the ranking further toward 8–9 B.

**Hard rules to apply throughout.**
- Do **not** substitute Qwen3-8B for Qwen3.5-9B — the thinking-mode bug is documented across llama.cpp, MLX, vLLM, and Ray. The 3.5 small-series defaults are the only safe Qwen path here.
- Do **not** load Qwen3.5-9B through `mlx_vlm` unless you actually need vision; use `mlx_lm` to skip the vision encoder and save ~1 GB of resident memory.
- Cap `max_tokens` at 200 in the streaming call. Voice turns are 2–5 sentences; runaway generation is the single largest avoidable latency cost.

## Caveats

- **LLMCheck.net is a community-aggregated benchmark site, not a first-party source.** Methodology (Q4_K_M, 256-tok input, 512-tok output, 3-run average) is documented and internally consistent, but treat all M3 Pro tok/s and TTFT figures as ±20 %. Verify in your own pipeline before committing.
- **Qwen3.5-9B existence was briefly questioned** by the subagent. It is confirmed via Qwen's GitHub release log ("2026-03-02: Qwen3.5-9B, Qwen3.5-4B, Qwen3.5-2B, and Qwen3.5-0.8B are now available on Hugging Face Hub and ModelScope") and the live `mlx-community/Qwen3.5-9B-MLX-4bit` HuggingFace repository. The confusion stems from Qwen3.5 being a multimodal release that some users access via `mlx_vlm`; load text-only via `mlx_lm`.
- **Streaming + TTS pipelining shrinks the felt latency gap.** First audio reaches the speaker within ~0.6–0.9 s for both Gemma 3 4B (88 tok/s) and Llama 3.1 8B (62 tok/s) on M3 Pro. Persona stability over a 30-minute mock interview is the harder constraint — hence the tilt toward the 8–9 B class.
- **Gemma 3 4B model card is >12 months old** → mandatory re-verification before long-term adoption. The QAT Q4_0 weights and Ollama tags remain actively maintained but the underlying model has not had a major refresh.
- **Multiple primary GitHub issues confirm** that for the base Qwen3 family (not the 3.5 small series), `enable_thinking=False` is not reliable. Do not casually swap Qwen3-8B for Qwen3.5-9B.

---

## Update — 2026-05-22 (feature 006: shipped generation config + 4-bit-only decision) — model since superseded; see 2026-05-25 update at the bottom

This document is the *original* model survey; it recommended Qwen3.5-9B. The code instead
ships **`mlx-community/Qwen3-8B-4bit`** because the `Qwen3.5-9B` MLX repo turned out to be a
vision-language build incompatible with `mlx_lm.load()` (rationale: `installer/manifest.py:56-65`;
root `CLAUDE.md` trap 3). Feature 006 hardened the single grammar LLM call site. The source of
truth for these decisions is **`doc/QWEN_IMPROVMENT_RESEARCH.md`**, lifted into
**`specs/006-feedback-quality-reliability/research.md`**.

**Generation config now applied inside `llm/qwen_engine.py`** (Constitution Principle V — no engine
config leaks to the call site). Supersedes the bare "Sampling (Qwen non-thinking)" line above:

| Param | Default | Bounded regenerate (`retry=True`) | Source |
|---|---|---|---|
| `enable_thinking` | `False` | `False` | Qwen3-8B card; `<think>` still stripped defensively |
| `temperature` | `0.7` | `0.6` (−0.1) | Qwen3-8B "Best Practices" |
| `top_p` / `top_k` / `min_p` | `0.8` / `20` / `0` | unchanged | same |
| `repetition_penalty` | `1.05` | `1.15` | research R2 (mlx-lm default 1.0 = no-op; 4-bit is loop-prone) |
| `repetition_context_size` | `40` | `40` | research R2 |
| `stop` (defensive EOS) | `["<\|im_end\|>"]` | same | research R5 — applied by truncation (mlx-lm `generate` has no `stop=`) |
| `max_tokens` | `≤ 2048` | same | research R6 |

- Built via `make_sampler(...)` + `make_logits_processors(repetition_penalty=…, repetition_context_size=…)`
  — mlx-lm-native, **no new dependency** for sampling/repetition control.
- **Output recovery**: `json-repair` (post-hoc) replaces the old hand-rolled regex repair, plus **one
  bounded regenerate** on a repetition loop / truncation, then the existing graceful Phase-B fallback
  (`feedback/grammar_analyzer.py`). One new dependency: `json-repair` (offline, pure-Python).

**Quantization decision (firm).** Stay on **4-bit**; the **8-bit variant is out of scope this sprint**
(no A/B, no adoption threshold). 8-bit adds ~4 GB to every download and doubles resident RAM —
the wrong trade for the target user under Constitution VI (bandwidth) / VII (Apple-Silicon RAM),
and the research has no *measured* GEC gain to weigh against it. Any future revisit belongs in its
own sprint decision record (`specs/006-…/research.md` Decision 2 / M3).
- **All five finalists support streaming** in their recommended Python inference engine; none is disqualified on that axis. The differentiation is on quality, latency, persona stability, and freshness.

---

## Update — 2026-05-24 (model swap to Qwen3-14B-6bit + thinking ON + free-form prompt) — 6-bit re-quantised to 4-bit on 2026-05-25 (next section)

The code now ships **`mlx-community/Qwen3-14B-6bit`** (replacing the prior
`mlx-community/Qwen3-8B-4bit`), with the Qwen3 chat template's `enable_thinking`
flag **enabled** and the leading `<think>...</think>` block stripped at the
wrapper boundary (`llm/qwen_engine.py:_strip_artefacts`). The grammar analyzer
adopts a **free-form prompt** in place of the Persian-L1 catalog; the model
returns its own `error_type` strings which become `GrammarPattern.label`.

**Pre-adoption testing.** A representative Persian-L1 transcript triple was run
through three candidate models with the same free-form prompt:

| Model | Recall on triple | Present-continuous vs simple |
|---|---|---|
| **Qwen3-14B-6bit (chosen)** | **7 / 7** | **distinguishes correctly** |
| Granite-4.1-8B | partial | does not distinguish |
| Ministral-3-14B-Instruct | partial | does not distinguish |

Qwen3-14B-6bit was the only candidate that consistently surfaced every grammar
error and the only candidate that distinguished present continuous from present
simple — the deciding capability for Persian-L1 learners.

**Generation config (analyzer call site).** Temperature is **0.3** (vs the
`LLMEngine.generate` Protocol default 0.7); pre-adoption testing showed
materially improved recall and JSON discipline at 0.3 for analytic /
structured-output tasks. The Protocol default remains 0.7 for compatibility.
The wrapper still owns the sampler config (top_p 0.8, top_k 20, min_p 0) and
the rep-penalty (1.05 / context 40; 1.15 on `retry=True`).

**Thinking-mode strip (wrapper).** The leading-block-only regex
`re.compile(r"^\s*<think>.*?</think>\s*", flags=re.DOTALL)` strips the
expected reasoning prelude. Mid-output `<think>` is unexpected with the
Qwen3-14B chat template and is left in place; a truncated thinking pass
(missing `</think>`) is also left in place and triggers the analyzer's
bounded regenerate path.

**Closed divergence.** Trap 3 in the root `CLAUDE.md` is retired. Research
and shipped model finally agree on the Qwen3 family at 14B-6bit; the prior
Qwen3.5-9B-VLM divergence is now historical context only.

**On-disk footprint.** ~12 GB vs ~4.31 GiB (Qwen3-8B-4bit). The trade is
deliberate under Constitution VI (bandwidth) / VII (Apple-Silicon RAM): the
recall lift on real Persian-L1 transcripts is decisive for the target user,
and the resumable HF download flow already softens the bandwidth cost.

---

## Update — 2026-05-25 (re-quantised 14B → 4-bit to fit M3 Pro 18 GB)

The 6-bit variant of Qwen3-14B did not fit the M3 Pro 18 GB unified-memory
target: a real-session crash with `[METAL] Command buffer execution failed:
Insufficient Memory` occurred during a Whisper transcribe after multiple
sequential calls, before Qwen had even loaded. Memory math: macOS + apps
(~4-6 GB) + Python deps (~1-2 GB) + Whisper-large-v3-turbo resident (~3 GB) +
Qwen3-14B-6bit resident (~14 GB with KV cache) = ~22-25 GB demanded vs 18 GB
available.

**Resolved by re-quantising to 4-bit at the same 14B size:**
`mlx-community/Qwen3-14B-4bit` is ~8 GB on disk, ~9-10 GB resident with KV
cache. Combined with the resident Whisper (~3 GB) and system overhead it fits
the 18 GB budget with headroom. Quality cost vs 6-bit at the same parameter
count is small for analytic / structured-output tasks at temperature 0.3
(no community measurements show a material drop on GEC-style work at this
quant level).

**Thinking mode stays ON; free-form prompt unchanged.** The wrapper still
strips the leading `<think>...</think>` block; the analyzer still passes
`temperature=0.3`. The only change is the manifest entry and a smaller
on-disk / resident footprint.

**Hardware target reaffirmed.** Future LLM swaps in this repo MUST sanity-
check resident size against 18 GB unified memory minus ~3 GB for the resident
ASR encoder minus ~5 GB for macOS + Python overhead — i.e. an LLM resident
ceiling of roughly 10 GB. This is the working budget for the M3 Pro 18 GB
target user.