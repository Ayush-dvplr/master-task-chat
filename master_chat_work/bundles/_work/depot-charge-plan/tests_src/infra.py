"""Checks for the depot charging day plan.

Expected documents are derived here from the shipped data folder and from fresh data
folders drawn by a seeded generator that lives only in this file. The delivered program is
run with the command the instruction states, as an unprivileged user, from a working
directory of its own, and every output document is compared whole.
"""
# pyright: reportUndefinedVariable=false, reportUnhashable=false, reportArgumentType=false, reportOptionalMemberAccess=false

from __future__ import annotations

import ast
import base64
import configparser
import csv
import heapq
import json
import os
import pwd
import random
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import xml.etree.ElementTree as ET
import zlib
from collections import deque
from datetime import datetime, timedelta
from pathlib import Path

from rewardkit import criteria, criterion

OUT = Path("/app/out")
SCRIPT = OUT / "derive_report.py"
DOC_NAMES = ["policy_audit.json", "summary.json", "data_quality.json", "region_North.json",
             "region_South.json", "region_West.json", "region_East.json",
             "segment_commercial.json", "segment_public.json"]
_SETPRIV = ["setpriv", "--reuid=nobody", "--regid=nogroup", "--clear-groups"]
_RUN_SECONDS = 120
_FRESH = {"h1": (61207, "hidden"), "h2": (72931, "hidden"), "h3": (84419, "hidden"), "h4": (93503, "large"),
          "rel": (47713, "hidden"), "dflt": (55109, "hidden")}
_UPLIFT = {"u1": 11113, "u2": 22229, "u3": 33343, "u4": 44449, "u5": 55547, "u6": 66653, "u7": 77761,
           "u8": 88867, "u9": 99971}
_LOCK = threading.Lock()
_MEMO: dict[str, dict] = {}


# ==== CHECKS ====
def _root_only_tests_present() -> bool:
    try:
        st = Path("/tests").stat()
    except OSError:
        return False
    return st.st_uid == 0 and (st.st_mode & 0o077) == 0


def _grant_read(argument: str) -> None:
    """Make an agent-written path readable before the uid drop.

    Agent editors write through a temp file in the same directory and rename it, so a
    program the agent wrote can land at mode 0600 (owner-only). The checks run that
    program as an unprivileged user, which then cannot open it, and a correct submission
    would score zero for a reason that has nothing to do with the task. The verifier runs
    as root, so widening the mode is always allowed here and it changes no graded content.
    """
    if not argument.startswith("/app"):
        return
    path = Path(argument)
    try:
        if path.exists():
            path.chmod(path.stat().st_mode | (0o555 if path.is_dir() else 0o444))
        for parent in path.parents:
            if parent == Path("/"):
                break
            parent.chmod(parent.stat().st_mode | 0o555)
            if parent == Path("/app"):
                break
    except OSError as exc:
        print("could not widen the mode of %s: %s" % (argument, exc), file=sys.stderr)


def _untrusted_command(command: list[str]) -> list[str]:
    if os.name != "posix" or not hasattr(os, "geteuid"):
        if _root_only_tests_present():
            raise RuntimeError("cannot drop privileges on this platform")
        return command
    if os.geteuid() != 0:
        if _root_only_tests_present():
            raise RuntimeError("checks must run as root to drop privileges")
        return command
    for argument in command:
        _grant_read(argument)
    return [*_SETPRIV, *command]


def _seal(root: Path) -> None:
    for path in sorted(root.rglob("*")):
        path.chmod(0o755 if path.is_dir() else 0o644)
    root.chmod(0o755)


def _shipped_files() -> dict[str, bytes]:
    return {name: zlib.decompress(base64.b64decode(blob)) for name, blob in _SHIPPED_DATA.items()}


def _write_tree(files: dict[str, bytes], root: Path | None = None) -> Path:
    if root is None:
        root = Path(tempfile.mkdtemp(prefix="inputs-"))
    root.mkdir(parents=True, exist_ok=True)
    for name, raw in files.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_bytes(raw)
    _seal(root)
    return root


