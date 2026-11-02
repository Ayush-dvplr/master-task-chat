#!/usr/bin/env python3
"""Mixture of experts dispatch, compile and settlement planner.

Verbs:
  build DATA_DIR OUT_DIR   read a corpus directory, write every record
  trace CONFIG_DOCUMENT    compile and dispatch records for one document
  replay RUN_DOCUMENT      routing, numeric and loss records for one document
  settle CANDIDATE_DOCUMENT   candidate sweep for one document
  resolve SEALED_DOCUMENT  sealed policy resolution for one document

Standard library only.
"""

import csv
import hashlib
import itertools
import json
import math
import os
import struct
import sys

MASK64 = (1 << 64) - 1
GOLDEN = 0x9E3779B97F4A7C15
FNV_OFFSET = 0xCBF29CE484222325
FNV_PRIME = 0x100000001B3

CONFIG_KEYS = (
    "aux_loss_weight",
    "cache_size_limit",
    "capacity_bucket",
    "capacity_factor",
    "clip_threshold",
    "compile_mode",
    "dynamic_promotion_enabled",
    "ep_world_size",
    "expert_bias_enabled",
    "learning_rate",
    "loss_scale",
    "mark_dynamic",
    "min_capacity",
    "moe_layer_indices",
    "num_experts",
    "promotion_threshold",
    "reset_steps",
    "router_jitter_slots",
    "run_id",
    "seed",
    "seq_profile",
    "steps",
    "top_k",
    "warmup_bound",
)

TIE_FIELDS = ("expert_index", "running_load", "placement_rank", "bias_rank")

CAUSE_NAMES = (
    "capacity_below_minimum",
    "convergence_band_unmet",
    "drop_tolerance_exceeded",
    "eager_mode_forbidden",
    "memory_ceiling_exceeded",
    "recompile_budget_exceeded",
    "speedup_gate_unmet",
)

STAGE_RECORDS = (
    "route_plan.json",
    "capacity_plan.json",
    "mesh_plan.json",
    "dispatch_ledger.json",
    "drop_ledger.json",
    "alltoall_ledger.json",
    "guard_key_index.json",
    "recompile_report.json",
    "graph_break_ledger.json",
    "cudagraph_report.json",
    "host_memory_report.json",
    "steptime_report.json",
    "warmup_profile.json",
    "sealed_policy_resolution.json",
)

REPLAY_RECORDS = (
    "aux_loss_trace.json",
    "loss_curve.json",
    "gradient_ledger.json",
    "optimizer_trace.json",
    "convergence_report.json",
    "baseline_parity.json",
    "settlement_report.json",
    "rejection_ledger.json",
    "sensitivity.json",
    "audit_statistics.json",
    "deployed_diagnosis.json",
    "validation_report.json",
)

MANIFEST_RECORDS = ("stage_manifest.json", "replay_manifest.json", "final_state.json")


class PlannerError(Exception):
    pass


# ---------------------------------------------------------------- serialisation


def canonical_bytes(value):
    text = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False)
    return (text + "\n").encode("utf-8")


def digest_of(value):
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


# ------------------------------------------------------------------- numerics


def rnd(value, decimals):
    out = round(float(value), decimals)
    if out == 0.0:
        return 0.0
    return out


def f32(value):
    return struct.unpack("<f", struct.pack("<f", value))[0]


def bf16(value):
    """Top sixteen bits of the binary32 value, round to nearest ties to even."""
    single = struct.unpack("<I", struct.pack("<f", value))[0]
    low = single & 0xFFFF
    truncated = single & 0xFFFF0000
    if low > 0x8000 or (low == 0x8000 and (truncated >> 16) & 1):
        truncated = (truncated + 0x10000) & 0xFFFFFFFF
    return struct.unpack("<f", struct.pack("<I", truncated))[0]


FP8_MAX = 448.0
FP8_SUBNORMAL_QUANTUM = 2.0 ** -9


def fp8(value):
    """Four bit exponent, three bit mantissa, bias seven, no infinity."""
    if value == 0.0:
        return 0.0
    sign = -1.0 if value < 0.0 else 1.0
    magnitude = abs(float(value))
    unbiased = math.frexp(magnitude)[1] - 1
    if unbiased < -6:
        quantum = FP8_SUBNORMAL_QUANTUM
    else:
        quantum = 2.0 ** (unbiased - 3)
    scaled = magnitude / quantum
    units = round_half_even(scaled)
    rounded = units * quantum
    if rounded > FP8_MAX:
        rounded = FP8_MAX
    return sign * rounded


def round_half_even(value):
    floor = math.floor(value)
    diff = value - floor
    if diff > 0.5:
        return floor + 1
    if diff < 0.5:
        return floor
    return floor if floor % 2 == 0 else floor + 1


def token_feature(draw):
    return draw * 2.0 - 1.0


def quantize(logit, levels):
    return round_half_even(logit * levels) / levels


# ------------------------------------------------------------------- the stream


def xorshift(state):
    x = state & MASK64
    x ^= (x << 13) & MASK64
    x &= MASK64
    x ^= x >> 7
    x ^= (x << 17) & MASK64
    return x & MASK64


class Stream(object):
    __slots__ = ("state",)

    def __init__(self, seed):
        state = seed & MASK64
        if state == 0:
            state = GOLDEN
        self.state = state

    def next_u64(self):
        self.state = xorshift(self.state)
        return self.state

    def unit(self):
        return (self.next_u64() >> 11) * 2.0 ** -53


def mixing_hash(parts):
    h = FNV_OFFSET
    for part in parts:
        h ^= part & MASK64
        h = (h * FNV_PRIME) & MASK64
        h ^= h >> 29
    return h


def step_seed(seed, step):
    return mixing_hash((seed, step))


# -------------------------------------------------------------- corpus loading


def parse_csv_text(text):
    rows = []
    for row in csv.DictReader(line for line in text.splitlines() if line.strip() != ""):
        rows.append({key: ("" if value is None else value) for key, value in row.items()})
    return rows


def load_corpus(data_dir):
    if not os.path.isdir(data_dir):
        raise PlannerError("corpus directory is not a directory: %s" % data_dir)
    tables = {}
    for name in sorted(os.listdir(data_dir)):
        path = os.path.join(data_dir, name)
        if not os.path.isfile(path):
            continue
        if name.endswith(".json"):
            with open(path, "r", encoding="utf-8") as handle:
                try:
                    tables[name] = json.load(handle)
                except ValueError as exc:
                    raise PlannerError("file is not valid JSON: %s (%s)" % (name, exc))
        elif name.endswith(".jsonl"):
            records = []
            with open(path, "r", encoding="utf-8") as handle:
                for number, line in enumerate(handle, 1):
                    if line.strip() == "":
                        continue
                    try:
                        records.append(json.loads(line))
                    except ValueError as exc:
                        raise PlannerError(
                            "file holds an invalid JSON line: %s line %d (%s)" % (name, number, exc)
                        )
            tables[name] = records
        elif name.endswith(".csv"):
            with open(path, "r", encoding="utf-8") as handle:
                tables[name] = parse_csv_text(handle.read())
    return tables


def require_table(tables, name):
    if name not in tables:
        raise PlannerError("corpus is missing the required file: %s" % name)
    return tables[name]


def require_config(raw, origin):
    if not isinstance(raw, dict):
        raise PlannerError("configuration is not an object: %s" % origin)
    missing = [key for key in CONFIG_KEYS if key not in raw]
    if missing:
        raise PlannerError(
            "configuration is missing the required setting %s: %s" % (missing[0], origin)
        )
    return dict(raw)


# ------------------------------------------------------------------- the tables


class Corpus(object):
    def __init__(self, tables):
        self.tables = tables
        self.topology = require_table(tables, "model_topology.json")
        router = self.topology.get("router", {})
        self.jitter_scale = float(router["jitter_scale"])
        self.quantization_levels = int(router["quantization_levels"])
        surrogate = self.topology.get("surrogate", {})
        self.payload_scale = float(surrogate["payload_scale"])
        self.signal_weight = float(surrogate["signal_weight"])
        self.base_loss = float(surrogate["base_loss"])
        self.decay_rate = float(surrogate["decay_rate"])

        tolerances = require_table(tables, "validation_tolerances.json")
        self.float_decimals = int(tolerances["float_decimals"])
        self.time_decimals = int(tolerances["time_decimals"])

        self.bias_gain = {}
        for row in require_table(tables, "expert_bias_table.csv"):
            self.bias_gain[int(row["expert_index"])] = float(row["bias_gain"])
        self.cost_weight = {}
        self.kernel_us = {}
        for row in require_table(tables, "expert_cost_table.csv"):
            index = int(row["expert_index"])
            self.cost_weight[index] = float(row["cost_weight"])
            self.kernel_us[index] = float(row["kernel_us_per_slot"])
        self.placement_group = {}
        for row in require_table(tables, "expert_placement.csv"):
            self.placement_group[int(row["expert_index"])] = int(row["placement_group"])

        self.rank_affinity = {}
        for row in require_table(tables, "rank_affinity.csv"):
            world = int(row["ep_world_size"])
            self.rank_affinity.setdefault(world, []).append(
                (int(row["group_order"]), int(row["rank"]))
            )

        self.alltoall_cost = {}
        for row in require_table(tables, "alltoall_cost_table.csv"):
            self.alltoall_cost[int(row["ep_world_size"])] = (
                float(row["fixed_us"]),
                float(row["per_slot_us"]),
            )
        self.capture_cost = {}
        for row in require_table(tables, "capture_cost_table.csv"):
            self.capture_cost[row["compile_mode"]] = (
                float(row["capture_us"]),
                float(row["replay_discount"]),
            )
        self.compile_cost = {}
        for row in require_table(tables, "compile_cost_table.csv"):
            self.compile_cost[(row["compile_mode"], int(row["static_dims"]))] = float(
                row["compile_us"]
            )
        self.memory_slots = {}
        for row in require_table(tables, "memory_slot_table.csv"):
            self.memory_slots[int(row["static_dims"])] = (
                int(row["entry_bytes"]),
                int(row["guard_bytes"]),
            )
        self.pool_blocks = []
        for row in require_table(tables, "pool_block_table.csv"):
            self.pool_blocks.append((int(row["capacity_ceiling"]), int(row["block_bytes"])))
        self.break_causes = []
        self.bubble_us = {}
        for row in require_table(tables, "graph_break_catalog.csv"):
            self.break_causes.append(row["cause"])
            self.bubble_us[row["cause"]] = float(row["bubble_us"])
        self.break_causes.sort()

        self.schedule = {}
        for row in require_table(tables, "seq_length_schedule.csv"):
            self.schedule.setdefault(row["profile"], []).append(
                (int(row["step"]), int(row["tokens"]))
            )
        for profile in self.schedule:
            self.schedule[profile].sort()

        gates = require_table(tables, "steptime_gates.json")
        self.min_speedup = float(gates["min_speedup"])
        self.recompile_budget = int(gates["recompile_budget"])
        self.sync_bubble_us = float(gates["sync_bubble_us"])
        self.eager_compute_multiplier = float(gates["eager_compute_multiplier"])
        self.fallback_compile_us = float(gates["fallback_compile_us"])

        memory = require_table(tables, "memory_gates.json")
        self.host_base_bytes = int(memory["host_base_bytes"])
        self.host_ceiling_bytes = int(memory["host_ceiling_bytes"])
        self.capacity_floor = int(memory["capacity_floor"])

        convergence = require_table(tables, "convergence_gates.json")
        self.parity_band = float(convergence["parity_band"])
        self.settlement_parity_band = float(convergence["settlement_parity_band"])
        self.max_drop_rate = float(convergence["max_drop_rate"])
        self.max_slope = float(convergence["max_slope"])
        self.slope_window = int(convergence["slope_window"])
        self.target_loss = float(convergence["target_loss"])

        self.candidates = require_table(tables, "capacity_candidates.json")
        self.bounds = require_table(tables, "contract_bounds.json")["settings"]
        self.register = require_table(tables, "revision_register.json")["revisions"]

    def revision_in_force(self, policy):
        best = None
        for entry in self.register:
            if entry["policy"] != policy or entry["status"] != "applied":
                continue
            if best is None or entry["effective_order"] > best["effective_order"]:
                best = entry
        if best is None:
            raise PlannerError("revision register has no applied revision for policy: %s" % policy)
        return best["revision"]

    def token_counts(self, profile, steps):
        rows = self.schedule.get(profile)
        if not rows:
            raise PlannerError(
                "sequence schedule has no rows for the profile named by seq_profile: %s" % profile
            )
        tokens = [value for _, value in rows]
        return [tokens[(step - 1) % len(tokens)] for step in range(1, steps + 1)]

    def rank_order(self, world):
        rows = self.rank_affinity.get(world)
        if not rows:
            raise PlannerError(
                "rank affinity table has no rows for ep_world_size: %d" % world
            )
        return [rank for _, rank in sorted(rows)]

    def pool_block(self, bucket):
        for ceiling, block in self.pool_blocks:
            if ceiling >= bucket:
                return block
        raise PlannerError(
            "pool block table has no row whose capacity_ceiling covers the rank bucket: %d"
            % bucket
        )

    def compile_us(self, mode, static_dims):
        key = (mode, static_dims)
        if key not in self.compile_cost:
            return self.fallback_compile_us
        return self.compile_cost[key]

    def memory_slot(self, marked):
        if marked not in self.memory_slots:
            raise PlannerError(
                "memory slot table has no row whose static_dims equals the marked count: %d"
                % marked
            )
        return self.memory_slots[marked]


