# Baseline (before) — observed failures

10 real `claude` (sonnet) grammar calls over the fixture transcripts.

| Failure kind | Count | Detail |
|--------------|-------|--------|
| JSON parse failure (any rung) | **0** | every returning call parsed on rung 1 (strict `json.loads` after fence-strip) |
| Bounded regenerate fired | **0** | the `payload is None or _looks_like_repetition_loop` trigger never fired |
| `ClaudeCodeTimeoutError` (240 s) | **2** | runs 7 & 10 — single grammar pass exceeded the 240 s engine timeout and was aborted |

There is **no raw model output to save** for the two failures: a timeout aborts the
subprocess before any `result` is returned, so nothing was emitted to parse. The failure
mode observed is a **model-latency tail** (single-pass sonnet grammar analysis occasionally
runs past the 240 s ceiling), **not** a JSON-discipline problem.

This means the parse-failure → bounded-regenerate path that this sprint set out to eliminate
**did not reproduce** in the sample. Per the honesty clause, the JSON-discipline prompt change
is applied anyway as low-risk preventive hardening (it cannot hurt and addresses the
hypothesized fence/preamble/escaping/truncation modes), and this is stated plainly in the
report. The latency tail / timeout is a separate model-latency issue, out of scope for a
prompt JSON-discipline change.
