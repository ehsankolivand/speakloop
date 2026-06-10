# Store fixtures (010-interview-loop, P2a)

Sample session sets and their expected rebuilt store, backing the
`tests/unit/store/test_rebuild.py` round-trip (the derived store is fully
rebuildable from session files — research R4).

A test points `paths.set_sessions_dir(...)` at a small set of session `.md`
fixtures (reuse `tests/fixtures/sessions/`), runs `store.rebuild(sessions_dir)`,
and asserts the resulting schedule entries (next-due dates from replayed grades),
key-point sets, and per-pattern series — then asserts a second rebuild is
idempotent. No byte-exact golden file; assertions are on parsed values.
