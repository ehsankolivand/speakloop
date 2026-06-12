# CLI Command Contracts: Engine-Aware Onboarding (015)

Contracts for the new/changed command surface. Exit codes follow the existing convention
(`0` ok, `1` user-actionable failure, `2` bad invocation, `130` aborted). All output English.
No engine package is imported at CLI import (guarded by `test_help_without_models.py`).

---

## `speakloop setup` (NEW)

Pick + persist the feedback engine and provision exactly what it needs.

**Options**
- `--engine {local|openrouter|claude}` — choose the engine non-interactively. Omitted +
  interactive tty → numbered prompt defaulting to the current persisted engine; omitted +
  non-interactive → keep the current persisted engine (no prompt, no hang).
- `--no-download` — persist the choice and report readiness, but perform no model download
  in this invocation (FR-011).

**Behavior**
1. Resolve the target engine (per above); reject unknown values → exit `2`.
2. Persist to `loop.yaml engine:` via `loop_config.save_engine` (FR-001/FR-005); print the
   key + path written.
3. Unless `--no-download`: `installer.ensure_models("B")` (TTS+ASR, always — size disclosure
   + consent reused); if the engine is `local`, additionally `ensure_models("C")` (the local
   feedback model). Cloud engines never trigger Phase C (FR-006/FR-007).
4. Report cloud-credential readiness (no network): openrouter → token present? (offer to
   store one if absent); claude → `doctor_probe()` install/auth.
5. Print a readiness summary (via `engine_status`) with the exact next step for anything
   missing.

**Exit codes**: `0` configured (ready or with a clearly-stated next step); `1` a required
download was declined/failed; `2` invalid engine value.

**Guarantees**: never writes any home file other than `loop.yaml` (and, only if the user
opts to store one, the OpenRouter token); offline except the sanctioned model download.

---

## `speakloop questions` (NEW sub-app)

### `speakloop questions validate [PATH]`
- `PATH` optional; default = the precedence-resolved active file (`paths.resolve_qa_file`).
- Loads via `content.load()`. Success → `OK: <N> question(s)` + any warnings, exit `0`.
  Failure → the loader's precise message (file:line for YAML; file + entry id + field for
  schema), exit `1`. No resolvable file → actionable message naming the precedence, exit `1`.

### `speakloop questions template`
- Prints a canonical, schema-valid, commented question set (`content.template.template_text()`)
  to **stdout**. Writes no file. Exit `0`. (Redirect to save: `… > ~/.speakloop/qa.yaml`.)

### `speakloop questions where`
- Prints the precedence order and the currently-active file (with question count if loadable),
  or states none is found and how to add one. Exit `0`.

---

## `speakloop doctor` (CHANGED — additive)

- **Engine-aware models**: the local-feedback-model row (`required_for_phase == "C"`) is `FAIL`
  on absence **only** when the active engine is `local`; for a cloud active engine it renders a
  non-failing "not required for the active engine (<engine>)" row. TTS/ASR model rows keep
  `FAIL`-on-missing. Every model row still renders (keeps `test_doctor_failure_modes`).
- **New "Feedback engine" section**: active engine (from `loop.yaml engine:`), readiness, and
  next steps. Cloud/claude requirement rows are non-failing (opt-in convention).
- **Exit code**: still `1` if any always-required model or core precondition fails; a cloud
  user with only the local LLM missing now exits `0`.
- `--json` shape unchanged (list of rows with `status`).

---

## `speakloop practice` (CHANGED — provisioning only)

- Engine resolution, flags, and session behavior unchanged (`resolve_engine_choice`).
- **Provisioning**: required base `ensure_models("A" if --listen-only else "B")` (decline →
  exit `1`, unchanged). Then, when `engine_needs_local_llm(active_engine, listen_only=...)` and
  the local feedback model is absent, offer `ensure_models("C")`; declining or a failure prints
  one English notice and **continues** — the session records and writes a resumable report
  (FR-009). Cloud engines never trigger Phase C.
- No new network on the default local path after download (FR-022).

---

## Contract tests (mapping)

| Contract | Test |
|---|---|
| setup persists engine + cloud→{B}, local→{B,C}, `--no-download`→no ensure | `tests/unit/cli/test_setup.py`, `tests/integration/test_setup_flow.py` |
| `engine_needs_local_llm` truth table | `tests/unit/installer/test_engine_provisioning.py` |
| `save_engine` round-trip + key preservation | `tests/unit/config/test_loop_config_save.py` |
| questions validate/template/where | `tests/unit/cli/test_questions.py` |
| template round-trips through loader | `tests/unit/content/test_question_template.py` |
| doctor engine-aware (cloud→no FAIL on Qwen; active engine named) | `tests/unit/cli/test_doctor.py` |
| engine readiness model | `tests/unit/cli/test_engine_status.py` |
| practice provisioning by engine | `tests/integration/test_practice_engine_aware_download.py` |
| isolation preserved | existing `test_help_without_models.py`, `test_engine_import_isolation.py` |
