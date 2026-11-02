# P9 harden r2: emberforge-vault-settlement, issued 22 Oct 2026 10:25 IST (from template P9 v1)

This file is saved at `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/prompts/issued/emberforge-vault-settlement/P9_harden_r2.md`. After any compaction, re-read it in full.

You are hardening one Harbor 0.24 bundle from real harness results. Edit in place. Never regenerate it and never use `--force`.

Read in full, in this order:
1. `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/prompts/templates/_COMMON_RULES.md`
2. `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/prompts/issued/_adhoc/20261022_round_notes.md` (binding for this round; it overrides the template steps where they differ)
3. `WORK/DESIGN.md`, `WORK/LEVERS.md`, `WORK/baselines.json`, then the inputs below.

## Inputs
- BUNDLE: `/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/emberforge-vault-settlement/` (converted task, not a generator archetype; the validator are advisory only, open question Q23)
- WORK: `/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/emberforge-vault-settlement/`
- Round 1 harden reports: `/Users/mac/Desktop/Terminal Bench/master_chat_work/20261021_emberforge-vault-settlement/harden_r1/{DIAGNOSIS.md,HARDEN_REPORT.md}`
- PL QC v1 (FAIL 3) and its recheck (12 REAL): `.../20261021_emberforge-vault-settlement/baseline_v0/qc_report_v1.md`, `.../recheck_r1/RECHECK.md` and `recheck.json`
- Real run (claude-opus-5): `.../baseline_v0/trajectory_job/trajectory/claude-opus-5/Run 1/` (agent/trajectory.json, artifacts/app/out/, verifier/). Reported tests 1.94 was a permission bug; corrected by Docker replay to tests 94.19 (146/155), rubric 84.21 (R1-R5 met, R9 honesty negative fired). Lost only structure_findings_canonical_form, cap_and_floor_one_findings (the QC's ambiguous S6/N3 reading), quiet_rules_findings. Re-score: `/Users/mac/Desktop/Terminal Bench/master_chat_work/20261021_v0-rescore/RESCORE_REPORT.md`.
- OUT: `/Users/mac/Desktop/Terminal Bench/master_chat_work/20261022_emberforge-vault-settlement/harden_r2/`

## Phase 1: diagnosis
Round 1 predicted a careful score of 0.168; the real agent scored 0.94. Read the trajectory in pieces and find out exactly how: for each round 1 lever (LV-EF-1..4, LV-EF-L7), the step where the agent read the rule, how it checked itself (the calibration slice? the shipped season?), and why the lever did not cost it. Build the lever table (points available, earned, HELD/LEAKED). Write `OUT/DIAGNOSIS.md`. If the diagnosis shows a cause that none of the fixes below addresses, stop and say "DIAGNOSIS CONFLICT: <path>"; otherwise continue to Phase 2 without stopping.

## Phase 2: Master's fixes (apply all)
1. Verifier permissions (round notes C): `_run_delivered` (test_output.py:2186-2194) runs `/app/out/settle_vault.py` as uid 4001 without opening it; the real run delivered it 0600 (probe: Errno 13). Stage a readable copy in a grader-made folder and run that; kill leftovers by uid.
2. Every REAL row in `recheck_r1/recheck.json`, with its listed fix (S6 salvage sentence added to rulebook_salvage.md and RULEBOOK_TEXTS; record_shapes.md separator wording; a season with two retired reagents in one edition; TRUTH requisition counts; negative_rebinds weight; R5 split; numeric JSON types stated; R7 replaced by an AST negative). The recheck notes JD-16 needs no positive-total change.
3. Hardness redesign from round notes B (the real run scored 94 on tests):
   - Remove anything that confirms the full answer: the published calibration slice with settled outputs (study rule 7, emberforge instruction line 5) goes, or keeps only evidence that decides individual rules without settled totals.
   - Instruction: remove the convention count ("four conventions") and any trap list in the final-reply ask; ask for computed figures instead.
   - Composition: today 40+ checks isolate one lever per reseeded season (test_output.py:3144-3173). Re-weight so at most about 30% of positive test weight is isolated; the rest grades whole settled documents downstream of the chain on reseeded seasons where two or three levers meet.
   - Add one decoy default contradicted by the authoritative rulebook on a rare boundary the shipped season shows, and one rule by omission or split across two files (study rules 4 and 5).
   - Judge: R1-R4 were met from visible-season values; replace them per round notes B.12. Keep the honesty negative (it fired, so it works).
4. `tests/test.sh`: keep `chmod 755 /logs/verifier`; `tests/Dockerfile`: add `litellm==1.105.0` to the rewardkit pip line (K8).

## Phase 3: verify, once
Run the gates in round notes D (validator advisory for this bundle; report them, fix only cheap ones).
Write `OUT/HARDEN_REPORT.md`: diagnosis summary, changes per fix, before/after lever table, new checks and judge criteria, isolated vs composed weight share, every gate result.

Stop after 3 harden rounds in total (this is round 2).

Final reply (12 lines max): the levers that LEAKED and why (one line each), fixes applied, new check and judge counts, isolated-weight share, oracle x2 / oracle-0600 / nop / forgery scores, QC results, what was not run, report path. Next step: Ayush runs the PL QC and 1 trajectory.
