# DIAGNOSIS 3106c16 metered-usage-rating-pipeline, harden round 1

Probe 1 (24 Oct 20:18 IST, build b5f7557, tree 212f389aeb8d): tests 199/199 = 100, judge 21/28 = 75.0, overall 87.5.
QC kit HEAD 976c166611e555e2ba20eb8d81bed279cee1ea30 (matches expected).
Session rename: `name_session.py 3106c16` listed `ses_e919672efffeDk1K2Q7SqC1jYm`, not 3106c16; noted, not retried.
Missing inputs: WORK has no `XREF.md` (create in Phase 2) and no `baselines.json` for this slug (first probe, so no hard baseline exists).

## 1. Phase A: GENUINE

- Staged copy `.kiro-staged-tasks/metered-usage-rating-pipeline` vs BUNDLE (`diff -rq`): only the `.kiro-staged-from` marker and the harness `allowed_hosts` addition of `host.docker.internal` in task.toml. Nothing else differs.
- `Run 1/result.json`: exception_info null, reward 0.875. Agent ran 14:31:04Z to 14:47:02Z (about 16 min of 7200 s), 3.46M input / 74k output tokens.
- trial.log clean (only the docker inspect OS-validation skip notes). wrapper.log: "INTEGRITY: all 1 trial(s) completed cleanly; scores are trustworthy."
- Verifier: no Permission denied, Errno 13, Traceback or missing file. ctrf has 52 tests; the only non-pass is `negative_hardcoded_sample_answers` (a negative that did not fire, which is correct).
- Judge response parsed whole: R1-R7 1, R8 0, R9 0, R10 1, R11 fired, R12-R14 not fired.

## 2. Causes

| # | Cause | Verdict | Evidence |
|---|---|---|---|
| 1 | Run error / wrong copy | NO | Copy = bundle; clean trial; integrity line |
| 2 | Harness / rescoring change | NO | Same kit HEAD; reward-details layout as built (judge weight 0.017857, tests component) |
| 3 | QC/fix rounds made it easier | NO | WORK/LOG.md: build ends P9 19:13 IST at tree 212f389aeb8d; probe 20:18 on the same tree. No file changed since the build, and no earlier hard baseline exists |
| 4 | Levers weak by design | YES, PRIMARY | All four levers right first time in a single program write (step 16); see the table below |

Contributing factor (inside cause 4): this Opus run carried out every explicit sentence, including two rules that no shipped data exercises. LV-MU-4: 0 non-canonical ids shipped, but the agent added lower-case and hyphenated ids to its own generator at step 40. LV-MU-2: no shipped ties, but it searched for ties at step 44 (found 0 and 0) and built a tie fixture at step 45. So hiding the separating cases is not enough when the rule is explicit and prominent.

### Cause 4 per lever (the key question)

| Lever | Rule text and location | Trajectory step where it got it right | What gave it away |
|---|---|---|---|
| LV-MU-1 strict JSON integer units (north) | rating_contract.md L62-66, inside the north field block: "a JSON number written as an integer, with no fraction part and no exponent. Any other JSON value (a string, true, false, null, or a number with a fraction part or an exponent) is malformed." Plus L75-76 "In every collector except north, units is text..." | Step 10 profiling printed north unit types (int 3119, 12.5 x11, 12.0 x10, '12.0' x10, 100.0 x9, None x9, False x7, True x7, 'n/a' x4, '103' x2, ' 21', ' 333'); step 12 listed `1e2`, false, true; step 16 code `isinstance(raw_units,int) and not isinstance(raw_units,bool)` | Writing: full enumeration of malformed values at the point of use, and the carve-out sentence "except north" explains the trap (breaks W1/W3). The shipped separating rows were seen before coding, but in collateral the same rows did not save Opus. The enumeration did. Fixable: KEEP and REWRITE |
| LV-MU-2 exact decimal, half-even, per line | L149-152 "computed exactly in decimal arithmetic on the rate as written ... rounded to 0.01 with ties to the even hundredth. Totals are sums of rounded line charges." Credit L156-160 same | Step 16: `Decimal(units)*rate).quantize(CENT, ROUND_HALF_EVEN)`, rate card `parse_float=Decimal`, Fraction credit rounding; steps 44-45 tie hunt and fixture | Reflex: Python billing code goes to Decimal with HALF_EVEN, and the one-line rule names the library call. Rounding unit stated where it is used (peer pa slipped on a unit stated in a different file). Not fixable by writing alone: REPLACE |
| LV-MU-3 credit base = committed at line timestamp | Glossary L22-24 "whose account is on the committed plan at the line's timestamp"; Credit L156-158; invariant L105-106 | Step 16 L446-458: base = sum of charge where `line['plan']=='committed'`, plan already on each line for normalized.jsonl | Output design: normalized.jsonl must carry `plan` in force at the timestamp, so the intended reading is the per-line field the agent already has. The right answer was the easiest code path. REWRITE so the correct answer is no longer the per-line field |
| LV-MU-4 canonical account id mattering only in plan_changes.log | Own section "### Identifiers" L81-84, global: "compared after converting them to upper case and removing every hyphen" | Step 16 `canonical_account()` applied to every source; step 40 generator self-test of non-canonical shapes | Writing: a global rule in its own section becomes one helper applied everywhere. Peer slo slipped because the rule sat in one file's reading convention, but a canonicalisation helper is still a one-line reflex. REPLACE |

