# PL note b7c42a8f (IBNR reserving), fix round 3

All 12 QC v3 findings were real, and 11 are fixed using the exact wording in QC's Fix lines. No false positives, no open questions.

Kept (1 warn):
- G04-1, judge R32 (judge.toml:417, weight -3) charges an agent that types the 0.75/0.50 attachment factors into its module. The rule is stated in attachment_rules.md:11 ("The authority is that file alone, not any value typed into the delivered module."). No test grades it, so it is paid once, which is what JD-16 item 4 asks (04_Judge_QC.md:97). QC's Fix line itself says "or leave it".

Carried over unchanged: KEPT-1 to KEPT-5 (exact-match bar, R16/R17 weight 3, R33 200-line cap, oracle x3, check count, now 32).

One change differs from the direction: the test total stays 64, not 63. Deleting the stdlib check takes off 1 point, and splitting the summary check (G03-3) adds 1 back, because weights can only be 1, 3 or 5. reward.toml stays 0.5/64.
