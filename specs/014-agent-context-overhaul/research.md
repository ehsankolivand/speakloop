# Phase 0 Research — Agent Context Overhaul (014)

**Date**: 2026-06-11 · **Branch**: `014-agent-context-overhaul`
**Empirical inputs**: full read of `doc/research_context_engineering.md`; 7 parallel
read-only code audits (see `audit/claim-audit.md`); line/token inventory below.

## 1. Binding checklist extracted from doc/research_context_engineering.md

Every item below is a requirement for this feature (guide section in parens).

- [ ] B1 Smallest possible set of high-signal tokens; cut anything that does not earn its place (§6.1).
- [ ] B2 Root CLAUDE.md ≤200 lines (docs target; §12 "files over 200 lines … may reduce adherence"); 400 is a hard ceiling never approached.
- [ ] B3 Root anatomy exactly: 2–3 sentence overview · tech stack fixed list · module layout + dependency rules · exact build/test commands · conventions (3–7 concrete rules per area) · known traps · never-do list · pointers (§9).
- [ ] B4 Pointers over copies; long detail lives elsewhere and loads just-in-time (§6.3, §9).
- [ ] B5 Nested CLAUDE.md files load on demand (NOT at launch, NOT re-injected after /compact) → rules that must never be lost live at root (§7, §14).
- [ ] B6 `.claude/rules/*.md` with `paths` frontmatter for path-scoped rules that should load only for matching files (§12, §13, §14).
- [ ] B7 No rule duplicated across files — duplication causes context clash; one source of truth, others reference (§5, §12).
- [ ] B8 Concrete, verifiable rules only; no vague rules ("write clean code") (§12).
- [ ] B9 Markdown headings as boundaries between instruction sections (§6.4).
- [ ] B10 `<!-- … -->` block comments are stripped before injection — usable for human-only notes at zero token cost (§7).
- [ ] B11 `@`-imports load at launch (defeat on-demand) and max 5 hops — this feature uses none (clarification Q4: one-hop plain path references) (§7, §14).
- [ ] B12 Stable content cacheable: don't churn root CLAUDE.md mid-session; edit between sessions (§15).
- [ ] B13 Maintenance is event-driven: a PR that changes a convention updates the owning file in the same commit (§11, §14 — basis of the anti-rot rule).
- [ ] B14 Match rule lifetime to tool scope (project/every-session → root; path-scoped → rules/; on-demand module-local → nested) (§13).

## 2. Inventory — context artifacts (before)

Token counts are chars/4 estimates.

