# Low-score 10-task study: PROGRESS

Brief: `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/prompts/issued/_adhoc/20261022T0105_lowscore_10task_study.md`

Phase: B_done

| NN | slug | status | owner | steps done (1-9) | report | step 2 label |
|---|---|---|---|---|---|---|
| 01 | assay-plate-triage | done | bg_432319f9 / ses_ea0001393ffeXybQ1JcQPz5zVY | 1-9 | tasks/01_assay-plate-triage.md | GENUINE (2 EXEC passed under setpriv; 27/0 verified) + same bit-position design cap as 06 (42/90) |
| 02 | modulus-sieve-replay | done | bg_432319f9 / ses_ea0001393ffeXybQ1JcQPz5zVY | 1-9 | tasks/02_modulus-sieve-replay.md | GENUINE (4 EXEC checks passed under setpriv incl. empty_pass_reports_are_written; 28/0 verified) |
| 03 | inference-gate-replay | done | bg_432319f9 / ses_ea0001393ffeXybQ1JcQPz5zVY | 1-9 | tasks/03_inference-gate-replay.md | GENUINE (6 EXEC checks passed under setpriv, e.g. throughput_normalisation_gain; 25/0 verified) |
| 04 | speculative-decode-arbiter | done | bg_432319f9 / ses_ea0001393ffeXybQ1JcQPz5zVY | 1-9 | tasks/04_speculative-decode-arbiter.md | GENUINE (fired nondeterminism negative proves driver ran exit 0 twice as nobody; tests stage a readable copy; 18/1 verified) |
| 05 | quillfen-sla-settlement-repair | done | bg_57a7adaf / ses_ea0001380ffetRMVF6oOM1XxxW | 1-9 | tasks/05_quillfen-sla-settlement-repair.md | GENUINE (EXEC checks e.g. job_identity, schedule_probe passed; tests chmod unpacked tree 0755/0644; 17/1 verified) |
| 06 | grain-intake-settlement | done | bg_57a7adaf / ses_ea0001380ffetRMVF6oOM1XxxW | 1-9 | tasks/06_grain-intake-settlement.md | SUSPECT-design (EXEC passed, no permission issue; 78/94 grade bit positions no shipped file identifies; this run's failure itself genuine; 28/0 verified) |
| 07 | fdc5a20d-2dfe-5f64-a3fa-2c023318a760 | done | bg_57a7adaf / ses_ea0001380ffetRMVF6oOM1XxxW | 1-9 | tasks/07_fdc5a20d-2dfe-5f64-a3fa-2c023318a760.md | SUSPECT (0/27 EXEC passed incl. trivial ones, 4/4 READ passed; traj step 13 shows -rw------- derive_report.py; run as uid 65532 with no chmod; 27/0 verified) |
| 08 | registry-lock-footprint-resolution | done | bg_141e6fe9 / ses_ea000136dffeQyZxD2FiM2lADO | 1-9 | tasks/08_registry-lock-footprint-resolution.md | SUSPECT (0/27 EXEC passed; traj shows optimize.py -rw-------, no chmod before setpriv nobody; master verified 28/0 counts) |
| 09 | ninefold-crown-settlement-recompute | done | bg_141e6fe9 / ses_ea000136dffeQyZxD2FiM2lADO | 1-9 | tasks/09_ninefold-crown-settlement-recompute.md | SUSPECT (0/19 EXEC passed incl. 3 clean-exit manifest checks, 8/8 READ byte-exact; program never chmodded; false -5 replayer fire; 19/1 verified) |
| 10 | reefer-power-dispatch-recompute | done | bg_141e6fe9 / ses_ea000136dffeQyZxD2FiM2lADO | 1-9 | tasks/10_reefer-power-dispatch-recompute.md | GENUINE (0/9 EXEC passed, but 4/5 READ shipped blocks fail on the shipped day; permission hazard present, not needed; 13/0 verified) |

Subagent step progress is read from each `notes/<NN>.md` (subagents never write this file).

Approved Phase B tasks: operator text "approved: 07, 08, 09" at 2026-10-22 09:18 IST (03:48 UTC)

Phase B runs (V600 / V644): 07 done: V600 0.1569 = record (0 diffs), V644 1.0 (+27 checks) | 08 done: V600 0.0216 = record (0 diffs), V644 0.4173 (+11 trap checks) | 09 done: V600 0.1529 = record (0 diffs), V644 1.0 (+19 positives, -5 brand gone) (runner /tmp/lowscore-study-20261022T0105/run_seq.sh, logs /tmp/opencode-logs/lowscore-study-20261022T0105/, jobs /tmp/lowscore-study-20261022T0105/jobs/lsr-<NN>-<V>)

Next action: none. Phase B done 09:30 IST; reports 07/08/09 have Phase B sections; SYNTHESIS section 8 added; scratch /tmp/lowscore-study-20261022T0105 deleted (logs kept in /tmp/opencode-logs/lowscore-study-20261022T0105/).
