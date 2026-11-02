#!/usr/bin/env python3
"""Rebuild the optimizer step ledger of a sharded training run and publish the
nine audit reports described by the run contract.

Usage: optimize.py --data <archive directory> --out <output directory>
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

MICRO_KEYS = frozenset(
    {
        "record",
        "sequence",
        "owner",
        "shard",
        "pass_index",
        "examples",
        "loss_scale",
        "overflow",
    }
)
MARKER_KEYS = frozenset({"record", "sequence", "kind", "phase"})

REASON_ORDER = (
    "duplicate_sequence",
    "unknown_field",
    "unknown_shard",
    "retired_shard",
    "empty_shard",
    "unknown_owner",
    "owner_excluded",
    "owner_mismatch",
    "examples_out_of_range",
    "bad_loss_scale",
)

STAGE_REASONS = {
    "validation": (
        "duplicate_sequence",
        "unknown_field",
        "unknown_shard",
        "retired_shard",
        "empty_shard",
        "examples_out_of_range",
        "bad_loss_scale",
    ),
    "ownership": ("unknown_owner", "owner_excluded", "owner_mismatch"),
}

RECOMMENDATION_RULES = (
    ("align-restart-to-window", lambda r: r["discarded_partial_records"] > 0),
    ("shorten-checkpoint-interval", lambda r: r["rolled_back_records"] > 0),
    ("freeze-shard-moves", lambda r: r["reject_counts"]["owner_mismatch"] > 0),
    ("restore-probe-cadence", lambda r: r["missing_probe"] > 0),
    ("retire-stray-probes", lambda r: r["orphan_probe"] > 0),
    ("lower-loss-scale", lambda r: r["overflow_skipped"] * 100 > r["accepted_records"] * 5),
    ("pad-final-window", lambda r: r["trailing_partial_records"] > 0),
    ("repair-schedule-spans", lambda r: r["zero_denominator"] > 0),
    ("reconcile-shard-plan", lambda r: r["coverage_gap"] != 0),
)

LOSS_SCALE_LOW = 64
LOSS_SCALE_HIGH = 65536

TABLE_SIGNATURES = {
    frozenset(
        {"shard_id", "owner", "example_count", "pass_index", "order_key", "status"}
    ): "manifest",
    frozenset({"shard_id", "from_owner", "to_owner", "effective_sequence"}): "moves",
    frozenset({"owner", "role", "slots"}): "roster",
    frozenset(
        {"checkpoint", "micro_cursor", "superseded_by", "written_at_sequence"}
    ): "checkpoints",
    frozenset({"example_id", "shard_id", "reason"}): "holdouts",
    frozenset({"group_id", "shard_id", "example_id", "keep"}): "duplicates",
}


def canonical(payload: object) -> str:
    """Return the one serialization the contract accepts."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def seal(body: dict) -> dict:
    """Attach the self describing fingerprint of a finished report body."""
    stripped = {key: value for key, value in body.items() if key != "body_fingerprint"}
    digest = hashlib.sha256(canonical(stripped).encode("utf-8")).hexdigest()
    body["body_fingerprint"] = digest[:16]
    return body


class Tally:
    """Counter for the division events the contract makes observable."""

    def __init__(self) -> None:
        self.zero_denominator = 0

    def ratio(self, numerator: int, denominator: int) -> int:
        if denominator == 0:
            self.zero_denominator += 1
            return 0
        quotient, remainder = divmod(numerator, denominator)
        twice = remainder * 2
        if twice > denominator:
            return quotient + 1
        if twice < denominator:
            return quotient
        return quotient if quotient % 2 == 0 else quotient + 1

    def percent(self, value: int, pct: int) -> int:
        return self.ratio(value * pct, 100)

    def mean(self, values: list) -> int:
        return self.ratio(sum(values), len(values))


def read_archive(data_dir: Path) -> dict:
    """Group every shipped file by the role its own content declares."""
    archive = {
        "records": [],
        "docs": {},
        "manifest": [],
        "moves": [],
        "roster": [],
        "checkpoints": [],
        "holdouts": [],
        "duplicates": [],
    }
    for path in sorted(data_dir.iterdir()):
        if not path.is_file():
            continue
        if path.name.endswith(".jsonl"):
            for line in path.read_text(encoding="utf-8").splitlines():
                text = line.strip()
                if text:
                    archive["records"].append(json.loads(text))
        elif path.name.endswith(".json"):
            doc = json.loads(path.read_text(encoding="utf-8"))
            archive["docs"][doc["document"]] = doc
        elif path.name.endswith(".csv"):
            with path.open(newline="", encoding="utf-8") as handle:
                reader = csv.DictReader(handle)
                header = frozenset(reader.fieldnames or ())
                role = TABLE_SIGNATURES.get(header)
                if role is None:
                    continue
                for row in reader:
                    archive[role].append(row)
    return archive


