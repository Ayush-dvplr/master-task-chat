# STACKING_CHECK - board 8cd7597

**Not run for a new design.** Phase 1 found NO NATURAL TRAP and the prompt directs a stop before Phase 2. No new test rows, logic or penalty groups exist to audit.

The inherited r2 tests have 33 checks, with 98 positive weight: 18/98 isolated (18.37%), 76/98 whole hidden documents (77.55%), and 4/98 shipped only (4.08%). The inherited a5 program scored 11/98 = 0.1122 tests-only in `harden_lp1_r2/HARDEN_REPORT.md`; the fresh blind program scored 98/98 = 1.000 tests-only on the same bundle and checks (`blind_r1/SCORE.md`). Thus the fresh-solver gate fails. No rescoring against new tests was possible because none were written. The inherited r2 stacking audit is `harden_lp1_r2/STACKING_CHECK.md`.
