"""Write single-rule mutants of solution/solve.py.  Usage: mutants.py <solve.py> <out_dir>
Each mutant applies one wrong reading (lever rows L_*, plain-rule rows R_*, combined rows X_*)."""
import sys
from pathlib import Path

M = {
    # levers (Shape D sharp rules)
    "L_meter_identity": [("current.prices[(s + meters[d]) % day]", "current.prices[s % day]")],
    "L_feeder_ignored": [("net.arc(first_slot + s, SNK, feeder_by_slot[s], 0)", "net.arc(first_slot + s, SNK, 10 ** 9, 0)")],
    "L_cabinets_ignored": [("net.arc(first_cell + d * slots + s, first_slot + s, caps[depot][s], 0)",
                            "net.arc(first_cell + d * slots + s, first_slot + s, 10 ** 9, 0)")],
    "L_tiebreak_first_found": [("    settle_ties(net, cells)\n", "    pass\n")],
    "L_tiebreak_reversed_order": [("for key in sorted(cells):", "for key in sorted(cells, key=lambda k: (k[1], k[0])):")],
    # combined: the first-write program (meter as written, optimum without tie pass)
    "X_first_write": [("current.prices[(s + meters[d]) % day]", "current.prices[s % day]"),
                      ("    settle_ties(net, cells)\n", "    pass\n")],
    # plain rules
    "R_derate_ignored": [("            feeder_by_slot[s] = limit\n", "            pass\n")],
    "R_outage_ignored": [("working[s] -= n", "working[s] -= 0")],
    "R_span_inclusive_end": [("hi = min(clock.count, clock.first_at_or_after(stamp(b)))",
                              "hi = min(clock.count, clock.first_at_or_after(stamp(b)) + 1)")],
    "R_extra_trips_ignored": [("        if when == after:\n", "        if False:\n")],
    "R_extra_trips_any_date": [("        if when == after:\n", "        if True:\n")],
    "R_trips_plan_date": [('if date.fromisoformat(t["service_date"]) == after:', 'if date.fromisoformat(t["service_date"]) == pd:')],
    "R_reserve_ignored": [("trip_kwh[bid] + reserve - int(", "trip_kwh[bid] - int(")],
    "R_need_no_floor": [("need = max(0, trip_kwh[bid]", "need = abs(trip_kwh[bid]")],
    "R_unlisted_contract_public": [('classes.get(row["contract_id"].strip(), "commercial")',
                                    'classes.get(row["contract_id"].strip(), "public")')],
    "R_class_weight_ignored": [("w_unmet * bus.weight", "w_unmet * 1")],
    "R_retired_accepted": [('elif fleet[bid][1] != "active":', "elif False:")],
    "R_duplicate_accepted": [("elif bid in buses:", "elif False:")],
    "R_bad_window_order_only": [("elif not arrive < depart or arrive < clock.first or depart > clock.end:",
                                 "elif not arrive < depart:")],
    "R_published_outside_kept": [("if not (bus.a <= s < bus.e) or clock.first + clock.step * s != at:", "if False:")],
    "R_moved_term_ignored": [("keep = min(bus.published.get(s, 0), bus.rate)", "keep = 0")],
    "R_unmet_reason_no_window": [("elif b.need > b.rate * (b.e - b.a):", "elif False:")],
    "R_changed_by_total": [("differs = any(got.get(s, 0) != b.published.get(s, 0) for s in set(got) | set(b.published))",
                            "differs = delivered != sum(b.published.values())")],
    "R_moved_absolute": [("moved += sum(max(0, k - got.get(s, 0)) for s, k in b.published.items())",
                          "moved += sum(abs(k - got.get(s, 0)) for s, k in b.published.items()) + sum(k for s, k in got.items() if s not in b.published)")],
    "R_settled_start_price": [("if all(kwh * sum(p[(first + j + shift) % day] for j in range(parts)) == cents * parts",
                               "if all(kwh * p[(first + shift) % day] == cents")],
    "R_quality_file_order": [('for f, n, r in sorted(rejected)]', "for f, n, r in rejected]")],
    "R_slot_feeder_is_group": [('"feeder_kwh": fleet_by_slot[s]}', '"feeder_kwh": per_slot[s]}')],
    "I_data_argument_ignored": [("        run(args.data, args.out)\n", '        run("/app/data", args.out)\n')],
    "I_out_argument_ignored": [("        run(args.data, args.out)\n", '        run(args.data, "/app/out")\n')],
    "R_missing_file_unnamed": [('        print("derive_report: cannot read input %s" % err, file=sys.stderr)\n',
                                '        print("derive_report: cannot read an input", file=sys.stderr)\n')],
}


def main():
    src = Path(sys.argv[1]).read_text()
    out = Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    for name, edits in M.items():
        text = src
        for old, new in edits:
            assert text.count(old) == 1, (name, old, text.count(old))
            text = text.replace(old, new)
        (out / (name + ".py")).write_text(text)
    print("wrote", len(M), "mutants")


if __name__ == "__main__":
    main()
