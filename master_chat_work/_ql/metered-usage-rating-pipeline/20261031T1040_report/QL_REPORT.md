# QL report pasted by Ayush, 31 Oct 2026 10:40 IST (QL = Sugam; reviewer "Sisyphus"). Tables condensed by the master; every claim, number, file:line and quote kept as written. Ids F-1, F-2, M-1, M-2, W-1..W-5 as in the report.

QC Report: metered-usage-rating-pipeline
Verdict: ❌ FAIL (2 fails, 2 minors, 5 warns)

Field	Value
Tasker	Shubhi_Goyal
Task	metered-usage-rating-pipeline
Bundle	/Users/apple/Desktop/Terminal Tasks/Anubis_Tasks_Samples/Pass@1_New/Sugam_Agrawal/Shubhi_Goyal/metered-usage-rating-pipeline (task root one level down, in metered-usage-rating-pipeline/)
Reviewer	Sisyphus
Date	2026-10-30
Scope	The five root entries (environment/, instruction.md, solution/, task.toml, tests/). trajectories/ and output/ were excluded by operator instruction.
Step 10 counts	Set by the operator: oracle 2 runs (not 5), nop 1, stub 1, plus step10.py's default owner-only run. Step 10 is not marked down for running fewer than 5 oracles.

1. Task summary
A cloud team bills metered usage every month. Five regional collectors each write their own file in their own format. The September 2026 extract (month "2026-09") sits in /app/data, and /app/data is to be treated as read-only.
(Files: collector_central.csv, collector_east.tsv, collector_north.jsonl, collector_south.txt, collector_west.log, accounts.csv 2,405 accounts, plan_changes.log 2,208, rate_card.json, commitments.xml, products.ini, collector_controls.json, rating_contract.md 230 lines.) The five collector files hold 3,232 records each.
The agent must write one reusable, standard-library-only program at /app/out/transform.py, run as python3 /app/out/transform.py --input <dir> --output <dir>; any month laid out like this one, any working directory; deterministic; every run within 15 seconds (contract L48-49); exit non-zero with `missing input: <file name>` for the first missing input in list order; `control mismatch: <file name>` on record-count disagreement. Rules: dedupe; quarantine in order timestamp_outside_month, unknown_account, unknown_product, units_not_integer; plan/segment changes at timestamps; tier counter per billing group and product; half-even cents; 0.50 floor-and-reshare commitment credit; same for true-up. Fourteen files in /app/out. Final reply lists files and checks run.
Oracle on shipped month: 15,154 accepted lines; charge 598740.61; credit 126305.23; true_up 0.00; net 472435.38.
Task settings: agent timeout 7200 s; Data Processing; expert 480 min, junior 1440 min; verifier timeout 2700 s; 2 CPUs, 8192 MB, no network.

Grading layout
Deterministic tests (tests/test_output.py, 2,210 lines, 113 checks: 112 positive totalling 422, plus 1 negative at -5): shipped inputs embedded zlib+base64; fresh months from gen_month HIDDEN_SEED = 58213, expected from in-file ref_compute. Visible 28 x 3 = 84 (documents left in /app/out). Hidden-month 28 x 5 = 140 (renamed folder, foreign cwd, runs as nobody under setpriv). Mutation 13. Refusals 21. determinism 3, transform_exists 1. Scale: long_1..3 (48), ladder_1..4 (112, 50,000-tier rate cards). RUN_LIMIT_SEC = 15. Negative negative_hardcoded_sample_answers (-5).
Judge (tests/judge.toml, 23 binary criteria, openai/gpt-5.6-sol, trajectory only): 18 positive = 50; 5 negative = 19; 16 positive are verification acts at w3 (b1-b9, b11-b17), b10/b18 reply duties w1; n1-n5 (-3, -5, -3, -5, -3). Reward 0.5/422 tests + 0.5/50 judge.
Oracle: solve.sh copies solve.py (380 lines) to /app/out/transform.py, runs it, then 21-step self-check.

How the issues were established: four QC scripts; all five gate files read; local harness importing test_output.py with stub rewardkit, every check run serially against oracle /app/out and solve.py; long and long-card months generated locally from the test code and solve.py timed; Step 10 via hq (job j296, step10.py) on exe_copy.py copies; containers inspected (/tmp rerun folders, docker stats, docker events); every fail confirmed twice; bundle unedited.

