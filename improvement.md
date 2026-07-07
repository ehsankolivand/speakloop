# SpeakLoop — Improvement Review

_A prioritized, checkbox-driven list of concrete improvements for SpeakLoop, grounded in the current
codebase. Generated 2026-07-07 by a read-only multi-agent review (9 module/dimension reviewers +
per-finding adversarial verification against real code). No source was modified._

**Impact legend** — **High**: materially improves correctness, robustness, or maintainability of
something important; clear lasting benefit. **Medium**: solid improvement, moderate benefit or limited
scope. **Low**: worthwhile but minor polish.

**Summary:** High: 4 · Medium: 20 · Low: 21  (45 total)

Every item respects the project's hard constraints (offline default path, function-local engine
imports, English-only, no GUI, `schema_version` frozen at 1, immutable `specs/001`–`016`). Functional
defects already catalogued and resolved in `bug.md` (BUG-001..005) are **not** repeated here — this
review is forward-looking (structure, robustness gaps in untested branches, testing, tooling, UX).

---

## High

- [x] **IMP-001 — Restore the SIGINT handler after a session so Ctrl-C keeps working**
  - Impact: High
  - Area: Correctness
  - Where: `src/speakloop/sessions/abort.py:26-37` (`install_signal_handler`); installed at `sessions/coordinator.py:1063`, `finally` at `:1178-1179` never restores it
  - What & why: `run_session` installs a process-global SIGINT handler that only sets `abort_event` + deletes `*.tmp` and never raises/exits, and it is never uninstalled (the only `finally` just closes the ASR worker). After `run_session` returns into the debrief cbreak menu (`debrief/menu.py:34`, `os.read` under `tty.setcbreak`, which leaves `ISIG` on) and then `_pick_question`'s `input()` loop, a Ctrl-C fires this inert handler and returns without raising, so PEP 475 restarts the blocking read and the keypress is swallowed. Before any session the same Ctrl-C raised `KeyboardInterrupt` and exited; after one completed session it is dead for the rest of the process — a silent robustness regression on the most-used flow. The `abort.py:1` docstring ("exit 130") is also stale.
  - How to do it: Have `install_signal_handler` capture `signal.getsignal(SIGINT)` and return it (or add `abort.restore_signal_handler(prev)`); wrap the `run_session` body in `try/finally` and restore the previous handler on the way out (it runs on the main thread, so `signal.signal` is legal). Add a regression test asserting the prior handler is reinstated after `run_session` returns. Fix the `abort.py:1` docstring.
  - Effort: Small
  - Resolution: `abort.install_signal_handler` now returns the prior SIGINT handler and a new `abort.restore_signal_handler(prev)` reinstalls it; `run_session` captures `_prev_sigint` and wraps its whole body in `try/finally` to restore on both the normal-return and re-raised-`AbortedError` paths (`sessions/abort.py`, `sessions/coordinator.py`). Fixed the stale `abort.py` module docstring and the `sessions/CLAUDE.md` abort bullet. Tests: `tests/unit/sessions/test_abort.py` (install-returns-prior / restore round-trip, None-noop) + new `tests/integration/test_sigint_handler_restored.py` (normal + abort paths reinstate the prior handler). Verified by the full suite (870 passed, +4), `git diff -w` (body change is pure indentation), ruff clean on touched files, context-budget + byte-identical + phase-b-abort gates green.

- [x] **IMP-002 — Reject partial/interrupted downloads instead of validating them as complete**
  - Impact: High
  - Area: Correctness
  - Where: `src/speakloop/installer/validator.py:35` (`validate`) / `:25` (`_directory_size`); `installer/__init__.py:53` (`_missing_or_invalid`)
  - What & why: `validate()` declares a model OK whenever the summed byte count is within −25% of `expected_size_bytes`, with no awareness of aria2 control sidecars, and `_directory_size` sums every file including any `<shard>.aria2`. An aria2 download killed past ~75% (Ctrl-C, crash, power loss) leaves partial shard bytes plus a `.aria2` control file; on the next run `_missing_or_invalid` calls `validate` first, sees "ok", so the model is treated as present, resume never runs, and the user hits a cryptic engine-load / safetensors-parse failure whose only fix is manually deleting the directory. This nullifies feature 007's headline resumable-download guarantee.
  - How to do it: In `validate()`, before the size check, scan `local_path.rglob("*.aria2")` (and the `.incomplete` markers `snapshot_download` leaves) and return not-ok (reuse `reason="size_mismatch"` or add an additive reason) when any exist, so `_missing_or_invalid` re-queues the model and aria2 resumes via `--continue=true`. Optionally exclude `*.aria2` from `_directory_size`. Add a validator test that drops a `<shard>.aria2` sidecar next to an otherwise large-enough file and asserts `ok` is False.
  - Effort: Small
  - Resolution: Added `_has_incomplete_download()` + additive `reason="incomplete"` (Literal extended) to `installer/validator.py`; `validate()` now scans `local_path.rglob("*.aria2")`/`*.incomplete` BEFORE the size test and returns not-ok, so `_missing_or_invalid` re-queues an interrupted download for aria2 `--continue`/snapshot `resume_download`. No consumer switches on `reason` (doctor/engine_status/`_missing_or_invalid` read only `.ok`), so the new value is safe. Documented in `installer/CLAUDE.md`. Tests: two new cases in `tests/unit/installer/test_validator.py` (aria2 control file + `.incomplete` marker next to an otherwise size-passing file → `ok is False`, `reason=="incomplete"`). Verified by full suite (872 passed, +2), installer/doctor/engine_status/context-budget suites, ruff clean.

- [x] **IMP-003 — Break up the 439-line `run_session` god function**
  - Impact: High
  - Area: Structure
  - Where: `src/speakloop/sessions/coordinator.py:1024-1463` (`run_session`)
  - What & why: `run_session` is ~439 lines threading dir/scratch setup, signal install, the opt-in listen block, engine defaults, domain-context build, warm-up, the 3-attempt record loop + `_BackgroundAsr` worker + abort cleanup, triage, follow-ups, a 3-way analysis branch (serial / drills-concurrent-with-background-thread / aborted), the single store mutation, grading, trend folding, a ~50-line `Session` assembly, report write, SRS advance, and summary. It is the single hardest function in the app to modify safely; the drills-concurrent branch (`:1237-1286`) with its `_bg_analyze` thread + `holder` dict is especially fragile. Extraction lowers the risk of every future session change.
  - How to do it: Extract cohesive phases that already have clean inputs/outputs: (a) `_record_and_transcribe(...) -> list[Transcript]` around the attempt loop + `_BackgroundAsr` + abort cleanup (`:1134-1179`); (b) `_run_analysis_phase(...)` owning the aborted/drills-concurrent/serial selection incl. the background-thread orchestration (`:1228-1300`); (c) `_assemble_and_write_report(...)` for the `Session` build + write (`:1372-1423`); (d) `_persist_store(...)` for the SRS advance + contrast tally (`:1425-1452`). Lean on the byte-identical gates (`test_analysis_equivalence.py`, `test_drills_additive_byte_identical.py`) and `test_phase_b_abort.py` to protect the refactor.
  - Effort: Large
  - Resolution: Extracted (a) `_record_and_transcribe`, (b) `_run_analysis_phase` (the fragile three-strategy branch incl. the drills-concurrent daemon-thread orchestration), and (d) `_persist_store` as module-level helpers in `sessions/coordinator.py`; `run_session` now calls them, dropping ~90 lines and isolating its most fragile logic. (c) Session-assembly was consciously left INLINE — its ~25-field interface would make an extracted call wider and more error-prone than the single readable constructor. Documented the phase decomposition in `sessions/CLAUDE.md`. Verified byte-identical: all 70 session-path gates pass (analysis-equivalence, drills-additive-byte-identical, phase-b-abort/silent, followups, session-controls, cloud-coaching, phase-c-error, triage, artifact-consistency, daily-loop, sigint-restore), full suite 872 passed, ruff clean, `git diff HEAD` audited line-by-line by an independent fresh-context verifier subagent → EQUIVALENT.

