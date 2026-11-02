#!/usr/bin/env python3
"""Master run queue for route B: OpenHands on Claude, judge on Codex.

Keeps up to N tasks from a FIFO queue running through scripts/anubis-run
(openhands-sdk on claude-opus-5 via the Claude subscription bridge, judge
gpt-5.6-sol via the Codex bridge, on a task copy staged by
scripts/kiro_oauth/stage_task.py), records every attempt (start, finish,
score, failure) in .master-queue/state.json, and re-renders the AUTO blocks of
MASTER_RUN_LEDGER.md after every change. Runs recorded before route B used the
Kiro route (scripts/run-with-kiro-subscription.sh).

    .venv/bin/python scripts/master_queue.py add PATH [PATH ...]   # copy to Tasks_INPUT, queue, start runner
    .venv/bin/python scripts/master_queue.py status
    .venv/bin/python scripts/master_queue.py start | stop | resume
    .venv/bin/python scripts/master_queue.py cancel TASK
    .venv/bin/python scripts/master_queue.py set-max N
    .venv/bin/python scripts/master_queue.py render
    .venv/bin/python scripts/master_queue.py dry-run TASK   # print the launch for Tasks_INPUT/TASK; no agent runs

The runner is a detached process. It exits on its own once nothing is queued or
running, and `add`, `start` and `resume` start it again. Stopping the runner
never stops runs that are already going: each run lives in its own session.

A run counts as hung when a kiro-cli-chat process of its bridge has been alive
for HANG_SECS with no ESTABLISHED TCP connection while the run log has not
grown for HANG_SECS, on HANG_STRIKES consecutive checks. A hung run is killed,
its containers and unfinished job folder are deleted, and it is put back at the
front of the queue once (one automatic relaunch per queued item). Only Kiro runs
have such a process; a route B run is bounded by harbor's agent and verifier
timeouts.
"""

from __future__ import annotations

import argparse
import fcntl
import filecmp
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
import tomllib
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

ROOT = Path(__file__).resolve().parents[1]
LOG_ROOT = Path("/tmp/opencode-logs")
WRAPPER = "scripts/anubis-run"
ROUTE = "claude"            # marks route B runs in state.json
BRIDGE_HOST = "host.docker.internal"
# Flags anubis-run does not add itself (see the route B guide): agent and model, bridge access
# for the agent, the trajectory for the separate verifier, and three agent env fixes.
ROUTE_ARGS = ["--agent", "openhands-sdk", "-m", "claude-opus-5", "-y",
              "--allow-agent-host", BRIDGE_HOST, "--artifact", "/logs/agent/trajectory.json",
              "--ae", "LITELLM_LOCAL_MODEL_COST_MAP=True", "--ae", "HOME=/tmp", "--ae", "LLM_NUM_RETRIES=10"]
DEFAULT_MAX = 3
HANG_SECS = 15 * 60
HANG_STRIKES = 3
TICK_SECS = 60
STARTUP_FAIL_SECS = 300     # a run that dies this fast with no model request pauses the queue
MEM_HEADROOM_MB = 3072
DEFAULT_CPUS, DEFAULT_MEM_MB = 2.0, 4096
TRIAL_NAME_MAX = 32         # harbor truncates the task part of trial names to this

ANSI = re.compile(r"\x1b\[[0-9;]*m")
FINAL_RE = re.compile(r"finalize complete\. jobs_dir=(.+?)\s{2,}harbor_exit=(-?\d+)")
WRAPPER_EXIT_RE = re.compile(r"\[master_queue\] wrapper_exit=(-?\d+)")
# AUTH (login fault) is checked before USAGE_LIMIT_RE: `EXHAUSTED http 401` and wrapper exit 8 are not limits.
AUTH_RE = re.compile(r"(?:EXHAUSTED|BADKEY) http 40[13]\b|\[master_queue\] wrapper_exit=8\b", re.I)
RESET_SECS_RE = re.compile(r"reset in (\d+)s\b", re.I)
HOLD_FILE = "auto_hold.json"   # written by master_chat_tasks/auto/auto.py each poll; launch waits while it holds
USAGE_LIMIT_RE = re.compile(r"monthly usage limit has been reached|accounts exhausted|EXHAUSTED http \d+", re.I)
ERROR_RE = re.compile(r"traceback|exception|not logged in|abort|error:", re.I)
REDACT = [
    (re.compile(r"\b(\w*(?:API_KEY|SECRET|TOKEN|AUTH_VALUE))=\S+"), r"\1=<redacted>"),
    (re.compile(r"(token prefix: )\S+"), r"\1<redacted>"),
    (re.compile(r"sk-ant-[\w-]+"), "<redacted>"),
    (re.compile(r"(Bearer )\S+"), r"\1<redacted>"),
    (re.compile(r"\b[0-9a-fA-F]{32,}\b"), "<redacted>"),
]

Run = dict[str, Any]
State = dict[str, Any]

_strikes: dict[tuple[str, int], int] = {}


@dataclass(frozen=True)
class Ctx:
    root: Path = ROOT
    log_root: Path = LOG_ROOT
    hang_secs: int = HANG_SECS

    @property
    def qdir(self) -> Path:
        return self.root / ".master-queue"

    @property
    def state_file(self) -> Path:
        return self.qdir / "state.json"

    @property
    def pid_file(self) -> Path:
        return self.qdir / "runner.pid"

    @property
    def ledger(self) -> Path:
        return self.root / "MASTER_RUN_LEDGER.md"

    @property
    def tasks_input(self) -> Path:
        return self.root / "Tasks_INPUT"

    @property
    def jobs(self) -> Path:
        return self.root / "jobs"

    @property
    def runner_log(self) -> Path:
        return self.log_root / "master-queue" / "runner.log"


# ---------- time ----------

def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def ts(iso: str) -> float:
    return datetime.fromisoformat(iso).timestamp()


def fmt(iso: str | None) -> str:
    return datetime.fromisoformat(iso).strftime("%Y-%m-%d %H:%M") if iso else "-"


# ---------- state ----------

