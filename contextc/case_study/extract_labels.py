"""Review aid that extracts Git evidence but never approves or writes labels."""

from __future__ import annotations

from pathlib import Path

from contextc.hashing import semantic_hash

from .loader import load_historical_labels, load_public_case_task
from .repository import HistoricalRepository


def extract_label_candidates(
    task_directory: Path, repository: HistoricalRepository | None = None
) -> dict[str, object]:
    """Return immutable historical evidence with an explicit approval requirement."""

    source = repository or HistoricalRepository()
    public = load_public_case_task(task_directory)
    task = load_historical_labels(task_directory, repository_id=public.repository_id)
    patch = source.patch(public.pre_fix_revision, task.fix_revision)
    return {
        "task_id": public.task_id,
        "pre_fix_revision": public.pre_fix_revision,
        "fix_revision": task.fix_revision,
        "changed_files": source.changed_files(public.pre_fix_revision, task.fix_revision),
        "patch_identity": semantic_hash({"patch": patch}),
        "patch": patch,
        "approval_required": True,
        "writes_ground_truth": False,
    }
