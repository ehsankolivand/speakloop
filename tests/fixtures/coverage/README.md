# Coverage fixtures (010-interview-loop, P3)

Human-labelled key-point + coverage cases backing **SC-004** (artifacts consistent
with the ideal answer), **SC-009** (first→final coverage visible), and the coverage
scoring/content-error tests.

## Labeling rubric

`cases.yaml` pairs an ideal answer with its derived key points and, per attempt,
the expected coverage state of each point plus any content errors. Authored
independently of the implementation. States: `covered` (core assertion stated
correctly), `partial` (mentioned but incomplete/hedged), `missed` (absent or
contradicted). A `content_error` is a *mutually-exclusive* contradiction only
(omissions and extra-correct facts are NOT content errors).

Tests stub the LLM with a **recorded** coverage JSON response (the model's judgment
is not re-run live) and assert the deterministic parts: parse/validate, the
aggregate `(covered + 0.5·partial)/N`, the first→final delta, the key-point-version
guard, and content-error filtering. No byte-exact golden files.