def validate_config(cfg, origin):
    if cfg["num_experts"] % cfg["ep_world_size"] != 0:
        raise PlannerError(
            "num_experts %d does not divide by ep_world_size %d: %s"
            % (cfg["num_experts"], cfg["ep_world_size"], origin)
        )
    if cfg["top_k"] < 1 or cfg["top_k"] > cfg["num_experts"]:
        raise PlannerError(
            "top_k is outside the expert range: %r: %s" % (cfg["top_k"], origin)
        )
    if cfg["steps"] < 1:
        raise PlannerError("steps is not positive: %r: %s" % (cfg["steps"], origin))
    for name in cfg["mark_dynamic"]:
        if name not in ("tokens", "capacity", "local_experts"):
            raise PlannerError("mark_dynamic names an unknown dimension: %r: %s" % (name, origin))


# ------------------------------------------------------------------- placement


def place_experts(corpus, num_experts, world):
    order = sorted(range(num_experts), key=lambda e: (corpus.placement_group[e], e))
    ranks = corpus.rank_order(world)
    if len(ranks) != world:
        raise PlannerError(
            "rank affinity table does not cover every rank for ep_world_size: %d" % world
        )
    block = num_experts // world
    expert_rank = [0] * num_experts
    rank_experts = {}
    for index, rank in enumerate(ranks):
        chunk = order[index * block:(index + 1) * block]
        rank_experts[rank] = sorted(chunk)
        for expert in chunk:
            expert_rank[expert] = rank
    return expert_rank, rank_experts


# --------------------------------------------------------------------- routing


def route_step(corpus, cfg, step, tokens, expert_rank, tie_order):
    experts = cfg["num_experts"]
    decimals = corpus.float_decimals
    stream = Stream(step_seed(cfg["seed"], step))
    token_salt = [stream.unit() for _ in range(tokens)]
    expert_phase = [stream.unit() for _ in range(experts)]
    if cfg["expert_bias_enabled"]:
        bias_draw = [stream.unit() for _ in range(experts)]
    else:
        bias_draw = [0.5] * experts
    slots = cfg["router_jitter_slots"]
    jitter = [stream.unit() for _ in range(slots)]

    gains = []
    for expert in range(experts):
        if expert not in corpus.bias_gain:
            raise PlannerError(
                "expert bias table has no row for expert_index: %d" % expert
            )
        gains.append(corpus.bias_gain[expert])
    bias = [rnd((bias_draw[e] * 2.0 - 1.0) * gains[e], decimals) for e in range(experts)]
    bias_rank = [int(gains[e] * 10.0) for e in range(experts)]

    token_bits = [int(math.floor(value * 2.0 ** 52)) for value in token_salt]
    expert_bits = [int(math.floor(value * 2.0 ** 52)) for value in expert_phase]

    levels = corpus.quantization_levels
    running_load = [0] * experts
    demand = [0] * experts
    gate_mass = [0.0] * experts
    assignments = []
    tie_events = []
    for i in range(tokens):
        qs = []
        for e in range(experts):
            affinity = Stream(mixing_hash((token_bits[i], expert_bits[e]))).next_u64()
            u = rnd((affinity >> 11) * 2.0 ** -53, decimals)
            if slots > 0:
                jit = rnd((jitter[(i + e) % slots] * 2.0 - 1.0) * corpus.jitter_scale, decimals)
            else:
                jit = 0.0
            logit = rnd((u * 2.0 - 1.0) + bias[e] + jit, decimals)
            qs.append(quantize(logit, levels))
        keyed = []
        for e in range(experts):
            fields = {
                "expert_index": e,
                "running_load": running_load[e],
                "placement_rank": expert_rank[e],
                "bias_rank": bias_rank[e],
            }
            keyed.append((-qs[e], tuple(fields[name] for name in tie_order), e))
        keyed.sort()
        selected = [entry[2] for entry in keyed[:cfg["top_k"]]]

        edge = qs[selected[-1]]
        contenders = [e for e in range(experts) if qs[e] == edge]
        if len(contenders) > 1:
            tie_events.append(
                {
                    "step": step,
                    "token_index": i,
                    "quantized_logit": rnd(edge, decimals),
                    "contenders": contenders,
                    "selected": sorted(e for e in selected if qs[e] == edge),
                }
            )

        floor_q = min(qs)
        shifts = [qs[e] - floor_q + 1.0 for e in selected]
        denominator = math.fsum(shifts)
        for position, expert in enumerate(selected):
            weight = rnd(shifts[position] / denominator, decimals)
            assignments.append((i, expert, weight))
            running_load[expert] += 1
            demand[expert] += 1
            gate_mass[expert] += weight

    return {
        "token_salt": token_salt,
        "assignments": assignments,
        "demand": demand,
        "gate_mass": gate_mass,
        "tie_events": tie_events,
    }


# --------------------------------------------------------------- tie break key


def tie_break_candidates():
    return [list(order) for order in itertools.permutations(TIE_FIELDS)]


def tie_break_events_for(corpus, cfg, steps, tie_order):
    expert_rank, _ = place_experts(corpus, cfg["num_experts"], cfg["ep_world_size"])
    counts = corpus.token_counts(cfg["seq_profile"], steps)
    events = []
    for step in range(1, steps + 1):
        routed = route_step(
            corpus, cfg, step, counts[step - 1], expert_rank, tie_order
        )
        events.extend(routed["tie_events"])
    return events


def resolve_tie_break_key(corpus):
    sealed = require_table(corpus.tables, "sealed_tiebreak_digests.json")["digests"]
    named = sealed_named_configs(corpus)
    candidates = tie_break_candidates()
    matches = []
    for order in candidates:
        for name in sorted(sealed):
            entry = sealed[name]
            events = tie_break_events_for(corpus, named[name], int(entry["steps"]), order)
            if digest_of(events) != entry["digest"]:
                break
        else:
            matches.append(order)
    if not matches:
        raise PlannerError(
            "no tie break field order reproduces the digests of sealed_tiebreak_digests.json"
        )
    narrowed = narrow_by_parity_rows(corpus, matches)
    narrowed.sort()
    return narrowed[0], len(narrowed), len(candidates), sorted(sealed)


def shipped_configs(tables):
    """Every run configuration carried by the corpus, keyed by run_id."""
    found = {}
    for name in sorted(tables):
        if not name.endswith(".json"):
            continue
        value = tables[name]
        nested = [value] if isinstance(value, dict) else []
        if isinstance(value, dict):
            nested.extend(item for item in value.values() if isinstance(item, dict))
        for item in nested:
            if all(key in item for key in CONFIG_KEYS):
                found.setdefault(item["run_id"], (name, dict(item)))
    return found


def parity_rows(corpus):
    """The shipped per step parity evidence and the configuration it describes."""
    baseline = corpus.tables.get("eager_baseline.json")
    rows = corpus.tables.get("calibration_parity.jsonl")
    if not isinstance(baseline, dict) or not isinstance(rows, list) or not rows:
        return None
    run_id = baseline.get("run_id")
    shipped = shipped_configs(corpus.tables)
    if run_id not in shipped:
        return None
    ordered = sorted(rows, key=lambda row: row["step"])
    if not all("capacity" in row and "accepted_count" in row for row in ordered):
        return None
    return shipped[run_id][1], ordered


def narrow_by_parity_rows(corpus, matches):
    """Keep the orders the shipped parity rows agree with, when they decide."""
    if len(matches) < 2:
        return list(matches)
    evidence = parity_rows(corpus)
    if evidence is None:
        return list(matches)
    cfg, rows = evidence
    horizon = min(len(rows), cfg["steps"])
    kept = []
    for order in matches:
        sim = Simulation(corpus, cfg, order, horizon=horizon)
        if all(
            row["capacity"] == rows[index]["capacity"]
            and row["accepted_count"] == rows[index]["accepted_count"]
            for index, row in enumerate(sim.per_step)
        ):
            kept.append(order)
    return kept if kept else list(matches)


