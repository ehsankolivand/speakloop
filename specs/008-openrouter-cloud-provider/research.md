# Research: OpenRouter Cloud-Model Provider

Phase 0 decision record. Each decision resolves a project-fit choice the spec
explicitly delegated (CLI shape, token location/precedence, model-id mechanism,
prompt-file location, transport) or a constitution tension. Format: Decision /
Rationale / Alternatives considered.

---

## Decision 1 — Integration seam: a second `LLMEngine` behind the existing Protocol

**Decision**: Implement `OpenRouterEngine` satisfying the existing
`speakloop.llm.LLMEngine` Protocol
(`generate(system_prompt, user_prompt, max_tokens, temperature, retry) -> str`).
Reuse the entire engine-agnostic grammar pipeline in
`feedback/grammar_analyzer.py` (user-prompt formatting, JSON extraction +
`json-repair` recovery, verbatim-substring verify V1, coherence filter V2,
no-op-fix drop V3, dedup/rank, one bounded regenerate). Cloud mode differs from
local mode in exactly two inputs: **which engine** the analyzer calls, and
**which system prompt** it passes.

**Rationale**: This is Constitution Principle V working as designed — the LLM is
already behind a stable interface specifically so it can be swapped in one file.
The verify/rank pipeline is engine-independent infrastructure (it operates on the
returned JSON and the transcripts), so forking it for cloud would be pure
duplication and a divergence risk the "boring over novel / DRY" guideline warns
against. Reuse maximizes correctness parity (cloud findings are verified exactly
like local findings) and minimizes the change surface.

**Alternatives considered**:
- *Fork a parallel `cloud_grammar_analyzer.py`* — rejected: duplicates the V1–V3
  verification + ranking logic; two code paths drift over time.
- *A generic provider-abstraction layer* — rejected: explicitly out of scope
  (FR-013); only OpenRouter is supported now. The `LLMEngine` Protocol already
  *is* the only abstraction we need.

---

## Decision 2 — Cloud system prompt injection: one additive `analyze(system_prompt=None)` parameter

**Decision**: Add an optional `system_prompt: str | None = None` parameter to
`grammar_analyzer.analyze(...)` (threaded into `_generate_and_parse`). When
`None` (every existing/local caller), it resolves to the module-local
`_SYSTEM_PROMPT` exactly as today. Cloud mode passes its own prompt text loaded
from the dedicated cloud prompt file.

**Rationale**: Cloud must use its **own** prompt and must **not reference** the
local prompt (FR-010, FR-012). Passing the cloud prompt explicitly through
`analyze(...)` is the minimal, honest seam: the local `_SYSTEM_PROMPT` constant is
never read or passed in cloud mode, and the local path is byte-for-byte unchanged
because the default parameter value preserves it. This keeps the `LLMEngine.generate`
contract honest (the engine uses the system prompt it is given) rather than having
the engine silently ignore its `system_prompt` argument.

