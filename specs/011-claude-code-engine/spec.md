# Feature Specification: Claude Code Analysis Engine

**Feature Branch**: `011-claude-code-engine`

**Created**: 2026-06-10

**Status**: Draft

**Input**: User description: "Add a third analysis engine to SpeakLoop: 'claude' — routing every LLM analysis call through the learner's locally installed and logged-in Claude Code, billed to their existing Claude subscription instead of pay-per-token APIs."

## Overview

SpeakLoop today routes the Phase-C / Interview-Loop LLM analysis calls through one of two
engines behind a single injected interface: the local **Qwen** engine (default, fully offline)
and the **OpenRouter** cloud engine (opt-in via `--cloud`). OpenRouter calls cost real dollars
per token. Many learners already pay a flat monthly Claude subscription, which includes the
locally installed **Claude Code** product. Driving the analysis through the learner's own logged-in
Claude Code lets a full daily session run at **zero marginal token cost**, drawing on the
subscription instead of a metered API key.

This feature adds a third engine — `claude` — selectable by one flag or one config line,
changing **no** report semantics, prompts, or JSON schemas. It is an EXTENSION behind the
existing interface, not a rewrite.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Subscription-billed analysis via Claude Code (Priority: P1)

A learner who already pays for a Claude subscription wants every LLM analysis step of a daily
SpeakLoop session — follow-up generation, key-point derivation, coverage + content errors,
mishearing classification, artifact consistency, drill generation, grammar, and coaching — to run
through their locally installed, logged-in Claude Code, so the session costs them nothing beyond
their existing subscription. They select the engine once (a flag, or a one-line config default)
and otherwise see the exact same report they would get from the local or OpenRouter engine.

**Why this priority**: This is the core value of the feature — eliminating per-token cost for
learners who own a subscription. Without it, nothing else matters.

**Independent Test**: Run a full daily session (or resume a pending one) with `--engine claude`
on a machine with Claude Code installed and logged in; confirm the report is complete and
structurally identical to a Qwen/OpenRouter report, and that no pay-per-token API call was made.

**Acceptance Scenarios**:

1. **Given** Claude Code is installed and logged in, **When** the learner runs `practice --engine claude`,
   **Then** every analysis call routes through Claude Code and the session produces a complete report
   with the same sections and `schema_version` as the other engines.
2. **Given** a session was saved earlier with `analysis_pending`, **When** the learner runs
   `resume --engine claude`, **Then** the pending analysis is completed through Claude Code and the
   report is rewritten with `analysis_pending` cleared.
3. **Given** the learner sets `engine: claude` in the loop config, **When** they run `practice`
   with no engine flag, **Then** the Claude Code engine is used by default.
4. **Given** the learner runs `practice --cloud`, **When** the command starts, **Then** it behaves
   exactly as `practice --engine openrouter` (backward-compatible alias).
5. **Given** Claude Code is **not** installed (or the learner is logged out, offline, or out of
   credit), **When** they run `practice --engine claude`, **Then** recordings and transcripts are
   saved, a deterministic report is written, `analysis_pending` is set, and the session is resumable
   later — identical to today's degradation behavior.
6. **Given** an `ANTHROPIC_API_KEY` is present in the environment, **When** a claude-engine analysis
   call runs, **Then** the call still bills to the subscription (never pay-per-token) because the
   engine prevents that key from reaching Claude Code.

---

### User Story 2 - Per-call model tiering to conserve subscription credit (Priority: P2)

To stretch the subscription's monthly Agent-SDK credit, the learner wants cheap, mechanical calls
(mishearing classification, drill generation) to use a fast/cheaper model while reasoning-heavy
calls (coverage, content errors, artifact consistency, follow-ups, grammar, coaching, key points)
use a stronger model. The mapping ships with sensible defaults and can be overridden in the loop
config.

**Why this priority**: Valuable optimization, but the feature delivers its core value (P1) even if
every call uses a single model. Tiering refines cost/quality once the engine works.

**Independent Test**: With the claude engine selected, run a session and confirm that mishearing and
drill calls invoke the configured fast model while coverage/consistency/follow-up calls invoke the
configured strong model; then override the mapping in the loop config and confirm the new models are
used.

**Acceptance Scenarios**:

1. **Given** the default tier mapping, **When** a mishearing-classification or drill call runs,
   **Then** it uses the configured **fast** model.
