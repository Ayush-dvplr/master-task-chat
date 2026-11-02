#!/usr/bin/env python3
"""Run ledger auditor.

Rebuilds the optimizer step ledger of a sharded training run from the archive's
primary evidence and publishes the reports named in run_contract.md.
"""

import argparse
import csv
import hashlib
import json
import os

MICRO_KEYS = frozenset(
    ["record", "sequence", "owner", "shard", "pass_index", "examples", "loss_scale", "overflow"]
)

REJECT_REASONS = [
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
]

VALIDATION_REASONS = [
    "duplicate_sequence",
    "unknown_field",
    "unknown_shard",
    "retired_shard",
    "empty_shard",
    "examples_out_of_range",
    "bad_loss_scale",
]

OWNERSHIP_REASONS = ["unknown_owner", "owner_excluded", "owner_mismatch"]

STAGES = ["validation", "ownership", "rollback", "partial_discard", "trailing"]

MANIFEST_COLUMNS = frozenset(
    ["shard_id", "owner", "example_count", "pass_index", "order_key", "status"]
)
MOVE_COLUMNS = frozenset(["shard_id", "from_owner", "to_owner", "effective_sequence"])
ROSTER_COLUMNS = frozenset(["owner", "role", "slots"])
CHECKPOINT_COLUMNS = frozenset(
    ["checkpoint", "micro_cursor", "superseded_by", "written_at_sequence"]
)
HOLDOUT_COLUMNS = frozenset(["example_id", "shard_id", "reason"])
DUPLICATE_COLUMNS = frozenset(["group_id", "shard_id", "example_id", "keep"])


# --------------------------------------------------------------------------- #
# serialization and arithmetic
# --------------------------------------------------------------------------- #


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def short_digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def seal(report):
    body = dict((k, v) for k, v in report.items() if k != "body_fingerprint")
    report["body_fingerprint"] = short_digest(canonical(body))
    return report


class Counters(object):
    """Per profile event tallies that the arithmetic policy can raise."""

    def __init__(self):
        self.zero_denominator = 0


def ratio(numerator, denominator, counters):
    if denominator == 0:
        counters.zero_denominator += 1
        return 0
    quotient, remainder = divmod(numerator, denominator)
    twice = 2 * remainder
    if twice > denominator:
        return quotient + 1
    if twice < denominator:
        return quotient
    return quotient if quotient % 2 == 0 else quotient + 1


def percent(value, pct, counters):
    return ratio(value * pct, 100, counters)


def mean(values, counters):
    return ratio(sum(values), len(values), counters)


def to_int(value, default=0):
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def is_power_of_two(value):
    return (
        isinstance(value, int)
        and not isinstance(value, bool)
        and value > 0
        and value & (value - 1) == 0
    )


# --------------------------------------------------------------------------- #
# archive loading: role comes from content, never from the file name
# --------------------------------------------------------------------------- #


class Archive(object):
    def __init__(self, data_dir):
        self.docs = {}
        self.tables = {}
        self.lines = []
        names = sorted(
            n for n in os.listdir(data_dir) if os.path.isfile(os.path.join(data_dir, n))
        )
        for name in names:
            path = os.path.join(data_dir, name)
            lower = name.lower()
            if lower.endswith(".json"):
                with open(path, "r", encoding="utf-8") as handle:
                    obj = json.load(handle)
                self.docs.setdefault(obj.get("document"), []).append(obj)
            elif lower.endswith(".csv"):
                with open(path, "r", encoding="utf-8", newline="") as handle:
                    reader = csv.DictReader(handle)
                    fields = reader.fieldnames or []
                    rows = [dict(row) for row in reader]
                self.tables.setdefault(frozenset(fields), []).extend(rows)
            elif lower.endswith(".jsonl"):
                with open(path, "r", encoding="utf-8") as handle:
                    for raw in handle:
                        raw = raw.strip()
                        if raw:
                            self.lines.append(json.loads(raw))

    def doc(self, role):
        found = self.docs.get(role)
        return found[0] if found else {}

    def doc_list(self, role, key):
        out = []
        for obj in self.docs.get(role, []):
            out.extend(obj.get(key) or [])
        return out

    def table(self, columns):
        return self.tables.get(columns, [])


