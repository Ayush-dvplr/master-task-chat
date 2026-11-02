# RECHECK_FIX 5f2e150 (P12 v3 fix r2) caldermoor-commitment-closure

## Phase 1 reproducers (current bundle e56aea87b39e, verifier image, agent program p2)

### CM-B survivor second pass (H7)
Smallest reproducer, case P2-072 (seed 44985048, fixtures env+env2+ident, mutation waivers):
- principal-month 2032-09 / ACT-0013, envelope 30 (OVERRIDE), reserve 0, distributable 30
- open efforts: CMT-01276 = 20, CMT-01686 = 15 (demand 35 > 30)
- first pass: 17 / 13; CMT-01686 is below fifteen and drops
- second pass: survivor CMT-01276 alone, its effort 20 is at or below 30
- oracle: CMT-01276 = 30, CMT-01686 = 0 (month_load_index `2032-09,ACT-0013,OVERRIDE,30,0,35,30,2`)
- agent p2: CMT-01276 = 20, CMT-01686 = 0 (re-enters the at-or-below branch, leaves 10 undistributed)
- agent differs in 9 artifacts: actionable_queue.tsv, actor_rollup.json, attention_allocation.csv, audit_totals.csv, commitment_ledger.jsonl, month_load_index.csv, project_lineage.csv, project_rollup.json, reconciliation.txt; oracle 0 diffs.

Case P2-022 (seed 96934951, fixtures env+ident+env2, mutation revision): 2032-11 / ACT-0036, envelope 300, reserve 90, distributable 210; efforts 60/15/15/90/45; oracle 65/0/0/97/48, agent 60/0/0/90/45. Agent differs in 10 artifacts (the 9 above plus blocked_commitments.csv); oracle 0 diffs.

### CM-A malformed reference-table line
Seed 4100011 + small envelopes + one extra budget_overrides.psv line:
- blank line: agent exit 1 (KeyError 'monthly_minutes'), oracle exit 0
- short line `ACT-0001|2032-09`: agent exit 1 (KeyError), oracle exit 0
- long line `ACT-0001|2032-09|20|x`: both exit 0

## Per-direction table

