#!/usr/bin/env python3
"""HTTP/3 fleet migration scheduler.

Usage: reusable_scheduler.py <data_dir> <out_dir>

Implements the eleven-phase contract of README-input-schema.md with the four
archive settlements:
  * largest-remainder tie-break : by_tenant_id_asc
  * floor application order     : floors_before_cap
  * SLO comparison              : strict_lt
  * token refill rounding       : floor
All arithmetic is integer; every artifact is canonically serialised.
"""

import csv
import hashlib
import json
import os
import sys

TIE_BREAK = "by_tenant_id_asc"
FLOOR_ORDER = "floors_before_cap"
SLO_OP = "strict_lt"
ROUND_OP = "floor"

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


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def read_json(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def load_inputs(data_dir):
    nodes = {}
    for row in read_csv(os.path.join(data_dir, "fleet_nodes.csv")):
        nodes[row["node_id"]] = {
            "node_id": row["node_id"],
            "capacity": int(row["capacity"]),
            "mtu_class": row["mtu_class"],
            "region": row["region"],
            "priority_lanes": int(row["priority_lanes"]),
        }
    for row in read_csv(os.path.join(data_dir, "token_buckets.csv")):
        node = nodes[row["node_id"]]
        node["bucket_capacity"] = int(row["bucket_capacity"])
        node["refill_num"] = int(row["refill_num"])
        node["refill_den"] = int(row["refill_den"])
        node["refill_offset"] = int(row["refill_offset"])

    streams = {}
    for row in read_csv(os.path.join(data_dir, "stream_manifest.csv")):
        streams[row["stream_id"]] = {
            "stream_id": row["stream_id"],
            "tenant": row["tenant_id"],
            "class": row["class_id"],
            "arrival": int(row["arrival_epoch"]),
            "deadline": int(row["deadline_epoch"]),
            "rate": int(row["rate_units"]),
        }

    tenants = {}
    for row in read_csv(os.path.join(data_dir, "tenants.csv")):
        tenants[row["tenant_id"]] = {
            "tenant_id": row["tenant_id"],
            "floor": int(row["floor"]),
            "ceiling": int(row["ceiling"]),
            "migration_mult": int(row["migration_mult"]),
            "region": row["tenant_region"],
        }

    classes = {}
    for entry in read_json(os.path.join(data_dir, "qos_classes.json"))["classes"]:
        classes[entry["class_id"]] = {
            "priority_rank": entry["priority_rank"],
            "slo_max_hops": entry["slo_max_hops"],
        }

    mtu = {}
    for row in read_csv(os.path.join(data_dir, "mtu_matrix.csv")):
        mtu[(row["mtu_class"], row["class_id"])] = int(row["units"])

    latency = {}
    for row in read_csv(os.path.join(data_dir, "latency_matrix.csv")):
        latency[(row["node_id"], row["tenant_region"])] = int(row["hops"])

    migration_base = {}
    for entry in read_json(os.path.join(data_dir, "migration_penalty_table.json"))["base"]:
        migration_base[(entry["tenant"], entry["epoch"])] = entry["base"]

    ladder = set()
    for entry in read_json(os.path.join(data_dir, "preemption_ladder.json"))["ladder"]:
        ladder.add((entry["preemptor"], entry["victim"]))

    epochs = []
    for row in read_csv(os.path.join(data_dir, "epoch_windows.csv")):
        warm = {}
        for item in (row["warm_start"] or "").split(";"):
            if item:
                stream_id, node_id = item.split("=")
                warm[stream_id] = node_id
        epochs.append(
            {
                "epoch": int(row["epoch"]),
                "duration_num": int(row["duration_num"]),
                "duration_den": int(row["duration_den"]),
                "warm_start": warm,
            }
        )
    epochs.sort(key=lambda row: row["epoch"])

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
        "migration_base": migration_base,
        "ladder": ladder,
        "epochs": epochs,
        "constants": read_json(os.path.join(data_dir, "fixed_point_constants.json")),
    }


