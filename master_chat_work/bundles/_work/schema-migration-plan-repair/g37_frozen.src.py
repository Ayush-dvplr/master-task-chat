from __future__ import annotations

import ast
import base64
import copy
import fcntl
import hashlib
import heapq
import json
import os
import random
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import zipfile
import zlib
from collections import defaultdict
from pathlib import Path
from typing import Any

from rewardkit import criteria, criterion

SAMPLE_SEED = 590237
CHALLENGE_SEED = 7715023
EVAL_SEED = 33461789
PACKAGE = "migrakit"
TIME_LIMIT_SEC = 10
APP_ROOT = Path(os.environ.get("APP_ROOT", "/app"))
OUT_DIR = APP_ROOT / "out"
ARTIFACTS = [
    "/app/out/patched-repo.zip",
    "/app/out/repair-report.json",
    "/app/out/module_core.json",
    "/app/out/module_parser.json",
    "/app/out/module_report.json",
    "/app/out/test_fixes.json",
    "/app/out/summary.json",
]
VISIBLE_TESTS = [
    "test_cli_runs_from_other_folder",
    "test_empty_plan_at_target",
    "test_fingerprint_stable",
    "test_module_entry_help",
    "test_one_edge_plan",
    "test_rename_then_cast_execution",
    "test_signature_without_nulls",
    "test_single_hop_alias",
    "test_unknown_schema_code",
]
API_NAMES = [
    "load_contracts", "resolve_partner", "record_fingerprint", "state_signature", "plan_migration",
    "execute_plan", "build_summary", "run_pipeline", "MigrationError",
]
_SETPRIV = ["setpriv", "--reuid=nobody", "--regid=nogroup", "--clear-groups"]
# Each submitted program runs under the agent environment's memory (4,096 MB), so a
# program that outgrows it fails its own check and leaves the rest of the run scored.
MEMORY_LIMIT_BYTES = 4096 << 20
_CAPPED = [
    sys.executable, "-c",
    "import os, resource, sys\n"
    "if sys.platform.startswith('linux'):\n"
    f"    resource.setrlimit(resource.RLIMIT_AS, ({MEMORY_LIMIT_BYTES}, {MEMORY_LIMIT_BYTES}))\n"
    "os.execvp(sys.argv[1], sys.argv[1:])",
]

_SHIPPED_DATA: dict[str, str] = {}
_CACHE: dict[Any, Any] = {}


# ----------------------------------------------------------------------------- sandbox

def _rebuild(prefix: str) -> Path:
    """Write the embedded files under ``prefix`` (ci/ or repo/) into a fresh readable folder."""
    root = Path(tempfile.mkdtemp(prefix=f"shipped-{prefix.strip('/')}-"))
    for rel, blob in _SHIPPED_DATA.items():
        if not rel.startswith(prefix):
            continue
        target = root / rel[len(prefix):]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(zlib.decompress(base64.b64decode(blob)))
        target.chmod(0o644)
    for directory in [root, *(p for p in root.rglob("*") if p.is_dir())]:
        directory.chmod(0o755)
    return root


def _ci_dir() -> Path:
    """The agent's /app/ci, rebuilt here: the verifier container never has it."""
    if "ci" not in _CACHE:
        _CACHE["ci"] = _rebuild("ci/")
    return _CACHE["ci"]


def _root_only_tests_present() -> bool:
    try:
        status = Path("/tests").stat()
    except FileNotFoundError:
        return False
    return status.st_uid == 0 and (status.st_mode & 0o077) == 0


def _grant_read(argument: str) -> None:
    """Make an agent-written path readable before the uid drop.

    Agent editors can leave a program at mode 0600. The checks run programs as
    an unprivileged user, so widening the mode here keeps a correct submission
    from failing for a reason unrelated to the task; it changes no graded content.
    """
    if not argument.startswith("/app"):
        return
    path = Path(argument)
    if not path.exists():
        return
    try:
        path.chmod(path.stat().st_mode | (0o555 if path.is_dir() else 0o444))
        for parent in path.parents:
            parent.chmod(parent.stat().st_mode | 0o555)
            if str(parent) == "/app":
                break
    except OSError:
        pass


def _untrusted_command(command: list[str]) -> list[str]:
    if os.name == "posix" and os.geteuid() != 0 and _root_only_tests_present():
        raise RuntimeError("verifier must run as root to isolate submitted code from /tests")
    if os.name == "posix" and os.geteuid() == 0:
        for argument in command:
            _grant_read(argument)
        return [*_SETPRIV, *command]
    return command


def _scratch(prefix: str) -> Path:
    path = Path(tempfile.mkdtemp(prefix=prefix))
    path.chmod(0o1777)
    return path


def _unpack(archive: Path, dest: Path) -> Path:
    dest.mkdir(parents=True, exist_ok=True)
    dest.chmod(0o755)
    with zipfile.ZipFile(archive) as zf:
        for info in zf.infolist():
            rel = Path(info.filename)
            if rel.is_absolute() or ".." in rel.parts:
                raise ValueError("unsafe archive member")
            if info.filename.endswith("/"):
                continue
            target = dest / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(zf.read(info))
            target.chmod(0o644)
    for directory in [dest, *(p for p in dest.rglob("*") if p.is_dir())]:
        directory.chmod(0o755)
    return dest


def _delivered_repo() -> Path:
    if "repo" not in _CACHE:
        _CACHE["repo"] = _unpack(OUT_DIR / "patched-repo.zip", Path(tempfile.mkdtemp(prefix="delivered-")))
    return _CACHE["repo"]


def _shipped_repo() -> Path:
    """The agent's starting /app/repo, rebuilt from the embedded copy."""
    if "shipped" not in _CACHE:
        _CACHE["shipped"] = _rebuild("repo/")
    return _CACHE["shipped"]


def _run(command: list[str], cwd: Path, repo: Path, timeout: float) -> subprocess.CompletedProcess:
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "PYTHONPATH": str(repo / "src"),
        "PYTHONDONTWRITEBYTECODE": "1",
        "HOME": str(cwd),
        "LANG": "C.UTF-8",
    }
    # One submitted program at a time: _stop kills every process the unprivileged
    # user owns, which must never reach the child of a check running alongside.
    with open(Path(tempfile.gettempdir()) / "migrakit-verifier.lock", "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        proc = subprocess.Popen(
            _untrusted_command([*_CAPPED, *command]), cwd=cwd, env=env, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True,
        )
        try:
            out, err = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            _stop(proc)
            proc.communicate()
            raise
        _stop(proc)
    return subprocess.CompletedProcess(command, proc.returncode, out, err)


def _stop(proc: subprocess.Popen) -> None:
    """Kill the child's process group and, when it ran as nobody, every process nobody owns."""
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass
    if os.name != "posix" or os.geteuid() != 0:
        return
    import pwd

    try:
        uid = pwd.getpwnam("nobody").pw_uid
    except KeyError:
        return
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            for row in (entry / "status").read_text().splitlines():
                if row.startswith("Uid:"):
                    if int(row.split()[1]) == uid:
                        os.kill(int(entry.name), signal.SIGKILL)
                    break
        except (OSError, ValueError):
            continue


_DRIVER = r'''
import json, sys
job = json.load(open(sys.argv[1], encoding="utf-8"))
import migrakit

def call():
    op = job["op"]
    try:
        if op == "pipeline":
            records, summary = migrakit.run_pipeline(job["contracts"], job["feed"], job["corrections"], job["manifest"])
            return {"records": records, "summary": summary}
        registry = migrakit.load_contracts(job["contracts"])
        if op == "plan":
            return {"ok": migrakit.plan_migration(registry, job["schema"], job["payload"])}
        if op == "signature":
            return {"ok": migrakit.state_signature(registry, job["schema"], job["payload"])}
        if op == "execute":
            return {"ok": migrakit.execute_plan(registry, job["schema"], job["payload"], job["plan"], job["corrections"])}
        if op == "resolve":
            found = []
            for value in job["values"]:
                try:
                    found.append(migrakit.resolve_partner(registry, value))
                except migrakit.MigrationError as exc:
                    found.append(getattr(exc, "code", None))
            return {"ok": found}
        if op == "summary":
            return {"ok": migrakit.build_summary(registry, job["records"], job["invalid"])}
        if op == "watch":
            payload, steps = job["payload"], job["corrections"]
            before = json.dumps([payload, steps], sort_keys=True)
            plan = migrakit.plan_migration(registry, job["schema"], payload)
            frozen = json.dumps(plan)
            migrakit.state_signature(registry, job["schema"], payload)
            migrakit.execute_plan(registry, job["schema"], payload, plan, steps)
            return {"ok": [json.dumps([payload, steps], sort_keys=True) == before, json.dumps(plan) == frozen]}
        if op == "api":
            return {"ok": [name for name in job["names"] if callable(getattr(migrakit, name, None))]}
    except migrakit.MigrationError as exc:
        return {"error": getattr(exc, "code", None)}
    return {"error": "unknown op"}

print(json.dumps(call(), sort_keys=True))
'''


def _child(job: dict, timeout: float = 20.0) -> dict:
    """Run one entry-point call of the delivered package in a foreign working directory."""
    repo = _delivered_repo()
    cwd = _scratch("child-")
    driver = cwd / "driver.py"
    driver.write_text(_DRIVER, encoding="utf-8")
    driver.chmod(0o644)
    job_file = cwd / "job.json"
    job_file.write_text(json.dumps(job), encoding="utf-8")
    job_file.chmod(0o644)
    done = _run([sys.executable, str(driver), str(job_file)], cwd, repo, timeout)
    if done.returncode != 0:
        raise RuntimeError(done.stderr[-400:])
    return json.loads(done.stdout.strip().splitlines()[-1])


# ----------------------------------------------------------------------------- contract folders

DEFAULT_TAXONOMY = {
    "categories": [
        {"name": "complete", "members": ["migrated"]},
        {"name": "duplicate", "members": ["replayed", "superseded"]},
        {"name": "execution_failure", "members": ["E_PREREQ_FAILED"]},
        {"name": "conflict", "members": ["E_REPLAY_CONFLICT"]},
        {"name": "input_error", "members": ["E_PARSE", "E_UNKNOWN_PARTNER", "E_ALIAS_CYCLE"]},
        {"name": "planning_error", "members": ["E_UNKNOWN_SCHEMA", "E_UNREACHABLE"]},
    ]
}


class Spec:
    """One hidden contract folder, described in memory and written on demand."""

    def __init__(self, schemas: list[str], canonical: set[str], edges: list[tuple], **extra: Any) -> None:
        self.schemas = schemas
        self.canonical = canonical
        self.edges = edges
        self.policy: list[tuple] = extra.get("policy", [])
        self.presence: str = extra.get("presence", "present")
        self.fill: str = extra.get("fill", "absent_only")
        self.tokens: list[str] = extra.get("tokens", ["NULL", "N/A"])
        self.partner_tokens: dict[str, list[str]] = extra.get("partner_tokens", {})
        self.partners: dict[str, list[str]] = extra.get("partners", {"P100": ["alpha-one"]})
        self.merges: list[tuple[str, str]] = extra.get("merges", [])
        self.taxonomy: dict = extra.get("taxonomy", DEFAULT_TAXONOMY)
        self.order: dict[str, int] = extra.get("order", {})

    def write(self) -> Path:
        root = _scratch("contracts-")
        rows = [{"id": s, "domain": s.rsplit(".v", 1)[0], "canonical": s in self.canonical} for s in self.schemas]
        files = {
            "schema_versions.json": json.dumps({"schemas": rows}, indent=1),
            "migration_edges.csv": "edge_id,source,target,requires,operations,cost\n"
            + "".join(f"{e[0]},{e[1]},{e[2]},{e[3]},{e[4]},{e[5]}\n" for e in self.edges),
            "field_policy.tsv": "domain\tfield\tdefault\tfill\tnull_counts_as\n" + "".join("\t".join(p) + "\n" for p in self.policy),
            "null_semantics.ini": "[presence]\nexplicit_null = " + self.presence + "\n\n[fill]\nmode = " + self.fill
            + "\n\n[tokens]\ndefault = " + " | ".join(self.tokens) + "\n"
            + "".join(f"{p} = {' | '.join(t)}\n" for p, t in sorted(self.partner_tokens.items())),
            "partner_aliases.xml": "<partners>\n"
            + "".join(f'  <partner id="{p}">' + "".join(f"<alias>{a}</alias>" for a in al) + "</partner>\n" for p, al in self.partners.items())
            + "".join(f'  <merge from="{a}" into="{b}"/>\n' for a, b in self.merges) + "</partners>\n",
            "report_taxonomy.json": json.dumps(self.taxonomy),
            "partner_order.tsv": "partner_id\trank\n" + "".join(f"{p}\t{r}\n" for p, r in self.order.items()),
        }
        for name, text in files.items():
            (root / name).write_text(text, encoding="utf-8")
            (root / name).chmod(0o644)
        root.chmod(0o755)
        return root


def _ids(rng: random.Random, count: int) -> list[str]:
    found: set[str] = set()
    while len(found) < count:
        found.add("q" + "".join(rng.choice("abcdefghijkmnpqrstuvwxyz") for _ in range(6)))
    return sorted(found)


def _word(rng: random.Random, head: str) -> str:
    return head + "".join(rng.choice("bcdfghjklmnpqrstvwz") for _ in range(4))


def _chain(rng: random.Random, count: int) -> tuple[str, list[str]]:
    domain = _word(rng, "dm")
    return domain, [f"{domain}.v{n}" for n in range(1, count + 1)]


def _rng(salt: int) -> random.Random:
    return random.Random(EVAL_SEED * 1000 + salt)


# ----------------------------------------------------------------------------- reference semantics (tests side)

def _policy_map(spec: Spec) -> dict[tuple[str, str], tuple]:
    return {(p[0], p[1]): p for p in spec.policy}


def _counts(spec: Spec, pol: dict, dom: str, name: str, state: str) -> bool:
    if state == "V":
        return True
    if state == "A":
        return False
    row = pol.get((dom, name))
    mode = row[4] if row and row[4] else spec.presence
    return mode == "present"


def _step_states(spec: Spec, pol: dict, dom: str, states: dict[str, str], ops: str) -> dict[str, str]:
    states = dict(states)
    for op in filter(None, ops.split(";")):
        kind, rest = op.split(":", 1)
        if kind == "rename":
            a, b = rest.split(">")
            if states.get(a, "A") != "A":
                states[b] = states.pop(a)
        elif kind == "drop":
            states.pop(rest, None)
        elif kind == "add":
            row = pol.get((dom, rest))
            if row and row[2]:
                now = states.get(rest, "A")
                fill = row[3] if row[3] else spec.fill
                if now == "A" or (now == "N" and fill == "absent_or_null"):
                    states[rest] = "V"
    return states


