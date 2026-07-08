# shadowing

## Purpose

Answer shadowing — Mode B pure logic (018). Splits a question's ideal answer into sentences
(abbreviation-aware) and judges a learner's spoken repeat for content-word completeness. **Pure
logic** — no engine import, deterministic and fully offline. mypy-gated.

Consumed by the thin `cli/shadow.py` orchestrator (`speakloop shadow`), which pairs this with the
resident TTS/ASR and `metrics.compute_all` for the live per-sentence feedback.

## Public interface (`from speakloop import shadowing`)

- `split_sentences(text) -> list[str]` — split an ideal answer into sentences. Blank-line
  paragraph breaks are hard boundaries; a `.`/`?`/`!` splits only when it is not a decimal
  (`3.14`), not inside a `.`-glued identifier (`System.out` — no following space), and not a known
  abbreviation (`e.g.`, `i.e.`, `etc.`, …). Sub-2-word fragments are merged into their neighbour.
- `judge_completeness(sentence, repeat_text) -> CompletenessResult` — deterministic content-word
  scoring. `content_words` = normalized tokens (`[A-Za-z0-9']+`, lowercased) minus the English
  function-word set; `covered`/`missed` by presence in the repeat; `coverage` = covered/total;
  `captured` is False for an empty repeat ("not captured", distinct from low coverage). `.is_strong`
  is `coverage >= STRONG_COVERAGE` (0.70) — a display flag only; nothing blocks progress.
- `CompletenessResult` — frozen dataclass (see fields above). `STRONG_COVERAGE = 0.70`.

## Dependencies & consumers

- Depends on: stdlib only (`re`, `dataclasses`, `difflib` is NOT used here). **No engine package,
  no `speakloop.*` engine import.**
- Consumers: `cli/shadow.py` (the `speakloop shadow` command). The command adds pace/fillers via
  `metrics.compute_all` — this module never imports `metrics` (stays a leaf).

## File map

- `split.py` — `split_sentences` + the guarded splitter (`_ABBREV` set, `_BOUNDARY`/`_LAST_TOKEN`
  regexes, `_merge_short`).
- `judge.py` — `judge_completeness`, `CompletenessResult`, `_STOPWORDS`, `STRONG_COVERAGE`.

## Invariants & traps

- **Deterministic & offline**: no model in the loop; identical output for a fixed transcript
  (pinned by `tests/unit/shadowing/test_judge.py`). Never add an LLM/engine call here.
- **Completeness is formative, not pass/fail** (spec clarification): the judge only reports
  covered/missed; the CLI never blocks advancing on a low score.
- The abbreviation set is deliberately small and collision-safe (no bare `no`/`st`/`al`, which
  appear inside common words). Extend it carefully with the `endswith`-boundary logic.

## Pointers

- Root map: `../../../CLAUDE.md`. Spec: `specs/018-self-practice-modes/`. Warm-up judge (the
  normalization this mirrors): `../warmup/CLAUDE.md`. Metrics: `../metrics/CLAUDE.md`.
