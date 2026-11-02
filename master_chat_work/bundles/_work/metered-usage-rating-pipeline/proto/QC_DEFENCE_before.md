# QC_DEFENCE b5f7557 metered-usage-rating-pipeline (updated harden round 1, 3106c16; harden round 2, e2dc50b)

One entry per lever and per cascade. Rule texts quoted from checks.json; PASS cites from QC_RULINGS.md; fallbacks from QC_FIX_PLAYBOOK_v2.md (DO column only).

## LV-MU-1 strict JSON integer `units` in collector_north.jsonl (H1 / L5), harden round 1 rewrite
- Rules touched: IN-15, IN-16, TS-19, AL-27, TS-13.
- Live rule (rating_contract.md:69-71): "... `sku` (product) and `units` (a JSON integer)."; 80-82 "In collector_central.csv, collector_east.tsv, collector_south.txt and collector_west.log, units is one or more ASCII digits 0-9, read as a whole number."; 133 "4. `units_not_integer`: the units value is not in its collector's form."
- IN-15 "every graded rule of engagement is stated plainly enough to act on": the north form is a bare type property in the north field block; Checking item 4 makes any other value malformed. PASS precedent: district-heat v3:119, cohort v2:119.
- IN-16 "nothing graded has two defensible readings the contract fails to settle": a JSON string, boolean, null or a number with fraction or exponent is not "a JSON integer"; the digits form is stated only for the four text collectors, by name. The global trim rule (58-59) speaks of text fields. PASS precedent: district-heat v3:120 (global default + exception in another section is one reading, W3).
- AL-27 "every stated rule has a fixture that triggers it": separating rows ship and are reseeded in every hidden month (string digits, padded string, "12.0", true, false, 12.5, null, 1e2).
- TS-19: hidden generator draws only value kinds the contract names; G12 asserts bounds.
- Fallback if flagged: playbook IN-16 (line 28) DO: add one settling clause in the north field block, general form ("a JSON string is not a JSON integer whatever it contains"), no example, no note. Playbook AL-27 (line 32) DO: add hidden reseeded north rows of the named kind inside stated bounds.

## LV-MU-2 exact decimal, half-even per line at 0.01 (H2 / L8), graded noise since harden round 1 (not a lever)
- Rules touched: IN-15, IN-16, AL-27, TS-19, JD-7.
- IN-15/IN-16: Rating section: "computed exactly in decimal arithmetic on the rate as written in rate_card.json, then rounded to 0.01 with ties to the even hundredth. Totals are sums of rounded line charges." One reading for step (per line), mode (half-even), operand (rate as written) and totals (sum of rounded). PASS precedent: district-heat v3:119/120.
- AL-27: shipped month carries no tie (W5); every hidden month plants >= 3 ties per region, per segment, per product (target 6 per region-segment cell), all inside stated bounds (units integer range, rates from the rate card).
- TS-19: the tie rule is graded by every hidden whole-doc test that carries a tied line; no ungraded promise.
- Fallback: playbook AL-27 DO: raise the planted tie count in the hidden generator (never in shipped data). Playbook IN-16 DO: one clause in the Rating section ("the rate is read as the decimal written in the file") if QC finds the operand unclear.

## LV-MU-3 credit base = lines of committed accounts of accounts.csv (H3 / L6), harden round 1 rewrite
- Rules touched: IN-15, IN-16, AL-27, TS-13, TS-26.
- Live rule (rating_contract.md:22-23): "**committed account**: an account whose value in the plan column of accounts.csv is `committed`."; 30-31 "**credit base** (of a region): the sum of the charges of the accepted lines of that region whose account is a committed account."; 161-165 "The credit of a line counted in the credit base of its region is credit pool times line charge divided by credit base ...; every other line has credit 0.00."
- IN-15/IN-16: the term names the file and the column ("the plan column of accounts.csv"), not "its plan", so it has one reading; no sentence in Plans and segments, Credit or the commitments block ties the base to the plan in force (the pool-under-half-base sentence was deleted). The plan in force is a separate defined term used only for rating and for the `plan` output field. W3 form (definition). PASS precedent: cohort v2:120, district-heat v3:120.
- AL-27: every hidden month has accounts whose plan changes mid-month in both directions (seed 58213: 1950 of 7555 lines differ between the readings). The shipped month carries plan changes too, but none before a later usage line of its account changes the plan (W5).
- TS-13/TS-26: credit_base appears in region documents; normalized credit per line and region totals are different documents (district-heat v3:185 PASS).
- Fallback: playbook IN-16 DO: add one settling clause to the committed account entry ("whatever plan is in force later in the month"), never an example. Playbook TS-26 DO: narrow one test wording.

