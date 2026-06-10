# Contract: Keyboard Abstraction, Session States & Controls

## Canonical keys

The `KeyReader.poll()` returns one of these canonical names, or `None` (no key waiting):

| Canonical | Raw bytes accepted | Line-fallback words |
|-----------|--------------------|---------------------|
| `space` | `" "` (0x20) | `""` (blank line), `"space"` |
| `enter` | `\r`, `\n` | (Enter alone — alias of `space` per FR-009) |
| `r` | `r` | `r` |
| `s` | `s` | `s` |
| `q` | `q`, `\x03` (Ctrl-C maps to quit where quitting exists) | `q`, `quit` |

`enter` is treated as an alias of `space` by call sites (FR-009). Unknown bytes → ignored
(`poll()` returns `None` or a key the current state does not bind → no-op, FR-011).

## State → valid keys (the on-screen hint shows exactly these)

| State | Valid keys | Effect |
|-------|-----------|--------|
| `PLAYING` (question / ideal answer) | `space`/`enter` → skip; `r` → replay | FR-005/006 |
| `PLAYING` (follow-up prompt) | `space`/`enter` → skip-to-answer; `s` → skip whole follow-up; `r` → replay | FR-008 |
| `RECORDING` (attempt / warm-up / follow-up) | `space`/`enter` → stop early; (`s` on a follow-up recording → abandon follow-up) | FR-007/008 |
| `TRANSCRIBING` | (none) — keys ignored gracefully | FR-011 |
| `ANALYZING` | (none) — keys ignored gracefully | FR-011 |
| listen-loop idle (between clips) | `r` replay question · `R`/`r`-ideal · `space` next · `q` quit | preserves today's listen-loop commands (FR-009) |

> The listen-loop's existing `r`/`R`/`space`/`q` semantics are retained verbatim for the
> idle prompt; the new single-key controls govern the *during-playback* and *during-recording*
> windows that today have no controls.

## `KeyReader` protocol

```python
class KeyReader(Protocol):
    def __enter__(self) -> "KeyReader": ...   # enter raw/cbreak mode (no-op for Null/Fake)
    def __exit__(self, *exc) -> None: ...      # restore terminal
    def poll(self) -> str | None: ...          # non-blocking; canonical key or None
    @property
    def raw_capable(self) -> bool: ...         # False for NullKeyReader (fallback active)
```

- `RawKeyReader`: resolves a tty fd (stdin if `os.isatty`, else `os.open("/dev/tty")`); cbreak
  via termios/tty; `select.select([fd],[],[],timeout)` to poll without blocking. Restores the
  saved termios attrs on `__exit__`. Drains pending input on enter (mirrors today's
  `termios.tcflush`) so stray pre-stage keys don't trip a control at t=0.
- `NullKeyReader`: used when no tty is reachable (piped stdin, no controlling terminal — the
  measured non-interactive case). `poll()` always `None`; `raw_capable=False`. The session
  still completes on time budgets + the line-based path (FR-012).
- `FakeKeyReader`: test double. Constructed with a script like `[(0.2,"space"),(1.0,"r")]`
  (delay, key); `poll()` returns the next due key based on an injected clock. Never opens a fd.

## Interruptible playback contract

```python
def play_interruptible(wav_path, *, should_stop: Callable[[], bool],
                       on_first_frame: Callable[[], None] | None = None) -> bool
```

- Starts non-blocking `sd.play`; loops polling `should_stop()` (~30 ms) until the stream ends
  or `should_stop()` is true; on true → `sd.stop()` and returns `True` (interrupted), else
  `False`. Reuses the device-loss reload + resample fallback of `play()`.
- Guarantee: an interrupt takes effect ≤ 500 ms (measured `sd.stop()` ≈ 110 ms). SC-004.
- `warm_output_device()` is called once during model load to absorb the one-time CoreAudio
  device-open latency, so the first clip is not delayed.

## Behavioral guarantees (testable with fakes)

- B1 — Exactly one state is active at any time (FR-001); the displayed hint matches the active
  state's key map (FR-010).
- B2 — A `RECORDING` indicator is present for the full recording window (FR-003, SC-005).
- B3 — A countdown precedes every recording, attempts and follow-ups (FR-004).
- B4 — `space` during `PLAYING` stops playback within 500 ms (SC-004); `r` restarts it.
- B5 — `space`/`enter` during `RECORDING` ends it and transitions to `TRANSCRIBING` (FR-007).
- B6 — `s` during a follow-up's prompt or answer abandons that follow-up (no answer recorded),
  advancing the session (FR-008).
- B7 — A key with no binding in the current state is ignored; no crash, no state change (FR-011).
- B8 — With `NullKeyReader`, the session completes via the line/timeout path (FR-012).
