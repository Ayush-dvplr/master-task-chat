"""Cost table driver: inject one wrong reading into the fixed package, rebuild the seven
artifacts the way solve.py does, and run the real test file against them.

usage: python3 -B cost_run.py <test_output.py> <row-name>=<FLAG+FLAG> ...
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

WORK = Path(__file__).resolve().parents[1]
FIXED = WORK / "project_fixed"
DATA = Path("/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/batch-lease-scheduler-replay/environment/data")
STUB = "/tmp/blsr/stub"

CLI = '''"""Command line entry (cost variant)."""
import json
import os
import sys

from .book import BookError, load_book
from ._heap import documents as heap_documents

FLAGS = frozenset(%r)


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 2:
        return 2
    data_dir, out_dir = args
    try:
        book = load_book(data_dir)
    except BookError as exc:
        print(exc.message())
        return 2
    model = {"lease": book.lease, "delay": book.delay, "pools": dict(book.pools), "sets": {}}
    for sid, spec in book.sets.items():
        model["sets"][sid] = {
            "workers": {w: list(v) for w, v in spec["workers"].items()},
            "jobs": {j: list(v) for j, v in spec["jobs"].items()},
            "work": dict(spec["work"]), "deps": [list(e) for e in spec["deps"]],
            "events": [{k: v for k, v in e.items() if k != "set"} for e in spec["events"]],
            "checkpoints": list(spec["checkpoints"])}
    names = ("module_core.json", "module_metrics.json", "dependency_resolution.json", "summary.json")
    os.makedirs(out_dir, exist_ok=True)
    for name, doc in zip(names, heap_documents(model, FLAGS)):
        with open(os.path.join(out_dir, name), "w", encoding="utf-8") as handle:
            json.dump(doc, handle, indent=1, sort_keys=True)
            handle.write("\\n")
    return 0
'''


PATCHES = {
    "MISSREV": ("src/leasebook/book.py", "for name in INPUT_FILES:", "for name in reversed(INPUT_FILES):"),
    "MISSDETAIL": ("src/leasebook/book.py", 'raise BookError("MISSING_INPUT", name)', 'raise BookError("MISSING_INPUT")'),
    "POLAFTER": ("src/leasebook/book.py", "    lease, delay = _read_policy(path(\"policy.ini\"))\n", ""),
    "NOCONFLICT": ("src/leasebook/book.py", "    _check_event_ids(sets)\n", ""),
    "CYCLEFIRST": ("src/leasebook/book.py", "    _check_event_ids(sets)\n    if any(_has_cycle(spec) for spec in sets.values()):\n        raise BookError(\"DEPENDENCY_CYCLE\")\n",
                   "    if any(_has_cycle(spec) for spec in sets.values()):\n        raise BookError(\"DEPENDENCY_CYCLE\")\n    _check_event_ids(sets)\n"),
    "NOCYCLE": ("src/leasebook/book.py", "    if any(_has_cycle(spec) for spec in sets.values()):\n        raise BookError(\"DEPENDENCY_CYCLE\")\n", ""),
    "UNKWORKER": ("src/leasebook/book.py", 'if event["type"] in WORKER_EVENTS and event["worker"] not in spec["workers"]:', 'if False:'),
    "BLANKCRASH": ("src/leasebook/book.py", "            if line.strip():\n                events.append", "            if True:\n                events.append"),
    "STDERR": ("src/leasebook/cli.py", "        print(exc.message())", "        print(exc.message(), file=sys.stderr)"),
    "EXIT1": ("src/leasebook/cli.py", "        print(exc.message())\n        return 2", "        print(exc.message())\n        return 1"),
    "WRITEFIRST": ("src/leasebook/cli.py", "        print(exc.message())\n", "        print(exc.message())\n        os.makedirs(out_dir, exist_ok=True)\n        open(os.path.join(out_dir, 'summary.json'), 'w').write('{}')\n"),
    "VERSION": ("src/leasebook/__init__.py", '__version__ = "1.4.0"', '__version__ = "1.4.1"'),
    "TESTEDIT": ("tests/test_book.py", "import os\n", "import os  # edited\n"),
    "NOMAIN": ("src/leasebook/__main__.py", None, None),
    "IDTEXT": ("src/leasebook/replay.py", "key=lambda j: (-j.priority, j.id))", "key=lambda j: (-j.priority, str(j.id)))"),
    "WORKERTEXT": ("src/leasebook/replay.py", "return min(idle, key=lambda w: w.id)", "return min(idle, key=lambda w: str(w.id))"),
}
ARTIFACT_PATCHES = ("SELFTEST", "UNSORTED", "SHA")


def apply_patch(tree, name):
    rel, old, new = PATCHES[name]
    target = tree / rel
    if old is None:
        target.unlink()
        return
    text = target.read_text()
    if old == "    lease, delay = _read_policy(path(\"policy.ini\"))\n":
        text = text.replace("    return Book(lease, delay, pools, sets)", old + "    return Book(lease, delay, pools, sets)")
    assert old in text, name
    target.write_text(text.replace(old, new, 1))


def pack(tree, archive):
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(p for p in tree.rglob("*") if p.is_file() and "__pycache__" not in p.parts):
            info = zipfile.ZipInfo(path.relative_to(tree).as_posix(), (1980, 1, 1, 0, 0, 0))
            info.external_attr = 0o644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, path.read_bytes())


def build(flags, out):
    scratch = Path(tempfile.mkdtemp(prefix="cost-"))
    tree = scratch / "pkg"
    shutil.copytree(FIXED, tree, ignore=shutil.ignore_patterns("__pycache__"))
    patches = [f[2:] for f in flags if f.startswith("P:")]
    arts = [f[2:] for f in flags if f.startswith("A:")]
    flags = [f for f in flags if ":" not in f]
    for name in patches:
        apply_patch(tree, name)
    if flags:
        shutil.copy(WORK / "engine" / "heap.py", tree / "src/leasebook/_heap.py")
        (tree / "src/leasebook/cli.py").write_text(CLI % sorted(flags))
    out.mkdir(parents=True, exist_ok=True)
    pack(tree, out / "package.zip")
    env = dict(os.environ, PYTHONPATH=str(tree / "src"), PYTHONDONTWRITEBYTECODE="1")
    run = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests"], cwd=tree,
                         capture_output=True, text=True, env=env)
    ran = int(re.search(r"Ran (\d+) test", run.stderr).group(1))
    bad = sum(int(x) for x in re.findall(r"(?:failures|errors|skipped)=(\d+)", run.stderr))
    version = "1.4.0"
    (out / "selftest.json").write_text(json.dumps({"package": "leasebook", "version": version,
                                                   "tests_run": ran, "tests_passed": ran - bad}))
    with zipfile.ZipFile(out / "package.zip") as zf:
        files = sorted(zf.namelist())
    sha = hashlib.sha256((out / "package.zip").read_bytes()).hexdigest()
    if "SELFTEST" in arts:
        (out / "selftest.json").write_text(json.dumps({"package": "leasebook", "version": version,
                                                       "tests_run": ran, "tests_passed": ran - bad - 1}))
    if "UNSORTED" in arts:
        files = files[::-1]
    if "SHA" in arts:
        sha = hashlib.sha256(b"x" + (out / "package.zip").read_bytes()).hexdigest()
    (out / "build_report.json").write_text(json.dumps({"package": "leasebook", "version": version,
                                                       "files": files, "archive_sha256": sha}))
    subprocess.run([sys.executable, "-c", "import sys, leasebook.cli as c; sys.exit(c.main(sys.argv[1:]))", str(DATA), str(out)], check=False, env=env)


def weights(test_file):
    return {m.group(1): int(m.group(2)) for m in re.finditer(r"^criteria\.(\w+)\(weight=(-?\d+)\)", test_file.read_text(), re.M)}


def score(test_file, out):
    local = out / "t_local.py"
    local.write_text(test_file.read_text().replace("Path(\"/app/out\")", "Path(%r)" % str(out)).replace("Path('/app/out')", "Path(%r)" % str(out)))
    res = subprocess.run([sys.executable, "-B", str(local)], capture_output=True, text=True,
                         env=dict(os.environ, PYTHONPATH=STUB), cwd=str(out))
    verdict = dict(reversed(line.split(" ", 1)) for line in res.stdout.splitlines() if line[:4] in ("PASS", "FAIL"))
    return {name: v == "PASS" for name, v in verdict.items()}


def main():
    test_file = Path(sys.argv[1])
    w = weights(test_file)
    pos = sum(x for x in w.values() if x > 0)
    rows = {}
    for arg in sys.argv[2:]:
        name, _, flagtxt = arg.partition("=")
        flags = [f for f in flagtxt.split("+") if f]
        out = Path(tempfile.mkdtemp(prefix="cost-out-"))
        build(flags, out)
        res = score(test_file, out)
        lost = [n for n, ok in res.items() if w[n] > 0 and not ok]
        neg = [n for n, ok in res.items() if w[n] < 0 and ok]
        pts = sum(w[n] for n in lost)
        tests_pct = 100.0 * (pos - pts - sum(-w[n] for n in neg)) / pos
        rows[name] = {"flags": flags, "lost_points": pts, "lost_pct": round(100.0 * pts / pos, 1),
                      "tests_pct": round(tests_pct, 1), "overall": round(0.5 * tests_pct + 45.0, 1),
                      "lost": lost, "negatives_hit": neg}
        print(name, rows[name]["lost_points"], rows[name]["lost_pct"], rows[name]["overall"], flush=True)
    target = Path(os.environ.get("COST_OUT", str(WORK / "cost" / "cost_rows.json")))
    merged = json.loads(target.read_text()) if target.exists() else {}
    merged.update(rows)
    target.write_text(json.dumps(merged, indent=1))


if __name__ == "__main__":
    main()