## LV-MU-5 tier counter shared by the billing group, group = top of the parent chain (H6 / L6), harden round 2 rewrite
- Rules touched: IN-15, IN-16, AL-27, TS-19, DS-25, CL-4.
- Live rule (rating_contract.md:24-26): "**billing group** (of an account): the account itself when its parent column in accounts.csv is empty, and otherwise the billing group of the account named in its parent column."; 27-29 tier counter "... an account of the same billing group as the line's account"; 96-99 "`parent` is empty or the account_id of another account in the file."; 152-160 Rating uses the tier counter.
- IN-15/IN-16: a recursive definition with one base case has one reading (the head of the chain); no sentence bounds the depth, none states a one-level shortcut. ids compare canonically (Identifiers 91-92). W3 form (definition with a branch, no warning). PASS precedent: district-heat v3:120.
- AL-27: every hidden month builds chains (seed 58213: 201 accounts with a parent, 91 at depth 2-3); the generator asserts depth >= 2 for at least 1/40 of normal accounts. Shipped parents all empty (W5).
- TS-19: chains are acyclic by construction (each member's parent is an earlier member of its group); every parent names an account of the file.
- CL-4: one depth-2 account wrong costs 53.8% because its moved tier changes charges that feed the region credit base and true-up (stated COUPLING); the contract judges every output document whole and exactly.
- Fallback: playbook IN-16 DO: one settling clause in the billing group entry ("however many parent links lie between them"), no example. Playbook AL-27 DO: more hidden chains. CL-4 DO: narrow rating_<r> to tier/charge and move credit/true_up owners off the chain accounts (owned rows).

## LV-MU-6 credit pool shared again across the lines that held 0.50 (H7 re-entry), new in harden round 2
- Rules touched: IN-15, IN-16, AL-27, TS-19, TS-26, DS-25.
- Live rule (rating_contract.md:162-177): "When the credit base of a region is at or below its credit pool, each counted line receives its own charge as credit, and the rest of the pool is left unused." / "When the credit base exceeds the credit pool, each counted line first receives credit pool times line charge divided by credit base, computed exactly and rounded to 0.01 with ties to the even hundredth. A line whose credit is then below 0.50 receives 0.00, and every cent of the credit pool is shared again, pool × line charge ÷ summed charge of the lines that held 0.50 or more, rounded half-even to 0.01, across only those lines. When no line holds 0.50 or more, every credit in the region is 0.00."
- IN-15/IN-16: the second pass states its formula, its rounding, its amount ("every cent of the credit pool") and its set ("across only those lines"); the formula leaves no branch to choose (the master's F2 form, replacing the caldermoor "by the same rule" wording that QC could read two ways). PASS precedent: caldermoor commitment-protocol ruling on "the whole ... distributed again" (TEST_DEPTH CM-B GENUINE).
- AL-27: every hidden month has three regions whose held lines' summed charge fits in the pool while the base exceeds it (seed 58213: 323 / 358 / 344 lines whose credit exceeds their charge), one region with base under pool, one tie region; mutation_near_base_pool sets one pool to base - 0.01. Shipped pools 0.20-0.45 of base (W5).
- TS-19: a credit above a line's charge and a negative net are what the formula gives; the region block already says credit_unallocated may be negative; nothing in the contract bounds a credit by its charge.
- TS-26: credit_<r> owns plan and credit; true_up_<r> owns true_up; net is graded only inside documents.
- Fallback: playbook IN-16 DO: one settling clause ("a credit may exceed its line's charge"), no example. Playbook AL-27 DO: more hidden sep regions.

## LV-MU-7 true-up shortfall shared again across the lines that held 0.50 (H7 re-entry), new in harden round 2
- Rules touched: IN-15, IN-16, AL-27, TS-19, TS-26.
- Live rule (rating_contract.md:34-35): "**minimum** (of a region): the `minimum` of that region's `pool` element in commitments.xml."; 113-115 commitments.xml `minimum` (the committed spend for the month); 179-189 True-up: the shortfall is the minimum minus the credit base; lines first get the shortfall "in proportion to charge, rounded half-even to 0.01"; a line below 0.50 gets 0.00 "and every cent of the shortfall is shared again, in proportion to charge, rounded half-even to 0.01, across only the lines that held 0.50 or more"; none standing -> 0.00; 191-192 net = charge - credit + true-up.
- IN-15/IN-16: "every cent of the shortfall" names the amount of the second pass; the method is named the same way as the first pass (master change 2). One reading.
- AL-27: three hidden regions under their minimum with sub-floor lines (seed 58213: 699 / 674 / 664 lines with a true-up); mutation_small_commitment puts one minimum one cent above its base (no line holds 0.50). Shipped minimums all under base (W5).
- TS-19: minimum is a decimal with two places like amount; generator asserts survivors exist in every shortfall region.
- Fallback: playbook IN-16 DO: one settling clause ("the shortfall is not recomputed"), no example. Playbook AL-27 DO: more hidden shortfall regions.

## LV-MU-4 account id upper-case + hyphen removal, matters in plan_changes.log (H4 / L10), graded noise since harden round 1 (not a lever)
- Rules touched: IN-15, IN-16, AL-27, TS-19.
- IN-15/IN-16: Identifiers section: "Account ids are compared after converting them to upper case and removing every hyphen; outputs write this canonical form." The parent column of accounts.csv (94-97) is an account id too; hidden months write 50% of parent values in a variant form. One reading; the rule is global, written once (W3 global default).
- AL-27: shipped log writes canonical ids only (W5); hidden months write about 60% of matched ids in lower or mixed case with hyphens, all of which canonicalise to an accounts.csv id; genuinely unknown ids are drawn outside the account id space.
- TS-19: hidden ids stay inside the stated id form (letters, digits, hyphens).
- Fallback: playbook AL-27 DO: more hidden reseeded mixed-form ids. Playbook IN-15 DO: restate as a bare property in the plan_changes.log block of rating_contract.md (same file), no example.

## Cascade C-ROW: row-owned tests and the COUPLING quantity (all levers; CL-4)
- Rules touched: TS-13, TS-26, AL-28, TS-20, kit CL-4.
- Layout: 30 families, each owning its rows (accepted_lines; rating_<r>; credit_<r>; true_up_<r>; region_<r>; segment_<s>; product_summary; summary; data_quality), visible on shipped data and `_hard` on a fresh hidden month. A slip fails a test only when it changes that test's rows.
- TS-13 "one property per test": each test asserts one family's rows on one input. PASS precedent district-heat v3:176, emberforge v5:161.
- TS-26 "no test pair pays twice for one observable": families own disjoint fields (rating_<r>: segment, tier, unit_rate, charge; credit_<r>: plan, credit; true_up_<r>: true_up; net only inside documents); visible and `_hard` read different inputs. PASS precedent district-heat v3:185, cohort v2:183.
- CL-4 "one wrong fact should cost about one fact": the spread of a slip comes from the stated COUPLING quantity, the region credit base, which the contract defines once and which decides the credit and true-up of every line of its region. Moving it legitimately moves every credit row of that region. One-fact-wrong scores are measured per lever in COST_TABLE.md.
- AL-28: tests carry no negatives; judge negatives name single cheating acts. PASS precedent cohort v2:242, district-heat v3:251.
- TS-20: `_hard` w5 core, visible w3 sub-goal, existence w1. PASS precedent cohort v2:181.
- Fallback: playbook TS-26 DO: narrow one test's owned fields or merge two at the larger weight. Playbook TS-23 DO: keep WARN A3 above 35 checks, never merge lever checks.

## Cascade C-MUT: mutation and rejection tests
- Rules touched: TS-19, AL-27, TS-26.
- Missing input and control mismatch error strings are stated verbatim in rating_contract.md (DS-25); M3 and M5 trigger them. M1 tier-threshold scale, mutation_small_commitment (minimum one cent above base), mutation_near_base_pool (pool one cent under base) and M4 determinism read different observables from the hidden whole-doc tests (product_summary under a changed rate card; equality of two runs).
- Fallback: playbook TS-19 DO: add the generated case or bring the generator inside the stated bounds.

## Judge (J1-J9)
- Rules touched: JD-7, JD-15, JD-18, JD-8.
- JD-7 "every criterion true of / avoided by the reference solution": R1-R6 'independently recomputes' conduct criteria (one per output family) and R7 J9 (altered-content copy, dependent figures move) and R10 (foreign cwd run) are shown by solve.sh's self-check stage (solution/solve.sh self-check stage, separate from solve.py) printing `check R<n> ok`; R15 tier recompute and R16 credit and true-up recompute (harden round 2) are shown by `check tier_counter ok` and `check credit_true_up ok`. R8 code quality is met by solve.py (no bare or pass-only except, no function over about 150 lines, no unused function). FAIL precedent cohort v3:38 avoided (no `except ...: return None`).
- JD-15: conduct criteria labelled conduct; the /app/data write negative labelled instruction following with the quoted instruction sentence (sensor v1:36).
- JD-8 / J8: recompute criteria name the act of checking a figure family, never the figure or the rule a test grades.
- Fallback: playbook JD-7 DO: fix the oracle (add the act to selfcheck.py); JD-15 DO: relabel.
