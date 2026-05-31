# Implementation Plan: Resilient Model Downloads (aria2c port)

**Branch**: `007-robust-model-download` | **Date**: 2026-05-31 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/007-robust-model-download/spec.md`

## Summary

Replace the single-connection `huggingface_hub.snapshot_download(...)` call in
`src/speakloop/installer/downloader.py` with a Python port of the already-
validated `download_aria.sh` shell script: `curl` for the small metadata files,
parse `model.safetensors.index.json` to discover the exact set of shard
filenames, then `aria2c` for the multi-GB shards with parallel connections,
indefinite retry, byte-range resume, and connect-timeout. Spawn `caffeinate
-dimsu -w <parent-pid>` for the duration of `ensure_models(...)` to keep the
Mac awake. Bridge aria2's progress output into the existing Rich console.

Anonymous is the default; when set, the credential is read at runtime from
`$HF_TOKEN` first, then from `~/.cache/huggingface/token` (the file produced by
`huggingface-cli login`), and added as an `Authorization: Bearer ...` header on
both `curl` and `aria2c` calls. No token value is ever committed.

When `aria2c` is missing from `PATH`, the installer auto-falls back to the
current `snapshot_download` path with a one-line Rich warning that names the
missing tool. Validation (`installer/validator.py`) is unchanged and still gates
"model is ready." The per-phase manifest, on-disk layout, consent prompt,
schema_version, and the offline-after-download guarantee are all untouched.

## Technical Context

**Language/Version**: Python 3.12 (pinned `>=3.12,<3.13` in `pyproject.toml`).

**Primary Dependencies (Python)**:
- Existing only: `huggingface_hub`, `rich`. NO new Python dep added.
- `hf-transfer` is currently in `pyproject.toml` but is not activated anywhere
  (no `HF_HUB_ENABLE_HF_TRANSFER` set). Cleanup: drop it from `pyproject.toml`
  in this feature, since the chosen mechanism is aria2 and we are not adding a
  second parallel-download backend.

**Primary Dependencies (system, external to uv)**:
- `aria2c` (≥ 1.36, `brew install aria2`). System binary — not a Python package.
- `caffeinate` (ships with macOS — no install).
- `curl` (ships with macOS — no install).

**Storage**: On-disk model directories under `paths.models_dir()` (existing
layout, slug = `repo_id.replace("/", "__")`); no schema change.

**Testing**: `pytest` with the existing markers (`unit`, `integration`,
`live_asr`). One new opt-in marker proposed: `live_download` for a real
network-touching shell-out smoke test, mirroring `live_asr`.

**Target Platform**: Apple Silicon macOS (constitution Principle VII).

**Project Type**: CLI (single-project layout under `src/speakloop/`).

**Performance Goals**:
- **Throughput**: parallel byte-range pulls should saturate the link well above
  what a single connection achieves; field measurement (see Q4 deferral in
  `checklists/requirements.md`) targets ≥ 2× wall-clock speedup on a shaped
  link, with the empirical 5–10× cited in `download_aria.sh` header for the
  Qwen3-14B-4bit checkpoint as the upper-bound reference.
- **Resilience**: zero manual restarts across an arbitrary number of network
  drops; resume is byte-accurate via aria2's `--continue=true`.

**Constraints**:
- Offline after download: only network traffic is aria2 → HuggingFace.
- No new user-facing command surface (FR-017).
- macOS-only mechanism (Principle VII); fallback path covers the rest.
- Token never committed (FR-013, SC-006).

**Scale/Scope**:
- Up to 4 models per phase (Phase C), summing to ~12 GB on disk.
- Each model is 1 directory; each contains 1 weight file (Whisper, Parakeet,
  Kokoro) or N shards (Qwen3-14B has ~3 shards per the index).

## Constitution Check

*GATE: must pass before Phase 0. Re-evaluated post-design (see end of file).*

| Principle / Constraint | Status | Argument |
|---|---|---|
| **I. English-Only UI** | ✅ Pass | All new console output (progress line, retry status, fallback warning) is English. The single retained Persian comment line in the source script is dropped during the Python port. |
| **II. Offline-First** | ✅ Pass | The only outbound destination remains HuggingFace, used only during the install step. No telemetry / no auto-update introduced (FR-016). |
| **III. Privacy by Design** | ✅ Pass | Nothing user-generated leaves the device. The optional token is read locally, never logged, never sent anywhere except the `Authorization:` header on the HF request. |
| **IV. Modular by Design** | ✅ Pass | All changes confined to `src/speakloop/installer/` (the same module that owns the download seam today). `installer/CLAUDE.md` updated in the same commit per Principle IV. |
| **V. Swappable Engines** | N/A (not an inference engine) | aria2 is the download mechanism, not a TTS/ASR/LLM engine. The spirit (single-wrapper change) is preserved: the only file that calls `aria2c` is `installer/downloader.py`. |
| **VI. Resumable Model Downloads** | ✅ Strengthened | aria2's `--continue=true --max-tries=0` gives byte-range resume AND indefinite retry — strictly stronger than the constitution's "SHOULD use snapshot_download or equivalent." The new mechanism is *more* compliant, not less. |
| **VII. Apple Silicon Primary Target** | ✅ Pass | aria2c + caffeinate are first-class on macOS. The fallback path covers non-mac (no `aria2c` on PATH ⇒ snapshot_download). |
| **VIII. Easy Install for Everyone** | ⚠️ Justified — see Complexity Tracking | Adds one non-Python prerequisite (`brew install aria2`). Mitigated by: (a) FR-019 auto-fallback to `snapshot_download` keeps the no-aria2 path at parity with today; (b) `doctor` reports missing aria2 with the install command; (c) README adds a one-line `brew install aria2` to the install steps. `speakloop --help` still loads no engine packages and still works without models. |
| **IX. Obsidian-Compatible Reports** | ✅ Pass | This feature does not touch the report pipeline. `schema_version` stays at 1. |
| **X. Research is Part of the Repo** | ✅ Pass | A new `doc/research_install.md` is added to record the aria2-vs-hf_transfer-vs-snapshot_download decision and link back to this plan / spec. |
| **XI. AI-Collaborator Friendly** | ✅ Pass | All changes inside one module; per-module `installer/CLAUDE.md` updated in the same commit; no widening of the "context an agent must load" beyond installer/. |
| **XII. Iterative Delivery** | ✅ Pass | The three user stories (P1 resilience, P2 throughput, P3 optional auth) are independently testable slices per the spec. P1 can ship on its own with caffeinate + indefinite retry + resume, even if parallel-streams tuning is iterated afterward. |
| **Constraint: uv / no `pip install`** | ✅ Pass | No new Python dep added (`hf-transfer` is dropped — net deps go down by 1). All Python deps still managed by `uv`. The new external dependency is a system binary outside Python's scope. |
| **Constraint: Model storage location** | ✅ Pass | Per-model directory layout under `paths.models_dir()` is unchanged. |
| **Constraint: External services = HF only** | ✅ Pass | aria2c hits the same `https://huggingface.co/...` URLs the current path hits. No new host. |
| **Dev guideline: stdlib over deps, boring over novel** | ✅ Pass | aria2 is a 20-year-old, ubiquitous parallel HTTP downloader. The Python port uses `subprocess`, `re`, `json` (all stdlib) plus `rich` (already a dep). |

