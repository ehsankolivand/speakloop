# Quickstart — speakloop v1 on a fresh Apple Silicon Mac

This is the path a brand-new user follows from `git clone` to a finished session report. Each step is the smallest possible action that delivers user-visible progress; if a step fails, the next step's diagnostic tells you exactly what to fix.

> **Phase awareness.** speakloop ships in three phases (`A` → `B` → `C`). This quickstart shows the full Phase C experience. If you install while only Phase A is merged, steps 5–7 are replaced by step 4's listen-only loop and `speakloop trends` is unavailable; everything else is the same.

## 1. Prerequisites

- macOS on Apple Silicon (M1 or newer). See Constitution Principle VII — Intel Macs are best-effort and not gating in v1.
- Python 3.12 available. Check with `python3.12 --version`. If absent: `brew install python@3.12`.
- `uv` available. Install per <https://docs.astral.sh/uv/>; e.g. `brew install uv`.
- Working speakers / headphones for Phase A; working microphone added in Phase B.
- ~8 GB free disk space if you intend to install all three models (TTS + ASR + LLM).

## 2. Clone and set up

```bash
git clone <repo-url> speakloop
cd speakloop
uv sync           # creates .venv, installs the project + dependencies
```

`uv sync` resolves Python 3.12 automatically, creates an in-tree `.venv`, and installs the project in editable mode. No models are touched yet.

## 3. Verify the install

```bash
uv run speakloop --help
```

This MUST succeed even with no models present (FR-018, SC-006). You will see a summary of the three subcommands: `practice`, `doctor`, `trends`.

```bash
uv run speakloop doctor
```

You will see a checklist with `OK` / `WARN` / `FAIL` per check. On a fresh machine, the models section will say `FAIL` with the remediation hint "Run `speakloop practice` to consent and download." That is expected.

## 4. First practice session — listen only (works at the end of Phase A)

```bash
uv run speakloop practice --listen-only
```

The installer flow runs first:

1. The tool prints the list of models needed for listen-only — in v1 that is **Kokoro-82M (~370 MB on disk; ~170 MB of bf16 weights + voice packs)** to `~/.speakloop/models/mlx-community__Kokoro-82M-bf16/`.
2. Prompt: `Proceed with download? [y/N]:` — type `y` to consent.
3. A `rich` progress bar shows the download. **If you Ctrl+C now, the partial file is preserved; re-running resumes from the existing byte offset** (FR-021, SC-002).
4. After validation, the question picker opens. Arrow keys to pick a question from the starter file.
5. You hear the question, then the ideal answer. Replay with `r`. Quit with `q`.

No microphone is required for this step. No report is written (Story 1 acceptance scenario 3).

## 5. First full session — attempts + interim report (works at the end of Phase B)

```bash
uv run speakloop practice
```

The installer prompts again for the additional models (Parakeet ASR ~2.4 GB). After consent and download:

1. Question picker — choose one.
2. Listen to question + ideal answer (replay as needed).
3. Press space when ready. **Attempt 1 begins**: a 4-minute countdown appears; speak your answer. Press `Enter` to end early.
4. **Attempt 2** (3 minutes) — same UX.
5. **Attempt 3** (2 minutes) — same UX.
6. The tool transcribes the three attempts and writes an interim Markdown report under `data/sessions/YYYY-MM-DD-<question-id>.md` with frontmatter, per-attempt metrics, and transcripts. The `grammar_patterns:` block is `[]` and `generated_by_phase: B`.
7. Open `data/sessions/` as an Obsidian vault to review.

## 6. Full report with grammar feedback (Phase C)

Phase C is opt-in. `speakloop practice` auto-installs Phase A (listen-only) or Phase B (default); it does **not** auto-install the Phase-C LLM. Fetch it explicitly via the installer module:

```bash
uv run python -c "from speakloop.installer import ensure_models; from rich.console import Console; ensure_models('C', console=Console())"
```

This goes through the same consent prompt, size disclosure, and resumable-download flow as `practice`, and writes **Qwen3-8B-4bit (~4.62 GB)** to `~/.speakloop/models/mlx-community__Qwen3-8B-4bit/`. (Direct `huggingface-cli download` works for the bytes but bypasses the consent prompt, manifest validation, and target-path logic — prefer the installer module.)

After the download completes, the next `uv run speakloop practice` session detects the Phase-C model via the validator check in `cli/practice.py` and automatically wires the LLM grammar analyzer into the report. The resulting report has the **Grammar patterns** section with evidence quotes and `generated_by_phase: C`.

_Future work_: v2 should expose this as a first-class `speakloop install --phase C` subcommand (or auto-escalate `practice` to Phase C with consent), and route the doctor remediation message through it.

## 7. Review your progress (Phase C)

```bash
uv run speakloop trends
```

Renders a `rich` table: total sessions, date range, fluency-metric trajectories (attempt 3 across sessions), and the top-10 recurring grammar patterns ranked by total occurrence count.

## 8. Personalize the Q&A

The starter file ships at `src/speakloop/content/starter.yaml` and is copied to `~/.speakloop/qa.yaml` on first run. Edit `~/.speakloop/qa.yaml` in any text editor; new entries appear in the picker on the next run. See `specs/001-v1-product-spec/contracts/content-schema.yaml` for the schema.

If you save invalid YAML, the next session prints the parse error with the file path and line number, and exits cleanly (FR-029).

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `speakloop --help` is slow (> 2 s) | Heavy import in the CLI module before argument parsing | This is a bug — file an issue. Help MUST work without touching models. |
| Download restarts from zero after Ctrl+C | Resumable-download contract is broken | This is a bug — file an issue. The `.incomplete` part file should be present. |
| Report file is empty after Ctrl+C | Bug — atomic-write contract is broken | This is a bug — file an issue. No partial report should ever land. |
| Doctor says microphone missing on a Mac with a built-in mic | macOS Privacy → Microphone permission for your terminal app is denied | Grant the permission in System Settings, rerun. |
| Ctrl+C left a `.tmp` file in `data/sessions/` | Signal handler ran before the temp file could be cleaned | Safe to delete manually; the next session will not reuse it. |

## What is intentionally NOT in v1

Pronunciation feedback, GUI, mobile, cloud sync, multi-user accounts, voice cloning, real-time conversation, cross-platform binaries beyond macOS arm64, auto-update mechanisms — see `spec.md` § Assumptions.
