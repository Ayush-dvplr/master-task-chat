# Stage r12: State dependent eligibility

An event may carry a `requires` predicate, read against the state as it
stands immediately before the event is offered. A compensating event is
never deferred: a `requires` field it carries is not read.

`eligibility_predicates.csv` carries the predicate forms, one row per
form and revision, and the row in force for a form is the one with the
greatest revision at or below the frozen register revision. A predicate
writes its form and then its arguments, separated by colons, in the
order the form in force lists them. A form the register in force does
not carry as active, and a predicate whose argument count disagrees with
its form, is false whenever it is read. Arguments are read as written;
the crosswalk is not applied to them.

`balance_at_least` holds when the balance of `station` stands at or
above `amount_cu`. `allotment_below` holds when the allotment `station`
holds under `programme` stands strictly below `amount_cu`.
`counter_at_least` holds when the derived counter `counter` stands at or
above `amount`. `no_pending` holds when the pending queue is empty.
`station_active` holds when the frozen register carries `station` as
active.

An event whose predicate is false is not discarded and is not
quarantined. Its identifier joins the end of the pending queue and the
pass moves on. A compensating event later in the same window can change
the state its predicate reads, which is why eligibility cannot be
settled once before the pass.

When the window is exhausted the re offer rounds begin. Each round
offers the pending identifiers in the order the ladder in
`precedence_directive.docx` gives, each against the state as it then
stands, and applies the ones whose predicate holds, removing them from
the queue and adding one to `deferred_admitted` for each. The queue
itself keeps the order in which identifiers joined it: the ladder orders
a round's offers, never the queue, and an identifier that leaves the
queue leaves the others in place. Admitting an event inside a round changes
the state the rest of that round reads, but an identifier already
offered this round waits for the next one. The region an event takes on
the ladder is the region the frozen register carries for its station,
ranked by the reporting roster.

A round that admits nothing ends the run and the run has settled. A run
that reaches the round ceiling in the memo while the last round was
still admitting stops there and has not settled. Only rounds that
admitted at least one identifier are published.
