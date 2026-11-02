#!/usr/bin/env python3
"""Issue one session: cap check, board row, pending step, saved prompt, link-only handoff.

  issue.py SLUG KIND DRAFT OUT [--title T] [--override "Ayush's exact words"] [--by WHO] [--dry-run]
           [--force-lint "reason"]
  issue.py --lint FILE [--slug SLUG]     lint only (exit 1 on a hard finding, 0 otherwise)

KIND is one of: build probe qc fix harden rebuild blind loss ql research run adhoc
DRAFT is the prompt text written by the master. It must contain the literal `<SHA>`
(the "Board id: `<SHA>`" line and the name_session.py call); issue.py fills in the real sha.
OUT is the session's output folder; `<SHA>` is allowed in it too.
The draft may also use `<PROMPT_PATH>` (the saved prompt file) and `<OUT>` (OUT with the sha filled in).

Hard refusals (plan v1 U1, approved 24 Oct 11:15). Only --override with Ayush's verbatim
line lifts one; the line is logged to decisions.jsonl.
  fix      more than 2 fix rounds since the last QC round
  qc       more than 2 QC rounds in the v3 regime, or the task already passed QC (stop at first PASS)
  harden   the task already passed QC (no harden after PASS)
  harden/rebuild  3 harden or rebuild rounds already issued (drop rule, Ayush 22 Oct 22:34)
  any      task stage is dropped, killed or parked
  any      time box: 8 sessions for this task since the later of the v3 regime start and the
           task's last stage change (pipeline.stage_since). Not counted: ql sessions, and
           qc/fix/harden sessions while the task is pushed with an open QL round.
"Passed" = stage qc_pass, gate_runs, pl_ready, or pushed without an open QL round.
Open QL round = pipeline.ql_round set (not empty/0/none) and pipeline.ql_last not starting "closed".
The override row in decisions.jsonl records "by": --by, default "master (auto)" when AUTO_RUN is
set or the run in auto/LATEST is live, else "Ayush". A same-minute prompt name gets _2, _3 ...
The handoff printed at the end is the only thing Ayush gets: board sha, step, one clickable link.

Prompt lint (min plan A-3, Ayush 31 Oct), run on every draft before issuing:
  hard (always refused)  a leftover template placeholder [[NAME]];
                         two different oracle counts (oracle xN / oracle-1..oracle-N) outside lines that
                         talk about the QC kit
  warning (refused unless --force-lint "<reason>", reason logged to decisions.jsonl)
                         a gate target (`gate ... final < N`, `tests < N`, `rubric < N`) that differs from
                         the live gate (tests<85, rubric<85, final<40) with no decisions.jsonl row naming
                         the slug and that number;
                         a predicted/target score bar (`predicted final <= N`) with no `Reachable:` line
                         saying how the allowed edits can reach it (cold-chain 30 Oct 12:00 lesson)
MT_ROOT env overrides the master_chat_tasks root (tests).
"""
import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

HERE = Path(os.environ.get("MT_ROOT") or Path(__file__).resolve().parent.parent)
ROOT = HERE.parent
IST = timezone(timedelta(hours=5, minutes=30))
REGIME = "2026-10-24 11:26"  # plan v1 approval; v3 caps count from here
KINDS = {"build", "probe", "qc", "fix", "harden", "rebuild", "blind", "loss", "ql", "research", "run", "adhoc"}
LEGACY = {"qc": ("P11", "QC"), "fix": ("P12",), "harden": ("P9", "P10"), "rebuild": ("P10",)}
TIME_BOX = 8
TASK_KINDS = KINDS - {"research", "adhoc"}
LIVE_GATE = {"tests": 85, "rubric": 85, "final": 40}
PLACEHOLDER_RE = re.compile(r"\[\[[A-Z][A-Z0-9_]*\]\]")
ORACLE_RE = re.compile(r"oracle\s*(?:1\.0\s*)?[x×]\s*(\d+)|oracle-1\s*\.\.\s*oracle-(\d+)", re.I)
GATE_RE = re.compile(r"gate\b[^\n]{0,60}?\b(tests|rubric|final)\s*<\s*(\d+)", re.I)
GATE_MORE_RE = re.compile(r"\b(tests|rubric|final)\s*<\s*(\d+)", re.I)
BAR_RE = re.compile(r"(?:pred(?:icted)?|target)\s+final\s*(?:<=|≤|<)\s*(\d+)", re.I)


def now():
    return datetime.now(IST)


def board():
    return json.loads((HERE / "board.json").read_text())["rows"]


def kind_of(row):
    if row.get("kind"):
        return row["kind"]
    step = row["step"]
    for k, prefixes in LEGACY.items():
        if step.startswith(prefixes):
            return k
    return "other"