def sealed_named_configs(corpus):
    calibration = require_config(
        require_table(corpus.tables, "calibration_config.json"), "calibration_config.json"
    )
    probes = require_table(corpus.tables, "probe_configurations.json")
    named = {"calibration": calibration}
    for name, raw in probes.items():
        named[name] = require_config(raw, "probe_configurations.json")
    return named


# ------------------------------------------------------------------ simulation


class Simulation(object):
    """One configuration replayed over a horizon against the contracts."""

    def __init__(self, corpus, cfg, tie_order, horizon=None, routing_cache=None):
        self.corpus = corpus
        self.cfg = cfg
        self.tie_order = tie_order
        self.steps = int(horizon if horizon is not None else cfg["steps"])
        self.reset_steps = sorted(
            step for step in cfg["reset_steps"] if 1 <= step <= self.steps
        )
        self.routing_cache = routing_cache if routing_cache is not None else {}
        self.run()

    # ------------------------------------------------------------- the routing
    def routed_step(self, step, tokens):
        key = (
            self.cfg["seed"],
            step,
            tokens,
            self.cfg["num_experts"],
            self.cfg["ep_world_size"],
            bool(self.cfg["expert_bias_enabled"]),
            self.cfg["router_jitter_slots"],
            self.cfg["top_k"],
            tuple(self.tie_order),
        )
        hit = self.routing_cache.get(key)
        if hit is None:
            hit = route_step(
                self.corpus, self.cfg, step, tokens, self.expert_rank, self.tie_order
            )
            self.routing_cache[key] = hit
        return hit

    # ---------------------------------------------------------------- the loop
    def run(self):
        corpus = self.corpus
        cfg = self.cfg
        experts = cfg["num_experts"]
        world = cfg["ep_world_size"]
        validate_config(cfg, cfg["run_id"])
        self.expert_rank, self.rank_experts = place_experts(corpus, experts, world)
        self.ranks = sorted(self.rank_experts)
        self.local_experts = experts // world
        self.layers = sorted(cfg["moe_layer_indices"])
        self.code_objects = ["router"] + ["moe_block_%d" % index for index in self.layers]
        self.token_counts = corpus.token_counts(cfg["seq_profile"], self.steps)
        mode = cfg["compile_mode"]
        if mode not in corpus.capture_cost:
            raise PlannerError("capture cost table has no row for compile_mode: %r" % mode)
        capture_us_each, discount = corpus.capture_cost[mode]
        marked = list(cfg["mark_dynamic"])
        entry_bytes, guard_bytes = corpus.memory_slot(len(marked))
        decimals = corpus.float_decimals
        td = corpus.time_decimals
        rank_kernel = {
            rank: math.fsum(corpus.kernel_us[e] for e in self.rank_experts[rank])
            for rank in self.ranks
        }
        if world not in corpus.alltoall_cost:
            raise PlannerError(
                "all to all cost table has no row for ep_world_size: %d" % world
            )
        fixed_us, per_slot_us = corpus.alltoall_cost[world]

        dynamic = {}
        seen = {}
        for name in self.code_objects:
            for dim in self.guarded_dims(name):
                dynamic[(name, dim)] = dim in marked
                seen[(name, dim)] = set()
        caches = {}
        for name in self.code_objects:
            for rank in self.ranks:
                caches[(name, rank)] = {}
        clock = 0
        pool = 0
        peak_carried = 0
        params = [0.0] * experts
        eager_params = [0.0] * experts
        folded = 0.0
        eager_folded = 0.0
        keys_by_slot = {}
        previous_tokens = None

        self.per_step = []
        self.recompile_events = []
        self.specialized_keys = set()
        self.evictions = 0
        self.capture_attempts = 0
        self.capture_success = 0
        self.failure_causes = {}
        self.tie_events = []

        for step in range(1, self.steps + 1):
            tokens = self.token_counts[step - 1]
            if step in self.reset_steps:
                for slot in caches:
                    caches[slot] = {}
                pool = 0
            routed = self.routed_step(step, tokens)
            demand = routed["demand"]
            gate_mass = routed["gate_mass"]
            total_assignments = sum(demand)
            capacity = self.capacities(demand, total_assignments)
            accepted, dropped, drop_mass = self.dispatch(routed["assignments"], capacity)
            accepted_count = [len(accepted[e]) for e in range(experts)]
            rank_bucket = {
                rank: max(capacity[e] for e in self.rank_experts[rank]) for rank in self.ranks
            }
            alltoall_bucket = max(rank_bucket.values())
            spread = alltoall_bucket - min(rank_bucket.values())
            payload_slots = alltoall_bucket * world * self.local_experts
            padded = sum(capacity[e] - accepted_count[e] for e in range(experts))

            causes = self.fired_causes(
                capacity, tokens, previous_tokens, len(dropped), rank_bucket, demand, marked
            )

            step_events = []
            visited_keys = []
            step_compile_us = 0.0
            for name in self.code_objects:
                for rank in self.ranks:
                    dims = self.dim_values(name, tokens, rank_bucket.get(rank))
                    key = self.key_text(name, dims, dynamic)
                    static_before = sum(1 for part in key.split("|") if part != "dyn")
                    cache = caches[(name, rank)]
                    clock += 1
                    if any(
                        dynamic[(name, dim)] and value in (0, 1) for dim, value in dims
                    ):
                        self.specialized_keys.add(key)
                    if key in cache:
                        cache[key] = clock
                        if name != "router":
                            visited_keys.append(key)
                        continue
                    if cfg["dynamic_promotion_enabled"]:
                        for dim, value in dims:
                            if dynamic[(name, dim)]:
                                continue
                            bag = seen[(name, dim)]
                            bag.add(value)
                            if len(bag) >= cfg["promotion_threshold"]:
                                dynamic[(name, dim)] = True
                    compiled_key = self.key_text(name, dims, dynamic)
                    static_after = sum(
                        1 for part in compiled_key.split("|") if part != "dyn"
                    )
                    if name != "router":
                        visited_keys.append(compiled_key)
                    evicted = None
                    if compiled_key not in cache and len(cache) >= cfg["cache_size_limit"]:
                        evicted = min(cache, key=lambda text: (cache[text], text))
                        del cache[evicted]
                        self.evictions += 1
                    cache[compiled_key] = clock
                    keys_by_slot.setdefault("%s@%d" % (name, rank), set()).add(compiled_key)
                    event = {
                        "step": step,
                        "code_object": name,
                        "rank": rank,
                        "guard_key": key,
                        "guard_delta": static_before - static_after,
                        "evicted_key": evicted,
                    }
                    step_compile_us += corpus.compile_us(mode, static_before)
                    step_events.append(event)
                    self.recompile_events.append(event)

            captured, attempts, step_failures = self.captures(
                visited_keys, mode, bool(causes)
            )
            self.capture_attempts += attempts
            self.capture_success += captured
            for cause, count in step_failures.items():
                self.failure_causes[cause] = self.failure_causes.get(cause, 0) + count
            if captured:
                pool += sum(corpus.pool_block(rank_bucket[rank]) for rank in self.ranks)
            pool_peak = max(peak_carried, pool)
            peak_carried = pool

            cache_entries = sum(len(cache) for cache in caches.values())
            guard_closures = 0
            for cache in caches.values():
                for text in cache:
                    guard_closures += sum(1 for part in text.split("|") if part != "dyn")
            host_bytes = (
                corpus.host_base_bytes
                + cache_entries * entry_bytes
                + guard_closures * guard_bytes
                + pool_peak
            )
            headroom = corpus.host_ceiling_bytes - host_bytes

            compile_us = rnd(step_compile_us, td)
            capture_us = rnd(capture_us_each * captured, td)
            compute_base = max(rank_kernel[rank] * rank_bucket[rank] for rank in self.ranks)
            compute_us = rnd(compute_base * discount if captured else compute_base, td)
            alltoall_us = rnd(fixed_us + per_slot_us * alltoall_bucket * world, td)
            bubble = math.fsum(corpus.bubble_us[cause] for cause in causes) * len(self.layers)
            if step_events:
                bubble += corpus.sync_bubble_us
            bubble_us = rnd(bubble, td)
            step_us = rnd(
                compile_us + capture_us + compute_us + alltoall_us + bubble_us, td
            )
            eager_compute_us = rnd(compute_base * corpus.eager_compute_multiplier, td)
            eager_step_us = rnd(eager_compute_us + alltoall_us, td)

            numeric = self.numeric_walk(routed["token_salt"], accepted, params)
            eager = self.eager_walk(routed["token_salt"], accepted, eager_params)
            folded = f32(folded + numeric["signal"])
            eager_folded = eager_folded + eager["signal"]

            balance = self.balance(demand, gate_mass, total_assignments, tokens, accepted_count)
            base_term = rnd(corpus.base_loss / (1.0 + corpus.decay_rate * step), decimals)
            aux_term = balance["aux_loss"]
            loss = rnd(
                base_term + aux_term + rnd(corpus.signal_weight * numeric["signal"], decimals),
                decimals,
            )
            eager_loss = rnd(
                base_term + aux_term + rnd(corpus.signal_weight * eager["signal"], decimals),
                decimals,
            )

            self.tie_events.extend(routed["tie_events"])

            self.per_step.append(
                {
                    "step": step,
                    "tokens": tokens,
                    "demand": list(demand),
                    "gate_mass": list(gate_mass),
                    "total_assignments": total_assignments,
                    "capacity": capacity,
                    "accepted_count": accepted_count,
                    "padded_slots": padded,
                    "dropped": len(dropped),
                    "dropped_mass": drop_mass,
                    "rank_bucket": rank_bucket,
                    "alltoall_bucket": alltoall_bucket,
                    "spread": spread,
                    "payload_slots": payload_slots,
                    "causes": causes,
                    "events": step_events,
                    "captured": captured,
                    "attempts": attempts,
                    "pool_bytes": pool,
                    "pool_peak_bytes": pool_peak,
                    "cache_entries": cache_entries,
                    "guard_closures": guard_closures,
                    "host_bytes": host_bytes,
                    "headroom": headroom,
                    "compile_us": compile_us,
                    "capture_us": capture_us,
                    "compute_us": compute_us,
                    "alltoall_us": alltoall_us,
                    "bubble_us": bubble_us,
                    "step_us": step_us,
                    "eager_step_us": eager_step_us,
                    "numeric": numeric,
                    "eager": eager,
                    "balance": balance,
                    "loss": loss,
                    "eager_loss": eager_loss,
                    "tie_count": len(routed["tie_events"]),
                }
            )
            previous_tokens = tokens

        self.keys_by_slot = keys_by_slot
        self.dynamic_final = dynamic
        self.params = params
        self.eager_params = eager_params
        self.folded_signal = folded
        self.eager_folded_signal = eager_folded
        self.marked = marked

    # --------------------------------------------------------------- the parts
    def guarded_dims(self, name):
        if name == "router":
            return ("tokens",)
        return ("capacity", "local_experts")

    def dim_values(self, name, tokens, bucket):
        if name == "router":
            return (("tokens", tokens),)
        return (("capacity", bucket), ("local_experts", self.local_experts))

    def key_text(self, name, dims, dynamic):
        parts = []
        for dim, value in dims:
            if dynamic[(name, dim)] and value not in (0, 1):
                parts.append("dyn")
            else:
                parts.append(str(value))
        return "|".join(parts)

    def capacities(self, demand, total_assignments):
        cfg = self.cfg
        bucket = cfg["capacity_bucket"]
        if bucket <= 0:
            raise PlannerError("capacity_bucket is not positive: %r" % bucket)
        ideal = cfg["capacity_factor"] * total_assignments / float(cfg["num_experts"])
        out = []
        for value in demand:
            target = min(float(value), ideal)
            aligned = bucket * int(math.ceil(math.ceil(target) / float(bucket)))
            out.append(max(int(cfg["min_capacity"]), aligned))
        return out

    def dispatch(self, assignments, capacity):
        counters = [0] * self.cfg["num_experts"]
        accepted = [[] for _ in range(self.cfg["num_experts"])]
        dropped = []
        mass = 0.0
        for token_index, expert, weight in assignments:
            slot = counters[expert]
            counters[expert] += 1
            if slot >= capacity[expert]:
                dropped.append((token_index, expert, weight))
                mass += weight
            else:
                accepted[expert].append((token_index, weight))
        return accepted, dropped, mass

    def fired_causes(
        self, capacity, tokens, previous_tokens, dropped, rank_bucket, demand, marked
    ):
        bucket = self.cfg["capacity_bucket"]
        causes = []
        if any(value % bucket != 0 for value in capacity):
            causes.append("data_dependent_capacity")
        if previous_tokens is not None and tokens != previous_tokens and "tokens" not in marked:
            causes.append("dynamic_token_count")
        if dropped:
            causes.append("token_drop_mask")
        if len(set(rank_bucket.values())) > 1:
            causes.append("unbalanced_expert_slice")
        if any(value == 0 for value in demand):
            causes.append("zero_token_expert")
        known = set(self.corpus.break_causes)
        for cause in causes:
            if cause not in known:
                raise PlannerError("graph break catalog has no row for cause: %s" % cause)
        return sorted(causes)

    def captures(self, visited_keys, mode, broke):
        keys = sorted(set(visited_keys))
        attempts = len(keys)
        captured = 0
        failures = {}
        for key in keys:
            if mode != "reduce-overhead":
                cause = "capture_disabled_for_mode"
            elif broke:
                cause = "operation_not_permitted_when_stream_is_capturing"
            elif "dyn" in key.split("|"):
                cause = "dynamic_dimension_in_guard_key"
            else:
                cause = None
            if cause is None:
                captured += 1
            else:
                failures[cause] = failures.get(cause, 0) + 1
        return captured, attempts, failures

    # ------------------------------------------------------------ numeric path
    def numeric_walk(self, token_salt, accepted, params):
        corpus = self.corpus
        scale = corpus.payload_scale
        experts = self.cfg["num_experts"]
        outputs = []
        partials = []
        signal = 0.0
        for expert in range(experts):
            slots = accepted[expert]
            if not slots:
                outputs.append(bf16(0.0))
                continue
            acc = 0.0
            for token_index, weight in slots:
                t = bf16(token_feature(token_salt[token_index]))
                w = bf16(weight)
                raw = f32(w * (1.0 - t * 0.25))
                payload = fp8(f32(raw * scale))
                value = f32(payload / scale)
                acc = f32(acc + value)
            outputs.append(bf16(f32(acc / len(slots))))
        for expert in range(experts):
            partial = f32(outputs[expert] * corpus.cost_weight[expert])
            partials.append(partial)
            signal = f32(signal + partial)
        gradients = [
            f32(outputs[expert] * corpus.signal_weight * corpus.cost_weight[expert])
            for expert in range(experts)
        ]
        scaled = [f32(gradient * self.cfg["loss_scale"]) for gradient in gradients]
        sumsq = 0.0
        for value in scaled:
            sumsq = f32(sumsq + f32(value * value))
        norm = math.sqrt(sumsq)
        reference = self.cfg["clip_threshold"] * self.cfg["loss_scale"]
        factor = 1.0 if norm <= reference else reference / norm
        clipped = [f32(value * factor) for value in scaled]
        unscaled = [f32(value / self.cfg["loss_scale"]) for value in clipped]
        for expert in range(experts):
            params[expert] = bf16(
                f32(params[expert] - f32(self.cfg["learning_rate"] * unscaled[expert]))
            )
        return {
            "outputs": outputs,
            "partials": partials,
            "signal": signal,
            "gradients": gradients,
            "scaled_norm": norm,
            "clip_reference": reference,
            "clip_factor": factor,
            "clipped": norm > reference,
            "unscaled": unscaled,
            "params": list(params),
        }

    def eager_walk(self, token_salt, accepted, params):
        corpus = self.corpus
        scale = corpus.payload_scale
        experts = self.cfg["num_experts"]
        outputs = []
        partials = []
        signal = 0.0
        for expert in range(experts):
            slots = accepted[expert]
            if not slots:
                outputs.append(0.0)
                continue
            acc = 0.0
            for token_index, weight in slots:
                t = token_feature(token_salt[token_index])
                w = weight
                raw = w * (1.0 - t * 0.25)
                payload = raw * scale
                acc = acc + payload / scale
            outputs.append(acc / len(slots))
        for expert in range(experts):
            partial = outputs[expert] * corpus.cost_weight[expert]
            partials.append(partial)
            signal = signal + partial
        gradients = [
            outputs[expert] * corpus.signal_weight * corpus.cost_weight[expert]
            for expert in range(experts)
        ]
        scaled = [gradient * self.cfg["loss_scale"] for gradient in gradients]
        sumsq = 0.0
        for value in scaled:
            sumsq = sumsq + value * value
        norm = math.sqrt(sumsq)
        reference = self.cfg["clip_threshold"] * self.cfg["loss_scale"]
        factor = 1.0 if norm <= reference else reference / norm
        clipped = [value * factor for value in scaled]
        unscaled = [value / self.cfg["loss_scale"] for value in clipped]
        for expert in range(experts):
            params[expert] = params[expert] - self.cfg["learning_rate"] * unscaled[expert]
        return {
            "outputs": outputs,
            "partials": partials,
            "signal": signal,
            "gradients": gradients,
            "scaled_norm": norm,
            "clip_reference": reference,
            "clip_factor": factor,
            "clipped": norm > reference,
            "params": list(params),
        }

    # ------------------------------------------------------------ balance term
    def balance(self, demand, gate_mass, total_assignments, tokens, accepted_count):
        corpus = self.corpus
        decimals = corpus.float_decimals
        experts = self.cfg["num_experts"]
        fractions = []
        probabilities = []
        for expert in range(experts):
            if total_assignments == 0:
                fractions.append(0.0)
            else:
                fractions.append(rnd(demand[expert] / float(total_assignments), decimals))
            if tokens == 0:
                probabilities.append(0.0)
            else:
                probabilities.append(rnd(gate_mass[expert] / float(tokens), decimals))
        total = 0.0
        for expert in range(experts):
            total += rnd(fractions[expert] * probabilities[expert], decimals)
        total = rnd(total, decimals)
        aux = rnd(self.cfg["aux_loss_weight"] * experts * total, decimals)
        live = [fractions[e] for e in range(experts) if demand[e] > 0]
        if not live:
            dispersion = None
        else:
            dispersion = rnd(max(live) - min(live), decimals)
        utilization = []
        for expert in range(experts):
            if demand[expert] == 0:
                utilization.append(None)
            else:
                utilization.append(
                    rnd(
                        accepted_count[expert] / float(demand[expert]) * fractions[expert],
                        decimals,
                    )
                )
        gate_total = rnd(math.fsum(probabilities) * tokens, decimals)
        return {
            "fractions": fractions,
            "probabilities": probabilities,
            "aux_loss": aux,
            "load_dispersion": dispersion,
            "expert_utilization": utilization,
            "empty_experts": [e for e in range(experts) if demand[e] == 0],
            "gate_mass_total": gate_total,
        }

    # ------------------------------------------------------------- aggregates
    def gated_steps(self):
        bound = self.cfg["warmup_bound"]
        return [row for row in self.per_step if row["step"] > bound]

    def window_steps(self):
        bound = self.cfg["warmup_bound"]
        return [row for row in self.per_step if row["step"] <= bound]

    def speedup(self):
        gated = self.gated_steps()
        compiled = rnd(math.fsum(row["step_us"] for row in gated), self.corpus.time_decimals)
        eager = rnd(math.fsum(row["eager_step_us"] for row in gated), self.corpus.time_decimals)
        if compiled == 0.0:
            return 0.0, compiled, eager
        return rnd(eager / compiled, self.corpus.float_decimals), compiled, eager

    def total_recompiles(self):
        return len(self.recompile_events)

    def recompiles_after_warmup(self):
        bound = self.cfg["warmup_bound"]
        return sum(1 for event in self.recompile_events if event["step"] > bound)

    def first_step_over_budget(self):
        bound = self.cfg["warmup_bound"]
        budget = self.corpus.recompile_budget
        running = 0
        for row in self.per_step:
            if row["step"] <= bound:
                continue
            running += len(row["events"])
            if running > budget:
                return row["step"]
        return None

    def drop_rate(self):
        dropped = sum(row["dropped"] for row in self.per_step)
        total = sum(row["total_assignments"] for row in self.per_step)
        if total == 0:
            return 0.0
        return rnd(dropped / float(total), self.corpus.float_decimals)

    def min_headroom(self):
        return min(row["headroom"] for row in self.per_step)

    def min_capacity_seen(self):
        return min(min(row["capacity"]) for row in self.per_step)

    def closing_loss(self):
        return self.per_step[-1]["loss"]

    def baseline_closing_loss(self):
        return self.per_step[-1]["eager_loss"]

    def relative_deviation(self):
        return relative_deviation(
            self.closing_loss(), self.baseline_closing_loss(), self.corpus.float_decimals
        )


