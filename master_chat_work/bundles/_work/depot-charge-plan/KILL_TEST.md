# KILL_TEST depot-charge-plan (board 154f570)

All rows run in Docker only: `docker run --rm --memory 4g --cpus 2 python:3.12-slim`, wall cap `perl -e 'alarm CAP; exec @ARGV'`
(dockfree START=yes before every block). Prototype: WORK/proto/{gen_proto.py, core.py, compare.py, killall.sh, brute.py}.
Scratch and logs: _runs/20261101/depot-charge-plan/kill-20261101T0130/{scratch*,logs/block*.log}.

Instances: `shipped:k` = degenerate shipped-like day (no supply limit binds; bindF 0, bindC 0);
`hidden:k` = 70-120 buses, feeder binds in 11-20 slots and depot supply in 1-12 slots, derate block, flat tariff bands;
`large:k` = same generator at 350-450 buses (the one held-out large corpus).
"lever points kept" = output families identical to the reference out of 8 (policy_audit, region x4, segment x2, summary);
every family carries the feeder-shared plan, so one wrong plan choice moves all 8.

Brute force (brute.py, 300 tiny instances, every feasible integer plan enumerated): reference = brute optimum on 300/300,
optimum unique under the full order on 300/300 (log logs/brute.log `BRUTE checked 300 mismatches 0`).

## Summary table

| solver | instance | seconds | WRONG / TIMEOUT / CRASH / EXACT | lever points kept | shipped inputs fast |
|---|---|---|---|---|---|
| greedy_id (per bus, bus id order, cheapest slot, published first) | shipped | 0 | EXACT | 8/8 | yes |
| greedy_id | hidden 1-6 | 0-1 | WRONG | 0/8 each | yes |
| greedy_edf (earliest departure first) | hidden 1-6 | 0-1 | WRONG | 0/8 each | yes |
| greedy_class (public class first) | hidden 1-6 | 0-1 | WRONG | 0/8 each | yes |
| greedy_swap (greedy + improving swaps) | hidden 1-6 | 0-1 | WRONG | 0/8 each | yes |
| depot_prorata (per-depot exact, feeder trimmed pro rata) | hidden 1-6 | 0-1 | WRONG | 0/8 each | yes |
| depot_priority (per-depot exact, feeder trimmed by class) | hidden 1-6 | 0-1 | WRONG | 0-1/8 | yes |
| split_exact (split into independent parts, exact flow per part) | hidden 1-6 | 0-1 | WRONG (one part: feeder joins all) | 0/8 each | yes |
| flow_plain (exact min-cost flow on terms 1-3, first optimum found) | hidden 1-6, large 1-2 | 0-6 | WRONG (same objective, other plan) | 0/8 each | yes |
| flow_eps (flow + per-slot epsilon tie) | hidden 1-6 | 0-1 | WRONG | 0/8 each | yes |
| flow_post (flow + post-pass moving energy to earlier slots) | shipped, hidden 1-6 | 0-1 | WRONG (term 3 higher) | 0/8 each | yes |
| careful_resolve (natural exact: fix each (slot, bus) in order by re-solving) | shipped (250 buses) | 300 | TIMEOUT | 0/8 | no (shipped itself slow) |
| flow_bigint (careful exact: whole order folded into one big-integer cost) | hidden 1-3 | 3-4 | EXACT | 8/8 | yes |
| flow_bigint | shipped (250 buses) | 55 | EXACT | 8/8 | slow-ish |
| flow_bigint | large 1-2 (371, ~400 buses) | 172, 157 | EXACT (TIMEOUT under a 120 s per-run limit) | 8/8 (0/8 at 120 s) | see block5 |
| reference (flow + exact tie pass) | shipped / hidden / large | 1.9 / 0.4-0.7 / 7.1 | EXACT | 8/8 | yes |

Block5-8 (shipped now 120 buses with the published plan the unique optimum; logs block5.log .. block8.log, all ALL_DONE):

| solver | instance | seconds | WRONG / TIMEOUT / CRASH / EXACT | lever points kept | shipped inputs fast |
|---|---|---|---|---|---|
| greedy_id, greedy_edf, greedy_class, greedy_swap, depot_prorata, depot_priority, split_exact, flow_plain, flow_eps | shipped 1-3 | 0-1 | EXACT | 8/8 | yes |
| same 9 programs | hidden 4-6, large 3 | 0-7 | WRONG | 0/8 each | yes |
| flow_post | shipped 1-2, hidden 4-6, large 3 | 0-7 | WRONG | 0/8 | yes |
| bigint_min (exact, tie-break read as lex-min) | shipped 1-3 | 5-8 | EXACT (tie never decides on shipped) | 8/8 | yes |
| bigint_min | hidden 4 | 3 | WRONG | 0/8 | yes |
| flow_bigint (careful exact, lex-max fold) | shipped 1-2 / hidden 4-6 / large 3 | 8, 6 / 2-8 / 186 | EXACT / EXACT / TIMEOUT at 120 s | 8/8 / 8/8 / 0/8 | yes |
| ref_nofeed (reference without R1 feeder) | shipped 1 / hidden 1-4, large 1 | 0 / 0-5 | EXACT / WRONG (infeasible plan) | 8/8 / 0/8 | yes |
| ref_nocab (reference without R3 cabinets) | shipped 1 / hidden 1-4, large 1 | 0 / 0-7 | EXACT / WRONG | 8/8 / 0, 0, 3, 1, 0 of 8 | yes |
| ref_noterm3 (reference without term 3 moved energy) | shipped 1 / hidden 1-4, large 1 | 0-7 | WRONG on shipped too (term 3 is a plain rule visible on shipped) / WRONG | 0/8 | yes |
| reference | shipped 1-3 / hidden 1-6 / large 1-3 | 0.4-0.45 / 0.3-0.9 / 5.7-7.6 | EXACT | 8/8 | yes |
| careful_resolve | hidden 1-2 (CAP 600) | 600 | TIMEOUT (killed by alarm, no output) | 0/8 | no |

