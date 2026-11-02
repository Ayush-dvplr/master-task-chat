# PLAN - district-heat-flex-procurement

Source of truth: `_work/district-heat-flex-procurement/DESIGN.md` (approved 2026-10-19).
Section 9 lists what the DESIGN leaves open or what the QC rules force me to change.
Nothing past P0 starts until those are answered.

## 1. Summaries of what I read

### Final_checklist.md
1. Bundle tree is fixed: root, `environment/`, `solution/`, `tests/` hold exactly the listed entries; `cheat/`, `tests/test_weights.json`, `tests/rubric.json` fail outright (FC-S2, FC-S16).
2. Two containers: grading runs in a fresh image built from `tests/Dockerfile`; `/app/data` does not exist there (harness fact 1).
3. Artifacts are absolute paths copied verbatim; `[verifier] environment_mode = "separate"` is pinned (harness facts 1, 2).
4. Reward: rewardkit writes `reward.json`; `reward.toml` gives each channel `0.5 / positive total` as a repr float; range -1..1, no clamp (lines 217-231).
5. task.toml template is letter-exact in table and key order; only angle-bracket values are per task; network roles pinned (`[environment]` no-network) (lines 41-106).
6. judge.toml `[judge]`/`[scoring]` header pinned (5 keys incl. `atif-trajectory`); criterion schema lives in gate 04 (lines 108-163).
7. test_output.py shape: `@criterion(description=...)` with no braces, only `workspace`, returns bool, never raises, registered once with W in {5,3,1,-1,-3,-5}; 10..35 checks; sum|neg| <= sum pos (lines 169-215).
8. test.sh and tests/Dockerfile are fixed templates (`util-linux`, `harbor-rewardkit==0.2.1`, `LITELLM_LOCAL_MODEL_COST_MAP=True`, `COPY . /tests/`) (lines 233-266).
9. Foundational F0a-F0e: no residue, data needed, work needed, no double scoring, solvable from instruction + environment (lines 477-483).
10. CL-1..CL-10: action checkers, forgery price, no copyable answers, partial credit, no hidden conventions, signposted wrong values, named paths exist in graded corpus, no oracle fallback, grading never supplies the measured value, every fact reachable (lines 485-501).

### 01_Instruction_QC.md
1. Plain everyday English; banned inflated words incl. "crucial", "robust" judged in context (Language rules).
2. No AI-tell phrases; reads like a colleague.
3. IN-1 "You have N seconds to complete this task." with N == `[agent] timeout_sec`.
4. IN-2 never name tests/, solution/, grader, checker, reward, logs, TRUTH.md; stating WHAT is judged is fine.
5. IN-5 inputs need not be described; any named path must exist.
6. IN-6 exactly one landing place per declared artifact, and nothing undeclared asked for.
7. IN-8 every graded expectation knowable from prompt, a pointed-to spec, or the data.
8. IN-9/IN-14 no answer or recipe leak; end state plus rules of engagement only.
9. IN-12 category, description, keywords, tags honest and on topic.
10. IN-16 no graded expectation with two defensible readings left unsettled.

### 02_Data_Solution_QC.md
1. DS-2 data necessary; DS-21 data plus instruction sufficient (hard is fine, unreachable is not).
2. DS-4 no answers or answer-derivable content in data; contract material is allowed.
3. DS-5 no template residue, no `sample_NNN`, no redacted DRAFT spec.
4. DS-10/DS-11 every tool installed, everything offline including the oracle.
5. DS-28/29/30 uid 1000 writable artifact dirs, pre-baked openhands venv, agent account with HOME.
6. DS-14 oracle computes, never pastes; DS-17 oracle never reads tests/.
7. DS-20 oracle obeys every contract rule, including untriggered ones; precedence order checked pairwise.
8. DS-24 oracle independent of the verifier (tests_qc warns from 20% overlap, fails at 35%).
9. DS-25 every output literal the tests require is findable in an agent-visible file.
10. DS-22/23/27 TRUTH.md matches the shipped code and weights, is unreachable, and has no production narrative.

### 03_Tests_QC.md
1. TS-1 no unconditional `/app/data` read under tests/.
2. TS-6/TS-8/TS-9 test.sh hardens, ends with `exec rewardkit`, no skip switches, no agent-writable exec.
3. TS-10 reward.toml exact shape and arithmetic.
4. TS-11 deterministic (no unsorted iteration, no clock, seeded RNG).
5. TS-12 outcome-driven, never command history.
6. TS-13 one property per test; TS-14 names state the property.
7. TS-15/16 negatives return True on the cheat only, with an inline comment.
8. TS-20 weights mean 5 core, 3 sub-goal/edge, 1 minor; ordering follows the instruction.
9. TS-25 no positive pays for an absence; TS-26 no pair reads the same observable; TS-27 no positive pays for source tokens.
10. TS-24/TS-28/TS-29 agent code only as a timed subprocess under setpriv, process group killed, checks never raise.

### 04_Judge_QC.md
1. Criterion keys `id, name, description, type, weight`, then annotations `mode, type, evidence, residue, kind, category, evaluation_target, importance` + `contract_sentence, contract_file` (constraint) or `serves` (conduct).
2. ids R1.. with no gaps; names unique `^[a-zA-Z0-9_-]{1,64}$`; `type = "binary"`; weights in {±1,±3,±5}.
3. JD-1 "The agent" for trajectory/state_change, "The response" for final_answer/user_facing_message.
4. JD-2 positive grammar only (no not, without, fails to, cannot, instead of).
5. JD-3 no vague qualifiers or threshold-free quantifiers; use counts.
6. JD-5 one observable per criterion; JD-6 decidable from evidence.
7. JD-7 every criterion true of the reference solution; JD-8 zero overlap with tests.
8. JD-13 importance/weight pairing: critically_important 3 or 5, important 1 or 3.
9. JD-15 conduct criteria must hold for every competent route or be odds-raising; preferences fail; each names what it serves.
10. JD-18 at least one criterion judges the quality of the code the agent writes, without prescribing a style.

