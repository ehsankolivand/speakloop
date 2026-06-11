# Claim-Audit Table — every context file vs. current code (2026-06-11)

Method: 7 parallel read-only audit agents, each reading the context file AND the cited
module code in the current working tree (branch `014-agent-context-overhaul`, parent
`b611f8d`). Disputed findings re-verified by the orchestrator firsthand. Verdicts:
**accurate** (claim matches code), **stale** (contradicted/outdated — fix or delete),
**unverifiable** (no code evidence — delete or mark explicitly).

Baseline suite: 696 passed, 3 skipped, 2 deselected.

## Summary

| Context file | Claims audited | Accurate | Stale | Unverifiable |
|---|---|---|---|---|
| CLAUDE.md (root) | 53 | 38 | 12 | 3 |
| README.md | 23 | 15 | 4 | 4 |
| src/speakloop/llm/CLAUDE.md | 28 | 27 | 1 | 0 |
| src/speakloop/cli/CLAUDE.md | 21 | 15 | 6 | 0 |
| src/speakloop/sessions/CLAUDE.md | 21 | 15 | 6 | 0 |
| src/speakloop/audio/CLAUDE.md | 13 | 11 | 1 | 1 |
| src/speakloop/asr/CLAUDE.md | 18 | 14 | 4 | 0 |
| src/speakloop/feedback/CLAUDE.md | 49 | 46 | 3 | 1 |
| src/speakloop/metrics/CLAUDE.md | 14 | 9 | 5 | 0 |
| src/speakloop/trends/CLAUDE.md | 12 | 9 | 3 | 0 |
| src/speakloop/triage/CLAUDE.md | 16 | 16 | 0 | 0 |
| src/speakloop/coverage/CLAUDE.md | 15 | 15 | 0 | 0 |
| src/speakloop/interviewer/CLAUDE.md | 13 | 12 | 1 | 0 |
| src/speakloop/srs/CLAUDE.md | 18 | 17 | 1 | 0 |
| src/speakloop/store/CLAUDE.md | 18 | 14 | 4 | 0 |
| src/speakloop/warmup/CLAUDE.md | 14 | 14 | 0 | 0 |
| src/speakloop/tts/CLAUDE.md | 9 | 8 | 1 | 0 |
| src/speakloop/installer/CLAUDE.md | 12 | 12 | 0 | 0 |
| src/speakloop/config/CLAUDE.md | 11 | 7 | 4 | 0 |
| src/speakloop/content/CLAUDE.md | 9 | 9 | 0 | 0 |
| src/speakloop/debrief/CLAUDE.md | 11 | 9 | 2 | 0 |

## Stale claims (every one must be fixed or deleted in implementation)

### Root CLAUDE.md

| # | Claim | Evidence | Fix |
|---|---|---|---|
| R1 | "Active feature: 012-responsive-session-flow" | branch history: 013 merged (`b611f8d`), 014 active | SPECKIT block → 014 active; 012/013 prior |
| R2 | keyboard.py "consolidating `cli/practice._cbreak_read`" | `cli/practice.py:118` `_cbreak_read` still exists (listen loop); `debrief/menu.py:34` `_cbreak_read_key` | Rephrase: keyboard.py is the session-path key reader; listen loop + debrief keep their own cbreak readers |
| R3 | torchaudio cap at "`pyproject.toml:29`" | actual `pyproject.toml:34` | Fix line number |
| R4 | "Thirteen single-responsibility modules" | 19 modules with CLAUDE.md exist | "Nineteen" |
| R5 | "cli → 9 modules" | import scan: cli imports 16 internal modules | Update count |
| R6 | "sessions → 6" | coordinator imports 12 internal modules | Update count |
| R7 | sessions deps row missing coverage/srs/store/trends/triage/warmup | `coordinator.py:22-33` + conditional imports | Update table row |
| R8 | coverage deps row missing config | `coverage/prompts.py:11` | Update table row |
| R9 | store row "feedback (+srs)" | no `speakloop.srs` import anywhere in store/ | Remove "+srs" (srs→store, not reverse) |
| R10 | `feedback/frontmatter.py:20,40,91` for schema_version | `SCHEMA_VERSION = 1` is at `frontmatter.py:11` | Fix citation |
| R11 | Report names "`YYYY-MM-DD-qXX.md`" | `markdown_writer.py:42`: `YYYY-MM-DD-<question_id>.md`, arbitrary id | Fix pattern |
| R12 | Pointers "specs/001–specs/006" | specs exist through 014 | Update range |
| R13 (unverifiable) | "torchaudio ≥2.11 moves decoding to torchcodec" | external fact; commit `21dfb86` is in-repo evidence | Keep, cite the commit as evidence |
| R14 (unverifiable) | downstream claims of 012 SPECKIT prose (measured timings etc.) | history, not current-code claims | Collapse into one-line prior-feature pointer |

