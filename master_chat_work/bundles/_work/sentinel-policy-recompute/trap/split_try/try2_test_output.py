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


def write_corpus(name: str) -> Path:
    files, _, _, _ = build_variant(name)
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
    """POSITIVE: the delivered resolve, run twice on one reseeded hidden-a corpus directory into two fresh output directories, writes the authoritative documents, byte-identical and canonical across both runs."""
    corpus = write_corpus("hidden-a")
    first = run_resolve("hidden-a", corpus)
    second = run_resolve("hidden-a", corpus)
    want = reference_documents("hidden-a")
    for doc in RESOLVE_DOCS:
        try:
            got = json.loads(first[doc])
        except json.JSONDecodeError as error:
            raise AssertionError(f"hidden-a {doc} is not JSON: {error}") from error
        if doc == "dependency_trace.json":
            assert isinstance(got, dict), "hidden-a dependency_trace.json is not an object"
            got = {key: got.get(key) for key in TRACE_GRADED_KEYS}
        assert_document(got, want[doc], f"hidden-a {doc}")
    for doc in RESOLVE_DOCS:
        assert first[doc] == second[doc], f"{doc} differs between two runs on one hidden-a corpus"
        assert_canonical(first[doc], f"hidden-a {doc}")


def assert_shipped_json(path: Path) -> Any:
    assert path.is_file() and path.stat().st_size > 0, f"missing or empty {path}"
    assert path.stat().st_size < MAX_MEMBER_BYTES, f"oversized {path}"
    assert_canonical(path.read_bytes(), path.name)
    document = load_json(path)
    found = [key for key in json_keys(document) if key in FORBIDDEN_KEYS]
    assert not found, f"{path.name} carries dynamic keys {found}"
    return document


def test_shipped_config_matches_policy_and_rebuild():
    """POSITIVE: the shipped config.json equals the authoritative configuration and its bytes equal the init and set rebuild."""
    assert_document(assert_shipped_json(CONFIG_PATH), expected_config(), "config.json")
    assert rebuild_config("shipped").read_bytes() == CONFIG_PATH.read_bytes(), "config.json bytes differ from the init and set rebuild"


def test_shipped_profiles_match_policy():
    """POSITIVE: both shipped profiles equal the authoritative profile documents."""
    shipped = reference_documents("shipped")
    for name, path in (("dev", PROFILE_DEV_PATH), ("prod", PROFILE_PROD_PATH)):
        assert_document(assert_shipped_json(path), expected_profile(name, shipped["policy_resolved.json"]), path.name)


def test_shipped_validation_report_follows_field_spec():
    """POSITIVE: the shipped validation_report.json carries true checks and the authoritative resolved documents."""
    shipped = reference_documents("shipped")
    validation = assert_shipped_json(VALIDATION_REPORT_PATH)
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


def test_shipped_report_records_transcript():
    """POSITIVE: the shipped report.json records the successful command transcript, the config digest and the trailer."""
    report = assert_shipped_json(REPORT_PATH)
    assert report.get("ok") is True and report.get("tool") == "sentinel-ctl", "report.json ok or tool is wrong"
    commands = report.get("commands")
    assert isinstance(commands, list) and commands, "report.json has no commands"
    seen = "\n".join(" ".join(str(arg) for arg in item.get("argv", [])) for item in commands)
    for subcommand in ("resolve", "init", "set", "validate"):
        assert subcommand in seen, f"report.json commands lack a {subcommand} run"
    assert all(item.get("returncode") == 0 for item in commands), "report.json lists a failed command"
    assert report.get("config_sha256") == hashlib.sha256(CONFIG_PATH.read_bytes()).hexdigest(), "report.json digest does not match config.json"
    assert report.get("trailer") == TRAILER, "report.json trailer is wrong"


def test_shipped_summary_lists_inputs_and_artifacts():
    """POSITIVE: the shipped summary.json lists the inputs, profiles and artifacts as its field spec says."""
    summary = assert_shipped_json(SUMMARY_PATH)
    assert summary["artifact_count"] == len(ARTIFACT_NAMES) and summary["artifacts"] == ARTIFACT_NAMES, "summary.json artifacts differ"
    assert summary["profiles"] == ["dev", "prod"] and summary["format_tag"] == FORMAT_TAG and summary["trailer"] == TRAILER, "summary.json fields differ"
    assert summary["inputs"] == sorted(summary["inputs"]) and summary["input_count"] == len(summary["inputs"]) >= 50, "summary.json inputs differ"


def test_shipped_tool_zip_layout_is_deterministic():
    """POSITIVE: the shipped tool.zip keeps the source member layout with pinned dates and modes and a repaired cli.py."""
    assert TOOL_ARCHIVE.is_file() and TOOL_ARCHIVE.stat().st_size < MAX_MEMBER_BYTES, "tool.zip is missing or oversized"
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


@criterion(description="split shipped check shipped_config_matches_policy_and_rebuild.")
def shipped_config_matches_policy_and_rebuild(workspace: Path) -> bool:
    return _passes("shipped_config_matches_policy_and_rebuild", test_shipped_config_matches_policy_and_rebuild)


@criterion(description="split shipped check shipped_profiles_match_policy.")
def shipped_profiles_match_policy(workspace: Path) -> bool:
    return _passes("shipped_profiles_match_policy", test_shipped_profiles_match_policy)


@criterion(description="split shipped check shipped_validation_report_follows_field_spec.")
def shipped_validation_report_follows_field_spec(workspace: Path) -> bool:
    return _passes("shipped_validation_report_follows_field_spec", test_shipped_validation_report_follows_field_spec)


@criterion(description="split shipped check shipped_report_records_transcript.")
def shipped_report_records_transcript(workspace: Path) -> bool:
    return _passes("shipped_report_records_transcript", test_shipped_report_records_transcript)


@criterion(description="split shipped check shipped_summary_lists_inputs_and_artifacts.")
def shipped_summary_lists_inputs_and_artifacts(workspace: Path) -> bool:
    return _passes("shipped_summary_lists_inputs_and_artifacts", test_shipped_summary_lists_inputs_and_artifacts)


@criterion(description="split shipped check shipped_tool_zip_layout_is_deterministic.")
def shipped_tool_zip_layout_is_deterministic(workspace: Path) -> bool:
    return _passes("shipped_tool_zip_layout_is_deterministic", test_shipped_tool_zip_layout_is_deterministic)


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
criteria.shipped_config_matches_policy_and_rebuild(weight=1)
criteria.shipped_profiles_match_policy(weight=1)
criteria.shipped_validation_report_follows_field_spec(weight=1)
criteria.shipped_report_records_transcript(weight=1)
criteria.shipped_summary_lists_inputs_and_artifacts(weight=1)
criteria.shipped_tool_zip_layout_is_deterministic(weight=1)
criteria.negative_hardcoded_sample_answers(weight=-5)
criteria.negative_transcript_disagrees_with_config(weight=-3)
criteria.negative_url_or_secret_in_artifacts(weight=-3)


# Embedded copy of environment/data (a deterministic zip, base64), unpacked for the resolve reruns.
REFERENCE_CORPUS_B64 = "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"
