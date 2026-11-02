# Corrections

adj_log.psv holds the corrections, one per row, laid out in dict_tx.md. Rows appear in no particular order. Corrections whose `seq` is at or below the cutoff sequence apply, in ascending `seq`; corrections above it do not apply and are only counted.

A `void` correction removes its transaction from the applied transactions. An `amend` correction replaces the magnitude of its transaction's amount by its `value`, in cents, and keeps the direction the transaction row gives. A later amend replaces an earlier one. A correction of a transaction that is already voided changes nothing, and so does a correction of a row that is malformed or out of period.

data_quality.json counts every correction at or below the cutoff sequence as applied, whatever its effect, and every correction above it as past the cutoff.
