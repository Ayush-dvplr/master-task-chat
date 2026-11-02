# Temporal rules

Sections of this document are amended by `errata_2031-07.md`.

## 1. Clock marks

`site_clock_marks.csv` carries one or more marks for each site and local date.
For a site local wall stamp, the offset in force is the one on the greatest
mark of that local date whose `from_local_time` is at or before the stamp.
`mark_kind` is `standing`, `clocks_forward` or `clocks_back`.

After a `clocks_back` mark the wall clock repeats a window whose length is the
difference between the two offsets. A stamp inside that window is ambiguous.
The `fold` field of the record selects which pass it belongs to: 0 selects the
offset in force before the mark and 1 selects the offset after it. A record
with no fold field is read as 0.

After a `clocks_forward` mark the wall clock omits a window of the same
length. A stamp inside that window did not occur. Move it forward by the
length of the window and read it with the offset after the mark.

Instants stated in UTC need no mark. A field whose name ends in `_local` is
site local, and for an entitlement ceiling the site is the one in
`declaring_site`.

## 2. Cycles and horizon

The horizon holds twenty four allocation cycles, `C01` to `C24`, inside the
calendar year 2031. Each cycle starts at 06:00:00 site local. Odd numbered
cycles start on the first day of their month and even numbered cycles start on
the sixteenth, so `C01` starts on 1 January and `C24` starts on 16 December.
The horizon closes at 06:00:00 site local on 1 January 2032. Cycle intervals
are half open: a cycle holds every instant at or after its own start and
before the start of the next cycle. A request whose governing effective
instant lies outside the horizon is out of scope and carries the reason
`OUT_OF_HORIZON`. Because each site keeps its own clock, the same UTC instant
can fall in different cycles at different sites.

## 3. The as of instant

`derivation_policy.ini` declares the as of instant. A record whose recorded
instant is after that moment had not reached the system when the view was
taken, so it is not admitted. This holds for every file: request rows, state
events, amendment notices, retractions, ceilings, agreements, priority rows,
exceptions, capacity declarations, substitution rows, alias rows, authority
grants and master rows alike. Admission is decided only by the recorded
instant and never by the effective instant. Rows that are not admitted are
tallied by source in `data_quality.late_recorded`.

A request all of whose rows are late has no ledger row at all.
