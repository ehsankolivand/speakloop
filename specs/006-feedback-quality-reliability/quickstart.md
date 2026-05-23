# Quickstart: Validating Reliable, Higher-Quality Session Feedback

**Feature**: 006-feedback-quality-reliability · **Audience**: maintainer / contributor

This feature is **invisible to end users** (the report looks the same — `contracts/report-invariance.md`).
Its "demo" is therefore a **before/after measurement**, not a new screen. This quickstart shows how to
prove SC-001 (failure rate ↓) and SC-002 (grammar agreement ↑) on a fresh checkout, fully offline.

> Prerequisite: the Phase-C model is already downloaded (`uv run speakloop doctor` shows it healthy).
> Everything below uses only that local model — no network (Principle II).

## 0. The golden rule of ordering

**Capture the baseline BEFORE any analyzer change ships.** Once the code changes, "today's level"
is gone. The sequence is: build eval set → baseline (pre) on *current* code → implement → post.

## 1. Build the held-out eval set (sprint deliverable A-EvalSet)

```bash
# 20–30 labeled cases live here, outside the shipped package:
ls eval/grammar/cases/            # case-001.yaml … (synthetic / de-identified L2 transcripts)
cat eval/grammar/PROTOCOL.md      # the labeling rubric + taxonomy + adjudication rules
```

Validate the set without touching the model (CI-safe, deterministic):

```bash
uv run python eval/grammar/run_eval.py --validate-only
# Enforces: verbatim gold quotes (E1), known labels (E2), no personal data/paths (E3), 20≤N≤30 (E4)
```

Format and rules: `contracts/eval-set-format.md`.

The **failure-rate batch** (≥100 unlabeled synthetic/replayed sessions, `eval/grammar/failure_batch/`)
is built alongside — it needs no human labels and feeds SC-001 only (the 20–30 labeled cases can't
resolve a ~1% rate).

## 2. Capture the pre-change baseline (A-Baseline → SC-001 & SC-002)

On **current** code, against the local 4-bit model:

```bash
uv run python eval/grammar/run_eval.py --phase pre \
    --out eval/grammar/baselines/baseline-pre.yaml
cat eval/grammar/baselines/baseline-pre.yaml   # failure_rate + grammar.{precision,recall,f05}
```

Pre-register the SC-002 F0.5 improvement threshold now — e.g. "F0.5 must improve ≥ X absolute" — and
record it next to the baseline. (8-bit is out of scope this sprint; the model stays
`mlx-community/Qwen3-8B-4bit` — Decision 2.)

## 3. Implement, then re-measure (post)

After the analyzer/wrapper changes land:

```bash
uv run pytest                       # full suite still green; report format unchanged (SC-005)
uv run python eval/grammar/run_eval.py --phase post \
    --out eval/grammar/baselines/post.yaml
```

## 4. Read the verdict

| Success criterion | Pass condition |
|-------------------|----------------|
| **SC-001** failure rate | `post.failure_rate ≤ 0.01` over the **≥100-session failure batch** (a 20–30 case set can't resolve 1%), and noticeably below `baseline-pre.failure_rate` |
| **SC-002** agreement | `post.grammar.f05` clears the pre-registered threshold **and** neither `precision` nor `recall` falls below `baseline-pre` (no regression on either axis) |
| **SC-004** clean output | zero garbled/looping/malformed/duplicate findings across the run |
| **SC-005** invariance | `uv run pytest` green; structural report diff empty (`contracts/report-invariance.md` V-R3) |
| **SC-006** offline + same model | no network during the run; Qwen3-8B family unchanged |
| **SC-003 / SC-007** subjective | blind paired review of pre/post reports (see below) |

## 5. Subjective review (SC-003, SC-007)

```bash
# Reuse real saved reports + freshly generated ones; review blind.
ls data/sessions/*.md
```

Pull a sample of recent pre-change reports and matched post-change reports; in a blind paired review,
confirm the post narrative is more accurate/grounded and the top-priority more meaningful (SC-003),
and that sampled corrections are grammatically correct with plain-language explanations (SC-007).

## 6. Offline & invariance smoke checks

```bash
uv run speakloop --help                                   # still loads no engine package (Principle VIII)
uv run pytest tests/integration/test_path_portability_audit.py   # eval/ adds no personal-path leak (E3)
# (new) a marked check that a full session+analysis makes zero network calls (SC-006, V-R4)
```

Live-model measurement (steps 2–3) is **manual / `live_llm`-marked** and excluded from default
`pytest` (Constitution Dev Guidelines: no live model calls in the normal suite). The `--validate-only`
self-check and all repair-fixture tests run model-free in CI.

Because grammar generation samples at temperature 0.7, steps 2–3 MUST run each unit **K ≈ 3 times**
(`--runs 3`) and report the per-unit **median/mean** (`runs_per_case` in the baseline record) —
seeding alone is insufficient to make `pre`/`post` verdicts stable. The failure
rate is taken over the **≥100-session failure batch** (`eval/grammar/failure_batch/`), not the
20–30 labeled cases.
