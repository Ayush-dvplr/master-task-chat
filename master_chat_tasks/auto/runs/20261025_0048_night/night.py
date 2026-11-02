#!/usr/bin/env python3
"""Night mode: run the master chat's pipeline while Ayush sleeps.

The master chat (opencode TUI started with `oc master -s <id>`) keeps deciding as
by day, using NIGHT_POLICY.md in place of Ayush's answers. This script is its
hands and the watcher that replaces Ayush's "done: <sha>" messages.

  night.py start --until 07:30      worker server + watcher (run from the master chat)
  night.py spawn SHA PROMPT.md      new worker session titled SHA, prompt = file text
  night.py send SHA TEXT|@FILE      next message ("go", answers) to an idle worker
  night.py harness BUNDLE           harness queue recipe (one run at a time)
  night.py status                   workers, harness, watcher
  night.py stop                     start nothing new; watcher winds down
  night.py watch                    the watcher loop (started by `start`)

Paths can be moved for tests with NIGHT_DIR, NIGHT_PROJECT, NIGHT_HARNESS,
NIGHT_REGISTRY, NIGHT_SECRET.
"""
from __future__ import annotations

import argparse
import base64
import fcntl
import json
import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")
HERE = Path(__file__).resolve().parent
NIGHT_DIR = Path(os.environ.get("NIGHT_DIR", HERE))
PROJECT = Path(os.environ.get("NIGHT_PROJECT", HERE.parents[1]))
HARNESS = Path(os.environ.get("NIGHT_HARNESS", PROJECT / "Terminal_2.0_Harbor_Harness"))
REGISTRY = Path(os.environ.get("NIGHT_REGISTRY", Path.home() / ".local/state/oc-bridge/tui"))
SECRET = Path(os.environ.get("NIGHT_SECRET", Path.home() / ".config/oc-bridge/secret"))

STATE = NIGHT_DIR / "state.json"
LOG = NIGHT_DIR / "night_log.jsonl"
STOP = NIGHT_DIR / "NIGHT_STOP"
LOGS = NIGHT_DIR / "logs"
POLICY = NIGHT_DIR / "NIGHT_POLICY.md"
MORNING = NIGHT_DIR / "MORNING.md"
HARNESS_STATE = HARNESS / ".master-queue/state.json"

MASTER_SESSION = "ses_ea5ff5f97ffe6WB1VzP4StPOw6"
MODEL = {"providerID": "anthropic", "modelID": "claude-opus-5-5"}
VARIANT = "high"
MAX_BUSY_WORKERS = 4
MAX_BUILDS = 2
MAX_HARNESS = 2
POLL_S = int(os.environ.get("NIGHT_POLL_S", "60"))
IDLE_POLLS = 2            # a session must be idle this many polls in a row
LONG_BUSY_H = 6
NUDGE_MIN = 45            # idle check when nothing runs
MAX_NUDGES = 3
WIND_DOWN_MAX_H = 2

# Workers may do anything inside the project except publish, commit, queue the
# harness, or drive night mode; outside the project only temp dirs.
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
        "*night.py*": "deny",
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


class NightError(Exception):
    pass


# ---------------------------------------------------------------- helpers
def now() -> datetime:
    return datetime.now(IST)


def ts() -> str:
    return now().isoformat(timespec="seconds")


def log(event: str, **data) -> None:
    NIGHT_DIR.mkdir(parents=True, exist_ok=True)
    with LOG.open("a") as f:
        f.write(json.dumps({"ist": ts(), "event": event, **data}) + "\n")


@contextmanager
def locked():
    """Serialise every read-modify-write of state.json (watcher and commands)."""
    NIGHT_DIR.mkdir(parents=True, exist_ok=True)
    with (NIGHT_DIR / "state.lock").open("w") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def load_state() -> dict:
    if STATE.exists():
        return json.loads(STATE.read_text())
    return {}


def save_state(st: dict) -> None:
    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(st, indent=2) + "\n")
    tmp.replace(STATE)


def secret() -> str:
    if not SECRET.is_file():
        raise NightError(f"no secret at {SECRET}; start the master chat with `oc master -s {MASTER_SESSION}`")
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
        return bool((http(url + "/global/health", timeout=5) or {}).get("healthy"))
    except (urllib.error.URLError, OSError, ValueError):
        return False


