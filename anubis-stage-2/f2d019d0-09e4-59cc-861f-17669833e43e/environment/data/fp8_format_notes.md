# Eight bit dispatch payload

The exchanged payload uses a four bit exponent and three bit mantissa binary
float with a bias of seven. The format has no infinity. Its largest finite
magnitude is 448. Its smallest normal exponent is minus six and its subnormal
quantum is two to the power minus nine.

Casting a magnitude `a`:

1. write `a = m * 2 ** e` with `m` in the half open range from one half to one
2. the unbiased exponent is `e - 1`
3. the quantum is two to the power minus nine when the unbiased exponent is below
   minus six, otherwise two to the power of the unbiased exponent minus three
4. divide by the quantum, round to nearest with ties to even, multiply back
5. **then** saturate: a rounded magnitude above 448 becomes exactly 448

Rounding happens before saturation. Saturating first and rounding afterwards
gives a different answer for magnitudes just under the limit. Zero maps to zero
and the sign is reapplied at the end.
