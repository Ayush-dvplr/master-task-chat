#!/usr/bin/env python3
"""Reference scheduler for the HTTP/3 fleet migration scheduling task.

Reads a flat data directory produced under the README-input-schema.md contract
and emits ten canonical JSON artifacts plus copies itself as
`reusable_scheduler.py`. Every arithmetic operation is integer; no floats are
used and no external state (env, network, tests/) is consulted.

Settlements used by the reference (locked to the archive's original values):

    LARGEST_REMAINDER_TIE = "by_tenant_id_asc"
    FLOOR_APPLICATION_ORDER = "floors_before_cap"
    SLO_COMPARISON = "strict_lt"
    BUCKET_REFILL_ROUNDING = "floor"
"""

from __future__ import annotations

import csv
import hashlib
import json
import sys
from pathlib import Path

LARGEST_REMAINDER_TIE = "by_tenant_id_asc"
FLOOR_APPLICATION_ORDER = "floors_before_cap"
SLO_COMPARISON = "strict_lt"
BUCKET_REFILL_ROUNDING = "floor"

CANONICAL_ARTIFACT_ORDER = (
    "schedule_matrix.json",
    "fleet_utilization.json",
    "tenant_fairness_report.json",
    "migration_ledger.json",
    "preemption_events.json",
    "sla_violation_report.json",
    "objective_breakdown.json",
    "fixed_point_trace.json",
)


