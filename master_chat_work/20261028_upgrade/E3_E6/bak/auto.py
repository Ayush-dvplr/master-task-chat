#!/usr/bin/env python3
"""Auto mode: run the master chat's pipeline while Ayush is away (replaces night mode).

The master chat (opencode TUI started with `oc master -s <id>`) keeps deciding as
by day, using AUTO_POLICY.md and the run's PLAN.md in place of Ayush's answers.
This script is its hands and the watcher that replaces Ayush's "done: <sha>" messages.

  auto.py start --until HH:MM [--at HH:MM] [--plan FILE] [--label L] [--workers N] [--harness N]
                [--ramp HH:MM W H] [--no-adopt]
                                    new run folder, worker server, watcher, caffeinate;
                                    adopts every running board.json row.  With --at: checks now,
                                    then a waiter starts it at that IST time (SCHEDULED.json)
  auto.py cancel                    remove a scheduled start
  auto.py resume                    after a reboot/terminal close: restart server + watcher,
                                    continue interrupted workers
  auto.py adopt SHA [--session ID]  track a session started elsewhere (found by title = SHA)
  auto.py spawn SHA PROMPT.md       new worker session titled SHA, prompt = file text
  auto.py send SHA TEXT|@FILE       next message to an idle/finished worker
  auto.py harness BUNDLE            harness queue recipe (limited runs at a time)
  auto.py limits --workers N --harness N
  auto.py status                    workers, harness, watcher, network, retries, plan
  auto.py stop                      start nothing new; watcher winds down
  auto.py watch                     the watcher loop (started by `start`/`resume`)

Run folders live in AUTO_DIR/runs/<YYYYMMDDTHHMM>_<label>/ (state.json, events.jsonl,
REPORT.md, PLAN.md, logs/); AUTO_DIR/LATEST holds the current one.
Paths can be moved for tests with AUTO_DIR, AUTO_PROJECT, AUTO_HARNESS, AUTO_REGISTRY,
AUTO_SECRET, AUTO_DB (opened read-only, never written), AUTO_BOARD, AUTO_POLL_S, AUTO_NET_URL.
"""
from __future__ import annotations

import argparse
import base64
import fcntl
import json
import os
import re
import signal
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.request
from contextlib import closing, contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")
HERE = Path(__file__).resolve().parent
AUTO_DIR = Path(os.environ.get("AUTO_DIR", HERE))
PROJECT = Path(os.environ.get("AUTO_PROJECT", HERE.parents[1]))
HARNESS = Path(os.environ.get("AUTO_HARNESS", PROJECT / "Terminal_2.0_Harbor_Harness"))
REGISTRY = Path(os.environ.get("AUTO_REGISTRY", Path.home() / ".local/state/oc-bridge/tui"))
SECRET = Path(os.environ.get("AUTO_SECRET", Path.home() / ".config/oc-bridge/secret"))
DB_PATH = Path(os.environ.get("AUTO_DB", Path.home() / ".local/share/opencode/opencode.db"))
BOARD = Path(os.environ.get("AUTO_BOARD", PROJECT / "master_chat_tasks/board.json"))
NET_URL = os.environ.get("AUTO_NET_URL", "https://api.anthropic.com")

MASTER_SESSION = "ses_ea5ff5f97ffe6WB1VzP4StPOw6"
MODEL = {"providerID": "anthropic", "modelID": "claude-opus-5-5"}
VARIANT = "high"
MAX_BUSY_WORKERS = 5  # Ayush 27 Oct 22:20: 5 workers overnight
MAX_BUILDS = 2
MAX_HARNESS = 2
POLL_S = int(os.environ.get("AUTO_POLL_S", "60"))
IDLE_POLLS = 2            # a session must be idle this many polls in a row
LONG_BUSY_H = 6
STALL_MIN = 20            # plan v2 E2 / R5-05: every busy worker without activity this long -> STALL
MASTER_HOLD_POLLS = 2     # R5-04: master in retry/busy this many polls with events queued -> REPORT + notice
HEALTH_TIMEOUT_S = 15     # R5-07: one slow answer is not an outage
WORKER_DOWN_POLLS = 2     # R5-07: failed health checks in a row before "not answering"
NUDGE_MIN = 45            # idle check when nothing runs
MAX_NUDGES = 3
WIND_DOWN_MAX_H = 2
GAP_MIN = 10              # watcher silence that counts as a gap
STALE_MIN = 10            # a session untouched this long is not "busy" any more
NET_NOTE_MIN = 5
MAX_RETRIES = 4
RETRY_DEFAULT_MIN = 30
HARNESS_RESUME_DEFAULT_MIN = 60
HARNESS_RESUME_MAX = 3
RESUME_PAD_MIN = 5        # plan v2 E1: harness resume = parsed reset + 5 min
MAX_BUSY_AT_LAUNCH = 2    # ANS Q16 a: a paid run starts only with <= 2 busy workers
MAX_BUSY_WITH_RUN = 3     # ANS Q16 a: at most 3 busy workers while a paid run is RUNNING
LIMIT_CLEAR_POLLS = 2     # clean polls in a row before LIMIT CLEARED
LIMIT_PAUSE_PREFIX = "auto.py LIMIT"   # MQ pause reason set by the watcher (no LIMIT_RE words)
HOLD_FILE = "auto_hold.json"           # in HARNESS/.master-queue; MQ starts nothing while it holds
MASTER_KEY = "@master"

LIMIT_RE = re.compile(r"usage limit|extra usage|rate.?limit|429|overloaded|exhausted|quota|credit balance", re.I)
NETWORK_RE = re.compile(r"Cannot connect to API|Unable to connect|ECONN|ENOTFOUND|fetch failed|network|"
                        r"timed? ?out|socket", re.I)
RESET_AT_RE = re.compile(r"resets?\s+(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*([ap]m)?", re.I)
RESET_IN_RE = re.compile(r"(?:try again|reset) in\s+(\d+)\s*(seconds?|secs?|s|minutes?|mins?|hours?|hrs?|h|m)\b", re.I)
AUTH_RE = re.compile(r"^AUTH\b|(?:EXHAUSTED|BADKEY|AUTH) http 40[13]\b|\b401 Unauthorized\b", re.I)
EXHAUSTED_LINE_RE = re.compile(r"[^\n]*accounts exhausted[^\n]*", re.I)
DOOM_RE = re.compile(r"prevents you from using this specific tool call|doom.?loop", re.I)
DOOM_CONTINUE = ("continue: the same poll ran 3 times; add a rising counter or sleep N to each poll, "
                 "do not relaunch")
OUT_RE = re.compile(r"^\s*[-*]?\s*OUT\b[^`\n]{0,30}`([^`]+)`", re.M)
UNDELIVERED_HEADER = "## Watcher events not delivered"
PLAN_AT_RE = re.compile(r"^\s*[-*]?\s*at\s+(\d{1,2}:\d{2})\s*[:\-\u2013]\s*(.+)$", re.I)
RETRY_KINDS = ("limit", "network")

# Workers may do anything inside the project except publish, commit, queue the
# harness, or drive auto/night mode; outside the project only temp dirs.
WORKER_PERMISSION = {
    "edit": "allow",
    "read": "allow",
    "webfetch": "allow",
    "bash": {
        "*": "allow",
        "git push*": "deny",
        "git commit*": "deny",
        "gh *": "deny",
        "sudo *": "deny",
        "*master_queue.py*": "deny",
        "*harbor run*": "deny",
        # Ayush decision 9 (27 Oct): QC Step 10 oracle/nop runs are allowed;
        # opencode applies the last matching rule, so these must follow the deny.
        "*harbor run*--agent oracle*": "allow",
        "*harbor run*--agent nop*": "allow",
        "*night.py*": "deny",
        "*auto.py*": "deny",
    },
    "external_directory": {
        "*": "deny",
        "/tmp/**": "allow",
        "/private/tmp/**": "allow",
        "/var/folders/**": "allow",
        "/private/var/folders/**": "allow",
    },
    "doom_loop": "deny",
    "question": "deny",
}

REPORT_TEMPLATE = """# AUTO report ({label}: {started} -> {until})

## In short

## Needs Ayush

## Results

## Decisions and overrides

## Interrupted or unfinished

## Still running at stop

## Proposed changes (not applied)
"""
INTERRUPTED_HEADER = "## Interrupted or unfinished"
FINISHED_MSG = "last run finished normally; use start"


class AutoError(Exception):
    pass


class RunDir:
    """Paths of one run folder."""

    def __init__(self, d: Path) -> None:
        self.dir = d
        self.state = d / "state.json"
        self.log = d / "events.jsonl"
        self.stop = d / "AUTO_STOP"
        self.lock = d / "state.lock"
        self.logs = d / "logs"
        self.report = d / "REPORT.md"
        self.plan = d / "PLAN.md"


RUN: RunDir | None = None


def cur() -> RunDir:
    if RUN is None:
        raise AutoError("no run selected")
    return RUN


def use_run(d: Path) -> RunDir:
    global RUN
    RUN = RunDir(d)
    return RUN


def latest_run() -> RunDir:
    f = AUTO_DIR / "LATEST"
    if not f.is_file():
        raise AutoError("no auto run yet (auto.py start --until HH:MM)")
    return use_run(Path(f.read_text().strip()))


# ---------------------------------------------------------------- helpers
def now() -> datetime:
    return datetime.now(IST)


def ts() -> str:
    return now().isoformat(timespec="seconds")


def hm(iso: str | None) -> str:
    return datetime.fromisoformat(iso).strftime("%H:%M") if iso else "?"


def log(event: str, **data: object) -> None:
    r = cur()
    r.dir.mkdir(parents=True, exist_ok=True)
    with r.log.open("a") as f:
        f.write(json.dumps({"ist": ts(), "event": event, **data}) + "\n")


@contextmanager
def locked():
    """Serialise every read-modify-write of state.json (watcher and commands)."""
    r = cur()
    r.dir.mkdir(parents=True, exist_ok=True)
    with r.lock.open("w") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def load_state() -> dict:
    r = cur()
    return json.loads(r.state.read_text()) if r.state.exists() else {}


def save_state(st: dict) -> None:
    r = cur()
    tmp = r.state.with_suffix(".tmp")
    tmp.write_text(json.dumps(st, indent=2) + "\n")
    tmp.replace(r.state)


def insert_report_line(text: str, line: str, header: str = INTERRUPTED_HEADER) -> str:
    """Add `line` at the end of the `header` section (before the next "## ")."""
    lines = text.split("\n")
    try:
        start = next(i for i, l in enumerate(lines) if l.strip() == header)
    except StopIteration:
        return text.rstrip("\n") + "\n" + line + "\n"
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    pos = end
    while pos > start + 1 and not lines[pos - 1].strip():
        pos -= 1
    lines.insert(pos, line)
    if pos == start + 1:
        lines.insert(pos, "")
    return "\n".join(lines)


