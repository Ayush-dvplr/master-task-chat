VERDICT: Fix the QC template contradictions first, make worker and Docker waits observable, and pilot contract-grounded hidden cases before building another task.

`TB` means `/Users/mac/Desktop/Terminal Bench`. Paths in links are relative to this report. This is a learning report; no task, template, worker, or Docker state was changed.

## Coverage

All six sessions have `FINDINGS.md`, `QUESTIONS.md`, extras, and `result.json` marked `DONE` ([L1](../L1_qc_fixes/result.json), [L2](../L2_qc_kit_map/result.json), [L3](../L3_auto_problems/result.json), [L4](../L4_docker/result.json), [L5](../L5_stage2_study/result.json), [L6](../L6_web_ideas/result.json)). None is missing or marked PARTIAL. L2's note that L1 `FINDINGS.md` was absent describes an earlier read; it exists now ([L1 findings](../L1_qc_fixes/FINDINGS.md):1-7; [L2 findings](../L2_qc_kit_map/FINDINGS.md):19). The audit script reads the summary CSVs and prints 585 QC finding rows, 303 kit rows, 93 auto-linked sessions, 552 image rows and 15 ranked stage-2 runs ([script](scripts/audit_synthesis.py); `python3 scripts/audit_synthesis.py` output).

## Top 10 lessons

1. **Final QC needs five oracle runs.** The live kit explicitly requires five fresh 1.000 runs; P2 and P12 still prescribe three. Correct the templates before the next sign-off ([kit](../../../Terminal_2.0_Harbor_Harness/Input_Bundle_QC/Final_checklist.md):354-390; [P2](../../../master_chat_tasks/prompts/templates/P2_build_v5.md):132; [P12](../../../master_chat_tasks/prompts/templates/P12_recheck_fix_v4.md):67).
2. **A small honest artifact score is allowed.** The kit fails content-blind credit or a forgery in genuine-partial range, whereas P2/P12 say any positive score fails. Record paying checks and their weights ([kit](../../../Terminal_2.0_Harbor_Harness/Input_Bundle_QC/Final_checklist.md):418-420,489; [P2](../../../master_chat_tasks/prompts/templates/P2_build_v5.md):137; [P12](../../../master_chat_tasks/prompts/templates/P12_recheck_fix_v4.md):62).
3. **Fixes need a cross-file receipt.** L1 indexed 27 new-finding/shared-edit links; cold-chain v5 added a 30/31 cold-room contradiction and raised checks from 33 to 54 after a prose fix. These are temporal links, not isolated causes ([L1](../L1_qc_fixes/FINDINGS.md):15-19; [cold-chain QC](../../../QC/reports/cold-chain-backbone-quote/v5.md):386-393).
4. **Trigger every promised rule.** AL-27 requires a graded input where breaking one rule changes the result; empty rule maps and correct-sounding test names are insufficient. L1 found AL-27 across 13 tasks ([kit](../../../Terminal_2.0_Harbor_Harness/Input_Bundle_QC/05_Alignment_Integrity_QC.md):38; [L1 recipes](../L1_qc_fixes/FIX_RECIPES.md):31-39).
5. **Low score and valid run are different from QC-safe difficulty.** L5 found 102 recorded Opus runs meeting its file/score consistency gate, yet the foundry author truth calls two graded rules withheld. Require reachability and uniqueness proof before borrowing inverse tasks ([L5](../L5_stage2_study/FINDINGS.md):5-21; [foundry truth](../../../anubis-stage-2/aa314fee-a873-5778-9d55-e8892e6d7cda/solution/TRUTH.md):7-10).
6. **Preserve partial credit and failure cause.** Royalty's scenario checks hash all nine reports, and `_holds` turns every exception into false. A one-fact perturbation and WRONG/TIMEOUT/CRASH logging are needed before copying that pattern ([royalty tests](../../../anubis-stage-2/75407a55-6665-505e-95d8-5ff9bdb3384f/tests/test_output.py):74-115; [CL-4](../../../Terminal_2.0_Harbor_Harness/Input_Bundle_QC/Final_checklist.md):491; [L5](../L5_stage2_study/PATTERNS.md):19-22).
7. **The worker freezes were shared, but their layer is unknown.** Two event-delivery gaps coincide with ten session pauses, while `auto.py` only detects a stall when every active worker is old. A per-worker progress check and independent watcher test are warranted; provider, host and runtime cause remain UNVERIFIED ([events](../../../master_chat_tasks/auto/runs/20261027T2239_overnight/events.jsonl):19-20,47-48; [auto.py](../../../master_chat_tasks/auto/auto.py):1492-1512; [L3](../L3_auto_problems/FINDINGS.md):11-18).
8. **Polling costs tool time, not proven wall time.** The 93 auto-linked sessions contain 987 sleep calls, 2,183.7 summed minutes, and 240 `docker ps` sleeps. Replace repeated own-job polls with one bounded completion wait and a job manifest; measured wall saving is UNVERIFIED ([L3 CSV](../L3_auto_problems/POLL_STATS.csv); [audit script](scripts/audit_synthesis.py); [common rules](../../../master_chat_tasks/prompts/templates/_COMMON_RULES_v5.md):35,50).
9. **Docker cleanup should be narrow and measured.** The saved snapshot has 60 parked/dropped and 24 dangling image rows, plus 38 unresolved rows; Buildx reports 18.73 GB cache accounting. Preserve live/pushed images and verify current state before any later deletion; physical bytes freed are UNVERIFIED ([image inventory](../L4_docker/IMAGES.csv); [Buildx snapshot](../L4_docker/inventory/buildx_du_verbose.txt):7914-7917; [cleanup plan](../L4_docker/CLEANUP.md):1-61).
10. **Select ideas with an early wrong-output witness.** L6's rolling-reservations pilot is a hypothesis, not a score forecast. The existing design-blind rule and earlier parked builds support testing three hidden seeds and a strong generic solver before a full bundle ([L6 ideas](../L6_web_ideas/IDEAS.md):5-13,20-23; [lever rule](../../../master_chat_tasks/knowledge/LEVER_RULES_v3.md):227-244; [S5](../../../master_chat_work/20261030_upgrade2/S5_build_method/FINDINGS.md):5-9).

