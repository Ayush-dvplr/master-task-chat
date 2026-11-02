#!/usr/bin/env python3
"""Reference recovery for 072aced5-ac2b-5029-8831-e570547ce89a.

Everything below is computed from the evidence shipped under the agent data
directory. The authority layer is the only source of published values; the
derived, index, runtime and journal layers are treated as consequences.
"""

import json
import os

DATA = os.path.join("/app", "data")
OUT = os.path.join("/app", "out")
MODULUS = 100003
CANON_DOMAIN = "presentation_interval_id"
ALT_DOMAIN = "decode_order_index"
FIELD = "interval_basis"

NAMES = {'authority': 'keyframe_interval_ledger.jsonl', 'derived': 'generated_interval_snapshot.json', 'index': 'interval_index_manifest.json', 'runtime': 'encoder_runtime_state.json', 'journal': 'encode_operations_journal.jsonl', 'reconcile': 'interval_reconciliation_report.json', 'policy': 'interval_authority_policy.md', 'map': 'decode_order_map.json', 'fixtures': 'interval_conformance_fixtures.json', 'snapshot': 'pre_incident_interval_snapshot.json', 'partitions': 'track_partition_map.json', 'operations': 'operations_catalogue.json', 'compiler': 'generated_interval_snapshot_compiler_notes.md'}
ROLE_PATHS = {'core': '/app/out/normalized.jsonl', 'metrics': '/app/out/product_summary.json', 'resolution': '/app/out/product_summary.json', 'report': '/app/out/data_quality.json', 'verdict': '/app/out/data_quality.json', 'summary': '/app/out/summary.json'}
PARTITION_PATHS = {'group_a': {'central': '/app/out/region_central.json', 'east': '/app/out/region_east.json', 'north': '/app/out/region_north.json', 'south': '/app/out/region_south.json', 'west': '/app/out/region_west.json'}, 'group_b': {'consumer': '/app/out/segment_consumer.json', 'corporate': '/app/out/segment_corporate.json', 'enterprise': '/app/out/segment_enterprise.json', 'smb': '/app/out/segment_smb.json'}}
SCRIPT_PATH = '/app/out/transform.py'
REJECTED_HYPOTHESIS = "stale_index_generation"