def master_url(name: str) -> str:
    f = REGISTRY / f"{name}.json"
    if not f.is_file():
        raise NightError(f"master chat not registered ({f}); restart it with `oc {name} -s {MASTER_SESSION}`")
    url = json.loads(f.read_text())["url"]
    if not healthy(url):
        raise NightError(f"master chat port {url} not answering; restart it with `oc {name} -s {MASTER_SESSION}`")
    return url


def busy_ids(url: str) -> set[str]:
    st = http(url + "/session/status") or {}
    return {sid for sid, s in st.items() if s.get("type") != "idle"}


def last_message(url: str, sid: str) -> dict | None:
    msgs = http(f"{url}/session/{sid}/message?limit=1") or []
    return msgs[-1] if msgs else None


def message_text(msg: dict | None, tail: int = 1500) -> str:
    if not msg:
        return ""
    text = "\n".join(p.get("text", "") for p in msg.get("parts", []) if p.get("type") == "text").strip()
    return text if len(text) <= tail else "..." + text[-tail:]


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


def require_not_worker() -> None:
    if os.environ.get("OC_NIGHT_WORKER"):
        raise NightError("night workers may not drive night mode")


def require_running(st: dict) -> None:
    if not st.get("worker_url") or not healthy(st["worker_url"]):
        raise NightError("night mode is not running (night.py start --until HH:MM)")


def harness_runs() -> dict:
    if not HARNESS_STATE.is_file():
        return {"runs": [], "queue": [], "paused": False}
    return json.loads(HARNESS_STATE.read_text())


def worker_env() -> dict:
    env = dict(os.environ)
    env["OPENCODE_SERVER_PASSWORD"] = secret()
    env["OPENCODE_PERMISSION"] = json.dumps(WORKER_PERMISSION)
    env["OC_NIGHT_WORKER"] = "1"
    if not env.get("ANTHROPIC_CLI_VERSION"):
        # opus-5-5 is gated on the advertised Claude Code version; ~/.zshrc computes it.
        out = subprocess.run(["zsh", "-ic", "print -r -- $ANTHROPIC_CLI_VERSION"], capture_output=True, text=True)
        ver = out.stdout.strip().splitlines()[-1] if out.stdout.strip() else ""
        if ver:
            env["ANTHROPIC_CLI_VERSION"] = ver
    return env


def parse_until(hhmm: str) -> datetime:
    h, m = (int(x) for x in hhmm.split(":"))
    t = now().replace(hour=h, minute=m, second=0, microsecond=0)
    return t if t > now() else t + timedelta(days=1)


def limits(st: dict) -> tuple[int, int]:
    """(max busy workers, max harness runs) now: the ramp values once its time has passed."""
    ramp = st.get("ramp")
    if ramp and now() >= datetime.fromisoformat(ramp["at"]):
        return ramp["workers"], ramp["harness"]
    return st.get("max_workers", MAX_BUSY_WORKERS), st.get("max_harness", 1)


def check_limits(workers: int, harness: int) -> None:
    if not (1 <= workers <= MAX_BUSY_WORKERS and 1 <= harness <= MAX_HARNESS):
        raise NightError(f"limits must be workers 1-{MAX_BUSY_WORKERS}, harness 1-{MAX_HARNESS}")


