# Leak audit: tariff-engine-audit-repair (board ed0bc62)

- Slug: `tariff-engine-audit-repair` (repo-repair task, Harbor 0.24, verifier `environment_mode = "separate"`)
- Bundle: `master_chat_work/bundles/tariff-engine-audit-repair`. Newest file is `solution/TRUTH.md` at 25 Oct 01:34. `tests/test_output.py` and `tests/reward.toml` are 25 Oct 01:23. Everything under `environment/ci` is 24 Oct 19:50 to 25 Oct 00:54, and `api_contract.md` is 25 Oct 00:49.
- Trajectory: `jobs/tariff-engine-audit-repair/trajectory/claude-opus-5/Run 1/`, 25 Oct 06:42-06:56. It is newer than every bundle file. `agent/instruction.txt` is byte-identical to `instruction.md` (`diff` printed SAME_INSTR). Step 4 `cat api_contract.md` returns 10514 characters and contains the sentence "shared again" (the 00:20 N1 wording). The run therefore saw the current bundle.
- Probe score: tests 100 (pytest 31 of 33 criteria, 127/127 weighted points), judge 3.33 (R8 +3, R13 +3, R9 -5), overall 51.66. Source: `report.json` and `judge_response.txt`.
- Latest diagnosis: `20261025_tariff-engine-audit-repair/harden_r2/DIAGNOSIS.md`. It already blames explicit method sentences (section 2, cause 4).
- Scratch: `_scratch/tariff-engine-audit-repair/` holds copies only (`test_output_copy.py`, `ci/`, `an1.py` to `an4.py`). The oracle `_Ledger` was cut out of the test file and exec'd there with `python3 -B`, so nothing was imported from the bundle.

## Step 1: agent-visible surface

`environment/Dockerfile` (the full file, 891 bytes):

```
FROM python:3.12-slim@sha256:...
RUN groupadd -g 1000 agent && useradd -u 1000 ... agent
ENV HOME=/home/agent
RUN apt-get ... xxd file curl bash nodejs npm procps ca-certificates tmux ...
RUN python3.12 -m venv /opt/openhands-sdk-venv && ...pip install openhands-sdk==1.55.1 ...
RUN mkdir -p /app && chown 1000:1000 /app
WORKDIR /app
COPY --chown=1000:1000 repo /app/repo
COPY ci /app/ci
```

`task.toml` sets `[agent] user = "1000:1000"`. The `ci` copy has no chown, so it is root-owned and readable but not writable by the agent.

| path in container | size | note |
|---|---|---|
| `/app/ci/api_contract.md` | 10515 B | the full spec; every rule is written out |
| `/app/ci/failing_tests.log` | 757515 B | 2000 `test_dispute_NNNN` lines, 1405 FAIL, 79 ERROR, 516 ok; traces show `'actual' != 'customer_claim'` |
| `/app/ci/regression_cases.jsonl` | 1560870 B | 2000 cases with `customer_claim` and `disputed_total` |
| `/app/ci/meter_reads.jsonl` | 1061380 B | shipped reads (quantity types: int 10372, str 143, float 79, bool 55, None 37) |
| `/app/ci/accounts.csv` | 87731 B | 2000 accounts |
| `/app/ci/billing_periods.csv` | 92484 B | 2000 periods, all within one calendar month |
| `/app/ci/lint_report.json` | 61250 B | 380 pylint-style issues, noise |
| `/app/ci/rate_card.json` | 1868 B | 6 plans |
| `/app/ci/package_manifest.json` | 194 B | version 2.4.1 |
| `/app/ci/build_config.json` | 288 B | archive settings |
| `/app/repo/README.md` | 639 B | describes the drifted behaviour ("30-day month", "metered consumption") |
| `/app/repo/pyproject.toml` | 202 B | wrong version, `requires-python`, `dependencies = ["requests"]` |
| `/app/repo/src/tariff/{__init__,__main__,core,parser,report}.py` | 175 / 294 / 1564 / 2471 / 3325 B | the buggy code; no TODO, FIXME or comment about a bug |
| `/app/repo/tests/test_visible.py` | 5670 B | 13 tests, two assert drifted values; `allowance` is always "0.00" |
| `instruction.md` (prompt) | 1680 B | |

