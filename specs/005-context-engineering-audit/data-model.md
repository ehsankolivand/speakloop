# Data Model — Context Engineering Audit

**Feature**: 005-context-engineering-audit · **Date**: 2026-05-21

This feature's "data" is documentation structure and audit evidence. The entities
below formalize the spec's Key Entities; the **anatomy definitions** make FR-010
(top-level) and FR-030/FR-031 (module) concrete and ordered so the rewrite is
deterministic.

---

## Entities

### Context file
A `CLAUDE.md` at a given scope.
- `scope`: `root` | `module:<name>`
- `sections_present`: ordered list of anatomy section keys (see below)
- `line_count`: int (≤ 200 for root, ≤ 100 for module)
- `load_timing`: `launch` (root only) | `on-demand` (modules)
- `language`: must be `en`
- `launch_tokens`: int — root contributes to the ≤ 6000 budget; modules contribute 0

### Divergence record (FR-001)
- `id`: e.g. `D-1`
- `claim_ref`: `file:line` in a `CLAUDE.md`
- `ground_truth_ref`: `file:line` in `src/speakloop/`, `tests/`, or `pyproject.toml`
- `severity`: `CRITICAL` | `MAJOR` | `MINOR` | `INFO`
- `action`: recommended fix (doc edit) OR `flag-and-defer` (code change out of scope)

### Known-trap entry (FR-004)
- `description`: the trap, stated as a concrete "don't / do" rule
- `evidence_ref`: commit hash | session-report path | `specs/` reference (REQUIRED — no
  evidence ⇒ dropped)

### Command record (FR-003)
- `command`: the exact invocation string
- `status`: `verified` | `failed` | `missing`
- `claimed_in`: source `file:line`

### Cross-reference (FR-005)
- `source`: `file` (+ optional anchor)
- `target`: path
- `resolves`: bool

### Scoped rule file (FR-040)
- `path`: `.claude/rules/<name>.md`
- `paths_glob`: frontmatter scope (REQUIRED)
- `justification`: HTML-comment rationale (REQUIRED)

### Claim-ledger reference (FR-056)
- `claim_number`: an entry in `doc/research_context_engineering.md` §17
- `decision`: the design decision it justifies

---

## Anatomy definition — TOP-LEVEL `CLAUDE.md` (FR-010)

Fixed order. The SPECKIT-managed block (`<!-- SPECKIT START -->…<!-- SPECKIT END -->`)
is preserved at the top of the file (FR-015) and is NOT part of the anatomy spine; the
anatomy applies to the human-authored region below it.

| # | Section key | Content | Mandatory? |
|---|-------------|---------|------------|
| a | `overview` | Project purpose in 2–3 sentences | **Yes** |
| b | `tech-stack` | Fixed list from `pyproject.toml`, verified vs imports: Python 3.12, `uv`, `mlx-whisper`, `mlx-lm`, `kokoro-mlx`, `silero-vad`, `onnxruntime` (transitive), `parakeet-mlx`, `torchaudio<2.9` cap, `typer`/`rich`/`pyyaml`/`sounddevice`/`huggingface_hub`/`numpy` | **Yes** |
| c | `layout` | Module layout + dependency rules from the import scan (§C/FR-007), not from prose | **Yes** |
| d | `commands` | Verified build/test/lint commands (§E) — each actually run | **Yes** |
| e | `conventions` | Conventions cross-verified vs code + constitution | **Yes** |
| f | `maintenance` | "How to maintain this context layer" — the 7-item checklist (research §J), feature-driven cadence, correct-twice, PR-coupling, split-on-overflow (FR-020) | **Yes** |
| g | `traps` | ≥ 5 known traps, each evidence-cited (§F/FR-011) | **Yes** |
| h | `never-do` | Never-do list with code-pattern citations where applicable | **Yes** |
| i | `pointers` | Pointers to per-module `CLAUDE.md`, `specs/`, `doc/research_*.md`, the constitution (prefer pointers over `@`-imports; depth ≤ 5) | **Yes** |

