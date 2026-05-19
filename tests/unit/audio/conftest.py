"""Reset the process-global abort flag around each audio unit test.

`recorder.record` now polls `speakloop.sessions.abort.abort_event` so a
SIGINT in one test can't shorten an unrelated test's recording loop.
"""

from __future__ import annotations

import pytest

from speakloop.sessions import abort


@pytest.fixture(autouse=True)
def _reset_abort_event():
    abort.reset()
    yield
    abort.reset()
