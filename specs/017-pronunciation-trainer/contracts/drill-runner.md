# Contract: `pronunciation/drill_runner.py` (pure per-drill loop + selection)

A new file in the existing `pronunciation/` module. It owns the hear → say → see → retry loop logic
for ONE drill and the weak-sound base-drill ordering. It is **pure and UI-agnostic**: it imports no
engine package and no `sessions`/`tts`/`audio` module; the speak/record/scorer/key_reader/console are
injected. Both the interview drill block (sessions) and the standalone command (cli) call it.

## `run_drill_item(...)`

```python
def run_drill_item(
    drill,                      # pronunciation.Drill
    *,
    contrast,                   # pronunciation.Contrast | None (for tip + competitors)
    scorer,                     # PronunciationScorer (duck-typed; never raises into the session)
    speak,                      # Callable[[str], None]  — synthesize+play target, or no-op when TTS off
    record,                     # Callable[[Path, str], None] — record to wav (caller provides UI)
    key_reader,                 # KeyReader (raw_capable gates replay/retry); may be a NullKeyReader
    console,                    # rich.Console for calibrated live prints
    scratch_dir,                # Path for the throwaway wav (discarded after scoring)
    retries: int = 1,           # bounded per-item retry budget (clamped 0..3 upstream)
    tts_on: bool = True,        # config toggle; speak() is also a no-op when TTS is unavailable
    is_follow_on: bool = False,
) -> dict: ...                  # the extended item dict (data-model §2)
```

**Behaviour**:
1. Print the prompt (cyan), tagged `(follow-up)` when `is_follow_on`.
2. **Hear-first**: if `tts_on`, call `speak(drill.prompt)`. When `key_reader.raw_capable`, enter a
   short interactive loop: `r`/`R` → `speak` again (replay on demand); `space`/`enter` → proceed to
   record; `q` → caller-defined quit signal (raise `DrillQuit` for standalone; the interview block maps
   it to "move on"). When not raw-capable, proceed straight to recording.
3. **Record + score**: `record(wav, label)` → `scorer.score(wav, canonical=…, targets=…, tip=…,
   competitors=…, …)`; unlink the wav. Map status/flags to the item dict; print the calibrated live
   summary via `pronunciation.feedback.live_flag_summary`.
4. **Bounded retry**: while the target is flagged AND `key_reader.raw_capable` AND retries remain:
   print "let's try that once more", `speak` again, `record`, `score`; decrement budget; stop early
   when the previously-flagged target index clears. Record `retry = {attempts, outcome, final_flags}`.
   `outcome` ∈ {`improved` (target cleared), `still_off`, `not_captured`}.
5. Return the item dict. **Never raises into the session** except the explicit `DrillQuit` sentinel
   (standalone quit), which the interview caller catches and treats as "stop asking for more".

**Invariants**: the first attempt's `flags` are preserved as the item `flags` (016 `with_flags`
semantics unchanged); `retry` is omitted when no retry ran; the wav is always unlinked (privacy);
deterministic given the same injected `record`/`scorer` outputs.

## `select_drills(...)`

```python
def select_drills(
    bank,                       # pronunciation.DrillBank
    *,
    weak_contrasts: list[str],  # contrast ids, most-weak first; [] when no history
    max_base: int,              # cap (interview: ≤4; standalone: --limit or a default)
) -> list[Drill]: ...
```

**Behaviour**: return up to `max_base` base drills (`bank.base_drills()`), ordered so that drills whose
`contrast_id` is in `weak_contrasts` come first (in `weak_contrasts` order), preserving the bank's
curated order within ties and for non-weak contrasts. When `weak_contrasts` is empty → the curated
order unchanged (the 016 `base_drills()[:max_base]`). Pure; no I/O.

## `DrillQuit(Exception)`

A small sentinel raised by `run_drill_item` when the learner presses `q` during a hear-first/retry
wait. The standalone command catches it to end the loop; the interview block catches it to stop the
drill block (the report is still written by `run_session`). Subclass of `PronunciationError` so any
caller that only catches the module base still degrades safely.

## Invariants

- No file-scope import of `torch`/`transformers`/`sessions`/`tts`/`audio` (guards:
  `test_engine_import_isolation.py`, `test_help_without_models.py`).
- Unit-tested with a fake scorer + fake `speak`/`record` + `FakeKeyReader` — no model/mic/tty/network.