def pipeline(slug):
    tasks = json.loads((HERE / "registry" / "tasks.json").read_text())["tasks"]
    t = next((x for x in tasks if x["slug"] == slug), None)
    return (t or {}).get("pipeline", {})


def ql_open(p):
    rnd = str(p.get("ql_round", "")).strip().lower()
    return rnd not in ("", "0", "none") and not str(p.get("ql_last", "")).strip().lower().startswith("closed")


def refusals(slug, kind):
    rows = [r for r in board() if r["slug"] == slug and r["status"] != "dropped"]
    new = [r for r in rows if r["issued"] >= REGIME]
    p = pipeline(slug)
    st = p.get("stage", "")
    open_ql = st == "pushed" and ql_open(p)
    out = []
    if st in ("dropped", "killed", "parked"):
        out.append(f"task stage is {st}")
    passed = st in ("qc_pass", "gate_runs", "pl_ready") or (st == "pushed" and not open_ql)
    if kind == "fix":
        last_qc = max((i for i, r in enumerate(new) if kind_of(r) == "qc"), default=-1)
        fixes = [r for r in new[last_qc + 1:] if kind_of(r) == "fix"]
        if len(fixes) >= 2:
            out.append(f"2 fix rounds already since the last QC ({', '.join(r['sha'] for r in fixes)})")
    if kind == "qc":
        if passed:
            out.append(f"task already passed QC (stage {st}); stop at first PASS")
        qcs = [r for r in new if kind_of(r) == "qc"]
        if len(qcs) >= 2:
            out.append(f"2 QC rounds already in v3 ({', '.join(r['sha'] for r in qcs)})")
    if kind == "harden" and passed:
        out.append(f"task already passed QC (stage {st}); no harden after PASS")
    if kind in ("harden", "rebuild"):
        hr = [r for r in rows if kind_of(r) in ("harden", "rebuild")]
        if len(hr) >= 3:
            out.append(f"drop rule: {len(hr)} harden/rebuild rounds already ({', '.join(r['sha'] for r in hr)})")
    since = max(REGIME, p.get("stage_since", ""))
    free = {"ql"} | ({"qc", "fix", "harden"} if open_ql else set())
    boxed = [r for r in rows if r["issued"] >= since and kind_of(r) not in free]
    if kind in TASK_KINDS and kind not in free and len(boxed) >= TIME_BOX:
        out.append(f"time box: {len(boxed)} sessions for {slug} since {since}")
    return out


def decisions_text():
    try:
        return (HERE / "decisions.jsonl").read_text(errors="replace").splitlines()
    except OSError:
        return []


def lint(text, slug=""):
    """Return (hard, warnings) lists of strings for one prompt text."""
    hard, warn = [], []
    ph = sorted(set(PLACEHOLDER_RE.findall(text)))
    if ph:
        hard.append(f"leftover template placeholder(s): {', '.join(ph)}")
    counts = {}
    for n, line in enumerate(text.splitlines(), 1):
        if re.search(r"\bkit\b", line, re.I):
            continue
        for m in ORACLE_RE.finditer(line):
            counts.setdefault(int(m.group(1) or m.group(2)), []).append(n)
    if len(counts) > 1:
        hard.append("two different oracle counts: " +
                    "; ".join(f"x{k} at line {', '.join(map(str, v[:3]))}" for k, v in sorted(counts.items())))
    rows = [r for r in decisions_text() if slug and slug in r]
    seen = set()
    for m in GATE_RE.finditer(text):
        span = text[m.start():text.find("\n", m.start()) if "\n" in text[m.start():] else len(text)]
        for g in GATE_MORE_RE.finditer(span):
            key, n = g.group(1).lower(), int(g.group(2))
            if n == LIVE_GATE[key] or (key, n) in seen:
                continue
            seen.add((key, n))
            if not any(re.search(rf"<\s*{n}\b", r) for r in rows):
                warn.append(f"gate target {key}<{n} differs from the live gate {key}<{LIVE_GATE[key]} and no "
                            f"decisions.jsonl row names {slug or '(no slug)'} with <{n}")
    if BAR_RE.search(text) and not re.search(r"^\s*[-*]?\s*Reachable:", text, re.M | re.I):
        bars = sorted(set(BAR_RE.findall(text)))
        warn.append(f"score bar(s) final <= {', '.join(bars)} with no 'Reachable:' line (how can the allowed "
                    "edits reach it?)")
    return hard, warn