**Result**: Pass with one justified deviation (Principle VIII friction — see
Complexity Tracking).

## Project Structure

### Documentation (this feature)

```text
specs/007-robust-model-download/
├── plan.md              # This file
├── spec.md              # Already created by /speckit-specify + /speckit-clarify
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── downloader-cli-contract.md   # subprocess invocations + flags
│   ├── token-resolution-contract.md # env > file > anon precedence
│   └── progress-bridge-contract.md  # aria2 stdout → Rich Progress
├── checklists/
│   └── requirements.md  # Already created
└── tasks.md             # Phase 2 output (/speckit-tasks - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
src/speakloop/installer/
├── __init__.py          # ensure_models(...) — UNCHANGED public signature
├── consent.py           # UNCHANGED (FR-014)
├── manifest.py          # UNCHANGED (FR-008, FR-009)
├── validator.py         # UNCHANGED (FR-007)
├── downloader.py        # REWRITTEN — orchestrates token → caffeinate →
│                        # metadata (curl) → shard discovery → aria2c → cleanup
├── aria.py              # NEW — subprocess wrapper around aria2c, parses
│                        # progress stdout, drives a Rich Progress, returns
│                        # cleanly on success / raises a typed error on hard fail
├── tokens.py            # NEW — env > ~/.cache/huggingface/token > None
│                        # resolver; pure function, no I/O at import time
├── shards.py            # NEW — parse model.safetensors.index.json,
│                        # return list[str] of unique shard filenames
└── CLAUDE.md            # UPDATED — new file map, new traps,
                         #           constitution VIII justification note

tests/unit/installer/
├── test_downloader.py   # REPLACED — assert correct subprocess invocations,
│                        # fallback path on missing aria2, header presence
│                        # only when token is set
├── test_aria.py         # NEW — progress-line parser, error classification
├── test_tokens.py       # NEW — precedence: env > file > None; no I/O
├── test_shards.py       # NEW — index.json → sorted-unique shard list;
│                        # single-file (no index) → ["model.safetensors"]
├── test_consent.py      # UNCHANGED
├── test_manifest.py     # UNCHANGED
└── test_validator.py    # UNCHANGED

tests/integration/
├── test_phase_a_install_flow.py   # UNCHANGED — uses injected download_fn,
│                                  # so the seam holds
├── test_aria_fallback.py          # NEW — when aria2 absent, falls back to
│                                  # snapshot_download path, prints warning
└── test_caffeinate_lifecycle.py   # NEW — caffeinate spawned at ensure_models
                                   # entry, killed at exit (success or raise)

tests/                              # opt-in live marker
└── live_download_test.py          # NEW (marker: live_download) — real aria2
                                   # against a tiny public HF repo;
                                   # excluded from default suite

doc/
└── research_install.md            # NEW — decision record (aria2 vs hf_transfer
                                   # vs snapshot_download); pinned to this spec
```

