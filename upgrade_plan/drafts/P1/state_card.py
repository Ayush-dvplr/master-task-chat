#!/usr/bin/env python3
"""DRAFT v2 (not applied before PROCEED). Builds master_chat_tasks/STATE_CARD.md for the master chat.

The master reads only this card after any compaction (P1 step 2, R2). It is rebuilt by a script, not by the
model, after every records write (issue.py, intake.py, status.py and pending.py would call it at the end).

  state_card.py [--root DIR] [--out FILE] [--now "YYYY-MM-DD HH:MM"]

Budget (Q118, option 3): target 6 KB with short lines; hard limit 8 KB. Over the hard limit, sections are
dropped from the bottom of the fill order and a LEFT OUT line names them. Sizes come from settings.json.

Fill order (R2 fix b): rules, settings, QC kit, progress, news since last card, waiting for Ayush,
sessions, active tasks, other open items, uniqueness reminder, handoff format.

Sources (all read only, except the news snapshot STATE_CARD.prev.json that this script owns):
RULES_IN_FORCE.md, settings.json (DR2, one place for gate, caps and card sizes), GOALS.md "Today's goal",
board.json, registry/tasks.json, pending.db, knowledge/fingerprints/qc.json and the live kit it names.
"""
import argparse, hashlib, json, os, re, sqlite3, sys
from datetime import datetime, timedelta

DEFAULTS = {
    "gate": {"tests": 85, "rubric": 85, "final": 40},
    "counts": {"soft_cap": 70, "hard_cap": 100},
    "card": {"target_kb": 6, "hard_kb": 8, "sessions_shown": 6, "open_items_shown": 5,
             "next_chars": 60, "step_chars": 50, "title_chars": 70, "long_running_hours": 3,
             "question_age_hours": 12, "news_hours": 48, "unique_last": 3},
    "target": {"push_ready_per_day": 4, "push_ready_per_week": 20},
}
CLOSED = {"parked", "killed", "dropped", "pl_ready", "pushed"}
FMT = "%Y-%m-%d %H:%M"


def read(p):
    try:
        return open(p, encoding="utf-8").read()
    except OSError:
        return ""


def load_json(p, default):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return default


def when(s):
    try:
        return datetime.strptime(str(s)[:16].replace("T", " "), FMT)
    except ValueError:
        return None


def section(md, title):
    m = re.search(r"^#+\s*" + re.escape(title) + r".*?$\n(.*?)(?=^#+\s|\Z)", md, re.M | re.S)
    return m.group(1).strip() if m else ""


def cut(s, n):
    s = " ".join(str(s).split())
    return s if len(s) <= n else s[: n - 3] + "..."


def merged(base, over):
    out = json.loads(json.dumps(base))
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k].update(v)
        else:
            out[k] = v
    return out


def kit_line(R):
    fp = load_json(os.path.join(R, "knowledge", "fingerprints", "qc.json"), None)
    if not fp:
        return "QC KIT: no snapshot (knowledge/fingerprints/qc.json). Tell Ayush."
    src, files = fp.get("source", ""), fp.get("files", {})
    if not os.path.isdir(src):
        return f"QC KIT: live kit not reachable here; snapshot {fp.get('generated_ist','?')[:10]}, head {fp.get('git_head','?')[:8]}"
    changed = []
    for name, sha in files.items():
        try:
            if hashlib.sha256(open(os.path.join(src, name), "rb").read()).hexdigest() != sha:
                changed.append(name)
        except OSError:
            changed.append(name + " (missing)")
    extra = sorted(set(os.listdir(src)) - set(files) - {".git"})
    if not changed and not extra:
        return f"QC KIT: unchanged since snapshot {fp.get('generated_ist','?')[:10]}"
    return ("QC KIT: CHANGED (" + ", ".join(changed + [e + " (new)" for e in extra])[:200]
            + "). An agent classifies LENIENT, MINOR or MAJOR (S7); Ayush decides.")


