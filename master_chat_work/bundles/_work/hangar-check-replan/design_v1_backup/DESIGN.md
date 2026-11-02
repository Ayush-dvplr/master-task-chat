# DESIGN af5dddf hangar-check-replan (Shape D, P-3 primary, S3, N2, P-5)

## 1. Model (the contract the docs will state, in plain words)
- Season: days 1..S, given as ISO dates (season_start, season_end in fleet_limits.toml). Shipped S = 120,
  hidden S in 120..160.
- Bases North, South, West, East. Each base has ONE heavy-check line: at most one check in work on a
  day. A check occupies consecutive calendar days start..finish.
- Base calendar (base_calendar.jsonl, one row per base per date, many seasons): `status` is OPEN,
  NO_START (work may continue, a check may not start that day) or CLOSED (no work; no check span may
  include it). The disruption notice adds CLOSED days for the season (base, from, to); the notice wins
  over the calendar.
- Check request (check_requests.csv, many seasons): request_id, tail, check_type (A, C, D), base,
  available_from (earliest start), due_date, duration_days, status. Planning set = rows whose season
  is the planned season and status OPEN, after rejects. The notice can replace available_from for a
  tail (AVAILABLE_FROM table). Each tail has at most one open check in the planning set.
- Class from fleet_register.csv via tail: widebody, narrowbody, regional. Segment commercial =
  widebody + narrowbody; public = regional.
- class_rates.yaml per class: revenue_per_day, overdue_weight, deferral_penalty.
- check_types.json per type: max_compress_days c, overtime_shifts_per_day h.
- Compression x in 0..min(c, p-1); finish = start + p - x - 1; overtime used = h * x.
- fleet_limits.toml: overtime_pool_shifts K (one pool for the whole fleet), shift_cost.
- Published plan (published_plan.csv): published start ps per request_id (pre-disruption plan).
- A check is either scheduled (start >= available_from, start day not NO_START, no CLOSED day in
  span, finish <= S, no overlap with another check on the same line) or deferred.
- Objective, compared in this order, smaller is better:
  T1 = sum over scheduled of overdue_weight * max(0, finish - due) + sum over deferred of deferral_penalty;
  T2 = sum over scheduled of revenue_per_day * (p - x) + shift_cost * (total overtime shifts);
  T3 = number of moved requests (scheduled with start != ps, plus every deferred request);
  T4 = the fleet vector: start day of every request in request_id order (deferred = S + 1), followed
       by the finish day of every request in the same order (deferred = S + 1); lexicographically smallest.
  Subject to: total overtime over the fleet <= K.
- Deferral reason: `no_slot` when the check has no feasible start finishing by S on an empty line at
  any compression; otherwise `plan_trade`.
- The plan is unique: T4 is a total order on distinct plans (start and finish fix x).

## 2. Why the reference is exact and fast (internal only; never stated)
- Dominance: in an optimal plan each scheduled check starts either at its published start or at the
  earliest feasible start after the line frees (for its chosen x). Proof: moving any other start to
  the earliest feasible start keeps T1 no worse, T2 equal, T3 no worse, and lowers T4; later checks
  stay feasible because the line frees earlier.
- Per base backward memo over (remaining set, line free day) returning, for every exact overtime
  amount o, the best (T1, T2, T3, base-restricted vector). Optimal substructure holds because T is
  additive and the vector comparison of two completions with the same fixed part differs only in the
  completion positions.
- Fleet merge: DP over the four bases over exact overtime, total <= K, comparing (T1, T2, T3) then the
  fleet vector. Per-base restriction is consistent with the fleet vector because the vector is
  two blocks (starts, then finishes): the first difference between two fleet plans that differ at one
  base is that base's first difference.
- Hidden scale: 8 checks per base (32 per corpus); shipped 5 per base (20). Measured in Docker
  (KILL_TEST.md): reference 3.2-3.5 s at hidden scale; plain exact over every start day 119-142 s (one
  seed over 300 s); whole-fleet joint search over 180 s already at 7 per base.

