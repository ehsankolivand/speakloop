# Phase 0 Research & Audit Deliverables — Context Engineering Audit

**Feature**: 005-context-engineering-audit · **Date**: 2026-05-21

> Code is the source of truth. Every row below was produced by reading the code,
> running a command, or scanning imports — NOT by trusting existing prose. These
> are **inputs to** the rewrite, captured before any `CLAUDE.md` was edited.

---

## §A — Launch-footprint budget (FR-043, SC-K) — PINNED

**Decision**: The launch-time context layer MUST stay **≤ 6000 tokens** (cl100k_base),
measured as a hard ceiling.

**What counts toward the budget** (everything injected at session launch / re-injected
after `/compact`):
- The entire top-level `CLAUDE.md` (both the SPECKIT-managed block and the human map).
- Any unscoped `.claude/rules/*.md` (rules with NO `paths` frontmatter).
- Any `@`-imported file transitively pulled in from the above.

**What contributes ZERO launch tokens** (must be verified to stay at zero):
- The 13 module `CLAUDE.md` files (loaded just-in-time when a file in that module is read).
- Any `paths`-scoped `.claude/rules/*.md`.

**Rationale for 6000**: The current top-level `CLAUDE.md` is 69 lines / 5100 chars ≈
**~1275 tokens** (`chars / 4` proxy). The rewrite targets < 200 lines; at the current
density a full 200-line file is ≈ 3700–4200 tokens. A 6000-token ceiling leaves
headroom for the rewrite plus a couple of small unscoped rules without ever
approaching a level that bloats every session. If the rewrite + rules exceed 6000,
the fix is to push detail down into module files or `paths`-scoped rules — not to
raise the ceiling.

