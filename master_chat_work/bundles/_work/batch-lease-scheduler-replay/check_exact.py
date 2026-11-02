"""Second, independent recomputation of the four replay documents (G9).

Reads a book directory with its own parser, replays it with the unit-step
simulator engine/refsim.py (integer clock, one tick at a time, no heap), and
diffs every record against a directory of produced documents.  Never imports
or reads solution/solve.py.

usage:
  python3 -B check_exact.py book <book_dir> <out_dir>     per-record diff + invariants
  python3 -B check_exact.py generated <pkg_root> <n>       n generated sets vs the package
  python3 -B check_exact.py probe <book_dir> <pkg_root>    redelivery-removal probe
"""
import csv
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "engine"))
import refsim  # noqa: E402
import gen  # noqa: E402
from datagen import write_book  # noqa: E402

DOCS = ("module_core.json", "module_metrics.json", "dependency_resolution.json", "summary.json")


def parse_book(d):
    lease = delay = None
    section = None
    for line in open(os.path.join(d, "policy.ini"), encoding="utf-8"):
        line = line.strip()
        if line.startswith("["):
            section = line.strip("[]")
        elif "=" in line:
            key, val = (x.strip() for x in line.split("=", 1))
            if (section, key) == ("lease", "ticks"):
                lease = int(val)
            if (section, key) == ("retry", "delay"):
                delay = int(val)
    pools = {p["pool"]: p["preempt"] for p in json.load(open(os.path.join(d, "pools.json")))["pools"]}
    sets = {}
    for line in open(os.path.join(d, "checkpoints.txt"), encoding="utf-8"):
        if line.strip():
            sid, t = map(int, line.split())
            sets.setdefault(sid, {"workers": {}, "jobs": {}, "work": {}, "deps": [],
                                  "events": [], "checkpoints": []})["checkpoints"].append(t)

    def rows(name, sep):
        with open(os.path.join(d, name), newline="", encoding="utf-8") as fh:
            return [r for r in csv.DictReader(fh, delimiter=sep) if any(r.values())]
    for r in rows("workers.csv", ","):
        sets[int(r["set"])]["workers"][int(r["worker"])] = [r["pool"], r["state"] == "up"]
    for r in rows("jobs.tsv", "\t"):
        sets[int(r["set"])]["jobs"][int(r["job"])] = [r["pool"], int(r["priority"]), int(r["retry_limit"])]
    for r in rows("durations.csv", ","):
        sets[int(r["set"])]["work"][int(r["job"])] = int(r["work"])
    for r in rows("dependencies.csv", ","):
        sets[int(r["set"])]["deps"].append([int(r["parent"]), int(r["child"])])
    for line in open(os.path.join(d, "events.jsonl"), encoding="utf-8"):
        if line.strip():
            e = json.loads(line)
            sets[e.pop("set")]["events"].append(e)
    for s in sets.values():
        s["checkpoints"].sort()
    return {"lease": lease, "delay": delay, "pools": pools, "sets": sets}


