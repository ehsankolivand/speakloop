# audio

## Purpose

Local audio I/O — microphone recording, interruptible clip playback, and device probing
via `sounddevice` + `soundfile`. No model packages here.

## Public interface

- `playback.play(wav_path)` — synchronous blocking playback.
- `playback.play_interruptible(wav_path, *, should_stop, on_first_frame=None,
  poll_interval=0.03) -> bool` — non-blocking `sd.play` + 30 ms poll + `sd.stop()`
  (≈110 ms); returns `True` if interrupted. Optional `on_first_frame` callback fires after
  the stream starts. Used by the listen loop to skip a clip within ~110 ms (SC-004).
- `playback.warm_output_device()` — plays ~50 ms silence to pay the one-time CoreAudio
  open latency up front; best-effort, any failure is swallowed (`playback.py:122-132`).
- `playback.PlaybackError` — raised when no output device is available or WAV is unreadable.
- `recorder.record(out_path, time_budget_seconds, early_exit_event=None, *, sample_rate,
  channels) -> float` — records to WAV; returns actual wall-clock duration; stops early
  when `early_exit_event` is set or `abort.abort_event` is set.
- `recorder.RecorderError` — raised on `sd.PortAudioError`.
- `devices.default_input()`, `devices.default_output()`, `devices.list_devices()` —
  enumeration for `doctor` and the FR-009 pre-check.

## Dependencies

- Third-party: `sounddevice`, `soundfile` (not engine packages — safe to import at module
  level).
- Internal: `recorder.py` lazy-imports `speakloop.sessions.abort` at call time (`recorder.py:44`)
  to avoid a circular import (`audio → sessions → audio`). No other internal imports.

## Consumers

`cli`, `sessions`.

## File map

- `playback.py` — `play`, `play_interruptible`, `warm_output_device`, `_start_nonblocking`.
  Device-loss/resample recovery shared across all play paths: `_OPEN_RETRIES = 3`,
  backoff `0.25 s` (`playback.py:35-36`). Resample fallback imports `scipy.signal.resample_poly`
  (`playback.py:66`) — see Traps.
- `recorder.py` — `record()` via `sd.InputStream`; lazy `abort` import at `:44`.
- `devices.py` — device enumeration.

## Invariants & traps

- The resample fallback imports `scipy.signal.resample_poly` function-local at
  `playback.py:66`; `scipy` is declared in `pyproject.toml`. A SciPy import failure is
  caught with the PortAudio handler (`playback.py:113`/`:156`) and surfaces as
  `PlaybackError`, so playback degrades with one English error rather than a traceback.
- `warm_output_device` is only called from `cli/practice.py` when `key_reader.raw_capable`
  is True (`practice.py:376-377`) — not unconditionally.
- `recorder.py` lazy-imports `speakloop.sessions.abort` (not at module top) to avoid the
  `audio → sessions → audio` circular import.

## Common modification patterns

- **Change capture format/sample rate**: edit `recorder.py`.
- **Add a device diagnostic**: extend `devices.py`; surface in `cli/doctor.py`.
- **Tune skip latency**: adjust `_POLL_INTERVAL_SECONDS` in `playback.py` (default 0.03 s).

## Pointers

- Root map: `../../../CLAUDE.md`.
- Engine-import rules (O1) and torchaudio cap (O2): root CLAUDE.md Traps.