## Ten source spot-checks

Each row compares one load-bearing session claim with the cited source. `RIGHT` means the cited source supports that narrow claim; it does not validate the entire session.

| # | Claim checked | Result | Direct source |
|---:|---|---|---|
| 1 | L1: 95 QC versions | RIGHT | `find TB/QC/reports -maxdepth 2 -name 'v*.md' -type f \| wc -l` → `95`; [L1](../L1_qc_fixes/FINDINGS.md):3-5 |
| 2 | L1: cold-chain v5 gained 30/31 contradiction and 54 checks | RIGHT | [v5 comparison](../../../QC/reports/cold-chain-backbone-quote/v5.md):389-393 |
| 3 | L2: kit requires five fresh oracle scores of 1.000 | RIGHT | [Step 10](../../../Terminal_2.0_Harbor_Harness/Input_Bundle_QC/Final_checklist.md):354-390 |
| 4 | L2: P2 and P12 ask for three | RIGHT | [P2](../../../master_chat_tasks/prompts/templates/P2_build_v5.md):132; [P12](../../../master_chat_tasks/prompts/templates/P12_recheck_fix_v4.md):67 |
| 5 | L2: kit permits small artifact-presence credit | RIGHT | [stub and CL-2](../../../Terminal_2.0_Harbor_Harness/Input_Bundle_QC/Final_checklist.md):418-420,489 |
| 6 | L3: two long watcher delivery gaps | RIGHT | [event timestamps](../../../master_chat_tasks/auto/runs/20261027T2239_overnight/events.jsonl):19-20,47-48 |
| 7 | L3: current stall rule waits until all active workers are old | RIGHT | [auto.py](../../../master_chat_tasks/auto/auto.py):1492-1504 |
| 8 | L4: snapshot has 552 images in stated categories | RIGHT | `python3 scripts/audit_synthesis.py` → `552`, `342 pushed`, `83 live`, `60 parked/dropped`, `24 dangling`, `38 unresolved`, `5 base`; [CSV](../L4_docker/IMAGES.csv) |
| 9 | L4: Buildx reports 18.73 GB total, 8.517 shared | RIGHT | [saved Buildx output](../L4_docker/inventory/buildx_du_verbose.txt):7914-7917 |
| 10 | L5: foundry truth calls two graded rules withheld | RIGHT | [author truth](../../../anubis-stage-2/aa314fee-a873-5778-9d55-e8892e6d7cda/solution/TRUTH.md):7-9 |