# ---------------------------------------------------------------- commands
def cmd_start(a) -> int:
    require_not_worker()
    st = load_state()
    if st.get("watcher_pid") and pid_alive(st["watcher_pid"]):
        raise NightError(f"night mode already running (watcher pid {st['watcher_pid']}); night.py status")
    murl = master_url(a.master)
    until = parse_until(a.until)
    check_limits(a.workers, a.harness)
    ramp = None
    if a.ramp:
        r_at, r_w, r_h = a.ramp
        check_limits(int(r_w), int(r_h))
        ramp = {"at": parse_until(r_at).isoformat(timespec="minutes"), "workers": int(r_w), "harness": int(r_h)}
    LOGS.mkdir(parents=True, exist_ok=True)
    STOP.unlink(missing_ok=True)

    srv_log = LOGS / f"worker_server_{now():%Y%m%dT%H%M%S}.log"
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
            break
        if srv.poll() is not None:
            raise NightError(f"worker server exited; see {srv_log}")
    if not url:
        srv.kill()
        raise NightError(f"worker server did not start in 60 s; see {srv_log}")

    hs = harness_runs()
    st = {
        "started": ts(), "until": until.isoformat(timespec="minutes"), "master": a.master,
        "master_url": murl, "master_session": a.session, "worker_url": url, "worker_pid": srv.pid,
        "worker_log": str(srv_log), "workers": {}, "builds": 0,
        "harness_seen": [f"{r['task']}#{r.get('attempt')}#{r.get('started_at')}" for r in hs.get("runs", [])
                         if r.get("status") in ("DONE", "FAILED")],
        "events": [], "stopping": False,
        "max_workers": a.workers, "max_harness": a.harness, "ramp": ramp,
    }
    save_state(st)
    wlog = LOGS / "watcher.log"
    with wlog.open("a") as out:
        w = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "watch"], env=dict(os.environ),
                             stdout=out, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, start_new_session=True)
    st["watcher_pid"] = w.pid
    save_state(st)
    if not MORNING.exists():
        MORNING.write_text(MORNING_TEMPLATE.format(started=st["started"], until=st["until"]))
    log("start", until=st["until"], worker_url=url, worker_pid=srv.pid, watcher_pid=w.pid,
        max_workers=a.workers, max_harness=a.harness, ramp=ramp)
    print(f"NIGHT MODE ON until {until:%H:%M} IST\n  worker server {url} (pid {srv.pid})\n  watcher pid {w.pid}"
          f"\n  limits: {a.workers} workers, {a.harness} harness"
          + (f"; from {ramp['at'][11:16]}: {ramp['workers']} workers, {ramp['harness']} harness" if ramp else "")
          +
          f"\n  watch a worker: opencode attach {url} -s <session id>   (password: {SECRET})"
          f"\n  stop: night.py stop  or  touch {STOP}")
    return 0


def cmd_stop(a) -> int:
    STOP.write_text(ts() + "\n")
    log("stop_requested")
    print("NIGHT_STOP written: nothing new starts; running workers finish their current step.")
    return 0


def cmd_spawn(a) -> int:
    require_not_worker()
    st = load_state()
    require_running(st)
    if STOP.exists() or st.get("stopping"):
        raise NightError("night mode is stopping; nothing new starts")
    if a.sha in st["workers"]:
        raise NightError(f"{a.sha} already has a worker ({st['workers'][a.sha]['session']}); use send")
    text = Path(a.prompt).read_text()
    if f"`{a.sha}`" not in text and a.sha not in text:
        raise NightError(f"prompt file does not mention board id {a.sha}; issue it with tools/issue.py first")
    url = st["worker_url"]
    busy = busy_ids(url) & {w["session"] for w in st["workers"].values()}
    max_w = limits(st)[0]
    if len(busy) >= max_w:
        raise NightError(f"{len(busy)} workers busy (limit {max_w} now); wait for one to finish")
    if a.build and st.get("builds", 0) >= MAX_BUILDS:
        raise NightError(f"{MAX_BUILDS} new builds already started tonight (limit)")
    sess = http(url + "/session", "POST", {"title": a.sha})
    prompt(url, sess["id"], text)
    st = load_state()
    st["workers"][a.sha] = {"session": sess["id"], "prompt": str(Path(a.prompt).resolve()), "spawned": ts(),
                            "build": bool(a.build), "sent": ts(), "busy_seen": False, "idle_polls": 0,
                            "reported_msg": None, "long_warned": False}
    st["builds"] = st.get("builds", 0) + (1 if a.build else 0)
    save_state(st)
    log("spawn", sha=a.sha, session=sess["id"], prompt=a.prompt, build=bool(a.build))
    print(f"spawned {a.sha} -> {sess['id']}\n  watch: opencode attach {url} -s {sess['id']}")
    return 0


def cmd_send(a) -> int:
    require_not_worker()
    st = load_state()
    require_running(st)
    w = st["workers"].get(a.sha)
    if not w:
        raise NightError(f"no night worker for {a.sha}")
    url = st["worker_url"]
    if w["session"] in busy_ids(url):
        raise NightError(f"{a.sha} is busy; wait for its done event")
    text = Path(a.text[1:]).read_text() if a.text.startswith("@") else a.text
    prompt(url, w["session"], text)
    st = load_state()
    st["workers"][a.sha].update(sent=ts(), busy_seen=False, idle_polls=0)
    save_state(st)
    log("send", sha=a.sha, text=text[:300])
    print(f"sent to {a.sha} ({w['session']})")
    return 0


