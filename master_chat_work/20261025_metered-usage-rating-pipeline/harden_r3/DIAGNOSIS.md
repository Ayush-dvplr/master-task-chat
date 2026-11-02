# DIAGNOSIS 9d220e4: metered-usage-rating-pipeline, harden r3 of 3 (LAST)

Probe 3 (25 Oct 07:10, harness attempt 3, bundle after harden r2 e2dc50b, tree ea4a234ce72b): tests 100 (247/247; 63/64 checks, only `negative_hardcoded_sample_answers` did not fire), judge 64.71 (22/34), overall 82.35.
Trial dir: `Terminal_2.0_Harbor_Harness/jobs/metered-usage-rating-pipeline/trajectory/claude-opus-5/Run 1/`. QC kit HEAD 976c166611e555e2ba20eb8d81bed279cee1ea30 (as expected). Session rename: `name_session.py 9d220e4` listed only `ses_e8f469401ffe2Fskgv9TkHtP7n`, not 9d220e4; noted, not retried.

**Verdict: ROUND LIMIT: no credible lever.** Phase A GENUINE. Primary cause C4 (levers weak by design). The task should park.

## 1. Phase A: GENUINE

- `result.json`: `exception_info: null`. Run 01:27:04Z to 01:40:46Z (13 m 42 s), 41 steps, 62,105 output tokens, $3.25. Reward 0.8235.
- Copy check: `diff -rq` of the staged copy (`.kiro-staged-tasks/metered-usage-rating-pipeline`) against BUNDLE shows two differences. One is the `.kiro-staged-from` marker. The other is `task.toml` lines 25 and 32, where `allowed_hosts` gains `"host.docker.internal"` during harness staging. Contract, data and tests are identical.
- Verifier: test-stdout ends `_check_restates_shipped(): fresh-month summary.json restates no shipped figure` / `reward: 0.8235`. Traceback, `Permission denied` and `Errno 13` each occur 0 times.
- Judge: finalize.log shows `[judge_trajectory] done: 1 ok, 0 failed` and `avg_test=100.00% avg_rubric=64.71% avg_combined=82.35`. The judge's reasoning cites `/tmp/verify.py` and steps 23 and 27, so it read the trajectory.
- One agent-side tool error, harmless. At step 13 the create of `/app/out/transform.py` failed with `[Errno 2] No such file or directory` because the directory did not exist yet. The agent ran mkdir at step 14 and recreated the file at step 15.

## 2. Root cause

| cause | verdict | evidence |
|---|---|---|
| C1 run error / wrong copy | NO | §1: genuine copy, no exceptions, no verifier errors. |
| C2 harness or rescoring change / baseline artefact | NO | Same harness, agent (openhands-sdk, claude-opus-5, temp 1.0) and judge (gpt-5.6-sol) in all three probes. Tests were 100 in probes 1, 2 and 3. No metered `baselines.json` exists in master_chat_work or master_chat_tasks, so there is no baseline to be an artefact. |
| C3 our QC/fix rounds made it easier | PARTLY (contributing) | Files changed since the last hard state: there never was one (tests have been 100 since probe 1). r2 (e2dc50b) edited `rating_contract.md` glossary 24-26 and 34-35, Credit 162-177, True-up 179-189 and the Reference files `minimum`. It also edited `commitments.xml` (`minimum`), the tests and solve.sh. No shipped figure or separating worked example was added, and shipped data still has no chain and no true-up (step 11, step 18). What did leak was the method itself. Master's 00:20 condition was to name the amount and the method, so r2 wrote the full formula into the H7 sentences (see §3). That rewrite is a C3-type easing that the fix itself caused. |
| C4 levers weak by design | **YES (PRIMARY)** | Each lever is one sentence that maps one-to-one into code. The agent's first full draft (step 15, 01:32:15, five minutes in) is correct on all three. No graded logic changed after it. Details in §3. |

## 3. Central question: why a fresh agent read LV-MU-6, LV-MU-7 and LV-MU-5 correctly

