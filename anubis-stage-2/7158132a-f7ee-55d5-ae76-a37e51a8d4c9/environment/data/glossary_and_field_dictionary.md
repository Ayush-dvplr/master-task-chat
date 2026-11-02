# glossary and field dictionary

aperture. One steerable antenna at one station. Identified network wide
by antenna_uid and locally by station_id with aperture_label.

accounting period. The station local settlement window, P1, P2 or P3,
derived from station_accounting_calendar.csv. Half open.

allowance. carry_in_kib plus entitlement_kib for one contract period.
Consumed carry first.

backlog. Volume the spacecraft is holding, in KiB, per mission per
period. The opening figure feeds S09; the running figure feeds S10.

basis point. One ten thousandth. utilisation_bp is an integer.

binding row. The row of a history that decides, as opposed to the rows
it superseded.

canonical row. One pass in one settlement period. The unit of the
canonical contact ledger and of everything after S04.

carry forward. Unconsumed allowance moving into the next period,
capped, and forfeited when the cap or the contract says so.

commit boundary. scheduled_start_s less the station commit lead. The
instant after which a pass counts as committed.

commit evidence. An operational event recorded at or before the commit
boundary by an operator whose grade carries it.

demand. The smaller of usable capacity and opening backlog.

displacement. Losing a whole eligible interval to an earlier ranked
pass on the same aperture.

eligible set. The clipped, availability intersected, period split
interval set of a canonical row.

KiB. 1024 bytes. All volumes are integer KiB.

late cancellation. A binding cancellation effective at or after the
commit boundary. The pass stays admitted.

milli credit. One thousandth of a credit. All settlement money is
integer milli credits, written mcr.

milli KiB per second. The rate unit. Divide by rate_scale_divisor after
multiplying by seconds, flooring each rate piece separately.

MiB. 1024 KiB. Credit rates are quoted per MiB and the conversion
divides by credit_basis_kib_per_mib.

pass. One scheduled contact between one mission and one aperture. Also
the name of one round of the ration; the context distinguishes them.

pinned. A ration row that has reached its demand and takes no further
part in the share arithmetic.

protection. See commit evidence. The first key of the S07 ordering.

ration. The damped integer division of an over subscribed aperture
period budget across the passes that want it.

residual. Budget less the sum of the allocations after the last ration
pass. Distributed, or reclaimed when negative.

settled terms. The highest executed revision of a contract period
amendment.

share. Room divided by active row count, floored, inside one ration
pass.

theta. The damping fraction, applied to the movement from the current
allocation toward the target.

trim. Not a term of this settlement. Rows are pinned, never trimmed.

usable capacity. Raw capacity capped at the per contact cap.