# --------------------------------------------------------------------------- #
# the single ordered stream
# --------------------------------------------------------------------------- #


def build_stream(archive):
    """Order every jsonl line by ascending sequence, resolving shared sequences."""
    claimants = {}
    for index, line in enumerate(archive.lines):
        sequence = to_int(line.get("sequence"))
        claimants.setdefault(sequence, []).append((canonical(line), index, line))

    stream = []
    for sequence in sorted(claimants):
        group = sorted(
            claimants[sequence], key=lambda item: (item[0].encode("utf-8"), item[1])
        )
        stream.append({"sequence": sequence, "line": group[0][2], "duplicate": False})
        for loser in group[1:]:
            if loser[2].get("record") == "micro":
                stream.append({"sequence": sequence, "line": loser[2], "duplicate": True})
    stream.sort(key=lambda item: (item["sequence"], item["duplicate"]))
    return stream


def build_phase_timeline(stream):
    openings = []
    for item in stream:
        line = item["line"]
        if item["duplicate"]:
            continue
        if line.get("record") == "marker" and line.get("kind") == "phase_open":
            openings.append((item["sequence"], line.get("phase")))
    openings.sort(key=lambda entry: entry[0])
    return openings


def phase_at(openings, sequence):
    found = None
    for seq, phase in openings:
        if seq <= sequence:
            found = phase
        else:
            break
    return found


def restart_in_force(restarts, openings, sequence):
    """A restart holds from its own sequence until the next phase opening past it."""
    chosen = None
    for restart in restarts:
        if restart["at_sequence"] <= sequence:
            chosen = restart
        else:
            break
    if chosen is None:
        return None
    for seq, _phase in openings:
        if seq > chosen["at_sequence"]:
            if sequence >= seq:
                return None
            break
    return chosen


# --------------------------------------------------------------------------- #
# shard plan
# --------------------------------------------------------------------------- #


class ShardPlan(object):
    def __init__(self, archive):
        rows = archive.table(MANIFEST_COLUMNS)
        ordered = sorted(
            enumerate(rows), key=lambda pair: (to_int(pair[1].get("order_key")), pair[0])
        )
        self.shards = {}
        self.pairs = set()
        self.manifest_conflict = 0
        for _index, row in ordered:
            shard = row.get("shard_id")
            owner = row.get("owner")
            count = to_int(row.get("example_count"))
            status = row.get("status")
            self.pairs.add((shard, to_int(row.get("pass_index"))))
            settled = self.shards.get(shard)
            if settled is None:
                self.shards[shard] = {
                    "owner": owner,
                    "example_count": count,
                    "status": status,
                }
            elif (
                settled["owner"] != owner
                or settled["example_count"] != count
                or settled["status"] != status
            ):
                self.manifest_conflict += 1

        holdouts = {}
        for row in archive.table(HOLDOUT_COLUMNS):
            shard = row.get("shard_id")
            holdouts[shard] = holdouts.get(shard, 0) + 1
        dropped = {}
        for row in archive.table(DUPLICATE_COLUMNS):
            if to_int(row.get("keep")) == 0:
                shard = row.get("shard_id")
                dropped[shard] = dropped.get(shard, 0) + 1

        self.effective = {}
        for shard, info in self.shards.items():
            self.effective[shard] = (
                info["example_count"] - holdouts.get(shard, 0) - dropped.get(shard, 0)
            )

        self.moves = {}
        for row in archive.table(MOVE_COLUMNS):
            shard = row.get("shard_id")
            self.moves.setdefault(shard, []).append(
                (to_int(row.get("effective_sequence")), row.get("to_owner"))
            )
        for shard in self.moves:
            self.moves[shard].sort(key=lambda entry: (entry[0], str(entry[1])))

        self.planned_examples = 0
        for shard, _pass_index in self.pairs:
            size = self.effective.get(shard, 0)
            self.planned_examples += size if size > 0 else 0

    def owner_at(self, shard, sequence):
        owner = self.shards.get(shard, {}).get("owner")
        for eff, to_owner in self.moves.get(shard, []):
            if eff <= sequence:
                owner = to_owner
            else:
                break
        return owner


