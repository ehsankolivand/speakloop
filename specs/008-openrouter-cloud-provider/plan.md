# Implementation Plan: OpenRouter Cloud-Model Provider

**Branch**: `008-openrouter-cloud-provider` | **Date**: 2026-06-08 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/008-openrouter-cloud-provider/spec.md`

## Summary

Add an **opt-in cloud mode** to `speakloop practice` that routes the Phase-C
grammar/coherence feedback step to an OpenRouter-hosted model instead of loading
the local Qwen3-14B weights — unblocking users whose machines cannot fit the
local LLM in RAM. Cloud mode swaps **only the LLM**: speech synthesis (Kokoro)
and transcription (Whisper/Parakeet) stay local and unchanged.

The technical approach is a textbook application of **Constitution Principle V
(Swappable Engines)**: a new `OpenRouterEngine` implements the existing
`LLMEngine` Protocol, so the engine-agnostic grammar pipeline
(`feedback/grammar_analyzer.py` — verbatim-substring verify, coherence filter,
dedup/rank, bounded regenerate) is reused untouched. The only entry-point change
is a `--cloud` flag on `practice` that selects which engine the analyzer runs
against, plus one additive, behavior-preserving optional parameter on
`analyze(...)` so cloud mode can supply its **own** system prompt without ever
referencing the local one.

Configuration is exposed through the project's existing conventions:
- **Token**: env `OPENROUTER_API_KEY` > `~/.speakloop/openrouter_token` (plain
  0600 file, mirroring the HF-token convention 007 already reads). Prompted once
  on first cloud run, stored, then reused silently.
- **Model id**: a `model:` key in a dedicated YAML config file
  `~/.speakloop/openrouter.yaml`, default `qwen/qwen3.7-max` (clarified Session
  2026-06-08 — chosen over an env var to honor the constitution's YAML-for-config
  mandate and persist across shells; `pyyaml` is already a dep, so no new dep).
- **Cloud system prompt**: a dedicated user-editable file
  `~/.speakloop/openrouter_prompt.txt`, seeded on first run from a packaged
  default asset — wholly separate from the local `_SYSTEM_PROMPT`.

Networking uses **stdlib `urllib.request`** — no new Python dependency
(Constitution dev guideline: "standard library over dependencies"). The default
local/offline path is byte-for-byte unchanged; network calls happen only while
`--cloud` is explicitly invoked.

## Technical Context

**Language/Version**: Python 3.12 (pinned `>=3.12,<3.13` in `pyproject.toml`).

**Primary Dependencies (Python)**:
- Existing only. **No new dependency.** OpenRouter HTTP uses stdlib
  `urllib.request` + `json`; CLI/console uses `rich`/`typer` (already deps); JSON
  recovery reuses the existing `json-repair` path in the analyzer.
- The local LLM (`mlx-lm`) stays a dep and is **not** loaded in cloud mode.

**Storage**:
- `~/.speakloop/openrouter_token` — plain file, mode `0600` (the secret).
- `~/.speakloop/openrouter.yaml` — cloud settings YAML; one `model:` key today
  (clarified Session 2026-06-08).
- `~/.speakloop/openrouter_prompt.txt` — user-editable cloud system prompt
  (seeded from a packaged default).
- No change to model storage, session-report layout, or `schema_version` (stays 1).

**Testing**: `pytest` with existing markers (`unit`, `integration`, `live_asr`).
One new opt-in marker proposed: `live_cloud` for a real OpenRouter round-trip
smoke test, mirroring `live_asr`/`live_download`; excluded from the default suite
(Constitution dev guideline: live model calls are forbidden in the default suite).

**Target Platform**: Apple Silicon macOS (Principle VII). Cloud mode is also the
path that helps users whose Macs cannot fit the local LLM.

**Project Type**: CLI (single-project layout under `src/speakloop/`).

**Performance Goals**:
- Cloud feedback latency is bounded by the OpenRouter round-trip + remote model
  time (replaces local inference time). No hard target; the win is **memory**,
  not latency — cloud mode never loads the ~10 GB-resident Qwen weights.
- `speakloop --help` / `--version` stay < 2 s and model-free (Principle VIII);
  cloud engine imports remain function-local.

**Constraints**:
- Default path stays fully offline (Principle II) — network only when `--cloud`.
- Cloud mode sends **attempt transcript text** (not audio, not reports) to
  OpenRouter — a Principle III trade-off, opt-in + disclosed (see Constitution
  Check + Complexity Tracking).
- Token never logged, never committed.
- Additive only: local Qwen flow unmodified beyond the entry-point branch and one
  backward-compatible optional `analyze(...)` parameter.

**Scale/Scope**:
- One new LLM engine, three config surfaces (token / model id / prompt file), one
  CLI flag, one additive analyzer parameter.
- ~4 new source files + ~5 small additive edits + doc/CLAUDE.md updates.

## Constitution Check

*GATE: must pass before Phase 0. Re-evaluated post-design (see end of file).*

| Principle / Constraint | Status | Argument |
|---|---|---|
| **I. English-Only UI** | ✅ Pass | All new console output (token prompt, disclosure line, error messages, doctor rows) is English. The seeded default cloud prompt is English. |
| **II. Offline-First** | ⚠️ Justified — see Complexity Tracking | Cloud mode makes network calls to OpenRouter, an explicit exception to "zero network calls after model download." Strictly **opt-in** (`--cloud`); the default path makes no new network calls and stays byte-for-byte offline (US3/SC-001, guarded by a test). |
| **III. Privacy by Design** | ⚠️ Justified — see Complexity Tracking | Cloud mode transmits the user's **attempt transcript text** to OpenRouter for analysis (audio recordings and reports never leave the device). This is inherent to cloud feedback. Mitigated by: opt-in `--cloud`, a one-time disclosure at cloud entry / token capture (informed, per-invocation consent in the spirit of Principle III), and the default path preserving Principle III fully. |
| **IV. Modular by Design** | ✅ Pass | New code is confined to existing module seams: `llm/` (engine + credentials), `feedback/` (cloud prompt loader + default asset), `config/` (path/setting accessors), `cli/` (entry-point branch). Each touched module's `CLAUDE.md` is updated in the same commit. |
| **V. Swappable Engines** | ✅ Exemplary | This *is* Principle V: OpenRouter sits behind the existing `LLMEngine` Protocol; the only file importing OpenRouter HTTP is `llm/openrouter_engine.py`; selecting it is a one-line branch. No engine-specific logic leaks across module boundaries. |
| **VI. Resumable Model Downloads** | N/A | Cloud mode downloads no model; the local download path is untouched. |
| **VII. Apple Silicon Primary Target** | ✅ Pass | No platform-specific code; cloud mode is pure HTTP. It additionally serves Macs that cannot fit the local LLM. |
| **VIII. Easy Install for Everyone** | ✅ Pass | No new install step; no new Python dep. `--help` still works model-free. First cloud run guides the user through token capture with a clear prompt (informed-consent spirit). `doctor` reports cloud config status. |
| **IX. Obsidian-Compatible Reports** | ✅ Pass | Cloud feedback renders through the existing report writer; on-disk layout, naming, and `schema_version` (1) are unchanged. No new frontmatter key. |
| **X. Research is Part of the Repo** | ✅ Pass | A "Cloud provider option (008)" section is appended to `doc/research_llm.md` recording the OpenRouter decision, default model, transport choice, and privacy trade-off. |
| **XI. AI-Collaborator Friendly** | ✅ Pass | Changes stay within established module boundaries; per-module `CLAUDE.md` updated; no widening of the context an agent must load to work on a module. |
| **XII. Iterative Delivery** | ✅ Pass | The spec's stories are independent slices: P1 (cloud feedback runs) + P1 (token capture/reuse) form a shippable MVP; model-id (P2) and prompt-file tuning (P3) bolt on without rework. |
| **Constraint: uv / no `pip install`** | ✅ Pass | No new Python dep (stdlib `urllib`). All deps still managed by `uv`. |
| **Constraint: User config = YAML, no `.env`** | ✅ Pass (strengthened by clarification) | The model-id setting is a **YAML file** `~/.speakloop/openrouter.yaml` (`model:` key) — directly honoring the "User configuration: YAML" non-negotiable (clarified Session 2026-06-08; no env var, no `.env`). The token is a plain secret file (mirroring HF's token file), not user-facing config. No TOML/JSON config introduced. The YAML is read in `llm/` (via the existing `pyyaml` dep), keeping the stdlib-only `config` leaf a pure path provider. |
| **Constraint: Model storage location** | ✅ Pass | Unchanged. Cloud artifacts live under `~/.speakloop/` (the established home root), not under `models/`. |
| **Constraint: External services = HF only** | ⚠️ Justified — see Complexity Tracking | Adds OpenRouter as a second external service, reached **only** in opt-in cloud mode. The constraint's intent (no silent/background external calls) is preserved: the default experience contacts no service after model download. |
| **Dev guideline: stdlib over deps, boring over novel** | ✅ Pass | stdlib `urllib.request` + `json`; no new framework. The new engine is a thin HTTP transport behind an interface that already exists. |
| **Dev guideline: engine tests use cached fixtures** | ✅ Pass | Unit tests mock `urllib` (no live call). A real round-trip lives only behind the opt-in `live_cloud` marker, excluded from the default suite. |

**Result**: Pass with three justified deviations (Principle II offline, Principle
III privacy, and the "external services = HF only" constraint) — all the same
root cause: cloud mode is a deliberate, opt-in network feature. Justified in
Complexity Tracking; mitigated by opt-in gating + disclosure + an unchanged
offline default.

## Project Structure

### Documentation (this feature)

```text
specs/008-openrouter-cloud-provider/
├── plan.md              # This file
├── spec.md              # Already created by /speckit-specify
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── openrouter-engine-contract.md      # request/response shape, error mapping
│   ├── credential-and-config-contract.md  # token precedence + storage; model id; prompt file
│   └── cloud-analyzer-bridge-contract.md   # --cloud branch, analyze() override, graceful degradation
├── checklists/
│   └── requirements.md  # Already created
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
src/speakloop/llm/
├── __init__.py                 # UNCHANGED (cloud engine imported function-local, like QwenEngine)
├── interface.py                # UNCHANGED (LLMEngine Protocol already fits OpenRouter)
├── qwen_engine.py              # UNCHANGED (local flow untouched)
├── openrouter_engine.py        # NEW — OpenRouterEngine(LLMEngine) over stdlib urllib;
│                               #       the ONLY file that talks to OpenRouter;
│                               #       OpenRouterAuthError(LLMEngineError) + check_auth()
├── openrouter_credentials.py   # NEW — pure resolve_token() (env > file > None) +
│                               #       store_token() (0600); no interactive I/O, no import-time I/O
├── openrouter_config.py        # NEW — resolve_model() reads ~/.speakloop/openrouter.yaml
│                               #       `model:` via pyyaml, else default qwen/qwen3.7-max
└── CLAUDE.md                   # UPDATED — second engine, new files, traps

