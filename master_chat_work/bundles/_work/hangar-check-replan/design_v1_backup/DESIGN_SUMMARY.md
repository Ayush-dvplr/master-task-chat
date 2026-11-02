# DESIGN_SUMMARY hangar-check-replan (af5dddf, 31 Oct 2026 23:35 IST; Phase 0b update 23:46)

Core: replan a season of heavy maintenance checks for a fleet at four bases (one check line each) after a
disruption notice (closures, later available_from). Per check choose start day, compression x (overtime
shifts h*x) or deferral. Lexicographic order: T1 overdue weight + deferral penalty, T2 revenue days lost +
overtime cost, T3 moved count (start != published start, or deferred), T4 start-day vector then finish
vector in request_id order. One fleet overtime pool K across all bases. Outputs: audit json per check,
region and segment json roll-ups (every base and segment always reported), fleet summary, rejects (8 reasons). Program: `python3 /app/out/derive_report.py --data <dir> --out <dir>`, stated limit 60 s per run.
Shape D: shipped n=5 per base, pool slack, every request starts at published start, no tie, no deferral
(BRANCH_FIRE shipped all 0, seed 1). Hidden n=8 per base: pool binds non-convexly, tie on T1-T3, earliest
start != optimal start, plan_trade deferral, planted no_slot behind a season-end closure; h1, h2 also have one base with no
eligible request and an empty public segment (per-field checks region_empty, segment_empty, summary_empty_rows w1).
Sharp rules (3 + coupling): R1 one fleet overtime pool; R2 four-term order incl. moved term and start-day
vector tie; R3 any request may be deferred, reason no_slot / plan_trade; S3 every figure from the single
fleet-optimal plan.
Reference: per-base memo over (mask, line free day) with dominance starts {earliest, published}, pareto
frontier over exact overtime, fleet merge DP over overtime with vector key; brute-checked 400 tiny
instances, 0 mismatches. 3.2-3.5 s at hidden scale in Docker (6% of 60 s).

Kill table (Docker 4g/2cpu, hidden n=7 x 8 seeds, timing n=8 x 3 seeds; KILL_TEST.md):
| solver | shipped | hidden | lever pts kept | loss |
|---|---|---|---|---|
| greedy EDD, disrupted repair | WRONG | WRONG 8/8 | 0% | WRONG |
| split into bases, exact per base, pool shared fcfs / prorata / marginal | EXACT | WRONG 8/8 | 0-6% | WRONG |
| split into bases + memoised exact + frontier merge, first-found tie | EXACT | WRONG 6/8 | 44% | WRONG |
| same, revenue tie | EXACT | WRONG 8/8 | 25% | WRONG |
| same, earliest start only | EXACT | WRONG 8/8 | 0% | WRONG |
| same, defer only when no slot | EXACT | WRONG 8/8 | 0% | WRONG |
| plain exact over every start day, all readings right | EXACT 6-7 s | EXACT 119-142 s | 0% | TIMEOUT v3.5 |
| joint whole-fleet exact | - | >180 s at n=7 | 0% | TIMEOUT v3.5 |
| reference, bases/segments from records seen | EXACT | WRONG on h1, h2 empty axes | 93% | WRONG (stacks) |
Timeout share of lost lever points over the table 10.8%.

G-7 bar: (a) first-write tests 27 + judge mid 40 -> final 33.6 <= 35 (was 34.5); all-but-one tests
55 <= 60. (b) lever share 75%, held-out w5 70%. (c) blind 24bff4e: 100% kept (see Design blind) -> NO CORE. (d) verifier worst 420 s
= 16% of 2700 s. (e) every fast generic solver loses >= 15% lever points by WRONG, shipped fast,
reference <= 1/4 of limit (34-43x faster than best plain exact).
RISKS: (1) a careful agent that splits by base, merges the pool exactly AND reads R2 tie, R2 moved and
R3 right is the reference: it wins; only R2/R3 readings stand between it and full marks. (2) correct-
readings plain exact loses 100% by TIMEOUT (G-6 30% cap if read per solver). (3) a (33.6) is 1.4 under
the bar. Design blind folder: _work/hangar-check-replan/design_blind/ (instruction + environment/data + docs). Files: DESIGN.md, KILL_TEST.md, BRANCH_FIRE.md, QC_DEFENCE.md, PREMORTEM.md, proto/.

## Design blind (24bff4e, claude-opus-5, scored 00:00)
| corpus | blind terms = ref | families EXACT | lever pts kept | sec (limit 60) |
|---|---|---|---|---|
| shipped s1 | 130/9670/5 yes | 5/5 | 20/20 | 0.15 |
| h1 1:1 (South + public empty) | 660/11600/2 yes | 8/8 | 20/20 | 0.61 |
| h2 3:1 (empty base + public) | 660/9460/3 yes | 8/8 | 20/20 | 0.65 |
| h3 1:0 / h4 3:0 / h5 5:0 | 128/13475/10, 126/13060/11, 124/9635/6 yes | 5/5 each | 60/60 | 0.65-0.81 |
Hidden lever points kept 100/100 = 100%; loss split WRONG 0 / TIMEOUT 0 / CRASH 0. data_quality also EXACT.
Why it won: it wrote the reference in 6 min. plan_base = memo over (remaining mask, line free day),
starts {earliest feasible, published start if later and legal} (the dominance set), Pareto per exact
shift count with pruning; choose_plan = exact merge over the shared pool, then global request_id
start/finish vectors. Every reading right: pool hard cap (R1), moved = start != published or deferred
(R2), tie vector (S3), no_slot judged on an empty line (R3), fixed base/segment universe. It ran 5-7x
faster than my reference. The levers are rules a careful reader applies, and the core method (split by
base + exact merge) is the obvious method for a strong model at n=8/base. VERDICT: NO CORE (G-8).
