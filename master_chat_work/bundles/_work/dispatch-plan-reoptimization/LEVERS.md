# LEVERS, dispatch-plan-reoptimization

## v0 levers (reconstructed from TRUTH.md and handbook, outcome from claude-opus-5 Run 1)

| id | family | lever | outcome | step quote |
|---|---|---|---|---|
| V0-01 | A | sequence cutoff 8140, not memo 9340 or report 9999 | LEAKED | #50 "cutoff 8140, the memo's rev3=9340 is lifecycle-voided" |
| V0-02 | A | EUR unit costs converted at the live treasury rate | LEAKED | #50 "treasury rate 1,047,514 micros (highest live sequence at or below the cutoff)" |
| V0-03 | A | capital envelope comes from the workbook, not the 4200000 steering figure | LEAKED | #50 "The 4,200,000 in the operator notes ... is the unratified steering figure" |
| V0-04 | A | holding rate 132 bps from the penalty schedule pdf | LEAKED | #31 "HOLDING ('132', 'bps', '3')" |
| V0-05 | A | energy surcharge 214 bps from the memo | LEAKED | #50 "energy surcharge 214 bps, rev5 is the - sentinel" |
| V0-06 | B | exact knapsack replaces greedy ratio drift | LEAKED | #50 "solved as an exact knapsack ... rather than the incumbent's greedy ratio policy" |
| V0-07 | A | lifecycle log void and restore across files | LEAKED | #50 "the lifecycle log is what settles the apparent conflicts" |
| V0-08 | A | horizon in fiscal order from fiscal_ordinal | LEAKED | #50 "fiscal order runs P05 to P24 then P01 to P04" |
| V0-09 | A | amendments accumulate, dedupe by amend_id | LEAKED | corrected_coefficients exact |
| V0-10 | A | VOI flag on restored rows | LEAKED | coefficient_corrections exact |
| V0-11 | A | adj_id first live copy, global | LEAKED | plant_utilization capacities match gold |
| V0-12 | A | K31/K44/K57 absent from status register give unknown_item | LEAKED | #50 "K31/K44/K57 are absent from the status register" |
| V0-13 | A | capital ties RP02/RP04/RP26 by value, capex, indicator | LEAKED | retrofit_selection exact |
| V0-14 | A | in-file rev/seq tie goes to the later row | LEAKED | data_quality exact |
| V0-15 | B | exact lot sizing replaces lot for lot | LEAKED | #50 "Lot sizing is an exact dynamic programme over contiguous coverage blocks" |
| V0-16 | A | mirror registers are stale | LEAKED | #36 "mismatches=['item_registry_bak.csv', 'plant_book_mirror.csv', ...]" |
| V0-17 | A | incumbent per-key coefficient dump is pre-correction evidence | LEAKED | #21 the agent read `basis: pre_correction` and did not republish it |
| LV-EF-L7 / V0-18 | A | lot-sizing cost tie: the earlier production period wins (K13) | HELD | agent splits K13 at P02, gold keeps one P23 lot; 14 chained checks fail |

Held 1, leaked 17. For why they leaked, see OUT/DIAGNOSIS.md.

## Harden round 1 levers

Every lever is graded on the four hidden sets H1 to H4 (all four carry every
constructed case), never on the shipped run. Outcome column = agent v0 solver
replayed on the hidden sets (local, stub rewardkit).

| id | family | rule text (handbook) | reflex reading | constructed hidden cases | checks the wrong reading fails | v0 replay |
|---|---|---|---|---|---|---|
| LV-DPR-01 | A (composition of documented rules) | s10 "compare their production periods starting from the last one in fiscal order and moving back; at the first position where they differ, the schedule whose production period there is earlier in fiscal order wins" | backward recursion that keeps the shorter, later block on a cost tie | 2 ties per set: setup row (rev 9) at a split period priced so split == merged; shipped K13 tie | m_tie: hidden_*_plan, _sourcing, _totals (all 4 sets), _certificate (3 sets); 32/101 | HELD (fails plan chain) |
| LV-DPR-02 | B (dependent chain) + decoy default | s7 "A key with no live setup row takes the `setup_fallback_cents` that its item carries under `item_defaults` in the runbook. An item that `item_defaults` does not list takes the control `default_setup_cents`." | control `default_setup_cents` 96000 (runbook control block and authority sqlite) for every key | 6 opened keys per set have every setup row voided through the lifecycle log (split across files), incl. one K22 key (unlisted, scope by omission, 96000) and one K14 key (41000); rare shipped boundary K14 P06 = 41000 | m_fallback: hidden_*_coefficients, _plan, _totals, _certificate in all 4 sets; 37/101 | HELD (v0 uses control default) |
| LV-DPR-03 | C (audit-repair pipeline) | s3 "rows that repeat one identity are one entry that is added once, taking the first live row in canonical order" + lifecycle log s3 | dedupe on first copy seen, live or not | per set: repeated amend_id whose first copy is voided by a log entry in adjustment_log.jsonl, and a repeated amend_id with two live copies | m_amend: hidden_*_coefficients and full chain, 17/101 | LEAKED (v0 handles first live copy) |
| LV-DPR-04 | F (error-path / rejection weight) | s5/s14 retired_item, unknown_item "has no live row in the item status register", sentinel; code normalisation s4; void_rows "blocked by their own void field or by the lifecycle log" | raw code compare; void count from the void column only | per set: `k_07` (retired), ` K-9n ` (unknown), TBD units on an active item; lifecycle voids of setup rows raise void_rows | m_rejnorm: hidden_*_quality, _totals 69/101; m_voidlog: hidden_*_quality 89/101 | LEAKED (v0 passes quality) |

