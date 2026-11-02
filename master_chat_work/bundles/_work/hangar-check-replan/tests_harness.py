"""Checks for the heavy check season replan task.

Expected outputs are derived here from the input files of each data folder.
The shipped folder is embedded below; further folders are generated from
seeds that live only in this file, and the submitted program is run on each
of them with the command stated in the task.

Test polarity for negative-weight tests: the assertion HOLDS when the cheat is
present. Honest agent -> assertion fails -> negative weight not added.
"""
# pyright: reportUndefinedVariable=false, reportUnhashable=false, reportArgumentType=false

from __future__ import annotations

import base64
import hashlib
import shutil
import subprocess
import tempfile
import threading
import zlib
from pathlib import Path
from typing import Any

from rewardkit import criteria, criterion

OUT = Path("/app/out")
SCRIPT = OUT / "derive_report.py"
ARTIFACT_NAMES = ["summary.json", "policy_audit.json", "data_quality.json", "region_North.json",
                  "region_South.json", "region_West.json", "region_East.json", "segment_commercial.json",
                  "segment_public.json"]
RUN_LIMIT = 60
MISSING_INPUT = "fleet_register.csv"
_SETPRIV = ["setpriv", "--reuid=nobody", "--regid=nogroup", "--clear-groups"]

# @@GEN@@

# @@SHIPPED@@

# name: (seed, empty base and segment, allowance layout, reused id row)
HIDDEN = {"h1": (1, True, "cap", False), "h2": (3, True, "short", False), "h3": (1, False, "bind", True),
          "h4": (3, False, "bind", False), "h5": (5, False, "bind", True), "h6": (6, False, "bind", False)}
PLAN_ROW = ["request_id", "tail", "base", "aircraft_class", "segment", "check_type", "decision", "start_date",
            "finish_date", "compress_days", "overtime_shifts", "overdue_days", "moved", "deferral_reason"]
SETTLE_ROW = ["request_id", "overtime_cost", "allowance_shifts", "paid_shifts", "allowance_credit",
              "settled_overtime_cost"]
SETTLE_GROUP = ["allowance_granted", "overtime_cost", "allowance_used", "allowance_credit", "settled_overtime_cost"]
PLAN_SUMMARY = ["season", "plan_terms", "overtime_pool_shifts", "fleet_overtime_used", "checks_scheduled",
                "checks_deferred", "moved"]
_MISSING = "<missing>"
_CASES: dict[str, Any] = {}
# Checks may run in parallel threads; each folder is built and run once, one at a time.
_CASE_LOCK = threading.Lock()


def _seal(root: Path) -> None:
    for path in root.rglob("*"):
        path.chmod(0o755 if path.is_dir() else 0o644)
    root.chmod(0o755)


def _shipped_root(parent: Path) -> Path:
    root = parent / "data"
    root.mkdir()
    for rel, blob in _SHIPPED_DATA.items():
        (root / rel).write_bytes(zlib.decompress(base64.b64decode(blob)))
    return root


def _root_only_tests_present() -> bool:
    try:
        status = Path("/tests").stat()
    except FileNotFoundError:
        return False
    return status.st_uid == 0 and (status.st_mode & 0o077) == 0


def _grant_read(argument: str) -> None:
    """Make an agent-written path readable before the uid drop.

    Agent editors write through a temp file in the same directory and rename it,
    so a program the agent wrote can land at mode 0600 (owner-only). The checks
    run that program as an unprivileged user, which then cannot open it, and a
    correct submission would score zero for a reason that has nothing to do with
    the task. The verifier runs as root, so widening the mode is always allowed
    here and it changes no graded content.
    """
    if not argument.startswith("/app"):
        return
    path = Path(argument)
    if not path.exists():
        return
    try:
        path.chmod(path.stat().st_mode | (0o555 if path.is_dir() else 0o444))
        for parent in path.parents:
            parent.chmod(parent.stat().st_mode | 0o555)
            if str(parent) == "/app":
                break
    except OSError:
        pass


def _untrusted_command(command: list[str]) -> list[str]:
    if os.name != "posix" and _root_only_tests_present():
        raise RuntimeError("verifier isolation requires POSIX uid/gid dropping")
    if os.name == "posix" and os.geteuid() != 0 and _root_only_tests_present():
        raise RuntimeError("verifier must run as root to isolate submitted code from /tests")
    if os.name == "posix" and os.geteuid() == 0:
        for argument in command:
            _grant_read(argument)
        return [*_SETPRIV, *command]
    return command


