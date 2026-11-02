# S13 credit and debit

Credits and debits are per contract per period, in integer milli
credits. The three rates and the two carry restore terms live only in
the credit_rates block of the binding workbook sheet.

## the delivered figure

delivered_kib of a contract period is the sum of accepted_kib over the
accepted rows whose binding contract, from S10, is that contract.

    shortfall_kib        = max(0, obligation_kib - delivered_kib)
    unused_reserved_kib  = max(0, reserved_kib  - delivered_kib)

## the outage test, which runs first

outage_claims.psv carries one row per claim. Only claims whose
claim_status is accepted count; rejected and withdrawn claims count for
nothing.

For the mission of the contract and the period in question, take every
accepted claim. For each, sum the seconds by which its half open window
[claim_from_s, claim_to_s) intersects the eligible sets of the accepted
rows of that contract on the aperture the claim names. Total those
seconds across the claims.

When that total reaches the outage qualifying floor from
network_operations_memo.pdf, the contract period is outage qualified.
The floor is a floor: a total equal to it qualifies.

A qualifying claim is an accepted claim whose own overlap total above
is one second or more. An accepted claim that overlaps no accepted row
of the contract contributes nothing to the test and is not a qualifying
claim, so it takes no part in the pool below.

## what qualification changes

    exempt_kib = min(shortfall_kib, exempt_pool)

exempt_pool is a sum taken claim by claim. Walk the qualifying
claims in claim_id order, and for each of them add the deferred_kib of
every accepted row of the contract that sits on the aperture that claim
names, excluding any row whose late_cancel is one. A row on an aperture
that two qualifying claims both name is added once for each of them, so
the pool counts claim and row pairs rather than rows. A pass the
operator cancelled after its commit boundary is the operator own doing
and does not swell the pool.

When the contract period is outage qualified:

    shortfall_debit_mcr = 0
    outage_credit_mcr   = (exempt_kib * outage_credit_mcr_per_mib) // credit_basis
    carry_restore_kib   = min(carry_forfeit_kib,
                              (exempt_kib * restore_num) // restore_den)

The shortfall is waived, not reduced. A pass that looked responsible for
a shortfall at S10 can be reclassified here, and the reclassification
changes the settlement and nothing operational.

When it is not qualified:

    shortfall_debit_mcr = (shortfall_kib * shortfall_debit_mcr_per_mib) // credit_basis
    outage_credit_mcr   = 0
    carry_restore_kib   = 0

## the unused reserved credit, which is always paid

    unused_credit_mcr = (unused_reserved_kib * unused_reserved_credit_mcr_per_mib) // credit_basis

credit_basis is credit_basis_kib_per_mib in unit_scaling_rules.json.
Every one of these divisions is a floor applied once, at this stage,
to the quantity named.

    net_mcr = unused_credit_mcr + outage_credit_mcr - shortfall_debit_mcr

## the compliance state

met when the shortfall is zero. exempt when it is positive and the
contract period is outage qualified. short otherwise.

## the outage ledger

One row per contract period, whether or not it qualified, carrying the
overlap total, the floor, the verdict, the exempt volume and the carry
restored. A contract period with no claim at all carries zeros.