def run(cmd: list[str], cwd: Path | None = None, timeout: int = 120) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)


def cmd_harness(a) -> int:
    require_not_worker()
    st = load_state()
    if STOP.exists() or st.get("stopping"):
        raise NightError("night mode is stopping; nothing new starts")
    bundle = Path(a.bundle).resolve()
    if not (bundle / "task.toml").is_file():
        raise NightError(f"{bundle} has no task.toml")
    hs = harness_runs()
    active = [r["task"] for r in hs.get("runs", []) if r.get("status") == "RUNNING"] + \
             [q if isinstance(q, str) else q.get("task", "?") for q in hs.get("queue", [])]
    max_h = limits(st)[1]
    if len(active) >= max_h:
        raise NightError(f"harness busy ({', '.join(active)}); limit {max_h} run(s) at a time now")
    if bundle.name in active:
        raise NightError(f"{bundle.name} is already running or queued on the harness")
    if hs.get("paused"):
        raise NightError(f"harness paused: {hs.get('pause_reason')}")
    checks = {
        "docker": run(["docker", "ps", "-q"]).returncode == 0,
        "pypi": run(["curl", "-sS", "-o", "/dev/null", "-m", "15", "-w", "%{http_code}",
                     "https://pypi.org/simple/pip/"]).stdout.strip() == "200",
    }
    harbor = [l for l in run(["ps", "-axo", "pid,command"]).stdout.splitlines()
              if "harbor" in l and "run" in l and "grep" not in l]
    load = run(["uptime"]).stdout.strip()
    print(f"pre-checks: {checks}  harbor processes: {len(harbor)}\n  {load}")
    if not all(checks.values()):
        raise NightError(f"pre-check failed: {checks}")
    staged = HARNESS / "Tasks_INPUT" / bundle.name
    before = run(["diff", "-rq", str(bundle), str(staged)]).stdout.strip() if staged.exists() else "(not staged yet)"
    print("diff before:", before or "(same)")
    py = HARNESS / ".venv/bin/python"
    add = run([str(py), "scripts/master_queue.py", "add", str(bundle)], cwd=HARNESS, timeout=300)
    print(add.stdout.strip(), add.stderr.strip())
    if add.returncode != 0:
        raise NightError(f"master_queue add failed (exit {add.returncode})")
    after = run(["diff", "-rq", str(bundle), str(staged)]).stdout.strip()
    if after:
        raise NightError(f"staged copy differs from bundle after add:\n{after}")
    print(run([str(py), "scripts/master_queue.py", "status"], cwd=HARNESS).stdout.strip())
    log("harness_add", bundle=str(bundle))
    return 0


def cmd_limits(a) -> int:
    require_not_worker()
    check_limits(a.workers, a.harness)
    st = load_state()
    if not st:
        raise NightError("night mode never started")
    st.update(max_workers=a.workers, max_harness=a.harness, ramp=None)
    save_state(st)
    log("limits", workers=a.workers, harness=a.harness)
    print(f"limits now: {a.workers} workers, {a.harness} harness (ramp cleared)")
    return 0


def cmd_status(a) -> int:
    st = load_state()
    if not st:
        print("night mode never started")
        return 0
    up = bool(st.get("worker_url")) and healthy(st["worker_url"])
    print(f"started {st['started']} until {st['until']}  stop file: {STOP.exists()}  stopping: {st.get('stopping')}")
    print(f"watcher pid {st.get('watcher_pid')} alive={pid_alive(st.get('watcher_pid'))}  "
          f"worker server {st.get('worker_url')} up={up}  builds {st.get('builds', 0)}/{MAX_BUILDS}")
    busy = busy_ids(st["worker_url"]) if up else set()
    for sha, w in st.get("workers", {}).items():
        print(f"  {sha}  {w['session']}  {'BUSY' if w['session'] in busy else 'idle'}  spawned {w['spawned']}  "
              f"last sent {w['sent']}")
    hs = harness_runs()
    running = [r["task"] for r in hs.get("runs", []) if r.get("status") == "RUNNING"]
    print(f"harness: running {running or '-'}  queued {len(hs.get('queue', []))}  paused {hs.get('paused')}")
    w, h = limits(st)
    ramp = st.get("ramp")
    print(f"limits now: {w} workers, {h} harness" +
          (f"  (ramp at {ramp['at'][11:16]} -> {ramp['workers']}/{ramp['harness']})" if ramp else ""))
    print(f"undelivered events: {len(st.get('events', []))}")
    return 0