# --------------------------------------------------------------------------- #
# precedence
# --------------------------------------------------------------------------- #


def layered_width(profile, exception, phase_entry, policy):
    width = 0
    for candidate in (
        profile.get("width_override"),
        (exception or {}).get("accumulation_width"),
        (phase_entry or {}).get("accumulation_width"),
        policy.get("default_width"),
    ):
        if candidate is not None:
            width = to_int(candidate)
            break
    minimum = policy.get("minimum_width")
    maximum = policy.get("maximum_width")
    if minimum is not None and width < to_int(minimum):
        width = to_int(minimum)
    if maximum is not None and width > to_int(maximum):
        width = to_int(maximum)
    return width


def layered_carry(profile, exception, policy):
    for candidate in (profile.get("carry_partial"), (exception or {}).get("carry_partial")):
        if isinstance(candidate, bool):
            return candidate
    return policy.get("partial_window_rule") == "carry"


def layered_decay_span(profile, schedule_base):
    span = profile.get("decay_span_steps")
    if span is None:
        span = schedule_base.get("decay_span_steps")
    return to_int(span)


def base_rate(step, schedule_base, span, counters):
    peak = to_int(schedule_base.get("peak_rate_milli"))
    floor = to_int(schedule_base.get("floor_rate_milli"))
    warmup = to_int(schedule_base.get("warmup_steps"))
    period = to_int(schedule_base.get("restart_period_steps"))
    if step <= warmup:
        return ratio(peak * step, warmup, counters)
    elapsed = step - warmup
    if period > 0:
        elapsed = ((elapsed - 1) % period) + 1
    travelled = elapsed if elapsed < span else span
    return peak - ratio((peak - floor) * travelled, span, counters)


# --------------------------------------------------------------------------- #
# the audit of one profile
# --------------------------------------------------------------------------- #