NOT visible to the agent, with proof:

- `tests/` and `solution/` are never COPY'd: the environment Dockerfile above has only `repo` and `ci`. No ENV, ADD or RUN fetches them.
- `tests/Dockerfile` is a separate verifier image (`FROM python:3.12-slim`, `COPY . /tests/`). `task.toml` has `environment_mode = "separate"`, and `tests/test.sh` runs `chmod -R go-rwx /tests` and then `rewardkit /tests --workspace /app`. Tests therefore arrive after the agent finishes and are not reachable at agent time.
- Trajectory R11 (opens `/tests` or `/logs/verifier`) scored 0. `find /app -type f` at step 3 listed only `/app/ci/*` and `/app/repo/*`.
- Expected output, digest or computing script in a shipped file: no digest and no script. `regression_cases.jsonl` carries a customer total per case, which is an unchecked answer key for 64% of its inputs (see F05). No expected output exists for the shipped files themselves.
- No `.git`, `__pycache__`, `.DS_Store`, `~` or `.bak` anywhere under `environment/` (`find -name ".*" -o -name __pycache__ ...` printed nothing). `ls -a` of the bundle root shows only the five expected entries.

## Step 2: checklist A-J

| id | Y/N | evidence |
|---|---|---|
| A names | N | Ids are neutral: `A0001`/`M00001` (shipped), `C0001`/`N00010` (regression), plans `HOME-A`, `SME-1`, `IND-2`. Reasons are the contract's five. No `stale_`, `deprecated_`, `_b` or decoy-like ids. Test name `test_commitment_credit_base` names the credit-base topic, which is the task-declared drift. |
| B tone | N (weak) | Nothing in CAPS and no "note that" or "be careful". `api_contract.md:3-5` and `instruction.md:3` ("the contract wins") are arbiter statements. `instruction.md:7` says "judged whole and exactly", which is mildly exact. See F06. |
| C rules naming the separating case | Y | `api_contract.md:125-128` (N1: amount, method, repetition), `:46-48`, `:115-119` + `:51` (N2), `:38-40` + `:107-113` (N3), `:63` + `:85-86` (strict integer gate), `:132-136` (credit base), `:49-50` + `:128-129` (half to even). Details in the map below and in F01-F04. |
| D shipped data showing the separating case | N for N1/N2/N3, Y for the gates | Scratch variant runs. On the 2000 shipped accounts, N3 per-meter positions differ in 0, N1 one-pass in 0, and N2 30-day months in 1287 (that last one is the visible drift, not a lever). 0/2000 shipped periods cross a month. On 2000 regression cases, N3 per-meter, N1 one-pass and N1 two-pass all differ in 0. Regression data does give worked examples of the gates and of first-pass allowance sharing (F05, F11). |
| E visible tests, CI logs, validators | Y | `failing_tests.log` + `regression_cases.jsonl` act as a partial answer key (F05). `test_visible.py` has no lever test: `allowance` is always `"0.00"`, one meter, no month-crossing period. It exercises only the gates (`test_bool_quantity_is_rejected`, `test_decimal_quantity_is_rejected`) and the two drifted assertions. |
| F repo/history | N | No `.git`. `grep -rniE "TODO|FIXME|XXX|bug|trap|hidden..."` over `environment/repo` found nothing. Docstrings and README describe the drifted behaviour (core.py:31 "30-day month", core.py:39-40 "metered consumption charge", parser.py:19-23 "Meter gateways sometimes send the reading as text"). They mislead rather than point at a fix. `lint_report.json`: line numbers are spread over every line (core errors at 3, 5, 7, 8, ... 47 across 47 lines), codes are unrelated (E0602, E1136), and the module line maxima equal the file lengths. It points at no bug. |
| G leftovers | N | `grep -rniE "harbor\|QC\|lever\|rubric\|trap\|decoy\|hidden\|grader\|oracle\|verifier\|cheat"` over `environment/repo`, `instruction.md`, `api_contract.md`, `build_config.json`, `package_manifest.json` and `rate_card.json` found only "drift/drifted" (`instruction.md:1`) and "Do not cheat" (`:17`). The word "hidden" is absent from the log, the cases and the lint report. |
| H cross-file consistency | Y | Each lever is stated twice in the contract: N1 at `:46-48` and `:125-128`, N2 at `:51` and `:115-119`, N3 at `:38-40` and `:107-110`. README ("30-day month", "metered consumption reaches their commitment") against contract is drift by design. Contract `:71` allows periods of "1 to 62 days" while every shipped period is 8-31 days (F07). |
| I judge/conduct hints | N | `judge.toml` (R1-R13) is not echoed in the instruction. The instruction asks only for the final list of changed functions (R8). It tells the agent no self-check. R4, R5, R12 and R13 describe the probes the agent should have made, but none of it is visible. |
| J what the agent used | Y | See "Trajectory evidence" below. |