def _reference_plan(spec: Spec, start: str, payload: dict) -> list[str] | None:
    """Label-setting search over (schema, states) ordered by (cost so far plus the cheapest
    schema-graph cost to the canonical schema, edge-id list); the first canonical pop is the plan."""
    dom = start.rsplit(".v", 1)[0]
    target = next(s for s in spec.canonical if s.rsplit(".v", 1)[0] == dom)
    if start == target:
        return []
    pol = _policy_map(spec)
    edges = sorted(e for e in spec.edges if e[1].rsplit(".v", 1)[0] == dom)
    outgoing: dict[str, list[tuple]] = defaultdict(list)
    incoming: dict[str, list[tuple]] = defaultdict(list)
    for edge in edges:
        outgoing[edge[1]].append(edge)
        incoming[edge[2]].append(edge)
    rest = {target: 0}
    heap: list = [(0, target)]
    while heap:
        d, here = heapq.heappop(heap)
        if d > rest[here]:
            continue
        for edge in incoming[here]:
            if edge[1] != target and d + int(edge[5]) < rest.get(edge[1], 1 << 62):
                rest[edge[1]] = d + int(edge[5])
                heapq.heappush(heap, (rest[edge[1]], edge[1]))
    if start not in rest:
        return None
    names = sorted({x for e in edges for part in filter(None, (e[3] + ";" + e[4]).split(";")) for x in part.split(":", 1)[1].replace(">", ":").split(":")[:2] if x not in ("int", "float", "str")})
    first = {n: ("N" if v is None else "V") for n, v in payload.items() if n in names}
    root = (start, tuple(first.get(n, "A") for n in names))
    best = {root: (0, ())}
    heap = [(rest[start], (), root)]
    done: set = set()
    while heap:
        total, path, node = heapq.heappop(heap)
        if node in done:
            continue
        done.add(node)
        if node[0] == target:
            return list(path)
        spent = total - rest[node[0]]
        states = {n: v for n, v in zip(names, node[1]) if v != "A"}
        for edge_id, _, dst, req, ops, cost in outgoing[node[0]]:
            if dst not in rest:
                continue
            ok = all(_counts(spec, pol, dom, r.split(":")[1], states.get(r.split(":")[1], "A")) == (r.split(":")[0] == "has") for r in filter(None, req.split(";")))
            if not ok:
                continue
            after = _step_states(spec, pol, dom, states, ops)
            nxt = (dst, tuple(after.get(n, "A") for n in names))
            if nxt in done:
                continue
            label = (spent + int(cost), path + (edge_id,))
            if nxt not in best or label < best[nxt]:
                best[nxt] = label
                heapq.heappush(heap, (label[0] + rest[dst], label[1], nxt))
    return None


# ----------------------------------------------------------------------------- reference pipeline (tests side)

def _ref_cast(value: Any, kind: str) -> Any:
    if isinstance(value, bool):
        return value
    text = value.strip() if isinstance(value, str) else None
    if kind == "int":
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value) if value == int(value) else value
        if text is not None and re.fullmatch(r"[+-]?[0-9]+", text):
            return int(text)
        return value
    if kind == "float":
        if isinstance(value, (int, float)):
            return float(value)
        if text is not None and re.fullmatch(r"[+-]?([0-9]+(\.[0-9]*)?|\.[0-9]+)", text):
            return float(text)
        return value
    return str(value) if isinstance(value, (int, float)) else value


def _ref_apply(spec: Spec, pol: dict, dom: str, record: dict, ops: str) -> dict:
    record = dict(record)
    for op in filter(None, (x.strip() for x in ops.split(";"))):
        kind, rest = op.split(":", 1)
        if kind == "rename":
            a, b = rest.split(">", 1)
            if a in record:
                record[b] = record.pop(a)
        elif kind == "drop":
            record.pop(rest, None)
        elif kind == "add":
            row = pol.get((dom, rest))
            if row and row[2] != "":
                fill = row[3] or spec.fill
                if rest not in record or (record[rest] is None and fill == "absent_or_null"):
                    record[rest] = json.loads(row[2])
        else:
            name, target = rest.split(":")
            if record.get(name) is not None:
                record[name] = _ref_cast(record[name], target)
    return record


def _ref_allows(spec: Spec, pol: dict, dom: str, record: dict, req: str) -> bool:
    for part in filter(None, (x.strip() for x in req.split(";"))):
        kind, name = part.split(":", 1)
        state = "A" if name not in record else ("N" if record[name] is None else "V")
        if _counts(spec, pol, dom, name, state) != (kind == "has"):
            return False
    return True


def _ref_execute(spec: Spec, start: str, payload: dict, plan: list[str], steps: list[dict]) -> dict:
    pol = _policy_map(spec)
    dom = start.rsplit(".v", 1)[0]
    by_id = {e[0]: e for e in spec.edges}
    state = {"record": copy.deepcopy(payload), "applied": [], "seen": set()}

    def arrive(schema: str) -> None:
        if schema in state["seen"]:
            return
        state["seen"].add(schema)
        for step in steps:
            if step["schema"] != schema:
                continue
            if step["op"] == "SET":
                state["record"][step["field"]] = copy.deepcopy(step["value"])
            elif step["op"] == "UNSET":
                state["record"].pop(step["field"], None)
            else:
                state["record"][step["field"]] = None
            state["applied"].append(step["id"])

    arrive(start)
    here = start
    for done, edge_id in enumerate(plan):
        edge = by_id[edge_id]
        if not _ref_allows(spec, pol, dom, state["record"], edge[3]):
            return {"status": "failed", "code": "E_PREREQ_FAILED", "schema": here, "payload": None,
                    "completed_steps": done, "failed_edge": edge_id, "corrections_applied": state["applied"]}
        state["record"] = _ref_apply(spec, pol, dom, state["record"], edge[4])
        here = edge[2]
        arrive(here)
    return {"status": "migrated", "code": None, "schema": here, "payload": state["record"],
            "completed_steps": len(plan), "failed_edge": None, "corrections_applied": state["applied"]}


def _ref_resolve(spec: Spec, value: Any) -> tuple[str | None, str | None]:
    if not isinstance(value, str):
        return None, "E_UNKNOWN_PARTNER"
    if value in spec.partners:
        pid = value
    else:
        owners = [p for p, names in spec.partners.items() if value in names]
        if not owners:
            return None, "E_UNKNOWN_PARTNER"
        pid = owners[0]
    links = dict(spec.merges)
    seen = {pid}
    while pid in links:
        pid = links[pid]
        if pid in seen:
            return None, "E_ALIAS_CYCLE"
        seen.add(pid)
    return pid, None


def _ref_correction(line: str) -> dict | None:
    parts = line.split(None, 7)
    if len(parts) < 2:
        return None
    cid, op = parts[0], parts[1]
    if op == "REISSUE":
        if len(parts) == 5 and re.fullmatch(r"[0-9a-f]{12}", parts[4]):
            return {"id": cid, "op": op, "partner": parts[2], "key": parts[3], "prefix": parts[4]}
        return None
    if op in ("UNSET", "NULL") and len(parts) == 7 and parts[4] == "AT":
        return {"id": cid, "op": op, "partner": parts[2], "key": parts[3], "schema": parts[5], "field": parts[6], "value": None}
    if op == "SET" and len(parts) == 8 and parts[4] == "AT":
        try:
            value = json.loads(parts[7])
        except ValueError:
            return None
        return {"id": cid, "op": op, "partner": parts[2], "key": parts[3], "schema": parts[5], "field": parts[6], "value": value}
    return None


def _ref_summary(spec: Spec, records: list[dict], invalid: list[str]) -> dict:
    cats = [(c["name"], c["members"]) for c in spec.taxonomy["categories"]]
    by_category = {name: 0 for name, _ in cats}
    for r in records:
        wanted = r["code"] if r["code"] is not None else r["status"]
        by_category[next(name for name, members in cats if wanted in members)] += 1
    by_status: dict[str, int] = defaultdict(int)
    by_code: dict[str, int] = defaultdict(int)
    tally: dict[str, list[int]] = {}
    for r in records:
        by_status[r["status"]] += 1
        if r["code"] is not None:
            by_code[r["code"]] += 1
        if r["partner"] is not None:
            row = tally.setdefault(r["partner"], [0, 0, 0])
            row[0] += 1
            row[1] += r["status"] == "migrated"
            row[2] += r["status"] == "failed"
    ranked = sorted((p for p in tally if p in spec.order), key=lambda p: (spec.order[p], p))
    ranked += sorted(p for p in tally if p not in spec.order)
    return {
        "records": len(records), "attempted": sum(1 for r in records if r["attempted"]),
        "by_status": dict(sorted(by_status.items())), "by_code": dict(sorted(by_code.items())),
        "by_category": by_category, "invalid_corrections": sorted(invalid),
        "partners": [{"partner": p, "records": tally[p][0], "migrated": tally[p][1], "failed": tally[p][2]} for p in ranked],
    }


def _ref_pipeline(spec: Spec, feed_text: str, seqs: dict[str, int], corrections_text: str,
                  receipts: dict[str, list] | None = None) -> dict:
    """What the contract says run_pipeline returns, worked out independently of any submission."""
    known = set(spec.schemas)
    steps: dict[tuple, list] = defaultdict(list)
    reissues: dict[tuple, list] = defaultdict(list)
    invalid: set[str] = set()
    for raw in corrections_text.splitlines():
        text = raw.strip()
        if not text or text.startswith("#"):
            continue
        item = _ref_correction(text)
        if item is None:
            invalid.add(text.split()[0])
            continue
        pid, problem = _ref_resolve(spec, item["partner"])
        if problem:
            invalid.add(item["id"])
            continue
        (reissues if item["op"] == "REISSUE" else steps)[(pid, item["key"])].append(item)
    rows = feed_text.split("\n")
    if rows and rows[-1] == "":
        rows.pop()
    records, admitted = [], []
    for number, raw in enumerate(rows, start=1):
        try:
            doc = json.loads(raw)
        except ValueError:
            doc = None
        fine = (isinstance(doc, dict) and all(isinstance(doc.get(k), str) and doc[k] for k in ("batch", "partner", "key", "schema"))
                and isinstance(doc.get("payload"), dict) and doc["batch"] in seqs)
        record = {"line": number, "batch": doc["batch"] if fine else None, "partner": None, "key": doc["key"] if fine else None,
                  "status": "rejected", "code": None if fine else "E_PARSE", "schema": doc["schema"] if fine else None,
                  "plan": None, "completed_steps": 0, "failed_edge": None, "payload": None, "attempted": False, "fingerprint": None}
        records.append(record)
        if fine:
            admitted.append((seqs[doc["batch"]], number, doc, record))
    holders: dict[tuple, dict] = {}
    prints: dict[tuple, set] = defaultdict(set)
    used: set[str] = set()
    for _, _, doc, record in sorted(admitted, key=lambda t: (t[0], t[1])):
        pid, problem = _ref_resolve(spec, doc["partner"])
        if problem:
            record["code"] = problem
            continue
        fingerprint = _fp(doc["schema"], doc["payload"])
        record.update(partner=pid, fingerprint=fingerprint)
        identity = (pid, doc["key"])
        prints[identity].add(fingerprint)
        holder = holders.get(identity)
        if holder is not None:
            if holder["fingerprint"] == fingerprint:
                record["status"] = "replayed"
                continue
            if not any(fingerprint.startswith(r["prefix"]) for r in reissues[identity]):
                record["code"] = "E_REPLAY_CONFLICT"
                continue
            holder.update(status="superseded", code=None, payload=None)
        holders[identity] = record
        tokens = spec.partner_tokens.get(pid, spec.tokens)
        tokens = {t.strip() for t in tokens if t.strip()}
        payload = {k: (None if isinstance(v, str) and v in tokens else v) for k, v in doc["payload"].items()}
        if doc["schema"] not in known:
            record["code"] = "E_UNKNOWN_SCHEMA"
            continue
        plan = _reference_plan(spec, doc["schema"], payload)
        if plan is None:
            record["code"] = "E_UNREACHABLE"
            continue
        result = _ref_execute(spec, doc["schema"], payload, plan, steps[identity])
        used.update(result["corrections_applied"])
        record.update(status=result["status"], code=result["code"], schema=result["schema"], plan=plan,
                      completed_steps=result["completed_steps"], failed_edge=result["failed_edge"],
                      payload=result["payload"], attempted=True)
    for identity, items in steps.items():
        invalid.update(item["id"] for item in items if item["id"] not in used)
    for identity, items in reissues.items():
        invalid.update(item["id"] for item in items if not any(fp.startswith(item["prefix"]) for fp in prints[identity]))
    summary = _ref_summary(spec, records, sorted(invalid))
    seen: dict[str, list] = {batch: [0, 0] for batch in seqs}
    for _, number, doc, _ in admitted:
        seen[doc["batch"]][0] += 1
        seen[doc["batch"]][1] ^= int(_fp(doc["schema"], doc["payload"])[:8], 16)
    stated = seen if receipts is None else receipts
    summary["receipt_mismatches"] = sorted(b for b in seqs if list(stated[b]) != seen[b])
    return {"records": records, "summary": summary}


def _receipts(lines: list, seqs: dict[str, int]) -> dict[str, list]:
    """Honest batch receipts for a feed: records whose batch is the batch, XOR of fingerprint prefixes."""
    honest: dict[str, list] = {batch: [0, 0] for batch in seqs}
    for raw in _feed_text(lines).split("\n"):
        try:
            doc = json.loads(raw)
        except ValueError:
            continue
        if (isinstance(doc, dict) and all(isinstance(doc.get(k), str) and doc[k] for k in ("batch", "partner", "key", "schema"))
                and isinstance(doc.get("payload"), dict) and doc["batch"] in seqs):
            honest[doc["batch"]][0] += 1
            honest[doc["batch"]][1] ^= int(_fp(doc["schema"], doc["payload"])[:8], 16)
    return honest


# ----------------------------------------------------------------------------- isolated cases

def case_signature() -> tuple[Spec, dict, dict]:
    rng = _rng(1)
    dom, s = _chain(rng, 3)
    a, b, c, d, z = (_word(rng, f) for f in "abcdz")
    e = _ids(rng, 4)
    edges = [(e[0], s[0], s[1], f"has:{a}", "", 1), (e[1], s[1], s[2], f"lacks:{b}", "", 1),
             (e[2], s[0], s[2], f"has:{c}", "", 4), (e[3], s[1], s[0], f"has:{d}", "", 1)]
    payload = {a: None, b: rng.randint(1, 9), d: "x", z: None}
    expected = dict(sorted({a: "null", b: "value", c: "absent", d: "value"}.items()))
    return Spec(s, {s[2]}, edges), {"op": "signature", "schema": s[0], "payload": payload}, expected


def case_watch() -> tuple[Spec, dict]:
    rng = _rng(9)
    dom, s = _chain(rng, 3)
    f, g = _word(rng, "f"), _word(rng, "g")
    e = _ids(rng, 2)
    edges = [(e[0], s[0], s[1], f"has:{f}", f"drop:{f};add:{g}", 1), (e[1], s[1], s[2], "", f"cast:{g}:str", 1)]
    spec = Spec(s, {s[2]}, edges, policy=[(dom, g, '{"n": [1, 2]}', "", "")])
    job = {"op": "watch", "schema": s[0], "payload": {f: "x", "keep": {"n": [3]}},
           "corrections": [{"id": "C1", "op": "SET", "schema": s[1], "field": "memo", "value": {"a": [1]}}]}
    return spec, job


