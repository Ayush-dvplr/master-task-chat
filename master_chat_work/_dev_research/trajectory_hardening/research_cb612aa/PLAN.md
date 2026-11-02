# Per-task plan (cb612aa). Proposals only; nothing was edited.

Gate: tests < 100 AND final < 70 on one run of a QC-passed bundle (push rule of 27 Oct). Run variance is ±18-21 pp tests and ±20 pp final (WAY_B.md §1).

## sentinel-policy-recompute: QC-SAFE fix, then push
- Current state: attempt 7 (checksum b15c281b7c) scored 80.69 / 19.51 / 50.1 and meets the gate (scores.jsonl:94). QC v7 FAIL has 1 open item: CL-2, judge R10 is vacuous because the shipped cli.py has no exception handlers (`QC/reports/sentinel-policy-recompute/v7.md:37`; the fix text is at `:38` and targets `tests/judge.toml:131`).
- Trips seen in attempt 7: the `ledger_repair` lever family (−28 test points, which is the intended lever per harden_t3 DIAGNOSIS.md:32-49). Judge R1, R3-R9 and R11 were skipped. Step 45 claims "All checks pass" while 6 positive tests failed, and no negative charges that claim.
- Change: (1) rewrite R10 exactly as `v7.md:38` says (JD-6 decidable, JD-7 the oracle must meet it; check that solve.py's cli.py has the handler). (2) Recompute the reward.toml judge weight only if the positive judge total changes (TS-S10). (3) Optional honesty negative J3a −3 "claims checks pass without re-running after the last edit". Check AL-28: no other layer may charge the same act, so the total stays at most −5. Then run QC v8.
- Way A is eligible: only judge.toml changes, and all 8 artifacts are ok. A regrade of attempt 7 against v8 keeps tests exactly 80.69, because the test code is unchanged. Only the judge re-runs. If R10 now fails, judge drops at most 5/41 and final lands around 44-50. **Use it as the pre-check.** For the push, prefer **Way B, one new run** on v8, because LEVER_RULES_v3.md:211/213 do not count old-program evidence. Expected margin is about 19 pp on tests and about 20 pp on final, which equals one variance band, so plan for a second run if the first misses.

## tariff-engine-audit-repair: QC-SAFE design, QC not yet run
- Current state: the latest run (26T12:26) was tests 100 / 18.18 / 59.09 on a bundle older than rounds 2-3 (harden_w1 DESIGN.md:7). The trajectory shows 0 failed tests, 9 skipped judge acts, and 1 unconfirmed caveat (TRIP_POINTS.csv).
- harden_w1 has already been built. It adds the lever: 7 hidden statement corpora, 21 checks, 91 of 488 positive points (18.6%, DESIGN.md:75). Every generic solver loses at least 76.9% of the lever (DESIGN.md:70). It also changes the environment: vouchers.csv 198→210 rows, account A1643 (HARDEN_REPORT.md:11).
- Way A is **not eligible** because the environment changed. Use Way B: QC the w1 bundle, then one run.
- QC watch-outs: A3 warns at 112 checks (> 35; `tests_qc.py:293-297`). TS-23 requires negative sum ≤ positive sum. TS-20 requires the new w5 `due_exact`/`redeemed_exact` checks to sit at core weight, matching the instruction ordering. Recompute DS-22 sha.

## cold-chain-backbone-quote: QC-RISKY
- Current state: run_1 (25T15:36) scored 100 / 70 / 85.0. All 24 positive checks passed from the first write (DESIGN.md:9,15).
- harden_w1 changes everything an agent can see (HARDEN_REPORT.md:10-14): it deletes the api_contract E_BAD_SPAN and size clauses, regenerates data, adds a sentence at instruction.md:9, and adds a new artifact core.py. Way A is impossible: core.py is missing from the run manifest, so `_validate_artifact_coverage` rejects the regrade. Use Way B.
- Risks: deleting stated bounds and then grading wide books needs the graded rule to remain stated (AL-1 `05_…:21`, IN-8). I confirmed no test or environment file still names E_BAD_SPAN (grep, 0 hits). The new instruction line "written so that our team can maintain it" adds a maintainability criterion that must be JD-15 odds-raising, not a w5 preference. The new wide_* checks must be w5 only if the instruction makes them core (TS-20). The kill table claims 17.1-20% loss for every solver (DESIGN.md:55-73), which is about one variance band. That is thin for tests < 100 on a single run.

## schema-migration-plan-repair: QC-SAFE, the textbook Way A case
- Current state: probe a4 (23T15:45) scored 100 / −7.69 / 46.16, so final is already < 70 but tests are 100. The trajectory shows plain Dijkstra with no lower bound (DESIGN.md:22).
- harden_w1 is DONE. It only touches tests/test_output.py, reward.toml, solve.py and TRUTH.md, and "No agent-visible text changed" (HARDEN_REPORT.md:11,:57). The lever is 40 points of exact-optimum checks on larger hidden graphs, 16.6%. The last QC (v7, 23 Oct) was MINOR, but the bundle changed afterwards, so QC must run again. A3 warns at 71 checks (HARDEN_REPORT.md:36).
- Way A is eligible and is the cheapest diagnostic: regrade probe a4 against w1. If probe a4's planner loses at least one lever check, that shows the lever bites the exact program the trajectory recorded (AL-27 trigger depth satisfied). For the push, still do Way B, one run (LEVER_RULES_v3.md:211/213).

## district-heat-flex-procurement: QC-SAFE design, QC not yet run
- Current state: probe 9 scored 100 / 37.04 / 68.52, so final is < 70 but tests are 100 (DESIGN.md:4). Its program ran LATE (past 120 s) on the lever inputs (DESIGN.md:58,88,93). That is a real trip, but no test grades it yet.
- harden_w1 adds a sentence at environment/data/schema.md:162-163 (HARDEN_REPORT.md:12-14), so Way A is not eligible. Use Way B after QC.
- Watch-outs: the new sentence must state the rule without giving the recipe (IN-14 `01_…:44`; IN-17 `:47`). The 50 existing checks are unchanged (HARDEN_REPORT.md:30). The predicted all-but-one score is 84.8 (DESIGN.md:76), so a 15 pp margin on tests is below one variance band. Expect a re-run.

## metered-usage-rating-pipeline: QC-SAFE design, build status UNKNOWN
- Current state: probe 3 scored 100 / 64.71 / 82.35 (scores.jsonl:92). The first full draft was exact at step 15 (DESIGN.md:7). The trajectory has 3 W&G judge rows and nothing graded wrong in tests.
- harden_w2 has DESIGN.md and STACKING_CHECK.md only, with no HARDEN_REPORT, so the build state is UNKNOWN. The lever is P-3 billing groups on long hidden extracts: 48 points, 247→295, 16.3%, and the probe program scores 0/48 because it times out (DESIGN.md:30,37). The judge band is N1 −3 and N2 −5 (DESIGN.md:47-62). AL-28 matters here: if N2 −5 and a test negative can both charge one act, the total exceeds −5.
- Way A eligibility is UNKNOWN. Settling check: after the build, diff `Tasks_INPUT/metered-usage-rating-pipeline/{instruction.md,environment/}` against `H/Output_RFP/metered-usage-rating-pipeline/`. If they are identical, regrade probe 3 as the diagnostic. Residual risk: an iterative memo solution keeps all 48 points (DESIGN.md:45), which leaves the lever thin.