def order_stream(records: list) -> tuple:
    """Fold every segment into one ascending stream keyed by sequence."""
    by_sequence: dict = {}
    duplicates: list = []
    for item in sorted(records, key=canonical):
        key = int(item["sequence"])
        if key in by_sequence:
            duplicates.append(item)
        else:
            by_sequence[key] = item
    ordered = [by_sequence[key] for key in sorted(by_sequence)]
    micro = [item for item in ordered if item.get("record") == "micro"]
    markers = [item for item in ordered if item.get("record") == "marker"]
    dup_micro = [item for item in duplicates if item.get("record") == "micro"]
    return micro, markers, dup_micro


def shard_facts(archive: dict) -> tuple:
    """Resolve per shard owner, status, size and the manifest conflict count."""
    owners: dict = {}
    status: dict = {}
    counts: dict = {}
    blocks: set = set()
    conflicts = 0
    seen: dict = {}
    for row in sorted(archive["manifest"], key=lambda r: int(r["order_key"])):
        shard = row["shard_id"]
        blocks.add((shard, int(row["pass_index"])))
        if shard in seen:
            if seen[shard] != (row["owner"], int(row["example_count"]), row["status"]):
                conflicts += 1
            continue
        seen[shard] = (row["owner"], int(row["example_count"]), row["status"])
        owners[shard] = row["owner"]
        status[shard] = row["status"]
        counts[shard] = int(row["example_count"])
    held: dict = {}
    for row in archive["holdouts"]:
        held[row["shard_id"]] = held.get(row["shard_id"], 0) + 1
    dropped: dict = {}
    for row in archive["duplicates"]:
        if int(row["keep"]) == 0:
            dropped[row["shard_id"]] = dropped.get(row["shard_id"], 0) + 1
    size = {}
    for shard, total in counts.items():
        size[shard] = total - held.get(shard, 0) - dropped.get(shard, 0)
    planned = 0
    for shard, passes in sorted(blocks):
        planned += max(size.get(shard, 0), 0)
    return owners, status, size, blocks, planned, conflicts


def owner_at(shard: str, sequence: int, owners: dict, moves: list) -> str:
    """Walk the ownership timeline to the owner in force at one sequence."""
    current = owners.get(shard)
    best = None
    for row in moves:
        if row["shard_id"] != shard:
            continue
        when = int(row["effective_sequence"])
        if when > sequence:
            continue
        candidate = (when, row["to_owner"])
        if best is None or candidate > best:
            best = candidate
    if best is not None:
        current = best[1]
    return current


def phase_timeline(markers: list) -> list:
    """Return the phase openings in the order the contract fixes."""
    opens = [
        (int(item["sequence"]), item["phase"])
        for item in markers
        if item.get("kind") == "phase_open"
    ]
    return sorted(opens)


def phase_at(sequence: int, timeline: list) -> str:
    name = ""
    for when, phase in timeline:
        if when <= sequence:
            name = phase
        else:
            break
    return name


def exception_at(sequence: int, restarts: list, timeline: list) -> dict:
    """An exception rules from its restart until the next phase opening."""
    chosen = None
    for entry in sorted(restarts, key=lambda r: int(r["at_sequence"])):
        when = int(entry["at_sequence"])
        if when > sequence:
            continue
        blocked = any(when < marker <= sequence for marker, _ in timeline)
        if not blocked:
            chosen = entry
    return chosen


def is_power_of_two(value: int) -> bool:
    return value > 0 and value & (value - 1) == 0