## 3. Shape D: shipped degenerate, hidden firing
| branch | shipped | hidden (every corpus) |
|---|---|---|
| pool binds (unconstrained optimum uses > K) | no (uses < K) | yes, with a base whose frontier gains nothing at 1 unit and much at 2 |
| available_from < ps, optimum waits to ps | no (available_from = ps after notice) | yes |
| plan_trade deferral | no | yes |
| deciding T4 tie across bases (equal T1-T3) | no | yes, smaller request id at a later base |
| no_slot deferral | 1 row (stated, ordinary) | yes |

## 4. Sharp rules (Shape D, 3 levers) and the supporting S3 rule
| id | rule text (governing file) | reflex reading (PREMORTEM) | hidden cases (every corpus) | why shipped cannot confirm | interaction |
|---|---|---|---|---|---|
| R1 | "The fleet has one overtime pool for the season: the overtime shifts of all compressed checks at all four bases together may not exceed `overtime_pool_shifts`." (docs/overtime_policy.md; value in fleet_limits.toml) + compression sentence (check_types.json fields named in docs/overtime_policy.md) | split by base: solve each base exactly and share the pool first come (base order), pro rata, or by greedy marginal gain | pool binds; one base whose best gain needs 2+ compressions at once (non-convex frontier), so greedy marginal and FCFS pick a worse split | shipped optimum uses fewer shifts than the pool, so every split program is exact on shipped | the pool split changes compressed days, finishes, overdue days, T2 and the moved count at two or more bases |
| R2 | "Plans are compared on four terms in order ... third, the number of moved requests: a scheduled request whose start differs from its published start, and every deferred request" (docs/planning_policy.md) | left-shift: every check starts as early as the line and calendar allow (classic dominance), so a check whose available_from is earlier than its published start is pulled forward and counted moved | available_from < published start for several checks; the optimum keeps the published start when the earlier start buys nothing in T1/T2 | shipped: available_from = published start for every open request after the notice, so earliest start = published start | a moved check shifts the line free day and can change which later check fits before a closure |
| R3 | "A request may be deferred to next season. A deferred request adds its class `deferral_penalty` to the first term ... reason `no_slot` when it cannot finish by season end on an empty line at any compression, otherwise `plan_trade`." (docs/deferral_policy.md; penalties in class_rates.yaml) | defer only what cannot be fitted (fit-first, H8) | a late regional heavy check whose only fit runs long overdue past a closure: deferring (penalty 30) beats any late run (weight 2 x overdue days); optimum defers with `plan_trade` | shipped has one `no_slot` deferral only; every fit-if-possible plan is optimal on shipped | the freed line days let another check finish earlier; deferred counts as moved in T3 |
| S3 | "When two plans tie on all three terms, the plan whose list of start days in request_id order (deferred = day after season end), followed by finish days in the same order, is smaller at the first difference wins." (docs/planning_policy.md) | first plan found / base order / smallest overtime | planted twins at two bases with equal class/type/slack where the pool allows only one compression | shipped has no tie on the three terms | supporting; graded only through whole documents |

All four sentences sit in the docs file that governs the data they touch (W2); the rule register docs/README.md names every governing file (W10).

## 5. Spine, input files, chains
Spine: load + reject (data_quality) -> planning set (season, status, notice overrides) -> per-request
attributes (class via tail, type limits, rates) -> calendars (base calendar + notice closures) -> exact
fleet plan under the pool -> per-request audit rows -> base, segment, fleet roll-ups.

| file | format | rows | role |
|---|---|---|---|
| environment/data/fleet_register.csv | csv | ~3000 tails | tail -> class, operator, status (retired tails reject requests) |
| environment/data/check_requests.csv | csv | ~5000 (many seasons) | requests; malformed rows rejected |
| environment/data/published_plan.csv | csv | ~5000 | published start per request_id |
| environment/data/base_calendar.jsonl | jsonl | 4 bases x ~1830 days | OPEN / NO_START / CLOSED per date |
| environment/data/disruption_notice.md | md | 1 notice, 2 tables | extra CLOSED ranges; AVAILABLE_FROM replacements per tail |
| environment/data/class_rates.yaml | yaml | 3 classes | revenue_per_day, overdue_weight, deferral_penalty |
| environment/data/check_types.json | json | 3 types | max_compress_days, overtime_shifts_per_day |
| environment/data/fleet_limits.toml | toml | 1 | season_start, season_end, overtime_pool_shifts, shift_cost |
| environment/data/old_rates_2025.yaml | yaml | 3 classes | partial-authority sheet: header demotes it, its `shift_cost` note stays live? (NO: dropped, see note) |
| docs/README.md, docs/planning_policy.md, docs/overtime_policy.md, docs/deferral_policy.md, docs/data_conventions.md, docs/output_schema.md | md | | rule register and governing files |

