# Grammar eval — labeling protocol

**Feature**: 006-feedback-quality-reliability · **Instrument for**: SC-001 (failure rate),
SC-002 (grammar agreement). This protocol is the rubric a labeler follows to author a
`cases/case-NNN.yaml` file. It is the human contract behind the numbers; the machine-checkable
half lives in `contracts/eval-set-format.md` (E1–E4) and is enforced by `run_eval.py --validate-only`.

> Everything here is a **validation artifact**, never shipped (`eval/` is outside the wheel).
> No real recordings, no real names, no machine paths (Principle III / E3).

## 1. What counts as an error (labeling rubric)

A `gold_issue` is recorded only when **all** of these hold:

1. **It is a grammar error**, not a vocabulary choice, pronunciation artifact, or content
   judgment. The shipped analyzer is grammar-only (`grammar_analyzer._build_system_prompt`).
2. **It is anchored to a verbatim span.** The `quote` MUST be an exact substring of the
   referenced transcript (E1, mirrors the analyzer's V1 verbatim guarantee). Quote the
   *minimal* span that carries the error.
3. **It is coherent English, not ASR garble.** If a fluent reader cannot tell what was meant,
   it is garble — do **not** label it (the deterministic coherence filter would drop it anyway;
   labeling it would unfairly penalize recall). Garble belongs in `notes`, not `gold_issues`.
4. **The correction is itself correct** and is a *minimal* rewrite of the quote — change only
   what the error requires. A `correction` equal to the `quote` is not an error (it would be a
   no-op fix, which the analyzer suppresses — V3).

A case with **zero** `gold_issues` is valid and **encouraged**: a clean, correct transcript
measures the false-alarm rate (precision). Include several.

## 2. Taxonomy (labels)

`label` is either a **catalog label** (preferred when it fits) or an explicit **open-bucket**
label. The catalog is `src/speakloop/feedback/persian_l1_catalog.yaml` — labels (and their
`impact_rank`) at the time of writing:

| Catalog label | `catalog_id` | rank |
|---|---|---|
| `gerund/infinitive confusion` | gerund-infinitive-confusion | 2 |
| `comparative form error` | comparative-form | 2 |
| `plural/singular agreement` | plural-agreement | 3 |
| `3rd-person singular -s drop` | 3sg-s-drop | 3 |
| `auxiliary be/do drop` | aux-drop | 3 |
| `definite/indefinite article omission (common nouns)` | article-omission-common | 4 |
| `preposition substitution / non-standard preposition` | preposition-substitution | 4 |
| `possessor-order transfer (ezafe)` | possessor-order | 4 |

If the error fits a catalog row, use that exact label string. Otherwise pick a short, surface-true
**open-bucket** label (e.g. `tense agreement`, `word order`) — open-bucket findings need
`occurrence_count >= 2` and an explanation to survive in the live analyzer (V4), so prefer the
catalog when in doubt. The scorer's match rule treats two open-bucket labels as compatible only
when they describe the **same surface type** (see `contracts/eval-set-format.md` §3).

## 3. Adjudication (ambiguous calls)

- **Two plausible labels for one span** → choose the catalog label that names the *grammatical
  mechanism* (e.g. "since two years" is a preposition error, not a plural error), and record the
  alternative in `notes`.
- **Overlapping spans** → label the smallest span that isolates a single mechanism; do not stack
  two issues on identical spans.
- **Dialectal but acceptable** (e.g. "different than") → not an error; note it.
- **Error the catalog can't name** → open-bucket with a surface-true label; justify in `notes`.
- **Disagreement between labelers** → the `notes` field records the resolved call and the dissent,
  so the gold set is auditable. One labeler + adjudication notes is acceptable for a synthetic set.

## 4. Provenance & de-identification

Every case is **synthetic or de-identified** (`source: synthetic | deidentified`). Synthetic
transcripts are written to mimic Persian-L1 spoken technical English (the target user) without
copying any real session. De-identified cases must strip names, employers, and any path/handle.
See `README.md`.
