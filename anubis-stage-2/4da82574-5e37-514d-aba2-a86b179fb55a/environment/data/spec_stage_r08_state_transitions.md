# Stage r08: Ordinary state transitions

A `grant` adds the normalised quantity to the station balance and to the
station programme allotment, adds one to `grants` and adds the quantity
to `granted_cu`.

A `retire` subtracts the normalised quantity from the station balance
and from the station programme allotment, adds one to `retires` and adds
the quantity to `retired_cu`.

A `transfer` subtracts the normalised quantity from the station balance
and the station programme allotment and adds it to the counterparty
balance and the counterparty allotment under the same programme, adds
one to `transfers` and adds the quantity to `transferred_cu`.

Every applied event appends its identifier to the applied ledger and one
row to the transition log. The transition log row carries the one based
application order, the identifier, the canonical position, the kind, the
station, the programme, the quantity in credit units and the station
balance after the event settled.

Applied transitions and applied compensations draw their application
order from one counter, which starts at one in each replay. The
transition log therefore skips the orders applied compensations took.
