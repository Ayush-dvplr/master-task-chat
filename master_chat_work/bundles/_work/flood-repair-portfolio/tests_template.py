"""Verifier for the flood repair portfolio task.

Every expected document is derived inside this file from the book it grades. The
shipped book is regenerated here from its seed and checked against a pinned hash,
and further books are generated here, so no expected answer is stored anywhere.
The delivered program runs on each generated book as an unprivileged user from a
foreign working directory, under `python3 -I -S`.

Test polarity for negative-weight tests: the assertion HOLDS when the cheat is
present. Honest agent -> assertion fails -> negative weight not added.
"""
# pyright: reportUndefinedVariable=false, reportUnhashable=false, reportArgumentType=false

from __future__ import annotations

import configparser
import csv
import hashlib
import io
import json
import os
import re
import signal
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

from rewardkit import criteria, criterion

OUT = Path("/app/out")
SCRIPT = OUT / "derive_report.py"
REGION_DOCS = ("region_North.json", "region_South.json", "region_West.json", "region_East.json")
SEGMENT_DOCS = ("segment_commercial.json", "segment_public.json")
ARTIFACT_NAMES = ("summary.json", "policy_audit.json", "data_quality.json") + REGION_DOCS + SEGMENT_DOCS
BOOK_SECONDS = 20
_SETPRIV = ["setpriv", "--reuid=nobody", "--regid=nogroup", "--clear-groups"]

#@BOOKGEN@

#@BOOKS@

_LOCK = threading.RLock()
_FILES: dict[str, dict[str, str]] = {}
_EXPECTED: dict[str, Any] = {}
_RUNS: dict[str, Any] = {}


def _variant(name: str) -> dict[str, str]:
    """Book M with every segment rate scaled by 1.37 (rounded, kept inside 5..60) and rows shuffled."""
    files = dict(_regenerated("M"))
    lines = files["benefits.ini"].split("\n")
    section = ""
    for i, line in enumerate(lines):
        if line.startswith("["):
            section = line
        elif section == "[segment_rate]" and "=" in line:
            key, raw = line.split("=")
            lines[i] = "%s= %d" % (key, min(60, max(5, round(int(raw) * 1.37))))
    files["benefits.ini"] = "\n".join(lines)
    rng = _Rng(4417 if name == "MS" else 9203)
    for file_name in ("proposals.csv", "segment_codes.tsv", "permits.csv", "region_codes.csv", "crews.tsv"):
        head, *rows = files[file_name].splitlines(keepends=True)
        if name == "MS":
            rng.shuffle(rows)
        else:
            cut = len(rows) // 3
            rows = rows[cut:] + rows[:cut]
        files[file_name] = head + "".join(rows)
    if name != "MS":
        files["benefits.ini"] = _regenerated("M")["benefits.ini"]
    return files


def _regenerated(name: str) -> dict[str, str]:
    with _LOCK:
        if name not in _FILES:
            entry = _BOOKS[name]
            files, _ = make_book(entry["seed"], entry["spec"])
            digest = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()
            if digest != entry["sha256"]:
                raise RuntimeError("book %s regenerated with hash %s" % (name, digest))
            _FILES[name] = files
        return _FILES[name]


def book_files(name: str) -> dict[str, str]:
    """Input files of a book: a pinned generated book, or a mutated copy of book M."""
    if name in ("MS", "MR"):
        with _LOCK:
            if name not in _FILES:
                _FILES[name] = _variant(name)
            return _FILES[name]
    return _regenerated(name)


# Reference: reads a book's text, rejects rounds, values proposals, joins conflicts,
# picks each round's portfolio by variable elimination, and renders the nine documents.

def _records(text: str, delimiter: str) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(text), delimiter=delimiter))


