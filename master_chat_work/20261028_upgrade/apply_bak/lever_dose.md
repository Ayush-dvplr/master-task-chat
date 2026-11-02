# Lever dose test (IMPROVEMENT_PLAN_v1 D2), procedure v1, 23 Oct 2026

Purpose: measure each lever's share of the points a reflex program loses, without a new trajectory. Run it on a pilot that passed the gate (tests < 85, rubric < 85, overall < 50 on a real trajectory; gate v3.6 27 Oct 22:20), after the trajectory, read-only on the bundle.

Inputs: BUNDLE (copied to scratch; never edit the real one), the reflex program (`agent_program/` from the trajectory), `WORK/LEVERS.md`, and the reference `solution/solve.py`.

## Steps
1. Copy BUNDLE to `/tmp/dose-<slug>-<TS>/bundle/` (TS = `date +%Y%m%dT%H%M%S` + 2 random hex). All work happens there.
2. Prove the scorer: run the REAL `tests/test_output.py` (rewardkit 0.2.1, or the local stub used by the stacking check) on the oracle (must be 1.0) and the nop (must be 0.0). Record the method.
3. Baseline: score the reflex program unchanged on all levers ON. Call it R_all.
4. Lever OFF, one at a time: for each lever k in LEVERS.md, make a scratch variant of the reference generator/tests in which lever k cannot bite: the hidden inputs carry no separating case for k (e.g. no control mismatch for L1, no repairable mismatch for L2, no state-consuming early record for L3, no override in a far file for L4, no strict-field row for L5, no out-of-scope record for L6, no per-item rounding remainder for L7). Every other lever stays ON. Regenerate expected values with the reference solution, so the oracle stays 1.0 in each variant (check it).
5. Score the reflex program on each variant: R_off(k). Lever k's dose = R_off(k) - R_all (points it costs on its own, given the others).
6. Lever ON alone: for each k, a variant with only k ON. Score: R_only(k). 1 - R_only(k) = what k costs alone.
7. Interaction: sum over k of (1 - R_only(k)) compared with 1 - R_all. A sum well below 1 - R_all means the levers interact (stacking); D3 says to add interaction, not more levers, when pilots land at 70 to 85.
8. One-lever-enough check (D1): any k with R_only(k) <= 0.20 alone would pass the reflex gate on its own; record it.

## Output
`master_chat_work/<date>_<slug>/dose/DOSE_REPORT.md`: method, R_all, a table `lever | R_off | dose | R_only | alone passes gate?`, the interaction line, and the oracle check per variant. Append per-lever `dose` and `alone` numbers to the lever's `reflex_score` entry in `registry/levers.json` (master does this at intake). Delete `/tmp/dose-<slug>-<TS>/` at the end.

## Rules
- Never edit BUNDLE, WORK or the trajectory copy. No Docker needed; no trajectory.
- A variant changes only the hidden-input generation (in the scratch copy of tests/) for one lever; the check list and weights stay as shipped, so scores are comparable.
- Tests channel only; label every number "tests-only, reflex replay".
