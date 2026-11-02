"""Seeded configuration context for the cli-config archetype.

defaults.json, config_schema.json, env_overrides.json and the sample profiles
are templates. This writes the two files that make the final values
impossible to reach without every other input:

  validation_rules.json  bounds and allowed modes that decide which journal ops apply
  change_journal.jsonl   ~21,000 seq-numbered set operations across environments;
                         the effective config is defaults + the valid base ops in
                         seq order, each profile adds its sample/env deltas and then
                         its own valid ops
"""

from __future__ import annotations

import json
import random
from pathlib import Path

ENVS = ["base", "dev", "prod", "staging", "qa"]
MODES = ["strict-local", "batch-local", "audit-local"]
BAD_KEYS = ["max_record", "TIMEOUT_MS", "debug", "cache_dir", "retry", "profile", "trailer", "checksum"]
ACTORS = ["ops-bot", "a.ng", "r.okafor", "deploy-pipeline", "m.patel", "s.rivera", "change-advisory"]


def generate(data_dir: Path, seed: int, subs: dict[str, str]) -> None:
    rng = random.Random(seed)
    base = {
        "max_records": int(subs["{{CLI_MAX_RECORDS_BASE}}"]),
        "retry_limit": int(subs["{{CLI_RETRY_LIMIT_BASE}}"]),
        "timeout_ms": int(subs["{{CLI_TIMEOUT_MS_BASE}}"]),
    }
    bounds = {
        "max_records": [max(1, base["max_records"] - 40), base["max_records"] + 4000],
        "retry_limit": [0, 12],
        "timeout_ms": [250, base["timeout_ms"] + 20000],
    }
    rules = json.loads((data_dir / "validation_rules.json").read_text(encoding="utf-8"))
    rules["bounds"] = bounds
    rules["allowed_modes"] = MODES
    rules["journal_envs"] = ["base", *rules["profiles"]]
    (data_dir / "validation_rules.json").write_text(json.dumps(rules, indent=2) + "\n", encoding="utf-8")

    seqs = rng.sample(range(100000, 999999), 21000)
    lines = []
    for seq in seqs:
        env = rng.choices(ENVS, weights=[4, 3, 3, 2, 1])[0]
        roll = rng.random()
        if roll < 0.06:
            key, value = rng.choice(BAD_KEYS), rng.randint(1, 99)
        elif roll < 0.30:
            key = "mode"
            value = rng.choice(MODES) if rng.random() < 0.8 else rng.choice(["fast-remote", "STRICT-LOCAL", ""])
        else:
            key = rng.choice(list(bounds))
            low, high = bounds[key]
            value = rng.randint(low, high) if rng.random() < 0.85 else rng.choice([low - rng.randint(1, 50), high + rng.randint(1, 500)])
            if rng.random() < 0.02:
                value = str(value)
        lines.append(json.dumps({"seq": seq, "env": env, "key": key, "value": value,
                                 "actor": rng.choice(ACTORS), "ticket": f"CHG-{rng.randint(1000, 99999)}"},
                                separators=(",", ":")))
    (data_dir / "change_journal.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