**Alternatives considered**:
- *Engine ignores the passed `system_prompt` and loads its own file* — rejected:
  violates the `generate(...)` contract semantics (a reader expects the passed
  prompt to be used) and means the analyzer would still *construct and pass* the
  local `_SYSTEM_PROMPT` to the cloud engine — a soft breach of FR-012 ("cloud
  must not reference the local prompt").
- *Module-level global to swap the prompt* — rejected: hidden state, not
  thread/test-friendly, harder to reason about than an explicit parameter.

---

## Decision 3 — CLI shape: a `--cloud` boolean flag on `practice`

**Decision**: Opt into cloud mode with `speakloop practice --cloud`. Implemented
as a `typer` boolean option on the existing `practice` command, plumbed to
`practice.run(cloud=...)`.

**Rationale**: Matches the project's established per-command boolean-flag
convention (`--listen-only`, `--no-audio`, plus the valued `--asr-engine`). The
LLM feedback step only runs inside `practice` (neither `doctor` nor `trends`
invoke it), so a per-command flag is the precise surface — no need for a global
option or a parallel command. Keeps the default invocation (`speakloop practice`)
untouched.

**Alternatives considered**:
- *A parallel command (e.g., `practice-cloud`)* — rejected: duplicates the
  command's option surface and help text; drifts from `practice` over time.
- *A global root option* — rejected: the root callback options are cross-cutting
  (`--qa-file`, `--models-dir`); cloud mode is specific to the feedback step of
  one command.
- *An `--llm-engine {local,openrouter}` valued option mirroring `--asr-engine`* —
  reasonable and symmetric, but a plain `--cloud` boolean reads more clearly for a
  binary local/cloud choice and is the lighter surface. Recorded as the runner-up;
  `/speckit-clarify` can flip to the valued form if a third LLM provider is ever
  anticipated (it is explicitly not, per FR-013).

---

## Decision 4 — Token storage & precedence: env `OPENROUTER_API_KEY` > `~/.speakloop/openrouter_token`

**Decision**: Resolve the credential as: (1) `OPENROUTER_API_KEY` environment
variable if set and non-empty, else (2) the contents of
`~/.speakloop/openrouter_token` (a plain UTF-8 file, written mode `0600`), else
(3) none → trigger the first-run interactive prompt. The first-run prompt writes
the entered token to the file.

**Rationale**:
- **Location** (`~/.speakloop/`): the project's established per-user home root
  (`_speakloop_home()` already anchors `models/`, `qa.yaml`, `cache/tts/`).
  A plain token file mirrors the HuggingFace-CLI convention 007 already relies on
  (`~/.cache/huggingface/token`), so it is a known, "boring" pattern — not a new
  secrets scheme (FR-015).
- **Precedence** (env > file): identical to 007's token resolver
  (`installer/tokens.py`: `$HF_TOKEN` > file > anon), so the project has one
  consistent env-over-file rule.
- **Env var name** (`OPENROUTER_API_KEY`): the de-facto standard name OpenRouter's
  own docs/SDKs use, so users with it already exported get zero-prompt setup.
- **Permissions** (`0600`): minimal hardening for a stored secret; cheap and
  expected.

**Alternatives considered**:
- *Store the token inside a YAML config file* — rejected: mixes a secret into
  user-facing config; HF (and 007) keep the token in its own plain file, which is
  the precedent. Keeps the secret out of anything a user might paste/share.
- *OS keychain integration* — rejected: explicitly out of scope (FR-015, "no new
  secrets manager"); adds platform-specific complexity against the "boring"
  guideline.

---

## Decision 5 — Model-id setting: a `model:` key in `~/.speakloop/openrouter.yaml`, default `qwen/qwen3.7-max`

> **Resolved by clarification (Session 2026-06-08).** The user chose a dedicated
> YAML config file over an env var. This supersedes the earlier env-var draft;
> the env var is now the rejected alternative below.

**Decision**: The OpenRouter model id is the `model:` key in a dedicated YAML
config file at `~/.speakloop/openrouter.yaml`. Absent file or absent key → default
`qwen/qwen3.7-max`. There is **no** env-var override for the model id — the YAML
file is the single designated place. `config/paths.py` exposes only the **path**
(`openrouter_config_path()`), keeping the config leaf stdlib-only (its `CLAUDE.md`
forbids non-`mkdir` I/O); the YAML is *read* in the `llm` module
(`llm/openrouter_config.py:resolve_model()`) using `pyyaml` (already a project
dependency — no new dep), mirroring how `content/` already loads `questions.yaml`.

**Rationale**: The constitution's non-negotiable "User configuration: YAML" makes a
YAML file the most faithful home for a persistent user setting, and unlike an env
var it survives across shells without editing a shell profile. It also gives cloud
settings a natural place to grow (e.g., a future `base_url:` or timeout) without
adding more env vars. `pyyaml` is already a dependency, so this adds no install
footprint. Keeping the read in `llm/` (not `config/paths.py`) preserves the config
module's documented "stdlib-only, no I/O beyond mkdir" leaf property.

**Alternatives considered**:
- *Env var `SPEAKLOOP_OPENROUTER_MODEL`* — the original draft and most
  precedent-faithful to the `SPEAKLOOP_*` overrides in `config/paths.py`; lightest
  to implement. **Rejected by clarification**: an env var does not persist across
  shells and is a weaker fit for the constitution's YAML-for-user-config mandate
  than a real config file.
- *Both (YAML home + env override)* — more flexible but two places to document and
  reason about for a single value; rejected as over-built for one setting.
- *Hard-code with a code edit to change* — rejected: violates FR-007/FR-009.

---

## Decision 6 — Cloud system-prompt file: `~/.speakloop/openrouter_prompt.txt`, seeded from a packaged default

**Decision**: The cloud system prompt lives at `~/.speakloop/openrouter_prompt.txt`.
On the first cloud run (file absent), `feedback/cloud_prompt.py` seeds it by
copying a packaged default asset
(`src/speakloop/feedback/openrouter_prompt_default.txt`) to that path, prints the
path so the user knows where to edit, then reads and returns it. On later runs the
user's (possibly edited) file is read verbatim.

**Rationale**:
- A real on-disk file the user edits directly satisfies FR-010/FR-011/SC-005
  ("edit the file → behavior changes next run, no code change").
- Seeding from a **packaged default** gives the user a working starting point and,
  critically, keeps the cloud prompt's content **independent of** the local
  `_SYSTEM_PROMPT` (FR-012 — the default asset is its own file, never imported from
  the analyzer). The default mirrors the local prompt's *intent* (same strict
  `{"errors":[...]}` JSON schema the verify/rank pipeline consumes) but is a
  separate, separately-editable artifact.
- Location under `~/.speakloop/` and the read-via-`Path(__file__).parent` packaged
  asset both mirror existing conventions (`feedback/common_words.txt` is read that
  way today).

**Alternatives considered**:
- *Read the packaged default directly with no user-file seeding* — rejected: the
  user couldn't "edit the file" without first knowing to create it; seeding makes
  the editable surface discoverable.
- *Derive the cloud default by copying `_SYSTEM_PROMPT`* — rejected: that would
  make cloud *reference* the local prompt (FR-012 breach). The default must be its
  own asset.

---

## Decision 7 — Transport: stdlib `urllib.request` to OpenRouter's OpenAI-compatible endpoint

**Decision**: POST to `https://openrouter.ai/api/v1/chat/completions` using stdlib
`urllib.request` + `json`, with header `Authorization: Bearer <token>` and body
`{"model": <id>, "messages": [{"role":"system",...},{"role":"user",...}],
"temperature": <t>, "max_tokens": <n>}`. Parse `choices[0].message.content`.
No new dependency. A bounded connect/read timeout is applied.

**Rationale**: OpenRouter exposes an OpenAI-compatible chat-completions API, so a
plain JSON POST suffices. stdlib `urllib` honors "standard library over
dependencies" and adds nothing to `pyproject.toml` (so `uv` lockfile, install
footprint, and Principle VIII are untouched). `requests` is only a *transitive*
dep via `huggingface_hub`; relying on it directly would be an implicit, unpinned
dependency — worse than stdlib.

