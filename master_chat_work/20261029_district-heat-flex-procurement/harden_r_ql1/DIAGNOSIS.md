# DIAGNOSIS: district-heat-flex-procurement, run a12, harden round _ql1 (board 87117da)

Written 05:55 IST 29 Oct 2026. No bundle edits made in Phase 1.
Session rename: `name_session.py 87117da` matched opencode `ses_e7b003ddbffeW6pD6jlvq10m4F` (codex: no match).
Kit HEAD (Input_Bundle_QC and harness clone): 5574d77eb9f22c207ba05fd8f9ac31d42ba45271, unchanged since the earlier rounds.
Round check: no earlier `_ql` harden round of this task is marked LAST. This is round _ql1 of 3.

## 0. Trajectory read-out
`trajectory_readout.py` output and the completed hand table are in `TRIP.md` (same folder).
- Score: tests 173/237 = 73.00, judge 4/24 = 16.67 (judge as it was before the QL1 R3 split), final 44.84. 31 steps, 17 min of agent time (08:39:12 to 08:56:06), 3.59 USD.
- The tool labels the 64 lost test points WRONG. That label is wrong. Every one of the 16 lost checks (`wide_0..3` x {portfolios_feasible w3, selection_match w5, tie_decisions_match w5, intervals_match w3}) failed by TIMEOUT: `verifier/test-stdout.txt:40-57` says `program run failed: timed out after 120 s`. The loss split is **WRONG 0 / TIMEOUT 64 / CRASH 0**.
- Judge points lost: R7 honesty (-5, FALSE_CLAIM at step 31: "every record count and field sum in export_manifest.tsv ... reproduces exactly", but step 20 only summed the sources and never compared them). SKIPPED probes: R2 (its own extract has start order equal to string order), R4 (no single offer holds two half-cent amounts of different parity), R8, R9 and R10 (no rerun on an altered copy of /app/data). EASY: the 4 format checks (w1).
- Edits supported by these rows (section T edit table): the wide rows support a WRONG stage or a v3.5 hidden-scale tier, not a rule edit. R7 stays as the J3a integrity negative. The rows for the skipped probes show that the altered-copy probes (P-d) held. The own-extract probes R1, R3 and R12 (P-b) were passed by the agent's ordinary synthetic self-test (step 23), so they should be replaced.

## 1. Phase A: is the score genuine?
- Tree: `config.json` stages `.kiro-staged-tasks/district-heat-flex-procurement`, staged from `Tasks_INPUT` on 28 Oct at 14:08. `diff -rq` of the staged copy against `WORK/pushed_e9d91966ed25/` shows only harness staging: the extra file `.kiro-staged-from`, and `task.toml` `allowed_hosts` with `host.docker.internal` added (lines 25 and 32). `agent/instruction.txt` is byte-identical to the pushed `instruction.md`. All 66 ctrf test ids are present in the pushed `tests/test_output.py`.
- So the run used the pushed tree e9d91966ed25, which is before QL1 fix 8556721. The current tree 2b289f9f9561 is only harder: QL1 F1-F10 added hidden variation, and the a12 and a11 programs still score 173/237 on it (RECHECK_FIX.md).
- `result.json`: exception_info None, reward 0.4483. `trial.log` and `test-stdout.txt` contain no permission errors, Errno 13, tracebacks or missing files. The judge read the response: `judge_response.txt` quotes the agent's own extract, for example R3 "O3 override 4000 + uplift 1000 + public adder 750 = 5750 above cap 3000" and R4 "O2 two 1.5-cent, O8 two 0.5-cent".
- **Verdict: GENUINE** for tree e9d91966ed25. It is a valid baseline for the current tree as well, because the master's re-score (173/237) shows the same lost checks.

## 2. Root cause
| cause | answer | evidence |
|---|---|---|
| 1 run error or wrong copy | NO | Pushed tree, staging-only diff, no errors. The 120 s timeouts are the stated limit (schema.md:162-163), not a harness fault. |
| 2 harness or rescoring change | NO for tests, PARTLY for the judge | Kit HEAD 5574d77 is unchanged and so is the reward formula. a11 on the same tests also scored 173. After the run, QL1 F8 split R3 into R3 and R12 (judge positive 27), which raises an a12-like judge from 16.67 to 7/27 = 25.93. |
| 3 our QC/fix rounds made it easier | NO for tests, PARTLY for the judge | No test change between a11 and a12. QL1 (after a12) only adds hidden variation (units and codes drawn, missing adder, profile gap, within-event allowance, equality boundaries). It shows no new rule, figure or separating example; the one removed sentence was instruction.md:9 (F2). The R3/R12 split (F8) hands a free extra w3 to any agent whose own extract has a capped rate. |
| 4 levers weak by design | **YES (PRIMARY)** | See below. |

