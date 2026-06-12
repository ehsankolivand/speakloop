# content

## Purpose

Q&A YAML loading + validation. Loads and validates whatever question file it is
given; it does not choose the file (that is `config.resolve_qa_file`) and never
auto-creates one. A leaf module.

## Public interface

- `schema.Question` — frozen dataclass; fields: `id`, `question`, `ideal_answer`,
  `tags`, `difficulty`, `voice_override`, `type` (default `"definition"`).
- `schema.QAFile` — frozen dataclass; fields: `schema_version`, `questions`,
  `warnings` (list of strings for unknown keys / unrecognised difficulty or type).
- `schema.QASchemaError(message, *, entry_id, missing_field)` — raised on validation
  failure; `.entry_id` and `.missing_field` are always set so callers can surface them.
- `schema.parse(doc: dict) -> QAFile` — module-level public function; validates a
  pre-parsed YAML mapping.
- `loader.load(path: Path) -> QAFile` — reads, parses, and validates; raises
  `QALoadError` with `file:line` on YAML error, `file: entry id=... missing field...`
  on schema error (FR-029/FR-030).
- `loader.QALoadError` — wraps both error kinds.
- `template.template_text() -> str` (015) — the canonical commented, schema-valid starter
  question set. Single source of truth for `speakloop questions template`; must round-trip
  through `load()` unedited (guarded by `tests/unit/content/test_question_template.py`).

## Key schema constants (schema.py)

- `MAX_ID_LEN = 40`, `MAX_QUESTION_LEN = 1000`, `MAX_IDEAL_ANSWER_LEN = 4000`
  (`schema.py:9-11`).
- `KEBAB_CASE` regex enforced on every `id` (`schema.py:8`).
- `_VALID_TYPES = {"definition", "behavioral", "hypothetical"}` (`schema.py:53`);
  `type` defaults to `"definition"` on absent/unknown values; unknown types produce a
  warning, not an error (`schema.py:135-138`).
- `_VALID_DIFFICULTIES = {"easy", "medium", "hard"}` (`schema.py:52`); unrecognised
  values produce a warning + `difficulty=None` (`schema.py:121-123`).
- Unknown YAML keys in an entry produce a `QAFile.warnings` entry, not an error
  (`schema.py:140-142`).

## Dependencies & consumers

- Third-party: `pyyaml`. No internal deps (leaf); no engine packages.
- Consumers: `cli`, `sessions` (and indirectly every command that loads questions).

## File map

- `schema.py` — `Question`, `QAFile`, `QASchemaError`, `parse()`, constants.
- `loader.py` — `load()`, `QALoadError`.
- `template.py` (015) — `template_text()`; the commented starter set, kept next to `schema.py`
  so the two stay in sync. Printed to stdout by `cli/questions.py` (never written to home).

## Invariants & traps

- Default questions ship at the repo-root `content/questions.yaml` (feature 004),
  not inside this package. `~/.speakloop/qa.yaml` is the opt-in personal override.
  No file is auto-created on first run. File-choice logic lives in `config/paths.py`.
- `schema_version` of the Q&A file is separate from the report `schema_version`
  (both are 1, but the Q&A schema is validated here, not in `feedback/`).
- `parse()` is module-level (not a method), so callers that already hold a parsed
  dict can bypass the YAML I/O in `load()`.

## Common modification patterns

- **Add a question field**: add it to `schema.Question` (optional, for back-compat),
  add to `_KNOWN_FIELDS`, validate in `parse()`.
- **Add a validated type or difficulty**: extend `_VALID_TYPES` / `_VALID_DIFFICULTIES`.

## Pointers

- Root map: `CLAUDE.md` (repo root).
- Schema contract: `specs/001-v1-product-spec/contracts/content-schema.yaml`.
- Testing rules: `.claude/rules/testing.md`.
