# P9 harden r2: district-heat-flex-procurement, issued 22 Oct 2026 10:25 IST (from template P9 v1)

This file is saved at `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/prompts/issued/district-heat-flex-procurement/P9_harden_r2.md`. After any compaction, re-read it in full.

You are hardening one Harbor 0.24 bundle from real harness results. Edit in place. Never regenerate it and never use `--force`.

Read in full, in this order:
1. `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/prompts/templates/_COMMON_RULES.md`
2. `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/prompts/issued/_adhoc/20261022_round_notes.md` (binding for this round; it overrides the template steps where they differ)
3. `WORK/DESIGN.md`, `WORK/LEVERS.md`, `WORK/baselines.json`, then the inputs below.

## Inputs
- BUNDLE: `/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/district-heat-flex-procurement/` (archetype `domain-calculation`)
- WORK: `/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/district-heat-flex-procurement/`
- Round 1 harden report: `/Users/mac/Desktop/Terminal Bench/master_chat_work/20261021_district-heat-flex-procurement/harden_r1/HARDEN_REPORT.md`
- PL QC v1 (FAIL 11) and its recheck (18 REAL, 1 FALSE POSITIVE CL-2, 2 UNSURE): `.../20261021_district-heat-flex-procurement/baseline_v0/qc_report_v1.md`, `.../recheck_r1/RECHECK.md` and `recheck.json`
- Real runs (claude-opus-5): both timed out at the 7200 s agent limit with no score. No trajectory.json was saved; the agent's full session logs are `.../baseline_v0/trajectory_job_20261021T173139_timeout/trajectory/claude-opus-5/Run 1/agent/openhands_sdk.txt` and `.../baseline_v0/trajectory_job_2026-10-21__23-29-37_timeout/trajectory/claude-opus-5/Run 1/agent/openhands_sdk.txt`; delivered files are under each `artifacts/app/out/`. Summary: `.../baseline_v0/TRAJECTORY_RESULT.md`.
- OUT: `/Users/mac/Desktop/Terminal Bench/master_chat_work/20261022_district-heat-flex-procurement/harden_r2/`

## Phase 1: short diagnosis (the master has already diagnosed; confirm, do not repeat)
Read the two session logs in pieces. Confirm or correct: the program ran in about 1-8 s on the shipped data, and the agent spent the remaining time building and timing its own 20-22-site stress cases (21-23 s in run 1, 54-120 s with self-kills at 120 s in run 2) against the instruction's 30-second limit until the 2-hour budget ran out. Also note where its program would have lost points (read its derive_report.py against the rules; mark UNVERIFIED). Write `OUT/DIAGNOSIS.md`. If your diagnosis contradicts the master's in a way that changes the fixes below, stop and say "DIAGNOSIS CONFLICT: <path>"; otherwise continue to Phase 2 without stopping.

## Phase 2: Master's fixes (apply all)
1. Timing (the cause of both lost runs): rework LV-DH-1 so a correct, straightforward solution finishes the largest graded case in a few seconds and the task's own time limit does not invite open-ended load testing. Options: drop the per-run time target from the instruction and grade correctness only on sizes where exact search is cheap, or keep a size ladder but state a generous limit (for example 10x the oracle's slowest time) and size the hidden cases so the oracle stays under 2 s. Measure the oracle's wall time on every graded case and report it. The agent limit stays 7200 s.
2. Verifier permissions (round notes C): `run_agent` (test_output.py:897-927) runs derive_report.py in place as nobody; both real runs delivered it as 0600. Stage a readable copy or open it and its parents. Also fix the setsid daemon that rewrites cached out/ folders (cache the parsed JSON, kill by uid).
3. Every REAL row in `recheck_r1/recheck.json`, with its listed fix (waiver count wording; independent solve.py search without the dead scale knob; at most 4 offers per site in hidden extracts; the 4 untriggered rules; R9 split and true of the reference; R10 target; R5/R13/R15 replaced; TRUTH rejected-row counts and root-cause wording; TS-14 description; negative path matching). No change for the FALSE POSITIVE (CL-2). Leave the two UNSURE rows (JD-15 R4, TS-20) as they are and list them.
4. Judge: replace every criterion that rewards effort or restates schema.md (R1-R8 and the rest) per round notes B.12; the round 1 go message named only some IDs, so apply the rule to all criteria.
5. Hardness redesign from round notes B: remove rule counts and trap topics from the instruction and the final-reply ask (study: district instruction lines 15 and 19-24); grade whole region and segment documents downstream of the portfolio choice on hidden extracts, with at most about 30% on isolated cases; make the derivable funded-pool lever DH-3 (careful solver 0.381 when right) count only through composed cases; add one decoy default and one rule by omission or split across files (study rules 4 and 5).
6. `tests/test.sh`: keep `chmod 755 /logs/verifier`; `tests/Dockerfile`: add `litellm==1.105.0` to the rewardkit pip line (K8).

## Phase 3: verify, once
Run the gates in round notes D (validator with `--archetype domain-calculation`). Also report the oracle's wall time per graded case.
Write `OUT/HARDEN_REPORT.md`: diagnosis summary, changes per fix, before/after lever table, new checks and judge criteria, isolated vs composed weight share, every gate result, oracle timings.

Stop after 3 harden rounds in total (this is round 2).

Final reply (12 lines max): the timing fix and the largest-case oracle time, fixes applied, new check and judge counts, isolated-weight share, oracle x2 / oracle-0600 / nop / forgery scores, QC and validator results, what was not run, report path. Next step: Ayush runs the PL QC and 1 trajectory.
