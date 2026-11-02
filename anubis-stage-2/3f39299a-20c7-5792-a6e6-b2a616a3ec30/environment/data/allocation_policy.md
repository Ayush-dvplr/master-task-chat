# Allocation policy

This document covers the allocation parameters, when a depot-week is rationed, how a rationed
depot-week is shared out, how much weight each customer carries when salt is short, and the
true-up owed to public customers at the end of the season. When the allocation happens and what
is on offer are covered in calendar_and_time.md and lot_ledger.md.

## Allocation parameters

Eight parameters govern the allocation. Each has a standing default.

| Parameter | Values | Standing default |
|---|---|---|
| `public_weight` | whole number, 1 or more | 2 |
| `commercial_weight` | whole number, 1 or more | 1 |
| `allocation_unit_kg` | whole number of kg, 1 or more | 500 |
| `tie_break` | `lowest_customer_id`, `highest_weight` or `oldest_open_lot` | `lowest_customer_id` |
| `deficit_threshold` | decimal string with exactly two decimal places, between 0 and 1 | `"0.50"` |
| `bonus_composition` | `additive` or `multiplicative` | `additive` |
| `review_floor` | decimal string with exactly two decimal places, between 0 and 1 | `"0.40"` |
| `review_round_limit` | whole number, 0 or more | 1 |

The office issues parameter versions in `allocation_parameters.json`. A version is in force from
its effective instant on. The parameters in force at an instant follow from the versions
effective at or before that instant, taken in order of effective instant (and, between versions
with the same effective instant, in order of `version_id`), starting from the standing defaults:

- a `replace` version first sets every parameter back to its standing default, then sets the
  parameters it lists;
- a `patch` version sets the parameters it lists and leaves every other parameter as it was.

With no version effective at or before an instant, the standing defaults are in force. Each week
is allocated under the parameters in force at its allocation instant (calendar_and_time.md).

Below, U stands for the `allocation_unit_kg` in force for the week.

## Rationed and unrationed depot-weeks

A depot-week is rationed when the total open demand of all customers at the depot that week is
strictly greater than the depot's available stock. In a depot-week that is not rationed, every
customer receives its whole open demand.

## Allocation units

In a rationed depot-week, salt is shared out only in whole allocation units of U kg.

- The depot has `floor(available stock / U)` allocable units.
- Each customer's cap is `floor(its open demand / U)` units.

A customer never receives more than its cap. Any stock that is not handed out stays at the depot.

## Fair shares

Each customer at a rationed depot-week carries a positive whole-number weight (Customer weight,
below). If the caps of all customers together do not exceed the allocable units, every customer
receives exactly its cap. Otherwise the level L is the non-negative rational number such that giving every customer the smaller of its cap and its weight times L uses up exactly the
allocable units. Each customer's fair share is the smaller of its cap and its weight times L. Fair
shares are measured in units and are usually not whole numbers. When every customer receives its
cap, each customer's fair share is its cap and there is no level.

## Whole units

When the caps of a rationed depot-week together exceed its allocable units, the office hands the
allocable units out by one of the following bounded divisor procedures. Start every customer's
unit count at zero. Repeatedly give one unit to an uncapped customer maximizing its current
weight divided by d(n), where n is that customer's count before the unit. Resolve equal exact
rational priorities by the tie-break below. Stop when all allocable units have been given. The
same procedure, with the same divisor parameters, applies at every depot-week and in every
season; there is no adjustment by depot, customer, week or input size. The admissible divisor
sequences are exactly these four forms (all endpoints included; integers advance by one):

- d(0) = k/1000 for integer k from 1000 through 2000; d(n) = 2n+1 for n at least 1.
- d(n) = n+k/1000 for all n at least 0, integer k from 100 through 1000.
- d(0) = a/100, d(n) = n+b/100 for n at least 1, integers a from 40 through 100 and b
  from 30 through 70.
- d(0) = a/100, d(n) = 2n+b/100 for n at least 1, integers a from 100 through 199 and b
  from 0 through 149.

Multiplying every divisor in a sequence by the same positive constant gives the same procedure.
All comparisons use exact
rational arithmetic. A customer receives its final count times U in kg.

Wherever the procedure has to choose between customers it treats alike, the `tie_break` in force
decides which of them comes first:

