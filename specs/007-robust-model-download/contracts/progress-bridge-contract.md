# Contract: aria2 → Rich Progress Bridge

**Feature**: 007-robust-model-download
**Module**: `src/speakloop/installer/aria.py` (new)
**Test file**: `tests/unit/installer/test_aria.py`

This contract specifies how `aria2c`'s subprocess output is parsed and
projected into the existing Rich console, so that spec FR-020 ("live
per-model progress bar + concise retry status line that resumes from prior
offset, never resets to zero") is testably satisfied.

## 1. Subprocess shape

```python
proc = subprocess.Popen(
    cmd,                                  # from downloader-cli-contract §5
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,             # merge stderr into stdout
    text=True,
    bufsize=1,                            # line-buffered
)
```

Reading loop:

```python
for line in proc.stdout:
    snapshot = _parse_progress(line)      # may be None
    if snapshot is not None:
        on_progress(snapshot)             # caller-provided callback
```

When `proc.wait()` returns:
- exit code → classify per [`data-model.md`](../data-model.md) → `Aria2Outcome`
- return `(outcome, optional_error)` to the caller.

## 2. Progress-line grammar

aria2 prints status lines that look like:

```text
[#XXXXXX 1.5GiB/8.0GiB(18%) CN:16 SD:16 DL:6.4MiB ETA:1m45s]
```

The parser MUST tolerate variants seen in the field:

- Missing `ETA:` segment (during the first few seconds of a download).
- Missing `SD:` (single-stream files).
- Trailing whitespace.
- ANSI cursor codes prefixing the bracket (mostly absent in piped mode, but
  defensively stripped).
- Lines that are NOT progress lines (status banners, error messages,
  retry notices) — `_parse_progress(...)` returns `None` for these.

Reference regex (illustrative; pin to test fixtures in
`tests/unit/installer/test_aria.py`):

```python
_PROGRESS_RE = re.compile(
    r"\["
    r"#[0-9a-fA-F]+\s+"
    r"(?P<received>[\d.]+[KMGT]?i?B)"
    r"/"
    r"(?P<total>[\d.]+[KMGT]?i?B)"
    r"\(\s*(?P<percent>\d+)%\)\s+"
    r"CN:(?P<conn>\d+)\s+"
    r"(?:SD:\d+\s+)?"
    r"DL:(?P<rate>[\d.]+[KMGT]?i?B)"
    r"(?:\s+ETA:(?P<eta>[\dhms]+))?"
    r"\]"
)
```

`_parse_progress(line)` returns:

```python
Aria2Progress(
    bytes_received=_parse_size(m.group("received")),
    bytes_total=_parse_size(m.group("total")),
    download_rate_bps=_parse_size(m.group("rate")),
    eta_seconds=_parse_eta(m.group("eta")),  # None if missing
    shard_filename=current_shard,            # injected by caller; aria2's
                                             # plain-mode line does not
                                             # include the filename
)
```

The size parser MUST accept SI and IEC suffixes: `B`, `KB`/`KiB`,
`MB`/`MiB`, `GB`/`GiB`, `TB`/`TiB`.

## 3. Rich Progress wiring

The downloader holds ONE `rich.progress.Progress` instance for the whole
install run. For each shard, a task is added:

```python
task_id = progress.add_task(
    description=f"{model.name} / {shard}",
    total=expected_shard_bytes_or_None,
)
```

- `total` is initially `None` if not known until the first parsed line;
  Rich treats it as "indeterminate" until set.
- On the first `Aria2Progress` snapshot, the task's `total` is updated:
  `progress.update(task_id, total=snapshot.bytes_total)`.
- On each subsequent snapshot:
  `progress.update(task_id, completed=snapshot.bytes_received)`.

When the outer Python retry loop respawns aria2 (transient failure):
- The task is NOT removed.
- The task's `completed` value carries forward — when the new aria2 process
  starts emitting progress lines from a resumed byte offset, those offsets
  ARE the prior offset (because of `--continue=true`), so `completed`
  appears to "freeze and then keep growing" — visually matching spec
  FR-020's "resume the progress display from the prior byte offset…it MUST
  NOT reset to zero."
- BETWEEN process exit and the next process emitting its first progress
  line, the downloader writes one transient line above the progress
  block: `[yellow]Connection lost — retrying in 10s…[/yellow]` (per FR-020
  and §5 of the downloader CLI contract). Rich's `Progress` supports
  `progress.console.print(...)` interleaved with the live display.

## 4. Hard-error surface

When the exit-code classification yields `HARD_FAILURE`:
- The progress task for the offending shard is left in its last state (NOT
  marked as complete).
- The downloader prints one red line: `[red bold]Download failed:[/red bold] {message}`.
- The typed exception is raised so `ensure_models(...)` can propagate it.

When classification yields `TRANSIENT_FAILURE`:
- The downloader prints one yellow line (see above) and sleeps the
  Python-side retry wait.
- No exception is raised; the outer loop respawns aria2.

## 5. Test fixtures

`tests/unit/installer/fixtures/aria2_output/` (new) MUST contain a set of
captured aria2 stdout transcripts, one per scenario:

| Fixture | Scenario covered |
|---|---|
| `normal_run.txt` | Happy-path download from 0 % to 100 %. |
| `resume_run.txt` | aria2 starting at non-zero offset because partial file exists. |
| `transient_drop.txt` | Mid-download "errorCode=1" then continues. |
| `hard_auth.txt` | HTTP 401 → exit code 22. |
| `hard_404.txt` | HTTP 404 → exit code 22. |
| `disk_full.txt` | exit code 9, no progress lines. |
| `missing_eta.txt` | First few status lines without `ETA:`. |

`test_aria.py` MUST exercise each fixture against `_parse_progress(...)`
and the classifier and assert the resulting `Aria2Progress` /
`Aria2Outcome`.

## 6. Non-progress lines (passthrough policy)

Lines that are NOT progress lines and NOT classified errors:
- aria2 banners (`aria2 ver. 1.36.0 - <license>`),
- destination-path log lines (`Saving the result to model.safetensors`),
- summary lines at exit (`Download Results:`, `gid|stat|...`),

are silently dropped from the user-facing display. They are NOT logged
to the installer console. (Rationale: the Rich progress bar IS the
user-facing display; piping aria2's verbose banner into it would create
visual noise without information value.)

## 7. Live download smoke test

`tests/live_download_test.py` (new, marker `live_download`) is a single
opt-in test that:
1. Asserts `aria2c` is on PATH (skips if absent — same pattern as
   `live_asr_test.py`).
2. Downloads ONE small public artifact (e.g., `config.json` from a small
   public HF repo) via the real downloader.
3. Asserts the file is present and the byte count matches the HTTP
   `Content-Length`.

This test is EXCLUDED from the default suite (matches the existing
`live_asr` / `live_llm` pattern in `pyproject.toml`). It exists so a
maintainer touching this code can re-validate end-to-end with one
`pytest -m live_download`.
