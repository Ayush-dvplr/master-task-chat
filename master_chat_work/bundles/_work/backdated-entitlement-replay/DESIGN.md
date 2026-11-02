# DESIGN: backdated-entitlement-replay (board 99230f0, Shape D, lever pilot P-A / P-B / P-C)

## 1. Job and spine
The agent writes one reusable program `/app/out/derive_report.py`, run as
`python3 /app/out/derive_report.py --input <dir> --output <dir>`, that reads a subscription billing extract and writes the ten fixed documents of the archetype (`summary.json`, `policy_audit.json`, `data_quality.json`, `region_{North,South,West,East}.json`, `segment_{commercial,public}.json`) and leaves its own outputs for the shipped extract in `/app/out/`.

Spine stages (every one feeds the next):
1. Parse and validate the nine data files (missing -> exit 2 `missing input: <name>`; malformed -> exit 2 `malformed input: <name>`).
2. Recover each account's anchor day (1-28) and proration basis (`actual` or `thirty`) from its own paid invoices, rated with the original entitlement events; exactly one of the 56 combinations must reproduce every paid line, else the account is unresolved (`anchor_none` / `anchor_ambiguous`, with `candidates_fitting`).
3. Screen corrections (stated check order) and insert the accepted ones into the entitlement timeline in effective-date order (same account, item and date: higher `arrival_seq` stands).
4. Replay from the earliest effective correction: re-rate every non-void window invoice with the recovered anchor/basis.
5. Re-derive the credit ledger per parent group in date order: lot application at each issue, payments, overpayment lots (expiry from the live legacy key), transfers capped by the replayed balance, expiries; transfers on a day before that day's invoices.
6. Write the documents; region/segment/summary carry each account's anchor, basis and replayed balances (COUPLING).

## 2. Input files (`/app/data/`, flat; 14 files, 7 formats)
| file | format | shipped rows | read by stage | depends on |
|---|---|---|---|---|
| rule_register.md | md | ~40 lines | all (register + arbiter) | - |
| billing_terms.md | md | ~70 | 2, 4 | price_book, events, register, lines |
| correction_policy.md | md | ~50 | 3, 4 | corrections, accounts |
| credit_policy.md | md | ~70 | 5 | lots, log, legacy_terms |
| output_contract.md | md | ~120 | 6 | all |
| accounts.json | json | 400 accounts (2407 lines) | 2-6 | - |
| price_book.json | json | 4 items | 2, 4 | - |
| legacy_terms.yaml | yaml | ~12 lines | 5 (one live key) | credit_policy |
| entitlement_events.jsonl | jsonl | 2879 | 2, 3, 4 | accounts, price_book |
| invoice_register.tsv | tsv | 5050 | 2, 4 | accounts |
| invoice_lines.csv | csv | 20207 | 2 | register |
| corrections.json | json | ~66 records (530 lines) | 3 | accounts, events |
| credit_lots.json | json | ~250 lots (2242 lines) | 5 | accounts |
| ledger_activity.log | log | 5323 (PAYMENT + 193 TRANSFER) | 5 | register, accounts |

Volume (A5): every csv/tsv/jsonl/log file >= 2000 lines; total ~38,700 lines.

Chains (length >= 4):
- C1 invoice_lines.csv + invoice_register.tsv status -> anchor/basis fit -> cycle start dates -> `legacy_terms.yaml` live `credit_expiry_cycles` -> overpayment lot `expires_on` -> later credit application -> `closing_credit` in region -> segment -> summary.
- C2 corrections.json -> timeline -> re-rated invoice (fit anchor/basis) -> credit applied and overpayment lot -> transfer cap in ledger_activity.log -> receiver lots -> region/segment/summary.
- C3 accounts.json parent/region/segment -> transfer screening (`different_parent`) -> receiver lots -> region file -> segment aggregation -> summary counts.
- C4 register `void` status -> excluded evidence -> fit -> `before_window` (anchor-dependent first cycle start) -> `data_quality.rejected_corrections` -> `summary.corrections_applied`.