- [x] **IMP-004 — Add a macOS-arm64 CI workflow that runs the default pytest suite**
  - Impact: High
  - Area: Tooling
  - Where: `.github/` (absent — no directory); gate filter `pyproject.toml:102`; arm64-only deps `pyproject.toml:26-33`
  - What & why: There is zero automated regression protection for an 866-test suite whose entire purpose is guarding hard constitution invariants — offline default path, function-local engine imports, byte-identical serial-vs-concurrent reports, CLAUDE.md line budgets, no personal absolute paths. Those tests run only when a human remembers `uv run pytest`. CI would catch a module-level engine import, a report byte-diff, or a >200-line CLAUDE.md the instant it is pushed.
  - How to do it: Add `.github/workflows/ci.yml` on `macos-14` (arm64 required — the mlx/kokoro/parakeet wheels are Apple-Silicon-only and will not install on Ubuntu). Steps: `astral-sh/setup-uv`, `uv sync`, `uv run pytest`. The `addopts` filter already deselects `live_download`/`live_cloud`/`live_pron`, and `live_asr`/`live_llm` self-skip without models, so the ~866 mocked tests run with no model download and exercise the import-isolation, analysis-equivalence, context-budget, and path-portability guards. Runs on dev tooling, not the runtime path — no offline-constraint violation.
  - Effort: Medium
  - Resolution: Added `.github/workflows/ci.yml` — `runs-on: macos-14` (arm64), steps `actions/checkout@v4` → `astral-sh/setup-uv@v5` (cache on) → `uv python install 3.12` → `uv sync` (uses committed `uv.lock`) → `uv run pytest`. Triggers on push + PR with a cancel-in-progress concurrency group. Verified: YAML parses (`yaml.safe_load`), no personal `/Users/` paths, path-portability + help-isolation gates pass; the commands are exactly the ones that pass locally. Note: end-to-end GitHub Actions execution can't be run from this environment, but every locally-verifiable aspect (syntax, runner, action versions, commands, lockfile) checks out.

---

## Medium

- [x] **IMP-005 — Guard untrusted `int()` conversions in coverage scoring**
  - Impact: Medium
  - Area: Correctness
  - Where: `src/speakloop/coverage/content_errors.py:25,27` (`validate_content_errors`); `coverage/scoring.py:46,54` (`_coverage_records`)
  - What & why: Four `int()` calls run directly on LLM-supplied fields with no guard (`int(e["attempt_ordinal"])`, `int(e["key_point_id"])`, `int(att.get("ordinal",0))`, `states[int(c["id"])]`). The model is untrusted output; one non-numeric value ("attempt 3", "n/a") raises `ValueError`. Worse, `score_coverage` builds the valid per-attempt records at `scoring.py:97` and only then calls `validate_content_errors` at `:98`, so a single stray content-error ordinal discards the already-computed valid coverage too — the job fails in `run_group`, flags the report analysis-pending, and `resume.py:137-146` swallows it silently. This is inconsistent with `grammar_analyzer.py:194-196`, which already defends the identical field per-item with `try/except (TypeError, ValueError): continue`.
  - How to do it: Wrap each per-item `int()` in `try/except (TypeError, ValueError)` and skip just that item (or drop just the malformed optional field), mirroring `grammar_analyzer._verify_and_enrich`. Add a unit test with a non-numeric `attempt_ordinal`/`id` (current `test_content_errors.py` only covers non-dict items).
  - Resolution: `content_errors.validate_content_errors` now drops just a malformed `attempt_ordinal`/`key_point_id` via `contextlib.suppress(TypeError, ValueError)` (keeping the contradiction); `scoring._coverage_records` skips just the malformed attempt (non-numeric `ordinal`) or coverage entry (non-numeric `id`) — so one stray LLM value can't discard the whole coverage pass and flag the report pending. Documented in `coverage/CLAUDE.md`. Tests: `test_content_errors.py` (non-numeric optional fields dropped) + `test_scoring.py` (non-numeric ordinal/id skipped, valid parts survive). Verified: coverage suite 15 passed, full suite 874 passed (+2), ruff clean (used `contextlib.suppress` to avoid a new SIM105).
  - Effort: Small

- [x] **IMP-006 — Guard the session-file read in store rebuild against unreadable/non-UTF8 files**
  - Impact: Medium
  - Area: Correctness
  - Where: `src/speakloop/store/rebuild.py:27-40` (`_iter_sessions`), read at `:31`
  - What & why: `_iter_sessions` is documented to skip unparseable files and wraps `frontmatter.parse(text)` in `try/except Exception: continue` — but `text = path.read_text(encoding="utf-8")` at `:31` sits **outside** the try. A single non-UTF8 byte, a `.md` with restrictive permissions, or a transient OS read error raises `UnicodeDecodeError`/`OSError` and crashes the whole `rebuild` run before any report is folded — the one command whose purpose is to recover from corruption. `trends/reader.py:60` handles the same corpus without this hole because `frontmatter.load` reads inside its guarded try.
  - How to do it: Move `path.read_text(...)` inside the `try` block so `UnicodeDecodeError`/`OSError` also hit the `continue` skip path, matching the docstring and the `reader.py` precedent. Add a regression test that drops a non-UTF8/binary `.md` into the sessions dir and asserts rebuild still returns and folds the valid siblings.
  - Effort: Small
  - Resolution: Moved `path.read_text(encoding="utf-8")` inside the `try` in `store/rebuild._iter_sessions`, so a non-UTF8 byte / unreadable file (`UnicodeDecodeError`/`OSError`) now hits the same `continue` skip path as a malformed frontmatter — matching the docstring and `trends.reader`. No CLAUDE.md change needed (store/CLAUDE.md already documents rebuild as skipping unparseable files / always recoverable). Test: `test_rebuild_skips_non_utf8_report_and_folds_valid_siblings` drops `\xff\xfe...` bytes into the sessions dir and asserts the valid siblings still fold. Verified: store suite 15 passed, full suite 875 passed (+1), ruff clean.

- [x] **IMP-007 — Fail loudly when a target phone is out-of-vocab instead of a silent "clear ✓"**
  - Impact: Medium
  - Area: Correctness
  - Where: `src/speakloop/pronunciation/wav2vec2_engine.py:197-227` (`Wav2Vec2Scorer._score_against_canonical`), the `if old_idx not in old_to_new: continue` at `:199-201`
  - What & why: `old_to_new` is built only for canonical symbols present in the model vocab; the `not canon_ids` guard returns `error` only when **all** phones are unknown. When just the **target** phone is out-of-vocab, the target loop `continue`s past it and the drill returns status `scored` with empty `flags` — which the runner renders as `clear ✓`, telling the learner they nailed a sound the model never evaluated. This is the last silent false-positive on the core teaching flow, and the only guards (`test_drill_bank.py`, the live oracle) both SKIP when `vocab.json` is absent, so a model swap, truncated/older vocab, or a misauthored symbol ships green and mis-teaches at runtime.
  - How to do it: In `_score_against_canonical`, track whether each requested target survived the vocab map; when a target's `old_idx` is not in `old_to_new`, return `DrillResult(..., "error", detail=f"target phone {sym!r} not in model vocab")` (error if none of the drill's targets survived), routing it to the same actionable `error` outcome the runner already surfaces/logs under `SPEAKLOOP_DEBUG`. Keep the existing `not canon_ids` guard.
  - Effort: Small
  - Resolution: `_score_against_canonical` now collects out-of-vocab targets into `unscored_targets`; if NO target survived the vocab map it returns `DrillResult(..., "error", detail="target phone(s) [...] not in model vocab")` instead of `scored`+empty flags (a false "clear ✓"). The existing `not canon_ids` guard (whole canonical unknown) still fires first; a drill with some targets surviving still scores those. Documented in `pronunciation/CLAUDE.md`. Test: `test_out_of_vocab_target_errors_instead_of_false_clear` (synthetic `_sym2id` lacking the target /w/, no model) asserts `status=="error"` and the phone is named. Verified: pronunciation suite 58 passed, full suite 876 passed (+1), ruff clean.

