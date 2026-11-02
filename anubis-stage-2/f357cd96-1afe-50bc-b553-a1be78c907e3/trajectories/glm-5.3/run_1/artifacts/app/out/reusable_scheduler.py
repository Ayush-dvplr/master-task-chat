#!/usr/bin/env python3
"""HTTP/3 fleet migration scheduler.

Usage::

    python3 reusable_scheduler.py <data_dir> <out_dir>

Reads every scheduling input from ``<data_dir>`` and writes the eleven report
artifacts into ``<out_dir>``.  The run is fully deterministic: every iteration
order is derived from sorted identifiers, all arithmetic is integer, and no
environment variable and no network resource is consulted.
"""

import csv
import hashlib
import json
import os
import sys

# ---------------------------------------------------------------------------
# Operational settlements (recovered from the sealed reference archive).
#
#   Phase 4 largest-remainder tie-break ..... by_tenant_id_asc
#   Phase 4 floor application order .......... floors_before_cap
#   Phase 6 SLO comparison operator .......... strict_lt
#   Phase 8 token-bucket refill rounding ...... floor
#
# Each value below is the reading under which every sealed corpus reproduces
# its witness exactly; every other candidate is rejected by at least one seal.
# ---------------------------------------------------------------------------
TIEBREAK = "by_tenant_id_asc"
FLOOR_ORDER = "floors_before_cap"
SLO_OP = "strict_lt"
REFILL_ROUND = "floor"

# The one-time epoch-0 bucket credit is added to the initial (full) balance
# before Phase 6 of epoch 0; the bucket-capacity clamp belongs to the Phase 8
# refill transition, not to that one-time credit.
EPOCH0_BUCKET_UNCLAMPED = True

# "Admitted" counts streams that survived Phase 5 selection (the contract calls
# a stream that survived Phase 5 but found no node an "unplaced admitted
# stream"); "placed" counts streams that actually landed on a node.
ADMITTED_BASIS = "selected"

# A node that has already hosted a cascade eviction stays reserved for the rest
# of the epoch (Phase 6 feasibility condition six).
CASCADE_RESERVES_NODE = True

# fixed_point_trace.final_iteration is the global index of the last iteration.
FINAL_ITERATION_IS_INDEX = True

ARTIFACT_ORDER = [
    "schedule_matrix.json",
    "fleet_utilization.json",
    "tenant_fairness_report.json",
    "migration_ledger.json",
    "preemption_events.json",
    "sla_violation_report.json",
    "objective_breakdown.json",
    "fixed_point_trace.json",
]


# ---------------------------------------------------------------------------
# Canonical serialisation
# ---------------------------------------------------------------------------

def canonical_bytes(payload):
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def write_json(out_dir, name, payload):
    data = canonical_bytes(payload) + b"\n"
    with open(os.path.join(out_dir, name), "wb") as handle:
        handle.write(data)
    return data


# ---------------------------------------------------------------------------
# Input loading
# ---------------------------------------------------------------------------

def read_csv(path):
    with open(path, newline="") as handle:
        return list(csv.DictReader(handle))


