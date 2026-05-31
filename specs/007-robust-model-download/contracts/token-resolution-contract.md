# Contract: Token Resolution

**Feature**: 007-robust-model-download
**Module**: `src/speakloop/installer/tokens.py` (new)
**Test file**: `tests/unit/installer/test_tokens.py`

This contract pins the resolution order for the optional HuggingFace token
and the no-leak invariants that surround it. Derived from spec FR-010 …
FR-013 and clarification Q2 → Option A.

## 1. Public function

```python
def resolve_token() -> ResolvedToken:
    """Return the active HF token, or anonymous if none is set.

    Resolution order, first non-empty wins:
      1. $HF_TOKEN
      2. ~/.cache/huggingface/token  (produced by `huggingface-cli login`)
      3. anonymous
    """
```

- Pure function. No side effects (no logging, no exceptions on missing
  inputs).
- Returns `ResolvedToken(value=None, source="anonymous")` when no token is
  found — never raises.
- Strips leading/trailing whitespace from the file contents before
  treating the result as a token (the HF CLI writes the token followed by
  a trailing newline).

## 2. Resolution rules (exhaustive)

| `$HF_TOKEN` set & non-empty? | File exists & non-empty after strip? | Result |
|---|---|---|
| ✅ | ✅ | `ResolvedToken(value=$HF_TOKEN, source="env")` (env wins) |
| ✅ | ❌ | `ResolvedToken(value=$HF_TOKEN, source="env")` |
| ❌ (unset or empty) | ✅ | `ResolvedToken(value=<file contents>, source="hf_cli_file")` |
| ❌ | ❌ | `ResolvedToken(value=None, source="anonymous")` |

- "non-empty" means: after `.strip()`, length > 0.
- A file present-but-empty is treated identically to an absent file
  (do not raise; the user may have removed their token deliberately).
- `os.path.expanduser("~/.cache/huggingface/token")` is the canonical path
  (`~/Library/Caches/...` is NOT used — the HF CLI uses POSIX `~/.cache`
  on macOS).

## 3. No-leak invariants

These are testable properties; the test file enforces each one.

| Invariant | Enforcement |
|---|---|
| The token value MUST NOT appear in `repr(ResolvedToken(...))`. | `__repr__` overridden to print only `source`, never `value`. |
| The token value MUST NOT appear in any installer log line (Rich console output). | Test scans the captured console output for the token value after a download run; asserts absence. |
| The token value MUST NOT appear in any raised exception's `args` or `__str__`. | Hard-error constructors redact the bearer header to the string `<redacted>` before storing the failing URL. |
| The token value MUST NOT be committed to the repo. | The path-portability audit (`test_path_portability_audit.py`) is extended to also scan committed files for any `hf_*` prefix outside doc files. Or: a new dedicated test in `tests/integration/`. |
| `$HF_TOKEN` MUST NOT be set as a process default by speakloop. | Test asserts `resolve_token()` does not write to `os.environ`. |

## 4. Use sites (the ONLY places `value` may flow to)

`ResolvedToken.value` may be inserted into exactly these strings, nowhere
else:

1. The `Authorization: Bearer <value>` header on a `curl` invocation
   (see [`downloader-cli-contract.md` §3](downloader-cli-contract.md#3-metadata-pass-curl)).
2. The `--header=Authorization: Bearer <value>` flag on an `aria2c`
   invocation (see [`downloader-cli-contract.md` §5](downloader-cli-contract.md#5-shard-pass-aria2c-one-shard-at-a-time-indefinite-outer-loop-retry)).
3. The `token=...` kwarg on `huggingface_hub.snapshot_download(...)` in
   the fallback path (see [`downloader-cli-contract.md` §6](downloader-cli-contract.md#6-fallback-path-aria2-missing)).

Any new use site is a contract change and requires a test update.

## 5. Diagnostic line (allowed, source only)

At download start, exactly ONE line MAY be printed to the installer console
to confirm the active credential source:

| `source` | Line printed |
|---|---|
| `"env"` | `Using HuggingFace token from $HF_TOKEN.` |
| `"hf_cli_file"` | `Using HuggingFace token from ~/.cache/huggingface/token.` |
| `"anonymous"` | (no line printed — anonymous is the default and needs no announcement) |

The token VALUE never appears in this line. The line exists so a user
debugging a 401 can verify which credential is in use without grepping
their environment.

## 6. Negative tests (must all pass)

1. With `HF_TOKEN=""` and no `~/.cache/huggingface/token`: result is
   `anonymous`, no exception.
2. With `HF_TOKEN="hf_abc"` and a non-empty file: env wins, file is not
   read.
3. With no `HF_TOKEN` and a file containing exactly `hf_xyz\n`: value is
   `hf_xyz` (newline stripped), source is `hf_cli_file`.
4. With no `HF_TOKEN` and a file containing only whitespace: result is
   `anonymous`.
5. `repr(resolve_token())` for any non-anonymous case does NOT contain the
   raw token characters.
