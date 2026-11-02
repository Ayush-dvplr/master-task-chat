"""Canonical partner identity."""

from __future__ import annotations

from ..errors import MigrationError
from .contracts import Registry


def resolve_partner(registry: Registry, value: object) -> str:
    """Map a partner id or alias to its canonical partner id.

    The id is found first (a partner id, else an alias), then its merge link.
    """
    if not isinstance(value, str):
        raise MigrationError("E_UNKNOWN_PARTNER", repr(value))
    if value in registry.partners:
        partner_id = value
    elif value in registry.aliases:
        partner_id = registry.aliases[value]
    else:
        raise MigrationError("E_UNKNOWN_PARTNER", value)
    visited = {partner_id}
    while partner_id in registry.merges:
        partner_id = registry.merges[partner_id]
        if partner_id in visited:
            raise MigrationError("E_ALIAS_CYCLE", value)
        visited.add(partner_id)
    return partner_id
