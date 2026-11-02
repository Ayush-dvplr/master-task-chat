# LEVERS stall-graph-postmortem (reconstructed, harden r1 Phase 1)

Status from the 25 Oct claude-opus-5 run, rescored on the fixed grader
(`jobs/fix-agent/b_stall_fix__NjtKJ9Z/verifier/reward-details.json`, 132/142) and the trajectory
(61 steps, 20:32:24-20:48:54Z). HELD = the agent's program failed the check; LEAKED = passed.
Doc paths are under `environment/data/`; test lines are `tests/test_output.py`.

## A. Twelve decode rules (flag word, `journal-and-wire.md`)

| # | flag | rule text (file:line) | constant / control | reference | check (line, w) | status | what gave it away |
|---|---|---|---|---|---|---|---|
| 1 | 0x001 | zigzag wait, first line outright, `journal-and-wire.md:42-46` | none | decode_journal 143-264 | trap_zigzag_wait 1441, 5 | LEAKED | one explicit sentence, transliterated at step 35 |
| 2 | 0x002 | hold xor low bits of previous wait, `:48-51` | chain width, CTRL-C | same | trap_chained_hold_mask 1450, 5 | LEAKED | sentence + CTRL-C hit at step 30 (search4) |
| 3 | 0x004 | stride order over the segment, `:53-57` | stride, CTRL-B | interleave_order over true count | trap_stride_interleave 1459, 5 | LEAKED | reading variants enumerated against CTRL-B, steps 23-26 ("HIT 5 7 logical False") |
| 4 | 0x008 | padding past the true count, `:59-62` | count window, CTRL-A | body[:n] physical tail | trap_biased_declared_count 1468, 5 | LEAKED | CTRL-A at step 18-22; pad order chosen by CTRL-B, step 26 |
| 5 | 0x010 | origin byte pairs in the opposite order, `:64-65` | none (CTRL-H confirms) | pair_reverse, full byte reversal | trap_reversed_origin_pairs 1477, 5 | LEAKED | first read as half swap; CTRL-H 76750712749 fixed it at step 34 |
| 6 | 0x020 | origin distance from previous segment, `:67-69` | none | prev_origin across file | trap_chained_segment_origin 1486, 5 | LEAKED | sentence + reach paragraph `:99-101` |
| 7 | 0x040 | '!' marks the FOLLOWING line in logical order, complement within width, `:71-74` | depth width, CTRL-D | prev_raw_symbol startswith '!' | trap_sentinel_escape 1495, 5 | LEAKED | follower reading transliterated correctly from the first scratch decoder (step 17); CTRL-D then pinned the width (steps 41-42 added "complemented depth must fit the width") |
| 8 | 0x080 | owner ring, read before write, `:76-81` | ring width, CTRL-E | ring advances on event lines only | trap_ring_owner_reference 1504, 5 | LEAKED | padding-writes variant enumerated, CTRL-E chose (step 26) |
| 9 | 0x100 | '~' spins times coarse unit, `:83-84` | coarse unit, CTRL-F | spins * unit | trap_coarse_spin_escape 1513, 5 | LEAKED | sentence + CTRL-F |
| 10 | 0x200 | token rotate by slot + offset mod 16, `:86-88` | token offset, CTRL-G | rotate right | trap_rotated_token 1522, 5 | LEAKED | sentence + CTRL-G |
| 11 | 0x400 | registry worker column, `:90-91` | none | resolve_identity 282-299 | trap_registry_alias_worker 1531, 5 | LEAKED | sentence + `identity-and-registry.md` |
| 12 | 0x800 | slot after colon (shadow slot), `:93-95` | none | rpartition ':' | trap_shadow_slot 1540, 5 | LEAKED | sentence |

Constants hold scale (CTRL-H) and epoch span (CTRL-I) are settled by the same search; CTRL-J/K check
quarantine count and residual bytes.

## B. Thirteen hidden window variations (`generalises_*`, w5 each)

| variation | generator mutation | rule text (file:line) | check line | status | what gave it away |
|---|---|---|---|---|---|
| to_a_fresh_stall_window | none, reseeded challenge tier | all of the above | 1550 | LEAKED | rules transliterated |
| when_budget_ties_move | ladder tie_config (834) | contended = more over than at/below, `attribution-and-blame.md:18-27` | 1559 | LEAKED | explicit comparison |
| when_waits_sit_on_the_budget | waits planted at budget | within budget = at or below, `attribution-and-blame.md:40-47` | 1568 | LEAKED | explicit |
| when_registry_presentation_order_inverts | rule_order (783) | lowest revision governs, bold, `identity-and-registry.md:21-26` | 1577 | LEAKED | bold rule + trap explanation sentence `:25-26` |
| when_a_service_cell_empties | host table cells East/North/South only (856-862) | four region files, `instruction.md:11`; zero report, `invariants-and-closure.md:50-53` | 1586 | HELD | agent derived cells from table values, `agent_program/derive_report.py:384` |
| when_the_registry_carries_a_cycle | cycle (783) | cycle unresolved, `identity-and-registry.md:35-39` | 1595 | LEAKED | explicit |
| when_the_pool_boundary_shifts | boundary_shift (783, 842) | pool at event's own epoch, `epochs-and-clocks.md:28-43` | 1604 | LEAKED | explicit |
| when_a_new_worker_enters | new_entity (783, 907) | registry only authority, `identity-and-registry.md:3-13` | 1613 | LEAKED | program reads registry |
| when_a_dormant_rule_fires | nonapplying_rule (783) | six-row hop limit, `identity-and-registry.md:35-39` | 1622 | LEAKED | explicit constant |
| when_the_partition_count_changes | host table North/South only (856-862) | as service cell empties | 1631 | HELD | same line 384 |
| when_the_window_scales | scale_population 60/100 (907) | no dependence on counts, `instruction.md:3` | 1640 | LEAKED | nothing hardcoded |
| when_the_window_contradicts_the_control_slice | contradict_calibration window table (842) | constants carried, `calibration-and-controls.md:53-61` | 1649 | LEAKED | carried record |
| when_every_tag_has_one_live_row | single_revision (783) | lowest revision, `identity-and-registry.md:21-26` | 1658 | LEAKED | explicit |