### Trajectory evidence (J)

- Step 4 reads the whole contract in one `cat`.
- Step 13 counts the quantity value types in `meter_reads.jsonl` and `regression_cases.jsonl`. It finds 28 negatives and floats 14.5, 2.5 and 40.0 in the regression reads. Step 16 writes `_quantity` as a strict JSON integer.
- Step 18 is a single `cat > core.py` carrying all three levers. N3 is `rate_tiers(quantity, tiers, offset)`, whose docstring says "the number of the account's units that lie before this meter, so the split follows account positions rather than meter positions". N2 is `month_spans` with `calendar.monthrange`. N1 is `share_allowance` ("whatever stays unshared is offered again to the lines that are not yet at zero, until none stays unshared or no such line is left"), a loop `while left > 0 and takers: part = left/len(takers); take = min(part, room)`. Half-to-even is `round_money`. The graded logic is not rewritten later (steps 19 and 47 are cosmetic).
- Steps 22-24 replay the 2000 cases against `customer_claim`. Step 24 prints the deltas: `-1.5 75 / -0.4 91 / 0.25 92 / 0.9 93`.
- Step 31 tags cases `onetier/share2`. Step 32 looks for allowance above a line and finds 3 cases (`dispute_0575`, `0940`, `1656`).
- Step 30 prints a regression case with two meters and an allowance whose claim reconciles, as a worked example.
- Step 39-40 self-probes: A is a 2026-01-20..2026-03-02 period (expects units 42, amount 27.00), B is 150+100 units across two meters against the 200 boundary, C is a 10.00 allowance over two meters. Each probe mirrors a contract sentence one for one.
- Step 49 (final reply): "1286/2000 dispute replays match... The 714 non-matches split exactly into 363 whose claim equals the old drifted total and 351 whose claim is offset ... by one of only four fixed values (-1.50, -0.40, +0.25, +0.90) — i.e. deliberately wrong claims, not engine error."
- The agent's messages carry no free text (every `message` field in steps 3-48 is empty), so the agent's own wording of the trap exists only as code docstrings and the final reply.

## Test-to-leak map (tests/test_output.py, 127 weighted points)

