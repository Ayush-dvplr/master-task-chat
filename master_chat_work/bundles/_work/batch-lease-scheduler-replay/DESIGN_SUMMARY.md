# DESIGN_SUMMARY 98c5c50 batch-lease-scheduler-replay (build-repair, seed 413927)

Task: repair zipped package `leasebook` (packaging + parser defects, lazy internal events,
preemption counted as failure, release on any terminal, no redelivery dedup, stale tokens
applied); ship out/package.zip; package replays a book of sets and writes module_core,
module_metrics, dependency_resolution, summary; plus selftest.json, build_report.json.
Data (/app/data, 10 files, 8 formats, 420 sets, ~37k lines): project.zip, replay_contract.md
(the only rule file), policy.ini, pools.json, workers.csv, jobs.tsv, durations.csv,
dependencies.csv, events.jsonl, checkpoints.txt. Chains C1-C5 (DESIGN 2), all >= 4 links.
Contract: integer clock 0..last checkpoint; per time ONE order: completions, expiries,
retry-ready, external events by id, dispatch (once, end of time). Dispatch priority desc then
job id; victim lowest priority, latest start, larger id; preempted job waits for next time.
No secondary lever (core build). No L5/L11, no separating case ships, no answers ship (W11).

First-write program (event heap, PREMORTEM C), 5 hidden corpora x 3 sets (80-140 jobs,
525-905 events): clean heap == unit-step reference on all sets (two independent engines).
| slip | hidden docs wrong per corpus (of 4) | shipped sets changed (of 400) |
|---|---|---|
| FIRSTWRITE (FW3b cancel remaining + FW4 preempted heartbeat + FW5 cascade unsubmitted) | 4 4 4 4 4 | n/a |
| FW1 completion guard by attempt | 4 x5 | 72 |
| FW2 externals before internals | 4 x5 | 0 |
| LAZY (shipped loop kept) [LV-BS-1 wrong reading] | 4 4 4 3 4 | 399 |
| PREFAIL [LV-BS-2] / STALE | 4 x5 / 4 x5 | 149 / 0 |
| ANYTERM [LV-BS-3] / REDUP / FW5 | 4 x5 each | 37 / 0 / 4 |
| FW3 lost=run ticks / PRECSWAP audit precedence | 2 x5 / 2 x5 | 13 / 0 |
| FW2R checkpoint remaining / SUBORDER / PEREVENT | 1 x5 / 4 x5 / 4 x5 | 397 / 41 / 88 |
Every slip loses >= 1 whole document on every hidden corpus: no redesign needed.

Tests (36, WARN A3): H1-H4 x 4 docs w5 (80), M1 shuffled rows core w5, M2 policy changed
summary w5, M3 run twice w3, S1-S4 shipped docs w3, I1 worker capacity w3, I2 state
invariants w3, R1-R5 rejections w3, P0 existence w1, P1-P4 package/selftest/report/tests w3;
N1 reads /tests -5, N2 precomputed docs in archive -3. Positive 139.
Shares: whole-doc 73%, hidden/mutated 82%, isolated 27%, shipped-only 9%.
Cost (predicted): each lever wrong alone loses >= 102/139 (73%); all-but-one overall
0.5*27+0.5*90 = 58 < 70; one-fact-wrong = 20/139 (one corpus, 4 docs).
Judge (9): J2 x5 w3 (core, metrics, deps, summary, archive), J9 w3, J4 w3, J6 w3, J3 -3.
Time limit stated: book of up to 4 sets at bounds within 60 s; reference ~0.1 s per corpus
(to be measured in Docker).
Risk: a careful unit-step simulator is exact; hardness rests on interaction slips and on
anchored repair of the shipped loop. Probe decides.
