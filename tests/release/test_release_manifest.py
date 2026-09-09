from pathlib import Path


def test_manifest_excludes_historical_docs_from_sdist() -> None:
    manifest = Path(__file__).resolve().parents[2] / "MANIFEST.in"
    entries = manifest.read_text(encoding="utf-8")
    assert "prune docs/history" in entries