## 3. Rule register (planned, ~22 rules; file = governing file, W2)
billing_terms.md: B1 cycle = anchor day A of month M to the day before A of M+1, invoice for M issued on the cycle start; B2 anchor 1-28 and basis per account, recovered from that account's paid invoices rated with the original events; void and open invoices are no evidence; exactly one combination must fit, else unresolved (`anchor_none` 0 fit, `anchor_ambiguous` >1, `candidates_fitting`); B3 recurring line = quantity held on the cycle start day x price (a change dated on a cycle start is billed in full on that cycle, no proration); B4 proration line on the next invoice: (new - old quantity) x price x days from the change day (included) to the next cycle start / L, L = days of the cycle (`actual`) or 30 (`thirty`); B5 each line rounded half-even to cents, invoice total = sum of lines; B6 line order; B7 quantity on a day = last event on or before it.
correction_policy.md: C1 correction = entitlement event at its effective date; C2 effective-date order, same account+item+date: higher arrival_seq stands; C3 rejection order unknown_account, unknown_item, duplicate_id (later arrival), account_unresolved, before_window (effective before the account's first window cycle start); C4 replay re-rates every non-void window invoice; `first_affected_statement_month` = first month whose cycle start is on or after the effective date.
credit_policy.md: K1 lot usable from `created_on` up to the day before `expires_on`; K2 at issue, credit applied earliest `expires_on` then `lot_id`, up to the total; K3 paid = sum of PAYMENT lines, `balance_due` = max(due - paid, 0), overpayment lot `<invoice_id>-OP` created on the issue date, expiring on the anchor day N statement months later, N = `credit_expiry_cycles` in legacy_terms.yaml (the one key still in force); K4 on one date transfers post before that date's invoices; transfers in log order, invoices by account_id; K5 transfers within one parent only; moved = min(requested, sender's usable balance in the replayed ledger), the log's `posted` figure is history; rejections unknown_account, different_parent, account_unresolved; K6 receiver lots `<transfer_id>-<k>` keep the source expiry; K7 closing at the end of the account's last window cycle; lots with `expires_on` on or before it are expired.
legacy_terms.yaml: header states it is superseded by billing_terms.md and credit_policy.md for every key except `credit_expiry_cycles` (S5 partial-authority decoy, graded both sides: dead keys `default_anchor_day: 1`, `default_basis: actual`, `rounding: half_up`; live key read).
output_contract.md: schemas, sort orders, 2-decimal amount strings, error strings, exit codes. rule_register.md: governing file per topic and the arbiter sentence (the topic's governing file wins).

## 4. Sharp rules (Shape D: three levers)
### L-FIT (P-B, S3 unique fit, S2 degenerate shipped): rule B2 in billing_terms.md
- Reflex (PREMORTEM): loop 1..28 x {actual, thirty}, `break` on the first candidate that reproduces the invoices (H8); evidence = every invoice of the account (void included); self-test on shipped only (H9), where every account fits only 1/actual.
- Hidden: every extract uses anchors 2-28 and both bases; every hidden extract carries one void invoice rated at the superseded legacy default (disagrees with the true fit); tier PB1 (account whose only change falls in the open invoice's period: several anchors fit), PB1b (actual-basis account whose prorations all fall in 30-day cycles: both bases fit), PB2 (one paid line off by a cent: none fits); the second extract of every other tier carries one quiet account (no change in the window: all 56 fit).
- Why shipped cannot confirm: shipped truth is 1/actual for all 400 accounts with unique fit; first fit == unique fit; voids agree; no quiet account. Shipped fires 0 (BRANCH_FIRE).
- UNIQUENESS: generator asserts, per hidden extract, reference unique fit == truth for every non-target account, the planted outcome for every target and quiet account (WORK/UNIQUENESS.md in Phase 4).
### L-REPLAY (S1 core): rules C1, C2, C4, K5 cap, K3 live key
- Reflex: forward-only adjustment of the invoice holding the effective date with one delta; transfer amounts taken from the log's `posted`; N fixed.
- Hidden: every extract has accepted corrections effective before later invoices; PA4 sender balance after replay below the posted amount; PS N = 2-3 so overpayment lots expire inside the window (shipped N = 12, beyond the window).
### L-PAIRS (P-A: one stated pair per small extract): B3, K1, K4, K5, C2, B5, K3
| tier | pair | sentence | reflex wrong reading |
|---|---|---|---|
| PA1 | correction effective exactly on a cycle start | B3/C4 | half-open: billed from the next cycle, prorated |
| PA2 | lot `expires_on` equal to an issue date | K1 | inclusive expiry (still usable that day) |
| PA3 | transfer on the sender's issue date | K4 | invoices first (midnight / timestamp order) |
| PA4 | transfer capped by the replayed balance | K5 | log `posted` figure |
| PA5 | two corrections on one item, arrival order reversed | C2 | last arrival wins |
| PA6 | exact half-cent proration (SEAT-PRO, 28-day cycle) | B5 | half-up |
| PS | live legacy key N = 2-3 | K3 | N = 12 / ignore legacy file |
Interaction: every pair is rated with the recovered anchor/basis (a wrong fit makes the pair row wrong anyway) and its effect flows into the credit ledger (C2 chain).

## 5. Rejection paths
Corrections: unknown_account, unknown_item, duplicate_id, account_unresolved, before_window (shipped carries 5 of each plain kind; account_unresolved hidden only). Transfers: unknown_account, different_parent, account_unresolved. Accounts: anchor_none, anchor_ambiguous. Inputs: missing or malformed file -> exit 2 with the stated message, no partial output.

## 6. Test plan (LEVER_RULES v3 G1-G13)
- Hidden tier: embedded seeded generator in tests (seed only in tests, own RNG stream for plants), 10 tiers x 2 extracts; the agent's program run as `nobody` from a foreign cwd with exactly the stated command; per tier 3 whole-document checks w5 (ledger, rollup, control) = 30 checks, 150 points.
- Shipped: 3 family checks w3 (9) comparing `/app/out` and a rerun.
- Mutation (G6, counted only where the plain hidden run of the family is exact): M1 shuffled rows + relocated input dir; M2 run twice from a foreign cwd (byte-identical). 2 x w3.
- Existence w1 (program file present).
- Positive total 166; hidden share 150/166 = 90.4% (G3 Shape D >= 70%). 36 checks -> WARN A3 recorded.
- G1a OWNED: each family check owns its files for its tier; shared columns not re-graded elsewhere. G7 messages give the first differing JSON path. G12: generator asserts bounds, plants every branch, 300 seeds crash-free.
- Negatives (cheating acts only): `negative_program_ignores_input` -5 (identical documents for two different extracts), `negative_mutates_input_directory` -3.
- CL-4 one-fact-wrong: one wrong value fails one tier family = 5/166 = 3.0%.
- Lever shares of positive weight: L-FIT touches all 30 hidden checks (90%); L-REPLAY all 30 (90%); L-PAIRS 21 checks (63%); each lever alone wrong >= 25% (kill rows R4a, R1, all-pairs-wrong est. 70% lost).

## 7. Judge plan (J1-J10)
10 probes x w3 (important, process, trajectory), each printed by a solve.sh self-check stage (`check <id> ok` + witness): P1 P-a correction on a cycle start (B3); P2 P-a transfer on an issue date (K4); P3 P-g uniqueness witness (B2); P4 P-a ambiguous account built input (B2); P5 P-c recompute one corrected invoice total outside the program (B4/B5); P6 P-c recompute one closing credit (K1-K7); P7 P-d altered copy changing `credit_expiry_cycles` (K3); P8 P-e relocated rerun (instruction rerun promise); P9 P-h missing declared input (output_contract error string); P10 P-b one account where the void invoice disagrees, with the fit decision (B2). Plus J4 code quality w5, J6 per-item enumeration of unresolved accounts w5, J10 process order w3. Positive 43; probe share 69.8%. Negatives: J3a -3, J3b -5, scope -1, grader-read -5.
Judge estimate (section 6): lower 18.6 (J6 + J10 only), mid 41.9 (probes at 25%, J4 at 50%, J6 and J10 pass), upper ~70.

## 8. Expected loss per lever (careful solver)
| lever | hidden input | checks lost |
|---|---|---|
| L-FIT (H8) | quiet account in extract 2 of every non-PB tier; PB1/PB1b/PB2 | all 30 hidden checks |
| L-FIT (void as evidence) | ambient void on every extract | all 30 |
| L-REPLAY | every extract | all 30 |
| L-PAIRS, one pair | that pair's tier (PA2 slip also PS) | 3 (6 for expiry) |

## 9. DESIGN READY assessment (v3.7)
(a) predicted final = (first-write tests + judge mid)/2: PREMORTEM first write (first fit, R5b) 2.9 -> (2.9 + 41.9)/2 = 22.4 <= 35. Risk case: a first write that counts fits (R6, two pair slips) 79.0 -> 60.5, fails; the design blind decides.
(b) lever share >= 40%: 90% hidden, held-out w5 tier 150/166 = 90% >= 50%.
(c) no blind program above 65: not yet measured (Phase 0b).
(d) verifier worst case: ~25 runs x 60 s stated limit = 1500 s <= 0.9 x 2700 = 2430 s.
(e) kill table: every generic row loses >= 15% of lever points by WRONG (R6 loses 21.7%); shipped fast (0.6 s); reference 1.33 s <= 1/4 of 60 s.
Honest gaps: (1) a program that transliterates every sentence, including the uniqueness sentence and all pair sentences, is the reference and is EXACT; the lever rests on H8 (first fit) and H9 (shipped-only self-test of the pair sentences). (2) Judge mid 41.9 is above the <= 20 probe target: with the band capped at 70% and J4/J6/J10 expected to pass, mid cannot fall below ~35 unless the outcome criteria fail; final (a) therefore needs first-write tests <= ~28.
BRANCH_FIRE: WORK/BRANCH_FIRE.md (shipped 0 for all 12 hard-branch variants; each fires on both seeds). Per-probe expected Opus PASS: PREMORTEM.md probe table (P-e relocated and P-h missing input likely PASS; P-a/P-g/P-d unlikely).

## 10. Deviation from IDEA line 15 (decision for Ayush)
IDEA says the docs state exactly one combination fits each account and the generator asserts unique fit for every account. This design keeps that for every ordinary account, but states the unresolved outcome and plants ambiguous / none / quiet accounts on hidden extracts only, because with unique fit everywhere the first fit is the unique fit and row 4 keeps 100% of the fit lever (KILL_TEST strict-IDEA note). Fallback if Ayush rejects: drop PB1/PB1b/PB2 and quiet accounts; L-FIT then rests on H9 (anchor 1 shipped) and the ambient void only (R4c still 2.9; R4a 100 on fit).
Decision: IDEA line 15 changed, Ayush OK 31 Oct 14:30 (docs state the unresolved outcome anchor_none / anchor_ambiguous; hidden extracts plant no-fit, ambiguous and quiet accounts; shipped stays degenerate).
