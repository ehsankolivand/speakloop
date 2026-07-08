# Phase 0 Research — Offline Self-Practice Modes (018)

Decisions that shape the design, each with rationale and rejected alternatives. All are grounded in a code-true read of the current tree (feature 016/017 `pronounce` template, `srs`, `store`, `feedback.frontmatter`, `warmup`, `metrics`, `asr`, `tts`, `content`).

---

## D1 — Mode A card source: structured grammar evidence, not coach cards

**Decision**: Derive line-cards from `grammar_patterns[].evidence[]` — each item is a plain dict `{attempt_ordinal: int, quote: str, corrected?: str}` — taking items where `corrected` is present and `corrected != quote`. The pattern's `label`/`explanation` supply the rule hint. Skip no-op corrections (mirrors `report_builder._pattern_card`, which drops `better == you_said`).

**Rationale**: This evidence is machine-readable YAML frontmatter that round-trips through `feedback.frontmatter.parse` and is **fully reconstructable from reports** → the store stays a pure cache. 40+ existing reports already carry these pairs.

**Alternatives rejected**:
- *Parse the cloud coach's Anki cards* (`Session.coaching`): rejected — coaching is a **free-form Markdown blob, body-only, and does NOT round-trip through the parser** (never serialized to / read from frontmatter). It is also cloud-only. Deriving cards from it would be unparseable and non-rebuildable, breaking the store invariant.

## D2 — Reuse the SRS ladder generically via an extracted `advance()`

**Decision**: Extract the pure recurrence inside `srs.schedule.next_due` into `srs.schedule.advance(prev_interval, consecutive_strong, mastered, grade) -> AdvanceResult` (returns `interval_days`, `consecutive_strong`, `mastered`). `next_due` becomes a thin wrapper that computes `prev`, calls `advance`, and stamps the `ScheduleEntry` dates. A new `linecards.advance_card` uses the same `advance` for card SRS state.

**Rationale**: The interval ladder (poor→1d, fair→2d, good→×2, strong→×2.5, cap 21d, mastery 2×strong→30d) becomes the **single tuning surface** for both questions and cards. Behavior-preserving: existing `srs` unit tests pin `next_due` and must stay green.

**Alternatives rejected**:
- *Duplicate the ladder constants/branches in `linecards`*: rejected — two tuning surfaces drift.
- *Duck-type a `ScheduleEntry` for cards*: rejected — `ScheduleEntry` is `question_id`-keyed and `next_due` constructs one; abusing it for cards muddies both.

## D3 — No RAM/phoneme-model gate

**Decision**: Neither mode loads the wav2vec2 phoneme scorer, so neither uses `assess_standalone_safety`/`assess_safety`. `deck` provisions Phase A (TTS); `shadow` provisions Phase B (TTS+ASR); each via the existing `installer.ensure_models(...)` consent flow.

**Rationale**: The pronunciation RAM gate exists specifically because `pronounce` stacks the ~1.26 GB wav2vec2 model on resident models. These modes never load it. Adding a gate that can't meaningfully fire is cruft. This matches listen-only `practice`, which has no special gate.

**Alternatives rejected**: *Bolt on a token gate for template symmetry* — rejected as dead code.

## D4 — Cloze derivation: word-level diff of quote → corrected

**Decision**: `cloze_from_correction(quote, corrected)` computes a word-level diff (stdlib `difflib.SequenceMatcher` over normalized tokens) and wraps the **inserted/replaced span(s)** of `corrected` in `{{c1::…}}`, emitting a single Anki line `"<corrected with cloze>. (<rule hint>)"`. When the diff is degenerate (pure deletion, or no clean span), fall back to clozing the whole corrected phrase. Starter cards carry an explicit cloze span in the bundled YAML (no quote to diff).

**Rationale**: Matches the existing coach format exactly (`{{c1::…}}`, one card/line, trailing `(hint)` — verified in `openrouter_coach_prompt_default.txt` and real report bodies). Clozing the *changed* token is the whole point ("the user forgot the article `a`" → `{{c1::a}} new instance`). Pure/deterministic → unit-testable, mypy-gated.

**Alternatives rejected**: *Cloze the entire corrected line always* — rejected as less targeted; the diff gives the precise recall target the correction is about.

## D5 — Self-mark → existing four-level Grade

**Decision**: The deck's self-mark buttons map onto the existing `srs.grade.Grade` literal: **again→poor, hard→fair, good→good, easy→strong**. Keys `1/2/3/4` (also `a/h/g/e`), read via the shared `sessions.keyboard` reader; `r` replays, `q` quits.

**Rationale**: Reuses the ladder unchanged (D2) and the shared keyboard reader (no new tty code). Two consecutive `easy`(strong) marks retire the card to maintenance, exactly like a question.

## D6 — Abbreviation-aware sentence splitter (Mode B)