2. **Given** the default tier mapping, **When** a coverage, consistency, follow-up, grammar,
   coach, or key-point call runs, **Then** it uses the configured **strong** model.
3. **Given** the learner overrides the tier→model mapping in the loop config, **When** any call
   runs, **Then** the overridden model is used for that tier.

---

### Edge Cases

- **Logged out mid-session**: calls completed before logout keep their analysis; remaining calls
  degrade per-step (best-effort steps return empty, required steps set `analysis_pending`). Partial
  analysis is preserved.
- **Credit or rate window exhausted mid-session**: same per-step degradation as logged-out; the
  cause is surfaced in the report's error field and pinpointed by `doctor`.
- **Non-JSON / truncated / error-enveloped CLI output**: treated as an engine failure that flows
  into the standard degradation path; never silently misparsed.
- **Call exceeds a hard timeout**: the call is aborted and treated as an engine failure (degradation
  path), not left hanging.
- **`ANTHROPIC_API_KEY` present in the environment**: the engine strips it (and related override
  variables) from the subprocess so billing stays on the subscription; it never silently switches to
  pay-per-token.
- **Claude Code auto-updated and a flag/output-shape changed**: the engine fails loudly with a clear
  message into the degradation path rather than misparsing — the expected CLI contract is pinned so
  an incompatible change is detected, not absorbed.
- **No engine available at all** (claude absent AND no local model AND no OpenRouter token): the
  session still completes recordings + deterministic report with `analysis_pending`.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST offer an engine selector `--engine {local|openrouter|claude}` on both
  `practice` and `resume`, where `local` is the offline Qwen engine (default), `openrouter` is the
  cloud engine, and `claude` is the new Claude Code engine.
- **FR-002**: System MUST preserve the existing `--cloud` flag as an exact alias for
  `--engine openrouter`; existing `--cloud` invocations behave identically to today.
- **FR-003**: System MUST let the learner set a default engine once in the loop config so no flag is
  needed each session. An explicit `--engine`/`--cloud` flag MUST override the config default; the
  config default MUST override the built-in default (`local`).
- **FR-004**: When the claude engine is selected, System MUST route EVERY analysis call in the
  current pipeline through Claude Code: follow-up generation, key-point derivation, coverage +
  content errors, mishearing classification, artifact consistency, drill generation, grammar, and
  coaching.
- **FR-005**: The claude engine MUST NOT change any analysis prompt, JSON schema, report section,
  report semantics, or report `schema_version`. JSON contracts, editable prompt files, retry
  behavior, and fallbacks MUST be identical to the OpenRouter engine.
- **FR-006**: When the claude engine is unavailable for any reason (not installed, not logged in,
  credit/rate exhausted, offline, or timeout), System MUST save recordings and transcripts, write the
  deterministic report, set `analysis_pending`, and keep the session resumable — identical to today's
  degradation behavior.
- **FR-007**: System MUST ensure claude-engine calls bill to the learner's subscription and never to
  a pay-per-token API key. Specifically, an `ANTHROPIC_API_KEY` (or related billing/endpoint override
  variable) present in the environment MUST NOT cause Claude Code to bill pay-per-token for these
  calls.
- **FR-008**: `speakloop doctor` MUST gain rows reporting: (a) whether the Claude Code binary is
  present, (b) its version, (c) the authentication state, and (d) the configured default engine.
- **FR-009**: When the Claude Code CLI returns output that is not the expected success envelope
  (non-JSON, truncated, error-enveloped, or an unrecognized shape after an auto-update), System MUST
  fail loudly into the standard degradation path with a clear message rather than silently
  misparsing.
- **FR-010**: The existing engine contract test suite MUST pass unchanged against the new engine.
- **FR-011**: System MUST drive the genuine Claude Code product. It MUST NOT extract or reuse
  subscription OAuth tokens, make direct HTTP calls to model endpoints with subscription credentials,
  or route through an OpenAI-compatible proxy.
- **FR-012**: The default (no-flag) engine MUST remain the local Qwen engine, and the default path
  MUST stay fully offline and byte-identical to today.
- **FR-013** *(P2)*: System MUST map each analysis call site to a model tier (`fast` | `strong`) and,
  for the claude engine, use the fast model for cheap calls (mishearing classification, drill
  generation) and the strong model for reasoning-heavy calls (coverage, content errors, artifact
  consistency, follow-ups, grammar, coaching, key points).
- **FR-014** *(P2)*: The tier→model mapping MUST ship with sensible defaults and be overridable in
  the loop config.

