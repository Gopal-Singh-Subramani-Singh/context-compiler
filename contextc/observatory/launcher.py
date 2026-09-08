"""Lazy Streamlit launcher; importing core Context Compiler never imports Streamlit."""

from __future__ import annotations

import sys
from pathlib import Path

from contextc.optional import require_optional


def launch_observatory(*, address: str = "127.0.0.1", port: int = 8501) -> int:
    """Launch the local, read-only Observatory on loopback by default."""

    require_optional(feature="Context Compiler Observatory", module="streamlit", extra="ui")
    from streamlit.web import cli as streamlit_cli

    app = Path(__file__).with_name("streamlit_app.py")
    original = list(sys.argv)
    try:
        sys.argv = [
            "streamlit",
            "run",
            str(app),
            "--server.address",
            address,
            "--server.port",
            str(port),
            "--server.headless",
            "true",
            "--browser.gatherUsageStats",
            "false",
        ]
        streamlit_cli.main()
    finally:
        sys.argv = original
    return 0
