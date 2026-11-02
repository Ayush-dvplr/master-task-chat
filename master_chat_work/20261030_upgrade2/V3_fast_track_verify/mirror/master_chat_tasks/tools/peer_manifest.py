#!/usr/bin/env python3
"""Peer research store manifest (SETUP_PLAN_v1 Part 2.1, Q48).

Registry: master_chat_tasks/registry/peer_tasks.json
A task folder is any directory that contains task.toml.
root_sha = sha256 over every file in the task folder, in sorted relative-path
order, feeding for each file: <relpath> NUL <size> NUL <content bytes>.
(Symlinks feed their target string instead of content.)

Commands:
  check <dir>                 list task folders under <dir> that are NEW or CHANGED
                              (root_sha differs) against the registry
  add <task_dir> [options]    add or update one entry (recomputes root_sha)
  add --from-result <result.json> <dir> [--group G] [--studied DATE]
                              add every task listed in a P14 / peer-group result json,
                              matched by slug under <dir>
  show [slug]                 print entries (all, or one slug)
Read-only on task folders; git is used read-only (rev-parse, log).
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

REGISTRY = Path(__file__).resolve().parent.parent / "registry" / "peer_tasks.json"
HASH_RULE = ("sha256 over every file in the task folder, sorted by relative posix path; "
             "per file: relpath NUL size NUL content (symlink: target)")
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))


def root_sha(folder: Path) -> tuple[str, int]:
    files = []
    for dirpath, dirnames, filenames in os.walk(folder, followlinks=False):
        dirnames.sort()
        for name in filenames:
            p = Path(dirpath) / name
            files.append((p.relative_to(folder).as_posix(), p))
        # directory symlinks are not walked; record them as entries
        for d in list(dirnames):
            p = Path(dirpath) / d
            if p.is_symlink():
                files.append((p.relative_to(folder).as_posix(), p))
    files.sort(key=lambda t: t[0])
    h = hashlib.sha256()
    for rel, p in files:
        h.update(rel.encode("utf-8") + b"\0")
        if p.is_symlink():
            data = os.readlink(p).encode("utf-8")
            h.update(b"L%d\0" % len(data))
            h.update(data)
            continue
        h.update(b"%d\0" % p.stat().st_size)
        with open(p, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
    return h.hexdigest(), len(files)


def find_tasks(base: Path) -> list[Path]:
    found = []
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))
        if "task.toml" in filenames:
            found.append(Path(dirpath))
            dirnames[:] = []  # a task folder never nests another task
    return sorted(found)


def git(repo: Path, *args: str) -> str:
    try:
        out = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True)
        return out.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""


def repo_root(p: Path) -> Path | None:
    top = git(p, "rev-parse", "--show-toplevel")
    return Path(top) if top else None


def load() -> dict:
    if REGISTRY.exists():
        return json.loads(REGISTRY.read_text())
    return {"updated_ist": "", "hash_rule": HASH_RULE, "tasks": []}


def save(reg: dict) -> None:
    reg["updated_ist"] = dt.datetime.now(IST).strftime("%Y-%m-%d %H:%M")
    reg["hash_rule"] = HASH_RULE
    reg["tasks"].sort(key=lambda e: e["repo_path"])
    tmp = REGISTRY.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(reg, indent=1, ensure_ascii=False) + "\n")
    tmp.replace(REGISTRY)


def describe(task: Path) -> dict:
    task = task.resolve()
    root = repo_root(task)
    rel = task.relative_to(root).as_posix() if root else task.as_posix()
    parts = rel.split("/")
    sha, n = root_sha(task)
    return {
        "slug": task.name,
        "author": parts[-2] if len(parts) >= 2 else "",
        "reviewer": parts[-3] if len(parts) >= 3 else "",
        "repo": str(root) if root else "",
        "repo_path": rel,
        "anubis_commit": git(root, "log", "-1", "--format=%H", "--", rel) if root else "",
        "repo_head": git(root, "rev-parse", "HEAD") if root else "",
        "root_sha": sha,
        "file_count": n,
    }


def index(reg: dict) -> dict[str, dict]:
    return {e["repo_path"]: e for e in reg["tasks"]}


def cmd_check(args) -> int:
    reg = load()
    idx = index(reg)
    by_slug = {e["slug"]: e for e in reg["tasks"]}
    tasks = find_tasks(Path(args.dir))
    new, changed, same = [], [], 0
    for t in tasks:
        d = describe(t)
        e = idx.get(d["repo_path"]) or by_slug.get(d["slug"])
        if e is None:
            new.append(d)
        elif e["root_sha"] != d["root_sha"]:
            changed.append((d, e))
        else:
            same += 1
    print(f"scanned {len(tasks)} task folders under {args.dir}")
    for d in new:
        print(f"NEW      {d['repo_path']}  root_sha={d['root_sha'][:12]}")
    for d, e in changed:
        print(f"CHANGED  {d['repo_path']}  {e['root_sha'][:12]} -> {d['root_sha'][:12]}")
    print(f"new: {len(new)}  changed: {len(changed)}  unchanged: {same}")
    return 0


def upsert(reg: dict, task: Path, meta: dict) -> dict:
    d = describe(task)
    idx = index(reg)
    e = idx.get(d["repo_path"])
    if e is None:
        e = {}
        reg["tasks"].append(e)
    e.update(d)
    for k, v in meta.items():
        if v is not None:
            e[k] = v
    return e


def cmd_add(args) -> int:
    reg = load()
    if args.from_result:
        res = json.loads(Path(args.from_result).read_text())
        tasks = {t.name: t for t in find_tasks(Path(args.task_dir))}
        missing = []
        for t in res["tasks"]:
            folder = tasks.get(t["slug"])
            if folder is None:
                missing.append(t["slug"])
                continue
            meta = {
                "date_studied": args.studied,
                "group": args.group or res.get("group"),
                "board": res.get("sha"),
                "verdict": t.get("verdict"),
                "tests": t.get("tests"),
                "rubric": t.get("rubric"),
                "genuine_tests_points_lost": t.get("genuine_tests_points_lost"),
                "patterns": t.get("levers", []),
                "report": res.get("report"),
                "result_file": str(Path(args.from_result).resolve()),
            }
            e = upsert(reg, folder, meta)
            print(f"added {e['repo_path']}  {e['verdict']}  root_sha={e['root_sha'][:12]}")
        save(reg)
        if missing:
            print("not found under dir: " + ", ".join(missing), file=sys.stderr)
            return 1
        return 0
    meta = {
        "date_studied": args.studied, "group": args.group, "board": args.board,
        "verdict": args.verdict, "patterns": args.pattern or None, "report": args.report,
    }
    e = upsert(reg, Path(args.task_dir), meta)
    save(reg)
    print(f"added {e['repo_path']}  root_sha={e['root_sha'][:12]}")
    return 0


def cmd_show(args) -> int:
    reg = load()
    rows = [e for e in reg["tasks"] if not args.slug or e["slug"] == args.slug]
    if args.slug and rows:
        print(json.dumps(rows, indent=1, ensure_ascii=False))
        return 0
    print(f"{len(rows)} entries (registry updated {reg.get('updated_ist','')})")
    for e in rows:
        print(f"{e.get('group',''):3} {e.get('verdict',''):8} {e['root_sha'][:12]}  {e['slug']}  ({len(e.get('patterns', []))} patterns)")
    return 0 if rows or not args.slug else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("dir")
    a = sub.add_parser("add")
    a.add_argument("task_dir", help="task folder, or the base dir with --from-result")
    a.add_argument("--from-result")
    a.add_argument("--group")
    a.add_argument("--board")
    a.add_argument("--verdict", choices=["GENUINE", "PARTLY", "ARTEFACT"])
    a.add_argument("--pattern", action="append")
    a.add_argument("--report")
    a.add_argument("--studied", default=dt.datetime.now(IST).strftime("%Y-%m-%d"))
    s = sub.add_parser("show")
    s.add_argument("slug", nargs="?")
    args = ap.parse_args()
    return {"check": cmd_check, "add": cmd_add, "show": cmd_show}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
