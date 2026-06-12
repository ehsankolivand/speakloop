"""T009 (015) — loop_config.save_engine: persist the default feedback engine."""

from __future__ import annotations

import pytest
import yaml

from speakloop.config import loop_config, paths

pytestmark = pytest.mark.unit


def test_save_engine_round_trip():
    path = loop_config.save_engine("openrouter")
    assert path == paths.loop_config_path()
    assert loop_config.load().engine == "openrouter"


@pytest.mark.parametrize("engine", ["local", "openrouter", "claude"])
def test_save_engine_all_valid(engine):
    loop_config.save_engine(engine)
    assert loop_config.load().engine == engine


def test_save_engine_preserves_other_keys():
    path = paths.loop_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("daily_capacity: 9\nwarmup_enabled: false\n", encoding="utf-8")

    loop_config.save_engine("claude")

    cfg = loop_config.load()
    assert cfg.engine == "claude"
    assert cfg.daily_capacity == 9
    assert cfg.warmup_enabled is False
    # The written file still carries the untouched keys.
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert data["daily_capacity"] == 9
    assert data["engine"] == "claude"


def test_save_engine_rejects_unknown_value():
    with pytest.raises(ValueError):
        loop_config.save_engine("gpt")
    # Nothing persisted.
    assert loop_config.load().engine == "local"


def test_save_engine_tolerates_malformed_existing_file():
    path = paths.loop_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(": not valid yaml : [", encoding="utf-8")

    loop_config.save_engine("openrouter")
    assert loop_config.load().engine == "openrouter"
