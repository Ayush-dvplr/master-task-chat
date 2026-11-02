#!/usr/bin/env python3
"""Chainfold run ledger auditor.

Rebuilds the optimizer step ledger of a sharded training run from primary
evidence and publishes the reports named in the run contract.

    python3 optimize.py --data <archive directory> --out <output directory>

Reads only files directly inside the archive directory, writes only files
directly inside the output directory, standard library only, byte identical
output for the same archive. File names carry no authority: every file
declares its own role by content.
"""

import argparse
import csv
import hashlib
import json
import os
import sys
from bisect import bisect_right

# ---------------------------------------------------------------------------
# Fixed vocabularies from the policy notes
# ---------------------------------------------------------------------------

MICRO_KEYS = frozenset((
    "record", "sequence", "owner", "shard", "pass_index",
    "examples", "loss_scale", "overflow",
))

REJECTION_REASONS = (
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

VALIDATION_REASONS = frozenset((
    "duplicate_sequence", "unknown_field", "unknown_shard", "retired_shard",
    "empty_shard", "examples_out_of_range", "bad_loss_scale",
))

OWNERSHIP_REASONS = frozenset((
    "unknown_owner", "owner_excluded", "owner_mismatch",
))

STAGES = ("validation", "ownership", "rollback", "partial_discard", "trailing")

RECOMMENDATION_RULES = (
    ("align-restart-to-window",
     lambda m: m["discarded_partial_records"] > 0),
    ("shorten-checkpoint-interval",
     lambda m: m["rolled_back_records"] > 0),
    ("freeze-shard-moves", lambda m: m["reject_counts"]["owner_mismatch"] > 0),
    ("restore-probe-cadence", lambda m: m["missing_probe"] > 0),
    ("retire-stray-probes", lambda m: m["orphan_probe"] > 0),
    ("lower-loss-scale",
     lambda m: m["overflow_skipped"] * 100 > m["accepted_records"] * 5),
    ("pad-final-window", lambda m: m["trailing_partial_records"] > 0),
    ("repair-schedule-spans", lambda m: m["zero_denominator"] > 0),
    ("reconcile-shard-plan", lambda m: m["coverage_gap"] != 0),
)

# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


def canonical(value):
    """Canonical JSON text: sorted keys, compact separators, ASCII only."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True)


def fingerprint(body):
    """First 16 lowercase hex characters of the SHA-256 digest of the body."""
    return hashlib.sha256(canonical(body).encode("utf-8")).hexdigest()[:16]


def seal(body):
    """Insert the fingerprint of the finished body into the same body."""
    sealed = dict(body)
    sealed["body_fingerprint"] = fingerprint(body)
    return sealed


def _as_int(value, default=0):
    if value is None or isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------------------
# Arithmetic policy
# ---------------------------------------------------------------------------


class Arithmetic:
    """The one division operation, plus the zero denominator events."""

    def __init__(self):
        self.zero_denominator = 0

    def ratio(self, numerator, denominator):
        if denominator == 0:
            self.zero_denominator += 1
            return 0
        quotient, remainder = divmod(numerator, denominator)
        twice = 2 * remainder
        if twice > denominator:
            return quotient + 1
        if twice < denominator:
            return quotient
        return quotient if quotient % 2 == 0 else quotient + 1

    def percent(self, value, pct):
        return self.ratio(value * pct, 100)

    def mean(self, values):
        if not values:
            return self.ratio(0, 0)
        return self.ratio(sum(values), len(values))


# ---------------------------------------------------------------------------
# Archive loading
# ---------------------------------------------------------------------------


def _merge_docs(base, extra):
    """Two documents of one role merge; list payloads extend."""
    merged = dict(base)
    for key, value in extra.items():
        if key not in merged:
            merged[key] = value
        elif isinstance(merged[key], list) and isinstance(value, list):
            merged[key] = merged[key] + value
        elif isinstance(merged[key], dict) and isinstance(value, dict):
            combined = dict(merged[key])
            combined.update(value)
            merged[key] = combined
        else:
            merged[key] = value
    return merged


def load_archive(data_dir):
    """Read every file directly inside the archive directory once."""
    docs = {}
    tables = {}
    lines = []
    for name in sorted(os.listdir(data_dir)):
        path = os.path.join(data_dir, name)
        if not os.path.isfile(path):
            continue
        if name.endswith(".json"):
            with open(path, "r", encoding="utf-8") as handle:
                doc = json.load(handle)
            if isinstance(doc, dict) and "document" in doc:
                role = doc["document"]
                docs[role] = (_merge_docs(docs[role], doc)
                              if role in docs else doc)
        elif name.endswith(".csv"):
            with open(path, "r", encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle)
                header = tuple(reader.fieldnames or ())
                rows = [row for row in reader
                        if any(v not in (None, "") for v in row.values())]
            tables.setdefault(header, []).extend(rows)
        elif name.endswith(".jsonl"):
            with open(path, "r", encoding="utf-8") as handle:
                for line in handle:
                    stripped = line.strip()
                    if stripped:
                        lines.append(json.loads(stripped))
    return docs, tables, lines


class Book:
    """Documents and joined tables, addressed by content role."""

    def __init__(self, docs, tables):
        self.docs = docs
        self.tables = tables

    def doc(self, role):
        doc = self.docs.get(role)
        return doc if isinstance(doc, dict) else {}

    def entries(self, role, key):
        doc = self.docs.get(role)
        if not isinstance(doc, dict):
            return []
        payload = doc.get(key)
        return payload if isinstance(payload, list) else []

    def rows(self, *columns):
        wanted = tuple(columns)
        rows = []
        for header in sorted(self.tables):
            if tuple(header) == wanted:
                rows.extend(self.tables[header])
        return rows


# ---------------------------------------------------------------------------
# Reference tables
# ---------------------------------------------------------------------------


def _manifest_sort_key(row):
    return (_as_int(row.get("order_key")),
            str(row.get("shard_id") or ""), _as_int(row.get("pass_index")),
            str(row.get("owner") or ""), _as_int(row.get("example_count")),
            str(row.get("status") or ""))


def build_shards(book):
    """Manifest rows for one shard agree, or raise manifest_conflict."""
    rows = book.rows("shard_id", "owner", "example_count", "pass_index",
                     "order_key", "status")
    shards = {}
    conflicts = 0
    for row in sorted(rows, key=_manifest_sort_key):
        shard_id = row.get("shard_id")
        if shard_id is None:
            continue
        pass_index = _as_int(row.get("pass_index"))
        owner = row.get("owner")
        count = _as_int(row.get("example_count"))
        status = row.get("status")
        known = shards.get(shard_id)
        if known is None:
            shards[shard_id] = {
                "owner": owner,
                "example_count": count,
                "status": status,
                "passes": {pass_index},
            }
        else:
            known["passes"].add(pass_index)
            if (owner != known["owner"] or count != known["example_count"]
                    or status != known["status"]):
                conflicts += 1
    return shards, conflicts


def effective_sizes(shards, book):
    """Manifest count minus holdout rows minus duplicate rows kept at 0."""
    sizes = {shard_id: shard["example_count"]
             for shard_id, shard in shards.items()}
    for row in book.rows("example_id", "shard_id", "reason"):
        shard_id = row.get("shard_id")
        if shard_id in sizes:
            sizes[shard_id] -= 1
    for row in book.rows("group_id", "shard_id", "example_id", "keep"):
        shard_id = row.get("shard_id")
        if shard_id in sizes and _as_int(row.get("keep")) == 0:
            sizes[shard_id] -= 1
    return sizes


def planned_examples(shards, sizes):
    """Effective size summed over every distinct shard and pass pair."""
    total = 0
    for shard_id in sorted(shards):
        effective = sizes.get(shard_id, 0)
        if effective < 0:
            effective = 0
        for _ in sorted(shards[shard_id]["passes"]):
            total += effective
    return total


def ownership_timeline(shards, book, last_sequence):
    """Move rows replace the manifest owner from their effective sequence."""
    by_shard = {}
    for row in book.rows("shard_id", "from_owner", "to_owner",
                         "effective_sequence"):
        shard_id = row.get("shard_id")
        sequence = _as_int(row.get("effective_sequence"))
        if shard_id is None or shard_id not in shards:
            continue
        if sequence > last_sequence:
            continue
        by_shard.setdefault(shard_id, []).append(
            (sequence, str(row.get("to_owner") or "")))
    for shard_id in by_shard:
        # A shared effective sequence is won by the to_owner sorting last.
        by_shard[shard_id].sort(key=lambda item: (item[0], item[1]))
    return by_shard


def owner_at(timeline, shards, shard_id, sequence):
    """The owner in force for a shard at a sequence."""
    moves = timeline.get(shard_id)
    if moves:
        sequences = [item[0] for item in moves]
        position = bisect_right(sequences, sequence)
        if position:
            return moves[position - 1][1]
    shard = shards.get(shard_id)
    return shard["owner"] if shard else None


def roster_owners(book):
    return set(row.get("owner") for row in book.rows("owner", "role", "slots"))


def checkpoint_index(book):
    return {row.get("checkpoint"): row
            for row in book.rows("checkpoint", "micro_cursor", "superseded_by",
                                 "written_at_sequence")
            if row.get("checkpoint")}


# ---------------------------------------------------------------------------
# The single ordered stream
# ---------------------------------------------------------------------------


def order_stream(lines):
    """One stream by ascending sequence. A shared sequence keeps the
    canonically first claimant; every other claimant leaves the stream.

    The returned ledger lists every micro record that must be classified,
    winners and duplicate losers alike, each flagged, ordered by sequence
    and then by canonical form so the winner of a shared sequence comes
    first. Markers survive only as the stream timeline.
    """
    by_sequence = {}
    unusable = []
    for raw in lines:
        if not isinstance(raw, dict):
            continue
        sequence = raw.get("sequence")
        if not isinstance(sequence, int) or isinstance(sequence, bool):
            unusable.append(raw)
            continue
        by_sequence.setdefault(sequence, []).append(raw)
    stream = []
    records = []
    for sequence in sorted(by_sequence):
        claimants = sorted(by_sequence[sequence], key=canonical)
        stream.append(claimants[0])
        for position, raw in enumerate(claimants):
            if raw.get("record") == "micro":
                records.append((raw, position > 0))
    return stream, records, unusable


def phase_openings(stream):
    """Surviving phase_open markers, as a sorted timeline."""
    openings = {}
    for raw in stream:
        if raw.get("record") == "marker" and raw.get("kind") == "phase_open":
            sequence = raw.get("sequence")
            if isinstance(sequence, int) and not isinstance(sequence, bool):
                openings[sequence] = raw.get("phase")
    return openings, sorted(openings)


def phase_at(openings, sequences, sequence):
    """The phase opened by the latest opening at or before the sequence."""
    position = bisect_right(sequences, sequence)
    if position == 0:
        return None
    return openings[sequences[position - 1]]


def build_restarts(book, opening_sequences):
    """Restarts in ascending sequence, each with its in force limit."""
    restarts = []
    for entry in book.entries("restarts", "restarts"):
        if not isinstance(entry, dict):
            continue
        at = entry.get("at_sequence")
        if not isinstance(at, int) or isinstance(at, bool):
            continue
        limit = None
        for opened_at in opening_sequences:
            if opened_at > at:
                limit = opened_at
                break
        restarts.append({
            "at_sequence": at,
            "restart_id": entry.get("restart_id"),
            "resume_checkpoint": entry.get("resume_checkpoint"),
            "limit": limit,
        })
    restarts.sort(key=lambda item: (item["at_sequence"],
                                    str(item["restart_id"] or "")))
    return restarts


def restart_in_force(restarts, sequence):
    """The restart holding at a sequence; a later restart replaces earlier."""
    current = None
    for restart in restarts:
        at = restart["at_sequence"]
        if at > sequence:
            break
        limit = restart["limit"]
        if limit is not None and sequence >= limit:
            continue
        current = restart
    return current


# ---------------------------------------------------------------------------
# Layered settings
# ---------------------------------------------------------------------------


class Settings:
    """The four layered settings, resolved per record or per step."""

    def __init__(self, book):
        self.policy = book.doc("accumulation_policy")
        self.schedule_base = book.doc("schedule_base")
        self.phases = {}
        for entry in book.entries("schedule_phases", "phases"):
            if isinstance(entry, dict) and "phase" in entry:
                self.phases[entry["phase"]] = entry
        self.exceptions = {}
        for entry in book.entries("restart_exceptions", "exceptions"):
            if isinstance(entry, dict) and "restart_id" in entry:
                self.exceptions[entry["restart_id"]] = entry
        self.min_width = _as_int(self.policy.get("minimum_width"))
        self.max_width = _as_int(self.policy.get("maximum_width"))

    def width(self, profile, phase, restart_id):
        """Profile, then exception, then phase, then policy, then clamp."""
        resolved = None
        for layer, key in ((profile, "width_override"),
                           (self.exceptions.get(restart_id),
                            "accumulation_width"),
                           (self.phases.get(phase), "accumulation_width"),
                           (self.policy, "default_width")):
            if not isinstance(layer, dict):
                continue
            value = layer.get(key)
            if value is None or value == "":
                continue
            resolved = _as_int(value)
            break
        if resolved is None:
            resolved = _as_int(self.policy.get("default_width"))
        if self.min_width and resolved < self.min_width:
            resolved = self.min_width
        if self.max_width and resolved > self.max_width:
            resolved = self.max_width
        return resolved

    def carry_partial(self, profile, restart_id):
        """Profile, then exception, then the policy string rule."""
        for layer in (profile, self.exceptions.get(restart_id)):
            if isinstance(layer, dict):
                value = layer.get("carry_partial")
                if value is True or value is False:
                    return value
        return self.policy.get("partial_window_rule") == "carry"

    def decay_span(self, profile):
        if isinstance(profile, dict):
            value = profile.get("decay_span_steps")
            if value is not None and value != "":
                return _as_int(value)
        return _as_int(self.schedule_base.get("decay_span_steps"))

    def base_rate(self, arith, step, span):
        """The rate curve built from the schedule base document alone."""
        peak = _as_int(self.schedule_base.get("peak_rate_milli"))
        floor = _as_int(self.schedule_base.get("floor_rate_milli"))
        warmup = _as_int(self.schedule_base.get("warmup_steps"))
        period = _as_int(self.schedule_base.get("restart_period_steps"))
        if warmup > 0 and step <= warmup:
            return arith.ratio(peak * step, warmup)
        elapsed = step - warmup
        if period > 0:
            elapsed = ((elapsed - 1) % period) + 1
        travelled = elapsed if elapsed < span else span
        return peak - arith.ratio((peak - floor) * travelled, span)

    def scaled_rate(self, arith, base, profile, phase, restart_id):
        """Phase, then profile, then exception, each rounded separately."""
        rate = base
        scales = []
        if phase is not None:
            phase_entry = self.phases.get(phase)
            if isinstance(phase_entry, dict):
                scales.append(phase_entry.get("rate_scale_percent"))
        if isinstance(profile, dict):
            scales.append(profile.get("rate_scale_percent"))
        if restart_id is not None:
            exception = self.exceptions.get(restart_id)
            if isinstance(exception, dict):
                scales.append(exception.get("rate_scale_percent"))
        for scale in scales:
            if scale is None or scale == "":
                continue
            rate = arith.percent(rate, _as_int(scale, 100))
        return rate


# ---------------------------------------------------------------------------
# Probe accounting
# ---------------------------------------------------------------------------


def probe_sort_key(entry):
    return (_as_int(entry.get("step")), str(entry.get("probe") or ""))


def expected_probe_steps(cadence, scale, final_step):
    every = _as_int(cadence.get("eval_every_steps"))
    if every <= 0:
        return []
    stride = every * scale
    if stride <= 0:
        return []
    return list(range(stride, final_step + 1, stride))


def stopping_walk(matched, patience):
    """Early stopping over matched probes in step order."""
    standing = None
    strikes = 0
    stop_step = 0
    for entry in matched:
        metric = _as_int(entry.get("metric_milli"))
        step = _as_int(entry.get("step"))
        if standing is None:
            standing = metric
            strikes = 0
            stop_step = step
            continue
        if metric < standing:
            standing = metric
            strikes = 0
        else:
            strikes += 1
        stop_step = step
        if strikes >= patience:
            break
    return stop_step


def select_best_probe(matched):
    """Lowest metric, then smaller step, then smaller probe identifier."""
    best = None
    best_key = None
    for entry in matched:
        key = (_as_int(entry.get("metric_milli")), _as_int(entry.get("step")),
               str(entry.get("probe") or ""))
        if best_key is None or key < best_key:
            best_key = key
            best = entry
    return best


def settle_checkpoint(checkpoint, index):
    """Follow the supersession chain, stopping at a revisit."""
    seen = []
    current = checkpoint
    cycle = 0
    while current:
        if current in seen:
            cycle = 1
            break
        seen.append(current)
        row = index.get(current)
        if row is None:
            break
        successor = row.get("superseded_by") or ""
        if successor == current:
            cycle = 1
            break
        current = successor or None
    return (seen[-1] if seen else checkpoint), cycle


def stands_alone(checkpoint, index):
    """A checkpoint superseded by nothing stands alone."""
    row = index.get(checkpoint)
    if row is None:
        return True
    return not (row.get("superseded_by") or "")


# ---------------------------------------------------------------------------
# Profile audit
# ---------------------------------------------------------------------------


def loss_scale_reason(value):
    scale = _as_int(value, -1)
    if scale < 64 or scale > 65536:
        return "bad_loss_scale"
    if scale & (scale - 1):
        return "bad_loss_scale"
    return None


def audit_profile(profile, context):
    arith = Arithmetic()
    shards = context["shards"]
    sizes = context["sizes"]
    timeline = context["timeline"]
    roster = context["roster"]
    settings = context["settings"]
    records = context["records"]
    unusable = context["unusable"]
    openings = context["openings"]
    opening_sequences = context["opening_sequences"]
    restarts = context["restarts"]
    checkpoints = context["checkpoints"]
    cadence = context["cadence"]
    probes = context["probes"]
    excluded = set(profile.get("excluded_owners") or [])

    reject_counts = dict.fromkeys(REJECTION_REASONS, 0)
    rejected_examples = dict.fromkeys(REJECTION_REASONS, 0)
    total_records = 0
    accepted = []
    overflow_skipped = 0
    skipped_examples = 0

    def charge(reason, examples):
        reject_counts[reason] += 1
        rejected_examples[reason] += examples

    for raw in unusable:
        if raw.get("record") != "micro":
            continue
        total_records += 1
        charge("unknown_field", _as_int(raw.get("examples")))

    for raw, is_duplicate in records:
        total_records += 1
        examples = _as_int(raw.get("examples"))
        if is_duplicate:
            charge("duplicate_sequence", examples)
            continue
        if frozenset(raw.keys()) != MICRO_KEYS:
            charge("unknown_field", examples)
            continue
        sequence = raw.get("sequence")
        shard_id = raw.get("shard")
        pass_index = _as_int(raw.get("pass_index"))
        shard = shards.get(shard_id)
        effective = sizes.get(shard_id)
        owner = raw.get("owner")
        if shard is None or pass_index not in shard["passes"]:
            reason = "unknown_shard"
        elif shard["status"] == "retired":
            reason = "retired_shard"
        elif effective is None or effective <= 0:
            reason = "empty_shard"
        elif owner not in roster:
            reason = "unknown_owner"
        elif owner in excluded:
            reason = "owner_excluded"
        elif owner != owner_at(timeline, shards, shard_id, sequence):
            reason = "owner_mismatch"
        elif examples <= 0 or examples > effective:
            reason = "examples_out_of_range"
        else:
            reason = loss_scale_reason(raw.get("loss_scale"))
        if reason is not None:
            charge(reason, examples)
            continue
        if _as_int(raw.get("overflow")) == 1:
            overflow_skipped += 1
            skipped_examples += examples
            continue
        accepted.append(raw)

    # Roll back, once per restart, in ascending restart sequence.
    rolled_back = set()
    rolled_back_records = 0
    rolled_back_examples = 0
    for restart in restarts:
        row = checkpoints.get(restart["resume_checkpoint"])
        if row is None:
            continue
        written = _as_int(row.get("written_at_sequence"))
        at = restart["at_sequence"]
        for position, raw in enumerate(accepted):
            sequence = raw.get("sequence")
            if written < sequence < at and position not in rolled_back:
                rolled_back.add(position)
                rolled_back_records += 1
                rolled_back_examples += _as_int(raw.get("examples"))
    survivors = [raw for position, raw in enumerate(accepted)
                 if position not in rolled_back]

    # Cursor drift is an observation, never a number to trust.
    cursor_drift = 0
    for checkpoint in sorted(checkpoints):
        row = checkpoints[checkpoint]
        written = _as_int(row.get("written_at_sequence"))
        rebuilt = sum(1 for raw in survivors if raw.get("sequence") <= written)
        if rebuilt != _as_int(row.get("micro_cursor")):
            cursor_drift += 1

    ledger = walk_ledger(survivors, profile, settings, openings,
                         opening_sequences, restarts, arith)
    optimizer_steps = ledger["steps"]
    rate_table = ledger["rate_table"]

    log_every = _as_int(cadence.get("log_every_steps"))
    if log_every <= 0:
        logged_steps = 0
        arith.zero_denominator += 1
    else:
        logged_steps = optimizer_steps // log_every

    expected = expected_probe_steps(
        cadence, _as_int(profile.get("eval_cadence_scale"), 1), optimizer_steps)
    expected_set = set(expected)
    matched = sorted((entry for entry in probes
                      if _as_int(entry.get("step")) in expected_set),
                     key=probe_sort_key)
    matched_steps = set(_as_int(entry.get("step")) for entry in matched)
    missing_probe = sum(1 for step in expected if step not in matched_steps)
    orphan_probe = sum(1 for entry in probes
                       if _as_int(entry.get("step")) not in expected_set)

    patience = _as_int(cadence.get("patience_probes"))
    stop_step = stopping_walk(matched, patience) if matched else 0
    best = select_best_probe(matched) if matched else None

    best_checkpoint = ""
    supersession_cycle = 0
    averaging_pool = []
    if best is not None:
        best_checkpoint, supersession_cycle = settle_checkpoint(
            best.get("checkpoint"), checkpoints)
        cutoff = stop_step if stop_step else _as_int(best.get("step"))
        pool = [entry for entry in matched
                if _as_int(entry.get("step")) <= cutoff
                and stands_alone(entry.get("checkpoint"), checkpoints)]
        window = _as_int(cadence.get("average_window"))
        pool = pool[-window:] if window > 0 else pool
        averaging_pool = [_as_int(entry.get("metric_milli")) for entry in pool]
    averaged_metric = arith.mean(averaging_pool)

    return {
        "profile": profile.get("name"),
        "accepted_examples": sum(_as_int(raw.get("examples"))
                                for raw in survivors),
        "accepted_records": len(survivors),
        "averaged_metric_milli": averaged_metric,
        "best_checkpoint": best_checkpoint,
        "cursor_drift": cursor_drift,
        "discarded_partial_examples": ledger["discarded_examples"],
        "discarded_partial_records": ledger["discarded_records"],
        "logged_steps": logged_steps,
        "matched_probes": len(matched),
        "missing_probe": missing_probe,
        "optimizer_steps": optimizer_steps,
        "orphan_probe": orphan_probe,
        "overflow_skipped": overflow_skipped,
        "rate_table": rate_table,
        "reject_counts": reject_counts,
        "rejected_examples": rejected_examples,
        "rejected_records": sum(reject_counts.values()),
        "rolled_back_examples": rolled_back_examples,
        "rolled_back_records": rolled_back_records,
        "skipped_examples": skipped_examples,
        "stop_step": stop_step,
        "supersession_cycle": supersession_cycle,
        "total_records": total_records,
        "trailing_partial_examples": ledger["trailing_examples"],
        "trailing_partial_records": ledger["trailing_records"],
        "zero_denominator": arith.zero_denominator,
    }


def walk_ledger(survivors, profile, settings, openings, opening_sequences,
                restarts, arith):
    """The optimizer step ledger as a running state.

    Every window closes against the width in force at the record being
    counted. A restart boundary acts on whatever window is open when the
    stream reaches it, and the fate of that window is the carry decision.
    """
    pending_records = 0
    pending_examples = 0
    steps = 0
    rate_table = []
    discarded_records = 0
    discarded_examples = 0
    fired = set()
    span = settings.decay_span(profile)
    for raw in survivors:
        sequence = raw.get("sequence")
        for restart in restarts:
            at = restart["at_sequence"]
            if at > sequence or at in fired:
                continue
            fired.add(at)
            if not settings.carry_partial(profile, restart["restart_id"]):
                discarded_records += pending_records
                discarded_examples += pending_examples
                pending_records = 0
                pending_examples = 0
        restart = restart_in_force(restarts, sequence)
        restart_id = restart["restart_id"] if restart else None
        phase = phase_at(openings, opening_sequences, sequence)
        width = settings.width(profile, phase, restart_id)
        pending_records += 1
        pending_examples += _as_int(raw.get("examples"))
        if pending_records >= width:
            steps += 1
            rate_table.append([steps, settings.scaled_rate(
                arith, settings.base_rate(arith, steps, span),
                profile, phase, restart_id)])
            pending_records = 0
            pending_examples = 0
    return {
        "steps": steps,
        "rate_table": rate_table,
        "discarded_records": discarded_records,
        "discarded_examples": discarded_examples,
        "trailing_records": pending_records,
        "trailing_examples": pending_examples,
    }


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------


def partition_holds(metrics):
    return (metrics["total_records"] == metrics["accepted_records"]
            + metrics["rejected_records"] + metrics["overflow_skipped"]
            + metrics["rolled_back_records"])


def scenario_report(metrics):
    rates = [entry[1] for entry in metrics["rate_table"]]
    return seal({
        "document": "scenario",
        "profile": metrics["profile"],
        "accepted_examples": metrics["accepted_examples"],
        "accepted_records": metrics["accepted_records"],
        "averaged_metric_milli": metrics["averaged_metric_milli"],
        "best_checkpoint": metrics["best_checkpoint"],
        "cursor_drift": metrics["cursor_drift"],
        "discarded_partial_examples": metrics["discarded_partial_examples"],
        "discarded_partial_records": metrics["discarded_partial_records"],
        "logged_steps": metrics["logged_steps"],
        "matched_probes": metrics["matched_probes"],
        "missing_probe": metrics["missing_probe"],
        "optimizer_steps": metrics["optimizer_steps"],
        "orphan_probe": metrics["orphan_probe"],
        "overflow_skipped": metrics["overflow_skipped"],
        "rate_digest": hashlib.sha256(
            canonical(metrics["rate_table"]).encode("utf-8")).hexdigest()[:16],
        "rate_first": rates[0] if rates else 0,
        "rate_last": rates[-1] if rates else 0,
        "rate_max": max(rates) if rates else 0,
        "rate_min": min(rates) if rates else 0,
        "rate_sum": sum(rates),
        "reject_counts": dict(metrics["reject_counts"]),
        "rejected_records": metrics["rejected_records"],
        "rolled_back_examples": metrics["rolled_back_examples"],
        "rolled_back_records": metrics["rolled_back_records"],
        "stop_step": metrics["stop_step"],
        "supersession_cycle": metrics["supersession_cycle"],
        "total_records": metrics["total_records"],
        "trailing_partial_examples": metrics["trailing_partial_examples"],
        "trailing_partial_records": metrics["trailing_partial_records"],
        "zero_denominator": metrics["zero_denominator"],
    })


def perf_report(all_metrics):
    visible = all_metrics.get("visible")
    profiles = {}
    for name in sorted(all_metrics):
        metrics = all_metrics[name]
        rates = [entry[1] for entry in metrics["rate_table"]]
        profiles[name] = {
            "accepted_examples": metrics["accepted_examples"],
            "accepted_records": metrics["accepted_records"],
            "averaged_metric_milli": metrics["averaged_metric_milli"],
            "best_checkpoint": metrics["best_checkpoint"],
            "optimizer_steps": metrics["optimizer_steps"],
            "rate_last": rates[-1] if rates else 0,
            "stop_step": metrics["stop_step"],
        }
    deltas = {}
    if visible is not None:
        for name in sorted(all_metrics):
            if name == "visible":
                continue
            metrics = all_metrics[name]
            deltas[name] = {
                "accepted_examples_delta":
                    metrics["accepted_examples"] - visible["accepted_examples"],
                "optimizer_steps_delta":
                    metrics["optimizer_steps"] - visible["optimizer_steps"],
            }
    totals = {
        "accepted_examples": sum(m["accepted_examples"]
                                 for m in all_metrics.values()),
        "accepted_records": sum(m["accepted_records"]
                                for m in all_metrics.values()),
        "optimizer_steps": sum(m["optimizer_steps"]
                               for m in all_metrics.values()),
        "rejected_records": sum(m["rejected_records"]
                                 for m in all_metrics.values()),
        "rolled_back_records": sum(m["rolled_back_records"]
                                   for m in all_metrics.values()),
        "skipped_records": sum(m["overflow_skipped"]
                               for m in all_metrics.values()),
    }
    identity_checks = {
        "coverage_gap_total": sum(m["coverage_gap"]
                                   for m in all_metrics.values()),
        "partition_holds": 1 if all(partition_holds(m)
                                     for m in all_metrics.values()) else 0,
        "profiles_checked": len(all_metrics),
    }
    return seal({
        "document": "perf_report",
        "deltas_vs_visible": deltas,
        "identity_checks": identity_checks,
        "profiles": profiles,
        "totals": totals,
    })


def bottleneck_report(all_metrics):
    profiles = {}
    for name in sorted(all_metrics):
        metrics = all_metrics[name]
        stage_records = dict.fromkeys(STAGES, 0)
        stage_examples = dict.fromkeys(STAGES, 0)
        for reason in REJECTION_REASONS:
            if reason in OWNERSHIP_REASONS:
                stage = "ownership"
            elif reason in VALIDATION_REASONS:
                stage = "validation"
            else:
                stage = "validation"
            stage_records[stage] += metrics["reject_counts"][reason]
            stage_examples[stage] += metrics["rejected_examples"][reason]
        stage_records["rollback"] = metrics["rolled_back_records"]
        stage_examples["rollback"] = metrics["rolled_back_examples"]
        stage_records["partial_discard"] = metrics["discarded_partial_records"]
        stage_examples["partial_discard"] = metrics[
            "discarded_partial_examples"]
        stage_records["trailing"] = metrics["trailing_partial_records"]
        stage_examples["trailing"] = metrics["trailing_partial_examples"]
        stages = [{"stage": stage,
                   "records_removed": stage_records[stage],
                   "examples_removed": stage_examples[stage]}
                  for stage in STAGES]
        stages.sort(key=lambda entry: (-entry["records_removed"],
                                       entry["stage"]))
        candidates = [reason for reason in REJECTION_REASONS
                      if metrics["reject_counts"][reason] > 0]
        dominant_reason = "none"
        if candidates:
            dominant_reason = sorted(
                candidates,
                key=lambda reason: (-metrics["reject_counts"][reason],
                                    reason))[0]
        profiles[name] = {
            "stages": stages,
            "dominant_stage": stages[0]["stage"],
            "dominant_reason": dominant_reason,
        }
    return seal({
        "document": "bottleneck_analysis",
        "profiles": profiles,
    })


def recommendations(all_metrics):
    per_profile = {}
    fired = []
    for name in sorted(all_metrics):
        metrics = all_metrics[name]
        codes = [code for code, predicate in RECOMMENDATION_RULES
                 if predicate(metrics)]
        if not codes:
            codes = ["hold-current-plan"]
        per_profile[name] = codes
        for code in codes:
            if code != "hold-current-plan" and code not in fired:
                fired.append(code)
    ordered = [code for code, _ in RECOMMENDATION_RULES if code in fired]
    if not ordered:
        ordered = ["hold-current-plan"]
    return seal({
        "document": "recommendations",
        "per_profile": per_profile,
        "codes": ordered,
    })


def data_quality(all_metrics, manifest_conflict):
    profiles = {}
    for name in sorted(all_metrics):
        metrics = all_metrics[name]
        profiles[name] = {
            "reject_counts": dict(metrics["reject_counts"]),
            "overflow_skipped": metrics["overflow_skipped"],
            "cursor_drift": metrics["cursor_drift"],
            "manifest_conflict": manifest_conflict,
            "supersession_cycle": metrics["supersession_cycle"],
            "zero_denominator": metrics["zero_denominator"],
            "partition": {
                "accepted_records": metrics["accepted_records"],
                "holds": 1 if partition_holds(metrics) else 0,
                "rejected_records": metrics["rejected_records"],
                "rolled_back_records": metrics["rolled_back_records"],
                "skipped_records": metrics["overflow_skipped"],
                "total_records": metrics["total_records"],
            },
            "coverage": {
                "accepted_examples": metrics["accepted_examples"],
                "coverage_gap": metrics["coverage_gap"],
                "planned_examples": metrics["planned_examples"],
            },
        }
    return seal({
        "document": "data_quality",
        "profiles": profiles,
    })


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def run(data_dir, out_dir):
    docs, tables, lines = load_archive(data_dir)
    book = Book(docs, tables)

    profiles = [entry for entry in book.entries("profiles", "profiles")
                if isinstance(entry, dict) and entry.get("name")]
    if not profiles:
        profiles = [{"name": "visible"}]

    stream, records, unusable = order_stream(lines)
    openings, opening_sequences = phase_openings(stream)
    last_sequence = max((raw.get("sequence") for raw in stream
                         if isinstance(raw.get("sequence"), int)), default=0)

    shards, manifest_conflict = build_shards(book)
    sizes = effective_sizes(shards, book)
    planned = planned_examples(shards, sizes)
    timeline = ownership_timeline(shards, book, last_sequence)
    restarts = build_restarts(book, opening_sequences)
    checkpoints = checkpoint_index(book)
    probes = [entry for entry in book.entries("eval_probes", "probes")
              if isinstance(entry, dict)]
    cadence = book.doc("cadence")
    settings = Settings(book)

    context = {
        "shards": shards,
        "sizes": sizes,
        "timeline": timeline,
        "roster": roster_owners(book),
        "settings": settings,
        "records": records,
        "unusable": unusable,
        "openings": openings,
        "opening_sequences": opening_sequences,
        "restarts": restarts,
        "checkpoints": checkpoints,
        "probes": probes,
        "cadence": cadence,
    }

    outputs = {}
    all_metrics = {}
    for profile in profiles:
        metrics = audit_profile(profile, context)
        metrics["planned_examples"] = planned
        metrics["coverage_gap"] = planned - metrics["accepted_examples"]
        all_metrics[profile["name"]] = metrics
        outputs["scenario_%s.json" % profile["name"]] = scenario_report(metrics)

    outputs["perf_report.json"] = perf_report(all_metrics)
    outputs["bottleneck_analysis.json"] = bottleneck_report(all_metrics)
    outputs["recommendations.json"] = recommendations(all_metrics)
    outputs["data_quality.json"] = data_quality(all_metrics, manifest_conflict)

    os.makedirs(out_dir, exist_ok=True)
    for name in sorted(outputs):
        with open(os.path.join(out_dir, name), "wb") as handle:
            handle.write(canonical(outputs[name]).encode("utf-8"))
            handle.write(b"\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Chainfold run auditor")
    parser.add_argument("--data", required=True, help="archive directory")
    parser.add_argument("--out", required=True, help="output directory")
    args = parser.parse_args(argv)
    run(args.data, args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
