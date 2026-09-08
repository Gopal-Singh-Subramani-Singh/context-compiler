"""Compare two wheel/sdist archives without overclaiming byte reproducibility."""

from __future__ import annotations

import argparse
import hashlib
import json
import tarfile
import zipfile
from collections.abc import Mapping
from pathlib import Path


def _sha(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _members(path: Path) -> Mapping[str, str]:
    values: dict[str, str] = {}
    if path.suffix in {".whl", ".zip"}:
        with zipfile.ZipFile(path) as archive:
            for info in archive.infolist():
                if not info.is_dir():
                    values[info.filename] = _sha(archive.read(info))
        return values
    if path.name.endswith(".tar.gz"):
        with tarfile.open(path, "r:gz") as archive:
            for member in archive.getmembers():
                if not member.isfile():
                    continue
                handle = archive.extractfile(member)
                if handle is not None:
                    values[member.name] = _sha(handle.read())
        return values
    raise ValueError(f"unsupported distribution type: {path}")


def compare(left: Path, right: Path) -> dict[str, object]:
    left_bytes = left.read_bytes()
    right_bytes = right.read_bytes()
    left_members = _members(left)
    right_members = _members(right)
    left_names = set(left_members)
    right_names = set(right_members)
    changed = tuple(
        sorted(
            name for name in left_names & right_names if left_members[name] != right_members[name]
        )
    )
    return {
        "left": str(left),
        "right": str(right),
        "left_sha256": _sha(left_bytes),
        "right_sha256": _sha(right_bytes),
        "byte_identical": left_bytes == right_bytes,
        "member_lists_identical": left_names == right_names,
        "content_identities_identical": left_members == right_members,
        "left_only_members": tuple(sorted(left_names - right_names)),
        "right_only_members": tuple(sorted(right_names - left_names)),
        "changed_member_contents": changed,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("left", type=Path)
    parser.add_argument("right", type=Path)
    args = parser.parse_args()
    result = compare(args.left, args.right)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
