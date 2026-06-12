# Contract: `speakloop pronounce` (standalone trainer command)

A new thin command — `cli/pronounce.py` + `@app.command("pronounce")` in `cli/main.py`. Mirrors the
`practice`/`setup` wiring (engine-import deferral, consent flow, injected fakes for tests).

## CLI surface

```
speakloop pronounce [--limit N]
```

- `--limit N` (int, optional): cap the number of base drills this run (default: a small bundled
  default, e.g. 6). The loop is otherwise user-paced (`q` to quit at any hear-first/retry prompt; press
  on after each item, until the bank is exhausted or the limit is reached, then a closing summary).
- No `--engine`/`--cloud`: there is no feedback engine in standalone mode.
- All output English. `speakloop --help` MUST NOT import `cli/pronounce.py` or any engine package
  (the command body defers every heavy import, like `practice_cmd`).

## `pronounce.run(...)` (the testable entry point)

```python
def run(
    *,
    limit: int | None = None,
    tts_engine=None,            # injected fake in tests; else KokoroEngine (function-local build)
    play_fn=None,               # injected fake in tests; else audio.playback.play
    record_fn=None,             # injected fake in tests; else audio.recorder.record
    scorer=None,                # injected fake in tests; else pronunciation.build_scorer()
    bank=None,                  # injected in tests; else pronunciation.load_drill_bank()
    key_reader=None,            # injected FakeKeyReader in tests; else sessions.keyboard.make_key_reader()
    store_path=None,            # injected tmp in tests; else config.paths.store_path()
    input_fn=input,             # for the freeze-warned override + provisioning consent
    console=None,
) -> None: ...
```

## Flow (FR-010..FR-014)

1. **Config**: `loop_config.load()` → `pronunciation_min_free_mb`, `pronunciation_retries`,
   `pronunciation_tts_playback`.
2. **Gate (RAM-only)**: `assess_standalone_safety(min_free_mb=…)`. UNSAFE → print the reason; offer the
   freeze-warned `[y/N]` override only when interactive; declined/non-interactive → exit cleanly (no
   model load — SC-009).
3. **Provision** (only when proceeding): `installer.ensure_models("A")` (Kokoro TTS) +
   `installer.ensure_pronunciation_model(...)`. `InstallDeclinedError` → one-line hint + clean exit;
   `InstallFailedError` → one-line message + clean exit. **No ASR models** are provisioned.
4. **Build**: scorer (`build_scorer`), bank (`load_drill_bank`), tts (`KokoroEngine`), play
   (`playback.play`), record (`recorder.record` wrapped in the shared recording UI), key_reader; load
   the store + derive `weak_contrasts` from `pronunciation_contrasts`.
5. **Loop**: `select_drills(bank, weak_contrasts=…, max_base=limit or DEFAULT)` → for each, call
   `pronunciation.run_drill_item(...)` (hear → say → see → retry). Track flagged contrasts. `q` (→
   `DrillQuit`) ends the loop early.
6. **Close**: print a short, encouraging summary (drills done, tricky sounds); update + save the store
   `pronunciation_contrasts` tally. **No markdown report is written** (FR-014).

## Provisioning model set (verify against the repo)

- Kokoro TTS = `manifest.KOKORO_82M`, fetched by `ensure_models("A")` (Phase A = TTS).
- Pronunciation model = `manifest.WAV2VEC2_PRONUNCIATION`, fetched by `ensure_pronunciation_model`
  (opt-in, not in any phase). Both reuse the aria2 consent/download path (FR-013).

## doctor

`doctor._pronunciation()` gains a line noting standalone availability (RAM-only) and the new config
keys; it still never FAILs the exit code (opt-in).

## Tests (default suite — no model/mic/tty/network)

- standalone loop runs the hear→say→see→retry sequence over a faked bank (assert TTS spoken before
  record; bounded retry; `q` quits; closing summary printed; store tally updated; **no** report file).
- the RAM-only gate: a `local`-engine `loop.yaml` does **not** block standalone (only RAM does); low
  RAM → skip unless interactive override; the model build is never invoked when skipped.
- declining provisioning exits cleanly with no build.
