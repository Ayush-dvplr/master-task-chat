# RULE_TRACE: hangar-check-replan

One row per generator branch. Generator = `WORK/datagen.py` GEN block (pasted unchanged into `tests/test_output.py`). Doc paths are under `environment/data/docs/`.

| generator branch | datagen.py line | governing sentence | doc file:line |
|---|---|---|---|
| empty base (rare RNG, h1 h2) | 145, 436-438 | every base always gets its report file and summary row, zero counts, null first/last day | output_schema.md:5-8 |
| empty segment public (h1 h2: only widebody/narrowbody) | 150-151, 217 | same universe sentence; segments by class | output_schema.md:5-8, 10-11 |
| tight base gadget (regional D or narrowbody C behind a long closure) -> plan_trade deferral | 147, 185-200 | deferred reason `plan_trade` when it could finish on an empty line | deferral_policy.md:3-9 |
| ordinary closures (prob 0.8, 11-19 days) | 201-205 | no closed day from start to finish | planning_policy.md:10-17 |
| closures split calendar vs notice (hidden: all in-season closures in the notice) | 496 | closed days = calendar CLOSED plus notice closure days | data_conventions.md:54-56 |
| no_slot fixture (season-end closure, late availability) | 207-216 | reason `no_slot` when it cannot finish by season end on an empty line | deferral_policy.md:3-9 |
| published start later than available day (hidden prob 0.45) | 174-176 | moved = start other than published_start; start options | planning_policy.md:30-31 |
| twin check across bases (equal type, length, class) | 158, 177-181 | tie by start-day list then finish-day list in request_id order | planning_policy.md:36-38 |
| pool K = half of free use (hidden) | make() end, after 218 | four bases together within overtime_pool_shifts | overtime_policy.md:9-10 |
| revised availability in notice (hidden: half of r<ps checks; shipped 15%) | 405-411 | available day from notice tail table, else own available_from | data_conventions.md:51-53 |
| clip fixture (available_from before season start) | 413 | before season_start counts as the first season day | data_conventions.md:51-53 |
| other seasons and CANCELLED rows (ignored) | 399, 430 | only season match + OPEN rows are read; others never reported | data_conventions.md:29-33 |
| seven reject kinds + three extra at empty base | 433-457 | eight reasons in order, first that applies | data_conventions.md:34-43 |
| duplicate row after first occurrence | 460-466 | duplicate_request: id already on an earlier read row; earlier kept | data_conventions.md:34-36 |
| X1: ignored CANCELLED row reuses a planned id earlier in the file (h3 h5) | 467-475 | duplicate_request counts read rows only; ignored rows never reported | data_conventions.md:29-36 |
| stype slack (shipped, A = U + 6..12) | 287 | allowance_left = granted minus used | output_schema.md:56 |
| stype cap (h1, A = U) | 289 | each check takes the smaller of its shifts and the allowance left | overtime_policy.md:16-19 |
| stype short (h2, A = U - 1) | 291 | same; one check partly paid | overtime_policy.md:16-19 |
| stype bind + equal-due pair across bases (h3-h6) | 280-281, 245-274 | class, then earlier due_date, then smaller request_id, whichever base | overtime_policy.md:16-19 |
| hidden grants: some base uses more than its own grant | grants_for loop (275-318) | four grants form one fleet allowance | overtime_policy.md:12-15 |
| mutation m1 (grants rewritten binding) | tests_harness.py `_mutant_data` | settlement fields per check and per base | overtime_policy.md:21-24 |
| mutation m2 (revised availability emptied) | tests_harness.py `_mutant_data` | available day falls back to own available_from | data_conventions.md:51-53 |
