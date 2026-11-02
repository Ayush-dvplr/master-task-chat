PASS WITH FIXES

# Verify report for UPGRADE_PLAN_v1 (board 3d3a74a), verify session 5125258, 29 Oct 2026 00:17-00:50 IST

The plan's structure, batches and almost all numbers hold. 28 WRONG findings (fixed in `UPGRADE_PLAN_v2.md`), 6 COULD NOT CHECK. None is a FAIL: every fix is covered by Ayush's answers or the current rules. One conflict (F3 vs C2) is fixed by Q24's own "a miss -> park". Nothing was applied; v1 is untouched.

Roots: `T` = `/Users/mac/Desktop/Terminal Bench`, `MT` = `T/master_chat_tasks`, `U` = `T/master_chat_work/20261028_upgrade`, `H` = `T/Terminal_2.0_Harbor_Harness`. Abbreviations as in plan v2 line 29.

## Check 1 — citations

| # | Item | Verdict | Evidence | Fix in v2 |
|---|---|---|---|---|
| 1.1 | v1:6 R1T, R1M paths | WRONG | `U/R1_ql_loop/TOOL_CHANGE_SPECS.md` and `MASTER_STEPS.md` do not exist; files are `U/R1_ql_loop/drafts/TOOL_CHANGE_SPECS.md`, `drafts/MASTER_STEPS.md` | v2:29 |
| 1.2 | A1 issue.py :14-19, :34, :36, :37, :71, :89-90, :101, :118-122, :137, :138-142 (`"who": "Ayush"` :140) | CONFIRMED | read `MT/tools/issue.py` (148 lines) | — |
| 1.3 | A2 intake.py :11, :104, :106, :108-111, :124 | CONFIRMED | `MT/tools/intake.py` (133 lines); :104 `gate = t < 85 and r < 85 and o < 50` | — |
| 1.4 | A3 status.py :22-23 FIELDS | CONFIRMED | `MT/tools/status.py` | — |
| 1.5 | A4 package_rfp_bundles.py :15, :117, :152, :236; "main :273-280" | WRONG (main) | `H/scripts/package_rfp_bundles.py` main is :273-298; :117 `_package_run`, :152 `_task_source`, :216 `package()` CONFIRMED | v2 A4 |
| 1.6 | E6/E1 "master_queue.py" | WRONG (path) | file is `H/scripts/master_queue.py` (1029 lines), not `H/master_queue.py`; :75, :230-235, :595-596, :616-625 (:623) CONFIRMED | v2 MQ abbreviation + backup |
| 1.7 | CR:27, :49, :61, :65-66; LR:1, :87-89, :210, :215; KN:113, :118, :119; AP:15, :26, :28-30, :37, :46, :47, :54; CHANGELOG:46-48 | CONFIRMED | read each line | — |
| 1.8 | F1 "Never 10 (CR:28 area)" | WRONG | Never 10 (freeze passed bytes) is CR:29; CR:28 is rule 9 | v2 F1 |
| 1.9 | auto.py :65-70, :73, :79-80, :87, :93-121, :271-275, :299-301, :403-430, :566-577, :597, :693, :909-954 (:935), :970-975, :1038, :1174-1180, :1237-1259, :1294-1338, :1367-1376, :1391-1397, :1420 | CONFIRMED | `MT/auto/auto.py` (1521 lines) | — |
| 1.10 | F2 "Ayush already OK'd the metered paid run, REPORT.md:22" | WRONG | `MT/auto/runs/20261028T1553_evening/REPORT.md:22` is an open Needs-Ayush question ("may it run ... once QC v1 passes?"); no OK row in DEC tail. The OK now exists: ANS Q23 a | v2 F2 cites ANS Q23 |
| 1.11 | REPORT.md:13-17 (3 paused rows, rule carry-over) | CONFIRMED | read | — |
| 1.12 | F1 HARDEN_REPORT :20, :29, :50; F2 DESIGN :114; F3 DESIGN :27, :36-39, :84, :96, :98-99 | CONFIRMED | `master_chat_work/20261027_cold-chain-backbone-quote/harden_w1_678c839/HARDEN_REPORT.md`; `.../20261027_metered-usage-rating-pipeline/harden_g36_361674d/DESIGN.md`; `.../20261028_schema-migration-plan-repair/harden_g36_a4f790c/DESIGN.md` | — |
| 1.13 | F1 "RECHECK_FIX v3 :107-112" (no folder) | WRONG (no path) | real file `T/master_chat_work/20261028_cold-chain-backbone-quote/p12_fix_v3_b0aca9b/RECHECK_FIX.md:107-112` (diff -r rc=0) | v2 F1 |
| 1.14 | A1 "24 overrides" | WRONG (minor) | counted `override` rows in DEC ranges 293-313, 359-360, 380-381, 393-395, 397-399, 401-404 = 23 (62 cap overrides since 24 Oct); no decision impact | v2 A1 |
| 1.15 | DEC:390-391, :400 (sentinel regrade 44.53, district 44.84) | CONFIRMED | `MT/decisions.jsonl` | — |
| 1.16 | R2A section lines 5/33/38/44; old daemon.json; Docker memory 12 GiB | CONFIRMED | `U/R2_mac_setup/apply_safe.md`; `~/.docker/daemon.json`; settings-store.json `MemoryMiB 12288` | — |

