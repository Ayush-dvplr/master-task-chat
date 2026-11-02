# ChatGPT reply to P1_paste.txt (batch 2, 25 Oct 20:35). Paste the full reply below this line

All six task instructions would state that reports are compared as **whole documents on fresh inputs**, and only exact matches count. JSON comparison is structural, JSONL order is significant, and ZIP outputs are checked by their contents and behavior. Invalid inputs exit with status 2 and the specified single-line error; they produce no normal outputs. The only declared size limits are counts, integer ranges, and a 60-second runtime per instance. All scoring rules, event semantics, report schemas, and tie-breaks appear in the shipped instruction or spec.

## Operations research

### 1. Flood-defence repair portfolio

1. **Title and pitch.** *Flood-defence repair portfolio* asks an agency to choose the highest-value compatible set of repair proposals across its service areas.

2. **Setting.** Regional infrastructure planners select work before a seasonal funding deadline. An avoidable conflict can reserve the same specialist crew or permit twice; a suboptimal portfolio leaves measurable risk reduction unclaimed.

3. **Archetype and outputs.** **Domain-calculation.** `out/derive_report.py` is the reusable solver; `out/summary.json` contains the chosen proposal IDs and total benefit; `out/policy_audit.json` explains exclusions and valuation; `out/data_quality.json` counts accepted records; the four `out/region_{North,South,West,East}.json` and two `out/segment_{commercial,public}.json` files project the same globally optimal choice.

4. **Computational core.** For proposal \(i\), let \(x_i\in\{0,1\}\) and let its integer benefit \(v_i\) be derived from the shipped rate and site files. For each documented incompatibility \(\{i,j\}\), require \(x_i+x_j\leq1\). Maximize \(\sum_i v_ix_i\); among maximizers choose the lexicographically smallest sorted list of selected IDs. An expert derives the conflict graph, conditions on vertices whose removal separates it, solves the resulting components exactly with bitset search and admissible clique bounds, and combines their certified optima. The separator is discoverable from the instance, never stated as a parameter.

5. **Why naive approaches fail.** Greedy benefit ordering takes an attractive shared-crew proposal and loses the combined value of several local proposals. One- or two-proposal swaps cannot cross the exchange barrier. A time-limited global branch-and-bound returns that feasible incumbent without proving optimality. The edge-constraint LP admits fractional selections on overlapping odd cycles; rounding it yields the same attractive incumbent. Small shipped instances contain only one short conflict motif, where each approach reaches the optimum.

6. **Instance design.** Samples have 10–16 proposals; hidden instances have 90–130, with at most 160 proposals and 900 conflict records permitted. The same generator creates overlapping local proposal motifs and shared crew and permit links at every size. Larger draws connect many motifs through a few proposals and place benefit near the exchange threshold. Neither component count nor separator size is promised in the instruction. The author’s exact oracle and an independent feasibility checker establish each hidden answer before release.

7. **Input files.** Ten flat files in JSON, JSONL, CSV, TSV, INI, and text; approximate rows are sample/hidden:

   | File | Rows | Contents and dependency |
   |---|---:|---|
   | `manifest.json` | 1/1 | File order, run ID, requested reports |
   | `proposals.csv` | 16/130 | IDs, site, crew, base benefit; uses site and code files |
   | `sites.jsonl` | 12/90 | Risk classes and site premiums; used by proposals |
   | `crews.tsv` | 8/35 | Exclusive crew identifiers; used to derive conflicts |
   | `permits.csv` | 9/100 | Proposal-to-permit requirements; uses proposal IDs |
   | `exclusions.json` | 8/300 | Explicit incompatible ID pairs |
   | `benefits.ini` | 12/12 | Integer benefit adjustments by risk class |
   | `region_codes.csv` | 4/4 | Site-to-region interpretation |
   | `segment_codes.tsv` | 2/2 | Proposal-to-segment interpretation |
   | `audit_queries.txt` | 5/20 | Required policy-audit rows; uses the resolved portfolio |

8. **Checks.** **48 independent weighted checks:** 36 whole-report checks across four hidden instances (nine JSON reports each), eight binary feasibility checks on complete selected-ID lists, and four rejection-path checks. The 28 summary, region, and segment report checks are **heavy** because an inferior portfolio changes their whole expected documents. Feasible but inferior plans can earn the feasibility checks.

