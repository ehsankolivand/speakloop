# Phase 0 Research: Resilient Model Downloads

**Feature**: 007-robust-model-download
**Plan**: [plan.md](plan.md)
**Spec**: [spec.md](spec.md)

This document records the decisions that resolve the Technical Context's
open questions and the user's planning brief. Each entry is in
`Decision / Rationale / Alternatives` form. The `[NEEDS CLARIFICATION]` set
on the spec is empty post-`/speckit-clarify`; this research phase confirms
that no new unknowns surface during design.

---

## Decision 1 — Use `aria2c` as the parallel downloader (port `download_aria.sh`)

**Decision**: Port the in-repo `download_aria.sh` to Python and call `aria2c`
as a subprocess for each shard, with the same flag set the script uses:
`--max-connection-per-server=16 --split=16 --min-split-size=1M
--continue=true --max-tries=0 --retry-wait=5 --connect-timeout=30`. Wrap the
invocation in a Python `until-success` retry loop so even a hard aria2 exit
restarts it indefinitely until the file completes.

**Rationale**:
- This is the user's already-validated configuration. The script header
  documents 5–10× wall-clock speedup on the Qwen3-14B-4bit checkpoint over
  a constrained link, indefinite resume across drops, and correct shard
  selection — i.e., it has been measured against the actual target user
  environment.
- aria2's `--continue=true` does true byte-range resume of in-flight files,
  satisfying FR-002 strictly (no file is re-downloaded from zero).
- `--max-tries=0` (zero = unlimited) + the outer Python `until` loop
  satisfies FR-003 (indefinite hands-free retry) — strictly stronger than
  `huggingface_hub.snapshot_download`'s bounded internal retry.
- Boring, ubiquitous tool: `aria2c` is in Homebrew, the Debian / Ubuntu /
  Arch / Alpine package repositories, and most other Unix package
  managers; pretty much every macOS power user can install it with one
  command.

**Alternatives considered**:
1. **`hf-transfer` (Rust parallel downloader via `HF_HUB_ENABLE_HF_TRANSFER=1`)**
   — already declared in `pyproject.toml` (currently inactive). Pro: pure
   Python install, no external prereq. Con: does not implement indefinite
   outer-loop retry (FR-003); does not address sleep prevention (FR-004); a
   hard failure still exits and forces a re-run; less observability hooks
   for the Rich-progress bridge. Adopting it would only partially close
   the spec, and we would then add caffeinate + outer retry on top — at
   which point the mechanism is no simpler than the aria2 path while
   inheriting a less-validated configuration.
2. **`aiohttp` + custom range-request scheduler**. Pro: pure Python, full
   control. Con: significant new code, no field validation, violates the
   "boring over novel" dev guideline, more failure modes to test.
3. **Stay on `snapshot_download` only**. Pro: zero new prereqs. Con: this is
   the status quo the spec exists to replace; rejected on its face.
4. **Vendor a static `aria2c` binary in the repo**. Pro: no `brew install`.
   Con: license tracking, code signing, macOS notarization for distribution
   — a much larger surface than asking for one `brew install`.

→ aria2 chosen.

---

## Decision 2 — `curl` for metadata, `aria2c` for shards (two tools, by file class)

**Decision**: Download the small JSON / text metadata files (`config.json`,
`tokenizer*.json`, `chat_template.jinja`, `model.safetensors.index.json`,
`README.md`, generation/special-tokens config, vocab/merges if present) with
`curl -L -f --retry 5 --retry-delay 3`. Reserve `aria2c` for the
multi-GB shards listed in `model.safetensors.index.json` (or the single
`model.safetensors` when no index file exists).

**Rationale**:
- aria2's 16-connection split on a 10 KB JSON is wasted setup overhead.
  curl is faster and simpler for the small files.
- Mirrors the original `download_aria.sh` separation — keeping the two-tool
  split makes the port a literal translation, easier to review.
- Metadata files are also needed *before* shard discovery (to parse
  `model.safetensors.index.json`), so they get their own pass anyway.

**Alternatives considered**:
- Use `aria2c` for everything. Rejected: 16-stream split on tiny files is
  measurably slower than a single `curl`, and adds aria2 noise to the Rich
  progress display for files that finish in milliseconds.

---

## Decision 3 — Use Python `subprocess` (not aria2's RPC mode) and parse progress from stdout

**Decision**: Spawn `aria2c` with the human-readable progress on by default
(no `--quiet`), redirecting both stdout and stderr to a pipe via
`subprocess.Popen(..., stdout=PIPE, stderr=STDOUT, text=True,
bufsize=1)`. Read line-by-line from the parent Python; parse each `(...) [#... ... B/s ETA: ...]`
status line into a `(bytes_received, bytes_total, eta_seconds)` triple; push
each update into a `rich.progress.Progress` task bound to the model name.
On a line that matches an error pattern (e.g. `errorCode=...`), classify it
and either let the outer Python retry loop respawn aria2 (transient) or
raise (hard error: 401, 403, 404).

