"""Run a plan on one record, applying pinned corrections along the way."""

from __future__ import annotations

import copy

from ..parser.contracts import Registry
from .operations import apply_operations
from .records import FieldView, edge_allowed


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
    """Execute ``plan`` from ``schema_id``, applying each correction on the first arrival at its schema."""
    domain = registry.domain_of(schema_id)
    record = copy.deepcopy(payload)
    applied: list[str] = []
    arrived: set[str] = set()

    def arrive(schema: str) -> None:
        if schema in arrived:
            return
        arrived.add(schema)
        for correction in corrections:
            if correction["schema"] == schema:
                _apply_correction(record, correction)
                applied.append(correction["id"])

    current = schema_id
    arrive(current)
    for step, edge_id in enumerate(plan):
        edge = registry.edges.get(edge_id)
        if edge is None or edge.source != current:
            raise ValueError(f"plan step {step} ({edge_id}) does not leave {current}")
        if not edge_allowed(registry, domain, FieldView.from_payload(record), edge):
            return {
                "status": "failed",
                "code": "E_PREREQ_FAILED",
                "schema": current,
                "payload": None,
                "completed_steps": step,
                "failed_edge": edge_id,
                "corrections_applied": applied,
            }
        record = apply_operations(registry, domain, record, edge.operations)
        current = edge.target
        arrive(current)
    return {
        "status": "migrated",
        "code": None,
        "schema": current,
        "payload": record,
        "completed_steps": len(plan),
        "failed_edge": None,
        "corrections_applied": applied,
    }
