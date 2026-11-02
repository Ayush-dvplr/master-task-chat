# S3a cohort-retention-reconciliation round outputs

Paths (prefix master_chat_work/):
- C1 = 20261022_cohort-retention-reconciliation/harden_r1/DIAGNOSIS.md
- C2 = 20261022_cohort-retention-reconciliation/harden_r1/HARDEN_REPORT.md
- C3 = 20261023_cohort-retention-reconciliation/harden_r2/DIAGNOSIS.md
- C4 = 20261023_cohort-retention-reconciliation/harden_r2/HARDEN_REPORT.md
- C5 = 20261023_cohort-retention-reconciliation/p12_r2/RECHECK_FIX.md, gates/trap_survival/separation.txt, lever_loss.json
- C6 = 20261023_cohort-retention-reconciliation/harden_r2/STACKING_CHECK.md

## v0 (permission artefact)
- C1:6-8 reward 0.5868 = 0.5x0.4235 (tests 36/85) + 0.5x0.75 (judge 27/36). "the prompt said 'no judge key'; the file says otherwise" (same mis-statement in dispatch D1:13, sensor S1:5 -> prompt-fact process failure, 3 tasks).
- C1:10-16 18x Errno 13 Permission denied, 49 points lost; probe w/o trap 85/85.
- C1:22-33 every V0 lever LEAKED; "every rule sits next to its use in one file; the instruction lists the topics ...; the schema counts the residuals ('three residuals') and artifacts ('Ten JSON artifacts'); each fixture isolates one rule so a per-rule handler passes it; the agent's synthetic extract mirrors the fixtures one for one."
- C1:36-41 composition shipped-only 45.9%, isolated 38.8%, whole-doc 15.3%; "the seeded generator only redraws events over a001-a008 ... so even these never move a boundary the shipped data does not show." (generator too narrow = hidden inputs not hidden)
- C1:45-48 judge 18 criteria all process/echo; met 16.

## r1 (A+B+E+F, CR-1..CR-5)
- C2:88-96 single-lever wrong-reading local scores 0.40-0.85; "The v0 agent program scores 1/60 = 0.017 on the new tests channel."
- C2:100-102 hidden whole docs 70%, isolated 28.3%, shipped-only 1.7%.
- C2:119 stub 0.0333 "the canonical check passes trivially on `{}`" (bundle weak spot).
- C2:123-125 EnvironmentStartTimeoutError 900 s, litellm wheel at 63 kB/s (tooling).
- C2:132 "Not run: a real agent trajectory on the hardened bundle, the judge, PL QC, P8, P7."

## Real a2 run on r1+P12 tree: 100/100/100 (C3)
- C3:4 tests 100 rubric 100 combined 100.
- C3:9-14 run copy verified = current bundle; staged copy adds host.docker.internal to allowed_hosts (harness judge proxy).
- C3:17 "v0 had a judge. The master note says it did not, and that is wrong."
- C3:19-20 "Without the trap, v0 = 0.5 x 1.0 + 0.5 x 0.75 = 87.5 ... The tests channel was never hard."
- C3:28 R4 judge figure was 13 (wrong for oracle), P12 corrected to 14; "With 13, the agent's correct 14 would have failed R4" (bundle bug: judge figure not derived from oracle run).
- C3:35-39 agent sequence: step 4 cat schema.md, step 5 cat audit_policy.md, step 6 cat every data file; step 8 plan; wrote program once (step 9, recreated step 11 cosmetic); ran (12); self-tested synthetic extract (14-16) "covering unsorted calendar, chained merges, plan-history tie, minimum_value>0, negative revenue, offset_zero_is_full true, a duplicated exclusion row and a final-period cohort"; determinism diff (17). "It never edited the logic after the first write."
- C3:43 CR-1 "the reflex trap is spelled out in the rule" (audit_policy L20-25 "not only the one for the cleaning step that removed it").
- C3:44 CR-2 decoy "contradicted in plain words"; shipped boundary a002/e009 shows it.
- C3:47 CR-5 two duplicate notions in two files, each fully explicit -> leaked (split across files alone does not hold).
- C3:57-62 common pattern: "No rule had a plausible wrong reading. Each sentence named its own exception." "The only 'split across files' was a two-file read, and instruction.md tells the agent to read schema.md 'together with the study records it points to'." "The decoy was refuted on the same page as its use." "The shipped boundaries ... let a careful agent watch each rule fire. Hidden cases only repeat rules the agent had already coded." "Every check graded a rule the agent read correctly, so the hidden-input design (70% weight) had nothing to separate."
- C3:147 "It made no mistakes. It verified more than the grader requires: synthetic extract, determinism diff, AST parse, and a grep for network modules."
- C3:149 judge "states figure X" can only drop below 100 if a lever changes a SHIPPED figure.
- C3:165 honest risk: legacy-code C lever is registry candidate with no real-run evidence; "An agent that ignores /app/legacy/ and writes from the contracts (as a2 did) avoids the code decoys."

## r2 (LEVER_PLAN_v1 L1-L4)
- C4:10-13 CR2-L1 green control wrong answer (D), CR2-L2 identifiers vs strict fields "make-it-match repair" (NEW control-fitting + F; shipped e035 " 4500"), CR2-L3 refundable balance ledger (C+B), CR2-L4 segment weight override across files (A+E).
- C4:17 giveaways removed; instruction now "Each output document is graded whole on fresh inputs" and asks only total revenue and clean count.
- C4:23-29 whole-doc 60.6%, isolated+mutation 29.6%, shipped-only 1.4%.
- C4:33 judge: all "states figure X" deleted; R1-R5 behaviour on lever cases; R7 reran after last edit; R8 honesty negative.
- C4:52-54 a2 program 0.0563; S4 careful 0.1690; S2 0.0563.
- C4:66 single-lever misreads: L1a 0.8451, L1b 0.8873, L2 0.24-0.46, L3 0.7465, L4 0.70-0.77. => only L2 (cascading identifier normalisation) costs much in isolation; L1/L3/L4 each cost 11-30%.
- C4:60-62 playground.py absent; oracle x3 per Ayush vs kit x5; no real trajectory; judge not executed.
- C5 trap survival after P12 r2: lever_loss before/after equal (L2a 54->53 only from generator draw shift); reflex 0.0563 before/after. "Minor findings that only ask for a written note are cheaper to fix than to defend." (PL_NOTE)
- C5:15 TS-13 (one property per test) KEEP: fixing would pay 6/71 to programs with no cohort right -> CONFLICT QC rule TS-13 vs whole-doc gate design.

## Derived
- CO-a: Third task where a 0600/0711 permission artefact posed as difficulty (cohort 58.67, vendor 4.83%, dispatch tests 0.297, emberforge 1.94).
- CO-b: Rules that name their own exception, decoys refuted beside use, two-file reads the instruction points to => leak. Same as district/vendor (3 for 3).
- CO-c: claude-opus-5 self-tests with a synthetic extract that covers every hidden-case family; hidden generator that only varies cases the agent can enumerate from the docs adds nothing.
- CO-d: Judge figure bug (R4 13 vs 14) caught only in P12; judge figures must be produced by running the oracle.
- CO-e: r2 relies on the agent misreading L2; a single strong cascading lever dominates the score (S4 0.169 is mostly L2). Unmeasured on a real run.