# ---------------------------------------------------------------- watcher
def poll_workers(st: dict, events: list[str]) -> None:
    url = st["worker_url"]
    busy = busy_ids(url)
    for sha, w in st["workers"].items():
        sid = w["session"]
        if sid in busy:
            w["busy_seen"], w["idle_polls"] = True, 0
            started = datetime.fromisoformat(w["sent"])
            if not w["long_warned"] and now() - started > timedelta(hours=LONG_BUSY_H):
                w["long_warned"] = True
                events.append(f"WARN {sha}: busy for over {LONG_BUSY_H} h since the last message")
            continue
        w["idle_polls"] += 1
        if w["idle_polls"] < IDLE_POLLS:
            continue
        msg = last_message(url, sid)
        if not msg or msg["info"].get("role") != "assistant" or msg["info"]["id"] == w["reported_msg"]:
            continue
        w["reported_msg"] = msg["info"]["id"]
        err = msg["info"].get("error")
        head = f"done : {sha}" if not err else f"ERROR {sha}: {json.dumps(err)[:400]}"
        events.append(f"{head}\n  session {sid}\n  last reply (tail):\n{message_text(msg)}")
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
    reason = hs.get("pause_reason") if hs.get("paused") else ""
    if reason and reason != st.get("pause_reported"):
        events.append(f"harness PAUSED: {reason}")
    st["pause_reported"] = reason


def nothing_running(st: dict) -> bool:
    busy = busy_ids(st["worker_url"]) & {w["session"] for w in st["workers"].values()}
    hs = harness_runs()
    return not busy and not hs.get("queue") and not any(r.get("status") == "RUNNING" for r in hs.get("runs", []))


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
            with MORNING.open("a") as f:
                f.write(f"\n- WATCHER {ts()}: master chat unreachable since {st['master_down_since']}; "
                        f"undelivered events are in {STATE} and {LOG}.\n")
        return
    st["master_down_noted"] = False
    st["master_down_since"] = None
    if msid in busy_ids(murl):
        st["master_idle_polls"] = 0
        return
    st["master_idle_polls"] = st.get("master_idle_polls", 0) + 1
    if not st["events"] or st["master_idle_polls"] < IDLE_POLLS:
        return
    agent, model, variant = master_identity(murl, msid)
    body = (f"[NIGHT WATCHER] {now():%H:%M} IST (night mode until {st['until'][11:16]}; Ayush is asleep)\n\n"
            + "\n\n".join(st["events"])
            + f"\n\nAct per {POLICY} in place of Ayush. Use night.py spawn/send/harness. Never push. "
              f"Record decisions as by day and add every item for Ayush to {MORNING}.")
    prompt(murl, msid, body, agent=agent, model=model, variant=variant)
    log("deliver", events=st["events"])
    st["events"], st["master_idle_polls"], st["last_delivery"] = [], 0, ts()


