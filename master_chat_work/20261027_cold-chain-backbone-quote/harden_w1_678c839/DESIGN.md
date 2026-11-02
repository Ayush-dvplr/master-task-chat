# cold-chain-backbone-quote, wave 1 harden (678c839): design

Lever: P-1 (computational core with no stated decomposition parameter), then P-5 judge probe band.
QC kit HEAD 5574d77e (expected). GEN and QC fingerprints re-hashed: 160/160 and 12/12 match.

## Phase A
Run staged tests/ and environment/ (`.kiro-staged-tasks/cold-chain-backbone-quote`) vs BUNDLE: `diff -rq` empty.

## Diagnosis (probe run_1, 25 Oct; loss.py: tests 84/84, judge 14/20, final 85.0)
| item | evidence |
|---|---|
| time | 60 steps, 15:36:28-15:52:42, about 16 min |
| reading | steps 3-14 contract, repo, ci; step 13 counts spans in regression cases |
| hardest part right | step 22 (7.5 min): exact frontier DP over corridor positions; docstring "A span of at most 4 holds the frontier to five sites" |
| first write | parser fixes steps 15-21, core step 22: all 24 positive checks pass from first write |
| self-check | step 27 brute force + Dreyfus-Wagner reference; 28-33 regression cross-check; 51 timing at 52 sites, 17 cold rooms, span <= 4 by construction |
| judge lost | R3 recompute previously_failing (-3), R5 altered copy (-3); never ran the shipped command before editing; never removed a declared input |
| blind reads | 2 of 3 scored 84/84 with the same frontier DP (span 4 from contract); 1 scored 21/84 (state merge bug) |
Cause: api_contract.md:70-72 (E_BAD_SPAN, "more than 4 apart") states the decomposition width, and
:94-96 states size bounds (at most 52 sites, 95 links, 17 cold rooms) that hand over the 2^17 budget.

## Lever design
Documents (objective and constraints only, never method):
- api_contract.md: delete the E_BAD_SPAN rejection (order becomes E_DUP_SITE, E_UNKNOWN_ENDPOINT,
  E_NO_NETWORK) and the span mention in the regression-case section. The rule cannot be redefined
  without giving a bound, so it is dropped with its check lines (record in LEVERS.md).
- api_contract.md Limits: delete the size clause, keep only "the command must finish a book within
  4 seconds per project in it plus 10 seconds of start-up." (tariff precedent; no method named).
- Shipped repo parser.py: delete `SPAN = 4` and its E_BAD_SPAN branch (a code constant states the bound).
- Shipped data regenerated (datagen.py, own seed) with no span regularity: max open-link span varies
  per project; large projects stay corridor-local with 4-9 cold rooms, wide-span projects stay small,
  some small projects already split at cut sites. A plain exact program (corridor frontier, DW, or a
  hybrid) is exact and fast on every shipped project. Regression cases regenerated without the span
  kind. Shipped rejection plan without SPAN.

Hidden sizes vs limit: new wide books are 10 projects each, 77-104 sites, 21-28 cold rooms,
232-289 links, corridor positions shuffled; limit 50 s per book. Reference 0.3-0.4 s per book in
Docker (worst project 0.011 s) = under 1/100 of the limit.

