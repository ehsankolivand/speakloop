# Getting the Highest-Quality Output from `mlx-community/Qwen3-8B-4bit` under `mlx-lm`

> ## ⚠️ Historical — the shipped model is no longer Qwen3-8B-4bit
>
> This document is the deep-dive that informed the original 006 generation
> config when the code shipped Qwen3-8B-4bit. The shipped model has since
> moved to **`mlx-community/Qwen3-14B-4bit` with thinking mode ON** (see
> `doc/research_llm.md` Updates 2026-05-24 and 2026-05-25 at the bottom of
> that file). The wrapper-side config that ultimately landed —
> top_p 0.8 / top_k 20 / min_p 0; `repetition_penalty` 1.05 / context 40;
> defensive `<|im_end|>` stop; `json-repair` post-hoc recovery + one bounded
> regenerate — is unchanged from the recommendations here. The two things
> that diverged: **`enable_thinking=True`** (this file argues for False, which
> was right for 8B-4bit on a 2 s voice loop but wrong for 14B-4bit one-shot
> grammar analysis at `temperature=0.3`), and the catalog/prompt direction
> (the Persian-L1 catalog was retired in favour of a free-form
> model-emitted-`error_type` prompt). Source of truth for the live config is
> `src/speakloop/llm/qwen_engine.py` + `src/speakloop/feedback/grammar_analyzer.py`.

