# DESIGN 361674d metered-usage-rating-pipeline, gate v3.6 harden (Phase 1)

Gate: tests < 85 AND rubric < 85 AND final < 50. Target (master note 6): first-write tests <= 75,
run tests 65-75, rubric 15-20, final <= 45. Setup: QC kit HEAD 5574d77e; GEN and QC fingerprints
0 diffs; session renamed (opencode list showed it).

## 1. TRIP summary (OUT/TRIP.md, probe 3, 25 Oct, tests 247/247, rubric 22/34 = 64.71, final 82.35)
- Phase A: staged tests/ and environment/ differ from BUNDLE in judge.toml, reward.toml,
  test_output.py, accounts.csv, commitments.xml, rating_contract.md (r3 and wave-2 edits; expected).
- Program written once (steps 13-15), last graded-logic edit step 23. Tier picked by a forward scan
  over the tier list per line (`pick_tier`, break on first larger `from`); billing group by memo walk.
- Self-checks: second implementation `/tmp/verify.py` on /app/data and on a built month of 7,889
  accepted lines (smaller than /app/data's 15,154); altered copy (commitments, parents, CMP rate);
  tiny hand fixture; foreign cwd. Never timed a run, never built a long tier list or a deep chain,
  never summed charge over normalized.jsonl against summary.json.
- Judge losses: J4 (main 364-630), summary sum skipped, J3a fired (-3, error-path claim with no output
  after last edit), aggregate-count negative fired (-3).
- Wave-2 status: 2 of 3 fresh blinds scored 100 (memo walk, 2.2-2.9 s on the long months).

## 2. Arithmetic
- Now (bundle 09963d3): 76 checks, positive 295, of which long reseller months (LV-MU-8) 48 = 16.3%.
  A memo-walk program (blinds c60b, 9d66) scores 100; probe-3 program 247/295 = 83.7.
- Constraint: all-but-one <= 75 needs each lever alone to cost >= 25%, yet both together <= 40%.
  Separate lever corpora cannot do both (missing LV-MU-8 alone keeps (247+X)/(295+X) > 83%).
  So the new corpora are long reseller months that ALSO carry a long tier ladder: a program must
  get both the group walk and the tier pick fast to keep them.
- New points X: missing ladder only = 295/(295+X) <= 75% needs X >= 98.3; share (48+X)/(295+X)
  <= 40% needs X <= 116.7. Chosen X = 4 corpora x 28 = 112: positive 407, lever share 160/407 = 39.3%.
- Judge: positive 28 -> 37 (three new probes, w3 each); run-3 earned 10 of 37 positive, J3a fires:
  7/37 = 18.9% (27.0% if J3a does not fire).

## 3. Lever LV-MU-9 (P-3 dimension: hidden-scale tier ladder, stated 15 s limit)
- Objective as the docs already state it: rate_card.json L110-113 (`tiers`, a list of objects with
  `tier`, `from`, `rates`; first tier starts at 0); Rating L153-156 (tier = the tier with the largest
  `from` less than or equal to the tier counter); Program L48-49 "Every run of the program finishes
  within 15 seconds." No new sentence, no size bound, no method word. Shipped rate card keeps 3 tiers.
- Hidden instances: 4 long fresh months from `gen_month(..., resellers=R, ladder=50000)`: reseller tree
  as LONG_SHAPES (13000-15000 rows per collector, 76000-84000 accounts, 11000-12000 sub-resellers),
  rate card with 50,000 tiers per product (25.9 MB), starts at the month's own tier-counter quantiles
  (strictly increasing, first 0, consecutive tier numbers), rates from the existing `_gen_rate`;
  own RNG `Random(seed*6271+53)`; seeds HIDDEN_SEED*37+k. 61-71k accepted lines.
- Reference: bisect over sorted `from` (solution/solve.py tier_for already bisects; WORK ref_core
  switched from a scan to bisect, equal output on shipped/hidden/scaled/small/near corpora).
- Loss: a per-line scan of the tier list (forward with or without break, reverse, max over starts)
  does 0.5-1.9 billion steps and passes 15 s; a memo walk without the ladder fix still times out.
  Shipped data and every visible example stay fast (3 tiers), so v3.5 (1)-(3) hold: no shipped warning,
  stated limit, cost inside the lever checks (each corpus its own program call).
- Generator: old hidden and long corpora byte-identical (digests hidden cd6a472b, long 1-3 edd33d4a /
  f2b38758 / e613c293, all equal). Tests per corpus k (k = 1..4): `ladder_<k>_finishes` w3,
  `ladder_<k>_normalized` w5, `ladder_<k>_summary` w5, `ladder_<k>_product_summary` w3,
  `ladder_<k>_segment_<s>` w3 x4 = 28. Existing check bodies unchanged. Checks 76 -> 108 (TS-23 warn).

## 4. Kill table (Docker python:3.12-slim, --cpus 2, --memory 4g; WORK/KILL_TEST.md)
Corpora: ladder_72001 (76000 acc, 11000 res, 20000 tiers, 61587 lines), ladder_72002 (same, 50000
tiers, 61530 lines), ladder_72003 (84000 acc, 12000 res, 50000 tiers, 70963 lines). Points per
corpus in the prototype = 16 (finishes 3, normalized 5, summary 5, product_summary 3). Shipped inputs
fast: yes for every solver (3-tier card, 15k lines).

| solver | 72001 s | 72002 s | 72003 s | kind | lever pts kept (72003) |
|---|---|---|---|---|---|
| ref_solve (solution/solve.py, bisect + memo) | 2.56 | 2.92 | 3.07 | EXACT | 16/16 |
| s8_memo (iterative memo walk, scan tiers) | 39.18 | - | >45 | TIMEOUT | 0 |
| s9_plainwalk | - | - | 21.57 | TIMEOUT | 0 |
| s10 full forward tier scan | 27.11 | >60 | >45 | TIMEOUT | 0 |
| s11 forward scan with break (strongest scan) | 12.71 | 28.05 | 31.40 | TIMEOUT | 0 |
| s12 reverse scan with break | 20.24 | 46.18 | >45 | TIMEOUT | 0 |
| s13 max over starts | 28.23 | >60 | >45 | TIMEOUT | 0 |
| s1 probe / s2 per-line / s4 end-only / s6 naive | - | - | >45 | TIMEOUT | 0 |
| s7 recursive lru | - | - | 0.20 | CRASH (RecursionError) | 0 |
| s3 keyed by parent text | - | - | 3.54 | WRONG | 3/16 |
| s5 greedy one level | - | - | 3.46 | WRONG | 3/16 |
| agent_p3 (probe-3 program) | >45 | - | >45 | TIMEOUT | 0 |
| blind_c60b (scored 100 in wave 2) | >45 | - | >45 | TIMEOUT | 0 |
| blind_9d66 (scored 100 in wave 2) | >45 | - | >45 | TIMEOUT | 0 |
| blind_d576 (6f5046a) | >45 | - | >45 | TIMEOUT | 0 |

Bar: every generic, blind and agent program loses >= 81% of the lever points (bar 15%); reference max
3.07 s (test reference 3.24 s) <= 3.75 s = 1/4 of 15 s. Strongest generic solver for the new core is
bisect over `from`; it is the reference, which is why the lever also needs the deep tree (memo walk).

## 5. Predicted test cost (positive 407; measured in Phase 3)
| program | lost | tests % |
|---|---|---|
| memo walk + tier scan (blinds c60b, 9d66; all-but-one on LV-MU-9) | 112 | 72.5 |
| plain walk + bisect (all-but-one on LV-MU-8) | 160 | 60.7 |
| probe-3 program / plain first write (walk without memo or with scan) | 160 | 60.7 |
| oracle | 0 | 100 |

## 6. Judge band (37 positive, mid 15-20 on the run-3 trajectory)
Kept (wave 2, ids R1-R15): B1 times last program on /app/data (3, run no); B2 larger built input (3,
no); B3 sums a money field over normalized.jsonl beside summary.json (3, no); B4 missing-input refusal
shown (3, no output after edit); B5 control-mismatch refusal shown (3, no); B6 J4 code quality (3,
no); B7 recomputes line charges every region (3, yes); B8 altered copy, narrowed to "changed a pool
amount or minimum in commitments.xml and shows a credit or true-up figure that moved" (3, yes, step
19); B9 foreign cwd and folders after last edit (3, yes); B10 lists every /app/out file (1, yes).
New probes (type "agent behavior", target trajectory, oracle shows each in solve.sh self-check):
- B11 (3): after its last edit to /app/out/transform.py, runs it on an input it built whose
  rate_card.json lists 1,000 or more tiers for one product, and a command output shows that run's
  elapsed seconds. Serves rating_contract.md:48-49 and :110-113 via instruction.md:28. Run 3: no.