def relative_deviation(compiled, eager, decimals):
    if eager == 0.0:
        return 0.0
    return rnd(abs(compiled - eager) / abs(eager), decimals)


# ------------------------------------------------------------------ settlement


def warmup_profile_figures(sim):
    window = sim.window_steps()
    tokens = sorted(set(row["tokens"] for row in window))
    buckets = sorted(set(
        value for row in window for value in row["rank_bucket"].values()
    ))
    locals_seen = sorted(set([sim.local_experts]) if window else [])
    threshold = sim.cfg["promotion_threshold"]
    required = []
    if len(tokens) >= threshold:
        required.append("tokens")
    if len(locals_seen) >= threshold:
        required.append("local_experts")
    return {
        "window_steps": [row["step"] for row in window],
        "distinct_token_values": tokens,
        "distinct_capacity_values": buckets,
        "distinct_local_expert_values": locals_seen,
        "promotion_threshold": threshold,
        "dims_requiring_dynamic": sorted(required),
        "warmup_recompiles": sum(len(row["events"]) for row in window),
    }


def candidate_label(candidate):
    marks = candidate["mark_dynamic"]
    text = "+".join(marks) if marks else "none"
    return "cf=%s|bucket=%d|dynamic=%s|mode=%s" % (
        repr(float(candidate["capacity_factor"])),
        candidate["capacity_bucket"],
        text,
        candidate["compile_mode"],
    )