def first_diff(a, b, path="$"):
    if type(a) is not type(b):
        return path
    if isinstance(a, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b:
                return "%s.%s" % (path, k)
            p = first_diff(a[k], b[k], "%s.%s" % (path, k))
            if p:
                return p
        return None
    if isinstance(a, list):
        if len(a) != len(b):
            return "%s[len %d vs %d]" % (path, len(a), len(b))
        for i, (x, y) in enumerate(zip(a, b)):
            p = first_diff(x, y, "%s[%d]" % (path, i))
            if p:
                return p
        return None
    return None if a == b else path


def invariants(book, core, metrics):
    for sid, s in book["sets"].items():
        body = core["sets"][str(sid)]
        for cp in body["checkpoints"]:
            busy = [j["worker"] for j in cp["jobs"].values() if j["state"] == "running"]
            assert len(busy) == len(set(busy)), (sid, cp["t"], "worker double-booked")
            for jid, j in cp["jobs"].items():
                limit = s["jobs"][int(jid)][2]
                assert 1 <= j["attempt"] <= limit + 1, (sid, jid, "attempt bound")
                assert 0 <= j["remaining"] <= s["work"][int(jid)], (sid, jid, "remaining bound")
                if j["state"] == "running":
                    assert cp["workers"][str(j["worker"])]["up"], (sid, jid, "down worker busy")
        tot = metrics["sets"][str(sid)]["totals"]
        assert tot["runs"] == len(body["dispatches"]), sid


def cmd_book(book_dir, out_dir):
    book = parse_book(book_dir)
    want = dict(zip(DOCS, refsim.documents(book)))
    bad = 0
    for name in DOCS:
        got = json.load(open(os.path.join(out_dir, name)))
        for sid in sorted(want[name]["sets"], key=int):
            p = first_diff(want[name]["sets"][sid], got["sets"].get(sid), "%s:%s" % (name, sid))
            if p:
                bad += 1
                if bad <= 10:
                    print("DIFF", p)
        extra = set(got["sets"]) - set(want[name]["sets"])
        bad += len(extra)
        if name == "summary.json" and got["set_count"] != want[name]["set_count"]:
            bad += 1
    invariants(book, want["module_core.json"], want["module_metrics.json"])
    print("book %s: %d sets, %d differing set-docs" % (book_dir, len(book["sets"]), bad))
    return bad


def run_pkg(pkg_root, book_dir, out_dir):
    env = dict(os.environ, PYTHONPATH=os.path.join(pkg_root, "src"), PYTHONDONTWRITEBYTECODE="1")
    subprocess.run([sys.executable, "-m", "leasebook", book_dir, out_dir], env=env, check=True)


def cmd_generated(pkg_root, n):
    scratch = tempfile.mkdtemp(prefix="cx-")
    bad = 0
    profiles = ("hidden", "shipped")
    for i in range(n):
        book = gen.make_book(1000 + i, profiles[i % 2], 1)
        bd, od = os.path.join(scratch, "b%d" % i), os.path.join(scratch, "o%d" % i)
        write_book(book, bd, seed=i, blank_every=7)
        run_pkg(pkg_root, bd, od)
        bad += cmd_book(bd, od) > 0
        shutil.rmtree(bd)
        shutil.rmtree(od)
    shutil.rmtree(scratch)
    print("generated: %d sets, %d disagree" % (n, bad))
    return bad


def cmd_probe(book_dir, pkg_root):
    scratch = tempfile.mkdtemp(prefix="cxp-")
    stripped = os.path.join(scratch, "book")
    shutil.copytree(book_dir, stripped)
    seen, kept, dropped = set(), [], 0
    for line in open(os.path.join(book_dir, "events.jsonl"), encoding="utf-8"):
        if not line.strip():
            continue
        e = json.loads(line)
        if (e["set"], e["id"]) in seen:
            dropped += 1
            continue
        seen.add((e["set"], e["id"]))
        kept.append(line if line.endswith("\n") else line + "\n")
    open(os.path.join(stripped, "events.jsonl"), "w", encoding="utf-8").writelines(kept)
    run_pkg(pkg_root, book_dir, os.path.join(scratch, "a"))
    run_pkg(pkg_root, stripped, os.path.join(scratch, "b"))
    a = json.load(open(os.path.join(scratch, "a", "module_core.json")))
    b = json.load(open(os.path.join(scratch, "b", "module_core.json")))
    moved = sum(1 for s in a["sets"] if a["sets"][s]["audit"] != b["sets"][s]["audit"])
    same_disp = all(a["sets"][s]["dispatches"] == b["sets"][s]["dispatches"] for s in a["sets"])
    shutil.rmtree(scratch)
    print("probe: dropped %d redelivered copies; audit moved in %d sets; dispatches unchanged=%s"
          % (dropped, moved, same_disp))
    return 0 if moved else 1


if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "book":
        sys.exit(1 if cmd_book(sys.argv[2], sys.argv[3]) else 0)
    if mode == "generated":
        sys.exit(1 if cmd_generated(sys.argv[2], int(sys.argv[3])) else 0)
    if mode == "probe":
        sys.exit(cmd_probe(sys.argv[2], sys.argv[3]))
    sys.exit(__doc__)