def _assert_contract_bounds(root: Path) -> None:
    """Every drawn value stays inside what the shipped rules describe."""
    grid = configparser.ConfigParser()
    grid.read(root / "grid.ini")
    assert grid["plan"]["slot_minutes"] == "15" and grid["plan"]["slots"] == "96"
    assert int(grid["feeder"]["feeder_kwh_per_slot"]) > 0
    first = datetime.strptime(grid["plan"]["first_slot"], "%Y-%m-%dT%H:%M")
    assert first.minute % 15 == 0
    with open(root / "roster.csv", newline="") as handle:
        for row in csv.DictReader(handle):
            for key in ("arrive", "depart"):
                assert datetime.strptime(row[key], "%Y-%m-%dT%H:%M").minute % 15 == 0
            assert int(row["soc_arrival_kwh"]) >= 0
    with open(root / "published_plan.csv", newline="") as handle:
        for row in csv.DictReader(handle):
            assert int(row["kwh"]) > 0
            assert datetime.strptime(row["slot_start"], "%Y-%m-%dT%H:%M").minute % 15 == 0
    with open(root / "settlements.csv", newline="") as handle:
        for row in csv.DictReader(handle):
            assert int(row["kwh"]) > 0 and int(row["cents"]) > 0
    with open(root / "trips.jsonl") as handle:
        for line in handle:
            assert int(json.loads(line)["kwh"]) > 0
    for band in ET.parse(root / "tariff.xml").getroot().iter("band"):
        assert int(band.get("cents_per_kwh")) > 0
    for depot in json.loads((root / "depots.json").read_text())["depots"]:
        assert depot["depot"] in DEPOTS and int(depot["cabinets"]) > 0


def _fresh_tree(seed: int, kind: str) -> Path:
    root = Path(tempfile.mkdtemp(prefix="inputs-"))
    render(seed, kind, str(root))
    docs = {name: raw for name, raw in _shipped_files().items() if name.startswith("docs/")}
    _write_tree(docs, root)
    _assert_contract_bounds(root)
    _seal(root)
    return root


def _expected(data: Path) -> dict[str, object]:
    inst, rej, pd, ts = load(str(data))
    plan = solve_flow(inst)
    scratch = tempfile.mkdtemp(prefix="expected-")
    try:
        write(inst, plan, rej, pd, ts, scratch)
        return {name: json.loads(Path(scratch, name).read_text()) for name in DOC_NAMES}
    finally:
        shutil.rmtree(scratch)


