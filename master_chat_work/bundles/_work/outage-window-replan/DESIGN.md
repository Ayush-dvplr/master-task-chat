# DESIGN 7d363c8 outage-window-replan (Shape D, P-3 exact optimum + N2 held-out w5 tier)

## 0. One-paragraph picture
A transmission operator published a maintenance-outage season (91 days, 4 regions). A control-room log then reports crew losses, new urgent requests and withdrawals. The agent writes `/app/out/derive_report.py`, which rebuilds the replanned season from the data folder and writes ten documents. The replanned season is the lexicographic optimum of (1) total weighted risk-days including deferral penalties, (2) number of published outages moved, (3) start-day list in ascending asset-id order with a deferred request ranked after every season day. Every figure in every output is computed from that one season (COUPLING). On the shipped season every plausible greedy, local-search and B&B program finds the optimum (quiet instance, S2); on the verifier's fresh seasons (more requests per lane, contention clusters, planted exact ties) they return feasible but non-optimal or wrongly tie-broken seasons (WRONG stage, Law-1 v3.4).

## 1. Spine stages
1. Load and validate inputs; reject bad request records into data_quality (stated reasons).
2. Apply control-room events stamped after the publication time (crew losses, new requests, withdrawals).
3. Build per request: lane (region, crew type), weight (customer classes x class weights), allowed start days (window, blackout, crew capacity), per-start risk-days (weight x band factor per day out), deferral penalty.
4. Solve the replan: lexicographic optimum per lane (constraints never cross a lane, stated in the network spec as a data fact: every pair joins two assets of one region and one crew type).
5. Assign deferral reasons, moved flags.
6. Write policy_audit, region x4, segment x2, summary, data_quality from the one season.

## 2. Input files (environment/data/, 13 files, 7 formats: md, json, jsonl, csv, tsv, toml, log)
| file | format | rows (shipped) | role / depends on |
|---|---|---|---|
| docs/RULES.md | md | ~40 | rule register: names each governing file and the rules it governs; arbiter sentence (contract wins) |
| docs/replan_contract.md | md | ~150 | objective order, moved, deferral and reasons, tie-break, COUPLING sentence, every output key/type/sort order, rejection reason strings, invocation and per-run limit |
| assets.jsonl | jsonl | 2400 | asset_id (opaque `A` + 5 digits), region, kind (line/transformer), crew_type (line/substation/protection) |
| requests.json | json | ~110 records (~100 valid) | asset_id, duration_days, earliest_start, latest_finish, crews; depends on assets |
| customers.csv | csv | 9000 | customer_id, asset_id, class (commercial/public); weight = sum of class weights |
| risk_policy.toml | toml | ~25 | class weights, load bands (daily peak MW thresholds -> factor 1/2/3), defer factor 4 |
| load_forecast.tsv | tsv | 2184 (4 regions x 91 days x 6 periods) | daily peak = max over periods -> band factor |
| crew_roster.jsonl | jsonl | ~2200 | crew_id, region, crew_type, day, status (on_duty/leave): capacity = on-duty count |
| published_plan.json | json | ~100 | published start (or deferred) per asset, publication timestamp |
| network_constraints.json | json | ~15 | incompatible pairs (no common day out), precedence pairs (successor starts the day after predecessor ends or later; predecessor deferred -> successor deferred) |
| region_calendar.json | json | 4 x ~6 | blackout days (no outage may start) per region |
| control_room.log | log | ~2400 | timestamped events: CREW_LOSS region type day_from day_to count, NEW_REQUEST record, WITHDRAW asset; heartbeat/noise lines; only events after the publication timestamp apply |
| docs/output_schema.json | json | ~120 | JSON schema of the ten outputs (keys, types) |

Chains of length >= 4:
- C1 customers.csv class -> risk_policy.toml class weight -> request weight -> load_forecast.tsv daily peak -> risk_policy.toml band factor -> risk-days -> objective -> every output.
- C2 crew_roster.jsonl on-duty count -> control_room.log CREW_LOSS (after publication) -> lane capacity -> allowed starts -> schedule -> region crew_days.
- C3 assets.jsonl (region, crew_type) -> requests.json -> lane -> network_constraints.json pair -> feasible schedule -> policy_audit.
- C4 published_plan.json start + timestamp -> control_room.log event filter -> moved flag (level 2) -> policy_audit moved, summary moved.
- C5 control_room.log NEW_REQUEST -> assets.jsonl lookup -> data_quality rejection or new request (never moved) -> schedule.
A5 volume: customers 9000, assets 2400, roster ~2200, load 2184, log ~2400 => > 18k + json/md; customers raised if needed so total >= 20,000 and every csv/tsv/jsonl/log >= 2,000.

