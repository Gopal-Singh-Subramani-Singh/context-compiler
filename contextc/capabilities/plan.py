"""Static proposed-call plan loading and canonicalization."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

from contextc.capabilities.models import (
    CAPABILITY_PLAN_SCHEMA,
    BindingKind,
    CapabilityPlan,
    InputBinding,
    PlanCall,
)
from contextc.schema import SchemaVersion


def _parse_schema(value: object) -> tuple[SchemaVersion, str | None]:
    if value is None:
        return CAPABILITY_PLAN_SCHEMA, "schema_version is required"
    if not isinstance(value, Mapping):
        return CAPABILITY_PLAN_SCHEMA, "schema_version must be an object"
    try:
        parsed = SchemaVersion.from_dict(value)
    except Exception as error:  # normalized into CTX442 by validation
        return CAPABILITY_PLAN_SCHEMA, str(error)
    if parsed != CAPABILITY_PLAN_SCHEMA:
        return parsed, (
            f"unsupported capability plan schema {parsed.major}.{parsed.minor}; "
            f"expected {CAPABILITY_PLAN_SCHEMA.major}.{CAPABILITY_PLAN_SCHEMA.minor}"
        )
    return parsed, None


def _binding(input_name: str, raw: object) -> InputBinding:
    if isinstance(raw, str):
        if raw.startswith("resource:"):
            return InputBinding(
                input_name=input_name,
                kind=BindingKind.RESOURCE,
                resource_id=raw.removeprefix("resource:"),
            )
        if raw.startswith("call:"):
            value = raw.removeprefix("call:")
            call_id, _, output_name = value.partition(".")
            return InputBinding(
                input_name=input_name,
                kind=BindingKind.CALL_OUTPUT,
                call_id=call_id,
                output_name=output_name or "output",
            )
        raise ValueError(f"binding {input_name!r} must start with resource: or call:")
    if not isinstance(raw, Mapping):
        raise ValueError(f"binding {input_name!r} must be a string or object")
    if isinstance(raw.get("resource_id"), str):
        return InputBinding(
            input_name=input_name,
            kind=BindingKind.RESOURCE,
            resource_id=str(raw["resource_id"]),
        )
    if isinstance(raw.get("call_id"), str):
        return InputBinding(
            input_name=input_name,
            kind=BindingKind.CALL_OUTPUT,
            call_id=str(raw["call_id"]),
            output_name=str(raw.get("output", "output")),
        )
    raise ValueError(f"binding {input_name!r} lacks resource_id or call_id")


def plan_from_mapping(raw: object) -> CapabilityPlan:
    if not isinstance(raw, Mapping):
        raise ValueError("capability plan must be an object")
    errors: list[str] = []
    plan_id_raw = raw.get("plan_id")
    if not isinstance(plan_id_raw, str) or not plan_id_raw:
        plan_id = "<invalid-plan-id>"
        errors.append("plan_id must be a non-empty string")
    else:
        plan_id = plan_id_raw
    schema_version, schema_error = _parse_schema(raw.get("schema_version"))
    calls_raw = raw.get("calls")
    if not isinstance(calls_raw, list):
        errors.append("plan calls must be a list")
        calls_raw = []
    calls: list[PlanCall] = []
    for index, item in enumerate(calls_raw):
        if not isinstance(item, Mapping):
            errors.append(f"plan call {index} must be an object")
            continue
        call_id_raw = item.get("call_id")
        tool_id_raw = item.get("tool_id")
        if not isinstance(call_id_raw, str) or not call_id_raw:
            call_id = f"<invalid-call-{index}>"
            errors.append(f"plan call {index} requires call_id")
        else:
            call_id = call_id_raw
        if not isinstance(tool_id_raw, str) or not tool_id_raw:
            tool_id = f"<invalid-tool-{index}>"
            errors.append(f"plan call {index} requires tool_id")
        else:
            tool_id = tool_id_raw
        bindings_raw = item.get("input_bindings", {})
        literals_raw = item.get("literal_inputs", {})
        approvals_raw = item.get("requested_approvals", [])
        if not isinstance(bindings_raw, Mapping):
            errors.append(f"plan call {call_id} input_bindings must be an object")
            bindings_raw = {}
        if not isinstance(literals_raw, Mapping):
            errors.append(f"plan call {call_id} literal_inputs must be an object")
            literals_raw = {}
        if not isinstance(approvals_raw, list):
            errors.append(f"plan call {call_id} requested_approvals must be a list")
            approvals_raw = []
        bindings: list[InputBinding] = []
        for name, value in sorted(bindings_raw.items(), key=lambda pair: str(pair[0])):
            try:
                bindings.append(_binding(str(name), value))
            except ValueError as error:
                errors.append(str(error))
        calls.append(
            PlanCall(
                call_id=call_id,
                tool_id=tool_id,
                input_bindings=tuple(bindings),
                literal_inputs={str(k): v for k, v in literals_raw.items()},
                requested_approvals=tuple(str(v) for v in approvals_raw),
            )
        )
    return CapabilityPlan(
        plan_id=plan_id,
        calls=tuple(calls),
        structure_errors=tuple(errors),
        schema_error=schema_error,
        schema_version=schema_version,
    )


def load_plan(path: Path) -> CapabilityPlan:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid capability plan JSON: {error.msg}") from error
    return plan_from_mapping(raw)
