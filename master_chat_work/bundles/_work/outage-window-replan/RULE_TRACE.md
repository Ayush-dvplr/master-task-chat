# RULE_TRACE (one row per generator branch in tests/test_output.py)

Docs: C = environment/data/docs/replan_contract.md, I = docs/intake.md, O = docs/output_schema.md. Lines = tests/test_output.py.
Hidden families graded per corpus h2 (seed 70413) and h3 (seed 88261): region_x4 w5, policy_audit w5, segment_x2 w3, summary w3, data_quality w3.

| rule id | sentence file:line | generator branch that plants it | tests that grade it |
|---|---|---|---|
| S-1 min risk-days | C:35, C:31 | contention clusters + bridges, role cluster (121-126); stuck requests (156) | h2/h3 region_x4, policy_audit, segment_x2, summary |
| S-2 fewest moved | C:36 | keep pair keepX/keepY (144-145); random published plan (published_plan) | h2/h3 region_x4 (moved), policy_audit (moved), summary (moved) |
| S-3 start list tie-break | C:37 | tie pair tieL/tieH own stream seed*104729+17 (134-135) | h2/h3 region_x4 (schedule), policy_audit, segment_x2 |
| deferral penalty | C:31 | stuck requests (156), contention clusters (121-126) | h2/h3 segment_x2, summary, region_x4 |
| reason no_feasible_start | C:43 | stuck request with crew loss to 0 (156) | h2/h3 policy_audit |
| reason predecessor_deferred | C:44 | stuck precedence to later plain request (build_inputs, after 322) | h2/h3 policy_audit |
| reason displaced | C:45 | contention clusters (121-126) | h2/h3 policy_audit |
| incompatible pairs | C:24 | incompatible twin role incpair (304-311), random inc pairs | h2/h3 policy_audit, region_x4 |
| precedence | C:25 | precedence follower role precpair (313-322), random prec among plain | h2/h3 policy_audit, region_x4 |
| no-effect constraint entries | C:27 | ghost inc/prec pairs (render, network constraints) | h2/h3 policy_audit |
| blackout forbids start only | C:22 | region blackout days (build_inputs) | h2/h3 policy_audit, region_x4 |
| crew capacity less CREW_LOSS, add up | C:15, I:36 | cluster loss runs + extra loss as two overlapping notices (181) | h2/h3 region_x4, policy_audit |
| class weights from risk_policy.toml | C:7 | release_literals public 3 or 4 (57) | h2/h3 segment_x2, summary |
| load bands, largest min_mw not above peak | C:11 | release_literals band2/band3; peak_rows boundary peaks | h2/h3 region_x4, segment_x2 |
| defer factor from risk_policy.toml | C:31 | release_literals defer 5 or 6 (57) | h2/h3 segment_x2, summary |
| events at or before published_at no effect | I:34 | pre-publication CREW_LOSS / NEW_REQUEST; notice stamped exactly at published_at (608) | h2/h3 policy_audit, data_quality |
| HEARTBEAT no effect, not counted | I:28 | heartbeat lines (render log) | h2/h3 data_quality |
| malformed lines counted in ignored_lines | I:29-33 | CREW_RESTORE (578), CREW_LOSS from>to (579), duration_days=two (580), pre-pub missing `to` | h2/h3 data_quality |
| check order | I:11 | records failing two checks at once, own stream seed*7+3 (496) | h2/h3 data_quality |
| unknown_asset | I:13 | ghost records in requests.json and log (575) | h2/h3 data_quality |
| out_of_season | I:14 | spare out-of-season records | h2/h3 data_quality |
| window_too_short | I:15 | dur5 window 40-43 records; log NEW_REQUEST dur4 50-52 | h2/h3 data_quality |
| duplicate_request incl withdrawn | I:16 | duplicates of published records; NEW_REQUEST of first withdrawn asset (570) | h2/h3 data_quality |
| rejected then later accepted | I:16, I:18 | rejected record followed by valid record of same asset (508) | h2/h3 data_quality, policy_audit |
| WITHDRAW | I:38 | withdraw of published plain requests (565); WITHDRAW of non-request spare | h2/h3 data_quality, policy_audit |
| NEW_REQUEST position = log line | I:37 | log-side rejections | h2/h3 data_quality |
| control-room requests never moved | C:36 | new requests (keepY, tie pair, incpair, precpair, 40% cluster) | h2/h3 policy_audit, summary |
| output orders | O:3, O:24, O:46 | every corpus | every whole-document test |
| missing input names the file | instruction.md:11 | customers.csv deleted from shipped copy (1394) | missing_customers_named |