def build(R, now, S):
    C = S["card"]
    secs = []  # (name, lines); order is the fill order

    rules = read(os.path.join(R, "RULES_IN_FORCE.md")).strip()
    secs.append(("rules", ["RULES IN FORCE (RULES_IN_FORCE.md; the only rule text the master follows)",
                           rules or "MISSING: RULES_IN_FORCE.md not found. Stop and tell Ayush."]))

    g, c = S["gate"], S["counts"]
    secs.append(("settings", [f"SETTINGS (settings.json{'' if S.get('_found') else ', MISSING: defaults used, tell Ayush'}): "
                              f"gate tests <{g['tests']}, rubric <{g['rubric']}, final <{g['final']}; "
                              f"counts QC minimum, soft {c['soft_cap']}, hard {c['hard_cap']}"]))
    secs.append(("qc kit", [kit_line(R)]))

    tasks = load_json(os.path.join(R, "registry", "tasks.json"), {}).get("tasks", [])
    def pushed_since(t0):
        return sum(1 for t in tasks if (t.get("pipeline") or {}).get("stage") == "pushed"
                   and (when((t.get("pipeline") or {}).get("stage_since")) or datetime.min) >= t0)
    day0 = now.replace(hour=0, minute=0)
    week0 = day0 - timedelta(days=now.weekday())
    T = S["target"]
    goal = section(read(os.path.join(R, "GOALS.md")), "Today's goal")
    secs.append(("progress", [f"PROGRESS (registry/tasks.json): pushed today {pushed_since(day0)} of {T['push_ready_per_day']}, "
                              f"this week {pushed_since(week0)} of {T['push_ready_per_week']}",
                              "TODAY (GOALS.md): " + (cut(goal, 400) if goal else "(no Today's goal section)")]))

    rows = load_json(os.path.join(R, "board.json"), {}).get("rows", [])
    prev_path = os.path.join(R, "STATE_CARD.prev.json")
    prev = load_json(prev_path, {"sessions": {}, "stages": {}})
    snap = {"sessions": {r.get("sha"): r.get("status") for r in rows},
            "stages": {t["slug"]: (t.get("pipeline") or {}).get("stage") for t in tasks}}
    news = []
    for sha, st in snap["sessions"].items():
        if sha in prev["sessions"] and prev["sessions"][sha] != st:
            r = next(x for x in rows if x.get("sha") == sha)
            news.append(f"{sha} {prev['sessions'][sha]} -> {st} | {r.get('slug')} | {cut(r.get('note',''), 80)}")
    for slug, st in snap["stages"].items():
        if slug in prev["stages"] and prev["stages"][slug] != st:
            news.append(f"{slug}: {prev['stages'][slug]} -> {st}")
    if not prev["sessions"] and not prev["stages"]:
        news = [f"{r.get('sha')} {r.get('status')} | {r.get('slug')} | {cut(r.get('note',''), 80)}" for r in rows
                if r.get("status") == "done" and (when(r.get("updated")) or datetime.min) >= now - timedelta(hours=C["news_hours"])]
    secs.append(("news", [f"NEWS SINCE LAST CARD ({len(news)}; board.json, registry/tasks.json)"] + (news[:8] or ["none"])))

    try:
        db = sqlite3.connect(f"file:{os.path.join(R, 'pending.db')}?mode=ro", uri=True)
        items = db.execute("select id,kind,title,priority,created_ist from items where status='open' order by "
                           "case priority when 'high' then 0 when 'medium' then 1 else 2 end, seq").fetchall()
    except Exception:
        items = []
    old = now - timedelta(hours=C["question_age_hours"])
    waiting = [i for i in items if i[1] in ("question", "blocked")]
    waiting.sort(key=lambda i: (0 if (when(i[4]) or now) <= old else 1))
    secs.append(("waiting", [f"WAITING FOR AYUSH ({len(waiting)}; pending.db; always shown, older than {C['question_age_hours']} h first)"]
                 + [f"{i[0]} | {i[3]} | {(when(i[4]) and str(int((now - when(i[4])).total_seconds() // 3600)) + ' h') or '?'} | {cut(i[2], C['title_chars'])}" for i in waiting]))

    live = sorted([r for r in rows if r.get("status") in ("running", "issued")], key=lambda r: r.get("issued", ""), reverse=True)
    L = [f"SESSIONS RUNNING OR ISSUED ({len(live)}; board.json; Ayush decides when issued becomes running)"]
    for r in live[: C["sessions_shown"]]:
        age = when(r.get("issued"))
        hrs = (now - age).total_seconds() / 3600 if age else 0
        flag = f" | LONG {hrs:.0f} h, chase" if hrs > C["long_running_hours"] else ""
        L.append(f"{r.get('sha')} | {r.get('status')} | {r.get('slug')} | {cut(r.get('step',''), C['step_chars'])} | {r.get('prompt','')}{flag}")
    if len(live) > C["sessions_shown"]:
        L.append(f"+{len(live) - C['sessions_shown']} more: python3 tools/board.py list")
    secs.append(("sessions", L))

    act = [t for t in tasks if (t.get("pipeline") or {}).get("stage") and (t.get("pipeline") or {}).get("stage") not in CLOSED]
    secs.append(("tasks", [f"ACTIVE TASKS ({len(act)}; registry/tasks.json; detail: python3 tools/status.py <slug>)"]
                 + [f"{t['slug']} | {t['pipeline']['stage']} | next: {cut(t['pipeline'].get('next',''), C['next_chars'])}" for t in act]))

    rest = [i for i in items if i not in waiting]
    secs.append(("open items", [f"OTHER OPEN ITEMS (top {min(len(rest), C['open_items_shown'])} of {len(rest)}; full list: python3 tools/pending.py list)"]
                 + [f"{i[0]} | {i[1]} | {i[3]} | {cut(i[2], C['title_chars'])}" for i in rest[: C["open_items_shown"]]]))

    recent = sorted(tasks, key=lambda t: t.get("created_ist", ""), reverse=True)[: C["unique_last"]]
    secs.append(("uniqueness", [f"UNIQUENESS (last {len(recent)} builds; a new build must not repeat these): "
                                + "; ".join(f"{t['slug']}: " + (f"{t['design'].get('family','?')}, lever {t['design'].get('primary_lever_kind','?')}"
                                           if isinstance(t.get("design"), dict) else f"{t.get('archetype','?')}, {t.get('category','?')} (no design field)")
                                  for t in recent)]))
    secs.append(("handoff", ["HANDOFF FORMAT: a table with board sha, step, status and a clickable file link; never 'read and follow'."]))
    return secs, snap, prev_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    ap.add_argument("--out", default=None)
    ap.add_argument("--now", default=None, help="for tests only")
    a = ap.parse_args()
    R = a.root
    sp = os.path.join(R, "settings.json")
    S = merged(DEFAULTS, load_json(sp, {}))
    S["_found"] = os.path.isfile(sp)
    now = datetime.strptime(a.now, FMT) if a.now else datetime.utcnow() + timedelta(hours=5, minutes=30)
    secs, snap, prev_path = build(R, now, S)

    head = f"STATE CARD (generated {now:%d %b %Y %H:%M} IST by tools/state_card.py; do not edit by hand)"
    hard = S["card"]["hard_kb"] * 1024
    kept, left = list(secs), []
    def render(ss, left):
        body = [head, ""] + [ln for _, lines in ss for ln in lines + [""]]
        if left:
            body.append("LEFT OUT (over the hard limit; read the named source): " + ", ".join(left))
        return "\n".join(body).rstrip() + "\n"
    text = render(kept, left)
    while len(text.encode()) > hard and len(kept) > 2:
        left.insert(0, kept.pop(-2)[0])  # keep rules first and the handoff line last
        text = render(kept, left)

    out = a.out or os.path.join(R, "STATE_CARD.md")
    open(out, "w", encoding="utf-8").write(text)
    json.dump(snap, open(prev_path, "w", encoding="utf-8"))
    kb = len(text.encode()) / 1024
    print(f"wrote {out}: {kb:.1f} KB (target {S['card']['target_kb']} KB, hard {S['card']['hard_kb']} KB)")
    if kb > S["card"]["target_kb"]:
        print(f"NOTE: over the {S['card']['target_kb']} KB target", file=sys.stderr)
    if left:
        print("WARNING: left out " + ", ".join(left), file=sys.stderr)


if __name__ == "__main__":
    main()