### 05_Alignment_Integrity_QC.md
1. Runs F0a-F0e and CL-1..CL-10 with numbers or quotes, never bare ticks.
2. AL-1 everything graded is promised (tests strict; criteria by kind).
3. AL-2 everything promised is graded.
4. AL-3 exact shapes agree across contract, tests, solution.
5. AL-4 no hidden graded behaviour beyond the contract.
6. AL-27 every stated rule has a fixture that triggers it; every adjacent precedence pair traced.
7. AL-28 no penalty stacking: one act fires at most one penalty, across tests and judge.
8. AL-10..AL-14, AL-24, AL-25 anti-cheat vectors closed (hardcoding, env abuse, grader influence, reward tamper, filename keying, nondeterminism).
9. AL-15 offline contract consistent across layers.
10. AL-19..AL-23 no secrets, exfiltration, destructive ops, obfuscation, prompt injection.

### templates/domain-calculation/ (13 files)
1. `archetype.toml`: the 10 artifacts, `min_inputs = 10`, `min_outputs = 10`, no `ablation_max` (so playground uses 0.5).
2. `task.toml`: the pinned template with tokens; I may edit only description, keywords, tags, time estimates.
3. `instruction.md`: a reconciliation prompt; it says "the verifier independently derives additional cases", which IN-2 would flag; I replace the whole text.
4. `environment/Dockerfile`: digest-pinned python 3.12, uid 1000 agent, openhands venv, `chown 1000:1000 /app`, `COPY data /app/data`. Keep unchanged.
5. `environment/data/schema.md`: transactions contract; replaced entirely.
6. `datagen.py`: the template's transaction corpus generator; not copied; I write my own in `_work/`.
7. `solution/solve.sh`: `mkdir -p /app/out; cp /solution/solve.py /app/out/derive_report.py; python3 /app/out/derive_report.py /app/data /app/out`.
8. `solution/solve.py`: transaction pipeline; replaced. `solution/TRUTH.md`: token-filled 8-section skeleton; rewritten at P9.
9. `tests/test.sh`, `tests/Dockerfile`: the authoritative templates; keep unchanged.
10. `tests/test_output.py` / `judge.toml`: shapes to keep (`_SHIPPED_DATA`, Rng, `setpriv` wrapper, `_holds`, four negatives); content replaced. Note: the template's `negative_missing_substantive_sections` fires when `summary.json` is missing, which would make nop score below 0; mine returns False when the file is absent.

### DESIGN.md
1. District-heating demand response: per event and region pick a portfolio of offer modes under interval relief and recovery ceilings, one mode per site.
2. 500 events x 4 regions x 5 sites x 9 modes x 6 intervals; exhaustive enumeration is exact (at most 162 portfolios per event-region).
3. 14 files (md, ini, jsonl, csv, tsv, fixed-width txt, json, xml) with four chains of length 4.
4. Spine: canonicalise codes and ticks, eligibility = dispatch_authorized only, optimise, two money branches (credits, grants), aggregate.
5. Hard rules written once as conventions in schema.md section 2, applied by reference elsewhere; misleading surfaces in the XML and the waiver CSV column order.
6. H1 compliance precedence with waiver; H2 greatest sorted offer-id tuple; H3 cap after uplift; H4 descending-id residual cents; H5 quantise each value early.
7. Shipped data neutral to all five rules (no waiver pair, unique optimum, no cap bind, distinct remainders, Wh multiples of 10, exact-cent credits).
8. 25 positive checks (13 visible, 12 hidden) + 4 negatives, positive 87, negative 16.
9. 12 judge criteria, conduct only, positive 30, negative 10.
10. Instruction draft, TRUTH defect labels (3 focal, 2 drift, 3 trap), and the change log from the sketch.

## 2. Data files (environment/data/)

Record rows are data rows (plus one header line where the format has one).

| # | File | Format | Rows | Role | Depends on |
|---|---|---|---|---|---|
| 1 | `schema.md` | md | - | the contract | - |
| 2 | `program.ini` | ini | ~20 keys | `[region_codes]` N1,N2->North, S1,S2->South, W1,W2->West, E1,E2->East; `[segment_codes]` C->commercial, P->public; `[units]` wh_per_tick=10, millicents_per_cent=1000 | - |
| 3 | `events.json` (see Q2) | json | 500 | event_id, interval_count=6, objective weights, settlement uplift (mill-cents/kWh) | program.ini (units) |
| 4 | `sites.csv` | csv | 10,000 | event_id, site_id, region_code, segment_code, beneficiary_id, critical | program.ini, events |
| 5 | `offers.csv` | csv | 18,000 (+ a few orphan rows) | offer_id, event_id, site_id, mode_label, bid_cost_cents | sites |
| 6 | `profiles.tsv` | tsv | 108,000 (+ a few orphans) | offer_id, interval, relief_wh, recovery_wh | offers, program.ini (ticks) |
| 7 | `targets.tsv` | tsv | 12,000 | event_id, region_code, interval, target_wh, shortfall_weight | events, program.ini |
| 8 | `feeder_limits.txt` | fixed-width | 12,000 | event_id, region_code, interval, relief_ceiling_wh, recovery_ceiling_wh | events, program.ini |
| 9 | `site_state.jsonl` | jsonl | 10,000 | event_id, site_id, dispatch_authorized, safety_hold, cooldown | sites |
| 10 | `continuity_waivers.csv` | csv | 10,000 | event_id, site_id, routine_certificate_pending, waiver_status, waiver_signed (optional, blank when absent) | sites, site_state (precedence) |
| 11 | `segment_floors.json` | json | 4,000 entries | event_id, region_code, segment_code, floor_wh, priority_weight | events, program.ini |
| 12 | `rate_cards.xml` | xml | 10,000 `<card>` | event_id, site_id, `<base>`, `<cap>` (mill-cents/kWh) | sites, events (uplift), program.ini (units) |
| 13 | `recipient_weights.tsv` | tsv | 10,000 | event_id, site_id, grant_weight (beneficiary comes from sites.csv, see Q6) | sites |
| 14 | `pools.txt` | fixed-width | 2,000 | event_id, region_code, pool_cents | events, program.ini |

