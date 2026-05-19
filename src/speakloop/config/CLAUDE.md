# config

Single source of truth for filesystem paths and runtime constants.

**Public surface**:

- `paths.models_dir()` → `~/.speakloop/models/` (or `--models-dir` override).
- `paths.sessions_dir()` → `data/sessions/` (CWD-relative; overridable).
- `paths.qa_file_path()` → `~/.speakloop/qa.yaml`.
- `paths.tts_cache_dir()` → `~/.speakloop/cache/tts/`.

**Forbidden**: importing engine packages, doing I/O beyond `mkdir -p`.