**Rationale**:
- `subprocess` is stdlib; no new dep; matches "boring over novel."
- aria2's stdout format is stable and documented. Field experience: the
  `[#NN size/totalSize(percent%) CN:n SD:n DL:rate ETA:x]` line is the
  canonical place to read progress for a single download.
- Bridging through a Python `Popen` lets us:
  - Wrap each shard in a Python `while not success:` loop for FR-003.
  - Map aria2's per-shard status into a per-model `rich.progress` task
    that already matches the existing Rich console style.
  - Suppress aria2's TTY animations by piping (aria2 auto-falls back to
    plain progress lines when stdout is not a TTY), so the Rich display
    is not corrupted by ANSI escapes from the child.

**Alternatives considered**:
1. **aria2's `--enable-rpc` JSON-RPC mode** — start aria2 as a server, talk
   to it over HTTP/JSON. Pro: structured progress data (no parsing). Con:
   extra moving parts, port management, less common in field reports, and
   the user's reference script uses plain CLI mode. The stdout parser is
   ~20 lines; not worth the architectural cost.
2. **aria2 `--log=- --log-level=info`** — structured log lines. Pro: more
   machine-readable. Con: noisier and the progress line itself is not in
   the log stream by default. Stdout is simpler.

See [`contracts/progress-bridge-contract.md`](contracts/progress-bridge-contract.md)
for the exact parser shape.

---

## Decision 4 — Spawn `caffeinate -dimsu -w <parent-pid>` at the top of `ensure_models(...)`

**Decision**: At the entry of `installer.ensure_models(...)`, immediately
spawn `caffeinate -dimsu -w <os.getpid()>` as a detached child via
`subprocess.Popen`. Register an `atexit` / `try/finally` handler that kills
the caffeinate process on any exit path (success, `InstallDeclinedError`,
`InstallFailedError`, `KeyboardInterrupt`, unhandled exception). The `-w`
flag means caffeinate self-terminates if the parent dies for any reason —
defense in depth against a stranded wakelock.

**Rationale**:
- `caffeinate -dimsu` prevents display sleep (`-d`), idle sleep (`-i`),
  disk sleep (`-m`), system sleep (`-s`), and assertion-based sleep (`-u`).
  This is the exact set used by the user's validated script.
- The `-w <pid>` flag ties caffeinate's lifetime to the speakloop install
  process — so if the user `kill -9`'s speakloop, caffeinate also exits
  and we do not strand power-management overrides.
