# STACKING_CHECK 0d8cf26 (P12 QC v3 fix)

Tool output: [stacking_tool.txt](stacking_tool.txt). `tools/stacking_check.py` on the fixed bundle and on PREV_QC_COPY a4ffe55 gives byte-identical output (`diff` empty): the TS-11 change adds a lock inside `_memo` and changes no check, observable, input or weight. The ql1 reading below therefore stands unchanged (tool G3 21.8% is the same name misread; call graph 637/670 = 95.1% hidden reseeded).

---


Tool output: [stacking_tool.txt](stacking_tool.txt) (`tools/stacking_check.py`, static hints). Corrections below come from reading `tests/test_output.py`.

## (a) Tests
158 checks: 156 positive (670 points), 2 negatives (-5, -3). Families (one observable and one decisive helper each; corpora are separate generated texts):
| family | checks | w | observable | logic | corpora |
|---|---|---|---|---|---|
| deliverables (archive, manifest, visible suite, corrected tests, regression rows, module notes, summary, report shape, previously_failing) | 9 | 1/3 | one artifact or file each | one `_check_*` each | shipped files / agent artifacts |
| shipped invoice + statement | 6 | 1/3/5 | shipped invoice rows, exceptions, statements | `_check_lines/_heads/_settlement/_exceptions`, `_check_statement_document` | shipped |
| hidden invoice families | 27 | 3/5 | lines, heads, settlement, exceptions per corpus | as above | 7 hidden corpora |
| owned-row families (Q1-Q5, U1, D1, D2, T4) | 31 | 3/5 | owned invoices only (G1a `_owned`) | `_check_owned` | hidden |
| statement sets statement / ledger / batch / cycle | 84 | 3/5/5 | statement list per corpus: feasible, due, redeemed | `_check_statement_feasible`, `_check_statement_field`, `_check_ledger_*` | 28 hidden documents, one call each |
| missing_source, two_runs | 2 | 3 | exit code + stderr; byte equality of two runs | `_check_missing_source`, `_check_two_runs` | hidden fresh copy (G6 mutation) |
TS-26: the tool's candidate group (deliverable checks sharing `_holds(lambda ...)`) reads 9 different files with 9 different helpers: not duplicates. Statement feasible / due / redeemed read three different properties (TS-13), pre-existing QC-passed shape.

## (b) Penalty groups (AL-28)
hardcoding -5 (test only); visible test removed or skipped -3 (test only); false pass claim R9 -5 (judge only); grader paths R10 -5 (judge only). Every group <= 5: PASS. No negative grades a lever.

## (c) Weight shares (call graph, not names)
- Shipped-only: shipped_* 18 + deliverables 15 = 33 / 670 = 4.9%.
- Hidden reseeded inputs: 637 / 670 = 95.1% (tool's 21.8% is a name misread: every corpus-named check builds its texts from the embedded generator).
- Lever (hidden-scale statements, S1H): 364 / 670 = 54.3% (>= 40%).
- Held-out w5: 535 / 670 = 79.9% (>= 50%, N2 shape).
- Whole-document per corpus (statement lists, invoice families): every hidden check compares its whole observable for the corpus (G1).

## (d) Cost / kill (see WORK/KILL_TEST.md and HARDEN_REPORT.md)
Shape D lever S1H alone: losing it costs 364 / 670 = 54.3% (>= 25%).

## (e)-(i)
- RULE_TRACE / BRANCH_FIRE / JUDGE_MAP updated for _ql1 (no new sentence; scale shapes fire 0 times on shipped data, on all 28 hidden statement documents).
- EVIDENCE_MAP: no new evidence-settled rule.
- Judge: 16 criteria, 42 positive, batched; probes R1-R6, R11-R16 = 36 / 42 = 85.7% (above the 55-70% band; the band was 82% before and passed QC; noted, not changed beyond R14-R16 the go ordered).
- Invocation (G8a): tests run `python -B -m tariff --statements <dir>` with `/app/repo/src` on the path, the contract :25-28 command.

STACKING PASS

## Lessons for the master
- A lock-only test change leaves stacking output byte-identical; diffing the tool output before/after is enough evidence | no change: already covered by Always 13 noise diff
