"""Hardness round 1 (auditor): write every solver as a small edit of the bundle's solution/solve.py.

    python3 make_solvers.py OUT_DIR

Each solver = solve.py + one VARIANT block inserted after FIX_NOTES. The block
can (a) DROP repairs (the shipped text of that defect stays), (b) REPLACE the
repaired text of a repair, (c) ADD repairs. Planner variants swap the body of
the repaired plan_migration. Every edit is asserted to match exactly once.
Written from repository_contract.md, migration_semantics.md and the contract
file headers; the builder's wrong/ was not read before these were scored.
"""

from __future__ import annotations

import sys
from pathlib import Path

BUNDLE = Path("/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/schema-migration-plan-repair")
SOLVE = (BUNDLE / "solution" / "solve.py").read_text(encoding="utf-8")
ANCHOR = 'AREAS = {"core": ("core.", "pipeline."),'
assert SOLVE.count(ANCHOR) == 1

# Unique markers of the oracle repairs: (file, substring of the SHIPPED text).
R = {
    "plan": ("src/migrakit/core/planner.py", "def _better("),
    "heapq": ("src/migrakit/core/planner.py", "from ..errors import MigrationError"),
    "null_kept": ("src/migrakit/core/records.py", "return cls({name: VALUE"),
    "presence_policy": ("src/migrakit/core/records.py", "def null_counts_as("),
    "fill_policy": ("src/migrakit/core/records.py", "def fill_mode("),
    "tokens_replace": ("src/migrakit/parser/contracts.py", "partner: tuple(dict.fromkeys"),
    "executor": ("src/migrakit/core/executor.py", "def execute_plan("),
    "executor_import": ("src/migrakit/core/executor.py", "from .operations import apply_operations"),
    "classify": ("src/migrakit/report/classify.py", "if plan is not None:"),
    "admit": ("src/migrakit/pipeline.py", "def _admit("),
    "order": ("src/migrakit/pipeline.py", "Processing order of the admitted lines"),
    "merge_chain": ("src/migrakit/parser/identity.py", "return registry.merges.get(partner_id, partner_id)"),
    "merge_doc": ("src/migrakit/parser/identity.py", "The id is found first"),
    "feed": ("src/migrakit/parser/feed.py", "document = json.loads(raw)"),
    "summary": ("src/migrakit/report/summary.py", "def build_summary("),
    "summary_import": ("src/migrakit/report/summary.py", "from ..parser.contracts import Registry"),
    "cli": ("src/migrakit/cli.py", "relative paths are taken from the package folder"),
}

# Body of the oracle's repaired plan_migration, from `start = ...` to the last heappush.
_lines = SOLVE.splitlines(keepends=True)
_first = next(i for i, l in enumerate(_lines) if l.startswith("    start = FieldView.from_payload(payload).states(names)"))
_last = next(i for i, l in enumerate(_lines) if "heapq.heappush(frontier, (cost + edge.cost, path + (edge.edge_id,)" in l)
ORACLE_PLAN_BODY = "".join(_lines[_first:_last + 1])
assert SOLVE.count(ORACLE_PLAN_BODY) == 1

PLAN_RECEIVED_RECORD = ORACLE_PLAN_BODY.replace(
    "view = FieldView(dict(zip(names, state)))", "view = FieldView(dict(zip(names, start)))")

