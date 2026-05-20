# Contract: Question-file resolution

The CLI surface (the public interface this project exposes) for locating the active
question set. Governs `config/paths.py` and `cli/practice.py`.

## Functions (config/paths.py)

```python
def default_qa_file() -> Path:
    """Repo default question file: <cwd>/content/questions.yaml.

    Resolved cwd-relative, matching paths.sessions_dir()'s convention. Pure;
    does not check existence.
    """

def resolve_qa_file() -> Path | None:
    """Active question file by precedence, or None if none is found/readable.

    Order (first match wins):
      1. the --qa-file override set via set_qa_file_path(), if present.
      2. ~/.speakloop/qa.yaml, if it exists.
      3. default_qa_file() (content/questions.yaml), if it exists.
    Returns None when no candidate exists, so the caller can emit FR-006.
    """
```

- `set_qa_file_path(path)` / the existing `qa_file_path()` semantics for the **override
  home path** are preserved (FR-005). `qa_file_path()` continues to return
  `~/.speakloop/qa.yaml` (or the `--qa-file` value) — i.e. the override location.
- No function auto-creates any file (R2): the first-run copy is removed.

## CLI behavior (cli/practice.py)

- Replaces `_ensure_starter_qa` (which copied starter→home) with resolution via
  `paths.resolve_qa_file()`.
- On a resolved path → `content.load(path)` as today.
- On `None` → print one English message naming both the default
  (`content/questions.yaml`) and override (`~/.speakloop/qa.yaml`) locations and
  `raise typer.Exit(1)` (FR-006). No empty session.
- `--qa-file PATH` flag unchanged (help text updated to mention the new default).

## Precedence table

| `--qa-file` | `~/.speakloop/qa.yaml` exists | `content/questions.yaml` exists | Active source |
|:---:|:---:|:---:|---|
| set | — | — | the `--qa-file` path |
| unset | yes | — | `~/.speakloop/qa.yaml` (override) |
| unset | no | yes | `content/questions.yaml` (default) |
| unset | no | no | error (FR-006), exit 1 |

## Invariants

- Loader signature `content.loader.load(path) -> QAFile` is unchanged (FR-005).
- Override wins over default when both exist (edge case in spec).
- No network, no telemetry (Principle II); pure filesystem resolution.
