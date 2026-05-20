# config

Single source of truth for filesystem paths and runtime constants.

**Public surface**:

- `paths.models_dir()` → `~/.speakloop/models/` (or `--models-dir` override).
- `paths.sessions_dir()` → `data/sessions/` (CWD-relative; overridable).
- `paths.default_qa_file()` → `content/questions.yaml` (CWD-relative in-repo default).
- `paths.qa_file_path()` → the personal-override location (`--qa-file` / SPEAKLOOP_QA_FILE
  / `~/.speakloop/qa.yaml`). Override location only.
- `paths.resolve_qa_file()` → active question file by precedence (`--qa-file` →
  `~/.speakloop/qa.yaml` if it exists → `content/questions.yaml` if it exists → `None`).
- `paths.tts_cache_dir()` → `~/.speakloop/cache/tts/`.

**Forbidden**: importing engine packages, doing I/O beyond `mkdir -p`.
