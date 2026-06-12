# Research & Decisions: Pronunciation Drills (016)

All external identifiers below were verified against primary sources (Hugging Face model
cards/file trees, PyPI JSON, project repos) on **2026-06-12**. The broad domain research
(approach, calibration ceiling, licensing landscape) lives in `doc/research_pronunciation.md`;
this file records the concrete engineering decisions and the deltas from that baseline.

## D1 — Scoring approach: read-aloud GOP, bundled canonical phonemes

**Decision**: Score only **read-aloud** drills (known target text). For each drill, force-align the
user's audio to a **bundled canonical phoneme sequence** and compute per-phone Goodness-of-Pronunciation
(GOP); at the drill's **target contrast** position compare P(expected phone) vs the top competing phone
to produce a hedged diagnosis.

**Rationale**: Reliable offline mispronunciation detection requires a known reference (the entire
GOP/L2-ARCTIC/speechocean762 literature assumes it). The "wrapper→rapper" case only works when we can
score the target /w/ against the canonical sequence; spontaneous scoring loses the signal (ASR just
transcribes the wrong word). Curated drills make the canonical phonemes knowable ahead of time.

**Alternatives rejected**: end-to-end MDD phone-string + Needleman-Wunsch (more moving parts, more
recognizer-error sensitivity); alignment-free GOP (research-grade, no packaged release).

## D2 — Canonical phonemes are BUNDLED, not computed at runtime (offline-critical)

**Decision**: Ship each drill's canonical phoneme sequence (in the model's own IPA symbol set) as
**bundled data** in `drill_bank.yaml`. The runtime does **not** call any grapheme-to-phoneme service.

**Rationale (the load-bearing offline decision)**: The baseline suggested `g2p_en` for canonical
phonemes. Verified finding: `g2p_en` (Apache-2.0, v2.1.0) **downloads NLTK data (`cmudict`,
`averaged_perceptron_tagger`) over the network on first use** via a `LookupError`→`nltk.download`
fallback (and the NLTK ≥3.8.2 tagger rename makes this fire even when a renamed tagger is present).
A runtime network fetch violates Constitution II (offline-first) and would break
`tests/integration/test_no_network_during_session.py`. Because the drill bank is **curated and known**,
we author the canonical sequences once at dev time and bundle them — eliminating g2p, NLTK, and any
network dependency from the runtime path.

**Authoring method (dev-time only, documented, not shipped)**: author each sequence in the model's
symbol set and validate every symbol against the model's downloaded `vocab.json` (392 labels); a
clean Kokoro-TTS rendering of the sentence passed once through the model is a useful cross-check
(greedy decode ≈ the canonical reference). `g2p_en` may be used as an **offline authoring aid** on a
dev machine with NLTK data pre-seeded — it is **not** a runtime dependency and is not declared.

**Future**: a general text→pronunciation hook for arbitrary user sentences (out of scope here).

## D3 — Acoustic model: `facebook/wav2vec2-lv-60-espeak-cv-ft`

**Decision**: Use this wav2vec2 CTC **phoneme** model. License **Apache-2.0**. Load via
`transformers` `Wav2Vec2ForCTC` + `Wav2Vec2Processor`. Output = space-separated IPA phoneme tokens
(vocab 392). Inference on **CPU**.

**Critical file-layout finding (drives D6)**: the repo ships **only `pytorch_model.bin` (~1.26 GB)** —
**no** `model.safetensors`, **no** `model.safetensors.index.json`. Aux files: `config.json`,
`preprocessor_config.json` (212 B), `vocab.json` (4.6 kB), `tokenizer_config.json`,
`special_tokens_map.json`. No `tokenizer.json`/`merges.txt`.

**CPU vs MPS**: CPU avoids MPS op-coverage gaps (some Conv1d/FFT ops fall back) and is deterministic;
a single short utterance scores in ~1–4 s, acceptable for a user-paced drill. `PYTORCH_ENABLE_MPS_FALLBACK=1`
+ MPS is a documented Future toggle.

