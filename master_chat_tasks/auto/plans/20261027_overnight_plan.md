# Overnight auto plan, 27 Oct 22:30 -> 28 Oct 08:00 (gate v3.6)

Ayush 27 Oct 22:20: "new gate is test < 85 , rubrics < 85 and overall < 50"; harden the gate-approved tasks from their trajectory with the proven levers. Answers 22:25-22:30 (decisions.jsonl): schema + sentinel hardened; tariff/district/cold-chain run first, harden after a miss; proven levers + section T edits (stated-rule levers stay paused); judge probe band mid 15-20; proof = 1 run gate met; metered redesign tonight; lever 25-40%, first-write aim tests <= 75; each of 3 blinds tests <= 80; master sends "go" at DESIGN READY if the kill table passes; sentinel harden merges 3eb08a6 without F4.

Limits: 5 workers, 2 harness, up to 5 Docker-heavy sessions, at most 8 paid harness runs (raised 22:40). Before each Docker spawn: `docker ps` and `sysctl vm.swapusage`; swap > 20 GB -> hold spawns. Nothing new after 08:00; running sessions finish (wind-down cap 2 h).

Gate (intake.py v3.6): tests < 85 AND rubric < 85 AND final < 50 on 1 valid run of frozen QC-passed bytes.

## Start (22:3x)
- Harness 1: tariff-engine-audit-repair, frozen tree 0de116d29fdb (QC v2 PASS f054899). Check Tasks_INPUT == bundle first; `auto.py harness <Tasks_INPUT/tariff-engine-audit-repair>`.
- Workers:
  1. f0331ad schema gate v3.6 harden (prompts/issued/schema-migration-plan-repair/20261027T2228_harden.md).
  2. 217875e sentinel gate v3.6 harden + QC v7 merge (prompts/issued/sentinel-policy-recompute/20261027T2229_harden.md).
  3. 361674d metered redesign (prompts/issued/metered-usage-rating-pipeline/20261027T2229_harden.md).
  4. ba5455c district QC v6 full (prompts/issued/district-heat-flex-procurement/20261027T2213_qc.md).
  5. 5fe096b cold-chain blind scoring (prompts/issued/cold-chain-backbone-quote/20261027T2207_run.md).

## Rules per event
- DESIGN READY (harden sessions): master reads DESIGN.md + KILL_TEST.md. Send "go" only if every generic solver and every blind/agent program loses >= 15% of lever points by WRONG or Law-1 v3.5 hidden-scale loss, shipped inputs fast, reference <= 1/4 of the limit, first-write/all-but-one predicted tests <= 75, judge predicted mid 15-20 (sentinel 10-20). Otherwise send the specific corrections once; second failure or NO CORE -> Needs Ayush.
- Harden DONE -> 3 fresh P13 blinds (fresh /tmp/blind dirs, copy of the task's latest blind prompt) -> one Docker scoring session (method of score_185c588) -> each blind tests <= 80 with WRONG or v3.5 losses -> P11 v3 (recheck against the last QC report for schema v8 / sentinel v7; full for metered) -> PASS (warns kept under option A) -> freeze -> 1 harness run. Any blind > 80 -> Needs Ayush.
- Cold-chain scoring done: each of 3 blinds (2cbd32a, 23bef90, 9387727) tests <= 80 with lever losses only -> P11 v3 full QC -> PASS -> freeze -> 1 run. Else Needs Ayush.
- QC FAIL -> P12 v4 fix (G1-G7) -> P11 v3 MODE recheck. QC PASS -> freeze tree sha, Tasks_INPUT == bundle == QC copy -> 1 harness run.
- Run done: intake.py --event gate_run; trajectory_readout.py. Gate met -> pl_ready (sentinel: re-push is Ayush's). Missed -> no re-run on the same bytes; P9 v4 gate v3.6 harden from that trajectory (same base prompt as the 22:28 hardens), then blinds -> QC recheck -> 1 new run, within the 8-run cap.
- Harness run order when slots free: tariff, district, cold-chain, then any harden that reached QC PASS.

## Do not
Push or commit; edit rule files, templates, GOALS or policy; touch pushed tasks other than sentinel (dispatch, match-replay, caldermoor, emberforge; Ayush 22:35 "no need to work for the pushed tasks except for 50.1 overall task"); touch wave 3 (cleanroom, counter-page, flood, batch-lease, fuel-card, pilotage) or parked tasks; Docker prune; Q52; re-run a run on the same bytes; more than 8 harness runs.

## Sentinel extra (Ayush 22:37)
- QL review of pushed 07363dd arriving tonight: do NOT merge into the running harden; leave for the morning.
- Sentinel run meets gate v3.6: mark ready to re-push only (status pl_ready + REPORT Needs Ayush line); never push.

## Priority and limits (Ayush 22:40: "1. yes 2. yes 3. yes 4. yes"; overrides lines above)
- Aim: at least 2 tasks marked ready to push (gate v3.6 met on 1 run) by the end. Priority order for slots, Docker, runs and 'go': tariff run, district QC v6 -> run, sentinel smallest-change harden -> QC recheck -> run; then schema, cold-chain; metered last and first to pause when the machine is tight (swap > 20 GB or Docker full).
- Sentinel: smallest change (judge band + merged fixes, lever unchanged, predicted final <= 45). If its test lever and test checks stay unchanged, skip the 3 blinds: go straight to P11 v3 recheck vs v7, freeze, 1 run.
- Run cap raised to 8 paid harness runs.
- Wind-down: sessions mid-run or mid-QC at 08:00 may continue up to 2 h so a task can reach ready to push; nothing new after 08:00 except the next step of a task that is one step from pl_ready (QC recheck after fix, or its 1 run).
