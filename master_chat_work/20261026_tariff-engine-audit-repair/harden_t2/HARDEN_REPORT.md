# HARDEN_REPORT: tariff-engine-audit-repair, test-hardening round 2 (board 15b380e, 27 Oct 2026)

Bundle edited in place: `/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/tariff-engine-audit-repair/` (slug unchanged, no `--force`, no regeneration).
Session renamed to 15b380e (opencode `ses_e8616e2a0ffeSu1IABLJF1DIbi`; codex had no match). QC kit HEAD 5574d77e. Phase A: the blind read's staged `environment/` and `instruction.md` match BUNDLE (`diff -rq` empty).
Diagnosis: `DIAGNOSIS.md` (same folder).

## D2 decision (master condition 3)
harden_r2 DIAGNOSIS (25 Oct) rejected cumulative register reads at :125 and :161 with "large shipped change, and the rule would be explicit anyway". In this round D2 never touches shipped data: it fires only in hidden corpora, and the measured cost shows the explicit sentence still misses (blind round-1 program and per-row reading). The rejection reason does not apply, so D2 is kept.

## New rules (all in `environment/ci/api_contract.md`; one sentence plus one toy on invented 2031 X1/Y9/K values)

| id | rule | sentence (file:line) | toy | habitual reading (plausible wrong document, no crash) |
|---|---|---|---|---|
| U1 (S3 unique fit) | a plan's invoices are rated with the `tiers` of the one revision under which every paid invoice on the plan totals its paid amount; if no revision fits, or more than one does, the plan's own `tiers` | Tier definition :63-70 (verdict :65-67); `revisions` format only :115-117; witnesses in `payments.csv` :119-123 (separate file) | plan K / 12.00 :67-70 | `revisions` ignored; first fitting revision; first revision |
| D1 (derived state) | an invoice gets no credit when the account's previous invoice by `start` has a paid amount below that invoice's total | Credit :191-195 | X1 April 50.00 / 40.00 | credit applied per row; a missing row read as 0.00 paid |
| D2 (derived state) | a cumulative read bills its quantity less that of the same meter's accepted cumulative read with the latest earlier `day`; 0 with none; whole quantity when that earlier one is larger | Billed quantity :53-59, Period quantity :60-61, field `cumulative` :81 | Y9 900/940/15 -> 0, 40, 15 | raw count billed; chain per billing row; chain in file order |

`payments.csv` is optional (absent means no paid amounts). It is not shipped, and it is not added to the missing-input order. No sentence gives a procedure. No "try each revision" wording appears. Nothing sits beside `revisions` saying how to choose. "Previous invoice" uses the contract's existing order by `start`. "Previous accepted read" uses `day`. No order directive was added.

## BRANCH_FIRE (accounts whose document changes when the rule is switched off; WORK/t2_scripts/bf2.py)

| rule | shipped | each hidden corpus (fresh, rescaled, relocated, rotated, api, recoded, renamed) |
|---|---|---|
| U1 off / first fit / no-fit uses first | 0 | 5 / 3 / 2 |
| D1 off / missing row read as 0 | 0 | 4 / 10-16 |
| D2 off / per row / file order / rejected reads chained | 0 | 6 / 2 / 5-6 / 2 |

Shipped keys: `cumulative` 0, `revisions` 0, no `payments.csv`, no underpaid account.

Planting is `_levers` (tests/test_output.py :6705-7060). It uses its own RNG, `Random(seed*37+11+1000003*attempt)`, and runs after `_quiet` on new ids and plans. Each corpus gets these accounts:
- U1: 8 accounts on three plans. Plan A has one fit among three revisions, with a near decoy that fits the tier-1-only witness. Plan B has two fits, so the truth is the plan's own tiers. Plan C has no fit.
- U1+Q3: 2 accounts.
- D1+Q3: 2 four-invoice chains. In one, an underpaid invoice removes the next credit, and the next witness is the credited figure, so the arrears continue. The other mixes a missing row, an overpayment and an underpayment.
- D1+Q2+Q3+Q4: 2 accounts with carried allowance and a standing change.
- D2: 2 accounts with a shuffled file order, an outside-period count, a replaced estimated count, a reset and a plain read.
- D2+Q3: 2 accounts with the chain crossing billing rows.
- D2+Q5: 2 accounts with a meter exchange, an inactive count in the gap, and a lower count after the gap.

Plan A's witnesses use two meters crossing the cap by account position, plus re-shared allowance. `_levers_once` asserts that under Q3, N1 or N3 off the true revision no longer fits (master condition 1). `_assert_levers` proves three things: non-lever accounts are byte-equal to the round-1 document, each lever off moves exactly its owners, and each group has at least 2 accounts. A 300-seed sweep gave 300 ok and 0 fail.

## Counts and weights
- Tests: 69 checks (67 positive = 301 points; 2 negatives at -5 and -3, unchanged). Before this round: 54 checks, 226 points. The A3 WARN (above 35 checks) is kept per TS-23.
- New owned checks, 15 at weight 5:
  - revision: 3 checks plus revision_rows: 2 checks = 25 points.
  - arrears: 3 plus arrears_carried: 2 = 25 points.
  - cumulative: 3, cumulative_rows: 1 and cumulative_meter_rows: 1 = 25 points.
