# LEVERS tariff-engine-audit-repair (harden round 1, d62ffe6)

File:line refer to `environment/ci/api_contract.md` (194 lines, agent path `/app/ci/api_contract.md`).
Families: FR = fresh + rescaled (seed H1, 30 accounts), LT = relocated + rotated (seed H3, 24 accounts),
A = api (seed H5, 45 accounts). Planting: FR carries N1 + N2, LT carries N1 + N3, A carries N2 + N3.
Measured scores come from `WORK/measure_variants.py` (oracle repair with one slip) scored by
`WORK/run_checks.py`, 127 points.

## N1 allowance re-share (H7 re-entry) - counted
- Rule: Definitions :46-48 (Energy share: first an equal part, never more than the exact value, a part a
  line cannot take stays unshared); Amounts :125-128 (unshared allowance shared again in equal parts,
  never more than a line's remaining exact value, among the energy lines not yet at zero, as often as some
  stays unshared and such a line remains); Line amount :49-50; column :69-72.
- Reflex reading: one pass of equal parts capped at each line (or one re-share); allowance ignored by the
  probe-1 agent program.
- Shipped: 1080 of 2000 accounts carry an allowance; every one settles in the first pass (one-pass and
  two-pass habits give 0 differing accounts). Regression cases: 980 with allowance, all one pass.
- Hidden: every second non-quiet FR and LT account has an allowance that needs >= 3 passes and leaves
  >= 0.05 after two (generator search, `_assert_bounds`); fresh 14, rescaled 12, relocated 11 accounts.
- Checks the wrong reading fails: fresh energy/subtotals/credits, rescaled energy/subtotals/credits,
  relocated lines/subtotals/credits, rotated lines/subtotals/credits = 60 points (47.2%). One/two-pass
  variants 67/127; ignoring the allowance 59/127 (also shipped energy/settlement and regression rows).
- Interactions: a line's net exact value feeds the half-even rounding (TR-2) and the subtotal and credit
  (COUPLING); tie counting uses net values.

## N2 calendar-month proration (H3 defined term) - counted
- Rule: Definitions :51 Month = calendar month; :43 Active days = days of the billing period on which the
  meter is active; Standing :115-119 sum over every month holding an active day of standing_charge x
  active days in that month / days in that month.
- Reflex reading: days of the start month (or the period length) as the denominator.
- Shipped: periods are calendar months or within-month short periods (470 accounts, 8-27 days); none
  crosses a month end, so the start-month habit differs on 0 accounts (period length differs on 499).
- Hidden: FR and A periods start on day 2..27 and cross one month end, 27/29/32/33/34 days long.
- Checks the wrong reading fails: fresh standing/subtotals/credits, rescaled standing/subtotals/credits,
  api standing/subtotals/credits = 45 points (35.4%); start-month variant 82/127, period-length 69/127.
- Interactions: standing exact value feeds rounding and subtotal; LT corpora use whole calendar months of
  28 or 31 days, so /30 still fails there.

## N3 account tier position (H6 counter wider than the line) - counted
- Rule: Definitions :38-40 Account position counted over the account's meters in ascending `meter` order;
  Energy :107-113 tiers cover account positions; :52 Period quantity stays per meter.
- Reflex reading: tiers restart for each meter (the probe-1 agent program).
- Shipped: every account's accepted units stay at or under tier 1 `up_to` (103 accounts exactly at it), so
  per-meter tiers differ on 0 accounts; regression cases likewise.
- Hidden: LT and A tie meters fill tiers in meter order and cross tier boundaries jointly; the top line of
  each crossing meter is a half-cent tie unit.
- Checks the wrong reading fails: relocated lines/subtotals/credits, rotated lines/subtotals/credits, api
  energy/subtotals/credits = 45 points (35.4%); per-meter variant 82/127.
- Interactions: units per tier feed exact values and the N1 share in LT.

## Uncounted gates (kept)
- LV-TR-4 strict quantity (H1): :63 "a JSON integer, 0 or more"; :85-86 exception points to the field rule
  (enumeration removed, LV-ENUM clean). Coercion variant 41/127.
- LV-TR-2 exact half-even per line, round the total: :124-130, :132-136. Half-up 52/127, credit rounded
  102/127. Half-cent ties stay in hidden data (judge R5 hook).
- LV-TR-1 contract over visible tests (amplifier): :3-5, :141-145; keep-asserts variant 121/127.
- COUPLING: credit on the subtotal of line amounts (:132-136) carries every line error into subtotal,
  credit and total tests of the same corpus.