def report_line(text: str) -> None:
    r = cur()
    line = f"- WATCHER {now():%H:%M}: {text}"
    old = r.report.read_text() if r.report.exists() else ""
    r.report.write_text(insert_report_line(old, line))


def report_undelivered(events: list[str], since: str) -> None:
    """List queued events (first line each) under "Watcher events not delivered" in REPORT.md."""
    r = cur()
    text = r.report.read_text() if r.report.exists() else ""
    if UNDELIVERED_HEADER not in text.split("\n"):
        text = text.rstrip("\n") + f"\n\n{UNDELIVERED_HEADER}\n"
    for e in events:
        first = (e.strip().splitlines() or [""])[0][:200]
        text = insert_report_line(text, f"- {now():%H:%M} (held since {hm(since)}): {first}", UNDELIVERED_HEADER)
    r.report.write_text(text)


def secret() -> str:
    if not SECRET.is_file():
        raise AutoError(f"no secret at {SECRET}; start the master chat with `oc master -s {MASTER_SESSION}`")
    return SECRET.read_text().strip()


def http(url: str, method: str = "GET", body: dict | None = None, timeout: float = 15):
    req = urllib.request.Request(url, method=method)
    token = base64.b64encode(f"opencode:{secret()}".encode()).decode()
    req.add_header("Authorization", f"Basic {token}")
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, data=data, timeout=timeout) as r:
        raw = r.read()
    return json.loads(raw) if raw.strip() else None


def healthy(url: str) -> bool:
    try:
        return bool((http(url + "/global/health", timeout=HEALTH_TIMEOUT_S) or {}).get("healthy"))
    except (urllib.error.URLError, OSError, ValueError):
        return False


def net_up() -> bool:
    """Any HTTP answer from the API host (even 4xx) means the network is up."""
    try:
        urllib.request.urlopen(NET_URL, timeout=8).close()
        return True
    except urllib.error.HTTPError:
        return True
    except (urllib.error.URLError, OSError):
        return False


def master_url(name: str) -> str:
    f = REGISTRY / f"{name}.json"
    if not f.is_file():
        raise AutoError(f"master chat not registered ({f}); restart it with `oc {name} -s {MASTER_SESSION}`")
    url = json.loads(f.read_text())["url"]
    if not healthy(url):
        raise AutoError(f"master chat port {url} not answering; restart it with `oc {name} -s {MASTER_SESSION}`")
    return url


def session_status(url: str) -> dict:
    return http(url + "/session/status") or {}


def busy_ids(url: str, status: dict | None = None, include_retry: bool = False) -> set[str]:
    """Sessions doing work. A session in provider `retry` is waiting, not busy (see retry_ids);
    include_retry=True also returns retry sessions (callers that must not prompt them)."""
    st = session_status(url) if status is None else status
    skip = ("idle",) if include_retry else ("idle", "retry")
    return {sid for sid, s in st.items() if s.get("type") not in skip}


def retry_ids(url: str, status: dict | None = None) -> dict[str, dict]:
    """Sessions in provider retry: {sid: {"type": "retry", "attempt", "message", "next"}}."""
    st = session_status(url) if status is None else status
    return {sid: s for sid, s in st.items() if s.get("type") == "retry"}



def last_message(url: str, sid: str) -> dict | None:
    msgs = http(f"{url}/session/{sid}/message?limit=1") or []
    return msgs[-1] if msgs else None


def tail_text(text: str, tail: int = 1500) -> str:
    text = text.strip()
    return text if len(text) <= tail else "..." + text[-tail:]


def message_text(msg: dict | None, tail: int = 1500) -> str:
    if not msg:
        return ""
    return tail_text("\n".join(p.get("text", "") for p in msg.get("parts", []) if p.get("type") == "text"), tail)


def prompt(url: str, sid: str, text: str, agent: str | None = None, model: dict | None = None,
           variant: str | None = None) -> None:
    body = {"model": model or MODEL, "variant": variant or VARIANT, "parts": [{"type": "text", "text": text}]}
    if agent:
        body["agent"] = agent
    http(f"{url}/session/{sid}/prompt_async", "POST", body)


def master_identity(url: str, sid: str) -> tuple[str | None, dict | None, str | None]:
    """Agent/model/variant of the master's last user message, so the watcher speaks as Ayush would."""
    msgs = http(f"{url}/session/{sid}/message?limit=20") or []
    for m in reversed(msgs):
        info = m.get("info", {})
        if info.get("role") == "user":
            model = info.get("model") or {}
            return (info.get("agent"),
                    {"providerID": model["providerID"], "modelID": model["modelID"]} if model.get("modelID") else None,
                    model.get("variant"))
    return None, None, None


def pid_alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def proc_is(pid: int | None, needle: str) -> bool:
    """True when `pid` is alive and its command line contains `needle` (guards against pid reuse)."""
    if not pid_alive(pid):
        return False
    out = subprocess.run(["ps", "-p", str(pid), "-o", "command="], capture_output=True, text=True)
    return needle in out.stdout


def terminate(pid: int | None, needle: str) -> None:
    """SIGTERM a process this script started; refuses anything whose command line does not match."""
    if not proc_is(pid, needle):
        return
    try:
        os.killpg(pid, signal.SIGTERM)
    except OSError:
        os.kill(pid, signal.SIGTERM)


def require_not_worker() -> None:
    if os.environ.get("OC_AUTO_WORKER"):
        raise AutoError("auto workers may not drive auto mode")


def require_running(st: dict) -> None:
    if not st.get("worker_url") or not healthy(st["worker_url"]):
        raise AutoError("worker server is not running (auto.py start --until HH:MM, or auto.py resume)")


def harness_state_file() -> Path:
    return HARNESS / ".master-queue/state.json"


def harness_runs() -> dict:
    f = harness_state_file()
    if not f.is_file():
        return {"runs": [], "queue": [], "paused": False}
    return json.loads(f.read_text())


def worker_env() -> dict:
    env = dict(os.environ)
    env["OPENCODE_SERVER_PASSWORD"] = secret()
    env["OPENCODE_PERMISSION"] = json.dumps(WORKER_PERMISSION)
    env["OC_AUTO_WORKER"] = "1"
    if not env.get("ANTHROPIC_CLI_VERSION"):
        # opus-5-5 is gated on the advertised Claude Code version; ~/.zshrc computes it.
        out = subprocess.run(["zsh", "-ic", "print -r -- $ANTHROPIC_CLI_VERSION"], capture_output=True, text=True)
        ver = out.stdout.strip().splitlines()[-1] if out.stdout.strip() else ""
        if ver:
            env["ANTHROPIC_CLI_VERSION"] = ver
    return env


def next_occurrence(hhmm: str, after: datetime) -> datetime:
    """The next wall-clock HH:MM strictly after `after`."""
    try:
        h, m = (int(x) for x in hhmm.split(":"))
        t = after.replace(hour=h, minute=m, second=0, microsecond=0)
    except ValueError as e:
        raise AutoError(f"bad time {hhmm!r} (want HH:MM)") from e
    return t if t > after else t + timedelta(days=1)


def parse_until(hhmm: str) -> datetime:
    return next_occurrence(hhmm, now())


def parse_plan(text: str, start: datetime) -> list[dict]:
    """Timed plan lines ("- at 03:00: do X") -> schedule entries, next occurrence after `start`."""
    out = []
    for line in text.splitlines():
        m = PLAN_AT_RE.match(line)
        if not m:
            continue
        try:
            at = next_occurrence(m.group(1), start)
        except AutoError:
            continue
        out.append({"at": at.isoformat(timespec="minutes"), "text": m.group(2).strip(), "sent": False})
    return out


def limits(st: dict) -> tuple[int, int]:
    """(max busy workers, max harness runs) now: the ramp values once its time has passed."""
    ramp = st.get("ramp")
    if ramp and now() >= datetime.fromisoformat(ramp["at"]):
        return ramp["workers"], ramp["harness"]
    return st.get("max_workers", MAX_BUSY_WORKERS), st.get("max_harness", 1)


def check_limits(workers: int, harness: int) -> None:
    if not (1 <= workers <= MAX_BUSY_WORKERS and 1 <= harness <= MAX_HARNESS):
        raise AutoError(f"limits must be workers 1-{MAX_BUSY_WORKERS}, harness 1-{MAX_HARNESS}")


# ---------------------------------------------------------------- errors and retries
def classify(err: dict | None) -> str:
    """limit | network | aborted | doom | other, from the error name and message."""
    err = err or {}
    if err.get("name") == "MessageAbortedError":
        return "aborted"
    text = f"{err.get('name', '')} {err_message(err)}"
    if DOOM_RE.search(text):  # opencode doom_loop guard (kept on "deny", ANS Q19 a)
        return "doom"
    if LIMIT_RE.search(text):
        return "limit"
    if NETWORK_RE.search(text):
        return "network"
    return "other"


def err_message(err: dict | None) -> str:
    err = err or {}
    data = err.get("data") or {}
    return str(data.get("message") or err.get("message") or err.get("name") or "")


def reset_in_text(msg: str, base: datetime) -> datetime | None:
    """Reset time named in the text ('try again in 5 minutes', 'reset in 4698s', 'at 3pm'), else None."""
    m = RESET_IN_RE.search(msg)
    if m:
        n, unit = int(m.group(1)), m.group(2).lower()
        if unit.startswith("h"):
            return base + timedelta(hours=n)
        if unit.startswith("s"):
            return base + timedelta(seconds=n)
        return base + timedelta(minutes=n)
    m = RESET_AT_RE.search(msg)
    if m and (m.group(2) or m.group(3)):
        h, mi, ap = int(m.group(1)), int(m.group(2) or 0), (m.group(3) or "").lower()
        if ap:
            h = h % 12 + (12 if ap == "pm" else 0)
        if h < 24 and mi < 60:
            t = base.replace(hour=h, minute=mi, second=0, microsecond=0)
            return t if t > base else t + timedelta(days=1)
    return None


def parse_reset(msg: str, base: datetime, default_min: int = RETRY_DEFAULT_MIN) -> datetime:
    """When a limit/network pause should be retried: parsed reset time, else base + default_min."""
    return reset_in_text(msg, base) or base + timedelta(minutes=default_min)


