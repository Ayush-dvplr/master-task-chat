IST 2026-10-28 (received 29 Oct 02:30) | from QL (Sugam) | task district-heat-flex-procurement | frozen tree e9d91966ed25
Numbering: QL1-F1..QL1-F11 = Issues 1..11 in section 3 (master, 29 Oct 03:58).

# QC Report: district-heat-flex-procurement

| Field | Value |
|---|---|
| Task | `district-heat-flex-procurement` (`terminal-bench/district-heat-flex-procurement`, version 1.0.0) |
| Tasker | Ayush sah (task author in task.toml: Ayush Sah) |
| Bundle location | `/Users/apple/Desktop/Terminal Tasks/Anubis_Tasks_Samples/Pass@1_New/Sugam_Agrawal/Ayush sah/district-heat-flex-procurement` |
| QC date | 2026-10-28 |
| Reviewer | Sisyphus (QC agent) |
| QC framework | `Terminal_2.0_Harbor_Harness/Input_Bundle_QC` (Starter.md, Final_checklist.md, gates 01 to 05, Steps 10 and 11) |

**Verdict: ❌ FAIL (7 fails, 1 minor, 3 warns)**

---

## 1. Task summary

### What the agent is asked to do (`instruction.md`)
- The scenario is a district-heating company's winter demand-response programme. One season of exports sits in `/app/data`, and `/app/data/schema.md` is the rulebook for every rule, unit and output field.
- The agent must write one reusable program at `/app/out/derive_report.py`, run as `python3 /app/out/derive_report.py DATA_DIR OUT_DIR`, using only the Python 3.12 standard library.
- The program "will also be run on other extracts in the same schema, so it must follow the rules in general and must not depend on the shipped records."
- The agent must run it on the shipped data so that nine reports exist in `/app/out`:
  - `summary.json`, `policy_audit.json`, `data_quality.json`
  - `region_North.json`, `region_South.json`, `region_West.json`, `region_East.json`
  - `segment_commercial.json`, `segment_public.json`
- Output rules:
  - Each report is "graded whole on fresh inputs".
  - The best portfolio must be picked for every event and region.
  - Energy is in integer ticks, money in integer cents and ratios in integer basis points.
  - JSON keys are sorted, each file ends with a trailing newline, and arrays are ordered as schema.md says.
- The agent must finish with a short reply describing what the program does and how it was checked.
- Agent time limit: 7200 seconds.

### Shipped input (`environment/data`, copied to `/app/data`)
- **Files:** 16 in total. `schema.md` is the rulebook (358 lines). The other 15 data files cover seven formats: ini, json, jsonl, csv, tsv, fixed-width txt and xml.
  - `program.ini`, `events.json`, `sites.csv`, `offers.csv`, `profiles.tsv`, `targets.tsv`
  - `feeder_limits.txt`, `site_state.jsonl`, `continuity_waivers.csv`, `segment_floors.json`
  - `rate_cards.xml`, `recipient_weights.tsv`, `pools.txt`, `site_allowances.tsv`, `export_manifest.tsv`
- **Size:** 500 events, 10,000 site rows, 18,014 offers, 108,036 profile rows and 2,000 event-regions (4 regions × 500 events).
- **Rules outside schema.md:** several rules live in comment lines of the data files themselves (`rate_cards.xml`, `site_allowances.tsv`, `program.ini`, `export_manifest.tsv`).
- **Deliberate traps:**
  - `program.ini [export] waiver_signed = Y` is not a programme rule.
  - `export_manifest.tsv` claims that the files "arrived whole", although orphan offer and profile rows exist.

