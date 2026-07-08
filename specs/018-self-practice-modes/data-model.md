# Phase 1 Data Model — Self-Practice Modes (018)

Exact field names and types the implementation targets. All new dataclasses are pure data (no engine import) and live in the mypy-gated modules.

---

## Mode A — Rescue-lines deck

### `LineCard` (`linecards/cards.py`)

One drillable corrected line. Content fields are rebuildable from reports; SRS fields are the live scheduling state.

```python
@dataclass(frozen=True)
class LineCard:
    card_id: str          # stable id: sha1(f"{question_id}\x1f{quote}\x1f{corrected}")[:12], or f"starter:{slug}"
    corrected: str        # the target line the learner hears/says ("Better:")
    quote: str            # the learner's original ("You said"); "" for starter cards
    rule: str             # short hint (pattern.explanation or pattern.label); "" if none
    question_id: str      # source question id; "" for starter cards
    source: str           # "report" | "starter"
```

- **Identity / uniqueness (FR-012)**: `card_id` is a pure hash of `(question_id, quote, corrected)`. The same correction seen in multiple reports collapses to one card.
- **Validity (FR-011)**: a card is only created when `corrected` is non-empty and `corrected != quote` (no-op corrections skipped).

### `CardState` — SRS scheduling state (persisted in the store)

Mirrors the observable fields of `store.ScheduleEntry`, keyed by `card_id` instead of `question_id`.

```python
# stored as a plain dict under Store.line_cards[card_id], merged with the LineCard content fields:
{
  "corrected": str, "quote": str, "rule": str, "question_id": str, "source": str,   # content (rebuildable)
  "last_grade": str | None,          # "poor"|"fair"|"good"|"strong"
  "interval_days": int,              # 0 for a never-reviewed card
  "next_due": str | None,            # ISO date YYYY-MM-DD; None/placeholder = due now
  "consecutive_strong": int,
  "mastered": bool,
  "last_practiced": str | None,      # ISO date
  "total_reviews": int,
}
```

**Self-mark → Grade mapping (FR-014/FR-015)**: `again → "poor"`, `hard → "fair"`, `good → "good"`, `easy → "strong"`. Rescheduling calls `srs.schedule.advance(...)` (the shared ladder), then stamps `next_due = today + interval`. Two consecutive `easy`(strong) marks → `mastered`, `interval = 30` (maintenance).

### `StarterCard` bundled data (`linecards/starter_cards.yaml`)

English-only, ≥ 8 entries. Each carries an explicit cloze span (no quote to diff).

```yaml
version: 1
cards:
  - slug: walk-you-through
    text: "Let me walk you through my approach."
    cloze: "walk you through"          # substring of text wrapped as {{c1::...}}
    rule: "signpost the structure before diving in"
  - slug: trade-off-here
    text: "The trade-off here is between latency and consistency."
    cloze: "trade-off"
    rule: "name the tension explicitly"
  # ... >= 8 total
```

Loaded into `LineCard(card_id=f"starter:{slug}", corrected=text, quote="", rule=rule, source="starter")`; the `cloze` span is used directly by the exporter.

### `Store.line_cards` section (`store/model.py`)

```python
# additive, default-empty; STORE_VERSION stays 1
line_cards: dict[str, dict] = field(default_factory=dict)   # card_id -> content+state dict (above)
```

- `to_dict`/`from_dict` round-trip it (absent in old stores → `{}`).
- **Rebuild fold (`store/rebuild.py`, FR-017)**: per report, derive cards from grammar evidence and insert content with placeholder SRS state (`interval_days=0`, `next_due=None`, `total_reviews=0`, `last_grade=None`) — the same placeholder trade-off as `schedule.next_due`. Standalone `deck` runs are the source of real scheduling state (live-only, like `pronounce`'s contrast tally).
- **Helpers**: `Store` gains small methods to upsert a card's state and to read cards; card *content* merge (add new derived cards, keep existing state) happens in `linecards`/`cli.deck` at runtime.

### Cloze export format (`linecards/cloze.py`, FR-018)

One card per line, matching the existing coach format:

```
A {{c1::new instance}} of activity A is created. (use "a" before a new singular noun)
The system {{c1::creates}} a new instance. (third person singular: system + creates)
Let me {{c1::walk you through}} my approach. (signpost the structure before diving in)
```

`to_anki(cards) -> str`: for a derived card, `cloze_from_correction(quote, corrected)` wraps the changed span; for a starter card, wrap the bundled `cloze` span. Trailing `(rule)` when `rule` is non-empty. Whole-deck snapshot (derived + starter, deduped by `card_id`).

---

## Mode B — Answer shadowing (all ephemeral; no persistence)

### `ShadowSentence` (`shadowing/split.py` output)

```python
# split_sentences(ideal_answer: str) -> list[str]
# each item is one sentence string, in reading order; paragraphs flattened.
```

### `CompletenessResult` (`shadowing/judge.py`)

```python
@dataclass(frozen=True)
class CompletenessResult:
    content_words: tuple[str, ...]   # key words of the sentence (post-stopword-removal), in order
    covered: tuple[str, ...]         # content words present in the repeat
    missed: tuple[str, ...]          # content words absent from the repeat
    coverage: float                  # len(covered) / len(content_words); 0.0 when no content words
    captured: bool                   # False when the repeat is empty/whitespace ("not captured")
```

- `coverage >= 0.70` → the CLI flags the sentence *strong* (display only; never blocks).
- `captured == False` when the ASR repeat is empty → reported as "didn't catch that", distinct from low coverage (FR-036).

### Per-sentence feedback (ephemeral, shown live)

The CLI composes, per sentence: the `CompletenessResult` (covered X/Y + missed list) plus pace + fillers from `metrics.compute_all(transcript)` — reading `speech_rate_wpm`, `filler_words_count`, `filler_density_per_100_words`. Nothing is persisted.

---

## Reused existing types (no change to their shape)

- `feedback.frontmatter.Session` / `GrammarPattern` / evidence dict `{attempt_ordinal, quote, corrected?}` — the Mode A card source (read-only).
- `srs.schedule.advance(...)` (new shared helper) + ladder constants — Mode A scheduling.
- `content.Question` (`ideal_answer: str`) via `content.load(...)` — Mode B material.
- `asr.Transcript` (`.text`, `.words`, `.audio_duration_seconds`) — Mode B repeat.
- `metrics.compute_all(transcript) -> dict[str, float|int]` — Mode B pace/fillers.
- `store.Store` / `store.io` — Mode A persistence.
