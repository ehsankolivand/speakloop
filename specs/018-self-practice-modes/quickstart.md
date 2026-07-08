# Quickstart — Self-Practice Modes (018)

## Mode A — Rescue-lines deck

```bash
# Drill the corrected lines due today (self-graded; TTS only, no mic/ASR):
uv run speakloop deck                    # hear -> say -> see -> self-mark (1/2/3/4)
uv run speakloop deck --limit 10         # cap this run to 10 cards

# Export the whole deck as Anki cloze cards (offline, no models):
uv run speakloop deck --export ~/cards.txt
#   -> one card per line, changed word wrapped {{c1::...}}, trailing (rule hint)
```

- Cards come from the "Better:" corrections in `data/sessions/*.md`, deduped, plus a bundled starter set (≥ 8 interview discourse chunks) so a brand-new user is never empty.
- Self-marks reschedule each card on the existing SRS ladder; progress persists in `~/.speakloop/store.json` (`line_cards` section). `speakloop rebuild` re-derives card content from reports (scheduling resets to placeholder — same as the question schedule).

**Verify**:
```bash
uv run speakloop deck --help             # works with no models; loads no engine
uv run pytest tests/unit/linecards tests/unit/cli/test_deck_command.py
uv run pytest tests/unit/store           # line_cards round-trip + rebuild fold
```

## Mode B — Answer shadowing

```bash
# Shadow a question's ideal answer sentence-by-sentence (TTS + ASR, no scorer/LLM):
uv run speakloop shadow                   # interactive question picker
uv run speakloop shadow --question activity-rotation-callbacks
uv run speakloop shadow --slow --limit 5  # slower first read; first 5 sentences
```

- Each sentence: hear it -> repeat it -> get **completeness** (covered X/Y key words + which were missed) plus **pace** (WPM) and **fillers**. Deterministic, fully offline. No report; the recording is deleted after transcription.

**Verify**:
```bash
uv run speakloop shadow --help            # works with no models; loads no engine
uv run pytest tests/unit/shadowing tests/unit/cli/test_shadow_command.py
```

## Whole-feature gates

```bash
uv run pytest                                            # full suite green (baseline 926 passed)
uv run pytest tests/integration/test_help_without_models.py        # no engine import at module load
uv run pytest tests/unit/asr/test_engine_import_isolation.py       # engines stay in one wrapper each
uv run mypy                                              # add linecards + shadowing to scope; stays green
uv run ruff check src/speakloop/linecards src/speakloop/shadowing src/speakloop/cli/deck.py src/speakloop/cli/shadow.py
```

## Manual smoke (optional, needs models)

```bash
uv run speakloop deck                      # confirm hear-before-see, self-mark reschedules
uv run speakloop shadow --question activity-destroyed-definition   # confirm per-sentence feedback
```