**Structure Decision**: single-project layout (matches the existing speakloop
repo); all changes live under `src/speakloop/installer/` with mirroring test
modules under `tests/unit/installer/` and one new integration test pair.

## Complexity Tracking

> Filled because the Constitution Check flagged Principle VIII friction.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| New non-Python prerequisite `brew install aria2` (Principle VIII friction). | aria2 is the mechanism that delivers FR-001 (parallel streams), FR-002 (byte-accurate resume), and FR-003 (indefinite retry) at the quality the spec requires. The user's pre-validated `download_aria.sh` proves the configuration works on their constrained link. | (a) **Stay on `snapshot_download` only** — rejected: this is the status quo, which the spec exists to replace. (b) **Use `hf-transfer` (rust-backed parallel downloader, already a transitive dep)** — rejected: hf_transfer does not implement indefinite outer-loop retry (FR-003) and does not address caffeinate (FR-004); to add those we would re-implement most of the script anyway and still depend on a less-validated path. (c) **Write a Python `aiohttp`-based parallel downloader from scratch** — rejected: more code to maintain, no field validation, violates "boring over novel" dev guideline. (d) **Ship aria2 as a vendored binary** — rejected: vendoring native binaries crosses a much larger boundary (license tracking, code signing, notarization for distribution) than asking for one `brew install`. |

Mitigations that bring the friction back inside the constitution's intent:
- FR-019 auto-fallback keeps `git clone && uv run speakloop` working at parity
  with today even without aria2.
- `doctor` will surface the missing tool with the exact `brew install aria2`
  command, addressing Principle VIII's "guide the user through setup" intent.
- README adds a single line `brew install aria2` to the prerequisites,
  consistent with the existing `uv` prerequisite.

## Post-Design Constitution Re-Check

Re-evaluated after writing Phase 0 (research.md) and Phase 1
(data-model.md / contracts/ / quickstart.md):

- Principle V is **N/A but spirit preserved**: confirmed that the only file
  importing/invoking aria2 is `installer/downloader.py` (through the
  `installer/aria.py` helper). Other modules see the same `ensure_models(...)`
  signature.
- Principle VI is **strengthened**, not weakened.
- Principle VIII justification holds: the contracts spell out the fallback
  path and the `doctor` integration; no additional friction was introduced
  during design.
- No new NEEDS CLARIFICATION emerged during research / design.
- No additional Python deps needed beyond what was already declared.

**Result**: Constitution Check passes post-design with the same single
justified deviation tracked above. Ready for `/speckit-tasks`.