| hidden check (weight) | visible sentence or data that reveals it |
|---|---|
| archive_and_metadata_follow_build_config (3), delivered_visible_tests_pass (3) | `api_contract.md:12-15, :141-145, :149-155` and `build_config.json`, fully stated. Nothing hidden. |
| corrected_tests_name_the_changed_tests (3) | `instruction.md:1` ("some of the repository's own unit tests ... assert the drifted behaviour"), `api_contract.md:141-145`, and discoverable by running `unittest` against the repaired code. The two test names are not given. |
| regression_rows_match_contract (3) | `api_contract.md:181-190` spells the whole procedure. `regression_cases.jsonl` also holds the claims, which equal the oracle for 1286/2000 (F05). |
| module_notes_follow_contract, summary_lists_inputs_and_artifacts, repair_report_and_failing_cases (1 each) | `api_contract.md:157-194`, fully stated. |
| missing_source_is_named (3) | `api_contract.md:19-24` states stderr text, order and exit code 2. Nothing hidden. |
| two_runs_are_identical (3) | `api_contract.md:173-174` (`deterministic`). |
| shipped_exceptions_exact (3), fresh_exceptions_exact (3) | `api_contract.md:83-96`, the order rule and the `quantity` field rule at `:63`. Shipped data shows 143 padded strings, 79 floats, 55 bools, 37 nulls and 28 negative ints (step 13). Gate LV-TR-4 (F04). |
| shipped_standing_lines_exact (5), shipped_energy_and_settlement_exact (5) | `:115-119` (months), `:107-113` (tiers), `:132-136` (credit), `:49-50` (half to even). The shipped data separates only the 30-day proration (1287/2000 accounts). Levers N1/N2/N3 do not move any shipped line (0/2000, 0/2000 and 0/2000 crossing). The visible test `test_partial_period_standing_charge` asserts 14 days -> 8.68 against Feb 15-28. |
| fresh_{energy 5, standing 5, subtotals 5, credits_and_totals 5} (levers N1 + N2), rescaled_* (4 x 5, same corpus plus a rate change and shuffled rows) | N1: `:46-48`, `:125-128`. N2: `:51`, `:115-119`, `:41-43`. Both named with amount, method and repetition. |
| relocated_{lines, subtotals, credits} (3 x 5, N1 + N3), rotated_* (3 x 5, same + rotated rows) | N1 as above. N3: `:38-40`, `:107-113`. |
| api_{energy, standing, subtotals, credits} (4 x 5, N2 + N3, via `build_invoices`) | N2 and N3 as above. |
| negative_hardcoded_sample_answers (-5), negative_visible_test_removed (-3) | `api_contract.md:141-143` states the no-delete rule. The reused ids A0003, A0010 and A0042 are not visible as such. |
| judge R4 (month-crossing standing), R12 (third allowance share), R13 (tier crossing account) | R4 and R13 were the probes the agent made (steps 29, 39-40). R12 was not probed; the agent tested up to the second share. The contract sentence names the repetition, but the agent did not build a three-share case. |

Genuinely hidden: only the ids of the hidden corpora and the three-share requirement (the hidden N1 accounts are built so they share at least three times, `_assert_bounds`). Every behaviour tested is stated in the contract.

## Findings

