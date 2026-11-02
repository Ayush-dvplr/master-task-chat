"""Field states of a record and the presence and fill policy that reads them."""

from __future__ import annotations

from ..parser.contracts import Edge, Registry

ABSENT = "absent"
NULL = "null"
VALUE = "value"


class FieldView:
    """The state of each field of one record: absent, explicit null, or a value."""

    def __init__(self, states: dict[str, str]) -> None:
        self._states = states

    @classmethod
    def from_payload(cls, payload: dict) -> "FieldView":
        return cls({name: (NULL if value is None else VALUE) for name, value in payload.items()})

    def state(self, name: str) -> str:
        return self._states.get(name, ABSENT)

    def states(self, names: list[str]) -> tuple[str, ...]:
        return tuple(self.state(name) for name in names)

    def signature(self, names: list[str]) -> dict[str, str]:
        return {name: self.state(name) for name in sorted(names)}


def null_counts_as(registry: Registry, domain: str, name: str) -> str:
    policy = registry.policies.get((domain, name))
    if policy is not None and policy.null_counts_as:
        return policy.null_counts_as
    return registry.presence_default


def fill_mode(registry: Registry, domain: str, name: str) -> str:
    policy = registry.policies.get((domain, name))
    if policy is not None and policy.fill:
        return policy.fill
    return registry.fill_default


def counts_present(registry: Registry, domain: str, name: str, state: str) -> bool:
    if state == VALUE:
        return True
    if state == NULL:
        return null_counts_as(registry, domain, name) == "present"
    return False


def edge_allowed(registry: Registry, domain: str, view: FieldView, edge: Edge) -> bool:
    """True when every prerequisite of ``edge`` holds on the record ``view`` describes."""
    for kind, name in edge.requires:
        present = counts_present(registry, domain, name, view.state(name))
        if present != (kind == "has"):
            return False
    return True
