#!/usr/bin/env python3
"""Issue one session: cap check, board row, pending step, saved prompt, link-only handoff.

  issue.py SLUG KIND DRAFT OUT [--title T] [--override "Ayush's exact words"] [--dry-run]

KIND is one of: build probe qc fix harden rebuild blind loss research run adhoc
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
  any      time box: 8 sessions for this task in the v3 regime
The handoff printed at the end is the only thing Ayush gets: board sha, step, one clickable link.
"""
import argparse
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

HERE = Path(__file__).resolve().parent.parent
ROOT = HERE.parent
IST = timezone(timedelta(hours=5, minutes=30))
REGIME = "2026-10-24 11:26"  # plan v1 approval; v3 caps count from here
KINDS = {"build", "probe", "qc", "fix", "harden", "rebuild", "blind", "loss", "research", "run", "adhoc"}
LEGACY = {"qc": ("P11", "QC"), "fix": ("P12",), "harden": ("P9", "P10"), "rebuild": ("P10",)}
TIME_BOX = 8
TASK_KINDS = KINDS - {"research", "adhoc"}


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


def stage(slug):
    tasks = json.loads((HERE / "registry" / "tasks.json").read_text())["tasks"]
    t = next((x for x in tasks if x["slug"] == slug), None)
    return (t or {}).get("pipeline", {}).get("stage", "")


def refusals(slug, kind):
    rows = [r for r in board() if r["slug"] == slug and r["status"] != "dropped"]
    new = [r for r in rows if r["issued"] >= REGIME]
    st = stage(slug)
    out = []
    if st in ("dropped", "killed", "parked"):
        out.append(f"task stage is {st}")
    passed = st in ("qc_pass", "gate_runs", "pl_ready")
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
    if kind in TASK_KINDS and len(new) >= TIME_BOX:
        out.append(f"time box: {len(new)} sessions for {slug} since {REGIME}")
    return out


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
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    text = Path(a.draft).read_text()
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
    name = f"{stamp}_{a.kind}.md" if folder != "_adhoc" else f"{stamp}_{a.slug}.md"
    dest = HERE / "prompts" / "issued" / folder / name
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
            f.write(json.dumps({"ist": t.strftime("%Y-%m-%d %H:%M"), "who": "Ayush",
                                "decision": f"cap override for {a.slug} {a.kind} ({sha}): {'; '.join(bad)}",
                                "verbatim": a.override}, ensure_ascii=False) + "\n")
    print(f"Board `{sha}` · {title} · OUT {out_dir}")
    print(f"[{title}]({link(dest)})")


if __name__ == "__main__":
    main()
