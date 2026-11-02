# Idea card: cold-chain-backbone-quote (25 Oct 2026 16:55 IST)
Source: ChatGPT P1 v2 brainstorm, idea 2 of 6 (`prompts/issued/20261025_newbuilds/P1_reply.md:41-71`). Ayush 25 Oct chose '2' (= build ideas #2 and #1). Archetype repo-patch, category optimization.

## Master gate notes (these override the idea text where they differ)
- G-1 Difficulty source = computational core (exact node- and edge-weighted Steiner network along a stated corridor order with span bound 4). It is NOT a stated-rule habit lever; every stated-rule lever we built leaked (98-100 tests). Every rule is stated plainly and completely in the contract.
- G-2 Repo: the shipped package solves the problem with a plausible heuristic (terminal shortest-path MST or greedy attach) plus a few honest parser and report defects. Its own visible tests pass on small near-tree samples. The heuristic is a bug only because the contract says the quote is the minimum-cost network; say that once in the contract, plainly.
- G-3 Ties: the contract states the full tie order (edge bit vector, then site bit vector, as in the idea), but every shipped and hidden instance must have exactly one optimal network. The reference solver counts optimal networks; keep only seeds with count 1. Record that count per instance in WORK.
- G-4 Seeds are kept only if terminal-MST, greedy attach and Dreyfus-Wagner-in-time all fail them: either a wrong cost, or DW blows the stated runtime limit at that terminal count. Record per-baseline loss in COST_TABLE.
- G-5 Volume (A5) comes from many instances: ship a quote book of many corridor projects across the full stated size range, some at the maximum. Do not make one huge instance. Hidden books come from the same generator with denser shared-relay structure (same distribution, stated bounds).
- G-6 Stated limits (sites, edges, terminals, span, seconds per project) live in the contract. Tests run the patched package from the zip, never from /app/repo, under that limit.
- G-7 W11: no optimal cost, expected network or claimed minimum anywhere in environment/ (including failing_tests.log and README). Dispute or customer quotes may appear only if they are not the answer.
- G-8 IN-17: no sentence says the heuristic is wrong, that ties never occur, or that sharing relays matters.
- G-9 Biggest risk (ChatGPT): frontier connectivity code is easy to get subtly wrong. check_exact.py must compare against exhaustive enumeration on every small generated instance (<= 14 edges) and a second exact method (e.g. Dreyfus-Wagner with node costs) on mid-size ones.

## Idea text (verbatim from ChatGPT)
### 2. Cold-chain telemetry backbone

1. **Title and pitch.** *Refrigerated Corridor Backbone* — install the cheapest connected telemetry network across a depot, mandatory cold rooms, optional relay sites, and quoted conduit links.

2. **Setting.** A warehouse engineering team needs a defensible minimum installation quote. Shared conduit and relay costs make individually cheapest connections misleading.

3. **Archetype and outputs.** **repo-patch.** Repair the supplied solver repository and deliver `out/patched-repo.zip`. `repair-report.json` describes the repair; `module_core.json` gives the selected network and cost; `module_parser.json` records accepted inputs; `module_report.json` gives site and corridor totals; `test_fixes.json` reports the prescribed regression cases; `summary.json` states the minimum quote.

4. **Computational core.** Select edges \(x_e\) and optional relay activations \(y_v\). The depot and all mandatory cold rooms must be in one connected component; selecting an edge activates its endpoints. Minimize \(\sum c_ex_e+\sum a_vy_v\), with positive integer costs. Ties compare the edge-selection bit vector over sorted edge IDs, then the optional-site bit vector, both with `0<1`. Non-depot vertices have a stated corridor order, and every non-depot edge spans at most four positions. An expert uses a left-to-right frontier DP: state records which frontier vertices are selected and their connectivity partition, always retaining the depot. A component may disappear from the frontier only if it is already joined to the depot. Costs are charged when an edge or site is introduced.

5. **Why plausible approaches fail.** Greedy connects each terminal to its cheapest current route, paying repeatedly for links that a shared relay could replace. Local edge swaps cannot discover a solution needing a new relay and several simultaneous link changes. Time-limited enumeration returns an expensive tree. The likely “smart” attempt, a minimum spanning tree on terminals after pairwise shortest-path distances, loses shared nonterminal costs. Sample corridor graphs are nearly trees, so those methods agree with the optimum.

6. **Instance design.** Samples: 7–10 sites, 9–14 quoted edges, width at most two. Hidden: 38–52 sites, 65–95 edges, up to 18 terminals, span bound four; limits are 52 sites, 95 edges, 60 seconds. The same ordered-corridor generator adds local links and occasional depot links. Hidden draws have more overlapping relay alternatives and shared trenches. The author gates seeds against the terminal-MST heuristic and validates the exact frontier result against exhaustive enumeration on small draws. Target exact runtime is under 12 seconds.

7. **Input files.** Eight files: `repo.zip` (broken multi-module Python repository); `sites.csv` (~52 ordered sites and roles); `layout.tsv` (corridor positions referenced by sites); `links.jsonl` (~95 quotes referencing endpoint IDs); `terminals.tsv` (~18 mandatory site IDs); `access_rules.toml` (permitted corridor classes); `activation.ini` (relay activation charges by site class); `contract.json` (depot ID and requested report groups). Every file changes either the feasible graph, its costs, or a graded report.

8. **Checks.** **40 independent weighted checks.** Four fresh instances each have six whole-document JSON checks, one network-feasibility check, one independent cost recomputation, and one patched-package functional rerun: 36 checks. Four rejection cases complete the set. `module_core.json` and `summary.json` are heavy optimum checks. Feasible but more expensive networks retain feasibility and parser credit.

9. **Rejection paths.** Duplicate site → `E_DUP_SITE`; edge endpoint absent → `E_UNKNOWN_ENDPOINT`; non-depot edge exceeds the stated span bound → `E_BAD_SPAN`; no depot-to-all-terminals network exists → `E_NO_NETWORK`.

10. **Reviewer checks.** The log should explain: (1) the connectivity invariant; (2) why the stated order bounds the frontier; (3) its frontier state; (4) when site charges are paid; (5) when edge charges are paid; (6) why a disappearing unjoined component is invalid; (7) how positive costs eliminate useless detached components; (8) tie propagation; (9) a small-graph exhaustive comparison; and (10) a hidden-sized runtime measurement.

11. **Shortcuts and cheats.** Fresh graph labels and quote values defeat fixed-site answers. Shuffling input rows defeats row-position logic. Hidden tests import and run the patched ZIP on new graphs. A connected but costly network passes feasibility and fails the heavy minimum-cost checks.

12. **Expected scores.** Lazy: **10–20%**, mainly parser and rejection work. Careful: **25–45%**, with valid networks from shortest-path or MST-based methods. Expert: **100%**, with frontier partitions and ties.

13. **Nearest known problem.** This resembles [Steiner tree on bounded-width graphs](https://arxiv.org/abs/2302.14128). Here activation costs, an explicitly supplied corridor order, depot links, archive repair, and a total-order output contract change both the recurrence and the deliverable; recognizing “Steiner tree” alone does not supply the required program.

14. **Solvability.** The depot plus four recent sites leaves a small partition frontier. Canonical partition labels make memoization practical in Python. The supplied ordering removes the need to discover a tree decomposition.

15. **Biggest risk.** Frontier connectivity code is easy to get subtly wrong. The author should independently enumerate every small generated graph and reject any seed whose optimal network has an unstated tie.
