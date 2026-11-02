# HARDEN_REPORT: tariff-engine-audit-repair, test-hardening round 3 (board fc1fb76, 27 Oct 2026)

The bundle was edited in place at `/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/tariff-engine-audit-repair/`. The slug is unchanged. No `--force` and no regeneration were used.

**Session rename.** `name_session.py fc1fb76` printed `codex: no match` and `opencode: ['ses_e85c78cf3ffeqNBGmoOGQnxQAM']`. One opencode session was listed.

**QC kit.** HEAD is 5574d77e.

**Phase A.** BUNDLE `environment/` and `instruction.md` are identical to the round-2 blind copy (`diff -rq` empty). The blind program was copied to `WORK/blind_r2`.

**AUTO mode.** The master notes put this round in AUTO mode, so Phase 2 started without waiting for "go".

The diagnosis is in `DIAGNOSIS.md` in this folder.

## New rules (computational core plus a long-replay link). All are in `environment/ci/api_contract.md`.

### S1: exact optimum
- **Where it is written:**
  - :25-28 is the CLI `python -m tariff --statements <data_dir>`, with a 10-second limit.
  - :129-132 describes `vouchers.csv`.
  - :219-224 describes `redeemed`. It is the largest sum not above `balance`, using whole vouchers; when none fits it is `[]`.
- **Toy example:** :226-229, on invented X1 and A1-A4 values.
- **Readings it targets:**
  - largest-first greedy;
  - an exact search over subsets or a table of sums over cents. Both are exact on the shipped data but give no output inside 10 s on hidden data.

### S2: tie verdict
- **Where it is written:** :219-223. Ids go in ascending plain string order ("A10" before "A9"), and on a tie the first id list wins.
- **Toy example:** the same one (A1+A2+A3 beats A4).
- **Readings it targets:**
  - another optimal set;
  - ids in numeric order.

### S3: balance link
- **Where it is written:** :217-218. The balance is the account's invoice totals less paid amounts, and 0.00 when that is below zero.
- **Readings it targets:**
  - payments ignored;
  - no clamp at 0.00.
- **Why it matters:** the balance carries Q1-Q5, U1, D1 and D2, so any of those errors changes the optimum.

### Other edits
- `instruction.md:13` G5 sentence: "Each invoice, each exception list and each statement list is graded whole on fresh inputs, and only an exact match counts."
- No size, count or width bound is stated. No method word, no "note that", and no trap wording.
- Shipped `environment/ci/vouchers.csv` has 198 rows and 60 statements with 1-6 vouchers each.

### Hidden corpora
The hidden statement corpora (`_statement_texts`, own RNG `Random(seed*53+29+1000003*attempt)`) are separate from the invoice corpora, so every old check and expected value is byte-unchanged. Each corpus has 12 statements:
- 3 big cloned accounts: balances 50,000-90,000.00, 45-70 vouchers each, and the amounts share a factor the balance lacks, so the balance is never reached exactly;
- 8 small accounts with planted ties;
- 1 overpaid account at balance 0.00.

Each corpus draws its clone and small accounts from one round-1/2 rule family (`_STATEMENT_LEVER`):

| corpus | rule family |
|---|---|
| fresh | D2 |
| rescaled | D1 (+Q2/Q3/Q4) |
| relocated | Q1 |
| rotated | Q2 |
| api | Q5 |
| recoded | Q3+Q4 |
| renamed | U1 |

## BRANCH_FIRE (`WORK/t3_scripts/bf3.py`): shipped vs each hidden corpus
| branch | shipped | hidden (per corpus, all 7) |
|---|---|---|
| statements | 60 | 12 |
| big balance (> 1,000,000 cents) | 0 | 3 |
| greedy differs from optimum | 15 | 9-11 |
| tie (>= 2 optimal sets) | 1 | 2-4 |
| no voucher fits | 9 | 0-2 |
| balance clamped to 0.00 | 0 | 1-2 |

The optimum fires on the shipped data on purpose. It is a computational lever, not a quiet branch: shipped instances are small, and the hidden ones have the same form but are large.

## Counts and weights
- **Tests:** 91 checks: 89 positive worth 397 points, plus 2 negatives (-5 and -3, unchanged). Before this round there were 301 points.
- **New checks:** 22.
  - `shipped_statements_exact` (5).
  - Per hidden corpus: `<c>_statements_feasible` (3), `<c>_statement_due_exact` (5) and `<c>_statement_redeemed_exact` (5).
  - The feasible check covers accounts, order, balance, ids owned and distinct, sum within the balance, and a consistent `due`. It is graded apart from the two optimality checks.
- **Shares:** hidden reruns are 361/397 = 90.9%. Statement hidden checks are 22.9%, shipped checks 4.8%, deliverable checks 4.3%.
- **Rules:** 86 graded stated rules over 14 files in 8 formats.
- **Judge:** unchanged (14 criteria, 33 positive). No probe was added, because the oracle's self-check prints no statement witness.
- **A3 WARN:** 91 checks, above 35. Kept per TS-23.

