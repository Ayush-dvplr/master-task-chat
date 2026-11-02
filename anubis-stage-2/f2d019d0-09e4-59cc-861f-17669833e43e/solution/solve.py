"""moeplan: replay, diagnose and settle a mixture of experts training run.

Written against the corpus contracts. Standard library only and deterministic:
every figure is recomputed from the directory or document handed to a verb.
"""

import hashlib
import json
import math
import os
import struct
import sys

U64 = 0xFFFFFFFFFFFFFFFF
GOLDEN = 0x9E3779B97F4A7C15
FNV_OFFSET = 0xCBF29CE484222325
FNV_PRIME = 0x100000001B3
E4M3_CEILING = 448.0
E4M3_SUB_STEP = 2.0 ** -9
E4M3_LOWEST_EXP = -6

REJECTION_CAUSES = tuple(sorted(
    "capacity_below_minimum convergence_band_unmet drop_tolerance_exceeded eager_mode_forbidden "
    "memory_ceiling_exceeded recompile_budget_exceeded speedup_gate_unmet".split()
))
TIE_FIELDS = tuple("expert_index running_load placement_rank bias_rank".split())
BREAK_ORDER = tuple(sorted(
    "data_dependent_capacity dynamic_token_count token_drop_mask unbalanced_expert_slice zero_token_expert".split()
))


# ----------------------------------------------------------- bit level helpers


def _xs_step(x):
    x ^= (x << 13) & U64
    x ^= x >> 7
    x ^= (x << 17) & U64
    return x & U64


class Stream(object):
    """The xorshift64 generator of the stream contract."""

    def __init__(self, seed):
        self._word = (int(seed) & U64) or GOLDEN

    def word(self):
        self._word = _xs_step(self._word)
        return self._word

    def unit(self):
        return (self.word() >> 11) * (2.0 ** -53)


def _fold(values):
    acc = FNV_OFFSET
    for value in values:
        acc ^= value & U64
        acc = (acc * FNV_PRIME) & U64
        acc ^= acc >> 29
    return acc & U64


def mix_words(*parts):
    return _fold(int(part) for part in parts)


def pair_affinity(token_word, expert_word):
    return _xs_step(_fold((token_word, expert_word)) or GOLDEN)


def as_fp32(x):
    return struct.unpack("<f", struct.pack("<f", float(x)))[0]


def as_bf16(x):
    x = float(x)
    if math.isnan(x):
        return x
    (word,) = struct.unpack("<I", struct.pack("<f", x))
    word = (word + 0x7FFF + ((word >> 16) & 1)) & 0xFFFFFFFF
    return struct.unpack("<f", struct.pack("<I", word & 0xFFFF0000))[0]


def _nearest_even(scaled):
    whole = math.floor(scaled)
    frac = scaled - whole
    if frac > 0.5 or (frac == 0.5 and int(whole) % 2 == 1):
        whole += 1.0
    return whole


def as_e4m3(x):
    x = float(x)
    if math.isnan(x):
        return x
    if x == 0.0:
        return 0.0
    magnitude = abs(x)
    exponent = math.frexp(magnitude)[1] - 1
    quantum = E4M3_SUB_STEP if exponent < E4M3_LOWEST_EXP else 2.0 ** (exponent - 3)
    snapped = min(_nearest_even(magnitude / quantum) * quantum, E4M3_CEILING)
    return snapped if x > 0.0 else -snapped


def grid_snap(x, levels):
    return _nearest_even(float(x) * float(levels)) / float(levels)


def rnd(x, places):
    x = float(x)
    if math.isnan(x) or math.isinf(x):
        return x
    out = round(x, int(places))
    return 0.0 if out == 0.0 else out


def encode(obj):
    text = json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=False)
    return (text + "\n").encode("utf-8")


def sha_hex(blob):
    return hashlib.sha256(blob).hexdigest()


def obj_digest(obj):
    return sha_hex(encode(obj))


def dump(path, obj):
    blob = encode(obj)
    with open(path, "wb") as sink:
        sink.write(blob)
    return sha_hex(blob)


def _text(path):
    try:
        with open(path, encoding="utf-8") as source:
            return source.read()
    except (OSError, UnicodeDecodeError) as problem:
        raise SystemExit("cannot read input file %s: %s" % (path, problem))


def _parse(path, text):
    try:
        return json.loads(text)
    except ValueError as problem:
        raise SystemExit("input file %s is not valid JSON: %s" % (path, problem))


def load_json(path):
    return _parse(path, _text(path))


def load_csv(path):
    header, table = None, []
    for raw in _text(path).splitlines():
        line = raw.strip()
        if line == "" or line[0] == "#":
            continue
        cells = [cell.strip() for cell in line.split(",")]
        if header is None:
            header = cells
        else:
            table.append(dict(zip(header, cells)))
    return table


def load_jsonl(path):
    lines = (raw.strip() for raw in _text(path).splitlines())
    return [_parse(path, line) for line in lines if line]