def classify(
    record: dict,
    profile: dict,
    owners: dict,
    status: dict,
    size: dict,
    blocks: set,
    moves: list,
    roster: set,
) -> str:
    """Name the first rejection reason the record earns, or an empty string."""
    if set(record.keys()) != set(MICRO_KEYS):
        return "unknown_field"
    shard = record["shard"]
    if (shard, int(record["pass_index"])) not in blocks:
        return "unknown_shard"
    if status.get(shard) == "retired":
        return "retired_shard"
    if size.get(shard, 0) <= 0:
        return "empty_shard"
    owner = record["owner"]
    if owner not in roster:
        return "unknown_owner"
    if owner in profile["excluded_owners"]:
        return "owner_excluded"
    if owner != owner_at(shard, int(record["sequence"]), owners, moves):
        return "owner_mismatch"
    examples = int(record["examples"])
    if examples <= 0 or examples > size.get(shard, 0):
        return "examples_out_of_range"
    scale = int(record["loss_scale"])
    if not is_power_of_two(scale) or scale < LOSS_SCALE_LOW or scale > LOSS_SCALE_HIGH:
        return "bad_loss_scale"
    return ""


def resolve_width(profile: dict, phase: dict, exception: dict, policy: dict) -> int:
    width = profile["width_override"]
    if width is None and exception is not None:
        width = exception["accumulation_width"]
    if width is None and phase is not None:
        width = phase["accumulation_width"]
    if width is None:
        width = policy["default_width"]
    width = max(policy["minimum_width"], width)
    return min(policy["maximum_width"], width)


def resolve_carry(profile: dict, exception: dict, policy: dict) -> bool:
    if profile["carry_partial"] is not None:
        return bool(profile["carry_partial"])
    if exception is not None and exception["carry_partial"] is not None:
        return bool(exception["carry_partial"])
    return policy["partial_window_rule"] == "carry"


def step_rate(
    index: int,
    phase: dict,
    exception: dict,
    base: dict,
    profile: dict,
    tally: Tally,
) -> int:
    """Apply the base schedule, then the phase, profile and exception scales."""
    peak = int(base["peak_rate_milli"])
    floor = int(base["floor_rate_milli"])
    warmup = int(base["warmup_steps"])
    span = base["decay_span_steps"]
    if profile["decay_span_steps"] is not None:
        span = profile["decay_span_steps"]
    span = int(span)
    period = int(base["restart_period_steps"])
    if index <= warmup:
        rate = tally.ratio(peak * index, warmup)
    else:
        elapsed = index - warmup
        if period > 0:
            elapsed = ((elapsed - 1) % period) + 1
        travelled = min(elapsed, span)
        rate = peak - tally.ratio((peak - floor) * travelled, span)
    if phase is not None:
        rate = tally.percent(rate, int(phase["rate_scale_percent"]))
    rate = tally.percent(rate, int(profile["rate_scale_percent"]))
    if exception is not None:
        rate = tally.percent(rate, int(exception["rate_scale_percent"]))
    return rate


