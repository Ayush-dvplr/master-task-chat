"""Stage p13. The amendments, their classification and their cascade.

An amendment is classified by its kind. The seed set is the cell or cells the
directive names for that kind and nothing else. A reversal carries the seed
set of the amendment it names, and a restatement carries the seed set its own
kind would carry, which is why a restatement whose normalised value stands
unchanged reaches the rule cell and stops there.
"""
from . import cells, graph, normalise

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
    out = []
    for record in sorted(rows, key=lambda r: int(r["sequence"])):
        payload = dict(record.get("payload") or {})
        for (amendment_id, field), value in sorted(late.items()):
            if amendment_id != record["amendment_id"]:
                continue
            if source.get((amendment_id, field)) != SUPPLEMENT:
                continue
            payload[field] = value
        out.append({"amendment_id": record["amendment_id"],
                    "sequence": int(record["sequence"]),
                    "kind": record["kind"], "payload": payload,
                    "note": record.get("note", "")})
    return out


def seeds_for(model, kind, payload):
    if kind == "job_note_revision":
        return [cells.named("norm", payload["job_id"])]
    if kind == "job_field_revision":
        return [cells.named("norm", payload["job_id"])]
    if kind == "edge_withdrawn":
        return []
    if kind == "edge_lodged":
        return [cells.named("closure", payload["requiring_job"])]
    if kind == "group_member_revision":
        return [cells.named("group", payload["group_id"])]
    if kind == "capacity_revision":
        return [cells.named("closure", name) for name in sorted(model.jobs)
                if model.jobs[name]["precinct"] == payload["precinct"]] + [
                    cells.named("solve", payload["precinct"])]
    if kind == "carryover_revision":
        return [cells.named("solve", payload["precinct"])]
    if kind in ("charge_rule_revision", "restatement"):
        return [cells.named("rule", payload["rule_id"])]
    if kind == "class_rate_revision":
        return [cells.named("charge", name) for name in sorted(model.jobs)
                if model.jobs[name]["class"] == payload["class"]]
    raise SystemExit("the directive classifies no kind " + kind)


def resolve(model, amendment):
    """Fill in what the payload needs, and turn down a lodgement the papers
    do not accept."""
    kind = amendment["kind"]
    payload = dict(amendment["payload"])
    if kind == "reversal":
        named = model.inverse.get(payload["amendment_id"])
        if named is None:
            return "reversal", payload, "rejected", "AMD-NOTARGET"
        return named[0], dict(named[1]), "governed", ""
    if kind == "edge_lodged":
        requiring = payload["requiring_job"]
        required = payload["required_job"]
        payload["edge_id"] = amendment["amendment_id"] + "-E"
        if requiring not in model.jobs or required not in model.jobs:
            return kind, payload, "rejected", "EDG-UNKNOWNJOB"
        if requiring == required:
            return kind, payload, "rejected", "EDG-SELF"
        if model.jobs[requiring]["precinct"] != model.jobs[required]["precinct"]:
            return kind, payload, "rejected", "EDG-CROSSPRECINCT"
        if graph.stands_behind(model.accepted, required, requiring):
            return kind, payload, "rejected", "EDG-CYCLE"
        if required in model.accepted.get(requiring, []):
            return kind, payload, "rejected", "EDG-DUPLICATE"
    if kind == "edge_withdrawn":
        row = model.journal.get(payload["edge_id"])
        if row is None or row["requiring_job"] not in model.jobs:
            return kind, payload, "rejected", "EDG-UNKNOWNJOB"
        payload["requiring_job"] = row["requiring_job"]
        payload["required_job"] = row["required_job"]
    if kind == "carryover_revision":
        if payload["commitment_id"] not in model.carryover:
            return kind, payload, "rejected", "CMT-UNKNOWN"
        payload["precinct"] = model.carryover[payload["commitment_id"]]["precinct"]
    verdict = "inert" if kind == "job_note_revision" else "governed"
    return kind, payload, verdict, ""


