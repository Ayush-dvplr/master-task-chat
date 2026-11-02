# Programme revisions

The programme registry lists one row per revision of a programme. Each row carries
the programme identifier, the revision number, the first day on which the revision
takes effect, the first day on which it stops taking effect, and the process family
the revision belongs to.

- A revision governs a submission day when the day sits at or after the first day
  of effect and strictly before the day the revision stops taking effect.
- A programme may carry days that no revision governs. Work whose submission day
  falls in such a gap is rejected and settles nowhere.
- The process family of a work order is the family of the revision that governs it,
  which may differ between two orders naming the same programme.
