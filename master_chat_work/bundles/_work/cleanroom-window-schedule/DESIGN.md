# DESIGN 3040f47 cleanroom-window-schedule (domain-calculation, optimization, seed 666278)

## 1. Core (G-1, changed under G-2)
A book of nights; each night has jobs with fixed half-open minute intervals [start, end) inside [0, 1440).
Three cleanroom bays; each bay is qualified for a subset of the 3 product families (qualifications.ini)
and has a minute rate (bays.json). A plan picks the jobs that run and one qualified bay for each; jobs on
one bay never overlap (touching allowed). Mandatory jobs (mandatory.json) must run.
Changeover: when a job's family differs from its bay's previous family, the night pays
fee(prev, next) and the shared sterilisation crew works a window [start - crew_minutes(prev, next), start)
on that bay (setup_fees.csv, per night table). The bay must have finished its previous job by the window
start; the window must start at or after minute 0; the one crew works one window at a time (windows on
all bays pairwise disjoint, half-open). Previous family = family of the last job the bay ran in the book,
in night date order (audit.toml); a bay that has run no job holds its bays.json initial family.
Net value = sum(value) - sum(minute_rate x job minutes) - sum(changeover fees). A night's plan is its
maximum-net-value plan. Contract carries the coupling sentence verbatim: "Every reported figure of a
night is computed from its maximum-net-value plan." Tie order stated (acceptance bit vector over job ids
sorted ascending, 0 before 1, then bay index vector), but the generator keeps only nights with exactly
one optimal plan. Contract states every accepted night admits a plan that runs all its mandatory jobs.

Why G-2 fired: without the crew, the joint sweep DP (state = per-bay last family + busy job) is exact and
fast; with the crew, a bay's state needs its end time relative to the next possible window (lead time)
plus the crew release time. Correct state collapse: an end time or crew release <= s - max_crew_minutes
behaves as "free" (reference does this; 0.05-0.33 s per 72-job night). Exact DP keyed on raw end times:
1-25 s and >30 s on largest hidden nights (not a lever, recorded only).

## 2. Levers (no secondary lever)
| lever | rule | wrong implementation(s) | measured on hidden books (3 seeds) |
| LV-CW-1 exact max net plan | maximum-net-value plan | value-density greedy; greedy + single-swap/move local search; flow relaxation (ignore quals and crew) | greedy and LS differ on every night of every book (loss 3,791-17,835 per book) |
| LV-CW-2 previous family | last job run in the book, date order; initial family before first job | reset to initial family each night; ignore initial family (first job free); charge only touching jobs | reset differs 3-5 nights/book; noinit 1-6; touching-only infeasible on 4-8 |
| LV-CW-3 crew coupling | one crew, windows disjoint, lead time, bay idle | ignore crew (per-bay or joint DP without crew); lane-by-lane DP; collapse bay to free when job ends | nocrew differs 2-4 nights/book (infeasible); lane-by-lane infeasible every book; naive collapse 4-8 nights/book |

## 3. Data (WORK/datagen.py, stdlib, seeded 666278 -> BUNDLE/environment/data/)
jobs.csv (job_id,night_id,window_id,client_id,family,value; rows shuffled), windows.tsv (window_id,start,end),
bays.json (bay_id, minute_rate, initial_family), qualifications.ini ([bay] families=), setup_fees.csv
(night_id,from_family,to_family,fee,crew_minutes), clients.jsonl (client_id, site, tier), regions.csv
(site,region; North/South/West/East), segments.tsv (client_id, segment; commercial/public), mandatory.json
(night_id -> job ids), audit.toml (nights with date, thresholds). 10 files, 6 formats. About 340 nights,
mostly 4-12 jobs, about 20 nights up to 72 jobs; >= 2k rows in every csv/tsv/jsonl; >= 20k lines total.
Neutral ids (DS-4): night ids N-xxxx random, job ids J-xxxxx random, not date ordered.
Planted defects (shipped and hidden): duplicate job id, missing/reversed window, unknown family or client,
missing fee pair. Night-level rejection priority E_DUP_JOB > E_BAD_WINDOW > E_UNKNOWN_RESOURCE > E_BAD_FEE;
rejected night has no plan and bays keep their families. No plan/net/rollup in environment/ (G-7, W11).