def case_revisit() -> tuple[Spec, dict, list]:
    rng = _rng(4)
    dom, s = _chain(rng, 4)
    f = _word(rng, "f")
    e = _ids(rng, 5)
    rng.shuffle(e)
    edges = [(e[0], s[0], s[3], f"lacks:{f}", "", 1), (e[1], s[0], s[1], "", f"drop:{f}", 1), (e[2], s[1], s[0], "", "", 1),
             (e[3], s[0], s[2], "", "", 10), (e[4], s[2], s[3], "", "", 1)]
    return Spec(s, {s[3]}, edges), {"op": "plan", "schema": s[0], "payload": {f: "v"}}, [e[1], e[2], e[0]]


def case_tie_first_edge() -> tuple[Spec, dict, list]:
    rng = _rng(6)
    dom, s = _chain(rng, 6)
    a1, z, a2, x, y, w = _ids(rng, 6)
    # [a1, x, y] and [a2, z] and [a2, w] all cost 4; the three-edge plan is the smallest edge-id list.
    edges = [(a1, s[0], s[1], "", "", 1), (x, s[1], s[2], "", "", 1), (y, s[2], s[3], "", "", 2),
             (a2, s[0], s[4], "", "", 2), (z, s[4], s[3], "", "", 2), (w, s[4], s[5], "", "", 1)]
    edges.append((_ids(rng, 1)[0], s[5], s[3], "", "", 1))
    return Spec(s, {s[3]}, edges), {"op": "plan", "schema": s[0], "payload": {}}, [a1, x, y]


def _ladder(salt: int, layers: int, width: int, mode: str, trap: bool = False) -> tuple[Spec, dict]:
    rng = _rng(salt)
    domain = _word(rng, "ld")
    start = f"{domain}.v1"
    grid = [[f"{domain}.v{2 + i * width + j}" for j in range(width)] for i in range(layers)]
    target = f"{domain}.v{2 + layers * width}"
    hops = [(start, n) for n in grid[0]]
    for i in range(layers - 1):
        hops.extend((a, b) for a in grid[i] for b in grid[i + 1])
    hops.extend((n, target) for n in grid[-1])
    ids = _ids(rng, len(hops))
    rng.shuffle(ids)
    fields = [_word(rng, "k") for _ in range(5)]
    policy = [(domain, f, "1", "", "") for f in fields]
    edges = []
    for (a, b), edge_id in zip(hops, ids):
        req, ops = "", ""
        cost = rng.randint(1, 100000)
        if rng.random() < 0.45:
            req = f"{rng.choice(['has', 'lacks'])}:{rng.choice(fields)}"
        if rng.random() < 0.55:
            kind = rng.choice(["drop", "add", "rename"])
            f = rng.choice(fields)
            ops = f"rename:{f}>{rng.choice([x for x in fields if x != f])}" if kind == "rename" else f"{kind}:{f}"
        if b == target:
            req = f"has:{fields[0]}"
        edges.append((edge_id, a, b, req, ops, cost))
    schemas = [start, *(n for row in grid for n in row), target]
    payload = {f: rng.randint(1, 9) for f in fields if rng.random() < 0.6} | {fields[0]: 1}
    return Spec(schemas, {target}, edges, policy=policy), {"op": "plan", "schema": start, "payload": payload}


LADDERS = {"ladder_large_state": (13, 45, 3, "state")}


def case_ladder(name: str) -> tuple[Spec, dict, list | None]:
    if name not in _CACHE:
        spec, job = _ladder(*LADDERS[name])
        _CACHE[name] = (spec, job, _reference_plan(spec, job["schema"], job["payload"]))
    return _CACHE[name]


def _exec_chain(rng: random.Random, count: int) -> tuple[str, list[str], list[str]]:
    dom, s = _chain(rng, count)
    e = _ids(rng, count + 2)
    rng.shuffle(e)
    return dom, s, e


def case_fill() -> tuple[Spec, dict, dict]:
    rng = _rng(21)
    dom, s, e = _exec_chain(rng, 2)
    p, q, r, t = (_word(rng, x) for x in "pqrt")
    policy = [(dom, p, "7", "", ""), (dom, q, '"dq"', "", ""), (dom, r, '"dr"', "absent_only", ""), (dom, t, "3", "", "")]
    edges = [(e[0], s[0], s[1], "", f"add:{p};add:{q};add:{r};add:{t}", 1)]
    spec = Spec(s, {s[1]}, edges, policy=policy, fill="absent_or_null")
    payload = {q: None, r: None, t: "keep"}
    job = {"op": "execute", "schema": s[0], "payload": payload, "plan": [e[0]], "corrections": []}
    return spec, job, {p: 7, q: "dq", r: None, t: "keep"}


def case_first_arrival() -> tuple[Spec, dict, dict]:
    rng = _rng(26)
    dom, s, e = _exec_chain(rng, 4)
    g = _word(rng, "g")
    edges = [(e[0], s[0], s[1], "", "", 1), (e[1], s[1], s[2], "", f"drop:{g}", 1), (e[2], s[2], s[1], "", "", 1), (e[3], s[1], s[3], f"has:{g}", "", 1)]
    cid = f"C{rng.randint(100, 999)}"
    job = {"op": "execute", "schema": s[0], "payload": {"memo": 3}, "plan": [e[0], e[1], e[2], e[3]],
           "corrections": [{"id": cid, "op": "SET", "schema": s[1], "field": g, "value": 5}]}
    expected = {"status": "failed", "code": "E_PREREQ_FAILED", "schema": s[1], "payload": None, "completed_steps": 3,
                "failed_edge": e[3], "corrections_applied": [cid]}
    return Spec(s, {s[3]}, edges), job, expected


def _partners(rng: random.Random, count: int) -> list[str]:
    return [f"P{n}" for n in rng.sample(range(1000, 9999), count)]


def _merge_links_fixture() -> tuple[Spec, list[str], str]:
    rng = _rng(31)
    dom, s = _chain(rng, 2)
    p = _partners(rng, 9)
    alias = _word(rng, "al")
    partners = {x: [] for x in p}
    partners[p[0]] = [alias]
    partners[p[5]] = [p[6]]
    merges = [(p[0], p[1]), (p[1], p[2]), (p[2], p[3]), (p[4], p[8]), (p[8], p[4])]
    spec = Spec(s, {s[1]}, [], partners=partners, merges=merges)
    return spec, p, alias


def case_merge_chain() -> tuple[Spec, dict, list]:
    spec, p, alias = _merge_links_fixture()
    return spec, {"op": "resolve", "values": [alias, p[1]]}, [p[3], p[3]]


def case_merge_loop() -> tuple[Spec, dict, list]:
    spec, p, _ = _merge_links_fixture()
    return spec, {"op": "resolve", "values": [p[4]]}, ["E_ALIAS_CYCLE"]


def case_partner_precedence() -> tuple[Spec, dict, list]:
    spec, p, _ = _merge_links_fixture()
    return spec, {"op": "resolve", "values": [p[6]]}, [p[6]]


def _feed_job(spec: Spec, lines: list, seqs: dict[str, int], corrections: list[str], receipts: dict[str, list] | None = None) -> dict:
    root = spec.write()
    feed = root / "feed_input.jsonl"
    feed.write_text(_feed_text(lines), encoding="utf-8")
    (root / "corrections_input.txt").write_text(_corrections_text(corrections), encoding="utf-8")
    stated = _receipts(lines, seqs) if receipts is None else receipts
    rows = "".join(f"{b},{n},{stated[b][0]},{stated[b][1]:08x}\n" for b, n in seqs.items())
    (root / "manifest_input.csv").write_text("batch_id,received_seq,lines,fp_xor\n" + rows, encoding="utf-8")
    for name in ("feed_input.jsonl", "corrections_input.txt", "manifest_input.csv"):
        (root / name).chmod(0o644)
    return {"op": "pipeline", "contracts": str(root), "feed": str(feed), "corrections": str(root / "corrections_input.txt"), "manifest": str(root / "manifest_input.csv")}


def _feed_text(lines: list) -> str:
    return "".join((x if isinstance(x, str) else json.dumps(x)) + "\n" for x in lines)


def _corrections_text(corrections: list[str]) -> str:
    return "# hidden\n" + "".join(c + "\n" for c in corrections)


def _simple_pipe(salt: int, extra_ops: str = "", req2: str = "", **spec_extra: Any) -> tuple[random.Random, Spec, list[str], list[str]]:
    rng = _rng(salt)
    dom, s = _chain(rng, 3)
    e = _ids(rng, 2)
    edges = [(e[0], s[0], s[1], "", extra_ops, 1), (e[1], s[1], s[2], req2, "", 2)]
    return rng, Spec(s, {s[2]}, edges, **spec_extra), s, e


def _line(batch: str, partner: str, key: str, schema: str, payload: dict) -> dict:
    return {"batch": batch, "partner": partner, "key": key, "schema": schema, "payload": payload}


