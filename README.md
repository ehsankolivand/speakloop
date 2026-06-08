# speakloop

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
![Platform: macOS Apple Silicon](https://img.shields.io/badge/platform-macOS%20Apple%20Silicon-lightgrey.svg)
![Status: v1](https://img.shields.io/badge/status-v1-brightgreen.svg)

**Practice answering technical-interview questions out loud — fully offline, on your
own Mac, with feedback that respects your privacy.**

speakloop is a command-line tool for non-native-English software engineers preparing
for senior-level interviews at international companies. You listen to a natively-spoken
interview question and an ideal answer, then attempt your own answer under time pressure
using the 4/3/2 method (the same answer in 4, then 3, then 2 minutes). After each
session it writes a Markdown report — fluency metrics, grammar patterns, and the single
most important thing to fix next — that you can review later in any editor or Obsidian.

Everything runs locally. Three AI models (text-to-speech, speech recognition, and a
language model) live on your machine. After the one-time model download, **speakloop
makes zero network calls** — no telemetry, no uploads, your voice never leaves the
device.

## Who it's for

- You are comfortable in a terminal and a Python environment.
- You are preparing for English-language technical interviews and want to practice
  *speaking*, not just reading.
- You want a private, offline tool that respects your time and bandwidth.

If you want a polished consumer app with a GUI and a cloud account, this is not that —
and deliberately so.

## Platforms & status

- **Supported platform**: macOS on Apple Silicon (M-series), Python 3.12.
- **Status**: v1. Usable end-to-end; see [Known limitations](#known-limitations) for the
  honest edges. Intel Macs, Linux, and Windows are out of scope for v1.
- **License**: [MIT](LICENSE).

## Install

You need [`uv`](https://docs.astral.sh/uv/) and a microphone.

```bash
brew install aria2        # Recommended for faster, more resilient downloads on slow links — without it, speakloop falls back to a single-connection download.
git clone https://github.com/ehsankolivand/speakloop.git
cd speakloop
uv sync
uv run speakloop --help   # works immediately — no models required just to read help
```

The first time you run a real session, speakloop asks for consent and downloads the
models, disclosing each model's size and the total disk footprint before anything is
fetched. Downloads are resumable — a dropped connection picks up where it left off.

## Quickstart

```bash
# 1. See what a session looks like without a mic or recording — listen only:
uv run speakloop practice --listen-only

# 2. Run a full session (records your spoken attempts):
uv run speakloop practice

# 3. Review your progress across sessions:
uv run speakloop trends
```

A full session plays the question and the ideal answer, then prompts you to record your
4/3/2 attempts. When it finishes it saves a report and offers an interactive debrief
(replay the question, hear your feedback read aloud, or move on). Start to first saved
report is a few minutes once the models are downloaded.

The questions you practice with ship in the repo — see
[Where things live](#where-things-live) — so a fresh clone is ready to use immediately.

## Cloud mode (optional)

If your Mac can't run the local Qwen feedback model (it needs ~10 GB of free unified
memory), you can route **just the grammar feedback step** to an OpenRouter-hosted model
instead. Speech and transcription stay local; the default offline experience is unchanged
if you don't pass `--cloud`.

> Privacy note: cloud mode sends your **attempt transcript text** to OpenRouter for
> analysis. Your audio recordings and saved reports never leave your machine. The default
> (local) mode sends nothing anywhere.

```bash
# Get a key at https://openrouter.ai/keys, then:
uv run speakloop practice --cloud
# First run prompts once for your token and stores it at ~/.speakloop/openrouter_token.
# Prefer an env var? export OPENROUTER_API_KEY=sk-or-... (it takes precedence, no prompt).
```

- **Change the model** (default `qwen/qwen3.7-max`) — edit one line in
  `~/.speakloop/openrouter.yaml`:
  ```yaml
  model: anthropic/claude-3.5-sonnet
  ```
- **Tune cloud feedback** — edit `~/.speakloop/openrouter_prompt.txt` (seeded on first cloud
  run; separate from local mode's prompt).
- **Check status** — `uv run speakloop doctor` shows the active model id, whether a token is
  configured, and the prompt-file path.
- **Bad/missing token?** The error tells you how to update the token or just drop `--cloud`
  to use the local model.

## What you get: an example report

Every session writes a Markdown file with a YAML frontmatter block. Here is a
**generic, hand-authored** example (not a real recording) so you know what to expect
before you run anything:

```markdown
---
schema_version: 1
session_id: 2026-01-15-android-lifecycle-example
started_at: 2026-01-15T09:00:00-08:00
question_id: android-lifecycle-example
question: |
  Walk me through the Activity lifecycle callbacks on a configuration change.
attempts:
  - ordinal: 1
    time_budget_seconds: 240
    actual_duration_seconds: 232
    metrics:
      words_total: 290
      speech_rate_wpm: 92.0
      filler_words_count: 16
      filler_density_per_100_words: 5.5
      pauses_count: 19
      mean_pause_ms: 650
      self_corrections_count: 4
grammar_patterns:
  - label: Missing article before singular noun
    occurrence_count: 3
    impact_rank: 1
    explanation: |
      Persian has no indefinite article, so "a/an" is often dropped before
      English singular count nouns. This is the highest-impact pattern this session.
    evidence:
      - attempt_ordinal: 1
        quote: the system creates new Activity instance
        corrected: the system creates a new Activity instance
    suggested_fix: Add "a/an" before singular count nouns introduced for the first time.
top_priority: |
  Add articles before singular nouns — it appeared 3 times and most affects clarity.
asr:
  engine: whisper-mlx
  model: mlx-community/whisper-large-v3-turbo
  initial_prompt: |
    Android, Activity, lifecycle, onCreate, onDestroy, configuration change.
  initial_prompt_sha256: 1f0c…(truncated)
  vad:
    threshold: 0.5
    min_silence_ms: 300
  fell_back: false
generated_by_phase: C
---

# Body
... human-readable narrative + per-attempt feedback render below the frontmatter ...
```

Reading top to bottom:

- The **`asr:` provenance block** records which speech-recognition engine and model
  actually ran, the per-session domain biasing prompt (and its hash), the
  voice-activity-detection settings, and whether the engine fell back to the backup.
  If a term was misheard, this block tells you exactly what produced the transcript.
- Each **grammar pattern** carries a label, how many times it occurred, an explanation
  of *why* the pattern happens, an evidence quote with a corrected version, and a fix.
- The **`top_priority`** line is the single most impactful thing to work on next,
  chosen across all grammar and fluency signals.

If the language model is not installed, the report degrades gracefully to fluency-only
metrics and a fluency narrative (see [Known limitations](#known-limitations)).

## Where things live

- **Reports** Reports are saved under data/sessions/ as YYYY-MM-DD-qXX.md. Open that folder
  as an [Obsidian](https://obsidian.md) vault to browse, link, and tag past sessions —
  the files are plain Markdown, so any editor works too.
- **Questions** ship in the repo at [`content/questions.yaml`](content/questions.yaml).
  Open and edit that file directly — add, remove, or reword questions; no
  home-directory path is involved. Each entry has an `id`, a `question`, an
  `ideal_answer`, and optional `tags` / `difficulty`.

### Use your own question set

You don't have to edit the shipped file. speakloop resolves the active question file by
precedence (first match wins):

1. `--qa-file PATH` — an explicit path you pass on the command line.
2. `~/.speakloop/qa.yaml` — a personal override file in your home directory, used
   automatically **if it exists**. It takes precedence over the in-repo default.
3. `content/questions.yaml` — the in-repo default.

So to practice with a private set, either pass `uv run speakloop practice --qa-file
~/my-questions.yaml`, or drop your file at `~/.speakloop/qa.yaml` and it will be picked
up on its own. Nothing is created in your home directory unless you put it there.

## For contributors

- The project is governed by its [constitution](.specify/memory/constitution.md)
  (offline-first, modular, swappable engines, English-only, MIT — the non-negotiables).
- Feature specs, plans, and research live under [`specs/`](specs/), and the
  architecture map plus per-module guides start at the top-level
  [`CLAUDE.md`](CLAUDE.md).

## Known limitations

This is **v1**. It works end-to-end, but be aware of these honest edges before you rely
on it:

- **Accented technical jargon can be misheard.** Speech recognition is biased toward
  each question's domain terms, but a strong L1 accent on dense technical vocabulary can
  still produce wrong transcripts. The `asr:` block in each report shows what was used so
  you can judge transcript quality.
- **Language-model feedback can fail and degrade to fluency-only.** If the LLM is not
  installed or errors out, the session still completes — you get fluency metrics and a
  fluency narrative instead of grammar patterns. The report records why (see
  troubleshooting below).
- **Audio replay exists; full pronunciation feedback does not.** You can replay the
  question and the ideal answer, and hear your feedback read aloud, but speakloop does
  not yet score your pronunciation at the phoneme level.

## Troubleshooting

Each entry is **symptom → cause → fix**.

### Model download failed partway through

**Cause:** the network dropped during the one-time model download from Hugging Face.

**Fix:** just re-run the same command — downloads are resumable and pick up where they
left off; nothing already on disk is re-fetched. Behind a proxy or in a
network-restricted environment, set the standard `HTTPS_PROXY` / `HF_ENDPOINT`
environment variables before running, or download on an unrestricted network and copy
the `~/.speakloop/models/` directory over. This is a normal recoverable condition, not a
bug.

### My feedback only shows fluency metrics — no grammar patterns

**Cause:** the Phase C language model was unavailable, so the session degraded to
fluency-only. The report's **`phase_c_error`** frontmatter field records the cause: if
it is absent the model simply was not installed; if it contains a message, the analyzer
raised that error during the session.

**Fix:** confirm the LLM is installed (run `uv run speakloop doctor`); if it is missing,
run a session again and accept the model download when prompted. If `phase_c_error`
shows a runtime message, that session fell back on purpose so the failure is diagnosable
from the saved file — re-running usually succeeds.

### A technical term came out wrong in the transcript

**Cause:** speech recognition mis-transcribed accented domain vocabulary. speakloop
biases each session toward the question's terms (the `initial_prompt` shown in the
report's `asr:` block), but biasing is not perfect.

**Fix:** add the terms you use to the relevant question's `tags`/answer wording in your
question file so they feed the per-session biasing prompt. Improving raw accuracy beyond
this is a **known v1 limitation** — see [Known limitations](#known-limitations).

### Voice activity detection errors after upgrading dependencies

**Cause:** the `silero-vad` dependency is version-pinned; a newer, incompatible version
got installed and changed the VAD API.

**Fix:** restore the pinned versions with `uv sync` (it resolves from the committed
`uv.lock`). The dependency is pinned deliberately because VAD/Whisper APIs have drifted
between releases; only bump it on a scheduled update window.

### macOS won't let speakloop use the microphone

**Cause:** macOS blocks microphone access until you grant permission to the terminal app
running speakloop (this happens on first run).

**Fix:** open **System Settings → Privacy & Security → Microphone** and enable your
terminal (Terminal, iTerm, VS Code, etc.), then re-run. `uv run speakloop doctor`
reports microphone status if you are unsure.

### The recording loop seems to hang at the final attempt

**Cause:** a known issue where the recording loop can fail to advance on the last 4/3/2
attempt.

**Fix (interim):** press **Ctrl-C** to abort the attempt cleanly — the signal handler
removes any partial temporary files and exits. This is a **known v1 limitation**; the
underlying fix is deferred to a future version.

### I want to switch from my old ~/.speakloop/qa.yaml to the in-repo questions

**Cause:** the home-directory file `~/.speakloop/qa.yaml` is treated as a personal
override and takes precedence over the in-repo default per the resolution order.

**Fix:** delete or rename `~/.speakloop/qa.yaml`. With no override present, speakloop
falls back to the in-repo default `content/questions.yaml` automatically.

## License

## Found this useful?

If speakloop helps your interview prep, a star on GitHub is appreciated. If you have ideas, bugs, or want to add Persian-L1 grammar patterns, issues and PRs are welcome.

---

MIT. See [LICENSE](LICENSE).
