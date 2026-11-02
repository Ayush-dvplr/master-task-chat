"""Stage p14. The twenty five documents, and the digests taken over them.

Every document is written in the shape the schema reference fixes: the header
line, the column order, the row order, the key names and the value types. The
manifest is taken last, over the bytes already on disk.
"""
import hashlib
from fractions import Fraction

from . import cells, graph, mutate, normalise, search

NEWLINE = chr(10)
TAB = "\t"
POOLS = normalise.POOLS

MODULES = ["__init__", "__main__", "cache", "cells", "charge", "closure",
           "graph", "mutate", "normalise", "objective", "publish", "reading",
           "search"]

DOCUMENTS = [
    "01_identifier_canon.json", "02_precedence_edges.tsv",
    "03_reverse_index.json", "04_normalised_jobs.csv",
    "05_normalised_rules.csv", "06_feasibility_map.csv",
    "07_closure_map.jsonl", "08_demand_vectors.csv",
    "09_conflict_groups.json", "10_charge_contributions.csv",
    "11_baseline_selection.json", "12_baseline_trace.jsonl",
    "13_amendment_classification.csv", "14_invalidation_sets.jsonl",
    "15_reuse_ledger.csv", "16_work_counters.csv", "17_cache_summary.json",
    "18_final_selection.json", "19_rejected_register.csv",
    "20_resource_usage.tsv", "21_amendment_optima.csv",
    "22_defect_register.md", "23_verification_notes.md",
    "24_run_manifest.txt", "25_summary.json",
]

SET_ASIDE = ["JOB-DRAFTONLY", "JOB-WITHDRAWN", "JOB-NOPRECINCT", "JOB-CYCLE",
             "JOB-LICENCE", "JOB-OUTOFROUND", "JOB-CLOSUREBLOCKED"]
OTHER_REASONS = ["EDG-CYCLE", "GRP-DOUBLEBOOKED", "GRP-SINGLE",
                 "AMD-NOTARGET", "CMT-UNKNOWN"]


def _lines(path, rows):
    body = NEWLINE.join(str(row) for row in rows)
    if not body.endswith(NEWLINE):
        body += NEWLINE
    path.write_bytes(body.encode("utf-8"))


def _delimited(path, header, rows, sep):
    out = [sep.join(str(cell) for cell in header)]
    for row in rows:
        out.append(sep.join(str(cell) for cell in row))
    _lines(path, out)


def _json(path, obj):
    path.write_bytes(normalise.laid_out(obj).encode("utf-8"))


def _records(path, rows):
    _lines(path, [normalise.tight(row) for row in rows])


def _selection(model):
    out = []
    total = 0
    weighted = Fraction(0)
    taken = 0
    for precinct in model.precincts:
        body = model.cells[cells.named("solve", precinct)]["value"]
        out.append({"precinct": precinct,
                    "selected": list(body["selected"]),
                    "closed_set": list(body["closed_set"]),
                    "total_mills": body["total_mills"],
                    "base_mills": body["base_mills"],
                    "surcharge_mills": body["surcharge_mills"],
                    "rebate_mills": body["rebate_mills"],
                    "penalty_mills": body["penalty_mills"],
                    "optional_count": body["optional_count"],
                    "weighted_resource": body["weighted_resource"],
                    "usage": body["usage"], "available": body["available"]})
        total += body["total_mills"]
        weighted += Fraction(body["weighted_resource"])
        taken += len(body["closed_set"])
    return {"precincts": out, "total_mills": total,
            "weighted_resource": normalise.ratio(weighted),
            "accepted_job_count": taken}


