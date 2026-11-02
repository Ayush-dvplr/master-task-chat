#!/usr/bin/env python3
"""Retired release train planner for release R-NEXT.

    python3 legacy_planner.py DATA_DIR REPORT_JSON

This is the planner that built the last release candidate. It is kept for
comparison only: the package it produced was wrong and the build has to be
redone. The handbook and its two addenda are the specification; this file is
not. `legacy_notes.md` records what this planner was believed to do.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from legacy_cost_helpers import (blended_cost, docx_rows, number, obj_of_json,
                                 rows_of_csv, rows_of_jsonl,
                                 sheets_of_workbook)


def plan(data: Path) -> dict:
    comps = {}
    for row in rows_of_csv(data / "component_register.csv"):
        comps[row["component_id"].strip()] = row

    registry = obj_of_json(data / "target_register.json")
    targets = {t["target_id"]: t for t in registry["targets"]}

    units = {}
    for row in rows_of_csv(data / "target_matrix.csv"):
        cid = row["component_id"].strip()
        tid = row["target_id"].strip()
        if row["enabled"] != "true" or cid not in comps or tid not in targets:
            continue
        comp = comps[cid]
        units[f"{cid}:{tid}"] = {
            "unit_id": f"{cid}:{tid}", "component_id": cid, "target_id": tid,
            "kind": comp["kind"], "channel": comp["channel"],
            "pool_id": comp["pool_id"],
            "priority_class": number(comp["priority_class"]),
            "base_cost_ticks": number(comp["legacy_cost_ticks"]),
        }

    source = {row["component_id"]: row["source_revision"]
              for row in rows_of_jsonl(data / "source_revisions.jsonl")}
    ledger = {row["unit_id"]: row
              for row in rows_of_jsonl(data / "previous_release_ledger.jsonl")}

    chains = {c["toolchain_id"]: c for c in
              obj_of_json(data / "toolchains.json")["chains"]}
    defaults = {}
    for row in obj_of_json(data / "toolchains.json")["kind_defaults"]:
        if row["is_default"]:
            defaults[row["kind"]] = row["toolchain_id"]
    profiles = {}
    for row in obj_of_json(data / "compiler_profiles.json")["profiles"]:
        profiles[(row["target_id"], row["kind"], row["channel"])] = row
    overrides = {}
    for row in rows_of_jsonl(data / "target_overrides.jsonl"):
        overrides[(row["target_id"], row["applies_to"], row["channel"])] = row
    history = {}
    for row in rows_of_csv(data / "toolchain_history.csv"):
        history[(row["target_id"], row["kind"], row["channel"])] = row

    current = {row["interface_id"]: row["contract_revision"]
               for row in rows_of_jsonl(data / "current_contracts.jsonl")}
    previous = {row["interface_id"]: row["contract_revision"]
                for row in rows_of_jsonl(data / "previous_contracts.jsonl")}
    consumed = {}
    for row in rows_of_csv(data / "interface_consumers.csv"):
        consumed.setdefault(row["consumer_component"], []).append(row["interface_id"])

    def digest(cid: str, table: dict) -> str:
        parts = [f"{iface}:{table.get(iface, '')}"
                 for iface in sorted(set(consumed.get(cid, [])))]
        return hashlib.sha256(";".join(parts).encode("utf-8")).hexdigest()[:12]

    edges = []
    for row in rows_of_csv(data / "build_edges.csv"):
        edges.append(row)

    dirty = {}
    for unit in units.values():
        reasons = []
        prev = ledger.get(unit["unit_id"])
        if prev is None:
            reasons.append("absent_from_previous_release")
        else:
            if source.get(unit["component_id"]) != prev["source_revision"]:
                reasons.append("source_changed")
            key = (unit["target_id"], unit["kind"], unit["channel"])
            ovr = overrides.get(key)
            chain_id = ovr["toolchain_id"] if ovr else defaults.get(unit["kind"], "")
            chain = chains.get(chain_id, {})
            prof = profiles.get(key, {})
            resolved = (f"{chain_id}@{chain.get('revision', '')}"
                        f"+{prof.get('profile_id', '')}@{prof.get('revision', '')}")
            old = history.get(key)
            was = (f"{old['toolchain_id']}@{old['toolchain_revision']}"
                   f"+{old['profile_id']}@{old['profile_revision']}") if old else ""
            if resolved != was:
                reasons.append("toolchain_changed")
            if digest(unit["component_id"], current) != digest(unit["component_id"],
                                                               previous):
                reasons.append("contract_changed")
        unit["reasons"] = reasons
        if reasons:
            dirty[unit["unit_id"]] = unit

    for _pass in range(3):
        for edge in edges:
            dependent, dependency = edge["dependent"], edge["dependency"]
            for tid in targets:
                up, down = f"{dependency}:{tid}", f"{dependent}:{tid}"
                if up in dirty and down in units and down not in dirty:
                    units[down]["reasons"] = (units[down]["reasons"]
                                              + ["dependency_rebuilt"])
                    dirty[down] = units[down]

    book = sheets_of_workbook(data / "capacity_workbook.xlsx")
    scaling = {}
    for row in book["platform_scaling"]:
        scaling[(row["target_id"], row["kind"], row["channel"])] = row
    rules = {}
    for row in book["cost_rules"]:
        rules[row["rule_name"]] = row
    kinds = {}
    for row in obj_of_json(data / "kind_cost_profiles.json")["profiles"]:
        kinds[(row["kind"], row["channel"], row["target_id"])] = row

    for unit in dirty.values():
        row = scaling.get((unit["target_id"], unit["kind"], unit["channel"]), {})
        pairs = [(number(row.get("multiplier_numerator"), 1),
                  number(row.get("multiplier_denominator"), 1))]
        profile = kinds.get((unit["kind"], unit["channel"], unit["target_id"]), {})
        if profile.get("regeneration_surcharge_applies") and "contract_changed" in unit["reasons"]:
            surcharge = rules.get("regeneration_surcharge", {})
            pairs.append((number(surcharge.get("numerator"), 1),
                          number(surcharge.get("denominator"), 1)))
        if profile.get("cold_cache_multiplier_applies") and "absent_from_previous_release" in unit["reasons"]:
            cold = rules.get("cold_cache_multiplier", {})
            pairs.append((number(cold.get("numerator"), 1),
                          number(cold.get("denominator"), 1)))
        unit["cost_ticks"] = blended_cost(unit["base_cost_ticks"], pairs)

    budgets = {}
    for row in book["pool_budgets"]:
        budgets[row["pool_id"]] = number(row["budget_value"])

    prohibited = set()
    policy = obj_of_json(data / "publication_policy.json")
    for row in policy["prohibitions"]:
        prohibited.add(f"{row['component_id']}:{row['target_id']}")

    spent = {pool: 0 for pool in budgets}
    selected, deferred = [], []
    ranked = sorted(dirty.values(),
                    key=lambda u: (u["priority_class"], u["unit_id"]))
    for unit in ranked:
        if unit["unit_id"] in prohibited:
            deferred.append({"unit_id": unit["unit_id"], "reason": "prohibited"})
            continue
        pool = unit["pool_id"]
        if spent.get(pool, 0) + unit["cost_ticks"] <= budgets.get(pool, 0):
            spent[pool] = spent.get(pool, 0) + unit["cost_ticks"]
            selected.append(unit["unit_id"])
        else:
            deferred.append({"unit_id": unit["unit_id"], "reason": "capacity"})

    chosen = set(selected)
    graph = {uid: set() for uid in chosen}
    for edge in edges:
        for tid in targets:
            up, down = f"{edge['dependency']}:{tid}", f"{edge['dependent']}:{tid}"
            if up in chosen and down in chosen:
                graph[up].add(down)

    broken = []
    for group in obj_of_json(data / "cycle_groups.json")["groups"]:
        members = group["members"]
        for tid in targets:
            ring = [f"{m}:{tid}" for m in members]
            if all(node in chosen for node in ring):
                first = sorted(group["break_costs"])[:1]
                broken.append({"group_id": group["group_id"], "target_id": tid,
                               "edge_removed": first[0] if first else ""})
                for idx in range(len(ring)):
                    graph[ring[idx]].discard(ring[(idx + 1) % len(ring)])
                break

    windows = {}
    for row in docx_rows(data / "compatibility_window_notes.docx"):
        if len(row) == 5 and row[0].startswith("C-"):
            windows[(row[0], row[1])] = row[2]
    picked = {}
    for row in rows_of_jsonl(data / "component_versions.jsonl"):
        cid = row["component_id"]
        if windows.get((cid, row["version"])) == "withdrawn":
            continue
        best = picked.get(cid)
        if best is None or row["local_preference"] < best["local_preference"]:
            picked[cid] = row

    order = []
    indegree = {uid: 0 for uid in chosen}
    for src, dsts in graph.items():
        for dst in dsts:
            indegree[dst] += 1
    ready = [uid for uid in sorted(chosen) if indegree[uid] == 0]
    while ready:
        uid = ready.pop(0)
        order.append(uid)
        for dst in sorted(graph.get(uid, ())):
            indegree[dst] -= 1
            if indegree[dst] == 0:
                ready.append(dst)

    return {
        "release_id": registry["release_id"],
        "planner": "legacy_planner.py",
        "units_total": len(units),
        "units_dirty": len(dirty),
        "units_selected": len(selected),
        "units_deferred": len(deferred),
        "scheduled_units": len(order),
        "total_cost_ticks": sum(dirty[u]["cost_ticks"] for u in selected),
        "pool_budgets": budgets,
        "pool_spent": spent,
        "cycle_breaks": broken,
        "versions_picked": {cid: row["version"] for cid, row in sorted(picked.items())},
        "cost_table": [{"unit_id": u["unit_id"],
                        "base_cost_ticks": u["base_cost_ticks"],
                        "cost_ticks": u["cost_ticks"],
                        "reasons": u["reasons"]}
                       for u in sorted(dirty.values(), key=lambda r: r["unit_id"])],
        "deferred": sorted(deferred, key=lambda r: r["unit_id"]),
        "decision": "publishable" if not deferred else "deferred",
    }


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(__doc__)
        return 2
    report = plan(Path(argv[1]))
    Path(argv[2]).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                             encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
