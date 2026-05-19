# audio

Local audio I/O — recording and playback via `sounddevice` + `soundfile`.

**Public surface**:

- `playback.play(wav_path)` (Phase A).
- `recorder.record(out_path, time_budget_seconds, early_exit_event)` (Phase B).
- `devices.default_input()`, `default_output()`, `list_devices()` (doctor + FR-009 pre-check).