- [ ] **IMP-008 — Implement the specced last-practiced tiebreak in the due queue**
  - Impact: Medium
  - Area: Correctness
  - Where: `src/speakloop/srs/queue.py:50-54` (`_sort_key`); `DueItem` at `queue.py:26-32`
  - What & why: The docstring, `srs/CLAUDE.md`, and the inline comment at `queue.py:52` all promise "most overdue → lower grade → oldest last-practiced", but the tertiary key is `_parse_date(item.next_due)`, not last-practiced. `DueItem` carries no `last_practiced` field, and for two below-mastery non-new questions with equal `days_overdue`, `next_due = today − days_overdue` is identical, so the third element is always equal and the stable sort collapses to input file order. When daily capacity truncates the list, a recently-practiced question can win a slot over one not practiced in far longer — daily selection ends up depending on question-file ordering (contradicts FR-014's fairness intent).
  - How to do it: Add `last_practiced: str | None = None` to `DueItem` (defaulted, so `cli/today.py` stays source-compatible), populate it from `entry.last_practiced` (`store/model.py:34`) for non-new items in `due_queue`, make the final `_sort_key` element the parsed `last_practiced` ordinal (oldest first; `None → date.min`), and drop the redundant `next_due` key. Add a test with two equally-overdue same-grade questions whose `last_practiced` differs.
  - Effort: Small

- [ ] **IMP-009 — Align the grammar prompt's "minimal span" rule with the coherence filter's 2-token floor**
  - Impact: Medium
  - Area: Correctness
  - Where: `src/speakloop/feedback/grammar_analyzer.py:52` (`_SYSTEM_PROMPT`) vs `feedback/coherence.py:99` (`_coherent`, `MIN_WORD_TOKENS=2`)
  - What & why: The system prompt tells the model to "Quote the MINIMAL span containing the error — just the broken part, not the whole sentence," but the V2 coherence filter unconditionally returns `False` for any quote with fewer than 2 word tokens (`if len(tokens) < MIN_WORD_TOKENS: return False`, deliberately per `test_single_token_is_too_short`). A whole class of single-word L2 errors — "childs", "informations", "runned", "goed" — is a minimal single-token span, so a correct finding the model returns is silently discarded before it reaches the report. The two rules are in direct tension and the loss is invisible.
  - How to do it: Resolve it prompt-side: change `grammar_analyzer.py:52` to require one anchor word of context (e.g. "quote the broken part plus one adjacent word") and add a worked example so 'childs' is quoted as 'two childs'. That preserves V2's garble precision while letting single-word errors survive the ≥2-token floor. Add a coherence/analyzer test asserting a two-token minimal span for a single-word error passes; confirm no test pins the exact prompt text first.
  - Effort: Small

- [ ] **IMP-010 — Surface the reason when background feedback crashes in the drills path**
  - Impact: Medium
  - Area: Correctness
  - Where: `src/speakloop/sessions/coordinator.py:1246-1256` (`_bg_analyze`) and `:1284-1286`
  - What & why: In the drills-concurrent path, `_analyze` runs in a background thread wrapped in bare `except Exception: holder["outs"] = None`. Because `_analyze` already handles per-call LLM failures internally, this catch only fires on an **unexpected** crash — and silently converts it to a pending report with no reason printed and no diagnostic recorded. It is asymmetric with the serial path (`:1287` else-branch, where failures propagate) and contradicts 017's own "surface the swallowed reason" philosophy behind `pronounce --debug`. The user finishes the drills and gets a bare "run resume" with zero indication of why.
  - How to do it: Capture the exception (`holder["error"] = repr(e)`, optionally with a traceback) instead of discarding it; after the join, when `outs is None`, print one yellow line with the reason and/or thread it into the pending report's `phase_c_error`. Keep the degrade-to-pending behavior; just stop dropping the diagnostic.
  - Effort: Small

- [ ] **IMP-011 — Give the coverage/keypoints JSON calls the same bounded regenerate as grammar**
  - Impact: Medium
  - Area: Correctness
  - Where: `src/speakloop/coverage/scoring.py:90-95` (`score_coverage`); `coverage/keypoints.py:58-66` (`derive_key_points`) vs `feedback/grammar_analyzer.py:311-322`
  - What & why: Only `grammar_analyzer.analyze` retries — on parse failure or a detected repetition loop it does one bounded regenerate with `retry=True`. The other structured-output callers, including `score_coverage` (the single most expensive analytic call: all three attempts + every key point + the reference answer) and `derive_key_points`, do a single `generate` + `_extract_json` with no fallback, so one transient JSON-format hiccup discards the entire coverage result and flags the report analysis-pending. The `LLMEngine` Protocol exposes `retry=True` intent for exactly this and all three engines honor it, but the coverage path never uses it.
  - How to do it: On `_extract_json` `ValueError` (and empty response), do one bounded re-call with `retry=True` before giving up — ideally via a shared `generate_json(llm, system, user, *, max_tokens, temperature)` helper (pairs naturally with IMP-034) encapsulating generate + parse + one retry, then route `score_coverage`/`derive_key_points`/`generate_followups` through it. Keep it to a single retry so it stays bounded.
  - Effort: Medium

- [ ] **IMP-012 — Fix the broken `.gitignore` line that disables the `*.pem` credential safety net**
  - Impact: Medium
  - Area: Correctness
  - Where: `.gitignore` last lines — `*.pem` and `.claude/scheduled_tasks.lock` are glued into one pattern with no separating newline
  - What & why: Confirmed via `od -c`: the bytes are `*.key\n*.pem.claude/scheduled_tasks.lock\n`, so the `# credentials (safety net)` block's `*.pem` and the scheduled-tasks lock are concatenated into the single pattern `*.pem.claude/scheduled_tasks.lock`. As a result `*.pem` is **not** ignored (`git check-ignore foo.pem` exits 1), so a committed private key would slip past the stated safety net, and `.claude/scheduled_tasks.lock` is only excluded via the un-shared `.git/info/exclude`.
  - How to do it: Split into two lines — `*.pem` alone, then `.claude/scheduled_tasks.lock` (and likely `.claude/scheduled_tasks.json`). Verify with `git check-ignore -v foo.pem` returning a `.gitignore` rule.
  - Effort: Small

- [ ] **IMP-013 — Surface OpenRouter's error-response body**
  - Impact: Medium
  - Area: UX
  - Where: `src/speakloop/llm/openrouter_engine.py:83` (`OpenRouterEngine._send`, `HTTPError` branch)
  - What & why: On `urllib.error.HTTPError` the handler raises "OpenRouter request failed (HTTP {status})." and drops `e` entirely — `e.read()` is never called for the generic/404/5xx cases. OpenRouter returns a JSON body with `error.message` explaining the real cause (unsupported model, insufficient credits, provider outage, moderation). Cloud analysis is opt-in and silent-fails into `phase_c_error`, so the user gets only a bare status code with no way to diagnose. The token lives only in the request `Authorization` header, never in the response body, so echoing a truncated body snippet does not violate the module's "token never logged" rule.
  - How to do it: In the `HTTPError` branch, read the body defensively (`detail = e.read().decode(errors="replace")[:200]` inside its own `try/except`), attempt `json.loads` to pull `error.message`, and append the truncated detail to the raised `LLMEngineError` for the generic/404/5xx cases (keep 401/403 → `OpenRouterAuthError`). Add a test that raises `HTTPError` with a non-empty JSON error body.
  - Effort: Small

- [ ] **IMP-014 — Repaint the debrief read-aloud in place via `rich.Live` instead of reprinting the whole view per section**
  - Impact: Medium
  - Area: UX
  - Where: `src/speakloop/debrief/debrief.py:100-102` (`_on_section`); `debrief/renderer.py:169,203-210` (`supports_live`/`live`, both unused)
  - What & why: The read-aloud stage advances a highlight by calling `renderer.print_static(...)` in the per-section callback, and `print_static` re-emits the **entire** composed view — narrative panel, top-priority banner, attempt table, every grammar card, transcripts panel — once per audio section, scrolling the terminal with stacked duplicate copies just to move one highlight. `renderer.py` already ships `live()` (`rich.Live`) and `supports_live()` for exactly this in-place repaint, but a grep shows zero callers of either — dead code. The headline follow-along feature (US3) is materially degraded.
  - How to do it: In the read-aloud path, when `supports_live(console)` is true, open the renderer's `live()` context and have `_on_section` call `live.update(renderer.build(highlight_ref=...))` instead of `print_static`, so the highlight moves in place. Keep `print_static` as the non-terminal/test fallback (`supports_live` is false for the `StringIO` console tests use, so captured-output assertions stay valid).
  - Effort: Medium

- [ ] **IMP-015 — Break up the 240-line `practice.run()` orchestrator**
  - Impact: Medium
  - Area: Structure
  - Where: `src/speakloop/cli/practice.py:420-663` (`run`)
  - What & why: `run()` interleaves at least five separable responsibilities across ~243 lines: engine-choice resolution + speed clamping (`440-454`), Q&A load + question pick (`456-474`), phase A/B/C model provisioning with three nested `try/except` and three distinct degrade messages (`481-508`), ASR + grammar-analyzer + pronunciation-drill construction (`558-594`), and the listen/session/debrief loop (`598-663`). At this length with deep nesting it is hard to follow and effectively untestable except end-to-end through the CLI.
  - How to do it: Extract two private helpers taking `(engine_choice, listen_only, console, ...)`: `_provision_models(...)` for the `ensure_models` base + `engine_needs_local_llm` Phase-C block (`481-508`), and `_build_analysis(engine_choice, console)` for the grammar/coach/runners/parallel_safe wiring (`572-585`). `run()` then reads as a short named sequence, and each helper becomes unit-testable with a fake installer/console.
  - Effort: Medium

- [ ] **IMP-016 — Consolidate the three blocking raw-key readers**
  - Impact: Medium
  - Area: Structure
  - Where: `src/speakloop/cli/practice.py:126` (`_cbreak_read`); `debrief/menu.py:34` (`_cbreak_read_key`); vs `sessions/keyboard.py:90` (`RawKeyReader._resolve_fd`) + `:29` (`canonicalize`)
  - What & why: The termios cbreak + `/dev/tty`-fallback + byte-to-canonical-key logic is hand-reimplemented three times. `practice._cbreak_read` (1 byte) and `menu._cbreak_read_key` (3 bytes for arrows) have near-identical `tcgetattr`/`setcbreak`/`os.read`/`tcsetattr` bodies, and each of `read_key()`/`_read_key()` repeats the same stdin-then-`os.open("/dev/tty")` fd-resolution that `keyboard._resolve_fd` already owns. A subtle fix to one copy (Ctrl-C `0x03` mapping, EOF-on-tty) silently won't propagate. This is documented as Trap 6 ("code fix pending").
  - How to do it: Add one blocking helper in `sessions/keyboard.py`, e.g. `read_key_blocking(*, decode, read_bytes=1)`, centralizing the stdin-then-`/dev/tty` cbreak read and the line-buffered fallback, taking the caller's own `decode` function (practice keeps its case-sensitive r/R table; menu keeps its 3-byte arrow-escape table). Delete `practice._cbreak_read` and `menu._cbreak_read_key` and route both through it. Update the CLAUDE.md divergence notes in the same commit.
  - Effort: Medium

- [ ] **IMP-017 — Replace the stringly-attached `.runners`/`.engine` on analyzer functions with a typed container**
  - Impact: Medium
  - Area: Structure
  - Where: `src/speakloop/cli/practice.py:684-687, :885-886, :965-966` (attach) and `:581-585` (read)
  - What & why: All three grammar-analyzer builders return a plain closure and monkeypatch `.runners` and `.engine` onto the function object; `run()` reads them back via `getattr(grammar_analyzer, "engine", None)` then `getattr(_analysis_engine, "parallel_safe", False)`. If any current or future builder forgets `_runner.engine = ...`, `analysis_parallel_safe` silently resolves to `False` and cloud/Claude analysis runs **serially** — a pure performance regression with no error. Crucially the byte-identical equivalence test (serial == concurrent) still passes, so no test would catch it. The fragile attribute pattern is a robustness and readability liability on a core flow (all three builders happen to set both attributes today, so there is no live bug — this closes the blind spot).
  - How to do it: Have the three builders return a small frozen dataclass, e.g. `GrammarAnalysis(runner, runners, engine, coach)`, instead of a bare callable with bolted-on attributes. `run()`/`resume` then read typed fields; a missing `engine` becomes a construction-time error rather than a silent serial fallback. The change is contained to the three builders + the read site.
  - Effort: Medium

- [ ] **IMP-018 — Unify the duplicated device-loss/resample recovery ladder in playback**
  - Impact: Medium
  - Area: Structure
  - Where: `src/speakloop/audio/playback.py:95` (`play`) / `:141` (`_start_nonblocking`)
  - What & why: The 3-attempt open loop (catch `sd.PortAudioError` → `sd.stop` → `_reinitialize` → backoff) plus the "resample to device native rate" fallback is implemented twice, nearly verbatim: `play()` at `:95-119` and `_start_nonblocking()` at `:141-161`. This is the subtlest, most-likely-to-drift code in the module — it exists to survive Bluetooth loss and CoreAudio rate switches — and a future fix applied to one copy silently misses the other, splitting behavior between the blocking listen-loop path and the non-blocking interruptible path.
  - How to do it: Extract `_open_with_recovery(data, sample_rate, *, blocking)` running the retry+resample ladder, `sd.wait`-ing when blocking else returning the effective samplerate. `play()` calls it `blocking=True`, `_start_nonblocking()` `blocking=False`. The existing `test_playback` / `test_playback_interruptible` suites pin both sides across the refactor.
  - Effort: Medium

- [ ] **IMP-019 — Correct `AI_CONTEXT.md`, which actively denies the pronunciation-scoring feature exists**
  - Impact: Medium
  - Area: Structure
  - Where: `AI_CONTEXT.md:60` and `AI_CONTEXT.md:449-450` (also spot-check `README.md:193-194`, cited as their source)
  - What & why: This 54 KB onboarding briefing (purpose: accurately describe the repo "as it is today") predates 016/017 and explicitly states phoneme-level pronunciation scoring is "Out of scope for v1" and "speakloop does not score pronunciation" — but 016/017 shipped exactly that (wav2vec2 CTC GOP scorer, `pronounce` command, drill trainer). An agent or contributor reading it forms a wrong mental model of a whole subsystem. (`AI_CONTEXT.md` is not a `specs/001`–`016` or constitution artifact, so editing it is allowed.)
  - How to do it: Regenerate `AI_CONTEXT.md` to include the pronunciation module (mirroring how root `CLAUDE.md` documents 016/017) and bump `last_updated`; or, if it is meant to be point-in-time, add a top banner pointing to `CLAUDE.md` as the live source. At minimum remove the two false "no pronunciation scoring" lines and fix the README source line if it carries the same stale claim.
  - Effort: Medium

- [ ] **IMP-020 — Add mypy on the pure-logic modules to the dev group (it finds real issues today)**
  - Impact: Medium
  - Area: Tooling
  - Where: `pyproject.toml:61-66` (dev group has ruff/pytest, no type-checker); targets: `srs`, `store`, `coverage`, `metrics`, `pronunciation/gop.py` + `drill_runner.py`
  - What & why: The codebase is ~98% annotated (508/518 functions) and leans on Protocols (`LLMEngine`, `PronunciationScorer`) — ideal for a static checker — yet none is configured. A trial run (`uv run --with mypy mypy --ignore-missing-imports`) surfaces concrete latent issues tests do not catch: `srs/queue.py:89` calls `_parse_date(it.next_due)` twice so the value re-widens to `date | None` (`Unsupported operand types for >= ("date" and "None")` — also a minor real inefficiency), and `drill_runner.py:396,427` pass a `Callable | None` `speak` into `_hear_first`, whose param (`:151`) is non-Optional.
  - How to do it: Add `mypy` to `[dependency-groups] dev` and a `[tool.mypy]` scoped to the engine-free pure-logic modules with `ignore_missing_imports = true` (mlx/torch lack stubs). Run non-blocking in CI first (pairs with IMP-004), then tighten. Concretely fix the two errors above (bind the `_parse_date` result once; reconcile the `speak` signatures).
  - Effort: Medium

- [ ] **IMP-021 — Wire up the unused `live_llm` marker: fix its filter/name and add the smoke test it implies**
  - Impact: Medium
  - Area: Testing
  - Where: `pyproject.toml:97` (marker text) + `:102` (addopts filter); `tests/unit/llm/test_qwen_engine.py:99-142` (`_install_fake_mlx_lm`)
  - What & why: The `live_llm` marker is declared and referenced in a docstring but used by **zero** test — the DEFAULT engine (local Qwen via `mlx_lm`) is the only model path with no real-model harness (ASR, cloud, downloader, pronunciation each have one). The qwen unit tests fabricate a fake `mlx_lm` module and assert the wrapper calls `make_sampler(...)`/`generate(...)` a certain way, so the "regression for the real mlx_lm API" is validated only against the test's own fake — an `mlx_lm` bump that changed those signatures would break every local session while the suite stays green. Two adjacent defects compound it: the marker text says "excluded from the default suite" but `addopts` excludes only `live_download`/`live_cloud`/`live_pron` (not `live_llm`), and the text mislabels the model "Qwen3-8B" while the manifest is `Qwen3-14B-4bit`.
  - How to do it: Add `tests/live_llm_test.py` marked `@pytest.mark.live_llm` that self-skips when the model/deps are absent (`pytest.importorskip("mlx_lm")` + a model-presence guard, mirroring `live_pron_test.py`), loads the real Qwen through `QwenEngine`, and does one tiny generate asserting the real `make_sampler`/`generate` kwargs the fakes assume. While there, add `and not live_llm` to the `addopts` `-m` filter and correct the marker text `Qwen3-8B → Qwen3-14B-4bit`.
  - Effort: Medium

- [ ] **IMP-022 — Unit-test `Wav2Vec2Scorer._read_audio` silence/short-clip gating with the committed silent WAV**
  - Impact: Medium
  - Area: Testing
  - Where: `src/speakloop/pronunciation/wav2vec2_engine.py:143-157` (`_read_audio`) + `tests/fixtures/wav/recordings/attempt-silent.wav`, `attempt-short.wav` (committed, unused)
  - What & why: `_read_audio` decides the user-facing `not_captured` outcome via three pure, model-free rules: multi-channel averaging (`data.mean(axis=1)`), a min-length gate (`data.size < _MIN_SPEECH_SECONDS * _SAMPLE_RATE`), an RMS silence gate, plus a scipy resample when `sr != 16 kHz`. A grep for `_read_audio` in `tests/` returns nothing — every `not_captured` test fakes a scorer that just returns the status, so the actual gating math is never exercised, and the committed `attempt-silent.wav`/`attempt-short.wav` fixtures sit unused. A regression in either threshold, the RMS formula, or the resample path would silently ship a scorer that drops real speech or scores silence.
  - How to do it: Add a unit test calling `Wav2Vec2Scorer._read_audio(...)` on `attempt-silent.wav` (assert `None` via RMS gate), a sub-min-length / `attempt-short.wav` clip (assert `None` via length gate), and a normal clip (assert a 16 kHz float32 array). Synthesize a 2-channel and an off-rate array with `soundfile` to pin the averaging + resample branches. No model needed — `_read_audio` is a pure staticmethod.
  - Effort: Small

- [ ] **IMP-023 — Cover `resume.py` corrupt-report / no-transcript / still-failing skip paths**
  - Impact: Medium
  - Area: Testing
  - Where: `src/speakloop/cli/resume.py:73-77, 115-117, 128-130` + `tests/integration/test_daily_loop.py:103` (`test_resume_clears_pending`, the sole resume test)
  - What & why: `resume.run` has three robustness branches `cli/CLAUDE.md` explicitly calls load-bearing ("a corrupt pending report can't masquerade as nothing to resume"): unreadable frontmatter → warn-and-skip; pending report with no recoverable transcripts → warn-and-skip; analysis failing again → left pending (not falsely marked done). None of these messages appears in any resume test — the only resume test drives the happy path, and `_extract_attempt_transcripts` is exercised only transitively. A regression that made resume skip corrupt reports silently, or mark a still-failing report resolved, would pass green.
  - How to do it: Add resume tests: a pending `.md` with malformed frontmatter → assert the yellow "unreadable … skipping" line + file left pending; a pending report with an empty/garbled Transcripts section → assert the "no transcripts found" skip; inject a grammar analyzer that raises → assert `analysis_pending` stays `True`. Add a direct unit test for `_extract_attempt_transcripts` (the `_(silent)_`→"" mapping and section-boundary exit).
  - Effort: Medium

- [ ] **IMP-024 — Add a substitution (true-positive) case to the live pronunciation calibration oracle**
  - Impact: Medium
  - Area: Testing
  - Where: `tests/live_pron_test.py:39-87` vs thresholds in `src/speakloop/pronunciation/wav2vec2_engine.py:39-41`
  - What & why: The `-m live_pron` harness renders each drill's own clean prompt and asserts **no** flag fires — it validates only the false-positive axis. Nothing renders a **wrong** word to confirm a genuine substitution DOES flag. Since `_COMPETITOR_FLAG_MARGIN` was loosened 0.5→1.5 to fix over-flagging, the same lever can silently drift into **under**-flagging (a real /r/-for-/w/ error scored `clear ✓`) with zero automated signal on real audio — the only true-positive coverage is synthetic posteriors in `test_scorer_thresholds.py`. CLAUDE.md calls this harness "the calibration oracle," yet it guards only one direction.
  - How to do it: Extend the live harness (or add a sibling `-m live_pron` test) that, per contrast, TTS-renders a competitor/confusion word (from `Contrast.competitors`) and scores it against the **target** drill's canonical sequence, asserting the target phone DOES flag (e.g. synth "rest" scored against the `w_r` canonical must flag /w/; "doze" against `th_d`'s "those" canonical must flag /ð/). Closes the loop so both too-loose and too-tight threshold regressions are caught on real audio.
  - Effort: Medium