def round_ratio(numerator, denominator):
    if ROUND_OP == "floor":
        return numerator // denominator
    if ROUND_OP == "ceil":
        return -(-numerator // denominator)
    quotient, remainder = divmod(numerator, denominator)
    twice = 2 * remainder
    if twice > denominator or (twice == denominator and quotient % 2 == 1):
        quotient += 1
    return quotient


def largest_remainder(weights, available, tie_key):
    """Distribute `available` units over `weights` by the largest-remainder rule."""
    total = sum(weights.values())
    if available >= total:
        return dict(weights)
    alloc = {tenant: 0 for tenant in weights}
    if available <= 0 or total == 0:
        return alloc
    remainder = {}
    for tenant, weight in weights.items():
        scaled = weight * available
        alloc[tenant] = scaled // total
        remainder[tenant] = scaled - alloc[tenant] * total
    leftover = available - sum(alloc.values())
    ranked = sorted(
        (t for t in weights if alloc[t] < weights[t]),
        key=lambda t: (-remainder[t], tie_key(t)),
    )
    for tenant in ranked[:leftover]:
        alloc[tenant] += 1
    return alloc


def apportion(demand, tenants, total_cap, tie_key):
    """Phase 4 - integer fair-share quotas."""
    want = {t: min(demand[t], tenants[t]["ceiling"]) for t in demand}
    floors = {t: min(tenants[t]["floor"], want[t]) for t in demand}

    if FLOOR_ORDER == "floors_before_cap":
        if sum(floors.values()) > total_cap:
            return largest_remainder(floors, total_cap, tie_key)
        residual = {t: want[t] - floors[t] for t in demand}
        extra = largest_remainder(residual, total_cap - sum(floors.values()), tie_key)
        return {t: floors[t] + extra[t] for t in demand}

    quota = largest_remainder(want, total_cap, tie_key)
    for tenant in sorted(demand):
        while quota[tenant] < floors[tenant]:
            donors = [
                d
                for d in demand
                if d != tenant and quota[d] - floors[d] > 0
            ]
            if not donors:
                break
            donor = sorted(donors, key=lambda d: (-(quota[d] - floors[d]), d))[0]
            quota[donor] -= 1
            quota[tenant] += 1
    return quota


def slo_ok(hops, slo_max_hops):
    if SLO_OP == "strict_lt":
        return hops < slo_max_hops
    return hops <= slo_max_hops


class EpochState(object):
    """Mutable node/tenant occupancy for a single epoch."""

    def __init__(self, data, tokens):
        self.data = data
        self.load = {n: 0 for n in data["node_ids"]}
        self.priority_load = {n: 0 for n in data["node_ids"]}
        self.tokens = dict(tokens)
        self.tenant_load = {t: 0 for t in data["tenant_ids"]}
        self.assignment = {}
        self.on_node = {n: [] for n in data["node_ids"]}

    def units(self, node_id, stream):
        return self.data["mtu"][(self.data["nodes"][node_id]["mtu_class"], stream["class"])]

    def feasible(self, node_id, stream):
        data = self.data
        node = data["nodes"][node_id]
        tenant = data["tenants"][stream["tenant"]]
        klass = data["classes"][stream["class"]]
        if self.load[node_id] + 1 > node["capacity"]:
            return False
        if klass["priority_rank"] >= 2 and self.priority_load[node_id] + 1 > node["priority_lanes"]:
            return False
        if self.tokens[node_id] < self.units(node_id, stream):
            return False
        if not slo_ok(data["latency"][(node_id, tenant["region"])], klass["slo_max_hops"]):
            return False
        if self.tenant_load[stream["tenant"]] + 1 > tenant["ceiling"]:
            return False
        return True

    def place(self, node_id, stream):
        self.load[node_id] += 1
        if self.data["classes"][stream["class"]]["priority_rank"] >= 2:
            self.priority_load[node_id] += 1
        self.tokens[node_id] -= self.units(node_id, stream)
        self.tenant_load[stream["tenant"]] += 1
        self.assignment[stream["stream_id"]] = node_id
        self.on_node[node_id].append(stream["stream_id"])

    def evict(self, stream):
        node_id = self.assignment.pop(stream["stream_id"])
        self.load[node_id] -= 1
        if self.data["classes"][stream["class"]]["priority_rank"] >= 2:
            self.priority_load[node_id] -= 1
        self.tokens[node_id] += self.units(node_id, stream)
        self.tenant_load[stream["tenant"]] -= 1
        self.on_node[node_id].remove(stream["stream_id"])
        return node_id


def candidate_nodes(data, stream, previous):
    region = data["tenants"][stream["tenant"]]["region"]
    sticky = previous.get(stream["stream_id"])
    return sorted(
        data["node_ids"],
        key=lambda n: (0 if n == sticky else 1, data["latency"][(n, region)], n),
    )


def run_epoch(data, epoch, active_ids, tokens_start, previous):
    """Phases 4-7 for one epoch."""
    tenants = data["tenants"]
    streams = data["streams"]
    classes = data["classes"]

    demand = {t: 0 for t in data["tenant_ids"]}
    for stream_id in active_ids:
        demand[streams[stream_id]["tenant"]] += 1

    total_cap = sum(data["nodes"][n]["capacity"] for n in data["node_ids"])

    first_stream = {}
    for stream_id in active_ids:
        tenant = streams[stream_id]["tenant"]
        if tenant not in first_stream:
            first_stream[tenant] = stream_id

    if TIE_BREAK == "by_stream_id_asc":
        def tie_key(tenant):
            return first_stream.get(tenant, "~")
    else:
        def tie_key(tenant):
            return tenant

    quota = apportion(demand, tenants, total_cap, tie_key)

    admitted = []
    for tenant in data["tenant_ids"]:
        ranked = sorted(
            (s for s in active_ids if streams[s]["tenant"] == tenant),
            key=lambda s: (-classes[streams[s]["class"]]["priority_rank"], s),
        )
        admitted.extend(ranked[: quota[tenant]])

    admitted.sort(
        key=lambda s: (
            -classes[streams[s]["class"]]["priority_rank"],
            streams[s]["tenant"],
            s,
        )
    )

    state = EpochState(data, tokens_start)
    events = []
    for stream_id in admitted:
        stream = streams[stream_id]
        placed = False
        for node_id in candidate_nodes(data, stream, previous):
            if state.feasible(node_id, stream):
                state.place(node_id, stream)
                placed = True
                break
        if placed:
            continue

        victim_id, victim_node = cascade_victim(data, state, stream, previous)
        if victim_id is None:
            events.append(
                {
                    "epoch": epoch,
                    "victim": stream_id,
                    "class": stream["class"],
                    "beneficiary": None,
                    "reason": "no_feasible_node",
                }
            )
            continue
        state.evict(streams[victim_id])
        state.place(victim_node, stream)
        events.append(
            {
                "epoch": epoch,
                "victim": victim_id,
                "class": streams[victim_id]["class"],
                "beneficiary": stream_id,
                "reason": "cascade_evicted",
            }
        )

    return {
        "demand": demand,
        "quota": quota,
        "admitted": admitted,
        "assignment": state.assignment,
        "state": state,
        "events": events,
    }


def cascade_victim(data, state, stream, previous):
    """Phase 6b - pick the single eviction that frees a slot for `stream`."""
    streams = data["streams"]
    best = None
    for node_id in candidate_nodes(data, stream, previous):
        for victim_id in sorted(state.on_node[node_id]):
            victim = streams[victim_id]
            if (stream["class"], victim["class"]) not in data["ladder"]:
                continue
            state.evict(victim)
            ok = state.feasible(node_id, stream)
            state.place(node_id, victim)
            if not ok:
                continue
            region = data["tenants"][victim["tenant"]]["region"]
            cost = data["latency"][(node_id, region)] * victim["rate"]
            key = (-cost, victim_id)
            if best is None or key < best[0]:
                best = (key, victim_id, node_id)
    if best is None:
        return None, None
    return best[1], best[2]


def run_schedule(data):
    """One full pass over every epoch (one fixed-point iteration)."""
    nodes = data["nodes"]
    streams = data["streams"]
    tenants = data["tenants"]

    tokens = {n: nodes[n]["bucket_capacity"] + nodes[n]["refill_offset"] for n in data["node_ids"]}
    previous = dict(data["epochs"][0]["warm_start"])
    epochs_out = []

    for window in data["epochs"]:
        epoch = window["epoch"]
        active_ids = [
            s for s in data["stream_ids"]
            if streams[s]["arrival"] <= epoch <= streams[s]["deadline"]
        ]
        tokens_start = dict(tokens)
        result = run_epoch(data, epoch, active_ids, tokens_start, previous)
        state = result["state"]

        latency_cost = 0
        migrations = []
        for stream_id in sorted(state.assignment):
            stream = streams[stream_id]
            node_id = state.assignment[stream_id]
            region = tenants[stream["tenant"]]["region"]
            latency_cost += data["latency"][(node_id, region)] * stream["rate"]
            origin = previous.get(stream_id)
            if origin is not None and origin != node_id:
                cost = (
                    data["migration_base"][(stream["tenant"], epoch)]
                    * tenants[stream["tenant"]]["migration_mult"]
                )
                migrations.append(
                    {
                        "epoch": epoch,
                        "stream": stream_id,
                        "from": origin,
                        "to": node_id,
                        "cost": cost,
                    }
                )

        admitted_count = {t: 0 for t in data["tenant_ids"]}
        for stream_id in state.assignment:
            admitted_count[streams[stream_id]["tenant"]] += 1
        fairness = {}
        for tenant in data["tenant_ids"]:
            target = min(result["demand"][tenant], tenants[tenant]["ceiling"])
            fairness[tenant] = {
                "admitted": admitted_count[tenant],
                "target": target,
                "deviation": abs(admitted_count[tenant] - target),
            }

        utilization = {}
        tokens_next = {}
        for node_id in data["node_ids"]:
            node = nodes[node_id]
            consumed = sum(1 for _s in state.assignment if state.assignment[_s] == node_id)
            available = min(node["bucket_capacity"], tokens_start[node_id] - consumed)
            refill = round_ratio(
                node["refill_num"] * window["duration_num"],
                node["refill_den"] * window["duration_den"],
            )
            tokens_next[node_id] = min(node["bucket_capacity"], available + refill)
            utilization[node_id] = {
                "epoch": epoch,
                "used": state.load[node_id],
                "capacity": node["capacity"],
                "priority_used": state.priority_load[node_id],
                "priority_capacity": node["priority_lanes"],
                "bucket_tokens_start": tokens_start[node_id],
                "bucket_tokens_end": available,
            }

        epochs_out.append(
            {
                "epoch": epoch,
                "assignments": dict(state.assignment),
                "preempted": sorted(event["victim"] for event in result["events"]),
                "events": result["events"],
                "migrations": migrations,
                "latency_cost": latency_cost,
                "migration_cost": sum(item["cost"] for item in migrations),
                "fairness": fairness,
                "utilization": utilization,
                "admitted_count": admitted_count,
            }
        )

        tokens = tokens_next
        previous = dict(state.assignment)

    return epochs_out


def fixed_point(data):
    """Phase 9 - damped fixed-point loop over the whole horizon."""
    constants = data["constants"]
    previous_admissions = {}
    trace = []
    schedule = None
    converged = False
    iteration = 0
    for iteration in range(constants["max_iterations"]):
        schedule = run_schedule(data)
        admissions = {}
        for epoch_out in schedule:
            for tenant, count in epoch_out["admitted_count"].items():
                admissions[(tenant, epoch_out["epoch"])] = count
        keys = set(admissions) | set(previous_admissions)
        delta = sum(
            abs(admissions.get(key, 0) - previous_admissions.get(key, 0)) for key in keys
        )
        trace.append(
            {
                "iteration": iteration,
                "delta": delta,
                "admitted_total": sum(admissions.values()),
            }
        )
        previous_admissions = admissions
        if delta <= constants["tolerance"]:
            converged = True
            break
    return schedule, {
        "converged": converged,
        "final_iteration": iteration,
        "iterations": trace,
    }


def build_artifacts(data, schedule, trace):
    constants = data["constants"]
    nodes = data["nodes"]
    streams = data["streams"]
    tenants = data["tenants"]

    schedule_matrix = {
        "epochs": [
            {
                "epoch": epoch_out["epoch"],
                "assignments": epoch_out["assignments"],
                "preempted": epoch_out["preempted"],
            }
            for epoch_out in schedule
        ]
    }

    fleet_utilization = {
        "nodes": [
            {
                "node": node_id,
                "utilization_by_epoch": [epoch_out["utilization"][node_id] for epoch_out in schedule],
            }
            for node_id in data["node_ids"]
        ]
    }

    tenant_fairness = {
        "tenants": [
            {
                "tenant": tenant_id,
                "floor": tenants[tenant_id]["floor"],
                "ceiling": tenants[tenant_id]["ceiling"],
                "epochs": [
                    {
                        "epoch": epoch_out["epoch"],
                        "admitted": epoch_out["fairness"][tenant_id]["admitted"],
                        "target": epoch_out["fairness"][tenant_id]["target"],
                        "deviation": epoch_out["fairness"][tenant_id]["deviation"],
                    }
                    for epoch_out in schedule
                ],
            }
            for tenant_id in data["tenant_ids"]
        ]
    }

    migration_events = []
    for epoch_out in schedule:
        migration_events.extend(epoch_out["migrations"])
    migration_events.sort(key=lambda item: (item["epoch"], item["stream"]))
    migration_ledger = {
        "events": migration_events,
        "total_cost": sum(item["cost"] for item in migration_events),
    }

    preemption_list = []
    for epoch_out in schedule:
        preemption_list.extend(epoch_out["events"])
    preemption_list.sort(key=lambda item: (item["epoch"], item["victim"]))
    preemption_events = {"events": preemption_list, "total_count": len(preemption_list)}

    placed_by_class = {class_id: 0 for class_id in data["class_ids"]}
    breaches_by_class = {class_id: 0 for class_id in data["class_ids"]}
    for epoch_out in schedule:
        for stream_id, node_id in epoch_out["assignments"].items():
            stream = streams[stream_id]
            placed_by_class[stream["class"]] += 1
            region = tenants[stream["tenant"]]["region"]
            hops = data["latency"][(node_id, region)]
            if not slo_ok(hops, data["classes"][stream["class"]]["slo_max_hops"]):
                breaches_by_class[stream["class"]] += 1
    sla_violation = {
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

    latency_cost = sum(epoch_out["latency_cost"] for epoch_out in schedule)
    migration_cost = sum(epoch_out["migration_cost"] for epoch_out in schedule)
    fairness_deviation = sum(
        epoch_out["fairness"][tenant_id]["deviation"]
        for epoch_out in schedule
        for tenant_id in data["tenant_ids"]
    )
    total_cost = (
        constants["alpha"] * latency_cost
        + constants["beta"] * migration_cost
        + constants["gamma"] * fairness_deviation
    )
    objective = {
        "alpha": constants["alpha"],
        "beta": constants["beta"],
        "gamma": constants["gamma"],
        "fairness_deviation": fairness_deviation,
        "latency_cost": latency_cost,
        "migration_cost": migration_cost,
        "total_cost": total_cost,
    }

    return (
        {
            "schedule_matrix.json": schedule_matrix,
            "fleet_utilization.json": fleet_utilization,
            "tenant_fairness_report.json": tenant_fairness,
            "migration_ledger.json": migration_ledger,
            "preemption_events.json": preemption_events,
            "sla_violation_report.json": sla_violation,
            "objective_breakdown.json": objective,
            "fixed_point_trace.json": trace,
        },
        total_cost,
    )


def canonical(payload):
    return json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"


def write_artifacts(out_dir, payloads, data, total_cost):
    digests = {}
    for name in ARTIFACTS:
        blob = canonical(payloads[name]).encode("utf-8")
        with open(os.path.join(out_dir, name), "wb") as handle:
            handle.write(blob)
        digests[name] = hashlib.sha256(blob).hexdigest()

    manifest = {"artifact_names": sorted(digests), "artifact_sha256": digests}
    with open(os.path.join(out_dir, "integrity_manifest.json"), "wb") as handle:
        handle.write(canonical(manifest).encode("utf-8"))

    folded = hashlib.sha256(
        json.dumps(digests, sort_keys=True).encode("utf-8")
    ).hexdigest()
    final_state = {
        "artifact_count": 10,
        "epoch_count": len(data["epochs"]),
        "folded_digest_sha256": folded,
        "stream_count": len(data["stream_ids"]),
        "total_cost": total_cost,
    }
    with open(os.path.join(out_dir, "final_state.json"), "wb") as handle:
        handle.write(canonical(final_state).encode("utf-8"))


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: reusable_scheduler.py <data_dir> <out_dir>\n")
        return 2
    data_dir, out_dir = argv[1], argv[2]
    os.makedirs(out_dir, exist_ok=True)
    data = load_inputs(data_dir)
    schedule, trace = fixed_point(data)
    payloads, total_cost = build_artifacts(data, schedule, trace)
    write_artifacts(out_dir, payloads, data, total_cost)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
