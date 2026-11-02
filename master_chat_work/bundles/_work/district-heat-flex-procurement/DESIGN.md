# DESIGN - district-heat-flex-procurement

Status: APPROVED by Ayush on 2026-10-19. Seed 731904. Source: ChatGPT sketch of 2026-10-19, reviewed
and corrected against the generator, the QC folder and the build notes. Section 13
lists every change from the sketch.

## 0. Identity

| Field | Value |
|---|---|
| Slug / bundle name | `district-heat-flex-procurement` |
| Archetype | `domain-calculation` (10 fixed artifacts) |
| Category flag | `--category optimization` -> `[metadata].category = "Optimization"` |
| Author | `Ayush Sah <ayush.sah@ethara.ai>` |
| Seed | `731904` |
| Agent timeout | 7200 s (generator default) |

## 1. Premise

A district-heating utility runs a winter demand-response programme. For every event
window and every region it must pick a portfolio of heat-pump / boiler "offer modes"
from participating buildings, under interval relief ceilings, recovery-load
ceilings and one-mode-per-site exclusivity, then settle performance credits, share
out a grant pool, classify each site for compliance and report everything per
region, per customer segment and globally. The agent ships one reusable stdlib
program that does this for any extract in the same schema.

Not this: a 0-1 knapsack (multi-interval profiles, mode exclusivity, lexicographic
multi-part objective), not Hungarian assignment (portfolios, not 1:1 matches), not
a textbook unit-commitment LP (exact integer enumeration with a contract-defined
comparator).

## 2. Scale (reduced from the sketch)

The sketch's 2,200 events gave ~950k input lines and a 475k-line profile file:
too heavy for the embedded verifier copy and the hidden-extract reruns. Use:

- 500 events x 4 regions x 5 sites per event-region x 9 offer modes per
  event-region (1 to 3 modes per site) x 6 intervals.
- Exhaustive search per event-region is at most a few hundred portfolios
  (product over sites of modes+1), so plain enumeration is exact and fast.

## 3. Input files (14 files, 7 formats)

All in flat `environment/data/`. Record-file line counts are data rows.

| # | File | Format | Rows | Role | Needs |
|---|---|---|---|---|---|
| 1 | `schema.md` | markdown | - | The whole contract (section map in 5) | - |
| 2 | `program.ini` | ini | - | Region code map (`N1`,`N2`->North ...), unit constants (Wh per tick, mill-cents per cent), segment code map (`C`/`P`) | - |
| 3 | `events.jsonl` | jsonl | 500 | Event id, interval count, objective weights, settlement uplift (mill-cents/kWh) | program.ini |
| 4 | `sites.csv` | csv | 10,000 | Event/site snapshot: region code, segment code, beneficiary id, critical flag | program.ini, events |
| 5 | `offers.csv` | csv | 18,000 | Offer id, site id, mode label, bid cost (cents) | sites |
| 6 | `profiles.tsv` | tsv | 108,000 | Offer x interval: relief Wh, recovery Wh | offers, program.ini |
| 7 | `targets.tsv` | tsv | 12,000 | Event x region code x interval: relief target Wh, shortfall weight | events, program.ini |
| 8 | `feeder_limits.txt` | fixed-width txt | 12,000 | Event x region code x interval: relief ceiling Wh, recovery ceiling Wh | events, program.ini |
| 9 | `site_state.jsonl` | jsonl | 10,000 | Event/site: dispatch_authorized, safety_hold, cooldown | sites |
| 10 | `continuity_waivers.csv` | csv | 10,000 | Event/site: routine_certificate_pending, waiver_status, waiver_signed (optional field) | sites, site_state |
| 11 | `segment_floors.json` | json | 4,000 entries | Event x region x segment: floor Wh, priority weight | events, program.ini |
| 12 | `rate_cards.xml` | xml | 10,000 elements | Event/site: base rate and rate cap (mill-cents/kWh) | sites, events (uplift) |
| 13 | `recipient_weights.tsv` | tsv | 10,000 | Event/site/beneficiary: integer grant weight | sites |
| 14 | `pools.txt` | fixed-width txt | 2,000 | Event x region code: grant pool cents | events, program.ini |

Totals: well over 20,000 lines; every csv/tsv/jsonl/txt record file >= 2,000 rows.
Formats: md, ini, jsonl, csv, tsv, fixed-width txt, json, xml.