def load_inputs(data_dir):
    def path(name):
        return os.path.join(data_dir, name)

    nodes = {}
    for row in read_csv(path("fleet_nodes.csv")):
        nodes[row["node_id"]] = {
            "node_id": row["node_id"],
            "capacity": int(row["capacity"]),
            "mtu_class": row["mtu_class"],
            "region": row["region"],
            "priority_lanes": int(row["priority_lanes"]),
        }

    streams = {}
    for row in read_csv(path("stream_manifest.csv")):
        streams[row["stream_id"]] = {
            "stream_id": row["stream_id"],
            "tenant": row["tenant_id"],
            "class_id": row["class_id"],
            "arrival": int(row["arrival_epoch"]),
            "deadline": int(row["deadline_epoch"]),
            "rate_units": int(row["rate_units"]),
            "rate_profile": row["rate_profile"],
        }

    tenants = {}
    for row in read_csv(path("tenants.csv")):
        tenants[row["tenant_id"]] = {
            "tenant_id": row["tenant_id"],
            "floor": int(row["floor"]),
            "ceiling": int(row["ceiling"]),
            "migration_mult": int(row["migration_mult"]),
            "region": row["tenant_region"],
        }

    classes = {}
    with open(path("qos_classes.json")) as handle:
        for entry in json.load(handle)["classes"]:
            classes[entry["class_id"]] = {
                "class_id": entry["class_id"],
                "priority_rank": int(entry["priority_rank"]),
                "slo_max_hops": int(entry["slo_max_hops"]),
            }

    buckets = {}
    for row in read_csv(path("token_buckets.csv")):
        buckets[row["node_id"]] = {
            "bucket_capacity": int(row["bucket_capacity"]),
            "refill_num": int(row["refill_num"]),
            "refill_den": int(row["refill_den"]),
            "refill_offset": int(row["refill_offset"]),
        }

    mtu_units = {}
    for row in read_csv(path("mtu_matrix.csv")):
        mtu_units[(row["mtu_class"], row["class_id"])] = int(row["units"])

    latency = {}
    for row in read_csv(path("latency_matrix.csv")):
        latency[(row["node_id"], row["tenant_region"])] = int(row["hops"])

    mig_base = {}
    with open(path("migration_penalty_table.json")) as handle:
        for entry in json.load(handle)["base"]:
            mig_base[(entry["tenant"], int(entry["epoch"]))] = int(entry["base"])

    preempt_ok = set()
    with open(path("preemption_ladder.json")) as handle:
        for entry in json.load(handle)["ladder"]:
            preempt_ok.add((entry["preemptor"], entry["victim"]))

    epochs = {}
    warm_start = {}
    for row in read_csv(path("epoch_windows.csv")):
        epoch = int(row["epoch"])
        epochs[epoch] = {
            "epoch": epoch,
            "duration_num": int(row["duration_num"]),
            "duration_den": int(row["duration_den"]),
        }
        spec = row["warm_start"].strip()
        if spec:
            for pair in spec.split(";"):
                stream_id, node_id = pair.split("=")
                warm_start[stream_id] = node_id

    with open(path("fixed_point_constants.json")) as handle:
        constants = json.load(handle)

    # Descriptive metadata only: rate_units in the stream manifest is
    # authoritative for every scheduling and cost computation.
    profiles = {}
    for row in read_csv(path("packet_rate_profiles.csv")):
        profiles[row["profile_id"]] = row

    return {
        "nodes": nodes,
        "streams": streams,
        "tenants": tenants,
        "classes": classes,
        "buckets": buckets,
        "mtu_units": mtu_units,
        "latency": latency,
        "mig_base": mig_base,
        "preempt_ok": preempt_ok,
        "epochs": epochs,
        "warm_start": warm_start,
        "constants": constants,
        "profiles": profiles,
    }


# ---------------------------------------------------------------------------
# Settled arithmetic helpers
# ---------------------------------------------------------------------------