No spot-check was WRONG. The checks do not establish causal gains, current Docker state, or whether the stage-2 examples would pass our full QC.

## Ranked changes: rules/templates

| Rank | What and where | Expected gain | Risk | How to check |
|---:|---|---|---|---|
| 1 | Change final QC targets to five fresh oracle runs in `prompts/templates/P2_build_v5.md` and `P12_recheck_fix_v4.md`. | Kit-complete sign-off; two more determinism samples. | Longer QC. | Five distinct fresh results, each 1.000, tied to frozen tree; [kit](../../../Terminal_2.0_Harbor_Harness/Input_Bundle_QC/Final_checklist.md):354-390. |
| 2 | Correct vacuity text in P2/P12 and `knowledge/QC_FIX_PLAYBOOK_v3.md`; price each paying check. | Avoid false failure of legitimate small credit; expose content-blind reward. | Subjective threshold. | Run stub and plausible forgery; report positive-weight share and test IDs; [CL-2](../../../Terminal_2.0_Harbor_Harness/Input_Bundle_QC/Final_checklist.md):489. |
| 3 | Add rule/observable map, one-rule mutant, and changed-file receipt to P2/P12 and playbook. Regenerate `TRUTH.md` last. | Fewer AL-27 and stale-prose returns; gain INFERRED. | More work and possible test-count growth. | Recheck every touched rule against AL-27, DS-22, TS-23 and CL-4; [L1](../L1_qc_fixes/FINDINGS.md):11-25; [L2 checklist](../L2_qc_kit_map/BUILD_CHECKLIST_DRAFT.md):1-22. |
| 4 | Put a read-only run-learning card beside TRIP: first separating input, first wrong assumption, per-check cause, seed vector, judge evidence. | Better diagnosis; gain INFERRED. | Extra review time. | Apply to one high and one low frozen past run without changing official scores; [L6](../L6_web_ideas/FINDINGS.md):23-27. |

## Ranked changes: auto mode

| Rank | What and where | Expected gain | Risk | How to check |
|---:|---|---|---|---|
| 1 | Require a detached-job manifest, completion sentinel and bounded wait in `_COMMON_RULES_v5.md`, P11/P12, and `auto/runs/<run>/`. | Fewer repeated polls and duplicate launches; wall gain UNVERIFIED. | Stale sentinel or hidden failure. | Fake success, nonzero exit, hung job and lost sentinel; verify result/tree identity; [L3](../L3_auto_problems/FINDINGS.md):21-29. |
| 2 | Add per-worker `WORKER_STALL` and child ownership checks near `auto.py:1346-1512`; do not mark done before expected result exists. | Detect one stalled worker beside active peers. | False alert during long tool; duplicate resume. | Replay [20 episodes](../L3_auto_problems/SLEEP_CASES.csv), plus live-heartbeat control; [auto.py](../../../master_chat_tasks/auto/auto.py):1346-1358,1492-1512. |
| 3 | Dry-run an independent watcher for `auto.py` heartbeat; make resume audit pending work. | Alert during watcher-only silence; no proven host-wide rescue. | Duplicate watcher or false restart. | Simulate watcher-only and host-wide pauses; one leader and one GAP each; [L3](../L3_auto_problems/FINDINGS.md):37-49. |

## Ranked changes: Docker

