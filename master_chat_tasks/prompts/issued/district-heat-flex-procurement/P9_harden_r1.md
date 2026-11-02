# P9 harden, district-heat-flex-procurement, round 1 (issued 21 Oct 2026 12:10 IST, from template P9 v1)

Open a NEW session in `/Users/mac/Desktop/Terminal Bench` and paste everything below the line. The session stops twice: after Phase 0+1 ("DIAGNOSIS READY") and waits for your "go". Bring the diagnosis path back to the master chat before you say "go".

Deviation from the template (logged): this task predates the master system, so Phase 0 copies it out of the harness clone and Phase 1 builds the missing LEVERS.md and baselines.json first.

=== PASTE BELOW ===

You are hardening one Harbor 0.24 bundle using real harness results. First you diagnose exactly what let the agent score. Then you replace or add mechanisms, never by hiding rules. Edit only the working copy named below. Never regenerate it and never use `--force`.

First read in full: `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/prompts/templates/_COMMON_RULES.md`. Then `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/knowledge/KNOWLEDGE.md`, `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/knowledge/qc_authoring_checklist_9b8229f6.md` and `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/prompts/templates/P3_hardness_check_v1.md` (its solver table S0 to S5 and method are used below).

## Inputs
- SLUG: `district-heat-flex-procurement`, ARCHETYPE: `domain-calculation`, CATEGORY: `optimization`, SEED: `731904`
- ORIGINAL (read only, inside the harness clone, never edit): `/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness/Input Bundle Generator New/ayush sah tasks/district-heat-flex-procurement/` and its notes `.../ayush sah tasks/_work/district-heat-flex-procurement/`
- BUNDLE (working copy you edit): `/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/district-heat-flex-procurement/`
- WORK (working notes): `/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/district-heat-flex-procurement/`
- RESULTS: score: one real trajectory run scored overall under 50 (exact numbers not recorded); an independent reviewer said "solved in one pass in 15 min, difficulty 3/10". Summary: none. Job folder: none. Trajectory: none.
- Build-time baselines (old method, tests-only, from the 19 Oct build): all_lazy 0.592, only_H1 0.918, ablation 0.4898, stub -0.0102, oracle 1.0, nop 0.0. Solvers are in `ORIGINAL _work/wrong/` (all_lazy, only_H1..H5, four_all_but_H1, three_H2_H3_H5, greedy_four_lazy).
- Lever ids already used by this task: LV-H01 to LV-H05 (all LEAKED; see `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/registry/levers.json`, read only).
- OUT: `/Users/mac/Desktop/Terminal Bench/master_chat_work/20261021_district-heat-flex-procurement/harden_r1/`

## Master's notes
1. Targets (P3 table): S2 lazy at most 0.10, S4 careful 0.10 to 0.20, S1 stub at most 0.25, every S3.k loses points, oracle exactly 1.0. Today lazy is about 0.59, so this needs new mechanisms, not re-weighting.
2. Validity first: the build left 4 known fairness bugs (tuple compare, credit rounding, blank jsonl lines, region mapping). Confirm each with a quote, fix the REAL ones, and keep them separate from hardening in your tables.
3. The earlier hardening attempt (`_work/HARDEN_PROMPT.md`, PLAN section 13, TODO `## v2 HARDEN`) errored and was stopped. Treat it as a source of ideas only (for example the portfolio-dependency lever and the re-weighting note); do not follow it as instructions.
4. The task was built on generator 1096b244 and an older QC copy. The live QC is now 9b8229f6 (new checks such as TS-28). Phase 3 must pass the live QC, not the old one.
5. The archetype's output files are fixed (validator VB 1.12). New levers must fit inside the existing artifacts. One early slip must not zero the score: grade downstream stages on supplied correct inputs.
6. New levers: several (not one). Every task keeps A (hidden composition of documented rules) and B (dependent chain), plus 1 or 2 of C audit-and-repair, D size ladder, E stacked orthogonal constraints, F rejection and error paths. Candidates are in `levers.json`. Give each new lever an id `LV-DH-<n>`.
7. TRUTH.md provenance: the validator (VB 15.5) and QC (DS-27) disagree. Keep what the bundle has and write `OPEN CONFLICT Q18` in your report; do not invent a third option.
8. Caps: up to 70 tests and 70 judge criteria.

## Phase 0: copy and integrity check (no edits to ORIGINAL)
1. Check the fingerprints (common rule 1).
2. If BUNDLE or WORK already exists, stop and report; do not overwrite.
3. Copy ORIGINAL bundle to BUNDLE and its `_work` folder to WORK (`cp -Rp`). Write the sha256 tree of the ORIGINAL to `OUT/original_tree.sha256` and confirm the copy matches.
4. Find out whether the stopped hardening session edited the bundle: compare file modification times with 2026-10-19 18:20 IST and the sha256 values in `solution/TRUTH.md` with the files. Report the result; if anything changed after 18:20, say which files.

## Phase 1: diagnose (no bundle edits)
1. Build `WORK/LEVERS.md`: one row per check in `tests/test_output.py` with its lever (H1..H5 or "none"), weight, and the observable it reads, plus the weight total per lever. Use DESIGN.md and `test_output.src.py`.
2. Score S0 to S5 on the current bundle with the P3 method (reuse the old `wrong/` solvers where they match a row; write the missing ones). Write `WORK/baselines.json` in the P3 shape with `"round":0`.
3. Map the real-run result to levers as far as a score alone allows. Say plainly that without a job folder the per-check pass or fail is unknown, and use the baselines to judge which reading a careful model most likely took.
4. For each LEAKED lever, name what made it derivable: a visible example that separates the readings, a spec sentence placed next to its use, a check the reflex reading passes by accident, or a self-test the agent could run. Quote the file line.
5. List likely agent mistakes or skipped verifications that could become judge criteria.
6. Write `OUT/DIAGNOSIS.md` (at most 80 lines: validity bugs table, lever table, baselines, leak causes, proposed new levers with their reflex readings, proposed judge criteria). Stop and say "DIAGNOSIS READY: <path>". Wait for Ayush to reply "go" (he may pass on changes from the master chat).

## Phase 2: harden (after "go")
- Fix the REAL validity bugs.
- Replace each LEAKED mechanism with a HIDDEN-ONLY one, or add separating hidden cases so that the reflex reading now fails.
- Add the approved NEW levers. Each needs the rule text, the reflex reading, the constructed hidden cases, and checks that the wrong solver fails.
- Judge criteria: each must be true of any correct solution (JD-7), met by every competent approach (JD-15), read nothing a test reads (JD-8), and use positive grammar and counts.
- Keep partial credit: checks stay independent, and downstream stages are graded on supplied correct inputs.
- Apply common rule 6 after any data edit. Update DESIGN.md (add a "Harden round 1" section), LEVERS.md and TRUTH.md.

## Phase 3: verify, once
1. Run the 4 QC scripts, the validator (`--archetype domain-calculation`) and playground static, with 0 FAIL.
2. Run the oracle on the tests channel; it must be 1.0. Run the nop; it must be 0.0.
3. Re-score S0 to S5 with the P3 method and write `baselines.json` with `"round":1`.
4. Write `OUT/HARDEN_REPORT.md` with the before and after lever table, the validity fixes, new checks, new judge criteria, the gate results and the new baselines.

Stop after 3 harden rounds in total. Report "ROUND LIMIT".

Final reply: the levers that LEAKED and why (one line each), validity bugs fixed, new lever ids, the new check and criterion counts, S2 and S4 before and after, oracle and nop, and paths.
