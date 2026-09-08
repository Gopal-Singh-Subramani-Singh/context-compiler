"""Legacy single-target writer retained below the M4 artifact transaction boundary."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from contextc.targets.types import RenderedContext


def write_rendered_context(path: Path, rendered: RenderedContext) -> Path:
    """Atomically replace one text target only after successful complete lowering."""

    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=path.parent,
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            handle.write(rendered.rendered_bytes)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
        temporary_path = None
        return path
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
