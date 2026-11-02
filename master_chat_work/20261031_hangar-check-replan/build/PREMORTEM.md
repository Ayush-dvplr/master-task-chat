# PREMORTEM af5dddf hangar-check-replan (written before any other design file)

Assumed solver: claude-opus-5, careful, stdlib Python, 10 minute first write, H8 (first fitting
candidate) and H9 (self-tests on shipped data and its own tiny examples, never an input that fires a
stated branch it did not already think of).

## Minutes 0-10, step by step
1. Reads instruction.md (job, output paths, exactness, rerun command), then docs/rule_register.md,
   which names each governing file. Opens docs/planning_policy.md (objective order, deferral,
   moved count, tie-break), docs/data_conventions.md (calendar, closures, availability, rejects),
   then the data files in register order: fleet_limits.toml, class_rates.yaml, check_types.json,
   check_requests.csv, published_plan.csv, fleet_register.csv, base_calendar.jsonl,
   disruption_notice.md.
2. Sees four bases, one heavy-check line per base, a fleet-wide overtime shift pool. Notes the
   shipped season has about 6 open checks per base.
3. First program (the transliteration): parse and validate, map tail -> class, apply the notice,
   then per base a recursive search over check order with ASAP start and a compression choice,
   scoring (overdue, revenue, moved) lexicographically. Likely variants:
   - V1 split-by-base exact, overtime taken first come first served in base order (or pro-rata),
     because "each base is independent except the pool" is the first fitting decomposition;
   - V2 split-by-base exact, then a greedy marginal allocation of the pool (give the next shift to
     the base whose objective drops most), the "careful" version;
   - V3 whole-fleet joint search with pruning (seen as safest, slow on hidden scale);
   - V4 per-base exact frontier (best plan for every overtime budget) merged by a knapsack over
     bases. This is the exact method; we expect at least one of the subtler rules below to break
     it anyway.
4. Self-tests: runs on shipped data, checks pool not exceeded, checks every finish <= season end,
   no overlap on a line, no closed day inside a span, no start on a no-start day. Maybe a tiny
   2-check example of its own. Compares nothing against an independent brute force at hidden
   scale, and never builds a case where the pool binds (H9), because on shipped data the
   unconstrained optimum already fits inside the pool.

## Per rule: where the first program goes wrong, and why self-tests miss it
| rule | reflex reading / program | where it goes wrong | why its self-tests pass |
|---|---|---|---|
| R1 shared overtime pool + compression | V1 FCFS or pro-rata pool, V2 greedy marginal | hidden pool binds: FCFS starves later bases; pro-rata rounds wrong; greedy marginal stops at a local step when a base needs 2 shifts to gain anything (non-convex frontier planted every hidden seed) | shipped optimum uses less than the pool, so every allocation rule returns the same plan; feasibility asserts all pass on the wrong hidden plan too |
| R2a moved count (start differs from published start) third in order | ASAP-only starts (left-shifted schedule is the textbook dominance) | hidden checks whose availability is earlier than the published start: the optimum waits to the published start when overdue and revenue are unchanged; ASAP moves it | shipped availability equals the published start for every check, so ASAP equals published |
| R2b tie-break: fleet vector of start days in request-id order, then finish days | first found in loop order, or per-base key then base order | hidden planted ties: two allocations of the same pool shifts to different bases with equal (overdue, revenue, moved); the fleet vector picks by request id across bases | shipped data has no tie at the optimum; a program cannot see a tie it never generates |
| R3 deferral penalty in the first term, reason strings | defer only when no slot exists (no_slot), never as a trade | hidden: deferring one low-penalty regional check removes more weighted overdue than its penalty (risk_trade) | shipped deferrals (if any) are all no_slot; "everything that fits gets scheduled" passes every shipped invariant |

V4 (exact frontier merge) still loses on R2b if the merge compares cost only, and on R2a if starts
are ASAP-only; both are the default shape of a frontier DP (state = finish time, one start per
choice).

## Planned judge probes: does the first-write trajectory show the act?
| probe | act | Opus first write shows it? |
|---|---|---|
| P-b optimality witness on a pool-binding instance | builds or edits an input where the pool binds and shows the plan is optimal against an alternative | no (H9: never builds a firing input) |
| P-c recompute objective outside the program | recomputes the objective vector from policy_audit.json by a separate script | sometimes (about 1 in 3) |
| P-d altered-copy rerun | runs the program on a copy of data/ with values changed | rarely |
| P-e relocated rerun | runs the program from another cwd with data copied elsewhere | rarely |
| P-h deferral/infeasible input | builds an input where a check cannot finish in season and shows the deferral row | rarely |
| P-g uniqueness witness | shows a planted tie resolved by the stated vector | no |
| P-a edge input run (pool 0) | runs with the overtime pool set to 0 | no |
| P-f broken tool run first | runs the shipped derive_report.py before editing it | about half |

## Redesign trigger check
A first-write program that is exact on shipped AND on a fresh hidden seed would have to: merge per
base frontiers exactly, consider the wait-to-published start, defer as a trade, and break ties by the
fleet vector. V1-V3 and plain V4 each miss at least one; the kill test must measure this in Docker
before DESIGN READY.
