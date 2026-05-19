"""Contract test for the Q&A YAML schema example."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.contract

CONTRACT_PATH = (
    Path(__file__).parents[2]
    / "specs"
    / "001-v1-product-spec"
    / "contracts"
    / "content-schema.yaml"
)


def test_content_schema_example_is_valid_yaml():
    with open(CONTRACT_PATH) as f:
        doc = yaml.safe_load(f)
    assert doc["schema_version"] == 1
    assert isinstance(doc["questions"], list)
    assert len(doc["questions"]) >= 1
    for q in doc["questions"]:
        assert isinstance(q["id"], str)
        assert q["id"]
        assert isinstance(q["question"], str)
        assert q["question"].strip()
        assert isinstance(q["ideal_answer"], str)
        assert q["ideal_answer"].strip()
