# Implementation Plan: Reliable, Higher-Quality Session Feedback

**Branch**: `006-feedback-quality-reliability` | **Date**: 2026-05-22 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/006-feedback-quality-reliability/spec.md`

## Summary

Make the three existing AI-derived feedback components — grammar suggestions, the cross-attempt
narrative, and the single top-priority pick — reliably higher-quality **without** new feedback
dimensions, **without** a model swap, and **without** any report-format change. The work concentrates
on the single LLM call site (grammar analysis): apply the Qwen3-8B vendor non-thinking config
(`temperature=0.7`, the already-correct `top_p/top_k/min_p`), add the missing repetition control
(`repetition_penalty=1.05`, `repetition_context_size=40`) and defensive `stop`, replace the brittle
hand-rolled JSON repair with `json-repair` plus a bounded regenerate, and keep the existing
verbatim+coherence+no-op verification intact. The narrative and top-priority **stay deterministic**
(Decision 1) and improve by inheriting cleaner grammar inputs and tightened grounding. A held-out
eval set + offline harness make the failure-rate and grammar-agreement gains measurable
(baseline → post). Source of truth for all config/prompt/recovery decisions: `doc/QWEN_IMPROVMENT_RESEARCH.md`
(lifted into [research.md](./research.md)).

## Technical Context

**Language/Version**: Python 3.12 (pinned `>=3.12,<3.13`, `pyproject.toml:7`).

**Primary Dependencies**: existing — `mlx-lm>=0.31.3` (already satisfies research R4), `typer`, `rich`,
`pyyaml`, `python-frontmatter`, `numpy`. **New (one)**: `json-repair` (offline, pure-Python, zero
required runtime deps; replaces the hand-rolled regex repair) — see Complexity Tracking.

**Storage**: session reports stay Markdown + YAML frontmatter in `data/sessions/`, **`schema_version: 1`
unchanged**. New validation data lives **outside the package** in `eval/grammar/` (cases + failure batch + baselines,
YAML).

**Testing**: `pytest`. Repair/wrapper-config/invariance tests use **cached fixtures + monkeypatched
`mlx_lm`** (no live model — Constitution Dev Guidelines). On-device measurement is **manual / a new
`live_llm` marker**, excluded from default `pytest` (mirrors the existing `live_asr` marker).

**Target Platform**: macOS Apple Silicon (Principle VII).

**Project Type**: single-project local CLI (library + `typer` app). No frontend/backend split.

**Performance Goals**: bounded recovery (≤ 1 regenerate) so a bad session never hangs (FR-003);
analysis cost not materially higher (rep-penalty + json-repair are cheap); `failure_rate ≤ 1%` under
normal operating conditions (SC-001).

**Constraints**: fully offline after download (II); English-only output (I); `schema_version` stays 1,
additive-only keys (IX, FR-018); all engine specifics confined to `llm/qwen_engine.py` (V); no GUI, no
`pip` workflow, no non-YAML user config (Non-Negotiables).

**Scale/Scope**: single-user local tool; ~1 wrapper file + 1 analyzer + 1 deterministic narrative
touched; eval set 20–30 labeled cases + a ≥100-session unlabeled failure batch (SC-001).

## Constitution Check

*GATE: must pass before Phase 0. Re-checked after Phase 1 design (below).*

| Principle / Constraint | Verdict | Notes |
|---|---|---|
| **II Offline-First** (FR-016, FR-019) | ✅ PASS | No Phase-0 finding adds a network call. `json-repair` is pure-Python/offline; the eval harness uses only the already-downloaded local model and prints "model unavailable" rather than fetching. Verified by V-R4 + the existing engine-import offline guard. |
| **IX / Dev-Guidelines Stable schema** (FR-018) | ✅ PASS | `SCHEMA_VERSION` stays **1**; **no** frontmatter key added this sprint. Recovery telemetry is in-process only (data-model §3). Any future field is additive+optional (the `asr:`/`phase_c_error` pattern). `dump→parse→dump` idempotence preserved (V-R2). |
| **V Swappable Engines / single wrapper** (FR-019) | ✅ PASS | Sampler, `repetition_penalty`, `stop`, and `enable_thinking=False` are all constructed **inside `qwen_engine.py`**; the analyzer call site passes intent only. Dual-mode thinking is **not** adopted (Decision 1), so nothing leaks; the deferred dual-mode design keeps the mode a wrapper-internal param. `mlx_lm` import stays function-local (T-G5). |
| **I English-Only** | ✅ PASS | No new locale surface; any changed user-facing string stays English (I6). |
| **IV Modular + per-module CLAUDE.md** | ✅ PASS | Touches `llm/` and `feedback/`; both already have `CLAUDE.md` and will be updated (traps: new config, json-repair). Root `CLAUDE.md` SPECKIT block + maintenance checklist updated. |
| **X Research in repo** | ⚠ ACTION | Config + quantization decision must be reflected in the canonical `doc/research_llm.md` (cross-link `doc/QWEN_IMPROVMENT_RESEARCH.md`, note the new sampler/rep-penalty + the firm **4-bit-only** decision — 8-bit out of scope this sprint, Constitution VI/VII). Not a violation if done in the same change; tracked as a task. |
| **XII Iterative Delivery** | ✅ PASS | US1 (reliability) ships as a standalone slice; US2/US3 layer on without breaking it. |
| **Non-Negotiables** (uv, YAML, CLI, no new external service) | ✅ PASS | `uv` only; eval data is YAML; CLI unchanged; the only external interaction remains the HF model download. New dep installed via `uv`. |

**Result: PASS** (one ⚠ action, not a blocker — the Principle X doc update is a task, not a gate failure).

## Project Structure

### Documentation (this feature)

```text
specs/006-feedback-quality-reliability/
├── plan.md              # this file
├── spec.md
├── research.md          # Phase 0 — verified findings lifted + 3 decisions + measurement tasks
├── data-model.md        # Phase 1 — entities (GrammarPattern unchanged; eval set; baseline)
├── quickstart.md        # Phase 1 — before/after validation workflow
├── contracts/           # Phase 1
│   ├── grammar-output-schema.md   # model output + generation config + recovery ladder
│   ├── eval-set-format.md         # held-out set + scoring + offline harness
│   └── report-invariance.md       # "nothing the user sees changes" guardrail
├── checklists/requirements.md     # from /speckit-specify
└── tasks.md             # Phase 2 — created by /speckit-tasks (NOT here)
```

### Source code (repository root) — files this feature touches

```text
src/speakloop/
├── llm/
│   ├── qwen_engine.py        # + repetition_penalty/context_size, + stop=["<|im_end|>"],
│   │                          #   sampler temp default → 0.7; enable_thinking=False already set
│   ├── interface.py          # generate(): signature stable, OR additive optional params w/ defaults
│   └── CLAUDE.md             # update traps: rep-penalty/stop config now owned here
├── feedback/
│   ├── grammar_analyzer.py   # remove temp=0.2 override; swap hand-rolled repair → json-repair;
│   │                          #   add bounded regenerate; KEEP V1–V5 verification + dedupe
│   ├── narrative.py          # tighten deterministic grounding (no LLM); stays reproducible
│   └── CLAUDE.md             # update: json-repair dependency, grounding note
└── (report_builder.py, frontmatter.py: NO structural change — invariance contract)