@contextmanager
def locked(ctx: Ctx) -> Iterator[None]:
    ctx.qdir.mkdir(parents=True, exist_ok=True)
    with open(ctx.qdir / "state.lock", "w") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        yield


def load(ctx: Ctx) -> State:
    if ctx.state_file.is_file():
        return json.loads(ctx.state_file.read_text())
    return {"max_concurrent": DEFAULT_MAX, "paused": False, "pause_reason": "", "queue": [], "runs": []}


def save(ctx: Ctx, st: State) -> None:
    tmp = ctx.state_file.with_suffix(".tmp")
    tmp.write_text(json.dumps(st, indent=2) + "\n")
    os.replace(tmp, ctx.state_file)


def running(st: State) -> list[Run]:
    return [r for r in st["runs"] if r["status"] == "RUNNING"]


def next_attempt(st: State, task: str) -> int:
    return 1 + max((r["attempt"] for r in st["runs"] if r["task"] == task), default=0)


# ---------- processes ----------

def pid_alive(pid: int) -> bool:
    try:
        done, _ = os.waitpid(pid, os.WNOHANG)   # reap our own exited children (zombies look alive)
        if done == pid:
            return False
    except ChildProcessError:
        pass
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def parse_etime(s: str) -> int:
    days, _, rest = s.rpartition("-")
    secs = 0
    for part in rest.split(":"):
        secs = secs * 60 + int(part)
    return secs + int(days or 0) * 86400


def ps_table() -> list[tuple[int, int, int, str]]:
    out = subprocess.run(["ps", "-axo", "pid=,pgid=,etime=,command="],
                         capture_output=True, text=True).stdout
    rows = []
    for line in out.splitlines():
        parts = line.split(None, 3)
        if len(parts) == 4:
            rows.append((int(parts[0]), int(parts[1]), parse_etime(parts[2]), parts[3]))
    return rows


def kiro_chat_procs(pgid: int) -> list[tuple[int, int]]:
    """(pid, elapsed seconds) of the bridge's kiro-cli-chat sessions in a run's process group."""
    return [(pid, et) for pid, pg, et, cmd in ps_table()
            if pg == pgid and cmd.split()[0].endswith("/kiro-cli-chat") and " acp" in cmd]


def established(pid: int) -> int:
    out = subprocess.run(["lsof", "-nP", "-a", "-p", str(pid), "-iTCP", "-sTCP:ESTABLISHED"],
                         capture_output=True, text=True).stdout
    return max(0, len(out.splitlines()) - 1)


def harbor_pgids(task: str | None = None) -> set[int]:
    """Process groups of `harbor run` processes, for one task or for all."""
    found = set()
    for _, pg, _, cmd in ps_table():
        if "bin/harbor run " not in cmd:
            continue
        if task is None or f"/.kiro-staged-tasks/{task} " in cmd or f"Tasks_INPUT/{task} " in cmd:
            found.add(pg)
    return found


def external_harbor_pgids(st: State) -> set[int]:
    """Harbor runs on this machine that this queue did not start; they count toward the limit."""
    ours = set()
    for r in running(st):
        ours |= harbor_pgids(r["task"])
    return harbor_pgids() - ours


def docker_budget() -> tuple[float, int] | None:
    """(cpus, memory MB) Docker can give to runs, or None when Docker is not reachable."""
    try:
        r = subprocess.run(["docker", "info", "--format", "{{.NCPU}} {{.MemTotal}}"],
                           capture_output=True, text=True, timeout=30)
        if r.returncode != 0:
            return None
        n, mem = r.stdout.split()
        return float(n), int(mem) // 2**20 - MEM_HEADROOM_MB
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return None


def trial_prefixes(ctx: Ctx, task: str) -> set[str]:
    names = {task}
    try:
        name = tomllib.loads((ctx.tasks_input / task / "task.toml").read_text())["task"]["name"]
        names.add(name.rsplit("/", 1)[-1])
    except (OSError, KeyError, tomllib.TOMLDecodeError):
        pass
    return names | {n[:TRIAL_NAME_MAX] for n in names}


def remove_containers(prefixes: set[str]) -> list[str]:
    starts = tuple(p.lower() + "__" for p in prefixes)
    removed = []
    for kind, ls_cmd, rm_cmd in (
        ("container", ["docker", "ps", "-a", "--format", "{{.Names}}"], ["docker", "rm", "-f"]),
        ("network", ["docker", "network", "ls", "--format", "{{.Name}}"], ["docker", "network", "rm"]),
    ):
        try:
            names = subprocess.run(ls_cmd, capture_output=True, text=True, timeout=60).stdout.split()
            for name in (n for n in names if n.startswith(starts)):
                subprocess.run([*rm_cmd, name], capture_output=True, timeout=120)
                removed.append(f"{kind} {name}")
        except (OSError, subprocess.TimeoutExpired):
            pass
    return removed


def kill_run(ctx: Ctx, run: Run) -> list[str]:
    """Stop the wrapper, bridge and harbor of a run, then remove its containers."""
    for sig in (signal.SIGTERM, signal.SIGKILL):
        groups = {run["pid"]} | harbor_pgids(run["task"])
        for pg in groups:
            try:
                os.killpg(pg, sig)
            except (ProcessLookupError, PermissionError):
                pass
        deadline = time.time() + 20
        while time.time() < deadline:
            launcher_alive = pid_alive(run["pid"])   # first, so our own exited child gets reaped
            alive = {pg for _, pg, _, _ in ps_table()} & groups
            if not alive and not launcher_alive:
                break
            time.sleep(1)
        else:
            continue
        break
    return remove_containers(trial_prefixes(ctx, run["task"]))


def partial_job_dirs(ctx: Ctx, run: Run) -> list[Path]:
    """Unfinalized (still timestamp-named) job folders this run created."""
    if not ctx.jobs.is_dir():
        return []
    since = ts(run["started_at"]) - 120
    prefixes = trial_prefixes(ctx, run["task"])
    return [d for d in ctx.jobs.iterdir()
            if d.is_dir() and d.name.startswith("20") and d.stat().st_mtime >= since
            and any(any(d.glob(f"{p}__*")) for p in prefixes)]


# ---------- results ----------

