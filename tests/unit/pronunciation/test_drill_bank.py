"""T010 — the bundled drill bank loads, validates, and routes follow-ons (bounded)."""

from __future__ import annotations

import pytest

from speakloop.pronunciation import drill_bank

pytestmark = pytest.mark.unit


def test_bank_loads_and_is_structurally_valid():
    bank = drill_bank.load_drill_bank()
    assert bank.drills
    assert bank.base_drills(), "bank must offer at least one base drill"
    for d in bank.drills:
        assert d.contrast_id in bank.contrasts, f"{d.id} references unknown contrast"
        assert d.canonical, f"{d.id} has no canonical phones"
        for t in d.targets:
            assert 0 <= t["index"] < len(d.canonical)


def test_every_target_phone_matches_its_contrast_expected_or_is_intentional():
    bank = drill_bank.load_drill_bank()
    for d in bank.drills:
        c = bank.contrasts[d.contrast_id]
        for t in d.targets:
            phone = d.canonical[t["index"]]
            assert phone == c.expected, (
                f"{d.id}: target phone {phone!r} != contrast expected {c.expected!r}"
            )


def test_next_drills_is_bounded_and_excludes_seen():
    bank = drill_bank.load_drill_bank()
    cid = bank.base_drills()[0].contrast_id
    follow = bank.next_drills(cid, exclude_ids=set(), max=2)
    assert len(follow) <= 2
    assert all(d.contrast_id == cid for d in follow)
    if follow:
        seen = {follow[0].id}
        again = bank.next_drills(cid, exclude_ids=seen, max=2)
        assert all(d.id not in seen for d in again)


def test_load_rejects_unknown_contrast(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "version: 1\ncontrasts:\n  - id: a\n    expected: x\n    competitors: [y]\n"
        "drills:\n  - id: d1\n    contrast_id: NOPE\n    prompt: d\n    canonical: [x]\n"
        "    targets: [{index: 0, word: d}]\n    is_base: true\n",
        encoding="utf-8",
    )
    with pytest.raises(drill_bank.DrillBankError):
        drill_bank.load_drill_bank(bad)


def test_canonical_symbols_are_in_a_supplied_vocab():
    # When a vocab is available, every referenced symbol should exist in it. Uses the
    # real model vocab IF present on disk; otherwise skips (no network, no model needed).
    import json

    from speakloop.installer import manifest

    vocab_path = manifest.WAV2VEC2_PRONUNCIATION.local_path / "vocab.json"
    if not vocab_path.exists():
        pytest.skip("model vocab.json not present (drills not downloaded)")
    vocab = set(json.loads(vocab_path.read_text(encoding="utf-8")).keys())
    bank = drill_bank.load_drill_bank()
    missing = {s for s in bank.all_symbols() if s not in vocab}
    assert not missing, f"drill-bank symbols missing from model vocab: {missing}"
