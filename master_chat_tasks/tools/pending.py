#!/usr/bin/env python3
"""Pending-items store for the master chat (SQLite, stdlib only).

One row per thing that is not finished: a step Ayush runs, a question for him,
a reminder, or a job that is running. Every change is kept in `history`.

  pending.py list [--all] [--kind K]        ordered table (open items by default)
  pending.py md                             same, as Markdown with clickable prompt links
  pending.py show ID                        one item plus its history
  pending.py add KIND TITLE [field=value ...]
  pending.py set ID field=value [...]       update any field (status, seq, note, ...)
  pending.py done ID [note]                 status=done, closed time set
  pending.py drop ID [note]                 status=dropped

Kinds: step | question | reminder | running.  Status: open | running | waiting | done | dropped.
Fields: title, detail, prompt, send_back, seq, priority (high/medium/low), status, owner, note.
"""
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

DB = Path(__file__).resolve().parent.parent / "pending.db"
IST = timezone(timedelta(hours=5, minutes=30))
KINDS = {"step", "question", "reminder", "running"}
STATUSES = {"open", "running", "waiting", "done", "dropped"}
FIELDS = {"title", "detail", "prompt", "send_back", "seq", "priority", "status", "owner", "note", "kind"}
PREFIX = {"step": "S", "question": "Q", "reminder": "R", "running": "J"}
ORDER = "CASE status WHEN 'running' THEN 0 WHEN 'open' THEN 1 WHEN 'waiting' THEN 2 ELSE 3 END, seq, id"


def now() -> str:
    return datetime.now(IST).strftime("%Y-%m-%d %H:%M")


def connect() -> sqlite3.Connection:
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    con.executescript(
        """
        CREATE TABLE IF NOT EXISTS items (
          id TEXT PRIMARY KEY, kind TEXT NOT NULL, title TEXT NOT NULL,
          detail TEXT DEFAULT '', prompt TEXT DEFAULT '', send_back TEXT DEFAULT '',
          seq INTEGER DEFAULT 100, priority TEXT DEFAULT 'medium',
          status TEXT DEFAULT 'open', owner TEXT DEFAULT 'Ayush', note TEXT DEFAULT '',
          created_ist TEXT, updated_ist TEXT, closed_ist TEXT);
        CREATE TABLE IF NOT EXISTS history (
          item_id TEXT, ist TEXT, change TEXT);
        """
    )
    return con


def parse_pairs(pairs: list[str]) -> dict[str, str]:
    out = {}
    for p in pairs:
        key, sep, value = p.partition("=")
        if not sep or key not in FIELDS:
            sys.exit(f"bad field '{p}'; allowed: {sorted(FIELDS)}")
        out[key] = value
    if "status" in out and out["status"] not in STATUSES:
        sys.exit(f"bad status; allowed: {sorted(STATUSES)}")
    if "kind" in out and out["kind"] not in KINDS:
        sys.exit(f"bad kind; allowed: {sorted(KINDS)}")
    return out


def next_id(con: sqlite3.Connection, kind: str) -> str:
    p = PREFIX[kind]
    n = [int(r[0][1:]) for r in con.execute("SELECT id FROM items WHERE id LIKE ?", (p + "%",)) if r[0][1:].isdigit()]
    return f"{p}{max(n, default=0) + 1:02d}"


def log(con, item_id, change):
    con.execute("INSERT INTO history VALUES (?,?,?)", (item_id, now(), change))


def link(path: str) -> str:
    if not path:
        return ""
    name = Path(path).name
    return f"[{name}](file://{path.replace(' ', '%20')})"


def rows(con, show_all: bool, kind: str | None):
    q = "SELECT * FROM items WHERE 1=1"
    args = []
    if not show_all:
        q += " AND status NOT IN ('done','dropped')"
    if kind:
        q += " AND kind=?"
        args.append(kind)
    return con.execute(q + " ORDER BY " + ORDER, args).fetchall()


def main(argv: list[str]) -> None:
    if not argv:
        sys.exit(__doc__)
    cmd, rest = argv[0], argv[1:]
    con = connect()
    if cmd in ("list", "md"):
        show_all = "--all" in rest
        kind = rest[rest.index("--kind") + 1] if "--kind" in rest else None
        items = rows(con, show_all, kind)
        if cmd == "list":
            for r in items:
                print(f"{r['id']:4} {r['status']:8} {r['kind']:9} seq={r['seq']:<4} {r['priority']:6} {r['title']}"
                      + (f"  -> {r['prompt']}" if r["prompt"] else ""))
        else:
            for k, head in (("running", "Running"), ("step", "Do next (in order)"),
                            ("question", "Questions for Ayush"), ("reminder", "Reminders")):
                sel = [r for r in items if r["kind"] == k]
                if not sel:
                    continue
                print(f"\n**{head}**\n")
                for r in sel:
                    extra = " ".join(x for x in (link(r["prompt"]),
                                                 f"Send back: {r['send_back']}." if r["send_back"] else "") if x)
                    print(f"- {r['id']} ({r['status']}) {r['title']}" + (f" {extra}" if extra else ""))
    elif cmd == "show":
        r = con.execute("SELECT * FROM items WHERE id=?", (rest[0],)).fetchone()
        if r is None:
            sys.exit("no such id")
        for k in r.keys():
            print(f"{k}: {r[k]}")
        for h in con.execute("SELECT ist, change FROM history WHERE item_id=? ORDER BY rowid", (rest[0],)):
            print(f"  {h['ist']}  {h['change']}")
    elif cmd == "add":
        kind, title = rest[0], rest[1]
        given = [p for p in rest[2:] if p.startswith("id=")]
        pairs = parse_pairs([p for p in rest[2:] if not p.startswith("id=")])
        if kind not in KINDS:
            sys.exit(f"bad kind; allowed: {sorted(KINDS)}")
        item_id = given[0][3:] if given else next_id(con, kind)
        t = now()
        cols = {"id": item_id, "kind": kind, "title": title, "created_ist": t, "updated_ist": t, **pairs}
        con.execute(f"INSERT INTO items ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})", list(cols.values()))
        log(con, item_id, f"added: {title}")
        print(item_id)
    elif cmd in ("set", "done", "drop"):
        item_id = rest[0]
        if con.execute("SELECT 1 FROM items WHERE id=?", (item_id,)).fetchone() is None:
            sys.exit("no such id")
        if cmd == "set":
            pairs = parse_pairs(rest[1:])
        else:
            pairs = {"status": "done" if cmd == "done" else "dropped"}
            if len(rest) > 1:
                pairs["note"] = " ".join(rest[1:])
        pairs["updated_ist"] = now()
        if pairs.get("status") in ("done", "dropped"):
            pairs["closed_ist"] = pairs["updated_ist"]
        con.execute(f"UPDATE items SET {','.join(k + '=?' for k in pairs)} WHERE id=?", [*pairs.values(), item_id])
        log(con, item_id, ", ".join(f"{k}={v}" for k, v in pairs.items() if k != "updated_ist"))
        print(item_id, pairs.get("status", "updated"))
    else:
        sys.exit(__doc__)
    con.commit()


if __name__ == "__main__":
    main(sys.argv[1:])
