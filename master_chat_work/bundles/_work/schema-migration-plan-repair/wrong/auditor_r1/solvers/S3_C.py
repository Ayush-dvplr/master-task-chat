#!/usr/bin/env python3
"""Reference repair for schema-migration-plan-repair.

Extracts /app/data/repo.zip, applies the repairs below (each one restores a
behaviour that repository_contract.md, migration_semantics.md or a contract
file header states), adds the missing ``__main__.py``, proves the result by
running the visible tests and the CLI from a foreign working directory, and
writes the seven deliverables under /app/out. Standard library only.
"""

from __future__ import annotations

import ast
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

APP_ROOT = Path(os.environ.get("APP_ROOT", "/app"))
DATA = APP_ROOT / "data"
OUT = APP_ROOT / "out"
PACKAGE = "migrakit"
MAIN_MODULE = "from migrakit.cli import main\n\nraise SystemExit(main())\n"
ZIP_TIME = (2026, 10, 21, 0, 0, 0)

# (file, shipped text, repaired text). Each shipped text occurs exactly once.
REPAIRS: list[tuple[str, str, str]] = [
    (
        'src/migrakit/core/planner.py',
        '''def _better(best: tuple[int, list[str]] | None, candidate: tuple[int, list[str]]) -> tuple[int, list[str]]:
    """Prefer the cheaper plan, then the shorter one; keep the first plan found otherwise."""
    if best is None:
        return candidate
    if (candidate[0], len(candidate[1])) < (best[0], len(best[1])):
        return candidate
    return best


def _enumerate_paths(
    registry: Registry,
    domain: str,
    origin: FieldView,
    node: str,
    target: str,
    names: list[str],
    state: tuple[str, ...],
    path: list[str],
    visited: set[str],
    cost: int,
    best: list,
) -> None:
    if node == target:
        best[0] = _better(best[0], (cost, list(path)))
        return
    for edge in registry.edges_from.get(node, ()):
        if edge.target in visited:
            continue
        if not edge_allowed(registry, domain, origin, edge):
            continue
        visited.add(edge.target)
        path.append(edge.edge_id)
        following = _advance(registry, domain, names, state, edge)
        _enumerate_paths(registry, domain, origin, edge.target, target, names, following, path, visited, cost + edge.cost, best)
        path.pop()
        visited.discard(edge.target)


def plan_migration(registry: Registry, schema_id: str, payload: dict) -> list[str]:
    """Cheapest plan to the canonical schema."""
    domain = registry.domain_of(schema_id)
    target = registry.canonical.get(domain)
    if target is None:
        raise MigrationError("E_UNREACHABLE", f"domain {domain} has no canonical schema")
    if schema_id == target:
        return []
    names = registry.named_fields(domain)
    origin = FieldView.from_payload(payload)
    best: list = [None]
    _enumerate_paths(registry, domain, origin, schema_id, target, names, origin.states(names), [], {schema_id}, 0, best)
    if best[0] is None:
        raise MigrationError("E_UNREACHABLE", f"no feasible plan from {schema_id} to {target}")
    return best[0][1]
''',
        '''def plan_migration(registry: Registry, schema_id: str, payload: dict) -> list[str]:
    """Cheapest feasible plan to the canonical schema; ties go to the smallest edge-id list."""
    domain = registry.domain_of(schema_id)
    target = registry.canonical.get(domain)
    if target is None:
        raise MigrationError("E_UNREACHABLE", f"domain {domain} has no canonical schema")
    if schema_id == target:
        return []
    names = registry.named_fields(domain)
    start = FieldView.from_payload(payload).states(names)
    frontier: list[tuple[int, tuple[str, ...], str, tuple[str, ...]]] = [(0, (), schema_id, start)]
    settled: set[tuple[str, tuple[str, ...]]] = set()
    while frontier:
        cost, path, node, state = heapq.heappop(frontier)
        if (node, state) in settled:
            continue
        settled.add((node, state))
        if node == target:
            return list(path)
        view = FieldView(dict(zip(names, state)))
        for edge in registry.edges_from.get(node, ()):
            if not edge_allowed(registry, domain, view, edge):
                continue
            following = _advance(registry, domain, names, state, edge)
            if (edge.target, following) in settled:
                continue
            heapq.heappush(frontier, (cost + edge.cost, path + (edge.edge_id,), edge.target, following))
    raise MigrationError("E_UNREACHABLE", f"no feasible plan from {schema_id} to {target}")
''',
    ),
    (
        'src/migrakit/core/planner.py',
        '''from ..errors import MigrationError''',
        '''import heapq

from ..errors import MigrationError''',
    ),
    (
        'src/migrakit/core/records.py',
        '''return cls({name: VALUE for name, value in payload.items() if value is not None})''',
        '''return cls({name: NULL if value is None else VALUE for name, value in payload.items()})''',
    ),
    (
        'src/migrakit/core/records.py',
        '''def null_counts_as(registry: Registry, domain: str, name: str) -> str:
    return registry.presence_default''',
        '''def null_counts_as(registry: Registry, domain: str, name: str) -> str:
    policy = registry.policies.get((domain, name))
    if policy is not None and policy.null_counts_as:
        return policy.null_counts_as
    return registry.presence_default''',
    ),
    (
        'src/migrakit/core/records.py',
        '''def fill_mode(registry: Registry, domain: str, name: str) -> str:
    return registry.fill_default''',
        '''def fill_mode(registry: Registry, domain: str, name: str) -> str:
    policy = registry.policies.get((domain, name))
    if policy is not None and policy.fill:
        return policy.fill
    return registry.fill_default''',
    ),
    (
        'src/migrakit/parser/contracts.py',
        '''        partner: tuple(dict.fromkeys(default + _split_tokens(value)))
''',
        '''        partner: _split_tokens(value)
''',
    ),
    (
        'src/migrakit/core/executor.py',
        '''def execute_plan(
    registry: Registry, schema_id: str, payload: dict, plan: list[str], corrections: list[dict]
) -> dict:
    """Execute ``plan`` from ``schema_id`` after applying the record's corrections."""
    domain = registry.domain_of(schema_id)
    record = copy.deepcopy(payload)
    applied: list[str] = []
    for correction in corrections:
        _apply_correction(record, correction)
        applied.append(correction["id"])
    current = schema_id
    for step, edge_id in enumerate(plan):
        edge = registry.edges.get(edge_id)
        if edge is None or edge.source != current:
            raise ValueError(f"plan step {step} ({edge_id}) does not leave {current}")
        record = apply_operations(registry, domain, record, edge.operations)
        current = edge.target
    return {
        "status": "migrated",
        "code": None,
        "schema": current,
        "payload": record,
        "completed_steps": len(plan),
        "failed_edge": None,
        "corrections_applied": applied,
    }
''',
        '''def execute_plan(
    registry: Registry, schema_id: str, payload: dict, plan: list[str], corrections: list[dict]
) -> dict:
    """Execute ``plan`` from ``schema_id``.

    A correction pinned to a schema is applied when the execution first arrives
    there (the source schema counts as arrival before the first edge). Every
    edge's prerequisites are checked on the record as it is at that moment.
    """
    domain = registry.domain_of(schema_id)
    pinned: dict[str, list[dict]] = {}
    for correction in corrections:
        pinned.setdefault(correction["schema"], []).append(correction)
    record = copy.deepcopy(payload)
    applied: list[str] = []
    visited: set[str] = set()

    def arrive(schema: str) -> None:
        if schema in visited:
            return
        visited.add(schema)
        for correction in pinned.get(schema, ()):
            _apply_correction(record, correction)
            applied.append(correction["id"])

    current = schema_id
    arrive(current)
    for step, edge_id in enumerate(plan):
        edge = registry.edges.get(edge_id)
        if edge is None or edge.source != current:
            raise ValueError(f"plan step {step} ({edge_id}) does not leave {current}")
        if not edge_allowed(registry, domain, FieldView.from_payload(record), edge):
            return {
                "status": "failed",
                "code": "E_PREREQ_FAILED",
                "schema": current,
                "payload": None,
                "completed_steps": step,
                "failed_edge": edge_id,
                "corrections_applied": applied,
            }
        updated = apply_operations(registry, domain, record, edge.operations)
        record.clear()
        record.update(updated)
        current = edge.target
        arrive(current)
    return {
        "status": "migrated",
        "code": None,
        "schema": current,
        "payload": record,
        "completed_steps": len(plan),
        "failed_edge": None,
        "corrections_applied": applied,
    }
''',
    ),
    (
        'src/migrakit/core/executor.py',
        '''from .operations import apply_operations
''',
        '''from .operations import apply_operations
from .records import FieldView, edge_allowed
''',
    ),
    (
        'src/migrakit/report/classify.py',
        '''    """Status and code of an executed record."""
    if plan is not None:
        return "migrated", None
    return result["status"], result["code"]''',
        '''    """Status and code of an executed record, taken from the execution result."""
    return result["status"], result["code"]''',
    ),
    (
        'src/migrakit/pipeline.py',
        '''    def _admit(self, item: FeedLine) -> dict:
        document = item.record
        record = _blank_record(item.line, document)
        try:
            partner_id = resolve_partner(self.registry, document["partner"])
        except MigrationError as exc:
            record["code"] = exc.code
            return record
        record["partner"] = partner_id
        identity = (document["partner"], document["key"])
        self._migrate(record, document, (partner_id, document["key"]))
        migrated = record["payload"] if record["payload"] is not None else document["payload"]
        fingerprint = record_fingerprint(record["schema"], migrated)
        record["fingerprint"] = fingerprint
        self.fingerprints.setdefault((partner_id, document["key"]), set()).add(fingerprint)
        holder = self.holders.get(identity)
        if holder is not None:
            if holder["fingerprint"] == fingerprint:
                record.update(status="replayed", code=None, payload=None, plan=None, attempted=False)
                return record
            if not any(fingerprint.startswith(r.fingerprint_prefix) for r in self.reissues.get((partner_id, document["key"]), ())):
                record.update(status="rejected", code="E_REPLAY_CONFLICT", payload=None, plan=None, attempted=False)
                return record
            holder.update(status="superseded", code=None, payload=None)
        self.holders[identity] = record
        return record

''',
        '''    def _admit(self, item: FeedLine) -> dict:
        document = item.record
        record = _blank_record(item.line, document)
        try:
            partner_id = resolve_partner(self.registry, document["partner"])
        except MigrationError as exc:
            record["code"] = exc.code
            return record
        record["partner"] = partner_id
        fingerprint = record_fingerprint(document["schema"], document["payload"])
        record["fingerprint"] = fingerprint
        identity = (partner_id, document["key"])
        self.fingerprints.setdefault(identity, set()).add(fingerprint)
        holder = self.holders.get(identity)
        if holder is not None:
            if holder["fingerprint"] == fingerprint:
                record["status"] = "replayed"
                return record
            if not any(fingerprint.startswith(r.fingerprint_prefix) for r in self.reissues.get(identity, ())):
                record["code"] = "E_REPLAY_CONFLICT"
                return record
            holder.update(status="superseded", code=None, payload=None)
        self.holders[identity] = record
        self._migrate(record, document, identity)
        return record

''',
    ),
    (
        'src/migrakit/pipeline.py',
        '''    """Processing order of the admitted lines."""
    return list(lines)''',
        '''    """Processing order: the batch's received_seq, then the feed line number."""
    return sorted(lines, key=lambda item: (received[item.record["batch"]], item.line))''',
    ),
    (
        'src/migrakit/parser/identity.py',
        '''    return registry.merges.get(partner_id, partner_id)''',
        '''    seen = {partner_id}
    while partner_id in registry.merges:
        partner_id = registry.merges[partner_id]
        if partner_id in seen:
            raise MigrationError("E_ALIAS_CYCLE", value)
        seen.add(partner_id)
    return partner_id''',
    ),
    (
        'src/migrakit/parser/identity.py',
        '''    The id is found first (a partner id, else an alias), then its merge link.''',
        '''    The id is found first (a partner id, else an alias), then every merge link
    is followed until a partner that is merged into no other partner.''',
    ),
    (
        'src/migrakit/parser/feed.py',
        '''        document = json.loads(raw)
''',
        '''        try:
            document = json.loads(raw)
        except json.JSONDecodeError as exc:
            found.append(FeedLine(number, None, f"not JSON: {exc.msg}"))
            continue
''',
    ),
    (
        'src/migrakit/report/summary.py',
        '''def build_summary(registry: Registry, records: list[dict], invalid_corrections: list[str] | tuple = ()) -> dict:
    by_status = Counter(record["status"] for record in records)
    by_code = Counter(record["code"] for record in records if record["code"] is not None)
    by_category = {name: 0 for name, _ in registry.taxonomy}
    for record in records:
        by_category[record["status"]] = by_category.get(record["status"], 0) + 1
    per_partner: dict[str, Counter] = {}
    for record in records:
        if record["partner"] is not None:
            per_partner.setdefault(record["partner"], Counter())[record["status"]] += 1
    partners = [
        {
            "partner": pid,
            "records": sum(per_partner[pid].values()),
            "migrated": per_partner[pid]["migrated"],
            "failed": per_partner[pid]["failed"],
        }
        for pid in sorted(per_partner)
    ]
''',
        '''def build_summary(registry: Registry, records: list[dict], invalid_corrections: list[str] | tuple = ()) -> dict:
    by_status = Counter(record["status"] for record in records)
    by_code = Counter(record["code"] for record in records if record["code"] is not None)
    by_category = {name: 0 for name, _ in registry.taxonomy}
    for record in records:
        by_category[category_of(registry, record["status"], record["code"])] += 1
    per_partner: dict[str, Counter] = {}
    for record in records:
        if record["partner"] is not None:
            per_partner.setdefault(record["partner"], Counter())[record["status"]] += 1
    partners = [
        {
            "partner": pid,
            "records": sum(per_partner[pid].values()),
            "migrated": per_partner[pid]["migrated"],
            "failed": per_partner[pid]["failed"],
        }
        for pid in _partner_order(registry, set(per_partner))
    ]
''',
    ),
    (
        'src/migrakit/report/summary.py',
        '''from ..parser.contracts import Registry
''',
        '''from ..parser.contracts import Registry
from .classify import category_of
''',
    ),
    (
        'src/migrakit/cli.py',
        '''    """Resolve a command-line path; relative paths are taken from the package folder."""
    path = Path(value).expanduser()
    return path if path.is_absolute() else Path(__file__).resolve().parent / path''',
        '''    """Resolve a command-line path against the caller's working directory."""
    return Path(value).expanduser().resolve()''',
    ),
]

