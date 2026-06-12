# Research & Decisions: Engine-Aware Onboarding (015)

Phase 0. Every decision is verified against current code on the
`015-engine-aware-onboarding` branch (based on `fix/low-effort-improvements`). No open
NEEDS CLARIFICATION items remain.

## Current-state findings (verified against code)

- **F1 — the local feedback model is never auto-downloaded.** `cli/practice.py:362` is the
  only `ensure_models` call in a user flow, always with phase `"A"` (listen-only) or `"B"`
  (full). `PHASE_C_MODELS` (which adds `QWEN3_14B_4BIT`) is referenced only by `doctor`
  (`cli/doctor.py:45`) and by `_build_grammar_analyzer`'s presence check
  (`cli/practice.py:520`). There is **no** CLI path that downloads Qwen, yet
  `DEFAULT_ENGINE = "local"` (`config/loop_config.py:21`). → A default clone yields sessions
  with no grammar feedback.
- **F2 — persistence half-exists.** `loop.yaml` already has an optional `engine:` key
  (`config/loop_config.py:41,71-73`, default `local`) and `resolve_engine_choice`
  (`cli/practice.py:275-299`) already reads it (`--engine` → `loop.yaml engine:` → `local`).
  Nothing **writes** the key; `loop_config.py` is read-only.
- **F3 — `doctor` false-fails for cloud users.** `_models()` (`cli/doctor.py:43-58`) iterates
  `PHASE_C_MODELS` and marks any missing model `FAIL`, including Qwen — even when the active
  engine is a cloud engine that never needs it. `_any_fail` then exits non-zero.
- **F4 — `--cloud` is already a clean alias.** `resolve_engine_choice` treats `--cloud` as
  exactly `--engine openrouter` and raises `EngineSelectionError` on a conflicting combo. No
  change needed beyond clarity/docs.
- **F5 — the question loader already gives precise errors.** `content/loader.py` surfaces
  `file:line` on YAML error and `file + entry id + missing field` on schema error;
  `content/schema.py` returns non-fatal `warnings`. The feature only needs to *expose* this.
- **F6 — graceful degradation already exists for a missing local model.** `_build_grammar_analyzer`
  returns `None` when Qwen is absent (`cli/practice.py:516-521`), and the coordinator writes a
  recorded, resumable, Phase-B report. The feature preserves this for the decline path.
- **F7 — tests default the active engine to `local`.** The autouse `_isolate_loop_config`
  fixture (`tests/conftest.py:107-120`) points `loop_config_path()` at an empty temp file, so
  `loop_config.load().engine == "local"` everywhere unless a test writes the file. Existing
  doctor tests therefore keep their current FAIL-on-missing-Qwen behavior; only new tests that
  set a cloud engine exercise the new branch.

## Decisions

### D1 — Onboarding entry point: a single `setup` command

**Decision**: Add one flat `speakloop setup` command that (a) resolves+persists the engine,
(b) provisions exactly what that engine needs, (c) reports cloud-credential readiness, and
(d) prints a readiness summary. **Rationale**: matches the existing flat command style
(`practice`, `doctor`, `today`, …); one discoverable verb covers the whole "clone → ready"
arc (SC-001). **Alternatives**: a generic `config set engine X` (rejected — splits onboarding
across two commands and exposes a config-editing surface the spec does not ask for); folding
everything into `practice` (rejected — provisioning + persistence + readiness is a distinct
job from running a session, and `setup --no-download` needs to exist independently).

### D2 — Persist to the existing `loop.yaml engine:` key via a read-modify-write writer

**Decision**: Add `loop_config.save_engine(engine)`: validate against `VALID_ENGINES`, read
the existing mapping (tolerating absent/malformed → `{}`), set `engine`, write with
`yaml.safe_dump(sort_keys=False)`, creating the parent dir. **Rationale**: reuses the key
that resolution already reads (F2); YAML-only (constitution); read-modify-write preserves any
other keys the user set. **Trade-off**: pyyaml does not preserve comments — a hand-commented
`loop.yaml` loses comments on rewrite. Accepted: `loop.yaml` is rarely hand-authored, the file
is small and self-describing via `doctor`/README, and a comment-preserving round-trip
dependency (ruamel) is unjustified weight (constitution: boring over novel). **Alternatives**:
textual line-patch (rejected — fragile against arbitrary formatting); new dedicated engine file
(rejected — second config surface, violates "YAML, one config" simplicity).

### D3 — Writing config is explicit-only; nothing auto-creates `loop.yaml`

**Decision**: Only `setup` ever writes `loop.yaml` (FR-005). `practice`/`resume`/`doctor` never
write it. **Rationale**: preserves the documented "no file is auto-created in your home
directory" guarantee (config/CLAUDE.md, loop_config docstring); the write is a user-initiated
action, the same model as the OpenRouter token store.

### D4 — Engine→model provisioning predicate in the installer