### Core work the task demands
1. **Parsing and counting.** Parse 15 linked files. Scale meter readings by `register_multiplier`. Reject and count orphan, out-of-range and duplicate profile rows, orphan offers and unknown-region site rows.
2. **Allowance ledger.** Keep a season-wide site allowance ledger. Events are walked in order of their start instant (UTC offsets differ), and `draws_from` chains are followed. An offer whose relief exceeds what remains of its allowance is not a candidate.
3. **Portfolio choice.** For every event-region, find the exact best portfolio under per-interval relief and recovery ceilings, with at most one offer per site. Portfolios are compared lexicographically on five components: weighted shortfall, weighted floor deficit, blended cost, overdelivery and offer count. Remaining ties go to the greatest sorted id tuple, and tied portfolios are counted.
4. **Credits.** Settle capped performance credits. Rates are composed from the base or override value in `rate_cards.xml`, the event uplift and the segment adder, and each interval amount is rounded half to even.
5. **Grant pools.** Fund each grant pool after credits and carry unallocated cents between events. Pay claims, or share the pool by largest remainder with doubled weight for waived sites. Drop shares below the minimum grant, re-share the pool, and track residual cents and remainder ties.
6. **Reports.** Write nine exact JSON reports.

### How the bundle grades (`tests/`)
- **Tests channel** (`tests/test_output.py`, 2.4 MB, 66 checks, positive weight total 237, negative total -13):
  - 4 format checks (weight 1 each).
  - 20 value families. Each is checked on the shipped extract (weight 3) and on a seeded hidden extract built at grade time (`_hard`, weight 5).
  - 16 checks on four large "wide" extracts (weights 3 and 5).
  - 3 mutation checks (weight 3 each).
  - 3 negative checks (weights -5, -5 and -3).
  - Every value check reruns the agent's program as user `nobody`, with a 120 s limit, and compares its output with an embedded reference implementation of schema.md. The shipped data is embedded in the test file as zlib and base64 blobs.
- **Judged channel** (`tests/judge.toml`, judge `openai/gpt-5.6-sol`): 11 binary criteria, positive total +24 and negative -5.
  - R1 to R4 reward building and checking the agent's own small extracts.
  - R8 to R10 reward rerunning the program on altered copies of the shipped data.
  - R5 covers exact arithmetic, R6 a final run after the last edit, R7 (negative) a fabricated check claim, and R11 the maintainability of the program.
- **Reward weights** (`reward.toml`): `test_output = 0.5/237` and `judge = 0.5/24`.

### Reference solution (`solution/`)
- `solve.sh` copies `solve.py` (612 lines, standard library only, integer arithmetic, exact branch-and-bound search) to `/app/out/derive_report.py` and runs it on `/app/data`.
- It then runs its own outside recomputations and builds hand extracts and altered copies.
- `TRUTH.md` documents the focal rules, the traps and the measured scores.

### task.toml highlights
- Category `Optimization`.
- Agent timeout 7200 s. Verifier timeout 2700 s, run in a separate environment.
- Agent environment `no-network`, 2 CPUs, 4096 MB memory.
- Expert estimate 360 min; junior estimate 1080 min.

---

## 2. QC performed

- **Process:** Starter.md followed top to bottom. Final_checklist.md and all five gate files (01 Instruction, 02 Data & Solution, 03 Tests, 04 Judge, 05 Alignment & Integrity, including CL-1 to CL-10) were read in full, and every checklist item was evaluated. TRUTH.md was read only after solvability had been decided.
- **Scripts:** `structure_qc.py`, `instruction_qc.py`, `tests_qc.py` and `judge_qc.py` were all run.
- **Step 10:** executed through `HQ_JOB_QUEUE.md` on copies made by `exe_copy.py`. Run counts were set by the operator: oracle ×2, nop ×1, stub ×1, owner-only ×1.
- **Step 11:** coverage and overlap re-check done.
- **Local reproduction (on copies only; the bundle was never edited):**
  - The embedded reference implementation was run on all 13 graded extracts: shipped, hidden H1, hidden H2, wide 0 to 3, and the six mutation extracts.
  - More than 60 single wrong readings of the contract were patched into a copy of the reference and scored against every registered check.
  - Every graded extract was scanned for whether each stated rule's condition actually occurs.
  - Forged and constant programs were scored to price forgery.
- **Scope:** five root entries (`environment/`, `instruction.md`, `solution/`, `task.toml`, `tests/`). `trajectories/` and `output/` are out of scope by operator instruction.

---

## 3. Issue index

