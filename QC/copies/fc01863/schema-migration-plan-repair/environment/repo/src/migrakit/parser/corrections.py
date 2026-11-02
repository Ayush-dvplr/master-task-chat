"""Correction log reader."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

FINGERPRINT_PREFIX = re.compile(r"[0-9a-f]{12}")


@dataclass(frozen=True)
class Correction:
    correction_id: str
    op: str
    partner: str
    key: str
    schema: str = ""
    field: str = ""
    value: object = None
    fingerprint_prefix: str = ""

    def as_step(self) -> dict:
        """The shape ``execute_plan`` takes."""
        return {
            "id": self.correction_id,
            "op": self.op,
            "schema": self.schema,
            "field": self.field,
            "value": self.value,
        }


def _parse_line(line: str) -> Correction | None:
    parts = line.split(None, 7)
    if len(parts) < 2:
        return None
    correction_id, op = parts[0], parts[1]
    if op == "REISSUE":
        if len(parts) != 5 or not FINGERPRINT_PREFIX.fullmatch(parts[4]):
            return None
        return Correction(correction_id, op, parts[2], parts[3], fingerprint_prefix=parts[4])
    if op in ("UNSET", "NULL"):
        if len(parts) != 7 or parts[4] != "AT":
            return None
        return Correction(correction_id, op, parts[2], parts[3], parts[5], parts[6])
    if op == "SET":
        if len(parts) != 8 or parts[4] != "AT":
            return None
        try:
            value = json.loads(parts[7])
        except json.JSONDecodeError:
            return None
        return Correction(correction_id, op, parts[2], parts[3], parts[5], parts[6], value)
    return None


def parse_corrections(text: str) -> tuple[list[Correction], list[str]]:
    """Return the well-formed corrections in log order and the ids of malformed lines."""
    corrections: list[Correction] = []
    malformed: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parsed = _parse_line(line)
        if parsed is None:
            malformed.append(line.split()[0])
        else:
            corrections.append(parsed)
    return corrections, malformed
