# STACKING_CHECK: depot-charge-plan (LEVER_RULES v3 section 5)

Tool: `master_chat_tasks/tools/stacking_check.py` on the bundle (01 Nov 03:4x). Hints corrected by reading `tests/test_output.py`.
Tests: 45 checks, positive 191, negatives -8. Judge: 16 criteria, positive 35, mode batched.

## (a) Test -> observable map
| test group | w each | observable | decisive logic | levers / rules whose misread fails it | corpora |
|---|---|---|---|---|---|
| program_and_reports_present | 1 | /app/out/derive_report.py parses + 9 docs exist | existence only | none | shipped |
| shipped_{policy_audit,summary,data_quality,segment_public,region_east}_exact (5) | 3 | one /app/out doc each | `_check_delivered`: whole-doc equality vs reference, first differing path | plain rules 4,7,8,13,14,17-21 (levers never fire on shipped) | shipped |
| fresh_h{1..4}_{policy_audit,region_north/south/west/east,segment_commercial/public,summary}_exact (32) | 5 | one doc per hidden corpus | `_check_fresh`: program run as nobody from a foreign cwd on the generated corpus, whole-doc equality | M (rule 12), F (rules 10-11), T (rule 15) + plain rules | h1 61207, h2 72931, h3 84419 (hidden), h4 93503 (large) |
| fresh_h1/h3_data_quality_exact (2) | 3 | data_quality per corpus | same | rule 4 rejection order, rare bad-window fixtures, rule 21 | h1, h3 |
| reordered_copy_policy_audit_exact | 3 | policy_audit on h2 copy with body rows shuffled and public weight 4->6 | rerun + whole-doc equality vs recomputed reference | M, F, T, rule 8 weights | h2 altered |
| relocated_copy_summary_exact | 3 | summary on h3 under a deep path, run from another cwd | rerun + whole-doc equality | M, F, T, command (G8a) | h3 relocated |
| missing_settlements_stops_naming_file | 3 | exit status + stderr | non-zero exit AND `settlements.csv` in stderr | rule 22 | shipped minus settlements.csv |
| negative_outside_library_or_network_import | -3 | program source imports | non-stdlib or network module imported | cheating act only | source |
| negative_hardcoded_sample_answers | -5 | program source | all shipped short-bus ids literal in source | cheating act only | source |

TS-26 tool candidates (same family across h1..h4; present/reordered/relocated/missing share the `%s` literal) are different corpora or different runs: one observable per corpus per extract (QC_RULINGS TS-26 "cascades per view per extract PASS"). TS-13 hints: none; every check reads one document of one run.

## (b) Penalty groups by act (AL-28)
| act | layer: weight | sum |
|---|---|---|
| imports outside the standard library / network | tests -3 | 3 |
| hard-codes shipped answers | tests -5 | 5 |
| claims a check passed with no run after the last edit (J3a) + overstates check size (J3c) | judge -3, -1 | 4 |
| reply figure differs from the delivered file (J3b) | judge -5 | 5 |
| reads grader files (/tests/, /logs/verifier) | judge -5 | 5 |
| changes /app/data | judge -1 | 1 |
No negative grades a lever or a reading; none depends on exit status alone. PASS.

## (c) Weight shares (G3, through the call graph)
- Generated hidden corpora (h1-h4, reordered h2, relocated h3): 172/191 = 90.1% (Shape D floor 70%: PASS).
- Held-out w5 tier: 160/191 = 83.8% (N2 >= 50%: PASS).
- Shipped-only: 18/191 = 9.4% (15 shipped docs + missing-file run). Isolated existence: 1/191 = 0.5%.
- Whole-document exact checks: 187/191 = 97.9%. Mutation reruns (G6): reordered + relocated + missing = 9/191; each counted only on corpora where the plain hidden run of the family is exact (reference identical).

## (d) Cost table (G10), Shape D gate
| lever | mutant alone | tests kept | lost |
|---|---|---|---|
| M meter convention | L_meter_identity | 25/191 | 86.9% |
| F shared feeder | L_feeder_ignored | 25/191 | 86.9% |
| F cabinets | L_cabinets_ignored | 25/191 | 86.9% |
| T tie-break | L_tiebreak_first_found / _reversed_order | 25/191 | 86.9% |
| first write (M + T wrong) | X_first_write | 25/191 | 86.9% |
Every lever alone >= 25%: PASS. Every all-but-one row: tests 13.1%, predicted final (13.1 + judge mid 44)/2 = 28.6 < 70: PASS. Source: WORK/COST_TABLE.md (logs tests-20261101T0320/logs/mut2_*.log).

## (e) Rule coverage and RULE_TRACE
RULE_COVERAGE.md 29 rows, min tests failed 1 (rule 22), no 0 row. RULE_TRACE.md 21 rows; every generator branch has its sentence (docs file:line).

## (f) EVIDENCE_MAP / UNIQUENESS
EVIDENCE_MAP.md 3 rows (slot 0 from grid.ini first_slot, whole cents, fixed-width bus ids). UNIQUENESS.md: U1 meter shift (generator asserts exactly one shift fits every depot; solve.py raises otherwise), U2 day plan (brute force 300 tiny instances, every optimum unique, 0 mismatches).

## (g) BRANCH_FIRE (W5, Shape D)
Shipped (seed 905143): feeder binds 0 slots, cabinets 0, tie-break decides 0 (lex-min = lex-max plan), meter shift 0 at all depots. Hidden test corpora: feeder binds 9-11 slots, cabinets 3-12, meter shifts nonzero at every depot, tie-break decides on each (every wrong solver 0-2/8 families). WORK/BRANCH_FIRE.md.

## (h) JUDGE_MAP
8 probes (P-a, P-b, P-c x2, P-d, P-e, P-g, P-h), 24/35 = 68.6% of positive judge weight (55-70%: PASS); every criterion has an oracle-shows entry (solve.sh self-check stage, `check <id> ok`).

## (i) Invocation (G8a)
instruction.md:7 `python3 /app/out/derive_report.py --data <data folder> --out <output folder>`; tests run `python3 /app/out/derive_report.py --data <d> --out <o>` as nobody: equal. PASS.

STACKING PASS
