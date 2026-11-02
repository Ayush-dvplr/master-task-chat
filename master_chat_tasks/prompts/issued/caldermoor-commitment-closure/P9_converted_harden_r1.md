# Converted harden-rebuild r1: caldermoor-commitment-closure, issued 22 Oct 2026 15:52 IST (from template P9 v1)

This file is saved at `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/prompts/issued/caldermoor-commitment-closure/P9_converted_harden_r1.md`. After any compaction, re-read it in full, then the two notes files, then `_work/caldermoor-commitment-closure/TODO.md`.

You are hardening one converted Harbor 0.24 task from a real harness result. Edit the COPY in place. Never regenerate, never `--force`.

Read in full, in this order:
1. `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/prompts/templates/_COMMON_RULES.md`
2. `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/prompts/issued/_adhoc/20261022_round_notes.md`
3. `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/prompts/issued/_adhoc/20261022_converted_batch_notes.md` (its section 2 REPLACES round notes section A; that is intended, not a conflict)
4. `/Users/mac/Desktop/Terminal Bench/master_chat_work/20261022_lowscore-study/SYNTHESIS.md` section 6, and `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/registry/levers.json`

## Inputs
- SOURCE (read only): `/Users/mac/Desktop/Terminal Bench/QC assigned/converted tasks/caldermoor-commitment-closure/`
- BUNDLE (copy here first, batch notes 1): `/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/caldermoor-commitment-closure/`
- WORK (create, batch notes 5): `/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/caldermoor-commitment-closure/`
- QC history: `/Users/mac/Desktop/Terminal Bench/QC assigned/qc_report/caldermoor-commitment-closure/` — latest report `v3.md`, latest fix plan `fixplan_v3.md` (read triage files only if a FAIL is unclear)
- Conversion notes: `/Users/mac/Desktop/Terminal Bench/QC assigned/converted_tasks_report/caldermoor-commitment-closure.conversion_notes.md` and `caldermoor-commitment-closure.verify.md`
- Real run (claude-opus-5, recorded reward 0.8722, no judge key): `/Users/mac/Desktop/Terminal Bench/Harbor_Harness/Terminal_2.0_Harbor_Harness/jobs/caldermoor-commitment-closure/trajectory/claude-opus-5/Run 1/`
- OUT: `/Users/mac/Desktop/Terminal Bench/master_chat_work/20261022_caldermoor-commitment-closure/harden_r1/`

## Phase 0: setup
Check HEAD (batch notes 2). Copy SOURCE to BUNDLE and the job folder to `OUT/baseline_v0/` (batch notes 3). Record the copied bundle tree sha (sha256 over sorted file paths + contents) in `WORK/baselines.json`. Create the WORK files.

## Phase 1: diagnosis (do not stop after it unless a conflict)
1. From ctrf.json / reward.json: tests-channel score, judge state, and whether the permission trap fired (batch notes 3).
2. Read the trajectory in pieces. Reconstruct the task's existing difficulty levers into `WORK/LEVERS.md` (rule, reflex reading, which checks grade it, family A-F). For each: the step where the agent read the rule, how it checked itself, HELD or LEAKED, and what made it derivable (visible example, rule next to its use, a check the reflex reading passes, a self-test). Quote the step or file line.
3. Score composition: share of positive test weight on rule-isolating checks and on shipped-data-only checks (study rules 6 and 11).
4. Write `OUT/DIAGNOSIS.md`. If you find a cause none of Phase 2 addresses, stop and say "DIAGNOSIS CONFLICT: <path>".

## Phase 2: fixes (apply all)
1. Mandatory format: K8 litellm pin, `_grant_read()` / round notes C permission fix with kill-by-uid, judge header `mode = "batched"` (batch notes 2). Keep `chmod 755 /logs/verifier`.
2. Re-check every FAIL and WARN in `v3.md` against the live QC at HEAD; fix any still open.
3. Hardness redesign (batch notes 4, study rules 1-13): remove anything that confirms the full answer; drop rule counts and trap lists from the instruction; at least one scope-by-omission or split-across-files rule; one decoy default contradicted on a rare shipped boundary; route it through a dependent chain; re-weight so isolated checks are at most ~30% and shipped-data-only checks at most 5%; grade whole downstream documents on reseeded hidden inputs. Levers A + B + 1-2 of C-F, several new levers, not a repeated set.
4. Judge: replace criteria a competent agent meets from visible values; one figure per criterion needing the full chain; keep or add one honesty negative; one code-quality criterion.
5. Update DESIGN.md ("Harden round 1"), LEVERS.md, TRUTH.md; common rule 6 after any data edit.

## Phase 3: gates, once
Batch notes section 6. Write `OUT/HARDEN_REPORT.md` as each gate finishes: diagnosis summary, changes per fix, before/after lever table, new check and criterion counts, isolated / shipped-only weight shares, every gate result, what was not run.

Final reply (12 lines max): tests-channel score of the v0 run and whether the trap fired, levers that LEAKED (one line each), new lever ids and families, check and criterion counts, isolated-weight share, oracle x2 / owner-only / oracle-0600 / nop / forgery, QC results, report path. Next step: Ayush runs PL QC, P8, P7, then 1 trajectory.