def rel(ctx: Ctx, p: Path) -> str:
    try:
        return str(p.relative_to(ctx.root)) + "/"
    except ValueError:
        return str(p) + "/"


def log_text(run: Run) -> str:
    p = Path(run["log"])
    return ANSI.sub("", p.read_text(errors="replace")) if p.is_file() else ""


def request_counts(text: str) -> tuple[int, int]:
    posts = [ln for ln in text.splitlines() if "POST /chat" in ln or "POST /v1/messages" in ln]
    return len(posts), sum("200 OK" not in ln for ln in posts)


def read_bundle(job: Path) -> Run:
    """Scores from a finalized bundle; empty when it has no pass_summary.json."""
    summaries = sorted(job.glob("trajectory/*/pass_summary.json"), key=lambda p: p.stat().st_mtime)
    if not summaries:
        return {}
    s = json.loads(summaries[-1].read_text())
    upd: Run = {"combined": s.get("average_combined_score"), "tests_pct": s.get("average_test_weights_percentage"),
                "rubric_pct": s.get("average_rubric_weights_percentage"), "failed_tests": []}
    reports = sorted(summaries[-1].parent.glob("Run */report.json"),
                     key=lambda p: int(p.parent.name.split()[-1]) if p.parent.name.split()[-1].isdigit() else 0)
    if reports:
        tests = (json.loads(reports[-1].read_text()).get("pytest") or {}).get("tests") or []
        failed = [t.get("name", "?") for t in tests if not t.get("passed")]
        upd.update(tests_passed=len(tests) - len(failed), tests_total=len(tests), failed_tests=failed)
    return upd


def failed_note(failed: list[str]) -> str:
    if not failed:
        return ""
    return f"failed: {', '.join(failed[:4])}" + (f" (+{len(failed) - 4} more)" if len(failed) > 4 else "")


def adopt_bundle(ctx: Ctx, run: Run, job: Path, st: State) -> Path:
    """Move a finished bundle out of the run's private jobs root into jobs/<name>."""
    root = Path(run["jobs_root"])
    if job.parent != root or not job.is_dir():
        return job
    ctx.jobs.mkdir(parents=True, exist_ok=True)
    target = ctx.jobs / job.name
    if target.exists():
        archive = ctx.jobs / "_archive" / f"{job.name}-{datetime.now().strftime('%Y%m%dT%H%M%S')}"
        archive.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(target), str(archive))
        for r in st["runs"]:
            if r.get("job_dir") == rel(ctx, target):
                r["job_dir"] = rel(ctx, archive)
    shutil.move(str(job), str(target))
    if all(p.name == ".kiro-usage" for p in root.iterdir()):
        shutil.rmtree(root, ignore_errors=True)
    return target


def read_result(ctx: Ctx, run: Run, st: State) -> Run:
    text = log_text(run)
    reqs, non200 = request_counts(text)
    upd: Run = {"requests": reqs, "non_200": non200}
    finals = list(FINAL_RE.finditer(text))
    if finals:
        job, harbor_exit = Path(finals[-1].group(1).strip()), int(finals[-1].group(2))
        exit_label = "harbor_exit"
        prefixes = trial_prefixes(ctx, run["task"])
        if job.name not in prefixes and not any(any(job.glob(f"{p}__*")) for p in prefixes):
            upd.update(status="FAILED", note=f"harness finalized another run's folder ({job.name}); {UNFINALIZED}")
            return upd
    else:
        # Route B prints no finalize line: the wrapper exit code and the one job folder in the
        # run's private root stand in for it.
        exits = WRAPPER_EXIT_RE.findall(text)
        job = find_unfinalized_job(ctx, run) if exits and run.get("jobs_root") else None
        prefixes = trial_prefixes(ctx, run["task"])
        started = job is not None and (any(job.glob("trajectory/*"))
                                       or any(any(job.glob(f"{p}__*")) for p in prefixes))
        if not started:
            errors = [ln.strip() for ln in text.splitlines() if ERROR_RE.search(ln)]
            note = errors[-1][:200] if errors else "wrapper exited without finalizing"
            upd.update(status="FAILED", note=f"wrapper_exit={exits[-1]}; {note}" if exits else note)
            if job is not None:
                upd["job_dir"] = rel(ctx, job)
            return upd
        harbor_exit, exit_label = int(exits[-1]), "wrapper_exit"
    clean = "completed cleanly" in text
    scores = read_bundle(job)
    failed = scores.pop("failed_tests", [])
    upd.update(scores)
    if harbor_exit == 0 and scores and clean:
        if run.get("jobs_root"):
            job = adopt_bundle(ctx, run, job, st)
        upd.update(status="DONE", note=failed_note(failed))
    else:
        upd["status"] = "FAILED"
        upd["note"] = (f"{exit_label}={harbor_exit}, integrity {'clean' if clean else 'NOT clean'}, "
                       f"pass_summary {'found' if scores else 'missing'}")
    upd["job_dir"] = rel(ctx, job)
    return upd


# ---------- re-finalize (runs the harness's own finalize steps on one bundle) ----------

SCRIPTS = Path(__file__).resolve().parent
JUDGE_MODEL = "gpt-5.6-sol"   # run-with-kiro-subscription.sh default for --judge-with
UNFINALIZED = "pass_summary missing"


def stage_task(src: Path, stage_root: Path) -> Path:
    """Copy of the task whose verifier allowlist also lets the judge reach the Codex bridge."""
    p = subprocess.run([sys.executable, str(SCRIPTS / "kiro_oauth" / "stage_task.py"), str(src),
                        str(stage_root), BRIDGE_HOST], capture_output=True, text=True, timeout=120)
    lines = p.stdout.strip().splitlines()
    if p.returncode or not lines:
        raise RuntimeError((p.stderr.strip() or p.stdout.strip() or f"exit {p.returncode}")[:200])
    return Path(lines[-1])


def wrapper_argv(root: Path, task_dir: Path) -> list[str]:
    # The wrapper's exit code is echoed into the run log: route B prints no finalize line.
    return ["bash", "-c", 'bash "$0" "$@"; rc=$?; echo "[master_queue] wrapper_exit=$rc"; exit $rc',
            WRAPPER, "-o", str(root), str(task_dir), "1", *ROUTE_ARGS]


