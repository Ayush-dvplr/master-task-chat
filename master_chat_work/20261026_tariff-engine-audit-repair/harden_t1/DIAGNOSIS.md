# DIAGNOSIS: tariff-engine-audit-repair, test half (board 78d433c)

Run read: probe attempt 3 (26 Oct 18:12), claude-opus-5 run_1, final 59.09, tests 100 (37/37 positives, 2 negatives unfired), judge 18.18.

## Phase A
`diff -rq` of the run's staged tests/, environment/, solution/, instruction.md against BUNDLE: identical (rc 0). QC kit HEAD 5574d77e. No `baselines.json` exists for this slug (searched the work tree); the run's reward-details.json is the baseline.

## 1. Every positive test: where the agent got it and why it was easy

Trajectory: 44 steps. s4 `cat api_contract.md` (whole contract, once). s12 Counter of plan values (codes seen). s13 data profile. s15/s17 parser.py, s18 core.py (4199 chars, one write), s19 report.py, s20 `_plans` maps codes. Nothing was found by a failure; every rule was transliterated in s15-s20.

| test (weight) | rule(s) | step right | what made it easy |
|---|---|---|---|
| archive_and_metadata_follow_build_config (3) | zip layout, pyproject | s34 | every key named in contract :149-155 next to build_config.json |
| delivered_visible_tests_pass (3) | visible tests | s26-28 | unittest run is the feedback loop |
| corrected_tests_name_the_changed_tests (3) | test_fixes | s26-27, s34 | failing_tests.log names the two contradicting tests |
| regression_rows_match_contract (3) | regression rows | s35-36 | recipe given step by step :181-190 |
| module_notes / summary / repair_report (1+1+1) | report shapes | s34, s37-39 | key lists stated, lint counts countable |
| shipped_exceptions_exact (3) | quantity strictness, reason order, trim | s15-17 | shipped data holds every bad quantity type (s13 profile); reason list numbered :83-92 |
| shipped_standing_lines_exact (5) | standing per month | s18 | sentence :115-117 is a formula; shipped periods sit in one month |
| shipped_energy_and_settlement_exact (5) | tiers, share, half-even, credit | s18-19 | each a formula sentence next to its use |
| fresh_* (3+5+5+5+5) | N1 re-share, N2 month split | s18 (`energy_shares` loop, `month_spans`) | :125-128 says "as often as some stays unshared": loop written verbatim; :115-117 "every month" |
| rescaled_* (4x5) | N1, N2, decimals as written | s18-19 | Decimal parse; same code path as fresh |
| relocated_* / rotated_* (6x5) | N1, N3 account position, row order | s18 (`rate_tiers(offset)`), s21-23 | :38-40 defines position across meters; file order irrelevant by construction |
| recoded_* / renamed_* (6x5) | L11 codes | s12, s20 | key-only lookup crashes KeyError on 503 shipped rows; s12 Counter points straight at the codes |
| api_* (4x5) | N2, N3 via build_invoices | s24 | same code; API named :16-17 |
| missing_source_is_named (3) | exit 2 + message order | s24 | sentence :21-24 gives order and text |
| two_runs_are_identical (3) | determinism | s19 | sort_keys render |

Pattern: every rule is a stated formula one paragraph from its use; the four levers (N1-N3, L11) were read and coded in one write. Shipped data either fires the branch (L11, exceptions) or the sentence alone carries it (N1-N3). The agent's s40 self-test built a crossing period by hand, so N2 also had its feedback.

## 2. Arithmetic

Positive total 157. 70-90 tests means losing 16-47 points. Today every hidden check rides on N1, N2, N3 or L11, and all four are coded from one reading. Rules with no hidden-only behaviour: all 7 deliverable checks (15), shipped checks (13), missing/two_runs (6), exceptions (6). No current rule is met only in hidden data in a way the agent cannot see from the sentence plus the shipped file.

The agent's own report.py shows the reflex readings the new rules target (quoted from /tmp/tt_agent/src/tariff/report.py):
- `periods[row["account"]] = {...}`: one billing row per account, last row wins.
- `meters[(row["account"], row["meter"])] = (from, to)`: one window per meter, last row wins.
- `card["plans"]` keys read: `standing_charge`, `credit_rate`, `tiers`, `codes`; any other key is ignored.
- `parse_reads` keeps read_id/account/meter/day/quantity; any other key is ignored.
- allowance not taken is dropped (`energy_shares` returns the shares only).
None of these crash on the planted data; each yields a full, well-formed, wrong document.

