# Lot ledger

The office tracks salt owed to customers as lots. This document covers the life of a lot from the
order that creates it to the end of the season, and how stock moves from week to week. The
layouts of `orders.csv`, `order_classes.csv`, `receipts.csv` and `depots.xml` are in
record_dictionary.md.

## Lots

Every order that is neither void, cancelled nor an orphan becomes exactly one lot. A lot carries:

- the order id;
- its quantity in kg: the order's final quantity after its amendments (source_authority.md);
- its placement instant, and the week that instant belongs to (calendar_and_time.md), called its
  placement week;
- its order class, as keyed on the order;
- its depot, fixed when it is created (identity_register.md, Service areas) and never changed;
- its holder: the customer that the order's reference resolves to at the placement instant. The
  holder can change later through a merge.

## Opening stock

Each depot starts the first week with the stock given as its `opening_stock_kg`.

## Holder changes through merges

When a customer is merged into another, the transfer of its lots happens at the allocation of the
week that holds the merge's effective instant, before any demand at any depot is assessed for that
week. Every lot the merged customer holds at that moment and placed before the merge instant (open
lots, fully delivered lots, lapsed and withdrawn lots, every one of them) passes to the merge
target, which holds it from then on. When the target has itself been merged into another customer
by the merge instant, the lots pass to the customer the target resolves to at that instant
(identity_register.md). The lot keeps its depot, its placement instant, its order
class and its delivery history. A lot placed at or after the merge instant was already resolved
to the target when it was created.

If a merge target is itself merged later, the lots it holds at that later merge, including the
ones it received earlier, pass on again.

When several merges and retirements belong to the same week, they take effect at that week's
allocation one after another, in order of effective instant (identity_register.md gives the order
between events with the same instant). A merge or
retirement whose effective instant belongs to no week of the season moves and withdraws no lots,
although it still governs how references resolve.

## How long a lot stays on offer

A lot is on offer at its depot in its placement week and in the weeks that follow it, for as many
weekly allocations in all as the offer window of its order class (`offer_weeks`), and only while it
has an open quantity (below): a lot with no open quantity is on offer nowhere.

Whatever part of a lot is still undelivered after the allocation of the last week of its offer
window lapses: the lapsed quantity is recorded against that week and the lot is never offered
again. Only a lot whose offer window would run past the last week of
the season stays open when the season closes, and its undelivered quantity is reported as open at
close, not as lapsed.

## Open quantity and open demand

A lot's open quantity at any moment is its undelivered quantity while it has neither lapsed nor
been withdrawn; a lapsed, withdrawn or fully delivered lot has no open quantity.

A customer's open demand at a depot in a week is the sum of the open quantities of the lots it
holds at that depot that are on offer that week, taken after the week's merges and retirements
have taken effect.

## Applying a delivery to lots

Whatever a customer receives at a depot in a week is applied to its lots on offer at that depot
oldest first: in order of placement instant, and between lots placed at the same instant, in order
of order id. Each lot is filled as far as possible before the next one receives anything.

## Stock carried between weeks

A depot's available stock in a week is the stock it carried out of the previous week plus every
receipt that arrives at it during the week (source_authority.md converts receipt quantities).
After the week's allocation, whatever was not delivered stays at the depot and is carried into the
next week. Nothing is lost or moved between depots, and stock never goes below zero. A receipt
whose arrival instant belongs to no week never becomes part of any depot's stock.

## Retirement

When a customer is retired, the allocation of the week that holds the retirement instant first
withdraws every lot that customer holds, placed before the retirement instant, that still has an
open quantity: that open quantity is recorded as withdrawn against the week, and the lot is never
offered again. A later reactivation does not bring withdrawn lots back; orders resolved to the
customer after the reactivation create new lots as usual.

## Season close

After the allocation of the last week, every lot that is neither fully delivered, lapsed nor
withdrawn is open at close for its undelivered quantity.

## Whose lot it is in the reports

Whenever a report attributes a lot's quantities to a customer (regional reports, segment totals,
lapsed and withdrawn lot lists, true-up credits), the customer is the lot's holder at the close of
the season.