9. **Rejection paths.** Unknown proposal reference: `ERROR UNKNOWN_PROPOSAL\n`; duplicate proposal ID: `ERROR DUPLICATE_PROPOSAL\n`; negative derived benefit: `ERROR NEGATIVE_BENEFIT\n`; malformed input: `ERROR INVALID_INPUT\n`. The first fault in manifest file order, then row order, determines the error.

10. **Reviewer checks.** The work log should show: (1) an integer valuation model; (2) a complete conflict derivation; (3) a feasibility check independent of the optimiser; (4) a stated global tie rule; (5) an admissible optimality argument; (6) evidence that discarded search states cannot improve the answer; (7) an exhaustive check on a small generated instance; (8) a timed fresh-input run; (9) agreement between global and projected reports; (10) no sample-ID assumptions.

11. **Shortcuts and cheats.** Hidden IDs, graph labels, rates, and motif positions are regenerated. Exact whole-report checks defeat a memorized sample; feasibility checks retain partial credit for a sound heuristic, while heavy optimum checks deny it full credit. Source inspection and a fresh renamed input run expose filename-keyed answers.

12. **Expected scores.** Lazy: **10–20%**, from valid parsing and perhaps a feasible portfolio. Careful: **25–45%**, from complete rules and good but uncertified search. Expert: **95–100%**, from decomposition and exact certificates.