All nine are mandatory for the root file. (`maintenance` is placed after `conventions`
and before `traps` so the "how we keep this true" rules sit next to the conventions they
protect.)

---

## Anatomy definition — MODULE `CLAUDE.md` (FR-030, FR-031)

Per the Q1 clarify decision (**module-adapted order**): keep the shared section *order*,
**omit** sections that have no module-scope meaning (no global tech-stack, no global
build/test/lint commands), and always include the Principle IV six fields. Optional
sections are included only when they hold real content (not padded with "N/A").

| # | Section key | Content | Mandatory? | Maps to Principle IV |
|---|-------------|---------|------------|----------------------|
| a | `purpose` | Module purpose in 1–2 sentences | **Yes** | purpose |
| b | `public-interface` | What the module exports to other modules (the Protocols, functions, dataclasses other modules import) | **Yes** | public interface |
| c | `dependencies` | What this module imports: the engine package it owns (Principle V boundary, §C) + internal module deps | **Yes** | dependencies |
| d | `consumers` | Which modules import this one | **Yes** | consumers |
| e | `file-map` | Key files + 1-line role each | **Yes** | file map |
| f | `modification-patterns` | How to make common changes here ("to add an X, …") | **Yes** | common modification patterns |
| g | `traps` | Module-specific known traps | Optional — include iff ≥1 real trap | — |
| h | `never-do` | Module-specific prohibitions | Optional — include iff a real one exists | — |
| i | `pointers` | Pointer back to the root map / related modules | Optional | — |

The six mandatory sections (a–f) are exactly Principle IV's six fields → the anatomy
**supersets** Principle IV (FR-031). Sections g–i are the optional-when-empty tail.

**Engine-owning modules** (`asr`, `llm`, `tts`) MUST name their engine-import boundary
in section `c` (FR-032): `asr` → `mlx_whisper` (whisper_mlx_engine.py), `silero_vad`
(vad.py), `parakeet_mlx` (parakeet_engine.py); `llm` → `mlx_lm` (qwen_engine.py); `tts`
→ `kokoro_mlx` (kokoro_engine.py). `onnxruntime` is documented as transitive-via-silero
in `asr` (finding D-1), not as an owned import.

---

## Shared anatomy spine (SC-B reconciliation)

SC-B names one 9-slot spine — "overview, scope/stack, layout/boundaries, commands,
conventions, maintenance, traps, never-do, pointers" — realized differently per scope.
A reader finds the same *slot* in the same place; modules drop the inapplicable slots.

| SC-B spine slot | Root realization | Module realization |
|-----------------|------------------|--------------------|
| overview | `overview` | `purpose` |
| scope / stack | `tech-stack` | *(omitted — no module-scope stack)* |
| layout / boundaries | `layout` | `public-interface` + `dependencies` + `consumers` |
| commands | `commands` | *(omitted — no module-scope build commands)* |
| conventions | `conventions` | `file-map` + `modification-patterns` |
| maintenance | `maintenance` | *(omitted — modules carry no maintenance section)* |
| traps | `traps` (≥5) | `traps` (optional) |
| never-do | `never-do` | `never-do` (optional) |
| pointers | `pointers` | `pointers` (optional) |

---

## Validation rules (from requirements)

- Root `CLAUDE.md` < 200 lines (FR-013); each module `CLAUDE.md` < 100 lines (FR-033).
- All content English (FR-050).
- Root traps ≥ 5, each evidence-cited (FR-011).
- Every documented command verified (FR-012); failing/missing removed.
- Every cross-reference resolves (SC-J).
- Each engine package → exactly one wrapper file, recorded (SC-L).
- No module `CLAUDE.md` rewritten unless its module was read in full (FR-002, FR-034).
- Launch footprint ≤ 6000 tokens; module files + scoped rules = 0 launch tokens (SC-K).
- Every non-obvious decision traces to a §17 claim number (FR-056).
