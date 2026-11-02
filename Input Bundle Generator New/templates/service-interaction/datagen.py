"""Seeded operation history for the service-interaction archetype.

The simulator, client, contract, seed config, scenarios, schema and channel
policy are templates. This writes the history the run must be derived from:

  request_log.jsonl  ~21,000 recorded requests (seq, channel, action, key, amount,
                     idempotency_key, approval)
  approvals.csv      approval_id -> status; only `approved` requests replay

The replay plan needs request_log + approvals + auth_policy (allowed channels);
the closing bonuses need seed_config; final_state keys come from expected_schema
(seeded extras); the scenario files need scenarios.json.
"""

from __future__ import annotations

import csv
import io
import json
import random
from pathlib import Path

CHANNELS = ["cli", "api", "grpc", "batch"]
APPROVERS = ["n.okafor", "r.patel", "change-board", "s.rivera", "auto-approver", "m.ito"]


def generate(data_dir: Path, seed: int, subs: dict[str, str]) -> None:
    rng = random.Random(seed)
    stale = data_dir / "sample_requests.jsonl"
    if stale.exists():
        stale.unlink()

    schema_path = data_dir / "expected_schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    extras = rng.sample(["localhost_port", "alpha_bonus", "beta_bonus"], rng.randint(1, 2))
    schema["final_state_required"] = sorted(set(schema["final_state_required"]) | set(extras))
    schema_path.write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")

    approvals: list[list[str]] = []
    used: set[str] = set()
    while len(approvals) < 2400:
        ident = f"AP-{rng.randrange(16**6):06X}"
        if ident in used:
            continue
        used.add(ident)
        status = "approved" if len(approvals) < 46 else rng.choice(["rejected", "expired", "pending", "withdrawn"])
        approvals.append([ident, status, rng.choice(APPROVERS), f"2026-{rng.randint(1, 9):02d}-{rng.randint(1, 28):02d}"])
    approved = [row[0] for row in approvals if row[1] == "approved"]
    others = [row[0] for row in approvals if row[1] != "approved"]
    rng.shuffle(approvals)
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(["approval_id", "status", "approver", "decided_on"])
    writer.writerows(approvals)
    (data_dir / "approvals.csv").write_text(buf.getvalue(), encoding="utf-8")

    def amount_for(action: str, key: str) -> int:
        if action == "multiply":
            return rng.choice([2, 3])
        if key == "mode_code":
            return rng.randint(1, 99)
        return rng.randint(-40, 90)

    requests = []
    for index, approval in enumerate(approved):
        channel = ["cli", "api"][index % 2] if index < 30 else rng.choice(CHANNELS)
        key = rng.choice(["alpha", "beta", "mode_code"]) if index >= 4 else ["alpha", "beta", "alpha", "mode_code"][index]
        action = ("set" if key == "mode_code" else rng.choices(["add", "multiply"], weights=[5, 1])[0])
        if index >= 40:
            action, key = rng.choice([("delete", "alpha"), ("add", "gamma"), ("reset", "beta")])
        idem = f"ik-{rng.randrange(16**8):08x}"
        for copy in range(rng.choice([1, 1, 2, 3])):
            requests.append({"channel": channel, "action": action, "key": key, "amount": amount_for(action, key),
                             "idempotency_key": idem, "approval": approval})
    while len(requests) < 21000:
        action = rng.choice(["add", "multiply", "set", "delete"])
        key = rng.choice(["alpha", "beta", "mode_code", "gamma"])
        requests.append({"channel": rng.choice(CHANNELS), "action": action, "key": key,
                         "amount": amount_for(action, key), "idempotency_key": f"ik-{rng.randrange(16**8):08x}",
                         "approval": rng.choice(others) if rng.random() < 0.7 else None})
    seqs = rng.sample(range(10_000, 999_999), len(requests))
    lines = []
    for seq, request in zip(seqs, requests):
        lines.append(json.dumps({"seq": seq, "request_id": f"rq-{seq:06d}", **request}, separators=(",", ":")))
    rng.shuffle(lines)
    (data_dir / "request_log.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
