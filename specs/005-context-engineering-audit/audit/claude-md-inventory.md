# CLAUDE.md inventory (T005, refreshed in T041) — SC-A

Command: `find . -name CLAUDE.md -not -path '*/.git/*' | sort | xargs wc -l`

## Baseline (before rewrite)

| File | Lines | Ceiling | OK? |
|------|-------|---------|-----|
| `CLAUDE.md` (root) | 73 | 200 | ✅ |
| `asr/CLAUDE.md` | 46 | 100 | ✅ |
| `feedback/CLAUDE.md` | 35 | 100 | ✅ |
| `debrief/CLAUDE.md` | 33 | 100 | ✅ |
| `cli/CLAUDE.md` | 18 | 100 | ✅ |
| `config/CLAUDE.md` | 16 | 100 | ✅ |
| `content/CLAUDE.md` | 16 | 100 | ✅ |
| `installer/CLAUDE.md` | 13 | 100 | ✅ |
| `metrics/CLAUDE.md` | 11 | 100 | ✅ thin |
| `trends/CLAUDE.md` | 11 | 100 | ✅ thin |
| `tts/CLAUDE.md` | 11 | 100 | ✅ thin |
| `llm/CLAUDE.md` | 10 | 100 | ✅ thin |
| `audio/CLAUDE.md` | 9 | 100 | ✅ thin |
| `sessions/CLAUDE.md` | 9 | 100 | ✅ thin |

All under ceiling; thin files (9–11 lines) lack Principle IV's six fields and are expanded.

## Post-rewrite line counts are re-measured in T041 / G1; see gate-checklist.md.
