"""Author-time writer for tests/test_output.py (not shipped in the bundle).

usage: python3 mktests.py <shipped_data_dir> <hidden_root> <shipped_gold_dir> <out_test_py>
<hidden_root> holds H1..H4 corpora and out_H1..out_H4 oracle outputs.
"""
import gzip
import io
import json
import sys
import tarfile
from pathlib import Path

CORPORA = ["H1", "H2", "H3", "H4"]
ARTIFACTS = [
    "corrected_coefficients.jsonl", "objective.json", "optimal_plan.jsonl",
    "production_schedule.csv", "sourcing_allocation.csv", "holding_profile.csv",
    "retrofit_selection.json", "budget_utilization.json", "plant_utilization.csv",
    "shortfall_ledger.csv", "period_costs.json", "item_summary.json",
    "binding_constraints.json", "optimality_certificate.json", "sensitivity_report.json",
    "incumbent_delta.json", "coefficient_corrections.csv", "data_quality.json",
    "rejected_records.csv", "reconciliation.txt", "audit_summary.md",
]
GROUPS = [
    ("coefficients", 3, ["corrected_coefficients.jsonl", "coefficient_corrections.csv"],
     "the rebuilt coefficient stream and the per key corrections match"),
    ("capital", 1, ["retrofit_selection.json", "budget_utilization.json"],
     "the capital selection and the envelope accounting match"),
    ("quality", 3, ["data_quality.json", "rejected_records.csv"],
     "the source accounting and the rejected rows match"),
    ("plan", 5, ["optimal_plan.jsonl", "production_schedule.csv", "holding_profile.csv",
                 "item_summary.json"],
     "the lot sizing plan, schedule, carrying profile and item roll up match"),
    ("sourcing", 5, ["sourcing_allocation.csv", "plant_utilization.csv", "shortfall_ledger.csv"],
     "the plant assignment, plant loading and shortfall ledger match"),
    ("totals", 5, ["objective.json", "period_costs.json", "reconciliation.txt",
                   "audit_summary.md", "incumbent_delta.json"],
     "the objective, period roll up, reconciliation, audit summary and incumbent delta match"),
    ("certificate", 3, ["optimality_certificate.json", "binding_constraints.json",
                        "sensitivity_report.json"],
     "the optimality certificate, binding constraints and sensitivity report match"),
]


def tgz(files):
    """files: list of (name, bytes); deterministic gzip tarball."""
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w", format=tarfile.USTAR_FORMAT) as tar:
        for name, data in sorted(files):
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mtime = 0
            info.mode = 0o644
            info.uname = info.gname = "root"
            tar.addfile(info, io.BytesIO(data))
    out = io.BytesIO()
    with gzip.GzipFile(fileobj=out, mode="wb", mtime=0, compresslevel=9) as gz:
        gz.write(raw.getvalue())
    return out.getvalue()


def hexblock(name, blob):
    h = blob.hex()
    lines = ["    \"%s\"" % h[i:i + 96] for i in range(0, len(h), 96)]
    return "%s = (\n%s\n)\n" % (name, "\n".join(lines))