| Artifact | Lines | ~Tokens | Load trigger |
|---|---|---|---|
| CLAUDE.md (root) | **298** | 5286 | every session ← **over the 200-line budget** |
| src/speakloop/asr/CLAUDE.md | 68 | 832 | on-demand |
| src/speakloop/audio/CLAUDE.md | 42 | 399 | on-demand |
| src/speakloop/cli/CLAUDE.md | 67 | 899 | on-demand |
| src/speakloop/config/CLAUDE.md | 52 | 480 | on-demand |
| src/speakloop/content/CLAUDE.md | 42 | 335 | on-demand |
| src/speakloop/coverage/CLAUDE.md | 50 | 570 | on-demand |
| src/speakloop/debrief/CLAUDE.md | 53 | 526 | on-demand |
| src/speakloop/feedback/CLAUDE.md | 104 | 1649 | on-demand |
| src/speakloop/installer/CLAUDE.md | 105 | 1505 | on-demand |
| src/speakloop/interviewer/CLAUDE.md | 49 | 541 | on-demand |
| src/speakloop/llm/CLAUDE.md | 117 | 1884 | on-demand |
| src/speakloop/metrics/CLAUDE.md | 42 | 313 | on-demand |
| src/speakloop/sessions/CLAUDE.md | 73 | 1050 | on-demand |
| src/speakloop/srs/CLAUDE.md | 46 | 473 | on-demand |
| src/speakloop/store/CLAUDE.md | 57 | 617 | on-demand |
| src/speakloop/trends/CLAUDE.md | 36 | 275 | on-demand |
| src/speakloop/triage/CLAUDE.md | 67 | 840 | on-demand |
| src/speakloop/tts/CLAUDE.md | 48 | 519 | on-demand |
| src/speakloop/warmup/CLAUDE.md | 44 | 427 | on-demand |
| .claude/rules/ | — | — | **does not exist** |
| .claude/skills/speckit-*/SKILL.md ×14 | 49–372 | ~28 500 total | per-skill invocation (tooling, NOT project context — out of audit scope, untouched) |
| .claude/settings.local.json | 30 | — | harness config (untouched) |
| .specify/memory/constitution.md | 305 | 3726 | referenced, loads on demand |
| README.md | 344 | 4084 | human-facing |
| CHANGELOG.md | 452 | 8074 | human-facing |
| doc/*.md ×8 | 81–583 | ~59 200 total | on-demand pointers |

**Launch footprint (root CLAUDE.md only): ~5 286 tokens / 298 lines.** Target after:
≤200 lines, ≈3 500 tokens.

## 3. Claim audit

Full table: `audit/claim-audit.md`. Headline: **375 claims audited, 332 accurate,
58 stale + 9 unverifiable across 18 of 21 files**. Densest staleness: root (12),
sessions (6+e), cli (6), metrics (5 — every per-metric signature has the wrong
return type), config (4 — `loop_config.py` entirely undocumented), store (4 —
"P2 wired srs into rebuild" never happened).

Decision (per spec edge cases): every stale claim is fixed from code or deleted;
the 9 unverifiable claims are deleted except the torchaudio/torchcodec trap, which
is re-anchored to in-repo evidence (commit `21dfb86` + `pyproject.toml:34`).

## 4. Rule-ownership map (single home per rule)

| Rule | Owner (single home) | Everyone else |
|---|---|---|
| O1 Engine packages imported function-local, each in exactly one wrapper; `--help` loads no models | root CLAUDE.md (traps + never-do) | module files state only their LOCAL fact ("kokoro_mlx lives in kokoro_engine.py only"), no restated rule |
| O2 torchaudio `<2.9` cap (torchcodec crash) | root CLAUDE.md trap (it bites at `pyproject.toml:34`, a root file) | asr/CLAUDE.md one-line pointer |
| O3 Report `schema_version` stays 1; frontmatter keys additive-optional | root CLAUDE.md (cross-module: feedback, store, trends, sessions all touch it) | feedback/store/trends point |
| O4 JSON recovery = `json-repair` ladder via `_extract_json`; no hand-rolled regex; one bounded regenerate | feedback/CLAUDE.md (the ladder lives in grammar_analyzer.py) | root drops detail; triage/coverage/interviewer/warmup say "shared ladder — see feedback" |
| O5 Qwen generation config lives only in `llm/qwen_engine.py`; callers pass intent (`retry`, `temperature`) only | llm/CLAUDE.md | feedback points |
| O6 Serial == concurrent byte-identical report; pure jobs, name-keyed slots, main-thread store writes post-join | sessions/CLAUDE.md (analysis.py + coordinator own it) | root keeps one-line trap pointer; store points |
| O7 `ideal_answer` never enters analytic LLM calls (grammar/coach/narrative/mishearing); legitimately enters keypoints/coverage/consistency | `.claude/rules/llm-calls.md` (cross-cuts feedback, interviewer, triage, coverage) | feedback/coverage files point |
| O8 LLM-caller degradation contract: failures → `LLMEngineError` → per-call `*_error` frontmatter / skip; never crash the session; no auto-fallback between engines | `.claude/rules/llm-calls.md` | module files point |
| O9 Tests never touch the real `claude` binary, microphone, keyboard, or live models; inject fakes (FakeKeyReader, fake runner, fake record_fn); engine tests use cached fixtures | `.claude/rules/testing.md` (paths: tests/**) | root never-do keeps one line; module files point |
| O10 Q&A precedence `--qa-file → ~/.speakloop/qa.yaml → content/questions.yaml`, no auto-copy | config/CLAUDE.md (resolve_qa_file owner) | root drops to pointer |
| O11 Offline-first / no network after model download; English-only; no GUI; uv-only; MIT | constitution (Principles I–III, constraints) | root never-do cites principle numbers in one line each |
| O12 Engine change updates matching `doc/research_*.md` | constitution Principle X | root conventions one line |
| O13 Claude CLI invocation contract (pin 2.1.170, `--safe-mode` not `--bare`, key off `is_error` not `subtype`, env-strip set, subscription billing) | llm/CLAUDE.md | root trap keeps one line + pointer |
| O14 Interval ladder / mastery constants | srs/CLAUDE.md | root module-table row says only "SRS scheduling (pure logic)" |
| O15 Store is a rebuildable cache, never source of truth; STORE_VERSION independent of report schema_version | store/CLAUDE.md | root table row pointer |
| O16 Anti-rot: any behavior-changing commit updates the owning context file in the same commit | constitution (new Development Guideline, MINOR bump) | root never-do one line |
| O17 Every CLAUDE.md ≤200 lines | guard test `tests/integration/test_context_file_budget.py` (executable owner) | root maintenance note one line |
| O18 Module-local invariants (per module: thresholds, constants, signatures, extension points) | each module's own CLAUDE.md | — |

## 5. Decisions

- **D1 Root rewrite shape**: 9 sections per guide anatomy (B3) + SPECKIT block at top
  (harness requirement, kept ≤25 lines: active feature ≤10 lines + one line per prior
  feature 001–013). Maintenance checklist (current §Maintenance, 25 lines) compresses
  to 5 lines; the audit history (D-numbers) is dropped — history lives in specs/005.
  Rationale: B1/B2. Alternative (keep 298-line file, trim lightly) rejected: stays
  over budget, keeps duplicated rules.
- **D2 Module files**: all 19 kept (Constitution Principle IV — spec clarification 6),
  each rewritten to: purpose (1–2 lines) · public interface · local invariants/traps ·
  extension points · pointers. Target ≤70 lines each; everything rediscoverable by
  reading the module's code in <1 min is cut (B1). Stale claims fixed per
  audit/claim-audit.md; missing-coverage items added only where they encode invariants
  or non-obvious behavior (not API listings — those are rediscoverable).
- **D3 Two rules files**: `.claude/rules/testing.md` (paths: `tests/**`) and
  `.claude/rules/llm-calls.md` (paths: the 5 LLM-caller modules). No more — other
  cross-cutting rules are either every-session (root) or single-module (nested) (B14).
- **D4 No @-imports anywhere** (clarification Q4, B11). One-hop pointers.
- **D5 Guard test**: `tests/integration/test_context_file_budget.py`, plain pytest,
  globs `CLAUDE.md` + `**/CLAUDE.md` (git-tracked only), asserts ≤200 lines each.
  Zero new deps. The single permitted code addition (FR-007).
- **D6 Constitution amendment**: add anti-rot rule to Development Guidelines +
  version bump 1.0.0 → 1.1.0 (MINOR: guidance materially expanded) with Sync Impact
  Report update, per Governance procedure.
- **D7 README**: fix the 4 factual stale claims only (D1–D4 in audit); no rewrite.
- **D8 Divergences that need a code fix (out of scope here)** are recorded as explicit
  traps, not silently dropped: phantom `readchar` dep (`pyproject.toml:24`, never
  imported); silent `scipy` import (`audio/playback.py:66`, undeclared); `q`-key not
  wired in-session; `rebuild` does not restore `next_due`. Each gets one trap line in
  the owning file marked "(divergence — code fix pending)".
- **D9 CHANGELOG/specs/doc untouched** except: nothing. Specs are immutable history;
  CHANGELOG is a record. (Spec Out-of-Scope.)
- **D10 .claude/skills** are speckit tooling, not project context: untouched.

## 6. Constitution gates check (Phase 0)

- Session files (`data/sessions/`) untouched: ✓ (docs-only feature).
- `src/` untouched: ✓ (module CLAUDE.md files live under src/ but are documentation;
  no `.py` changes).
- Suite behavior identical: ✓ baseline 696 passed / 3 skipped / 2 deselected; guard
  test adds 1 new passing test (reported separately per spec assumption).
- Principle IV (per-module CLAUDE.md): ✓ all 19 kept.
- Principle XI (smaller agent context = improvement, not regression): ✓ by design.