PLAN_LAST_EDGE_TIE = '''    start = FieldView.from_payload(payload).states(names)
    best: dict = {(schema_id, start): (0, "", None)}
    frontier: list[tuple[int, str, tuple[str, ...]]] = [(0, schema_id, start)]
    settled: set[tuple[str, tuple[str, ...]]] = set()
    while frontier:
        cost, node, state = heapq.heappop(frontier)
        if (node, state) in settled:
            continue
        settled.add((node, state))
        if node == target:
            plan: list[str] = []
            key = (node, state)
            while best[key][2] is not None:
                plan.append(best[key][1])
                key = best[key][2]
            return plan[::-1]
        view = FieldView(dict(zip(names, state)))
        for edge in registry.edges_from.get(node, ()):
            if not edge_allowed(registry, domain, view, edge):
                continue
            following = _advance(registry, domain, names, state, edge)
            key = (edge.target, following)
            if key in settled:
                continue
            known = best.get(key)
            new_cost = cost + edge.cost
            if known is None or new_cost < known[0] or (new_cost == known[0] and edge.edge_id < known[1]):
                best[key] = (new_cost, edge.edge_id, (node, state))
                heapq.heappush(frontier, (new_cost, edge.target, following))
'''

PLAN_ENUMERATE = '''    start = FieldView.from_payload(payload).states(names)
    best: list = [None]

    def walk(node: str, state: tuple[str, ...], path: list[str], cost: int, on_path: set) -> None:
        if node == target:
            if best[0] is None or (cost, path) < best[0]:
                best[0] = (cost, list(path))
            return
        view = FieldView(dict(zip(names, state)))
        for edge in registry.edges_from.get(node, ()):
            if not edge_allowed(registry, domain, view, edge):
                continue
            following = _advance(registry, domain, names, state, edge)
            key = (edge.target, following)
            if key in on_path:
                continue
            on_path.add(key)
            path.append(edge.edge_id)
            walk(edge.target, following, path, cost + edge.cost, on_path)
            path.pop()
            on_path.discard(key)

    walk(schema_id, start, [], 0, {(schema_id, start)})
    if best[0] is not None:
        return best[0][1]
'''

# Careful agent's Dijkstra on schema ids: each schema keeps the record state of its
# best path, prerequisites checked on that state; equal cost keeps the smaller last edge.
PLAN_SCHEMA_DIJKSTRA = '''    start = FieldView.from_payload(payload).states(names)
    best: dict = {schema_id: (0, "", None, start)}
    frontier: list[tuple[int, str]] = [(0, schema_id)]
    settled: set[str] = set()
    while frontier:
        cost, node = heapq.heappop(frontier)
        if node in settled:
            continue
        settled.add(node)
        if node == target:
            plan: list[str] = []
            while best[node][2] is not None:
                plan.append(best[node][1])
                node = best[node][2]
            return plan[::-1]
        state = best[node][3]
        view = FieldView(dict(zip(names, state)))
        for edge in registry.edges_from.get(node, ()):
            if edge.target in settled or not edge_allowed(registry, domain, view, edge):
                continue
            new_cost = cost + edge.cost
            known = best.get(edge.target)
            if known is None or new_cost < known[0] or (new_cost == known[0] and edge.edge_id < known[1]):
                best[edge.target] = (new_cost, edge.edge_id, node, _advance(registry, domain, names, state, edge))
                heapq.heappush(frontier, (new_cost, edge.target))
'''

# LV-MR-6 reflex: FieldView keeps dropping nulls; the signature and the operations
# are fixed at their call sites instead.
CALL_SITE_NULL_FIX = [
    ("src/migrakit/core/planner.py",
     "    return FieldView.from_payload(payload).signature(registry.prerequisite_fields(domain))",
     "    return {name: (ABSENT if name not in payload else NULL if payload[name] is None else VALUE)"
     " for name in registry.prerequisite_fields(domain)}"),
    ("src/migrakit/core/planner.py",
     "from .records import ABSENT, NULL, FieldView, edge_allowed",
     "from .records import ABSENT, NULL, VALUE, FieldView, edge_allowed"),
    ("src/migrakit/core/operations.py",
     "    if view.state(source) == ABSENT:\n        return\n    record[target] = record.pop(source)",
     "    if source not in record:\n        return\n    record[target] = record.pop(source)"),
    ("src/migrakit/core/operations.py",
     "    state = view.state(name)\n    if state == ABSENT or",
     "    state = ABSENT if name not in record else NULL if record[name] is None else VALUE\n    if state == ABSENT or"),
]

