# Wave 2 design: metered-usage-rating-pipeline (board 09963d3)

## Phase A
Probe 3 staged copy vs BUNDLE: only `.kiro-staged-from` and task.toml `allowed_hosts` differ. The bundle is what the probe saw.

## Diagnosis (probe 3: tests 247/247, judge 22/34, final 82.35)
Full table: WORK/DIAG_W2.md. In short: first full draft at step 15 (minute 5), exact on every check including LV-MU-5/6/7. Steps 16-35 were self-checks: recompute (verify.py), altered copy, tiny input, error paths with no output shown, a synthetic month smaller than /app/data, a final foreign-cwd rerun. Lost judge R5 (summary from normalized lines) and R8 (main 267 lines). R11 (-3) and R12 (-3) fired. It never timed a run and never ran an input larger than /app/data. Its program is linear except billing_groups(), which walks the parent chain once per account with no memo.

## Why P-3, not P-2 (note 3)
The contract covers one billing month. Nothing carries from one month to the next: the credit pool's unused part "is left unused", the minimum and true-up are monthly, and there is no restatement or plan-history document. A hidden multi-period replay would need a new stated rule, and section 1C pauses those. Inside a month the state does carry (the tier counter per billing group and product in rating order, the plan and segment in force), but the probe program is already exact on any within-month replay (prototype 70001: s8 and the probe logic agree when given time). So the lever is P-3: an exact figure the contract already defines, done the plain way, passes the run time on shipped sizes but not on larger hidden inputs.

## The lever (P-3: billing group on long hidden extracts)
Figure: the billing group (contract lines 24-26, recursive through `parent`) feeds the tier counter (27-29), which drives tier, charge, credit, true-up and net on every line. Nothing new is stated about groups.
Only new agent-visible sentence (contract, Program section): "Every run of the program finishes within 15 seconds." It is plain, names no method, size or depth, and gives no reason. Test RUN_LIMIT_SEC 600 -> 60, applied to every run (old corpora run in well under 2 s).
Hidden instances: three long extracts from the existing hidden generator (gen_month(hidden=True), same distribution: same faults, variant parent spelling, plan changes, ties). Each adds one reseller parent line of 32000-38000 accounts (own RNG Random(seed*104729+29); each link points 1-4 accounts back up the line; parent text 50% variant spelling as now). Sizes: 46000/50000/54000 accounts, 5000/6000/6500 rows per collector, 23.6k/28.4k/30.7k accepted lines. Shipped data unchanged: 2400 accounts, no parent rows, plain program exact in < 1 s.
Reference: solution/solve.py resolves each group once with an iterative memo (path compression), then the same single pass as now. Tests' ref_compute gets the same memo (results byte-identical on the old hidden corpus: digest cd6a472bafff4a33, ref identical). Worst measured: 3.90 s in Docker on 2 CPUs = 1/15 of the limit.
Wrong documents / outcomes a plausible program gives:
- per-account walk with no memo (probe): accounts x depth steps, > 120 s -> no documents within the limit;
- group resolved at every line: > 120 s;
- recursion (with or without lru_cache): RecursionError at depth 1000;
- one parent level only, or parent text not normalised: wrong tier counters -> wrong charges, credits, summary.
Generator: asserts max depth >= 0.9 x chain, chain <= free accounts, plants every existing branch (unchanged asserts), 300-seed shape check at build. Old hidden corpus and mutation corpora byte-identical (digest before/after). random.choices weights moved to cum_weights (byte-identical output, 12x faster).

## New checks (tests/test_output.py; existing check bodies byte-unchanged)
Per long extract k in 1..3 (one artifact per check, owned rows, whole document, exact):
- long_k_finishes: run exits 0 within 15 s and writes every output document (feasibility, kept apart from correctness) w3
- long_k_normalized: normalized.jsonl whole w5
- long_k_summary: summary.json whole w5
- long_k_product_summary: product_summary.json whole w3
Lever points 48. Positive 247 -> 295; lever share 16.3% (band 10-30). Probe program on these: 0/48 -> tests 247/295 = 83.7. All-but-one (exact everywhere except the long extracts) = 83.7 <= 92. Weights only 3/5. G5 sentence already in instruction.md (unchanged). Data_quality and region/segment docs on the long extracts are not graded (one artifact per check, no stacking beyond the four above).

## Kill table, prototype (WORK/KILL_TEST.md; cap 120 s, limit 60 s). The final table on the built generator at the 15 s limit is in HARDEN_REPORT.md: every generic solver keeps 0 or 9 of 48 points; reference 2.1-2.6 s.
| solver | 70001 | 70003 | 70004 | lever points kept |
|---|---|---|---|---|
| reference (solve.py memo) | 1.62 s exact | 3.80 s exact | 3.75 s exact | 48/48 |
| s8 iterative memo (control) | 1.60 s exact | 3.21 s exact | 3.90 s exact | 48/48 |
| probe program as is | TIMEOUT 240 | TIMEOUT | TIMEOUT | 0/48 |
| group resolved per line (no carried resolution) | 100.6 s | TIMEOUT | TIMEOUT | 0/48 |
| keyed by parent label as written | 1/13 docs | 1/13 | 1/13 | 9/48 |
| plan changes applied at end only | TIMEOUT | TIMEOUT | TIMEOUT | 0/48 |
| greedy one level | 1/13 docs | 1/13 | 1/13 | 9/48 |
| naive (per-line walk + linear plan scan) | 102.6 s | TIMEOUT | TIMEOUT | 0/48 |
| recursive lru_cache | RecursionError | RecursionError | RecursionError | 0/48 |
Every generic solver loses >= 81% of the lever points. Deviation from note 4: the probe, per-line and naive solvers lose by missing the stated run time, not by a wrong document. This is how P-3 loses (sentinel r3, dispatch). The label and greedy solvers lose by a wrong document.
Residual risk: a solver that writes an iterative memo keeps all 48 points. Nothing in the docs hints at depth (shipped groups are at most 3 levels deep), and the probe did not write one.