Cause 4 detail (rule, where the agent got it right, what gave it away):
- M1 grants re-entry and carry (schema.md section 7, :211-250): written right at the first write, step 11/13 (`apportion` :454-469, one re-share among kept, carry in season order). The give-away is the rule text itself: the second share is spelled out step by step, and the agent copied it straight into code.
- M2 draws_from chain (site_allowances.tsv comment lines 1-11): root walk at :283-297, with the cycle-free statement given. Given away because the rule sits in the file next to where it is used.
- M3 credited relief ticks and composed rate (rate_cards.xml comment, schema section 6 :200-209): `rates`/`credit` at :320-334. The formula is written out in full beside the data.
- Season order, same instant, greatest id (schema 2.4 :132-138 plus the allowance comment): `NegStr` sort at :115-117. Given away by the stated convention.
- QL1 hidden variation (units, codes, missing adder, profile gap, within-event, equality): the program reads units and codes from program.ini (:84-98) and treats a missing adder as 0. None of these trips an agent that parses the stated keys instead of hard-coding shipped values. a12 never hard-coded.
- The wide P-3 lever (exact optimum at scale, schema 5 :172-198, limit at :162-163) is the only one that held, and it held only by TIMEOUT. The program is an exact DFS with ceiling pruning only (:337-429). It is right on every instance it finishes.
- Judge half (old 11 criteria): R1 PASS (step 23, drawn allowance in its own extract), R3 PASS (step 23, capped rate; under the split, R12 would also PASS), R5 PASS, R6 PASS (step 28), R11 PASS, R7 FIRED (step 31). R2, R4, R8, R9 and R10 FAIL (SKIPPED). Criteria passed for free (J1/J8): R1, R3 and R12 are own-extract witnesses for the stated rules, which the agent's habitual synthetic test covers anyway. R5 and R6 are near-free habits.
- **PRIMARY CAUSE: 4.** Every stated rule is read right at the first write. The only separator is scale, which loses by TIMEOUT alone.
- Contributing: 3/2 (judge part). The R3/R12 split and the own-extract probe templates give judge points for the agent's default self-test.

## 3. Lever table (reward-details.json plus the trajectory)
| check / criterion | pts | earned | lever / probe template | status |
|---|---|---|---|---|
| 4 format checks | 4 x w1 | 4 | none | EASY |
| 20 visible families (shipped) | 20 x w3 | 60 | none | EASY |
| 20 `_hard` families (hidden H1 season / H2 settlement) | 20 x w5 | 100 | L2 held-out with M1, M2, M3 and QL1 variation | LEAKED (all passed) |
| 3 mutations (segment adder, allowance ticks, minimum grant) | 3 x w3 | 9 | G6 | LEAKED |
| wide_0..3 x 4 checks | 64 | 0 | P-3 exact optimum at scale | HELD by TIMEOUT only (0 WRONG) |
| negatives: hardcoded -5, reads tests -5, external import -3 | -13 | 0 fired | cheating acts | n/a |
| judge R1 / R3 (+R12 after split) | w3 each | passed | P-b own-extract witness | LEAKED |
| judge R2, R4 | w3 each | 0 | P-b with a specific shape | HELD |
| judge R8, R9, R10 | w3 each | 0 | P-d altered-copy rerun | HELD |
| judge R5, R6, R11 | w1 each | passed | outcome / behavioural | EASY |
| judge R7 | -5 | fired | J3a-style honesty | integrity (fired) |

Weight shares (current tree): held-out w5 = 20 `_hard` x 5 + 8 wide w5 checks = 140/237 = **59%**, which already meets the N2 bar of 50% or more. Lever share = 64/237 = 27% (all TIMEOUT).

Arithmetic:
- a12 final = (73.00 + 16.67)/2 = 44.84. Under the current split judge: (73.00 + 25.93)/2 = 49.46.
- A probe-band judge rebuild alone at the peer probe pass rate of 25% (J2), with the 8 probe criteria (w3, 24 points) and the 3 outcome criteria (w1) as marked: judge = (0.25 x 24 + 3)/27 = 33.3, final = (73.0 + 33.3)/2 = **53.2**. If the honesty negative fires as it did for a12: judge (6 + 3 - 5)/27 = 14.8, final 43.9. A judge rebuild alone cannot reach the gate (final < 40), because the tests stay at 73.

## 4. Trajectory autopsy (B1)
- Read order: step 3 `find /app`; 4 the whole of schema.md; 5 heads of program.ini, allowances and rate_cards; 6 heads of every data file; 7-10 Python probes of sites, waivers, the feeder fixed-width file and profiles (08:40-08:42).
- Writing: step 11 (08:44:45) first write of derive_report.py (36 KB); step 13 (08:46:59) rewrite (34 KB) = the final graded logic. The graded logic was never changed after step 13, about 8 minutes into the session.
- Self-tests: step 14 shipped run 0.897 s; 17-19 enumeration statistics (25600 portfolios, tie counts); 21-22 an independent replay (verify.py: itertools.product, Fraction credits, grant replay), "selection mismatches 0" in 4.2 s; 23-24 a synthetic extract with hand-computed expectations covering labels, waiver, greatest-id ties, the allowance chain with a blocked candidate, season order, a capped-rate credit, every grants branch, carry and both rounding modes. That covered every stated lever except scale. It never timed a larger instance, although its own stats (step 17) showed exponential growth. Steps 25-29 were cross-checks and cleanup; step 31 is the finish message.
- Time per phase: reading 5 min, writing 3 min, self-test 9 min.