**Decision**: `split_sentences(text)`: (1) split on blank-line paragraph breaks; (2) within a paragraph, split on `[.?!]` + whitespace + capital/EOL, but **do not** split when the period sits between two digits (decimals/versions), inside a dotted/`camelCase` identifier, or immediately after a known abbreviation (`e.g.`, `i.e.`, `vs.`, `etc.`, `Dr.`, `Mr.`, `Ms.`, `Fig.`, `No.`, `approx.`). Merge fragments shorter than a small word floor into the neighbor so no 1–2-word "sentence" is produced.

**Rationale**: The real `ideal_answer` corpus is dense with `API 28`, `ON_DESTROY`, `onSaveInstanceState`, `600dp`, `PROPERTY_COMPAT_ALLOW_RESTRICTED_RESIZABILITY` — a naive `.split(".")` over- or under-splits. A guarded regex splitter is boring, deterministic, and mypy-gateable; a full NLP tokenizer would add a dependency and violate "boring over novel". The answers are clean sentence-terminated prose, so the guard set is small.

**Alternatives rejected**: *`nltk`/`spacy` sentence tokenizer* — rejected (heavy dependency, offline-model download, overkill for clean prose).

## D7 — Completeness judge: content-word coverage, formative

**Decision**: `judge_completeness(sentence, repeat_text) -> CompletenessResult` with `content_words: list[str]`, `covered: list[str]`, `missed: list[str]`, `coverage: float`. Content words = normalized tokens of `sentence` minus an English stopword/function-word set (articles, pronouns, prepositions, auxiliaries, conjunctions). A content word is "covered" iff its normalized token appears in the normalized repeat. Coverage = `len(covered)/len(content_words)`. **Formative**: no pass/fail gate; a sentence is *flagged strong* at `coverage >= 0.70`. Reuse `warmup.drill`'s normalization approach (`_WORD_RE`, lowercase join).

**Rationale**: Mirrors the deterministic warm-up judge the repo already trusts. Deterministic for a fixed transcript (SC-008). Excludes function words so "the/a/of" don't inflate coverage.

**Alternatives rejected**: *Stemming/lemmatization* — rejected for v1 (adds a dependency; exact normalized match is predictable and good enough for whole-sentence shadowing). *Hard pass/fail* — rejected (shadowing is formative practice, not a test; the spec clarification pins this).

## D8 — Deck due-selection order

**Decision**: `linecards.select_due(cards, *, today, capacity)` returns due cards (never-reviewed OR `next_due <= today`) ordered most-overdue-first, ties by lower last-grade then oldest-practiced (mirrors `srs.queue.due_queue` semantics), truncated to `capacity` (default 20, or `--limit`). When nothing is due, `deck` offers to practise ahead by drilling the soonest-due cards up to the cap.

**Rationale**: Reuses the established priority intuition from `srs.queue`. Bounded runs keep sessions short.

## D9 — Store `line_cards` section shape + rebuild

**Decision**: `Store.line_cards: dict[str, dict]` (default `{}`), `card_id -> {corrected, quote, rule, question_id, source, interval_days, next_due, consecutive_strong, mastered, last_grade, last_practiced, total_reviews}`. `card_id` = short stable hash of `(question_id, quote, corrected)` for derived cards, or `starter:<slug>` for starter cards. `to_dict`/`from_dict` round-trip it (default-empty). `store.rebuild` folds cards from report evidence with **placeholder SRS state** (never-reviewed); `deck` runtime merges freshly-derived content with any stored SRS state (keeping review history, adding new cards). `STORE_VERSION` stays 1.

**Rationale**: Exact mirror of the 017 `pronunciation_contrasts` additive pattern. Content is rebuildable; scheduling state is the "live" part that a manual `rebuild` resets — the same documented trade-off as `schedule.next_due`.

## D10 — Mode B is ephemeral (no store) in v1

**Decision**: `shadow` writes nothing to the store or reports. The "chronically-mangled sentence" tally is a noted future extension.

**Rationale**: `shadow` never runs inside an interview session, so any store section it populated would be **100% live-only and always empty on `rebuild`** — a weaker rebuildability story than `pronunciation_contrasts` (which is rebuildable from interview-session reports). Keeping v1 ephemeral avoids introducing a never-rebuildable section and keeps the footprint minimal. The intent explicitly frames this tally as optional.

## D11 — Config surface: reuse, one new key

**Decision**: Reuse `cfg.pronunciation_tts_speed` (already clamped 0.5–1.5) for the deck's coaching cadence and shadow's read; reuse `loop_config.teach_speed(...)` for shadow's optional slower replay. Add exactly one optional `loop.yaml` key `deck_daily_capacity` (default 20, floor 1) via the existing `_int` helper.

**Rationale**: Minimal additive config surface; follows the `daily_capacity` precedent for the deck's run cap. `--limit` remains the per-run override.

---

## Open items → resolved

All spec `[NEEDS CLARIFICATION]` were resolved during `/speckit-specify` + `/speckit-clarify` (see spec `## Clarifications`). No unresolved unknowns remain for planning.