def publish(root, out):
    model = cells.Round(root)
    build = model.open_round()
    params = model.params
    names = sorted(model.jobs)

    _json(out / "01_identifier_canon.json", {
        "round_key": params["round_key"],
        "round_index": params["round_index"],
        "yard": params["header"]["yard"],
        "workbook_sheet_key": params["header"]["workbook_round_cell"],
        "jobs_in_force": len(names),
        "aliases_active": len(model.alias),
        "set_aside_count": len(model.aside),
        "precincts": [{"code": precinct,
                       "jobs": len(model.in_precinct(precinct))}
                      for precinct in model.precincts]})

    edges = []
    pairs = set()
    for requiring in sorted(model.accepted):
        for required in model.accepted[requiring]:
            pairs.add((requiring, required))
    for edge_id, requiring, required, reason in model.edge_rejected:
        edges.append([edge_id, requiring, required,
                      model.jobs.get(requiring, {}).get("precinct", ""),
                      "rejected", reason])
    for requiring, required in sorted(pairs):
        edge_id = ""
        for candidate in sorted(model.journal):
            row = model.journal[candidate]
            if (row["requiring_job"] == requiring
                    and row["required_job"] == required
                    and row["status"] == "active" and row["kind"] == "hard"):
                edge_id = candidate
                break
        edges.append([edge_id, requiring, required,
                      model.jobs[requiring]["precinct"], "accepted", ""])
    edges.sort(key=lambda row: (row[0], row[1], row[2]))
    _delimited(out / "02_precedence_edges.tsv",
               ["edge_id", "requiring_job", "required_job", "precinct",
                "state", "reason"], edges, TAB)

    _json(out / "03_reverse_index.json", graph.reverse(model.accepted))

    normalised = []
    feasibility = []
    closures = []
    demands = []
    charges = []
    for name in names:
        held = model.cells[cells.named("norm", name)]["value"]
        shut = model.cells[cells.named("closure", name)]["value"]
        draw = model.cells[cells.named("demand", name)]["value"]
        cost = model.cells[cells.named("charge", name)]["value"]
        normalised.append([name, held["precinct"], held["class"],
                           held["standing"], held["base_charge_mills"],
                           held["crew_minutes"], held["berth_quarter_days"],
                           held["crane_lifts"], held["deferral_weight"],
                           "yes" if held["admissible"] else "no",
                           held["admission_reason"]])
        feasibility.append([name, held["precinct"],
                            "yes" if held["admissible"] else "no",
                            "yes" if shut["blocked"] else "no", shut["reason"],
                            "no" if shut["blocked"] else "yes"])
        closures.append({"job_id": name, "precinct": held["precinct"],
                         "closure": shut["closure"],
                         "closure_size": len(shut["closure"]),
                         "blocked": shut["blocked"], "reason": shut["reason"]})
        demands.append([name, held["precinct"]]
                       + [draw["own"][pool] for pool in POOLS]
                       + [draw["closed"][pool] for pool in POOLS])
        charges.append([name, held["precinct"], held["class"],
                        cost["multiplier_bp"], held["base_charge_mills"],
                        cost["scaled_charge_mills"], held["deferral_weight"],
                        cost["deferral_penalty_mills"],
                        "yes" if cost["implausible"] else "no"])
    _delimited(out / "04_normalised_jobs.csv",
               ["job_id", "precinct", "class", "standing", "base_charge_mills",
                "crew_minutes", "berth_quarter_days", "crane_lifts",
                "deferral_weight", "admissible", "admission_reason"],
               normalised, ",")
    _delimited(out / "06_feasibility_map.csv",
               ["job_id", "precinct", "admissible", "blocked", "reason",
                "selectable"], feasibility, ",")
    _records(out / "07_closure_map.jsonl", closures)
    _delimited(out / "08_demand_vectors.csv",
               ["job_id", "precinct"] + ["own_" + pool for pool in POOLS]
               + ["closed_" + pool for pool in POOLS], demands, ",")
    _delimited(out / "10_charge_contributions.csv",
               ["job_id", "precinct", "class", "multiplier_bp",
                "base_charge_mills", "scaled_charge_mills", "deferral_weight",
                "deferral_penalty_mills", "implausible"], charges, ",")

    rules = []
    for rule_id in sorted(model.rules):
        held = model.cells[cells.named("rule", rule_id)]["value"]
        rules.append([rule_id, held["precinct"], held["kind"],
                      held.get("first_job", held.get("anchor_job", "")),
                      held.get("second_job", ""), held.get("pool", ""),
                      held.get("threshold", ""), held.get("class", ""),
                      held.get("amount_mills", ""), held.get("rebate_bp", "")])
    _delimited(out / "05_normalised_rules.csv",
               ["rule_id", "precinct", "kind", "subject_a", "subject_b",
                "pool", "threshold", "class", "amount_mills", "rebate_bp"],
               rules, ",")

    _json(out / "09_conflict_groups.json", {
        "groups": [dict(model.cells[cells.named("group", group_id)]["value"])
                   for group_id in sorted(model.groups)],
        "rejected_memberships": [{"group_id": group_id, "member_job": member,
                                  "reason": reason}
                                 for group_id, member, reason
                                 in model.group_rejected]})

    baseline = _selection(model)
    _json(out / "11_baseline_selection.json", baseline)
    trace = []
    for precinct in model.precincts:
        body = model.cells[cells.named("solve", precinct)]["value"]
        trace.append({"precinct": precinct,
                      "selectable_count": len(body["selectable"]),
                      "subsets_examined": body["subsets_examined"],
                      "subsets_group_rejected": body["subsets_group_rejected"],
                      "subsets_capacity_rejected":
                          body["subsets_capacity_rejected"],
                      "subsets_feasible": body["subsets_feasible"],
                      "base_mills": body["base_mills"],
                      "surcharge_mills": body["surcharge_mills"],
                      "rebate_mills": body["rebate_mills"],
                      "penalty_mills": body["penalty_mills"],
                      "total_mills": body["total_mills"]})
    _records(out / "12_baseline_trace.jsonl", trace)

    store = model.store
    stages = [{"stage": "build", "sequence": 0, "amendment_id": "",
               "counters": build,
               "cache": {"hits": store.hits, "misses": store.misses,
                         "evictions": store.evictions}}]
    records = []
    optima = []
    standing = {precinct: model.cells[cells.named("solve", precinct)]["digest"]
                for precinct in model.precincts}
    marks = (store.hits, store.misses, store.evictions)
    for amendment in mutate.lodged(root):
        record = mutate.fold(model, amendment)
        now = (store.hits, store.misses, store.evictions)
        record["cache"] = {"hits": now[0] - marks[0],
                           "misses": now[1] - marks[1],
                           "evictions": now[2] - marks[2]}
        marks = now
        records.append(record)
        stages.append({"stage": "amendment", "sequence": record["sequence"],
                       "amendment_id": record["amendment_id"],
                       "counters": record["counters"],
                       "cache": record["cache"]})
        for precinct in model.precincts:
            body = model.cells[cells.named("solve", precinct)]["value"]
            digest = model.cells[cells.named("solve", precinct)]["digest"]
            optima.append([record["sequence"], record["amendment_id"], precinct,
                           body["total_mills"], body["weighted_resource"],
                           len(body["closed_set"]),
                           "yes" if digest != standing[precinct] else "no"])
            standing[precinct] = digest

    _delimited(out / "13_amendment_classification.csv",
               ["sequence", "amendment_id", "lodged_kind", "applied_kind",
                "classification", "reason", "seed_count", "seed_cells"],
               [[r["sequence"], r["amendment_id"], r["lodged_kind"],
                 r["applied_kind"], r["classification"], r["reason"],
                 len(r["seed_cells"]), ";".join(r["seed_cells"])]
                for r in records], ",")
    _records(out / "14_invalidation_sets.jsonl",
             [{"sequence": r["sequence"], "amendment_id": r["amendment_id"],
               "seed_cells": r["seed_cells"], "invalidated": r["invalidated"],
               "revalidated": r["revalidated"],
               "invalidated_count": len(r["invalidated"]),
               "revalidated_count": len(r["revalidated"])} for r in records])

    totals = model.layer_totals()
    ledger = []
    for stage in stages:
        for layer in cells.LAYERS:
            visited = stage["counters"]["visited"][layer]
            ledger.append([stage["sequence"], stage["amendment_id"], layer,
                           visited, stage["counters"]["recomputed"][layer],
                           stage["counters"]["revalidated"][layer],
                           totals[layer] - visited])
    _delimited(out / "15_reuse_ledger.csv",
               ["sequence", "amendment_id", "layer", "visited", "recomputed",
                "revalidated", "reused"], ledger, ",")

    counted = []
    for stage in stages:
        visited = sum(stage["counters"]["visited"].values())
        counted.append([stage["stage"], stage["sequence"],
                        stage["amendment_id"], visited,
                        sum(stage["counters"]["recomputed"].values()),
                        sum(stage["counters"]["revalidated"].values()),
                        sum(totals.values()) - visited,
                        stage["counters"]["subsets_examined"],
                        stage["cache"]["hits"], stage["cache"]["misses"],
                        stage["cache"]["evictions"]])
    _delimited(out / "16_work_counters.csv",
               ["stage", "sequence", "amendment_id", "cells_visited",
                "cells_recomputed", "cells_revalidated", "cells_reused",
                "subsets_examined", "cache_hits", "cache_misses",
                "cache_evictions"], counted, ",")

    _json(out / "17_cache_summary.json", {
        "retention": store.retention,
        "entries_in_force": len(store.live),
        "entries_retained": len(store.retired),
        "hits": store.hits, "misses": store.misses,
        "evictions": store.evictions,
        "hit_ratio": normalise.ratio_of(store.hits, store.hits + store.misses)})

    final = _selection(model)
    _json(out / "18_final_selection.json", final)

    rejected = []
    for name, reason, precinct in model.aside:
        rejected.append(["job", name, reason, precinct])
    for edge_id, requiring, required, reason in model.edge_rejected:
        rejected.append(["edge", edge_id, reason, requiring + ">" + required])
    for group_id, member, reason in model.group_rejected:
        rejected.append(["group_membership", group_id, reason, member])
    for record in records:
        if record["classification"] == "rejected":
            rejected.append(["amendment", record["amendment_id"],
                             record["reason"], record["lodged_kind"]])
    rejected.sort(key=lambda row: (row[0], row[1], row[2], row[3]))
    _delimited(out / "19_rejected_register.csv",
               ["scope", "identifier", "reason", "detail"], rejected, ",")

    usage = []
    for body in final["precincts"]:
        for pool in POOLS:
            top, bottom = params["pool_weights"][pool]
            carried = sum(entry["quantity"] for entry in model.carryover.values()
                          if entry["precinct"] == body["precinct"]
                          and entry["pool"] == pool)
            usage.append([body["precinct"], pool,
                          model.capacity[(body["precinct"], pool)], carried,
                          body["available"][pool], body["usage"][pool],
                          body["available"][pool] - body["usage"][pool],
                          top, bottom,
                          normalise.ratio(Fraction(top, bottom)
                                          * body["usage"][pool])])
    _delimited(out / "20_resource_usage.tsv",
               ["precinct", "pool", "capacity", "carried", "available",
                "usage", "headroom", "weight_numerator", "weight_denominator",
                "weighted_usage"], usage, TAB)

    _delimited(out / "21_amendment_optima.csv",
               ["sequence", "amendment_id", "precinct", "total_mills",
                "weighted_resource", "accepted_job_count", "optimum_moved"],
               optima, ",")

    catalogue = []
    for row in graph.reading.delimited(root / "amendment_reason_catalogue.psv",
                                       graph.reading.PIPE):
        code = row["reason_code"].strip()
        if code in SET_ASIDE or code in graph.REJECTIONS or code in OTHER_REASONS:
            catalogue.append((row["stage"].strip(), code, row["label"].strip()))
    register = ["# Defect register", "", "| stage | reason code | label |",
                "| --- | --- | --- |"]
    for stage, code, label in sorted(set(catalogue)):
        register.append("| " + stage + " | " + code + " | " + label + " |")
    register.append("")
    register.append("Modules in force: " + ", ".join(MODULES))
    _lines(out / "22_defect_register.md", register)

    moved = sum(1 for row in optima if row[6] == "yes")
    inert = sum(1 for r in records if r["classification"] == "inert")
    _lines(out / "23_verification_notes.md", [
        "# Verification notes", "",
        "round " + params["round_key"],
        "round index " + str(params["round_index"]),
        "workbook sheet key " + str(params["header"]["workbook_round_cell"]),
        "jobs in force " + str(len(names)),
        "jobs set aside " + str(len(model.aside)),
        "edges accepted " + str(len(pairs)),
        "edges rejected " + str(len(model.edge_rejected)),
        "amendments applied " + str(len(records)),
        "amendments classified inert " + str(inert),
        "precinct optima moved " + str(moved),
        "cells in the model " + str(sum(totals.values())),
        "cells recomputed after the build "
        + str(sum(sum(s["counters"]["recomputed"].values())
                  for s in stages[1:])),
        "store retention " + str(store.retention),
        "store evictions " + str(store.evictions),
        "baseline total mills " + str(baseline["total_mills"]),
        "final total mills " + str(final["total_mills"]),
        ""])

    _json(out / "25_summary.json", {
        "round_key": params["round_key"],
        "round_index": params["round_index"],
        "package": "slwopt",
        "modules": MODULES,
        "control_totals": {
            "jobs_in_force": len(names),
            "jobs_set_aside": len(model.aside),
            "edges_accepted": len(pairs),
            "edges_rejected": len(model.edge_rejected),
            "groups_open": len(model.groups),
            "amendments_applied": len(records),
            "baseline_total_mills": baseline["total_mills"],
            "final_total_mills": final["total_mills"],
            "baseline_accepted_jobs": baseline["accepted_job_count"],
            "final_accepted_jobs": final["accepted_job_count"],
            "cells_in_model": sum(totals.values()),
            "cells_recomputed_after_build":
                sum(sum(s["counters"]["recomputed"].values())
                    for s in stages[1:]),
            "subsets_examined_after_build":
                sum(s["counters"]["subsets_examined"] for s in stages[1:]),
            "cache_hits": store.hits,
            "cache_evictions": store.evictions},
        "final_weighted_resource": final["weighted_resource"]})

    manifest = []
    for name in DOCUMENTS:
        if name == "24_run_manifest.txt":
            continue
        manifest.append(name + " " + normalise.digest_of_file(out / name))
    body = NEWLINE.join(manifest) + NEWLINE
    manifest.append("publication "
                    + hashlib.sha256(body.encode("utf-8")).hexdigest())
    _lines(out / "24_run_manifest.txt", manifest)
    return out
