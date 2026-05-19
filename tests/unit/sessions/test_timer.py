"""T059 — timer budgets + early exit."""

from __future__ import annotations

import threading
import time

import pytest

from speakloop.sessions import timer

pytestmark = pytest.mark.unit


def test_budgets_are_4_3_2_minutes():
    assert timer.time_budget_for(1) == 240
    assert timer.time_budget_for(2) == 180
    assert timer.time_budget_for(3) == 120


def test_invalid_ordinal_raises():
    with pytest.raises(ValueError):
        timer.time_budget_for(0)
    with pytest.raises(ValueError):
        timer.time_budget_for(4)


def test_early_exit_interrupts():
    event = threading.Event()

    def stopper():
        time.sleep(0.2)
        event.set()

    t = threading.Thread(target=stopper, daemon=True)
    t.start()
    elapsed = timer.run(budget_seconds=10, early_exit_event=event)
    assert elapsed < 1.0


def test_budget_elapsed_is_returned():
    elapsed = timer.run(budget_seconds=0.3)
    assert 0.2 < elapsed < 0.6
