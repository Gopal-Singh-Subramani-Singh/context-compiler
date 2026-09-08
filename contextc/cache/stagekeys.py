"""Stage-specific semantic cache-key construction."""

from __future__ import annotations

from contextc.cache.keys import ComputationKey
from contextc.hashing import semantic_hash
from contextc.pass_versions import pass_version


def stage_key(
    stage: str, semantic_inputs: object, *, namespace: str = "contextc"
) -> ComputationKey:
    identity = semantic_hash(
        {
            "stage": stage,
            "pass_version": pass_version(stage),
            "inputs": semantic_inputs,
        }
    )
    return ComputationKey(namespace=namespace, stage=stage, semantic_input_identity=identity)
