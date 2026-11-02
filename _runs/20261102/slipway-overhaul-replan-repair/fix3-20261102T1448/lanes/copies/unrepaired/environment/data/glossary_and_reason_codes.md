# Glossary and reason codes

**Precinct**  one part of the yard, with its own pools, its own
slot groups, its own charge rules and its own jobs. Nothing
crosses a precinct.

**Job**  one berth job the desk may accept or defer.

**Standing**  `charter` for a job the yard owes, which carries a
deferral penalty when it is left out, or `optional` for a job
that carries none.

**Closure**  every job standing behind a job through accepted
prerequisites, at any depth.

**Closed set**  a selection together with the closure of every
job in it, each distinct job counted once.

**Cell**  one derived value with a key over the inputs it reads.

**Seed set**  the cells an amendment reaches first.

**Cascade**  the walk from the seed set through the cells that
read them, stopping wherever a value comes back unchanged.

**Working store**  what lets a configuration the round has
already stood in be read back rather than derived again.

## Reason codes

| code | stage | what it says |
| --- | --- | --- |
| JOB-DRAFTONLY | p01 | the register in force holds no sealed row for this job at or below the round index |
| JOB-WITHDRAWN | p01 | the row in force carries the state withdrawn |
| JOB-NOPRECINCT | p01 | the precinct named is not in the live topology |
| JOB-CYCLE | p02 | the job stands among its own prerequisites |
| JOB-LICENCE | p04 | the licence is not valid for this round |
| JOB-OUTOFROUND | p04 | the round index lies outside the window of the job |
| JOB-CLOSUREBLOCKED | p05 | something in the closure is inadmissible or set aside |
| EDG-WITHDRAWN | p02 | the lodgement is not active |
| EDG-ADVISORY | p02 | the lodgement is advisory and creates no prerequisite |
| EDG-SELF | p02 | both ends are one job |
| EDG-UNKNOWNJOB | p02 | an end is not a job in force |
| EDG-CROSSPRECINCT | p02 | the ends stand in different precincts |
| EDG-DUPLICATE | p02 | the pair is already carried by a lower lodgement |
| EDG-CYCLE | p02 | the lodgement would close a precedence cycle |
| GRP-DOUBLEBOOKED | p08 | the job already stands in a group of earlier precedence |
| GRP-SINGLE | p08 | a group of one open member binds nothing |
| AMD-NOTARGET | p13 | the reversal names no amendment this round applied |
| CMT-UNKNOWN | p13 | the commitment named is not binding this round |