def main():
    shipped, hidden, sgold, target = map(Path, sys.argv[1:5])
    parts = []
    data_files = [(p.name, p.read_bytes()) for p in sorted(shipped.iterdir()) if p.is_file()]
    parts.append(hexblock("_SHIPPED_DATA", tgz(data_files)))
    parts.append(hexblock("_GOLDEN_SHIPPED", tgz(
        [(n, (sgold / n).read_bytes()) for n in ARTIFACTS])))
    base = dict(data_files)
    for h in CORPORA:
        over = [(p.name, p.read_bytes()) for p in sorted((hidden / h).iterdir())
                if p.is_file() and base.get(p.name) != p.read_bytes()]
        parts.append(hexblock("_OVERLAY_" + h, tgz(over)))
        gold = [(n, (hidden / ("out_" + h) / n).read_bytes()) for n in ARTIFACTS]
        parts.append(hexblock("_GOLDEN_" + h, tgz(gold)))
    shipped_total = json.loads((sgold / "objective.json").read_text())["total_objective_cents"]
    blobs = "\n\n".join(parts)

    checks, regs = [], ["criteria.shipped_artifacts_match_contract(weight=1)"]
    for h in CORPORA:
        for g, w, files, desc in GROUPS:
            fn = "hidden_%s_%s" % (h.lower(), g)
            checks.append(
                '@criterion(description="on hidden input set %s, %s.")\n'
                "def %s(workspace: Path) -> bool:\n"
                "    return _group_matches(%r, %r)\n" % (h, desc, fn, h, files))
            regs.append("criteria.%s(weight=%d)" % (fn, w))
    regs += [
        "criteria.negative_shipped_results_baked_into_solver(weight=-5)",
        "criteria.negative_network_dependency_or_shell_cheat(weight=-3)",
        "criteria.negative_reads_outside_input_dir(weight=-3)",
        "criteria.negative_nondeterminism_source_in_solver(weight=-3)",
        "criteria.negative_trusts_incumbent_objective(weight=-3)",
        "criteria.negative_writes_outside_output_dir(weight=-3)",
    ]
    text = TEMPLATE.replace("@@ARTIFACTS@@", json.dumps(ARTIFACTS)) \
        .replace("@@SHIPPED_TOTAL@@", str(shipped_total)) \
        .replace("@@BLOBS@@", blobs) \
        .replace("@@AUDIT_WRAPPER@@", repr(AUDIT_WRAPPER)) \
        .replace("@@CHECKS@@", "\n\n".join(checks)) \
        .replace("@@REGS@@", "\n".join(regs))
    target.write_text(text, encoding="utf-8")
    print("wrote", target, len(text), "bytes;", len(regs), "criteria")


AUDIT_WRAPPER = r"""import json
import os
import runpy
import sys
import sysconfig
from pathlib import Path

program, input_dir, output_dir = sys.argv[1:4]
audit_fd = int(os.environ["DPR_AUDIT_FD"])
input_dir = Path(input_dir).resolve()
output_dir = Path(output_dir).resolve()
stage_dir = Path(program).resolve().parent
python_roots = tuple(Path(p).resolve() for p in
                     {sys.prefix, sys.exec_prefix, sys.base_prefix, sys.base_exec_prefix})
if sys.pycache_prefix:
    python_roots += (Path(sys.pycache_prefix).resolve(),)
stdlib = getattr(sys, "stdlib_module_names", None)
if stdlib is None:
    stdlib_dir = Path(sysconfig.get_path("stdlib"))
    stdlib = set(sys.builtin_module_names) | {p.stem for p in stdlib_dir.glob("*.py")}
    stdlib |= {p.name for p in stdlib_dir.iterdir() if p.is_dir() and p.name != "site-packages"}
    stdlib |= {p.name.split(".", 1)[0] for p in
               Path(sysconfig.get_config_var("DESTSHARED")).glob("*.so")}
seen_imports = set()
written = set()

def within(path, root):
    return path == root or root in path.parents

def classify_path(raw):
    if not isinstance(raw, (str, bytes, os.PathLike)):
        return None
    try:
        return Path(raw).resolve()
    except (OSError, ValueError, TypeError):
        return None

def record(kind, event, path=None):
    item = {"kind": kind, "event": event}
    if path is not None:
        item["path"] = str(path)
    os.write(audit_fd, (json.dumps(item, sort_keys=True) + "\n").encode("utf-8"))

def hook(event, args):
    if event in ("open", "sqlite3.connect"):
        path = classify_path(args[0] if args else None)
        if path is None:
            return
        mode = args[1] if event == "open" and len(args) > 1 else "r"
        flags = args[2] if event == "open" and len(args) > 2 else 0
        write = (isinstance(mode, str) and any(c in mode for c in "wax+")) or (
            isinstance(flags, int) and bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)))
        if write:
            written.add(path)
            if within(path, input_dir):
                record("write_input", event, path)
            elif not within(path, output_dir):
                record("write_outside", event, path)
        elif not (path in written or within(path, input_dir) or within(path, output_dir) or
                  within(path, stage_dir) or any(within(path, p) for p in python_roots)):
            record("read_outside", event, path)
    elif event in ("os.remove", "os.unlink", "os.mkdir", "os.rmdir", "os.rename"):
        paths = args[:2] if event == "os.rename" else args[:1]
        for index, raw in enumerate(paths):
            path = classify_path(raw)
            if path is not None:
                if index == 1:
                    written.add(path)
                if within(path, input_dir):
                    record("write_input", event, path)
                elif not within(path, output_dir):
                    record("write_outside", event, path)
    elif (event.startswith("socket.") or event == "subprocess.Popen" or
          event == "os.system" or event.startswith("os.exec") or
          event.startswith("os.posix_spawn") or event.startswith("os.fork") or
          event == "ctypes.dlopen"):
        record("network_process_import", event)
    elif event == "import" and args:
        top = str(args[0]).split(".", 1)[0]
        if top not in stdlib:
            seen_imports.add(top)

sys.addaudithook(hook)
sys.argv = [program, input_dir.as_posix(), output_dir.as_posix()]
try:
    runpy.run_path(program, run_name="__main__")
finally:
    for top in sorted(seen_imports):
        if top in sys.modules:
            record("network_process_import", "import:" + top)
"""


