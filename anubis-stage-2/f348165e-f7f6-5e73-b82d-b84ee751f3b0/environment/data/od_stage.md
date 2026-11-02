# Stage dependencies

This file lists which stage consumes which; the rules of each stage are in its own document.

- Billing consumes the settlement result of every pool of the class, the token units of every member, and the rate row of the class.
- Corrections consume the register and both correction layers, and they are complete before pool membership is formed.
- Calibration consumes the meter sheet, the alias table, the corrected tenant rows and the token units of every class in scope, and gives the units per RU of every pool that needs one.
- Demand consumes the window of the class, the model weights, the alias table, the corrected tenant rows and the units per RU of every pool of the class.
- Reconciliation consumes the bill lines, the class totals and the ledger database written in the same run.
- Recommendations consume the settlement results and the review threshold.
- Settlement of a pool consumes the corrected membership, the demand of every member and the pool parameters.
- The manifest consumes every other report of the run, and is written last.

The program settles every class in scope before it writes any report.