# LV-MR-5 reflex: fingerprint taken after null-token replacement (still before migration).
FP_AFTER_TOKENS = ('fingerprint = record_fingerprint(document["schema"], document["payload"])',
                   'fingerprint = record_fingerprint(document["schema"], _replace_tokens(document["payload"], self.registry.tokens_for(partner_id)))')

# LV-MR-7 reflex: corrections applied at the top of each step for the schema the record is at
# (so on every arrival, and never at the final schema); re-check and failure kept.
LOOP_TOP_EXECUTOR = '''def execute_plan(
    registry: Registry, schema_id: str, payload: dict, plan: list[str], corrections: list[dict]
) -> dict:
    """Execute ``plan`` from ``schema_id``, applying each correction while the record is at its schema."""
    domain = registry.domain_of(schema_id)
    record = copy.deepcopy(payload)
    applied: list[str] = []
    current = schema_id
    for step, edge_id in enumerate(plan):
        edge = registry.edges.get(edge_id)
        if edge is None or edge.source != current:
            raise ValueError(f"plan step {step} ({edge_id}) does not leave {current}")
        for correction in corrections:
            if correction["schema"] == current:
                _apply_correction(record, correction)
                applied.append(correction["id"])
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
'''

# C reflex (shipped CLI): no __main__.py, package-relative paths; the solver then gets its
# summary through migrakit.cli.main with absolute paths and ships despite failing visible tests.
SHIP_WITHOUT_CLI_FIX = [
    ('    (tree / "src" / PACKAGE / "__main__.py").write_text(MAIN_MODULE, encoding="utf-8")\n', ""),
    ('    if set(after.values()) != {"pass"} or len(after) != len(before):', "    if len(after) != len(before):"),
    ('    done = subprocess.run([sys.executable, "-m", PACKAGE, *args], cwd=workdir',
     '    args[-1] = str(workdir / "visible-run")\n'
     '    script = "import sys; from migrakit.cli import main; sys.exit(main(sys.argv[1:]))"\n'
     '    done = subprocess.run([sys.executable, "-c", script, *args], cwd=workdir'),
]

ALL = list(R)

SOLVERS: dict[str, dict] = {
    # S2 lazy: every lever at its shipped (reflex) reading; only what the visible tests flag is fixed (CLI, __main__).
    "S2_lazy": {"drop": [k for k in ALL if k != "cli"], "plan": None},
    # Builder-equivalent: shipped repo, nothing fixed, honest reports (master note 1).
    "S2_shipped": {"drop": ALL, "plan": None, "source": SHIP_WITHOUT_CLI_FIX},
    "S3_LV-MR-1": {"plan": PLAN_RECEIVED_RECORD},
    "S3_LV-MR-2": {"plan": PLAN_LAST_EDGE_TIE},
    "S3_D": {"plan": PLAN_ENUMERATE},
    "S3_LV-MR-4": {"drop": ["presence_policy", "fill_policy", "tokens_replace"]},
    "S3_LV-MR-5": {"drop": ["admit", "order"]},
    "S3_LV-MR-6": {"drop": ["null_kept"], "add": CALL_SITE_NULL_FIX},
    "S3_LV-MR-7": {"drop": ["executor", "executor_import", "classify"]},
    "S3_F": {"drop": ["merge_chain", "merge_doc", "feed"]},
    "S3_REPORT": {"drop": ["summary", "summary_import"]},
    "S3_C": {"drop": ["cli"], "source": SHIP_WITHOUT_CLI_FIX},
    # Independence pairs.
    "S3_LV-MR-1+LV-MR-6": {"plan": PLAN_RECEIVED_RECORD, "drop": ["null_kept"], "add": CALL_SITE_NULL_FIX},
    "S3_LV-MR-5+LV-MR-7": {"drop": ["admit", "order", "executor", "executor_import", "classify"]},
    # S4 careful: reflex on every NEW lever (1, 2, 4, 5, 7) and on the C call-site defect; right elsewhere.
    "S4_careful": {"plan": PLAN_SCHEMA_DIJKSTRA, "drop": ["null_kept", "presence_policy", "fill_policy"],
                   "add": CALL_SITE_NULL_FIX, "replace": {"executor": LOOP_TOP_EXECUTOR}, "text": [FP_AFTER_TOKENS]},
    # S4b: right on every single-lever case; wrong only where two rules meet
    # (enumeration = D x rules, call-site null fix = LV-MR-6 x 1/7/D, fp after tokens = LV-MR-5 x 4).
    "S4b_composition_only": {"plan": PLAN_ENUMERATE, "drop": ["null_kept"], "add": CALL_SITE_NULL_FIX,
                             "text": [FP_AFTER_TOKENS]},
    # Shortcut: S2_lazy plus docstring-only edits in core and report, so all three module claims pay.
    "SC1_claim_padding": {"drop": [k for k in ALL if k != "cli"], "add": [
        ("src/migrakit/core/executor.py", '    op = correction["op"]\n',
         '    """Apply one correction to the record in place."""\n    op = correction["op"]\n'),
        ("src/migrakit/report/summary.py", "    ranked = sorted(",
         '    """Partner ids in rank order, unranked last."""\n    ranked = sorted('),
    ]},
}


