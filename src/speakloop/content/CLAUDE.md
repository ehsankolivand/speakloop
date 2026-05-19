# content

Q&A YAML loading + validation.

**Public surface**:

- `schema.Question`, `schema.QAFile` (dataclasses, validated).
- `loader.load(path) -> QAFile`. Raises with file path + line number on YAML error
  (FR-029); raises naming the entry id + missing field on schema error (FR-030).
- `starter.yaml` — shipped Q&A, copied to `~/.speakloop/qa.yaml` on first run.

Matches `specs/001-v1-product-spec/contracts/content-schema.yaml`.
