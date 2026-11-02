# AUTO report (stage2cause: 2026-10-31 16:06 -> 2026-10-31 17:30)

## In short

FINAL 17:32: all 5 sessions + scorer DONE; CAUSE_REPORT written. Answer to step 1: the five lowest stage-2 tasks are low mostly through UNFAIR contracts (78% of lost test points: hidden clocks that contradict the docs, undefined output keys/IDs, all amplified by whole-report checks). One real, copyable trap found: PM2.5 shared-channel echo attribution (21.9%, holds on inputs with no clock changes). Our blind matched Opus test scores exactly on billing, PM2.5 and pension. No paid runs, no edits to rules or anubis-stage-2. Report: [CAUSE_REPORT.md](file:///Users/mac/Desktop/Terminal%20Bench/master_chat_work/20261031_stage2_calib/CAUSE_REPORT.md).

- 16:06 started: replays 3d517b2, 4e9d595 (GPT gpt-6.1-sol); blinds d830ccb billing, 5c1644a PM2.5, de212ed pension (Opus). No paid runs.
- 16:12 Ayush rule: every GPT prompt/message says strictly no subagents, all work in main chat (could not send to the two busy GPT replays; 0 child sessions so far).
- 16:14 de212ed pension blind DONE (program app/calculate_pension.py, result json parses, self-check PASS on shipped, judge est 15-18/56, first write 2 min). Waiting for the other two blinds before the scorer.
- 16:16 d830ccb billing blind DONE (app/transform.py, 13 reports, self-check PASS shipped, only 1/8 what-ifs match: one clock offset per handset vs per-day fit; judge est 11-14/58) and 5c1644a PM2.5 blind DONE (app/derive_report.py, 9 reports, self-check PASS, 3 of what-ifs match: single clock offset per unit; judge est 11/58). Both blinds hit the same latent value (time-varying clock offset) Opus likely missed.
- 16:17 scorer b366e00 spawned on openai/gpt-6.1-sol (prompt prompts/issued/_stage2_calib/20261031T1615_score_blinds.md, no-subagent line, lint clean): runs each blind program through the real stage-2 tests via harbor oracle, per-check table blind vs Opus, cause labels; OUT master_chat_work/20261031_stage2_calib/score_blinds/.

## Needs Ayush

1. Twin first? Recommended: a new task built on the PM2.5 echo-attribution trap (stated constant clocks, shared-channel echoes that fool per-unit voting, unique anchor receipts, attribution scored separately from downstream reports). Alternative: royalty-style rule composition with defined IDs and split credit (weaker evidence: Opus's arithmetic was already right there).
2. Keep the blind as the gate before a paid run? Recommended: yes, plus a contract audit and a one-fact partial-credit check (blind = Opus tests exactly on 3/3 tasks). Alternative: allow a capped paid pilot right after a design blind when causes are unclear.
3. Judge target? Recommended: judge mid <= 20% with small fair conduct criteria + independent boundary evidence. Alternative: accept higher if the final still clears <40.
4. Pilot first? Recommended: a small mechanism-only pilot (echo attribution alone, measure blind loss) before a full bundle. Alternative: full build straight away.
5. Hangar af5dddf and depot 154f570 are still held (issued, not opened).

## Results

- d830ccb (billing blind): DONE, [BLIND_REPORT.md](file:///Users/mac/Desktop/Terminal%20Bench/_runs/20261031/stage2-calib/blind-billing-20261031T1552-ba10/work/BLIND_REPORT.md).
- 5c1644a (PM2.5 blind): DONE, [BLIND_REPORT.md](file:///Users/mac/Desktop/Terminal%20Bench/_runs/20261031/stage2-calib/blind-pm25-20261031T1552-ad2c/work/BLIND_REPORT.md).
- de212ed (pension blind): DONE, [BLIND_REPORT.md](file:///Users/mac/Desktop/Terminal%20Bench/_runs/20261031/stage2-calib/blind-pension-20261031T1552-1540/work/BLIND_REPORT.md).

- 16:27 4e9d595 replay A2 DONE verified (result json parses; 0 child sessions): pension + spectrum replay tests 23.08 = recorded 23.08, oracle 100. All 80 lost raw test points (40 per task, 8 scenario checks w5 each) are UNFAIR: report details undefined or contradictory in the docs (e.g. pension count keys schema.md:27, revision-decision keys schema.md:29), amplified by whole-bundle hashes. No calculation errors. Caveat: private ECR base image 401, used local python:3.12-slim; grading code unchanged. Mechanism is NOT copyable under our kit (fails IN-8/CL-4 style checks). [FINDINGS](file:///Users/mac/Desktop/Terminal%20Bench/master_chat_work/20261031_stage2_calib/replay_A2/FINDINGS.md).
- 16:41 b366e00 blind scorer DONE verified (result json parses; 0 child sessions; oracle 100% on all three). Our blinds score EXACTLY like Opus on tests: billing 7/97, PM2.5 10/110, pension 12/52; 46 of 46 lost checks lost by both, 0 only-Opus, 0 only-blind. Cause on billing + PM2.5 (the tasks we thought QC-safe): every hidden extract changes a device clock offset over time, while the shipped docs say the offset never changes (billing record_dictionary.md:19 'never adjusted afterwards'; PM2.5 record_dictionary.md:40-44 'the offset holds for every row'; master read both lines). So their low scores come from hidden data that contradicts the stated rule = UNFAIR, amplified by whole-report exact checks. Pension: same UNFAIR undefined keys + one blind-only ledger misread masked by the hash. [FINDINGS](file:///Users/mac/Desktop/Terminal%20Bench/master_chat_work/20261031_stage2_calib/score_blinds/FINDINGS.md).
- 16:58 3d517b2 replay A1 DONE verified (result json parses; 0 child sessions): billing 7.22, PM2.5 9.09, royalty 23.08 replay tests = recorded, every criterion value matches; oracle 100. Billing: UNFAIR (hidden clocks change vs record_dictionary.md:19; fixing only changed handsets makes all 18 extracts exact). Royalty: UNFAIR (one unspecified INVALID_STATEMENT id ST-BAD-A vs ST-BAD, schema.md:9; one expression change makes all 8 bundles exact). PM2.5: LATENT-WRONG plus UNFAIR co-cause: the agent's independent max-match offset vote is fooled by shared-channel echoes even on constant-clock units; 3 new probes with NO clock steps still fail the captured program -> a copyable, QC-clean inference trap (the only one found). Judge loss: FIGURE-WRONG 50%, PROBE-SKIPPED 26%, PROCESS-SKIPPED 17%. [FINDINGS](file:///Users/mac/Desktop/Terminal%20Bench/master_chat_work/20261031_stage2_calib/replay_A1/FINDINGS.md).
- 16:59 plan step 5: codex exec -s read-only (high, no multi_agent) drafting CAUSE_REPORT from the three session outputs; draft at master_chat_work/20261031_stage2_calib/cause_draft/last.txt; master checks numbers then writes master_chat_work/20261031_stage2_calib/CAUSE_REPORT.md.

## Decisions and overrides

- 17:02 codex draft checked and written to master_chat_work/20261031_stage2_calib/CAUSE_REPORT.md (checked per-task numbers vs result json, UNFAIR/LATENT totals, constant-clock doc lines; judge shares not re-derived).

- 16:17 scorer b366e00 issued and spawned per plan step 3 (before 17:00), GPT model, no subagents.

## Interrupted or unfinished

- None. All six sessions (3d517b2, 4e9d595, d830ccb, 5c1644a, de212ed, b366e00) finished; board done. 0 subagent child sessions in the three GPT sessions.

## Still running at stop

- Nothing.

- none: no worker busy and no paid run active (FINAL 17:30)

## Proposed changes (not applied)

- Add to the build checklist (after Ayush OK): a doc-vs-hidden-input contradiction check (every hidden generator parameter must stay inside what the docs state), since the stage-2 low scores came from exactly that.
- Blind scoring and replays need a tests-only harbor copy (judge removed); A1 hit `Trajectory not found` with the judge on. Worth a small helper script for future calibration runs.
- trajectory_readout.py still labels metered ladder timeouts as WRONG (pending R10).