def subscription_env() -> dict[str, str]:
    p = Path.home() / ".anubis" / "subscription.env"
    out: dict[str, str] = {}
    if p.is_file():
        for line in p.read_text().splitlines():
            m = re.match(r"\s*(?:export\s+)?([A-Z_][A-Z0-9_]*)=(.*)$", line)
            if m:
                out[m.group(1)] = m.group(2).strip().strip("'\"")
    return out


def run_finalize(ctx: Ctx, job: Path, log: Path) -> Path:
    """The steps of _kiro_run_and_finalize.sh after `harbor run`, for an existing job folder.

    The judge step reuses the verifier's verdicts, so a dead endpoint is enough
    (KIRO_RUN_GUIDE.md section 6). Odoo records already accepted are skipped by
    build_trajectory_usage.py itself. Returns the bundle path after renaming.
    """
    env = dict(os.environ)
    for k, v in subscription_env().items():
        env.setdefault(k, v)
    env.update(OPENAI_BASE_URL="http://127.0.0.1:9", OPENAI_API_BASE="http://127.0.0.1:9", OPENAI_API_KEY="x")
    log.parent.mkdir(parents=True, exist_ok=True)
    with open(log, "a") as fh:
        def step(*args: Any) -> str:
            fh.write(f"$ {' '.join(map(str, args))}\n")
            fh.flush()
            r = subprocess.run([sys.executable, *map(str, args)], cwd=ctx.root, env=env,
                               capture_output=True, text=True, timeout=1800)
            fh.write(r.stdout + r.stderr + f"[exit {r.returncode}]\n")
            fh.flush()
            return r.stdout + r.stderr

        step(SCRIPTS / "rescale_rewards.py", job)
        step(SCRIPTS / "normalize_ctrf.py", job)
        step(SCRIPTS / "judge_trajectory.py", "--model", JUDGE_MODEL, "--provider", "openai", job)
        step(SCRIPTS / "generate_pass_summary.py", job)
        if os.access(SCRIPTS / "backfill_thinking_tokens.py", os.X_OK):
            step(SCRIPTS / "backfill_thinking_tokens.py", job)
        usage = [SCRIPTS / "build_trajectory_usage.py", job, "-o", job / "trajectory_usage.json",
                 "--no-account-subscription"]
        if env.get("ANUBIS_USAGE_API_URL"):
            usage.append("--post")
        step(*usage)
        step(SCRIPTS / "aggregate_logs.py", job)
        step(SCRIPTS / "reshape_trajectories.py", job, "--quiet")
        named = step(SCRIPTS / "name_job_by_task.py", job, "--apply")
        m = re.search(r"^\[name_job\] .* -> (.+)$", named, re.M)
        if m and (job.parent / m.group(1)).is_dir() and not job.exists():
            job = job.parent / m.group(1)
        step(SCRIPTS / "build_deliverables.py", job.parent)
        step(SCRIPTS / "package_rfp_bundles.py", "--jobs", job.parent, "-o", ctx.root / "Output_RFP")
    return job


def find_unfinalized_job(ctx: Ctx, run: Run) -> Path | None:
    if run.get("jobs_root"):
        root = Path(run["jobs_root"])
        dirs = [d for d in root.iterdir() if d.is_dir() and not d.name.startswith(".")] if root.is_dir() else []
    else:
        dirs = partial_job_dirs(ctx, run)
    return dirs[0] if len(dirs) == 1 else None


def refinalize(ctx: Ctx, run: Run, st: State) -> str:
    run["refinalized"] = True
    task = run["task"]
    job = find_unfinalized_job(ctx, run)
    if job is None:
        # Another run's finalize may already have finalized and renamed this bundle.
        done = [d for d in (ctx.jobs / p for p in trial_prefixes(ctx, task))
                if any(d.glob("trajectory/*/pass_summary.json")) and d.stat().st_mtime >= ts(run["started_at"])]
        if not done:
            run["note"] += "; re-finalize skipped: job folder not found"
            return f"{task}: re-finalize skipped, job folder not found"
        job = done[0]
    else:
        log = ctx.log_root / "master-queue" / f"refinalize-{task}-{datetime.now().strftime('%Y%m%dT%H%M%S')}.log"
        run["refinalize_log"] = str(log)
        job = run_finalize(ctx, job, log)
        if run.get("jobs_root"):
            job = adopt_bundle(ctx, run, job, st)
    scores = read_bundle(job)
    failed = scores.pop("failed_tests", [])
    run["job_dir"] = rel(ctx, job)
    if not scores:
        run["note"] += "; re-finalize produced no pass_summary"
        return f"{task}: re-finalize produced no pass_summary ({run.get('refinalize_log')})"
    run.update(scores, status="DONE", note=("re-finalized after the harness picked the wrong job folder"
                                            + (f"; {failed_note(failed)}" if failed else "")))
    return f"{task}: re-finalized, combined={scores.get('combined')}"


# ---------- scheduling ----------

def task_resources(ctx: Ctx, task: str) -> tuple[float, int]:
    try:
        env = tomllib.loads((ctx.tasks_input / task / "task.toml").read_text()).get("environment", {})
    except (OSError, tomllib.TOMLDecodeError):
        env = {}
    return float(env.get("cpus") or DEFAULT_CPUS), int(env.get("memory_mb") or DEFAULT_MEM_MB)


def is_hung(ctx: Ctx, run: Run, now: float) -> bool:
    key = (run["task"], run["attempt"])
    stuck = [pid for pid, et in kiro_chat_procs(run["pid"]) if et >= ctx.hang_secs and established(pid) == 0]
    log = Path(run["log"])
    idle = now - log.stat().st_mtime if log.is_file() else 0
    if stuck and idle >= ctx.hang_secs:
        _strikes[key] = _strikes.get(key, 0) + 1
    else:
        _strikes.pop(key, None)
    return _strikes.get(key, 0) >= HANG_STRIKES


