"""Verifier for the sentinel-policy-recompute task.

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
    """POSITIVE: for each reseeded corpus, the delivered init and set fed the authoritative policy values write a config that is canonical JSON and equals the authoritative config, and the same init and set fed the authoritative shipped values reproduce the delivered config.json byte for byte."""
    for name in HIDDEN:
        want = reference_documents(name)["policy_resolved.json"]
        expected = config_doc(want["max_records"], want["retry_limit"], want["timeout_ms"])
        raw = rebuild_config(name).read_bytes()
        assert_canonical(raw, f"{name} rebuilt config.json")
        assert_document(json.loads(raw), expected, f"{name} rebuilt config.json")
    assert rebuild_config("shipped").read_bytes() == CONFIG_PATH.read_bytes(), "config.json bytes differ from the init and set rebuild with the shipped values"


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


def test_shipped_config_and_profiles_carry_policy_values():
    """POSITIVE: config.json, profile_dev.json and profile_prod.json exist, are canonical JSON without dynamic keys, config.json equals the authoritative shipped config and each profile equals the shipped policy shifted by its profile deltas."""
    for path in (CONFIG_PATH, PROFILE_DEV_PATH, PROFILE_PROD_PATH):
        assert_artifact_file(path)
    assert_document(load_json(CONFIG_PATH), expected_config(), "config.json")
    policy = reference_documents("shipped")["policy_resolved.json"]
    for name, path in (("dev", PROFILE_DEV_PATH), ("prod", PROFILE_PROD_PATH)):
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
    """POSITIVE: summary.json is canonical JSON without dynamic keys, lists the seven artifact names with their count, both profiles, the format tag and the trailer, and a sorted input list of at least 50 names whose count matches."""
    assert_artifact_file(SUMMARY_PATH)
    summary = load_json(SUMMARY_PATH)
    assert summary["artifact_count"] == len(ARTIFACT_NAMES) and summary["artifacts"] == ARTIFACT_NAMES, "summary.json artifacts differ"
    assert summary["profiles"] == ["dev", "prod"] and summary["format_tag"] == FORMAT_TAG and summary["trailer"] == TRAILER, "summary.json fields differ"
    assert summary["inputs"] == sorted(summary["inputs"]) and summary["input_count"] == len(summary["inputs"]) >= 50, "summary.json inputs differ"


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


@criterion(description="for each reseeded corpus, the delivered init and set fed the authoritative policy values write a canonical config equal to the authoritative config, and fed the shipped values they reproduce the delivered config.json byte for byte.")
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


SHIPPED_CHECKS = (
    test_shipped_config_and_profiles_carry_policy_values,
    test_shipped_report_records_tool_runs_and_digest,
    test_shipped_validation_report_grades_policy_and_branches,
    test_shipped_summary_lists_artifacts_and_inputs,
    test_shipped_tool_archive_is_pinned_and_repaired,
)


def test_shipped_artifacts_carry_policy_runs_and_archive():
    """POSITIVE: the shipped config, profiles, report, validation report, summary and tool archive each meet their check above."""
    for check in SHIPPED_CHECKS:
        check()


@criterion(description="the shipped config and profiles carry the policy values, report.json records the tool runs and the config digest, validation_report.json grades the policy and rejected branches, summary.json lists the artifacts and inputs, and tool.zip is pinned and repaired.")
def shipped_artifacts_carry_policy_runs_and_archive(workspace: Path) -> bool:
    return _passes("shipped_artifacts_carry_policy_runs_and_archive", test_shipped_artifacts_carry_policy_runs_and_archive)


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
criteria.shipped_artifacts_carry_policy_runs_and_archive(weight=1)
criteria.negative_hardcoded_sample_answers(weight=-5)
criteria.negative_transcript_disagrees_with_config(weight=-3)
criteria.negative_url_or_secret_in_artifacts(weight=-3)


# Embedded copy of environment/data (a deterministic zip, base64), unpacked for the resolve reruns.
REFERENCE_CORPUS_B64 = "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"
