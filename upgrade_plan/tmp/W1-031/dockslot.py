#!/usr/bin/env python3
"""dockslot: Docker room manager for many worker sessions (S1 draft, W1-031, 3 Nov 2026).

  dockslot.py status [--json]
  dockslot.py acquire --kind K [--mb N] [--cpus N] [--owner-pid P] [--ticket T] [--wait-max S]
  dockslot.py release LEASE
  dockslot.py run --kind K [--mb N] [--cpus N] -- <command ...>
  dockslot.py daemon [--once]          refresh measured room, free dead leases, write status.json
  dockslot.py stop                     stop the daemon (never touches leases or containers)
  dockslot.py hold REASON | unhold     no new grants while held (running jobs go on)
  dockslot.py peaks --minutes M [--csv FILE]   read only peak memory and CPU per container

Global flags (before the subcommand): --settings FILE (or DOCKSLOT_SETTINGS), --state-dir DIR
(or DOCKSLOT_DIR), --fake-capacity "vm_mb=N,cpus=N" (or DOCKSLOT_FAKE; no docker or ps calls).

Room = Docker VM memory - headroom - max(reservation, measured use) per lease - foreign use.
New grants stop while the Mac itself is short of memory (free percent, swap, orphan solvers).
Waiters are served paid first, then oldest first; a waiter that does not fit blocks the
ones behind it, so a big job is never starved by small ones.

This script never calls docker rm, docker kill, docker stop, docker system prune or harbor
delete, and never signals any process except its own daemon. A dead lease is only freed and
reported; a long job is only reported.
Exit codes: 0 ok, 1 not found or refused, 2 bad use, 3 acquire waited --wait-max and gave up.
"""
import argparse
import errno
import fcntl
import json
import os
import platform
import re
import select
import signal
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path

DEFAULTS = {
    "state_dir": "~/.local/state/dockslot",
    "headroom_mb": 3072,
    "cpu_cap": 12,
    "fallback_vm_mb": 15970,
    "fallback_vm_cpus": 8,
    "refresh_s": 5,
    "measure_max_age_s": 10,
    "dead_grace_s": 120,
    "kinds": {
        "kill": {"mb": 4096, "cpus": 2, "priority": 1, "long_h": 1},
        "oracle": {"mb": 2048, "cpus": 1, "priority": 1, "long_h": 2, "fast": True},
        "nop": {"mb": 2048, "cpus": 1, "priority": 1, "long_h": 2, "fast": True},
        "paid": {"mb": 8192, "cpus": 4, "priority": 0, "long_h": 6, "max_running": 2},
    },
    "host": {"min_free_pct": 15, "max_swap_mb": 8192, "orphan_rss_mb": 2048, "orphan_hold_mb": 8192,
             "orphan_names": ["python", "Python", "node", "java", "perl", "ruby", "pypy"],
             "big_rss_mb": 4096},
}
UNITS = {"b": 1, "kb": 1e3, "kib": 1024, "mb": 1e6, "mib": 1024 ** 2, "gb": 1e9, "gib": 1024 ** 3,
         "tb": 1e12, "tib": 1024 ** 4}
MIB = 1024 * 1024


def merge(base, extra):
    out = dict(base)
    for k, v in (extra or {}).items():
        out[k] = merge(base[k], v) if isinstance(v, dict) and isinstance(base.get(k), dict) else v
    return out


