"""Bundled drill-bank loader + bounded follow-on routing (016).

Reads the packaged ``drill_bank.yaml`` (via ``Path(__file__).parent``, the same way
``feedback/cloud_prompt.py`` reads its packaged default) — NO network, NO g2p/NLTK.
Pure data + bounded routing; imports no engine package.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

_BANK_PATH = Path(__file__).parent / "drill_bank.yaml"


@dataclass(frozen=True)
class Contrast:
    id: str
    expected: str
    competitors: list[str]
    tip: str


@dataclass(frozen=True)
class Drill:
    id: str
    contrast_id: str
    prompt: str
    canonical: list[str]
    targets: list[dict]  # [{"index": int, "word": str}, ...]
    is_base: bool = False
    # 017 P2: a short, readable ENGLISH respelling of the target word(s) — curated bundled
    # data (NOT derived at runtime), e.g. "WEE — round your lips for /w/". Shown with the
    # drill and, when the sound is flagged, alongside the focused per-sound teaching beat.
    say_like: str = ""


@dataclass(frozen=True)
class DrillBank:
    contrasts: dict[str, Contrast]
    drills: list[Drill] = field(default_factory=list)

    def base_drills(self) -> list[Drill]:
        return [d for d in self.drills if d.is_base]

    def contrast(self, contrast_id: str) -> Contrast | None:
        return self.contrasts.get(contrast_id)

    def next_drills(
        self, contrast_id: str, *, exclude_ids: set[str] | None = None, max: int = 2
    ) -> list[Drill]:
        """Up to ``max`` not-yet-seen drills for ``contrast_id`` (bounded, FR-024)."""
        exclude = exclude_ids or set()
        pool = [
            d
            for d in self.drills
            if d.contrast_id == contrast_id and d.id not in exclude
        ]
        return pool[: max if max > 0 else 0]

    def all_symbols(self) -> set[str]:
        """Every phoneme symbol referenced (canonical + expected + competitors)."""
        syms: set[str] = set()
        for c in self.contrasts.values():
            syms.add(c.expected)
            syms.update(c.competitors)
        for d in self.drills:
            syms.update(d.canonical)
        return syms


class DrillBankError(Exception):
    """Raised when the bundled drill bank is structurally invalid."""


def load_drill_bank(path: Path | None = None) -> DrillBank:
    """Load + structurally validate the bundled bank."""
    src = path or _BANK_PATH
    data = yaml.safe_load(src.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise DrillBankError(f"{src} is not a mapping")

    contrasts: dict[str, Contrast] = {}
    for c in data.get("contrasts") or []:
        cid = str(c["id"])
        contrasts[cid] = Contrast(
            id=cid,
            expected=str(c["expected"]),
            competitors=[str(x) for x in (c.get("competitors") or [])],
            tip=str(c.get("tip", "")),
        )

    drills: list[Drill] = []
    seen_ids: set[str] = set()
    for d in data.get("drills") or []:
        did = str(d["id"])
        if did in seen_ids:
            raise DrillBankError(f"duplicate drill id {did!r}")
        seen_ids.add(did)
        cid = str(d["contrast_id"])
        if cid not in contrasts:
            raise DrillBankError(f"drill {did!r} references unknown contrast {cid!r}")
        canonical = [str(x) for x in (d.get("canonical") or [])]
        targets = [
            {"index": int(t["index"]), "word": str(t.get("word", ""))}
            for t in (d.get("targets") or [])
        ]
        for t in targets:
            if not (0 <= t["index"] < len(canonical)):
                raise DrillBankError(
                    f"drill {did!r} target index {t['index']} out of range "
                    f"(canonical has {len(canonical)} phones)"
                )
        drills.append(
            Drill(
                id=did,
                contrast_id=cid,
                prompt=str(d.get("prompt", "")),
                canonical=canonical,
                targets=targets,
                is_base=bool(d.get("is_base", False)),
                say_like=str(d.get("say_like", "")),
            )
        )
    if not any(d.is_base for d in drills):
        raise DrillBankError("drill bank has no base drills")
    return DrillBank(contrasts=contrasts, drills=drills)