| id | cat | severity | file:line + quote | evidence it helped (trajectory) | proposed fix (NOT applied) | QC rule touched + risk | touches tests/data |
|---|---|---|---|---|---|---|---|
| F01 | C | HIGH | `environment/ci/api_contract.md:125-128` "Allowance left unshared is shared again in equal parts, never more than a line's remaining exact value, among the energy lines not yet at zero, as often as some stays unshared and such a line remains"; `:46-48` "Each energy line of the account first takes an equal part of the allowance, but never more than its exact value; a part a line cannot take stays unshared." Names the amount (remaining exact value), the method (equal parts among lines not at zero) and the repetition. | Step 18: `share_allowance` docstring and loop paraphrase these sentences. Step 39-40 probe C and step 49 "multi-round allowance re-sharing with unusable surplus". Gets all N1-owned checks (about 60 of 127 points). | Replace the use-site sentence with a bare recursive or "by the same rule" form and drop "as often as ..."; or leave N1 as an explicit gate row and move the lever to a quantity the agent cannot read off one sentence. | Contract completeness (IN-16: bare "by the same rule" was called ambiguous); risk of a QC fail for ambiguity, and DIAGNOSIS section 9 says the recursive form leaked on caldermoor. | Y (contract text only; tests and data unchanged) |
| F02 | C | HIGH | `api_contract.md:115-117` "The exact value of a meter's standing line is the sum, over every month holding one of its active days, of `standing_charge` x its active days in that month / days in that month"; `:51` "Month: a calendar month, from its first to its last day." | Step 18: `month_spans` with `calendar.monthrange`. Step 29/39 probe A: 2026-01-20..2026-03-02, "expect units 42, 27.00". Gets about 45 points. | Define "month" in the glossary only and let the Standing line say "prorated" without the sum; or add a competing per-line field. | Spec clarity: removing the sum may make it ambiguous. Risk is high. | Y (contract text only) |
| F03 | C | HIGH | `api_contract.md:38-40` "Account position: the place of a unit among the account's accepted units, counted from 1 over its meters in ascending `meter` order, the period quantity of each meter following those of the meters before it."; `:107-110` "Tier 1 covers the units whose account position is from 1 up to and including its `up_to`". | Step 18: `rate_tiers(offset)` docstring "so the split follows account positions rather than meter positions". Judge R13 (+3): the agent probed 150+100 against 200. Gets about 45 points. | Do not describe the carry-over in the definition; leave "position" as "of the account's units" and let the tier text imply it. | Spec clarity: ambiguity risk (which meter order?). | Y (contract text only) |
| F04 | C | HIGH | `api_contract.md:63` "`quantity`: a JSON integer, 0 or more."; `:85-86` "`malformed_quantity`: its `quantity` is not what the `quantity` field rule allows"; visible `test_visible.py:63-71` (`test_bool_quantity_is_rejected`, `test_decimal_quantity_is_rejected`). Gate LV-TR-4: the field rule names the exact type. | Step 13: type census of both data files (`str 143, float 79, bool 55`). Step 16: `_quantity` rewritten to accept only JSON integers (rejects bool, strings, floats). Applies to every exception and line check. | Keep the field rule but drop one of the two visible tests, or loosen the wording to the same sense without the type name. | LV-TR gate; the repo's own tests intentionally pin it. Risk: a gate cannot be hidden without an ambiguity. | Y (visible test file or contract) |
| F05 | E/D | MEDIUM | `environment/ci/regression_cases.jsonl` (`customer_claim`, 2000 rows) + `failing_tests.log` (`AssertionError: 'actual' != 'claim'`, 1405 times). Scratch run of the oracle `_Ledger` over all 2000 cases: claim == oracle total in 1286 (64%); the log's expected value equals the oracle in 1074 of the 1405 FAIL traces. The 714 wrong claims are mechanically separable: 363 equal the old buggy `disputed_total`, and 351 differ from the oracle by exactly one of four constants (-1.50 / -0.40 / +0.25 / +0.90). | Steps 22-24 and 49: the agent measured the 1286 matches, split the rest, and called the offsets "deliberately wrong claims". The set validates the gates (floats such as 14.5 and 2.5, the credit base, half to even, inclusive boundaries) without a hidden test. It cannot validate N1/N2/N3: oracle variants (N3 per meter, N1 one pass, N1 two passes) differ in 0 of 2000 cases, no case crosses a month, and `passes` never exceeds 1. | Add claims that are plausible but wrong in other ways, or blur the two decoy patterns; or accept it as the designed task surface. | Dataset realism; risk: `regression_cases.jsonl` is part of `regression_rows_match_contract`, so any change needs an oracle re-run. | Y (shipped data) |
| F06 | C/B | MEDIUM | `instruction.md:7` "Each invoice and each exception list is judged whole and exactly against the contract, on the shipped files and on fresh corpora of other periods and sizes." Announces generalisation to other period shapes (the N2 axis and a larger corpus), and "exactly" signals precision. | INFERRED: no agent text quotes it. Probes at 29 and 39 use a 3-month span, but `:115-117` already motivates that. | Drop "of other periods and sizes". | Instruction fairness (verifier coverage statement). Risk: low. | N |
| F07 | D/H | MEDIUM | `api_contract.md:71` "the period is 1 to 62 days long" against shipped `billing_periods.csv`: lengths 8-31 days, 0/2000 cross a month; regression periods are also within one month. A 62-day cap shows that month-crossing periods exist; the shipped data shows none, which can only mean the lever lives in other data. | INFERRED: agent probes a 42-day span at step 29/39, but the contract at `:115-119` would trigger that anyway. | Cut "62" to the longest shipped period only if the hidden corpora allow it; else leave as is. | Contract consistency (the field range must cover hidden data). Risk: changes tests/data. | Y |
| F08 | H | MEDIUM | Redundancy: N1 at `:46-48` and `:125-128`, N2 at `:51` and `:115-119`, N3 at `:38-40` and `:107-110`, the credit rule once at `:132-136`. The credit base wording ("sum of its accepted, rated, prorated lines in the billing period, before rounding of the total", `:132-133`) names the drift fixed in step 26. | Step 4 reads all; step 18 has all three in one write. | State each rule once, at the use site. | Contract style; risk: low. | Y (contract) |
| F09 | E | LOW | `failing_tests.log` lines "tests/test_regressions.py, line 44, in replay ... self.assertEqual(invoice['total'], case['customer_claim'])" and "TimeoutError: replay exceeded 5.0 s" (79 ERRORs). The log shows the replay harness shape (`customer_claim` is the expected value) and that the old code was slow. Neither is a lever. | Step 11 reads the log; step 22 rebuilt the harness (`run_case` mirrors the contract text at `:184-190`). | None needed. | | N |
| F10 | B/F | LOW | `instruction.md:1` "some of the repository's own unit tests ... pass only because they assert the drifted behaviour"; README and docstrings echo the drift (`README.md:11-14` "prorated over a 30-day month", `core.py:31`, `core.py:39-40` "metered consumption charge"). | Steps 25-26 edited exactly the two drifted tests after running `unittest`. The task asks for this, so it is the designed discovery path. | None needed. | | N |
| F11 | D | LOW | `regression_cases.jsonl`: 980 cases with `allowance` > 0, 675 with two meters; 3 cases where an allowance exceeds a line (`dispute_0575`, `0940`, `1656`). Worked examples for the first pass of N1. No case needs a second pass or crosses a tier across meters. | Steps 29, 30 and 32 printed such cases. Not a separating case. | None needed. | | N |

