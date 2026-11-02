# QL round 1 triage: metered-usage-rating-pipeline (fc64da5)

Bytes triaged: Tasks_INPUT tree 88bd0a39d67b (= Output_RFP). Only diff vs BUNDLE / QC v4 copy (bbc865f36130) is task.toml:9 authors line. Kit HEAD 5574d77e.
Abbreviations: kit 01..05/FC = `Terminal_2.0_Harbor_Harness/Input_Bundle_QC/0N_*.md` / `Final_checklist.md`; T = Tasks_INPUT bundle; v4 = `QC/reports/metered-usage-rating-pipeline/v4.md`; RUN = `_runs/20261031/metered-usage-rating-pipeline/ql1-20261031T1057`; COMMON = `_COMMON_RULES_v5.md`; LEVER = `LEVER_RULES_v3.md`; PB = `QC_FIX_PLAYBOOK_v3.md`.

| id | label | kit rule + wording file:line | evidence file:line | reproduced? | precedent | reason |
|---|---|---|---|---|---|---|
| F-1 "The verifier cannot finish inside its 2700 s timeout: unlocked caches plus rewardkit's 8 concurrent check threads regenerate every fresh month several times." | REAL | AL-17 kit 05:74 "verifier timeout plausible for what test.sh does"; FC:390 "Every one of the five oracle runs must read exactly 1.000"; FC:400 "An errored trial is not a score" | T tests/test_output.py:1041-1045, 1048-1057, 1060-1070, 1073-1096, 1120-1133, 1243-1246, 1258-1261 check-then-set with no lock; only lock :1209 used at :1195; tests/test.sh:10 no concurrency flag; tests/Dockerfile:5 rewardkit 0.2.1 (`rewardkit --help`: default 8); task.toml:21 timeout 2700 | Duplicate generation YES (RUN/logs/last_ls.txt: hidden 8 runs, long-1/2/3 4 each, ladder-1 5, ladder-2/3/4 8 each, every other label 1). Timeout NO on our machine: 1819.6 s, reward 1.0 | v4:279 AL-17 PASS on Step 10 timings (v4:349-356, 3 reduced oracle runs, 1509-1979 s); not KEPT | Line unchanged since v4, but FC:390/:400 are live lines v4 missed: v4 never looked at the concurrency, and our run used 67.4% of the limit with each long-card month run up to 8x; a machine ~1.5x slower times out, as QL saw 5 times. Same rewardkit 0.2.1 in every run, so the difference is machine speed and load (INFERRED). |
| F-2 "The 15 s wall limit per program run is too tight for the long and long-card months. The oracle's correct program loses 56 of 422 test weight on a loaded machine." | PARTLY | TS-11 kit 03:41 "timing margins tight enough to lose on a slow machine"; COMMON:58 limit "at least 3x the oracle's measured time on the hidden inputs"; LEVER 1C:90 (e) reference <= 1/4 of stated limit | T tests/test_output.py:29 `RUN_LIMIT_SEC = 15`, :1199; environment/data/rating_contract.md:48-49 "finishes within 15 seconds" | Oracle loss NOT reproduced (verifier reward 1.0; worst oracle run 6.35 s). Thin margin YES: worst serial 4.77 s (3.1x), one busy core 4.03 s (3.7x), both cores busy 6.35 s (2.4x) | v4:195 TS-11 PASS "no randomness"; v4:326 lists the 15 s checks | The "slow machine" clause of kit 03:41 is a live line v4's reason misses. Margin meets COMMON:58 only in serial / one-core-busy cases, fails LEVER (e) 1/4 everywhere (4.77 > 3.75). QL's 56-point loss came from a starved host (his user time 3.3-4.0 s matches ours, wall 9-24.6 s) (INFERRED). |
| M-1 "The recorded task.toml digest is stale." | REAL | AL-18 kit 05:75 "nothing mentions ... numbers that do not match the actual bundle"; DS-22 kit 02:78 "TRUTH.md describes the bundle that actually shipped" | T solution/TRUTH.md:198 `bd6b83a7...`; `shasum -a 256 T/task.toml` = 4ac8cf6b...; other 8 digests match | YES (shasum) | v4:170 DS-22 PASS, digest matched the v4 copy | New since v4: task.toml:9 authors line changed after QC v4, so not a carry-over. |
| M-2 "instruction.md L28 says the program 'is run again on this month's files' and each document 'is graded whole', but the shipped month is graded from /app/out as delivered, and normalized.jsonl is graded in field slices." | PARTLY | TS-19 kit 03:50 "every promise the instruction makes must be graded by something" | T instruction.md:28; tests/test_output.py:1296-1299 visible tier = `_expected("shipped", ...)`, OUT_DIR; every `_run` uses a fresh month (:1410-1412, :1480-1488, :1496); :1313-1316 slice keys; long/long-card documents compared whole (:1404-1405) | YES (code read) | v4:203/:300 TS-19 PASS covered learnability and missing input only | "run again on this month's files" is a promise no check grades: REAL. "graded whole" holds for fresh months (whole-document compare), so the slice part is a wording mismatch on the shipped month only. |
| W-1 "113 registered checks, over the 35 cap." | FALSE POSITIVE (carry-over) | TS-23 kit 03:62 "at most 35 (warn)" | T tests/test_output.py:2097-2210 | count true | KEPT.md G03-2; QC_RULINGS:137-138; PB:41 KEEP warn, no cap; v4:24/:40 | Unchanged since v4 where it is KEPT; no live kit line beyond the warn. |
| W-2 "37.9% of positive test weight rides on fresh-month scale that nothing the agent can read states." | FALSE POSITIVE (carry-over) | TS-20 kit 03:51 (weight ordering); CL-5 FC:492 (hidden conventions) | T rating_contract.md:48-49 states the run limit; instruction.md:28 states fresh months; test_output.py:30-34 shapes | share true (160/422) | v4:204 TS-20 PASS, v4:255 CL-5 PASS; QC_RULINGS:66 (state run caps: done); PB:24 never describe the hidden distribution | TS-20 grades weight order, not share; CL-5 covers conventions, not data size; unchanged lines. |
| W-3 "n2 needs the delivered document's value, but the judge sees only the trajectory." | FALSE POSITIVE (carry-over) | JD-6 kit 04:72 "decidable" | T tests/judge.toml:154-167, :5; a4 judge_response.txt:46-49 decided n2 from documents shown in the trajectory | n/a | v4:227 JD-6 PASS, unchanged | A negative criterion fires only on evidence it can see; it was decided in the paid run. |
| W-4 "16 positive criteria (48 of 50) prescribe exact verification acts that copy solve.sh's self-check." | FALSE POSITIVE (carry-over) | JD-9 kit 04:86 "Process focus ... verification habits ... Prefer trajectory/state_change criteria" | T tests/judge.toml:13-120, :208-289; test.sh:8 `chmod -R go-rwx /tests`; task.toml:23 separate | n/a | v4:230 JD-9 PASS, unchanged | JD-9 asks for process criteria; the 1000-tier/link wording sits in judge.toml, which the agent never sees. |
| W-5 "n4 penalises opening paths that do not exist in the agent container." | FALSE POSITIVE (carry-over) | JD-11 kit 04:88 "reading or influencing the grader" | T tests/judge.toml:180-192; task.toml:23; a4 judge_response.txt:54-57 | n/a | v4:232 JD-11 PASS, unchanged | The attempt to open grader paths is the cheat this negative targets, whether or not the path exists. |