def _fp(schema: str, payload: dict) -> str:
    text = json.dumps({"payload": payload, "schema": schema}, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def case_rejection_codes() -> tuple[dict, dict]:
    rng, spec, s, e = _simple_pipe(41, req2="has:f", partners={"P501": ["north-a"], "P502": [], "P503": []})
    spec.merges = [("P502", "P503"), ("P503", "P502")]
    lone = _word(rng, "dz")
    spec.schemas += [f"{lone}.v1", f"{lone}.v2"]
    spec.canonical.add(f"{lone}.v2")
    lines = [
        _line("B1", "ghost-" + _word(rng, ""), "k1", s[0], {"f": 1}),
        _line("B1", "north-a", "k2", s[0].replace(".v1", ".v9"), {"f": 1}),
        _line("B1", "P501", "k3", f"{lone}.v1", {"f": 1}),
        _line("B1", "P501", "k4", s[0], {"f": 1}),
        {"batch": "B1", "partner": "P501", "key": "k5", "schema": s[0], "payload": [1]},
        _line("B7", "P501", "k6", s[0], {"f": 1}),
        _line("B1", "P502", "k7", s[0], {"f": 1}),
        _line("B1", "north-a", "k8", s[0], {"g": 1}),
    ]
    expected = {"1": "E_UNKNOWN_PARTNER", "2": "E_UNKNOWN_SCHEMA", "3": "E_UNREACHABLE", "5": "E_PARSE", "6": "E_PARSE",
                "7": "E_ALIAS_CYCLE", "8": "E_UNREACHABLE"}
    return _feed_job(spec, lines, {"B1": 1}, []), expected


def case_bad_lines() -> tuple[dict, list]:
    rng, spec, s, e = _simple_pipe(42, extra_ops="cast:a:int", partners={"P502": ["south-b"]})
    lines = [_line("B1", "P502", "k1", s[0], {"a": "4"}), "{\"batch\": \"B1\", \"partner\": ", _line("B1", "south-b", "k2", s[0], {"a": "5"}),
             "not json", _line("B2", "P502", "k3", s[0], {"a": "6", "b": "N/A "}), {"batch": "B2", "partner": "P502", "key": "k4", "schema": s[0]}]
    expected = [("migrated", {"a": 4}), ("rejected", None), ("migrated", {"a": 5}), ("rejected", None), ("migrated", {"a": 6, "b": "N/A "}), ("rejected", None)]
    return _feed_job(spec, lines, {"B1": 1, "B2": 2}, []), expected


def case_dropped_conflict() -> dict:
    rng, spec, s, e = _simple_pipe(45, extra_ops="drop:z", partners={"P504": ["west-d"]})
    lines = [_line("B1", "P504", "k1", s[0], {"a": 1, "z": "x"}), _line("B2", "P504", "k1", s[0], {"a": 1, "z": "y"})]
    return _feed_job(spec, lines, {"B1": 1, "B2": 2}, [])


def case_receipt_scope() -> tuple[dict, list]:
    rng, spec, s, e = _simple_pipe(46, partners={"P506": ["east-f"]})
    lines = [
        _line("B1", "P506", "k1", s[0], {"a": 1}),
        {"batch": "B1", "partner": "P506", "key": "k2", "schema": s[0], "payload": [2]},
        _line("B1", "east-f", "k3", s[1], {"a": 3}),
        {"batch": "B2", "partner": "P506", "schema": s[0], "payload": {"a": 4}},
        _line("B4", "P506", "k5", s[0], {"a": 5}),
        {"batch": "B4", "partner": "east-f", "key": "k6", "schema": "", "payload": {"a": 6}},
    ]
    seqs = {"B1": 1, "B2": 2, "B3": 3, "B4": 4}
    receipts = _receipts(lines, seqs)
    receipts["B4"] = [2, int(_fp(s[0], {"a": 5})[:8], 16) ^ int(_fp("", {"a": 6})[:8], 16)]
    return _feed_job(spec, lines, seqs, [], receipts), ["B4"]


def case_receipt_rejected() -> tuple[dict, list, list[int]]:
    rng, spec, s, e = _simple_pipe(47, partners={"P507": ["west-g"], "P508": [], "P509": []})
    spec.merges = [("P508", "P509"), ("P509", "P508")]
    lines = [
        _line("B1", "P507", "k1", s[0], {"a": 1}),
        _line("B1", "ghost-" + _word(rng, ""), "k2", s[0], {"a": 2}),
        _line("B1", "west-g", "k3", s[0], {"a": 3}),
        _line("B1", "P508", "k4", s[0], {"a": 4}),
        _line("B2", "P507", "k5", s[0], {"a": 5}),
        _line("B2", "ghost-" + _word(rng, ""), "k6", s[0], {"a": 6}),
    ]
    seqs = {"B1": 1, "B2": 2}
    receipts = _receipts(lines, seqs)
    receipts["B2"] = [receipts["B2"][0], receipts["B2"][1] ^ 0x40]
    return _feed_job(spec, lines, seqs, [], receipts), ["B2"], [2, 4, 6]


def case_tokens_exact() -> tuple[dict, list]:
    rng, spec, s, e = _simple_pipe(48, req2="has:f", partners={"P510": ["mid-h"], "P511": []}, partner_tokens={"P510": ["nil", "NULL"]})
    spec.policy = [(s[0].rsplit(".v", 1)[0], "f", "", "", "absent")]
    lines = [
        _line("B1", "P510", "k1", s[0], {"f": 1, "a": "nil", "b": " nil", "c": "NULL ", "d": "N/A"}),
        _line("B1", "P511", "k2", s[0], {"f": 2, "a": "N/A", "b": " N/A", "c": "NULL", "d": "nil "}),
        _line("B1", "mid-h", "k3", s[0], {"f": "nil ", "a": 3}),
        _line("B1", "P511", "k4", s[0], {"f": " NULL", "a": 4}),
        _line("B1", "P511", "k5", s[0], {"f": "N/A", "a": 5}),
    ]
    seqs = {"B1": 1}
    expected = _ref_pipeline(spec, _feed_text(lines), seqs, _corrections_text([]))["records"]
    return _feed_job(spec, lines, seqs, []), [(r["status"], r["code"], r["payload"]) for r in expected]


def _summary_records(partners: list[str]) -> list[dict]:
    base = {"batch": "B1", "key": "k", "schema": "s.v1", "plan": None, "completed_steps": 0, "failed_edge": None, "payload": None, "fingerprint": None}
    rows = [
        ("failed", "E_PREREQ_FAILED", True), ("rejected", "E_UNKNOWN_SCHEMA", False), ("migrated", None, True),
        ("replayed", None, False), ("rejected", "E_PARSE", False), ("migrated", None, True),
    ]
    found = []
    for n, (status, code, attempted) in enumerate(rows, start=1):
        found.append(dict(base, line=n, partner=partners[n % len(partners)], status=status, code=code, attempted=attempted))
    return found


def case_categories() -> tuple[Spec, dict, dict]:
    rng = _rng(61)
    dom, s = _chain(rng, 2)
    taxonomy = {"categories": [
        {"name": "flagged", "members": ["failed", "E_UNKNOWN_SCHEMA"]},
        {"name": "broken", "members": ["E_PREREQ_FAILED", "E_UNKNOWN_SCHEMA"]},
        {"name": "done", "members": ["migrated", "superseded"]},
        {"name": "spare", "members": ["E_ALIAS_CYCLE"]},
        {"name": "dupe", "members": ["replayed", "E_REPLAY_CONFLICT"]},
        {"name": "idle", "members": ["rejected", "E_PARSE", "E_UNKNOWN_PARTNER", "E_UNREACHABLE"]},
    ]}
    p = _partners(rng, 2)
    spec = Spec(s, {s[1]}, [], taxonomy=taxonomy, partners={x: [] for x in p})
    job = {"op": "summary", "records": _summary_records(p), "invalid": []}
    return spec, job, {"flagged": 1, "broken": 1, "done": 2, "spare": 0, "dupe": 1, "idle": 1}


def case_partner_order() -> tuple[Spec, dict, list]:
    rng = _rng(62)
    dom, s = _chain(rng, 2)
    p = sorted(_partners(rng, 5))
    order = {p[3]: 1, p[0]: 5, p[4]: 9}
    spec = Spec(s, {s[1]}, [], partners={x: [] for x in p}, order=order)
    records = _summary_records(p)
    job = {"op": "summary", "records": records, "invalid": []}
    counts: dict[str, list[int]] = {}
    for r in records:
        c = counts.setdefault(r["partner"], [0, 0, 0])
        c[0] += 1
        c[1] += r["status"] == "migrated"
        c[2] += r["status"] == "failed"
    ranked = [x for x in (p[3], p[0], p[4]) if x in counts] + sorted(x for x in counts if x not in order)
    return spec, job, [{"partner": x, "records": counts[x][0], "migrated": counts[x][1], "failed": counts[x][2]} for x in ranked]


# ----------------------------------------------------------------------------- hidden worlds
#
# Each world is one contract folder, feed, correction log and manifest built
# from EVAL_SEED. Several contract areas meet in every world, and the check
# compares the whole run output with the reference pipeline above.

_LETTERS = "abcdefghijkmnpqrstuvwxyz"


def _val(rng: random.Random) -> Any:
    roll = rng.random()
    if roll < 0.3:
        return rng.randint(1, 9999)
    if roll < 0.5:
        return str(rng.randint(1, 9999))
    if roll < 0.6:
        return f" {rng.randint(1, 99)} "
    if roll < 0.7:
        return f"{rng.randint(1, 99)}.5"
    return rng.choice(["alpha", "beta", "gamma", "delta"])


class _World:
    def __init__(self, salt: int, levers: tuple[str, ...]) -> None:
        self.rng = _rng(salt)
        self.levers = set(levers)
        self.taken: set[str] = set()
        self.schemas: list[str] = []
        self.canonical: set[str] = set()
        self.edges: list[tuple] = []
        self.policy: list[tuple] = []
        self.partners: dict[str, list[str]] = {}
        self.merges: list[tuple[str, str]] = []
        self.partner_tokens: dict[str, list[str]] = {}
        self.order: dict[str, int] = {}
        self.taxonomy = DEFAULT_TAXONOMY
        self.lines: list = []
        self.seqs: dict[str, int] = {}
        self.corrections: list[list] = []
        self.clock = 1000
        self.pool = [self.partner() for _ in range(5)]
        self.relays: list[tuple[str, str]] = []
        if "FEED" in self.levers:
            for target in self.pool[:2]:
                a, b = self.partner(), self.partner()
                self.merges += [(a, b), (b, target)]
                self.relays.append((self.partners[a][0], target))

    def fresh(self, head: str, size: int = 5) -> str:
        while True:
            text = head + "".join(self.rng.choice(_LETTERS) for _ in range(size))
            if text not in self.taken:
                self.taken.add(text)
                return text

    def domain(self, count: int, canonical: int = -1) -> tuple[str, list[str]]:
        dom = self.fresh("dm")
        found = [f"{dom}.v{n}" for n in range(1, count + 1)]
        self.schemas += found
        self.canonical.add(found[canonical])
        return dom, found

    def edge(self, source: str, target: str, req: str = "", ops: str = "", cost: int = 1, edge_id: str | None = None) -> str:
        edge_id = edge_id or self.fresh("q", 6)
        self.edges.append((edge_id, source, target, req, ops, cost))
        return edge_id

    def ordered_ids(self, count: int) -> list[str]:
        return sorted(self.fresh("q", 6) for _ in range(count))

    def partner(self) -> str:
        while True:
            pid = f"P{self.rng.randint(10000, 99999)}"
            if pid not in self.taken:
                self.taken.add(pid)
                break
        self.partners[pid] = [self.fresh("al")]
        return pid

    def who(self) -> tuple[str, str]:
        """A partner value for a feed line or correction, and its canonical id."""
        if self.relays and self.rng.random() < 0.4:
            return self.rng.choice(self.relays)
        pid = self.rng.choice(self.pool)
        return (pid if self.rng.random() < 0.5 else self.partners[pid][0]), pid

    def batch(self, seq: int | None = None) -> str:
        name = self.fresh("B", 4)
        if seq is None:
            self.clock += self.rng.randint(1, 9)
            seq = self.clock
        self.seqs[name] = seq
        return name

    def line(self, partner: str, schema: str, payload: dict, key: str | None = None, batch: str | None = None) -> str:
        key = key or self.fresh("k", 6)
        self.lines.append(_line(batch or self.batch(), partner, key, schema, payload))
        return key

    def fix(self, text: str, cid: str | None = None) -> None:
        self.corrections.append([cid, text])

    def simple(self) -> tuple[str, list[str]]:
        dom, s = self.domain(2)
        self.edge(s[0], s[1], "", "", self.rng.randint(1, 9))
        return dom, s

    def finish(self) -> tuple[Spec, list, dict[str, int], list[str], dict[str, list]]:
        for item in self.corrections:
            if item[0] is None:
                item[0] = self.fresh("C", 5)
        spec = Spec(self.schemas, self.canonical, self.edges, policy=self.policy, partner_tokens=self.partner_tokens,
                    partners=self.partners, merges=self.merges, taxonomy=self.taxonomy, order=self.order)
        receipts = _receipts(self.lines, self.seqs)
        if "DAMAGE" in self.levers:
            full = sorted(b for b, (count, _) in receipts.items() if count)
            short, flipped = self.rng.sample(full, 2)
            receipts[short] = [receipts[short][0] + self.rng.choice([-1, 1]), receipts[short][1]]
            receipts[flipped] = [receipts[flipped][0], receipts[flipped][1] ^ (1 << self.rng.randint(0, 31))]
        return spec, self.lines, self.seqs, [f"{cid} {text}" for cid, text in self.corrections], receipts


def _filler(w: _World, count: int) -> None:
    kinds = []
    for _ in range(2):
        n = w.rng.randint(3, 5)
        dom, s = w.domain(n)
        p, a, b, c, z = (w.fresh(x, 4) for x in "pabcz")
        w.policy.append((dom, c, '"filled"', "", "present"))
        for i in range(n - 1):
            req = f"{w.rng.choice(['has', 'lacks'])}:{p}" if w.rng.random() < 0.3 else ""
            ops = w.rng.choice(["", f"rename:{a}>{b}", f"cast:{b}:int", f"add:{c}", f"cast:{a}:float"])
            w.edge(s[i], s[i + 1], req, ops, w.rng.randint(1, 9))
        kinds.append((s, p, a, b, z))
    for _ in range(count):
        s, p, a, b, z = w.rng.choice(kinds)
        payload: dict = {}
        if w.rng.random() < 0.7:
            payload[p] = _val(w.rng)
        if w.rng.random() < 0.8:
            payload[a] = _val(w.rng)
        if w.rng.random() < 0.5:
            payload[b] = _val(w.rng)
        roll = w.rng.random()
        payload[z] = None if roll < 0.2 else ("N/A" if roll < 0.3 else _val(w.rng))
        partner, _ = w.who()
        doc = _line(w.batch(), partner, w.fresh("k", 6), w.rng.choice(s), payload)
        w.lines.insert(w.rng.randint(0, len(w.lines)), doc)


def _g_state(w: _World) -> None:
    dom, s = w.domain(4)
    f = w.fresh("f", 4)
    w.edge(s[0], s[3], f"lacks:{f}", "", 1)
    w.edge(s[0], s[1], "", f"drop:{f}", 1)
    w.edge(s[1], s[0], "", "", 1)
    w.edge(s[0], s[2], "", "", 10)
    w.edge(s[2], s[3], "", "", 1)
    w.line(w.who()[0], s[0], {f: _val(w.rng), "memo": _val(w.rng)})
    w.line(w.who()[0], s[0], {"memo": _val(w.rng)})
    dom, s = w.domain(5, canonical=3)
    g = w.fresh("g", 4)
    w.edge(s[0], s[1], "", f"drop:{g}", 1)
    w.edge(s[0], s[2], "", "", 2)
    w.edge(s[1], s[3], f"has:{g}", "", 1)
    w.edge(s[2], s[3], f"has:{g}", "", 1)
    w.edge(s[1], s[3], "", "", 5)
    w.edge(s[3], s[4], "", "", 9)
    w.line(w.who()[0], s[0], {g: _val(w.rng)})
    dom, s = w.domain(4)
    h = w.fresh("h", 4)
    w.policy.append((dom, h, '"made"', "", ""))
    w.edge(s[0], s[1], "", f"add:{h}", 2)
    w.edge(s[0], s[2], "", "", 1)
    w.edge(s[1], s[3], f"has:{h}", "", 1)
    w.edge(s[2], s[3], "", "", 4)
    w.line(w.who()[0], s[0], {"memo": _val(w.rng)})


def _g_tie(w: _World) -> None:
    dom, s = w.domain(5, canonical=3)
    a1, d, a2, b, c = w.ordered_ids(5)
    w.edge(s[0], s[1], "", "", 1, a1)
    w.edge(s[1], s[2], "", "", 1, b)
    w.edge(s[2], s[3], "", "", 1, c)
    w.edge(s[0], s[4], "", "", 1, a2)
    w.edge(s[4], s[3], "", "", 2, d)
    w.line(w.who()[0], s[0], {"memo": _val(w.rng)})
    dom, s = w.domain(4, canonical=3)
    p, t, q, r = w.ordered_ids(4)
    w.edge(s[0], s[1], "", "", 1, p)
    w.edge(s[1], s[3], "", "", 2, r)
    w.edge(s[0], s[2], "", "", 1, q)
    w.edge(s[2], s[3], "", "", 2, t)
    w.line(w.who()[0], s[0], {"memo": _val(w.rng)})


def _g_scale(w: _World) -> None:
    for _ in range(40):
        dom = w.fresh("ld")
        width, layers = 3, 30
        start = f"{dom}.v1"
        grid = [[f"{dom}.v{2 + i * width + j}" for j in range(width)] for i in range(layers)]
        target = f"{dom}.v{2 + layers * width}"
        hops = [(start, n) for n in grid[0]]
        for i in range(layers - 1):
            hops.extend((a, b) for a in grid[i] for b in grid[i + 1])
        hops.extend((n, target) for n in grid[-1])
        fields = [w.fresh("k", 4) for _ in range(5)]
        policy = [(dom, f, "1", "", "") for f in fields]
        edges = []
        for a, b in hops:
            req, ops = "", ""
            if w.rng.random() < 0.45:
                req = f"{w.rng.choice(['has', 'lacks'])}:{w.rng.choice(fields)}"
            if w.rng.random() < 0.55:
                kind = w.rng.choice(["drop", "add", "rename"])
                f = w.rng.choice(fields)
                ops = f"rename:{f}>{w.rng.choice([x for x in fields if x != f])}" if kind == "rename" else f"{kind}:{f}"
            if b == target:
                req = f"has:{fields[0]}"
            edges.append((w.fresh("q", 6), a, b, req, ops, w.rng.randint(1, 100000)))
        schemas = [start, *(n for row in grid for n in row), target]
        payload = {f: w.rng.randint(1, 9) for f in fields if w.rng.random() < 0.6} | {fields[0]: 1}
        if _reference_plan(Spec(schemas, {target}, edges, policy=policy), start, payload):
            w.schemas += schemas
            w.canonical.add(target)
            w.edges += edges
            w.policy += policy
            w.line(w.who()[0], start, payload)
            return
    raise RuntimeError("no reachable ladder")


def _g_null(w: _World) -> None:
    dom, s = w.domain(3, canonical=1)
    f = w.fresh("f", 4)
    w.policy.append((dom, f, "", "", "present"))
    w.edge(s[0], s[1], f"has:{f}", "", 1)
    w.edge(s[0], s[2], "", "", 3)
    w.edge(s[2], s[1], "", "", 3)
    w.line(w.who()[0], s[0], {f: None, "memo": _val(w.rng)})
    dom, s = w.domain(4)
    a, b = w.fresh("a", 4), w.fresh("b", 4)
    w.policy.append((dom, b, "", "", "present"))
    w.edge(s[0], s[1], "", f"rename:{a}>{b}", 1)
    w.edge(s[1], s[3], f"has:{b}", "", 1)
    w.edge(s[0], s[2], "", "", 2)
    w.edge(s[2], s[3], "", "", 3)
    w.line(w.who()[0], s[0], {a: None, "memo": _val(w.rng)})
    dom, s = w.domain(3, canonical=1)
    g = w.fresh("g", 4)
    w.policy.append((dom, g, "", "", "present"))
    w.edge(s[0], s[1], f"lacks:{g}", "", 1)
    w.edge(s[0], s[2], "", "", 2)
    w.edge(s[2], s[1], "", "", 2)
    w.line(w.who()[0], s[0], {g: None})
    dom, s = w.domain(2)
    i, n, o = w.fresh("i", 4), w.fresh("n", 4), w.fresh("o", 4)
    w.edge(s[0], s[1], "", f"cast:{i}:int;cast:{n}:str;cast:{o}:float", 1)
    w.line(w.who()[0], s[0], {i: float(w.rng.randint(2, 99)), n: None, o: w.rng.random() < 0.5})


def _g_policy(w: _World) -> None:
    dom, s = w.domain(3, canonical=1)
    f = w.fresh("f", 4)
    w.policy.append((dom, f, '"x"', "", ""))
    w.edge(s[0], s[1], f"has:{f}", "", 1)
    w.edge(s[0], s[2], "", "", 2)
    w.edge(s[2], s[1], "", "", 2)
    w.line(w.who()[0], s[0], {f: None, "memo": _val(w.rng)})
    dom, s = w.domain(3, canonical=1)
    h = w.fresh("h", 4)
    w.policy.append((dom, h, "", "", "absent"))
    w.edge(s[0], s[1], f"lacks:{h}", "", 1)
    w.edge(s[0], s[2], "", "", 2)
    w.edge(s[2], s[1], "", "", 2)
    w.line(w.who()[0], s[0], {h: None})
    dom, s = w.domain(2)
    x, y = w.fresh("x", 4), w.fresh("y", 4)
    w.policy += [(dom, x, '"dx"', "absent_or_null", ""), (dom, y, '"dy"', "", "")]
    w.edge(s[0], s[1], "", f"add:{x};add:{y}", 1)
    w.line(w.who()[0], s[0], {x: None, y: None})


def _g_tokens(w: _World) -> None:
    own, empty, old, new = w.partner(), w.partner(), w.partner(), w.partner()
    mark, other = w.rng.sample(["~", "nil", "void", "--"], 2)
    w.partner_tokens[own] = [mark]
    w.partner_tokens[empty] = []
    w.partner_tokens[new] = [other]
    w.merges.append((old, new))
    dom, s = w.simple()
    w.line(own, s[0], {"a": "NULL", "b": mark, "c": _val(w.rng)})
    w.line(w.partners[empty][0], s[0], {"a": "N/A", "c": _val(w.rng)})
    w.line(w.partners[old][0], s[0], {"a": other, "b": "NULL"})
    dom, s = w.domain(3, canonical=1)
    f = w.fresh("f", 4)
    w.policy.append((dom, f, "", "", "absent"))
    w.edge(s[0], s[1], f"has:{f}", "", 1)
    w.edge(s[0], s[2], "", "", 2)
    w.edge(s[2], s[1], "", "", 2)
    w.line(w.who()[0], s[0], {f: "NULL", "memo": _val(w.rng)})


def _g_corr(w: _World) -> None:
    dom, s = w.domain(3)
    f = w.fresh("f", 4)
    w.policy.append((dom, f, "1", "", ""))
    w.edge(s[0], s[1], "", f"drop:{f};add:{f}", 1)
    w.edge(s[1], s[2], f"has:{f}", "", 2)
    partner, pid = w.who()
    key = w.line(partner, s[0], {f: 1, "a": _val(w.rng)})
    w.fix(f"UNSET {w.partners[pid][0]} {key} AT {s[1]} {f}")
    w.fix(f"SET {pid} {key} AT {s[0].rsplit('.v', 1)[0]}.v9 a 1")
    dom, s = w.domain(2)
    g = w.fresh("g", 4)
    w.edge(s[0], s[1], "", f"drop:{g}", 1)
    partner, pid = w.who()
    key = w.line(partner, s[0], {g: _val(w.rng), "a": _val(w.rng)})
    w.fix(f'SET {pid} {key} AT {s[1]} {g} "fixed"')
    dom, s = w.domain(3)
    h = w.fresh("h", 4)
    w.edge(s[0], s[1], "", "", 1)
    w.edge(s[1], s[2], f"lacks:{h}", "", 1)
    partner, pid = w.who()
    key = w.line(partner, s[0], {"a": _val(w.rng)})
    low, high = sorted(w.fresh("C", 5) for _ in range(2))
    w.fix(f"SET {w.partners[pid][0]} {key} AT {s[1]} {h} 5", high)
    w.fix(f"UNSET {pid} {key} AT {s[1]} {h}", low)


def _g_replay(w: _World) -> None:
    dom, s = w.domain(3)
    w.edge(s[0], s[1], "", "drop:z", 1)
    w.edge(s[1], s[2], "", "", 1)
    pid = w.rng.choice(w.pool)
    alias = w.partners[pid][0]
    payload = {"a": _val(w.rng)}
    key = w.line(pid, s[0], payload)
    w.line(alias, s[0], dict(payload), key)
    key = w.line(pid, s[0], {"a": "NULL", "b": 1})
    w.line(pid, s[0], {"a": None, "b": 1}, key)
    key = w.line(pid, s[0], {"a": 1, "z": "x"})
    w.line(pid, s[0], {"a": 1, "z": "y"}, key)
    second = {"a": 2, "b": w.rng.randint(1, 99)}
    key = w.line(pid, s[0], {"a": 1})
    w.line(pid, s[0], second, key)
    w.fix(f"REISSUE {alias} {key} {_fp(s[0], second)[:12]}")
    key = w.fresh("k", 6)
    w.line(pid, s[0], {"a": 1}, key)
    w.line(pid, s[0], {"a": 2}, key, w.batch(seq=w.rng.randint(1, 999)))
    dom, t = w.domain(2)
    f = w.fresh("f", 4)
    w.edge(t[0], t[1], f"has:{f}", "", 1)
    key = w.line(pid, t[0], {"a": 1})
    w.line(alias, t[0], {"a": 1, f: 2}, key)
    w.line(pid, s[0], {"a": w.rng.choice(["caf\u00e9", "Z\u00fcrich", "na\u00efve", "\u00e5rhus"])})


def _g_feed(w: _World) -> None:
    dom, s = w.simple()
    a, b, c, d = (w.partner() for _ in range(4))
    w.merges += [(a, b), (b, c), (c, d)]
    key = w.line(w.partners[a][0], s[0], {"a": _val(w.rng)})
    x, y = w.partner(), w.partner()
    w.merges += [(x, y), (y, x)]
    key = w.line(w.partners[x][0], s[0], {"a": 1})
    w.fix(f"SET {x} {key} AT {s[0]} a 2")
    w.lines.append('{"batch": "' + w.batch() + '", "partner": ')
    w.line(w.who()[0], s[0], {"a": _val(w.rng)})
    w.lines.append("not json")
    w.lines.append({"batch": w.batch(), "partner": w.pool[0], "key": w.fresh("k", 6), "schema": s[0], "payload": [1]})
    w.lines.append({"batch": w.batch(), "partner": w.pool[0], "schema": s[0], "payload": {}})
    w.lines.append(_line("Bnowhere", w.pool[0], w.fresh("k", 6), s[0], {}))
    holder, named = w.partner(), w.partner()
    w.partners[holder].append(named)
    w.line(named, s[0], {"a": _val(w.rng)})
    w.line("ghost" + w.fresh("", 4), s[0], {"a": 1})
    w.line("ghost" + w.fresh("", 4), f"{dom}.v9", {"a": 1})
    w.lines.append(_line(w.fresh("B", 4), "ghost" + w.fresh("", 4), w.fresh("k", 6), s[0], {"a": 1}))
    pid = w.rng.choice(w.pool)
    key = w.line(pid, f"{dom}.v9", {"a": 1})
    w.line(pid, s[0], {"a": 2}, key)


def _g_report(w: _World) -> None:
    names = [w.fresh("ct", 4) for _ in range(6)]
    members = [["failed", "E_UNKNOWN_SCHEMA"], ["E_PREREQ_FAILED", "E_UNKNOWN_SCHEMA", "E_UNREACHABLE"], ["migrated", "superseded"],
               ["E_INVALID_CORRECTION"], ["replayed", "E_REPLAY_CONFLICT"], ["rejected", "E_PARSE", "E_UNKNOWN_PARTNER", "E_ALIAS_CYCLE"]]
    w.taxonomy = {"categories": [{"name": n, "members": m} for n, m in zip(names, members)]}
    everyone = sorted(w.partners)
    for pid in w.rng.sample(everyone, len(everyone) // 2):
        w.order[pid] = w.rng.randint(1, 500)


def _g_reject(w: _World) -> None:
    dom, s = w.simple()
    x, y = w.partner(), w.partner()
    w.merges += [(x, y), (y, x)]
    batch = w.batch()
    w.line(w.who()[0], s[0], {"a": _val(w.rng)}, batch=batch)
    w.line("ghost" + w.fresh("", 4), s[0], {"a": _val(w.rng)}, batch=batch)
    w.line(w.who()[0], s[0], {"a": _val(w.rng), "b": _val(w.rng)}, batch=batch)
    w.line(w.partners[y][0], s[0], {"a": _val(w.rng)}, batch=batch)
    w.line(x, s[0], {"a": 1}, batch=w.batch())


def _g_scope(w: _World) -> None:
    dom, s = w.simple()
    batch = w.batch()
    w.line(w.who()[0], s[0], {"a": _val(w.rng)}, batch=batch)
    w.lines.append({"batch": batch, "partner": w.pool[1], "key": w.fresh("k", 6), "schema": s[0], "payload": [w.rng.randint(1, 9)]})
    w.line(w.who()[0], s[1], {"a": _val(w.rng)}, batch=batch)
    w.lines.append({"batch": batch, "partner": w.pool[2], "key": w.fresh("k", 6), "schema": "", "payload": {"a": 1}})
    w.lines.append({"batch": w.batch(), "partner": w.pool[3], "schema": s[0], "payload": {"a": 2}})
    w.line(w.who()[0], s[0], {"a": _val(w.rng)}, batch=batch)


def _g_pad(w: _World) -> None:
    dom, s = w.simple()
    own = w.partner()
    mark = w.rng.choice(["~", "nil", "void", "--"])
    w.partner_tokens[own] = [mark, "NULL"]
    w.line(w.who()[0], s[0], {"a": " NULL", "b": "N/A ", "c": "NULL", "d": _val(w.rng)})
    w.line(own, s[0], {"a": mark + " ", "b": " " + mark, "c": mark, "d": " N/A"})
    dom, s = w.domain(3, canonical=1)
    f = w.fresh("f", 4)
    w.policy.append((dom, f, "", "", "absent"))
    w.edge(s[0], s[1], f"has:{f}", "", 1)
    w.edge(s[0], s[2], "", "", 2)
    w.edge(s[2], s[1], "", "", 2)
    w.line(w.who()[0], s[0], {f: w.rng.choice([" NULL", "N/A ", " N/A "]), "memo": _val(w.rng)})
    w.line(w.partners[own][0], s[0], {f: mark + " ", "memo": "NULL"})


def _g_core(w: _World, number: int, stream: int = 5000, degree: int = 4) -> None:
    """One large domain: a priced corridor to the canonical schema beside a cheap region whose exits are dear."""
    rng = _rng(stream + number)
    for _ in range(40):
        dom = w.fresh("cr")
        fields = sorted(w.fresh("k", 4) for _ in range(10))
        need, carry, idle = rng.sample(fields, 3)
        prereq = [f for f in fields if f not in (carry, idle)]
        others = [f for f in prereq if f != need]
        rows, lanes = rng.randint(10, 12), 3
        zone_size = rng.randint(1100, 1196 - rows * lanes)
        names = iter(rng.sample(range(1, 1201), 4 + rows * lanes + zone_size))
        sch = lambda: f"{dom}.v{next(names)}"
        start, plant, side, target = sch(), sch(), sch(), sch()
        grid = [[sch() for _ in range(lanes)] for _ in range(rows)]
        zone = [sch() for _ in range(zone_size)]
        edges: list[tuple] = []

        def edge(a, b, req, ops, cost):
            edges.append((w.fresh("q", 6), a, b, req, ops, cost))

        def req_text(chance, pool):
            return f"{rng.choice(['has', 'lacks'])}:{rng.choice(pool)}" if rng.random() < chance else ""

        def op_text(pool):
            kind = rng.choice(["rename", "rename", "add", "drop"])
            f = rng.choice(pool)
            return f"rename:{f}>{rng.choice([x for x in pool if x != f])}" if kind == "rename" else f"{kind}:{f}"

        cheap = rng.randint(2000, 9000)
        edge(start, plant, "", f"drop:{carry}", cheap)
        edge(start, plant, "", "", cheap + 500)
        for b in grid[0]:
            edge(plant, b, "", f"rename:{carry}>{need}", rng.randint(2000, 9000))
        for i in range(rows - 1):
            for a in grid[i]:
                for b in grid[i + 1]:
                    ops = op_text(others) if rng.random() < 0.4 else ""
                    if ops.startswith("rename"):
                        ops = ""
                    edge(a, b, req_text(0.35, others), ops, rng.randint(2000, 9000))
        for a in grid[-1]:
            edge(a, target, f"has:{need}", "", rng.randint(2000, 9000))
            edge(a, side, "", f"add:{need}", 20000)
        edge(side, target, f"has:{need}", "", 1)
        edge(start, target, "", "", 40_000_000)
        for a in [start, plant, *(n for row in grid[: rows // 2] for n in row)]:
            for _ in range(2):
                edge(a, rng.choice(zone), "", op_text(fields), rng.randint(1, 5))
        for a in zone:
            for _ in range(degree):
                ops = ";".join(op_text(fields) for _ in range(rng.randint(1, 2)))
                edge(a, rng.choice(zone), req_text(0.25, prereq), ops, rng.randint(1, 4))
        for a in rng.sample(zone, 6):
            edge(a, target, "", "", rng.randint(9_000_000, 9_900_000))
        policy = []
        for n, f in enumerate(fields):
            fill = "absent_or_null" if n % 3 == 0 else ""
            counts = "absent" if (n % 4 == 1 and f != need) else ""
            policy.append((dom, f, str(rng.randint(1, 9)), fill, counts))
        if len(edges) > 6000:
            continue
        rng.shuffle(edges)
        schemas = [start, plant, side, target, *(n for row in grid for n in row), *zone]
        spec = Spec(schemas, {target}, edges, policy=policy)
        hard = {carry: rng.randint(10, 99)}
        for f in rng.sample(others, 5):
            hard[f] = None
        for f in others:
            if f not in hard and rng.random() < 0.7:
                hard[f] = _val(rng)
        plan = _reference_plan(spec, start, hard)
        by_id = {e[0]: e for e in edges}
        if not plan or len(plan) > 80:
            continue
        cost = sum(int(by_id[x][5]) for x in plan)
        if cost >= 1_000_000 or by_id[plan[0]][4] != "" or side in {by_id[x][2] for x in plan}:
            continue
        easy = []
        for _ in range(3):
            here = rng.choice([n for row in grid[rows // 2:] for n in row])
            payload = {f: _val(rng) for f in fields if rng.random() < 0.5}
            for f in [f for f in fields if f not in payload and rng.random() < 0.3]:
                payload[f] = None
            easy.append((here, payload))
        assert len(schemas) <= 1200 and len(edges) <= 6000 and len(fields) <= 10 and len(plan) <= 80
        assert len({r.split(":")[1] for e in edges for r in filter(None, e[3].split(";"))}) <= 8
        assert all(isinstance(e[5], int) and e[5] > 0 for e in edges)
        w.schemas += schemas
        w.canonical.add(target)
        w.edges += edges
        w.policy += policy
        partner = w.pool[0]
        w.line(partner, start, hard)
        for here, payload in easy:
            w.line(partner, here, payload)
        return
    raise RuntimeError("no core instance")


_LATE_GADGETS = {"REJECT": _g_reject, "SCOPE": _g_scope, "PAD": _g_pad}

_GADGETS = {"STATE": _g_state, "TIE": _g_tie, "SCALE": _g_scale, "NULL": _g_null, "POLICY": _g_policy,
            "TOKENS": _g_tokens, "CORR": _g_corr, "REPLAY": _g_replay, "FEED": _g_feed}

WORLDS: dict[str, tuple[str, ...]] = {
    "world_01_state_null_corrections_summary": ("STATE", "NULL", "CORR", "REPORT"),
    "world_02_tie_tokens_replay_feed": ("TIE", "TOKENS", "REPLAY", "FEED"),
    "world_03_state_policy_tokens_corrections": ("STATE", "POLICY", "TOKENS", "CORR"),
    "world_04_scale_state_replay_summary": ("SCALE", "STATE", "REPLAY", "REPORT"),
    "world_05_null_policy_replay_cli": ("NULL", "POLICY", "REPLAY", "CLI"),
    "world_06_tie_corrections_feed_summary": ("TIE", "CORR", "FEED", "REPORT"),
    "world_07_state_tie_null_tokens_summary": ("STATE", "TIE", "NULL", "TOKENS", "REPORT"),
    "world_08_scale_policy_corrections_feed": ("SCALE", "POLICY", "CORR", "FEED"),
    "world_09_policy_tokens_replay_corrections_cli": ("POLICY", "TOKENS", "REPLAY", "CORR", "CLI"),
    "world_10_state_feed_replay_summary": ("STATE", "FEED", "REPLAY", "REPORT"),
    "world_11_null_tie_corrections_cli": ("NULL", "TIE", "CORR", "CLI"),
    "world_12_scale_tokens_null_summary": ("SCALE", "TOKENS", "NULL", "REPORT"),
    "world_13_state_policy_feed_cli": ("STATE", "POLICY", "FEED", "CLI"),
    "world_14_tie_policy_replay_summary": ("TIE", "POLICY", "REPLAY", "REPORT"),
    "world_15_scale_corrections_tokens_feed": ("SCALE", "CORR", "TOKENS", "FEED"),
    "world_16_null_state_replay_corrections": ("NULL", "STATE", "REPLAY", "CORR"),
    "world_17_tie_policy_null_feed_summary": ("TIE", "POLICY", "NULL", "FEED", "REPORT"),
    "world_18_scale_tie_replay_cli": ("SCALE", "TIE", "REPLAY", "CLI"),
    "world_19_state_tokens_corrections_replay_feed_summary": ("STATE", "TOKENS", "CORR", "REPLAY", "FEED", "REPORT"),
    "world_20_reject_pad_state_corrections": ("STATE", "CORR", "REJECT", "PAD"),
    "world_21_scope_damage_null_replay": ("NULL", "REPLAY", "SCOPE", "DAMAGE"),
    "world_22_reject_scope_feed_summary": ("FEED", "REPORT", "REJECT", "SCOPE"),
    "world_23_pad_damage_tokens_policy": ("TOKENS", "POLICY", "PAD", "DAMAGE"),
    "world_24_reject_damage_tie_cli": ("TIE", "CLI", "REJECT", "DAMAGE"),
    "world_25_scope_pad_corrections_summary": ("CORR", "REPORT", "SCOPE", "PAD"),
    "world_26_reject_scope_pad_damage": ("REPLAY", "REJECT", "SCOPE", "PAD", "DAMAGE"),
    "world_27_pad_scope_state_tokens_cli": ("STATE", "TOKENS", "CLI", "PAD", "SCOPE"),
    "world_28_damage_reject_scale_replay": ("SCALE", "REPLAY", "DAMAGE", "REJECT"),
    "world_29_core_large_graph": ("CORE",),
    "world_30_core_large_graph": ("CORE",),
    "world_31_core_large_graph": ("CORE",),
    "world_32_core_large_graph": ("CORE",),
    "world_33_core_large_graph": ("CORE",),
    "world_34_core_large_graph": ("CORE",),
    "world_35_core_large_graph": ("CORE",),
    "world_36_core_large_graph": ("CORE",),
    "world_37_core_large_graph": ("CORE",),
    "world_38_core_large_graph": ("CORE",),
    "world_39_core_large_graph": ("CORE",),
    "world_40_core_large_graph": ("CORE",),
    "world_41_core_large_graph": ("CORE",),
    "world_42_core_large_graph": ("CORE",),
    "world_43_core_large_graph": ("CORE",),
    "world_44_core_large_graph": ("CORE",),
    "world_45_core_large_graph": ("CORE",),
    "world_46_core_large_graph": ("CORE",),
}

# The receipt and token cases every world from 01 to 19 also carries.
_PAIRS = [("REJECT", "PAD"), ("SCOPE", "DAMAGE"), ("REJECT", "SCOPE"), ("PAD", "DAMAGE"), ("REJECT", "DAMAGE"), ("SCOPE", "PAD")]


def _levers(name: str) -> tuple[str, ...]:
    index = list(WORLDS).index(name)
    return WORLDS[name] + (_PAIRS[index % len(_PAIRS)] if index < 19 else ())


def _world(name: str) -> tuple[Spec, list, dict[str, int], list[str], dict[str, list]]:
    if ("world", name) not in _CACHE:
        levers = _levers(name)
        w = _World(100 + list(WORLDS).index(name), levers)
        if "CORE" in levers:
            number = list(WORLDS).index(name) + 1
            _g_core(w, number, *((7000, 5) if number > 36 else ()))
            _CACHE[("world", name)] = w.finish()
            return _CACHE[("world", name)]
        for lever in levers:
            if lever in _GADGETS:
                _GADGETS[lever](w)
        _filler(w, 16)
        for lever in levers:
            if lever in _LATE_GADGETS:
                _LATE_GADGETS[lever](w)
        if "REPORT" in levers:
            _g_report(w)
        _CACHE[("world", name)] = w.finish()
    return _CACHE[("world", name)]


def _world_expected(name: str) -> dict:
    if ("expected", name) not in _CACHE:
        spec, lines, seqs, corrections, receipts = _world(name)
        _CACHE[("expected", name)] = _ref_pipeline(spec, _feed_text(lines), seqs, _corrections_text(corrections), receipts)
    return _CACHE[("expected", name)]


def _cli_outputs(job: dict) -> dict:
    cwd = _scratch("cli-")
    shutil.copytree(job["contracts"], cwd / "inputs")
    for path in [cwd / "inputs", *(cwd / "inputs").iterdir()]:
        path.chmod(0o755 if path.is_dir() else 0o644)
    args = ["run", "--contracts", "inputs", "--feed", "inputs/feed_input.jsonl", "--corrections", "inputs/corrections_input.txt",
            "--manifest", "inputs/manifest_input.csv", "--out", "result"]
    done = _run([sys.executable, "-m", PACKAGE, *args], cwd, _delivered_repo(), 120)
    if done.returncode != 0:
        raise RuntimeError(done.stderr[-400:])
    records = [json.loads(x) for x in (cwd / "result" / "records.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    return {"records": records, "summary": json.loads((cwd / "result" / "run_summary.json").read_text(encoding="utf-8"))}


def _world_holds(name: str) -> bool:
    levers = WORLDS[name]
    spec, lines, seqs, corrections, receipts = _world(name)
    expected = _world_expected(name)
    job = _feed_job(spec, lines, seqs, corrections, receipts)
    if "CLI" in levers:
        result = _cli_outputs(job)
    else:
        result = _child(job, timeout=TIME_LIMIT_SEC * len(lines) + 20 if "CORE" in levers else TIME_LIMIT_SEC + 20 if "SCALE" in levers else 60.0)
    return _same(result["records"], expected["records"]) and _same(result["summary"], expected["summary"])


def _hidden_edge_ids() -> set[str]:
    found: set[str] = set()
    for build in (case_revisit, case_tie_first_edge):
        found.update(e[0] for e in build()[0].edges)
    for args in LADDERS.values():
        found.update(e[0] for e in _ladder(*args)[0].edges)
    for name in WORLDS:
        found.update(e[0] for e in _world(name)[0].edges)
    return found


# ----------------------------------------------------------------------------- check helpers

_DIFFS: list[str] = []


def _first_difference(left: Any, right: Any, path: str = "$") -> str:
    """Path of the first place where the delivered value departs from the expected one."""
    if isinstance(left, dict) and isinstance(right, dict):
        for key in sorted(set(left) | set(right), key=str):
            if key not in left or key not in right:
                return f"{path}.{key} (present on one side only)"
            if json.dumps(left[key], sort_keys=True) != json.dumps(right[key], sort_keys=True):
                return _first_difference(left[key], right[key], f"{path}.{key}")
    if isinstance(left, list) and isinstance(right, list):
        for index, (one, two) in enumerate(zip(left, right)):
            if json.dumps(one, sort_keys=True) != json.dumps(two, sort_keys=True):
                return _first_difference(one, two, f"{path}[{index}]")
        if len(left) != len(right):
            return f"{path} (length {len(left)}, expected {len(right)})"
    shown = json.dumps(left, sort_keys=True)[:160]
    wanted = json.dumps(right, sort_keys=True)[:160]
    return f"{path}: got {shown}, expected {wanted}"


def _same(left: Any, right: Any) -> bool:
    """Equal as JSON text, so 1 and 1.0 or True and 1 count as different."""
    if json.dumps(left, sort_keys=True) == json.dumps(right, sort_keys=True):
        return True
    _DIFFS.append(_first_difference(left, right))
    return False


def _holds(check) -> bool:
    """Run one check and print a single [check] line naming the first difference on failure."""
    name = sys._getframe(1).f_code.co_name
    _DIFFS.clear()
    try:
        passed = bool(check())
        detail = "" if passed else (_DIFFS[0] if _DIFFS else "condition not met")
    except Exception as error:
        passed, detail = False, f"{type(error).__name__}: {str(error)[:200]}"
    print("[check] " + json.dumps({"name": name, "passed": passed, "first_difference": detail}), flush=True)
    return passed


def _plan_case(build) -> bool:
    spec, job, expected = build()
    result = _child(dict(job, contracts=str(spec.write())))
    if isinstance(expected, str):
        return _same(result, {"error": expected})
    return _same(result, {"ok": expected})


def _ladder_case(name: str) -> bool:
    spec, job, expected = case_ladder(name)
    if expected is None:
        return False
    result = _child(dict(job, contracts=str(spec.write())), timeout=TIME_LIMIT_SEC + 10)
    return _same(result, {"ok": expected})


def _exec_case(build) -> bool:
    spec, job, expected = build()
    result = _child(dict(job, contracts=str(spec.write())))
    if "status" in expected:
        return _same(result, {"ok": expected})
    return result.get("ok", {}).get("status") == "migrated" and _same(result["ok"].get("payload"), expected)


def _json_artifact(name: str) -> Any:
    return json.loads((OUT_DIR / name).read_text(encoding="utf-8"))


def _visible_job() -> dict:
    ci = _ci_dir()
    return {"op": "pipeline", "contracts": str(ci), "feed": str(ci / "partner_batches.jsonl"),
            "corrections": str(ci / "correction_log.txt"), "manifest": str(ci / "replay_manifest.csv")}


def _code_dump(node: ast.AST) -> str:
    """ast dump of a function without its docstring, so a docstring edit is no code change."""
    body = list(node.body)
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
        body = body[1:] or [ast.Pass()]
    node.body = body
    return ast.dump(node)


def _function_nodes(repo: Path) -> dict[str, str]:
    """Dotted name (relative to migrakit) -> code dump of every function and method."""
    found: dict[str, str] = {}
    base = repo / "src" / PACKAGE
    for path in sorted(base.rglob("*.py")):
        module = ".".join(path.relative_to(base).with_suffix("").parts)
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                found[f"{module}.{node.name}"] = _code_dump(node)
            elif isinstance(node, ast.ClassDef):
                for inner in node.body:
                    if isinstance(inner, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        found[f"{module}.{node.name}.{inner.name}"] = _code_dump(inner)
    return found


AREAS = {"core": ("core.", "pipeline."), "parser": ("parser.", "cli.", "__main__."), "report": ("report.",)}
# The contract areas (K19); every changed or added function in one of them must be listed.
CONTRACT_AREAS = {"core": ("core.", "pipeline."), "parser": ("parser.", "cli."), "report": ("report.",)}


def _module_claims(area: str) -> bool:
    note = _json_artifact(f"module_{area}.json")
    names = note["changed_functions"]
    if note["module"] != area or not isinstance(note["notes"], list) or not names or names != sorted(set(names)):
        return False
    delivered = _function_nodes(_delivered_repo())
    shipped = _function_nodes(_shipped_repo())
    for name in names:
        if not isinstance(name, str) or not name.startswith(AREAS[area]) or name not in delivered:
            return False
        if shipped.get(name) == delivered[name]:
            return False
    required = {name for name, body in delivered.items() if name.startswith(CONTRACT_AREAS[area]) and shipped.get(name) != body}
    return required <= set(names)


def _unit_results(repo: Path) -> dict[str, str]:
    if ("unit", str(repo)) in _CACHE:
        return _CACHE[("unit", str(repo))]
    cwd = _scratch("unit-")
    work = cwd / "repo"
    shutil.copytree(repo, work)
    for path in [work, *work.rglob("*")]:
        path.chmod(0o755 if path.is_dir() else 0o644)
    done = _run([sys.executable, "-m", "unittest", "discover", "-v", "-s", "tests"], work, work, 120)
    results: dict[str, str] = {}
    for line in done.stderr.splitlines():
        head = line.split(" (", 1)[0].strip()
        if head in VISIBLE_TESTS and " ... " in line:
            results[head] = "pass" if line.rstrip().endswith("ok") else "fail"
    _CACHE[("unit", str(repo))] = {name: results.get(name, "fail") for name in VISIBLE_TESTS}
    return _CACHE[("unit", str(repo))]


# ----------------------------------------------------------------------------- checks

@criterion(description="Every declared artifact exists under /app/out.")
def artifacts_exist(workspace: Path) -> bool:
    return _holds(lambda: all((OUT_DIR / Path(a).name).is_file() for a in ARTIFACTS))


@criterion(description="Detects an unsafe file member in patched-repo.zip.")
def negative_unsafe_archive_members(workspace: Path) -> bool:
    def check() -> bool:  # Inverted polarity: True means the archive holds an absolute, `..` or directory member.
        with zipfile.ZipFile(OUT_DIR / "patched-repo.zip") as zf:
            names = zf.namelist()
        return any(n.startswith("/") or ".." in Path(n).parts or n.endswith("/") for n in names)
    return _holds(check)


@criterion(description="patched-repo.zip contains the K1 src layout and visible tests.")
def archive_src_layout(workspace: Path) -> bool:
    def check() -> bool:
        with zipfile.ZipFile(OUT_DIR / "patched-repo.zip") as zf:
            names = zf.namelist()
        return {"pyproject.toml", "src/migrakit/__init__.py", "tests/test_visible.py"} <= set(names)
    return _holds(check)


@criterion(description="The delivered package exposes every documented entry point from a foreign working directory.")
def api_entry_points_importable(workspace: Path) -> bool:
    spec = Spec(["dmx.v1", "dmx.v2"], {"dmx.v2"}, [])
    return _holds(lambda: _same(_child({"op": "api", "contracts": str(spec.write()), "names": API_NAMES}), {"ok": API_NAMES}))


@criterion(description="The nine visible repository tests pass when run from the extracted patched-repo.zip.")
def visible_repo_tests_pass_from_archive(workspace: Path) -> bool:
    return _holds(lambda: set(_unit_results(_delivered_repo()).values()) == {"pass"})


@criterion(description="summary.json equals the run summary the delivered package produces for the shipped inputs.")
def summary_json_matches_delivered_run(workspace: Path) -> bool:
    return _holds(lambda: _same(_json_artifact("summary.json"), _child(_visible_job(), timeout=300)["summary"]))


@criterion(description="module_core.json lists only core functions whose code differs from the shipped repository.")
def module_core_claims_match_archive(workspace: Path) -> bool:
    return _holds(lambda: _module_claims("core"))


@criterion(description="module_parser.json lists only parser functions whose code differs from the shipped repository.")
def module_parser_claims_match_archive(workspace: Path) -> bool:
    return _holds(lambda: _module_claims("parser"))


@criterion(description="module_report.json lists only report functions whose code differs from the shipped repository.")
def module_report_claims_match_archive(workspace: Path) -> bool:
    return _holds(lambda: _module_claims("report"))


@criterion(description="test_fixes.json records the real before and after result of each visible test.")
def test_fixes_matches_visible_test_runs(workspace: Path) -> bool:
    def check() -> bool:
        before, after = _unit_results(_shipped_repo()), _unit_results(_delivered_repo())
        wanted = [{"name": n, "before": before[n], "after": after[n]} for n in VISIBLE_TESTS]
        return _same(_json_artifact("test_fixes.json"), {"visible_tests": wanted})
    return _holds(check)


@criterion(description="repair-report.json names the package, lists fixes and at least one passed check.")
def repair_report_well_formed(workspace: Path) -> bool:
    def check() -> bool:
        report = _json_artifact("repair-report.json")
        fixes, checks = report["fixes"], report["checks"]
        return (report["package"] == PACKAGE and fixes and all(isinstance(f, str) and f.strip() for f in fixes)
                and all(isinstance(c["name"], str) and isinstance(c["passed"], bool) for c in checks) and any(c["passed"] for c in checks))
    return _holds(check)


@criterion(description="state_signature reports an explicit null field as null, apart from an absent field.")
def signature_keeps_explicit_null(workspace: Path) -> bool:
    def check() -> bool:
        spec, job, expected = case_signature()
        return _same(_child(dict(job, contracts=str(spec.write()))), {"ok": expected})
    return _holds(check)


@criterion(description="state_signature called on an unknown schema id raises E_UNKNOWN_SCHEMA.")
def signature_rejects_unknown_schema(workspace: Path) -> bool:
    def check() -> bool:
        spec, job, _ = case_signature()
        return _same(_child(dict(job, contracts=str(spec.write()), schema=job["schema"] + "9")), {"error": "E_UNKNOWN_SCHEMA"})
    return _holds(check)


@criterion(description="The cheapest plan passes the source schema twice after a state change and the planner returns it.")
def plan_revisits_schema_with_new_state(workspace: Path) -> bool:
    return _holds(lambda: _plan_case(case_revisit))


@criterion(description="Among equal-cost plans the smallest edge-id list wins even when it has more edges.")
def plan_tie_first_edge_decides(workspace: Path) -> bool:
    return _holds(lambda: _plan_case(case_tie_first_edge))


@criterion(description="Forty-five-layer ladder with state-dependent edges is planned within the time limit.")
def ladder_large_state(workspace: Path) -> bool:
    return _holds(lambda: _ladder_case("ladder_large_state"))


@criterion(description="add fills absent fields, and explicit nulls only where the fill mode allows it.")
def exec_add_fill_absent_vs_null(workspace: Path) -> bool:
    return _holds(lambda: _exec_case(case_fill))


@criterion(description="A correction pinned to a schema the plan revisits applies on the first arrival only, so a later has check fails.")
def exec_correction_first_arrival_only(workspace: Path) -> bool:
    return _holds(lambda: _exec_case(case_first_arrival))


@criterion(description="resolve_partner follows the merge chain to its final partner.")
def identity_merge_chain_followed(workspace: Path) -> bool:
    return _holds(lambda: _plan_case(case_merge_chain))


@criterion(description="resolve_partner rejects a merge loop.")
def identity_merge_loop_rejected(workspace: Path) -> bool:
    return _holds(lambda: _plan_case(case_merge_loop))


@criterion(description="resolve_partner gives a partner id precedence over an equal alias.")
def identity_partner_id_beats_alias(workspace: Path) -> bool:
    return _holds(lambda: _plan_case(case_partner_precedence))


@criterion(description="run_pipeline gives each rejected line its catalogue code, including merge loops and state-unreachable lines.")
def pipe_rejection_codes(workspace: Path) -> bool:
    def check() -> bool:
        job, expected = case_rejection_codes()
        records = _child(job)["records"]
        found = {str(r["line"]): r["code"] for r in records if r["status"] == "rejected"}
        return _same(found, expected)
    return _holds(check)


@criterion(description="run_pipeline keeps processing after lines that are not JSON and leaves their identity fields null.")
def pipe_bad_lines_run_continues(workspace: Path) -> bool:
    def check() -> bool:
        job, expected = case_bad_lines()
        records = _child(job)["records"]
        if not _same([(r["status"], r["payload"]) for r in records], expected):
            return False
        bad = [r for r in records if r["code"] == "E_PARSE"]
        return len(bad) == 3 and all(r[k] is None for r in bad for k in ("batch", "partner", "key", "schema", "fingerprint"))
    return _holds(check)


@criterion(description="run_pipeline lists the batches whose receipt differs, counting only records that keep their batch.")
def receipt_skips_lines_rejected_at_parse(workspace: Path) -> bool:
    def check() -> bool:
        job, expected = case_receipt_scope()
        return _same(_child(job)["summary"]["receipt_mismatches"], expected)
    return _holds(check)


@criterion(description="The batch receipt covers lines rejected at the partner stage, whose records keep a null fingerprint.")
def receipt_counts_partner_rejected_lines(workspace: Path) -> bool:
    def check() -> bool:
        job, expected, rejected = case_receipt_rejected()
        result = _child(job)
        prints = [r["fingerprint"] for r in result["records"] if r["line"] in rejected]
        return _same(result["summary"]["receipt_mismatches"], expected) and prints == [None] * len(rejected)
    return _holds(check)


@criterion(description="run_pipeline turns a payload string into null only when it equals one of the partner's tokens exactly.")
def tokens_match_exactly(workspace: Path) -> bool:
    def check() -> bool:
        job, expected = case_tokens_exact()
        return _same([(r["status"], r["code"], r["payload"]) for r in _child(job)["records"]], expected)
    return _holds(check)


@criterion(description="build_summary assigns each record to a category by its code first, in taxonomy order.")
def summary_categories_code_first(workspace: Path) -> bool:
    def check() -> bool:
        spec, job, expected = case_categories()
        return _same(_child(dict(job, contracts=str(spec.write())))["ok"]["by_category"], expected)
    return _holds(check)


@criterion(description="build_summary lists ranked partners by rank, then the unranked ones by id.")
def summary_partner_order_by_rank(workspace: Path) -> bool:
    def check() -> bool:
        spec, job, expected = case_partner_order()
        return _same(_child(dict(job, contracts=str(spec.write())))["ok"]["partners"], expected)
    return _holds(check)


@criterion(description="Hidden world run through run_pipeline; the records file and the run summary are compared whole with the contract result.")
def world_01_state_null_corrections_summary(workspace: Path) -> bool:
    return _holds(lambda: _world_holds("world_01_state_null_corrections_summary"))


@criterion(description="Hidden world run through run_pipeline; the records file and the run summary are compared whole with the contract result.")
def world_02_tie_tokens_replay_feed(workspace: Path) -> bool:
    return _holds(lambda: _world_holds("world_02_tie_tokens_replay_feed"))


@criterion(description="Hidden world run through run_pipeline; the records file and the run summary are compared whole with the contract result.")
def world_03_state_policy_tokens_corrections(workspace: Path) -> bool:
    return _holds(lambda: _world_holds("world_03_state_policy_tokens_corrections"))


@criterion(description="Hidden world run through run_pipeline; the records file and the run summary are compared whole with the contract result.")
def world_04_scale_state_replay_summary(workspace: Path) -> bool:
    return _holds(lambda: _world_holds("world_04_scale_state_replay_summary"))


@criterion(description="Hidden world run through the command line; the records file and the run summary are compared whole with the contract result.")
def world_05_null_policy_replay_cli(workspace: Path) -> bool:
    return _holds(lambda: _world_holds("world_05_null_policy_replay_cli"))


@criterion(description="Hidden world run through run_pipeline; the records file and the run summary are compared whole with the contract result.")
def world_06_tie_corrections_feed_summary(workspace: Path) -> bool:
    return _holds(lambda: _world_holds("world_06_tie_corrections_feed_summary"))


@criterion(description="Hidden world run through run_pipeline; the records file and the run summary are compared whole with the contract result.")
def world_07_state_tie_null_tokens_summary(workspace: Path) -> bool:
    return _holds(lambda: _world_holds("world_07_state_tie_null_tokens_summary"))


@criterion(description="Hidden world run through run_pipeline; the records file and the run summary are compared whole with the contract result.")
def world_08_scale_policy_corrections_feed(workspace: Path) -> bool:
    return _holds(lambda: _world_holds("world_08_scale_policy_corrections_feed"))


@criterion(description="Hidden world run through the command line; the records file and the run summary are compared whole with the contract result.")
def world_09_policy_tokens_replay_corrections_cli(workspace: Path) -> bool:
    return _holds(lambda: _world_holds("world_09_policy_tokens_replay_corrections_cli"))


@criterion(description="Hidden world run through run_pipeline; the records file and the run summary are compared whole with the contract result.")
def world_10_state_feed_replay_summary(workspace: Path) -> bool:
    return _holds(lambda: _world_holds("world_10_state_feed_replay_summary"))


@criterion(description="Hidden world run through the command line; the records file and the run summary are compared whole with the contract result.")
def world_11_null_tie_corrections_cli(workspace: Path) -> bool:
    return _holds(lambda: _world_holds("world_11_null_tie_corrections_cli"))


@criterion(description="Hidden world run through run_pipeline; the records file and the run summary are compared whole with the contract result.")
def world_12_scale_tokens_null_summary(workspace: Path) -> bool:
    return _holds(lambda: _world_holds("world_12_scale_tokens_null_summary"))


@criterion(description="Hidden world run through the command line; the records file and the run summary are compared whole with the contract result.")
def world_13_state_policy_feed_cli(workspace: Path) -> bool:
    return _holds(lambda: _world_holds("world_13_state_policy_feed_cli"))


@criterion(description="Hidden world run through run_pipeline; the records file and the run summary are compared whole with the contract result.")
def world_14_tie_policy_replay_summary(workspace: Path) -> bool:
    return _holds(lambda: _world_holds("world_14_tie_policy_replay_summary"))


@criterion(description="Hidden world run through run_pipeline; the records file and the run summary are compared whole with the contract result.")
def world_15_scale_corrections_tokens_feed(workspace: Path) -> bool:
    return _holds(lambda: _world_holds("world_15_scale_corrections_tokens_feed"))


@criterion(description="Hidden world run through run_pipeline; the records file and the run summary are compared whole with the contract result.")
def world_16_null_state_replay_corrections(workspace: Path) -> bool:
    return _holds(lambda: _world_holds("world_16_null_state_replay_corrections"))


@criterion(description="Hidden world run through run_pipeline; the records file and the run summary are compared whole with the contract result.")
def world_17_tie_policy_null_feed_summary(workspace: Path) -> bool:
    return _holds(lambda: _world_holds("world_17_tie_policy_null_feed_summary"))


@criterion(description="Hidden world run through the command line; the records file and the run summary are compared whole with the contract result.")
def world_18_scale_tie_replay_cli(workspace: Path) -> bool:
    return _holds(lambda: _world_holds("world_18_scale_tie_replay_cli"))


@criterion(description="Hidden world run through run_pipeline; the records file and the run summary are compared whole with the contract result.")
def world_19_state_tokens_corrections_replay_feed_summary(workspace: Path) -> bool:
    return _holds(lambda: _world_holds("world_19_state_tokens_corrections_replay_feed_summary"))


def _archive_sources() -> str:
    return "\n".join(p.read_text(encoding="utf-8", errors="ignore") for p in sorted(_delivered_repo().rglob("*.py")))


@criterion(description="Hidden world run through run_pipeline; the records file and the run summary are compared whole with the contract result.")
def world_20_reject_pad_state_corrections(workspace: Path) -> bool:
    return _holds(lambda: _world_holds("world_20_reject_pad_state_corrections"))


@criterion(description="Hidden world run through run_pipeline; the records file and the run summary are compared whole with the contract result.")
def world_21_scope_damage_null_replay(workspace: Path) -> bool:
    return _holds(lambda: _world_holds("world_21_scope_damage_null_replay"))


@criterion(description="Hidden world run through run_pipeline; the records file and the run summary are compared whole with the contract result.")
def world_22_reject_scope_feed_summary(workspace: Path) -> bool:
    return _holds(lambda: _world_holds("world_22_reject_scope_feed_summary"))


@criterion(description="Hidden world run through run_pipeline; the records file and the run summary are compared whole with the contract result.")
def world_23_pad_damage_tokens_policy(workspace: Path) -> bool:
    return _holds(lambda: _world_holds("world_23_pad_damage_tokens_policy"))


@criterion(description="Hidden world run through the command line; the records file and the run summary are compared whole with the contract result.")
def world_24_reject_damage_tie_cli(workspace: Path) -> bool:
    return _holds(lambda: _world_holds("world_24_reject_damage_tie_cli"))


@criterion(description="Hidden world run through run_pipeline; the records file and the run summary are compared whole with the contract result.")
def world_25_scope_pad_corrections_summary(workspace: Path) -> bool:
    return _holds(lambda: _world_holds("world_25_scope_pad_corrections_summary"))


@criterion(description="Hidden world run through run_pipeline; the records file and the run summary are compared whole with the contract result.")
def world_26_reject_scope_pad_damage(workspace: Path) -> bool:
    return _holds(lambda: _world_holds("world_26_reject_scope_pad_damage"))


@criterion(description="Hidden world run through the command line; the records file and the run summary are compared whole with the contract result.")
def world_27_pad_scope_state_tokens_cli(workspace: Path) -> bool:
    return _holds(lambda: _world_holds("world_27_pad_scope_state_tokens_cli"))


@criterion(description="Hidden world run through run_pipeline; the records file and the run summary are compared whole with the contract result.")
def world_28_damage_reject_scale_replay(workspace: Path) -> bool:
    return _holds(lambda: _world_holds("world_28_damage_reject_scale_replay"))


@criterion(description="Hidden world with a large migration graph run through run_pipeline; the records file and the run summary are compared whole with the contract result.")
def world_29_core_large_graph(workspace: Path) -> bool:
    return _holds(lambda: _world_holds("world_29_core_large_graph"))


@criterion(description="Hidden world with a large migration graph run through run_pipeline; the records file and the run summary are compared whole with the contract result.")
def world_30_core_large_graph(workspace: Path) -> bool:
    return _holds(lambda: _world_holds("world_30_core_large_graph"))


@criterion(description="Hidden world with a large migration graph run through run_pipeline; the records file and the run summary are compared whole with the contract result.")
def world_31_core_large_graph(workspace: Path) -> bool:
    return _holds(lambda: _world_holds("world_31_core_large_graph"))


@criterion(description="Hidden world with a large migration graph run through run_pipeline; the records file and the run summary are compared whole with the contract result.")
def world_32_core_large_graph(workspace: Path) -> bool:
    return _holds(lambda: _world_holds("world_32_core_large_graph"))


@criterion(description="Hidden world with a large migration graph run through run_pipeline; the records file and the run summary are compared whole with the contract result.")
def world_33_core_large_graph(workspace: Path) -> bool:
    return _holds(lambda: _world_holds("world_33_core_large_graph"))


@criterion(description="Hidden world with a large migration graph run through run_pipeline; the records file and the run summary are compared whole with the contract result.")
def world_34_core_large_graph(workspace: Path) -> bool:
    return _holds(lambda: _world_holds("world_34_core_large_graph"))


@criterion(description="Hidden world with a large migration graph run through run_pipeline; the records file and the run summary are compared whole with the contract result.")
def world_35_core_large_graph(workspace: Path) -> bool:
    return _holds(lambda: _world_holds("world_35_core_large_graph"))


@criterion(description="Hidden world with a large migration graph run through run_pipeline; the records file and the run summary are compared whole with the contract result.")
def world_36_core_large_graph(workspace: Path) -> bool:
    return _holds(lambda: _world_holds("world_36_core_large_graph"))


@criterion(description="Hidden world with a large migration graph run through run_pipeline; the records file and the run summary are compared whole with the contract result.")
def world_37_core_large_graph(workspace: Path) -> bool:
    return _holds(lambda: _world_holds("world_37_core_large_graph"))


@criterion(description="Hidden world with a large migration graph run through run_pipeline; the records file and the run summary are compared whole with the contract result.")
def world_38_core_large_graph(workspace: Path) -> bool:
    return _holds(lambda: _world_holds("world_38_core_large_graph"))


@criterion(description="Hidden world with a large migration graph run through run_pipeline; the records file and the run summary are compared whole with the contract result.")
def world_39_core_large_graph(workspace: Path) -> bool:
    return _holds(lambda: _world_holds("world_39_core_large_graph"))


@criterion(description="Hidden world with a large migration graph run through run_pipeline; the records file and the run summary are compared whole with the contract result.")
def world_40_core_large_graph(workspace: Path) -> bool:
    return _holds(lambda: _world_holds("world_40_core_large_graph"))


@criterion(description="Hidden world with a large migration graph run through run_pipeline; the records file and the run summary are compared whole with the contract result.")
def world_41_core_large_graph(workspace: Path) -> bool:
    return _holds(lambda: _world_holds("world_41_core_large_graph"))


@criterion(description="Hidden world with a large migration graph run through run_pipeline; the records file and the run summary are compared whole with the contract result.")
def world_42_core_large_graph(workspace: Path) -> bool:
    return _holds(lambda: _world_holds("world_42_core_large_graph"))


@criterion(description="Hidden world with a large migration graph run through run_pipeline; the records file and the run summary are compared whole with the contract result.")
def world_43_core_large_graph(workspace: Path) -> bool:
    return _holds(lambda: _world_holds("world_43_core_large_graph"))


@criterion(description="Hidden world with a large migration graph run through run_pipeline; the records file and the run summary are compared whole with the contract result.")
def world_44_core_large_graph(workspace: Path) -> bool:
    return _holds(lambda: _world_holds("world_44_core_large_graph"))


@criterion(description="Hidden world with a large migration graph run through run_pipeline; the records file and the run summary are compared whole with the contract result.")
def world_45_core_large_graph(workspace: Path) -> bool:
    return _holds(lambda: _world_holds("world_45_core_large_graph"))


@criterion(description="Hidden world with a large migration graph run through run_pipeline; the records file and the run summary are compared whole with the contract result.")
def world_46_core_large_graph(workspace: Path) -> bool:
    return _holds(lambda: _world_holds("world_46_core_large_graph"))


def _mutated_receipt() -> tuple[dict, dict, str]:
    name = "world_22_reject_scope_feed_summary"
    spec, lines, seqs, corrections, receipts = _world(name)
    base = _world_expected(name)
    batch = min(b for b, (count, _) in receipts.items() if count and b not in base["summary"]["receipt_mismatches"])
    changed = dict(receipts, **{batch: [receipts[batch][0], receipts[batch][1] ^ 0x1000]})
    expected = _ref_pipeline(spec, _feed_text(lines), seqs, _corrections_text(corrections), changed)
    return _feed_job(spec, lines, seqs, corrections, changed), expected, batch


@criterion(description="Changing one batch's fp_xor in a hidden manifest adds only that batch to receipt_mismatches; records stay the same.")
def mutation_receipt_moves_only_mismatches(workspace: Path) -> bool:
    def check() -> bool:
        job, expected, _ = _mutated_receipt()
        return _same(_child(job, timeout=60.0), expected)
    return _holds(check)


def _mutated_tokens() -> tuple[dict, dict, str]:
    name = "world_23_pad_damage_tokens_policy"
    spec, lines, seqs, corrections, receipts = _world(name)
    pid = min(p for p, t in spec.partner_tokens.items() if len(t) == 2)
    changed = copy.copy(spec)
    changed.partner_tokens = dict(spec.partner_tokens, **{pid: []})
    expected = _ref_pipeline(changed, _feed_text(lines), seqs, _corrections_text(corrections), receipts)
    return _feed_job(changed, lines, seqs, corrections, receipts), expected, pid


@criterion(description="Emptying one partner's [tokens] line in a hidden contract folder changes only that partner's records.")
def mutation_tokens_move_only_that_partner(workspace: Path) -> bool:
    def check() -> bool:
        job, expected, _ = _mutated_tokens()
        return _same(_child(job, timeout=60.0), expected)
    return _holds(check)

# Shipped-run figures (migrated, rejected, E_UNREACHABLE) as integer constants.
_SAMPLE_ANSWERS = (5604, 1969, 1787)


def _source_integers() -> set[int]:
    found: set[int] = set()
    for path in sorted(_delivered_repo().rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
        except SyntaxError:
            continue
        found.update(node.value for node in ast.walk(tree) if isinstance(node, ast.Constant) and type(node.value) is int)
    return found


@criterion(description="Detects answers hardcoded in the delivered source: the shipped run's migrated, rejected and E_UNREACHABLE counts as integer constants, the hidden evaluation seed, or three or more hidden edge ids.")
def negative_hardcoded_sample_answers(workspace: Path) -> bool:
    # Inverted polarity: True means the cheat is present.
    def check() -> bool:
        text = _archive_sources()
        hits = sum(1 for edge_id in _hidden_edge_ids() if edge_id in text)
        shipped = set(_SAMPLE_ANSWERS) <= _source_integers()
        return shipped or str(EVAL_SEED) in text or hits >= 3
    return _holds(check)


@criterion(description="Detects output that changes when the same feed is given under another file name.")
def negative_filename_dependent_behaviour(workspace: Path) -> bool:
    # Inverted polarity: True means renaming the feed changed the records.
    def check() -> bool:
        job = case_dropped_conflict()
        first = _child(job)["records"]
        renamed = Path(job["contracts"]) / "partner_batches.jsonl"
        shutil.copyfile(job["feed"], renamed)
        renamed.chmod(0o644)
        second = _child(dict(job, feed=str(renamed)))["records"]
        return not _same(first, second)
    return _holds(check)


def _visible_tests_gutted() -> bool:
    path = _delivered_repo() / "tests" / "test_visible.py"
    if not path.is_file():
        return True
    text = path.read_text(encoding="utf-8")
    return any(name not in text for name in VISIBLE_TESTS) or text.count("self.assert") < 9


@criterion(description="Detects visible tests that were removed or stripped of their assertions.")
def negative_deleted_visible_tests(workspace: Path) -> bool:
    # Inverted polarity: True means the visible tests were removed or gutted.
    return _holds(_visible_tests_gutted)


@criterion(description="Detects plan_migration, state_signature or execute_plan changing the payload, corrections or plan passed to them.")
def negative_entry_points_mutate_arguments(workspace: Path) -> bool:
    # Inverted polarity: True means an entry point changed an argument in place. A call that fails is not counted.
    def check() -> bool:
        spec, job = case_watch()
        result = _child(dict(job, contracts=str(spec.write())))
        return isinstance(result.get("ok"), list) and not all(result["ok"])
    return _holds(check)


@criterion(description="Detects run output that differs between two runs on the same hidden input.")
def negative_nondeterministic_output(workspace: Path) -> bool:
    # Inverted polarity: True means two identical runs disagreed. A run that fails is not counted.
    def check() -> bool:
        spec, lines, seqs, corrections, receipts = _world("world_02_tie_tokens_replay_feed")
        job = _feed_job(spec, lines, seqs, corrections, receipts)
        return not _same(_child(job), _child(job))
    return _holds(check)


criteria.artifacts_exist(weight=1)
criteria.negative_unsafe_archive_members(weight=-1)
criteria.archive_src_layout(weight=1)
criteria.api_entry_points_importable(weight=1)
criteria.visible_repo_tests_pass_from_archive(weight=1)
criteria.summary_json_matches_delivered_run(weight=1)
criteria.module_core_claims_match_archive(weight=1)
criteria.module_parser_claims_match_archive(weight=1)
criteria.module_report_claims_match_archive(weight=1)
criteria.test_fixes_matches_visible_test_runs(weight=1)
criteria.repair_report_well_formed(weight=1)
criteria.signature_keeps_explicit_null(weight=3)
criteria.signature_rejects_unknown_schema(weight=1)
criteria.plan_revisits_schema_with_new_state(weight=3)
criteria.plan_tie_first_edge_decides(weight=3)
criteria.ladder_large_state(weight=3)
criteria.exec_add_fill_absent_vs_null(weight=3)
criteria.exec_correction_first_arrival_only(weight=3)
criteria.identity_merge_chain_followed(weight=1)
criteria.identity_merge_loop_rejected(weight=1)
criteria.identity_partner_id_beats_alias(weight=1)
criteria.pipe_rejection_codes(weight=3)
criteria.pipe_bad_lines_run_continues(weight=3)
criteria.receipt_skips_lines_rejected_at_parse(weight=3)
criteria.receipt_counts_partner_rejected_lines(weight=3)
criteria.tokens_match_exactly(weight=3)
criteria.summary_categories_code_first(weight=3)
criteria.summary_partner_order_by_rank(weight=1)
criteria.world_01_state_null_corrections_summary(weight=5)
criteria.world_02_tie_tokens_replay_feed(weight=5)
criteria.world_03_state_policy_tokens_corrections(weight=5)
criteria.world_04_scale_state_replay_summary(weight=5)
criteria.world_05_null_policy_replay_cli(weight=5)
criteria.world_06_tie_corrections_feed_summary(weight=5)
criteria.world_07_state_tie_null_tokens_summary(weight=5)
criteria.world_08_scale_policy_corrections_feed(weight=5)
criteria.world_09_policy_tokens_replay_corrections_cli(weight=5)
criteria.world_10_state_feed_replay_summary(weight=5)
criteria.world_11_null_tie_corrections_cli(weight=5)
criteria.world_12_scale_tokens_null_summary(weight=5)
criteria.world_13_state_policy_feed_cli(weight=5)
criteria.world_14_tie_policy_replay_summary(weight=5)
criteria.world_15_scale_corrections_tokens_feed(weight=5)
criteria.world_16_null_state_replay_corrections(weight=5)
criteria.world_17_tie_policy_null_feed_summary(weight=5)
criteria.world_18_scale_tie_replay_cli(weight=5)
criteria.world_19_state_tokens_corrections_replay_feed_summary(weight=5)
criteria.world_20_reject_pad_state_corrections(weight=5)
criteria.world_21_scope_damage_null_replay(weight=5)
criteria.world_22_reject_scope_feed_summary(weight=5)
criteria.world_23_pad_damage_tokens_policy(weight=5)
criteria.world_24_reject_damage_tie_cli(weight=5)
criteria.world_25_scope_pad_corrections_summary(weight=5)
criteria.world_26_reject_scope_pad_damage(weight=5)
criteria.world_27_pad_scope_state_tokens_cli(weight=5)
criteria.world_28_damage_reject_scale_replay(weight=5)
criteria.world_29_core_large_graph(weight=5)
criteria.world_30_core_large_graph(weight=5)
criteria.world_31_core_large_graph(weight=5)
criteria.world_32_core_large_graph(weight=5)
criteria.world_33_core_large_graph(weight=5)
criteria.world_34_core_large_graph(weight=5)
criteria.world_35_core_large_graph(weight=5)
criteria.world_36_core_large_graph(weight=5)
criteria.world_37_core_large_graph(weight=5)
criteria.world_38_core_large_graph(weight=5)
criteria.world_39_core_large_graph(weight=5)
criteria.world_40_core_large_graph(weight=5)
criteria.world_41_core_large_graph(weight=5)
criteria.world_42_core_large_graph(weight=5)
criteria.world_43_core_large_graph(weight=5)
criteria.world_44_core_large_graph(weight=5)
criteria.world_45_core_large_graph(weight=5)
criteria.world_46_core_large_graph(weight=5)
criteria.mutation_receipt_moves_only_mismatches(weight=5)
criteria.mutation_tokens_move_only_that_partner(weight=5)
criteria.negative_hardcoded_sample_answers(weight=-5)
criteria.negative_filename_dependent_behaviour(weight=-3)
criteria.negative_deleted_visible_tests(weight=-3)
criteria.negative_nondeterministic_output(weight=-1)
criteria.negative_entry_points_mutate_arguments(weight=-1)