def audit_profile(profile, context):
    plan = context["plan"]
    stream = context["stream"]
    openings = context["openings"]
    restarts = context["restarts"]
    exceptions = context["exceptions"]
    phases = context["phases"]
    policy = context["policy"]
    schedule_base = context["schedule_base"]
    cadence = context["cadence"]
    checkpoints = context["checkpoints"]
    probes = context["probes"]
    roster = context["roster"]

    counters = Counters()
    excluded = set(profile.get("excluded_owners") or [])

    reject_counts = dict((reason, 0) for reason in REJECT_REASONS)
    reject_examples = dict((reason, 0) for reason in REJECT_REASONS)
    total_records = 0
    overflow_skipped = 0
    skipped_examples = 0
    accepted = []

    for item in stream:
        line = item["line"]
        if line.get("record") != "micro":
            continue
        total_records += 1
        sequence = item["sequence"]
        examples = to_int(line.get("examples"))
        shard = line.get("shard")
        pass_index = to_int(line.get("pass_index"))
        owner = line.get("owner")
        info = plan.shards.get(shard, {})
        size = plan.effective.get(shard, 0)
        loss_scale = line.get("loss_scale")

        reason = None
        if item["duplicate"]:
            reason = "duplicate_sequence"
        elif frozenset(line.keys()) != MICRO_KEYS:
            reason = "unknown_field"
        elif (shard, pass_index) not in plan.pairs:
            reason = "unknown_shard"
        elif info.get("status") == "retired":
            reason = "retired_shard"
        elif size <= 0:
            reason = "empty_shard"
        elif owner not in roster:
            reason = "unknown_owner"
        elif owner in excluded:
            reason = "owner_excluded"
        elif owner != plan.owner_at(shard, sequence):
            reason = "owner_mismatch"
        elif examples <= 0 or examples > size:
            reason = "examples_out_of_range"
        elif not is_power_of_two(loss_scale) or loss_scale < 64 or loss_scale > 65536:
            reason = "bad_loss_scale"

        if reason is not None:
            reject_counts[reason] += 1
            reject_examples[reason] += examples
        elif to_int(line.get("overflow")) == 1:
            overflow_skipped += 1
            skipped_examples += examples
        else:
            accepted.append({"sequence": sequence, "examples": examples})

    # roll back, once per restart, in ascending order of restart sequence
    rolled_back_records = 0
    rolled_back_examples = 0
    for restart in restarts:
        checkpoint = checkpoints.get(restart.get("resume_checkpoint"))
        if checkpoint is None:
            continue
        written = checkpoint["written_at_sequence"]
        at = restart["at_sequence"]
        kept = []
        for record in accepted:
            if written < record["sequence"] < at:
                rolled_back_records += 1
                rolled_back_examples += record["examples"]
            else:
                kept.append(record)
        accepted = kept

    accepted_records = len(accepted)
    accepted_examples = sum(record["examples"] for record in accepted)

    # the accumulation walk over the surviving stream
    pending_records = 0
    pending_examples = 0
    step_sequences = []
    discarded_partial_records = 0
    discarded_partial_examples = 0
    fired = 0
    for record in accepted:
        while fired < len(restarts) and restarts[fired]["at_sequence"] <= record["sequence"]:
            restart = restarts[fired]
            fired += 1
            exception = exceptions.get(restart.get("restart_id"))
            if not layered_carry(profile, exception, policy) and pending_records > 0:
                discarded_partial_records += pending_records
                discarded_partial_examples += pending_examples
                pending_records = 0
                pending_examples = 0
        pending_records += 1
        pending_examples += record["examples"]
        in_force = restart_in_force(restarts, openings, record["sequence"])
        width = layered_width(
            profile,
            exceptions.get((in_force or {}).get("restart_id")),
            phases.get(phase_at(openings, record["sequence"])),
            policy,
        )
        if pending_records >= width:
            step_sequences.append(record["sequence"])
            pending_records = 0
            pending_examples = 0

    trailing_partial_records = pending_records
    trailing_partial_examples = pending_examples
    optimizer_steps = len(step_sequences)

    # the rate table, one entry per optimizer step
    span = layered_decay_span(profile, schedule_base)
    rate_table = []
    for index, sequence in enumerate(step_sequences):
        step = index + 1
        rate = base_rate(step, schedule_base, span, counters)
        phase_entry = phases.get(phase_at(openings, sequence))
        if phase_entry is not None and phase_entry.get("rate_scale_percent") is not None:
            rate = percent(rate, to_int(phase_entry.get("rate_scale_percent")), counters)
        if profile.get("rate_scale_percent") is not None:
            rate = percent(rate, to_int(profile.get("rate_scale_percent")), counters)
        in_force = restart_in_force(restarts, openings, sequence)
        exception = exceptions.get((in_force or {}).get("restart_id"))
        if exception is not None and exception.get("rate_scale_percent") is not None:
            rate = percent(rate, to_int(exception.get("rate_scale_percent")), counters)
        rate_table.append([step, rate])

    rates = [entry[1] for entry in rate_table]

    log_every = to_int(cadence.get("log_every_steps"))
    if log_every > 0:
        logged_steps = optimizer_steps // log_every
    else:
        counters.zero_denominator += 1
        logged_steps = 0

    # checkpoint cursor drift
    cursor_drift = 0
    sequences = [record["sequence"] for record in accepted]
    for name in sorted(checkpoints):
        checkpoint = checkpoints[name]
        rebuilt = sum(1 for seq in sequences if seq <= checkpoint["written_at_sequence"])
        if rebuilt != checkpoint["micro_cursor"]:
            cursor_drift += 1

    # probe cadence
    stride = to_int(cadence.get("eval_every_steps")) * to_int(
        profile.get("eval_cadence_scale"), 1
    )
    expected = []
    if stride > 0:
        step = stride
        while step <= optimizer_steps:
            expected.append(step)
            step += stride
    expected_set = set(expected)
    matched = [probe for probe in probes if probe["step"] in expected_set]
    matched_probes = len(matched)
    orphan_probe = len(probes) - matched_probes
    probe_steps = set(probe["step"] for probe in probes)
    missing_probe = sum(1 for step in expected if step not in probe_steps)

    # early stopping walk over the matched probes
    patience = to_int(cadence.get("patience_probes"))
    stop_step = 0
    best_metric = None
    strikes = 0
    for probe in matched:
        if best_metric is None or probe["metric_milli"] < best_metric:
            best_metric = probe["metric_milli"]
            strikes = 0
        else:
            strikes += 1
        stop_step = probe["step"]
        if patience > 0 and strikes >= patience:
            break

    # selection and the supersession chain
    supersession_cycle = 0
    best_checkpoint = "none"
    if matched:
        chosen = min(
            matched, key=lambda probe: (probe["metric_milli"], probe["step"], probe["probe"])
        )
        current = chosen["checkpoint"]
        visited = [current]
        while True:
            row = checkpoints.get(current)
            if row is None or not row["superseded_by"]:
                break
            nxt = row["superseded_by"]
            if nxt in visited:
                supersession_cycle += 1
                break
            visited.append(nxt)
            current = nxt
        best_checkpoint = current

    # weight averaging
    window = to_int(cadence.get("average_window"))
    metrics = []
    for probe in matched:
        if probe["step"] > stop_step:
            continue
        row = checkpoints.get(probe["checkpoint"])
        if row is not None and row["superseded_by"]:
            continue
        metrics.append(probe["metric_milli"])
    metrics = metrics[-window:] if window > 0 else []
    averaged_metric_milli = mean(metrics, counters)

    rejected_records = sum(reject_counts.values())
    coverage_gap = plan.planned_examples - accepted_examples
    partition_holds = (
        total_records
        == accepted_records + rejected_records + overflow_skipped + rolled_back_records
    )

    stage_records = {
        "validation": sum(reject_counts[r] for r in VALIDATION_REASONS),
        "ownership": sum(reject_counts[r] for r in OWNERSHIP_REASONS),
        "rollback": rolled_back_records,
        "partial_discard": discarded_partial_records,
        "trailing": trailing_partial_records,
    }
    stage_examples = {
        "validation": sum(reject_examples[r] for r in VALIDATION_REASONS),
        "ownership": sum(reject_examples[r] for r in OWNERSHIP_REASONS),
        "rollback": rolled_back_examples,
        "partial_discard": discarded_partial_examples,
        "trailing": trailing_partial_examples,
    }

    return {
        "profile": profile.get("name"),
        "accepted_examples": accepted_examples,
        "accepted_records": accepted_records,
        "averaged_metric_milli": averaged_metric_milli,
        "best_checkpoint": best_checkpoint,
        "coverage_gap": coverage_gap,
        "cursor_drift": cursor_drift,
        "discarded_partial_examples": discarded_partial_examples,
        "discarded_partial_records": discarded_partial_records,
        "logged_steps": logged_steps,
        "manifest_conflict": plan.manifest_conflict,
        "matched_probes": matched_probes,
        "missing_probe": missing_probe,
        "optimizer_steps": optimizer_steps,
        "orphan_probe": orphan_probe,
        "overflow_skipped": overflow_skipped,
        "partition_holds": 1 if partition_holds else 0,
        "planned_examples": plan.planned_examples,
        "rate_digest": short_digest(canonical(rate_table)),
        "rate_first": rates[0] if rates else 0,
        "rate_last": rates[-1] if rates else 0,
        "rate_max": max(rates) if rates else 0,
        "rate_min": min(rates) if rates else 0,
        "rate_sum": sum(rates),
        "reject_counts": reject_counts,
        "rejected_records": rejected_records,
        "rolled_back_examples": rolled_back_examples,
        "rolled_back_records": rolled_back_records,
        "skipped_examples": skipped_examples,
        "stage_examples": stage_examples,
        "stage_records": stage_records,
        "stop_step": stop_step,
        "supersession_cycle": supersession_cycle,
        "total_records": total_records,
        "trailing_partial_examples": trailing_partial_examples,
        "trailing_partial_records": trailing_partial_records,
        "zero_denominator": counters.zero_denominator,
    }


