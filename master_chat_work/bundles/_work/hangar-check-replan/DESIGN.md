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

## 11. Redesign 1 (G-8, master m0183): Office package current-text lever

Why: design blind 24bff4e matched the reference on every corpus (NO CORE). The world, the 4-term order, the pool, the outputs and the fixed base/segment universe stay. New hardness: the governing numbers that drive the optimisation now live in two WordprocessingML packages, and only their current text counts.

### 11.1 Files that change
| old | new | content |
|---|---|---|
| disruption_notice.md | disruption_notice.docx | heading paragraphs; table `base, from, days` (closures, inclusive run of `days` days from `from`); table `tail, available_from` |
| class_rates.yaml + pool lines of fleet_limits.toml | planning_limits.docx | table `item, value` (overtime_pool_shifts, shift_cost); table `class, revenue_per_day, overdue_weight, deferral_penalty` |
| fleet_limits.toml | fleet_limits.toml | season, season_start, season_end only |

### 11.2 Profile sentence (docs/data_conventions.md, stated once, no trap list)
"`disruption_notice.docx` and `planning_limits.docx` are WordprocessingML packages as ECMA-376 Parts 1 and 2 define them. The package relationship of type officeDocument names the main document part. Only the current text of the main document part counts: text inside `w:del` or `w:moveFrom` is not current text, text inside `w:ins` or `w:moveTo` is. Where `mc:AlternateContent` gives alternatives, the first `mc:Choice` whose `Requires` prefixes the reader understands applies, otherwise `mc:Fallback`; a reader of these files understands the WordprocessingML main namespace (`w`) and no other. A table cell's value is its current text with surrounding spaces removed. Each table is found by the text of its first header cell."

