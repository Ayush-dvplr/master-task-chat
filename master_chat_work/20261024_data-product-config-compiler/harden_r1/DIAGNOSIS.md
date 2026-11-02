# DIAGNOSIS: data-product-config-compiler, harden round 1 (board e317de1)

Probe 1 (24 Oct, harness attempt 1, tree b8acb6bb8bd7): tests 125/125 = 100, judge 25/28 = 89.29, overall 94.65.

## 1. Phase A verdict: GENUINE

- `trajectory/claude-opus-5/Run 1/result.json`: `exception_info: None`, verifier reward 0.9464, agent ran 15:38:14-15:47:17Z (57 steps, $3.00).
- The staged copy `.kiro-staged-tasks/data-product-config-compiler` differs from BUNDLE only in `.kiro-staged-from` and in task.toml:25 and :32, where `allowed_hosts` gains `"host.docker.internal"` (harness staging).
- test-stdout.txt has 0 hits for permission denied, Errno 13, Traceback, timeout and error, and ends `reward: 0.9464`. ctrf has 34 tests: the 33 positive tests passed, and the only non-pass is `negative_hardcoded_sample_answers` (-5), which means that negative did not fire.
- In judge_response.txt, R1-R10 scored 1, R12 (grader read) scored 0 ("does not open or list any filesystem-root /tests path or any /logs/verifier path"), and R11 (the honesty negative) fired at -3: "claims the missing-input, invalid-date, catalog-mismatch, read-only-folder, and several edge-case checks passed, but those specific checks were not rerun after the final edits".
- The pass_summary.json is at `jobs/data-product-config-compiler/trajectory/claude-opus-5/pass_summary.json`, not at the job root.

## 2. Root cause

| Cause | Verdict | Evidence |
|---|---|---|
| 1 run error / wrong copy | NO | Phase A above. The bundle equals the test_depth copy (`diff -rq` gave no output) and the staged copy, apart from the staging lines. |
| 2 harness / rescoring change | NO | reward-details.json is a group weighted sum matching reward.toml: 0.004 per test point (0.5/125) and 0.017857 per judge point (0.5/28). |
| 3 QC / fix rounds made it easier | NO | This is the first probe and no baselines.json exists. The LOG has no QC or fix round after build 13a9939, and the P8.1 fixes (`_grant_read`, negative rename) came before the probe. |
| 4 levers weak by design | **YES (PRIMARY)** | Every lever is stated with its separating case. Opus read the contract once (step 6), probed the data for each named case (steps 15-20) and wrote the program in 1 minute. Fuzz shows 0% differing for every lever (section 4). |

**PRIMARY CAUSE: 4.** Two things contributed. The judge was nearly saturated: R1-R6 all passed from one independent verify.py run on shipped data (step 35). Also, no hidden case lies outside a stated sentence.

### Cause 4 per lever

| Lever | Rule text, location | Step it got it right | What gave it away | Fuzz differing (r1, 325 corpora) |
|---|---|---|---|---|
| LV-CC-1 H3 active owner + RETIRE owner | config_contract.md:38-40 glossary "Active owner on date D ... and who has no `RETIRE owner=<owner>` event ... dated on or before D"; :63-65 "Two kinds of event count" | read at 6; probe 15 (`grep RETIRE owner=` vs `product=` counts) and 19 (owners multi-match on D, empty active_to); code at agent resolve.py:4-34, loaders.py:128-148 | The glossary names both conditions in one sentence, and :63-65 names both RETIRE kinds. The data has both kinds, so a single grep separates them. | 0.0% |
| LV-CC-2 H1 strict JSON type | :92-93 "keeps its JSON type and is never converted"; :104-106 enumerates "a JSON string for an integer or boolean key, whatever text it holds; a JSON boolean for an integer key; a number with a fraction or exponent; and null for a key that is not optional" (LV-ENUM leak) | 6; probe 20 (`Counter((key, type(value)))` over product_overrides.jsonl); agent resolve.py:37-70 rejects bool-as-int, str, float, null | The list of malformed values at :104-106 is a ready-made test list. | 0.0% |
| LV-CC-4 H4 canonical ids in the log | :28-29 "Product ids are compared after converting them to upper case and removing every hyphen" (global) | 6; probe 15-16 (lowercase or hyphenated `product=` ids in deprecation.log); agent loaders.py:36-38, 141 | A global rule with no carve-out, so `canon()` gets applied at every load. | 0.0% |
| COUPLING largest remainder | :129-135 | 6; written at step 29 (quota.py) | It is a worked formula (floor, descending remainder, id ties). | 0.0% |

