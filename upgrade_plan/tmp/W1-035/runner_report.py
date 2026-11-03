#!/usr/bin/env python3
"""Runner comparison from the records (S9 draft, W1-035). Read only; standard library only.

  runner_report.py [--root MASTER_CHAT_TASKS] [--settings SETTINGS_JSON] [--since "YYYY-MM-DD HH:MM"]
                   [--origin all|own|outside|intake_unclassified]

For each step (board kind) and runner (board row field "runner") it shows, always with the count n
beside every average:
  sessions        rows counted (done, partial, failed); dropped, superseded and cancelled rows are skipped
  qc              fails, minors and warns per QC session, parsed from the board note ("FAIL 7/0/1",
                  "F/M/W 2/0/2", "PASS 0/0/0"); pass share
  fix             fails left at the next QC of the same task after this fix session; fix rounds per
                  QC cycle (fix sessions between a failing QC and the next QC)
  gate            valid gate_run rows of registry/scores.jsonl, credited to the runner of the last
                  build, harden, rebuild or fix session of that task issued before the run;
                  tests, rubric, final, gate met share, and lever_loss_pct when the row has it
  wall            hours from "started" (else "issued") to "updated" for finished rows; this includes
                  the wait until Ayush opened the session, so it is an upper bound
A board row without "runner" is shown as "unknown" (every row written before S9).
A fair comparison needs the same step on similar tasks and enough sessions on each side; a cell with
n under 5 is marked "(few)".
MT_ROOT env overrides --root, like the other tools.
"""
import argparse
import json
import os
import re
import statistics
from collections import defaultdict
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve()
DEFAULT_ROOT = Path(os.environ.get("MT_ROOT") or HERE.parents[3] / "master_chat_tasks")
DEFAULT_SETTINGS = HERE.parents[2] / "drafts" / "P1" / "settings.json"
# legacy rows have no "kind"; same idea as issue.py LEGACY, widened to every prompt family on the board
LEGACY = [("qc", ("P11", "QC")), ("fix", ("P12",)), ("harden", ("P9", "P10")), ("blind", ("P13",)),
          ("build", ("P2",)), ("loss", ("P14",))]
SKIP_STATUS = {"dropped", "superseded", "cancelled"}
EDIT_KINDS = {"build", "harden", "rebuild", "fix"}
QC_RX = re.compile(r"\b(PASS|FAIL|WARN|MINOR|F/M/W)[:\s]*(\d+)/(\d+)/(\d+)")
FEW = 5


def kind_of(row):
    if row.get("kind"):
        return row["kind"]
    for k, prefixes in LEGACY:
        if row["step"].startswith(prefixes):
            return k
    return "other"


def when(text, year_from=""):
    """Board and score time stamps in one form; 'MM-DD HH:MM' borrows the year of year_from."""
    s = str(text or "").strip().replace("T", " ")[:16]
    if re.match(r"^\d\d-\d\d \d\d:\d\d$", s) and year_from:
        s = f"{str(year_from)[:4]}-{s}"
    try:
        return datetime.strptime(s, "%Y-%m-%d %H:%M")
    except ValueError:
        return None


def avg(xs):
    xs = [x for x in xs if x is not None]
    if not xs:
        return "-"
    tag = " (few)" if len(xs) < FEW else ""
    return f"{statistics.mean(xs):.2f} (n={len(xs)}){tag}"


def load_jsonl(p):
    out = []
    if p.exists():
        for line in p.read_text(errors="replace").splitlines():
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return out