## Check 2 — statistics (re-ran in `/tmp/V1-verify-5125258/`)

| # | Item | Verdict | Evidence | Fix |
|---|---|---|---|---|
| 2.1 | C2 evidence: 10 valid gate runs, mean tests 78.7, rubric 23.5, 1 below 40 | CONFIRMED | copy of R3 `s08_ours.py` on `MT/registry/scores.jsonl` -> "gate runs 10 ... final<40 1 ... mean tests 78.7 mean rubric 23.5" | v2 marks CHECKED |
| 2.2 | C3 L2: shipped 62% vs held-out 42%; w5 43% vs 23%; within-author r_tests -0.43 | CONFIRMED | copy of R3 `s05_confounds_recipe.py` (doc85) | CHECKED |
| 2.3 | C3 N1: r -0.40 pooled, -0.32 within-author | CONFIRMED | same run | CHECKED |
| 2.4 | C3 N2: held-out w5 share >= 50%: 8 tasks mean 34.8, 5 < 40; cur90 9 tasks mean 32.8 | CONFIRMED | same run (cur90: n 9, mean 32.8, 6 < 40) | CHECKED |
| 2.5 | HardExpert hidden share 0.68 vs 0.16-0.18, hidden pass 0.01; share >= 0.5 median 35.7 vs 56.5 | CONFIRMED | R4 `contrast.py` re-run: contrast.md + features.csv byte-identical to R4; medians 0.677 / 0.155 / 0.179, pass 0.013; n 14 median 35.67 vs n 76 median 56.46 | CHECKED |
| 2.6 | C5 claims 41/18/5/4; wrong C10, C24, C51, C58, C60 | CONFIRMED | claims.csv: 68 rows, counts and ids match | — |
| 2.7 | C3 L6 "verify criteria 52% vs read 24%" | COULD NOT CHECK | not re-run (one R3 + one R4 script was the bar; did two R3 + one R4); left [UNVERIFIED] | — |
| note | R3F:101 r_final -0.31 is the cur90 value; doc85 gives -0.26 | — | s05 output | plan cites only r_tests; no impact |

## Check 3 — arithmetic

| # | Item | Verdict | Evidence | Fix |
|---|---|---|---|---|
| 3.1 | F1 predicted (77.8 + 34) / 2 = 55.9 ≈ 56 | CONFIRMED | — | — |
| 3.2 | F3: rubric 28.95 -> tests < 51.05 -> L >= 280 (56 worlds) -> 18x60 + 56x30 + 120 = 2,880 > 2,700 s; 45 worlds 291/516 = 56.4, final 38.2, 2,550 s (94%); 42 worlds 291/501 = 58.1, final 39.0, 2,460 s (91%) | CONFIRMED | recomputed | — |
| 3.3 | F3 plan (Q24 a "~42-45 worlds") vs adopted C2 (a) predicted final <= 35 and (d) verifier worst case <= 90% of limit (2,430 s) | WRONG (conflict) | 42-45 worlds at 30 s give 2,460-2,550 s (> 2,430) and predicted final 38.2-39.0 (> 35); max at 30 s is 41 worlds (2,430 s), final 39.3 at judge mid 20 | v2 F3: DESIGN v2 must meet C2 (a)+(d), e.g. judge mid <= 15 and ~48 worlds at <= 25 s/world (2,400 s; tests 291/531 = 54.8; final ~34.9); else park (Q24 "a miss -> park") |

## Check 4 — fit with Ayush's 25 answers

