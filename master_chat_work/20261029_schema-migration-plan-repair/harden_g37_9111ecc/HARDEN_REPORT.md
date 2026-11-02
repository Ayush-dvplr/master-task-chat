# HARDEN_REPORT: schema-migration-plan-repair, 9111ecc

## Status

**PAUSED: generic exhaustive solver crash+timeout share 71.57% of positive test weight > 70% cap.** Everything in the
14:15 not_run list was finished: full-test cost matrix, Harbor gates, judge prediction. Every other bar passes. The
exhaustive solver's excess is 33 points of TIMEOUT on OLD frozen checks (SCALE worlds 04, 08, 12, 15, 18, 28 and
`ladder_large_state`, unchanged since QC v11) on top of old core 90 and new tier 300. Per the master rule, Tasks_INPUT
was NOT synced (H4 withheld). Master options: exempt the generic, non-agent exhaustive solver, or set the cap to 72%.

Session naming: OpenCode `ses_e7a40682dffeCVs57SfRcaIqc1` listed under 9111ecc; codex returned no match. Kit HEAD
`5574d77eb9f2`. Main chat only after the no-subagent instruction. No commit, push, PR, harness/QC-kit edit, slug rename,
scaffold, `--force`, `--delete` or prune. Blinds 9179 and b686: skipped: identical to 4 measured blinds (master 16:50).

## Step 1a And Arithmetic

a6 beat f0331ad by using the tests' own schema-graph remainder in an exact all-field-state A*. The replacement keeps
the migration contract but builds large regions whose cheap exits need a prerequisite field never set in the zone; the
reference/oracle uses a per-field projection remainder. a6 returns no wrong plan; its loss is hidden-scale TIMEOUT.

| Figure | Frozen a6 | Built candidate (tree ebf080b7b781) |
|---|---|---|
| Positive tests | 291 over 81 checks | 591 over 141 checks (135 positive; 6 negatives worth 14) |
| New held-out tier | none | 60 x w5 = 300/591 = 50.76% |
| Hidden whole-document weight | frozen tier | 540/591 = 91.37% |
| Judge | 20 criteria, positive 38; a6 earned 11 | 23 criteria, positive 49; 16 probes = 48/49 |
| a6 tests | 291/291 = 100% | measured 291/591 = 49.24% |
| Judge prediction | measured 28.95% | low 8.16 / mid 14.29 / high 26.53 |
| Final | measured 64.47 | predicted 31.76 (range 28.70 / 31.76 / 37.88) |
| Verifier | limit 2,700 s, bar 2,430 s | worst measured 2,348 s (exhaustive); Harbor forgery 2,118.9 s |

## Implemented Changes

- New checks `world_47_core_gated_graph` .. `world_106_core_gated_graph`, w5, at `tests/test_output.py:10401` +
  5*(n-47); each owns RNG stream `9000+n`, one program call, whole-output compare. Rows in `WORK/LEVERS.md:289` and
  `WORK/QC_DEFENCE.md` (9111ecc section). `_g_gate` `tests/test_output.py:9542`; `_reference_plan` `:8347`
  (projection remainder); 15 s GATE child cap in `_world_holds` `:9804`.
- Doc sentences: `environment/ci/repository_contract.md:88` (sizes and 10 s runtime), `migration_semantics.md:10`
  onward (edges, prerequisites, smallest cost then edge ids), `null_semantics.ini:7`. No doc changed.
- Judge: logical R5 and R13 out; R21-R25 (P-h missing file, P-h empty feed, P-h malformed cost, P-d policy row, P-d
  explicit_null) in; live IDs R1-R23 (map in `WORK/JUDGE_MAP.md`). Oracle witnesses `solution/solve.py:962`, `:968`,
  `:976`, `:1002`, `:1019`. J3 negatives and J4 code-quality criterion unchanged.

## Measured Final-Test Costs (Docker 4g/2 CPU, direct runner on bundle tests)

| Program | tests % | wall s | lever loss | crash+timeout / positive |
|---|---|---|---|---|
| a6 final repo | 49.24 | 982 | 300 TIMEOUT | 50.76 |
| a5 program | 34.01 | 2,060 | 300 TIMEOUT | 65.99 |
| blind cee149a | 7.11 | 2,163 | 300 TIMEOUT | 65.99 |
| blind 4f7606c / d721 / d2fb | 33.67 each | 2,126 / 2,084 / 2,101 | 300 TIMEOUT | 65.99 |
| first write (Opus a4) | 33.67 | 2,074 | 300 TIMEOUT | 65.99 |
| all-but-one (oracle + plain Dijkstra) | 33.84 | 2,159 | 300 TIMEOUT | 65.99 |
| A* schema bound | 49.07 | 1,070 | 300 TIMEOUT | 50.76 |
| prerequisite-keyed / incumbent | 33.84 each | 2,091 / 2,095 | 300 TIMEOUT | 65.99 |
| bidirectional | 33.33 | 2,096 | 300 TIMEOUT | 65.99 |
| exhaustive | 28.26 | 2,348 | 300 TIMEOUT | **71.57** |
| greedy / schema-only / dominance | 20.47 / 5.75 / 21.83 | 155 / 172 / 411 | 300 WRONG | 0 |

Every program keeps 0 of 300 lever points. Full per-check kinds: `WORK/COST_TABLE.md` (9111ecc section),
`WORK/proto/g37_cost_summary.json`. Swap-built programs also lose two w1 report-claim checks (swap artefact).
Audit: 987 old reference calls identical (digest b0f465e55d9b6d1a); 300 shape seeds pass; reference max 0.2665 s
(audit) / 0.82 s (prototype) <= 2.5 s; old 81 check bodies identical (digest f1a77eab...bbfd668); 35 immutable files.

## Gates And Delivery

- Harbor 0.24 (live-kit exe_copy copies, one nohup chain, ALL_DONE 18:45): oracle 1.0 / 1.0 / 1.0 (verifier
  117.4 / 118.9 / 122.7 s), owner-only 1.0, nop 0.0, stub 0.0017, forgery 0.0102 (2,118.9 s).
- PRECHECK last line: `PRECHECK CLEAN`; validator 40 passed, 0 failed, 0 warnings; xref 50 entries, 0 findings;
  stacking tool run once plus manual adjudication. LSP servers not installed (declined), so no LSP-clean claim.
- Tree: BUNDLE ebf080b7b781; Tasks_INPUT 308399b4016e (not synced, PAUSED). Docs changed: no. Judge changed: yes.
- Not run: Tasks_INPUT sync, P11 QC, paid harness run, blinds 9179/b686 (skipped by master).

## Lessons for the master
Cap checks must count inherited old-check timeouts per program, generics included | no change: master owns the cap.
Swap-built cost programs lose report-claim checks as an artefact | no change: noted in COST_TABLE.