src/speakloop/feedback/
├── grammar_analyzer.py         # EDITED (additive) — analyze(..., system_prompt=None);
│                               #       None → local _SYSTEM_PROMPT (byte-identical local behavior)
├── cloud_prompt.py             # NEW — load_cloud_prompt() → seed-from-default-if-missing, read, return (text, path)
├── openrouter_prompt_default.txt  # NEW — packaged default cloud system prompt (its OWN content)
└── CLAUDE.md                   # UPDATED — cloud prompt loader + default asset

src/speakloop/config/
├── paths.py                    # EDITED (additive) — openrouter_token_path(),
│                               #       openrouter_prompt_path(), openrouter_config_path()
│                               #       (PATHS only — YAML is read in llm/, keeping config stdlib-only)
└── CLAUDE.md                   # UPDATED — new accessors

src/speakloop/cli/
├── main.py                     # EDITED (additive) — `--cloud` flag on practice → run(cloud=...)
├── practice.py                 # EDITED — run(cloud=False); _build_cloud_grammar_analyzer(console)
├── doctor.py                   # EDITED (additive, optional) — "Cloud" section: model id, token present?, prompt path
└── CLAUDE.md                   # UPDATED — --cloud flag, cloud analyzer build

tests/unit/llm/
├── test_openrouter_engine.py       # NEW — mock urllib: request shape, content extraction,
│                                   #       401→OpenRouterAuthError, 5xx/timeout→LLMEngineError, retry nudge
├── test_openrouter_credentials.py  # NEW — env>file>None precedence; store writes 0600; no import-time I/O
└── test_openrouter_config.py       # NEW — resolve_model(): YAML `model:` → value; absent/empty → default; malformed → default

