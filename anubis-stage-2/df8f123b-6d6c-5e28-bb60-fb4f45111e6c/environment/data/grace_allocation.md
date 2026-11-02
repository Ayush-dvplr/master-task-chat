# Grace allocation

The desk holds a grace pool for the window. The pool size in minutes comes from
the governing directive revision. A grace round runs once, after every pledge has
a state and a lateness figure, and only when the governing mode is tempered.

A pledge enters the round when its state is breached, it carries an effective
instant, and the class facts in force for it carry a grace eligible flag of yes.
A pledge that reached the cutoff with no effective instant is a matter of non
delivery rather than late delivery and stays outside the round. Class facts come
from pledge_class_catalog.csv and the row that applies is the row whose effective
period contains the governing due instant of that pledge.

Each pledge in the round has a raw share of the pool in proportion to the ceiling
minutes its class facts carry, measured against the total of those ceiling minutes
across the round. A raw share is then limited by the smaller of the lateness of
that pledge and the ceiling minutes its class facts carry. Capacity that a limit
holds back returns to the desk and is not offered to another pledge.

Granted minutes are whole minutes. grace_precedent_rounds.csv records closed
rounds with the lateness, the ceiling, the pool, the granted minutes for each
pledge and the round totals, which settle how shares become whole minutes and
which pledge takes an odd minute.

A pledge whose granted minutes reach its lateness is tempered clear. A pledge
with granted minutes below its lateness stays breached and carries the remainder
as residual minutes. A pledge outside the round keeps zero granted minutes.
