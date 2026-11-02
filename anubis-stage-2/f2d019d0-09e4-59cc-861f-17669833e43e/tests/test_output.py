"""Mixture of experts capacity and compile cache planner.

Reference core. Pure standard library. Deterministic.
"""

import hashlib
import json
import math
import os
import struct
import sys
from pathlib import Path

MASK64 = (1 << 64) - 1
E4M3_MAX = 448.0
E4M3_SUBNORMAL_QUANTUM = 2.0 ** -9
E4M3_MIN_NORMAL_EXPONENT = -6

CAUSE_NAMES = (
    "capacity_below_minimum",
    "convergence_band_unmet",
    "drop_tolerance_exceeded",
    "eager_mode_forbidden",
    "memory_ceiling_exceeded",
    "recompile_budget_exceeded",
    "speedup_gate_unmet",
)

TIEBREAK_FIELDS = ("expert_index", "running_load", "placement_rank", "bias_rank")

BREAK_CAUSES = (
    "data_dependent_capacity",
    "dynamic_token_count",
    "token_drop_mask",
    "unbalanced_expert_slice",
    "zero_token_expert",
)


class Xorshift64:
    """Fully specified 64 bit xorshift generator."""

    def __init__(self, seed):
        s = int(seed) & MASK64
        if s == 0:
            s = 0x9E3779B97F4A7C15
        self.state = s

    def next_u64(self):
        x = self.state
        x ^= (x << 13) & MASK64
        x ^= x >> 7
        x ^= (x << 17) & MASK64
        self.state = x & MASK64
        return self.state

    def next_unit(self):
        return (self.next_u64() >> 11) * (2.0 ** -53)


def affinity_bits(token_bits, expert_bits):
    h = 0xCBF29CE484222325
    for part in (token_bits, expert_bits):
        h ^= part & MASK64
        h = (h * 0x100000001B3) & MASK64
        h ^= h >> 29
    x = h & MASK64
    if x == 0:
        x = 0x9E3779B97F4A7C15
    x ^= (x << 13) & MASK64
    x ^= x >> 7
    x ^= (x << 17) & MASK64
    return x & MASK64


def mix64(*parts):
    h = 0xCBF29CE484222325
    for part in parts:
        h ^= int(part) & MASK64
        h = (h * 0x100000001B3) & MASK64
        h ^= h >> 29
    return h & MASK64


def fp32(value):
    return struct.unpack(">f", struct.pack(">f", float(value)))[0]


def bf16(value):
    v = float(value)
    if v != v:
        return v
    bits = struct.unpack(">I", struct.pack(">f", v))[0]
    lsb = (bits >> 16) & 1
    bits = (bits + 0x7FFF + lsb) & 0xFFFFFFFF
    return struct.unpack(">f", struct.pack(">I", bits & 0xFFFF0000))[0]


def fp8_e4m3(value):
    v = float(value)
    if v != v:
        return v
    sign = -1.0 if v < 0.0 else 1.0
    a = abs(v)
    if a == 0.0:
        return 0.0
    mant, exp2 = math.frexp(a)
    exponent = exp2 - 1
    if exponent < E4M3_MIN_NORMAL_EXPONENT:
        quantum = E4M3_SUBNORMAL_QUANTUM
    else:
        quantum = 2.0 ** (exponent - 3)
    scaled = a / quantum
    floor_value = math.floor(scaled)
    remainder = scaled - floor_value
    if remainder > 0.5:
        floor_value += 1.0
    elif remainder == 0.5 and (int(floor_value) % 2) == 1:
        floor_value += 1.0
    rounded = floor_value * quantum
    if rounded > E4M3_MAX:
        rounded = E4M3_MAX
    return sign * rounded


def round_half_even(value, levels):
    scaled = float(value) * float(levels)
    floor_value = math.floor(scaled)
    remainder = scaled - floor_value
    if remainder > 0.5:
        floor_value += 1.0
    elif remainder == 0.5 and (int(floor_value) % 2) == 1:
        floor_value += 1.0
    return floor_value / float(levels)


def rd(value, decimals):
    v = float(value)
    if v != v or v in (float("inf"), float("-inf")):
        return v
    out = round(v, int(decimals))
    if out == 0.0:
        return 0.0
    return out


