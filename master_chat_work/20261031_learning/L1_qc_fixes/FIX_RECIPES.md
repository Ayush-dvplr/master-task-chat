# Fix recipes — 20 check IDs appearing in the most tasks

Counts are distinct tasks, not report rows (`python3 scripts/build_l1.py`; `parse_summary.json:$.check_tasks`). “Reported fixed” means the next QC comparison says fixed; no scored agent rerun is implied. Shared-file side effects use the operational definition in `FIX_EFFECTS.csv`.

## JD-5 — 14 tasks

- Usual problem: A judge item combines two or more independently gradable observations. Example: `TB/QC/reports/b7c42a8f-6d19-4e35-9f82-5a3c1d7e8042/v2.md:58`.
- Worked: the same R9 edit as finding 2; outage-window-replan v1 to the next round. Evidence: `TB/QC/reports/outage-window-replan/v1.md:42`, `TB/QC/reports/outage-window-replan/v2.md:24`, `TB/master_chat_work/20261030_outage-window-replan/p12_fix_v1_20552cf/RECHECK_FIX.md`.
- Failed or returned: the criterion was still reported in schema-migration-plan-repair v1 and the next round; whether the identical defect survived is UNVERIFIED. Evidence: `TB/QC/reports/schema-migration-plan-repair/v1.md:46`, `TB/QC/reports/schema-migration-plan-repair/v2.md:47`.
- Build time: Make each judge criterion test one observable.

## DS-22 — 14 tasks

- Usual problem: TRUTH.md has a stale count, digest or description after code or test edits. Example: `TB/QC/reports/assay-plate-triage/v1.md:45`.
- Worked: Give the five probes descriptive names like the other contract checks; schema-migration-plan-repair v12 to the next round. Evidence: `TB/QC/reports/schema-migration-plan-repair/v12.md:41`, `TB/QC/reports/schema-migration-plan-repair/v13.md:408`, `TB/master_chat_work/20261029_schema-migration-plan-repair/p12_fix_v12_08741c4/RECHECK_FIX.md`.
- Failed or broke: solution/solve.py planner +102-105, 107, 126-127, 137, 139-143, 153-198, 201, 218, 227; new DS-22 appeared in schema-migration-plan-repair v13. This is a file/criterion link, not isolated causality. Evidence: `TB/QC/reports/schema-migration-plan-repair/v13.md:33`, `TB/master_chat_work/20261029_schema-migration-plan-repair/p12_fix_v12_08741c4/RECHECK_FIX.md`.
- Build time: Recompute every count, digest and claimed behaviour in TRUTH.md after the final edit.

## AL-27 — 13 tasks

- Usual problem: A stated rule has no graded input that activates it. Example: `TB/QC/reports/b7c42a8f-6d19-4e35-9f82-5a3c1d7e8042/v1.md:57`.
- Worked: add a generator record with an unknown asset id and earliest_start 0 so the pair is graded in h2/h3; outage-window-replan v1 to the next round. Evidence: `TB/QC/reports/outage-window-replan/v1.md:37`, `TB/QC/reports/outage-window-replan/v2.md:25`, `TB/master_chat_work/20261030_outage-window-replan/p12_fix_v1_20552cf/RECHECK_FIX.md`.
- Failed or broke: new fixtures fixed several branches but left and exposed other untriggered branches; new AL-27 appeared in cohort-retention-reconciliation v5. This is a file/criterion link, not isolated causality. Evidence: `TB/QC/reports/cohort-retention-reconciliation/v5.md:35`, `TB/QC/reports/cohort-retention-reconciliation/v5.md:379`.
- Build time: Mutate each stated branch once and require at least one graded fixture to change.

## TS-23 — 12 tasks

