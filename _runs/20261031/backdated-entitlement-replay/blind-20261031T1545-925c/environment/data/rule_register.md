# Rule register

This register lists the document that governs each topic of the entitlement
replay. When two documents disagree on a topic, the document named here for
that topic wins.

| Topic | Governing document |
| --- | --- |
| Statement months, billing cycles, anchor day, proration basis | billing_terms.md |
| Quantities, recurring lines, proration lines, rounding | billing_terms.md |
| Recovering each account's anchor day and basis | billing_terms.md |
| Backdated corrections, screening, replay | correction_policy.md |
| Credit lots, credit application, payments, overpayment credit | credit_policy.md |
| Credit transfers, expiry, closing credit | credit_policy.md |
| Credit lifetime in statement months (credit_expiry_cycles) | legacy_terms.yaml |
| Output documents, keys, ordering, number forms, errors | output_contract.md |

## Input files

| File | Content |
| --- | --- |
| accounts.json | Extract id, first and last statement month of the window, and every account with its parent group, region and segment |
| price_book.json | Monthly price per unit of each item |
| legacy_terms.yaml | Terms of the retired billing system; only credit_expiry_cycles is in force |
| entitlement_events.jsonl | Original entitlement events: from `date` on, the account holds `quantity` units of `item` |
| invoice_register.tsv | One row per invoice: account, statement month and status (paid, open or void) |
| invoice_lines.csv | The recorded lines of every invoice as originally billed |
| corrections.json | Backdated corrections to entitlement quantities |
| credit_lots.json | Credit lots held before the window opens |
| ledger_activity.log | Payments and credit transfer requests, one per line, in time order |

Every input file sits in one flat input folder. Dates are ISO dates
(YYYY-MM-DD) and statement months are YYYY-MM. Money amounts are decimal
strings in US dollars.
