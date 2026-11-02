# emberforge P9 r1: "go" message (master, 21 Oct 2026 12:58 IST)
Paste everything below the line into the emberforge harden session.

=== PASTE BELOW ===

go. Apply these answers and changes first:

1. Gates for this bundle (it is not a PL-generator scaffold). The live QC is the authority. It has no line-count rule and does not require the generator's validator or playground.
   - The 4 QC scripts must show 0 FAIL, and the manual QC checks you touch must pass.
   - Validator: fix §5.3, §5.4, §5.5, §7.2, §11.3 and §11.5 where the fix does not conflict with a QC rule. §1.12 is N/A (no matching archetype). §15.5 and §15.7 stay OPEN CONFLICT Q18. Any other remaining FAIL must be listed with the reason.
   - Playground static: fix A1 and A4. A5 (line counts) is WAIVED. Record it with the reason "generator volume check, not a QC rule; volume is not the difficulty". Do not pad data to reach it.
2. Answer key: delete `calibration_reference_bundle.json` and add `record_shapes.md` as you proposed. Also check that the example report publishes no values of a graded record beyond what is needed to pin the draw. If it does, cut it to the minimum and show that the draw stays unique (1 of 840).
3. Visible-season checks: do NOT move them to weight 1. Live TS-20 says "a core-deliverable test carrying weight 1 ... is wrong".
   - Drop the visible value checks whose outcome is graded again on hidden corpora.
   - Keep weight 1 only for real minor or existence checks.
   - Any visible value check that stays gets weight 3 and counts in the S2 budget.
   - Keep S2 at or below 0.10 and S1 at or below 0.25.
4. Levers: LV-EF-1, LV-EF-2 and LV-EF-3 are approved. LV-EF-4 is IN.
   - Its time limit is N = max(30, 10 x the slowest of 3 oracle runs on the 48-requisition case, 2 CPUs), rounded up to whole seconds.
   - State N and the size bound in the instruction.
   - Show by arithmetic that exhaustive search on the largest case needs at least 100 x N.
   - Write a second, independent optimum check in WORK (`check_exact.py`).
   - No check may depend on a run time close to N (TS-11).
5. L7 is the only mechanism that held in a real run: a hidden-only composition spread across files. Model LV-EF-1 to LV-EF-3 on it.
   - Plant each in hidden corpora, combined with at least one other rule.
   - Keep the split so that S3_k loses only its own lever's share.
   - The 40 all-or-nothing gen points on whole outputs must become per-lever, per-record checks.
6. Judge:
   - Drop the conduct criterion "runs the program on an edited copy". It rewards effort, and the rule is outcome criteria on what the agent states.
   - For each stated value (charge, admitted, allocated, the count of entries with two or more findings), name the observable each test reads. If any test grades the same number in an output file, the criterion overlaps (JD-8 and TS-26). Replace it with a stated fact that no test reads, for example the entry id and both finding codes of one forge refused by both cap and floor, or the reason a named forge was refused.
   - Every stated fact must be something the instruction asks the agent to report in its final reply. Ask for it in plain words, with no mention of a reviewer, grader or judge.
   - Keep the four conventions criterion, the code-quality criterion (JD-18) and the 4 negatives. The negatives total must stay at or below the positives total.
7. Shortcut hunt: required in Phase 3. The hardcoded-draw shortcut scored L5 0.184 and L6 0.144 in round 0. After the changes, the best shortcut must score 0.10 or less. Report it next to S0 to S5.
8. Phase 3 also re-scores the run's own `settle_vault.py` against the new tests. Expected: well under its old 0.68.
