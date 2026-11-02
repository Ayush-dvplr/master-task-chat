# Discounting rules

The treasury discount curve is a methodology reading reported in `methodology_audit.json` under `settlement.discount_curve`. It is settled from the observations in `treasury_curve_observations.log` by enumeration against the two candidate readings `flat_10y` and `duration_matched`. A reading that fits only some of the observations is the wrong reading; the surviving reading is unique.

Under `flat_10y`, every tenor is priced using the 10-year rate in `curve_marks.csv`, so `pv_factor = (1 + curve[10]/100)^(-tenor)` regardless of the row's own tenor. Under `duration_matched`, each tenor is priced at the rate marked for that tenor, with linear interpolation between adjacent marks, so `pv_factor = (1 + observed/100)^(-tenor)` row by row.

The settled reading is applied to the three long-tail LOBs (`wc`, `cal`, `gl`) when discounting the IBNR carryforward.
