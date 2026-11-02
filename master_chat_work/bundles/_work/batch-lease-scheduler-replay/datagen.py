"""Seeded, stdlib-only producer of environment/data for batch-lease-scheduler-replay.

usage: python3 -B datagen.py <out_dir> [--seed N] [--sets N] [--profile shipped|hidden] [--no-extras]
Writes the 8 book files; unless --no-extras also project.zip (from project_src/) and replay_contract.md.
"""
import argparse
import json
import os
import random
import shutil
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "engine"))
import gen  # noqa: E402

EVENT_KEYS = ("job", "attempt", "delta", "worker")


def write_book(book, out, seed=0, blank_every=0):
    """Write a book model (gen.make_book shape) as the 8 input files."""
    rng = random.Random(seed ^ 0x5EED)
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "policy.ini"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("[lease]\nticks = %d\n\n[retry]\ndelay = %d\n" % (book["lease"], book["delay"]))
    pools = [{"pool": n, "preempt": f} for n, f in book["pools"].items()]
    with open(os.path.join(out, "pools.json"), "w", encoding="utf-8", newline="\n") as fh:
        json.dump({"pools": pools}, fh, indent=2)
        fh.write("\n")
    sids = list(book["sets"])
    rows = {"workers": [], "jobs": [], "work": [], "deps": [], "events": [], "cps": []}
    for sid in sids:
        s = book["sets"][sid]
        w = [(sid, wid, p, "up" if up else "down") for wid, (p, up) in s["workers"].items()]
        rng.shuffle(w)
        rows["workers"] += w
        j = [(sid, jid, p, pr, lim) for jid, (p, pr, lim) in s["jobs"].items()]
        rng.shuffle(j)
        rows["jobs"] += j
        d = [(sid, jid, wk) for jid, wk in s["work"].items()]
        rng.shuffle(d)
        rows["work"] += d
        e = [(sid, p, c) for p, c in s["deps"]]
        rng.shuffle(e)
        rows["deps"] += e
        ev = list(s["events"])
        rng.shuffle(ev)
        ev.sort(key=lambda x: x["t"])
        for x in ev:
            rec = {"set": sid, "id": x["id"], "t": x["t"], "type": x["type"]}
            for k in EVENT_KEYS:
                if k in x:
                    rec[k] = x[k]
            rows["events"].append(rec)
        rows["cps"] += [(sid, t) for t in s["checkpoints"]]

    def csv_out(name, header, data, sep):
        with open(os.path.join(out, name), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(sep.join(header) + "\n")
            for r in data:
                fh.write(sep.join(str(v) for v in r) + "\n")

    csv_out("workers.csv", ("set", "worker", "pool", "state"), rows["workers"], ",")
    csv_out("jobs.tsv", ("set", "job", "pool", "priority", "retry_limit"), rows["jobs"], "\t")
    csv_out("durations.csv", ("set", "job", "work"), rows["work"], ",")
    csv_out("dependencies.csv", ("set", "parent", "child"), rows["deps"], ",")
    with open(os.path.join(out, "events.jsonl"), "w", encoding="utf-8", newline="\n") as fh:
        for n, rec in enumerate(rows["events"], 1):
            fh.write(json.dumps(rec) + "\n")
            if blank_every and n % blank_every == 0:
                fh.write("\n")
    with open(os.path.join(out, "checkpoints.txt"), "w", encoding="utf-8", newline="\n") as fh:
        for sid, t in rows["cps"]:
            fh.write("%d %d\n" % (sid, t))


def zip_dir(src, dest):
    """Deterministic zip: sorted members, fixed timestamp, deflated."""
    names = []
    for root, dirs, files in os.walk(src):
        dirs[:] = sorted(d for d in dirs if d != "__pycache__")
        for f in sorted(files):
            if not f.endswith(".pyc"):
                names.append(os.path.relpath(os.path.join(root, f), src))
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
        for rel in sorted(names):
            info = zipfile.ZipInfo(rel.replace(os.sep, "/"), date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            with open(os.path.join(src, rel), "rb") as fh:
                zf.writestr(info, fh.read())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--seed", type=int, default=413927)
    ap.add_argument("--sets", type=int, default=420)
    ap.add_argument("--profile", default="shipped")
    ap.add_argument("--no-extras", action="store_true")
    a = ap.parse_args()
    book = gen.make_book(a.seed, a.profile, a.sets)
    write_book(book, a.out, a.seed, blank_every=997 if a.profile == "shipped" else 0)
    if not a.no_extras:
        zip_dir(os.path.join(HERE, "project_src"), os.path.join(a.out, "project.zip"))
        shutil.copyfile(os.path.join(HERE, "replay_contract.md"), os.path.join(a.out, "replay_contract.md"))


if __name__ == "__main__":
    main()