## Measurements
All in Docker on scratch copy RUN/scratch/run (exe_copy.py plain), `--cpus 2 --memory 8g`, host Apple M1 Max, dockfree START=yes each time, nothing else running.
- Oracle verifier (rewardkit 0.2.1, default 8 concurrent checks): StartedAt 05:31:17.69Z, FinishedAt 06:01:37.34Z, exit 0, **1819.6 s = 67.4% of 2700**, reward 1.0 (RUN/logs/verifier_logs/reward.json). Peak mem 5.96 GiB, CPU 60-200% (RUN/logs/mon.log).
- Program runs per month (RUN/logs/last_ls.txt, one `extract-<label>` dir per run, never deleted): hidden 8, long-1 4, long-2 4, long-3 4, ladder-1 5, ladder-2 8, ladder-3 8, ladder-4 8, all others 1. Each extra run implies one extra generation of that month (unlocked `_cached_run`, :1243-1246). Duplicate generation is real. Headroom to 2700 s: 1.48x.
- F-2, oracle `python3 -I solution/solve.py` on months built by test code (wall / user s; RUN/logs/f2_*.txt):

| month | serial | one generator running | two generators running |
|---|---|---|---|
| long_1 | 4.77 / 3.95 | 2.85 / 2.70 | 4.76 / 3.02 |
| long_2 | 3.93 / 3.77 | 2.90 / 2.75 | 5.19 / 3.30 |
| long_3 | 3.76 / 3.61 | 3.23 / 3.13 | 5.40 / 3.46 |
| ladder_1 | 4.52 / 4.21 | 3.71 / 3.49 | 5.68 / 3.57 |
| ladder_2 | 4.29 / 4.06 | 3.91 / 3.71 | 6.00 / 3.84 |
| ladder_3 | 4.04 / 3.84 | 4.03 / 3.86 | **6.35 / 4.10** |
| ladder_4 | 3.83 / 3.62 | 3.74 / 3.58 | 5.54 / 3.51 |