## 3. Sharp rules (Shape D: 3) and stated noise rules
All three are stated word for word in docs/replan_contract.md section "Objective" (W2); RULES.md points there.

### S-1 level 1: minimum total weighted risk-days (with deferral penalty)
- Text: "Among all feasible replanned seasons, the published one has the smallest total risk-days, where a scheduled outage contributes its weight times the sum of the load-band factors of its days out and a deferred request contributes its weight times its duration times the defer factor."
- Reflex reading (PREMORTEM): correct reading, wrong method: greedy by weight or deadline, greedy + local swaps, repair of only the disrupted outages, or B&B with a wall-clock guard returning its incumbent.
- Hidden cases: every lane of H2/H3 has 2-4 contention clusters (cheap factor-1 stretch L 5-9 days flanked by factor-3 days, crew loss to capacity 1 over the stretch +-4 days, 4-6 members of duration 2-4 whose windows overlap the stretch), n 18-24 per lane, filler windows long so window-overlap components do not split the lane.
- Why visible data cannot confirm: shipped lanes (n 6-10) are rejection-sampled until every solver in KILL_TEST is exact (BRANCH_FIRE shipped 0); a program that matches its own brute force on shipped lanes is still wrong on contended lanes.
- Interaction: an S-1 slip moves risk-days in its region file, its policy_audit rows, both segment files and the summary (COUPLING amplification).

### S-2 level 2: fewest published outages moved
- Text: "Among seasons equal on level 1, the published one moves the fewest outages; an outage is moved when it appeared in the published plan and its replanned start differs from its published start, a published outage that becomes deferred is moved, a request that was deferred in the published plan and stays deferred is not moved, and a request added by the control-room log is never moved."
- Reflex reading: moved computed but used after the start-vector tie-break (first fit by earliest start), or ignored when the cheapest start is found.
- Hidden cases (own RNG stream): per region at least one "keep" pair: a published request inside a flat factor stretch whose published start is not the earliest equal-cost start, plus a second request that makes the earliest start reachable only by moving it.
- Visible data: shipped published starts are all earliest-cost starts (shipped count 0).

### S-3 level 3: start-day list in ascending asset-id order
- Text: "Among seasons equal on levels 1 and 2, the published one has the smaller start-day list, read in ascending asset_id order, at the first asset where two seasons differ; a deferred request counts as later than every season day."
- Reflex reading: first optimum found in the program's own search order (heuristic order, time order, DP edge order) is published.
- Hidden cases (own RNG stream `seed*104729+17`): per lane 1-2 exact tie pairs (flat factor-1 stretch of length d1+d2 at capacity 1 flanked by factor-3 days, both windows equal the stretch, the lower asset_id is the lighter request, both new so moved is 0). Swapping the two is cost-equal; only S-3 decides.
- Visible data: shipped lanes rejection-sampled with no exact tie among optimal seasons (dp_nofix exact on shipped).