Check to lever map: coefficients <- 02, 03; capital <- reseeded savings (V0-06/V0-13 carry over); quality <- 04; plan, sourcing, totals, certificate <- 01, 02, 03 through the chain. v0 replay 17/101 = 0.168 (capital 4, quality 12, existence 1).

## P12 r1 changes (22 Oct 2026)
- Type lever added: strict JSON type compare on all JSON/JSONL artifacts (1, 1.0, true differ). Harder.
- Certificate value type now stated in handbook (easier), offset by the strict type lever.
- Nondeterminism rule now stated in instruction (no effect on correct solvers).
- Judge R9 code quality w3; judge P = 21.

## P12 r2 changes (23 Oct 2026)
- H2 and H4 now re-author the figures held in penalty_schedule.pdf, amendment_memo.docx and capital_program.xlsx (holding rate, shortfall penalty, energy surcharge, capital budget, committed volumes). Harder: hardcoded binary figures fail every dependent group on two sets.
- Clock and process-start probes widened (time.monotonic, perf_counter, process_time, localtime, date.today, datetime.today; os.exec*, os.spawn*, os.posix_spawn*, os.fork*, multiprocessing, pty; literal names passed to __import__/import_module). Harder.
- `__import__`/`importlib.import_module` alone no longer fire the shell negative (IN-15). No effect on correct solvers.
- `negative_writes_outside_output_dir` no longer watches the input copy (AL-28); /app/data is judged once by R8. No effect (watch was unreachable as nobody).
- Instruction states the 400 s per-run limit. No effect.
- Oracle solver split into stages for R9. No effect on outputs.

## P12 r3 QC fixes (23 Oct 2026)

| Fix family | LV-DPR-01 tie | LV-DPR-02 fallback | LV-DPR-03 amendment | LV-DPR-04 rejection/void | Compensation |
|---|---|---|---|---|---|
| Credential scrub and runtime file/import/process audit | none | none | none | none | none |
| Recursive type-sensitive JSON comparison | harder | harder | harder | harder | none |
| Stated serialization checks on hidden groups | harder | harder | harder | harder | none |
| All 21 shipped values at existing weight 1 | none | none | none | none | none |
| Task-specific online lookup judge negative | none | none | none | none | none |

Trap replay (tests-only) kept the constructed separating cases on H1-H4. Before/after points earned of 101: oracle 101/101 both; reflex 17/101 to 16/101; m_fallback 32 to 31; m_tie 32 to 31; m_amend 32 to 32; m_rejnorm 69 to 68; m_voidlog 89 to 88. The variant sources and score JSON are in `WORK/trap/`.

## cc4bb7f judge rework from attempt 2 (23 Oct 2026)

| Change | LV-DPR-01 tie | LV-DPR-02 fallback | LV-DPR-03 amendment | LV-DPR-04 rejection/void | Compensation |
|---|---|---|---|---|---|
| R2 to R5 reply figures w3 to w1 | none | none | none | none | +8 points moved to R11, R12 |
| R11 sweep order (judge w5, state_change) | none | none | none | harder (judge column) | none |
| R12 rejected count from rejection artifact (judge w3) | none | none | none | none (a2 and oracle both pass) | none |

Judge P = 21 (unchanged), N = 11, 12 criteria. Tests, goldens and data untouched. Paper scores: a2 rubric 85.71 to 61.90 (overall 76.52 to 64.62); reference (a2 with the sweep fixed) rubric 85.71, overall 92.86.

