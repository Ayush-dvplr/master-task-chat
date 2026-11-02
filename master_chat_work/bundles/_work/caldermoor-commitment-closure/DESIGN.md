# DESIGN caldermoor-commitment-closure

No DESIGN.md existed before this round; this file starts at harden round 2.

## Harden round 2 (593ecae, P9 r2, 24 Oct 2026)

Probe 1 on 8826f3a scored tests 133/133, judge 9/19, overall 73.69. Phase A
GENUINE. Primary cause 4 (levers weak by design): the agent read the blocked
predicate and the first-match walk correctly from the rule documents, helped by
an instruction hint ("rules are written in the document that owns the idea")
and by two explanatory sentences (dependency-semantics cycle carve-out clause,
cadence-register restatement of the discharged-and-waived case). Cause 3 PARTLY:
the P12 r1 cut of instruction.md:86-138 did not name A or B; nothing else in
8826f3a changed data or rule documents. Full write-up in
OUT/harden_r2/DIAGNOSIS.md.

### Levers

| lever | rule file:line | wrong reading | points lost alone (of 162) |
|---|---|---|---|
| A blocked predicate | dependency-semantics.md:50-51 | blocked set = class BLOCKED (closed dependents dropped) | 54 (33.3%) |
| B first-match walk | cadence-register.md:58-69 | discharged and waived period counted as waived | 57 (35.2%) |
| C waiver allowance (new, H6/L3) | cadence-register.md:49-54, 74-76 | only suppressing waivers draw on the allowance | 67 (41.4%) |

COUPLING quantity: the envelope reserve, commitment-protocol.md:189-195
(thirty minutes per blocked line of the principal in that month plus fifteen
per waived period of its cadences). It reads A (blocked set) and B/C (periods
waived), so a slip moves allocation and every deliverable that carries
`allocated_minutes`: attention_allocation, month_load_index (`reserve_minutes`),
commitment_ledger, blocked_commitments, both queues, project_lineage,
actor_rollup, project_rollup, escalation, audit totals, validation report and
run manifest. Carriers added this round: `actor_roster.csv` `waivers_granted`
and `waivers_lapsed`, `live_edges.csv` `dependent_blocked`.

### W1/W5 changes

- instruction.md: hint about the document that owns the idea cut; G5 sentence
  added ("Every deliverable is held to its exact bytes on each of those unseen
  extracts as well as on the shipped one.").
- cadence-register.md: restatement of the discharged-and-waived case cut; walk
  table is the only statement; counts defined as periods taken on each line.
- dependency-semantics.md: cycle carve-out moved into the blocked definition
  ("stands on no cycle"), explanatory clause removed.
- Shipped extract: generator `build_all(seed)` drops 252 edges and 74 waivers
  for SHIPPED_SEED only (`_SHIPPED_DROP`), so no shipped row separates A or B
  (and so not C's wrong reading). Hidden and probe seeds keep them.

### Grading

49 tests: 44 positive worth 162 points, five negatives. Fourteen shipped family
tests w3 (w2 is outside the kit's weight set, tests_qc W2), fourteen hidden `_hard` family tests w5 (one per family, eval seeds
rotated), escalation and class partition w5, thirteen w3 (ten probes,
identity, determinism, failed run), declared w1. Hidden/mutated reruns carry
more than 30% of positive weight. Judge: 12 criteria +22/-12, R12 added for
lever C (solve.sh `check 4 ok`). reward.toml 0.5/162 and 0.5/22.

### Reflex gate

Agent program (probe 1 final reconcile.py) under the new tests: 0.6014 before
strengthening, 0.4595 after try 1 (ledger/blocked/roster carriers), 0.3649 after
try 2 (lineage, live edges), 0.3519 once the shipped family checks moved to w3. Above 0.20 after two tries: PILOT WEAK: 0.3519.
The agent had A and B right; only C and the reserve separate it.

## Fix round 2 (5f2e150, P12 v3 r2, 24 Oct 2026)

- Evidence: differential fuzz CM-B (P2-022, P2-072): no hidden seed planted a
  principal-month whose floor survivors' clamped effort fits the distributable
  minutes, so the second share (commitment-protocol.md:207-210) was never
  graded; the probe-2 program scored 162/162 with the H7 re-entry slip.
- tests: `SURVIVOR_SEEDS = (4100149, 68250419)`; `_write_corpus` applies
  `_add_survivor_envelopes` (override envelope = reserve + a distributable amount
  where the floor drops at least one commitment and the survivors' effort is
  under it; up to 8 principal-months). Six owned-row tests: survivor_allocation,
  survivor_month_load, survivor_ledger, each `_exact` w3 on SURVIVOR_SEEDS[0]
  and `_hard` w5 on SURVIVOR_SEEDS[1], comparing only rows of the survivor
  principal-months (ledger: their commitment keys), first differing path in the
  message. P 162 -> 186, reward.toml test_output 0.5/186.
- Artifacts not given their own test: actionable_queue, blocked_commitments,
  deferred_queue (status subsets of the ledger rows carrying the same
  allocated_minutes), project_lineage, actor_rollup, project_rollup,
  audit_totals, reconciliation (sums, not survivor-month rows). Adding them
  would put the probe-2 program at 77.1% (6 row artifacts) or 64.8% (all 11)
  and A below the G10 25% line.
- Docs: commitment-protocol.md:207-210 second share reworded to fix the amount
  ("every one of the distributable minutes ... in proportion to clamped effort
  by largest remainder"), W9; record-layouts.md section 1 gains the outcome of a
  blank or MALFORMED_ROW line in the two budget tables (skipped, no envelope);
  oracle outputs on the shipped data byte-identical.
- Measured: oracle 186/186, probe-2 program 162/186 = 87.10%, A 58.06%,
  B 56.45%, C 51.08%, H7 87.10%; reference vs oracle on 300 fuzz seeds 0 diffs.

## Harden round 3 (da61544, P9 r3, 25 Oct 2026, LAST)

- Probe 3 (5f2e150 tree): tests 186/186, judge 3/22, overall 56.82, GENUINE. Fuzz on the probe-3 program: 0/300 corpora differ for A, B, C, H7 (all REVEALING); H7 leaked through its own W9 rewrite. OUT/harden_r3/DIAGNOSIS.md.
- New lever N2 "wait": glossary.md:57-59 one clause; commitment-protocol.md section 9 reserve now "thirty minutes times the wait of each commitment with a line in `blocked_commitments.csv` ...". No sentence pairs wait with chain depth. A, B, C, H7, the H7 wording and the five negatives unchanged.
- Code: solve.py `wait_of` + reserve; tests reference `wait` in reconcile(), reserve in compute(); `_SHIPPED_DROP` + EDG-000342, EDG-000454 (shipped edges_desk_01.csv regenerated, 2 rows fewer; 0 of 155 shipped blocked commitments separate); WAIT_SEEDS fixture `_add_wait_shortcuts` (WAIT_MAX_GROUPS 10, WAIT_MIN_MONTHS 4); tests wait_reserve_exact w3 / wait_reserve_hard w5 via shared `_owned_rows`; P 186 -> 194; reward.toml 0.5/194 and 0.5/25.
- Judge: R13 w3 recompute-wait conduct; solve.sh check_wait_reserve prints `check R13 ok`.
- Measured: oracle 194/194; N2 mutant 126/194 (35.05% lost); A 45.36%, B 48.45%, C 51.03%, H7 12.37%; probe-3 and probe-2 programs 0.4485 each.
