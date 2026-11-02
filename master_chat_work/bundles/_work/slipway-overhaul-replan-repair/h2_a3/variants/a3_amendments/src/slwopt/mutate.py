"""Stage p13. The amendments, their classification and their cascade.

An amendment is classified by its kind. The seed set is the cell or cells the
directive names for that kind and nothing else. A reversal carries the seed
set of the amendment it names, and a restatement carries the seed set its own
kind would carry, which is why a restatement whose normalised value stands
unchanged reaches the rule cell and stops there.
"""
from . import cells, charge, graph, normalise

JOURNAL = "amendment_journal.jsonl"
SUPPLEMENT = "amendment_supplement.ndjson"
PROVENANCE = "row_provenance_ledger.csv"


def lodged(root):
    """The lodged amendments in sequence, with the payload fields the
    supplement completes folded in under the provenance ledger."""
    rows = [record for record in graph.reading.records(root / JOURNAL)
            if record.get("state") == "lodged"]
    late = {}
    for record in graph.reading.records(root / SUPPLEMENT):
        if record.get("state") == "in_force":
            late[(record["amendment_id"], record["field"])] = record["value"]
    source = {}
    for row in graph.reading.delimited(root / PROVENANCE):
        if row["state"] == "in_force":
            source[(row["amendment_id"], row["field"])] = row["source_file"]
    alias = normalise.crosswalk(root)[0]
    out = []
    for record in sorted(rows, key=lambda r: int(r["sequence"])):
        payload = dict(record.get("payload") or {})
        for (amendment_id, field), value in sorted(late.items()):
            if amendment_id != record["amendment_id"]:
                continue
            if source.get((amendment_id, field)) != SUPPLEMENT:
                continue
            payload[field] = value
        for field in ("job_id", "requiring_job", "required_job",
                      "member_job"):
            if field in payload:
                payload[field] = alias.get(payload[field], payload[field])
        out.append({"amendment_id": record["amendment_id"],
                    "sequence": int(record["sequence"]),
                    "kind": record["kind"], "payload": payload,
                    "note": record.get("note", "")})
    return out


def implied_kind(payload):
    """The kind a restatement restates, read off the payload it carries."""
    if "rule_id" in payload:
        return "charge_rule_revision"
    if "commitment_id" in payload:
        return "carryover_revision"
    if "capacity" in payload:
        return "capacity_revision"
    if "group_id" in payload:
        return "group_member_revision"
    if "multiplier_bp" in payload:
        return "class_rate_revision"
    if "requiring_job" in payload:
        return "edge_lodged"
    if "edge_id" in payload:
        return "edge_withdrawn"
    if "job_id" in payload:
        if payload.get("field") in charge.PRESENTATION_FIELDS:
            return "job_note_revision"
        return "job_field_revision"
    raise SystemExit("the directive restates no payload of this shape")


def seeds_for(model, kind, payload):
    """The cells the directive names for this kind, and no others."""
    if kind == "job_note_revision":
        return []
    if kind == "job_field_revision":
        return [cells.named("norm", payload["job_id"])]
    if kind in ("edge_lodged", "edge_withdrawn"):
        return [cells.named("closure", payload["requiring_job"])]
    if kind == "group_member_revision":
        return [cells.named("group", payload["group_id"])]
    if kind in ("capacity_revision", "carryover_revision"):
        return [cells.named("solve", payload["precinct"])]
    if kind == "charge_rule_revision":
        return [cells.named("rule", payload["rule_id"])]
    if kind == "class_rate_revision":
        return [cells.named("charge", name) for name in sorted(model.jobs)
                if model.jobs[name]["class"] == payload["class"]]
    if kind == "restatement":
        return seeds_for(model, implied_kind(payload), payload)
    raise SystemExit("the directive classifies no kind " + kind)


def resolve(model, amendment):
    """Fill in what the payload needs, and turn down a lodgement the papers
    do not accept. A reversal is classified by the kind it names and carries
    the action that puts that amendment back."""
    kind = amendment["kind"]
    payload = dict(amendment["payload"])
    action = kind
    if kind == "reversal":
        named = model.inverse.get(payload.get("amendment_id"))
        if named is None:
            return "reversal", "reversal", payload, "rejected", "AMD-NOTARGET"
        return named["kind"], named["action"], dict(named["payload"]), \
            "governed", ""
    shape = implied_kind(payload) if kind == "restatement" else kind
    if shape == "edge_lodged":
        requiring = payload["requiring_job"]
        required = payload["required_job"]
        payload["edge_id"] = amendment["amendment_id"] + "-E"
        if requiring == required:
            return kind, action, payload, "rejected", "EDG-SELF"
        if requiring not in model.jobs or required not in model.jobs:
            return kind, action, payload, "rejected", "EDG-UNKNOWNJOB"
        if model.jobs[requiring]["precinct"] != model.jobs[required]["precinct"]:
            return kind, action, payload, "rejected", "EDG-CROSSPRECINCT"
        if graph.stands_behind(model.accepted, required, requiring):
            return kind, action, payload, "rejected", "EDG-CYCLE"
        if required in model.accepted.get(requiring, []):
            return kind, action, payload, "rejected", "EDG-DUPLICATE"
    elif shape == "edge_withdrawn":
        row = model.journal.get(payload["edge_id"])
        if row is None or row["requiring_job"] not in model.jobs:
            return kind, action, payload, "rejected", "EDG-UNKNOWNJOB"
        payload["requiring_job"] = row["requiring_job"]
        payload["required_job"] = row["required_job"]
    elif shape == "carryover_revision":
        entry = model.carryover.get(payload["commitment_id"])
        if entry is None or entry["precinct"] not in model.precincts:
            return kind, action, payload, "rejected", "CMT-UNKNOWN"
        payload["precinct"] = entry["precinct"]
    elif not _names_something(model, shape, payload):
        return kind, action, payload, "rejected", "AMD-NOTARGET"
    return kind, action, payload, "governed", ""


