# Quickstart: Engine-Aware Onboarding (015)

The walkthrough P3 documents and the manual test plan validates. All commands run from the
repo root after `uv sync`.

## 0. It runs before any model is downloaded

```bash
uv run speakloop --help          # works model-free
uv run speakloop setup --help    # new
uv run speakloop questions --help
```

## 1. Pick and persist an engine (once)

### Local feedback (default; needs the large local model)
```bash
uv run speakloop setup --engine local
# → persists engine: local to ~/.speakloop/loop.yaml
# → downloads speech + transcription, then offers the local feedback model (size disclosed)
```

### Cloud feedback (OpenRouter) — never downloads the large local model
```bash
uv run speakloop setup --engine openrouter
# → persists engine: openrouter
# → downloads ONLY speech + transcription
# → reports whether an OpenRouter token is configured + the next step
export OPENROUTER_API_KEY=sk-or-...   # or let `practice` prompt on first run
```

### Claude Code feedback — never downloads the large local model
```bash
uv run speakloop setup --engine claude
# → persists engine: claude
# → downloads ONLY speech + transcription
# → reports whether the Claude Code CLI is installed + logged in
```

### Configure now, download later
```bash
uv run speakloop setup --engine openrouter --no-download
```

## 2. Confirm readiness

```bash
uv run speakloop doctor
# Names the active engine and whether its requirements are satisfied.
# A cloud engine with the local feedback model absent is NOT a failure.
```

## 3. Practice with no flags (the persisted engine is used)

```bash
uv run speakloop practice --listen-only   # hear a question + ideal answer (speech only)
uv run speakloop practice                 # full 4/3/2 session using the persisted engine
uv run speakloop practice --engine local  # override for a single run; persisted default unchanged
```

If the engine is `local` and the feedback model is absent, a full session offers the
download; declining still records the session and leaves a resumable report
(`uv run speakloop resume` finishes it later).

## 4. Use your own questions

```bash
uv run speakloop questions where                       # which file is active + precedence
uv run speakloop questions template > ~/.speakloop/qa.yaml   # start from a valid template
# edit ~/.speakloop/qa.yaml, then:
uv run speakloop questions validate                    # validate the active (resolved) file
uv run speakloop questions validate ./my-set.yaml      # validate a specific file
uv run speakloop practice --qa-file ./my-set.yaml      # one-off use of a specific file
```

A broken file is rejected with the exact entry id and field at fault; a valid file reports
the question count. Nothing is written into your home directory unless you redirect it there.

## Acceptance smoke (maps to spec Success Criteria)

- SC-002: `setup --engine openrouter` then `doctor` → the local feedback model is never
  downloaded; speech + transcription are present.
- SC-003: after `setup --engine openrouter`, `practice` with no flag uses openrouter;
  `practice --engine local` overrides only that run.
- SC-004: `doctor` names the active engine and does not false-fail on an unneeded model.
- SC-005/006: `questions validate` on a broken vs. valid file; `questions template` output
  validates unedited.
- SC-007: no home file created by `template`/`validate`/`where`, or by `setup --no-download`
  beyond `loop.yaml`.
- SC-008: every command above runs with no models present and loads no engine package.
