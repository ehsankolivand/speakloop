# content

## Purpose

Q&A YAML loading + validation. Loads and validates whatever question file it is given; it does
not choose the file (that is `config.resolve_qa_file`) and never auto-creates one. A leaf module.

## Public interface

- `schema.Question`, `schema.QAFile` — validated dataclasses.
- `loader.load(path) -> QAFile` — raises with file path + line number on YAML error; raises
  naming the entry id + missing field on schema error.
- `loader.QALoadError`, `schema.QASchemaError`.

## Dependencies

- Third-party: `pyyaml`. No internal module deps (leaf); no engine packages.

## Consumers

`cli`, `sessions`.

## File map

- `schema.py` — `Question` / `QAFile` dataclasses + `QASchemaError`.
- `loader.py` — `load()` + `QALoadError`.

## Common modification patterns

- **Add a question field**: add it to `schema.Question` (keep it optional for back-compat) and
  validate in `loader.load`. Match `specs/001-v1-product-spec/contracts/content-schema.yaml`.

## Traps

- Default questions ship at the repo-root **`content/questions.yaml`** (004), not inside this
  package; `~/.speakloop/qa.yaml` is the opt-in personal override. No file is auto-created on
  first run.

## Pointers

- Root map: [`../../../CLAUDE.md`](../../../CLAUDE.md);
  schema contract: `specs/001-v1-product-spec/contracts/content-schema.yaml`.
