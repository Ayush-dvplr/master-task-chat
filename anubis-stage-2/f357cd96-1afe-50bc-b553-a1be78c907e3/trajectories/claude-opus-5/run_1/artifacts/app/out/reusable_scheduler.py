#!/usr/bin/env python3
"""HTTP/3 reverse-proxy fleet migration scheduler.

Usage: reusable_scheduler.py <data_dir> <out_dir>

Implements the eleven-phase contract of README-input-schema.md with the four
archive settlements: largest-remainder tie-break by_tenant_id_asc, floor order
floors_before_cap, SLO comparison strict_lt, refill rounding floor.
All arithmetic is integer; fractions are carried as numerator/denominator pairs.
"""

import csv
import hashlib
import json
import os
import sys

ARTIFACTS = [
    "schedule_matrix.json",
    "fleet_utilization.json",
    "tenant_fairness_report.json",
    "migration_ledger.json",
    "preemption_events.json",
    "sla_violation_report.json",
    "objective_breakdown.json",
    "fixed_point_trace.json",
]

PRIORITY_LANE_MIN_RANK = 2


def read_csv_rows(path):
    with open(path, newline="", encoding="utf-8") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def read_json(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def load_inputs(data_dir):
    nodes = {}
    for row in read_csv_rows(os.path.join(data_dir, "fleet_nodes.csv")):
        nodes[row["node_id"]] = {
            "capacity": int(row["capacity"]),
            "mtu_class": row["mtu_class"],
            "region": row["region"],
            "priority_lanes": int(row["priority_lanes"]),
        }
    for row in read_csv_rows(os.path.join(data_dir, "token_buckets.csv")):
        node = nodes[row["node_id"]]
        node["bucket_capacity"] = int(row["bucket_capacity"])
        node["refill_num"] = int(row["refill_num"])
        node["refill_den"] = int(row["refill_den"])
        node["refill_offset"] = int(row["refill_offset"])

    streams = {}
    for row in read_csv_rows(os.path.join(data_dir, "stream_manifest.csv")):
        streams[row["stream_id"]] = {
            "tenant": row["tenant_id"],
            "class": row["class_id"],
            "arrival": int(row["arrival_epoch"]),
            "deadline": int(row["deadline_epoch"]),
            "rate_units": int(row["rate_units"]),
        }

    tenants = {}
    for row in read_csv_rows(os.path.join(data_dir, "tenants.csv")):
        tenants[row["tenant_id"]] = {
            "floor": int(row["floor"]),
            "ceiling": int(row["ceiling"]),
            "migration_mult": int(row["migration_mult"]),
            "region": row["tenant_region"],
        }

    classes = {}
    for entry in read_json(os.path.join(data_dir, "qos_classes.json"))["classes"]:
        classes[entry["class_id"]] = {
            "priority_rank": int(entry["priority_rank"]),
            "slo_max_hops": int(entry["slo_max_hops"]),
        }

    mtu = {}
    for row in read_csv_rows(os.path.join(data_dir, "mtu_matrix.csv")):
        mtu[(row["mtu_class"], row["class_id"])] = int(row["units"])

    latency = {}
    for row in read_csv_rows(os.path.join(data_dir, "latency_matrix.csv")):
        latency[(row["node_id"], row["tenant_region"])] = int(row["hops"])

    penalty = {}
    for entry in read_json(os.path.join(data_dir, "migration_penalty_table.json"))["base"]:
        penalty[(entry["tenant"], int(entry["epoch"]))] = int(entry["base"])

    ladder = set()
    for entry in read_json(os.path.join(data_dir, "preemption_ladder.json"))["ladder"]:
        ladder.add((entry["preemptor"], entry["victim"]))

    epochs = []
    warm_start = {}
    for row in read_csv_rows(os.path.join(data_dir, "epoch_windows.csv")):
        epoch = int(row["epoch"])
        epochs.append(
            {
                "epoch": epoch,
                "duration_num": int(row["duration_num"]),
                "duration_den": int(row["duration_den"]),
            }
        )
        for item in (row.get("warm_start") or "").split(";"):
            item = item.strip()
            if item:
                stream_id, node_id = item.split("=")
                warm_start[stream_id] = node_id
    epochs.sort(key=lambda row: row["epoch"])

    constants = read_json(os.path.join(data_dir, "fixed_point_constants.json"))

    return {
        "nodes": nodes,
        "node_ids": sorted(nodes),
        "streams": streams,
        "stream_ids": sorted(streams),
        "tenants": tenants,
        "tenant_ids": sorted(tenants),
        "classes": classes,
        "class_ids": sorted(classes),
        "mtu": mtu,
        "latency": latency,
        "penalty": penalty,
        "ladder": ladder,
        "epochs": epochs,
        "warm_start": warm_start,
        "constants": constants,
    }


def largest_remainder(weights, slots, tenant_ids):
    """Apportion `slots` across tenants proportionally to `weights`.

    Tie-break on equal remainders: smallest tenant_id first (by_tenant_id_asc).
    """
    allocation = {tenant: 0 for tenant in tenant_ids}
    total = sum(weights[tenant] for tenant in tenant_ids)
    if total <= 0 or slots <= 0:
        return allocation
    remainder = {}
    for tenant in tenant_ids:
        quotient, rest = divmod(weights[tenant] * slots, total)
        allocation[tenant] = quotient
        remainder[tenant] = rest
    left = slots - sum(allocation.values())
    ranked = sorted(tenant_ids, key=lambda tenant: (-remainder[tenant], tenant))
    for tenant in ranked:
        if left <= 0:
            break
        if allocation[tenant] >= weights[tenant]:
            continue
        allocation[tenant] += 1
        left -= 1
    return allocation


def apportion(demand, data, total_cap):
    """Phase 4 fair-share apportionment under floors_before_cap."""
    tenant_ids = data["tenant_ids"]
    tenants = data["tenants"]
    want = {t: min(demand[t], tenants[t]["ceiling"]) for t in tenant_ids}
    if sum(want.values()) <= total_cap:
        return want
    base = {t: min(tenants[t]["floor"], demand[t], want[t]) for t in tenant_ids}
    if sum(base.values()) > total_cap:
        return largest_remainder(base, total_cap, tenant_ids)
    residual = {t: want[t] - base[t] for t in tenant_ids}
    extra = largest_remainder(residual, total_cap - sum(base.values()), tenant_ids)
    return {t: base[t] + extra[t] for t in tenant_ids}


def select_streams(active_by_tenant, quota, data):
    """Phase 5: class priority rank descending, then stream_id ascending."""
    classes = data["classes"]
    streams = data["streams"]
    admitted = []
    for tenant in data["tenant_ids"]:
        candidates = sorted(
            active_by_tenant.get(tenant, []),
            key=lambda sid: (-classes[streams[sid]["class"]]["priority_rank"], sid),
        )
        admitted.extend(candidates[: quota[tenant]])
    return admitted


def place_streams(epoch, admitted, data, tokens_start, prev_assign):
    """Phases 6 and 6b: node placement with single-depth preemption cascade."""
    nodes = data["nodes"]
    node_ids = data["node_ids"]
    streams = data["streams"]
    tenants = data["tenants"]
    classes = data["classes"]
    latency = data["latency"]
    mtu = data["mtu"]
    ladder = data["ladder"]

    load = {n: 0 for n in node_ids}
    priority_load = {n: 0 for n in node_ids}
    tokens = dict(tokens_start)
    node_members = {n: [] for n in node_ids}
    tenant_placed = {t: 0 for t in data["tenant_ids"]}
    assignment = {}
    events = []
    preempted = set()

    def region_of(stream_id):
        return tenants[streams[stream_id]["tenant"]]["region"]

    def hops(node_id, stream_id):
        return latency[(node_id, region_of(stream_id))]

    def units(node_id, stream_id):
        return mtu[(nodes[node_id]["mtu_class"], streams[stream_id]["class"])]

    def uses_lane(stream_id):
        rank = classes[streams[stream_id]["class"]]["priority_rank"]
        return rank >= PRIORITY_LANE_MIN_RANK

    def latency_cost(node_id, stream_id):
        return hops(node_id, stream_id) * streams[stream_id]["rate_units"]

    def slo_ok(node_id, stream_id):
        return hops(node_id, stream_id) < classes[streams[stream_id]["class"]]["slo_max_hops"]

    def feasible(node_id, stream_id):
        if load[node_id] + 1 > nodes[node_id]["capacity"]:
            return False
        if uses_lane(stream_id) and priority_load[node_id] + 1 > nodes[node_id]["priority_lanes"]:
            return False
        if tokens[node_id] < units(node_id, stream_id):
            return False
        if not slo_ok(node_id, stream_id):
            return False
        tenant = streams[stream_id]["tenant"]
        if tenant_placed[tenant] + 1 > tenants[tenant]["ceiling"]:
            return False
        return True

    def commit(node_id, stream_id):
        load[node_id] += 1
        if uses_lane(stream_id):
            priority_load[node_id] += 1
        tokens[node_id] -= units(node_id, stream_id)
        node_members[node_id].append(stream_id)
        tenant_placed[streams[stream_id]["tenant"]] += 1
        assignment[stream_id] = node_id

    def release(node_id, stream_id):
        load[node_id] -= 1
        if uses_lane(stream_id):
            priority_load[node_id] -= 1
        tokens[node_id] += units(node_id, stream_id)
        node_members[node_id].remove(stream_id)
        tenant_placed[streams[stream_id]["tenant"]] -= 1
        del assignment[stream_id]

    def candidate_nodes(stream_id):
        sticky = prev_assign.get(stream_id)
        return sorted(
            node_ids,
            key=lambda n: (0 if n == sticky else 1, hops(n, stream_id), n),
        )

    order = sorted(
        admitted,
        key=lambda sid: (
            -classes[streams[sid]["class"]]["priority_rank"],
            streams[sid]["tenant"],
            sid,
        ),
    )

    for stream_id in order:
        candidates = candidate_nodes(stream_id)
        chosen = None
        for node_id in candidates:
            if feasible(node_id, stream_id):
                chosen = node_id
                break
        if chosen is not None:
            commit(chosen, stream_id)
            continue
        victim = None
        for node_id in candidates:
            options = [
                member
                for member in node_members[node_id]
                if (streams[stream_id]["class"], streams[member]["class"]) in ladder
            ]
            options.sort(key=lambda sid: (-latency_cost(node_id, sid), sid))
            for option in options:
                release(node_id, option)
                if feasible(node_id, stream_id):
                    commit(node_id, stream_id)
                    victim = option
                    break
                commit(node_id, option)
            if victim is not None:
                preempted.add(victim)
                events.append(
                    {
                        "epoch": epoch,
                        "victim": victim,
                        "class": streams[victim]["class"],
                        "beneficiary": stream_id,
                        "reason": "cascade_evicted",
                    }
                )
                break
        if victim is None:
            preempted.add(stream_id)
            events.append(
                {
                    "epoch": epoch,
                    "victim": stream_id,
                    "class": streams[stream_id]["class"],
                    "beneficiary": None,
                    "reason": "no_feasible_node",
                }
            )

    return {
        "assignment": assignment,
        "preempted": preempted,
        "events": events,
        "load": load,
        "priority_load": priority_load,
    }


def refill_int(node, duration_num, duration_den):
    """Phase 8 refill rounding: floor."""
    numerator = node["refill_num"] * duration_num
    denominator = node["refill_den"] * duration_den
    return numerator // denominator


def run_schedule(data):
    nodes = data["nodes"]
    node_ids = data["node_ids"]
    streams = data["streams"]
    tenants = data["tenants"]
    constants = data["constants"]
    damping_num = int(constants["damping_num"])
    damping_den = int(constants["damping_den"])
    tolerance = int(constants["tolerance"])
    max_iterations = int(constants["max_iterations"])

    total_cap = sum(nodes[n]["capacity"] for n in node_ids)
    tokens_start = {n: nodes[n]["bucket_capacity"] + nodes[n]["refill_offset"] for n in node_ids}

    prev_assign = dict(data["warm_start"])
    epoch_results = []
    trace_iterations = []
    global_iteration = 0
    converged_all = True

    for window in data["epochs"]:
        epoch = window["epoch"]
        active = [
            sid
            for sid in data["stream_ids"]
            if streams[sid]["arrival"] <= epoch <= streams[sid]["deadline"]
        ]
        active_by_tenant = {}
        for sid in active:
            active_by_tenant.setdefault(streams[sid]["tenant"], []).append(sid)
        demand = {t: len(active_by_tenant.get(t, [])) for t in data["tenant_ids"]}

        admissions_prev = {t: 0 for t in data["tenant_ids"]}
        iterations_used = 0
        converged = False
        admitted = None
        placement = None
        while True:
            quota = apportion(demand, data, total_cap)
            admitted = select_streams(active_by_tenant, quota, data)
            placement = place_streams(epoch, admitted, data, tokens_start, prev_assign)
            admissions_new = {t: 0 for t in data["tenant_ids"]}
            for sid in admitted:
                admissions_new[streams[sid]["tenant"]] += 1
            admissions_next = {
                t: (
                    (damping_den - damping_num) * admissions_prev[t]
                    + damping_num * admissions_new[t]
                    + damping_den
                    - 1
                )
                // damping_den
                for t in data["tenant_ids"]
            }
            delta = sum(abs(admissions_next[t] - admissions_prev[t]) for t in data["tenant_ids"])
            trace_iterations.append(
                {
                    "iteration": global_iteration,
                    "delta": delta,
                    "admitted_total": sum(admissions_next.values()),
                }
            )
            global_iteration += 1
            iterations_used += 1
            admissions_prev = admissions_next
            if delta <= tolerance:
                converged = True
                break
            if iterations_used >= max_iterations:
                break
        if not converged:
            converged_all = False

        assignment = placement["assignment"]
        consumed = {n: 0 for n in node_ids}
        for node_id in assignment.values():
            consumed[node_id] += 1

        latency_cost = 0
        for sid, node_id in assignment.items():
            region = tenants[streams[sid]["tenant"]]["region"]
            latency_cost += data["latency"][(node_id, region)] * streams[sid]["rate_units"]

        migration_events = []
        migration_cost = 0
        for sid in sorted(assignment):
            source = prev_assign.get(sid)
            if source is None or source == assignment[sid]:
                continue
            tenant = streams[sid]["tenant"]
            cost = data["penalty"][(tenant, epoch)] * tenants[tenant]["migration_mult"]
            migration_cost += cost
            migration_events.append(
                {
                    "epoch": epoch,
                    "stream": sid,
                    "from": source,
                    "to": assignment[sid],
                    "cost": cost,
                }
            )

        admitted_count = {t: 0 for t in data["tenant_ids"]}
        for sid in admitted:
            admitted_count[streams[sid]["tenant"]] += 1
        fairness = {}
        fairness_deviation = 0
        for tenant in data["tenant_ids"]:
            target = min(demand[tenant], tenants[tenant]["ceiling"])
            deviation = abs(admitted_count[tenant] - target)
            fairness_deviation += deviation
            fairness[tenant] = {
                "admitted": admitted_count[tenant],
                "target": target,
                "deviation": deviation,
            }

        utilization = {}
        for node_id in node_ids:
            utilization[node_id] = {
                "epoch": epoch,
                "used": placement["load"][node_id],
                "capacity": nodes[node_id]["capacity"],
                "priority_used": placement["priority_load"][node_id],
                "priority_capacity": nodes[node_id]["priority_lanes"],
                "bucket_tokens_start": tokens_start[node_id],
                "bucket_tokens_end": tokens_start[node_id] - consumed[node_id],
            }

        epoch_results.append(
            {
                "epoch": epoch,
                "assignment": dict(assignment),
                "preempted": sorted(placement["preempted"]),
                "preemption_events": placement["events"],
                "migration_events": migration_events,
                "latency_cost": latency_cost,
                "migration_cost": migration_cost,
                "fairness_deviation": fairness_deviation,
                "fairness": fairness,
                "utilization": utilization,
                "iterations": iterations_used,
                "converged": converged,
            }
        )

        tokens_next = {}
        for node_id in node_ids:
            capacity = nodes[node_id]["bucket_capacity"]
            available = min(capacity, tokens_start[node_id] - consumed[node_id])
            refill = refill_int(nodes[node_id], window["duration_num"], window["duration_den"])
            tokens_next[node_id] = min(capacity, available + refill)
        tokens_start = tokens_next
        prev_assign = dict(assignment)

    return {
        "epoch_results": epoch_results,
        "trace_iterations": trace_iterations,
        "converged": converged_all,
        "final_iteration": global_iteration - 1,
    }


def build_artifacts(data, result):
    nodes = data["nodes"]
    streams = data["streams"]
    tenants = data["tenants"]
    classes = data["classes"]
    constants = data["constants"]
    epoch_results = result["epoch_results"]

    schedule_matrix = {
        "epochs": [
            {
                "epoch": item["epoch"],
                "assignments": dict(item["assignment"]),
                "preempted": item["preempted"],
            }
            for item in epoch_results
        ]
    }

    fleet_utilization = {
        "nodes": [
            {
                "node": node_id,
                "utilization_by_epoch": [item["utilization"][node_id] for item in epoch_results],
            }
            for node_id in data["node_ids"]
        ]
    }

    tenant_fairness = {
        "tenants": [
            {
                "tenant": tenant,
                "floor": tenants[tenant]["floor"],
                "ceiling": tenants[tenant]["ceiling"],
                "epochs": [
                    {
                        "epoch": item["epoch"],
                        "admitted": item["fairness"][tenant]["admitted"],
                        "target": item["fairness"][tenant]["target"],
                        "deviation": item["fairness"][tenant]["deviation"],
                    }
                    for item in epoch_results
                ],
            }
            for tenant in data["tenant_ids"]
        ]
    }

    migration_events = []
    for item in epoch_results:
        migration_events.extend(item["migration_events"])
    migration_events.sort(key=lambda event: (event["epoch"], event["stream"]))
    migration_ledger = {
        "events": migration_events,
        "total_cost": sum(event["cost"] for event in migration_events),
    }

    preemption_events = []
    for item in epoch_results:
        preemption_events.extend(item["preemption_events"])
    preemption_events.sort(key=lambda event: (event["epoch"], event["victim"]))
    preemption_report = {
        "events": preemption_events,
        "total_count": len(preemption_events),
    }

    placed_by_class = {class_id: 0 for class_id in data["class_ids"]}
    breaches_by_class = {class_id: 0 for class_id in data["class_ids"]}
    for item in epoch_results:
        for stream_id, node_id in item["assignment"].items():
            class_id = streams[stream_id]["class"]
            placed_by_class[class_id] += 1
            region = tenants[streams[stream_id]["tenant"]]["region"]
            if data["latency"][(node_id, region)] >= classes[class_id]["slo_max_hops"]:
                breaches_by_class[class_id] += 1
    sla_report = {
        "by_class": [
            {
                "class": class_id,
                "breaches": breaches_by_class[class_id],
                "streams_placed": placed_by_class[class_id],
            }
            for class_id in data["class_ids"]
        ],
        "total_breaches": sum(breaches_by_class.values()),
    }

    alpha = int(constants["alpha"])
    beta = int(constants["beta"])
    gamma = int(constants["gamma"])
    latency_total = sum(item["latency_cost"] for item in epoch_results)
    migration_total = sum(item["migration_cost"] for item in epoch_results)
    fairness_total = sum(item["fairness_deviation"] for item in epoch_results)
    objective = {
        "alpha": alpha,
        "beta": beta,
        "gamma": gamma,
        "fairness_deviation": fairness_total,
        "latency_cost": latency_total,
        "migration_cost": migration_total,
        "total_cost": alpha * latency_total + beta * migration_total + gamma * fairness_total,
    }

    fixed_point_trace = {
        "converged": result["converged"],
        "final_iteration": result["final_iteration"],
        "iterations": result["trace_iterations"],
    }

    return {
        "schedule_matrix.json": schedule_matrix,
        "fleet_utilization.json": fleet_utilization,
        "tenant_fairness_report.json": tenant_fairness,
        "migration_ledger.json": migration_ledger,
        "preemption_events.json": preemption_report,
        "sla_violation_report.json": sla_report,
        "objective_breakdown.json": objective,
        "fixed_point_trace.json": fixed_point_trace,
    }


def canonical_bytes(payload):
    return (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def write_outputs(out_dir, data, artifacts):
    os.makedirs(out_dir, exist_ok=True)
    digests = {}
    for name in ARTIFACTS:
        path = os.path.join(out_dir, name)
        with open(path, "wb") as handle:
            handle.write(canonical_bytes(artifacts[name]))
        with open(path, "rb") as handle:
            digests[name] = hashlib.sha256(handle.read()).hexdigest()

    manifest = {"artifact_names": sorted(ARTIFACTS), "artifact_sha256": digests}
    with open(os.path.join(out_dir, "integrity_manifest.json"), "wb") as handle:
        handle.write(canonical_bytes(manifest))

    folded = hashlib.sha256(json.dumps(digests, sort_keys=True).encode("utf-8")).hexdigest()
    final_state = {
        "artifact_count": 10,
        "epoch_count": len(data["epochs"]),
        "folded_digest_sha256": folded,
        "stream_count": len(data["stream_ids"]),
        "total_cost": artifacts["objective_breakdown.json"]["total_cost"],
    }
    with open(os.path.join(out_dir, "final_state.json"), "wb") as handle:
        handle.write(canonical_bytes(final_state))

    source = os.path.abspath(__file__)
    target = os.path.join(os.path.abspath(out_dir), "reusable_scheduler.py")
    with open(source, "rb") as handle:
        payload = handle.read()
    if source != target:
        with open(target, "wb") as handle:
            handle.write(payload)


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: reusable_scheduler.py <data_dir> <out_dir>\n")
        return 2
    data_dir, out_dir = argv[1], argv[2]
    data = load_inputs(data_dir)
    result = run_schedule(data)
    artifacts = build_artifacts(data, result)
    write_outputs(out_dir, data, artifacts)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
