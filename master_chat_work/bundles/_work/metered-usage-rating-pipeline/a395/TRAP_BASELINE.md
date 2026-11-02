# Trap baseline (P0.3) a395eb2
Source: WORK/cost_table_g36.json (Docker, 28 Oct 03:30-03:57, proto/g36_runner.py cost, log proto/logs/g36_cost.log).
Measured on tests/test_output.py sha256 93b4efd1e2f3aed9cdf4ab13aadb825da9c6d9fff5f5b4561dfc33aaee800694
= current shipped file (TRUTH.md:181 and `shasum` 29 Oct 04:10), so it is the baseline on the current tests.
Positive test points 407.

| lever | variant (alone) | got | lost | lost % |
|---|---|---|---|---|
| LV-MU-6 | credit second pass re-enters | 203 | 204 | 50.1 |
| LV-MU-5 | one-level billing group | 72 | 335 | 82.3 |
| LV-MU-7 | true-up second pass re-computes | 203 | 204 | 50.1 |
| LV-MU-8 | unmemoized per-account walk | 247 | 160 | 39.3 |
| LV-MU-9 | linear tier scan | 295 | 112 | 27.5 |
| LV-MU-1 (noise) | quoted digit strings accepted | 56 | 351 | 86.2 |
| LV-MU-3 (noise) | committed account by plan in force | 150 | 257 | 63.1 |
QC v1 variant A (north integral floats accepted, LV-MU-1 family): 158/407 lost (v1.md CL-4 row).
