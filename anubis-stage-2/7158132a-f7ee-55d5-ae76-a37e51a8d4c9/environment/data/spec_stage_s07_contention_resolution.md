# S07 contention resolution

Contention is settled per aperture per settlement period, over the
canonical rows that survived S03.

## the ordering

Order the rows of an aperture period by, in this order:

  1. protection, protected before unprotected
  2. effective_rank ascending
  3. commit_boundary_s ascending
  4. remaining contractual obligation descending
  5. contact_id ascending

The fifth key is total, so the order is total and no two runs disagree.

remaining contractual obligation is the obligation_kib of the settled
terms of the period, taken over the contracts of the pass from S03, and
where the pass has more than one such contract it is the largest of
them. It is read at the opening of the period and is not reduced as
passes settle. This is the one edge that runs backwards, from S08 into
S07, and ordering_dependencies.yaml names it.

## the greedy walk

Walk the ordered rows once. Keep a list of the rows already accepted for
this aperture period, initially empty. For each row in turn:

  if its eligible set intersects the eligible set of any accepted row by
  one second or more, the row is displaced, and the first accepted row
  it intersects in acceptance order is recorded as its displaced_by;

  otherwise the row is accepted and joins the list.

A displaced row keeps none of its interval. Displacement is whole, not
partial. Its allocated and accepted volumes are zero and it appears in
no delivery ledger.

Two rows that abut, where one ends exactly where the other begins, do
not intersect and both are accepted. A zero length row intersects
nothing and is always accepted.

## contention groups

contention_groups is a report, not a decision. The groups are the
connected components of the intersection graph over the rows of the
aperture period, so a row that intersects nothing forms a group of one
and is still listed. Components are ordered by their smallest
contact_id. group_seq counts from one inside each aperture period.

The greedy walk is over the whole aperture period in the published
order, not over one component at a time. A row can be displaced by a row
in its component and by no other.

## the tie report

tie_resolution_report carries one row for each pair of intersecting rows
in one aperture period, naming which key decided between them:

  1 protection, 2 effective_rank, 3 commit_boundary_s,
  4 remaining obligation, 5 contact_id

contact_id_kept is the row that came first in the published order and
contact_id_yielded the one that came second, whichever of them the
greedy walk went on to accept. Pairs that do not intersect are not
reported.