Chains of length 4 or more (draw these in PLAN.md):
- profiles.tsv -> offers.csv -> sites.csv -> program.ini (region, segment)
- rate_cards.xml -> sites.csv -> events.jsonl (uplift) -> program.ini (unit constants)
- continuity_waivers.csv -> site_state.jsonl -> sites.csv -> program.ini
- pools.txt -> program.ini (region code) -> sites.csv -> recipient_weights.tsv

Every file is load-bearing: deleting any one breaks portfolios, settlement,
compliance or reporting for all regions (playground ablation must show <= 0.5).

Data-generation rules (so the shipped data cannot expose a wrong reading):
- No site/event has both a pending certificate and a valid signed waiver.
- No event-region has two distinct optimal portfolios (unique optimum).
- Every shipped base rate + uplift <= cap.
- Every shipped grant pool has distinct fractional remainders.
- Every shipped Wh value is a multiple of 10, and every shipped credit lands on an
  exact cent, so per-value and end-only rounding agree on the shipped data.
- No file carries declared totals, checksums or answer values.
- No em/en dashes anywhere.

## 4. Spine

1. Canonicalise and join (region/segment codes via program.ini, Wh -> ticks).
2. Eligibility: drop offers whose site is not `dispatch_authorized`. (Compliance
   labels never affect eligibility.)
3. Optimise each event-region: exhaustive enumeration under per-interval relief
   ceiling, per-interval recovery ceiling, one mode per site; minimise the
   objective tuple of 6 (rule H2).
4. Two independent money branches: performance credits (H3) and grant
   apportionment (H4). Neither feeds the optimiser or the other.
5. Aggregate into region, segment, summary, audit and quality outputs.

## 5. schema.md section map (where each rule lives)

Each hard rule is written in full, ONCE, but as a programme-wide convention in
section 2 "Conventions", not inside the section where it applies. The applying
section only says "ties and caps follow the programme conventions". This is legal
(DS-21: the rule is in an agent-visible file) and is the difficulty.

| Section | Content |
|---|---|
| 1 Files and keys | every file, every column/key, optional fields and their meaning |
| 2 Conventions | 2.1 units and ticks; 2.2 round-half-up definition; 2.3 "every quantity is quantised when it is first derived, never at the end" (H5); 2.4 "whenever an ordered choice among equals is needed, the greatest identifier or tuple wins" (H2, H4); 2.5 "a cap always binds the final rate after every adjustment" (H3); 2.6 "compliance findings are ranked SAFETY_HOLD, COOLDOWN, CONTINUITY_WAIVED, CERTIFICATE_PENDING, CLEAR" plus waiver validity (H1) |
| 3 Eligibility | dispatch_authorized only |
| 4 Compliance | how each finding is detected; points to 2.6 |
| 5 Optimisation | constraints, objective components 1-5 in order; "remaining ties follow 2.4" |
| 6 Settlement | credit formula; "caps follow 2.5"; per-site rounding "follows 2.3" |
| 7 Grants | largest-remainder apportionment; "equal remainders follow 2.4"; zero weight sum -> pool unallocated; event-region with no recipients -> unallocated |
| 8 Outputs | every output file, every key name, value type, unit suffix, array ordering |
| 9 Data quality | every count `data_quality.json` must carry |

Misleading surfaces (allowed, the contract is authoritative): `rate_cards.xml`
puts `<cap>` next to `<base>` (suggests capping the base); the waiver CSV lists
columns in the order certificate, waiver, so first-populated-column gives the
wrong label.

## 6. Hard rules (5 independent mechanisms)

| ID | Rule (reference) | Lazy reading | Separating hidden case | Outputs touched |
|---|---|---|---|---|
| H1 | Compliance precedence: SAFETY_HOLD > COOLDOWN > CONTINUITY_WAIVED (critical public site, pending certificate, waiver valid AND signed) > CERTIFICATE_PENDING > CLEAR | First populated flag, or pending certificate always CERTIFICATE_PENDING | Critical public site, pending cert, valid signed waiver, no hold/cooldown -> CONTINUITY_WAIVED | policy_audit, region/segment compliance counts |
| H2 | Final tie among equal objective tuples: lexicographically GREATEST sorted offer-id tuple | First found or smallest | Two modes at one site with identical numbers, ids `...-A` / `...-Z` -> pick Z; same case with input rows reversed | region selected offers, segment attribution, audit tie record |
| H3 | Effective rate = min(base + uplift, cap) | min(base, cap) + uplift | base 850, uplift 250, cap 1000 mill-cents/kWh on 500 ticks -> 5 cents (lazy 6) | credits in region/segment/summary, audit cap count |
| H4 | Largest remainder; equal remainders by DESCENDING beneficiary id | ascending id or first seen | 5-cent pool, three equal weights ALPHA/MU/ZULU -> ZULU and MU get the extra cents | grant allocations, pool accounting |
| H5 | Quantise each Wh value to ticks (round half up) before summing; round each site credit to cents before summing | sum raw Wh / credits, round once | Profile values of 5 Wh and 15 Wh in one portfolio; two half-cent credits | interval quantities, shortfalls, credit totals |