def _names_something(model, shape, payload):
    """Whether the amendment names anything the round holds."""
    if shape in ("job_field_revision", "job_note_revision"):
        return payload["job_id"] in model.jobs
    if shape == "group_member_revision":
        return payload["group_id"] in model.groups
    if shape == "charge_rule_revision":
        return payload["rule_id"] in model.rules
    if shape == "capacity_revision":
        return (payload["precinct"] in model.precincts
                and (payload["precinct"], payload["pool"]) in model.capacity)
    if shape == "class_rate_revision":
        return payload["class"] in model.params["class_bp"]
    return True


def apply(model, action, payload):
    """Move the model and hand back the action that puts it back."""
    if action == "restatement":
        action = implied_kind(payload)
    if action == "job_note_revision":
        name, field = payload["job_id"], payload["field"]
        back = {"job_id": name, "field": field,
                "value": model.meta[name][field]}
        model.meta[name][field] = payload["value"]
        return action, back
    if action == "job_field_revision":
        name, field = payload["job_id"], payload["field"]
        back = {"job_id": name, "field": field, "value": model.jobs[name][field]}
        model.jobs[name][field] = payload["value"]
        return action, back
    if action == "edge_lodged":
        model.journal[payload["edge_id"]] = {
            "requiring_job": payload["requiring_job"],
            "required_job": payload["required_job"],
            "kind": payload.get("kind", "hard"), "status": "active"}
        model.refresh_edges(model.jobs[payload["requiring_job"]]["precinct"])
        return "edge_withdrawn", {"edge_id": payload["edge_id"],
                                  "requiring_job": payload["requiring_job"],
                                  "required_job": payload["required_job"]}
    if action == "edge_withdrawn":
        row = model.journal[payload["edge_id"]]
        back = {"edge_id": payload["edge_id"],
                "requiring_job": row["requiring_job"],
                "required_job": row["required_job"], "kind": row["kind"]}
        row["status"] = "withdrawn"
        model.refresh_edges(model.jobs[row["requiring_job"]]["precinct"])
        return "edge_lodged", back
    if action == "group_member_revision":
        entry = model.groups[payload["group_id"]]
        member = payload["member_job"]
        if payload["action"] == "remove":
            entry["members"] = [m for m in entry["members"] if m != member]
            return action, {"group_id": payload["group_id"],
                            "member_job": member, "action": "add"}
        entry["members"] = sorted(set(entry["members"]) | {member})
        return action, {"group_id": payload["group_id"],
                        "member_job": member, "action": "remove"}
    if action == "capacity_revision":
        marker = (payload["precinct"], payload["pool"])
        back = {"precinct": payload["precinct"], "pool": payload["pool"],
                "capacity": model.capacity[marker]}
        model.capacity[marker] = int(payload["capacity"])
        return action, back
    if action == "carryover_revision":
        entry = model.carryover[payload["commitment_id"]]
        back = {"commitment_id": payload["commitment_id"],
                "quantity": entry["quantity"], "precinct": entry["precinct"]}
        entry["quantity"] = int(payload["quantity"])
        return action, back
    if action == "charge_rule_revision":
        record = model.rules[payload["rule_id"]]
        back = {"rule_id": payload["rule_id"],
                "amount_text": record["amount_text"]}
        record["amount_text"] = payload["amount_text"]
        return action, back
    if action == "class_rate_revision":
        klass = payload["class"]
        back = {"class": klass, "multiplier_bp": model.params["class_bp"][klass]}
        model.params["class_bp"][klass] = int(payload["multiplier_bp"])
        return action, back
    raise SystemExit("no payload rule for " + action)


def fold(model, amendment):
    """One amendment: classify it, move the model, seed the cells the
    directive names, and let the cascade stop where a value stands."""
    kind, action, payload, verdict, reason = resolve(model, amendment)
    counters = cells.fresh_counters()
    record = {"amendment_id": amendment["amendment_id"],
              "sequence": amendment["sequence"],
              "lodged_kind": amendment["kind"], "applied_kind": kind,
              "classification": verdict, "reason": reason,
              "seed_cells": [], "invalidated": [], "revalidated": [],
              "counters": counters}
    if verdict == "rejected":
        return record
    undo_action, back = apply(model, action, payload)
    model.inverse[amendment["amendment_id"]] = {
        "kind": kind, "action": undo_action, "payload": back}
    seeds = seeds_for(model, kind, payload)
    if not seeds:
        record["classification"] = "inert"
    trail, moved = model.cascade(seeds, counters)
    record["seed_cells"] = sorted(seeds)
    record["invalidated"] = sorted(moved)
    record["revalidated"] = sorted(marker for marker, state in trail
                                   if state == "revalidated")
    record["target"] = normalise.tight(payload)
    return record