# --------------------------------------------------------------------------- #
# reports
# --------------------------------------------------------------------------- #

SCENARIO_KEYS = [
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
]

RULES = [
    ("align-restart-to-window", lambda a: a["discarded_partial_records"] > 0),
    ("shorten-checkpoint-interval", lambda a: a["rolled_back_records"] > 0),
    ("freeze-shard-moves", lambda a: a["reject_counts"]["owner_mismatch"] > 0),
    ("restore-probe-cadence", lambda a: a["missing_probe"] > 0),
    ("retire-stray-probes", lambda a: a["orphan_probe"] > 0),
    ("lower-loss-scale", lambda a: a["overflow_skipped"] * 100 > a["accepted_records"] * 5),
    ("pad-final-window", lambda a: a["trailing_partial_records"] > 0),
    ("repair-schedule-spans", lambda a: a["zero_denominator"] > 0),
    ("reconcile-shard-plan", lambda a: a["coverage_gap"] != 0),
]


def scenario_report(audit):
    report = {"document": "scenario", "profile": audit["profile"]}
    for key in SCENARIO_KEYS:
        report[key] = audit[key]
    return seal(report)


def perf_report(audits):
    baseline = next((a for a in audits if a["profile"] == "visible"), None)
    profiles = {}
    deltas = {}
    totals = dict(
        (key, 0)
        for key in (
            "accepted_examples",
            "accepted_records",
            "optimizer_steps",
            "rejected_records",
            "rolled_back_records",
            "skipped_records",
        )
    )
    coverage_gap_total = 0
    partition_holds = 1
    for audit in audits:
        profiles[audit["profile"]] = {
            "accepted_examples": audit["accepted_examples"],
            "accepted_records": audit["accepted_records"],
            "averaged_metric_milli": audit["averaged_metric_milli"],
            "best_checkpoint": audit["best_checkpoint"],
            "optimizer_steps": audit["optimizer_steps"],
            "rate_last": audit["rate_last"],
            "stop_step": audit["stop_step"],
        }
        if audit["profile"] != "visible":
            deltas[audit["profile"]] = {
                "accepted_examples_delta": audit["accepted_examples"]
                - (baseline["accepted_examples"] if baseline else 0),
                "optimizer_steps_delta": audit["optimizer_steps"]
                - (baseline["optimizer_steps"] if baseline else 0),
            }
        totals["accepted_examples"] += audit["accepted_examples"]
        totals["accepted_records"] += audit["accepted_records"]
        totals["optimizer_steps"] += audit["optimizer_steps"]
        totals["rejected_records"] += audit["rejected_records"]
        totals["rolled_back_records"] += audit["rolled_back_records"]
        totals["skipped_records"] += audit["overflow_skipped"]
        coverage_gap_total += audit["coverage_gap"]
        if not audit["partition_holds"]:
            partition_holds = 0
    return seal(
        {
            "document": "perf_report",
            "profiles": profiles,
            "deltas_vs_visible": deltas,
            "totals": totals,
            "identity_checks": {
                "coverage_gap_total": coverage_gap_total,
                "partition_holds": partition_holds,
                "profiles_checked": len(audits),
            },
        }
    )


