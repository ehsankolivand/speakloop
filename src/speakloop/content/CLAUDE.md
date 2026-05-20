# content

Q&A YAML loading + validation.

**Public surface**:

- `schema.Question`, `schema.QAFile` (dataclasses, validated).
- `loader.load(path) -> QAFile`. Raises with file path + line number on YAML error
  (FR-029); raises naming the entry id + missing field on schema error (FR-030).
Default questions ship in the repo at the **top-level `content/questions.yaml`**
(004-public-release-readiness), not inside this package. The active file is chosen by
`paths.resolve_qa_file()`: `--qa-file` → `~/.speakloop/qa.yaml` (personal override, if
present) → `content/questions.yaml` (in-repo default). No file is auto-created on first
run. This module just loads/validates whatever path it is given.

Matches `specs/001-v1-product-spec/contracts/content-schema.yaml`.
