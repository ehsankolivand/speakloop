# Quickstart: Resilient Model Downloads

**Feature**: 007-robust-model-download
**Audience**: a maintainer or new contributor verifying this feature
**Time**: ~10 minutes to validate the happy path, ~30 minutes to exercise the
resilience and fallback cases.

## What changed for an end user

If the user already has `aria2` installed (`brew install aria2`), they get:
- Multi-stream downloads that are noticeably faster on slow links.
- Downloads that survive Wi-Fi drops, lid closures, and lock screens.
- The same consent prompt, the same on-disk layout, the same
  `~/.speakloop/models/...` paths.

If the user does NOT have `aria2`, they get a one-line warning at install
time and the install proceeds at today's single-connection speed. Nothing
breaks.

## One-time setup (target machine)

```bash
brew install aria2
```

This is the only new prerequisite. Optional:

```bash
huggingface-cli login   # only if hitting rate limits or fetching gated repos
# OR
export HF_TOKEN=hf_xxxxx
```

## Happy-path verification

From the repo root:

```bash
# 1. Ensure aria2 is on PATH
which aria2c

# 2. Fresh install (deletes existing models first if you want a true cold start;
#    skip if you want to verify the resume path instead)
rm -rf ~/.speakloop/models/mlx-community__Kokoro-82M-bf16

# 3. Run doctor — it should report aria2 as detected and healthy
uv run speakloop doctor

# 4. Trigger Phase A install via a one-off command
#    (uses the `--help`-loadable installer path; does NOT load any engines)
uv run python -c "from speakloop.installer import ensure_models; ensure_models('A')"
```

Expected console output (abbreviated):

```text
Phase A: 1 model(s) need to be downloaded.
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Model         HF repo                          Size     Target path ┃
┃ Kokoro-82M    mlx-community/Kokoro-82M-bf16    170.0 MB ~/.speakloop/…┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
Total disk footprint: 170.0 MB
All artifacts stay on your local machine. No telemetry.
Proceed with download? [y/N]: y

Downloading Kokoro-82M → ~/.speakloop/models/mlx-community__Kokoro-82M-bf16
  Kokoro-82M / config.json ... ok
  Kokoro-82M / tokenizer.json ... ok
  ...
==> Shards to download:
    model.safetensors
Kokoro-82M / model.safetensors  ████████████████████ 170.0/170.0 MB  6.4 MiB/s  0:00:00
```

When the run completes, `validator.validate(KOKORO_82M).ok == True`.

## Resilience verification

### Test 1 — Network drop mid-download

In one terminal, start the install for a larger model (e.g., Phase B
including Whisper at ~1.5 GB):

```bash
uv run python -c "from speakloop.installer import ensure_models; ensure_models('B')"
```

In a second terminal, drop and restore Wi-Fi several times during the
shard transfer:

```bash
networksetup -setairportpower en0 off
sleep 30
networksetup -setairportpower en0 on
```

Expected: the Rich progress bar pauses; the line
`Connection lost — retrying in 10s…` appears in yellow; once the network
returns, the progress bar resumes from the prior byte offset (NOT zero).
No exception is raised; you do NOT have to re-run the command.

### Test 2 — Lid-close survival

Start the install for Phase C (~10 GB total, several minutes even on a fast
link). Immediately close the laptop lid. Wait 60 s. Open the lid.

Expected: the install is still running, the progress bar reflects bytes
received while the lid was closed (caffeinate prevented system / display /
disk sleep). On the system event log:

```bash
log show --last 5m --predicate 'sender CONTAINS "caffeinate"' --info
```

You should see a `caffeinate` assertion held by the speakloop process.

### Test 3 — Missing-aria2 fallback

Temporarily make aria2 unavailable:

```bash
mv "$(which aria2c)" "$(which aria2c).bak"
```

Run a fresh install (after deleting one model directory). Expected:

```text
aria2 not found — using single-connection fallback. Install with: brew install aria2
Downloading Kokoro-82M → ~/.speakloop/models/...
  (huggingface_hub.snapshot_download progress)
```

Install completes; validation passes. Restore aria2:

```bash
mv "$(which aria2c).bak" "$(which aria2c)"
```

### Test 4 — Anonymous works for public models

```bash
unset HF_TOKEN
mv ~/.cache/huggingface/token ~/.cache/huggingface/token.bak 2>/dev/null || true
rm -rf ~/.speakloop/models/mlx-community__Kokoro-82M-bf16
uv run python -c "from speakloop.installer import ensure_models; ensure_models('A')"
```

Expected: no `Using HuggingFace token from ...` diagnostic line, install
completes, validation passes.

Restore:

```bash
mv ~/.cache/huggingface/token.bak ~/.cache/huggingface/token 2>/dev/null || true
```

## Automated tests

```bash
# Default suite (no network, no live model calls): MUST pass
uv run pytest

# Live downloader smoke test (opt-in, network required):
uv run pytest -m live_download

# Existing live ASR / LLM smoke tests are unaffected:
uv run pytest -m live_asr
uv run pytest -m live_llm
```

`uv run pytest` MUST stay green after this feature lands. The
`live_download` marker is excluded from the default suite by design — it
hits the network on purpose for end-to-end validation.

## Throughput A/B (SC-001 evidence)

To produce the SC-001 ≥ 2× wall-clock speedup evidence:

1. Throttle the link with the macOS Network Link Conditioner (Settings →
   Developer → Network Link Conditioner) using a profile such as "DSL"
   (1.5 Mbps down, 384 Kbps up, 70 ms RTT) or define a custom shaped link.
2. Download Qwen3-14B-4bit ONCE via `snapshot_download` (toggle the
   missing-aria2 fallback by temporarily renaming `aria2c`); record the
   elapsed wall-clock time.
3. Delete the downloaded model directory.
4. Download Qwen3-14B-4bit ONCE via the new aria2 path; record the
   elapsed wall-clock time.
5. Compute the ratio. Acceptance: aria2 time ≤ 0.5 × snapshot_download
   time on the same shaped profile.

Record the numbers in the PR description so future regressions are
catchable against a known baseline.

## Rollback

If the new mechanism causes a regression in production:

1. The fastest revert is to remove `aria2c` from PATH — the fallback path
   then handles all downloads at status-quo behavior.
2. The full code revert touches only
   `src/speakloop/installer/{downloader,aria,tokens,shards}.py` and the
   matching tests. The public `ensure_models(...)` signature has not
   changed, so callers are unaffected.