---

## Low

- [ ] **IMP-025 — Fix the broken `_pick_question` return annotation**
  - Impact: Low
  - Area: Correctness
  - Where: `src/speakloop/cli/practice.py:43` (`_pick_question`)
  - What & why: The return annotation is `speakloop.content.Question | None` with `# noqa: F821` suppressing the undefined-name warning. The module never binds the name `speakloop` (it does `from speakloop.content import ...` and `from speakloop import installer`), so the annotation only survives because `from __future__ import annotations` stringizes it — `typing.get_type_hints()` on this function raises `NameError` (reproduced). It's a misleading, non-resolvable hint kept alive by a `noqa`.
  - How to do it: Import the type properly — `from speakloop.content import Question` (under `TYPE_CHECKING`), annotate `-> Question | None`, and drop the `# noqa: F821`.
  - Effort: Small

- [ ] **IMP-026 — Harden `_coverage_section` against missing per-point keys**
  - Impact: Low
  - Area: Correctness
  - Where: `src/speakloop/feedback/report_builder.py:196-213` (`_coverage_section`)
  - What & why: `_coverage_section` subscripts parsed dicts directly (`int(pp["id"])`, `pp["state"]`) — values that come straight from `frontmatter.parse` with no inner-key validation. In `resume` the coverage runner may not overwrite `session.coverage`, so a hand-edited or truncated pending report with a per-point missing `state`/`id` reaches `build()`, which is called at `resume.py:166` **outside** the loop's `try/except` — so one malformed report raises `KeyError`/`ValueError` and aborts the whole resume pass, even though `parse()` is deliberately tolerant. The same file is already defensive at `:304` (`pp.get("state")`).
  - How to do it: Switch the direct subscripts to `.get(...)` with sane fallbacks (`pp.get("state", "missed")`, skip a per-point whose id is missing/non-int), mirroring `:304`. Add a render test feeding a coverage record with a malformed per-point.
  - Effort: Small

