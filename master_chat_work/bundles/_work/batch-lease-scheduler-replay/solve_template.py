"""Repair the leasebook package, ship it as a zip and replay the shipped book.

Stages: unpack project.zip, replace the faulty sources, zip the repaired tree,
run the archive's own tests, replay /app/data, then cross-check every
written document against figures recomputed here from the other documents.
"""
import csv
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from collections import Counter
from pathlib import Path

DATA = Path("/app/data")
OUT = Path("/app/out")
WORK = Path("/app/build")
PACKAGE = "leasebook"
DOCUMENTS = ("module_core.json", "module_metrics.json", "dependency_resolution.json", "summary.json")
TERMINAL = ("completed", "dead", "cancelled")

# Repaired files; every other member of project.zip (the tests) is kept as shipped.
SOURCES = {}  # SOURCES-BLOCK


def unpack(archive, target):
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    with zipfile.ZipFile(archive) as zf:
        for name in zf.namelist():
            dest = (target / name).resolve()
            if not str(dest).startswith(str(target.resolve())):
                raise SystemExit("unsafe member %s" % name)
        zf.extractall(target)


def repair(tree):
    for rel, text in sorted(SOURCES.items()):
        path = tree / rel
        old = path.read_text(encoding="utf-8") if path.exists() else None
        if old != text:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            print("changed %s" % rel)


def pack(tree, archive):
    files = sorted(p for p in tree.rglob("*") if p.is_file() and "__pycache__" not in p.parts)
    archive.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in files:
            info = zipfile.ZipInfo(path.relative_to(tree).as_posix(), (1980, 1, 1, 0, 0, 0))
            info.external_attr = 0o644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, path.read_bytes())


def version_of(tree):
    import tomllib
    with open(tree / "pyproject.toml", "rb") as handle:
        return tomllib.load(handle)["project"]["version"]


def run_unittests(tree):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    probe = (
        "import sys, unittest\n"
        "suite = unittest.defaultTestLoader.discover('tests')\n"
        "result = unittest.TextTestRunner(stream=sys.stderr, verbosity=1).run(suite)\n"
        "print(result.testsRun, len(result.failures), len(result.errors), len(result.skipped))\n"
    )
    done = subprocess.run([sys.executable, "-c", probe], cwd=tree, env=env,
                          capture_output=True, text=True, check=True)
    run, failures, errors, skipped = (int(x) for x in done.stdout.split())
    return run, run - failures - errors - skipped


def write_json(path, value):
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=1, sort_keys=True)
        handle.write("\n")


def replay(tree, data, out):
    env = dict(os.environ, PYTHONPATH=str(tree / "src"), PYTHONDONTWRITEBYTECODE="1")
    return subprocess.run([sys.executable, "-m", PACKAGE, str(data), str(out)], env=env,
                          capture_output=True, text=True)


def load(out):
    return {name: json.loads((out / name).read_text(encoding="utf-8")) for name in DOCUMENTS}