def origin_of(task):
    """'outside' only from a P13 provenance block. pipeline.kind 'intake' alone is not proof: today it
    marks both a teammate task (b7c42a8f, not Ayush's) and tasks Ayush pushed himself."""
    if (task.get("provenance") or {}).get("origin"):
        return "outside"
    return "intake_unclassified" if (task.get("pipeline") or {}).get("kind") == "intake" else "own"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(DEFAULT_ROOT))
    ap.add_argument("--settings", default=str(DEFAULT_SETTINGS))
    ap.add_argument("--since", default="")
    ap.add_argument("--origin", default="all", choices=["all", "own", "outside", "intake_unclassified"])
    a = ap.parse_args()
    root = Path(a.root)
    rows = json.loads((root / "board.json").read_text())["rows"]
    tasks = {t["slug"]: t for t in json.loads((root / "registry" / "tasks.json").read_text())["tasks"]}
    scores = load_jsonl(root / "registry" / "scores.jsonl")
    try:
        runners = json.loads(Path(a.settings).read_text()).get("runners", {})
    except (OSError, ValueError):
        runners = {}
    known = list((runners.get("options") or {}).keys())
    since = when(a.since) if a.since else None

    def keep(r):
        if r["status"] in SKIP_STATUS:
            return False
        if since and (when(r["issued"]) or datetime.min) < since:
            return False
        if a.origin != "all" and origin_of(tasks.get(r["slug"], {})) != a.origin:
            return False
        return True

    all_rows = [dict(r, _kind=kind_of(r), _runner=r.get("runner") or "unknown", _t=when(r["issued"])) for r in rows]
    live = [r for r in all_rows if keep(r)]
    by_slug = defaultdict(list)
    for r in all_rows:
        if r["status"] not in SKIP_STATUS:
            by_slug[r["slug"]].append(r)
    for v in by_slug.values():
        v.sort(key=lambda r: r["_t"] or datetime.min)

    out = []
    p = out.append
    p("RUNNER REPORT (S9 draft, read only)")
    p(f"records: {root}/board.json ({len(rows)} rows), registry/tasks.json ({len(tasks)} tasks), registry/scores.jsonl ({len(scores)} rows)")
    p(f"runners in settings: {', '.join(known) or 'none found'}; default {runners.get('default', '?')}")
    p(f"filters: since {a.since or 'all'}; origin {a.origin}; skipped statuses {sorted(SKIP_STATUS)}")
    with_runner = sum(1 for r in live if r["_runner"] != "unknown")
    p(f"rows counted {len(live)}; with a runner field {with_runner}; unknown {len(live) - with_runner}")
    bad = sorted({r["_runner"] for r in live if r["_runner"] not in known + ["unknown"]})
    if bad:
        p(f"WARNING runner values not in settings.runners.options: {bad}")
    p("NOTE a fair comparison needs the same step on similar tasks and enough sessions per runner; "
      f"'(few)' marks n under {FEW}. Unknown rows are history before S9 and compare with nothing.")
    p("")

    # 1 sessions and wall time
    p("1. SESSIONS AND WALL TIME (hours, started or issued to last update; upper bound)")
    p(f"{'step':10} {'runner':16} {'sessions':>8}  {'done':>5} {'partial':>7} {'failed':>6} {'running':>7}  wall hours")
    groups = defaultdict(list)
    for r in live:
        groups[(r["_kind"], r["_runner"])].append(r)
    for (k, rn), rs in sorted(groups.items()):
        st = defaultdict(int)
        for r in rs:
            st[r["status"]] += 1
        hours = []
        for r in rs:
            if r["status"] in ("done", "partial", "failed"):
                t0 = when(r.get("started"), r["issued"]) or r["_t"]
                t1 = when(r.get("updated"), r["issued"])
                if t0 and t1 and t1 >= t0:
                    hours.append((t1 - t0).total_seconds() / 3600)
        med = f"; median {statistics.median(hours):.2f}" if hours else ""
        p(f"{k:10} {rn:16} {len(rs):>8}  {st['done']:>5} {st['partial']:>7} {st['failed']:>6} {st['running'] + st['issued']:>7}  {avg(hours)}{med}")
    p("")

    # 2 QC findings per QC session
    p("2. QC FINDINGS PER QC SESSION (parsed from the board note)")
    qc = defaultdict(lambda: {"f": [], "m": [], "w": [], "pass": 0, "parsed": 0, "all": 0})
    for r in live:
        if r["_kind"] != "qc":
            continue
        g = qc[r["_runner"]]
        g["all"] += 1
        m = QC_RX.search(r.get("note", ""))
        if m:
            f_, mi, w = map(int, m.groups()[1:])
            g["parsed"] += 1
            g["f"].append(f_)
            g["m"].append(mi)
            g["w"].append(w)
            g["pass"] += m.group(1) == "PASS" or f_ == 0
    for rn, g in sorted(qc.items()):
        share = f"{g['pass']}/{g['parsed']}" if g["parsed"] else "-"
        p(f"  {rn:16} QC sessions {g['all']}, note parsed {g['parsed']}; fails {avg(g['f'])}; minors {avg(g['m'])}; "
          f"warns {avg(g['w'])}; no fail {share}")
    if not qc:
        p("  none")
    p("")

    # 3 fix outcome and fix rounds
    p("3. FIX SESSIONS: fails left at the next QC of the same task; fix rounds per QC cycle")
    left = defaultdict(list)
    rounds = defaultdict(list)
    live_shas = {r["sha"] for r in live}
    for slug, rs in by_slug.items():
        cycle = []
        for i, r in enumerate(rs):
            if r["_kind"] == "fix":
                cycle.append(r)
                if r["sha"] in live_shas:
                    nxt = next((x for x in rs[i + 1:] if x["_kind"] == "qc"), None)
                    m = QC_RX.search(nxt.get("note", "")) if nxt else None
                    left[r["_runner"]].append(int(m.group(2)) if m else None)
            elif r["_kind"] == "qc":
                if cycle and any(x["sha"] in live_shas for x in cycle):
                    who = {x["_runner"] for x in cycle}
                    rounds[who.pop() if len(who) == 1 else "mixed"].append(len(cycle))
                cycle = []
    for rn in sorted(set(left) | set(rounds)):
        p(f"  {rn:16} fails left at next QC {avg(left[rn])}; fix rounds per QC cycle {avg(rounds[rn])}")
    if not left and not rounds:
        p("  none")
    p("")

    # 4 gate runs
    p("4. GATE RUNS (valid gate_run rows; credited to the last build, harden, rebuild or fix runner before the run)")
    gate = defaultdict(lambda: {"t": [], "r": [], "o": [], "met": 0, "lever": [], "n": 0})
    for s in scores:
        if s.get("event") != "gate_run" or s.get("valid") is False:
            continue
        slug = s.get("slug", "")
        if a.origin != "all" and origin_of(tasks.get(slug, {})) != a.origin:
            continue
        ts = when(s.get("ist"))
        if since and ts and ts < since:
            continue
        editors = [r for r in by_slug.get(slug, []) if r["_kind"] in EDIT_KINDS and r["_t"] and ts and r["_t"] <= ts]
        rn = editors[-1]["_runner"] if editors else "no editor on board"
        rw = s.get("rewards") or {}
        g = gate[rn]
        g["n"] += 1
        t, ru, o = rw.get("tests"), rw.get("rubric"), rw.get("combined")
        g["t"].append(t)
        g["r"].append(ru)
        g["o"].append(o)
        if None not in (t, ru, o):
            g["met"] += t < 85 and ru < 85 and o < 40
        g["lever"].append(s.get("lever_loss_pct"))
    for rn, g in sorted(gate.items()):
        lev = avg(g["lever"]) if any(x is not None for x in g["lever"]) else "no lever_loss_pct field yet"
        p(f"  {rn:18} runs {g['n']}; tests {avg(g['t'])}; rubric {avg(g['r'])}; final {avg(g['o'])}; "
          f"gate met {g['met']}/{g['n']}; lever loss share {lev}")
    if not gate:
        p("  none")
    p("")

    # 5 origin split
    p("5. ORIGIN (registry): own, outside (P13 provenance block), intake_unclassified (pipeline.kind intake, no provenance yet)")
    oc = defaultdict(int)
    for t in tasks.values():
        oc[origin_of(t)] += 1
    p("  " + ", ".join(f"{k} {v}" for k, v in sorted(oc.items())))
    print("\n".join(out))


if __name__ == "__main__":
    main()