### README.md (factual staleness only)

| # | Claim | Evidence | Fix |
|---|---|---|---|
| D1 | Reports named "`YYYY-MM-DD-qXX.md`" | `markdown_writer.py:42` | Fix pattern |
| D2 | invite to "add Persian-L1 grammar patterns" | catalog retired (006); no catalog files exist | Reword to current free-form prompt reality |
| D3 | "silero-vad dependency is version-pinned" | `pyproject.toml:32` is `>=5.1` lower bound | Say "lower-bounded; exact pin via uv.lock" |
| D4 | empty `## License` heading; content after "Found this useful?" | README structure | Move license line under its heading |

### src/speakloop/llm/CLAUDE.md

| # | Claim | Evidence | Fix |
|---|---|---|---|
| L1 | `parallel_safe` declared on the `LLMEngine` Protocol | `interface.py` Protocol body has no `parallel_safe`; per-class attr only (`qwen_engine.py:47`, `openrouter_engine.py:41`, `claude_code_engine.py:183`) | State it is a per-class convention; new engines must declare it manually |

### src/speakloop/cli/CLAUDE.md

| # | Claim | Evidence | Fix |
|---|---|---|---|
| C1 | "warms the output device" (unconditional) | `practice.py:376-377` — only when `key_reader.raw_capable` | Add condition |
| C2 | doctor Cloud section item list incomplete | `doctor.py:117-164` has coach-prompt row; doctor also has Interview Loop + Claude Code sections (011) | Update description |
| C3 | "debrief imported function-local in practice.py:290" | actual `practice.py:393` | Fix line |
| C4 | file map lists 4 files | `resume.py`, `today.py`, `rebuild.py` exist | Add to map |
| C5 | (omission treated as stale claim of completeness) public interface lacks `today`/`rebuild`/`resume` commands | `main.py:149,161,173` | Add |
| C6 | consolidation implication (same as R2) | `practice.py:118` | Same fix as R2 |

### src/speakloop/sessions/CLAUDE.md

| # | Claim | Evidence | Fix |
|---|---|---|---|
| S1 | `q`=quit implied to work in-session | `q` only wired in pre-session listen loop (`cli/practice.py`); not handled by `_spawn_key_poller`/`_play_prompt` | Document the actual key surface per stage |
| S2 | `run_group` description omits the ≤1-job serial fallback and `min(concurrency, len(jobs))` cap | `analysis.py:48-73` | Refine |
| S3 | `abort` "exit 130" | no `sys.exit(130)` anywhere; handler cleans `*.tmp` + sets `abort_event` (`abort.py:26-36`) | Rephrase to actual behavior |
| S4 | abort file-map "exits 130" | same | same |
| S5 | deps list `asr, audio, config, content, feedback, metrics` | coordinator also imports triage (module-level, `coordinator.py:33`) + coverage/srs/store/trends/warmup | Update |
| S6 | "ASR worker pool `max_workers=1`" | `_BackgroundAsr` is a queue-fed single daemon thread, not a pool (`coordinator.py:239-285`) | Rephrase ("single daemon worker thread; never 2 Whisper jobs") |
| S7 | keyboard consolidation claim (same as R2) | `keyboard.py:2-6` docstring overstates | Rephrase |

### src/speakloop/audio/CLAUDE.md

| # | Claim | Evidence | Fix |
|---|---|---|---|
| A1 | playback.py file-map entry covers only `play()` | `play_interruptible`, `warm_output_device`, `_start_nonblocking`, recovery helpers all live there | Update entry |
| A2 (new trap) | silent `scipy` dependency | `playback.py:66` `from scipy.signal import resample_poly`; scipy NOT in pyproject.toml | Document as divergence/trap (no src change allowed in 014) |

### src/speakloop/asr/CLAUDE.md

| # | Claim | Evidence | Fix |
|---|---|---|---|
| AS1 | mlx_whisper import "lines 78, 102, 118" | actual 84, 108, 124 | Fix or drop line numbers |
| AS2 | silero_vad "line 81" | actual `vad.py:82` | Fix or drop |
| AS3 | `pyproject.toml:29` for torchaudio | actual :34 | Fix (point to root owner) |
| AS4 | consumers "feedback, metrics, sessions" | also triage (`hallucination.py:22`), coverage (`scoring.py:14`), interviewer (`followups.py:20`), cli (`resume.py:105`) | Update |

### src/speakloop/feedback/CLAUDE.md

| # | Claim | Evidence | Fix |
|---|---|---|---|
| F1 | `openrouter_prompt_default.txt` entry carries no 013 note | b611f8d (013) hardened its output-format block | Add 013 note |
| F2 | `to_frontmatter()` described without `analysis_mode`/`analysis_concurrency`/`analysis_wall_seconds` kwargs | `timings.py:69-88` | Update signature |
| F3 | recovery ladder omits 4th rung (json_repair on `{...}` region) | `grammar_analyzer.py:99-137` | Update |
| F4 (unverifiable) | "the caller prints each returned path once" | cli behavior, owned by cli docs | Move/delete |

