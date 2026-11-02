# RULE_TRACE: one row per generator branch (embedded generator in tests/test_output.py = WORK/gen_core.py)

Docs = environment/data/docs/charging_rules.md. Tests: H = fresh_h1..h4 families (w5 each), S = shipped_* (w3), Q = fresh_h1/h3_data_quality_exact, A = reordered_copy_policy_audit_exact, L = relocated_copy_summary_exact, M = missing_settlements_stops_naming_file.

| rule id | sentence file:line | generator branch that plants it | tests that grade it |
|---|---|---|---|
| R1 feeder limit | docs:23 rule 11 | gen(): hidden feeder = 45-65% of published peak, 10% slots halved | H (all 32), A, L |
| R1b feeder derating | docs:23 rule 11 + notice section | gen(): derate block d0..d0+dl at 30%; render(): '## Feeder derating' lines (shipped one non-binding block) | H, A, L |
| R3 depot cabinets | docs:22 rule 10 | gen(): hidden cap 50-90% of depot peak in multiples of 15 | H, A, L |
| R3b cabinet outage | docs:22 rule 10 + notice section | gen(): outage block o0, len 2-8 at c//2; render(): '## Cabinet outages' lines (shipped two non-binding) | H, A, L |
| M meter convention | docs:27 rule 12 | conv(): hidden distinct shifts per depot from range(4,92), unique-fit loop over 14 settled days; shipped shift 0 | H (regions, segments, summary cost fields; audit via plan) |
| M2 tariff versions | docs:27 rule 12 (valid_from/valid_to) | render(): 3 versions, settled days under the two old ones | H, S |
| T lexicographic order | docs:33 rule 15 terms 1-3 | gen(): hidden partial published chunks (25%), short-window cluster in derate block (term 1), flat price bands (ties) | H, A |
| T4 tie-break | docs:33 rule 15 last clause | gen(): flat bands + binding limits give many equal optima on hidden; shipped published = unique optimum | H (audit charges) |
| C coupling | docs:34 rule 16 | every hidden corpus: one feeder shared by 4 depots | H |
| P1 slots and spans | docs:7 rule 1, :8 rule 2 | render(): ISO stamps on 15-min boundaries; notice spans | S, H |
| P2 plan-date roster rows | docs:12 rule 3 | render(): 42 padding days of roster/trips/published | S, H |
| P3 rejection order | docs:13 rule 4 | render(): unknown B9990, retired, duplicate after original, bad window; rare stream: arrive before first slot, depart after end, arrive == depart, bad row before a valid row | S data_quality, Q |
| P4 window and depot | docs:14 rule 5 | render(): depot from roster row | S, H |
| P5 bus type | docs:15 rule 6 | render(): fleet_register types E12/E15/E18 | S, H |
| P6 need | docs:16 rule 7 | render(): trips on plan+1 split 2-4, soc = reserve + x, extra trips in notice; rare stream: extra trip dated plan date (ignored) | S audit, H |
| P7 class | docs:17 rule 8 | render(): contracts public/commercial, blank contract; rare stream: unlisted 'SCH-nn' -> commercial | S segments, H |
| P8 per-bus bounds | docs:21 rule 9 | gen(): rates 30/45/60, need cap | H |
| P9 published plan | docs:28 rule 13 | render(): published rows incl one outside window | S data_quality, Q, H |
| P10 moved energy | docs:29 rule 14 | gen(): partial published chunks on hidden | H summary, A |
| P11 reports | docs:40-44 rules 17-21 | all kinds | S, H, Q |
| P12 unreadable input | docs:48 rule 22 | test helper _without_settlements | M |
