# CHANGELOG

A dated record of changes that affect the project's context (`CLAUDE.md`, `AI_CONTEXT.md`,
research docs, manifest entries, invariants), plus post-release errors discovered and how
they were fixed. Newest entry on top. Engine swaps, prompt rewrites, schema changes, and
constitution-touching decisions belong here; routine refactors do not.

## How to add an entry

1. Append a new `## YYYY-MM-DD — <one-line title>` block above the previous one.
2. Sections to fill: **What changed** (bulleted, with file paths), **Why**, **Constitution
   impact** (principle refs / traps opened or closed), **Tests touched**, **Out of scope**.
3. If an error surfaced after the change landed, add a section under **Errors fixed** at the
   bottom of the entry: symptom, root cause, fix, why it happened. Future agents read this
   to recognise the failure mode without re-discovering it.
4. Cross-link the corresponding `CLAUDE.md` / `AI_CONTEXT.md` / `doc/research_*.md` updates
   so a reader can navigate from the changelog into the live context layer.

---

## 2026-05-25 (still later) — Copy Q&A `ideal_answer` into the session report (human-only reference)

### What changed

| Area | Before | After | Files |
|---|---|---|---|
| Frontmatter | `ideal_answer` not carried into the report | New additive optional key `ideal_answer:` emitted right after `question:` when the Q&A entry has one | `src/speakloop/feedback/frontmatter.py` (Session dataclass, `dump`, `parse`) |
| Report body | Question and ideal answer only existed in `content/questions.yaml` | New optional body section "## Question & reference answer" renders right after the title when `ideal_answer` is set | `src/speakloop/feedback/report_builder.py` (`_question_reference_section`, `build`) |
| Coordinator | `Session` carried `question_text` only | `Session.ideal_answer` populated from `question.ideal_answer` | `src/speakloop/sessions/coordinator.py` |
| Report-invariance contract (006) | I3 fixed sections + I7 forbade "ideal-answer / semantic-equivalence" content | I3 lists the new section as **optional**; I7 narrowed to "no semantic-equivalence judging / scoring / new metric" — the reference copy is explicitly allowed because the AI never sees it | `specs/006-feedback-quality-reliability/contracts/report-invariance.md` |
| Invariance test | Forbade "ideal answer" substring outright | Forbids only the judging-style tokens ("semantic", "model answer", "## score", "similarity"); positively asserts the reference section is absent when `ideal_answer` is unset and present + round-trips when set | `tests/unit/feedback/test_report_invariance.py` |
| Existing report | `data/sessions/2026-05-20-onstop-savedinstancestate-api28-ordering-2.md` had question but no reference answer | Patched in-place: frontmatter `ideal_answer:` + body section | the file itself |

Schema version stays **1** — the new key is additive and optional (pre-feature reports and Q&A entries without an `ideal_answer` set produce byte-identical output to before).

### Why

The user wanted the Q&A file's `ideal_answer` visible in the saved report so they can compare their attempts against the reference after a session, without re-opening `content/questions.yaml`. The active 006 sprint had explicitly declared "no ideal-answer judging" out of scope and codified that as invariant I7 — but the invariant was scoped to **AI judging** against an ideal answer (semantic equivalence, scoring, new metric). A **static reference copy that the AI never sees** is a different thing: it serves the human reader, not the model. I7's wording was tightened to reflect that distinction.

### Constitution impact

| Principle / trap | Effect |
|---|---|
| **VI (Schema version stays 1)** | Honoured — `ideal_answer:` is additive + optional + emitted only when present, same pattern as `asr:` / `phase_c_error:` |
| **I (English-only)** | Honoured — the copy is verbatim from `content/questions.yaml`, all English |
| **006 FR-015 / I7** | Re-scoped, not violated — the rule was about feedback dimensions (judging), not human reference material. Contract + test now state that explicitly |
| **AI never sees the reference** | `feedback/grammar_analyzer.analyze` takes `transcripts` only (verified); `feedback/narrative.py` is deterministic over metrics/grammar patterns; no other call site reads `Session.ideal_answer` |

### Tests touched