- [ ] **IMP-027 — Don't silently return zero grammar patterns when the model omits the `errors` wrapper**
  - Impact: Low
  - Area: Correctness
  - Where: `src/speakloop/feedback/grammar_analyzer.py:327` (`analyze`)
  - What & why: After JSON recovery, `errors_raw = payload.get("errors") or []`. If the model returns a valid dict missing the `errors` wrapper (a bare single-error object or a synonym key), `analyze` returns `[]` and the report says "No actionable grammar patterns detected" though the model found errors — a silent-zero that is worse than the graceful `phase_c_error` path. It's also asymmetric: `_extract_json` only returns dicts, so a top-level JSON **list** of errors falls through to a `ValueError` and hard-fails to `phase_c_error`.
  - How to do it: When `payload` is a dict with no `errors` key but looks like a single error object (has `quote`/`attempt_ordinal`), wrap it into a one-element list; and let `_extract_json` return/coerce a top-level list so a bare list survives. Feed the coerced list to `_verify_and_enrich` — V1/V2/V3 still discard anything that isn't a real error, so only genuine findings are recovered. Add tests for an unwrapped single object and an unwrapped list.
  - Effort: Small

- [ ] **IMP-028 — Distinguish a network failure from a genuinely absent metadata file**
  - Impact: Low
  - Area: Correctness
  - Where: `src/speakloop/installer/downloader.py:260` (`_fetch_metadata`); `shards.py:34` (fallback)
  - What & why: `_fetch_metadata` treats **every** non-zero curl exit as "not in repo, skipping" and deletes the target, without inspecting the code. Under `curl --fail`, exit 22 means HTTP≥400 (file legitimately absent) but 6/7/28/35/56 mean DNS/connect/timeout/TLS. A transient blip on `model.safetensors.index.json` is swallowed; `discover_shards` then falls back to `["model.safetensors"]`, which for a sharded repo (Qwen3-14B-4bit) 404s and surfaces `DownloadNotFoundError "repo or shard filename is wrong"` — a misdiagnosis of a network blip. (Narrow window: needs a transient failure hitting only the index.)
  - How to do it: Inspect `proc.returncode`: keep the silent "skipping" path only for `0`/`22`; for network-class exits print a distinct warning and either retry the metadata phase or raise a typed transient error rather than silently degrading the shard plan.
  - Effort: Small

