"""Status and category of one pipeline record."""

from __future__ import annotations

from ..parser.contracts import Registry


def classify_result(plan: list[str] | None, result: dict) -> tuple[str, str | None]:
    """Status and code of an executed record."""
    return result["status"], result["code"]


def category_of(registry: Registry, status: str, code: str | None) -> str:
    """First taxonomy category listing the code; a record without a code is matched on its status."""
    wanted = code if code is not None else status
    for name, members in registry.taxonomy:
        if wanted in members:
            return name
    raise ValueError(f"no taxonomy category lists {wanted!r}")