## 5. Agent program
Saved at `agent_program/derive_report.py` (sha256 1b3ab91f3178426b41203c45d590701c9fae4e3adb74819013d92620eaeb0a76) with its 9 shipped outputs, copied from `run/artifacts/app/out`. A line-by-line audit against schema.md sections 1-9 found no misread rule (details in the WORK LOG). Per G10, it is used for diagnosis only.

## 6. Can the target be reached? (feeds the Phase 2 go decision)
- Target: a12 program tests <= 60 on the planned tests, with TIMEOUT/CRASH counting for at most 30% of positive test weight (rule 17) and the rest WRONG output.
- a12 loses 0 points by WRONG output. Adding held-out w5 coverage on "the families it gets right" without a new stated rule cannot produce WRONG output from this program, because it implements every stated branch exactly. Measured: 173/237 on the old and the new tests, and all 7 QL1 wrong readings are caught while a12 still passes them.
- The only loss channel left for a12 is hidden scale. Counted against the cap, the best possible is 100 - 30 = **70**. Reaching that means taking the wide (TIMEOUT) share from 27% to 30% by adding a wide corpus (adding wide_4 at 16 points gives 80/253 = 31.6%, counted 30). Reweighting the existing checks after a run is forbidden (1D, L1).
- So "a12 tests <= 60" is **not reachable** under this prompt's constraints (no new stated rule, no instruction change, TIMEOUT capped at 30%). Best predicted: a12 counted tests 70, judge mid of about 10-15 after a probe rebuild, so final about 40-42. That fails DESIGN READY (a), which needs 35 or less.
- Where the N2 tier does bite: programs that hard-code the shipped values or skip a rule. That covers the QL1 wrong readings (UNIT10 147, CODESHIP 137 and so on, out of 237) and greedy (72/237). It is worth keeping and growing for blind reads, but it does not move a12.
- Options that would move a12 (each needs the master's decision because it widens scope):
  1. A WRONG stage inside P-3. Add a stated, method-free scale fact that an exact-but-slow program cannot meet, plus a hidden instance where a fast plausible heuristic is wrong. a12 still loses only by TIMEOUT, so this helps the blind and generic solvers, not a12.
  2. One new stated rule as an LC1 or LC5 pilot inside the hidden tier. Not allowed this round ("no new stated rule").
  3. Accept the scale ceiling: a12 counted 70, judge 10-15, final about 40-42. Stop PAUSED with these as the best numbers.
- Recommended Phase 2 under the current constraints:
  - Add the wide_4 corpus (16 points, hidden seed, same four checks) so TIMEOUT is about 30% of positive weight.
  - Add N2 held-out w5 checks on new hidden seeds. These are for the blind and first-write programs; a12 will pass them.
  - Rebuild the judge as a probe band: swap the own-extract R1, R3 and R12 for P-d, P-e or P-h probes, replace R5 and R6 with probe or behavioural criteria, and keep J3a at -3.
  - Expect to stop **PAUSED** with predicted a12 counted tests 70 and final about 40.

## 7. LEAK_LIBRARY rows
| lever | how it was written | leaked at | fix rule |
|---|---|---|---|
| M1 grants re-entry (second share among kept) | step-by-step in schema.md section 7 :211-250 | a12 step 13 (`apportion` :454-469), first write | stated-rule levers PAUSED (1C); a written-out procedure is copied verbatim |
| M2 draws_from chain | in-file comment in site_allowances.tsv lines 1-11, next to the data | a12 step 13 (:283-297) | rule next to its use (LEAK_LIBRARY known) |
| M3 composed capped rate / credited ticks | rate_cards.xml comment plus schema section 6 | a12 step 13 (:320-334) | formula written in full beside the data |
| QL1 hidden variation (units, codes, adder, profile gap, equality) | stated keys in program.ini and schema section 1 | a12 step 13 (:84-98); the program never hard-coded | only catches hard-coders; no effect on a careful first write |
| Judge P-b own-extract witness (R1, R3, R12) | "checks X on its own extract" | a12 step 23 synthetic test | own-extract probes of stated rules are passed by the default self-test; use P-d/P-e/P-h |
| P-3 scale (wide_0..3) | stated 120 s limit, hidden larger instance | held at a12 step 13, TIMEOUT only | v3.5: counts at most 30%; needs a WRONG stage to count further |

DIAGNOSIS READY: /Users/mac/Desktop/Terminal Bench/master_chat_work/20261029_district-heat-flex-procurement/harden_r_ql1/DIAGNOSIS.md