Every hidden case must be constructed, not sampled, and the test must re-check
at grade time that its lazy reading really gives a different answer.

## 7. Outputs (10 fixed artifacts)

- `/app/out/derive_report.py`: the reusable program.
- `summary.json`: global counts, energy totals (ticks), shortfall, overdelivery,
  bid cost, credit total, pool total = allocated + unallocated, per-region and
  per-segment rollups.
- `policy_audit.json`: compliance label counts and per-site labels, tie decisions,
  cap-binding count, residual-cent decisions.
- `data_quality.json`: rows per file, join coverage, optional-field omissions,
  empty candidate groups, zero-denominator count.
- `region_North/South/West/East.json`: per event: selected offer ids, interval
  relief/recovery ticks, shortfalls, costs, credits, grants, compliance counts.
- `segment_commercial.json` / `segment_public.json`: the same results attributed
  to the segment, by region and event, with floor attainment in basis points.

Exact key names, types and orderings are defined in schema.md section 8 (DS-25).

## 8. Tests (test_output.py)

Two kinds of positive checks: VISIBLE (agent's `/app/out` outputs vs the
reference computed from the embedded shipped data; no hard rule is triggered
there) and HIDDEN (the verifier runs the agent's script as `nobody` on extracts it
generates; one mechanism per trap case so each lazy reading loses exactly its own
checks).

| Check | Kind | W (registered in the 19 Oct build) |
|---|---|---|
| `artifact_set_exists_and_parses` | visible | 1 |
| `canonical_serialization_and_integer_units` | visible | 1 |
| `region_north_selected_offers_match` | visible | 5 |
| `region_south_selected_offers_match` | visible | 5 |
| `region_west_selected_offers_match` | visible | 5 |
| `region_east_selected_offers_match` | visible | 5 |
| `region_interval_quantities_match` | visible | 5 |
| `procurement_cost_and_credit_totals_match` | visible | 5 |
| `region_grant_allocations_match` | visible | 3 |
| `segment_commercial_attribution_match` | visible | 3 |
| `segment_public_attribution_match` | visible | 3 |
| `summary_rollups_match` | visible | 3 |
| `data_quality_counts_match` | visible | 3 |
| `policy_audit_labels_match` | visible | 3 |
| `hidden_ordinary_extract_portfolios_match` | hidden, no trap | 5 |
| `hidden_ordinary_extract_settlement_match` | hidden, no trap | 3 |
| `waiver_precedence_case` | H1 | 5 |
| `safety_hold_over_waiver_case` | H1 | 3 |
| `tie_break_greatest_tuple_case` | H2 | 5 |
| `tie_break_reversed_input_case` | H2 | 3 |
| `cap_after_uplift_case` | H3 | 5 |
| `cap_with_base_above_cap_case` | H3 | 3 |
| `residual_ties_descending_id_case` | H4 | 5 |
| `residual_ties_mixed_weights_case` | H4 | 3 |
| `per_value_tick_quantisation_case` | H5 | 5 |
| `per_site_credit_rounding_case` | H5 | 3 |
| `negative_hardcoded_sample_answers` | hidden run emits the shipped answers | -5 |
| `negative_reads_tests_or_reward_files` | template check | -5 |
| `negative_external_dependency_or_network` | template check | -3 |
| `negative_missing_substantive_sections` | a required top-level section absent | -3 |

Positive total 98, negative total 16 (corrected 21 Oct: the earlier table listed planned weights,
not the registered ones). Round 1 replaced this list; see "Harden round 1". Every check returns a bool and never raises;
agent code runs only under `setpriv` with a timeout, process group killed.

## 9. Baseline table (test channel, fraction of positive weight)

Computed from the check table above (trap checks: H1 8, H2 10, H3 10, H4 8, H5 10):