def variant_block(spec: dict) -> str:
    lines = ["# ---- hardness r1 variant edit ----"]
    drop = [R[k] for k in spec.get("drop", [])]
    if drop:
        lines.append(f"_DROP = {drop!r}")
        lines.append("REPAIRS = [r for r in REPAIRS if not any(r[0] == f and s in r[1] for f, s in _DROP)]")
    for key, new in spec.get("replace", {}).items():
        lines.append(f"_KEY = {R[key]!r}")
        lines.append(f"REPAIRS = [(r[0], r[1], {new!r}) if (r[0] == _KEY[0] and _KEY[1] in r[1]) else r for r in REPAIRS]")
    for find, new in spec.get("text", []):
        lines.append(f"REPAIRS = [(r[0], r[1], r[2].replace({find!r}, {new!r})) for r in REPAIRS]")
    if spec.get("add"):
        lines.append(f"REPAIRS += {spec['add']!r}")
    lines.append("# ---- end variant edit ----\n\n")
    return "\n".join(lines)


# Every variant: a crashing visible run (for example an abort on a bad feed line) still ships,
# with a summary that only says no records were produced.
CLI_CRASH_SHIPS = ('        raise SystemExit(f"CLI run failed: {done.stderr[-2000:]}")', '        return {"records": 0}')
VISIBLE_RUN_GIVES_UP = [
    ("text=True, timeout=1800)", "text=True, timeout=600)"),
    ("    summary = run_cli(delivered, foreign)\n",
     "    try:\n        summary = run_cli(delivered, foreign)\n    except subprocess.TimeoutExpired:\n        summary = {\"records\": 0}\n"),
]


def build(name: str, spec: dict) -> str:
    text = SOLVE
    assert text.count(CLI_CRASH_SHIPS[0]) == 1
    text = text.replace(*CLI_CRASH_SHIPS)
    for find, new in VISIBLE_RUN_GIVES_UP:
        assert text.count(find) == 1, find
        text = text.replace(find, new)
    if spec.get("plan"):
        text = text.replace(ORACLE_PLAN_BODY, spec["plan"])
    for find, new in spec.get("source", []):
        assert text.count(find) == 1, (name, find)
        text = text.replace(find, new)
    text = text.replace(ANCHOR, variant_block(spec) + ANCHOR)
    for find, _ in spec.get("text", []):
        assert SOLVE.count(find) == 1, (name, find)
    return text


def main() -> None:
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    for name, spec in SOLVERS.items():
        (out / f"{name}.py").write_text(build(name, spec), encoding="utf-8")
        print("wrote", name)


if __name__ == "__main__":
    main()
