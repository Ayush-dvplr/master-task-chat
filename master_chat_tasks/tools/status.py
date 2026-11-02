#!/usr/bin/env python3
"""Task status overview from the master chat's records (run from master_chat_tasks/).

  status.py                 table of every task: stage, latest QC counts, tests-only scores, trajectory, live session
  status.py SLUG            one task in full (pipeline block + its board rows)
  status.py set SLUG k=v .. update registry/tasks.json -> tasks[SLUG].pipeline (creates the task if missing)

Stages (in order, v3 flow 24 Oct): build | probe | harden | qc | fix | qc_pass | gate_runs | pl_ready | parked | killed | dropped
"qc_pass" = zero QC findings (fails, minors, warns; dec 101) or a proven false positive in knowledge/FP_DOSSIER.md.
"killed" = probe tests >= 95 (kill rule). Legacy stages qc_clean/trajectory/traj_scored are read but not set.
Source of truth: registry/tasks.json pipeline blocks; live session state from board.json.
tree_sha = bundle tree sha set at freeze (intake.py tree_sha method); ql_round / ql_last = QL review round
and its last result ("closed ..." ends the round). Setting a new stage also stamps pipeline.stage_since
(issue.py time box counts from it). MT_ROOT env overrides the master_chat_tasks root (tests).
"""
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(os.environ.get("MT_ROOT") or Path(__file__).resolve().parent.parent)
TASKS = HERE / "registry" / "tasks.json"
BOARD = HERE / "board.json"
IST = timezone(timedelta(hours=5, minutes=30))
FIELDS = ["stage", "kind", "qc_round", "fail", "minor", "warn", "oracle", "nop", "stub", "v0_reward",
          "traj_tests", "traj_rubric", "traj_overall", "next", "updated", "tree_sha", "ql_round", "ql_last"]
STAGES = ["build", "probe", "harden", "qc", "fix", "qc_pass", "gate_runs", "pl_ready", "pushed", "parked", "killed", "dropped"]


def load():
    return json.loads(TASKS.read_text())


def board_rows():
    return json.loads(BOARD.read_text())["rows"] if BOARD.exists() else []


def live(slug, rows):
    act = [r for r in rows if r["slug"] == slug and r["status"] in ("issued", "running")]
    return ", ".join(f"{r['sha']} {r['step']} ({r['status']})" for r in act) or "-"


def main(a):
    t = load()
    tasks = {x["slug"]: x for x in t["tasks"]}  # tasks.json stores a list of task dicts
    if a and a[0] == "set":
        slug = a[1]
        if slug not in tasks:
            if " " in slug or "=" in slug or "--new" not in a:
                sys.exit(f"unknown slug {slug!r}; pass slug and k=v as separate args, or --new to add a task")
            tasks[slug] = {"slug": slug}
            t["tasks"].append(tasks[slug])
        task = tasks[slug]
        p = task.setdefault("pipeline", {})
        for kv in [x for x in a[2:] if x != "--new"]:
            k, v = kv.split("=", 1)
            if k not in FIELDS:
                sys.exit(f"bad field {k}; allowed {FIELDS}")
            if k == "stage" and v not in STAGES:
                sys.exit(f"bad stage {v}; allowed {STAGES}")
            if k == "stage" and (p.get("stage") != v or "stage_since" not in p):
                p["stage_since"] = datetime.now(IST).strftime("%Y-%m-%d %H:%M")
            p[k] = v
        p["updated"] = datetime.now(IST).strftime("%m-%d %H:%M")
        t["updated_ist"] = datetime.now(IST).isoformat(timespec="minutes")
        TASKS.write_text(json.dumps(t, indent=1, ensure_ascii=False))
        print("ok")
        return
    rows = board_rows()
    if a:
        task = tasks[a[0]]
        print(json.dumps(task.get("pipeline", {}), indent=1))
        for r in rows:
            if r["slug"] == a[0]:
                print(r["sha"], r["step"], r["status"], r.get("note", ""))
        return
    order = ["build", "probe", "harden", "qc", "fix", "qc_pass", "gate_runs", "pl_ready", "pushed", "parked", "killed", "dropped"]
    items = sorted(tasks.values(), key=lambda x: (order.index(x.get("pipeline", {}).get("stage", "harden"))
                                                 if x.get("pipeline", {}).get("stage", "harden") in order else 9, x["slug"]))
    print(f"{'task':42} {'stage':11} {'kind':9} {'QC':5} {'F/M/W':7} {'oracle/nop/stub':16} {'v0':6} {'traj t/r/o':14} live session / next")
    for x in items:
        p = x.get("pipeline", {})
        fmw = "/".join(p.get(k, "-") for k in ("fail", "minor", "warn"))
        on = "/".join(p.get(k, "-") for k in ("oracle", "nop", "stub"))
        tr = "/".join(p.get(k, "-") for k in ("traj_tests", "traj_rubric", "traj_overall"))
        lv = live(x["slug"], rows)
        print(f"{x['slug'][:42]:42} {p.get('stage','?'):11} {p.get('kind','-'):9} {p.get('qc_round','-'):5} {fmw:7} {on:16} {p.get('v0_reward','-'):6} {tr:14} {lv if lv != '-' else p.get('next','-')}")
    counts = {}
    for x in items:
        s = x.get("pipeline", {}).get("stage", "?")
        counts[s] = counts.get(s, 0) + 1
    print("\ncounts:", ", ".join(f"{k} {v}" for k, v in counts.items()), "| scores are tests-only unless a judge ran")


if __name__ == "__main__":
    main(sys.argv[1:])