def apply(model, kind, payload):
    """Move the model and hand back the payload that puts it back."""
    if kind == "job_note_revision":
        name, field = payload["job_id"], payload["field"]
        back = {"job_id": name, "field": field,
                "value": model.meta[name][field]}
        model.meta[name][field] = payload["value"]
        return back
    if kind == "job_field_revision":
        name, field = payload["job_id"], payload["field"]
        back = {"job_id": name, "field": field, "value": model.jobs[name][field]}
        model.jobs[name][field] = payload["value"]
        return back
    if kind == "edge_lodged":
        model.journal[payload["edge_id"]] = {
            "requiring_job": payload["requiring_job"],
            "required_job": payload["required_job"],
            "kind": payload.get("kind", "hard"), "status": "active"}
        model.refresh_edges(model.jobs[payload["requiring_job"]]["precinct"])
        return {"edge_id": payload["edge_id"]}
    if kind == "edge_withdrawn":
        row = model.journal[payload["edge_id"]]
        back = {"edge_id": payload["edge_id"],
                "requiring_job": row["requiring_job"],
                "required_job": row["required_job"], "kind": row["kind"]}
        row["status"] = "withdrawn"
        model.refresh_edges(model.jobs[row["requiring_job"]]["precinct"])
        return back
    if kind == "group_member_revision":
        entry = model.groups[payload["group_id"]]
        member = payload["member_job"]
        if payload["action"] == "remove":
            entry["members"] = [m for m in entry["members"] if m != member]
            return {"group_id": payload["group_id"], "member_job": member,
                    "action": "add"}
        entry["members"] = sorted(set(entry["members"]) | {member})
        return {"group_id": payload["group_id"], "member_job": member,
                "action": "remove"}
    if kind == "capacity_revision":
        marker = (payload["precinct"], payload["pool"])
        back = {"precinct": payload["precinct"], "pool": payload["pool"],
                "capacity": model.capacity[marker]}
        model.capacity[marker] = int(payload["capacity"])
        return back
    if kind == "carryover_revision":
        entry = model.carryover[payload["commitment_id"]]
        back = {"commitment_id": payload["commitment_id"],
                "quantity": entry["quantity"], "precinct": entry["precinct"]}
        entry["quantity"] = int(payload["quantity"])
        return back
    if kind in ("charge_rule_revision", "restatement"):
        record = model.rules[payload["rule_id"]]
        back = {"rule_id": payload["rule_id"],
                "amount_text": record["amount_text"]}
        record["amount_text"] = payload["amount_text"]
        return back
    if kind == "class_rate_revision":
        klass = payload["class"]
        back = {"class": klass, "multiplier_bp": model.params["class_bp"][klass]}
        model.params["class_bp"][klass] = int(payload["multiplier_bp"])
        return back
    raise SystemExit("no payload rule for " + kind)


def fold(model, amendment):
    """One amendment: classify it, move the model, seed the cells the
    directive names, and let the cascade stop where a value stands."""
    kind, payload, verdict, reason = resolve(model, amendment)
    counters = cells.fresh_counters()
    record = {"amendment_id": amendment["amendment_id"],
              "sequence": amendment["sequence"],
              "lodged_kind": amendment["kind"], "applied_kind": kind,
              "classification": verdict, "reason": reason,
              "seed_cells": [], "invalidated": [], "revalidated": [],
              "counters": counters}
    if verdict == "rejected":
        return record
    back = apply(model, kind, payload)
    model.inverse[amendment["amendment_id"]] = (kind, back)
    seeds = seeds_for(model, kind, payload)
    trail, moved = model.cascade(seeds, counters)
    record["seed_cells"] = sorted(seeds)
    record["invalidated"] = sorted(moved)
    record["revalidated"] = sorted(marker for marker, state in trail
                                   if state == "revalidated")
    record["target"] = normalise.tight(payload)
    return record
