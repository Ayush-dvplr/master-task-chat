# HARDEN REPORT: district-heat-flex-procurement, round 1 (21 Oct 2026, 16:30 IST)

Verdict: P3 PASS on the tests channel. All numbers are tests-only, measured with P3 method (b):
the exe_copy tests image runs rewardkit 0.2.1 and reruns each solver inside it with the 30 s
limit. Raw results are in `r1_results.json` (round 1) and `r0_results.json` (round 0).
Working copy: `master_chat_work/bundles/district-heat-flex-procurement/`. The ORIGINAL was not
edited.

## Before and after
| Row | Round 0 measured | Round 1 arithmetic | Round 1 measured | Target |
|---|---|---|---|---|
| S0 nop | 0.000 | 0 | 0.000 | 0.0 |
| S1 stub | -0.010 | -1/139 = -0.007 | -0.007 (paid artifact_set 1, canonical 1; negative_missing_sections fired) | at most 0.25 |
| S2 lazy (all 10 levers wrong) | 0.592 | 12/139 = 0.086 | 0.086 | at most 0.10 |
| S4 careful (old rules right, 5 new levers wrong) | 1.000 | 27/139 = 0.194 | 0.194 | 0.10 to 0.20 |
| S4b (S4 with DH-3 right, extra row) | - | 53/139 = 0.381 | 0.381 | info |
| S5 oracle | 1.000 | 1 | 1.000 | 1.0 |
| shortcut (hardcoded shipped reports) | 0.459 | - | -0.007 (negative_hardcoded_sample_answers fired) | at most 0.10 |

S3 (one lever wrong), measured, with weight lost out of 139: H1 0.885 (16), H2 0.871 (18; this
also loses large_tie_count_case because the logged tuple changes), H3 0.942 (8), H4 0.942 (8),
H5 0.957 (6), DH-1 0.813 (26), DH-2 0.820 (25), DH-3 0.813 (26), DH-4 0.806 (27), DH-5 0.942 (8).
Every lever loses points, and the share lost stays at or below 0.194.
S4b is an honest warning: DH-3 is plainly stated, so a careful run probably gets it right. On the
tests, that run would sit near 0.38 unless it also misses DH-1, DH-2, DH-4 or DH-5.

## Levers (full table: `_work/.../LEVERS.md`, round 0 in `LEVERS_r0.md`)
| Lever | Round 0 | Round 1 | Weight needing it (of 139) | Shipped data |
|---|---|---|---|---|
| LV-H01 waiver precedence | 8 of 98, leaked | 1 case at 3, plus H1 x DH-5 (5 + 3) and DH-3 x DH-5 (5) | 11 | HIDDEN-ONLY |
| LV-H02 greatest tuple | 8, leaked | 1 case at 3, plus x DH-1 (5) and x DH-2 (5) | 13 | HIDDEN-ONLY |
| LV-H03 cap after uplift | 8, leaked | 1 case at 3, plus x DH-3 (5) | 8 | HIDDEN-ONLY |
| LV-H04 descending-id cents | 8, leaked | 1 case at 3, plus x DH-3 (5) | 8 | DERIVABLE now (1,054 funded pools tie); no shipped value graded |
| LV-H05 quantise when derived | 8, leaked | 1 case at 3, plus H5c x DH-3 (3) | 6 | HIDDEN-ONLY |
| LV-DH-1 exact search, 20 and 22 sites, 30 s (D) | - | 6 checks | 26 | HIDDEN-ONLY |
| LV-DH-2 per-value ticks inside the search (A) | - | 5 checks | 25 | HIDDEN-ONLY |
| LV-DH-3 funded pool after credits (B) | - | 1 pure + 1 ordinary + 4 compositions | 26 | DERIVABLE, counted through compositions |
| LV-DH-4 rejected profile and site rows (F) | - | 7 checks | 27 | HIDDEN-ONLY |
| LV-DH-5 waived recipient weight (A) | - | 2 checks + 1 composition | 13 | HIDDEN-ONLY |
Composition share: 0 in round 0, now 38/139 = 0.273. No visible value check remains. The lever-neutral weight is 12/139: 4 format checks at 1 each, ordinary portfolios 5, ordinary segments 3.