| Rank | What and where | Expected gain | Risk | How to check |
|---:|---|---|---|---|
| 1 | Replace fixed worker-count/empty-Docker waits in `AUTO_POLICY.md` and P11 with a shared CPU/memory admission lease. | Targets one documented 102-minute foreign-slot wait; wider gain UNVERIFIED. | OOM or paid-run starvation. | Controlled 1/2/3-job test after active work; record memory, OOM and gate time; [L4](../L4_docker/FINDINGS.md):17-24; [policy](../../../master_chat_tasks/auto/AUTO_POLICY.md):47. |
| 2 | For identical frozen QC copies, test explicit `--no-delete` and one prewarm in P11. | Avoid repeated cold dependency work when cache misses; measured steps 19.3s and 76.2s. | Storage growth or stale tag. | Two identical tree builds, then one-byte Dockerfile change; compare image ID and logs; [L4](../L4_docker/FINDINGS.md):12-16; [build logs](../L4_docker/BUILD_LOGS.csv). |
| 3 | In an idle window, review only dangling and parked/dropped image IDs; consider a 15 GB Buildx cap. | Up to 3.73 GB cache-accounting reduction, physical saving UNVERIFIED. | Future cold build or wrong image mapping. | Refresh Docker/registry inventory before and after; compare next frozen build; [cleanup plan](../L4_docker/CLEANUP.md):1-61. |

## Ranked changes: task ideas

| Rank | What and where | Expected gain | Risk | How to check |
|---:|---|---|---|---|
| 1 | Design-only pilot of rolling reservations; record contract, independent oracle, first-program wrong output and three hidden seeds. | Avoid full build of another solver-easy idea; gain INFERRED. | Early blind rejects a viable task. | Preserve draft; compare blind and generic solver with oracle on valid seeds; [idea](../L6_web_ideas/IDEAS.md):5-7,20-23. |
| 2 | In `knowledge/LEVER_RULES_v3.md`, copy contract-grounded fresh cases and finite latent recovery with a uniqueness proof. | Hardness without hidden-rule defects; gain INFERRED. | More proof work; score may rise. | Enumerate alternatives and trace every graded fact to copied input or prompt; [L5](../L5_stage2_study/PATTERNS.md):11-17,23-27; [AL-1](../../../Terminal_2.0_Harbor_Harness/Input_Bundle_QC/05_Alignment_Integrity_QC.md):19-29. |
| 3 | Prefer independently meaningful per-field/report credit in next `tests/test_output.py`, while monitoring check count. | Fair near-miss scores and failure attribution. | Verifier time and TS-23 warning. | One-fact score perturbation, count/time budget, full QC; [L5](../L5_stage2_study/FINDINGS.md):23-29; [CL-4](../../../Terminal_2.0_Harbor_Harness/Input_Bundle_QC/Final_checklist.md):491. |

## Conflicts and the supported resolution

- **Live kit versus house templates:** five oracle runs and defensible small stub credit are explicit in the kit; P2/P12 say three and “any pass.” Follow the kit for final QC, and ask Ayush whether to retain a stricter *house* vacuity policy ([kit](../../../Terminal_2.0_Harbor_Harness/Input_Bundle_QC/Final_checklist.md):354-390,418-420; [L2](../L2_qc_kit_map/FINDINGS.md):37-43).
- **L1 versus L2 check counts:** L1's 14 DS-22 task count covers all severities; L2's 11 counts only ❌ fails. These are different denominators, not a source conflict ([L1](../L1_qc_fixes/FINDINGS.md):21-25; [L2](../L2_qc_kit_map/FINDINGS.md):7-11).
- **L3 versus L4 wait fix:** a bounded completion wait addresses a worker's own job; a capacity lease addresses another worker's Docker slot. Both are needed; neither observed aggregate sleep time nor image/cache size proves wall or disk savings ([L3](../L3_auto_problems/FINDINGS.md):25-31; [L4](../L4_docker/FINDINGS.md):17-28).
- **L5 exact scores versus L6 hidden exact ideas:** hidden instances can create real losses, but nine-report hashes and withheld rules can defeat partial credit or reachability. Keep hidden cases with a stated/determinate contract, independent oracle, and one-fact score check ([L5](../L5_stage2_study/PATTERNS.md):19-27; [L6](../L6_web_ideas/FINDINGS.md):17-21; [kit](../../../Terminal_2.0_Harbor_Harness/Input_Bundle_QC/Final_checklist.md):480,491).

The six material UNVERIFIED items are: isolated fix causality, shared-freeze root layer, recoverable wall time from polls, physical disk freed by cleanup, stage-2 check-level WRONG/TIMEOUT/CRASH split, and the proposed task idea's future score. L6's outside-benchmark transfer remains INFERRED; its source ledger was read as a reported literature summary without a new network verification ([L6 sources](../L6_web_ideas/SOURCES.md):1-31).
