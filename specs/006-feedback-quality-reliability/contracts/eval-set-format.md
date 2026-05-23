# Contract: Held-out evaluation set, scoring, and offline harness

**Feature**: 006-feedback-quality-reliability · **Phase**: 1 · **Location**: `eval/` (repo root, NOT in `src/speakloop/`)

This is the instrument that makes SC-001 (failure rate) and SC-002 (grammar agreement)
falsifiable. It is a **validation artifact, not an end-user feature** (FR-020): nothing under
`eval/` is imported by the CLI or shipped in the wheel (`[tool.hatch.build.targets.wheel]
packages = ["src/speakloop"]` already scopes the wheel to the package).

## 1. Case file — `eval/grammar/cases/case-NNN.yaml`

```yaml
id: case-001
source: synthetic            # synthetic | deidentified  (NEVER a real recording — Principle III)
l1: persian
transcripts:                 # 1–3 attempt strings, fed to grammar_analyzer.analyze(...)
  - "I am working on this project since two years and still I am learn new things."
gold_issues:                 # human ground truth; [] is valid and valuable (false-alarm cases)
  - attempt_ordinal: 1
    quote: "since two years"        # MUST be a verbatim substring of transcripts[ordinal-1]
    label: preposition              # catalog label OR an explicit open-bucket label
    correction: "for two years"
    explanation: "Use 'for' with a duration."
notes: "Why this is/ isn't an error; adjudication for ambiguous calls."
```

Validation (a harness self-check, runnable without the model):
- **E1** every `gold_issues[].quote` ∈ `transcripts[attempt_ordinal-1]` (verbatim).
- **E2** every `label` is in `feedback/persian_l1_catalog.yaml` **or** flagged open-bucket.
- **E3** no personal data, no real names, no audio, no machine paths — the existing
  `tests/integration/test_path_portability_audit.py` MUST still pass over `eval/`.
- **E4** 20 ≤ N ≤ 30 cases; ≥1 transcript each; include some empty-`gold_issues` cases.

`eval/grammar/PROTOCOL.md` (labeling rubric + taxonomy + adjudication) and `eval/grammar/README.md`
(provenance, de-identification, how to run) ship alongside.

## 2. Baseline / post record — `eval/grammar/baselines/{baseline-pre,post}.yaml`

```yaml
captured_at: 2026-05-2x
phase: pre                   # pre (today's code, before any change) | post
model_id: mlx-community/Qwen3-8B-4bit
quant: 4bit                  # records the quantization run (this sprint: always 4bit — Decision 2)
eval_set_version: <git sha of eval/grammar/cases at capture>
runs_per_case: 3             # K repeated runs; metrics below are the per-unit median (temp 0.7 is stochastic)
# Failure rate (SC-001) — a separate, larger UNLABELED batch so a ~1% rate is observable:
failure_batch_size: 120      # ≥100 synthetic/replayed sessions; no human labels needed
failure_rate: 0.NN
# Grammar agreement (SC-002) — the 20–30 labeled cases only:
n_labeled_cases: 25
grammar: {precision: 0.NN, recall: 0.NN, f05: 0.NN}
```

## 3. Scoring contract

Two distinct instruments (FR-020): **grammar agreement** is scored on the 20–30 labeled cases;
the **failure rate** is measured on a separate, larger unlabeled batch (§3a).

- **Match** (labeled set): predicted evidence ↔ gold issue iff same `attempt_ordinal`, quotes overlap
  (either ⊆ the other, case-insensitive), labels compatible. One gold ↔ at most one prediction.
- **Metrics** (labeled set, SC-002): `precision = matched/predicted`, `recall = matched/gold`, **`F0.5`** (precision-weighted; a false alarm costs a learner more than a near-miss). **Pass bar**: F0.5 clears the pre-registered improvement threshold **and** neither precision nor recall falls below baseline — no regression on either axis.
- **Failure** (counts toward `failure_rate`): analyzer raises, returns unusable/garbled output,
  or the session would fall back to Phase-B.

### 3a. Failure-rate batch (SC-001)

`failure_rate` is measured over a **separate batch of ≥100 synthetic/replayed sessions**
(`eval/grammar/failure_batch/*.yaml`), **not** the 20–30 labeled set: a 20–30 case set cannot
observe a ~1% rate (one failure ≈ 3–4%). These sessions need **no human labels** — failure
detection (raise / unusable-or-garbled output / Phase-B fallback) requires none. A single measure
run scores agreement on the labeled cases and failure rate on this batch in one pass.

## 4. Harness invocation (offline, manual / `live_llm`-marked)

```bash
# Validate the set without the model (CI-safe, fast, deterministic):
uv run python eval/grammar/run_eval.py --validate-only

# Measure against the local model (developer machine, model already downloaded):
# --runs 3: repeat each unit K times and record the per-unit median (temp 0.7 is stochastic).
uv run python eval/grammar/run_eval.py --phase pre  --runs 3 --out eval/grammar/baselines/baseline-pre.yaml
uv run python eval/grammar/run_eval.py --phase post --runs 3 --out eval/grammar/baselines/post.yaml
```

- **Offline** (Principle II): calls only the already-downloaded local model; if the model is
  absent it prints "model unavailable — skipped" and exits non-zero **without** a network fetch.
- **No live model in the default test suite** (Constitution Dev Guidelines): the measuring run
  is manual or guarded by a `live_llm` pytest marker (mirroring the existing `live_asr` marker),
  excluded from `uv run pytest`. The `--validate-only` self-check (E1–E4) MAY run in CI because
  it touches no model.
- Stability under sampling (temperature 0.7): seeding alone is **insufficient** — grammar
  generation is stochastic, so the harness MUST run each unit **K ≈ 3 times** (`--runs`, recorded
  as `runs_per_case`) and report the per-unit **median/mean**. It also seeds generation where the
  engine allows and always stamps `eval_set_version`, so `pre`/`post` are compared
  on identical inputs and a single unlucky sample cannot flip a verdict.

## Test obligations

- T-E1 `--validate-only` enforces E1–E4 and fails on a planted bad case (bad quote / unknown label / planted path leak).
- T-E2 the scorer matches a hand-checked prediction↔gold example and computes precision/recall/F0.5 correctly (pure-function unit test, no model).
- T-E3 `eval/` contributes zero runtime imports to the shipped package (import-graph / wheel-content check).