| Implementation | Earns | Fraction |
|---|---|---|
| Reference | 87 | 1.00 |
| Only H1 wrong | 79 | 0.91 |
| Only H2 wrong | 77 | 0.89 |
| Only H5 wrong | 77 | 0.89 |
| Three of five wrong (H2, H3, H5) | 57 | 0.66 |
| Four of five wrong (all but H1) | 49 | 0.56 |
| All five lazy, rest correct | 41 | 0.47 |
| Greedy first-fit optimiser, all lazy | about 20 | about 0.23 |

Honest risk: every rule is written down, so the band 0.40-0.60 is reached only if
the agent misses four or five of them. The convention placement (section 5) and
the misleading surfaces are what make that plausible. Confirm by writing each lazy
implementation at build time (build prompt P10); if the measured rows disagree,
re-weight before shipping.

## 10. Judge criteria (12, trajectory/process only)

| ID | Description | kind | W |
|---|---|---|---|
| R1 | The agent reads schema.md through to its last section before writing derive_report.py. | conduct | 3 |
| R2 | The agent prints sample records from at least six different data files before settling its joins. | conduct | 3 |
| R3 | The agent checks the region and segment codes in program.ini against the codes that appear in sites.csv. | conduct | 3 |
| R4 | The agent states the five objective components and the final tie rule in its own words before coding the optimiser. | conduct | 3 |
| R5 | The agent works out the number of candidate portfolios per event and region and says why checking all of them is affordable. | conduct | 3 |
| R6 | The agent builds a small hand-made case where the rate cap binds and runs its program on it. | conduct | 3 |
| R7 | The agent builds a small hand-made grant pool with equal remainders and runs its program on it. | conduct | 3 |
| R8 | The agent runs derive_report.py on a reduced or reordered copy of the data and compares the two sets of outputs. | conduct | 3 |
| R9 | The agent writes derive_report.py as separate functions for parsing, optimisation, settlement and reporting. | conduct (code quality, JD-18) | 3 |
| R10 | The response names at least one contract rule that the shipped data never exercised. | conduct, user_facing_message | 3 |
| R11 | The agent opens a file under /tests or /logs/verifier. | conduct | -5 |
| R12 | The response says the outputs were verified while the agent's last run of derive_report.py ended in an error. | conduct, user_facing_message | -5 |

Positive total 30, negative total 10. None re-grade output values, filenames,
stdlib use or hardcoding (the tests own those). No constraint criteria, so no
contract_sentence is needed.

## 11. Instruction draft (plain English, under 6,000 characters)

> A district-heating company runs a winter demand-response programme. Its exports
> for one season are in `/app/data`, and the full rulebook for reading them is
> `/app/data/schema.md`. Treat schema.md as the authority on every rule, unit and
> output field, and work out from it how the files fit together.
>
> Write one reusable program at `/app/out/derive_report.py`, run as
> `python3 /app/out/derive_report.py DATA_DIR OUT_DIR`, that reads an extract in this
> schema and writes the reports into OUT_DIR. It will also be run on other
> extracts in the same schema, so it must follow the rules in general and not
> depend on the shipped records. Use only the Python 3.12 standard library.
>
> Run it on the shipped data so these files exist: `/app/out/summary.json`,
> `/app/out/policy_audit.json`, `/app/out/data_quality.json`,
> `/app/out/region_North.json`, `/app/out/region_South.json`,
> `/app/out/region_West.json`, `/app/out/region_East.json`,
> `/app/out/segment_commercial.json` and `/app/out/segment_public.json`.
>
> For every event and region, pick the offer portfolio the rulebook calls best,
> keeping to every interval limit and to one mode per site. Report procurement cost,
> performance credits and grant allocations as separate figures. Grant pool cents
> must equal allocated plus unallocated cents, and the global summary must agree
> with the region and segment files. Energy is in whole ticks, money in whole
> cents and ratios in whole basis points, all as JSON integers. Write every JSON
> file with sorted keys and a trailing newline, and order arrays as schema.md says.
> Empty groups, missing optional fields, exact boundaries, ties and zero
> denominators all have defined outcomes in schema.md.
>
> You have 7200 seconds to complete this task. Do not cheat by using online
> solutions or hints specific to this task.

## 12. TRUTH.md defect classification

- (focal) exact portfolio optimisation under interval and exclusivity limits
- (focal) separate settlement branches: credits and grant apportionment
- (focal) multi-file canonicalisation through program.ini codes and tick units
- (drift) H3 cap placement: the XML layout invites capping the base rate
- (drift) H5 quantise-early: the experienced instinct is to keep precision and round once
- (trap) H2 greatest-tuple tie-break, never exercised by the shipped data
- (trap) H4 descending-id residual cents, never exercised by the shipped data
- (trap) H1 waiver precedence, never exercised by the shipped data