REPRODUCER = "#!/usr/bin/env python3\n\"\"\"Recompute the canonical render tracks state from the authority layer alone.\n\nThe script reads only the directory given on the command line. It resolves\nevery authority record, converts alternate reference domain records through the\ngeneration map using the lineage anchor that survives the replayed lineage\nsupersession, applies the weighting multipliers, ranks the render tracks by\ndescending weighted value with an ascending name tie break and reports the\nstate digest.\n\"\"\"\n\nimport argparse\nimport json\nimport os\n\nMODULUS = 100003\nCANON_DOMAIN = \"presentation_interval_id\"\nLEDGER_NAME = \"keyframe_interval_ledger.jsonl\"\nMAP_NAME = \"decode_order_map.json\"\nJOURNAL_NAME = \"encode_operations_journal.jsonl\"\nWEIGHT_NAME = \"track_partition_map.json\"\n\n\ndef load_jsonl(path):\n    rows = []\n    with open(path, \"r\", encoding=\"utf-8\") as handle:\n        for line in handle:\n            line = line.strip()\n            if line:\n                rows.append(json.loads(line))\n    return rows\n\n\ndef load_json(path):\n    with open(path, \"r\", encoding=\"utf-8\") as handle:\n        return json.load(handle)\n\n\ndef resolve(input_dir):\n    records = load_jsonl(os.path.join(input_dir, LEDGER_NAME))\n    generation_map = load_json(os.path.join(input_dir, MAP_NAME))\n    journal = load_jsonl(os.path.join(input_dir, JOURNAL_NAME))\n    weights = load_json(os.path.join(input_dir, WEIGHT_NAME))\n\n    multiplier = {}\n    for row in weights[\"entries\"]:\n        multiplier[row[\"entity\"]] = row[\"multiplier\"]\n\n    generation = 0\n    for op in journal:\n        if op[\"applied_generation\"] > generation:\n            generation = op[\"applied_generation\"]\n\n    declared_anchor = {}\n    for row in records:\n        if row[\"op\"] == \"declare\":\n            declared_anchor[row[\"entity\"]] = row[\"lineage_anchor\"]\n\n    retired_anchor = {}\n    for op in journal:\n        if op[\"op\"] == \"supersede_lineage\" and op[\"applied_generation\"] <= generation:\n            retired_anchor[op[\"entity\"]] = op[\"retire_anchor\"]\n\n    def precedence(row):\n        return (row[\"effective_generation\"],\n                1 if row[\"recorded_by\"] == \"authority-service\" else 0,\n                row[\"seq\"])\n\n    kept = {}\n    retired = []\n    for row in sorted(records, key=precedence):\n        if row[\"effective_generation\"] > generation:\n            continue\n        if row[\"op\"] == \"retire\":\n            retired.append(row[\"entity\"])\n            kept.pop(row[\"entity\"], None)\n            continue\n        kept[row[\"entity\"]] = row\n\n    # A rollback operation addresses its target by position in the surviving\n    # set, so the set has to be settled first. The ordering is recomputed for\n    # each rollback because an earlier rollback moves its subject back onto a\n    # lower sequence, which shifts every position after it.\n    for op in journal:\n        if op[\"op\"] != \"rollback_amendment\":\n            continue\n        if op[\"applied_generation\"] > generation:\n            continue\n        order = [e for e, _ in sorted(kept.items(), key=lambda kv: kv[1][\"seq\"])]\n        position = op[\"target_position\"]\n        if position < 1 or position > len(order):\n            continue\n        subject = order[position - 1]\n        current = kept[subject]\n        prior = [r for r in records\n                 if r[\"entity\"] == subject\n                 and r[\"op\"] in (\"declare\", \"amend\")\n                 and r[\"effective_generation\"] <= generation\n                 and precedence(r) < precedence(current)]\n        if prior:\n            kept[subject] = max(prior, key=precedence)\n\n    deferred_entity = None\n    deferred_seq = 0\n    for row in records:\n        if row[\"reference_domain\"] != CANON_DOMAIN and row[\"lineage_anchor\"] == \"pending\":\n            if row[\"seq\"] > deferred_seq:\n                deferred_seq = row[\"seq\"]\n                deferred_entity = row[\"entity\"]\n\n    entries = []\n    for entity in sorted(kept):\n        row = kept[entity]\n        value = row[\"value\"]\n        if row[\"reference_domain\"] != CANON_DOMAIN:\n            anchor = row[\"lineage_anchor\"]\n            if anchor == \"pending\" or anchor == retired_anchor.get(entity):\n                anchor = declared_anchor[entity]\n            for candidate in generation_map[\"rows\"]:\n                if candidate[\"alt_key\"] == value and candidate[\"lineage_anchor\"] == anchor:\n                    value = candidate[\"canonical_value\"]\n                    break\n        factor = multiplier[entity]\n        entries.append({\n            \"entity\": entity,\n            \"value\": value,\n            \"multiplier\": factor,\n            \"weighted\": value * factor,\n        })\n\n    digest = 0\n    for item in entries:\n        digest += item[\"weighted\"]\n    digest = digest % MODULUS\n\n    ranked = sorted(entries, key=lambda item: (-item[\"weighted\"], item[\"entity\"]))\n    for position, item in enumerate(ranked):\n        item[\"rank\"] = position + 1\n\n    canonical_value = None\n    for item in entries:\n        if item[\"entity\"] == deferred_entity:\n            canonical_value = item[\"value\"]\n\n    return {\n        \"generation\": generation,\n        \"digest\": digest,\n        \"root_cause_entity\": deferred_entity,\n        \"canonical_value\": canonical_value,\n        \"entries\": entries,\n        \"retired\": sorted(retired),\n        \"deferred_record_seq\": deferred_seq,\n    }\n\n\ndef main():\n    parser = argparse.ArgumentParser(description=\"recompute canonical state\")\n    parser.add_argument(\"--input\", required=True)\n    parser.add_argument(\"--out\", required=True)\n    args = parser.parse_args()\n    state = resolve(args.input)\n    os.makedirs(args.out, exist_ok=True)\n    target = os.path.join(args.out, \"reproduced_state.json\")\n    with open(target, \"w\", encoding=\"utf-8\") as handle:\n        json.dump(state, handle, indent=2, sort_keys=True)\n        handle.write(\"\\n\")\n    return 0\n\n\nif __name__ == \"__main__\":\n    raise SystemExit(main())\n"