def schedule_retry(st: dict, key: str, kind: str, msg: str, msg_id: str | None) -> str:
    """Record a pause. Returns paused (first), rescheduled, gave_up (first time) or gave_up_again."""
    prev = st["retries"].get(key)
    count = prev["count"] if prev else 0
    entry = {"kind": kind, "msg": msg_id, "count": count, "at": None, "gave_up": False, "text": msg[:200]}
    if count >= MAX_RETRIES:
        entry["gave_up"] = True
        st["retries"][key] = entry
        return "gave_up_again" if prev and prev.get("gave_up") else "gave_up"
    entry["at"] = parse_reset(msg, now()).isoformat(timespec="seconds")
    st["retries"][key] = entry
    return "paused" if prev is None else "rescheduled"


# ---------------------------------------------------------------- opencode.db (read-only)
@dataclass(frozen=True, slots=True)
class DbState:
    state: str                       # busy | done | error | interrupted | unknown
    msg_id: str | None = None
    tail: str = ""
    error: dict | None = None


def db_connect() -> sqlite3.Connection:
    return sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True, timeout=5)


def find_session(title: str) -> str | None:
    with closing(db_connect()) as c:
        row = c.execute("select id from session where parent_id is null and title=? "
                        "order by time_updated desc limit 1", (title,)).fetchone()
    return row[0] if row else None


def session_exists(sid: str) -> bool:
    with closing(db_connect()) as c:
        return c.execute("select 1 from session where id=?", (sid,)).fetchone() is not None


def db_state(sid: str, now_ms: int | None = None) -> DbState:
    now_ms = now_ms if now_ms is not None else int(time.time() * 1000)
    fresh_ms = STALE_MIN * 60 * 1000
    try:
        with closing(db_connect()) as c:
            row = c.execute("select id, time_created, data from message where session_id=? "
                            "order by time_created desc, id desc limit 1", (sid,)).fetchone()
            sess = c.execute("select time_updated from session where id=?", (sid,)).fetchone()
            if not row or not sess:
                return DbState("unknown")
            mid, created, raw = row
            data = json.loads(raw)
            parts = c.execute("select data from part where message_id=? order by time_created, id", (mid,)).fetchall()
    except sqlite3.Error:
        return DbState("unknown")
    text = tail_text("\n".join(p.get("text", "") for p in (json.loads(r[0]) for r in parts)
                               if p.get("type") == "text"))
    if data.get("role") == "user":
        return DbState("busy" if now_ms - created < fresh_ms else "interrupted", mid, text)
    err = data.get("error")
    if err:
        return DbState("error", mid, text, err)
    recent = now_ms - sess[0] < fresh_ms
    if not (data.get("time") or {}).get("completed") or data.get("finish") == "tool-calls":
        return DbState("busy" if recent else "interrupted", mid, text)
    return DbState("done", mid, text)


# ---------------------------------------------------------------- worker bookkeeping
def is_passive(w: dict) -> bool:
    """Adopted session nobody in this run has sent to: watched through the DB, not the worker server."""
    return bool(w.get("adopted")) and not w.get("owned")


def new_worker(session: str, prompt_path: str, build: bool = False, adopted: bool = False) -> dict:
    return {"session": session, "prompt": prompt_path, "spawned": ts(), "build": build, "sent": ts(),
            "busy_seen": False, "idle_polls": 0, "reported_msg": None, "long_warned": False,
            "adopted": adopted, "owned": not adopted}


def mark_sent(w: dict) -> None:
    w.update(sent=ts(), busy_seen=False, idle_polls=0, owned=True)


def load_board() -> list[dict]:
    if not BOARD.is_file():
        return []
    return json.loads(BOARD.read_text()).get("rows", [])


def adopt_one(st: dict, sha: str, session: str | None) -> bool:
    """Track an existing session under `sha`. False when no session can be found."""
    sid = session if session and session_exists(session) else (None if session else find_session(sha))
    if not sid:
        return False
    row = next((r for r in load_board() if r.get("sha") == sha), {})
    st["workers"][sha] = new_worker(sid, row.get("prompt", ""), adopted=True)
    log("adopt", sha=sha, session=sid)
    return True


def busy_workers(st: dict) -> list[str]:
    """SHAs whose session is working now (server status for owned, DB for passive)."""
    url = st.get("worker_url")
    server = busy_ids(url) if url and healthy(url) else set()
    return [sha for sha, w in st["workers"].items()
            if (db_state(w["session"]).state == "busy" if is_passive(w) else w["session"] in server)]


# ---------------------------------------------------------------- commands
def start_worker_server() -> tuple[str, subprocess.Popen, Path]:
    r = cur()
    r.logs.mkdir(parents=True, exist_ok=True)
    srv_log = r.logs / f"worker_server_{now():%Y%m%dT%H%M%S}.log"
    with srv_log.open("w") as out:
        srv = subprocess.Popen(["opencode", "serve", "--port", "0", "--hostname", "127.0.0.1"],
                               cwd=PROJECT, env=worker_env(), stdout=out, stderr=subprocess.STDOUT,
                               stdin=subprocess.DEVNULL, start_new_session=True)
    url = None
    for _ in range(60):
        time.sleep(1)
        for line in srv_log.read_text().splitlines():
            if "listening on http" in line:
                url = line.split("listening on ", 1)[1].strip()
        if url and healthy(url):
            return url, srv, srv_log
        if srv.poll() is not None:
            raise AutoError(f"worker server exited; see {srv_log}")
    srv.kill()
    raise AutoError(f"worker server did not start in 60 s; see {srv_log}")


def start_watcher_and_caffeinate(st: dict) -> None:
    r = cur()
    with (r.logs / "watcher.log").open("a") as out:
        w = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "watch", "--run", str(r.dir)],
                             env=dict(os.environ), stdout=out, stderr=subprocess.STDOUT,
                             stdin=subprocess.DEVNULL, start_new_session=True)
    with (r.logs / "caffeinate.log").open("a") as out:
        c = subprocess.Popen(["caffeinate", "-i", "-s", "-w", str(w.pid)], stdout=out, stderr=subprocess.STDOUT,
                             stdin=subprocess.DEVNULL, start_new_session=True)
    st.update(watcher_pid=w.pid, caffeinate_pid=c.pid)
    save_state(st)


def new_run_dir(label: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_.-]", "-", label) or "auto"
    base = AUTO_DIR / "runs" / f"{now():%Y%m%dT%H%M}_{safe}"
    d, n = base, 1
    while d.exists():
        n += 1
        d = base.with_name(f"{base.name}-{n}")
    d.mkdir(parents=True)
    return d


def start_event(plan_text: str, adopted: list[str], missing: list[str], until: datetime) -> str:
    parts = [f"AUTO MODE START (until {until:%H:%M} IST)"]
    parts.append("PLAN:\n" + plan_text.strip() if plan_text.strip() else "PLAN: (none given)")
    parts.append(f"ADOPTED running sessions: {', '.join(adopted) or '-'}"
                 + (f"\nNOT FOUND (no session titled with the sha): {', '.join(missing)}" if missing else ""))
    return "\n\n".join(parts)


def refuse_if_running() -> None:
    prev = AUTO_DIR / "LATEST"
    if prev.is_file():
        old = Path(prev.read_text().strip()) / "state.json"
        if old.is_file() and pid_alive(json.loads(old.read_text()).get("watcher_pid")):
            raise AutoError(f"auto mode already running (see {old.parent}); auto.py status")


def cmd_start(a) -> int:
    require_not_worker()
    if a.at:
        return schedule_start(a)
    if not getattr(a, "from_schedule", False):
        sch = load_schedule()
        if sch:
            raise AutoError(f"a scheduled start exists ({sch['at'][11:16]} IST); `auto.py cancel` first")
    refuse_if_running()
    murl = master_url(a.master)
    started, until = now(), parse_until(a.until)
    check_limits(a.workers, a.harness)
    ramp = None
    if a.ramp:
        r_at, r_w, r_h = a.ramp
        check_limits(int(r_w), int(r_h))
        ramp = {"at": parse_until(r_at).isoformat(timespec="minutes"), "workers": int(r_w), "harness": int(r_h)}
    plan_text = Path(a.plan).read_text() if a.plan else ""
    r = use_run(new_run_dir(a.label))
    with locked():
        r.logs.mkdir(parents=True, exist_ok=True)
        if a.plan:
            r.plan.write_text(plan_text)
        r.report.write_text(REPORT_TEMPLATE.format(label=a.label, started=f"{started:%Y-%m-%d %H:%M}",
                                                   until=f"{until:%Y-%m-%d %H:%M}"))
        url, srv, srv_log = start_worker_server()
        hs = harness_runs()
        st = {
            "started": ts(), "until": until.isoformat(timespec="minutes"), "label": a.label, "master": a.master,
            "master_url": murl, "master_session": a.session, "worker_url": url, "worker_pid": srv.pid,
            "worker_log": str(srv_log), "workers": {}, "builds": 0, "retries": {}, "harness_resume": {},
            "harness_seen": [f"{x['task']}#{x.get('attempt')}#{x.get('started_at')}" for x in hs.get("runs", [])
                             if x.get("status") in ("DONE", "FAILED")],
            "events": [], "stopping": False, "max_workers": a.workers, "max_harness": a.harness, "ramp": ramp,
            "schedule": parse_plan(plan_text, started), "last_poll": ts(),
        }
        adopted: list[str] = []
        missing: list[str] = []
        if not a.no_adopt:
            for row in load_board():
                if row.get("status") == "running" and row.get("sha"):
                    (adopted if adopt_one(st, row["sha"], None) else missing).append(row["sha"])
        st["events"].append(start_event(plan_text, adopted, missing, until))
        note = getattr(a, "schedule_note", None)
        if note:
            st["events"][-1] += "\n\n" + note
            report_line(note)
        save_state(st)
        (AUTO_DIR / "LATEST").write_text(str(r.dir) + "\n")
        start_watcher_and_caffeinate(st)
        log("start", until=st["until"], worker_url=url, worker_pid=srv.pid, watcher_pid=st["watcher_pid"],
            caffeinate_pid=st["caffeinate_pid"], adopted=adopted, not_found=missing, schedule=st["schedule"])
    print(f"AUTO MODE ON until {until:%H:%M} IST\n  run folder {r.dir}\n  worker server {url} (pid {srv.pid})"
          f"\n  watcher pid {st['watcher_pid']}  caffeinate pid {st['caffeinate_pid']}"
          f"\n  limits: {a.workers} workers, {a.harness} harness"
          + (f"; from {ramp['at'][11:16]}: {ramp['workers']} workers, {ramp['harness']} harness" if ramp else "")
          + f"\n  adopted: {adopted or '-'}  not found: {missing or '-'}"
          f"\n  plan schedule: {len(st['schedule'])} timed line(s)"
          f"\n  watch a worker: opencode attach {url} -s <session id>   (password: {SECRET})"
          f"\n  stop: auto.py stop  or  touch {r.stop}")
    return 0


