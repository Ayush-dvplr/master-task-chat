# Next plan, written 28 Oct ~15:15 (gate v3.6). STARTED 28 Oct ~15:55 (Ayush: "start")

Until: 18:00 IST (nothing new after 18:00; running sessions finish, wind-down cap 2 h). Paid-run cap: 6 (Ayush ~15:25: "raise the cap to 6").
Ayush 28 Oct ~15:20 answers: till 18:00; capacity same as today; a run that misses -> harden once, then 1 new run (at most one harden-and-rerun per task), within the 6-run cap. A second miss on the same task, or the cap used up -> Needs Ayush.
Ayush 28 Oct ~15:12 answers: schema = re-harden tests; cold-chain = (a) fix book_reach -> recheck -> 1 run; metered = P11 v3 full QC -> 1 run; finish these 3 first, no new tasks.

Limits: 5 workers, 2 harness, at most 3 Docker-heavy sessions. While a metered Docker job runs (memory_mb 8192, VM 12.5 GB), at most 1 other Docker-heavy job. Before each Docker spawn, check `docker ps` and `sysctl vm.swapusage`; if swap > 20 GB, hold spawns.

Gate (intake.py v3.6): tests < 85 AND rubric < 85 AND final < 50 on 1 valid run of frozen bytes that passed QC.

## Tracks (in parallel, priority cold-chain > metered > schema)

### 1. cold-chain-backbone-quote (2 steps from a run)
1. P12 v4 fix of QC v3 DS-20 only: solve.py:618-631 book_reach skips [closed] links, depot at 0, so the printed widest link = contract 51. No other edits; no change to tests, docs or judge. Then check: oracle 1.0x3, nop 0, PRECHECK CLEAN, synced, lever unchanged. Copy KEPT.md.
2. P11 v3 recheck (prev v3 copy 7304a6f, writes v4).
3. PASS -> diff bundle == Tasks_INPUT == QC copy, freeze the tree sha -> 1 run.

### 2. metered-usage-rating-pipeline (first QC)
1. P11 v3 MODE full (base prompts/issued/tariff-engine-audit-repair/20261027T2025_qc.md; report dir QC/reports/metered-usage-rating-pipeline, writes v1). Docker-heavy, 8 GiB.
2. FAIL -> P12 v4 fix -> recheck. PASS -> freeze -> 1 run.

### 3. schema-migration-plan-repair (re-harden tests; kill rule was hit at tests 100)
Evidence (gate_run_a6/TRIP.md): 291/291 tests, 0 lost; the agent skipped judge probes R3, R4, R6-R12. The behaviours behind those probes have no test that a generic repair fails:
- parse-rejected line naming a manifest batch (R3)
- null token with surrounding spaces (R4)
- planner on 1000+ schema graph: time limit and optimal plan (R6/R7)
- edge cost > 1e6 (R8)
- extra unnamed file in contract folder (R9)
- batch with no admitted lines (R10)
- rerun over an older, longer records.jsonl (R11)
- changed edge cost changes plan (R12)
1. P9 v4 gate v3.6 harden, tests side, from the a6 trajectory: add hidden-scale test worlds on the behaviours above that the agent's 100% code would fail (WRONG or Law-1 v3.5 timeout). Each must follow from docs that already ship; no new stated rule, no easy judged points; judge unchanged unless a test makes a rubric item redundant. -> DESIGN READY.
2. Master go only if the DESIGN READY bar is met (below). Specifically, the a6 agent's own final repo, rerun on the new tests, must score <= 75.
3. Docs changed -> 3 blinds; else rescore the existing blind programs + the a6 final repo.
4. P11 v3 recheck (prev v11 copy 361ee0a, writes v12) -> PASS -> freeze -> 1 run (attempt 7).
5. Harden cannot reach the bar -> stop, Needs Ayush (kill).

## Rules per event
Same as auto/plans/20261028_day_plan.md "Rules per event" and the DESIGN READY bar: every generic solver and blind/agent program loses >= 15% of lever points through WRONG or a Law-1 v3.5 hidden-scale loss; shipped inputs run fast; reference <= 1/4 of the limit; predicted tests for first-write/all-but-one <= 75; predicted judge mid 15-20.
After a run: copy it to master_chat_work/20261028_<slug>/gate_run_a<N>/, write TRIP.md, intake --apply. Gate met -> pl_ready (Ayush pushes). Missed -> no re-run on the same bytes; harden once from that trajectory, then 1 new run (line 4); a second miss -> Needs Ayush.

## Do not
Push or commit. Edit rule files, templates, GOALS or policy. Touch the 7 pushed tasks or merge any QL review. Touch wave 3, parked, killed or dropped tasks. Start new tasks. Docker prune. Re-run on the same bytes. Exceed the paid-run cap.

## Start (issued 15:53, spawned ~15:56)
1. b0aca9b cold-chain P12 v4 fix of QC v3 DS-20 (book_reach only): prompts/issued/cold-chain-backbone-quote/20261028T1553_fix.md
2. ac12c0b metered P11 v3 MODE full (first QC; writes v1; Step 10 runs one at a time, 8 GiB): prompts/issued/metered-usage-rating-pipeline/20261028T1553_qc.md
3. a4f790c schema P9 v4 gate36 harden tests from a6 (stops at DESIGN READY; master go only if a6 final repo <= 75 on new tests): prompts/issued/schema-migration-plan-repair/20261028T1553_harden.md