**Decision**: Add `installer.engine_needs_local_llm(engine, *, listen_only) -> bool`
(`engine == "local" and not listen_only`). The CLI computes the base phase (`"A"`/`"B"`) and
calls this predicate to decide whether to also provision Phase C. **Rationale**: the installer
already owns "what models does a phase need"; this keeps the engine→models mapping in one
testable, import-light place and out of the CLI's control flow. **Alternatives**: a single
`models_for_engine()` returning a flat list (rejected — the base models and the local LLM have
**different decline semantics**: base is required→exit, the LLM is optional→degrade, so they
cannot share one consent/return path).

### D5 — Two-step provisioning in `practice`: required base, optional local LLM

**Decision**: keep `ensure_models(base_phase)` required (decline→exit, unchanged). For
`local` + full session with the model absent, call `ensure_models("C")` wrapped to treat
`InstallDeclinedError`/`InstallFailedError` as "continue degraded". **Rationale**: TTS+ASR are
genuinely required to record; the feedback LLM is not (F6, Principle XII). Two consent prompts
on a totally-fresh `local` direct-`practice` run is acceptable; `setup` is the smoother guided
path. **Alternatives**: one `ensure_models("C")` for local (rejected — makes Qwen *required*,
so declining the 8 GB model would abort an otherwise-recordable session).

### D6 — Cloud engines never reference the local feedback model

**Decision**: for `openrouter`/`claude`, `practice` and `setup` provision only base `"B"`
and never call `ensure_models("C")` (D4 predicate is `False`). **Rationale**: FR-007/SC-002 —
a cloud user is never pushed through the large local download.

### D7 — `doctor` becomes engine-aware without breaking existing gates

**Decision**: in `_models()`, the local-feedback row (`required_for_phase == "C"`) FAILs on
absence **only** when `active_engine() == "local"`; otherwise it renders a non-failing
"not required for the active engine (<engine>)" row. TTS/ASR rows keep FAIL-on-missing; every
model row still renders. Add a `_feedback_engine()` section (active engine + readiness +
next-step) using `engine_status`; its cloud/claude rows are non-failing (opt-in convention,
matching the existing Cloud/Claude Code sections). **Rationale**: fixes F3 while keeping
`test_missing_model_fails` (default engine `local` → Qwen + TTS/ASR all FAIL),
`test_doctor_failure_modes` (all model names still rendered), and `test_doctor_claude_rows`
(opt-in rows never FAIL) green. A FAIL model remediation keeps the `speakloop practice`
substring the existing test asserts.

### D8 — `questions` command group reusing the existing loader/schema

**Decision**: a `questions` typer sub-app with `validate [PATH]`, `template`, `where`.
`validate` calls `content.load()` (no new validation logic) and formats success/error +
warnings; `template` prints a canonical commented YAML to **stdout**; `where` prints the
precedence chain + active file. **Rationale**: F5 — the precise errors already exist; the gap
is exposure + discoverability + a template. Sub-app keeps three related verbs grouped and
discoverable (`speakloop questions --help`). **Alternatives**: flat `validate-questions`
(rejected — three loose verbs clutter the top-level help and lose grouping).

### D9 — Template is a stdout artifact, never written to home

**Decision**: `questions template` prints to stdout; the user redirects it
(`> ~/.speakloop/qa.yaml`) if they want. The canonical text lives in `content/template.py`
(single source of truth, next to the schema it must satisfy). **Rationale**: preserves the
no-auto-create guarantee (FR-019/SC-007); keeps the template provably valid by testing it
against `content.load()` (SC-006).

### D10 — Cloud credential readiness is reported, not deep-validated, in setup

**Decision**: `setup`/`doctor` report openrouter token presence via `resolve_token()` (env/file,
no network) and Claude Code status via the credit-free local `doctor_probe()`; they print the
exact next step. Deep token validation (a network `check_auth`) stays on the existing
`practice --cloud` first-run path. **Rationale**: keeps `setup`/`doctor` fast and offline-safe
(constitution II) while still telling the user what to do; avoids duplicating the validation
flow already in `practice.py`.

## Test seams (no live engines, no real binary — `.claude/rules/testing.md`)

- `loop_config.save_engine` → write to the temp `loop_config_path()` the autouse fixture
  installs; assert round-trip + key preservation.
- `installer.engine_needs_local_llm` → pure truth-table unit test.
- `cli/setup` → monkeypatch `installer.ensure_models` to record `(phase)` calls; inject
  `input_fn`; set `SPEAKLOOP_HOME` to tmp; assert cloud→{"B"} only, local→{"B","C"},
  persistence written, `--no-download`→no ensure calls.
- `cli/questions` → CliRunner; valid fixture passes, invalid fixture names entry+field,
  `template` output round-trips through `content.load()`.
- `cli/doctor` → write a cloud `engine:` to the temp loop config; assert missing-Qwen does
  not FAIL and active engine is named; keep existing local-default cases.
- `cli/engine_status` → unit test the readiness model per engine with monkeypatched
  validator/credentials/probe.