## Validity fixes (kept apart from hardening)
- V4 REAL, fixed: schema.md section 1 now states that every `region_code` in sites, targets,
  feeder limits, segment floors and pools goes through `[region_codes]`, and that records match on
  the region name. V1 to V3 are unchanged, as instructed.
- Contradictions fixed: task.toml no longer says "exhaustive search"; judge R5 ("before choosing
  exhaustive search") is replaced; DESIGN.md section 8 now lists the registered round-0 weights
  (total 98, not 87).
- Pre-existing failure against the live QC: judge.toml used the retired annotation keys, and the
  live judge_qc failed the ORIGINAL with 24 FAILs. judge_build.py now writes the four keys mode,
  type, evaluation_target, importance (19/0/0).
- Found during build (my own new code): both DP optimisers first merged states on raw bid cost
  rather than cost_weight times bid cost. check_exact.py caught it (5 of 200 mismatches); fixed,
  then 0 of 300.

## New checks (round 1: 41 checks, 37 positive = 139, 4 negatives = -16; QC WARN A3 over 35, recorded)
- Format checks, weight 1: artifact_set_exists_and_parses, canonical_serialization_and_integer_units,
  report_keys_match_schema, report_arrays_in_schema_order. The 12 visible value checks are removed
  (TS-20, master answer D2).
- Ordinary seeded extract: portfolios 5, segment files 3, summary and totals 3 (needs DH-3).
- One rule each: waiver_precedence 3, tie_break_greatest_tuple 3, cap_after_uplift 3,
  residual_ties_descending_id 3, per_value_tick_quantisation 3 (now on segment relief).
- DH-1: large_20 portfolio 5 and intervals 3, large_22 portfolio 5 and intervals 3, large_tie_count
  5, large_tie_greatest_tuple_shuffled 5.
- DH-2: tick_feasibility, tick_shortfall_order, tick_created_tie, tick_floor_deficit,
  tick_recovery_ceiling, 5 each.
- DH-3: funded_pool 5 (North plain, South credit above pool), after_capped_credit 5,
  residual_tie 5, after_site_rounding 3, waived_weight 5.
- DH-5: held_waiver_weight 5, cooldown_waiver_weight 3.
- DH-4: duplicate row portfolio 5 and count 3, out-of-range portfolio 5 and count 3, unknown region
  counts 3 and reports 5, mixed rejection counts 3.
- Each check first proves that every wrong reading it names changes its observable. The large
  checks also prove the product of choices exceeds 10^12 and that the tie count is as built.
  Downstream stages are graded on forced portfolios (one site, one offer), so an optimiser slip
  costs nothing in the grant checks.

## Time limit N (answer 5)
Oracle, 3 runs per large extract, docker --cpus=2 --memory=4g, agent image (exe_copy variant
without the OpenHands venv, same base image and data):
- large_20: 1.785 / 1.126 / 1.018 s
- large_22: 0.660 / 0.634 / 0.755 s
- large_tie: 0.389 / 0.358 / 0.408 s
- large_tie_shuffled: 0.848 / 0.757 / 0.754 s

N = max(30, 10 x 1.785) = 30 s. The 22-site cases have 7.8e14 and 7.6e14 portfolios; at a
generous 10^7 portfolios per second, enumeration needs about 7.8e7 s, far above 100 x N = 3000 s.
Even the 1.1e10 to 1.5e10 ceiling-feasible portfolios need 3000 s at 5 x 10^6 per second.
TS-11: the oracle uses at most 6% of N, and the reference solves each case in about 1 s or
less. No check passes or fails on a time near N for the oracle or for full enumeration.
Measured verifier wall time: about 35 to 45 s for a solver with no timeouts (oracle 18 s before
nop). Solvers that time out on all four large extracts take about 2.6 min.

## New judge criteria (17 criteria, positive 45, negative -10)
- R5: the response states that the shared cents are the pool minus the event-region credit, and 0
  when the credits exceed it.
- R13: the response states that the search rounds each Wh value to ticks before adding.
- R14: the response states that a waived row counts double only with the final label
  CONTINUITY_WAIVED, so hold and cooldown count once.
- R15: the response states that the first of two repeated profile rows is kept.
- R16 (kept): the agent runs the final derive_report.py on /app/data after its last edit.
- R17 (kept): the response states the largest event-region run and its seconds.
- R5, R13, R14, R15 and R17 are outcome criteria on the closing message. The instruction asks for
  each of these facts in plain words.
- Unchanged: R1 to R4 and R6 to R8 still reward effort. They fall under the same "outcome, not
  effort" rule, so the master chat may want them replaced too.

## Gates (run once)
- structure_qc 17/0/0, instruction_qc 5/0/0, tests_qc 34/1/0 (A3 WARN, 41 checks), judge_qc 19/0/0.
- validate_bundle --archetype domain-calculation: 39 passed, 1 FAIL. The FAIL is §15.5
  `authored_by`, `status`; see Q18.
- playground --skip-docker: 0 FAIL, 1 WARN. A2 flags `late_profile_rows` and `shuffle`, which are
  keys of the verifier's internal extract specs and are never read from agent output.
- Oracle 1.0 and nop 0.0 on the tests channel (measured above). These are not Harbor Step-10
  runs.
- D1, playground D4 ablation: N/A. Hidden extracts are generated verifier-side, so deleting a
  shipped file cannot lower the 135 hidden points. Proof that every file is load-bearing on the
  shipped run is in `load_bearing.txt`: deleting any file crashes the oracle, and emptying one
  either crashes it or changes 6 to 9 of the 9 reports.
- Exactness: `_work/.../check_exact.py`, 300 random extracts (1,200 event-regions, 338 tie
  decisions, twin offers and odd Wh values): the verifier DP, the oracle DP and the round-0 plain
  enumeration agree on all of them, 0 mismatches.

## UPSTREAM CHANGED (common rule 1)
The harness clone was fast-forwarded during this session. The pulls were not mine (reflog shows
`pull --ff-only` at 15:18 and 16:08 IST): 9b8229f6, then 95401d0e, then bde868c4. Compared with
the fingerprints:
- GEN: 50 files changed and 9 missing (template folders of repo-patch and service-interaction),
  including validate_bundle.py, playground.py and templates/domain-calculation/{archetype.toml,
  TRUTH.md, judge.toml, test.sh}.
- QC: 9 files changed (01 to 05, Final_checklist, judge_qc, structure_qc, tests_qc).

The judge, validator and playground gates above ran on 95401d0e. The scoring did not depend on
either QC version. I re-ran the 4 QC scripts and the validator once on bde868c4: still 0 QC FAIL,
and the validator still fails only §15.5. One new WARN: tests_qc H5 now prefers `chmod 755
/logs/verifier` over the bundle's 700, and the generator's test.sh template changed the same way.
I did not apply it because it is a new upstream rule; it is a one-line change in tests/test.sh.
The fingerprint files in master_chat_tasks are stale; the master chat owns them.

## OPEN CONFLICT Q18
TRUTH provenance still carries `authored_by: null` and `status: reference`, as instructed. New
fact: the live validator (f0579497) now forbids both keys under §15.5, citing DS-27. Both live
tools therefore agree, and the validator's only FAIL is this one. Resolving it means deleting those
two lines; I did not apply that.

## Not run or not checked
- Harbor oracle x5 Step 10.
- playground with Docker.
- Any real model run or judged channel. There is no OPENAI_API_KEY here, so the judge
  criteria are untested against a trajectory.
- The levers' effect on a real model, which only real runs measure. The PL generator and the live QC
  fingerprints were not re-hashed after Phase 0; no file under GEN or QC was written.
