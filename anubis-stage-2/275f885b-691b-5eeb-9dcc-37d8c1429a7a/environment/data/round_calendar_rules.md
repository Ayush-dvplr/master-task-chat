# Round calendar rules

## Recurrence

Rounds are coded `R01` upward and number as many as `campaign.rounds` declares. `R01` starts on
the date declared as `campaign.anchor.date` and each later round starts fourteen days after the
round before it.

## Notices

`calendar_exceptions.csv` carries notices against round codes. Only a notice whose `region`
field reads `ALL` can change a round. For each round the notice with the latest `issued_at`
decides, with `notice_ref` breaking a tie. A notice with action `confirm` leaves the recurrence
start in place. A notice with action `move` starts the round on `new_start_date`. A notice with
action `skip` removes the round from the live sequence and leaves the recurrence start in place
for the purposes of the claim window.

Rounds that survive are the live rounds, ordered by start date with the round code breaking a
tie. Calendar order means that order.

## Settlement round

A requisition that names a live round settles in that round. A requisition that names a skipped
round settles in the first live round whose start date is later, and its claim window stays the
window of the round it names.

A claim settled in a round draws on records naming that round and on records naming any skipped
round that settles in it. Handling ceilings, priority tiers, campaign phases and dose factors
are read for the round of settlement.