class Ctx:
    def __init__(self, a):
        path = a.settings or os.environ.get("DOCKSLOT_SETTINGS") or str(Path(__file__).resolve().parent.parent / "settings.json")
        raw = {}
        if Path(path).is_file():
            raw = json.loads(Path(path).read_text())
        self.settings_path = path if raw else None
        self.s = merge(DEFAULTS, raw.get("docker", {}))
        limits = raw.get("limits", {})
        if "harness" in limits:  # R21/R22: one source for the paid run cap
            self.s["kinds"]["paid"]["max_running"] = int(limits["harness"])
        self.dir = Path(os.path.expanduser(a.state_dir or os.environ.get("DOCKSLOT_DIR") or self.s["state_dir"]))
        for sub in ("leases", "waiters"):
            (self.dir / sub).mkdir(parents=True, exist_ok=True)
        fake = a.fake_capacity or os.environ.get("DOCKSLOT_FAKE")
        self.fake = None
        if fake:
            kv = dict(p.split("=", 1) for p in fake.split(",") if "=" in p)
            self.fake = {"vm_mb": int(kv.get("vm_mb", self.s["fallback_vm_mb"])),
                         "cpus": float(kv.get("cpus", self.s["fallback_vm_cpus"]))}

    def kind(self, name):
        if name not in self.s["kinds"]:
            raise SystemExit(f"unknown kind {name!r}; known: {', '.join(self.s['kinds'])}")
        return self.s["kinds"][name]


# ---------- small file helpers ----------

def write_json(path, data):
    tmp = path.with_name(path.name + f".tmp{os.getpid()}")
    tmp.write_text(json.dumps(data, indent=1, sort_keys=True))
    os.replace(tmp, path)


def read_json(path):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


