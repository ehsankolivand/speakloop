# Quickstart — Running the Context Engineering Audit

**Feature**: 005-context-engineering-audit

How to reproduce the audit and the sub-agent review from a clean checkout. All commands
run from the repo root. No new dependency is installed.

## 1. Reconnaissance (code-wins ground truth)

```bash
# Line counts of every CLAUDE.md (SC-A baseline)
find . -name CLAUDE.md -not -path '*/node_modules/*' | sort | xargs wc -l

# Engine-import owner map (Principle V, SC-L, FR-006)
rg -n "^\s*(import|from)\s+(mlx_whisper|silero_vad|onnxruntime|parakeet_mlx|mlx_lm|kokoro)" src/speakloop/

# Personal-path leak in the research doc (FR-041, SC-F)
grep -n "/Users/" doc/research_context_engineering.md

# Tests coupled to CLAUDE.md content (SC-H, FR-054)
rg -ln "CLAUDE\.md" tests/

# Confirm `speakloop doctor` exists (FR-003)
rg -n "doctor" src/speakloop/cli/main.py
```

## 2. Verify documented commands (FR-003, FR-012, SC-I)

```bash
uv run speakloop --help        # must work with no models (Principle VIII)
uv run speakloop doctor        # health check — confirm exit 0
uv run pytest                  # full suite stays green (SC-H)
uv run pytest -m live_asr      # only when touching torchaudio
ruff check .                   # lint
```
Mark each `verified` / `failed` / `missing` in the command matrix (research §E). Remove
any failing/missing command from the docs; add any real-but-undocumented one.

## 3. Measure the launch footprint (FR-043, SC-K)

```bash
# Precise (cl100k_base) — tiktoken invoked ephemerally, NOT added to pyproject:
uv run --with tiktoken python - <<'PY'
import tiktoken, pathlib
enc = tiktoken.get_encoding("cl100k_base")
paths = ["CLAUDE.md"]  # + any UNSCOPED .claude/rules/*.md
total = sum(len(enc.encode(pathlib.Path(p).read_text())) for p in paths)
print(f"launch footprint: {total} tokens (ceiling 6000)")
assert total <= 6000, f"OVER BUDGET by {total-6000}"
PY

# Offline fallback (stdlib char proxy):
python3 -c "import pathlib;c=len(pathlib.Path('CLAUDE.md').read_text());print(f'{c} chars ≈ {c//4} tokens (ceiling 6000)')"
```
Module `CLAUDE.md` files and `paths`-scoped rules MUST contribute 0 (they do not load at
launch — confirm none is unscoped).

## 4. Reproduce the adversarial sub-agent review (FR-014, SC-C)

Invoke the Claude Code Task/general-purpose (or Explore) agent with the exact prompt in
`research.md §I`. The agent reads ONLY `CLAUDE.md` + `src/speakloop/` + `tests/` +
`pyproject.toml` + the constitution, and returns a severity-classified divergence table
ending in `VERDICT: PASS|FAIL`. Required result: **PASS** (0 CRITICAL, 0 MAJOR). On FAIL,
fix the named claims and re-run the same agent; record the final PASS in the divergence
inventory.

## 5. Confirm the gates

Walk `contracts/audit-pass-fail-contract.md` G1–G16. The path-portability gate:

```bash
uv run pytest tests/integration/test_path_portability_audit.py
git diff --name-only   # G13: only *.md and .claude/rules/ touched; no src/, tests/, pyproject
```

## 6. Per-feature maintenance (FR-020, SC-E)

At the start of every new `specs/NNN-*` feature, walk the 7-item checklist in the
top-level `CLAUDE.md` maintenance section (authored from research §J). It is designed to
take under 2 minutes.
