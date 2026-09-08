"""Dependency-free reader for benchmark files encoded in the JSON subset of YAML."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

from contextc.decoding import require_mapping
from contextc.errors import SourceValidationError


def read_json_yaml(path: Path) -> Mapping[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SourceValidationError(f"invalid benchmark record {path}: {error}") from error
    return require_mapping(value, str(path))