## TL;DR
- For thinking mode use `temperature=0.6, top_p=0.95, top_k=20, min_p=0`; for non-thinking use `temperature=0.7, top_p=0.8, top_k=20, min_p=0`; never use greedy decoding — these are vendor-mandated values from the official Qwen3-8B model card (verified).
- Use mlx-lm **v0.31.3** (released 22 Apr 2026) and avoid mlx==0.30.4 for any Qwen3 weights — a known regression produces garbage output past ~1000 tokens (issue #844, closed). For grammar checking, disable thinking (`enable_thinking=False`) and keep outputs short; thinking mode wastes tokens for shallow edit tasks.
- mlx-lm has **no native** `response_format`/`json_schema` constrained decoding in v0.31.3 (issue #852, open). For schema enforcement on this stack you have one good option (Outlines's `mlxlm` backend via logits processors) and one safety net (`json-repair` for post-hoc cleanup); everything else (lm-format-enforcer, XGrammar, Guidance) lacks a working mlx-lm integration.

---

## Key Findings

### Axis 1 — Configuration

1. **Canonical sampler values come from the Qwen3-8B model card "Best Practices" section** (verified, https://huggingface.co/Qwen/Qwen3-8B): thinking → `Temperature=0.6, TopP=0.95, TopK=20, MinP=0`; non-thinking → `Temperature=0.7, TopP=0.8, TopK=20, MinP=0`. Greedy decoding is explicitly banned: *"DO NOT use greedy decoding, as it can lead to performance degradation and endless repetitions."* `presence_penalty` 0–2 is recommended to suppress loops, with a warning that high values cause language mixing.

2. **mlx-lm's sampler pipeline applies in a fixed order**: `top_k → top_p → min_p → XTC → temperature` (verified from `make_sampler` in `mlx_lm/generate.py`). Server defaults are `temperature=0.0, top_p=1.0, top_k=0, min_p=0.0, repetition_penalty=1.0, repetition_context_size=20` — these are wrong for Qwen3 and must be overridden explicitly.

3. **Current stack is mlx-lm 0.31.3 + mlx 0.31.2** (both released 22 Apr 2026 per PyPI). v0.31.3 is a bugfix release ("Lots of bugfixes — Thread local generation stream to accompany MLX v0.31.2"); upgrade to it.

4. **Avoid mlx==0.30.4** — issue #844 (closed) reports `mlx-community/Qwen3-Coder-Next-4bit` emitting garbage after ~1000 tokens with mlx==0.30.4. Rolling back to mlx==0.30.3 fixes it. The fix landed in mlx 0.31.x; verify your `mlx` and `mlx-metal` are ≥ 0.31.0.

5. **Do not enable speculative decoding with Qwen3 weights**. Issue #846 (open as of May 2026) demonstrates token-dropping on Qwen3 family with `--draft-model` on mlx-lm 0.30.4; the documented workaround is "Disable speculative decoding (don't use `--draft-model` flag)."

6. **Chat-template `enable_thinking` is correctly present in `mlx-community/Qwen3-8B-4bit`** — the tokenizer_config.json embedded `chat_template` contains the canonical Jinja conditional `{%- if enable_thinking is defined and enable_thinking is false %}{{- '<think>\n\n</think>\n\n' }}{%- endif %}` (verified via raw fetch). The known mlx-swift-lm issue #154 about stripped `enable_thinking` logic affects `Qwen3-4B-Instruct-2507-4bit`, not this checkpoint.

7. **4-bit quantization measurably hurts Qwen3-8B**. The Zheng et al. empirical study (arXiv:2505.02214; first author Xingyu Zheng, Beihang University) reports Qwen3-8B MMLU 74.7 → 69.3 under AWQ w4a16, and C4 perplexity 10.4 → 14.8. The authors note Qwen3 is more quantization-sensitive than LLaMA-3 because "a more thorough pre-training process likely results in fewer redundant representations." Treat 4-bit outputs as systematically lower-quality than fp16. Per N8 Programs, "An Examination of MLX Quantization: Empirical scaling laws, surprising results, and an esoteric quantization recipe" (Aug 11, 2025, https://n8programs.substack.com/p/an-examination-of-mlx-quantization), on Qwen3-4B-2507-Instruct "the 8bit quant is essentially lossless (matching the ~8.5 ppl of the bf16)" — the same pattern is generally observed for the 8B size. For ≥ 12 GB free RAM, prefer `mlx-community/Qwen3-8B-8bit` when accuracy matters; reserve 4-bit for memory pressure.

8. **Context-length practical advice**: native context is 32,768 tokens; YaRN extends to 131,072 (`--rope-scaling yarn --rope-scale 4 --yarn-orig-ctx 32768`). The Qwen team warns: *"static YaRN, which means the scaling factor remains constant regardless of input length, potentially impacting performance on shorter texts. We advise adding the rope_scaling configuration only when processing long contexts is required."* Don't enable YaRN unless you actually need > 32K. With 4-bit at 8 GB unified memory, expect a comfortable working budget of ~16K input + 1–4K output before paging.

### Axis 2 — Prompting

1. **Thinking mode is the wrong default for grammar checking on Qwen3-8B-4bit.** Qwen3's `<think>` blocks can run thousands of tokens; for a one-shot "find the L2 errors and propose corrections" task this is pure overhead and burns through the 4-bit quality budget (the model's edge-case decoding margin is the first thing quantization erodes). Use `enable_thinking=False`. Verified Qwen team guidance: thinking is for "complex logical reasoning, math, and coding" — grammar correction is a pattern-completion + edit task that maps to the non-thinking path.

2. **System role works, but keep it short and stable.** Long system prompts dilute attention more on smaller dense models; Qwen3-8B is a dense transformer with 36 layers, 32 query heads, and 8 key-value heads (GQA, per Together AI's model page, https://www.together.ai/models/qwen3-8b). Put the task definition in `system`, the input text in `user`, and demand a single block of output. Multi-turn is fine but the Qwen team requires you to *strip thinking content from history* in multi-turn: *"the historical model output should only include the final output part."*

3. **Few-shot helps for output format consistency, not for grammatical-error coverage.** Two carefully selected examples in the system message stabilize JSON output and the choice of edit verbs. More than ~3 examples on an 8B-4bit model wastes context that you need for the user's text — and at 4-bit the marginal benefit per example collapses faster than at fp16 (extrapolated from quantization-sensitivity findings). Stop at 2 examples; add a third only if you see schema drift.

4. **Output format ranked by malformation risk on 8B-4bit:**
   - Plain numbered list of edits → most reliable, hardest to parse downstream
   - Tab/pipe-separated lines (one edit per line) → reliable, easy to parse
   - Minimal flat JSON (array of `{span, error_type, suggestion}`) → reliable if schema is small
   - Nested JSON with optional/`oneOf` fields → fragile at 4-bit; expect schema drift on ~3–8% of cases (inferred from the "repetition / format drift after ~5 turns at 4-bit" pattern reported in mlx-lm #1011 and Outlines #1131)
   - XML-ish → works but no advantage over JSON; skip.

   Decision: use **minimal flat JSON** plus a `json-repair` safety net.

5. **The `/no_think` soft switch works as documented** when `enable_thinking=True` is the template default — useful inside multi-turn agents. For a single-shot grammar pass just pass `enable_thinking=False` to `apply_chat_template`.

6. **Length budgets for grammar tasks**: cap `max_tokens` at roughly `4 × input_length` (in tokens), 512 for sentence-level, 1024–2048 for paragraph-level. The model card recommends 32,768 for general queries, but that's for reasoning answers; here it just enlarges the tail of repetition loops.

### Axis 3 — Output Repair / Structured Generation

1. **mlx-lm has no native structured-output / JSON-mode flag** in v0.31.3. The `mlx_lm.server` documented Request Fields are: `messages, role_mapping, stop, max_tokens, stream, temperature, top_p, top_k, min_p, repetition_penalty, repetition_context_size, logit_bias, logprobs, model, adapters, draft_model, num_draft_tokens` — no `response_format`, `json_schema`, `grammar`, or `structured_outputs`. Issue #852 (open) is the tracked feature request; maintainers are still debating logits-processor vs. prompt-injection paths.

2. **Outlines's `mlxlm` backend is the only first-class constrained-decoding option for this stack.** Install via `pip install "outlines[mlxlm]"`. Usage (verified from Outlines docs at https://dottxt-ai.github.io/outlines/latest/features/models/mlxlm/): wrap with `outlines.from_mlxlm(*mlx_lm.load("mlx-community/Qwen3-8B-4bit"))` then pass a Pydantic model or JSON schema as `output_type=`. Caveat from Outlines #1131: Outlines does not currently expose `repetition_penalty` through its sampler for mlx-lm, so a long prompt can spiral into an infinite-loop JSON (`"Methodist Hospital", "Methodist Hospital", ...`) bounded only by `max_tokens`. Pair Outlines with a tight `max_tokens` and a `stop` list; if you need rep penalty, drop to mlx-lm's `logits_processors` API and ship your own JSON-schema processor.

3. **lm-format-enforcer does NOT support mlx-lm.** Per its own README, supported backends are "LlamaCPP and HuggingfaceLLM" plus vLLM/TGI integrations through v0.11.2 (Aug 2025); no MLX integration ships. Don't try to use it here.

4. **XGrammar runs on Apple Silicon but has no mlx-lm integration.** Its README lists supported engines as "vLLM, SGLang, TensorRT-LLM, MLC-LLM" — mlx-lm is not on the list. Apple-Silicon support means the engine compiles natively; it does not mean a wired bitmask path into mlx-lm's sampler. Possible to glue manually via the logits-processor hook, but treat it as a research project.

5. **Guidance (guidance-ai) likewise lacks an mlx-lm backend.** Supported model interfaces are HuggingFace Transformers, llama.cpp, and remote APIs; no MLX adapter ships.

6. **`json-repair` is the practical safety net**. Latest stable is 0.59.10 (PyPI, released May 14, 2026 per the project's PyPI history). Use as a drop-in fallback for `json.loads()`. Schema-guided repair (beta) accepts a JSON Schema or Pydantic v2 model and will coerce strings to ints, fill missing required fields, and reject ambiguous duplicates in `strict=True`. The right ordering for a grammar checker: (1) try `json.loads`; (2) on failure, `json_repair.loads(text, schema=Schema)`; (3) on second failure, retry generation with a slightly lower temperature and a re-anchored prompt.

7. **Streaming-time repair patterns that work for Qwen3**:
   - **Truncated thinking-block guard**: when `enable_thinking=True`, scan for token id 151668 (`</think>`); reject responses where it never appeared but `finish_reason='length'`. Retry with higher `max_tokens` or fall back to `enable_thinking=False`.
   - **Repetition-loop detection**: track sliding-window n-gram repetition (n=4, window=64); if the same 4-gram appears > 8 times, kill generation and retry with `repetition_penalty=1.1, repetition_context_size=64`. mlx-lm exposes both via `make_logits_processors`.
   - **EOS-token sanity**: `<|im_end|>` is the documented EOS token for Qwen3; pass `stop=["<|im_end|>"]` defensively in case the chat-template path doesn't.

---

## Details

### Recommended sampler config (Python dict, copy-pasteable)

```python
# For grammar-checking and other instruction-following tasks
NON_THINKING_SAMPLER = {
    "temperature": 0.7,
    "top_p": 0.8,
    "top_k": 20,
    "min_p": 0.0,
    "repetition_penalty": 1.05,    # mild; Qwen team prefers presence_penalty but mlx-lm exposes rep_penalty
    "repetition_context_size": 40, # default 20 is too small; 40 catches most n-gram loops
}

# For reasoning-heavy uses (analysis, multi-step diff explanations)
THINKING_SAMPLER = {
    "temperature": 0.6,
    "top_p": 0.95,
    "top_k": 20,
    "min_p": 0.0,
    "repetition_penalty": 1.0,     # leave alone; Qwen explicitly warns about side-effects in thinking mode
    "repetition_context_size": 20,
}
```

Rationale: temperature/top_p/top_k/min_p come verbatim from the Qwen3-8B model card "Best Practices" section. `repetition_penalty=1.05` and `repetition_context_size=40` are conservative deltas added because (a) mlx-lm's default `repetition_penalty=1.0` is a no-op, and (b) 4-bit Qwen3 is observably more loop-prone on long outputs (mlx-lm #844, Outlines #1131). Sources: https://huggingface.co/Qwen/Qwen3-8B, https://github.com/ml-explore/mlx-lm/blob/main/mlx_lm/SERVER.md.

### Chat-template invocation (mlx-lm Python API)

```python
from mlx_lm import load, generate
from mlx_lm.sample_utils import make_sampler, make_logits_processors

model, tokenizer = load("mlx-community/Qwen3-8B-4bit")

messages = [
    {"role": "system", "content": SYSTEM_PROMPT},
    {"role": "user",   "content": USER_INPUT},
]

# IMPORTANT: enable_thinking is a kwarg passed straight through to the Jinja template.
# The mlx-community/Qwen3-8B-4bit template contains the canonical conditional, so this works.
prompt = tokenizer.apply_chat_template(
    messages,
    add_generation_prompt=True,
    enable_thinking=False,        # grammar tasks: turn thinking OFF
    tokenize=False,
)

sampler = make_sampler(**NON_THINKING_SAMPLER)  # temperature, top_p, top_k, min_p
logits_processors = make_logits_processors(
    repetition_penalty=1.05,
    repetition_context_size=40,
)

text = generate(
    model, tokenizer,
    prompt=prompt,
    max_tokens=1024,
    sampler=sampler,
    logits_processors=logits_processors,
    verbose=False,
)
```

Rationale: this is the mlx-lm-documented separation of concerns — `sampler` covers temperature/top-k/top-p/min-p, `logits_processors` covers rep-penalty and any custom constraints. Source: README of `ml-explore/mlx-lm` and `mlx_lm/sample_utils.py`.

### Prompt template for L2 English grammar checking (system + user)

```text
SYSTEM:
You are an English grammar assistant for L2 learners. For each input sentence,
return one JSON object with this exact shape — no preface, no markdown fence:

{"sentence_id": <int>, "edits": [
    {"span": "<verbatim erroneous substring>",
     "error_type": "<one of: tense, agreement, article, preposition, word_choice, word_order, punctuation, spelling, other>",
     "suggestion": "<corrected substring>",
     "explanation": "<one short sentence, plain English, no jargon>"}
]}

Rules:
- If the sentence is already correct, return {"sentence_id": <id>, "edits": []}.
- Do not paraphrase. Each edit must be the minimum substring change.
- Quote span exactly as it appears, including casing and punctuation.

Two examples:
Input: {"sentence_id": 1, "text": "She go to school every day."}
Output: {"sentence_id": 1, "edits": [{"span": "go", "error_type": "agreement",
"suggestion": "goes", "explanation": "Third-person singular present needs -s."}]}

Input: {"sentence_id": 2, "text": "I have lived here since five years."}
Output: {"sentence_id": 2, "edits": [{"span": "since", "error_type": "preposition",
"suggestion": "for", "explanation": "Use 'for' with a duration; 'since' marks a start time."}]}

USER:
{"sentence_id": 42, "text": "I am living in Tokyo since 2019 and I am still learn Japanese."}
```

Rationale: minimal flat schema → low malformation risk at 4-bit; two examples → format stabilization without context bloat; explicit "no preface, no markdown fence" → counters Qwen3's tendency to wrap JSON in ```json fences; closed enum on `error_type` → makes downstream filtering reliable and is exactly the kind of constraint that schema-guided `json_repair` can fix when the model drifts. Inferred from the prompting-cost analysis above and the Qwen team's standardize-output-format guidance.

### Output-repair decision tree

```
generate(text)
  └─ if finish_reason == "length":
     ├─ if enable_thinking and "</think>" never seen → RETRY with enable_thinking=False
     └─ else                                       → RETRY with max_tokens *= 2, up to a hard ceiling

  └─ try json.loads(stripped_text)
     ├─ on success → validate against Pydantic → if OK return
     └─ on JSONDecodeError:
        ├─ try json_repair.loads(text, schema=Pydantic_model)
        │   ├─ on success → return repaired
        │   └─ on ValueError → fall through
        ├─ if response shows repetition (n-gram detector trips):
        │   RETRY once with repetition_penalty=1.15, temperature -= 0.1
        ├─ if response is well-formed prose, not JSON:
        │   RETRY once with a stricter "JSON only, no prose" reminder appended
        └─ FALLBACK: re-prompt with a smaller schema
            (drop "explanation" field, then drop "error_type", then go to TSV)
            If TSV also fails → return raw text to the user, log for inspection.
```

Rationale: the cheapest fix (repair) is tried first; the most expensive (regenerate) is rationed. The schema-decay fallback matches the "smaller-context, more-reliable" pattern that 4-bit Qwen3 exhibits empirically.

---

## Recommendations

Format: do X because of Y; source.

1. **Use sampler `temperature=0.7, top_p=0.8, top_k=20, min_p=0` for grammar checking** because that is the vendor-recommended non-thinking config and matches Qwen3's RLHF distribution. Source: Qwen3-8B model card §Best Practices, https://huggingface.co/Qwen/Qwen3-8B (verified May 2026).
2. **Set `enable_thinking=False` explicitly via `tokenizer.apply_chat_template`** because (a) the template default is True and (b) thinking burns budget for tasks the non-thinking path handles better. Source: same model card; also the Jinja in `mlx-community/Qwen3-8B-4bit/tokenizer_config.json` (verified by raw fetch).
3. **Pin mlx-lm ≥ 0.31.3 and mlx ≥ 0.31.0** because (a) v0.31.3 ships parallel-tool-call and BatchKVCache fixes and (b) mlx 0.30.4 has a Qwen3 garbage-output regression. Sources: https://github.com/ml-explore/mlx-lm/releases (v0.31.3, 22 Apr 2026); issue #844 (closed).
4. **Do not pass `--draft-model` with any Qwen3 weights** because speculative decoding drops/skips tokens on this family. Source: issue #846 (open).
5. **Default `repetition_penalty=1.05, repetition_context_size=40`** because mlx-lm's defaults disable rep penalty entirely and 4-bit Qwen3 is empirically loop-prone on long outputs. Source: mlx-lm SERVER.md defaults; mlx-lm #844; Outlines #1131.
6. **Cap `max_tokens=1024` for sentence-level and 2048 for paragraph-level grammar tasks** because longer caps just enlarge the tail of repetition failures and the Qwen team's 32,768-token recommendation is for reasoning answers, not edits. Source: Qwen3-8B model card §Best Practices.
7. **Prefer `mlx-community/Qwen3-8B-8bit` if you have ≥ 12 GB free** because Qwen3-8B drops ~5.4 MMLU points and ~4.4 C4-PPL from FP16 to 4-bit AWQ, while 8-bit is "essentially lossless" on MLX quantization curves at the same size class. Sources: Zheng et al., arXiv:2505.02214; N8 Programs, "An Examination of MLX Quantization" (Aug 2025).
8. **For JSON output, use Outlines's `mlxlm` backend OR `json-repair`, not both at first** because Outlines enforces format at decode time (best correctness, no rep-penalty) and `json-repair` is a cheap post-hoc fallback (works with stock mlx-lm rep penalty). Sources: https://dottxt-ai.github.io/outlines/latest/features/models/mlxlm/; https://github.com/mangiucugna/json_repair.
9. **Don't try lm-format-enforcer, XGrammar, or Guidance on mlx-lm in 2026** because none ship a working backend; gluing manually via `logits_processors=` is possible but not maintained. Sources: lm-format-enforcer README; XGrammar README; Guidance README.
10. **Always pass `stop=["<|im_end|>"]` defensively** because chat-template parsing has occasionally dropped EOS handling in edge cases of mlx-lm regressions. Source: tokenizer config of `mlx-community/Qwen3-8B-4bit` (eos_token is `<|im_end|>`).
11. **Add `<think>\n\n</think>\n\n` to history before any cached-history multi-turn call when toggling between modes** because the Qwen team's chat template strips thinking content from previous turns and you must keep history token-identical to the format the template expects. Source: Qwen3-8B model card §"No Thinking Content in History."
12. **For schema enforcement on JSON, prefer a flat array over nested oneOf** because 4-bit Qwen3 exhibits schema drift on nested optional fields. Source: extrapolated from mlx-lm #1011 (multi-turn tool-call drift on mlx-community 4-bit/8-bit Qwen3.5 quants).

---

## Open Empirical Questions (require on-device testing)

1. What is the actual malformation rate for the recommended flat JSON schema across, say, 1000 sentences of a known L2 corpus (e.g., the W&I+LOCNESS dev set)? No public number exists for Qwen3-8B-4bit + mlx-lm; the closest reported figure is from a University of Twente master's thesis (Arifin, 2026, https://essay.utwente.nl/fileshare/file/108514/M.Arifin.H_Final_Project.pdf) evaluating **Qwen3-0.6B** at 4-bit (~1.9% F0.5 drop server-side, ~6.9% mobile) — not directly transferable to 8B.
2. Does setting `repetition_context_size=40` vs `=20` materially reduce the long-output loop rate, or just the visible 4-gram repeats? Needs measurement.
3. Does the Outlines `mlxlm` backend actually outperform `json-repair` on this model, given Outlines's lack of rep-penalty support (issue #1131)? Plausible that with tight `max_tokens` and rare rep-loops, Outlines wins on schema fidelity; needs A/B test.
4. Quantitative comparison between `mlx-community/Qwen3-8B-4bit` (group_size=64 default), `mlx-community/Qwen3-8B-4bit-AWQ`, and `mlx-community/Qwen3-8B-8bit` on English GEC. No published numbers as of May 2026.

---

## Caveats

- **Verified**: every Qwen3 sampler value, every mlx-lm release date and changelog claim, the absence of `response_format` in mlx-lm 0.31.3, the presence of the `enable_thinking` conditional in `mlx-community/Qwen3-8B-4bit`'s template, the closed/open status of issues #844, #846, #852, #1011, the existence of an Outlines `mlxlm` backend, the json-repair 0.59.10 release date (May 14, 2026), and the Qwen3-8B 36-layer / 32Q-8KV-head architecture.
- **Inferred** (not measured for Qwen3-8B-4bit specifically but cross-supported by similar models on the same stack): the 3–8% schema-drift rate range for nested JSON, the diminishing return on > 2 few-shot examples, the practical 16K input + 1–4K output budget on 8 GB unified memory.
- **Extrapolated**: the quantization-quality delta from MMLU/PPL numbers in Zheng et al. (which measure general capability, not GEC) onto grammar-checking specifically; the Qwen3-8B 4-bit → 8-bit recommendation threshold (`≥ 12 GB free`); the N8 Programs "8-bit essentially lossless" finding (measured on Qwen3-4B-2507-Instruct) applied to Qwen3-8B.
- **Potentially outdated**: the Outlines #1131 rep-penalty gap is documented from late 2024–2025; check Outlines's current release notes before relying on it. The MLX engine moves fast — anything older than September 2025 in this domain should be re-verified against the v0.31.3 source tree before shipping.
- **One conflict noted**: mlx-lm's server doc says `repetition_penalty` defaults to `0.0`; the Python sampler API treats `1.0` as the no-op identity (anything other than 1.0 is multiplicative). The intent (no penalty by default) is consistent; just don't trust the literal "0.0" in SERVER.md — pass `1.05` if you want a mild penalty, not `0.05`. Source: comparing https://github.com/ml-explore/mlx-lm/blob/main/mlx_lm/SERVER.md against `mlx_lm/sample_utils.py`.
- **No GEC benchmarks of Qwen3-8B exist publicly** (verified). Any quality claim about grammar correction performance for this specific model is by transfer from MMLU / PPL / general-capability numbers, not from direct measurement. Plan to measure on your own L2 set before depending on it for end users.