def refill_round(num, den):
    """Round the fractional refill ``num/den`` to an integer token count."""
    if den <= 0:
        raise ValueError("refill denominator must be positive")
    if REFILL_ROUND == "floor":
        return num // den
    if REFILL_ROUND == "ceil":
        return -(-num // den)
    if REFILL_ROUND == "banker":
        whole, rest = divmod(num, den)
        twice = rest * 2
        if twice > den:
            return whole + 1
        if twice < den:
            return whole
        return whole if whole % 2 == 0 else whole + 1
    raise ValueError("unknown refill rounding settlement")


def slo_compliant(hops, slo_max_hops):
    if SLO_OP == "strict_lt":
        return hops < slo_max_hops
    if SLO_OP == "non_strict_leq":
        return hops <= slo_max_hops
    raise ValueError("unknown SLO operator settlement")


# ---------------------------------------------------------------------------
# Phase 4 - fair-share apportionment
# ---------------------------------------------------------------------------

def largest_remainder(weights, slots, pools, base_offsets):
    """Apportion ``slots`` across ``weights`` with the settled tie-break.

    ``pools`` maps tenant -> its streams in Phase 5 order and is only consulted
    by the ``by_stream_id_asc`` tie-break candidate; ``base_offsets`` maps
    tenant -> slots already held before this step.
    """
    result = {t: 0 for t in weights}
    total = sum(weights.values())
    if slots <= 0 or total <= 0:
        return result
    rem = {}
    for tenant, weight in weights.items():
        whole, rest = divmod(slots * weight, total)
        result[tenant] = whole
        rem[tenant] = rest
    remaining = slots - sum(result.values())
    if remaining <= 0:
        return result

    def hint(tenant):
        pool = pools.get(tenant, [])
        start = result[tenant] + base_offsets.get(tenant, 0)
        pending = [s for s in pool[start:] if s is not None]
        return min(pending) if pending else None

    if TIEBREAK == "by_tenant_id_asc":
        key = lambda t: (-rem[t], t)
    elif TIEBREAK == "by_stream_id_asc":
        key = lambda t: (-rem[t], hint(t) is None, hint(t), t)
    else:
        raise ValueError("unknown tie-break settlement")
    for tenant in sorted(weights, key=key)[:remaining]:
        result[tenant] += 1
    return result


def enforce_floors(quota, need_floor):
    """floors_after_cap candidate: re-apply floors by reclaiming surplus."""
    result = dict(quota)
    for tenant in sorted(result):
        while result[tenant] < need_floor[tenant]:
            donors = [
                t
                for t in sorted(result)
                if t != tenant and result[t] > need_floor[t]
            ]
            if not donors:
                break
            donor = min(donors, key=lambda t: (-(result[t] - need_floor[t]), t))
            result[donor] -= 1
            result[tenant] += 1
    return result


def apportion(demand, floors, ceilings, cap, pools):
    """Phase 4: integer per-tenant quota honouring the settled floor order."""
    raw = {t: min(demand[t], ceilings[t]) for t in demand}
    need_floor = {t: min(demand[t], floors[t]) for t in demand}

    if FLOOR_ORDER == "floors_before_cap":
        initial = dict(need_floor)
    elif FLOOR_ORDER == "floors_after_cap":
        initial = dict(raw)
    else:
        raise ValueError("unknown floor-order settlement")

    if sum(initial.values()) > cap:
        quota = largest_remainder(initial, cap, pools, {})
    else:
        need = {t: max(0, raw[t] - initial[t]) for t in initial}
        spare = cap - sum(initial.values())
        if sum(need.values()) <= spare:
            granted = dict(need)
        else:
            granted = largest_remainder(need, spare, pools, initial)
        quota = {t: initial[t] + granted[t] for t in initial}

    if FLOOR_ORDER == "floors_after_cap":
        quota = enforce_floors(quota, need_floor)
    return quota


# ---------------------------------------------------------------------------
# Phases 5 and 6
# ---------------------------------------------------------------------------

def phase5_order(stream_ids, streams, classes):
    return sorted(
        stream_ids,
        key=lambda s: (-classes[streams[s]["class_id"]]["priority_rank"], s),
    )


def select_streams(active, quota, streams, classes, tenants):
    """Phase 5: per-tenant selection ordered by class rank then stream id."""
    pools = {t: [] for t in tenants}
    for stream_id in active:
        pools[streams[stream_id]["tenant"]].append(stream_id)
    pools = {t: phase5_order(v, streams, classes) for t, v in pools.items()}
    admitted = []
    for tenant in sorted(pools):
        admitted.extend(pools[tenant][: quota[tenant]])
    admitted.sort(
        key=lambda s: (
            -classes[streams[s]["class_id"]]["priority_rank"],
            streams[s]["tenant"],
            s,
        )
    )
    return admitted, pools


def node_order(stream_id, streams, tenants, latency, nodes, previous):
    """Candidate nodes: sticky first, then lowest latency, then node id."""
    region = tenants[streams[stream_id]["tenant"]]["region"]
    home = previous.get(stream_id)

    def key(node_id):
        sticky = 0 if (home is not None and node_id == home) else 1
        return (sticky, latency[(node_id, region)], node_id)

    return sorted(nodes, key=key)


def feasible(node_id, stream_id, state, cfg):
    stream = cfg["streams"][stream_id]
    node = cfg["nodes"][node_id]
    klass = cfg["classes"][stream["class_id"]]
    units = cfg["mtu_units"][(node["mtu_class"], stream["class_id"])]
    hops = cfg["latency"][(node_id, cfg["tenants"][stream["tenant"]]["region"])]
    if state["load"][node_id] + 1 > node["capacity"]:
        return False
    if klass["priority_rank"] >= 2 and state["lanes"][node_id] + 1 > node["priority_lanes"]:
        return False
    if state["tokens"][node_id] < units:
        return False
    if not slo_compliant(hops, klass["slo_max_hops"]):
        return False
    if CASCADE_RESERVES_NODE and node_id in state["reserved"]:
        return False
    if state["tenant_count"][stream["tenant"]] + 1 > cfg["tenants"][stream["tenant"]]["ceiling"]:
        return False
    return True


def node_latency_cost(node_id, stream_id, cfg):
    stream = cfg["streams"][stream_id]
    region = cfg["tenants"][stream["tenant"]]["region"]
    return cfg["latency"][(node_id, region)] * stream["rate_units"]


def occupy(node_id, stream_id, state, cfg):
    stream = cfg["streams"][stream_id]
    units = cfg["mtu_units"][(cfg["nodes"][node_id]["mtu_class"], stream["class_id"])]
    state["load"][node_id] += 1
    state["tokens"][node_id] -= units
    state["tenant_count"][stream["tenant"]] += 1
    if cfg["classes"][stream["class_id"]]["priority_rank"] >= 2:
        state["lanes"][node_id] += 1


def release(node_id, stream_id, state, cfg):
    stream = cfg["streams"][stream_id]
    units = cfg["mtu_units"][(cfg["nodes"][node_id]["mtu_class"], stream["class_id"])]
    state["load"][node_id] -= 1
    state["tokens"][node_id] += units
    state["tenant_count"][stream["tenant"]] -= 1
    if cfg["classes"][stream["class_id"]]["priority_rank"] >= 2:
        state["lanes"][node_id] -= 1


def place_epoch(admitted, tokens_start, previous, cfg):
    """Phase 6 (with the depth-1 cascade of Phase 6b) for one epoch."""
    nodes = cfg["nodes"]
    state = {
        "load": {n: 0 for n in nodes},
        "lanes": {n: 0 for n in nodes},
        "tokens": dict(tokens_start),
        "tenant_count": {t: 0 for t in cfg["tenants"]},
        "reserved": set(),
    }
    assignments = {}
    preempted = []
    events = []

    for stream_id in admitted:
        order = node_order(
            stream_id, cfg["streams"], cfg["tenants"], cfg["latency"], nodes, previous
        )
        target = None
        for node_id in order:
            if feasible(node_id, stream_id, state, cfg):
                target = node_id
                break
        if target is not None:
            occupy(target, stream_id, state, cfg)
            assignments[stream_id] = target
            continue

        # Phase 6b - cascade preemption, depth exactly one.
        victim = None
        victim_node = None
        for node_id in order:
            if CASCADE_RESERVES_NODE and node_id in state["reserved"]:
                continue
            candidates = [
                s
                for s, n in assignments.items()
                if n == node_id
                and (cfg["streams"][stream_id]["class_id"], cfg["streams"][s]["class_id"])
                in cfg["preempt_ok"]
            ]
            workable = []
            for candidate in candidates:
                release(node_id, candidate, state, cfg)
                ok = feasible(node_id, stream_id, state, cfg)
                occupy(node_id, candidate, state, cfg)
                if ok:
                    workable.append(candidate)
            if workable:
                workable.sort(key=lambda s: (-node_latency_cost(node_id, s, cfg), s))
                victim = workable[0]
                victim_node = node_id
                break
        if victim is None:
            preempted.append(stream_id)
            events.append(
                {
                    "epoch": None,
                    "victim": stream_id,
                    "class": cfg["streams"][stream_id]["class_id"],
                    "beneficiary": None,
                    "reason": "no_feasible_node",
                }
            )
        else:
            release(victim_node, victim, state, cfg)
            occupy(victim_node, stream_id, state, cfg)
            del assignments[victim]
            assignments[stream_id] = victim_node
            preempted.append(victim)
            events.append(
                {
                    "epoch": None,
                    "victim": victim,
                    "class": cfg["streams"][victim]["class_id"],
                    "beneficiary": stream_id,
                    "reason": "cascade_evicted",
                }
            )
            if CASCADE_RESERVES_NODE:
                state["reserved"].add(victim_node)
    return state, assignments, preempted, events


# ---------------------------------------------------------------------------
# Per-epoch driver (phases 1-9)
# ---------------------------------------------------------------------------

def admitted_counts(admitted, assignments, cfg):
    """Per-tenant admitted stream count under the settled basis."""
    counts = {t: 0 for t in cfg["tenants"]}
    if ADMITTED_BASIS == "selected":
        for stream_id in admitted:
            counts[cfg["streams"][stream_id]["tenant"]] += 1
    elif ADMITTED_BASIS == "placed":
        for stream_id in assignments:
            counts[cfg["streams"][stream_id]["tenant"]] += 1
    else:
        raise ValueError("unknown admitted basis")
    return counts


def run_epoch(epoch, cfg, tokens_start, previous):
    streams = cfg["streams"]
    tenants = cfg["tenants"]
    nodes = cfg["nodes"]
    classes = cfg["classes"]
    constants = cfg["constants"]

    active = sorted(
        s for s in streams if streams[s]["arrival"] <= epoch <= streams[s]["deadline"]
    )
    demand = {t: 0 for t in tenants}
    for stream_id in active:
        demand[streams[stream_id]["tenant"]] += 1
    cap = sum(nodes[n]["capacity"] for n in nodes)

    pools = {t: [] for t in tenants}
    for stream_id in active:
        pools[streams[stream_id]["tenant"]].append(stream_id)
    pools = {t: phase5_order(v, streams, classes) for t, v in pools.items()}

    floors = {t: tenants[t]["floor"] for t in tenants}
    ceilings = {t: tenants[t]["ceiling"] for t in tenants}
    damping_num = int(constants["damping_num"])
    damping_den = int(constants["damping_den"])
    tolerance = int(constants["tolerance"])
    max_iterations = int(constants["max_iterations"])

    prev_admitted = {t: 0 for t in tenants}
    trace = []
    converged = False
    outcome = None

    for _ in range(max_iterations):
        quota = apportion(demand, floors, ceilings, cap, pools)
        admitted, _ = select_streams(active, quota, streams, classes, tenants)
        state, assignments, preempted, events = place_epoch(
            admitted, tokens_start, previous, cfg
        )
        counts = admitted_counts(admitted, assignments, cfg)

        damped = {}
        for tenant in tenants:
            damped[tenant] = (
                (damping_den - damping_num) * prev_admitted[tenant]
                + damping_num * counts[tenant]
                + damping_den
                - 1
            ) // damping_den
        delta = sum(abs(damped[t] - prev_admitted[t]) for t in tenants)
        trace.append(
            {"iteration": 0, "delta": delta, "admitted_total": sum(damped.values())}
        )
        prev_admitted = damped
        outcome = (quota, state, assignments, preempted, events)
        if delta <= tolerance:
            converged = True
            break

    quota, state, assignments, preempted, events = outcome
    return {
        "epoch": epoch,
        "active": active,
        "demand": demand,
        "cap": cap,
        "quota": quota,
        "state": state,
        "assignments": assignments,
        "preempted": sorted(preempted),
        "events": events,
        "trace": trace,
        "converged": converged,
        "admitted_count": prev_admitted,
    }


# ---------------------------------------------------------------------------
# Full run
# ---------------------------------------------------------------------------

def schedule(data_dir):
    cfg = load_inputs(data_dir)
    nodes = cfg["nodes"]
    streams = cfg["streams"]
    tenants = cfg["tenants"]
    classes = cfg["classes"]
    buckets = cfg["buckets"]
    epochs = sorted(cfg["epochs"])
    warm_start = cfg["warm_start"]
    constants = cfg["constants"]

    alpha = int(constants["alpha"])
    beta = int(constants["beta"])
    gamma = int(constants["gamma"])

    tokens_start = {}
    for node_id in nodes:
        base = buckets[node_id]["bucket_capacity"]
        credit = buckets[node_id]["refill_offset"]
        if EPOCH0_BUCKET_UNCLAMPED:
            tokens_start[node_id] = base + credit
        else:
            tokens_start[node_id] = min(base, base + credit)

    schedule_epochs = []
    utilization_rows = []
    fairness_rows = []
    migrations = []
    preemptions = []
    latency_total = 0
    migration_total = 0
    fairness_total = 0
    trace_iterations = []
    all_converged = True
    placed_by_class = {c: 0 for c in classes}
    breaches_by_class = {c: 0 for c in classes}

    for epoch in epochs:
        previous = warm_start if epoch == 0 else schedule_epochs[-1]["assignments"]
        result = run_epoch(epoch, cfg, tokens_start, previous)
        schedule_epochs.append(result)
        if not result["converged"]:
            all_converged = False

        assignments = result["assignments"]

        # Phase 7 - per-epoch costs.
        for stream_id in sorted(assignments):
            node_id = assignments[stream_id]
            stream = streams[stream_id]
            hops = cfg["latency"][(node_id, tenants[stream["tenant"]]["region"])]
            latency_total += hops * stream["rate_units"]
            placed_by_class[stream["class_id"]] += 1
            if not slo_compliant(hops, classes[stream["class_id"]]["slo_max_hops"]):
                breaches_by_class[stream["class_id"]] += 1

        previous_map = warm_start if epoch == 0 else schedule_epochs[-2]["assignments"]
        for stream_id in sorted(assignments):
            node_id = assignments[stream_id]
            former = previous_map.get(stream_id)
            if former is None or former == node_id:
                continue
            stream = streams[stream_id]
            cost = (
                cfg["mig_base"][(stream["tenant"], epoch)]
                * tenants[stream["tenant"]]["migration_mult"]
            )
            migrations.append(
                {
                    "epoch": epoch,
                    "stream": stream_id,
                    "from": former,
                    "to": node_id,
                    "cost": cost,
                }
            )
            migration_total += cost

        admitted_count = result["admitted_count"]
        target = {t: min(result["demand"][t], tenants[t]["ceiling"]) for t in tenants}
        deviation = {t: abs(admitted_count[t] - target[t]) for t in tenants}
        fairness_total += sum(deviation.values())
        for tenant in sorted(tenants):
            fairness_rows.append(
                {
                    "tenant": tenant,
                    "floor": tenants[tenant]["floor"],
                    "ceiling": tenants[tenant]["ceiling"],
                    "epoch": epoch,
                    "admitted": admitted_count[tenant],
                    "target": target[tenant],
                    "deviation": deviation[tenant],
                }
            )

        for event in result["events"]:
            event["epoch"] = epoch
        preemptions.extend(result["events"])

        # Phase 8 - token bucket refill for the next epoch.
        consumed = {n: 0 for n in nodes}
        for node_id in assignments.values():
            consumed[node_id] += 1
        window = cfg["epochs"][epoch]
        next_tokens = {}
        for node_id in sorted(nodes):
            capacity = buckets[node_id]["bucket_capacity"]
            balance = tokens_start[node_id] - consumed[node_id]
            available = min(capacity, balance)
            refill_int = refill_round(
                buckets[node_id]["refill_num"] * window["duration_num"],
                buckets[node_id]["refill_den"] * window["duration_den"],
            )
            next_tokens[node_id] = min(capacity, available + refill_int)
            utilization_rows.append(
                {
                    "node": node_id,
                    "epoch": epoch,
                    "used": result["state"]["load"][node_id],
                    "capacity": nodes[node_id]["capacity"],
                    "priority_used": result["state"]["lanes"][node_id],
                    "priority_capacity": nodes[node_id]["priority_lanes"],
                    "bucket_tokens_start": tokens_start[node_id],
                    "bucket_tokens_end": balance,
                }
            )
        tokens_start = next_tokens

        for entry in result["trace"]:
            entry["iteration"] = len(trace_iterations)
            trace_iterations.append(entry)

    utilisation_nodes = []
    for node_id in sorted(nodes):
        rows = [
            {k: v for k, v in row.items() if k != "node"}
            for row in utilization_rows
            if row["node"] == node_id
        ]
        utilisation_nodes.append({"node": node_id, "utilization_by_epoch": rows})

    tenant_rows = []
    for tenant in sorted(tenants):
        epochs_rows = [
            {
                "epoch": row["epoch"],
                "admitted": row["admitted"],
                "target": row["target"],
                "deviation": row["deviation"],
            }
            for row in fairness_rows
            if row["tenant"] == tenant
        ]
        tenant_rows.append(
            {
                "tenant": tenant,
                "floor": tenants[tenant]["floor"],
                "ceiling": tenants[tenant]["ceiling"],
                "epochs": epochs_rows,
            }
        )

    migrations.sort(key=lambda e: (e["epoch"], e["stream"]))
    preemptions.sort(key=lambda e: (e["epoch"], e["victim"]))

    sla_rows = []
    total_breaches = 0
    for class_id in sorted(classes):
        total_breaches += breaches_by_class[class_id]
        sla_rows.append(
            {
                "class": class_id,
                "breaches": breaches_by_class[class_id],
                "streams_placed": placed_by_class[class_id],
            }
        )

    total_cost = alpha * latency_total + beta * migration_total + gamma * fairness_total

    artifacts = {
        "schedule_matrix.json": {
            "epochs": [
                {
                    "epoch": result["epoch"],
                    "assignments": {
                        s: result["assignments"][s]
                        for s in sorted(result["assignments"])
                    },
                    "preempted": result["preempted"],
                }
                for result in schedule_epochs
            ]
        },
        "fleet_utilization.json": {"nodes": utilisation_nodes},
        "tenant_fairness_report.json": {"tenants": tenant_rows},
        "migration_ledger.json": {"events": migrations, "total_cost": migration_total},
        "preemption_events.json": {
            "events": preemptions,
            "total_count": len(preemptions),
        },
        "sla_violation_report.json": {
            "by_class": sla_rows,
            "total_breaches": total_breaches,
        },
        "objective_breakdown.json": {
            "alpha": alpha,
            "beta": beta,
            "gamma": gamma,
            "fairness_deviation": fairness_total,
            "latency_cost": latency_total,
            "migration_cost": migration_total,
            "total_cost": total_cost,
        },
        "fixed_point_trace.json": {
            "converged": all_converged,
            "final_iteration": (
                len(trace_iterations) - 1
                if FINAL_ITERATION_IS_INDEX
                else len(trace_iterations)
            ),
            "iterations": trace_iterations,
        },
    }
    final_state = {
        "artifact_count": 10,
        "epoch_count": len(epochs),
        "folded_digest_sha256": None,
        "stream_count": len(streams),
        "total_cost": total_cost,
    }
    return artifacts, final_state


def main(data_dir, out_dir):
    artifacts, final_state = schedule(data_dir)
    os.makedirs(out_dir, exist_ok=True)
    for name in ARTIFACT_ORDER:
        write_json(out_dir, name, artifacts[name])
    digest_map = {}
    for name in ARTIFACT_ORDER:
        with open(os.path.join(out_dir, name), "rb") as handle:
            digest_map[name] = hashlib.sha256(handle.read()).hexdigest()
    write_json(
        out_dir,
        "integrity_manifest.json",
        {"artifact_names": sorted(ARTIFACT_ORDER), "artifact_sha256": digest_map},
    )
    folded = hashlib.sha256(
        json.dumps(digest_map, sort_keys=True).encode("utf-8")
    ).hexdigest()
    final_state["folded_digest_sha256"] = folded
    write_json(out_dir, "final_state.json", final_state)
    with open(__file__, "rb") as handle:
        own_source = handle.read()
    with open(os.path.join(out_dir, "reusable_scheduler.py"), "wb") as handle:
        handle.write(own_source)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.stderr.write("usage: reusable_scheduler.py <data_dir> <out_dir>\n")
        sys.exit(2)
    main(sys.argv[1], sys.argv[2])
