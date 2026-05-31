# Research: Install / Model-Download Mechanism

**Status**: live (feature 007-robust-model-download landed 2026-05-31)
**Spec / plan**: [specs/007-robust-model-download/](../specs/007-robust-model-download/)
**Constitution principle this satisfies**: X (research is part of the repo).

## Decision (one line)

Use `aria2c` (system binary, `brew install aria2`) for the multi-GB safetensors
shards, `curl` for the small metadata files, with auto-fallback to
`huggingface_hub.snapshot_download(resume_download=True)` when `aria2c` is not
on `PATH`. Anonymous by default; optional `$HF_TOKEN` → `~/.cache/huggingface/token`
credential read at runtime, never committed.

## Why aria2 (the 9 in-feature decisions, 1-line form)

The full decision records live in
[`specs/007-robust-model-download/research.md`](../specs/007-robust-model-download/research.md).
Summary:

1. **aria2c is the mechanism.** Port `download_aria.sh` to Python, keep the
   same flag set (`--max-connection-per-server=16 --split=16
   --min-split-size=1M --continue=true --max-tries=0 --retry-wait=5
   --connect-timeout=30`) plus an outer Python `until-success` retry loop.
2. **Split metadata vs shards.** `curl -L -f --retry 5 --retry-delay 3` for
   small JSON / text files; aria2c for the multi-GB shards.
3. **`subprocess.Popen`, not aria2's RPC mode.** Parse the human-readable
   progress lines and bridge them into the existing Rich console.
4. **Sleep prevention via caffeinate.** Spawn `caffeinate -dimsu -w <pid>` at
   the entry of `ensure_models(...)`; `terminate()` in `finally`. The `-w`
   flag means caffeinate self-exits if the parent dies.
5. **Token order: `$HF_TOKEN` → `~/.cache/huggingface/token` → anonymous.**
   No new speakloop-owned credential file. Anonymous works for public repos.
6. **Shard discovery via `model.safetensors.index.json`.** Parse the
   `weight_map`, return `sorted(set(values))`. No index file ⇒
   `["model.safetensors"]`. This guarantees FR-006 (only the selected
   quantisation, no sibling weight formats).
7. **Missing-`aria2c` fallback.** `shutil.which("aria2c") is None` ⇒
   one-line yellow warning + `huggingface_hub.snapshot_download(...)`.
   Validation still gates readiness.
8. **SC-001 ≥ 2× wall-clock speedup** is the measurable acceptance target
   on a representative shaped link (Qwen3-14B-4bit, ≥ 25 Mbit/s × ~150 ms
   RTT). The user's field result on the source script header cites 5–10×.
9. **Drop `hf-transfer` from `pyproject.toml`.** The dep was declared but
   never activated; the chosen mechanism is aria2; two parallel-download
   backends would re-fragment the path.

## Source of the validated configuration

The flag values and the metadata-vs-shards split come from `download_aria.sh`,
the user's pre-validated shell script (removed from the repo root once its
logic was ported in full — see git history for the original). The Python
port lives in `src/speakloop/installer/` (`downloader.py` orchestrator +
`aria.py` subprocess bridge + `shards.py` index parser + `tokens.py` resolver).

## Alternatives rejected (with one-line reasons)

- **`hf-transfer` (Rust parallel downloader, already a transitive dep)** —
  no indefinite outer-loop retry, no caffeinate, less observability for the
  Rich progress bridge; would still need a wrapper to close the spec.
- **`aiohttp` + custom range-request scheduler** — significant new code,
  no field validation; violates the "boring over novel" dev guideline.
- **Stay on `snapshot_download` only** — the status quo this feature
  exists to replace.
- **Vendor a static `aria2c` binary** — license tracking, code signing,
  macOS notarization — a much larger surface than asking for one
  `brew install aria2`.

## Constitution principle VIII friction (justified)

Adding `brew install aria2` as a prerequisite is friction Principle VIII
explicitly minimises. Mitigations that keep the spirit intact:

- FR-019 auto-fallback to `snapshot_download` keeps "clone + run" working
  at parity with today even without aria2.
- `speakloop doctor` reports the missing tool with the exact
  `brew install aria2` command (Principle VIII's "guide the user" intent).
- README's install steps list `brew install aria2` immediately after `uv`.

See [`specs/007-robust-model-download/plan.md` § Complexity Tracking](../specs/007-robust-model-download/plan.md)
for the full alternatives-considered table.