@contextmanager
def locked(ctx):
    fd = os.open(ctx.dir / "lock", os.O_RDWR | os.O_CREAT, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def event(ctx, kind, text, **extra):
    rec = {"t": time.strftime("%Y-%m-%d %H:%M:%S"), "event": kind, "text": text, **extra}
    with open(ctx.dir / "events.log", "a") as f:
        f.write(json.dumps(rec) + "\n")
    print(f"dockslot {kind}: {text}", file=sys.stderr)


def last_events(ctx, n=6):
    try:
        lines = (ctx.dir / "events.log").read_text().splitlines()[-n:]
    except OSError:
        return []
    return [json.loads(x) for x in lines if x.strip()]


def pid_alive(pid):
    if not pid:
        return False
    try:
        os.kill(int(pid), 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def leases(ctx):
    return [d for d in (read_json(p) for p in sorted((ctx.dir / "leases").glob("*.json"))) if d]


def waiters(ctx):
    ws = [d for d in (read_json(p) for p in sorted((ctx.dir / "waiters").glob("*.json"))) if d]
    return sorted(ws, key=lambda w: (w["priority"], w["created"]))


def wake(ctx, wid):
    fifo = ctx.dir / "waiters" / f"{wid}.fifo"
    try:
        fd = os.open(fifo, os.O_WRONLY | os.O_NONBLOCK)
    except OSError:
        return  # no reader (waiter gone) or no fifo
    try:
        os.write(fd, b"x")
    except OSError:
        pass
    finally:
        os.close(fd)


# ---------- measuring ----------

def run_cmd(args, timeout=20):
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r.stdout if r.returncode == 0 else None


def to_mb(text):
    m = re.match(r"\s*([\d.]+)\s*([A-Za-z]*)", text or "")
    if not m:
        return 0.0
    return float(m.group(1)) * UNITS.get(m.group(2).lower() or "b", 1) / MIB


def measure_docker():
    info = run_cmd(["docker", "info", "--format", "{{.MemTotal}} {{.NCPU}}"])
    if not info or len(info.split()) != 2:
        return None
    total, ncpu = info.split()
    labels = {}
    ps = run_cmd(["docker", "ps", "--no-trunc", "--format", '{{.ID}}\t{{.Label "dockslot.lease"}}\t{{.Names}}'])
    for line in (ps or "").splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            labels[parts[0][:12]] = parts[1].strip()
    conts = []
    st = run_cmd(["docker", "stats", "--no-stream", "--format", "{{.ID}}\t{{.Name}}\t{{.MemUsage}}\t{{.CPUPerc}}"], timeout=40)
    for line in (st or "").splitlines():
        parts = line.split("\t")
        if len(parts) < 4:
            continue
        cid, name, mem, cpu = parts[:4]
        conts.append({"id": cid[:12], "name": name, "mem_mb": round(to_mb(mem.split("/")[0])),
                      "cpu_pct": float(cpu.strip().rstrip("%") or 0), "lease": labels.get(cid[:12], "")})
    return {"vm_mb": int(total) // MIB, "vm_cpus": int(ncpu), "containers": conts}


def measure_host(ctx):
    h = ctx.s["host"]
    out = {"free_pct": None, "swap_used_mb": None, "orphans": [], "big": []}
    if platform.system() == "Darwin":
        lvl = run_cmd(["sysctl", "-n", "kern.memorystatus_level"])
        if lvl and lvl.strip().isdigit():
            out["free_pct"] = int(lvl.strip())
        sw = run_cmd(["sysctl", "-n", "vm.swapusage"])
        m = re.search(r"used\s*=\s*([\d.]+)([MG])", sw or "")
        if m:
            out["swap_used_mb"] = round(float(m.group(1)) * (1024 if m.group(2) == "G" else 1))
    else:
        try:
            mi = dict((l.split(":")[0], int(l.split()[1])) for l in open("/proc/meminfo") if len(l.split()) >= 2)
            out["free_pct"] = round(100 * mi["MemAvailable"] / mi["MemTotal"])
            out["swap_used_mb"] = (mi.get("SwapTotal", 0) - mi.get("SwapFree", 0)) // 1024
        except (OSError, KeyError, ValueError):
            pass
    ps = run_cmd(["ps", "-axo", "pid=,ppid=,rss=,etime=,comm="])
    for line in (ps or "").splitlines():
        parts = line.split(None, 4)
        if len(parts) < 5 or not parts[2].isdigit():
            continue
        pid, ppid, rss_kb, etime, comm = parts
        rss_mb = int(rss_kb) // 1024
        name = os.path.basename(comm.strip())
        rec = {"pid": int(pid), "ppid": int(ppid), "rss_mb": rss_mb, "etime": etime, "name": name}
        if rss_mb >= h["orphan_rss_mb"] and int(ppid) == 1 and any(n in name for n in h["orphan_names"]):
            out["orphans"].append(rec)
        elif rss_mb >= h["big_rss_mb"]:
            out["big"].append(rec)
    return out


def measure(ctx):
    if ctx.fake:
        return {"time": time.time(), "source": "fake", "vm_mb": ctx.fake["vm_mb"], "vm_cpus": ctx.fake["cpus"],
                "containers": [], "host": {"free_pct": None, "swap_used_mb": None, "orphans": [], "big": []}}
    d = measure_docker()
    host = measure_host(ctx)
    if d is None:
        return {"time": time.time(), "source": "settings (docker unreachable)", "vm_mb": ctx.s["fallback_vm_mb"],
                "vm_cpus": ctx.s["fallback_vm_cpus"], "containers": [], "host": host}
    return {"time": time.time(), "source": "docker", **d, "host": host}


def get_measure(ctx, force=False):
    path = ctx.dir / "measure.json"
    m = read_json(path)
    if force or not m or time.time() - m.get("time", 0) > ctx.s["measure_max_age_s"] or \
            (m.get("source") == "fake") != bool(ctx.fake):
        m = measure(ctx)
        write_json(path, m)
    return m


def room(ctx, m, ls):
    """Free memory and CPU now, and the reasons new grants are held."""
    by_lease, unlabeled = {}, 0
    ids = {l["id"] for l in ls}
    for c in m["containers"]:
        if c.get("lease") in ids:
            by_lease[c["lease"]] = by_lease.get(c["lease"], 0) + c["mem_mb"]
        else:
            unlabeled += c["mem_mb"]
    reserved = sum(l["mb"] for l in ls)
    res_unlabeled = sum(l["mb"] for l in ls if l["id"] not in by_lease)
    foreign = max(0, unlabeled - res_unlabeled)  # use beyond what unlabeled leases reserved
    used = sum(max(l["mb"], by_lease.get(l["id"], 0)) for l in ls) + foreign
    cap_mb = m["vm_mb"] - ctx.s["headroom_mb"]
    cpu_cap = ctx.s["cpu_cap"] or m["vm_cpus"] * 1.5
    h, hs = m["host"], ctx.s["host"]
    hold = []
    manual = read_json(ctx.dir / "hold.json")
    if manual:
        hold.append(f"manual: {manual.get('reason', '')}")
    if h["free_pct"] is not None and h["free_pct"] < hs["min_free_pct"]:
        hold.append(f"host free {h['free_pct']}% < {hs['min_free_pct']}%")
    if h["swap_used_mb"] is not None and h["swap_used_mb"] > hs["max_swap_mb"]:
        hold.append(f"host swap {h['swap_used_mb']} MB > {hs['max_swap_mb']} MB")
    orphan_mb = sum(o["rss_mb"] for o in h["orphans"])
    if orphan_mb >= hs["orphan_hold_mb"]:
        hold.append(f"orphan host processes hold {orphan_mb} MB")
    return {"cap_mb": cap_mb, "reserved_mb": reserved, "measured_mb": sum(c["mem_mb"] for c in m["containers"]),
            "foreign_mb": foreign, "used_mb": used, "free_mb": cap_mb - used,
            "cpus_used": sum(l["cpus"] for l in ls), "cpu_cap": cpu_cap, "hold": hold}


# ---------- core: clean and schedule (call with the lock held) ----------

def clean_dead(ctx, m):
    now = time.time()
    running_labels = {c.get("lease") for c in m["containers"] if c.get("lease")}
    for l in leases(ctx):
        path = ctx.dir / "leases" / f"{l['id']}.json"
        changed = False
        if pid_alive(l["pid"]):
            if l.pop("dead_seen", None):
                changed = True
        elif l["id"] in running_labels:
            if not l.get("orphan_reported"):
                l["orphan_reported"] = now
                changed = True
                event(ctx, "OWNER_GONE", f"lease {l['id']} owner pid {l['pid']} gone but its container still runs; lease kept, nothing stopped")
        else:
            if "dead_seen" not in l:
                l["dead_seen"] = now
                changed = True
            elif now - l["dead_seen"] >= ctx.s["dead_grace_s"]:
                path.unlink(missing_ok=True)
                event(ctx, "FREED", f"dead lease {l['id']} ({l['kind']}, {l['mb']} MB) freed: owner pid {l['pid']} gone, "
                      "no container with its label; nothing was stopped", lease=l["id"])
                continue
        long_h = ctx.kind(l["kind"]).get("long_h", 3) if l["kind"] in ctx.s["kinds"] else 3
        if now - l["granted"] > long_h * 3600 and not l.get("long_reported"):
            l["long_reported"] = now
            changed = True
            event(ctx, "LONG", f"lease {l['id']} ({l['kind']}) running {(now - l['granted']) / 3600:.1f} h > {long_h} h; reported only")
        if changed:
            write_json(path, l)
    for w in waiters(ctx):
        if not pid_alive(w["waiter_pid"]) and now - w["touched"] >= ctx.s["dead_grace_s"]:
            (ctx.dir / "waiters" / f"{w['id']}.json").unlink(missing_ok=True)
            (ctx.dir / "waiters" / f"{w['id']}.fifo").unlink(missing_ok=True)
            event(ctx, "WAITER_GONE", f"waiter {w['id']} (pid {w['waiter_pid']}) gone; removed from queue")


def schedule(ctx, force_measure=False):
    m = get_measure(ctx, force_measure)
    clean_dead(ctx, m)
    ls = leases(ctx)
    r = room(ctx, m, ls)
    if r["hold"]:
        return m, r
    free, cpus = r["free_mb"], r["cpus_used"]
    running = {}
    for l in ls:
        running[l["kind"]] = running.get(l["kind"], 0) + 1
    blocked = None  # first waiter that does not fit (head of line)
    fast_max = ctx.s.get("fast_max_running", 4)
    starve_s = ctx.s.get("fast_starve_s", 300)
    for w in waiters(ctx):
        k = ctx.kind(w["kind"])
        if running.get(w["kind"], 0) >= k.get("max_running", 10 ** 6):
            continue  # waits for its own kind's slot; does not block other kinds
        if blocked is not None:
            # Fast lane (Ayush, ENTRY 68): short QC oracle and nop jobs may pass a blocked big job
            # while they fit, at most fast_max_running at once, and only until the blocked job
            # has waited fast_starve_s, so a big job is never starved.
            fast_now = sum(n for kn, n in running.items() if ctx.s["kinds"].get(kn, {}).get("fast"))
            if not k.get("fast") or fast_now >= fast_max or time.time() - blocked["created"] >= starve_s:
                continue
        if w["mb"] > free or cpus + w["cpus"] > r["cpu_cap"]:
            if blocked is None:
                blocked = w
            continue
        lease = {"id": w["id"], "kind": w["kind"], "mb": w["mb"], "cpus": w["cpus"], "pid": w["owner_pid"],
                 "note": w.get("note", ""), "created": w["created"], "granted": time.time()}
        write_json(ctx.dir / "leases" / f"{w['id']}.json", lease)
        (ctx.dir / "waiters" / f"{w['id']}.json").unlink(missing_ok=True)
        free -= w["mb"]
        cpus += w["cpus"]
        running[w["kind"]] = running.get(w["kind"], 0) + 1
        event(ctx, "GRANT", f"{w['id']} {w['kind']} {w['mb']} MB {w['cpus']:g} cpus after {time.time() - w['created']:.0f} s wait",
              lease=w["id"])
        wake(ctx, w["id"])
    return m, room(ctx, m, leases(ctx))


def snapshot(ctx, m, r):
    now = time.time()
    ls, ws = leases(ctx), waiters(ctx)
    dpid = read_json(ctx.dir / "daemon.json") or {}
    st = {
        "time": time.strftime("%Y-%m-%d %H:%M:%S"), "source": m["source"], "vm_mb": m["vm_mb"], "vm_cpus": m["vm_cpus"],
        "headroom_mb": ctx.s["headroom_mb"], **r,
        "leases": [{"id": l["id"], "kind": l["kind"], "mb": l["mb"], "cpus": l["cpus"], "pid": l["pid"],
                    "owner_alive": pid_alive(l["pid"]), "age_min": round((now - l["granted"]) / 60, 1),
                    "long": bool(l.get("long_reported")), "note": l.get("note", "")} for l in ls],
        "waiters": [{"id": w["id"], "kind": w["kind"], "mb": w["mb"], "cpus": w["cpus"], "pos": i + 1,
                     "wait_min": round((now - w["created"]) / 60, 1)} for i, w in enumerate(ws)],
        "containers": m["containers"], "host": m["host"],
        "idle": not ls and not ws and not m["containers"],
        "daemon": "running" if pid_alive(dpid.get("pid")) else "stopped",
        "settings": ctx.settings_path or "defaults",
        "events": last_events(ctx),
    }
    write_json(ctx.dir / "status.json", st)
    return st


# ---------- commands ----------

def cmd_status(ctx, a):
    with locked(ctx):
        m, r = schedule(ctx)
        st = snapshot(ctx, m, r)
    if a.json:
        print(json.dumps(st, indent=1))
        return 0
    print(f"DOCKSLOT source={st['source']} vm={st['vm_mb']}MB cap={st['cap_mb']}MB used={st['used_mb']}MB "
          f"(reserved {st['reserved_mb']}, measured {st['measured_mb']}, foreign {st['foreign_mb']}) "
          f"free={st['free_mb']}MB cpus={st['cpus_used']:g}/{st['cpu_cap']:g} "
          f"hold={'; '.join(st['hold']) or 'no'} leases={len(st['leases'])} waiters={len(st['waiters'])} "
          f"idle={'yes' if st['idle'] else 'no'} daemon={st['daemon']}")
    for l in st["leases"]:
        print(f"  LEASE {l['id']} {l['kind']} {l['mb']}MB {l['cpus']:g}cpu pid={l['pid']}"
              f"{'' if l['owner_alive'] else ' OWNER-GONE'} age={l['age_min']}min{' LONG' if l['long'] else ''}")
    for w in st["waiters"]:
        print(f"  WAIT  #{w['pos']} {w['id']} {w['kind']} {w['mb']}MB waiting {w['wait_min']}min")
    h = st["host"]
    if h["free_pct"] is not None:
        print(f"  HOST free={h['free_pct']}% swap_used={h['swap_used_mb']}MB")
    for o in h["orphans"]:
        print(f"  ORPHAN? pid={o['pid']} {o['name']} {o['rss_mb']}MB up {o['etime']} (ppid 1; not killed, check it)")
    for b in h["big"]:
        print(f"  BIG   pid={b['pid']} {b['name']} {b['rss_mb']}MB up {b['etime']}")
    return 0


def safe_id(text):
    return re.sub(r"[^A-Za-z0-9_.-]", "_", text)[:60]


def acquire(ctx, kind, mb, cpus, owner_pid, ticket=None, wait_max=None, note=""):
    k = ctx.kind(kind)
    mb = int(mb or k["mb"])
    cpus = float(cpus or k["cpus"])
    wid = safe_id(ticket) if ticket else f"{kind}-{time.strftime('%m%d-%H%M%S')}-{os.getpid()}"
    wdir = ctx.dir / "waiters"
    fifo = wdir / f"{wid}.fifo"
    with locked(ctx):
        if (ctx.dir / "leases" / f"{wid}.json").exists():
            return wid  # ticket re-call after a grant
        old = read_json(wdir / f"{wid}.json") or {}
        now = time.time()
        write_json(wdir / f"{wid}.json", {"id": wid, "kind": kind, "mb": mb, "cpus": cpus, "owner_pid": owner_pid,
                                          "waiter_pid": os.getpid(), "priority": k.get("priority", 1),
                                          "created": old.get("created", now), "touched": now, "note": note})
        if not fifo.exists():
            os.mkfifo(fifo)
    rfd = os.open(fifo, os.O_RDONLY | os.O_NONBLOCK)
    wfd = os.open(fifo, os.O_WRONLY | os.O_NONBLOCK)  # keeps a writer so select never sees EOF
    deadline = None if wait_max is None else time.time() + wait_max
    said = False
    try:
        while True:
            with locked(ctx):
                m, r = schedule(ctx)
                if (ctx.dir / "leases" / f"{wid}.json").exists():
                    return wid
                ws = waiters(ctx)
                pos = next((i + 1 for i, w in enumerate(ws) if w["id"] == wid), "?")
                wp = wdir / f"{wid}.json"
                w = read_json(wp)
                if w:
                    w["touched"] = time.time()
                    write_json(wp, w)
            if not said:
                why = "; ".join(r["hold"]) or f"free {r['free_mb']} MB"
                print(f"WAITING {wid} position {pos} of {len(ws)}, need {mb} MB ({why})", file=sys.stderr)
                said = True
            left = ctx.s["refresh_s"] if deadline is None else min(ctx.s["refresh_s"], deadline - time.time())
            if left <= 0:
                if not ticket:
                    with locked(ctx):
                        (wdir / f"{wid}.json").unlink(missing_ok=True)
                return None
            ready, _, _ = select.select([rfd], [], [], left)
            if ready:
                try:
                    os.read(rfd, 4096)
                except OSError as e:
                    if e.errno != errno.EAGAIN:
                        raise
    except BaseException:
        with locked(ctx):
            (wdir / f"{wid}.json").unlink(missing_ok=True)
        raise
    finally:
        os.close(rfd)
        os.close(wfd)
        fifo.unlink(missing_ok=True)


def release(ctx, lid):
    with locked(ctx):
        p = ctx.dir / "leases" / f"{safe_id(lid)}.json"
        l = read_json(p)
        if not l:
            print(f"no lease {lid}", file=sys.stderr)
            return 1
        p.unlink()
        event(ctx, "RELEASE", f"{lid} {l['kind']} after {(time.time() - l['granted']) / 60:.1f} min", lease=lid)
        schedule(ctx)
    return 0


def cmd_acquire(ctx, a):
    lid = acquire(ctx, a.kind, a.mb, a.cpus, a.owner_pid or os.getppid(), a.ticket, a.wait_max, a.note or "")
    if lid is None:
        print("TIMEOUT no lease yet" + (f"; call again with --ticket {a.ticket} to keep the place" if a.ticket else ""))
        return 3
    print(f"LEASE={lid}")
    print(f"docker run hint: --label dockslot.lease={lid}", file=sys.stderr)
    return 0


def cmd_release(ctx, a):
    return release(ctx, a.lease)


def cmd_run(ctx, a):
    cmd = a.command[1:] if a.command and a.command[0] == "--" else a.command
    if not cmd:
        print("run needs a command after --", file=sys.stderr)
        return 2
    lid = acquire(ctx, a.kind, a.mb, a.cpus, os.getpid(), None, None, a.note or " ".join(cmd)[:120])
    env = dict(os.environ, DOCKSLOT_LEASE=lid)
    try:
        child = subprocess.Popen(cmd, env=env)
        while True:
            try:
                return child.wait()
            except KeyboardInterrupt:
                continue  # the job keeps its room until it ends
    finally:
        release(ctx, lid)


def cmd_daemon(ctx, a):
    stop = {"flag": False}
    signal.signal(signal.SIGTERM, lambda *_: stop.update(flag=True))
    if not a.once:
        old = read_json(ctx.dir / "daemon.json") or {}
        if pid_alive(old.get("pid")) and old.get("pid") != os.getpid():
            print(f"daemon already running (pid {old['pid']})")
            return 1
        write_json(ctx.dir / "daemon.json", {"pid": os.getpid(), "started": time.strftime("%Y-%m-%d %H:%M:%S")})
        event(ctx, "DAEMON", f"started pid {os.getpid()}")
    try:
        while True:
            with locked(ctx):
                m, r = schedule(ctx, force_measure=True)
                snapshot(ctx, m, r)
            if a.once or stop["flag"]:
                return 0
            t_end = time.time() + ctx.s["refresh_s"]
            while time.time() < t_end and not stop["flag"]:
                time.sleep(0.5)
            if stop["flag"]:
                return 0
    finally:
        if not a.once:
            (ctx.dir / "daemon.json").unlink(missing_ok=True)
            event(ctx, "DAEMON", f"stopped pid {os.getpid()}")


def cmd_stop(ctx, a):
    d = read_json(ctx.dir / "daemon.json") or {}
    pid = d.get("pid")
    if not pid_alive(pid):
        print("daemon not running")
        (ctx.dir / "daemon.json").unlink(missing_ok=True)
        return 0
    cmdline = run_cmd(["ps", "-o", "command=", "-p", str(pid)]) or ""
    if "dockslot" not in cmdline:
        print(f"pid {pid} is not a dockslot daemon ({cmdline.strip()!r}); not signalled")
        return 1
    os.kill(pid, signal.SIGTERM)
    print(f"daemon pid {pid} asked to stop; leases and containers untouched")
    return 0


def cmd_hold(ctx, a):
    write_json(ctx.dir / "hold.json", {"reason": a.reason, "time": time.strftime("%Y-%m-%d %H:%M:%S")})
    event(ctx, "HOLD", f"new grants held: {a.reason}; running jobs go on")
    return 0


def cmd_unhold(ctx, a):
    with locked(ctx):
        (ctx.dir / "hold.json").unlink(missing_ok=True)
        event(ctx, "UNHOLD", "grants resumed")
        schedule(ctx)
    return 0


def cmd_peaks(ctx, a):
    peaks, end = {}, time.time() + a.minutes * 60
    while time.time() < end:
        d = measure_docker()
        h = measure_host(ctx)
        if d is None:
            print("docker unreachable", file=sys.stderr)
            return 1
        for c in d["containers"]:
            p = peaks.setdefault(c["name"], {"mem_mb": 0, "cpu_pct": 0.0, "first": time.strftime("%H:%M:%S")})
            p["mem_mb"] = max(p["mem_mb"], c["mem_mb"])
            p["cpu_pct"] = max(p["cpu_pct"], c["cpu_pct"])
            p["last"] = time.strftime("%H:%M:%S")
        total = sum(c["mem_mb"] for c in d["containers"])
        peaks.setdefault("_ALL_CONTAINERS", {"mem_mb": 0, "cpu_pct": 0.0, "first": "", "last": ""})
        peaks["_ALL_CONTAINERS"]["mem_mb"] = max(peaks["_ALL_CONTAINERS"]["mem_mb"], total)
        peaks["_ALL_CONTAINERS"]["cpu_pct"] = max(peaks["_ALL_CONTAINERS"]["cpu_pct"], sum(c["cpu_pct"] for c in d["containers"]))
        sw = peaks.setdefault("_HOST_SWAP_USED_MB", {"mem_mb": 0, "cpu_pct": 0.0, "first": "", "last": ""})
        sw["mem_mb"] = max(sw["mem_mb"], h["swap_used_mb"] or 0)
        time.sleep(a.every)
    rows = sorted(peaks.items())
    print(f"{'container':40} {'peak_mem_mb':>11} {'peak_cpu_%':>10} first    last")
    for name, p in rows:
        print(f"{name:40} {p['mem_mb']:>11} {p['cpu_pct']:>10.0f} {p['first']:8} {p['last']}")
    if a.csv:
        with open(a.csv, "w") as f:
            f.write("container,peak_mem_mb,peak_cpu_pct,first,last\n")
            for name, p in rows:
                f.write(f"{name},{p['mem_mb']},{p['cpu_pct']:.0f},{p['first']},{p['last']}\n")
    return 0


def main():
    ap = argparse.ArgumentParser(description="Docker room manager (dockslot)")
    ap.add_argument("--settings")
    ap.add_argument("--state-dir")
    ap.add_argument("--fake-capacity", help='dry mode, e.g. "vm_mb=11264,cpus=8"')
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("status"); p.add_argument("--json", action="store_true"); p.set_defaults(fn=cmd_status)
    for name, fn in (("acquire", cmd_acquire), ("run", cmd_run)):
        p = sub.add_parser(name)
        p.add_argument("--kind", required=True)
        p.add_argument("--mb", type=int)
        p.add_argument("--cpus", type=float)
        p.add_argument("--note")
        if name == "acquire":
            p.add_argument("--owner-pid", type=int, help="process whose life holds the lease (default: parent)")
            p.add_argument("--ticket", help="stable name; a re-call keeps the queue place")
            p.add_argument("--wait-max", type=float, help="seconds; then exit 3")
        else:
            p.add_argument("command", nargs=argparse.REMAINDER)
        p.set_defaults(fn=fn)
    p = sub.add_parser("release"); p.add_argument("lease"); p.set_defaults(fn=cmd_release)
    p = sub.add_parser("daemon"); p.add_argument("--once", action="store_true"); p.set_defaults(fn=cmd_daemon)
    p = sub.add_parser("stop"); p.set_defaults(fn=cmd_stop)
    p = sub.add_parser("hold"); p.add_argument("reason"); p.set_defaults(fn=cmd_hold)
    p = sub.add_parser("unhold"); p.set_defaults(fn=cmd_unhold)
    p = sub.add_parser("peaks"); p.add_argument("--minutes", type=float, default=20)
    p.add_argument("--every", type=float, default=5); p.add_argument("--csv"); p.set_defaults(fn=cmd_peaks)
    a = ap.parse_args()
    ctx = Ctx(a)
    sys.exit(a.fn(ctx, a))


if __name__ == "__main__":
    main()
