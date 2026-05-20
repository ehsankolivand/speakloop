"""Persian-L1 error catalog loader (002-post-session-debrief, research.md §a).

Loads ``persian_l1_catalog.yaml`` ONCE at import into frozen dataclasses. The
catalog is the source of accurate labels, learner-facing transfer reasons (the
"Because:" line), and the deterministic impact ranking (FR-001..FR-005). A
malformed catalog fails loudly **at import**, never mid-session.

Open-bucket rule: patterns the analyzer surfaces that match no catalog
``id``/``label`` are admitted with :data:`OPEN_BUCKET_IMPACT_RANK`, which is
fixed BELOW every catalog entry (a larger number = lower impact), so they always
sort last among findings (FR-002, research.md §b).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

CATALOG_PATH = Path(__file__).parent / "persian_l1_catalog.yaml"

# Fixed impact rank for open-bucket (non-catalog) patterns. Larger == lower
# impact; this value is asserted at load to exceed every catalog rank so
# open-bucket findings always sort last (FR-002). It is intentionally a fixed
# constant (not catalog-derived) so the open-bucket weight is stable and
# explainable across catalog edits.
OPEN_BUCKET_IMPACT_RANK = 99


class CatalogError(Exception):
    """Raised at import when the catalog file is missing or malformed."""


@dataclass(frozen=True)
class CatalogEntry:
    """One Persian-L1 error category (data-model §B.1)."""

    id: str
    label: str
    transfer_reason: str
    impact_rank: int
    detection_hints: tuple[str, ...] = ()
    examples: tuple[tuple[str, str], ...] = ()  # (wrong, right) pairs
    methodology_ref: str = ""


@dataclass(frozen=True)
class Catalog:
    """The loaded catalog with id/label lookup (data-model §B.2)."""

    catalog_version: int
    entries: tuple[CatalogEntry, ...]
    _by_id: dict[str, CatalogEntry] = field(default_factory=dict, repr=False)
    _by_label: dict[str, CatalogEntry] = field(default_factory=dict, repr=False)

    def get(self, key: str | None) -> CatalogEntry | None:
        """Look up an entry by exact ``id`` or (case-insensitive) ``label``.

        Returns ``None`` for an open-bucket / unknown key.
        """
        if not key:
            return None
        return self._by_id.get(key) or self._by_label.get(key.strip().lower())

    @property
    def open_bucket_impact_rank(self) -> int:
        return OPEN_BUCKET_IMPACT_RANK


def _coerce_examples(raw) -> tuple[tuple[str, str], ...]:
    out: list[tuple[str, str]] = []
    for ex in raw or []:
        if isinstance(ex, dict) and "wrong" in ex and "right" in ex:
            out.append((str(ex["wrong"]).strip(), str(ex["right"]).strip()))
    return tuple(out)


def _entry_from_dict(d: dict) -> CatalogEntry:
    required = ("id", "label", "transfer_reason", "impact_rank")
    missing = [k for k in required if not d.get(k)]
    if missing:
        raise CatalogError(
            f"catalog entry {d.get('id', '?')!r} is missing required field(s): "
            f"{', '.join(missing)}."
        )
    try:
        impact_rank = int(d["impact_rank"])
    except (TypeError, ValueError) as e:
        raise CatalogError(f"catalog entry {d['id']!r}: impact_rank must be an int.") from e
    return CatalogEntry(
        id=str(d["id"]).strip(),
        label=str(d["label"]).strip(),
        transfer_reason=" ".join(str(d["transfer_reason"]).split()),
        impact_rank=impact_rank,
        detection_hints=tuple(str(h).strip() for h in (d.get("detection_hints") or [])),
        examples=_coerce_examples(d.get("examples")),
        methodology_ref=str(d.get("methodology_ref") or "").strip(),
    )


def _load(path: Path = CATALOG_PATH) -> Catalog:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:  # missing/unreadable → fail loudly at import
        raise CatalogError(f"Persian-L1 catalog not found or unreadable: {path}: {e}") from e
    try:
        doc = yaml.safe_load(text)
    except yaml.YAMLError as e:
        line = getattr(getattr(e, "problem_mark", None), "line", None)
        where = f"{path}:{line + 1}" if line is not None else str(path)
        raise CatalogError(f"{where}: catalog YAML parse error: {e}") from e

    if not isinstance(doc, dict):
        raise CatalogError(f"{path}: catalog root must be a mapping.")
    if doc.get("catalog_version") != 1:
        raise CatalogError(
            f"{path}: unsupported catalog_version {doc.get('catalog_version')!r}; expected 1."
        )
    raw_entries = doc.get("entries")
    if not isinstance(raw_entries, list) or not raw_entries:
        raise CatalogError(f"{path}: 'entries' must be a non-empty list.")

    entries = tuple(_entry_from_dict(e) for e in raw_entries)
    by_id: dict[str, CatalogEntry] = {}
    by_label: dict[str, CatalogEntry] = {}
    for e in entries:
        if e.id in by_id:
            raise CatalogError(f"{path}: duplicate catalog id {e.id!r}.")
        by_id[e.id] = e
        by_label[e.label.strip().lower()] = e

    max_rank = max(e.impact_rank for e in entries)
    if OPEN_BUCKET_IMPACT_RANK <= max_rank:
        raise CatalogError(
            f"OPEN_BUCKET_IMPACT_RANK ({OPEN_BUCKET_IMPACT_RANK}) must exceed every "
            f"catalog impact_rank (max {max_rank}) so open-bucket patterns sort last."
        )
    return Catalog(
        catalog_version=int(doc["catalog_version"]),
        entries=entries,
        _by_id=by_id,
        _by_label=by_label,
    )


# Loaded once at import; a malformed catalog raises here, not mid-session.
CATALOG: Catalog = _load()


def get_catalog() -> Catalog:
    """Return the process-wide loaded catalog."""
    return CATALOG
