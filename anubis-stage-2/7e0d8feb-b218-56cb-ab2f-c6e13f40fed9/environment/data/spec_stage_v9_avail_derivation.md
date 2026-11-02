# V9 avail derivation

Inputs: `spot_order_book.jsonl`, `clearance_state_journal.csv`,
`rate_card_book.csv`, the break sets from V10, and the separation minimum
published in `regulatory_minutage_memo.pdf`.

## The break capacity

Each break carries an `avail_seconds`. Its capacity in channel frames is
that duration converted by the carry rule inside the scope `V9:` and the
market reference, with the breaks of a market converted in transmission
order. A break with an `avail_seconds` of zero has a capacity of zero
frames.

## R32 the effective clearance state

`clearance_state_journal.csv` holds several rows per `clearance_ref`. The
effective state is the state of the row with the greatest `journal_seq`.
The `logged_at` column is backfilled by the traffic system and its order
frequently disagrees with the sequence order. The sequence settles it.

## R38 the sequence is a whole number

`journal_seq` is a whole number and compares as one. A journal can run past
nine entries, and sequence 10 follows sequence 9. Compared as text, `9`
sorts after `10` and `11`, which settles the wrong row.

## R21 the spot duration

A spot occupies the channel frames its `nominal_seconds` converts to under
the carry rule inside the scope `V11:` and the advertiser reference, as V4
sets out. That conversion happens for every order in the book before any
admission decision is taken.

## R22 the admission predicates

Orders are considered market by market. Within a market, orders are ordered
by ascending `priority_band` and then by ascending `order_ref`, and are
walked in that order. That is rule R24.

For each order, these seven predicates are evaluated in this exact order and
the first one that holds settles the order. The break named by an order's
`break_ref` is the break it is sold against; it is never moved to another
break.

  1. the effective clearance state is `CL_HELD`, giving `DF_CLEARANCE_HELD`
  2. the slot the break belongs to is substituted in this market, giving
     `DF_MARKET_BLACKED`
  3. the break reference is not in this market's break set, giving
     `DF_NO_MATCHING_BREAK`
  4. the order's `daypart_ref` differs from the break's daypart, giving
     `DF_DAYPART_MISMATCH`
  5. the order's rate card has no row effective on or before the
     transmission date, giving `DF_NO_RATE_CARD`
  6. the frames already admitted to the break plus this spot's frames exceed
     the break's capacity, giving `DF_BREAK_FULL`
  7. the separation rule is breached, giving `DF_SEPARATION`

An order that none of the seven settles is admitted. It takes the next
admitted position in its break, starts at the break position plus the frames
already admitted there, and occupies its own frames.

The order of the predicates is the whole of the rule. A held order that
would also have overflowed its break is deferred as held, not as full.

## R23 the separation rule

Let `S` be the separation minimum positions published in the memorandum, and
let the order under consideration be about to take position `n` in its
break. The separation rule is breached when an already admitted spot at
position `p` in the same break carries the same `separation_class` and
`n - p` is less than `S`. A minimum of two therefore bars two spots of one
class from adjacent positions.

A deferral costs the break nothing: a deferred spot consumes no capacity and
takes no position.

## Published

`avail_plan.tsv` publishes the admitted spots ordered by market, then by
break position, then by break reference, then by position in break.
`deferral_ledger.jsonl` publishes one record per deferred order, ordered by
`order_ref` and then by market reference, carrying the reason and the one
based index of the predicate that settled it.