def read_pools_of_workers(data):
    pools = {}
    with open(data / "workers.csv", newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            pools[(row["set"], row["worker"])] = row["pool"]
    jobs = {}
    with open(data / "jobs.tsv", newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            jobs[(row["set"], row["job"])] = row["pool"]
    return pools, jobs


def check_core(docs, data):
    worker_pool, job_pool = read_pools_of_workers(data)
    for sid, body in docs["module_core.json"]["sets"].items():
        for cp in body["checkpoints"]:
            for jid, job in cp["jobs"].items():
                if job["state"] != "running":
                    assert job["worker"] is None, (sid, cp["t"], jid)
                    continue
                slot = cp["workers"][str(job["worker"])]
                assert slot["up"] and slot["job"] == int(jid), (sid, cp["t"], jid)
                assert worker_pool[(sid, str(job["worker"]))] == job_pool[(sid, jid)], (sid, jid)
            for wid, slot in cp["workers"].items():
                if slot["job"] is not None:
                    assert cp["jobs"][str(slot["job"])]["worker"] == int(wid), (sid, cp["t"], wid)
    print("check C1 ok")


def check_metrics(docs):
    for sid, body in docs["module_metrics.json"]["sets"].items():
        core = docs["module_core.json"]["sets"][sid]
        runs = Counter(str(row[1]) for row in core["dispatches"])
        reasons = Counter(row[2] for row in core["audit"])
        for jid, counts in body["jobs"].items():
            assert counts["runs"] == runs.get(jid, 0), (sid, jid)
        for name, total in body["totals"].items():
            if name == "audit":
                assert total == {r: reasons.get(r, 0) for r in total}, sid
            else:
                assert total == sum(c[name] for c in body["jobs"].values()), (sid, name)
    print("check C2 ok")


def check_dependencies(docs):
    for sid, body in docs["dependency_resolution.json"]["sets"].items():
        last = docs["module_core.json"]["sets"][sid]["checkpoints"][-1]["jobs"]
        for edge in body["edges"]:
            state = last[str(edge["parent"])]["state"]
            want = "satisfied" if state == "completed" else "broken" if state in TERMINAL else "open"
            assert edge["outcome"] == want, (sid, edge)
            assert (edge["t"] is None) == (want == "open"), (sid, edge)
        for jid in body["cascaded"]:
            assert last[jid]["state"] == "cancelled", (sid, jid)
    print("check C3 ok")


def check_summary(docs):
    summary = docs["summary.json"]
    assert summary["set_count"] == len(docs["module_core.json"]["sets"])
    for sid, body in summary["sets"].items():
        core = docs["module_core.json"]["sets"][sid]
        totals = docs["module_metrics.json"]["sets"][sid]["totals"]
        final = Counter()
        for job in core["checkpoints"][-1]["jobs"].values():
            final[job["state"] if job["state"] in TERMINAL else "other"] += 1
        assert body["final"] == {k: final.get(k, 0) for k in body["final"]}, sid
        assert (body["executed"], body["lost"]) == (totals["executed"], totals["lost"]), sid
        text = "".join("%d %d %d %d\n" % tuple(row) for row in core["dispatches"])
        assert body["dispatch_sha256"] == hashlib.sha256(text.encode()).hexdigest(), sid
    print("check C4 ok")


def check_archive(archive):
    report = json.loads((OUT / "build_report.json").read_text(encoding="utf-8"))
    assert report["archive_sha256"] == hashlib.sha256(archive.read_bytes()).hexdigest()
    with zipfile.ZipFile(archive) as zf:
        assert report["files"] == sorted(zf.namelist())
    fresh = Path(tempfile.mkdtemp(prefix="leasebook-check-"))
    unpack(archive, fresh)
    selftest = json.loads((OUT / "selftest.json").read_text(encoding="utf-8"))
    run, passed = run_unittests(fresh)
    assert (selftest["tests_run"], selftest["tests_passed"]) == (run, passed)
    assert selftest["version"] == report["version"] == version_of(fresh)
    shutil.rmtree(fresh)
    print("check C5 ok")


def check_altered_copy(tree, docs):
    scratch = Path(tempfile.mkdtemp(prefix="leasebook-alter-"))
    copy = scratch / "book"
    shutil.copytree(DATA, copy)
    policy = (copy / "policy.ini").read_text(encoding="utf-8")
    ticks = int(policy.split("ticks =")[1].split()[0])
    (copy / "policy.ini").write_text(policy.replace("ticks = %d" % ticks, "ticks = %d" % (ticks + 3)),
                                     encoding="utf-8")
    done = replay(tree, copy, scratch / "out")
    assert done.returncode == 0, done.stdout + done.stderr
    moved = load(scratch / "out")["summary.json"]["sets"]
    changed = [s for s, body in moved.items() if body != docs["summary.json"]["sets"][s]]
    assert changed, "altered lease left every set unchanged"
    shutil.rmtree(scratch)
    print("check J9 ok (%d sets moved)" % len(changed))


def main():
    tree = WORK / PACKAGE
    unpack(DATA / "project.zip", tree)
    repair(tree)
    archive = OUT / "package.zip"
    pack(tree, archive)
    built = WORK / "from_zip"
    unpack(archive, built)
    run, passed = run_unittests(built)
    if passed != run:
        raise SystemExit("package tests failed: %d of %d passed" % (passed, run))
    version = version_of(built)
    write_json(OUT / "selftest.json", {"package": PACKAGE, "version": version,
                                       "tests_run": run, "tests_passed": passed})
    with zipfile.ZipFile(archive) as zf:
        members = sorted(zf.namelist())
    write_json(OUT / "build_report.json", {
        "package": PACKAGE, "version": version, "files": members,
        "archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest()})
    done = replay(built, DATA, OUT)
    if done.returncode != 0:
        raise SystemExit("replay refused the shipped book: " + done.stdout + done.stderr)
    docs = load(OUT)
    check_core(docs, DATA)
    check_metrics(docs)
    check_dependencies(docs)
    check_summary(docs)
    check_archive(archive)
    check_altered_copy(built, docs)
    print("wrote %s" % ", ".join(sorted(p.name for p in OUT.iterdir())))


if __name__ == "__main__":
    main()
