# CLI command contract — speakloop v1

This document defines the user-facing CLI surface. Every subcommand here is a stable contract; renaming or removing one is a breaking change.

## Entry point

```text
uv run speakloop [GLOBAL OPTIONS] <COMMAND> [COMMAND OPTIONS]
```

After `uv tool install`, the bare binary `speakloop ...` is equivalent.

## Global options

| Flag | Type | Default | Purpose |
|------|------|---------|---------|
| `--help` | flag | n/a | Print help and exit 0. **MUST succeed with no models present** (FR-018). |
| `--version` | flag | n/a | Print `speakloop x.y.z`. |
| `--qa-file PATH` | path | `~/.speakloop/qa.yaml` | Override the Q&A file location. |
| `--models-dir PATH` | path | `~/.speakloop/models` | Override the model directory (XDG-compliant alternative supported). |

## Subcommands

### `speakloop practice` (Phase A in listen-only form; extended in Phase B/C)

Run a practice session. With no flags, presents an interactive picker of available questions and walks through the full loop the current phase supports.

| Flag | Type | Default | Purpose |
|------|------|---------|---------|
| `--question ID` | string | none (interactive) | Skip the picker; jump to this question. |
| `--listen-only` | flag | false (Phase B+); true (Phase A) | Skip the attempt phase even when ASR is installed. |

**Exit codes**:

| Code | Meaning |
|------|---------|
| 0 | Session completed; report written (B/C) or session ended cleanly without report (A). |
| 1 | Configuration error (Q&A parse failure, missing models, etc.). |
| 130 | User aborted with Ctrl+C. **No report is written for this exit code** (FR-016). |

### `speakloop doctor`

Run the health-check. Exits non-zero if any check fails (FR-026).

| Flag | Type | Default | Purpose |
|------|------|---------|---------|
| `--json` | flag | false | Emit results as JSON for scripting; default is `rich`-rendered tables. |

**Output sections** (FR-024):

1. Python runtime: version, executable path.
2. Models: each required model's path, presence, expected size, validated size or checksum status.
3. Audio output: default device name, sample rate.
4. Audio input: default device name, sample rate. *(only required in Phase B+)*
5. Filesystem: `data/sessions/` exists and is writable.

Each section line has a status icon — `OK` / `WARN` / `FAIL` — and a one-line remediation hint on failure (FR-025).

### `speakloop trends` *(Phase C)*

Read all reports under `data/sessions/`, render an aggregated summary in the terminal.

| Flag | Type | Default | Purpose |
|------|------|---------|---------|
| `--sessions-dir PATH` | path | `data/sessions/` | Override the report directory. |
| `--top-patterns N` | int | 10 | How many grammar patterns to rank. |
| `--since YYYY-MM-DD` | date | unlimited | Filter to reports started on or after this date. |

**Empty state**: with zero report files, exits 0 and prints a one-paragraph hint pointing at `speakloop practice` (FR-033).

## First-run flow (FR-019..FR-021)

`speakloop practice` calls the installer before doing any work. `speakloop trends` and `speakloop doctor` do **not** — they only read state. The installer:

1. Computes which models are needed for the requested phase. `practice` escalates to phase `A` with `--listen-only`, phase `B` otherwise. **Phase `C` (the LLM) is not auto-installed by any CLI command in v1**; fetch it by invoking the installer module directly:

   ```bash
   uv run python -c "from speakloop.installer import ensure_models; from rich.console import Console; ensure_models('C', console=Console())"
   ```

2. For each model NOT validated locally, lists name + HF repo + size + target path.
3. Sums sizes; prints total disk footprint.
4. Asks `Proceed with download? [y/N]:` — **default is N** (decline-by-default is safer for consent flows).
5. On `n` or EOF, exits 1 without writing any file.
6. On `y`, calls `huggingface_hub.snapshot_download(... resume_download=True)` for each model in turn, with `rich.progress` shown.

`speakloop --help` does NOT trigger anything but help printing — it MUST work without models (FR-018).

## Help-text language

All command help, error messages, and prompts are in English (FR-036, Constitution Principle I). No localization layer in v1.