Region codes are mixed on purpose: the same event-region may appear as `N1` in sites.csv and `N2` in
targets.tsv, so every join needs program.ini. Total record lines about 206,000; 8 formats.

### Dependency graph

```
                      program.ini (region codes, segment codes, units)
                     ^      ^        ^          ^           ^
                     |      |        |          |           |
 events.json --------+  sites.csv  targets.tsv  feeder_limits.txt  segment_floors.json  pools.txt
      ^  ^              ^  ^  ^  ^       \___________\______________/             |
      |  |              |  |  |  |              (event, canonical region)          |
      |  +-- rate_cards.xml (uplift from events; units)                            |
      |                 |  |  |  +-- recipient_weights.tsv (beneficiary, region via sites) <-- pools.txt
      |                 |  |  +-- site_state.jsonl <-- continuity_waivers.csv (precedence)
      |                 |  +-- offers.csv <-- profiles.tsv (ticks via units)
      +-----------------+ (sites per event)
```

Chains of length >= 4 (each arrow = "needs"):
- C1 profiles.tsv -> offers.csv -> sites.csv -> program.ini (region, segment, ticks)
- C2 rate_cards.xml -> sites.csv -> events.json (uplift) -> program.ini (units)
- C3 continuity_waivers.csv -> site_state.jsonl -> sites.csv -> program.ini (segment code for the public test)
- C4 pools.txt -> program.ini (region code) -> sites.csv -> recipient_weights.tsv
Every file is needed by at least one other and feeds at least one graded number; the
ablation check confirms each deletion breaks the oracle on the shipped data.

## 3. Rules (where they will live in schema.md)

| Rule | schema.md place | Lazy reading | Separating hidden case | Visible data |
|---|---|---|---|---|
| H1 compliance precedence SAFETY_HOLD > COOLDOWN > CONTINUITY_WAIVED (critical AND public AND certificate pending AND waiver_status valid AND waiver_signed Y) > CERTIFICATE_PENDING > CLEAR | 2.6 (convention), 4 points to it | pending certificate -> CERTIFICATE_PENDING always; or waiver checked before hold/cooldown | case A: critical public pending + valid signed waiver -> CONTINUITY_WAIVED; case B: same with hold, with cooldown, and with each waiver condition missing one at a time | never both pending and valid signed waiver; hold+cooldown and cooldown+pending pairs present so the other adjacent pairs are graded visibly |
| H2 final tie: greatest sorted offer-id tuple (Python tuple order) | 2.4, 5 says "remaining ties follow 2.4" | first found, or smallest | case A: two identical modes `...-A`, `...-Z` -> Z; case B: same with offers/profiles rows reversed | unique optimum in every event-region |
| H3 effective rate = min(base + uplift, cap) | 2.5, 6 says "caps follow 2.5" | min(base, cap) + uplift | case A: base 850, uplift 250, cap 1000, 500 ticks -> 5 cents (lazy 6); case B: base 1200 > cap 1000, uplift 100 | base + uplift <= cap everywhere |
| H4 largest remainder, equal remainders by descending beneficiary id | 2.4, 7 says "equal remainders follow 2.4" | ascending id or first seen | case A: pool 5, three equal weights ALPHA/MU/ZULU -> ZULU, MU get the extra cent; case B: pool 9, weights 3/2/2 -> ALPHA by remainder, then ZULU over MU | distinct remainders in every pool |
| H5 quantise each Wh value to ticks (half up) when read; round each site credit to cents before summing | 2.3, 6 says "per-site rounding follows 2.3" | sum raw Wh then convert; sum raw credits then round once | case A: profile values 5 Wh and 15 Wh -> 1 + 2 = 3 ticks (lazy 2); case B: two sites at half a cent each -> 2 cents (lazy 1) | every Wh a multiple of 10; every site credit an exact cent |
| V1 eligibility = dispatch_authorized only; labels never remove offers | 3 | drop held or cooling sites | (visible) | held but authorized sites present in shipped data |
| V2 objective components C1..C5 in order (see Q3) | 5 | any reorder | (visible) | datagen asserts each adjacent pair decides >= 20 event-regions |
| V3 grants: zero weight sum or no recipient rows -> whole pool unallocated | 7 | divide by zero / drop pool | (visible) | some zero-weight and no-recipient pools shipped |
| V4 orphan rows (unknown offer or site) are skipped and counted | 1 and 9 | crash or include | (visible) | a few orphan rows shipped |
| V5 floor attainment bp = min(10000, half-up 10000 x relief / floor); floor 0 -> 10000 and counted as a zero denominator | 8, 9 | float ratio, crash | (visible) | some zero floors shipped |

## 4. Output shape (draft; exact keys, types and orderings go in schema.md section 8 at P3)

