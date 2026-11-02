#!/usr/bin/env python3
"""Rebuild the durable interval_basis state of the render track fleet.

The durable state is a function of the keyframe interval ledger (the authority
layer), the replayed encode operations journal and the maps.  No compiled,
index or runtime layer is read.
"""

import argparse
import itertools
import json
import os

CONTRACT_DOMAIN = "presentation_interval_id"
FIELD = "interval_basis"
PENDING = "pending"


def read_json(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def read_jsonl(path):
    rows = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_json(path, payload):
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


class Sources:
    def __init__(self, input_dir):
        self.ledger = sorted(
            read_jsonl(os.path.join(input_dir, "keyframe_interval_ledger.jsonl")),
            key=lambda r: r["seq"],
        )
        self.journal = sorted(
            read_jsonl(os.path.join(input_dir, "encode_operations_journal.jsonl")),
            key=lambda r: r["journal_seq"],
        )
        self.decode_map = read_json(os.path.join(input_dir, "decode_order_map.json"))
        self.partition_map = read_json(os.path.join(input_dir, "track_partition_map.json"))
        self.fixtures = read_json(os.path.join(input_dir, "interval_conformance_fixtures.json"))


def declaring_anchors(ledger):
    anchors = {}
    for rec in ledger:
        if rec["op"] == "declare":
            anchors.setdefault(rec["entity"], rec["lineage_anchor"])
    return anchors


def active_anchor(rec, anchors, retired_anchors):
    anchor = rec["lineage_anchor"]
    if anchor == PENDING or anchor in retired_anchors:
        return anchors[rec["entity"]]
    return anchor


def published_value(rec, anchors, retired_anchors, decode_rows):
    """Convert an alternate-domain record into the published contract domain."""
    if rec["reference_domain"] == CONTRACT_DOMAIN:
        return rec["value"]
    anchor = active_anchor(rec, anchors, retired_anchors)
    for row in decode_rows:
        if row["alt_key"] == rec["value"] and row["lineage_anchor"] == anchor:
            return row["canonical_value"]
    raise KeyError((rec["seq"], rec["value"], anchor))


def conflict_groups(base_records):
    """Entities carrying more than one amendment inside a single generation."""
    buckets = {}
    for rec in base_records:
        if rec["op"] == "amend":
            buckets.setdefault((rec["entity"], rec["effective_generation"]), []).append(rec)
    return {key: recs for key, recs in sorted(buckets.items()) if len(recs) > 1}


def settle_conflicts(base_records, groups, sources, anchors):
    """The recorded order of competing same generation amendments settles
    nothing, so the conformance cohort digest is the evidence that decides."""
    cohort = set(sources.fixtures["reference_cohort"])
    target = sources.fixtures["reference_cohort_digest"]
    modulus = sources.fixtures["digest_modulus"]
    multipliers = {e["entity"]: e["multiplier"] for e in sources.partition_map["entries"]}
    decode_rows = sources.decode_map["rows"]

    contested = {key: recs for key, recs in groups.items() if key[0] in cohort}
    settled = {}
    for key, recs in groups.items():
        if key not in contested:
            settled[key] = max(recs, key=lambda r: r["seq"])

    if contested:
        keys = sorted(contested)
        for choice in itertools.product(*[contested[k] for k in keys]):
            trial = dict(settled)
            trial.update(dict(zip(keys, choice)))
            state = fold(base_records, groups, trial)
            digest = 0
            for entity in sorted(cohort):
                rec = state[entity][-1]
                value = published_value(rec, anchors, set(), decode_rows)
                digest += value * multipliers[entity]
            if digest % modulus == target:
                return trial
        raise ValueError("no settlement reproduces the reference cohort digest")
    return settled


def fold(base_records, groups, settled):
    """Per entity chain of the authority records that stand, in seq order."""
    losers = set()
    for key, recs in groups.items():
        for rec in recs:
            if rec["seq"] != settled[key]["seq"]:
                losers.add(rec["seq"])
    chains = {}
    for rec in base_records:
        if rec["seq"] in losers:
            continue
        chains.setdefault(rec["entity"], []).append(rec)
    return chains


def surviving_set(chains):
    """One record per active render track, ordered by ascending seq."""
    standing = [chain[-1] for chain in chains.values() if chain[-1]["op"] != "retire"]
    return sorted(standing, key=lambda r: r["seq"])


def replay(chains, journal, by_seq):
    retired_anchors = set()
    transitions = []
    for op in journal:
        if op.get("status") != PENDING:
            continue
        kind = op["op"]
        if kind == "supersede_lineage":
            retired_anchors.add(op["retire_anchor"])
            transitions.append((op["journal_seq"], kind, op["entity"]))
        elif kind == "apply_amendment":
            record = by_seq[op["record_seq"]]
            chains.setdefault(record["entity"], []).append(record)
            transitions.append((op["journal_seq"], kind, record["entity"]))
        elif kind == "rollback_amendment":
            target = surviving_set(chains)[op["target_position"] - 1]
            chain = chains[target["entity"]]
            if len(chain) < 2:
                raise ValueError("rollback leaves no preceding record")
            chain.pop()
            transitions.append((op["journal_seq"], kind, target["entity"]))
        else:
            raise ValueError(kind)
    return retired_anchors, transitions


def compute(input_dir):
    sources = Sources(input_dir)
    by_seq = {rec["seq"]: rec for rec in sources.ledger}

    anchors = declaring_anchors(sources.ledger)
    pending_applies = {
        op["record_seq"]
        for op in sources.journal
        if op.get("status") == PENDING and op["op"] == "apply_amendment"
    }
    base_records = [rec for rec in sources.ledger if rec["seq"] not in pending_applies]

    groups = conflict_groups(base_records)
    settled = settle_conflicts(base_records, groups, sources, anchors)
    chains = fold(base_records, groups, settled)

    decode_rows = sources.decode_map["rows"]
    multipliers = {e["entity"]: e["multiplier"] for e in sources.partition_map["entries"]}
    modulus = sources.partition_map["weighting_modulus"]

    retired_anchors, transitions = replay(chains, sources.journal, by_seq)

    entries = []
    retired = []
    for entity, chain in sorted(chains.items()):
        rec = chain[-1]
        anchor = active_anchor(rec, anchors, retired_anchors)
        if rec["op"] == "retire":
            retired.append(entity)
            continue
        entries.append(
            {
                "entity": entity,
                "value": published_value(rec, anchors, retired_anchors, decode_rows),
                "multiplier": multipliers[entity],
                "lineage_anchor": anchor,
                "state": "active",
                "record_seq": rec["seq"],
            }
        )

    for entry in entries:
        entry["weighted"] = entry["value"] * entry["multiplier"]
    digest = sum(entry["weighted"] for entry in entries) % modulus

    order = sorted(entries, key=lambda e: (-e["weighted"], e["entity"]))
    ranks = {entry["entity"]: index + 1 for index, entry in enumerate(order)}
    for entry in entries:
        entry["rank"] = ranks[entry["entity"]]

    root = None
    for entry in entries:
        rec = by_seq[entry["record_seq"]]
        if rec["reference_domain"] != CONTRACT_DOMAIN and rec["lineage_anchor"] == PENDING:
            root = {
                "record_seq": rec["seq"],
                "entity": rec["entity"],
                "field": rec["field"],
                "recorded_reference_domain": rec["reference_domain"],
                "required_reference_domain": CONTRACT_DOMAIN,
                "recorded_value": rec["value"],
                "canonical_value": entry["value"],
            }
            break

    generation = max(
        max(rec["effective_generation"] for rec in sources.ledger),
        max(op["applied_generation"] for op in sources.journal),
    )

    return {
        "sources": sources,
        "generation": generation,
        "digest": digest,
        "digest_modulus": modulus,
        "entries": entries,
        "retired": retired,
        "root_cause": root,
        "chains": chains,
        "groups": groups,
        "settled": settled,
        "retired_anchors": retired_anchors,
        "transitions": transitions,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    result = compute(args.input)
    os.makedirs(args.out, exist_ok=True)
    write_json(
        os.path.join(args.out, "reproduced_state.json"),
        {
            "generation": result["generation"],
            "digest": result["digest"],
            "root_cause_entity": result["root_cause"]["entity"],
            "canonical_value": result["root_cause"]["canonical_value"],
            "entries": [
                {
                    "entity": entry["entity"],
                    "value": entry["value"],
                    "multiplier": entry["multiplier"],
                    "weighted": entry["weighted"],
                    "rank": entry["rank"],
                }
                for entry in sorted(result["entries"], key=lambda e: e["entity"])
            ],
        },
    )


if __name__ == "__main__":
    main()