eval/                          # NEW — repo root, NOT in the wheel (validation only, FR-020)
└── grammar/
    ├── cases/case-NNN.yaml    # 20–30 labeled cases (synthetic / de-identified)
    ├── failure_batch/*.yaml   # ≥100 unlabeled synthetic/replayed sessions (SC-001 failure rate)
    ├── baselines/             # baseline-pre.yaml, post.yaml
    ├── run_eval.py            # --validate-only | --phase {pre,post} [--model …]
    ├── PROTOCOL.md            # labeling rubric + taxonomy + adjudication
    └── README.md              # provenance, de-identification, how-to-run

tests/                         # new repair-fixture, wrapper-config, invariance, offline tests;
                               # + `live_llm` marker registration (excluded by default)
pyproject.toml                 # + json-repair ; (optional explicit mlx floor) ; + live_llm marker
doc/research_llm.md            # Principle X: reflect config + quant decision; cross-link research doc
CLAUDE.md                      # root: SPECKIT block active→006, traps, maintenance checklist run
```

**Structure Decision**: Single project; reuse the existing module layout. The only new top-level
directory is `eval/`, deliberately **outside `src/speakloop/`** so it is never imported by the CLI or
shipped (the wheel is already scoped to `packages = ["src/speakloop"]`). This keeps the validation
harness a first-class but non-shipping artifact (FR-020).

## Phase sequencing (for /speckit-tasks)

1. **Foundational** — A-EvalSet (build `eval/grammar/` + `run_eval.py --validate-only`) → A-Baseline
   (`phase: pre` on current code). *Must precede analyzer changes* (quickstart §0).
2. **US1 (P1) Reliability** — wrapper config (R1/R2/R5), json-repair + bounded regenerate (Decision 3),
   dedupe; repair-fixture + wrapper-config + offline tests.
3. **US2 (P2) Grammar accuracy** — prompt/few-shot tuning within the flat schema (R7); re-measure
   agreement against the baseline (model stays 4-bit — Decision 2).
4. **US3 (P3) Narrative + top-priority** — tighten deterministic grounding; invariance/golden tests.
5. **Polish** — `post` measurement, subjective review, Principle X doc update, CLAUDE.md updates.

## Complexity Tracking

| Violation | Why needed | Simpler alternative rejected because |
|---|---|---|
| **New dependency `json-repair`** (vs Constitution "stdlib over dependencies") | The research-recommended output-recovery safety net; directly serves SC-001/SC-004; **removes ~5 brittle regexes** (net simplicity). Offline, pure-Python, zero required deps. | Hardening the existing hand-rolled regex repair keeps zero new deps but adds more "clever" brittle code the constitution disfavors; it is retained only as the documented fallback if the maintainer vetoes the dependency. |
| **New top-level `eval/` directory** | A held-out labeled set + offline harness are required to make SC-001/SC-002 falsifiable (FR-020); must live outside the shipped package. | Putting eval code in `src/speakloop/` would ship validation-only tooling to users and risk CLI import; a `tests/`-only home can't hold the labeled corpus + manual live-model harness cleanly. |

## Post-Phase-1 Constitution re-check

Design artifacts introduce no new violation: contracts confirm offline (eval-set-format §4),
schema invariance (report-invariance I1–I2), and wrapper encapsulation (grammar-output-schema §B).
The two Complexity-Tracking items are the only justified deviations. **Gate: PASS.**