**Footprint (gate basis)**: ~1.26 GB fp32 weights + ~1–1.5 GB activation peak ⇒ ~2–3 GB resident.
Comfortable in 18 GB **only** when the local Qwen feedback model is **not** resident — hence D5.

## D4 — Forced alignment + GOP: pure-numpy, no extra dependency

**Decision**: Implement CTC forced alignment (insert CTC blanks between canonical tokens; Viterbi over
the log-softmax `[T, vocab]` posteriors) and per-phone GOP in **pure numpy** inside `pronunciation/gop.py`.
GOP(phone) = mean log P(canonical phone) over its aligned frames; competitor = argmax non-blank phone
over those frames (diagnosis).

**Rationale**: `ctc_segmentation` (Apache-2.0) is **sdist-only** and compiles a **Cython** extension
against numpy; the repo resolves **numpy 2.4.5**, and the package's bundled C is numpy-1.x-era (open
build/staleness issues) — a real risk to the "git clone && uv run" install promise (Constitution VIII).
Constitution dev-guideline "standard library over dependencies; boring over novel" favors ~80 lines of
well-understood numpy we can unit-test exactly (synthetic posteriors) over a fragile build-from-source
dep. No torch/torchaudio/k2 touched.

**Alternatives rejected**: `ctc_segmentation` (build risk above); `ctc-forced-aligner`/MahmoudAshraf
(now pulls `torchcodec` → Trap 1, and is CC-BY-NC); torchaudio forced-align API (would tempt a
torchaudio bump — forbidden).

## D5 — Safety gate: engine-aware + live available RAM (psutil)

**Decision**: Before loading the model, compute a SAFE/UNSAFE decision from (a) the active feedback
engine (`loop_config.engine`) and (b) live available RAM (`psutil.virtual_memory().available`).

Gate logic (conservative; errs toward skipping):
- If the **active engine is `local`** (Qwen resident or about to be): **UNSAFE** by default — the local
  feedback model + the pronunciation model together blow the 18 GB budget. Reason: "you're using the
  local Qwen engine; adding the pronunciation model would likely exceed memory and freeze your machine."
- Else (cloud engine `openrouter`/`claude`): require **available RAM ≥ threshold**
  (`pronunciation_min_free_mb`, default **4500 MB** ≈ model peak ~3 GB + headroom). Below → UNSAFE
  ("low free memory"). At/above → SAFE.
- Setting `off` → no gate, no offer, no load. Setting `auto`/`on` → gate applies.
- UNSAFE + `auto`/`on` + interactive → offer the **explicit override** (a freeze-warned `[y/N]`,
  default N) before any load. Non-interactive (CI/tests) never overrides → skips.

**Rationale**: psutil's `.available` is the only reliable *available*-RAM source on darwin (stdlib
`SC_AVPHYS_PAGES` is unsupported; `resource` is per-process; `vm_stat` needs subprocess+heuristics).
psutil 7.2.2 is BSD-3, MIT-compatible, ships a macOS-arm64 wheel, zero transitive deps, no network.
The gate degrades gracefully if psutil import fails: treat available-RAM as unknown → only the engine
signal is used and a cloud engine without a RAM reading is treated conservatively (offer, but the
threshold check is skipped with a one-line note). The default threshold is an optional `loop.yaml`
key so a power user can tune it.

## D6 — Download: extend the aria2 downloader in place (FR-019/FR-020)

**Decision**: Register the model in `installer/manifest.py` (`WAV2VEC2_PRONUNCIATION`, **not** in any
Phase A/B/C list) and fetch it through the **existing** `downloader.download_model` /
`ensure_models` machinery. Two minimal in-place extensions, both required by D3's file layout:
1. Add an optional `Model.weight_files: tuple[str, ...] | None = None`. When set, `downloader` uses it
   directly instead of `shards.discover_shards` (which would otherwise fall back to the non-existent
   `model.safetensors` and 404). For this model: `("pytorch_model.bin",)`.
2. Add `preprocessor_config.json` to `downloader.META_FILES` (harmless to other repos — missing files
   are skipped). `vocab.json`/`config.json`/`tokenizer_config.json`/`special_tokens_map.json` are
   already in `META_FILES`.