def _read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _canonical(obj) -> bytes:
    return (json.dumps(obj, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _round_frac(num: int, den: int, mode: str) -> int:
    if den <= 0:
        raise ValueError("denominator must be positive")
    if mode == "floor":
        return num // den
    if mode == "ceil":
        return -(-num // den)
    if mode == "banker":
        q, r = divmod(num, den)
        two_r = 2 * r
        if two_r < den:
            return q
        if two_r > den:
            return q + 1
        return q if q % 2 == 0 else q + 1
    raise ValueError(f"unknown rounding mode: {mode!r}")


class Instance:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.nodes = _read_csv(data_dir / "fleet_nodes.csv")
        self.streams = _read_csv(data_dir / "stream_manifest.csv")
        self.tenants = _read_csv(data_dir / "tenants.csv")
        self.classes = _read_json(data_dir / "qos_classes.json")["classes"]
        self.buckets = _read_csv(data_dir / "token_buckets.csv")
        self.mtu_rows = _read_csv(data_dir / "mtu_matrix.csv")
        self.migration_rows = _read_json(data_dir / "migration_penalty_table.json")["base"]
        self.latency_rows = _read_csv(data_dir / "latency_matrix.csv")
        self.ladder_rows = _read_json(data_dir / "preemption_ladder.json")["ladder"]
        self.epoch_rows = _read_csv(data_dir / "epoch_windows.csv")
        self.constants = _read_json(data_dir / "fixed_point_constants.json")
        self.profiles = _read_csv(data_dir / "packet_rate_profiles.csv")

        self.node_ids = sorted(row["node_id"] for row in self.nodes)
        self.node_by_id = {row["node_id"]: row for row in self.nodes}
        self.capacity = {r["node_id"]: int(r["capacity"]) for r in self.nodes}
        self.mtu_class = {r["node_id"]: r["mtu_class"] for r in self.nodes}
        self.node_region = {r["node_id"]: r["region"] for r in self.nodes}
        self.priority_lanes = {r["node_id"]: int(r["priority_lanes"]) for r in self.nodes}

        self.tenant_ids = sorted(row["tenant_id"] for row in self.tenants)
        self.tenant_by_id = {row["tenant_id"]: row for row in self.tenants}
        self.floor = {r["tenant_id"]: int(r["floor"]) for r in self.tenants}
        self.ceiling = {r["tenant_id"]: int(r["ceiling"]) for r in self.tenants}
        self.migration_mult = {r["tenant_id"]: int(r["migration_mult"]) for r in self.tenants}
        self.tenant_region = {r["tenant_id"]: r["tenant_region"] for r in self.tenants}

        self.class_by_id = {r["class_id"]: r for r in self.classes}
        self.class_priority = {r["class_id"]: int(r["priority_rank"]) for r in self.classes}
        self.class_slo_hops = {r["class_id"]: int(r["slo_max_hops"]) for r in self.classes}

        self.bucket_capacity = {r["node_id"]: int(r["bucket_capacity"]) for r in self.buckets}
        self.refill_num = {r["node_id"]: int(r["refill_num"]) for r in self.buckets}
        self.refill_den = {r["node_id"]: int(r["refill_den"]) for r in self.buckets}
        self.refill_offset = {r["node_id"]: int(r["refill_offset"]) for r in self.buckets}

        self.mtu_units = {}
        for r in self.mtu_rows:
            self.mtu_units[(r["mtu_class"], r["class_id"])] = int(r["units"])

        self.migration_base = {}
        for r in self.migration_rows:
            self.migration_base[(r["tenant"], int(r["epoch"]))] = int(r["base"])

        self.latency = {}
        for r in self.latency_rows:
            self.latency[(r["node_id"], r["tenant_region"])] = int(r["hops"])

        self.preempts = {c["class_id"]: set() for c in self.classes}
        for r in self.ladder_rows:
            self.preempts[r["preemptor"]].add(r["victim"])

        self.epochs = sorted((int(r["epoch"]) for r in self.epoch_rows))
        self.epoch_count = len(self.epochs)
        self.duration_num = {int(r["epoch"]): int(r["duration_num"]) for r in self.epoch_rows}
        self.duration_den = {int(r["epoch"]): int(r["duration_den"]) for r in self.epoch_rows}
        self.warm_start = {}
        for r in self.epoch_rows:
            if int(r["epoch"]) == 0 and r["warm_start"].strip():
                for pair in r["warm_start"].split(";"):
                    if "=" in pair:
                        sid, nid = pair.split("=", 1)
                        self.warm_start[sid.strip()] = nid.strip()

        self.stream_ids = sorted(row["stream_id"] for row in self.streams)
        self.stream_by_id = {row["stream_id"]: row for row in self.streams}
        self.stream_tenant = {r["stream_id"]: r["tenant_id"] for r in self.streams}
        self.stream_class = {r["stream_id"]: r["class_id"] for r in self.streams}
        self.stream_arrival = {r["stream_id"]: int(r["arrival_epoch"]) for r in self.streams}
        self.stream_deadline = {r["stream_id"]: int(r["deadline_epoch"]) for r in self.streams}
        self.stream_rate = {r["stream_id"]: int(r["rate_units"]) for r in self.streams}

        self.alpha = int(self.constants["alpha"])
        self.beta = int(self.constants["beta"])
        self.gamma = int(self.constants["gamma"])
        self.damping_num = int(self.constants["damping_num"])
        self.damping_den = int(self.constants["damping_den"])
        self.tolerance = int(self.constants["tolerance"])
        self.max_iterations = int(self.constants["max_iterations"])

    def active_streams(self, epoch: int) -> list[str]:
        return sorted(
            s
            for s in self.stream_ids
            if self.stream_arrival[s] <= epoch <= self.stream_deadline[s]
        )


def _apportion(inst: Instance, demand: dict, epoch: int, total_cap: int) -> dict:
    tenants = inst.tenant_ids

    def _tie_priority(t: str) -> tuple:
        if LARGEST_REMAINDER_TIE == "by_tenant_id_asc":
            return (t,)
        if LARGEST_REMAINDER_TIE == "by_stream_id_asc":
            streams = sorted(
                s
                for s in inst.stream_ids
                if inst.stream_tenant[s] == t
                and inst.stream_arrival[s] <= epoch <= inst.stream_deadline[s]
            )
            return (streams[0] if streams else "\uFFFF", t)
        raise ValueError(LARGEST_REMAINDER_TIE)

    if FLOOR_APPLICATION_ORDER == "floors_before_cap":
        floors_capped = {t: min(inst.floor[t], demand.get(t, 0)) for t in tenants}
        total_floors = sum(floors_capped.values())
        if total_floors >= total_cap:
            if total_floors == 0:
                return {t: 0 for t in tenants}
            base = {t: (floors_capped[t] * total_cap) // total_floors for t in tenants}
            remainder = {t: (floors_capped[t] * total_cap) - base[t] * total_floors for t in tenants}
            remaining = total_cap - sum(base.values())
            for t in sorted(tenants, key=lambda x: (-remainder[x], _tie_priority(x)))[:remaining]:
                base[t] += 1
            return base
        extras = {t: max(0, min(demand.get(t, 0), inst.ceiling[t]) - floors_capped[t]) for t in tenants}
        surplus_cap = total_cap - total_floors
        total_extras = sum(extras.values())
        if total_extras <= surplus_cap:
            return {t: floors_capped[t] + extras[t] for t in tenants}
        alloc = {t: floors_capped[t] + (extras[t] * surplus_cap) // total_extras for t in tenants}
        remainder = {t: (extras[t] * surplus_cap) - ((extras[t] * surplus_cap) // total_extras) * total_extras for t in tenants}
        remaining = surplus_cap - sum(alloc[t] - floors_capped[t] for t in tenants)
        for t in sorted(tenants, key=lambda x: (-remainder[x], _tie_priority(x)))[:remaining]:
            alloc[t] += 1
        return alloc

    if FLOOR_APPLICATION_ORDER == "floors_after_cap":
        initial = {t: min(demand.get(t, 0), inst.ceiling[t]) for t in tenants}
        total_initial = sum(initial.values())
        if total_initial <= total_cap:
            base = dict(initial)
        else:
            base = {t: (initial[t] * total_cap) // total_initial for t in tenants}
            remainder = {t: (initial[t] * total_cap) - base[t] * total_initial for t in tenants}
            remaining = total_cap - sum(base.values())
            ordering = sorted(tenants, key=lambda t: (-remainder[t], _tie_priority(t)))
            for t in ordering[:remaining]:
                base[t] += 1
        # Enforce floors after.
        for t in tenants:
            floor_target = min(inst.floor[t], demand.get(t, 0))
            if base[t] < floor_target:
                deficit = floor_target - base[t]
                donors = sorted(
                    (u for u in tenants if u != t and base[u] > min(inst.floor[u], demand.get(u, 0))),
                    key=lambda u: (base[u] - min(inst.floor[u], demand.get(u, 0)),),
                    reverse=True,
                )
                for u in donors:
                    if deficit <= 0:
                        break
                    take = min(deficit, base[u] - min(inst.floor[u], demand.get(u, 0)))
                    base[u] -= take
                    base[t] += take
                    deficit -= take
        return base

    raise ValueError(FLOOR_APPLICATION_ORDER)


def _slo_compliant(latency: int, slo_cap: int) -> bool:
    if SLO_COMPARISON == "strict_lt":
        return latency < slo_cap
    if SLO_COMPARISON == "non_strict_leq":
        return latency <= slo_cap
    raise ValueError(SLO_COMPARISON)


def _select_streams(inst: Instance, tenant: str, quota: int, epoch: int) -> list[str]:
    if quota <= 0:
        return []
    candidates = [
        s
        for s in inst.stream_ids
        if inst.stream_tenant[s] == tenant
        and inst.stream_arrival[s] <= epoch <= inst.stream_deadline[s]
    ]
    candidates.sort(key=lambda s: (-inst.class_priority[inst.stream_class[s]], s))
    return candidates[:quota]


def _place_streams(
    inst: Instance,
    admitted: list[str],
    epoch: int,
    prev_assignments: dict,
    bucket_tokens: dict,
) -> tuple[dict, list[dict], list[dict]]:
    node_load = {n: 0 for n in inst.node_ids}
    node_priority_load = {n: 0 for n in inst.node_ids}
    assignments: dict[str, str] = {}
    preemption_events: list[dict] = []
    migration_events: list[dict] = []
    tenant_running = {t: 0 for t in inst.tenant_ids}
    node_streams: dict[str, list[str]] = {n: [] for n in inst.node_ids}

    ordered = sorted(
        admitted,
        key=lambda s: (
            -inst.class_priority[inst.stream_class[s]],
            inst.stream_tenant[s],
            s,
        ),
    )

    def _node_priority(stream: str, node: str) -> tuple:
        prev = prev_assignments.get(stream)
        migration_pref = 0 if prev == node else 1
        latency = inst.latency[(node, inst.tenant_region[inst.stream_tenant[stream]])]
        return (migration_pref, latency, node)

    def _feasible(stream: str, node: str) -> bool:
        cls = inst.stream_class[stream]
        tenant = inst.stream_tenant[stream]
        if node_load[node] + 1 > inst.capacity[node]:
            return False
        if inst.class_priority[cls] >= 2 and node_priority_load[node] + 1 > inst.priority_lanes[node]:
            return False
        cost = inst.mtu_units[(inst.mtu_class[node], cls)]
        if bucket_tokens[node] < cost:
            return False
        if not _slo_compliant(inst.latency[(node, inst.tenant_region[tenant])], inst.class_slo_hops[cls]):
            return False
        if tenant_running[tenant] + 1 > inst.ceiling[tenant]:
            return False
        return True

    def _apply(stream: str, node: str) -> None:
        cls = inst.stream_class[stream]
        tenant = inst.stream_tenant[stream]
        cost = inst.mtu_units[(inst.mtu_class[node], cls)]
        assignments[stream] = node
        node_load[node] += 1
        if inst.class_priority[cls] >= 2:
            node_priority_load[node] += 1
        bucket_tokens[node] -= cost
        tenant_running[tenant] += 1
        node_streams[node].append(stream)

    def _revoke(stream: str) -> None:
        node = assignments.pop(stream)
        cls = inst.stream_class[stream]
        tenant = inst.stream_tenant[stream]
        cost = inst.mtu_units[(inst.mtu_class[node], cls)]
        node_load[node] -= 1
        if inst.class_priority[cls] >= 2:
            node_priority_load[node] -= 1
        bucket_tokens[node] += cost
        tenant_running[tenant] -= 1
        node_streams[node].remove(stream)

    for stream in ordered:
        cls = inst.stream_class[stream]
        candidates = sorted(inst.node_ids, key=lambda n: _node_priority(stream, n))
        placed = False
        for node in candidates:
            if _feasible(stream, node):
                _apply(stream, node)
                placed = True
                break
        if placed:
            continue

        # Preemption cascade (depth exactly 1, per README-input-schema.md Phase 6b).
        cascade = _try_cascade(
            inst=inst,
            beneficiary=stream,
            node_streams=node_streams,
            assignments=assignments,
            bucket_tokens=bucket_tokens,
            tenant_running=tenant_running,
            node_load=node_load,
            node_priority_load=node_priority_load,
            candidates=candidates,
        )
        if cascade is not None:
            evictions, target_node = cascade
            for victim in evictions:
                preemption_events.append(
                    {
                        "epoch": epoch,
                        "victim": victim,
                        "class": inst.stream_class[victim],
                        "beneficiary": stream,
                        "reason": "cascade_evicted",
                    }
                )
                _revoke(victim)
            _apply(stream, target_node)
        else:
            preemption_events.append(
                {
                    "epoch": epoch,
                    "victim": stream,
                    "class": cls,
                    "beneficiary": None,
                    "reason": "no_feasible_node",
                }
            )

    # Migration events for placed streams.
    for stream in inst.stream_ids:
        if stream not in assignments:
            continue
        prev = prev_assignments.get(stream)
        curr = assignments[stream]
        if prev is not None and prev != curr:
            tenant = inst.stream_tenant[stream]
            base = inst.migration_base[(tenant, epoch)]
            cost = base * inst.migration_mult[tenant]
            migration_events.append(
                {
                    "epoch": epoch,
                    "stream": stream,
                    "from": prev,
                    "to": curr,
                    "cost": cost,
                }
            )

    return assignments, preemption_events, migration_events


def _try_cascade(
    inst: Instance,
    beneficiary: str,
    node_streams: dict,
    assignments: dict,
    bucket_tokens: dict,
    tenant_running: dict,
    node_load: dict,
    node_priority_load: dict,
    candidates: list,
) -> tuple[list[str], str] | None:
    ben_cls = inst.stream_class[beneficiary]
    ben_tenant = inst.stream_tenant[beneficiary]

    for node in candidates:
        # Compose candidate victims on this node (single-hop cascade).
        victims_pool = [
            s
            for s in node_streams[node]
            if inst.stream_class[s] in inst.preempts.get(ben_cls, set())
        ]
        victims_pool.sort(
            key=lambda s: (
                -inst.latency[(node, inst.tenant_region[inst.stream_tenant[s]])] * inst.stream_rate[s],
                s,
            ),
        )

        for victim in victims_pool:
            # Simulate revocation.
            v_cls = inst.stream_class[victim]
            v_tenant = inst.stream_tenant[victim]
            cost_ben = inst.mtu_units[(inst.mtu_class[node], ben_cls)]
            cost_vic = inst.mtu_units[(inst.mtu_class[node], v_cls)]
            new_load = node_load[node] - 1 + 1
            new_priority = node_priority_load[node] - (1 if inst.class_priority[v_cls] >= 2 else 0) + (
                1 if inst.class_priority[ben_cls] >= 2 else 0
            )
            new_bucket = bucket_tokens[node] + cost_vic - cost_ben
            if new_load > inst.capacity[node]:
                continue
            if new_priority > inst.priority_lanes[node]:
                continue
            if new_bucket < 0:
                continue
            if not _slo_compliant(
                inst.latency[(node, inst.tenant_region[ben_tenant])],
                inst.class_slo_hops[ben_cls],
            ):
                continue
            if tenant_running[ben_tenant] + 1 > inst.ceiling[ben_tenant]:
                continue
            return [victim], node
        # Cascade halts after this single eviction; a preempted stream never preempts further.
    return None


def _bucket_state_next(
    inst: Instance,
    epoch: int,
    consumed: dict,
    bucket_tokens_start: dict,
) -> dict:
    next_tokens = {}
    for node in inst.node_ids:
        available = min(
            inst.bucket_capacity[node],
            bucket_tokens_start[node] - consumed[node],
        )
        num = inst.refill_num[node] * inst.duration_num[epoch]
        den = inst.refill_den[node] * inst.duration_den[epoch]
        refill = _round_frac(num, den, BUCKET_REFILL_ROUNDING)
        next_tokens[node] = min(inst.bucket_capacity[node], available + refill)
    return next_tokens


def solve(data_dir: Path) -> dict:
    inst = Instance(data_dir)

    epoch_assignments: list[dict] = []
    epoch_preemptions: list[list[dict]] = []
    epoch_migrations: list[list[dict]] = []
    fixed_point_iterations: list[dict] = []

    bucket_tokens = {n: inst.bucket_capacity[n] + inst.refill_offset[n] for n in inst.node_ids}
    prev_assignments = dict(inst.warm_start)
    utilization = {n: [] for n in inst.node_ids}

    total_iterations = 0
    for epoch in inst.epochs:
        active = inst.active_streams(epoch)
        demand = {t: 0 for t in inst.tenant_ids}
        for s in active:
            demand[inst.stream_tenant[s]] += 1
        total_cap = sum(inst.capacity.values())

        prev_admissions = {t: 0 for t in inst.tenant_ids}
        it = 0
        while True:
            it += 1
            total_iterations += 1
            quota = _apportion(inst, demand, epoch, total_cap)
            admitted: list[str] = []
            for tenant in inst.tenant_ids:
                admitted.extend(_select_streams(inst, tenant, quota.get(tenant, 0), epoch))

            # Snapshot bucket tokens for placement (do not mutate carry-over).
            placement_bucket = dict(bucket_tokens)
            assignments, preemptions, migrations = _place_streams(
                inst=inst,
                admitted=admitted,
                epoch=epoch,
                prev_assignments=prev_assignments,
                bucket_tokens=placement_bucket,
            )
            admissions = {t: 0 for t in inst.tenant_ids}
            for s, node in assignments.items():
                admissions[inst.stream_tenant[s]] += 1

            delta = sum(abs(admissions[t] - prev_admissions[t]) for t in inst.tenant_ids)
            fixed_point_iterations.append(
                {
                    "iteration": total_iterations - 1,
                    "delta": delta,
                    "admitted_total": sum(admissions.values()),
                }
            )
            if delta <= inst.tolerance or it >= inst.max_iterations:
                # Persist the final iteration's state.
                consumed = {n: sum(1 for s in assignments if assignments[s] == n) for n in inst.node_ids}
                node_priority_used = {n: 0 for n in inst.node_ids}
                for s, node in assignments.items():
                    if inst.class_priority[inst.stream_class[s]] >= 2:
                        node_priority_used[node] += 1
                bucket_start_snapshot = dict(bucket_tokens)
                bucket_tokens_end = {
                    n: bucket_start_snapshot[n] - consumed[n] for n in inst.node_ids
                }
                for n in inst.node_ids:
                    utilization[n].append(
                        {
                            "epoch": epoch,
                            "used": consumed[n],
                            "capacity": inst.capacity[n],
                            "priority_used": node_priority_used[n],
                            "priority_capacity": inst.priority_lanes[n],
                            "bucket_tokens_start": bucket_start_snapshot[n],
                            "bucket_tokens_end": bucket_tokens_end[n],
                        }
                    )
                epoch_assignments.append(
                    {
                        "epoch": epoch,
                        "assignments": dict(sorted(assignments.items())),
                        "preempted": sorted(ev["victim"] for ev in preemptions),
                    }
                )
                epoch_preemptions.append(preemptions)
                epoch_migrations.append(migrations)
                # Bucket refill for next epoch.
                bucket_tokens = _bucket_state_next(inst, epoch, consumed, bucket_tokens)
                prev_assignments = dict(assignments)
                break
            prev_admissions = admissions

    # ----- Assemble artifacts -----
    schedule_matrix = {"epochs": epoch_assignments}
    fleet_utilization = {
        "nodes": [
            {"node": n, "utilization_by_epoch": utilization[n]}
            for n in inst.node_ids
        ]
    }
    tenant_report = []
    for t in inst.tenant_ids:
        epochs_list = []
        for idx, epoch in enumerate(inst.epochs):
            admitted_count = sum(
                1
                for s, node in epoch_assignments[idx]["assignments"].items()
                if inst.stream_tenant[s] == t
            )
            active_here = [
                s
                for s in inst.stream_ids
                if inst.stream_tenant[s] == t
                and inst.stream_arrival[s] <= epoch <= inst.stream_deadline[s]
            ]
            target = min(len(active_here), inst.ceiling[t])
            epochs_list.append(
                {
                    "epoch": epoch,
                    "admitted": admitted_count,
                    "target": target,
                    "deviation": abs(admitted_count - target),
                }
            )
        tenant_report.append(
            {
                "tenant": t,
                "floor": inst.floor[t],
                "ceiling": inst.ceiling[t],
                "epochs": epochs_list,
            }
        )
    tenant_fairness_report = {"tenants": tenant_report}

    migration_events_flat: list[dict] = []
    for evs in epoch_migrations:
        migration_events_flat.extend(evs)
    migration_events_flat.sort(key=lambda e: (e["epoch"], e["stream"]))
    migration_total = sum(e["cost"] for e in migration_events_flat)
    migration_ledger = {"events": migration_events_flat, "total_cost": migration_total}

    preemption_events_flat: list[dict] = []
    for evs in epoch_preemptions:
        preemption_events_flat.extend(evs)
    preemption_events_flat.sort(key=lambda e: (e["epoch"], e["victim"]))
    preemption_report = {
        "events": preemption_events_flat,
        "total_count": len(preemption_events_flat),
    }

    by_class = []
    for cls in sorted(inst.class_by_id):
        placed = 0
        for entry in epoch_assignments:
            for s in entry["assignments"]:
                if inst.stream_class[s] == cls:
                    placed += 1
        by_class.append({"class": cls, "breaches": 0, "streams_placed": placed})
    sla_report = {"by_class": by_class, "total_breaches": 0}

    latency_cost = 0
    for idx, epoch in enumerate(inst.epochs):
        for s, node in epoch_assignments[idx]["assignments"].items():
            tenant = inst.stream_tenant[s]
            latency_cost += inst.latency[(node, inst.tenant_region[tenant])] * inst.stream_rate[s]
    fairness_dev = 0
    for entry in tenant_report:
        for e in entry["epochs"]:
            fairness_dev += e["deviation"]
    total_cost = inst.alpha * latency_cost + inst.beta * migration_total + inst.gamma * fairness_dev
    objective = {
        "alpha": inst.alpha,
        "beta": inst.beta,
        "gamma": inst.gamma,
        "fairness_deviation": fairness_dev,
        "latency_cost": latency_cost,
        "migration_cost": migration_total,
        "total_cost": total_cost,
    }

    fixed_point_trace = {
        "converged": True,
        "final_iteration": total_iterations - 1,
        "iterations": fixed_point_iterations,
    }

    artifacts_payload = {
        "schedule_matrix.json": schedule_matrix,
        "fleet_utilization.json": fleet_utilization,
        "tenant_fairness_report.json": tenant_fairness_report,
        "migration_ledger.json": migration_ledger,
        "preemption_events.json": preemption_report,
        "sla_violation_report.json": sla_report,
        "objective_breakdown.json": objective,
        "fixed_point_trace.json": fixed_point_trace,
    }

    return {
        "artifacts": artifacts_payload,
        "epoch_count": inst.epoch_count,
        "stream_count": len(inst.stream_ids),
        "total_cost": total_cost,
    }


def _write_artifacts(out_dir: Path, result: dict) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    sha_map = {}
    for name in CANONICAL_ARTIFACT_ORDER:
        payload = result["artifacts"][name]
        canon = _canonical(payload)
        (out_dir / name).write_bytes(canon)
        sha_map[name] = hashlib.sha256(canon).hexdigest()

    manifest = {
        "artifact_names": sorted(sha_map),
        "artifact_sha256": sha_map,
    }
    manifest_bytes = _canonical(manifest)
    (out_dir / "integrity_manifest.json").write_bytes(manifest_bytes)

    folded = hashlib.sha256(
        json.dumps(sha_map, sort_keys=True).encode("utf-8")
    ).hexdigest()
    final_state = {
        "artifact_count": 10,
        "epoch_count": result["epoch_count"],
        "folded_digest_sha256": folded,
        "stream_count": result["stream_count"],
        "total_cost": result["total_cost"],
    }
    (out_dir / "final_state.json").write_bytes(_canonical(final_state))
    return {"manifest_sha256": sha_map, "folded": folded}


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: reusable_scheduler.py <data_dir> <out_dir>", file=sys.stderr)
        return 2
    data_dir = Path(argv[1])
    out_dir = Path(argv[2])
    result = solve(data_dir)
    _write_artifacts(out_dir, result)
    self_path = Path(__file__).resolve()
    (out_dir / "reusable_scheduler.py").write_bytes(self_path.read_bytes())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
