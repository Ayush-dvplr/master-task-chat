# Stage p10  what one accepted set costs and how two are ranked

Only a charge rule of `conditional_charge_rules.jsonl` whose state is
`in_force` is read; a rule in any other state adds nothing.

The charge of an accepted set is built in this order and no other.

The class multiplier reaches the base charge of each job first, at stage p07.
The scaled charges of the closed set are added. The surcharges of the precinct
are added next: a pair surcharge is added once when both of the jobs it names
stand in the closed set, and a threshold surcharge is added once for each job
of the class it names that stands in the closed set, but only while the usage
of the pool it names is above its threshold. The closure rebate is taken last:
where the job it hangs on stands in the closed set and that job holds two or
more jobs in its closure, the rebate in basis points is taken of the scaled
charges and the surcharges together, rounded once, half away from zero. The
precedence directive carries the order these three stages apply in.

The deferral penalties are added last of all. A job carries its penalty when
it is selectable, its standing is `charter`, and it is left out of the closed
set. A job that is inadmissible, blocked or set aside carries none, and an
optional job carries none whatever happens to it.

Two accepted sets are ranked on four keys in this order: the charge in mills,
then the weighted resource, then the count of optional jobs standing in the
closed set, then the closed set itself in canonical job order. The weighted
resource of a set is the sum over the three pools of the usage of that pool
multiplied by the weight of that pool, held as an exact rational and published
to twelve decimal places. The pool weights stand in the parameter workbook and
nowhere else. Two sets equal on all four keys are one set.
