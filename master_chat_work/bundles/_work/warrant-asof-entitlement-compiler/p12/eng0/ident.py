"""Identity normalization: employee numbers, contractor ids and login handles."""

from __future__ import annotations

import re

_EMP = re.compile(r"^(?:[Ee]-?)?(\d{1,6})$")
_CTR = re.compile(r"^(?:[Cc][Tt][Rr]-?|[Cc]-?)(\d{1,4})$")


def norm_employee(ref) -> str | None:
    if not isinstance(ref, str):
        return None
    m = _EMP.match(ref.strip())
    return f"emp:{m.group(1).zfill(6)}" if m else None


def norm_contractor(ref) -> str | None:
    if not isinstance(ref, str):
        return None
    m = _CTR.match(ref.strip())
    return f"ctr:{m.group(1).zfill(4)}" if m else None


def norm_subject(ref) -> str | None:
    return norm_contractor(ref) or norm_employee(ref)


def norm_handle(handle) -> str:
    return handle.strip().lower() if isinstance(handle, str) else ""