## 3. Lever table (reward-details.json + ctrf)

| Lever | Checks (families, visible w3 + _hard w5) | Points at stake alone | Earned | Status |
|---|---|---|---|---|
| LV-MU-1 | 47 tests (all row-owned families; quarantine/data_quality and everything downstream of the units set) | 189 / 199 | 189 | LEAKED |
| LV-MU-2 | 22 tests (all `_hard` + mutation_tier_scale) | 110 / 199 | 110 | LEAKED |
| LV-MU-3 | 33 tests (credit_*, region_*, segment_*, product_summary, visible + hard) | 133 / 199 | 133 | LEAKED |
| LV-MU-4 | 23 tests (all `_hard`, data_quality_hard, mutation_tier_scale) | 115 / 199 | 115 | LEAKED |
| COUPLING region credit base | inside LV-MU-3 families | - | earned | LEAKED |
| Judge | R1-R14, positive 28 | - | 21 | R8 -3 (write_outputs > 150 lines), R9 -1 (basenames, not each full /app/out path), R11 fired -3 (said the missing-input north check passed; after the last edit at step 54 only the accounts.csv case was rerun) |

HELD: none. Tests 199/199.

## 4. Trajectory autopsy (agent/trajectory.json, 57 steps; full observations in agent/openhands_sdk.txt)

- Read order: step 3 `ls /app/data /app/out`; step 4 `wc -c`; step 5 `cat rating_contract.md` WHOLE, first, at 14:31:41 (about 40 s in); step 6 controls, commitments, products.ini, rate_card; step 7 head + wc of every collector, accounts and plan_changes.
- Profiling, steps 8-14 (14:32-14:34): central unit anomalies; north type census (step 10); exponent and bool lines (step 12); accounts: 2405, odd ids 0; plan_changes: 2208 lines, odd ids [], unmatched 59 (step 13); out-of-month, unknown and duplicates per collector (step 14).
- Program written once at step 16 (14:35:08, about 4 min in); first run at step 17. No graded logic change afterwards. Later edits were robustness only: step 46-47 physical_lines for csv, step 54 a timedelta touch.
- Self-tests:
  - Steps 18-21: independent reimplementation compared on all outputs.
  - Steps 23-24: audit.
  - Step 25: quarantine precedence.
  - Steps 26-27: doubled central pool.
  - Step 29: plan change at a boundary timestamp.
  - Step 30: units 12.5 and a 740 tier shift.
  - Step 31: control mismatch.
  - Step 32: missing north and missing accounts.
  - Steps 33-41: generator of fresh months with truth.json, extended with non-canonical ids at step 40 (covers LV-MU-4).
  - Step 42: other cwd.
  - Step 43: determinism.
  - Step 44: tie search on the shipped ledger.
  - Step 45: tie fixture (covers LV-MU-2).
  - Steps 48-50: battery.sh + truthcheck.py.
  - Step 55: battery after the last edit.
  - Step 57: reply.
  These covered all four levers, but only because each rule was explicit: the agent's generator and recompute encode the agent's own reading.
- Time per phase: read and profile about 2.5 min, code about 1 min, verify about 10 min, reply 14:45:42.
- No solve.sh output, test names, TRUTH-like file or answer key was visible in the container. The only control file is collector_controls.json (record counts). That reconciles parsing volume, not graded meaning.

## 5. Agent program

Saved to `OUT/agent_program/`: transform.py (677 lines) + 13 output docs.
- Key lines: `canonical_account` L52-53; north units L167; half-even charge L434; Fraction credit rounding L85-94; credit base L446-458; write_outputs L479-660.
- Parsers: csv.reader over `\n`-split physical lines; west uses `split()` tokens; plan state by bisect over (ts, file order); Decimal rate card.

## 6. LEAK_LIBRARY rows