| # | Item | Verdict | Evidence | Fix |
|---|---|---|---|---|
| 4.1 | Q6: B-N2/N3/N4 "Ayush GUI, Batch 4" | WRONG | ANS Q6 verbatim: steps after all questions, "i will do the restart if needed after the session upgrade"; ANS:33 | v2: after Batch 4, from `DOCKER_STEPS.md`; master `docker info` check after |
| 4.2 | Q12: C0 snapshot `_COMMON_RULES_v5_g36_snapshot.md` | WRONG | ANS Q12 names `*_v3.6_snapshot.md` | v2: `_COMMON_RULES_v5_v3.6_snapshot.md` (+ PV4 snapshot) |
| 4.3 | Q14: Ayush asks Aditya Jain and Anjali Kumari | WRONG (missing) | grep of v1: no name, no item | v2 new D6 (no dependency for D4) |
| 4.4 | Q17: REPORT line + macOS notification on LIMIT | WRONG (missing) | v1 E1 has no notification (only E2 "optional osascript") | v2 E1: `osascript` notification, not optional |
| 4.5 | Q8 N5 "master after Ayush OK, all opencode stopped" | WRONG | the master is an opencode session (pid 50127); opencode.db in use (modified 00:26) | v2 B-N5: Ayush in Terminal.app, steps in DOCKER_STEPS.md |
| 4.6 | Q1, Q3, Q18, Q22, Q23, Q24 open-question text in A7, E1, F1-F3, sec 6-8 | CONFIRMED (folded) | ANS rows | v2 writes only the chosen branch |
| 4.7 | Q2, Q4, Q5, Q7, Q9-Q11, Q13, Q15, Q16, Q19-Q21, Q25 | CONFIRMED | plan text matches option a | — |

## Check 5 — fit with current rules

| # | Item | Verdict | Evidence | Fix |
|---|---|---|---|---|
| 5.1 | C1 gate-50 site list (intake:104, CR:61, LR:210, LR:89, CR:49, KN:118, AP, PV4 stage 6/7) | WRONG (incomplete) | grep 00:31: 20 live lines in 11 files; missed INDEX.md:6, LR:1, P2_build_v5.md:66, P9_harden_from_results_v4.md:67, GOALS.md:18, :34, state.json:126, tools/lever_dose.md:3, PV4:28, :56 (CHANGELOG:48 lists GOALS, state.json, lever_dose.md as v3.6 sites) | v2 C1 full list |
| 5.2 | A7 regrade exception sites CR:65-66, KN:119, LR:215 | WRONG (incomplete) | PV4:12 (decision 5), :59, :99 also ban regrade | v2 A7 adds PV4 lines |
| 5.3 | Regrade ban vs A7 | CONFIRMED | Q1 a = named exception | — |
| 5.4 | AP:51 (auto mode never edits templates/LEVER_RULES) vs Batch 1 | CONFIRMED | the upgrade runs in master mode after "proceed", not auto mode | — |
| 5.5 | C0 in-place edit precedent | CONFIRMED | CHANGELOG:48 (9 files edited in place for v3.6) | — |

## Check 6 — every step executable