def canonical_bytes(obj):
    return (json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def sha256_hex(payload):
    return hashlib.sha256(payload).hexdigest()


def digest_of(obj):
    return sha256_hex(canonical_bytes(obj))


def write_json(path, obj):
    data = canonical_bytes(obj)
    with open(path, "wb") as handle:
        handle.write(data)
    return sha256_hex(data)


def read_json(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def read_text(path):
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def read_csv(path):
    rows = []
    header = None
    for line in read_text(path).splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parts = [cell.strip() for cell in stripped.split(",")]
        if header is None:
            header = parts
            continue
        rows.append(dict(zip(header, parts)))
    return rows


def read_jsonl(path):
    out = []
    for line in read_text(path).splitlines():
        stripped = line.strip()
        if stripped:
            out.append(json.loads(stripped))
    return out


def ceil_div(numerator, denominator):
    return -((-int(numerator)) // int(denominator))


# ---------------------------------------------------------------- corpus load


class Corpus(object):
    """Everything the planner reads from a data directory."""

    def __init__(self, data_dir):
        base = str(data_dir)
        self.base = base
        self.tolerances = read_json(os.path.join(base, "validation_tolerances.json"))
        self.decimals = int(self.tolerances["float_decimals"])
        self.time_decimals = int(self.tolerances["time_decimals"])
        self.run_config = read_json(os.path.join(base, "sample_run_config.json"))
        self.calibration_config = read_json(os.path.join(base, "calibration_config.json"))
        self.deployed_config = read_json(os.path.join(base, "deployed_config.json"))
        self.topology = read_json(os.path.join(base, "model_topology.json"))
        self.candidates = read_json(os.path.join(base, "capacity_candidates.json"))
        self.convergence_gates = read_json(os.path.join(base, "convergence_gates.json"))
        self.steptime_gates = read_json(os.path.join(base, "steptime_gates.json"))
        self.memory_gates = read_json(os.path.join(base, "memory_gates.json"))
        self.warmup_windows = read_json(os.path.join(base, "warmup_windows.json"))
        self.rank_inventory = read_json(os.path.join(base, "ep_rank_inventory.json"))
        self.probes = read_json(os.path.join(base, "probe_configurations.json"))
        self.sealed_precedence = read_json(os.path.join(base, "sealed_precedence_digests.json"))
        self.sealed_tiebreak = read_json(os.path.join(base, "sealed_tiebreak_digests.json"))
        self.revisions = read_json(os.path.join(base, "revision_register.json"))
        self.bounds = read_json(os.path.join(base, "contract_bounds.json"))
        self.deployed_summary = read_json(os.path.join(base, "deployed_run_summary.json"))
        self.deployed_mesh = read_json(os.path.join(base, "deployed_mesh_dump.json"))
        self.eager_baseline = read_json(os.path.join(base, "eager_baseline.json"))
        self.expert_cost = read_csv(os.path.join(base, "expert_cost_table.csv"))
        self.expert_bias = read_csv(os.path.join(base, "expert_bias_table.csv"))
        self.expert_placement = read_csv(os.path.join(base, "expert_placement.csv"))
        self.compile_cost = read_csv(os.path.join(base, "compile_cost_table.csv"))
        self.capture_cost = read_csv(os.path.join(base, "capture_cost_table.csv"))
        self.alltoall_cost = read_csv(os.path.join(base, "alltoall_cost_table.csv"))
        self.memory_slots = read_csv(os.path.join(base, "memory_slot_table.csv"))
        self.pool_blocks = read_csv(os.path.join(base, "pool_block_table.csv"))
        self.seq_schedule = read_csv(os.path.join(base, "seq_length_schedule.csv"))
        self.rank_affinity = read_csv(os.path.join(base, "rank_affinity.csv"))
        self.break_catalog = read_csv(os.path.join(base, "graph_break_catalog.csv"))
        self.calibration_parity = read_jsonl(os.path.join(base, "calibration_parity.jsonl"))
        self.deployed_compile_log = read_jsonl(os.path.join(base, "deployed_compile_log.jsonl"))
        self.deployed_step_timeline = read_jsonl(os.path.join(base, "deployed_step_timeline.jsonl"))
        self.deployed_guard_dump = read_jsonl(os.path.join(base, "deployed_guard_dump.jsonl"))
        self.deployed_alltoall = read_jsonl(os.path.join(base, "deployed_alltoall_trace.jsonl"))
        self.deployed_memory = read_csv(os.path.join(base, "deployed_memory_trace.csv"))
        self.token_batches = read_jsonl(os.path.join(base, "token_batches.jsonl"))


def effective_policy(revision_register, policy_name):
    """Revision in force for a policy: highest effective_order among applied entries."""
    best = None
    for entry in revision_register["revisions"]:
        if entry["policy"] != policy_name:
            continue
        if entry["status"] != "applied":
            continue
        if best is None or int(entry["effective_order"]) > int(best["effective_order"]):
            best = entry
    if best is None:
        raise ValueError("no revision in force for policy " + str(policy_name))
    return best


def table_lookup(rows, key_field, key_value, value_field, cast=float):
    for row in rows:
        if row[key_field] == str(key_value):
            return cast(row[value_field])
    raise KeyError(str(key_field) + "=" + str(key_value))


# ------------------------------------------------------------------ run spec


class RunSpec(object):
    """A configuration bound to the shipped tables."""

    def __init__(self, config, corpus):
        self.config = dict(config)
        self.corpus = corpus
        self.decimals = corpus.decimals
        self.time_decimals = corpus.time_decimals
        self.run_id = str(config["run_id"])
        self.num_experts = int(config["num_experts"])
        self.top_k = int(config["top_k"])
        self.ep_world_size = int(config["ep_world_size"])
        self.steps = int(config["steps"])
        self.warmup_bound = int(config["warmup_bound"])
        self.capacity_factor = float(config["capacity_factor"])
        self.capacity_bucket = int(config["capacity_bucket"])
        self.min_capacity = int(config["min_capacity"])
        self.cache_size_limit = int(config["cache_size_limit"])
        self.promotion_threshold = int(config["promotion_threshold"])
        self.dynamic_promotion_enabled = bool(config["dynamic_promotion_enabled"])
        self.expert_bias_enabled = bool(config["expert_bias_enabled"])
        self.router_jitter_slots = int(config["router_jitter_slots"])
        self.compile_mode = str(config["compile_mode"])
        self.mark_dynamic = tuple(sorted(config["mark_dynamic"]))
        self.loss_scale = float(config["loss_scale"])
        self.learning_rate = float(config["learning_rate"])
        self.clip_threshold = float(config["clip_threshold"])
        self.aux_loss_weight = float(config["aux_loss_weight"])
        self.reset_steps = tuple(sorted(int(v) for v in config["reset_steps"]))
        self.seed = int(config["seed"])
        profile = str(config["seq_profile"])
        rows = [r for r in corpus.seq_schedule if r["profile"] == profile]
        if not rows:
            raise ValueError("no sequence schedule for profile " + profile)
        self.seq_lengths = [int(r["tokens"]) for r in sorted(rows, key=lambda r: int(r["step"]))]
        self.moe_layer_indices = [int(v) for v in config["moe_layer_indices"]]

        topo = corpus.topology
        self.jitter_scale = float(topo["router"]["jitter_scale"])
        self.quantization_levels = int(topo["router"]["quantization_levels"])
        self.base_loss = float(topo["surrogate"]["base_loss"])
        self.signal_weight = float(topo["surrogate"]["signal_weight"])
        self.decay_rate = float(topo["surrogate"]["decay_rate"])
        self.d_model = int(topo["d_model"])
        self.d_ff = int(topo["d_ff"])

        self.bias_gain = [
            table_lookup(corpus.expert_bias, "expert_index", e, "bias_gain")
            for e in range(self.num_experts)
        ]
        self.cost_weight = [
            table_lookup(corpus.expert_cost, "expert_index", e, "cost_weight")
            for e in range(self.num_experts)
        ]
        self.kernel_us = [
            table_lookup(corpus.expert_cost, "expert_index", e, "kernel_us_per_slot")
            for e in range(self.num_experts)
        ]
        self.placement_group = [
            int(table_lookup(corpus.expert_placement, "expert_index", e, "placement_group", int))
            for e in range(self.num_experts)
        ]
        self.bias_rank = self._bias_rank()
        self.expert_rank = self._place_experts()
        self.rank_experts = {}
        for e in range(self.num_experts):
            self.rank_experts.setdefault(self.expert_rank[e], []).append(e)
        for key in self.rank_experts:
            self.rank_experts[key].sort()

    def _bias_rank(self):
        return [int(math.floor(self.bias_gain[e] * 10.0)) for e in range(self.num_experts)]

    def _place_experts(self):
        world = self.ep_world_size
        if self.num_experts % world != 0:
            raise ValueError("expert count must divide across the mesh")
        block = self.num_experts // world
        rows = [
            row for row in self.corpus.rank_affinity
            if int(row["ep_world_size"]) == world
        ]
        if len(rows) != world:
            raise ValueError("rank affinity table does not cover world size " + str(world))
        rank_order = [int(row["rank"]) for row in sorted(rows, key=lambda r: int(r["group_order"]))]
        ordered = sorted(range(self.num_experts), key=lambda e: (self.placement_group[e], e))
        placement = [0] * self.num_experts
        for index, expert in enumerate(ordered):
            placement[expert] = rank_order[index // block]
        return placement

    def tokens_at(self, step):
        return self.seq_lengths[(step - 1) % len(self.seq_lengths)]

    def step_draws(self, step):
        rng = Xorshift64(mix64(self.seed, step))
        count = self.tokens_at(step)
        token_salt = [rng.next_unit() for _ in range(count)]
        expert_phase = [rng.next_unit() for _ in range(self.num_experts)]
        if self.expert_bias_enabled:
            bias_draw = [rng.next_unit() for _ in range(self.num_experts)]
        else:
            bias_draw = [0.5] * self.num_experts
        jitter = [rng.next_unit() for _ in range(self.router_jitter_slots)]
        return token_salt, expert_phase, bias_draw, jitter


# -------------------------------------------------------------------- router


def route_step(spec, step, tiebreak_order):
    """Top k dispatch for one step. Returns a routing record."""
    decimals = spec.decimals
    token_salt, expert_phase, bias_draw, jitter = spec.step_draws(step)
    count = len(token_salt)
    experts = spec.num_experts
    bias = []
    for e in range(experts):
        if spec.expert_bias_enabled:
            bias.append(rd((bias_draw[e] * 2.0 - 1.0) * spec.bias_gain[e], decimals))
        else:
            bias.append(0.0)

    running_load = [0] * experts
    assignments = []
    tie_events = []
    quantized_rows = []
    for i in range(count):
        token_bits = int(token_salt[i] * (2.0 ** 52))
        row = []
        for e in range(experts):
            expert_bits = int(expert_phase[e] * (2.0 ** 52))
            affinity = affinity_bits(token_bits, expert_bits)
            base = rd((affinity >> 11) * 2.220446049250313e-16 - 1.0, decimals)
            if spec.router_jitter_slots > 0:
                slot = (i + e) % spec.router_jitter_slots
                jit = rd((jitter[slot] * 2.0 - 1.0) * spec.jitter_scale, decimals)
            else:
                jit = 0.0
            logit = rd(base + bias[e] + jit, decimals)
            row.append(rd(round_half_even(logit, spec.quantization_levels), decimals))
        quantized_rows.append(row)

        def sort_key(expert_index):
            fields = {
                "expert_index": expert_index,
                "running_load": running_load[expert_index],
                "placement_rank": spec.expert_rank[expert_index],
                "bias_rank": spec.bias_rank[expert_index],
            }
            return tuple(fields[name] for name in tiebreak_order)

        decorated = sorted((-row[e],) + sort_key(e) + (e,) for e in range(experts))
        order = [item[-1] for item in decorated]
        chosen = order[: spec.top_k]
        top_values = [row[e] for e in chosen]
        contested = [e for e in range(experts) if row[e] == top_values[-1]]
        if len(contested) > 1:
            tie_events.append({
                "step": step,
                "token_index": i,
                "quantized_logit": top_values[-1],
                "contenders": sorted(contested),
                "selected": sorted(e for e in chosen if row[e] == top_values[-1]),
            })
        floor_value = min(row)
        shifts = [rd(row[e] - floor_value + 1.0, decimals) for e in chosen]
        total = rd(sum(shifts), decimals)
        weights = [rd(shift / total, decimals) for shift in shifts]
        for slot_index, expert in enumerate(chosen):
            running_load[expert] += 1
            assignments.append({
                "token_index": i,
                "expert": expert,
                "rank_in_topk": slot_index,
                "weight": weights[slot_index],
            })

    demand = [0] * experts
    for item in assignments:
        demand[item["expert"]] += 1
    gate_mass = [0.0] * experts
    for item in assignments:
        gate_mass[item["expert"]] = rd(gate_mass[item["expert"]] + item["weight"], decimals)

    return {
        "step": step,
        "token_count": count,
        "assignments": assignments,
        "demand": demand,
        "gate_mass": [rd(v, decimals) for v in gate_mass],
        "tie_break_events": tie_events,
        "quantized": quantized_rows,
    }


# ------------------------------------------------------------------ capacity


def capacity_for_step(spec, demand):
    """Capacity is aligned first and only then held at the minimum."""
    ideal = spec.capacity_factor * float(sum(demand)) / float(spec.num_experts)
    caps = []
    for e in range(spec.num_experts):
        target = min(float(demand[e]), ideal)
        aligned = spec.capacity_bucket * ceil_div(math.ceil(target), spec.capacity_bucket)
        caps.append(max(spec.min_capacity, aligned))
    return caps


def mesh_buckets(spec, caps):
    rank_bucket = {}
    for rank in sorted(spec.rank_experts):
        rank_bucket[rank] = max(caps[e] for e in spec.rank_experts[rank])
    alltoall = max(rank_bucket.values())
    return rank_bucket, alltoall


def dispatch_step(spec, routing, caps):
    """Accepted and dropped assignments in token index order."""
    decimals = spec.decimals
    running = [0] * spec.num_experts
    accepted = []
    dropped = []
    for item in routing["assignments"]:
        expert = item["expert"]
        slot = running[expert]
        if slot >= caps[expert]:
            dropped.append(dict(item))
            continue
        running[expert] += 1
        record = dict(item)
        record["slot"] = slot
        accepted.append(record)
    accepted_count = [0] * spec.num_experts
    for item in accepted:
        accepted_count[item["expert"]] += 1
    drop_mass = 0.0
    for item in dropped:
        drop_mass = rd(drop_mass + item["weight"], decimals)
    return {
        "accepted": accepted,
        "dropped": dropped,
        "accepted_count": accepted_count,
        "dropped_tokens": len(dropped),
        "dropped_token_mass": rd(drop_mass, decimals),
    }


def aux_loss_step(spec, routing, dispatch):
    """Auxiliary balance term sourced from pre drop demand."""
    decimals = spec.decimals
    experts = spec.num_experts
    total_assignments = sum(routing["demand"])
    fractions = []
    probabilities = []
    for e in range(experts):
        if total_assignments == 0:
            fractions.append(0.0)
        else:
            fractions.append(rd(float(routing["demand"][e]) / float(total_assignments), decimals))
        if routing["token_count"] == 0:
            probabilities.append(0.0)
        else:
            probabilities.append(rd(routing["gate_mass"][e] / float(routing["token_count"]), decimals))
    total = 0.0
    for e in range(experts):
        total = rd(total + rd(fractions[e] * probabilities[e], decimals), decimals)
    aux = rd(spec.aux_loss_weight * float(experts) * total, decimals)
    live = [fractions[e] for e in range(experts) if routing["demand"][e] > 0]
    if len(live) >= 2:
        dispersion = rd(max(live) - min(live), decimals)
    elif len(live) == 1:
        dispersion = 0.0
    else:
        dispersion = None
    utilization = []
    for e in range(experts):
        if routing["demand"][e] == 0:
            utilization.append(None)
        else:
            denom = float(routing["demand"][e])
            utilization.append(rd(float(dispatch["accepted_count"][e]) / denom * fractions[e], decimals))
    return {
        "aux_loss": aux,
        "assignment_fractions": fractions,
        "gate_probabilities": probabilities,
        "load_dispersion": dispersion,
        "expert_utilization": utilization,
        "empty_experts": [e for e in range(experts) if routing["demand"][e] == 0],
    }


# ------------------------------------------------------- guards and the cache


class GuardState(object):
    """Per code object dimension promotion and per rank compiled caches."""

    def __init__(self, spec):
        self.spec = spec
        self.code_objects = ["router"] + [
            "moe_block_" + str(index) for index in spec.moe_layer_indices
        ]
        self.dims = {"router": ("tokens",)}
        for name in self.code_objects:
            if name != "router":
                self.dims[name] = ("capacity", "local_experts")
        self.seen = {}
        self.promoted = {}
        for name in self.code_objects:
            for dim in self.dims[name]:
                self.seen[(name, dim)] = set()
                self.promoted[(name, dim)] = dim in spec.mark_dynamic
        self.cache = {}
        self.last_use = {}
        self.clock = 0

    def is_dynamic(self, name, dim):
        return self.promoted[(name, dim)]

    def observe(self, name, dim, value):
        """Distinct value accounting counts the value being compiled now."""
        key = (name, dim)
        if self.promoted[key]:
            return
        self.seen[key].add(value)
        if not self.spec.dynamic_promotion_enabled:
            return
        if len(self.seen[key]) >= self.spec.promotion_threshold:
            self.promoted[key] = True

    def component(self, name, dim, value):
        if self.promoted[(name, dim)] and value not in (0, 1):
            return "dyn"
        return str(value)

    def reset(self):
        self.cache = {}
        self.last_use = {}

    def entry_count(self):
        return sum(len(entries) for entries in self.cache.values())

    def guard_closures(self):
        total = 0
        for entries in self.cache.values():
            for key in entries:
                total += sum(1 for part in key.split("|") if part != "dyn")
        return total


def dim_values(spec, name, token_count, rank_bucket, rank):
    values = {
        "tokens": token_count,
        "capacity": rank_bucket[rank],
        "local_experts": len(spec.rank_experts[rank]),
    }
    return values


def compile_step(spec, guards, step, token_count, rank_bucket):
    """Guard keys, recompiles and evictions for one step."""
    events = []
    keys = []
    for name in guards.code_objects:
        dims = guards.dims[name]
        for rank in sorted(spec.rank_experts):
            values = dim_values(spec, name, token_count, rank_bucket, rank)
            static_before = sum(1 for dim in dims if not guards.is_dynamic(name, dim))
            for dim in dims:
                guards.observe(name, dim, values[dim])
            parts = [guards.component(name, dim, values[dim]) for dim in dims]
            key = "|".join(parts)
            static_after = sum(1 for part in parts if part != "dyn")
            slot = (name, rank)
            entries = guards.cache.setdefault(slot, {})
            guards.clock += 1
            keys.append({
                "code_object": name,
                "rank": rank,
                "key": key,
                "static_dims_before": static_before,
                "static_dims_after": static_after,
            })
            if key in entries:
                guards.last_use[(slot, key)] = guards.clock
                continue
            evicted = None
            if len(entries) >= spec.cache_size_limit:
                candidates = sorted(
                    entries.keys(),
                    key=lambda k: (guards.last_use[(slot, k)], k),
                )
                evicted = candidates[0]
                del entries[evicted]
                del guards.last_use[(slot, evicted)]
            entries[key] = True
            guards.last_use[(slot, key)] = guards.clock
            events.append({
                "step": step,
                "code_object": name,
                "rank": rank,
                "guard_key": key,
                "static_dims_before": static_before,
                "static_dims_after": static_after,
                "guard_delta": static_after - static_before,
                "evicted_key": evicted,
            })
    return events, keys


# -------------------------------------------------------------- graph breaks


def graph_breaks_step(spec, caps, rank_bucket, dispatch, demand, previous_tokens, token_count):
    fired = []
    if any(cap % spec.capacity_bucket != 0 for cap in caps):
        fired.append("data_dependent_capacity")
    if previous_tokens is not None and previous_tokens != token_count:
        if "tokens" not in spec.mark_dynamic:
            fired.append("dynamic_token_count")
    if dispatch["dropped_tokens"] > 0:
        fired.append("token_drop_mask")
    values = list(rank_bucket.values())
    if max(values) != min(values):
        fired.append("unbalanced_expert_slice")
    if any(value == 0 for value in demand):
        fired.append("zero_token_expert")
    return [cause for cause in BREAK_CAUSES if cause in fired]


def capture_step(spec, keys, break_count):
    """Capture eligibility for the reduce overhead path."""
    attempts = []
    for item in keys:
        if item["code_object"] == "router":
            continue
        if spec.compile_mode != "reduce-overhead":
            attempts.append({
                "code_object": item["code_object"],
                "rank": item["rank"],
                "guard_key": item["key"],
                "captured": False,
                "cause": "capture_disabled_for_mode",
            })
            continue
        if break_count > 0:
            attempts.append({
                "code_object": item["code_object"],
                "rank": item["rank"],
                "guard_key": item["key"],
                "captured": False,
                "cause": "operation_not_permitted_when_stream_is_capturing",
            })
            continue
        if "dyn" in item["key"].split("|"):
            attempts.append({
                "code_object": item["code_object"],
                "rank": item["rank"],
                "guard_key": item["key"],
                "captured": False,
                "cause": "dynamic_dimension_in_guard_key",
            })
            continue
        attempts.append({
            "code_object": item["code_object"],
            "rank": item["rank"],
            "guard_key": item["key"],
            "captured": True,
            "cause": None,
        })
    return attempts


def pool_bytes_for(spec, rank_bucket):
    rows = sorted(spec.corpus.pool_blocks, key=lambda r: int(r["capacity_ceiling"]))
    total = 0
    for rank in sorted(rank_bucket):
        value = rank_bucket[rank]
        chosen = None
        for row in rows:
            if value <= int(row["capacity_ceiling"]):
                chosen = int(row["block_bytes"])
                break
        if chosen is None:
            chosen = int(rows[-1]["block_bytes"])
        total += chosen
    return total


# ------------------------------------------------------------------ timings


def step_timing(spec, compile_events, captures, breaks, rank_bucket, alltoall, eager):
    decimals = spec.time_decimals
    corpus = spec.corpus
    gates = corpus.steptime_gates
    mode = "eager" if eager else spec.compile_mode
    compile_us = 0.0
    if not eager:
        for event in compile_events:
            cost = None
            for row in corpus.compile_cost:
                if row["compile_mode"] == spec.compile_mode and int(row["static_dims"]) == event["static_dims_before"]:
                    cost = float(row["compile_us"])
                    break
            if cost is None:
                cost = float(gates["fallback_compile_us"])
            compile_us = rd(compile_us + cost, decimals)
    capture_us = 0.0
    discount = 1.0
    if not eager:
        for row in corpus.capture_cost:
            if row["compile_mode"] == spec.compile_mode:
                unit = float(row["capture_us"])
                discount = float(row["replay_discount"])
                break
        else:
            unit = 0.0
        captured = sum(1 for item in captures if item["captured"])
        capture_us = rd(unit * float(captured), decimals)
        if captured == 0:
            discount = 1.0
    compute_us = 0.0
    for rank in sorted(spec.rank_experts):
        local = 0.0
        for expert in spec.rank_experts[rank]:
            local = rd(local + spec.kernel_us[expert] * float(rank_bucket[rank]), decimals)
        compute_us = max(compute_us, local)
    if eager:
        compute_us = rd(compute_us * float(gates["eager_compute_multiplier"]), decimals)
    else:
        compute_us = rd(compute_us * discount, decimals)
    fixed = 0.0
    per_slot = 0.0
    for row in corpus.alltoall_cost:
        if int(row["ep_world_size"]) == spec.ep_world_size:
            fixed = float(row["fixed_us"])
            per_slot = float(row["per_slot_us"])
            break
    alltoall_us = rd(fixed + per_slot * float(alltoall) * float(spec.ep_world_size), decimals)
    bubble_us = 0.0
    if not eager:
        for cause in breaks:
            unit = table_lookup(corpus.break_catalog, "cause", cause, "bubble_us")
            bubble_us = rd(bubble_us + unit * float(len(spec.moe_layer_indices)), decimals)
        if compile_events:
            bubble_us = rd(bubble_us + float(gates["sync_bubble_us"]), decimals)
    total = rd(
        rd(compile_us, decimals)
        + rd(capture_us, decimals)
        + rd(compute_us, decimals)
        + rd(alltoall_us, decimals)
        + rd(bubble_us, decimals),
        decimals,
    )
    return {
        "compile_us": rd(compile_us, decimals),
        "capture_us": rd(capture_us, decimals),
        "compute_us": rd(compute_us, decimals),
        "alltoall_us": rd(alltoall_us, decimals),
        "bubble_us": rd(bubble_us, decimals),
        "step_us": total,
    }


# ------------------------------------------------------------ numeric replay


def store(value, eager):
    return float(value) if eager else bf16(value)


def accumulate(value, eager):
    return float(value) if eager else fp32(value)


def replay_step(spec, routing, dispatch, caps, params, eager):
    """Expert outputs, loss terms and the optimizer update for one step."""
    decimals = spec.decimals
    experts = spec.num_experts
    payload_scale = float(spec.corpus.topology["surrogate"]["payload_scale"])
    salt = spec.step_draws(routing["step"])[0]
    per_expert = {}
    for e in range(experts):
        per_expert[e] = []
    for item in dispatch["accepted"]:
        per_expert[item["expert"]].append(item)
    outputs = []
    partials = []
    for e in range(experts):
        acc = accumulate(0.0, eager)
        slots = sorted(per_expert[e], key=lambda r: r["slot"])
        for item in slots:
            t = store(rd(salt[item["token_index"]] * 2.0 - 1.0, decimals), eager)
            w = store(item["weight"], eager)
            raw = accumulate(w * (1.0 - t * 0.25), eager)
            payload = raw * payload_scale if eager else fp8_e4m3(accumulate(raw * payload_scale, eager))
            acc = accumulate(acc + accumulate(payload / payload_scale, eager), eager)
        count = dispatch["accepted_count"][e]
        if count == 0:
            outputs.append(store(0.0, eager))
        else:
            outputs.append(store(acc / float(count), eager))
        partials.append(rd(acc, decimals))
    signal = accumulate(0.0, eager)
    for e in range(experts):
        signal = accumulate(signal + accumulate(outputs[e] * spec.cost_weight[e], eager), eager)
    grads = []
    for e in range(experts):
        grads.append(accumulate(outputs[e] * spec.signal_weight * spec.cost_weight[e], eager))
    scaled = [accumulate(g * spec.loss_scale, eager) for g in grads]
    square_sum = accumulate(0.0, eager)
    for value in scaled:
        square_sum = accumulate(square_sum + accumulate(value * value, eager), eager)
    global_norm = math.sqrt(square_sum)
    clip_ref = spec.clip_threshold * spec.loss_scale
    if global_norm <= clip_ref:
        factor = 1.0
    else:
        factor = clip_ref / global_norm
    unscaled = [accumulate(accumulate(value * factor, eager) / spec.loss_scale, eager) for value in scaled]
    new_params = []
    for e in range(experts):
        new_params.append(store(params[e] - spec.learning_rate * unscaled[e], eager))
    return {
        "expert_outputs": [rd(v, decimals) for v in outputs],
        "expert_partials": partials,
        "step_signal": rd(signal, decimals),
        "gradients": [rd(v, decimals) for v in grads],
        "scaled_norm": rd(global_norm, decimals),
        "clip_reference": rd(clip_ref, decimals),
        "clip_factor": rd(factor, decimals),
        "unscaled_gradients": [rd(v, decimals) for v in unscaled],
        "params": new_params,
        "clipped": global_norm > clip_ref,
    }


# ------------------------------------------------------------------ full run


def simulate(spec, tiebreak_order, eager=False, collect=True, capacity=None, faults=None):
    """Walk every step of a run in order."""
    plan_capacity = capacity_for_step if capacity is None else capacity
    faults = faults or {}
    balance = faults.get("aux", aux_loss_step)
    pool_growth = faults.get("pool", pool_bytes_for)
    decimals = spec.decimals
    guards = faults.get("guards", GuardState)(spec)
    params = [store(0.0, eager)] * spec.num_experts
    pool_bytes = 0
    pool_peak = 0
    previous_tokens = None
    steps = []
    for step in range(1, spec.steps + 1):
        reset = step in spec.reset_steps
        if reset:
            guards.reset()
            pool_bytes = 0
        routing = route_step(spec, step, tiebreak_order)
        caps = plan_capacity(spec, routing["demand"])
        rank_bucket, alltoall = mesh_buckets(spec, caps)
        dispatch = dispatch_step(spec, routing, caps)
        aux = balance(spec, routing, dispatch)
        breaks = graph_breaks_step(
            spec, caps, rank_bucket, dispatch, routing["demand"], previous_tokens, routing["token_count"]
        )
        events, keys = compile_step(spec, guards, step, routing["token_count"], rank_bucket)
        captures = capture_step(spec, keys, len(breaks))
        captured_new = 0
        for item in captures:
            if item["captured"]:
                captured_new += 1
        if captured_new > 0 and not eager:
            pool_bytes += pool_growth(spec, rank_bucket)
        peak_for_step = max(pool_peak, pool_bytes)
        timing = step_timing(spec, events, captures, breaks, rank_bucket, alltoall, eager)
        numeric = replay_step(spec, routing, dispatch, caps, params, eager)
        params = numeric["params"]
        decay = 1.0 / (1.0 + spec.decay_rate * float(step))
        loss = rd(
            rd(spec.base_loss * decay, decimals)
            + aux["aux_loss"]
            + rd(spec.signal_weight * numeric["step_signal"], decimals),
            decimals,
        )
        entry_bytes = 0
        guard_bytes = 0
        for row in spec.corpus.memory_slots:
            if int(row["static_dims"]) == min(3, max(0, len(spec.mark_dynamic))):
                entry_bytes = int(row["entry_bytes"])
                guard_bytes = int(row["guard_bytes"])
                break
        if entry_bytes == 0:
            entry_bytes = int(spec.corpus.memory_slots[-1]["entry_bytes"])
            guard_bytes = int(spec.corpus.memory_slots[-1]["guard_bytes"])
        if "host" in faults:
            host_bytes = faults["host"](spec, guards, peak_for_step)
        else:
            host_bytes = (
                int(spec.corpus.memory_gates["host_base_bytes"])
                + guards.entry_count() * entry_bytes
                + guards.guard_closures() * guard_bytes
                + peak_for_step
            )
        headroom = int(spec.corpus.memory_gates["host_ceiling_bytes"]) - host_bytes
        record = {
            "step": step,
            "reset": reset,
            "token_count": routing["token_count"],
            "demand": routing["demand"],
            "capacity": caps,
            "rank_bucket": dict((str(k), v) for k, v in rank_bucket.items()),
            "alltoall_bucket": alltoall,
            "accepted_count": dispatch["accepted_count"],
            "dropped_tokens": dispatch["dropped_tokens"],
            "dropped_token_mass": dispatch["dropped_token_mass"],
            "aux": aux,
            "breaks": breaks,
            "recompiles": len(events),
            "events": events,
            "keys": keys,
            "captures": captures,
            "pool_bytes": pool_bytes,
            "pool_peak_bytes": peak_for_step,
            "cache_entries": guards.entry_count(),
            "guard_closures": guards.guard_closures(),
            "host_bytes": host_bytes,
            "host_headroom_bytes": headroom,
            "timing": timing,
            "numeric": numeric,
            "loss": loss,
            "tie_break_events": routing["tie_break_events"],
        }
        if reset:
            pool_peak = pool_bytes
        else:
            pool_peak = peak_for_step
        previous_tokens = routing["token_count"]
        steps.append(record if collect else {
            "step": step,
            "loss": loss,
            "timing": timing,
            "recompiles": len(events),
        })
    return {
        "spec": spec,
        "steps": steps,
        "guards": guards,
        "final_params": [rd(v, decimals) for v in params],
    }


def gated_steps(spec, steps):
    return [record for record in steps if record["step"] > spec.warmup_bound]


def warmup_steps(spec, steps):
    return [record for record in steps if record["step"] <= spec.warmup_bound]


def total_us(records, decimals):
    total = 0.0
    for record in records:
        total = rd(total + record["timing"]["step_us"], decimals)
    return total


def run_summary(spec, compiled, baseline):
    """Gate figures for one configuration."""
    decimals = spec.time_decimals
    numeric_decimals = spec.decimals
    tail = gated_steps(spec, compiled["steps"])
    base_tail = gated_steps(spec, baseline["steps"])
    compiled_us = total_us(tail, decimals)
    eager_us = total_us(base_tail, decimals)
    speedup = rd(eager_us / compiled_us, decimals) if compiled_us > 0 else 0.0
    recompiles_after = sum(record["recompiles"] for record in tail)
    min_headroom = min(record["host_headroom_bytes"] for record in compiled["steps"])
    drops = sum(record["dropped_tokens"] for record in compiled["steps"])
    assignments = sum(sum(record["demand"]) for record in compiled["steps"])
    drop_rate = rd(float(drops) / float(assignments), numeric_decimals) if assignments else 0.0
    closing = compiled["steps"][-1]["loss"]
    base_closing = baseline["steps"][-1]["loss"]
    deviation = rd(abs(closing - base_closing) / abs(base_closing), numeric_decimals) if base_closing else 0.0
    min_capacity_seen = min(min(record["capacity"]) for record in compiled["steps"])
    return {
        "compiled_tail_us": compiled_us,
        "eager_tail_us": eager_us,
        "speedup": speedup,
        "recompiles_after_warmup": recompiles_after,
        "min_host_headroom_bytes": min_headroom,
        "drop_rate": drop_rate,
        "closing_loss": closing,
        "baseline_closing_loss": base_closing,
        "relative_deviation": deviation,
        "min_capacity_seen": min_capacity_seen,
    }


# ------------------------------------------------------------- warmup profile


def build_warmup_profile(spec, run):
    window = warmup_steps(spec, run["steps"])
    tokens = sorted(set(record["token_count"] for record in window))
    caps = sorted(set(value for record in window for value in record["rank_bucket"].values()))
    locals_seen = sorted(set(len(spec.rank_experts[rank]) for rank in spec.rank_experts))
    return {
        "run_id": spec.run_id,
        "warmup_bound": spec.warmup_bound,
        "window_steps": [record["step"] for record in window],
        "distinct_token_values": tokens,
        "distinct_capacity_values": caps,
        "distinct_local_expert_values": locals_seen,
        "promotion_threshold": spec.promotion_threshold,
        "dims_requiring_dynamic": sorted(
            name for name, values in (
                ("tokens", tokens),
                ("local_experts", locals_seen),
            ) if len(values) >= spec.promotion_threshold
        ),
        "warmup_recompiles": sum(record["recompiles"] for record in window),
    }


# ----------------------------------------------------------------- settlement


def candidate_configs(spec):
    axes = spec.corpus.candidates
    out = []
    for factor in axes["capacity_factor"]:
        for bucket in axes["capacity_bucket"]:
            for dynamic in axes["mark_dynamic"]:
                for mode in axes["compile_mode"]:
                    out.append({
                        "capacity_factor": float(factor),
                        "capacity_bucket": int(bucket),
                        "mark_dynamic": sorted(dynamic),
                        "compile_mode": str(mode),
                    })
    out.sort(key=lambda c: (
        c["capacity_factor"], -c["capacity_bucket"],
        "|".join(c["mark_dynamic"]), c["compile_mode"],
    ))
    return out


def candidate_spec(spec, candidate, horizon):
    config = dict(spec.config)
    config["capacity_factor"] = candidate["capacity_factor"]
    config["capacity_bucket"] = candidate["capacity_bucket"]
    config["mark_dynamic"] = list(candidate["mark_dynamic"])
    config["compile_mode"] = candidate["compile_mode"]
    config["steps"] = horizon
    config["reset_steps"] = [v for v in spec.reset_steps if v <= horizon]
    return RunSpec(config, spec.corpus)


def candidate_violations(spec, candidate, horizon, baseline_cache):
    probe = candidate_spec(spec, candidate, horizon)
    compiled = simulate(probe, spec.tiebreak_order)
    key = (candidate["capacity_factor"], candidate["capacity_bucket"])
    if key not in baseline_cache:
        base_config = dict(probe.config)
        base_config["compile_mode"] = "eager"
        base_config["mark_dynamic"] = []
        baseline_cache[key] = simulate(RunSpec(base_config, spec.corpus), spec.tiebreak_order, eager=True)
    summary = run_summary(probe, compiled, baseline_cache[key])
    return summary, gate_violations(spec, candidate["compile_mode"], summary)


def gate_violations(spec, compile_mode, summary):
    gates = spec.corpus.steptime_gates
    conv = spec.corpus.convergence_gates
    memory = spec.corpus.memory_gates
    violated = []
    if compile_mode == "eager":
        violated.append("eager_mode_forbidden")
    if summary["recompiles_after_warmup"] > int(gates["recompile_budget"]):
        violated.append("recompile_budget_exceeded")
    if summary["speedup"] < float(gates["min_speedup"]):
        violated.append("speedup_gate_unmet")
    if summary["min_host_headroom_bytes"] < 0:
        violated.append("memory_ceiling_exceeded")
    if summary["drop_rate"] > float(conv["max_drop_rate"]):
        violated.append("drop_tolerance_exceeded")
    if summary["relative_deviation"] > float(conv["settlement_parity_band"]):
        violated.append("convergence_band_unmet")
    if summary["min_capacity_seen"] < int(memory["capacity_floor"]):
        violated.append("capacity_below_minimum")
    return sorted(violated)


def precedence_candidates():
    """Every cause order allowed by the shipped partial order constraints."""
    import itertools
    out = []
    for order in itertools.permutations(CAUSE_NAMES):
        if order[0] != "eager_mode_forbidden":
            continue
        if order.index("capacity_below_minimum") > order.index("drop_tolerance_exceeded"):
            continue
        if order.index("recompile_budget_exceeded") > order.index("speedup_gate_unmet"):
            continue
        out.append(list(order))
    out.sort()
    return out


def tiebreak_candidates():
    import itertools
    return [list(order) for order in sorted(itertools.permutations(TIEBREAK_FIELDS))]


def sweep(spec, horizon):
    baseline_cache = {}
    rows = []
    for candidate in candidate_configs(spec):
        summary, violated = candidate_violations(spec, candidate, horizon, baseline_cache)
        rows.append({"candidate": candidate, "summary": summary, "violations": violated})
    return rows


def prefilter(spec, profile, candidate):
    """Candidates that ignore a dimension the warmup window already promoted."""
    missing = [dim for dim in profile["dims_requiring_dynamic"] if dim not in candidate["mark_dynamic"]]
    return sorted(missing)


def build_rejection_ledger(spec, rows, profile, order):
    counts = dict((cause, 0) for cause in CAUSE_NAMES)
    entries = []
    prefiltered = []
    admissible = []
    for row in rows:
        candidate = row["candidate"]
        missing = prefilter(spec, profile, candidate)
        label = candidate_label(candidate)
        if missing:
            prefiltered.append({"candidate": label, "unmarked_dims": missing})
            continue
        if not row["violations"]:
            admissible.append(label)
            continue
        cause = None
        for name in order:
            if name in row["violations"]:
                cause = name
                break
        counts[cause] += 1
        entries.append({"candidate": label, "cause": cause, "all_violations": row["violations"]})
    entries.sort(key=lambda item: item["candidate"])
    prefiltered.sort(key=lambda item: item["candidate"])
    return {
        "cause_order": list(order),
        "per_cause_counts": counts,
        "rejected": entries,
        "prefiltered": prefiltered,
        "admissible_candidates": sorted(admissible),
    }


def candidate_label(candidate):
    return "cf={0}|bucket={1}|dynamic={2}|mode={3}".format(
        format_float(candidate["capacity_factor"]),
        candidate["capacity_bucket"],
        "+".join(candidate["mark_dynamic"]) if candidate["mark_dynamic"] else "none",
        candidate["compile_mode"],
    )


def format_float(value):
    text = repr(float(value))
    return text


def select_candidate(admissible_labels, rows):
    lookup = dict((candidate_label(row["candidate"]), row["candidate"]) for row in rows)
    ranked = sorted(
        admissible_labels,
        key=lambda label: (
            lookup[label]["capacity_factor"],
            -lookup[label]["capacity_bucket"],
            len(lookup[label]["mark_dynamic"]),
            "|".join(lookup[label]["mark_dynamic"]),
        ),
    )
    ranked = sorted(
        ranked,
        key=lambda label: (
            lookup[label]["capacity_factor"],
            -lookup[label]["capacity_bucket"],
            len(lookup[label]["mark_dynamic"]),
            "|".join(lookup[label]["mark_dynamic"]),
        ),
    )
    best = ranked[0] if ranked else None
    if best is not None:
        head = (
            lookup[best]["capacity_factor"],
            -lookup[best]["capacity_bucket"],
            len(lookup[best]["mark_dynamic"]),
            "|".join(lookup[best]["mark_dynamic"]),
        )
        siblings = [
            label for label in ranked
            if (
                lookup[label]["capacity_factor"],
                -lookup[label]["capacity_bucket"],
                len(lookup[label]["mark_dynamic"]),
                "|".join(lookup[label]["mark_dynamic"]),
            ) == head
        ]
        ranked = sorted(siblings, key=lambda label: lookup[label]["compile_mode"], reverse=True)
    if not ranked:
        return None
    return lookup[ranked[0]]


# ------------------------------------------------------------ sealed policies


def resolve_tiebreak(corpus, config_name, config):
    sealed = corpus.sealed_tiebreak["digests"]
    matches = []
    for order in tiebreak_candidates():
        spec = RunSpec(config, corpus)
        events = []
        for step in range(1, int(sealed[config_name]["steps"]) + 1):
            events.extend(route_step(spec, step, order)["tie_break_events"])
        if digest_of(events) == sealed[config_name]["digest"]:
            matches.append(order)
    return matches


def resolve_precedence(corpus, rows_by_config, sealed):
    matches = []
    for order in precedence_candidates():
        ok = True
        for name, payload in sorted(rows_by_config.items()):
            counts = dict((cause, 0) for cause in CAUSE_NAMES)
            for row in payload["rows"]:
                if prefilter(payload["spec"], payload["profile"], row["candidate"]):
                    continue
                if not row["violations"]:
                    continue
                for cause in order:
                    if cause in row["violations"]:
                        counts[cause] += 1
                        break
            if digest_of(counts) != sealed["digests"][name]["digest"]:
                ok = False
                break
        if ok:
            matches.append(order)
    return matches


# ------------------------------------------------------------------ analysis


STAGE_ARTIFACTS = (
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

REPLAY_ARTIFACTS = (
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


def make_spec(corpus, config, order):
    spec = RunSpec(config, corpus)
    spec.tiebreak_order = order
    return spec


def eager_twin(spec):
    config = dict(spec.config)
    config["compile_mode"] = "eager"
    config["mark_dynamic"] = []
    twin = RunSpec(config, spec.corpus)
    twin.tiebreak_order = spec.tiebreak_order
    return twin


def artifact_route_plan(spec, run):
    steps = []
    ties = []
    for record in run["steps"]:
        steps.append({
            "step": record["step"],
            "token_count": record["token_count"],
            "demand": record["demand"],
            "gate_mass_total": rd(sum(record["aux"]["gate_probabilities"]) * record["token_count"], spec.decimals),
            "tie_break_count": len(record["tie_break_events"]),
        })
        ties.extend(record["tie_break_events"])
    return {
        "run_id": spec.run_id,
        "top_k": spec.top_k,
        "tie_break_key": list(spec.tiebreak_order),
        "steps": steps,
        "tie_break_events": ties,
        "total_assignments": sum(sum(record["demand"]) for record in run["steps"]),
    }


def artifact_capacity_plan(spec, run):
    steps = []
    for record in run["steps"]:
        steps.append({
            "step": record["step"],
            "capacity": record["capacity"],
            "unaligned_experts": [
                e for e in range(spec.num_experts)
                if record["capacity"][e] % spec.capacity_bucket != 0
            ],
        })
    return {
        "run_id": spec.run_id,
        "capacity_factor": spec.capacity_factor,
        "capacity_bucket": spec.capacity_bucket,
        "min_capacity": spec.min_capacity,
        "steps": steps,
        "min_capacity_seen": min(min(record["capacity"]) for record in run["steps"]),
        "max_capacity_seen": max(max(record["capacity"]) for record in run["steps"]),
        "distinct_capacity_values": sorted(set(
            value for record in run["steps"] for value in record["capacity"]
        )),
    }


def artifact_mesh_plan(spec, run):
    placement = {}
    for rank in sorted(spec.rank_experts):
        placement[str(rank)] = spec.rank_experts[rank]
    return {
        "run_id": spec.run_id,
        "ep_world_size": spec.ep_world_size,
        "expert_rank": [spec.expert_rank[e] for e in range(spec.num_experts)],
        "rank_experts": placement,
        "placement_groups": [spec.placement_group[e] for e in range(spec.num_experts)],
        "rank_bucket_by_step": [
            {"step": record["step"], "rank_bucket": record["rank_bucket"]}
            for record in run["steps"]
        ],
        "expert_shape_matrix": len(set(
            tuple(record["capacity"]) for record in run["steps"]
        )) * len(spec.moe_layer_indices),
    }


def artifact_dispatch_ledger(spec, run):
    steps = []
    for record in run["steps"]:
        steps.append({
            "step": record["step"],
            "accepted_count": record["accepted_count"],
            "padded_slots": [
                record["capacity"][e] - record["accepted_count"][e]
                for e in range(spec.num_experts)
            ],
        })
    return {
        "run_id": spec.run_id,
        "steps": steps,
        "total_accepted": sum(sum(record["accepted_count"]) for record in run["steps"]),
        "total_padded_slots": sum(
            sum(record["capacity"][e] - record["accepted_count"][e] for e in range(spec.num_experts))
            for record in run["steps"]
        ),
    }


def artifact_drop_ledger(spec, run):
    steps = []
    for record in run["steps"]:
        steps.append({
            "step": record["step"],
            "dropped_tokens": record["dropped_tokens"],
            "dropped_token_mass": record["dropped_token_mass"],
        })
    total_mass = 0.0
    for record in run["steps"]:
        total_mass = rd(total_mass + record["dropped_token_mass"], spec.decimals)
    assignments = sum(sum(record["demand"]) for record in run["steps"])
    dropped = sum(record["dropped_tokens"] for record in run["steps"])
    return {
        "run_id": spec.run_id,
        "steps": steps,
        "dropped_tokens": dropped,
        "dropped_token_mass": total_mass,
        "drop_rate": rd(float(dropped) / float(assignments), spec.decimals) if assignments else 0.0,
        "steps_with_drops": [record["step"] for record in run["steps"] if record["dropped_tokens"] > 0],
    }


def artifact_alltoall_ledger(spec, run):
    steps = []
    for record in run["steps"]:
        payload = record["alltoall_bucket"] * spec.ep_world_size * len(spec.rank_experts[0])
        steps.append({
            "step": record["step"],
            "alltoall_bucket": record["alltoall_bucket"],
            "payload_slots": payload,
            "rank_bucket_spread": max(record["rank_bucket"].values()) - min(record["rank_bucket"].values()),
        })
    return {
        "run_id": spec.run_id,
        "ep_world_size": spec.ep_world_size,
        "steps": steps,
        "uniform_steps": [item["step"] for item in steps if item["rank_bucket_spread"] == 0],
        "total_payload_slots": sum(item["payload_slots"] for item in steps),
    }


def artifact_guard_key_index(spec, run):
    index = {}
    for record in run["steps"]:
        for item in record["keys"]:
            slot = item["code_object"] + "@" + str(item["rank"])
            index.setdefault(slot, set()).add(item["key"])
    out = {}
    for slot in sorted(index):
        out[slot] = sorted(index[slot])
    return {
        "run_id": spec.run_id,
        "keys_by_slot": out,
        "distinct_key_count": sum(len(values) for values in out.values()),
        "specialized_zero_one_keys": sorted(set(
            item["key"]
            for record in run["steps"] for item in record["keys"]
            if any(part in ("0", "1") for part in item["key"].split("|"))
        )),
        "dynamic_dims_final": sorted(
            dim for (name, dim), value in run["guards"].promoted.items() if value
        ),
    }


def artifact_recompile_report(spec, run):
    events = []
    for record in run["steps"]:
        for item in record["events"]:
            events.append({
                "step": item["step"],
                "code_object": item["code_object"],
                "rank": item["rank"],
                "guard_key": item["guard_key"],
                "guard_delta": item["guard_delta"],
                "evicted_key": item["evicted_key"],
            })
    tail = gated_steps(spec, run["steps"])
    return {
        "run_id": spec.run_id,
        "warmup_bound": spec.warmup_bound,
        "recompile_events": events,
        "total_recompiles": len(events),
        "recompiles_after_warmup": sum(record["recompiles"] for record in tail),
        "first_step_over_budget": first_over_budget(spec, run),
        "evictions": sum(1 for item in events if item["evicted_key"] is not None),
        "recompiles_by_step": [
            {"step": record["step"], "count": record["recompiles"]}
            for record in run["steps"] if record["recompiles"] > 0
        ],
    }


def first_over_budget(spec, run):
    budget = int(spec.corpus.steptime_gates["recompile_budget"])
    running = 0
    for record in gated_steps(spec, run["steps"]):
        running += record["recompiles"]
        if running > budget:
            return record["step"]
    return None


def artifact_graph_break_ledger(spec, run):
    counts = dict((cause, 0) for cause in BREAK_CAUSES)
    steps = []
    for record in run["steps"]:
        for cause in record["breaks"]:
            counts[cause] += 1
        steps.append({"step": record["step"], "causes": record["breaks"]})
    return {
        "run_id": spec.run_id,
        "cause_order": list(BREAK_CAUSES),
        "per_cause_counts": counts,
        "steps": steps,
        "total_breaks": sum(counts.values()),
        "clean_steps": [record["step"] for record in run["steps"] if not record["breaks"]],
    }


def artifact_cudagraph_report(spec, run):
    failures = {}
    captured = 0
    attempts = 0
    steps = []
    for record in run["steps"]:
        local = 0
        for item in record["captures"]:
            attempts += 1
            if item["captured"]:
                captured += 1
                local += 1
            else:
                failures[item["cause"]] = failures.get(item["cause"], 0) + 1
        steps.append({
            "step": record["step"],
            "captured": local,
            "pool_bytes": record["pool_bytes"],
            "pool_peak_bytes": record["pool_peak_bytes"],
        })
    return {
        "run_id": spec.run_id,
        "compile_mode": spec.compile_mode,
        "capture_attempts": attempts,
        "captures": captured,
        "failure_causes": failures,
        "steps": steps,
        "final_pool_peak_bytes": run["steps"][-1]["pool_peak_bytes"],
        "reset_steps": list(spec.reset_steps),
    }


def artifact_host_memory_report(spec, run):
    steps = []
    for record in run["steps"]:
        steps.append({
            "step": record["step"],
            "cache_entries": record["cache_entries"],
            "guard_closures": record["guard_closures"],
            "host_bytes": record["host_bytes"],
            "host_headroom_bytes": record["host_headroom_bytes"],
        })
    negative = [item["step"] for item in steps if item["host_headroom_bytes"] < 0]
    return {
        "run_id": spec.run_id,
        "host_ceiling_bytes": int(spec.corpus.memory_gates["host_ceiling_bytes"]),
        "steps": steps,
        "min_host_headroom_bytes": min(item["host_headroom_bytes"] for item in steps),
        "peak_host_bytes": max(item["host_bytes"] for item in steps),
        "steps_over_ceiling": negative,
        "memory_gate_met": len(negative) == 0,
    }


def artifact_steptime_report(spec, compiled, baseline):
    decimals = spec.time_decimals
    steps = []
    for record, base in zip(compiled["steps"], baseline["steps"]):
        steps.append({
            "step": record["step"],
            "compile_us": record["timing"]["compile_us"],
            "capture_us": record["timing"]["capture_us"],
            "compute_us": record["timing"]["compute_us"],
            "alltoall_us": record["timing"]["alltoall_us"],
            "bubble_us": record["timing"]["bubble_us"],
            "step_us": record["timing"]["step_us"],
            "eager_step_us": base["timing"]["step_us"],
        })
    tail = gated_steps(spec, compiled["steps"])
    base_tail = gated_steps(spec, baseline["steps"])
    compiled_us = total_us(tail, decimals)
    eager_us = total_us(base_tail, decimals)
    speedup = rd(eager_us / compiled_us, decimals) if compiled_us else 0.0
    return {
        "run_id": spec.run_id,
        "steps": steps,
        "gated_step_range": [spec.warmup_bound + 1, spec.steps],
        "compiled_tail_us": compiled_us,
        "eager_tail_us": eager_us,
        "speedup": speedup,
        "min_speedup": float(spec.corpus.steptime_gates["min_speedup"]),
        "speedup_gate_met": speedup >= float(spec.corpus.steptime_gates["min_speedup"]),
        "amortized_compile_us": rd(
            total_compile(compiled["steps"], decimals) / float(max(1, len(tail))), decimals
        ),
    }


def total_compile(steps, decimals):
    total = 0.0
    for record in steps:
        total = rd(total + record["timing"]["compile_us"], decimals)
    return total


def artifact_aux_loss_trace(spec, run):
    steps = []
    for record in run["steps"]:
        steps.append({
            "step": record["step"],
            "aux_loss": record["aux"]["aux_loss"],
            "load_dispersion": record["aux"]["load_dispersion"],
            "expert_utilization": record["aux"]["expert_utilization"],
            "empty_experts": record["aux"]["empty_experts"],
        })
    total = 0.0
    for record in run["steps"]:
        total = rd(total + record["aux"]["aux_loss"], spec.decimals)
    live = [item["load_dispersion"] for item in steps if item["load_dispersion"] is not None]
    return {
        "run_id": spec.run_id,
        "aux_loss_weight": spec.aux_loss_weight,
        "steps": steps,
        "aux_loss_total": total,
        "steps_with_empty_experts": [item["step"] for item in steps if item["empty_experts"]],
        "mean_load_dispersion": rd(sum(live) / float(len(live)), spec.decimals) if live else None,
    }


def artifact_loss_curve(spec, compiled, baseline):
    steps = []
    for record, base in zip(compiled["steps"], baseline["steps"]):
        steps.append({
            "step": record["step"],
            "loss": record["loss"],
            "eager_loss": base["loss"],
            "signed_gap": rd(record["loss"] - base["loss"], spec.decimals),
        })
    return {
        "run_id": spec.run_id,
        "steps": steps,
        "closing_loss": steps[-1]["loss"],
        "opening_loss": steps[0]["loss"],
        "minimum_loss": min(item["loss"] for item in steps),
        "steps_above_opening": [item["step"] for item in steps if item["loss"] > steps[0]["loss"]],
    }


def artifact_gradient_ledger(spec, run):
    steps = []
    for record in run["steps"]:
        steps.append({
            "step": record["step"],
            "expert_partials": record["numeric"]["expert_partials"],
            "expert_outputs": record["numeric"]["expert_outputs"],
            "gradients": record["numeric"]["gradients"],
            "step_signal": record["numeric"]["step_signal"],
        })
    folded = 0.0
    for record in run["steps"]:
        folded = rd(folded + record["numeric"]["step_signal"], spec.decimals)
    return {
        "run_id": spec.run_id,
        "steps": steps,
        "folded_signal": folded,
        "final_params": run["final_params"],
        "accumulation_order": ["slot_ascending", "expert_index_ascending"],
    }


def artifact_optimizer_trace(spec, run):
    steps = []
    for record in run["steps"]:
        steps.append({
            "step": record["step"],
            "scaled_norm": record["numeric"]["scaled_norm"],
            "clip_reference": record["numeric"]["clip_reference"],
            "clip_factor": record["numeric"]["clip_factor"],
            "clipped": record["numeric"]["clipped"],
        })
    return {
        "run_id": spec.run_id,
        "loss_scale": spec.loss_scale,
        "clip_threshold": spec.clip_threshold,
        "learning_rate": spec.learning_rate,
        "steps": steps,
        "clipped_steps": [item["step"] for item in steps if item["clipped"]],
        "clipped_step_count": sum(1 for item in steps if item["clipped"]),
    }


def artifact_convergence_report(spec, compiled, baseline):
    gates = spec.corpus.convergence_gates
    losses = [record["loss"] for record in compiled["steps"]]
    window = int(gates["slope_window"])
    if len(losses) >= window and window > 1:
        slope = rd((losses[-1] - losses[-window]) / float(window - 1), spec.decimals)
    else:
        slope = rd(losses[-1] - losses[0], spec.decimals)
    closing = losses[-1]
    base_closing = baseline["steps"][-1]["loss"]
    deviation = rd(abs(closing - base_closing) / abs(base_closing), spec.decimals) if base_closing else 0.0
    parity = deviation <= float(gates["parity_band"])
    met = parity and slope <= float(gates["max_slope"]) and closing <= float(gates["target_loss"])
    return {
        "run_id": spec.run_id,
        "slope_window": window,
        "windowed_slope": slope,
        "closing_loss": closing,
        "baseline_closing_loss": base_closing,
        "relative_deviation": deviation,
        "parity_band": float(gates["parity_band"]),
        "parity_holds": parity,
        "target_loss": float(gates["target_loss"]),
        "verdict": "met" if met else "unmet",
    }


def artifact_baseline_parity(spec, compiled, baseline):
    rows = []
    worst = 0.0
    worst_step = None
    for record, base in zip(compiled["steps"], baseline["steps"]):
        if base["loss"] == 0.0:
            deviation = 0.0
        else:
            deviation = rd(abs(record["loss"] - base["loss"]) / abs(base["loss"]), spec.decimals)
        rows.append({"step": record["step"], "relative_deviation": deviation})
        if deviation > worst:
            worst = deviation
            worst_step = record["step"]
    band = float(spec.corpus.convergence_gates["parity_band"])
    return {
        "run_id": spec.run_id,
        "steps": rows,
        "max_relative_deviation": rd(worst, spec.decimals),
        "max_deviation_step": worst_step,
        "parity_band": band,
        "parity_holds": worst <= band,
        "steps_outside_band": [item["step"] for item in rows if item["relative_deviation"] > band],
    }


def artifact_audit_statistics(spec, deployed, settled, settled_spec):
    def breaks_steps(run, predicate):
        return sum(1 for record in run["steps"] if record["breaks"] and predicate(record["step"]))

    def keys_for(run, wanted_router):
        found = set()
        for record in run["steps"]:
            for item in record["keys"]:
                is_router = item["code_object"] == "router"
                if is_router == wanted_router:
                    found.add(item["code_object"] + "@" + str(item["rank"]) + "#" + item["key"])
        return len(found)

    d_assign = sum(sum(record["demand"]) for record in deployed["steps"])
    d_tokens = sum(record["token_count"] for record in deployed["steps"])
    d_drops = sum(record["dropped_tokens"] for record in deployed["steps"])
    s_drops = sum(record["dropped_tokens"] for record in settled["steps"])
    s_tokens = sum(record["token_count"] for record in settled["steps"])
    d_attempts = sum(len(record["captures"]) for record in deployed["steps"])
    d_fail = sum(1 for record in deployed["steps"] for item in record["captures"] if not item["captured"])
    s_attempts = sum(len(record["captures"]) for record in settled["steps"])
    s_ok = sum(1 for record in settled["steps"] for item in record["captures"] if item["captured"])
    return {
        "deployed_recompiles_total": sum(record["recompiles"] for record in deployed["steps"]),
        "settled_recompiles_after_warmup": sum(record["recompiles"] for record in gated_steps(settled_spec, settled["steps"])),
        "deployed_distinct_capacity_values": len(set(
            value for record in deployed["steps"] for value in record["capacity"]
        )),
        "settled_distinct_rank_buckets": len(set(
            value for record in settled["steps"] for value in record["rank_bucket"].values()
        )),
        "deployed_drop_rate_assignment_denominator": rd(float(d_drops) / float(d_assign), spec.decimals) if d_assign else 0.0,
        "settled_drop_rate_token_denominator": rd(float(s_drops) / float(s_tokens), spec.decimals) if s_tokens else 0.0,
        "deployed_break_steps_inclusive_warmup": breaks_steps(deployed, lambda s: s <= spec.warmup_bound),
        "settled_break_steps_exclusive_warmup": breaks_steps(settled, lambda s: s > settled_spec.warmup_bound),
        "deployed_mean_host_bytes": rd(
            sum(record["host_bytes"] for record in deployed["steps"]) / float(len(deployed["steps"])),
            spec.decimals,
        ),
        "settled_peak_host_bytes": max(record["host_bytes"] for record in settled["steps"]),
        "deployed_capture_failure_ratio": rd(float(d_fail) / float(d_attempts), spec.decimals) if d_attempts else 0.0,
        "settled_capture_success_ratio": rd(float(s_ok) / float(s_attempts), spec.decimals) if s_attempts else 0.0,
        "deployed_empty_expert_step_count": sum(
            1 for record in deployed["steps"] if record["aux"]["empty_experts"]
        ),
        "settled_empty_expert_slot_count": sum(
            len(record["aux"]["empty_experts"]) for record in settled["steps"]
        ),
        "deployed_unique_guard_keys_router_only": keys_for(deployed, True),
        "settled_unique_guard_keys_moe_only": keys_for(settled, False),
        "deployed_token_total": d_tokens,
    }


def artifact_deployed_diagnosis(spec, run, baseline, bounds, register):
    published = spec.corpus.deployed_summary["published"]
    summary = run_summary(spec, run, baseline)
    replayed = {
        "closing_loss": summary["closing_loss"],
        "speedup": summary["speedup"],
        "recompiles_after_warmup": summary["recompiles_after_warmup"],
        "min_host_headroom_bytes": summary["min_host_headroom_bytes"],
        "drop_rate": summary["drop_rate"],
        "total_recompiles": sum(record["recompiles"] for record in run["steps"]),
    }
    comparison = {}
    for field in sorted(replayed):
        if field not in published:
            continue
        comparison[field] = {
            "published": published[field],
            "replayed": replayed[field],
            "signed_delta": rd(float(published[field]) - float(replayed[field]), spec.decimals),
        }
    departing = []
    for setting in sorted(bounds["settings"]):
        rule = bounds["settings"][setting]
        value = spec.config.get(setting)
        governing = effective_policy(register, rule["policy"])
        bad = False
        if "allowed_values" in rule:
            bad = value not in rule["allowed_values"]
        else:
            if float(value) < float(rule["minimum"]) or float(value) > float(rule["maximum"]):
                bad = True
        if bad:
            departing.append({
                "setting": setting,
                "value": value,
                "policy": rule["policy"],
                "revision": governing["revision"],
            })
    causes = {}
    for record in run["steps"]:
        for item in record["captures"]:
            if not item["captured"]:
                causes[item["cause"]] = causes.get(item["cause"], 0) + 1
    return {
        "run_id": spec.run_id,
        "published_vs_replayed": comparison,
        "departing_settings": departing,
        "capture_failure_causes": causes,
        "first_step_over_budget": first_over_budget(spec, run),
        "admissible": not departing and not gate_violations(spec, spec.compile_mode, summary),
        "published_agrees_with_replay": all(
            entry["signed_delta"] == 0.0 for entry in comparison.values()
        ),
    }


def artifact_settlement_report(spec, deployed_spec, settled, settled_spec, baseline, ledger, probe_steps, rows):
    summary = run_summary(settled_spec, settled, baseline)
    changed = []
    for field in ("capacity_factor", "capacity_bucket", "mark_dynamic", "compile_mode"):
        before = deployed_spec.config[field]
        after = settled_spec.config[field]
        if before != after:
            changed.append({"setting": field, "from": before, "to": after})
    return {
        "run_id": deployed_spec.run_id,
        "probe_steps": probe_steps,
        "candidates_evaluated": len(rows),
        "prefiltered_count": len(ledger["prefiltered"]),
        "rejected_count": len(ledger["rejected"]),
        "admissible_count": len(ledger["admissible_candidates"]),
        "settled_configuration": {
            "capacity_factor": settled_spec.capacity_factor,
            "capacity_bucket": settled_spec.capacity_bucket,
            "mark_dynamic": list(settled_spec.mark_dynamic),
            "compile_mode": settled_spec.compile_mode,
        },
        "settled_gate_figures": summary,
        "changed_settings": changed,
        "gates_met": {
            "recompile_budget": summary["recompiles_after_warmup"] <= int(spec.corpus.steptime_gates["recompile_budget"]),
            "speedup": summary["speedup"] >= float(spec.corpus.steptime_gates["min_speedup"]),
            "memory": summary["min_host_headroom_bytes"] >= 0,
            "convergence": summary["relative_deviation"] <= float(spec.corpus.convergence_gates["parity_band"]),
        },
    }


def artifact_sensitivity(spec, base_spec, rows, probe_steps, order):
    gates = spec.corpus.steptime_gates
    perturbations = spec.corpus.candidates["perturbations"]
    out = []
    cache = {}
    for item in perturbations:
        config = dict(base_spec.config)
        field = item["setting"]
        config[field] = base_spec.config[field] + item["delta"] if isinstance(base_spec.config[field], int) else base_spec.config[field]
        if field == "capacity_factor":
            config[field] = rd(float(base_spec.config[field]) + float(item["delta"]), spec.decimals)
        config["steps"] = probe_steps
        config["reset_steps"] = [v for v in base_spec.reset_steps if v <= probe_steps]
        probe = RunSpec(config, spec.corpus)
        probe.tiebreak_order = order
        compiled = simulate(probe, order)
        key = (probe.capacity_factor, probe.capacity_bucket)
        if key not in cache:
            twin = eager_twin(probe)
            cache[key] = simulate(twin, order, eager=True)
        summary = run_summary(probe, compiled, cache[key])
        out.append({
            "setting": field,
            "delta": item["delta"],
            "speedup_margin": rd(summary["speedup"] - float(gates["min_speedup"]), spec.time_decimals),
            "headroom_margin": summary["min_host_headroom_bytes"],
            "recompile_margin": int(gates["recompile_budget"]) - summary["recompiles_after_warmup"],
        })
    out.sort(key=lambda entry: (entry["setting"], entry["delta"]))
    return {
        "run_id": base_spec.run_id,
        "probe_steps": probe_steps,
        "perturbations": out,
        "negative_speedup_margins": [
            entry["setting"] for entry in out if entry["speedup_margin"] < 0
        ],
        "negative_headroom_margins": [
            entry["setting"] for entry in out if entry["headroom_margin"] < 0
        ],
    }


def artifact_validation_report(spec, artifacts, deployed_run, baseline):
    summary = run_summary(spec, deployed_run, baseline)
    published = spec.corpus.deployed_summary["published"]
    residuals = {}
    for field in sorted(published):
        if field in summary:
            residuals[field] = rd(float(published[field]) - float(summary[field]), spec.decimals)
    counts = {}
    for name in sorted(artifacts):
        payload = artifacts[name]
        if isinstance(payload, dict) and isinstance(payload.get("steps"), list):
            counts[name] = len(payload["steps"])
        elif isinstance(payload, dict):
            counts[name] = len(payload)
        else:
            counts[name] = 0
    return {
        "residuals": residuals,
        "record_counts": counts,
        "max_absolute_residual": rd(max((abs(v) for v in residuals.values()), default=0.0), spec.decimals),
        "artifact_count": len(artifacts),
        "float_decimals": spec.decimals,
        "time_decimals": spec.time_decimals,
    }


# ------------------------------------------------------ self contained inputs


CORPUS_FILES = {
    "tolerances": "validation_tolerances.json",
    "run_config": "sample_run_config.json",
    "calibration_config": "calibration_config.json",
    "deployed_config": "deployed_config.json",
    "topology": "model_topology.json",
    "candidates": "capacity_candidates.json",
    "convergence_gates": "convergence_gates.json",
    "steptime_gates": "steptime_gates.json",
    "memory_gates": "memory_gates.json",
    "warmup_windows": "warmup_windows.json",
    "rank_inventory": "ep_rank_inventory.json",
    "probes": "probe_configurations.json",
    "sealed_precedence": "sealed_precedence_digests.json",
    "sealed_tiebreak": "sealed_tiebreak_digests.json",
    "revisions": "revision_register.json",
    "bounds": "contract_bounds.json",
    "deployed_summary": "deployed_run_summary.json",
    "deployed_mesh": "deployed_mesh_dump.json",
    "eager_baseline": "eager_baseline.json",
    "expert_cost": "expert_cost_table.csv",
    "expert_bias": "expert_bias_table.csv",
    "expert_placement": "expert_placement.csv",
    "compile_cost": "compile_cost_table.csv",
    "capture_cost": "capture_cost_table.csv",
    "alltoall_cost": "alltoall_cost_table.csv",
    "memory_slots": "memory_slot_table.csv",
    "pool_blocks": "pool_block_table.csv",
    "seq_schedule": "seq_length_schedule.csv",
    "rank_affinity": "rank_affinity.csv",
    "break_catalog": "graph_break_catalog.csv",
    "calibration_parity": "calibration_parity.jsonl",
    "deployed_compile_log": "deployed_compile_log.jsonl",
    "deployed_step_timeline": "deployed_step_timeline.jsonl",
    "deployed_guard_dump": "deployed_guard_dump.jsonl",
    "deployed_alltoall": "deployed_alltoall_trace.jsonl",
    "deployed_memory": "deployed_memory_trace.csv",
    "token_batches": "token_batches.jsonl",
}


def corpus_from_document(document):
    obj = Corpus.__new__(Corpus)
    obj.base = None
    tables = document["tables"]
    for attribute, name in CORPUS_FILES.items():
        setattr(obj, attribute, tables[name])
    obj.tolerances = tables["validation_tolerances.json"]
    obj.decimals = int(obj.tolerances["float_decimals"])
    obj.time_decimals = int(obj.tolerances["time_decimals"])
    return obj


def sealed_config(corpus, name):
    if name == "calibration":
        return corpus.calibration_config
    return corpus.probes[name]


# ------------------------------------------------------------------- resolve


def resolve_tiebreak_key(corpus):
    tie_matches = None
    for name in sorted(corpus.sealed_tiebreak["digests"]):
        found = set(tuple(order) for order in resolve_tiebreak(corpus, name, sealed_config(corpus, name)))
        tie_matches = found if tie_matches is None else (tie_matches & found)
    if not tie_matches:
        raise SystemExit("no tie break key reproduces the sealed digests")
    return list(sorted(tie_matches)[0]), len(tie_matches)


def resolve_policies(corpus):
    probe_steps = int(corpus.candidates["probe_steps"])
    tie_matches = None
    for name in sorted(corpus.sealed_tiebreak["digests"]):
        found = set(tuple(order) for order in resolve_tiebreak(corpus, name, sealed_config(corpus, name)))
        tie_matches = found if tie_matches is None else (tie_matches & found)
    if not tie_matches:
        raise SystemExit("no tie break key reproduces the sealed digests")
    order = list(sorted(tie_matches)[0])
    rows_by_config = {}
    for name in sorted(corpus.sealed_precedence["digests"]):
        spec = make_spec(corpus, sealed_config(corpus, name), order)
        run = simulate(spec, order)
        rows_by_config[name] = {
            "spec": spec,
            "profile": build_warmup_profile(spec, run),
            "rows": sweep(spec, probe_steps),
        }
    precedence = resolve_precedence(corpus, rows_by_config, corpus.sealed_precedence)
    if not precedence:
        raise SystemExit("no precedence order reproduces the sealed digests")
    return {
        "tie_break_key": order,
        "tie_break_matches": len(tie_matches),
        "tie_break_candidates_enumerated": len(tiebreak_candidates()),
        "precedence_order": precedence[0],
        "precedence_matches": len(precedence),
        "precedence_candidates_enumerated": len(precedence_candidates()),
        "sealed_configs": sorted(corpus.sealed_precedence["digests"]),
    }


# --------------------------------------------------------------------- build


def build_all(corpus):
    resolution = resolve_policies(corpus)
    order = resolution["tie_break_key"]
    precedence = resolution["precedence_order"]
    probe_steps = int(corpus.candidates["probe_steps"])

    deployed_spec = make_spec(corpus, corpus.deployed_config, order)
    deployed = simulate(deployed_spec, order)
    deployed_base = simulate(eager_twin(deployed_spec), order, eager=True)
    profile = build_warmup_profile(deployed_spec, deployed)
    rows = sweep(deployed_spec, probe_steps)
    ledger = build_rejection_ledger(deployed_spec, rows, profile, precedence)
    chosen = select_candidate(ledger["admissible_candidates"], rows)
    if chosen is None:
        raise SystemExit("no admissible candidate survives the shipped gates")

    settled_config = dict(corpus.deployed_config)
    settled_config["capacity_factor"] = chosen["capacity_factor"]
    settled_config["capacity_bucket"] = chosen["capacity_bucket"]
    settled_config["mark_dynamic"] = list(chosen["mark_dynamic"])
    settled_config["compile_mode"] = chosen["compile_mode"]
    settled_config["run_id"] = str(corpus.deployed_config["run_id"]) + "-settled"
    settled_spec = make_spec(corpus, settled_config, order)
    settled = simulate(settled_spec, order)
    settled_base = simulate(eager_twin(settled_spec), order, eager=True)

    artifacts = {}
    artifacts["route_plan.json"] = artifact_route_plan(deployed_spec, deployed)
    artifacts["capacity_plan.json"] = artifact_capacity_plan(deployed_spec, deployed)
    artifacts["mesh_plan.json"] = artifact_mesh_plan(deployed_spec, deployed)
    artifacts["dispatch_ledger.json"] = artifact_dispatch_ledger(deployed_spec, deployed)
    artifacts["drop_ledger.json"] = artifact_drop_ledger(deployed_spec, deployed)
    artifacts["alltoall_ledger.json"] = artifact_alltoall_ledger(deployed_spec, deployed)
    artifacts["guard_key_index.json"] = artifact_guard_key_index(deployed_spec, deployed)
    artifacts["recompile_report.json"] = artifact_recompile_report(deployed_spec, deployed)
    artifacts["graph_break_ledger.json"] = artifact_graph_break_ledger(deployed_spec, deployed)
    artifacts["cudagraph_report.json"] = artifact_cudagraph_report(deployed_spec, deployed)
    artifacts["host_memory_report.json"] = artifact_host_memory_report(deployed_spec, deployed)
    artifacts["steptime_report.json"] = artifact_steptime_report(deployed_spec, deployed, deployed_base)
    artifacts["warmup_profile.json"] = profile
    artifacts["sealed_policy_resolution.json"] = resolution

    artifacts["aux_loss_trace.json"] = artifact_aux_loss_trace(settled_spec, settled)
    artifacts["loss_curve.json"] = artifact_loss_curve(settled_spec, settled, settled_base)
    artifacts["gradient_ledger.json"] = artifact_gradient_ledger(settled_spec, settled)
    artifacts["optimizer_trace.json"] = artifact_optimizer_trace(settled_spec, settled)
    artifacts["convergence_report.json"] = artifact_convergence_report(settled_spec, settled, settled_base)
    artifacts["baseline_parity.json"] = artifact_baseline_parity(settled_spec, settled, settled_base)
    artifacts["settlement_report.json"] = artifact_settlement_report(
        deployed_spec, deployed_spec, settled, settled_spec, settled_base, ledger, probe_steps, rows
    )
    artifacts["rejection_ledger.json"] = ledger
    artifacts["sensitivity.json"] = artifact_sensitivity(deployed_spec, settled_spec, rows, probe_steps, order)
    artifacts["audit_statistics.json"] = artifact_audit_statistics(
        deployed_spec, deployed, settled, settled_spec
    )
    artifacts["deployed_diagnosis.json"] = artifact_deployed_diagnosis(
        deployed_spec, deployed, deployed_base, corpus.bounds, corpus.revisions
    )
    artifacts["validation_report.json"] = artifact_validation_report(
        deployed_spec, artifacts, deployed, deployed_base
    )
    return artifacts


def build(data_dir, out_dir):
    corpus = Corpus(data_dir)
    artifacts = build_all(corpus)
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    stage_digests = {}
    for name in STAGE_ARTIFACTS:
        stage_digests[name] = write_json(os.path.join(out_dir, name), artifacts[name])
    stage_manifest = {
        "stage": "dispatch_and_compile",
        "artifact_count": len(STAGE_ARTIFACTS),
        "artifact_sha256": stage_digests,
    }
    stage_bytes = canonical_bytes(stage_manifest)
    with open(os.path.join(out_dir, "stage_manifest.json"), "wb") as handle:
        handle.write(stage_bytes)
    replay_digests = {}
    for name in REPLAY_ARTIFACTS:
        replay_digests[name] = write_json(os.path.join(out_dir, name), artifacts[name])
    replay_manifest = {
        "stage": "replay_and_settlement",
        "artifact_count": len(REPLAY_ARTIFACTS),
        "artifact_sha256": replay_digests,
        "stage_manifest_sha256": sha256_hex(stage_bytes),
    }
    replay_bytes = canonical_bytes(replay_manifest)
    with open(os.path.join(out_dir, "replay_manifest.json"), "wb") as handle:
        handle.write(replay_bytes)
    settlement = artifacts["settlement_report.json"]["settled_configuration"]
    salt = digest_of(settlement)
    folded = {
        "replay": sha256_hex(replay_bytes),
        "salt": salt,
        "stage": sha256_hex(stage_bytes),
    }
    final_state = {
        "closing_loss": artifacts["convergence_report.json"]["closing_loss"],
        "convergence_verdict": artifacts["convergence_report.json"]["verdict"],
        "deployed_admissible": artifacts["deployed_diagnosis.json"]["admissible"],
        "digest_of_digests": digest_of(folded),
        "first_step_over_budget": artifacts["recompile_report.json"]["first_step_over_budget"],
        "precedence_order": artifacts["sealed_policy_resolution.json"]["precedence_order"],
        "replay_manifest_sha256": folded["replay"],
        "settled_configuration": settlement,
        "settlement_salt": salt,
        "speedup": artifacts["settlement_report.json"]["settled_gate_figures"]["speedup"],
        "stage_manifest_sha256": folded["stage"],
        "tie_break_key": artifacts["sealed_policy_resolution.json"]["tie_break_key"],
        "total_artifacts": len(STAGE_ARTIFACTS) + len(REPLAY_ARTIFACTS) + 3,
    }
    write_json(os.path.join(out_dir, "final_state.json"), final_state)
    return artifacts


# ----------------------------------------------------------------------- cli


def verb_trace(document):
    corpus = corpus_from_document(document)
    order, matched = resolve_tiebreak_key(corpus)
    spec = make_spec(corpus, document["config"], order)
    run = simulate(spec, order)
    return {
        "tie_break_key": order,
        "tie_break_matches": matched,
        "guard_key_index": artifact_guard_key_index(spec, run),
        "recompile_report": artifact_recompile_report(spec, run),
        "graph_break_ledger": artifact_graph_break_ledger(spec, run),
        "cudagraph_report": artifact_cudagraph_report(spec, run),
        "capacity_plan": artifact_capacity_plan(spec, run),
        "mesh_plan": artifact_mesh_plan(spec, run),
        "host_memory_report": artifact_host_memory_report(spec, run),
        "warmup_profile": build_warmup_profile(spec, run),
    }


def verb_replay(document):
    corpus = corpus_from_document(document)
    order, matched = resolve_tiebreak_key(corpus)
    spec = make_spec(corpus, document["config"], order)
    run = simulate(spec, order)
    base = simulate(eager_twin(spec), order, eager=True)
    return {
        "tie_break_key": order,
        "tie_break_matches": matched,
        "route_plan": artifact_route_plan(spec, run),
        "dispatch_ledger": artifact_dispatch_ledger(spec, run),
        "drop_ledger": artifact_drop_ledger(spec, run),
        "alltoall_ledger": artifact_alltoall_ledger(spec, run),
        "aux_loss_trace": artifact_aux_loss_trace(spec, run),
        "loss_curve": artifact_loss_curve(spec, run, base),
        "gradient_ledger": artifact_gradient_ledger(spec, run),
        "optimizer_trace": artifact_optimizer_trace(spec, run),
        "convergence_report": artifact_convergence_report(spec, run, base),
        "baseline_parity": artifact_baseline_parity(spec, run, base),
        "steptime_report": artifact_steptime_report(spec, run, base),
    }


def verb_settle(document):
    corpus = corpus_from_document(document)
    resolution = resolve_policies(corpus)
    order = resolution["tie_break_key"]
    probe_steps = int(corpus.candidates["probe_steps"])
    spec = make_spec(corpus, document["config"], order)
    run = simulate(spec, order)
    profile = build_warmup_profile(spec, run)
    rows = sweep(spec, probe_steps)
    ledger = build_rejection_ledger(spec, rows, profile, resolution["precedence_order"])
    chosen = select_candidate(ledger["admissible_candidates"], rows)
    return {
        "rejection_ledger": ledger,
        "warmup_profile": profile,
        "settled_configuration": chosen,
        "probe_steps": probe_steps,
    }


def verb_resolve(document):
    return resolve_policies(corpus_from_document(document))


def main(argv):
    if len(argv) < 2:
        raise SystemExit("usage: moeplan build DATA_DIR OUT_DIR | trace|replay|settle|resolve DOCUMENT")
    verb = argv[1]
    if verb == "build":
        if len(argv) != 4:
            raise SystemExit("usage: moeplan build DATA_DIR OUT_DIR")
        artifacts = build(argv[2], argv[3])
        settlement = artifacts["settlement_report.json"]
        sys.stdout.write(
            "settled cf={0} bucket={1} dynamic={2} mode={3} speedup={4} closing_loss={5}\n".format(
                settlement["settled_configuration"]["capacity_factor"],
                settlement["settled_configuration"]["capacity_bucket"],
                "+".join(settlement["settled_configuration"]["mark_dynamic"]) or "none",
                settlement["settled_configuration"]["compile_mode"],
                settlement["settled_gate_figures"]["speedup"],
                artifacts["convergence_report.json"]["closing_loss"],
            )
        )
        return 0
    if verb not in ("trace", "replay", "settle", "resolve"):
        raise SystemExit("unknown verb " + str(verb))
    if len(argv) != 3:
        raise SystemExit("usage: moeplan " + verb + " DOCUMENT")
    document = read_json(argv[2])
    handler = {
        "trace": verb_trace,
        "replay": verb_replay,
        "settle": verb_settle,
        "resolve": verb_resolve,
    }[verb]
    sys.stdout.write(canonical_bytes(handler(document)).decode("utf-8"))
    return 0



# =============================================================== corpus build
# The encoder below produced the shipped environment/data tree. Running this
# module with a directory argument rewrites that tree byte for byte.

SAMPLE_SEED = 0x5A17C0DE2024
CHALLENGE_SEED = 0x7F31B90455AA
EVAL_SEED = 0x2C4E8811D3F7

# The held out corpus the verifier builds beside the shipped one. Same prose,
# same tables and sealed configurations, a different deployed run and
# different gates, chosen so that every cause fires in its sweep and every
# adjacent pair of the resolved cause order is present together on some row.
EVAL_VARIANT = {
    "tables": {
        "memory_gates.json": {"capacity_floor": 8, "host_ceiling_bytes": 314572800},
        "convergence_gates.json": {"max_drop_rate": 0.02, "settlement_parity_band": 0.00003},
    },
    "deployed_tokens": [40, 56, 48, 72, 40, 64, 56, 80, 48, 72, 64, 40,
                        80, 56, 72, 48, 64, 80, 40, 56, 72, 64, 48, 80],
    "deployed": {"run_id": "moe-run-8120", "num_experts": 12, "ep_world_size": 4,
                 "steps": 60, "warmup_bound": 4, "capacity_factor": 1.75,
                 "capacity_bucket": 6, "min_capacity": 4, "cache_size_limit": 6,
                 "promotion_threshold": 3, "seed": 77031529},
}

TRUE_TIEBREAK_ORDER = ["placement_rank", "bias_rank", "running_load", "expert_index"]
TRUE_PRECEDENCE = [
    "eager_mode_forbidden",
    "capacity_below_minimum",
    "memory_ceiling_exceeded",
    "recompile_budget_exceeded",
    "convergence_band_unmet",
    "drop_tolerance_exceeded",
    "speedup_gate_unmet",
]

MAX_EXPERTS = 16


def _csv(rows, header):
    lines = [",".join(header)]
    for row in rows:
        lines.append(",".join(str(row[name]) for name in header))
    return "\n".join(lines) + "\n"


def _jsonl(rows):
    return "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows)


def _fmt(value):
    text = ("%.6f" % float(value)).rstrip("0")
    if text.endswith("."):
        text += "0"
    return text


def _seq_rows(variant=None):
    rows = []
    for step in range(1, 9):
        rows.append({"profile": "sample", "step": step, "tokens": 64})
    calibration = [72, 80, 72, 96, 80, 64, 96, 72, 88, 64, 80, 96, 72, 88, 64, 80, 96, 88, 72, 64]
    for index, tokens in enumerate(calibration):
        rows.append({"profile": "calibration", "step": index + 1, "tokens": tokens})
    alpha = [56, 72, 64, 88, 56, 96, 72, 64, 88, 96, 56, 72]
    for index, tokens in enumerate(alpha):
        rows.append({"profile": "probe_alpha", "step": index + 1, "tokens": tokens})
    deployed = [
        96, 112, 88, 128, 96, 80, 112, 128, 88, 96,
        120, 80, 104, 128, 96, 112, 88, 120, 104, 80,
        128, 96, 112, 88, 104, 120, 80, 96, 128, 112,
        88, 104, 96, 120, 80, 128, 112, 96, 104, 88,
    ]
    if variant is not None:
        deployed = list(variant["deployed_tokens"])
    for index, tokens in enumerate(deployed):
        rows.append({"profile": "deployed", "step": index + 1, "tokens": tokens})
    return rows


def _static_tables(variant=None):
    tables = {}
    tables["validation_tolerances.json"] = {
        "comparison": "exact",
        "float_decimals": 12,
        "time_decimals": 6,
        "note": "every published figure is compared for exact equality after rounding",
    }
    tables["model_topology.json"] = {
        "d_model": 1024,
        "d_ff": 4096,
        "num_layers": 12,
        "router": {"jitter_scale": 0.35, "quantization_levels": 64},
        "surrogate": {
            "base_loss": 2.5,
            "decay_rate": 0.02,
            "payload_scale": 64.0,
            "signal_weight": 0.18,
        },
    }
    tables["memory_gates.json"] = {
        "capacity_floor": 8,
        "host_base_bytes": 268435456,
        "host_ceiling_bytes": 301989888,
    }
    tables["steptime_gates.json"] = {
        "eager_compute_multiplier": 2.9,
        "fallback_compile_us": 3300.0,
        "min_speedup": 2.2,
        "recompile_budget": 0,
        "sync_bubble_us": 450.0,
    }
    tables["convergence_gates.json"] = {
        "max_drop_rate": 0.06,
        "max_slope": 0.0,
        "parity_band": 0.0009,
        "settlement_parity_band": 0.0005,
        "slope_window": 8,
        "target_loss": 3.0,
    }
    tables["capacity_candidates.json"] = {
        "capacity_bucket": [4, 8],
        "capacity_factor": [1.0, 1.25, 1.5],
        "compile_mode": ["reduce-overhead", "default", "eager"],
        "mark_dynamic": [[], ["tokens"], ["capacity", "tokens"]],
        "perturbations": [
            {"delta": 0.25, "setting": "capacity_factor"},
            {"delta": -0.25, "setting": "capacity_factor"},
            {"delta": 1, "setting": "cache_size_limit"},
            {"delta": -1, "setting": "promotion_threshold"},
        ],
        "probe_steps": 10,
    }
    tables["warmup_windows.json"] = {
        "inclusive_upper_bound": True,
        "gate_window_is_strictly_after_bound": True,
        "profiles": {"calibration": 4, "deployed": 5, "probe_alpha": 3, "sample": 2},
    }
    tables["ep_rank_inventory.json"] = {
        "supported_world_sizes": [1, 2, 4, 8],
        "device_slots_per_rank": 1,
        "collective_backend": "alltoall_single",
        "uniform_bucket_required": True,
    }
    tables["contract_bounds.json"] = {
        "settings": {
            "capacity_bucket": {"allowed_values": [4, 8], "policy": "capacity"},
            "capacity_factor": {"maximum": 1.5, "minimum": 1.0, "policy": "capacity"},
            "cache_size_limit": {"maximum": 64, "minimum": 12, "policy": "cache"},
            "compile_mode": {"allowed_values": ["reduce-overhead", "default"], "policy": "compile"},
            "min_capacity": {"maximum": 8, "minimum": 4, "policy": "capacity"},
            "promotion_threshold": {"maximum": 3, "minimum": 2, "policy": "guard"},
        }
    }
    tables["revision_register.json"] = {
        "revisions": [
            {"policy": "capacity", "revision": "cap-r1", "effective_order": 1, "status": "superseded",
             "summary": "hold at the minimum before aligning to the bucket"},
            {"policy": "capacity", "revision": "cap-r2", "effective_order": 2, "status": "applied",
             "summary": "align to the bucket and only then hold at the minimum"},
            {"policy": "guard", "revision": "guard-r1", "effective_order": 1, "status": "superseded",
             "summary": "count distinct shapes seen before the pending compilation"},
            {"policy": "guard", "revision": "guard-r2", "effective_order": 2, "status": "applied",
             "summary": "count the pending shape within the distinct shape total"},
            {"policy": "cache", "revision": "cache-r1", "effective_order": 1, "status": "applied",
             "summary": "least recently used eviction with the smallest key breaking a tie"},
            {"policy": "compile", "revision": "compile-r1", "effective_order": 1, "status": "applied",
             "summary": "capture is attempted only under the reduce overhead mode"},
            {"policy": "aux", "revision": "aux-r1", "effective_order": 1, "status": "superseded",
             "summary": "balance term sourced from accepted assignments"},
            {"policy": "aux", "revision": "aux-r2", "effective_order": 2, "status": "applied",
             "summary": "balance term sourced from demand recorded before capacity is applied"},
            {"policy": "pool", "revision": "pool-r1", "effective_order": 1, "status": "applied",
             "summary": "the running peak restarts once the reported figure for the step is final"},
        ]
    }
    if variant is not None:
        for name, patch in variant["tables"].items():
            tables[name] = dict(tables[name], **patch)
    return tables


def _table_files(variant=None):
    files = {}
    cost = []
    bias = []
    placement = []
    for e in range(MAX_EXPERTS):
        cost.append({
            "expert_index": e,
            "cost_weight": _fmt(0.80 + 0.03 * e),
            "kernel_us_per_slot": _fmt(4.5 + 0.5 * (e % 4)),
        })
        bias.append({"expert_index": e, "bias_gain": _fmt(0.10 + 0.02 * e)})
        placement.append({
            "expert_index": e,
            "placement_group": (e * 5 + 3) % 4,
            "affinity_weight": _fmt(1.0 + 0.1 * e),
        })
    files["expert_cost_table.csv"] = _csv(cost, ["expert_index", "cost_weight", "kernel_us_per_slot"])
    files["expert_bias_table.csv"] = _csv(bias, ["expert_index", "bias_gain"])
    files["expert_placement.csv"] = _csv(placement, ["expert_index", "placement_group", "affinity_weight"])

    affinity = []
    for world in (1, 2, 4, 8):
        for rank in range(world):
            affinity.append({"ep_world_size": world, "rank": rank, "group_order": world - 1 - rank})
    files["rank_affinity.csv"] = _csv(affinity, ["ep_world_size", "rank", "group_order"])

    compile_rows = []
    for mode, base in (("reduce-overhead", 2500.0), ("default", 1900.0), ("eager", 0.0)):
        for static in range(4):
            value = 0.0 if mode == "eager" else base + 800.0 * static
            compile_rows.append({
                "compile_mode": mode, "static_dims": static, "compile_us": _fmt(value),
            })
    files["compile_cost_table.csv"] = _csv(compile_rows, ["compile_mode", "static_dims", "compile_us"])

    capture_rows = [
        {"compile_mode": "reduce-overhead", "capture_us": _fmt(60.0), "replay_discount": _fmt(0.34)},
        {"compile_mode": "default", "capture_us": _fmt(0.0), "replay_discount": _fmt(0.86)},
        {"compile_mode": "eager", "capture_us": _fmt(0.0), "replay_discount": _fmt(1.0)},
    ]
    files["capture_cost_table.csv"] = _csv(capture_rows, ["compile_mode", "capture_us", "replay_discount"])

    alltoall_rows = [
        {"ep_world_size": 1, "fixed_us": _fmt(0.0), "per_slot_us": _fmt(0.0)},
        {"ep_world_size": 2, "fixed_us": _fmt(12.0), "per_slot_us": _fmt(0.04)},
        {"ep_world_size": 4, "fixed_us": _fmt(18.0), "per_slot_us": _fmt(0.06)},
        {"ep_world_size": 8, "fixed_us": _fmt(30.0), "per_slot_us": _fmt(0.09)},
    ]
    files["alltoall_cost_table.csv"] = _csv(alltoall_rows, ["ep_world_size", "fixed_us", "per_slot_us"])

    slot_rows = [
        {"static_dims": 0, "entry_bytes": 1572864, "guard_bytes": 65536},
        {"static_dims": 1, "entry_bytes": 1310720, "guard_bytes": 57344},
        {"static_dims": 2, "entry_bytes": 1048576, "guard_bytes": 49152},
        {"static_dims": 3, "entry_bytes": 786432, "guard_bytes": 40960},
    ]
    files["memory_slot_table.csv"] = _csv(slot_rows, ["static_dims", "entry_bytes", "guard_bytes"])

    pool_rows = [
        {"capacity_ceiling": 8, "block_bytes": 2097152},
        {"capacity_ceiling": 16, "block_bytes": 4194304},
        {"capacity_ceiling": 32, "block_bytes": 8388608},
        {"capacity_ceiling": 64, "block_bytes": 16777216},
        {"capacity_ceiling": 256, "block_bytes": 33554432},
    ]
    files["pool_block_table.csv"] = _csv(pool_rows, ["capacity_ceiling", "block_bytes"])

    catalog = [
        {"cause_id": 1, "cause": "data_dependent_capacity", "bubble_us": _fmt(26.0)},
        {"cause_id": 2, "cause": "dynamic_token_count", "bubble_us": _fmt(18.0)},
        {"cause_id": 3, "cause": "token_drop_mask", "bubble_us": _fmt(32.0)},
        {"cause_id": 4, "cause": "unbalanced_expert_slice", "bubble_us": _fmt(14.0)},
        {"cause_id": 5, "cause": "zero_token_expert", "bubble_us": _fmt(22.0)},
    ]
    files["graph_break_catalog.csv"] = _csv(catalog, ["cause_id", "cause", "bubble_us"])
    files["seq_length_schedule.csv"] = _csv(_seq_rows(variant), ["profile", "step", "tokens"])
    return files


def _configs(variant=None):
    sample = {
        "run_id": "moe-sample-0001",
        "num_experts": 4,
        "top_k": 2,
        "ep_world_size": 1,
        "steps": 8,
        "warmup_bound": 2,
        "seq_profile": "sample",
        "capacity_factor": 1.5,
        "capacity_bucket": 8,
        "min_capacity": 8,
        "cache_size_limit": 32,
        "promotion_threshold": 3,
        "dynamic_promotion_enabled": False,
        "expert_bias_enabled": False,
        "router_jitter_slots": 0,
        "compile_mode": "reduce-overhead",
        "mark_dynamic": [],
        "loss_scale": 1024.0,
        "learning_rate": 0.05,
        "clip_threshold": 1.0,
        "aux_loss_weight": 0.01,
        "reset_steps": [],
        "seed": 11412171,
        "moe_layer_indices": [3, 7],
    }
    calibration = {
        "run_id": "moe-calibration-0001",
        "num_experts": 8,
        "top_k": 2,
        "ep_world_size": 4,
        "steps": 20,
        "warmup_bound": 4,
        "seq_profile": "calibration",
        "capacity_factor": 1.25,
        "capacity_bucket": 4,
        "min_capacity": 6,
        "cache_size_limit": 16,
        "promotion_threshold": 3,
        "dynamic_promotion_enabled": True,
        "expert_bias_enabled": True,
        "router_jitter_slots": 5,
        "compile_mode": "reduce-overhead",
        "mark_dynamic": [],
        "loss_scale": 1024.0,
        "learning_rate": 0.05,
        "clip_threshold": 1.0,
        "aux_loss_weight": 0.01,
        "reset_steps": [13],
        "seed": 30219977,
        "moe_layer_indices": [3, 7, 11],
    }
    probe_alpha = dict(calibration)
    probe_alpha.update({
        "run_id": "moe-probe-alpha",
        "num_experts": 16,
        "ep_world_size": 8,
        "steps": 12,
        "warmup_bound": 3,
        "seq_profile": "probe_alpha",
        "capacity_factor": 1.0,
        "capacity_bucket": 8,
        "min_capacity": 5,
        "cache_size_limit": 10,
        "promotion_threshold": 2,
        "reset_steps": [],
        "seed": 51330941,
    })
    deployed = {
        "run_id": "moe-run-7734",
        "num_experts": 8,
        "top_k": 2,
        "ep_world_size": 4,
        "steps": 100,
        "warmup_bound": 5,
        "seq_profile": "deployed",
        "capacity_factor": 2.0,
        "capacity_bucket": 3,
        "min_capacity": 10,
        "cache_size_limit": 8,
        "promotion_threshold": 24,
        "dynamic_promotion_enabled": True,
        "expert_bias_enabled": True,
        "router_jitter_slots": 5,
        "compile_mode": "reduce-overhead",
        "mark_dynamic": [],
        "loss_scale": 1024.0,
        "learning_rate": 0.05,
        "clip_threshold": 1.0,
        "aux_loss_weight": 0.01,
        "reset_steps": [],
        "seed": 20240917,
        "moe_layer_indices": [3, 7, 11],
    }
    if variant is not None:
        deployed = dict(deployed, **variant["deployed"])
    return sample, calibration, probe_alpha, deployed


DOCS = {}

DOCS["glossary.md"] = """# Glossary and reading order

This corpus describes one mixture of experts training run that regressed. Read
this file first, then the contracts it names.

- assignment: one pair of a token and an expert chosen for it. With top k
  dispatch each token produces `top_k` assignments.
- demand: for an expert, the number of assignments naming it in a step, counted
  before any capacity limit is applied.
- capacity: the padded slot count reserved for one expert in one step. It is the
  second dimension of the dispatch tensor and therefore part of a guard key.
- rank bucket: the slot count a single expert parallel rank must allocate. Every
  expert living on that rank is padded to it.
- all to all bucket: the slot count every rank exchanges. The collective forces
  one figure across the whole mesh.
- guard key: the tuple TorchDynamo compares to decide whether a compiled entry
  can be reused.
- recompile: a compilation triggered because no cached entry matched the guard
  key.
- promotion: the moment a dimension stops being specialised and starts being
  treated as dynamic.
- capture: recording a compiled region into a graph replay pool.
- warmup window: the leading steps excluded from the throughput and recompile
  gates.

Reading order that matches the pipeline:
`stream_contract.md`, `routing_contract.md`, `capacity_contract.md`,
`mesh_contract.md`, `alltoall_contract.md`, `guard_semantics.md`,
`recompile_policy.md`, `cudagraph_policy.md`, `host_memory_model.md`,
`steptime_model.md`, `numeric_contract.md`, `aux_loss_contract.md`,
`optimizer_contract.md`, `warmup_contract.md`, `settlement_procedure.md`,
`precedence_constraints.md`, `sealed_policy_notes.md`, `audit_definitions.md`,
`enumeration_order.md`, `output_schema.md`.

Background material: `incident_report.md`, `fault_report.md`,
`compile_flags.md`, `fp8_format_notes.md`, `worked_step.md`,
`unreachable_branches.md`, `revision_history.md`, `legacy_planner_notes.md`.

Two rules used by this pipeline are deliberately absent from the prose. See
`sealed_policy_notes.md` for the sealed evidence that pins them down.
"""

DOCS["stream_contract.md"] = """# Deterministic input stream

Every run is reproducible from its configuration alone. No file records the
per step token features; they are drawn.

## Generator

A 64 bit xorshift with the update applied in this order, all arithmetic masked
to 64 bits:

```
x ^= (x << 13)
x ^= (x >> 7)
x ^= (x << 17)
```

`next_u64` applies the update and returns the new state. A unit draw is
`(state >> 11) * 2 ** -53`. A zero seed is replaced by `0x9E3779B97F4A7C15`.

## Per step seed

```
h = 0xCBF29CE484222325
for part in (config.seed, step):
    h ^= part
    h = (h * 0x100000001B3) mod 2**64
    h ^= (h >> 29)
```

The step index is one based. The generator is constructed fresh for every step
from `h`.

## Consumption order

Exactly these blocks are drawn, in this order, and nothing else:

```
for count in (tokens_in_step,
              num_experts,
              num_experts if expert_bias_enabled else 0,
              router_jitter_slots):
    draw count unit values
```

The first block is `token_salt`, the second is `expert_phase`, the third is
`bias_draw`, the fourth is `jitter`. When `expert_bias_enabled` is false the
third block consumes nothing at all and every `bias_draw` entry is treated as
`0.5`, which the routing contract then turns into a zero bias.

`tokens_in_step` is read from `seq_length_schedule.csv` for the profile named by
the configuration, ordered by the `step` column, cycled when the run is longer
than the schedule.
"""

DOCS["routing_contract.md"] = """# Router and top k dispatch

## Logit

For token `i` and expert `e`, with `J = router_jitter_slots`:

```
token_bits[i]  = floor(token_salt[i] * 2 ** 52)
expert_bits[e] = floor(expert_phase[e] * 2 ** 52)
affinity(i, e) = the value returned by one update of the stream generator seeded
                 with the mixing hash of token_bits[i] and expert_bits[e]
u(i, e)        = (affinity(i, e) >> 11) * 2 ** -53
b_e            = (bias_draw[e] * 2 - 1) * bias_gain[e] when the bias is enabled,
                 otherwise 0
j_ie           = (jitter[(i + e) mod J] * 2 - 1) * jitter_scale when J > 0,
                 otherwise 0

logit(i, e) = (u(i, e) * 2 - 1) + b_e + j_ie
```

The mixing hash is the one named in `stream_contract.md`, fed the two integers in
that order. The generator is constructed from the hash and updated once; the
returned state is the affinity. `bias_gain` comes from `expert_bias_table.csv`
and `jitter_scale` from `model_topology.json`. Every named quantity above is
rounded to the published decimal count before the next one consumes it.

## Quantisation

Ranking never sees the raw logit. It sees

```
q(i, e) = round_half_even(logit(i, e) * quantization_levels) / quantization_levels
```

with `quantization_levels` from `model_topology.json`. Half way values round to
the even multiple. Ties on `q` are common and are resolved by the sealed key.

## Selection

Experts are ordered by descending `q`, and ties on `q` are broken by a sort key
built from four fields whose order is sealed rather than printed here. The first
`top_k` experts in that order are selected. Tokens are processed in ascending
token index and the four fields are

- `expert_index`, ascending
- `running_load`, the number of assignments already made to that expert within
  the current step, ascending
- `placement_rank`, the mesh rank owning the expert, ascending
- `bias_rank`, the integer part of ten times the `bias_gain` of the expert,
  ascending. Several experts share a value

A tie break event is recorded whenever more than one expert presents the value
that the last selected slot holds. The event carries the step, the token index,
that quantised value, the sorted list of every contender and the sorted list of
the contenders actually selected.

## Combine weights

Let `floor_i` be the smallest `q(i, e)` over **all** experts for that token, not
only the selected ones. For each selected expert

```
shift = q(i, e) - floor_i + 1
weight = shift / sum of the shifts of the selected experts
```

Each weight is rounded independently; they are not renormalised afterwards.
"""

DOCS["capacity_contract.md"] = """# Expert capacity

Capacity is computed once per step from the demand recorded before any token is
dropped.

```
ideal = capacity_factor * total_assignments / num_experts
target(e) = min(demand(e), ideal)
aligned(e) = capacity_bucket * ceil(ceil(target(e)) / capacity_bucket)
capacity(e) = max(min_capacity, aligned(e))
```

`total_assignments` is the sum of demand over every expert for that step. The
alignment happens first and the minimum is applied to the aligned value. The
minimum is used exactly as configured and is never itself aligned, so a run
whose `min_capacity` is not a multiple of `capacity_bucket` produces capacities
that are not multiples of the bucket. That situation is legal and is reported.

The revision register decides which of the two orderings is in force. Read it.

## Dispatch

Assignments are walked in the order the router produced them, which is ascending
token index and, within a token, ascending selection slot. The running counter
for the named expert gives the slot index. An assignment whose slot index is at
least the capacity of its expert is dropped. Dropping affects only that
assignment; the other expert chosen for the same token is unaffected.

Two figures are published and they are sourced differently. `dropped_tokens`
counts dropped assignments. `dropped_token_mass` sums the combine weights of the
dropped assignments.

Slots between the accepted count and the capacity are padding. Padding carries
no token, contributes nothing to any accumulator, and never appears in a
denominator.
"""

DOCS["mesh_contract.md"] = """# Expert parallel placement

`num_experts` must divide by `ep_world_size`. Each rank receives exactly
`num_experts / ep_world_size` experts.

Placement is table driven.

1. Sort experts ascending by `(placement_group, expert_index)` using
   `placement_group` from `expert_placement.csv`.
2. Read the rows of `rank_affinity.csv` whose `ep_world_size` matches the run and
   sort them ascending by `group_order`. That yields a rank order.
3. Cut the sorted expert list into consecutive blocks of
   `num_experts / ep_world_size` entries. Block `k` lands on the `k` th rank of
   the rank order.

The rank order is not the natural rank order and the expert list is not the
natural expert order. Neither shortcut reproduces the shipped placement.

## Buckets

```
rank_bucket(r) = max capacity(e) over the experts placed on rank r
alltoall_bucket = max rank_bucket(r) over every rank
```

The guard key of a compiled expert region uses `rank_bucket` for the rank that
owns the region. The exchanged payload uses `alltoall_bucket`. These are two
different quantities and only coincide when the mesh happens to be balanced.
"""

DOCS["alltoall_contract.md"] = """# Collective exchange

Each step exchanges a uniform payload.

```
payload_slots = alltoall_bucket * ep_world_size * experts_per_rank
rank_bucket_spread = max rank_bucket - min rank_bucket
```

A step is uniform when the spread is zero. The cost of the exchange is

```
alltoall_us = fixed_us + per_slot_us * alltoall_bucket * ep_world_size
```

with both coefficients read from `alltoall_cost_table.csv` for the world size in
force. A world size of one has both coefficients at zero.
"""

DOCS["guard_semantics.md"] = """# Guard keys

One code object exists for the router and one for each index in
`moe_layer_indices`, named `moe_block_<index>`. Each rank holds its own cache of
compiled entries for each code object.

Dimensions, in the order they appear in a key:

- the router code object guards `tokens`
- an expert region guards `capacity` and `local_experts` and nothing else,
  because the padded dispatch tensor carries no token axis once the router has
  scattered into slots

Values: `tokens` is the token count of the step, `capacity` is `rank_bucket` for
the rank holding the entry, `local_experts` is the number of experts placed on
that rank. Marking `tokens` dynamic therefore reaches the router alone, and the
router is never captured.

## Promotion

Promotion is tracked per code object and per dimension and is shared across
ranks. A dimension named in `mark_dynamic` is dynamic from the first step. Any
other dimension accumulates the distinct values it has been compiled against.
The pending value is inserted into that set before the count is compared, so the
count includes the shape currently being compiled. When the count reaches
`promotion_threshold` the dimension becomes dynamic for that code object from
that compilation onward. Promotion happens only when
`dynamic_promotion_enabled` is true, and a promotion is never undone.

The revision register decides whether the pending shape counts. Read it.

## Key text

Each dimension contributes one component and the components are joined with a
single vertical bar in the dimension order above. A dimension contributes the
literal `dyn` when it is dynamic **and** its value is neither zero nor one. A
dynamic dimension whose value is zero or one contributes that value, because the
compiler specialises those two sizes even after a dimension has gone dynamic.
Every other dimension contributes its decimal value.

The static dimension count of a key is the number of components that are not
`dyn`. The count taken before the pending promotions are applied and the count
taken after are both recorded, and their difference is the guard delta of the
event.
"""

DOCS["recompile_policy.md"] = """# Compiled entry cache

Each `(code_object, rank)` pair owns a cache holding at most `cache_size_limit`
entries. Within one step the pairs are visited in ascending code object name and
then ascending rank, and the router is visited before the expert regions because
its name sorts first.

A key already present is a hit; its use marker is refreshed and nothing else
happens. A key absent from the cache is a recompile. When the cache already
holds `cache_size_limit` entries the least recently used entry is evicted first,
and a tie on the use marker is broken by evicting the lexicographically smallest
key text. The new entry is then inserted and marked used.

A recompile event carries the step, the code object, the rank, the key, the two
static dimension counts, their signed difference and the evicted key or a null
when nothing was evicted.

`recompiles_after_warmup` counts recompile events at steps strictly greater than
`warmup_bound`.

## Reset

At the start of a step listed in `reset_steps` every cache and the capture pool
are cleared. Promotion state survives a reset.
"""

DOCS["cudagraph_policy.md"] = """# Graph capture

Capture is attempted once per guard key visited in the step, for expert regions
only. The router is never captured.

- When the compile mode is not `reduce-overhead` no capture is attempted and the
  recorded cause is `capture_disabled_for_mode`.
- When at least one graph break fired anywhere in the step the capture fails and
  the recorded cause is `operation_not_permitted_when_stream_is_capturing`.
- When any component of the key is `dyn` the capture fails and the recorded cause
  is `dynamic_dimension_in_guard_key`.
- Otherwise the capture succeeds and no cause is recorded.

## Pool

A step in which at least one capture succeeded grows the pool by the sum over
ranks of the block size chosen from `pool_block_table.csv`, taking the first row
whose `capacity_ceiling` is at least the `rank_bucket` of that rank. The pool is
cleared by a reset.

The reported figure for a step is the running peak, which is the larger of the
peak carried into the step and the pool size after the step. The running peak
restarts from the pool size of the step **after** the figure for that step has
been reported, so a reset step still publishes the peak reached before it.

## Graph breaks

Causes fire at most once per step. A cause fires when its condition holds:

- `data_dependent_capacity`: at least one capacity is not a multiple of
  `capacity_bucket`
- `dynamic_token_count`: the token count differs from the previous step and
  `tokens` is absent from `mark_dynamic`. The first step of a run never fires it
- `token_drop_mask`: at least one assignment was dropped
- `unbalanced_expert_slice`: the rank buckets are not all equal
- `zero_token_expert`: at least one expert recorded zero demand

The ledger lists fired causes in ascending cause name, which is the order of
`graph_break_catalog.csv`.
"""

DOCS["host_memory_model.md"] = """# Host memory

```
entry_bytes, guard_bytes = row of memory_slot_table.csv whose static_dims equals
                           the number of dimensions named in mark_dynamic
guard_closures = over every cached entry, the count of key components that are
                 not `dyn`, summed
host_bytes = host_base_bytes
           + cached entries * entry_bytes
           + guard_closures * guard_bytes
           + running pool peak
host_headroom_bytes = host_ceiling_bytes - host_bytes
```

Headroom is signed. A run that exceeds the ceiling publishes a negative figure
and the steps where that happened. The figure is never clamped.
"""

DOCS["steptime_model.md"] = """# Step time

Every named term is rounded to `time_decimals` before the total consumes it, and
the total is rounded again.

```
compile_us  = sum over the recompile events of the step of the cost read from
              compile_cost_table.csv for the compile mode and for the static
              dimension count taken **before** the pending promotions applied
capture_us  = capture_us of the mode times the number of successful captures
compute_us  = max over ranks of the sum over the experts on that rank of
              kernel_us_per_slot * rank_bucket(rank)
              multiplied by replay_discount when at least one capture succeeded,
              otherwise unscaled
alltoall_us = see the collective contract
bubble_us   = sum over fired causes of bubble_us times the number of expert
              layers, plus sync_bubble_us when the step recompiled anything
step_us     = compile_us + capture_us + compute_us + alltoall_us + bubble_us
```

The eager reference uses the same walk with no compile cost, no capture cost, no
bubble, no discount, and `compute_us` multiplied by `eager_compute_multiplier`.

The throughput gate divides the eager total by the compiled total over the steps
strictly greater than `warmup_bound`. `amortized_compile_us` divides the compile
cost of the whole run by the number of gated steps.
"""

DOCS["numeric_contract.md"] = """# Numeric contract

Two dtypes are in play on the compiled path. Storage is bfloat16, which is the
top sixteen bits of a binary32 value rounded to nearest with ties to even.
Accumulation is binary32. The dispatch payload additionally passes through an
eight bit float described in `fp8_format_notes.md`.

The compiled path applies the casts at these points, in this order, for each
expert walked in ascending expert index and for each accepted slot walked in
ascending slot index:

1. the token feature `t` is stored
2. the combine weight `w` is stored
3. `raw = w * (1 - t * 0.25)` is accumulated
4. `raw * payload_scale` is accumulated and then cast to the eight bit float
5. the payload divided by `payload_scale` is accumulated
6. the running expert accumulator absorbs it and is accumulated

After the slots of an expert are exhausted:

7. the expert output is the accumulator divided by the number of accepted slots
   and is stored. An expert with no accepted slot stores a zero
8. each contribution `output * cost_weight` is accumulated
9. the step signal accumulates those contributions in ascending expert index
10. each gradient `output * signal_weight * cost_weight` is accumulated
11. each scaled gradient `gradient * loss_scale` is accumulated
12. each squared scaled gradient is accumulated
13. the sum of squares is accumulated
14. each clipped scaled gradient is accumulated
15. each unscaled gradient is accumulated
16. each parameter update is stored
17. the loss terms are rounded

The eager reference performs the identical walk in binary64 with no cast at any
of those points. The two paths therefore differ only by rounding, and the parity
band measures that difference.

`payload_scale`, `signal_weight`, `base_loss` and `decay_rate` come from
`model_topology.json`.

```
loss(step) = base_loss / (1 + decay_rate * step) + aux_loss(step)
           + signal_weight * step_signal(step)
```

Each of the three terms is rounded before the sum, and the sum is rounded.

Every published float is rounded to `float_decimals` from
`validation_tolerances.json`, except the timing figures which use
`time_decimals`. A negative zero is published as zero.
"""

DOCS["fp8_format_notes.md"] = """# Eight bit dispatch payload

The exchanged payload uses a four bit exponent and three bit mantissa binary
float with a bias of seven. The format has no infinity. Its largest finite
magnitude is 448. Its smallest normal exponent is minus six and its subnormal
quantum is two to the power minus nine.

Casting a magnitude `a`:

1. write `a = m * 2 ** e` with `m` in the half open range from one half to one
2. the unbiased exponent is `e - 1`
3. the quantum is two to the power minus nine when the unbiased exponent is below
   minus six, otherwise two to the power of the unbiased exponent minus three
4. divide by the quantum, round to nearest with ties to even, multiply back
5. **then** saturate: a rounded magnitude above 448 becomes exactly 448

Rounding happens before saturation. Saturating first and rounding afterwards
gives a different answer for magnitudes just under the limit. Zero maps to zero
and the sign is reapplied at the end.
"""

DOCS["aux_loss_contract.md"] = """# Balance term

```
fraction(e)    = demand(e) / total_assignments
probability(e) = gate_mass(e) / token_count
aux_loss       = aux_loss_weight * num_experts * sum over e of
                 fraction(e) * probability(e)
```

`demand` is the count recorded before capacity is applied. `gate_mass` is the sum
of the combine weights of every assignment naming the expert, again before
capacity is applied. Each fraction and each probability is rounded when it is
formed, and either one is zero when its denominator is zero. Each product is
rounded before the running sum absorbs it and the sum is rounded before the
weight multiplies it. The revision register decides which of the two sourcings
is in force. Read it.

The convergence record, the parity record and the settled gate verdicts all
compare against `parity_band`. The sweep's `convergence_band_unmet` cause
compares the probe horizon deviation against `settlement_parity_band`. The two
figures differ and neither substitutes for the other.

`load_dispersion` is the largest fraction minus the smallest fraction taken over
the experts whose demand is non zero. Experts with zero demand are excluded from
both ends of that comparison; they are not treated as zero. With exactly one live
expert the dispersion is zero and with none it is null.

`expert_utilization` publishes one entry per expert in ascending expert index. An
expert with zero demand publishes null. Every other expert publishes its accepted
count divided by its demand, multiplied by its fraction.
"""

DOCS["optimizer_contract.md"] = """# Optimizer

```
gradient(e)   = output(e) * signal_weight * cost_weight(e)
scaled(e)     = gradient(e) * loss_scale
norm          = square root of the sum over e in ascending index of scaled(e) ** 2
reference     = clip_threshold * loss_scale
factor        = 1 when norm is at most the reference, otherwise reference / norm
unscaled(e)   = scaled(e) * factor / loss_scale
parameter(e)  = parameter(e) - learning_rate * unscaled(e)
```

The norm is taken on the scaled gradients and compared against the scaled
reference. Unscaling before clipping is a different computation on this path
because the casts land in different places. Parameters start at zero.

A step is clipped when the norm is strictly greater than the reference.
"""

DOCS["warmup_contract.md"] = """# Warmup

The warmup window is every step whose index is at most `warmup_bound`. The two
gates read the complementary window, every step whose index is strictly greater
than `warmup_bound`. The bound itself therefore belongs to the profile and not
to the gates.

The profile publishes the distinct token counts, the distinct rank bucket values
and the distinct local expert counts observed inside the window, each sorted
ascending, together with the number of recompiles inside the window.

A dimension is listed in `dims_requiring_dynamic` when the number of distinct
values it showed inside the window is at least `promotion_threshold`. Only
`tokens` and `local_experts` are eligible for that list. The capacity dimension
is chosen by the settlement itself and is never listed there, however many
distinct values the window happened to show.

`warmup_windows.json` records the bound used by each shipped profile.
"""

DOCS["settlement_procedure.md"] = """# Settlement

The candidate space is the full cross product of the four axes in
`capacity_candidates.json`. Every candidate keeps every other setting of the run
it replaces and is evaluated over the leading `probe_steps` steps, with the reset
list truncated to that horizon.

Each candidate is compared against an eager reference sharing its capacity factor
and bucket. Those references may be reused across candidates.

## Pre filter

A candidate is removed before any rejection cause is considered when it fails to
mark a dimension that the warmup profile listed in `dims_requiring_dynamic`. Such
candidates are published under `prefiltered` with the sorted list of unmarked
dimensions and they never reach the cause counts.

## Causes

A surviving candidate is checked against seven conditions.

- `eager_mode_forbidden`: the compile mode is `eager`
- `recompile_budget_exceeded`: recompiles after warmup exceed `recompile_budget`
- `speedup_gate_unmet`: the measured speedup is below `min_speedup`
- `memory_ceiling_exceeded`: the smallest headroom is negative
- `drop_tolerance_exceeded`: the drop rate exceeds `max_drop_rate`
- `convergence_band_unmet`: the relative deviation exceeds
  `settlement_parity_band`, which is the tighter of the two bands recorded in the
  convergence gate file and is used here and nowhere else
- `capacity_below_minimum`: the smallest capacity is below `capacity_floor`

The drop rate divides dropped assignments by total assignments.

A candidate violating nothing is admissible. A candidate violating anything is
attributed to the **first** cause in the precedence order that it violates, and
only that cause. Every one of the seven causes appears in the count map, with a
zero when no candidate is attributed to it. The precedence order is fixed for this pipeline and is not
printed in this document. `precedence_constraints.md` narrows it and
`sealed_policy_notes.md` pins it down.

## Selection

Among the admissible candidates, order by ascending capacity factor, then by
descending bucket, then by the number of marked dimensions ascending, then by the
marked dimensions joined with a vertical bar ascending, then by compile mode
**descending**. The first entry settles. The last key runs the other way from the
four before it.

A candidate label is written
`cf=<factor>|bucket=<bucket>|dynamic=<marks>|mode=<mode>` where the factor is the
Python repr of the float, the marks are joined with a plus sign and an empty set
is written `none`.
"""

DOCS["precedence_constraints.md"] = """# Constraints on the cause order

The precedence order is a permutation of the seven cause names. Three facts about
it are on record.

1. `eager_mode_forbidden` occupies the first position.
2. `capacity_below_minimum` precedes `drop_tolerance_exceeded`.
3. `recompile_budget_exceeded` precedes `speedup_gate_unmet`.

Nothing else about the order is recorded in prose. The remaining freedom is
finite and small enough to enumerate.
"""

DOCS["sealed_policy_notes.md"] = """# Sealed evidence

Two decisions are withheld from the prose: the field order of the routing tie
break key, and the precedence order of the rejection causes. Both are recoverable
from the shipped digests without guessing.

`sealed_tiebreak_digests.json` maps a configuration name to a step count and to
the SHA-256 of the canonical serialisation of the list of tie break events that
the correct key produces over those leading steps of that configuration. Events
are concatenated in ascending step and, within a step, in the order the router
recorded them.

`sealed_precedence_digests.json` maps a configuration name to the SHA-256 of the
canonical serialisation of the per cause count map produced by the correct order
over the settlement sweep of that configuration. The map holds all seven cause
names, including the ones that never fire.

The named configurations are `calibration`, which is `calibration_config.json`,
and `probe_alpha`, which is the entry of that name in
`probe_configurations.json`.

Canonical serialisation is the shape described in `output_schema.md`: two space
indentation, keys sorted at every level, no ASCII escaping, one trailing newline,
UTF-8 bytes.

A candidate order that reproduces the digest for every named configuration is the
order in force. Should more than one candidate reproduce every digest, the one
that sorts first when the candidate orders are compared as lists of strings is
the one in force. If no candidate reproduces them, something upstream of the digest
is wrong; the digests are not a substitute for the pipeline.
"""

DOCS["enumeration_order.md"] = """# Iteration orders

- tokens: ascending token index
- selected experts within a token: ascending selection slot
- experts in any sum, any published list and any accumulator: ascending expert
  index
- accepted slots within an expert: ascending slot index
- ranks: ascending rank number
- code objects within a step: the router first, then the expert regions in
  ascending layer index
- steps: ascending step index
- rejection causes in the ledger: the precedence order in force
- graph break causes in the ledger: ascending cause name
- candidate labels in every published list: ascending label text
- keys inside `keys_by_slot`: ascending key text
- slots inside `keys_by_slot`: ascending slot text, where a slot is the code
  object name, an at sign and the rank
"""

DOCS["audit_definitions.md"] = """# Audit statistics

The audit block mixes figures taken from the replayed deployed run and from the
settled run. The definitions are deliberately not parallel; each name states its
own source, window and denominator.

- `deployed_recompiles_total`: recompile events over every step of the deployed
  replay
- `settled_recompiles_after_warmup`: recompile events of the settled run at steps
  strictly greater than its bound
- `deployed_distinct_capacity_values`: distinct per expert capacities over the
  deployed replay
- `settled_distinct_rank_buckets`: distinct rank bucket values over the settled
  run
- `deployed_drop_rate_assignment_denominator`: dropped assignments over total
  assignments, deployed replay
- `settled_drop_rate_token_denominator`: dropped assignments over total tokens,
  settled run
- `deployed_break_steps_inclusive_warmup`: steps with at least one break whose
  index is at most the deployed bound
- `settled_break_steps_exclusive_warmup`: steps with at least one break whose
  index is strictly greater than the settled bound
- `deployed_mean_host_bytes`: arithmetic mean over every deployed step
- `settled_peak_host_bytes`: maximum over every settled step
- `deployed_capture_failure_ratio`: failed capture attempts over all attempts
- `settled_capture_success_ratio`: successful captures over all attempts
- `deployed_empty_expert_step_count`: steps holding at least one empty expert
- `settled_empty_expert_slot_count`: pairs of a step and an empty expert, counted
  with repeats
- `deployed_unique_guard_keys_router_only`: distinct triples of code object, rank
  and key restricted to the router
- `settled_unique_guard_keys_moe_only`: the same count restricted to the expert
  regions
- `deployed_token_total`: tokens summed over every deployed step
"""

DOCS["unreachable_branches.md"] = """# A branch specified but never exercised

One behaviour is part of the contract and no shipped or generated configuration
reaches it. It is recorded so that an implementation is not surprised by its
absence.

- a capacity factor of zero yields a target of zero for every expert; the aligned
  value is zero and the minimum then holds
"""

DOCS["compile_flags.md"] = """# Compile modes

- `reduce-overhead` compiles and then attempts graph capture. It pays the highest
  compile cost and the capture cost, and it earns the replay discount.
- `default` compiles without capture. It pays a lower compile cost, records the
  cause `capture_disabled_for_mode` for every attempt and earns a much weaker
  discount.
- `eager` compiles nothing. It is present in the candidate axes so that the
  settlement can reject it by name rather than by silence. It is never an
  admissible answer.

`mark_dynamic` names dimensions that start dynamic. Only `tokens` and `capacity`
appear in the shipped axes. Marking a dimension changes the memory slot row that
the host ledger reads, because that row is indexed by the number of marked
dimensions.
"""

DOCS["revision_history.md"] = """# Revision register

`revision_register.json` is the machine readable register. Each entry names a
policy, a revision label, an effective order and a status. The revision in force
for a policy is the applied entry with the highest effective order. Superseded
entries are kept because the deployed orchestrator still follows some of them.

Policies covered: `capacity`, `guard`, `cache`, `compile`, `aux`, `pool`.

Two of the pairs matter most. The capacity policy moved from holding at the
minimum first to aligning first. The guard policy moved from counting shapes seen
before the pending compilation to counting the pending shape as well. A reader
who follows the superseded entry produces plausible figures that disagree with
every gate.
"""

DOCS["legacy_planner_notes.md"] = """# Notes from the previous planner

These notes describe the planner that ran before the register was introduced.
They are kept for context and they are not the contract.

The old planner held capacity at the minimum first and aligned the result to the
bucket afterwards, so every capacity was a multiple of the bucket and the
`data_dependent_capacity` break never fired. It counted a shape as seen only
after its compilation finished, so promotion always lagged by one shape. It
sourced the balance term from accepted assignments rather than from demand, which
made the term shrink whenever capacity bit. It placed experts on ranks by integer
division of the expert index, which is not what the affinity table says.

Every one of those four behaviours has since been superseded.
"""

DOCS["incident_report.md"] = """# Incident 7734

The run reached the first checkpoint and then degraded. Symptoms recorded by the
on call engineer:

- device utilisation collapsed to roughly a third of the profiled figure and the
  timeline filled with gaps between kernels
- the compile log kept emitting recompilation lines far past the warmup window,
  long after the shape distribution was supposed to have settled
- the host resident set grew monotonically and the job was eventually killed by
  the out of memory reaper
- capture attempts logged `CUDA error: operation not permitted when stream is
  capturing`
- the published throughput figure did not match the wall clock of the job

The orchestrator that produced the run is `deployed_trainer.py`. Its published
figures are `deployed_run_summary.json`. Nothing in this corpus states which of
its decisions is wrong.
"""

DOCS["fault_report.md"] = """# On call notes

Observations only.

- the shape distribution stops changing after the first dozen steps yet
  compilation continues
- several experts receive no tokens at all on some steps and the balance term
  behaves differently on those steps than the previous run
- the exchanged payload is larger than the per rank padding suggests
- host memory grows in steps that look like whole cache entries rather than
  activations
- host memory never falls from one step to the next, and the last row of the
  memory trace carries the peak
- the loss is close to the reference but the closing figure sits outside the band
  the acceptance sheet quotes

No diagnosis was reached before the job was killed.
"""

DOCS["worked_step.md"] = """# One worked step

This walk uses `sample_run_config.json`, whose promotion sentinel is off, whose
bias is off, whose jitter slot count is zero and whose mesh has a single rank.
Several layers of the contract are therefore inert here. The walk is a
calibration aid, not a representative case.

Step 1 of that configuration draws 64 token salts and 4 expert phases and
consumes nothing else. Every logit reduces to the affinity term alone because the
bias and the jitter terms vanish. Quantisation still applies and ties still occur, so the
sealed key still decides selection, but the placement rank and the bias rank are
constant across experts on this configuration and cannot separate the candidate
keys on their own.

Capacity uses a factor of 1.5 over 128 assignments and 4 experts, so the ideal is
48 and every demand is below it. The aligned value is the demand rounded up to a
multiple of 8 and the minimum of 8 then holds only for an expert whose demand is
zero. No assignment is dropped. The single rank makes the rank bucket and the all
to all bucket equal, so the two quantities cannot be told apart here either.

The compiled cache sees one key per code object per step and the token count is
constant, so nothing recompiles after the first step and nothing is evicted.
"""

DOCS["output_schema.md"] = """# Published records

Every record is a JSON object serialised with two space indentation, keys sorted
at every level, no ASCII escaping, and exactly one trailing newline. Integers are
written as integers. Floats are rounded as the numeric contract requires. A field
documented as absent is absent, not null, unless the contract says null.

Integers, floats and booleans are not interchangeable. A float whose value is
whole is still a float and is written with a trailing `.0`. Counts, step and
token indices, ranks, capacities, buckets, slot figures, guard deltas, the per
step `captured` count and byte figures are integers, except that a mean of bytes
is a float. Losses, masses, logits, outputs, partials, signals, gradients,
parameters, norms, factors, scales, rates, ratios, slopes, deviations, bands,
targets, timings, speed margins, every `signed_delta` and every residual are
floats. A configuration setting, whether it is published under its own name or
as a `value`, a `from`, a `to` or a `delta`, keeps the JSON type that setting
has in `deployed_config.json`. A figure copied from `deployed_run_summary.json` keeps
the type it has there. A yes or no outcome is a boolean.

Each record carries exactly the top level keys listed for it here, no more and no
fewer.

- `route_plan.json`: `run_id`, `top_k`, `tie_break_key`, `steps`,
  `tie_break_events`, `total_assignments`. Each entry of `steps` carries `step`,
  `token_count`, `demand`, `gate_mass_total`, `tie_break_count`. Each entry of
  `tie_break_events` carries `step`, `token_index`, `quantized_logit`,
  `contenders`, `selected`. `gate_mass_total` is formed from the balance term
  probabilities of that step under the sourcing in force: they are added in
  ascending expert index with no rounding between additions, the sum is
  multiplied by `token_count`, and the product is rounded once. It is not the
  count of assignments and it is not the sum of the unrounded gate masses, so it
  can differ from a whole number in its last places.
- `capacity_plan.json`: `run_id`, `capacity_factor`, `capacity_bucket`,
  `min_capacity`, `steps`, `min_capacity_seen`, `max_capacity_seen`,
  `distinct_capacity_values`. Each step entry carries `step`, `capacity`,
  `unaligned_experts`.
- `mesh_plan.json`: `run_id`, `ep_world_size`, `expert_rank`, `rank_experts`,
  `placement_groups`, `rank_bucket_by_step`, `expert_shape_matrix`. The last of
  those is a single number, the count of distinct capacity vectors multiplied by
  the number of expert layers. `rank_experts` is keyed by rank. Each entry of
  `rank_bucket_by_step` carries `step` and `rank_bucket`, the latter keyed by
  rank.
- `dispatch_ledger.json`: `run_id`, `steps`, `total_accepted`,
  `total_padded_slots`. Each step entry carries `step`, `accepted_count`,
  `padded_slots`.
- `drop_ledger.json`: `run_id`, `steps`, `dropped_tokens`, `dropped_token_mass`,
  `drop_rate`, `steps_with_drops`. Each step entry carries `step`,
  `dropped_tokens`, `dropped_token_mass`.
- `alltoall_ledger.json`: `run_id`, `ep_world_size`, `steps`, `uniform_steps`,
  `total_payload_slots`. Each step entry carries `step`, `alltoall_bucket`,
  `payload_slots`, `rank_bucket_spread`.
- `guard_key_index.json`: `run_id`, `keys_by_slot`, `distinct_key_count`,
  `specialized_zero_one_keys`, `dynamic_dims_final`.
- `recompile_report.json`: `run_id`, `warmup_bound`, `recompile_events`,
  `total_recompiles`, `recompiles_after_warmup`, `first_step_over_budget`,
  `evictions`, `recompiles_by_step`. The events list holds objects, each carrying
  `step`, `code_object`, `rank`, `guard_key`, `guard_delta`, `evicted_key`.
  Each entry of `recompiles_by_step` carries `step`, `count`.
- `graph_break_ledger.json`: `run_id`, `cause_order`, `per_cause_counts`,
  `steps`, `total_breaks`, `clean_steps`. `per_cause_counts` is keyed by cause
  name. Each step entry carries `step`, `causes`.
- `cudagraph_report.json`: `run_id`, `compile_mode`, `capture_attempts`,
  `captures`, `failure_causes`, `steps`, `final_pool_peak_bytes`, `reset_steps`.
  `failure_causes` is keyed by cause name. Each step entry carries `step`,
  `captured`, `pool_bytes`, `pool_peak_bytes`.
- `host_memory_report.json`: `run_id`, `host_ceiling_bytes`, `steps`,
  `min_host_headroom_bytes`, `peak_host_bytes`, `steps_over_ceiling`,
  `memory_gate_met`. Each step entry carries `step`, `host_bytes`,
  `host_headroom_bytes`, `cache_entries`, `guard_closures`.
- `steptime_report.json`: `run_id`, `steps`, `gated_step_range`,
  `compiled_tail_us`, `eager_tail_us`, `speedup`, `min_speedup`,
  `speedup_gate_met`, `amortized_compile_us`. Each step entry carries `step`,
  `step_us`, `compute_us`, `alltoall_us`, `compile_us`, `capture_us`,
  `bubble_us`, `eager_step_us`.
- `warmup_profile.json`: `run_id`, `warmup_bound`, `window_steps`,
  `distinct_token_values`, `distinct_capacity_values`,
  `distinct_local_expert_values`, `promotion_threshold`,
  `dims_requiring_dynamic`, `warmup_recompiles`.
- `sealed_policy_resolution.json`: `tie_break_key`, `tie_break_matches`,
  `tie_break_candidates_enumerated`, `precedence_order`, `precedence_matches`,
  `precedence_candidates_enumerated`, `sealed_configs`.
- `aux_loss_trace.json`: `run_id`, `aux_loss_weight`, `steps`, `aux_loss_total`,
  `steps_with_empty_experts`, `mean_load_dispersion`. Each step entry carries
  `step`, `aux_loss`, `expert_utilization`, `load_dispersion`, `empty_experts`.
- `loss_curve.json`: `run_id`, `steps`, `closing_loss`, `opening_loss`,
  `minimum_loss`, `steps_above_opening`. Each step entry carries `step`, `loss`,
  `eager_loss`, `signed_gap`.
- `gradient_ledger.json`: `run_id`, `steps`, `folded_signal`, `final_params`,
  `accumulation_order`. Each step entry carries `step`, `expert_outputs`,
  `expert_partials`, `step_signal`, `gradients`. `accumulation_order` is the
  list `["slot_ascending", "expert_index_ascending"]`, naming the inner walk of
  the numeric contract first and the outer walk second.
- `optimizer_trace.json`: `run_id`, `loss_scale`, `clip_threshold`,
  `learning_rate`, `steps`, `clipped_steps`, `clipped_step_count`. Each step
  entry carries `step`, `scaled_norm`, `clip_reference`, `clip_factor`,
  `clipped`.
- `convergence_report.json`: `run_id`, `slope_window`, `windowed_slope`,
  `closing_loss`, `baseline_closing_loss`, `relative_deviation`, `parity_band`,
  `parity_holds`, `target_loss`, `verdict`. With `losses` the per step compiled
  losses of the settled run and `w` the `slope_window` of
  `convergence_gates.json`, `windowed_slope` is
  `(losses[-1] - losses[-w]) / (w - 1)` when the run has at least `w` steps and
  `w` exceeds one, and `losses[-1] - losses[0]` otherwise, rounded once.
  `closing_loss` is the last compiled loss and `baseline_closing_loss` the last
  eager loss. `relative_deviation` is the absolute difference of the two divided
  by the absolute eager figure, rounded, and zero when the eager figure is zero;
  the settlement gate figures and the run summaries use the same formula.
  `parity_holds` is true when that deviation is at most `parity_band`.
  `verdict` is the string `met` when parity holds, `windowed_slope` is at most
  `max_slope` and `closing_loss` is at most `target_loss`, and the string
  `unmet` otherwise.
- `baseline_parity.json`: `run_id`, `steps`, `max_relative_deviation`,
  `max_deviation_step`, `parity_band`, `parity_holds`, `steps_outside_band`.
  Each step entry carries `step`, `relative_deviation`, computed per step with
  the convergence formula. `max_deviation_step` is the first step attaining the
  largest deviation and is null when every deviation is zero. `parity_holds` is
  true when the largest deviation is at most `parity_band`, and
  `steps_outside_band` lists in ascending order the steps whose deviation
  exceeds it.
- `settlement_report.json`: `run_id`, `probe_steps`, `candidates_evaluated`,
  `prefiltered_count`, `rejected_count`, `admissible_count`,
  `settled_configuration`, `settled_gate_figures`, `changed_settings`,
  `gates_met`. `settled_configuration` carries `capacity_factor`,
  `capacity_bucket`, `mark_dynamic`, `compile_mode`. `settled_gate_figures`
  and `gates_met` describe the settled configuration replayed over the full step
  count of the run it replaces, never over the probe horizon. `gates_met`
  carries `speedup`, true when the speedup is at least `min_speedup`; `memory`,
  true when the smallest host headroom is zero or more; `recompile_budget`, true
  when the recompiles after warmup are at most `recompile_budget`; and
  `convergence`, true when the relative deviation is at most `parity_band`.
  `settled_gate_figures` carries `speedup`, `compiled_tail_us`,
  `eager_tail_us`, `min_host_headroom_bytes`, `recompiles_after_warmup`,
  `drop_rate`, `min_capacity_seen`, `closing_loss`, `baseline_closing_loss`,
  `relative_deviation`. Each entry of `changed_settings` carries `setting`,
  `from`, `to`.
- `rejection_ledger.json`: `cause_order`, `per_cause_counts`, `rejected`,
  `prefiltered`, `admissible_candidates`. `per_cause_counts` is keyed by cause
  name. Each entry of `rejected` carries `candidate`, `cause`,
  `all_violations`.
- `sensitivity.json`: `run_id`, `probe_steps`, `perturbations`,
  `negative_speedup_margins`, `negative_headroom_margins`. Each entry of
  `perturbations` carries `setting`, `delta`, `speedup_margin`,
  `headroom_margin`, `recompile_margin`.
- `audit_statistics.json`: the seventeen names listed in `audit_definitions.md`.
- `deployed_diagnosis.json`: `run_id`, `published_vs_replayed`,
  `departing_settings`, `capture_failure_causes`, `first_step_over_budget`,
  `admissible`, `published_agrees_with_replay`. `published_vs_replayed` is keyed
  by `speedup`, `closing_loss`, `drop_rate`, `min_host_headroom_bytes`,
  `total_recompiles`, `recompiles_after_warmup`, and each of its entries carries
  `published`, `replayed`, `signed_delta`. Each entry of `departing_settings`
  carries `setting`, `value`, `policy`, `revision`. `signed_delta` is the
  published figure minus the replayed figure, rounded to `float_decimals` for
  every field including `speedup`. `admissible` is true
  exactly when `departing_settings` is empty and the corrected replay of the
  deployed configuration over its whole run triggers none of the rejection
  causes of `settlement_procedure.md`; it is false otherwise.
- `validation_report.json`: `residuals`, `record_counts`,
  `max_absolute_residual`, `artifact_count`, `float_decimals`,
  `time_decimals`. `residuals` is keyed by `speedup`, `closing_loss`,
  `drop_rate`, `min_host_headroom_bytes`, `recompiles_after_warmup`. Each
  residual is the published figure of `deployed_run_summary.json` minus the
  same figure of the corrected deployed replay, rounded to `float_decimals` for
  every field including `speedup`, and
  `max_absolute_residual` is the largest absolute residual, zero when there is
  none. `record_counts` is keyed by record file name and covers the
  twenty-five records listed above `validation_report.json`. A record whose
  `steps` is a list counts its step entries; any other record counts its top
  level keys. `artifact_count` is the number of records `record_counts` covers.
- `stage_manifest.json`: `stage`, `artifact_count`, `artifact_sha256`.
- `replay_manifest.json`: `stage`, `artifact_count`, `artifact_sha256`,
  `stage_manifest_sha256`.
- `final_state.json`: `closing_loss`, `convergence_verdict`,
  `deployed_admissible`, `digest_of_digests`, `first_step_over_budget`,
  `precedence_order`, `replay_manifest_sha256`, `settled_configuration`,
  `settlement_salt`, `speedup`, `stage_manifest_sha256`, `tie_break_key`,
  `total_artifacts`.

The stage manifest digests the fourteen dispatch and compile records. The replay
manifest digests the twelve replay and settlement records and additionally
carries the SHA-256 of the canonical bytes of the stage manifest as written to
disk. The final state folds a map of three entries, keyed `replay`, `salt` and
`stage`, holding the replay manifest digest, the digest of the settled
configuration object and the stage manifest digest.

The fourteen dispatch and compile records are `route_plan.json` through
`sealed_policy_resolution.json` in the order listed above, and the stage manifest
carries `stage` set to `dispatch_and_compile`. The twelve replay and settlement
records are `aux_loss_trace.json` through `validation_report.json` in the order
listed above, and the replay manifest carries `stage` set to
`replay_and_settlement`. In each manifest `artifact_count` is the number of
records it digests and `artifact_sha256` is keyed by record file name, one entry
per digested record. `total_artifacts` counts every record named in this file.

The records describing routing, capacity, the mesh, dispatch, drops, the
collective, guard keys, recompiles, breaks, capture, host memory, step time and
the warmup profile describe the deployed configuration replayed against the
contracts in force. The records describing the balance term, the loss, gradients,
the optimizer, convergence and parity describe the settled configuration.

# Document verbs

A document is a JSON object with exactly two keys. `config` is a run
configuration carrying the same keys as `deployed_config.json`. `tables` is an
object keyed by file name that holds one entry for every `.json`, `.jsonl` and
`.csv` file of the corpus. A `.json` entry holds the parsed value of that file.
A `.jsonl` entry holds the list of its parsed lines in file order. A `.csv`
entry holds the list of its rows in file order, each row an object keyed by the
header with every cell kept as a string, blank lines dropped. The prose files
are not carried. The configuration names its schedule through `seq_profile`, and
its rows are the rows of `seq_length_schedule.csv` carrying that profile.

Each verb prints one canonical JSON object with exactly these top level keys.
A key that names a record holds that record, computed for `config`.

- `trace`: `tie_break_key`, `tie_break_matches`, `guard_key_index`,
  `recompile_report`, `graph_break_ledger`, `cudagraph_report`,
  `capacity_plan`, `mesh_plan`, `host_memory_report`, `warmup_profile`.
- `replay`: `tie_break_key`, `tie_break_matches`, `route_plan`,
  `dispatch_ledger`, `drop_ledger`, `alltoall_ledger`, `aux_loss_trace`,
  `loss_curve`, `gradient_ledger`, `optimizer_trace`, `convergence_report`,
  `baseline_parity`, `steptime_report`.
- `settle`: `rejection_ledger`, `warmup_profile`, `settled_configuration`,
  `probe_steps`.
- `resolve`: the keys of `sealed_policy_resolution.json`.
"""


DEPLOYED_TRAINER = '''"""Deployed mixture of experts training orchestrator for run 7734.

This is the module of the deployed run. Its capacity, placement, shape
promotion, balance and pool helpers, and the host accounting in its driver loop,
are the code that produced the published figures and are kept verbatim. The guard
key and the cache table are cut down to a single code object for the driver; the
deployed run kept one cache per code object and rank under the same least
recently used eviction, as its logs record. The main entry point below is only a
standalone smoke driver:
it feeds zero demand and no tokens through those helpers, so the counts it
prints are not the published figures. The published figures come from the
routed run recorded in the deployed logs.
"""

import json
import math
import os
import sys


def load(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def expert_capacity(demand, factor, bucket, minimum, experts):
    """Capacity per expert for one step."""
    ideal = factor * float(sum(demand)) / float(experts)
    out = []
    for value in demand:
        target = min(float(value), ideal)
        held = max(float(minimum), math.ceil(target))
        out.append(int(bucket * math.ceil(held / bucket)))
    return out


def place_experts(experts, world):
    """Assign experts to expert parallel ranks."""
    block = experts // world
    return [index // block for index in range(experts)]


def guard_key(tokens, bucket, local_experts, dynamic):
    parts = []
    for name, value in (("capacity", bucket), ("local_experts", local_experts), ("tokens", tokens)):
        if name in dynamic:
            parts.append("dyn")
        else:
            parts.append(str(value))
    return "|".join(parts)


class CompileCache(object):
    def __init__(self, limit, threshold):
        self.limit = limit
        self.threshold = threshold
        self.entries = {}
        self.clock = 0
        self.seen = {}
        self.dynamic = set()

    def observe(self, name, value):
        bag = self.seen.setdefault(name, set())
        if len(bag) >= self.threshold:
            self.dynamic.add(name)
        bag.add(value)

    def visit(self, key):
        self.clock += 1
        if key in self.entries:
            self.entries[key] = self.clock
            return False
        if len(self.entries) >= self.limit:
            victim = min(self.entries, key=lambda k: self.entries[k])
            del self.entries[victim]
        self.entries[key] = self.clock
        return True


def balance_term(accepted, weight, experts):
    total = float(sum(accepted))
    if total <= 0.0:
        return 0.0
    parts = 0.0
    for value in accepted:
        share = float(value) / total
        parts += share * share
    return weight * float(experts) * parts


def pool_growth(bucket, ranks):
    return ranks * 4194304 * max(1, bucket // 16)


def main(argv):
    config = load(argv[1])
    experts = config["num_experts"]
    world = config["ep_world_size"]
    placement = place_experts(experts, world)
    cache = CompileCache(config["cache_size_limit"], config["promotion_threshold"])
    pool = 0
    peak = 0
    host = 268435456
    recompiles = 0
    for step in range(1, config["steps"] + 1):
        if step in config["reset_steps"]:
            cache.entries = {}
            pool = 0
            peak = 0
        demand = [0] * experts
        caps = expert_capacity(demand, config["capacity_factor"], config["capacity_bucket"],
                               config["min_capacity"], experts)
        bucket = max(caps)
        for name, value in (("capacity", bucket), ("tokens", 0)):
            cache.observe(name, value)
        key = guard_key(0, bucket, experts // world, cache.dynamic)
        if cache.visit(key):
            recompiles += 1
        pool += pool_growth(bucket, world)
        peak = max(peak, pool)
        host = 268435456 + len(cache.entries) * 1048576 + peak
    sys.stdout.write("recompiles %d host %d\\n" % (recompiles, host))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
'''


def _faulty_capacity(spec, demand):
    ideal = spec.capacity_factor * float(sum(demand)) / float(spec.num_experts)
    caps = []
    for e in range(spec.num_experts):
        target = min(float(demand[e]), ideal)
        held = max(spec.min_capacity, int(math.ceil(target)))
        caps.append(spec.capacity_bucket * ceil_div(held, spec.capacity_bucket))
    return caps


def _faulty_placement(spec):
    """Rebinds a spec to the deployed integer division placement."""
    block = spec.num_experts // spec.ep_world_size
    spec.expert_rank = [index // block for index in range(spec.num_experts)]
    spec.rank_experts = {}
    for e in range(spec.num_experts):
        spec.rank_experts.setdefault(spec.expert_rank[e], []).append(e)
    for key in spec.rank_experts:
        spec.rank_experts[key].sort()
    return spec


class _LaggingGuards(GuardState):
    """The deployed promotion check, which tests the threshold before counting the value."""

    def observe(self, name, dim, value):
        key = (name, dim)
        if self.promoted[key]:
            return
        if self.spec.dynamic_promotion_enabled and len(self.seen[key]) >= self.spec.promotion_threshold:
            self.promoted[key] = True
        self.seen[key].add(value)


def _faulty_balance(spec, routing, dispatch):
    """The deployed balance term, squared shares of the accepted counts."""
    decimals = spec.decimals
    out = aux_loss_step(spec, routing, dispatch)
    accepted = dispatch["accepted_count"]
    total = float(sum(accepted))
    parts = 0.0
    if total > 0.0:
        for value in accepted:
            share = rd(float(value) / total, decimals)
            parts = rd(parts + rd(share * share, decimals), decimals)
    out = dict(out)
    out["aux_loss"] = rd(spec.aux_loss_weight * float(spec.num_experts) * parts, decimals)
    return out


def _faulty_pool(spec, rank_bucket):
    """The deployed pool growth, a flat block per rank scaled by the widest bucket."""
    widest = max(rank_bucket.values())
    return len(rank_bucket) * 4194304 * max(1, widest // 16)


def _faulty_host(spec, guards, peak):
    """The deployed host accounting, a flat megabyte per cache entry and no guard closures."""
    return int(spec.corpus.memory_gates["host_base_bytes"]) + guards.entry_count() * 1048576 + peak


DEPLOYED_FAULTS = {
    "guards": _LaggingGuards,
    "aux": _faulty_balance,
    "pool": _faulty_pool,
    "host": _faulty_host,
}


def _faulty_run(corpus, config, order):
    """Replays the deployed orchestrator with every one of its shipped helpers."""
    spec = _faulty_placement(make_spec(corpus, config, order))
    run = simulate(spec, order, capacity=_faulty_capacity, faults=DEPLOYED_FAULTS)
    twin = _faulty_placement(eager_twin(spec))
    base = simulate(twin, order, eager=True, capacity=_faulty_capacity, faults=DEPLOYED_FAULTS)
    return spec, run, base


def _seal_tiebreak(corpus, order):
    """Digest the tie break events of every sealed configuration under the true key."""
    digests = {}
    for name, steps in (("calibration", 10), ("probe_alpha", 8)):
        spec = make_spec(corpus, sealed_config(corpus, name), order)
        events = []
        for step in range(1, steps + 1):
            events.extend(route_step(spec, step, order)["tie_break_events"])
        digests[name] = {"steps": steps, "digest": digest_of(events)}
    return digests


def _seal_precedence(corpus, order):
    """Digest the first cause counts of every sealed configuration under the true precedence."""
    probe_steps = int(corpus.candidates["probe_steps"])
    digests = {}
    for name in ("calibration", "probe_alpha"):
        spec = make_spec(corpus, sealed_config(corpus, name), order)
        run = simulate(spec, order)
        profile = build_warmup_profile(spec, run)
        rows = sweep(spec, probe_steps)
        counts = dict((cause, 0) for cause in CAUSE_NAMES)
        for row in rows:
            if prefilter(spec, profile, row["candidate"]):
                continue
            if not row["violations"]:
                continue
            for cause in TRUE_PRECEDENCE:
                if cause in row["violations"]:
                    counts[cause] += 1
                    break
        digests[name] = {"digest": digest_of(counts)}
    return digests


def _write_corpus(root, variant=None):
    data = os.path.join(str(root), "data")
    if not os.path.isdir(data):
        os.makedirs(data)
    written = {}

    def put(name, text):
        with open(os.path.join(data, name), "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        written[name] = text

    def put_json(name, obj):
        put(name, canonical_bytes(obj).decode("utf-8"))

    for name, text in sorted(DOCS.items()):
        put(name, text)
    for name, text in sorted(_table_files(variant).items()):
        put(name, text)
    for name, obj in sorted(_static_tables(variant).items()):
        put_json(name, obj)

    sample, calibration, probe_alpha, deployed = _configs(variant)
    put_json("sample_run_config.json", sample)
    put_json("calibration_config.json", calibration)
    put_json("deployed_config.json", deployed)
    put_json("probe_configurations.json", {"probe_alpha": probe_alpha})
    put_json("sealed_tiebreak_digests.json", {"digests": {}})
    put_json("sealed_precedence_digests.json", {"digests": {}})
    put_json("deployed_run_summary.json", {"published": {}})
    put_json("deployed_mesh_dump.json", {})
    put_json("eager_baseline.json", {})
    put("deployed_trainer.py", DEPLOYED_TRAINER)
    put("calibration_parity.jsonl", "")
    put("deployed_compile_log.jsonl", "")
    put("deployed_step_timeline.jsonl", "")
    put("deployed_guard_dump.jsonl", "")
    put("deployed_alltoall_trace.jsonl", "")
    put("deployed_memory_trace.csv", "step,host_bytes,pool_peak_bytes,cache_entries\n")
    put("token_batches.jsonl", "")

    corpus = Corpus(data)
    order = list(TRUE_TIEBREAK_ORDER)

    put_json("sealed_tiebreak_digests.json", {"digests": _seal_tiebreak(corpus, order)})

    corpus = Corpus(data)
    put_json("sealed_precedence_digests.json", {"digests": _seal_precedence(corpus, order)})

    corpus = Corpus(data)
    faulty_spec, faulty_run, faulty_base = _faulty_run(corpus, corpus.deployed_config, order)
    summary = run_summary(faulty_spec, faulty_run, faulty_base)
    put_json("deployed_run_summary.json", {
        "run_id": faulty_spec.run_id,
        "published": {
            "closing_loss": summary["closing_loss"],
            "drop_rate": summary["drop_rate"],
            "min_host_headroom_bytes": summary["min_host_headroom_bytes"],
            "recompiles_after_warmup": summary["recompiles_after_warmup"],
            "speedup": summary["speedup"],
            "total_recompiles": sum(record["recompiles"] for record in faulty_run["steps"]),
        },
        "source": "deployed_trainer.py",
        "note": "figures as printed by the deployed orchestrator before the job was killed",
    })
    put_json("deployed_mesh_dump.json", {
        "ep_world_size": faulty_spec.ep_world_size,
        "expert_rank": [index // (faulty_spec.num_experts // faulty_spec.ep_world_size)
                        for index in range(faulty_spec.num_experts)],
        "source": "deployed_trainer.py place_experts",
    })

    log = []
    timeline = []
    guard_dump = []
    alltoall = []
    memory_rows = []
    batches = []
    for record in faulty_run["steps"]:
        for event in record["events"]:
            log.append({
                "event": "recompile",
                "step": event["step"],
                "code_object": event["code_object"],
                "rank": event["rank"],
                "guard_key": event["guard_key"],
                "evicted": event["evicted_key"],
            })
        for cause in record["breaks"]:
            log.append({"event": "graph_break", "step": record["step"], "cause": cause})
        timeline.append({
            "step": record["step"],
            "step_us": record["timing"]["step_us"],
            "compile_us": record["timing"]["compile_us"],
            "bubble_us": record["timing"]["bubble_us"],
        })
        guard_dump.append({
            "step": record["step"],
            "keys": sorted(set(item["key"] for item in record["keys"])),
            "cache_entries": record["cache_entries"],
        })
        alltoall.append({
            "step": record["step"],
            "alltoall_bucket": record["alltoall_bucket"],
            "rank_bucket": record["rank_bucket"],
        })
        memory_rows.append({
            "step": record["step"],
            "host_bytes": record["host_bytes"],
            "pool_peak_bytes": record["pool_peak_bytes"],
            "cache_entries": record["cache_entries"],
        })
        batches.append({
            "profile": "deployed",
            "step": record["step"],
            "tokens": record["token_count"],
            "assignments": sum(record["demand"]),
        })
    put("deployed_compile_log.jsonl", _jsonl(log))
    put("deployed_step_timeline.jsonl", _jsonl(timeline))
    put("deployed_guard_dump.jsonl", _jsonl(guard_dump))
    put("deployed_alltoall_trace.jsonl", _jsonl(alltoall))
    put("deployed_memory_trace.csv", _csv(memory_rows, ["step", "host_bytes", "pool_peak_bytes", "cache_entries"]))
    put("token_batches.jsonl", _jsonl(batches))

    corpus = Corpus(data)
    sample_spec = make_spec(corpus, corpus.run_config, order)
    sample_run = simulate(sample_spec, order)
    sample_base = simulate(eager_twin(sample_spec), order, eager=True)
    put_json("eager_baseline.json", {
        "run_id": sample_spec.run_id,
        "profile": "sample",
        "closing_loss": sample_base["steps"][-1]["loss"],
        "step_us": [record["timing"]["step_us"] for record in sample_base["steps"]],
        "losses": [record["loss"] for record in sample_base["steps"]],
        "note": "binary64 reference walk of the shipped sample configuration",
    })
    parity = []
    for record, base in zip(sample_run["steps"], sample_base["steps"]):
        parity.append({
            "step": record["step"],
            "compiled_loss": record["loss"],
            "eager_loss": base["loss"],
            "capacity": record["capacity"],
            "accepted_count": record["accepted_count"],
        })
    put("calibration_parity.jsonl", _jsonl(parity))
    return sorted(written)


# =================================================================== verifier

import io
import shutil
import signal
import subprocess
import tempfile
import threading
import tokenize

from rewardkit import criteria, criterion

APP_OUT = Path("/app/out")
SUBMISSION = APP_OUT / "moeplan.py"
DECOY_ROOT = Path("/app") / "data"
DELIVERED = tuple(sorted(STAGE_ARTIFACTS + REPLAY_ARTIFACTS)) + (
    "stage_manifest.json", "replay_manifest.json", "final_state.json",
)
AGENT_UID = 1000
AGENT_GID = 1000

# rewardkit runs programmatic criteria concurrently in threads, so every
# shared cache entry is built under one lock.
_CACHE = {}
_LOCK = threading.RLock()


def _share_tree(root, writable=False):
    """Open a verifier temp tree to the unprivileged user the agent code runs as."""
    dir_mode = 0o777 if writable else 0o755
    file_mode = 0o666 if writable else 0o644
    os.chmod(root, dir_mode)
    for base, dirs, files in os.walk(root):
        for name in dirs:
            os.chmod(os.path.join(base, name), dir_mode)
        for name in files:
            os.chmod(os.path.join(base, name), file_mode)


def _scratch(prefix, writable=False):
    path = tempfile.mkdtemp(prefix=prefix)
    os.chmod(path, 0o777 if writable else 0o755)
    return path


def _corpus_root():
    with _LOCK:
        if "root" not in _CACHE:
            root = tempfile.mkdtemp(prefix="moecorpus-")
            _write_corpus(Path(root))
            _share_tree(root)
            _CACHE["root"] = root
        return _CACHE["root"]


def _reference_corpus():
    with _LOCK:
        if "corpus" not in _CACHE:
            _CACHE["corpus"] = Corpus(os.path.join(_corpus_root(), "data"))
        return _CACHE["corpus"]


def _reference():
    with _LOCK:
        if "artifacts" not in _CACHE:
            _CACHE["artifacts"] = build_all(_reference_corpus())
        return _CACHE["artifacts"]


def _read_tables(base):
    tables = {}
    for attribute, name in CORPUS_FILES.items():
        path = os.path.join(base, name)
        if name.endswith(".json"):
            tables[name] = read_json(path)
        elif name.endswith(".jsonl"):
            tables[name] = read_jsonl(path)
        else:
            tables[name] = read_csv(path)
    return tables


def _tables():
    with _LOCK:
        if "tables" not in _CACHE:
            _CACHE["tables"] = _read_tables(os.path.join(_corpus_root(), "data"))
        return _CACHE["tables"]


def _submitted(name):
    path = APP_OUT / name
    if not path.is_file():
        raise AssertionError("missing artifact " + name)
    with open(str(path), "r", encoding="utf-8") as handle:
        return json.load(handle)


def _submitted_bytes(name):
    with open(str(APP_OUT / name), "rb") as handle:
        return handle.read()


def _install_copy(module_name="moeplan.py", prefix="moedeliver-"):
    if not SUBMISSION.is_file():
        raise AssertionError("missing delivered program")
    target = _scratch(prefix)
    destination = os.path.join(target, module_name)
    shutil.copyfile(str(SUBMISSION), destination)
    os.chmod(destination, 0o644)
    return destination


def _delivered_path():
    with _LOCK:
        if "copy" not in _CACHE:
            _CACHE["copy"] = _install_copy()
        return _CACHE["copy"]


def _launch(program, args, timeout, flags=("-I", "-S")):
    """Run agent code as the unprivileged agent user; return (exit code, stdout, stderr).

    -S hides site-packages, so only the standard library can be imported.
    """
    command = [sys.executable] + list(flags) + [program] + list(args)
    if os.geteuid() == 0:
        command = ["setpriv", "--reuid=" + str(AGENT_UID), "--regid=" + str(AGENT_GID),
                   "--clear-groups", "--"] + command
    work = _scratch("moework-", writable=True)
    proc = subprocess.Popen(
        command, cwd=work, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, start_new_session=True,
    )
    try:
        out, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        _reap_group(proc.pid)
        proc.communicate()
        return None, b"", b"timed out"
    # A background child the program left behind dies with its session.
    _reap_group(proc.pid)
    return proc.returncode, out, err


def _reap_group(pgid):
    try:
        os.killpg(pgid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass


def _run_delivered(args, program=None, timeout=2400):
    code, out, err = _launch(program or _delivered_path(), args, timeout)
    if code is None:
        raise AssertionError("delivered program timed out on " + " ".join(args))
    if code != 0:
        raise AssertionError(
            "delivered program exited " + str(code) + " on " + " ".join(args)
            + " :: " + err.decode("utf-8", "replace")[-800:]
        )
    return out.decode("utf-8")


def _document(config, extra_rows=()):
    tables = dict(_tables())
    schedule = list(tables["seq_length_schedule.csv"]) + [dict(row) for row in extra_rows]
    tables["seq_length_schedule.csv"] = schedule
    return {"config": config, "tables": tables}


def _document_file(document):
    handle, path = tempfile.mkstemp(suffix=".json")
    os.close(handle)
    with open(path, "wb") as sink:
        sink.write(canonical_bytes(document))
    os.chmod(path, 0o644)
    return path


def _run_document(verb, document):
    return json.loads(_run_delivered([verb, _document_file(document)]))


def _build_into(prefix):
    target = _scratch(prefix, writable=True)
    _run_delivered(["build", os.path.join(_corpus_root(), "data"), target])
    return target


def _read_bytes(path):
    if not os.path.isfile(path):
        return None
    with open(path, "rb") as handle:
        return handle.read()


# ------------------------------------------------------------------ scenarios


def _scenario_rows(profile, seed, count, low, high):
    rng = Xorshift64(seed)
    rows = []
    span = (high - low) // 8
    for step in range(1, count + 1):
        tokens = low + 8 * int(rng.next_unit() * (span + 1))
        rows.append({"profile": profile, "step": str(step), "tokens": str(tokens)})
    return rows


# Scenarios whose document carries its own router grid. The sealed digests of
# such a document are resealed under that grid, so a planner that snaps logits
# to a fixed grid instead of the topology it was handed resolves no key.
_REGRIDDED = {"dense_router": 16}


def _regrid_document(document, levels):
    tables = dict(document["tables"])
    topology = json.loads(json.dumps(tables["model_topology.json"]))
    topology["router"]["quantization_levels"] = levels
    tables["model_topology.json"] = topology
    regridded = {"config": document["config"], "tables": tables}
    order = list(TRUE_TIEBREAK_ORDER)
    tables["sealed_tiebreak_digests.json"] = {
        "digests": _seal_tiebreak(corpus_from_document(regridded), order)}
    tables["sealed_precedence_digests.json"] = {
        "digests": _seal_precedence(corpus_from_document(regridded), order)}
    return regridded


def _scenario(name):
    with _LOCK:
        return _scenario_locked(name)


def _scenario_locked(name):
    if name in _CACHE.setdefault("scenarios", {}):
        return _CACHE["scenarios"][name]
    base = {
        "top_k": 2,
        "capacity_factor": 1.25,
        "capacity_bucket": 8,
        "min_capacity": 6,
        "cache_size_limit": 16,
        "promotion_threshold": 3,
        "dynamic_promotion_enabled": True,
        "expert_bias_enabled": True,
        "router_jitter_slots": 5,
        "compile_mode": "reduce-overhead",
        "mark_dynamic": [],
        "loss_scale": 1024.0,
        "learning_rate": 0.05,
        "clip_threshold": 1.0,
        "aux_loss_weight": 0.01,
        "reset_steps": [],
        "moe_layer_indices": [3, 7, 11],
    }
    table = {
        "dense_router": dict(base, run_id="hidden-dense", num_experts=8, ep_world_size=2,
                             steps=24, warmup_bound=4, seq_profile="hidden_dense",
                             seed=(CHALLENGE_SEED ^ 0x11) & MASK64),
        "expert_starvation": dict(base, run_id="hidden-starve", num_experts=16, ep_world_size=4,
                                  steps=20, warmup_bound=3, seq_profile="hidden_starve",
                                  capacity_factor=1.0, min_capacity=2, promotion_threshold=5,
                                  seed=(CHALLENGE_SEED ^ 0x22) & MASK64),
        "cache_thrash": dict(base, run_id="hidden-thrash", num_experts=12, ep_world_size=2,
                             steps=26, warmup_bound=4, seq_profile="hidden_thrash",
                             capacity_bucket=4, cache_size_limit=3, promotion_threshold=40,
                             seed=(EVAL_SEED ^ 0x33) & MASK64),
        "rank_skew": dict(base, run_id="hidden-skew", num_experts=16, ep_world_size=8,
                          steps=18, warmup_bound=3, seq_profile="hidden_skew",
                          capacity_factor=1.5, min_capacity=5, promotion_threshold=4,
                          seed=(EVAL_SEED ^ 0x44) & MASK64),
        "long_horizon": dict(base, run_id="hidden-long", num_experts=8, ep_world_size=4,
                             steps=40, warmup_bound=5, seq_profile="hidden_long",
                             cache_size_limit=4, promotion_threshold=30,
                             reset_steps=[14, 29],
                             seed=(EVAL_SEED ^ 0x55) & MASK64),
    }
    spans = {
        "dense_router": (48, 120),
        "expert_starvation": (24, 48),
        "cache_thrash": (40, 128),
        "rank_skew": (56, 112),
        "long_horizon": (48, 120),
    }
    config = table[name]
    low, high = spans[name]
    rows = _scenario_rows(config["seq_profile"], config["seed"], config["steps"], low, high)
    document = _document(config, rows)
    if name in _REGRIDDED:
        document = _regrid_document(document, _REGRIDDED[name])
    corpus = corpus_from_document(document)
    order, _ = resolve_tiebreak_key(corpus)
    spec = make_spec(corpus, config, order)
    run = simulate(spec, order)
    payload = {"document": document, "run": run, "spec": spec}
    _CACHE["scenarios"][name] = payload
    return payload


def _dense_router_guard(payload):
    assert sum(r["dropped_tokens"] for r in payload["run"]["steps"]) > 0
    assert payload["spec"].quantization_levels == _REGRIDDED["dense_router"]
    shipped = _tables()["model_topology.json"]["router"]["quantization_levels"]
    assert payload["spec"].quantization_levels != shipped


def _expert_starvation_guard(payload):
    empty = sum(len(r["aux"]["empty_experts"]) for r in payload["run"]["steps"])
    assert empty > 0, "the starvation scenario must starve an expert"


def _cache_thrash_guard(payload):
    evicted = sum(1 for r in payload["run"]["steps"] for e in r["events"] if e["evicted_key"])
    assert evicted > 0, "the thrash scenario must evict"


def _rank_skew_guard(payload):
    skew = [r for r in payload["run"]["steps"]
            if max(r["rank_bucket"].values()) != min(r["rank_bucket"].values())]
    assert skew, "the skew scenario must produce unequal rank buckets"


def _long_horizon_guard(payload):
    assert len(payload["spec"].reset_steps) == 2
    reset_marks = [r["step"] for r in payload["run"]["steps"] if r["reset"]]
    assert reset_marks == list(payload["spec"].reset_steps)


SCENARIO_GUARDS = {
    "cache_thrash": _cache_thrash_guard,
    "dense_router": _dense_router_guard,
    "expert_starvation": _expert_starvation_guard,
    "long_horizon": _long_horizon_guard,
    "rank_skew": _rank_skew_guard,
}


def _canonical_spec():
    corpus = _reference_corpus()
    order = ["expert_index", "running_load", "placement_rank", "bias_rank"]
    return corpus, make_spec(corpus, corpus.deployed_config, order)


# ------------------------------------------------------- shared, built once

_SLOTS = {}


def _once(key, build):
    """Build a shared value once; threads asking for other keys are never held up."""
    with _LOCK:
        slot = _SLOTS.setdefault(key, {"lock": threading.Lock(), "done": False, "value": None})
    with slot["lock"]:
        if not slot["done"]:
            slot["value"] = build()
            slot["done"] = True
        return slot["value"]


def _canonical_builds():
    """Two builds of the delivered program under its own name, shared by two checks."""
    return _once("builds", lambda: (_build_into("moedet1-"), _build_into("moedet2-")))


# ----------------------------------------------------------- held out corpus
#
# A second full corpus written to the same contract with a different expert
# count, schedule, thresholds and gates. The delivered build verb is graded on
# it record by record, so records copied from the shipped corpus earn nothing.


def _eval_root():
    def build():
        root = tempfile.mkdtemp(prefix="moeeval-")
        _write_corpus(Path(root), EVAL_VARIANT)
        _share_tree(root)
        return root
    return _once("eval_root", build)


def _eval_corpus():
    return _once("eval_corpus", lambda: Corpus(os.path.join(_eval_root(), "data")))


def _eval_reference():
    return _once("eval_reference", lambda: build_all(_eval_corpus()))


def _eval_build():
    """The delivered build over the held out corpus; whatever it wrote is graded record by record."""
    def build():
        target = _scratch("moeevalbuild-", writable=True)
        _launch(_delivered_path(), ["build", os.path.join(_eval_root(), "data"), target], 2400)
        return target
    return _once("eval_build", build)


# ----------------------------------------------------------------- documents


VERB_KEYS = {
    "trace": (
        "tie_break_key", "tie_break_matches", "guard_key_index", "recompile_report",
        "graph_break_ledger", "cudagraph_report", "capacity_plan", "mesh_plan",
        "host_memory_report", "warmup_profile",
    ),
    "replay": (
        "tie_break_key", "tie_break_matches", "route_plan", "dispatch_ledger",
        "drop_ledger", "alltoall_ledger", "aux_loss_trace", "loss_curve",
        "gradient_ledger", "optimizer_trace", "convergence_report",
        "baseline_parity", "steptime_report",
    ),
    "settle": ("rejection_ledger", "warmup_profile", "settled_configuration", "probe_steps"),
    "resolve": (
        "tie_break_key", "tie_break_matches", "tie_break_candidates_enumerated",
        "precedence_order", "precedence_matches", "precedence_candidates_enumerated",
        "sealed_configs",
    ),
}

REFERENCE_VERBS = {
    "replay": verb_replay,
    "resolve": verb_resolve,
    "settle": verb_settle,
    "trace": verb_trace,
}

# The five scenario documents and the held out deployed run go through trace,
# replay and resolve. Settle runs where the sweep leaves an admissible
# candidate, so its settled configuration is a real answer.
DOCUMENT_RUNS = tuple(
    (document, verb)
    for document in ("cache_thrash", "dense_router", "eval_deployed",
                     "expert_starvation", "long_horizon", "rank_skew")
    for verb in ("replay", "resolve", "trace")
) + (
    ("dense_router", "settle"),
    ("eval_deployed", "settle"),
    ("long_horizon", "settle"),
)


def _named_document(name):
    def build():
        if name == "eval_deployed":
            data = os.path.join(_eval_root(), "data")
            config = json.loads(json.dumps(_eval_corpus().deployed_config))
            return {"config": config, "tables": _read_tables(data)}
        payload = _scenario(name)
        SCENARIO_GUARDS[name](payload)
        return payload["document"]
    return _once(("document", name), build)


def _named_document_file(name):
    return _once(("document_file", name), lambda: _document_file(_named_document(name)))


def _expected(name, verb):
    return _once(("expected", name, verb), lambda: REFERENCE_VERBS[verb](_named_document(name)))


def _produced(name, verb):
    """What the delivered verb printed for a document, or None when it did not answer."""
    def build():
        try:
            code, out, _ = _launch(_delivered_path(), [verb, _named_document_file(name)], 2400)
            if code != 0:
                return None
            payload = json.loads(out.decode("utf-8"))
            return payload if isinstance(payload, dict) else None
        except Exception:
            return None
    return _once(("produced", name, verb), build)


def _record_for(verb, key):
    """The record whose contract a key printed by a document verb follows."""
    if verb == "resolve" or key in ("tie_break_key", "tie_break_matches"):
        return "sealed_policy_resolution.json"
    if verb == "settle":
        return {
            "rejection_ledger": "rejection_ledger.json",
            "warmup_profile": "warmup_profile.json",
        }.get(key, "settlement_report.json")
    return key + ".json"


def _same_json(left, right):
    # Canonical text comparison keeps False distinct from 0 and 1 distinct from 1.0.
    return canonical_bytes(left) == canonical_bytes(right)


def _built_record(base, name):
    data = _read_bytes(os.path.join(base, name))
    if data is None:
        raise AssertionError("missing artifact " + name)
    return json.loads(data.decode("utf-8"))


def _record_matches(name):
    """One record contract, graded wherever the planner produces it.

    The record written to /app/out from the shipped corpus, the same record
    written by the delivered build over the held out corpus, and every key a
    document verb prints under that record's contract must all agree with the
    reference.
    """
    if name not in _reference():
        raise AssertionError("unknown artifact " + name)
    if not _same_json(_submitted(name), _reference()[name]):
        return False
    if not _same_json(_built_record(_eval_build(), name), _eval_reference()[name]):
        return False
    for document, verb in DOCUMENT_RUNS:
        keys = [key for key in VERB_KEYS[verb] if _record_for(verb, key) == name]
        if not keys:
            continue
        produced = _produced(document, verb)
        if produced is None:
            return False
        expected = _expected(document, verb)
        for key in keys:
            if key not in produced or not _same_json(produced[key], expected[key]):
                return False
    return True


# ------------------------------------------------------------------- criteria


@criterion(description="Two builds of the delivered planner over one corpus agree byte for byte.")
def determinism_across_repeated_runs(workspace: Path) -> bool:
    try:
        first, second = _canonical_builds()
        for name in DELIVERED:
            left = _read_bytes(os.path.join(first, name))
            right = _read_bytes(os.path.join(second, name))
            if left is None or left != right:
                return False
        return True
    except Exception:
        return False


@criterion(description="Each document verb prints exactly the top level keys the schema names for it.")
def document_verbs_print_exactly_their_schema_keys(workspace: Path) -> bool:
    try:
        for document, verb in DOCUMENT_RUNS:
            produced = _produced(document, verb)
            if produced is None or set(produced) != set(VERB_KEYS[verb]):
                return False
        return True
    except Exception:
        return False


@criterion(description="Routing, quantisation and the resolved tie break key agree with the reference.")
def route_plan_matches_reference(workspace: Path) -> bool:
    try:
        assert _reference()["route_plan.json"]["tie_break_events"], "the shipped run must exercise the tie break"
        return _record_matches("route_plan.json")
    except Exception:
        return False


@criterion(description="Capacity aligns to the bucket before the minimum holds.")
def capacity_plan_aligns_then_holds_minimum(workspace: Path) -> bool:
    try:
        corpus, spec = _canonical_spec()
        demand = [0, 1, 2, 40, 41, 42, 43, 44]
        correct = capacity_for_step(spec, demand)
        rival = []
        for value in demand:
            ideal = spec.capacity_factor * float(sum(demand)) / float(spec.num_experts)
            held = max(spec.min_capacity, int(math.ceil(min(float(value), ideal))))
            rival.append(spec.capacity_bucket * ceil_div(held, spec.capacity_bucket))
        assert correct != rival, "fixture no longer separates aligning first from holding first"
        return _record_matches("capacity_plan.json")
    except Exception:
        return False


@criterion(description="Placement follows the affinity table across every rank of the mesh.")
def mesh_plan_follows_the_affinity_table(workspace: Path) -> bool:
    try:
        corpus, spec = _canonical_spec()
        naive = [index // (spec.num_experts // spec.ep_world_size) for index in range(spec.num_experts)]
        assert spec.expert_rank != naive, "fixture no longer separates the affinity walk from integer division"
        return _record_matches("mesh_plan.json")
    except Exception:
        return False


@criterion(description="The collective bucket of every step is the largest rank bucket.")
def alltoall_ledger_takes_the_largest_rank_bucket(workspace: Path) -> bool:
    try:
        return _record_matches("alltoall_ledger.json")
    except Exception:
        return False


@criterion(description="Accepted slots and padded slots agree with the reference.")
def dispatch_ledger_matches_reference(workspace: Path) -> bool:
    try:
        return _record_matches("dispatch_ledger.json")
    except Exception:
        return False


@criterion(description="The dropped count and the dropped gate mass are sourced separately.")
def drop_ledger_separates_count_from_gate_mass(workspace: Path) -> bool:
    try:
        corpus = _reference_corpus()
        order = _reference()["sealed_policy_resolution.json"]["tie_break_key"]
        spec = make_spec(corpus, corpus.calibration_config, order)
        routing = route_step(spec, 1, order)
        dispatch = dispatch_step(spec, routing, [1] * spec.num_experts)
        assert dispatch["dropped_tokens"] > 0, "fixture no longer drops anything"
        assert dispatch["dropped_token_mass"] != float(dispatch["dropped_tokens"]), \
            "fixture no longer separates the dropped count from the dropped gate mass"
        return _record_matches("drop_ledger.json")
    except Exception:
        return False


@criterion(description="Promoted dimensions still specialise on the zero and one sizes.")
def guard_key_index_specializes_zero_and_one(workspace: Path) -> bool:
    try:
        corpus, spec = _canonical_spec()
        guards = GuardState(spec)
        guards.promoted[("moe_block_3", "capacity")] = True
        assert guards.component("moe_block_3", "capacity", 1) == "1"
        assert guards.component("moe_block_3", "capacity", 12) == "dyn"
        return _record_matches("guard_key_index.json")
    except Exception:
        return False


@criterion(description="Recompiles, evictions and the first step over budget agree with the reference.")
def recompile_report_matches_reference(workspace: Path) -> bool:
    try:
        reference = _reference()["recompile_report.json"]
        assert reference["evictions"] > 0, "the shipped run must evict cached entries"
        assert reference["recompiles_after_warmup"] > 0, "the shipped run must recompile past warmup"
        return _record_matches("recompile_report.json")
    except Exception:
        return False


@criterion(description="Break causes are counted and ordered as the catalogue records them.")
def graph_break_ledger_orders_catalogued_causes(workspace: Path) -> bool:
    try:
        reference = _reference()["graph_break_ledger.json"]
        assert reference["cause_order"] == sorted(reference["cause_order"])
        assert reference["total_breaks"] > 0
        return _record_matches("graph_break_ledger.json")
    except Exception:
        return False


@criterion(description="Capture attempts, failure causes and the pool peak agree with the reference.")
def cudagraph_report_capture_failures_match_reference(workspace: Path) -> bool:
    try:
        reference = _reference()["cudagraph_report.json"]
        assert "operation_not_permitted_when_stream_is_capturing" in reference["failure_causes"]
        return _record_matches("cudagraph_report.json")
    except Exception:
        return False


@criterion(description="Host headroom is signed and the ceiling breach is reported.")
def host_memory_report_signed_headroom_matches_reference(workspace: Path) -> bool:
    try:
        reference = _reference()["host_memory_report.json"]
        assert reference["min_host_headroom_bytes"] < 0, "the shipped run must breach the ceiling"
        return _record_matches("host_memory_report.json")
    except Exception:
        return False


@criterion(description="The timing walk, the gated window and the speedup agree with the reference.")
def steptime_report_speedup_and_amortized_compile(workspace: Path) -> bool:
    try:
        reference = _reference()["steptime_report.json"]
        bound = _reference()["warmup_profile.json"]["warmup_bound"]
        assert reference["gated_step_range"][0] == bound + 1, "the gated window opens one step past the warmup bound"
        assert reference["speedup_gate_met"] is False, "the deployed run must miss the throughput gate"
        return _record_matches("steptime_report.json")
    except Exception:
        return False


@criterion(description="The warmup window includes its bound while the gates exclude it.")
def warmup_profile_window_is_inclusive(workspace: Path) -> bool:
    try:
        reference = _reference()["warmup_profile.json"]
        assert reference["window_steps"][-1] == reference["warmup_bound"]
        assert reference["warmup_bound"] not in _reference()["steptime_report.json"]["gated_step_range"][:1]
        return _record_matches("warmup_profile.json")
    except Exception:
        return False


@criterion(description="Both sealed policies are recovered by enumeration.")
def sealed_policy_resolution_matches_reference(workspace: Path) -> bool:
    try:
        reference = _reference()["sealed_policy_resolution.json"]
        assert reference["tie_break_candidates_enumerated"] == 24
        assert reference["precedence_candidates_enumerated"] == 180
        held_out = _eval_reference()["sealed_policy_resolution.json"]
        assert held_out["precedence_order"] != reference["precedence_order"], \
            "the held out gates must resolve a different cause order"
        return _record_matches("sealed_policy_resolution.json")
    except Exception:
        return False


@criterion(description="The balance term is sourced from demand before capacity is applied.")
def aux_loss_trace_sources_predrop_demand(workspace: Path) -> bool:
    try:
        corpus, spec = _canonical_spec()
        routing = route_step(spec, 1, spec.tiebreak_order)
        caps = capacity_for_step(spec, routing["demand"])
        dispatch = dispatch_step(spec, routing, caps)
        aux = aux_loss_step(spec, routing, dispatch)
        rival_total = float(sum(dispatch["accepted_count"]))
        if rival_total > 0 and rival_total != float(sum(routing["demand"])):
            rival = [rd(float(v) / rival_total, spec.decimals) for v in dispatch["accepted_count"]]
            assert aux["assignment_fractions"] != rival, "fixture no longer separates demand from accepted"
        return _record_matches("aux_loss_trace.json")
    except Exception:
        return False


@criterion(description="The settled loss curve and its eager twin agree with the reference.")
def loss_curve_matches_reference(workspace: Path) -> bool:
    try:
        return _record_matches("loss_curve.json")
    except Exception:
        return False


@criterion(description="Padded slots are masked out of the accumulated gradients.")
def gradient_ledger_masks_padded_slots(workspace: Path) -> bool:
    try:
        assert bf16(1.0009765625) != 1.0009765625, "the storage cast must round"
        return _record_matches("gradient_ledger.json")
    except Exception:
        return False


@criterion(description="The clip walk keeps its declared order and the narrow cast rounds before it saturates.")
def optimizer_trace_keeps_the_clip_order(workspace: Path) -> bool:
    try:
        assert fp8_e4m3(447.9) == 448.0, "rounding must precede saturation"
        return _record_matches("optimizer_trace.json")
    except Exception:
        return False


@criterion(description="Convergence, the slope window and the convergence band agree with the reference.")
def convergence_report_matches_reference(workspace: Path) -> bool:
    try:
        reference = _reference()["convergence_report.json"]
        assert reference["verdict"] == "met", "the settled run must converge"
        assert reference["parity_band"] != float(_reference_corpus().convergence_gates["settlement_parity_band"])
        return _record_matches("convergence_report.json")
    except Exception:
        return False


@criterion(description="Step by step parity against the eager baseline agrees with the reference.")
def baseline_parity_matches_reference(workspace: Path) -> bool:
    try:
        return _record_matches("baseline_parity.json")
    except Exception:
        return False


@criterion(description="The settled configuration, its gate figures and its gate verdicts agree with the reference.")
def settlement_report_matches_reference(workspace: Path) -> bool:
    try:
        reference = _reference()["settlement_report.json"]
        assert reference["settled_configuration"]["compile_mode"] != "eager"
        assert reference["gates_met"]["speedup"] is True
        held_out = _eval_reference()["settlement_report.json"]
        assert held_out["gates_met"]["convergence"] != reference["gates_met"]["convergence"], \
            "the held out corpus must exercise the other convergence verdict"
        return _record_matches("settlement_report.json")
    except Exception:
        return False


@criterion(description="The signed margins of the settled configuration agree with the reference.")
def sensitivity_matches_reference(workspace: Path) -> bool:
    try:
        return _record_matches("sensitivity.json")
    except Exception:
        return False


def _cause_order_is_exercised(ledger):
    """Every cause fires, and every adjacent pair of the order meets in one rejected candidate."""
    found = [set(row["all_violations"]) for row in ledger["rejected"]]
    for cause in CAUSE_NAMES:
        assert any(cause in row for row in found), "no rejected candidate carries " + cause
    order = ledger["cause_order"]
    pairs = list(zip(order, order[1:])) + [
        ("capacity_below_minimum", "drop_tolerance_exceeded"),
        ("recompile_budget_exceeded", "speedup_gate_unmet"),
    ]
    for first, second in pairs:
        assert any(first in row and second in row for row in found), \
            "no rejected candidate carries both " + first + " and " + second
    assert ledger["admissible_candidates"], "the held out sweep must leave a candidate"
    assert ledger["prefiltered"], "the held out sweep must prefilter a candidate"


@criterion(description="Every rejected candidate is attributed to the first violated cause.")
def rejection_ledger_follows_resolved_cause_order(workspace: Path) -> bool:
    try:
        reference = _reference()["rejection_ledger.json"]
        evaluated = _reference()["settlement_report.json"]["candidates_evaluated"]
        assert sorted(reference["per_cause_counts"]) == sorted(CAUSE_NAMES)
        accounted = (
            sum(reference["per_cause_counts"].values())
            + len(reference["admissible_candidates"])
            + len(reference["prefiltered"])
        )
        assert accounted == evaluated, "every candidate must be accounted for exactly once"
        assert sum(reference["per_cause_counts"].values()) > 0
        _cause_order_is_exercised(_eval_reference()["rejection_ledger.json"])
        return _record_matches("rejection_ledger.json")
    except Exception:
        return False


@criterion(description="The audit block keeps each definition on its own source and window.")
def audit_statistics_use_non_parallel_definitions(workspace: Path) -> bool:
    try:
        assert len(_reference()["audit_statistics.json"]) == 17
        return _record_matches("audit_statistics.json")
    except Exception:
        return False


PUBLISHED_DEPARTURES = (
    "closing_loss", "min_host_headroom_bytes", "recompiles_after_warmup", "speedup", "total_recompiles",
)


@criterion(description="The diagnosis of the deployed run agrees with the reference.")
def deployed_diagnosis_matches_reference(workspace: Path) -> bool:
    try:
        diagnosis = _reference()["deployed_diagnosis.json"]
        assert diagnosis["admissible"] is False
        assert diagnosis["published_agrees_with_replay"] is False
        assert diagnosis["departing_settings"], "the deployed configuration must depart"
        for field in PUBLISHED_DEPARTURES:
            entry = diagnosis["published_vs_replayed"][field]
            assert entry["published"] != entry["replayed"], "the published " + field + " must depart"
        return _record_matches("deployed_diagnosis.json")
    except Exception:
        return False


@criterion(description="The residuals, the record counts and the artifact count agree with the reference.")
def validation_report_matches_reference(workspace: Path) -> bool:
    try:
        reference = _reference()["validation_report.json"]
        assert reference["artifact_count"] == len(reference["record_counts"])
        assert any(value != 0.0 for value in reference["residuals"].values())
        return _record_matches("validation_report.json")
    except Exception:
        return False


FINAL_STATE_KEYS = (
    "closing_loss", "convergence_verdict", "deployed_admissible", "digest_of_digests",
    "first_step_over_budget", "precedence_order", "replay_manifest_sha256",
    "settled_configuration", "settlement_salt", "speedup", "stage_manifest_sha256",
    "tie_break_key", "total_artifacts",
)


def _manifests_and_final_state_match(reference, stage, replay, final):
    """Manifest shapes, coverage and every non digest field of the final state."""
    if sorted(stage) != ["artifact_count", "artifact_sha256", "stage"]:
        return False
    if sorted(replay) != ["artifact_count", "artifact_sha256", "stage", "stage_manifest_sha256"]:
        return False
    if sorted(final) != sorted(FINAL_STATE_KEYS):
        return False
    if not _same_json(stage["stage"], "dispatch_and_compile"):
        return False
    if not _same_json(replay["stage"], "replay_and_settlement"):
        return False
    if not _same_json(stage["artifact_count"], len(STAGE_ARTIFACTS)):
        return False
    if not _same_json(replay["artifact_count"], len(REPLAY_ARTIFACTS)):
        return False
    if sorted(stage["artifact_sha256"]) != sorted(STAGE_ARTIFACTS):
        return False
    if sorted(replay["artifact_sha256"]) != sorted(REPLAY_ARTIFACTS):
        return False
    expected = {
        "closing_loss": reference["convergence_report.json"]["closing_loss"],
        "convergence_verdict": reference["convergence_report.json"]["verdict"],
        "deployed_admissible": reference["deployed_diagnosis.json"]["admissible"],
        "first_step_over_budget": reference["recompile_report.json"]["first_step_over_budget"],
        "precedence_order": reference["sealed_policy_resolution.json"]["precedence_order"],
        "settled_configuration": reference["settlement_report.json"]["settled_configuration"],
        "speedup": reference["settlement_report.json"]["settled_gate_figures"]["speedup"],
        "tie_break_key": reference["sealed_policy_resolution.json"]["tie_break_key"],
        "total_artifacts": len(STAGE_ARTIFACTS) + len(REPLAY_ARTIFACTS) + 3,
    }
    for key in sorted(expected):
        if not _same_json(final[key], expected[key]):
            return False
    return True


def _digest_chain_holds(base, reference):
    """Every digest in the chain is the digest of the bytes the build wrote beside it."""
    def raw(name):
        data = _read_bytes(os.path.join(base, name))
        if data is None:
            raise AssertionError("missing artifact " + name)
        return data

    stage = json.loads(raw("stage_manifest.json").decode("utf-8"))
    replay = json.loads(raw("replay_manifest.json").decode("utf-8"))
    final = json.loads(raw("final_state.json").decode("utf-8"))
    if not _manifests_and_final_state_match(reference, stage, replay, final):
        return False
    for manifest in (stage, replay):
        for name, digest in sorted(manifest["artifact_sha256"].items()):
            if sha256_hex(raw(name)) != digest:
                return False
    if replay["stage_manifest_sha256"] != sha256_hex(raw("stage_manifest.json")):
        return False
    folded = {
        "replay": sha256_hex(raw("replay_manifest.json")),
        "salt": digest_of(final["settled_configuration"]),
        "stage": sha256_hex(raw("stage_manifest.json")),
    }
    return (
        _same_json(final["digest_of_digests"], digest_of(folded))
        and _same_json(final["settlement_salt"], folded["salt"])
        and _same_json(final["stage_manifest_sha256"], folded["stage"])
        and _same_json(final["replay_manifest_sha256"], folded["replay"])
    )


@criterion(description="The manifests, the final state and the three level digest chain agree with the reference.")
def manifests_and_digest_chain_match_reference(workspace: Path) -> bool:
    try:
        return (
            _digest_chain_holds(str(APP_OUT), _reference())
            and _digest_chain_holds(_eval_build(), _eval_reference())
        )
    except Exception:
        return False


@criterion(description="An unreadable input file or an unknown input value is rejected by name.")
def planner_errors_name_the_rejected_input(workspace: Path) -> bool:
    try:
        program = _delivered_path()
        root = _scratch("moebroken-")
        corpus = os.path.join(root, "data")
        shutil.copytree(os.path.join(_eval_root(), "data"), corpus)
        with open(os.path.join(corpus, "deployed_config.json"), "w", encoding="utf-8") as sink:
            sink.write("{not json\n")
        _share_tree(root)
        target = _scratch("moebrokenout-", writable=True)
        code, _, err = _launch(program, ["build", corpus, target], 2400)
        if code in (None, 0) or b"deployed_config.json" not in err:
            return False
        holder = _scratch("moebrokendoc-")
        broken = os.path.join(holder, "moe-rejected-document.json")
        with open(broken, "w", encoding="utf-8") as sink:
            sink.write("{not json\n")
        os.chmod(broken, 0o644)
        code, _, err = _launch(program, ["replay", broken], 2400)
        if code in (None, 0) or b"moe-rejected-document.json" not in err:
            return False
        document = _named_document("long_horizon")
        config = dict(document["config"], seq_profile="zz-unlisted-profile")
        unknown = os.path.join(holder, "moe-unlisted-profile.json")
        with open(unknown, "wb") as sink:
            sink.write(canonical_bytes({"config": config, "tables": document["tables"]}))
        os.chmod(unknown, 0o644)
        code, _, err = _launch(program, ["trace", unknown], 2400)
        if code in (None, 0):
            return False
        return b"zz-unlisted-profile" in err or b"moe-unlisted-profile.json" in err
    except Exception:
        return False


@criterion(description="The delivered planner carries a produced answer as a literal constant.")
def negative_hardcoded_sample_answers(workspace: Path) -> bool:
    try:
        text = SUBMISSION.read_text(encoding="utf-8")
        reference = _reference()
        marks = [
            str(reference["convergence_report.json"]["closing_loss"]),
            str(reference["settlement_report.json"]["settled_gate_figures"]["speedup"]),
        ]
        final_path = APP_OUT / "final_state.json"
        if final_path.is_file():
            final = _submitted("final_state.json")
            for key in ("digest_of_digests", "stage_manifest_sha256", "replay_manifest_sha256"):
                if final.get(key):
                    marks.append(str(final[key]))
        code = " ".join(
            token.string
            for token in tokenize.generate_tokens(io.StringIO(text).readline)
            if token.type != tokenize.COMMENT
        )
        # Holds when the cheat happened; the negative weight does the punishing.
        return any(mark in code for mark in marks)
    except Exception:
        return False


@criterion(description="Renaming the planner, its corpus directory and its output directory changes what it writes.")
def negative_filename_dependent_behaviour(workspace: Path) -> bool:
    try:
        first, second = _canonical_builds()
        # Only records two canonical builds agree on can witness a name dependence;
        # run to run drift is the determinism check's business, not this one's.
        stable = [name for name in DELIVERED
                  if _read_bytes(os.path.join(first, name)) is not None
                  and _read_bytes(os.path.join(first, name)) == _read_bytes(os.path.join(second, name))]
        renamed_root = _scratch("moerename-")
        corpus = os.path.join(renamed_root, "other_inputs")
        shutil.copytree(os.path.join(_corpus_root(), "data"), corpus)
        _share_tree(renamed_root)
        target = _scratch("moerenamed-results-", writable=True)
        program = _install_copy("zz_other_name.py", prefix="moerenamedprog-")
        code, _, _ = _launch(program, ["build", corpus, target], 2400)
        if code != 0:
            return False
        differing = [name for name in stable
                     if _read_bytes(os.path.join(target, name)) != _read_bytes(os.path.join(first, name))]
        # Holds when the cheat happened; the negative weight does the punishing.
        return bool(differing)
    except Exception:
        return False


@criterion(description="A document verb changes its answer when a corpus appears at the shipped data location.")
def negative_reads_training_corpus_at_runtime(workspace: Path) -> bool:
    try:
        if DECOY_ROOT.exists():
            return False
        path = _named_document_file("dense_router")
        program = _delivered_path()
        absent = _launch(program, ["replay", path], 2400)
        _write_corpus(DECOY_ROOT.parent / "decoy-build")
        shutil.move(str(DECOY_ROOT.parent / "decoy-build" / "data"), str(DECOY_ROOT))
        shutil.rmtree(str(DECOY_ROOT.parent / "decoy-build"), ignore_errors=True)
        _share_tree(str(DECOY_ROOT))
        try:
            present = _launch(program, ["replay", path], 2400)
        finally:
            shutil.rmtree(str(DECOY_ROOT), ignore_errors=True)
        if absent[0] is None or present[0] is None:
            return False
        # Holds when the cheat happened; the negative weight does the punishing.
        return (absent[0], absent[1]) != (present[0], present[1])
    except Exception:
        return False


@criterion(description="The delivered planner mutates the corpus directory it was given.")
def negative_writes_to_shipped_corpus(workspace: Path) -> bool:
    try:
        root = _scratch("moeguard-")
        corpus = os.path.join(root, "data")
        shutil.copytree(os.path.join(_corpus_root(), "data"), corpus)
        _share_tree(root, writable=True)
        before = {}
        for name in sorted(os.listdir(corpus)):
            before[name] = sha256_hex(_read_bytes(os.path.join(corpus, name)))
        target = _scratch("moeguardout-", writable=True)
        _launch(_delivered_path(), ["build", corpus, target], 2400)
        touched = []
        for name in sorted(before):
            payload = _read_bytes(os.path.join(corpus, name))
            if payload is None or sha256_hex(payload) != before[name]:
                touched.append(name)
        extra = sorted(set(os.listdir(corpus)) - set(before))
        # Holds when the cheat happened; the negative weight does the punishing.
        return bool(touched or extra)
    except Exception:
        return False


# Runs the delivered program inside an audit hook. Starting any other program,
# by any route the interpreter offers, ends the run with a marker on stderr.
_AUDIT_WRAPPER = """\
import os
import runpy
import sys

_EVENTS = ("subprocess.Popen", "os.system", "os.exec", "os.posix_spawn", "os.spawn", "os.startfile")


def _hook(event, args):
    if event in _EVENTS:
        os.write(2, b"moe-audit-tripped:" + event.encode("ascii"))
        os._exit(97)


sys.addaudithook(_hook)
sys.argv = sys.argv[1:]
runpy.run_path(sys.argv[0], run_name="__main__")
"""


@criterion(description="The delivered planner starts another program while it runs.")
def negative_shells_out_to_another_program(workspace: Path) -> bool:
    try:
        holder = _scratch("moeaudit-")
        wrapper = os.path.join(holder, "moe_audit_wrapper.py")
        with open(wrapper, "w", encoding="utf-8") as sink:
            sink.write(_AUDIT_WRAPPER)
        os.chmod(wrapper, 0o644)
        program = _delivered_path()
        target = _scratch("moeauditout-", writable=True)
        runs = (
            ["build", os.path.join(_corpus_root(), "data"), target],
            ["replay", _named_document_file("long_horizon")],
            ["trace", _named_document_file("long_horizon")],
        )
        tripped = False
        for args in runs:
            _, _, err = _launch(wrapper, [program] + list(args), 2400)
            tripped = tripped or b"moe-audit-tripped:" in err
        # Holds when the cheat happened; the negative weight does the punishing.
        return tripped
    except Exception:
        return False


criteria.determinism_across_repeated_runs(weight=1)
criteria.document_verbs_print_exactly_their_schema_keys(weight=1)
criteria.alltoall_ledger_takes_the_largest_rank_bucket(weight=3)
criteria.baseline_parity_matches_reference(weight=3)
criteria.optimizer_trace_keeps_the_clip_order(weight=3)
criteria.planner_errors_name_the_rejected_input(weight=3)
criteria.sensitivity_matches_reference(weight=3)
criteria.audit_statistics_use_non_parallel_definitions(weight=5)
criteria.aux_loss_trace_sources_predrop_demand(weight=5)
criteria.capacity_plan_aligns_then_holds_minimum(weight=5)
criteria.convergence_report_matches_reference(weight=5)
criteria.cudagraph_report_capture_failures_match_reference(weight=5)
criteria.deployed_diagnosis_matches_reference(weight=5)
criteria.dispatch_ledger_matches_reference(weight=5)
criteria.drop_ledger_separates_count_from_gate_mass(weight=5)
criteria.gradient_ledger_masks_padded_slots(weight=5)
criteria.graph_break_ledger_orders_catalogued_causes(weight=5)
criteria.guard_key_index_specializes_zero_and_one(weight=5)
criteria.host_memory_report_signed_headroom_matches_reference(weight=5)
criteria.loss_curve_matches_reference(weight=5)
criteria.manifests_and_digest_chain_match_reference(weight=5)
criteria.mesh_plan_follows_the_affinity_table(weight=5)
criteria.recompile_report_matches_reference(weight=5)
criteria.rejection_ledger_follows_resolved_cause_order(weight=5)
criteria.route_plan_matches_reference(weight=5)
criteria.sealed_policy_resolution_matches_reference(weight=5)
criteria.settlement_report_matches_reference(weight=5)
criteria.steptime_report_speedup_and_amortized_compile(weight=5)
criteria.validation_report_matches_reference(weight=5)
criteria.warmup_profile_window_is_inclusive(weight=5)
criteria.negative_filename_dependent_behaviour(weight=-5)
criteria.negative_hardcoded_sample_answers(weight=-5)
criteria.negative_reads_training_corpus_at_runtime(weight=-5)
criteria.negative_shells_out_to_another_program(weight=-3)
criteria.negative_writes_to_shipped_corpus(weight=-3)


if __name__ == "__main__":
    _write_corpus(Path(sys.argv[1]))