| Lever | How written | Step leaked | Planned fix |
|---|---|---|---|
| LV-MU-1 strict JSON int | Field block lists every malformed JSON value; separate carve-out sentence "In every collector except north" | Step 10/12 profiling, step 16 code | Bare property only, in the north field block; drop the enumeration and the carve-out; one clause in the Checking records list; keep the global trim sentence and the shipped separating rows |
| LV-MU-2 half-even exact decimal | One explicit sentence at use naming decimal and ties-to-even | Step 16 (reflex), steps 44-45 tie hunt | Drop as lever (reflex: Decimal + HALF_EVEN); keep the rule and planted ties as graded noise |
| LV-MU-3 credit base scope | Glossary definition with the instant "at the line's timestamp" equal to the per-line plan the output already exposes | Step 16 L446-458 | Base keyed to a defined status that differs from the per-line plan field |
| LV-MU-4 canonical ids in plan_changes only | Global "Identifiers" section | Step 16 helper, step 40 self-test | Drop as lever (uniform helper reflex); keep the rule as noise |

## 7. What trips Opus vs what does not (for LEVER_RULES 1b)

| Trips Opus (peer evidence) | Does not trip Opus (this probe) |
|---|---|
| Bare type property ("a JSON integer") beside a global normalising rule (trim / corrections), no enumeration, no warning (collateral, 55 pts) | Same property with the malformed values enumerated and a carve-out sentence naming the exception (LV-MU-1 here) |
| Scope inherited from a definition or earlier sentence, while loud text covers a different trap; agent's check is plausibility only (gm denominator) | Scope stated as an instant that equals a per-line field the output already requires (LV-MU-3 here) |
| Rule in one file's reading convention or a rarely joined field (slo) | Canonicalisation in a global "Identifiers" section: one helper everywhere (LV-MU-4) |
| Rounding unit stated in another file or ambiguous per stage (pa) | Rounding mode and unit in one sentence at use: Decimal HALF_EVEN reflex (LV-MU-2) |
| Stateful stream: early records change state later records read; invariants hold either way (G3 P1) | Separating cases hidden-only for an explicit rule: Opus builds its own generator and fixtures for every explicit sentence (steps 40, 44-45) |
| Definition then a later override in other vocabulary (lane, 94 pts) | Reading the whole contract first (step 5) does not protect against the left column; it does make every explicit enumeration count |

## 8. Phase 2 lever plan (for master review)

Target: Opus tests <= ~75 with judge ~75, so overall < 70. Rules stay in rating_contract.md; instruction.md states no rule; no visible trap lists. The instruction sentence "Each output document is judged whole and exactly against the contract" stays true (every new test still compares whole documents). COUPLING amplifier unchanged: region credit base (charge -> base -> credit -> region/segment/product/summary).

### LV-MU-1 KEEP + REWRITE (L5 / H1 lenient coercion)

- Rule file: rating_contract.md.
- North field block becomes a bare property: "`units`: a JSON integer".
- Delete the malformed-value enumeration (L63-66) and the carve-out sentence at L75 ("In every collector except north").
- Units text rule: "`units`, in the text collectors: one or more ASCII digits after trimming".
- Checking records item 4 becomes one clause inside the existing reason list ("units_not_integer: units is not a whole number as its collector writes it").
- Keep the global trim sentence L51-52 as the normalising neighbour (collateral pattern).
- Shipped: keep the separating rows ('103', ' 21', '12.0', 12.0, 100.0, true, false, null, 1e2). W5 allows these for L5 only.
- Hidden: the same shapes at about 3% of north rows, plus quoted integers that create tier crossings.
- Predicted alone 95.0% (measured cost table); one-fact-wrong 73.9%.
- Why the agent's method misses it: profiling at step 10 shows '103' as a quoted number. Without an enumeration, "a JSON integer" next to "surrounding spaces are removed from every text field" invites `int(str(x).strip())`. The agent's recompute and generator would encode the same coercion.
- Risk: still explicit enough that Opus may pass. Estimated slip about 35%.

### LV-MU-2 REPLACE (reflex; kept as graded noise, not counted)

The rule and the planted hidden ties stay, so tests keep rewarding exact half-even. The lever is not counted toward >= 3.

### LV-MU-3 REWRITE (L6 / H3 scope by definition, COUPLING carrier)

