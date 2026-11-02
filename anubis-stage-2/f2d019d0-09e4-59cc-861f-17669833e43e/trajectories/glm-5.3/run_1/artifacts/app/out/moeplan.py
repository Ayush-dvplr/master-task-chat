#!/usr/bin/env python3
"""Planner for the mixture of experts training corpus.

Verbs:
    build   DATA_DIR OUT_DIR
    trace   CONFIG_DOCUMENT
    replay  RUN_DOCUMENT
    settle  CANDIDATE_DOCUMENT
    resolve SEALED_DOCUMENT

Standard library only.  Two runs over the same corpus produce byte identical
records.  Every error raised names the input value or the input file rejected.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import math
import os
import struct
import sys

MASK64 = (1 << 64) - 1
FNV_OFFSET = 0xCBF29CE484222325
FNV_PRIME = 0x100000001B3
GOLDEN = 0x9E3779B97F4A7C15

ROUTER_NAME = "router"
TIE_BREAK_FIELDS = ("expert_index", "running_load", "placement_rank", "bias_rank")
GUARD_DIMS = ("tokens", "capacity", "local_experts")
CAUSE_CAPTURE_DISABLED = "capture_disabled_for_mode"
CAUSE_CAPTURE_STREAM = "operation_not_permitted_when_stream_is_capturing"
CAUSE_CAPTURE_DYNAMIC = "dynamic_dimension_in_guard_key"
CAPTURE_CAUSES = (CAUSE_CAPTURE_DISABLED, CAUSE_CAPTURE_STREAM, CAUSE_CAPTURE_DYNAMIC)
REJECTION_CAUSES = (
    "eager_mode_forbidden",
    "recompile_budget_exceeded",
    "speedup_gate_unmet",
    "memory_ceiling_exceeded",
    "drop_tolerance_exceeded",
    "convergence_band_unmet",
    "capacity_below_minimum",
)
ACCUMULATION_ORDER = ["slot_ascending", "expert_index_ascending"]

STAGE_ONE = "dispatch_and_compile"
STAGE_TWO = "replay_and_settlement"

STAGE_ONE_RECORDS = (
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

STAGE_TWO_RECORDS = (
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

COUNTED_RECORDS = STAGE_ONE_RECORDS + STAGE_TWO_RECORDS[:11]
ALL_RECORDS = (
    STAGE_ONE_RECORDS
    + STAGE_TWO_RECORDS
    + ("stage_manifest.json", "replay_manifest.json", "final_state.json")
)

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


class PlanError(Exception):
    """Every instance names the input value or input file that was rejected."""


# --------------------------------------------------------------- canonical form


def canonical_text(value):
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def canonical_bytes(value):
    return canonical_text(value).encode("utf-8")


def canonical_digest(value):
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


# --------------------------------------------------------------- numeric helpers


def mix_hash(parts):
    state = FNV_OFFSET
    for part in parts:
        state ^= (int(part) & MASK64)
        state = (state * FNV_PRIME) & MASK64
        state ^= (state >> 29)
    return state & MASK64


class XorShift64(object):
    __slots__ = ("state",)

    def __init__(self, seed):
        state = int(seed) & MASK64
        if state == 0:
            state = GOLDEN
        self.state = state

    def next_u64(self):
        x = self.state
        x ^= (x << 13) & MASK64
        x ^= (x >> 7)
        x ^= (x << 17) & MASK64
        self.state = x & MASK64
        return self.state

    def unit(self):
        return (self.next_u64() >> 11) * (2.0 ** -53)


def f32(value):
    return struct.unpack("<f", struct.pack("<f", float(value)))[0]


def bf16(value):
    bits = struct.unpack("<I", struct.pack("<f", float(value)))[0]
    lower = bits & 0xFFFF
    upper = bits >> 16
    if lower > 0x8000 or (lower == 0x8000 and (upper & 1) == 1):
        upper += 1
    upper &= 0xFFFF
    return struct.unpack("<f", struct.pack("<I", upper << 16))[0]


def round_half_even(value):
    floor = math.floor(value)
    diff = value - floor
    if diff > 0.5:
        return floor + 1
    if diff < 0.5:
        return floor
    return floor if (floor % 2) == 0 else floor + 1


def fp8_cast(value):
    magnitude = abs(float(value))
    if magnitude == 0.0:
        return 0.0
    sign = -1.0 if value < 0 else 1.0
    mantissa, exponent = math.frexp(magnitude)
    unbiased = exponent - 1
    if unbiased < -6:
        quantum = 2.0 ** -9
    else:
        quantum = 2.0 ** (unbiased - 3)
    rounded = round_half_even(magnitude / quantum) * quantum
    if rounded > 448.0:
        rounded = 448.0
    return sign * rounded


class Rounder(object):
    def __init__(self, decimals):
        self.decimals = int(decimals)

    def __call__(self, value):
        out = round(float(value), self.decimals)
        if out == 0.0:
            return 0.0
        return out


# --------------------------------------------------------------- corpus access


def _csv_rows_from_text(text, name):
    rows = []
    lines = [line for line in text.split("\n") if line.strip() != ""]
    if not lines:
        raise PlanError("table file '%s' holds no header row" % name)
    header = lines[0].split(",")
    for line in lines[1:]:
        cells = line.split(",")
        if len(cells) != len(header):
            raise PlanError(
                "table file '%s' holds a row with %d cells against %d header columns"
                % (name, len(cells), len(header))
            )
        rows.append(dict(zip(header, cells)))
    return rows


class Corpus(object):
    """Read only view of one corpus, whether loaded from a directory or a document."""

    def __init__(self, tables, source):
        if not isinstance(tables, dict):
            raise PlanError("tables of '%s' is not an object" % source)
        self.tables = tables
        self.source = source
        tolerances = self.json_table("validation_tolerances.json")
        self.r_float = Rounder(tolerances["float_decimals"])
        self.r_time = Rounder(tolerances["time_decimals"])
        self.float_decimals = int(tolerances["float_decimals"])
        self.time_decimals = int(tolerances["time_decimals"])
        self.topology = self.json_table("model_topology.json")
        self.gates = self.json_table("convergence_gates.json")
        self.memory_gates = self.json_table("memory_gates.json")
        self.steptime_gates = self.json_table("steptime_gates.json")
        self.candidates = self.json_table("capacity_candidates.json")

    # -- loading ---------------------------------------------------------

    @classmethod
    def from_directory(cls, data_dir):
        if not os.path.isdir(data_dir):
            raise PlanError("corpus directory '%s' is not a directory" % data_dir)
        tables = {}
        for name in sorted(os.listdir(data_dir)):
            path = os.path.join(data_dir, name)
            if not os.path.isfile(path):
                continue
            if name.endswith(".json"):
                tables[name] = _load_json(path)
            elif name.endswith(".jsonl"):
                tables[name] = _load_jsonl(path)
            elif name.endswith(".csv"):
                with open(path, "r", encoding="utf-8") as handle:
                    tables[name] = _csv_rows_from_text(handle.read(), name)
        if not tables:
            raise PlanError("corpus directory '%s' holds no corpus tables" % data_dir)
        return cls(tables, data_dir)

    @classmethod
    def from_document(cls, document, source):
        if not isinstance(document, dict):
            raise PlanError("document '%s' is not a JSON object" % source)
        if set(document.keys()) != {"config", "tables"}:
            raise PlanError(
                "document '%s' must carry exactly the keys config and tables" % source
            )
        return cls(document["tables"], source)

    # -- accessors -------------------------------------------------------

    def need(self, name):
        if name not in self.tables:
            raise PlanError("table file '%s' is missing from '%s'" % (name, self.source))
        return self.tables[name]

    def json_table(self, name):
        value = self.need(name)
        if not isinstance(value, dict):
            raise PlanError("table file '%s' does not hold a JSON object" % name)
        return value

    def rows(self, name):
        value = self.need(name)
        if not isinstance(value, list):
            raise PlanError("table file '%s' does not hold a list of rows" % name)
        for row in value:
            if not isinstance(row, dict):
                raise PlanError("table file '%s' holds a row that is not an object" % name)
        return value

def _load_json(path):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except ValueError as exc:
        raise PlanError("file '%s' is not valid JSON: %s" % (path, exc))


def _load_jsonl(path):
    rows = []
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip() == "":
                continue
            try:
                rows.append(json.loads(line))
            except ValueError as exc:
                raise PlanError("file '%s' holds a line that is not valid JSON: %s" % (path, exc))
    return rows


# --------------------------------------------------------------- configuration


def validate_config(config, source):
    if not isinstance(config, dict):
        raise PlanError("configuration of '%s' is not an object" % source)
    for key in CONFIG_KEYS:
        if key not in config:
            raise PlanError("configuration of '%s' is missing the key '%s'" % (source, key))
    for key in ("aux_loss_weight", "capacity_factor", "clip_threshold", "learning_rate", "loss_scale"):
        if not isinstance(config[key], float):
            raise PlanError("configuration value %s=%r must be a float" % (key, config[key]))
    for key in (
        "cache_size_limit",
        "capacity_bucket",
        "ep_world_size",
        "min_capacity",
        "num_experts",
        "promotion_threshold",
        "router_jitter_slots",
        "seed",
        "steps",
        "top_k",
        "warmup_bound",
    ):
        if not isinstance(config[key], int) or isinstance(config[key], bool):
            raise PlanError("configuration value %s=%r must be an integer" % (key, config[key]))
    if not isinstance(config["compile_mode"], str):
        raise PlanError("configuration value compile_mode=%r must be a string" % config["compile_mode"])
    if config["compile_mode"] not in ("reduce-overhead", "default", "eager"):
        raise PlanError("configuration value compile_mode=%r is not a known compile mode" % config["compile_mode"])
    for key in ("dynamic_promotion_enabled", "expert_bias_enabled"):
        if not isinstance(config[key], bool):
            raise PlanError("configuration value %s=%r must be a boolean" % (key, config[key]))
    if not isinstance(config["mark_dynamic"], list) or not all(
        isinstance(item, str) for item in config["mark_dynamic"]
    ):
        raise PlanError("configuration value mark_dynamic=%r must be a list of strings" % config["mark_dynamic"])
    for name in config["mark_dynamic"]:
        if name not in ("tokens", "capacity"):
            raise PlanError("configuration value mark_dynamic names the unknown dimension %r" % name)
    for key in ("moe_layer_indices", "reset_steps"):
        if not isinstance(config[key], list) or not all(
            isinstance(item, int) and not isinstance(item, bool) for item in config[key]
        ):
            raise PlanError("configuration value %s=%r must be a list of integers" % (key, config[key]))
    if not isinstance(config["seq_profile"], str):
        raise PlanError("configuration value seq_profile=%r must be a string" % config["seq_profile"])
    if not isinstance(config["run_id"], str):
        raise PlanError("configuration value run_id=%r must be a string" % config["run_id"])
    if int(config["capacity_bucket"]) < 1:
        raise PlanError("configuration value capacity_bucket=%r must be at least one" % config["capacity_bucket"])
    if int(config["min_capacity"]) < 0:
        raise PlanError("configuration value min_capacity=%r must not be negative" % config["min_capacity"])
    if int(config["steps"]) < 1:
        raise PlanError("configuration value steps=%r must be at least one" % config["steps"])
    if int(config["warmup_bound"]) < 0 or int(config["warmup_bound"]) > int(config["steps"]):
        raise PlanError(
            "configuration value warmup_bound=%r lies outside 0..steps=%r"
            % (config["warmup_bound"], config["steps"])
        )
    if int(config["top_k"]) < 1 or int(config["top_k"]) > int(config["num_experts"]):
        raise PlanError(
            "configuration value top_k=%r lies outside 1..num_experts=%r"
            % (config["top_k"], config["num_experts"])
        )
    for step in config["reset_steps"]:
        if int(step) < 1 or int(step) > int(config["steps"]):
            raise PlanError(
                "configuration value reset_steps holds %r outside 1..steps=%r"
                % (step, config["steps"])
            )
    return config


def check_mesh(corpus, config):
    experts = int(config["num_experts"])
    world = int(config["ep_world_size"])
    if experts % world != 0:
        raise PlanError(
            "configuration value num_experts=%r does not divide by ep_world_size=%r"
            % (experts, world)
        )
    rows = [row for row in corpus.rows("rank_affinity.csv") if int(row["ep_world_size"]) == world]
    if len(rows) != world:
        raise PlanError(
            "table file 'rank_affinity.csv' holds %d rows for ep_world_size=%r"
            % (len(rows), world)
        )
    for index in range(experts):
        found = False
        for row in corpus.rows("expert_placement.csv"):
            if int(row["expert_index"]) == index:
                found = True
                break
        if not found:
            raise PlanError("table file 'expert_placement.csv' has no row for expert_index=%r" % index)
        found = False
        for row in corpus.rows("expert_cost_table.csv"):
            if int(row["expert_index"]) == index:
                found = True
                break
        if not found:
            raise PlanError("table file 'expert_cost_table.csv' has no row for expert_index=%r" % index)
    if config["expert_bias_enabled"]:
        for index in range(experts):
            found = False
            for row in corpus.rows("expert_bias_table.csv"):
                if int(row["expert_index"]) == index:
                    found = True
                    break
            if not found:
                raise PlanError(
                    "table file 'expert_bias_table.csv' has no row for expert_index=%r" % index
                )


def schedule_tokens(corpus, config):
    profile = config["seq_profile"]
    rows = []
    for row in corpus.rows("seq_length_schedule.csv"):
        if row["profile"] == profile:
            rows.append(row)
    if not rows:
        raise PlanError(
            "table file 'seq_length_schedule.csv' holds no rows for seq_profile=%r" % profile
        )
    try:
        rows.sort(key=lambda row: int(row["step"]))
    except ValueError:
        raise PlanError(
            "table file 'seq_length_schedule.csv' holds a non integer step for seq_profile=%r" % profile
        )
    tokens = []
    total = int(config["steps"])
    for index in range(total):
        row = rows[index % len(rows)]
        try:
            tokens.append(int(row["tokens"]))
        except ValueError:
            raise PlanError(
                "table file 'seq_length_schedule.csv' holds the non integer token count %r"
                % row["tokens"]
            )
    return tokens


def expert_placement(corpus, config):
    experts = int(config["num_experts"])
    world = int(config["ep_world_size"])
    per_rank = experts // world
    groups = [None] * experts
    ordered = []
    for row in corpus.rows("expert_placement.csv"):
        index = int(row["expert_index"])
        if index < experts:
            groups[index] = int(row["placement_group"])
            ordered.append((int(row["placement_group"]), index))
    ordered.sort()
    ranks = sorted(
        (row for row in corpus.rows("rank_affinity.csv") if int(row["ep_world_size"]) == world),
        key=lambda row: int(row["group_order"]),
    )
    if len(ranks) != world:
        raise PlanError(
            "table file 'rank_affinity.csv' holds %d rows for ep_world_size=%r" % (len(ranks), world)
        )
    rank_order = [int(row["rank"]) for row in ranks]
    expert_rank = [None] * experts
    for block, rank in enumerate(rank_order):
        for offset in range(per_rank):
            expert_rank[ordered[block * per_rank + offset][1]] = rank
    rank_experts = {rank: [] for rank in range(world)}
    for index in range(experts):
        rank_experts[expert_rank[index]].append(index)
    for rank in rank_experts:
        rank_experts[rank].sort()
    return expert_rank, rank_experts, groups


# --------------------------------------------------------------- routing


class Router(object):
    def __init__(self, corpus, config, tie_break_key):
        self.corpus = corpus
        self.config = config
        self.tie_break_key = tuple(tie_break_key)
        self.levels = float(corpus.topology["router"]["quantization_levels"])
        self.jitter_scale = float(corpus.topology["router"]["jitter_scale"])
        self.bias_gain = {}
        for row in corpus.rows("expert_bias_table.csv"):
            self.bias_gain[int(row["expert_index"])] = row["bias_gain"]
        self.cache = {}

    def _identity(self, config):
        return (
            int(config["seed"]),
            int(config["num_experts"]),
            int(config["top_k"]),
            int(config["router_jitter_slots"]),
            bool(config["expert_bias_enabled"]),
            int(config["ep_world_size"]),
        )

    def step(self, config, step_index, tokens, placement_rank):
        key = (self._identity(config), int(step_index), int(tokens))
        hit = self.cache.get(key)
        if hit is not None:
            return hit
        result = self._route(config, step_index, tokens, placement_rank)
        self.cache[key] = result
        return result

    def _route(self, config, step_index, tokens, placement_rank):
        rng = XorShift64(mix_hash([int(config["seed"]), int(step_index)]))
        experts = int(config["num_experts"])
        slots = int(config["router_jitter_slots"])
        salts = [rng.unit() for _ in range(tokens)]
        phases = [rng.unit() for _ in range(experts)]
        if bool(config["expert_bias_enabled"]):
            bias_draw = [rng.unit() for _ in range(experts)]
        else:
            bias_draw = None
            for _ in range(experts):
                pass
        jitter = [rng.unit() for _ in range(slots)] if slots > 0 else []
        r = self.corpus.r_float
        token_bits = [int(math.floor(value * (2.0 ** 52))) for value in salts]
        expert_bits = [int(math.floor(value * (2.0 ** 52))) for value in phases]
        bias_values = []
        for index in range(experts):
            if bias_draw is None:
                bias_values.append(0.0)
            else:
                gain = float(self.bias_gain[index])
                bias_values.append(r((bias_draw[index] * 2.0 - 1.0) * gain))
        quantized = []
        for index in range(tokens):
            row = []
            for expert in range(experts):
                affinity = XorShift64(mix_hash([token_bits[index], expert_bits[expert]])).next_u64()
                unit = r((affinity >> 11) * (2.0 ** -53))
                if slots > 0:
                    jitter_value = r((jitter[(index + expert) % slots] * 2.0 - 1.0) * self.jitter_scale)
                else:
                    jitter_value = 0.0
                logit = r(r(r(unit * 2.0 - 1.0) + bias_values[expert]) + jitter_value)
                row.append(round_half_even(logit * self.levels) / self.levels)
            quantized.append(row)
        top_k = int(config["top_k"])
        running = [0] * experts
        demand = [0] * experts
        gate_mass = [0.0] * experts
        assignments = []
        events = []
        bias_rank = [int(math.floor(float(self.bias_gain[e]) * 10.0)) for e in range(experts)]
        for index in range(tokens):
            row = quantized[index]

            def sort_key(expert):
                fields = [-row[expert]]
                for name in self.tie_break_key:
                    if name == "expert_index":
                        fields.append(expert)
                    elif name == "running_load":
                        fields.append(running[expert])
                    elif name == "placement_rank":
                        fields.append(placement_rank[expert])
                    elif name == "bias_rank":
                        fields.append(bias_rank[expert])
                return tuple(fields)

            order = sorted(range(experts), key=sort_key)
            selected = order[:top_k]
            floor_value = min(row)
            shifts = [row[e] - floor_value + 1.0 for e in selected]
            total_shift = sum(shifts)
            weights = [r(shift / total_shift) for shift in shifts]
            for slot, expert in enumerate(selected):
                assignments.append((index, expert, slot, weights[slot]))
                demand[expert] += 1
                running[expert] += 1
                gate_mass[expert] += weights[slot]
            if top_k > 0:
                boundary = row[selected[top_k - 1]]
                contenders = [e for e in range(experts) if row[e] == boundary]
                if len(contenders) > 1:
                    chosen = sorted(set(contenders) & set(selected))
                    events.append(
                        {
                            "step": int(step_index),
                            "token_index": index,
                            "quantized_logit": r(boundary),
                            "contenders": contenders,
                            "selected": chosen,
                        }
                    )
        return {
            "tokens": int(tokens),
            "salts": salts,
            "quantized": quantized,
            "assignments": assignments,
            "demand": demand,
            "gate_mass": gate_mass,
            "tie_events": events,
        }


def gate_mass_total(config, routing, r):
    tokens = routing["tokens"]
    if tokens <= 0:
        return r(0.0)
    total = 0.0
    for value in routing["gate_mass"]:
        total += value / tokens
    return r(total * tokens)


def capacities_for(corpus, config, demand):
    experts = int(config["num_experts"])
    total = 0
    for value in demand:
        total += value
    ideal = float(config["capacity_factor"]) * total / experts
    bucket = int(config["capacity_bucket"])
    minimum = int(config["min_capacity"])
    out = []
    for value in demand:
        target = min(float(value), ideal)
        aligned = bucket * int(math.ceil(math.ceil(target) / bucket)) if bucket > 0 else 0
        out.append(max(minimum, aligned))
    return out, ideal


# --------------------------------------------------------------- simulation


class Simulation(object):
    def __init__(self, corpus, config, router, horizon=None):
        self.corpus = corpus
        self.config = config
        self.router = router
        self.horizon = int(config["steps"]) if horizon is None else min(int(horizon), int(config["steps"]))
        self.experts = int(config["num_experts"])
        self.world = int(config["ep_world_size"])
        self.per_rank = self.experts // self.world
        self.layers = [int(index) for index in config["moe_layer_indices"]]
        self.code_objects = [ROUTER_NAME] + ["moe_block_%d" % index for index in self.layers]
        self.tokens = schedule_tokens(corpus, config)[: self.horizon]
        self.expert_rank, self.rank_experts, self.groups = expert_placement(corpus, config)
        self.mark_dynamic = list(config["mark_dynamic"])
        self.promote = bool(config["dynamic_promotion_enabled"])
        self.threshold = int(config["promotion_threshold"])
        self.limit = int(config["cache_size_limit"])
        self.r_float = corpus.r_float
        self.r_time = corpus.r_time
        self._build_tables()
        self.caches = {}
        self.clock = {}
        for name in self.code_objects:
            for rank in range(self.world):
                self.caches[(name, rank)] = {}
                self.clock[(name, rank)] = 0
        self.dynamic = set()
        self.seen = {}
        self.steps = []

    def _build_tables(self):
        corpus = self.corpus
        self.cost_weight = {}
        self.kernel_us = {}
        for row in corpus.rows("expert_cost_table.csv"):
            index = int(row["expert_index"])
            self.cost_weight[index] = float(row["cost_weight"])
            self.kernel_us[index] = float(row["kernel_us_per_slot"])
        world = self.world
        self.alltoall_fixed = None
        self.alltoall_per_slot = None
        for row in corpus.rows("alltoall_cost_table.csv"):
            if int(row["ep_world_size"]) == world:
                self.alltoall_fixed = float(row["fixed_us"])
                self.alltoall_per_slot = float(row["per_slot_us"])
        if self.alltoall_fixed is None:
            raise PlanError(
                "table file 'alltoall_cost_table.csv' holds no row for ep_world_size=%r" % world
            )
        self.capture_us = None
        self.replay_discount = None
        for row in corpus.rows("capture_cost_table.csv"):
            if row["compile_mode"] == self.config["compile_mode"]:
                self.capture_us = float(row["capture_us"])
                self.replay_discount = float(row["replay_discount"])
        if self.capture_us is None:
            raise PlanError(
                "table file 'capture_cost_table.csv' holds no row for compile_mode=%r"
                % self.config["compile_mode"]
            )
        self.compile_cost = {}
        for row in corpus.rows("compile_cost_table.csv"):
            if row["compile_mode"] == self.config["compile_mode"]:
                self.compile_cost[int(row["static_dims"])] = float(row["compile_us"])
        self.break_catalog = []
        for row in corpus.rows("graph_break_catalog.csv"):
            self.break_catalog.append((row["cause"], float(row["bubble_us"])))
        self.break_catalog.sort(key=lambda item: item[0])
        self.break_bubble = dict(self.break_catalog)
        self.memory_slot = {}
        for row in corpus.rows("memory_slot_table.csv"):
            self.memory_slot[int(row["static_dims"])] = (
                int(row["entry_bytes"]),
                int(row["guard_bytes"]),
            )
        self.pool_blocks = []
        for row in corpus.rows("pool_block_table.csv"):
            self.pool_blocks.append((int(row["capacity_ceiling"]), int(row["block_bytes"])))
        self.pool_blocks.sort(key=lambda item: item[0])
        self.host_base = int(corpus.memory_gates["host_base_bytes"])
        self.host_ceiling = int(corpus.memory_gates["host_ceiling_bytes"])
        self.eager_multiplier = float(corpus.steptime_gates["eager_compute_multiplier"])
        self.sync_bubble = float(corpus.steptime_gates["sync_bubble_us"])
        self.payload_scale = float(corpus.topology["surrogate"]["payload_scale"])
        self.signal_weight = float(corpus.topology["surrogate"]["signal_weight"])
        self.base_loss = float(corpus.topology["surrogate"]["base_loss"])
        self.decay_rate = float(corpus.topology["surrogate"]["decay_rate"])

    # -- guard machinery -------------------------------------------------

    def _visit(self, code_object, rank, values):
        promoted = set()
        if self.promote:
            for name, value in values:
                if name in self.mark_dynamic:
                    continue
                bag = self.seen.setdefault((code_object, name), set())
                bag.add(value)
                if len(bag) >= self.threshold and (code_object, name) not in self.dynamic:
                    self.dynamic.add((code_object, name))
                    promoted.add((code_object, name))
        before_dynamic = self.dynamic - promoted
        before_parts = []
        after_parts = []
        for name, value in values:
            was_dynamic = name in self.mark_dynamic or (code_object, name) in before_dynamic
            now_dynamic = name in self.mark_dynamic or (code_object, name) in self.dynamic
            before_parts.append("dyn" if was_dynamic and value not in (0, 1) else str(value))
            after_parts.append("dyn" if now_dynamic and value not in (0, 1) else str(value))
        before = "|".join(before_parts)
        after = "|".join(after_parts)
        count_before = sum(1 for part in before_parts if part != "dyn")
        count_after = sum(1 for part in after_parts if part != "dyn")
        cache = self.caches[(code_object, rank)]
        clock_key = (code_object, rank)
        self.clock[clock_key] += 1
        now = self.clock[clock_key]
        evicted = None
        if after in cache:
            cache[after] = now
            recompiled = False
        else:
            recompiled = True
            if len(cache) >= self.limit:
                victim = None
                oldest = None
                for key in cache:
                    marker = cache[key]
                    if oldest is None or marker < oldest or (marker == oldest and key < victim):
                        oldest = marker
                        victim = key
                if victim is None:
                    raise PlanError(
                        "guard cache for %s@%d holds no entry to evict at limit %r"
                        % (code_object, rank, self.limit)
                    )
                del cache[victim]
                evicted = victim
            cache[after] = now
        return {
            "code_object": code_object,
            "rank": rank,
            "key": after,
            "count_before": count_before,
            "count_after": count_after,
            "recompiled": recompiled,
            "evicted": evicted,
        }

    # -- main walk ------------------------------------------------------

    def run(self):
        config = self.config
        params = [0.0] * self.experts
        eager_params = [0.0] * self.experts
        pool = 0
        carried = 0
        previous_tokens = None
        reset_steps = [int(s) for s in config["reset_steps"]]
        record_steps = []
        for offset, step_index in enumerate(range(1, self.horizon + 1)):
            step_index = offset + 1
            if step_index in reset_steps:
                for name in self.code_objects:
                    for rank in range(self.world):
                        self.caches[(name, rank)] = {}
                        self.clock[(name, rank)] = 0
                pool = 0
            routing = self.router.step(config, step_index, self.tokens[offset], self.expert_rank)
            tokens = routing["tokens"]
            capacity, ideal = capacities_for(self.corpus, config, routing["demand"])
            rank_bucket = {}
            for rank in range(self.world):
                rank_bucket[rank] = max(capacity[e] for e in self.rank_experts[rank])
            alltoall_bucket = max(rank_bucket.values())
            spread = max(rank_bucket.values()) - min(rank_bucket.values())
            payload_slots = alltoall_bucket * self.world * self.per_rank
            # dispatch
            counters = [0] * self.experts
            accepted = [0] * self.experts
            dropped = []
            accepted_slots = {e: [] for e in range(self.experts)}
            for (token, expert, slot, weight) in routing["assignments"]:
                index = counters[expert]
                counters[expert] = index + 1
                if index >= capacity[expert]:
                    dropped.append((token, expert, slot, weight))
                else:
                    accepted[expert] += 1
                    accepted_slots[expert].append((token, weight))
            padded = 0
            for expert in range(self.experts):
                padded += capacity[expert] - accepted[expert]
            # breaks
            causes = []
            bucket = int(config["capacity_bucket"])
            if any(value % bucket != 0 for value in capacity):
                causes.append("data_dependent_capacity")
            if (
                previous_tokens is not None
                and tokens != previous_tokens
                and "tokens" not in self.mark_dynamic
            ):
                causes.append("dynamic_token_count")
            if dropped:
                causes.append("token_drop_mask")
            if spread != 0:
                causes.append("unbalanced_expert_slice")
            if any(value == 0 for value in routing["demand"]):
                causes.append("zero_token_expert")
            causes.sort()
            # guard visits
            visits = []
            for name in self.code_objects:
                for rank in range(self.world):
                    if name == ROUTER_NAME:
                        values = [("tokens", tokens)]
                    else:
                        values = [("capacity", rank_bucket[rank]), ("local_experts", self.per_rank)]
                    visits.append(self._visit(name, rank, values))
            recompiles = [visit for visit in visits if visit["recompiled"]]
            # capture
            capture_attempts = 0
            captures = 0
            failure_causes = {name: 0 for name in CAPTURE_CAUSES}
            for visit in visits:
                if visit["code_object"] == ROUTER_NAME:
                    continue
                capture_attempts += 1
                if config["compile_mode"] != "reduce-overhead":
                    failure_causes[CAUSE_CAPTURE_DISABLED] += 1
                elif causes:
                    failure_causes[CAUSE_CAPTURE_STREAM] += 1
                elif "dyn" in visit["key"].split("|"):
                    failure_causes[CAUSE_CAPTURE_DYNAMIC] += 1
                else:
                    captures += 1
            if captures > 0:
                for rank in range(self.world):
                    block = None
                    for ceiling, size in self.pool_blocks:
                        if ceiling >= rank_bucket[rank]:
                            block = size
                            break
                    if block is None:
                        raise PlanError(
                            "table file 'pool_block_table.csv' holds no row covering rank_bucket=%r"
                            % rank_bucket[rank]
                        )
                    pool += block
            reported_peak = max(carried, pool)
            # host memory
            entries = 0
            closures = 0
            for name in self.code_objects:
                for rank in range(self.world):
                    cache = self.caches[(name, rank)]
                    entries += len(cache)
                    for key in cache:
                        closures += sum(1 for part in key.split("|") if part != "dyn")
            slot = self.memory_slot.get(len(self.mark_dynamic))
            if slot is None:
                raise PlanError(
                    "table file 'memory_slot_table.csv' holds no row for %d marked dimensions"
                    % len(self.mark_dynamic)
                )
            entry_bytes, guard_bytes = slot
            host_bytes = self.host_base + entries * entry_bytes + closures * guard_bytes + reported_peak
            headroom = self.host_ceiling - host_bytes
            # numeric walk
            compiled = self._numeric_walk(routing, capacity, accepted_slots, params, False)
            eager = self._numeric_walk(routing, capacity, accepted_slots, eager_params, True)
            # aux loss
            aux = self._aux_loss(routing)
            loss = self._loss(step_index, aux, compiled["signal"])
            eager_loss = self._loss(step_index, aux, eager["signal"])
            # step time
            compute_base = 0.0
            for rank in range(self.world):
                total = 0.0
                for expert in self.rank_experts[rank]:
                    total += self.kernel_us[expert] * rank_bucket[rank]
                if total > compute_base:
                    compute_base = total
            discount = self.replay_discount if captures > 0 else 1.0
            compute_us = self.r_time(compute_base * discount)
            alltoall_us = self.r_time(
                self.alltoall_fixed + self.alltoall_per_slot * alltoall_bucket * self.world
            )
            compile_us = 0.0
            for visit in recompiles:
                dims = visit["count_before"]
                if dims not in self.compile_cost:
                    raise PlanError(
                        "table file 'compile_cost_table.csv' holds no row for static_dims=%r" % dims
                    )
                compile_us += self.compile_cost[dims]
            compile_us = self.r_time(compile_us)
            capture_cost = self.r_time(self.capture_us * captures)
            bubble = 0.0
            for cause in causes:
                bubble += self.break_bubble[cause] * len(self.layers)
            if recompiles:
                bubble += self.sync_bubble
            bubble_us = self.r_time(bubble)
            step_us = self.r_time(compile_us + capture_cost + compute_us + alltoall_us + bubble_us)
            eager_compute = self.r_time(compute_base * self.eager_multiplier)
            eager_step_us = self.r_time(eager_compute + alltoall_us)
            record_steps.append(
                {
                    "step": step_index,
                    "tokens": tokens,
                    "salts": routing["salts"],
                    "demand": routing["demand"],
                    "gate_mass": routing["gate_mass"],
                    "gate_mass_total": gate_mass_total(config, routing, self.r_float),
                    "total_assignments": len(routing["assignments"]),
                    "tie_events": routing["tie_events"],
                    "capacity": capacity,
                    "ideal": ideal,
                    "rank_bucket": rank_bucket,
                    "alltoall_bucket": alltoall_bucket,
                    "payload_slots": payload_slots,
                    "spread": spread,
                    "accepted": accepted,
                    "dropped": dropped,
                    "padded": padded,
                    "causes": causes,
                    "visits": visits,
                    "recompiles": recompiles,
                    "capture_attempts": capture_attempts,
                    "captures": captures,
                    "failure_causes": failure_causes,
                    "pool": pool,
                    "pool_peak": reported_peak,
                    "cache_entries": entries,
                    "guard_closures": closures,
                    "host_bytes": host_bytes,
                    "headroom": headroom,
                    "compiled": compiled,
                    "eager": eager,
                    "aux": aux,
                    "loss": loss,
                    "eager_loss": eager_loss,
                    "compute_base": compute_base,
                    "compute_us": compute_us,
                    "alltoall_us": alltoall_us,
                    "compile_us": compile_us,
                    "capture_us": capture_cost,
                    "bubble_us": bubble_us,
                    "step_us": step_us,
                    "eager_step_us": eager_step_us,
                }
            )
            params = compiled["params"]
            eager_params = eager["params"]
            carried = pool
            previous_tokens = tokens
        self.steps = record_steps
        return record_steps

    def _aux_loss(self, routing):
        config = self.config
        experts = self.experts
        total = 0
        for value in routing["demand"]:
            total += value
        tokens = routing["tokens"]
        r = self.r_float
        running = 0.0
        for expert in range(experts):
            fraction = r(routing["demand"][expert] / total) if total > 0 else 0.0
            probability = r(routing["gate_mass"][expert] / tokens) if tokens > 0 else 0.0
            running = r(running + r(fraction * probability))
        running = r(running)
        return r(float(config["aux_loss_weight"]) * experts * running)

    def _loss(self, step_index, aux, signal):
        r = self.r_float
        base = r(self.base_loss / (1.0 + self.decay_rate * step_index))
        term = r(self.signal_weight * signal)
        return r(base + aux + term)

    def _numeric_walk(self, routing, capacity, accepted_slots, params, eager):
        experts = self.experts
        scale = self.payload_scale
        outputs = [0.0] * experts
        partials = [0.0] * experts
        if eager:
            for expert in range(experts):
                slots = accepted_slots[expert]
                accumulator = 0.0
                for (token, weight) in slots:
                    feature = routing["salts"][token] * 2.0 - 1.0
                    accumulator += weight * (1.0 - feature * 0.25)
                if slots:
                    outputs[expert] = accumulator / len(slots)
            signal = 0.0
            for expert in range(experts):
                contribution = outputs[expert] * self.cost_weight[expert]
                partials[expert] = contribution
                signal += contribution
        else:
            for expert in range(experts):
                slots = accepted_slots[expert]
                accumulator = 0.0
                for (token, weight) in slots:
                    feature = bf16(routing["salts"][token] * 2.0 - 1.0)
                    stored_weight = bf16(weight)
                    raw = f32(stored_weight * (1.0 - feature * 0.25))
                    payload = fp8_cast(f32(raw * scale))
                    accumulator = f32(accumulator + f32(payload / scale))
                if slots:
                    outputs[expert] = bf16(f32(accumulator / len(slots)))
                else:
                    outputs[expert] = 0.0
            signal = 0.0
            for expert in range(experts):
                contribution = f32(outputs[expert] * self.cost_weight[expert])
                partials[expert] = contribution
                signal = f32(signal + contribution)
        signal_weight = self.signal_weight
        gradients = []
        scaled = []
        for expert in range(experts):
            gradients.append(outputs[expert] * signal_weight * self.cost_weight[expert])
            scaled.append(gradients[expert] * float(self.config["loss_scale"]))
        if eager:
            norm_sq = 0.0
            for expert in range(experts):
                norm_sq += scaled[expert] * scaled[expert]
            norm = math.sqrt(norm_sq)
        else:
            norm_sq = 0.0
            for expert in range(experts):
                norm_sq = f32(norm_sq + f32(scaled[expert] * scaled[expert]))
            norm = f32(math.sqrt(norm_sq))
        reference = float(self.config["clip_threshold"]) * float(self.config["loss_scale"])
        if not eager:
            reference = f32(reference)
        factor = 1.0 if norm <= reference else (reference / norm if eager else f32(reference / norm))
        clipped = []
        unscaled = []
        new_params = []
        loss_scale = float(self.config["loss_scale"])
        learning_rate = float(self.config["learning_rate"])
        for expert in range(experts):
            value = scaled[expert] * factor if eager else f32(scaled[expert] * factor)
            clipped.append(value)
            unscaled.append(value / loss_scale if eager else f32(value / loss_scale))
            update = learning_rate * unscaled[expert]
            if eager:
                new_params.append(params[expert] - update)
            else:
                new_params.append(bf16(f32(params[expert] - f32(update))))
        return {
            "outputs": outputs,
            "partials": partials,
            "signal": signal,
            "gradients": gradients,
            "scaled": scaled,
            "norm": norm,
            "reference": reference,
            "factor": factor,
            "clipped": clipped,
            "unscaled": unscaled,
            "params": new_params,
        }


def simulate(corpus, config, router, horizon=None):
    sim = Simulation(corpus, config, router, horizon)
    sim.run()
    return sim


# --------------------------------------------------------------- aggregates


def gated_steps(sim):
    warmup = int(sim.config["warmup_bound"])
    return [step for step in sim.steps if step["step"] > warmup]


def tail_figures(sim):
    gated = gated_steps(sim)
    compiled = sum(step["step_us"] for step in gated)
    eager = sum(step["eager_step_us"] for step in gated)
    r = sim.r_time
    compiled = r(compiled)
    eager = r(eager)
    if compiled > 0:
        speedup = r(eager / compiled)
    else:
        speedup = r(0.0)
    return compiled, eager, speedup


def recompile_summary(sim):
    warmup = int(sim.config["warmup_bound"])
    events = []
    by_step = []
    after = 0
    evictions = 0
    for step in sim.steps:
        for visit in step["recompiles"]:
            events.append(
                {
                    "step": step["step"],
                    "code_object": visit["code_object"],
                    "rank": visit["rank"],
                    "guard_key": visit["key"],
                    "guard_delta": visit["count_after"] - visit["count_before"],
                    "evicted_key": visit["evicted"],
                }
            )
        by_step.append({"step": step["step"], "count": len(step["recompiles"])})
        if step["step"] > warmup:
            after += len(step["recompiles"])
        evictions += sum(1 for visit in step["recompiles"] if visit["evicted"] is not None)
    first_over = None
    budget = int(sim.corpus.steptime_gates["recompile_budget"])
    running = 0
    for step in sim.steps:
        if step["step"] > warmup:
            running += len(step["recompiles"])
            if running > budget and first_over is None:
                first_over = step["step"]
    return events, by_step, after, evictions, first_over


def min_capacity_seen(sim):
    values = []
    for step in sim.steps:
        values.extend(step["capacity"])
    return min(values) if values else int(sim.config["min_capacity"])


def drop_figures(sim):
    dropped = 0
    mass = 0.0
    total = 0
    steps_with = 0
    r = sim.r_float
    for step in sim.steps:
        step_dropped = len(step["dropped"])
        dropped += step_dropped
        total += step["total_assignments"]
        for (token, expert, slot, weight) in step["dropped"]:
            mass += weight
        if step_dropped:
            steps_with += 1
    rate = r(dropped / total) if total > 0 else r(0.0)
    return dropped, r(mass), total, rate, steps_with


def headroom_figures(sim):
    values = [step["headroom"] for step in sim.steps]
    peak = max(step["host_bytes"] for step in sim.steps) if sim.steps else sim.host_base
    return (min(values) if values else sim.host_ceiling), peak


def guard_index(sim):
    keys_by_slot = {}
    slot_keys = {}
    for step in sim.steps:
        for visit in step["visits"]:
            slot = "%s@%d" % (visit["code_object"], visit["rank"])
            slot_keys.setdefault(slot, set()).add(visit["key"])
    for slot in sorted(slot_keys):
        keys_by_slot[slot] = sorted(slot_keys[slot])
    distinct = set()
    for slot in slot_keys:
        distinct.update(slot_keys[slot])
    return {
        "run_id": sim.config["run_id"],
        "keys_by_slot": keys_by_slot,
        "distinct_key_count": len(distinct),
        "specialized_zero_one_keys": len(
            [
                key
                for key in distinct
                if any(part in ("0", "1") for part in key.split("|"))
            ]
        ),
        "dynamic_dims_final": sorted("%s.%s" % (name, dim) for (name, dim) in sim.dynamic),
    }


def warmup_profile_record(sim):
    warmup = int(sim.config["warmup_bound"])
    window = [step for step in sim.steps if step["step"] <= warmup]
    tokens = sorted({step["tokens"] for step in window})
    buckets = set()
    for step in window:
        buckets.update(step["rank_bucket"].values())
    local = sorted({sim.per_rank})
    threshold = int(sim.config["promotion_threshold"])
    dims = []
    if len(tokens) >= threshold:
        dims.append("tokens")
    if len(local) >= threshold:
        dims.append("local_experts")
    dims.sort()
    return {
        "run_id": sim.config["run_id"],
        "warmup_bound": warmup,
        "window_steps": len(window),
        "distinct_token_values": tokens,
        "distinct_capacity_values": sorted(buckets),
        "distinct_local_expert_values": local,
        "promotion_threshold": threshold,
        "dims_requiring_dynamic": dims,
        "warmup_recompiles": sum(len(step["recompiles"]) for step in window),
    }


def relative_deviation(compiled, baseline, r):
    if baseline == 0:
        return r(0.0)
    return r(abs(compiled - baseline) / abs(baseline))


# --------------------------------------------------------------- record builders


def route_plan_record(sim):
    steps = []
    events = []
    total = 0
    for step in sim.steps:
        steps.append(
            {
                "step": step["step"],
                "token_count": step["tokens"],
                "demand": list(step["demand"]),
                "gate_mass_total": step["gate_mass_total"],
                "tie_break_count": len(step["tie_events"]),
            }
        )
        events.extend(step["tie_events"])
        total += step["total_assignments"]
    return {
        "run_id": sim.config["run_id"],
        "top_k": int(sim.config["top_k"]),
        "tie_break_key": list(sim.router.tie_break_key),
        "steps": steps,
        "tie_break_events": events,
        "total_assignments": total,
    }


def capacity_plan_record(sim):
    steps = []
    values = []
    for step in sim.steps:
        steps.append(
            {
                "step": step["step"],
                "capacity": list(step["capacity"]),
                "unaligned_experts": sum(
                    1 for value in step["capacity"] if value % int(sim.config["capacity_bucket"]) != 0
                ),
            }
        )
        values.extend(step["capacity"])
    return {
        "run_id": sim.config["run_id"],
        "capacity_factor": sim.config["capacity_factor"],
        "capacity_bucket": int(sim.config["capacity_bucket"]),
        "min_capacity": int(sim.config["min_capacity"]),
        "steps": steps,
        "min_capacity_seen": min(values) if values else int(sim.config["min_capacity"]),
        "max_capacity_seen": max(values) if values else int(sim.config["min_capacity"]),
        "distinct_capacity_values": len(set(values)),
    }


def mesh_plan_record(sim):
    vectors = {tuple(step["capacity"]) for step in sim.steps}
    return {
        "run_id": sim.config["run_id"],
        "ep_world_size": sim.world,
        "expert_rank": list(sim.expert_rank),
        "rank_experts": {
            str(rank): list(sim.rank_experts[rank]) for rank in sorted(sim.rank_experts)
        },
        "placement_groups": list(sim.groups),
        "rank_bucket_by_step": [
            {
                "step": step["step"],
                "rank_bucket": {
                    str(rank): step["rank_bucket"][rank] for rank in sorted(step["rank_bucket"])
                },
            }
            for step in sim.steps
        ],
        "expert_shape_matrix": len(vectors) * len(sim.layers),
    }


def dispatch_ledger_record(sim):
    steps = []
    total_accepted = 0
    total_padded = 0
    for step in sim.steps:
        accepted = sum(step["accepted"])
        steps.append(
            {"step": step["step"], "accepted_count": accepted, "padded_slots": step["padded"]}
        )
        total_accepted += accepted
        total_padded += step["padded"]
    return {
        "run_id": sim.config["run_id"],
        "steps": steps,
        "total_accepted": total_accepted,
        "total_padded_slots": total_padded,
    }


def drop_ledger_record(sim):
    dropped, mass, total, rate, steps_with = drop_figures(sim)
    return {
        "run_id": sim.config["run_id"],
        "steps": [
            {
                "step": step["step"],
                "dropped_tokens": len(step["dropped"]),
                "dropped_token_mass": sim.r_float(
                    sum(weight for (token, expert, slot, weight) in step["dropped"])
                ),
            }
            for step in sim.steps
        ],
        "dropped_tokens": dropped,
        "dropped_token_mass": mass,
        "drop_rate": rate,
        "steps_with_drops": steps_with,
    }


def alltoall_ledger_record(sim):
    steps = []
    uniform = 0
    total = 0
    for step in sim.steps:
        steps.append(
            {
                "step": step["step"],
                "alltoall_bucket": step["alltoall_bucket"],
                "payload_slots": step["payload_slots"],
                "rank_bucket_spread": step["spread"],
            }
        )
        if step["spread"] == 0:
            uniform += 1
        total += step["payload_slots"]
    return {
        "run_id": sim.config["run_id"],
        "ep_world_size": sim.world,
        "steps": steps,
        "uniform_steps": uniform,
        "total_payload_slots": total,
    }


def recompile_report_record(sim):
    events, by_step, after, evictions, first_over = recompile_summary(sim)
    return {
        "run_id": sim.config["run_id"],
        "warmup_bound": int(sim.config["warmup_bound"]),
        "recompile_events": events,
        "total_recompiles": len(events),
        "recompiles_after_warmup": after,
        "first_step_over_budget": first_over,
        "evictions": evictions,
        "recompiles_by_step": by_step,
    }


def graph_break_ledger_record(sim):
    cause_order = [name for (name, bubble) in sim.break_catalog]
    counts = {name: 0 for name in cause_order}
    steps = []
    clean = 0
    total = 0
    for step in sim.steps:
        steps.append({"step": step["step"], "causes": list(step["causes"])})
        for cause in step["causes"]:
            counts[cause] += 1
            total += 1
        if not step["causes"]:
            clean += 1
    return {
        "run_id": sim.config["run_id"],
        "cause_order": cause_order,
        "per_cause_counts": counts,
        "steps": steps,
        "total_breaks": total,
        "clean_steps": clean,
    }


def cudagraph_report_record(sim):
    causes = {name: 0 for name in CAPTURE_CAUSES}
    steps = []
    attempts = 0
    captures = 0
    for step in sim.steps:
        steps.append(
            {
                "step": step["step"],
                "captured": step["captures"],
                "pool_bytes": step["pool"],
                "pool_peak_bytes": step["pool_peak"],
            }
        )
        attempts += step["capture_attempts"]
        captures += step["captures"]
        for name in CAPTURE_CAUSES:
            causes[name] += step["failure_causes"][name]
    return {
        "run_id": sim.config["run_id"],
        "compile_mode": sim.config["compile_mode"],
        "capture_attempts": attempts,
        "captures": captures,
        "failure_causes": causes,
        "steps": steps,
        "final_pool_peak_bytes": sim.steps[-1]["pool_peak"] if sim.steps else 0,
        "reset_steps": [int(value) for value in sim.config["reset_steps"]],
    }


def host_memory_report_record(sim):
    minimum, peak = headroom_figures(sim)
    return {
        "run_id": sim.config["run_id"],
        "host_ceiling_bytes": sim.host_ceiling,
        "steps": [
            {
                "step": step["step"],
                "host_bytes": step["host_bytes"],
                "host_headroom_bytes": step["headroom"],
                "cache_entries": step["cache_entries"],
                "guard_closures": step["guard_closures"],
            }
            for step in sim.steps
        ],
        "min_host_headroom_bytes": minimum,
        "peak_host_bytes": peak,
        "steps_over_ceiling": sum(1 for step in sim.steps if step["headroom"] < 0),
        "memory_gate_met": minimum >= 0,
    }


def steptime_report_record(sim):
    compiled, eager, speedup = tail_figures(sim)
    gated = gated_steps(sim)
    total_compile = sum(step["compile_us"] for step in sim.steps)
    amortized = sim.r_time(total_compile / len(gated)) if gated else sim.r_time(0.0)
    minimum = float(sim.corpus.steptime_gates["min_speedup"])
    return {
        "run_id": sim.config["run_id"],
        "steps": [
            {
                "step": step["step"],
                "step_us": step["step_us"],
                "compute_us": step["compute_us"],
                "alltoall_us": step["alltoall_us"],
                "compile_us": step["compile_us"],
                "capture_us": step["capture_us"],
                "bubble_us": step["bubble_us"],
                "eager_step_us": step["eager_step_us"],
            }
            for step in sim.steps
        ],
        "gated_step_range": [gated[0]["step"], gated[-1]["step"]] if gated else [],
        "compiled_tail_us": compiled,
        "eager_tail_us": eager,
        "speedup": speedup,
        "min_speedup": minimum,
        "speedup_gate_met": speedup >= minimum,
        "amortized_compile_us": amortized,
    }


def aux_loss_record(sim):
    steps = []
    empty_steps = 0
    dispersions = []
    for step in sim.steps:
        demand = step["demand"]
        total = sum(demand)
        tokens = step["tokens"]
        r = sim.r_float
        fractions = [
            (r(demand[e] / total) if total > 0 else 0.0) for e in range(sim.experts)
        ]
        live = [fractions[e] for e in range(sim.experts) if demand[e] > 0]
        if len(live) == 0:
            dispersion = None
        elif len(live) == 1:
            dispersion = r(0.0)
        else:
            dispersion = r(max(live) - min(live))
        utilization = []
        for e in range(sim.experts):
            if demand[e] == 0:
                utilization.append(None)
            else:
                utilization.append(
                    r((step["accepted"][e] / demand[e]) * fractions[e])
                )
        empty = sum(1 for value in demand if value == 0)
        if empty:
            empty_steps += 1
        if dispersion is not None:
            dispersions.append(dispersion)
        steps.append(
            {
                "step": step["step"],
                "aux_loss": step["aux"],
                "expert_utilization": utilization,
                "load_dispersion": dispersion,
                "empty_experts": empty,
            }
        )
    mean = (
        sim.r_float(sum(dispersions) / len(dispersions)) if dispersions else None
    )
    return {
        "run_id": sim.config["run_id"],
        "aux_loss_weight": sim.config["aux_loss_weight"],
        "steps": steps,
        "aux_loss_total": sim.r_float(sum(step["aux"] for step in sim.steps)),
        "steps_with_empty_experts": empty_steps,
        "mean_load_dispersion": mean,
    }


def loss_curve_record(sim):
    losses = [step["loss"] for step in sim.steps]
    eager = [step["eager_loss"] for step in sim.steps]
    opening = losses[0] if losses else sim.r_float(0.0)
    return {
        "run_id": sim.config["run_id"],
        "steps": [
            {
                "step": step["step"],
                "loss": step["loss"],
                "eager_loss": step["eager_loss"],
                "signed_gap": sim.r_float(step["loss"] - step["eager_loss"]),
            }
            for step in sim.steps
        ],
        "closing_loss": losses[-1] if losses else sim.r_float(0.0),
        "opening_loss": opening,
        "minimum_loss": min(losses) if losses else sim.r_float(0.0),
        "steps_above_opening": sum(1 for value in losses if value > opening),
    }


def gradient_ledger_record(sim):
    folded = 0.0
    for step in sim.steps:
        folded += step["compiled"]["signal"]
    return {
        "run_id": sim.config["run_id"],
        "steps": [
            {
                "step": step["step"],
                "expert_outputs": [sim.r_float(value) for value in step["compiled"]["outputs"]],
                "expert_partials": [sim.r_float(value) for value in step["compiled"]["partials"]],
                "step_signal": sim.r_float(step["compiled"]["signal"]),
                "gradients": [sim.r_float(value) for value in step["compiled"]["gradients"]],
            }
            for step in sim.steps
        ],
        "folded_signal": sim.r_float(folded),
        "final_params": [
            sim.r_float(value) for value in (sim.steps[-1]["compiled"]["params"] if sim.steps else [])
        ],
        "accumulation_order": list(ACCUMULATION_ORDER),
    }


def optimizer_trace_record(sim):
    clipped_steps = []
    for step in sim.steps:
        if step["compiled"]["norm"] > step["compiled"]["reference"]:
            clipped_steps.append(step["step"])
    return {
        "run_id": sim.config["run_id"],
        "loss_scale": sim.config["loss_scale"],
        "clip_threshold": sim.config["clip_threshold"],
        "learning_rate": sim.config["learning_rate"],
        "steps": [
            {
                "step": step["step"],
                "scaled_norm": sim.r_float(step["compiled"]["norm"]),
                "clip_reference": sim.r_float(step["compiled"]["reference"]),
                "clip_factor": sim.r_float(step["compiled"]["factor"]),
                "clipped": step["compiled"]["norm"] > step["compiled"]["reference"],
            }
            for step in sim.steps
        ],
        "clipped_steps": clipped_steps,
        "clipped_step_count": len(clipped_steps),
    }


def convergence_record(sim):
    losses = [step["loss"] for step in sim.steps]
    baseline = [step["eager_loss"] for step in sim.steps]
    window = int(sim.corpus.gates["slope_window"])
    if len(losses) >= window and window > 1:
        slope = sim.r_float((losses[-1] - losses[-window]) / (window - 1))
    elif losses:
        slope = sim.r_float(losses[-1] - losses[0])
    else:
        slope = sim.r_float(0.0)
    closing = losses[-1] if losses else sim.r_float(0.0)
    base_closing = baseline[-1] if baseline else sim.r_float(0.0)
    deviation = relative_deviation(closing, base_closing, sim.r_float)
    band = float(sim.corpus.gates["parity_band"])
    parity = deviation <= band
    target = float(sim.corpus.gates["target_loss"])
    verdict = (
        "met"
        if parity and slope <= float(sim.corpus.gates["max_slope"]) and closing <= target
        else "unmet"
    )
    return {
        "run_id": sim.config["run_id"],
        "slope_window": window,
        "windowed_slope": slope,
        "closing_loss": closing,
        "baseline_closing_loss": base_closing,
        "relative_deviation": deviation,
        "parity_band": band,
        "parity_holds": parity,
        "target_loss": target,
        "verdict": verdict,
    }


# --------------------------------------------------------------- sealed evidence


def baseline_parity_record(sim):
    steps = []
    outside = []
    worst = None
    worst_step = None
    band = float(sim.corpus.gates["parity_band"])
    for step in sim.steps:
        deviation = relative_deviation(step["loss"], step["eager_loss"], sim.r_float)
        steps.append({"step": step["step"], "relative_deviation": deviation})
        if deviation > band:
            outside.append(step["step"])
        if deviation != 0.0 and (worst is None or deviation > worst):
            worst = deviation
            worst_step = step["step"]
    peak = worst if worst is not None else sim.r_float(0.0)
    return {
        "run_id": sim.config["run_id"],
        "steps": steps,
        "max_relative_deviation": peak,
        "max_deviation_step": worst_step,
        "parity_band": band,
        "parity_holds": peak <= band,
        "steps_outside_band": outside,
    }


def sealed_configs(corpus):
    names = []
    tie = corpus.json_table("sealed_tiebreak_digests.json")
    precedence = corpus.json_table("sealed_precedence_digests.json")
    for name in tie.get("digests", {}):
        if name not in precedence.get("digests", {}):
            raise PlanError(
                "table file 'sealed_precedence_digests.json' holds no entry for the named configuration %r"
                % name
            )
        names.append(name)
    names.sort()
    return names


def sealed_config_for(corpus, name):
    if name == "calibration":
        return corpus.json_table("calibration_config.json")
    probes = corpus.json_table("probe_configurations.json")
    if name in probes:
        return probes[name]
    raise PlanError(
        "the sealed configuration %r is neither calibration_config.json nor an entry of "
        "'probe_configurations.json'" % name
    )


def candidate_label(factor, bucket, marks, mode):
    joined = "+".join(marks) if marks else "none"
    return "cf=%s|bucket=%d|dynamic=%s|mode=%s" % (repr(float(factor)), int(bucket), joined, mode)


def _parity_evidence(corpus, order):
    """Return true when the order reproduces the shipped calibration parity rows.

    The digests over the named configurations leave the field order of
    `running_load` and `expert_index` undetermined; the shipped parity table
    records the per step accepted counts, capacities and losses of the sample
    configuration and settles it.
    """
    rows = corpus.tables.get("calibration_parity.jsonl")
    baseline = corpus.tables.get("eager_baseline.json")
    if not isinstance(rows, list) or not rows or not isinstance(baseline, dict):
        return False
    run_id = baseline.get("run_id")
    config = None
    for name in sorted(corpus.tables):
        if not name.endswith(".json"):
            continue
        value = corpus.tables[name]
        if isinstance(value, dict) and value.get("run_id") == run_id and "num_experts" in value:
            config = value
            break
    if config is None:
        return False
    horizon = max(int(row["step"]) for row in rows)
    try:
        validate_config(config, "eager_baseline.json")
        check_mesh(corpus, config)
        router = Router(corpus, config, order)
        sim = Simulation(corpus, config, router, horizon)
        sim.run()
    except PlanError:
        return False
    by_step = {int(row["step"]): row for row in rows}
    for step in sim.steps:
        row = by_step.get(step["step"])
        if row is None:
            continue
        if list(step["accepted"]) != [int(value) for value in row["accepted_count"]]:
            return False
        if list(step["capacity"]) != [int(value) for value in row["capacity"]]:
            return False
        if step["loss"] != float(row["compiled_loss"]):
            return False
        if step["eager_loss"] != float(row["eager_loss"]):
            return False
    return True


def resolve_tie_break(corpus):
    names = sealed_configs(corpus)
    orders = []
    for order in itertools.permutations(TIE_BREAK_FIELDS):
        orders.append(tuple(order))
    orders.sort()
    matches = []
    for order in orders:
        ok = True
        for name in names:
            config = validate_config(sealed_config_for(corpus, name), name)
            check_mesh(corpus, config)
            info = corpus.json_table("sealed_tiebreak_digests.json")["digests"][name]
            horizon = int(info["steps"])
            router = Router(corpus, config, order)
            sim = Simulation(corpus, config, router, horizon)
            sim.run()
            events = []
            for step in sim.steps:
                events.extend(step["tie_events"])
            if canonical_digest(events) != info["digest"]:
                ok = False
                break
        if ok:
            matches.append(order)
    if not matches:
        raise PlanError(
            "no candidate tie break key reproduces the digests of 'sealed_tiebreak_digests.json'"
        )
    if len(matches) == 1:
        chosen = matches[0]
    else:
        chosen = None
        for order in matches:
            if _parity_evidence(corpus, order):
                chosen = order
                break
        if chosen is None:
            chosen = matches[0]
    return {
        "tie_break_key": list(chosen),
        "tie_break_matches": len(matches),
        "tie_break_candidates_enumerated": len(orders),
    }


def sweep_space(corpus):
    axes = corpus.json_table("capacity_candidates.json")
    for key in ("capacity_factor", "capacity_bucket", "compile_mode", "mark_dynamic"):
        if key not in axes:
            raise PlanError(
                "table file 'capacity_candidates.json' is missing the axis '%s'" % key
            )
    space = []
    for factor in axes["capacity_factor"]:
        for bucket in axes["capacity_bucket"]:
            for mode in axes["compile_mode"]:
                for marks in axes["mark_dynamic"]:
                    space.append(
                        {
                            "capacity_factor": factor,
                            "capacity_bucket": bucket,
                            "compile_mode": mode,
                            "mark_dynamic": list(marks),
                        }
                    )
    return space, axes


def evaluate_candidate(corpus, config, router, horizon):
    sim = Simulation(corpus, config, router, horizon)
    sim.run()
    return candidate_figures(sim)


def candidate_figures(sim):
    _, _, speedup = tail_figures(sim)
    events, by_step, after, evictions, first_over = recompile_summary(sim)
    dropped, mass, total, rate, steps_with = drop_figures(sim)
    minimum, peak = headroom_figures(sim)
    losses = [step["loss"] for step in sim.steps]
    baseline = [step["eager_loss"] for step in sim.steps]
    closing = losses[-1] if losses else sim.r_float(0.0)
    base_closing = baseline[-1] if baseline else sim.r_float(0.0)
    deviation = relative_deviation(closing, base_closing, sim.r_float)
    return {
        "sim": sim,
        "speedup": speedup,
        "recompiles_after_warmup": after,
        "min_headroom": minimum,
        "drop_rate": rate,
        "relative_deviation": deviation,
        "min_capacity": min_capacity_seen(sim),
        "closing_loss": closing,
        "baseline_closing_loss": base_closing,
    }


def candidate_violations(corpus, figures):
    gates = corpus.steptime_gates
    convergence = corpus.gates
    memory = corpus.memory_gates
    violations = []
    if figures["sim"].config["compile_mode"] == "eager":
        violations.append("eager_mode_forbidden")
    if figures["recompiles_after_warmup"] > int(gates["recompile_budget"]):
        violations.append("recompile_budget_exceeded")
    if figures["speedup"] < float(gates["min_speedup"]):
        violations.append("speedup_gate_unmet")
    if figures["min_headroom"] < 0:
        violations.append("memory_ceiling_exceeded")
    if figures["drop_rate"] > float(convergence["max_drop_rate"]):
        violations.append("drop_tolerance_exceeded")
    if figures["relative_deviation"] > float(convergence["settlement_parity_band"]):
        violations.append("convergence_band_unmet")
    if figures["min_capacity"] < int(memory["capacity_floor"]):
        violations.append("capacity_below_minimum")
    return violations


def precedence_candidates():
    rest = [name for name in REJECTION_CAUSES if name != "eager_mode_forbidden"]
    orders = []
    for order in itertools.permutations(rest):
        candidate = ["eager_mode_forbidden"] + list(order)
        if candidate.index("capacity_below_minimum") < candidate.index("drop_tolerance_exceeded"):
            if candidate.index("recompile_budget_exceeded") < candidate.index("speedup_gate_unmet"):
                orders.append(tuple(candidate))
    orders.sort()
    return orders


def resolve_precedence(corpus, tie_break_key):
    names = sealed_configs(corpus)
    space, axes = sweep_space(corpus)
    probe = int(axes.get("probe_steps", 0))
    if probe < 1:
        raise PlanError(
            "table file 'capacity_candidates.json' carries the unusable probe_steps=%r" % axes.get("probe_steps")
        )
    prepared = []
    for name in names:
        config = validate_config(sealed_config_for(corpus, name), name)
        check_mesh(corpus, config)
        router = Router(corpus, config, tie_break_key)
        base = Simulation(corpus, config, router, int(config["steps"]))
        base.run()
        required = list(warmup_profile_record(base)["dims_requiring_dynamic"])
        results = []
        for candidate in space:
            missing = [dim for dim in required if dim not in candidate["mark_dynamic"]]
            if missing:
                continue
            trial = dict(config)
            trial.update(candidate)
            trial["reset_steps"] = [
                int(s) for s in trial["reset_steps"] if int(s) <= probe
            ]
            figures = evaluate_candidate(corpus, trial, router, probe)
            results.append(candidate_violations(corpus, figures))
        prepared.append((name, results))
    digests = corpus.json_table("sealed_precedence_digests.json")["digests"]
    matches = []
    for order in precedence_candidates():
        ok = True
        for name, results in prepared:
            counts = {cause: 0 for cause in order}
            for violations in results:
                if violations:
                    for cause in order:
                        if cause in violations:
                            counts[cause] += 1
                            break
            if canonical_digest(counts) != digests[name]["digest"]:
                ok = False
                break
        if ok:
            matches.append(order)
    if not matches:
        raise PlanError(
            "no candidate precedence order reproduces the digests of 'sealed_precedence_digests.json'"
        )
    chosen = min(matches)
    return {
        "precedence_order": list(chosen),
        "precedence_matches": len(matches),
        "precedence_candidates_enumerated": len(precedence_candidates()),
        "sealed_configs": list(names),
    }


# --------------------------------------------------------------- settlement


def run_settlement(corpus, config, tie_break_key, precedence_order):
    space, axes = sweep_space(corpus)
    probe = int(axes["probe_steps"])
    router = Router(corpus, config, tie_break_key)
    base = Simulation(corpus, config, router, int(config["steps"]))
    base.run()
    profile = warmup_profile_record(base)
    required = list(profile["dims_requiring_dynamic"])
    prefiltered = []
    rejected = []
    admissible = []
    figures_by_label = {}
    for candidate in space:
        label = candidate_label(
            candidate["capacity_factor"],
            candidate["capacity_bucket"],
            candidate["mark_dynamic"],
            candidate["compile_mode"],
        )
        missing = sorted([name for name in required if name not in candidate["mark_dynamic"]])
        trial = dict(config)
        trial.update(candidate)
        trial["reset_steps"] = [int(s) for s in trial["reset_steps"] if int(s) <= probe]
        figures = evaluate_candidate(corpus, trial, router, probe)
        figures_by_label[label] = figures
        if missing:
            prefiltered.append({"candidate": label, "unmarked_dimensions": missing})
            continue
        violations = candidate_violations(corpus, figures)
        if violations:
            cause = None
            for name in precedence_order:
                if name in violations:
                    cause = name
                    break
            rejected.append(
                {"candidate": label, "cause": cause, "all_violations": violations}
            )
        else:
            admissible.append(
                {
                    "label": label,
                    "capacity_factor": candidate["capacity_factor"],
                    "capacity_bucket": candidate["capacity_bucket"],
                    "mark_dynamic": list(candidate["mark_dynamic"]),
                    "compile_mode": candidate["compile_mode"],
                }
            )
    prefiltered.sort(key=lambda entry: entry["candidate"])
    rejected.sort(key=lambda entry: entry["candidate"])
    counts = {cause: 0 for cause in precedence_order}
    for entry in rejected:
        counts[entry["cause"]] += 1
    admissible.sort(
        key=lambda entry: (
            float(entry["capacity_factor"]),
            -int(entry["capacity_bucket"]),
            len(entry["mark_dynamic"]),
            "|".join(entry["mark_dynamic"]),
            tuple(-ord(char) for char in entry["compile_mode"]),
        )
    )
    settled = admissible[0] if admissible else None
    return {
        "probe_steps": probe,
        "space": space,
        "prefiltered": prefiltered,
        "rejected": rejected,
        "admissible": admissible,
        "counts": counts,
        "settled": settled,
        "required": required,
        "figures_by_label": figures_by_label,
        "warmup_profile": profile,
    }


def settled_configuration_object(settled):
    return {
        "capacity_factor": settled["capacity_factor"],
        "capacity_bucket": settled["capacity_bucket"],
        "mark_dynamic": list(settled["mark_dynamic"]),
        "compile_mode": settled["compile_mode"],
    }


def rejection_ledger_record(settlement, precedence_order):
    return {
        "cause_order": list(precedence_order),
        "per_cause_counts": {
            cause: settlement["counts"].get(cause, 0) for cause in precedence_order
        },
        "rejected": [
            {
                "candidate": entry["candidate"],
                "cause": entry["cause"],
                "all_violations": list(entry["all_violations"]),
            }
            for entry in settlement["rejected"]
        ],
        "prefiltered": [
            {
                "candidate": entry["candidate"],
                "unmarked_dimensions": list(entry["unmarked_dimensions"]),
            }
            for entry in settlement["prefiltered"]
        ],
        "admissible_candidates": [entry["label"] for entry in settlement["admissible"]],
    }


def sensitivity_record(corpus, config, settled, tie_break_key, probe):
    axes = corpus.json_table("capacity_candidates.json")
    router = Router(corpus, config, tie_break_key)
    entries = []
    negative_speedup = 0
    negative_headroom = 0
    for item in axes.get("perturbations", []):
        setting = item["setting"]
        delta = item["delta"]
        trial = dict(config)
        if settled is not None:
            trial.update(settled_configuration_object(settled))
        if setting not in trial:
            raise PlanError(
                "table file 'capacity_candidates.json' perturbs the unknown setting %r" % setting
            )
        if isinstance(trial[setting], float):
            trial[setting] = float(trial[setting]) + float(delta)
        else:
            trial[setting] = int(trial[setting]) + int(delta)
        figures = evaluate_candidate(corpus, trial, router, probe)
        speedup_margin = figures["sim"].r_time(
            figures["speedup"] - float(corpus.steptime_gates["min_speedup"])
        )
        headroom_margin = figures["min_headroom"]
        recompile_margin = (
            int(corpus.steptime_gates["recompile_budget"]) - figures["recompiles_after_warmup"]
        )
        if speedup_margin < 0:
            negative_speedup += 1
        if headroom_margin < 0:
            negative_headroom += 1
        entries.append(
            {
                "setting": setting,
                "delta": delta,
                "speedup_margin": speedup_margin,
                "headroom_margin": headroom_margin,
                "recompile_margin": recompile_margin,
            }
        )
    return {
        "run_id": config["run_id"],
        "probe_steps": probe,
        "perturbations": entries,
        "negative_speedup_margins": negative_speedup,
        "negative_headroom_margins": negative_headroom,
    }


def full_figures(sim):
    compiled, eager, speedup = tail_figures(sim)
    dropped, mass, total, rate, steps_with = drop_figures(sim)
    minimum, peak = headroom_figures(sim)
    events, by_step, after, evictions, first_over = recompile_summary(sim)
    losses = [step["loss"] for step in sim.steps]
    baseline = [step["eager_loss"] for step in sim.steps]
    return {
        "compiled_tail_us": compiled,
        "eager_tail_us": eager,
        "speedup": speedup,
        "min_host_headroom_bytes": minimum,
        "recompiles_after_warmup": after,
        "drop_rate": rate,
        "min_capacity_seen": min_capacity_seen(sim),
        "closing_loss": losses[-1] if losses else sim.r_float(0.0),
        "baseline_closing_loss": baseline[-1] if baseline else sim.r_float(0.0),
        "relative_deviation": relative_deviation(
            losses[-1] if losses else 0.0,
            baseline[-1] if baseline else 0.0,
            sim.r_float,
        ),
    }


def gates_met_record(corpus, figures):
    return {
        "speedup": figures["speedup"] >= float(corpus.steptime_gates["min_speedup"]),
        "memory": figures["min_host_headroom_bytes"] >= 0,
        "recompile_budget": figures["recompiles_after_warmup"]
        <= int(corpus.steptime_gates["recompile_budget"]),
        "convergence": figures["relative_deviation"] <= float(corpus.gates["parity_band"]),
    }


def audit_statistics_record(deployed_sim, settled_sim, corpus):
    r = deployed_sim.r_float
    dep_after = recompile_summary(deployed_sim)[2]
    dep_events = recompile_summary(deployed_sim)[0]
    set_after = recompile_summary(settled_sim)[2]
    dep_capacity = set()
    for step in deployed_sim.steps:
        dep_capacity.update(step["capacity"])
    set_buckets = set()
    for step in settled_sim.steps:
        set_buckets.update(step["rank_bucket"].values())
    dep_dropped = sum(len(step["dropped"]) for step in deployed_sim.steps)
    dep_total = sum(step["total_assignments"] for step in deployed_sim.steps)
    set_dropped = sum(len(step["dropped"]) for step in settled_sim.steps)
    set_tokens = sum(step["tokens"] for step in settled_sim.steps)
    dep_bound = int(deployed_sim.config["warmup_bound"])
    set_bound = int(settled_sim.config["warmup_bound"])
    dep_breaks = sum(1 for step in deployed_sim.steps if step["causes"] and step["step"] <= dep_bound)
    set_breaks = sum(1 for step in settled_sim.steps if step["causes"] and step["step"] > set_bound)
    dep_host = [step["host_bytes"] for step in deployed_sim.steps]
    attempts = sum(step["capture_attempts"] for step in deployed_sim.steps)
    dep_failures = attempts - sum(step["captures"] for step in deployed_sim.steps)
    set_attempts = sum(step["capture_attempts"] for step in settled_sim.steps)
    set_captures = sum(step["captures"] for step in settled_sim.steps)
    dep_empty_steps = 0
    for step in deployed_sim.steps:
        if any(value == 0 for value in step["demand"]):
            dep_empty_steps += 1
    set_empty_slots = 0
    for step in settled_sim.steps:
        set_empty_slots += sum(1 for value in step["demand"] if value == 0)
    dep_router_keys = set()
    set_moe_keys = set()
    for step in deployed_sim.steps:
        for visit in step["visits"]:
            if visit["code_object"] == ROUTER_NAME:
                dep_router_keys.add((visit["code_object"], visit["rank"], visit["key"]))
    for step in settled_sim.steps:
        for visit in step["visits"]:
            if visit["code_object"] != ROUTER_NAME:
                set_moe_keys.add((visit["code_object"], visit["rank"], visit["key"]))
    return {
        "deployed_recompiles_total": len(dep_events),
        "settled_recompiles_after_warmup": set_after,
        "deployed_distinct_capacity_values": len(dep_capacity),
        "settled_distinct_rank_buckets": len(set_buckets),
        "deployed_drop_rate_assignment_denominator": r(dep_dropped / dep_total) if dep_total else r(0.0),
        "settled_drop_rate_token_denominator": r(set_dropped / set_tokens) if set_tokens else r(0.0),
        "deployed_break_steps_inclusive_warmup": dep_breaks,
        "settled_break_steps_exclusive_warmup": set_breaks,
        "deployed_mean_host_bytes": r(sum(dep_host) / len(dep_host)) if dep_host else r(0.0),
        "settled_peak_host_bytes": max(step["host_bytes"] for step in settled_sim.steps),
        "deployed_capture_failure_ratio": r(dep_failures / attempts) if attempts else r(0.0),
        "settled_capture_success_ratio": r(set_captures / set_attempts) if set_attempts else r(0.0),
        "deployed_empty_expert_step_count": dep_empty_steps,
        "settled_empty_expert_slot_count": set_empty_slots,
        "deployed_unique_guard_keys_router_only": len(dep_router_keys),
        "settled_unique_guard_keys_moe_only": len(set_moe_keys),
        "deployed_token_total": sum(step["tokens"] for step in deployed_sim.steps),
    }


def departing_settings_record(corpus, config):
    bounds = corpus.json_table("contract_bounds.json")["settings"]
    register = corpus.json_table("revision_register.json")["revisions"]
    applied = {}
    for entry in register:
        policy = entry["policy"]
        order = int(entry["effective_order"])
        if entry["status"] != "applied":
            continue
        if policy not in applied or order > applied[policy][0]:
            applied[policy] = (order, entry["revision"])
    out = []
    for setting in sorted(bounds):
        rule = bounds[setting]
        if setting not in config:
            continue
        value = config[setting]
        broken = False
        if "minimum" in rule and value < rule["minimum"]:
            broken = True
        if "maximum" in rule and value > rule["maximum"]:
            broken = True
        if "allowed_values" in rule and value not in rule["allowed_values"]:
            broken = True
        if not broken:
            continue
        policy = rule["policy"]
        revision = applied.get(policy, (0, None))[1]
        out.append(
            {
                "setting": setting,
                "value": value,
                "policy": policy,
                "revision": revision,
            }
        )
    return out


def deployed_diagnosis_record(corpus, config, deployed_sim, published, departing, admissible):
    figures = full_figures(deployed_sim)
    events, by_step, after, evictions, first_over = recompile_summary(deployed_sim)
    keys = (
        ("speedup", published.get("speedup"), figures["speedup"]),
        ("closing_loss", published.get("closing_loss"), figures["closing_loss"]),
        ("drop_rate", published.get("drop_rate"), figures["drop_rate"]),
        ("min_host_headroom_bytes", published.get("min_host_headroom_bytes"), figures["min_host_headroom_bytes"]),
        ("total_recompiles", published.get("total_recompiles"), len(events)),
        ("recompiles_after_warmup", published.get("recompiles_after_warmup"), after),
    )
    r = corpus.r_float
    compare = {}
    agrees = True
    for name, published_value, replayed in keys:
        if published_value is None:
            raise PlanError(
                "table file 'deployed_run_summary.json' is missing the published figure %r" % name
            )
        delta = r(float(published_value) - float(replayed))
        if delta != 0.0:
            agrees = False
        compare[name] = {
            "published": published_value,
            "replayed": replayed,
            "signed_delta": delta,
        }
    causes = {name: 0 for name in CAPTURE_CAUSES}
    for step in deployed_sim.steps:
        for name in CAPTURE_CAUSES:
            causes[name] += step["failure_causes"][name]
    return {
        "run_id": config["run_id"],
        "published_vs_replayed": compare,
        "departing_settings": departing,
        "capture_failure_causes": causes,
        "first_step_over_budget": first_over,
        "admissible": admissible,
        "published_agrees_with_replay": agrees,
    }


def validation_report_record(corpus, published, deployed_sim, records):
    figures = full_figures(deployed_sim)
    events = recompile_summary(deployed_sim)[0]
    replayed = {
        "speedup": figures["speedup"],
        "closing_loss": figures["closing_loss"],
        "drop_rate": figures["drop_rate"],
        "min_host_headroom_bytes": figures["min_host_headroom_bytes"],
        "recompiles_after_warmup": figures["recompiles_after_warmup"],
    }
    r = corpus.r_float
    residuals = {}
    worst = 0.0
    for name in ("speedup", "closing_loss", "drop_rate", "min_host_headroom_bytes", "recompiles_after_warmup"):
        if name not in published:
            raise PlanError(
                "table file 'deployed_run_summary.json' is missing the published figure %r" % name
            )
        value = r(float(published[name]) - float(replayed[name]))
        residuals[name] = value
        if abs(value) > abs(worst):
            worst = value
    counts = {}
    for name in COUNTED_RECORDS:
        if name not in records:
            raise PlanError("record '%s' was not built for the validation report" % name)
        body = records[name]
        if isinstance(body, dict) and "steps" in body and isinstance(body["steps"], list):
            counts[name] = len(body["steps"])
        else:
            counts[name] = len(body) if isinstance(body, dict) else 0
    return {
        "residuals": residuals,
        "record_counts": counts,
        "max_absolute_residual": r(abs(worst)),
        "artifact_count": len(COUNTED_RECORDS),
        "float_decimals": corpus.float_decimals,
        "time_decimals": corpus.time_decimals,
    }


# --------------------------------------------------------------- document verbs


def trace_output(corpus, config, tie_info):
    router = Router(corpus, config, tuple(tie_info["tie_break_key"]))
    sim = simulate(corpus, config, router)
    return {
        "tie_break_key": list(tie_info["tie_break_key"]),
        "tie_break_matches": tie_info["tie_break_matches"],
        "guard_key_index": guard_index(sim),
        "recompile_report": recompile_report_record(sim),
        "graph_break_ledger": graph_break_ledger_record(sim),
        "cudagraph_report": cudagraph_report_record(sim),
        "capacity_plan": capacity_plan_record(sim),
        "mesh_plan": mesh_plan_record(sim),
        "host_memory_report": host_memory_report_record(sim),
        "warmup_profile": warmup_profile_record(sim),
    }


def replay_output(corpus, config, tie_info):
    router = Router(corpus, config, tuple(tie_info["tie_break_key"]))
    sim = simulate(corpus, config, router)
    return {
        "tie_break_key": list(tie_info["tie_break_key"]),
        "tie_break_matches": tie_info["tie_break_matches"],
        "route_plan": route_plan_record(sim),
        "dispatch_ledger": dispatch_ledger_record(sim),
        "drop_ledger": drop_ledger_record(sim),
        "alltoall_ledger": alltoall_ledger_record(sim),
        "aux_loss_trace": aux_loss_record(sim),
        "loss_curve": loss_curve_record(sim),
        "gradient_ledger": gradient_ledger_record(sim),
        "optimizer_trace": optimizer_trace_record(sim),
        "convergence_report": convergence_record(sim),
        "baseline_parity": baseline_parity_record(sim),
        "steptime_report": steptime_report_record(sim),
    }


def resolve_output(corpus):
    tie = resolve_tie_break(corpus)
    precedence = resolve_precedence(corpus, tuple(tie["tie_break_key"]))
    out = dict(tie)
    out.update(precedence)
    out["sealed_configs"] = list(sealed_configs(corpus))
    return out


def settle_output(corpus, config):
    tie = resolve_tie_break(corpus)
    precedence = resolve_precedence(corpus, tuple(tie["tie_break_key"]))
    settlement = run_settlement(
        corpus, config, tuple(tie["tie_break_key"]), precedence["precedence_order"]
    )
    settled = settlement["settled"]
    return {
        "rejection_ledger": rejection_ledger_record(settlement, precedence["precedence_order"]),
        "warmup_profile": settlement["warmup_profile"],
        "settled_configuration": (
            settled_configuration_object(settled) if settled is not None else None
        ),
        "probe_steps": settlement["probe_steps"],
    }


# --------------------------------------------------------------- build


def build_output(data_dir, out_dir):
    corpus = Corpus.from_directory(data_dir)
    if "deployed_config.json" not in corpus.tables:
        raise PlanError("table file 'deployed_config.json' is missing from '%s'" % data_dir)
    if "deployed_run_summary.json" not in corpus.tables:
        raise PlanError("table file 'deployed_run_summary.json' is missing from '%s'" % data_dir)
    config = validate_config(corpus.tables["deployed_config.json"], "deployed_config.json")
    check_mesh(corpus, config)
    summary = corpus.json_table("deployed_run_summary.json")
    if "published" not in summary:
        raise PlanError("table file 'deployed_run_summary.json' carries no published block")
    published = summary["published"]

    sealed = resolve_output(corpus)
    tie_break_key = tuple(sealed["tie_break_key"])
    precedence_order = list(sealed["precedence_order"])

    router = Router(corpus, config, tie_break_key)
    deployed_sim = simulate(corpus, config, router)
    settlement = run_settlement(corpus, config, tie_break_key, precedence_order)
    settled = settlement["settled"]
    if settled is None:
        raise PlanError(
            "the candidate sweep of 'capacity_candidates.json' left no admissible configuration"
        )
    settled_config = dict(config)
    settled_config.update(settled_configuration_object(settled))
    settled_router = Router(corpus, settled_config, tie_break_key)
    settled_sim = simulate(corpus, settled_config, settled_router)

    records = {}
    records["route_plan.json"] = route_plan_record(deployed_sim)
    records["capacity_plan.json"] = capacity_plan_record(deployed_sim)
    records["mesh_plan.json"] = mesh_plan_record(deployed_sim)
    records["dispatch_ledger.json"] = dispatch_ledger_record(deployed_sim)
    records["drop_ledger.json"] = drop_ledger_record(deployed_sim)
    records["alltoall_ledger.json"] = alltoall_ledger_record(deployed_sim)
    records["guard_key_index.json"] = guard_index(deployed_sim)
    records["recompile_report.json"] = recompile_report_record(deployed_sim)
    records["graph_break_ledger.json"] = graph_break_ledger_record(deployed_sim)
    records["cudagraph_report.json"] = cudagraph_report_record(deployed_sim)
    records["host_memory_report.json"] = host_memory_report_record(deployed_sim)
    records["steptime_report.json"] = steptime_report_record(deployed_sim)
    records["warmup_profile.json"] = warmup_profile_record(deployed_sim)
    records["sealed_policy_resolution.json"] = {
        "tie_break_key": sealed["tie_break_key"],
        "tie_break_matches": sealed["tie_break_matches"],
        "tie_break_candidates_enumerated": sealed["tie_break_candidates_enumerated"],
        "precedence_order": sealed["precedence_order"],
        "precedence_matches": sealed["precedence_matches"],
        "precedence_candidates_enumerated": sealed["precedence_candidates_enumerated"],
        "sealed_configs": sealed["sealed_configs"],
    }
    records["aux_loss_trace.json"] = aux_loss_record(settled_sim)
    records["loss_curve.json"] = loss_curve_record(settled_sim)
    records["gradient_ledger.json"] = gradient_ledger_record(settled_sim)
    records["optimizer_trace.json"] = optimizer_trace_record(settled_sim)
    records["convergence_report.json"] = convergence_record(settled_sim)
    records["baseline_parity.json"] = baseline_parity_record(settled_sim)

    figures = full_figures(settled_sim)
    gates = gates_met_record(corpus, figures)
    settled_object = settled_configuration_object(settled)
    settlement_report = {
        "run_id": config["run_id"],
        "probe_steps": settlement["probe_steps"],
        "candidates_evaluated": len(settlement["space"]),
        "prefiltered_count": len(settlement["prefiltered"]),
        "rejected_count": len(settlement["rejected"]),
        "admissible_count": len(settlement["admissible"]),
        "settled_configuration": settled_object,
        "settled_gate_figures": {
            "speedup": figures["speedup"],
            "compiled_tail_us": figures["compiled_tail_us"],
            "eager_tail_us": figures["eager_tail_us"],
            "min_host_headroom_bytes": figures["min_host_headroom_bytes"],
            "recompiles_after_warmup": figures["recompiles_after_warmup"],
            "drop_rate": figures["drop_rate"],
            "min_capacity_seen": figures["min_capacity_seen"],
            "closing_loss": figures["closing_loss"],
            "baseline_closing_loss": figures["baseline_closing_loss"],
            "relative_deviation": figures["relative_deviation"],
        },
        "changed_settings": [
            {"setting": key, "from": config[key], "to": settled_object[key]}
            for key in ("capacity_factor", "capacity_bucket", "mark_dynamic", "compile_mode")
            if config[key] != settled_object[key]
        ],
        "gates_met": gates,
    }
    records["settlement_report.json"] = settlement_report
    records["rejection_ledger.json"] = rejection_ledger_record(settlement, precedence_order)
    records["sensitivity.json"] = sensitivity_record(
        corpus, config, settled, tie_break_key, settlement["probe_steps"]
    )
    records["audit_statistics.json"] = audit_statistics_record(deployed_sim, settled_sim, corpus)

    departing = departing_settings_record(corpus, config)
    deployed_probe = candidate_figures(deployed_sim)
    deployed_violations = candidate_violations(corpus, deployed_probe)
    admissible = (not departing) and (not deployed_violations)
    records["deployed_diagnosis.json"] = deployed_diagnosis_record(
        corpus, config, deployed_sim, published, departing, admissible
    )
    records["validation_report.json"] = validation_report_record(
        corpus, published, deployed_sim, records
    )

    if not os.path.isdir(out_dir):
        try:
            os.makedirs(out_dir)
        except OSError as exc:
            raise PlanError("output directory '%s' cannot be created: %s" % (out_dir, exc))
    stage_manifest = {
        "stage": STAGE_ONE,
        "artifact_count": len(STAGE_ONE_RECORDS),
        "artifact_sha256": {
            name: canonical_digest(records[name]) for name in STAGE_ONE_RECORDS
        },
    }
    stage_bytes = canonical_bytes(stage_manifest)
    replay_manifest = {
        "stage": STAGE_TWO,
        "artifact_count": len(STAGE_TWO_RECORDS),
        "artifact_sha256": {
            name: canonical_digest(records[name]) for name in STAGE_TWO_RECORDS
        },
        "stage_manifest_sha256": hashlib.sha256(stage_bytes).hexdigest(),
    }
    replay_bytes = canonical_bytes(replay_manifest)
    salt = canonical_digest(settled_object)
    fold = {
        "replay": hashlib.sha256(replay_bytes).hexdigest(),
        "salt": salt,
        "stage": hashlib.sha256(stage_bytes).hexdigest(),
    }
    convergence = convergence_record(settled_sim)
    deployed_report = records["deployed_diagnosis.json"]
    final_state = {
        "closing_loss": figures["closing_loss"],
        "convergence_verdict": convergence["verdict"],
        "deployed_admissible": deployed_report["admissible"],
        "digest_of_digests": canonical_digest(fold),
        "first_step_over_budget": deployed_report["first_step_over_budget"],
        "precedence_order": precedence_order,
        "replay_manifest_sha256": fold["replay"],
        "settled_configuration": settled_object,
        "settlement_salt": salt,
        "speedup": figures["speedup"],
        "stage_manifest_sha256": fold["stage"],
        "tie_break_key": list(tie_break_key),
        "total_artifacts": len(ALL_RECORDS),
    }
    records["stage_manifest.json"] = stage_manifest
    records["replay_manifest.json"] = replay_manifest
    records["final_state.json"] = final_state
    for name in ALL_RECORDS:
        if name not in records:
            raise PlanError("record '%s' was not built for this corpus" % name)
        path = os.path.join(out_dir, name)
        with open(path, "wb") as handle:
            handle.write(canonical_bytes(records[name]))
    return records


# --------------------------------------------------------------- entry point


def _load_document(path):
    if not os.path.isfile(path):
        raise PlanError("document '%s' is not a file" % path)
    value = _load_json(path)
    if not isinstance(value, dict):
        raise PlanError("document '%s' is not a JSON object" % path)
    return value


def main(argv):
    program = os.path.basename(argv[0]) if argv and argv[0] else "moeplan.py"
    if len(argv) < 2:
        raise PlanError("usage: %s build|trace|replay|settle|resolve ARGUMENT" % program)
    verb = argv[1]
    if verb == "build":
        if len(argv) != 4:
            raise PlanError("usage: %s build DATA_DIR OUT_DIR" % program)
        build_output(argv[2], argv[3])
        return 0
    if verb not in ("trace", "replay", "settle", "resolve"):
        raise PlanError("verb %r is not one of build, trace, replay, settle, resolve" % verb)
    if len(argv) != 3:
        raise PlanError("usage: %s %s DOCUMENT" % (program, verb))
    path = argv[2]
    document = _load_document(path)
    corpus = Corpus.from_document(document, path)
    if verb == "resolve":
        output = resolve_output(corpus)
    else:
        if "config" not in document:
            raise PlanError("document '%s' carries no configuration" % path)
        config = validate_config(document["config"], path)
        check_mesh(corpus, config)
        if verb == "trace":
            tie = resolve_tie_break(corpus)
            output = trace_output(corpus, config, tie)
        elif verb == "replay":
            tie = resolve_tie_break(corpus)
            output = replay_output(corpus, config, tie)
        else:
            output = settle_output(corpus, config)
    sys.stdout.write(canonical_text(output))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except PlanError as error:
        sys.stderr.write("moeplan: %s\n" % error)
        sys.exit(2)

