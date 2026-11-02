"""Aggregate fuzz jsonl logs into the TRIP.md fuzz table.  python3 fuzztable.py LOG...  (prints markdown)"""
import collections
import json
import sys

DC = "data_conventions.md"
DOC = {
    "D_sdt_row_allow": DC + ":20-23; overtime_policy.md:14", "D_sdt_allrows_allow": DC + ":20-23; overtime_policy.md:14",
    "D_cxml_row_allow": DC + ":20-23; overtime_policy.md:14", "D_alt_allow": DC + ":20-23; overtime_policy.md:14",
    "D_sdt_row_closure": DC + ":20-23,54-55", "D_cxml_row_closure": DC + ":20-23,54-55",
    "D_alt_closure_days": DC + ":20-23,54-55", "D_sdt_row_avail": DC + ":20-23,51-53",
    "D_cxml_row_avail": DC + ":20-23,51-53", "D_alt_avail": DC + ":20-23,51-53",
    "D_sdt_row_item": DC + ":15,20-23", "D_sdt_row_class": DC + ":15,20-23", "D_cellsdt_allow": DC + ":20-23",
    "D_altcontent": DC + ":20-23", "D_altcontent_data": DC + ":20-23", "D_dot_target": DC + ":20-21",
    "S_avail_after_end": DC + ":51-53", "S_avail_before_start": DC + ":51-53", "S_avail_late_in": DC + ":51-53",
    "S_avail_own_out": DC + ":51-53", "S_closure_from_before": DC + ":54-56", "S_closure_past_end": DC + ":54-56",
    "S_closure_outside": DC + ":54-56", "S_calendar_random": DC + ":54-56",
    "S_pool0": "overtime_policy.md:9-10", "S_pool_big": "overtime_policy.md:9-10",
    "S_pool_small": "overtime_policy.md:9-10", "S_shift_cost": "planning_policy.md:28-29",
    "S_grants0": "overtime_policy.md:14-24", "S_grants_big": "overtime_policy.md:14-24",
    "S_grants_rand": "overtime_policy.md:14-24", "S_dur1": "overtime_policy.md:3-7",
    "S_due_far": "planning_policy.md:24-25", "S_status_case": DC + ":31-32", "S_empty_requests": "output_schema.md",
    "S_pub_outside": "planning_policy.md:30-31", "S_ids_varlen": "planning_policy.md:36-41",
    "S_rates_types": "planning_policy.md:22-29", "C_blankline": DC + ":45-46",
}
WHO = {"WRONG": "reference (a1 misreads ECMA-376 markup)", "CRASH": "reference; a1 stops (not a lever, Law 1)"}


def main():
    agg = collections.OrderedDict()
    for path in sys.argv[1:]:
        for line in open(path):
            if not line.startswith("{"):
                continue
            r = json.loads(line)
            key = r.get("mut") or ("branch " + r["branch"])
            a = agg.setdefault(key, {"n": 0, "v": collections.Counter(), "first": {}})
            a["n"] += 1
            a["v"][r["verdict"]] += 1
            a["first"].setdefault(r["verdict"], (r.get("diff") or r.get("why") or "")[:70])
    print("| branch or mutator | doc line | folders | MATCH/DIFF | first DIFF field | who is right |")
    print("|---|---|---|---|---|---|")
    for key in sorted(agg, key=lambda k: (not k.startswith("branch"), k)):
        a = agg[key]
        v = a["v"]
        diff = v["WRONG"] + v["CRASH"] + v["TIMEOUT"]
        md = "MATCH %d" % v["EXACT"] + ("; DIFF %d (W%d C%d T%d)" % (diff, v["WRONG"], v["CRASH"], v["TIMEOUT"]) if diff else "")
        other = {k: c for k, c in v.items() if k not in ("EXACT", "WRONG", "CRASH", "TIMEOUT")}
        if other:
            md += "; " + ", ".join("%s %d" % kv for kv in sorted(other.items()))
        first = a["first"].get("WRONG") or a["first"].get("CRASH") or a["first"].get("TIMEOUT") or "-"
        who = WHO["WRONG"] if v["WRONG"] else (WHO["CRASH"] if v["CRASH"] else "-")
        doc = DOC.get(key, DC + ":20-23" if key.startswith("D_") else (DC + ":9-16" if key.startswith("C_") else "all docs"))
        print("| %s | %s | %d | %s | %s | %s |" % (key, doc, a["n"], md, first.replace("|", "/"), who))
    print("\nTotal folders: %d" % sum(a["n"] for a in agg.values()))


main()
