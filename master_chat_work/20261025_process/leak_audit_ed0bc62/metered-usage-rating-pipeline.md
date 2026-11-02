# Leak audit: metered-usage-rating-pipeline

- slug: `metered-usage-rating-pipeline`
- bundle: `master_chat_work/bundles/metered-usage-rating-pipeline` (newest file 25 Oct 01:23; instruction.md 24 Oct 19:03)
- trajectory: `jobs/metered-usage-rating-pipeline/trajectory/claude-opus-5/Run 1/` (run 25 Oct 06:57-07:10 host time; agent clock 01:27-01:40Z). `diff agent/instruction.txt bundle/instruction.md` = identical (SAME). The run saw the current instruction. Data and contract mtime 01:23 predate the run, so the run saw the current data too.
- probe score: tests 100 (247/247, only `negative_hardcoded_sample_answers` unfired), rubric 64.71, overall 82.35.
- latest diagnosis: `20261025_metered-usage-rating-pipeline/harden_r3/DIAGNOSIS.md` (C4, levers weak by design, round limit).
- Method: read-only. Python runs only parsed files with `open()`. Nothing was written outside OUT.

## Step 1: agent-visible surface

`environment/Dockerfile` (quoted):
```
RUN mkdir -p /app && chown 1000:1000 /app
WORKDIR /app
COPY data /app/data
```

| path | size | note |
|---|---|---|
| /app/data/rating_contract.md | 11,545 B, 228 lines | the full rule set; every lever has its own rule sentence |
| /app/data/collector_central.csv | 182,503 B | 3232 records, 3200 distinct ids, padded accounts (` AC...`) |
| /app/data/collector_east.tsv | 143,197 B | 3232 / 3200 |
| /app/data/collector_north.jsonl | 315,595 B | 3232 / 3200; units types int 3119, str 60, float 30, bool 14, null 9 |
| /app/data/collector_south.txt | 235,936 B | Latin-1, 3232 / 3200 |
| /app/data/collector_west.log | 249,551 B | offsets +01:00, +09:00, -04:00, -07:00, +05:30, +00:00; 3232 / 3200 |
| /app/data/accounts.csv | 60,473 B, 2405 accounts | `parent` column is empty on all 2405 rows |
| /app/data/plan_changes.log | 138,096 B, 2208 lines | all 2208 account ids are already canonical `AC\d+` |
| /app/data/rate_card.json, commitments.xml, products.ini, collector_controls.json | 1,692 / 409 / 414 / 364 B | |
| /app/out (empty), /opt/openhands-sdk-venv | n/a | the agent runtime, not task content |

Not visible. The Dockerfile copies only `data`. There is no `COPY tests`, `COPY solution` or `COPY . .` line. `tests/` (test_output.py, judge.toml, reward.toml, test.sh, Dockerfile) and `solution/` (solve.py, solve.sh, TRUTH.md) are not in the agent image. task.toml has `environment_mode = "separate"` under `[verifier]`, and `tests/Dockerfile` has `COPY . /tests/` in its own image. `tests/test.sh` runs `chmod -R go-rwx /tests` and `rewardkit /tests --workspace /app`. The tests therefore exist only in the verifier image, after the agent finishes. The agent never opened `/tests` or `/logs/verifier` (judge R13 scored 0; `ls -la /app/data /app/out` at step 3 only).

Shipped expected output, digests or compute scripts: none. `collector_controls.json` (full content below) holds `month` and per-collector `file` and `records` only. There is no total, hash, charge or credit figure in any shipped file.
```
{"month":"2026-09","collectors":{"central":{"file":"collector_central.csv","records":3232}, ... "west":{... "records":3232}}}
```
Record counts include duplicates (3232 lines against 3200 ids), so they expose "32 duplicates per file" and nothing else. They cannot check charge, credit, tier, true-up or billing group. The instruction says the same (instruction.md:28). Verdict on the question asked: the controls do NOT let the agent self-verify the separating cases (credit re-share, true-up, billing group).

Other surface facts:
- `task.toml` artifacts are only `/app/out/*`. `[agent] user = "1000:1000"`. Agent network allowlist is api.anthropic.com and api.z.ai only.
- `[verifier.env] OPENAI_API_KEY` is passed to the verifier container only.
- Hidden-month generator and reference engine live in `tests/test_output.py` (`HIDDEN_SEED = 58213`, lines 1-60). `_hidden_files()` is not in the agent image.

## Step 2: checklist A-J

