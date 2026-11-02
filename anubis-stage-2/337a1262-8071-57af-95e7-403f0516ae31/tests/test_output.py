"""Verifier for the 337a1262-8071-57af-95e7-403f0516ae31 task.

This verifier reads the delivered artifacts under /app/out and never reads /app/data.
It extracts the delivered tool.zip and reruns its resolve subcommand, unprivileged,
on corpora it builds itself: an embedded copy of the reference data, fresh corpora
whose override ledger, region allowances, window admits and unit cutover are
reseeded inside the value ranges the data states, and copies with one governed
input changed. The authoritative policy of
every corpus is computed here from literals, independently of the delivered tool.

Negative tests use polarity inversion: their assertions hold when a cheat is
present, so honest submissions fail those tests and avoid the negative weight.
"""

from __future__ import annotations

import ast
import base64
import hashlib
import heapq
import io
import json
import os
import pwd
import random
import re
import signal
import subprocess
import sys
import tempfile
import threading
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Any

from rewardkit import criteria, criterion

OUT = Path("/app/out")
CONFIG_PATH = OUT / "config.json"
REPORT_PATH = OUT / "report.json"
TOOL_ARCHIVE = OUT / "tool.zip"
PROFILE_DEV_PATH = OUT / "profile_dev.json"
PROFILE_PROD_PATH = OUT / "profile_prod.json"
VALIDATION_REPORT_PATH = OUT / "validation_report.json"
SUMMARY_PATH = OUT / "summary.json"

ARTIFACT_PATHS = [
    CONFIG_PATH, REPORT_PATH, TOOL_ARCHIVE, PROFILE_DEV_PATH, PROFILE_PROD_PATH,
    VALIDATION_REPORT_PATH, SUMMARY_PATH,
]
JSON_ARTIFACT_PATHS = [path for path in ARTIFACT_PATHS if path.suffix == ".json"]
ARTIFACT_NAMES = [
    "config.json", "report.json", "tool.zip", "profile_dev.json", "profile_prod.json",
    "validation_report.json", "summary.json",
]
RESOLVE_DOCS = ("policy_resolved.json", "threshold_curve.json", "dependency_trace.json")
REPAIR_DOC = "ledger_repair.json"

FORMAT_TAG = "TASK"
TRAILER = "sentinel:policy:TASK:2c016d65"
SHIPPED_CLI_SHA256 = "ba16cc906efe5a00bed557ef2736956f4027fad079613df448470c26c6a6549b"
FORBIDDEN_KEYS = {"timestamp", "generated_at", "uuid", "random_seed"}
MAX_MEMBER_BYTES = 1024 * 1024

# Authoritative chain for every corpus built here (held as literals; independent of /app/data).
ACTIVE_BUNDLE = "B7"
EFFECTIVE_INSTANT = 1700000000
EFFECTIVE_VERSION = "v100"
PARAM_KEY = "K042"
TENANT = "t-atlas"
BASE_MAX_RECORDS = 300
BASE_RETRY_LIMIT = 2
BASE_TIMEOUT_SECONDS = 2
BASE_RISK_WEIGHT = 57
MULT_BPS = 1075
MAX_RECORDS_CAP = 285
TIER = 4
BASE_THRESHOLD = 40
ITERATION_DIVISOR = 10
CONVERGENCE_EPSILON = 0
MAX_ITERATIONS = 64

# The policy of the shipped reference data.
MAX_RECORDS = 285
RETRY_LIMIT = 3
TIMEOUT_MS = 2250
RISK_THRESHOLD = 51
POLICY_CONSTANTS = (MAX_RECORDS, TIMEOUT_MS)
PROFILE_DELTAS = {
    "dev": {"max_records": -10, "retry_limit": 1, "timeout_ms": -125},
    "prod": {"max_records": 25, "retry_limit": 0, "timeout_ms": 250},
}
TRACE_KEYS = {
    "active_bundle", "effective_version", "param_key", "tenant", "client_version_ignored",
    "applied_overrides", "ledger_controls", "resolution_order", "rejected_branches",
}
TRACE_GRADED_KEYS = (
    "active_bundle", "effective_version", "param_key", "tenant", "client_version_ignored",
    "applied_overrides", "ledger_controls",
)

# Reseeded ledger heads (they replace the rows with seq up to 8). Each row: override_id, param_key,
# tenant, status, window_id, row version, rev, timeout_ms_delta, max_records_delta, retry_limit_delta,
# risk_delta.
A, U, F3, F5, C = TENANT, "t-aurora", "t-f003", "t-f005", "t-cinder"
HIDDEN_HEADS: dict[str, list[tuple[str, str, str, str, str, str, int, int, int, int, int]]] = {
    "n1-a": [
        ("OV-K301-n1", "K301", U, "active", "WIN-AUX", "v100", 2, 100, 5, 0, 1),
        ("OV-K042-n2", "K042", A, "active", "WIN-AUTH", "v100", 2, 200, -40, 1, 2),
        ("OV-K042-n3", "K042", A, "superseded", "WIN-AUTH", "v100", 2, 90, 10, 0, 2),
        ("OV-K042-n4", "K042", A, "active", "WIN-AUTH", "v100", 2, 150, -10, 1, 4),
    ],
    "n1-b": [
        ("OV-F003-n5", "K003", F3, "active", "WIN-AUX", "v100", 2, 60, 2, 0, 1),
        ("OV-F003-n6", "K003", F3, "active", "WIN-AUX", "v100", 2, 70, 3, 0, 2),
        ("OV-K042-n7", "K042", A, "active", "WIN-AUTH", "v100", 2, 120, -40, 1, 2),
        ("OV-K118-n8", "K118", A, "active", "WIN-AUTH", "v100", 2, 30, 4, 0, 1),
        ("OV-K042-n9", "K042", A, "active", "WIN-AUTH", "v100", 2, 80, -5, 1, 1),
    ],
    "n2-a": [
        ("OV-K042-u1", "K042", A, "active", "WIN-AUTH", "v100", 1, 120, -40, 1, 2),
        ("OV-K042-u2", "K042", A, "active", "WIN-AUTH", "v100", 2, 60, -5, 0, 0),
        ("OV-K042-u3", "K042", A, "superseded", "WIN-OLD", "v040", 2, 3, 6, 0, 2),
    ],
    "n2-b": [
        ("OV-K042-u4", "K042", A, "active", "WIN-AUTH", "v100", 2, 1, -40, 1, 2),
        ("OV-K118-u5", "K118", A, "active", "WIN-AUTH", "v100", 2, 0, 3, 0, 1),
    ],
    "n3-a": [
        ("OV-F003-w2", "K003", F3, "active", "WIN-AUTH", "v100", 2, 40, 3, 0, 1),
        ("OV-K042-w3", "K042", A, "active", "WIN-AUTH", "v100", 2, 300, -40, 1, 5),
        ("OV-K042-w4", "K042", A, "active", "WIN-AUX", "v100", 2, 150, -36, 1, 2),
    ],
    "n3-b": [
        ("OV-K042-w5", "K042", A, "active", "WIN-AUX", "v100", 2, 200, -40, 1, 1),
        ("OV-K042-w6", "K042", A, "active", "WIN-AUX", "v100", 2, 100, -10, 1, 2),
        ("OV-K042-w7", "K042", A, "active", "WIN-AUTH", "v100", 2, 50, 0, 0, 0),
    ],
    "hidden-a": [
        ("OV-K301-a1", "K301", U, "active", "WIN-AUX", "v100", 2, 100, 5, 0, 1),
        ("OV-K042-a2", "K042", A, "active", "WIN-AUTH", "v099", 2, 120, 15, 1, 4),
        ("OV-K042-a3", "K042", A, "active", "WIN-AUTH", "v100", 1, 80, -40, 1, 2),
        ("OV-K042-a4", "K042", A, "superseded", "WIN-AUTH", "v100", 1, -4, -30, 3, 11),
        ("OV-F003-a5", "K003", F3, "active", "WIN-AUX", "v100", 2, 40, 5, 0, 1),
        ("OV-K042-a6", "K042", A, "active", "WIN-AUTH", "v100", 2, 150, -20, 1, 3),
        ("OV-K042-a7", "K042", A, "active", "WIN-PRE", "v100", 2, 500, 30, 2, 9),
        ("OV-K042-a8", "K042", A, "active", "WIN-AUTH-V099", "v099", 2, 60, 12, 1, 6),
    ],
    "hidden-b": [
        ("OV-K042-b0", "K042", A, "active", "WIN-PRE", "v100", 2, 400, 20, 2, 8),
        ("OV-F003-b1", "K003", F3, "active", "WIN-AUTH", "v100", 2, 200, 4, 0, 1),
        ("OV-K118-b2", "K118", A, "active", "WIN-AUTH", "v100", 1, 30, -3, 0, 2),
        ("OV-K042-b3", "K042", A, "active", "WIN-AUTH", "v100", 2, 300, -40, 2, 6),
        ("OV-K042-b4", "K042", A, "active", "WIN-OLD", "v040", 2, 1, 8, 0, 1),
        ("OV-K042-b5", "K042", A, "active", "WIN-AUX", "v100", 1, 90, -45, 1, 1),
        ("OV-K042-b6", "K042", A, "superseded", "WIN-AUTH", "v100", 2, 300, -5, 1, 3),
    ],
    "hidden-c": [
        ("OV-K042-c0", "K042", A, "active", "WIN-AUTH-V099", "v100", 2, 40, 9, 1, 3),
        ("OV-F003-c1", "K003", F3, "active", "WIN-AUX", "v100", 2, 20, 1, 0, 1),
        ("OV-F005-c2", "K005", F5, "active", "WIN-AUX", "v100", 2, 30, 2, 0, 1),
        ("OV-K042-c3", "K042", A, "active", "WIN-AUX", "v100", 2, 200, -40, 1, 4),
        ("OV-K042-cs", "K042", A, "superseded", "WIN-AUTH", "v100", 2, 500, -30, 2, 9),
        ("OV-K042-c4", "K042", A, "active", "WIN-AUTH", "v100", 2, 520, -40, 1, 2),
        ("OV-K118-c5", "K118", A, "active", "WIN-AUTH", "v100", 2, 400, 0, 1, 0),
        ("OV-K042-c6", "K042", A, "active", "WIN-AUTH", "v100", 2, 90, -5, 0, 3),
        ("OV-F003-c7", "K003", F3, "superseded", "WIN-OLD", "v020", 2, 2, 1, 0, 1),
    ],
    "pool-a": [
        ("OV-F003-p1", "K003", F3, "active", "WIN-AUTH", "v100", 2, 66, 1, 0, 1),
        ("OV-K042-p2", "K042", A, "active", "WIN-AUTH", "v100", 2, 231, -59, 2, 3),
        ("OV-K042-p3", "K042", A, "active", "WIN-AUTH", "v100", 2, 516, 33, 3, 19),
        ("OV-K118-p4", "K118", A, "active", "WIN-AUTH", "v100", 2, 220, -30, 2, 17),
    ],
    "pool-b": [
        ("OV-C003-q1", "K003", C, "active", "WIN-AUTH", "v100", 2, 95, 1, 0, 1),
        ("OV-K042-q2", "K042", A, "active", "WIN-AUTH", "v100", 2, 562, 25, 0, 16),
        ("OV-K042-q3", "K042", A, "active", "WIN-AUTH", "v100", 2, 152, -49, 1, 3),
        ("OV-K042-q4", "K042", A, "active", "WIN-AUTH", "v100", 2, 158, 1, 0, 18),
    ],
    "hidden-d": [
        ("OV-F003-d1", "K003", F3, "active", "WIN-AUX", "v100", 2, 20, 1, 0, 1),
        ("OV-F003-d2", "K003", F3, "active", "WIN-AUTH", "v100", 2, 30, 2, 0, 1),
        ("OV-K118-d4", "K118", A, "active", "WIN-AUTH", "v100", 2, 4, 0, 0, 1),
        ("OV-K042-d3", "K042", A, "active", "WIN-AUTH", "v100", 2, 2, -40, 1, 2),
        ("OV-K042-d5", "K042", A, "active", "WIN-AUTH", "v100", 2, 3, -20, 1, 5),
        ("OV-K042-d6", "K042", A, "active", "WIN-AUX", "v100", 1, -1, -5, 0, 3),
    ],
}
VARIANTS: dict[str, dict[str, Any]] = {
    "shipped": {},
    "n1-a": {"head": "n1-a", "allowance": {"r-north": 2}, "admit": {"WIN-AUTH": 6}, "aux": 6},
    "n1-b": {"head": "n1-b", "allowance": {"r-north": 2}, "admit": {"WIN-AUTH": 6}, "aux": 6},
    "n2-a": {"head": "n2-a", "aux": 6},
    "n2-b": {"head": "n2-b", "aux": 6, "cutover": 1750000000},
    "n3-a": {"head": "n3-a", "admit": {"WIN-AUTH": 1}, "aux": 3},
    "n3-b": {"head": "n3-b", "admit": {"WIN-AUTH": 4}, "aux": 1},
    "hidden-a": {"head": "hidden-a", "allowance": {"r-north": 2}, "aux": 2},
    "hidden-b": {"head": "hidden-b", "allowance": {"r-north": 4}, "admit": {"WIN-AUTH": 2}, "aux": 3, "corrupt": "t-f003"},
    "hidden-c": {"head": "hidden-c", "aux": 2, "pool": {"WIN-AUTH": 1000}},
    "pool-a": {"head": "pool-a", "admit": {"WIN-AUTH": 6}, "allowance": {"r-north": 6}, "pool": {"WIN-AUTH": 1000}},
    "pool-b": {"head": "pool-b", "admit": {"WIN-AUTH": 6}, "allowance": {"r-north": 6}, "pool": {"WIN-AUTH": 960}},
    "hidden-d": {"head": "hidden-d", "allowance": {"r-03": 1, "r-north": 3}, "admit": {"WIN-AUTH": 2}, "aux": 2,
                 "cutover": 1750000000},
    "mutation-risk": {"head": "hidden-c", "aux": 2, "pool": {"WIN-AUTH": 1000}, "risk": {"OV-K042-c6": 4}},
    "mutation-allowance": {"head": "hidden-a", "aux": 2, "allowance": {"r-north": 1}},
    "mutation-pool": {"head": "pool-b", "admit": {"WIN-AUTH": 6}, "allowance": {"r-north": 6}, "pool": {"WIN-AUTH": 900}},
    "q1-a": {"gen": ("q1", 1)},
    "q1-b": {"gen": ("q1", 2)},
    "q2-a": {"gen": ("q2", 1)},
    "q2-b": {"gen": ("q2", 2)},
    "q3-a": {"gen": ("q3", 1)},
    "q3-b": {"gen": ("q3", 2)},
    "q4-a": {"gen": ("q4", 1)},
    "q4-b": {"gen": ("q4", 2)},
    "q5-a": {"gen": ("q5", 1)},
    "q5-b": {"gen": ("q5", 2)},
    "combo-a": {"gen": ("combo", 1)},
    "combo-b": {"gen": ("combo", 2)},
    "utie-a": {"gen": ("utie", 1)},
    "utie-b": {"gen": ("utie", 2)},
    "udecoy-a": {"gen": ("udecoy", 1)},
    "udecoy-b": {"gen": ("udecoy", 2)},
    "d1-a": {"gen": ("d1", 1)},
    "d1-b": {"gen": ("d1", 2)},
    "d2-a": {"gen": ("d2", 1)},
    "d2-b": {"gen": ("d2", 2)},
    "combo2-a": {"gen": ("combo2", 1)},
    "combo2-b": {"gen": ("combo2", 2)},
    "rbig-a": {"gen": ("rbig", 1)},
    "rbig-b": {"gen": ("rbig", 2)},
    "rtie-a": {"gen": ("rtie", 1)},
    "rtie-b": {"gen": ("rtie", 2)},
    "runit-a": {"gen": ("runit", 1)},
    "runit-b": {"gen": ("runit", 2)},
    "rspare-a": {"gen": ("rspare", 1)},
    "rspare-b": {"gen": ("rspare", 2)},
    "rall-a": {"gen": ("rall", 1)},
    "rall-b": {"gen": ("rall", 2)},
}
VARIANTS.update({f"fresh-{family}": {"gen": (family, 3)} for family in ("q1", "q2", "q3", "q4", "q5", "utie", "udecoy", "d1", "d2")})
HIDDEN = ("hidden-a", "hidden-b", "hidden-c", "hidden-d")
REGION_CORPORA = ("n1-a", "n1-b")
CUTOVER_CORPORA = ("n2-a", "n2-b")
ADMIT_CORPORA = ("n3-a", "n3-b")
POOL_CORPORA = ("pool-a", "pool-b")
AUX_WINDOW = '<window id="WIN-AUX" start="1699999600" end="1700000400" version="v100" admit="{admit}" timeout_pool="{pool}" />'
RESOLUTION_CHAIN = ("boot_manifest.toml", "bundle_ledger.jsonc", "principal_role_index.yaml", "override_deltas.json")
# Rules whose branch the shipped corpus never takes; each owns two generated corpora, and the combo corpora put
# two of them on the same record. READINGS lists the wrong readings each owned corpus must tell apart.
TIMEOUT_FLOOR_MS = 1000
QUIET = ("q1", "q2", "q3", "q4", "q5")
READINGS = {
    "q1": ("q1-sum", "q1-final"),
    "q2": ("q2-none",),
    "q3": ("q3-none", "q3-nospan"),
    "q4": ("q4-none", "q4-anyorder"),
    "q5": ("q5-none", "q5-any"),
}
OWNED = {family: (f"{family}-a", f"{family}-b") for family in QUIET}
COMBO_CORPORA = ("combo-a", "combo-b")
# Rules whose state comes from earlier records: the curve reports that fix the divisor (utie, udecoy), the resets
# that withdraw earlier reports (d1) and reinstated rows (d2). The combo2 corpora put them on Q1-Q5 records.
STATEFUL = ("utie", "udecoy", "d1", "d2")
READINGS.update({
    "utie": ("u-none", "u-firstfit", "u-firstreport"),
    "udecoy": ("u-none", "u-firstreport"),
    "d1": ("d1-none", "d1-first"),
    "d2": ("d2-none", "d2-own", "d2-prev", "d2-first"),
})
OWNED.update({family: (f"{family}-a", f"{family}-b") for family in STATEFUL})
COMBO2_CORPORA = ("combo2-a", "combo2-b")
UNIQUE_FIT_CORPORA = OWNED["utie"] + OWNED["udecoy"]
DIVISORS = range(6, 15)
# role key -> (param_key, risk_weight_base, mult_bps, base_threshold of its role_level)
WITNESS = {
    "operator": ("K042", 57, 1075, 40),
    "operator_legacy": ("K118", 88, 1075, 70),
    "auditor": ("K077", 41, 1000, 30),
    "guardian": ("K201", 63, 1120, 55),
}
# Ledger repair corpora: two filler tenants per corpus store controls that omit some spare rows, and a third
# tenant's controls fit no set of its spare rows. Each family plants the cases its readings must tell apart.
REPAIR_FAMILIES = ("rbig", "rtie", "runit", "rspare", "rall")
REPAIR_FLAGS = {"rbig": ("tie", "unit"), "rtie": ("tie", "spare"), "runit": ("unit",), "rspare": ("spare",),
                "rall": ("tie", "unit", "spare")}