def audit(archive: dict, profile: dict) -> dict:
    """Run one profile of the run through the whole chain."""
    tally = Tally()
    base = archive["docs"]["schedule_base"]
    policy = archive["docs"]["accumulation_policy"]
    phases = {entry["phase"]: entry for entry in archive["docs"]["schedule_phases"]["phases"]}
    exceptions = {
        entry["restart_id"]: entry
        for entry in archive["docs"]["restart_exceptions"]["exceptions"]
    }
    cadence = archive["docs"]["cadence"]
    probes = archive["docs"]["eval_probes"]["probes"]
    restarts = archive["docs"]["restarts"]["restarts"]

    micro, markers, dup_micro = order_stream(archive["records"])
    timeline = phase_timeline(markers)
    owners, status, size, blocks, planned, conflicts = shard_facts(archive)
    roster = {row["owner"] for row in archive["roster"]}
    checkpoints = {row["checkpoint"]: row for row in archive["checkpoints"]}

    rejects = {reason: 0 for reason in REASON_ORDER}
    reject_examples = {reason: 0 for reason in REASON_ORDER}
    rejects["duplicate_sequence"] = len(dup_micro)
    for item in dup_micro:
        reject_examples["duplicate_sequence"] += max(int(item.get("examples", 0)), 0)

    accepted: list = []
    skipped = 0
    skipped_examples = 0
    for record in micro:
        reason = classify(
            record, profile, owners, status, size, blocks, archive["moves"], roster
        )
        if reason:
            rejects[reason] += 1
            reject_examples[reason] += max(int(record.get("examples", 0)), 0)
            continue
        if int(record["overflow"]) == 1:
            skipped += 1
            skipped_examples += int(record["examples"])
            continue
        accepted.append(record)

    rolled: list = []
    for entry in sorted(restarts, key=lambda r: int(r["at_sequence"])):
        point = checkpoints.get(entry["resume_checkpoint"])
        if point is None:
            continue
        low = int(point["written_at_sequence"])
        high = int(entry["at_sequence"])
        kept = []
        for record in accepted:
            if low < int(record["sequence"]) < high:
                rolled.append(record)
            else:
                kept.append(record)
        accepted = kept

    drift = 0
    for name in sorted(checkpoints):
        row = checkpoints[name]
        mark = int(row["written_at_sequence"])
        rebuilt = sum(1 for record in accepted if int(record["sequence"]) <= mark)
        if rebuilt != int(row["micro_cursor"]):
            drift += 1

    pending = 0
    pending_examples = 0
    discarded = 0
    discarded_examples = 0
    steps: list = []
    applied: set = set()
    schedule = sorted(restarts, key=lambda r: int(r["at_sequence"]))
    for record in accepted:
        sequence = int(record["sequence"])
        for entry in schedule:
            if entry["restart_id"] in applied:
                continue
            if int(entry["at_sequence"]) > sequence:
                continue
            applied.add(entry["restart_id"])
            carry = resolve_carry(
                profile, exceptions.get(entry["restart_id"]), policy
            )
            if not carry and pending > 0:
                discarded += pending
                discarded_examples += pending_examples
                pending = 0
                pending_examples = 0
        phase = phases.get(phase_at(sequence, timeline))
        active = exception_at(sequence, restarts, timeline)
        exception = exceptions.get(active["restart_id"]) if active else None
        width = resolve_width(profile, phase, exception, policy)
        pending += 1
        pending_examples += int(record["examples"])
        if pending >= width:
            steps.append(
                {
                    "index": len(steps) + 1,
                    "sequence": sequence,
                    "width": width,
                    "examples": pending_examples,
                    "phase": phase["phase"] if phase else "",
                    "exception": exception["restart_id"] if exception else "",
                }
            )
            pending = 0
            pending_examples = 0

    rates: list = []
    for step in steps:
        phase = phases.get(step["phase"])
        exception = exceptions.get(step["exception"])
        rates.append([step["index"], step_rate(step["index"], phase, exception, base, profile, tally)])

    final_step = steps[-1]["index"] if steps else 0
    log_every = int(cadence["log_every_steps"])
    if log_every <= 0:
        tally.zero_denominator += 1
        logged = 0
    else:
        logged = final_step // log_every
    probe_every = int(cadence["eval_every_steps"]) * int(profile["eval_cadence_scale"])
    if probe_every <= 0:
        tally.zero_denominator += 1
        expected: set = set()
    else:
        expected = {k for k in range(probe_every, final_step + 1, probe_every)}

    matched = []
    orphan = 0
    for probe in sorted(probes, key=lambda p: (int(p["step"]), p["probe"])):
        if int(probe["step"]) in expected:
            matched.append(probe)
        else:
            orphan += 1
    missing = len(expected) - len({int(probe["step"]) for probe in matched})

    cycles = 0

    def settle(name: str) -> str:
        nonlocal cycles
        seen = [name]
        current = name
        while True:
            row = checkpoints.get(current)
            if row is None:
                break
            nxt = row["superseded_by"].strip()
            if not nxt:
                break
            if nxt in seen:
                cycles += 1
                break
            seen.append(nxt)
            current = nxt
        return current

    best = ""
    if matched:
        ranked = sorted(
            matched, key=lambda p: (int(p["metric_milli"]), int(p["step"]), p["probe"])
        )
        best = settle(ranked[0]["checkpoint"])

    strikes = 0
    standing = None
    stop_step = 0
    for probe in matched:
        value = int(probe["metric_milli"])
        if standing is None or value < standing:
            standing = value
            strikes = 0
        else:
            strikes += 1
        stop_step = int(probe["step"])
        if strikes >= int(cadence["patience_probes"]):
            break

    window = int(cadence["average_window"])
    pool = [
        int(probe["metric_milli"])
        for probe in matched
        if int(probe["step"]) <= stop_step
        and not checkpoints.get(probe["checkpoint"], {}).get("superseded_by", "").strip()
    ]
    averaged = tally.mean(pool[-window:]) if window > 0 and pool else tally.mean([])

    accepted_examples = sum(int(record["examples"]) for record in accepted)
    rolled_examples = sum(int(record["examples"]) for record in rolled)
    result = {
        "accepted_examples": accepted_examples,
        "accepted_records": len(accepted),
        "averaged_metric_milli": averaged,
        "best_checkpoint": best,
        "coverage_gap": planned - accepted_examples,
        "cursor_drift": drift,
        "discarded_partial_examples": discarded_examples,
        "discarded_partial_records": discarded,
        "logged_steps": logged,
        "manifest_conflict": conflicts,
        "matched_probes": len(matched),
        "missing_probe": missing,
        "optimizer_steps": len(steps),
        "orphan_probe": orphan,
        "overflow_skipped": skipped,
        "planned_examples": planned,
        "profile": profile["name"],
        "rate_digest": hashlib.sha256(canonical(rates).encode("utf-8")).hexdigest()[:16],
        "rate_first": rates[0][1] if rates else 0,
        "rate_last": rates[-1][1] if rates else 0,
        "rate_max": max((pair[1] for pair in rates), default=0),
        "rate_min": min((pair[1] for pair in rates), default=0),
        "rate_sum": sum(pair[1] for pair in rates),
        "reject_counts": dict(rejects),
        "reject_examples": dict(reject_examples),
        "rejected_records": sum(rejects.values()),
        "rolled_back_examples": rolled_examples,
        "rolled_back_records": len(rolled),
        "skipped_examples": skipped_examples,
        "stop_step": stop_step,
        "supersession_cycle": cycles,
        "total_records": len(micro) + len(dup_micro),
        "trailing_partial_examples": pending_examples,
        "trailing_partial_records": pending,
        "zero_denominator": tally.zero_denominator,
    }
    return result