def up_div(top, bottom):
    return -(-int(top) // int(bottom))


# ------------------------------------------------------------- corpus loading


CORPUS_LAYOUT = (
    ("tolerances", "validation_tolerances.json"),
    ("run_config", "sample_run_config.json"),
    ("calibration_config", "calibration_config.json"),
    ("deployed_config", "deployed_config.json"),
    ("topology", "model_topology.json"),
    ("candidates", "capacity_candidates.json"),
    ("convergence_gates", "convergence_gates.json"),
    ("steptime_gates", "steptime_gates.json"),
    ("memory_gates", "memory_gates.json"),
    ("warmup_windows", "warmup_windows.json"),
    ("rank_inventory", "ep_rank_inventory.json"),
    ("probes", "probe_configurations.json"),
    ("sealed_precedence", "sealed_precedence_digests.json"),
    ("sealed_tiebreak", "sealed_tiebreak_digests.json"),
    ("revisions", "revision_register.json"),
    ("bounds", "contract_bounds.json"),
    ("deployed_summary", "deployed_run_summary.json"),
    ("deployed_mesh", "deployed_mesh_dump.json"),
    ("eager_baseline", "eager_baseline.json"),
    ("expert_cost", "expert_cost_table.csv"),
    ("expert_bias", "expert_bias_table.csv"),
    ("expert_placement", "expert_placement.csv"),
    ("compile_cost", "compile_cost_table.csv"),
    ("capture_cost", "capture_cost_table.csv"),
    ("alltoall_cost", "alltoall_cost_table.csv"),
    ("memory_slots", "memory_slot_table.csv"),
    ("pool_blocks", "pool_block_table.csv"),
    ("seq_schedule", "seq_length_schedule.csv"),
    ("rank_affinity", "rank_affinity.csv"),
    ("break_catalog", "graph_break_catalog.csv"),
    ("calibration_parity", "calibration_parity.jsonl"),
    ("deployed_compile_log", "deployed_compile_log.jsonl"),
    ("deployed_step_timeline", "deployed_step_timeline.jsonl"),
    ("deployed_guard_dump", "deployed_guard_dump.jsonl"),
    ("deployed_alltoall", "deployed_alltoall_trace.jsonl"),
    ("deployed_memory", "deployed_memory_trace.csv"),
    ("token_batches", "token_batches.jsonl"),
)

_LOADERS = {".json": load_json, ".csv": load_csv, ".jsonl": load_jsonl}


class Corpus(object):
    """The parsed contents of one data directory."""

    def __init__(self, folder):
        self.base = str(folder)
        for attribute, filename in CORPUS_LAYOUT:
            loader = _LOADERS[os.path.splitext(filename)[1]]
            setattr(self, attribute, loader(os.path.join(self.base, filename)))
        self.decimals = int(self.tolerances["float_decimals"])
        self.time_decimals = int(self.tolerances["time_decimals"])


def policy_in_force(register, policy):
    """The applied revision with the highest effective order wins."""
    applied = [
        entry for entry in register["revisions"]
        if entry["policy"] == policy and entry["status"] == "applied"
    ]
    if not applied:
        raise ValueError("revision_register.json holds no applied revision for policy " + repr(policy))
    return max(applied, key=lambda entry: int(entry["effective_order"]))


def lookup(rows, field, wanted, column, cast=float):
    wanted = str(wanted)
    for row in rows:
        if row[field] == wanted:
            return cast(row[column])
    raise KeyError("no row with " + field + "=" + wanted + " carries " + column)


# ------------------------------------------------------------ bound run spec


_INT_KEYS = ("num_experts", "top_k", "ep_world_size", "steps", "warmup_bound", "capacity_bucket",
             "min_capacity", "cache_size_limit", "promotion_threshold", "router_jitter_slots", "seed")
_FLOAT_KEYS = ("capacity_factor", "loss_scale", "learning_rate", "clip_threshold", "aux_loss_weight")
_BOOL_KEYS = ("dynamic_promotion_enabled", "expert_bias_enabled")


class Spec(object):
    """One run configuration joined to the shipped tables."""

    def __init__(self, config, corpus):
        self.config = dict(config)
        self.corpus = corpus
        self.decimals = corpus.decimals
        self.time_decimals = corpus.time_decimals
        for name in _INT_KEYS:
            setattr(self, name, int(config[name]))
        for name in _FLOAT_KEYS:
            setattr(self, name, float(config[name]))
        for name in _BOOL_KEYS:
            setattr(self, name, bool(config[name]))
        self.run_id = str(config["run_id"])
        self.compile_mode = str(config["compile_mode"])
        self.mark_dynamic = tuple(sorted(config["mark_dynamic"]))
        self.reset_steps = tuple(sorted(int(value) for value in config["reset_steps"]))
        self.moe_layer_indices = [int(value) for value in config["moe_layer_indices"]]
        self.seq_lengths = self._schedule(str(config["seq_profile"]))

        surrogate = corpus.topology["surrogate"]
        self.jitter_scale = float(corpus.topology["router"]["jitter_scale"])
        self.grid_levels = int(corpus.topology["router"]["quantization_levels"])
        self.base_loss = float(surrogate["base_loss"])
        self.signal_weight = float(surrogate["signal_weight"])
        self.decay_rate = float(surrogate["decay_rate"])
        self.d_model = int(corpus.topology["d_model"])
        self.d_ff = int(corpus.topology["d_ff"])

        experts = range(self.num_experts)
        self.bias_gain = [lookup(corpus.expert_bias, "expert_index", e, "bias_gain") for e in experts]
        self.cost_weight = [lookup(corpus.expert_cost, "expert_index", e, "cost_weight") for e in experts]
        self.kernel_us = [lookup(corpus.expert_cost, "expert_index", e, "kernel_us_per_slot") for e in experts]
        self.placement_group = [
            lookup(corpus.expert_placement, "expert_index", e, "placement_group", int) for e in experts
        ]
        self.bias_rank = [int(math.floor(gain * 10.0)) for gain in self.bias_gain]
        self.expert_rank = self._placement()
        self.rank_experts = {}
        for expert, rank in enumerate(self.expert_rank):
            self.rank_experts.setdefault(rank, []).append(expert)

    def _schedule(self, profile):
        picked = [row for row in self.corpus.seq_schedule if row["profile"] == profile]
        if not picked:
            raise ValueError("no sequence schedule for profile " + repr(profile) + " in seq_length_schedule.csv")
        picked.sort(key=lambda row: int(row["step"]))
        return [int(row["tokens"]) for row in picked]

    def _placement(self):
        world, experts = self.ep_world_size, self.num_experts
        if experts % world:
            raise ValueError("expert count " + str(experts) + " does not divide across an expert parallel mesh of " + str(world) + " ranks")
        per_rank = experts // world
        affinity = [row for row in self.corpus.rank_affinity if int(row["ep_world_size"]) == world]
        if len(affinity) != world:
            raise ValueError("rank_affinity.csv does not cover the ep_world_size " + str(world))
        affinity.sort(key=lambda row: int(row["group_order"]))
        walk = sorted(range(experts), key=lambda e: (self.placement_group[e], e))
        owner = [0] * experts
        for position, expert in enumerate(walk):
            owner[expert] = int(affinity[position // per_rank]["rank"])
        return owner

    def tokens_at(self, step):
        return self.seq_lengths[(step - 1) % len(self.seq_lengths)]

    def draws(self, step):
        """Four blocks in contract order; the bias block draws nothing when disabled."""
        stream = Stream(mix_words(self.seed, step))
        salt = [stream.unit() for _ in range(self.tokens_at(step))]
        phase = [stream.unit() for _ in range(self.num_experts)]
        if self.expert_bias_enabled:
            bias = [stream.unit() for _ in range(self.num_experts)]
        else:
            bias = [0.5 for _ in range(self.num_experts)]
        jitter = [stream.unit() for _ in range(self.router_jitter_slots)]
        return salt, phase, bias, jitter


# --------------------------------------------------------------------- router


def _tie_keys(spec, order, load):
    columns = {
        "expert_index": list(range(spec.num_experts)),
        "running_load": load,
        "placement_rank": spec.expert_rank,
        "bias_rank": spec.bias_rank,
    }
    picked = [columns[name] for name in order]
    return [tuple(column[e] for column in picked) for e in range(spec.num_experts)]


def route(spec, step, order):
    """Quantised top k routing for one step under a given tie break order."""
    dp = spec.decimals
    salt, phase, bias_draw, jitter = spec.draws(step)
    n = spec.num_experts
    if spec.expert_bias_enabled:
        offsets = [rnd((bias_draw[e] * 2.0 - 1.0) * spec.bias_gain[e], dp) for e in range(n)]
    else:
        offsets = [0.0] * n
    phase_words = [int(value * (2.0 ** 52)) for value in phase]
    slots = spec.router_jitter_slots
    load = [0] * n
    picks, ties, grid = [], [], []
    for token, value in enumerate(salt):
        token_word = int(value * (2.0 ** 52))
        logits = []
        for e in range(n):
            centred = rnd((pair_affinity(token_word, phase_words[e]) >> 11) * 2.220446049250313e-16 - 1.0, dp)
            noise = rnd((jitter[(token + e) % slots] * 2.0 - 1.0) * spec.jitter_scale, dp) if slots > 0 else 0.0
            logits.append(rnd(grid_snap(rnd(centred + offsets[e] + noise, dp), spec.grid_levels), dp))
        grid.append(logits)
        keys = _tie_keys(spec, order, load)
        ranking = sorted(range(n), key=lambda e: (-logits[e],) + keys[e] + (e,))
        winners = ranking[: spec.top_k]
        edge = logits[winners[-1]]
        level = [e for e in range(n) if logits[e] == edge]
        if len(level) > 1:
            ties.append({
                "step": step,
                "token_index": token,
                "quantized_logit": edge,
                "contenders": level,
                "selected": sorted(e for e in winners if logits[e] == edge),
            })
        low = min(logits)
        lifted = [rnd(logits[e] - low + 1.0, dp) for e in winners]
        norm = rnd(sum(lifted), dp)
        for place, expert in enumerate(winners):
            load[expert] += 1
            picks.append({
                "token_index": token,
                "expert": expert,
                "rank_in_topk": place,
                "weight": rnd(lifted[place] / norm, dp),
            })
    demand = [0] * n
    mass = [0.0] * n
    for pick in picks:
        demand[pick["expert"]] += 1
        mass[pick["expert"]] = rnd(mass[pick["expert"]] + pick["weight"], dp)
    return {
        "step": step,
        "token_count": len(salt),
        "assignments": picks,
        "demand": demand,
        "gate_mass": [rnd(value, dp) for value in mass],
        "tie_break_events": ties,
        "quantized": grid,
    }


# ------------------------------------------------------- capacity and mesh


def capacities(spec, demand):
    """Align to the bucket first, then hold at the minimum."""
    fair = spec.capacity_factor * float(sum(demand)) / float(spec.num_experts)
    bucket = spec.capacity_bucket
    return [
        max(spec.min_capacity, bucket * up_div(math.ceil(min(float(want), fair)), bucket))
        for want in demand
    ]


def rank_reduction(spec, caps):
    per_rank = dict((rank, max(caps[e] for e in spec.rank_experts[rank])) for rank in sorted(spec.rank_experts))
    return per_rank, max(per_rank.values())


def dispatch(spec, routing, caps):
    """Fill expert slots in assignment order; overflow is dropped."""
    dp = spec.decimals
    fill = [0] * spec.num_experts
    kept, lost = [], []
    for pick in routing["assignments"]:
        expert = pick["expert"]
        if fill[expert] >= caps[expert]:
            lost.append(dict(pick))
            continue
        entry = dict(pick)
        entry["slot"] = fill[expert]
        fill[expert] += 1
        kept.append(entry)
    lost_mass = 0.0
    for pick in lost:
        lost_mass = rnd(lost_mass + pick["weight"], dp)
    return {
        "accepted": kept,
        "dropped": lost,
        "accepted_count": fill,
        "dropped_tokens": len(lost),
        "dropped_token_mass": rnd(lost_mass, dp),
    }


def balance_term(spec, routing, sent):
    """The auxiliary balance term, sourced from demand before capacity applies."""
    dp = spec.decimals
    n = spec.num_experts
    demand = routing["demand"]
    wanted = sum(demand)
    tokens = routing["token_count"]
    share = [rnd(float(d) / float(wanted), dp) if wanted else 0.0 for d in demand]
    prob = [rnd(m / float(tokens), dp) if tokens else 0.0 for m in routing["gate_mass"]]
    dot = 0.0
    for e in range(n):
        dot = rnd(dot + rnd(share[e] * prob[e], dp), dp)
    live = [share[e] for e in range(n) if demand[e] > 0]
    spread = None
    if len(live) == 1:
        spread = 0.0
    elif live:
        spread = rnd(max(live) - min(live), dp)
    usage = []
    for e in range(n):
        if demand[e] == 0:
            usage.append(None)
            continue
        took = sent["accepted_count"][e]
        usage.append(rnd(float(took) / float(demand[e]) * share[e], dp))
    return {
        "aux_loss": rnd(spec.aux_loss_weight * float(n) * dot, dp),
        "assignment_fractions": share,
        "gate_probabilities": prob,
        "load_dispersion": spread,
        "expert_utilization": usage,
        "empty_experts": [e for e in range(n) if demand[e] == 0],
    }


# ------------------------------------------------------ guards and caching


class Guards(object):
    """Dimension promotion per code object and a bounded cache per rank."""

    def __init__(self, spec):
        self.spec = spec
        self.code_objects = ["router"] + ["moe_block_%d" % layer for layer in spec.moe_layer_indices]
        self.dims = dict((name, ("capacity", "local_experts")) for name in self.code_objects)
        self.dims["router"] = ("tokens",)
        self.seen = {}
        self.promoted = {}
        for name in self.code_objects:
            for dim in self.dims[name]:
                self.seen[name, dim] = set()
                self.promoted[name, dim] = dim in spec.mark_dynamic
        self.cache = {}
        self.last_use = {}
        self.clock = 0

    def note(self, name, dim, size):
        """The size being compiled now counts toward the distinct total."""
        if self.promoted[name, dim]:
            return
        sizes = self.seen[name, dim]
        sizes.add(size)
        if self.spec.dynamic_promotion_enabled and len(sizes) >= self.spec.promotion_threshold:
            self.promoted[name, dim] = True

    def part(self, name, dim, size):
        if self.promoted[name, dim] and size not in (0, 1):
            return "dyn"
        return str(size)

    def clear(self):
        self.cache = {}
        self.last_use = {}

    def entries(self):
        return sum(len(bucket) for bucket in self.cache.values())

    def closures(self):
        return sum(
            len([piece for piece in key.split("|") if piece != "dyn"])
            for bucket in self.cache.values() for key in bucket
        )


def compile_walk(spec, guards, step, tokens, per_rank):
    """Guard keys, recompilations and least recently used evictions for one step."""
    fired, seen_keys = [], []
    for name in guards.code_objects:
        dims = guards.dims[name]
        for rank in sorted(spec.rank_experts):
            size = {"tokens": tokens, "capacity": per_rank[rank], "local_experts": len(spec.rank_experts[rank])}
            before = len([dim for dim in dims if not guards.promoted[name, dim]])
            for dim in dims:
                guards.note(name, dim, size[dim])
            pieces = [guards.part(name, dim, size[dim]) for dim in dims]
            key = "|".join(pieces)
            after = len([piece for piece in pieces if piece != "dyn"])
            home = (name, rank)
            bucket = guards.cache.setdefault(home, {})
            guards.clock += 1
            seen_keys.append({
                "code_object": name, "rank": rank, "key": key,
                "static_dims_before": before, "static_dims_after": after,
            })
            if key in bucket:
                guards.last_use[home, key] = guards.clock
                continue
            victim = None
            if len(bucket) >= spec.cache_size_limit:
                victim = min(bucket, key=lambda old: (guards.last_use[home, old], old))
                bucket.pop(victim)
                guards.last_use.pop((home, victim))
            bucket[key] = True
            guards.last_use[home, key] = guards.clock
            fired.append({
                "step": step, "code_object": name, "rank": rank, "guard_key": key,
                "static_dims_before": before, "static_dims_after": after,
                "guard_delta": after - before, "evicted_key": victim,
            })
    return fired, seen_keys


# ----------------------------------------------- breaks, capture and pools


def breaks_for(spec, caps, per_rank, sent, demand, last_tokens, tokens):
    hits = set()
    if [cap for cap in caps if cap % spec.capacity_bucket]:
        hits.add("data_dependent_capacity")
    if last_tokens is not None and last_tokens != tokens and "tokens" not in spec.mark_dynamic:
        hits.add("dynamic_token_count")
    if sent["dropped_tokens"] > 0:
        hits.add("token_drop_mask")
    if len(set(per_rank.values())) > 1:
        hits.add("unbalanced_expert_slice")
    if 0 in demand:
        hits.add("zero_token_expert")
    return [cause for cause in BREAK_ORDER if cause in hits]


def capture_attempts(spec, seen_keys, break_total):
    """Which expert blocks the reduce overhead path may capture this step."""
    tried = []
    for seen in seen_keys:
        if seen["code_object"] == "router":
            continue
        if spec.compile_mode != "reduce-overhead":
            reason = "capture_disabled_for_mode"
        elif break_total > 0:
            reason = "operation_not_permitted_when_stream_is_capturing"
        elif "dyn" in seen["key"].split("|"):
            reason = "dynamic_dimension_in_guard_key"
        else:
            reason = None
        tried.append({
            "code_object": seen["code_object"],
            "rank": seen["rank"],
            "guard_key": seen["key"],
            "captured": reason is None,
            "cause": reason,
        })
    return tried


def pool_growth(spec, per_rank):
    blocks = sorted(spec.corpus.pool_blocks, key=lambda row: int(row["capacity_ceiling"]))
    grown = 0
    for rank in sorted(per_rank):
        fitting = [row for row in blocks if per_rank[rank] <= int(row["capacity_ceiling"])]
        grown += int((fitting[0] if fitting else blocks[-1])["block_bytes"])
    return grown


# --------------------------------------------------------------- step time


def _first(rows, test):
    for row in rows:
        if test(row):
            return row
    return None


def step_time(spec, fired, tried, breaks, per_rank, collective, eager):
    tp = spec.time_decimals
    corpus = spec.corpus
    gates = corpus.steptime_gates
    compile_total = capture_total = bubble_total = 0.0
    discount = 1.0
    if not eager:
        for event in fired:
            row = _first(corpus.compile_cost, lambda r: r["compile_mode"] == spec.compile_mode
                         and int(r["static_dims"]) == event["static_dims_before"])
            price = float(row["compile_us"]) if row is not None else float(gates["fallback_compile_us"])
            compile_total = rnd(compile_total + price, tp)
        row = _first(corpus.capture_cost, lambda r: r["compile_mode"] == spec.compile_mode)
        unit = 0.0
        if row is not None:
            unit, discount = float(row["capture_us"]), float(row["replay_discount"])
        captured = len([attempt for attempt in tried if attempt["captured"]])
        capture_total = rnd(unit * float(captured), tp)
        if not captured:
            discount = 1.0
    compute = 0.0
    for rank in sorted(spec.rank_experts):
        local = 0.0
        for expert in spec.rank_experts[rank]:
            local = rnd(local + spec.kernel_us[expert] * float(per_rank[rank]), tp)
        compute = max(compute, local)
    scale = float(gates["eager_compute_multiplier"]) if eager else discount
    compute = rnd(compute * scale, tp)
    row = _first(corpus.alltoall_cost, lambda r: int(r["ep_world_size"]) == spec.ep_world_size)
    fixed, per_slot = (float(row["fixed_us"]), float(row["per_slot_us"])) if row is not None else (0.0, 0.0)
    exchange = rnd(fixed + per_slot * float(collective) * float(spec.ep_world_size), tp)
    if not eager:
        layers = float(len(spec.moe_layer_indices))
        for cause in breaks:
            bubble_total = rnd(bubble_total + lookup(corpus.break_catalog, "cause", cause, "bubble_us") * layers, tp)
        if fired:
            bubble_total = rnd(bubble_total + float(gates["sync_bubble_us"]), tp)
    parts = [rnd(value, tp) for value in (compile_total, capture_total, compute, exchange, bubble_total)]
    whole = parts[0] + parts[1] + parts[2] + parts[3] + parts[4]
    return dict(zip(
        ("compile_us", "capture_us", "compute_us", "alltoall_us", "bubble_us", "step_us"),
        parts + [rnd(whole, tp)],
    ))


# -------------------------------------------------------- numeric replay


def _keep(x, eager):
    return float(x) if eager else as_bf16(x)


def _acc(x, eager):
    return float(x) if eager else as_fp32(x)


def numeric_step(spec, routing, sent, params, eager):
    """Expert outputs, the folded step signal and the clipped optimizer update."""
    dp = spec.decimals
    n = spec.num_experts
    scale = float(spec.corpus.topology["surrogate"]["payload_scale"])
    salt = spec.draws(routing["step"])[0]
    queues = [[] for _ in range(n)]
    for entry in sent["accepted"]:
        queues[entry["expert"]].append(entry)
    outs, partial = [], []
    for e in range(n):
        running = _acc(0.0, eager)
        for entry in sorted(queues[e], key=lambda item: item["slot"]):
            centred = _keep(rnd(salt[entry["token_index"]] * 2.0 - 1.0, dp), eager)
            gate = _keep(entry["weight"], eager)
            product = _acc(gate * (1.0 - centred * 0.25), eager)
            if eager:
                wire = product * scale
            else:
                wire = as_e4m3(_acc(product * scale, eager))
            running = _acc(running + _acc(wire / scale, eager), eager)
        filled = sent["accepted_count"][e]
        outs.append(_keep(running / float(filled), eager) if filled else _keep(0.0, eager))
        partial.append(rnd(running, dp))
    signal = _acc(0.0, eager)
    for e in range(n):
        signal = _acc(signal + _acc(outs[e] * spec.cost_weight[e], eager), eager)
    grads = [_acc(outs[e] * spec.signal_weight * spec.cost_weight[e], eager) for e in range(n)]
    lifted = [_acc(g * spec.loss_scale, eager) for g in grads]
    squares = _acc(0.0, eager)
    for value in lifted:
        squares = _acc(squares + _acc(value * value, eager), eager)
    norm = math.sqrt(squares)
    ceiling = spec.clip_threshold * spec.loss_scale
    shrink = 1.0 if norm <= ceiling else ceiling / norm
    restored = [_acc(_acc(value * shrink, eager) / spec.loss_scale, eager) for value in lifted]
    updated = [_keep(params[e] - spec.learning_rate * restored[e], eager) for e in range(n)]
    return {
        "expert_outputs": [rnd(value, dp) for value in outs],
        "expert_partials": partial,
        "step_signal": rnd(signal, dp),
        "gradients": [rnd(value, dp) for value in grads],
        "scaled_norm": rnd(norm, dp),
        "clip_reference": rnd(ceiling, dp),
        "clip_factor": rnd(shrink, dp),
        "unscaled_gradients": [rnd(value, dp) for value in restored],
        "params": updated,
        "clipped": norm > ceiling,
    }


# ----------------------------------------------------------- full run walk


def _slot_prices(spec):
    rows = spec.corpus.memory_slots
    wanted = min(3, max(0, len(spec.mark_dynamic)))
    row = _first(rows, lambda r: int(r["static_dims"]) == wanted)
    entry_size = int(row["entry_bytes"]) if row is not None else 0
    guard_size = int(row["guard_bytes"]) if row is not None else 0
    if entry_size == 0:
        entry_size, guard_size = int(rows[-1]["entry_bytes"]), int(rows[-1]["guard_bytes"])
    return entry_size, guard_size


def run(spec, order, eager=False, collect=True):
    """Walk every step of one configuration in order."""
    dp = spec.decimals
    guards = Guards(spec)
    params = [_keep(0.0, eager)] * spec.num_experts
    entry_size, guard_size = _slot_prices(spec)
    base_host = int(spec.corpus.memory_gates["host_base_bytes"])
    ceiling = int(spec.corpus.memory_gates["host_ceiling_bytes"])
    pool, peak, last_tokens = 0, 0, None
    records = []
    for step in range(1, spec.steps + 1):
        reset = step in spec.reset_steps
        if reset:
            guards.clear()
            pool = 0
        routing = route(spec, step, order)
        caps = capacities(spec, routing["demand"])
        per_rank, collective = rank_reduction(spec, caps)
        sent = dispatch(spec, routing, caps)
        balance = balance_term(spec, routing, sent)
        breaks = breaks_for(spec, caps, per_rank, sent, routing["demand"], last_tokens, routing["token_count"])
        fired, seen_keys = compile_walk(spec, guards, step, routing["token_count"], per_rank)
        tried = capture_attempts(spec, seen_keys, len(breaks))
        if not eager and [attempt for attempt in tried if attempt["captured"]]:
            pool += pool_growth(spec, per_rank)
        step_peak = max(peak, pool)
        timing = step_time(spec, fired, tried, breaks, per_rank, collective, eager)
        numeric = numeric_step(spec, routing, sent, params, eager)
        params = numeric["params"]
        decayed = rnd(spec.base_loss * (1.0 / (1.0 + spec.decay_rate * float(step))), dp)
        loss = rnd(decayed + balance["aux_loss"] + rnd(spec.signal_weight * numeric["step_signal"], dp), dp)
        host = base_host + guards.entries() * entry_size + guards.closures() * guard_size + step_peak
        if collect:
            records.append({
                "step": step,
                "reset": reset,
                "token_count": routing["token_count"],
                "demand": routing["demand"],
                "capacity": caps,
                "rank_bucket": dict((str(rank), size) for rank, size in per_rank.items()),
                "alltoall_bucket": collective,
                "accepted_count": sent["accepted_count"],
                "dropped_tokens": sent["dropped_tokens"],
                "dropped_token_mass": sent["dropped_token_mass"],
                "aux": balance,
                "breaks": breaks,
                "recompiles": len(fired),
                "events": fired,
                "keys": seen_keys,
                "captures": tried,
                "pool_bytes": pool,
                "pool_peak_bytes": step_peak,
                "cache_entries": guards.entries(),
                "guard_closures": guards.closures(),
                "host_bytes": host,
                "host_headroom_bytes": ceiling - host,
                "timing": timing,
                "numeric": numeric,
                "loss": loss,
                "tie_break_events": routing["tie_break_events"],
            })
        else:
            records.append({"step": step, "loss": loss, "timing": timing, "recompiles": len(fired)})
        peak = pool if reset else step_peak
        last_tokens = routing["token_count"]
    return {
        "spec": spec,
        "steps": records,
        "guards": guards,
        "final_params": [rnd(value, dp) for value in params],
    }


# ------------------------------------------------------------ gate figures


def after_warmup(spec, records):
    return [item for item in records if item["step"] > spec.warmup_bound]


def within_warmup(spec, records):
    return [item for item in records if item["step"] <= spec.warmup_bound]


def summed_time(records, places):
    acc = 0.0
    for item in records:
        acc = rnd(acc + item["timing"]["step_us"], places)
    return acc


def gate_figures(spec, compiled, baseline):
    """Speedup, budget, memory, drop and parity figures for one configuration."""
    tp, dp = spec.time_decimals, spec.decimals
    walk = compiled["steps"]
    late = after_warmup(spec, walk)
    fast = summed_time(late, tp)
    slow = summed_time(after_warmup(spec, baseline["steps"]), tp)
    lost = sum(item["dropped_tokens"] for item in walk)
    asked = sum(sum(item["demand"]) for item in walk)
    end_loss = walk[-1]["loss"]
    ref_loss = baseline["steps"][-1]["loss"]
    return {
        "compiled_tail_us": fast,
        "eager_tail_us": slow,
        "speedup": rnd(slow / fast, tp) if fast > 0 else 0.0,
        "recompiles_after_warmup": sum(item["recompiles"] for item in late),
        "min_host_headroom_bytes": min(item["host_headroom_bytes"] for item in walk),
        "drop_rate": rnd(float(lost) / float(asked), dp) if asked else 0.0,
        "closing_loss": end_loss,
        "baseline_closing_loss": ref_loss,
        "relative_deviation": rnd(abs(end_loss - ref_loss) / abs(ref_loss), dp) if ref_loss else 0.0,
        "min_capacity_seen": min(min(item["capacity"]) for item in walk),
    }


def warmup_profile(spec, outcome):
    window = within_warmup(spec, outcome["steps"])
    token_values = sorted(set(item["token_count"] for item in window))
    cap_values = sorted(set(size for item in window for size in item["rank_bucket"].values()))
    local_values = sorted(set(len(members) for members in spec.rank_experts.values()))
    needing = [
        dim for dim, values in (("local_experts", local_values), ("tokens", token_values))
        if len(values) >= spec.promotion_threshold
    ]
    return {
        "run_id": spec.run_id,
        "warmup_bound": spec.warmup_bound,
        "window_steps": [item["step"] for item in window],
        "distinct_token_values": token_values,
        "distinct_capacity_values": cap_values,
        "distinct_local_expert_values": local_values,
        "promotion_threshold": spec.promotion_threshold,
        "dims_requiring_dynamic": sorted(needing),
        "warmup_recompiles": sum(item["recompiles"] for item in window),
    }


# ------------------------------------------------------- candidate sweep


def sweep_grid(spec):
    axes = spec.corpus.candidates
    grid = [
        {
            "capacity_factor": float(factor),
            "capacity_bucket": int(bucket),
            "mark_dynamic": sorted(dims),
            "compile_mode": str(mode),
        }
        for factor in axes["capacity_factor"]
        for bucket in axes["capacity_bucket"]
        for dims in axes["mark_dynamic"]
        for mode in axes["compile_mode"]
    ]
    grid.sort(key=lambda c: (c["capacity_factor"], -c["capacity_bucket"], "|".join(c["mark_dynamic"]), c["compile_mode"]))
    return grid


def probe_spec(spec, choice, horizon):
    config = dict(spec.config)
    for name in ("capacity_factor", "capacity_bucket", "compile_mode"):
        config[name] = choice[name]
    config["mark_dynamic"] = list(choice["mark_dynamic"])
    config["steps"] = horizon
    config["reset_steps"] = [mark for mark in spec.reset_steps if mark <= horizon]
    return Spec(config, spec.corpus)


def judge_candidate(spec, choice, horizon, eager_runs):
    """Figures and every violated gate for one sweep candidate."""
    probe = probe_spec(spec, choice, horizon)
    compiled = run(probe, spec.tiebreak_order)
    shape = (choice["capacity_factor"], choice["capacity_bucket"])
    if shape not in eager_runs:
        plain = dict(probe.config)
        plain["compile_mode"] = "eager"
        plain["mark_dynamic"] = []
        eager_runs[shape] = run(Spec(plain, spec.corpus), spec.tiebreak_order, eager=True)
    figures = gate_figures(probe, compiled, eager_runs[shape])
    return figures, broken_gates(spec.corpus, choice["compile_mode"], figures)


def broken_gates(corpus, compile_mode, figures):
    """Every rejection cause the figures of one configuration trigger, sorted by name."""
    checks = (
        ("eager_mode_forbidden", compile_mode == "eager"),
        ("recompile_budget_exceeded",
         figures["recompiles_after_warmup"] > int(corpus.steptime_gates["recompile_budget"])),
        ("speedup_gate_unmet", figures["speedup"] < float(corpus.steptime_gates["min_speedup"])),
        ("memory_ceiling_exceeded", figures["min_host_headroom_bytes"] < 0),
        ("drop_tolerance_exceeded", figures["drop_rate"] > float(corpus.convergence_gates["max_drop_rate"])),
        ("convergence_band_unmet",
         figures["relative_deviation"] > float(corpus.convergence_gates["settlement_parity_band"])),
        ("capacity_below_minimum", figures["min_capacity_seen"] < int(corpus.memory_gates["capacity_floor"])),
    )
    return sorted(name for name, broken in checks if broken)


def _orders(items):
    """Every ordering of items, in lexicographic order of the result."""
    pool = sorted(items)
    if len(pool) <= 1:
        return [list(pool)]
    found = []
    for index, head in enumerate(pool):
        for rest in _orders(pool[:index] + pool[index + 1:]):
            found.append([head] + rest)
    return found


def cause_orders():
    """Cause orders permitted by the shipped partial order."""
    allowed = []
    for order in _orders(REJECTION_CAUSES):
        place = dict((cause, index) for index, cause in enumerate(order))
        if order[0] != "eager_mode_forbidden":
            continue
        if place["capacity_below_minimum"] > place["drop_tolerance_exceeded"]:
            continue
        if place["recompile_budget_exceeded"] > place["speedup_gate_unmet"]:
            continue
        allowed.append(order)
    return sorted(allowed)


def tie_orders():
    return sorted(_orders(TIE_FIELDS))


def run_sweep(spec, horizon):
    eager_runs = {}
    table = []
    for choice in sweep_grid(spec):
        figures, broken = judge_candidate(spec, choice, horizon, eager_runs)
        table.append({"candidate": choice, "summary": figures, "violations": broken})
    return table


def unmarked(profile, choice):
    """Dimensions the warmup window promoted that the candidate leaves static."""
    return sorted(dim for dim in profile["dims_requiring_dynamic"] if dim not in choice["mark_dynamic"])


def first_cause(order, broken):
    for cause in order:
        if cause in broken:
            return cause
    return None


def label_of(choice):
    dims = "+".join(choice["mark_dynamic"]) or "none"
    return "cf=%s|bucket=%d|dynamic=%s|mode=%s" % (
        repr(float(choice["capacity_factor"])), choice["capacity_bucket"], dims, choice["compile_mode"],
    )


def rejection_ledger(table, profile, order):
    tally = dict((cause, 0) for cause in REJECTION_CAUSES)
    rejected, screened, passing = [], [], []
    for row in table:
        label = label_of(row["candidate"])
        missing = unmarked(profile, row["candidate"])
        if missing:
            screened.append({"candidate": label, "unmarked_dims": missing})
        elif not row["violations"]:
            passing.append(label)
        else:
            cause = first_cause(order, row["violations"])
            tally[cause] += 1
            rejected.append({"candidate": label, "cause": cause, "all_violations": row["violations"]})
    return {
        "cause_order": list(order),
        "per_cause_counts": tally,
        "rejected": sorted(rejected, key=lambda item: item["candidate"]),
        "prefiltered": sorted(screened, key=lambda item: item["candidate"]),
        "admissible_candidates": sorted(passing),
    }


def pick_settlement(passing, table):
    """Smallest factor, widest bucket, fewest dynamic dims; then the later compile mode."""
    by_label = dict((label_of(row["candidate"]), row["candidate"]) for row in table)

    def rank(label):
        choice = by_label[label]
        dims = choice["mark_dynamic"]
        return (choice["capacity_factor"], -choice["capacity_bucket"], len(dims), "|".join(dims))

    ordered = sorted(passing, key=rank)
    if not ordered:
        return None
    best = rank(ordered[0])
    tied = [label for label in ordered if rank(label) == best]
    tied.sort(key=lambda label: by_label[label]["compile_mode"], reverse=True)
    return by_label[tied[0]]


# -------------------------------------------------------- sealed decisions


def tie_events(corpus, config, order, horizon):
    spec = Spec(config, corpus)
    found = []
    for step in range(1, horizon + 1):
        found.extend(route(spec, step, order)["tie_break_events"])
    return found


def match_tie_orders(corpus, config_name, config):
    entry = corpus.sealed_tiebreak["digests"][config_name]
    horizon = int(entry["steps"])
    return [order for order in tie_orders() if obj_digest(tie_events(corpus, config, order, horizon)) == entry["digest"]]


def _cause_tally(payload, order):
    tally = dict((cause, 0) for cause in REJECTION_CAUSES)
    for row in payload["rows"]:
        if unmarked(payload["profile"], row["candidate"]) or not row["violations"]:
            continue
        tally[first_cause(order, row["violations"])] += 1
    return tally


def match_cause_orders(rows_by_config, sealed):
    names = sorted(rows_by_config)
    return [
        order for order in cause_orders()
        if all(obj_digest(_cause_tally(rows_by_config[name], order)) == sealed["digests"][name]["digest"] for name in names)
    ]


# ------------------------------------------------------------ record builders


STAGE_RECORDS = tuple(name + ".json" for name in (
    "route_plan", "capacity_plan", "mesh_plan", "dispatch_ledger", "drop_ledger",
    "alltoall_ledger", "guard_key_index", "recompile_report", "graph_break_ledger",
    "cudagraph_report", "host_memory_report", "steptime_report", "warmup_profile",
    "sealed_policy_resolution",
))
REPLAY_RECORDS = tuple(name + ".json" for name in (
    "aux_loss_trace", "loss_curve", "gradient_ledger", "optimizer_trace", "convergence_report",
    "baseline_parity", "settlement_report", "rejection_ledger", "sensitivity",
    "audit_statistics", "deployed_diagnosis", "validation_report",
))


def bind(corpus, config, order):
    spec = Spec(config, corpus)
    spec.tiebreak_order = order
    return spec


def eager_of(spec):
    """The same configuration run eagerly with every dimension static."""
    plain = dict(spec.config, compile_mode="eager", mark_dynamic=[])
    return bind(spec.corpus, plain, spec.tiebreak_order)


def _picked(records, *fields):
    return [dict((field, item[field]) for field in ("step",) + fields) for item in records]


def _rolling(values, places):
    acc = 0.0
    for value in values:
        acc = rnd(acc + value, places)
    return acc


def _ratio(top, bottom, places):
    return rnd(float(top) / float(bottom), places) if bottom else 0.0


def rec_route_plan(spec, outcome):
    walk = outcome["steps"]
    rows = [dict(
        step=item["step"],
        token_count=item["token_count"],
        demand=item["demand"],
        gate_mass_total=rnd(sum(item["aux"]["gate_probabilities"]) * item["token_count"], spec.decimals),
        tie_break_count=len(item["tie_break_events"]),
    ) for item in walk]
    return dict(
        run_id=spec.run_id,
        top_k=spec.top_k,
        tie_break_key=list(spec.tiebreak_order),
        steps=rows,
        tie_break_events=[event for item in walk for event in item["tie_break_events"]],
        total_assignments=sum(sum(item["demand"]) for item in walk),
    )


def rec_capacity_plan(spec, outcome):
    walk = outcome["steps"]
    every = [size for item in walk for size in item["capacity"]]
    rows = []
    for item in walk:
        odd = [e for e, size in enumerate(item["capacity"]) if size % spec.capacity_bucket]
        rows.append(dict(step=item["step"], capacity=item["capacity"], unaligned_experts=odd))
    return dict(
        run_id=spec.run_id,
        capacity_factor=spec.capacity_factor,
        capacity_bucket=spec.capacity_bucket,
        min_capacity=spec.min_capacity,
        steps=rows,
        min_capacity_seen=min(every),
        max_capacity_seen=max(every),
        distinct_capacity_values=sorted(set(every)),
    )


def rec_mesh_plan(spec, outcome):
    walk = outcome["steps"]
    shapes = set(tuple(item["capacity"]) for item in walk)
    return dict(
        run_id=spec.run_id,
        ep_world_size=spec.ep_world_size,
        expert_rank=list(spec.expert_rank),
        rank_experts=dict((str(rank), spec.rank_experts[rank]) for rank in sorted(spec.rank_experts)),
        placement_groups=list(spec.placement_group),
        rank_bucket_by_step=_picked(walk, "rank_bucket"),
        expert_shape_matrix=len(shapes) * len(spec.moe_layer_indices),
    )


def rec_dispatch_ledger(spec, outcome):
    walk = outcome["steps"]
    rows = []
    for item in walk:
        spare = [size - took for size, took in zip(item["capacity"], item["accepted_count"])]
        rows.append(dict(step=item["step"], accepted_count=item["accepted_count"], padded_slots=spare))
    return dict(
        run_id=spec.run_id,
        steps=rows,
        total_accepted=sum(sum(item["accepted_count"]) for item in walk),
        total_padded_slots=sum(sum(row["padded_slots"]) for row in rows),
    )


def rec_drop_ledger(spec, outcome):
    walk = outcome["steps"]
    lost = sum(item["dropped_tokens"] for item in walk)
    asked = sum(sum(item["demand"]) for item in walk)
    return dict(
        run_id=spec.run_id,
        steps=_picked(walk, "dropped_tokens", "dropped_token_mass"),
        dropped_tokens=lost,
        dropped_token_mass=_rolling((item["dropped_token_mass"] for item in walk), spec.decimals),
        drop_rate=_ratio(lost, asked, spec.decimals),
        steps_with_drops=[item["step"] for item in walk if item["dropped_tokens"] > 0],
    )


def rec_alltoall_ledger(spec, outcome):
    width = spec.ep_world_size * len(spec.rank_experts[0])
    rows = []
    for item in outcome["steps"]:
        sizes = list(item["rank_bucket"].values())
        rows.append(dict(
            step=item["step"],
            alltoall_bucket=item["alltoall_bucket"],
            payload_slots=item["alltoall_bucket"] * width,
            rank_bucket_spread=max(sizes) - min(sizes),
        ))
    return dict(
        run_id=spec.run_id,
        ep_world_size=spec.ep_world_size,
        steps=rows,
        uniform_steps=[row["step"] for row in rows if not row["rank_bucket_spread"]],
        total_payload_slots=sum(row["payload_slots"] for row in rows),
    )


def _is_special(key):
    return bool(set(key.split("|")) & set(["0", "1"]))


def rec_guard_key_index(spec, outcome):
    by_slot = {}
    for item in outcome["steps"]:
        for seen in item["keys"]:
            by_slot.setdefault("%s@%d" % (seen["code_object"], seen["rank"]), set()).add(seen["key"])
    listed = dict((slot, sorted(keys)) for slot, keys in by_slot.items())
    special = set(key for keys in by_slot.values() for key in keys if _is_special(key))
    return dict(
        run_id=spec.run_id,
        keys_by_slot=listed,
        distinct_key_count=sum(len(keys) for keys in listed.values()),
        specialized_zero_one_keys=sorted(special),
        dynamic_dims_final=sorted(pair[1] for pair, flag in outcome["guards"].promoted.items() if flag),
    )


def over_budget_step(spec, outcome):
    """First gated step whose running recompilation count passes the budget."""
    allowance = int(spec.corpus.steptime_gates["recompile_budget"])
    tally = 0
    for item in after_warmup(spec, outcome["steps"]):
        tally += item["recompiles"]
        if tally > allowance:
            return item["step"]
    return None


def rec_recompile_report(spec, outcome):
    walk = outcome["steps"]
    fields = ("step", "code_object", "rank", "guard_key", "guard_delta", "evicted_key")
    fired = [dict((field, event[field]) for field in fields) for item in walk for event in item["events"]]
    return dict(
        run_id=spec.run_id,
        warmup_bound=spec.warmup_bound,
        recompile_events=fired,
        total_recompiles=len(fired),
        recompiles_after_warmup=sum(item["recompiles"] for item in after_warmup(spec, walk)),
        first_step_over_budget=over_budget_step(spec, outcome),
        evictions=len([event for event in fired if event["evicted_key"] is not None]),
        recompiles_by_step=[dict(step=item["step"], count=item["recompiles"]) for item in walk if item["recompiles"]],
    )


def rec_graph_break_ledger(spec, outcome):
    walk = outcome["steps"]
    tally = dict.fromkeys(BREAK_ORDER, 0)
    for item in walk:
        for cause in item["breaks"]:
            tally[cause] += 1
    return dict(
        run_id=spec.run_id,
        cause_order=list(BREAK_ORDER),
        per_cause_counts=tally,
        steps=[dict(step=item["step"], causes=item["breaks"]) for item in walk],
        total_breaks=sum(tally.values()),
        clean_steps=[item["step"] for item in walk if not item["breaks"]],
    )


def _failure_tally(outcome):
    tally = {}
    for item in outcome["steps"]:
        for attempt in item["captures"]:
            if not attempt["captured"]:
                tally[attempt["cause"]] = tally.get(attempt["cause"], 0) + 1
    return tally


def rec_cudagraph_report(spec, outcome):
    walk = outcome["steps"]
    rows = []
    for item in walk:
        good = len([attempt for attempt in item["captures"] if attempt["captured"]])
        rows.append(dict(
            step=item["step"], captured=good,
            pool_bytes=item["pool_bytes"], pool_peak_bytes=item["pool_peak_bytes"],
        ))
    return dict(
        run_id=spec.run_id,
        compile_mode=spec.compile_mode,
        capture_attempts=sum(len(item["captures"]) for item in walk),
        captures=sum(row["captured"] for row in rows),
        failure_causes=_failure_tally(outcome),
        steps=rows,
        final_pool_peak_bytes=walk[-1]["pool_peak_bytes"],
        reset_steps=list(spec.reset_steps),
    )


def rec_host_memory_report(spec, outcome):
    rows = _picked(outcome["steps"], "cache_entries", "guard_closures", "host_bytes", "host_headroom_bytes")
    over = [row["step"] for row in rows if row["host_headroom_bytes"] < 0]
    return dict(
        run_id=spec.run_id,
        host_ceiling_bytes=int(spec.corpus.memory_gates["host_ceiling_bytes"]),
        steps=rows,
        min_host_headroom_bytes=min(row["host_headroom_bytes"] for row in rows),
        peak_host_bytes=max(row["host_bytes"] for row in rows),
        steps_over_ceiling=over,
        memory_gate_met=not over,
    )


_TIMING_PARTS = ("compile_us", "capture_us", "compute_us", "alltoall_us", "bubble_us", "step_us")


def rec_steptime_report(spec, compiled, baseline):
    tp = spec.time_decimals
    rows = []
    for item, plain in zip(compiled["steps"], baseline["steps"]):
        row = dict((part, item["timing"][part]) for part in _TIMING_PARTS)
        row.update(step=item["step"], eager_step_us=plain["timing"]["step_us"])
        rows.append(row)
    late = after_warmup(spec, compiled["steps"])
    fast = summed_time(late, tp)
    slow = summed_time(after_warmup(spec, baseline["steps"]), tp)
    ratio = rnd(slow / fast, tp) if fast else 0.0
    floor = float(spec.corpus.steptime_gates["min_speedup"])
    compile_sum = _rolling((item["timing"]["compile_us"] for item in compiled["steps"]), tp)
    return dict(
        run_id=spec.run_id,
        steps=rows,
        gated_step_range=[spec.warmup_bound + 1, spec.steps],
        compiled_tail_us=fast,
        eager_tail_us=slow,
        speedup=ratio,
        min_speedup=floor,
        speedup_gate_met=ratio >= floor,
        amortized_compile_us=rnd(compile_sum / float(max(1, len(late))), tp),
    )


def rec_aux_loss_trace(spec, outcome):
    walk = outcome["steps"]
    rows = []
    for item in walk:
        row = dict(step=item["step"])
        for field in ("aux_loss", "load_dispersion", "expert_utilization", "empty_experts"):
            row[field] = item["aux"][field]
        rows.append(row)
    spreads = [row["load_dispersion"] for row in rows if row["load_dispersion"] is not None]
    return dict(
        run_id=spec.run_id,
        aux_loss_weight=spec.aux_loss_weight,
        steps=rows,
        aux_loss_total=_rolling((row["aux_loss"] for row in rows), spec.decimals),
        steps_with_empty_experts=[row["step"] for row in rows if row["empty_experts"]],
        mean_load_dispersion=rnd(sum(spreads) / float(len(spreads)), spec.decimals) if spreads else None,
    )


def rec_loss_curve(spec, compiled, baseline):
    rows = [dict(
        step=item["step"],
        loss=item["loss"],
        eager_loss=plain["loss"],
        signed_gap=rnd(item["loss"] - plain["loss"], spec.decimals),
    ) for item, plain in zip(compiled["steps"], baseline["steps"])]
    first = rows[0]["loss"]
    return dict(
        run_id=spec.run_id,
        steps=rows,
        closing_loss=rows[-1]["loss"],
        opening_loss=first,
        minimum_loss=min(row["loss"] for row in rows),
        steps_above_opening=[row["step"] for row in rows if row["loss"] > first],
    )


def rec_gradient_ledger(spec, outcome):
    walk = outcome["steps"]
    rows = []
    for item in walk:
        row = dict(step=item["step"])
        for field in ("expert_partials", "expert_outputs", "gradients", "step_signal"):
            row[field] = item["numeric"][field]
        rows.append(row)
    return dict(
        run_id=spec.run_id,
        steps=rows,
        folded_signal=_rolling((row["step_signal"] for row in rows), spec.decimals),
        final_params=outcome["final_params"],
        accumulation_order=["slot_ascending", "expert_index_ascending"],
    )


def rec_optimizer_trace(spec, outcome):
    rows = []
    for item in outcome["steps"]:
        row = dict(step=item["step"])
        for field in ("scaled_norm", "clip_reference", "clip_factor", "clipped"):
            row[field] = item["numeric"][field]
        rows.append(row)
    hit = [row["step"] for row in rows if row["clipped"]]
    return dict(
        run_id=spec.run_id,
        loss_scale=spec.loss_scale,
        clip_threshold=spec.clip_threshold,
        learning_rate=spec.learning_rate,
        steps=rows,
        clipped_steps=hit,
        clipped_step_count=len(hit),
    )


def rec_convergence_report(spec, compiled, baseline):
    gates = spec.corpus.convergence_gates
    dp = spec.decimals
    curve = [item["loss"] for item in compiled["steps"]]
    span = int(gates["slope_window"])
    if span > 1 and len(curve) >= span:
        slope = rnd((curve[-1] - curve[-span]) / float(span - 1), dp)
    else:
        slope = rnd(curve[-1] - curve[0], dp)
    end_loss = curve[-1]
    ref_loss = baseline["steps"][-1]["loss"]
    gap = rnd(abs(end_loss - ref_loss) / abs(ref_loss), dp) if ref_loss else 0.0
    band = float(gates["parity_band"])
    target = float(gates["target_loss"])
    inside = gap <= band
    good = inside and slope <= float(gates["max_slope"]) and end_loss <= target
    return dict(
        run_id=spec.run_id,
        slope_window=span,
        windowed_slope=slope,
        closing_loss=end_loss,
        baseline_closing_loss=ref_loss,
        relative_deviation=gap,
        parity_band=band,
        parity_holds=inside,
        target_loss=target,
        verdict="met" if good else "unmet",
    )


def rec_baseline_parity(spec, compiled, baseline):
    dp = spec.decimals
    band = float(spec.corpus.convergence_gates["parity_band"])
    rows = []
    top, top_step = 0.0, None
    for item, plain in zip(compiled["steps"], baseline["steps"]):
        ref = plain["loss"]
        gap = 0.0 if ref == 0.0 else rnd(abs(item["loss"] - ref) / abs(ref), dp)
        rows.append(dict(step=item["step"], relative_deviation=gap))
        if gap > top:
            top, top_step = gap, item["step"]
    return dict(
        run_id=spec.run_id,
        steps=rows,
        max_relative_deviation=rnd(top, dp),
        max_deviation_step=top_step,
        parity_band=band,
        parity_holds=top <= band,
        steps_outside_band=[row["step"] for row in rows if row["relative_deviation"] > band],
    )


def _break_step_count(outcome, keep):
    return len([item for item in outcome["steps"] if item["breaks"] and keep(item["step"])])


def _slot_keys(outcome, router_side):
    found = set()
    for item in outcome["steps"]:
        for seen in item["keys"]:
            if (seen["code_object"] == "router") is router_side:
                found.add("%s@%d#%s" % (seen["code_object"], seen["rank"], seen["key"]))
    return len(found)


def _attempts(outcome, want_success):
    flags = [attempt["captured"] for item in outcome["steps"] for attempt in item["captures"]]
    return len([flag for flag in flags if flag is want_success]), len(flags)


def rec_audit_statistics(spec, deployed, settled, settled_spec):
    """Seventeen statistics whose definitions deliberately differ per side."""
    dp = spec.decimals
    old, new = deployed["steps"], settled["steps"]
    failed, tried_old = _attempts(deployed, False)
    passed, tried_new = _attempts(settled, True)
    stats = dict(
        deployed_recompiles_total=sum(item["recompiles"] for item in old),
        settled_recompiles_after_warmup=sum(item["recompiles"] for item in after_warmup(settled_spec, new)),
        deployed_distinct_capacity_values=len(set(size for item in old for size in item["capacity"])),
        settled_distinct_rank_buckets=len(set(size for item in new for size in item["rank_bucket"].values())),
        deployed_drop_rate_assignment_denominator=_ratio(
            sum(item["dropped_tokens"] for item in old), sum(sum(item["demand"]) for item in old), dp),
        settled_drop_rate_token_denominator=_ratio(
            sum(item["dropped_tokens"] for item in new), sum(item["token_count"] for item in new), dp),
        deployed_break_steps_inclusive_warmup=_break_step_count(deployed, lambda s: s <= spec.warmup_bound),
        settled_break_steps_exclusive_warmup=_break_step_count(settled, lambda s: s > settled_spec.warmup_bound),
        deployed_mean_host_bytes=rnd(sum(item["host_bytes"] for item in old) / float(len(old)), dp),
        settled_peak_host_bytes=max(item["host_bytes"] for item in new),
        deployed_capture_failure_ratio=_ratio(failed, tried_old, dp),
        settled_capture_success_ratio=_ratio(passed, tried_new, dp),
        deployed_empty_expert_step_count=len([item for item in old if item["aux"]["empty_experts"]]),
        settled_empty_expert_slot_count=sum(len(item["aux"]["empty_experts"]) for item in new),
        deployed_unique_guard_keys_router_only=_slot_keys(deployed, True),
        settled_unique_guard_keys_moe_only=_slot_keys(settled, False),
        deployed_token_total=sum(item["token_count"] for item in old),
    )
    return stats


def _departs(rule, value):
    if "allowed_values" in rule:
        return value not in rule["allowed_values"]
    return not (float(rule["minimum"]) <= float(value) <= float(rule["maximum"]))


def rec_deployed_diagnosis(spec, outcome, baseline, bounds, register):
    dp = spec.decimals
    claimed = spec.corpus.deployed_summary["published"]
    figures = gate_figures(spec, outcome, baseline)
    ours = dict((field, figures[field]) for field in (
        "closing_loss", "speedup", "recompiles_after_warmup", "min_host_headroom_bytes", "drop_rate"))
    ours["total_recompiles"] = sum(item["recompiles"] for item in outcome["steps"])
    side_by_side = {}
    for field in sorted(set(ours) & set(claimed)):
        side_by_side[field] = dict(
            published=claimed[field],
            replayed=ours[field],
            signed_delta=rnd(float(claimed[field]) - float(ours[field]), dp),
        )
    off_contract = []
    for setting in sorted(bounds["settings"]):
        rule = bounds["settings"][setting]
        value = spec.config.get(setting)
        governing = policy_in_force(register, rule["policy"])
        if _departs(rule, value):
            off_contract.append(dict(setting=setting, value=value, policy=rule["policy"], revision=governing["revision"]))
    return dict(
        run_id=spec.run_id,
        published_vs_replayed=side_by_side,
        departing_settings=off_contract,
        capture_failure_causes=_failure_tally(outcome),
        first_step_over_budget=over_budget_step(spec, outcome),
        admissible=not off_contract and not broken_gates(spec.corpus, spec.compile_mode, figures),
        published_agrees_with_replay=all(entry["signed_delta"] == 0.0 for entry in side_by_side.values()),
    )


_SETTLED_FIELDS = ("capacity_factor", "capacity_bucket", "mark_dynamic", "compile_mode")


def rec_settlement_report(gates_spec, deployed_spec, settled, settled_spec, baseline, ledger, horizon, table):
    corpus = gates_spec.corpus
    figures = gate_figures(settled_spec, settled, baseline)
    moved = []
    for field in _SETTLED_FIELDS:
        was, now = deployed_spec.config[field], settled_spec.config[field]
        if was != now:
            moved.append({"setting": field, "from": was, "to": now})
    return dict(
        run_id=deployed_spec.run_id,
        probe_steps=horizon,
        candidates_evaluated=len(table),
        prefiltered_count=len(ledger["prefiltered"]),
        rejected_count=len(ledger["rejected"]),
        admissible_count=len(ledger["admissible_candidates"]),
        settled_configuration=dict(
            capacity_factor=settled_spec.capacity_factor,
            capacity_bucket=settled_spec.capacity_bucket,
            mark_dynamic=list(settled_spec.mark_dynamic),
            compile_mode=settled_spec.compile_mode,
        ),
        settled_gate_figures=figures,
        changed_settings=moved,
        gates_met=dict(
            recompile_budget=figures["recompiles_after_warmup"] <= int(corpus.steptime_gates["recompile_budget"]),
            speedup=figures["speedup"] >= float(corpus.steptime_gates["min_speedup"]),
            memory=figures["min_host_headroom_bytes"] >= 0,
            convergence=figures["relative_deviation"] <= float(corpus.convergence_gates["parity_band"]),
        ),
    )


def rec_sensitivity(gates_spec, base_spec, horizon, order):
    """Margins against each gate when one setting moves by its listed delta."""
    corpus = gates_spec.corpus
    gates = corpus.steptime_gates
    eager_runs = {}
    rows = []
    for nudge in corpus.candidates["perturbations"]:
        field = nudge["setting"]
        config = dict(base_spec.config)
        current = base_spec.config[field]
        if field == "capacity_factor":
            config[field] = rnd(float(current) + float(nudge["delta"]), gates_spec.decimals)
        elif isinstance(current, int):
            config[field] = current + nudge["delta"]
        config["steps"] = horizon
        config["reset_steps"] = [mark for mark in base_spec.reset_steps if mark <= horizon]
        probe = bind(corpus, config, order)
        compiled = run(probe, order)
        shape = (probe.capacity_factor, probe.capacity_bucket)
        if shape not in eager_runs:
            eager_runs[shape] = run(eager_of(probe), order, eager=True)
        figures = gate_figures(probe, compiled, eager_runs[shape])
        rows.append(dict(
            setting=field,
            delta=nudge["delta"],
            speedup_margin=rnd(figures["speedup"] - float(gates["min_speedup"]), gates_spec.time_decimals),
            headroom_margin=figures["min_host_headroom_bytes"],
            recompile_margin=int(gates["recompile_budget"]) - figures["recompiles_after_warmup"],
        ))
    rows.sort(key=lambda row: (row["setting"], row["delta"]))
    return dict(
        run_id=base_spec.run_id,
        probe_steps=horizon,
        perturbations=rows,
        negative_speedup_margins=[row["setting"] for row in rows if row["speedup_margin"] < 0],
        negative_headroom_margins=[row["setting"] for row in rows if row["headroom_margin"] < 0],
    )


def _record_size(payload):
    if not isinstance(payload, dict):
        return 0
    if isinstance(payload.get("steps"), list):
        return len(payload["steps"])
    return len(payload)


def rec_validation_report(spec, records, outcome, baseline):
    dp = spec.decimals
    figures = gate_figures(spec, outcome, baseline)
    claimed = spec.corpus.deployed_summary["published"]
    gaps = dict(
        (field, rnd(float(claimed[field]) - float(figures[field]), dp))
        for field in sorted(claimed) if field in figures
    )
    worst = max([abs(value) for value in gaps.values()] or [0.0])
    return dict(
        residuals=gaps,
        record_counts=dict((name, _record_size(records[name])) for name in sorted(records)),
        max_absolute_residual=rnd(worst, dp),
        artifact_count=len(records),
        float_decimals=spec.decimals,
        time_decimals=spec.time_decimals,
    )


# ------------------------------------------------------- inline documents


def corpus_of(document):
    """A corpus whose tables arrive inside a document instead of a directory."""
    shell = Corpus.__new__(Corpus)
    shell.base = None
    tables = document["tables"]
    for attribute, filename in CORPUS_LAYOUT:
        setattr(shell, attribute, tables[filename])
    shell.decimals = int(shell.tolerances["float_decimals"])
    shell.time_decimals = int(shell.tolerances["time_decimals"])
    return shell


def sealed_run_config(corpus, name):
    return corpus.calibration_config if name == "calibration" else corpus.probes[name]


# ------------------------------------------------------- policy resolution


def settle_tie_order(corpus):
    """Orders that reproduce every sealed tie break digest; the first wins."""
    common = None
    for name in sorted(corpus.sealed_tiebreak["digests"]):
        hits = set(tuple(order) for order in match_tie_orders(corpus, name, sealed_run_config(corpus, name)))
        common = hits if common is None else common.intersection(hits)
    if not common:
        raise SystemExit("no tie break key reproduces the sealed digests in sealed_tiebreak_digests.json for configurations " + ", ".join(sorted(corpus.sealed_tiebreak["digests"])))
    return list(min(common)), len(common)


def settle_policies(corpus):
    order, tie_hits = settle_tie_order(corpus)
    horizon = int(corpus.candidates["probe_steps"])
    payloads = {}
    for name in sorted(corpus.sealed_precedence["digests"]):
        spec = bind(corpus, sealed_run_config(corpus, name), order)
        payloads[name] = {
            "profile": warmup_profile(spec, run(spec, order)),
            "rows": run_sweep(spec, horizon),
        }
    survivors = match_cause_orders(payloads, corpus.sealed_precedence)
    if not survivors:
        raise SystemExit("no precedence order reproduces the sealed digests in sealed_precedence_digests.json for configurations " + ", ".join(sorted(corpus.sealed_precedence["digests"])))
    return dict(
        tie_break_key=order,
        tie_break_matches=tie_hits,
        tie_break_candidates_enumerated=len(tie_orders()),
        precedence_order=survivors[0],
        precedence_matches=len(survivors),
        precedence_candidates_enumerated=len(cause_orders()),
        sealed_configs=sorted(corpus.sealed_precedence["digests"]),
    )


# ------------------------------------------------------------ full build


def settled_config_from(corpus, choice):
    config = dict(corpus.deployed_config)
    for field in _SETTLED_FIELDS:
        config[field] = choice[field]
    config["mark_dynamic"] = list(choice["mark_dynamic"])
    config["run_id"] = "%s-settled" % corpus.deployed_config["run_id"]
    return config


def assemble(corpus):
    """Every stage and replay record for one corpus, keyed by file name."""
    resolution = settle_policies(corpus)
    order = resolution["tie_break_key"]
    horizon = int(corpus.candidates["probe_steps"])

    live_spec = bind(corpus, corpus.deployed_config, order)
    live = run(live_spec, order)
    live_eager = run(eager_of(live_spec), order, eager=True)
    profile = warmup_profile(live_spec, live)
    table = run_sweep(live_spec, horizon)
    ledger = rejection_ledger(table, profile, resolution["precedence_order"])
    choice = pick_settlement(ledger["admissible_candidates"], table)
    if choice is None:
        raise SystemExit("no admissible candidate survives the shipped gates among the " + str(len(table)) + " candidates swept from capacity_candidates.json")

    fixed_spec = bind(corpus, settled_config_from(corpus, choice), order)
    fixed = run(fixed_spec, order)
    fixed_eager = run(eager_of(fixed_spec), order, eager=True)

    out = {}
    for name, maker in (
        ("route_plan", rec_route_plan), ("capacity_plan", rec_capacity_plan), ("mesh_plan", rec_mesh_plan),
        ("dispatch_ledger", rec_dispatch_ledger), ("drop_ledger", rec_drop_ledger),
        ("alltoall_ledger", rec_alltoall_ledger), ("guard_key_index", rec_guard_key_index),
        ("recompile_report", rec_recompile_report), ("graph_break_ledger", rec_graph_break_ledger),
        ("cudagraph_report", rec_cudagraph_report), ("host_memory_report", rec_host_memory_report),
    ):
        out[name + ".json"] = maker(live_spec, live)
    out["steptime_report.json"] = rec_steptime_report(live_spec, live, live_eager)
    out["warmup_profile.json"] = profile
    out["sealed_policy_resolution.json"] = resolution

    for name, maker in (
        ("aux_loss_trace", rec_aux_loss_trace), ("gradient_ledger", rec_gradient_ledger),
        ("optimizer_trace", rec_optimizer_trace),
    ):
        out[name + ".json"] = maker(fixed_spec, fixed)
    for name, maker in (
        ("loss_curve", rec_loss_curve), ("convergence_report", rec_convergence_report),
        ("baseline_parity", rec_baseline_parity),
    ):
        out[name + ".json"] = maker(fixed_spec, fixed, fixed_eager)
    out["settlement_report.json"] = rec_settlement_report(
        live_spec, live_spec, fixed, fixed_spec, fixed_eager, ledger, horizon, table)
    out["rejection_ledger.json"] = ledger
    out["sensitivity.json"] = rec_sensitivity(live_spec, fixed_spec, horizon, order)
    out["audit_statistics.json"] = rec_audit_statistics(live_spec, live, fixed, fixed_spec)
    out["deployed_diagnosis.json"] = rec_deployed_diagnosis(
        live_spec, live, live_eager, corpus.bounds, corpus.revisions)
    out["validation_report.json"] = rec_validation_report(live_spec, out, live, live_eager)
    return out


def _write_stage(folder, names, records):
    return dict((name, dump(os.path.join(folder, name), records[name])) for name in names)


def _write_blob(path, blob):
    with open(path, "wb") as sink:
        sink.write(blob)


def build(data_dir, out_dir):
    records = assemble(Corpus(data_dir))
    os.makedirs(out_dir, exist_ok=True)
    first = encode({
        "stage": "dispatch_and_compile",
        "artifact_count": len(STAGE_RECORDS),
        "artifact_sha256": _write_stage(out_dir, STAGE_RECORDS, records),
    })
    _write_blob(os.path.join(out_dir, "stage_manifest.json"), first)
    second = encode({
        "stage": "replay_and_settlement",
        "artifact_count": len(REPLAY_RECORDS),
        "artifact_sha256": _write_stage(out_dir, REPLAY_RECORDS, records),
        "stage_manifest_sha256": sha_hex(first),
    })
    _write_blob(os.path.join(out_dir, "replay_manifest.json"), second)
    settled = records["settlement_report.json"]["settled_configuration"]
    salt = obj_digest(settled)
    chain = {"replay": sha_hex(second), "salt": salt, "stage": sha_hex(first)}
    verdict = records["convergence_report.json"]
    policies = records["sealed_policy_resolution.json"]
    dump(os.path.join(out_dir, "final_state.json"), dict(
        closing_loss=verdict["closing_loss"],
        convergence_verdict=verdict["verdict"],
        deployed_admissible=records["deployed_diagnosis.json"]["admissible"],
        digest_of_digests=obj_digest(chain),
        first_step_over_budget=records["recompile_report.json"]["first_step_over_budget"],
        precedence_order=policies["precedence_order"],
        replay_manifest_sha256=chain["replay"],
        settled_configuration=settled,
        settlement_salt=salt,
        speedup=records["settlement_report.json"]["settled_gate_figures"]["speedup"],
        stage_manifest_sha256=chain["stage"],
        tie_break_key=policies["tie_break_key"],
        total_artifacts=len(STAGE_RECORDS) + len(REPLAY_RECORDS) + 3,
    ))
    return records


# ------------------------------------------------------------- verbs


def _bound_document(document, policies=False):
    corpus = corpus_of(document)
    if policies:
        resolution = settle_policies(corpus)
        order = resolution["tie_break_key"]
    else:
        order, hits = settle_tie_order(corpus)
        resolution = {"tie_break_key": order, "tie_break_matches": hits}
    return corpus, bind(corpus, document["config"], order), resolution


def do_trace(document):
    _, spec, found = _bound_document(document)
    outcome = run(spec, spec.tiebreak_order)
    reply = dict(found)
    for name, maker in (
        ("guard_key_index", rec_guard_key_index), ("recompile_report", rec_recompile_report),
        ("graph_break_ledger", rec_graph_break_ledger), ("cudagraph_report", rec_cudagraph_report),
        ("capacity_plan", rec_capacity_plan), ("mesh_plan", rec_mesh_plan),
        ("host_memory_report", rec_host_memory_report), ("warmup_profile", warmup_profile),
    ):
        reply[name] = maker(spec, outcome)
    return reply


def do_replay(document):
    _, spec, found = _bound_document(document)
    outcome = run(spec, spec.tiebreak_order)
    plain = run(eager_of(spec), spec.tiebreak_order, eager=True)
    reply = dict(found)
    for name, maker in (
        ("route_plan", rec_route_plan), ("dispatch_ledger", rec_dispatch_ledger),
        ("drop_ledger", rec_drop_ledger), ("alltoall_ledger", rec_alltoall_ledger),
        ("aux_loss_trace", rec_aux_loss_trace), ("gradient_ledger", rec_gradient_ledger),
        ("optimizer_trace", rec_optimizer_trace),
    ):
        reply[name] = maker(spec, outcome)
    for name, maker in (
        ("loss_curve", rec_loss_curve), ("convergence_report", rec_convergence_report),
        ("baseline_parity", rec_baseline_parity), ("steptime_report", rec_steptime_report),
    ):
        reply[name] = maker(spec, outcome, plain)
    return reply


def do_settle(document):
    corpus, spec, resolution = _bound_document(document, policies=True)
    horizon = int(corpus.candidates["probe_steps"])
    profile = warmup_profile(spec, run(spec, spec.tiebreak_order))
    table = run_sweep(spec, horizon)
    ledger = rejection_ledger(table, profile, resolution["precedence_order"])
    return dict(
        rejection_ledger=ledger,
        warmup_profile=profile,
        settled_configuration=pick_settlement(ledger["admissible_candidates"], table),
        probe_steps=horizon,
    )


def do_resolve(document):
    return settle_policies(corpus_of(document))


VERBS = {"trace": do_trace, "replay": do_replay, "settle": do_settle, "resolve": do_resolve}


def _summary_line(records):
    settled = records["settlement_report.json"]
    chosen = settled["settled_configuration"]
    return "settled cf=%s bucket=%s dynamic=%s mode=%s speedup=%s closing_loss=%s\n" % (
        chosen["capacity_factor"], chosen["capacity_bucket"], "+".join(chosen["mark_dynamic"]) or "none",
        chosen["compile_mode"], settled["settled_gate_figures"]["speedup"],
        records["convergence_report.json"]["closing_loss"],
    )


def main(argv):
    if len(argv) < 2:
        raise SystemExit("usage: moeplan build DATA_DIR OUT_DIR | trace|replay|settle|resolve DOCUMENT; got arguments " + repr(argv[1:]))
    verb, rest = argv[1], argv[2:]
    if verb == "build":
        if len(rest) != 2:
            raise SystemExit("usage: moeplan build DATA_DIR OUT_DIR; got arguments " + repr(rest))
        sys.stdout.write(_summary_line(build(rest[0], rest[1])))
        return 0
    handler = VERBS.get(verb)
    if handler is None:
        raise SystemExit("unknown verb %r; expected one of build, trace, replay, settle, resolve" % verb)
    if len(rest) != 1:
        raise SystemExit("usage: moeplan %s DOCUMENT; got arguments %r" % (verb, rest))
    sys.stdout.write(encode(handler(load_json(rest[0]))).decode("utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