13. **Nearest known problem.** This is closest to maximum-weight independent set. Its distinction is that the graph must be assembled from several business files, and exact performance depends on finding structure in the resulting instance rather than on a supplied graph-width bound or a solver call. Exact weighted-independent-set research uses reductions and stronger search bounds for this reason. [Exact Algorithms for Maximum Weighted Independent Set on Sparse Graphs](https://arxiv.org/abs/2108.12840).

14. **Solvability.** Parsing and report generation are routine standard-library work. On the generator, conditioning leaves small independent subproblems; bitsets, memoization, and integer bounds finish with margin under 60 seconds. Two hours allows implementation and a small-instance exhaustive cross-check.

15. **Biggest risk.** A generic solver may also finish quickly if the conflicts are too sparse. Pilot generation should retain only instances for which the offline optimum is certified, the intended expert solver has margin, and the natural global search misses the optimum within the limit.

### 2. Quality-release precedence repair

1. **Title and pitch.** *Quality-release precedence repair* finds the least costly set of approval-order requests to reverse before a manufacturing release.

2. **Setting.** Quality managers receive conflicting sequencing requests from plants and regulators. Reversing the wrong request carries a documented escalation cost, while the final approval order must be executable.

3. **Archetype and outputs.** **Cli-config.** The repaired `out/tool.zip` runs on fresh inputs. `out/config.json` gives the selected reversals and final order; `out/profile_dev.json` and `out/profile_prod.json` solve two documented cost profiles; `out/report.json`, `out/validation_report.json`, and `out/summary.json` provide costs, graph validation, and consolidated decisions.

4. **Computational core.** Each request is a directed arc \(e=(u,v)\) with positive integer reversal cost \(c_e\). Choose \(F\subseteq E\) minimizing \(\sum_{e\in F}c_e\) such that reversing those arcs leaves a directed acyclic graph. Ties use the lexicographically smallest sorted reversal-ID list; the reported order is the lexicographically smallest topological order of the resulting graph. Each profile has its own documented costs and optimum. An expert decomposes the directed graph into strongly connected components: cross-component arcs need no reversal. Within each component, a subset dynamic programme chooses the last task in each subset and charges arcs that point back to earlier tasks. No component-size limit is advertised.

5. **Why naive approaches fail.** Greedy cycle repair reverses the cheapest arc in each encountered cycle, paying repeatedly where one shared arc would resolve several cycles. Local arc swaps remain trapped by overlapping cycles. Time-limited search over all tasks finds a legal order but cannot certify it. A basic cycle-constraint LP gives fractional reversal weights on interlocked cycles, and naive rounding returns a costlier repair. Samples have one isolated cycle, so these methods agree.

6. **Instance design.** Samples have 6–9 tasks; hidden instances have 65–90 tasks and up to 700 requests, within stated limits of 100 and 900. The same generator builds cyclic review groups and forward intergroup requests. At larger size it overlaps cycles inside groups and adds many cross-group arcs, making the full graph look dense while retaining discoverable strongly connected structure. Hidden maximum component sizes are chosen for exact subset DP, but are not stated in the task. Both profile optima are computed offline.

7. **Input files.** Eight flat files in ZIP, CSV, TSV, INI, JSON, and text:

   | File | Rows | Contents and dependency |
   |---|---:|---|
   | `tool.zip` | 8/8 members | Repairable CLI and its parser/report modules |
   | `tasks.csv` | 9/90 | Task IDs and division codes |
   | `requests.tsv` | 14/700 | Directed requests and cost-class IDs; uses tasks |
   | `cost_rules.ini` | 10/10 | Integer class costs |
   | `profile_dev.json` | 1/1 | Documented class overrides |
   | `profile_prod.json` | 1/1 | Different documented overrides |
   | `divisions.csv` | 5/12 | Division names used in validation and reports |
   | `run_manifest.txt` | 6/6 | Input order, requested profiles, output contract |

8. **Checks.** **45 independent weighted checks:** five hidden instances × six whole JSON reports = 30; five plan-legality checks; five repaired-archive behavior checks; five rejection checks. The 15 `config` and profile document checks are **heavy** and require exact minimum-cost reversal sets, including ties.

9. **Rejection paths.** Missing task endpoint: `ERROR UNKNOWN_TASK\n`; duplicate request ID: `ERROR DUPLICATE_REQUEST\n`; nonpositive reversal cost: `ERROR INVALID_COST\n`; invalid ZIP member path: `ERROR INVALID_ARCHIVE\n`. Fault priority follows manifest order and then row order.

10. **Reviewer checks.** The log should show: (1) the directed-arc cost model; (2) why an output order is acyclic; (3) a total tie-break implementation; (4) separate costs for the two profiles; (5) a valid lower-bound or exhaustive argument; (6) an independently checked small graph; (7) inspection of the provided package; (8) a clean package rebuild; (9) a fresh renamed-input run; (10) runtime measurement at a declared-limit case.

11. **Shortcuts and cheats.** Profile costs change on hidden inputs, preventing canned reversal sets. Random task and request IDs defeat file-name lookup. A legal but costly reversal set earns legality checks but loses the heavy whole-document checks.

12. **Expected scores.** Lazy: **10–20%**, from package repair and legal ordering. Careful: **25–45%**, from correct parsing and a strong heuristic. Expert: **95–100%**, from component-wise exact optimisation.

13. **Nearest known problem.** The optimisation is related to minimum feedback arc set. It differs through two cost profiles, required repaired CLI behavior, derived reports, and the need to identify useful decomposition from data rather than receive a bounded-size component promise. Exact work on feedback arc sets explicitly exploits strongly connected components. [An Exact Method for the Minimum Feedback Arc Set Problem](https://www.mat.univie.ac.at/~herman/fwf-P27891-N32/minimum_feedback_arc_set.pdf).

14. **Solvability.** Strongly connected components take linear time to find. The hidden generator keeps each resulting exact subset calculation comfortably within 60 seconds in Python, and all other work uses the standard library.

15. **Biggest risk.** The decomposition may be too obvious to a strong agent. Pilot runs should verify that a competent general search still returns nonminimal repairs, while the component-based oracle finishes with margin.

### 3. Freight-quote consolidation

1. **Title and pitch.** *Freight-quote consolidation* chooses a minimum-cost collection of carrier quotes that covers every shipment exactly once.

2. **Setting.** A freight procurement team receives quotes for bundles of shipments. Each accepted carrier also incurs a fixed onboarding fee, so individually cheap quotes can make the final purchase more expensive.

3. **Archetype and outputs.** **Data-pipeline.** `out/transform.py` is reusable. `out/normalized.jsonl` records the selected quote-to-shipment assignments; `out/summary.json` records total cost; `out/data_quality.json` and `out/product_summary.json` audit inputs and products; the five `out/region_{central,east,north,south,west}.json` and four `out/segment_{consumer,corporate,enterprise,smb}.json` files project the single global solution.

4. **Computational core.** Let \(y_q\in\{0,1\}\) select quote \(q\) covering shipment set \(S_q\), and \(z_c\in\{0,1\}\) activate carrier \(c\). Require \(\sum_{q:s\in S_q}y_q=1\) for every shipment \(s\), and \(z_c=1\) exactly when at least one quote from \(c\) is chosen. Minimize \(\sum_q p_qy_q+\sum_cf_cz_c\), with the lexicographically smallest sorted selected-quote list breaking cost ties. An expert identifies quotes that couple otherwise separate shipment incidence components, conditions on compatible selections of those quotes, solves residual components by memoized uncovered-shipment masks while retaining used-carrier masks, then combines costs with fixed fees.

5. **Why naive approaches fail.** Greedy cost per shipment takes a cheap bridge quote that forces expensive leftovers. Local quote replacement cannot repair a whole cover exchange. Time-limited exact-cover backtracking finds a complete cover but has a weak cost bound before conditioning. A basic set-partitioning LP fractionally shares overlapping quotes and carrier fees, suggesting an unattainable low-cost combination. The small samples have no competing bridge-cover pattern.

6. **Instance design.** Samples contain 12–18 shipments and 20–35 quotes; hidden instances contain 60–85 shipments and 180–320 quotes, within limits of 100 and 450. The same generator produces local quote families, occasional cross-family quotes, and carrier fees. More families make cross-family decisions consequential without adding a hidden rule. The offline author uses an exact solver and separately verifies one-cover-per-shipment feasibility.

7. **Input files.** Ten flat files in JSON, JSONL, CSV, TSV, INI, and text:

   | File | Rows | Contents and dependency |
   |---|---:|---|
   | `manifest.json` | 1/1 | Run and report contract |
   | `shipments.csv` | 18/85 | Shipment IDs and order references |
   | `orders.jsonl` | 12/70 | Product, region, and segment attributes |
   | `quotes.tsv` | 35/320 | Quote IDs, carrier IDs, integer prices |
   | `quote_items.csv` | 65/850 | Quote-to-shipment membership |
   | `carriers.json` | 5/12 | Carrier identities and eligibility classes |
   | `fees.ini` | 5/12 | Fixed integer onboarding fees |
   | `regions.csv` | 5/5 | Region interpretation for orders |
   | `segments.tsv` | 4/4 | Segment interpretation for orders |
   | `embargo.txt` | 3/25 | Disallowed carrier-product combinations |

8. **Checks.** **50 independent weighted checks:** three hidden instances × 13 whole data documents = 39, six binary cover/eligibility checks, and five rejection checks. The normalized stream, total-cost summary, and nine group documents receive **heavy** weights. A feasible cover that costs too much still earns the six feasibility checks.

9. **Rejection paths.** Quote references unknown shipment: `ERROR UNKNOWN_SHIPMENT\n`; duplicate quote ID: `ERROR DUPLICATE_QUOTE\n`; quote with no shipments: `ERROR EMPTY_QUOTE\n`; shipment with no eligible quote: `ERROR UNCOVERABLE_SHIPMENT\n`. The first fault is selected in manifest file order and row order.

10. **Reviewer checks.** The log should show: (1) exact-cover constraints; (2) fee activation semantics; (3) eligibility filtering before optimisation; (4) an integer cost calculation; (5) a tie-break definition; (6) a complete-cover verifier independent of search; (7) a justification for state merging; (8) a small exhaustive comparison; (9) a fresh-input runtime; (10) reconciliation of global and group totals.

11. **Shortcuts and cheats.** Regenerated shipment IDs, quote memberships, and fees invalidate sample answers. Hidden checks compare every selected assignment, not only the total. Feasibility receives separate credit so emitting any cover cannot masquerade as an optimum.

12. **Expected scores.** Lazy: **10–20%**, for normalization and a cover. Careful: **25–45%**, for valid but costly covers and correct ancillary reports. Expert: **95–100%**, for exact conditioning and component combination.

13. **Nearest known problem.** It is closest to minimum-cost exact cover or set partitioning. Carrier activation fees and cross-family quotes couple covers that a plain exact-cover routine could otherwise solve separately; the useful split must be inferred from the incidence data. Exact-cover research likewise distinguishes plain search from representations that reuse subproblem results. [Dancing with Decision Diagrams: A Combined Approach to Exact Cover](https://ojs.aaai.org/index.php/AAAI/article/view/10662).

14. **Solvability.** Quote membership fits Python integer bitsets. Enumerating the generated cross-family decisions, caching residual cover states, and combining small carrier masks runs with margin under 60 seconds; no external solver is needed.

15. **Biggest risk.** If fixed fees or cross-family quotes are too weak, ordinary exact-cover search may become exact quickly. Keep only piloted instances with certified optimality, a clear heuristic gap, and comfortable expert runtime.

## Systems

### 4. Warranty-reserve ledger replay

1. **Title and pitch.** *Warranty-reserve ledger replay* reconstructs claims, reserves, payments, and audit checkpoints after corrections and reversals arrive.

2. **Setting.** A warranty administrator must publish an exact reserve position by region and customer segment. A corrected early claim event can change the status of later payments and the account that owns the remaining reserve.

3. **Archetype and outputs.** **Domain-calculation.** `out/derive_report.py` replays fresh logs. `out/summary.json` is the final ledger; `out/policy_audit.json` records applied and rejected business events; `out/data_quality.json` records duplicate and structural counts; four region and two segment reports contain complete projections.

4. **Computational core.** The documented state is a deterministic function \(S_k=R(E_1,\ldots,E_k)\) at each requested arrival prefix \(k\), with all money in integer cents. Business events open a claim, adjust its reserve, pay against it, transfer its owning account, close it, or reopen it. Duplicate `(producer,event_id)` deliveries with identical payload have no second effect. A correction replaces the payload of its named business event at that event’s original position; the latest correction present at prefix \(k\) wins. A void permanently suppresses its target even if a later correction arrives. At each prefix, effective business events replay in original positions: a payment exceeding available reserve and a close with nonzero reserve are recorded as rejected, have no state effect, and do not stop later events. A change to an early effective event can therefore change downstream acceptance, account ownership, and all projections. The expert implementation separates event identity, effective payload, and materialized state, then replays affected prefixes or uses dependency-aware invalidation.

5. **Why naive approaches fail.** Greedy application adds a correction’s delta to the current balance and mishandles an already voided target. A local patch adjusts one claim total but leaves later rejected payments and transfers unchanged. A time-limited replay from the latest checkpoint inherits a checkpoint built under the old event payload. A plausible “smart” incremental ledger treats rejection decisions as permanent, so it reports a payment as rejected after a correction makes it valid. Isolated shipped examples exercise each rule without this cascade.

6. **Instance design.** Samples contain 20–50 events each and isolate duplicate delivery, correction, void, transfer, payment rejection, and close/reopen. Hidden logs contain 600–1,200 events within a stated 1,500-event limit, but only a modest number of claims; difficulty comes from references converging on the same claims, not raw volume. The same event templates and rules generate both, with more cross-references at larger size. Eight checkpoints are requested; a full clean replay for each is still below 60 seconds.

7. **Input files.** Ten flat files in JSON, JSONL, CSV, TSV, INI, and text:

   | File | Rows | Contents and dependency |
   |---|---:|---|
   | `manifest.json` | 1/1 | File order, checkpoint and output contract |
   | `claims.csv` | 8/90 | Claim IDs and contract IDs |
   | `contracts.json` | 8/70 | Product and coverage codes |
   | `accounts.tsv` | 7/45 | Account-to-region ownership |
   | `segments.csv` | 2/2 | Contract-to-segment interpretation |
   | `events.jsonl` | 50/1,200 | Arrival-ordered business and control events |
   | `producer_keys.csv` | 3/15 | Producer namespace interpretation for event IDs |
   | `policy.ini` | 12/12 | Valid event transitions and reserve rules |
   | `reserve_codes.tsv` | 8/8 | Adjustment reason-to-effect mapping |
   | `checkpoints.txt` | 5/8 | Prefixes for audit projections |

8. **Checks.** **50 independent weighted checks:** four hidden inputs × nine whole JSON reports = 36; eight binary cross-report ledger-invariant checks; six structural rejection checks. The summary and six group reports account for 28 **heavy** checks. A single wrong early acceptance decision changes whole later documents.

9. **Rejection paths.** Conflicting payload for an existing producer/event ID: `ERROR EVENT_ID_CONFLICT\n`; correction or void naming an unknown ID: `ERROR UNKNOWN_EVENT\n`; unknown claim or account: `ERROR UNKNOWN_REFERENCE\n`; malformed event: `ERROR INVALID_EVENT\n`. Business events rejected by the reserve state are audit outcomes, not fatal input errors. Fatal faults use manifest order and then arrival order.

10. **Reviewer checks.** The log should show: (1) arrival order as the replay order; (2) producer-scoped identity; (3) a separate effective-event representation; (4) correction at the target’s original position; (5) void precedence over correction; (6) recomputation of downstream acceptance; (7) integer-only balances; (8) an independent conservation check; (9) checkpoint reproducibility from genesis; (10) agreement of region and segment projections with the global ledger.

11. **Shortcuts and cheats.** Hidden producer IDs, claim IDs, and event order are regenerated. A final-balance-only implementation loses policy-audit and checkpoint documents. A program that handles each semantic alone fails dense hidden chains, while whole-document grading prevents partial field credit.

12. **Expected scores.** Lazy: **10–20%**, from parsing and simple claims. Careful: **30–50%**, from all isolated rules but one faulty interaction. Expert: **95–100%**, from prefix-correct replay and coherent projections.

13. **Nearest known problem.** It resembles event-sourced accounting with compensating events. Its benchmark core is the precise interaction of replacement-at-original-position, permanent voids, and downstream state-dependent rejection, rather than the prior replica-desynchronization task’s first-divergence search. Event-sourcing guidance describes replay and compensating events but leaves application semantics to the system’s contract. [Microsoft’s Event Sourcing Pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/event-sourcing).

14. **Solvability.** A correct from-genesis replay at eight checkpoints is fast for 1,500 events. Python’s standard library suffices, and independent conservation checks give the agent a practical way to validate the implementation in two hours.

15. **Biggest risk.** Ambiguity about whether a corrected event moves in time would make the task unfair. The shipped spec must say explicitly that its position never changes and include isolated sample fixtures for that rule.

### 5. Batch-worker scheduler reconstruction

1. **Title and pitch.** *Batch-worker scheduler reconstruction* repairs a scheduler package and reproduces exact job states, worker occupancy, and dependency outcomes from its event history.

2. **Setting.** A data-processing operator audits billed worker time and failed jobs after preemption, retries, lease expiry, and priority changes. The final state must explain every consumed attempt.

3. **Archetype and outputs.** **Build-repair.** `out/package.zip` contains the repaired reusable package. `out/selftest.json` and `out/build_report.json` document its clean run; `out/module_core.json` contains replayed job and worker state; `out/module_metrics.json` contains integer work and attempt totals; `out/dependency_resolution.json` contains dependency outcomes; `out/summary.json` joins them.

4. **Computational core.** Jobs have integer remaining work, priority, pool, dependencies, retry limit, and attempt token. Events submit, reprioritize, heartbeat, fail, cancel, advance time, or change worker availability. Between external timestamps, the engine processes scheduled completions, lease expiries, and retry-ready times in time order. At a shared timestamp, the stated order is completion, expiry, retry-ready, external event, then dispatch. Dispatch chooses the highest-priority eligible job, with job ID as the total tie-break; a strictly higher-priority arrival may preempt the lowest-priority running job, preserving its remaining work and attempt. Failure or lease expiry consumes an attempt; preemption does not. Late events carrying an old attempt token are ignored and audited. Successful completion unlocks dependents; cancellation follows the documented dependency cascade. Identical event-ID redeliveries are idempotent. An expert uses an event calendar and explicit job, attempt, and worker states, with a replay invariant after every transition.

5. **Why naive approaches fail.** Greedy timestamp processing handles all events at the new time before a completion that occurred between timestamps, dispatching the wrong job. A local correction to a retry count leaves worker occupancy and dependent readiness wrong. A time-limited replay starting at the last textual “snapshot” carries a stale attempt token forward. A plausible smart first attempt models preemption as failure, so it exhausts retry limits early and changes all subsequent dispatches. Shipped examples exercise each transition alone.

6. **Instance design.** Samples have 8–15 jobs and 25–60 events. Hidden inputs have 80–140 jobs and 500–1,000 events, under declared limits of 160 jobs and 1,200 events. The same generator places arrivals, duration completions, lease deadlines, and retries; larger instances create more coincident times and dependency links. This is an interaction-density task: an event-calendar replay remains well within 60 seconds.

7. **Input files.** Nine flat files in ZIP, JSON, JSONL, CSV, TSV, INI, and text:

   | File | Rows | Contents and dependency |
   |---|---:|---|
   | `scheduler.zip` | 9/9 members | Broken package and bundled sample tests |
   | `pools.json` | 3/8 | Pool capacities and eligible worker classes |
   | `workers.csv` | 5/35 | Worker IDs and pool membership |
   | `jobs.tsv` | 15/140 | Job IDs, priority, pool, retry class |
   | `durations.csv` | 15/140 | Integer work by job ID |
   | `dependencies.csv` | 10/260 | Parent-to-dependent edges |
   | `policy.ini` | 14/14 | Lease, retry, and tie-order rules |
   | `events.jsonl` | 60/1,000 | Arrival-ordered commands and tokens |
   | `checkpoints.txt` | 5/12 | Requested state and metrics points |

8. **Checks.** **45 independent weighted checks:** five hidden sets × six whole JSON reports = 30; five functional package checks; five complete-state invariants; five rejection checks. `module_core`, `dependency_resolution`, and `summary` are **heavy** because an early scheduling slip changes their complete documents.

9. **Rejection paths.** Cyclic declared job dependency: `ERROR DEPENDENCY_CYCLE\n`; unknown worker or job in an external event: `ERROR UNKNOWN_ENTITY\n`; conflicting duplicate event ID: `ERROR EVENT_ID_CONFLICT\n`; negative duration or retry limit: `ERROR INVALID_POLICY\n`. Stale but structurally valid attempt tokens are ignored-and-audited events, not fatal errors.

10. **Reviewer checks.** The log should show: (1) a documented shared-timestamp order; (2) job state and attempt identity kept separately; (3) preemption preserving work; (4) failure consuming an attempt; (5) lease expiry independent of heartbeat arrival order; (6) late-token handling; (7) dependency release only on success; (8) worker-capacity invariants; (9) an independent small replay; (10) a clean build and fresh-input timing run.

11. **Shortcuts and cheats.** Hidden runs regenerate job IDs, durations, times, and dependency edges. Returning final statuses without transition-accurate metrics fails multiple whole reports. A repaired ZIP is executed on fresh inputs, blocking a package that merely emits the shipped sample answers.

12. **Expected scores.** Lazy: **10–20%**, from build repair and basic statuses. Careful: **25–45%**, from correct isolated transitions but a wrong coincident-time interaction. Expert: **95–100%**, from a disciplined event calendar and invariant checks.

13. **Nearest known problem.** It resembles deterministic workflow-history replay: events must recreate exactly the same state and subsequent decisions. This task’s worker leases, preemption, retry tokens, and priority dispatch form a specified scheduler state machine rather than a general workflow API. [Temporal’s workflow replay documentation](https://docs.temporal.io/workflows).

14. **Solvability.** An event heap and ordinary dictionaries process the declared limits easily in Python. The challenge is maintaining the specified transition order, which can be tested on small independently calculated timelines before running the long logs.

15. **Biggest risk.** An unstated same-timestamp precedence would invalidate otherwise sound solutions. The spec must give one exhaustive ordering and define precisely when dispatch runs.

### 6. Controlled-procedure publication history

1. **Title and pitch.** *Controlled-procedure publication history* repairs a repository that materializes the current publishable procedure catalog from a long revision and publication log.

2. **Setting.** A regulated manufacturer must know which procedure revision was visible to each plant at each checkpoint. Earlier corrections, renames, retractions, and dependency changes can alter the published catalog without changing later event IDs.

3. **Archetype and outputs.** **Repo-patch.** `out/patched-repo.zip` contains the reusable repair. `out/repair-report.json` describes changed modules; `out/module_core.json` contains materialized revisions and publication state; `out/module_parser.json` records accepted event interpretation; `out/module_report.json` contains checkpoint catalogs; `out/test_fixes.json` records repaired bundled-test behavior; `out/summary.json` consolidates counts.

4. **Computational core.** Each document has a stable ID, immutable revision IDs, a current head, canonical path, aliases, and publication state. `PATCH` creates a revision by applying named field operations to its specified parent. `CORRECT` replaces an earlier patch operation at that patch’s original position; descendant revisions retain their IDs but are rematerialized. `RENAME` changes the canonical path while retaining the old path as an alias under the stated collision rule. `SUPERSEDE` changes the active document for a procedure code, while existing pinned references keep their original document and revision. `RETRACT` removes a document from publication; `RESTORE` restores its current head. Dependencies may pin a revision or float to the active document for a code. A publication is eligible only when its transitive dependencies resolve and remain eligible. Duplicate deliveries are idempotent. At each checkpoint the catalog is the unique result of replay in arrival order, with rows sorted by procedure code and document ID. An expert retains immutable event identity, recomputes affected revision descendants, and then recomputes publication eligibility through dependency edges.

5. **Why naive approaches fail.** Greedy in-place patching applies a correction only to the old revision and leaves descendants stale. A local fix to a renamed path leaves floating dependencies pointed at the wrong document. A time-limited replay from a cached catalog retains publications that an earlier retraction should suppress. A plausible smart first attempt resolves every dependency once at declaration time, so it mishandles later supersession while pinned references remain correct. Each shipped sample isolates one operation; hidden chains combine them.

6. **Instance design.** Samples have 8–12 documents and 30–50 events. Hidden runs have 70–110 documents and 500–900 events, within declared limits of 130 and 1,100. The same templates generate patches, corrections, aliases, dependencies, and publication events; larger runs produce deeper revision descendants and denser dependency overlap. Full replay plus affected-descendant rematerialization is under 60 seconds.

7. **Input files.** Nine flat files in ZIP, CSV, TSV, JSON, JSONL, INI, and text:

   | File | Rows | Contents and dependency |
   |---|---:|---|
   | `registry.zip` | 12/12 members | Repairable multi-layer repository |
   | `documents.csv` | 12/110 | Stable document IDs and procedure codes |
   | `base_fields.json` | 12/110 | Initial field maps by document ID |
   | `initial_aliases.tsv` | 5/45 | Starting path aliases |
   | `dependency_pins.csv` | 8/180 | Initial pinned and floating dependencies |
   | `publication_policy.ini` | 11/11 | Eligibility and collision rules |
   | `events.jsonl` | 50/900 | Arrival-ordered revision and publication events |
   | `checkpoints.txt` | 5/12 | Catalog query prefixes |
   | `manifest.json` | 1/1 | File order and required report contract |

8. **Checks.** **45 independent weighted checks:** five hidden sets × six whole JSON reports = 30; five patched-repository behavior checks; five publication-invariant checks; five rejection checks. `module_core`, `module_report`, and `summary` are **heavy**: one incorrectly rematerialized early revision changes entire later catalog documents.

9. **Rejection paths.** Patch naming an unknown parent revision: `ERROR UNKNOWN_REVISION\n`; alias collision forbidden by policy: `ERROR ALIAS_COLLISION\n`; cyclic dependency declaration: `ERROR DEPENDENCY_CYCLE\n`; conflicting duplicate event ID: `ERROR EVENT_ID_CONFLICT\n`. Fault priority is manifest file order, then event arrival order.

10. **Reviewer checks.** The log should show: (1) stable document and revision identities; (2) explicit parent links; (3) correction at the original patch position; (4) descendant rematerialization; (5) pinned versus floating resolution; (6) alias collision handling; (7) retraction and restoration semantics; (8) a transitive publication check; (9) replay from genesis at a checkpoint; (10) a clean repaired-repository run on renamed fresh inputs.

11. **Shortcuts and cheats.** Hidden document IDs, paths, patch fields, and event order are regenerated. Tests execute the ZIP on fresh logs and compare complete catalog documents, so patching only the bundled sample or emitting a final catalog without working replay loses most checks.

12. **Expected scores.** Lazy: **10–20%**, from package repair and simple revisions. Careful: **25–45%**, from correct individual operations but one stale descendant or dependency interaction. Expert: **95–100%**, from explicit provenance and replay.

13. **Nearest known problem.** It is closest to version-control history materialization and dependency-aware publication. Unlike Git’s general three-way merge, this benchmark has fully specified field operations, retroactive correction at a fixed event position, and pinned versus floating publication references; it does not ask for textual merge heuristics or the previously used persistent block-map snapshot core. [Git’s merge documentation](https://git-scm.com/docs/git-merge).

14. **Solvability.** The limits permit even a simple full rematerialization at each requested checkpoint. Standard-library graph traversal, dictionaries, CSV/JSON parsing, and ZIP handling suffice; a correct state model is the main work.

15. **Biggest risk.** “Current” could ambiguously mean current at dependency declaration or at query time. The shipped spec must define floating references as resolved at each queried prefix, pinned references as fixed, and give isolated fixtures for both.