- Usual problem: The number of test checks exceeds the kit’s 35-check warning cap. Example: `TB/QC/reports/caldermoor-commitment-closure/v1.md:40`.
- Reported closed, exact edit UNVERIFIED; dispatch-plan-reoptimization v5 to the next round. Evidence: `TB/QC/reports/dispatch-plan-reoptimization/v5.md:54`, `TB/QC/reports/dispatch-plan-reoptimization/v6.md:445`.
- Failed or broke: FIX: R5 deleted. Old R6-R12 renumbered R5-R11, because judge_qc.py:17/245 requires sequential ids. reward.toml judge 0.018518518518518517 -> 0.02083333333333333; new TS-23 appeared in district-heat-flex-procurement v7. This is a file/criterion link, not isolated causality. Evidence: `TB/QC/reports/district-heat-flex-procurement/v7.md:43`, `TB/master_chat_work/20261027_district-heat-flex-procurement/p12_fix_v6_9a85fdc/RECHECK_FIX.md`.
- Build time: Budget the check count before splitting fixtures; record a count-cap decision when needed.

## TS-13 — 11 tasks

- Usual problem: One check bundles unrelated properties or repeats credit for one error. Example: `TB/QC/reports/b7c42a8f-6d19-4e35-9f82-5a3c1d7e8042/v1.md:65`.
- Worked: split the bundled checks, give dev and prod values the same weight and summary 3; warrant-asof-entitlement-compiler v1 to the next round. Evidence: `TB/QC/reports/warrant-asof-entitlement-compiler/v1.md:52`, `TB/QC/reports/warrant-asof-entitlement-compiler/v2.md:427`, `TB/master_chat_work/20261029_warrant-asof-entitlement-compiler/p12_fix_v1_4989b35/RECHECK_FIX.md`.
- Failed or broke: FIX: _same(a, b) compares json.dumps(sort_keys=True) texts (bool and int differ); used for config, summary, self check, reproduce and the new checks; FIX: split; new TS-13 appeared in warrant-asof-entitlement-compiler v2. This is a file/criterion link, not isolated causality. Evidence: `TB/QC/reports/warrant-asof-entitlement-compiler/v2.md:35`, `TB/master_chat_work/20261029_warrant-asof-entitlement-compiler/p12_fix_v1_4989b35/RECHECK_FIX.md`.
- Build time: Give unrelated properties separate checks and avoid repeated payment for one wrong fact.

## AL-2 — 11 tasks