2. Issue index
F-1 ❌ Tests / task.toml (AL-17, AL-5, DS-15, TS-30, Step 10): The verifier cannot finish inside its 2700 s timeout: unlocked caches plus rewardkit's 8 concurrent check threads regenerate every fresh month several times. All five Step 10 runs errored with no reward.
F-2 ❌ Tests / contract (TS-11, AL-5, DS-15): The 15 s wall limit per program run is too tight for the long and long-card months. The oracle's correct program loses 56 of 422 test weight on a loaded machine.
M-1 🟡 TRUTH.md (AL-18, DS-22): The recorded task.toml digest is stale.
M-2 🟡 Instruction / tests (TS-19): instruction.md L28 says the program "is run again on this month's files" and each document "is graded whole", but the shipped month is graded from /app/out as delivered, and normalized.jsonl is graded in field slices.
W-1 ⚠️ Tests (TS-23): 113 registered checks, over the 35 cap.
W-2 ⚠️ Tests / contract (TS-20, CL-5): 37.9% of positive test weight rides on fresh-month scale that nothing the agent can read states.
W-3 ⚠️ Judge (JD-6): n2 needs the delivered document's value, but the judge sees only the trajectory.
W-4 ⚠️ Judge (JD-9): 16 positive criteria (48 of 50) prescribe exact verification acts that copy solve.sh's self-check.
W-5 ⚠️ Judge (JD-11): n4 penalises opening paths that do not exist in the agent container.
Gates: tests_qc warn W-1; Gate 02 fail F-1,F-2 (DS-15), minor M-1 (DS-22); Gate 03 fail F-1 (TS-30), F-2 (TS-11), minor M-2 (TS-19), warns W-1 (TS-23), W-2 (TS-20); Gate 04 warns W-3,W-4,W-5; Gate 05 fail F-1 (AL-17/AL-5), F-2 (AL-5), minor M-1 (AL-18); Step 10 fail F-1.

3. Fails
F-1. The verifier cannot finish inside its own 2700 s timeout, so no Step 10 run produced a reward.
rewardkit 0.2.1 runs up to 8 programmatic checks at once, each in a thread (--max-concurrent-programmatic default 8, dispatched via asyncio.to_thread inside a TaskGroup). tests/test_output.py fills every month cache and run cache with unlocked check-then-set code. When several checks need the same month at the same moment, each thread finds the cache empty and generates, reference-computes and runs that month itself. The only lock in the file guards Popen. Long ~70 s, long-card ~125 s to generate serially on their machine. Serial local harness of 113 checks finished in 631.6 s.
task.toml:22 timeout_sec = 2700.0. Unlocked caches: L1041-1044 _hidden_files; L1056 _long_files; L1068 _ladder_files; L1243-1245 _cached_run; L1260 _expected; also _tier_scaled_files (L1095), _small_commitment_files (L1124), _near_base_files (L1132). Only lock L1209 _RUN_LOCK used at L1195 around the program run. _cached_run calls files_fn() before _run checks PROGRAM.is_file() (L1192), so nop and stub also pay full month generation.
Step 10 evidence (job dir /tmp/step10.20261030-163853.60638/jobs): oracle-1 11:10:40-11:56:55 VerifierTimeoutError; oracle-2 11:58:57-12:45:00 VerifierTimeoutError; nop-1 12:45:26-12:59:44 RewardFileNotFoundError, test-stdout 0 bytes; stub-1 13:00:44-13:46:17 VerifierTimeoutError, exit 137; owner-only-1 13:48:06-14:34:04 VerifierTimeoutError, exit 137. step10.py: all five ERRORED, elapsed 12326 s.
In-container: oracle-1 /tmp held 8 extract-hidden / 8 reports-hidden folders (one cached hidden month generated and run 8 times, created 11:13-11:14Z), 4 extract-long-1 (11:39:15-11:40:44Z), 4 extract-long-2 (11:41:40-11:41:47Z), no long-3, no ladder before kill. CPU ~100-105% (one core), memory 2.0-2.4 GiB. stub-1 test-stdout 8224 bytes, 72 completed checks, eight distinct hidden output folders; memory 3.63 -> 4.08 GiB of 6.52 GiB. owner-only-1 at 45 min: 8 extract-hidden, 4 long-1, 4 long-2, peak 3.22 GiB.
Impact: no run can produce a score; owner-only cannot confirm 0600 case (TS-30); every agent trial would end in verifier timeout.
Fix: guard every _CACHE fill with a per-key lock, or build every fresh month once before the checks start (_hidden_files, _long_files, _ladder_files, _tier_scaled_files, _small_commitment_files, _near_base_files, _cached_run, _expected). Measure verifier wall time on the oracle, set [verifier] timeout_sec with headroom, re-run whole Step 10.