## C. Levers added in harden round 1 (built, measured)

Costs are measured on the 142 point test channel by reference mutants (`/tmp` driver, corpora built by
the unmutated reference). Oracle 142/142. Reflex on all three: 14/142.

### LV-1 closed partition set (structural habit; amplifies the habit Opus missed in the run)
- Rule text: `instruction.md:11` names four region files and two segment files;
  `environment/data/invariants-and-closure.md:50-53` "A cell or a segment that no counted event reaches
  still reports, and reports zero." Bound: `instruction.md:3` and `calibration-and-controls.md:53-55`
  (a later capture brings its own copies of the side tables, laid out as the shipped ones are).
- Determinate shipped fact (EVIDENCE_MAP): `invariants-and-closure.md:53`; empty partition content fixed
  by the empty LCK-B row in `sample_audit_answer.json:27` and present-only maps in
  `sample_summary_answer.json`.
- Reflex reading: partition set = values the host and tenant tables carry (run program
  `agent_program/derive_report.py:384-385`). Exit 0, plausible files, some missing.
- Hidden cases (12 of 25): drop cells only: trap_zigzag_wait, trap_sentinel_escape,
  a_service_cell_empties, a_new_worker_enters; drop segment only: trap_stride_interleave,
  trap_coarse_spin_escape, to_a_fresh_stall_window, the_window_scales; both: trap_reversed_origin_pairs,
  trap_registry_alias_worker, the_partition_count_changes, budget_ties_move. Plants live in `PLANTS`
  in `tests/test_output.py` (host_cell_table / side_tables filters).
- Checks failed alone: those 12 (60 pts, 42%).
- Interactions: independent of LV-2/LV-3 (file set, not figures).

### LV-2 padding writes the owner window (L1: green control, wrong answer; correctness fix D2)
- Rule text: `journal-and-wire.md:60-66` (0x008: padding lines are the last body lines as written and
  in logical order follow the event lines in written order); `journal-and-wire.md:81-86` (0x080:
  "Every body line of the file, in logical order, writes its own owner into the window slot").
- Reference now follows the text (`decode_journal` padding loop; `solve.py` `_decode_segment`).
- Control neutrality (W7): calibration tier puts ring references only in the first half of its
  segments and padding only in the second half, so every control figure reconciles under both
  readings; `recover` returns the same unique survivors under either reading; no control figure moved.
- Reflex reading: drop padding after the true count before the owner window sees it (the run's
  agent searched `ringpad` True/False against CTRL-E and kept False).
- Hidden cases: every challenge corpus with padding before a ring reference: all 13 generalises
  and the shipped window (shipped answers are not shipped as files; sample tier has flags clear).
- Checks failed alone: shipped_policy_audit + 13 generalises (68 pts, 48%).
- Interactions: co-fails with LV-1/LV-3 on shared generalises; never forces a slip on either.

### LV-3 owner tags follow alias rows (L10: general rule in a rarely joined field)
- Rule text: `identity-and-registry.md:57-66` (`## Owner tags`): resolved at the carrying event's
  epoch by following governing rows while they name a different tag; first self-naming tag is the
  owner whatever its status; no live row, a seventh row, or a revisit leaves the tag as written.
- Determinate shipped fact: alias rows `thread_registry.csv:36` (ALS-2001 -> WRK-1001) and `:60`.
  Shipped, calibration and sample owners all name themselves, so no shipped figure moves.
- Reflex reading: owner tag literal (run program `:336`, `:512-518`, `:534`, `:631`, `:639`).
- Hidden cases (12): trap_chained_hold_mask, trap_biased_declared_count, trap_chained_segment_origin,
  trap_ring_owner_reference, trap_rotated_token, trap_shadow_slot, waits_sit_on_the_budget,
  pool_boundary_shifts, registry_presentation_order_inverts, a_dormant_rule_fires,
  window_contradicts_the_control_slice, every_tag_has_one_live_row.
- Checks failed alone: those 12 (60 pts, 42%).
- Interactions: disjoint corpora from LV-1.

### Measured mutant table (142 channel)
| LV1 | LV2 | LV3 wrong | points | share |
|---|---|---|---|---|
| no | no | no | 142 | 100.0 |
| no | no | yes | 82 | 57.7 |
| no | yes | no | 74 | 52.1 |
| yes | no | no | 82 | 57.7 |
| no | yes | yes | 44 | 31.0 |
| yes | no | yes | 22 | 15.5 |
| yes | yes | no | 44 | 31.0 |
| yes | yes | yes | 14 | 9.9 |