## Totals
- Habit slips alone: N1 60, N2 45, N3 45 of 127; union 90. Probe-1 agent program 23/127 = 0.1811.
- Differential fuzz (OUT/fuzz_r1): agent program differs on 0/79 lever-free corpora, 74/74 N1,
  74/74 N2, 79/79 N3.

# Harden round 2, Phase 2 (7f1d771): L11 evidence-induction pilot
N1, N2, N3 stay exactly as written above (master note 1; Options A and B dropped). One new lever, L11.

## L11 shortlist
| shape | fact type (LEVER_RULES 1, list b) | witness | wrong readings | UNIQUENESS / 0b |
|---|---|---|---|---|
| S1 plan codes (PICK) | undefined symbol defined by a config value / alias register (listed candidate set) | `rate_card.json`: a plan entry carries `codes`, a list of tariff codes; a `billing_periods.csv` row names its plan by one of them | key only (no entry), key casefold, key alnum-normalised, key prefix, first plan, last plan, most common plan, skip the invoice, codes untrimmed | ONE: only key-else-listed-code names an entry for every billing value in every corpus and reproduces every graded invoice (UNIQUENESS.md) |
| S2 re-installed meter, two `accounts.csv` rows | merge winner | second row for the same pair | first wins, last wins, union of windows | FAIL 0b: no input fact separates first/last/union (silence), and "one row per meter" (:65-67) is contradicted |
| S3 plan revisions with a `from` date | flag-versus-date | revision entry in `rate_card.json` | bind at period start, bind at period end, prorate | FAIL UNIQUENESS: start and end binding coincide on every period that sits inside one revision; a crossing period has no determinate answer |
| S4 tier `block` sizes beside `up_to` | undefined symbol | `block` in the same tier entry | block as cap, block as width | FAIL W5: witness and governed data in the same file, and contradicts Energy lines :107-113 |

## L11 plan codes (counted)
- Rule (no sentence anywhere): the plan of an account is the `rate_card.json` entry whose key is the
  trimmed `plan` value; when no key matches, it is the one entry whose `codes` list holds that value
  (each code trimmed). The invoice `plan` field is the account's trimmed `plan` value as written (a
  format statement, contract invoice shape, same output under every reading of the lookup).
- Witness: `environment/ci/rate_card.json` `codes` lists (cited line in EVIDENCE_MAP.md); the governed
  data is `environment/ci/billing_periods.csv` `plan` column (different file). Never labelled; the key
  name `codes` says what the values are, not what they prove.
- Reflex reading: `card["plans"][period["plan"]]` (probe-2 program `report.py`, and the repo itself):
  a KeyError on shipped data; the silent variants are a default plan or a normalised key.
- Hidden: every hidden corpus card carries fresh codes (new letter and digits each corpus, one code
  padded with a space); the L11 family `recoded` names 40% or more of its accounts by code, and the
  mutated rerun `renamed` renames every code in card and billing together and rotates plan order.
- Checks the wrong reading fails: recoded lines/subtotals/credits, renamed lines/subtotals/credits, and
  the shipped invoice checks (see COST_TABLE.md for the measured share).
- Interactions: N1-N3 stay neutral in recoded/renamed (whole months, tier 1, one-pass allowance), so the
  family owns L11 alone; the plan feeds tiers, standing and credit rate, so one wrong plan fails lines,
  subtotal and credit of that account.
- Witness lines (shipped): `environment/ci/rate_card.json:108-110` IND-2 `["T3415"]` governs
  `billing_periods.csv:2` (A0001); also :7-10 HOME-A (two codes), :29-31 HOME-B `T1140` (shares the
  `T11` stem with HOME-A), :50-53 SME-1 with the padded `" T2319"`, :93 IND-1 `[]`. 503 of 2000 billing
  rows carry a code.
- Constructed hidden cases (generator `_plant_codes`, `_share_stem`, `_name_by_code`, `_renamed`,
  asserted by `_assert_codes`): a plan without codes, a two-code plan with both codes billed, a padded
  card code, a padded billing value, a three-character stem shared across two plans, owners other than
  the first and last entry, every code billed.