### Stated noise rules (not budgeted levers; each written once in its governing file)
R1 weight (customers.csv + risk_policy.toml); R2 daily peak = max over periods (load_forecast spec in contract data section); R3 band thresholds inclusive lower bound (risk_policy.toml); R4 capacity = on_duty count (crew_roster); R5 CREW_LOSS reduces capacity on day_from..day_to inclusive, floor 0; R6 events at or before the publication timestamp are already in the published plan and are skipped; R7 blackout forbids starts only; R8 window inclusive; R9 incompatible = no common day out; R10 precedence; R11 deferral penalty; R12 deferral reason (first that applies: no_feasible_start, predecessor_deferred, displaced); R13 rejection reasons (unknown_asset, duplicate_request keeps the first record in file order, window_too_short, out_of_season); R14 withdrawn requests leave every output except data_quality counts; R15 output sort orders; R16 segment split (class share of each request's risk-days by class weight sum); R17 crew_days = crews x duration. About 20 stated rules over 13 files in 7 formats.

## 4. BRANCH_FIRE (see WORK/BRANCH_FIRE.md)
Hard branches: (S-1) greedy-class or capped-search season is non-optimal; (S-2) earliest-equal-cost choice moves a published outage; (S-3) search-order first optimum differs from the asset-id least start list. Shipped count 0 for all three (rejection sampling with the full KILL_TEST solver set); every hidden corpus that grades them (H2, H3) fires each in every region.

## 5. Rejection paths
data_quality.json: rejected request records (source file, asset_id, reason) for unknown_asset, duplicate_request, window_too_short, out_of_season; rejected NEW_REQUEST log lines with the same reasons; counts per reason. Malformed log lines (no parseable event) are counted as `ignored_lines`. A missing or unreadable declared input stops the program with a non-zero exit and a message naming the file (stated in the contract; graded by M3).

## 6. Test plan (LEVER_RULES G1-G13)
Instruction states: whole-document exactness on fresh inputs ("each output document is graded whole, and only an exact match counts"), rerun promise ("the program is run again on fresh data folders in the same layout"), invocation `python3 /app/out/derive_report.py --data <data dir> --out <out dir>`, per-run limit 300 s.
| id | corpus | owns | weight |
|---|---|---|---|
| T01 shipped_policy_audit | shipped /app/out | policy_audit.json whole | 3 |
| T02 shipped_summary | shipped | summary.json whole | 3 |
| T03 shipped_data_quality | shipped | data_quality.json whole | 3 |
| T04-T07 h2_region_{North,South,West,East} | H2 | region file whole | 5 each |
| T08 h2_policy_audit | H2 | whole | 5 |
| T09-T10 h2_segment_{commercial,public} | H2 | whole | 3 each |
| T11 h2_summary | H2 | whole | 3 |
| T12 h2_data_quality | H2 | whole | 3 |
| T13-T21 | H3 | same nine | 37 |
| M1 shuffled_copy | shipped rows shuffled, one weight scaled | policy_audit whole | 3 |
| M2 relocated_foreign | shipped copy in another dir, foreign uid, foreign cwd | summary whole | 3 |
| M3 missing_input | shipped copy with customers.csv deleted | non-zero exit AND message names customers.csv | 3 |
| N1 negative hardcoding | reads verifier paths `/tests/`, `/logs/verifier` | -5 |
Positive total 92; hidden H2+H3 74 (80.4%); w5 tier 50 (54.3%); lever families (region, audit, segment, summary on H2/H3) 68 (73.9%). Region and segment files from the shipped run are graded through M-tests and hidden reruns, not separately (TS-13: every test opens one output file). Hidden generator embedded in tests/, seed only in tests/, rare fixtures (ties, keep pairs) on own RNG stream, bounds asserted, 300-seed survival. OWNED map: each document owned once per corpus.

## 7. Judge plan (J1-J10)
8 probes w3 (P-a optimality witness on a self-built lane where greedy is wrong; P-b one-instance witness: one request's risk-days recomputed by hand from customers, policy and load rows; P-c objective recomputed outside the program from policy_audit; P-d altered-copy rerun (one weight or crew changed) with a moved output; P-e relocated rerun; P-g uniqueness witness: a tie built by hand resolved by asset-id order; P-h missing input run; P-a2 brute-force comparison on a small lane), J4 w3, J6 w5 (lists every deferred request of the shipped season by asset_id with its reason), J10 w3 (stated process order). Negatives J3a -3, J3b -5, J3c -3, grader-read -5. Positive 35; probe share 68.6%. Estimate (section 6 method): probes 25% = 6, J4 50% = 1.5, J6 50% = 2.5, J10 50% = 1.5 -> mid 11.5/35 = 32.9%; lower ~15%; upper ~55%.

## 8. Expected loss per lever and predictions
| lever | hidden input | checks a careful solver loses |
|---|---|---|
| S-1 | H2/H3 contended lanes | T04-T11, T13-T20 (68 points) |
| S-2 | keep pairs per region | T04-T08, T11, T13-T17, T20 (56) |
| S-3 | tie pairs per lane | T04-T08, T13-T17 (50) |
Predicted first-write (B&B with guard, PREMORTEM a): shipped 9 + M 6-9 + h dq 6 + ~3 region = ~26/92 = 28%. All-but-S-3 (exact risk, tie wrong): 92-50 = 42/92 = 46%. Cost alone: S-1 74%, S-2 61%, S-3 54% (each >= 25%).

## 9. DESIGN READY bar
(a) predicted final = (28 + 32.9)/2 = 30.5 <= 35. (b) lever share 73.9% >= 40%; w5 tier 54.3% >= 50%. (c) blind ceiling: the strongest generic (comp_heur) keeps ~24% of region points => tests ~ (26 + 0.24*40)/92 ~ 39% < 65. (d) verifier worst: 5 agent runs x 300 s + reference ~10 s = 1510 s of a stated 2700 s verifier limit = 56% <= 90%. (e) kill table: every generic solver loses >= 15% of lever points by WRONG (greedy family 100%, guarded B&B 75-90%, comp_heur ~76%, dp_nofix 100% of region points), shipped < 0.1 s, reference 0.2 s per lane (~3 s per corpus) <= 75 s.
Main risk: a careful agent that writes the sweep/memo DP carrying lex-min (value, remaining start vector) per state is exact (reference class). PREMORTEM puts that near 10%; the design blind read tests it.