| # | Severity | Check ID(s) | Issue |
|---|---|---|---|
| 1 | ❌ Fail | TS-25, CL-2 | The shipped-extract `tie_decisions_match` (weight 3) grades an empty list, so it pays a program that never detects ties |
| 2 | ❌ Fail | AL-2, Step 11 coverage | The instruction's reply-report requirement is graded only by a negative criterion; no positive test or criterion covers it |
| 3 | ❌ Fail | AL-27 | `[units]`, `[region_codes]` and `[segment_codes]` never vary in any graded extract, so hardcoding the shipped values loses nothing |
| 4 | ❌ Fail | AL-27 | The rule "A segment name with no option has an adder of 0" is never triggered |
| 5 | ❌ Fail | AL-27 | The rule "An interval with no kept row means 0 Wh of both" is never triggered |
| 6 | ❌ Fail | AL-27 | The rule that only offers chosen in earlier events draw an allowance (never offers in the same event) is never exercised |
| 7 | ❌ Fail | AL-27 | The equality boundaries "add up to F or less" (claims) and "more than what remains" (allowance) are never reached |
| 8 | 🟡 Minor | JD-5 | Judge criterion R3 grades two report figures in one binary verdict |
| 9 | ⚠️ Warn | TS-23 (tests_qc A3) | 66 test checks, above the 35-check cap |
| 10 | ⚠️ Warn | TS-16 | The negative check penalises standard-library network modules, although the instruction only says "standard library" |
| 11 | ⚠️ Warn | TS-28 | The agent's program inherits the verifier environment, including `OPENAI_API_KEY` |

---

## 4. Issues and evidence

### Issue 1: ❌ Fail (TS-25, CL-2). The shipped-extract `tie_decisions_match` grades an empty list and pays a program that never detects ties

**Type:** Bug/Error

**What is wrong**
- The positive check `tie_decisions_match` (weight 3) compares the `tie_decisions` array of `policy_audit.json` produced on the shipped extract.
- On the shipped extract the correct value is the empty list, because no event-region has a tie.
- So the check pays any program that never detects ties or always writes `[]`. In effect it grades an absence.
- Its description claims it checks content: "reports the tie_decisions entries … exactly as the contract defines them".
- It can only fail a program that invents spurious ties.

**Where**
- `tests/test_output.py` L1922-1924:
  ```python
  @criterion(description="Run on the shipped extract, the program reports the tie_decisions entries of policy_audit.json exactly as the contract defines them.")
  def tie_decisions_match(workspace: Path) -> bool:
      return _graded("tie_decisions_match", lambda: family_passes(workspace, "tie_decisions", False))
  ```
- `tests/test_output.py` L1493 (projection): `"tie_decisions": lambda f: f["policy_audit.json"]["tie_decisions"],`
- `tests/test_output.py` L2370 (registration): `criteria.tie_decisions_match(weight=3)`
- `environment/data/schema.md` L322-325 (definition): "`tie_decisions`: one `{event_id, region, tied_portfolio_count, selected_offer_ids}` entry for every event-region where two or more feasible portfolios are equal on components 1 to 5 at the best value …"

**Evidence (computed on copies; bundle untouched)**
- The embedded reference implementation, run on the shipped extract, gives `policy_audit.json` with `"tie_decisions": []` (with `cap_binding_count` 383, `residual_cents` 0, `residual_tie_pool_count` 0).
- A scan of best-portfolio ties found 0 tied event-regions in the shipped extract, out of 2,000. For comparison, hidden extract H1 has 2 and each wide extract has 80.
- A constant program was built that writes the same zero-valued reports of the correct shape for any input, including `"tie_decisions": []`. It was scored against all 59 value checks (40 family, 16 wide, 3 mutation). It passes `tie_decisions_match` and no other value check.
- **Forgery price (CL-2):**
  - Hand-written fake reports of the correct shape pass the 4 format checks (4/237 = 1.69% of the test positive weight).
  - Adding the constant program raises the total to 7/237 = 2.95%.
  - The 3 points from `tie_decisions_match` come from a test that believes it is grading content. That makes this a content-paying forgery path, not a format point.
- Tie detection is actually exercised only by `tie_decisions_match_hard` (weight 5, L2371) and `wide_0..3_tie_decisions_match` (weight 5 each, L2408, L2412, L2416, L2420). The shipped-extract variant adds no tie coverage and pays an empty answer.

---

