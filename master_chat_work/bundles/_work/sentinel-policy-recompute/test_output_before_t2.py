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
}
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
        stored = ledger_controls(files, rows)
        if "corrupt" in spec:
            stored[spec["corrupt"]]["rows"] += 1
        document: dict[str, Any] = {"conventions": ledger["conventions"]}
        if spec.get("aliases"):
            document["param_key_aliases"] = [{key: entry[key] for key in sorted(entry)} for entry in spec["aliases"]]
        document["overrides"] = [{key: row[key] for key in sorted(row)} for row in rows]
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


def evaluate(files: dict[str, bytes], rows: list[dict[str, Any]], stored: dict[str, Any],
             readings: frozenset[str] = frozenset()) -> tuple[dict[str, Any], dict[str, int]]:
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

    def draw(requires: str, named: frozenset[str] = frozenset()) -> tuple[list[dict[str, Any]], int]:
        region_left, admit_left = dict(allowance), dict(admits)
        drawn: list[dict[str, Any]] = []
        refused = 0
        for row in ordered:
            if row["status"] != "active" or not in_window(row):
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
        if row["status"] == "superseded" and row.get("carry") and principal_of(row) == PARAM_KEY
        and ("q5-any" in readings or in_window(row))
    ]
    fires["q5"] = len(carried)
    added = pooled_deltas(files, drawn, delta_ms)
    applied = [row for row in drawn if principal_of(row) == PARAM_KEY]
    records = [int(row["max_records_delta"]) for row in applied]
    records += [int(row["max_records_delta"]) for row in carried if row["carry"] == "max_records_delta"]
    risks = [int(row["risk_delta"]) for row in applied]
    risks += [int(row["risk_delta"]) for row in carried if row["carry"] == "risk_delta"]
    max_records = min(MAX_RECORDS_CAP, scaled(BASE_MAX_RECORDS + sum(records)))
    retry_limit = BASE_RETRY_LIMIT + sum(int(row["retry_limit_delta"]) for row in applied)
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
    iterations = [BASE_THRESHOLD]
    for _ in range(MAX_ITERATIONS):
        following = BASE_THRESHOLD + (contribution + iterations[-1]) // ITERATION_DIVISOR
        settled = abs(following - iterations[-1]) <= CONVERGENCE_EPSILON
        iterations.append(following)
        if settled:
            break
    policy = config_doc(max_records, retry_limit, timeout_ms)
    policy.update({
        "effective_version": EFFECTIVE_VERSION, "param_key": PARAM_KEY,
        "risk_threshold": iterations[-1], "tenant": TENANT,
    })
    curve = {
        "base_threshold": BASE_THRESHOLD, "contribution": contribution, "converged": iterations[-1],
        "iterations": iterations, "tier": TIER,
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


PLANTERS = {"q1": plant_q1, "q2": plant_q2, "q3": plant_q3, "q4": plant_q4, "q5": plant_q5, "combo": plant_combo}


def check_bounds(spec: dict[str, Any], rows: list[dict[str, Any]]) -> None:
    """Every generated value lies inside the ranges and forms the reference data states."""
    ids = {row["override_id"] for row in rows}
    last_seq = {row["override_id"]: int(row["seq"]) for row in sorted(rows, key=lambda row: int(row["seq"]))}
    for row in rows:
        if row.get("version") != EFFECTIVE_VERSION:
            continue
        assert -60 <= row["max_records_delta"] <= 60 and 0 <= row["retry_limit_delta"] <= 3, row
        assert 0 <= row["risk_delta"] <= 20 and 100 <= abs(row["timeout_ms_delta"]) <= 900 and row["rev"] == 2, row
        assert row["status"] in ("active", "superseded"), row
        if "carry" in row:
            assert row["status"] == "superseded" and row["carry"] in ("max_records_delta", "risk_delta"), row
            assert int(row["seq"]) == last_seq[row["override_id"]] and "requires" not in row, row
        if "requires" in row:
            assert row["status"] == "active" and row["requires"] in ids and row["requires"] != row["override_id"], row
    assert all(1 <= value <= 6 for value in spec["allowance"].values()), spec["allowance"]
    for entry in spec.get("aliases", []):
        assert entry["start"] < entry["end"] and entry["principal"] == PARAM_KEY, entry


def accepted(family: str, spec: dict[str, Any]) -> bool:
    files, rows, stored = build_from_spec(family, spec)
    check_bounds(spec, rows)
    docs, fires = evaluate(files, rows, stored)
    if family == "combo":
        if any(fires[quiet] < 2 for quiet in QUIET):
            return False
        return all(evaluate(files, rows, stored, frozenset({READINGS[quiet][0]}))[0] != docs for quiet in QUIET)
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
