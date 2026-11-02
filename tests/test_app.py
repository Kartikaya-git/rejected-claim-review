from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest


def test_screen_opens_with_its_notice():
    app = AppTest.from_file(str(Path(__file__).parents[1] / "app.py"), default_timeout=20).run()

    assert not app.exception
    assert "not advice" in app.warning[0].value