### src/speakloop/metrics/CLAUDE.md

| # | Claim | Evidence | Fix |
|---|---|---|---|
| M1 | `compute_all(transcript)` omits `vad_regions` kwarg | `__init__.py:6` | Fix signature |
| M2 | `speech_rate.compute` "-> tuple" | returns dict (`speech_rate.py:32-40`) | Fix |
| M3 | `pauses.compute` "-> tuple", omits kwargs | returns dict; `threshold_ms`, `vad_regions` kwargs (`pauses.py:36-52`) | Fix |
| M4 | `fillers.compute` "-> tuple" | returns dict (`fillers.py:46-50`) | Fix |
| M5 | `self_corrections.compute` "-> count" | returns dict (`self_corrections.py:51-52`) | Fix |

### src/speakloop/trends/CLAUDE.md

| # | Claim | Evidence | Fix |
|---|---|---|---|
| T1 | `read_reports -> list[Report]` | returns `ReadResult(reports, skipped)` (`reader.py:26-28,46-87`) | Fix |
| T2 | `render(summary) -> rich.Console output` | returns `str`; optional `console=` kwarg (`renderer.py:13`) | Fix |
| T3 | "no internal module deps" phrasing misleading + no 010 additions (pattern_series, 4th table) | `aggregator.py:37`, `renderer.py:67-77` | Fix + add 010 facts |

### src/speakloop/interviewer/CLAUDE.md

| # | Claim | Evidence | Fix |
|---|---|---|---|
| I1 | raises only `LLMEngineError` | `ValueError` from `_extract_json` also propagates (`followups.py:77`); coordinator wraps broadly (`coordinator.py:448`) | Document both |
| I2 (missing) | 012 reorder: follow-ups fire BEFORE heavy analysis | `coordinator.py:1048-1069` | Add |

### src/speakloop/srs/CLAUDE.md

| # | Claim | Evidence | Fix |
|---|---|---|---|
| SR1 | consumers omit `cli/resume.py` | `resume.py:145,176` | Add |

### src/speakloop/store/CLAUDE.md

| # | Claim | Evidence | Fix |
|---|---|---|---|
| ST1 | "In P2 it also uses `speakloop.srs` for schedule replay" | no srs import in store/; replay lives in `coordinator.py:1227` + `resume.py:176`; `rebuild.py:69` sets `next_due = iso_date` placeholder | Fix: rebuild does NOT restore next_due; schedule advance happens at session end |
| ST2 | consumers omit resume | `resume.py:177-184` | Add |
| ST3 | "follow-up grammar … still counts" (rebuild comment claim) | `rebuild.py:52` iterates only `session.grammar_patterns`; follow-up patterns NOT folded | Fix to actual behavior |
| ST4 | atomic-write description omits fsync | `io.py:46` | Minor fix |

### src/speakloop/tts/CLAUDE.md

| # | Claim | Evidence | Fix |
|---|---|---|---|
| TT1 | kokoro_mlx import "(line 41)" | actual `kokoro_engine.py:52` | Fix or drop line |

### src/speakloop/config/CLAUDE.md

| # | Claim | Evidence | Fix |
|---|---|---|---|
| CF1 | "Standard library only" | `loop_config.py:13` imports pyyaml | Qualify per-file |
| CF2 | file map lists only `paths.py` | `loop_config.py` exists with all loop.yaml keys | Add full entry + key table |
| CF3 | consumers "cli, feedback, installer, sessions, tts" | also coverage, interviewer, llm, triage, warmup | Update |
| CF4 | "no I/O beyond mkdir -p" | `loop_config.py:61` reads YAML | Qualify |

### src/speakloop/debrief/CLAUDE.md

| # | Claim | Evidence | Fix |
|---|---|---|---|
| DB1 | `run()` signature missing `console=`, `read_key=` injectables; tts_engine/play_fn defaults | `debrief.py:30-39` | Fix signature |
| DB2 | "practice.py:290" import citation | actual :393 | Fix |

## Accurate-claim evidence index (per file, abbreviated)

Full row-level evidence was gathered by the audit agents; load-bearing accurate anchors:

