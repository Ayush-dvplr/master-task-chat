# ChatGPT reply to P1_ideas.md (paste the full reply below this line)

The six proposals below are author-facing designs. Each shipped instruction would state the rules, size limits, runtime limit, rejection messages, and exact grading contract, but would omit the discussion of failure modes and hidden-instance construction in fields 5 and 6.

For all six, report schemas and serialization are specified in the shipped spec: sorted JSON keys, compact separators, UTF-8, and one final newline; JSONL has a specified row order. Every generated report document is compared whole on fresh inputs. Program and ZIP artifacts are rerun on those inputs. The author computes expected answers offline with an exact implementation, cross-checks small cases exhaustively, and checks feasibility separately from optimality. Each rejection uses exit code 2, the stated single-line stderr message, and no output files.

## Operations research

### 1. Two-lane cleanroom maintenance schedule

1. **Title and pitch.** *Cleanroom Window Book* — choose and assign optional maintenance jobs to two qualified cleanroom lanes to maximize net contract value across fixed service windows.

2. **Setting.** A pharmaceutical plant planner uses it to commit overnight maintenance. An overstated optimum can cause a contract to be accepted when a better, feasible schedule existed.

3. **Archetype and outputs.** **domain-calculation.** `out/derive_report.py` is the reusable solver. `summary.json` contains the selected jobs, lane assignments, and net value; `policy_audit.json` explains qualification and overlap compliance; `data_quality.json` records validated inputs. The four `region_*.json` and two `segment_*.json` files aggregate the chosen jobs by client region and contract segment.

4. **Computational core.** Job \(j\) has a fixed half-open interval \([s_j,e_j)\), value \(v_j\), family \(f_j\), and eligible lanes. A job is rejected or assigned to exactly one of two lanes; intervals on a lane cannot overlap. The first job on a lane incurs a stated initial-family changeover charge, and every later job incurs the charge for its predecessor’s family and its own. Maximize selected value minus changeover charges. Ties use, in order, the acceptance bit vector over sorted job IDs with `0<1`, then the lane-ID vector, with `0` for rejected jobs. An exact dynamic programme scans jobs by start time. Its state is each lane’s release time and last family; for each state it keeps the best value and tie prefix. No earlier detail can affect future feasibility or cost.

5. **Why plausible approaches fail.** Greedy value-per-hour accepts a long attractive job that blocks a better pair and may leave an expensive family changeover. Single-job swaps cannot escape a schedule requiring two removals before three additions. Time-limited branch-and-bound can return a feasible incumbent without proving it optimal. A plausible min-cost-flow formulation handles interval capacity but omits lane-specific family transitions. The small samples have sparse overlap and one dominant family, so all four approaches appear to work there.

6. **Instance design.** Samples: 6–9 jobs, two lanes, at most two overlapping jobs. Hidden: 48–72 jobs, three families, maximum overlap 7, within a stated 72-job limit; 60 seconds per instance. The same generator places jobs in short window bands, draws values and families from the same tables, and varies the number and density of bands. Hidden draws contain coupled bands where a choice changes the last family carried into the next band. The author retains hidden seeds only after verifying that value-density greedy and the flow relaxation miss the optimum. The DP target is under 8 seconds in the reference standard-library implementation.

7. **Input files.** Ten flat files, each used by a graded result: `jobs.csv` (~72 jobs; references windows and clients); `windows.tsv` (~40 interval definitions); `bays.json` (two lanes and initial families); `qualifications.ini` (lane/family eligibility); `setup_fees.csv` (ordered family-pair charges); `clients.jsonl` (~30 client records referenced by jobs); `regions.csv` (client-to-region mapping); `segments.tsv` (client-to-segment mapping); `mandatory.json` (contract jobs that must be accepted); `audit.toml` (named report cohorts and audit thresholds). CSV, TSV, JSON, JSONL, INI, and TOML are standard-library readable.

8. **Checks.** **45 independent weighted checks.** On each of four fresh instances: nine whole-document checks, one for each JSON report, plus a separate selected-plan feasibility check (40). `summary.json` and the six group reports are heavy optimum-dependent checks; `data_quality.json` and feasibility retain partial credit. Four distinct rejection checks and one reusable-program rerun complete the set. The feasibility checker independently recalculates overlap, eligibility, mandatory jobs, and value; the optimum checker compares against the offline DP result.

