# Reservation settlement

Each pool of a traffic class settles the reservation units its members hold for the settlement window. The members of a pool are the tenants assigned to it once the correction layers of ct_svc.md are applied, retired tenants left out. A member starts with its contracted reservation, and the pool total is the sum of these starting holdings; no settlement round changes the pool total. The state of a pool is the list of its members' holdings read in member name order, names compared by code point, and one state is smaller than another when it holds less at the first member where the two differ.

Settlement proceeds in rounds numbered from zero. Every round opens on the holdings with which the round before it closed, and round zero opens on the starting holdings. The pool parameters named below (starting step, patience and budget) come from the pool table of the register.

A member's target in a round is its share of the pool total in proportion to demand in RU. Each member first receives the whole part of the pool total times its demand divided by the total demand of the pool, and the units this leaves unassigned go one each to the members with the largest remainders of that division. Among members whose remainders are equal, a unit goes first to the member of greater standing, and then to the earlier name. When no member of the pool has demand, the target of every member is its standing.

A member's residual in a round is its target minus its standing, and the residual total of the round is the sum of the residuals of all members taken without sign. A round whose residual total is zero settles the pool, which keeps its standing holdings.

The step of a pool is a whole number of quarters. It starts at the starting step, and it is the only setting that changes during settlement. Each round from round one on either improves or adds one to the patience count of the pool. The step is halved, rounding down and never below one quarter, in the round in which the patience count reaches the patience of the pool.

A member's raw movement in a round is its residual times the step, divided by four and rounded to the nearest whole unit. The raw movements of a pool need not sum to zero. The amount that brings their sum to zero is added in full to one member: the member furthest from its target, and among members equally far the earlier name. The movements after this correction are what the round yields.

A round that yields only zero movements stalls the pool, which keeps its standing holdings. Any other round adds the movements it yields to the holdings, and the round closes on the resulting state. A holding may fall below zero in this way, and it is kept as it is; a settled reservation below zero is a valid result.

A pool cycles when a round closes on a state the pool has already held, and this holds even for the last round the budget allows. A cycling pool reports as its holdings the smallest state of its cycle.

The budget of a pool is the most rounds it may close. A pool whose closed rounds reach its budget without settling, stalling or cycling stops with the holdings of the last closed round.

The settlement result of a pool is its exit (settled, stalled, cycled or budget), its round count, the step in force when it stopped, and the holding of every member. The settled reservation of a member is its holding in that result.