def candidate_space(corpus):
    axes = corpus.candidates
    for name in ("capacity_bucket", "capacity_factor", "compile_mode", "mark_dynamic"):
        if name not in axes:
            raise PlannerError(
                "capacity_candidates.json is missing the candidate axis: %s" % name
            )
    space = []
    for factor in axes["capacity_factor"]:
        for bucket in axes["capacity_bucket"]:
            for marks in axes["mark_dynamic"]:
                for mode in axes["compile_mode"]:
                    space.append(
                        {
                            "capacity_factor": factor,
                            "capacity_bucket": bucket,
                            "mark_dynamic": list(marks),
                            "compile_mode": mode,
                        }
                    )
    return space


def merge_candidate(cfg, candidate):
    merged = dict(cfg)
    merged.update(
        {
            "capacity_factor": candidate["capacity_factor"],
            "capacity_bucket": candidate["capacity_bucket"],
            "mark_dynamic": list(candidate["mark_dynamic"]),
            "compile_mode": candidate["compile_mode"],
        }
    )
    return merged


def gate_figures(corpus, sim):
    speedup, compiled_tail, eager_tail = sim.speedup()
    return {
        "speedup": speedup,
        "compiled_tail_us": compiled_tail,
        "eager_tail_us": eager_tail,
        "min_host_headroom_bytes": sim.min_headroom(),
        "recompiles_after_warmup": sim.recompiles_after_warmup(),
        "drop_rate": sim.drop_rate(),
        "min_capacity_seen": sim.min_capacity_seen(),
        "closing_loss": sim.closing_loss(),
        "baseline_closing_loss": sim.baseline_closing_loss(),
        "relative_deviation": sim.relative_deviation(),
    }


def violations_of(corpus, candidate, figures):
    found = set()
    if candidate["compile_mode"] == "eager":
        found.add("eager_mode_forbidden")
    if figures["recompiles_after_warmup"] > corpus.recompile_budget:
        found.add("recompile_budget_exceeded")
    if figures["speedup"] < corpus.min_speedup:
        found.add("speedup_gate_unmet")
    if figures["min_host_headroom_bytes"] < 0:
        found.add("memory_ceiling_exceeded")
    if figures["drop_rate"] > corpus.max_drop_rate:
        found.add("drop_tolerance_exceeded")
    if figures["relative_deviation"] > corpus.settlement_parity_band:
        found.add("convergence_band_unmet")
    if figures["min_capacity_seen"] < corpus.capacity_floor:
        found.add("capacity_below_minimum")
    return found


class Sweep(object):
    """The documented candidate sweep of one configuration."""

    def __init__(self, corpus, cfg, tie_order, routing_cache=None):
        self.corpus = corpus
        self.cfg = cfg
        self.probe_steps = int(corpus.candidates["probe_steps"])
        if self.probe_steps < 1:
            raise PlannerError(
                "capacity_candidates.json carries a probe_steps that is not positive: %r"
                % corpus.candidates["probe_steps"]
            )
        cache = routing_cache if routing_cache is not None else {}
        self.full = Simulation(corpus, cfg, tie_order, routing_cache=cache)
        self.profile = warmup_profile_figures(self.full)
        required = self.profile["dims_requiring_dynamic"]
        self.prefiltered = []
        self.evaluated = []
        for candidate in candidate_space(corpus):
            label = candidate_label(candidate)
            unmarked = sorted(set(required) - set(candidate["mark_dynamic"]))
            if unmarked:
                self.prefiltered.append(
                    {"candidate": label, "unmarked_dimensions": unmarked}
                )
                continue
            horizon = min(self.probe_steps, cfg["steps"])
            sim = Simulation(
                corpus,
                merge_candidate(cfg, candidate),
                tie_order,
                horizon=horizon,
                routing_cache=cache,
            )
            figures = gate_figures(corpus, sim)
            self.evaluated.append(
                {
                    "candidate": candidate,
                    "label": label,
                    "figures": figures,
                    "violations": violations_of(corpus, candidate, figures),
                }
            )

    def cause_counts(self, order):
        counts = {name: 0 for name in CAUSE_NAMES}
        for entry in self.evaluated:
            cause = first_violated(order, entry["violations"])
            if cause is not None:
                counts[cause] += 1
        return counts

    def admissible(self):
        return [entry for entry in self.evaluated if not entry["violations"]]

    def settled(self):
        admissible = self.admissible()
        if not admissible:
            raise PlannerError(
                "the candidate sweep leaves no admissible candidate for run_id: %s"
                % self.cfg["run_id"]
            )
        return min(admissible, key=lambda entry: selection_key(entry["candidate"]))


def selection_key(candidate):
    marks = candidate["mark_dynamic"]
    return (
        float(candidate["capacity_factor"]),
        -int(candidate["capacity_bucket"]),
        len(marks),
        "|".join(marks),
        invert_text(candidate["compile_mode"]),
    )


def invert_text(text):
    return tuple(-ord(character) for character in text)


def first_violated(order, violations):
    for cause in order:
        if cause in violations:
            return cause
    return None


def precedence_candidates(corpus):
    constraints = [
        ("capacity_below_minimum", "drop_tolerance_exceeded"),
        ("recompile_budget_exceeded", "speedup_gate_unmet"),
    ]
    first = "eager_mode_forbidden"
    rest = [name for name in CAUSE_NAMES if name != first]
    out = []
    for tail in itertools.permutations(rest):
        order = [first] + list(tail)
        position = {name: index for index, name in enumerate(order)}
        if all(position[before] < position[after] for before, after in constraints):
            out.append(order)
    return out


def resolve_precedence_order(corpus, tie_order):
    sealed = require_table(corpus.tables, "sealed_precedence_digests.json")["digests"]
    named = sealed_named_configs(corpus)
    sweeps = {}
    for name in sorted(sealed):
        if name not in named:
            raise PlannerError(
                "sealed_precedence_digests.json names an unknown configuration: %s" % name
            )
        sweeps[name] = Sweep(corpus, named[name], tie_order)
    candidates = precedence_candidates(corpus)
    matches = []
    for order in candidates:
        for name in sorted(sealed):
            if digest_of(sweeps[name].cause_counts(order)) != sealed[name]["digest"]:
                break
        else:
            matches.append(order)
    if not matches:
        raise PlannerError(
            "no rejection cause order reproduces the digests of "
            "sealed_precedence_digests.json"
        )
    matches.sort()
    return matches[0], len(matches), len(candidates), sorted(sealed)


# --------------------------------------------------------------------- records


def route_plan(corpus, sim, tie_order):
    decimals = corpus.float_decimals
    steps = []
    for row in sim.per_step:
        steps.append(
            {
                "step": row["step"],
                "token_count": row["tokens"],
                "demand": list(row["demand"]),
                "gate_mass_total": row["balance"]["gate_mass_total"],
                "tie_break_count": row["tie_count"],
            }
        )
    events = []
    for event in sim.tie_events:
        events.append(
            {
                "step": event["step"],
                "token_index": event["token_index"],
                "quantized_logit": rnd(event["quantized_logit"], decimals),
                "contenders": list(event["contenders"]),
                "selected": list(event["selected"]),
            }
        )
    return {
        "run_id": sim.cfg["run_id"],
        "top_k": sim.cfg["top_k"],
        "tie_break_key": list(tie_order),
        "steps": steps,
        "tie_break_events": events,
        "total_assignments": sum(row["total_assignments"] for row in sim.per_step),
    }


def capacity_plan(corpus, sim):
    bucket = sim.cfg["capacity_bucket"]
    steps = []
    seen = set()
    for row in sim.per_step:
        steps.append(
            {
                "step": row["step"],
                "capacity": list(row["capacity"]),
                "unaligned_experts": [
                    index
                    for index, value in enumerate(row["capacity"])
                    if value % bucket != 0
                ],
            }
        )
        seen.update(row["capacity"])
    return {
        "run_id": sim.cfg["run_id"],
        "capacity_factor": sim.cfg["capacity_factor"],
        "capacity_bucket": bucket,
        "min_capacity": sim.cfg["min_capacity"],
        "steps": steps,
        "min_capacity_seen": min(seen),
        "max_capacity_seen": max(seen),
        "distinct_capacity_values": len(seen),
    }


def mesh_plan(corpus, sim):
    vectors = set(tuple(row["capacity"]) for row in sim.per_step)
    return {
        "run_id": sim.cfg["run_id"],
        "ep_world_size": sim.cfg["ep_world_size"],
        "expert_rank": list(sim.expert_rank),
        "rank_experts": {
            str(rank): list(sim.rank_experts[rank]) for rank in sim.ranks
        },
        "placement_groups": [
            corpus.placement_group[expert] for expert in range(sim.cfg["num_experts"])
        ],
        "rank_bucket_by_step": [
            {
                "step": row["step"],
                "rank_bucket": {
                    str(rank): row["rank_bucket"][rank] for rank in sim.ranks
                },
            }
            for row in sim.per_step
        ],
        "expert_shape_matrix": len(vectors) * len(sim.layers),
    }


def dispatch_ledger(corpus, sim):
    steps = [
        {
            "step": row["step"],
            "accepted_count": list(row["accepted_count"]),
            "padded_slots": row["padded_slots"],
        }
        for row in sim.per_step
    ]
    return {
        "run_id": sim.cfg["run_id"],
        "steps": steps,
        "total_accepted": sum(sum(row["accepted_count"]) for row in sim.per_step),
        "total_padded_slots": sum(row["padded_slots"] for row in sim.per_step),
    }


def drop_ledger(corpus, sim):
    decimals = corpus.float_decimals
    steps = [
        {
            "step": row["step"],
            "dropped_tokens": row["dropped"],
            "dropped_token_mass": rnd(row["dropped_mass"], decimals),
        }
        for row in sim.per_step
    ]
    return {
        "run_id": sim.cfg["run_id"],
        "steps": steps,
        "dropped_tokens": sum(row["dropped"] for row in sim.per_step),
        "dropped_token_mass": rnd(
            math.fsum(row["dropped_mass"] for row in sim.per_step), decimals
        ),
        "drop_rate": sim.drop_rate(),
        "steps_with_drops": [row["step"] for row in sim.per_step if row["dropped"]],
    }


