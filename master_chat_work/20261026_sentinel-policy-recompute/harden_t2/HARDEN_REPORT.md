# HARDEN_REPORT sentinel-policy-recompute, test-hardening round 2 (board 4a82a12)

Verdict: BUILD READY except the Docker gate. The local oracle scores 98/98 and PRECHECK is CLEAN. The Docker block did not run: this session's permission rules deny the harness run command (see Gates).

Session rename: `name_session.py 4a82a12` printed `codex: no match` and `opencode: ['ses_e8613349fffesQ5WqXW4tVOMlN']`. The list does not show 4a82a12; continued as instructed.

## New rules (paths under environment/data/)
| id | rule | file:line | shipped fires | hidden fires |
|---|---|---|---|---|
| U | The divisor is fixed by the standing curve reports. When the reports fix no single divisor, the threshold is unresolved: iterations holds only the seed, and converged and risk_threshold are null. | convergence_spec.txt:7; range comment reconciliation_rules.conf:3 ("a whole number from 6 to 14", sits where the divisor is defined); nulls output_field_spec.txt:14-15 | 0 | utie-a 2, utie-b 2 (tie, unresolved); udecoy-a/b 3 (divisor 14, first report alone fits 13 and 14); combo2-a 3 (divisor 12); combo2-b 2 (tie) |
| D1 | A reset withdraws every curve report at a lower seq. The order comes from the existing seq definition (line 5, seq unique across rows and reports). | override_deltas.json:15 (reports sentence plus toy example), :5 | 0 | d1-a 2, d1-b 2, combo2-a/b 2 |
| D2 | Statuses are active, superseded, withdrawn and reinstated. A reinstated row selects like an active row and adds the deltas of the last active row of its override_id at a lower seq. | override_deltas.json:14 (OV-Z1 toy example), override_precedence.conf:2 | 0 | d2-a 3, d2-b 3, combo2-a/b 3 |

Master go conditions:
1. The U sentence names no search, range or count. The 6-14 range is a comment beside `iteration_divisor`. U has no toy example.
2. Each witness curve is recomputed through the full draw. That covers allowance and admit (N1/N3), alias (Q3), reissue (Q2), requires (Q4) and carry (Q5). The combo2 generator rejects a corpus unless at least 2 of the Q2-Q5 wrong readings move the fitted divisor (1 on the tie corpus). Q1 cannot reach a witness, because a witness sums only risk terms.
3. D2 chains have length 3 or more: active, then withdrawn, then reinstated. Combo2 adds a superseded carry tail and a withdrawn tail. Every D1 corpus has 2 resets, each of which removes a curve that would change the fit.
4. Shipped data has no reports, no withdrawn or reinstated rows, and no ties. Shipped answers are unchanged: 285, 3, 2250, 51.

Interpretation, flagged for the master. Resets and reinstated chains are planted in their own corpora and in combo2, not in every hidden corpus. That keeps each lever's cost at 8.2% and keeps ownership intact (G1a). Planting them everywhere would push each lever past 12%.

## Counts
- Rules: 31 stated, up from 28. RULE_TRACE adds R38-R43.
- Data: 56 data files in 9 formats. 5 text files were edited; no other data byte changed.
- Tests: 27 checks (4 new: w5 unique_divisor_fit, w5 curve_reset, w5 reinstated_chain, w3 rare_state_pairs). Positive total is 98 (was 80); negatives -11.
- reward.toml: test_output 0.5/98 = 0.00510204081632653.
- Judge: 15 criteria, unchanged. No probe was added, because solve.sh self-checks run on copies of the shipped data, where U, D1 and D2 never fire.
- Old checks: weights unchanged. The documents and rows of all 28 old corpora are identical to the snapshot taken before this round.
- Weight shares: hidden or mutated corpora carry 95.9%; the new t2 checks carry 18/98.

## Measured cost table
Measured locally on the real test_output.py, tests channel only (WORK/t2_levers.py, log WORK/t2_levers3.log). No variant crashed.

| program | tests % | checks lost |
|---|---|---|
| oracle | 100 (98/98) | none |
| each Q wrong alone (q1-sum, q2-none, q3-none, q4-none, q5-none) | 88.78 (87/98) | own owned w5 + rare_rule_pairs w3 + rare_state_pairs w3 |
| u-none / u-firstfit / u-firstreport | 91.84 each | unique_divisor_fit + rare_state_pairs |
| d1-none / d1-first | 91.84 each | curve_reset + rare_state_pairs |
| d2-none / d2-own / d2-first | 91.84 each | reinstated_chain + rare_state_pairs |
| first write (skips every rule shipped never fires: Q1-Q5, U, D2) | 58.16 (57/98) | 9 checks |
| blind r1 program (WORK/blind_r1) | 86.73 (85/98) | unique_divisor_fit, reinstated_chain, rare_state_pairs |

Against the targets:
- Each new lever alone costs 8.2%, inside the 5-12% target.
- The worst all-but-one program scores 91.84, inside the 92 limit.
- The blind r1 program scores 86.7, inside the 70-90 target. It passes curve_reset because the D1 corpora resolve to its fixed divisor of 10.

## Gates
- STACKING_CHECK: `STACKING PASS (the AL-28 and TS-26 hints were corrected by hand as above)` (OUT/STACKING_CHECK.md).
- PRECHECK last line: `PRECHECK CLEAN`. It reports 0 IN17 and G5 warnings. Within it, structure_qc, instruction_qc, tests_qc and judge_qc all report 0 FAIL.
- Validator: 37 passed, 3 failed, 0 warnings. The 3 failures (sections 15.5-15.7, TRUTH yaml provenance) were already present in t1, r2 and r3.
- xref_check: 80 entries, 0 findings. TRUTH.md shas were rewritten by script as the last edit.
- Docker block: NOT RUN. Oracle x3, owner, nop, stub and forgery are all unmeasured.
  - The exe_copy copies were built (reward 1/98 per test), but the nohup chain was refused: a permission rule denies any bash command containing the harness run command. I did not work around it.
  - The lock and the copies were removed.
  - This needs a session where that command is allowed, or the master's queue.
- Tasks_INPUT: synced with `cp -Rp`; `diff -rq` BUNDLE vs Tasks_INPUT is empty. Tree sha 1774b1e2c376.

## Not run
- The Docker block, as above.
- The blind P13 read, which is the master's next step.
- The 300-seed generator sweep for the new families. Only the 10 graded seeds and the generator retries were exercised.

## Lessons for the master
- A unique-fit lever needs a tie corpus as well as a decoy corpus. Without the tie, a first-fit reading loses only the decoy test (it scored 94.9 before combo2-b became a tie) | no change: design note for LEVER_RULES S3.
- Witnesses that are recomputed through the full draw make earlier rule slips move the fit (condition 2) at no extra wording cost | no change: pattern worth reuse.
- This session's permission rules block the harness run command, so the Docker gate cannot run from build sessions | template_change: prompts/templates (Phase 3 Docker step) should name who runs Docker when it is blocked.
