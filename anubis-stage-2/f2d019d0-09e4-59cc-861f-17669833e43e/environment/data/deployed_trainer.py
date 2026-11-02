"""Deployed mixture of experts training orchestrator for run 7734.

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
    sys.stdout.write("recompiles %d host %d\n" % (recompiles, host))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
