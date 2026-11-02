# Worked reference slice

A complete compile of a tiny invented extract, stage by stage, so every stage
can be checked against arithmetic before the real extract is compiled. None of
the identifiers or figures below belong to this extract.

## The slice

One operator, OP-01, rank weight 3. One zone, Z-ONE, whose transition table
holds a single row: at 2030-03-31T01:00:00Z the offset grows from 0 to 3600.
One section, SEC-01, class mainline, zone Z-ONE. One route, RT-01, whose only
leg is SEC-01 at offset 0. The minimum headway in force for mainline is 15
minutes, the deferral step is 6 minutes and the maximum is 2 deferrals.

One rule, RL-01: `freq` month, `anchor` 2030-03-04, `byday` [1], `bymonthday`
empty, `setpos` [1, -1], `limit` 3, `horizon_periods` 2.

Two paths:

| path | rule | depart | valid_from | valid_to | priority | issue stamp | variant_of |
|---|---|---|---|---|---|---|---|
| PP-00001 | RL-01 | 01:30 | 2030-03-01 | 2030-04-30 | 4 | 2030-01-01T08:00:00Z | |
| PP-00002 | RL-01 | 01:45 | 2030-03-01 | 2030-04-30 | 4 | 2030-02-01T08:00:00Z | pp 00001 |

One exception row: PP-00001, 2030-03-25, exclude. One alias row: OLD-00001 to
PP-00002. No superseded field matters in a slice this small.

## Stage 1

`pp 00001` canonicalises to PP-00001. No alias row retires PP-00001 or
PP-00002, so both resolve to themselves. Both are registered, nothing is on a
cycle, and the one alias row retires OLD-00001, which no file outside the alias
map mentions, so no spelling resolved through an alias.

## Stage 3

Period 0 is March 2030. Its Mondays are 2030-03-04, 2030-03-11, 2030-03-18 and
2030-03-25, a candidate set of four. Position 1 selects 2030-03-04 and position
-1 selects 2030-03-25. Period 1 is April 2030. Its Mondays are 2030-04-01,
2030-04-08, 2030-04-15, 2030-04-22 and 2030-04-29, a candidate set of five.
Position 1 selects 2030-04-01 and position -1 selects 2030-04-29.

Both paths select 2030-03-04, 2030-03-25, 2030-04-01 and 2030-04-29. The
candidate count is nine for each and the selected count is four.

## Stage 4

PP-00001 carries one exclusion on 2030-03-25, which was selected, so it is
removed. Its merged sequence is 2030-03-04, 2030-04-01 and 2030-04-29, three
dates. The cap of 3 keeps all three. The window keeps all three.

PP-00002 carries no exception. Its merged sequence is the four selected dates.
The cap of 3 keeps 2030-03-04, 2030-03-25 and 2030-04-01 and drops 2030-04-29,
so PP-00002 is cap bound. The window keeps the three that survived.

Note the order: had the cap run before the exclusion, PP-00001 would have kept
2030-03-04, 2030-03-25 and 2030-04-01, then dropped 2030-03-25, and ended with
two dates rather than three.

## Stage 5

PP-00002 names PP-00001 as its base, so PP-00001 is the chain root at depth 0
and PP-00002 is at depth 1. One edge. The shared days are 2030-03-04 and
2030-04-01. The priorities tie at 4, so the later issue stamp decides and
PP-00002 wins. PP-00001 keeps 2030-04-29 alone, losing two days. PP-00002 keeps
all three.

## Stage 6

Z-ONE has distinct offsets 0 and 3600. For 2030-04-29 at 01:30 only offset 3600
gives a candidate, so PP-00001 departs at 2030-04-29T00:30:00Z. PP-00002
departs at 2030-03-04T01:30:00Z under offset 0, at 2030-03-25T01:30:00Z under
offset 0, and at 2030-04-01T00:45:00Z under offset 3600. No reading of either
path sits in a gap or a fold here, so both counts are zero and no minute is
shifted. One movement for PP-00001 and three for PP-00002, four in total.

## Stage 7

The walk order is rank weight 3 for both, then priority 4 for both, then the
identifier, so PP-00001 comes before PP-00002, and inside each path the service
date ascends. Four movements:

1. PP-00001 on 2030-04-29, entry 2030-04-29T00:30:00Z. The section is empty, so
   count 0 clears. Admitted, deferral 0.
2. PP-00002 on 2030-03-04, entry 2030-03-04T01:30:00Z. Fifty six days from the
   only admitted entry, so count 0 clears. Admitted, deferral 0.
3. PP-00002 on 2030-03-25, entry 2030-03-25T01:30:00Z. Count 0 clears.
   Admitted, deferral 0.
4. PP-00002 on 2030-04-01, entry 2030-04-01T00:45:00Z. Count 0 clears.
   Admitted, deferral 0.

Four admitted, none deferred, none withheld, four entries on SEC-01.

## Stage 8

PP-00001: one admitted day, zero deferred, zero withheld, zero deferral
minutes, and path minutes of one times the route span of 0, so 0. PP-00002:
three admitted days and path minutes of 0 as well, because this route spans no
minutes.

## Stage 9

PP-00001 has one admitted date, so its base day is 2030-04-29, its bit length
is 1 and bit 0 is set, which packs to the single byte 0x01 and the hex string
`01`. PP-00002 has 2030-03-04, 2030-03-25 and 2030-04-01. Its base day is
2030-03-04, the latest is 2030-04-01, which is 28 days later, so the bit length
is 29. Bits 0, 21 and 28 are set. Byte 0 holds bit 0, so it is 0x01. Byte 1
holds bits 8 to 15, none set, so 0x00. Byte 2 holds bits 16 to 23 and bit 21 is
the value 32 bit, so 0x20. Byte 3 holds bits 24 to 31 and bit 28 is the value 16
bit, so 0x10. The hex string is `01002010`. The set bit total over both paths is
four.

## Stage 10

The paths in identifier order are PP-00001 at position 1 and PP-00002 at
position 2. The value of PP-00001 is 1 times 1000 plus 0, so 1000, and its term
is 1 times 1000, so 1000. The value of PP-00002 is 3 times 1000 plus 0, so
3000, and its term is 2 times 3000, so 6000. The digest is 7000 modulo
2147483647, so 7000.
