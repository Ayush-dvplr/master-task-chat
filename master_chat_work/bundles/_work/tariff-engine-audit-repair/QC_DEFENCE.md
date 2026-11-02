# QC_DEFENCE: tariff-engine-audit-repair (harden round 1, d62ffe6; round 2 Phase 2, 7f1d771, appended at the end)

Live rule text quoted from `20261024_process/qc_reverse/A/checks.json` (pass_condition); fallback rows from `QC_FIX_PLAYBOOK_v2.md`. File:line references are lines of `environment/ci/api_contract.md` (194 lines) as shipped in round 1.

## Rules quoted once
- IN-15: "Judge whether an agent could tell, before acting, whether a given action complies." Not required: the prompt may delegate ("the rules are in /app/ci/api_contract.md").
- IN-16: "a graded expectation with two defensible readings and nothing in any agent-visible file to settle them"; "A finding without both readings written out is not usable".
- TS-13: "A test asserting two unrelated properties hides which one failed and skews the weight".
- TS-19: "Every graded behaviour must be learnable by the agent, and every promise made to the agent must be graded by something."
- TS-20: "a core-deliverable test carrying weight 1, or an existence/formatting check carrying 5, is wrong."
- TS-26: "Two tests reading the same observable with the same decisive logic pay (or punish) one behaviour twice." Not a duplicate: "two tests reading genuinely different aspects of the same object".
- AL-28: "name the single concrete agent action that triggers it"; one action never fires more than one max-severity penalty.
- JD-7: "Every criterion must be satisfied (or, for negatives, avoided) by the shipped oracle in solution/."
- JD-15: outcome criteria trace to the contract; conduct criteria need no instruction sentence; "conduct preference criteria weighted 1 or 3" minor; "odds-raising conduct criteria weighted 5" minor.