SCENARIO_FIELDS = (
    "accepted_examples",
    "accepted_records",
    "averaged_metric_milli",
    "best_checkpoint",
    "cursor_drift",
    "discarded_partial_examples",
    "discarded_partial_records",
    "logged_steps",
    "matched_probes",
    "missing_probe",
    "optimizer_steps",
    "orphan_probe",
    "overflow_skipped",
    "rate_digest",
    "rate_first",
    "rate_last",
    "rate_max",
    "rate_min",
    "rate_sum",
    "reject_counts",
    "rejected_records",
    "rolled_back_examples",
    "rolled_back_records",
    "stop_step",
    "supersession_cycle",
    "total_records",
    "trailing_partial_examples",
    "trailing_partial_records",
    "zero_denominator",
)


def scenario_body(result: dict) -> dict:
    body = {"document": "scenario", "profile": result["profile"]}
    for field in SCENARIO_FIELDS:
        body[field] = result[field]
    return seal(body)


def stage_rows(result: dict) -> list:
    rows = []
    for stage, reasons in sorted(STAGE_REASONS.items()):
        rows.append(
            {
                "stage": stage,
                "records_removed": sum(result["reject_counts"][r] for r in reasons),
                "examples_removed": sum(result["reject_examples"][r] for r in reasons),
            }
        )
    rows.append(
        {
            "stage": "rollback",
            "records_removed": result["rolled_back_records"],
            "examples_removed": result["rolled_back_examples"],
        }
    )
    rows.append(
        {
            "stage": "partial_discard",
            "records_removed": result["discarded_partial_records"],
            "examples_removed": result["discarded_partial_examples"],
        }
    )
    rows.append(
        {
            "stage": "trailing",
            "records_removed": result["trailing_partial_records"],
            "examples_removed": result["trailing_partial_examples"],
        }
    )
    return sorted(rows, key=lambda row: (-row["records_removed"], row["stage"]))


def dominant_reason(result: dict) -> str:
    counts = result["reject_counts"]
    if not any(counts.values()):
        return "none"
    return sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))[0][0]


def codes_for(result: dict) -> list:
    found = [code for code, rule in RECOMMENDATION_RULES if rule(result)]
    return found if found else ["hold-current-plan"]