### Issue 2: ❌ Fail (AL-2; Step 11 coverage). The reply-report requirement is not positively graded by any test or criterion

**Type:** Bug/Error

**What is wrong**
- The instruction requires a final reply describing what the program does and how it was checked.
- No test and no positive judged criterion grades that reply.
- The only criterion that reads the response is the negative R7, which penalises a false claim of a passing check.
- So an agent that sends no report, or a report that omits what the program does or how it was checked, loses nothing.
- Skipping the report also removes any exposure to R7's -5. The scoring therefore favours silence over the requested report.

**Where**
- `instruction.md` L9: "When you finish, reply with a short report of what the program does and how you checked it."
- `tests/judge.toml` L91-99, R7, the only criterion whose target is the response:
  - `name = "r7_claims_a_check_its_output_contradicts"`
  - `description = "The response says a check of derive_report.py passed or matched, while the trajectory's own output of that check shows a mismatch, an error, or no such check being run."`
  - `weight = -5`
  - `evaluation_target = "user_facing_message"`
- `tests/judge.toml`, targets of every other criterion:
  - R1 L21, R2 L34, R3 L47, R4 L60, R5 L73, R6 L86, R8 L112, R9 L125, R10 L138: `evaluation_target = "trajectory"`
  - R11 L151: `evaluation_target = "state_change"`
- `tests/test_output.py`: all 66 checks read either `/app/out/*.json` (format checks) or the outputs and source of `/app/out/derive_report.py` (value checks and negatives). None reads the agent's reply.

**Evidence**
- Requirement-to-checker mapping (Step 11 coverage): instruction L9 maps only to the negative R7. No checker rewards meeting the requirement, and leaving the reply out is never penalised.

---

### Issue 3: ❌ Fail (AL-27). `[units]`, `[region_codes]` and `[segment_codes]` never vary in any graded extract, so hardcoding the shipped values costs nothing

**Type:** Bug/Error

**What is wrong**
- Schema.md makes `program.ini` the source of the tick size, the mill-cents-per-cent factor and the feeder-code and segment-code maps.
- The instruction says the program "must follow the rules in general and must not depend on the shipped records".
- Every graded extract carries exactly the shipped values for these three sections: the shipped extract, hidden H1 and H2, wide 0 to 3, and the six mutation extracts.
- So a program that hardcodes `wh_per_tick = 10`, `millicents_per_cent = 1000`, `N1/N2=North … E1/E2=East` and `C=commercial, P=public` produces identical outputs on every graded input and keeps the full test score.
- If the program broke these rules, no graded input would change.

**Where**
- `environment/data/schema.md` L19-22:
  - "`[units]`: `wh_per_tick` (Wh in one energy tick) and `millicents_per_cent`."
  - "`[region_codes]`: each option is a feeder code and its value is the region name"
  - "`[segment_codes]`: each option is a segment code and its value is the segment name."
- `environment/data/schema.md` L114-115: "Energy in every report is counted in ticks; one tick is `wh_per_tick` Wh. … `millicents_per_cent` mill-cents make one cent …"
- `instruction.md` L3: "It will also be run on other extracts in the same schema, so it must follow the rules in general and must not depend on the shipped records."
- `tests/test_output.py` L789-791 (`write_extract`, which writes `program.ini` for every hidden, wide and mutation extract):
  ```python
  ini = f"[units]\nwh_per_tick = {spec.get('wh_per_tick', 10)}\nmillicents_per_cent = 1000\n\n[region_codes]\n"
  ini += "".join(f"{c} = {r}\n" for r, codes in REGION_CODES.items() for c in codes)
  ini += "\n[segment_codes]\n" + "".join(f"{k} = {v}\n" for k, v in SEGMENT_CODES.items())
  ```
- `tests/test_output.py` L43-44:
  - `REGION_CODES = {"North": ("N1", "N2"), "South": ("S1", "S2"), "West": ("W1", "W2"), "East": ("E1", "E2")}`
  - `SEGMENT_CODES = {"C": "commercial", "P": "public"}`
- The shipped `environment/data/program.ini` holds the same values: `wh_per_tick = 10`, `millicents_per_cent = 1000`, `N1 = North` … `E2 = East`, `C = commercial`, `P = public`.