**Alternatives considered**:
- *`requests`/`httpx`* — rejected: a new (or implicit) dependency for a single
  JSON POST; stdlib is sufficient and dependency-honest.
- *The official `openai` SDK pointed at OpenRouter* — rejected: a heavy new dep,
  and we only need one endpoint.

---

## Decision 8 — Auth handling: fail-fast preflight up front, graceful degradation at runtime

**Decision**: Two distinct failure regimes:
1. **Missing/invalid token** is resolved **before** the timed session, at
   cloud-analyzer build time. Missing → prompt once, store. After capture (and for
   an already-stored token), a cheap **preflight auth check** (`GET
   https://openrouter.ai/api/v1/key` with the bearer token) validates it. A `401`
   prints a clear, actionable error naming both remediation paths (update the
   token / run without `--cloud`), re-prompts once, and on continued failure exits
   non-zero (FR-006/SC-006). This guarantees the token is known-good before the
   user invests time in attempts (FR-005: never re-prompts a good token).
2. **Transient runtime failures** (network drop, timeout, `5xx`, unparseable
   response) during the actual feedback call propagate as `LLMEngineError` and are
   caught by the coordinator's existing `try/except Exception → phase_c_error`
   wrapper, so the rest of the debrief is preserved (FR-014/SC-007) — identical to
   how local-mode feedback failures already degrade.

**Rationale**: Auth problems are best surfaced *before* the 4/3/2 attempts so the
user isn't told "bad token" only after speaking three answers; the preflight is one
cheap request and cloud mode is already online. Transient problems are unpredictable
and should never crash a session, which the existing graceful path already handles
for free — no new error-handling machinery needed for the runtime case.

**Alternatives considered**:
- *No preflight; discover bad auth only at analyzer time* — rejected: a rejected
  token would surface as a buried `phase_c_error` note after the whole session,
  failing SC-006's "clear, actionable error" intent and wasting the user's time.
- *Preflight everything including connectivity, blocking on each run* — partially
  adopted: the preflight already exercises connectivity + auth in one request; no
  extra check needed.

---

## Decision 9 — Privacy disclosure & consent (Principle III)

**Decision**: Because cloud mode sends attempt-transcript text off-device, the
first-run token capture includes an explicit English disclosure line ("Cloud mode
sends your attempt transcripts to OpenRouter for analysis; audio and reports stay
on your device."), and entering cloud mode reprints a one-line reminder. The
`--cloud` flag itself is the per-invocation opt-in.

**Rationale**: Principle III requires explicit, opt-in consent for any path that
sends user data to a third party. The flag + disclosure make the consent informed
and per-invocation. Audio and reports are never transmitted; only the transcript
text the analysis needs.

**Alternatives considered**:
- *Silent network use under the flag* — rejected: the flag opts into *cloud
  compute*, but Principle III specifically wants the user to know their transcript
  text leaves the device. Cheap one-line disclosure closes the gap.
- *A blocking yes/no consent prompt every run* — rejected: heavier than needed;
  the explicit `--cloud` flag plus a disclosure is sufficient informed consent and
  avoids per-run friction (FR-005's "never ask again" spirit). A one-time
  disclosure at token capture + a concise reminder line balances both.

---

## Resolved spec deferrals

| Spec deferral (Assumptions) | Resolved by |
|---|---|
| Opt-in shape (flag/subcommand/parallel) | Decision 3 — `--cloud` on `practice` |
| Token storage location & format | Decision 4 — `~/.speakloop/openrouter_token`, 0600 plain |
| Token precedence (env vs file) | Decision 4 — `OPENROUTER_API_KEY` > file |
| Model-id mechanism | Decision 5 (clarified) — `model:` key in `~/.speakloop/openrouter.yaml`, default `qwen/qwen3.7-max` |
| Prompt-file mechanism | Decision 6 — `~/.speakloop/openrouter_prompt.txt`, seeded from packaged default |
| Transport / new dependency? | Decision 7 — stdlib `urllib`, no new dep |
| Constitution offline/privacy tension | Decisions 8–9 + plan Complexity Tracking |

No `NEEDS CLARIFICATION` markers remain.