# ---------------------------------------------------------------- scheduled start (start --at HH:MM)
# A small waiter process holds the schedule (AUTO_DIR/SCHEDULED.json); caffeinate keeps the Mac
# awake while it waits. At the start time it runs the normal `start`, so adoption happens then.
SCHED_POLL_S = int(os.environ.get("AUTO_SCHED_POLL_S", "30"))
SCHED_RETRY_S = int(os.environ.get("AUTO_SCHED_RETRY_S", "60"))
SCHED_RETRY_N = int(os.environ.get("AUTO_SCHED_RETRY_N", "15"))   # Ayush 27 Oct: retry 15 min, then give up
SCHED_LATE_MIN = 2


def sched_file() -> Path:
    return AUTO_DIR / "SCHEDULED.json"


def sched_log(text: str) -> None:
    with (AUTO_DIR / "SCHEDULED.log").open("a") as f:
        f.write(f"{ts()} {text}\n")


def load_schedule() -> dict:
    f = sched_file()
    return json.loads(f.read_text()) if f.is_file() else {}


def start_argv(a) -> list[str]:
    """The `start` arguments the waiter replays at the start time (no --at; plan path absolute)."""
    argv = ["start", "--until", a.until, "--label", a.label, "--master", a.master, "--session", a.session,
            "--workers", str(a.workers), "--harness", str(a.harness)]
    if a.plan:
        argv += ["--plan", str(Path(a.plan).resolve())]
    if a.ramp:
        argv += ["--ramp", *a.ramp]
    if a.no_adopt:
        argv.append("--no-adopt")
    return argv


def schedule_start(a) -> int:
    """Check everything now, then leave a waiter that runs the normal start at `a.at`."""
    old = load_schedule()
    if old:
        alive = proc_is(old.get("waiter_pid"), "auto.py")
        raise AutoError(f"a start is already scheduled for {old['at'][11:16]} IST"
                        + ("" if alive else " (its waiter is gone)") + "; `auto.py cancel` first")
    refuse_if_running()
    master_url(a.master)
    check_limits(a.workers, a.harness)
    if a.ramp:
        check_limits(int(a.ramp[1]), int(a.ramp[2]))
        next_occurrence(a.ramp[0], now())
    if a.plan:
        Path(a.plan).read_text()
    at = next_occurrence(a.at, now())
    until = next_occurrence(a.until, at)
    sid = f"{now():%Y%m%dT%H%M%S}-{os.getpid()}"
    sch = {"id": sid, "at": at.isoformat(timespec="minutes"), "until": until.isoformat(timespec="minutes"),
           "set_at": ts(), "argv": start_argv(a), "waiter_pid": None, "caffeinate_pid": None}
    AUTO_DIR.mkdir(parents=True, exist_ok=True)
    sched_file().write_text(json.dumps(sch, indent=1))
    with (AUTO_DIR / "SCHEDULED.out").open("a") as out:
        w = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "scheduled", "--id", sid],
                             env=dict(os.environ), stdout=out, stderr=subprocess.STDOUT,
                             stdin=subprocess.DEVNULL, start_new_session=True)
        c = subprocess.Popen(["caffeinate", "-i", "-s", "-w", str(w.pid)], stdout=out, stderr=subprocess.STDOUT,
                             stdin=subprocess.DEVNULL, start_new_session=True)
    sch.update(waiter_pid=w.pid, caffeinate_pid=c.pid)
    sched_file().write_text(json.dumps(sch, indent=1))
    sched_log(f"scheduled {at:%Y-%m-%d %H:%M} -> {until:%Y-%m-%d %H:%M} (waiter {w.pid}): {' '.join(sch['argv'])}")
    print(f"AUTO MODE SCHEDULED: starts {at:%a %d %b %H:%M} IST, runs until {until:%a %d %b %H:%M} IST"
          f"\n  waiter pid {w.pid}  caffeinate pid {c.pid}  (keep the lid open and the charger in)"
          f"\n  checked now: master chat reachable, limits, plan file, no run active"
          f"\n  adopts board rows that are running at {at:%H:%M}; cancel: auto.py cancel")
    return 0


def sched_still_mine(sid: str) -> bool:
    return load_schedule().get("id") == sid


def cmd_scheduled(a) -> int:
    """The waiter: sleep to the start time, then run the normal start (retry 15 min if it fails)."""
    sch = load_schedule()
    if sch.get("id") != a.id:
        return 0
    at, until = datetime.fromisoformat(sch["at"]), datetime.fromisoformat(sch["until"])
    while now() < at:
        if not sched_still_mine(a.id):
            sched_log("waiter: schedule cancelled")
            return 0
        time.sleep(max(1, min(SCHED_POLL_S, (at - now()).total_seconds())))
    last = ""
    for n in range(1, SCHED_RETRY_N + 1):
        if not sched_still_mine(a.id):
            sched_log("waiter: schedule cancelled")
            return 0
        t = now()
        if t >= until:
            sched_log(f"SKIPPED: woke at {t:%H:%M}, after the end time {until:%H:%M}; nothing started")
            sched_file().unlink(missing_ok=True)
            return 0
        sa = build_parser().parse_args(sch["argv"])
        sa.from_schedule = True
        late = (t - at).total_seconds() / 60
        if late >= SCHED_LATE_MIN:
            sa.schedule_note = (f"SCHEDULED START was {at:%H:%M} IST; it began late at {t:%H:%M} "
                                f"(Mac asleep or master chat unreachable" + (f"; try {n}" if n > 1 else "") + ")")
        try:
            cmd_start(sa)
            sched_log(f"STARTED at {t:%H:%M} (scheduled {at:%H:%M}, try {n})")
            sched_file().unlink(missing_ok=True)
            return 0
        except Exception as e:  # noqa: BLE001 - the waiter must log every failure, never die silently
            last = f"{type(e).__name__}: {e}"
            sched_log(f"start try {n}/{SCHED_RETRY_N} failed: {last}")
            if not (isinstance(e, AutoError) and str(e).startswith("master chat")):
                sched_log("FAILED: not a master-chat reachability error, so no retry (see SCHEDULED.out)")
                sched_file().unlink(missing_ok=True)
                return 1
            if n < SCHED_RETRY_N:
                time.sleep(SCHED_RETRY_S)
    sched_log(f"GAVE UP after {SCHED_RETRY_N} tries; last error: {last}")
    sched_file().unlink(missing_ok=True)
    return 1


def schedule_status() -> str:
    sch = load_schedule()
    if not sch:
        f = AUTO_DIR / "SCHEDULED.log"
        last = f.read_text().strip().splitlines()[-1] if f.is_file() and f.read_text().strip() else ""
        return f"schedule: none" + (f"  (last: {last})" if last else "")
    alive = proc_is(sch.get("waiter_pid"), "auto.py")
    if not alive:
        return (f"schedule: STALE start for {sch['at'][11:16]} IST (until {sch['until'][11:16]}); its waiter is "
                "gone (power cut or restart?). Ask Ayush: `auto.py cancel`, then set it again or start now")
    return (f"schedule: start at {sch['at'].replace('T', ' ')} IST until {sch['until'].replace('T', ' ')} IST, "
            f"waiter pid {sch['waiter_pid']} alive, caffeinate alive={proc_is(sch.get('caffeinate_pid'), 'caffeinate')}")


def cmd_cancel(a) -> int:
    require_not_worker()
    sch = load_schedule()
    if not sch:
        print("nothing scheduled")
        return 0
    sched_file().unlink(missing_ok=True)
    terminate(sch.get("waiter_pid"), "auto.py")
    terminate(sch.get("caffeinate_pid"), "caffeinate")
    sched_log(f"CANCELLED (was {sch['at'][11:16]})")
    print(f"cancelled the start scheduled for {sch['at'][11:16]} IST")
    return 0


def resume_refusal(st: dict) -> str | None:
    """Why `resume` must not run, or None."""
    if not st:
        return "no previous run to resume (auto.py start --until HH:MM)"
    if pid_alive(st.get("watcher_pid")):
        return f"watcher is still running (pid {st['watcher_pid']}); nothing to resume (auto.py status)"
    if st.get("ended") and st.get("final_sent"):
        return FINISHED_MSG
    return None


def resume_worker(st: dict, sha: str, fresh_server: bool, server_busy: set[str]) -> str:
    """Bring one worker back after the gap. Returns a short action note."""
    w = st["workers"][sha]
    d = db_state(w["session"])
    if d.state in ("busy", "interrupted"):
        if not fresh_server and w["session"] in server_busy:
            return f"{sha}: still working on the live server"
        prompt(st["worker_url"], w["session"], "continue")
        mark_sent(w)
        w["resumed_at"] = ts()
        st["retries"].pop(sha, None)
        return f"{sha}: was {d.state}, sent 'continue'"
    if d.state == "error":
        handle_result(st, st["events"], sha, d)
        return f"{sha}: ended in error ({classify(d.error)}), handled"
    if d.state == "done":
        w["idle_polls"] = IDLE_POLLS
        return f"{sha}: finished (will be reported)"
    return f"{sha}: state unknown, left alone"


def harness_resume_note() -> str:
    runs = [r["task"] for r in harness_runs().get("runs", []) if r.get("status") == "RUNNING"]
    py = HARNESS / ".venv/bin/python"
    status = (sh([str(py), "scripts/master_queue.py", "status"], cwd=HARNESS).stdout.strip()
              if py.exists() else "(harness python not found; status skipped)")
    return f"harness runs RUNNING: {runs or '-'}\n{status}"