def load_jsonl(path):
    rows = []
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def load_json(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def data_path(key):
    return os.path.join(DATA, NAMES[key])


def toposort(nodes, edges):
    pending = {}
    for node in nodes:
        pending[node] = [p for p in edges.get(node, []) if p in nodes]
    order = []
    while pending:
        ready = sorted(n for n, parents in pending.items()
                       if not [p for p in parents if p in pending])
        if not ready:
            raise SystemExit("dependency cycle")
        chosen = ready[0]
        order.append(chosen)
        del pending[chosen]
    return order


def build_state():
    records = load_jsonl(data_path("authority"))
    generation_map = load_json(data_path("map"))
    journal = load_jsonl(data_path("journal"))
    weights = load_json(data_path("partitions"))
    index = load_json(data_path("index"))
    derived = load_json(data_path("derived"))
    runtime = load_json(data_path("runtime"))
    catalogue = load_json(data_path("operations"))

    multiplier = {}
    partition_of = {}
    for row in weights["entries"]:
        multiplier[row["entity"]] = row["multiplier"]
        partition_of[row["entity"]] = row["partitions"]

    generation = 0
    for op in journal:
        if op["applied_generation"] > generation:
            generation = op["applied_generation"]

    declared_anchor = {}
    for row in records:
        if row["op"] == "declare":
            declared_anchor[row["entity"]] = row["lineage_anchor"]

    retired_anchor = {}
    for op in journal:
        if op["op"] == "supersede_lineage" and op["applied_generation"] <= generation:
            retired_anchor[op["entity"]] = op["retire_anchor"]

    def precedence(row):
        return (row["effective_generation"],
                1 if row["recorded_by"] == "authority-service" else 0,
                row["seq"])

    kept = {}
    retired = []
    for row in sorted(records, key=precedence):
        if row["effective_generation"] > generation:
            continue
        if row["op"] == "retire":
            retired.append(row["entity"])
            kept.pop(row["entity"], None)
            continue
        kept[row["entity"]] = row

    # A rollback operation addresses its target by position in the surviving
    # set, so the set has to be settled first. The ordering is recomputed for
    # each rollback because an earlier rollback moves its subject back onto a
    # lower sequence, which shifts every position after it.
    for op in journal:
        if op["op"] != "rollback_amendment":
            continue
        if op["applied_generation"] > generation:
            continue
        order = [e for e, _ in sorted(kept.items(), key=lambda kv: kv[1]["seq"])]
        position = op["target_position"]
        if position < 1 or position > len(order):
            continue
        subject = order[position - 1]
        current = kept[subject]
        prior = [r for r in records
                 if r["entity"] == subject
                 and r["op"] in ("declare", "amend")
                 and r["effective_generation"] <= generation
                 and precedence(r) < precedence(current)]
        if prior:
            kept[subject] = max(prior, key=precedence)

    focal = None
    focal_seq = 0
    focal_recorded = None
    for row in records:
        if row["reference_domain"] != CANON_DOMAIN and row["lineage_anchor"] == "pending":
            if row["seq"] > focal_seq:
                focal_seq = row["seq"]
                focal = row["entity"]
                focal_recorded = row["value"]

    values = {}
    anchors = {}
    for entity in sorted(kept):
        row = kept[entity]
        value = row["value"]
        anchor = row["lineage_anchor"]
        if anchor == "pending" or anchor == retired_anchor.get(entity):
            anchor = declared_anchor[entity]
        if row["reference_domain"] != CANON_DOMAIN:
            for candidate in generation_map["rows"]:
                if candidate["alt_key"] == value and candidate["lineage_anchor"] == anchor:
                    value = candidate["canonical_value"]
                    break
        values[entity] = value
        anchors[entity] = anchor

    active = sorted(values)
    digest = 0
    for entity in active:
        digest += values[entity] * multiplier[entity]
    digest = digest % MODULUS

    derived_values = {}
    for row in derived["entries"]:
        derived_values[row["entity"]] = row["value"]
    pre_digest = 0
    for entity in active:
        pre_digest += derived_values[entity] * multiplier[entity]
    pre_digest = pre_digest % MODULUS

    runtime_values = {}
    for row in runtime["entries"]:
        runtime_values[row["entity"]] = row["value"]

    divergent = sorted(e for e in active
                       if derived_values.get(e) != values[e]
                       or runtime_values.get(e) != values[e])

    weighted = {}
    for entity in active:
        weighted[entity] = values[entity] * multiplier[entity]
    ranked = sorted(active, key=lambda e: (-weighted[e], e))
    rank = {}
    for position, entity in enumerate(ranked):
        rank[entity] = position + 1

    edges = {}
    for row in index["dependency_edges"]:
        edges[row["entity"]] = [p for p in row["depends_on"] if p in values]
    dependency_order = toposort(active, edges)

    layers = [row["layer"] for row in sorted(catalogue["layers"],
                                             key=lambda item: item["position"])]
    transitions = [row["transition"] for row in sorted(catalogue["transitions"],
                                                       key=lambda item: item["position"])]

    # The preservation clause covers a track whose durable record is an
    # amendment standing over an earlier amendment of the same track. Counting
    # amendments in the raw ledger answers a different question, because a
    # track whose later amendment the replay withdrew keeps the earlier value.
    later_amendment = []
    for entity in sorted(kept):
        durable = kept[entity]
        if durable["op"] != "amend":
            continue
        stamp = (durable["effective_generation"], durable["seq"])
        earlier = [r for r in records
                   if r["entity"] == entity
                   and r["op"] == "amend"
                   and (r["effective_generation"], r["seq"]) < stamp]
        if earlier:
            later_amendment.append(entity)

    superseded = retired_anchor.get(focal)

    return {
        "records": records,
        "values": values,
        "anchors": anchors,
        "active": active,
        "retired": sorted(retired),
        "multiplier": multiplier,
        "partition_of": partition_of,
        "generation": generation,
        "digest": digest,
        "pre_digest": pre_digest,
        "divergent": divergent,
        "weighted": weighted,
        "rank": rank,
        "dependency_order": dependency_order,
        "layers": layers,
        "transitions": transitions,
        "focal": focal,
        "focal_seq": focal_seq,
        "focal_recorded": focal_recorded,
        "later_amendment": later_amendment,
        "superseded_anchor": superseded,
    }


def sections(state):
    focal = state["focal"]
    core = {
        "generation": state["generation"],
        "authority_anchored": True,
        "entries": [
            {
                "entity": entity,
                "value": state["values"][entity],
                "multiplier": state["multiplier"][entity],
                "lineage_anchor": state["anchors"][entity],
                "state": "active",
            }
            for entity in state["active"]
        ],
    }
    metrics = {
        "digest": state["digest"],
        "digest_modulus": MODULUS,
        "entity_metrics": [
            {
                "entity": entity,
                "weighted": state["weighted"][entity],
                "rank": state["rank"][entity],
            }
            for entity in state["active"]
        ],
        "pre_repair_digest": state["pre_digest"],
        "post_repair_digest": state["digest"],
    }
    resolution = {
        "transition_order": state["transitions"],
        "dependency_order": state["dependency_order"],
        "revisited_repair": {
            "entity": focal,
            "transition": state["transitions"][2],
            "restored_lineage_anchor": state["anchors"][focal],
            "superseded_lineage_anchor": state["superseded_anchor"],
        },
    }
    preserved = []
    for entity in state["later_amendment"]:
        preserved.append({"entity": entity, "reason": "later_amendment"})
    for entity in state["retired"]:
        preserved.append({"entity": entity, "reason": "retired_record_retained"})
    report = {
        "root_cause": {
            "layer": state["layers"][0],
            "entity": focal,
            "record_seq": state["focal_seq"],
            "field": FIELD,
            "recorded_reference_domain": ALT_DOMAIN,
            "required_reference_domain": CANON_DOMAIN,
            "recorded_value": state["focal_recorded"],
            "canonical_value": state["values"][focal],
        },
        "rejected_hypothesis": {
            "name": REJECTED_HYPOTHESIS,
            "layer": state["layers"][2],
            "falsified_by_transition": state["transitions"][4],
            "falsifying_evidence": (
                "the replayed lineage supersession retires "
                + str(state["superseded_anchor"])
                + " and moves the active anchor of "
                + str(focal)
                + " to "
                + str(state["anchors"][focal])
                + ", which selects a different generation map row"
            ),
        },
        "minimal_delta": {
            "authority_records_changed": 1,
            "changed_record_seq": state["focal_seq"],
        },
        "preserved_records": preserved,
    }
    verdict = {
        "verdict": "in_sync",
        "authority_anchored": True,
        "post_replay": True,
        "layers_compared": state["layers"],
        "mismatches": [],
        "pre_repair_divergence_count": len(state["divergent"]),
        "post_repair_divergence_count": 0,
    }
    summary = {
        "root_cause_entity": focal,
        "canonical_value": state["values"][focal],
        "generation": state["generation"],
        "digest": state["digest"],
        "authority_records_changed": 1,
        "verdict": "in_sync",
        "active_entity_count": len(state["active"]),
    }
    return {
        "core": core,
        "metrics": metrics,
        "resolution": resolution,
        "report": report,
        "verdict": verdict,
        "summary": summary,
    }


def partition_payloads(state):
    payloads = {}
    for group, labels in PARTITION_PATHS.items():
        for label in labels:
            members = []
            for entity in state["active"]:
                if state["partition_of"].get(entity, {}).get(group) == label:
                    members.append({
                        "entity": entity,
                        "value": state["values"][entity],
                    })
            payloads[(group, label)] = {
                "partition": label,
                "group": group,
                "entities": members,
            }
    return payloads


def write_json(path, payload):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")


def write_core_jsonl(path, core):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    lines = [json.dumps({
        "record_type": "header",
        "generation": core["generation"],
        "authority_anchored": core["authority_anchored"],
    }, sort_keys=True)]
    for row in core["entries"]:
        item = dict(row)
        item["record_type"] = "entry"
        lines.append(json.dumps(item, sort_keys=True))
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines))
        handle.write("\n")


def main():
    os.makedirs(OUT, exist_ok=True)
    state = build_state()
    payloads = sections(state)
    parts = partition_payloads(state)

    merged = {}
    for role, path in ROLE_PATHS.items():
        if role not in payloads:
            continue
        merged.setdefault(path, {}).update(payloads[role])

    for path, payload in sorted(merged.items()):
        if path.endswith(".jsonl"):
            write_core_jsonl(path, payload)
        else:
            write_json(path, payload)

    for group, labels in PARTITION_PATHS.items():
        for label in labels:
            write_json(labels[label], parts[(group, label)])

    os.makedirs(os.path.dirname(SCRIPT_PATH), exist_ok=True)
    with open(SCRIPT_PATH, "w", encoding="utf-8") as handle:
        handle.write(REPRODUCER)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