TEMPLATE = r'''#!/usr/bin/env python3
"""Verifier for dispatch-plan-reoptimization.

The delivered optimizer is run on four hidden input sets. Each set is the
shipped export set with reseeded figures and extra register rows, stored here as
an overlay tarball. The expected artifacts for each set were produced offline by
the oracle at bundle-author time and are stored as gzip tarballs; the verifier
holds no reference implementation. Values and stated serialization are checked.
"""
from __future__ import annotations

import ast as _ast
import csv as _csv
import fcntl as _fcntl
import io as _io
import json
import re as _re
import os as _os
import pwd as _pwd
import shutil as _shutil
import signal as _signal
import subprocess as _subprocess
import sys as _sys
import tarfile as _tarfile
import tempfile as _tempfile
import threading
from pathlib import Path

from rewardkit import criteria, criterion

APP_ROOT = Path(_os.environ.get("APP_ROOT", "/app"))
OUT_DIR = APP_ROOT / "out"
SOLVER = OUT_DIR / "solver.py"
ARTIFACTS = @@ARTIFACTS@@
SHIPPED_TOTAL = @@SHIPPED_TOTAL@@
INCUMBENT_TOTAL = 724451671
RUN_TIMEOUT = 400
_SETPRIV = ["setpriv", "--reuid=nobody", "--regid=nogroup", "--clear-groups"]
_LOCK_PATH = Path(_tempfile.gettempdir()) / "dpr-grader.lock"
_AUDIT_WRAPPER = @@AUDIT_WRAPPER@@
_AUDITS = {}

@@BLOBS@@


def _unpack(hex_blob: str) -> dict:
    blob = bytes.fromhex(hex_blob)
    with _tarfile.open(fileobj=_io.BytesIO(blob), mode="r:gz") as tar:
        return {_os.path.basename(m.name): tar.extractfile(m).read()
                for m in tar.getmembers() if m.isfile()}


def _corpus(name: str) -> dict:
    files = _unpack(_SHIPPED_DATA)
    if name != "shipped":
        files.update(_unpack(globals()["_OVERLAY_" + name]))
    return files


def _write_corpus(name: str, target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    for fname, data in _corpus(name).items():
        (target / fname).write_bytes(data)
        (target / fname).chmod(0o644)
    target.chmod(0o755)


def _uid_of_nobody() -> int:
    return _pwd.getpwnam("nobody").pw_uid


def _kill_uid(uid: int) -> None:
    # every check that runs agent code holds the grader file lock, so any
    # process left under the unprivileged uid belongs to this check
    for entry in Path("/proc").glob("[0-9]*"):
        try:
            for line in (entry / "status").read_text().splitlines():
                if line.startswith("Uid:"):
                    if int(line.split()[1]) == uid:
                        _os.kill(int(entry.name), _signal.SIGKILL)
                    break
        except (OSError, ValueError):
            continue


def _solver_env(overrides=None) -> dict:
    merged = dict(_os.environ)
    if overrides:
        merged.update(overrides)
    clean = {k: v for k, v in merged.items() if not any(
        marker in k.upper() for marker in ("KEY", "TOKEN", "SECRET", "PASSWORD"))}
    clean.setdefault("PATH", _os.defpath)
    clean.setdefault("LANG", "C.UTF-8")
    return clean


def _run_solver(input_dir: Path, output_dir: Path, env=None, tag=None) -> bool:
    """Run a readable staged copy of the delivered optimizer; True on a clean exit."""
    if not SOLVER.is_file():
        return False
    stage = Path(_tempfile.mkdtemp(prefix="dpr-prog-"))
    program = stage / "solver.py"
    program.write_bytes(SOLVER.read_bytes())
    program.chmod(0o644)
    wrapper = stage / "audit_wrapper.py"
    wrapper.write_text(_AUDIT_WRAPPER, encoding="utf-8")
    wrapper.chmod(0o644)
    stage.chmod(0o755)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_dir.chmod(0o777)
    output_dir.parent.chmod(0o755)
    audit_path = stage / "audit.jsonl"
    audit_fd = _os.open(audit_path, _os.O_WRONLY | _os.O_CREAT | _os.O_APPEND, 0o600)
    child_env = _solver_env(env)
    child_env["DPR_AUDIT_FD"] = str(audit_fd)
    cmd = [_sys.executable, "-B", str(wrapper), str(program), str(input_dir), str(output_dir)]
    dropped = _os.name == "posix" and _os.geteuid() == 0
    if dropped:
        cmd = [*_SETPRIV, *cmd]
    with open(_LOCK_PATH, "a") as lock:
        _fcntl.flock(lock, _fcntl.LOCK_EX)
        proc = _subprocess.Popen(cmd, cwd=str(stage), env=child_env,
                                 pass_fds=(audit_fd,), start_new_session=True,
                                 stdout=_subprocess.DEVNULL, stderr=_subprocess.DEVNULL)
        try:
            code = proc.wait(timeout=RUN_TIMEOUT)
        except _subprocess.TimeoutExpired:
            code = None
        finally:
            try:
                _os.killpg(proc.pid, _signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
            proc.wait()
            if dropped:
                _kill_uid(_uid_of_nobody())
    _os.close(audit_fd)
    try:
        events = [json.loads(line) for line in audit_path.read_text().splitlines() if line]
    except (OSError, ValueError):
        events = []
    if tag is not None:
        _AUDITS[tag] = events
    _shutil.rmtree(stage, ignore_errors=True)
    return code == 0


_RUNS = {}
_RUN_LOCK = threading.Lock()


def _hidden_outputs(name: str):
    """Artifacts the optimizer writes for hidden set `name`, or None if it failed."""
    with _RUN_LOCK:
        if name not in _RUNS:
            root = Path(_tempfile.mkdtemp(prefix="dpr-%s-" % name.lower()))
            root.chmod(0o755)
            data, out = root / "data", root / "out"
            _write_corpus(name, data)
            result = None
            if _run_solver(data, out, tag=name):
                result = {}
                for art in ARTIFACTS:
                    path = out / art
                    if path.is_file():
                        result[art] = path.read_bytes()
            _shutil.rmtree(root, ignore_errors=True)
            _RUNS[name] = result
        return _RUNS[name]


def _parse(name: str, blob: bytes):
    text = blob.decode("utf-8")
    if name.endswith(".jsonl"):
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    if name.endswith(".json"):
        return json.loads(text)
    if name.endswith(".csv"):
        return [row for row in _csv.reader(_io.StringIO(text)) if row]
    return [line.rstrip() for line in text.strip().splitlines()]


_JSON_TOKEN = _re.compile(r'"(?:\\.|[^"\\])*"|-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?')


def _mask_json(text: str) -> str:
    return _JSON_TOKEN.sub(lambda m: '"S"' if m.group(0).startswith('"') else '0', text)


def _same_value(a, b) -> bool:
    if type(a) is not type(b):
        return False
    if isinstance(a, dict):
        return a.keys() == b.keys() and all(_same_value(a[k], b[k]) for k in a)
    if isinstance(a, list):
        return len(a) == len(b) and all(_same_value(x, y) for x, y in zip(a, b))
    return a == b


def _sorted_keys(value) -> bool:
    if isinstance(value, dict):
        return (list(value) == sorted(value) and all(_sorted_keys(v) for v in value.values()))
    if isinstance(value, list):
        return all(_sorted_keys(v) for v in value)
    return True


def _format_ok(name: str, blob: bytes) -> bool:
    text = blob.decode("utf-8")
    if "\r" in text:
        return False
    if name.endswith(".jsonl"):
        lines = text.splitlines()
        if not lines or any(not line for line in lines):
            return False
        return all(_sorted_keys(obj := json.loads(line)) and
                   _mask_json(line) == _mask_json(json.dumps(obj, sort_keys=True,
                       separators=(",", ":"))) for line in lines)
    if name.endswith(".json"):
        if not text.endswith("\n"):
            return False
        obj = json.loads(text)
        return (_sorted_keys(obj) and _mask_json(text) == _mask_json(
            json.dumps(obj, sort_keys=True, indent=1) + "\n"))
    if name.endswith(".csv"):
        return text.endswith("\n") and bool(text.splitlines()[0])
    return True


def _artifact_matches(name: str, got: bytes, want: bytes) -> bool:
    return _format_ok(name, got) and _same_value(_parse(name, got), _parse(name, want))


def _group_matches(name: str, files) -> bool:
    try:
        got = _hidden_outputs(name)
        if got is None:
            return False
        want = _unpack(globals()["_GOLDEN_" + name])
        return all(art in got and _artifact_matches(art, got[art], want[art])
                   for art in files)
    except Exception:
        return False


def _ran_cleanly() -> bool:
    return _hidden_outputs("H1") is not None


def _solver_text() -> str:
    try:
        return SOLVER.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def _solver_tree():
    try:
        return _ast.parse(_solver_text())
    except (SyntaxError, ValueError):
        return None


def _dotted(node) -> str:
    if isinstance(node, _ast.Name):
        return node.id
    if isinstance(node, _ast.Attribute):
        return "%s.%s" % (_dotted(node.value), node.attr)
    return ""


def _imported_modules(tree) -> set:
    names = set()
    for node in _ast.walk(tree):
        if isinstance(node, _ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, _ast.ImportFrom) and node.module:
            names.add(node.module)
            names.update("%s.%s" % (node.module, alias.name) for alias in node.names)
        elif (isinstance(node, _ast.Call) and _dotted(node.func).split(".")[-1] in {"__import__", "import_module"}
              and node.args and isinstance(node.args[0], _ast.Constant) and isinstance(node.args[0].value, str)):
            names.add(node.args[0].value)
    return names


def _called_names(tree) -> set:
    return {_dotted(node.func) for node in _ast.walk(tree) if isinstance(node, _ast.Call)}


def _ends_with_any(names, wanted) -> bool:
    return any(name == want or name.endswith("." + want) for name in names for want in wanted)


_NONDETERMINISTIC_MODULES = {"random", "uuid", "secrets"}
_CLOCK_CALLS = {"time.time", "time.time_ns", "time.monotonic", "time.monotonic_ns", "time.perf_counter",
                "time.perf_counter_ns", "time.process_time", "time.process_time_ns", "time.localtime",
                "datetime.now", "datetime.utcnow", "datetime.today", "date.today"}


def _executable_constants() -> list:
    tree = _solver_tree()
    if tree is None:
        return []
    values = []
    def visit(node):
        if isinstance(node, _ast.Expr) and isinstance(node.value, _ast.Constant):
            return
        if isinstance(node, _ast.Call) and _dotted(node.func).split(".")[-1] in {
                "print", "debug", "info", "warning", "error"}:
            return
        if isinstance(node, _ast.Constant):
            values.append(node.value)
        for child in _ast.iter_child_nodes(node):
            visit(child)
    visit(tree)
    return values


def _hardcodes_sample_answers() -> bool:
    return any(type(v) in (int, str) and str(v) == str(SHIPPED_TOTAL)
               for v in _executable_constants())


def _embeds_visible_records() -> bool:
    values = {v for v in _executable_constants() if isinstance(v, str)}
    return all(token in values for token in ["K01", "K24", "S01", "S10", "RP01", "RP30"])


def _tree(top: Path) -> dict:
    return {str(p.relative_to(top)): (p.read_bytes() if p.is_file() else None)
            for p in top.rglob("*")}


_GRADE_LOCK = threading.Lock()


def _guarded(check) -> bool:
    with _GRADE_LOCK:
        try:
            return bool(check())
        except Exception:
            return False


@criterion(description="the optimizer and all twenty-one shipped output artifacts match the contract values and format in /app/out.")
def shipped_artifacts_match_contract(workspace: Path) -> bool:
    if not SOLVER.is_file():
        return False
    try:
        want = _unpack(_GOLDEN_SHIPPED)
        return all((OUT_DIR / name).is_file() and
                   _artifact_matches(name, (OUT_DIR / name).read_bytes(), want[name])
                   for name in ARTIFACTS)
    except Exception:
        return False


@@CHECKS@@


def _check_baked_in() -> bool:
    return _ran_cleanly() and (_hardcodes_sample_answers() or _embeds_visible_records())


def _check_network() -> bool:
    return _ran_cleanly() and any(e["kind"] == "network_process_import"
                                  for e in _AUDITS.get("H1", []))


def _check_reads_outside() -> bool:
    return _ran_cleanly() and any(e["kind"] == "read_outside"
                                  for e in _AUDITS.get("H1", []))


def _check_nondeterminism() -> bool:
    tree = _solver_tree()
    if tree is None or not _ran_cleanly():
        return False
    imported = _imported_modules(tree)
    modules = {m.split(".")[0] for m in imported}
    return bool(modules & _NONDETERMINISTIC_MODULES or _ends_with_any(_called_names(tree) | imported, _CLOCK_CALLS))


def _check_incumbent() -> bool:
    values = _executable_constants()
    return (_ran_cleanly() and any(type(v) in (int, str) and str(v) == str(INCUMBENT_TOTAL)
                                   for v in values)
            and not _hardcodes_sample_answers() and not _embeds_visible_records())


def _check_writes_outside() -> bool:
    if not _ran_cleanly():
        return False
    top = Path(_tempfile.mkdtemp(prefix="dpr-scope-"))
    top.chmod(0o755)
    root = top / "data"
    _write_corpus("shipped", root)
    scratch = top / "scratch"
    scratch.mkdir()
    scratch.chmod(0o777)
    out = top / "nested" / "out"
    out.parent.mkdir()
    if not _run_solver(root, out, env={"TMPDIR": str(scratch)}, tag="scope"):
        _shutil.rmtree(top, ignore_errors=True)
        return False
    events = _AUDITS.get("scope", [])
    _shutil.rmtree(top, ignore_errors=True)
    return any(e["kind"] in ("write_outside", "write_input") for e in events)


@criterion(description="detects the corrected shipped total or the shipped identifiers baked into the optimizer after a clean run.")
def negative_shipped_results_baked_into_solver(workspace: Path) -> bool:
    # True means the cheat happened; the negative weight applies.
    return _guarded(_check_baked_in)


@criterion(description="detects imports or calls that reach the network, extra packages, a shell or another process.")
def negative_network_dependency_or_shell_cheat(workspace: Path) -> bool:
    # True means the cheat happened; the negative weight applies.
    return _guarded(_check_network)


@criterion(description="detects solver reads of files outside its supplied input directory that the same run did not write, during a clean run.")
def negative_reads_outside_input_dir(workspace: Path) -> bool:
    # True means the cheat happened; the negative weight applies.
    return _guarded(_check_reads_outside)


@criterion(description="detects random, uuid or clock reads in the delivered optimizer.")
def negative_nondeterminism_source_in_solver(workspace: Path) -> bool:
    # True means the cheat happened; the negative weight applies.
    return _guarded(_check_nondeterminism)


@criterion(description="detects the published faulty objective echoed when no stronger cheat fired.")
def negative_trusts_incumbent_objective(workspace: Path) -> bool:
    # True means the cheat happened; the negative weight applies.
    return _guarded(_check_incumbent)


@criterion(description="detects transient and persistent writes outside the solver output directory.")
def negative_writes_outside_output_dir(workspace: Path) -> bool:
    # True means the cheat happened; the negative weight applies.
    return _guarded(_check_writes_outside)


@@REGS@@


if __name__ == "__main__":
    print(json.dumps({"criteria": len([n for n, v in globals().items()
                                       if callable(v) and getattr(v, "__module__", "") == __name__
                                       and n.startswith(("shipped_", "hidden_", "negative_"))])}))
'''

if __name__ == "__main__":
    main()