- Every existing check, weight and expected value is unchanged. The old checks skip owned accounts, and a snapshot of every reference document was byte-identical before and after the Ledger edit.
- Shares: hidden reruns are 270/301 = 89.7%; owned lever rows 24.9%; owned quiet rows 22.9%; shipped 4.7%; deliverables 5.6%.
- Rules: 77 graded stated rules plus L11, over 13 files in 8 formats (RULE_TRACE.md).
- Judge unchanged: 14 criteria, 33 positive points. No probe was added: the existing self-check prints no witness for the new rules.

## Measured COST_TABLE (tests share of 301; WORK/measure_variants.py on patched solve.py; real test file through run_checks.py)

| program | tests | checks failed |
|---|---|---|
| oracle | 1.0000 | 0 |
| **blind round-1 program (WORK/blind_r1)** | **0.7508** | 15 (exactly the new lever checks; no crash) |
| U1 off (revisions ignored) | 0.9169 | 5 |
| U1 first fitting revision | 0.9502 | 3 |
| U1 first revision always | 0.9169 | 5 |
| D1 off (credit per row) | 0.9169 | 5 |
| D1 missing payment row read as 0.00 | 0.7708 | 15 |
| D2 off (count billed raw) | 0.9169 | 5 |
| D2 chain per billing row | 0.9834 | 1 |
| D2 chain in file order | 0.9169 | 5 |
| Q1 off | 0.8804 | 8 (cascade into D2 replaced count) |
| Q2 off | 0.8970 | 7 |
| Q3 off | 0.7375 | 17 (cascade into U1 rows, D1, D2 rows) |
| Q4 off | 0.8372 | 11 |
| Q5 off | 0.9136 | 6 |
| all-but-one (best single-rule-wrong) | 0.9169 | 5 |
| first write (Q1-Q5, U1, D1, D2 all wrong) | 0.5216 | 30 |

Against the targets:
- Each new lever alone costs 8.3%, inside the 5-12% band.
- The blind program lands at 75.1, inside 70-90.
- All-but-one is 91.7, at or below the 92 cap.
- No variant fired a negative.

Two side readings fall outside the band:
- First fit on U1 costs 5.0%. It fails only the plan-B two-fit decoy, because the plan-A decoy is already rejected by the second witness.
- Reading a missing payment row as 0.00 costs 22.9%. The contract states the opposite in so many words.

## Gates
- STACKING_CHECK: `STACKING PASS` (`STACKING_CHECK.md`; tool class hints corrected by reading the code).
- xref_check: 65 entries, 0 findings.
- Validator: 40 passed, 0 failed.
- 4 QC scripts: 0 FAIL (WARN A3 only).
- PRECHECK last line: `PRECHECK CLEAN` (0 IN17/G5 warns).
- Docker: see the Docker section below.

## Not run
- No harness agent probe and no P13 blind read (by instruction).
- Round-1 rule mutants M01-M70 were not re-run: 14 of their solve.py patch targets moved. Round 1 killed 69/69, and the reference output for non-lever accounts is unchanged. The new rules have 8 variant rows in RULE_COVERAGE.md, each failing 1-15 checks.
- No probe was added to the judge.

## Docker (tests only; live-kit `exe_copy.py` copies; ALL_DONE 03:05:35)
Run folder `/tmp/opencode-logs/tariff-engine-audit-repair-15b380e-20261027T030030-0863`. The verifier image was warmed first. One nohup chain ran with the lock held, and the lock was released after it.
| run | trial | reward |
|---|---|---|
| oracle 1 | plain__LdCjt34 | 1.0 |
| oracle 2 | plain__9sgytC3 | 1.0 |
| oracle 3 | plain__Kni3XxV | 1.0 |
| owner-only | owner__Tp83piA | 1.0 |
| nop | plain__23bB9x6 | 0.0 |
| stub | stub__jyvHUCj | 0.0 |
| forgery | forgery__DQmGUt3 | 0.0864 |

## Final state
- TRUTH.md was rewritten by script as the last bundle edit (golden trial plain__LdCjt34). After that, PRECHECK printed `PRECHECK CLEAN` and xref_check found 0.
- No `__pycache__` or .pyc files are in the bundle. Tree sha: d95ee4203bbd.
- Tasks_INPUT sync: `cp -p` of 5 files (api_contract.md, solve.py, TRUTH.md, test_output.py, reward.toml). `diff -rq` BUNDLE vs Tasks_INPUT is empty.

## Lessons for the master
- A blind program that transliterates every per-row rule still loses all the owned rows of state that runs across invoices (fit over paid amounts, arrears, cumulative chains): 0.7508 with no crash | no change: matches LEVER_RULES_v3 S3/H6.
- Derived-state levers cascade through the quiet rules they ride on (Q3 wrong alone now costs 26.3%). Budget for that when the all-but-one cap is tight | no change: reported in COST_TABLE.
- A rare combination can be needed just to push a rule's alone cost above the all-but-one cap (Q2 0.930 -> 0.897 after Q2+D1+Q3+Q4) | template_change: LEVER_RULES_v3 G10, add "re-measure old quiet rules after the total grows".
- Round-1 mutant patches go stale when solve.py is restructured. Keep mutants as AST or function-level patches | no change: WORK-local tool.