- Spawning at `ensure_models(...)` entry (not inside the per-shard loop)
  scopes the wakelock to the whole install, including the consent prompt
  and the metadata pass — matches FR-004 ("for the duration of a single
  model-download run").
- If `caffeinate` is missing (it ships with macOS, so this is unlikely
  but possible in sandboxes / CI), the spawn fails silently and we log
  one warning line that sleep prevention is unavailable; the install
  still proceeds (matches the spec edge case "sleep prevention is
  unavailable").

**Alternatives considered**:
- **`pmset noidle` background process** — more invasive (changes global power
  state); caffeinate is the standard.
- **IOKit `IOPMAssertionCreateWithName` via `objc`/`PyObjC`** — adds a heavy
  Python dep for a one-line shell-out replacement. Rejected.

---

## Decision 5 — Token resolution order: `$HF_TOKEN` → `~/.cache/huggingface/token` → anonymous

**Decision**: Read the optional HuggingFace token in this strict order, using
the first non-empty value found:
1. `os.environ["HF_TOKEN"]` (matches the variable name documented by HF and
   used by the user's `download_aria.sh`).
2. The contents of `~/.cache/huggingface/token` (the file produced by
   `huggingface-cli login`), trimmed.
3. Otherwise: no token (anonymous).

When a token is present, both `curl` and `aria2c` receive an
`Authorization: Bearer <token>` header. When no token is present, both
calls run anonymous — public repos download successfully without any
header (the original script's `TOKEN:?...` hard-requirement is dropped
during the port; this is a deliberate change from the shell script to
align with FR-010).

**Rationale**:
- Matches the spec clarification (Q2 → Option A): no new speakloop-owned
  credential file; the HF CLI's standard location is the lone "local user
  configuration" path.
- `HF_TOKEN` is the variable name the HF docs canonically use; lower-case
  variants and `HUGGINGFACE_HUB_TOKEN` exist historically but are not part
  of this feature's surface.
- Anonymous-by-default satisfies FR-010 and SC-003.

**Alternatives considered**:
- `HUGGINGFACE_HUB_TOKEN` as primary — older form, less widely used in
  current HF docs; reject as primary, do not even support as alias to keep
  the documented surface minimal.
- Read both env vars and prefer the longer one — gimmicky, no benefit.

See [`contracts/token-resolution-contract.md`](contracts/token-resolution-contract.md)
for the exact resolution rules and the no-leak invariants.

---

## Decision 6 — Shard discovery: parse `model.safetensors.index.json`

**Decision**: After the metadata pass (Decision 2), if
`model.safetensors.index.json` exists in the destination directory, parse
it as JSON and read the `weight_map` field; the unique sorted values of
`weight_map` are the shard filenames to feed to aria2. If the index file
does NOT exist (i.e., the repo ships a single `model.safetensors`), fall
back to the single filename `model.safetensors`.

**Rationale**:
- This is exactly what the source script does, and is the standard layout
  for MLX / safetensors repos on HF.
- Parsing the index instead of globbing the HF tree means we fetch ONLY the
  files for the selected quantisation; alternate weight formats in the
  same repo (`.gguf`, `.bin`, `fp16/` siblings) are ignored — satisfying
  FR-006.

**Alternatives considered**:
- Hit the HF tree API and download every file in the repo. Rejected: pulls
  alternate weight formats by accident, violates FR-006.
- Hardcode the shard list per model in `manifest.py`. Rejected: brittle,
  invalidated by upstream re-shardings, more code for no benefit.

See [`contracts/downloader-cli-contract.md`](contracts/downloader-cli-contract.md)
for the exact JSON shape this parser assumes.

---

## Decision 7 — Missing-`aria2c` fallback path

**Decision**: At download start, `shutil.which("aria2c")` decides the path:
- If aria2 is on `PATH`: proceed with the aria2 mechanism (parallel,
  resumable, indefinite-retry).
- If aria2 is NOT on `PATH`: log one Rich-styled warning that names the
  missing tool and the install command (`brew install aria2`), then call
  the pre-existing `huggingface_hub.snapshot_download(..., resume_download=
  True)` path. The metadata + shard split is irrelevant in this branch —
  snapshot_download fetches the repo whole. Validation (FR-007) still
  gates readiness in both branches.

**Rationale**:
- Matches the spec clarification (Q1 → Option B). Keeps "stranger can
  clone and run" working at parity with today even without aria2.
- `shutil.which(...)` is stdlib; no extra dep.

**Alternatives considered**:
- Treat aria2 as a hard prerequisite checked at `doctor`. Rejected during
  clarification (Q1 option C) — too brittle for the "first run on a fresh
  machine" case.

---

## Decision 8 — Define and measure the SC-001 speedup target

**Decision**: For the post-implementation acceptance test, fix the SC-001
target at **≥ 2× wall-clock speedup** for a representative multi-gigabyte
model (Qwen3-14B-4bit, ~8 GB) on a single A/B comparison over a
representative shaped link (≥ 25 Mbit/s × ~150 ms RTT). The reference
field result on the user's link is 5–10× per the source script's header,
so the 2× target is conservative and reliably clears even on links where
the per-stream BDP penalty is smaller.

**Rationale**:
- The Q4 clarification (Q4 of session 2026-05-31) was deferred to planning
  when the user moved straight to `/speckit-plan`. The recommended option
  at that point was 2× speedup, which this research now adopts as the
  measurable acceptance threshold.
- Falsifiable: two timed runs of the same model, same shaped link, with
  and without aria2 → compute the ratio. Pass / fail is unambiguous.

**Alternatives considered**: 3× speedup (more aspirational; risk of
flaking on lossy links), throughput-vs-link-capacity ratio (harder to
measure cleanly because link capacity must be calibrated). Recorded in
the deferred-clarification note in `checklists/requirements.md`.

---

## Decision 9 — Drop the inactive `hf-transfer` dep from `pyproject.toml`

**Decision**: Remove `"hf-transfer>=0.1.9"` from `pyproject.toml`'s
`dependencies` list as part of this feature. It is declared but never
activated (`HF_HUB_ENABLE_HF_TRANSFER` is not set anywhere in the source),
and the chosen mechanism is aria2; carrying a second parallel-download
backend would violate the "minimal-deps" intent.

**Rationale**:
- Dev guideline: "standard library over dependencies." Dead deps invite
  future confusion ("which backend is actually pulling these bytes?").
- Net dep count after this feature: −1 Python dep, +1 system binary
  (aria2). The Python install size goes down.

**Alternatives considered**:
- Keep `hf-transfer` as a secondary fallback before snapshot_download.
  Rejected: three-tier fallback (aria2 → hf_transfer → snapshot_download)
  is over-engineering for "missing aria2 on a Mac"; the snapshot_download
  fallback is sufficient.

---

## Open questions after research

None. All NEEDS CLARIFICATION markers from the spec are resolved; no new
unknowns surfaced during the research above. Ready for Phase 1 design.