def auto_live():
    if os.environ.get("AUTO_RUN"):
        return True
    try:
        run = Path((HERE / "auto" / "LATEST").read_text().strip())
        pid = int(json.loads((run / "state.json").read_text()).get("watcher_pid") or 0)
    except (OSError, ValueError):
        return False
    if pid <= 0:
        return False
    cmd = subprocess.run(["ps", "-p", str(pid), "-o", "command="], capture_output=True, text=True).stdout
    return "auto.py" in cmd


def link(path):
    return f"file://{quote(str(path))}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("kind", choices=sorted(KINDS))
    ap.add_argument("draft")
    ap.add_argument("out")
    ap.add_argument("--title", default="")
    ap.add_argument("--override", default="")
    ap.add_argument("--by", default="", help="who typed the override (default: 'master (auto)' in auto mode, else 'Ayush')")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force-lint", default="", help="reason to issue despite lint warnings (logged)")
    a = ap.parse_args()

    text = Path(a.draft).read_text()
    hard, warn = lint(text, a.slug)
    if hard:
        sys.exit("REFUSED (lint):\n  - " + "\n  - ".join(hard))
    if warn and not a.force_lint:
        sys.exit("REFUSED (lint warnings):\n  - " + "\n  - ".join(warn) +
                 "\nFix the draft, or rerun with --force-lint \"<reason>\" (logged).")
    if "<SHA>" not in text:
        sys.exit("REFUSED: draft has no <SHA> placeholder (Board id line + name_session.py call)")
    if "name_session.py" not in text:
        sys.exit("REFUSED: draft does not call tools/name_session.py")
    bad = refusals(a.slug, a.kind)
    if bad and not a.override:
        sys.exit("REFUSED (cap):\n  - " + "\n  - ".join(bad) + "\nAsk Ayush; rerun with --override \"<his exact words>\" only if he says so.")

    t = now()
    stamp = t.strftime("%Y%m%dT%H%M")
    folder = "_adhoc" if a.kind in ("research", "adhoc") else a.slug
    title = a.title or f"{a.kind} {a.slug}"
    base = f"{stamp}_{a.kind}" if folder != "_adhoc" else f"{stamp}_{a.slug}"
    dest = HERE / "prompts" / "issued" / folder / f"{base}.md"
    n = 1
    while dest.exists():
        n += 1
        dest = dest.with_name(f"{base}_{n}.md")
    if a.dry_run:
        print(f"DRY RUN ok: would write {dest}; refusals={bad or 'none'}; override={'yes' if a.override else 'no'}")
        return

    def run(*cmd):
        return subprocess.run(["python3", *cmd], cwd=HERE, check=True, capture_output=True, text=True).stdout.strip()

    rel = dest.relative_to(ROOT)
    sha = run("tools/board.py", "new", a.slug, title, str(rel), a.out)
    pid = run("tools/pending.py", "add", "step", f"{title} ({sha})", f"prompt={rel}").split()[-1]
    out_dir = a.out.replace("<SHA>", sha)
    run("tools/board.py", "set", sha, f"pending_id={pid}", f"kind={a.kind}", f"result={out_dir}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text.replace("<SHA>", sha).replace("<PROMPT_PATH>", str(dest)).replace("<OUT>", out_dir))
    if a.override:
        with open(HERE / "decisions.jsonl", "a") as f:
            by = a.by or ("master (auto)" if auto_live() else "Ayush")
            f.write(json.dumps({"ist": t.strftime("%Y-%m-%d %H:%M"), "by": by,
                                "decision": f"cap override for {a.slug} {a.kind} ({sha}): {'; '.join(bad)}",
                                "verbatim": a.override}, ensure_ascii=False) + "\n")
    if warn:
        with open(HERE / "decisions.jsonl", "a") as f:
            f.write(json.dumps({"ist": t.strftime("%Y-%m-%d %H:%M"), "by": "master",
                                "decision": f"lint warnings accepted for {a.slug} {a.kind} ({sha}): {'; '.join(warn)}",
                                "verbatim": a.force_lint}, ensure_ascii=False) + "\n")
    print(f"Board `{sha}` · {title} · OUT {out_dir}")
    print(f"[{title}]({link(dest)})")


def lint_main(argv):
    ap = argparse.ArgumentParser(prog="issue.py --lint")
    ap.add_argument("file")
    ap.add_argument("--slug", default="")
    a = ap.parse_args(argv)
    hard, warn = lint(Path(a.file).read_text(errors="replace"), a.slug)
    for h in hard:
        print(f"HARD  {h}")
    for w in warn:
        print(f"WARN  {w}")
    if not hard and not warn:
        print("lint clean")
    sys.exit(1 if hard else 0)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--lint":
        lint_main(sys.argv[2:])
    else:
        main()