- Measured (OUT/g10b): L11 first-plan or last-plan default 117/157 (40 points lost = 25.5%: shipped
  standing 5, shipped energy and settlement 5, recoded 15, renamed 15); key-only and untrimmed codes
  crash on shipped data (loud; would cost the same 40 plus whatever the crash takes). One fact wrong on
  one recoded account 127/157 (CL-4 measure). Mutants M58, M59, M60, M62 killed (RULE_COVERAGE.md).
- UNIQUENESS: ONE (UNIQUENESS.md; 18 readings x 83 witness sets).

# Test-hardening round (78d433c): quiet branches Q1-Q5 (S6)

All earlier levers (N1-N3, L11, LV-TR-1/2/4) and their checks and weights are kept unchanged. Five new stated
rules, each one paragraph sentence in the part of api_contract.md it governs plus one toy example on invented
values; shipped data never fires them (BRANCH_FIRE.md), every hidden corpus fires each 3-8 times.

| lever | sentence (api_contract.md) | toy | habitual first write | hidden planting | criterion (weight) | alone |
|---|---|---|---|---|---|---|
| Q1 estimated reads | :65, :111-115 | :117-119 | read dict ignores `estimated`; duplicate by account/meter/day in file order | 3 single + Q1+Q3, Q1+Q5 per corpus; estimate before/after actual, two estimates, malformed actual, explicit false | estimated_read_accounts_on_* (15) | 9.3% |
| Q2 standing changes | :92-96, :142-143 | :96-99 | `plan["standing_charge"]` per month | 3 single + Q2+Q3, Q2+Q3+Q4; unsorted lists, change before the period, mid-month change, future change | standing_change_accounts_on_* (15) | 9.3% |
| Q3 several billing rows | :76-82, :110, :127-128 | :82-85 | `periods[account] = row` (last wins) | 2 single + 2 Q3+Q4 + 4 pairs; rows written out of start order, gap read | billing_row_accounts_on_* (10) | 10.6% |
| Q4 allowance carried | :154-156 | :156-159 | leftover allowance dropped | 2 Q3+Q4 + Q2+Q3+Q4; single meter, 2 rows and 3 rows with an empty middle row | carried_allowance_accounts_on_* (8) | 6.2% |
| Q5 several accounts rows | :41-43, :67-69 | :70-73 | `meters[(account, meter)] = row` (last wins) | 2 single + Q3+Q5, Q1+Q5; two windows with a gap read, written reversed | meter_row_accounts_on_* (15) | 9.3% |
| pairs (T4) | as above | | | Q1+Q3, Q2+Q3, Q3+Q5, Q1+Q5, Q2+Q3+Q4, one each per corpus | combined_row_accounts_on_* (6) | in each row above |

Weights: master GO named 15/15/15/12/12; shipped as 15/15/15/10/8 plus 6 for the pair criterion (total 69 of
226). Reason: a pair account belongs to one criterion only (TS-26), so the pair points come out of the Q3 and Q4
budgets that the pairs mostly carry; a Q3 miss also fails the Q3+Q4 accounts, so Q3 alone still costs 24 points.
Measured alone costs 9.3/9.3/10.6/6.2/9.3% stay inside 5-12%.
The kit allows only weights 1/3/5 per check (tests_qc W2), so each group is split by corpus set into checks of
weight 5 or 3 (`_check_owned(group, corpora)`): estimated, standing_change, meter_row 3 x 5 over {fresh,
rescaled} / {relocated, rotated} / {api, recoded, renamed}; billing_row 2 x 5, carried_allowance 5 + 3,
combined_row 3 + 3 over {fresh, rescaled, relocated, rotated} / {api, recoded, renamed}. Totals and costs are
unchanged (each Q variant fails every corpus); tests count 54.
None of the five fails loudly: each habitual reading yields a full document with wrong rows (no KeyError, no
empty output); the dict-last-wins readings are the code the round-3 agent wrote (report.py `_load`).

