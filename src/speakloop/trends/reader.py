"""Read session reports under sessions_dir via python-frontmatter."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import frontmatter


@dataclass(frozen=True)
class Report:
    path: Path
    schema_version: int
    session_id: str
    started_at: datetime | None
    question_id: str
    attempts: list[dict]
    grammar_patterns: list[dict]
    generated_by_phase: str


@dataclass(frozen=True)
class ReadResult:
    reports: list[Report]
    skipped: list[tuple[Path, str]]  # (path, reason)


def _parse_started_at(raw) -> datetime | None:
    if isinstance(raw, datetime):
        return raw
    if isinstance(raw, str):
        try:
            return datetime.fromisoformat(raw)
        except ValueError:
            return None
    return None


def _looks_like_speakloop(fm: dict) -> bool:
    return "schema_version" in fm and "attempts" in fm and "generated_by_phase" in fm


def read_reports(
    sessions_dir: Path,
    *,
    since: date | None = None,
) -> ReadResult:
    """Read every Markdown file under `sessions_dir`. Skip non-speakloop / malformed."""
    sessions_dir = Path(sessions_dir)
    reports: list[Report] = []
    skipped: list[tuple[Path, str]] = []
    if not sessions_dir.exists():
        return ReadResult(reports=[], skipped=[])

    for path in sorted(sessions_dir.glob("*.md")):
        try:
            doc = frontmatter.load(str(path))
        except Exception as e:
            skipped.append((path, f"frontmatter parse error: {e}"))
            continue
        fm = doc.metadata
        if not isinstance(fm, dict) or not _looks_like_speakloop(fm):
            # not a speakloop report — silently skip
            continue
        started_at = _parse_started_at(fm.get("started_at"))
        if since is not None:
            if started_at is None or started_at.date() < since:
                continue
        try:
            reports.append(
                Report(
                    path=path,
                    schema_version=int(fm["schema_version"]),
                    session_id=str(fm.get("session_id", path.stem)),
                    started_at=started_at,
                    question_id=str(fm.get("question_id", "")),
                    attempts=list(fm.get("attempts") or []),
                    grammar_patterns=list(fm.get("grammar_patterns") or []),
                    generated_by_phase=str(fm.get("generated_by_phase", "")),
                )
            )
        except Exception as e:
            skipped.append((path, f"schema error: {e}"))
    return ReadResult(reports=reports, skipped=skipped)


def iter_reports(result: ReadResult) -> Iterator[Report]:
    yield from result.reports
