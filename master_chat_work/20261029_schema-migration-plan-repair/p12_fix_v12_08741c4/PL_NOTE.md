# PL note: schema-migration-plan-repair, QC v12

False positives: none. All six findings were real and five are fixed:

- DS-20: the reference solution now answers QC's 1,102-schema graph in about 0.06 s (was 21-27 s), with the same plan; it gives identical plans on all 1,109 planner calls the tests make.
- DS-27: the truth file now describes only the current grading, with criterion ids R1-R21.
- JD-15: the two judge probes on missing-file and bad-cost behaviour were removed (no contract sentence states that behaviour). The judge is now 21 criteria, 43 positive points.
- Verifier timeout: raised to 3,600 s (as in caldermoor-commitment-closure).
- Probe names in the solution's report are now descriptive (no judge ids).

Kept warn:

- TS-23 (141 checks over the 35 guide): kept with the count, by the no-cap decision (24 Oct, option A 27 Oct). The extra checks are the 60 large gated worlds that carry the difficulty.

No open questions.