def bottleneck_report(audits):
    profiles = {}
    for audit in audits:
        stages = [
            {
                "stage": stage,
                "records_removed": audit["stage_records"][stage],
                "examples_removed": audit["stage_examples"][stage],
            }
            for stage in STAGES
        ]
        stages.sort(key=lambda entry: (-entry["records_removed"], entry["stage"]))
        counts = audit["reject_counts"]
        if max(counts.values()) > 0:
            dominant_reason = min(REJECT_REASONS, key=lambda reason: (-counts[reason], reason))
        else:
            dominant_reason = "none"
        profiles[audit["profile"]] = {
            "stages": stages,
            "dominant_stage": stages[0]["stage"],
            "dominant_reason": dominant_reason,
        }
    return seal({"document": "bottleneck_analysis", "profiles": profiles})


def recommendations_report(audits):
    per_profile = {}
    fired = set()
    for audit in audits:
        codes = [code for code, test in RULES if test(audit)]
        fired.update(codes)
        per_profile[audit["profile"]] = codes if codes else ["hold-current-plan"]
    merged = [code for code, _test in RULES if code in fired]
    return seal(
        {
            "document": "recommendations",
            "per_profile": per_profile,
            "codes": merged if merged else ["hold-current-plan"],
        }
    )


def data_quality_report(audits):
    profiles = {}
    for audit in audits:
        profiles[audit["profile"]] = {
            "reject_counts": audit["reject_counts"],
            "overflow_skipped": audit["overflow_skipped"],
            "cursor_drift": audit["cursor_drift"],
            "manifest_conflict": audit["manifest_conflict"],
            "supersession_cycle": audit["supersession_cycle"],
            "zero_denominator": audit["zero_denominator"],
            "partition": {
                "accepted_records": audit["accepted_records"],
                "holds": audit["partition_holds"],
                "rejected_records": audit["rejected_records"],
                "rolled_back_records": audit["rolled_back_records"],
                "skipped_records": audit["overflow_skipped"],
                "total_records": audit["total_records"],
            },
            "coverage": {
                "accepted_examples": audit["accepted_examples"],
                "coverage_gap": audit["coverage_gap"],
                "planned_examples": audit["planned_examples"],
            },
        }
    return seal({"document": "data_quality", "profiles": profiles})


