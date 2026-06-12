"""Calibrated drill-feedback wording (016, FR-009).

Turns the drill-block result dict into Markdown for the report's Pronunciation
section, and shorter lines for the live terminal. Calibration rule: LEAD WITH
DETECTION ("this sound was off"); present any phone DIAGNOSIS as a hedged
SUGGESTION, never a verdict. Pure formatter — no engine import.
"""

from __future__ import annotations

_HEADER = "## Pronunciation drills"
_DISCLAIMER = (
    "_Read-aloud practice. Detection (a sound was off) is reliable; any specific "
    '"heard as …" guess is a suggestion, not a verdict._'
)


def _flag_line(flag: dict) -> str:
    """One detection-led line; diagnosis only when confident, always hedged."""
    expected = str(flag.get("expected", "")).strip()
    word = str(flag.get("word", "")).strip()
    where = f" in *{word}*" if word else ""
    line = f"The **{expected}** sound{where} sounded off."
    if flag.get("confident_diagnosis") and flag.get("competitor"):
        comp = str(flag["competitor"]).strip()
        line += f" _(suggestion: it may have come out closer to **{comp}**)_"
    return line


def render_drills_section(drills: dict | None) -> str | None:
    """Markdown for the report (data-model §5). None when there are no items."""
    if not drills or not drills.get("items"):
        return None
    lines = [_HEADER, "", _DISCLAIMER, ""]
    note = str(drills.get("engine_note", "")).strip()
    if note:
        lines += [f"_{note}_", ""]
    for it in drills["items"]:
        prompt = str(it.get("text") or it.get("prompt") or "").strip()
        tag = " *(follow-up)*" if it.get("is_follow_on") else ""
        status = it.get("status")
        if status == "not_captured":
            lines.append(f"- **{prompt}**{tag} — _not captured (read right after the prompt)_")
            continue
        if status == "error":
            lines.append(f"- **{prompt}**{tag} — _could not score this one_")
            continue
        flags = it.get("flags") or []
        if not flags:
            lines.append(f"- **{prompt}**{tag} — clear ✓")
            continue
        lines.append(f"- **{prompt}**{tag}")
        for fl in flags:
            lines.append(f"  - {_flag_line(fl)}")
            tip = str(fl.get("tip", "")).strip()
            if tip:
                lines.append(f"    - Tip: {tip}")
    return "\n".join(lines)


def live_flag_summary(flags: list[dict]) -> str:
    """A short one/two-line summary for the terminal right after a drill."""
    if not flags:
        return "clear ✓"
    return "; ".join(_flag_line(fl).rstrip(".") for fl in flags)