tests/unit/feedback/
├── test_cloud_prompt.py        # NEW — seeds default when missing; reads user file when present;
│                               #       returns path; never touches grammar_analyzer._SYSTEM_PROMPT
└── test_grammar_analyzer.py    # EXTENDED — analyze(system_prompt=X) forwards X; default == local prompt;
                                #       existing local cases unchanged

tests/unit/config/
└── test_paths.py               # EXTENDED — token/prompt/config path accessors (pure paths, no I/O)

tests/integration/
├── test_cloud_mode.py          # NEW — injected stub OpenRouterEngine: cloud branch produces a
│                               #       grammar report WITHOUT local Qwen installed; first run prompts+stores
│                               #       token, second run silent; invalid token → actionable error + exit
├── test_local_mode_unchanged.py    # NEW — default run (no token, no network) byte-identical to pre-feature (SC-001)
└── test_help_without_models.py # EXTENDED — importing CLI still loads no engine packages with cloud paths present

doc/
└── research_llm.md             # UPDATED — append "Cloud provider option (008)" decision section

README.md                       # UPDATED — short "Cloud mode (optional)" section
pyproject.toml                  # UNCHANGED — no new dependency
```

**Structure Decision**: single-project layout (matches the existing speakloop
repo). New LLM engine + credentials live in `llm/` (Principle V — the module that
owns LLM engines); the cloud prompt loader + default asset live in `feedback/`
(the grammar-analysis domain, alongside the existing `common_words.txt` packaged
asset); path/setting accessors live in `config/paths.py` (the single source of
truth for paths); the opt-in branch lives in `cli/` (the only module that wires
everything together).

## Complexity Tracking

> Filled because the Constitution Check flagged Principle II (Offline-First),
> Principle III (Privacy by Design), and the "external services = HF only"
> constraint. All three share one root cause.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| **Network calls to OpenRouter** (Principle II; "external services = HF only" constraint) — only in opt-in cloud mode. | The feature's entire purpose is to serve users who cannot run the local LLM in RAM. Producing grammar feedback without the local model **requires** a remote model, which requires a network call. There is no offline way to satisfy the core need. | (a) **Quantize/shrink the local model further** — rejected: 4-bit is already the floor for usable Qwen3-14B quality on the target hardware (per `doc/research_llm.md`); smaller models regress feedback quality and still need RAM the target user lacks. (b) **Ship a tiny always-local model for low-RAM users** — rejected: still occupies RAM, still degrades quality, and doesn't match the user's explicit ask for an OpenRouter path. (c) **Do nothing** — rejected: low-RAM users get no language feedback at all. |
| **Transmitting attempt-transcript text to a third party** (Principle III) — only in opt-in cloud mode. | Grammar/coherence analysis is computed *from the transcript*; a remote analyzer cannot work without receiving the text to analyze. | (a) **Send only redacted/derived features** — rejected: grammar analysis needs the verbatim text (the pipeline verifies findings as exact substrings of the transcript); redaction would break the analysis and the V1 verbatim-substring guarantee. (b) **Local-only** — that is exactly the default mode this feature complements, not replaces. |

Mitigations that keep the deviations inside the constitution's intent:
- **Opt-in gating**: every network call and every byte sent off-device happens
  *only* when the user explicitly runs `--cloud`. The default `speakloop
  practice` is byte-for-byte unchanged, fully offline, and never prompts for a
  token (US3 / FR-002 / SC-001 — asserted by `test_local_mode_unchanged.py`).
- **Informed, per-invocation consent**: cloud mode prints a one-time disclosure
  (at first-run token capture, and a concise reminder on entry) that attempt
  transcripts are sent to OpenRouter — satisfying Principle III's "explicit,
  opt-in consent" requirement for any off-device data path.
- **Minimal exposure**: only ASR transcript text is sent. Audio recordings and
  session reports never leave the device by any code path.
- **No silent/background calls**: nothing phones home; the only outbound traffic
  is the synchronous feedback request the user explicitly initiated.
- **Scoped service**: OpenRouter is reachable from exactly one file
  (`llm/openrouter_engine.py`); no other module gains a network seam.

## Post-Design Constitution Re-Check

Re-evaluated after writing Phase 0 (research.md) and Phase 1 (data-model.md /
contracts/ / quickstart.md):

- **Principle V confirmed exemplary**: the design adds zero new public interface —
  `OpenRouterEngine` satisfies the existing `LLMEngine` Protocol, and the only
  shared-code touch is one additive, defaulted `system_prompt` parameter on
  `analyze(...)` that leaves local behavior byte-identical. The grammar
  verify/rank pipeline is reused, not forked (avoids the divergence the "boring
  over novel" guideline warns against).
- **Principle III mitigation made concrete** in the credential contract: the
  first-run token prompt includes the transcript-disclosure line, and cloud entry
  reprints a one-line reminder.
- **Graceful degradation** is inherited for free: the coordinator already wraps
  the analyzer call in `try/except Exception → phase_c_error`
  (`sessions/coordinator.py`), so transient OpenRouter failures preserve the rest
  of the debrief (FR-014/SC-007). Auth failures are caught *up front* at
  build/preflight time so they surface as a clear actionable error before the
  timed session, not as a buried post-hoc note (FR-006/SC-006).
- **No new Python dependency** confirmed during design (stdlib `urllib` for the
  HTTP call; `pyyaml`, already a dependency, for the model-id YAML).
- **Clarification (Session 2026-06-08) applied**: (1) model id is a YAML file
  (`~/.speakloop/openrouter.yaml` `model:` key), not an env var — strengthening
  the YAML-for-config constraint; the YAML read lives in `llm/openrouter_config.py`
  so the `config` leaf stays stdlib-only. (2) Cloud privacy consent is a one-time
  disclosure + per-run reminder with no blocking prompt (FR-018), matching the
  original Decision 9. No other NEEDS CLARIFICATION remained.

**Result**: Constitution Check passes post-design with the three justified,
opt-in-gated deviations tracked above. Ready for `/speckit-tasks`.