**Evidence**
- In `tests/test_output.py`, `wh_per_tick` appears only at L166 (the reference reads it) and L789 (the default `10`). No spec ever sets `wh_per_tick`. `millicents_per_cent = 1000` is a literal.
- The planted unknown-region code `Z9` only checks that a code is absent from the map. A hardcoded map treats it the same way.
- By contrast, `[grants]` and `[segment_rate_adders]` values do vary across graded extracts, which shows the generator can vary `program.ini`. It never varies these three sections.

---

### Issue 4: ❌ Fail (AL-27). The rule "A segment name with no option has an adder of 0" is never triggered

**Type:** Bug/Error

**What is wrong**
- Schema.md states a default for a segment with no option under `[segment_rate_adders]`.
- Every graded extract writes an adder option for both segments.
- So a program that crashes on a missing option, or applies some other value, loses nothing.

**Where**
- `environment/data/schema.md` L23-25: "`[segment_rate_adders]`: each option is a segment name and its value is an integer in mill-cents per kWh; the comment above the section says how it applies. A segment name with no option has an adder of 0."
- `tests/test_output.py` L794 (`write_extract`): `ini += "".join(f"{g} = {v}\n" for g, v in sorted(spec.get("adders", {"commercial": 0, "public": 0}).items()))`
- Every spec that sets adders sets both segments:
  - L981 `"adders": {"commercial": 0, "public": 1500 if name == "mut_adder_moved" else 500}`
  - L1147 `"adders": {"commercial": rng.pick([0, 0, 250]), "public": rng.pick([500, 750, 1250])}`
  - L1421 `"adders": {"commercial": 0, "public": 750}`
- The shipped `program.ini` `[segment_rate_adders]` also has both: `commercial = 0` and `public = 750`.

**Evidence**
- A scan of all 13 graded extracts found a missing segment adder option in 0 of 13.

---

### Issue 5: ❌ Fail (AL-27). The rule "An interval with no kept row means 0 Wh of both" is never triggered

**Type:** Bug/Error

**What is wrong**
- Schema.md defines what an interval with no kept profile row means.
- Every live offer in every graded extract has a kept profile row for every interval of its event.
- So a program that crashes, drops the offer, or carries a previous value forward when an interval row is missing keeps the full score.

**Where**
- `environment/data/schema.md` L57-59: "… its recovery in Wh is its `recovery_wh` times its `register_multiplier`. An interval with no kept row means 0 Wh of both."
- `tests/test_output.py` L833 (`write_extract`), which writes one profile row per interval for every offer: `profile_body = [[o["offer_id"], t + 1, o["r"][t], o["v"][t], o["m"][t]] for o in offers for t in range(len(o["r"]))]`
- The extra rows that the hidden specs append are duplicates, out-of-range rows or orphan rows. They add rejected rows but never remove an in-range row.

**Evidence**
- A scan of all 13 graded extracts counted (live offer, interval) pairs with no kept row. The count was 0 in every extract.

---

### Issue 6: ❌ Fail (AL-27). The rule that only offers chosen in earlier events draw an allowance (never offers in the same event) is never exercised

**Type:** Bug/Error

**What is wrong**
- The allowance rule says what remains of an allowance when an event is reached is reduced only by offers chosen in the events reached before it.
- So offers chosen in one region of an event must not reduce the allowance seen by another region of the same event.
- The allowance limits candidacy offer by offer. It is not a joint limit on a portfolio.
- No graded extract contains a situation where these readings differ:
  - No allowance is drawn on by sites in two regions of the same event.
  - No event-region chooses several offers on one allowance whose combined relief exceeds what remains.
- So a program that deducts within an event, region by region, keeps the full score. So does a program that enforces the allowance jointly over a portfolio.

**Where**
- `environment/data/site_allowances.tsv` L6-11 (comment lines; binding per schema.md L4-6, "a comment that states how a file's own fields are read is binding"):
  > An allowance is drawn by the events of the season, which reach it one at a time in the order of the instants at which they start (dispatch_start in events.json), events that start at the same instant following the programme conventions. When an event is reached, what remains of an allowance is its allowance_ticks less the relief ticks, over all intervals, of the offers chosen in the events reached before it at every site that draws on it. An offer whose relief ticks over all intervals are more than what remains of the allowance its site draws on when its event is reached is not a candidate offer.
