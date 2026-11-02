"""Edge operations: rename, drop, add and cast, applied left to right."""

from __future__ import annotations

import copy
import re

from ..parser.contracts import Registry
from .records import ABSENT, NULL, VALUE, FieldView, fill_mode

_INTEGER = re.compile(r"[+-]?[0-9]+")
_DECIMAL = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)")


def _convert(value: object, target_type: str) -> object:
    if isinstance(value, bool):
        return value
    if target_type == "int":
        if isinstance(value, int):
            return value
        if isinstance(value, float) and value.is_integer():
            return int(value)
        if isinstance(value, str) and _INTEGER.fullmatch(value.strip()):
            return int(value.strip())
        return value
    if target_type == "float":
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str) and _DECIMAL.fullmatch(value.strip()):
            return float(value.strip())
        return value
    if isinstance(value, (int, float)):
        return str(value)
    return value


def _rename(record: dict, view: FieldView, source: str, target: str) -> None:
    if view.state(source) == ABSENT:
        return
    record[target] = record.pop(source)


def _add(registry: Registry, domain: str, record: dict, view: FieldView, name: str) -> None:
    policy = registry.policies.get((domain, name))
    if policy is None or not policy.has_default:
        return
    state = view.state(name)
    if state == ABSENT or (state == NULL and fill_mode(registry, domain, name) == "absent_or_null"):
        record[name] = copy.deepcopy(policy.default)


def _cast(record: dict, view: FieldView, name: str, target_type: str) -> None:
    if view.state(name) == VALUE:
        record[name] = _convert(record[name], target_type)


def apply_operations(
    registry: Registry, domain: str, record: dict, operations: tuple[tuple[str, ...], ...]
) -> dict:
    """Return a new record with ``operations`` applied in order."""
    result = dict(record)
    for operation in operations:
        view = FieldView.from_payload(result)
        kind = operation[0]
        if kind == "rename":
            _rename(result, view, operation[1], operation[2])
        elif kind == "drop":
            result.pop(operation[1], None)
        elif kind == "add":
            _add(registry, domain, result, view, operation[1])
        elif kind == "cast":
            _cast(result, view, operation[1], operation[2])
    return result
