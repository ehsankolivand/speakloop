# Quickstart — verifying the 014 context overhaul

```bash
# 1. Every CLAUDE.md within budget (the new guard test)
uv run pytest tests/integration/test_context_file_budget.py -q

# 2. Full suite — pass count must match baseline 696 passed, 3 skipped, 2 deselected
#    (+1 for the new guard test, reported separately)
uv run pytest -q

# 3. Diff-scope guard — nothing outside context paths + the one guard test
git diff --name-only main...HEAD | grep -v -E \
  '(\.md$|^\.claude/|^specs/014-|^tests/integration/test_context_file_budget\.py$)' \
  && echo "SCOPE VIOLATION" || echo "scope OK"

# 4. Duplicate-rule spot check (each distinctive phrase → exactly one owner)
rg -l "schema_version" --glob 'CLAUDE.md' --glob '**/CLAUDE.md'

# 5. Memory loading — run /memory in an interactive session; expect root CLAUDE.md
#    + (when editing matching paths) .claude/rules/{testing,llm-calls}.md
```