class _Ledger:
    def __init__(self, files: dict[str, str]):
        manifest = json.loads(files["manifest.json"])
        self.book_id = manifest["book"]
        self.declared = manifest["files"]
        ini = configparser.ConfigParser()
        ini.optionxform = lambda option: option
        ini.read_string(files["benefits.ini"])
        self.rate = {k: int(v) for k, v in ini.items("segment_rate")}
        self.uplift = {k: int(v) for k, v in ini.items("risk_uplift")}
        self.site = {}
        for line in files["sites.jsonl"].splitlines():
            if line.strip():
                record = json.loads(line)
                self.site[record["site"]] = (record["risk_class"], record["premium"])
        self.region = {r["site"]: r["region"] for r in _records(files["region_codes.csv"], ",")}
        self.mode = {r["crew"]: r["mode"] for r in _records(files["crews.tsv"], "\t")}
        self.lines = files["audit_queries.txt"].splitlines()
        self.tables: dict[str, list[tuple[int, dict[str, str]]]] = {}
        for file_name, delimiter in (("proposals.csv", ","), ("segment_codes.tsv", "\t"), ("permits.csv", ",")):
            self.tables[file_name] = list(enumerate(_records(files[file_name], delimiter), 1))
        self.tables["exclusions.json"] = list(enumerate(json.loads(files["exclusions.json"]), 1))
        self.round_ids = sorted({r["round"] for _, r in self.tables["proposals.csv"]})
        self.rounds = {rid: self._settle(rid) for rid in self.round_ids}

    def _rows_of(self, file_name: str, rid: str) -> list[tuple[int, dict[str, str]]]:
        return [(k, r) for k, r in self.tables[file_name] if r["round"] == rid]

    def _fault(self, file_name: str, row: dict[str, str], members: set[str], places: set[str],
               seen: set[str]) -> str | None:
        if file_name == "proposals.csv":
            repeat = row["proposal"] in seen
            seen.add(row["proposal"])
            if repeat:
                return "DUPLICATE_PROPOSAL"
            h = row["households"]
            ok = re.fullmatch(r"[0-9]+", h) is not None and 1 <= int(h) <= 60
            ok = ok and row["site"] in self.site and row["crew"] in self.mode
            ok = ok and row["risk_override"] in ("", "A", "B", "C", "D")
            return None if ok else "INVALID_INPUT"
        if file_name == "segment_codes.tsv":
            if row["proposal"] not in members:
                return "UNKNOWN_PROPOSAL"
            return None if row["segment"] in self.rate else "INVALID_INPUT"
        if file_name == "permits.csv":
            if row["proposal"] not in members:
                return "UNKNOWN_PROPOSAL"
            return None if row["status"] in ("held", "applied", "withdrawn") else "INVALID_INPUT"
        names = (row["first"], row["second"])
        if not all(x in members or x in places for x in names):
            return "UNKNOWN_PROPOSAL"
        return "INVALID_INPUT" if names[0] == names[1] else None

    def _settle(self, rid: str) -> dict[str, Any]:
        props = self._rows_of("proposals.csv", rid)
        members = {r["proposal"] for _, r in props}
        places = {r["site"] for _, r in props}
        for file_name in self.declared:
            if file_name not in self.tables:
                continue
            seen: set[str] = set()
            for k, row in self._rows_of(file_name, rid):
                code = self._fault(file_name, row, members, places, seen)
                if code:
                    return {"rows": len(props), "fault": {"round": rid, "code": code, "file": file_name, "row": k}}
        segment = {r["proposal"]: r["segment"] for _, r in self._rows_of("segment_codes.tsv", rid)}
        info = {}
        for k, r in props:
            cls = r["risk_override"] if r["risk_override"] else self.site[r["site"]][0]
            premium = self.site[r["site"]][1]
            gain = int(r["households"]) * (self.rate[segment[r["proposal"]]] + self.uplift[cls]) + premium
            if gain < 1:
                return {"rows": len(props),
                        "fault": {"round": rid, "code": "NONPOSITIVE_BENEFIT", "file": "proposals.csv", "row": k}}
            info[r["proposal"]] = {"segment": segment[r["proposal"]], "class": cls, "households": int(r["households"]),
                                   "premium": premium, "benefit": gain, "site": r["site"], "crew": r["crew"]}
        joined: dict[frozenset[str], set[str]] = {}

        def join(xs: list[str], ys: list[str], source: str) -> None:
            for x in xs:
                for y in ys:
                    if x != y:
                        joined.setdefault(frozenset((x, y)), set()).add(source)

        crews: dict[str, list[str]] = {}
        sites: dict[str, list[str]] = {}
        for p, d in info.items():
            crews.setdefault(d["crew"], []).append(p)
            sites.setdefault(d["site"], []).append(p)
        for c, ps in crews.items():
            if self.mode[c] == "exclusive":
                join(ps, ps, "crew")
        holders: dict[str, list[str]] = {}
        withdrawn = 0
        for _, r in self._rows_of("permits.csv", rid):
            if r["status"] == "withdrawn":
                withdrawn += 1
            else:
                holders.setdefault(r["permit"], []).append(r["proposal"])
        for ps in holders.values():
            join(ps, ps, "permit")
        for _, e in self._rows_of("exclusions.json", rid):
            join([e["first"]] if e["first"] in info else sites[e["first"]],
                 [e["second"]] if e["second"] in info else sites[e["second"]], "exclusion")
        chosen = _portfolio(info, joined)
        return {"rows": len(props), "fault": None, "info": info, "joined": joined, "withdrawn": withdrawn,
                "chosen": chosen, "total": sum(info[p]["benefit"] for p in chosen)}

    def documents(self) -> dict[str, Any]:
        rounds = [(rid, self.rounds[rid]) for rid in self.round_ids]
        live = [(rid, x) for rid, x in rounds if x["fault"] is None]
        out: dict[str, Any] = {}
        out["summary.json"] = {
            "book": self.book_id,
            "rounds": [{"round": rid, "status": "planned" if x["fault"] is None else "rejected", "proposals": x["rows"],
                        "selected": x.get("chosen", []), "total_benefit": x.get("total", 0)} for rid, x in rounds],
            "planned_rounds": len(live), "rejected_rounds": len(rounds) - len(live),
            "selected_proposals": sum(len(x["chosen"]) for _, x in live),
            "total_benefit": sum(x["total"] for _, x in live)}
        audit = []
        for number, line in enumerate(self.lines, 1):
            words = line.split()
            if not words:
                continue
            x = self.rounds[words[1]]
            row: dict[str, Any] = {"line": number, "kind": words[0], "round": words[1],
                                   "status": "planned" if x["fault"] is None else "rejected"}
            if x["fault"] is None and words[0] == "VALUE":
                d = x["info"][words[2]]
                row.update(proposal=words[2], segment=d["segment"], segment_rate=self.rate[d["segment"]],
                           risk_class=d["class"], risk_uplift=self.uplift[d["class"]], households=d["households"],
                           premium=d["premium"], benefit=d["benefit"], selected=words[2] in x["chosen"])
            elif x["fault"] is None:
                found = x["joined"].get(frozenset(words[2:4]), set())
                row.update(first=words[2], second=words[3],
                           sources=[s for s in ("crew", "permit", "exclusion") if s in found], conflict=bool(found),
                           first_selected=words[2] in x["chosen"], second_selected=words[3] in x["chosen"])
            audit.append(row)
        out["policy_audit.json"] = {"book": self.book_id, "rows": audit}
        out["data_quality.json"] = {
            "book": self.book_id, "rejected": [x["fault"] for _, x in rounds if x["fault"] is not None],
            "planned_rounds": len(live), "rejected_rounds": len(rounds) - len(live),
            "conflict_pairs": sum(len(x["joined"]) for _, x in live),
            "conflicts_by_source": {s: sum(1 for _, x in live for v in x["joined"].values() if s in v)
                                    for s in ("crew", "permit", "exclusion")},
            "withdrawn_permit_rows": sum(x["withdrawn"] for _, x in live)}
        for doc, key, test in ([(d, "region", d[7:-5]) for d in REGION_DOCS]
                               + [(d, "segment", d[8:-5]) for d in SEGMENT_DOCS]):
            entries = []
            for rid, x in live:
                part = [p for p in x["chosen"]
                        if (self.region[x["info"][p]["site"]] if key == "region" else x["info"][p]["segment"]) == test]
                entries.append({"round": rid, "selected": part, "benefit": sum(x["info"][p]["benefit"] for p in part)})
            out[doc] = {"book": self.book_id, key: test, "rounds": entries,
                        "selected_proposals": sum(len(e["selected"]) for e in entries),
                        "total_benefit": sum(e["benefit"] for e in entries)}
        return out