- `tests/unit/feedback/test_report_invariance.py` — updated `test_no_new_feedback_dimension` (narrowed forbidden list, added negative assertion); added `test_reference_answer_renders_when_set_and_round_trips`.
- All 19 frontmatter + invariance tests pass; 139 unit tests across `feedback/`, `debrief/`, `sessions/` pass; 41 integration tests pass (3 skipped need on-disk fixtures, 3 deselected by request).

### Out of scope (deliberate)

- **No backfill of other existing reports.** Only the one report the user pointed at was patched in-place. Future sessions pick up the new field automatically via the coordinator.
- **No new tests in `tests/unit/feedback/test_frontmatter*.py`** — the existing dump/parse + round-trip coverage already exercises the additive-optional path (and the new round-trip is asserted from `test_report_invariance.py`).
- **No rendering changes to the existing five sections** (Top priority, Attempt-by-attempt summary, Cross-attempt comparison, Grammar patterns, Transcripts) — the new section is purely additive and only renders when `ideal_answer` is set.

### Live documentation updated alongside this entry

- `CLAUDE.md` (root) — active-feature line clarified ("no new feedback dimension (no ideal-answer judging) — but a static reference copy of the Q&A `ideal_answer` IS now rendered for the human reader") and feedback row note updated.
- `src/speakloop/feedback/CLAUDE.md` — public interface lists the new optional frontmatter key + body section; traps note the AI never sees it.
- `specs/006-feedback-quality-reliability/contracts/report-invariance.md` — I3 + I7 wording (see table above).

---

## 2026-05-25 (later) — Re-quantised Qwen3-14B 6-bit → 4-bit (M3 Pro 18 GB GPU OOM fix)

### What changed

| Area | Before | After | Files |
|---|---|---|---|
| LLM manifest | `mlx-community/Qwen3-14B-6bit` (~12 GB on-disk, ~14 GB resident) | `mlx-community/Qwen3-14B-4bit` (~8 GB on-disk, ~9–10 GB resident) | `src/speakloop/installer/manifest.py` |
| Manifest constant | `QWEN3_14B_6BIT` | `QWEN3_14B_4BIT` | manifest + every importer |
| Hardware budget | implicit; assumed 14B-6bit would fit alongside resident Whisper | documented in `doc/research_llm.md`: LLM resident ceiling ~10 GB on the M3 Pro 18 GB target after subtracting macOS, Python deps, and the resident Whisper encoder | `doc/research_llm.md` |

Free-form prompt, thinking-on, `temperature=0.3`, catalog deletion — **all unchanged.**
Only the manifest entry (and its name) moved.

### Why

A real session crashed with `[METAL] Command buffer execution failed: Insufficient Memory
(kIOGPUCommandBufferCallbackErrorOutOfMemory)` during the third sequential Whisper
transcribe — *before* Qwen had even loaded. Memory math on M3 Pro 18 GB: macOS + apps
(~4–6 GB) + Python deps (~1–2 GB) + Whisper-large-v3-turbo resident (~3 GB) + the
*pending* Qwen3-14B-6bit (~14 GB resident with KV cache) totals ~22–25 GB — exceeds the
18 GB unified-memory pool. Re-quantising to 4-bit at the same 14B parameter count drops
the LLM resident size to ~9–10 GB, which fits with the resident Whisper plus system
overhead.

### Constitution impact

| Principle / trap | Effect |
|---|---|
| **VII (Apple Silicon primary target)** | Hardware-budget rule formalised in `doc/research_llm.md`: future LLM swaps MUST sanity-check resident size against the 18 GB minus 8 GB system/ASR overhead ≈ 10 GB ceiling |
| **V (Swappable engines)** | Wrapper unchanged; only the manifest entry + constant name moved |
| **X (Research in the repo)** | `doc/research_llm.md` got a new "Update — 2026-05-25" section documenting the OOM diagnosis and the 4-bit fix |

### Tests touched

- `tests/unit/llm/test_model_identity.py` — rewritten to pin the 4-bit identity (Qwen3-14B-4bit, "4bit" in repo id, "6bit"/"8bit" absent).
- `tests/unit/llm/test_qwen_engine.py` — `QWEN3_14B_6BIT` import renamed to `QWEN3_14B_4BIT`.
- `tests/unit/installer/test_manifest.py` — constant rename.
- All 51 affected tests pass.

### Out of scope (deliberate)