- B12 (3): after its last edit, runs it on an input it built in which one account is 1,000 or more
  parent links below the top of its billing group, and a command output shows that run's elapsed
  seconds. Serves rating_contract.md:24-26, :48-49. Run 3: no (chains of 1-3 links only).
- B13 (3): runs the program on a copy of the inputs in which it changed a `from` value in
  rate_card.json, and a command output shows a normalized.jsonl line whose `tier` changed. Serves
  rating_contract.md:153-156 via instruction.md:28. Run 3: no (changed a rate, not a `from`).
Negatives unchanged and disjoint (AL-28, largest single act -5): N1 J3a -3, N2 -5, N3 -3, N4 -5,
N5 -3. B8 and B13 read different observables (credit/true-up vs a line's tier: JD-14).

| | positives earned | negatives | rubric % |
|---|---|---|---|
| run 3 as observed | B7 3 + B8 3 + B9 3 + B10 1 = 10 / 37 | N1 -3 | 18.9 (27.0 without N1) |
| peer mid (probes at 25%) | about 8-10 / 37 | 0 to -3 | 15-27 |

Predicted run: tests 60.7-72.5 (memo-walk agent 72.5), rubric 18.9, final 39.8-45.7 (under 50).

## 7. Phase 2 build plan (after "go")
- gen_core `_gen_ladder` + `ladder` parameter (done in WORK, default 0); ref_core bisect (done in WORK).
- tests_template: `LADDER_SHAPES`, `_ladder_files(k)`, 32 new checks, reward.toml 0.5/407; assemble.
- judge.toml: B8 narrowed, B11-B13 added (R ids renumbered sequentially), reward judge 0.5/37.
- solve.sh self-check: three new plain checks (ladder timing, deep chain timing, `from` edit tier move).
- Docs unchanged except none; TRUTH by script last; XREF, LEVERS, COST_TABLE, QC_DEFENCE, JUDGE_MAP.

## Lessons for the master
- Two levers that must each cost >= 25% alone but <= 40% together only fit when one corpus carries both | template_change: harden prompt Phase 1 step 3 could state the combined-corpus rule
- Test reference itself used a linear tier scan; check the reference's own complexity before scaling a dimension | no change: caught in Phase 1