### Key Entities *(include if feature involves data)*

- **Analysis Engine**: the injected text-generation interface every analysis step depends on. Three
  implementations now exist: local Qwen, OpenRouter, and Claude Code. Selecting one changes only
  which implementation is injected — never the prompts, schemas, or report.
- **Engine Selection**: the resolved choice of engine for a run, derived from (in precedence order)
  the explicit flag → the loop-config default → the built-in default (`local`).
- **Model Tier Mapping**: a small mapping from each analysis call site to a tier (`fast`/`strong`),
  and from each tier to a concrete Claude model alias. Ships with defaults; overridable in config.
- **Doctor Health Rows**: human-readable status rows for Claude Code binary presence, version,
  authentication state, and the configured default engine.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A full daily session (warm-up + 4/3/2 attempts + follow-ups + complete analysis) run
  with the claude engine finishes with **zero** marginal pay-per-token cost — it uses only the
  subscription.
- **SC-002**: Switching engines requires exactly **one** flag or **one** config line, and the
  resulting report has the same sections and `schema_version` as the other engines (no report
  semantics change).
- **SC-003**: With Claude Code absent or logged out, the session still completes: a report is written
  with `analysis_pending` set, and `speakloop doctor` pinpoints the specific cause (e.g.,
  not-installed vs not-authenticated).
- **SC-004**: The existing engine contract test suite passes unchanged against the new engine.
- **SC-005**: When an `ANTHROPIC_API_KEY` is present in the environment, claude-engine calls still
  bill to the subscription — no pay-per-token billing occurs.
- **SC-006**: The default (no-flag) path remains the offline local Qwen engine and is byte-identical
  to today's behavior; no automated test ever invokes the real Claude Code binary.

## Assumptions

These reasonable defaults were chosen where the description left a detail open; the more important
ones are recorded so reviewers can challenge them.

- **Subprocess, stdlib only.** The claude engine drives the installed Claude Code CLI in
  non-interactive print mode via `subprocess`, using only the Python standard library — no Agent SDK
  dependency (zero new dependencies, consistent with the OpenRouter engine's stdlib-`urllib`
  approach). The Python `claude-agent-sdk` is the considered-and-rejected alternative (extra
  dependency, same underlying CLI, same credit coverage).
- **Project isolation without breaking subscription auth.** Empirical testing of the installed CLI
  (Claude Code **2.1.170**) shows `--bare` forces Anthropic auth to be **strictly** `ANTHROPIC_API_KEY`
  or `apiKeyHelper` (OAuth and keychain are never read) — which is incompatible with the
  billing-safety requirement to strip `ANTHROPIC_API_KEY`. Therefore the engine uses `--safe-mode`
  (disables CLAUDE.md/skills/plugins/hooks/MCP/custom agents while keeping subscription auth, model
  selection, and built-in tools working normally) instead of `--bare`. This is a deliberate deviation
  from the original plan note and is recorded in research.md.
- **Pure analysis behavior.** Tool use is disabled (no tools granted) so each call returns a single
  text-only response with no tool invocation; the analysis system prompt replaces the default system
  prompt so the call behaves as a deterministic JSON-producing function. Structured output relies on
  the existing JSON-recovery ladder (the CLI may wrap output in markdown code fences, which the ladder
  already strips) — no analysis prompt or schema is changed.
- **Billing-safety stripping.** The engine removes `ANTHROPIC_API_KEY` and related override variables
  (auth token, base-URL/API-URL overrides, Bedrock/Vertex toggles) from the subprocess environment so
  calls always bill to the subscription.
- **Timeout & retry.** A hard per-call timeout (default ~90 s) bounds each call; `retry=True` maps to
  one bounded re-invocation, mirroring the OpenRouter engine.
- **Tier defaults.** Default `fast` model = a Haiku-class alias; default `strong` model = a
  Sonnet-class alias (strong but credit-conserving — Opus is intentionally not the default). Both are
  overridable in the loop config.
- **Config surface.** The default engine and the tier→model mapping are additive, optional keys in
  the existing loop config (`~/.speakloop/loop.yaml`); absence preserves today's behavior. Report
  `schema_version` stays 1.
- **CLI contract pinned.** The observed CLI flags, JSON-envelope fields, and exit/error behavior are
  pinned as named constants citing the observed `claude --version`, so a future incompatible CLI
  change fails loudly in exactly one place (FR-009).