- a4 program (`gate_run_a4/.../app/out/transform.py`, cap 120 s): TIMEOUT on all 7 months serial (120.05-120.12 s wall, 119-120 s user, CPU-bound, 0 documents); TIMEOUT on long_1 with one generator running. Its shipped-month normalized.jsonl equals the oracle's (15154 lines).
- In the verifier, checks share one Python process (one core busy with generation), so "one generator running" is the closest model of a real program run (INFERRED).

## Directions for P12
```
F-1 | FIX | row AL-17 | tests/test_output.py:1026-1133,1243-1246,1258-1261: unguarded check-then-set caches -> guard each cache key so every fresh month, its expected documents and its program run are built exactly once; then record verifier wall / 2700 in TRUTH.md | levers: L2=none | compensation: none
F-2 | FIX | row TS-11 | tests/test_output.py:29 RUN_LIMIT_SEC 15 -> 20, with descriptions :1877-2057, environment/data/rating_contract.md:49 and solution/TRUTH.md:48,154,160,266 changed to 20 in the same edit (needs F-1 first) | levers: L2=easier (only programs between 15 and 20 s; a4 unaffected) | compensation: none
M-1 | FIX | row DS-22 | solution/TRUTH.md:198: task.toml digest bd6b83a7... -> sha256 of shipped task.toml, recomputed by script after all other edits (all nine digests) | levers: none | compensation: none
M-2 | FIX | row TS-19 | instruction.md:28: "your program is run again on this month's files and on fresh extracts" -> this month's documents are graded as delivered in /app/out; the program is run again on fresh extracts of other months | levers: L2=none | compensation: none
```
W-1..W-5: no direction (carry-over). If the master prefers option (c) for F-2, drop the F-2 line and keep F-1; margin then 3.1x serial, still below the 1/4 rule.

## Score impact
a4 paid run: tests 62.09 (262/422), rubric 26.0, final 44.05 = (62.09 + 26.0) / 2. All 160 lost test points are TIMEOUT (100% of loss, 37.9% of test weight). The a4 program needs more than 120 s on every long/long-card month, so no limit up to 120 s changes its result.

| option | new limit / month sizes | oracle worst as share of limit | a4 measured vs new limit | pred. a4 tests / final | timeout share of lost points | easier? |
|---|---|---|---|---|---|---|
| (a) raise limit + contract line together (with F-1) | 20 s (3x of 6.35 = 19.05); 26 s if the 1/4 rule must hold under two busy cores | 6.35/20 = 0.32 (<= 1/3); 4.77/20 = 0.24 serial | >120 s vs 20 s: still TIMEOUT x7 | 62.09 / 44.05 | 100% | slightly (15-20 s programs now pass) |
| (b) shrink long/long-card months, keep 15 s | about 0.75x each LONG_SHAPES/LADDER_SHAPES entry and LADDER_TIERS 50000 -> ~37500 so worst oracle <= 5 s (INFERRED linear scaling) | ~4.8/15 = 0.32 (INFERRED) | still >60 s at 0.75x (INFERRED from >120 s) -> TIMEOUT | 62.09 / 44.05 (INFERRED) | 100% (INFERRED) | yes; PB:24 never shrink hidden data |
| (c) keep 15 s, fix only F-1 | 15 s, sizes unchanged | 4.77/15 = 0.32 serial; 4.03/15 = 0.27 one generator; 6.35/15 = 0.42 two generators | >120 s: TIMEOUT x7 | 62.09 / 44.05 | 100% | no |

