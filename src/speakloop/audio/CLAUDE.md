# audio

## Purpose

Local audio I/O — microphone recording, clip playback, and device probing via `sounddevice` +
`soundfile`. No model packages here.

## Public interface

- `playback.play(wav_path)` — blocking playback [Phase A].
- `playback.play_interruptible(wav_path, *, should_stop, ...)` (012) — non-blocking play +
  ~30 ms poll + `sd.stop()` (≈110 ms) so a single keypress skips a clip within 500 ms (SC-004);
  returns whether it was interrupted. `warm_output_device()` pays the one-time CoreAudio open up
  front. Both reuse `play()`'s device-loss/resample recovery.
- `recorder.record(out_path, time_budget_seconds, early_exit_event)` — records to WAV; the
  event lets the coordinator stop before the budget ends [Phase B].
- `devices.default_input()`, `devices.default_output()`, `devices.list_devices()` — enumeration
  (used by `doctor` and the FR-009 pre-check).

## Dependencies

- Third-party: `sounddevice`, `soundfile` (not engine packages — always safe to import).
- Internal: `speakloop.sessions` (the shared `abort` early-exit event).

## Consumers

`cli`, `sessions`.

## File map

- `playback.py` — `play()` via sounddevice + soundfile.
- `recorder.py` — `record()` using `sounddevice.InputStream` + soundfile; honours `early_exit_event`.
- `devices.py` — device enumeration for doctor + pre-check.

## Common modification patterns

- **Change capture format/sample rate**: edit `recorder.py`.
- **Add a device diagnostic**: extend `devices.py` and surface it in `cli/doctor.py`.

## Pointers

- Root map: [`../../../CLAUDE.md`](../../../CLAUDE.md).