### 11.3 Trap families (hidden only; shipped packages are plain, main part at the default name)
| family | construction | wrong reading it punishes |
|---|---|---|
| F1 relmain | `_rels/.rels` officeDocument target `word/main_document.xml` (+ content-type override); a stale `word/document.xml` with older numbers (pool 2K+7, rates +10, tight-base closure missing) | opening `word/document.xml` by default name |
| F2 altcontent | `mc:AlternateContent` in the cell paragraph: covering the leading digits of a value of 10 or more, then the last digit as a plain run: Choice Requires="wps" stale (lead//3), Choice Requires="w" current (lead), Fallback stale (lead//2) | joining every alternative (longer number), always Fallback or first Choice regardless of Requires (smaller number), dropping the element (last digit only); every slip parses, so it loses by WRONG |
| F3 tracked move | last digit moved: `w:moveFrom` digit at front, rest, `w:moveTo` digit at end (range markers present) | joining all `w:t` (3 digits), reading moveFrom and skipping moveTo (rotated value) |
| F4 delete/insert | prefix + `w:del/w:delText` old digit + `w:ins` new digit | itertext over every text node (3 digits) |

Targets (amplification): enlarging slips (F3, F4) go first on the pool limit (binds on every hidden corpus) then on ordinary closures (11-19 days, in the notice, with checks after them); shrinking alternatives (F2) go first on the pool limit then on the tight-base closure (shorter closure turns the `plan_trade` deferral into a wait). Pool limit and tight closure always end in a nonzero digit. Each cell carries at most one trap.

### 11.4 Corpus layout (each family on 5 of 6 hidden corpora, overlapping)
h1 = seed 1 empty-axes F1+F2+F3+F4; h2 = seed 3 empty-axes F1+F2+F3+F4; h3 = seed 1 F1+F2+F3; h4 = seed 3 F2+F3+F4; h5 = seed 5 F1+F3+F4; h6 = seed 6 F1+F2+F4. Shipped = seed 2 n=5 (seed 1 gained a plan_trade deferral once ordinary closures became 11-19 days), plain packages.
History: 3 of 6 per family (r1d) left every single slip at 30-37% kept, which predicts first-write tests near 46%; 5 of 6 (r1e) is the chosen density. All hidden corpora keep the no_slot fixture, the tight base, the twin check, r<ps rows and the binding pool.
Final generator rules (r1g): family order shuffled per corpus on the trap RNG stream (seed*104729+3); each in-text family (F2, F3, F4) takes one cell and a second when a target is left; every in-season closure of a hidden corpus is carried in the notice (none in the calendar), so each corpus has 3-4 closure cells besides the pool and shift_cost.

### 11.5 Kill result r1g, test plan, G-7 numbers
Kill (KILL_TEST.md, redesign 1 section): every single reader slip keeps 18-22% of hidden lever points, all WRONG with exit 0; python-docx-like direct-runs reader and the naive stdlib reader (default name + regex over every `w:t`) keep 2%; design blind 24bff4e CRASHES on every corpus (0%); reference 0.37 s shipped, 3.8-5.7 s hidden (<= 10% of 60 s).
Test plan r1: program runs w1; shipped check_plan, rollups, summary 3 x w3 = 9; hidden h1..h6 x {audit, regions, segments, summary} w5 = 120 (h1, h2: regions w4 + region_empty w1, segments w4 + segment_empty w1, summary w4 + summary_empty_rows w1); data_quality on h1, h4 w2 = 4; two mutation corpora (shipped with one notice cell edited in place, read back) w2 = 4. Total 138; hidden lever 120 = 87%.
G-7: (a) first-write = naive stdlib reader: 1 + 9 + 4 + 4 + 2% of 120 (2.4) = 20.4/138 = 15% tests; judge mid 40 -> final 27.5 <= 35. One reader slip with everything else right: 1 + 9 + 4 + 4 + 22% of 120 (26.4) = 44.4/138 = 32% tests -> final 36 (one slip only; a first write rarely gets the optimisation readings R1-R3 right as well). All-but-one tests <= 32% <= 60. (b) lever share 87%, held-out w5 87%. (c) design blind: pending fresh blind (24bff4e on the new files: CRASH, 0%). (d) verifier worst 7 runs x 60 s = 420 s = 16% of 2700 s. (e) every generic solver and every reader slip loses >= 78% of lever points by WRONG; shipped fast for all; reference <= 1/10 of the stated limit.

## 12. Redesign 2 (G-8 2 of 2, master m0300): stated settlement rule with propagation (L01)
Backup of r1 files: WORK/design_r1_backup/. World, planner, 4-term order, outputs and fixed base/segment list kept.
Word packages kept as the file format (no extra work for the lever) but plain on every corpus: no traps (r1 lever retired; a docx slip must not mix into the settlement measurement).

### 12.1 Rule (settlement_policy.md, stated once)
- planning_limits.docx gains table `base | allowance_shifts`: the overtime shifts granted to each base from the season budget. "The four grants together form one fleet overtime allowance."
- "After the season plan is fixed, the fleet allowance pays for overtime one scheduled check at a time in this order: aircraft class widebody, then narrowbody, then regional; within a class the earlier start day first; on the same start day the smaller request_id first. Each check takes the smaller of its overtime shifts and the allowance still left, whichever base it is at."
- Per check: allowance_shifts (taken), paid_shifts = overtime_shifts - allowance_shifts; overtime_cost = shift_cost x overtime_shifts; allowance_credit = shift_cost x allowance_shifts; settled_overtime_cost = overtime_cost - allowance_credit.
- Per base, per segment, fleet: sums of the per-check figures; base files also show allowance_granted (its row) and the fleet total; summary shows fleet allowance_granted, allowance_used, allowance_left = granted - used.
- "The settlement is a report on the fixed plan: it never changes which plan is optimal." (second term keeps shift_cost x overtime_shifts.)

### 12.2 Corpus layout (settlement type, own RNG stream)
Allowance A = sum of grants, set from the reference plan's overtime U. Shipped: A = U + 6..12, every base grant >= its own use (cap never reached; per-base cap, order, ties all inert). Hidden: grants split so at least one base uses more than its grant; types h1 slack (A = U + 5..12), h2 at cap (A = U), h3 one shift short (A = U - 1), h4..h6 binding (A = 40-70% of U) with an equal-priority pair (same class, same start day, different bases) straddling the point where the allowance runs out.

### 12.3 Slips (kill rows)
granted_not_used (base/segment/fleet credit from grants, not use), cap_not_subtracted (settled = gross), per_base_cap (each base pays only from its own grant), unordered (request_id order), plus reference slips: tie_by_base (equal priority broken by base order), start_first (start day before class), whole_only (a check that does not fit whole takes nothing).

### 12.4 Kill result and test plan r2 (01 Nov 01:40)

Kill table: KILL_TEST.md "Redesign 2". Row (a) passes: granted_not_used keeps 50%, cap_not_subtracted 5%, per_base_cap 5%, unordered 27% of hidden settlement points, all WRONG. Literal reader of the stated rule is EXACT (row b). Both earlier blinds keep 0% of settlement points (row c). Tie-key slips keep 58-62% (row d).

Test plan r2 (31 tests, 117 points): program runs w1; shipped plan fields w3 and shipped settlement fields w3; hidden plan fields (audit, rollups, summary without settlement keys) one check per corpus w2 = 12; hidden settlement per corpus 3 checks w5 (per-check settlement fields; region and segment settlement fields with the empty-axis rows on h1, h2; summary settlement object and base rows) = 90; data_quality h1, h4 w2 = 4; two mutation corpora w2 = 4. Hidden settlement share 90/117 = 77%; all held-out lever checks w5.

G-7 numbers (planner right, as both blinds had it; judge mid 40):
| first write | tests | final |
|---|---|---|
| granted_not_used | (24 + 0 + 45)/117 = 59% | 49.5 |
| cap_not_subtracted | (24 + 0 + 4.5)/117 = 24% | 32 |
| per_base_cap | (24 + 3 + 4.5)/117 = 27% | 33.5 |
| unordered | (24 + 3 + 24)/117 = 44% | 42 |
| mean of the four row (a) slips | 39% | 39.5 |
| literal reader | 100% | 70 |
(a) predicted final <= 35 only for the cap slips; mean 39.5 misses the bar. (b) lever share 77%. (c) pending fresh blind. (d) 7 runs x 60 s = 420 s of 2700 (16%). (e) slips lose by WRONG, reference 6.2 s worst = 10% of 60 s, shipped 0.37 s.

## 13. Build notes (route 1, 1 Nov 11:40)

### 13.1 Design blind e8e9c82: readings fitted to the sample (route-1 R3 item 2)
Program kept at `WORK/kill/e8e9c82_program.py` (1302 lines, exact on shipped + h1..h10 in score-e8e9c82).
Spots read line by line:
- L27-34 bases, segments, class->segment map, class order hard-coded: all stated in docs (data_conventions Bases, output_schema segments, overtime_policy order). Not a fit.
- L563-568: rows that are not read (other season, or not OPEN) are added to `seen` before the duplicate test, so a read row whose `request_id` already sits on an ignored row is rejected as `duplicate_request`. data_conventions.md states "already appeared on an earlier read row" and "Every other row is ignored". The shipped data never reuses an id across read and ignored rows, so the sample cannot show the slip. -> **Hidden fixture X1 (reused id)**: on hidden corpora h3 and h5 (own RNG stream `Random(seed*7349+11)`), one planned OPEN row reuses the `request_id` of an earlier CANCELLED row of the same season (or of an older season); it is a normal request and is planned. Wrong reading drops it -> plan, settlement, rollups and data_quality move. No new rule sentence.
- L588 `status != "ACTIVE"` for retired_tail: the register states only ACTIVE/RETIRED; same result. Not a fit.
- L603-605 notice availability replaces the csv value whether earlier or later, clipped to day 1: stated; hidden already has notice-earlier rows. Not a fit.
- L1015 moved = start != published day: stated; hidden has r < published. Not a fit.
- L1050 negative grants clamped to 0: value never negative (bounds asserted). Not graded.
The generator also guarantees no accidental id reuse anywhere else (ids drawn without replacement), so X1 is the only reuse.

### 13.2 Where a careful solver loses points (Phase 8 step 4; measured, WORK/COST_TABLE.md)
| rule | hidden input that fires it | checks that move | careful slip measured |
|---|---|---|---|
| S1 payment order (class, due_date, request_id) | h3, h4, h6 equal-due pair across bases at the run-out point; h2-h6 binding allowance | hN settlement x3 | start-day key 79/129; request_id order 51/129 |
| S2 used not granted; settled = cost - credit | every corpus (shipped slack too) | shipped_settlement, hN group + summary | granted 58/129; cap not subtracted 30/129 |
| S2 one fleet allowance | h1-h6 (some base uses more than its grant) | hN settlement x3, changed_allowance_grants | per-base cap 36/129 |
| U fixed base/segment list | h1 (South empty), h2 (North empty), public segment empty | h1/h2 plan, settlement, empty-axis, h1_data_quality | from records 88/129 |
| X1 duplicate counts earlier read rows only | h3, h5 (reused id of an ignored CANCELLED row) | h3 x4, h5 plan + per check | e8e9c82 reading 103/129 |
| R2 tie vector, R3 deferral, R1 pool | all hidden corpora | plan + settlement | 75, 36, 4 of 129 |
Expected for a careful literal reader (both blinds were): 103-129/129; predicted final 61.9-72 (COST_TABLE). Recorded per route 1; the paid run decides the harden.

### 13.3 Judge probes: expected Opus show
R2 recompute terms, R3 base total, R6 relocated rerun, R8 missing file: likely shown (Opus self-checks of this kind seen in both blind reports). R1 smaller pool, R4 allowance replay, R5 changed grants, R7 counted plans on a small input, R9 empty base: unlikely unless prompted (blind reports showed identity checks on shipped only). Judge mid 44% (JUDGE_MAP.md).