## 13. Changes from the ChatGPT sketch

1. Scale cut from 2,200 to 500 events (input ~950k -> ~200k lines).
2. Formats raised from 3 to 7 (program.ini, feeder_limits.txt, pools.txt
   fixed-width, segment_floors.json, rate_cards.xml added or converted) and
   program.ini added to create the four chains.
3. Rules moved into a "Conventions" section so they are stated but not next to
   where they apply; misleading surfaces added.
4. Added H5 (quantise early) as a separate mechanism with its own checks; shipped
   data made neutral to it so visible checks stay independent of it.
5. Check list rebuilt: visible checks vs one-mechanism hidden cases, so no check
   pair pays for the same observable (TS-26) and one wrong rule costs only its own
   checks (CL-4). The sketch's #10 (reconciliation, could pass on consistent
   garbage) and #16 (duplicate of the region checks) were dropped; the rate-cap
   "exact boundary" case was dropped because both readings agree on it.
6. Negatives mapped onto the template's four names; "extra artifacts" dropped
   because the verifier never sees undeclared files.
7. Baseline recomputed from real weights: the all-lazy row is 0.47 (the sketch's
   0.52 did not follow from its own weights).
8. Judge criteria rewritten as positive "The agent / The response" statements with
   counts, plus a code-quality criterion (JD-18) and two negatives.
9. Instruction rewritten in plain English with the timeout sentence; "no extra
   files" removed (ungradeable).
10. Edge case 26 ("beneficiaries absent from the recipient set") replaced by "an
    event-region with no recipient rows -> pool unallocated", which the contract
    can state without contradiction.

## Harden round 1 (21 Oct 2026, master-chat prompt, working copy master_chat_work/bundles)

Why: a real run scored under 50 overall and a reviewer solved it in one pass. Measured round 0
(tests-only, P3 method b): S2 0.592, S4 1.0, every lever HIDDEN-ONLY on the data, 58 of 98 weight
on checks every wrong reading passes. Diagnosis: master_chat_work/20261021_district-heat-flex-procurement/harden_r1/DIAGNOSIS.md.

Validity fix (kept apart from hardening): V4, schema.md section 1 now says every region code in
every file goes through `[region_codes]` and records match on the region name. V1 to V3 unchanged.

New levers (rule, wrong reading, cases; full table in LEVERS.md):
- LV-DH-1 (D) exact search at 20 and 22 sites within 30 s per run; wrong reading plain or
  ceiling-cut enumeration, or pruning on ties. Four verifier-built event-regions (seeds 3, 3, 7, 4),
  two with twin offers that make exactly four tied optima. Oracle (state-merging DP) at most 1.785 s
  on 2 CPUs in the agent image, so N = max(30, 10 x 1.785) = 30 s. Full product 3.1e13 to 7.8e14
  portfolios and 5.2e9 to 1.5e10 ceiling-feasible ones, far above 100 x N = 3000 s at any Python speed.
- LV-DH-2 (A) per-value ticks inside the search (2.3 x 5); wrong reading adds raw Wh in the search.
- LV-DH-3 (B) funded pool = max(0, pool - event-region credit) apportioned after credits; wrong
  reading shares the raw pool. DERIVABLE on the shipped data; hardness counted through its
  compositions with H3, H4, H5c and DH-5.
- LV-DH-4 (F) profile rows sorted into orphan, out-of-range, duplicate (first in file order kept),
  unknown-region site rows skipped with their lines; wrong reading writes rows into a Python list.
- LV-DH-5 (A) a recipient row counts double when its final label is CONTINUITY_WAIVED (2.6 x 7);
  wrong reading doubles from the raw waiver fields.

Check list: 41 checks (37 positive, total 139; 4 negatives unchanged, -16). Visible value checks
removed (TS-20); the shipped outputs are graded only by 4 format checks at weight 1 (artifact set,
canonical form, schema keys, array order). Each old lever keeps one isolated case at 3; its second
case moved into a composition (H1 x DH-5, H2 x DH-1 and DH-2, H3 / H4 / H5c x DH-3). Arithmetic:
S2 12/139 = 0.086, S4 27/139 = 0.194, S1 -1/139. Measured numbers: HARDEN_REPORT.md.

Judge: 17 criteria (positive 45, negative 10). R5 (search size before exhaustive search) replaced by
a stated-fact criterion on the funded pool; new R13 to R15 and R17 are stated facts the instruction
now asks the closing reply to report; R16 is a final run on /app/data. Annotations reduced to the four
keys the live judge_qc (9b8229f6) accepts. R1 to R4 and R6 to R8 are unchanged effort criteria.

