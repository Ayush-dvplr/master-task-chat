# Dependency rules

prereq_edges.tsv names a pledge and a pledge it depends on. Edges carry a window
identifier for filing convenience only; an edge is read whenever its dependent
pledge is on the docket. A prerequisite can sit outside the docket window, in
which case the prerequisite still carries its own evidence and its own state.

A pledge is settled by discharge when a governing discharge record exists for it.
A pledge is settled by waiver when a governing waiver grant exists for it. A
pledge with neither is unsettled.

A waiver carries the instant of the grant. A waiver that was granted after the
governing due instant still settles the pledge. A waiver overrides discharge
evidence only when the waiver instant falls before the evidence instant of that
pledge.

A pledge whose holder carries a dissolved status, with a dissolution local date
at or before the local date of the governing due instant, is lapsed. A dormant
holder is active for settlement.

The effective instant of a pledge depends on its own evidence and on what its
prerequisites contribute. readiness_examples.csv records closed outcomes for
stated own evidence and stated prerequisite contributions, including the tokens
that stand for an unsettled prerequisite and for a lapsed prerequisite. Those
outcomes settle how contributions combine, which outcome state follows, and which
reason codes attach.

Two pledges can name each other, directly or through a chain. cycle_findings.csv
records how closed windows resolved such groups.
