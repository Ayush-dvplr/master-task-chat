#!/usr/bin/env python3
"""Interval basis recovery reproducer.

Rebuilds the durable render track state from the keyframe interval ledger (the
authority layer), the replayed encode operations journal and the maps held under
the input directory.  No compiled, index or runtime layer is consulted: the
durable state is a function of the authority records, the journal and the maps.

Standard library only.  Deterministic: two runs over the same input directory
produce byte identical output.

Usage:
    python3 transform.py --input <data dir> --out <out dir>
"""

import argparse
import json
import os

MODULUS = 100003
REQUIRED_DOMAIN = "presentation_interval_id"

LEDGER_NAME = "keyframe_interval_ledger.jsonl"
JOURNAL_NAME = "encode_operations_journal.jsonl"
DECODE_MAP_NAME = "decode_order_map.json"
PARTITION_MAP_NAME = "track_partition_map.json"
FIXTURES_NAME = "interval_conformance_fixtures.json"


def read_json(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def read_jsonl(path):
    rows = []
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def record_rank(record):
    """Settlement order for competing records of one render track.

    Higher effective generation first.  Inside one generation the record the
    durable state settles on is decided by evidence, not by recorded order: the
    conformance fixtures prove, for the one same-generation pair they cover, that
    the authority-service record stands over the migration-service record.
    """
    return (
        -record["effective_generation"],
        0 if record["recorded_by"] == "authority-service" else 1,
        record["seq"],
    )


class Recovery:
    """Carries the ledger and the journal through the recovery transitions."""

    def __init__(self, ledger, journal, decode_map, partition_map, fixtures=None):
        self.records = sorted(ledger, key=lambda r: r["seq"])
        self.by_seq = {r["seq"]: dict(r) for r in self.records}
        self.journal = sorted(journal, key=lambda r: r["journal_seq"])
        self.decode_map = {
            (row["alt_key"], row["lineage_anchor"]): row["canonical_value"]
            for row in decode_map["rows"]
        }
        self.multipliers = {
            entry["entity"]: entry["multiplier"] for entry in partition_map["entries"]
        }
        self.fixtures = fixtures or {}
        self.correction = None
        self.withdrawn = set()
        self.standing = {}
        self.in_effect = {}
        self.retired = set()
        self.active_anchor = {}
        self.pre_replay_anchor = {}
        self._prepare()

    # ------------------------------------------------------------------ setup

    def entity_records(self, entity):
        return [self.by_seq[r["seq"]] for r in self.records if r["entity"] == entity]

    def declare_record(self, entity):
        for record in self.entity_records(entity):
            if record["op"] == "declare":
                return record
        return None

    def applied_generation(self):
        generations = [
            row["applied_generation"] for row in self.journal if row["status"] == "applied"
        ]
        return max(generations) if generations else 0

    def _prepare(self):
        applied = self.applied_generation()
        for record in self.records:
            if record["op"] == "retire":
                if record["effective_generation"] <= applied:
                    self.retired.add(record["entity"])
                continue
            if record["effective_generation"] <= applied:
                self.in_effect.setdefault(record["entity"], set()).add(record["seq"])
        for entity in self.in_effect:
            self.standing[entity] = self._best(entity)
        # Pre-replay registry anchors.  A pending supersede_lineage names the
        # anchor it retires, which is the anchor the registry holds active until
        # the replay advances it.
        for row in self.journal:
            if row["op"] == "supersede_lineage" and row["status"] == "pending":
                self.pre_replay_anchor[row["entity"]] = row["retire_anchor"]
        for entity in sorted(set(self.standing) | self.retired):
            if entity in self.pre_replay_anchor:
                continue
            standing = self.standing.get(entity)
            anchor = self.by_seq[standing].get("lineage_anchor") if standing else None
            if anchor in (None, "pending"):
                declare = self.declare_record(entity)
                anchor = declare["lineage_anchor"] if declare else None
            self.pre_replay_anchor[entity] = anchor

    def _best(self, entity):
        candidates = [
            self.by_seq[seq]
            for seq in self.in_effect.get(entity, ())
            if seq not in self.withdrawn
        ]
        if not candidates:
            return None
        return min(candidates, key=record_rank)["seq"]

    def _preceding(self, entity, seq):
        """The record immediately preceding `seq` for that render track."""
        earlier = [
            r
            for r in self.entity_records(entity)
            if r["op"] != "retire" and r["seq"] < seq and r["seq"] not in self.withdrawn
        ]
        if earlier:
            return earlier[-1]["seq"]
        declare = self.declare_record(entity)
        return declare["seq"] if declare else None

    def surviving_records(self):
        """One standing record per active render track, ordered by record seq."""
        return sorted(
            self.standing[entity] for entity in self.standing if entity not in self.retired
        )

    # ----------------------------------------------------------------- replay

    def replay(self):
        for row in self.journal:
            if row["status"] != "pending":
                continue
            if row["op"] == "supersede_lineage":
                declare = self.declare_record(row["entity"])
                if declare is not None:
                    self.active_anchor[row["entity"]] = declare["lineage_anchor"]
            elif row["op"] == "apply_amendment":
                entity = row["entity"]
                self.in_effect.setdefault(entity, set()).add(row["record_seq"])
                self.standing[entity] = self._best(entity)
            elif row["op"] == "rollback_amendment":
                survivors = self.surviving_records()
                position = row["target_position"]
                if position < 1 or position > len(survivors):
                    raise ValueError("target_position out of range: %d" % position)
                target_seq = survivors[position - 1]
                target = self.by_seq[target_seq]
                self.withdrawn.add(target_seq)
                self.in_effect[target["entity"]].discard(target_seq)
                self.standing[target["entity"]] = self._preceding(target["entity"], target_seq)
            else:
                raise ValueError("unknown journal operation: %s" % row["op"])
        for entity in self.standing:
            if entity not in self.active_anchor:
                self.active_anchor[entity] = self.pre_replay_anchor.get(entity)
        for entity in self.retired:
            declare = self.declare_record(entity)
            self.active_anchor[entity] = declare["lineage_anchor"] if declare else None

    # ------------------------------------------------------------- correction

    def detect_defect(self):
        """Find the authority record whose recorded domain forces a conversion it
        cannot itself settle: it is not in the contract's reference domain and its
        lineage anchor is deferred, so no derived layer can convert it."""
        defects = [
            r
            for r in self.records
            if r["op"] != "retire"
            and r["reference_domain"] != REQUIRED_DOMAIN
            and r.get("lineage_anchor") == "pending"
        ]
        if len(defects) > 1:
            raise ValueError("more than one deferred alternate-domain record found")
        return defects[0] if defects else None

    def correct_record(self):
        defect = self.detect_defect()
        if defect is None:
            return None
        entity = defect["entity"]
        anchor = self.active_anchor.get(entity)
        key = (defect["value"], anchor)
        if key not in self.decode_map:
            raise KeyError("no decode_order_map row for %r" % (key,))
        canonical = self.decode_map[key]
        self.correction = {
            "record_seq": defect["seq"],
            "entity": entity,
            "field": defect["field"],
            "recorded_reference_domain": defect["reference_domain"],
            "required_reference_domain": REQUIRED_DOMAIN,
            "recorded_value": defect["value"],
            "canonical_value": canonical,
            "restored_lineage_anchor": anchor,
        }
        # Rewrite the one authority record: the published value now stands on
        # the record itself, in the contract's reference domain.
        self.by_seq[defect["seq"]] = dict(
            defect,
            reference_domain=REQUIRED_DOMAIN,
            value=canonical,
            lineage_anchor=anchor,
        )
        return self.correction

    # ------------------------------------------------------------------ state

    def published_value(self, entity):
        record = self.by_seq[self.standing[entity]]
        if record["reference_domain"] == REQUIRED_DOMAIN:
            return record["value"]
        key = (record["value"], self.active_anchor[entity])
        if key not in self.decode_map:
            raise KeyError("no decode_order_map row for %r" % (key,))
        return self.decode_map[key]

    def active_entities(self):
        return sorted(entity for entity in self.standing if entity not in self.retired)

    def state(self):
        entries = []
        for entity in self.active_entities():
            value = self.published_value(entity)
            multiplier = self.multipliers[entity]
            entries.append(
                {
                    "entity": entity,
                    "record_seq": self.standing[entity],
                    "value": value,
                    "multiplier": multiplier,
                    "weighted": value * multiplier,
                    "lineage_anchor": self.active_anchor[entity],
                    "state": "active",
                }
            )
        return entries

    def generation(self):
        generations = [self.by_seq[seq]["effective_generation"] for seq in self.standing.values()]
        generations += [row["applied_generation"] for row in self.journal]
        return max(generations)

    def digest(self, entries=None):
        if entries is None:
            entries = self.state()
        return sum(entry["weighted"] for entry in entries) % MODULUS

    def ranked(self, entries):
        ordered = sorted(entries, key=lambda entry: (-entry["weighted"], entry["entity"]))
        for position, entry in enumerate(ordered, start=1):
            entry["rank"] = position
        return sorted(entries, key=lambda entry: entry["entity"])


def pre_repair_state(recovery):
    """The state as it stood before the repair: the generation the applied
    operations reached, with deferred conversions resolved against the
    pre-replay registry anchors."""
    entries = []
    for entity in sorted(recovery.standing):
        if entity in recovery.retired:
            continue
        record = recovery.by_seq[recovery.standing[entity]]
        anchor = recovery.pre_replay_anchor.get(entity)
        if record["reference_domain"] == REQUIRED_DOMAIN:
            value = record["value"]
        else:
            key = (record["value"], anchor)
            if key not in recovery.decode_map:
                raise KeyError("no decode_order_map row for %r" % (key,))
            value = recovery.decode_map[key]
        multiplier = recovery.multipliers[entity]
        entries.append(
            {
                "entity": entity,
                "record_seq": record["seq"],
                "value": value,
                "multiplier": multiplier,
                "weighted": value * multiplier,
                "lineage_anchor": anchor,
                "state": "active",
            }
        )
    return entries


def verify_fixtures(recovery, pre_state):
    fixtures = recovery.fixtures
    if not fixtures:
        return
    cohort = fixtures.get("reference_cohort") or []
    expected = fixtures.get("reference_cohort_digest")
    if cohort and expected is not None:
        by_entity = {entry["entity"]: entry for entry in pre_state}
        digest = sum(by_entity[name]["weighted"] for name in cohort if name in by_entity) % MODULUS
        if digest != expected:
            raise AssertionError(
                "reference cohort digest %d does not reproduce %d" % (digest, expected)
            )
    final_state = {entry["entity"]: entry for entry in recovery.state()}
    for pair in fixtures.get("known_pairs") or []:
        entry = final_state.get(pair["entity"])
        if entry is None:
            raise AssertionError("known pair entity missing from the durable state")
        if entry["value"] != pair["published_value"]:
            raise AssertionError(
                "known pair value mismatch for %s: %d" % (pair["entity"], entry["value"])
            )
        if entry["multiplier"] != pair["multiplier"] or entry["weighted"] != pair["weighted"]:
            raise AssertionError("known pair weighting mismatch for %s" % pair["entity"])
    expected_count = fixtures.get("active_entity_count")
    if expected_count is not None and len(recovery.active_entities()) != expected_count:
        raise AssertionError(
            "active entity count %d does not match %d"
            % (len(recovery.active_entities()), expected_count)
        )


def run(input_dir):
    """Replay the journal, settle the deferred anchor, correct the record."""
    ledger = read_jsonl(os.path.join(input_dir, LEDGER_NAME))
    journal = read_jsonl(os.path.join(input_dir, JOURNAL_NAME))
    decode_map = read_json(os.path.join(input_dir, DECODE_MAP_NAME))
    partition_map = read_json(os.path.join(input_dir, PARTITION_MAP_NAME))
    fixtures_path = os.path.join(input_dir, FIXTURES_NAME)
    fixtures = read_json(fixtures_path) if os.path.exists(fixtures_path) else None

    recovery = Recovery(ledger, journal, decode_map, partition_map, fixtures)
    pre_state = pre_repair_state(recovery)
    recovery.replay()
    recovery.correct_record()
    verify_fixtures(recovery, pre_state)
    return recovery, pre_state


def reproduced_state(recovery):
    entries = recovery.ranked(recovery.state())
    correction = recovery.correction or {}
    return {
        "generation": recovery.generation(),
        "digest": recovery.digest(recovery.state()),
        "root_cause_entity": correction.get("entity"),
        "canonical_value": correction.get("canonical_value"),
        "entries": [
            {
                "entity": entry["entity"],
                "value": entry["value"],
                "multiplier": entry["multiplier"],
                "weighted": entry["weighted"],
                "rank": entry["rank"],
            }
            for entry in entries
        ],
    }


def main():
    parser = argparse.ArgumentParser(description="Interval basis recovery reproducer")
    parser.add_argument("--input", required=True, help="directory holding the input documents")
    parser.add_argument("--out", required=True, help="directory to write reproduced_state.json into")
    args = parser.parse_args()

    recovery, _ = run(args.input)
    state = reproduced_state(recovery)
    os.makedirs(args.out, exist_ok=True)
    path = os.path.join(args.out, "reproduced_state.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2)
        handle.write("\n")


if __name__ == "__main__":
    main()