def alltoall_ledger(corpus, sim):
    steps = [
        {
            "step": row["step"],
            "alltoall_bucket": row["alltoall_bucket"],
            "payload_slots": row["payload_slots"],
            "rank_bucket_spread": row["spread"],
        }
        for row in sim.per_step
    ]
    return {
        "run_id": sim.cfg["run_id"],
        "ep_world_size": sim.cfg["ep_world_size"],
        "steps": steps,
        "uniform_steps": [row["step"] for row in sim.per_step if row["spread"] == 0],
        "total_payload_slots": sum(row["payload_slots"] for row in sim.per_step),
    }


def guard_key_index(corpus, sim):
    keys_by_slot = {
        slot: sorted(keys) for slot, keys in sorted(sim.keys_by_slot.items())
    }
    distinct = set()
    for keys in keys_by_slot.values():
        distinct.update(keys)
    final = {}
    for name in sim.code_objects:
        dims = sorted(
            dim for dim in sim.guarded_dims(name) if sim.dynamic_final[(name, dim)]
        )
        final[name] = dims
    return {
        "run_id": sim.cfg["run_id"],
        "keys_by_slot": keys_by_slot,
        "distinct_key_count": len(distinct),
        "specialized_zero_one_keys": sorted(sim.specialized_keys),
        "dynamic_dims_final": final,
    }


def recompile_report(corpus, sim):
    events = [
        {
            "step": event["step"],
            "code_object": event["code_object"],
            "rank": event["rank"],
            "guard_key": event["guard_key"],
            "guard_delta": event["guard_delta"],
            "evicted_key": event["evicted_key"],
        }
        for event in sim.recompile_events
    ]
    return {
        "run_id": sim.cfg["run_id"],
        "warmup_bound": sim.cfg["warmup_bound"],
        "recompile_events": events,
        "total_recompiles": sim.total_recompiles(),
        "recompiles_after_warmup": sim.recompiles_after_warmup(),
        "first_step_over_budget": sim.first_step_over_budget(),
        "evictions": sim.evictions,
        "recompiles_by_step": [
            {"step": row["step"], "count": len(row["events"])} for row in sim.per_step
        ],
    }


def graph_break_ledger(corpus, sim):
    counts = {cause: 0 for cause in corpus.break_causes}
    for row in sim.per_step:
        for cause in row["causes"]:
            counts[cause] += 1
    return {
        "run_id": sim.cfg["run_id"],
        "cause_order": list(corpus.break_causes),
        "per_cause_counts": counts,
        "steps": [
            {"step": row["step"], "causes": list(row["causes"])} for row in sim.per_step
        ],
        "total_breaks": sum(len(row["causes"]) for row in sim.per_step),
        "clean_steps": [row["step"] for row in sim.per_step if not row["causes"]],
    }


def cudagraph_report(corpus, sim):
    return {
        "run_id": sim.cfg["run_id"],
        "compile_mode": sim.cfg["compile_mode"],
        "capture_attempts": sim.capture_attempts,
        "captures": sim.capture_success,
        "failure_causes": dict(sim.failure_causes),
        "steps": [
            {
                "step": row["step"],
                "captured": row["captured"],
                "pool_bytes": row["pool_bytes"],
                "pool_peak_bytes": row["pool_peak_bytes"],
            }
            for row in sim.per_step
        ],
        "final_pool_peak_bytes": sim.per_step[-1]["pool_peak_bytes"],
        "reset_steps": list(sim.cfg["reset_steps"]),
    }


def host_memory_report(corpus, sim):
    steps = [
        {
            "step": row["step"],
            "host_bytes": row["host_bytes"],
            "host_headroom_bytes": row["headroom"],
            "cache_entries": row["cache_entries"],
            "guard_closures": row["guard_closures"],
        }
        for row in sim.per_step
    ]
    smallest = sim.min_headroom()
    return {
        "run_id": sim.cfg["run_id"],
        "host_ceiling_bytes": corpus.host_ceiling_bytes,
        "steps": steps,
        "min_host_headroom_bytes": smallest,
        "peak_host_bytes": max(row["host_bytes"] for row in sim.per_step),
        "steps_over_ceiling": [
            row["step"] for row in sim.per_step if row["headroom"] < 0
        ],
        "memory_gate_met": smallest >= 0,
    }


def steptime_report(corpus, sim):
    td = corpus.time_decimals
    speedup, compiled_tail, eager_tail = sim.speedup()
    gated = sim.gated_steps()
    total_compile = math.fsum(row["compile_us"] for row in sim.per_step)
    amortized = rnd(total_compile / len(gated), td) if gated else 0.0
    return {
        "run_id": sim.cfg["run_id"],
        "steps": [
            {
                "step": row["step"],
                "step_us": row["step_us"],
                "compute_us": row["compute_us"],
                "alltoall_us": row["alltoall_us"],
                "compile_us": row["compile_us"],
                "capture_us": row["capture_us"],
                "bubble_us": row["bubble_us"],
                "eager_step_us": row["eager_step_us"],
            }
            for row in sim.per_step
        ],
        "gated_step_range": [sim.cfg["warmup_bound"] + 1, sim.steps],
        "compiled_tail_us": compiled_tail,
        "eager_tail_us": eager_tail,
        "speedup": speedup,
        "min_speedup": corpus.min_speedup,
        "speedup_gate_met": speedup >= corpus.min_speedup,
        "amortized_compile_us": amortized,
    }


def warmup_profile(corpus, sim):
    figures = warmup_profile_figures(sim)
    record = {"run_id": sim.cfg["run_id"], "warmup_bound": sim.cfg["warmup_bound"]}
    record.update(figures)
    return record


def aux_loss_trace(corpus, sim):
    decimals = corpus.float_decimals
    steps = []
    dispersions = []
    for row in sim.per_step:
        balance = row["balance"]
        steps.append(
            {
                "step": row["step"],
                "aux_loss": balance["aux_loss"],
                "expert_utilization": list(balance["expert_utilization"]),
                "load_dispersion": balance["load_dispersion"],
                "empty_experts": list(balance["empty_experts"]),
            }
        )
        if balance["load_dispersion"] is not None:
            dispersions.append(balance["load_dispersion"])
    mean = rnd(math.fsum(dispersions) / len(dispersions), decimals) if dispersions else 0.0
    return {
        "run_id": sim.cfg["run_id"],
        "aux_loss_weight": sim.cfg["aux_loss_weight"],
        "steps": steps,
        "aux_loss_total": rnd(
            math.fsum(row["balance"]["aux_loss"] for row in sim.per_step), decimals
        ),
        "steps_with_empty_experts": [
            row["step"] for row in sim.per_step if row["balance"]["empty_experts"]
        ],
        "mean_load_dispersion": mean,
    }


def loss_curve(corpus, sim):
    decimals = corpus.float_decimals
    steps = [
        {
            "step": row["step"],
            "loss": row["loss"],
            "eager_loss": row["eager_loss"],
            "signed_gap": rnd(row["loss"] - row["eager_loss"], decimals),
        }
        for row in sim.per_step
    ]
    opening = sim.per_step[0]["loss"]
    return {
        "run_id": sim.cfg["run_id"],
        "steps": steps,
        "closing_loss": sim.closing_loss(),
        "opening_loss": opening,
        "minimum_loss": min(row["loss"] for row in sim.per_step),
        "steps_above_opening": [
            row["step"] for row in sim.per_step if row["loss"] > opening
        ],
    }


def gradient_ledger(corpus, sim):
    decimals = corpus.float_decimals
    steps = [
        {
            "step": row["step"],
            "expert_outputs": [rnd(value, decimals) for value in row["numeric"]["outputs"]],
            "expert_partials": [
                rnd(value, decimals) for value in row["numeric"]["partials"]
            ],
            "step_signal": rnd(row["numeric"]["signal"], decimals),
            "gradients": [rnd(value, decimals) for value in row["numeric"]["gradients"]],
        }
        for row in sim.per_step
    ]
    return {
        "run_id": sim.cfg["run_id"],
        "steps": steps,
        "folded_signal": rnd(sim.folded_signal, decimals),
        "final_params": [rnd(value, decimals) for value in sim.params],
        "accumulation_order": ["slot_ascending", "expert_index_ascending"],
    }


def optimizer_trace(corpus, sim):
    decimals = corpus.float_decimals
    steps = [
        {
            "step": row["step"],
            "scaled_norm": rnd(row["numeric"]["scaled_norm"], decimals),
            "clip_reference": rnd(row["numeric"]["clip_reference"], decimals),
            "clip_factor": rnd(row["numeric"]["clip_factor"], decimals),
            "clipped": bool(row["numeric"]["clipped"]),
        }
        for row in sim.per_step
    ]
    clipped = [row["step"] for row in sim.per_step if row["numeric"]["clipped"]]
    return {
        "run_id": sim.cfg["run_id"],
        "loss_scale": sim.cfg["loss_scale"],
        "clip_threshold": sim.cfg["clip_threshold"],
        "learning_rate": sim.cfg["learning_rate"],
        "steps": steps,
        "clipped_steps": clipped,
        "clipped_step_count": len(clipped),
    }


def convergence_report(corpus, sim):
    decimals = corpus.float_decimals
    losses = [row["loss"] for row in sim.per_step]
    window = corpus.slope_window
    if window > 1 and len(losses) >= window:
        slope = rnd((losses[-1] - losses[-window]) / float(window - 1), decimals)
    else:
        slope = rnd(losses[-1] - losses[0], decimals)
    closing = sim.closing_loss()
    baseline = sim.baseline_closing_loss()
    deviation = sim.relative_deviation()
    holds = deviation <= corpus.parity_band
    verdict = (
        "met"
        if holds and slope <= corpus.max_slope and closing <= corpus.target_loss
        else "unmet"
    )
    return {
        "run_id": sim.cfg["run_id"],
        "slope_window": window,
        "windowed_slope": slope,
        "closing_loss": closing,
        "baseline_closing_loss": baseline,
        "relative_deviation": deviation,
        "parity_band": corpus.parity_band,
        "parity_holds": holds,
        "target_loss": corpus.target_loss,
        "verdict": verdict,
    }


def baseline_parity(corpus, sim):
    decimals = corpus.float_decimals
    steps = []
    for row in sim.per_step:
        steps.append(
            {
                "step": row["step"],
                "relative_deviation": relative_deviation(
                    row["loss"], row["eager_loss"], decimals
                ),
            }
        )
    largest = max(entry["relative_deviation"] for entry in steps)
    attaining = None
    if largest > 0.0:
        for entry in steps:
            if entry["relative_deviation"] == largest:
                attaining = entry["step"]
                break
    return {
        "run_id": sim.cfg["run_id"],
        "steps": steps,
        "max_relative_deviation": largest,
        "max_deviation_step": attaining,
        "parity_band": corpus.parity_band,
        "parity_holds": largest <= corpus.parity_band,
        "steps_outside_band": [
            entry["step"]
            for entry in steps
            if entry["relative_deviation"] > corpus.parity_band
        ],
    }


