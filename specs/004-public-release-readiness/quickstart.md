# Quickstart: clone → first session report

This mirrors what the rewritten root README walks a first-time visitor through
(US1 / SC-A: a finished report in under 15 min, excluding model download).

## Prerequisites
- macOS on Apple Silicon (M-series).
- Python 3.12 and [`uv`](https://docs.astral.sh/uv/).
- A working microphone (for the attempt phase; `--listen-only` skips it).

## 1. Clone and install
```bash
git clone <repo-url> speakloop
cd speakloop
uv sync
uv run speakloop --help        # works with no models downloaded (Principle VIII)
```

## 2. Find and (optionally) edit the questions
The default questions ship in the repo at `content/questions.yaml` — open and edit it
directly; no home-directory path involved.

To use a personal set instead, place it at `~/.speakloop/qa.yaml` (it wins over the
repo default) or pass `--qa-file PATH`. Precedence: `--qa-file` → `~/.speakloop/qa.yaml`
→ `content/questions.yaml`.

## 3. Run a session
```bash
uv run speakloop practice
```
First run consents to and downloads the models (size disclosed; resumable). Then:
listen to the question + ideal answer, press space, and record your 4/3/2 attempts.

To try the loop without a microphone or models-for-recording first:
```bash
uv run speakloop practice --listen-only
```

## 4. Read the report
The session writes a Markdown report under `data/sessions/YYYY-MM-DD-qXX.md`. It opens
cleanly as an Obsidian note and contains:
- a top-level `asr:` provenance block (which engine/model ran, whether it fell back),
- fluency metrics per attempt,
- grammar patterns (Phase C) and a single `top_priority` line — or a fluency-only
  narrative if the LLM is absent (the `phase_c_error` field records why).

## 5. When something goes wrong
See the README **Known limitations** and **Troubleshooting** sections: model-download
resume, LLM feedback degrading to fluency-only, misheard technical terms + domain
biasing, the pinned `silero-vad` version conflict, macOS microphone permission, and the
known final-attempt recording-loop hang (interim Ctrl-C abort).

## Verifying the release gates (maintainers)
```bash
uv run pytest tests/integration/test_path_portability_audit.py   # SC-B / SC-G: zero leaks, < 2 s
uv run pytest                                                     # existing suite stays green (FR-005)
```
