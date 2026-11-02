# UNIQUENESS

Every accepted night in every book has exactly one maximum-net-value plan. The count is made at build time by WORK/cw.py solve_night(count=True) with families carried in date order; a night whose count is not 1 is redrawn with the next attempt number, and the attempt numbers are frozen into the books (shipped_meta.json, hidden_meta.json). Tests regenerate each book from those numbers and check its sha256, so no counting runs at test time.

| book | nights | nights redrawn | optimal-plan count on every accepted night | naive-collapse crossing nights |
|---|---|---|---|---|
| shipped | 415 | 9 | 1 | 30 nights of at most 12 jobs where naive collapse differs (check_exact.py enumeration) |
| dense (H1) | 6 | 0 | 1 | 3 |
| linked (H2) | 10 | 1 | 1 | 1 |
| wide (H3) | 8 | 0 | 1 | 1 |
| mutation (M) | 14 | 1 | 1 | 0 (not a crew book; carries reset_nightly and no_initial differences) |

Distinct bay minute rates break lane symmetry. In the prototype, nights without them had 4 to 128 optimal plans. Because the optimum is always unique, the stated tie order (contract.md:91-95) never decides an output. WORK/check_exact.py confirms this independently by full enumeration on every night of at most 12 jobs and by a counting memo recursion on the larger nights.

## Lessons for the master

- Unique optima came from distinct per-bay rates plus a redraw at build time | no change: recorded in DESIGN.md.