def watch_once(st: dict) -> bool:
    """One poll. Returns False when the watcher should exit."""
    events = st["events"]
    stop_now = STOP.exists() or now() >= datetime.fromisoformat(st["until"])
    if stop_now and not st["stopping"]:
        st["stopping"], st["stop_at"] = True, ts()
        STOP.write_text(st["stop_at"] + "\n")
        events.append("NIGHT STOP: start nothing new (no spawn, no harness add). Running workers finish their "
                      "current step; send them nothing new. Begin MORNING.md now.")
    if healthy(st["worker_url"]):
        poll_workers(st, events)
    else:
        if not st.get("worker_down_reported"):
            st["worker_down_reported"] = True
            events.append("ERROR: night worker server is not answering; workers are stopped")
    poll_harness(st, events)
    ramp = st.get("ramp")
    if ramp and not ramp.get("announced") and now() >= datetime.fromisoformat(ramp["at"]):
        ramp["announced"] = True
        events.append(f"LIMITS RAISED: up to {ramp['workers']} busy workers and {ramp['harness']} harness runs "
                      "at a time now. Fill the free slots from the night queue.")
        log("ramp", workers=ramp["workers"], harness=ramp["harness"])

    if st["stopping"]:
        idle = not healthy(st["worker_url"]) or not (
            busy_ids(st["worker_url"]) & {w["session"] for w in st["workers"].values()})
        overdue = now() - datetime.fromisoformat(st["stop_at"]) > timedelta(hours=WIND_DOWN_MAX_H)
        if (idle or overdue) and not st.get("final_sent"):
            st["final_sent"] = True
            events.append("ALL NIGHT WORKERS IDLE" if idle else f"WIND-DOWN TIMEOUT ({WIND_DOWN_MAX_H} h): "
                          "some workers still busy and will be stopped")
            events.append(f"FINAL: finish {MORNING} now (every decision, result, override, parked task, proposed "
                          "template change, and every question for Ayush), then stop. Issue nothing.")
    elif not events and healthy(st["master_url"]) and nothing_running(st):
        last = datetime.fromisoformat(st.get("last_delivery") or st["started"])
        if now() - last > timedelta(minutes=NUDGE_MIN) and st.get("nudges", 0) < MAX_NUDGES:
            st["nudges"] = st.get("nudges", 0) + 1
            events.append(f"IDLE CHECK {st['nudges']}/{MAX_NUDGES}: no worker or harness run is active. Start the "
                          "next item in the night queue per the policy, or record in MORNING.md why nothing can run.")
    if any(not e.startswith("IDLE CHECK") for e in events):
        st["nudges"] = 0

    deliver(st)
    if st.get("final_sent") and not st["events"] and st.get("master_idle_polls", 0) >= IDLE_POLLS:
        return False
    return True


def shutdown_workers(st: dict) -> None:
    pid = st.get("worker_pid")
    if pid_alive(pid):
        try:
            os.killpg(pid, signal.SIGTERM)
        except OSError:
            os.kill(pid, signal.SIGTERM)
    log("worker_server_stopped", pid=pid)


def cmd_watch(a) -> int:
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
    shutdown_workers(st)
    st["ended"] = ts()
    save_state(st)
    log("watcher_exit")
    return 0


MORNING_TEMPLATE = """# MORNING report (night mode {started} -> {until})

Written by the master chat during the night. Ayush reads this first.

## Needs Ayush (questions, approvals, overrides to confirm)

## Results (harness runs, QC verdicts, gate status per task)

## Decisions taken under NIGHT_POLICY (and round-limit overrides given)

## Parked or skipped (and why)

## Proposed template changes (not applied; apply only after Ayush says ok)

## Still running at stop
"""


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("start")
    s.add_argument("--until", required=True, help="HH:MM IST")
    s.add_argument("--master", default="master", help="oc registry name of the master chat")
    s.add_argument("--session", default=MASTER_SESSION)
    s.add_argument("--workers", type=int, default=MAX_BUSY_WORKERS, help="max busy workers at start")
    s.add_argument("--harness", type=int, default=1, help="max harness runs at a time at start")
    s.add_argument("--ramp", nargs=3, metavar=("HH:MM", "WORKERS", "HARNESS"),
                   help="raise the limits at this IST time, e.g. --ramp 01:45 4 2")
    s = sub.add_parser("limits", help="change the limits now (clears any ramp)")
    s.add_argument("--workers", type=int, required=True)
    s.add_argument("--harness", type=int, required=True)
    sub.add_parser("stop")
    sub.add_parser("status")
    sub.add_parser("watch")
    s = sub.add_parser("spawn")
    s.add_argument("sha")
    s.add_argument("prompt")
    s.add_argument("--build", action="store_true", help="counts toward the 2 new builds a night")
    s = sub.add_parser("send")
    s.add_argument("sha")
    s.add_argument("text", help="message text, or @file")
    s = sub.add_parser("harness")
    s.add_argument("bundle")
    a = p.parse_args()
    fn = {"start": cmd_start, "stop": cmd_stop, "status": cmd_status, "watch": cmd_watch, "spawn": cmd_spawn,
          "send": cmd_send, "harness": cmd_harness, "limits": cmd_limits}[a.cmd]
    try:
        if a.cmd in ("start", "spawn", "send", "limits"):
            with locked():
                return fn(a)
        return fn(a)
    except NightError as e:
        print(f"night.py: {e}", file=sys.stderr)
        return 2
    except urllib.error.URLError as e:
        print(f"night.py: opencode API error: {e}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())