- `region_<R>.json`: `{"region", "events": [ per event sorted by event_id: event_id, candidate_offer_count, selected_offer_ids (sorted), intervals [per interval ascending: interval, target_ticks, relief_ticks, recovery_ticks, shortfall_ticks, overdelivery_ticks], bid_cost_cents, credit_cents, grant_pool_cents, grant_allocated_cents, grant_unallocated_cents, grants [beneficiary_id, cents] sorted by beneficiary_id, compliance_counts {label: n} ], "totals": {...}}`
- `segment_<s>.json`: per (event_id, region) sorted: selected_offer_ids, relief_ticks, recovery_ticks, bid_cost_cents, credit_cents, floor_ticks, floor_attainment_bp; plus totals.
- `summary.json`: global counts and totals (ticks, cents), `regions` and `segments` rollups; pool = allocated + unallocated.
- `policy_audit.json`: compliance_counts, site_labels sorted by (event_id, site_id), tie_decisions, cap_binding_count, residual_cent_decisions.
- `data_quality.json`: rows per file, orphan counts, waiver_signed omissions, empty candidate groups, zero denominators.
All integers; sorted keys; 2-space indent optional, trailing newline required.

## 5. Check table (tests/test_output.py)

Weights below are the PROPOSED re-weighting from Q1; DESIGN weights in brackets where they differ.