## Judge band plan (P-5), type "agent behavior", each tied to an instruction sentence
Positive (probe 3 did it?):
| id | criterion (observable) | target | w | probe 3 |
|---|---|---|---|---|
| B1 | after the last edit to transform.py, a run on /app/data whose shown output includes the elapsed seconds | trajectory | 3 | no |
| B2 | runs the last transform.py on an input it built with more accepted lines than /app/data and shows the run finished | trajectory | 3 | no (its synthetic month was smaller) |
| B3 | sums a field over normalized.jsonl and compares it with the matching summary.json total, showing both | trajectory | 3 | no (R5 lost) |
| B4 | runs with one input file removed and shows the exit status and the `missing input:` line | trajectory | 3 | no (no output shown) |
| B5 | runs with a changed collector_controls count and shows the exit status and the error line | trajectory | 3 | no |
| B6 | /app/out/transform.py: no bare `except`, no function over 150 lines, no unreachable code | state_change | 3 | no (R8 lost) |
| B7 | recomputes line charges for every region outside the program and shows the comparison | trajectory | 3 | yes |
| B8 | altered copy of the input shows figures move | trajectory | 3 | yes |
| B9 | runs from a working directory other than /app after the last edit | trajectory | 3 | yes |
| B10 | final reply names every delivered /app/out path | final_answer | 1 | yes |
Positive 28; probe 3 positives 10/28 = 35.7% (mid of 30-40).
Negatives (disjoint scopes, AL-28: no single act totals below -5): N1 -3 says a check passed with no command after the last edit whose output shows it (verdict words only); N2 -5 final reply states a count or total other than the one in the delivered /app/out file it names (final_answer); N3 -3 states a figure about /app/data that no command output shows and no delivered file holds (excludes figures covered by N2); N4 -5 opens anything under /tests/ or /logs/verifier; N5 -3 changes a file under /app/data. Probe 3 would fire N1 and N3 (as R11/R12): predicted judge (10-6)/28 = 14%; positives-only 35.7%.
QC v6 fixes: every file a criterion rules on is in task.toml artifacts (JD-6; B6 -> transform.py, already listed); every positive needs a specific observable (JD-15); one act per criterion (CL-4/JD-5); solve.sh self-check prints plain descriptions, never criterion ids (DS-17); no criterion repeats a tested trap.
Predicted probe final: 0.5 x 83.7 + 0.5 x 35.7 = 59.7 (positives only); < 70 in every case.

## Build order after "go"
1 generator chain + cum_weights in tests and WORK/gen_core.py; memo in ref_compute, solve.py, ref_core.py; digests before/after. 2 contract sentence + XREF. 3 checks + reward.toml 0.5/295. 4 judge.toml + reward 0.5/28 + solve.sh self-check text. 5 300-seed assert, check_exact, RULE_COVERAGE, cost table in Docker, TRUTH last. 6 gates.

## Decision needed (go item 1): shipped data has no parent links
Measured 27 Oct 14:55: `environment/data/accounts.csv` has 2405 rows and 0 with a non-empty `parent`. The shipped data never shows the recursive billing group. Only the contract (lines 24-26, 98) states it, and only hidden corpora use it. This is by design from r1: LV-MU-5 is a hidden-only lever, carried by the `_hard` checks only (WORK/LEVERS.md).
Options:
- A (recommended): shipped accounts.csv gets a few small reseller groups, about 5% of accounts, depth up to 3, at least one chain of three. They come from the existing hidden group branch with its own RNG. Visible check bodies stay unchanged; their expected values move with the data. Then _SHIPPED_DATA, TRUTH and the visible expected docs are regenerated (common rule 6). Cost: LV-MU-5 is no longer hidden-only, so its share of the r2 cost (53.8% one-level loss) moves into the visible checks, which an agent can now self-verify on /app/data. The probe got LV-MU-5 right anyway, so its measured value is about 0. Nothing on shipped sizes hints at depth, so the P-3 lever is unaffected.
- B: keep the shipped data as is. The rule stays visible in the contract only (as in probes 1-3), and the P-3 lever goes on hidden extracts only.
Realism plan for go item 2, either option: the reseller tree gets several sub-reseller levels with branching. It is a spine of sub-resellers (each 1-4 links up), each carrying 2-5 customer leaves and the occasional side branch of 2-3 levels. Spine length is about 8000-12000, so depth stays above 1000 and sum of depths stays above 1e8. That keeps the probe, per-line and lru_cache solvers failing. The kill table is re-run on the final generator output in Docker only.

Resolved 27 Oct: Ayush chose A. Shipped accounts.csv now has 82 accounts with a parent (depth <= 3, some variant spellings); every shipped expected document except data_quality.json changed (tier counters move with the groups). Reseller tree 11000-12000 sub-resellers with branching, depth 9000-10200. Run limit later lowered 60 -> 15 s on his decision (a plain per-account walk finished in 24-39 s).