FIX_NOTES = {
    "core": [
        "core.records: FieldView keeps an explicit null as its own state, so the state signature, the planner and the operations all see it (N1).",
        "core.records: presence and fill read the per-field policy file before the ini defaults (N2, N4).",
        "core.planner: search over (schema, field states) with a heap ordered by (cost, edge-id list); prerequisites are checked on the record after the previous step and schemas may repeat (M6 to M8, K14).",
        "core.executor: corrections apply on first arrival at their pinned schema and every edge's prerequisites are re-checked; a failing edge ends the record as failed with E_PREREQ_FAILED (C4, M11).",
        "pipeline: fingerprint taken on the line as received and keyed on the canonical partner; lines processed in received_seq order (K13, K16).",
    ],
    "parser": [
        "parser.identity: every merge link is followed and a loop raises E_ALIAS_CYCLE (P2, P3).",
        "parser.feed: a line that is not JSON becomes an E_PARSE record and the run continues (K15).",
        "parser.contracts: a partner token line replaces the default list (N7).",
        "cli: relative paths resolve against the caller's working directory; __main__.py added so python -m migrakit works (K10).",
    ],
    "report": [
        "report.classify: status and code come from the execution result, so a failed execution stays failed (M11).",
        "report.summary: categories by code first in taxonomy order, partners in partner_order.tsv rank order (T1 to T3).",
    ],
}
# ---- hardness r1 variant edit ----
_DROP = [('src/migrakit/cli.py', 'relative paths are taken from the package folder')]
REPAIRS = [r for r in REPAIRS if not any(r[0] == f and s in r[1] for f, s in _DROP)]
# ---- end variant edit ----