## What is clean

- Tests and solution are not in the environment image. The tests live in a separate verifier image, mounted after the agent ends, with `chmod -R go-rwx /tests`. Trajectory R11 = 0.
- No `.git`, `__pycache__`, `.DS_Store`, backup or `~` files in `environment/`. No TODO/FIXME/XXX or author notes in `repo/`. No harness words (Harbor, QC, lever, rubric, hidden, oracle, grader) anywhere visible except "drift" and "cheat" in the instruction.
- Ids and enum values are neutral, with no `stale_` or decoy-like prefixes.
- `lint_report.json` is noise: lines are spread over every line of each module and codes do not match the code.
- `test_visible.py` never exercises N1, N2 or N3 (always `allowance = "0.00"`, one meter, one-month periods).
- Shipped data does not separate N1 (0/2000), N3 (0/2000) or N2 (0/2000 month-crossing periods). Regression cases do not either (0/2000 for N1 one and two passes and for N3). The contract is the only place the levers appear.
- No digest, checksum or script computing expected outputs ships. The judge criteria (R1-R13) are not echoed in `instruction.md`; the only self-check demand is the final list of changed functions.

TOP_LEAK: F01 api_contract.md:125-128 + :46-48 spell N1 (amount, equal-part method, repetition); the agent's share_allowance loop (step 18) is that sentence, as are F02/F03 for N2/N3 (F02, F03 and F04 are the same class)
COUNTS: C=0 H=4 M=4 L=3