- Usual problem: An instruction promise has no corresponding grading check. Example: `TB/QC/reports/b7c42a8f-6d19-4e35-9f82-5a3c1d7e8042/v1.md:56`.
- Worked: change judge.toml:131 R10 to "The response names every project of /app/ci that /app/out/module_parser.json records as rejected and gives a rejection code for each." (R12 keeps code correctness, so no double pay; cold-chain-backbone-quote v2 to the next round. Evidence: `TB/QC/reports/cold-chain-backbone-quote/v2.md:34`, `TB/QC/reports/cold-chain-backbone-quote/v3.md:292`, `TB/master_chat_work/20261028_cold-chain-backbone-quote/p12_fix_v2_905cf6e/RECHECK_FIX.md`.
- Failed or returned: the criterion was still reported in cold-chain-backbone-quote v1 and the next round; whether the identical defect survived is UNVERIFIED. Evidence: `TB/QC/reports/cold-chain-backbone-quote/v1.md:41`, `TB/QC/reports/cold-chain-backbone-quote/v2.md:34`.
- Build time: Trace every instruction promise to an executable check or judged criterion.

## DS-27 — 11 tasks

- Usual problem: TRUTH.md narrates authoring history instead of task truth. Example: `TB/QC/reports/cohort-retention-reconciliation/v1.md:39`.
- Worked: write "Digests:" and state the measured scores without "not yet run" wording; outage-window-replan v1 to the next round. Evidence: `TB/QC/reports/outage-window-replan/v1.md:46`, `TB/QC/reports/outage-window-replan/v2.md:22`, `TB/master_chat_work/20261030_outage-window-replan/p12_fix_v1_20552cf/RECHECK_FIX.md`.
- Failed or returned: the criterion was still reported in schema-migration-plan-repair v1 and the next round; whether the identical defect survived is UNVERIFIED. Evidence: `TB/QC/reports/schema-migration-plan-repair/v1.md:40`, `TB/QC/reports/schema-migration-plan-repair/v2.md:42`.
- Build time: Write TRUTH.md as task truth; remove build history and internal process notes.

## JD-15 — 11 tasks

- Usual problem: A judge item has the wrong kind or grades an unstated outcome. Example: `TB/QC/reports/b7c42a8f-6d19-4e35-9f82-5a3c1d7e8042/v1.md:67`.
- Worked: accept any input perturbation that shows a differing profile entry, or weight 1; warrant-asof-entitlement-compiler v1 to the next round. Evidence: `TB/QC/reports/warrant-asof-entitlement-compiler/v1.md:54`, `TB/QC/reports/warrant-asof-entitlement-compiler/v2.md:256`, `TB/master_chat_work/20261029_warrant-asof-entitlement-compiler/p12_fix_v1_4989b35/RECHECK_FIX.md`.
- Failed or broke: Files changed: instruction.md, tests/judge.toml, solution/TRUTH.md, task.toml. Not touched: environment/data, generators, hidden corpora, ledger_repair, tests/t; new JD-15 appeared in sentinel-policy-recompute v5. This is a file/criterion link, not isolated causality. Evidence: `TB/QC/reports/sentinel-policy-recompute/v5.md:34`, `TB/master_chat_work/20261026_sentinel-policy-recompute/p12_fix_v4/RECHECK_FIX.md`.
- Build time: Label conduct as agent behavior; put outcome requirements in visible instructions.

## JD-7 — 10 tasks

- Usual problem: The oracle fails or does not demonstrate a positive judge criterion. Example: `TB/QC/reports/b7c42a8f-6d19-4e35-9f82-5a3c1d7e8042/v1.md:49`.
- Worked: state the message rule in cli_contract.md and make the oracle wrap parse errors in CorpusError naming the file and record skipped rows, or narrow R9 to what cli_contract.md:14 states; warrant-asof-entitlement-compiler v1 to the next round. Evidence: `TB/QC/reports/warrant-asof-entitlement-compiler/v1.md:45`, `TB/QC/reports/warrant-asof-entitlement-compiler/v2.md:171`, `TB/master_chat_work/20261029_warrant-asof-entitlement-compiler/p12_fix_v1_4989b35/RECHECK_FIX.md`.
- Failed or returned: the criterion was still reported in b7c42a8f-6d19-4e35-9f82-5a3c1d7e8042 v1 and the next round; whether the identical defect survived is UNVERIFIED. Evidence: `TB/QC/reports/b7c42a8f-6d19-4e35-9f82-5a3c1d7e8042/v1.md:49`, `TB/QC/reports/b7c42a8f-6d19-4e35-9f82-5a3c1d7e8042/v2.md:43`.
- Build time: Run the oracle against each positive judged criterion before QC.

## TS-24 — 10 tasks

- Usual problem: A launched agent process can survive a timeout or hold the verifier past its budget. Example: `TB/QC/reports/assay-plate-triage/v1.md:67`.
- Worked: start the program with start_new_session=True and os.killpg its group on return and on timeout in _run_program; outage-window-replan v1 to the next round. Evidence: `TB/QC/reports/outage-window-replan/v1.md:33`, `TB/QC/reports/outage-window-replan/v2.md:23`, `TB/master_chat_work/20261030_outage-window-replan/p12_fix_v1_20552cf/RECHECK_FIX.md`.
- Failed or broke: UNVERIFIED; no linked recurrence or new finding was indexed.
- Build time: Start child programs in process groups and reap the entire group on every exit path.

## IN-16 — 9 tasks

- Usual problem: The instruction or visible contract leaves a graded edge case open to two readings. Example: `TB/QC/reports/cohort-retention-reconciliation/v4.md:35`.
- Worked: in handbook_ops_v9.md:27 change "never counted as rejected" to "never counted as rejected because of the cutoff; the section 14 rejection reasons are applied first"; dispatch-plan-reoptimization v6 to the next round. Evidence: `TB/QC/reports/dispatch-plan-reoptimization/v6.md:56`, `TB/QC/reports/dispatch-plan-reoptimization/v7.md:391`.
- Failed or broke: UNVERIFIED; no linked recurrence or new finding was indexed.
- Build time: State tie-breaks, units and edge cases before writing exact-output checks.

## TS-19 — 9 tasks

- Usual problem: A valid interpretation or honest agent fails a graded test. Example: `TB/QC/reports/assay-plate-triage/v1.md:47`.
- Worked: make the instruction and _RUN_SECONDS state the same limit; outage-window-replan v1 to the next round. Evidence: `TB/QC/reports/outage-window-replan/v1.md:41`, `TB/QC/reports/outage-window-replan/v2.md:23`, `TB/master_chat_work/20261030_outage-window-replan/p12_fix_v1_20552cf/RECHECK_FIX.md`.
- Failed or returned: the criterion was still reported in emberforge-vault-settlement v2 and the next round; whether the identical defect survived is UNVERIFIED. Evidence: `TB/QC/reports/emberforge-vault-settlement/v2.md:43`, `TB/QC/reports/emberforge-vault-settlement/v3.md:27`.
- Build time: Run an honest implementation against every fixture and compare fixture limits with the contract.

## DS-20 — 8 tasks

- Usual problem: The oracle disagrees with a stated rule or in-limit performance promise. Example: `TB/QC/reports/b7c42a8f-6d19-4e35-9f82-5a3c1d7e8042/v1.md:42`.
- Worked: route every listed window through the settled reading in solve.py and in the verifier's World/observe(), or narrow the contract sentence to the windows that actually follow it; warrant-asof-entitlement-compiler v1 to the next round. Evidence: `TB/QC/reports/warrant-asof-entitlement-compiler/v1.md:42`, `TB/QC/reports/warrant-asof-entitlement-compiler/v2.md:417`, `TB/master_chat_work/20261029_warrant-asof-entitlement-compiler/p12_fix_v1_4989b35/RECHECK_FIX.md`.
- Failed or returned: the criterion was still reported in schema-migration-plan-repair v12 and the next round; whether the identical defect survived is UNVERIFIED. Evidence: `TB/QC/reports/schema-migration-plan-repair/v12.md:31`, `TB/QC/reports/schema-migration-plan-repair/v13.md:32`.
- Build time: Compare the oracle against the stated contract on adversarial in-limit cases.

## IN-12 — 7 tasks

- Usual problem: Metadata misstates or underspecifies the dominant task work. Example: `TB/QC/reports/assay-plate-triage/v1.md:55`.
- Worked: add domain keywords and tags such as scheduling, combinatorial-optimization, maintenance-planning; outage-window-replan v1 to the next round. Evidence: `TB/QC/reports/outage-window-replan/v1.md:45`, `TB/QC/reports/outage-window-replan/v2.md:21`, `TB/master_chat_work/20261030_outage-window-replan/p12_fix_v1_20552cf/RECHECK_FIX.md`.
- Failed or broke: UNVERIFIED; no linked recurrence or new finding was indexed.
- Build time: Make category, description and tags match the dominant task work.

## TS-14 — 7 tasks

- Usual problem: A check’s name or description does not match its body. Example: `TB/QC/reports/assay-plate-triage/v1.md:57`.
- Worked: append ", cadence and capture count aside" to those nine descriptions and to the matching docstrings at test_output.py:2572-2652; match-replay-desync-audit v4 to the next round. Evidence: `TB/QC/reports/match-replay-desync-audit/v4.md:41`, `TB/QC/reports/match-replay-desync-audit/v5.md:347`.
- Failed or broke: import negative narrowed to third-party imports; name still says _or_network; new TS-14 appeared in district-heat-flex-procurement v10. This is a file/criterion link, not isolated causality. Evidence: `TB/QC/reports/district-heat-flex-procurement/v10.md:36`, `TB/QC/reports/district-heat-flex-procurement/v10.md:393`.
- Build time: Check that each criterion name and description describe its actual assertion.

## AL-28 — 7 tasks

- Usual problem: One act triggers multiple negative penalties whose total is excessive. Example: `TB/QC/reports/b7c42a8f-6d19-4e35-9f82-5a3c1d7e8042/v1.md:58`.
- Worked: carve R14 to claims about runs that do appear in the trajectory, or drop one of the two; outage-window-replan v1 to the next round. Evidence: `TB/QC/reports/outage-window-replan/v1.md:38`, `TB/QC/reports/outage-window-replan/v2.md:25`, `TB/master_chat_work/20261030_outage-window-replan/p12_fix_v1_20552cf/RECHECK_FIX.md`.
- Failed or broke: tests/judge.toml 65-195, 207-209, 220-221, 233-235, 246-248, 250, 254-268; new AL-28 appeared in schema-migration-plan-repair v9. This is a file/criterion link, not isolated causality. Evidence: `TB/QC/reports/schema-migration-plan-repair/v9.md:35`, `TB/QC/reports/schema-migration-plan-repair/v9.md`.
- Build time: Probe one cheating act against every negative and cap combined penalties.

## X1 — 6 tasks

- Usual problem: The structure scanner skips binary files, so embedded text can escape the sweep. Example: `TB/QC/reports/dispatch-plan-reoptimization/v1.md:51`.
- Worked: UNVERIFIED; no explicit next-round “fixed” comparison was indexed for this ID.
- Failed or returned: the criterion was still reported in dispatch-plan-reoptimization v3 and the next round; whether the identical defect survived is UNVERIFIED. Evidence: `TB/QC/reports/dispatch-plan-reoptimization/v3.md:43`, `TB/QC/reports/dispatch-plan-reoptimization/v4.md:52`.
- Build time: Inspect every file the text sweep skipped as binary, including archive members.

## IN-8 — 6 tasks

- Usual problem: A graded outcome is not learnable from an agent-visible source. Example: `TB/QC/reports/assay-plate-triage/v1.md:39`.
- Worked: UNVERIFIED; no explicit next-round “fixed” comparison was indexed for this ID.
- Failed or broke: tests/judge.toml 65-195, 207-209, 220-221, 233-235, 246-248, 250, 254-268; new IN-8 appeared in schema-migration-plan-repair v9. This is a file/criterion link, not isolated causality. Evidence: `TB/QC/reports/schema-migration-plan-repair/v9.md:34`, `TB/QC/reports/schema-migration-plan-repair/v9.md`.
- Build time: Map each judged outcome to an agent-visible rule or file.

## TS-16 — 6 tasks

- Usual problem: A negative check catches innocent code or misses the forbidden act. Example: `TB/QC/reports/b7c42a8f-6d19-4e35-9f82-5a3c1d7e8042/v1.md:48`.
- Worked: in tests/test_output.py:18221 count e["kind"] in ("write_outside", "write_input"); dispatch-plan-reoptimization v6 to the next round. Evidence: `TB/QC/reports/dispatch-plan-reoptimization/v6.md:57`, `TB/QC/reports/dispatch-plan-reoptimization/v7.md:392`.
- Failed or returned: the criterion was still reported in vendor-archive-roundtrip-recovery v3 and the next round; whether the identical defect survived is UNVERIFIED. Evidence: `TB/QC/reports/vendor-archive-roundtrip-recovery/v3.md:40`, `TB/QC/reports/vendor-archive-roundtrip-recovery/v4.md:38`.
- Build time: Probe anti-cheat checks with honest code and with a real cheat.

## CL-5 — 6 tasks

- Usual problem: A graded exact detail is absent from the agent-visible contract. Example: `TB/QC/reports/b7c42a8f-6d19-4e35-9f82-5a3c1d7e8042/v2.md:46`.
- Worked: add to record_shapes.md (and RULEBOOK_TEXTS) "Grades, tiers, ordinals and every other numeric column are written as JSON numbers."; emberforge-vault-settlement v1 to the next round. Evidence: `TB/QC/reports/emberforge-vault-settlement/v1.md:60`, `TB/QC/reports/emberforge-vault-settlement/v2.md:401`.
- Failed or broke: changed output contract still omits null sort placement; new CL-5 appeared in b7c42a8f-6d19-4e35-9f82-5a3c1d7e8042 v2. This is a file/criterion link, not isolated causality. Evidence: `TB/QC/reports/b7c42a8f-6d19-4e35-9f82-5a3c1d7e8042/v2.md:46`, `TB/QC/reports/b7c42a8f-6d19-4e35-9f82-5a3c1d7e8042/v2.md:374`.
- Build time: Specify every graded output detail, including null order and path form.

