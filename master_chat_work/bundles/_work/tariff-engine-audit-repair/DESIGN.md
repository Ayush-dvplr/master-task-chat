# DESIGN: tariff-engine-audit-repair (board a5f8657, P2)

Archetype repo-patch, category software-engineering, seed 583917. Written 2026-10-24 IST.
Levers: LV-TR-1 (H5, amplifier expected), LV-TR-2 (H2/L8), LV-TR-3 (H3/L9), LV-TR-4 (H1/L5). COUPLING: commitment-credit base.

## 1. The task in one paragraph
A stdlib-only package `tariff` (`/app/repo/src/tariff/`: `__init__.py`, `parser.py`, `core.py`, `report.py`, `__main__.py`) turns a data directory (meter reads, meters, billing periods, rate card) into one invoice document. An audit says the code drifted from `/app/ci/api_contract.md`. The agent repairs `/app/repo` in place, keeps every visible test function (correcting assertions the contract contradicts), and delivers the 7 repo-patch artifacts. Hidden tests extract `/app/out/patched-repo.zip`, import the package from it as `nobody`, run it on shipped data and on verifier-generated corpora, and compare whole rows exactly.

## 2. Spine stages
1. parse reads (`parser.parse_reads`): JSON lines, ids trimmed, quantity type check.
2. classify reads (`parser.classify`): malformed_quantity > unknown_meter > inactive_meter > outside_period > duplicate_read (first that applies).
3. rate (`core.rate_tiers`): sum accepted quantity per meter in the period, cumulative tiers, `up_to` inclusive.
4. prorate (`core.standing_line`): standing_charge x active_days / days in the month, month = the account's billing period.
5. round (`core.money`): each line amount half to even at 0.01 from the exact decimal value.
6. credit (`core.settle`): base = subtotal = sum of line amounts; if subtotal >= commitment: total = half-even(subtotal x (1 - credit_rate)), credit = subtotal - total; else credit 0.00, total = subtotal.
7. render (`report.build_invoices`, `report.render`, CLI `python -m tariff <data_dir>`): invoices by account, exceptions by read_id, amounts as 2dp strings.

