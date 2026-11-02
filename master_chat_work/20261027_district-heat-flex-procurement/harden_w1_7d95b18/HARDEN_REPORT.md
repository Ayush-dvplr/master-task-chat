# district-heat-flex-procurement: wave 1 hardening (board 7d95b18)

Status: DONE. Lever: P-3 (exact optimum on larger hidden procurement instances). P-4 was pre-tested and dropped (see below).
Session rename: `name_session.py 7d95b18` printed `codex: no match; opencode: ['ses_e841ead73ffehYZkJ4AEuw8B38']`; 7d95b18 not shown, not retried.
Fingerprints: GEN 976c166 and QC kit 5574d77eb9f22c207ba05fd8f9ac31d42ba45271 matched at start. Phase A: harness staged tests/ and environment/ and Tasks_INPUT were identical to BUNDLE before edits.

## The lever
The figure already exists: per event and region, the best portfolio (schema section 5, objective and constraints only) and its
`tied_portfolio_count` (section 8.4). Before this round the schema stated "An event-region has at most 8 sites with candidate
offers and at most 3 candidate offers per site", which handed over plain search; every hidden corpus stayed inside it.

New sentence (the only agent-visible change), `environment/data/schema.md:162-163`:
"A site has at most 3 candidate offers in an event. Each run of the program on an extract must finish within 120 seconds."
(the 120 s sentence was already there). No method words, no trap wording, no new quiet rule. instruction.md unchanged.

New hidden corpora (`tests/test_output.py`): `WIDE_SEEDS` :1404, `_wide_spec` :1413, `wide_root` :1464. Two seeded wide
extracts, 20 events each, every event-region 20 to 26 sites, 1 or 2 offers per site plus (95%) an identical copy of one, targets
60-110% of the reachable relief, relief ceilings 150-190% of it, 25% flat events; own RNG per event-region; fixed re-draw
constants `WIDE_BUMPS` keep each event-region under 150k reference nodes. Same offer/site/value distribution as the composed
generator; within every stated bound (`within_contract` now checks only 3 offers per site; old hidden seeds unchanged, verified).
Shipped data unchanged (it has no site with identical offers: 0 of 8794 site lanes; H1 has 14, H2 3).

New checks (each own weight, whole document, own corpus), registered `tests/test_output.py:2360-2367`:
| check | w | reads |
|---|---|---|
| wide_k_portfolios_feasible (k=0,1) | 3 | selected ids are distinct candidates, one per site, both ceilings every interval (feasibility separate from optimality) |
| wide_k_selection_match | 5 | candidate_offer_count + selected_offer_ids per event row, whole region files |
| wide_k_tie_decisions_match | 5 | policy_audit tie_decisions whole |
| wide_k_intervals_match | 3 | interval rows per event, whole |
Functions `wide_feasible` :2101, `wide_passes` :2135. Existing 50 checks byte-unchanged; no weight moved.
Reference: `solution/solve.py:268 choose_portfolio` and test reference `bounded` `tests/test_output.py:442` (independent code).
Old vs new solve.py byte-identical on all 22 old corpora (WORK/CMP_OLD_NEW.txt); solve.py == test reference on every family of
shipped, H1, H2, 19 cases, wide0, wide1 (WORK/CHECK_REF.txt).

## P-4 dropped
Docker pre-test (WORK/KILL_P4.txt): bundle solve.py, the probe-9 Opus program and the 8caff6e blind program all exit 1 and write
nothing when any of the 15 data files is missing, and write byte-identical files on rerun (PYTHONHASHSEED 1 vs 2). Both checks
would cost nobody, so no sentence and no check was added.