- The `mlx-whisper` transcribe loop does **not** call `mx.clear_cache()` between calls
  (potential incremental MLX cache growth across attempts). The 4-bit Qwen fits even
  without that hygiene fix; leaving the cache-clearing improvement as a separate, smaller
  follow-up.
- No code path changes (the wrapper, analyzer, narrative, frontmatter, etc. are all
  unchanged — strict scope: this entry is only the manifest swap to recover from a wrong
  sizing decision).

### Live documentation updated alongside this entry

- `CLAUDE.md` (root) — modules table + Overview line (Qwen3-14B 6-bit → 4-bit).
- `AI_CONTEXT.md` — `last_updated` → 2026-05-25, `version` → 4, Models table, Key runtime
  deps, Performance Profile.
- `src/speakloop/llm/CLAUDE.md` — engine identity + 4-bit ship rationale (replaces the
  6-bit-ship language).
- `src/speakloop/installer/CLAUDE.md` — manifest rationale line updated.
- `doc/research_llm.md` — new "Update — 2026-05-25" section.

### Errors fixed

#### E3 — GPU OOM during 3rd Whisper transcribe; Qwen3-14B-6bit didn't fit M3 Pro 18 GB

**Symptom (real user session):**
After "✓ Attempt 3 recorded — 6.8s captured. Transcribing…", the process printed:
```
libc++abi: terminating due to uncaught exception of type std::runtime_error:
[METAL] Command buffer execution failed: Insufficient Memory
(00000008:kIOGPUCommandBufferCallbackErrorOutOfMemory)
```
…and exited. No `phase_c_error` was written; no report was produced. This was the *second*
crash on the same hardware after the [E2 Anaconda venv fix](#e2--speakloop-practice-quit-silently-mid-transcription-anaconda-venv-conflict)
— the venv was clean (resource_tracker now referenced `~/.local/share/uv/python/...`),
so this was a different failure mode.

**Root cause:**
Hardware mismatch with the chosen model size. The user is on a **MacBook Pro M3 Pro / 18 GB
unified memory**. The previous Qwen3-14B-6bit manifest entry was ~12 GB on disk and ~14 GB
resident with KV cache. Memory accounting:

| Component | Resident demand |
|---|---|
| macOS + browser/apps | ~4–6 GB |
| Python + numpy + transformers (loaded by `uv sync`) | ~1–2 GB |
| Whisper-large-v3-turbo (resident in GPU after attempt 1) | ~3 GB |
| Qwen3-14B-6bit (about to load for Phase C) | ~13–14 GB |
| **Total** | **~21–25 GB ≫ 18 GB** |

The original `doc/research_llm.md` (pre-update) explicitly recommended the 8–9B class
for the M3 Pro 18 GB target; I overshot when choosing 6-bit precision for the swap.
The OOM hit during the 3rd transcribe (before Qwen loaded) because Whisper's MLX command
buffers accumulate across sequential transcribes — already brushing the pool ceiling
before any LLM allocation was attempted.

**Fix:**
Re-quantised the LLM at the same 14B size: `mlx-community/Qwen3-14B-6bit` →
`mlx-community/Qwen3-14B-4bit`. Resident size drops from ~14 GB to ~9–10 GB; combined
with the resident Whisper and system overhead it fits the 18 GB budget with headroom.
Quality cost vs 6-bit is small for analytic / structured-output tasks (no community
measurements show a material drop at this quant for GEC-style work). Free-form prompt,
thinking-on, `temperature=0.3` — all preserved.

**Why it happened:**
The May-2026 model swap PR did not document an explicit resident-RAM budget for the LLM,
so the 6-bit precision call was made on quality grounds without checking it against
the M3 Pro 18 GB target's unified-memory ceiling minus the resident Whisper encoder.
The original `doc/research_llm.md` table had a row for resident RAM but the swap entry
didn't enforce it.

**Prevention for future LLM swaps:**
The hardware budget rule is now codified in `doc/research_llm.md` (May-25 update):
**future LLM swaps MUST sanity-check resident size against ~10 GB** (18 GB unified ÷
minus ~5 GB macOS+Python ÷ minus ~3 GB resident ASR encoder). Any candidate model whose
resident size exceeds that ceiling must either come with an explicit unload-Whisper-before-
loading-LLM mechanism, or be rejected for the M3 Pro 18 GB target.

**Operator action after this fix:**
The previously-downloaded Qwen3-14B-6bit (12 GB on disk) is now orphaned. Reclaim with:
```sh
rm -rf ~/.speakloop/models/mlx-community__Qwen3-14B-6bit/
```
Then trigger the new model's download:
```sh
uv run python -c "from speakloop.installer import ensure_models; ensure_models('C')"
```

---

## 2026-05-25 — Qwen3-14B-6bit + thinking-on + free-form grammar prompt; Anaconda-venv crash fixed

### What changed

| Area | Before | After | Files |
|---|---|---|---|
| LLM manifest | `mlx-community/Qwen3-8B-4bit` (~4.31 GiB) | `mlx-community/Qwen3-14B-6bit` (~12 GB) | `src/speakloop/installer/manifest.py` |
| Manifest constant | `QWEN3_8B_4BIT` | `QWEN3_14B_6BIT` | manifest + every importer |
| Thinking mode | `enable_thinking=False`; wrapper scrubbed every `<think>` block | `enable_thinking=True`; wrapper strips only the leading `<think>...</think>` block (DOTALL regex, count=1) | `src/speakloop/llm/qwen_engine.py` |
| Grammar prompt | Catalog-aware (Persian-L1 transfer-error catalog injected into the prompt) | Free-form: model returns its own `error_type` strings which become `GrammarPattern.label` verbatim | `src/speakloop/feedback/grammar_analyzer.py` |
| Analyzer JSON key | `{"patterns": [...]}` | `{"errors": [...]}` (per-error schema with `attempt_ordinal`, `quote`, `corrected`, `error_type`, `explanation`) | `grammar_analyzer.py` |
| Analyzer temperature | inherited Protocol default (0.7) | 0.3 at the call site (Protocol default unchanged) | `grammar_analyzer.py` |
| Catalog | `feedback/catalog.py` + `persian_l1_catalog.yaml` + `OPEN_BUCKET_IMPACT_RANK` constant | Deleted. Constant moved to `feedback/frontmatter.py` (still exported by the same name; only matters for legacy-report parse fallback) | `feedback/*` |
| Eval harness | `eval/grammar/` (run_eval.py + 25 cases + 120 failure_batch + baselines) + `tests/unit/eval/` | Deleted entirely (catalog-shaped; redesign needed for free-form labels) | `eval/`, `tests/unit/eval/` |
| Test suite | 363 passed (catalog era) | **340 passed, 3 skipped** (the 3 skips are documented local-only `repro` + `live_asr` gates, unchanged) | full `tests/` |

### Why

Pre-adoption testing on a representative Persian-L1 transcript triple compared Qwen3-14B-6bit
vs Granite-4.1-8B vs Ministral-3-14B-Instruct against the same free-form prompt:

- Qwen3-14B-6bit reached **7 / 7 recall** and was the only candidate that distinguished
  present continuous from present simple — the deciding capability for Persian-L1 learners.
- The other two surfaced partial recall and conflated the tenses.

Temperature 0.3 (vs the Protocol default 0.7) materially improved both recall and JSON
discipline for analytic / structured-output tasks. The Protocol default stays 0.7 for
back-compat.

Thinking mode is enabled because Qwen3-14B's reasoning prelude measurably lifts grammar
extraction quality. The wrapper strips the *leading* `<think>...</think>` block so callers
see a clean JSON-ready payload; mid-output `<think>` is unexpected with the Qwen3-14B chat
template and is left in place; a truncated thinking pass (missing `</think>`) is also left
in place and triggers the analyzer's bounded regenerate path.

The catalog is retired because the free-form prompt subsumes its job (the model now labels
its own errors), and the on-the-fly free-form labels generalise beyond the Persian-L1 set
without losing the verbatim / coherence / no-op-fix guards.

### Constitution impact

| Principle / trap | Effect |
|---|---|
| **V (Swappable Engines)** | Wrapper + manifest swap; engine import stays function-local; the analyzer passes intent (`retry`) and `temperature`, never engine config |
| **VIII (`--help` model-free)** | Re-verified: 0.15 s, zero engine imports at module load |
| **IX (schema_version stays 1)** | Unchanged. `GrammarPattern.catalog_id` retained as additive optional (always `None` for new sessions; legacy reports still round-trip) |
| **X (Research lives in the repo)** | `doc/research_llm.md` appended with the May-2026 swap rationale; manifest and research finally agree |
| **Trap 3 (LLM diverges from research)** | **CLOSED.** Manifest and research now both target Qwen3-14B-6bit. Historical context preserved in `doc/research_llm.md` |
| **Trap 7 (json-repair recovery + engine config lives in wrapper)** | Updated. The catalog reference is removed; the json-repair + bounded-regenerate ladder is unchanged |

### Tests touched

- Added: `tests/unit/llm/test_model_identity.py` (4 tests pinning Qwen3-14B-6bit identity).
- Deleted (catalog era): `tests/unit/feedback/test_catalog.py`, `tests/unit/llm/test_model_family_unchanged.py`.
- Deleted (eval era): `tests/unit/eval/`, `tests/integration/test_eval_not_shipped.py`.
- Updated to the new `{"errors": [...]}` schema: `tests/unit/feedback/test_grammar_analyzer.py` (rewritten), `test_grammar_recovery.py`, `test_grammar_repair.py`, 8 fixtures under `tests/unit/feedback/fixtures/bad_json/`, `tests/integration/test_phase_c_report.py`, `tests/integration/phase_c_debrief_test.py`, `tests/integration/test_no_network_during_session.py`.
- Updated for thinking-ON: `tests/unit/llm/test_qwen_engine.py` (strip semantics changed to leading-only; expected outputs updated for unclosed / mid-text think cases), `tests/unit/llm/test_qwen_generation_config.py` (`enable_thinking` assertion flipped).

### Out of scope (deliberate)

- No `mlx-lm` pin bump (>=0.31.3 supports the Qwen3 family).
- No `uv.lock` regeneration (no `pyproject.toml` edit).
- No new dependency.
- No edits to TTS / ASR / audio / sessions / trends source files.
- `tests/fixtures/transcripts/gold_set.yaml` left as orphan data (was used only by the
  rewritten `test_grammar_analyzer.py`; harmless YAML).
- 8-bit Qwen quant stays out of scope.

### Live documentation updated alongside this entry

- `CLAUDE.md` (root) — modules table, Trap 3, Trap 7, command count line.
- `AI_CONTEXT.md` — frontmatter (last_updated, version), Models table, Key runtime deps,
  Performance Profile, Invariants table, Friction map, Domain Glossary, End-to-End Flow §13.
- `src/speakloop/llm/CLAUDE.md` — engine identity, file map, traps (thinking-on policy).
- `src/speakloop/feedback/CLAUDE.md` — analyzer description, file map (catalog removed),
  traps (`catalog_id` retention note).
- `src/speakloop/installer/CLAUDE.md` — manifest rationale + closed-divergence trap removed.
- `doc/research_llm.md` — new "Update — 2026-05-24" section documenting the swap.

---

### Errors fixed

#### E1 — Three integration tests failed after the schema swap

**Symptom (during Phase 8 validation):**
- `tests/integration/test_eval_not_shipped.py::test_eval_dir_is_outside_the_package`:
  `AssertionError: eval/ should exist at the repo root`.
- `tests/integration/test_phase_c_report.py::test_phase_c_report_has_grammar_patterns`:
  `AssertionError: assert 0 == 1` — the report had no grammar patterns.
- `tests/integration/phase_c_debrief_test.py::test_replay_loops_to_same_question_without_reload`:
  failed because the canned LLM payload produced zero patterns, then the debrief had no
  pattern card to read aloud.

**Root cause:**
- `test_eval_not_shipped.py` existed solely to guard the now-deleted `eval/` directory's
  isolation (that the wheel stays scoped to `src/speakloop`); with `eval/` gone, the test's
  premise vanished.
- The other two used the **old** `{"patterns": [{label, occurrence_count, evidence}]}` JSON
  shape for their stub LLM. The rewritten analyzer reads `payload.get("errors")` and ignores
  `patterns` — so the stub returned a dict the analyzer couldn't extract any errors from,
  giving empty grammar patterns.

**Fix:**
- Deleted `tests/integration/test_eval_not_shipped.py` (obsolete isolation guard).
- Rewrote the stub LLM payloads in both phase-C tests to the new schema
  (`{"errors": [{attempt_ordinal, quote, corrected, error_type, explanation}, ...]}`).

**Why it happened:**
The original task description listed the obvious test files to update but did not enumerate
every integration test with a hand-rolled stub LLM payload. The integration tests' canned
JSON survived the rewrite because they were not exercised until the post-edit `pytest` ran.
Lesson for future schema swaps: grep `tests/` for the old key (`"patterns":`) and the old
catalog identifiers before assuming the catalog is gone.

#### E2 — `speakloop practice` quit silently mid-transcription (Anaconda venv conflict)

**Symptom:**
After "✓ Attempt 1 recorded — 8.1s captured. Transcribing…", the process exited with no
Python traceback. Two tell-tale lines were emitted at shutdown:
```
OMP: Info #276: omp_set_nested routine deprecated, please use omp_set_max_active_levels instead.
/opt/anaconda3/lib/python3.12/multiprocessing/resource_tracker.py:254: UserWarning:
  resource_tracker: There appear to be 1 leaked semaphore objects to clean up at shutdown
```
…followed immediately by the shell prompt returning. No `phase_c_error` was written; no
report was produced.

**Root cause:**
The project's `.venv` was created with **Anaconda's** Python 3.12 (`(base)` conda env was
active when `uv venv` ran). Diagnostic confirmation:
```
exec:        .../speakloop/.venv/bin/python3
base_prefix: /opt/anaconda3        # <-- the smoking gun
CONDA_PREFIX: /opt/anaconda3
```
A venv with `base_prefix = /opt/anaconda3` loads its stdlib AND its dynamically-linked
runtime libraries (libomp, libgcc, libstdc++) from anaconda. When the ASR step imports
`mlx-whisper` + `silero-vad` + `torchaudio` together, each of those wheels bundles its own
libomp; anaconda's libomp was already in the process, so the second copy triggered a
silent native segfault (no Python frame to print). The `resource_tracker` warning was the
multiprocessing module noticing un-reaped semaphores at process tear-down — a symptom,
not the cause.

**Fix:**
Rebuilt the venv against a uv-managed CPython 3.12.8 so anaconda is fully out of the
process picture:
```sh
uv python install 3.12       # downloads CPython 3.12.8 to ~/.local/share/uv/python/...
rm -rf .venv                 # drop the anaconda-rooted venv
uv venv --python 3.12        # create fresh venv from the uv-managed Python
uv sync                      # reinstall all deps from uv.lock
```
Verification (post-fix):
```
exec:        .../.venv/bin/python3
base_prefix: /Users/ehsankolivans/.local/share/uv/python/cpython-3.12.8-macos-aarch64-none
```
All four previously-clashing imports now load cleanly in the same process: `mlx_whisper`,
`silero_vad`, `torchaudio`, `mlx_lm`. `uv run speakloop doctor` shows all 8 rows OK
(including Qwen3-14B-6bit, since the model bytes live under `~/.speakloop/models/` and
were untouched by the venv rebuild).

**Why it happened:**
1. The user's shell auto-activates conda's `base` environment on startup
   (`(base)` in the prompt).
2. When `uv venv` (or the first `uv sync`) was run, `uv` searched `PATH` for a Python
   matching `requires-python = ">=3.12,<3.13"`. Anaconda's `/opt/anaconda3/bin/python3.12`
   was the first hit, so `uv` used it to seed the venv.
3. From then on, every `uv run` activated a venv whose Python was anaconda's, with the
   anaconda stdlib + dylibs in scope. The conflict only surfaced at runtime when multiple
   native ML libraries tried to load OpenMP simultaneously — i.e. during ASR transcription.

**Prevention for future contributors:**
- Run `uv run python -c "import sys; print(sys.base_prefix)"` after creating the venv;
  the output should sit under `~/.local/share/uv/python/...`, NOT `/opt/anaconda3` or any
  conda env path.
- If you use conda for unrelated work, either run `conda deactivate` before
  `uv venv` / `uv sync`, or pass `--python 3.12` to `uv venv` together with
  `uv python install 3.12` to force a uv-managed interpreter.
- A `doctor` check that flags a non-uv-managed `base_prefix` would surface this earlier
  — a candidate follow-up (not in this entry's scope).