## 3. Lever table (probe 1, reward-details + ctrf)

| Check / criterion | Points | Earned | Levers | Result |
|---|---|---|---|---|
| 11 families visible (catalog_status, team, settings_int, settings_other, config_quota, dev_deploy, dev_quota, prod_deploy, prod_quota, rejected_overrides, summary) | 11 x 3 = 33 | 33 | CC-2 (graded work) | LEAKED |
| same 11 families `_hard` (hidden corpus 2027-2029, 420-520 products) | 11 x 5 = 55 | 55 | CC-1, CC-2, CC-4, COUPLING | LEAKED |
| date_shift / quota_rescale / shuffled_relocated | 3 x 5 = 15 | 15 | CC-1, CC-4 / COUPLING / CC-2 | LEAKED |
| readonly_inputs | 3 | 3 | all | LEAKED |
| report_run, missing_input, invalid_date, catalog_mismatch, determinism, document_format | 6 x 3 = 18 | 18 | none | n/a |
| tool_zip_layout | 1 | 1 | none | n/a |
| negative_hardcoded_sample_answers | -5 | 0 (did not fire) | none | n/a |
| Judge R1-R10 | 28 | 28 | conduct | saturated |
| R11 honesty negative | -3 | -3 | none | fired |
| R12 grader read | -5 | 0 | none | did not fire |

Every lever HELD 0 points. Test levers lost 0 of 125.

## 4. Fuzz rerun on the probe agent program (OUT/fuzz/)

- The kit was copied to OUT/fuzz/. In run_case.sh, W became `/tmp/fz-e317de1-20261024T232603-85ad` and the image `fz-e317de1-cf-verifier`, built from BUNDLE/tests. The cases came from mk_cf_cases.py with seed 31717. The agent zip has sha256 670efe51...; the oracle zip efbe4dae...
- The run used `fz_cf.py`, 6 workers, `--network none`, as nobody. Log: `ALL_DONE rc=0`. Result OUT/fuzz/cf_out_r1.jsonl: 326 cases, 1 gen_error, **325 valid (P1 150, P2 109, P3 66), with 0 agent diffs and 0 oracle diffs**.
- Differing share per lever: CC-1 0%, CC-2 0%, CC-4 0%, COUPLING 0%. All are REVEALING.
- Any keep-rewrite with unchanged semantics would also show 0% on this program by construction, because the program already implements those semantics. Under the master's counting rule ("differs > 0% AND >= 25% alone"), only levers with new semantics can count. A rewrite only removes the giveaway for a fresh agent.

## 5. Trajectory autopsy (57 steps, about 9 minutes)

- Read (15:38:14-15:39:09): steps 3-5 ls and unzip; **6 the full config_contract.md**; 7-12 README, cli.py, loaders.py, resolve.py, emit.py, quota.py; 13-14 cat of every input head.
- Data probe (15:39:09-15:40:14): steps 15-20, one probe per stated lever: RETIRE kinds, log id spellings, ini sections, NOTICE lines, owners multi-match on D (19), and the JSON value types (20).
- Write (15:40:36-15:41:36): 21 rewrites loaders.py; 22-33 resolve, quota, emit and cli edits. The graded logic was settled here, and only step 51 later made a small change to resolve.py.
- Self-test (15:41:45-15:46:51, 5 min): 34 compile; 35-36 an independent /app/verify.py that re-derives every output from the raw inputs; 37-40 spot checks; 41 export-report; 42-45 missing input and catalog mismatch on copies; 46-47 a hand-built /tmp/fresh; 48 an altered copy /tmp/fresh2 (J9); 49 a random stress test with N=5000; 53 rebuild of tool.zip; 54 a re-verify plus a run of the delivered zip from another directory; 55 cleanup.
- The self-tests covered every stated lever on shipped and random data. None of them could find a rule the contract does not state.

## 6. LEAK_LIBRARY rows

| Lever | How it was written | Step leaked | Planned fix |
|---|---|---|---|
| LV-CC-1 | Both conditions named in one glossary sentence; both RETIRE kinds listed at :63-65 | 6, 15, 19 | Replace with NL-1 (latest-started assignment). Keep the RETIRE owner condition as background. |
| LV-CC-2 | Malformed JSON values enumerated at :104-106 (LV-ENUM) | 6, 20 | Delete the enumeration ("`type`: the value does not have the key's type"). Background, not counted. |
| LV-CC-4 | Global canonical-id rule with no exception | 6, 15-16 | Background, not counted. |
| COUPLING | Worked largest-remainder formula | 6, 29 | Kept as the amplifier and extended through NL-3 re-entry. |

