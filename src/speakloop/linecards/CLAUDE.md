# linecards

## Purpose

Rescue-lines deck — Mode A pure logic (018). Derives spaced-repetition flashcards from the
learner's OWN corrected lines in past session reports (the "Better:" corrections in
`grammar_patterns[].evidence[]{quote, corrected}`) plus a bundled starter set, schedules them on
the shared SRS ladder, and exports them as offline Anki cloze cards. **Pure logic** — no engine
import; the only I/O is reading report `.md` files and the bundled starter YAML. mypy-gated.

Consumed by the thin `cli/deck.py` orchestrator (`speakloop deck`).

## Public interface (`from speakloop import linecards`)

- `LineCard` — frozen dataclass: `card_id`, `corrected`, `quote`, `rule`, `question_id`,
  `source` ("report"|"starter"), `cloze` (explicit span for starter cards; "" → exporter diffs).
- `card_id(question_id, quote, corrected) -> str` — stable 12-char sha1; the SAME correction
  across reports collapses to one card (FR-012).
- `derive_cards(reports_dir) -> list[LineCard]` — fold every report (flat glob, per-file
  tolerance like `trends.reader`), dedupe by `card_id`. Skips no-op / absent corrections (FR-011).
- `cards.cards_from_session(session) -> list[LineCard]` — per-report derivation (no dedupe);
  shared with `store.rebuild` so the derivation rule lives in ONE place.
- `merge_cards(derived, starter, stored) -> dict[card_id, {content+state}]` — deck content from
  derived+starter, SRS state kept from the stored `line_cards` map (new cards added, history kept).
- `select_due(cards, *, today, capacity, ahead=False) -> list[card_id]` — due (never-reviewed or
  `next_due<=today`) most-overdue-first, ties→lower grade→oldest practiced, capped; `ahead` →
  soonest-due when nothing is due (FR-016/020). `any_due(cards, *, today) -> bool`.
- `advance_card(state, grade, *, today) -> dict` — reschedule one card via `srs.schedule.advance`
  (the SHARED ladder — same tuning surface as questions). Self-mark → grade:
  again→poor, hard→fair, good→good, easy→strong.
- `cloze_from_correction(quote, corrected) -> str` — word-diff → wrap the changed span in
  `{{c1::…}}`; degenerate diff → cloze whole line. `to_anki(cards) -> str` / `anki_line(card)` —
  one card per line, trailing `(rule)`, matching the cloud-coach format (FR-018).
- `load_starter_cards() -> list[LineCard]` — the bundled `starter_cards.yaml` (≥ 8, English-only).
- state helpers: `new_state()` (placeholder SRS), `content_dict(card)`, `card_from_row(id, row)`.

## Dependencies & consumers

- Depends on: `speakloop.feedback.frontmatter` (parse reports), `speakloop.srs.schedule`
  (`advance` ladder) + `speakloop.srs.grade` (`Grade`), `pyyaml`. **No engine package; no
  `speakloop.store` import** (store folds cards via a function-local import of `cards`, so there
  is no cycle).
- Consumers: `cli/deck.py` (the `speakloop deck` command); `store/rebuild.py` (function-local
  `cards_from_session`/`content_dict`/`new_state`).

## File map

- `cards.py` — `LineCard`, `card_id`, `derive_cards`/`cards_from_session`, `merge_cards`, state
  serialization (`new_state`/`content_dict`/`card_from_row`).
- `cloze.py` — `cloze_from_correction` (difflib word-diff), `anki_line`, `to_anki`.
- `deck.py` — `advance_card` (calls `srs.schedule.advance`), `select_due`, `any_due`.
- `starter.py` + `starter_cards.yaml` — bundled starter cards loader + data.

## Invariants & traps

- **Rebuildable, cache-only**: card CONTENT re-derives from report evidence; the per-card SRS
  scheduling state is the live part (`rebuild` restores a placeholder, exactly like
  `schedule.next_due`). Documented in `store/CLAUDE.md`.
- **Single ladder**: card scheduling MUST go through `srs.schedule.advance` — never re-implement
  the interval math here (O14 single tuning surface).
- **No no-op cards**: skip evidence where `corrected` is empty or equals `quote` (mirrors
  `report_builder._pattern_card`).
- Every starter `cloze` MUST be a substring of its `text` (the exporter wraps it) — pinned by
  `tests/unit/linecards/test_starter.py`.

## Pointers

- Root map: `../../../CLAUDE.md`. Spec: `specs/018-self-practice-modes/`. SRS ladder:
  `../srs/CLAUDE.md`. Store section: `../store/CLAUDE.md`.