def launch(ctx: Ctx, st: State, item: dict[str, Any]) -> str:
    task = item["task"]
    run: Run = {"task": task, "source": item["source"], "attempt": item["attempt"], "status": "RUNNING",
                "started_at": now_iso(), "finished_at": None, "pid": None, "log": "", "job_dir": None, "note": ""}
    run["hang_retry"] = item.get("hang_retry", False)
    run["task_updated"] = item.get("task_updated", False)
    st["runs"].append(run)
    if not (ctx.tasks_input / task / "task.toml").is_file():
        run.update(status="FAILED", finished_at=now_iso(), note=f"Tasks_INPUT/{task} is missing")
        return f"{task}: not launched, Tasks_INPUT/{task} is missing"
    try:
        staged = stage_task(ctx.tasks_input / task, ctx.root / ".kiro-staged-tasks")
    except (RuntimeError, OSError, subprocess.SubprocessError) as e:
        run.update(status="FAILED", finished_at=now_iso(), note=f"staging Tasks_INPUT/{task} failed: {e}")
        return f"{task}: not launched, {run['note']}"
    stamp = datetime.now().strftime('%Y%m%dT%H%M%S')
    logdir = ctx.log_root / f"{task}-{stamp}"
    logdir.mkdir(parents=True, exist_ok=True)
    run["log"] = str(logdir / "run.log")
    # A private jobs root per run: the harness finalize takes "the newest new folder" under its
    # jobs root, so a shared jobs/ lets one run finalize another's folder. The root sits directly
    # in the repo because build_deliverables.py writes to <jobs root>/../Output_Deliverables.
    root = ctx.root / f".kiro-run-{task}-{stamp}"
    root.mkdir(parents=True, exist_ok=True)
    run["jobs_root"] = str(root)
    run["route"] = ROUTE
    with open(run["log"], "w") as fh:
        p = subprocess.Popen(wrapper_argv(root, staged),
                             cwd=ctx.root,
                             stdout=fh, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                             start_new_session=True)
    run["pid"] = p.pid
    return f"{task}: launched attempt {run['attempt']} (pid {p.pid}, log {run['log']})"


def auto_hold(ctx: Ctx) -> str:
    """Reason the auto watcher holds launches (LIMIT, too many busy workers), or "" (none / expired)."""
    try:
        h = json.loads((ctx.qdir / HOLD_FILE).read_text())
        if h.get("hold") and datetime.fromisoformat(h["expires"]).timestamp() > time.time():
            return str(h.get("reason") or "auto hold")
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return ""


def maybe_launch(ctx: Ctx, st: State) -> list[str]:
    if st["paused"] or not st["queue"] or auto_hold(ctx):
        return []
    active = running(st)
    external = external_harbor_pgids(st)
    if len(active) + len(external) >= st["max_concurrent"]:
        return []
    budget = docker_budget()
    if budget is None:
        return ["docker is not reachable; not launching"]
    used = [task_resources(ctx, r["task"]) for r in active] + [(DEFAULT_CPUS, DEFAULT_MEM_MB)] * len(external)
    cpus, mem = task_resources(ctx, st["queue"][0]["task"])
    if used and (sum(c for c, _ in used) + cpus > budget[0] or sum(m for _, m in used) + mem > budget[1]):
        return []   # FIFO: wait for room rather than letting a smaller task jump the queue
    return [launch(ctx, st, st["queue"].pop(0))]


def tick(ctx: Ctx, st: State) -> list[str]:
    msgs = []
    now = time.time()
    for run in running(st):
        task = run["task"]
        if not pid_alive(run["pid"]):
            run.update(read_result(ctx, run, st), finished_at=now_iso())
            msgs.append(f"{task}: attempt {run['attempt']} {run['status']} "
                        f"combined={run.get('combined')} {run.get('note', '')}".rstrip())
            text = log_text(run)
            if run["status"] == "FAILED" and AUTH_RE.search(text):
                run["note"] = f"login rejected (auth); {run['note']}"
                if not any(q["task"] == task for q in st["queue"]):
                    st["queue"].insert(0, {"task": task, "source": run["source"], "added_at": now_iso(),
                                           "attempt": run["attempt"] + 1,
                                           "task_updated": run.get("task_updated", False)})
                st["paused"] = True
                st["pause_task"] = task
                st["pause_reason"] = (f"AUTH: login rejected during {task} (requeued at the front). "
                                      f"Run scripts/anubis-auth setup, then master_queue.py resume.")
                msgs.append(f"queue paused: {st['pause_reason']}")
                continue
            if run["status"] == "FAILED" and USAGE_LIMIT_RE.search(text):
                run["note"] = f"subscription usage limit reached; {run['note']}"
                if not any(q["task"] == task for q in st["queue"]):
                    st["queue"].insert(0, {"task": task, "source": run["source"], "added_at": now_iso(),
                                           "attempt": run["attempt"] + 1,
                                           "task_updated": run.get("task_updated", False)})
                st["paused"] = True
                reset = RESET_SECS_RE.search(text)
                st["pause_task"] = task
                st["pause_reason"] = (f"subscription usage limit reached during {task} "
                                      f"(requeued at the front). Resume once the limit resets."
                                      + (f"; soonest reset in {reset.group(1)}s" if reset else ""))
                msgs.append(f"queue paused: {st['pause_reason']}")
                continue
            quick = now - ts(run["started_at"]) < STARTUP_FAIL_SECS
            if run["status"] == "FAILED" and quick and not run.get("requests"):
                st["paused"] = True
                st["pause_reason"] = f"{task} failed at startup: {run['note']}"
                msgs.append(f"queue paused: {st['pause_reason']}")
            continue
        if is_hung(ctx, run, now):
            removed = kill_run(ctx, run)
            deleted = [Path(run["jobs_root"])] if run.get("jobs_root") else partial_job_dirs(ctx, run)
            for d in deleted:
                shutil.rmtree(d, ignore_errors=True)
            reqs, _ = request_counts(log_text(run))
            note = (f"hung: kiro-cli idle with no connection for {ctx.hang_secs // 60}+ min after "
                    f"{reqs} requests; killed, removed {len(removed)} docker objects, deleted "
                    f"{', '.join(rel(ctx, d) for d in deleted) or 'no job folder'}")
            if not run.get("hang_retry"):
                st["queue"].insert(0, {"task": task, "source": run["source"], "added_at": now_iso(),
                                       "attempt": run["attempt"] + 1, "hang_retry": True,
                                       "task_updated": run.get("task_updated", False)})
                note += "; relaunch queued"
            else:
                note += "; attempts exhausted, not relaunched"
            run.update(status="FAILED", finished_at=now_iso(), requests=reqs, note=note)
            _strikes.pop((task, run["attempt"]), None)
            msgs.append(f"{task}: {note}")
    # Re-finalizing renames folders inside jobs/, so wait until no run is still finalizing there.
    shared_busy = any(not r.get("jobs_root") for r in running(st)) or external_harbor_pgids(st)
    # run_finalize is the Kiro finalize; a failed route B run is diagnosed by hand instead.
    if not shared_busy:
        for run in st["runs"]:
            note = run.get("note", "")
            if (run["status"] == "FAILED" and UNFINALIZED in note and "integrity NOT clean" not in note
                    and not run.get("refinalized") and run.get("route") != ROUTE):
                msgs.append(refinalize(ctx, run, st))
    msgs += maybe_launch(ctx, st)
    return msgs