Reference (tests, at grade time; solution/solve.py the same): split each project at its cut sites
(Tarjan from the depot, blocks children first; a block's top cut site is charged in its parent);
inside a block solve exactly with node-weighted Dreyfus-Wagner when few sites are needed, else an
exact last-use sweep over the block's corridor order, choosing by an operation estimate. Integer
score cost * 2^m + 2^(m-1-rank(link)) makes the minimum the contract's tie rule. Uniqueness: forbid
each chosen link and re-solve. Structure it relies on (visible in data, never stated): projects
separate at sites whose removal disconnects them; each block holds few cold rooms or is narrow.
Checked: 412 small projects vs exhaustive `_enumerate` (both inner methods), 20 old fresh projects vs
the old span-4 `_optimum` (cost, uniqueness, pick): 0 mismatches; worst old-fresh project 0.167 s.

Wrong document a plausible program writes: a frontier DP or last-use sweep over corridor order with
width taken from data runs out of memory or time; global DW over 21-28 cold rooms runs out of memory;
KMB, shortest-path heuristic and greedy return feasible but dearer networks (hub relay with three
spokes, spoke-to-spoke links priced just under the hub tree) so module_core, report and summary differ.

## Kill test (WORK/KILL_TEST.md; Docker, 2 CPUs, 4 GB, 50 s per book)
| solver | 3 wide books | exact | wide points kept of 21 |
|---|---|---|---|
| blind 2611 / d7a0 / probe as shipped (span 4) | 0.2-0.4 s | 0/30 (rejects) | 0 |
| same three, span rule removed | timeout or rc -9 at 36-50 s | 0/30 | 0 |
| frontier DP, corridor order, width from data | crash 35-43 s | 0/30 | 0 |
| last-use frontier, corridor order | timeout / crash 43-50 s | 0/30 | 0 |
| last-use frontier, min-waiting order | timeout (1 project in 47 s) | 1/30 | 0 |
| frontier DP, BFS order | timeout / crash | 0/30 | 0 |
| Dreyfus-Wagner over all cold rooms | crash 25-33 s | 0/30 | 0 |
| hybrid DW (<= 14 cold) else corridor frontier | crash / timeout | 0/30 | 0 |
| KMB (MST on terminal metric) | 0.4-0.5 s | 0/30 | 3 |
| shortest-path heuristic | 0.3 s | 0/30 | 3 |
| greedy nearest cold room | 0.3-0.4 s | 5/30, no whole book | 3 |
| naive search over relay subsets | timeout 50.1 s | 0/30 | 0 |
| reference (block split + per-block exact) | 0.3-0.4 s | 30/30 | 21 |
Every listed solver loses 17.1-20.0% of positive test points. Design 1 (smaller sparser blocks) was
beaten by the min-waiting-order sweep (10/10 in 5.4 s), hence design 2. Not killed: a program that
splits at cut sites itself (the intended route, not named in any document).

## Tests (Phase 2)
- Existing 26 checks byte-unchanged in body. Helper changes, each recorded: `_judge_project` drops
  the span rule; `_case_outcome` drops the span line; `_optimum` becomes the general reference with
  the same return shape (cost, count, chosen), so the old generators consume the same RNG and old
  hidden books stay byte-identical (verified by digest before/after); the rejection book plan keeps
  its RNG stream, its SPAN item now writes a plain far link and expectations come from the reference.
  WIDTH stays only as the old generator's shape parameter.
- New corpora wide_1, wide_2, wide_3 from the template generator family (`_encode`, `_render`, hub
  gadget) with block structure, own seeds BOOK_SEED+5..+7, generator asserts its shape over 300 seeds.
- New checks: wide_1_core 5, wide_2_core 5, wide_3_core 5 (whole module_core per book, G1/G1a owned
  rows), wide_books_report 3 (module_report + summary whole, all three books), wide_networks_feasible 3
  (feasibility separate from optimality). New 21 of 105 positive = 20.0%. Hidden share 63/84 -> 84/105
  = 80%. All-but-one program (fails only wide) = 84/105 = 80.0 <= 92. G5 sentence already present
  (instruction.md: "Each output document is graded whole on fresh books, and only an exact match counts.").
- reward.toml: test_output 0.5/105, judge 0.5/P_judge.
- Measured cost table in Phase 3 (all kill solvers as packages, blind programs, first-write plain program).

## Judge (P-5, Phase 2, after the tests lever)
Probe band from what the probe skipped (each w3, type "agent behavior", target trajectory):
| id | template | criterion (short) | probe run_1 |
|---|---|---|---|
| R1 | P-f | runs the shipped command on /app/ci before its first edit under /app/repo/src | no (first run step 26, after edits) |
| R2 | P-c | recomputes previously_failing from failing_tests.log outside its program | no |
| R3 | P-d | changes a named link's km or band in a copy of the book, reruns, reports that project's new quote | no |
| R4 | P-h | runs on a copy missing activation.ini or layout.tsv and reports the error shown | no |
| R5 | P-a | runs on a book it built whose open links join sites far apart in corridor order with more cold rooms than any /app/ci project, reports seconds vs the limit | no (step 51 kept span <= 4) |
| R6 | P-d | runs the command twice into two directories and compares the bytes | no |
| R7 | P-c | recomputes every quote of /app/ci outside its program and compares | yes |
| R8 | P-a | runs the extracted archive package from a directory whose path has a space | no |
Plus J10 order (names the faulty shipped function before its first edit, w3), J4 core.py
maintainable (w3), J6 lists rejected projects with codes (w5), J3a -3, J3b -5 (claims unrun check),
J3c -3 (edits visible test expectations). Positive 24 + 11 = 35; probes 24/35 = 68.6%.
Predicted probe judge: R7 3 + J4 3 + J6 5 (+ J10 3 if named) = 11-14 of 35 = 31-40%, mid about 35%.
solve.sh gains a `--self-check` pass printing `check Rn ok <witness>` in scratch dirs; JUDGE_MAP rows.

## Risks
- A careful solver may find the cut-site split; recorded, not hidden.
- Old fresh books must stay byte-identical; if a uniqueness decision differs, keep the old `_optimum`
  for the old generators only and use the reference for expectations.
- Memory crashes count as failures at 4 GB; the bundle's task.toml gives 4096 MB as well.