careful_resolve is the per-position re-solve a reader writes from the tie-break sentence; it does not finish shipped (250 buses, 300 s) or hidden (600 s), so a solver who writes it notices on shipped and switches method; it is not counted as a hidden-scale loss.

## Reading

Every per-bus, per-depot, split and plain-flow program is exact on shipped and WRONG on every hidden corpus with 0/8 families
kept. The only exact non-reference program is the big-integer fold of the full order (flow_bigint): it is the careful-reader
row G-10(a) asks for. At hidden sizes it is exact; at the large corpus it costs 22-24x the reference (G-10(c) ratio > 4x),
so under a plain stated per-run limit it loses the large corpus only (v3.5 hidden-scale loss, cost confined to one corpus).

Risk (hangar lesson): a careful reader who writes the reference method (exact optimum on terms 1-3, then a position-by-position
tie pass on the zero-reduced-cost face, or the big-integer fold) is EXACT on regular hidden corpora. The kill table passes for
every generic solver and for every all-but-one variant (each sharp rule alone costs 0/8 families on every hidden corpus), but
whether a blind reader writes an exact program is decided only by the design blind (Phase 0b).

## Design blind fd98e12 (scored 1 Nov 02:27 IST)
Program copied to proto/blind_fd98e12/derive_report.py (811 lines; min-cost flow primal-dual + `lex_refine` over the optimal face; 7 min to first write). Docker python:3.12-slim --memory 4g --cpus 2, perl alarm 120 per run, log `_runs/20261101/depot-charge-plan/score-fd98e12/logs/score.log` (ALL_DONE). Compared whole document per family with the prototype reference outputs (p0b-20261101T0210/scratch_b/<corpus>/ref).

| solver | instance | seconds | WRONG / TIMEOUT / CRASH / EXACT | lever points kept | shipped inputs fast |
|---|---|---|---|---|---|
| design blind fd98e12 | shipped:1 | 0.36 | EXACT | 9/9 | yes |
| design blind fd98e12 | hidden:1 | 0.34 | EXACT | 9/9 | yes |
| design blind fd98e12 | hidden:2 | 0.34 | EXACT | 9/9 | yes |
| design blind fd98e12 | hidden:3 | 0.32 | EXACT | 9/9 | yes |
| design blind fd98e12 | large:1 | 1.49 | EXACT | 9/9 | yes |

Lever points kept 100%; lost 0% (no WRONG, no TIMEOUT, no CRASH). The blind is faster than the reference on large (1.49 s vs 5.34 s), so no time lever exists either. Verdict: NO CORE (G-8).

## Redesign G-8: per-depot meter convention (02:30-02:45)
New hardness source on top of v1: each depot's meter applies the tariff with its own convention (hidden: a per-depot cyclic slot shift k_d, distinct, never 0; shipped: identity at every depot). Rule 12 states the convention is the one under which the depot's `settlements.csv` rows bill exactly, by the tariff version in force on each settled date, and that exactly one fits. The docs never name what the convention could be. Settled days fall under two older tariff versions, so per-slot prices learned from history do not carry to the plan date; only the convention carries. Generator asserts a unique k in range(96) per depot.

Instance-level kill rows (proto2/killconv.py, log conv-20261101T0240/logs/conv1.log ALL_DONE; each fitter yields per-depot prices, then the reference planner; 8 families vs reference):

| solver | shipped1 | hidden1 | hidden2 | hidden3 | hidden4 | large1 | verdict on hidden |
|---|---|---|---|---|---|---|---|
| (a) literal: tariff as stated, else per-depot multiplier sum(cents)/sum(stated) | EXACT 8/8 | 0/8 | 0/8 | 0/8 | 0/8 | 0/8 | WRONG |
| (b) careful enumerator: identity, start/end/previous-slot price, session start/max/min, multiplier; least residual | EXACT 8/8 | 0/8 | 0/8 | 0/8 | 0/8 | 0/8 | WRONG |
| (c) fd98e12 reading: tariff as stated | EXACT 8/8 | 0/8 | 0/8 | 0/8 | 0/8 | 0/8 | WRONG |
| (d) shipped convention carried (identity) | EXACT 8/8 | 0/8 | 0/8 | 0/8 | 0/8 | 0/8 | WRONG |
| (h8) first fitting shift on first settled day | EXACT | 8/8 | 8/8 | 8/8 | 8/8 | 8/8 | EXACT (risk) |
| (b+) every cyclic shift, unique fit (= reference) | EXACT | 8/8 | 8/8 | 8/8 | 8/8 | 8/8 | EXACT (risk) |