def cmd_resume(a) -> int:
    require_not_worker()
    r = latest_run()
    st = load_state()
    refusal = resume_refusal(st)
    if refusal == FINISHED_MSG:
        print(refusal)
        return 0
    if refusal:
        raise AutoError(refusal)
    st["master_url"] = master_url(st["master"])
    gap_from = st.get("last_poll") or st["started"]
    gap = f"{hm(gap_from)}-{now():%H:%M}"
    actions: list[str] = []
    expired = now() >= datetime.fromisoformat(st["until"])
    if expired:
        st.update(worker_down_reported=True, stopping=True, stop_at=ts(), final_sent=True)
        r.stop.write_text(st["stop_at"] + "\n")
        actions.append("until already passed; workers not restarted")
        st["events"].append(f"FINAL: finish {r.report} now (every decision, result, override, unfinished item, "
                            "proposed change, and every question for Ayush), then stop. Issue nothing.")
    else:
        fresh = not (st.get("worker_url") and healthy(st["worker_url"]))
        if fresh:
            terminate(st.get("worker_pid"), "opencode")
            url, srv, srv_log = start_worker_server()
            st.update(worker_url=url, worker_pid=srv.pid, worker_log=str(srv_log), worker_down_reported=False,
                      worker_fail=0, worker_fail_since=None)
            actions.append(f"worker server restarted at {url}")
        busy = busy_ids(st["worker_url"], include_retry=True)  # retry sessions get no "continue" either
        for sha in st["workers"]:
            actions.append(resume_worker(st, sha, fresh, busy))
        actions.append(harness_resume_note())
    st.pop("ended", None)
    st["last_poll"] = ts()
    for act in actions:
        report_line("resumed: " + act.splitlines()[0])
    report_line(f"gap {gap} (watcher not running); resumed by `auto.py resume`")
    st["events"].append(f"AUTO RESUMED after gap {gap}: " + "; ".join(actions))
    save_state(st)
    start_watcher_and_caffeinate(st)
    log("resume", gap=gap, actions=actions)
    print(f"AUTO RESUMED (gap {gap})\n  " + "\n  ".join(actions)
          + f"\n  watcher pid {st['watcher_pid']}  caffeinate pid {st['caffeinate_pid']}")
    return 0


def cmd_adopt(a) -> int:
    require_not_worker()
    latest_run()
    st = load_state()
    if not st:
        raise AutoError("auto mode never started")
    if a.sha in st["workers"]:
        raise AutoError(f"{a.sha} is already tracked ({st['workers'][a.sha]['session']})")
    if not adopt_one(st, a.sha, a.session):
        raise AutoError(f"no session found for {a.sha}" + (f" with id {a.session}" if a.session else " (by title)"))
    save_state(st)
    print(f"adopted {a.sha} -> {st['workers'][a.sha]['session']} (not owned until you send to it)")
    return 0


def cmd_stop(a) -> int:
    r = latest_run()
    r.stop.write_text(ts() + "\n")
    log("stop_requested")
    print(f"{r.stop.name} written: nothing new starts; running workers finish their current step.")
    return 0


def cmd_spawn(a) -> int:
    require_not_worker()
    latest_run()
    st = load_state()
    require_running(st)
    if cur().stop.exists() or st.get("stopping"):
        raise AutoError("auto mode is stopping; nothing new starts")
    refuse_if_limit(st, "spawn")
    if a.sha in st["workers"]:
        raise AutoError(f"{a.sha} already has a worker ({st['workers'][a.sha]['session']}); use send")
    text = Path(a.prompt).read_text()
    if f"`{a.sha}`" not in text and a.sha not in text:
        raise AutoError(f"prompt file does not mention board id {a.sha}; issue it with tools/issue.py first")
    url = st["worker_url"]
    busy = busy_workers(st)
    max_w = limits(st)[0]
    if len(busy) >= max_w:
        raise AutoError(f"{len(busy)} workers busy (limit {max_w} now); wait for one to finish")
    paid = paid_running()
    if paid and len(busy) >= MAX_BUSY_WITH_RUN:
        raise AutoError(f"held: {len(busy)} workers busy while paid run {', '.join(paid)} is RUNNING "
                        f"(limit {MAX_BUSY_WITH_RUN} during a paid run); wait for a worker or the run to finish")
    if a.build and st.get("builds", 0) >= MAX_BUILDS:
        raise AutoError(f"{MAX_BUILDS} new builds already started in this run (limit)")
    sess = http(url + "/session", "POST", {"title": a.sha})
    prompt(url, sess["id"], text)
    st = load_state()
    st["workers"][a.sha] = new_worker(sess["id"], str(Path(a.prompt).resolve()), build=bool(a.build))
    st["builds"] = st.get("builds", 0) + (1 if a.build else 0)
    save_state(st)
    log("spawn", sha=a.sha, session=sess["id"], prompt=a.prompt, build=bool(a.build))
    print(f"spawned {a.sha} -> {sess['id']}\n  watch: opencode attach {url} -s {sess['id']}")
    return 0


def cmd_send(a) -> int:
    require_not_worker()
    latest_run()
    st = load_state()
    require_running(st)
    w = st["workers"].get(a.sha)
    if not w:
        raise AutoError(f"no auto worker for {a.sha}")
    url = st["worker_url"]
    if is_passive(w):
        state = db_state(w["session"]).state
        if state not in ("done", "error", "interrupted"):
            raise AutoError(f"adopted {a.sha} is {state}; wait for its done event")
    elif w["session"] in busy_ids(url, include_retry=True):
        raise AutoError(f"{a.sha} is busy or in provider retry; wait for its done event")
    text = Path(a.text[1:]).read_text() if a.text.startswith("@") else a.text
    prompt(url, w["session"], text)
    st = load_state()
    mark_sent(st["workers"][a.sha])
    st["retries"].pop(a.sha, None)
    save_state(st)
    log("send", sha=a.sha, text=text[:300])
    print(f"sent to {a.sha} ({w['session']})")
    return 0


def sh(cmd: list[str], cwd: Path | None = None, timeout: int = 120) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)


def cmd_harness(a) -> int:
    require_not_worker()
    latest_run()
    st = load_state()
    if cur().stop.exists() or st.get("stopping"):
        raise AutoError("auto mode is stopping; nothing new starts")
    refuse_if_limit(st, "harness")
    bundle = Path(a.bundle).resolve()
    if not (bundle / "task.toml").is_file():
        raise AutoError(f"{bundle} has no task.toml")
    busy = busy_workers(st)
    if len(busy) > MAX_BUSY_AT_LAUNCH:
        raise AutoError(f"{len(busy)} workers busy; a paid run starts only with <= {MAX_BUSY_AT_LAUNCH} busy "
                        f"(ANS Q16 a); wait for workers to finish")
    hs = harness_runs()
    active = [r["task"] for r in hs.get("runs", []) if r.get("status") == "RUNNING"] + \
             [q if isinstance(q, str) else q.get("task", "?") for q in hs.get("queue", [])]
    max_h = limits(st)[1]
    if len(active) >= max_h:
        raise AutoError(f"harness busy ({', '.join(active)}); limit {max_h} run(s) at a time now")
    if bundle.name in active:
        raise AutoError(f"{bundle.name} is already running or queued on the harness")
    if hs.get("paused"):
        raise AutoError(f"harness paused: {hs.get('pause_reason')}")
    checks = {
        "docker": sh(["docker", "ps", "-q"]).returncode == 0,
        "pypi": sh(["curl", "-sS", "-o", "/dev/null", "-m", "15", "-w", "%{http_code}",
                    "https://pypi.org/simple/pip/"]).stdout.strip() == "200",
    }
    harbor = [l for l in sh(["ps", "-axo", "pid,command"]).stdout.splitlines()
              if "harbor" in l and "run" in l and "grep" not in l]
    print(f"pre-checks: {checks}  harbor processes: {len(harbor)}\n  {sh(['uptime']).stdout.strip()}")
    if not all(checks.values()):
        raise AutoError(f"pre-check failed: {checks}")
    staged = HARNESS / "Tasks_INPUT" / bundle.name
    before = sh(["diff", "-rq", str(bundle), str(staged)]).stdout.strip() if staged.exists() else "(not staged yet)"
    print("diff before:", before or "(same)")
    py = HARNESS / ".venv/bin/python"
    add = sh([str(py), "scripts/master_queue.py", "add", str(bundle)], cwd=HARNESS, timeout=300)
    print(add.stdout.strip(), add.stderr.strip())
    if add.returncode != 0:
        raise AutoError(f"master_queue add failed (exit {add.returncode})")
    after = sh(["diff", "-rq", str(bundle), str(staged)]).stdout.strip()
    if after:
        raise AutoError(f"staged copy differs from bundle after add:\n{after}")
    print(sh([str(py), "scripts/master_queue.py", "status"], cwd=HARNESS).stdout.strip())
    log("harness_add", bundle=str(bundle))
    return 0


def cmd_limits(a) -> int:
    require_not_worker()
    latest_run()
    check_limits(a.workers, a.harness)
    st = load_state()
    if not st:
        raise AutoError("auto mode never started")
    st.update(max_workers=a.workers, max_harness=a.harness, ramp=None)
    save_state(st)
    log("limits", workers=a.workers, harness=a.harness)
    print(f"limits now: {a.workers} workers, {a.harness} harness (ramp cleared)")
    return 0


def cmd_status(a) -> int:
    r = latest_run()
    st = load_state()
    if not st:
        print("auto mode never started")
        return 0
    up = bool(st.get("worker_url")) and healthy(st["worker_url"])
    print(f"run {r.dir}\nstarted {st['started']} until {st['until']}  stop file: {r.stop.exists()}  "
          f"stopping: {st.get('stopping')}")
    print(f"watcher pid {st.get('watcher_pid')} alive={pid_alive(st.get('watcher_pid'))}  "
          f"caffeinate pid {st.get('caffeinate_pid')} alive={proc_is(st.get('caffeinate_pid'), 'caffeinate')}")
    print(f"worker server {st.get('worker_url')} up={up}  builds {st.get('builds', 0)}/{MAX_BUILDS}  "
          f"network {'DOWN since ' + st['net_down_since'] if st.get('net_down_since') else 'up'}")
    status = session_status(st["worker_url"]) if up else {}
    busy, retry = busy_ids("", status), retry_ids("", status)
    for sha, w in st.get("workers", {}).items():
        flags = f"adopted={bool(w.get('adopted'))} owned={bool(w.get('owned'))}"
        if is_passive(w):
            d = db_state(w["session"])
            shown = f"db:{d.state}"
        else:
            shown = "BUSY" if w["session"] in busy else "RETRY" if w["session"] in retry else "idle"
        print(f"  {sha}  {w['session']}  {shown}  {flags}  spawned {w['spawned']}  last sent {w['sent']}")
    for key, rt in st.get("retries", {}).items():
        print(f"  retry {key}: {rt['kind']} pause, {rt['count']}/{MAX_RETRIES} used, "
              f"{'GAVE UP' if rt.get('gave_up') else 'next at ' + str(rt.get('at'))}")
    hs = harness_runs()
    running = [x["task"] for x in hs.get("runs", []) if x.get("status") == "RUNNING"]
    print(f"harness: running {running or '-'}  queued {len(hs.get('queue', []))}  paused {hs.get('paused')}")
    w, h = limits(st)
    ramp = st.get("ramp")
    print(f"limits now: {w} workers, {h} harness" +
          (f"  (ramp at {ramp['at'][11:16]} -> {ramp['workers']}/{ramp['harness']})" if ramp else ""))
    print(f"budget: paid run starts with <= {MAX_BUSY_AT_LAUNCH} busy; <= {MAX_BUSY_WITH_RUN} busy while one RUNS  "
          + (f"LIMIT since {hm(st['limit_since'])} (reset {hm(st.get('limit_reset'))})" if st.get("limit_since")
             else "no LIMIT"))
    for s in st.get("schedule", []):
        print(f"  plan {s['at'][11:16]} {'sent' if s['sent'] else 'pending'}: {s['text'][:80]}")
    print(f"undelivered events: {len(st.get('events', []))}")
    return 0