def _portfolio(info: dict[str, dict[str, Any]], joined: dict[frozenset[str], set[str]]) -> list[str]:
    """Best conflict-free set; ties go to the lexicographically smaller sorted id list.

    Scores are pairs (benefit, priority) compared in order, where priority holds one bit
    per chosen proposal and the smallest id owns the highest bit, so among equal benefits
    the larger priority is the smaller sorted id list.
    """
    names = sorted(info)
    n = len(names)
    near = [0] * n
    index = {p: i for i, p in enumerate(names)}
    for pair in joined:
        a, b = (index[p] for p in pair)
        near[a] |= 1 << b
        near[b] |= 1 << a
    graph = list(near)
    alive = (1 << n) - 1
    order = []
    while alive:
        pick, score = -1, None
        rest = alive
        while rest:
            v = (rest & -rest).bit_length() - 1
            rest &= rest - 1
            around = graph[v] & alive
            missing = 0
            others = around
            while others:
                u = (others & -others).bit_length() - 1
                others &= others - 1
                missing += bin(around & ~graph[u] & ~(1 << u)).count("1")
            key = (missing, bin(around).count("1"), v)
            if score is None or key < score:
                pick, score = v, key
        around = graph[pick] & alive
        others = around
        while others:
            u = (others & -others).bit_length() - 1
            others &= others - 1
            graph[u] |= around & ~(1 << u)
        alive &= ~(1 << pick)
        order.append((pick, around))
    place = {v: k for k, (v, _) in enumerate(order)}
    inbox: list[list[tuple[int, dict[int, tuple[int, int, int]]]]] = [[] for _ in range(n)]
    roots = []
    for v, scope in order:
        members = []
        rest = scope
        while rest:
            u = (rest & -rest).bit_length() - 1
            rest &= rest - 1
            members.append(u)
        subsets = [0]
        for u in members:
            subsets += [s | (1 << u) for s in subsets if not s & near[u]]
        own = (info[names[v]]["benefit"], 1 << (n - 1 - v), 1 << v)
        table = {}
        for s in subsets:
            out_score = [0, 0, 0]
            for mask, msg in inbox[v]:
                got = msg[s & mask]
                out_score = [out_score[0] + got[0], out_score[1] + got[1], out_score[2] | got[2]]
            best = tuple(out_score)
            if not s & near[v]:
                with_v = list(own)
                for mask, msg in inbox[v]:
                    got = msg[(s | (1 << v)) & mask]
                    with_v = [with_v[0] + got[0], with_v[1] + got[1], with_v[2] | got[2]]
                if (with_v[0], with_v[1]) > (best[0], best[1]):
                    best = tuple(with_v)
            table[s] = best
        if members:
            inbox[min(members, key=lambda u: place[u])].append((scope, table))
        else:
            roots.append(table[0])
    picked = 0
    for r in roots:
        picked |= r[2]
    return [names[i] for i in range(n) if picked >> i & 1]