def settlement_report(corpus, sweep, settled_sim, order):
    cfg = sweep.cfg
    entry = sweep.settled()
    candidate = entry["candidate"]
    figures = gate_figures(corpus, settled_sim)
    changed = []
    for setting in ("capacity_bucket", "capacity_factor", "compile_mode", "mark_dynamic"):
        if cfg[setting] != candidate[setting]:
            changed.append(
                {"setting": setting, "from": cfg[setting], "to": candidate[setting]}
            )
    rejected = [item for item in sweep.evaluated if item["violations"]]
    return {
        "run_id": cfg["run_id"],
        "probe_steps": sweep.probe_steps,
        "candidates_evaluated": len(sweep.evaluated) + len(sweep.prefiltered),
        "prefiltered_count": len(sweep.prefiltered),
        "rejected_count": len(rejected),
        "admissible_count": len(sweep.admissible()),
        "settled_configuration": {
            "capacity_factor": candidate["capacity_factor"],
            "capacity_bucket": candidate["capacity_bucket"],
            "mark_dynamic": list(candidate["mark_dynamic"]),
            "compile_mode": candidate["compile_mode"],
        },
        "settled_gate_figures": figures,
        "changed_settings": changed,
        "gates_met": {
            "speedup": figures["speedup"] >= corpus.min_speedup,
            "memory": figures["min_host_headroom_bytes"] >= 0,
            "recompile_budget": figures["recompiles_after_warmup"]
            <= corpus.recompile_budget,
            "convergence": figures["relative_deviation"] <= corpus.parity_band,
        },
    }


def rejection_ledger(corpus, sweep, order):
    rejected = []
    for entry in sorted(sweep.evaluated, key=lambda item: item["label"]):
        if not entry["violations"]:
            continue
        rejected.append(
            {
                "candidate": entry["label"],
                "cause": first_violated(order, entry["violations"]),
                "all_violations": [
                    cause for cause in order if cause in entry["violations"]
                ],
            }
        )
    return {
        "cause_order": list(order),
        "per_cause_counts": sweep.cause_counts(order),
        "rejected": rejected,
        "prefiltered": sorted(sweep.prefiltered, key=lambda item: item["candidate"]),
        "admissible_candidates": sorted(
            entry["label"] for entry in sweep.admissible()
        ),
    }


def sensitivity(corpus, cfg, sweep, tie_order, routing_cache):
    decimals = corpus.float_decimals
    settled = sweep.settled()["candidate"]
    base = merge_candidate(cfg, settled)
    horizon = min(sweep.probe_steps, cfg["steps"])
    rows = []
    for item in corpus.candidates.get("perturbations", []):
        setting = item["setting"]
        delta = item["delta"]
        if setting not in base:
            raise PlannerError(
                "capacity_candidates.json perturbs an unknown setting: %s" % setting
            )
        probe = dict(base)
        probe[setting] = base[setting] + delta
        sim = Simulation(
            corpus, probe, tie_order, horizon=horizon, routing_cache=routing_cache
        )
        figures = gate_figures(corpus, sim)
        rows.append(
            {
                "setting": setting,
                "delta": delta,
                "speedup_margin": rnd(figures["speedup"] - corpus.min_speedup, decimals),
                "headroom_margin": figures["min_host_headroom_bytes"],
                "recompile_margin": corpus.recompile_budget
                - figures["recompiles_after_warmup"],
            }
        )
    return {
        "run_id": cfg["run_id"],
        "probe_steps": sweep.probe_steps,
        "perturbations": rows,
        "negative_speedup_margins": sum(
            1 for row in rows if row["speedup_margin"] < 0.0
        ),
        "negative_headroom_margins": sum(
            1 for row in rows if row["headroom_margin"] < 0
        ),
    }


def audit_statistics(corpus, deployed, settled):
    decimals = corpus.float_decimals
    deployed_bound = deployed.cfg["warmup_bound"]
    settled_bound = settled.cfg["warmup_bound"]
    deployed_caps = set()
    for row in deployed.per_step:
        deployed_caps.update(row["capacity"])
    settled_buckets = set()
    for row in settled.per_step:
        settled_buckets.update(row["rank_bucket"].values())
    deployed_assignments = sum(row["total_assignments"] for row in deployed.per_step)
    deployed_dropped = sum(row["dropped"] for row in deployed.per_step)
    settled_dropped = sum(row["dropped"] for row in settled.per_step)
    settled_tokens = sum(row["tokens"] for row in settled.per_step)
    deployed_failures = deployed.capture_attempts - deployed.capture_success
    return {
        "deployed_recompiles_total": deployed.total_recompiles(),
        "settled_recompiles_after_warmup": settled.recompiles_after_warmup(),
        "deployed_distinct_capacity_values": len(deployed_caps),
        "settled_distinct_rank_buckets": len(settled_buckets),
        "deployed_drop_rate_assignment_denominator": (
            rnd(deployed_dropped / float(deployed_assignments), decimals)
            if deployed_assignments
            else 0.0
        ),
        "settled_drop_rate_token_denominator": (
            rnd(settled_dropped / float(settled_tokens), decimals)
            if settled_tokens
            else 0.0
        ),
        "deployed_break_steps_inclusive_warmup": sum(
            1
            for row in deployed.per_step
            if row["causes"] and row["step"] <= deployed_bound
        ),
        "settled_break_steps_exclusive_warmup": sum(
            1
            for row in settled.per_step
            if row["causes"] and row["step"] > settled_bound
        ),
        "deployed_mean_host_bytes": rnd(
            math.fsum(row["host_bytes"] for row in deployed.per_step)
            / len(deployed.per_step),
            decimals,
        ),
        "settled_peak_host_bytes": max(row["host_bytes"] for row in settled.per_step),
        "deployed_capture_failure_ratio": (
            rnd(deployed_failures / float(deployed.capture_attempts), decimals)
            if deployed.capture_attempts
            else 0.0
        ),
        "settled_capture_success_ratio": (
            rnd(settled.capture_success / float(settled.capture_attempts), decimals)
            if settled.capture_attempts
            else 0.0
        ),
        "deployed_empty_expert_step_count": sum(
            1 for row in deployed.per_step if row["balance"]["empty_experts"]
        ),
        "settled_empty_expert_slot_count": sum(
            len(row["balance"]["empty_experts"]) for row in settled.per_step
        ),
        "deployed_unique_guard_keys_router_only": unique_guard_keys(deployed, "router"),
        "settled_unique_guard_keys_moe_only": unique_guard_keys(settled, "moe"),
        "deployed_token_total": sum(row["tokens"] for row in deployed.per_step),
    }


def unique_guard_keys(sim, which):
    triples = set()
    for slot, keys in sim.keys_by_slot.items():
        name = slot.split("@")[0]
        if which == "router" and name != "router":
            continue
        if which == "moe" and name == "router":
            continue
        for key in keys:
            triples.add((slot, key))
    return len(triples)


def deployed_departures(corpus, cfg):
    rows = []
    for setting, bound in sorted(corpus.bounds.items()):
        if setting not in cfg:
            raise PlannerError(
                "contract_bounds.json names a setting absent from the configuration: %s"
                % setting
            )
        value = cfg[setting]
        departs = False
        if "allowed_values" in bound and value not in bound["allowed_values"]:
            departs = True
        if "minimum" in bound and value < bound["minimum"]:
            departs = True
        if "maximum" in bound and value > bound["maximum"]:
            departs = True
        if departs:
            rows.append(
                {
                    "setting": setting,
                    "value": value,
                    "policy": bound["policy"],
                    "revision": corpus.revision_in_force(bound["policy"]),
                }
            )
    return rows


def deployed_diagnosis(corpus, cfg, deployed, published):
    decimals = corpus.float_decimals
    replayed = {
        "speedup": deployed.speedup()[0],
        "closing_loss": deployed.closing_loss(),
        "drop_rate": deployed.drop_rate(),
        "min_host_headroom_bytes": deployed.min_headroom(),
        "total_recompiles": deployed.total_recompiles(),
        "recompiles_after_warmup": deployed.recompiles_after_warmup(),
    }
    comparison = {}
    for name in sorted(replayed):
        if name not in published:
            raise PlannerError(
                "deployed_run_summary.json does not publish the figure: %s" % name
            )
        comparison[name] = {
            "published": published[name],
            "replayed": replayed[name],
            "signed_delta": rnd(published[name] - replayed[name], decimals),
        }
    departures = deployed_departures(corpus, cfg)
    figures = gate_figures(corpus, deployed)
    violations = violations_of(corpus, cfg, figures)
    return {
        "run_id": cfg["run_id"],
        "published_vs_replayed": comparison,
        "departing_settings": departures,
        "capture_failure_causes": dict(deployed.failure_causes),
        "first_step_over_budget": deployed.first_step_over_budget(),
        "admissible": not departures and not violations,
        "published_agrees_with_replay": all(
            entry["signed_delta"] == 0.0 for entry in comparison.values()
        ),
    }


def validation_report(corpus, deployed, published, records):
    decimals = corpus.float_decimals
    replayed = {
        "speedup": deployed.speedup()[0],
        "closing_loss": deployed.closing_loss(),
        "drop_rate": deployed.drop_rate(),
        "min_host_headroom_bytes": deployed.min_headroom(),
        "recompiles_after_warmup": deployed.recompiles_after_warmup(),
    }
    residuals = {}
    for name in sorted(replayed):
        residuals[name] = rnd(published[name] - replayed[name], decimals)
    counts = {}
    for name in STAGE_RECORDS + REPLAY_RECORDS[:-1]:
        record = records[name]
        if isinstance(record.get("steps"), list):
            counts[name] = len(record["steps"])
        else:
            counts[name] = len(record)
    largest = max((abs(value) for value in residuals.values()), default=0.0)
    return {
        "residuals": residuals,
        "record_counts": counts,
        "max_absolute_residual": rnd(largest, decimals),
        "artifact_count": len(counts),
        "float_decimals": corpus.float_decimals,
        "time_decimals": corpus.time_decimals,
    }


# -------------------------------------------------------------------- pipeline