def write_report(out_dir, name, report):
    with open(os.path.join(out_dir, name), "w", encoding="utf-8", newline="") as handle:
        handle.write(canonical(report) + "\n")


# --------------------------------------------------------------------------- #
# entry point
# --------------------------------------------------------------------------- #


def build_context(archive):
    stream = build_stream(archive)
    openings = build_phase_timeline(stream)

    restarts = []
    for entry in archive.doc_list("restarts", "restarts"):
        restarts.append(
            {
                "at_sequence": to_int(entry.get("at_sequence")),
                "restart_id": entry.get("restart_id"),
                "resume_checkpoint": entry.get("resume_checkpoint"),
            }
        )
    restarts.sort(key=lambda entry: (entry["at_sequence"], str(entry["restart_id"])))

    exceptions = {}
    for entry in archive.doc_list("restart_exceptions", "exceptions"):
        exceptions[entry.get("restart_id")] = entry

    phases = {}
    for entry in archive.doc_list("schedule_phases", "phases"):
        phases[entry.get("phase")] = entry

    checkpoints = {}
    for row in archive.table(CHECKPOINT_COLUMNS):
        checkpoints[row.get("checkpoint")] = {
            "micro_cursor": to_int(row.get("micro_cursor")),
            "superseded_by": (row.get("superseded_by") or "").strip(),
            "written_at_sequence": to_int(row.get("written_at_sequence")),
        }

    probes = []
    for entry in archive.doc_list("eval_probes", "probes"):
        probes.append(
            {
                "checkpoint": entry.get("checkpoint"),
                "metric_milli": to_int(entry.get("metric_milli")),
                "probe": str(entry.get("probe")),
                "step": to_int(entry.get("step")),
            }
        )
    probes.sort(key=lambda probe: (probe["step"], probe["probe"]))

    roster = set(row.get("owner") for row in archive.table(ROSTER_COLUMNS))

    return {
        "plan": ShardPlan(archive),
        "stream": stream,
        "openings": openings,
        "restarts": restarts,
        "exceptions": exceptions,
        "phases": phases,
        "policy": archive.doc("accumulation_policy"),
        "schedule_base": archive.doc("schedule_base"),
        "cadence": archive.doc("cadence"),
        "checkpoints": checkpoints,
        "probes": probes,
        "roster": roster,
    }


def main():
    parser = argparse.ArgumentParser(description="Audit a sharded training run archive.")
    parser.add_argument("--data", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    archive = Archive(args.data)
    context = build_context(archive)
    audits = [
        audit_profile(profile, context)
        for profile in archive.doc_list("profiles", "profiles")
    ]

    os.makedirs(args.out, exist_ok=True)
    for audit in audits:
        write_report(args.out, "scenario_%s.json" % audit["profile"], scenario_report(audit))
    write_report(args.out, "perf_report.json", perf_report(audits))
    write_report(args.out, "bottleneck_analysis.json", bottleneck_report(audits))
    write_report(args.out, "recommendations.json", recommendations_report(audits))
    write_report(args.out, "data_quality.json", data_quality_report(audits))


if __name__ == "__main__":
    main()
