# Scoring rules

This file defines how every processed row is valued, how flag penalties are waived
through premium standing, how values fold into the checksum, and how the leading
accounts are ranked. It uses the terms of the other documents: processed rows, control
rows, positions and live rows (ledger_rules.md), booked accounts, billing regions and
sponsors (identity_rules.md), amended cells (amendments.md), kind weights
(rate_card.md) and chain rows (schema.md).

All arithmetic is exact integer arithmetic. No value is rounded unless a rule says so.
Values may be negative; a negative value is reported as it is.

## Base value

The base value of a processed row is

    amount * units * weight + region_offsets[billing region] - floor(latency / latency_quantum)

where amount, units and the flag are the row's cells after amendments, weight is the
kind weight of the row's kind (rate_card.md), the billing region is that of the row's
booked account, latency is the row's latency in whole milliseconds (schema.md), and
`region_offsets` and `latency_quantum` come from the rules file.

## Carried value

Every chain row carries part of the value of the chain row before it in its chain. The
carried value of a chain row is its base value plus the carry left by the chain row
before it; the first chain row of a chain starts from a carry of zero. The carry a
chain row leaves is its carried value reduced modulo `carry_modulus` from the rules
file, taken as the least non-negative residue.

Which processed rows are chain rows, how chain rows divide into chains, which chain row
comes before another, and the carried value of a processed row that is not a chain row
are set by the carry chain entry of the record dictionary (schema.md). This section
applies only together with that entry.

The carry is taken from the carried value before any flag penalty, so a penalty, and
the waiver of a penalty, never moves a carry.

## Flag penalty and final value

The flag penalty of a processed row is `flag_penalties[flag]` for its flag after
amendments; a flag the table does not list carries a penalty of zero. The final value
of a row is its carried value minus its flag penalty, unless the penalty is waived, in
which case the final value equals the carried value.

## Waivers and premium standing

The flag penalty of an ordinary row is waived when the sponsor of the row's booked
account (identity_rules.md) holds premium standing. Control rows are never waived. An
account with no sponsor is never waived.

Premium standing is held only by accounts that have at least one ordinary processed
row, and is decided by the standing rule of the legacy engine (legacy_notes.md), applied
to each such account's sponsor, its ordinary rows and live rows, its unwaived total, its
waivable penalty and its carried total, with `premium_floor` from the rules file as the
floor.

- The ordinary rows of an account are its ordinary processed rows, live or withdrawn;
  its live rows are those of them that are live at the end (ledger_rules.md).
- The unwaived total of an account is the sum of the final values its live ordinary
  rows would have with no penalty waived.
- The carried total of an account is the sum of the carried values of its live
  ordinary rows.
- The waivable penalty of an account is the sum of the flag penalties of its live
  ordinary rows.
- A rescued account is an account that holds premium standing but fails the standing
  policy's membership test for itself when its own waivable penalty is taken as zero,
  with the standing of every other account, its sponsor's included, kept as held.
- The waived penalty of a workload is the sum of the flag penalties waived on its
  processed rows, live or withdrawn.

## Checksum

The checksum folds every processed row, control rows included, in position order,
starting from zero:

    checksum = (checksum * 1315423911 + final value * position + int(id[1:])) & 0xFFFFFFFF

where position is the row's one-based position and int(id[1:]) is the integer written
after the letter of the row id. A withdrawal never changes a row's final value, so
withdrawn rows fold like any other.

## Ranking

`top_accounts` lists the first `top_n` entries of the account totals, ordered by total
from high to low, with equal totals ordered by account id compared as text, ascending.
Each entry is a two-element list of account id and total.

## Scenario metrics

`total_score` is the sum of every account total. `average_score` is `total_score`
divided by the number of rows live at the end, rounded down (toward negative
infinity); it is 0 when no row is live. `top_account` and `top_account_score` are the
account and total of the first entry of `top_accounts`, or null and 0 when the list is
empty.
