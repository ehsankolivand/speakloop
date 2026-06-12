# Data Model: Engine-Aware Onboarding (015)

No persistent schema changes. This feature reuses existing storage; the "entities" below are
conceptual views over current structures. The report `schema_version` and the question-file
schema are untouched.

## E1 — Persisted feedback-engine selection

- **Where**: `~/.speakloop/loop.yaml`, key `engine:` (already defined; `config/loop_config.py`).
- **Type / values**: string ∈ `VALID_ENGINES = ("local", "openrouter", "claude")`.
- **Default**: `"local"` (silent; absent/invalid → default, via existing `load()`).
- **Read by**: `resolve_engine_choice` (`cli/practice.py`), `resume`, `doctor`, `engine_status`.
- **Written by**: `loop_config.save_engine(engine)` — **new**, called **only** from `setup`.
- **Invariants**:
  - Resolution precedence unchanged: explicit `--engine` flag → `loop.yaml engine:` → `"local"`.
  - `--cloud` is an exact alias for `--engine openrouter`; conflicting combo → `EngineSelectionError`.
  - Writing is explicit-only; no normal run creates/edits `loop.yaml` (FR-005).
  - `save_engine` rejects values outside `VALID_ENGINES`; preserves other keys; never logs secrets.

## E2 — Engine requirement profile (derived, not stored)

The mapping from an active engine + run mode to what must be present for a "ready" session.

| Active engine | Speech (TTS, Phase A) | Transcription (ASR, Phase B) | Local feedback LLM (Phase C) | Credentials / binary |
|---|---|---|---|---|
| local | required | required (full session) | required (full session) — degrade if declined | — |
| openrouter | required | required (full session) | **never** | OpenRouter token (env or `~/.speakloop/openrouter_token`) |
| claude | required | required (full session) | **never** | Claude Code CLI installed + logged in |

- **Listen-only** needs only Phase A regardless of engine; never the local feedback LLM.
- **Predicate**: `installer.engine_needs_local_llm(engine, *, listen_only)` = `engine == "local"
  and not listen_only` — the single source of truth used by `practice`, `setup`, `doctor`.
- **Base phase**: `"A"` if `listen_only` else `"B"` (always required; decline → abort, unchanged).

## E3 — Readiness model (derived, in-memory)

Produced by `cli/engine_status.py`, consumed by `doctor` (as `CheckRow`s) and `setup` (printed lines).

```
EngineReadiness:
  engine: str                     # active engine
  requirements: list[Requirement] # one per checkable need
  ready: bool                     # all hard requirements satisfied

Requirement:
  label: str        # e.g. "local feedback model", "OpenRouter token", "Claude Code CLI"
  ok: bool          # satisfied?
  optional: bool    # cloud creds/binary are opt-in (never fail the exit code)
  detail: str       # current state, English
  next_step: str    # exact remediation when not ok ("" when ok)
```

- `local`: requirement = local feedback model present (`validator.validate(QWEN3_14B_4BIT).ok`),
  `optional=False`. `ready` reflects it.
- `openrouter`: requirement = token resolvable (`openrouter_credentials.resolve_token()`),
  `optional=True`. Always renders non-failing; `next_step` names env var / `practice --cloud`.
- `claude`: requirement = CLI installed + logged in (`claude_code_engine.doctor_probe()`),
  `optional=True`. Non-failing; `next_step` names install / `claude /login`.

## E4 — Question-file template (static artifact)

- **Where**: `content/template.py` → `template_text() -> str` (single source of truth).
- **Shape**: a `schema_version: 1` document with a non-empty `questions:` list of 2–3 commented
  entries spanning `type` values (`definition`, `behavioral`, `hypothetical`) and showing
  optional `tags`/`difficulty`/`voice_override`.
- **Invariant**: `content.load()` on `template_text()` succeeds with zero schema errors (SC-006);
  emitted to stdout only — never written to the home directory (FR-019/SC-007).
- **Consumers**: `questions template` (prints it); a unit test (round-trips it).

## E5 — Question-file precedence (unchanged, now discoverable)

- Order (existing `paths.resolve_qa_file`): explicit `--qa-file`/`SPEAKLOOP_QA_FILE` →
  `~/.speakloop/qa.yaml` (if exists) → `content/questions.yaml` (if exists) → `None`.
- `questions where` surfaces this order + the currently-active file; `questions validate`
  defaults to the resolved file when no path is given. No precedence change; no auto-copy.
