#!/usr/bin/env python3
"""Intake for a finished session or a harness run (plan v1 U2). Read-only unless --apply.

  intake.py SHA [--apply] [--status done|partial|failed] [--note TEXT]
      board row -> OUT folder: exists, file count, result*.json parses, its status/verdict,
      TODO.md open lines. --apply sets board status/note and closes the pending step.

  intake.py --job SLUG [--bundle PATH] [--event probe|gate_run|run] [--apply] [--note TEXT]
      jobs/SLUG: scores from logs/pass-summary.json; the staged task path must be the live
      harness (not the old Harbor_Harness/ copy); staged copy vs bundle (diff -rq); author-note
      grep in staged environment/; gate check (tests<85, rubric<85, overall<50; Ayush 27 Oct 22:20) and kill rule
      (tests>=95). --apply appends registry/scores.jsonl and updates registry/tasks.json.
"""
import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
ROOT = HERE.parent
HARNESS = ROOT / "Terminal_2.0_Harbor_Harness"
IST = timezone(timedelta(hours=5, minutes=30))
NOTE_RX = re.compile(r"\bTRAPS?\b|_traps\b|\bLEVERS?\b|(?i:\bgrader\b|hidden test|answer key|author note|\blever L\d)")


def now():
    return datetime.now(IST)


def py(*cmd):
    return subprocess.run(["python3", *cmd], cwd=HERE, check=True, capture_output=True, text=True).stdout.strip()


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
    gate = t < 85 and r < 85 and o < 50
    kill = t >= 95
    print(f"gate (tests<85, rubric<85, overall<50): {'MET' if gate else 'not met'} | kill rule tests>=95: {'KILL' if kill else 'no'}")
    if a.apply:
        row = {"ist": now().isoformat(timespec="minutes"), "slug": a.job, "event": a.event,
               "rewards": {"tests": t, "rubric": r, "combined": o}, "valid": live and not hits,
               "artefact_reason": None if live and not hits else ("old staged copy" if not live else "author notes in environment/"),
               "note": a.note, "report": str(jd.relative_to(ROOT))}
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
    ap.add_argument("--event", default="run", choices=["probe", "gate_run", "run"])
    ap.add_argument("--status", choices=["done", "partial", "failed"])
    ap.add_argument("--note", default="")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    job(a) if a.job else session(a) if a.sha else ap.error("give SHA or --job SLUG")


if __name__ == "__main__":
    main()
