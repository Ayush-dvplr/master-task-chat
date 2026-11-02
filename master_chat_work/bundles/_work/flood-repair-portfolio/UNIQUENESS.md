# UNIQUENESS ed7b0c2 flood-repair-portfolio

Every graded portfolio has exactly one reading. The contract (line 62) breaks ties by comparing the sorted id lists at the first differing position, the smaller id winning; since every benefit is at least 1, no maximiser is a prefix of another, so the rule always picks one list. Counts below are numbers of maximum-benefit portfolios on raw benefits (WORK/count_opt.py, frontier DP), before the tie-break.

| book | seed | large rounds (n, optimum count) | small rounds with count 2 | small rounds with count > 2 |
|---|---|---|---|---|
| SHIPPED | 558214 | R79260 (150, 1), R57468 (160, 1) | 24 planted ties (12 twin pairs, 12 path a-b-c with w(b) = w(a) + w(c)) | 0 |
| H1 | 714301 | R66927 (156, 1), R27904 (160, 1) | 8 planted ties | 0 |
| H2 | 721402 | R51408 (160, 1), R95003 (148, 1) | 8 planted ties | 0 |
| H3 | 731503 | R13512 (152, 1), R60496 (144, 1) | 8 planted ties | 0 |
| M | 742604 | R70125 (150, 1) | 6 planted ties | 0 |

Candidate seeds h1_2, h3_3, h3_4 were rejected because a large round had 2 or 4 maximisers. A planted tie is the only place the tie-break decides; the mutants no_tiebreak and tiebreak_largest each lose 80 of 108 test points.

Fault rows: the contract fixes one reported fault per round (files in manifest order, rows in file order, first applicable check, then NONPOSITIVE_BENEFIT on the first row below 1), so data_quality has one reading per round; the 19 planted fault kinds are covered by the shipped book and by H1-H3 + M together.

## Lessons for the master
- Count maximisers on raw benefits before the tie-break; a seed filter on uniqueness of large rounds removed 3 of 12 candidates | no change: task specific.
