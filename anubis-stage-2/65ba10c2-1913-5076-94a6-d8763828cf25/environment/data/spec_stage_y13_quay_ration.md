STAGE Y13  The quay ration and the load
shift KP-2042-S23

This stage rations the quay and settles what each vessel loads.
The ration is the one derivation of this shift that is not a
lookup: it is a damped iterate run a fixed number of times, and
the number of times is part of the answer.

RULE Y13.1  The pairings.
The ration is run once for each pairing of a slot with a
reporting berth, slots ascending and berths ascending inside a
slot. The vessels of a pairing are those whose applicable berth
is that berth and which carry an applicable demand return for
that slot, in ascending vessel_id.

RULE Y13.2  The applicable demand return.
In quay_demand_returns.csv a return counts only when its
return_state is filed. Among the filed returns of one vessel and
slot the one with the highest revision_seq is applicable. A
vessel with no filed return for a slot is not in that pairing at
all.

RULE Y13.3  The pool.
The applicable berth window is the row of berth_window_register
.csv with the highest revision_seq that is not marked draft. The
pool a pairing rations is the smaller of the crane minutes that
window declares and the sum of the gang minutes the quay gang
roster of berth_operations_memo.pdf crews for that berth and
slot. The roster is carried in no other paper.

RULE Y13.4  The ceiling.
The admissible minutes of a vessel in a slot are issued by the
vessel slot ceiling register of the live workbook sheet. A
pairing member the register does not carry has a ceiling of zero.

RULE Y13.5  The iterate.
Every share starts at zero. The ration runs exactly the number of
passes the pass budget of berth_operations_memo.pdf allows, and
each pass does the following in this order.

  a  The need of a vessel is its applicable declared minutes less
     its standing share, and never below zero. The unallocated
     pool is the pool less the sum of the standing shares. When
     the total need is zero, or the unallocated pool is zero or
     less, the ration stops early and the standing shares are the
     shares.

  b  The target of a vessel is its standing share plus the
     unallocated pool apportioned across the needs.

  c  The target is capped at the vessel's ceiling.

  d  What the caps freed is redistributed inside the cross
     classification of berth and service group. A vessel receives
     freed minutes only from vessels sharing both its berth and
     its service group, apportioned across the needs of the
     members of that cell whose target the cap did not bind.
     Freed minutes in a cell with no such member stay unassigned
     and are published as the unplaced minutes of that pass.
     Redistributing across the whole pairing rather than inside
     the cell is wrong and gives different shares.

  e  The aim of a vessel is its capped target plus what it
     received, capped at its ceiling again.

  f  The share moves from where it stands toward the aim by the
     damping fraction of the live workbook sheet.

  g  The result is rounded to whole crane minutes. This rounding
     happens at the end of every pass. The next pass begins from
     the rounded share, so the residues do not accumulate, and a
     ration that carries exact shares through every pass and
     rounds once at the end is a different ration and gives
     different numbers.

  h  A share that has not reached its rounded aim, and whose
     damped move rounded to no movement at all, moves instead by
     the minimum step of berth_operations_memo.pdf toward the
     aim, and never past it.

RULE Y13.6  The budget is a count, not a test.
The passes stop when the budget is spent. The ration is not run
to convergence, it is not iterated until the shares stop moving,
and it is not solved in closed form. The shares standing when the
budget is spent are the published shares whether or not they have
settled, and on this shift most of them have not.

RULE Y13.7  The share of a vessel.
The share of a vessel over the shift is the sum of its shares
across the pairings it belonged to.

RULE Y13.8  The load order.
The eligible boxes of a vessel are put in order by the keys
stowage_ordering_directive.docx names, read left to right, each
ascending. The class rank register of that directive is carried
in no other paper.

RULE Y13.9  What a box costs.
A box costs its teu factor multiplied by the base minutes of the
quay crane unit, which is the applicable unit of class quay_crane
with the lowest equipment_id.

RULE Y13.10  Where the load stops.
The boxes are taken in load order while the running total stays
within the vessel's share. The first box that would take the
total past the share is deferred, and so is every box after it.
The load is a sequence and not a selection: a later box that
would have fitted is deferred all the same.

RULE Y13.11  The republished charge.
A deferred box has its charge republished as the charge it was
assessed plus the surcharge of the last rung of the surcharge
ladder. A box that was never moved was assessed nothing and is
republished at the last rung alone.

PUBLISHES  ration_trace.jsonl, load_sequence_ledger.json,
departure_ledger.json, deferred_containers.tsv
