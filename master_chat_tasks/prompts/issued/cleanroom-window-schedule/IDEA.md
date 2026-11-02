# Idea card: cleanroom-window-schedule (25 Oct 2026 16:55 IST)
Source: ChatGPT P1 v2 brainstorm, idea 1 of 6 (`prompts/issued/20261025_newbuilds/P1_reply.md:9-39`). Ayush 25 Oct chose '2' (= build ideas #2 and #1). Archetype domain-calculation, category optimization.

## Master gate notes (these override the idea text where they differ)
- G-1 Difficulty source = computational core (exact choose-and-assign interval schedule on qualified lanes with predecessor-dependent changeover charges and mandatory jobs). It is NOT a stated-rule habit lever. Every rule is stated plainly and completely in the contract.
- G-2 MASTER'S MAIN WORRY: as written, the natural DP (per lane: release time + last family) is the first thing a careful frontier model writes, so the task may score near 100. PREMORTEM must write that DP the way Opus would. If it is exact and fast on hidden-size instances, redesign the core in Phase 0 before any file: add one stated coupling that breaks the per-lane state, e.g. a shared crew or tool count per window across lanes, a cumulative family budget over the night, or a third lane with lane-specific transitions. The goal is that the obvious state is incomplete or too slow and the exact method needs one more idea. Report the chosen coupling in DESIGN_SUMMARY.
- G-3 Ties: the contract states the full tie order, but every shipped and hidden instance must have exactly one optimal plan (the reference counts optimal plans; keep only count 1).
- G-4 Seeds are kept only if value-density greedy, single swap local search, the flow relaxation and the per-lane natural DP (if G-2 changed the core) all fail them. Record per-baseline loss in COST_TABLE.
- G-5 Volume (A5) comes from many instances: ship a book of many service nights across the full stated size range, some at the maximum. Hidden books come from the same generator with denser coupled bands.
- G-6 Stated limits (jobs, lanes, families, max overlap, seconds per night) live in the contract; tests run out/derive_report.py on fresh books under that limit.
- G-7 W11: no optimal value, chosen plan or claimed optimum anywhere in environment/.
- G-8 IN-17: no sentence says greedy is wrong, that ties never occur, or that families carry across gaps.

## Idea text (verbatim from ChatGPT)
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