- `tests/test_output.py` L545-569 (reference): candidates for every region of an event are filtered against `left` (L554), the winners are collected in `drawn` (L566), and `left` is reduced only after all regions of the event are processed (L567-569).

**Evidence (computed on copies; bundle untouched)**
- A copy of the reference was patched to subtract each region's chosen offers from `left` before the next region of the same event is handled. Scored against every registered check, it got 237/237 with no check lost.
- A scan of all 13 graded extracts for allowances drawn on by site rows in two or more regions of the same event found 0 in every extract.
- A scan for event-regions whose chosen portfolio holds two or more offers drawing on one allowance found 0 in the shipped extract and 3 in H1. In none of them does the combined relief exceed what remains, so a joint per-portfolio reading also changes no graded value.

---

### Issue 7: ❌ Fail (AL-27). The equality boundaries "add up to F or less" (claims) and "more than what remains" (allowance) are never reached

**Type:** Bug/Error

**What is wrong**
- Two stated rules draw their line at equality, and no graded extract contains the equal case.
  - **Grant claims:** claims are paid in full when they "add up to F or less". A program using strict "less than F" would send the equal case to largest-remainder sharing. There the minimum-grant rule can drop a beneficiary and re-share, which gives different grants.
  - **Allowance:** an offer is excluded only when its relief is "more than what remains". A program that excludes on "equal to or more than" would drop an offer whose relief exactly equals what remains.
- Both off-by-one readings keep the full score.

**Where**
- `environment/data/schema.md` L230-236: "When there are no recipients, or W is 0, the whole funded pool is unallocated. When the claims of the beneficiaries with a positive weight add up to F or less, each of them receives its claim and the rest of F is unallocated. Otherwise F is shared by largest remainder: … A beneficiary whose share is less than `minimum_grant_cents` receives nothing. When some beneficiaries receive nothing this way and others do not, every cent of F is shared again …"
- `environment/data/site_allowances.tsv` L10-11: "An offer whose relief ticks over all intervals are more than what remains of the allowance its site draws on when its event is reached is not a candidate offer."
- `tests/test_output.py` L648 (reference, claims test): `if "CLAIM0" not in lazy and sum(claims.values()) <= funded:`
- `tests/test_output.py` L554 (reference, allowance test): `cands = [o for o in every if sum(tk(x) for x in o["r"]) <= left[drawn_on(o["site"]["sid"])]]`

**Evidence (computed on copies; bundle untouched)**
- With the reference patched to `sum(claims.values()) < funded`, every registered check still passes: 237/237.
- With the reference patched to exclude an offer when its relief is ≥ what remains (instead of >), every registered check still passes: 237/237.
- The claims boundary changes grants only when the claims equal F exactly and at least one claim is below `minimum_grant_cents`. Largest remainder with F equal to the total claims reproduces each claim exactly, so only the minimum-grant drop can separate the two readings. No graded extract contains that case.
- The allowance boundary changes candidacy only when an offer's relief equals exactly what remains of its allowance. No graded extract contains that case.

---

### Issue 8: 🟡 Minor (JD-5). Judge criterion R3 grades two report figures in one binary verdict

**Type:** Suggestion/Improvement

**What is wrong**
- R3 asks the judge for one yes/no verdict on two separate checks of two different report figures: `credit_cents` and `cap_binding_count`.
- For an agent that checks one figure by hand but not the other, the binary verdict is ambiguous. This breaks the rule of one observable per criterion.

**Where**
- `tests/judge.toml` L39-47 (R3):
  - `name = "r3_checks_a_composed_rate_above_cap_on_its_own_extract"`
  - L40 `description = "The agent constructs its own extract in which a chosen offer's rate card carries an override element, its event has a non-zero uplift and its segment a non-zero rate adder, with the resulting rate above the card's cap, runs derive_report.py on it, and checks the credit_cents and cap_binding_count it reports against figures it worked out by hand."`
  - L42 `weight = 3`
  - L47 `evaluation_target = "trajectory"`

---