# ---------------------------------------------------------------- watcher
def handle_result(st: dict, events: list[str], sha: str, d: DbState) -> None:
    """Report a finished or failed worker reply once per message id."""
    w = st["workers"][sha]
    if d.msg_id == w["reported_msg"]:
        return
    w["reported_msg"] = d.msg_id
    sid = w["session"]
    if d.error is None:
        st["retries"].pop(sha, None)
        tag = f" (adopted session {sid})" if is_passive(w) else ""
        events.append(f"done : {sha}{tag}\n  session {sid}\n  last reply (tail):\n{d.tail}")
        return
    kind, msg = classify(d.error), err_message(d.error)
    if kind == "doom":
        handle_doom(st, events, sha, msg)
        return
    if kind not in RETRY_KINDS:
        events.append(f"ERROR {sha}: {kind}: {json.dumps(d.error)[:400]}\n  session {sid}\n"
                      "  not retried automatically; decide what to do")
        return
    outcome = schedule_retry(st, sha, kind, msg, d.msg_id)
    if outcome == "paused":
        events.append(f"PAUSED {sha}: {kind}: {msg[:200]}\n  session {sid}; retry 'continue' at "
                      f"{hm(st['retries'][sha]['at'])} (up to {MAX_RETRIES} times)")
    elif outcome == "gave_up":
        events.append(f"GAVE UP {sha} after {MAX_RETRIES} retries")


def handle_doom(st: dict, events: list[str], sha: str, msg: str) -> None:
    """opencode's doom_loop guard stopped a repeated tool call: one automatic corrective
    "continue" (AUTO_POLICY: one corrective message), a second doom -> BLOCKED, no second send."""
    w = st["workers"][sha]
    sid = w["session"]
    if w.get("doom_sent"):
        events.append(f"BLOCKED {sha}: doom_loop guard again after the automatic corrective continue "
                      f"({hm(w['doom_sent'])}); no second send. Decide per AUTO_POLICY (skip and report).\n"
                      f"  session {sid}: {msg[:200]}")
        log("doom_blocked", sha=sha)
        return
    try:
        prompt(st["worker_url"], sid, DOOM_CONTINUE)
    except (urllib.error.URLError, OSError) as e:
        events.append(f"ERROR {sha}: doom_loop guard stopped a repeated call; the automatic continue failed "
                      f"({e}); decide what to do\n  session {sid}")
        return
    mark_sent(w)
    w["doom_sent"] = w["corrective_sent"] = ts()
    events.append(f"DOOM {sha}: doom_loop guard stopped a repeated tool call; sent the one corrective message "
                  f"automatically: \"{DOOM_CONTINUE}\". Do not send another corrective; a second doom is BLOCKED.\n"
                  f"  session {sid}")
    log("doom_continue", sha=sha, msg=msg[:300])


def poll_workers(st: dict, events: list[str]) -> None:
    url = st["worker_url"]
    status = session_status(url)
    busy, retry = busy_ids(url, status), retry_ids(url, status)
    st["limit_workers"] = {}
    active: dict[str, str] = {}  # owned workers busy or in retry -> status text for STALL
    for sha, w in st["workers"].items():
        sid = w["session"]
        if sid in retry and not is_passive(w):
            # provider retry: neither busy nor idle; never read as a finished step
            w["idle_polls"] = 0
            note_retry(st, events, sha, retry[sid])
            active[sha] = f"retry: {str(retry[sid].get('message') or '')[:120]}"
            continue
        if is_passive(w):
            d = db_state(sid)
            if d.state == "interrupted" and w.get("interrupted_msg") != d.msg_id:
                w["interrupted_msg"] = d.msg_id
                events.append(f"INTERRUPTED {sha}: session stopped mid-step (its window may have been closed); "
                              "not resumed automatically")
            elif d.state in ("done", "error"):
                handle_result(st, events, sha, d)
            continue
        if sid in busy:
            w["busy_seen"], w["idle_polls"] = True, 0
            if not w["long_warned"] and now() - datetime.fromisoformat(w["sent"]) > timedelta(hours=LONG_BUSY_H):
                w["long_warned"] = True
                events.append(f"WARN {sha}: busy for over {LONG_BUSY_H} h since the last message")
            active[sha] = "busy"
            continue
        w["idle_polls"] += 1
        if w["idle_polls"] < IDLE_POLLS:
            continue
        msg = last_message(url, sid)
        if not msg or msg["info"].get("role") != "assistant":
            continue
        err = msg["info"].get("error")
        handle_result(st, events, sha, DbState("error" if err else "done", msg["info"]["id"], message_text(msg), err))
    check_stall(st, events, url, active)
    for kind in ("permission", "question"):
        try:
            pend = http(f"{url}/{kind}") or []
        except urllib.error.URLError:
            pend = []
        for p in pend:
            key = f"{kind}:{p.get('id')}"
            if key not in st.setdefault("pending_seen", []):
                st["pending_seen"].append(key)
                sha = next((s for s, w in st["workers"].items() if w["session"] == p.get("sessionID")), "?")
                events.append(f"BLOCKED {sha}: worker waits on a {kind}: {json.dumps(p)[:500]}")


def worker_out(w: dict) -> Path | None:
    """The worker's OUT folder, from the "OUT ... `path`" line of its prompt file (cached in w["out"])."""
    if "out" not in w:
        try:
            m = OUT_RE.search(Path(w.get("prompt") or "").read_text(errors="replace"))
        except OSError:
            m = None
        w["out"] = m.group(1).strip() if m else ""
    return Path(w["out"]) if w["out"] else None


def tree_mtime(d: Path, cap: int = 2000) -> float | None:
    """Newest mtime of a folder and (up to `cap`) files under it; None if it does not exist."""
    try:
        times = [d.stat().st_mtime]
    except OSError:
        return None
    for i, p in enumerate(d.rglob("*")):
        if i >= cap:
            break
        try:
            times.append(p.stat().st_mtime)
        except OSError:
            pass
    return max(times)


def last_activity(url: str, w: dict) -> float:
    """Epoch seconds of the newest of: last message time, OUT folder mtime, our last send."""
    times = [datetime.fromisoformat(w["sent"]).timestamp()]
    t = ((last_message(url, w["session"]) or {}).get("info") or {}).get("time") or {}
    times += [v / 1000 for v in t.values() if isinstance(v, (int, float))]
    out = worker_out(w)
    mt = tree_mtime(out) if out else None
    if mt:
        times.append(mt)
    return max(times)


def check_stall(st: dict, events: list[str], url: str, active: dict[str, str]) -> None:
    """R5-05: one STALL event when every busy (or retrying) owned worker has had no activity for
    STALL_MIN; a new one only after some activity and a fresh stall."""
    if not active:
        st["stall_reported"] = False
        return
    acts = {sha: last_activity(url, st["workers"][sha]) for sha in active}
    for sha, t in acts.items():
        st["workers"][sha]["last_activity"] = datetime.fromtimestamp(t, IST).isoformat(timespec="seconds")
    newest = max(acts.values())
    if now().timestamp() - newest < STALL_MIN * 60:
        st["stall_reported"] = False
        return
    if st.get("stall_reported"):
        return
    st["stall_reported"] = True
    status = next((s for s in active.values() if s.startswith("retry")), "busy")
    text = (f"STALL: {len(active)} workers no progress since {datetime.fromtimestamp(newest, IST):%H:%M} "
            f"(status: {status}) [{', '.join(active)}]")
    events.append(text)
    log("stall", workers=list(active), since=datetime.fromtimestamp(newest, IST).isoformat(timespec="seconds"))


def note_retry(st: dict, events: list[str], sha: str, rs: dict) -> None:
    """A worker in provider retry: AUTH (once per message) or a LIMIT hit for check_limit."""
    msg = str(rs.get("message") or "")
    if AUTH_RE.search(msg):
        key = f"{sha}:{msg[:200]}"
        if key not in st.setdefault("auth_seen", []):
            st["auth_seen"].append(key)
            events.append(f"AUTH {sha}: provider rejected the login ({msg[:200]}); not a usage limit, "
                          "no auto-resume. Fix the login, then send the worker `continue`.")
            log("auth_seen", sha=sha, msg=msg[:300])
        return
    if LIMIT_RE.search(msg):
        st["limit_workers"][sha] = {"msg": msg[:300], "next": rs.get("next")}


def notify(text: str) -> None:
    """macOS notification (tests replace this function)."""
    t = " ".join(text.split()).replace("\\", "\\\\").replace('"', '\\"')[:220]
    try:
        subprocess.run(["osascript", "-e", f'display notification "{t}" with title "auto"'],
                       capture_output=True, timeout=10)
    except (OSError, subprocess.SubprocessError) as e:
        log("notify_failed", error=str(e))


def mq(*args: str) -> subprocess.CompletedProcess:
    return sh([str(HARNESS / ".venv/bin/python"), "scripts/master_queue.py", *args], cwd=HARNESS, timeout=300)


def is_auth_pause(reason: str) -> bool:
    return bool(AUTH_RE.search(reason))


def is_limit_pause(reason: str) -> bool:
    """MQ paused for a usage limit (not startup, not AUTH, not our own LIMIT hold)."""
    return bool(reason and LIMIT_RE.search(reason)) and not is_auth_pause(reason) \
        and "startup" not in reason.lower() and not reason.startswith(LIMIT_PAUSE_PREFIX)