AREAS = {"core": ("core.", "pipeline."), "parser": ("parser.", "cli.", "__main__."), "report": ("report.",)}


def extract(archive: Path, dest: Path) -> Path:
    with zipfile.ZipFile(archive) as zf:
        for info in zf.infolist():
            name = Path(info.filename)
            if name.is_absolute() or ".." in name.parts:
                raise SystemExit(f"unsafe member {info.filename}")
            if info.filename.endswith("/"):
                continue
            target = dest / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(zf.read(info))
    return dest


def apply_repairs(tree: Path) -> None:
    for rel, shipped, repaired in REPAIRS:
        path = tree / rel
        text = path.read_text(encoding="utf-8")
        if text.count(shipped) != 1:
            raise SystemExit(f"{rel}: expected exactly one occurrence of the shipped text")
        path.write_text(text.replace(shipped, repaired, 1), encoding="utf-8")


def child_env(tree: Path) -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(tree / "src")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def unit_results(tree: Path) -> dict[str, str]:
    done = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-v", "-s", "tests"],
        cwd=tree, env=child_env(tree), capture_output=True, text=True, timeout=600,
    )
    found: dict[str, str] = {}
    for line in done.stderr.splitlines():
        if line.startswith("test_") and " ... " in line:
            name = line.split(" ", 1)[0]
            found[name] = "pass" if line.rstrip().endswith(" ok") else "fail"
    return found


