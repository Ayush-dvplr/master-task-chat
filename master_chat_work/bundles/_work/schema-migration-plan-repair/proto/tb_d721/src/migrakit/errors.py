"""Error type shared by every migrakit stage."""

from __future__ import annotations

CODES = (
    "E_PARSE",
    "E_UNKNOWN_PARTNER",
    "E_ALIAS_CYCLE",
    "E_UNKNOWN_SCHEMA",
    "E_UNREACHABLE",
    "E_PREREQ_FAILED",
    "E_REPLAY_CONFLICT",
    "E_INVALID_CORRECTION",
)


class MigrationError(Exception):
    """A rejection with one of the catalogue codes in ``CODES``."""

    def __init__(self, code: str, detail: str = "") -> None:
        if code not in CODES:
            raise ValueError(f"unknown error code {code!r}")
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail
