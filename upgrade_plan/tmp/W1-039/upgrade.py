#!/usr/bin/env python3
"""upgrade.py: the built in upgrade procedure of the master chat system (P14, Q141, Q142, Q145).

DRAFT, W1-039, 4 Nov 2026. Nothing here is applied before Ayush types PROCEED.
Standard library only. It never runs git and never commits, pushes, checks out or tags anything
(R34, Q145): it runs the checks itself and PRINTS the exact git commands for Ayush to paste.
It never stops a running session, a container or a background script.

  upgrade.py [common flags] status
  upgrade.py [common flags] backup  [--dest DIR] [--records-only]
  upgrade.py [common flags] preflight --to TAG [--backup-dir DIR] [--kit DIR] [--snapshot FILE]
  upgrade.py [common flags] recheck   --from TAG --to TAG [--known-bundle DIR] [--kit DIR]
                                      [--cold-result pass|fail]
  upgrade.py [common flags] rollback  --from TAG --to TAG [--backup-dir DIR]

Common flags (before the subcommand):
  --layout installed   (default) ROOT is the new root folder on the Mac: ROOT/master_chat_tasks,
                       ROOT/master_chat_work, ROOT/SYSTEM_VERSION, ROOT/.gitignore.
  --layout drafts      dry mode for the planning repo: the system files are read from
                       upgrade_plan/drafts and upgrade_plan/tmp, the records from the repo copy
                       of master_chat_tasks (read only). Every write goes under --work.
  --root DIR           installed layout root (default: two folders above this file).
  --drafts DIR         the upgrade_plan folder (drafts layout).
  --work DIR           scratch folder for copies, the test card and the dry backup.

Exit codes: 0 every check PASS or WARN, 1 a check FAIL (BLOCKED), 2 usage error,
3 only WAIT items left (a manual step such as the cold recovery test).

What is SYSTEM and what is DATA (Q141): git versions only the SYSTEM files (tools, templates,
rules, settings, scripts). DATA (records, registry, board, pending.db, logs, auto runs,
QC reports, master_chat_work outputs) is listed in DATA_RECORDS and DATA_WORK below and in
ROOT/.gitignore; it is never in git and gets a daily backup copy (backup subcommand).
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

IST = timezone(timedelta(hours=5, minutes=30))
DEFAULT_SYSTEM_ID = "mc2"
SYSTEM_ID_RE = re.compile(r"^[a-z][a-z0-9]{1,7}$")
TAG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,60}$")

# DATA, relative to the root. Records are small and copied whole every day; master_chat_work is
# large (about 2.2 GB in the repo copy) and is mirrored: a file is copied only when new or changed.
DATA_RECORDS = [
    "master_chat_tasks/board.json", "master_chat_tasks/BOARD.md", "master_chat_tasks/pending.db",
    "master_chat_tasks/log.jsonl", "master_chat_tasks/decisions.jsonl",
    "master_chat_tasks/feedback.jsonl", "master_chat_tasks/lessons.jsonl",
    "master_chat_tasks/open_questions.json", "master_chat_tasks/state.json",
    "master_chat_tasks/GOALS.md", "master_chat_tasks/STATE_CARD.md",
    "master_chat_tasks/STATE_CARD.prev.json", "master_chat_tasks/registry",
    "master_chat_tasks/knowledge/fingerprints", "master_chat_tasks/knowledge/intake",
    "master_chat_tasks/auto/runs", "master_chat_tasks/auto/LATEST",
    "master_chat_tasks/auto/SCHEDULED.json", "master_chat_tasks/auto/SCHEDULED.log",
    "master_chat_tasks/auto/SCHEDULED.out",
]
DATA_WORK = ["master_chat_work"]

# Files the state card needs, copied into --work for the dry layout so the card's own
# STATE_CARD.prev.json lands in the copy and never in the records.
CARD_INPUTS = ["board.json", "registry/tasks.json", "pending.db", "GOALS.md",
               "knowledge/fingerprints/qc.json"]

COLD_PROMPT = (
    "Context recovery for the master chat. You are the master (the brain of the task system). "
    "Read master_chat_tasks/STATE_CARD.md first (regenerate it with python3 tools/state_card.py "
    "if it is older than 1 hour) and follow its RULES IN FORCE. Read nothing else until the next "
    "step needs it. Then tell me in 5 short lines: sessions running and anything LONG (report "
    "only, never stop), questions waiting for me oldest first, news since the last card, today's "
    "progress against the target, and the next step you propose. Do not issue or write anything "
    "until I answer.")
COLD_PASS = [
    "names the goal, and the gate read from settings.json (not a typed number)",
    "names the running sessions and says a LONG session is only reported",
    "names the oldest question waiting for Ayush",
    "uses the handoff format: table with board sha, step, status, clickable link",
    "reads no history file and quotes no superseded lever text",
]


def now_ist():
    return datetime.now(IST)


def sha256(p, limit=None):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(p):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f), None
    except FileNotFoundError:
        return None, "missing"
    except (OSError, ValueError) as e:
        return None, f"not valid JSON: {e}"


def run(cmd, cwd=None, timeout=120, env_extra=None):
    """Run one read only command. Returns (exit code, combined output)."""
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    env.update(env_extra or {})
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, env=env)
        return p.returncode, (p.stdout + p.stderr)
    except subprocess.TimeoutExpired:
        return 124, f"timed out after {timeout} s"
    except OSError as e:
        return 127, str(e)


def q(p):
    """Quote a path for a printed shell command (paths on the Mac hold spaces)."""
    s = str(p)
    return '"' + s.replace('"', '\\"') + '"'


# ---------------------------------------------------------------- layout

class Layout:
    def __init__(self, a):
        self.mode = a.layout
        here = Path(__file__).resolve()
        if self.mode == "installed":
            root = Path(a.root).resolve() if a.root else here.parents[2]
            mct = root / "master_chat_tasks"
            self.root, self.data_root, self.records = root, root, mct
            self.settings = mct / "settings.json"
            self.rules = [mct / "RULES_IN_FORCE.md", mct / "BUILD_RULES.md"]
            self.state_card = mct / "tools" / "state_card.py"
            self.template_check = mct / "tools" / "template_check.py"
            self.manifest = mct / "prompts" / "templates" / "CURRENT.json"
            self.kit_watch = mct / "tools" / "kit_watch.py"
            self.snapshot = mct / "knowledge" / "fingerprints" / "qc.json"
            self.dockslot = mct / "tools" / "dockslot.py"
            self.precheck = mct / "tools" / "precheck.sh"
            self.version_file = root / "SYSTEM_VERSION"
            self.board = mct / "board.json"
            self.auto_dir = mct / "auto"
            self.kit = root / "Terminal_2.0_Harbor_Harness" / "Input_Bundle_QC"
            self.py_files = sorted((mct / "tools").glob("*.py")) + sorted((mct / "auto").glob("*.py"))
            self.work = Path(a.work).resolve() if a.work else root / "master_chat_work" / "_upgrade"
        else:
            up = Path(a.drafts).resolve() if a.drafts else here.parents[2]
            repo = up.parent
            mct = repo / "master_chat_tasks"
            self.root, self.data_root, self.records = repo, repo, mct
            self.settings = up / "drafts/P1/settings.json"
            self.rules = [up / "drafts/P1/RULES_IN_FORCE.md", up / "drafts/P1/BUILD_RULES.md"]
            self.state_card = up / "drafts/P1/state_card.py"
            self.template_check = up / "tmp/W1-032/template_check.py"
            self.manifest = up / "tmp/W1-032/CURRENT.json"
            self.kit_watch = up / "tmp/W1-032/kit_watch.py"
            self.snapshot = mct / "knowledge/fingerprints/qc.json"
            self.dockslot = up / "tmp/W1-031/dockslot.py"
            self.precheck = mct / "tools/precheck.sh"
            self.version_file = up / "tmp/W1-039/SYSTEM_VERSION"
            self.board = mct / "board.json"
            self.auto_dir = mct / "auto"
            self.kit = None
            drafts = [self.state_card, self.template_check, self.kit_watch, self.dockslot,
                      up / "tmp/W1-034/research_prompt.py", up / "tmp/W1-035/runner_report.py", here]
            self.py_files = drafts + sorted((mct / "tools").glob("*.py")) + [mct / "auto/auto.py"]
            self.work = Path(a.work).resolve() if a.work else here.parent / "dry"
        if getattr(a, "kit", None):
            self.kit = Path(a.kit).resolve()
        if getattr(a, "snapshot", None):
            self.snapshot = Path(a.snapshot).resolve()

    def settings_json(self):
        s, _ = load_json(self.settings)
        return s or {}

    def system_id(self):
        sid = (self.settings_json().get("system") or {}).get("id")
        return sid or DEFAULT_SYSTEM_ID

    def version(self):
        try:
            txt = self.version_file.read_text(encoding="utf-8")
            m = re.search(r"^version\s*=\s*(\S+)", txt, re.M)
            return m.group(1) if m else "unknown"
        except OSError:
            return "unknown (no SYSTEM_VERSION file)"


# ---------------------------------------------------------------- checks

class Report:
    def __init__(self, title):
        self.title, self.rows = title, []

    def add(self, status, name, detail=""):
        self.rows.append((status, name, detail))

    def worst(self):
        st = [r[0] for r in self.rows]
        if "FAIL" in st:
            return "FAIL"
        if "WAIT" in st:
            return "WAIT"
        return "PASS"

    def show(self):
        print(f"== {self.title}")
        for st, name, detail in self.rows:
            print(f"  {st:<5} {name}")
            for line in str(detail).splitlines()[:12]:
                if line.strip():
                    print(f"        {line.rstrip()[:150]}")


def check_settings(L, rep):
    s, err = load_json(L.settings)
    if err:
        rep.add("FAIL", "settings.json valid", f"{L.settings}: {err}")
        return
    bad, warn = [], []
    g = s.get("gate", {})
    for k in ("tests", "rubric", "final"):
        v = g.get(k)
        if not isinstance(v, (int, float)) or not 0 < v <= 100:
            bad.append(f"gate.{k} = {v!r}, need a number 1 to 100 (DR2)")
    m = s.get("design_margin")
    if not isinstance(m, (int, float)) or (isinstance(g.get("final"), (int, float)) and m >= g["final"]):
        bad.append(f"design_margin = {m!r}, need a number under gate.final")
    c = s.get("counts", {})
    if not (isinstance(c.get("soft_cap"), int) and isinstance(c.get("hard_cap"), int)
            and c["soft_cap"] <= c["hard_cap"]):
        bad.append(f"counts soft_cap {c.get('soft_cap')!r} and hard_cap {c.get('hard_cap')!r}: soft must be at most hard")
    card = s.get("card", {})
    if not (isinstance(card.get("target_kb"), (int, float)) and isinstance(card.get("hard_kb"), (int, float))
            and card["target_kb"] <= card["hard_kb"]):
        bad.append("card.target_kb must be at most card.hard_kb")
    d = s.get("docker", {})
    if d.get("manager") not in ("dockfree", "dockslot"):
        bad.append(f"docker.manager = {d.get('manager')!r}, need dockfree or dockslot")
    for kind, k in (d.get("kinds") or {}).items():
        if not (isinstance(k.get("mb"), int) and k["mb"] > 0 and isinstance(k.get("cpus"), (int, float))):
            bad.append(f"docker.kinds.{kind} needs mb and cpus")
    r = s.get("runners", {})
    opts = set((r.get("options") or {}).keys())
    if r.get("default") not in opts:
        bad.append(f"runners.default {r.get('default')!r} is not one of the runner options")
    for step, v in (s.get("steps") or {}).items():
        if isinstance(v, dict) and v.get("runner") and v["runner"] not in opts:
            bad.append(f"steps.{step}.runner {v['runner']!r} is not one of the runner options")
    if (s.get("steps") or {}).get("blind", {}).get("runner") != "oc-opus-5":
        bad.append("steps.blind.runner must be oc-opus-5 (Q136, blinds always on Opus 5)")
    sid = (s.get("system") or {}).get("id")
    if sid is None:
        warn.append(f"no system.id key: P17 needs \"system\": {{\"id\": \"{DEFAULT_SYSTEM_ID}\"}} (SYSTEM_ID.md)")
    elif not SYSTEM_ID_RE.match(str(sid)):
        bad.append(f"system.id {sid!r}: 2 to 8 lower case letters or digits, starting with a letter")
    if bad:
        rep.add("FAIL", "settings.json valid", "\n".join(bad + warn))
    elif warn:
        rep.add("WARN", "settings.json valid", "\n".join(warn))
    else:
        rep.add("PASS", "settings.json valid", f"gate {g['tests']}/{g['rubric']}/{g['final']}, manager {d['manager']}")


def check_rules(L, rep):
    missing = [str(p) for p in L.rules if not p.is_file() or p.stat().st_size == 0]
    if missing:
        rep.add("FAIL", "rules files present", "missing or empty: " + ", ".join(missing))
    else:
        rep.add("PASS", "rules files present", ", ".join(f"{p.name} {p.stat().st_size} B" for p in L.rules))


def check_template(L, rep):
    if not L.template_check.is_file():
        rep.add("FAIL", "template_check clean", f"missing {L.template_check}")
        return
    rc, out = run([sys.executable, "-B", str(L.template_check), "--root", str(L.records),
                   "--manifest", str(L.manifest), "--settings", str(L.settings)], timeout=180)
    total = [ln for ln in out.splitlines() if ln.startswith("TOTAL")]
    if rc == 0:
        rep.add("PASS", "template_check clean", total[0] if total else "no findings")
    else:
        rep.add("FAIL", "template_check clean",
                (total[0] if total else out[-400:]) + "\ncurrent templates still hold retired rules or typed settings (P10 step)")


def check_kit(L, rep):
    if not L.kit_watch.is_file():
        rep.add("FAIL", "kit_watch status", f"missing {L.kit_watch}")
        return
    if not L.kit or not Path(L.kit).is_dir():
        rep.add("WAIT" if L.mode == "installed" else "WARN", "kit_watch status",
                f"live kit not found ({L.kit}); give --kit")
        return
    rc, out = run([sys.executable, "-B", str(L.kit_watch), "card", "--kit", str(L.kit),
                   "--snapshot", str(L.snapshot)], timeout=120)
    line = out.strip().splitlines()[-1] if out.strip() else ""
    if rc == 0:
        rep.add("PASS", "kit_watch status", line)
    elif rc == 1:
        rep.add("WARN", "kit_watch status", line + "\nkit changed since the snapshot: classify it (S7, Q86) before or after the switch; a MAJOR change blocks")
    else:
        rep.add("FAIL", "kit_watch status", out[-400:])


def card_root(L):
    """The folder the state card is built in. Installed: a copy under work, so a recheck never
    touches the live card; drafts: a copy of the records plus the draft rules and settings."""
    dst = L.work / "card_root"
    if dst.exists():
        shutil.rmtree(dst)
    for rel in CARD_INPUTS:
        src = L.records / rel
        if src.is_file():
            (dst / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst / rel)
    dst.mkdir(parents=True, exist_ok=True)
    shutil.copy2(L.settings, dst / "settings.json") if L.settings.is_file() else None
    for r in L.rules:
        if r.is_file():
            shutil.copy2(r, dst / r.name)
    return dst


def check_card(L, rep):
    if not L.state_card.is_file():
        rep.add("FAIL", "state card builds", f"missing {L.state_card}")
        return
    croot = card_root(L)
    out_file = croot / "STATE_CARD.md"
    rc, out = run([sys.executable, "-B", str(L.state_card), "--root", str(croot), "--out", str(out_file)])
    if rc != 0 or not out_file.is_file():
        rep.add("FAIL", "state card builds", out[-400:])
        return
    text = out_file.read_text(encoding="utf-8")
    kb = len(text.encode("utf-8")) / 1024
    hard = float((L.settings_json().get("card") or {}).get("hard_kb", 8))
    probs = []
    if kb > hard:
        probs.append(f"{kb:.1f} KB over the hard limit {hard:g} KB")
    if "<protect>" not in text:
        probs.append("rules block not wrapped in <protect>")
    if "MISSING: RULES_IN_FORCE.md" in text:
        probs.append("RULES_IN_FORCE.md not found by the card")
    left = [ln for ln in text.splitlines() if ln.startswith("LEFT OUT")]
    detail = f"{kb:.1f} KB (hard {hard:g} KB), {text.count(chr(10))} lines" + (f"; {left[0]}" if left else "")
    rep.add("FAIL" if probs else "PASS", "state card builds", "; ".join(probs) or detail)


def check_tools(L, rep):
    bad, ok = [], 0
    for p in L.py_files:
        if not p.is_file():
            bad.append(f"missing {p}")
            continue
        try:
            compile(p.read_text(encoding="utf-8"), str(p), "exec")  # in memory, no __pycache__
            ok += 1
        except SyntaxError as e:
            bad.append(f"{p.name}: {e}")
    helps = []
    for p in (L.state_card, L.template_check, L.kit_watch, L.dockslot):
        if p.is_file():
            rc, out = run([sys.executable, "-B", str(p), "--help"], timeout=30)
            if rc != 0:
                bad.append(f"{p.name} --help exit {rc}")
            else:
                helps.append(p.name)
    st_dir = L.work / "dockslot_selftest"
    if L.dockslot.is_file():
        rc, out = run([sys.executable, "-B", str(L.dockslot), "--settings", str(L.settings),
                       "--state-dir", str(st_dir), "--fake-capacity", "vm_mb=15970,cpus=8", "status"], timeout=60)
        if rc != 0:
            bad.append(f"dockslot status (fake capacity) exit {rc}: {out[-200:]}")
        shutil.rmtree(st_dir, ignore_errors=True)
    detail = f"{ok} Python files compile; --help ok: {', '.join(helps)}; dockslot fake status ok"
    rep.add("FAIL" if bad else "PASS", "tool self tests", "\n".join(bad) if bad else detail)


def pid_alive(pid):
    try:
        os.kill(int(pid), 0)
        return True
    except (OSError, ValueError, TypeError):
        return False


def check_idle(L, rep):
    """No session of THIS system running: board rows running or issued, a live auto run, held
    dockslot leases. The old system's sessions are not counted (they are foreign, P17)."""
    busy = []
    b, err = load_json(L.board)
    rows = (b or {}).get("rows", []) if isinstance(b, dict) else (b or [])
    if err:
        busy.append(f"board.json {err}")
    for r in rows:
        if r.get("status") in ("running", "issued"):
            busy.append(f"board {r.get('sha', '?')} {r.get('status')} {r.get('slug', '')}")
    latest = L.auto_dir / "LATEST"
    if latest.is_file():
        st, _ = load_json(Path(latest.read_text().strip()) / "state.json")
        for k in ("watcher_pid", "worker_pid"):
            if st and st.get(k) and pid_alive(st[k]):
                busy.append(f"auto run live: {k} {st[k]}")
    if L.mode == "installed" and L.dockslot.is_file():
        rc, out = run([sys.executable, "-B", str(L.dockslot), "status", "--json"], timeout=60)
        try:
            leases = json.loads(out).get("leases", [])
            busy += [f"dockslot lease {x.get('id')} {x.get('kind')}" for x in leases]
        except ValueError:
            pass
    if busy:
        note = "" if L.mode == "installed" else "\n(records copy in the repo; on the Mac this must read 0)"
        rep.add("FAIL", "no session running", f"{len(busy)} busy:\n" + "\n".join(busy[:8]) + note)
    else:
        rep.add("PASS", "no session running", "board, auto run and dockslot leases idle")


def today_backup(backup_dir):
    d = Path(backup_dir) / now_ist().strftime("%Y%m%d")
    return d, d / "MANIFEST.json"


def check_backup(L, rep, backup_dir):
    d, man = today_backup(backup_dir)
    m, err = load_json(man)
    if err:
        rep.add("FAIL", "data backup done today", f"{man}: {err}; run: upgrade.py backup --dest {q(backup_dir)}")
        return
    changed = []
    for rel, info in m.get("records", {}).items():
        src = L.data_root / rel
        if not src.is_file() or sha256(src) != info["sha256"]:
            changed.append(rel)
    if changed:
        rep.add("FAIL", "data backup done today",
                f"{len(changed)} record files changed since the backup at {m.get('taken')}: " + ", ".join(changed[:5]))
    else:
        rep.add("PASS", "data backup done today",
                f"{m.get('taken')}: {len(m.get('records', {}))} record files match; work mirror {m.get('work_files', 0)} files")


def check_dockslot(L, rep):
    if not L.dockslot.is_file():
        rep.add("FAIL", "dockslot status", f"missing {L.dockslot}")
        return
    if L.mode == "installed":
        args = ["status"]
    else:
        args = ["--state-dir", str(L.work / "dockslot_state"), "--fake-capacity", "vm_mb=15970,cpus=8", "status"]
    rc, out = run([sys.executable, "-B", str(L.dockslot), "--settings", str(L.settings)] + args, timeout=60)
    first = out.strip().splitlines()[:3]
    manager = (L.settings_json().get("docker") or {}).get("manager")
    rep.add("PASS" if rc == 0 else "FAIL", "dockslot status",
            f"manager {manager}" + ("" if L.mode == "installed" else " (fake capacity, dry)") + "\n" + "\n".join(first))
    shutil.rmtree(L.work / "dockslot_state", ignore_errors=True) if L.mode != "installed" else None


def check_precheck(L, rep, bundle):
    bundle = bundle or (L.settings_json().get("upgrade") or {}).get("known_bundle")
    if not bundle:
        rep.add("WAIT", "dry precheck on a known bundle", "no bundle: give --known-bundle or settings upgrade.known_bundle")
        return
    if not L.precheck.is_file() or not Path(bundle).is_dir():
        rep.add("WAIT", "dry precheck on a known bundle", f"needs {L.precheck} and {bundle}")
        return
    kit_line = L.precheck.read_text(encoding="utf-8", errors="replace")
    m = re.search(r'^KIT="([^"]+)"', kit_line, re.M)
    if m and not Path(m.group(1)).is_dir():
        rep.add("SKIP" if L.mode != "installed" else "FAIL", "dry precheck on a known bundle",
                f"precheck.sh reads the kit at a fixed path {m.group(1)}, not present here (needs the Mac)")
        return
    rc, out = run(["bash", str(L.precheck), str(bundle)], timeout=600)
    rep.add("PASS" if rc == 0 else "FAIL", "dry precheck on a known bundle",
            f"{bundle}: exit {rc}\n" + "\n".join(out.strip().splitlines()[-4:]))


# ---------------------------------------------------------------- commands

def git_switch_commands(L, frm, to):
    stamp = now_ist().strftime("%Y%m%dT%H%M")
    return [
        f"cd {q(L.root)}",
        "git status --porcelain            # must print nothing: no uncommitted system edits",
        "git fetch origin --tags           # only if the new version comes from GitHub",
        f"git tag before-{to.replace('/', '-')}-{stamp}   # marks the version you run now ({frm}), local only",
        f"git checkout {to}",
        f"python3 master_chat_tasks/tools/upgrade.py recheck --from {frm} --to {to}",
    ]


def rollback_commands(L, frm, to, backup_dir):
    d, _ = today_backup(backup_dir)
    cmds = [
        f"cd {q(L.root)}",
        f"git checkout {to}                # back to the version that worked",
        f"python3 master_chat_tasks/tools/upgrade.py recheck --from {frm} --to {to}",
        "# Only if the failed version changed DATA (for example a registry field): restore the records",
        "# from today's backup. Look first with --dry-run, then run without it.",
        f"rsync -a --dry-run {q(str(d / 'records') + '/')} {q(str(L.root) + '/')}",
    ]
    return cmds


def cmd_status(L, a):
    print(f"system id      {L.system_id()}")
    print(f"version        {L.version()}")
    print(f"layout         {L.mode}  root {L.root}")
    print(f"settings       {L.settings}")
    print(f"work folder    {L.work}")
    present = [r for r in DATA_RECORDS if (L.data_root / r).exists()]
    print(f"data records   {len(present)} of {len(DATA_RECORDS)} paths present; work {', '.join(DATA_WORK)}")
    return 0


def iter_files(p):
    if p.is_file():
        yield p
    elif p.is_dir():
        for dp, dn, fn in os.walk(p):
            dn[:] = [x for x in dn if x != "__pycache__"]
            for f in fn:
                yield Path(dp) / f


def cmd_backup(L, a):
    dest = Path(a.dest).resolve() if a.dest else L.work / "backup"
    d, man = today_backup(dest)
    rec_dir = d / "records"
    records = {}
    for rel in DATA_RECORDS:
        for f in iter_files(L.data_root / rel):
            r = f.relative_to(L.data_root).as_posix()
            out = rec_dir / r
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, out)
            records[r] = {"sha256": sha256(f), "bytes": f.stat().st_size}
    work_files = copied = 0
    if not a.records_only:
        mirror = dest / "work_mirror"   # one mirror, updated in place: new or changed files only
        for rel in DATA_WORK:
            for f in iter_files(L.data_root / rel):
                work_files += 1
                out = mirror / f.relative_to(L.data_root)
                st = f.stat()
                if out.is_file() and out.stat().st_size == st.st_size and int(out.stat().st_mtime) == int(st.st_mtime):
                    continue
                out.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, out)
                copied += 1
    manifest = {"taken": now_ist().strftime("%Y-%m-%d %H:%M IST"), "system_id": L.system_id(),
                "version": L.version(), "records": records, "work_files": work_files,
                "work_copied": copied, "records_only": bool(a.records_only)}
    d.mkdir(parents=True, exist_ok=True)
    man.write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    print(f"BACKUP {d}: {len(records)} record files"
          + (" (records only; master_chat_work mirror skipped)" if a.records_only
             else f"; work mirror {work_files} files, {copied} copied"))
    return 0


def cmd_preflight(L, a):
    if not TAG_RE.match(a.to):
        print(f"bad tag {a.to!r}")
        return 2
    L.work.mkdir(parents=True, exist_ok=True)
    rep = Report(f"PREFLIGHT {L.system_id()} {L.version()} -> {a.to}  ({now_ist():%Y-%m-%d %H:%M} IST, layout {L.mode})")
    check_settings(L, rep)
    check_rules(L, rep)
    check_template(L, rep)
    check_kit(L, rep)
    check_card(L, rep)
    check_tools(L, rep)
    check_idle(L, rep)
    check_backup(L, rep, Path(a.backup_dir).resolve() if a.backup_dir else L.work / "backup")
    rep.show()
    verdict = rep.worst()
    print()
    if verdict == "FAIL":
        print("VERDICT: BLOCKED. Fix every FAIL above, then run preflight again. No git command is printed.")
        if L.mode == "drafts":
            print("(dry mode only) On READY it would print these commands for Ayush:")
            for c in git_switch_commands(L, L.version(), a.to):
                print("  " + c)
        return 1
    print("VERDICT: READY. Paste these commands yourself (upgrade.py never runs git):")
    for c in git_switch_commands(L, L.version(), a.to):
        print("  " + c)
    return 0 if verdict == "PASS" else 3


def cmd_recheck(L, a):
    L.work.mkdir(parents=True, exist_ok=True)
    rep = Report(f"RECHECK after {a.frm} -> {a.to}  ({now_ist():%Y-%m-%d %H:%M} IST, layout {L.mode})")
    check_settings(L, rep)
    check_card(L, rep)
    check_template(L, rep)
    if a.cold_result == "pass":
        rep.add("PASS", "cold recovery test", "Ayush ran the prompt in a fresh master session: pass")
    elif a.cold_result == "fail":
        rep.add("FAIL", "cold recovery test", "Ayush ran the prompt in a fresh master session: fail")
    else:
        rep.add("WAIT", "cold recovery test",
                "paste this prompt into a fresh master session, then rerun with --cold-result pass|fail:\n"
                + COLD_PROMPT + "\nPASS when the reply: " + "; ".join(COLD_PASS))
    check_precheck(L, rep, a.known_bundle)
    check_dockslot(L, rep)
    rep.show()
    verdict = rep.worst()
    print()
    if verdict == "FAIL":
        print("VERDICT: RECHECK FAILED. Roll back with these commands (paste them yourself):")
        for c in rollback_commands(L, a.to, a.frm, Path(a.backup_dir).resolve() if a.backup_dir else L.work / "backup"):
            print("  " + c)
        return 1
    if verdict == "WAIT":
        print("VERDICT: WAITING for the manual items above. Keep the new version only if they pass.")
        print("If one fails, roll back with:")
        for c in rollback_commands(L, a.to, a.frm, Path(a.backup_dir).resolve() if a.backup_dir else L.work / "backup"):
            print("  " + c)
        return 3
    print(f"VERDICT: UPGRADE GOOD. To mark it as the stable version, paste:")
    print(f"  cd {q(L.root)}")
    print(f"  git branch -f stable {a.to}")
    return 0


def cmd_rollback(L, a):
    print(f"ROLLBACK {a.frm} -> {a.to}. Paste these commands yourself (upgrade.py never runs git):")
    for c in rollback_commands(L, a.frm, a.to, Path(a.backup_dir).resolve() if a.backup_dir else L.work / "backup"):
        print("  " + c)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Built in upgrade procedure (P14). Prints git commands, never runs git.")
    ap.add_argument("--layout", choices=["installed", "drafts"], default="installed")
    ap.add_argument("--root")
    ap.add_argument("--drafts")
    ap.add_argument("--work")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    p = sub.add_parser("backup")
    p.add_argument("--dest")
    p.add_argument("--records-only", action="store_true")
    p = sub.add_parser("preflight")
    p.add_argument("--to", required=True)
    p.add_argument("--backup-dir")
    p.add_argument("--kit")
    p.add_argument("--snapshot")
    p = sub.add_parser("recheck")
    p.add_argument("--from", dest="frm", required=True)
    p.add_argument("--to", required=True)
    p.add_argument("--known-bundle")
    p.add_argument("--kit")
    p.add_argument("--backup-dir")
    p.add_argument("--cold-result", choices=["pass", "fail"])
    p = sub.add_parser("rollback")
    p.add_argument("--from", dest="frm", required=True)
    p.add_argument("--to", required=True)
    p.add_argument("--backup-dir")
    a = ap.parse_args(argv)
    L = Layout(a)
    fn = {"status": cmd_status, "backup": cmd_backup, "preflight": cmd_preflight,
          "recheck": cmd_recheck, "rollback": cmd_rollback}[a.cmd]
    return fn(L, a)


if __name__ == "__main__":
    sys.exit(main())