F-2. The 15-second wall limit per program run leaves the oracle too little margin on the long and long-card months.
Every program run is killed after 15 s wall. Long months (long_1..3) and long-card months (ladder_1..4) are 4-5x shipped record count, parent chains ~9,000-10,000 deep, long-card 50,000 tiers per product. Oracle needs ~4-5 s CPU; wall time swings with load and concurrent month generation (F-1). tests/test_output.py L29 RUN_LIMIT_SEC = 15; L1199 proc.communicate(timeout=RUN_LIMIT_SEC); L1396 message. rating_contract.md:48-49 "Every run of the program finishes within 15 seconds." Each long-card month 8 checks depending on one run (_check_ladder_finishes, _check_ladder_document): one slow run costs 18-24 weight.
Evidence: serial local run of 113 checks vs oracle /app/out and solve.py: weighted score 366 / 422 = 0.8673, elapsed 631.6; every miss in ladder_3_* and ladder_4_* (16 checks, 56 weight). Direct timings of python3 -I solution/solve.py (rc 0): long_1 61,459 lines depth 9,166 18.00 s; long_3 70,927 / 10,026 18.87 s, run B 9.05 s real 3.33 s user; ladder_1 61,502 / 9,195 17.69 s; ladder_3 70,972 / 10,007 24.58 s, run B 13.39 s real 3.97 s user. In oracle-1 verifier container each long-month run ~5-6 s.
Impact: oracle pass depends on machine load; tests not deterministic for a correct solution; up to 160/422 (37.9%) behind small-margin runs.
Fix: shrink the long and long-card months, or raise the limit in rating_contract.md and RUN_LIMIT_SEC together; oracle measured wall time in verifier container at most a third of the limit; generate months before the first timed run.

4. Minors
M-1. solution/TRUTH.md:198 task.toml: bd6b83a7b1c7450f6fae9576a345488ab20ed5f5374afbf1df2f9003ec3841a2; actual 4ac8cf6b95666e39c22baa533c4be81a54de735de47eb59d275484fa3bb86df0. Other eight digests match. Fix: recompute.
M-2. instruction.md:28 "Each output document is graded whole on fresh inputs, and only an exact match counts: your program is run again on this month's files and on fresh extracts of other months ..." vs tests: no check re-runs the program on the shipped month; visible checks read /app/out as delivered (test_output.py:1298-1299 `if tier == "visible": return _expected("shipped", _shipped_files), OUT_DIR`); normalized.jsonl graded in field slices _LINE_KEYS, _RATING_KEYS, _CREDIT_KEYS (L1313-1315); per-line net only in long/long-card whole-document checks. Impact: stale /app/out graded across 28 visible checks (84/422). Fix: re-run delivered program on shipped month from renamed folder, or reword L28.

5. Warns
W-1. tests_qc.py [A3] 113 checks; cap is 35 (warn). Registrations test_output.py:2097-2210. Suggest fold families.
W-2. 160/422 positive weight on 15 s runs over months far larger than shipped (accepted 61,459-70,972 vs 15,154; accounts 76,000-84,000 via LONG_SHAPES / LADDER_SHAPES L30-34; chain 9,166-10,026 vs 4; tiers 50,000 vs 3). Only statements: rating_contract.md:48-49 and instruction.md:28. Recursive walk hits recursion limit: 262/422 = 62.1%; linear tier scan too slow on 50,000 tiers: 310/422 = 73.5%. Scale reachable (iterative walk + bisect ~4-5 s CPU), so warn. Suggest stating upper bounds for records, accounts, chain depth, tier count next to the 15 s rule.
W-3. judge.toml:156-159 n2_states_document_figure_other_than_delivered (-5, critically_important) needs /app/out value; judge.toml:5 atif-trajectory only. Suggest restrict to figures the trajectory displays, or give judge /app/out.
W-4. b1-b9, b11-b17 (48/50) each pay one specific act mapping onto solve.sh's 21 self-check steps (e.g. b11 1000 tiers timed, b12 1000 parent links timed, b16 changed month quarantine count, b17 reordered records). 1000-tier/1000-link thresholds hint hidden scale (W-2). Suggest phrase as property verified.
W-5. judge.toml:182-185 n4_opens_verifier_paths (-5): task.toml:23 environment_mode = "separate", so /tests/ and /logs/verifier absent in agent container; penalises a probe attempt. Suggest keep only if intended, else retarget or lower to -3.

6. What to fix before resubmission
F-1 thread-safe _CACHE or pre-build months; measure verifier wall time; set timeout_sec with headroom. F-2 shrink months or raise limit (contract + RUN_LIMIT_SEC) so oracle verifier wall time <= 1/3 of the limit; keep generation out of timed windows. M-1 update digest. M-2 re-run shipped month or reword L28. W-1..W-5 show tasker; optional. Re-run Step 10 in full (5 oracles, nop, stub, owner-only): every oracle exactly 1.000, nop 0.000, owner-only 1.000; name which tests the stub's score came from.