## 4. Outputs (fixed by archetype)
out/derive_report.py (reads a data dir arg or /app/data, writes out dir); summary.json (nights in date
order: status, plan rows job/bay/start/end/family/fee, gross, bay_charge, fees, net; book totals);
policy_audit.json (per night crew windows, crew minutes, end families per bay, mandatory met, flags vs
audit.toml thresholds); data_quality.json (rejected nights: id, code, message with terminating newline);
region_{North,South,West,East}.json and segment_{commercial,public}.json (per night jobs run, gross, net
attributed per job = value - bay charge - its changeover fee; totals). Integers only (no float format risk).

## 5. Tests (weights 5 core / 3 sub / 1 presence; whole-doc exact per book; G1-G12)
Visible tier, shipped book (expected computed in tests by independent reference, never shipped):
summary 5, policy 3, data_quality 3, regions 3, segments 3.
Hidden tier (embedded seeded generator, books H1 dense crew 5 nights 64-72 jobs, H2 carry 8 nights
20-48, H3 wide 6 nights 48-72, each with shuffled rows and planted defects; copied to a fresh dir, run as
uid 1000 with python -I from a foreign cwd), per book: plans feasible 3, plans optimal 5, summary exact 5,
policy 3, data_quality 3, regions 3, segments 3 = 25 x 3 = 75. Hidden share about 78% (G3 >= 30%).
Mutation (G6): delete jobs.csv -> nonzero exit and message names the file (3); run twice byte-identical (3).
Negative (G4, cheating act only): program text names /tests/ or /logs/verifier (-5).
Failure messages give first differing record (G2/G7). Generator asserts stated bounds, count == 1 per
night, and that each hidden book has a night where each wrong implementation of section 2 differs (G12,
300 seeds, branch planting per cm_family.py). Per-book timeout = 10 s x nights (stated per-night limit).
Tests reference: memoised recursion over job index with explicit crew-window list (different code from
solve.py sweep DP; TS-S13 overlap < 20%). WORK/check_exact.py third independent brute force on <= 12 jobs.
Projected cost table (P4 computes from real wrong programs): LV-CW-1 alone loses optimal+summary+rollups
on all books and visible tier (about 85%); LV-CW-2 alone loses all hidden books bar feasibility and the
visible tier (about 75%); LV-CW-3 alone loses all hidden incl. feasibility (about 90%). All-but-one overall
= 0.5 x tests + 0.45 < 70 in every case.

## 6. Judge (J1-J9, batched, five-key header)
J2 conduct x5 families ("The agent independently recomputes <figure> outside its program for every
night and compares it with the program's output", w3 each); J3 honesty negative (-3, "other than");
J4 maintainability of out/derive_report.py (w3); J6 "The response lists every night that was rejected,
each by its id" (w3); J9 altered-copy check (w3); one constraint criterion labelled instruction following.
8-10 criteria. solve.sh self-check prints `check <id> ok`.

## 7. Instruction / contract
W10: one contract file docs/cleanroom_contract.md under environment/data or app docs holding every rule,
limits (G-6: <= 72 jobs/night, 3 bays, 3 families, overlap <= 7, fees 1-500, crew minutes 1-120,
10 s per night), formats, rejection codes, tie order, coupling sentence. instruction.md: job, paths,
exactness sentence ("only an exact match of each output document counts"), seconds, online lookup
sentence. G-8: no sentence that greedy is wrong, ties never occur, or families carry across gaps.

## Lessons for the master
- G-2 coupling via a shared crew with lead time defeats both per-lane and joint per-lane-state DP while keeping a fast exact reference | no change: task specific
- per-bay rates were needed to make optima unique; record as a generator pattern | no change: IDEA G-3 already requires counting
