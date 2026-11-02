# district-heat-flex-procurement: gate v3.6 harden (board dcd21a3)

Status: DONE. Lever: P-3, two more wide hidden event-region corpora (`wide_2`, `wide_3`) built by the existing generator family.
Session rename: `name_session.py dcd21a3` printed `codex: no match` / `opencode: ['ses_e80727fb1ffewGpUrQT8mR57aI']`. dcd21a3 was not in the list and I did not retry.
QC kit HEAD 5574d77eb9f22c207ba05fd8f9ac31d42ba45271 (expected). Phase A: the staged a10 copy equals BUNDLE except the task.toml `allowed_hosts` staging lines (tree 97fa1e920b44).

## Trajectory read-out (OUT/TRIP.md)
- a10 scored tests 173/205 = 84.39, rubric 4/24 = 16.67 and final 50.53. It lost only the 8 wide checks (32 points).
- Correction to master note 1: the loss kind is TIMEOUT, not WRONG. test-stdout.txt:41-50 reads `program run failed: timed out after 120 s`. The read-out tool labels a run with an empty first_difference WRONG by default.
- The TIMEOUT still counts under Law-1 v3.5: the limit is stated (schema.md:162-163), the shipped extract runs in about 1.2 s, and each corpus has its own program call.
- The agent wrote a lexicographic branch and bound (derive_report.py:429-519). It timed that program only up to 12 sites (step 38).

## Arithmetic
| | tests | rubric | final |
|---|---|---|---|
| a10 before | 173/205 = 84.39 | 16.67 | 50.53 |
| a10 program on the new tests (measured, Docker) | 173/237 = 73.00 | 16.67 (judge unchanged) | 44.83 predicted |

## Change (G7 diff: WORK/g36/G7_tests_diff.txt, hunks only these)
- `tests/test_output.py:1404` `WIDE_SEEDS` gains `EVAL_SEED % 99971 + 43` (7120, prefix W20) and `EVAL_SEED % 99961 + 53` (24943, prefix W23).
- `:1410-1412` `WIDE_BUMPS` gains entries for 7120 and 24943, taken from the node guard (budget 150k reference nodes per event-region, WORK/proto/g36_guard.py).
- `:2194-2235` new criteria `wide_2_*` ("third seeded wide season extract") and `wide_3_*` ("fourth ..."). Their bodies are the existing one-liners with K = 2 and 3. The TS-25 non-empty rule is inherited from `wide_feasible`.
- `:2414-2421` registrations: feasible w3, selection w5, tie_decisions w5, intervals w3, for each new corpus.
- `tests/reward.toml`: test_output 0.5/237 = 0.002109704641350211. The judge weight is unchanged.
- Byte checks (WORK/g36/b3/b3.log):
  - All 124 old functions are byte-identical.
  - The wide_0, wide_1, H1 and H2 corpora have the same digests as before.
  - The test reference equals solve.py on wide_2 and wide_3, all 9 files of each.
- Unchanged byte for byte: instruction.md, environment/ (docs and data), solve.py, solve.sh and judge.toml. TRUTH.md was regenerated last by WORK/w1_truth.py.

## Kill table (Docker, 4 GB, 2 CPU, 120 s per run; WORK/KILL_TEST.md gate36 section, raw WORK/proto/g36/dout/KILL36.txt)
| solver | wide2 | wide3 | new lever pts kept /32 | shipped fast |
|---|---|---|---|---|
| reference solve.py | 5.49 s EXACT | 6.41 s EXACT | 32 | yes (1.40 s) |
| a10 agent program | TIMEOUT | TIMEOUT | 0 | yes (1.18 s) |
| blinds ef9234c, d62d21c, 7dd7290 | TIMEOUT | TIMEOUT | 0 each | yes (1.1-1.4 s) |
| blind 8caff6e, probe-9, old plain search | TIMEOUT | TIMEOUT | 0 | yes |
| naive, bnb, bnb_ord, ref (merge only), ref3 (DP+bound) | TIMEOUT | TIMEOUT | 0 | yes (<= 2.36 s) |
| dp | TIMEOUT | CRASH (OOM 4 GB, 81 s) | 0 | yes |
| greedy, merit | WRONG (3/16) | WRONG (3/16) | 6 | yes |
Every solver loses at least 81% of the new lever points. The reference's slowest run is 6.41 s, 5.3% of the limit.

