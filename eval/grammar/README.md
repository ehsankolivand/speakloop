# `eval/grammar/` — held-out grammar evaluation harness

**Feature**: 006-feedback-quality-reliability. This directory is the **measurement instrument**
that makes two success criteria falsifiable:

- **SC-001** — failure rate of the grammar analyzer under normal operating conditions (`≤ 1%`).
- **SC-002** — grammar agreement (precision / recall / **F0.5**) versus a human-labeled gold set.

It is a **validation artifact, not a shipped feature** (FR-020). Nothing here is imported by the
CLI or included in the wheel (`[tool.hatch.build.targets.wheel] packages = ["src/speakloop"]`
scopes the wheel to the package; `eval/` sits outside it). A test (`T-E3`,
`tests/integration/test_eval_not_shipped.py`) enforces that.

## Layout

```
eval/grammar/
├── PROTOCOL.md           # labeling rubric + taxonomy + adjudication (read before authoring cases)
├── README.md             # this file
├── run_eval.py           # --validate-only (model-free) | --phase {pre,post} (live)
├── cases/                # 20–30 labeled cases (case-NNN.yaml) — agreement / SC-002
├── failure_batch/        # ≥100 unlabeled sessions (fb-NNN.yaml) — failure rate / SC-001
└── baselines/            # baseline-pre.yaml, post.yaml, thresholds.yaml
```

## Provenance & de-identification

All transcripts are **synthetic** (hand-authored to imitate Persian-L1 spoken technical English)
or **de-identified**. There are **no real recordings, no real names, no employer names, and no
machine paths** (Principle III). The path-portability audit
(`tests/integration/test_path_portability_audit.py`) runs over this directory and must stay green.

## How to run

```bash
# 1. Validate the set without the model (CI-safe, deterministic, fast):
uv run python eval/grammar/run_eval.py --validate-only
#    Enforces E1 (verbatim gold quotes), E2 (known/open-bucket labels),
#    E3 (no personal data/paths), E4 (20 ≤ N ≤ 30, ≥1 transcript each).

# 2. Capture the PRE baseline on CURRENT (unmodified) code — BEFORE any US1 change:
uv run python eval/grammar/run_eval.py --phase pre  --runs 3 --out eval/grammar/baselines/baseline-pre.yaml

# 3. After the analyzer/wrapper changes land, capture POST:
uv run python eval/grammar/run_eval.py --phase post --runs 3 --out eval/grammar/baselines/post.yaml
```

### The golden rule of ordering

The `pre` baseline MUST be captured on the code as it was **before** the US1 analyzer changes.
Because the implementation commits at each phase boundary, the unmodified pre-US1 code is preserved
in git at the **Foundational** phase commit — if a live `pre` capture was not taken before US1
landed, check out that commit and run step 2 there. `post` is captured on the final code against the
same `eval_set_version`.

### Offline & stochasticity

- **Offline** (Principle II): `--phase` runs call only the already-downloaded local model. If the
  model is absent the harness prints `model unavailable — skipped` and exits non-zero **without** a
  network fetch. `--validate-only` never touches the model.
- **Stochastic**: grammar generation samples at temperature 0.7, so each unit is run `--runs K`
  (default 3) and the **per-unit median** is recorded (`runs_per_case`). Seeding alone is
  insufficient to stabilize a `pre`/`post` verdict.
- The live `--phase` runs are **manual / `live_llm`-marked** and excluded from the default `pytest`
  (Constitution Dev Guidelines: no live-model calls in the normal suite).

## Reading the verdict

See `specs/006-feedback-quality-reliability/quickstart.md` §4. In short: `post.failure_rate ≤ 0.01`
and below `baseline-pre`; `post.grammar.f05` clears the threshold in `baselines/thresholds.yaml`
**and** neither precision nor recall regresses below `baseline-pre`.