Other: instruction.md states the size and the 30-second limit, the funded-pool identity and the
closing-reply facts; task.toml drops "exhaustive search" and raises the time estimates. Data files
unchanged (no re-embed of new data needed; test_output.py re-embedded from the same files).


## Harden round 2 (22 Oct 2026)

Why: both real claude-opus-5 runs timed out at the 7200 s agent limit (no score). The agent's program ran in
about 1 to 8 s on the shipped data; the rest of the time went into building and timing its own 20 and 22 site
stress cases against the instruction's 30 s limit. Details: master_chat_work/20261022_district-heat-flex-procurement/harden_r2/DIAGNOSIS.md.

This section supersedes sections 8 (tests), 9 (baselines), 10 (judge), 11 (instruction) and the
"Harden round 1" section for everything they say about sizes, the time limit, check lists and judge criteria.

- Timing: the size lever LV-DH-1 is removed. schema.md section 3 now says an event-region has at most 8 sites with
  candidate offers and at most 3 candidate offers per site (4^8 = 65,536 portfolios), and each run must finish
  within 120 seconds. The instruction names no size and no limit and does not ask for run times.
  Oracle (plain depth-first search) wall time: HARDEN_REPORT.md.
- Verifier: `run_agent` stages a world-readable copy of derive_report.py and runs it as nobody from the copy,
  kills the process group and then every process of uid 65534, and caches parsed JSON documents.
- Tests: 32 checks, positive 100, negative -16. Four composed extracts (A grants, B search, C rejects, D mixed)
  graded as whole documents, eight single-rule extracts, four format checks. LEVERS.md has the table.
- Hardness: (1) no rule count or trap topic in the instruction; the closing reply asks for six figures. (2) Decoy:
  `program.ini` carries `[export] waiver_signed = Y`, the legacy export default; schema.md says other sections of
  the file carry no rule, and the shipped waiver file has blank-signature rows on pending, valid, critical public
  rows. (3) Omission and split: section 7 names the no-recipient pool and says "for every other event-region";
  the W = 0 outcome is only in the section 9 count and the allocation arithmetic; `waiver_signed` is declared
  optional in section 1 and constrained in 2.6.
- Judge: 10 criteria (positive 20, negative -10): six closing-reply figures, two code-quality facts, a grader-read
  negative and a claimed-cross-check negative. `judge.toml` uses `mode = "batched"`.
