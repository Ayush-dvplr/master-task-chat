# Known traps and footguns

The desk has kept this list across several rounds.

A register holds rows sealed for a later round. They are not amendments and
this round does not read them.

A register holds withdrawn rows. A withdrawn row that is the row in force sets
the job aside; a withdrawn row behind a later sealed row does nothing.

The capacity history holds rescinded rows with a later effective round. They
look like the newest word on the pool and they settle nothing.

The charge rule file holds lapsed rules from earlier schedules. Only a rule in
force is read.

The amendment journal holds withdrawn rows from this round and rows raised
against earlier rounds. Only a lodged row is an amendment.

Two amendments may carry the same payload. The second one still has to be
classified, seeded and cascaded; what it costs is a matter for the store, not
for the classification.

An amendment may be the exact inverse of an earlier one. It is applied like
any other amendment and the store is what makes it cheap.

A slot group may be left with one member, or with none. Such a group binds
nothing, and a round that treats a group of one as a constraint will refuse
sets it should have accepted.

A precinct may carry a rule that never fires in this round. It is still a rule
and it still stands in the key of that precinct's solve.

The closure rebate needs the job it hangs on to hold two or more jobs in its
closure, counted at any depth. A rebate on a job whose closure holds one job
is not taken, however many prerequisites that job names directly.

The amount grammar accepts three forms of one figure. Two amounts that reach
the same whole mills are the same amount, and a restatement from one form to
another moves nothing behind the rule.

The edge journal may hold the same pair twice. One prerequisite, and
withdrawing either row while the other stands leaves the prerequisite in
place.