REPAIR_QUIET = ("r-tie-last", "r-unit", "r-q2", "r-q5", "r-d2")
REPAIR_READINGS = {
    "rbig": ("r-tie-last", "r-unit", "r-records", "r-greedy"),
    "rtie": ("r-tie-last", "r-q2", "r-q5", "r-d2", "r-greedy"),
    "runit": ("r-unit", "r-greedy"),
    "rspare": ("r-q2", "r-q5", "r-d2", "r-greedy"),
    "rall": REPAIR_QUIET + ("r-greedy",),
}
REPAIR_CORPORA = {family: (f"{family}-a", f"{family}-b") for family in REPAIR_FAMILIES}
REPAIR_FEASIBLE_CORPORA = REPAIR_CORPORA["rbig"] + REPAIR_CORPORA["runit"]
REPAIR_KEYS = tuple(f"K0{index:02d}" for index in range(100) if index not in (42, 77))
POST_CUTOVER_VERSIONS = tuple(f"v{index:03d}" for index in range(50, 240) if index != 100)
PRE_CUTOVER_VERSIONS = tuple(f"v{index:03d}" for index in range(50))
REPAIR_BUDGET = 400000
_GENERATED: dict[tuple[str, int], dict[str, Any]] = {}
_GEN_LOCK = threading.Lock()

_SETPRIV = ["setpriv", "--reuid=nobody", "--regid=nogroup", "--clear-groups"]
_TOOL_ROOT: Path | None = None
_CORPUS_FILES: dict[str, bytes] | None = None
_RESOLVED: dict[str, dict[str, bytes]] = {}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def config_doc(max_records: int, retry_limit: int, timeout_ms: int) -> dict[str, Any]:
    return {
        "checksum": "crc32",
        "container": "policy-bundle",
        "max_records": max_records,
        "mode": "strict-local",
        "producer": "sentinel-policyd",
        "profile": FORMAT_TAG,
        "retry_limit": retry_limit,
        "timeout_ms": timeout_ms,
        "trailer": TRAILER,
    }


def expected_config() -> dict[str, Any]:
    return config_doc(MAX_RECORDS, RETRY_LIMIT, TIMEOUT_MS)


def expected_profile(name: str, policy: dict[str, Any]) -> dict[str, Any]:
    deltas = PROFILE_DELTAS[name]
    data = config_doc(
        policy["max_records"] + deltas["max_records"],
        policy["retry_limit"] + deltas["retry_limit"],
        policy["timeout_ms"] + deltas["timeout_ms"],
    )
    data["profile"] = f"{FORMAT_TAG}-{name}"
    data["trailer"] = f"{TRAILER}:{name}"
    return data


def first_difference(got: Any, want: Any, path: str = "$") -> str | None:
    if isinstance(want, dict) and isinstance(got, dict):
        for key in sorted(set(want) | set(got)):
            if key not in got:
                return f"{path}.{key} missing (expected {want[key]!r})"
            if key not in want:
                return f"{path}.{key} unexpected (got {got[key]!r})"
            found = first_difference(got[key], want[key], f"{path}.{key}")
            if found:
                return found
        return None
    if isinstance(want, list) and isinstance(got, list):
        for index, (left, right) in enumerate(zip(got, want)):
            found = first_difference(left, right, f"{path}[{index}]")
            if found:
                return found
        if len(got) != len(want):
            return f"{path} has {len(got)} entries, expected {len(want)}"
        return None
    if type(got) is not type(want) or got != want:
        return f"{path} is {got!r}, expected {want!r}"
    return None


def assert_document(got: Any, want: Any, label: str) -> None:
    difference = first_difference(got, want)
    assert difference is None, f"{label}: {difference}"


def _grant_read(root: Path) -> None:
    """Make a grader-built tree readable by the unprivileged user that runs the tool."""
    for path in [root, *root.rglob("*")]:
        path.chmod(0o755 if path.is_dir() else 0o644)


def untrusted_command(command: list[str]) -> list[str]:
    if os.name == "posix" and os.geteuid() == 0:
        return [*_SETPRIV, *command]
    return command