## 77e8554 P12 v3 r1 QC v6 fixes (24 Oct 2026)

| Change | LV-DPR-01 tie | LV-DPR-02 fallback | LV-DPR-03 amendment | LV-DPR-04 rejection/void | Compensation |
|---|---|---|---|---|---|
| R11 rewritten: solver.py applies every rejection reason before out of scope (w5 to w3, code observable) | none | none | none | harder (judge column; a2 still fails) | none |
| R12 rewritten: agent checks how solver.py classifies a retired-item demand row above the cutoff (w3, trajectory) | none | none | none | harder (judge column; a2 now fails) | none |
| R10 one sentence (JD-5) | none | none | none | none | none |
| Merge two baked-answer negatives into `negative_shipped_results_baked_into_solver` -5 (TS-23) | none | none | none | none | none |
| `python -B` in grader (TS-16), M1 comment, `shipped_artifacts_match_contract` rename | none | none | none | none | none |
| Oracle reads sentinel tokens from nomenclature.yml; dead stores removed (outputs byte identical) | none | none | none | none | none |

Judge P = 19, N = 11, 12 criteria; tests 35 checks, P = 101, N = 20. Trap replay (tests-only, earned of 101, before = after): oracle 101, reflex 16, m_fallback 31, m_tie 31, m_amend 32, m_rejnorm 68, m_voidlog 88, a2 solver 68. Paper scores: a2 rubric 61.90 to 52.63 (overall 64.62 to 59.98); reference rubric 84.21, overall 92.11.

## 6cd567a P12 v3 r2 QC v6 (c2cde12) fixes (24 Oct 2026)

| Change | LV-DPR-01 tie | LV-DPR-02 fallback | LV-DPR-03 amendment | LV-DPR-04 rejection/void | Compensation |
|---|---|---|---|---|---|
| Oracle item scope `== "retired"` (DS-20; shipped and H1 to H4 outputs byte identical) | none | none | none | none | none |
| Hidden C5 rows: log entry above cutoff (H1, H3), own void=1 plus restore (H2, H4), negative energy half (H2 to H4) (AL-27) | none (ties rebuilt after, 2 per set) | none | none | harder (M10, M11 lose 48 each) | none |
| R11 deleted, settled by tests (JD-8); R12 renumbered R11 (kit J2 sequential ids) | none | none | none | none (tests still grade the sweep) | none |
| R6 relabelled instruction following with quoted sentence (JD-15/16) | none | none | none | none | none |
| Handbook cutoff sentence names the rejection-first order (IN-16) | none | none | none | none (sweep paragraph already stated it) | none |
| `negative_writes_outside_output_dir` also counts input-dir writes; R8 carved to acts other than running solver.py (TS-16, AL-28) | none | none | none | none | none |
| TRUTH "four optimality checks in their five check keys" (DS-22) | none | none | none | none | none |

Judge P = 16, N = 11, 11 criteria; tests 35 checks, P = 101, N = 20. Trap replay (tests-only, earned of 101, before = after): oracle 101, reflex 16, m_fallback 31, m_tie 31, m_amend 32, m_rejnorm 68, m_voidlog 88, a2 solver 68. New mutants before to after: M10 101 to 53, M11 101 to 53, M16 101 to 79. Paper scores: a2 rubric 52.63 to 62.50 (overall 59.98 to 64.92); reference rubric 81.25, overall 90.63.

## 2c2361c P12 v3 r3 QC v7 (31e7ead) fixes (24 Oct 2026)

| Change | LV-DPR-01 tie | LV-DPR-02 fallback | LV-DPR-03 amendment | LV-DPR-04 rejection/void | Compensation |
|---|---|---|---|---|---|
| Audit hook exempts from `read_outside` a path the same run already wrote; temp writes still count as writes outside the output directory (AL-28) | none | none | none | none | none |
| instruction.md:3 single process sentence (no subprocess, fork or multiprocessing pool) (IN-16) | none | none | none | none | none |
| Dead grader definitions removed; `_hardcodes_sample_answers()` and `_embeds_visible_records()` take no argument (TS-14) | none | none | none | none | none |

Judge unchanged; tests 35 checks, P = 101, N = 20. Trap replay (tests-only, earned of 101, before = after): oracle 101, reflex 16, m_fallback 31, m_tie 31, m_amend 32, m_rejnorm 68, m_voidlog 88, a2 solver 68, M10 53, M11 53, M16 79. AL-28 scratch write and read back: penalty -6 before, -3 after.
