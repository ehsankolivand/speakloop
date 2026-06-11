# Adversarial context-accuracy review — 014 (2026-06-11)

One reviewer subagent attacked every rewritten context file (root + 19 modules +
2 rules files), spot-checking file:line citations, signatures, constants, counts,
and ALWAYS/NEVER/ONLY claims against the code. ~180 tool calls.

## Findings → fixes (all applied and re-verified by the orchestrator)

| # | File | Finding | Severity | Fix |
|---|---|---|---|---|
| 1 | trends/CLAUDE.md | `format_series` documented with `window=5` default; actual default is `window=3` (`aggregator.py:40`); the renderer overrides with 5 (`renderer.py:76`) | HIGH | Default corrected to 3; renderer override noted |
| 2 | coverage/CLAUDE.md | "`MAX_POINTS=7` (line 72)" ambiguous — defined at `keypoints.py:22`, enforced at `:72` | LOW | Citation split: defined :22, enforced :72 |
| 3 | .claude/rules/llm-calls.md | `check_artifact (consistency.py:42-44)` cited prompt lines as if the definition | LOW | Reworded: defined :34; ideal_answer enters prompt at :42-44 |
| 4 | store/CLAUDE.md | Schedule-advance citations pointed at imports (`coordinator.py:1227`, `resume.py:176`) not the `next_due` calls | LOW | Corrected to `:1231` / `:183` (re-verified firsthand) |
| 5 | srs/CLAUDE.md | `resume.py:145,176` off by 2 (grade call `:147`, advance `:183`) | LOW | Corrected (re-verified firsthand) |

## Clean (no findings)

Root CLAUDE.md (all citations + dependency table confirmed against an import
scan), asr, audio, cli, config, content, debrief, feedback, installer,
interviewer, llm, metrics, sessions, triage, tts, warmup, .claude/rules/testing.md.

## Unconfirmed-suspicious items resolved

- `report_builder.py:388-395` cites the coaching-insertion tail, which is exactly
  what the sentence describes (order grammar→coaching→transcripts) — kept.
- `markdown_writer.py:42` cites the primary-path construction; collision suffixes
  at :46-50 are described in feedback/CLAUDE.md — kept.
- `testing.md` names research.md §4 as the O9 owner record — that file exists and
  contains the assignment — kept.

Result: zero known stale claims remain in the shipped context layer.
