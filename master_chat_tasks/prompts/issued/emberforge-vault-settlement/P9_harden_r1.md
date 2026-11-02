# P9 harden, emberforge-vault-settlement, round 1 (issued 21 Oct 2026 12:16 IST, from template P9 v1)

Open a NEW session in `/Users/mac/Desktop/Terminal Bench` and paste everything below the line. The session stops at "DIAGNOSIS READY" and waits for your "go". Bring the diagnosis path back to the master chat before you say "go".

Deviation from the template (logged): this task was not built by the master system, so Phase 0 copies it out of `QC assigned/` and Phase 1 builds the missing LEVERS.md and baselines.json first.

=== PASTE BELOW ===

You are hardening one Harbor 0.24 bundle using a real harness run (full trajectory, per-check verifier results and judge response). First you diagnose exactly what let the agent score. Then you replace or add mechanisms, never by hiding rules. Edit only the working copy named below. Never regenerate it and never use `--force`.

First read in full: `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/prompts/templates/_COMMON_RULES.md`. Then `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/knowledge/KNOWLEDGE.md`, `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/knowledge/qc_authoring_checklist_9b8229f6.md` and `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/prompts/templates/P3_hardness_check_v1.md` (its solver table S0 to S5 and method are used below).

## Inputs
- SLUG: `emberforge-vault-settlement`. Category "Data Processing". Author Ayush Sah. Not known to be a PL-generator scaffold: find out (see Phase 0).
- ORIGINAL (read only, never edit; `QC assigned/` is protected): `/Users/mac/Desktop/Terminal Bench/QC assigned/converted tasks/emberforge-vault-settlement/`
- BUNDLE (working copy you edit): `/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/emberforge-vault-settlement/`
- WORK (working notes): `/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/emberforge-vault-settlement/`
- RUN (read only, claude-opus-5, 1 run, 20 Oct 00:10 to 01:25 IST): `/Users/mac/Desktop/Terminal Bench/Harbor_Harness/Terminal_2.0_Harbor_Harness/jobs/emberforge-vault-settlement/trajectory/claude-opus-5/`
  - `pass_summary.json`: tests 68.0, rubric 100.0, combined 84.0
  - `Run 1/verifier/reward-details.json` (per-check results), `ctrf.json`, `reward.json`
  - `Run 1/judge_response.txt` (per-criterion judge verdicts)
  - `Run 1/agent/trajectory.json` (181 KB) and `openhands_sdk.txt` (245 KB): read with targeted searches and offsets, never paste them whole into your notes
  - `Run 1/artifacts/` (what the agent delivered)
- Note: that `Harbor_Harness/Terminal_2.0_Harbor_Harness/` is a second, older clone (b1ffb283). Use it only for the run files above. All QC and generator rules come from the paths in `_COMMON_RULES.md` (main clone, 9b8229f6).
- OUT: `/Users/mac/Desktop/Terminal Bench/master_chat_work/20261021_emberforge-vault-settlement/harden_r1/`

## Master's notes
1. Gate on every real run: tests < 90, rubric < 90, overall < 30. This run passes tests (68) but fails rubric (100) and overall (84). Both channels must drop: with tests near 0.20, overall < 30 needs rubric < 40. The judge is the bigger problem: every criterion passed.
2. Build-time targets (P3 table): S2 lazy at most 0.10, S4 careful 0.10 to 0.20, S1 stub at most 0.25, every S3.k loses points, oracle exactly 1.0.
3. A file named `calibration_reference_bundle.json` ships with the data. Check whether it is a labelled answer key that lets the agent fit graded rules (a known leak pattern). Quote what it contains before judging.
4. Rubric: replace criteria that any run passes with outcome criteria a typical run can genuinely fail, taken from the agent's actual mistakes and skipped verifications in the trajectory. Each must be true of any correct solution (JD-7), met by every competent approach (JD-15), read nothing a test reads (JD-8), use positive grammar and counts, and include one code-quality criterion (JD-18).
5. New levers: several (not one). Keep A (hidden composition of documented rules) and B (dependent chain), plus 1 or 2 of C audit-and-repair, D size ladder, E stacked orthogonal constraints, F rejection and error paths. Candidates are in `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/registry/levers.json` (read only). Give each new lever an id `LV-EF-<n>`.
6. Keep the artifact list in `task.toml` unchanged unless the diagnosis proves a change is needed; if so, propose it and wait.
7. If the validator and QC disagree on TRUTH.md provenance (VB 15.5 vs DS-27), keep what the bundle has and write `OPEN CONFLICT Q18`; do not invent a third option.
8. Caps: up to 70 tests and 70 judge criteria.