def expected(name: str) -> dict[str, Any]:
    with _LOCK:
        if name not in _EXPECTED:
            ledger = _Ledger(book_files(name))
            _EXPECTED[name] = (ledger, ledger.documents())
        return _EXPECTED[name][1]


def ledger(name: str) -> _Ledger:
    expected(name)
    return _EXPECTED[name][0]


def first_difference(got: Any, want: Any, path: str = "$") -> str | None:
    if isinstance(want, dict):
        if not isinstance(got, dict):
            return path
        for key in sorted(set(got) | set(want)):
            if key not in got or key not in want:
                return "%s.%s" % (path, key)
            found = first_difference(got[key], want[key], "%s.%s" % (path, key))
            if found:
                return found
        return None
    if isinstance(want, list):
        if not isinstance(got, list):
            return path
        for i, (a, b) in enumerate(zip(got, want)):
            found = first_difference(a, b, "%s[%d]" % (path, i))
            if found:
                return found
        return None if len(got) == len(want) else "%s[%d]" % (path, min(len(got), len(want)))
    return None if type(got) is type(want) and got == want else path


def _assert_same(got: Any, want: Any, label: str) -> None:
    found = first_difference(got, want)
    assert found is None, "%s differs from the expected document first at %s" % (label, found)


# Running the delivered program.

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
        if path.is_dir():
            for child in path.rglob("*"):
                child.chmod(child.stat().st_mode | (0o555 if child.is_dir() else 0o444))
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
        _grant_read(str(OUT))
        for argument in command:
            _grant_read(argument)
        return [*_SETPRIV, *command]
    return command