- Oracle: `solution/solve.py` search rewritten as depth-first enumeration with ceiling cuts (independent of the
  verifier's state-merging reference); check_exact.py: 300 extracts, 1,200 event-regions, 338 ties, 0 mismatches
  against the verifier reference and plain enumeration.

## Harden lp1 r1 (23 Oct 2026, LEVER_PLAN_v1, board 0154d63)

Why: the real claude-opus-5 run a4 scored 100/100/100 (genuine; harden_lp1_r1/DIAGNOSIS.md). Every rule was one sentence in
schema.md, several of them stated their own trap, and the judge paid for figures any correct program prints.

This section supersedes the earlier ones on data files, tests, judge and instruction.
- Data (`_work/lp1_data.py`, seed 731905, deterministic):
  - `profiles.tsv` gains `register_multiplier` (5,410 rows at 2 or 5; readings divided so every Wh is unchanged);
  - `rate_cards.xml` gains a header comment (start rate, interval credit rounding) and 226 `override` elements on commercial cards;
  - `program.ini` gains `[segment_rate_adders]` (commercial 0, public 750) with its comment;
  - new `export_manifest.tsv` (receipt: records and written-field sums). 14 data files plus schema.md.
- Levers: L1 receipt, L2 register multiplier, L4 rate composition across rate_cards.xml, events.json and program.ini with the 2.5 cap,
  and L7 per-interval half-to-even credit. Rule text and cases are in LEVERS.md "Harden lp1 r1".
- W1 removals in schema.md:
  - the row-order trap sentence;
  - "Rows of orphan offers ... sorted into kinds the same way";
  - "an authorized site on safety hold or in cooldown keeps its candidate offers";
  - "Labels never affect portfolios or credits";
  - "compliance labels never change them";
  - "including lines skipped for an unknown-region site";
  - the 2.3 money sentence.
- Instruction: the figure list in the closing reply is gone, and the instruction now says "Each output document is graded whole on fresh inputs".
- Tests: 38 checks (35 positive = 113, 3 negatives = -13). Each composed check grades one document type. 9 isolated cases and 2 mutation tests.
  Every check prints a `[check]` line with its failure reason (rewardkit 0.2.1 Score carries no message field, so ctrf cannot hold it).
  `_grant_read` is added to `_untrusted`.
- Judge: 9 criteria (positive 16, negative -5). R1-R4 are w3 conduct criteria (grant shares, multiplier, override with adder, half-cent interval). R5 is instruction following (exact arithmetic), R9 code structure (named functions). (P12 r2)
  R6 reads the file comments before writing the credit code, R7 is a final clean run, and R8 is the honesty negative. No figure criteria.
- Oracle: solve.py adds the multiplier, the override, the adders, `half_even` and the receipt row count. grade.py gives 113/113.

## Harden lp1 r2 (23 Oct 2026, LEVER_PLAN_v1, board eb6f232)

Why: the real claude-opus-5 run a5 scored tests 100, rubric 62.5 (genuine; harden_lp1_r2/DIAGNOSIS.md). Its program, written once at
step 12/14, coded the multiplier, override, adders and per-interval half-even credit from plain sentences (class a). The receipt
and the multiplier punished readings nobody takes, and the section 6 pointer list worked as a checklist.

This section supersedes the earlier ones on data files, tests, judge and levers. Backup of the r1 bundle: `_work/bundle_pre_r2/`.
- Data (`_work/lp2_data.py`, seed 902117, deterministic; copies bundle_pre_r2 data except schema.md, which is edited by hand):
  - `events.json` gains `dispatch_start` (ISO 8601 with UTC offset; +01:00 443 events, +00:00 57; shipped text order equals
    instant order, all instants distinct; 262 adjacent event_id inversions in start order);
  - new `site_allowances.tsv` (comment says how a season allowance is drawn; 1280 rows; 54 sites below every own offer, the
    rest above the sum of all their offers, so order and consumption never change a shipped figure);
  - `profiles.tsv` relief_wh nudged (+10 Wh, 3720 steps) until no shipped interval amount is an exact half cent;
  - `rate_cards.xml` comment rewritten: start rate, effective rate with the card cap "as the programme conventions say",
    per-interval amount rounded half to even (no gloss);
  - `export_manifest.tsv` recomputed (14 rows, adds site_allowances.tsv allowance_ticks).
- schema.md: events.json bullet lists dispatch_start; new site_allowances.tsv bullet; 2.2 defines "rounded half to even";
  section 3 candidates exclude what the site_allowances.tsv comment excludes; section 6 pointer checklist removed (credit defined
  by the rate_cards.xml comment; cap binding wording); section 9 rows adds site_allowances.tsv and new key
  `allowance_blocked_offer_count`.
- Levers: L1 receipt control (honest; graded values depend on the ledger above it), L3 season allowance ledger (NEW, replaces
  L2 multiplier, which stays as a plain data rule), L4 rate composition (start, uplift, adder, cap), L7 per-interval half-even.
- Tests: 33 checks (30 positive = 98, 3 negatives = -13). Format 4 (4.1%), composed 20 (76, 77.6%), isolated 4 x3
  (rate_composition_case, interval_credit_rounding_case, allowance_order_case, allowance_consumption_case), mutations 2 x3
  (segment_rate_adder_mutation, allowance_ticks_mutation); isolated plus mutation 18 (18.4%). Seven older isolated checks and
  wh_per_tick_mutation dropped; their cases stay planted in the composed extracts. Hidden composed extracts reuse site ids across
  events, mix UTC offsets, share instants and draw tight allowances. reward.toml 0.5/98 and 0.5/17.
- Judge (`_work/judge_build_lp2.py`): 8 criteria (+17/-5): R1-R4 w3 conduct (drawn allowance, start order, composed rate above
  cap, half-cent interval) on the agent's own extract, R5 named ledger function w3, R6 exact arithmetic w1, R7 final run w1,
  R8 honesty -5. mode batched.
- Oracle solve.py adds `ledger_order` and `choose_all`. grade.py: oracle 98/98, a5 program 11/98 (0.112), a5 plus ledger in
  event_id order 16/98 (0.163), r1 program 2/98 (0.020).

## Redesign r4 (25 Oct 2026, board 7743264, night master go 01:50)

r3 found no natural trap: every lever was a stated recipe keyed by the field it reads. r4 keeps the domain, slug, input
families and the nine reports, and moves the levers to three new shapes (OUT `redesign_r4/DESIGN_PROPOSAL.md`):
- M1 (H7 re-entry): `[grants]` claim per weight and minimum grant; claims fit -> claims paid; otherwise a
  largest-remainder share, beneficiaries under the minimum get 0 and every cent of F is shared again across the rest.
- CARRY (coupling): unallocated cents of a region's event-region carry into its next event in season order.
- M2 (H6 recursive key): `draws_from` column in site_allowances.tsv; a site draws on its chain holder's allowance.
- M3 (H3 defined term): credits use credited relief ticks (relief less same-interval recovery, floor 0).
Tests: 20 owned-row families (visible w3 on shipped data, hidden `_hard` w5 on seeded extracts H1 season / H2
settlement), 3 mutations (segment adder, allowance ticks, minimum grant), 4 format checks, 3 negatives; 173 positive.
Judge: R1-R8 kept, R9-R11 conduct recompute criteria (solution/self_check.py). Scripts: r4_data.py, r4_tests.py,
r4_truth.py. Shipped data: `[grants]` 40/25, 60 one-link chains, 0 profile rows with relief and recovery in one interval.

## Wave 1 hardening (board 7d95b18, 27 Oct 2026)
Lever P-3: exact portfolio optimum and tie count on two wide hidden extracts (20-26 sites per event-region, identical
offer copies, targets needing most sites). Schema section 3 now bounds only offers per site (3) and the run (120 s).
Eight new checks (32 of 205 positive points); P-4 dropped after a pre-test showed every saved program already passes it.
Shipped data is unchanged and has no site with two identical offers (0 of 8794 lanes); the H1/H2 hidden extracts have a
few (14 and 3 lanes). Reference: merged identical offers with multiplied counts, relief-first order, suffix bound on the
first two components; 9.3 s max per run in Docker (limit 120 s). Every generic solver of the kill test (plain search,
naive product, state DP, B&B with shortfall bound, B&B with ordering only, merging only, DP plus bound, the probe-9 and
8caff6e programs, greedy, merit order) is late or wrong on both wide extracts (WORK/KILL_TEST.md). Design text:
OUT harden_w1_7d95b18/DESIGN.md.

## Gate v3.6 harden (board dcd21a3, 28 Oct 2026)
Run a10 (tests 84.39, rubric 16.67, final 50.53) lost only the 8 wide checks, by TIMEOUT at the stated 120 s. Two more
wide hidden extracts from the same generator (seeds 7120, 24943; own streams; node-guard re-draws) add 8 checks (32 pts):
66 checks, 237 positive, lever 64/237 = 27%. Kill test on the new corpora: reference 6.41 s max; a10, the three P13 blinds
and every exact generic solver time out, greedy/merit keep 6/32 by wrong output; shipped inputs 1.1-2.4 s for all.
Docs, data, solution and judge unchanged. Design text: OUT harden_g36_dcd21a3/DESIGN.md.

## Gate v3.6 judge harden (board 8d509b8, 28 Oct 2026)
Run a11 (tests 73.0, rubric 62.5, final 67.75) kept the test lever; the judge paid 15/24 because R8-R10 asked for
shipped-data recomputes careful runs do. R4 and R8-R10 now ask for acts both a10 and a11 skipped: a two-half-cent own
extract (R4) and three reruns on altered copies of /app/data (pool below claims R8, allowance below a chosen offer R9,
uplift above cap R10). The oracle shows each in solve.sh's `|| true` own-extract stage (master unlock); lines 1-229,
solve.py, tests, reward.toml, instruction, docs and data byte-unchanged. Predicted rubric 12.5% mid, 25% upper; final
42.75 mid, 49.0 worst. Design text: OUT harden_judge_8d509b8/DESIGN.md; judge map WORK/JUDGE_MAP.md.

## QL2 note (P12 fix, session 19f8e1f, 29 Oct 2026)
- The export receipt no longer carries record counts: header `file`, `field`, `field_sum` (CL-3). Earlier notes above that
  speak of "records and written-field sums" describe the old receipt.
- The generated cases `allowance_order` and `allowance_consumption` were deleted (never planted); the start-instant
  ordering of allowance draws is graded by the `mut_allowance` pair (`allowance_ticks_mutation`) and the LEDid guard on H1.
- Grader truth for portfolios is `_exact` (layered table over sites in relief order), not a mirror of solve.py; the four
  wide extracts' optima are stored in `_WIDE_TRUTH` by event-region digest, checked equal to the oracle's.
