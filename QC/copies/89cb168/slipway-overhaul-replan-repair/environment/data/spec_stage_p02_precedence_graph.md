# Stage p02  the precedence graph and the indexes over it

`precedence_edge_journal.psv` holds lodgements, not prerequisites. A lodgement
becomes a prerequisite only after it has passed, in this order, every test
below. The first test a row fails is the reason it is rejected, and a rejected
row appears once in the rejection register with that reason.

`EDG-WITHDRAWN`  the row status is not `active`.
`EDG-ADVISORY`  the row kind is not `hard`. An advisory lodgement records an
  opinion and creates no prerequisite.
`EDG-SELF`  the two ends are one job after the crosswalk.
`EDG-UNKNOWNJOB`  either end is not a job in force.
`EDG-CROSSPRECINCT`  the two ends stand in different precincts. A prerequisite
  never crosses a precinct.
`EDG-DUPLICATE`  a row already accepted names the same pair after the
  crosswalk. Rows are taken in ascending edge identifier, so the row of the
  lowest identifier is the one that carries the prerequisite and every later
  row naming that pair is the duplicate.

A job that stands among its own prerequisites, at any depth, is set aside
under `JOB-CYCLE` together with every other job of that cycle, and the
lodgements that named it are then rejected under `EDG-UNKNOWNJOB` by the test
above.

Two indexes are derived here. The reverse index maps a job to the jobs that
name it directly as a prerequisite. The depth of a job is the longest chain of
prerequisites standing below it, counted in edges, and it is what puts a
prerequisite before the job that names it whenever a cascade reaches both.