## Kill table (Docker, 2 CPUs, 4 GB, limit 120 s, 16 points per wide corpus)
| solver | wide0 s | wide1 s | exact | points kept /32 |
|---|---|---|---|---|
| reference (bundle solve.py) | 7.67 | 11.08 | yes | 32 |
| hour-by-hour greedy (cheapest per relief tick) | 0.54 | 1.03 | no | 6 (feasible only) |
| merit-order stacking | 0.50 | 1.02 | no | 6 |
| naive subset search (product over sites) | LATE | LATE | - | 0 |
| state DP over relief/recovery/segment levels | LATE | LATE | - | 0 |
| branch and bound, suffix bound (probe-9 shape) | LATE | LATE | - | 0 |
| B&B with best-first order, no merge | LATE | LATE | - | 0 |
| B&B with identical-offer merge, no order | LATE | LATE | - | 0 |
| DP plus bound cut | LATE | LATE | - | 0 |
| pre-wave oracle (plain search) | LATE | LATE | - | 0 |
| probe-9 Opus program | LATE | LATE | - | 0 |
| 8caff6e blind program | LATE | LATE | - | 0 |
Every generic solver loses >= 81% of the 32 lever points. Reference max 11.08 s = 9.2% of the limit (<= 1/4). Full tables with
the smaller e6/e10 regimes (where merge-only B&B and DP+bound were still exact inside the limit, hence the move to 20 events):
`WORK/KILL_TEST.md`.

## Counts and shares
58 checks: 55 positive = 205 points, 3 negatives (-13). Judge 12 criteria +27/-5 unchanged (rubric 37.04 on probe 9).
reward.toml: test_output 0.5/205 = 0.0024390243902439024, judge 0.5/27. Lever share 32/205 = 15.6%. Hidden, wide and mutated
checks 141/205 = 68.8%. Weight-1 only the 4 format checks. Stacking: `OUT/STACKING_CHECK.md` (hand-corrected TS-26 groups).

## Measured cost table (Docker, grade.py on bundle tests, sequential; WORK/COST_w1.txt)
| program | tests /205 | % |
|---|---|---|
| oracle (solve.py) | 205 | 100 |
| first write = all-but-one (pre-wave oracle, plain search) | 173 | 84.4 |
| probe-9 Opus program | 173 | 84.4 |
| 8caff6e blind program | 31 | 15.1 |
| greedy / merit order | 66 | 32.2 |
| naive, state DP, B&B (3 variants), DP+bound | 173 each | 84.4 |

## Gates
- PRECHECK last line: `PRECHECK CLEAN` (structure/instruction/tests/judge QC exit 0 warns 0; only WARN [A3] 58 checks cap 35; 0 IN17/G5 warns; EVIDENCE-MAP 3 rows). `OUT/precheck.log`.
- Validator: 40 passed, 0 failed, GATE PASS (`OUT/validate_bundle.txt`). xref_check: 48 entries, 0 findings.
- Docker gate block (manual chain from live-kit `exe_copy.py` copies, images w1env-dhfp / w1ver-dhfp; log `/tmp/opencode-logs/dh-w1-7d95b18/runs.log`):
  oracle x3 1.0 / 1.0 / 1.0 (solve 3-4 s, verifier 27-30 s); owner-only 1.0; nop 0.0; stub 0.0049 (1/205);
  forgery (writes the shipped answers) 0.2878 (59/205: visible families and format only). ALL_DONE 17:03:28.
- Tasks_INPUT: `cp -Rp` of BUNDLE (5 changed files: schema.md, TRUTH.md, solve.py, reward.toml, test_output.py); `diff -rq` empty.
- No `__pycache__`/.pyc in BUNDLE. Tree sha (sha256 over sorted relative paths + bytes): 8d04a5de5c67.

## Not run / deviations
- `harbor run` not used; the gate block ran the same steps by hand in Docker (env image, solve.sh as uid 1000, /app/out into the verifier image, tests/test.sh, reward.json), as in sentinel t3.
- During the e10 kill run (13:22) three other containers were running, over the max-2 rule; later jobs waited for a slot.
- The first cost run (two graders in one container) was discarded: the test reaper kills every uid-nobody process; rerun sequentially.
- No fresh blind read (master issues it).

## Lessons for the master
- A stated size bound ("at most 8 sites") was the hole: dropping it and widening hidden instances made the existing optimum a P-3 lever with no new rule.
- Twin offers make tie counts 2^k; any program that counts ties one at a time is late, so the separator is merging plus order plus bound together.
- Merge-only B&B and DP+bound were exact inside 120 s at 6-10 events; 20 events per corpus was needed. Size the hidden corpus against the strongest generic, not the naive one.
- Missing-file and rerun-identical P-4 checks bit no program here (all three exit 1, write nothing); pre-test P-4 before writing sentences.
- Never run two rewardkit graders in one container: the agent reaper kills the other grader's runs.
