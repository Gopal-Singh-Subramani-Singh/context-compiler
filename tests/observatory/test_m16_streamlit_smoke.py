from __future__ import annotations

from pathlib import Path

import pytest

streamlit_testing = pytest.importorskip("streamlit.testing.v1")


def test_streamlit_landing_loads_all_four_release_demo_cards() -> None:
    app_path = Path(__file__).parents[2] / "contextc" / "observatory" / "streamlit_app.py"
    app_test = streamlit_testing.AppTest.from_file(str(app_path)).run(timeout=60)

    assert not app_test.exception
    assert app_test.title[0].value == "Context Compiler Observatory"
    subheaders = {item.value for item in app_test.subheader}
    assert {
        "Repository bug: empty natural_list",
        "Incident response: checkout latency",
        "Incremental rebuild: checkout_total",
        "Capability composition: sensitive to external",
    }.issubset(subheaders)