## Test-hardening round 2 (15b380e, 27 Oct 2026)
Three hidden-only levers; shipped data has no `revisions`, no `cumulative`, no `payments.csv`.
| id | shape | sentence | careful-reader reading | wrong document | owned checks (pts /301) |
|---|---|---|---|---|---|
| U1 | S3 unique fit | environment/ci/api_contract.md:63-70 (Tier definition), field form :115-117, witnesses in payments.csv :119-123 | ignore `revisions`; first fitting revision (H8); first revision | lines priced on wrong tiers, totals plausible | revision x3 (15) + revision_rows x2 (10) = 25 |
| D1 | derived state (previous invoice by `start`) | environment/ci/api_contract.md:191-195 | per-row credit; missing row read as paid 0 | credit on an invoice after an underpaid one | arrears x3 (15) + arrears_carried x2 (10) = 25 |
| D2 | derived state (previous accepted cumulative read by `day`) | environment/ci/api_contract.md:53-61, field :81 | bill the count; chain per invoice; chain in file order | energy lines billed on running counts | cumulative x3 (15) + cumulative_rows 5 + cumulative_meter_rows 5 = 25 |
Witness dependence: plan A's true revision fits only with Q3, N1, N3 right (asserted in `_levers_once`: under off {Q3}, {N1}, {N3} the choice differs). Plan B is a two-fit decoy (truth: own tiers), plan C no fit. T4 combos: U1+Q3, D1+Q2+Q3+Q4, D2+Q3, D2+Q5, D2 with Q1 replaced estimate.

## Test-hardening round 3 (fc1fb76, 27 Oct 2026): computational core
Stated rules alone were transliterated by careful blind reads (rounds 1-2), so this round adds one exact-optimum
figure defined by objective and constraints only, plus a long-replay link to the round-1/2 state.
| id | shape | sentence | careful-reader reading | wrong document | owned checks (pts /397) |
|---|---|---|---|---|---|
| S1 | computational core: exact optimum (subset sum, largest sum not above balance) | environment/ci/api_contract.md:219-223 (redeemed), example :226-229; CLI + 10 s limit :25-28 | largest-first greedy; exact dict/set or array DP over cents; plain enumeration | greedy: a feasible but smaller sum (redeemed and due wrong); DP / enumeration: no output inside 10 s on hidden corpora | per hidden corpus redeemed_exact 5 + due_exact 5 (70), shipped_statements_exact 5 |
| S2 | tie verdict (first id list, plain string order) | environment/ci/api_contract.md:219-223 | fewest vouchers first; numeric id order | a different optimal set (due right, redeemed wrong) | redeemed_exact (tie accounts 2-4 per corpus) |
| S3 | long-replay link: balance = invoice totals less paid amounts (clamped at 0.00) | environment/ci/api_contract.md:217-218 | ignore payments; skip clamp | wrong balance -> wrong optimum | feasible 3 per hidden corpus (21) + the above |
Hidden statement corpora: `_statement_texts(corpus)` = the corpus's invoice texts + 3 cloned big accounts (balance
50,000-90,000.00, 45-70 vouchers whose amounts share a factor that does not divide the balance, so the balance is
never reached exactly) + 8 smaller accounts (6-14 vouchers, planted ties) + `vouchers.csv`; own RNG
`Random(seed*53+29+1000003*attempt)`. Sources come from one round-1/2 lever family per corpus
(`_STATEMENT_LEVER`: fresh D2, rescaled D1(+Q2/Q3/Q4), relocated Q1, rotated Q2, api Q5, recoded Q3+Q4, renamed U1),
so a miss in that rule moves the balance and the optimum of 2-5 statements in that corpus only. No size, count or
width bound is stated; no method word. Shipped `vouchers.csv`: 198 rows, 60 statements, 1-6 vouchers each, so a
plain enumeration is exact and fast on shipped data.
Invoice document, its checks and their expected values are byte-unchanged (statement corpora are separate texts).

