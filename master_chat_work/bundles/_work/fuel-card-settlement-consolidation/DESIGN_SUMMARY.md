# DESIGN_SUMMARY R2: fuel-card-settlement-consolidation (60e9db0), 21:35 IST

Why R2: the design-stage blind read (DESIGN_BLIND.md) wrote all 42 rules and all 15 quiet branches right in about 4 minutes and was exact on 13/13 documents on shipped and 3 hidden seeds (after a lumen field-class hole was fixed). Plain `if` rules, even quiet ones, are transliterated.

Kept from R1: Shape B; S1 (42 stated rules, 23 files, 9 formats), S5 (2023 standard demoted at `group_standard_2023.md:3`, s7 CNG kept by `group_standard.md:149-150`), S6 (15 quiet branches, shipped 0, measured fire on 3 seeds); COUPLING sentence "Every settled amount uses the discount tier earned by the account's whole-month settled volume across all processors."; 30 checks, positive 121; 9 hidden months H1-H9 each graded on 2 families; toys on invented 2041 values.

Added (DESIGN.md section 9):
1. S3 unique fit, `group_standard.md` 11.4-11.5: a norvik or oberon reversal with an empty reference reverses the one sale line that fits (same processor, card, product, quantity and amount; settled as a sale line; dated on the reversal's date or the six days before; not reversed by another line). Referenced reversals are resolved first; empty-reference reversals in ledger order, consuming their match; none fits `orphan_reversal`, more than one `ambiguous_reversal` (new, 13th reason). One toy on 2041 values (window case).
2. Shipped: about 60 empty-reference reversals, each with exactly one fit under every reading.
3. Hidden sub-branches, 2 per hidden month, each on 3 months: U1 two fit; U2 ledger order differs from file order; U2r referenced reversal later in file consumes the twin; U3 rejected twin earlier in file; U4 first candidate outside window; U5 U2 across a mid-month card reassignment (moves tier volume between accounts; COUPLING).
4. Q16: referenced reversal after a mid-month tax change (11.3 negated original vs recomputed tax), master point 2.
5. Unstated cases (master point 1: date before first effective_from, card with missing account, unknown site, double referenced reversal) never generated; generator asserts; EVIDENCE_MAP rows.
6. Judge: probe R8 becomes P-g (input with two fitting lines, states how many fit); band 8 x3 = 24/35 (68.6%); lower 8.6, mid 37, upper 66.

Premortem (PREMORTEM.md section 6): the first write indexes `(card, product, qty, amount)` over every parsed line and pops the first in file order while streaming; exact on shipped, wrong on U1-U5; self-tests are shipped controls only.

Estimate: first-fit everywhere tests ~26, final ~31; one ordering sub-branch wrong tests ~75, final ~56; all exact tests ~100, final 64-68 (65-75 band). Risk: a careful transliterator may implement 11.5 exactly; the next blind read decides.

Next on go: extend fcgen.py and solve_proto.py with R43/U1-U5/Q16, regenerate shipped + 3 seeds, measure BRANCH_FIRE, refresh `design_blind/`, stop at DESIGN BLIND READY for a second P13 read.