## Measured cost table (tests share of 397; `WORK/t3_results/cost_final.json`; Docker timing in `python:3.12-slim`, 2 cpu)
| program | tests | checks failed |
|---|---|---|
| oracle | 1.0000 | 0 |
| blind round-2 program (WORK/blind_r2) | 0.7582 | 22 (all statement checks, no crash) |
| blind round-1 program (WORK/blind_r1) | 0.5693 | 37 |
| greedy, largest first | 0.8111 | 15 (hidden rows 1-3 of 12 right) |
| naive subsets / sum table / array DP | 0.7708 | 21 (exact on shipped, more than 30 s on all 7 hidden) |
| other optimal set / numeric id order | 0.8992 / 0.8992 | 8 / 8 |
| payments ignored / no clamp | 0.7708 / 0.8589 | 21 / 14 |
| Q1 / Q2 / Q3 / Q4 / Q5 wrong alone | 0.8438 / 0.8564 / 0.7154 / 0.7909 / 0.9018 | 14 / 13 / 25 / 19 / 9 |
| U1 / D1 / D2 wrong alone | 0.9169 / 0.9043 / 0.9043 | 7 / 8 / 8 |
| all-but-one (best single wrong) | 0.9169 | 7 |
| first write (eight rules wrong, exact optimiser) | 0.4207 | 50 |
| first write with sum table / with greedy | 0.4081 / 0.3955 | 51 / 52 |

The reference runs in 0.22-0.27 s per hidden corpus in Docker against the 10 s limit, about 1/37 of it.

Against the targets, every gate passes:
- **Blind r2:** loses 24.2% (target 10-30%), with no crash.
- **Greedy:** loses 18.9% (target at least 15%).
- **Naive exact:** loses 22.9% (target at least 15%).
- **All-but-one:** 91.7 (target at most 92).
- **Negatives:** no variant fired one.

## Gates
- **STACKING_CHECK:** `STACKING PASS` (`STACKING_CHECK.md`). Tool hints were corrected by reading the code:
  - the TS-26 group is a static artefact;
  - the AL-28 "UNMATCHED" pair joins two different acts;
  - G3 measured by code is 90.9%.
- **xref_check:** 71 entries, 0 findings.
- **Validator** (`validate_bundle.txt`): 40 passed, 0 failed.
- **4 QC scripts:** 0 FAIL (WARN A3 only).
- **PRECHECK last line:** `PRECHECK CLEAN` (0 IN17/G5 warns; `precheck.log`).
- **Docker** (tests only, copies built by the live kit's `exe_copy.py`, verifier image warmed first, one nohup chain, ALL_DONE 04:47:27; run folder `/tmp/opencode-logs/tariff-engine-audit-repair-fc1fb76-20261027T044036-5f21`):

| run | trial | reward |
|---|---|---|
| oracle 1 | plain__ELzaCpN | 1.0 |
| oracle 2 | plain__chgNhU5 | 1.0 |
| oracle 3 | plain__V5sasXo | 1.0 |
| owner-only | owner__gwzoFTs | 1.0 |
| nop | plain__SuRBDbS | 0.0 |
| stub | stub__xoeGXQz | 0.0 |
| forgery | | 0.0781 |

- **TRUTH.md:** rewritten by script (`WORK/t3_scripts/truth3.py`, golden trial plain__ELzaCpN) as the last bundle edit.
- **Bundle hygiene:** no `__pycache__` or .pyc. Tree sha is 53b0fc63f229.
- **Tasks_INPUT sync:** `cp -p` of 7 files (instruction.md, api_contract.md, vouchers.csv, solve.py, TRUTH.md, test_output.py, reward.toml). `diff -rq` BUNDLE vs Tasks_INPUT is empty.

## Not run
- No harness agent probe and no P13 blind read of this bundle. Those are the master's next steps.
- No judge run (no API key).
- Round-1 mutants M01-M70 were not re-run. The invoice checks and their reference are byte-unchanged.
- Blind-r1 first scoring returned 0.0. That was a harness artefact: its build script takes named arguments. It was rerun at 0.5693.

## Lessons for the master
- A rule stated as an objective (largest sum not above X) with a runtime limit and hidden instances large enough to rule out pseudo-polynomial search holds where stated transforms did not: greedy 81, plain exact search 77 | template_change: LEVER_RULES_v3.md:79 add "objective-only optimum with a stated time limit and no size bound" next to "exact optimum with a stated method".
- Put the optimum's planted accounts on one quiet-rule family per corpus; when every corpus draws from labelled accounts, single-rule cascades grow past the all-but-one cap | no change: recorded in WORK/LEVERS.md round 3.
- A stated verdict (balance 0.00 below zero) that no hidden account triggers costs 0, so plant one triggering account per corpus before measuring | no change: AL-27 already covers it.
- Blind-program harnesses must match each blind build script's own argument form; a 0.0 score is an artefact until the call is checked | no change: WORK-local tool.
