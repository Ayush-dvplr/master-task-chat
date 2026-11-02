# Worked examples

These are worked against invented figures. They show the shape of each rule,
not the values of this round.

## An amount in three forms

`4800`, `4,800 mills` and `4.800 GBP` are one amount of four thousand eight
hundred mills. `4 GBP` is four thousand mills. `12.5` is refused: an amount in
mills carries no fraction.

## A crew quantity

A job in a precinct whose shift length is 450 minutes, carrying a crew
quantity of 3 in the unit `shift`, draws 1350 crew minutes. The same job
carrying a crew quantity of 1350 in the unit `minute` draws the same 1350.

## A scaled charge

A base charge of 41 250 mills at a class multiplier of 10 400 basis points is
41 250 times 10 400 over 10 000, which is 42 900 exactly, so the scaled charge
is 42 900 mills. A base charge of 41 251 at the same multiplier is
42 901.04 exactly, which rounds to 42 901.

## A closure and what it draws

Take D requiring C, C requiring B, and B requiring A. The closure of D is A, B
and C. Selecting D alone opens the closed set A, B, C, D. If A draws 4 quarter
days and the other three draw 3 each, the usage is 13 quarter days, not the
4 plus 13 that adding the closed vectors of two of them would give.

## The order of the three charge stages

Take a precinct whose closed set carries scaled charges of 60 000 mills, a
pair surcharge of 5 000 mills, and a closure rebate of 900 basis points on a
job whose closure holds two jobs. The rebate is taken of 65 000, which is
5 850, so the charge is 60 000 plus 5 000 less 5 850, or 59 150. Taking the
rebate of 60 000 instead would give 5 400 and a charge of 59 600, which is the
reading not in force.

## The capacity test on its boundary

A pool of capacity 900 with 120 carried has 780 available. A selection using
780 is within the pool. A selection using 781 is not.

## Ranking two accepted sets

Two sets both come to 118 400 mills. The first uses 20 quarter days, 6 lifts
and 2 400 crew minutes; the second uses 18 quarter days, 8 lifts and 2 400.
At pool weights of 25, 7 and one sixtieth, the first weighs
500 plus 42 plus 40, which is 582; the second weighs 450 plus 56 plus 40,
which is 546. The second is the accepted set. Under a flat weighting they
would weigh 2 426 and 2 426 and the tie would fall through to the count of
optional jobs, which is a different answer.

## A cascade that stops

A restatement moves the text of a rule amount from `4,800 mills` to
`4.800 GBP`. The rule cell is seeded and derived again. Its normalised value
is the same four thousand eight hundred mills, so its digest has not moved,
the cell is revalidated, and the solve of that precinct is never visited. The
work ledger for that amendment shows one cell visited, one revalidated, one
recomputed if the store did not hold the key, and no subsets examined at all.

## A cascade that does not stop

A lodgement adds a prerequisite at the bottom of a chain of six jobs. The
closure of the job it names moves, so the closure of the job that names that
one is visited, and so on up the chain. Each of those closures moves the
demand of its own job, and the demand of every job whose closure now holds the
new prerequisite. The solve of that precinct is visited once, at the end.

## A legacy identifier

The crosswalk carries `LEG-0042` to `JOB-4242` and `LEG-0051` to `JOB-5151`,
both with the status `active`, and `LEG-0043` to `JOB-4343` with the status
`withdrawn`. An active hard precedence row naming `LEG-0042` as the requiring
job and `LEG-0051` as the required job reads as `JOB-4242` requiring
`JOB-5151`. An active hard precedence row naming `LEG-0043` as the requiring
job maps through nothing, names no job in force, and is rejected under
`EDG-UNKNOWNJOB`.

## A reversal

An amendment takes a pool capacity from 900 to 899. A later amendment names
it and reverses it, so the capacity goes back to 900. The solve of that
precinct is seeded and its key is the key it stood at before the first
amendment. The store is holding that key among its superseded entries, so the
value comes back as a hit, nothing is recomputed, and no subsets are examined.
