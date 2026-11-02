# LEVERS (harden r2, bddb388)

Lever kind: L2 held-out instances firing a documented quiet branch (route-1 R4).
Rule: spec_stage_p01_identifier_and_revision.md:19-22, every job identifier read through the
active crosswalk rows; toy example worked_examples.md:73-81 on a precedence row only.

| lever | shipped count | hidden rounds | checks (weight 5 each) | a3 program |
|---|---|---|---|---|
| crosswalk on slot group memberships | 0 legacy ids outside the crosswalk | HELD_GROUPS, HELD_GROUPS_CASCADE, HELD_GROUPS_PUBLISHED, plus the three every rounds | groups_state, groups_cascade, groups_publication | drops the member: WRONG |
| crosswalk on charge rule subjects | 0 | HELD_RULES, HELD_RULES_CASCADE, HELD_RULES_PUBLISHED, plus every rounds | rules_state, rules_cascade, rules_publication | rule never fires, raw subject in 05: WRONG |
| crosswalk on amendment payloads (with AMD-120 reversing AMD-102) | 0 | HELD_AMENDMENTS, HELD_AMENDMENTS_PUBLISHED, plus every rounds | amendments_cascade, amendments_state, amendments_publication | AMD-NOTARGET / EDG-UNKNOWNJOB: WRONG |
| all three places | 0 | HELD_EVERY, HELD_EVERY_CASCADE, HELD_PUBLISHED | every_state, every_cascade, every_publication | WRONG |

Lever weight 60 of 110 positive (54.5%). Generator: `_legacy`, `_lever_amendments`,
`_assert_legacy`, `write_corpus(dest, seed, legacy)`; default `legacy=()` keeps every old corpus
byte-identical. 300-seed scan (variant groups,rules,amendments): 133 build, 167 abort in the
pre-existing boundary engineering (Q4), 0 plant failures.

BRANCH_FIRE (W5)

| branch | shipped round | hidden rounds |
|---|---|---|
| legacy id in group membership | 0 | 6 |
| legacy id in rule subject | 0 | 6 |
| legacy id in amendment payload | 0 | 5 |
| reversal of an edge lodgement | 0 | 5 |
