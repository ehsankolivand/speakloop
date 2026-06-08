# Contract: Credentials & Cloud Configuration

Covers the three user-facing cloud config surfaces — token, model id, prompt file
— and their resolution rules. Implemented across `config/paths.py` (pure
accessors), `llm/openrouter_credentials.py` (token resolve/store), and
`feedback/cloud_prompt.py` (prompt load/seed).

## A. Token (the secret)

**Accessors** (`config/paths.py`):
- `openrouter_token_path() -> Path` → `_speakloop_home() / "openrouter_token"`
  (i.e. `~/.speakloop/openrouter_token`, honoring `SPEAKLOOP_HOME`).

**Resolution** (`llm/openrouter_credentials.py:resolve_token() -> str | None`):
1. `OPENROUTER_API_KEY` env if set and non-empty (stripped) → return it.
2. else if `openrouter_token_path()` exists and is non-empty → return its stripped
   contents.
3. else → `None` (caller triggers the first-run prompt).

**Storage** (`store_token(value) -> Path`):
- Strip surrounding whitespace; raise/refuse on empty.
- Write `openrouter_token_path()` with mode `0600` (create parent dir if needed).
- Return the path. Never log the value.

**Invariants (tests)**:
- [ ] env beats file beats None (precedence).
- [ ] empty env var is treated as unset (falls through to file).
- [ ] `store_token` writes `0600` and round-trips through `resolve_token`.
- [ ] no I/O at import time (pure module import).
- [ ] token value never logged or returned in any error string.

## B. Model id (clarified — YAML file, no env var)

**Path accessor** (`config/paths.py:openrouter_config_path() -> Path`):
- → `_speakloop_home() / "openrouter.yaml"` (`~/.speakloop/openrouter.yaml`).
  Pure path only — the config leaf does NOT read the file (its `CLAUDE.md` forbids
  I/O beyond `mkdir`).

**Resolver** (`llm/openrouter_config.py:resolve_model() -> str`):
- If `openrouter_config_path()` exists, parse it (`pyyaml`, already a dep) and
  return a non-empty `model:` value (stripped).
- else / missing-or-empty `model:` → `"qwen/qwen3.7-max"` (the pinned default).
- There is **no** env-var override for the model id — the YAML file is the one
  designated place (FR-007).

**Invariants (tests)**:
- [ ] absent file → `"qwen/qwen3.7-max"`.
- [ ] file with `model: X` → `X` (stripped).
- [ ] file present but `model:` missing/empty → default.
- [ ] editing the YAML and re-resolving yields the new model with no code change
      (SC-004).
- [ ] malformed YAML degrades to the default (or a clear error) — never crashes
      the resolver silently.

## C. Cloud system-prompt file

**Accessor** (`config/paths.py:openrouter_prompt_path() -> Path`):
- → `_speakloop_home() / "openrouter_prompt.txt"` (`~/.speakloop/openrouter_prompt.txt`).

**Packaged default**: `src/speakloop/feedback/openrouter_prompt_default.txt`
- Its own content (NOT derived from `grammar_analyzer._SYSTEM_PROMPT`).
- Instructs the same strict `{"errors":[{"attempt_ordinal","quote","corrected",
  "error_type","explanation"}]}` JSON schema the verify/rank pipeline consumes, so
  cloud findings verify exactly like local ones.

**Loader** (`feedback/cloud_prompt.py:load_cloud_prompt() -> tuple[str, Path]`):
1. If `openrouter_prompt_path()` does not exist → copy the packaged default to it
   (create parent dir), and the caller prints the path so the user can find/edit it.
2. Read the user file verbatim (UTF-8).
3. Return `(text, path)`.

**Invariants (tests)**:
- [ ] missing user file → seeded from the packaged default, then read.
- [ ] present (edited) user file → read verbatim, NOT re-seeded/overwritten.
- [ ] the loader never reads or imports `grammar_analyzer._SYSTEM_PROMPT`
      (FR-012) — verify by import-graph / no reference.
- [ ] editing the user file changes the returned text on the next call (SC-005).

## D. Precedence summary (mirrors existing project patterns)

| Surface | Order |
|---|---|
| Token | `OPENROUTER_API_KEY` env → `~/.speakloop/openrouter_token` → first-run prompt |
| Model id | `~/.speakloop/openrouter.yaml` `model:` key → default `qwen/qwen3.7-max` (no env override) |
| Prompt | `~/.speakloop/openrouter_prompt.txt` (seeded from packaged default if absent) |

The token's env-over-file precedence mirrors `installer/tokens.py` (007). The
model id is a YAML file (clarified Session 2026-06-08) per the constitution's
"User configuration: YAML" mandate — read via `pyyaml` in `llm/`, not in the
stdlib-only `config` leaf.
