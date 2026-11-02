# Identity register

Orders name the customer in their `customer_ref` field. A reference is usually the customer's
contract id from the contracts register, but dispatchers also use alias codes, and customer
identities change during the season. This document says how a reference resolves to a customer
at a given instant, which depot serves an order, and which orders never become lots. The layouts
of `identity_events.csv` and `service_areas.json` are in record_dictionary.md.

## Identity events

An identity event is in force for every instant at or after its `effective_at` instant, and for
no instant before it.

- `alias`: from its effective instant, `code` is another name for the customer `target`. Before
  that instant the alias code names nobody. Alias codes never coincide with contract ids.
- `merge`: the customer `code` is merged into the customer `target`. From the effective instant
  on, any reference that would name `code` names `target` instead. Merges chain: if the target has
  itself been merged into a third customer by the same instant, the reference follows on to that
  customer, and so on.
- `retire`: the customer `code` is retired from its effective instant.
- `reactivate`: the retired customer `code` is active again from its effective instant.

A customer is retired at an instant when the latest of its `retire` and `reactivate` events in
force at that instant is a `retire`; otherwise it is active. Events with the same effective
instant are taken in order of `event_id`.

## Resolving a reference

A reference is read
after removing any spaces before and after it and turning its letters into capitals; only then is
it compared with contract ids and alias codes. Reports that show a reference "as keyed" show it
exactly as it stands in the record, spaces and letter case included.

At a given instant, a reference resolves as follows. A contract id names its own customer. An
alias code names its target if the alias is in force at that instant, and names nobody otherwise.
The customer reached that way is then redirected through every merge in force at that instant, as
described above. The customer at the end of that chain is the customer the reference resolves to.

## Service areas

The service-area assignment in force for a customer at an instant is its entry with the latest
`effective_from` at or before that instant. A customer can move between depots, and between
regions, during the season. A customer with no entry at or before an instant is served by no
depot at that instant.

An order's depot is the depot whose assignment is in force, at the order's placement instant, for
the customer the order's reference resolves to at that same instant.

## Orders that never become lots

An order that is void or cancelled (source_authority.md) is set aside before anything else and is
not an orphan. Every other order either becomes a lot (lot_ledger.md) or is an orphan, with
exactly one of these reasons:

- `out_of_season`: its placement instant lies outside the season window.
- `unknown_reference`: its placement instant lies inside the season, and its reference names no
  customer at that instant.
- `retired_reference`: its placement instant lies inside the season, and its reference resolves to
  a customer that is retired at that instant.
- `unserved`: its placement instant lies inside the season, and its reference resolves to an
  active customer that has no service-area assignment in force at that instant.
- `unknown_class`: its placement instant lies inside the season, its reference resolves to an
  active customer with a service-area assignment in force at that instant, and its `order_class`
  is not listed in `order_classes.csv`.

Orphans never become lots, never count as demand and never count as ordered quantity anywhere.