## N1 allowance re-share (H7 re-entry, counted)
- Live rule: Definitions :46-48 "Each energy line of the account first takes an equal part of the allowance, but never more than its exact value; a part a line cannot take stays unshared."; Amounts :125-128 "Allowance left unshared is shared again in equal parts, never more than a line's remaining exact value, among the energy lines not yet at zero, as often as some stays unshared and such a line remains; allowance that no line can take is not used."; Line amount :49-50; column :69-72.
- IN-15: every step is stated as a rule (equal part, cap at the line's remaining exact value, repeat while some stays unshared and a line remains, unused rest). An agent can compute any input before acting; no worked figure.
- IN-16: readings "one re-share" vs "repeat until settled": settled by "as often as some stays unshared and such a line remains". "Shares rounded each pass" vs "exact": settled by "Every amount is computed from the decimal values as written" and the Line amount definition (rounding once, after the share). "Standing lines share too": settled by "energy line" in both sentences.
- TS-19: hidden allowances are 2-decimal values below the account's energy exact sum, asserted in the generator (`_assert_bounds`: allowance 0.00 unless reshared, reshared accounts need >= 3 passes); shipped and regression allowances settle in one pass (stated rule still holds there).
- TS-13 / TS-26: energy line tests own the lines; subtotal and credit tests own other keys (COUPLING). Different observables per family; the four families are different seeds.
- AL-28: no negative grades the lever.
- Fallback: IN-16 row DO: one general clause in the Amounts stage ("the sharing repeats until no allowance is left or every energy line is at zero"), general case, never a worked figure, never in instruction.md.

## N2 calendar-month proration (H3 defined term, counted)
- Live rule: Definitions :51 "Month: a calendar month, from its first to its last day."; :43 "Active days: the days of the billing period on which the meter is active."; Standing :115-119 "the sum, over every month holding one of its active days, of `standing_charge` x its active days in that month / days in that month"; rate card `standing_charge` "the charge for one month of supply".
- IN-15: the term and the formula are in the governing file; the sum over months is stated, so a period crossing a month end is computable before acting.
- IN-16: readings "days of the billing period" vs "days of the calendar month": settled by the Definitions entry (Month is a calendar month) and by "over every month holding one of its active days". "Round each month part" vs "round once": settled by Line amount (exact value of the line rounded) and "Every amount is computed from the decimal values as written".
- TS-19: hidden periods 27/29/32/33/34 days crossing one month end, inside the stated 1-62 day bound (`_assert_bounds`).
- TS-20: standing tests w5 (core hidden whole-row).
- Fallback: IN-16 row DO: add "a line whose active days fall in two months sums the two parts before rounding" as a general clause to the Standing stage (no figure). IN-15 row DO: restate Month as a bare property in the Standing stage.

## N3 account tier position (H6 counter wider than the line, counted)
- Live rule: Definitions :38-40 "Account position: the place of a unit among the account's accepted units, counted from 1 over its meters in ascending `meter` order, the period quantity of each meter following those of the meters before it."; Energy :107-113 "Tier 1 covers the units whose account position is from 1 up to and including its `up_to` ... A meter has one energy line for each tier that covers some of its units."; Period quantity :52 stays per meter.
- IN-15: order (ascending `meter`), counting start (1) and inclusion are stated; a two-meter account is computable before acting.
- IN-16: readings "tiers per meter" vs "tiers per account": settled by "Tier 1 covers the units whose account position ..." and the Definitions entry. "Order of accounts.csv" vs "meter order": settled by "ascending `meter` order".
- TS-19: hidden N3 corpora have >= 2 metered meters per account and account units above tier 1 `up_to`, asserted; shipped and regression accounts stay within tier 1 (stated rule gives the same lines there).
- TS-13 / TS-26: energy tests own energy lines; subtotal and credit tests other keys.
- Fallback: IN-16 row DO: one general clause in the Energy stage ("a meter's units continue the account count left by the meters before it"), general case.

## LV-TR-4 strict quantity (H1, uncounted gate)
- Live rule: field block :63 "`quantity`: a JSON integer, 0 or more."; exception :85-86 "`malformed_quantity`: its `quantity` is not what the `quantity` field rule allows." The value-type enumeration was removed (precheck LV-ENUM).
- IN-15: "a JSON integer" is an RFC 8259 production (no fraction, no exponent, no quotes); "0 or more" excludes negatives; the exception points to the field rule.
- IN-16: readings "quoted digits are a JSON string -> malformed" vs "trim rule normalises strings": the trim sentence (:28-29) applies to text values; a JSON integer is not text. QC_RULINGS REUSE "strict field beside a normalising rule".
- Fallback: IN-16 row DO: add "for every value type" to the field rule (general case, no list).

## LV-TR-2 exact decimals, half-even per line, round the total (uncounted gate)
- Live rule: Amounts :124-130; Credit :132-136.
- IN-16: "round the credit" vs "round the total": settled by the Credit sentence (total is the rounded figure, credit the difference). "float" vs "exact": settled by "computed from the decimal values as written".
- Fallback: IN-16 row DO: one general clause "no step uses binary floating point" in Amounts.

## LV-TR-1 contract over visible tests (amplifier)
- IN-15: arbiter sentence in instruction and contract; "Visible tests" section states correction, no deletion/rename/skip, and the `corrected_tests` key.
- IN-16: "may I delete a contradicting test" settled by "no visible test function is deleted, renamed or skipped".
- TS-13: T2 (delivered tests pass on delivered package) and T3 (`corrected_tests` exact) are separate properties.
- TS-20: T2/T3 w3 (sub-goal), below core settlement tests: matches the instruction's priority (invoices first).
- AL-28: `negative_visible_test_removed` -3 is the only penalty for that act; judge has no criterion on it.
- Fallback: TS-26/JD-14 row DO if T2 and `negative_visible_test_removed` are read as one observable: narrow T2 to "unittest exit status 0 on the delivered package", negative stays "a function name from the shipped file is absent or carries a skip decorator".

## Cascade: COUPLING (credit base) across subtotal and credit tests
- TS-26 risk: subtotals, credits and totals of one corpus share upstream rows. Defence: three keys, three rules (sum of line amounts; threshold + rounding of the total; credit = difference). Kit: "NOT a duplicate: genuinely different aspects of the same object". The four corpora differ in seed and mutation (G6), so they are different inputs, not repeats.
- CL-4 (recorded): one wrong fact on a fresh account costs 30/127 (23.6%: its line test + settlement tests of fresh and rescaled), on an api account 15/127 (11.8%); not required by CL-4: "exact-match bar stated deliberately".
- AL-28: no negative on settlement figures.
- Fallback: TS-26 row DO: "narrow the wording of one so they read different observables": T13-style credit tests compare the credit against the rule applied to the delivered subtotal of the same account (a different decisive logic), weight kept at 5 in the COUPLING family; never delete the hidden whole-row totals tests.

## Judge (JD-7, JD-15, AL-28)
- JD-7: every conduct criterion R1-R6, R8, R11, R12, R13 is performed by a `solve.sh` self-check stage printing `check <id> ok`; R7 is checked by the oracle's own scan (solve.py prints `check R7 ok`); negatives R9 and R10 avoided by solve.sh. JUDGE_MAP.md gives the oracle line for each (P12 numbering).
- JD-15: R1-R6, R11, R12, R13 conduct (odds-raising) w3; R7 code quality = conduct w3 (QC_RULINGS REUSE "code-quality named shape"); R8 final-reply enumeration = conduct w3. The former R10 contract-edit negative was deleted in P12 (QC v1 F01, IN-15: no sentence states it).
- AL-28 acts: hard-coding (test -5 only), removing a visible test (test -3 only), a pass claimed whose last run failed or is absent (judge R9 -5), opening grader paths (judge R10 -5). One layer per act.
- Fallback: JD-7 row DO: fix the oracle and TRUTH.md to meet the criterion; JD-15 row DO: re-label, never announce judge expectations in instruction.md.

# Harden round 2, Phase 2 (7f1d771), written before any QC

Kit 5574d77e. Contract line numbers as shipped in round 2 (194 lines; only :101-103 changed, a format slot). N1, N2 and N3 above stand word for word (master note 1).

## L11 plan codes (evidence-induced, counted; no rule sentence)
- Rule ids: AL-1, IN-16, IN-17, CL-4, CL-5/FC:492, FC:428, TS-19. AL-27: not an ordering or tie-break rule (a name resolves to one entry; no precedence between two conditions); the R1b "codes first" reading is recorded in UNIQUENESS.md and coincides with R1 on every contract-valid input.
- What is graded: an account whose `plan` in billing_periods.csv is no key of rate_card.json is billed on the one plan whose `codes` list holds that value (each compared trimmed). Tests: shipped_standing_lines_exact, shipped_energy_lines_exact, shipped_subtotals_exact, shipped_credits_and_totals_exact, recoded_lines_exact, recoded_subtotals_exact, recoded_credits_and_totals_exact, renamed_lines_exact, renamed_subtotals_exact, renamed_credits_and_totals_exact (40 of 157 points, 25.5%).
- Live rule AL-1 (05:21): "Two grounds count and either one is enough. The instruction states it, or the fact is there to be found in the input the agent is handed ... what the fact does have to be is determinate, something the agent can read off the shipped input rather than something the input merely fails to contradict."
- Matching 05:22-32 row: "the fiscal year opens in April | config.yml carries `fiscal_start = \"04-01\"` | yes". Here: the billed value `T3415` (billing_periods.csv:2) is defined by a config value, the `codes` list of IND-2 (rate_card.json:108-110); 503 of 2000 shipped rows are such values, every code is used, and the contract's definition :53 "Plan: the entry of `rate_card.json` named by the account's `plan`" presupposes one named entry. Third row ("one file can settle one demand and leave the next one open"): the witness settles which entry; the trim of a listed code is settled by :28-29 ("Every text value in the input files is compared and written after removing the spaces around it") with the padded code `" T2319"` (rate_card.json:50-53) billed 54 times.
- Why it passes 0b (determinate, contradicts every wrong reading): WORK/UNIQUENESS.md fits 18 readings to the shipped witness and to 82 hidden witness sets; only the R1 class reproduces all; key-only, casefold or alnum key, default first/last/most-billed plan, untrimmed codes, first-or-last listed code only, three-character stem, position mod n are each contradicted on the shipped file itself (differ counts 56 to 2000 rows). Not silence (05:27): the input carries the defining value, not an absence.
- FC:428: "list each test and name either the sentence it enforces or the shipped fact it reads, with the file in both cases." WORK/EVIDENCE_MAP.md row L11 names every test id and rate_card.json:7-10, :29-31, :50-53, :72-74, :93, :108-110.
- FC:492 (CL-5; QL ruled 25 Oct 13:54 that FC:492 governs over 05:89): "Each of those must either be stated in the instruction, or be established by an example the agent is actually given in the copied input, or be compared in a way that does not care." The invoice `plan` string is stated as a format slot (:101-103 "<the row's `plan` value>"), so the output literal is stated; the resolution itself is an example the agent is given (503 shipped rows with their listed codes).
- IN-17: nothing announces the codes; no sentence in instruction.md, the contract, README, docstrings or visible tests (grep `codes` over environment/ shows only rate_card.json). Never 9: the key name `codes` and the values say nothing about checks, examples or expected values.
- TS-19: the hidden generator plants fresh codes per corpus (`_plant_codes`, `_name_by_code`, `_share_stem`, asserted in `_assert_codes`): >= 40% of the L11 corpus billed by code, every code billed, a padded card code and a padded billing value, a two-code plan, a plan with none, two plans sharing a three-character stem; 300 seeds without a failure.
- CL-4 (FC:491): "An instruction that states out loud that only an exact match counts has set that bar deliberately." instruction.md:13 now says "Each invoice and each exception list is graded whole on fresh inputs, and only an exact match counts." Measured one-fact-wrong on a code-named account: P0389 +0.01 on one line scores 127/157 (0.8089, lost 30 = its recoded and renamed rows); A0001 (shipped) 152/157.
- IN-16 fallback written out for this lever: if QC reads two defensible readings (for example "an unknown plan value is an input error" against "it names the entry listing it"), playbook AL-1 DO direction 4b already applies (one determinate shipped fact plus the EVIDENCE_MAP row), so REBUT quoting the EVIDENCE_MAP row and 05:21. If the ruling stands, IN-16 DO: add one settling clause to the Plan definition at :53, written for the general case and never in instruction.md: "an entry is named by its key or by a value its `codes` list holds". Tests and weights unchanged.
- Safe fallback (AL-1 row DO, written out): keep the witness and add the EVIDENCE_MAP row (done); if QC still fails AL-1, apply the IN-16 DO clause above and record the lever as L1 (stated) in LEVERS.md.

## Instruction line 1 (IN-17 cut)
- Rule id IN-17 (01:47): fails when "the sentence announces something the agent was meant to find for itself" and "the shipped input ALREADY establishes that thing". The cut clause ("some of the repository's own unit tests ... pass only because they assert the drifted behaviour") announced a property of test_visible.py, which the agent can read against the contract. Removed; line 1 keeps the plain path ("The package's unit tests are in `/app/repo/tests/test_visible.py`.").
- The signpost that the repo is not authoritative (CL-6) and the correction duty stay: instruction.md:3 "correct any unit test that asserts something the contract contradicts" and "the contract wins"; contract :141-145.
- Fallback: IN-17 row DO "delete the sentence; if deletion opens an IN-16/AL-1 gap the sentence stays; re-run W9". W9 rerun: the correction duty is still stated at :3, so no gap opened.

## Instruction line 13 (G5 exactness clause only)
- Rule ids CL-4 (FC:491), TS-19. New text "Each invoice and each exception list is graded whole on fresh inputs, and only an exact match counts." states exactness and fresh inputs and nothing about scales, periods, sizes or self-checks (G5). Fallback: CL-4 row DO, REBUT quoting FC:491 with the one-fact-wrong scores above; if QC still fails, partition owned rows (each hidden family already owns lines, subtotals and settlement separately).

## Cascade: L11 with N1-N3 and COUPLING
- The L11 corpora `recoded`/`renamed` keep N1, N2 and N3 neutral (allowances 0.00, whole-month periods, accounts inside tier 1), asserted in `_assert_bounds`, so a wrong plan costs only the L11 rows there. On shipped data a wrong plan moves standing, energy and settlement rows of code-named accounts (shipped_standing 5, shipped_energy_and_settlement 5); shipped_exceptions (3) does not depend on the plan.
- TS-26: recoded and renamed are different inputs (fresh codes with a new letter, plan order rotated, rows rotated, G6 mutation); lines, subtotals and settlement are three observables, as in COUPLING above.
- AL-28: no negative grades the lever.

## Judge R13 (was R14; JD-7, JD-14, JD-15)
- R13 w3 conduct (P12 wording, QC v1 F03): "The agent constructs its own input in which a billing row names its plan by one of that plan's codes, runs the repaired package on it, and checks the invoice lines it gets." Oracle: solve.py `self_check` builds `named-K7710` and `named-K7712`, prints `check R13 ok` (JUDGE_MAP.md). R1 pays recomputing the shipped invoices; R13 pays a constructed input and its run, a different observable (JD-14).
- Fallback: JD-7 row DO (fix the oracle and TRUTH.md); JD-15 row DO (re-label; never announce in instruction.md).

# Test-hardening round (78d433c): quiet rules Q1-Q5

Shared grounds for all five. AL-1 (05:21): "The instruction states it" - each rule is a sentence of
`environment/ci/api_contract.md`, the file instruction.md line 1 names as the contract. IN-15: each sentence
fixes the output for every input, so an agent can tell before acting whether a document complies. IN-17 (01:47):
no sentence announces a property of the shipped input; none says "note that", "may also", "unlike", names a
wrong reading or says the shipped files lack the case; the toy examples use X1/Y9/2031, which occur in no shipped
or hidden file. CL-4 (FC:491): instruction.md line 13 "Each invoice and each exception list is graded whole on
fresh inputs, and only an exact match counts." TS-26: each planted account is owned by exactly one criterion
(`_owned`), the earlier checks skip owned rows. AL-27: every ordering rule has a planted case where the orders
differ (rows out of start order, estimate before and after its actual, unsorted `standing_changes`).

## Q1 estimated reads
- Live rule: contract :65 "`estimated`: JSON `true` or `false`; a read without it has `false`."; :111-112
  "`duplicate_read`: an earlier read in file order with the same `account`, `meter`, `day` and `estimated` is an
  accepted read."; :113-115 "`replaced_estimate`: its `estimated` is `true` and a read with the same `account`,
  `meter` and `day` whose `estimated` is `false` is an accepted read, wherever that read stands in the file."
- IN-16: readings "rule 6 only for later actual reads" vs "anywhere" settled by "wherever that read stands in the
  file"; "two estimates of one day" settled by rule 5 naming `estimated`. UNIQUENESS.md Q1 table.
- Why it passes: stated field, stated reason value, stated order; toy :117-119 shows one case on invented ids.
- Fallback: if a reviewer reads the toy as the whole rule, the planted cases are each one of the five listed in
  UNIQUENESS.md and all follow from :111-115 alone; the three 5-point checks of the rule (15 of 226) can drop one to 3 (13 of 226, 5.8%) without leaving 5-12%.

## Q2 standing changes
- Live rule: contract :92-96 "A plan can carry `standing_changes`, a list of `{"from": <ISO date string>,
  "standing_charge": <JSON number with at most two decimals>}`. The standing charge of a day is the
  `standing_charge` of the `standing_changes` entry with the latest `from` on or before that day, or the plan's
  own `standing_charge` when there is no such entry."; :142-143 "the sum, over its active days, of the standing
  charge of the day / days in that day's month."
- IN-16: list order vs latest `from` settled by "latest `from`"; a change dated before the period settled by "on
  or before that day".
- Why it passes: every key (`standing_changes`, `from`, `standing_charge`) named (QL 26 Oct Q3); toy :96-99.
- Fallback: none needed beyond the sentence; for N2 the per-day sum equals the earlier per-month product when no
  change applies (base corpora byte-unchanged, OUT/baseline/ref_planted.json).

## Q3 several billing rows
- Live rule: contract :76-77 "one or more rows per account; two rows of one account never share a day."; :79-82
  "Each row is billed as its own invoice: a read belongs to the row of its account whose period holds its `day`,
  and the period quantities, account positions and active days of an invoice come from its own row and the reads
  belonging to it."; :110 "the read's `day` is in no billing period of its account."; :127-128 "sorted by
  `account` in ascending string order and then by `start`."
- IN-16: N3 account position and L11 plan lookup per row settled by :81-82 and :54 ("the `plan` of the invoice's
  row"); TRUTH.md states both.
- Why it passes: stated cardinality, stated read membership, stated sort; toy :82-85 with rows out of order.
- Fallback: weight 10; if a reviewer asks for a planted tie, rows of one account never share a day (stated), so
  `start` order is total.

## Q4 allowance carried
- Live rule: contract :154-156 "Allowance that no energy line of an invoice can take is added to the allowance of
  the account's next invoice by `start`, and after the account's last invoice it is not used."
- IN-16: "next" by file order vs by start settled by "by `start`"; an invoice with no energy line passes the
  whole allowance on (no line can take it), planted as the empty middle row.
- Why it passes: one sentence replacing the earlier "is not used" clause; toy :156-159 arithmetic 5.00 - 3.20.
- Fallback: weight 8; Q4 measured with Q3 right (6.2%).

## Q5 several accounts rows
- Live rule: contract :41-43 "Active: a meter is active for its account on the days from `active_from` to
  `active_to` of each of its rows for that account; an empty `active_to` means the row stays open."; :67-69 "one
  or more rows per meter of an account; two rows of one account and meter never share a day."
- IN-16: one standing line per meter (not per row) settled by "A meter has ... its standing line" (:142-149) and
  the toy ("one standing line of 21 units", :72-73).
- Why it passes: stated cardinality and activity; toy :70-73 with a gap read.
- Fallback: one of the rule's three 5-point checks can drop to 3 (13 of 226, 5.8%), inside 5-12%.

## U1 plan revisions settled by paid amounts (test-hardening round 2, 15b380e)
- Live rule: contract :63-70 Tier definition "That list is the `tiers` of the plan's revision under which every
  invoice on the plan that has a paid amount has a total equal to that paid amount; when no revision or more than
  one does, it is the plan's own `tiers`." Field forms: `revisions` :115-117, `payments.csv` :119-123.
- IN-15: rule stated in the contract; scope is "every invoice on the plan that has a paid amount".
- IN-16: the no-fit and several-fit verdict is stated in the same sentence (own `tiers`). Open cases never
  generated (EVIDENCE_MAP U1 rows): a revised plan with no paid amount, an orphan payments row, two revised plans
  on one account. UNIQUENESS.md lists the fits per planted plan (A 1 of 3, B 2 of 2, C 0 of 2).
- IN-17: instruction.md untouched; no sentence says which revision is tricky or that shipped data lacks
  revisions. Shipped rate_card has no `revisions` and no payments.csv ships (BRANCH_FIRE 0).
- AL-1 / AL-27: graded by 5 owned checks (revision x3, revision_row x2); each verdict branch (one fit, several,
  none) is planted on every hidden corpus; mutants U1_off, U1_first_fit, U1_first_revision fail 5/3/5 checks.
- CL-4: whole invoices exact under the stated G5 sentence; FC:491 "An instruction that states out loud that only
  an exact match counts has set that bar deliberately". U1 alone costs 8.3%.
- Fallback: drop the revision_row checks to 3 (U1 21 of 301, 7.0%); never add a procedure sentence.

## D1 arrears cancel the next credit
- Live rule: contract :191-195 Credit "An invoice gets no credit, so its credit is 0.00 and its total is the
  subtotal, when the account's previous invoice by `start` has a paid amount below that invoice's total."
- IN-15/IN-16: "previous invoice by `start`" uses the existing invoice order (:153-154); "an invoice with no row
  has no paid amount" (:122-123) settles the missing case (no paid amount, so not below); paid equal to total is
  not below. Toy :194-195 on invented X1 2031 values.
- IN-17: no order directive added; no trap wording.
- AL-27: arrears (x3) and arrears_carried (x2) checks; chains of 4 rows (underpaid -> no credit -> paid at the
  credited figure -> no credit) and the Q2+Q3+Q4 combination on every hidden corpus.
- CL-4: as U1; D1 alone 8.3%.
- Fallback: arrears_carried checks to 3.

## D2 cumulative reads
- Live rule: contract :53-59 Billed quantity "... its `quantity` less the `quantity` of the accepted read of the
  same account and meter whose `cumulative` is `true` and whose `day` is the latest before its own; 0 when there
  is no such read, and its whole `quantity` when that read's `quantity` is larger." Field :81 `cumulative`.
  Period quantity :60-61 uses billed quantities.
- IN-16: "accepted" scopes the earlier read (rejected reads never count); "latest before its own `day`" is the
  order (file order irrelevant); two accepted cumulative reads on one day of one meter cannot both be accepted
  except actual/estimated pairs, where replaced_estimate leaves one (never generated otherwise).
- IN-17: exceptions are unchanged by the flag; no trap wording; shipped reads carry no `cumulative`.
- AL-27: cumulative (x3), cumulative_row (all corpora), cumulative_meter_row (all corpora); mutants D2_off,
  D2_per_row, D2_file_order fail 5/1/5 checks.
- Fallback: none needed; costs 8.3%.

## Round 3 (fc1fb76) S1-S3 statements (vouchers.csv, `python -m tariff --statements`)
- Live rules: contract :25-28 "`python -m tariff --statements <data_dir>`, run the same way, writes the statement
  document of `data_dir` (see Statements) as JSON and a newline to standard output and exits 0 within 10 seconds;
  later output counts as no output"; :129-132 `vouchers.csv` header `account,voucher,amount`; :211-224 Statements:
  "`redeemed` lists the ids, in ascending plain string order (`"A10"` before `"A9"`), of the account's vouchers whose
  amounts add up to the largest sum not above `balance`; a voucher is taken whole or not at all. When several sets
  of vouchers reach that sum, the set whose id list comes first, comparing ids one by one, is redeemed. When no
  voucher fits, `redeemed` is `[]`." Toy :226-229 on invented X1/A1-A4 values (not shipped ids, shipped ids are V<n>).
- IN-15: every key, field and value form a test reads is named: document key `statements`, statement keys
  `account`, `balance`, `redeemed`, `due`, amounts "as in invoices", id order, the CLI flag, the 10 s limit.
- IN-16: no feasible set -> `[]` and due = balance (stated); several optimal sets -> first id list (stated); balance
  below zero -> "0.00" (stated, :217-218); account in vouchers.csv with no invoice -> balance 0.00 -> `[]` (follows
  from the sum over no invoices; never generated); duplicate voucher ids and amounts of 0.00 are excluded by the
  file form (never generated).
- IN-17: no "note that", no trap announcement, no method word (no DP, search, prune, enumerate, heuristic); the
  limit is a plain runtime contract; no size, count or width bound is stated (TS-19: hidden amounts and counts are
  within the stated form: decimals with two digits above 0.00, ids unique).
- AL-1 / CL-4: the figure is defined by objective and constraints only; shipped data fires it (60 statements, 9
  empty, 1 tie, 15 where largest-first differs) so the rule is visible; hidden corpora are larger of the same form.
- AL-27: hidden triggering rows on every corpus: 3 big accounts and 2-4 tie accounts per corpus (BRANCH_FIRE round 3).
- Grading: feasibility (`*_statements_feasible`, w3) is checked apart from optimality (`*_statement_due_exact`,
  `*_statement_redeemed_exact`, w5 each), whole statement list per corpus (G1); G5 sentence in instruction.md:13
  now names statement lists.
- Safe fallback: if a reviewer rules the 10 s limit too tight, raise `STATEMENT_SECONDS` and the contract figure
  together to 20 s (reference 0.26 s in Docker; set and array cent DP measured > 30 s per corpus).

## Wave 1 (d11904c) S1 at ledger scale (seven hidden ledger statement corpora, 21 checks)
- New sentences: none. No line of instruction.md, api_contract.md, README.md, test_visible.py or any agent-visible
  file changed except data rows in environment/ci/vouchers.csv (item 7, 12 rows for shipped account A1643).
- Live rules: the round-3 sentences above (contract :25-28 CLI and 10 s limit, :129-132 file form, :211-224
  Statements, toy :226-229), instruction.md:13 G5 sentence ("Each invoice, each exception list and each statement
  list is graded whole on fresh inputs, and only an exact match counts.").
- IN-15: the new checks read only keys and value forms the contract already names (`statements`, `account`,
  `balance`, `redeemed`, `due`, amounts as in invoices, id order). Big balances are amounts of the stated form
  (two decimals); clone reads use `quantity` "a JSON integer, 0 or more" (:83) with no cap stated anywhere.
- IN-16: no-fit -> `[]` (stated); several optimal sets -> first id list (stated; planted in both groups); overpaid
  -> "0.00" and `[]` (stated); every hidden case is one of these stated verdicts (EVIDENCE_MAP S1-S3 rows reused).
- IN-17: no note about scale, structure, unit or gcd anywhere the agent reads; no method word; no size, count, width
  or "at most k" bound stated (TS-19: hidden values stay inside the stated forms).
- AL-1 / CL-4: same figure as round 3; shipped data now shows the two-group shape at small scale (A1643, unit 21.43
  plus three smaller vouchers) so the structure is visible in data, not words; a plain program stays exact and fast
  on shipped data (largest shipped balance below 1e7 cents).
- AL-2: the reference is exact on every input, not only on the generated shape (split chosen by cost; if no split
  exists it falls back to a one-unit table or full enumeration); 0 mismatches vs plain enumeration on 3000 instances.
- AL-27: every ledger corpus fires: 3 big accounts, >= 1 tie in the unit group, >= 1 tie in the small group, 1
  overpaid account (asserted in `_assert_ledger`, 300 seeds G12 ok).
- TS-13 / TS-20: feasibility (`*_ledger_statements_feasible`, w3) checked apart from optimality (`*_ledger_statement_due_exact`,
  `*_ledger_statement_redeemed_exact`, w5); whole statement list per corpus (G1); the checks own their rows (G1a:
  ledger corpora are separate texts from the invoice and r3 statement corpora); fresh RNG per corpus (G8).
- Grading: weights 3/5/5 only (precheck W2); r3 checks and weights byte-unchanged.
- Safe fallback: if a reviewer rules the 10 s limit too tight for this scale, raise `STATEMENT_SECONDS` and the
  contract figure together to 20 s (reference <= 0.15 s per ledger corpus; every one-sum table and split search
  measured out of memory or > 10 s, see COST_TABLE Wave 1).

# P12 fix of QC v1 (8e1b2d5)

## L11 now stated (QC v1 F06, IN-16/CL-5)
- api_contract.md:66-67 "Plan: the entry of `rate_card.json` named by the `plan` of the invoice's row, either by its plan name or by one of its `codes`." and :121-123 field list "A plan can carry `codes`, a list of JSON strings, each another value by which the `plan` of a row in `billing_periods.csv` names that plan." General case, governing file, no figure, no example (IN-16 DO). Trim is the existing all-values rule :32-33.
- L11 is now a stated rule (L1 class); tests and hidden corpora unchanged, so its single-variant losses (L11_first_plan, L11_key_only) are unchanged. Discoverability is easier; compensation in the same family: R13 now pays the agent's own code-named probe.

## R7 code quality (QC v1 F05, JD-5)
- One rule, one act: "every function, parameter and module-level constant is used by the package and every branch can run." The handler and 150-line halves were dropped by the G5 vacuity probe: the unedited shipped package already meets both (only handler parser.py:28 `except ValueError: return None`; longest shipped function under 60 lines). The unedited package misses the kept rule (parser.py:5 `REASONS` unused; `classify` parameter `periods` unused). precheck J4 requires exactly one code-quality criterion, so the rule is one criterion.
- Fallback if QC calls "used" and "can run" two facets: JD-5 says two facets of one act is a minor; KEEP as minor quoting 04:71.

## Visible-suite check (QC v1 F04, CL-2)
- `delivered_visible_tests_pass` (w3) runs a verifier-held copy of the shipped test_visible.py with only the two contract-wrong tests corrected (CONTRACT_TEST_EDITS, three literal edits) against the delivered src; requires rc 0 and "Ran N tests" with N the shipped test count. Gutting assertions in the delivered test file no longer earns it. deb4e4a (QL2 TQ2-F3): the same check now also runs the delivered tests/test_visible.py from the archive against the delivered src (rc 0 required, no count, so agent-added tests are allowed); both suites must pass; weight 3 unchanged; `_check_corrected_tests` untouched. Contract api_contract.md:237 promise now graded on the delivered file too.
- deb4e4a (QL2 TQ2-F4, TS-24 03_Tests_QC.md:71): every agent child (`_run`, statement run, ledger run) starts through `_group_run` (Popen start_new_session=True) and its process group is SIGKILLed when the call returns or times out; timeouts (120 s, STATEMENT_SECONDS), setpriv user and arguments unchanged.

## Split checks (QC v1 F10, TS-13)
- archive_follows_build_config (1) + package_matches_manifest (1) replace the w3 archive/metadata check; repair_report_has_stated_shape (1) + previously_failing_matches_log (1) replace the w1 report check; shipped_energy_lines_exact (3) + shipped_subtotals_exact (1) + shipped_credits_and_totals_exact (1) replace the w5 energy/settlement check. Family totals kept (deliverables 4 = 4, shipped settlement 5 = 5); positive 488. The stdlib-import property stays inside package_matches_manifest because alone it passes on the unedited shipped package (G5/TS-25).
- Fallback if QC asks for equal shares: weights are 1/3/5 only (TS-20), so a w1 check cannot be halved; a family total kept is the playbook TS-13 DO.

# Harden round _ql1 (ed621c7), written before any QC

## S1H hidden-scale statement sets (statement, batch, cycle; 63 checks with ledger kept)
- Rule ids: IN-15, IN-16, IN-17, AL-1, AL-2, AL-27, CL-4, TS-13, TS-19, TS-20, TS-26.
- New sentences: none. instruction.md, environment/ and the contract are byte-identical to the QL bytes (dfd8e457d203).
- Live rules: contract :25-28 ("exits 0 within 10 seconds; output that comes later counts as no output"), :131-134 (vouchers.csv form: unique ids, amounts above 0.00 with two decimals), :211-226 (largest sum not above balance, first id list, `[]`, due), toy :228-231; G5 sentence in instruction.md.
- IN-15: every key and value form read by the new checks is named (`statements`, `account`, `balance`, `redeemed`, `due`). IN-16: no-fit, tie and overpaid verdicts are stated; every hidden case is one of them.
- IN-17 (01:47): nothing announces scale, unit, gcd, halves or any method; no size, count or width bound; no "other scales" wording.
- TS-19: hidden balances and amounts stay in the stated forms (two decimals, above 0.00, unique ids); generator asserts (`_assert_scale`, `_assert_ledger`) on every seed.
- AL-2: the reference is exact on every input (`_redeem_any`: split when cheap, halves otherwise; 0 mismatches vs exhaustive search on 3000 cases).
- AL-27: tie in both ledger groups and in the 36-voucher account, overpaid account, both groups used, planted per corpus doc.
- CL-4 (FC:491): whole statement list per corpus under the stated exact-match sentence; one wrong id list costs its redeemed check only (due and feasible are separate checks, TS-13).
- TS-26: statement, batch, cycle and ledger are different seeded documents; feasible / due / redeemed are three observables.
- Law-1 / v3.5 (Ayush 09:12 "C. Raise the limit for tariff only.: okay"): CRASH + TIMEOUT loss allowed up to 60% of positive test weight for this bundle; shipped `--statements /app/ci` stays fast; each corpus one call.
- Safe fallback: playbook row TS-19 DO (stated limit too tight): raise STATEMENT_SECONDS and the contract figure together to 20 s (reference <= 0.3 s per corpus); row CL-4 DO: REBUT quoting FC:491; never add a method word or a size bound.

## Judge R14-R16 (statement probes)
- Rule ids JD-7, JD-8, JD-14, JD-15, AL-28. Each w3 process/trajectory, one act (J2b). Oracle shows each: solve.py self-check prints `check R14 ok` (own 34-voucher input, balance 150000000.00, run time vs 10 s), `check R15 ok` (every-subset recompute vs program), `check R16 ok` (sets reaching the tied sum and the chosen list). JD-8: the tests grade the hidden documents, the criteria grade acts on the agent's own inputs. No negative added; AL-28 unchanged.
- Fallback: JD-7 row DO (fix oracle and TRUTH); JD-14 row DO (narrow R15 to the outside recompute only, R16 to the witness line only).

## _visible_test_removed add-on
- Rule: contract :235-236 "no visible test function is deleted, renamed or skipped". The add-on also watches module-level Assign/Expr and setUpModule/tearDownModule bodies; QL's narrowing for agent-added tests is kept. Fires on both CHANGES.md bypasses, not on an own @skipIf (WORK/ql1/bypass_replay.py). TS-16: honest runs cannot trip it. AL-28: -3, one layer.
- Fallback: TS-16 row DO (narrow to the shipped class name if a reviewer finds an honest trip).