## 3. Planned new rules (T1 quiet branches; shipped BRANCH_FIRE checked 0 for all five)

Shipped check (python over /app/ci): billing rows 2000, accounts with >1 row 0; (account, meter) pairs with >1 row 0; meters on >1 account 0; reads with `estimated` 0; plans with keys other than standing_charge/credit_rate/codes/tiers 0.

| id | sentence (where) | reflex reading it targets | wrong document it yields |
|---|---|---|---|
| Q1 estimated reads | `meter_reads.jsonl` may carry `estimated` (JSON true/false, absent = false); a new reason `replaced_estimate`: an estimated read is set aside when an actual read for the same account, meter and day passes rules 1 to 5, wherever the two stand in the file (contract Input files + Reads list) | key ignored, first read wins; or "later replaces earlier" | actual listed as `duplicate_read` and the estimate billed (estimate first), or estimate listed as `duplicate_read` instead of `replaced_estimate` (actual first) |
| Q2 standing charge changes | a plan may carry `standing_changes`, a list of `{"from": <date>, "standing_charge": <number>}`; on each day the charge in force is that of the change with the latest `from` on or before the day, else `standing_charge`; a standing line sums charge in force / days in month over its active days (rate_card.json paragraph + Standing lines) | key ignored; or last list entry taken for the whole line; or charge at period start | standing amounts at the old rate, or at one rate for the whole period |
| Q3 several billing rows | an account may have several rows in `billing_periods.csv` with periods that never share a day; each row is one invoice, invoices sorted by account then `start`; a read belongs to the row whose period holds its day; account position counts within the row (billing_periods paragraph + Invoices + Reads 4) | `periods[account] = row`, last row wins | one invoice missing per such account, its reads listed `outside_period` |
| Q4 allowance carried | allowance no energy line of a row can take is added to the allowance of the account's next row by `start` (replaces "is not used" in Amounts) | carried allowance dropped | later row's energy amounts and subtotal too high |
| Q5 several meter rows | a meter may have several rows in `accounts.csv`, for one account or several, rows of one account and meter never sharing a day; the meter is active for an account on the days of any of that account's rows for it (accounts.csv paragraph + Active) | `meters[(account, meter)] = window` last wins, or a dict keyed by meter | reads in the other window `inactive_meter` (or `unknown_meter`), standing units and amount short |

Each gets one toy example in the contract on invented values (dates in 2031, ids like `X1`, charges not in any data file). No sentence names a wrong reading, says "note that", or says the shipped files lack the case (IN-17).

## 4. Grading plan (T3/T4)

- Planting: `_quiet(texts, seed)` appended after each corpus build, own RNG `random.Random(seed * 31 + 7)` (G8), new accounts with ids from a letter set the base corpora never use, new plans for Q2 only; every hidden corpus (all 7) gets each rule on >= 2 accounts, plus rare pairs on one account: Q1+Q3, Q2+Q3, Q3+Q5, Q1+Q5, Q2+Q4.
- Ownership (G1a): OWNED map account -> rules. The existing 33 hidden/shipped checks compare only accounts and exception rows not owned by a quiet rule (shipped has none, so shipped checks are unchanged). Five new criteria, one per rule, compare every owned invoice and every owned exception row across all 7 hidden corpora whole and exact.
- Weights: Q1 15, Q2 15, Q5 15, Q3 12, Q4 12; positive total 157 + 69 = 226. Alone costs: Q1/Q2/Q5 6.6%, Q4 5.3%, Q3 10.6% (Q4 rows need Q3). All five missed: 30.5% lost. All-but-one: <= 94.7. Existing weights unchanged.
- Planted rows avoid month crossings, tier crossings and re-share so N1-N3 do not leak cost into the new checks.
- `_assert_quiet` asserts every rule fires >= 2 times per corpus and every rare pair once; 300-seed crash sweep (G12).
- Judge unchanged; no new probes (the oracle self-check would need new witnesses; judge is not the problem this round).

DIAGNOSIS READY
