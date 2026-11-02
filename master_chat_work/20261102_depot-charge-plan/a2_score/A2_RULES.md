# A2_RULES: depot-charge-plan, a2 program rule trace

a2 = `a2_out/derive_report.py` (992 lines, sha 7c30bb1e4d67). Rules = `environment/data/docs/charging_rules.md` (CR). Ref = `solution/solve.py`.
a2 own fuzz = trajectory step 39 `/tmp/fuzz.py` (copy: scratch/a2_fuzz_step39.py), edits at steps 41 (duplicate row) and 44 (1-hour bands), runs at steps 40, 42, 43, 45, 53, 56, 63 (~240 seeds, 2-4 buses, 1-2 depots, slot_minutes 60, 3-4 slots); it checked only plan charges and the summary triple against brute force. Stress run steps 46-52 (800 buses, runtime only).
"Varied?" = did a2's own fuzz vary this branch. "Ref same?" = reference applies the same reading (by reading, then confirmed by fuzz, see A2_SCORE.md).

| Rule (CR line) | a2 lines | a2 fuzz varied? | Ref same? | Note |
|---|---|---|---|---|
| R1 slots, names (:7) | load_plan 87-108 | partly (60-min slots, 3-4 slots; never 15 min / 96) | yes | a2 rejects 1440 % slot_minutes != 0 |
| R2 "from X to Y" = slot start in [X,Y) (:8) | tariff 197-237, caps 666-682 | aligned spans only | yes | off-grid spans: both slot-start test |
| R3 roster plan_date filter (:12) | 585-588 | yes (other-date row) | yes | a2 string compare, ref date parse; same on ISO |
| R4 reject order unknown/retired/duplicate/bad_window (:13) | 593-604 | yes (BXXX, BRET, copy of row 0, reversed window) | yes | never varied arrive<first / depart>end; dup = accepted earlier (accepted_ids) in both |
| R5 window, roster depot (:14) | 606-628 | yes (roster depot random) | yes | off-grid arrive/depart never varied |
| R6 type, max, reserve (:15) | 124-135, 607-612 | yes | yes | |
| R7 need = trips(day after)+extras+reserve-soc, clamp 0 (:16) | trips 177-194, extras 569-572, 620-622 | yes (plan-date decoy trips, extras next day only) | yes | extras on other dates / buses off plan never varied |
| R8 class, blank/unlisted -> commercial, weights (:17) | 138-161, 617 | yes (P1/C1/''/ZZ) | yes | weight 0 never varied |
| R9 whole kWh 0..max in window, total <= need (:21) | network 703-740 | yes | yes | |
| R10 cabinets minus outages x cabinet_kwh (:22) | 666-674 | one outage line; never overlapping | yes | overlapping outages summed, clamp 0 in both |
| R11 feeder base replaced by derate (:23) | 675-682 | one derate <= base only | yes | above-base derate = "replaced" in both (uplift lever a1 failed); overlapping derates: last line wins in both, docs silent |
| R12 tariff versions, k fit, equal parts, cents (:27) | 197-293, prices 685-693 | yes (2 versions, k random, midnight-crossing sessions) | yes | never varied version ending on plan date; a2 DataError on bands off the slot grid (ref floors) |
| R13 published rows, outside window reject, sum (:28) | 641-663 | yes (pub > rate, outside window, unknown bus) | yes | off-grid slot_start -> reject in both |
| R14 moved (:29) | weights 696-701, reports 949-953 | yes (summary triple) | yes | |
| R15 lexicographic objective + tie-break (:33) | 696-701, min_cost_flow 380-473, tie-break 742-817 | objective yes; tie-break only via charges on tiny cases | yes | both lock (slot,bus) then push zero-reduced-cost cycles |
| R16 one joint plan (:34) | build 548-835 | yes | yes | |
| R17 policy_audit, unmet_reason, changed (:40) | 848-897 (unmet_reason 880, changed 867-872, write 895) | no (never checked) | yes | |
| R18 region docs (:41) | 900-934 (write 925) | no | yes | |
| R19 segment docs (:42) | 935-945 (write 937) | no | yes | |
| R20 summary (:43) | 946-968 (write 955, peak 960, changed 965) | triple only | yes | feeder_peak, buses_changed never checked by a2 |
| R21 data_quality sorted, physical line (:44) | read_rows 35-50, write 970 | no | NO on blank lines | ref DictReader skips blank lines -> line off by one; a2 physical line correct (reference bug) |
| R22 missing/unreadable file -> nonzero, names file (:48) | DataError paths, main | no | yes | |
| disruption_notice.md format (data) | load_disruption 294-330 | fixed format | yes on shipped format | a2 lenient regex vs ref strict; only differs off format |