## Wave 1 hardening (d11904c, 27 Oct 2026): P-1 computational core at ledger scale (no new sentence)
Round 3's figure (S1) was beaten in 7 minutes by a big-int shift bitset over cents (blind 36f4266, 397/397). This
wave keeps S1-S3 and every sentence as written and adds seven hidden "ledger" statement corpora where any one-sum
table is too wide and every 2^(n/2) split is too slow.
| id | shape | sentence | careful-reader reading | wrong document | owned checks (pts /488) |
|---|---|---|---|---|---|
| S1L | computational core: S1 at ledger scale (balances 4.0e10-8.0e10 cents, 55-66 vouchers per big account) | environment/ci/api_contract.md:219-223 (redeemed), :224 (due), CLI + 10 s limit :25-28 (all unchanged) | exact bitset / dict / array table over cents; meet in the middle; Pareto list; branch and bound; greedy | table: out of memory or no output in 10 s; halves, Pareto, B&B, enumeration: no output in 10 s; greedy: feasible smaller sum (due and redeemed wrong) | per ledger corpus: feasible 3 + due_exact 5 + redeemed_exact 5 = 13, x7 = 91 |
Structure the reference relies on (seen in the data, never stated): on each big account most voucher amounts share a
large common unit (gcd 50,000-99,999 cents) and the rest add up to less than that unit, so the unit part is searched
in units (width <= 1.6e6) and the rest (9-11 vouchers) in every combination for what the unit part leaves over.
`_redeem_split` (tests) and `_redeem` (solution) pick the split by cost; they are exact on any input (equal to the
round-3 reference on shipped + 7 r3 corpora and to plain enumeration on 3000 random instances: 0 mismatches).
Ledger corpora: `_ledger_texts(corpus)` = corpus invoice texts + 3 cloned big accounts (reads scaled so the balance
lands in 3e10-1e11 cents) + 3 tie accounts + 1 overpaid account + `vouchers.csv`; own RNG
`Random(seed*59+31+1000003*attempt)`; same lever family per corpus as `_STATEMENT_LEVER`. Branch plants asserted per
corpus: tie inside the unit group, tie inside the small group, overpaid balance 0, both groups used.
Shipped item 7: account A1643 (balance 311.48, unit 21.43, 12 vouchers, large-group tie) added to
environment/ci/vouchers.csv (198 -> 210 rows, 60 -> 61 statements; the other 60 statements unchanged).
Round-3 checks (91 checks, 397 points) and `_redeem` are byte-unchanged (insert-only diff of test_output.src.py).

## P12 fix of QC v1 (8e1b2d5, 27 Oct 2026)
- L11 plan codes: now stated in api_contract.md:66-67 and :121-123 (QC v1 F06, IN-16 DO, general case). Tests and hidden corpora unchanged; L11_first_plan / L11_key_only single-variant losses measured before and after in OUT/RECHECK_FIX.md `## Trap survival`. Effect: easier to discover (the blind r3 program already resolved codes, so measured blind loss on L11 was 0 before the change); compensation in the family: judge R13 (w3) now pays the agent's own code-named probe input.
- Shipped settlement check split (TS-13): shipped_energy_lines_exact 3, shipped_subtotals_exact 1, shipped_credits_and_totals_exact 1 (was one w5 check). L11 test set on shipped data is these three plus shipped_standing_lines_exact.
- P-1 ledger lever (21 checks, 91/488) byte-identical in tests/ (G7 diff: no hunk in the ledger checks or corpora).
- Judge renumbered after deleting R10: R11 -> R10, R12 -> R11 (third share, N1), R13 -> R12 (tier crossing, N3), R14 -> R13 (code probe, L11).

## Harden round _ql1 (ed621c7, 29 Oct 2026): hidden scale on every statement set
| id | shape | sentence | reflex reading (agent a4 program) | hidden cases | checks the wrong reading fails | interactions |
|---|---|---|---|---|---|---|
| S1H | P-1 computational core at hidden scale on all statement sets | environment/ci/api_contract.md:219-226 (redeemed, due), :25-28 (CLI, 10 s), task.toml memory_mb 4096; unchanged | cent bitset `1 << (balance+1)` with a suffix list (agent core.py:120-140) | per corpus doc: 2 ledger-shape accounts, 1 account of 36 unrelated large vouchers (gcd 1, 6 equal-amount pairs), 3 tie accounts, 1 overpaid | statement x7 (91), batch x7 (91), cycle x7 (91), ledger x7 (91) = 364 of 670 | balance carries the invoice replay of the corpus's lever family (`_STATEMENT_LEVER`); one call per corpus |
| S1T | tie verdict at hidden scale | :223-225 first id list | a search that returns any optimal set | equal-amount pairs used and unused in the 36-voucher account; ties in both ledger groups | redeemed_exact checks of all four sets | due stays right, only redeemed fails (WRONG) |
Single-technique outcomes per corpus doc (one call): cent bitset dies on memory; gcd split alone cannot finish the 36-voucher account; halves alone cannot finish the 55-66-voucher ledger account; a combined search with a naive tie order writes the wrong id list.

## P12 0d8cf26 (QC v3 fix, 29 Oct 2026)
- S1H, S1T: no check, input, weight or time limit changed. TS-11 fix gives each `_memo` key its own lock, so one `--statements` / `--ledger` child runs per corpus doc under rewardkit's 8 threads (before: duplicate children of the same doc ran side by side). Serial results are identical by construction; the kill table (measured serially) stands. S1H text corrected to six equal-amount pairs (matches `_scale_once`). Effect on every lever: none.
