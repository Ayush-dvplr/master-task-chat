# P4 rebuild r1: schema-migration-plan-repair, issued 22 Oct 2026 10:25 IST (from template P4 v1)

This file is saved at `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/prompts/issued/schema-migration-plan-repair/P4_rebuild_r1.md`. After any compaction, re-read it in full.

You are strengthening one Harbor 0.24 bundle that both the hardness audit and a real run showed is far too easy. Edit the bundle in place. Never regenerate it and never use `--force`.

Read in full, in this order:
1. `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/prompts/templates/_COMMON_RULES.md`
2. `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/prompts/issued/_adhoc/20261022_round_notes.md` (binding for this round; it overrides the template steps where they differ)
3. `WORK/DESIGN.md`, `WORK/LEVERS.md`, then the inputs below.

## Inputs
- BUNDLE: `/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/schema-migration-plan-repair/` (archetype `repo-patch`)
- WORK: `/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/schema-migration-plan-repair/`
- HARDNESS REPORT (P3 r1): `/Users/mac/Desktop/Terminal Bench/master_chat_work/20261021_schema-migration-plan-repair/hardness_r1/HARDNESS_REPORT.md`
- PL QC v1 (FAIL 8) and its recheck (9 REAL, 1 UNSURE): `.../20261021_schema-migration-plan-repair/baseline_v0/qc_report_v1.md`, `.../recheck_r1/RECHECK.md` and `recheck.json`
- Real run (claude-opus-5, valid): `.../baseline_v0/TRAJECTORY_RESULT.md` and `.../baseline_v0/trajectory_job_2026-10-21__23-36-45_4a1262/`. Score: tests 99.3, rubric 69.57, overall 84.44; it lost only module_core_claims_match_archive.
- Live repo-patch template (layout reference, read only): `/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness/Input Bundle Generator New/templates/repo-patch/`
- OUT: `/Users/mac/Desktop/Terminal Bench/master_chat_work/20261022_schema-migration-plan-repair/rebuild_r1/`

## Master's fixes (apply all)
1. Re-layout to the live repo-patch format: `environment/data/repo.zip` becomes `environment/repo/` (the package) plus `environment/ci/` (contract and CI inputs), with matching `COPY --chown=1000:1000 repo /app/repo` and `COPY ci /app/ci` lines; update instruction paths, tests, solve.sh/solve.py, TRUTH.md and the artifacts list so validator sections 1.4 and 5.5 pass. Today the verifier is permission-safe only because `_unpack` rewrites modes to 0644/0755 (test_output.py:7073-7086); after the re-layout the tests read the agent's repo directly, so apply round notes C to whatever the tests copy or run.
2. Every REAL row in `recheck_r1/recheck.json`, with its listed fix. Notes from the recheck: the tie fixture must use a plan the shipped search cannot take (the shipped parser already sorts edges, parser/contracts.py:158); TS-17 only the int/float half is reachable; TS-24 must also kill processes owned by nobody (setsid escapes killpg); category becomes "Software Engineering". Leave the UNSURE row (JD-5 on R14) as is and list it in the report.
3. From P3: rebuild P6, X6, X7 and Q1 so the shipped (unrepaired) code fails them; module claims must read code, not docstrings; add the untested levers P3 named (a correction pinned at the canonical schema, a holder that fails planning, an empty partner token line); regenerate the visible graph and feed so the right and reflex readings agree on them (all 10 levers were DERIVABLE).
4. Hardness redesign from the round notes B (the real run scored 99.3 on tests):
   - Instruction: remove the rule count (study: schema instruction line 3) and any trap list in the final-reply ask; ask for computed figures. Keep it short and plain.
   - Composition: at most about 30% of positive test weight on rule-isolating checks; the rest grades whole pipeline outputs on hidden inputs where three or more of the levers meet, downstream of the planning stage.
   - Add at least one rule placed by omission or split across two files, and one decoy default (for example a legacy runbook or shipped default in the repo) contradicted by the authoritative contract on a rare boundary the shipped feed shows (study rules 4 and 5).
   - Judge: replace R7-R13 (they restate rules the tests grade) per round notes B.12.
5. `tests/test.sh`: keep `chmod 755 /logs/verifier`; `tests/Dockerfile`: add `litellm==1.105.0` to the rewardkit pip line (K8).

## Steps
1. Write the change plan in `WORK/PLAN.md` under "Rebuild round 1 (22 Oct)": one line per fix, and what wrong reading each new check fails.
2. Apply the changes; update `LEVERS.md`, `DESIGN.md` ("Round 1 changes") and TRUTH.md; follow round notes E on the stale `_work` scripts (make_judge.py, make_truth.py, make_shipped.py, embed.py ...).
3. Run the gates in round notes D, once each (validator with `--archetype repo-patch`).
4. Write `OUT/REBUILD_REPORT.md`: changes per fix, files touched, the new layout, new check count and positive-weight share per lever, isolated vs composed weight share, every gate result, and the judge-by-reading check.

Stop after 3 rebuild rounds in total for this bundle (this is round 1).

Final reply (12 lines max): DONE or BLOCKED, fixes applied, new check and judge counts, isolated-weight share, oracle x2 / oracle-0600 / nop / forgery scores, QC and validator results (1.4 and 5.5 must pass), what was not run, report path. Next step: Ayush runs the PL QC and 1 trajectory.
