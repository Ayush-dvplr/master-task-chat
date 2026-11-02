# Dependency admission

## Where requirements come from

`unit_revision_requires.csv` is the primary requirement table. A row binds when
its `scope` is one of the scopes in force, which are listed in
`relay_policy_baseline.json`. A row whose scope is outside that list is kept for
reference and binds nothing.

`dependency_declarations_legacy.tsv` supplies requirements only for a unit and
revision pair that the primary table does not mention at all. The presence of any
primary row for the pair, binding or not, keeps the legacy table out.

Requirements are matched on the exact unit key and revision of the request. A row
written against another revision of the same unit binds nothing.

## When a requirement is met

A requirement names a unit and a minimum revision. It is met when the target
channel of the requesting unit seats that unit at a revision that is not lower
than the minimum. Seating counts what the channel already holds and every other
request in this cycle that targets that same channel and has not already failed an
earlier condition. A request targeting a different channel does not meet it.

Requirements among the requests of one cycle form a chain whenever one request
holds a requirement that another request in the same channel would meet. Where a
chain closes on itself, so that following the chain returns to where it started,
no member of that closed chain is met and every member of it carries the cycle
reason code. A closed chain of two members is the common case; a closed chain of
three or four members is read the same way.

## Admission order

Admitted requests are ordered so that a request appears after every request this
cycle that meets one of its requirements. Where several requests are ready at the
same point, the one with the lower tier rank goes first. Where the rank ties, the
request that meets the greater number of requirements held by other admitted
requests in its own channel goes first, counting each other request once for each
of its requirement rows this request would meet. Where that count ties as well,
the lower unit key goes first.

## Closure

Capacity is settled before closure. Once capacity has been settled, each request
still holding capacity is tested again against the requirements rule, now counting
only the requests that hold capacity. A request whose requirement is no longer met
loses its place and carries the missing requirement code. The place it loses is not
offered to anyone else.

Losing a place can leave another holder short, so the test is repeated until a
pass evicts nobody. The bound below is the greatest number of passes the board
will fund; reaching the bound with evictions still happening is a filing fault and
has never happened in a closed cycle.

## Normative parameters

```
closure_passes: until_stable
closure_pass_bound: 4
ready_tiebreak: tier_rank,met_for_others_desc,unit_key
```
