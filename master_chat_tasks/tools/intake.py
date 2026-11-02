#!/usr/bin/env python3
"""Intake for a finished session or a harness run (plan v1 U2). Read-only unless --apply.

  intake.py SHA [--apply] [--status done|partial|failed] [--note TEXT]
      board row -> OUT folder: exists, file count, result*.json parses, its status/verdict,
      TODO.md open lines. --apply sets board status/note and closes the pending step.

  intake.py --job SLUG [--bundle PATH] [--event probe|gate_run|run|ql_rerun|regrade] [--ayush-ok TEXT]
            [--apply] [--note TEXT]
      jobs/SLUG: scores from logs/pass-summary.json; the staged task path must be the live
      harness (not the old Harbor_Harness/ copy); staged copy vs bundle (diff -rq); author-note
      grep in staged environment/; gate check (tests<85, rubric<85, final<40; plan v2 A2) and kill rule
      (tests>=95). tree_sha of --bundle (default Tasks_INPUT/SLUG) goes in every row; gate_run and
      ql_rerun are refused unless it equals the registry tree_sha. A regrade row is valid only with
      --ayush-ok "<his verbatim words>". Without --apply the would-be scores.jsonl row is printed and
      nothing is written. --apply appends registry/scores.jsonl and updates registry/tasks.json.
MT_ROOT env overrides the master_chat_tasks root (tests).
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(os.environ.get("MT_ROOT") or Path(__file__).resolve().parent.parent)
ROOT = HERE.parent
HARNESS = Path(__file__).resolve().parent.parent.parent / "Terminal_2.0_Harbor_Harness"
IST = timezone(timedelta(hours=5, minutes=30))
FINAL_GATE = 40
SHA_EVENTS = ("gate_run", "ql_rerun")
NOTE_RX = re.compile(r"\bTRAPS?\b|_traps\b|\bLEVERS?\b|(?i:\bgrader\b|hidden test|answer key|author note|\blever L\d)")


def now():
    return datetime.now(IST)


def py(*cmd):
    return subprocess.run(["python3", *cmd], cwd=HERE, check=True, capture_output=True, text=True).stdout.strip()


def tree_sha(d):
    """Python twin of, run inside d:
    find . -type f -print0 | LC_ALL=C sort -z | xargs -0 shasum -a 256 | shasum -a 256 | cut -c1-12"""
    files = []

    def walk(path, rel):
        with os.scandir(path) as it:
            for e in it:
                r = f"{rel}/{e.name}"
                if e.is_dir(follow_symlinks=False):
                    walk(e.path, r)
                elif e.is_file(follow_symlinks=False):
                    files.append((os.fsencode(r), e.path))

    walk(d, ".")
    out = hashlib.sha256()
    for rel, full in sorted(files):
        h = hashlib.sha256()
        with open(full, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        if b"\\" in rel or b"\n" in rel:  # shasum escapes such names and prefixes the line with a backslash
            out.update(b"\\" + h.hexdigest().encode() + b"  " + rel.replace(b"\\", b"\\\\").replace(b"\n", b"\\n") + b"\n")
        else:
            out.update(h.hexdigest().encode() + b"  " + rel + b"\n")
    return out.hexdigest()[:12]


def registry_tree_sha(slug):
    tasks = json.loads((HERE / "registry" / "tasks.json").read_text())["tasks"]
    t = next((x for x in tasks if x["slug"] == slug), None)
    return str((t or {}).get("pipeline", {}).get("tree_sha", "") or "").strip()


def session(a):
    rows = json.loads((HERE / "board.json").read_text())["rows"]
    r = next((x for x in rows if x["sha"].startswith(a.sha)), None)
    if not r:
        sys.exit(f"no board row {a.sha}")
    out = ROOT / r["result"]
    print(f"board {r['sha']} | {r['slug']} | {r['step']} | status {r['status']} | pending {r.get('pending_id', '')}")
    print(f"OUT {out} exists={out.exists()}")
    verdict = "?"
    if out.exists():
        files = [p for p in (out.rglob("*") if out.is_dir() else [out]) if p.is_file()]
        print(f"files {len(files)}")
        for res in [p for p in files if p.name.startswith("result") and p.suffix == ".json"]:
            try:
                d = json.loads(res.read_text())
                verdict = d.get("status") or d.get("verdict") or "?"
                print(f"{res.relative_to(ROOT)} parses; status/verdict={verdict}; keys={list(d)[:12]}")
            except json.JSONDecodeError as e:
                print(f"{res.relative_to(ROOT)} DOES NOT PARSE: {e}")
        todo = out / "TODO.md" if out.is_dir() else None
        if todo and todo.exists():
            open_lines = [l for l in todo.read_text().splitlines() if l.strip().startswith(("- [ ]", "* [ ]"))]
            print(f"TODO.md open items {len(open_lines)}" + "".join(f"\n  {l.strip()}" for l in open_lines[:10]))
    if a.apply:
        st = a.status or ("done" if verdict in ("done", "complete", "completed", "PASS", "pass") else "partial")
        py("tools/board.py", "set", r["sha"], f"status={st}", f"note={a.note}")
        if r.get("pending_id"):
            py("tools/pending.py", "done" if st == "done" else "set", r["pending_id"],
               *([a.note] if st == "done" else [f"status=waiting", f"note={a.note}"]))
        print(f"applied: board {st}; pending {r.get('pending_id') or '-'}")


def job(a):
    H = Path(a.harness).resolve() if a.harness else HARNESS
    jd = H / "jobs" / a.job
    cfg = json.loads((jd / "logs" / "job-config.json").read_text())
    ps = json.loads((jd / "logs" / "pass-summary.json").read_text())
    t, r, o = ps["average_test_weights_percentage"], ps["average_rubric_weights_percentage"], ps["average_combined_score"]
    staged = Path(cfg["tasks"][0]["path"])
    print(f"job {jd}\nscores tests {t} rubric {r} overall {o} runs {ps.get('runs')}")
    live = staged.is_relative_to(H / ".kiro-staged-tasks")
    print(f"staged {staged} live_harness={live}" + ("" if live else "  <-- OLD COPY: score not valid for this bundle"))
    bundle = Path(a.bundle) if a.bundle else H / "Tasks_INPUT" / a.job
    if staged.exists() and bundle.exists():
        d = subprocess.run(["diff", "-rq", "-x", ".kiro-staged-from", "-x", "__pycache__", str(staged), str(bundle)],
                           capture_output=True, text=True).stdout.strip()
        if d.endswith("task.toml differ") and d.count("\n") == 0:
            td = subprocess.run(["diff", str(staged / "task.toml"), str(bundle / "task.toml")], capture_output=True, text=True).stdout
            changed = [l for l in td.splitlines() if l[:1] in "<>"]
            if all("allowed_hosts" in l or "host.docker.internal" in l for l in changed):
                d = ""
                print("staged == bundle (task.toml differs only by the harness allowed_hosts line)")
        if d:
            print(f"staged differs from bundle {bundle}:\n{d}")
        elif "allowed_hosts" not in locals().get("td", ""):
            print("staged == bundle")
    else:
        print(f"diff skipped: staged exists={staged.exists()} bundle exists={bundle.exists()} ({bundle})")
    env = staged / "environment"
    hits = []
    if env.exists():
        for p in env.rglob("*"):
            if p.is_file() and p.stat().st_size < 5_000_000:
                for i, line in enumerate(p.read_text(errors="ignore").splitlines(), 1):
                    if NOTE_RX.search(line):
                        hits.append(f"{p.relative_to(staged)}:{i}: {line.strip()[:120]}")
    print(f"author-note grep in environment/: {len(hits)} hits" + "".join(f"\n  {h}" for h in hits[:15]))
    gate = t < 85 and r < 85 and o < FINAL_GATE
    kill = t >= 95
    print(f"gate (tests<85, rubric<85, final<{FINAL_GATE}): {'MET' if gate else 'not met'} | kill rule tests>=95: {'KILL' if kill else 'no'}")
    ts = tree_sha(bundle) if bundle.is_dir() else None
    print(f"tree_sha {ts} ({bundle})")
    if a.event in SHA_EVENTS:
        reg = registry_tree_sha(a.job)
        if not reg:
            sys.exit(f"REFUSED {a.event}: registry tree_sha empty: set it at freeze (status.py set {a.job} tree_sha=...)")
        if ts != reg:
            sys.exit(f"REFUSED {a.event}: tree_sha {ts} of {bundle} != registry tree_sha {reg}")
    if a.event == "regrade":
        valid = bool(a.ayush_ok)
        reason = None if valid else "regrade without --ayush-ok"
    else:
        valid = live and not hits
        reason = None if valid else ("old staged copy" if not live else "author notes in environment/")
    row = {"ist": now().isoformat(timespec="minutes"), "slug": a.job, "event": a.event,
           "rewards": {"tests": t, "rubric": r, "combined": o}, "valid": valid, "artefact_reason": reason,
           "tree_sha": ts, "note": a.note, "report": str(jd.relative_to(ROOT) if jd.is_relative_to(ROOT) else jd)}
    if a.ayush_ok:
        row["ayush_ok"] = a.ayush_ok
    if not a.apply:
        print(f"would append row (no --apply, nothing written): {json.dumps(row, ensure_ascii=False)}")
    if a.apply:
        with open(HERE / "registry" / "scores.jsonl", "a") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        py("tools/status.py", "set", a.job, f"traj_tests={t}", f"traj_rubric={r}", f"traj_overall={o}")
        print("applied: scores.jsonl row + tasks.json traj fields")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sha", nargs="?")
    ap.add_argument("--job")
    ap.add_argument("--bundle")
    ap.add_argument("--harness", help="harness checkout holding jobs/ (default Terminal_2.0_Harbor_Harness)")
    ap.add_argument("--event", default="run", choices=["probe", "gate_run", "run", "ql_rerun", "regrade"])
    ap.add_argument("--ayush-ok", default="", help="Ayush's verbatim words; makes a regrade row valid")
    ap.add_argument("--status", choices=["done", "partial", "failed"])
    ap.add_argument("--note", default="")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    if a.ayush_ok and a.event != "regrade":
        ap.error("--ayush-ok is only for --event regrade")
    job(a) if a.job else session(a) if a.sha else ap.error("give SHA or --job SLUG")


if __name__ == "__main__":
    main()