def _kill_leftovers(proc: subprocess.Popen, command: list[str]) -> None:
    """Stop every process the run left behind before its check returns."""
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass
    if command[:1] != _SETPRIV[:1]:
        return
    # runs are serialised under _LOCK, so every process of the unprivileged user is this run's,
    # including a child that left the process group with setsid()
    nobody = pwd.getpwnam("nobody").pw_uid
    for status in Path("/proc").glob("[0-9]*/status"):
        try:
            uids = [line.split()[1] for line in status.read_text().splitlines() if line.startswith("Uid:")]
        except OSError:
            continue
        if uids and int(uids[0]) == nobody:
            try:
                os.kill(int(status.parent.name), signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass


def _run_program(data: Path, workdir: Path | None = None) -> dict:
    """Run the delivered program with the stated command; collect its documents."""
    out = Path(tempfile.mkdtemp(prefix="plan-out-"))
    out.chmod(0o777)
    if workdir is None:
        workdir = Path(tempfile.mkdtemp(prefix="elsewhere-"))
    workdir.mkdir(parents=True, exist_ok=True)
    workdir.chmod(0o777)
    command = _untrusted_command(["python3", str(SCRIPT), "--data", str(data), "--out", str(out)])
    result = {"returncode": None, "stderr": "", "docs": {}, "note": ""}
    proc = subprocess.Popen(command, cwd=workdir, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, start_new_session=True)
    try:
        _, stderr = proc.communicate(timeout=_RUN_SECONDS)
    except subprocess.TimeoutExpired:
        _kill_leftovers(proc, command)
        proc.wait()
        proc.stdout.close()
        proc.stderr.close()
        result["note"] = "the program did not finish within %d seconds" % _RUN_SECONDS
        return result
    _kill_leftovers(proc, command)
    result["returncode"] = proc.returncode
    result["stderr"] = stderr
    for name in DOC_NAMES:
        path = out / name
        if path.is_file():
            try:
                result["docs"][name] = json.loads(path.read_text())
            except ValueError as exc:
                result["docs"][name] = ("not valid JSON", str(exc))
    shutil.rmtree(out, ignore_errors=True)
    return result


def _memo(key: str, build) -> dict:
    with _LOCK:
        if key not in _MEMO:
            _MEMO[key] = build()
        return _MEMO[key]


def _shipped() -> dict:
    def build() -> dict:
        data = _write_tree(_shipped_files())
        return {"data": data, "expected": _expected(data)}
    return _memo("shipped", build)


def _fresh(key: str) -> dict:
    def build() -> dict:
        seed, kind = _FRESH[key]
        data = _fresh_tree(seed, kind)
        return {"expected": _expected(data), "run": _run_program(data)}
    return _memo(key, build)


def _uplifted(key: str) -> dict:
    """Held-out folder whose notice lists one feeder limit above feeder_kwh_per_slot."""
    def build() -> dict:
        root = Path(tempfile.mkdtemp(prefix="inputs-"))
        uplift(_UPLIFT[key], str(root))
        docs = {name: raw for name, raw in _shipped_files().items() if name.startswith("docs/")}
        _write_tree(docs, root)
        _assert_contract_bounds(root)
        _seal(root)
        return {"expected": _expected(root), "run": _run_program(root)}
    return _memo(key, build)


def _altered() -> dict:
    """Fresh set h2 with every table's body rows in a new order and a new public weight."""
    def build() -> dict:
        seed, kind = _FRESH["h2"]
        data = _fresh_tree(seed, kind)
        rng = random.Random(seed * 31 + 7)
        for name in ("roster.csv", "published_plan.csv", "settlements.csv", "fleet_register.csv", "trips.jsonl"):
            path = data / name
            lines = path.read_text().splitlines(keepends=True)
            skip = 0 if name.endswith(".jsonl") else 1
            body = lines[skip:]
            rng.shuffle(body)
            path.write_text("".join(lines[:skip] + body))
        weights = data / "service_classes.ini"
        weights.write_text(weights.read_text().replace("[public]\nweight = 4", "[public]\nweight = 6"))
        _seal(data)
        return {"expected": _expected(data), "run": _run_program(data)}
    return _memo("altered", build)


def _relocated() -> dict:
    """A fresh set of its own placed under a deeper folder and run from a different working directory."""
    def build() -> dict:
        seed, kind = _FRESH["rel"]
        base = Path(tempfile.mkdtemp(prefix="relocated-"))
        base.chmod(0o755)
        data = base / "archive" / "2026" / "inputs"
        shutil.copytree(_fresh_tree(seed, kind), data)
        for part in (base / "archive", base / "archive" / "2026"):
            part.chmod(0o755)
        _seal(data)
        return {"expected": _expected(data), "run": _run_program(data, base / "cwd")}
    return _memo("relocated", build)


_SCAN_ROOTS = (Path("/tmp"), Path("/var/tmp"), Path("/dev/shm"), Path("/app"))


def _nobody_files(skip: Path) -> set[str]:
    """Paths the unprivileged user owns, outside the folder skip."""
    try:
        nobody = pwd.getpwnam("nobody").pw_uid
    except KeyError:
        return set()
    found = set()
    for root in _SCAN_ROOTS:
        for dirpath, dirnames, filenames in os.walk(root):
            here = Path(dirpath)
            if here == skip or skip in here.parents:
                dirnames[:] = []
                continue
            for name in dirnames + filenames:
                try:
                    if (here / name).lstat().st_uid == nobody:
                        found.add(str(here / name))
                except OSError:
                    continue
    return found


def _snapshot(root: Path) -> dict:
    entries = {}
    for path in [root, *sorted(root.rglob("*"))]:
        st = path.lstat()
        rel = str(path.relative_to(root))
        if path.is_symlink():
            entries[rel] = ("link", os.readlink(path), st)
        elif path.is_dir():
            entries[rel] = ("dir", None, st)
        else:
            entries[rel] = ("file", path.read_bytes(), st)
    return entries


def _restore(root: Path, entries: dict) -> None:
    """Put root back exactly as _snapshot saw it."""
    for path in sorted(root.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        rel = str(path.relative_to(root))
        kind = "link" if path.is_symlink() else "dir" if path.is_dir() else "file"
        keep = rel in entries and entries[rel][0] == kind
        if keep and kind == "file":
            keep = path.lstat().st_uid == entries[rel][2].st_uid and path.read_bytes() == entries[rel][1]
        if keep and kind == "link":
            keep = os.readlink(path) == entries[rel][1]
        if not keep:
            if kind == "dir":
                shutil.rmtree(path, ignore_errors=True)
            else:
                path.unlink(missing_ok=True)
    for rel, (kind, raw, st) in sorted(entries.items(), key=lambda e: len(Path(e[0]).parts)):
        path = root / rel
        if kind == "dir":
            path.mkdir(parents=True, exist_ok=True)
        elif kind == "link" and not path.is_symlink():
            os.symlink(raw, path)
        elif kind == "file" and not path.exists():
            path.write_bytes(raw)
        if kind != "link":
            os.chown(path, st.st_uid, st.st_gid)
            path.chmod(st.st_mode & 0o7777)


def _flagless() -> dict:
    """A fresh set run by the bare command, so the data and output folders are the defaults."""
    def build() -> dict:
        seed, kind = _FRESH["dflt"]
        tree = _fresh_tree(seed, kind)
        expected = _expected(tree)
        if not SCRIPT.is_file():
            raise AssertionError("%s is missing" % SCRIPT)
        entries = _snapshot(OUT)
        data = Path("/app/data")
        held = None
        if data.exists() or data.is_symlink():
            held = Path(tempfile.mkdtemp(prefix=".data-held-", dir="/app")) / "data"
            os.rename(data, held)
        result = {"returncode": None, "stderr": "", "docs": {}, "note": ""}
        strays: list[str] = []
        try:
            shutil.copytree(tree, data)
            _seal(data)
            for name in DOC_NAMES:
                (OUT / name).unlink(missing_ok=True)
            OUT.chmod(0o777)
            workdir = Path(tempfile.mkdtemp(prefix="elsewhere-"))
            workdir.chmod(0o777)
            before = _nobody_files(OUT)
            command = _untrusted_command(["python3", str(SCRIPT)])
            proc = subprocess.Popen(command, cwd=workdir, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    text=True, start_new_session=True)
            try:
                _, stderr = proc.communicate(timeout=_RUN_SECONDS)
            except subprocess.TimeoutExpired:
                _kill_leftovers(proc, command)
                proc.wait()
                proc.stdout.close()
                proc.stderr.close()
                result["note"] = "the program did not finish within %d seconds" % _RUN_SECONDS
            else:
                _kill_leftovers(proc, command)
                result["returncode"] = proc.returncode
                result["stderr"] = stderr
                strays = sorted(_nobody_files(OUT) - before)
                for name in DOC_NAMES:
                    path = OUT / name
                    if path.is_file():
                        try:
                            result["docs"][name] = json.loads(path.read_text())
                        except ValueError as exc:
                            result["docs"][name] = ("not valid JSON", str(exc))
        finally:
            _restore(OUT, entries)
            shutil.rmtree(data, ignore_errors=True)
            if held is not None:
                os.rename(held, data)
                held.parent.rmdir()
        return {"expected": expected, "run": result, "strays": strays}
    return _memo("dflt", build)


def _with_broken_tariff() -> dict:
    def build() -> dict:
        files = _shipped_files()
        files["tariff.xml"] = files["tariff.xml"][: len(files["tariff.xml"]) // 2]
        return {"run": _run_program(_write_tree(files))}
    return _memo("malformed", build)


def _without_settlements() -> dict:
    def build() -> dict:
        files = _shipped_files()
        del files["settlements.csv"]
        return {"run": _run_program(_write_tree(files))}
    return _memo("missing", build)


def _first_difference(expected, got, path: str = "$") -> str | None:
    if type(expected) is not type(got):
        return path
    if isinstance(expected, dict):
        for key in sorted(set(expected) | set(got)):
            if key not in expected or key not in got:
                return "%s.%s" % (path, key)
            found = _first_difference(expected[key], got[key], "%s.%s" % (path, key))
            if found:
                return found
        return None
    if isinstance(expected, list):
        for index, (left, right) in enumerate(zip(expected, got)):
            found = _first_difference(left, right, "%s[%d]" % (path, index))
            if found:
                return found
        if len(expected) != len(got):
            return "%s[%d]" % (path, min(len(expected), len(got)))
        return None
    return None if expected == got else path


def _same_document(name: str, expected: dict, got) -> None:
    if not expected:
        raise AssertionError("%s: nothing to compare" % name)
    if got is None:
        raise AssertionError("%s: document not written" % name)
    where = _first_difference(expected, got)
    if where is not None:
        raise AssertionError("%s: first difference at %s" % (name, where))


def _check_present() -> None:
    with _LOCK:
        if not SCRIPT.is_file():
            raise AssertionError("%s: not delivered" % SCRIPT)
        ast.parse(SCRIPT.read_text(encoding="utf-8"), filename=str(SCRIPT))
        for name in DOC_NAMES:
            if not (OUT / name).is_file():
                raise AssertionError("%s: not delivered" % (OUT / name))


def _check_delivered(name: str) -> None:
    path = OUT / name
    expected = _shipped()["expected"][name]
    with _LOCK:
        if not path.is_file():
            raise AssertionError("%s: not delivered" % path)
        got = json.loads(path.read_text())
    _same_document(name, expected, got)


def _check_run(case: dict, name: str) -> None:
    run = case["run"]
    if run["returncode"] is None:
        raise AssertionError(run["note"])
    if run["returncode"] != 0:
        raise AssertionError("exit status %d: %s" % (run["returncode"], run["stderr"][-400:]))
    _same_document(name, case["expected"][name], run["docs"].get(name))


def _check_fresh(key: str, name: str) -> None:
    if not SCRIPT.is_file():
        raise AssertionError("%s: not delivered" % SCRIPT)
    _check_run(_fresh(key), name)


def _check_uplift(key: str, name: str) -> None:
    if not SCRIPT.is_file():
        raise AssertionError("%s: not delivered" % SCRIPT)
    _check_run(_uplifted(key), name)


def _check_altered() -> None:
    if not SCRIPT.is_file():
        raise AssertionError("%s: not delivered" % SCRIPT)
    _check_run(_altered(), "policy_audit.json")


def _check_relocated() -> None:
    if not SCRIPT.is_file():
        raise AssertionError("%s: not delivered" % SCRIPT)
    _check_run(_relocated(), "summary.json")


def _check_missing_input() -> None:
    if not SCRIPT.is_file():
        raise AssertionError("%s: not delivered" % SCRIPT)
    run = _without_settlements()["run"]
    if run["returncode"] is None:
        raise AssertionError(run["note"])
    if run["returncode"] == 0:
        raise AssertionError("exit status 0 with settlements.csv missing")
    if "settlements.csv" not in run["stderr"]:
        raise AssertionError("the error output does not name settlements.csv")


def _check_malformed_input() -> None:
    if not SCRIPT.is_file():
        raise AssertionError("%s: not delivered" % SCRIPT)
    run = _with_broken_tariff()["run"]
    if run["returncode"] is None:
        raise AssertionError(run["note"])
    if run["returncode"] == 0:
        raise AssertionError("exit status 0 with tariff.xml cut short")
    if "tariff.xml" not in run["stderr"]:
        raise AssertionError("the error output does not name tariff.xml")


def _check_default_paths() -> None:
    if not SCRIPT.is_file():
        raise AssertionError("%s: not delivered" % SCRIPT)
    _check_run(_flagless(), "summary.json")


def _check_wrote_outside_output() -> None:
    """Holds when the run started with no flags created a file outside the output folder.
    The instruction states that the program writes only into the output folder. The weight
    is negative, so it counts only against a program that wrote elsewhere."""
    case = _flagless()
    if case["run"]["returncode"] is None:
        raise AssertionError(case["run"]["note"])
    if not case["strays"]:
        raise AssertionError("nothing written outside %s" % OUT)
    print("written outside the output folder: %s" % ", ".join(case["strays"][:5]), file=sys.stderr)


_NETWORK_MODULES = {"socket", "ssl", "http", "urllib", "ftplib", "smtplib", "poplib",
                    "imaplib", "telnetlib", "xmlrpc", "asyncio", "socketserver"}


def _check_outside_library_import() -> None:
    """Holds when the delivered program imports a module from outside the Python 3
    standard library or a network module. The instruction states: "Use the Python 3
    standard library only, with no network access." The weight is negative, so it
    counts only against a program that does this."""
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"), filename=str(SCRIPT))
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names = [node.module]
        else:
            continue
        for name in names:
            root = name.split(".")[0]
            if root not in sys.stdlib_module_names or root in _NETWORK_MODULES:
                found.append(name)
    if not found:
        raise AssertionError("no outside or network import")
    print("outside or network imports: %s" % ", ".join(sorted(set(found))), file=sys.stderr)


def _check_hardcoded_sample_answers() -> None:
    """Holds when the delivered program's source carries every bus id that the shipped
    answers list as short (three or more). The instruction states: "It reads only the
    data folder it is given". The weight is negative, so it counts only against a program
    that does this."""
    source = SCRIPT.read_text(encoding="utf-8")
    rows = _shipped()["expected"]["policy_audit.json"]["buses"]
    marked = sorted(row["bus_id"] for row in rows if row["unmet_kwh"] > 0)
    hits = [bus for bus in marked if bus in source]
    if len(marked) < 3 or len(hits) < len(marked):
        raise AssertionError("no shipped answer ids in the program source")
    print("shipped answer ids in source: %s" % ", ".join(hits), file=sys.stderr)


def _holds(check, *args) -> bool:
    try:
        check(*args)
    except Exception as exc:
        print("%s%s: %s" % (check.__name__, args, exc), file=sys.stderr)
        return False
    return True


# ---- criteria ----