### Issue 9: ⚠️ Warn (TS-23; tests_qc A3). 66 test checks, above the 35-check cap

**Type:** Suggestion/Improvement

**What is wrong**
- The test channel registers 66 checks, while the template cap is 35.
- Several are correlated:
  - The `summary` family re-reads rollups that, by contract, equal the sums of the region and segment totals, which are graded separately.
  - The region totals are four separate families per channel.

**Where**
- `tests_qc.py` output: `WARN [A3] 66 checks; cap is 35 (warn)`.
- `tests/test_output.py` L2362-2427 registrations:
  - 4 format checks (L2362-2365, weight 1).
  - 40 family checks: 20 families × shipped (weight 3) and `_hard` (weight 5).
  - 16 wide checks (4 extracts × 4 checks, weights 3 and 5).
  - 3 mutation checks (weight 3).
  - 3 negatives (L2425-2427: -5, -5, -3).
- `environment/data/schema.md` L313: "The global totals equal the sums over the region files and over the segment files."

---

### Issue 10: ⚠️ Warn (TS-16). The negative check penalises standard-library network modules, although the instruction only says "standard library"

**Type:** Suggestion/Improvement

**What is wrong**
- `negative_external_dependency_or_network` (weight -3) fires on any import of `socket`, `urllib`, `http`, `ftplib`, `smtplib`, `ssl` or `xmlrpc`.
- These are all Python 3.12 standard-library packages.
- The contract only limits the program to the standard library and never forbids these modules. A program that uses, for example, `urllib.parse` or `http.HTTPStatus` follows the instruction but still loses 3 points.
- An honest trip is unlikely for this file-only task, so this is filed as a warn.

**Where**
- `instruction.md` L3: "Use only the Python 3.12 standard library."
- `tests/test_output.py` L2342-2357:
  ```python
  @criterion(description="The delivered program imports a third-party or network module.")
  def negative_external_dependency_or_network(workspace: Path) -> bool:
      # True means the cheat happened: a non-stdlib or network import in the program.
      ...
          network = {"socket", "urllib", "http", "ftplib", "smtplib", "ssl", "xmlrpc"}
          return any(r in network or r not in sys.stdlib_module_names for r in roots)
  ```
- `tests/test_output.py` L2427: `criteria.negative_external_dependency_or_network(weight=-3)`

---

### Issue 11: ⚠️ Warn (TS-28). The agent's program inherits the verifier environment, including `OPENAI_API_KEY`

**Type:** Suggestion/Improvement

**What is wrong**
- The verifier runs the agent-written program as user `nobody` through `setpriv`. Neither the `Popen` call nor `setpriv` resets the environment.
- So the untrusted program inherits every verifier environment variable. That includes the judge's `OPENAI_API_KEY`, which `task.toml` injects into the verifier.
- The verifier's network allowlist permits OpenAI hosts. During grading, a hostile program could therefore read the key and use it against the OpenAI API.
- No path to influencing the reward was found, so this is filed as a warn.

**Where**
- `tests/test_output.py` L1643-1645 (no `env=` argument):
  ```python
  proc = subprocess.Popen(_untrusted([sys.executable, str(staged), str(data), str(out)]), cwd=box,
                          stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL, start_new_session=True)
  ```
- `tests/test_output.py` L55 (no `--reset-env`): `_SETPRIV = ["setpriv", "--reuid=nobody", "--regid=nogroup", "--clear-groups"]`
- `tests/test_output.py` L1572-1576: `_untrusted` prefixes `_SETPRIV` to the command when running as root.
- `task.toml` L21-28:
  - `[verifier]` … `network_mode = "allowlist"`, `allowed_hosts = ["api.openai.com", "*.openai.com"]`
  - `[verifier.env]` `OPENAI_API_KEY = "${OPENAI_API_KEY:-}"`

---

## 5. Totals

| Severity | Count | Issues |
|---|---|---|
| ❌ Fail | 7 | 1, 2, 3, 4, 5, 6, 7 |
| 🟡 Minor | 1 | 8 |
| ⚠️ Warn | 3 | 9, 10, 11 |

**Verdict: ❌ FAIL (7 fails, 1 minor, 3 warns)**