A new `installer.ensure_pronunciation_model(...)` reuses the existing consent prompt (size disclosure),
`download_model`, validator, and caffeinate wakelock — no second download backend (installer Trap).
`validator` checks the model dir is ~1.26 GB ±25% (existing tolerance).

**Rationale**: Honors "single resilient download path, resumable, consent + size disclosure"
(FR-018/019/020, Principles VI/VIII). The `weight_files` field is additive and defaults to today's
behavior for every existing model (byte-identical aria2 invocation for them).

## D7 — Concurrency: background-thread `_analyze`, user-paced drills (FR-002/003/004)

**Decision**: In `coordinator.run_session`, when a drill capability is injected and the gate permitted
(decided in the CLI before the loop), run the existing `_analyze(...)` in a **background daemon
thread** while `_run_pronunciation_drills(...)` runs the interactive drill block on the main thread;
then **join** the analysis thread and assemble the report (incl. the pronunciation section).

Terminal-safety: two live `rich` displays must never run at once. Add `_analyze(..., quiet: bool)`;
when drills run concurrently, the backgrounded analysis is `quiet=True` (no live "Analyzing…" spinner;
plain degradation prints only). After the drills finish, the main thread joins under a single
`working(ANALYZING, "Finishing your feedback…")` spinner if analysis is still in flight. The drill
block is the only live display while it runs.

**Byte-identical guarantee**: `_analyze` produces the same `_AnalysisOutputs` whether called inline or
in a thread (it is pure w.r.t. the store; the single store mutation stays on the main thread after
join). The pronunciation section is additive-when-present. So `test_analysis_equivalence.py` and a new
`test_drills_additive_byte_identical.py` both hold; a no-drills session is byte-identical (SC-003).

**Abort**: drills check `abort.abort_event` between items and stop asking; the finished attempts +
joined feedback still produce a written report (never lose finished work), matching the existing
follow-up-stage abort semantics.

**No-op when absent**: exactly like `_run_warmup`/`_run_follow_ups`, the drill block is a no-op
(returns None) unless a scorer + drill bank + permission are injected — every existing caller/test is
unaffected.

## D8 — Calibration of report wording (FR-009)

**Decision**: Lead with **detection** ("the **w** sound in *wrapper* sounded off"); present any
phone-level diagnosis as a **suggestion** ("— it may have come out closer to **r**"); never assert the
substitution as fact. A per-drill confidence (GOP margin + competitor margin) decides whether to show a
diagnosis at all or only the detection.

**Rationale**: Verified literature ceiling — segmental detection is reliable; phone diagnosis is
< ~60% on hard cases, and benchmark numbers are optimistic vs noisy real speech. Honest calibration is
a spec requirement (FR-009) and protects the learner from chasing a wrong correction.

## D9 — Dependencies & licensing (MIT-clean, no GPL)

| Dep | Version (verified) | License | Status |
|---|---|---|---|
| `transformers` | 5.8.1 in lock; declare `>=4.34` | Apache-2.0 | declare (already transitive) |
| `torch` | 2.8.0 (present) | BSD-3 | keep; do **not** bump |
| `psutil` | 7.2.2 | BSD-3-Clause | **new** declared dep |
| model `wav2vec2-lv-60-espeak-cv-ft` | n/a | Apache-2.0 | opt-in download |
| `g2p_en` | 2.1.0 | Apache-2.0 | **not shipped** (authoring aid only; offline trap) |
| `ctc_segmentation` | 1.7.4 | Apache-2.0 | **rejected** (sdist Cython build risk) |
| `parselmouth`/`espeak`/`phonemizer` | — | GPL | **forbidden** (MIT project) |

## Open items resolved (no NEEDS CLARIFICATION remain)

- Default free-RAM threshold: **4500 MB** (overridable via `pronunciation_min_free_mb`).
- Drill setting key + values: `pronunciation_drills: auto|on|off`, default `auto`.
- Override UX: interactive freeze-warned `[y/N]` (default N); never in non-interactive mode.
- Per-run flags: `--drills` / `--no-drills` override the persisted default for one run (gate still applies).
- `resume`/`--listen-only`: no drills (live-only feature) — documented.
