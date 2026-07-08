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

It runs as an **adaptive daily loop**, not a one-shot drill: each session opens with a
short warm-up on your top recurring error, ends with **1–2 unscripted spoken follow-up
questions** built from what you actually said, scores **content coverage** of the key
points (separating wrong facts from grammar mistakes), and **schedules** each question for
spaced repetition so weak answers come back sooner. Definition, behavioral/STAR, and
hypothetical question types are supported.

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

You need [`uv`](https://docs.astral.sh/uv/) — the Python toolchain that runs speakloop — and
a microphone. If you don't have `uv` yet, install it first:

```bash
brew install uv           # or: curl -LsSf https://astral.sh/uv/install.sh | sh
```

Then clone the repo and let `uv` build the environment. `uv sync` creates the project's
virtual environment and installs the pinned dependencies for you — there is no `pip install`
and no separate "activate the venv" step; every command runs through `uv run`:

```bash
brew install aria2        # Recommended for faster, more resilient downloads on slow links — without it, speakloop falls back to a single-connection download.
git clone https://github.com/ehsankolivand/speakloop.git
cd speakloop
uv sync                   # build the environment from the committed lockfile
uv run speakloop --help   # works immediately — no models required just to read help
uv run speakloop setup    # pick your feedback engine + download only what it needs
```

### Update to the latest version

Already cloned speakloop? Pull the newest code, then **re-run `uv sync`** so your installed
commands match the updated source. That second step is what keeps you from running a stale
build where old commands linger or a new one looks "missing":

```bash
git pull                  # fetch the latest code
uv sync                   # reconcile the environment with the updated lockfile
uv run speakloop --help   # confirm the commands you expect are listed
```

`speakloop setup` is the one-step onboarding: it asks which **feedback engine** you want
(see [Choose your feedback engine](#choose-your-feedback-engine)), remembers your choice,
and downloads **only** the models that engine needs — disclosing each model's size and the
total disk footprint before anything is fetched, with consent. Downloads are resumable: a
dropped connection picks up where it left off. (You can also skip `setup` and just run
`speakloop practice` — it provisions what's needed on first use the same way.)

## Quickstart

```bash
# 1. See what a session looks like without a mic or recording — listen only:
uv run speakloop practice --listen-only

# 2. See what to practice today (the spaced-repetition due queue):
uv run speakloop today

# 3. Run the full daily loop (records your spoken attempts):
uv run speakloop practice

# 4. Review your progress across sessions:
uv run speakloop trends
```

A full session runs the adaptive loop: a 30–60-second **warm-up drill** on your top
recurring error, then the question and ideal answer, your **4/3/2 timed attempts**, then
**1–2 spoken follow-up questions** drawn from what you actually said (answer them by
voice within ~60 s each), and finally a report + interactive debrief. The report adds
**content coverage** (which key points you hit, round over round), **content errors**
(facts contradicting the ideal answer, kept separate from grammar), **pronunciation
flags**, and **per-pattern trends** versus past sessions. Prefer the classic
single-question flow? Add `--no-warmup --no-followups`. Start to first saved report is a
few minutes once the models are downloaded.

Two more commands:

- `uv run speakloop rebuild` — rebuild the cross-session store (schedule + trends) from your
  saved reports. It's only a cache: delete it any time and it's reconstructed from the reports.
- `uv run speakloop resume` — finish a session whose analysis was interrupted (e.g. the model
  was unavailable mid-session) without re-recording — your audio and transcripts are never lost.

The questions you practice with ship in the repo — see
[Where things live](#where-things-live) — so a fresh clone is ready to use immediately.

## Choose your feedback engine

Speech (text-to-speech) and transcription (speech recognition) **always run locally** — they
are always downloaded. Only the **grammar/coaching feedback** step has a choice of engine:

| Engine | What runs feedback | Downloads the large local LLM? | Needs |
|--------|--------------------|-------------------------------|-------|
| `local` (default) | offline Qwen model on your Mac | **yes** (~8 GB) | enough free unified memory |
| `openrouter` | a cloud model via OpenRouter | no | an OpenRouter API key |
| `claude` | your local Claude Code CLI | no | Claude Code installed + logged in |

Pick one **once** and speakloop remembers it — you don't pass a flag on every run:

```bash
uv run speakloop setup --engine openrouter   # persists your choice to ~/.speakloop/loop.yaml
uv run speakloop setup --engine local        # also downloads the local feedback model
uv run speakloop setup --engine claude
uv run speakloop setup --engine openrouter --no-download   # set the default now, fetch later
```

If you choose a cloud engine, the large local feedback model is **never downloaded**. If you
choose `local` and decline its download, sessions still record and save — you just get
fluency-only feedback until you fetch the model (finish later with `speakloop resume`).

- **Override for a single run** without changing your default: `uv run speakloop practice
  --engine local` (or `--engine claude`, `--engine openrouter`).
- **`--cloud` is an exact alias for `--engine openrouter`** — both select the OpenRouter
  engine; using `--cloud` with a different `--engine` is rejected.
- **Check readiness anytime**: `uv run speakloop doctor` names your active engine, says
  whether its requirements (models, credentials, or the Claude Code login) are satisfied, and
  prints the exact next step for anything missing — and it won't flag the local model as
  missing if your active engine doesn't need it.

## Cloud mode (optional)

This is the **openrouter** engine in detail (see [Choose your feedback
engine](#choose-your-feedback-engine)). If your Mac can't run the local Qwen feedback model
(it needs ~10 GB of free unified memory), you can route **just the grammar feedback step** to
an OpenRouter-hosted model instead. Speech and transcription stay local; the default offline
experience is unchanged if you don't select a cloud engine. Make it your default once with
`speakloop setup --engine openrouter`, or opt in per run with `--cloud` (an alias for
`--engine openrouter`).

Cloud mode also adds a **coaching section** to the report: a clean rewrite of *your own*
answer, the 2–3 highest-impact habits to fix (with a rule and a self-check cue), and 4–8
paste-ready cloze **Anki cards** — so the report teaches you everything without a second tool.
The coaching is best-effort: if that step fails, you still get the full grammar report. Before
it's shown, the coaching is **fact-checked against the question's reference answer** — any claim
that contradicts it is corrected or dropped, so the report never teaches you something wrong.

> Privacy note: cloud mode sends your **attempt transcript text** to OpenRouter for
> analysis. Your audio recordings and saved reports never leave your machine. The default
> (local) mode sends nothing anywhere. (The coaching step sends the same transcripts to the
> same provider — and never your question's reference answer.)

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
- **Tune the coaching section** — edit `~/.speakloop/openrouter_coach_prompt.txt` (also seeded
  on first cloud run; independent of the grammar prompt above).
- **Check status** — `uv run speakloop doctor` shows the active model id, whether a token is
  configured, and both prompt-file paths.
- **Bad/missing token?** The error tells you how to update the token or just drop `--cloud`
  to use the local model.

## Pronunciation trainer (optional)

speakloop includes a **read-aloud pronunciation trainer** built around a tight
**hear → say → see → retry** loop: it **plays the target aloud** (local TTS) so you hear the
correct pronunciation first (press **`r`** to replay it), you read it aloud, it **shows** which
sound was off, and when a sound is flagged it gives you an **immediate retry on the same item** so
you fix it while it's fresh. Practice is **sentence-led** (natural sentences, with minimal-pair
words as targeted follow-ons), and it **focuses on the sounds you keep missing**.

You can run it two ways:

- **During an interview session** — it fills the otherwise-idle wait while your spoken-answer
  feedback is generated. A **Pronunciation drills** section is added to the report, which appears
  only after **both** the drills and the feedback finish.
- **Standalone** — `uv run speakloop pronounce` runs the same loop on its own, for as long as you
  like (press **q** to stop). Because no feedback engine is loaded, it's gated by **free memory
  only**, so it's available in the common case even with the default local engine. It needs no
  speech-recognition model and writes no session report — just a short summary of your trickiest
  sounds. Use `--limit N` to cap the sentences per round.

It is **opt-in**, **offline after a one-time download**, and (in a session) **gated by engine +
free memory** so it never risks freezing your Mac:

- The pronunciation model is heavy (~1.3 GB on disk, ~2–3 GB in memory). With a **cloud feedback
  engine** (`--engine openrouter` / `--engine claude`) the large local feedback model isn't
  resident, so there's room — drills are **offered**.
- With the **local** feedback engine (the default), loading the pronunciation model on top of the
  resident Qwen model would likely exhaust memory, so drills are **skipped** with a plain reason
  (switch to a cloud engine to enable them). They're also skipped when free memory is low.
- If drills are skipped but you insist, the tool offers an explicit override behind a clear
  *"this may freeze your machine"* confirmation.

Control it in `~/.speakloop/loop.yaml` (all keys optional, silent defaults):

```yaml
pronunciation_drills: auto      # auto (offer when safe — default) | on | off
pronunciation_min_free_mb: 4500 # free RAM needed before drills are offered (in-session + standalone)
pronunciation_tts_playback: true # play the target before each drill (hear-first); false to skip
pronunciation_retries: 1        # bounded retries per flagged sound (0 = one shot; max 3)
```

Per-run override: `uv run speakloop practice --drills` (offer this run) / `--no-drills` (skip
this run) — the safety gate still applies. The first time you opt in (in a session or via
`pronounce`), the model is downloaded through the same resilient (parallel, resumable) downloader
as every other model, after disclosing its size; a user who never opts in never downloads it.
`uv run speakloop doctor` shows whether the model is present, your settings, and whether drills
would be offered both in-session and standalone.

**Honest calibration**: detection ("a sound was off") is reliable; any specific guess
("heard as …") is shown as a *suggestion*, not a verdict; a retry that fixes a sound is reported
encouragingly, never as a grade. Scoring is **read-aloud only** — your spontaneous answers are not
scored. `speakloop resume` and `--listen-only` do not run drills. (Future: stress/intonation
scoring; scoring your actual answers.)

## Self-practice modes (optional)

Two more **standalone, offline** trainers. Like the pronunciation trainer they run outside an
interview session, are **user-paced**, and **write no report** — and both reuse material the app
already has, so there is nothing new to author.

### Rescue-lines deck — `speakloop deck`

Spaced repetition of **your own corrected lines**. After a few sessions the analyzer has recorded,
for each grammar slip, what you said and the **"Better:"** correction. `deck` turns those into
flashcards and drills the ones due today:

```bash
uv run speakloop deck                       # drill the cards due today
uv run speakloop deck --limit 10            # cap this run to 10 cards
uv run speakloop deck --export cards.txt    # export to an Anki cloze file (offline), then exit
```

Each due card runs **hear → say → see → self-mark**: it **speaks the corrected line** (local TTS,
press **`r`** to replay), you say it aloud, it reveals the target (*You said* / *Better* / the
rule), and you **self-mark** *again / hard / good / easy* — which reschedules the card on the same
spaced-repetition ladder used for whole questions, until it sticks. Progress persists between runs.
A brand-new user with no history still gets a **bundled starter set** of high-value interview
phrases ("let me walk you through…", "the trade-off here is…").

`deck --export` writes an **Anki cloze-import file** — the changed word wrapped in `{{c1::…}}` with
a short rule hint — bringing a previously cloud-only convenience to the fully-local path. The deck
is **TTS-only** (no microphone, no recognition model) and cards are always rebuildable from your
session reports. Cap the daily run in `~/.speakloop/loop.yaml` with `deck_daily_capacity: 20` (or
per run with `--limit`).

### Answer shadowing — `speakloop shadow`

Shadowing over the **real interview material**. Pick a question and `shadow` splits its ideal
answer into sentences; for each it **speaks the sentence**, you **repeat it**, and it gives
**deterministic, offline** feedback — how many of the sentence's **key words** you covered (and
which you missed), plus your **pace** (words/minute) and **filler** count:

```bash
uv run speakloop shadow                                     # pick a question interactively
uv run speakloop shadow --question activity-rotation-callbacks
uv run speakloop shadow --slow --limit 5                    # slower first read; first 5 sentences
```

It provisions the speech + speech-recognition models (no feedback model, no pronunciation scorer),
and — like the other trainers — is **offline after the one-time download**, **English-only**, and
leaves **no recording on disk** and **no report**. (Future: pronunciation scoring of arbitrary
sentences; a cross-session tally of the sentences you keep mangling.)

## What you get: an example report

Every session writes a Markdown file with a YAML frontmatter block. Here is a
**generic, hand-authored** example (not a real recording) so you know what to expect
before you run anything. A real session adds sections as they apply — **Warm-up drill**,
**Content coverage** (per-round key-point hits), **Content errors**, **Pronunciation
flags**, **Follow-ups**, and a **STAR-structure** (behavioral) or **conditional-form**
(hypothetical) check — all additive, so the `schema_version` stays `1`. See
[`tests/fixtures/reports/sample-full-loop.md`](tests/fixtures/reports/sample-full-loop.md)
for a rendered example with every section:

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

- **Reports** Reports are saved under data/sessions/ as YYYY-MM-DD-<question-id>.md. Open that folder
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

You don't have to guess the format. The `questions` commands help you author and check a set:

```bash
uv run speakloop questions template > ~/.speakloop/qa.yaml   # start from a commented, valid template
uv run speakloop questions validate ~/.speakloop/qa.yaml     # check it — precise per-entry errors
uv run speakloop questions where                             # show the precedence + which file is active
```

`questions template` prints to your terminal (redirect it to save — it never writes a file
for you), and `questions validate` tells you exactly which entry and field is wrong, so you
catch mistakes before a session instead of mid-practice. With no path, `questions validate`
checks whichever file is currently active by the precedence above.

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

**Fix:** confirm your active engine and its readiness with `uv run speakloop doctor`. If the
local model is missing, run `uv run speakloop setup --engine local` (or start a session and
accept the download when prompted). Prefer not to download it? Switch to a cloud engine with
`uv run speakloop setup --engine openrouter` (or `--engine claude`). If `phase_c_error` shows
a runtime message, that session fell back on purpose so the failure is diagnosable from the
saved file — re-running usually succeeds.

### A technical term came out wrong in the transcript

**Cause:** speech recognition mis-transcribed accented domain vocabulary. speakloop
biases each session toward the question's terms (the `initial_prompt` shown in the
report's `asr:` block), but biasing is not perfect.

**Fix:** add the terms you use to the relevant question's `tags`/answer wording in your
question file so they feed the per-session biasing prompt. Improving raw accuracy beyond
this is a **known v1 limitation** — see [Known limitations](#known-limitations).

### Voice activity detection errors after upgrading dependencies

**Cause:** a newer, incompatible `silero-vad` (or `torchaudio`) version got installed
and changed the VAD API. `pyproject.toml` sets lower bounds (and caps `torchaudio<2.9`);
the exact working versions live in the committed `uv.lock`.

**Fix:** restore the locked versions with `uv sync` (it resolves from the committed
`uv.lock`). VAD/Whisper APIs have drifted between releases; only bump them on a
scheduled update window and re-run `uv run pytest -m live_asr`.

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

MIT. See [LICENSE](LICENSE).

## Found this useful?

If speakloop helps your interview prep, a star on GitHub is appreciated. If you have
ideas, bugs, or better prompts for the free-form grammar feedback, issues and PRs are
welcome.