def _kill_leftovers(pgid: int) -> None:
    try:
        os.killpg(pgid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    if os.name != "posix" or os.geteuid() != 0:
        return
    nobody = pwd.getpwnam("nobody").pw_uid
    for status in Path("/proc").glob("[0-9]*/status"):
        try:
            text = status.read_text()
        except OSError:
            continue
        match = re.search(r"^Uid:\s+(\d+)", text, re.M)
        if match and int(match.group(1)) == nobody:
            try:
                os.kill(int(status.parent.name), signal.SIGKILL)
            except ProcessLookupError:
                pass


def tool_root() -> Path:
    global _TOOL_ROOT
    if _TOOL_ROOT is not None:
        return _TOOL_ROOT
    root = Path(tempfile.mkdtemp(prefix="sentinel-tool-"))
    with zipfile.ZipFile(TOOL_ARCHIVE) as zf:
        names: set[str] = set()
        for info in zf.infolist():
            rel = Path(info.filename)
            assert not rel.is_absolute() and ".." not in rel.parts and "\\" not in info.filename, f"unsafe member {info.filename}"
            assert info.filename not in names, f"duplicate member {info.filename}"
            assert info.file_size <= MAX_MEMBER_BYTES, f"oversized member {info.filename}"
            names.add(info.filename)
            if info.is_dir():
                continue
            dest = root / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(zf.read(info))
    _grant_read(root)
    _TOOL_ROOT = root
    return root


def tool_path() -> Path:
    return tool_root() / "cli.py"


def schema_path() -> Path:
    return tool_root() / "schema.json"


def run_repaired_cli(*args: str) -> subprocess.CompletedProcess[str]:
    path = tool_path()
    assert path.is_file(), "cli.py is missing from the delivered tool.zip"
    command = untrusted_command([sys.executable, "-I", str(path), *args])
    proc = subprocess.Popen(
        command,
        cwd="/tmp",
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env={"PATH": "/usr/local/bin:/usr/bin:/bin", "PYTHONHASHSEED": "0", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"},
        start_new_session=True,
    )
    try:
        stdout, stderr = proc.communicate(timeout=60)
    except subprocess.TimeoutExpired:
        stdout, stderr = "", "timed out after 60 seconds"
    finally:
        _kill_leftovers(proc.pid)
        proc.wait()
    return subprocess.CompletedProcess(command, proc.returncode, stdout, stderr)


def writable_dir(prefix: str) -> Path:
    path = Path(tempfile.mkdtemp(prefix=prefix))
    path.chmod(0o1777)
    return path


def corpus_files() -> dict[str, bytes]:
    global _CORPUS_FILES
    if _CORPUS_FILES is None:
        with zipfile.ZipFile(io.BytesIO(base64.b64decode(REFERENCE_CORPUS_B64))) as zf:
            _CORPUS_FILES = {info.filename: zf.read(info) for info in zf.infolist()}
    return _CORPUS_FILES


def generated_spec(family: str, seed: int) -> dict[str, Any]:
    with _GEN_LOCK:
        if (family, seed) not in _GENERATED:
            _GENERATED[(family, seed)] = generate_spec(family, seed)
        return json.loads(json.dumps(_GENERATED[(family, seed)]))


def build_variant(name: str) -> tuple[dict[str, bytes], list[dict[str, Any]], dict[str, Any]]:
    """Return the corpus files, ledger rows and stored controls of one corpus."""
    spec = VARIANTS[name]
    if "gen" in spec:
        spec = generated_spec(*spec["gen"])
    return build_from_spec(name, spec)


def build_from_spec(name: str, spec: dict[str, Any]) -> tuple[dict[str, bytes], list[dict[str, Any]], dict[str, Any]]:
    files = dict(corpus_files())
    ledger = json.loads(files["override_deltas.json"])
    rows = [dict(row) for row in ledger["overrides"]]
    stored = ledger["controls"]
    if "head" in spec or "rows" in spec:
        head = [dict(row) for row in spec.get("rows", [])]
        for override_id, param_key, tenant, status, window_id, version, rev, timeout, records, retry, risk in HIDDEN_HEADS.get(spec.get("head"), []):
            head.append({
                "max_records_delta": records, "override_id": override_id, "param_key": param_key,
                "retry_limit_delta": retry, "rev": rev, "risk_delta": risk, "seq": 0, "status": status,
                "tenant": tenant, "timeout_ms_delta": timeout, "version": version, "window_id": window_id,
            })
        rows = head + [row for row in rows if int(row["seq"]) > 8]
        for index, row in enumerate(rows):
            row["seq"] = 10 + 3 * index
    for override_id, value in spec.get("risk", {}).items():
        edited = [row for row in rows if row["override_id"] == override_id]
        assert len(edited) == 1, f"corpus {name} has no single row {override_id}"
        edited[0]["risk_delta"] = value
    text = files["effective_windows.xml"].decode("utf-8")
    for window_id, admit in spec.get("admit", {}).items():
        text, count = re.subn(rf'(<window id="{window_id}" [^>]*admit=")[0-9]+(")', rf"\g<1>{admit}\g<2>", text)
        assert count == 1, f"corpus {name} has no single window {window_id}"
    if "aux" in spec:
        text = text.replace("</windows>", AUX_WINDOW.format(admit=spec["aux"], pool=spec.get("aux_pool", 1500)) + "</windows>")
    for window_id, pool in spec.get("pool", {}).items():
        text, count = re.subn(rf'(<window id="{window_id}" [^>]*timeout_pool=")[0-9]+(")', rf"\g<1>{pool}\g<2>", text)
        assert count == 1, f"corpus {name} has no single window {window_id}"
    files["effective_windows.xml"] = text.encode("utf-8")
    quota = files["quota_limits.cfg"].decode("utf-8")
    for region, allowance in spec.get("allowance", {}).items():
        quota, count = re.subn(rf"^{region} = [0-9]+$", f"{region} = {allowance}", quota, flags=re.M)
        assert count == 1, f"corpus {name} has no single allowance line for {region}"
    files["quota_limits.cfg"] = quota.encode("utf-8")
    if "cutover" in spec:
        units, count = re.subn(r"^timeout_ms_delta cutover: [0-9]+$", f"timeout_ms_delta cutover: {spec['cutover']}",
                               files["units_reference.txt"].decode("utf-8"), flags=re.M)
        assert count == 1, f"corpus {name} has no single cutover line"
        files["units_reference.txt"] = units.encode("utf-8")
    if "head" in spec or "rows" in spec or "risk" in spec:
        cut = [row for row in rows if row.pop("_cut", False)]
        stored = ledger_controls(files, rows)
        if "corrupt" in spec:
            stored[spec["corrupt"]]["rows"] += 1
        delta_ms = unit_reader(files)
        for row in cut:
            stored[row["tenant"]]["rows"] -= 1
            stored[row["tenant"]]["max_records_delta_sum"] -= int(row["max_records_delta"])
            stored[row["tenant"]]["timeout_ms_delta_sum_ms"] -= delta_ms(row)
        for tenant, amount in spec.get("skew", {}).items():
            stored[tenant]["max_records_delta_sum"] += amount
        document: dict[str, Any] = {"conventions": ledger["conventions"]}
        if spec.get("aliases"):
            document["param_key_aliases"] = [{key: entry[key] for key in sorted(entry)} for entry in spec["aliases"]]
        document["overrides"] = [{key: row[key] for key in sorted(row)} for row in rows]
        if spec.get("reports"):
            document["reports"] = [{key: entry[key] for key in sorted(entry) if key != "at"} | {"seq": 11 + 3 * entry["at"]}
                                   for entry in sorted(spec["reports"], key=lambda entry: entry["at"])]
        document["controls"] = stored
        files["override_deltas.json"] = (json.dumps(document, indent=2) + "\n").encode("utf-8")
    return files, rows, stored


def unit_reader(files: dict[str, bytes]):
    """timeout_ms_delta in milliseconds: whole seconds when the row version starts before the cutover."""
    starts = {entry["version"]: int(entry["effective_from"]) for entry in json.loads(files["policy_version_map.json"])["versions"]}
    cutover = int(re.search(r"^timeout_ms_delta cutover: ([0-9]+)$", files["units_reference.txt"].decode("utf-8"), re.M).group(1))

    def delta_ms(row: dict[str, Any]) -> int:
        value = int(row["timeout_ms_delta"])
        return value * 1000 if starts[row["version"]] < cutover else value
    return delta_ms


def ledger_controls(files: dict[str, bytes], rows: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    delta_ms = unit_reader(files)
    controls: dict[str, dict[str, int]] = {}
    for row in rows:
        entry = controls.setdefault(row["tenant"], {"max_records_delta_sum": 0, "rows": 0, "timeout_ms_delta_sum_ms": 0})
        entry["rows"] += 1
        entry["max_records_delta_sum"] += int(row["max_records_delta"])
        entry["timeout_ms_delta_sum_ms"] += delta_ms(row)
    return {tenant: controls[tenant] for tenant in sorted(controls)}


def scaled(amount: int) -> int:
    return (amount * MULT_BPS + 500) // 1000


def pooled_deltas(files: dict[str, bytes], drawn: list[dict[str, Any]], delta_ms) -> dict[int, int]:
    """The timeout delta each applied row (keyed by seq) adds after its window's timeout_pool is shared."""
    pools = {node.get("id"): int(node.get("timeout_pool")) for node in ET.fromstring(files["effective_windows.xml"]).iter("window")}
    added: dict[int, int] = {}
    for window_id in sorted({row["window_id"] for row in drawn}):
        group = [row for row in drawn if row["window_id"] == window_id]
        positive = {int(row["seq"]): delta_ms(row) for row in group if delta_ms(row) > 0}
        total, pool = sum(positive.values()), pools[window_id]
        if total <= pool:
            added.update(positive)
        else:
            kept = {key: value for key, value in positive.items() if pool * value // total >= 100}
            kept_total = sum(kept.values())
            added.update({key: (pool * kept[key] // kept_total if key in kept else 0) for key in positive})
        added.update({int(row["seq"]): delta_ms(row) for row in group if delta_ms(row) <= 0})
    return added


def converge(seed: int, amount: int, divisor: int) -> list[int]:
    """The reconciliation sequence from the seed: every computed value up to the first one within epsilon."""
    iterations = [seed]
    for _ in range(MAX_ITERATIONS):
        following = seed + (amount + iterations[-1]) // divisor
        settled = abs(following - iterations[-1]) <= CONVERGENCE_EPSILON
        iterations.append(following)
        if settled:
            break
    return iterations


def evaluate(files: dict[str, bytes], rows: list[dict[str, Any]], stored: dict[str, Any],
             readings: frozenset[str] = frozenset()) -> tuple[dict[str, Any], dict[str, Any]]:
    """The authoritative documents of one corpus (or those of the named wrong readings) and the quiet-rule fire counts."""
    delta_ms = unit_reader(files)
    region_of = {node.get("id"): node.get("region") for node in ET.fromstring(files["tenant_catalog.xml"]).iter("tenant")}
    section = files["quota_limits.cfg"].decode("utf-8").split("[override_allowance]", 1)[1]
    allowance = {key: int(value) for key, value in re.findall(r"^([a-z0-9-]+) = ([0-9]+)$", section, re.M)}
    windows = list(ET.fromstring(files["effective_windows.xml"]).iter("window"))
    spans = {node.get("id"): (int(node.get("start")), int(node.get("end")), node.get("version")) for node in windows}
    admits = {node.get("id"): int(node.get("admit")) for node in windows}
    aliases = json.loads(files["override_deltas.json"]).get("param_key_aliases", [])
    alias_names = {entry["alias"] for entry in aliases}

    def principal_of(row: dict[str, Any]) -> str | None:
        if row["param_key"] not in alias_names or "q3-none" in readings:
            return row["param_key"]
        for entry in aliases:
            if entry["alias"] == row["param_key"] and ("q3-nospan" in readings or int(entry["start"]) <= EFFECTIVE_INSTANT < int(entry["end"])):
                return entry["principal"]
        return None

    def in_window(row: dict[str, Any]) -> bool:
        span = spans.get(row["window_id"])
        return (span is not None and span[0] <= EFFECTIVE_INSTANT < span[1] and span[2] == EFFECTIVE_VERSION
                and row["version"] == EFFECTIVE_VERSION)

    ordered = sorted(rows, key=lambda row: int(row["seq"]))
    last_seq = {row["override_id"]: int(row["seq"]) for row in ordered}
    reissued = [row for row in ordered if int(row["seq"]) < last_seq[row["override_id"]]]
    fires = dict.fromkeys(QUIET, 0)
    fires["q2"] = sum(1 for row in reissued if row["status"] == "active" and in_window(row))
    reinstated_from: dict[int, dict[str, Any]] = {}
    for index, row in enumerate(ordered):
        if row["status"] != "reinstated" or "d2-none" in readings:
            continue
        earlier = [item for item in ordered[:index] if item["override_id"] == row["override_id"]]
        active = [item for item in earlier if item["status"] == "active"]
        if "d2-own" in readings:
            reinstated_from[int(row["seq"])] = row
        elif "d2-prev" in readings and earlier:
            reinstated_from[int(row["seq"])] = earlier[-1]
        elif active:
            reinstated_from[int(row["seq"])] = active[0] if "d2-first" in readings else active[-1]

    def deltas_of(row: dict[str, Any]) -> dict[str, Any]:
        return reinstated_from.get(int(row["seq"]), row)

    fires["d2"] = sum(1 for row in ordered if int(row["seq"]) in reinstated_from and in_window(row)
                      and int(row["seq"]) == last_seq[row["override_id"]])

    def draw(requires: str, named: frozenset[str] = frozenset()) -> tuple[list[dict[str, Any]], int]:
        region_left, admit_left = dict(allowance), dict(admits)
        drawn: list[dict[str, Any]] = []
        refused = 0
        for row in ordered:
            if (row["status"] != "active" and int(row["seq"]) not in reinstated_from) or not in_window(row):
                continue
            if "q2-none" not in readings and int(row["seq"]) < last_seq[row["override_id"]]:
                continue
            if row.get("requires") is not None and requires != "none":
                if row["requires"] not in (named if requires == "set" else {item["override_id"] for item in drawn}):
                    refused += 1
                    continue
            region = region_of[row["tenant"]]
            if region_left[region] == 0 or admit_left[row["window_id"]] == 0:
                continue
            region_left[region] -= 1
            admit_left[row["window_id"]] -= 1
            drawn.append(row)
        return drawn, refused

    if "q4-none" in readings:
        drawn, _ = draw("none")
    elif "q4-anyorder" in readings:
        drawn, _ = draw("set", frozenset(row["override_id"] for row in draw("none")[0]))
    else:
        drawn, fires["q4"] = draw("order")
    fires["north"] = sum(1 for row in drawn if region_of[row["tenant"]] == "r-north")
    fires["q3"] = sum(1 for row in ordered if row["param_key"] in alias_names and in_window(row)
                      and (row["status"] == "active" or row.get("carry")))
    carried = [] if "q5-none" in readings else [
        row for row in ordered
        if row["status"] == "superseded" and row.get("carry") and principal_of(row) is not None
        and ("q5-any" in readings or in_window(row))
    ]
    fires["q5"] = sum(1 for row in carried if principal_of(row) == PARAM_KEY)
    added = pooled_deltas(files, drawn, lambda row: delta_ms(deltas_of(row)))
    applied = [row for row in drawn if principal_of(row) == PARAM_KEY]
    records = [int(deltas_of(row)["max_records_delta"]) for row in applied]
    records += [int(row["max_records_delta"]) for row in carried if row["carry"] == "max_records_delta" and principal_of(row) == PARAM_KEY]
    risks = [int(deltas_of(row)["risk_delta"]) for row in applied]
    risks += [int(row["risk_delta"]) for row in carried if row["carry"] == "risk_delta" and principal_of(row) == PARAM_KEY]
    max_records = min(MAX_RECORDS_CAP, scaled(BASE_MAX_RECORDS + sum(records)))
    retry_limit = BASE_RETRY_LIMIT + sum(int(deltas_of(row)["retry_limit_delta"]) for row in applied)
    timeout_ms = BASE_TIMEOUT_SECONDS * 1000
    if "q1-sum" in readings or "q1-final" in readings:
        timeout_ms += sum(added[int(row["seq"])] for row in applied)
        if "q1-final" in readings:
            timeout_ms = max(TIMEOUT_FLOOR_MS, timeout_ms)
    else:
        for row in applied:
            timeout_ms += added[int(row["seq"])]
            if timeout_ms < TIMEOUT_FLOOR_MS:
                timeout_ms = TIMEOUT_FLOOR_MS
                fires["q1"] += 1
    contribution = sum(scaled(term) for term in [BASE_RISK_WEIGHT, *risks])

    def witness_amount(role: str) -> int:
        key, base, bps, _ = WITNESS[role]
        terms = [base] + [int(deltas_of(row)["risk_delta"]) for row in drawn if principal_of(row) == key]
        terms += [int(row["risk_delta"]) for row in carried if row["carry"] == "risk_delta" and principal_of(row) == key]
        return sum((term * bps + 500) // 1000 for term in terms)

    amounts = {role: witness_amount(role) for role in WITNESS}
    reports = sorted(json.loads(files["override_deltas.json"]).get("reports", []), key=lambda entry: int(entry["seq"]))
    resets = [int(entry["seq"]) for entry in reports if entry["kind"] == "reset"]
    curves = [entry for entry in reports if entry["kind"] == "curve"]
    standing = [entry for entry in curves if not any(seq > int(entry["seq"]) for seq in resets)]
    fires["u"], fires["d1"] = len(standing), len(curves) - len(standing)
    if "d1-none" in readings:
        standing = curves
    elif "d1-first" in readings and resets:
        standing = [entry for entry in curves if int(entry["seq"]) > min(resets)]

    def fit_set(entries: list[dict[str, Any]]) -> list[int]:
        return [trial for trial in DIVISORS if all(
            converge(WITNESS[entry["role"]][3], amounts[entry["role"]], trial)[-1] == int(entry["converged"]) for entry in entries)]

    divisor: int | None = ITERATION_DIVISOR
    if standing and "u-none" not in readings:
        fitting = fit_set(standing[:1] if "u-firstreport" in readings else standing)
        if "u-firstfit" in readings or "u-firstreport" in readings:
            divisor = fitting[0] if fitting else None
        else:
            divisor = fitting[0] if len(fitting) == 1 else None
    fires["divisor"], fires["amounts"] = divisor, amounts
    iterations = converge(BASE_THRESHOLD, contribution, divisor) if divisor is not None else [BASE_THRESHOLD]
    policy = config_doc(max_records, retry_limit, timeout_ms)
    policy.update({
        "effective_version": EFFECTIVE_VERSION, "param_key": PARAM_KEY,
        "risk_threshold": iterations[-1] if divisor is not None else None, "tenant": TENANT,
    })
    curve = {
        "base_threshold": BASE_THRESHOLD, "contribution": contribution,
        "converged": iterations[-1] if divisor is not None else None, "iterations": iterations, "tier": TIER,
    }
    recomputed = ledger_controls(files, rows)
    trace = {
        "active_bundle": ACTIVE_BUNDLE,
        "applied_overrides": [row["override_id"] for row in applied],
        "client_version_ignored": True,
        "effective_version": EFFECTIVE_VERSION,
        "ledger_controls": {tenant: ("ok" if recomputed.get(tenant) == stored[tenant] else "mismatch") for tenant in sorted(stored)},
        "param_key": PARAM_KEY,
        "tenant": TENANT,
    }
    return {"policy_resolved.json": policy, "threshold_curve.json": curve, "dependency_trace.json": trace}, fires


def reference_documents(name: str) -> dict[str, Any]:
    """The authoritative policy, curve and graded trace fields of one corpus."""
    return evaluate(*build_variant(name))[0]


def spare_seqs(rows: list[dict[str, Any]], readings: frozenset[str] = frozenset()) -> set[int]:
    """The seq of every spare row: withdrawn, superseded without carry, or below a higher-seq row of its override_id,
    except the last active row below a reinstated highest-seq row of its override_id."""
    ordered = sorted(rows, key=lambda row: int(row["seq"]))
    last_seq = {row["override_id"]: int(row["seq"]) for row in ordered}
    latest_active: dict[str, dict[str, Any]] = {}
    kept: set[int] = set()
    for row in ordered:
        if row["status"] == "active":
            latest_active[row["override_id"]] = row
        elif (row["status"] == "reinstated" and row["override_id"] in latest_active and "r-d2" not in readings
              and int(row["seq"]) == last_seq[row["override_id"]]):
            kept.add(int(latest_active[row["override_id"]]["seq"]))
    return {int(row["seq"]) for row in ordered if int(row["seq"]) not in kept and (
        row["status"] == "withdrawn"
        or (row["status"] == "superseded" and ("carry" not in row or "r-q5" in readings))
        or ("r-q2" not in readings and int(row["seq"]) < last_seq[row["override_id"]]))}


def repair_document(files: dict[str, bytes], rows: list[dict[str, Any]], stored: dict[str, Any],
                    readings: frozenset[str] = frozenset(), budget: int = REPAIR_BUDGET) -> dict[str, Any]:
    """The ledger_repair document of one corpus (or that of the named wrong readings)."""
    delta_ms = unit_reader(files)
    recomputed = ledger_controls(files, rows)
    spare = spare_seqs(rows, readings)
    document: dict[str, Any] = {}
    for tenant in sorted(stored):
        got = recomputed.get(tenant, {"max_records_delta_sum": 0, "rows": 0, "timeout_ms_delta_sum_ms": 0})
        if got == stored[tenant]:
            continue
        count = got["rows"] - stored[tenant]["rows"]
        need_m = got["max_records_delta_sum"] - stored[tenant]["max_records_delta_sum"]
        need_t = got["timeout_ms_delta_sum_ms"] - stored[tenant]["timeout_ms_delta_sum_ms"]
        cands = sorted((abs(int(row["timeout_ms_delta"])) if "r-unit" in readings else abs(delta_ms(row)),
                        int(row["seq"]), int(row["max_records_delta"]), delta_ms(row))
                       for row in rows if row["tenant"] == tenant and int(row["seq"]) in spare)
        if count < 0 or count > len(cands):
            document[tenant] = None
            continue
        if "r-greedy" in readings:
            pick = cands[:count]
            fits = sum(c[2] for c in pick) == need_m and sum(c[3] for c in pick) == need_t
            document[tenant] = sorted(c[1] for c in pick) if fits else None
            continue
        start = tuple(range(count))
        heap = [(sum(cands[i][0] for i in start), start)]
        seen, best, found, pops = {start}, None, [], 0
        while heap:
            cost, index = heapq.heappop(heap)
            pops += 1
            if pops > budget:
                found, best = ["slow"], -1
                break
            if best is not None and cost > best:
                break
            if sum(cands[i][2] for i in index) == need_m and (
                    "r-records" in readings or sum(cands[i][3] for i in index) == need_t):
                best = cost
                found.append(sorted(cands[i][1] for i in index))
            for position in range(count):
                following = index[position] + 1
                if following < (index[position + 1] if position + 1 < count else len(cands)):
                    nxt = index[:position] + (following,) + index[position + 1:]
                    if nxt not in seen:
                        seen.add(nxt)
                        heapq.heappush(heap, (cost - cands[index[position]][0] + cands[following][0], nxt))
        if found == ["slow"]:
            document[tenant] = "slow"
        elif not found:
            document[tenant] = None
        else:
            chosen = max(found) if "r-tie-last" in readings else min(found)
            if "r-records" in readings:
                ms = {c[1]: c[3] for c in cands}
                chosen = chosen if sum(ms[seq] for seq in chosen) == need_t else None
            document[tenant] = chosen
    return document


def reference_repair(name: str) -> dict[str, Any]:
    """The authoritative ledger_repair document of one corpus."""
    return repair_document(*build_variant(name))


class _Planter:
    """Draws the rows of one generated corpus from its own random stream."""

    def __init__(self, rng: random.Random, keys: set[str], ids: set[str]):
        self.rng, self.keys, self.ids = rng, set(keys), set(ids)

    def new_id(self, key: str) -> str:
        while True:
            override_id = f"OV-{key}-{self.rng.randrange(1000, 10000)}"
            if override_id not in self.ids:
                self.ids.add(override_id)
                return override_id

    def new_alias(self) -> str:
        while True:
            key = f"K{self.rng.randrange(2000, 10000)}"
            if key not in self.keys:
                self.keys.add(key)
                return key

    def row(self, param_key: str = PARAM_KEY, tenant: str = TENANT, status: str = "active", window_id: str | None = None,
            timeout: int | None = None, records: int | None = None, risk: int | None = None,
            override_id: str | None = None, **extra: Any) -> dict[str, Any]:
        rng = self.rng
        row = {
            "max_records_delta": rng.randint(-15, 15) if records is None else records,
            "override_id": override_id or self.new_id(param_key), "param_key": param_key,
            "retry_limit_delta": rng.randint(0, 1), "rev": 2,
            "risk_delta": rng.randint(0, 6) if risk is None else risk, "seq": 0, "status": status, "tenant": tenant,
            "timeout_ms_delta": rng.randint(100, 400) if timeout is None else timeout,
            "version": EFFECTIVE_VERSION, "window_id": window_id or rng.choice(("WIN-AUTH", "WIN-AUX")),
        }
        row.update(extra)
        return row

    def noise(self, kinds: tuple[str, ...] = ("cinder", "aurora", "pre", "superseded")) -> dict[str, Any]:
        kind = self.rng.choice(kinds)
        if kind == "cinder":
            return self.row("K201", "t-cinder")
        if kind == "aurora":
            return self.row("K301", "t-aurora")
        if kind == "pre":
            return self.row(window_id="WIN-PRE")
        return self.row(status="superseded")

    def interleave(self, fragments: list[list[dict[str, Any]]]) -> list[dict[str, Any]]:
        pending = [list(fragment) for fragment in fragments if fragment]
        merged = []
        while pending:
            fragment = self.rng.choice(pending)
            merged.append(fragment.pop(0))
            if not fragment:
                pending.remove(fragment)
        return merged

    def spec(self, fragments: list[list[dict[str, Any]]], aliases: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        spec: dict[str, Any] = {"rows": self.interleave(fragments), "allowance": {"r-north": 6}, "admit": {"WIN-AUTH": 6}, "aux": 6}
        if aliases:
            spec["aliases"] = aliases
        return spec

    def inside_alias(self) -> dict[str, Any]:
        start = EFFECTIVE_INSTANT if self.rng.random() < 0.5 else EFFECTIVE_INSTANT - self.rng.randint(1, 5000)
        return {"alias": self.new_alias(), "principal": PARAM_KEY, "start": start, "end": EFFECTIVE_INSTANT + self.rng.randint(1, 5000)}

    def outside_alias(self) -> dict[str, Any]:
        if self.rng.random() < 0.5:
            start, end = EFFECTIVE_INSTANT - self.rng.randint(1000, 5000), EFFECTIVE_INSTANT
        else:
            start = EFFECTIVE_INSTANT + self.rng.randint(1, 3000)
            end = start + self.rng.randint(1, 5000)
        return {"alias": self.new_alias(), "principal": PARAM_KEY, "start": start, "end": end}


def plant_q1(p: _Planter) -> dict[str, Any]:
    rows = [p.row(timeout=-p.rng.randint(500, 900)) for _ in range(p.rng.randint(3, 4))]
    rows += [p.row(timeout=p.rng.randint(100, 600)) for _ in range(p.rng.randint(1, 2))]
    p.rng.shuffle(rows)
    return p.spec([rows, [p.noise(("cinder", "pre", "superseded")) for _ in range(p.rng.randint(1, 2))]])


def plant_q2(p: _Planter) -> dict[str, Any]:
    fragments = []
    for kind in p.rng.sample(["gone", "twice", "aurora"], p.rng.randint(2, 3)):
        if kind == "aurora":
            first = p.row("K301", "t-aurora")
            fragments.append([first, p.row("K301", "t-aurora", status="superseded", override_id=first["override_id"])])
        else:
            first = p.row()
            fragments.append([first, p.row(status="superseded" if kind == "gone" else "active", override_id=first["override_id"])])
    fragments.append([p.row() for _ in range(p.rng.randint(1, 2))])
    fragments.append([p.noise(("cinder", "pre"))])
    return p.spec(fragments)


def plant_q3(p: _Planter) -> dict[str, Any]:
    inside, outside = p.inside_alias(), p.outside_alias()
    fragments = [[p.row(inside["alias"]) for _ in range(p.rng.randint(1, 2))],
                 [p.row(outside["alias"]) for _ in range(p.rng.randint(1, 2))],
                 [p.row()], [p.noise(("cinder", "pre", "superseded"))]]
    return p.spec(fragments, [inside, outside])


def plant_q4(p: _Planter) -> dict[str, Any]:
    later = p.row("K201", "t-cinder")
    fragments = [[p.row(requires=later["override_id"]), later]]
    if p.rng.random() < 0.5:
        ghost = p.row(status="superseded")
        fragments += [[ghost], [p.row(requires=ghost["override_id"])]]
    else:
        ghost = p.row(window_id="WIN-PRE")
        fragments += [[ghost], [p.row("K301", "t-aurora", requires=ghost["override_id"])]]
    if p.rng.random() < 0.7:
        first = p.row("K201", "t-cinder")
        fragments.append([first, p.row(requires=first["override_id"])])
    fragments.append([p.row() for _ in range(p.rng.randint(1, 2))])
    return p.spec(fragments)


def plant_q5(p: _Planter) -> dict[str, Any]:
    fragments = [
        [p.row(status="superseded", risk=p.rng.randint(3, 20), carry="risk_delta")],
        [p.row(status="superseded", records=-p.rng.randint(40, 60), carry="max_records_delta")],
        [p.row(status="superseded", window_id=p.rng.choice(("WIN-PRE", "WIN-AUTH-V099")), risk=p.rng.randint(3, 20),
               records=-p.rng.randint(20, 60), carry=p.rng.choice(("risk_delta", "max_records_delta")))],
        [p.row(records=p.rng.randint(-15, 5)) for _ in range(p.rng.randint(1, 2))],
        [p.noise(("cinder", "aurora", "pre"))],
    ]
    return p.spec(fragments)


def plant_combo(p: _Planter) -> dict[str, Any]:
    alias = p.inside_alias()
    key = alias["alias"]
    needed = p.row("K201", "t-cinder")
    first = p.row()
    reissued_by_alias = [first, p.row(key, override_id=first["override_id"])]
    early = p.row("K201", "t-cinder")
    requires_reissued = [early, p.row(requires=early["override_id"]), p.row("K201", "t-cinder", override_id=early["override_id"])]
    clip_first = p.row(timeout=p.rng.randint(100, 400))
    carry_first = p.row()
    fragments = [
        [p.row(key, requires=needed["override_id"]), needed],
        reissued_by_alias,
        [p.row(key, timeout=-p.rng.randint(700, 900)) for _ in range(2)],
        [p.row(key, status="superseded", risk=p.rng.randint(3, 20), carry="risk_delta")],
        requires_reissued,
        [clip_first, p.row(override_id=clip_first["override_id"], timeout=-p.rng.randint(700, 900))],
        [carry_first, p.row(status="superseded", override_id=carry_first["override_id"], risk=p.rng.randint(3, 20),
                            records=-p.rng.randint(20, 40), carry=p.rng.choice(("risk_delta", "max_records_delta")))],
    ]
    return p.spec(fragments, [alias])


def plain_rows(p: _Planter, risk_high: int) -> list[list[dict[str, Any]]]:
    """Rows of the resolved principal and of the witness principals, none of them on a quiet branch."""
    fragments = [[p.row() for _ in range(p.rng.randint(1, 2))]]
    for key, tenant in (("K118", TENANT), ("K077", "t-borealis"), ("K201", "t-cinder")):
        fragments.append([p.row(key, tenant, risk=p.rng.randint(0, risk_high)) for _ in range(p.rng.randint(0, 2))])
    fragments.append([p.noise(("cinder", "aurora", "pre", "superseded"))])
    return fragments


def chain(p: _Planter, key: str = PARAM_KEY, tenant: str = TENANT, sources: int = 1, tail: str | None = None,
          **reinstated: Any) -> list[dict[str, Any]]:
    """Rows of one override_id: active rows outside the effective window, a withdrawn row, a reinstated row and an optional tail."""
    first = p.row(key, tenant, window_id="WIN-PRE")
    rows = [first] + [p.row(key, tenant, window_id="WIN-PRE", override_id=first["override_id"]) for _ in range(sources - 1)]
    rows.append(p.row(key, tenant, status="withdrawn", override_id=first["override_id"]))
    rows.append(p.row(key, tenant, status="reinstated", override_id=first["override_id"], **reinstated))
    if tail == "superseded":
        rows.append(p.row(key, tenant, status="superseded", override_id=first["override_id"], risk=p.rng.randint(3, 20),
                          carry="risk_delta"))
    elif tail == "withdrawn":
        rows.append(p.row(key, tenant, status="withdrawn", override_id=first["override_id"]))
    return rows


def plant_utie(p: _Planter) -> dict[str, Any]:
    return p.spec(plain_rows(p, 3))


def plant_udecoy(p: _Planter) -> dict[str, Any]:
    return p.spec(plain_rows(p, 20))


def plant_d1(p: _Planter) -> dict[str, Any]:
    return p.spec(plain_rows(p, 20))


def plant_d2(p: _Planter) -> dict[str, Any]:
    fragments = [chain(p), chain(p, sources=2), chain(p, "K118", sources=p.rng.randint(1, 2))]
    if p.rng.random() < 0.5:
        fragments.append(chain(p, sources=p.rng.randint(1, 2)))
    fragments += [[p.row()], [p.noise(("cinder", "aurora", "pre"))]]
    return p.spec(fragments)


def plant_combo2(p: _Planter) -> dict[str, Any]:
    spec = plant_combo(p)
    alias_key = spec["aliases"][0]["alias"]
    needed = p.row("K201", "t-cinder")
    fragments = [
        spec["rows"],
        chain(p, alias_key),
        chain(p, sources=2, timeout=p.rng.randint(100, 300)),
        chain(p, "K118", tail="superseded"),
        chain(p, tail="withdrawn"),
        [chain_row for chain_row in chain(p, "K118", requires=needed["override_id"])] + [needed],
        [p.row("K118", TENANT, risk=p.rng.randint(0, 20)), p.row("K077", "t-borealis", risk=p.rng.randint(0, 20))],
        [p.row("K118", TENANT, status="superseded", risk=p.rng.randint(3, 20), carry="risk_delta")],
    ]
    for row in fragments[2][:2]:
        row["timeout_ms_delta"] = -p.rng.randint(700, 900)
    spec["rows"] = p.interleave(fragments)
    return spec


def plant_repair(p: _Planter, family: str) -> dict[str, Any]:
    """Two filler tenants whose stored controls omit cheap spare rows, among many spare rows, and one tenant with no repair."""
    rng, flags = p.rng, REPAIR_FLAGS[family]
    tenants = rng.sample([f"t-f{index:03d}" for index in range(10)], 3)

    def wide() -> int:
        return rng.choice((-1, 1)) * rng.randint(100, 900)

    def cheap(low: int = 1) -> int:
        return rng.choice((-1, 1)) * rng.randint(low, 60)

    def ledger_row(tenant: str, status: str, timeout: int, version: str | None = None, records: int | None = None,
                   **extra: Any) -> dict[str, Any]:
        return p.row(rng.choice(REPAIR_KEYS), tenant, status, window_id=rng.choice(("WIN-AUTH", "WIN-PRE")), timeout=timeout,
                     records=rng.randint(-60, 60) if records is None else records,
                     version=version or rng.choice(POST_CUTOVER_VERSIONS), **extra)

    def spare_row(tenant: str, timeout: int, **extra: Any) -> dict[str, Any]:
        return ledger_row(tenant, rng.choice(("superseded", "withdrawn")), timeout, **extra)

    fragments = plain_rows(p, 6)
    for tenant in tenants[:2]:
        units: list[list[dict[str, Any]]] = [[spare_row(tenant, wide())] for _ in range(34)]
        for _ in range(6):
            early = ledger_row(tenant, "active", wide())
            units.append([early, ledger_row(tenant, "active", wide(), override_id=early["override_id"])])
        units += [[ledger_row(tenant, "superseded", wide(), carry=rng.choice(("max_records_delta", "risk_delta")))] for _ in range(4)]
        units += [[ledger_row(tenant, "active", wide())] for _ in range(6)]
        for _ in range(3):
            source = ledger_row(tenant, "active", wide())
            units.append([source, ledger_row(tenant, "withdrawn", wide(), override_id=source["override_id"]),
                          ledger_row(tenant, "reinstated", wide(), override_id=source["override_id"])])
        units += [[spare_row(tenant, rng.choice((-1, 1)) * rng.randint(1, 3), version=rng.choice(PRE_CUTOVER_VERSIONS))] for _ in range(3)]
        units += [[spare_row(tenant, cheap())] for _ in range(3)]
        planted = [spare_row(tenant, cheap(), _cut=True) for _ in range(8)]
        units += [[row] for row in planted[4:]]
        if "unit" in flags:
            size = rng.randint(2, 60)
            planted[0]["timeout_ms_delta"], planted[1]["timeout_ms_delta"] = size, -size
            pair = planted[0]["max_records_delta"] + planted[1]["max_records_delta"]
            first = rng.randint(max(-60, pair - 60), min(60, pair + 60))
            units.append([spare_row(tenant, 1, version=rng.choice(PRE_CUTOVER_VERSIONS), records=first)])
            units.append([spare_row(tenant, -1, version=rng.choice(PRE_CUTOVER_VERSIONS), records=pair - first)])
        if "spare" in flags:
            early = planted[0] if "unit" not in flags else planted[4]
            units = [unit for unit in units if not (len(unit) == 1 and unit[0] is early)]
            early.update(status="active")
            units.append([early, ledger_row(tenant, "active", wide(), override_id=early["override_id"])])
            twin = ledger_row(tenant, "superseded", planted[2]["timeout_ms_delta"], records=planted[2]["max_records_delta"],
                              carry=rng.choice(("max_records_delta", "risk_delta")))
            source = ledger_row(tenant, "active", planted[3]["timeout_ms_delta"], records=planted[3]["max_records_delta"])
            units.append([twin, planted[2]])
            units.append([source, ledger_row(tenant, "withdrawn", wide(), override_id=source["override_id"]),
                          ledger_row(tenant, "reinstated", wide(), override_id=source["override_id"]), planted[3]])
            early_second = planted[1] if "unit" not in flags else None
            if early_second is not None:
                early_second.update(status="active")
                units.append([early_second, ledger_row(tenant, "active", wide(), override_id=early_second["override_id"])])
        for row in planted[:4]:
            if not any(row is item for unit in units for item in unit):
                units.append([row])
        if "tie" in flags:
            source = planted[4 + rng.randrange(4)]
            units.append([spare_row(tenant, source["timeout_ms_delta"], records=source["max_records_delta"])])
        rng.shuffle(units)
        fragments.append([row for unit in units for row in unit])
    null_rows = [spare_row(tenants[2], wide()) for _ in range(6)]
    for row in null_rows[:2]:
        row["_cut"] = True
    fragments.append(null_rows)
    spec = p.spec(fragments)
    spec["skew"] = {tenants[2]: 1}
    return spec


def repair_accepted(family: str, spec: dict[str, Any]) -> bool:
    files, rows, stored = build_from_spec(family, spec)
    check_bounds(spec, rows)
    for row in rows:
        assert -60 <= int(row["max_records_delta"]) <= 60 and -900 <= int(row["timeout_ms_delta"]) <= 900, row
    truth = repair_document(files, rows, stored)
    if "slow" in truth.values() or sum(isinstance(value, list) and len(value) > 0 for value in truth.values()) < 2:
        return False
    if sum(value is None for value in truth.values()) < 1:
        return False
    own = REPAIR_READINGS[family]
    if not all(repair_document(files, rows, stored, frozenset({reading}), 60000) != truth for reading in own):
        return False
    return all(repair_document(files, rows, stored, frozenset({reading}), 60000) == truth
               for reading in REPAIR_QUIET if reading not in own)


PLANTERS = {"q1": plant_q1, "q2": plant_q2, "q3": plant_q3, "q4": plant_q4, "q5": plant_q5, "combo": plant_combo,
            "utie": plant_utie, "udecoy": plant_udecoy, "d1": plant_d1, "d2": plant_d2, "combo2": plant_combo2}
PLANTERS.update({family: (lambda p, family=family: plant_repair(p, family)) for family in REPAIR_FAMILIES})
FIRE_KEY = {"utie": "u", "udecoy": "u", "d1": "d1", "d2": "d2"}


def attach_reports(family: str, spec: dict[str, Any], rng: random.Random, tie: bool = False) -> bool:
    """Add the curve reports and resets of a reporting family; False when this draw cannot hold them."""
    amounts = evaluate(*build_from_spec(family, spec))[1]["amounts"]

    def report(role: str, divisor: int) -> dict[str, Any]:
        return {"kind": "curve", "role": role, "converged": converge(WITNESS[role][3], amounts[role], divisor)[-1]}

    def fits(entries: list[dict[str, Any]]) -> list[int]:
        return [trial for trial in DIVISORS if all(report(entry["role"], trial)["converged"] == entry["converged"] for entry in entries)]

    roles = [role for role in WITNESS if role != "operator"]
    if family == "utie":
        reported = rng.choice(DIVISORS)
        standing = [report(role, reported) for role in rng.sample(roles, rng.randint(2, 3))]
        if len(fits(standing)) < 2:
            return False
        withdrawn: list[dict[str, Any]] = []
    elif tie:
        ties = [[report(first, trial), report(second, trial)] for first in roles for second in roles if first <= second
                for trial in DIVISORS]
        ties = [entries for entries in ties if len(fits(entries)) >= 2]
        if not ties:
            return False
        standing = rng.choice(ties)
        movers = [report(role, trial) for role in roles for trial in DIVISORS]
        movers = [entry for entry in movers if len(fits(standing + [entry])) == 1]
        if not movers:
            return False
        first = rng.choice(movers)
        second = [entry for entry in movers if fits(standing + [first, entry]) == fits(standing + [first])]
        withdrawn = [first, rng.choice(second)]
    else:
        truth = 10 if family == "d1" else rng.choice([trial for trial in DIVISORS if trial not in (6, 10)])
        standing = [report(role, truth) for role in rng.sample(roles, 3)]
        if fits(standing) != [truth] or (family != "d1" and min(fits(standing[:1])) >= truth):
            return False
        if family == "d1" and min(fits(standing[:1])) != truth:
            return False
        withdrawn = []
        if family in ("d1", "combo2"):
            for _ in range(2):
                old = report(rng.choice(roles), rng.choice([trial for trial in DIVISORS if trial != truth]))
                if truth in fits([old]):
                    return False
                withdrawn.append(old)
    places = sorted(rng.sample(range(len(spec["rows"]) + 1), len(withdrawn) + len(standing) + (2 if withdrawn else 0)))
    entries = []
    if withdrawn:
        entries = [withdrawn[0], {"kind": "reset"}, withdrawn[1], {"kind": "reset"}]
    entries += standing
    spec["reports"] = [dict(entry, at=at) for entry, at in zip(entries, places)]
    return True


def check_bounds(spec: dict[str, Any], rows: list[dict[str, Any]]) -> None:
    """Every generated value lies inside the ranges and forms the reference data states."""
    ids = {row["override_id"] for row in rows}
    last_seq = {row["override_id"]: int(row["seq"]) for row in sorted(rows, key=lambda row: int(row["seq"]))}
    for row in rows:
        if row.get("version") != EFFECTIVE_VERSION:
            continue
        assert -60 <= row["max_records_delta"] <= 60 and 0 <= row["retry_limit_delta"] <= 3, row
        assert 0 <= row["risk_delta"] <= 20 and 100 <= abs(row["timeout_ms_delta"]) <= 900 and row["rev"] == 2, row
        assert row["status"] in ("active", "superseded", "withdrawn", "reinstated"), row
        if row["status"] == "reinstated":
            assert any(item["override_id"] == row["override_id"] and item["status"] == "active" and int(item["seq"]) < int(row["seq"])
                       for item in rows), row
        if "carry" in row:
            assert row["status"] == "superseded" and row["carry"] in ("max_records_delta", "risk_delta"), row
            assert int(row["seq"]) == last_seq[row["override_id"]] and "requires" not in row, row
        if "requires" in row:
            assert row["status"] in ("active", "reinstated") and row["requires"] in ids and row["requires"] != row["override_id"], row
    assert all(1 <= value <= 6 for value in spec["allowance"].values()), spec["allowance"]
    for entry in spec.get("aliases", []):
        assert entry["start"] < entry["end"] and entry["principal"] == PARAM_KEY, entry
    for entry in spec.get("reports", []):
        assert entry["kind"] in ("curve", "reset") and 0 <= entry["at"] <= len(rows), entry
        assert entry["kind"] == "reset" or (entry["role"] in WITNESS and type(entry["converged"]) is int), entry


def accepted(family: str, spec: dict[str, Any]) -> bool:
    if family in REPAIR_FAMILIES:
        return repair_accepted(family, spec)
    files, rows, stored = build_from_spec(family, spec)
    check_bounds(spec, rows)
    docs, fires = evaluate(files, rows, stored)
    if family == "combo":
        if any(fires[quiet] < 2 for quiet in QUIET):
            return False
        return all(evaluate(files, rows, stored, frozenset({READINGS[quiet][0]}))[0] != docs for quiet in QUIET)
    others = {reading for family_readings in READINGS.values() for reading in family_readings}
    if family == "combo2":
        if any(fires[key] < 2 for key in (*QUIET, "u", "d1", "d2")):
            return False
        if not all(evaluate(files, rows, stored, frozenset({READINGS[name][0]}))[0] != docs for name in (*QUIET, *STATEFUL)):
            return False
        if fires["divisor"] is None and evaluate(files, rows, stored, frozenset({"u-firstfit"}))[0] == docs:
            return False
        moved = [quiet for quiet in ("q2", "q3", "q4", "q5")
                 if evaluate(files, rows, stored, frozenset({READINGS[quiet][0]}))[1]["divisor"] != fires["divisor"]]
        return len(moved) >= (1 if fires["divisor"] is None else 2)
    if family in STATEFUL:
        if fires[FIRE_KEY[family]] < 2 or any(fires[quiet] for quiet in QUIET):
            return False
        own = READINGS[family]
        if not all(evaluate(files, rows, stored, frozenset({reading}))[0] != docs for reading in own):
            return False
        return all(evaluate(files, rows, stored, frozenset({reading}))[0] == docs for reading in sorted(others - set(own)))
    if fires[family] < 2 or any(fires[quiet] for quiet in QUIET if quiet != family):
        return False
    return all(evaluate(files, rows, stored, frozenset({reading}))[0] != docs for reading in READINGS[family])


def generate_spec(family: str, seed: int) -> dict[str, Any]:
    """A corpus spec from the family's own random stream: the first draw that fires its rules and tells their readings apart."""
    rng = random.Random(f"sentinel-{family}-{seed}")
    shipped = json.loads(corpus_files()["override_deltas.json"])["overrides"]
    keys = {row["param_key"] for row in shipped} | {"K042", "K077", "K118", "K201", "K301"}
    ids = {row["override_id"] for row in shipped}
    for _ in range(600):
        spec = PLANTERS[family](_Planter(rng, keys, ids))
        if family in ("q2", "q4"):
            north = evaluate(*build_from_spec(family, spec))[1]["north"]
            spec["allowance"]["r-north"] = max(1, north)
        if family in ("utie", "udecoy", "d1", "combo2") and not attach_reports(family, spec, rng, family == "combo2" and seed == 2):
            continue
        if accepted(family, spec):
            return spec
    raise AssertionError(f"no {family} corpus fits seed {seed}")


def write_corpus(name: str) -> Path:
    files, _, _ = build_variant(name)
    corpus = Path(tempfile.mkdtemp(prefix=f"sentinel-{name}-"))
    for filename, payload in files.items():
        (corpus / filename).write_bytes(payload)
    _grant_read(corpus)
    return corpus


def run_resolve(name: str, corpus: Path | None = None) -> dict[str, bytes]:
    if corpus is None:
        corpus = write_corpus(name)
    out = writable_dir("sentinel-resolve-")
    result = run_repaired_cli("resolve", "--data-dir", str(corpus), "--out", str(out))
    assert result.returncode == 0, f"resolve exited {result.returncode} on corpus {name}: {(result.stderr or result.stdout)[-300:]}"
    documents: dict[str, bytes] = {}
    for doc in RESOLVE_DOCS:
        path = out / doc
        assert path.is_file() and not path.is_symlink(), f"resolve wrote no regular {doc} for corpus {name}"
        assert path.stat().st_size <= MAX_MEMBER_BYTES, f"{doc} is oversized for corpus {name}"
        documents[doc] = path.read_bytes()
    path = out / REPAIR_DOC
    if path.is_file() and not path.is_symlink() and path.stat().st_size <= MAX_MEMBER_BYTES:
        documents[REPAIR_DOC] = path.read_bytes()
    return documents


def resolved(name: str) -> dict[str, bytes]:
    if name not in _RESOLVED:
        _RESOLVED[name] = run_resolve(name)
    return _RESOLVED[name]


def resolved_document(name: str, doc: str) -> Any:
    try:
        return json.loads(resolved(name)[doc])
    except json.JSONDecodeError as error:
        raise AssertionError(f"{doc} from corpus {name} is not JSON: {error}") from error


def cli_value(text: str) -> Any:
    if re.fullmatch(r"-?[0-9]+", text):
        return int(text)
    if text in ("true", "false"):
        return text == "true"
    return text


def json_keys(node: Any):
    if isinstance(node, dict):
        for key, value in node.items():
            yield key
            yield from json_keys(value)
    elif isinstance(node, list):
        for value in node:
            yield from json_keys(value)


def json_values(node: Any):
    if isinstance(node, dict):
        for value in node.values():
            yield from json_values(value)
    elif isinstance(node, list):
        for value in node:
            yield from json_values(value)
    else:
        yield node


def is_policy_constant(value: Any) -> bool:
    if type(value) is int:
        return value in POLICY_CONSTANTS
    if isinstance(value, str):
        return any(re.search(rf"(?<![0-9]){number}(?![0-9])", value) for number in POLICY_CONSTANTS)
    return False


def embedded_policy_constants() -> list[Any]:
    tree = ast.parse(tool_path().read_text(encoding="utf-8", errors="replace"))
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
                docstrings.add(id(first.value))
    found = [node.value for node in ast.walk(tree)
             if isinstance(node, ast.Constant) and id(node) not in docstrings and is_policy_constant(node.value)]
    if schema_path().exists():
        found.extend(value for value in json_values(load_json(schema_path())) if is_policy_constant(value))
    return found


def assert_canonical(raw: bytes, label: str) -> None:
    text = raw.decode("utf-8")
    data = json.loads(text)
    assert isinstance(data, dict) and data, f"{label} is not a non-empty object"
    assert text.endswith("\n"), f"{label} has no trailing newline"
    lines = text.splitlines()
    assert len(lines) > 1, f"{label} has no fixed indent"
    indent = len(lines[1]) - len(lines[1].lstrip(" "))
    assert 1 <= indent <= 8, f"{label} has no fixed indent"
    assert text == json.dumps(data, sort_keys=True, indent=indent) + "\n", f"{label} is not serialized with sorted keys and one indent"


def rebuild_config(name: str) -> Path:
    """Build a config through the delivered init and set from the authoritative policy values of corpus name."""
    policy = reference_documents(name)["policy_resolved.json"]
    work = writable_dir("sentinel-rebuild-")
    target = work / "config.json"
    steps = [("init", "--schema", str(schema_path()), "--out", str(target))]
    for key in ("max_records", "retry_limit", "timeout_ms", "trailer"):
        steps.append(("set", "--config", str(target), "--key", key, "--value", str(policy.get(key))))
    for step in steps:
        result = run_repaired_cli(*step)
        assert result.returncode == 0, f"{name} {step[0]} failed while rebuilding config.json: {(result.stderr or result.stdout)[-300:]}"
    return target


def test_hidden_policy_resolved_document_matches():
    """POSITIVE: on each reseeded corpus, the policy_resolved document written by the delivered resolve equals the authoritative document."""
    for name in HIDDEN:
        assert_document(resolved_document(name, "policy_resolved.json"), reference_documents(name)["policy_resolved.json"], f"{name} policy_resolved.json")


def test_hidden_threshold_curve_document_matches():
    """POSITIVE: on each reseeded corpus, the threshold_curve document written by the delivered resolve equals the authoritative document."""
    for name in HIDDEN:
        assert_document(resolved_document(name, "threshold_curve.json"), reference_documents(name)["threshold_curve.json"], f"{name} threshold_curve.json")


def test_hidden_dependency_trace_document_matches():
    """POSITIVE: on each reseeded corpus, the dependency_trace document carries exactly its specified fields, its chain, applied overrides and ledger controls equal the authoritative document, and its resolution order consumes the boot manifest, bundle ledger, principal role index and override ledger in that order."""
    for name in HIDDEN:
        trace = resolved_document(name, "dependency_trace.json")
        assert isinstance(trace, dict), f"{name} dependency_trace.json is not an object"
        assert set(trace) == TRACE_KEYS, f"{name} dependency_trace.json keys differ: {sorted(set(trace) ^ TRACE_KEYS)}"
        graded = {key: trace[key] for key in TRACE_GRADED_KEYS}
        assert_document(graded, reference_documents(name)["dependency_trace.json"], f"{name} dependency_trace.json")
        order = trace["resolution_order"]
        assert isinstance(order, list), f"{name} dependency_trace.json resolution_order is not a list"
        names = [Path(str(item)).name for item in order]
        missing = [base for base in RESOLUTION_CHAIN if base not in names]
        assert not missing, f"{name} resolution_order misses {missing}: {names}"
        positions = [names.index(base) for base in RESOLUTION_CHAIN]
        assert positions == sorted(positions), f"{name} resolution_order lists {list(RESOLUTION_CHAIN)} out of order: {names}"


def assert_policy_and_trace(names: tuple[str, ...]) -> None:
    """The policy_resolved document and the graded dependency_trace fields other than ledger_controls of each corpus equal the authoritative ones."""
    for name in names:
        expected = reference_documents(name)
        assert_document(resolved_document(name, "policy_resolved.json"), expected["policy_resolved.json"], f"{name} policy_resolved.json")
        trace = resolved_document(name, "dependency_trace.json")
        assert isinstance(trace, dict), f"{name} dependency_trace.json is not an object"
        graded = {key: trace.get(key) for key in TRACE_GRADED_KEYS if key != "ledger_controls"}
        wanted = {key: value for key, value in expected["dependency_trace.json"].items() if key != "ledger_controls"}
        assert_document(graded, wanted, f"{name} dependency_trace.json")


def test_hidden_region_allowance_hard():
    """POSITIVE: on corpora where rows of another tenant of the same region, or of another region, pass selection before overrides of the resolved principal, the policy and graded trace equal the authoritative ones."""
    assert_policy_and_trace(REGION_CORPORA)


def test_hidden_unit_cutover_hard():
    """POSITIVE: on corpora whose applied overrides carry a rev that does not follow the timeout unit cutover, and on one whose cutover is moved, the policy and graded trace equal the authoritative ones."""
    assert_policy_and_trace(CUTOVER_CORPORA)


def test_hidden_window_admit_hard():
    """POSITIVE: on corpora where earlier passing rows use up the admit count of a window holding an override of the resolved principal, the policy and graded trace equal the authoritative ones."""
    assert_policy_and_trace(ADMIT_CORPORA)


def test_hidden_timeout_pool_hard():
    """POSITIVE: on corpora where the applied rows of one window, of more than one tenant, carry more timeout delta than its timeout_pool, the policy and graded trace equal the authoritative ones."""
    assert_policy_and_trace(POOL_CORPORA)


def assert_full_documents(names: tuple[str, ...]) -> None:
    """The policy_resolved and threshold_curve documents and the graded dependency_trace fields of each corpus equal the authoritative ones."""
    for name in names:
        expected = reference_documents(name)
        assert_document(resolved_document(name, "policy_resolved.json"), expected["policy_resolved.json"], f"{name} policy_resolved.json")
        assert_document(resolved_document(name, "threshold_curve.json"), expected["threshold_curve.json"], f"{name} threshold_curve.json")
        trace = resolved_document(name, "dependency_trace.json")
        assert isinstance(trace, dict), f"{name} dependency_trace.json is not an object"
        assert set(trace) == TRACE_KEYS, f"{name} dependency_trace.json keys differ: {sorted(set(trace) ^ TRACE_KEYS)}"
        graded = {key: trace[key] for key in TRACE_GRADED_KEYS}
        assert_document(graded, expected["dependency_trace.json"], f"{name} dependency_trace.json")


def test_hidden_running_timeout_floor_hard():
    """POSITIVE: on corpora whose applied overrides of the resolved principal take the running timeout below its floor, the three documents equal the authoritative ones."""
    assert_full_documents(OWNED["q1"])


def test_hidden_reissued_override_hard():
    """POSITIVE: on corpora where an override_id is stored on more than one row, the three documents equal the authoritative ones."""
    assert_full_documents(OWNED["q2"])


def test_hidden_principal_alias_span_hard():
    """POSITIVE: on corpora whose override ledger lists principal aliases with spans inside and outside the effective instant, the three documents equal the authoritative ones."""
    assert_full_documents(OWNED["q3"])


def test_hidden_requires_order_hard():
    """POSITIVE: on corpora whose rows name a required override that is refused, never drawn, or drawn at a higher seq, the three documents equal the authoritative ones."""
    assert_full_documents(OWNED["q4"])


def test_hidden_superseded_carry_hard():
    """POSITIVE: on corpora whose superseded rows carry one delta, inside and outside a matching window, the three documents equal the authoritative ones."""
    assert_full_documents(OWNED["q5"])


def test_hidden_rare_rule_pairs_hard():
    """POSITIVE: on corpora where single rows combine a principal alias, a reissued override_id, a requires field, a carried delta or a running timeout floor, the three documents equal the authoritative ones."""
    assert_full_documents(COMBO_CORPORA)


def test_hidden_unique_divisor_fit_hard():
    """POSITIVE: on corpora whose standing curve reports fix one divisor other than iteration_divisor, or fix none, the three documents equal the authoritative ones."""
    assert_full_documents(UNIQUE_FIT_CORPORA)


def test_hidden_curve_reset_hard():
    """POSITIVE: on corpora whose curve reports are withdrawn by later resets, the three documents equal the authoritative ones."""
    assert_full_documents(OWNED["d1"])


def test_hidden_reinstated_chain_hard():
    """POSITIVE: on corpora whose override_ids run through active, withdrawn and reinstated rows, the three documents equal the authoritative ones."""
    assert_full_documents(OWNED["d2"])


def test_hidden_rare_state_pairs_hard():
    """POSITIVE: on corpora where curve reports, resets and reinstated rows meet aliases, reissues, requires, carries and the timeout floor on the same records, the three documents equal the authoritative ones."""
    assert_full_documents(COMBO2_CORPORA)


def test_hidden_fresh_state_corpora_hard():
    """POSITIVE: on further corpora of the same kinds as the floor, reissue, alias, requires, carry, divisor, reset and reinstated corpora, the three documents equal the authoritative ones."""
    assert_full_documents(tuple(name for name in VARIANTS if name.startswith("fresh-")))


def written_repair(name: str) -> dict[str, Any]:
    raw = resolved(name).get(REPAIR_DOC)
    assert raw is not None, f"resolve wrote no regular {REPAIR_DOC} for corpus {name}"
    try:
        document = json.loads(raw)
    except json.JSONDecodeError as error:
        raise AssertionError(f"{REPAIR_DOC} from corpus {name} is not JSON: {error}") from error
    assert isinstance(document, dict), f"{REPAIR_DOC} from corpus {name} is not an object"
    return document


def test_hidden_ledger_repair_reconciles_hard():
    """POSITIVE: on corpora whose stored controls omit spare rows of some tenants, ledger_repair is keyed by the mismatched tenants, is null exactly where no repair exists, and every listed set is distinct spare rows of its tenant whose removal reconciles its controls."""
    for name in REPAIR_FEASIBLE_CORPORA:
        files, rows, stored = build_variant(name)
        want, got = repair_document(files, rows, stored), written_repair(name)
        assert sorted(got) == sorted(want), f"{name} {REPAIR_DOC} keys {sorted(got)} differ from the mismatched tenants {sorted(want)}"
        delta_ms, recomputed, spare = unit_reader(files), ledger_controls(files, rows), spare_seqs(rows)
        for tenant, value in want.items():
            listed = got[tenant]
            if value is None:
                assert listed is None, f"{name} {REPAIR_DOC} {tenant} lists {listed} where no repair exists"
                continue
            assert isinstance(listed, list) and all(type(seq) is int for seq in listed), f"{name} {REPAIR_DOC} {tenant} is not a list of seq values"
            assert len(set(listed)) == len(listed), f"{name} {REPAIR_DOC} {tenant} repeats a seq"
            mine = {int(row["seq"]): row for row in rows if row["tenant"] == tenant and int(row["seq"]) in spare}
            assert all(seq in mine for seq in listed), f"{name} {REPAIR_DOC} {tenant} lists a row that is not a spare row of the tenant"
            left = {
                "max_records_delta_sum": recomputed[tenant]["max_records_delta_sum"] - sum(int(mine[seq]["max_records_delta"]) for seq in listed),
                "rows": recomputed[tenant]["rows"] - len(listed),
                "timeout_ms_delta_sum_ms": recomputed[tenant]["timeout_ms_delta_sum_ms"] - sum(delta_ms(mine[seq]) for seq in listed),
            }
            assert left == stored[tenant], f"{name} {REPAIR_DOC} {tenant} removal leaves {left}, controls hold {stored[tenant]}"


def assert_repair_documents(names: tuple[str, ...]) -> None:
    for name in names:
        assert_document(written_repair(name), reference_repair(name), f"{name} {REPAIR_DOC}")


def test_hidden_ledger_repair_cheapest_hard():
    """POSITIVE: on corpora where many sets of spare rows reconcile a tenant's controls, the ledger_repair document equals the authoritative one."""
    assert_repair_documents(REPAIR_CORPORA["rbig"])


def test_hidden_ledger_repair_tie_hard():
    """POSITIVE: on corpora where two sets of spare rows reconcile a tenant's controls at the same total, the ledger_repair document equals the authoritative one."""
    assert_repair_documents(REPAIR_CORPORA["rtie"])


def test_hidden_ledger_repair_unit_hard():
    """POSITIVE: on corpora whose spare rows include rows stored in whole seconds, the ledger_repair document equals the authoritative one."""
    assert_repair_documents(REPAIR_CORPORA["runit"])


def test_hidden_ledger_repair_spare_hard():
    """POSITIVE: on corpora whose cheap rows include reissued, carried and reinstated-source rows, the ledger_repair document equals the authoritative one."""
    assert_repair_documents(REPAIR_CORPORA["rspare"])


def test_hidden_rare_repair_pairs_hard():
    """POSITIVE: on corpora where many sets of spare rows reconcile, two of them at the same total, some spare rows are stored in whole seconds and cheap rows include reissued, carried and reinstated-source rows, the ledger_repair document equals the authoritative one."""
    assert_repair_documents(REPAIR_CORPORA["rall"])


def test_cli_init_and_set_rebuild_config_from_authoritative_values():
    """POSITIVE: for each reseeded corpus, the delivered init and set fed the authoritative policy values write a config that is canonical JSON and equals the authoritative config."""
    for name in HIDDEN:
        want = reference_documents(name)["policy_resolved.json"]
        expected = config_doc(want["max_records"], want["retry_limit"], want["timeout_ms"])
        raw = rebuild_config(name).read_bytes()
        assert_canonical(raw, f"{name} rebuilt config.json")
        assert_document(json.loads(raw), expected, f"{name} rebuilt config.json")


def test_mutation_risk_delta_moves_only_contribution():
    """POSITIVE: mutation raising one applied risk_delta by one moves the curve contribution as the rounding rule says and leaves the policy figures unchanged."""
    expected = reference_documents("mutation-risk")
    assert_document(resolved_document("mutation-risk", "threshold_curve.json"), expected["threshold_curve.json"], "mutation-risk threshold_curve.json")
    assert_document(resolved_document("mutation-risk", "policy_resolved.json"), expected["policy_resolved.json"], "mutation-risk policy_resolved.json")


def test_mutation_allowance_cut_drops_later_override():
    """POSITIVE: mutation cutting the r-north override allowance to one changes the resolved policy to the authoritative one for that allowance."""
    expected = reference_documents("mutation-allowance")
    assert_document(resolved_document("mutation-allowance", "policy_resolved.json"), expected["policy_resolved.json"], "mutation-allowance policy_resolved.json")


def test_validate_accepts_supplied_config_and_rejects_missing_key():
    """POSITIVE: the repaired validate subcommand accepts a supplied correct config and rejects one that lacks a required key."""
    work = Path(tempfile.mkdtemp(prefix="sentinel-validate-"))
    good = work / "good.json"
    bad = work / "bad.json"
    good.write_text(json.dumps(expected_config(), sort_keys=True, indent=2) + "\n", encoding="utf-8")
    partial = expected_config()
    del partial["trailer"]
    bad.write_text(json.dumps(partial, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    _grant_read(work)
    accepted = run_repaired_cli("validate", "--schema", str(schema_path()), "--config", str(good))
    assert accepted.returncode == 0 and accepted.stdout.strip() == "ok", f"validate rejected a correct config: {(accepted.stderr or accepted.stdout)[-300:]}"
    rejected = run_repaired_cli("validate", "--schema", str(schema_path()), "--config", str(bad))
    assert rejected.returncode != 0, "validate accepted a config without trailer"


def test_hidden_resolve_rerun_is_canonical_and_byte_identical():
    """POSITIVE: the delivered resolve, run twice on one reseeded hidden-a corpus directory into two fresh output directories, writes byte-identical canonical documents both times, and the policy it writes differs from the policy of the shipped corpus."""
    corpus = write_corpus("hidden-a")
    first = run_resolve("hidden-a", corpus)
    second = run_resolve("hidden-a", corpus)
    for doc in RESOLVE_DOCS:
        assert first[doc] == second[doc], f"{doc} differs between two runs on one hidden-a corpus"
        assert_canonical(first[doc], f"hidden-a {doc}")
    policy = json.loads(first["policy_resolved.json"])
    assert policy != reference_documents("shipped")["policy_resolved.json"], "hidden-a policy_resolved.json equals the policy of the shipped corpus"


def assert_artifact_file(path: Path) -> None:
    assert path.is_file() and path.stat().st_size > 0, f"missing or empty {path}"
    assert path.stat().st_size < MAX_MEMBER_BYTES, f"oversized {path}"
    if path.suffix == ".json":
        assert_canonical(path.read_bytes(), path.name)
        found = [key for key in json_keys(load_json(path)) if key in FORBIDDEN_KEYS]
        assert not found, f"{path.name} carries dynamic keys {found}"


def test_shipped_config_carries_policy_values():
    """POSITIVE: config.json exists, is canonical JSON without dynamic keys, and equals the authoritative shipped config."""
    assert_artifact_file(CONFIG_PATH)
    assert_document(load_json(CONFIG_PATH), expected_config(), "config.json")


def test_shipped_config_produced_by_repaired_tool():
    """POSITIVE: config.json is byte-identical to the config the delivered init and set write when fed the shipped authoritative values."""
    assert rebuild_config("shipped").read_bytes() == CONFIG_PATH.read_bytes(), "config.json bytes differ from the init and set rebuild with the shipped values"


def test_shipped_profiles_carry_policy_deltas():
    """POSITIVE: profile_dev.json and profile_prod.json exist, are canonical JSON without dynamic keys, and each equals the shipped policy shifted by its profile deltas."""
    policy = reference_documents("shipped")["policy_resolved.json"]
    for name, path in (("dev", PROFILE_DEV_PATH), ("prod", PROFILE_PROD_PATH)):
        assert_artifact_file(path)
        assert_document(load_json(path), expected_profile(name, policy), path.name)


def test_shipped_report_records_tool_runs_and_digest():
    """POSITIVE: report.json is canonical JSON without dynamic keys, says ok from sentinel-ctl, lists resolve, init, set and validate runs that all returned 0, carries the sha256 of the delivered config.json and the trailer."""
    assert_artifact_file(REPORT_PATH)
    report = load_json(REPORT_PATH)
    assert report.get("ok") is True and report.get("tool") == "sentinel-ctl", "report.json ok or tool is wrong"
    commands = report.get("commands")
    assert isinstance(commands, list) and commands, "report.json has no commands"
    seen = "\n".join(" ".join(str(arg) for arg in item.get("argv", [])) for item in commands)
    for subcommand in ("resolve", "init", "set", "validate"):
        assert subcommand in seen, f"report.json commands lack a {subcommand} run"
    assert all(item.get("returncode") == 0 for item in commands), "report.json lists a failed command"
    assert report.get("config_sha256") == hashlib.sha256(CONFIG_PATH.read_bytes()).hexdigest(), "report.json digest does not match config.json"
    assert report.get("trailer") == TRAILER, "report.json trailer is wrong"


def test_shipped_validation_report_grades_policy_and_branches():
    """POSITIVE: validation_report.json is canonical JSON without dynamic keys, is ok with every artifact check true, lists the seven required artifacts and both profiles, carries the shipped policy, curve and graded trace fields, and its rejected branches name B9, legacy_override_table.ini and superseded_windows.xml."""
    assert_artifact_file(VALIDATION_REPORT_PATH)
    shipped = reference_documents("shipped")
    validation = load_json(VALIDATION_REPORT_PATH)
    checks = validation["checks"]
    assert validation["ok"] is True and checks["all_artifacts_present"] is True, "validation_report.json is not ok"
    assert checks["config_matches_policy"] is True and checks["config_scalar_flat"] is True, "validation_report.json checks are not true"
    assert checks["command_failures"] == [] and checks["required_artifacts"] == ARTIFACT_NAMES, "validation_report.json artifact checks differ"
    assert set(checks["profiles"]) == {"dev", "prod"}, "validation_report.json profiles differ"
    assert_document(validation["policy_resolved"], shipped["policy_resolved.json"], "validation_report.json policy_resolved")
    assert_document(validation["threshold_curve"], shipped["threshold_curve.json"], "validation_report.json threshold_curve")
    trace = validation["dependency_trace"]
    assert_document({key: trace.get(key) for key in TRACE_GRADED_KEYS}, shipped["dependency_trace.json"], "validation_report.json dependency_trace")
    rejected = json.dumps(trace.get("rejected_branches"))
    for name in ("B9", "legacy_override_table.ini", "superseded_windows.xml"):
        assert name in rejected, f"rejected_branches does not name {name}"


def test_shipped_summary_lists_artifacts_and_inputs():
    """POSITIVE: summary.json is canonical JSON without dynamic keys, lists the seven artifact names with their count, both profiles, the format tag and the trailer, and the sorted file names of the reference corpus as inputs with their count."""
    assert_artifact_file(SUMMARY_PATH)
    summary = load_json(SUMMARY_PATH)
    assert summary["artifact_count"] == len(ARTIFACT_NAMES) and summary["artifacts"] == ARTIFACT_NAMES, "summary.json artifacts differ"
    assert summary["profiles"] == ["dev", "prod"] and summary["format_tag"] == FORMAT_TAG and summary["trailer"] == TRAILER, "summary.json fields differ"
    corpus_names = sorted(Path(name).name for name in corpus_files() if not name.endswith("/"))
    assert summary["inputs"] == corpus_names and summary["input_count"] == len(summary["inputs"]), "summary.json inputs differ"


def test_shipped_tool_archive_is_pinned_and_repaired():
    """POSITIVE: tool.zip holds exactly README.md, cli.py and schema.json in that order, every member has the 1980-01-01 timestamp and mode 0644, and its cli.py differs from the unrepaired shipped source."""
    assert_artifact_file(TOOL_ARCHIVE)
    with zipfile.ZipFile(TOOL_ARCHIVE) as zf:
        infos = zf.infolist()
        assert [info.filename for info in infos] == ["README.md", "cli.py", "schema.json"], "tool.zip member layout differs from the shipped archive"
        for info in infos:
            assert info.date_time == (1980, 1, 1, 0, 0, 0), f"tool.zip member {info.filename} has an unpinned timestamp"
            assert (info.external_attr >> 16) & 0o777 == 0o644, f"tool.zip member {info.filename} mode is not 0644"
        assert hashlib.sha256(zf.read("cli.py")).hexdigest() != SHIPPED_CLI_SHA256, "cli.py is the unrepaired shipped source"


def test_negative_weight_hardcoded_sample_answers():
    """NEGATIVE: fires when the repaired source embeds the authoritative policy constants as literals."""
    assert embedded_policy_constants(), "honest baseline: policy is computed, not embedded"


def test_negative_weight_transcript_disagrees_with_config():
    """NEGATIVE: fires when the last recorded set of a config.json key disagrees with the delivered config."""
    config = load_json(CONFIG_PATH)
    recorded: dict[str, Any] = {}
    for item in load_json(REPORT_PATH)["commands"]:
        argv = [str(arg) for arg in item.get("argv", [])]
        if "set" not in argv or not {"--config", "--key", "--value"} <= set(argv):
            continue
        if Path(argv[argv.index("--config") + 1]).name != "config.json":
            continue
        recorded[argv[argv.index("--key") + 1]] = cli_value(argv[argv.index("--value") + 1])
    assert any(key not in config or config[key] != value for key, value in recorded.items()), "honest baseline: transcript matches the delivered config"


def test_negative_weight_url_or_secret_in_artifacts():
    """NEGATIVE: fires when a delivered JSON artifact carries a URL or a credential key."""
    text = "".join(path.read_text(encoding="utf-8", errors="ignore") for path in JSON_ARTIFACT_PATHS).lower()
    assert any(token in text for token in ("://", "api_key", "password")), "honest baseline: offline local configuration"


def third_party_imports() -> list[str]:
    roots = [tool_root()]
    sources = [(root, path) for root in roots for path in sorted(root.rglob("*.py")) if path.is_file()]
    own = {path.relative_to(root).parts[0].removesuffix(".py") for root, path in sources}
    allowed = set(sys.stdlib_module_names) | {"pyarrow"} | own
    found = []
    for _, path in sources:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names = [node.module]
            else:
                continue
            found.extend(f"{path.name}: {name}" for name in names if name.split(".")[0] not in allowed)
    return found


def test_negative_weight_third_party_import_in_tool():
    """NEGATIVE: fires when a Python file of the delivered tool imports a module outside the standard library, pyarrow and the tool itself."""
    assert third_party_imports(), "honest baseline: the tool imports only the standard library and pyarrow"


# rewardkit checks. Each one runs the test above and passes when it raises nothing;
# a failing check prints its first differing path. One lock runs the checks one at a
# time because rewardkit calls checks from parallel worker threads and every rerun
# of the delivered tool shares the unprivileged user.
_GRADE_LOCK = threading.Lock()


def test_mutation_pool_cut_reshares_timeout():
    """POSITIVE: mutation cutting the WIN-AUTH timeout_pool changes the resolved policy to the authoritative one for that pool."""
    expected = reference_documents("mutation-pool")
    assert_document(resolved_document("mutation-pool", "policy_resolved.json"), expected["policy_resolved.json"], "mutation-pool policy_resolved.json")


def _passes(name: str, test) -> bool:
    with _GRADE_LOCK:
        try:
            test()
        except Exception as error:
            print(f"[check] {name}: {type(error).__name__}: {str(error)[:400]}")
            return False
        return True


@criterion(description="on each reseeded corpus, the policy_resolved document written by the delivered resolve equals the authoritative document.")
def hidden_policy_resolved_document_matches(workspace: Path) -> bool:
    return _passes("hidden_policy_resolved_document_matches", test_hidden_policy_resolved_document_matches)


@criterion(description="on each reseeded corpus, the threshold_curve document written by the delivered resolve equals the authoritative document.")
def hidden_threshold_curve_document_matches(workspace: Path) -> bool:
    return _passes("hidden_threshold_curve_document_matches", test_hidden_threshold_curve_document_matches)


@criterion(description="on each reseeded corpus, the dependency_trace document carries exactly its specified fields, its chain, applied overrides and ledger controls equal the authoritative document, and its resolution_order lists the boot manifest, bundle ledger, principal role index and override ledger in that order.")
def hidden_dependency_trace_document_matches(workspace: Path) -> bool:
    return _passes("hidden_dependency_trace_document_matches", test_hidden_dependency_trace_document_matches)


@criterion(description="on corpora where rows of another tenant of the same region, or of another region, pass selection before overrides of the resolved principal, the policy and graded trace equal the authoritative ones.")
def hidden_region_allowance_hard(workspace: Path) -> bool:
    return _passes("hidden_region_allowance_hard", test_hidden_region_allowance_hard)


@criterion(description="on corpora whose applied overrides carry a rev that does not follow the timeout unit cutover, and on one whose cutover is moved, the policy and graded trace equal the authoritative ones.")
def hidden_unit_cutover_hard(workspace: Path) -> bool:
    return _passes("hidden_unit_cutover_hard", test_hidden_unit_cutover_hard)


@criterion(description="on corpora where earlier passing rows use up the admit count of a window holding an override of the resolved principal, the policy and graded trace equal the authoritative ones.")
def hidden_window_admit_hard(workspace: Path) -> bool:
    return _passes("hidden_window_admit_hard", test_hidden_window_admit_hard)


@criterion(description="on corpora where the applied rows of one window, of more than one tenant, carry more timeout delta than its timeout_pool, the policy and graded trace equal the authoritative ones.")
def hidden_timeout_pool_hard(workspace: Path) -> bool:
    return _passes("hidden_timeout_pool_hard", test_hidden_timeout_pool_hard)


@criterion(description="on corpora whose applied overrides of the resolved principal take the running timeout below its floor, the three documents equal the authoritative ones.")
def hidden_running_timeout_floor_hard(workspace: Path) -> bool:
    return _passes("hidden_running_timeout_floor_hard", test_hidden_running_timeout_floor_hard)


@criterion(description="on corpora where an override_id is stored on more than one row, the three documents equal the authoritative ones.")
def hidden_reissued_override_hard(workspace: Path) -> bool:
    return _passes("hidden_reissued_override_hard", test_hidden_reissued_override_hard)


@criterion(description="on corpora whose override ledger lists principal aliases with spans inside and outside the effective instant, the three documents equal the authoritative ones.")
def hidden_principal_alias_span_hard(workspace: Path) -> bool:
    return _passes("hidden_principal_alias_span_hard", test_hidden_principal_alias_span_hard)


@criterion(description="on corpora whose rows name a required override that is refused, never drawn, or drawn at a higher seq, the three documents equal the authoritative ones.")
def hidden_requires_order_hard(workspace: Path) -> bool:
    return _passes("hidden_requires_order_hard", test_hidden_requires_order_hard)


@criterion(description="on corpora whose superseded rows carry one delta, inside and outside a matching window, the three documents equal the authoritative ones.")
def hidden_superseded_carry_hard(workspace: Path) -> bool:
    return _passes("hidden_superseded_carry_hard", test_hidden_superseded_carry_hard)


@criterion(description="on corpora where single rows combine a principal alias, a reissued override_id, a requires field, a carried delta or a running timeout floor, the three documents equal the authoritative ones.")
def hidden_rare_rule_pairs_hard(workspace: Path) -> bool:
    return _passes("hidden_rare_rule_pairs_hard", test_hidden_rare_rule_pairs_hard)


@criterion(description="on corpora whose standing curve reports fix one divisor other than iteration_divisor, or fix none, the three documents equal the authoritative ones.")
def hidden_unique_divisor_fit_hard(workspace: Path) -> bool:
    return _passes("hidden_unique_divisor_fit_hard", test_hidden_unique_divisor_fit_hard)


@criterion(description="on corpora whose curve reports are withdrawn by later resets, the three documents equal the authoritative ones.")
def hidden_curve_reset_hard(workspace: Path) -> bool:
    return _passes("hidden_curve_reset_hard", test_hidden_curve_reset_hard)


@criterion(description="on corpora whose override_ids run through active, withdrawn and reinstated rows, the three documents equal the authoritative ones.")
def hidden_reinstated_chain_hard(workspace: Path) -> bool:
    return _passes("hidden_reinstated_chain_hard", test_hidden_reinstated_chain_hard)


@criterion(description="on corpora where curve reports, resets and reinstated rows meet aliases, reissues, requires, carries and the timeout floor on the same records, the three documents equal the authoritative ones.")
def hidden_rare_state_pairs_hard(workspace: Path) -> bool:
    return _passes("hidden_rare_state_pairs_hard", test_hidden_rare_state_pairs_hard)


@criterion(description="on further corpora of the same kinds as the floor, reissue, alias, requires, carry, divisor, reset and reinstated corpora, the three documents equal the authoritative ones.")
def hidden_fresh_state_corpora_hard(workspace: Path) -> bool:
    return _passes("hidden_fresh_state_corpora_hard", test_hidden_fresh_state_corpora_hard)


@criterion(description="for each reseeded corpus, the delivered init and set fed the authoritative policy values write a canonical config equal to the authoritative config.")
def cli_init_and_set_rebuild_config_from_authoritative_values(workspace: Path) -> bool:
    return _passes("cli_init_and_set_rebuild_config_from_authoritative_values", test_cli_init_and_set_rebuild_config_from_authoritative_values)


@criterion(description="mutation raising one applied risk_delta by one moves the curve contribution as the rounding rule says and leaves the policy figures unchanged.")
def mutation_risk_delta_moves_only_contribution(workspace: Path) -> bool:
    return _passes("mutation_risk_delta_moves_only_contribution", test_mutation_risk_delta_moves_only_contribution)


@criterion(description="mutation cutting the r-north override allowance to one changes the resolved policy to the authoritative one for that allowance.")
def mutation_allowance_cut_drops_later_override(workspace: Path) -> bool:
    return _passes("mutation_allowance_cut_drops_later_override", test_mutation_allowance_cut_drops_later_override)


@criterion(description="mutation cutting the WIN-AUTH timeout_pool changes the resolved policy to the authoritative one for that pool.")
def mutation_pool_cut_reshares_timeout(workspace: Path) -> bool:
    return _passes("mutation_pool_cut_reshares_timeout", test_mutation_pool_cut_reshares_timeout)


@criterion(description="the repaired validate subcommand accepts a supplied correct config and rejects one that lacks a required key.")
def validate_accepts_supplied_config_and_rejects_missing_key(workspace: Path) -> bool:
    return _passes("validate_accepts_supplied_config_and_rejects_missing_key", test_validate_accepts_supplied_config_and_rejects_missing_key)


@criterion(description="two resolve runs on the same reseeded hidden corpus write byte-identical canonical documents, and the policy they write differs from the policy of the shipped corpus.")
def hidden_resolve_rerun_is_canonical_and_byte_identical(workspace: Path) -> bool:
    return _passes("hidden_resolve_rerun_is_canonical_and_byte_identical", test_hidden_resolve_rerun_is_canonical_and_byte_identical)


@criterion(description="on corpora whose stored controls omit spare rows of some tenants, ledger_repair is keyed by the mismatched tenants, is null exactly where no repair exists, and every listed set is distinct spare rows of its tenant whose removal reconciles its controls.")
def hidden_ledger_repair_reconciles_hard(workspace: Path) -> bool:
    return _passes("hidden_ledger_repair_reconciles_hard", test_hidden_ledger_repair_reconciles_hard)


@criterion(description="on corpora where many sets of spare rows reconcile a tenant's controls, the ledger_repair document equals the authoritative one.")
def hidden_ledger_repair_cheapest_hard(workspace: Path) -> bool:
    return _passes("hidden_ledger_repair_cheapest_hard", test_hidden_ledger_repair_cheapest_hard)


@criterion(description="on corpora where two sets of spare rows reconcile a tenant's controls at the same total, the ledger_repair document equals the authoritative one.")
def hidden_ledger_repair_tie_hard(workspace: Path) -> bool:
    return _passes("hidden_ledger_repair_tie_hard", test_hidden_ledger_repair_tie_hard)


@criterion(description="on corpora whose spare rows include rows stored in whole seconds, the ledger_repair document equals the authoritative one.")
def hidden_ledger_repair_unit_hard(workspace: Path) -> bool:
    return _passes("hidden_ledger_repair_unit_hard", test_hidden_ledger_repair_unit_hard)


@criterion(description="on corpora whose cheap rows include reissued, carried and reinstated-source rows, the ledger_repair document equals the authoritative one.")
def hidden_ledger_repair_spare_hard(workspace: Path) -> bool:
    return _passes("hidden_ledger_repair_spare_hard", test_hidden_ledger_repair_spare_hard)


@criterion(description="on corpora where many sets of spare rows reconcile, two of them at the same total, some spare rows are stored in whole seconds and cheap rows include reissued, carried and reinstated-source rows, the ledger_repair document equals the authoritative one.")
def hidden_rare_repair_pairs_hard(workspace: Path) -> bool:
    return _passes("hidden_rare_repair_pairs_hard", test_hidden_rare_repair_pairs_hard)


@criterion(description="config.json is canonical JSON without dynamic keys and equals the authoritative shipped config.")
def shipped_config_carries_policy_values(workspace: Path) -> bool:
    return _passes("shipped_config_carries_policy_values", test_shipped_config_carries_policy_values)


@criterion(description="config.json is byte-identical to the config the delivered init and set write when fed the shipped authoritative values.")
def shipped_config_produced_by_repaired_tool(workspace: Path) -> bool:
    return _passes("shipped_config_produced_by_repaired_tool", test_shipped_config_produced_by_repaired_tool)


@criterion(description="profile_dev.json and profile_prod.json are canonical JSON without dynamic keys and each equals the shipped policy shifted by its profile deltas.")
def shipped_profiles_carry_policy_deltas(workspace: Path) -> bool:
    return _passes("shipped_profiles_carry_policy_deltas", test_shipped_profiles_carry_policy_deltas)


@criterion(description="validation_report.json is ok with every artifact check true, carries the shipped policy, curve and graded trace, and its rejected branches name B9, legacy_override_table.ini and superseded_windows.xml.")
def shipped_validation_report_grades_policy_and_branches(workspace: Path) -> bool:
    return _passes("shipped_validation_report_grades_policy_and_branches", test_shipped_validation_report_grades_policy_and_branches)


@criterion(description="report.json says ok from sentinel-ctl, lists resolve, init, set and validate runs that all returned 0, and carries the sha256 of the delivered config.json and the trailer.")
def shipped_report_records_tool_runs_and_digest(workspace: Path) -> bool:
    return _passes("shipped_report_records_tool_runs_and_digest", test_shipped_report_records_tool_runs_and_digest)


@criterion(description="summary.json lists the seven artifact names with their count, both profiles, the format tag, the trailer, and the sorted file names of the reference corpus as inputs with their count.")
def shipped_summary_lists_artifacts_and_inputs(workspace: Path) -> bool:
    return _passes("shipped_summary_lists_artifacts_and_inputs", test_shipped_summary_lists_artifacts_and_inputs)


@criterion(description="tool.zip holds exactly README.md, cli.py and schema.json in that order with the 1980-01-01 timestamp and mode 0644, and its cli.py differs from the unrepaired shipped source.")
def shipped_tool_archive_is_pinned_and_repaired(workspace: Path) -> bool:
    return _passes("shipped_tool_archive_is_pinned_and_repaired", test_shipped_tool_archive_is_pinned_and_repaired)


@criterion(description="fires when the repaired source embeds the authoritative policy constants as literals.")
def negative_hardcoded_sample_answers(workspace: Path) -> bool:
    # True means the cheat happened; the negative weight applies.
    return _passes("negative_hardcoded_sample_answers", test_negative_weight_hardcoded_sample_answers)


@criterion(description="fires when the last recorded set of a config.json key disagrees with the delivered config.")
def negative_transcript_disagrees_with_config(workspace: Path) -> bool:
    # True means the cheat happened; the negative weight applies.
    return _passes("negative_transcript_disagrees_with_config", test_negative_weight_transcript_disagrees_with_config)


@criterion(description="fires when a delivered JSON artifact carries a URL or a credential key.")
def negative_url_or_secret_in_artifacts(workspace: Path) -> bool:
    # True means the cheat happened; the negative weight applies.
    return _passes("negative_url_or_secret_in_artifacts", test_negative_weight_url_or_secret_in_artifacts)


@criterion(description="fires when a Python file of the delivered tool imports a module outside the standard library, pyarrow and the tool itself.")
def negative_third_party_import_in_tool(workspace: Path) -> bool:
    # True means the cheat happened; the negative weight applies.
    return _passes("negative_third_party_import_in_tool", test_negative_weight_third_party_import_in_tool)


criteria.hidden_region_allowance_hard(weight=5)
criteria.hidden_unit_cutover_hard(weight=5)
criteria.hidden_window_admit_hard(weight=5)
criteria.hidden_timeout_pool_hard(weight=5)
criteria.hidden_running_timeout_floor_hard(weight=5)
criteria.hidden_reissued_override_hard(weight=5)
criteria.hidden_principal_alias_span_hard(weight=5)
criteria.hidden_requires_order_hard(weight=5)
criteria.hidden_superseded_carry_hard(weight=5)
criteria.hidden_rare_rule_pairs_hard(weight=3)
criteria.hidden_unique_divisor_fit_hard(weight=5)
criteria.hidden_curve_reset_hard(weight=5)
criteria.hidden_reinstated_chain_hard(weight=5)
criteria.hidden_rare_state_pairs_hard(weight=3)
criteria.hidden_fresh_state_corpora_hard(weight=5)
criteria.hidden_ledger_repair_reconciles_hard(weight=5)
criteria.hidden_ledger_repair_cheapest_hard(weight=5)
criteria.hidden_ledger_repair_tie_hard(weight=5)
criteria.hidden_ledger_repair_unit_hard(weight=5)
criteria.hidden_ledger_repair_spare_hard(weight=5)
criteria.hidden_rare_repair_pairs_hard(weight=3)
criteria.hidden_policy_resolved_document_matches(weight=5)
criteria.hidden_threshold_curve_document_matches(weight=5)
criteria.hidden_dependency_trace_document_matches(weight=5)
criteria.cli_init_and_set_rebuild_config_from_authoritative_values(weight=3)
criteria.mutation_risk_delta_moves_only_contribution(weight=3)
criteria.mutation_allowance_cut_drops_later_override(weight=3)
criteria.mutation_pool_cut_reshares_timeout(weight=3)
criteria.validate_accepts_supplied_config_and_rejects_missing_key(weight=3)
criteria.hidden_resolve_rerun_is_canonical_and_byte_identical(weight=1)
criteria.shipped_config_carries_policy_values(weight=3)
criteria.shipped_config_produced_by_repaired_tool(weight=1)
criteria.shipped_profiles_carry_policy_deltas(weight=3)
criteria.shipped_validation_report_grades_policy_and_branches(weight=3)
criteria.shipped_report_records_tool_runs_and_digest(weight=3)
criteria.shipped_summary_lists_artifacts_and_inputs(weight=3)
criteria.shipped_tool_archive_is_pinned_and_repaired(weight=1)
criteria.negative_hardcoded_sample_answers(weight=-5)
criteria.negative_transcript_disagrees_with_config(weight=-3)
criteria.negative_url_or_secret_in_artifacts(weight=-3)
criteria.negative_third_party_import_in_tool(weight=-3)


# Embedded copy of environment/data (a deterministic zip, base64), unpacked for the resolve reruns.
REFERENCE_CORPUS_B64 = "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"