- [ ] **IMP-029 — Surface input-stream overflow instead of silently dropping it**
  - Impact: Low
  - Area: Correctness
  - Where: `src/speakloop/audio/recorder.py:48` (`_callback`)
  - What & why: The `InputStream` callback receives a `status` flag signalling input overflow (dropped mic samples) — the exact condition that degrades the ASR this app depends on — but discards it with a bare `pass` and a comment "surface later if needed", and nothing ever surfaces it. A glitchy capture yields a worse transcript with zero diagnostic trail.
  - How to do it: Thread-safely record overflow occurrences from the callback (set a `threading.Event` or increment a counter when `status` is truthy / has `input_overflow`), and after the stream closes log one English warning (optionally note it in ASR provenance) if any overflow was seen. Observability only — no change to recording behavior.
  - Effort: Small

- [ ] **IMP-030 — Remove or re-home the unused `timer.run` countdown**
  - Impact: Low
  - Area: Structure
  - Where: `src/speakloop/sessions/timer.py:27-64` (`run`); `sessions/CLAUDE.md:64`
  - What & why: `timer.run` has no production caller — the recording countdown/progress is owned by `session_ui.make_recording_progress` plus the inline `_ticker` thread in `coordinator._record_stage`. `timer.run`'s only references are its own two unit tests and `sessions/CLAUDE.md:64`, which still documents it as **the** "rich.progress countdown" public interface. It is dead code that makes the module doc misleading about how recording is actually rendered. (`timer.time_budget_for` is live — keep it.)
  - How to do it: Either delete `timer.run` + its two test cases and update the CLAUDE.md bullet to point at `session_ui.make_recording_progress` + `_record_stage` as the live path, or route `_record_stage` through it to remove the duplicated ticker/progress logic.
  - Effort: Small

- [ ] **IMP-031 — Deduplicate the pronunciation RAM-gate interactive-override UX**
  - Impact: Low
  - Area: Structure
  - Where: `src/speakloop/cli/practice.py:305 & :354-369` vs `cli/pronounce.py:63 & :77-87`
  - What & why: `practice.py` and `pronounce.py` each define an identical `_is_interactive()` and each implement the same "unsafe → offer the freeze-warned override" flow with a byte-identical prompt string — and the accept message has **already** drifted (`practice.py:365` "loading the pronunciation model…" vs `pronounce.py:85` "loading the model…"). Two copies of a machine-freeze consent prompt is exactly where inconsistency creeps in, and the drift proves it. Both live in the same `cli/` package.
  - How to do it: Extract one cli-level helper (e.g. `_confirm_freeze_override(console, decision, *, input_fn, interactive) -> bool`) plus a single shared `_is_interactive()`, and call it from both `_resolve_pronunciation_drills` and `_gate_ok`. The two gates still differ only in which `assess_*` produced `decision`.
  - Effort: Small

- [ ] **IMP-032 — Deduplicate the two cross-attempt narrative generators**
  - Impact: Low
  - Area: Structure
  - Where: `src/speakloop/feedback/report_builder.py:40-57` (`_cross_attempt_paragraph`) and `feedback/narrative.py:147-194` (`build_narrative`)
  - What & why: Two independent implementations produce the same climbed/dropped/held-steady WPM-and-filler prose. `report_builder.build` uses `session.cross_attempt_narrative or _cross_attempt_paragraph(...)`, but both production callers always persist `cross_attempt_narrative` via `narrative.build_narrative` — so the fallback is effectively test-only code that can silently rot or diverge from the canonical wording, and is strictly worse for <3 attempts (returns "" → an empty "Cross-attempt comparison" section, whereas `build_narrative` degrades gracefully).
  - How to do it: In `build()`, replace `_cross_attempt_paragraph(session.attempts)` with `narrative.build_narrative(session.attempts, session.grammar_patterns)` and delete `_cross_attempt_paragraph` (no import cycle: `narrative` imports only `frontmatter`, which `report_builder` already depends on). One prose implementation.
  - Effort: Small

- [ ] **IMP-033 — Dedupe the first-attempt and retry hear→score steps in `run_drill_item`**
  - Impact: Low
  - Area: Structure
  - Where: `src/speakloop/pronunciation/drill_runner.py:366-465` (`run_drill_item`): first attempt at `:396-401` vs retry loop body at `:425-448`
  - What & why: `run_drill_item` is a ~100-line function whose retry loop re-implements the first attempt's hear→record→score sequence (`_hear_first(...)` + `_score_once(..., label=...)` mirrored with a `retry:` label), with outcome bookkeeping interleaved with console printing across a 4-deep nested block — making the early-break outcomes and quit-during-retry item-preservation contract harder to follow than needed.
  - How to do it: Extract a small `_attempt(drill, *, label, ...) -> (status, flags, detail)` helper wrapping `_hear_first` + `_score_once`, and lift the retry loop into `_run_bounded_retry(...)` that returns the retry sub-dict and re-raises `DrillQuit` with the partial item attached. Existing `test_drill_runner*.py` tests pin the behavior, so it stays a pure readability refactor.
  - Effort: Small

