# Day auto plan, 28 Oct 12:20 -> 14:00 (gate v3.6)

Ayush 28 Oct ~11:55: "1. go 2. to 8192 MB (simplest) 3. now for auto mode ready plan for" district, schema, cold-chain, metered. Tariff and sentinel are pushed (28 Oct); no work on tariff until its QL review arrives. Sentinel gets ONE PL-feedback job only (below).

Limits: 5 workers, 2 harness, at most 3 Docker-heavy sessions, at most 6 paid harness runs. Docker VM has 12.5 GB; metered now declares memory_mb 8192, so while a metered Docker job runs, at most 1 other Docker-heavy job. Before each Docker spawn: `docker ps` and `sysctl vm.swapusage`; swap > 20 GB -> hold spawns. Nothing new after 14:00; running sessions finish (wind-down cap 2 h; the next step of a task one step from pl_ready may still start in the wind-down).

Gate (intake.py v3.6): tests < 85 AND rubric < 85 AND final < 50 on 1 valid run of frozen QC-passed bytes.

## Ayush answers 28 Oct ~12:18 ("Run auto mode till 2 pm today")
- Capacity 5 workers / 2 harness / 3 Docker-heavy / 6 paid runs.
- Wind-down: running sessions finish (cap 2 h, until 16:00); nothing new after 14:00 except the next step of a task one step from pl_ready (its QC recheck after a fix, or its 1 paid run, within the run cap).
- Metered today: 3 blinds + the scoring session only (it also measures verifier peak memory); STOP before QC; lowest priority, first to pause. Its QC and run are Ayush's.

## Start
Issued 12:01-12:05 (all 0 placeholders):
1. d1dab52 district P11 v3 recheck vs v7 after harden dcd21a3 (writes v8): prompts/issued/district-heat-flex-procurement/20261028T1205_qc.md
2. c9ea299 schema P12 v4 fix of QC v9 (R14 rewritten as a code-quality criterion with no unstated shape, R20 narrowed; tests/docs unchanged): prompts/issued/schema-migration-plan-repair/20261028T1205_fix.md
3. 905cf6e cold-chain P12 v4 fix of QC v2 (R10 + codes, R5 dimension, TRUTH:67, TS-26 guard): prompts/issued/cold-chain-backbone-quote/20261028T1205_fix.md
4. d5c7b9d metered P13 blind 1 (/tmp/blind/metered-usage-rating-pipeline-20261028T120151-de51): prompts/issued/metered-usage-rating-pipeline/20261028T1201_blind.md
5. f4f4ff5 metered P13 blind 2 (/tmp/blind/metered-usage-rating-pipeline-20261028T120252-1626): .../20261028T1202_blind.md
6. 188771e sentinel PL feedback: R13 reworded to the instruction's own words + ONE harbor regrade of run a8, no QC (prompts/issued/sentinel-policy-recompute/20261028T1214_fix.md). Highest priority: spawn first.
Queued (first free slot): 4d36b26 metered P13 blind 3 (/tmp/blind/metered-usage-rating-pipeline-20261028T120354-f05d): .../20261028T1203_blind.md

## Sentinel PL feedback (Ayush 28 Oct ~12:10; answers: reword R13, stop and ask, local checks only, update everything, "a very careful worker sessions and verifed by you")
- 188771e DONE -> master verifies before anything else: `diff -r` BUNDLE vs QC/copies/7d4de68 shows only the R13 line (+ TRUTH sha line if any); BUNDLE == Tasks_INPUT == Output_RFP task files; precheck CLEAN; regrade dir scores re-read by the master (tests, rubric, overall, R13 reasoning, judge ran); Output_RFP run_1 files all carry the regrade numbers (grep 40.48 / 0.4048). All good -> status pl_ready 'ready to RE-push (regrade)', registry note by the master, REPORT Needs Ayush line. Anything off -> Needs Ayush, no fix.
- 188771e STOPPED (rubric 0 again, overall >= 50, a non-lever check moved, regrade cannot start) -> Needs Ayush. No second edit or regrade.

## Rules per event
- QC PASS (0 fail; warns kept under option A; carry-over acknowledged) -> check bundle == Tasks_INPUT == QC copy (diff -rq, no __pycache__), record frozen tree sha -> `auto.py harness <Tasks_INPUT/<slug>>` 1 run.
- QC FAIL -> P12 v4 fix (base: prompts/issued/<slug>/20261028T1205_fix.md, or cold-chain's for district/metered), directions per finding, G1-G7, no new stated rule, no easy judged points -> copy OUT/KEPT.md to QC/reports/<slug>/KEPT.md -> P11 v3 MODE recheck.
- Fix DONE (schema c9ea299, cold-chain 905cf6e, later ones) -> check result json (oracle 1.0x3, nop 0, PRECHECK CLEAN, synced, lever unchanged) -> copy KEPT.md -> P11 v3 MODE recheck (base: district 20261028T1205_qc.md; schema prev v9 copy f26bda6 writes v10; cold-chain prev v2 copy 4fef871 writes v3).
- Metered 3 blinds DONE -> one Docker scoring session (base prompts/issued/metered-usage-rating-pipeline/20261027T2107_run.md; lever checks from master_chat_work/20261027_metered-usage-rating-pipeline/harden_g36_361674d/HARDEN_REPORT.md; also record verifier peak memory). Today: record the result in REPORT and stop (Ayush 12:18). Later rounds: each blind tests <= 80 with WRONG or Law-1 v3.5 lever losses, and verifier peak < 8 GiB -> P11 v3 MODE full (first QC of metered; base prompts/issued/tariff-engine-audit-repair/20261027T2025_qc.md; report dir QC/reports/metered-usage-rating-pipeline writes v1) -> PASS -> freeze -> 1 run. Any blind > 80, or peak >= 8 GiB -> Needs Ayush.
- Run done -> copy jobs/<slug>/trajectory/claude-opus-5/Run 1 to master_chat_work/<date>_<slug>/gate_run_a<N>/run, `tools/trajectory_readout.py` -> TRIP.md, `tools/intake.py --job <slug> --event gate_run --apply`. Gate met -> status pl_ready (push is Ayush's). Missed -> no re-run on the same bytes; P9 v4 gate v3.6 harden from that trajectory (base prompts/issued/district-heat-flex-procurement/20261028T0418_harden.md: DESIGN READY -> master go per the bar below) -> blinds only if docs change, else rescore existing blind programs -> P11 v3 recheck -> 1 new run, within the run cap.
- DESIGN READY bar for 'go': every generic solver and blind/agent program loses >= 15% of lever points by WRONG or Law-1 v3.5 hidden-scale loss, shipped inputs fast, reference <= 1/4 of the limit, first-write/all-but-one predicted tests <= 75, judge predicted mid 15-20.
- Harness run order when slots free: district, schema, cold-chain, metered.
- Priority for slots and Docker: district, schema, cold-chain, then metered (first to pause when Docker or swap is tight).

## Do not
Push or commit; edit rule files, templates, GOALS or policy; touch pushed tasks beyond the sentinel PL job above (tariff, sentinel, dispatch, match-replay, caldermoor, emberforge); merge any QL review; touch wave 3 (cleanroom, counter-page, flood, batch-lease, fuel-card, pilotage) or parked tasks; Docker prune; Q52; re-run on the same bytes; more than 6 paid harness runs.