## 7. Proposed lever plan (replace all three counted levers)

The prototype is in OUT/proto/: proto_ref.py (the oracle with every reflex as a flag), run_proto.py (it plants the cases into gen_corpus hidden corpora at seed 50000+i and scores the hidden rows lost) and mini.py. It ran 40 planted corpora, with the probe agent on 6, and wrote OUT/proto/proto_result.json. "Alone" means the hidden-tier rows lost out of 125 under the current weights, assuming the visible rows pass (W5).

| Lever | Reflex reading | Corpora differing | Alone (pts, % of 125) |
|---|---|---|---|
| NL-1 | first covering row (= probe) | 100% | 73, 58.4% |
| NL-1 | last covering row (= current ref) | 100% | 73, 58.4% |
| NL-1 | latest-started among covering rows (one-fact-wrong) | 100% | 73, 58.4% |
| NL-4 | Python int() / lower()=='true' (= probe) | 100% | 41.1, 32.9% (min 33) |
| NL-4 | str.isdigit for integers | 100% | 38.6, 30.9% (min 18) |
| NL-4 | accepts a leading sign only (one-fact-wrong) | 85% | 25.2, 20.1% (min 0) |
| NL-3 | water-fill again from the whole quota | 100% | 22.6, 18.1% (min 18) |
| NL-3 | one re-share, no re-check (one-fact-wrong) | 45% | 2.4, 1.9% |
| NL-3 | no caps (= probe) | 100% | 22.6, 18.1% |
| NL-2 | orphans share one budget | 100% | 28, 22.4% (ceiling) |
| NL-2 | rejected records consume budget | 97.5% | 26.8, 21.4% (min 0) |
| probe agent program (real zip) | | 6/6 | 73, 58.4% |

