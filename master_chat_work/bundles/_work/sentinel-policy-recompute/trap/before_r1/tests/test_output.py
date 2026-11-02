"""Verifier for the sentinel-policy-recompute task.

This verifier reads the delivered artifacts under /app/out and never reads /app/data.
It extracts the delivered tool.zip and reruns its resolve subcommand, unprivileged,
on corpora it builds itself: an embedded copy of the reference data, fresh corpora
whose override ledger and allowances are reseeded inside the value ranges the data
states, and copies with one governed input changed. The authoritative policy of
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

# Reseeded ledger heads. Each row: override_id, param_key, status, window_id, rev,
# timeout_ms_delta, max_records_delta, retry_limit_delta, risk_delta.
HIDDEN_HEADS: dict[str, list[tuple[str, str, str, str, int, int, int, int, int]]] = {
    "hidden-a": [
        ("OV-K118-a1", "K118", "active", "WIN-AUTH", 2, 40, 5, 0, 1),
        ("OV-K042-a2", "K042", "active", "WIN-PRE", 2, 500, 30, 2, 9),
        ("OV-K042-a3", "K042", "active", "WIN-AUTH", 1, 5, -20, 1, 2),
        ("OV-K042-a4", "K042", "superseded", "WIN-AUTH", 1, -4, -30, 3, 11),
        ("OV-K042-a5", "K042", "active", "WIN-AUTH", 2, 75, -25, 0, 2),
        ("OV-K042-a6", "K042", "active", "WIN-AUTH", 1, -3, -10, 1, 3),
        ("OV-K042-a7", "K042", "active", "WIN-AUTH-V099", 2, 60, 12, 1, 6),
    ],
    "hidden-b": [
        ("OV-K118-b1", "K118", "active", "WIN-AUTH", 1, 2, 4, 1, 0),
        ("OV-K118-b2", "K118", "active", "WIN-AUTH", 2, -60, -3, 0, 2),
        ("OV-K042-b3", "K042", "active", "WIN-AUTH", 2, 4, -40, 1, 4),
        ("OV-K042-b4", "K042", "active", "WIN-OLD", 1, 1, 8, 0, 1),
        ("OV-K042-b5", "K042", "active", "WIN-AUTH", 1, 0, -15, 2, 1),
        ("OV-K042-b6", "K042", "active", "WIN-AUTH", 2, -90, 20, 1, 5),
        ("OV-K042-b7", "K042", "superseded", "WIN-AUTH", 2, 300, -5, 1, 3),
    ],
    "hidden-c": [
        ("OV-K042-c1", "K042", "active", "WIN-PRE", 1, 3, 10, 1, 4),
        ("OV-K042-c2", "K042", "active", "WIN-AUTH", 1, 1, -36, 0, 3),
        ("OV-K118-c3", "K118", "active", "WIN-AUTH", 2, 90, 0, 1, 0),
        ("OV-K042-c4", "K042", "active", "WIN-AUTH", 2, 50, -10, 1, 2),
        ("OV-K042-c5", "K042", "active", "WIN-AUTH-V099", 2, 30, -8, 0, 1),
        ("OV-K042-c6", "K042", "superseded", "WIN-AUTH", 1, -1, 5, 2, 2),
    ],
}
VARIANTS: dict[str, dict[str, Any]] = {
    "shipped": {},
    "hidden-a": {"head": "hidden-a", "allowance": 3},
    "hidden-b": {"head": "hidden-b", "allowance": 4, "corrupt": "t-f003"},
    "hidden-c": {"head": "hidden-c", "allowance": 2},
    "mutation-risk": {"risk": {"OV-K042-auth": 3}},
    "mutation-allowance": {"allowance": 1},
}
HIDDEN = ("hidden-a", "hidden-b", "hidden-c")

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


def windows() -> dict[str, tuple[int, int, str]]:
    root = ET.fromstring(corpus_files()["effective_windows.xml"])
    return {node.get("id"): (int(node.get("start")), int(node.get("end")), node.get("version")) for node in root.iter("window")}


def delta_ms(row: dict[str, Any]) -> int:
    value = int(row["timeout_ms_delta"])
    return value * 1000 if int(row["rev"]) == 1 else value


def ledger_controls(rows: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    controls: dict[str, dict[str, int]] = {}
    for row in rows:
        entry = controls.setdefault(row["tenant"], {"max_records_delta_sum": 0, "rows": 0, "timeout_ms_delta_sum_ms": 0})
        entry["rows"] += 1
        entry["max_records_delta_sum"] += int(row["max_records_delta"])
        entry["timeout_ms_delta_sum_ms"] += delta_ms(row)
    return {tenant: controls[tenant] for tenant in sorted(controls)}


def build_variant(name: str) -> tuple[dict[str, bytes], list[dict[str, Any]], dict[str, Any], int]:
    """Return the corpus files, ledger rows, stored controls and tenant allowance of one corpus."""
    spec = VARIANTS[name]
    files = dict(corpus_files())
    ledger = json.loads(files["override_deltas.json"])
    rows = [dict(row) for row in ledger["overrides"]]
    stored = ledger["controls"]
    quota = files["quota_limits.cfg"].decode("utf-8")
    allowance = int(re.search(rf"^{TENANT} = (\d+)$", quota, re.M).group(1))
    changed = False
    if "head" in spec:
        spans = windows()
        head = []
        for override_id, param_key, status, window_id, rev, timeout, records, retry, risk in HIDDEN_HEADS[spec["head"]]:
            head.append({
                "max_records_delta": records, "override_id": override_id, "param_key": param_key,
                "retry_limit_delta": retry, "rev": rev, "risk_delta": risk, "seq": 0, "status": status,
                "tenant": TENANT, "timeout_ms_delta": timeout, "version": spans[window_id][2], "window_id": window_id,
            })
        rows = head + [row for row in rows if not (row["tenant"] == TENANT and int(row["seq"]) <= 6)]
        for index, row in enumerate(rows):
            row["seq"] = 10 + 3 * index
        changed = True
    for override_id, value in spec.get("risk", {}).items():
        for row in rows:
            if row["override_id"] == override_id:
                row["risk_delta"] = value
                changed = True
    if changed:
        stored = ledger_controls(rows)
        if "corrupt" in spec:
            stored[spec["corrupt"]]["rows"] += 1
        document = {
            "conventions": ledger["conventions"],
            "overrides": [{key: row[key] for key in sorted(row)} for row in rows],
            "controls": stored,
        }
        files["override_deltas.json"] = (json.dumps(document, indent=2) + "\n").encode("utf-8")
    if "allowance" in spec:
        allowance = spec["allowance"]
        quota = re.sub(rf"^{TENANT} = \d+$", f"{TENANT} = {allowance}", quota, flags=re.M)
        files["quota_limits.cfg"] = quota.encode("utf-8")
    return files, rows, stored, allowance


def scaled(amount: int) -> int:
    return (amount * MULT_BPS + 500) // 1000


def reference_documents(name: str) -> dict[str, Any]:
    """The authoritative policy, curve and graded trace fields of one corpus."""
    _, rows, stored, allowance = build_variant(name)
    spans = windows()
    remaining = allowance
    applied: list[dict[str, Any]] = []
    for row in sorted((row for row in rows if row["tenant"] == TENANT), key=lambda row: int(row["seq"])):
        span = spans.get(row["window_id"])
        if row["status"] != "active" or span is None:
            continue
        start, end, version = span
        if not start <= EFFECTIVE_INSTANT < end or version != EFFECTIVE_VERSION or row["version"] != EFFECTIVE_VERSION:
            continue
        if remaining == 0:
            continue
        remaining -= 1
        if row["param_key"] == PARAM_KEY:
            applied.append(row)
    max_records = min(MAX_RECORDS_CAP, scaled(BASE_MAX_RECORDS + sum(int(row["max_records_delta"]) for row in applied)))
    retry_limit = BASE_RETRY_LIMIT + sum(int(row["retry_limit_delta"]) for row in applied)
    timeout_ms = BASE_TIMEOUT_SECONDS * 1000 + sum(delta_ms(row) for row in applied)
    contribution = sum(scaled(term) for term in [BASE_RISK_WEIGHT, *(int(row["risk_delta"]) for row in applied)])
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
    recomputed = ledger_controls(rows)
    trace = {
        "active_bundle": ACTIVE_BUNDLE,
        "applied_overrides": [row["override_id"] for row in applied],
        "client_version_ignored": True,
        "effective_version": EFFECTIVE_VERSION,
        "ledger_controls": {tenant: ("ok" if recomputed.get(tenant) == stored[tenant] else "mismatch") for tenant in sorted(stored)},
        "param_key": PARAM_KEY,
        "tenant": TENANT,
    }
    return {"policy_resolved.json": policy, "threshold_curve.json": curve, "dependency_trace.json": trace}


def run_resolve(name: str) -> dict[str, bytes]:
    files, _, _, _ = build_variant(name)
    corpus = Path(tempfile.mkdtemp(prefix=f"sentinel-{name}-"))
    for filename, payload in files.items():
        (corpus / filename).write_bytes(payload)
    _grant_read(corpus)
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
    """Build a config through the delivered init and set from the delivered resolve output on corpus name."""
    policy = resolved_document(name, "policy_resolved.json")
    assert isinstance(policy, dict), f"{name} policy_resolved.json is not an object"
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
    """POSITIVE: on each reseeded corpus, the dependency_trace document carries exactly its specified fields and its chain, applied overrides and ledger controls equal the authoritative document."""
    for name in HIDDEN:
        trace = resolved_document(name, "dependency_trace.json")
        assert isinstance(trace, dict), f"{name} dependency_trace.json is not an object"
        assert set(trace) == TRACE_KEYS, f"{name} dependency_trace.json keys differ: {sorted(set(trace) ^ TRACE_KEYS)}"
        graded = {key: trace[key] for key in TRACE_GRADED_KEYS}
        assert_document(graded, reference_documents(name)["dependency_trace.json"], f"{name} dependency_trace.json")


def test_hidden_config_document_rebuilt_by_cli_matches():
    """POSITIVE: on each reseeded corpus, the config document built by the delivered init and set from the delivered resolve output equals the authoritative config."""
    for name in HIDDEN:
        want = reference_documents(name)["policy_resolved.json"]
        expected = config_doc(want["max_records"], want["retry_limit"], want["timeout_ms"])
        assert_document(load_json(rebuild_config(name)), expected, f"{name} rebuilt config.json")


def test_mutation_risk_delta_moves_only_contribution():
    """POSITIVE: mutation raising one applied risk_delta by one moves the curve contribution as the rounding rule says and leaves the policy figures unchanged."""
    expected = reference_documents("mutation-risk")
    assert_document(resolved_document("mutation-risk", "threshold_curve.json"), expected["threshold_curve.json"], "mutation-risk threshold_curve.json")
    assert_document(resolved_document("mutation-risk", "policy_resolved.json"), expected["policy_resolved.json"], "mutation-risk policy_resolved.json")


def test_mutation_allowance_cut_drops_later_override():
    """POSITIVE: mutation cutting the tenant override allowance to one changes the resolved policy to the authoritative one for that allowance."""
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
    """POSITIVE: two resolve runs on the same reseeded hidden corpus write byte-identical canonical documents."""
    first = resolved("hidden-a")
    second = run_resolve("hidden-a")
    for doc in RESOLVE_DOCS:
        assert first[doc] == second[doc], f"{doc} differs between two runs on hidden-a"
        assert_canonical(first[doc], f"hidden-a {doc}")


def test_shipped_artifacts_follow_field_specs():
    """POSITIVE: the seven shipped artifacts parse, follow their field specs and describe the policy of the reference data."""
    for path in ARTIFACT_PATHS:
        assert path.is_file() and path.stat().st_size > 0, f"missing or empty {path}"
        assert path.stat().st_size < MAX_MEMBER_BYTES, f"oversized {path}"
    for path in JSON_ARTIFACT_PATHS:
        assert_canonical(path.read_bytes(), path.name)
        found = [key for key in json_keys(load_json(path)) if key in FORBIDDEN_KEYS]
        assert not found, f"{path.name} carries dynamic keys {found}"
    assert_document(load_json(CONFIG_PATH), expected_config(), "config.json")
    shipped = reference_documents("shipped")
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
    for name, path in (("dev", PROFILE_DEV_PATH), ("prod", PROFILE_PROD_PATH)):
        assert_document(load_json(path), expected_profile(name, shipped["policy_resolved.json"]), path.name)
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
    summary = load_json(SUMMARY_PATH)
    assert summary["artifact_count"] == len(ARTIFACT_NAMES) and summary["artifacts"] == ARTIFACT_NAMES, "summary.json artifacts differ"
    assert summary["profiles"] == ["dev", "prod"] and summary["format_tag"] == FORMAT_TAG and summary["trailer"] == TRAILER, "summary.json fields differ"
    assert summary["inputs"] == sorted(summary["inputs"]) and summary["input_count"] == len(summary["inputs"]) >= 50, "summary.json inputs differ"
    with zipfile.ZipFile(TOOL_ARCHIVE) as zf:
        infos = zf.infolist()
        assert [info.filename for info in infos] == ["README.md", "cli.py", "schema.json"], "tool.zip member layout differs from the shipped archive"
        for info in infos:
            assert info.date_time == (1980, 1, 1, 0, 0, 0), f"tool.zip member {info.filename} has an unpinned timestamp"
            assert (info.external_attr >> 16) & 0o777 == 0o644, f"tool.zip member {info.filename} mode is not 0644"
        assert hashlib.sha256(zf.read("cli.py")).hexdigest() != SHIPPED_CLI_SHA256, "cli.py is the unrepaired shipped source"
    assert rebuild_config("shipped").read_bytes() == CONFIG_PATH.read_bytes(), "config.json bytes differ from the init and set rebuild"


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


@criterion(description="on each reseeded corpus, the dependency_trace document carries exactly its specified fields and its chain, applied overrides and ledger controls equal the authoritative document.")
def hidden_dependency_trace_document_matches(workspace: Path) -> bool:
    return _passes("hidden_dependency_trace_document_matches", test_hidden_dependency_trace_document_matches)


@criterion(description="on each reseeded corpus, the config document built by the delivered init and set from the delivered resolve output equals the authoritative config.")
def hidden_config_document_rebuilt_by_cli_matches(workspace: Path) -> bool:
    return _passes("hidden_config_document_rebuilt_by_cli_matches", test_hidden_config_document_rebuilt_by_cli_matches)


@criterion(description="mutation raising one applied risk_delta by one moves the curve contribution as the rounding rule says and leaves the policy figures unchanged.")
def mutation_risk_delta_moves_only_contribution(workspace: Path) -> bool:
    return _passes("mutation_risk_delta_moves_only_contribution", test_mutation_risk_delta_moves_only_contribution)


@criterion(description="mutation cutting the tenant override allowance to one changes the resolved policy to the authoritative one for that allowance.")
def mutation_allowance_cut_drops_later_override(workspace: Path) -> bool:
    return _passes("mutation_allowance_cut_drops_later_override", test_mutation_allowance_cut_drops_later_override)


@criterion(description="the repaired validate subcommand accepts a supplied correct config and rejects one that lacks a required key.")
def validate_accepts_supplied_config_and_rejects_missing_key(workspace: Path) -> bool:
    return _passes("validate_accepts_supplied_config_and_rejects_missing_key", test_validate_accepts_supplied_config_and_rejects_missing_key)


@criterion(description="two resolve runs on the same reseeded hidden corpus write byte-identical canonical documents.")
def hidden_resolve_rerun_is_canonical_and_byte_identical(workspace: Path) -> bool:
    return _passes("hidden_resolve_rerun_is_canonical_and_byte_identical", test_hidden_resolve_rerun_is_canonical_and_byte_identical)


@criterion(description="the seven shipped artifacts parse, follow their field specs and describe the policy of the reference data.")
def shipped_artifacts_follow_field_specs(workspace: Path) -> bool:
    return _passes("shipped_artifacts_follow_field_specs", test_shipped_artifacts_follow_field_specs)


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


criteria.hidden_policy_resolved_document_matches(weight=5)
criteria.hidden_threshold_curve_document_matches(weight=5)
criteria.hidden_dependency_trace_document_matches(weight=5)
criteria.hidden_config_document_rebuilt_by_cli_matches(weight=5)
criteria.mutation_risk_delta_moves_only_contribution(weight=3)
criteria.mutation_allowance_cut_drops_later_override(weight=3)
criteria.validate_accepts_supplied_config_and_rejects_missing_key(weight=3)
criteria.hidden_resolve_rerun_is_canonical_and_byte_identical(weight=1)
criteria.shipped_artifacts_follow_field_specs(weight=1)
criteria.negative_hardcoded_sample_answers(weight=-5)
criteria.negative_transcript_disagrees_with_config(weight=-3)
criteria.negative_url_or_secret_in_artifacts(weight=-3)


# Embedded copy of environment/data (a deterministic zip, base64), unpacked for the resolve reruns.
REFERENCE_CORPUS_B64 = "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"