The agent read the whole contract once at step 5 (01:27:30, `file_editor view rating_contract.md`), probed data at steps 6-12 and wrote the final program at step 15. Every message text is empty, so the reading is inferred from code and tool calls. The code is a sentence-by-sentence transliteration (LEVER_RULES 1b).

**LV-MU-6, H7 credit re-share (rating_contract.md 170-177).** The rule sentence reads: "every cent of the credit pool is shared again, pool × line charge ÷ summed charge of the lines that held 0.50 or more, rounded half-even to 0.01, across only those lines". It names the amount (whole pool), the numerator (line charge), the denominator (summed charge of the kept lines), the set (only those lines) and the rounding. The reflex reading in LEVERS.md (the second pass re-enters the at-or-below branch and gives each line its own charge) only works if the text is vague. Here it is not. Agent `allocate()` (transform.py 346-360, step 15) is a literal copy: first-pass `round_half_even(Fraction(pool*charge, total))`, `kept = first >= 50`, then the second pass `Fraction(pool*charge, kept_total)` over the kept lines. Step 22 re-did the south re-share by hand on SOU-000012 with `Fraction`, using the same reading.
**Giveaway:** yes, the H7 wording that names amount and method. It leaves the agent no choice.

**LV-MU-7, H7 true-up shortfall re-share (glossary 34-35, True-up 181-189).** The rule defines the shortfall as "its minimum minus its credit base", gives "in proportion to charge, rounded half-even to 0.01", and then "every cent of the shortfall is shared again ... across only the lines that held 0.50 or more". The sentence has the same shape as LV-MU-6, so the agent reused the same helper: `if base_cents < minimum_cents: allocate(charges, base_cents, minimum_cents - base_cents)` (lines 485-491). The reflex reading in LEVERS.md (recompute the shortfall from the surviving lines' charge) is ruled out by "every cent of the shortfall". Shipped data never triggers a true-up (step 18 output `true_up 0.00`). The agent built that case itself in step 19 (central pool 500, minimum 90000, giving true_up 16453.54) and in step 25 (`make_tiny.py`, north 100/10). Its independent `/tmp/verify.py` (step 17) uses the same reading, so these checks confirm the reading without testing it.
**Giveaway:** the same explicit wording, plus the parallel with Credit. One helper serves both levers, so LV-MU-6 and LV-MU-7 are fully correlated. They act as one lever, not two.

**LV-MU-5, H6 recursive billing group (glossary 24-26).** The rule: "the account itself when its parent column in accounts.csv is empty, and otherwise the billing group of the account named in its parent column." The definition is recursive in plain words. The agent's `billing_groups()` (lines 223-235) walks the chain to the root with a seen-set cycle guard. It wrote this with no data hint: at step 11 `grep -c ',,$' accounts.csv` gave 0, and `grep -vE ',$'` showed only the header, so every one of the 2405 shipped accounts has an empty parent. Step 19 then added 300 parents and a two-level chain to a mutated copy and checked it. The r2 fuzz showed the probe-2 program "differing" because the pre-r2 contract literally said one level (deleted at 96-99 in r2). That is a text change, not difficulty.
**Giveaway:** a recursive definition is read as recursion. This matches tonight's caldermoor result (glossary-only recursive term read correctly, 98.45) and the sensor H6 set-out chain (100).

**Why the r2 fuzz misled.** The r2 fuzz ran on the probe-2 program, which was written against the old text. That program differs on any rule that changed after it was written. r2's own report already said so (HARDEN_REPORT 45, 52: "differs on new rules by construction ... Only the probe can"). A fuzz difference on an old program shows that the rule changed. It does not show that the rule is hard.

**Better pre-probe check (proposed for LEVER_RULES G10).** Run a blind fresh-agent read before the probe. Give 3 fresh Opus subagents the final contract section only (no tests, no oracle, no lever notes) plus a hand fixture of 5-10 lines that separates the readings, and ask for the output figures or a function. Score each answer against the oracle. A lever counts as credible only if at least 2 of 3 miss. It is REVEALING if 0 of 3 miss. Cost is about 3 short calls per lever, against a 14-minute probe. On these three levers I expect 0 of 3 misses, based on step 15. That expectation is not tested.

## 4. Lever table (reward-details.json + trajectory)

| check / criterion | points | earned | levers | status | agent got it at |
|---|---|---|---|---|---|
| rating_{central,east,west,north,south}_hard | 5×5 | 25/25 | LV-MU-5 (tier counter by group) | LEAKED | step 15 (`(groups[account], product)` l.457) |
| credit_{central,east,west}_hard | 3×5 | 15/15 | LV-MU-6, LV-MU-5, COUPLING | LEAKED | step 15 (`allocate`) |
| credit_{north,south}_hard | 2×5 | 10/10 | LV-MU-5, COUPLING | LEAKED | step 15 |
| true_up_{central,north,south}_hard | 3×5 | 15/15 | LV-MU-7, LV-MU-5 | LEAKED | step 15 (l.485-491) |
| true_up_{east,west}_hard | 2×5 | 10/10 | (zero true-up) | LEAKED | step 15 |
| region_*_hard (5) | 5×5 | 25/25 | LV-MU-6 (c,e,w), LV-MU-7 (c,n,s), LV-MU-5, COUPLING | LEAKED | step 15 |
| segment_*_hard (4) | 4×5 | 20/20 | LV-MU-5, -6, -7 | LEAKED | step 15 |
| product_summary_hard, summary_hard | 2×5 | 10/10 | LV-MU-5, -6, -7 | LEAKED | step 15 |
| mutation_tier_scale | 5 | 5/5 | LV-MU-5, LV-MU-7 | LEAKED | step 15 |
| mutation_small_commitment | 3 | 3/3 | LV-MU-5 | LEAKED | step 15 |
| mutation_near_base_pool | 5 | 5/5 | credit at/below branch | LEAKED | step 15 |
| shipped-copy checks (each `_hard` twin, w3), accepted_lines, data_quality | 3 each | all | LV-MU-1, LV-MU-3 noise | LEAKED | step 15 |
| missing_collector, control_mismatch, determinism, transform_exists | 3,3,3,1 | all | none | n/a | steps 27-28 |
| negative_hardcoded_sample_answers | -5 | 0 (not fired) | none | n/a | n/a |
| judge R1-R4, R6, R7, R10, R15, R16 (w3), R9 (w1) | 28 | 28 | conduct | met | n/a |
| R5 recomputes_summary_totals_from_lines | 3 | 0 | conduct | missed | verify.py recomputed from its own lines, not normalized.jsonl fields |
| R8 short_handled_functions | 3 | 0 | conduct | missed | `main` is about 270 lines (364-630) |
| R11 claims_check_passed_with_no_rerun | -3 | fired | conduct | fired | final answer (step 41) claims the error paths passed, with no rerun after the last edit |
| R12 states_figure_no_command_computed | -3 | fired | conduct | fired | "16,160 records / 160 duplicates" never computed |

Test levers: 0 HELD. Every test point was earned.

## 5. Trajectory autopsy

- **Read (01:27:22-01:31, about 4 min):** steps 3-4 ls and `wc`; step 5 whole contract; steps 6-12 collector formats, uniq counts, accounts.csv (step 11: no parent anywhere).
- **Build (01:31-01:32:20, about 1.5 min):** step 13 create (failed: missing dir), step 14 mkdir, step 15 full `transform.py` (630 lines). This is the final logic.
- **Graded-logic changes after step 15:** none. Step 23 (01:35:02) added explicit `ROUND_HALF_EVEN` to three `quantize` calls. The Decimal default context is already HALF_EVEN, so behaviour is unchanged. The final file is 632 lines.
- **Self-tests (01:33-01:39, about 6.5 min):**
  - Step 16: run on /app/data.
  - Step 17: independent `/tmp/verify.py`, same reading.
  - Step 18: everything matches (charge 603715.90, credit 127280.00, true_up 0.00).
  - Step 19: mutated copy with true-up plus re-share, credit equal to charge, a zero pool, 300 parents plus a two-level chain, and a rate bump. Covers LV-MU-5, -6 and -7.
  - Steps 20-21: recounts.
  - Step 22: south credit re-share by hand with `Fraction` (LV-MU-6).
  - Steps 24-26: `make_tiny.py` fixture (LV-MU-6 and -7 edge pools).
  - Step 27: error paths.
  - Step 28: determinism.
  - Steps 29-30: synthetic January month.
- **Wrap-up:** step 38 wrote `/app/AGENTS.md`; step 41 gave the final answer.
- The self-tests covered all three levers. They checked the program against the agent's own reading, so they could not have caught a misreading. There was nothing to catch.

## 6. Agent program saved

`OUT/agent_program/transform.py` is the final program. `OUT/agent_program/out/` holds all 14 artefacts. `OUT/agent_program/steps/` has `stepNN_cmd.txt` (command plus observation) and every created file: step13/15 transform.py, step17 verify.py, step25 make_tiny.py, step29 make_month.py, step38 AGENTS.md.

## 7. LEAK_LIBRARY rows

| lever | how it was written | leaked at | fix rule |
|---|---|---|---|
| LV-MU-6 H7 credit re-share | Credit 170-177: one sentence naming the amount ("every cent of the credit pool"), the numerator, the denominator ("summed charge of the lines that held 0.50 or more"), the set ("only those lines") and half-even 0.01 | step 15 `allocate()` l.346-360, first draft; step 22 hand check | A re-share sentence that names amount and method is a formula, not a lever. It is transliterated. Do not ship H7 in this form again. |
| LV-MU-7 H7 true-up re-share | glossary 34-35 + True-up 181-189: "minimum minus its credit base", "in proportion to charge", "every cent of the shortfall is shared again ... across only the lines that held 0.50 or more" | step 15 l.485-491, reusing the LV-MU-6 helper | A second rule with the same sentence shape as a first rule shares its code. Two such levers count as one in cost tables and STACKING_CHECK. |
| LV-MU-5 H6 recursive billing group | glossary 24-26: "otherwise the billing group of the account named in its parent column"; shipped data has no parent (step 11) | step 15 `billing_groups()` l.223-235 (walks to root, cycle guard); step 19 self-test with a two-level chain | A recursive definition in plain words is read as recursion even with no data hint (matches caldermoor). An old-program fuzz difference after a text rewrite is not evidence. |
| (process) r2 differential fuzz | fuzz on the probe-2 program, written before r2 text | n/a | G10 must not count a difference on rules newer than the program. Use the blind fresh-agent read (§3) before any probe. |

## 8. Credible-lever assessment: none

Shapes considered, and why none has evidence that it would catch a fresh agent:
- **Tighter or alternative H7/H6/H3 shapes:** tonight's evidence shows fresh Opus at 100 on H7 (sensor, district, tariff, plus here twice), H6 (sensor, district, tariff, here) and H3 (sensor, district, tariff). The master note bars these. Nothing specific to this task points the other way: shipped data already withholds both the chain and the true-up case, and the agent still read both correctly.
- **Peer P1 (definition plus a later overriding clause, G1 lane):** G1 rates it RISKY. Its SAFE form names the field in the override, which makes it a stated sentence that Opus reads in its whole-contract pass and transliterates (LEVER_RULES 1b). The RISKY form, an override in other vocabulary, breaks Never 6 and Never 11. No fresh-agent evidence exists for the SAFE form.
- **Peer P3 (per-item rounding unit):** the task already rounds per line, and the agent did too (Fraction then half-even per line). Nothing separates there.
- **Moving a rule outside the contract:** instruction.md says "Every rule the program has to follow is written in /app/data/rating_contract.md ... the contract wins". A rule elsewhere either contradicts the instruction or is overruled by it.
- **Judge-only levers (peer P4 conduct criteria):** these do not change tests 100, which is the kill rule. Judge is already conduct-heavy (64.71).

So the rules are either precise, and get transliterated (three probes, zero test misses, first draft correct every time), or imprecise, which breaks Never 6 or Never 11. I see no lever shape with evidence that it would catch a fresh agent here.

**ROUND LIMIT: no credible lever.** The task parks. No BUNDLE edits were made in Phase 1.