## Counts and shares
- 66 checks: 63 positive worth 237 points, plus 3 negatives (-13). TS-23 is a recorded warn (66 > 35, option A). Nothing was merged.
- Lever: 16 wide checks, 64/237 = 27.0%.
- The hidden, wide and mutated checks carry 173/237 = 73.0%.
- Judge: 11 criteria, +24/-5, unchanged.
- Stacking: OUT/STACKING_CHECK.md, STACKING PASS.

## Measured cost table (Docker, real tests with grade.py; WORK/COST_TABLE.md gate36 section, raw WORK/g36/cost/)
| program | tests /237 | % | lever loss kind |
|---|---|---|---|
| oracle solve.py | 237 | 100.0 | - |
| a10 agent program | 173 | 73.00 | TIMEOUT x16 |
| blind ef9234c / d62d21c / 7dd7290 | 173 / 173 / 173 | 73.00 each | TIMEOUT x16 |
| first write = all-but-one (old plain search, every other rule right) | 173 | 73.00 | TIMEOUT x16 |
| probe-9 Opus, naive, dp, bnb, bnb_ord, ref3 | 173 each | 73.00 | TIMEOUT |
| ref (identical offers merged, no order) | 189 | 79.75 | TIMEOUT on wide_0/1/2 |
| greedy, merit | 72 | 30.38 | WRONG |
| blind 8caff6e | 31 | 13.08 | TIMEOUT + older misreads |
- The merge-only solver ran wide_3 in about 120 s; it finished inside the limit in the grader run and was cut off in the kill run, so it sits right at the limit. It is still under 80, so it passes the blind bar.
- Single wrong readings: REENTRY 192, CHAIN1 182 and RELIEF 179 of 237 (WORK/p12/dout/TRAP_g36.txt).
- The slowest grader run took 490 s, against the 2700 s verifier timeout.

## Judge band (unchanged)
- Positive weight 24; the 7 probe criteria (R1-R4, R8-R10) carry 21 of it.
- a10 earned 9 positive points and lost 5 to R7, the false-claim negative. That gives 4/24 = 16.67, inside the 15-20 band.
- Predicted run: tests 73.0, rubric 16.7, final 44.8.

## Gates
- precheck.sh last line: `PRECHECK CLEAN`. The only warn is A3 (66 checks); there are 0 IN17 and 0 G5 warns. Log: OUT/precheck.log.
- QC scripts: structure, instruction, tests and judge all exit 0 (inside precheck).
- Validator: 40 passed, 0 failed, GATE PASS (OUT/validate_bundle.txt).
- xref_check: 48 entries, 0 findings.
- Docker gate block: copies built by the live kit's exe_copy.py (plain, `--owner-only`, `--stub`, and a forge copy); chain log /tmp/opencode-logs/dh-g36-dcd21a3/dchain-20261028T0849/runs.log, ALL_DONE 08:54:17.
  - oracle x3: 1.0 / 1.0 / 1.0
  - owner-only: 1.0
  - nop: 0.0
  - stub: 0.0042 (1/237)
  - forgery: 0.2489 (59/237)
- No `__pycache__` or .pyc files in BUNDLE. Tree sha: b18d48a1deda.
- Tasks_INPUT: `cp -Rp` of tests/test_output.py, tests/reward.toml and solution/TRUTH.md; `diff -rq` BUNDLE vs that copy is empty.

## Not run / deviations
- `harbor run` was not used. The gate block ran the same steps by hand in Docker (env image, solve.sh as uid 1000, /app/out into the verifier image, tests/test.sh), as in rounds w1 and p12. Scores are tests-only.
- No fresh blind reads and no judge run; the master queues those.
- The guard and the kill test used the bundle-equivalent generator in WORK/proto/g36/tsrc_g36.py; the same corpora are confirmed in the final tests by b3.log.

## Lessons for the master
- The read-out tool marks a TIMEOUT as WRONG when first_difference is empty; check the `[check]` message in test-stdout | template_change: tools/trajectory_readout.py kind classifier, match "timed out" in the check message
- Adding corpora from the same generator with their own streams and guard bumps moved tests 84.4 -> 73.0 with zero changes to docs or checks | no change: already the KNOWLEDGE T "add test" row
- The merge-only solver is borderline at 120 s on one corpus (189/237); the guard budget of 150k nodes leaves little margin for partial solvers | no change: still under the blind bar