## 3. Input files (all agent-visible; /app/ci and /app/repo)
| file | format | rows (target) | role / dependencies |
|---|---|---|---|
| ci/api_contract.md | md | ~260 lines | THE one contract (W10): every graded rule, every key, every error string, arbiter sentence |
| ci/meter_reads.jsonl | jsonl | >= 6000 | {read_id, account, meter, day, quantity}; refs accounts.csv (account, meter), billing_periods.csv (day) |
| ci/accounts.csv | csv | >= 2000 | account,meter,active_from,active_to (blank = open); meter rows |
| ci/billing_periods.csv | csv | >= 2000 | account,start,end,plan,commitment; one row per account; plan -> rate_card.json |
| ci/rate_card.json | json | 6 plans | plans{P: {standing_charge, credit_rate, tiers[{up_to,int or null; rate}]}} as JSON numbers |
| ci/regression_cases.jsonl | jsonl | >= 2000 | dispute replays: {name, account, period, plan, commitment, meters, reads, disputed_total, customer_claim}; claims mixed right and wrong, no contract answer field |
| ci/failing_tests.log | log | >= 2000 | unittest-style log of dispute replays failing on shipped code (FAIL/ERROR/ok lines) |
| ci/lint_report.json | json | issues list | {module, line, code, severity, message}; module_*.json lint_errors |
| ci/package_manifest.json | json | 1 obj | version, entry points; __init__.VERSION and pyproject version |
| ci/build_config.json | json | 1 obj | archive: members sorted, no dir entries, timestamp, compression, mode |
| repo/src/tariff/*.py | py | 5 modules | planted defects P1-P8 |
| repo/tests/test_visible.py | py (unittest) | ~10 tests | passes on shipped code; asserts A and B encode wrong behaviour |
| repo/README.md, pyproject.toml | md, toml | short | README repeats the /30 wording (H5 noise, never a rule the contract lacks) |
Formats: md, jsonl, csv, json, log, py, toml (7). Volume: A5 (>= 20000 lines total, >= 2000 per csv/jsonl/log) checked in Phase 2 against the playground rule's actual path scope.

Chains (length >= 4):
- C1 read -> accounts.csv meter window -> billing_periods.csv period and plan -> rate_card tiers -> energy line -> subtotal -> credit -> total.
- C2 billing_periods.csv period -> accounts.csv active window -> active days -> rate_card standing_charge -> standing line -> subtotal -> total.
- C3 regression_cases.jsonl case -> its reads and meters -> repaired package -> test_fixes regression row actual -> passed -> all_regressions_passed.
- C4 failing_tests.log FAIL/ERROR lines -> case names -> test_fixes.previously_failing; lint_report.json -> module -> module_*.json lint_errors.
- C5 package_manifest.json version -> __init__.VERSION -> pyproject version -> zip built per build_config.json.

## 4. Planted defects (each breaks one contract sentence)
P1 parser coerces JSON strings `int(str(q).strip())` (bools, floats, null already rejected). P2 standing proration `/ 30`. P3 float arithmetic and `round()` on the total only. P4 credit base includes quantities of malformed numeric reads. P5 tier `up_to` exclusive. P6 outside-period reads billed. P7 exceptions sorted by account. P8 amounts rendered as floats. Visible assert A `test_partial_period_standing_charge` expects the /30 figure; assert B `test_commitment_credit_base` expects the base including a rejected 2.5 read.

## 5. Levers
### LV-TR-4 (H1/L5) strict quantity beside a normalising rule
- Rule text, governing file `api_contract.md` (twice, L5): field block "`quantity`: a JSON integer, 0 or more." and in the malformed list: "A read is `malformed_quantity` when its `quantity` is a JSON string, a JSON number written with a decimal point or an exponent, `true`, `false`, `null`, or a negative integer." Global rule elsewhere (Conventions): "Text values (`account`, `meter`, `read_id`) are compared after removing surrounding spaces." Value types stated for every case (QC_RULINGS AVOID schema v3:32).
- Reflex reading (PREMORTEM): keep `int(str(q).strip())` for strings under the trim rule.
- Shipped separating rows (W5, L5 only): ~1.5% of shipped reads are `"37"`, `" 37 "`; easy decoys 2.5, 12.0, true, null, -4 also ship.
- Hidden: every hidden account has >= 1 quoted-integer read on a meter whose energy line it moves (and some cross a tier boundary).
- Why visible data cannot confirm: no file ships an expected invoice or exception list; coercion keeps every invariant.
- Interactions: a coerced read enters the tier sum -> energy lines -> subtotal = credit base (COUPLING) -> credit and total of the account in every corpus.

### LV-TR-3 (H3/L9) proration denominator
- Rule text, `api_contract.md` stage "Standing charge": "A meter pays `standing_charge` x active days / days in the month, where active days are the days of the month on which the meter is active." Definitions list (long enumeration, W3 clause form), entry "month": "the account's billing period, its row of `billing_periods.csv`, from `start` to `end` with both days included." rate_card block: "`standing_charge`: the charge for one month of supply."
- Reflex reading: `calendar.monthrange(start)` days.
- Hidden: every hidden period starts on day 2..27 and crosses a month end, with a length that differs from the day count of both calendar months it touches; >= 1 partially active meter per corpus.
- Why visible data cannot confirm (recorded per master note W5): every shipped period is a calendar month (1st to last day, Feb/Mar/Apr 2026), so calendar-month and billing-period readings print identical shipped figures; the visible assert uses /30, wrong under both, so correcting it to either reading passes on the shipped Feb/Mar case. No worked example where the readings differ (W6).
- Interactions: standing line -> subtotal -> credit -> total (COUPLING); also active days use the same "month".

### LV-TR-2 (H2/L8) exact-decimal half-even per line, total rounded not credit
- Rule text, `api_contract.md` stage "Amounts": "Every amount is computed from the decimal values as written in the input files. Each line amount is its exact value rounded half to even to 0.01. The subtotal is the sum of the line amounts." Stage "Credit": "When the subtotal is at least `commitment`, the total is subtotal x (1 - `credit_rate`) rounded half to even to 0.01 and the credit is subtotal minus total; otherwise the credit is 0.00 and the total is the subtotal." COUPLING sentence verbatim beside it.
- Reflex readings: float product, `Decimal(float)`, ROUND_HALF_UP, or credit = round(subtotal x rate) and total = subtotal - credit.
- Hidden: >= 3 energy lines per hidden account land exactly on a half cent with an even preceding digit and a binary float product above the tie (so float, Decimal(float) and half-up all differ from half-even); >= 1 account per corpus whose subtotal x (1 - rate) is a half-cent tie with odd-cent subtotal (round-the-credit differs).
- Why visible data cannot confirm: no shipped line, credit or total sits on a tie; all modes print the same shipped figures.
- Interactions: tie lines feed the credit base, so the subtotal, credit and total of each account move.

### LV-TR-1 (H5) contract over visible tests (amplifier expected)
- Rule text, `api_contract.md` top: "When the code, its docstrings, its README or its visible tests disagree with this file, this file wins." Section "Visible tests": "A visible test that asserts behaviour this file contradicts is corrected to this file; no visible test function is deleted, renamed or skipped. `test_fixes.json` key `corrected_tests` lists, sorted, the names of the visible test functions whose assertions were changed." Instruction repeats only the arbiter sentence (W8).
- Reflex readings: bend code back to keep asserts A/B green; or fix code but leave tests failing; or omit `corrected_tests`.
- Own rows: T2 delivered visible tests pass on the delivered package (unittest, as nobody, from the zip), T3 `corrected_tests` exact.
- If bent: loses T7, T8, T11 and every coupled test (it is the /30 and rejected-base readings). If not bent: loses only T2/T3. Opus follows the arbiter, so G10 amplifier.

### COUPLING
"The commitment credit of an account is computed on the sum of its accepted, rated, prorated lines in the billing period, before rounding of the total." Settled by: subtotal = sum of line amounts (rounded lines, IN-16), credit stage text above. Every lever slip on any line moves subtotal, credit and total.

## 6. Rejection paths
Per read, first reason that applies: `malformed_quantity`, `unknown_meter` (account/meter pair absent from accounts.csv after trimming), `inactive_meter` (day outside the meter's active window), `outside_period` (day outside the account's period), `duplicate_read` (same account, meter, day as an earlier accepted read in file order). Exception row {read_id, account, reason}, rows sorted by read_id. CLI: a missing input file -> exit status 2, stderr line `missing input: <file name>`, no stdout. Every key and string in the contract (DS-25).

## 7. Test plan (tests/test_output.py; weights 5/3/1; total 111)
Hidden generator seeded in tests/ only (seed literal changes per release, no slug/author), bounds asserted (G12). Each hidden corpus ~30 accounts, 2-4 meters each.
| id | name | w | rows owned | levers |
|---|---|---|---|---|
| T1 | archive_follows_build_config | 3 | zip member order, no dirs, timestamp, compression, mode | meta |
| T2 | visible_tests_pass_on_delivered_package | 3 | unittest result of delivered tests from zip | LV-TR-1 |
| T3 | corrected_tests_listed | 3 | test_fixes.corrected_tests | LV-TR-1 |
| T4 | regression_rows_match_package | 3 | test_fixes.regression_cases actual/passed | meta (C3) |
| T5a | module_notes_complete | 1 | module_*.json keys, lint_errors | meta |
| T5b | summary_complete | 1 | summary.json | meta |
| T5c | repair_report_and_previously_failing | 1 | repair-report.json, previously_failing | meta |
| T6 | exceptions_shipped | 5 | exceptions on shipped data | LV-TR-4 |
| T7 | standing_lines_shipped | 5 | standing lines on shipped data | LV-TR-1 (A) |
| T8 | settlement_shipped | 5 | subtotal/credit/total on shipped data | LV-TR-1 (B), LV-TR-4 |
| T9 | exceptions_hard | 5 | H1 exceptions | LV-TR-4 |
| T10 | energy_lines_hard | 5 | H1 energy lines | LV-TR-2, LV-TR-4 |
| T11 | standing_lines_hard | 5 | H1 standing lines | LV-TR-3 |
| T12-14 | subtotals/credits/totals_hard | 5 each | H1 | COUPLING (all) |
| T15-17 | subtotals/credits/totals_shuffled_scaled | 5 each | H2: fresh seed, rows shuffled, one plan rate x 1.0375 (G6) | COUPLING |
| T18-20 | subtotals/credits/totals_relocated | 5 each | H3: fresh seed in a renamed dir, `python -I` from a foreign cwd (G6) | COUPLING |
| T21-23 | subtotals/credits/totals_rotated | 5 each | H4: fresh seed, rows rotated | COUPLING |
| T24 | missing_source_named | 3 | delete billing_periods.csv: exit 2 + stderr names it (G6) | meta |
| T25 | runs_twice_identical | 3 | H1 twice byte-equal stdout (G6) | meta |
Negatives (G4, cheating only): `negative_hardcoded_sample_answers` -5 (package output on H1 equals its shipped-data invoices for the same account ids, i.e. hard-coded), `negative_visible_test_removed` -3 (a visible test function deleted, renamed or skipped). Each act <= 5 across tests + judge (AL-28).
Shares: hidden/mutated reruns T9-T25 = 81/111 = 73% (G3 >= 30%); shipped-only T6-T8 = 15/111 = 14%; isolated meta = 15/111. Every assertion message names the first differing path (G7). No test returns early on another test's scalar. Above 35? No (27 incl. negatives).

## 8. Judge plan (tests/judge.toml, batched, five-key header exact)
R1 recomputes every shipped invoice (lines, subtotal, credit, total) outside its program and compares, w3 (invoice family). R2 recomputes the exception list of the shipped reads outside its program and compares, w3. R3 recomputes every regression case actual outside its program and compares with test_fixes.json, w3. R4 constructs its own input with a billing period that starts mid-month and crosses a month end and checks the standing line, w3 (JD-15 per-lever, shipped data lacks it). R5 constructs its own input with a line on an exact half cent and checks the amount, w3. R6 J9 altered copy rerun, w3. R7 J4 code quality on `/app/repo/src/tariff/*.py` exact J4 text, w3. R8 J6 response lists every function it changed, each by module and name, w3. R9 J3 honesty, -5. R10 writes to `/app/ci/api_contract.md`, -3. R11 grader-read anchored wording, -5. solve.sh self-check prints `check R1 ok` ... `check R6 ok`, `check R8 ok`. JUDGE_MAP.md per criterion.

## 9. Expected loss per lever (careful solver, predicted; G10 runs replace this in Phase 4)
| lever | hidden input and checks lost | alone pts / 111 | % | all-but-one overall (rubric 90) |
|---|---|---|---|---|
| LV-TR-3 calendar month | crossing periods in H1-H4: T11, T12-T23 | 65 | 58.6 | 65.7 |
| LV-TR-2 float / half-up | tie lines in H1-H4: T10, T12-T23 | 65 | 58.6 | 65.7 |
| LV-TR-2 variant: round the credit | odd-subtotal tie totals: T13,T14,T16,T17,T19,T20,T22,T23 | 40 | 36.0 | 77.0 (variant only) |
| LV-TR-4 coerce quoted ints | shipped + hidden: T6, T8, T9, T10, T12-T23 | 80 | 72.1 | 59.0 |
| LV-TR-1 bend code to asserts | T3, T7, T8, T11, T12-T23 | 78 | 70.3 | 59.9 |
| LV-TR-1 fix code, keep asserts | T2, T3 | 6 | 5.4 | amplifier |
One-fact-wrong (CL-4): one line off by 0.01 on one H1 account fails its line test and H1 subtotal/credit/total: about 20/111 (18%) per lever.
Most likely careful-solver loss: LV-TR-3 (T11, T12-T23), then LV-TR-4 (T6, T9 + coupled).

## Harden round 1 (d62ffe6, 2026-10-25 IST)
Probe 1 (build a5f8657): tests 121/121, judge 15/24, overall 81.25; every lever named its separating case
(DIAGNOSIS: OUT 20261024_tariff-engine-audit-repair/harden_r1/DIAGNOSIS.md, primary cause 4).
Sections 2-6 above describe the build; where they differ, this section wins.
- Spine stage 3 (rate): tiers by account position across the account's meters in ascending `meter` order
  (N3, H6). Stage 4 (prorate): Month = calendar month; standing exact = sum over each month holding an active
  day of standing_charge x active days in that month / days in that month (N2, H3). New stage 4b (share):
  `billing_periods.csv` gains `allowance`; energy lines take equal parts capped at their exact value, the rest
  re-shared among lines not yet at zero as often as some stays unshared (N1, H7). Rounding, credit, render
  unchanged.
- Uncounted gates: LV-TR-4 (exception :85-86 now points to the field rule; enumeration removed), LV-TR-2,
  LV-TR-1, COUPLING.
- Data: datagen regenerated meter_reads, accounts, billing_periods, regression_cases, failing_tests.log
  (lint_report.json hand-kept). Shipped/regression: allowance settles in one pass, no period crosses a
  month end, every account within tier 1.
- Hidden families: FR (fresh+rescaled) N1+N2, LT (relocated+rotated) N1+N3, A (api) N2+N3. 31 positive
  checks, 127 points (exceptions w3; rescaled and api line tests split into energy and standing).
- Judge: R12 own third-share input, R13 own account tier crossing (w3 each); 13 criteria, 30 positive.
- Reference fix: `_Ledger` reads standing_charge through `Fraction` (integer standing_charge crashed).
- Figures: LEVERS.md, COST_TABLE.md, RULE_COVERAGE.md (57 mutants, 0 uncovered), JUDGE_MAP.md, XREF.md.

## Harden round 2, Phase 2: L11 pilot (7f1d771, 2026-10-25 IST)
Probe 2 (d62ffe6): tests 127/127, judge 3.33, overall 51.66; every lever was an explicit sentence and was
transliterated (Phase 1 DIAGNOSIS, board 0dd7a8c). N1, N2, N3 stay word for word. This section wins over
the sections above where they differ.
- New lever L11 (evidence induction, no rule sentence anywhere): `billing_periods.csv` `plan` may hold a code
  that is no key of `rate_card.json`; exactly one plan lists it in a `codes` list (trimmed). Spine stage 3
  gains a resolve step before rating: key match, else the one entry whose trimmed `codes` holds the value.
  Invoice `plan` stays the trimmed billing value (contract invoice shape :101-103, format statement only).
  Witness: `rate_card.json` `codes` lists (:7-10, :29-31, :50-53, :72-74, :93, :108-110); governed data:
  503 of 2000 shipped billing rows. Shortlist S1-S4 and the pick: LEVERS.md; fit of 18 readings:
  UNIQUENESS.md (verdict ONE); EVIDENCE_MAP.md.
- Data: datagen.py CARD gains `codes`; `recode_periods` (own RNG, SEED+11) renames 30% of coded rows after
  commitments are settled, so every amount is unchanged; only billing_periods.csv and rate_card.json
  changed (regenerated and diffed, Always 11).
- Hidden: every corpus card plants fresh codes (`_plant_codes`, `_share_stem`); new L11 family recoded
  (H7 seed, 30 accounts, L11 only) and its mutated rerun renamed (fresh codes, plan order and rows rotated).
  6 new checks x 5; 37 positive checks, 157 points; L11 alone 40 (25.5%).
- Instruction: line 1 drops the visible-tests trap clause (IN-17), line 13 ends with the G5 exactness
  clause only.
- Judge: R14 (w3) own code-named invoice recomputed outside the program; solve.py prints `check R14 ok`;
  14 criteria, 33 positive.
- Figures: COST_TABLE.md, RULE_COVERAGE.md (61 mutants, 61 killed), JUDGE_MAP.md, QC_DEFENCE.md, XREF.md.

## Test-hardening round (78d433c, 26 Oct 2026)

Probe attempt 3 scored tests 100: every rule fired on shipped data next to its sentence. This round adds five
quiet branches (S6) that the shipped files never fire and every hidden corpus fires: Q1 estimated reads
(`estimated`, `replaced_estimate`), Q2 `standing_changes`, Q3 several billing rows per account, Q4 allowance
carried to the next invoice, Q5 several accounts rows per meter. Each is a sentence in the contract paragraph it
governs plus one toy example (X1/Y9/2031). Shipped files are unchanged (no `estimated` key, no `standing_changes`,
no second row).
- Reference `_Ledger(texts, off)` implements all five; `off` gives the habitual reading per rule for asserts.
  Base corpora give byte-identical documents to round 2 (OUT/baseline/ref_before.json vs ref_ledger.json).
- `_base_texts(corpus)` is the round-2 generator; `_corpus_texts(corpus)` = `_quiet(base, seed)`, own RNG,
  17 planted accounts per corpus (Q1 3, Q2 3, Q3 2, Q3+Q4 2, Q5 2, pairs Q1+Q3, Q2+Q3, Q3+Q5, Q1+Q5,
  Q2+Q3+Q4). `_assert_quiet` checks fires, ownership and base invariance; 300-seed sweep 0 crashes.
- Grading: earlier hidden checks skip owned accounts; six owned-row criteria compare whole invoices and exception
  rows across all 7 hidden corpora: estimated 15, standing_change 15, meter_row 15, billing_row 10,
  carried_allowance 8, combined_row 6. Positive test points 157 -> 226; judge unchanged (33).
- solve.py implements Q1-Q5 (parser `_row`, `_active` over windows, actual reads first; core `standing_charge`,
  per-day `standing_line`, `share_allowance` returns the leftover; report per-row invoices with carry).
- Measured: oracle 1.0; Q alone 6.2-10.6%; first write 69.5; all-but-one 93.8 (COST_TABLE.md).

## Test-hardening round 2 (15b380e, 27 Oct 2026)
The P13 blind read of round 1 scored 226/226: every Q rule was a formula beside its field. This round adds three
rules that need evidence or state from other records, all hidden-only (shipped data unchanged):
- U1 unique fit: a plan may carry `revisions`; optional `payments.csv` (`account,start,paid`) gives paid
  amounts; the plan is rated with the one revision under which every paid invoice on it totals its paid amount,
  else its own `tiers` (Tier definition). Witness totals depend on N1, N3, Q3, Q4 (asserted).
- D1 arrears: no credit when the previous invoice by `start` was paid below its total (Credit paragraph).
- D2 cumulative reads: billed quantity = count less the latest earlier accepted cumulative count of the meter;
  whole count on a fall (Definitions: Billed quantity, Period quantity).
- Generator: `_levers` after `_quiet`, own RNG `Random(seed*37+11+1000003*attempt)`, mini corpus merged in;
  `_assert_levers` proves non-lever rows equal the round-1 document and each lever moves only its owners.
- Grading: 15 owned checks x5 (75 points); positive 226 -> 301; judge unchanged (33).
- Measured: oracle 1.0; blind round-1 program 0.7508; each lever alone 0.9169; first write 0.5216.

## Test-hardening round 3 (fc1fb76, 27 Oct 2026)
Why: fresh blind reads of the round-1 and round-2 bundles scored 100% of tests; every fully stated rule was
transliterated. This round adds a computational core: `python -m tariff --statements <data_dir>` (contract :25-28)
writes one statement per account in the new optional `vouchers.csv` (:129-132) with `redeemed` = the vouchers whose
amounts reach the largest sum not above the account's balance, first id list on ties (:209-229). Balance is the
invoice totals less paid amounts, so it carries the whole replay (Q1-Q5, U1, D1, D2). Shipped instances are small
(1-6 vouchers); hidden statement corpora add 3 big clone accounts (45-70 vouchers, balances 50-90k) and 8 smaller
ones per corpus; sources come from one lever family per corpus (`_STATEMENT_LEVER`). No size bound, no method word.
Reference (big-integer reachability with id-order rebuild) 0.26 s per corpus in Docker against the 10 s limit.
Tests: 22 new checks (shipped exact 5; per hidden corpus feasible 3, due 5, redeemed 5) -> 397 positive points.
Invoice document, checks and expectations byte-unchanged (statement corpora are separate texts). solve.py gains
`build_statements` and the `--statements` branch of `__main__`. See LEVERS.md, BRANCH_FIRE.md, COST_TABLE.md round 3.

## Wave 1 hardening (d11904c, 27 Oct 2026)
Why: the fresh blind read of round 3 scored 397/397 in 7 minutes with a big-integer bitset over cents; every r3
hidden balance (4M-12M cents) fits such a table. Lever P-1 (computational core), data only, no new sentence.
Seven new hidden "ledger" statement corpora (`_ledger_texts`, RNG `Random(seed*59+31+1000003*attempt)`, one per
`_STATEMENT_LEVER` family) clone three accounts with read quantities scaled so balances land at 3e10-1e11 cents;
each has 55-66 vouchers: 46-55 multiples of one drawn unit (50 000-100 000 cents) plus 9-11 small amounts whose
total stays below the unit, with id ties planted in both groups; plus 3 small tie accounts and 1 overpaid account.
Reference `_redeem_split` (test and oracle): splits by suffix gcd, bitset over units for the large group, every
combination of the small group for the rest; exact for any input (no split found means plain search). 0.03-0.12 s.
Tests: 21 new checks (feasible 3, due 5, redeemed 5 per corpus) = 91 of 488 positive points (18.6%). r3 checks and
r3 `_redeem` byte-unchanged. Shipped data gains account A1643 (12 vouchers, same two-group shape at 311.48),
so the shipped document gains one statement; the 60 old statements are unchanged. See LEVERS.md, QC_DEFENCE.md,
BRANCH_FIRE.md, COST_TABLE.md wave 1 and OUT DESIGN.md / KILL_TEST.md for the measured kill table.

## Harden round _ql1 (ed621c7, 29 Oct 2026)
Start bytes: QL zip (dfd8e457d203) plus the `_visible_test_removed` add-on (module-level Assign/Expr and
setUpModule/tearDownModule bodies watched; both CHANGES.md bypasses now fire, an agent's own @skipIf does not;
WORK/ql1/bypass_replay.py). Pushed bytes backed up in WORK/pushed_0de116d29fdb/.
Why: run a4 scored tests 81.35 with only the ledger corpora lost (CRASH by OOM of the cent bitset); the r3
statement corpora kept balances below 1.2e7 cents, so the same reflex passed them (OUT DIAGNOSIS.md).
- F1: the 7 r3 statement corpora (`*_statement_*`, 91 points, names and weights kept) now carry hidden-scale
  documents (`_scale_texts("statement", corpus)`): three copied accounts at balances 4e10-8e10 cents, two of the
  ledger shape (unit group plus small group) and one with 36 unrelated large vouchers (gcd 1, six equal-amount
  pairs, split cost above SPLIT_LIMIT), plus 3 small tie accounts and 1 overpaid account.
- F2: two more sets of the same shape on reseeded documents, `batch` and `cycle` (RNG seed*61+37, seed*67+41),
  42 new checks (feasible w3, due w5, redeemed w5 per corpus), 182 points. Positive test points 488 -> 670.
- Reference `_redeem_any`: gcd split when its cost is at most 1<<24, else meet in the middle with the first id
  list (`_redeem_halves`); 0 mismatches against exhaustive search on 3000 small cases; ledger documents
  byte-identical to the pushed reference.
- Judge: R14 (own large statement input, run time), R15 (redeemed recomputed outside the package on a tied input),
  R16 (one tie decision shown); 16 criteria, 42 positive; solve.py self-check prints check R14/R15/R16 ok.
- No new rule text: instruction.md, environment/ and the contract are byte-identical to the QL bytes.
- reward.toml: test 0.5/670, judge 0.5/42.
- DESIGN READY numbers (kill table, agent rescore, timing): see section below once measured.

### DESIGN READY (_ql1, measured 12:05 IST)
- (a) predicted final = (45.67 + 21.4) / 2 = 33.5 <= 35 (agent package and blind_r3 both 45.67; first_write 28.06).
- (b) lever share 364/670 = 54.3% >= 40%; held-out w5 535/670 = 79.9% >= 50%.
- (c) blind programs: blind_r3 45.67, first_write 28.06; none above 65.
- (d) verifier worst measured 325 s, analytic ~340 s <= 2430 s.
- (e) kill table (KILL_TEST.md _ql1): every generic solver loses >= 15% of lever points (tie_naive 39.8% WRONG, greedy WRONG, gcd_split CRASH 75%, MITM forms TIMEOUT 100%); CRASH+TIMEOUT <= 54.3% <= 60% cap; shipped inputs fast; reference 0.28 s <= 2.5 s.
