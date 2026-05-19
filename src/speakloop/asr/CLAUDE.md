# asr

Speech-to-text engine wrapper.

**Public surface**: `interface.ASREngine` (Protocol), `interface.Transcript`,
`interface.WordTiming`, `interface.ASREngineError`.

**Engine wrapper**: `parakeet_engine.ParakeetEngine` — the ONLY file in the repo
allowed to `import parakeet_mlx` (Constitution Principle V).

RNN-T/TDT architecture does NOT hallucinate on silence (research_asr.md).