- [ ] **IMP-034 — Promote the shared `_extract_json` to public API**
  - Impact: Low
  - Area: Structure
  - Where: `src/speakloop/feedback/grammar_analyzer.py:99` (`_extract_json`), imported by `coverage/scoring.py`, `coverage/keypoints.py`, `triage/mishearing.py`, `triage/consistency.py`, `interviewer/followups.py`, `warmup/drill.py`
  - What & why: Six analysis modules across four packages import the underscore-prefixed private symbol `feedback.grammar_analyzer._extract_json` as their JSON-recovery ladder. The "shared recovery ladder" is a documented cross-module contract (`llm-calls.md` O8, `feedback/CLAUDE.md` O4), yet is expressed as a private import — the leading underscore misleads the next reader, and a future refactor of `grammar_analyzer` internals could silently break five other modules.
  - How to do it: Expose it as public API — rename to `feedback.grammar_analyzer.extract_json` (thin private alias if needed) or, cleaner, lift it plus `_strip_code_fences` into a small `feedback/json_recovery.py` and re-export, then update the six importers. No behavior change; gives the shared contract a natural test home (pairs with IMP-011).
  - Effort: Small

- [ ] **IMP-035 — Consolidate the duplicated prompt seed-and-read helper**
  - Impact: Low
  - Area: Structure
  - Where: `src/speakloop/coverage/prompts.py:17` (`_seed_and_read`); `interviewer/prompts.py:21-24`; `triage/prompts.py:20-25`; `warmup/drill.py:43-46`; `feedback/cloud_prompt.py:30-33,46-49`
  - What & why: The identical "if not target.exists(): mkdir(parents) + write packaged default; return `(target.read_text(), target)`" block is copy-pasted seven times across six files. `coverage/prompts.py` already factored it into `_seed_and_read`; the other five reimplement it inline. Seven hand-maintained copies of a first-run seeding routine is a drift risk (encoding, mkdir, seed-vs-read ordering must stay in lockstep).
  - How to do it: Add one shared helper (e.g. `config.paths.seed_and_read(target, default_asset) -> tuple[str, Path]`, since `config` already owns the `~/.speakloop` path builders and is a leaf) and route all loaders through it. Public loader signatures stay identical. (`triage.load_consistency_prompt` reads without seeding — leave it out.)
  - Effort: Small

- [ ] **IMP-036 — Collapse the repeated scalar-validation boilerplate in `loop_config.load()`**
  - Impact: Low
  - Area: Structure
  - Where: `src/speakloop/config/loop_config.py:119-156` (`load()`)
  - What & why: `load()` hand-rolls six near-identical `try: x = max(1, int(data.get(key, DEFAULT))) except (TypeError, ValueError): x = DEFAULT` blocks plus two copy-pasted bool checks and two enum-membership checks. The module CLAUDE.md lists "add a parse branch in `load()`" as a routine per-key modification, so the pattern is copied every feature (010/011/012/016/017 each added more). Consolidating cuts the copy-paste surface and gives the clamp logic one code path.
  - How to do it: Add small typed helpers next to the existing `_model`/`_effort`: `_int(data, key, default, *, floor=None, ceil=None)`, `_bool(data, key, default)`, `_choice(data, key, default, valid)`. Rewrite `load()` as a sequence of one-line helper calls; `LoopConfig` construction and behavior stay identical.
  - Effort: Small

- [ ] **IMP-037 — Archive the stale per-branch autonomous-run reports out of the repo root**
  - Impact: Low
  - Area: Structure
  - Where: Repo root: `MORNING_REPORT.md` (011) and `RETURN_REPORT.md` (014), both git-tracked
  - What & why: Two point-in-time sprint reports sit at the repo root beside `README`/`CLAUDE.md`, each declaring its branch "NOT merged into main" — but per project memory 010–015 are now on main, so the top-level claims are stale and confusing to a new contributor. The project already established the archival pattern (`RETURN_REPORT.md` itself notes the 012 report was moved into `specs/012-responsive-session-flow/`).
  - How to do it: Move `MORNING_REPORT.md` into `specs/011-claude-code-engine/` and `RETURN_REPORT.md` into `specs/014-agent-context-overhaul/`, matching the existing convention (adding a new archived file is allowed; the constraint forbids editing existing `specs/001`–`016` artifacts, not adding one), leaving the root with only live docs.
  - Effort: Small