All three keep a4 losing; (b) makes the task easier and breaks a playbook rule, (a) eases it slightly, (c) does not. F-1 (per-key guard or pre-build) changes no score: the same seed gives the same bytes, and the program timer starts only after `_RUN_LOCK` is taken (:1195-1199); nop/stub would finish with a reward instead of erroring. No honest option moves a4's final; it stays 44.05, above the final < 40 gate as pushed.

## Reply notes
- F-1: Agreed: the caches at test_output.py:1041-1070 and :1243-1261 are filled without a guard, and our oracle verifier ran each long-card month up to 8 times and took 1819.6 s of 2700 s, so a slower machine times out; we will build each month once (kit 05:74, FC:390).
- F-2: The margin is thinner than our 1/4 rule (worst oracle run 6.35 s against 15 s), so we will raise the limit and the contract line together; the 56-point oracle loss did not reproduce here (reward 1.0), and we read it as host load on your machine.
- M-1: Agreed, the digest went stale when the authors line in task.toml changed after QC; we will recompute all nine digests.
- M-2: Agreed on the first half: no check re-runs the program on the shipped month, so we will reword instruction.md:28 to say this month is graded as delivered in /app/out; fresh months are already compared whole (test_output.py:1404-1405).
- W-1: The 113 checks are a recorded warning kept at the last QC (kit 03:62 is a warn with no hard cap); no change.
- W-2: The 15 s cap is stated in rating_contract.md:48-49 and fresh months in instruction.md:28; TS-20 (kit 03:51) grades weight order, not share, and we do not describe hidden data size, so no change.
- W-3: n2 only fires when the delivered figure is visible and differs, and the paid-run judge decided it from what the transcript showed (kit 04:72), so no change.
- W-4: The criteria reward checking habits, which kit 04:86 asks for, and their wording is in judge.toml, which the agent cannot read (test.sh:8), so no change.
- W-5: Trying to open grader paths is the cheat n4 targets (kit 04:88), whether or not the path exists in that container, so no change.

## Freeze impact
- F-1: tests/test_output.py -> new QC recheck and new paid run (COMMON:29; LEVER 6:236, :241).
- F-2 (a): tests/test_output.py:29 and :1877-2057, environment/data/rating_contract.md:49, solution/TRUTH.md:48,154,160,266 -> contract and tests change: new QC recheck and new paid run.
- M-1: solution/TRUTH.md:189-199 only; recompute after every other edit.
- M-2: instruction.md:28 -> new QC recheck and new paid run.
- Any of these voids a4 as the gate run (LEVER 6:236); a4 itself is not a baseline anyway because its loss is timeouts (LEVER 6:244).

## Lessons for the master
- Test caches must be guarded per key because rewardkit runs 8 checks at once | template_change: _COMMON_RULES_v5.md:58 add "every cached fresh month is built once (per-key guard or pre-build)"
- Record verifier wall as container start-to-finish over timeout_sec plus runs per month, not trial times | template_change: _COMMON_RULES_v5.md:49 (d) add "measured from verifier container StartedAt/FinishedAt with shipped concurrency"
- Measure the oracle per-run limit with both cores busy, not only serial | template_change: _COMMON_RULES_v5.md:58 add "worst of serial and both-cores-busy runs"
- Post-QC metadata edits (authors) stale TRUTH.md digests | template_change: LEVER_RULES_v3.md:241 add "recompute TRUTH digests after any post-QC edit, task.toml included"
- An instruction promise of a rerun on the shipped month needs a check | no change: kit 03:50 TS-19 already says it; QC v4 applied only the learnability half
