# S3a dispatch-plan-reoptimization and sensor-network-lsq round outputs

Paths (prefix master_chat_work/):
- D1 = 20261022_dispatch-plan-reoptimization/harden_r1/DIAGNOSIS.md
- D2 = 20261022_dispatch-plan-reoptimization/harden_r1/HARDEN_REPORT.md
- N1 = 20261022_sensor-network-lsq-correlated-adjustment/harden_r1/DIAGNOSIS.md
- N2 = 20261022_sensor-network-lsq-correlated-adjustment/harden_r1/HARDEN_REPORT.md

## dispatch v0 (converted task)
- D1:9-11 combined 0.6419; tests 27/91 = 0.2967; judge ran 77/78. D1:13 "The judge did run ... Reported as fact." (prompt said otherwise)
- D1:17 permission trap: agent wrote solver.py with editor + `chmod +x` (step 36) -> mode 0711; verifier ran in place as nobody without read -> 2x5-pt rerun checks fail. Real tests 37/91 = 0.4066.
- D1:21 HELD lever = one documented tie rule: "Handbook s10: 'When two schedules cost the same, the schedule whose production period is earlier in fiscal order wins.' ... The agent's backward DP keeps the later P02 production period, even though its own docstring says ties prefer the earlier one. That one flipped lot changes handling, shortfall, sourcing, certificates and totals, so 14 chained checks fail".
  => second real HELD case: the rule was documented and the agent KNEW it (docstring) but the natural algorithm (backward DP, strict < comparison) implemented the opposite tie order; exact ties only occur on one item (K13). Same mechanism as emberforge L7: a stated rule whose natural code structure silently violates it on a rare case, plus a dependent chain amplifying it (14 checks).
- D1:28 leak cause 1: `solver_run_report.json` `assumptions` block "lists every wrong setting the previous run used ... The agent read it at step 21 and treated it as a checklist of things to fix." (confirmer = answer key)
- D1:29 instruction paragraph 3 names trap topics ("rounding rule, sequence cutoff, unit scales, currency conversion and tie break rules").
- D1:30 rules beside the file that settles them; s15 worked examples confirm readings.
- D1:31,39 94.5% shipped-data-only; one hidden perturbation 5.5%.
- D1:25 "Out of 17 reconstructed levers, 1 held and 16 leaked."

## dispatch r1
- D2:18-21 LV-DPR-01 lot tie order 2 constructed ties per set (A) HELD (v0 replay); LV-DPR-02 per item setup fallback, control default decoy, K22 by omission (B) HELD; LV-DPR-03 first live amendment copy (C) LEAKED; LV-DPR-04 rejection reasons/void accounting (F) LEAKED. (HELD/LEAKED here = v0 solver replay on new tests, not a fresh run.)
- D2:24-25 isolated 27.7%, shipped 1.0%; v0 solver 0.168; mutants m_fallback 0.366, m_tie 0.317, m_amend 0.168, m_rejnorm 0.683, m_voidlog 0.881.
- D2:29 validate_bundle 7 fail left (QC_DEFENCE); D2:35 "No agent trajectory on r1", judge not run.
- D2:8 F6/F7 defended "the chain is deliberate" (chain vs QC cascade rule conflict, see TS-26/AL-28).

## sensor v0 (converted task)
- N1:4-5 tests 1.0 (64/64); judge ran 22/52 -> 0.7115; prompt said "no judge key".
- N1:6 trap did not fire; grader relied on Harbor /app/out 0777.
- N1:9 "It read schema.md once (step 3), the header blocks (steps 5, 11), wrote one program (steps 20 and 22) and ran it once: step 23 printed `verdict=PASS ...`. Every later step was a format check."
- N1:12 "Answer key in every file. `trap_block()` appended 12 `TRAP i: <rule>; inverse: <exact fix>` lines to every shipped header ..." (PL generator bug; converted tasks).
- N1:13 "Full-answer confirmation ... a correct pipeline prints PASS and almost any wrong one prints REJECT. Step 23 is that check." (rule 7 confirmed)
- N1:14 manifest column prints every converted sigma, agent compared (step 32) (partial confirmer).
- N1:15 schema labels each rule `(Trap: ...)` and prints the factors.
- N1:18-19 isolated 12.5%, shipped-only 84.4%.
- Judge 22/52 although tests 1.0: judge lost on process/other criteria, not figures (detail not in DIAG; UNVERIFIED which criteria).

## sensor r1
- N2:46-51 new levers H1 centring split + omission, H2 angle reduce decoy default on rare boundary (2 shipped straddle rows), H3 revision duplicates, H4 chain; single-miss mutants 0.129, first_seen 0.081.
- N2:27 acceptance centres irregular per row, shipped verdict REJECT_LOW, "no single-miss mutant lands in the PASS band".
- N2:54 cheat negatives "stand down unless a hidden run was clean" (study rule 10).
- N2:79-81 judge not run; no trajectory; PL QC, P8, P7 not run.

## Derived
- DS-a: dispatch K13 tie = 2nd real HELD lever; mechanism = algorithm-shaped violation of a stated tie rule on a rare exact tie, chained. Agent even documented the right rule in its docstring and never tested an exact tie.
- DS-b: confirmers/answer keys in converted tasks: assumptions block (dispatch), TRAP/inverse blocks + PASS band (sensor) -> one-pass solves.
- DS-c: three of three converted-task DIAGs record "the prompt said no judge key; the judge ran" (cohort C1:6, dispatch D1:13, sensor N1:5) -> master prompt factual error repeated.
- DS-d: All r1 HELD claims rest on replaying the v0 program or local mutants; no fresh trajectory (same as emberforge/vendor/district/cohort r2).
