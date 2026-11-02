# BLIND REPORT: 1861cfe / backdated-entitlement-replay (P13, design blind)

Session rename: ran name_session.py 1861cfe. Its list showed `opencode: ['ses_e6ec64aacffeXZxiVEZFfXR5uQ']` (a session ID, not the name "1861cfe") and `codex: no match`. Noted here and not retried.

## Files read, in order
1. instruction.md
2. environment/data/rule_register.md, billing_terms.md, correction_policy.md, credit_policy.md, output_contract.md, legacy_terms.yaml, price_book.json
3. Heads of accounts.json, corrections.json, credit_lots.json, entitlement_events.jsonl, invoice_lines.csv, invoice_register.tsv, ledger_activity.log, followed by stdlib profiling scripts over all the data files

environment/ holds no Dockerfile, only data/.

## Timing
- Start 14:41:19 IST. First full write of app/derive_report.py about 14:43 (`date` showed 14:43:59 right after the write). Minutes to first full write: about 3.
- Program run: real 3.28 s on the shipped data, well under 60 s.

## Self-check (on shipped data only): PASS
- All nine documents exist, use indent 2 and end with a single newline. Money values are 2-decimal strings.
- Summary totals equal the sum of the region totals and the sum of the segment totals for all 7 keys.
- Accounts: 400 rows = 400 resolved + 0 unresolved = accounts_total. Corrections: 46 applied + 20 rejected = 66.
- closing_credit equals the sum of open_lots for every account. No negative balance_due.
- Transfers in = transfers out = sum of moved (1598.88). Sum of expiries = credits_expired (353.57).
- Error path: a missing input folder printed "missing input: accounts.json" and exited 2 without writing output.
- Crash fixed: none; no crash happened.
- Deviation: the first run used /tmp as its working directory (to prove the program does not depend on its cwd). Nothing was read or written there.

## Lessons for the master
- A negative corrected total (a seat reduction through proration) is not covered: should credit apply to it, and does a negative amount due become an overpayment lot? I chose credit 0 and read "paid exceeds amount due" literally.
- If an applied correction's first affected month falls after the window, its value is unspecified. I write null (this data has no such case).
- "Declared input file" is not defined. I took it as the 9 files in the rule_register Input table, not the .md documents.
- On these data all 400 accounts resolve, so the anchor_none/anchor_ambiguous and account_unresolved paths are never exercised.
- Ordering of transfers dated after an account's window end, and of payment lines whose account differs from the invoice's account, is unspecified. I keyed payments on invoice= and posted every transfer in the log.