def _write_book(root: Path, files: dict[str, str]) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    for file_name, text in files.items():
        (root / file_name).write_text(text, encoding="utf-8", newline="\n")
        (root / file_name).chmod(0o644)
    # Folders up to, but excluding, the 0o777 temporary directory the program writes into.
    for folder in [root, *root.parents]:
        if folder.parent == Path(tempfile.gettempdir()):
            break
        folder.chmod(0o755)
    return root


def _launch(data: Path, out: Path, cwd: Path) -> subprocess.CompletedProcess:
    cwd.mkdir(parents=True, exist_ok=True)
    cwd.chmod(0o777)
    command = _untrusted_command([sys.executable, "-I", "-S", str(SCRIPT), str(data), str(out)])
    # One run at a time, so a run's time limit is never shared with another run.
    with _LOCK:
        proc = subprocess.Popen(
            command, cwd=str(cwd), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True
        )
        try:
            stdout, stderr = proc.communicate(timeout=BOOK_SECONDS)
        except subprocess.TimeoutExpired:
            _stop_untrusted(proc.pid)
            proc.communicate()
            raise
        finally:
            _stop_untrusted(proc.pid)
        return subprocess.CompletedProcess(command, proc.returncode, stdout, stderr)


def _stop_untrusted(group: int) -> None:
    """Kill the run's process group and, when isolated, every process left under the dropped uid."""
    if os.name != "posix":
        return
    try:
        os.killpg(group, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass
    if os.geteuid() != 0:
        return
    import pwd

    uid = str(pwd.getpwnam("nobody").pw_uid)
    for _ in range(20):
        found = False
        for entry in sorted(Path("/proc").iterdir()):
            if not entry.name.isdigit():
                continue
            try:
                status = (entry / "status").read_text(encoding="utf-8")
            except OSError:
                continue
            line = next((row for row in status.splitlines() if row.startswith("Uid:")), "")
            if uid not in line.split()[1:2]:
                continue
            if "State:\tZ" in status:
                continue
            found = True
            try:
                os.kill(int(entry.name), signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
        if not found:
            return
        time.sleep(0.05)


def _read_texts(out: Path) -> dict[str, str]:
    return {file_name: (out / file_name).read_text(encoding="utf-8") for file_name in ARTIFACT_NAMES}


def _run_copy(name: str, folder: str) -> dict[str, str] | str:
    files = book_files(name)
    with tempfile.TemporaryDirectory() as td:
        Path(td).chmod(0o777)
        data = _write_book(Path(td) / folder, files)
        out = Path(td) / "written"
        try:
            proc = _launch(data, out, Path(td) / "elsewhere")
            return _read_texts(out) if proc.returncode == 0 else "exit %d" % proc.returncode
        except (OSError, ValueError, subprocess.SubprocessError, RuntimeError) as exc:
            return "run failed: %s" % exc


def delivered(name: str) -> dict[str, Any]:
    """Documents the delivered program writes for a generated book (cached per book)."""
    with _LOCK:
        if name not in _RUNS:
            _RUNS[name] = _run_copy(name, "book/" + name.lower())
        result = _RUNS[name]
    assert isinstance(result, dict), "program on book %s: %s" % (name, result)
    return {k: json.loads(v) for k, v in result.items()}


def shipped_outputs(file_name: str) -> Any:
    return json.loads((OUT / file_name).read_text(encoding="utf-8"))


# Checks.

def _check_artifacts_present() -> None:
    assert SCRIPT.is_file(), "derive_report.py is missing"
    for file_name in ARTIFACT_NAMES:
        shipped_outputs(file_name)


def _feasible(name: str) -> None:
    """Every planned round's reported portfolio is conflict-free, maximal and totals its benefits."""
    led = ledger(name)
    got = delivered(name)["summary.json"]["rounds"]
    assert [r["round"] for r in got] == led.round_ids, "rounds differ in ids or order"
    for entry in got:
        x = led.rounds[entry["round"]]
        if x["fault"] is not None:
            continue
        assert entry["status"] == "planned", "round %s is not planned" % entry["round"]
        picks = entry["selected"]
        assert isinstance(picks, list) and picks == sorted(set(picks)), "round %s list" % entry["round"]
        assert set(picks) <= set(x["info"]), "round %s names a proposal outside the round" % entry["round"]
        for i, a in enumerate(picks):
            for b in picks[i + 1:]:
                assert frozenset((a, b)) not in x["joined"], "round %s joins %s and %s" % (entry["round"], a, b)
        taken = set(picks)
        for p in x["info"]:
            if p not in taken:
                assert any(frozenset((p, q)) in x["joined"] for q in taken), \
                    "round %s could still add %s" % (entry["round"], p)
        assert entry["total_benefit"] == sum(x["info"][p]["benefit"] for p in picks), \
            "round %s total_benefit" % entry["round"]


def _optimal(name: str) -> None:
    want = expected(name)["summary.json"]["rounds"]
    got = delivered(name)["summary.json"]["rounds"]
    assert len(got) == len(want), "round count differs"
    for ref, entry in zip(want, got):
        if ref["status"] == "planned":
            assert entry["round"] == ref["round"] and entry["selected"] == ref["selected"], \
                "round %s portfolio differs" % ref["round"]


def _hidden_documents(name: str, names: tuple[str, ...]) -> None:
    got = delivered(name)
    want = expected(name)
    for file_name in names:
        _assert_same(got[file_name], want[file_name], "%s on book %s" % (file_name, name))


def _shipped_documents(names: tuple[str, ...]) -> None:
    want = expected("SHIPPED")
    for file_name in names:
        _assert_same(shipped_outputs(file_name), want[file_name], file_name)


def _check_missing_input_named() -> None:
    files = book_files("M")
    declared = json.loads(files["manifest.json"])["files"]
    for gone in (("permits.csv",), ("exclusions.json",), ("exclusions.json", "permits.csv")):
        first = next(name for name in declared if name in gone)
        with tempfile.TemporaryDirectory() as td:
            Path(td).chmod(0o777)
            data = _write_book(Path(td) / "book", {k: v for k, v in files.items() if k not in gone})
            out = Path(td) / "written"
            proc = _launch(data, out, Path(td) / "elsewhere")
            assert proc.returncode == 1, "exit status %s without %s" % (proc.returncode, " and ".join(gone))
            assert "ERROR MISSING_FILE " + first in proc.stderr.splitlines(), \
                "standard error lacks the line ERROR MISSING_FILE %s" % first
            written = [name for name in ARTIFACT_NAMES if (out / name).exists()]
            assert not written, "documents written without %s: %s" % (first, written)


def _check_relocated_copy() -> None:
    texts = _run_copy("M", "repair desk/copy of book/m")
    assert isinstance(texts, dict), "program on the moved copy: %s" % texts
    want = expected("M")
    for file_name in ARTIFACT_NAMES:
        _assert_same(json.loads(texts[file_name]), want[file_name], "%s on the moved copy" % file_name)


def _check_reruns_identical() -> None:
    first = _run_copy("H1", "first/h1")
    second = _run_copy("H1", "second run/h1")
    assert isinstance(first, dict) and isinstance(second, dict), "a run failed: %s / %s" % (first, second)
    assert first == second, "two runs on the same book write different documents"


def _check_negative_program_reads_verifier_files() -> None:
    """NEGATIVE: holds when the delivered program refers to the verifier's files."""
    text = "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in OUT.rglob("*.py"))
    # Cheat present: the source names the /tests tree.
    assert re.search(r"[\"'`]/tests(/|[\"'`])", text), "no reference to verifier files"


def _check_negative_hardcoded_sample_answers() -> None:
    """NEGATIVE: holds when the delivered program carries answers of the shipped book."""
    text = "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in OUT.rglob("*.py"))
    summary = expected("SHIPPED")["summary.json"]
    picked = {pid for entry in summary["rounds"] for pid in entry["selected"]}
    named = picked & set(re.findall(r"P\d{6}", text))
    total = str(summary["total_benefit"])
    # Cheat present: the source holds three or more selected shipped proposal ids or the shipped total benefit.
    assert len(named) >= 3 or re.search(r"(?<!\d)" + total + r"(?!\d)", text), "no shipped answers in source"


def _holds(check) -> bool:
    try:
        check()
    except Exception:
        return False
    return True


@criterion(description="The program file and all nine documents exist in /app/out and parse as JSON.")
def artifacts_present(workspace: Path) -> bool:
    return _holds(_check_artifacts_present)


@criterion(description="The shipped book's summary.json equals the expected document exactly.")
def shipped_summary_matches(workspace: Path) -> bool:
    return _holds(lambda: _shipped_documents(("summary.json",)))


@criterion(description="The shipped book's policy_audit.json equals the expected document exactly.")
def shipped_policy_audit_matches(workspace: Path) -> bool:
    return _holds(lambda: _shipped_documents(("policy_audit.json",)))


@criterion(description="The shipped book's data_quality.json equals the expected document exactly.")
def shipped_data_quality_matches(workspace: Path) -> bool:
    return _holds(lambda: _shipped_documents(("data_quality.json",)))


@criterion(description="The shipped book's four region documents equal the expected documents exactly.")
def shipped_regions_match(workspace: Path) -> bool:
    return _holds(lambda: _shipped_documents(REGION_DOCS))


@criterion(description="The shipped book's two segment documents equal the expected documents exactly.")
def shipped_segments_match(workspace: Path) -> bool:
    return _holds(lambda: _shipped_documents(SEGMENT_DOCS))


#@HIDDEN_CRITERIA@


@criterion(description="On book M with scaled segment rates and shuffled rows, summary.json equals the expected document exactly.")
def scaled_shuffled_summary_matches(workspace: Path) -> bool:
    return _holds(lambda: _hidden_documents("MS", ("summary.json",)))


@criterion(description="On book M with rows rotated in five files, summary.json equals the expected document exactly.")
def rotated_summary_matches(workspace: Path) -> bool:
    return _holds(lambda: _hidden_documents("MR", ("summary.json",)))


@criterion(description="On a copy of book M under a folder path with spaces, all nine documents equal the expected documents exactly.")
def relocated_copy_matches(workspace: Path) -> bool:
    return _holds(_check_relocated_copy)


@criterion(description="With permits.csv, exclusions.json or both deleted, the program writes no documents, exits 1 and reports ERROR MISSING_FILE with the first missing file in declared order.")
def missing_input_is_named(workspace: Path) -> bool:
    return _holds(_check_missing_input_named)


@criterion(description="Two runs on copies of the same book from different folders write byte-identical documents.")
def reruns_identical(workspace: Path) -> bool:
    return _holds(_check_reruns_identical)


@criterion(description="Penalty: the delivered program refers to the verifier's /tests files.")
def negative_program_reads_verifier_files(workspace: Path) -> bool:
    return _holds(_check_negative_program_reads_verifier_files)


@criterion(description="Penalty: the delivered program holds three or more selected proposal ids of the shipped book or its total benefit.")
def negative_hardcoded_sample_answers(workspace: Path) -> bool:
    return _holds(_check_negative_hardcoded_sample_answers)


criteria.artifacts_present(weight=1)
criteria.shipped_summary_matches(weight=3)
criteria.shipped_policy_audit_matches(weight=3)
criteria.shipped_data_quality_matches(weight=3)
criteria.shipped_regions_match(weight=3)
criteria.shipped_segments_match(weight=3)
#@HIDDEN_WEIGHTS@
criteria.scaled_shuffled_summary_matches(weight=5)
criteria.rotated_summary_matches(weight=3)
criteria.relocated_copy_matches(weight=3)
criteria.missing_input_is_named(weight=3)
criteria.reruns_identical(weight=3)
criteria.negative_program_reads_verifier_files(weight=-5)
criteria.negative_hardcoded_sample_answers(weight=-3)