| | Y/N | evidence |
|---|---|---|
| A names | N (mild Y) | Contract identifiers are neutral (`credit pool`, `minimum`, `billing group`). Account ids are `AC` plus digits for all ids, collector record ids are `CEN-/EAS-/NOR-/SOU-/WES-NNNNNN`. No stale_/deprecated_/_b ids in any collector file or accounts.csv. Two weak name hints: (1) the `parent` column of accounts.csv exists but is empty on all 2405 rows (agent step 11: `grep -c ',,$'` printed 0, `grep -vE ',$'` printed only the header), which signals hierarchy will appear in another month; (2) `commitments.xml` carries a `minimum` per pool although `true_up` is 0.00 in all five shipped regions. Unknown products in the data are plain names (`GPU`, `backup`), not labelled. |
| B tone | N | The contract is neutral. Only "exactly" in the sense "computed exactly in decimal arithmetic" (:157) and "every cent" (:175, :186). No CAPS, no bold warnings, no "note that", "be careful". The instruction has one "exactly" (:28) and "Do not cheat" boilerplate. |
| C rules naming the separating case | Y | See findings F1-F5. Each lever has its own sentence naming amount, method and set. |
| D shipped data showing the separating case | N for true-up and billing group; Y for north units and credit | True-up never triggers: agent output shows `true_up 0.00` and base above minimum in all five regions (region_*.json from the run: base 73491/70168/72315/70192/74224 vs minimum 55114/38088/37087/46563/45056). Billing groups never nest (parent empty everywhere). Credit second pass runs in every region (base 3x the pool), but the held-line sum (e.g. south 69,986 vs pool 24,400) never exceeds the pool, so "credit can exceed charge" is never shown. North units show non-integer shapes (str, float, bool, null) in 113 lines. |
| E visible tests / self-checks | N | No tests, validator, CI log, expected totals or script in `/app/data`. The instruction says "nothing in /app/data gives an expected count or total to check yourself against" (:28) except the record counts. The record counts check only the control-mismatch path. |
| F repo / history | N | No .git in the bundle or in the image (`git: command not found`, step 37). No TODO/FIXME comments in data. |
| G leftovers | N | `grep -rniE "trap\|decoy\|hidden\|grader\|oracle\|lever\|rubric\|harbor\|stale\|deprecated\|test\|todo\|fixme\|note"` over `environment/data` and `instruction.md`: no match. No `__pycache__`, `.DS_Store` or `~` file in the bundle (find listing). |
| H cross-file consistency | Y (mild) | The north parenthetical "(a JSON integer)" at rating_contract.md:73 plus ":80-82 In central, east, south, west units is one or more ASCII digits" says the same fact twice from two sides. The surrounding-spaces rule (:86-87) pulls the opposite way for ` 21`. See F6. `credit_unallocated ... may be negative` (:216) agrees with the second-pass rule (see F8). |
| I judge / conduct hints | Y | instruction.md:30-32 and :34 spell out the judge's plan: second-way recomputation (R1-R6, R15, R16), changed copy with moved figures (R7), foreign cwd/in/out (R10), list of files (R9), "which checks you ran on the last version" (R11/R12). See F5. |
| J what the agent used | Y | Step 15 (single 630-line draft at 01:32) is correct on every lever. Quotes and step indices are in the findings. The agent messages are empty (only tool calls), so reading is INFERRED from code except the final reply. |

## Test-to-leak map (tests/test_output.py)

| hidden test(s) | revealing visible sentence or data |
|---|---|
| accepted_lines(_hard), data_quality(_hard) | contract :73 `units (a JSON integer)` vs :80-82 digits for the other four; :86-87 spaces; "Checking records" order 1-4 incl. `units_not_integer`; duplicates rule. North non-int units are in the data. |
| rating_<region>(_hard) (5x2) | :24-29 billing group and tier counter, :145-148 change timing inclusive and file order, :153-159 tier and per-line half-even rounding; west offsets in data (:77-79 converted to UTC). Hyphen/case rule :91 stated; shipped ids canonical so the agent gets no data hint. |
| credit_<region>(_hard) (5x2) | :22-23 and :30-31 committed account = accounts.csv plan column (vs the plan in force); :165-177 two branches and re-share formula. |
| true_up_<region>(_hard) (5x2) | :179-189 shortfall, proportional first pass, 0.50 cut, re-share of every cent. Shipped data has `true_up` 0.00 everywhere, so only text reveals it. |
| region_*, segment_*, product_summary, summary (_hard) | all of the above plus output key lists :192-228 (`credit_unallocated` "may be negative" at :216). |
| mutation_tier_scale | :27-29 tier counter definition. No data hint. |
| mutation_small_commitment (pool 1.00, shortfall 1.00) | :171-177 and :181-189 re-share sentences. Instruction :31 nudges the agent to build such fixtures itself. |
| mutation_near_base_pool (pool 0.01 below base) | :165-170 "at or below" vs "exceeds". |
| missing_collector, control_mismatch | :46-51 and :112-116 give the exact stderr strings and order (specified, not hidden). |
| determinism | :53-60 "same input gives same output". |
| transform_exists | instruction :1-5. |
| negative_hardcoded_sample_answers (-5) | none; genuinely hidden (instruction announces fresh months at :28, which tells the agent not to hardcode). Did not fire. |
| judge R1-R7, R9, R10, R15, R16 | instruction.md:30-34 almost verbatim. R8 (functions <=150 lines) and R13/R14: none in the instruction; R8 is genuinely hidden and the one rubric check the agent failed together with R5, R11, R12. |