- `lowest_customer_id`: the customer with the lower customer id comes first (customer ids are
  compared as text, as they are everywhere in these documents).
- `highest_weight`: the customer with the higher weight comes first; between equal weights, the
  lower customer id comes first.
- `oldest_open_lot`: the customer whose oldest lot on offer at the depot that week was placed
  earliest comes first; between equal instants, the lower customer id comes first.

## Customer weight

A customer's weight in an allocation of a rationed depot-week starts from its segment weight:
`public_weight` for a public customer and `commercial_weight` for a commercial one. The segment is
the one source_authority.md assigns.

Three bonuses can apply on top of the segment weight:

- the critical route bonus, when the customer serves a critical route at the week's allocation
  instant (source_authority.md);
- the deficit bonus, when the customer is in deficit for the week (Deficit status, below);
- the review bonus, when the customer is on the depot-week's review list for the allocation being
  made (Review rounds, below).

How the bonuses combine with the segment weight is the `bonus_composition` in force:

- `additive`: weight = segment weight + 1 for each bonus that applies.
- `multiplicative`: weight = segment weight, doubled once for each bonus that applies.

## Deficit status

A customer is in deficit for a week when its season-to-date entitled quantity is above zero and
its season-to-date delivered quantity is strictly below the `deficit_threshold` times its
season-to-date entitled quantity.

Both figures are taken at the allocation of the week, after that week's merges and retirements
have taken effect, over every lot the customer then holds that was placed in an earlier week, and
only deliveries made in earlier weeks count. Each such lot contributes to the two figures as the
entitlement basis of its order class directs; record_dictionary.md defines the bases under
`order_classes.csv`.

The same deficit status applies at every depot where the customer has open demand that week.

## Review rounds

A rationed depot-week is not settled by its first allocation. After each allocation of the
depot-week the office reviews it, and the review may add customers to the depot-week's review
list. Which customers a review adds is decided by one test of the class below. For each customer not already listed, compare its grant g in whole units against
a threshold made from the `review_floor` F in force and one of the expressions below. Use exact
rational arithmetic. The same one expression and comparison apply to every review, including
reviews after a repeat allocation, in every depot-week and season. No other trigger or special
case is admissible. Let B be the customer's fair share calculated before any review bonus, C
its fair share in the allocation just reviewed, P its share in the preceding allocation (C on
the first review), K its cap, D its open demand in kg, A the depot's allocable units and W the
sum of current customer weights. The test is one of these:

| Reference | Permitted tests for joining |
|---|---|
| B | B > 0 and g < F*B; B > 0 and g <= F*B; B > 0 and g < F*floor(B); B > 0 and g < F*ceil(B) |
| C | C > 0 and g < F*C; C > 0 and g <= F*C; C > 0 and g < F*floor(C); C > 0 and g < F*ceil(C) |
| P | P > 0 and g < F*P |
| K | K >= 1 and g < F*K; K >= 1 and g <= F*K; K >= 1 and g < floor(F*K) |
| D | D > 0 and g*U < F*D |
| A and W | K >= 1 and g < F*A*current_customer_weight/W |

A customer added to the list stays on it for
the rest of the depot-week.

If the review adds nobody, the depot-week is settled and the allocation just reviewed stands. If
it adds anyone, the depot-week is allocated again from the start (same available stock, same
open demand), with the review bonus applying to every customer on the review list, and the new
allocation is reviewed in turn. The office makes at most `review_round_limit` such repeat
allocations in one depot-week. When that many repeat allocations have been made and the review of
the last one would still add a customer, the depot-week is unsettled: the last allocation stands
and nobody further joins the review list.

A depot-week's review rounds are the number of repeat allocations made in it. The review list and
the review bonus belong to that one depot-week only.

## Season true-up

Public customers hold contracts that promise a minimum season quantity (`contract_min_t` in the
contracts register). At the close of the season, each public customer with a contract minimum
above zero that is still in good standing at the final closing cutoff (it resolves to itself, so
it has not been merged into anyone, and it is not retired) is owed a true-up credit. The credit is
the smaller of its contract minimum and its season ordered quantity, less its season delivered
quantity, when that difference is positive; otherwise there is no credit.

The season ordered and delivered quantities of the true-up count every lot the customer holds at
the close of the season, at every depot, each at its full quantity and with everything ever
delivered to it, whatever its order class.
