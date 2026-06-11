# RETURN REPORT — 014-agent-context-overhaul (2026-06-11)

Autonomous context-engineering sprint. Branch `014-agent-context-overhaul`
(stacked on `013-grammar-json-discipline` @ `b611f8d`). Full spec-kit flow run:
specify → clarify (5 self-answered Q→A) → plan (empirical Phase 0) → tasks (30) →
implement → verify. **All 30 tasks complete. Pushed, NOT merged.**
(The prior 012 report was archived to `specs/012-responsive-session-flow/RETURN_REPORT.md`.)

## 1. Before/after inventory

| File | Lines before → after | ~Tokens before → after |
|---|---|---|
| CLAUDE.md (root) | **298 → 171** | **5286 → 2795** (launch footprint −47%) |
| src/speakloop/asr/CLAUDE.md | 68 → 86 | 832 → 1043 |
| src/speakloop/audio/CLAUDE.md | 42 → 64 | 399 → 764 |
| src/speakloop/cli/CLAUDE.md | 67 → 67 | 899 → 1150 |
| src/speakloop/config/CLAUDE.md | 52 → 80 | 480 → 971 |
| src/speakloop/content/CLAUDE.md | 42 → 67 | 335 → 768 |
| src/speakloop/coverage/CLAUDE.md | 50 → 61 | 570 → 824 |
| src/speakloop/debrief/CLAUDE.md | 53 → 79 | 526 → 1030 |
| src/speakloop/feedback/CLAUDE.md | 104 → 107 | 1649 → 1427 |
| src/speakloop/installer/CLAUDE.md | 105 → 82 | 1505 → 1113 |
| src/speakloop/interviewer/CLAUDE.md | 49 → 61 | 541 → 828 |
| src/speakloop/llm/CLAUDE.md | 117 → 81 | 1884 → 1446 |
| src/speakloop/metrics/CLAUDE.md | 42 → 63 | 313 → 721 |
| src/speakloop/sessions/CLAUDE.md | 73 → 107 | 1050 → 1578 |
| src/speakloop/srs/CLAUDE.md | 46 → 58 | 473 → 714 |
| src/speakloop/store/CLAUDE.md | 57 → 65 | 617 → 816 |
| src/speakloop/trends/CLAUDE.md | 36 → 69 | 275 → 780 |
| src/speakloop/triage/CLAUDE.md | 67 → 65 | 840 → 945 |
| src/speakloop/tts/CLAUDE.md | 48 → 58 | 519 → 674 |
| src/speakloop/warmup/CLAUDE.md | 44 → 68 | 427 → 837 |
| .claude/rules/testing.md | — → 27 | — → 389 (path-scoped, `tests/**`) |
| .claude/rules/llm-calls.md | — → 39 | — → 492 (path-scoped, 5 caller modules) |

Module files grew modestly on purpose: they load on demand only, and the growth is
verified invariants replacing wrong claims (e.g. metrics' five wrong return-type
signatures). Every CLAUDE.md ≤200 lines, enforced by the new guard test. The
always-loaded launch footprint dropped 47%.

## 2. Claim audit

Full table: `specs/014-agent-context-overhaul/audit/claim-audit.md` (375 claims,
file:line evidence per claim). Verdicts: **332 accurate · 58 stale → all fixed ·
9 unverifiable → 8 deleted, 1 (torchaudio/torchcodec) re-anchored to in-repo
evidence (commit `21dfb86` + `pyproject.toml:34`)**. Zero stale claims remain
(adversarial re-check in §6). What was wrong, in headline form: root said 13
modules (19 exist), cli→9 deps (16), sessions→6 (12); all five metrics signatures
had wrong return types; store claimed an srs integration that never shipped;
sessions claimed an `exit 130` no code performs; the "ONE raw-input module"
consolidation claim was false (`cli/practice.py:118`, `debrief/menu.py:34`).

## 3. Rule-ownership map

Authoritative copy: `specs/014-agent-context-overhaul/research.md` §4 (O1–O18).
Root owns every-session rules (engine-import isolation O1, torchaudio cap O2,
schema_version O3). Module files own module-local invariants (Qwen config O5 →
llm; serial==concurrent gate O6 → sessions; JSON ladder O4 → feedback; Q&A
precedence O10 → config; Claude CLI contract O13 → llm; ladder constants O14 →
srs; cache-not-source-of-truth O15 → store). Path-scoped rules own cross-module
contracts (ideal_answer boundary O7 + degradation O8 → `.claude/rules/llm-calls.md`;
test prohibitions O9 → `.claude/rules/testing.md`). The constitution owns the
principles (O11/O12) and the new anti-rot rule (O16, v1.1.0). The guard test owns
the line budget (O17). Pointer chains are one hop; zero `@`-imports.

## 4. Smoke tests + memory loading

Record: `specs/014-agent-context-overhaul/audit/smoke-tests.md`. **6/6 PASS** —
each fresh agent routed to the correct files and rules from the new context alone.
Caveat recorded there: the Agent harness injects the parent session's stale root
snapshot into subagents; SM4/SM5 were re-run with read-from-disk instructions
(their first runs answered from the snapshot with zero tool calls). Memory surface
verified by enumeration: launch = root CLAUDE.md (+ user-scope `~/.claude/CLAUDE.md`);
path-scoped = the two rules files with valid `paths` frontmatter; the 19 module
files load on demand; interactive `/memory` left as a one-command double-check.

## 5. Behavior-change proof + diff scope

- Suite before: **696 passed, 3 skipped, 2 deselected**.
- Suite after: **697 passed, 3 skipped, 2 deselected** — the +1 is exactly the new
  guard test `tests/integration/test_context_file_budget.py`; no existing test
  changed status.
- Diff scope vs. the run's base `b611f8d`: only `*.md`, `.claude/rules/*`,
  `specs/014-agent-context-overhaul/**`, the one guard test,
  `.specify/memory/constitution.md` (tasked amendment), `.specify/feature.json`
  (spec-kit bookkeeping), and the archival `git mv` of the 012 report into its
  spec dir. **Zero `.py` changes under `src/`.**
  (Note: `git diff main...HEAD` shows prior features' files because 010–013 were
  never merged to main; the correct base for this run is `b611f8d`.)

## 6. Adversarial review

Findings + fixes: `specs/014-agent-context-overhaul/audit/adversarial-review.md`.

## 7. Known divergences documented (code fixes pending, out of 014 scope)

- `readchar` declared (`pyproject.toml:24`) but never imported in `src/`.
- `scipy` imported (`audio/playback.py:66`) but never declared (transitive-only).
- `q`-quit not wired during in-session recording/playback (listen loop only).
- `speakloop rebuild` does not restore real `next_due` intervals
  (`store/rebuild.py:69` placeholder); follow-up grammar patterns are not folded
  into the patterns series (`rebuild.py:52`).
- Raw keyboard input not fully consolidated (`cli/practice.py:118`,
  `debrief/menu.py:34`).

## 8. Merge readiness

- ✅ All success criteria met (SC-001–SC-006); constitution gates pass
  (Principle IV: all 19 module files present; amendment via proper Governance
  procedure, 1.0.0 → 1.1.0).
- ⚠️ This branch stacks on unmerged 010–013 work; merging it to `main` brings
  those commits along. Recommend merging the stack in order (or fast-forwarding
  main to `b611f8d` first, then this branch).
- Not merged, per instructions.

## Blocked

Nothing blocked. The interactive `/memory` check is the only step that required a
human session; its non-interactive equivalent is recorded in
`audit/smoke-tests.md`.