def check_limit(st: dict, events: list[str]) -> None:
    """LIMIT on any owned worker in limit retry or an MQ usage-limit pause; LIMIT CLEARED after 2 clean polls."""
    hs = harness_runs()
    reason = (hs.get("pause_reason") or "") if hs.get("paused") else ""
    hits = {sha: h["msg"] for sha, h in (st.get("limit_workers") or {}).items()}
    if is_limit_pause(reason):
        hits["harness"] = reason
    if hits:
        st["limit_clean"] = 0
        if st.get("limit_since"):
            return
        base = now()
        resets = [r for r in (reset_in_text(m, base) for m in hits.values()) if r]
        resets += [datetime.fromtimestamp(h["next"] / 1000, IST) for h in (st.get("limit_workers") or {}).values()
                   if isinstance(h.get("next"), (int, float))]
        reset = min(resets) if resets else None
        st["limit_since"] = base.isoformat(timespec="seconds")
        st["limit_reset"] = reset.isoformat(timespec="seconds") if reset else None
        first = next(iter(hits.values()))
        text = (f"LIMIT: {', '.join(hits)} hit a usage/rate limit ({first[:160]}); reset "
                f"{f'{reset:%H:%M}' if reset else 'unknown'}. Holding spawns and the harness queue.")
        events.append(text)
        report_line(text)
        log("limit_seen", who=list(hits), msg=first[:300], reset=st["limit_reset"])
        notify(text)
        if (HARNESS / ".master-queue").is_dir() and not hs.get("paused"):
            out = mq("pause", f"{LIMIT_PAUSE_PREFIX} since {base:%H:%M}: no new paid run starts until it clears")
            st["mq_paused_by_limit"] = out.returncode == 0
            log("mq_pause", exit=out.returncode, out=(out.stdout + out.stderr)[:300])
        return
    if not st.get("limit_since"):
        return
    st["limit_clean"] = st.get("limit_clean", 0) + 1
    if st["limit_clean"] < LIMIT_CLEAR_POLLS:
        return
    events.append(f"LIMIT CLEARED: {st['limit_clean']} clean polls in a row (LIMIT since {hm(st['limit_since'])})")
    log("limit_cleared", since=st["limit_since"])
    if reason.startswith(LIMIT_PAUSE_PREFIX):
        out = mq("resume")
        log("mq_resume", exit=out.returncode, out=(out.stdout + out.stderr)[:300])
    for k in ("limit_since", "limit_reset", "limit_clean", "mq_paused_by_limit"):
        st.pop(k, None)


def refuse_if_limit(st: dict, what: str) -> None:
    if st.get("limit_since"):
        reset = f"; parsed reset {hm(st['limit_reset'])}" if st.get("limit_reset") else ""
        raise AutoError(f"LIMIT since {hm(st['limit_since'])}{reset}: no {what} until LIMIT CLEARED")


def paid_running() -> list[str]:
    return [r["task"] for r in harness_runs().get("runs", []) if r.get("status") == "RUNNING"]


def write_hold(st: dict) -> None:
    """Tell MQ not to launch from its queue (LIMIT, or > 2 busy workers). Expires if the watcher stops."""
    qdir = HARNESS / ".master-queue"
    if not qdir.is_dir():
        return
    busy = len(busy_workers(st))
    reason = (f"LIMIT since {hm(st['limit_since'])}" if st.get("limit_since") else
              f"{busy} workers busy (> {MAX_BUSY_AT_LAUNCH})" if busy > MAX_BUSY_AT_LAUNCH else "")
    hold = {"hold": bool(reason), "reason": reason, "busy": busy, "written": ts(),
            "expires": (now() + timedelta(seconds=3 * POLL_S)).isoformat(timespec="seconds")}
    tmp = qdir / (HOLD_FILE + ".tmp")
    tmp.write_text(json.dumps(hold) + "\n")
    tmp.replace(qdir / HOLD_FILE)


def process_retries(st: dict) -> None:
    """Send the scheduled 'continue' to paused workers whose retry time has come."""
    url = st["worker_url"]
    for sha, rt in st["retries"].items():
        if sha == MASTER_KEY or not rt.get("at") or now() < datetime.fromisoformat(rt["at"]):
            continue
        w = st["workers"].get(sha)
        if not w or w["session"] in busy_ids(url, include_retry=True):
            continue
        prompt(url, w["session"], "continue")
        mark_sent(w)
        rt["count"] += 1
        rt["at"] = None
        log("retry", sha=sha, n=rt["count"], kind=rt["kind"])


def poll_harness(st: dict, events: list[str]) -> None:
    hs = harness_runs()
    for r in hs.get("runs", []):
        if r.get("status") not in ("DONE", "FAILED"):
            continue
        key = f"{r['task']}#{r.get('attempt')}#{r.get('started_at')}"
        if key in st["harness_seen"]:
            continue
        st["harness_seen"].append(key)
        events.append(f"harness {r['status']}: {r['task']} attempt {r.get('attempt')}  combined {r.get('combined')}  "
                      f"tests {r.get('tests_pct')} ({r.get('tests_passed')}/{r.get('tests_total')})  "
                      f"rubric {r.get('rubric_pct')}\n  note: {r.get('note')}\n  job: {r.get('job_dir')}  "
                      f"log: {r.get('log')}\n  next: tools/intake.py --job {r['task']}")
    for r in hs.get("runs", []):
        if r.get("status") != "RUNNING" or not r.get("log"):
            continue
        try:
            m = EXHAUSTED_LINE_RE.search(Path(r["log"]).read_text(errors="replace"))
        except OSError:
            continue
        key = f"{r['task']}#{r.get('attempt')}"
        if m and key not in st.setdefault("exhausted_seen", []):
            # ANS Q18 a: log only; the paid run is NOT killed
            st["exhausted_seen"].append(key)
            text = f"harness LOG: {r['task']} attempt {r.get('attempt')} still RUNNING: {m.group(0).strip()[:200]} (not killed)"
            events.append(text)
            report_line(text)
            log("harness_exhausted_line", task=r["task"], line=m.group(0).strip()[:300])
    reason = hs.get("pause_reason") if hs.get("paused") else ""
    if reason and reason != st.get("pause_reported"):
        if is_auth_pause(reason):
            events.append(f"AUTH: harness paused on a login fault, not a usage limit; no auto-resume: {reason}")
            log("auth_seen", who="harness", msg=reason[:300])
        else:
            events.append(f"harness PAUSED: {reason}")
    st["pause_reported"] = reason


def harness_auto_resume(st: dict, events: list[str]) -> None:
    """Resume a harness pause caused by a usage limit, at its reset + 5 min, at most 3 times per task."""
    hs = harness_runs()
    reason = hs.get("pause_reason") or ""
    if not hs.get("paused") or not is_limit_pause(reason):
        return
    m = re.search(r"during (\S+)", reason)
    key = hs.get("pause_task") or (m.group(1) if m else reason)
    hr = st.setdefault("harness_resume", {}).setdefault(key, {"count": 0, "at": None, "gave_up": False})
    if hr["gave_up"]:
        return
    if hr["count"] >= HARNESS_RESUME_MAX:
        hr["gave_up"] = True
        events.append(f"harness resume GAVE UP after {HARNESS_RESUME_MAX} tries: {reason[:200]}")
        return
    if not hr["at"]:
        hr["at"] = (parse_reset(reason, now(), HARNESS_RESUME_DEFAULT_MIN)
                    + timedelta(minutes=RESUME_PAD_MIN)).isoformat(timespec="seconds")
    if now() < datetime.fromisoformat(hr["at"]):
        return
    out = mq("resume")
    hr["count"] += 1
    hr["at"] = None
    events.append(f"harness RESUME {hr['count']}/{HARNESS_RESUME_MAX} after limit pause ({reason[:120]}):\n"
                  f"{(out.stdout + out.stderr).strip()[:600]}")
    log("harness_resume", n=hr["count"], reason=reason[:200], exit=out.returncode)


def nothing_running(st: dict) -> bool:
    hs = harness_runs()
    return not busy_workers(st) and not hs.get("queue") and not any(
        r.get("status") == "RUNNING" for r in hs.get("runs", []))


def check_gap(st: dict, events: list[str]) -> None:
    last = st.get("last_poll")
    if last and now() - datetime.fromisoformat(last) > timedelta(minutes=GAP_MIN):
        text = f"GAP: watcher did not run from {hm(last)} to {now():%H:%M} (laptop asleep, shut down, or killed)"
        events.append(text)
        report_line(text)
    st["last_poll"] = ts()