**Measurement command (primary — precise cl100k_base):**
```bash
uv run --with tiktoken python - <<'PY'
import tiktoken, pathlib
enc = tiktoken.get_encoding("cl100k_base")
paths = ["CLAUDE.md"]  # + any unscoped .claude/rules/*.md
total = sum(len(enc.encode(pathlib.Path(p).read_text())) for p in paths)
print(f"launch footprint: {total} tokens (ceiling 6000)")
assert total <= 6000, f"OVER BUDGET by {total-6000}"
PY
```
`tiktoken` is invoked ephemerally with `--with`; it is NOT added to `pyproject.toml`
(keeps the dependency set clean per the constitution's "stdlib over dependencies").

**Measurement command (fallback — stdlib, offline):**
```bash
python3 -c "import pathlib; c=len(pathlib.Path('CLAUDE.md').read_text()); print(f'{c} chars ≈ {c//4} tokens (ceiling 6000)')"
```

**Footprint note**: The SPECKIT-managed block grows ~5–12 lines per feature (it
currently lists 4 prior features + the active one). Keeping that history terse is part
of staying under budget; the maintenance checklist (§F) includes pruning it.

---

## §B — Existing CLAUDE.md inventory (SC-A baseline)

All 14 files are already under their ceilings; the work is anatomy/signal/accuracy,
not trimming. Several thin files cannot yet cover Principle IV's six fields and will
be **expanded** (still < 100 lines).

| File | Lines | Ceiling | Headroom | Note |
|------|-------|---------|----------|------|
| `CLAUDE.md` (root) | 69 | 200 | 131 | Lines 1–45 are the SPECKIT-managed block; 47–69 the human map. |
| `asr/CLAUDE.md` | 46 | 100 | 54 | Richest module file; near-anatomy already. |
| `feedback/CLAUDE.md` | 35 | 100 | 65 | |
| `debrief/CLAUDE.md` | 33 | 100 | 67 | |
| `cli/CLAUDE.md` | 18 | 100 | 82 | |
| `config/CLAUDE.md` | 16 | 100 | 84 | |
| `content/CLAUDE.md` | 16 | 100 | 84 | |
| `installer/CLAUDE.md` | 13 | 100 | 87 | |
| `metrics/CLAUDE.md` | 11 | 100 | 89 | **Thin** — expand to 6 fields. |
| `trends/CLAUDE.md` | 11 | 100 | 89 | **Thin** — expand. |
| `tts/CLAUDE.md` | 11 | 100 | 89 | **Thin** — expand. |
| `llm/CLAUDE.md` | 10 | 100 | 90 | **Thin** — expand. |
| `audio/CLAUDE.md` | 9 | 100 | 91 | **Thinnest** — expand. |
| `sessions/CLAUDE.md` | 9 | 100 | 91 | **Thinnest** — expand. |

Command: `find . -name CLAUDE.md -not -path '*/node_modules/*' | xargs wc -l`.

---

## §C — Engine-import owner map (FR-006, SC-L) — Principle V VERIFIED

Scan: `rg -n "^\s*(import|from)\s+(mlx_whisper|silero_vad|onnxruntime|parakeet_mlx|mlx_lm|kokoro)" src/speakloop/`.
**Result: engine isolation holds.** Each engine package is imported (function-local)
in exactly one wrapper file.

| Engine package | Owning file | Import site(s) | Status |
|----------------|-------------|----------------|--------|
| `mlx_whisper` | `src/speakloop/asr/whisper_mlx_engine.py` | lines 78, 102, 118 | ✅ one file |
| `silero_vad` | `src/speakloop/asr/vad.py` | line 81 | ✅ one file |
| `parakeet_mlx` | `src/speakloop/asr/parakeet_engine.py` | line 48 | ✅ one file |
| `mlx_lm` | `src/speakloop/llm/qwen_engine.py` | lines 47, 78, 79 | ✅ one file |
| `kokoro_mlx` | `src/speakloop/tts/kokoro_engine.py` | line 41 | ✅ one file |
| `onnxruntime` | **none (transitive)** | — | ⚠ see finding D-1 |

**Naming nuances to fix in docs (D-2):** the spec/FR-006/FR-010 write "kokoro", but the
actual package imported is **`kokoro_mlx`** (pyproject: `kokoro-mlx`). Documentation
must name `kokoro_mlx`.

**Dedicated engine-isolation test EXISTS** (resolves the spec's open assumption):
`tests/unit/asr/test_engine_import_isolation.py` (1768 bytes) audits the asr engine
packages. Coverage of `mlx_lm` (llm) and `kokoro_mlx` (tts) is asserted indirectly by
`tests/integration/test_help_without_models.py` for `mlx_lm` but **not** for
`kokoro_mlx` — recorded as finding D-3 (flag only; no test is created here per FR-053).

---

## §D — Divergence inventory (FR-001) — seed rows from Phase 0

Severity scale (sprint-3): CRITICAL / MAJOR / MINOR / INFO. Full inventory is completed
during the rewrite; these are the divergences already surfaced by reconnaissance.

| ID | Claim (doc `file:line`) | Ground truth (code `file:line`) | Severity | Action |
|----|--------------------------|----------------------------------|----------|--------|
| D-1 | FR-006 lists `onnxruntime` as an engine package expected to have one owning wrapper | No direct `import onnxruntime` in `src/`; it is a **transitive** dep of `silero_vad` (declared `pyproject.toml:28`, used inside `asr/vad.py` via silero) | MINOR | Document `onnxruntime` as transitive-via-silero, not as an owned wrapper import. `asr/CLAUDE.md:31` already says vad.py is the only file importing silero/onnx — verify wording. |
| D-2 | Docs/spec say "kokoro" | Package is `kokoro_mlx` (`tts/kokoro_engine.py:41`, `pyproject.toml:18`) | MINOR | Use `kokoro_mlx` in tech-stack and tts module doc. |
| D-3 | `asr/CLAUDE.md:23-24` implies isolation is test-audited | Test exists for asr; `kokoro_mlx` isolation not asserted by any test | INFO | Flag as separate finding (no test created — FR-053). |
| D-4 | (top-level map) "Thirteen fine-grained modules" | 13 module dirs confirmed under `src/speakloop/` | INFO | Accurate — keep. |
| D-5 | SPECKIT block lists 004 as "Active feature" (`CLAUDE.md:2`) | Active branch is `005-context-engineering-audit` | MINOR | Update SPECKIT block to 005 during US1 (plan-step). |

---

## §E — Command matrix (FR-003, FR-012, SC-I)

Every command claimed in any `CLAUDE.md` is verified by running it. Seed status:

| Command | Claimed in | Status (Phase 0) | Note |
|---------|-----------|------------------|------|
| `speakloop doctor` | root map (`cli/`), `cli/CLAUDE.md:14`, `practice.py:286` | **VERIFIED EXISTS** | `cli/doctor.py`, registered `cli/main.py:89` (`@app.command("doctor")`). Resolves the spec's "unconfirmed" assumption. Run it during US1 to confirm exit-0. |
| `speakloop --help` | Principle VIII / tests | guarded by `tests/integration/test_help_without_models.py` | Loads no engine packages. |
| `uv run pytest` | (to document) | run during audit | Full suite must stay green (SC-H). |
| `uv run pytest -m live_asr` | `asr/CLAUDE.md:45` | run when touching torchaudio | Real silero+audio smoke. |
| `ruff` (lint) | (to document) | run during audit | `pyproject.toml` configures ruff. |

The full matrix (with verified/failed/missing + actual invocation strings) is finalized
in US1; any command that fails or is missing is **removed** from docs, any
existing-but-undocumented command is **added**.

---

## §F — Trap-evidence list (FR-004, FR-011, SC-D) — ≥5, each evidence-cited

Candidate traps traced to real corrections across sprints 1–4. Each must cite a commit,
a session report, or a `specs/` reference. Seed candidates (evidence confirmed/expand
during US1):

1. **`torchaudio<2.9` pin.** torchaudio≥2.11 moves decoding to unbundled `torchcodec`,
   crashing the first live VAD call. Evidence: `pyproject.toml:29` + `asr/CLAUDE.md:41-46`
   + the `live_asr` pytest marker (`pyproject.toml:77`). → trap: "don't bump torchaudio
   without running `pytest -m live_asr`."
2. **Qwen3-8B vs the research's Qwen3.5-9B.** The originally-researched HF repo was a VLM
   incompatible with `mlx_lm.load()`. Evidence: `CLAUDE.md:38-40` + installer/manifest.py
   rationale comment. → trap: "the LLM choice deviates from research_llm.md on purpose."
3. **Engine imports MUST be function-local.** Module-level engine imports break
   `speakloop --help` (Principle VIII). Evidence: `tests/integration/test_help_without_models.py`
   + the `# noqa: PLC0415 — function-local` comments in the wrapper files. → trap.
4. **Personal-path leakage breaks the build.** Sprint-4 added a path-portability audit
   that fails CI on any machine-specific absolute path. Evidence: `specs/004-public-release-readiness/`
   + `tests/integration/test_path_portability_audit.py`. → trap: "no `/Users/...` in any
   committed file." (Directly relevant: the research doc leak, §G/finding.)
5. **Q&A file precedence is `--qa-file → ~/.speakloop/qa.yaml → repo default`, no
   auto-copy.** Evidence: `specs/004-…/plan.md` + `config/paths.py` (`resolve_qa_file`). → trap.
6. **`schema_version` stays 1; new frontmatter keys are additive only.** Evidence:
   constitution Development Guidelines + 002/003 specs. → trap.

(Six candidates listed so the ≥5 floor survives if one fails final evidence check.)

---

## §G — Cross-reference link check (FR-005, SC-J) + the research-doc leak

**Research-doc personal-path leak — CONFIRMED (FR-041, SC-F):**
`doc/research_context_engineering.md:3` contains
`> **File to save at:** /Users/ehsankolivans/AndroidStudioProjects/WalletFlow2/...`.
This MUST be removed for the path-portability audit to pass. The claim ledger is at
**Section 17** (`## 17. Sources and claim ledger`, line 523) — the authoritative trace
target (FR-056).

**Cross-reference sweep**: every `[text](path)` and bare `path/` pointer in each
`CLAUDE.md` is resolved against the filesystem during US1/US2. Seed: the root map's 13
module links (`CLAUDE.md:57-69`) all point to existing files; engine-research pointers
(`doc/research_tts.md`, `doc/research_asr.md`, `doc/research_llm.md`) exist. Broken
links are fixed in the live doc (not the historical specs, FR-052).

**"trivial vs flag-and-defer" definition (FR-053, guidance #7) — PINNED:**
- **In-scope / "trivial" (fix in this feature):** edits to *documentation files only* —
  `CLAUDE.md` (any scope), `doc/*.md`, fixing a broken cross-reference path, removing the
  personal path from the research doc. These have zero behavior impact and ARE the
  feature's scope.
- **Out-of-scope / flag-and-defer (NEVER done here):** ANY edit to a file under
  `src/speakloop/**` or `tests/**` or `pyproject.toml` — including changing
  `__init__.py` exports, renaming a symbol, adding a function, OR editing a docstring in
  a `.py`. Even a "harmless" docstring fix in `src/` is deferred, to keep the
  no-code-changes boundary a bright line (FR-053). Such findings get a divergence row
  with severity + a deferral note; the doc is written to match the *current* code, never
  the other way around.

---

## §H — Test-coupling check (SC-H, FR-054)

`rg -ln "CLAUDE\.md" tests/` → only `tests/integration/test_help_without_models.py`, and
its single reference is a **docstring comment** ("the cli/CLAUDE.md contract", line 3),
NOT a content assertion. **Finding: no test asserts on `CLAUDE.md` content.** The
rewrite cannot break a test by changing prose. (Recorded per FR-054; no test is
weakened.) The full `pytest` suite must still be run green after the rewrites (SC-H).

---

## §I — Sub-agent adversarial-review protocol (FR-014, SC-C) — reproducible

The zero-CRITICAL/MAJOR verdict for the top-level `CLAUDE.md` is produced by a **fresh
review sub-agent** (the Claude Code Task/general-purpose or Explore agent), invoked once
per rewrite, independent of the author. This is a procedure, not a one-off.

**Agent scope (what it may read):** the rewritten `CLAUDE.md` + `src/speakloop/**` +
`tests/**` + `pyproject.toml` + `.specify/memory/constitution.md`. Nothing else (not the
spec, not the old CLAUDE.md, not the research doc) — the review is file-vs-code.

**Exact prompt given to the review sub-agent:**
> You are an adversarial documentation reviewer. Read ONLY `CLAUDE.md` and the code in
> `src/speakloop/`, `tests/`, and `pyproject.toml`. For EVERY factual claim in
> `CLAUDE.md` (tech-stack versions, module dependencies, commands, engine-import
> boundaries, traps, never-do items), find the `file:line` in code that supports or
> contradicts it. Output a table: `claim (CLAUDE.md:line) | ground truth (code file:line)
> | severity | verdict`. Severity scale: CRITICAL (claim is false and would mislead an
> agent into a wrong change), MAJOR (claim is materially inaccurate), MINOR (imprecise
> but not misleading), INFO (note). Do not suggest prose improvements; only verify
> truth against code. End with a one-line VERDICT: `PASS` (zero CRITICAL and zero MAJOR)
> or `FAIL` with the count of each.

**Output format**: the severity-classified divergence table above (sprint-3 docs-audit
shape), saved into the divergence inventory in this file/feature dir.

**Verdict gate**: SC-C requires **PASS** (0 CRITICAL, 0 MAJOR). On FAIL, fix the named
claims and re-run the same agent until PASS; record the final PASS verdict in the
audit artifacts.

---

## §J — Per-feature maintenance checklist (FR-020, SC-E) — lives in top-level CLAUDE.md

The maintenance cadence is **feature-driven** (per the clarify decision): each new
`specs/NNN-*` feature triggers this checklist, plus per-PR convention-change coupling.
The checklist below is authored verbatim into the top-level `CLAUDE.md` maintenance
section (concrete, applicable in < 2 minutes):

1. **Re-read the top-level `CLAUDE.md` against the new feature's scope** — does the
   overview/tech-stack/module-layout still hold? Update the SPECKIT block's active/prior
   feature lines and prune stale history to protect the 6000-token budget.
2. **Run the documented commands** (`speakloop --help`, `speakloop doctor`,
   `uv run pytest`, `ruff`) — remove any that now fail; add any new one.
3. **Flag any module whose code changed since last review** (`git log --since=<last
   feature> -- src/speakloop/<mod>/`) and re-check that module's `CLAUDE.md`.
4. **Re-run the engine-import scan** (§C command) — confirm each engine package still
   resolves to exactly one wrapper file (Principle V).
5. **Correct-twice-then-record**: if an agent was corrected on the same thing twice this
   feature, add it to the relevant `CLAUDE.md` (trap or never-do).
6. **PR-coupling**: any PR that changed a convention must have updated the relevant
   `CLAUDE.md` in the same commit — verify before merge.
7. **Footprint check**: re-measure the launch footprint (§A command); if over 6000,
   push detail into a module file or a `paths`-scoped rule.

---

## §K — Scoped-rules decision input (FR-040, SC-G)

`.claude/rules/` does not exist today; there are no `@`-imports in the top-level file.
Whether any rule file earns its place is decided in US3 from observed friction. Default
expectation: **zero** rule files (adding them speculatively violates the discipline this
feature enforces). If none is justified, that decision is recorded in US3's notes. Any
added file carries `paths` frontmatter + an HTML-comment justification (why module-scope
rule vs. living in the relevant `CLAUDE.md` vs. skipped) and must not add launch tokens.
