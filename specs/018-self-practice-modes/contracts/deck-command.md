# Contract — `speakloop deck` (Mode A, US1)

## CLI surface (`cli/main.py`)

```
speakloop deck [--limit N] [--export PATH] [--ahead]
```

- `--limit N` — max cards this run (default `deck_daily_capacity`, itself default 20). Bounds due-card selection.
- `--export PATH` — write the **whole deck** as an Anki cloze-import file to `PATH`, then exit. No drilling, no models, no network.
- `--ahead` — when nothing is due, drill the soonest-due cards anyway (also offered interactively). Optional convenience.
- `--help` — must work with **no models present** and load no engine (function-local imports only).

Registered as `@app.command("deck")` delegating to a function-local import of `cli.deck` → `deck.run(...)`.

## `cli/deck.py` entry point (injectable for tests)

```python
def run(
    *,
    limit: int | None = None,
    export_path: Path | None = None,
    ahead: bool = False,
    tts_engine=None,          # injected fake in tests; else KokoroEngine(speed=cfg.pronunciation_tts_speed)
    play_fn=None,             # injected; else audio.playback.play
    key_reader=None,          # injected FakeKeyReader/NullKeyReader; else sessions.keyboard.make_key_reader()
    reports_dir: Path | None = None,   # else config.paths.sessions_dir()
    store_path: Path | None = None,    # else config.paths.store_path()
    starter_cards=None,       # injected list[LineCard]; else linecards.load_starter_cards()
    today: date | None = None,         # injected for deterministic scheduling tests
    input_fn=input,
    console: Console | None = None,
) -> None: ...
```

Everything model/tty is injectable so tests use fakes (mirrors `cli/pronounce.py`). No microphone, no `record_fn`, no ASR.

## Behavior

1. **Export path**: if `export_path` set → derive all cards (reports + starter, deduped) → `linecards.to_anki(...)` → write file (atomic), print count, return. Works with no models and non-interactively. Unwritable path → clean error, exit non-zero (no traceback).
2. **Drill path**:
   - Load store; derive cards from `reports_dir`; merge derived content with stored `line_cards` SRS state (add new cards, keep existing history); fold in starter cards.
   - `select_due(cards, today=today, capacity=limit)`. If empty and not `--ahead`: print "caught up", offer practise-ahead (interactive); non-interactive → return.
   - Provision Phase A (TTS) via `installer.ensure_models("A")` only when building the real engine (skipped when `tts_engine` injected). Decline/fail → clean message, return.
   - For each due card: **hear** (TTS speaks `corrected`; `r` replays, `q` quits) → **say** (learner speaks aloud; no recording) → **see** (print "You said …" / "Better: …" / rule) → **self-mark** (`1/2/3/4` or `a/h/g/e`) → `advance_card(state, grade, today=today)` → update store.
   - Persist store (`store.io.save_atomic`) after the run (main thread).
   - Non-interactive (no TTY): skip the drilling loop with a notice (self-mark needs interaction); export still runs.
3. **No report** is ever written. **No** wav is recorded.

## Invariants asserted by tests

- Loop order per card is hear → see → self-mark (play before the target is revealed); `q` stops cleanly, persisting progress so far.
- A card marked `again` is due next run; two `easy` marks retire it to maintenance (assert via `today`-injected reschedule).
- `--export` writes a file with `{{c1::` on derived cards and one card per line; no models loaded; no `.md` report written anywhere.
- Non-interactive drill run records/plays nothing and writes no report.
- Deriving cards twice from the same reports yields identical `card_id`s (stable identity / dedup).
