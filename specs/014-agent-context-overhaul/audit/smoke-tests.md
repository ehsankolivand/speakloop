# Smoke tests + memory verification — 014 (2026-06-11)

Six fresh subagents, each given ONLY the task text. Graded on whether the new
context layer alone routed them to the correct files and rules.

**Harness caveat (recorded honestly):** the Agent tool injects the *parent
session's* snapshot of root CLAUDE.md into subagents. SM4/SM5 initially answered
from that stale snapshot with zero tool uses; both were re-run with an explicit
"read the context files from disk" instruction, which is the valid test of the
new layer. SM1/SM3/SM6 read the new files from disk unprompted.

| # | Task | Verdict | Evidence |
|---|---|---|---|
| SM1 | Add a new LLM analysis call — where + rules | **PASS** | Routed to `Runners` (coordinator.py:40-62), `_build_runners` (practice.py:530), `CLAUDE_TIER_MAP`, `.claude/rules/llm-calls.md` O7+O8, feedback `_extract_json` ladder (O4), sessions O6 purity + main-thread store writes, per-class `parallel_safe` convention, additive frontmatter. All owners correct. |
| SM2 | Add a session-report frontmatter key safely | **PASS** | Routed to `feedback/frontmatter.py` Session dataclass + dump()/parse() patterns, `SCHEMA_VERSION=1` at frontmatter.py:11 never bumped, emit-only-when-present, unknown-keys-ignored forward compat. (One quoted citation — "frontmatter.py:20,40,91" — came from the stale injected snapshot, but the disk-read answer used the corrected facts.) |
| SM3 | Engine selection precedence | **PASS** | `--engine` flag → `--cloud` alias → `loop.yaml engine:` → `"local"`; `resolve_engine_choice` practice.py:265-289 reused by resume.py:86; `EngineSelectionError` exit 2 on conflict; `VALID_ENGINES` loop_config.py. Cited new cli/CLAUDE.md + config/CLAUDE.md. |
| SM4 (rerun) | What must tests never do | **PASS** | Routed to `.claude/rules/testing.md` as the owner: no real claude binary/mic/keyboard/live models; FakeKeyReader/NullKeyReader, fake `runner` for ClaudeCodeEngine, fake `record_fn`, cached fixtures; equivalence/import-isolation/line-budget gates; root never-do pointer confirmed one-hop. |
| SM5 (rerun) | Add a new CLI flag to practice | **PASS** | Routed to `cli/main.py` practice_cmd + `cli/practice.py` run(); deferred imports for `--help`; `--cloud`/`--engine` conflict semantics; loop.yaml silent-default convention; additive frontmatter; anti-rot "update cli/CLAUDE.md in the same commit". |
| SM6 | TTS cache location + invalidation | **PASS** | `~/.speakloop/cache/tts/<sha256>.wav`, `SPEAKLOOP_TTS_CACHE_DIR` override (paths.py:127-131), content-address key (speed folded only ≠1.0), no time-based invalidation, `prune()` 512MB LRU after synthesize with keep-guard, `purge()` deletes all. Cited new tts/CLAUDE.md + config/CLAUDE.md. |

## Memory loading verification (T027)

Per the documented loading rules (doc/research_context_engineering.md §7, §13):

- Launch-loaded: root `CLAUDE.md` (171 lines) and the user-scope
  `~/.claude/CLAUDE.md` (exists, personal, out of repo scope). No
  `CLAUDE.local.md`, no `./.claude/CLAUDE.md` — nothing unexpected loads.
- Path-scoped: `.claude/rules/testing.md` (`paths: ["tests/**"]`) and
  `.claude/rules/llm-calls.md` (paths over the 5 LLM-caller modules) load only
  for matching files — frontmatter verified present and well-formed.
- On-demand: 19 module CLAUDE.md files (none loaded at launch; subdirectory rule).
- `@`-import count in root: **0** (one-hop plain-path pointers only).
- Interactive `/memory` could not be invoked from this autonomous run; the above
  enumeration per documented loading rules is the recorded equivalent (spec
  assumption 5). Run `/memory` interactively to double-check; expected listing:
  project `CLAUDE.md` + user `~/.claude/CLAUDE.md` (+ rules files when editing
  matching paths).
