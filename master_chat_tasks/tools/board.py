#!/usr/bin/env python3
"""Session board: every issued session gets a 7-char sha (its id and session title).

Usage (from master_chat_tasks/):
  board.py new SLUG STEP PROMPT RESULT [pending_id]   -> prints the new sha
  board.py set SHA field=value ...                    (status, result, note, pending_id)
  board.py show SHA
  board.py md                                         rewrite BOARD.md from board.json
"""
import hashlib
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
DB = HERE / "board.json"
MD = HERE / "BOARD.md"
IST = timezone(timedelta(hours=5, minutes=30))


def now():
    return datetime.now(IST).strftime("%Y-%m-%d %H:%M")


def load():
    return json.loads(DB.read_text()) if DB.exists() else {"rows": []}


def save(b):
    DB.write_text(json.dumps(b, indent=1, ensure_ascii=False))
    lines = ["# Session board (generated from board.json by tools/board.py md; do not edit)", "",
             "Ayush says `done: <sha>`; the master looks the row up, reads RESULT, verifies on disk.", "",
             "| sha | slug | step | status | pending | issued | prompt | result |", "|---|---|---|---|---|---|---|---|"]
    for r in reversed(b["rows"]):
        lines.append(f"| `{r['sha']}` | {r['slug']} | {r['step']} | {r['status']} | {r.get('pending_id','')} | {r['issued']} | {r['prompt']} | {r['result']} |")
    MD.write_text("\n".join(lines) + "\n")


def main(a):
    b = load()
    if a[0] == "new":
        slug, step, prompt, result = a[1:5]
        used = {r["sha"] for r in b["rows"]}
        sha = hashlib.sha1(f"{slug}{step}{time.time_ns()}".encode()).hexdigest()[:7]
        while sha in used:
            sha = hashlib.sha1(sha.encode()).hexdigest()[:7]
        b["rows"].append({"sha": sha, "slug": slug, "step": step, "prompt": prompt, "result": result.replace("<sha>", sha),
                          "status": "issued", "pending_id": a[5] if len(a) > 5 else "", "issued": now(), "note": ""})
        save(b)
        print(sha)
    elif a[0] == "set":
        r = next(r for r in b["rows"] if r["sha"] == a[1])
        for kv in a[2:]:
            k, v = kv.split("=", 1)
            r[k] = v
        r["updated"] = now()
        save(b)
        print("ok")
    elif a[0] == "show":
        print(json.dumps(next(r for r in b["rows"] if r["sha"].startswith(a[1])), indent=1))
    elif a[0] == "md":
        save(b)
        print("ok")


if __name__ == "__main__":
    main(sys.argv[1:] or ["md"])