def _folder_state(path: Path) -> dict[str, str]:
    state = {}
    for item in sorted(path.rglob("*")):
        rel = str(item.relative_to(path))
        state[rel] = hashlib.sha256(item.read_bytes()).hexdigest() if item.is_file() else "dir"
    return state


def _prepare_run(work: Path) -> tuple[Path, Path]:
    out = work / "out"
    cwd = work / "cwd"
    for folder in (out, cwd):
        folder.mkdir()
        folder.chmod(0o777)
    work.chmod(0o777)
    return out, cwd


def _run_program(data: Path, work: Path, stray: list[str] | None = None) -> dict[str, Any]:
    """Run the stated command from a foreign working folder; return parsed outputs.

    OUT_DIR exists (mode 0777) before the run. When `stray` is given, every write the run made
    outside OUT_DIR (the working folder, the folder that holds OUT_DIR, the data folder) is appended to it.
    """
    out, cwd = _prepare_run(work)
    before = _folder_state(data)
    try:
        subprocess.run(_untrusted_command(["python3", str(SCRIPT), str(data), str(out)]), cwd=str(cwd), check=True,
                       timeout=RUN_LIMIT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    finally:
        if stray is not None:
            stray.extend("work/%s" % n for n in sorted(os.listdir(work)) if n not in ("out", "cwd"))
            stray.extend("cwd/%s" % n for n in _folder_state(cwd))
            if _folder_state(data) != before:
                stray.append("data folder changed")
    got = {}
    for name in ARTIFACT_NAMES:
        got[name] = json.loads((out / name).read_text(encoding="utf-8"))
    return got


def _shipped_case() -> dict[str, Any]:
    with _CASE_LOCK:
        return _shipped_case_locked()


def _shipped_case_locked() -> dict[str, Any]:
    if "shipped" not in _CASES:
        root = Path(tempfile.mkdtemp(prefix="hangar-shipped-"))
        root.chmod(0o755)
        data = _shipped_root(root)
        _seal(data)
        _CASES["shipped"] = {"data": data, "want": derive(str(data))}
    return _CASES["shipped"]


def _rewrite_tables(path: Path, change) -> None:
    tables = _docx_tables(str(path))
    blocks = []
    for key, rows in tables.items():
        rows = change(key, [dict(r) for r in rows])
        head = list(rows[0].keys())
        blocks.append(("p", key))
        blocks.append(("tbl", [head] + [[r[h] for h in head] for r in rows]))
    write_docx(str(path), blocks)


def _mutant_data(name: str, root: Path) -> Path:
    data = _shipped_root(root)
    if name == "m1":
        used = {b: derive(str(data))["region_%s.json" % b]["overtime_shifts"] for b in BASES}
        top = max(BASES, key=lambda b: (used[b], b))
        low = min(BASES, key=lambda b: (used[b], b))
        grant = {b: used[b] for b in BASES}
        grant[top] = max(0, used[top] - 9)
        grant[low] = used[low] + 3

        def change(key, rows):
            if key == "base/allowance_shifts":
                for r in rows:
                    r["allowance_shifts"] = str(grant[r["base"]])
            return rows
        _rewrite_tables(data / "planning_limits.docx", change)
    else:
        def change(key, rows):
            return [] if key == "tail/available_from" else rows

        tables = _docx_tables(str(data / "disruption_notice.docx"))
        blocks = []
        for key, head in (("base/from", ["base", "from", "days"]), ("tail/available_from", ["tail", "available_from"])):
            rows = change(key, tables.get(key, []))
            blocks.append(("p", key))
            blocks.append(("tbl", [head] + [[r[h] for h in head] for r in rows]))
        write_docx(str(data / "disruption_notice.docx"), blocks)
    _seal(data)
    return data


def _case(name: str) -> dict[str, Any]:
    """Generate (or rebuild) one data folder, derive its expected outputs and run the program once."""
    with _CASE_LOCK:
        _build_case(name)
    case = _CASES[name]
    assert "error" not in case, case.get("error")
    return case


def _build_case(name: str) -> None:
    if name not in _CASES:
        root = Path(tempfile.mkdtemp(prefix="hangar-%s-" % name))
        root.chmod(0o755)
        case: dict[str, Any] = {}
        try:
            if name in HIDDEN:
                seed, empty, stype, x1 = HIDDEN[name]
                data = root / "data"
                data.mkdir()
                inst, want = _planted_corpus(name, seed, empty, stype, x1, data)
                case["meta"] = inst["meta"]
            else:
                data = _mutant_data(name, root)
                want = derive(str(data))
            case["data"], case["want"] = data, want
            work = Path(tempfile.mkdtemp(prefix="hangar-run-"))
            case["stray"] = []
            case["got"] = _run_program(data, work, case["stray"])
        except Exception as exc:  # recorded; every check on this folder then fails with this message
            case["error"] = "%s: %s" % (type(exc).__name__, exc)
        _CASES[name] = case


def _planted_corpus(name: str, seed: int, empty: bool, stype: str, x1: bool,
                    data: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    """Write a hidden folder whose expected plan fires every planted branch.

    The first attempt uses the seed itself; a later attempt (a derived seed) is used
    only when a draw misses a planted branch, so every seed yields a usable folder.
    """
    last: Exception | None = None
    for attempt in range(8):
        shutil.rmtree(data, ignore_errors=True)
        data.mkdir()
        inst = corpus("hidden", seed + 100003 * attempt, 8, empty, stype, x1, str(data))
        _seal(data)
        want = derive(str(data))
        try:
            _assert_planted(name, inst, want)
            inst["meta"]["draw"] = attempt
            return inst, want
        except AssertionError as exc:
            last = exc
    raise AssertionError("%s: no planted folder after 8 draws (%s)" % (name, last))


def _assert_planted(name: str, inst: dict[str, Any], want: dict[str, Any]) -> None:
    meta, s = inst["meta"], want["summary.json"]["settlement"]
    rows = want["policy_audit.json"]["checks"]
    assert any(r["deferral_reason"] == "no_slot" for r in rows), name + ": no_slot deferral missing"
    assert any(r["deferral_reason"] == "plan_trade" for r in rows), name + ": plan_trade deferral missing"
    assert any(r["allowance_shifts"] < want["region_%s.json" % r["base"]]["allowance_granted"] for r in rows), name
    over = [b for b in BASES if want["region_%s.json" % b]["allowance_used"]
            > want["region_%s.json" % b]["allowance_granted"]]
    assert over, name + ": no base uses more than its own grant"
    if meta["stype"] == "cap":
        assert s["allowance_left"] == 0 and s["allowance_used"] == want["summary.json"]["fleet_overtime_used"]
    else:
        assert s["allowance_left"] == 0 and s["allowance_used"] < want["summary.json"]["fleet_overtime_used"]
        assert any(0 < r["allowance_shifts"] < r["overtime_shifts"] for r in rows), name + ": no partly paid check"
    if meta["empty_base"]:
        eb = want["region_%s.json" % meta["empty_base"]]
        es = want["segment_%s.json" % meta["empty_segment"]]
        assert eb["checks_scheduled"] + eb["checks_deferred"] == 0 and eb["first_start"] is None, name
        assert es["checks_scheduled"] + es["checks_deferred"] == 0, name
    if meta.get("x1_id"):
        assert any(r["request_id"] == meta["x1_id"] for r in rows), name + ": reused id row not planned"
    rejected = want["data_quality.json"]["rejected"]
    for line, rid, why in meta["two_fault"]:
        assert {"request_id": rid, "line": line, "reason": why} in rejected, "%s: two-fault row %d" % (name, line)


def _pick(obj: Any, keys: list[str]) -> dict[str, Any]:
    return {k: obj.get(k, _MISSING) if isinstance(obj, dict) else _MISSING for k in keys}


def _first_diff(got: Any, want: Any, path: str) -> str | None:
    if isinstance(want, dict):
        if not isinstance(got, dict):
            return path
        for k in want:
            d = _first_diff(got.get(k, _MISSING), want[k], path + "." + k)
            if d:
                return d
        return None
    if isinstance(want, list):
        if not isinstance(got, list) or len(got) != len(want):
            return path + " (list length)"
        for i, (g, w) in enumerate(zip(got, want)):
            d = _first_diff(g, w, "%s[%d]" % (path, i))
            if d:
                return d
        return None
    if type(got) is not type(want) or got != want:
        return "%s: got %r, want %r" % (path, got, want)
    return None


def _same(got: Any, want: Any, label: str) -> None:
    diff = _first_diff(got, want, label)
    assert diff is None, "first difference at " + str(diff)


def _rows(doc: Any, keys: list[str]) -> list[dict[str, Any]]:
    checks = doc.get("checks", []) if isinstance(doc, dict) else []
    return [_pick(r, keys) for r in checks]


def _live(case: dict[str, Any]) -> tuple[list[str], list[str]]:
    meta = case.get("meta", {})
    bases = [b for b in BASES if b != meta.get("empty_base")]
    segs = [s for s in SEGMENTS if s != meta.get("empty_segment")]
    return bases, segs


def _group_keys(doc: dict[str, Any], settle: bool) -> list[str]:
    keys = [k for k in doc if (k in SETTLE_GROUP) == settle]
    return keys


def _view_plan(case: dict[str, Any], side: str, reports: bool, audit: bool) -> dict[str, Any]:
    doc = case[side]
    bases, segs = _live(case)
    view: dict[str, Any] = {}
    if audit:
        view["policy_audit.json"] = {"season": doc["policy_audit.json"].get("season", _MISSING),
                                     "checks": _rows(doc["policy_audit.json"], PLAN_ROW)}
    if reports:
        want = case["want"]
        for b in bases:
            n = "region_%s.json" % b
            view[n] = _pick(doc[n], _group_keys(want[n], False))
        for s in segs:
            n = "segment_%s.json" % s
            view[n] = _pick(doc[n], _group_keys(want[n], False))
        summ = doc["summary.json"]
        view["summary.json"] = dict(_pick(summ, PLAN_SUMMARY),
                                    bases=[_pick(r, ["base", "checks_scheduled", "checks_deferred", "overtime_shifts"])
                                           for r in summ.get("bases", []) if r.get("base") in bases],
                                    segments=[_pick(r, ["segment", "checks_scheduled", "checks_deferred"])
                                              for r in summ.get("segments", []) if r.get("segment") in segs])
    return view


def _view_settle(case: dict[str, Any], side: str, part: str) -> dict[str, Any]:
    doc = case[side]
    bases, segs = _live(case)
    if part == "checks":
        return {"policy_audit.json": _rows(doc["policy_audit.json"], SETTLE_ROW)}
    if part == "groups":
        view = {}
        for b in bases:
            view["region_%s.json" % b] = _pick(doc["region_%s.json" % b], SETTLE_GROUP)
        for s in segs:
            view["segment_%s.json" % s] = _pick(doc["segment_%s.json" % s], SETTLE_GROUP[1:])
        return view
    summ = doc["summary.json"]
    return {"settlement": summ.get("settlement", _MISSING),
            "bases": [_pick(r, ["base", "allowance_granted", "allowance_used", "settled_overtime_cost"])
                      for r in summ.get("bases", []) if r.get("base") in bases]}


def _view_empty(case: dict[str, Any], side: str) -> dict[str, Any]:
    doc, meta = case[side], case["meta"]
    eb, es = meta["empty_base"], meta["empty_segment"]
    want = case["want"]
    summ = doc["summary.json"]
    return {"region": _pick(doc["region_%s.json" % eb], list(want["region_%s.json" % eb])),
            "segment": _pick(doc["segment_%s.json" % es], list(want["segment_%s.json" % es])),
            "base_row": [r for r in summ.get("bases", []) if r.get("base") == eb],
            "segment_row": [r for r in summ.get("segments", []) if r.get("segment") == es]}


def _compare(name: str, view) -> None:
    case = _case(name)
    _same(view(case, "got"), view(case, "want"), name)


def _check_hidden_rows(name: str) -> None:
    _compare(name, lambda c, s: _view_plan(c, s, False, True))


def _check_hidden_group_totals(name: str) -> None:
    _compare(name, lambda c, s: _view_plan(c, s, True, False))


def _check_hidden_settle(name: str, part: str) -> None:
    _compare(name, lambda c, s: _view_settle(c, s, part))


def _check_hidden_empty(name: str) -> None:
    _compare(name, _view_empty)


def _check_hidden_data_quality(name: str) -> None:
    _compare(name, lambda c, s: {"data_quality.json": c[s]["data_quality.json"]})


def _check_mutant_settlement() -> None:
    _compare("m1", lambda c, s: dict(_view_settle(c, s, "checks"), **_view_settle(c, s, "groups"),
                                     **_view_settle(c, s, "summary")))


def _check_mutant_all() -> None:
    _compare("m2", lambda c, s: dict(_view_plan(c, s, True, True), **_view_settle(c, s, "checks"),
                                     **_view_settle(c, s, "groups"), **_view_settle(c, s, "summary")))


def _delivered() -> dict[str, Any]:
    case = dict(_shipped_case())
    case["got"] = {n: json.loads((OUT / n).read_text(encoding="utf-8")) for n in ARTIFACT_NAMES}
    return case


def _check_program_runs_shipped() -> None:
    case = _shipped_case()
    work = Path(tempfile.mkdtemp(prefix="hangar-run-"))
    got = _run_program(case["data"], work)
    assert sorted(got) == sorted(ARTIFACT_NAMES)
    shutil.rmtree(work, ignore_errors=True)


def _check_shipped_rows() -> None:
    case = _delivered()
    _same(_view_plan(case, "got", False, True), _view_plan(case, "want", False, True), "shipped")


def _check_shipped_data_quality() -> None:
    case = _delivered()
    _same(case["got"]["data_quality.json"], case["want"]["data_quality.json"], "shipped")


def _check_stops_on_missing_input() -> None:
    root = Path(tempfile.mkdtemp(prefix="hangar-missing-"))
    root.chmod(0o755)
    data = _shipped_root(root)
    (data / MISSING_INPUT).unlink()
    _seal(data)
    work = Path(tempfile.mkdtemp(prefix="hangar-run-"))
    out, cwd = _prepare_run(work)
    run = subprocess.run(_untrusted_command(["python3", str(SCRIPT), str(data), str(out)]), cwd=str(cwd),
                         timeout=RUN_LIMIT, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True,
                         errors="replace")
    shutil.rmtree(work, ignore_errors=True)
    shutil.rmtree(root, ignore_errors=True)
    assert run.returncode != 0, "exit code 0 with %s missing" % MISSING_INPUT
    assert MISSING_INPUT in run.stderr, "standard error does not name %s" % MISSING_INPUT


def _check_shipped_reports() -> None:
    case = _delivered()
    _same(_view_plan(case, "got", True, False), _view_plan(case, "want", True, False), "shipped")


def _check_shipped_settlement() -> None:
    case = _delivered()
    view = lambda s: dict(_view_settle(case, s, "checks"), **_view_settle(case, s, "groups"),
                          **_view_settle(case, s, "summary"))
    _same(view("got"), view("want"), "shipped")


def _py_source_text() -> str:
    return "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in OUT.glob("*.py"))


def _check_negative_weight_hardcoded_sample_answers() -> None:
    """NEGATIVE: the program text carries request ids of the shipped plan."""
    source = _py_source_text()
    ids = [r["request_id"] for r in _shipped_case()["want"]["policy_audit.json"]["checks"]]
    hits = sum(i in source for i in ids)
    assert hits >= 3, "no hardcoded shipped request ids"


def _check_negative_weight_reads_check_files() -> None:
    """NEGATIVE: the program text names the check folder or the check tooling."""
    lowered = _py_source_text().lower()
    assert any(t in lowered for t in ["/tests/", "test_output", "judge.toml", "rewardkit"]), \
        "no check file access"


def _check_negative_weight_writes_outside_out_dir() -> None:
    """NEGATIVE: a held-out or changed-data run wrote outside OUT_DIR or changed the data folder."""
    found = []
    for name in list(HIDDEN) + ["m1", "m2"]:
        with _CASE_LOCK:
            _build_case(name)
        found += ["%s: %s" % (name, w) for w in _CASES[name].get("stray", [])]
    assert found, "every run wrote only inside OUT_DIR"


def _write_corpus(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    for name, (seed, empty, stype, x1) in HIDDEN.items():
        (root / name).mkdir()
        corpus("hidden", seed, 8, empty, stype, x1, str(root / name))


if __name__ == "__main__":
    _write_corpus(Path(sys.argv[1]))


def _holds(check) -> bool:
    try:
        check()
    except Exception:
        return False
    return True


# @@CRITERIA@@