class Resolution(object):
    def __init__(self, corpus):
        key, key_matches, key_total, key_configs = resolve_tie_break_key(corpus)
        order, order_matches, order_total, order_configs = resolve_precedence_order(
            corpus, key
        )
        self.tie_break_key = key
        self.tie_break_matches = key_matches
        self.tie_break_candidates = key_total
        self.precedence_order = order
        self.precedence_matches = order_matches
        self.precedence_candidates = order_total
        self.sealed_configs = sorted(set(key_configs) | set(order_configs))

    def record(self):
        return {
            "tie_break_key": list(self.tie_break_key),
            "tie_break_matches": self.tie_break_matches > 0,
            "tie_break_candidates_enumerated": self.tie_break_candidates,
            "precedence_order": list(self.precedence_order),
            "precedence_matches": self.precedence_matches > 0,
            "precedence_candidates_enumerated": self.precedence_candidates,
            "sealed_configs": list(self.sealed_configs),
        }


class Pipeline(object):
    """The whole plan for one corpus: the deployed replay and the settlement."""

    def __init__(self, corpus, cfg):
        self.corpus = corpus
        self.cfg = cfg
        self.resolution = Resolution(corpus)
        self.tie_order = self.resolution.tie_break_key
        self.cache = {}
        self.sweep = Sweep(corpus, cfg, self.tie_order, routing_cache=self.cache)
        self.deployed = self.sweep.full
        self.settled_candidate = self.sweep.settled()["candidate"]
        self.settled_cfg = merge_candidate(cfg, self.settled_candidate)
        self.settled = Simulation(
            corpus, self.settled_cfg, self.tie_order, routing_cache=self.cache
        )

    def records(self):
        corpus = self.corpus
        deployed = self.deployed
        settled = self.settled
        order = self.resolution.precedence_order
        published = require_table(corpus.tables, "deployed_run_summary.json")["published"]
        records = {}
        records["route_plan.json"] = route_plan(corpus, deployed, self.tie_order)
        records["capacity_plan.json"] = capacity_plan(corpus, deployed)
        records["mesh_plan.json"] = mesh_plan(corpus, deployed)
        records["dispatch_ledger.json"] = dispatch_ledger(corpus, deployed)
        records["drop_ledger.json"] = drop_ledger(corpus, deployed)
        records["alltoall_ledger.json"] = alltoall_ledger(corpus, deployed)
        records["guard_key_index.json"] = guard_key_index(corpus, deployed)
        records["recompile_report.json"] = recompile_report(corpus, deployed)
        records["graph_break_ledger.json"] = graph_break_ledger(corpus, deployed)
        records["cudagraph_report.json"] = cudagraph_report(corpus, deployed)
        records["host_memory_report.json"] = host_memory_report(corpus, deployed)
        records["steptime_report.json"] = steptime_report(corpus, deployed)
        records["warmup_profile.json"] = warmup_profile(corpus, deployed)
        records["sealed_policy_resolution.json"] = self.resolution.record()
        records["aux_loss_trace.json"] = aux_loss_trace(corpus, settled)
        records["loss_curve.json"] = loss_curve(corpus, settled)
        records["gradient_ledger.json"] = gradient_ledger(corpus, settled)
        records["optimizer_trace.json"] = optimizer_trace(corpus, settled)
        records["convergence_report.json"] = convergence_report(corpus, settled)
        records["baseline_parity.json"] = baseline_parity(corpus, settled)
        records["settlement_report.json"] = settlement_report(
            corpus, self.sweep, settled, order
        )
        records["rejection_ledger.json"] = rejection_ledger(corpus, self.sweep, order)
        records["sensitivity.json"] = sensitivity(
            corpus, self.cfg, self.sweep, self.tie_order, self.cache
        )
        records["audit_statistics.json"] = audit_statistics(corpus, deployed, settled)
        records["deployed_diagnosis.json"] = deployed_diagnosis(
            corpus, self.cfg, deployed, published
        )
        records["validation_report.json"] = validation_report(
            corpus, deployed, published, records
        )

        stage = {
            "stage": "dispatch_and_compile",
            "artifact_count": len(STAGE_RECORDS),
            "artifact_sha256": {
                name: digest_of(records[name]) for name in STAGE_RECORDS
            },
        }
        records["stage_manifest.json"] = stage
        stage_digest = hashlib.sha256(canonical_bytes(stage)).hexdigest()
        replay = {
            "stage": "replay_and_settlement",
            "artifact_count": len(REPLAY_RECORDS),
            "artifact_sha256": {
                name: digest_of(records[name]) for name in REPLAY_RECORDS
            },
            "stage_manifest_sha256": stage_digest,
        }
        records["replay_manifest.json"] = replay
        replay_digest = hashlib.sha256(canonical_bytes(replay)).hexdigest()

        settled_configuration = records["settlement_report.json"]["settled_configuration"]
        salt = digest_of(settled_configuration)
        folded = {"replay": replay_digest, "salt": salt, "stage": stage_digest}
        convergence = records["convergence_report.json"]
        records["final_state.json"] = {
            "closing_loss": convergence["closing_loss"],
            "convergence_verdict": convergence["verdict"],
            "deployed_admissible": records["deployed_diagnosis.json"]["admissible"],
            "digest_of_digests": digest_of(folded),
            "first_step_over_budget": records["recompile_report.json"][
                "first_step_over_budget"
            ],
            "precedence_order": list(order),
            "replay_manifest_sha256": replay_digest,
            "settled_configuration": settled_configuration,
            "settlement_salt": salt,
            "speedup": records["settlement_report.json"]["settled_gate_figures"][
                "speedup"
            ],
            "stage_manifest_sha256": stage_digest,
            "tie_break_key": list(self.tie_order),
            "total_artifacts": len(STAGE_RECORDS) + len(REPLAY_RECORDS)
            + len(MANIFEST_RECORDS),
        }
        return records


# ------------------------------------------------------------------- the verbs


def build(data_dir, out_dir):
    tables = load_corpus(data_dir)
    corpus = Corpus(tables)
    cfg = require_config(
        require_table(tables, "deployed_config.json"), "deployed_config.json"
    )
    pipeline = Pipeline(corpus, cfg)
    records = pipeline.records()
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    for name in STAGE_RECORDS + REPLAY_RECORDS + MANIFEST_RECORDS:
        path = os.path.join(out_dir, name)
        with open(path, "wb") as handle:
            handle.write(canonical_bytes(records[name]))
    return records


def load_document(path):
    if not os.path.isfile(path):
        raise PlannerError("document is not a file: %s" % path)
    with open(path, "r", encoding="utf-8") as handle:
        try:
            document = json.load(handle)
        except ValueError as exc:
            raise PlannerError("document is not valid JSON: %s (%s)" % (path, exc))
    if not isinstance(document, dict):
        raise PlannerError("document is not an object: %s" % path)
    extra = sorted(set(document) - {"config", "tables"})
    if extra:
        raise PlannerError("document carries an unexpected key: %s" % extra[0])
    for key in ("config", "tables"):
        if key not in document:
            raise PlannerError("document is missing the required key: %s" % key)
    if not isinstance(document["tables"], dict):
        raise PlannerError("document carries a tables value that is not an object")
    corpus = Corpus(document["tables"])
    cfg = require_config(document["config"], "the document configuration")
    validate_config(cfg, "the document configuration")
    return corpus, cfg


def verb_trace(path):
    corpus, cfg = load_document(path)
    resolution = Resolution(corpus)
    sim = Simulation(corpus, cfg, resolution.tie_break_key)
    return {
        "tie_break_key": list(resolution.tie_break_key),
        "tie_break_matches": resolution.tie_break_matches > 0,
        "guard_key_index": guard_key_index(corpus, sim),
        "recompile_report": recompile_report(corpus, sim),
        "graph_break_ledger": graph_break_ledger(corpus, sim),
        "cudagraph_report": cudagraph_report(corpus, sim),
        "capacity_plan": capacity_plan(corpus, sim),
        "mesh_plan": mesh_plan(corpus, sim),
        "host_memory_report": host_memory_report(corpus, sim),
        "warmup_profile": warmup_profile(corpus, sim),
    }


def verb_replay(path):
    corpus, cfg = load_document(path)
    resolution = Resolution(corpus)
    sim = Simulation(corpus, cfg, resolution.tie_break_key)
    return {
        "tie_break_key": list(resolution.tie_break_key),
        "tie_break_matches": resolution.tie_break_matches > 0,
        "route_plan": route_plan(corpus, sim, resolution.tie_break_key),
        "dispatch_ledger": dispatch_ledger(corpus, sim),
        "drop_ledger": drop_ledger(corpus, sim),
        "alltoall_ledger": alltoall_ledger(corpus, sim),
        "aux_loss_trace": aux_loss_trace(corpus, sim),
        "loss_curve": loss_curve(corpus, sim),
        "gradient_ledger": gradient_ledger(corpus, sim),
        "optimizer_trace": optimizer_trace(corpus, sim),
        "convergence_report": convergence_report(corpus, sim),
        "baseline_parity": baseline_parity(corpus, sim),
        "steptime_report": steptime_report(corpus, sim),
    }


def verb_settle(path):
    corpus, cfg = load_document(path)
    resolution = Resolution(corpus)
    sweep = Sweep(corpus, cfg, resolution.tie_break_key)
    candidate = sweep.settled()["candidate"]
    return {
        "rejection_ledger": rejection_ledger(
            corpus, sweep, resolution.precedence_order
        ),
        "warmup_profile": warmup_profile(corpus, sweep.full),
        "settled_configuration": {
            "capacity_factor": candidate["capacity_factor"],
            "capacity_bucket": candidate["capacity_bucket"],
            "mark_dynamic": list(candidate["mark_dynamic"]),
            "compile_mode": candidate["compile_mode"],
        },
        "probe_steps": sweep.probe_steps,
    }


def verb_resolve(path):
    corpus, _ = load_document(path)
    return Resolution(corpus).record()


USAGE = (
    "usage: moeplan.py build DATA_DIR OUT_DIR\n"
    "       moeplan.py trace CONFIG_DOCUMENT\n"
    "       moeplan.py replay RUN_DOCUMENT\n"
    "       moeplan.py settle CANDIDATE_DOCUMENT\n"
    "       moeplan.py resolve SEALED_DOCUMENT\n"
)


def main(argv):
    if len(argv) < 2:
        sys.stderr.write(USAGE)
        return 2
    verb = argv[1]
    try:
        if verb == "build":
            if len(argv) != 4:
                sys.stderr.write(USAGE)
                return 2
            build(argv[2], argv[3])
            return 0
        if verb in ("trace", "replay", "settle", "resolve"):
            if len(argv) != 3:
                sys.stderr.write(USAGE)
                return 2
            handler = {
                "trace": verb_trace,
                "replay": verb_replay,
                "settle": verb_settle,
                "resolve": verb_resolve,
            }[verb]
            sys.stdout.write(canonical_bytes(handler(argv[2])).decode("utf-8"))
            return 0
        sys.stderr.write("unknown verb: %s\n%s" % (verb, USAGE))
        return 2
    except PlannerError as exc:
        sys.stderr.write("moeplan: %s\n" % exc)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
