# PL note: b7c42a8f (Nikhil Bansal, IBNR reserving), fix v2 72ebb9d

All 21 QC v2 findings (13 fail, 7 minor, 1 warn) were real and are fixed. No false positives, nothing unsure, nothing paused.

What changed, in plain words:
- The instruction and the judge now name the fourteen counterfactual numbers exactly as the parameter file defines them, with integers from one fresh oracle run.
- The data now has real loss development (IBNR about $2.0M instead of $88), and the oracle takes accident year from claim_master.csv as the rules say.
- The docs now say how the booked layer is chosen, spell the clash-cover identifier, and place a null reinsurer first in the ledger order. The unused attachment_windows.csv and the dead code that read it are gone.
- Hidden extract B now has a retraction notice for the unresolved-reinsurer claim, so that precedence is graded.
- Tests: four overlapping or empty checks removed, one mixed check split, two new small checks (summary/treaty values, standard-library imports). Negatives no longer stack on one cheat. Judge: two criteria dropped, three narrowed or relabelled.

Kept (carry-overs QC already accepted): exact whole-ledger bar, R16/R17 weights, 200-line cap, oracle run 3 times, test count.
Two small deviations: the TS-13 split is weights 3 + 1 (the kit allows no pair summing to 3), and the TS-20 fix raised the weaker check instead of swapping.
Oracle 1.0 x3, owner 1.0, nop 0.0. Saved run predicted final 18.68 before, 18.56 after.