## Phase 0: copy and intake (no edits to ORIGINAL or RUN)
1. Check the fingerprints (common rule 1).
2. If BUNDLE or WORK already exists, stop and report; do not overwrite.
3. Copy ORIGINAL to BUNDLE (`cp -Rp`). Write the sha256 tree of ORIGINAL to `OUT/original_tree.sha256` and confirm the copy matches.
4. Confirm the run was made on this bundle version: compare `Run 1/agent/instruction.txt` with `instruction.md`, and the test and judge counts in `reward-details.json` and `judge_response.txt` with `tests/test_output.py` and `tests/judge.toml`. Report any difference; if the bundle changed after the run, say which files.
5. Decide whether it fits a PL archetype: compare `task.toml` artifacts with each archetype in `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/knowledge/archetypes.md`. If one matches, use `--archetype <it>` for the validator; if none matches, run the validator without it and record that VB 1.12 does not apply.
6. Run the 4 live QC scripts once on the untouched copy and record FAIL and WARN lines (this is the before state, not a fix list).

## Phase 1: diagnose (no bundle edits)
1. Build `WORK/LEVERS.md`: one row per check in `tests/test_output.py` with its lever (name the levers from TRUTH.md and the spec), weight, the observable it reads, and the run result (pass or fail from `reward-details.json`), plus totals per lever.
2. Lever table: lever, points available, points earned in the run, status (HELD if the agent lost them, LEAKED if it earned them).
3. Judge table: every criterion, its verdict in `judge_response.txt`, and why the run passed it (trivially true, effort-based, overlaps a test, or genuinely met).
4. For each LEAKED lever, name what made it derivable: a visible example or reference output that separates the readings, a spec sentence placed next to its use, a check the reflex reading passes by accident, or a self-test the agent ran. Quote the trajectory step (step index) or the file line.
5. For each HELD lever, quote the step where the agent went wrong: this tells us which mechanisms work.
6. Score S0 to S5 on the current bundle with the P3 method (write the wrong solvers in WORK). Write `WORK/baselines.json` in the P3 shape with `"round":0`. Find the solver whose score matches the run's 68 most closely and say which reading that implies.
7. List the agent's mistakes and skipped verifications that can become judge criteria.
8. Write `OUT/DIAGNOSIS.md` (at most 90 lines: version check, lever table, judge table, leak causes with quotes, held causes, baselines, proposed new levers with their reflex readings, proposed judge criteria). Stop and say "DIAGNOSIS READY: <path>". Wait for Ayush to reply "go" (he may pass on changes from the master chat).

## Phase 2: harden (after "go")
- Remove or neutralise any answer key or reference output that lets the agent fit a graded rule (the rule itself stays written).
- Replace each LEAKED mechanism with a HIDDEN-ONLY one, or add separating hidden cases so that the run's reading now fails.
- Add the approved NEW levers. Each needs the rule text, the reflex reading, the constructed hidden cases, and checks that the wrong solver fails.
- Rewrite the judge as approved in the diagnosis.
- Keep partial credit: checks stay independent, and downstream stages are graded on supplied correct inputs.
- Apply common rule 6 after any data edit. Write `WORK/DESIGN.md` with a "Harden round 1" section, and update LEVERS.md and TRUTH.md.

## Phase 3: verify, once
1. Run the 4 QC scripts, the validator (as decided in Phase 0 step 5) and playground static, with 0 FAIL.
2. Run the oracle on the tests channel; it must be 1.0. Run the nop; it must be 0.0.
3. Re-score S0 to S5 with the P3 method and write `baselines.json` with `"round":1`. Also re-score the run's own delivered program from `Run 1/artifacts/` against the new tests (copy it to scratch first) and report its new tests score.
4. Write `OUT/HARDEN_REPORT.md` with the before and after lever and judge tables, new checks, new criteria, the gate results and the new baselines.

Stop after 3 harden rounds in total. Report "ROUND LIMIT".

Final reply: the levers that LEAKED and why (one line each), judge criteria replaced, new lever ids, the new check and criterion counts, S2 and S4 before and after, the run's program re-scored, oracle and nop, and paths.
