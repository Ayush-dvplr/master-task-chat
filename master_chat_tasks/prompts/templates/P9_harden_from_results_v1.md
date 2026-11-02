# P9 Harden from harness results, template v1 (21 Oct 2026)

Use this when a real run scored above the gate, or when Ayush says "make it harder". The input can be only a score, a pass_summary file, a Harbor job folder, or a full trajectory. Use whatever exists.

=== PASTE BELOW ===

You are hardening one Harbor 0.24 bundle using real harness results. First you diagnose exactly what let the agent score. Then you replace or add mechanisms, never by hiding rules. Edit in place. Never regenerate it and never use `--force`.

First read in full: `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/prompts/templates/_COMMON_RULES.md`. Then read `WORK/DESIGN.md`, `WORK/LEVERS.md` and the latest `baselines.json`.

## Inputs
- BUNDLE: `/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/[[SLUG]]/`
- WORK: `/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/[[SLUG]]/`
- RESULTS (any subset): score `[[SCORE_OR_NONE]]`; summary `[[PASS_SUMMARY_PATH_OR_NONE]]`; job folder `[[JOB_DIR_OR_NONE]]`; trajectory `[[TRAJECTORY_PATH_OR_NONE]]`
- Build-time baselines: `[[BASELINES_PATH]]`
- Master's notes (levers that leaked elsewhere, new levers to try): [[MASTER_NOTES]]
- OUT: `/Users/mac/Desktop/Terminal Bench/master_chat_work/[[DATE]]_[[SLUG]]/harden_r[[ROUND]]/`

## Phase 1: diagnose (no edits)
1. Read what exists:
   - from the job folder: `result.json`, `verifier/reward.json` and `reward-details.json` (per-check pass or fail);
   - from the trajectory: the steps where the agent read files, tested, and claimed it was done.
   If the input format is unfamiliar, describe the fields you found and use them.
2. Map every check to its lever through LEVERS.md. Build a table of lever, points available, points earned, and status (HELD if the agent lost them, LEAKED if it earned them).
3. Compare the score with the baselines. An exact match with a solver S-k tells you which reading the agent took.
4. For each LEAKED lever, name what made it derivable: a visible example that separates the readings, a spec sentence placed next to its use, a check the reflex reading passes by accident, or an agent self-test that caught it. Quote the trajectory step or the file line.
5. From the trajectory, list where the agent went wrong or skipped verification. These are candidate judge criteria.
6. Write `OUT/DIAGNOSIS.md` and stop. Say "DIAGNOSIS READY: <path>", then wait for Ayush to reply "go" (he may pass on changes from the master chat).

## Phase 2: harden (after "go")
- Replace each LEAKED mechanism with a HIDDEN-ONLY one, or add separating hidden cases so that the agent's reading now fails.
- Add NEW levers (several, not one). Each needs the rule text, the reflex reading, the constructed hidden cases, and checks that the wrong solver fails.
- Judge criteria taken from the trajectory's mistakes:
  - each must be true of any correct solution (JD-7);
  - each must be met by every competent approach (JD-15);
  - none may read what a test reads (JD-8);
  - use positive grammar and counts.
- Keep partial credit: checks stay independent, and downstream stages are graded on supplied correct inputs.
- Apply common rule 6 after any data edit. Update DESIGN.md (add a "Harden round N" section), LEVERS.md and TRUTH.md.

## Phase 3: verify, once
1. Run the 4 QC scripts, the validator (`--archetype [[ARCHETYPE]]`) and playground static, with 0 FAIL.
2. Run the oracle on the tests channel; it must be 1.0.
3. Re-score S2, S4 and the solver matching the agent's reading with the P3 method. The target is S4 between 0.10 and 0.20, and the agent's reading at 0.20 or below.
4. Write `OUT/HARDEN_REPORT.md` with the before and after lever table, new checks, new judge criteria, the gate results and the new baselines.

Stop after 3 harden rounds in total. Report "ROUND LIMIT".

Final reply: the levers that LEAKED and why (one line each), new lever ids, the new check and criterion counts, S4 before and after, oracle, and paths.
