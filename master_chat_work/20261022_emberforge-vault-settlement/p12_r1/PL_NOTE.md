# PL note: emberforge-vault-settlement, P12 r1

Fixed: AL-2 (new judge criterion R12 for the R05 closing balance, 270), JD-6 (R6 now names the three parts it means), and the two test file warns (dead timeout line, "matches" to "match").

## False positive

- W-01-1: "What must be true when you stop." and "Rules of engagement." are short leads for a paragraph, in plain English. The kit says layout is the author's choice (01_Instruction_QC.md:19), and QC itself said "readable, not slop". Text kept.

## Minors kept

- TS-19: the shipped season's records are checked for presence and form only, on purpose. Every record is checked value for value on reseeded seasons, and the headline figures go to the judge. A full value check on the shipped season would put that answer in the grader. TS-19 itself says a promise the judge covers is covered.
- JD-16 (R10 network): the kit says to warn, not fail, and the criterion is valid. A proper test would need a socket hook inside the agent's program; a static import scan would wrongly hit harmless imports. The agent environment has no network anyway.

## Questions

None.
