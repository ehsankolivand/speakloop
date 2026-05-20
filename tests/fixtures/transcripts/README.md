# Gold-set transcript fixtures

Human-labelled transcript → expected-pattern fixtures backing **SC-002**
(catalog-accurate labels) and **SC-003** (anchored, corrected fixes). The LLM is
always stubbed in tests; these fixtures are the ground truth the stub is checked
against.

## Contract

Each gold-set case (authored in T016, consumed by T019) pairs a short spoken
transcript with the catalog label(s) the analyzer is expected to surface — or an
expected **drop** for ASR garble. Documented cases:

| Transcript snippet                              | Expected outcome                          |
|-------------------------------------------------|-------------------------------------------|
| `I like to programming`                         | label `gerund/infinitive confusion`       |
| `eight year experience`                         | label `plural/singular agreement`         |
| `I like my job even bigger than ten years ago`  | label `comparative form error`            |
| `Killing RT check`                              | **dropped** by the coherence filter (FR-006) |

Cases live as YAML fixtures (`*.yaml`) so they are data, not code. Each carries
the verbatim transcript text plus `expected_labels` / `expected_dropped`. Attested
technical jargon (`Kotlin`, `coroutine`, `dispatcher`) must be **kept**, never
treated as garble.

Pre-existing transcript fixtures (used by the v1 ASR/engine tests via the
`transcript_fixture` conftest fixture) may also live here; the gold-set files are
additive and do not disturb them.
