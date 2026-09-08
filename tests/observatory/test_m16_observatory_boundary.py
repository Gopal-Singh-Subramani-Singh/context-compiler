from __future__ import annotations

from pathlib import Path

import pytest

from contextc.errors import OptionalDependencyError
from contextc.observatory.launcher import launch_observatory


def test_observatory_missing_extra_is_actionable(monkeypatch) -> None:
    monkeypatch.setattr(
        "contextc.optional.optional_dependency_available",
        lambda module: False,
    )
    with pytest.raises(OptionalDependencyError, match="'ui' extra"):
        launch_observatory()


def test_streamlit_page_is_presentation_only() -> None:
    path = Path(__file__).parents[2] / "contextc" / "observatory" / "streamlit_app.py"
    text = path.read_text(encoding="utf-8")
    assert "contextc.release_demos.service" in text
    assert "contextc.application.compile" not in text
    assert "contextc.live_mcp" not in text
    assert "subprocess" not in text
