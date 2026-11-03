#!/usr/bin/env python3
"""DRAFT (not applied before PROCEED). Builds master_chat_tasks/STATE_CARD.md for the master chat.

The master reads only this card after any compaction (P1 step 2). It is rebuilt by a script, not by the model,
after every records write (issue.py, intake.py, status.py and pending.py would call it at the end).

  state_card.py [--root DIR] [--out FILE] [--max-kb 4]

Sources (all read only): RULES_IN_FORCE.md (one current layer of rules, curated with Ayush; replaces the
"v3.8 overrides line 31" layers), GOALS.md section "Today's goal", board.json (running and issued sessions),
registry/tasks.json (active tasks and stage), pending.db (open items). Prints a warning when the card is too long.
"""
import argparse, json, os, re, sqlite3, sys
from datetime import datetime, timezone, timedelta

IST = timezone(timedelta(hours=5, minutes=30))
CLOSED_STAGES = {"parked", "killed", "dropped", "pl_ready", "pushed"}

def read(path):
    try:
        return open(path, encoding="utf-8").read()
    except OSError:
        return ""

def section(md, title):
    m = re.search(r"^#+\s*" + re.escape(title) + r".*?$\n(.*?)(?=^#+\s|\Z)", md, re.M | re.S)
    return m.group(1).strip() if m else ""

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=os.path.dirname(os.path.abspath(__file__)))
    ap.add_argument("--out", default=None)
    ap.add_argument("--max-kb", type=float, default=4.0)
    a = ap.parse_args()
    R = a.root
    out = a.out or os.path.join(R, "STATE_CARD.md")
    L = [f"STATE CARD (generated {datetime.now(IST):%d %b %Y %H:%M} IST by tools/state_card.py; do not edit by hand)", ""]

    rules = read(os.path.join(R, "RULES_IN_FORCE.md")).strip()
    L += ["RULES IN FORCE (one layer; the only rule text the master follows)", rules or "MISSING: RULES_IN_FORCE.md not found. Stop and tell Ayush.", ""]

    goal = section(read(os.path.join(R, "GOALS.md")), "Today's goal")
    L += ["TODAY", goal or "(no Today's goal section)", ""]

    try:
        rows = json.load(open(os.path.join(R, "board.json")))["rows"]
    except Exception:
        rows = []
    live = [r for r in rows if r.get("status") in ("running", "issued")]
    L.append(f"SESSIONS RUNNING OR ISSUED ({len(live)}; Ayush decides when issued becomes running)")
    for r in sorted(live, key=lambda r: r.get("issued", ""), reverse=True)[:12]:
        L.append(f"{r.get('sha')} | {r.get('status')} | {r.get('slug')} | {r.get('step','')[:60]} | {r.get('prompt','')}")
    L.append("")

    try:
        tasks = json.load(open(os.path.join(R, "registry", "tasks.json")))["tasks"]
    except Exception:
        tasks = []
    act = [t for t in tasks if (t.get("pipeline") or {}).get("stage") not in CLOSED_STAGES and (t.get("pipeline") or {}).get("stage")]
    L.append(f"ACTIVE TASKS ({len(act)})")
    for t in act:
        p = t["pipeline"]
        L.append(f"{t['slug']} | {p.get('stage')} | next: {str(p.get('next',''))[:90]}")
    L.append("")

    try:
        c = sqlite3.connect(f"file:{os.path.join(R, 'pending.db')}?mode=ro", uri=True)
        items = c.execute("select id,kind,title,priority,updated_ist from items where status='open' "
                          "order by case priority when 'high' then 0 when 'medium' then 1 else 2 end, seq limit 10").fetchall()
    except Exception:
        items = []
    L.append(f"OPEN ITEMS (top {len(items)}; full list: python3 tools/pending.py list)")
    for i in items:
        L.append(f"{i[0]} | {i[1]} | {i[3]} | {i[2][:90]}")
    L += ["", "HANDOFF FORMAT: a table with board sha, step, status and a clickable file link; never 'read and follow'."]

    text = "\n".join(L) + "\n"
    open(out, "w", encoding="utf-8").write(text)
    kb = len(text.encode()) / 1024
    print(f"wrote {out}: {kb:.1f} KB")
    if kb > a.max_kb:
        print(f"WARNING: card is {kb:.1f} KB, over {a.max_kb} KB; shorten RULES_IN_FORCE.md or the limits", file=sys.stderr)

if __name__ == "__main__":
    main()