- New glossary term: "committed account: an account whose plan in accounts.csv is committed."
- Credit base: "the sum of the charges of the accepted lines of that region whose account is a committed account."
- The Credit section uses the term without naming an instant. The Plans section keeps its loud timing rule (later line wins; same timestamp uses the new value) for the `plan` and `segment` written to normalized.jsonl and the segment split. That is the different trap the loud text points at.
- Shipped (W5 non-separating): plan= changes only for accounts with no accepted line after the change, so both readings give the same base on shipped data.
- Hidden: about 10% of accounts switch plan mid-month in both directions with lines after the switch, and pools are k/8 of the correct base so the wrong base plants half-cent credit differences in every region.
- L105-106 invariant "Every credit pool is less than half of its region's credit base": keep only if the generator guarantees it under both readings; otherwise delete it (it is a self-check aid).
- Predicted alone about 66.8% (same 33 tests as built); one-fact-wrong about 34.7%.
- Why the agent's method misses it: it already holds `line['plan']` (in force at the timestamp) for normalized.jsonl and filtered on it at L446-458. Under the new definition that is the wrong field, and its recompute script reused the same per-line plan.
- Estimated slip about 45%.

### LV-MU-4 REPLACE (reflex; kept as noise)

The rule stays; hidden non-canonical ids stay as graded noise.

### NEW LV-MU-5 billing-group tier counter (L6 + H6, stateful)

- Rule file: rating_contract.md, accounts.csv block and glossary.
- accounts.csv gains a `parent` column. Glossary entries:
  - "billing group (of an account): its parent in accounts.csv, or the account itself when parent is empty".
  - "tier counter (of a line): the total units of all earlier accepted lines, in all collectors, of the same product code whose accounts are in the line's billing group".
- Rating L143-147 uses "tier counter" instead of restating "same account and product". The loud wording stays on "in all collectors" (the different trap the agent already handles).
- Shipped: parent empty for every account (W5 non-separating).
- Hidden: about 25% of accounts in groups of 2-4 with interleaved lines that cross tier boundaries.
- Interactions: the parent id is canonicalised (LV-MU-4 noise); the counter uses the accepted set only (LV-MU-1 couples here, because a coerced row adds units to the group counter); the tier changes the charge, which changes the credit base and credit (COUPLING).
- Predicted alone about 55-60% (all `_hard` charge-bearing families + mutation_tier_scale, like LV-MU-2/4 hidden-only); one-fact-wrong about 20-25% (only lines after a group crossing move; downstream totals move).
- Why the agent's method misses it: its counter is keyed (account, product) by habit, and on shipped data the group equals the account. Its generator (steps 33-41) would emit an empty parent unless it reads the glossary term into the generator.
- Estimated slip about 40%.
- Separating cases reach about 27% of test points alone, so G10 >= 25% holds.

### Backup candidates (if the master rejects LV-MU-5)

1. Included units for committed accounts drawn in rating order across collectors (L3 / H6): early lines consume the allowance before later ones.
2. Credit rounding unit per account then summed per region (L7, unit stated once in the glossary).

West quoted values and other encoding variants are noise only (LEVER_RULES).

### Counts and prediction

- Independent levers: LV-MU-1, LV-MU-3, LV-MU-5 (3), plus the COUPLING amplifier.
- Hidden share stays >= 60% (seed 58213).
- With per-lever slip estimates 35/45/40%, P(at least one slip) is about 0.79. One slip of LV-MU-3 or LV-MU-5 alone leaves tests at about 33-45%, so overall is about 55-60 with judge 75. If all three hold, overall stays about 87.

### Judge

- Keep R1-R14 as built.
- Add one recompute conduct criterion per new lever family, w3:
  - R15: billing-group counter recompute, shown by solve.sh `check tier_counter ok`.
  - R16: committed-account credit base recompute, shown by `check credit_base ok`.
- R8 stays one J4 code-quality judgement.

### Reflex gate caveat

OUT/agent_program will fail the new LV-MU-5 and LV-MU-3 hidden tests mechanically. The `parent` column is new data and the base definition changed. So its score versus the new tests (expected <= 0.20 only if LV-MU-1 also separates it) partly measures new behaviour, not reflex resistance.

### Files to change in Phase 2

- environment/data: rating_contract.md, accounts.csv, regenerated collectors and plan_changes.log.
- WORK: gen_core.py, ref_core.py, datagen.py.
- tests/test_output.py (re-embed _SHIPPED_DATA), judge.toml, reward.toml.
- solution: solve.py, solve.sh, TRUTH.md (sha256 by script, last).
- WORK docs: DESIGN.md ("Harden round 1"), LEVERS.md, COST_TABLE.md, RULE_COVERAGE.md, QC_DEFENCE.md, JUDGE_MAP.md, XREF.md (new).

Waiting for Ayush "go" before Phase 2.