Note: no S5 decoy is planned (the source set already has P-3, S3, N2, P-5); the old_rates row is dropped.
Chains (length >= 4):
1. check_requests.tail -> fleet_register.class -> class_rates.overdue_weight -> T1 -> plan -> region file.
2. check_requests.base -> base_calendar status -> disruption_notice CLOSED -> feasible starts -> plan -> audit.
3. check_requests.check_type -> check_types.max_compress_days/overtime_shifts_per_day -> fleet_limits pool -> plan -> every file (fleet_overtime_used).
4. disruption_notice AVAILABLE_FROM -> check_requests.available_from -> published_plan start -> moved flag -> T3 -> summary.
Volume: csv/jsonl files >= 2000 lines each, total >= 20000 lines (A5); volume is noise, not difficulty.

## 6. Rejection paths (data_quality.json, error strings stated in docs/data_conventions.md)
- `unknown_tail` (tail absent from fleet_register), `retired_tail` (register status RETIRED),
  `bad_date` (unparseable available_from or due_date), `bad_duration` (duration not a positive whole number),
  `unknown_base`, `unknown_check_type`, `duplicate_request` (second and later rows of a request_id; first kept),
  `no_published_start` (no row in published_plan.csv). Each reject row: request_id, line number, reason.
- The program exits non-zero naming the file when a declared input file is missing or not parseable.

## 7. Test plan (G1-G13)
Invocation stated in instruction.md (G8a): `python3 /app/out/derive_report.py --data <dir> --out <dir>`
(defaults /app/environment/data and /app/out). Exactness + rerun promise stated: "each output document is
graded whole, and only an exact match counts; the program is run again on fresh inputs in the same layout".
Hidden corpora: embedded seeded generator in tests/ (seeds only there), renders the same file layout with
new values; 4 corpora, each picked by rejection offline so every hard branch fires (pool binds with a
non-convex base, available_from < published start that the optimum keeps, a `plan_trade` deferral, a
deciding tie); the rare-branch gadgets draw from their own RNG stream (G8). Program run as uid 1000 from
a foreign cwd, inputs made readable (_grant_read).

| tier | tests | weight each | total |
|---|---|---|---|
| program present and runs on shipped data (exit 0, writes the 9 json files) | 1 | 1 | 1 |
| shipped rerun, whole doc: audit, regions (4 files, one view), segments (2 files), summary, data_quality | 5 | 3 | 15 |
| hidden corpus h1..h4, whole doc: audit, regions, segments, summary | 16 | 5 | 80 |
| hidden corpus h1..h4, whole doc: data_quality | 4 | 3 | 12 |
| mutation: rows shuffled + rerun (h1), relocated data dir + foreign cwd (h2), each counted only when the plain run of that corpus is exact for audit | 2 | 3 | 6 |
| total | 28 | | 114 |
Held-out w5 tier 80/114 = 70% (N2 >= 50%). Hidden share (80+12+6)/114 = 86% (Shape D >= 70%).
Lever share (checks a lever slip flips: hidden audit, regions, segments, summary + mutations) 86/114 = 75%.
G1a OWNED: audit rows owned by audit test; region rows by regions test; segment rows by segments test;
fleet totals and `fleet_overtime_used` by summary; the copy of `fleet_overtime_used` in region and segment
files is masked outside summary, so one slip in the shared figure is charged once while the plan rows it
moves are charged in each family they sit in. A test that compared nothing fails. Messages give the first
differing path (G7). No test returns early on another test's scalar; every test runs its own program call
on its own temp copy (no shared mutable cache, G12; the program call per corpus is cached read-only by
corpus id inside one process, outputs copied before compare).
Verifier time: 6 program runs (shipped, h1-h4, 2 mutations reuse h1/h2 shapes = 7 runs) x reference ~3.5 s
worst = 25 s, plus generation; stated per-run limit 60 s, verifier timeout 2700 s; worst case of a slow
agent program 7 x 60 = 420 s (16% of 2700; under 90% of the stated limit per run by construction of the
alarm). Reference 3.5 s at hidden scale = 6% of the 60 s limit (<= 1/4).
Negatives (cheating acts only, AL-28): none in tests; judge holds grader-read -5, J3a -3, J3b -5, J3c -3.

