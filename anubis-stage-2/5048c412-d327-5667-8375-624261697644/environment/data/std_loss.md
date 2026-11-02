# Conveyance loss standard

Every net gauging records water that a canal carried between two reservoirs under a delivery licence, and the authority accounts a conveyance loss for it to the licence's segment. The loss depends on the balanced storages of the gauging's two reservoirs, so it is computed after balancing of every basin.

## Segment of a gauging

A gauging belongs to the segment of its licence. `lc_register.json` holds a `licences` list giving, per licence, the `licence` code, the `scheme` code and the `date` (ISO form) of the delivery order; the list is not in any particular order. The segment of a licence is the segment that `sc_k2.docx` gives for its scheme. That document holds one table whose header row names the columns `scheme`, `class` and `segment`; each further row is one scheme.

## Loss rates

The conveyance loss rates are the rows of the table in `mt_loss.pdf`. The table's header line is `segment revised_on rate_milli`, and every line after it is one row: the segment, the `revised_on` date (ISO form) and the rate in thousandths of a kilolitre lost per megalitre of storage at the canal's two ends, separated by single spaces.

## Loss of a gauging

The loss of a net gauging is the rate in force for its segment on its licence's date, multiplied by the sum of the balanced storages of its two reservoirs, divided by 1000, and taken to whole kilolitres by loss rounding (`std_precision.md`). The balanced storage of a reservoir is the storage its basin reports for it (`std_balancing.md`).
