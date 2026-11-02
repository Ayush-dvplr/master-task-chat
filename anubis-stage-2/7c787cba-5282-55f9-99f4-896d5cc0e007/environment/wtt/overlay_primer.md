# Overlay primer

One worked chain and one worked cycle on invented figures, so the rules of
stage 5 can be checked against arithmetic.

## A chain of three

Three paths name each other as bases. AA-00001 names nothing, AA-00002 names
AA-00001 and AA-00003 names AA-00002. So AA-00001 is the chain root at depth 0,
AA-00002 is at depth 1 and AA-00003 is at depth 2.

Their running day sets entering the stage, and their priority and issue stamp:

| path | days | priority | issue stamp |
|---|---|---|---|
| AA-00001 | 1 June, 2 June, 3 June | 4 | 2030-01-02T08:00:00Z |
| AA-00002 | 2 June, 3 June, 4 June | 4 | 2030-01-05T08:00:00Z |
| AA-00003 | 3 June, 4 June, 5 June | 2 | 2030-01-09T08:00:00Z |

Two edges exist. The edge whose base is AA-00001 has a base at depth 0 and is
taken first; the edge whose base is AA-00002 has a base at depth 1 and is taken
second.

The first edge shares 2 June and 3 June. The priorities tie at 4, so the later
issue stamp decides and AA-00002 wins. AA-00001 keeps 1 June alone and loses
two days.

The second edge shares the days both still hold. AA-00002 holds 2 June, 3 June
and 4 June and AA-00003 holds 3 June, 4 June and 5 June, so the shared days are
3 June and 4 June. AA-00002 has the higher priority and wins, so AA-00003 keeps
5 June alone and loses two days.

The result: AA-00001 keeps one day, AA-00002 keeps three and AA-00003 keeps one.
Had the second edge been taken first, AA-00002 would have entered the first edge
with a different day set and the answer would have moved, which is why the edge
order is part of the contract.

## A cycle

BB-00001 names BB-00002 as its base and BB-00002 names BB-00001. Following the
bases from BB-00001 reaches BB-00001 again, so both paths sit on a cycle. Both
are rejected, both run on no date, both report a chain root of their own
identifier and a chain depth of 0, and both lose every day they entered the
stage with. Neither one wins and neither one is chosen as the survivor.