# ---------- ledger ----------

def _cell(v: Any) -> str:
    return "-" if v in (None, "") else str(v).replace("|", "\\|")


def latest_scores(st: State) -> list[dict[str, Any]]:
    by_task: dict[str, list[Run]] = {}
    for r in st["runs"]:
        if r["status"] == "DONE":
            by_task.setdefault(r["task"], []).append(r)
    rows = []
    for task, done in by_task.items():
        last, prev = done[-1], (done[-2] if len(done) > 1 else None)
        change = None
        if prev and last.get("combined") is not None and prev.get("combined") is not None:
            change = round(last["combined"] - prev["combined"], 2)
        rows.append({"task": task, "attempt": last["attempt"], "finished": last.get("finished_at"),
                     "combined": last.get("combined"), "tests_pct": last.get("tests_pct"),
                     "rubric_pct": last.get("rubric_pct"),
                     "passed": f"{last['tests_passed']}/{last['tests_total']}" if last.get("tests_total") else "-",
                     "prev": prev.get("combined") if prev else None,
                     "change": change, "updated": bool(last.get("task_updated"))})
    return rows


def render(ctx: Ctx, st: State) -> None:
    if not ctx.ledger.is_file():
        return
    queue = [f"Updated {fmt(now_iso())}. Max concurrent: {st['max_concurrent']}."]
    if st["paused"]:
        queue.append(f"\n**PAUSED:** {st['pause_reason']} Fix it, then run `master_queue.py resume`.")
    queue += ["", "| # | Task | Status | Attempt | Since | Source |", "|---|---|---|---|---|---|"]
    rows = [(r["task"], "RUNNING", r["attempt"], r["started_at"], r["source"]) for r in running(st)]
    rows += [(q["task"], "QUEUED", q["attempt"], q["added_at"], q["source"]) for q in st["queue"]]
    for i, (task, status, att, since, src) in enumerate(rows, 1):
        queue.append(f"| {i} | {task} | {status} | {att} | {fmt(since)} | `{src}` |")
    if not rows:
        queue.append("| - | (empty) | | | | |")

    hist = ["| Task | Attempt | Started | Finished | Status | Combined | Tests % | Rubric % | Tests passed "
            "| Job folder | Log | Notes |", "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in st["runs"]:
        passed = f"{r['tests_passed']}/{r['tests_total']}" if r.get("tests_total") else "-"
        job = f"`{r['job_dir']}`" if r.get("job_dir") else "-"
        log = f"`{r['log']}`" if r.get("log") else "-"
        hist.append(f"| {r['task']} | {r['attempt']}{' (fixed task)' if r.get('task_updated') else ''} | {fmt(r['started_at'])} | {fmt(r.get('finished_at'))} "
                    f"| {r['status']} | {_cell(r.get('combined'))} | {_cell(r.get('tests_pct'))} "
                    f"| {_cell(r.get('rubric_pct'))} | {passed} | {job} | {log} | {_cell(r.get('note'))} |")

    latest = ["| Task | Attempt | Finished | Combined | Tests % | Rubric % | Tests passed | Previous combined "
              "| Change |", "|---|---|---|---|---|---|---|---|---|"]
    for x in latest_scores(st):
        ch = "-" if x["change"] is None else f"{x['change']:+}"
        att = f"{x['attempt']} (fixed task)" if x["updated"] else str(x["attempt"])
        latest.append(f"| {x['task']} | {att} | {fmt(x['finished'])} | {_cell(x['combined'])} "
                      f"| {_cell(x['tests_pct'])} | {_cell(x['rubric_pct'])} | {x['passed']} "
                      f"| {_cell(x['prev'])} | {ch} |")

    fails = [f"- **{fmt(r.get('finished_at'))}, {r['task']} attempt {r['attempt']}:** {r.get('note') or 'failed'}"
             for r in st["runs"] if r["status"] == "FAILED"]
    blocks = {"LATEST": "\n".join(latest), "QUEUE": "\n".join(queue), "HISTORY": "\n".join(hist), "FAILURES": "\n".join(fails) or "- (none)"}

    text = ctx.ledger.read_text()
    for name, body in blocks.items():
        text = re.sub(rf"(<!-- AUTO:{name} -->\n).*?(<!-- /AUTO:{name} -->)",
                      lambda m, b=body: m.group(1) + b + "\n" + m.group(2), text, flags=re.S)
    ctx.ledger.write_text(text)


# ---------- runner ----------

def runner_pid(ctx: Ctx) -> int | None:
    try:
        pid = int(ctx.pid_file.read_text().strip())
    except (OSError, ValueError):
        return None
    if not pid_alive(pid):
        return None
    cmd = subprocess.run(["ps", "-o", "command=", "-p", str(pid)], capture_output=True, text=True).stdout
    return pid if "master_queue.py" in cmd and " runner" in cmd else None


def ensure_runner(ctx: Ctx) -> None:
    if (pid := runner_pid(ctx)) is not None:
        print(f"runner already running (pid {pid})")
        return
    ctx.runner_log.parent.mkdir(parents=True, exist_ok=True)
    with open(ctx.runner_log, "a") as fh:
        p = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--root", str(ctx.root),
                              "--log-root", str(ctx.log_root), "runner"],
                             cwd=ctx.root, stdout=fh, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                             start_new_session=True)
    print(f"runner started (pid {p.pid}, log {ctx.runner_log})")


