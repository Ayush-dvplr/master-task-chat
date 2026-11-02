# KEPT b7c42a8f-6d19-4e35-9f82-5a3c1d7e8042 (after P12 fix 7b203bc)

| finding id | file:line | reason | kit line it rests on |
|---|---|---|---|
| G05-3 CL-4 | tests/test_output.py ledger_backbone_exact, ledger_spine_exact, lob_cycle_capacity_and_fill_exact (whole-ledger digests) | instruction.md:5 "Every figure is a whole number of dollars and exact equality is the bar, so a figure that is merely close is wrong." The exact whole-ledger bar is stated out loud. REBUT. | Final_checklist.md:491 "An instruction that states out loud that only an exact match counts has set that bar deliberately" |
| G04-5 JD-15 (weights) | tests/judge.toml R16, R17 (weight 3) | Weights kept by author decision; R19 fixed to the CLM-00056 row whose columns 4, 5, 7 all differ. | 04_Judge_QC.md:92 (minor) |
| G04-6 R35 cap | tests/judge.toml R35 | Cap is 200 lines, not 80: the oracle main() is 193 lines and an 80-line cap fails the oracle (JD-7). | 04_Judge_QC.md:76 JD-7 |
| Oracle x3 (kit x5) | Final_checklist Step 10 | Oracle run 3 times, 1.0 each (author rule). | Final_checklist.md Step 10 |
| TS-23/A3 count | tests/test_output.py (25 positive + 7 negative = 32 checks) | No count cap; nothing merged or dropped to get under 35. | 03_Tests_QC.md TS-23 (warn) |
