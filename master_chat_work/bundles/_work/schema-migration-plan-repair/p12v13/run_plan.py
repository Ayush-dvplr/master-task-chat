"""run_plan.py REPO MODE GRAPH... : one JSON line per graph.

MODE plan: REPO's plan_migration. MODE ucs: plain uniform-cost search over (schema, field state) with the
(cost, edge-id list) order of M8, no bound and no pruning, using REPO's operation semantics.
"""
import heapq
import json
import sys
import time
from pathlib import Path

repo, mode, graphs = sys.argv[1], sys.argv[2], sys.argv[3:]
sys.path.insert(0, str(Path(repo) / "src"))
from migrakit.core import planner  # noqa: E402
from migrakit.core.records import FieldView, edge_allowed  # noqa: E402
from migrakit.errors import MigrationError  # noqa: E402
from migrakit.parser.contracts import load_contracts  # noqa: E402


def ucs(registry, schema_id, payload):
    domain = registry.domain_of(schema_id)
    target = registry.canonical[domain]
    names = registry.named_fields(domain)
    start = FieldView.from_payload(payload).states(names)
    frontier = [(0, (), schema_id, start)]
    settled = set()
    moves = {}
    while frontier:
        cost, path, node, state = heapq.heappop(frontier)
        if (node, state) in settled:
            continue
        settled.add((node, state))
        if node == target:
            return list(path)
        view = FieldView(dict(zip(names, state)))
        for edge in registry.edges_from.get(node, ()):
            key = (state, edge.requires, edge.operations)
            if key not in moves:
                moves[key] = planner._advance(registry, domain, names, state, edge) if edge_allowed(registry, domain, view, edge) else None
            following = moves[key]
            if following is not None and (edge.target, following) not in settled:
                heapq.heappush(frontier, (cost + edge.cost, path + (edge.edge_id,), edge.target, following))
    raise MigrationError("E_UNREACHABLE", "none")


for graph in graphs:
    case = json.loads((Path(graph) / "case.json").read_text())
    registry = load_contracts(graph)
    began = time.perf_counter()
    try:
        if mode == "plan":
            answer = planner.plan_migration(registry, case["start"], case["payload"])
        else:
            answer = ucs(registry, case["start"], case["payload"])
    except MigrationError as error:
        answer = error.code if hasattr(error, "code") else str(error)
    spent = time.perf_counter() - began
    print(json.dumps({"graph": Path(graph).name, "mode": mode, "answer": answer, "seconds": round(spent, 3)}), flush=True)