def run_runner(ctx: Ctx) -> int:
    stop = False

    def on_term(*_: Any) -> None:
        nonlocal stop
        stop = True

    signal.signal(signal.SIGTERM, on_term)
    ctx.qdir.mkdir(parents=True, exist_ok=True)
    ctx.pid_file.write_text(f"{os.getpid()}\n")

    def say(msg: str) -> None:
        print(f"{fmt(now_iso())} {msg}", flush=True)

    say("runner started")
    try:
        while not stop:
            with locked(ctx):
                st = load(ctx)
                msgs = tick(ctx, st)
                save(ctx, st)
                render(ctx, st)
                done = not running(st) and (not st["queue"] or st["paused"])
            for m in msgs:
                say(m)
            if done:
                say("paused with nothing running; runner exiting" if st["paused"]
                    else "nothing queued or running; runner exiting")
                break
            for _ in range(TICK_SECS):
                if stop:
                    break
                time.sleep(1)
    finally:
        if ctx.pid_file.is_file() and ctx.pid_file.read_text().strip() == str(os.getpid()):
            ctx.pid_file.unlink()
        say("runner stopped")
    return 0


# ---------- commands ----------

def same_tree(a: Path, b: Path) -> bool:
    def files(p: Path) -> set[Path]:
        return {f.relative_to(p) for f in p.rglob("*") if f.is_file()}
    fa = files(a)
    return fa == files(b) and all(filecmp.cmp(a / f, b / f, shallow=False) for f in fa)


def cmd_add(ctx: Ctx, paths: list[str], start: bool = True) -> int:
    rc, queued = 0, 0
    for raw in paths:
        src = Path(raw).expanduser()
        if not src.is_absolute() and not src.exists():
            src = ctx.tasks_input / raw
        if not (src / "task.toml").is_file():
            print(f"skip {raw}: no task.toml there")
            rc = 1
            continue
        src = src.resolve()
        name, dst = src.name, ctx.tasks_input / src.name
        updated = False
        busy = load(ctx)
        if any(q["task"] == name for q in busy["queue"]) or any(r["task"] == name for r in running(busy)):
            print(f"skip {name}: already queued or running; Tasks_INPUT copy left untouched")
            rc = 1
            continue
        if src != dst.resolve():
            if dst.exists():
                if same_tree(src, dst):
                    print(f"{name}: Tasks_INPUT copy already identical, reusing it")
                else:
                    archive = ctx.qdir / "task-archive" / f"{name}-{datetime.now().strftime('%Y%m%dT%H%M%S')}"
                    archive.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(dst), str(archive))
                    shutil.copytree(src, dst, symlinks=True)
                    updated = True
                    print(f"{name}: differs from the Tasks_INPUT copy; replaced it with {src} "
                          f"(old copy in {rel(ctx, archive)})")
            else:
                ctx.tasks_input.mkdir(parents=True, exist_ok=True)
                shutil.copytree(src, dst, symlinks=True)
                print(f"{name}: copied to Tasks_INPUT/{name}")
        with locked(ctx):
            st = load(ctx)
            if any(q["task"] == name for q in st["queue"]) or any(r["task"] == name for r in running(st)):
                print(f"skip {name}: already queued or running")
                rc = 1
                continue
            prior = [r["source"] for r in st["runs"] if r["task"] == name]
            source = prior[-1] if src == dst.resolve() and prior else str(src)
            st["queue"].append({"task": name, "source": source, "added_at": now_iso(),
                                "attempt": next_attempt(st, name), "task_updated": updated})
            save(ctx, st)
            render(ctx, st)
            print(f"{name}: queued at position {len(st['queue'])}")
            queued += 1
    if start and queued:
        ensure_runner(ctx)
    return rc


