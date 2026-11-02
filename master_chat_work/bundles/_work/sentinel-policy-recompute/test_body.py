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