9. **Rejection paths.** In this priority order: duplicate job ID → `E_DUP_JOB`; missing or reversed window → `E_BAD_WINDOW`; unknown lane or family → `E_UNKNOWN_RESOURCE`; missing changeover entry → `E_BAD_FEE`. Each message includes the terminating newline.

10. **Reviewer checks.** The work log should explain: (1) its mathematical objective; (2) why release time and last family suffice as state; (3) how mandatory jobs enter transitions; (4) why half-open windows allow touching jobs; (5) how initial-family charges enter; (6) why qualifications are checked before assignment; (7) how tie prefixes are retained; (8) an exhaustive comparison on at least one small instance; (9) a measured runtime near the stated maximum; and (10) how the same program handles unseen job IDs and values. These assess reasoning, not another output value.

11. **Shortcuts and cheats.** Fresh IDs, shuffled file rows, and changed fee tables defeat sample hardcoding or filename-specific answers. Hidden reruns require a program. Feasibility-only output earns its separate check but loses the heavy optimum-dependent documents.

12. **Expected scores.** Lazy: **15–25%**, from validation and occasional feasible plans. Careful: **30–45%**, if it implements all rules but uses a flow or bounded search. Expert: **100%**, with the exact state DP and deterministic tie handling. These are calibration targets, not claimed measured rates.