| Check | Kind | W | Observable |
|---|---|---|---|
| artifact_set_exists_and_parses | visible | 1 | 10 files exist, 9 parse as JSON objects |
| canonical_serialization_and_integer_units | visible | 1 | bytes: sorted keys, trailing newline, no floats or bools in numeric fields |
| region_north_selected_offers_match | visible | 5 [3] | region_North.json selected_offer_ids per event |
| region_south_selected_offers_match | visible | 5 [3] | same, South |
| region_west_selected_offers_match | visible | 5 [3] | same, West |
| region_east_selected_offers_match | visible | 5 [3] | same, East |
| region_interval_quantities_match | visible | 5 [3] | intervals[] blocks in all four region files |
| segment_commercial_attribution_match | visible | 3 | segment_commercial.json events + totals |
| segment_public_attribution_match | visible | 3 | segment_public.json events + totals |
| procurement_cost_and_credit_totals_match | visible | 5 [3] | bid_cost_cents, credit_cents, grant fields per event in region files |
| summary_rollups_match | visible | 5 [3] | summary.json |
| data_quality_counts_match | visible | 3 | data_quality.json |
| policy_audit_labels_match | visible | 3 [1] | policy_audit.json |
| hidden_ordinary_extract_portfolios_match | hidden | 5 | selections + intervals on a seeded EVAL_SEED extract |
| hidden_ordinary_extract_settlement_match | hidden | 3 | money fields on the same extract |
| waiver_precedence_case | H1 | 5 | policy_audit site label of the crafted site |
| safety_hold_over_waiver_case | H1 | 3 | labels of hold/cooldown/incomplete-waiver sites |
| tie_break_greatest_tuple_case | H2 | 5 | selected_offer_ids of the tied event-region |
| tie_break_reversed_input_case | H2 | 3 [5] | same, rows reversed |
| cap_after_uplift_case | H3 | 5 | credit_cents of the crafted event-region |
| cap_with_base_above_cap_case | H3 | 3 [5] | same, base above cap |
| residual_ties_descending_id_case | H4 | 5 | grants of the crafted pool |
| residual_ties_mixed_weights_case | H4 | 3 | grants of the second pool |
| per_value_tick_quantisation_case | H5 | 5 | relief_ticks of the crafted interval |
| per_site_credit_rounding_case | H5 | 3 [5] | credit_cents of the crafted event-region |
| negative_hardcoded_sample_answers | neg | -5 | hidden run output equals the shipped-data answer (True = cheat) |
| negative_reads_tests_or_reward_files | neg | -5 | a string constant in /app/out/*.py names /tests, /logs/verifier or a grader file (True = cheat) |
| negative_external_dependency_or_network | neg | -3 | an import in /app/out/*.py of a non-stdlib or network module (True = cheat) |
| negative_missing_substantive_sections | neg | -3 | summary.json exists but lacks a required top-level section (absent file -> False) |

Proposed totals: positive 97 (visible 49, hidden 48: ordinary 8, traps 8 per rule), negative 16.
Hidden share 48/97 = 0.495.
Each hidden case is hand-built; at grade time the check also confirms that its own lazy
reading gives a different answer, so a broken case shows up as an oracle score below 1.0.

## 6. Judge table (tests/judge.toml), from DESIGN section 10

| ID | Description (DESIGN text unless noted) | kind / target | W |
|---|---|---|---|
| R1 | The agent reads schema.md through to its last section before writing derive_report.py. | conduct / trajectory | 3 |
| R2 | The agent prints sample records from at least six different data files before settling its joins. | conduct / trajectory | 3 |
| R3 | The agent checks the region and segment codes in program.ini against the codes that appear in sites.csv. | conduct / trajectory | 3 |
| R4 | The agent states the five objective components and the final tie rule in its own words before coding the optimiser. | conduct / trajectory | 3 |
| R5 | The agent works out the number of candidate portfolios per event and region and says why checking all of them is affordable. | conduct / trajectory | 3 |
| R6 | The agent builds a small hand-made case where the rate cap binds and runs its program on it. | conduct / trajectory | 3 |
| R7 | The agent builds a small hand-made grant pool with equal remainders and runs its program on it. | conduct / trajectory | 3 |
| R8 | The agent runs derive_report.py on a reduced or reordered copy of the data and compares the two sets of outputs. | conduct / trajectory | 3 |
| R9 | code quality, rewording proposed in Q5 | conduct / trajectory | 3 |
| R10 | The response names at least one contract rule that the shipped data never exercised. | conduct / user_facing_message | 3 |
| R11 | trigger narrowed per Q4: The agent runs a shell command such as cat, ls, head or find on a path under /tests or /logs/verifier. | conduct / trajectory | -5 |
| R12 | The response says the outputs were verified while the agent's last run of derive_report.py ended in an error. | conduct / user_facing_message | -5 |

Positive 30, negative 10. No constraint criteria, so no contract_sentence.

## 7. Baseline table (P10, test channel)

Not measured yet. Arithmetic from the proposed weights (not a measurement): reference 1.00;
one rule lazy 89/97 = 0.92 if both its cases fail; all five lazy, rest correct 57/97 = 0.59.
P10 measures the real rows.

## 8. Order of work

P1 scaffold -> P2 data -> P3 schema -> P4 oracle -> P5 tests -> P6 judge -> P7 instruction
-> P8 toml -> P9 TRUTH -> P10 baselines -> P11 validation -> P12 report, as in TODO.md.

## 9. Open questions (need your answer before P1)

Q1 Ablation vs hidden weight (blocks the playground gate). The playground ablation deletes one
data file and reruns the oracle. `solve.sh` copies `derive_report.py` into `/app/out` before it
runs, so with a file missing the program still exists, the run on `/app/data` crashes, and every
HIDDEN check still passes because the verifier builds its own complete extracts
(`playground.py` lines 251-262, 329-341). With DESIGN weights the hidden checks hold 54 of 87 =
0.62, above the 0.5 ceiling, so every ablation would FAIL. Options:
- A (recommended): re-weight so hidden <= half of the positive total (table in section 5:
  hidden 48 of 97 = 0.495; all-lazy row then 0.59, still inside 0.40-0.60). DESIGN section 9
  already allows re-weighting.
- B: keep DESIGN weights and have the oracle install `derive_report.py` only after a
  successful run on `/app/data`. Honest code, but it shapes the oracle around the measurement.

Q2 `events.jsonl` has 500 rows; the rule says every jsonl record file needs 2,000 lines
(playground A5 fails it). Options: (a, recommended) ship it as `events.json` (a JSON array,
not a record file; still 8 formats); (b) one jsonl line per event and region (2,000 lines,
objective weights and uplift then per event-region); (c) 2,000 events (4x data, ~430k profile
lines, heavier embedded copy).

Q3 The DESIGN names "objective components 1-5" and "objective weights" in events but never
defines them. Proposed lexicographic tuple, minimised:
- C1 weighted shortfall = sum over intervals of shortfall_weight x max(0, target - relief) ticks
- C2 weighted floor deficit = sum over segments of priority_weight x max(0, floor - segment relief) ticks
- C3 blended cost = cost_weight x bid_cost_cents + recovery_weight x total recovery ticks (both weights from events)
- C4 overdelivery = sum over intervals of max(0, relief - target) ticks
- C5 number of selected offers
- C6 final tie: greatest sorted offer-id tuple (H2)
Constraints: per interval sum relief <= relief ceiling, sum recovery <= recovery ceiling; at most one mode per site; empty portfolio allowed.

Q4 Penalty stacking (AL-28). `negative_reads_tests_or_reward_files` (-5) and R11 (-5) can both
fire on one act if the program reads /tests. I propose disjoint triggers: the test fires only on
the delivered program's source naming grader paths; R11 fires only on shell commands the agent
runs in its session (wording in section 6).

Q5 R9 "separate functions for parsing, optimisation, settlement and reporting" prescribes one
structure, which gate 04 treats as a preference (JD-15 example "implements the decoder as a
state machine", JD-18 "must judge quality, not prescribe a style"). Proposed: "The agent writes
derive_report.py with descriptive function names, specific exception types in every except
clause and no dead or duplicated code blocks."

Q6 Minor choices I will make unless you object:
- `recipient_weights.tsv` columns `event_id, site_id, grant_weight`; the beneficiary comes from sites.csv (keeps chain C4 load-bearing). Grants per beneficiary sum that beneficiary's weights in the event-region.
- Credits: a selected site's credit = relief ticks x wh_per_tick x effective rate / (1000 x millicents_per_cent), half up once per site; settlement is independent of compliance labels; grants are independent of selection and compliance.
- Keep the template `solve.sh` form (copy solve.py to `/app/out/derive_report.py`, then run it), unless Q1 B is chosen.
- Shipped data includes held-but-authorized sites, zero floors, zero-weight and no-recipient pools and a few orphan rows, so V1-V5 are graded on visible data.
- No shipped value is deliberately wrong, so CL-6 has nothing to signpost; the misleading surfaces (XML layout, waiver column order) are layout, not wrong values.
- TRUTH.md provenance `authored_by: null` (validator reads it as the non-empty string "null"; checked `c_15_provenance_keys`).

## 10. Decisions (Ayush, 2026-10-19 16:58 IST: "proceed with your best recommendations")

Q1 A (re-weight, hidden <= half). Q2 (a) `events.json`. Q3 objective tuple C1..C6 as proposed.
Q4 disjoint triggers (test = program source; R11 = shell commands in session). Q5 R9 reworded.
Q6 all minor choices as listed.

## 11. Rule locations in schema.md (P3 exit check)

| Rule | schema.md line |
|---|---|
| H1 | 111 "Every site row gets exactly one compliance label: the highest-ranked finding that applies" ; 113 "A continuity waiver is valid only when all four of these hold"; applied from 4 "chosen by the programme conventions" |
| H2 | 99 "the greatest identifier wins"; 100 "A set of identifiers compares as the tuple of its members sorted ascending"; applied from 160 "Remaining ties follow the programme conventions." |
| H3 | 106 "A cap always binds the final rate, after every adjustment to that rate has been applied"; applied from 166 "caps follow the programme conventions" |
| H4 | 102 "they are served in descending identifier order"; applied from 186 "equal remainders follow the programme conventions" |
| H5 | 91 "A Wh value read from any file becomes ticks ... as soon as it is read"; 93 "A money figure derived for one site is rounded half up to whole cents for that site"; applied from 169 |
| V1 | 123 "Compliance labels never change eligibility" |
| V2 | 148-158 components 1 to 5 |
| V3 | 182 "When there are no recipients, or W is 0, the whole pool is unallocated." |
| V4 | 35 orphan offer, 39-40 orphan profile row |
| V5 | 238 floor_attainment_bp |
| Serialization | 199-200 sorted keys, newline, integers only |

Data change vs PLAN section 2: datagen ships every Wh value and rate as a multiple of 1000, which
is what makes per-site credits land on exact cents (DESIGN section 3).

## 12. Baseline table (P10, measured with the real test_output.py through _work/grade.py)

| Implementation (solve.py with patches, _work/wrong/) | Earned / 98 | Fraction | Checks lost |
|---|---|---|---|
| Reference | 98 | 1.000 | none |
| Only H1 lazy (pending always CERTIFICATE_PENDING) | 90 | 0.918 | both H1 cases |
| Only H2 lazy (smallest tuple) | 90 | 0.918 | both H2 cases |
| Only H3 lazy (min(base, cap) + uplift) | 90 | 0.918 | both H3 cases |
| Only H4 lazy (ascending id) | 90 | 0.918 | both H4 cases |
| Only H5 lazy (raw Wh sums, credits rounded once) | 90 | 0.918 | both H5 cases |
| H2, H3, H5 lazy | 74 | 0.755 | 6 cases |
| H2, H3, H4, H5 lazy | 66 | 0.673 | 8 cases |
| All five lazy, rest correct | 58 | 0.592 | 10 cases |
| First-fit greedy optimiser, H1-H4 lazy | 19 | 0.194 | 19 checks |

The all-lazy row (0.592) is inside the 0.40-0.60 band. The first measurement had H1 losing
only 5 (waiver_precedence_case); `safety_hold_over_waiver_case` gained a site with a valid
signed waiver and no hold so it also separates the "pending always CERTIFICATE_PENDING"
reading. Greedy row has no H5 patch: combining the raw-Wh patch with the greedy patch
compares Wh against tick ceilings, which is a harness bug, not a reading.

## 13. v2 HARDEN plan (written 2026-10-19 18:30 IST, waiting for approval)

Input: the independent solve (one pass, about 15 min, full marks). Goal: real algorithmic
difficulty (L1), one coupling hop (L2), cheap spec-compliant parsing traps (L3), and the 4
fairness fixes, without breaking QC. Every number below marked "projected" is arithmetic from
the proposed weights, not a measurement; V5 measures the real rows.

### 13.1 Diagnosis -> response

| Finding | Response |
|---|---|
| Every rule maps straight to code | L1 makes the optimiser itself the hard part; L2 makes a wrong portfolio propagate into grants |
| `itertools.product` over <= 162 portfolios | 10 shipped and >= 2 hidden large event-regions with 18 to 22 sites, 3 to 4 modes (product about 10^11 to 10^13) |
| Every output is one hop from the inputs | grants funded from `pool - credits` of the chosen portfolio |
| 4 guesses | fixed in schema.md (13.2 items F1 to F4) |

Kept as is: shipped data inert to H1 to H5 (and to the new tie and floor rules); constructed
hidden cases test them.

### 13.2 schema.md edits (exact places)

| Id | Section | Change |
|---|---|---|
| F1 | 2.4 | After "using Python tuple order" add: "For example, the set {A, Z} is the tuple (A, Z) and the set {B, C} is (B, C); (B, C) is the greater because B is greater than A at the first position, even though Z is the largest single identifier. A tuple that is a proper prefix of another is the smaller one, so the empty portfolio is smaller than any other." |
| F2 | 2.3 + 6 | 2.3: "The credit of each chosen offer is rounded half up to whole cents on its own, before it is added to any total. A portfolio holds at most one offer per site, so this is also the site's credit." 6 keeps "Rounding of the credit follows the programme conventions." |
| F3 | 1 (opening paragraph) | "In every line-based file (CSV, TSV, JSONL and the fixed-width files) a line that is empty or holds only spaces or tabs is skipped and is not counted anywhere." 9 `site_state.jsonl` row count becomes "(non-blank lines)". |
| F4 | 1 (end of `program.ini` bullet) | "Every `region_code` in every file (sites, targets, feeder limits, segment floors, pools) is turned into its region name through `[region_codes]` before it is used to match records; records are always matched on the region name, never on the code. Segment codes likewise go through `[segment_codes]`." |
| L1a | 5 (after the component list) | Replace "Remaining ties follow the programme conventions." with: "The best value is the smallest tuple of components 1 to 5 over all feasible portfolios. The tied portfolios of an event-region are all feasible portfolios whose components 1 to 5 equal the best value; their number, the chosen one included, is its tied portfolio count (1 when the best portfolio is unique). The chosen portfolio is one of the tied portfolios, picked by the programme conventions. The answer must be the exact optimum: an event-region can have more than 20 sites, so the number of portfolios can exceed 10^12." (The last sentence is a fact about the data, not a method; the method stays the agent's.) |
| L1b | 8.1 | `events` entries gain `tied_portfolio_count` (defined in 5). 8.4 `tie_decisions` points to the same definition (no second definition). |
| L2a | 7 (new first paragraph) | "Calculation order for each event-region: the portfolio (section 5), then its credits (section 6), then the funded pool, then the apportionment below. The funded pool is the `pools.txt` pool minus the event-region's `credit_cents`, or 0 when that difference is negative." Every later "pool" in 7 becomes "funded pool". |
| L2b | 7 | Delete "Grants depend only on pools and weights, never on portfolios or compliance labels." Replace with "Compliance labels never change grants." |
| L2c | 8.1, 8.3 | Keep `grant_pool_cents` = the `pools.txt` pool; add `grant_funded_cents`; `grant_allocated_cents + grant_unallocated_cents = grant_funded_cents`. `totals` and `summary.json` gain `grant_funded_cents`. |
| L3a | 1 `feeder_limits.txt`, `pools.txt` | "Fields are read by character position only; adjacent fields can touch with no space between them (an `event_id` can fill all 10 columns and a ceiling all 10 digits)." |
| L3b | 1 (CSV sentence) | "CSV and TSV fields follow RFC 4180 quoting: a field that contains the separator or a quote is enclosed in double quotes (Python `csv` reads them correctly)." |
| L3c | 1 `rate_cards.xml` | "The order of `base` and `cap` inside a card varies, and spaces or line breaks around a number are ignored." |
| L3d | 1 `profiles.tsv` + 9 | "A profile row is an orphan only when its `offer_id` is absent from `offers.csv`. Rows of offers that are listed but are orphan offers, or whose site row cannot dispatch, are not orphan profile rows; they are skipped." 9 `ineligible_offer_count` unchanged; the two counts stay apart. |

Each rule stays stated once; applying sections keep pointing to section 2.

### 13.3 Output changes

- `region_<R>.json` events: `tied_portfolio_count`, `grant_funded_cents`; `totals`: `grant_funded_cents`.
- `summary.json`: `grant_funded_cents`. `policy_audit.json` `residual_cents` and
  `residual_tie_pool_count` now computed on funded pools.
- Artifact set unchanged (10 files).

### 13.4 Data changes (datagen.py, seed 731904)

- Large groups: 10 event-regions (North 3, South 3, West 2, East 2), 18 to 22 sites each,
  mostly 3 modes per site and a few 4 (product of (modes + 1) kept in 10^11..10^13, logged per
  group). Targets high enough that most sites are needed; 9 to 10 of the 12 ceilings slack
  (written as 10-digit values such as `9999999990`), 2 to 3 tight. Unique optimum asserted
  with datagen's own exact search (rerolls logged). Small groups unchanged in kind.
- L3: about 60 events get 10-character ids (`W26-0412-B` style), including every large-group
  event, so event ids touch the code column in both fixed-width files; slack ceilings touch the
  interval and each other. About 3% of `mode_label` values contain a comma and are quoted.
  About 30% of cards put `<cap>` first; about 20% of numbers carry surrounding spaces or a
  line break. Profile rows added for the 14 orphan offers (6 rows each); ineligible offers keep
  their rows. 5 blank lines inside `site_state.jsonl`.
- Neutrality kept and extended: H1 to H5 as before; every tie count is 1; every funded pool is
  positive (floor rule inert); distinct non-zero remainders on the funded pool (pool rerolled
  after the optimum and credits are known).
- Line counts: profiles about +4,600, offers about +760, sites about +150; every record file
  stays >= 2,000 lines (A5).

### 13.5 Reference, oracle and exactness proof

- `solution/solve.py`: depth-first branch-and-bound. Sites ordered by descending total relief;
  suffix maxima of relief per interval and per segment; lower bound tuple built componentwise
  (C1 from capped best-case relief, C2 from best-case segment relief, C3 partial cost plus
  partial recovery, C4 partial overdelivery that can only grow when no further relief fits, C5
  partial count). Prune on feasibility (relief and recovery only grow) and when the bound tuple
  is STRICTLY greater than the incumbent, so every tied optimum is visited and counted. The
  chosen portfolio is the greatest sorted id tuple among the ties, so search order never
  matters. Coupling and L3-safe parsing as in 13.2.
- Verifier reference (tests): an independently written exact method. First choice is a
  state-merging dynamic programme over sites in id order (state = relief and recovery per
  interval plus segment relief; keep the lexicographically best partial cost and count with
  their multiplicities and tied id tuples), pruned by ceilings. If it misses the verifier time
  budget in V4, fall back to a second branch-and-bound with a different branching order and
  bounds; the choice and its timing go in LOG.md.
- `_work/check_exact.py`: (a) 200 random small groups (<= 8 sites, 1 to 4 modes, random tight
  ceilings, forced ties in some) compared on best value, tie count and chosen ids against plain
  `itertools.product`; (b) every shipped and hidden large group compared between solve.py and
  the verifier reference. Result logged.

### 13.6 New hidden cases

| Case | Rule stressed | Construction | Expected lazy failure |
|---|---|---|---|
| ordinary extract (changed) | exact optimum at scale | existing seeded extract plus 2 large groups (18 to 20 sites), 10-char ids, 10-digit slack ceilings | brute force times out at N; greedy picks a worse portfolio; `str.split()` misreads the fixed-width lines |
| `large_tie` | tie counting | one 20-site group with 4 tied optima: two identical-number mode pairs at the first and the last branched site (2 x 2), plus no other tie | pruning on `>=` reports 1 (or fewer than 4) |
| `large_tie_shuffled` | tuple order and order independence | one 20-site group with 2 tied optima shaped like {A, Z} vs {B, C} (sorted-tuple winner differs from largest-element winner), all rows of offers.csv and profiles.tsv shuffled | largest-element order, smallest tuple, or first-found picks the other portfolio |
| `grant_after_credit` | funded pool, floor at 0 | North: one site, one mode, wide limits, credit 37 cents, pool 1000, three beneficiaries; South: same with credit above the pool | raw pool funds 1000 (North) and a positive pool (South); a missing floor gives negative cents |

Each case keeps the existing `separated()` guard: new lazy flags `TIEcount` (count reported as
1), `H2max` (largest-element order) and `L2` (raw pool) prove at grade time that the lazy
reading changes the observable.

### 13.7 Check list (proposed)

| Check | Kind | W | Observable |
|---|---|---|---|
| artifact_set_exists_and_parses | visible | 1 | 10 files, 9 parse |
| canonical_serialization_and_integer_units | visible | 1 | bytes |
| region_north/south/west/east_selected_offers_match | visible | 5 each (20) | candidate count, selected ids, tied_portfolio_count per event |
| region_interval_quantities_match | visible | 5 | intervals blocks |
| procurement_cost_and_credit_match | visible | 5 | per-event bid_cost_cents, credit_cents |
| region_grant_allocations_match | visible | 5 | per-event pool, funded, allocated, unallocated, grants |
| segment_commercial_attribution_match | visible | 3 | file |
| segment_public_attribution_match | visible | 3 | file |
| summary_rollups_match | visible | 5 | summary.json and the four region totals blocks |
| data_quality_counts_match | visible | 3 | file |
| policy_audit_labels_match | visible | 3 | file and per-event compliance counts |
| hidden_ordinary_extract_portfolios_match | hidden | 5 | selections, tie counts, intervals |
| hidden_ordinary_extract_settlement_match | hidden | 3 | bid costs, credits |
| hidden_ordinary_extract_grants_match | hidden | 1 | funded, allocated, grants |
| large_tie_count_case | L1 | 5 | tied_portfolio_count |
| large_tie_shuffled_selection_case | L1 | 3 | selected_offer_ids |
| grant_after_credit_case | L2 | 5 | grants and funded cents, North and South |
| waiver_precedence_case / safety_hold_over_waiver_case | H1 | 5 / 1 | labels |
| tie_break_greatest_tuple_case / tie_break_reversed_input_case | H2 | 5 / 1 | selected ids |
| cap_after_uplift_case / cap_with_base_above_cap_case | H3 | 5 / 1 | credit |
| residual_ties_descending_id_case / residual_ties_mixed_weights_case | H4 | 5 / 1 | grants |
| per_value_tick_quantisation_case / per_site_credit_rounding_case | H5 | 5 / 1 | ticks / credit |
| 4 negatives (unchanged) | neg | -5, -5, -3, -3 | as before |

Totals: 30 positive checks + 4 negatives = 34 (limit 35). Positive 106: visible 54, hidden 52
(share 0.491, so a playground ablation projects to 0.491 <= 0.5). Negative 16 <= 106. The
second case of each H rule drops from 3 to 1 to keep hidden <= half; the floor case is merged
into `grant_after_credit_case` (one property: funded = max(0, pool - credits)).

Projected rows (arithmetic only): reference 1.000; all-lazy (H1 to H5 lazy, prune on `>=`, no
coupling, exact otherwise) 49/106 = 0.462; greedy or time-capped search on large groups, rest
correct, about 40/106 = 0.377; only no coupling 87/106 = 0.821.

### 13.8 wrong/ variants (V5)

only_H1 .. only_H5, all_lazy (H1-H5 + `>=` pruning + no coupling), capped_bruteforce (product
search with a node cap, falls back to greedy on large groups), prune_ge (`>=` pruning only),
no_coupling (raw pool), split_fixed_width (`str.split()` on both fixed-width files), plus the old
greedy row. Tuning knobs if the band is missed: H-case second weights (1 or 3), V13 weight,
hidden ordinary grants weight; every iteration logged.

### 13.9 Runtime plan

- Measure in the agent image: `docker build` of `environment/` (tag `dhfp-v2-agent-<ts>`),
  `docker run --cpus=2 --memory=4g`, solve.py on `/app/data`, 3 runs, nohup with logs in
  `/tmp/opencode-logs/dhfp-v2-20261019T1822/`. A timing harness reports per-large-group seconds;
  target total for the 10 large groups < 60 s.
- N = ceiling of 3 x the slowest measured full oracle run, rounded up to 10 s. One N for every
  run, stated in instruction.md as "Each run of the program on an extract must finish within N
  seconds." and used as `_AGENT_TIMEOUT`. A single stated number is the only fair form: a
  per-extract 3x oracle time would be about 3 s on the tiny cases, which the instruction cannot
  state honestly.
- Verifier time: measured twice, (a) oracle workspace through grade.py in the tests image and
  (b) a worst case where every large hidden run hits N (capped_bruteforce without its cap).
  Bound: reference time + 3 large hidden extracts x N; target well under 2700 s (aim < 900 s).
  The ordinary-extract seed search is capped and its found step logged, so it never multiplies
  the large-group cost.

### 13.10 Other files

- instruction.md: add the runtime sentence; change the pool bullet to "Each grant pool's
  funded cents must equal its allocated plus unallocated cents." Nothing else.
- judge.toml: R5 becomes "The agent times derive_report.py on the shipped data and reports the
  number of seconds."; add "The agent compares its optimiser's result with plain enumeration of
  every portfolio on at least one group of 8 or fewer sites." and "The agent runs its program on
  a hand-made group with two or more tied best portfolios and checks the reported
  tied_portfolio_count." Positive total rises from 30 to 36; reward.toml judge factor rewritten.
- task.toml: description and keywords drop "exhaustive search" for "exact search"; time
  estimates raised (expert 300 min, junior 900 min, estimated 6600 s). Nothing else.
- TRUTH.md: focal "exact optimisation at scale with tie counting"; drift "grant funding after
  credits"; trap "strict pruning for tie counts" and "fixed-width touching fields"; fresh digests.
- DESIGN.md: `## v2` section listing every change.

### 13.11 Questions for approval

1. Pool fields: keep `grant_pool_cents` raw and add `grant_funded_cents` (recommended), or
   redefine `grant_pool_cents` as the funded pool?
2. Timeout: one stated N for every run (recommended, 13.9), instead of a per-extract 3x?
3. "Orphan profile rows that point at offers that exist but are ineligible": under the contract
   such rows are not orphans. I read the lever as "ship profile rows for orphan and ineligible
   offers and state that neither counts as an orphan profile row" (13.2 L3d). Confirm.
4. Floor at 0 of the funded pool: inert in shipped data, tested only by the hidden case
   (recommended, matches the inert design), or visible in shipped data?
5. Check count lands at 34 of 35 with the floor merged into `grant_after_credit_case`. OK?
