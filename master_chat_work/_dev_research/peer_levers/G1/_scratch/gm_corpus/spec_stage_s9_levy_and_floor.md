# S9 Settlement Levy and Floor

Two post-settlement adjustments are applied AFTER S8, in this exact order and
with these two constants that live ONLY in the levy addendum DOCX:
1. Smurf levy: subtract round_half_even(rewarded_credits * levy_bps / 10000)
   from the S8 net.
2. Settlement floor: the reported per-stratum net_credits is the greater of
   the post-levy value and the floor. The floor is applied last of all.
The season total net is the sum of the floored per-stratum net values. The
levy basis points and the floor are NOT in any plaintext file and NOT in the
spreadsheet; read them from the DOCX.