## 8. Judge plan (J1-J10)
Probe band: 10 probes x w3 = 30, non-probe positives 4 x w3 = 12 -> probe share 30/42 = 71%; trim to
9 probes (27/39 = 69%) if the non-probe set stays at 4. Each probe is performed by a solve.sh self-check
stage that prints `check <id> ok` and one witness line.
| id | template | act (trajectory) | requirement it serves |
|---|---|---|---|
| P1 | P-a | runs the program on an input it built where the pool is smaller than what the plan wants | overtime pool sentence |
| P2 | P-b | prints one instance where the best fleet plan differs from the plan built base by base with the pool shared out | single fleet plan sentence |
| P3 | P-c (json) | recomputes the four plan terms of the delivered audit outside the program | four-term order sentence |
| P4 | P-c (roll-up) | recomputes a region total from the audit rows outside the program | region file schema |
| P5 | P-d | reruns on an altered copy (one available_from changed) and shows the output moved | rerun promise |
| P6 | P-e | reruns from another working directory with --data/--out elsewhere | stated invocation |
| P7 | P-g | shows the delivered plan is the only one at its three-term value under the start-day order (enumeration on a small input) | tie-break sentence |
| P8 | P-h | runs with a missing declared input and shows the non-zero exit naming the file | missing-input sentence |
| P9 | P-a | runs on an input with a request that can only finish long past due after a closure | deferral sentence |
Non-probe: J4 code quality (w3, "agent", conduct), J6 enumeration on final answer (lists every deferred
request by request_id with its reason, w3), J10 instruction following (program written before any out/
json exists; out/ files produced by running it, quoting the sentence, w3), one task-completion process
criterion (runs the stated command after its last edit, w3).
Negatives: grader-read -5 (anchored wording), J3a -3, J3b -5 (final_answer), J3c -3.
Judge estimate (section 6 formula: probes at 25%, outcome criteria as Opus is expected to mark them):
probes 27 x 0.25 = 6.75; J6 3, J10 3, completion 3, J4 0 to 3 -> mid 15.75/39 = 40% (lower 6.75-3/39 = 9%,
upper 39/39 less one probe class). Evidence: mean rubric of our 10 valid gate runs 23.5 (LEVER_RULES 1C v3.7).
The bar below uses the formula mid 40, the worse of the two.

## 9. Kill summary, expected loss, G-7 numbers
Kill table (KILL_TEST.md; hidden n=7 seeds 2 4 5 7 8 9 10 12, timing at n=8 seeds 2 4 7; stated limit 60 s):
| solver | shipped | hidden | lever points kept | loss kind |
|---|---|---|---|---|
| greedy EDD / greedy + swap | WRONG | WRONG 8/8 | 0% | WRONG |
| disrupted repair (keep published, repair) | WRONG | WRONG 8/8 | 0% | WRONG |
| split pool fcfs / prorata | EXACT | WRONG 8/8, T differs | 0% | WRONG (R1, S3) |
| split pool marginal | EXACT | WRONG 8/8 | 6% | WRONG (R1, S3) |
| exact, first-found tie | EXACT | WRONG 6/8, T equal | 44% | WRONG (R2 tie) |
| exact, revenue tie | EXACT | WRONG 8/8, T equal | 25% | WRONG (R2 tie) |
| exact, earliest start only | EXACT | WRONG 8/8, third term | 0% | WRONG (R2 moved) |
| exact, defer only when no slot | EXACT (seed 1) | WRONG 8/8 | 0% | WRONG (R3) |
| plain exact over every start day, all readings right | EXACT 6-7 s | EXACT 119-142 s | 0% under 60 s | TIMEOUT (v3.5) |
| joint whole-fleet exact | not run at n=5 | over 180 s at n=7 | 0% | TIMEOUT (v3.5) |
Timeout share of lost lever points over the table: 100 / 925 = 10.8%.

