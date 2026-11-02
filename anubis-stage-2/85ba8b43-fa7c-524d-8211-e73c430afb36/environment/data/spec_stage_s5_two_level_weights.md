# S5 Two-Level Rarity Weights

Only matches that are resolved AND drawn (`drawn=1`) carry a weight. The weight
is `base_rate * nonresponse`. The base rate is population count over sampled
count per FROZEN stratum. The nonresponse factor is sampled count over resolved
count per SERVER - a DIFFERENT partition, so the product does not reduce to
population over resolved. Apply nonresponse inflation before quantization.
Quantize weights to 6 decimals half-to-even and allocate each stratum's
rounding residue to the largest
weight, ties broken by smallest `match_key`. For this settlement, 240 is a
reported diagnostic ceiling only; no trimming operation is part of S5.