def cmd_status(ctx: Ctx) -> int:
    st = load(ctx)
    pid = runner_pid(ctx)
    print(f"runner: {'running (pid %d)' % pid if pid else 'stopped'}   max concurrent: {st['max_concurrent']}")
    if st["paused"]:
        print(f"PAUSED: {st['pause_reason']}")
    hold = auto_hold(ctx)
    if hold:
        print(f"AUTO HOLD (no launch from the queue): {hold}")
    now = time.time()
    for r in running(st):
        reqs, non200 = request_counts(log_text(r))
        log = Path(r["log"])
        idle = int((now - log.stat().st_mtime) // 60) if log.is_file() else -1
        alive = "alive" if pid_alive(r["pid"]) else "exited (not yet recorded)"
        print(f"RUNNING  {r['task']}  attempt {r['attempt']}  since {fmt(r['started_at'])}  "
              f"{int((now - ts(r['started_at'])) // 60)} min  requests {reqs} (non-200 {non200})  "
              f"log idle {idle} min  {alive}\n         log {r['log']}")
    for i, q in enumerate(st["queue"], 1):
        print(f"QUEUED   #{i} {q['task']}  attempt {q['attempt']}")
    for r in [r for r in st["runs"] if r["status"] != "RUNNING"][-5:]:
        print(f"{r['status']:<8} {r['task']}  attempt {r['attempt']}  finished {fmt(r.get('finished_at'))}  "
              f"combined {_cell(r.get('combined'))}  tests {_cell(r.get('tests_pct'))}%  "
              f"rubric {_cell(r.get('rubric_pct'))}%  {r.get('note') or ''}".rstrip())
    return 0


def cmd_scores(ctx: Ctx) -> int:
    rows = latest_scores(load(ctx))
    w = max([len(x["task"]) for x in rows] + [4])
    print(f"{'task':<{w}}  att  combined  tests%  rubric%  passed  prev   change")
    for x in rows:
        ch = "-" if x["change"] is None else f"{x['change']:+}"
        print(f"{x['task']:<{w}}  {x['attempt']:<3}  {_cell(x['combined']):<8}  {_cell(x['tests_pct']):<6}  "
              f"{_cell(x['rubric_pct']):<7}  {x['passed']:<6}  {_cell(x['prev']):<5}  {ch}"
              + ("  (fixed task)" if x["updated"] else ""))
    return 0


def cmd_cancel(ctx: Ctx, task: str) -> int:
    with locked(ctx):
        st = load(ctx)
        before = len(st["queue"])
        st["queue"] = [q for q in st["queue"] if q["task"] != task]
        hit = before != len(st["queue"])
        for r in running(st):
            if r["task"] == task:
                removed = kill_run(ctx, r)
                r.update(status="STOPPED", finished_at=now_iso(),
                         note=f"cancelled by operator; removed {len(removed)} docker objects; job folder kept")
                hit = True
        save(ctx, st)
        render(ctx, st)
    print(f"{task}: {'cancelled' if hit else 'not queued or running'}")
    return 0 if hit else 1


def cmd_set(ctx: Ctx, **changes: Any) -> State:
    with locked(ctx):
        st = load(ctx)
        st.update(changes)
        save(ctx, st)
        render(ctx, st)
    return st


def cmd_dry_run(ctx: Ctx, task: str) -> int:
    if not (ctx.tasks_input / task / "task.toml").is_file():
        print(f"Tasks_INPUT/{task} is missing")
        return 1
    d = ctx.log_root / "master-queue" / f"dryrun-{task}-{datetime.now().strftime('%Y%m%dT%H%M%S')}"
    d.mkdir(parents=True, exist_ok=True)
    d.chmod(0o700)
    try:
        staged = stage_task(ctx.tasks_input / task, d / "staged")
        p = subprocess.run([*wrapper_argv(d / "jobs", staged), "--dry-run"], cwd=ctx.root,
                           stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           text=True, timeout=600)
        out, rc = p.stdout, p.returncode
    except (RuntimeError, OSError, subprocess.SubprocessError) as e:
        out, rc = f"[master_queue] dry run failed: {e}\n", 1
    finally:
        shutil.rmtree(d / "staged", ignore_errors=True)
        shutil.rmtree(d / "jobs", ignore_errors=True)
    out = ANSI.sub("", out)
    for pat, repl in REDACT:
        out = pat.sub(repl, out)
    log = d / "dry-run.log"
    log.write_text(out)
    print(out, end="")
    print(f"dry run exit {rc}, log {log}")
    return rc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", type=Path, default=ROOT, help=argparse.SUPPRESS)
    ap.add_argument("--log-root", type=Path, default=LOG_ROOT, help=argparse.SUPPRESS)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_add = sub.add_parser("add", help="copy tasks into Tasks_INPUT and queue them")
    p_add.add_argument("paths", nargs="+")
    sub.add_parser("status", help="show running, queued and recent runs")
    sub.add_parser("start", help="start the runner if it is not running")
    sub.add_parser("stop", help="stop the runner (runs already going keep going)")
    sub.add_parser("resume", help="clear a pause and start the runner")
    p_pause = sub.add_parser("pause", help="pause the queue (running runs keep going); used by auto.py on LIMIT")
    p_pause.add_argument("reason", nargs="?", default="paused by operator")
    p_cancel = sub.add_parser("cancel", help="drop a queued task or stop a running one")
    p_cancel.add_argument("task")
    p_max = sub.add_parser("set-max", help="set the maximum number of concurrent runs")
    p_max.add_argument("n", type=int, choices=range(1, 9))
    sub.add_parser("render", help="re-render the ledger from state")
    sub.add_parser("scores", help="latest combined, tests and rubric score per task")
    p_ref = sub.add_parser("refinalize", help="run the harness finalize steps again for a finished run")
    p_ref.add_argument("task")
    p_dry = sub.add_parser("dry-run", help="wrapper --dry-run for a Tasks_INPUT task; no agent runs, no state change")
    p_dry.add_argument("task")
    sub.add_parser("runner", help=argparse.SUPPRESS)
    a = ap.parse_args(argv)
    ctx = Ctx(root=a.root.resolve(), log_root=a.log_root)
    if a.cmd == "dry-run":
        return cmd_dry_run(ctx, a.task)

    if a.cmd == "add":
        return cmd_add(ctx, a.paths)
    if a.cmd == "status":
        return cmd_status(ctx)
    if a.cmd == "start":
        ensure_runner(ctx)
        return 0
    if a.cmd == "stop":
        pid = runner_pid(ctx)
        if pid:
            os.kill(pid, signal.SIGTERM)
        print(f"runner {'stopping (pid %d)' % pid if pid else 'was not running'}; runs already going keep going")
        return 0
    if a.cmd == "pause":
        cmd_set(ctx, paused=True, pause_reason=a.reason, pause_task="")
        print(f"queue paused: {a.reason}")
        return 0
    if a.cmd == "resume":
        cmd_set(ctx, paused=False, pause_reason="", pause_task="")
        ensure_runner(ctx)
        return 0
    if a.cmd == "cancel":
        return cmd_cancel(ctx, a.task)
    if a.cmd == "set-max":
        cmd_set(ctx, max_concurrent=a.n)
        print(f"max concurrent set to {a.n}")
        return 0
    if a.cmd == "refinalize":
        with locked(ctx):
            st = load(ctx)
            runs = [r for r in st["runs"] if r["task"] == a.task and r["status"] != "RUNNING"]
            if not runs:
                print(f"{a.task}: no finished run recorded")
                return 1
            if runs[-1].get("route") == ROUTE:
                print(f"{a.task}: refinalize runs the Kiro finalize steps; a route B run is "
                      "diagnosed and re-packaged by hand (route B guide 5a/6)")
                return 1
            print(refinalize(ctx, runs[-1], st))
            save(ctx, st)
            render(ctx, st)
        return 0
    if a.cmd == "scores":
        return cmd_scores(ctx)
    if a.cmd == "render":
        with locked(ctx):
            render(ctx, load(ctx))
        return 0
    return run_runner(ctx)


if __name__ == "__main__":
    sys.exit(main())