def write_report(out_dir: Path, name: str, body: dict) -> None:
    target = out_dir / name
    target.write_text(canonical(body) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit a sharded training run.")
    parser.add_argument("--data", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    data_dir = Path(args.data)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    archive = read_archive(data_dir)
    profiles = archive["docs"]["profiles"]["profiles"]
    results = {}
    for profile in profiles:
        results[profile["name"]] = audit(archive, profile)

    names = [profile["name"] for profile in profiles]
    for name in names:
        write_report(out_dir, "scenario_" + name + ".json", scenario_body(results[name]))

    summary = {}
    deltas = {}
    totals = {
        "accepted_examples": 0,
        "accepted_records": 0,
        "optimizer_steps": 0,
        "rejected_records": 0,
        "rolled_back_records": 0,
        "skipped_records": 0,
    }
    gap_total = 0
    for name in names:
        row = results[name]
        summary[name] = {
            "accepted_examples": row["accepted_examples"],
            "accepted_records": row["accepted_records"],
            "averaged_metric_milli": row["averaged_metric_milli"],
            "best_checkpoint": row["best_checkpoint"],
            "optimizer_steps": row["optimizer_steps"],
            "rate_last": row["rate_last"],
            "stop_step": row["stop_step"],
        }
        totals["accepted_examples"] += row["accepted_examples"]
        totals["accepted_records"] += row["accepted_records"]
        totals["optimizer_steps"] += row["optimizer_steps"]
        totals["rejected_records"] += row["rejected_records"]
        totals["rolled_back_records"] += row["rolled_back_records"]
        totals["skipped_records"] += row["overflow_skipped"]
        gap_total += row["coverage_gap"]
    anchor = results.get("visible")
    for name in names:
        if name == "visible" or anchor is None:
            continue
        deltas[name] = {
            "accepted_examples_delta": results[name]["accepted_examples"]
            - anchor["accepted_examples"],
            "optimizer_steps_delta": results[name]["optimizer_steps"]
            - anchor["optimizer_steps"],
        }
    holds = 1
    for name in names:
        row = results[name]
        parts = (
            row["accepted_records"]
            + row["rejected_records"]
            + row["overflow_skipped"]
            + row["rolled_back_records"]
        )
        if parts != row["total_records"]:
            holds = 0
    write_report(
        out_dir,
        "perf_report.json",
        seal(
            {
                "document": "perf_report",
                "profiles": summary,
                "deltas_vs_visible": deltas,
                "totals": totals,
                "identity_checks": {
                    "coverage_gap_total": gap_total,
                    "partition_holds": holds,
                    "profiles_checked": len(names),
                },
            }
        ),
    )

    write_report(
        out_dir,
        "bottleneck_analysis.json",
        seal(
            {
                "document": "bottleneck_analysis",
                "profiles": {
                    name: {
                        "stages": stage_rows(results[name]),
                        "dominant_stage": stage_rows(results[name])[0]["stage"],
                        "dominant_reason": dominant_reason(results[name]),
                    }
                    for name in names
                },
            }
        ),
    )

    per_profile = {name: codes_for(results[name]) for name in names}
    merged = [
        code
        for code, rule in RECOMMENDATION_RULES
        if any(rule(results[name]) for name in names)
    ]
    write_report(
        out_dir,
        "recommendations.json",
        seal(
            {
                "document": "recommendations",
                "per_profile": per_profile,
                "codes": merged if merged else ["hold-current-plan"],
            }
        ),
    )

    write_report(
        out_dir,
        "data_quality.json",
        seal(
            {
                "document": "data_quality",
                "profiles": {
                    name: {
                        "reject_counts": results[name]["reject_counts"],
                        "overflow_skipped": results[name]["overflow_skipped"],
                        "cursor_drift": results[name]["cursor_drift"],
                        "manifest_conflict": results[name]["manifest_conflict"],
                        "supersession_cycle": results[name]["supersession_cycle"],
                        "zero_denominator": results[name]["zero_denominator"],
                        "partition": {
                            "accepted_records": results[name]["accepted_records"],
                            "holds": 1
                            if results[name]["accepted_records"]
                            + results[name]["rejected_records"]
                            + results[name]["overflow_skipped"]
                            + results[name]["rolled_back_records"]
                            == results[name]["total_records"]
                            else 0,
                            "rejected_records": results[name]["rejected_records"],
                            "rolled_back_records": results[name]["rolled_back_records"],
                            "skipped_records": results[name]["overflow_skipped"],
                            "total_records": results[name]["total_records"],
                        },
                        "coverage": {
                            "accepted_examples": results[name]["accepted_examples"],
                            "coverage_gap": results[name]["coverage_gap"],
                            "planned_examples": results[name]["planned_examples"],
                        },
                    }
                    for name in names
                },
            }
        ),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
