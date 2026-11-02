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
