STAGE Y12  Cutoff joined to yard state
shift KP-2042-S23

This stage joins the yard state this shift produced to the cutoff
notices, which come from a different source. A box can be
standing in the yard and still be ineligible, and the two facts
are settled by different papers.

RULE Y12.1  The cutoff in force.
Among the notices of cutoff_notice_board.tsv that name this shift
and are not superseded, the one with the highest notice_seq is in
force for its vessel. A vessel with no such notice has no cutoff
in force.

RULE Y12.2  The ready minute.
The ready minute of a box is the raised minute of the last
admitted order that moved it. A box no order moved has a ready
minute of zero.

RULE Y12.3  The cutoff boundary.
A box whose ready minute is less than or equal to the cutoff
minute is inside the cutoff. Strictly greater is outside it. A
ready minute exactly equal to the cutoff minute is inside.

RULE Y12.4  The order the reasons are put in.
A box is settled by the first of these that holds, and the
published reason is that one: its vessel has no applicable call,
EL_NO_VESSEL; its vessel carries no stowage obligation for it,
EL_NO_OBLIGATION; that obligation holds it, EL_HELD; it has no
closing yard position, EL_OFF_YARD; its vessel has no cutoff in
force, EL_NO_CUTOFF; it is outside the cutoff, EL_AFTER_CUTOFF.
A box none of these catches is eligible and carries EL_OK.

RULE Y12.5  The cutoff waiver.
A cutoff_waiver naming the last admitted order of a box lifts the
cutoff test for that box alone. It lifts nothing else.

RULE Y12.6  Every box is published.
Every box with an applicable master record is published with its
verdict, eligible or not, and a vessel with no eligible box at
all is still published in the cutoff status with counts of zero.

RULE Y12.7  What the cutoff status counts.
The boxes_outside figure of vessel_cutoff_status.csv is the count
of the vessel's boxes this stage settled at EL_AFTER_CUTOFF, and
boxes_inside is the rest of boxes_total. The two figures are read
off the published verdict and not off a fresh comparison of ready
minute against cutoff minute, so a box a cutoff waiver lifted the
test for counts as inside, and so does a box an earlier reason
settled before the cutoff was ever reached.

PUBLISHES  load_eligibility.csv, vessel_cutoff_status.csv,
vessel_container_manifest.psv
