"""Generate or verify deterministic integrity metadata for M16 release demos."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEMOS = ROOT / "contextc" / "resources" / "release_demos"
REGISTRY = DEMOS / "registry.json"


def ignored_resource(path: Path, *, demos_root: Path = DEMOS) -> bool:
    """Return true for generated files that are never release-demo resources."""

    relative = path.relative_to(demos_root)
    return (
        "__pycache__" in relative.parts
        or path.suffix in {".pyc", ".pyo"}
        or path.name == ".DS_Store"
    )


def digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def render_registry(demos_root: Path = DEMOS) -> str:
    entries: list[dict[str, object]] = []
    for demo_dir in sorted(demos_root.iterdir(), key=lambda item: item.name):
        if not demo_dir.is_dir() or not (demo_dir / "demo.json").is_file():
            continue
        metadata = json.loads((demo_dir / "demo.json").read_text(encoding="utf-8"))
        files = []
        for path in sorted(demo_dir.rglob("*")):
            if not path.is_file() or ignored_resource(path, demos_root=demos_root):
                continue
            relative = path.relative_to(demo_dir).as_posix()
            files.append(
                {
                    "path": relative,
                    "sha256": digest(path),
                    "bytes": path.stat().st_size,
                }
            )
        entries.append({**metadata, "files": files})
    registry = {
        "schema_version": {"major": 1, "minor": 0},
        "registry_id": "contextc-release-demos",
        "profile_version": "1.0.0",
        "demos": entries,
    }
    return json.dumps(registry, indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    rendered = render_registry()
    if args.check:
        current = REGISTRY.read_text(encoding="utf-8") if REGISTRY.is_file() else ""
        if current != rendered:
            print("release-demo registry is stale; run tools/build_release_registry.py")
            return 1
        print("release-demo registry is current")
        return 0
    REGISTRY.write_text(rendered, encoding="utf-8")
    print(REGISTRY)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
