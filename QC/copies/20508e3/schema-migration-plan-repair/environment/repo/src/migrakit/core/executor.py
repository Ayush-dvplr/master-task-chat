"""Run a plan on one record, applying pinned corrections along the way."""

from __future__ import annotations

import copy

from ..parser.contracts import Registry
from .operations import apply_operations


def _apply_correction(record: dict, correction: dict) -> None:
    op = correction["op"]
    name = correction["field"]
    if op == "SET":
        record[name] = copy.deepcopy(correction.get("value"))
    elif op == "UNSET":
        record.pop(name, None)
    elif op == "NULL":
        record[name] = None
    else:
        raise ValueError(f"unknown correction op {op!r}")


def execute_plan(
    registry: Registry, schema_id: str, payload: dict, plan: list[str], corrections: list[dict]
) -> dict:
    """Execute ``plan`` from ``schema_id`` after applying the record's corrections."""
    domain = registry.domain_of(schema_id)
    record = copy.deepcopy(payload)
    applied: list[str] = []
    for correction in corrections:
        _apply_correction(record, correction)
        applied.append(correction["id"])
    current = schema_id
    for step, edge_id in enumerate(plan):
        edge = registry.edges.get(edge_id)
        if edge is None or edge.source != current:
            raise ValueError(f"plan step {step} ({edge_id}) does not leave {current}")
        record = apply_operations(registry, domain, record, edge.operations)
        current = edge.target
    return {
        "status": "migrated",
        "code": None,
        "schema": current,
        "payload": record,
        "completed_steps": len(plan),
        "failed_edge": None,
        "corrections_applied": applied,
    }