## Findings

Severity scale per brief. All 'fix' entries are proposals, none applied.

| id | cat | severity | file:line + quote | evidence it helped the agent | proposed fix (not applied) | QC rule touched + risk | touches tests/data |
|---|---|---|---|---|---|---|---|
| F1 | C | HIGH | rating_contract.md:171-177 "A line whose credit is then below 0.50 receives 0.00, and every cent of the credit pool is shared again, pool x line charge / summed charge of the lines that held 0.50 or more, rounded half-even to 0.01, across only those lines." Maps to credit_*, region_*, segment_*, mutation_small_commitment, mutation_near_base_pool. | Step 15 `allocate()` (transform.py:346-360) is a literal copy of the sentence. Step 22: hand re-share of SOU-000012 with `Fraction` on exactly this formula, matches reported 7.32. | Describe the second pass by its effect on one defined quantity ("the pool is split among the lines that held 0.50 or more") and drop the numerator, denominator and rounding from the prose, or move the exact arithmetic to a worked table only the verifier knows. | Contract must stay complete (instruction.md:9 "Every rule... is written in"); a vaguer sentence risks ambiguity findings (underspecified). Master's 00:20 condition was to name the amount and method. | N (contract only) |
| F2 | C | HIGH | rating_contract.md:181-189 "Otherwise the shortfall of the region is its minimum minus its credit base ... every cent of the shortfall is shared again, in proportion to charge, rounded half-even to 0.01, across only the lines that held 0.50 or more." Maps to true_up_*, region_*, mutation_small_commitment. | Step 15: one helper `allocate(charges, base, shortfall)` serves credit and true-up (transform.py:485-491). Step 19 fixture central pool 500 / minimum 90000 for true-up; step 26 `make_tiny.py`. Shipped true-up is 0.00, so the agent built the case from the text alone. | Same as F1; make true-up wording diverge structurally from credit so one helper does not serve both (a different rounding or ordering rule, specified once). | Changing rule semantics changes tests, solve.py, TRUTH.md; high cost. | N for wording; Y if semantics change |
| F3 | C | HIGH | rating_contract.md:24-26 "billing group (of an account): the account itself when its parent column ... is empty, and otherwise the billing group of the account named in its parent column." and :27-29 tier counter by billing group. Maps to rating_* (5x2), mutation_tier_scale, credit_*, true_up_*, all documents. | Step 15 `billing_groups()` (transform.py:223-235) walks the chain with a cycle guard. Step 11 proved the shipped parent column is empty, yet step 19 built 300 parents and a two-level chain on a copy and verified it. | Replace the recursive definition with a plainer-looking but equivalent construct (e.g. "accounts that share the same top parent") would still be transliterated; the only real fix is a lever that is not stateable in one sentence. | G10 blind-read probe rather than text edit. | N / lever redesign |
| F4 | C | HIGH | rating_contract.md:22-23 and :30-31 "committed account: an account whose value in the plan column of accounts.csv is `committed`", "credit base: ... lines of that region whose account is a committed account" next to :18-19 "plan in force". The separating case in TRUTH.md item 3 (plan in force vs accounts.csv plan). Maps to credit_*, region_*. | Step 22 selects `counted` with `acc[...]['plan']=='committed'` from accounts.csv, not the line's plan in force, and matches credit_base 70191.54. | Define the base through a quantity that does not name the file column ("accounts whose plan at the start of the month is committed" is the same leak; consider moving to the diagnosis that this lever is text-clear by design). | Same as F1. | N |
| F5 | I | MEDIUM | instruction.md:30-32 "recompute the important figures a second way, outside the program ..."; ":31 run the program on a copy of the data whose contents you have changed, and confirm that the figures which depend on that change move"; ":32 run it from a working directory other than /app/out ..."; ":34 list each file ... and say which checks you ran on the last version". Maps judge R1-R7, R9-R12, R15, R16 1:1. | Step 17 verify.py, step 19 mutated copy (commitments, parents, rate), step 28/30/32 foreign cwd. Judge scored R1-R4, R6, R7, R9, R10, R15, R16 = 28 points. The self-test on altered data is what built the true-up and parent cases (F2, F3). | Cut the three bullets to a single neutral sentence ("Report how you checked your work") so the plan is not in the prompt; rubric coverage still graded. | QC conduct rule (instruction must not tell the agent what to self-check); but dropping them may reduce R7/R10 rate. | N (instruction only; judge.toml unchanged) |
| F6 | H/D | HIGH | rating_contract.md:73 "`units` (a JSON integer)" together with :80-82 "units is one or more ASCII digits 0-9" for the other four collectors. Data: north units types int 3119 / str 60 / float 30 / bool 14 / null 9. TRUTH.md item 1 (shared reader accepting `"123"`/`" 45"`). Maps to accepted_lines(_hard), data_quality(_hard), and, through the tier counter, every rating/credit test. | Step 31 prints `type(v) is int` split and non-int samples (`' 152'`, `'103'`); transform.py:144 `isinstance(raw_units,int) and not isinstance(raw_units,bool)`; step 20 awk counts `units_not_integer 50`. The contract tells it which form is strict, the data shows the offending shapes. | Drop the parenthesis "(a JSON integer)" and put the "form" rule in one place for all five collectors; or ship north rows whose shape the contract does not name. | Contract completeness. The trap would need a rule elsewhere to stay gradable. | N/Y (contract, maybe data) |
| F7 | D/A | LOW | accounts.csv header `account_id,segment,plan,parent` with all 2405 parents empty (step 11); commitments.xml `minimum` with all five regions above minimum (region_*.json). | Step 11 saw "no parent anywhere" and still wrote recursion. INFERRED that the always-empty column and the never-binding minimum point at features other months use. | Ship a few parent rows and a binding minimum in the shipped month so shipped data exercises the feature (changes the surface the agent can debug on, a hint of a different kind). | Shipped-vs-hidden consistency checks; every `*_hard` twin and `_check_restates_shipped` assume the shipped month; test recompute. | Y (data + reference expectations) |
| F8 | B | LOW | rating_contract.md:216 "credit_unallocated (credit_pool minus credit_applied; it may be negative)". | INFERRED: tells the agent that applied credit can exceed the pool, i.e. that the second pass is a fresh share of the whole pool. Shipped data produces -0.02 / -0.10 (central, west). Not quoted by the agent. | Drop "it may be negative"; the formula stands alone. | Output-key completeness for credit_unallocated; low risk. | N |
| F9 | D | LOW | collector_controls.json `records: 3232` per collector against 3200 distinct ids per file. | INFERRED. Exposes 32 duplicates per collector; the agent's step 12 and 20 recomputed the 32 itself. No digest or figure of the separating cases. | None needed; consider shipping non-uniform counts. | none | Y (data) |
| F10 | G | LOW | `/app/out/__pycache__` created by the agent itself at step 35 and removed at step 36; `/app/AGENTS.md` written at step 38 outside `/app/out`. | Not a bundle leak; noted because the agent writes outside the declared outputs. | none | none | N |

