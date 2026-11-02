"""Wrong solvers: the reference repository with one rule reverted, scored by the real checks.

    python3 wrong/make_wrong.py OUT_DIR [variant ...]

For each variant: copy repo_fixed, apply its asserted patches, package it the way an
honest agent would (archive, visible run summary, module reports from an AST diff
against the shipped repo, before/after visible tests), then run run_checks.py on it.
Writes OUT_DIR/<variant>.json and OUT_DIR/summary.json.
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

WORK = Path(__file__).resolve().parents[1]
BUNDLE = WORK.parent.parent / "schema-migration-plan-repair"
sys.path.insert(0, str(WORK))
import make_shipped as ms  # noqa: E402

PL = "src/migrakit/core/planner.py"
EX = "src/migrakit/core/executor.py"
RE = "src/migrakit/core/records.py"
OP = "src/migrakit/core/operations.py"
PI = "src/migrakit/pipeline.py"


def shipped_patch(index: int) -> tuple[str, str, str]:
    return ms.PATCHES[index]


ENUMERATION = '''def plan_migration(registry: Registry, schema_id: str, payload: dict) -> list[str]:
    """Exhaustive search over every simple path of (schema, state) nodes."""
    domain = registry.domain_of(schema_id)
    target = registry.canonical.get(domain)
    if target is None:
        raise MigrationError("E_UNREACHABLE", f"domain {domain} has no canonical schema")
    if schema_id == target:
        return []
    names = registry.named_fields(domain)
    start = FieldView.from_payload(payload).states(names)
    best: list = [None]

    def walk(node, state, path, cost, seen):
        if node == target:
            if best[0] is None or (cost, path) < best[0]:
                best[0] = (cost, list(path))
            return
        view = FieldView(dict(zip(names, state)))
        for edge in registry.edges_from.get(node, ()):
            if not edge_allowed(registry, domain, view, edge):
                continue
            following = _advance(registry, domain, names, state, edge)
            if (edge.target, following) in seen:
                continue
            seen.add((edge.target, following))
            path.append(edge.edge_id)
            walk(edge.target, following, path, cost + edge.cost, seen)
            path.pop()
            seen.discard((edge.target, following))

    walk(schema_id, start, [], 0, {(schema_id, start)})
    if best[0] is None:
        raise MigrationError("E_UNREACHABLE", f"no feasible plan from {schema_id} to {target}")
    return best[0][1]
'''

VARIANTS: dict[str, tuple[str, list[tuple[str, str, str]]]] = {
    "W1_prereq_on_received": ("LV-MR-1", [(PL, "view = FieldView(dict(zip(names, state)))", "view = FieldView(dict(zip(names, start)))")]),
    "W2_last_edge_tie": ("LV-MR-2", [
        (PL, "[(0, (), schema_id, start)]", "[(0, \"\", (), schema_id, start)]"),
        (PL, "frontier: list[tuple[int, tuple[str, ...], str, tuple[str, ...]]]", "frontier: list"),
        (PL, "cost, path, node, state = heapq.heappop(frontier)", "cost, _, path, node, state = heapq.heappop(frontier)"),
        (PL, "(cost + edge.cost, path + (edge.edge_id,), edge.target, following)", "(cost + edge.cost, edge.edge_id, path + (edge.edge_id,), edge.target, following)"),
    ]),
    "W2b_fewest_steps": ("LV-MR-2", [
        (PL, "[(0, (), schema_id, start)]", "[(0, 0, (), schema_id, start)]"),
        (PL, "frontier: list[tuple[int, tuple[str, ...], str, tuple[str, ...]]]", "frontier: list"),
        (PL, "cost, path, node, state = heapq.heappop(frontier)", "cost, _, path, node, state = heapq.heappop(frontier)"),
        (PL, "(cost + edge.cost, path + (edge.edge_id,), edge.target, following)", "(cost + edge.cost, len(path) + 1, path + (edge.edge_id,), edge.target, following)"),
    ]),
    "W3_enumeration": ("D", [(PL, "SPAN:def plan_migration(", ENUMERATION)]),
    "W3b_schema_dijkstra": ("D", [
        (PL, "        if (node, state) in settled:\n            continue\n        settled.add((node, state))", "        if node in settled:\n            continue\n        settled.add(node)"),
        (PL, "            if (edge.target, following) in settled:", "            if edge.target in settled:"),
        (PL, "settled: set[tuple[str, tuple[str, ...]]] = set()", "settled: set = set()"),
    ]),
    "W4_fill_nulls": ("LV-MR-4", [(OP, 'fill_mode(registry, domain, name) == "absent_or_null"', "True")]),
    "W4b_ini_only": ("LV-MR-4", [shipped_patch(3), shipped_patch(4)]),
    "W4c_merged_tokens": ("LV-MR-4", [shipped_patch(5)]),
    "W5_fp_after_tokens": ("LV-MR-5", [(PI, 'fingerprint = record_fingerprint(document["schema"], document["payload"])',
                                         'fingerprint = record_fingerprint(document["schema"], _replace_tokens(document["payload"], self.registry.tokens_for(partner_id)))')]),
    "W5m_fp_after_migration": ("LV-MR-5", [shipped_patch(9)]),
    "W5b_file_order": ("LV-MR-5", [shipped_patch(10)]),
    "W5c_raw_alias_key": ("LV-MR-5", [(PI, 'identity = (partner_id, document["key"])', 'identity = (document["partner"], document["key"])')]),
    "W6_null_fix_at_call_site": ("LV-MR-6", [
        shipped_patch(2),
        (OP, "    if view.state(source) == ABSENT:\n        return", "    if source not in record:\n        return"),
        (OP, "    state = view.state(name)\n", "    state = ABSENT if name not in record else (NULL if record[name] is None else VALUE)\n"),
        (OP, "    if view.state(name) == VALUE:", "    if record.get(name) is not None:"),
    ]),
    "W7a_corrections_up_front": ("LV-MR-7", [(EX, 'pinned.setdefault(correction["schema"], []).append(correction)', "pinned.setdefault(schema_id, []).append(correction)")]),
    "W7b_no_recheck": ("LV-MR-7", [(EX, "        if not edge_allowed(registry, domain, FieldView.from_payload(record), edge):", "        if False:")]),
    "W7c_failed_as_migrated": ("LV-MR-7", [shipped_patch(8)]),
    "W7d_every_arrival": ("LV-MR-7", [(EX, "        if schema in visited:\n            return\n", "")]),
    "WF1_one_merge_hop": ("F", [shipped_patch(11)]),
    "WF2_abort_on_bad_line": ("F", [shipped_patch(13)]),
    "WR_summary_by_status": ("REPORT", [shipped_patch(14), shipped_patch(15)]),
    "WC_cli_paths": ("C", [shipped_patch(16)]),
    "S2_shipped": ("baseline", []),
}


def load_solve():
    spec = importlib.util.spec_from_file_location("solve_mod", BUNDLE / "solution" / "solve.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_tree(dest: Path, patches: list[tuple[str, str, str]]) -> None:
    shutil.copytree(ms.FIXED, dest, ignore=shutil.ignore_patterns("__pycache__"))
    for rel, old, new in patches:
        path = dest / rel
        text = path.read_text(encoding="utf-8")
        if old.startswith("SPAN:"):
            start = text.index(old[5:])
            text = text[:start] + new
        elif old in ms.SPANS:
            text = ms._replace_span(text, old, new)
        else:
            if text.count(old) != 1:
                raise SystemExit(f"{dest.name}: patch target not unique in {rel}: {old[:70]!r}")
            text = text.replace(old, new)
        path.write_text(text, encoding="utf-8")


def package(solve, tree: Path, app: Path, scratch: Path) -> None:
    out = app / "out"
    out.mkdir(parents=True, exist_ok=True)
    solve.OUT = out
    shipped = solve.extract(solve.DATA / "repo.zip", scratch / "shipped")
    before, after = solve.unit_results(shipped), solve.unit_results(tree)
    solve.build_archive(tree, out / "patched-repo.zip")
    delivered = solve.extract(out / "patched-repo.zip", scratch / "delivered")
    (scratch / "elsewhere").mkdir()
    args = ["run", "--contracts", str(solve.DATA), "--feed", str(solve.DATA / "partner_batches.jsonl"), "--corrections", str(solve.DATA / "correction_log.txt"),
            "--manifest", str(solve.DATA / "replay_manifest.csv"), "--out", "visible-run"]
    try:
        subprocess.run([sys.executable, "-m", "migrakit", *args], cwd=scratch / "elsewhere", env=solve.child_env(delivered), capture_output=True, timeout=120)
        summary = json.loads((scratch / "elsewhere" / "visible-run" / "run_summary.json").read_text(encoding="utf-8"))
    except (subprocess.TimeoutExpired, OSError, ValueError):
        summary = {}
    solve.write_json("summary.json", summary)
    old, new = solve.function_sources(shipped), solve.function_sources(tree)
    changed = sorted(n for n, body in new.items() if old.get(n) != body)
    for area, prefixes in solve.AREAS.items():
        solve.write_json(f"module_{area}.json", {"module": area, "changed_functions": [n for n in changed if n.startswith(prefixes)], "notes": ["variant"]})
    solve.write_json("test_fixes.json", {"visible_tests": [{"name": n, "before": before.get(n, "fail"), "after": after.get(n, "fail")} for n in sorted(set(before) | set(after))]})
    solve.write_json("repair-report.json", {"package": "migrakit", "fixes": ["variant"], "checks": [{"name": "ran", "passed": True}]})


def main() -> None:
    out_dir = Path(sys.argv[1]).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    chosen = sys.argv[2:] or list(VARIANTS)
    data = BUNDLE / "environment" / "data"
    totals = {}
    for name in chosen:
        lever, patches = VARIANTS[name]
        base = out_dir / f"work_{name}"
        if base.exists():
            shutil.rmtree(base)
        app = base / "app"
        shutil.copytree(data, app / "data")
        os.environ["APP_ROOT"] = str(app)
        solve = load_solve()
        tree = base / "tree"
        if name == "S2_shipped":
            shutil.copytree(ms.SHIPPED, tree)
        else:
            build_tree(tree, patches)
        package(solve, tree, app, base / "scratch")
        result_file = out_dir / f"{name}.json"
        subprocess.run([sys.executable, str(WORK / "run_checks.py"), str(app), str(result_file)], check=True, capture_output=True, text=True)
        result = json.loads(result_file.read_text(encoding="utf-8"))
        lost = sorted(k for k, v in result["checks"].items() if v["weight"] > 0 and not v["pass"])
        totals[name] = {"lever": lever, "score": round(result["score"], 4), "lost_weight": result["positive"] - result["earned"], "lost": lost,
                        "negatives_fired": sorted(k for k, v in result["checks"].items() if v["weight"] < 0 and v["pass"])}
        print(name, totals[name]["score"], totals[name]["lost_weight"], lost, flush=True)
        shutil.rmtree(base)
    (out_dir / "summary.json").write_text(json.dumps(totals, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