- **llm**: Protocol `interface.py:15`; errors `interface.py:33`, `claude_code_engine.py:93-114`; flags/constants `claude_code_engine.py:37-54,199-212`; `is_error` keying `:58,258`; env strip set (6 vars) `:63-70`; `--safe-mode` rationale `:47-50`; tier/timeout defaults `config/loop_config.py:23-24`, `claude_code_engine.py:72`; Qwen sampler `qwen_engine.py:110-116`; think-strip `:35,149-165`; stop truncation `:49-52,150-165`; OpenRouter urllib `openrouter_engine.py:17-18`, auth `:73,151-157`, token precedence `openrouter_credentials.py:24-43` (0600 `:54-57`).
- **sessions**: `run_session` params `coordinator.py:893-897`; coach degradation `:824-831`; KeyReader family `keyboard.py:49-213`; `_BackgroundAsr` `coordinator.py:239-285`; main-thread store writes `:1110-1116`; follow-up reorder `:1048-1069`; budgets `FOLLOWUP_BUDGET_SECONDS=60`, `WARMUP_ITEM_BUDGET_SECONDS=20` (`coordinator.py:538`); name-keyed slots `analysis.py:61-73`; equivalence gate `tests/integration/test_analysis_equivalence.py:133,179`.
- **audio**: `play_interruptible` `playback.py:21,164-206` (poll 0.03s); `warm_output_device` `:122-132`; recorder early-exit `recorder.py:25-89`; lazy abort import `recorder.py:44`.
- **asr**: engine ownership — `mlx_whisper` only in `whisper_mlx_engine.py` (84,108,124), `silero_vad` only `vad.py:82`, `parakeet_mlx` only `parakeet_engine.py:48`; fallback `selection.py:57-73`; guards `tests/unit/asr/test_engine_import_isolation.py`, `tests/integration/test_help_without_models.py:27`.
- **feedback**: `SCHEMA_VERSION = 1` `frontmatter.py:11`; coaching body-only `frontmatter.py:108-118`; report order `report_builder.py:388-395`; coach excludes ideal answer `coach.py:14-16,63-68`; recovery ladder `grammar_analyzer.py:89-137`; V1/V2/V3 `:203-208`; sort `:247-249`; temperature `:273-279`; timings `timings.py:19-105`; atomic write `markdown_writer.py:10-29`; collision suffix `:35-50`.
- **triage/coverage/interviewer/warmup/srs/store**: see agent tables; all signatures verified at `hallucination.py:98,133`, `mishearing.py:25,46-47`, `consistency.py:34,68`, `keypoints.py:30,43`, `scoring.py:32-36,65,87`, `content_errors.py:13-29`, `followups.py:28,47-53,60-61,86`, `drill.py:21-86`, `grade.py:17,39-69`, `schedule.py:25-60`, `queue.py:23-100`, `model.py:16-81`, `io.py:20-51`, `rebuild.py:37-77`.
- **tts/installer/config/content/debrief**: cache key `tts/cache.py:17-26`; prune wired `kokoro_engine.py:101`; aria2c flags `downloader.py:46-53,182-191`; token precedence `tokens.py:37-51`; Q&A precedence `paths.py:103-124`; loop.yaml key map `loop_config.py:58-91` (see research.md); content schema `schema.py:14-44`, loader errors `loader.py:16-52`; debrief menu `menu.py:23-28`.

## Cross-cutting verified facts (new since the context layer was written)

1. **ideal_answer boundary** (enforced structurally, no runtime guard): excluded from `grammar_analyzer.analyze` (`grammar_analyzer.py:286`), `coach.build_user_prompt` (`coach.py:63-68`), `narrative.py`, `coherence.py`, `followups.generate_followups` (`followups.py:47-53`), `mishearing.detect_mishearings` (`mishearing.py:25`). Legitimately passed to `keypoints.derive_key_points` (`keypoints.py:58-60`), `scoring.score_coverage` (`scoring.py:84`), `consistency.check_artifact` (`consistency.py:42-44`).
2. **loop.yaml keys** all parsed in `config/loop_config.py` `load()`: daily_capacity:66, engine:71-73, claude_timeout_seconds:75, analysis_concurrency:79, autoplay_ideal_answer:82-84, warmup_enabled:87, followups_enabled:88, claude_fast_model:90, claude_strong_model:91. Missing/malformed file → silent defaults (`:58-65`).
3. **readchar** declared `pyproject.toml:24` but never imported in src/ (phantom dep, pre-dates 012).
4. **scipy** imported `audio/playback.py:66` (resample fallback) but NOT declared — transitive-only.
5. **Feature 013** = commit `b611f8d`: hardened `feedback/openrouter_prompt_default.txt` output-format block; no spec dir.
6. **CLAUDE_TIER_MAP** `cli/practice.py:524-527`; `resolve_engine_choice` + `EngineSelectionError` `practice.py:265-289` (used by `resume.py:86`); precedence `--engine` flag → loop.yaml `engine:` → `local`; `--cloud` aliases openrouter, conflict raises.
7. **MIN_POINTS = 5** (`keypoints.py:21`) is prompt-soft, not code-enforced; only MAX_POINTS=7 capped (`:72`).