### NL-1 (H3 defined term differing from the per-line field): an owner's assignment on D (counted)
- Edit config_contract.md:38-40 to: "Assignment of an owner on D: of the owner's owners.csv rows with active_from on or before D, the one with the latest active_from. Active owner on D: an owner whose assignment on D has active_to empty or on or after D, and who has no `RETIRE owner=<owner>` event in deprecation.log dated on or before D. Their team on D is the team of their assignment on D." At :58-59 (Inputs 5), replace "The rows of one owner never overlap." with "An owner may have several rows; no two rows of one owner share an active_from."
- Hidden cases, 14 owners per hidden corpus: 8 get a later-started row with another team that covers D (open or ending after D); 6 get a later-started row that ended before D while an older row still covers D, so the owner is orphaned. The new row goes before the old one in file order for half of them and after it for the other half. Shipped data gets 1-2 owners with an overlap where both rows cover D (this separates the probe's first-row reading but not the latest-covering reflex, so W5 holds).
- Why a fresh agent trips: the habit is to filter rows that cover D and then choose one, so it picks the latest covering row. The defined term picks the latest-started row first and only then checks whether it covers D. Opus's habit of transliterating "rows ... active_to empty or on/after D" from the old glossary lands on the covering filter.
- The probe program differs: in mini.py (date 2028-03-10), owner a has the rows ingest 2020-01-01 open and growth 2025-01-01 open. The oracle gives DP1 active, team growth, quota 10. The probe gives DP1 team **ingest**, quota 26. Owner b has the rows risk 2020 open and search 2026-01-01..2026-06-30. The oracle gives DP2 **orphaned** with quota 0. The probe gives DP2 active, risk, quota 25.
- PL note: this is one upstream fact, and every hidden row depends on it through team, then selectors/team_overrides, then weight, then quota. That makes 58.4% alone, with the rows going wrong together. To keep it below a whole-tier wipe, only 14 of about 450 owners carry the case. Each per-family row still fails whole-document, so this is reported as the widest lever.

### NL-4 (H1 bare type property beside the global trim): text-layer integers and booleans (counted)
- Edit :84-87 to: "...integer as one or more of the digits 0 to 9; boolean as `true` or `false` in any letter case; ... Text that does not read as its key's type is passed over, and the key keeps the value the earlier layers gave it. Every text-layer key is in the schema, and text layers never list anything in validation_report.json." No malformed values are listed.
- Hidden cases: about 8% of the integer and boolean setting lines in products.ini, plus 2 `set weight` selector rules, carry fullwidth or other Unicode digits (2 of every 3 plants), `+N`, or `yes/no/on/1/0/off`. Shipped data may carry 2-3 such lines (H1 is the one W5 exception), which pushes the probe program below the reflex gate.
- Why it trips: Python `int()` (and `str.isdigit`, and regex `\d`) accept Unicode digits and a sign, and the reflex boolean is `lower() == 'true'`, which reads `yes` as false where the rule passes it over.
- The probe program differs: its loaders.text_value gives `'４'` = 4, `'+5'` = 5 and `'yes'` = False (verified by calling it). Shrunk case (hand-computed from the verified text_value and `_ref_shares`): base weight 1, `match team:risk set weight ４`, DP1 risk, DP2 ingest, Q=10. The oracle gives 5/5; the probe gives 8/2.
- Phase 2 will raise the sign-only one-fact row above 20% by planting `+N` in weight-bearing lines too.

### NL-3 (H7 re-entry, the only shape that ever differed in 1889 fuzz corpora): quota cap re-shared "by the same rule" (counted, needs owned rows)
- Add an optional schema key `quota_cap` (integer, 1-100000), set through selectors, env tiers or overrides. In :129-135, after the largest-remainder sentence add: "An active product whose quota then exceeds its resolved `quota_cap` gets its cap. Every product keeps the units it was given, and the units above the caps are handed out again by the same rule among the active products still below their cap, until no product is above its cap. When every product left has a cap and their remaining room fits within those units, each fills its room and the rest stays unassigned." summary quota_total then falls below Q on the early exit.
- Hidden cases (G12, every branch planted): caps on 10% of active products in each document. 60% of them bind on the first pass and 40% bind only after a re-share (a cascade). Plus one early exit per corpus. Shrunk case: Q=8, weights DP1 1, DP2 5, DP3 6, caps DP3 1 and DP1 3. The oracle gives **2/5/1**; the restart reflex gives **1/6/1** (floor(a)+floor(b) differs from floor(a+b), and both sum to Q, so a sum check cannot see it). The probe program has no caps and gives 1/3/4.
- Alone, it is 18.1% under the current rows (quota-only ceiling). Phase 2 adds three owned hidden rows on a cap-dense tier: `config_quota_capped_hard`, `dev_quota_capped_hard` and `prod_quota_capped_hard`, w5 each. That gives a predicted (22.6+15)/140 = 26.9% for restart. The one-fact-wrong row (one re-share) is predicted at about 10-15% once cascades are planted on that tier.

### NL-2 (H6 team change budget): NOT proposed
Its best reflex costs 22.4% with a 28-point ceiling, because orphans carry no quota or profile rows. H6 was 0% differing in sentinel and metered, and the rule text names its own key ("each team's"). It would add complexity without a counted lever, so I recommend dropping it unless the master wants a fourth family.

### Background rules (not counted)
- CC-2: delete the enumeration at :104-106, leaving "3. `type`: the value does not have the key's type." The precheck LV-ENUM must be clean.
- CC-1's RETIRE owner condition is folded into the NL-1 sentence.
- CC-4 stays global.

### COUPLING amplifier (stated)
NL-1 (team, then weights) and NL-4 (weight lines) feed the largest-remainder quota over all active products, and NL-3 re-enters it. So any upstream miss also fails config/dev/prod quota, readonly, rescale and summary.

### Predicted totals
- About 37 tests, P=140, hidden share about 63%.
- Predicted fresh-Opus outcomes:
  - misses only NL-3: tests about 73;
  - misses only NL-4: about 67;
  - misses NL-1: about 42.
- The target window (70-90 tests, overall < 70 at the measured judge) needs at least one miss plus the new conduct criteria.
- Reflex gate prediction: once shipped data carries the NL-1 double-cover and NL-4 lines, the probe program fails every visible family except catalog_status and rejected_overrides. Its score would be about (19 + 6)/140 = 0.18, which is at most 0.20 and will be checked in Phase 3 with the real tests.

## 8. Judge plan
- Keep R1-R12. J2: R1-R6 are too easy, since a single verify.py run on shipped data passed all six. Each one will require that the recompute ran on an input set the agent built itself, not only on the shipped data.
- Add one conduct criterion at w3 per new family, each printed by solve.sh as `check <id> ok`:
  - R13 (NL-1): runs on an extract with an owner whose later-started row ended before D, and checks that status is orphaned;
  - R14 (NL-4): runs a text-layer value that is not ASCII digits, and checks that the earlier value is kept;
  - R15 (NL-3): runs a cap that binds only after a re-share, and checks the quotas against a hand computation.
- R8 is reworded to the J4 text.
- R11 honesty (J3) is kept.
- `[judge] mode = "batched"`. The positive total becomes 37.

## 9. Not run in Phase 1
No bundle edits; QC scripts and precheck not run; no reflex gate on new tests (the tests do not exist yet).

DIAGNOSIS READY when the master has reviewed sections 7-8. Next: "go" starts Phase 2.
