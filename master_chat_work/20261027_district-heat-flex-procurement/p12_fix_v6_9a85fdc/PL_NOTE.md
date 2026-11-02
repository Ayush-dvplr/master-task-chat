# PL note: district-heat-flex-procurement after QC v6 (P12 9a85fdc)

False positives: none. All five QC v6 findings were real; four are fixed.

Fixed:
- DS-27: TRUTH.md no longer talks about rounds, probe programs or blind programs. It gives the oracle's score and the score of each named wrong reading, out of 205.
- JD-7: the reference solve.sh now builds four small extracts of its own, runs the program on each and prints the program's figure beside a hand-worked one. Judge R1-R4 are now shown by the oracle.
- JD-15: the code-layout criterion (old R5) is deleted; the rest are renumbered R1-R11 and the judge weight is 0.5/24.
- TS-25: the two wide feasibility checks now fail an empty portfolio where the best portfolio is not empty.

Kept (warn):
- TS-23: 58 checks, above the 35 warn line. The kit marks this as a warn only (03_Tests_QC.md:62). No two checks pay for the same thing, so nothing is merged.

Unsure: none.

## Lessons for the master
- none
