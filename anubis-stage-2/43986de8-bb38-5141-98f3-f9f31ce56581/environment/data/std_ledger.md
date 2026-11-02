# Ledger close

The ledger closes before the sweep runs. It turns the register of record, the three transaction exports and the bank's fee statement into one pre-sweep balance per envelope. The close runs in this order: each transaction row is tied to its envelope, the corrections apply, the keeping rates are settled, and the pre-sweep balances are formed.

## Envelopes and households

The envelope register of record is split over three register exports: env_a.csv, env_b.tsv and env_c.jsonl. Each uses its own column names; the crosswalk maps them to the canonical fields of dict_register.md. Every envelope appears in exactly one register export. An envelope reaches its household through its file number: the `file` table of hh_core.sqlite gives the household code of each file number, the `household` table gives the household's district id and family name, and the `district` table gives the district name for each district id. The category and the segment of an envelope come from its category code and funding code through std_codes.md.

## Transaction exports

Transactions come in three exports, laid out in dict_tx.md: tx_a.csv, tx_b.tsv and tx_c.bin. A row of tx_b.tsv names its envelope by an alias, which the `env_alias` table of hh_core.sqlite resolves to an envelope code: of the table's rows for that alias, the one with the latest `since` date on or before the row's date gives the envelope. A record of tx_c.bin writes the envelope code in any letter case. Envelope codes compare without regard to letter case wherever they appear, and reports write them as the register of record does. A row whose amount or direction is not written in the form dict_tx.md gives for its export is malformed: it is skipped and counted. Dates are always written as YYYY-MM-DD, except in tx_c.bin, which writes them as fmt_txc.md gives. A well-formed row that is out of period is skipped and counted. Every other row is a transaction of the period, and corrections apply to it (std_corrections.md).

## Keeping charge

The bank takes a keeping charge from every envelope for the month. Every envelope belongs to one keeping plan, which the `keep_plan` table of hh_core.sqlite names, and each keeping plan has one keeping rate for the month; no document of the office records the rates. An extract has between 4 and 11 keeping plans, and a keeping rate is a whole number of basis points (hundredths of a percent) from 12 to 50. An envelope's statement balance is its opening cents plus the signed cents of its applied transactions dated on or before the statement day. stmt_fees.csv (dict_tx.md) gives the statement day and, for each household, each funding code and each category code, the charge in cents the bank counted on the opening balances of its envelopes: for every envelope of the household, or with the funding code or category code, its opening cents times its plan's keeping rate divided by 10000 and rounded to whole cents (a value exactly halfway between two whole cents is taken to the one nearer zero), summed. The keeping rates of the extract are the one assignment of a rate of that range to every keeping plan under which every row of stmt_fees.csv holds. An envelope's keeping charge is its statement balance times its plan's keeping rate, divided by 1000000 and rounded to whole dollars.

## Pre-sweep balance

An envelope's closing cents are its opening cents plus the signed cents of all its applied transactions. Its pre-sweep balance is its closing cents converted to whole dollars by dropping the cents part, less its keeping charge. Closing cents, statement balances and pre-sweep balances are never below zero.

## Rules of the inputs

tx_c.bin carries the checksum fmt_txc.md gives. Each transaction id appears in one row across the three transaction exports. Every transaction row, malformed and out-of-period rows included, names an envelope of the register of record. Every correction at or below the cutoff sequence names a transaction id that one of the transaction exports holds. At least one assignment of keeping rates of the range to the keeping plans meets every row of stmt_fees.csv, and no two assignments both do. An extract that breaks one of these rules is not processed, and no report is written for it.