| # | Item | Verdict | Evidence | Fix |
|---|---|---|---|---|
| 6.1 | A1 verify "dry case prints the prompt" | WRONG | issue.py:114-116 refuses before the dry-run branch :124-126, which prints `DRY RUN ok: would write ...`; HERE = tools/.. so a temp test needs tools/issue.py + board.json + registry/tasks.json copied | v2 A1 recipe |
| 6.2 | A2/G1 verify "prints gate ... False"; "regrade without --ayush-ok prints valid: False" | WRONG | :106 prints `MET`/`not met`; row (and `valid`) only exists with `--apply`, which writes the real scores.jsonl. Ran read-only: `intake.py --job district-heat-flex-procurement` -> 73.0/16.67/44.84 `MET`; sentinel job dir holds 80.95/0.0/40.48 (the 44.53 regrade is not in H/jobs) | v2: expect `not met` for district; non-apply mode prints the would-be row |
| 6.3 | A3 verify `status.py --help` | WRONG | no argparse; `--help` is a KeyError on tasks | v2: `status.py set <slug> zz=1` -> "bad field zz; allowed [...]" before any write |
| 6.4 | A4 "import `_package_run()` and call only that" | WRONG | :117 copies one run only (no task files, no pass_summary.json); one-task packager is `package()` :216, which rmtree's out_root/<task> (:229-230) | v2: `package()` into /tmp staging, back up Output_RFP, then copy |
| 6.5 | C1 verify "only snapshots + CHANGELOG" | WRONG | auto/plans/*.md, auto/runs/* and in-place "[v3.6 ...]" history tags always hit; pattern misses spaced "overall < 50" | v2 grep with spaced forms, excludes, `grep -v v3.7` -> empty |
| 6.6 | E1/G2 verify fake server + `exp1.py` | WRONG | `/tmp/R5-auto-*` gone (R5 LOG.md:7), exp1.py hard-codes `/tmp/R5-auto-1/auto_copy.py`; fake_oc.py never kept | v2: copy step before exp1; fake server as unit test in `MT/auto/tests/test_auto.py` |
| 6.7 | G2 "1 dry auto plan (smoketest PLAN.md)" | WRONG | auto.py has no dry mode (grep "dry" no hit); `MT/auto/smoketest/PLAN.md` spawns 2 real workers (subscription, no paid run) | v2 says it is a real run and its cost |
| 6.8 | B-N4 JSON `keepStorage` / `unused-for` | WRONG (legacy) | Docker docs build/cache/garbage-collection use `reservedSpace` / `keepDuration` | v2 + DOCKER_STEPS with legacy fallback |
| 6.9 | B-N7 pids 15335, 23171 | CONFIRMED (changed state) | `ps`: 23171 gone; 15335 alive = `opencode --port 53366 ... -s ses_ea5ff5f97ffe6WB1VzP4StPOw6` (8 h 38 m) | v2: close 15335 only after Ayush confirms |
| 6.10 | MT/auto/tests unittest green | COULD NOT CHECK | not run (read-only session; tests run at apply time) | — |
| 6.11 | B-S1..S8 apply steps | COULD NOT CHECK | apply-time only; R2A section anchors CONFIRMED | — |
| 6.12 | Docker engine version / GC key support | COULD NOT CHECK | no docker commands allowed; Docker Desktop 4.95.0 from Info.plist | DOCKER_STEPS fallback JSON |
| 6.13 | R2 machine numbers beyond memory, daemon.json, ps, db size | COULD NOT CHECK | would need system commands outside read-only scope | left [UNVERIFIED] |
| 6.14 | QL hardness.md claim texts beyond claims.csv counts | COULD NOT CHECK | only counts and wrong ids checked | — |

## Check 7 — order and dependencies

| # | Item | Verdict | Evidence | Fix |
|---|---|---|---|---|
| 7.1 | E1 header "Batch 2 ... together with A1-A4" vs batch table (A1-A4 in Batch 1) | WRONG | v1:198 vs v1:260 | v2: E-code-1 does A1-A4 in Batch 1, stops at G1; master continues the same session (task_id) for E1 in Batch 2 |
| 7.2 | A2 "Depends Q1, Q9"; A3 "Depends none" | WRONG | A2's tree-sha refusal reads the A3 `tree_sha` field | v2: A2 depends on A3 |
| 7.3 | Batch 2 E1 then E2 serial; Batch 3 may start at RESUME | CONFIRMED | v1:261-266; Q21 a | — |
| 7.4 | B-N2..N4 inside Batch 4 | WRONG | Q6 (see 4.1) | v2 row "after 4" |

## Check 8 — gaps

| # | Item | Verdict | Evidence | Fix |
|---|---|---|---|---|
| 8.1 | `tree_sha` in registry | WRONG (gap) | no `tree_sha` key in `MT/registry/tasks.json`; 8ca9c267f59b not in tasks.json or board.json; A2 would refuse every gate run | v2 A3: freeze writes `tree_sha`; backfill cold-chain 8ca9c267f59b in Batch 1; A2 prints a clear refusal when empty |
| 8.2 | Metered (8 GiB) run before B-N2 | WRONG (gap) | R2F:53: metered + 1 heavy + harness needs ~13-14 GiB; B-N2 now after Batch 4, F2 runs at RESUME | v2: metered runs with no other Docker-heavy job until N2 |
| 8.3 | Sentinel REGRADE_REPORT path | CONFIRMED (path added) | `T/master_chat_work/20261028_sentinel-policy-recompute/regrade_r13_188771e/REGRADE_REPORT.md:18, :118-119` | v2 A4 |
| 8.4 | C0 counts "13 templates / 4" | CONFIRMED (note) | `grep -l` counts include CHANGELOG.md (12 + 3 templates) | v2 note |

Totals: WRONG 28 (1.1, 1.5, 1.6, 1.8, 1.10, 1.13, 1.14, 3.3, 4.1-4.5, 5.1, 5.2, 6.1-6.8, 7.1, 7.2, 7.4, 8.1, 8.2); COULD NOT CHECK 6 (2.7, 6.10-6.14).

## Lessons for the master
1. Six of v1's verify lines could not pass as written: when a plan states expected output, read the code path that prints it (dry-run branch, `--apply` gate, argparse).
2. "Grep shows only X" checks must exclude history (runs, plans, snapshots) and use every spacing of the literal.
3. Research scripts and fake servers in /tmp vanish; a plan's verify must say how to recreate them or put them in the repo's tests.
4. A REPORT "Needs Ayush" line is a question, not an OK; cite the answer row.
5. When a task fix (F3) and a new rule bar (C2) land in the same plan, check one against the other before asking Ayush.