13. **Nearest known problem.** [Weighted interval scheduling](https://ocw.mit.edu/courses/6-046j-design-and-analysis-of-algorithms-spring-2012/b1e5ac3c8f7d60db9b8d5b66c40bc55e_MIT6_046JS12_Notes.pdf) is the closest textbook starting point. This task has two separately qualified lanes and predecessor-dependent charges that persist across gaps, so its usual one-dimensional recurrence is insufficient.

14. **Solvability.** Two lanes and three families keep the release-time/last-family state modest. An expert can implement the DP, parent pointers, and reports in two hours using only dictionaries, tuples, sorting, `csv`, `json`, and `tomllib`.

15. **Biggest risk.** The state space may be easier than intended. Before shipping, the author should measure several exact and heuristic solutions on hidden-sized draws and replace seeds where a simple heuristic is exact.

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

### 3. Picking-route batch consolidation

1. **Title and pitch.** *Multi-client Pick Wave* — partition warehouse orders into carts while jointly minimizing cart charges and exact tours through pick zones.

2. **Setting.** A fulfillment supervisor releases a pick wave serving five regions and four customer segments. A wrong partition changes labor and equipment bookings.

3. **Archetype and outputs.** **data-pipeline.** `out/transform.py` reads new waves. `normalized.jsonl` records every order’s chosen batch, cart, and tour position. `summary.json`, `data_quality.json`, and `product_summary.json` give wave totals. Five `region_*.json` and four `segment_*.json` files report order, unit, and batch membership totals.

4. **Computational core.** Each order has integer weight, volume, hazard class, and a set of pick zones. A batch is feasible under a chosen cart’s weight and volume capacities and the stated pairwise hazard matrix. Its cost is cart fixed charge plus cart-specific integer travel rate times the shortest depot-to-depot tour through the union of its zones. Partition all orders into feasible batches at minimum total cost. Ties compare the sorted list of sorted batch-member ID lists, then cart IDs, then zone tours; tour ties use lexicographically smallest zone sequence. An expert first computes exact tour cost for every zone subset with a Held–Karp-style subset DP, then computes cheapest feasible cart and tour for each order subset, then uses an anchored subset-partition DP. Anchoring each transition on the least remaining order avoids duplicate partitions.

5. **Why plausible approaches fail.** Greedy first-fit packs nearby orders until capacity fills, overlooking a costly extra tour. Single-order or batch swaps cannot cross a boundary requiring a three-way repartition. A time-limited partition search may stop at a good packing. The likely smart first attempt minimizes cart count or total volume before routing; it misses the trade between a cheap cart and zone sharing. Sparse samples have distinct easy zones and obvious carts, so these methods match the optimum.

6. **Instance design.** Samples: 4–6 orders, 4–5 zones. Hidden: 12–14 orders, 8–11 zones, three cart types; limits are 14 orders, 11 zones, 60 seconds. Both use the same generator for clustered zones, capacities, and hazard pairs; hidden draws contain denser cross-cluster sharing and tight cart capacities. The author retains seeds only where first-fit and cart-count-first lose. A reference Python implementation targets under 15 seconds.

7. **Input files.** Eleven files: `orders.csv` (~14 orders referencing clients); `order_lines.jsonl` (~45 lines referencing products and zones); `products.tsv` (~30 product weights, volumes, hazards); `zones.json` (integer distance matrix); `carts.toml` (three capacities, fees, rates); `hazards.ini` (pairwise compatibility); `clients.csv` (~14 region/segment codes); `regions.json` (five region names); `segments.tsv` (four segment names); `wave_policy.toml` (depot and permitted carts); `product_groups.csv` (product report grouping). Each participates in feasibility, cost, normalized rows, or a group report.

8. **Checks.** **47 independent weighted checks.** Three fresh waves each receive 13 whole-document checks—JSONL plus the 12 JSON reports—and a separate batch/tour feasibility check: 42 checks. Four rejection cases and one program rerun bring the total to 47. `normalized.jsonl` and `summary.json` are heavy optimum checks; quality and some product totals remain available for partial credit.

9. **Rejection paths.** Unknown product or zone → `E_UNKNOWN_ITEM`; asymmetric or negative zone distance → `E_BAD_DISTANCE`; hazard pair absent → `E_BAD_HAZARD_TABLE`; any order that fits no permitted cart alone → `E_NO_BATCH`.

10. **Reviewer checks.** The log should explain: (1) batch feasibility; (2) exact route recurrence; (3) reuse of zone-subset tour costs; (4) order-subset cost construction; (5) why anchored partitioning is complete; (6) cart selection; (7) route tie handling; (8) partition tie handling; (9) a small-wave exhaustive comparison; and (10) the measured 14-order runtime.

11. **Shortcuts and cheats.** Fresh products, orders, zones, and distance matrices defeat fixed batches. Reports are recomputed from hidden waves. A valid partition without optimal routes passes feasibility but loses tour and optimum documents.

12. **Expected scores.** Lazy: **15–25%**, from normalization and feasible first-fit batches. Careful: **25–45%**, with correct constraints but approximate batch choice. Expert: **100%**, using both subset DPs.

13. **Nearest known problem.** The closest setting is [warehouse order batching coupled with picker routing](https://doi.org/10.1287/ijoo.2021.0066); the inner recurrence resembles the original [subset DP for sequencing problems](https://doi.org/10.1145/800029.808532). This task fixes small exact limits, multiple cart tariffs, hazard compatibility, and a complete tie order so neither a routing-only nor a bin-packing-only solution suffices.

14. **Solvability.** At 14 orders, anchored partition enumeration is about \(3^{14}\) candidate subset transitions before feasibility pruning; 11 zones keep tour DP small. Both fit standard-library bitmasks and integer arrays.

15. **Biggest risk.** The nested optimization might exceed 60 seconds in an unoptimized Python implementation. The author should benchmark worst-density seeds and reduce the stated maximum if the reference exact solver lacks margin.

## Systems

### 4. Write-ahead-log page recovery

1. **Title and pitch.** *Warehouse Controller Restart* — repair a Python recovery package that reconstructs durable counter pages after a crash using disk page LSNs, transaction chains, and compensation records.

2. **Setting.** A storage-engine team needs the exact post-restart image before accepting new writes. An incorrect page value can persist after the system resumes.

3. **Archetype and outputs.** **build-repair.** `out/package.zip` is the repaired reusable package. `selftest.json` records prescribed fixture results; `build_report.json` records import and packaging status; `module_core.json` gives recovered pages; `module_metrics.json` gives deterministic redo/undo counts; `dependency_resolution.json` gives transaction status and undo chain order; `summary.json` gives checksums and totals.

4. **Computational core.** Each log record has increasing LSN, transaction ID, page ID, predecessor LSN, and one of update, commit, abort, end, or compensation operations. An update adds an integer delta; its compensation adds the inverse and carries an `undoNext` pointer. Disk pages contain values and pageLSNs from independently timed flushes. The specified recovery computes active loser transactions, redoes each applicable update or compensation when its LSN exceeds that page’s disk pageLSN, then processes loser chains in descending LSN order, skipping compensation records via `undoNext` and undoing original updates exactly once. The required result is the exact recovered page vector and prescribed audit sequence. An expert keeps an LSN index, per-transaction status and predecessor links, per-page LSNs, and a max-heap for undo. The process is linear in log records apart from heap operations.

5. **Why plausible approaches fail.** Greedy “keep committed updates” ignores physical pages that already contain loser writes. Adjusting a wrong final page locally cannot infer which earlier records must be redone first. A time-limited chain walk leaves some losers partly undone. A smart reverse scan of all uncommitted updates double-undoes work already represented by compensation records. Samples have no interleaved flushes and only one short loser chain, so these methods appear correct.

6. **Instance design.** Samples: 20–35 records, 4 pages, one crash. Hidden: 500–1,200 records, 12–24 pages, 8–16 transactions, several flushed page generations and partially rolled-back losers; limits are 1,200 records, 24 pages, 60 seconds. The same transaction/flush generator produces both, with sample density restricted to low interleaving. Hidden seeds are gated against a commit-filter replay and reverse-undo baseline. Exact recovery should take under 3 seconds; complexity, not log size, is the barrier.

7. **Input files.** Eight files: `package.zip` (faulty recovery package); `journal.jsonl` (~1,200 linked records); `disk_pages.bin` (binary page values and pageLSNs); `page_map.ini` (~24 page IDs and binary offsets); `checkpoint.toml` (analysis and redo starting LSNs); `txn_catalog.csv` (transactions active at the checkpoint); `shards.tsv` (page-to-shard report labels); `audit_queries.json` (prescribed checksums and reported page groups). Each is needed to interpret or verify another.

8. **Checks.** **36 independent weighted checks.** Four fresh crash images each have six whole-document JSON checks, one independently checked recovered-page invariant, and one repaired-package rerun: 32. Four rejection checks complete the set. `module_core.json`, `dependency_resolution.json`, and `summary.json` are heavy; build and self-test documents provide partial credit.

9. **Rejection paths.** Duplicate LSN → `E_DUP_LSN`; unknown page mapping → `E_UNKNOWN_PAGE`; transaction predecessor or compensation `undoNext` points forward or to a different transaction → `E_BAD_CHAIN`; binary page image fails its specified checksum → `E_BAD_IMAGE`. A valid crash-truncated transaction is recoverable and is not a rejection.

10. **Reviewer checks.** The log should explain: (1) the disk-page starting state; (2) analysis of checkpoint-active transactions; (3) redo eligibility by pageLSN; (4) why loser updates can be redone before undo; (5) compensation redo; (6) compensation skip behavior during undo; (7) max-LSN undo order; (8) idempotence of a second recovery run; (9) a hand-checked short crash trace; and (10) a hidden-sized runtime measurement.

11. **Shortcuts and cheats.** Fresh LSNs, page maps, flush schedules, and loser chains defeat fixed recovered images. Hidden tests import the repaired package. A plausible committed-only image may pass import and some metrics checks but fails exact pages and checksum reports.

12. **Expected scores.** Lazy: **15–25%**, from packaging and simple replay. Careful: **25–45%**, if it handles most log rules but misses recovery phase interactions. Expert: **100%**, with analysis, redo, and undo maintained separately.

13. **Nearest known problem.** [ARIES recovery](https://www.cs.cmu.edu/~15849g/readings/mohan92.pdf) is the nearest systems precedent. This benchmark specifies a smaller additive-page model, supplied checkpoint state, a deterministic audit order, and a broken package to repair; knowing the name ARIES does not determine the exact outputs.

14. **Solvability.** The additive page model avoids ambiguous physical before-images, and all chain and checksum rules are documented. A dictionary index, heap, and byte parser suffice within two hours and the runtime limit.

15. **Biggest risk.** A hidden interaction could admit two audit orders despite one recovered image. The spec must fix undo queue ordering by descending LSN and every remaining tie by transaction ID.

### 5. Concurrent configuration history

1. **Title and pitch.** *Feature-Flag Release Witness* — repair a CLI that must find the lexicographically first legal serialization of overlapping configuration operations and emit the resulting profiles.

2. **Setting.** A release engineer investigates whether observed concurrent reads and compare-and-set responses could have come from one valid sequential configuration history. A false witness invalidates the audit.

3. **Archetype and outputs.** **cli-config.** `out/tool.zip` is the repaired CLI. `config.json` gives the final global state and the witness order; `profile_dev.json` and `profile_prod.json` give overlays after that order. `report.json`, `validation_report.json`, and `summary.json` give deterministic operation and consistency summaries.

4. **Computational core.** Each completed operation has invocation and return times, scope, key, action (`read`, `write`, or compare-and-set), and observed return value. A candidate total order must place operation \(i\) before \(j\) whenever \(i\) returned before \(j\) was invoked. Executing that order against the specified initial global/dev/prod maps must reproduce every observed return. Find the lexicographically smallest valid operation-ID sequence; its final maps and projections are unique. An expert searches ideals of the real-time partial order, trying enabled operations by ID, simulating their exact state transition, and memoizing failed `(completed-mask, complete configuration state)` pairs. The first successful path is the required witness.

5. **Why plausible approaches fail.** Greedy invocation-time order gives plausible final flags but can contradict an observed read. Adjacent-swap local search can get trapped when three overlapping operations need cyclic rearrangement. Time-limited DFS may report no witness after exploring a large wrong prefix. The likely smart first attempt checks each key independently, but cross-key profile reads and global overlays constrain one shared order. Samples contain little overlap, so timestamps happen to produce the witness.

6. **Instance design.** Samples: 5–7 operations, at most two simultaneous, two keys. Hidden: 18–22 operations, maximum concurrency six, five keys with values from a three-value alphabet; limits are 22 operations, five keys, 60 seconds. The same interval-history generator uses more overlapping operations and cross-key reads for hidden draws. Hidden histories are generated from a valid underlying order, then timestamps are widened; separate rejection cases are deliberately inconsistent. The author keeps seeds where timestamp ordering and per-key ordering fail. The memoized search target is under 10 seconds.

7. **Input files.** Seven files: `tool.zip` (broken CLI); `operations.jsonl` (~22 actions); `intervals.csv` (invocation/return times keyed by operation ID); `base.toml` (initial global/dev/prod values); `key_schema.json` (permitted keys, values, and actions); `profiles.ini` (documented overlay order); `observations.tsv` (observed operation responses). The action stream, intervals, and observations must be joined before consistency can be decided.

8. **Checks.** **36 independent weighted checks.** Four fresh histories each receive six whole-document JSON checks, a separately verified witness-validity check, and a repaired-CLI rerun: 32. Four rejection checks complete the set. `config.json`, the two profiles, and `summary.json` are heavy witness-dependent checks; validation work can still earn credit.

9. **Rejection paths.** Duplicate operation ID → `E_DUP_OP`; return time before invocation → `E_BAD_INTERVAL`; action outside the supplied schema → `E_BAD_ACTION`; well-formed history with no legal serialization → `E_NO_SERIALIZATION`.

10. **Reviewer checks.** The log should explain: (1) its real-time precedence relation; (2) the complete simulated state; (3) response matching; (4) why an enabled operation can be chosen next; (5) why the memo key is sufficient; (6) why ID-ordered search gives the required tie; (7) treatment of global overlays; (8) one small exhaustive history comparison; (9) a deliberate impossible-history check; and (10) runtime near 22 operations.

11. **Shortcuts and cheats.** Operation IDs and time coordinates change in every rerun. Hidden observations prevent emitting timestamp order. A final configuration without a valid witness earns only secondary checks; the checker replays the witness independently.

12. **Expected scores.** Lazy: **10–20%**, from parsing and simple timestamp replay. Careful: **25–45%**, from correct simulation with incomplete ordering search. Expert: **100%**, with memoized exact search.

13. **Nearest known problem.** The closest concept is [linearizability](https://www.cs.cmu.edu/~wing/publications/HerlihyWing90.pdf). This is a finite, explicitly bounded configuration-history reconstruction with profile overlays and a required lexicographically first witness, rather than a generic yes/no check of a concurrent object.

14. **Solvability.** The concurrency bound limits enabled choices; the small key/value state makes memoization effective. All operations are deterministic and fully specified, so a standard-library DFS can both prove absence and recover the first witness.

15. **Biggest risk.** Some generated histories might have too many reachable states. The author should measure explored memo states, cap concurrency as stated, and discard seeds that lack runtime margin.

### 6. Branching block-map snapshots

1. **Title and pitch.** *Snapshot Capacity Ledger* — process branching block-map updates in one pass and answer historical range queries exactly while meeting a measured speed ratio.

2. **Setting.** A storage-capacity team audits point-in-time block counters for several workload scenarios. Mutating a current array can silently corrupt earlier branch snapshots.

3. **Archetype and outputs.** **performance.** `out/optimize.py` is the reusable one-pass program. The five `scenario_*.json` files contain exact query answers for visible, peak, steady, burst, and latency streams. `perf_report.json` contains deterministic operation counts, while the harness measures the speed ratio externally. `bottleneck_analysis.json`, `recommendations.json`, and `data_quality.json` are deterministic summaries defined by the spec; none contains wall-clock timings.

4. **Computational core.** A version names a parent version and applies an integer range assignment or range addition to a fixed block array. New versions may fork from any earlier version. Queries request the sum and maximum over a half-open block range at any named version. Every result is an integer. A path-copying persistent segment tree stores sum, maximum, and composable lazy assignment/addition tags. Each update creates a root without modifying its parent; each query descends from its named root. The input event order guarantees that parents precede children. An expert processes each of five streams once, preserving all roots and answering queries when encountered.

5. **Why plausible approaches fail.** Greedy mutation of the newest array gives correct-looking current totals but changes old branches. Local corrections to failed historical queries cannot repair their common corrupted ancestor. A time-limited replay from the initial array for each query can leave late documents incomplete. The likely smart first attempt shallow-copies tree nodes but shares a mutable lazy tag or child object, producing errors only after overlapping assignment/addition on forks. Samples use mostly linear history with disjoint ranges, so those mistakes are invisible.

6. **Instance design.** Samples: 24–64 blocks and 30–50 events per scenario. Hidden: 2,048–4,096 blocks, 1,500–2,500 updates and 400–800 queries per scenario; limits are 4,096 blocks and 3,300 total events per scenario, 60 seconds per instance. The same generator draws parent versions, range lengths, and update types; hidden draws have deeper forks and more overlapping ranges. Hidden seeds are gated against mutable-current and shallow-copy baselines. The exact implementation should finish all five streams under 10 seconds and beat the bundled full-array-copy reference by at least **5×** on the specified benchmark machine.

7. **Input files.** Twelve files: `baseline.bin` (initial 4,096 integer blocks); `layout.toml` (binary layout and block range); `labels.tsv` (block groups); `scenarios.json` (five stream definitions); `events_visible.jsonl`, `events_peak.jsonl`, `events_steady.jsonl`, `events_burst.jsonl`, `events_latency.jsonl` (updates and version creation); `queries.csv` (versioned ranges across streams); `thresholds.ini` (deterministic recommendation bands); `reference.py` (specified full-copy speed baseline). All affect answers, reports, validation, or the measured performance check.

8. **Checks.** **48 independent weighted checks.** On four fresh input sets, nine whole-document JSON checks, one measured speed-ratio check, and one reusable-script rerun give 44 checks. Four rejection checks complete the set. The five scenario documents and speed checks carry the heaviest weights. Data-quality and analysis documents can be correct even if some historical answers are wrong.

9. **Rejection paths.** Duplicate version ID → `E_DUP_VERSION`; unknown or not-yet-created parent → `E_BAD_PARENT`; range outside the declared block extent → `E_BAD_RANGE`; baseline binary checksum mismatch → `E_BAD_BASELINE`.

10. **Reviewer checks.** The log should explain: (1) snapshot immutability; (2) lazy assignment/addition composition; (3) sum maintenance; (4) maximum maintenance; (5) copy-on-write boundaries; (6) parent-root selection; (7) historical query traversal; (8) one small exhaustive array comparison; (9) deterministic report calculations separated from timing; and (10) the measured ratio and runtime on the stated benchmark shape.

11. **Shortcuts and cheats.** Hidden parent graphs, block values, ranges, and query versions defeat sample answers. Reordering events changes valid parent availability. A full-copy program can earn exact scenario documents but loses the independently weighted speed checks; a fast mutable program loses historical documents.

12. **Expected scores.** Lazy: **15–25%**, from current-version answers and secondary summaries. Careful: **25–50%**, from either correct but slow copying or fast but flawed sharing. Expert: **100%**, with persistent lazy range updates.

13. **Nearest known problem.** The closest foundation is [persistent data structures](https://www.cs.cmu.edu/~sleator/papers/making-data-structures-persistent.pdf). This task combines branching version creation, two composable range-update types, historical sum/max queries, deterministic scenario reports, and a separately measured performance contract.

14. **Solvability.** A range operation touches \(O(\log 4096)\) copied tree nodes, so the stated event counts are modest for Python. The supplied slow reference establishes a reproducible ratio without third-party packages or nondeterministic timing fields in the required documents.

15. **Biggest risk.** A speed ratio can vary by host. The author should benchmark both programs on the actual grading machine, use multiple timed repetitions with a stated median rule, and set the 5× threshold only if the exact reference clears it comfortably.