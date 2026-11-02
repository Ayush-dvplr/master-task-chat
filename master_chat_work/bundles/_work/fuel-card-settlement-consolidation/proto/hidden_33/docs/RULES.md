# Settlement rule register

The monthly settlement data sits in three folders of the data directory:
`docs/` (the rule documents), `ref/` (master data) and `exports/` (one
settlement export per processor, at the path `ref/processors.json` gives).

## Documents

| document | governs |
|---|---|
| `docs/group_standard.md` | lines, business dates, scope, attribution, quantities, tax, rounding, discounts, settled amounts, reversals, duplicates, ledger ids |
| `docs/output_schema.md` | program invocation, failure behaviour, value forms, check order and reasons, ledger order, every output document |
| `docs/reference_data.md` | the layout and meaning of every file under `ref/` |
| `docs/handbook_kestrel.md` | the kestrel export |
| `docs/handbook_lumen.md` | the lumen export |
| `docs/handbook_marlow.md` | the marlow export |
| `docs/handbook_norvik.md` | the norvik export |
| `docs/handbook_oberon.md` | the oberon export |
| `docs/group_standard_2023.md` | the 2023 group settlement standard |

Where two documents disagree, the one listed higher in this table governs.

## Reference files

| file | holds |
|---|---|
| `ref/processors.json` | settlement month, processors, export paths and export settings |
| `ref/sites.csv` | sites, regions, UTC offsets, tax jurisdictions |
| `ref/cards.csv` | fuel cards and the accounts that hold them |
| `ref/accounts.csv` | accounts, segments and closing dates |
| `ref/products.xml` | product catalogue and processor aliases |
| `ref/discount_tiers.ini` | discount eligibility, tiers and caps |
| `ref/tax_rates.tsv` | tax rates by jurisdiction and tax class |
| `ref/batches.log` | processor batch events |
