# QC_DEFENCE caldermoor-commitment-closure (P9 harden r2, 593ecae)

Written before any QC run. One entry per new lever, per rewritten lever rule and per cascade.

## C waiver allowance (new lever)
- QC rule ids at risk: IN-16 (two defensible readings), IN-15 (rule stated nowhere), TS-19 (hidden input out of bounds), AL-27 (rule never triggered).
- Live rule, cadence-register.md:49-54: "Each principal holds one allowance of four waivers for the whole window, shared by every cadence it owns. The waivers in elapsed periods of those cadences draw on it one each, in ascending order of period start and, for one start, of cadence id. A waiver that draws while the allowance lasts is granted, and a waiver that finds the allowance spent is lapsed. A cadence owned by nobody draws on no allowance, and every waiver in its elapsed periods is granted." Walk line :64 "the period holds a granted waiver"; effects :74-76.
- Why it passes: one reading only. "The waivers in elapsed periods ... draw on it one each" names every elapsed-period waiver, discharged or not; the order is stated with its tie; owner resolution is cadence-register §1 (:14-19). The tests grade it on hidden seeds whose waivers stay inside the register's stated period bounds (generator draws period indexes from the cadence span). No instruction sentence, no example, no note.
- Safe fallback: IN-16 -> DO "one settling clause in the governing file, written for the general case ("for every value type ..."), never for the specific row." Here: add to :50-51 "whether or not their period is discharged" after "draw on it one each". If AL-27: RULE_COVERAGE rows r23-r25 and leverC already fail tests; precheck re-reads them.

## A blocked set (kept, wording moved)
- QC rule ids: IN-16, W1 restatement checks.
- Live rule, dependency-semantics.md:50-51: "A commitment is blocked when it stands on no cycle and at least one live edge leaving it carries a block." Holding :43-44, carrying a block :46-48, cycle :~70.
- Why it passes: the predicate names the edge and the blocker only; nothing names the dependent's state, so a SETTLED dependent with a live blocking edge is blocked. The old explanatory carve-out ("so no closure pair carries a cycle member ... and no cycle member appears among the blocked commitments") is now the clause "stands on no cycle", a definition, not an explanation.
- Safe fallback: IN-16 -> DO as above: add "whatever its own state" after "A commitment is blocked" (general clause in the governing file).

## B waived periods (kept, restatement cut)
- QC rule ids: IN-16, IN-15.
- Live rule, cadence-register.md:58-69: "for each period take the first of these that applies" + table + "The discharged periods, the waived periods and the debt of a cadence are the numbers of periods the walk takes on the first, the second and the third line."
- Why it passes: periods_waived is defined by the walk line, so a discharged period (first line) is never waived. Before this round periods_waived was a column name with no definition (IN-15 risk); now it is defined.
- Safe fallback: IN-15 -> DO "State it once as a bare property in the file that governs that data, in that file's own vocabulary (W2, W3); no example, no 'note'." Already done; nothing further.

## Cascade: envelope reserve (coupling)
- QC rule ids: TS-26 (two checks pay for one observable), AL-28 is negatives only (n/a), CL-4 (one fact wrong stays one fact), TS-19.
- Live rule, commitment-protocol.md:189-195: "An envelope first gives up a reserve. The reserve of a principal for a settlement month is thirty minutes for each line of `blocked_commitments.csv` whose commitment belongs to that principal and has its commitment day in that month, together with fifteen minutes for each waived period of every cadence that principal owns, as `cadence-register.md` counts them. The distributable minutes are the envelope less the reserve, and zero when the reserve is the larger." output-contract.md:158-163 `reserve_minutes`.
- Why it passes: each family test owns its own files (allocation_and_load reads attention_allocation.csv + month_load_index.csv; queues reads the queues; ledger reads the ledger); a lever slip fails several families because each family's own rows change, which is the stated COUPLING, not a whole-document test. Measured one-fact-wrong per lever is 36-45% of test points, overall with measured rubric 47.37 stays < 70.
- Safe fallback: TS-26 -> DO "Name the observable each reads; narrow the wording of one so they read different observables, or merge into one at the larger weight." Here: drop `allocated_minutes` from the carrier that duplicates (project_lineage.csv first).

## Cascade: carriers (`allocated_minutes`, `waivers_granted`/`waivers_lapsed`, `dependent_blocked`)
- QC rule ids: IN-15, TS-19.
- Live rules: output-contract.md:90-98 (roster, lineage), :107 (ledger), :116-119 (live edges "`dependent_blocked` is `yes` when the dependent has a line in `blocked_commitments.csv`"), :130-136 ("Wherever a deliverable carries `allocated_minutes` for one commitment, it is that commitment's share of its envelope, and zero when the envelope gave it none.").
- Why it passes: each column is defined once where its deliverable is laid out, by reference to the deliverable that owns the figure.
- Safe fallback: IN-15 -> DO as in B.

## Shipped data without separating cases (W5)
- QC rule ids: DS-4 (answer recoverable from data), TS-25 (check passes on an absence), DS-6.
- What changed: tests/test_output.py `_SHIPPED_DROP` leaves 252 edges and 74 waivers out of the shipped extract only (rng consumption unchanged); every hidden seed keeps them. Shipped data stays exactly `build_all(SHIPPED_SEED)` (46 files, 0 mismatches).
- Why it passes: W5 requires separating cases only in hidden reseeded inputs; shipped data never contradicts the rules. The `_hard` tests and probes earn on hidden extracts, so no positive passes on an absence.
- Safe fallback: TS-25 -> DO "Replace with an assertion on earned output in a case that separates the readings." (already: `_hard` tests on hidden seeds).

