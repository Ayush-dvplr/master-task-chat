"""Reference fixes for bddb388 (Q1 Q2 Q3 Q7 Q8 and the p01 crosswalk on every
identifier). Usage: python3 -B patch_ref.py <test_output.py>. Each edit must
match exactly once."""
import sys
from pathlib import Path

EDITS = [
    # Q1: lodgements naming a JOB-CYCLE job are rejected EDG-UNKNOWNJOB (p02:20-23)
    ("""    for jid in list(model["accepted"]):
        if jid not in jobs:
            del model["accepted"][jid]
        else:
            model["accepted"][jid] = [d for d in model["accepted"][jid] if d in jobs]
""", """    if cycles:
        accepted, edge_rejected = ref_edge_journal(root, jobs, aliases)
        model["accepted"] = accepted
"""),
    # crosswalk on group memberships (p01:19-21)
    ("""    groups, group_rejected = ref_groups(root, jobs)
""", """    groups, group_rejected = ref_groups(root, jobs, aliases)
"""),
    ("""def ref_groups(root, jobs):
    \"\"\"Stage p08. Open memberships, with a job standing in two open groups
    kept by the group of the lower precedence number.\"\"\"
    rows = [r for r in read_delim(Path(root) / "exclusive_slot_groups.csv")
            if r["state"] == "open" and r["member_job"] in jobs]
""", """def ref_groups(root, jobs, aliases):
    \"\"\"Stage p08. Open memberships, with a job standing in two open groups
    kept by the group of the lower precedence number.\"\"\"
    rows = [dict(r, member_job=aliases.get(r["member_job"], r["member_job"]))
            for r in read_delim(Path(root) / "exclusive_slot_groups.csv")]
    rows = [r for r in rows if r["state"] == "open" and r["member_job"] in jobs]
"""),
    # crosswalk on rule subjects (p01:19-21)
    ("""def ref_rules(root, params):
    out = {}
    for rec in read_jsonl(Path(root) / "conditional_charge_rules.jsonl"):
        if rec.get("state") != "in_force":
            continue
        out[rec["rule_id"]] = dict(rec)
    return out
""", """def ref_rules(root, params):
    aliases = ref_aliases(root)
    out = {}
    for rec in read_jsonl(Path(root) / "conditional_charge_rules.jsonl"):
        if rec.get("state") != "in_force":
            continue
        rec = dict(rec)
        for field in JOB_FIELDS_OF_RULES:
            if isinstance(rec.get(field), str):
                rec[field] = aliases.get(rec[field], rec[field])
        out[rec["rule_id"]] = rec
    return out


JOB_FIELDS_OF_RULES = ("first_job", "second_job", "anchor_job")
JOB_FIELDS_OF_PAYLOADS = ("job_id", "requiring_job", "required_job",
                          "member_job")
"""),
    # crosswalk on amendment payloads (p01:19-21)
    ("""            payload[field] = value
        out.append({"amendment_id": rec["amendment_id"],
""", """            payload[field] = value
        for field in JOB_FIELDS_OF_PAYLOADS:
            if isinstance(payload.get(field), str):
                payload[field] = aliases.get(payload[field], payload[field])
        out.append({"amendment_id": rec["amendment_id"],
"""),
    ("""    provenance = {}
    for row in read_delim(Path(root) / "row_provenance_ledger.csv"):
""", """    aliases = ref_aliases(root)
    provenance = {}
    for row in read_delim(Path(root) / "row_provenance_ledger.csv"):
"""),
    # Q2: the round's weighted resource is the exact sum, rounded once (p10:24-26)
    ("""        weighted += Fraction(body["weighted_resource"])
""", """        weights = ctx["model"]["params"]["pool_weights"]
        weighted += sum(Fraction(weights[pool][0], weights[pool][1])
                        * body["usage"][pool] for pool in POOLS)
"""),
    # Q8: aliases_active is the count of active crosswalk rows
    ("""        "aliases_active": len(aliases),
""", """        "aliases_active": sum(1 for row in read_delim(
            Path(root) / "identifier_crosswalk.tsv", TAB)
            if row["status"] == "active"),
"""),
    # Q7: p02 order puts EDG-SELF before EDG-UNKNOWNJOB
    ("""        if req not in model["jobs"] or dep not in model["jobs"]:
            return kind, payload, "rejected", "EDG-UNKNOWNJOB"
        if req == dep:
            return kind, payload, "rejected", "EDG-SELF"
""", """        if req == dep:
            return kind, payload, "rejected", "EDG-SELF"
        if req not in model["jobs"] or dep not in model["jobs"]:
            return kind, payload, "rejected", "EDG-UNKNOWNJOB"
"""),
    # Q7: a reversal of a lodgement or a withdrawal applies the exact inverse
    ("""    if kind == "edge_lodged":
        eid = payload["edge_id"]
        model["journal"][eid] = {"requiring_job": payload["requiring_job"],
                                 "required_job": payload["required_job"],
                                 "kind": payload.get("kind", "hard"),
                                 "status": "active"}
        _accept_edges(model, model["jobs"][payload["requiring_job"]]["precinct"])
        return {"edge_id": eid}
    if kind == "edge_withdrawn":
        eid = payload["edge_id"]
        row = model["journal"][eid]
        back = {"edge_id": eid, "requiring_job": row["requiring_job"],
                "required_job": row["required_job"], "kind": row["kind"]}
        row["status"] = "withdrawn"
        _accept_edges(model, model["jobs"][row["requiring_job"]]["precinct"])
        return back
""", """    if kind == "edge_lodged":
        eid = payload["edge_id"]
        back = {"edge_id": eid, "requiring_job": payload["requiring_job"],
                "required_job": payload["required_job"],
                "kind": payload.get("kind", "hard")}
        if payload.get("undo"):
            del model["journal"][eid]
        else:
            model["journal"][eid] = {"requiring_job": payload["requiring_job"],
                                     "required_job": payload["required_job"],
                                     "kind": payload.get("kind", "hard"),
                                     "status": "active"}
            back["undo"] = True
        _accept_edges(model, model["jobs"][payload["requiring_job"]]["precinct"])
        return back
    if kind == "edge_withdrawn":
        eid = payload["edge_id"]
        row = model["journal"][eid]
        back = {"edge_id": eid, "requiring_job": row["requiring_job"],
                "required_job": row["required_job"], "kind": row["kind"]}
        if payload.get("undo"):
            row["status"] = payload["undo"]
        else:
            back["undo"] = row["status"]
            row["status"] = "withdrawn"
        _accept_edges(model, model["jobs"][row["requiring_job"]]["precinct"])
        return back
"""),
    # Q3: an amendment that reaches no cell is inert (instruction.md:21)
    ("""    seeds, _label = _seed_set(ctx, {"kind": kind}, payload)
""", """    seeds, _label = _seed_set(ctx, {"kind": kind}, payload)
    if not seeds and kind in ("job_note_revision", "class_rate_revision"):
        record["classification"] = "inert"
"""),
]


def main():
    path = Path(sys.argv[1])
    text = path.read_text()
    for old, new in EDITS:
        count = text.count(old)
        if count != 1:
            raise SystemExit("edit matches " + str(count) + " times: "
                             + old.splitlines()[0])
        text = text.replace(old, new)
    path.write_text(text)
    print("patched", len(EDITS))


if __name__ == "__main__":
    main()
