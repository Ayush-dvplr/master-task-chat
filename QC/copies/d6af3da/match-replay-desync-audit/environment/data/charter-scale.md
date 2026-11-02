# Charter scale notes

These notes fix the arithmetic conventions the settlement uses. They describe
quantities and conventions only. They carry no figure taken from any capture.

## Published word tables

The twenty four unit words, in the order the engine publishes them, are
`aurochs`, `basilisk`, `cockatrice`, `dryad`, `ettin`, `fenrir`, `golem`,
`hydra`, `ifrit`, `jotun`, `kelpie`, `lamia`, `manticore`, `nixie`, `ogre`,
`pegasus`, `quasit`, `roc`, `sylph`, `troll`, `undine`, `vodyanoi`, `wyvern`,
`xorn`.

The twelve label words, in the order the engine publishes them, are `aegis`,
`banner`, `cinder`, `dagger`, `ember`, `falcon`, `gale`, `harrow`, `ingot`,
`javelin`, `kestrel`, `lantern`. A label is named by its position in this list,
counted from zero.

The five charters are `azure`, `crimson`, `gilded`, `sable` and `verdant`.

The four cadence classes, in index order, are `peak`, `steady`, `burst` and
`latency`.

Every keyed mask this engine stamps is a SHA two five six digest over the engine
key `MRD-2031`, then the label of the mask, then each number the mask covers
written in decimal and each preceded by a colon. A mask takes the first twelve
bytes of that digest. Beside the twelve label words the mask labels the engine
uses are `entry`, `seal`, `check`, `chain`, `drift` and `filler`.

A published control figure is stamped a different way. It is the first twelve
characters of the hexadecimal SHA two five six digest over the engine key
`MRD-2031` followed by every fragment the control reads, where each fragment is
preceded by a vertical bar and written in its UTF-8 form.

## Exact arithmetic

Every monetary quantity in this engine is a rational number. Stocks, amounts,
upkeep targets and residuals are held exactly. A quantity is rendered as the
numerator, a solidus, and the denominator, in lowest terms, with the
denominator written even when it is one. A negative quantity carries the sign
on the numerator. Binary floating point is not a faithful carrier for these
quantities and a run that routes them through it will disagree with the engine
on the low digits.

## Charter baselines

The roster register names the charter every unit was opened under. The baseline
of a charter is the sum over the units the register opens under that charter of
the unit's opening tick, taken as an exact integer. The baseline is a property
of the register alone. It does not read any capture, it does not change when a
unit retires, and it does not change when a unit is carried to a successor.

## Transfer between charters

Two charters are linked when a settled entry of kind one is recorded by a unit
whose canonical charter differs from the charter the register opened that unit
under. The share the opening charter gives to the canonical charter is the
settled kind one amount recorded across that pair, divided by the sum of every
charter baseline. The engine builds one share per ordered pair of distinct
charters and no share from a charter to itself.

The stock of a charter is its baseline plus the sum over the other charters of
that other charter's stock multiplied by the share it gives away. Every charter
gives away strictly less than the whole in total, so the assignment of stocks
that satisfies every one of these relations at once exists and is unique. It is
an assignment to be solved for, not a sequence to be walked.

## Caps

A charter cap is the charter baseline multiplied by the number of units the
register opens under that charter. Each charter holds an allowance the size of
its cap. The settled entries that serve a charter draw on its allowance one at
a time, in the walk order the reversal rules use. An entry draws its whole
amount while the allowance left covers it, and otherwise draws what is left,
which can be nothing. What an entry draws is its settled amount. The part it
cannot draw is surplus and the surplus is carried into the reconciliation
residual rather than into any stock. An entry that draws nothing still
settles. Reversal matching is complete before any entry draws, so a cancelled
entry never draws.

## Cadence scale

The cadence modulus is one of the withheld quantities. The candidate values it
may take are published with the control figures. Dividing a settled tick total
by the cadence modulus uses integer division that discards the remainder.

## Upkeep scale

The upkeep target scale is one of the withheld quantities. The candidate values
it may take are published with the control figures. The upkeep target is the
scale multiplied by the sum of every charter baseline. It is an exact integer.

## Bench candidates

The bench candidate list names units by word and gives each a whole upkeep
figure. Exactly one subset of the candidate list has upkeep summing to the
upkeep target exactly. The empty subset is a subset and is eligible when the
target is zero. Two subsets with the same sum would leave the answer ambiguous,
and the list is drawn so that this does not happen. A bench entry is reported by
the candidate word, and the bench is reported with its words in ascending order.

## Counting conventions

A settling pass over the identity register is one complete sweep that reads every
roster row once and rewrites every canonical charter that the sweep finds stale.
The sweep that finds nothing stale is the pass that proves stability and it counts
as a pass.

A candidate is one value from the published set for one withheld quantity. The
falsifier for a rejected candidate is the name of the control figure that the
candidate failed to reproduce, and a candidate is rejected against the first
control figure in published order that separates it.