- [ ] **IMP-038 — Refresh clip mtime on cache hit so prune is true LRU, not LRU-by-creation**
  - Impact: Low
  - Area: Performance
  - Where: `src/speakloop/tts/cache.py:34` (`lookup`) / `:74` (`prune`)
  - What & why: `prune()` evicts by `st_mtime` ("oldest mtime first"), but `lookup()` returns a hit without touching any timestamp and `store()` only sets mtime at creation — so eviction order is least-recently-**created**, not least-recently-**used**, contradicting the `:13` "Pruned LRU-by-mtime" comment. A frequently replayed prompt keeps its original synthesis mtime and can be evicted before recent one-off clips when the cap trips. (Payoff is modest — the 512 MB cap rarely trips — but it's a clean documented-intent fix.)
  - How to do it: In `lookup()`, on a hit best-effort bump mtime: `with contextlib.suppress(OSError): os.utime(p, None)`, turning `prune`'s mtime ordering into a real access-time LRU without changing the key formula or `store()`. Extend the prune test with a "use the oldest entry via lookup then assert it survives eviction" case.
  - Effort: Small

- [ ] **IMP-039 — Avoid decoding the recording WAV twice on the Whisper VAD path**
  - Impact: Low
  - Area: Performance
  - Where: `src/speakloop/asr/whisper_mlx_engine.py:167` (`_transcribe_with_vad`, `_load_audio` at `:110`); `asr/vad.py:96`
  - What & why: For every full attempt, `_transcribe_with_vad` calls `self._load_audio` (→ `mlx_whisper.audio.load_audio`, a full ffmpeg decode to 16 kHz) then `vad.segment(wav_path)` which calls `silero_vad.read_audio` (`vad.py:96`) — a second full decode of the same file at the same rate, producing numpy vs torch views of identical samples. Doubles the per-attempt file-decode cost for no benefit. (ROI is marginal — a short-WAV decode — and it touches the pinned-`torchaudio<2.9` silero path, so deprioritize.)
  - How to do it: Add a `vad.segment_array` variant (or optional pre-loaded-array arg) so the Whisper path decodes once and passes samples in, converting the mlx/numpy array to the torch tensor `get_speech_timestamps` wants via `torch.from_numpy`; keep the path-based signature for other callers. Validate with `-m live_asr`.
  - Effort: Medium

- [ ] **IMP-040 — Stop printing every doctor check twice**
  - Impact: Low
  - Area: UX
  - Where: `src/speakloop/cli/doctor.py:468-484` (`run`) + `:449` (`_render_rich`)
  - What & why: In the non-JSON path, `run()` first prints one plain `[STATUS] Section: label — detail → remediation` line per check (`:475-480`) and then immediately renders a full rich Table of the same rows via `_render_rich(rows, Console(width=200, force_terminal=False))`. A healthy environment has ~30 checks, so the user sees the same ~30 rows twice back-to-back — once as flat lines, once as a fixed-200-column table that wraps awkwardly in an 80-column terminal. It reads as a bug. (The `:474` comment documents this as intentional, so it's a judgment-call polish, not a defect.)
  - How to do it: Pick one representation per context: render the rich Table sized to the actual terminal (let rich fold the Remediation column) for interactive use, and emit the flat untruncated lines only when stdout is not a TTY (scripting) — or at minimum drop the hardcoded `width=200`. Leave `--json` untouched.
  - Effort: Small

- [ ] **IMP-041 — Label the consent disk figures GiB (or divide by decimal units)**
  - Impact: Low
  - Area: UX
  - Where: `src/speakloop/installer/consent.py:14` (`_human_size`)
  - What & why: `_human_size` divides by binary powers (`1<<30`, `1<<20`, `1<<10`) but labels the result GB/MB/KB. On the consent screen — the one place the user decides whether to spend gigabytes — an 8 GiB total renders as "8.0 GB", overstating relative to decimal GB and to the free space the OS reports.
  - How to do it: Relabel units to GiB/MiB/KiB to match the binary divisors, or switch divisors to `1e9`/`1e6`/`1e3` to match the GB label; pick whichever matches the mixed "GiB"/"GB" comments on `manifest.expected_size_bytes` and stays consistent with the `DownloadColumn` units shown during transfer.
  - Effort: Small

- [ ] **IMP-042 — Show friendly, direction-aware metric labels in the trends dashboard**
  - Impact: Low
  - Area: UX
  - Where: `src/speakloop/trends/renderer.py:34-46` (metric table build)
  - What & why: The "Fluency metrics (attempt 3)" table renders the raw `METRIC_KEYS` strings as the visible Metric column, so users see internal snake_case identifiers — `speech_rate_wpm`, `filler_density_per_100_words`, `pauses_count`, `mean_pause_ms`, `self_corrections_count` — as row labels. Separately the delta column (`f"{delta:+.1f}"`) carries no direction meaning: for filler density / pauses / self-corrections (higher is worse) a `+2.0` reads like improvement but is a regression. The debrief renderer already models friendly labels; the trends dashboard is the one surface still leaking internal identifiers.
  - How to do it: Add a small `METRIC_LABELS` map (key → human label) plus a per-metric `higher_is_better` flag; render the label instead of the raw key, and annotate the delta based on whether it moved in the better direction. Keep `METRIC_KEYS` as the single source for ordering.
  - Effort: Small

- [ ] **IMP-043 — Add a cross-parser agreement test for the two frontmatter readers**
  - Impact: Low
  - Area: Testing
  - Where: `src/speakloop/trends/reader.py:60` (third-party `frontmatter.load`) vs `feedback/frontmatter.py:317` (custom `_FENCE_RE` split)
  - What & why: Reports written by `feedback.frontmatter.dump` are read back by **two** parsers: the custom `feedback.frontmatter.parse` (rebuild/resume/debrief) and the third-party `python-frontmatter` `frontmatter.load` (`trends.reader`). The BUG-001 fence-anchoring fix — a `---` line inside a block-scalar `question`/`ideal_answer` must not truncate the parse — is hardened and regression-tested only on the custom parser. No test pins that the trends reader stays consistent, so a future `dump` change or a `python-frontmatter`/PyYAML bump could silently diverge and drop grammar rows from the trends dashboard only.
  - How to do it: Add one integration test that dumps a report containing a `---` line inside `question` and `ideal_answer`, then asserts **both** `feedback.frontmatter.parse` and `trends.reader.read_reports` recover the same `schema_version`/`attempts`/`grammar_patterns` (and that `read_reports` does not put it in `.skipped`). Cheap insurance that both readers honor the fence invariant.
  - Effort: Small

- [ ] **IMP-044 — Replace the tautological `assert ... or True` in the gate test**
  - Impact: Low
  - Area: Testing
  - Where: `tests/unit/pronunciation/test_gate.py:59` (`test_gate_never_imports_the_model`)
  - What & why: Line 59 is `assert "speakloop.pronunciation.wav2vec2_engine" not in sys.modules or True` — the `or True` makes it unconditionally true, so the test asserts nothing and would stay green even if `assess_safety` DID import the ~1.3 GB scorer. The test name promises it guards the RAM/engine gate against loading the model; the trailing comment (`:60`) concedes it is "informational". A misleading green that inflates perceived coverage of a constitution-critical import-isolation guarantee. (Ruff SIM222 already flags it — see IMP-004/IMP-020 for gating lint.)
  - How to do it: Drop the `or True` (`assert "…wav2vec2_engine" not in sys.modules`, plus torch/transformers), or — since the comment concedes the hard guarantee lives in `test_engine_import_isolation.py` — delete this stub. If keeping a real check, verify in a fresh subprocess (as `test_help_without_models.py` does) rather than an unreliable in-process `sys.modules` snapshot.
  - Effort: Small

- [ ] **IMP-045 — Add a retry `not_captured` test to close the drill_runner retry-outcome matrix**
  - Impact: Low
  - Area: Testing
  - Where: `src/speakloop/pronunciation/drill_runner.py:434-436` (retry `r_status=="not_captured"` → `outcome="not_captured"`) + `tests/unit/pronunciation/test_drill_runner*.py`
  - What & why: In `run_drill_item`'s bounded retry, three of four outcomes are pinned by tests (`improved`, `still_off`, `error` — the last has a dedicated test proving it isn't mislabelled, per BUG-004). The fourth, a retry returning `not_captured` (`:434-436`, which prints "not captured — moving on"), has no test. Given the care 017 took to keep each retry outcome distinct, this branch deserves the same pin so a refactor can't silently fold it into `still_off`.
  - How to do it: Add a scorer that flags on attempt 1 then returns `status="not_captured"` on retry (mirror `_FlagThenErrorScorer`), run interactively with two keypresses, and assert `item["retry"]["outcome"] == "not_captured"` and the "not captured — moving on" line appears while "Still a little off" does not.
  - Effort: Small

---

## Coverage note

**Diagnostics run (read-only):** `uv run ruff check .` (95 findings total — 14 in `src/`, all
style-category; the rest in `tests/`, incl. the SIM222 tautology behind IMP-044), `uv run ruff check
src/ --statistics`, `uv run pytest` (**866 passed, 3 skipped** — the skips are local-recording repro
gates needing user audio fixtures), and targeted `git`/`od`/`grep` checks for the tooling and
`.gitignore` findings. No type-checker or CI exists to run (that absence is itself IMP-004/IMP-020).

**How this review was produced:** nine reviewers covered the codebase by module-cluster and by
dimension — sessions core, cli, feedback, pronunciation, llm+analysis, installer/asr/tts/audio,
data/store/debrief, the test suite, and tooling/docs — and **every** candidate finding was
re-opened and adversarially verified against the actual source by a second agent (misreads were
caught and corrected; e.g. an initial "resume is silently always-serial" claim and a "no test
exercises the narrative fallback" claim were both refuted during verification and the affected items
re-scoped). The four **High** items (IMP-001, IMP-002, IMP-003, IMP-004) plus IMP-012 and the two
duplicate-pair merges (IMP-021, IMP-044) were additionally confirmed by hand by the lead against the
cited code.

**Reviewed fully:** all 20 `src/speakloop/` modules were opened and read at the function level; the
two largest files (`sessions/coordinator.py` 1463 lines, `cli/practice.py` 967) were traced in
detail; the test suite structure, `pyproject.toml`, `.gitignore`, and the root docs (`CLAUDE.md`,
`README.md`, `AI_CONTEXT.md`, the two `*_REPORT.md`) were inspected. `bug.md`'s five resolved
functional defects were read and deliberately excluded (not re-listed).

**Not exhaustively line-audited:** the thin engine-wrapper internals that call third-party model
packages (`llm/qwen_engine.py`, `asr/whisper_mlx_engine.py` model-call bodies, `tts/kokoro_engine.py`,
`pronunciation/wav2vec2_engine.py` tensor math) were read at the interface level but not driven
against live models, since this pass was read-only and the default suite excludes the `live_*`
markers; runtime behavior of those packages (e.g. an `mlx_lm` API drift) is precisely the gap IMP-021
targets. Deep multi-file dataflow through the full `coordinator` state machine was traced along the
analysis/coverage/drill/abort paths rather than every branch.

**No source file was modified; the only file created is this `improvement.md`.**