## What is clean

- Agent image holds only `/app/data`; no tests, solution, TRUTH, generator, reference engine or oracle output. `tests/Dockerfile` is a separate verifier image; the hidden-month seed and fixtures are in test_output.py only.
- No expected output, digest, checksum, schedule or computing script is shipped. `collector_controls.json` holds only record counts, which cover the control-mismatch path and nothing else.
- No rule-naming ids or column names (`stale_`, `deprecated_`, `_b`, `DS-`) in any data file. Record ids are uniform `XXX-NNNNNN`.
- No leftovers: grep for trap/decoy/hidden/grader/oracle/lever/rubric/harbor/test/todo/note in `environment/` and `instruction.md` returned 0 lines; no .git, `__pycache__`, `.DS_Store` or backup in the bundle.
- Tone is neutral in both the contract and the instruction.
- Hyphen/case canonicalisation (TRUTH item 4), the `sum of ties` lever (TRUTH item 2: agent found 0 tie lines in step 22) and the west-offset lever are only in text for ids; plan_changes ids are all canonical in shipped data, so shipped data gives no hint.
- The judge criteria R8 (function length) and the negative R13/R14 are not echoed in the instruction; R8 was missed.

The bundle does not leak hidden tests or answers. It leaks by completeness: the contract is a precise, single-reading specification of every lever and the agent transliterated it in one pass (step 15, 01:32). The self-verification plan in the instruction (F5) sets the agent up to build its own true-up and parent fixtures.

TOP_LEAK: F1 credit re-share sentence rating_contract.md:171-177 (amount, method and set named; transliterated at step 15, re-derived by hand at step 22); F2 and F3 are the same class
COUNTS: C=0 H=5 M=1 L=4
