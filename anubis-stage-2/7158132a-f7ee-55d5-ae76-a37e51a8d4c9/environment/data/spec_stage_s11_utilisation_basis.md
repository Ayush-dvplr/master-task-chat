# S11 utilisation basis

Utilisation is an operational measure and it is computed from the
resolved ledger.

## the numerator

The occupied seconds of an aperture period are the sum of
eligible_seconds over the canonical rows that S07 accepted for that
aperture and period. Rejected passes contribute nothing. Displaced
passes contribute nothing, because the aperture was not occupied by
them.

Computing the numerator from pass_plan_of_record.csv gives a larger and
plausible number that agrees with no ledger in this settlement. So does
computing it from the admitted rows before S07.

## the denominator

The available seconds of an aperture period are the length of its
availability set from S02 intersected with the station local accounting
period from the calendar. The denominator is physical availability. It
is not reduced because a contract could not pay for the time, and it is
not reduced because a budget ran out.

## the ratio

    utilisation_bp = (occupied_seconds * 10000) // available_seconds

The result is integer basis points and the division is a floor. When the
denominator is zero the utilisation_bp is zero and denominator_state is
empty. An aperture withdrawn from service for the whole period is the
case that produces it. Any other denominator_state is populated.

## stations

A station numerator and denominator are the sums over its apertures,
summed before the division rather than after. Averaging the aperture
basis points gives a different number and is wrong.

## what utilisation never sees

An outage exemption at S13 does not restore utilisation. The aperture
was idle and the ledger says so; the contract relief is a separate
entry in a separate ledger. Nothing at S13 writes back into S11.
