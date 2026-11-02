# HARDEN_REPORT: tariff-engine-audit-repair, test-hardening round (78d433c, 26 Oct 2026)

Bundle: `/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/tariff-engine-audit-repair/` (edited in place, slug unchanged, no `--force`).
Session renamed 78d433c (opencode `ses_e87303bb7ffepy2orSLl6t5slR`; codex: no match). QC kit HEAD 5574d77e. `baselines.json` not found anywhere (searched); not used.
Phase A: run's staged tests/environment/solution/instruction identical to BUNDLE (`diff -rq` empty).

## New rules (all in `environment/ci/api_contract.md`, one sentence + one toy on invented 2031 / X1 / Y9 values)

| id | rule | sentence | toy | habitual first write (yields wrong document, no crash) |
|---|---|---|---|---|
| Q1 | estimated reads: `estimated` field; duplicate_read compares `estimated`; reason `replaced_estimate` when an accepted actual read of the same account, meter, day exists anywhere in the file | :65, :111-115 | :117-119 | key ignored: estimate billed or actual flagged duplicate |
| Q2 | `standing_changes` on a plan: charge of a day = entry with latest `from` on or before it, else plan charge; standing line = sum over active days of charge of the day / days in month | :92-96, :142-143 | :96-99 | plan `standing_charge` for every day |
| Q3 | one or more billing rows per account; each row its own invoice; read belongs to row holding its day; sort by account then `start`; outside_period = in no period | :76-77, :79-82, :110, :127-128 | :82-85 | dict by account, last row wins |
| Q4 | allowance no energy line of an invoice can take carries to the account's next invoice by `start` | :154-156 | :156-159 | leftover dropped |
| Q5 | one or more accounts rows per meter of an account; active on any row's days; one standing line | :41-43, :67-69 | :69-73 | dict by (account, meter), last row wins |

No new section; each sentence sits in the paragraph it governs. No "note that", "may also", "unlike", no word on shipped files lacking the case. Shipped data shows none of the new keys (0 `estimated`, 0 `standing_changes`, no second row anywhere).

## BRANCH_FIRE (accounts whose document changes when the rule is switched off)

| rule | shipped | each of fresh, rescaled, relocated, rotated, api, recoded, renamed |
|---|---|---|
| Q1 | 0 | 5 |
| Q2 | 0 | 5 |
| Q3 | 0 | 8 |
| Q4 | 0 | 3 |
| Q5 | 0 | 4 |

Planting: `_quiet` on own RNG `Random(seed*31+7)` after `_assert_bounds`; 17 planted accounts / 27 invoices per corpus; labels Q1 3, Q2 3, Q3 2, Q3+Q4 2, Q5 2, rare pairs Q1+Q3, Q2+Q3, Q3+Q5, Q1+Q5, Q2+Q3+Q4 one each (T4). `_assert_quiet` proves unowned rows equal the base document and each rule changes exactly its labelled accounts. 300-seed crash sweep: 300 ok, 0 fail. Base proof: shipped doc and every hidden corpus's unowned invoices and exceptions byte-identical to the pre-edit reference (`baseline/ref_before.json` vs `ref_planted.json`).

## Counts and weights
- Tests: 54 checks (52 positive = 226 points, 2 negatives -5/-3 unchanged); was 39 / 157. A3 WARN (cap 35) kept per TS-23.
- New owned-row checks (G1a ownership, existing checks now skip owned accounts): estimated 3x5, standing_change 3x5, meter_row 3x5, billing_row 5+5, carried_allowance 5+3, combined_row 3+3 = 69 (30.5%). Split into corpus groups because W2 allows only weights in {1,3,5}. Master's 15/15/15/12/12 became 15/15/15/10/8 + pairs 6: pair accounts are owned once (TS-26) and a Q3 miss also fails Q3+Q4 accounts.
- G3 shares: hidden reruns 41 checks 195/226 = 86.3%; shipped 6.2%; deliverables 7.5%.
- Rules: 69 graded stated rules + L11 found fact over 13 files in 8 formats (RULE_TRACE.md) -> Shape B PASS. Judge unchanged: 14 criteria, 33 positive; no new probes.

## Measured COST_TABLE (tests share, test points of 226; `cost_q2.json`)
| program | tests |
|---|---|
| oracle | 1.000 |
| Q1 wrong alone | 0.9071 (-9.3%) |
| Q2 wrong alone | 0.9071 (-9.3%) |
| Q3 wrong alone | 0.8938 (-10.6%) |
| Q4 wrong alone (Q3 right) | 0.9381 (-6.2%) |
| Q5 wrong alone | 0.9071 (-9.3%) |
| all-but-one (best, Q4 wrong) | 0.9381 |
| first write (all five wrong, rest right) | 0.6947 |

Targets: alone 5-12% PASS, first write <= 75 PASS, all-but-one <= 95 PASS. Old levers re-measured /226 (`cost_old.json`): L11 first/last 0.823, key-only crash (unchanged design), N1 one pass 0.7345, N2 start month 0.8009, N3 per meter 0.8009, coercion 0.4867. Rule mutants: 69/69 killed, none fires a negative (`mutants_fix.json`).

## Gates
- STACKING_CHECK: `STACKING PASS` (`STACKING_CHECK.md`, tool hints corrected).
- xref_check: 61 entries, 0 findings. Validator: 40 passed, 0 failed. 4 QC scripts: PASS / PASS / WARN (A3 only) / PASS, 0 FAIL.
- PRECHECK last line: `PRECHECK CLEAN` (0 IN17/G5 warns; WARN A3 only).
- Docker (tests only, live-kit `exe_copy.py` copies, run `/tmp/opencode-logs/tariff-engine-audit-repair-78d433c-20261026T215534-9f68`, ALL_DONE 22:00:49): oracle 1.0 / 1.0 / 1.0 (plain__PpHJzPz, FCrpQ9X, 95JsTWi), owner-only 1.0, nop 0.0, stub 0.0, forgery 0.115. Lock released.
- No `__pycache__`/.pyc in bundle. TRUTH.md rewritten by script as last bundle edit (states 226, N3 account position per invoice row, L11 code lookup per row's `plan`). Tree sha 49d3eafcc017.
- Tasks_INPUT sync: `cp -Rp` of 5 changed files (api_contract.md, solve.py, TRUTH.md, reward.toml, test_output.py); `diff -rq` BUNDLE vs copy empty.

## Not run
No harness agent probe (by instruction). No P13 blind read. `Q_only_Qn` variants not measured.

## Lessons for the master
- Kit W2 forces weights in {1,3,5}, so a 15-point quiet rule must be split into per-corpus checks; plan the split up front | no change: rule already in QC kit.
- Ownership filtering of existing checks is what keeps quiet-rule costs clean (each Q miss failed only its own checks) | template_change: LEVER_RULES_v3 G1a, add "existing whole-doc checks skip owned accounts".
- Mutants that remove a gate can crash new per-row lookups; patch them to fall through, not to crash | no change: WORK-local.
