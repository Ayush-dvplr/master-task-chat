STAGE Y03  Vessel obligation state
shift KP-2042-S23

This stage settles which call each vessel is making.

RULE Y03.1  The applicable call revision.
In vessel_call_register.csv set aside rows of another shift and
rows marked withdrawn. The applicable revision of a vessel is the
surviving row with the highest revision_seq. A withdrawn revision
never becomes applicable, not even when it is the only revision a
vessel has; such a vessel has no applicable call and is absent
from the published obligation.

RULE Y03.2  What the call settles.
The applicable revision settles the vessel's berth, its service
group and its destination. Every later stage reads those three
from here and from nowhere else. A box takes its service group
and its destination from its vessel, not from its own papers.

RULE Y03.3  A box whose vessel has no applicable call.
Such a box carries the not supplied marker for service group and
destination, and the eligibility stage settles what happens to
it.

PUBLISHES  vessel_obligation.csv