Expected loss per lever (fraction of lever points a slip costs, from the kill rows):
R1 pool split 94-100%; R2 tie reflex 56-75%; R2 earliest-start reflex 100%; R3 no_slot-only 100%;
S3 base-by-base report 100% (same rows as R1 split).

G-7:
(a) first-write tests: program 1 + shipped 15 + hidden dq 9 of 12 + hidden families about 8 of 80 (one
reflex slip expected) + mutations 0 = 33/114 = 29%; judge mid 40 -> predicted final (29 + 40)/2 = 34.5 <= 35.
All-but-one: worst case keeps first_tie seeds -> 1 + 15 + 12 + 35 + 2 = 65/114 = 57% <= 60.
(b) lever share 86/114 = 75% >= 40; held-out w5 80/114 = 70% >= 50.
(c) no blind over 65: pending design blind (Phase 0b).
(d) verifier worst 420 s = 16% of 2700; per-run alarm 60 s.
(e) every fast generic solver loses >= 15% lever points by WRONG and is EXACT on shipped (greedy and
disrupted repair are WRONG on shipped too); the correct-readings plain exact loses by TIMEOUT only at
hidden scale and is fast on shipped; reference 3.5 s <= 15 s (1/4 of 60 s), 34-43x faster than it.
RISK: per solver, the correct-readings plain exact loses 100% by TIMEOUT (G-6 30% cap read per solver).

## 10. Phase 0b additions (master go m0127): fixed declared universe, planted no_slot, per-field grading
Universe sentence (docs/output_schema.md, where outputs are described; one sentence): "Every base listed in
`data_conventions.md` and both segments always get their report file and their row in `plan_summary.json`,
with zero counts and `null` for `first_start` and `last_finish` when they have no open request this season."
Hidden corpora h1, h2 (empty_axes=1, own RNG stream `Random(seed*7919+17)`): one base with no eligible
request (its season rows are all rejected (retired_tail, bad_date, bad_duration) or CANCELLED) and the
public segment empty (only widebody and narrowbody tails planned). h3, h4: every base and segment live.
Shipped: every base and both segments live (5/6/5/5 requests; commercial 15, public 6).
no_slot planted in every hidden corpus: a D check at a live base other than the tight one, season-end
closure 15-25 days in the calendar, available day 3..(p-4) days before the closure, so p - c days never fit.
Shipped keeps its one plain no_slot (available day too late for p - c before season end, no closure).
Per-field grading (CL-4 proportional, no whole-corpus cliff): each hidden family test scores fields, and
on h1, h2 the missing-axis documents get their own checks inside the family weights:
| corpus | regions | segments | summary | audit |
|---|---|---|---|---|
| h1, h2 | regions_live w4 + region_empty w1 | segments_live w4 + segment_empty w1 | summary w4 + summary_empty_rows w1 | w5 |
| h3, h4 | w5 | w5 | w5 | w5 |
Totals unchanged: 28 tests become 34 tests, 114 points (hidden families still 80).
Kill row added: reference that derives bases and segments from the records seen -> EXACT on shipped and
h3, h4; WRONG on region_empty, segment_empty, summary_empty_rows of h1, h2 = 6 of 86 lever points lost (7%).
Prototype check (Docker, rt and bf3 logs under _runs/20261031/hangar-check-replan/): solve_proto.py on the
rendered files equals ref.solve on the abstract instance (plan terms) for shipped 1, h 1:1, 3:1, 1:0.
New G-7 (a): first-write keeps hidden families about 6 of 80 (the summary rows it kept on h1, h2 now miss the
empty rows) -> 1 + 15 + 9 + 6 + 0 = 31/114 = 27%; final (27 + 40)/2 = 33.6. All-but-one 63/114 = 55%.
