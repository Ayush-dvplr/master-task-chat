"""Replay fingerprint of a record."""

from __future__ import annotations

import hashlib
import json


def record_fingerprint(schema_id: str, payload: dict) -> str:
    """sha256 hex of the canonical JSON of the schema and payload."""
    canonical = json.dumps(
        {"payload": payload, "schema": schema_id},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
