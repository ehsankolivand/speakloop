"""T011 — Persian-L1 catalog loader (research.md §a, data-model §B).

The catalog must load into frozen dataclasses, expose every documented seed id,
carry a non-empty transfer reason + impact rank per entry, place the open-bucket
default rank below every catalog rank, and fail loudly on malformed YAML.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from speakloop.feedback import catalog

pytestmark = pytest.mark.unit

# The documented Persian-L1 seed categories (data-model §B.1, contract).
SEED_IDS = {
    "gerund-infinitive-confusion",
    "comparative-form",
    "plural-agreement",
    "article-omission-common",
    "preposition-substitution",
    "3sg-s-drop",
    "aux-drop",
    "possessor-order",
}


def test_catalog_loads_with_version_one():
    cat = catalog.get_catalog()
    assert cat.catalog_version == 1
    assert len(cat.entries) >= len(SEED_IDS)


def test_all_seed_ids_present():
    cat = catalog.get_catalog()
    ids = {e.id for e in cat.entries}
    assert SEED_IDS <= ids


def test_every_entry_has_transfer_reason_and_impact_rank():
    for e in catalog.get_catalog().entries:
        assert e.transfer_reason.strip(), f"{e.id} missing transfer_reason"
        assert isinstance(e.impact_rank, int)
        assert e.impact_rank >= 1
        # transfer_reason is whitespace-normalised on load (single spaces).
        assert "\n" not in e.transfer_reason


def test_lookup_by_id_and_label():
    cat = catalog.get_catalog()
    by_id = cat.get("gerund-infinitive-confusion")
    assert by_id is not None
    assert by_id.label == "gerund/infinitive confusion"
    # Label lookup is case-insensitive.
    by_label = cat.get("Gerund/Infinitive Confusion")
    assert by_label is by_id
    # Unknown / empty keys → None (open-bucket).
    assert cat.get("not-a-real-id") is None
    assert cat.get(None) is None
    assert cat.get("") is None


def test_open_bucket_rank_sorts_below_every_catalog_rank():
    cat = catalog.get_catalog()
    worst_catalog_rank = max(e.impact_rank for e in cat.entries)
    assert catalog.OPEN_BUCKET_IMPACT_RANK > worst_catalog_rank
    assert cat.open_bucket_impact_rank == catalog.OPEN_BUCKET_IMPACT_RANK


def test_examples_are_wrong_right_pairs():
    entry = catalog.get_catalog().get("gerund-infinitive-confusion")
    assert entry.examples  # at least one seed pair
    wrong, right = entry.examples[0]
    assert wrong and right and wrong != right


def test_entries_are_frozen():
    entry = catalog.get_catalog().entries[0]
    with pytest.raises((AttributeError, TypeError)):
        entry.impact_rank = 0  # type: ignore[misc]


def test_malformed_yaml_raises_at_load(tmp_path: Path):
    bad = tmp_path / "bad_catalog.yaml"
    bad.write_text("entries: [this is : : not valid yaml\n", encoding="utf-8")
    with pytest.raises(catalog.CatalogError):
        catalog._load(bad)


def test_missing_required_field_raises(tmp_path: Path):
    incomplete = tmp_path / "incomplete.yaml"
    incomplete.write_text(
        "catalog_version: 1\n"
        "entries:\n"
        "  - id: no-reason\n"
        "    label: missing the transfer reason\n"
        "    impact_rank: 2\n",
        encoding="utf-8",
    )
    with pytest.raises(catalog.CatalogError):
        catalog._load(incomplete)


def test_wrong_catalog_version_raises(tmp_path: Path):
    wrong = tmp_path / "v2.yaml"
    wrong.write_text("catalog_version: 2\nentries: []\n", encoding="utf-8")
    with pytest.raises(catalog.CatalogError):
        catalog._load(wrong)
