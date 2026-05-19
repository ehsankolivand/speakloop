# speakloop

Local English interview-practice CLI for senior engineers. Runs Kokoro TTS, Parakeet
ASR, and Qwen3.5-9B LLM **fully offline** on Apple Silicon, walks you through a 4/3/2
spoken-attempt loop on questions of your choice, and writes an Obsidian-compatible
Markdown report under `data/sessions/`.

```bash
git clone <repo-url> speakloop
cd speakloop
uv sync
uv run speakloop --help
```

See **[specs/001-v1-product-spec/quickstart.md](specs/001-v1-product-spec/quickstart.md)**
for the full clone → finished-session walkthrough, including the per-phase
install path (Phase A → B → C, each shipping a complete working system per
Constitution Principle XII).

## Project shape

Twelve fine-grained modules under `src/speakloop/`, one responsibility each,
each with its own `CLAUDE.md`. Engine-specific imports live in exactly one file
per engine (`tts/kokoro_engine.py`, `asr/parakeet_engine.py`, `llm/qwen_engine.py`).

The full module map is in the top-level [CLAUDE.md](CLAUDE.md). The governing
principles are in [`.specify/memory/constitution.md`](.specify/memory/constitution.md) (v1.0.0).

## License

MIT. See [LICENSE](LICENSE).