| ID | evidence | change | files | effect on levers A / B / C / H7 (kept of P) |
|---|---|---|---|---|
| F1 | P2-022, P2-072 reproduce on e56aea87b39e; agent p2 and the H7 one-rule mutant differ in 11 artifacts on the planted seeds | fixture `_add_survivor_envelopes` (override envelopes that leave the floor's survivors more distributable minutes than their effort) planted on SURVIVOR_SEEDS (4100149, 68250419) inside `_write_corpus`; six owned-row tests | tests/test_output.py, tests/reward.toml (0.5/186) | A 66.67 -> 58.06, B 64.81 -> 56.45, C 58.64 -> 51.08, H7 100 -> 87.10 |
| F2 | W9 self-test: "by the same rule" can denote the section's whole procedure, which opens with the at-or-below test; the p2 agent took that reading | commitment-protocol.md:207-210 rewritten to fix the amount, paragraph kept 7 lines | environment/data/commitment-protocol.md | none on tests; removes the second reading |
| F3 | reference and oracle skip blank and short reference-table lines; agent p2 exits 1 (KeyError) | one sentence at record-layouts.md:10-12; oracle outputs on shipped data byte-identical before/after (diff -r) | environment/data/record-layouts.md | none; no test touches it |
| F4 | 300 seeds (Random(52150)), fixtures none/prec/env/ident/surv/all, Pool(4), 400 s alarm | no fix needed | none | none |
| F5 | bookkeeping | RULE_COVERAGE row, COST_TABLE section, LEVERS H7 row, DESIGN "Fix round 2", XREF entry, TRUTH.md by script last; JUDGE_MAP unchanged (no observable changed) | WORK/*, solution/TRUTH.md | none |

## F2 verdict: REWRITE

Self-test reading: "the whole of the distributable minutes is distributed again by the same rule" names a rule, and the nearest whole rule in the section is the one that starts "When the summed clamped effort is at or below the distributable minutes, each commitment receives its own clamped effort and the rest is left undistributed". A careful reader can apply that branch to the survivors and leave minutes undistributed, which is what reconcile.py:663-677 did. The amount had to be fixed in the sentence.

Before (commitment-protocol.md:207-210):
> commitment whose share then falls below fifteen minutes receives zero, and the
> whole of the distributable minutes is distributed again by the same rule across
> only the commitments that held fifteen or more. When that leaves no commitment
> standing, every share is zero.

After:
> commitment whose share then falls below fifteen minutes receives zero, and
> every one of the distributable minutes is distributed again, in proportion to
> clamped effort by largest remainder, ties settled as above, across only the
> commitments that held fifteen or more; when none held, every share is zero.

No explanation added (W1); the branch is not named. Oracle and reference already gave every minute, so no code changed.

## F3 sentence

Added to record-layouts.md section 1 (lines 10-12): "In `attention_budget.csv` and `budget_overrides.psv` a blank line or a `MALFORMED_ROW` line is skipped and records no envelope." Oracle run on BEFORE and AFTER environment/data: both exit 0, 28 artifacts each, `diff -r` identical.

## New tests (P 162 -> 186, 49 -> 55 checks)

| test | weight | seed | owned rows |
|---|---|---|---|
| survivor_allocation_exact | 3 | 4100149 (planted fixture) | attention_allocation.csv rows of the 8 survivor principal-months, keyed (year_month, obligor_actor, commitment_key) |
| survivor_allocation_hard | 5 | 68250419 (held back) | same, 8 principal-months |
| survivor_month_load_exact | 3 | 4100149 | month_load_index.csv rows of the survivor principal-months, keyed (year_month, obligor_actor) |
| survivor_month_load_hard | 5 | 68250419 | same |
| survivor_ledger_exact | 3 | 4100149 | commitment_ledger.jsonl objects whose commitment_key lies in a survivor principal-month (23 keys) |
| survivor_ledger_hard | 5 | 68250419 | same (25 keys) |

A survivor principal-month is one where some commitment kept a share, some commitment with demand got zero, and the kept shares exceed the kept demand; `_survivor_months` raises unless at least two exist (non-vacuity). Each test checks the delivered tree is exactly the declared set, then asserts exact equality on owned rows only and names the first differing path, e.g. `survivor extract 4100149: attention_allocation.csv[2032-03,ACT-0011,CMT-01731].allocated_minutes produced '30', expected '31'`. Hard tests run the delivered program through `_probe` as nobody, as every existing `_hard` family does. Every existing test keeps its logic and weight.

## Reference and generator fuzz (F4)

300 seeds, 300 unique, 0 errors, 0 hangs, 0 oracle exits other than 0, 0 artifact differences between reference and oracle; the survivor fixture found months on all 100 surv/all seeds; max reference 1.98 s, max oracle 0.64 s. Log WORK/fz/fuzz300.jsonl.

## Agent program p2 on AFTER tests

162 / 186 = 87.10 % of tests; fails exactly the six survivor tests. Overall at measured judge 1/22 (4.55): (87.10 + 4.55) / 2 = 45.82. At rubric 90: 88.55.

## One-rule variants, kept of P

| variant | BEFORE (P 162) | AFTER (P 186) | new tests failed |
|---|---|---|---|
| oracle | 100.00 | 100.00 | 0 |
| A (blocked closure) | 66.67 | 58.06 | 6 |
| B (periods_waived) | 64.81 | 56.45 | 6 |
| C (allowance per principal) | 58.64 | 51.08 | 6 |
| H7 (survivor re-entry) | 100.00 | 87.10 | 6 |
| agent p2 | 100.00 | 87.10 | 6 |

No negative fired for any variant. Logs WORK/fz/score_before.jsonl, score_after1.jsonl.

## Docker block (tests only, exe_copy plain / --owner-only / --stub, TS 20261024T234620-b2de)

oracle x3 = 1.0 / 1.0 / 1.0 (186 / 186, all six survivor tests pass), owner-only = 1.0, nop = 0.0, stub = 0.0 (0 / 186 of P, no negative fired). Chain /tmp/opencode-logs/caldermoor-commitment-closure-p12r2-20261024T234620-b2de/chain.sh, log ALL_DONE.

## Gates

xref_check 9 entries, 0 findings; precheck last line `PRECHECK CLEAN`; live kit structure_qc, instruction_qc, tests_qc (A3 warn), judge_qc exit 0 each; validate_bundle 38 / 11 (pre-existing advisory); STACKING_CHECK PASS (OUT/STACKING_CHECK.md); no `__pycache__`. Tree sha after: c027b3b8bf2a.

## Side effects

- Lever shares fall with the larger P, but A, B and C each also fail all six new tests (their reserve or status change moves survivor rows), so points lost rise: A 41.9 %, B 43.5 %, C 48.9 % of P (all at least 25 %, G10). All-but-one overall at rubric 90: A 74.0, B 73.2, C 70.5, H7 88.5; at judge 4.55: A 31.3, B 30.5, C 27.8, H7 45.8.
- H7 alone costs 24 / 186 = 12.9 %, below the G10 25 % line, by design of the 85-95 % target.
- tests_qc WARN A3 (55 checks over the 35 guide) stays a warn; no cap applies (master 12:50).
- validate_bundle 38 passed / 11 failed, the same 11 advisory items as 593ecae.
- The two doc edits change no oracle byte on shipped data.

## Deviations from master directions

- F1 asked for one test per artifact the slip changes and to keep every artifact whose rows are a direct result of the allocation. The slip changes 11 artifacts on the planted seeds. I kept the three that own rows of a survivor principal-month: attention_allocation.csv, month_load_index.csv, commitment_ledger.jsonl. actionable_queue, blocked_commitments and deferred_queue are status subsets of the ledger and carry the same allocated_minutes copy. project_lineage, actor_rollup, project_rollup, audit_totals and reconciliation are sums, not rows of a principal-month. Testing all six row-owning artifacts would add 48 points (agent p2 77.1 %); all 11 would add 88 (agent p2 64.8 %, A alone 21.6 % < 25 %). Both miss the 85-95 % target, and the target governs.
- "run as nobody from a foreign cwd like the existing `_hard` families": the existing `_hard` families run through `_probe` as nobody with the verifier's cwd (`_invoke_program` passes no cwd). The new tests do the same; no foreign cwd was added.

## Lessons for the master

- Per-artifact survivor tests for a slip that ripples into 11 artifacts overshoot the 85-95 % band; name the owning artifacts in the direction | template_change: knowledge/LEVER_RULES_v1.md:61 (G1): add "an amplified slip counts only in artifacts that own rows of the separating unit; queues and sums of those rows stay untested"
- "by the same rule" after a two-branch rule is a W9 trap of its own | template_change: knowledge/LEVER_RULES_v1.md:56 (W9): add "a back-reference to a multi-branch rule (by the same rule) states the amount or branch outright"
- `_hard` families here run with the verifier cwd, so "foreign cwd" in directions does not match the harness | no change: note it per bundle
