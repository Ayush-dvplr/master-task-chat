#!/usr/bin/env python3
"""Is there room in Docker for one more job?  (min plan D-1, Ayush 31 Oct: headroom 3 GiB)

  dockfree.py --need-mb N [--cpus C]

FREE_MB = Docker VM memory - 3072 MiB headroom - the memory limits of all running containers
(a container with no limit counts as 4096 MiB). START=yes when FREE_MB >= N and the running
containers' CPU limits + C stay <= 12 (soft CPU check; Docker has 8 vCPUs, CFS limits overcommit
fine up to this point). Harbor sets each container's limit from task.toml memory_mb/cpus, so
this sees QC gates, paid runs and worker `docker run --memory` jobs alike.

Prints:  FREE_MB=<n> USED_MB=<n> CONTAINERS=<n> CPUS=<used>/<cap> START=yes|no
Exit: 0 start, 1 no room, 2 Docker unreachable.
DOCKFREE_FAKE=<json file> replaces the docker calls (tests): {"total": bytes, "containers": [{"mem": bytes, "cpus": n}]}
"""
import argparse
import json
import os
import subprocess
import sys

HEADROOM_MB = 3072
NO_LIMIT_MB = 4096
CPU_CAP = 12
MIB = 1024 * 1024


def docker(*args):
    return subprocess.run(["docker", *args], capture_output=True, text=True, timeout=30)


def read_state():
    """(total_bytes, [(mem_bytes, cpus)]) or None when Docker can't be asked."""
    fake = os.environ.get("DOCKFREE_FAKE")
    if fake:
        d = json.loads(open(fake).read())
        return d["total"], [(c.get("mem", 0), c.get("cpus", 0)) for c in d["containers"]]
    try:
        info = docker("info", "--format", "{{.MemTotal}}")
        ids = docker("ps", "-q")
    except (OSError, subprocess.TimeoutExpired):
        return None
    if info.returncode or ids.returncode or not info.stdout.strip().isdigit():
        return None
    out = []
    id_list = ids.stdout.split()
    if id_list:
        ins = docker("inspect", "--format", "{{.HostConfig.Memory}} {{.HostConfig.NanoCpus}}", *id_list)
        if ins.returncode:
            return None
        for line in ins.stdout.split("\n"):
            if line.strip():
                mem, nano = line.split()
                out.append((int(mem), int(nano) / 1e9))
    return int(info.stdout.strip()), out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--need-mb", type=int, required=True)
    ap.add_argument("--cpus", type=float, default=2)
    a = ap.parse_args()
    st = read_state()
    if st is None:
        print("DOCKER=unreachable START=no")
        sys.exit(2)
    total, conts = st
    used = sum((m // MIB) if m > 0 else NO_LIMIT_MB for m, _ in conts)
    cpus = sum(c if c > 0 else 2 for _, c in conts)
    free = total // MIB - HEADROOM_MB - used
    ok = free >= a.need_mb and cpus + a.cpus <= CPU_CAP
    print(f"FREE_MB={free} USED_MB={used} CONTAINERS={len(conts)} CPUS={cpus:g}/{CPU_CAP} "
          f"START={'yes' if ok else 'no'}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
