# Quickstart: OpenRouter Cloud Mode

For users whose Mac cannot fit the local Qwen3-14B model in RAM. Cloud mode runs
the **feedback** step against an OpenRouter-hosted model; speech and transcription
stay local. The default offline experience is unchanged if you skip `--cloud`.

> Privacy note: cloud mode sends your **attempt transcript text** to OpenRouter for
> analysis. Your audio recordings and session reports never leave your machine.
> The default (local) mode sends nothing anywhere.

## 1. Get an OpenRouter token

Create one at <https://openrouter.ai/keys>. It looks like `sk-or-v1-...`.

## 2. Run a cloud-mode practice session

```bash
uv run speakloop practice --cloud
```

The first time, you'll be prompted once for your token (with the privacy
disclosure). It's saved to `~/.speakloop/openrouter_token` (mode 0600) and reused
silently afterwards. Every later `--cloud` run skips the prompt.

Prefer an env var (e.g. in CI or a shell profile)? Set it instead — it takes
precedence over the stored file and skips the prompt entirely:

```bash
export OPENROUTER_API_KEY="sk-or-v1-..."
uv run speakloop practice --cloud
```

## 3. Change the cloud model (one setting, no code change)

Default is `qwen/qwen3.7-max`. Edit one line in `~/.speakloop/openrouter.yaml`:

```yaml
# ~/.speakloop/openrouter.yaml
model: anthropic/claude-3.5-sonnet
```

Then re-run `uv run speakloop practice --cloud`. If the file (or the `model:` key)
is absent, the default `qwen/qwen3.7-max` is used.

## 4. Tune the cloud feedback prompt (one file, no code change)

The cloud system prompt lives in its own file, separate from the local model's
prompt:

```bash
$EDITOR ~/.speakloop/openrouter_prompt.txt
```

It's seeded with a working default on your first cloud run (the path is printed).
Edit it and re-run `--cloud`; the next session uses your edits. Local mode is
never affected by this file.

## 5. Stay local (default — fully offline)

```bash
uv run speakloop practice          # local Qwen, no network, no token prompt
```

## Troubleshooting

| Symptom | Fix |
|---|---|
| "Invalid OpenRouter token" | Re-enter when re-prompted, or replace `~/.speakloop/openrouter_token` / set `OPENROUTER_API_KEY`. Or drop `--cloud` to use local mode. |
| "Could not reach OpenRouter" at startup | Check connectivity; cloud mode needs network. Or run without `--cloud`. |
| Feedback failed mid-session | The report is still written with a `phase_c_error` note (same as a local feedback failure); re-run to retry. |
| Want to see cloud config status | `uv run speakloop doctor` shows the model id, whether a token is present, and the prompt-file path. |

## What changed vs. local mode

| | Local (default) | Cloud (`--cloud`) |
|---|---|---|
| Feedback model | Qwen3-14B (local, ~10 GB RAM) | OpenRouter model (no local LLM load) |
| Network | none after model download | feedback request to OpenRouter |
| Speech / transcription | local (unchanged) | local (unchanged) |
| Token needed | no | yes (prompted once, stored) |
| Report format / `schema_version` | 1 | 1 (identical) |
