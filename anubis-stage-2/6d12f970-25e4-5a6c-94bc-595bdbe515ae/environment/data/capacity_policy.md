# Site capacity and admission

Each site publishes a slot capacity. Admission of work to a site is governed by the
congestion the site is under, and the congestion a site is under is governed by the
work admitted to it. Exactly one congestion assignment over the four sites is
stable under the rules below, and the settled schedule is the one that assignment
produces.

- The congestion index of a site is one thousand multiplied by the billable slots
  admitted at that site, divided by the slot capacity of the site, taken as whole
  units with the remainder discarded.
- congestion_bounds: 400, 700, 900
- A congestion index below the first bound places the site in tier zero, below the
  second bound in tier one, below the third bound in tier two, and otherwise in
  tier three.
- A pass is one offering of the whole admission order at the tiers standing when
  that offering begins. The first pass is offered with every site at tier zero.
  The settlement is complete on the first pass that leaves every tier where it
  found it, and that confirming pass is counted along with the passes that moved
  a tier.
- base_ceiling: commercial=320, public=260
- tier_factor: 0=100, 1=118, 2=134, 3=152
- The admission ceiling of a client is the base ceiling of its service class
  multiplied by the tier factor of the tier its home site sits in, divided by one
  hundred, taken as whole units with the remainder discarded.
- Work is offered for admission in descending order of dispatch weight, and orders
  carrying equal weight are offered in ascending order of their identifier.
- An order whose billable slots would carry the running admitted total of its
  governing client past that client admission ceiling is held back. A held order is
  deferred, keeps its place in no lane, and settles no value.
- The billable slots of an order are its load units brought to a whole multiple of
  the granularity the record declares. The authority withholds which of the four
  quantisation modes it applies: discard the remainder, advance to the next
  multiple, take the closer multiple with the midpoint advancing, or discard the
  remainder unless the remainder reaches three quarters of the granularity.