## Fix round 2 (5f2e150): survivor second share, H7
- QC rule ids at risk: IN-16 (two defensible readings), TS-19 (hidden input out of bounds), TS-25 (check passes on an absence), DS-4.
- W9 self-test on commitment-protocol.md:207-209 (before): "A commitment whose share then falls below fifteen minutes receives zero, and the whole of the distributable minutes is distributed again by the same rule across only the commitments that held fifteen or more. When that leaves no commitment standing, every share is zero." Verdict: REWRITE. "by the same rule" can denote the section's whole procedure, which opens at :201-202 with the at-or-below branch ("each commitment receives its own clamped effort and the rest is left undistributed"); a reader who takes that reading gives each survivor its own effort when the survivors' effort fits, and the probe-2 agent program did exactly that (reconcile.py:663-677).
- After (commitment-protocol.md:207-210, same line count): "A commitment whose share then falls below fifteen minutes receives zero, and every one of the distributable minutes is distributed again, in proportion to clamped effort by largest remainder, ties settled as above, across only the commitments that held fifteen or more; when none held, every share is zero." The amount is fixed (every distributable minute) and the method is named, so the at-or-below branch has no way back in. No example, no note (W1).
- Hidden inputs: SURVIVOR_SEEDS envelopes are written into budget_overrides.psv as whole minutes for registered (actor, month) pairs, inside record-layouts.md section 7; they only replace an envelope, never add a field or a file.
- Owned rows: each new test compares only the rows of the survivor principal-months (attention_allocation.csv, month_load_index.csv) or of their commitments (commitment_ledger.jsonl); `_survivor_months` raises when fewer than two survivor months exist, so no check passes on an absence.
- record-layouts.md section 1 gained one bare sentence: "In `attention_budget.csv` and `budget_overrides.psv` a blank line or a `MALFORMED_ROW` line is skipped and records no envelope." It states what the oracle and the reference already do (solve.py from_separated skips blank lines and drops field-count mismatches; tests/test_output.py budget readers skip `__malformed__`); oracle outputs on the shipped data are byte-identical before and after both doc edits (28 of 28 artifacts). No test grades it.
- Safe fallback: IN-16 on :207-210 -> DO "one settling clause in the governing file, written for the general case". Already the case.

## Harden round 3 (da61544): N2 wait (H6 along a recursive chain, H3 defined term)
- QC rule ids at risk: IN-16 (two defensible readings), IN-15 (rule stated nowhere), AL-27 (rule never triggered), TS-19 (hidden input out of bounds), DS-4, CL-4 (one fact wrong costs more than one fact), W1 (no contrast sentence).
- Live rule, definition glossary.md:57-59: "**Wait** The wait of a commitment that is not blocked is zero, and the wait of a blocked commitment is one more than the greatest wait among the blockers of the blocking edges leaving it." Use, commitment-protocol.md section 9 (line 190 on): "The reserve of a principal for a settlement month is thirty minutes times the wait of each commitment with a line in `blocked_commitments.csv` that belongs to that principal and has its commitment day in that month, summed over those commitments, together with fifteen minutes for each waived period ..."
- Why it passes: one reading. The recursion is well founded (blocking edges among blocked commitments form no cycle, because a cycle of holding commitments makes its members UNRESOLVABLE and not blocked; terminal blockers and cycle members are not blocked, so their wait is zero). Every term it uses is defined in the same glossary (Blocking edge, Holding) or in dependency-semantics.md section 3 (blocked). No sentence names chain depth beside it, no example, no note (W1, W6). The definition lives in the glossary and the use in the protocol (W2).
- Hidden inputs: WAIT_SEEDS (30561877, 72914403) apply `_add_wait_shortcuts`: up to 10 extra edge rows in edges_desk_01.csv, each a copy of a live edge's own asserted_at between two admitted, holding commitments already joined by a two-step blocking path, so every row is inside record-layouts/dependency-semantics bounds; override envelopes in budget_overrides.psv are whole minutes for registered (actor, month) pairs (record-layouts section 7). The generator asserts at least WAIT_MIN_MONTHS = 4 principal-months part the two readings on each wait seed.
- Shipped data (W5): `_SHIPPED_DROP` gains EDG-000342 and EDG-000454, so on the shipped extract every blocked commitment has wait equal to its chain depth (0 of 155 separate); shipped data stays exactly `build_all(SHIPPED_SEED)`.
- Owned rows: wait_reserve_exact (w3, WAIT_SEEDS[0]) and wait_reserve_hard (w5, WAIT_SEEDS[1]) compare only month_load_index.csv rows of the parted principal-months; `_wait_rows` raises when fewer than 4 such months exist (no pass on an absence, TS-25).
- CL-4: the one-fact-wrong mutant (chain depth in place of wait) loses 68 of 194 test points (35.05%), inside the 25-45% band; the loss travels through the stated COUPLING quantity (reserve, commitment-protocol.md section 9).
- Safe fallback: IN-16 -> playbook row IN-16 DO "one settling clause in the governing file, written for the general case": add to glossary.md:59 "whatever path reaches that blocker" after "leaving it". AL-27 -> row AL-27 DO: WAIT_SEEDS fixture already constructs the case; RULE_COVERAGE row N2 fails 16 tests. IN-15 -> row IN-15: already stated once as a bare property in the governing file.

## Lessons for the master
- an allowance rule written "one allowance for every cadence it owns" reads as one per cadence; caught before QC and reworded to "one allowance ... shared by every cadence it owns" | no change: W3 already asks for plain forms