def check_net(st: dict, events: list[str]) -> bool:
    up = net_up()
    if not up:
        st["net_down_since"] = st.get("net_down_since") or ts()
        if not st.get("net_down_noted") and now() - datetime.fromisoformat(st["net_down_since"]) > timedelta(
                minutes=NET_NOTE_MIN):
            st["net_down_noted"] = True
            report_line(f"network down since {hm(st['net_down_since'])}; events and retries are held")
    elif st.get("net_down_since"):
        since = datetime.fromisoformat(st["net_down_since"])
        mins = int((now() - since).total_seconds() // 60)
        events.append(f"NETWORK BACK after {mins} min (down since {since:%H:%M})")
        report_line(f"network back after {mins} min (down since {since:%H:%M})")
        st["net_down_since"], st["net_down_noted"] = None, False
    return up


def master_gate(st: dict, murl: str, msid: str) -> bool:
    """True = hold delivery because the master itself paused on a limit/network error (retry scheduled)."""
    msg = last_message(murl, msid)
    info = (msg or {}).get("info", {})
    err = info.get("error") if info.get("role") == "assistant" else None
    kind = classify(err) if err else None
    if kind not in RETRY_KINDS:
        st["retries"].pop(MASTER_KEY, None)
        return False
    rt = st["retries"].get(MASTER_KEY)
    if rt is None or rt["msg"] != info["id"]:
        outcome = schedule_retry(st, MASTER_KEY, kind, err_message(err), info["id"])
        if outcome == "paused":
            report_line(f"master chat paused ({kind}): {err_message(err)[:150]}; retry at "
                        f"{hm(st['retries'][MASTER_KEY]['at'])}")
        elif outcome == "gave_up":
            report_line(f"master chat still failing after {MAX_RETRIES} retries; gave up")
        return not outcome.startswith("gave_up")
    if rt.get("gave_up"):
        return False
    if rt.get("at") and now() >= datetime.fromisoformat(rt["at"]):
        agent, model, variant = master_identity(murl, msid)
        prompt(murl, msid, "continue", agent=agent, model=model, variant=variant)
        rt["count"] += 1
        rt["at"] = None
        st["master_idle_polls"] = 0
        log("master_retry", n=rt["count"], kind=kind)
    return True


def note_master_hold(st: dict, murl: str, msid: str) -> None:
    """R5-04: events queued while the master is in provider retry for MASTER_HOLD_POLLS polls:
    one REPORT line, the events listed in REPORT.md, one notification per hold. Events stay queued."""
    if not st["events"]:
        st.pop("master_hold", None)
        return
    rs = retry_ids(murl).get(msid)
    if not rs:  # Ayush 29 Oct 01:58: alert only on provider retry, never on a merely busy master
        st.pop("master_hold", None)
        return
    kind = "retry"
    hold = st.get("master_hold")
    if not hold or hold["kind"] != kind:
        hold = st["master_hold"] = {"kind": kind, "since": ts(), "polls": 0, "reported": False}
    hold["polls"] += 1
    if hold["reported"] or hold["polls"] < MASTER_HOLD_POLLS:
        return
    hold["reported"] = True
    text = (f"master chat in provider retry since {hm(hold['since'])}: {str(rs.get('message') or '')[:200]}"
            if rs else f"master chat busy since {hm(hold['since'])}")
    text += f"; {len(st['events'])} watcher events not delivered (still queued)"
    report_line(text)
    report_undelivered(st["events"], hold["since"])
    notify(text)
    log("master_hold", kind=kind, since=hold["since"], events=len(st["events"]))


def deliver(st: dict) -> None:
    """Send queued events to the master once it has been idle IDLE_POLLS polls."""
    reg = REGISTRY / f"{st['master']}.json"
    if reg.is_file():  # Ayush may have restarted the master chat on a new port
        st["master_url"] = json.loads(reg.read_text())["url"]
    murl, msid = st["master_url"], st["master_session"]
    if not healthy(murl):
        st["master_down_since"] = st.get("master_down_since") or ts()
        if now() - datetime.fromisoformat(st["master_down_since"]) > timedelta(minutes=30) \
                and not st.get("master_down_noted"):
            st["master_down_noted"] = True
            report_line(f"master chat unreachable since {hm(st['master_down_since'])}; "
                        f"undelivered events are in {cur().state} and {cur().log}")
        return
    st["master_down_noted"] = False
    st["master_down_since"] = None
    if msid in busy_ids(murl, include_retry=True):
        st["master_idle_polls"] = 0
        note_master_hold(st, murl, msid)
        return
    st.pop("master_hold", None)
    st["master_idle_polls"] = st.get("master_idle_polls", 0) + 1
    if st["master_idle_polls"] < IDLE_POLLS:
        return
    if master_gate(st, murl, msid) or not st["events"]:
        return
    agent, model, variant = master_identity(murl, msid)
    r = cur()
    body = (f"[AUTO WATCHER] {now():%H:%M} IST (auto mode until {st['until'][11:16]}; Ayush is away)\n\n"
            + "\n\n".join(st["events"])
            + f"\n\nAct per {AUTO_DIR}/AUTO_POLICY.md and {r.dir}/PLAN.md (the plan wins where they differ) in "
              f"place of Ayush. Use auto.py spawn/send/harness. Never push. Record decisions as by day and keep "
              f"{r.dir}/REPORT.md current.")
    prompt(murl, msid, body, agent=agent, model=model, variant=variant)
    log("deliver", events=st["events"])
    st["events"], st["master_idle_polls"], st["last_delivery"] = [], 0, ts()


def due_plan_events(st: dict, events: list[str]) -> None:
    for s in st.get("schedule", []):
        if not s["sent"] and now() >= datetime.fromisoformat(s["at"]):
            s["sent"] = True
            events.append(f"PLAN AT {s['at'][11:16]}: {s['text']}")


def wind_down(st: dict, events: list[str]) -> None:
    r = cur()
    idle = not busy_workers(st)
    overdue = now() - datetime.fromisoformat(st["stop_at"]) > timedelta(hours=WIND_DOWN_MAX_H)
    if (idle or overdue) and not st.get("final_sent"):
        st["final_sent"] = True
        events.append("ALL AUTO WORKERS IDLE" if idle else f"WIND-DOWN TIMEOUT ({WIND_DOWN_MAX_H} h): "
                      "some workers still busy and will be stopped")
        events.append(f"FINAL: finish {r.report} now (every decision, result, override, unfinished item, proposed "
                      "change, and every question for Ayush), then stop. Issue nothing.")


def watch_once(st: dict) -> bool:
    """One poll. Returns False when the watcher should exit."""
    r = cur()
    events = st["events"]
    check_gap(st, events)
    up = check_net(st, events)
    if (r.stop.exists() or now() >= datetime.fromisoformat(st["until"])) and not st["stopping"]:
        st["stopping"], st["stop_at"] = True, ts()
        r.stop.write_text(st["stop_at"] + "\n")
        events.append("AUTO STOP: start nothing new (no spawn, no harness add). Running workers finish their "
                      f"current step; send them nothing new. Finish {r.report} now.")
    worker_ok = bool(st.get("worker_url")) and healthy(st["worker_url"])
    if worker_ok:
        if st.get("worker_down_reported"):
            text = (f"worker server answering again (not answering since {hm(st.get('worker_fail_since'))}); "
                    "polling workers again")
            events.append(text)
            report_line(text)
        st.update(worker_fail=0, worker_fail_since=None, worker_down_reported=False)
        poll_workers(st, events)
        if up:
            process_retries(st)
    else:
        # R5-07: down only after WORKER_DOWN_POLLS failed checks in a row; polls are skipped on any miss
        st["worker_fail"] = st.get("worker_fail", 0) + 1
        st["worker_fail_since"] = st.get("worker_fail_since") or ts()
        if st["worker_fail"] >= WORKER_DOWN_POLLS and not st.get("worker_down_reported"):
            st["worker_down_reported"] = True
            text = (f"ERROR: auto worker server not answering ({st['worker_fail']} health checks in a row since "
                    f"{hm(st['worker_fail_since'])}, {HEALTH_TIMEOUT_S} s timeout); workers are not polled")
            events.append(text)
            report_line(text)
    if not worker_ok:
        st["limit_workers"] = {}
    poll_harness(st, events)
    check_limit(st, events)
    if up:
        harness_auto_resume(st, events)
    write_hold(st)
    due_plan_events(st, events)
    ramp = st.get("ramp")
    if ramp and not ramp.get("announced") and now() >= datetime.fromisoformat(ramp["at"]):
        ramp["announced"] = True
        events.append(f"LIMITS RAISED: up to {ramp['workers']} busy workers and {ramp['harness']} harness runs "
                      "at a time now. Fill the free slots from the queue.")
        log("ramp", workers=ramp["workers"], harness=ramp["harness"])
    if st["stopping"]:
        wind_down(st, events)
    elif not events and up and healthy(st["master_url"]) and nothing_running(st):
        last = datetime.fromisoformat(st.get("last_delivery") or st["started"])
        if now() - last > timedelta(minutes=NUDGE_MIN) and st.get("nudges", 0) < MAX_NUDGES:
            st["nudges"] = st.get("nudges", 0) + 1
            events.append(f"IDLE CHECK {st['nudges']}/{MAX_NUDGES}: no worker or harness run is active. Start the "
                          "next item in the plan/policy queue, or record in REPORT.md why nothing can run.")
    if any(not e.startswith("IDLE CHECK") for e in events):
        st["nudges"] = 0
    if up:
        deliver(st)
    return not (st.get("final_sent") and not st["events"] and st.get("master_idle_polls", 0) >= IDLE_POLLS)


def shutdown_children(st: dict) -> None:
    terminate(st.get("worker_pid"), "opencode")
    terminate(st.get("caffeinate_pid"), "caffeinate")
    log("children_stopped", worker_pid=st.get("worker_pid"), caffeinate_pid=st.get("caffeinate_pid"))


def cmd_watch(a) -> int:
    if a.run:
        use_run(Path(a.run))
    else:
        latest_run()
    log("watcher_up", pid=os.getpid())
    while True:
        with locked():
            st = load_state()
            try:
                keep = watch_once(st)
            except Exception as e:  # keep watching through transient API errors; record them
                log("watch_error", error=repr(e))
                keep = True
            save_state(st)
        if not keep:
            break
        time.sleep(POLL_S)
    st = load_state()
    shutdown_children(st)
    st["ended"] = ts()
    save_state(st)
    log("watcher_exit")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("start")
    s.add_argument("--until", required=True, help="HH:MM IST")
    s.add_argument("--at", help="HH:MM IST: schedule the start instead of starting now")
    s.add_argument("--plan", help="plan file; copied to PLAN.md; 'at HH:MM: text' lines are scheduled")
    s.add_argument("--label", default="auto")
    s.add_argument("--master", default="master", help="oc registry name of the master chat")
    s.add_argument("--session", default=MASTER_SESSION)
    s.add_argument("--workers", type=int, default=MAX_BUSY_WORKERS, help="max busy workers at start")
    s.add_argument("--harness", type=int, default=1, help="max harness runs at a time at start")
    s.add_argument("--ramp", nargs=3, metavar=("HH:MM", "WORKERS", "HARNESS"),
                   help="raise the limits at this IST time, e.g. --ramp 01:45 4 2")
    s.add_argument("--no-adopt", action="store_true", help="do not adopt running board.json rows")
    sub.add_parser("resume", help="after a reboot/terminal close: restart server and watcher")
    s = sub.add_parser("adopt", help="track a session started elsewhere")
    s.add_argument("sha")
    s.add_argument("--session", help="session id (default: newest root session titled SHA)")
    s = sub.add_parser("limits", help="change the limits now (clears any ramp)")
    s.add_argument("--workers", type=int, required=True)
    s.add_argument("--harness", type=int, required=True)
    sub.add_parser("stop")
    sub.add_parser("status")
    sub.add_parser("cancel", help="remove a scheduled start")
    s = sub.add_parser("scheduled", help=argparse.SUPPRESS)
    s.add_argument("--id", required=True)
    s = sub.add_parser("watch")
    s.add_argument("--run", help=argparse.SUPPRESS)
    s = sub.add_parser("spawn")
    s.add_argument("sha")
    s.add_argument("prompt")
    s.add_argument("--build", action="store_true", help="counts toward the 2 new builds per run")
    s = sub.add_parser("send")
    s.add_argument("sha")
    s.add_argument("text", help="message text, or @file")
    s = sub.add_parser("harness")
    s.add_argument("bundle")
    return p


def main() -> int:
    a = build_parser().parse_args()
    fn = {"start": cmd_start, "resume": cmd_resume, "adopt": cmd_adopt, "stop": cmd_stop, "status": cmd_status,
          "watch": cmd_watch, "spawn": cmd_spawn, "send": cmd_send, "harness": cmd_harness,
          "limits": cmd_limits, "cancel": cmd_cancel, "scheduled": cmd_scheduled}[a.cmd]
    try:
        if a.cmd in ("status", "resume"):
            print(schedule_status())
        if a.cmd == "status" and not (AUTO_DIR / "LATEST").is_file():
            print("auto mode never started")
            return 0
        if a.cmd in ("resume", "adopt", "spawn", "send", "limits"):
            latest_run()
            with locked():
                return fn(a)
        return fn(a)
    except AutoError as e:
        print(f"auto.py: {e}", file=sys.stderr)
        return 2
    except urllib.error.URLError as e:
        print(f"auto.py: opencode API error: {e}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())