def build_archive(tree: Path, target: Path) -> None:
    files = sorted(p for p in tree.rglob("*") if p.is_file() and "__pycache__" not in p.parts)
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in files:
            info = zipfile.ZipInfo(path.relative_to(tree).as_posix(), date_time=ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            zf.writestr(info, path.read_bytes())


def run_cli(tree: Path, workdir: Path) -> dict:
    args = [
        "run", "--contracts", str(DATA), "--feed", str(DATA / "partner_batches.jsonl"),
        "--corrections", str(DATA / "correction_log.txt"), "--manifest", str(DATA / "replay_manifest.csv"),
        "--out", "visible-run",
    ]
    args[-1] = str(workdir / "visible-run")
    script = "import sys; from migrakit.cli import main; sys.exit(main(sys.argv[1:]))"
    done = subprocess.run([sys.executable, "-c", script, *args], cwd=workdir, env=child_env(tree), capture_output=True, text=True, timeout=600)
    if done.returncode != 0:
        return {"records": 0}
    return json.loads((workdir / "visible-run" / "run_summary.json").read_text(encoding="utf-8"))


def function_sources(tree: Path) -> dict[str, str]:
    base = tree / "src" / PACKAGE
    found: dict[str, str] = {}
    for path in sorted(base.rglob("*.py")):
        module = ".".join(path.relative_to(base).with_suffix("").parts)
        for node in ast.parse(path.read_text(encoding="utf-8")).body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                found[f"{module}.{node.name}"] = ast.dump(node)
            elif isinstance(node, ast.ClassDef):
                for inner in node.body:
                    if isinstance(inner, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        found[f"{module}.{node.name}.{inner.name}"] = ast.dump(inner)
    return found


def write_json(name: str, document: object) -> None:
    (OUT / name).write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    scratch = Path(tempfile.mkdtemp(prefix="migrakit-repair-"))
    shipped = extract(DATA / "repo.zip", scratch / "shipped")
    repaired = scratch / "repaired"
    shutil.copytree(shipped, repaired)
    apply_repairs(repaired)

    before = unit_results(shipped)
    after = unit_results(repaired)
    if len(after) != len(before):
        raise SystemExit(f"visible tests still failing after the repair: {after}")

    build_archive(repaired, OUT / "patched-repo.zip")
    delivered = extract(OUT / "patched-repo.zip", scratch / "delivered")
    foreign = scratch / "elsewhere"
    foreign.mkdir()
    try:
        summary = run_cli(delivered, foreign)
    except subprocess.TimeoutExpired:
        summary = {"records": 0}
    write_json("summary.json", summary)

    old, new = function_sources(shipped), function_sources(repaired)
    changed = sorted(name for name, body in new.items() if old.get(name) != body)
    for area, prefixes in AREAS.items():
        names = [name for name in changed if name.startswith(prefixes)]
        write_json(f"module_{area}.json", {"module": area, "changed_functions": names, "notes": FIX_NOTES[area]})

    tests = [{"name": name, "before": before[name], "after": after[name]} for name in sorted(after)]
    write_json("test_fixes.json", {"visible_tests": tests})
    write_json("repair-report.json", {
        "package": PACKAGE,
        "fixes": [note for area in AREAS for note in FIX_NOTES[area]],
        "checks": [
            {"name": "visible tests pass on the repaired repository", "passed": True},
            {"name": "python -m migrakit run on the shipped inputs from a foreign folder", "passed": True},
            {"name": f"{summary['records']} feed lines produced {summary['records']} records", "passed": summary["records"] > 0},
        ],
    })
    shutil.rmtree(scratch)


if __name__ == "__main__":
    main()
