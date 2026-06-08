# Contract: Cloud Analyzer Bridge (CLI entry-point branch)

Covers the minimal entry-point changes that wire cloud mode into the existing
practice/debrief loop without modifying the local Qwen flow.

## A. CLI surface (`cli/main.py`)

Add one option to the existing `practice` command:

```python
cloud: bool = typer.Option(
    False, "--cloud",
    help="Use the OpenRouter cloud model for feedback instead of the local Qwen model.",
)
```

- Plumb to `practice.run(..., cloud=cloud)`.
- No other command (`doctor`, `trends`) gains the flag; only `practice` runs the
  LLM feedback step.
- `speakloop practice` (no flag) is byte-for-byte unchanged.

**Invariants (tests)**:
- [ ] `--help` lists `--cloud`; importing the CLI loads no engine packages
      (existing guard still green).
- [ ] default invocation passes `cloud=False`.

## B. Engine selection (`cli/practice.py`)

`run(...)` gains `cloud: bool = False`. The build step branches:

```python
grammar_analyzer = (
    _build_cloud_grammar_analyzer(console)
    if cloud
    else _build_grammar_analyzer()        # UNCHANGED local path
)
```

`_build_cloud_grammar_analyzer(console)` (function-local imports — keeps `--help`
model-free):
1. `token = openrouter_credentials.resolve_token()`.
2. If `token is None`: print the privacy disclosure (Decision 9) + prompt once;
   on empty/declined → actionable error (how to set the token / run without
   `--cloud`) → `raise typer.Exit(1)`; else `store_token(entered)`.
3. **Preflight**: `OpenRouterEngine(...).check_auth()`.
   - `OpenRouterAuthError` → actionable error naming both remediation paths
     (update token / use local mode), re-prompt once, re-store, re-check; still
     bad → `raise typer.Exit(1)` (FR-006/SC-006).
   - other `LLMEngineError` (no connectivity) → actionable error → `Exit(1)`.
4. `cloud_prompt, prompt_path = cloud_prompt.load_cloud_prompt()`; print
   `prompt_path` once so the user knows where to edit (FR-010).
5. Build `engine = OpenRouterEngine(model=openrouter_config.resolve_model(), token=token)`
   (model id read from `~/.speakloop/openrouter.yaml`, default `qwen/qwen3.7-max`).
6. Print a one-line cloud-mode reminder (model id + transcript disclosure).
7. Return runner: `lambda transcripts: analyze(transcripts, engine,
   system_prompt=cloud_prompt)`.

Crucially, the cloud build path does **not** call
`validator.validate(QWEN3_14B_4BIT)` and never instantiates `QwenEngine` — so
cloud mode works with the local LLM absent (US1 / SC-002).

**Invariants (tests)**:
- [ ] cloud branch never touches `QwenEngine` / `QWEN3_14B_4BIT` validation.
- [ ] first cloud run with no token → exactly one prompt, then stored; second run
      → zero prompts (SC-003).
- [ ] preflight `OpenRouterAuthError` → actionable message naming both remediation
      paths + non-zero exit (SC-006).
- [ ] runner passes the **cloud** prompt (not `_SYSTEM_PROMPT`) to `analyze`.

## C. Analyzer override (`feedback/grammar_analyzer.py`) — additive

`analyze(transcripts, llm, *, max_tokens=2048, system_prompt=None)`:
- `system_prompt is None` → use the module-local `_SYSTEM_PROMPT` (local behavior
  byte-identical; every existing caller is unaffected).
- otherwise → pass `system_prompt` to `_generate_and_parse` → `llm.generate(...)`.
- All verify (V1–V3), dedup, ranking, and the one bounded regenerate are unchanged
  and shared by both modes.

**Invariants (tests)**:
- [ ] `analyze(..., system_prompt=X)` causes `llm.generate` to receive `X` as its
      system prompt; default path receives `_SYSTEM_PROMPT`.
- [ ] existing local analyzer tests pass unchanged.

## D. Graceful degradation (no new code — relies on the existing seam)

The coordinator already wraps the analyzer call:

```python
try:
    grammar_patterns = grammar_analyzer(transcripts)
except Exception as e:                       # sessions/coordinator.py
    phase_c_error = f"{type(e).__name__}: {e}"
```

So a transient `LLMEngineError` from `OpenRouterEngine.generate` during the session
is recorded as `phase_c_error` and the rest of the debrief is preserved
(FR-014/SC-007) — identical to local-mode feedback failures. No change to the
coordinator is required.

**Invariants (tests)**:
- [ ] an `OpenRouterEngine.generate` that raises `LLMEngineError` mid-session →
      report still written, `phase_c_error` populated, no crash.

## E. End-to-end behavior matrix

| Invocation | Token | Local Qwen present? | Result |
|---|---|---|---|
| `practice` | n/a | yes | local flow, offline, unchanged (SC-001) |
| `practice` | n/a | no | local flow degrades to Phase-B exactly as today |
| `practice --cloud` (1st) | none | either | prompt once + disclose → store → preflight → feedback via OpenRouter (SC-002/SC-003) |
| `practice --cloud` (2nd) | stored | either | silent reuse → feedback via OpenRouter (SC-003) |
| `practice --cloud` | stored-but-rejected | either | actionable error + re-prompt; still bad → exit (SC-006) |
| `practice --cloud` | valid, transient API failure | either | `phase_c_error`, debrief preserved (SC-007) |
