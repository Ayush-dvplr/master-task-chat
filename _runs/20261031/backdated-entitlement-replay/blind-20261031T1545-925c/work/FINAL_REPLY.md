I wrote one program, `/app/out/derive_report.py` (Python 3, standard library only), and ran it once on `/app/data`. It wrote the nine documents to `/app/out`: summary.json, policy_audit.json, data_quality.json, region_North/South/West/East.json and segment_commercial/public.json. The run passed every consistency check I made.

**What the program does**
1. It checks that all nine declared inputs exist and parse. If one is missing it prints `missing input: <file>`; if one cannot be parsed it prints `malformed input: <file>`. Either way it exits with status 2 and writes nothing.
2. It recovers each account's anchor day and basis by testing all 56 pairs. A pair fits when rating the original events reproduces every line of every paid invoice.
3. It screens the corrections in `arrival_seq` order and merges the applied ones into the events. Paid and open invoices are then rated again, with proration amounts computed exactly as fractions and rounded half to even to the cent.
4. It posts credit day by day: transfers first in log order, then invoices in account order. Credit is taken from lots with the earliest expiry first, then the lowest lot ID. Overpayments become `<invoice>-OP` lots that expire 12 statement months later, and lots are split into expired and open at each account's window end.

**Key figures for EX-2025H2**
- Accounts: 400 total, all 400 resolved, 0 unresolved.
- Corrections: 46 applied and 20 rejected (6 unknown_account, 5 unknown_item, 5 before_window, 4 duplicate_id).
- Transfers: 183 accepted and 10 rejected (6 different_parent, 4 unknown_account).
- Invoices: 193 rated to a new total; 249 void invoices ignored.

| Figure | Amount (USD) |
| --- | --- |
| Original billed | 1118536.30 |
| Corrected billed | 1120387.00 |
| Credit applied | 76953.99 |
| Balance due | 102142.13 |
| Credits issued | 24885.65 |
| Credits expired | 353.57 |
| Closing credit | 240.38 |

**Checks run**
- **Full run:** exit 0 in 3.28 s, and all nine files were written.
- **Totals:** summary totals equal both the sum of the four region files and the sum of the two segment files, for all seven money keys.
- **Account and correction counts:** 400 account rows match the 400 resolved accounts and `accounts_total`. The 46 applied plus 20 rejected corrections make up all 66 in the input.
- **Per-account credit:** each account's `closing_credit` equals the sum of its open lots, and no `balance_due` is negative.
- **Transfers and expiries:** money moved in equals money moved out (1598.88), and the expiries add up to `credits_expired` (353.57).
- **Missing input:** a run against a folder that does not exist printed `missing input: accounts.json`, exited 2 in 0.11 s and wrote no output.