Real program run on rendered files (log conv-20261101T0240/logs/render1.log): fd98e12 `derive_report.py` (written for v1 docs) keeps 2/9 on shipped1 (its single-version tariff parser misreads the new versioned tariff.xml: cost fields only) and 1/9 on hidden1-3 (cost fields everywhere plus planner differences from the depot prices). The shipped loss is a format artefact of v1, not a lever result.

Reading: every program that does not search for a per-slot shift loses all 8 families on every hidden corpus by WRONG output, and all are EXACT on shipped. The lever holds only if a careful reader does not think to test shifts; any program that tests all 96 shifts (or the first settled day) is EXACT. The design blind decides this (same honest risk as warrant P6o).

## Design blind d9d6ab5 (redesign G-8, scored 1 Nov 02:59)
Docker python:3.12-slim --memory 4g --cpus 2, per-run alarm 120 s; log `_runs/20261101/depot-charge-plan/score-d9d6ab5/logs/score.log` (ALL_DONE). Reference = proto2 outputs (redesign; conv-20261101T0240/scratch_r/<c>/ref, plus new renders hidden4-6). Program copy: WORK/proto/blind_d9d6ab5/derive_report.py (859 lines; pick_meters tries 5 slot readings, falls back to slot_start; no shift search).

| solver | instance | seconds | WRONG / TIMEOUT / CRASH / EXACT | lever points kept | shipped inputs fast |
|---|---|---|---|---|---|
| blind d9d6ab5 | shipped1 | 0.40 | EXACT (audit, regions, segsum, quality OK) | n/a (shipped) | yes |
| blind d9d6ab5 | hidden1 | 0.60 | WRONG audit /buses[0]/charges[0]/slot; regions, segsum cost_cents; 69/83 bus rows differ | 0/3 | yes |
| blind d9d6ab5 | hidden2 | 0.58 | WRONG audit /buses[0]/changed; 79/108 rows | 0/3 | yes |
| blind d9d6ab5 | hidden3 | 0.80 | WRONG audit /buses[0]/charges[0]/slot; 78/95 rows | 0/3 | yes |
| blind d9d6ab5 | hidden4 | 0.57 | WRONG audit /buses[1]/charges[0]/slot; 58/78 rows | 0/3 | yes |
| blind d9d6ab5 | hidden5 | 1.01 | WRONG audit /buses[1]/charges[0]/kwh; 83/120 rows | 0/3 | yes |
| blind d9d6ab5 | hidden6 | 1.00 | WRONG audit /buses[0]/changed; 83/107 rows | 0/3 | yes |
| blind d9d6ab5 | large1 | 8.63 | WRONG audit /buses[0]/charges[0]/slot; 277/374 rows | 0/3 | yes |

Weighted unmet equals the reference on every corpus (its planner is exact); energy cost is the tariff-as-stated value (identity meter) on every hidden corpus, so the per-depot meter convention is the whole loss. data_quality exact everywhere. Lever points lost by WRONG: 100% (0 TIMEOUT, 0 CRASH).

## Fix v2 kill table (board 0d6348c, 1 Nov 11:56-12:01 IST, final tests, tree 3e4d3ee74385)
Docker dcp-verifier:1, --memory 4g --cpus 2, alarm 2400 per program; programs and logs `_runs/20261101/depot-charge-plan/fix2-20261101T1135/kill/` (progs/, w/, logs/kill.log and kill2.log, each program EXIT rc=0). Tests-only reward 1/197. Lever = 32 fresh plan checks (w5) + reordered + relocated + default paths (w3 each) = 169 of 197.

| program | tests (of 197) | lever kept (of 169) | loss kind |
|---|---|---|---|
| blind1 (blind1-20261101T0345 out/derive_report.py) | 10 (5.1%) | 0 | WRONG (runs, plan differs on shipped and every fresh folder) |
| blind2 | 6 (3.0%) | 0 | CRASH (shipped: no tariff application fits depot East) |
| blind3 | 6 (3.0%) | 0 | CRASH (shipped: no tariff reading bills depot East as settled) |
| first-write (oracle without tie pass, meter k = 0) | 13 (6.6%) | 0 | WRONG |
| all-but-one (oracle without tie pass) | 16 (8.1%) | 0 | WRONG |
| careful shift search as saved (fix1 progs/careful, pre-rule-13 sentence) | 165 (83.8%) | 151 | WRONG on summary and data_quality: rejects a published row of a bus not on the plan |
| careful shift search + rule 13 sentence (careful_r13) | 197 (100%) | 169 | none (EXACT); recorded per route-1 R5(d), not a blocker |
| oracle solve.py | 197 | 169 | none |
