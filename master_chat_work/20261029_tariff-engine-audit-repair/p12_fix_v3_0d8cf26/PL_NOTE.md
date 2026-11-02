# PL note — tariff-engine-audit-repair, QC v3 fix (0d8cf26)

**Fixed (real):**
- DS-22: the answer key (TRUTH.md) described an old statement check and said "three pairs" where the tests build six. Rewritten to match the tests: three hidden statement sets (statement, batch, cycle), 21 checks and 91 points each, six repeated amounts. Prose only; no grading changed.
- TS-11: the tests' result cache was not thread-safe, so the 8 parallel grading threads started the same statement program several times at once (QC counted 82 runs for 28 inputs). Now each input runs once and the other threads wait for it (measured: 83 runs for 29 inputs before, 29 for 29 after). The 10 s limit, every check and every weight are unchanged.

**Kept, false positives (warnings):**
- TS-20 (369 of 670 points on statements): this is the approved difficulty lever (your OK, 29 Oct 09:12, 60% cap). The weight order is right, and QC itself wrote "not an ordering contradiction". Cutting batch/cycle would drop 182 lever points.
- TS-26 (batch/cycle look like duplicates): they grade different hidden inputs (different random seeds), which the kit says is not a duplicate; QC itself wrote "different inputs, so not the kit's strict duplicate".

**UNSURE:** none.

**Numbers after the fix:** oracle 1.0 x3, owner-only 1.0, nop 0.0. The QL agent program still scores 306/670 = 45.67 with no gain, and every kill-table solver loses exactly what it lost before (ratio 1.00). PRECHECK CLEAN, xref 0 findings.

## Lessons for the master
- A thread-unsafe test cache doubles the number of child runs under rewardkit. Catch G12 at harden time | no change: LEVER_RULES_v3 G12 already covers it.
