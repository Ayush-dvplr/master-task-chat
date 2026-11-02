# 36f01dd: survey-raking-disclosure-audit (masked id 71a3ecf5-d795-5052-943b-433dd78bcbba)

Paths: D = `Anubis_Tasks_Samples/Final_Delivery/71a3ecf5-d795-5052-943b-433dd78bcbba`, R = `D/trajectories/claude-opus-5/run_1`, S = `/tmp/fd-survey-raking-disclosure-audit-20261024T1156` (scratch, removed at the end). Commands and outputs are in `regrade.txt`, the per-item table is in `loss_table.md`, and the kit output is in `precheck.txt`.

## Verdict

**PARTLY.** The low score (41.22) comes from one real agent mistake that the grading multiplies. Opus read the reference-wave band sentence (HAS-7-standard.md:239-244, read whole at trajectory step 4) as "the reference-wave band is always the wave-two chain". So its program never uses the wave-three interview's own hours (agent derive_survey.py:1242-1251, written at step 29). That single branch accounts for 97 of the 98 lost raw points. When I patch only that branch, all 22 reports match the oracle byte for byte, the tests score 128/128 (regrade.txt), and the agent's own what-if commands then print every judge figure it missed: 5393301, 5, 331499999995, 3, 15, 43. Three things make it not a pure GENUINE loss:
- **The sentence allows two readings.** The parallel wave-one sentence says "whose interview carries no hours". The reference-wave sentence has no such qualifier, so its "it" can be read either way. The oracle's reading is the better one structurally, but nothing in the data lets the agent check it.
- **Most of the loss is amplification.** One rule error is charged across 15 tests and 6 figure-restating judge criteria: 55.6 of the 58.8 lost combined points.
- **The task was a single yes/no.** A second run that reads the sentence the oracle's way would score about 97-99, not about 41.

There is no artefact: the regrade reproduces exactly, the oracle scores 100%, and nop scores 0.

## Phase 1: identity, provenance, integrity

### 1.1 Mapping and diffs
- `Final_Delivery_Internal/mask_map.json` maps id 71a3ecf5-… to slug survey-raking-disclosure-audit. It records applied true, 8 rewritten files, 31 replacements, binary_leaks []. Its source is the Perfect_for_Delivery/Poonam_Chourey folder; locally that folder holds only the QC report.
- task.toml:9 gives the author as Aditya Jain. task.toml:12 gives `category = "Data Science"`. The QL folder is Poonam_Chourey.
- **`diff -rq` against Pass@1_New/Poonam_Chourey/Aditya Jain/… (ignoring trajectories/ and output/): 5 files differ, all from masking.**
  - environment/Dockerfile:1, tests/Dockerfile:1, task.toml:5 and tests/test_output.py:1: slug → id.
  - solution/TRUTH.md:1 (title) and :199-201: provenance `uuid: null` → id, plus instance_id and task_name.
  - No functional change. The Pass@1 copy also holds an unmasked `output/` with logs titled `…-regrade` and trial `__TBa2niP`. That is the regrade trial whose id appears in trajectory_usage.json.
- **`diff -rq` against Low_Effort_Tasks_(Client_Fixed)/No_Trajectory/…: a different, older generation of the task.**
  - Old layout: README.md and TRUTH.md at the root, tests/rubric.json (32 items), tests/test_weights.json (33 tests, positive sum 93), no judge.toml or reward.toml.
  - Old instruction: 265 lines / 2764 words. Delivered: 24 / 608.
  - 54 data files, against 47 now. Eight old files are dropped (sensitivity, published-margins, transitions, activity/psu/sector codes, malformations, recodes). calib__pilot-round.json and solution/TRUTH.md are new.
  - Why it matters: this is a full re-authoring to the rewardkit layout, not a QC patch. The instruction was cut by about 78%, the rules moved into the standard, and the rubric went from 32 items to 18 criteria.

### 1.2 Masking residue
`grep -rnIi` over all of D, including trajectories, for slug, author, QL, `/Users/`, `.kiro-staged`, `macbookpro` and `/home/` finds only:
- task.toml:9 `authors = [{ name = "Aditya Jain", email = "aditya.jainint17@ethara.ai" }]`. This is the authors field, so it is by design, but it does name the author.
- environment/Dockerfile:5-6 `/home/agent`. Benign.

No slug and no host paths remain.

### 1.3 Author-note and answer leaks in environment/
- Grepping for TRAP, LEVER, grader, hidden test, answer key, expected value, oracle, solution, TRUTH, verifier, pytest, judge and rubric finds two hits:
  - environment/Dockerfile:31: "…so the agent and the oracle can write it". This file is not visible inside the container.
  - HAS-7-standard.md:186 `## 10. Frame resolution`. False positive.
- None of the judge figures (5393301, 331499999995, 867452) appears under environment/.
- calib__pilot-round.json is a separate pilot dataset (controls_uw, published, units). It contains none of the main answers.
- One near-leak, found by the team QC (AL-18): the Q5 answer 331499999995 equals `final_total_uw` of replicate NR1::NR1P2 in the oracle's replicate_summary.csv. That makes instruction.md:13 "None of the answers is written into any report" literally false. It is a coincidence the agent could not exploit.

## Phase 2: kit verdict

### 2.1 precheck.sh (copy without trajectories)
| item | value |
|---|---|
| kit fails / minors / warns | 0 / 0 / 0 (structure 17 pass, instruction 5, tests 37, judge 19) |
| our extra-check hits | 1: `FINDING: ENV HOME not in lines 2-3 after FROM: environment/Dockerfile (FC-S24)`. ENV HOME is at line 6 |
| tests | 35 (28 positive, 128 pts; 7 negatives, -25) |
| judge criteria | 18 (11 positive, 39 pts; 7 negatives, -17) |
| precheck rc | 1 (`PRECHECK: 1 finding(s)`) |

### 2.2 Team QC report against our live kit
- **Team report (Perfect_for_Delivery/Poonam_Chourey/survey-raking-disclosure-audit_QC_Report.md).**
  - :3 `WARN (0 fails, 0 minors, 1 warn, accepted by the tasker)`.
  - The single warn is AL-18 (:30, :242): the Q5 answer sits in replicate_summary.csv. The tasker accepted it (:32-41, :273) under the kit's "push-ready once the tasker sees it and approves" rule (Final_checklist.md:448).
  - Today our live kit returns 0 warns. It does not fire AL-18, which is a reading check (UNVERIFIED whether the kit's AL-18 is automated; precheck.txt shows no AL-18 line). We agree with the team that the fact is real.
- **QC change table (:47-52).**
  - Changes: judge R9 weight 1→3; R15 retargeted; R16 made positive (+3); reward.toml judge weight 0.5/39.
  - "Its judge score needs re-grading against the new judge.toml; the agent does not need to re-run." This is why the delivered judge result is a regrade (verifier at 2026-10-23T06:14Z, a day after the agent run).
- **The team's CL-4 pass contradicts this run.** CL-4 passed (:216, "68 to 118 of 128 per single-rule slip"), but this run's single-rule slip scored 53/128.
- **IN-16 (:113), JD-8 (:194) and DS-30 (:131) passed in the team QC.**

**Where the delivered task breaks OUR rules:**
| # | breach | our rule |
|---|---|---|
| 1 | Warn accepted, not fixed (AL-18) | _COMMON_RULES_v3.md:56 "The PL accepts zero findings, warns included (dec 101): a WARN is a finding to fix, not to record." |
| 2 | ENV HOME at Dockerfile line 6, not the first lines (FC-S24) | _COMMON_RULES_v3.md:38 "`environment/Dockerfile` sets `ENV HOME` in its first lines" |
| 3 | Only 1 model run (pass_summary.json `runs: 1`) | _COMMON_RULES_v3.md:55 "tests < 100, rubric < 100, overall < 70, on 2 runs before PL"; KNOWLEDGE.md:6 |
| 4 | R1-R8 are "The response states … N" criteria: 34 of 39 positive judge points restate a TRUTH figure | P2_build_v3.md:91 "J1 no "states figure X" criteria"; _COMMON_RULES_v3.md:48; QC_FIX_PLAYBOOK_v2.md:29 |
| 5 | Shipped-only tests 4×5 = 20/128 = 15.6% | P2_build_v3.md:82 "shipped-only <= 5%" |
| 6 | Grouped tests: each group test asserts 2-7 documents together (test_output.py:3194-3206, `_group_on` :3281-3284) | P2_build_v3.md:81 "one test per downstream document … each asserting only its own document … no whole-set asserts" |
| 7 | No isolated rule checks on supplied correct upstream inputs: every test derives from raw data, so one upstream slip fails every downstream group | P2_build_v3.md:81 ("isolated rule checks on supplied correct upstream inputs") |
| 8 | A rule that can be read two ways decided 97 raw points (HAS-7-standard.md:239-244) | P2_build_v3.md:41 "one reading (IN-16)" |
| 9 | Judge criteria were edited after the run and the run was re-graded, not re-run (QC report :47-52). No direct rule; noted only | none (cf. _COMMON_RULES_v3.md:55, 2 runs) |

Not a breach:
- Overall 41.22 is under 70.
- 35 tests and 18 criteria are within the caps (_COMMON_RULES_v3.md:56).
- The 120 s program limit is at least 3× the oracle time: the oracle took 7.28 s wall on the shipped data, and all 7 runs in the full verifier grade took about 31 s (regrade.txt) (:51).
- The settings left for the agent to derive (instruction.md:9) are settled by the shipped pilot data and graded, so they meet _COMMON_RULES_v3.md:25.

## Phase 3: scores, re-graded
- **3.1 Combined score.**
  - ctrf/reward-details give tests 53/128 = 41.406% and judge 16/39 = 41.026%.
  - reward.toml weights are 0.5/128 and 0.5/39, so combined = 0.5·41.406 + 0.5·41.026 = 41.216 → 41.22.
  - This matches pass_summary.json, reward.json `{"reward": 41.22}`, reward_raw.json 0.4122 and result.json `verifier_result.reward 0.4122`. No mismatch.
- **Earlier 36.88 / 41.41 / 32.35.** That was graded on the pre-QC-fix judge: 34 positive points (R2 5 + R3 5 + R9 1 = 11, so 11/34 = 32.35). The delivered judge.toml raised R9 to 3 and added R16 +3, which the agent passes. That gives 16/39 = 41.03 (QC report :47-52). Tests are unchanged.
- **3.2 Loss table.** See `loss_table.md`. Positive points lost: 75 test + 23 judge. No negative fired, either in tests (7 tests, all 0) or in the judge (7 criteria, all 0).
- **3.3 Regrade.** I ran the delivered tests in a verifier image built from tests/Dockerfile (judge.toml removed, `rewardkit` only):
  - Agent's artifacts: `reward: 0.4141`, 53/128, with zero per-item differences from the delivered reward-details. **Reproduces.**
  - Oracle (solve.sh run as uid 1000): `reward: 1.0`, 128/128.
  - nop (empty /app/out): `reward: 0.0`.
  - Agent script with the one band branch patched: `reward: 1.0`, 128/128.

## Phase 4: where Opus lost, from the trajectory
- **4.1 Timeline.**
  - 62 steps; 2026-10-22 11:21:18 → 11:44:32 UTC, about 23 min of the 7200 s allowed.
  - Tokens: 7,413,829 in (7,213,709 cached), 102,970 out, $7.43.
  - Reading order:
    - Step 3: `ls /app`.
    - Step 4: `cat` of the whole HAS-7-standard.md. This includes the band paragraph.
    - Step 5: the field dictionary. Step 6: the rules, ref and config files. Step 7: the frame registers.
    - Steps 8-10: contact logs. Step 11: interviews and prior bands. Step 12: benchmarks and registry.
    - Steps 13-14: the pilot JSON plus a 12-combination search in Fractions. This found the unique combination that reproduces 26/26 pilot figures.
  - Build and test:
    - Step 22 (11:30:30): first write of /app/out/derive_survey.py. The band block is written at step 29 and revisited at step 44, where only the wave indices changed.
    - Step 33: first full run, to /tmp/t1.
    - Self-tests: step 45 (row shuffle and renamed directory), step 55 (determinism), step 57 (report keys), step 58 (an independent re-implementation of the raking).
    - What-ifs: steps 47, 48, 56 and 59.
    - Step 53 (11:41:53): first write of the reports to /app/out. Step 54: it removes /app/out/__pycache__.
    - Step 62: final summary.
  - A grep of every argument and observation shows no access to `/tests`, `/logs/verifier` or `solution/`.
- **4.2 Per-loss cause.** See `loss_table.md`.
  - All 15 failed test groups (3 shipped, 12 hidden) are caused by M1, the band rule. The root is AMBIGUITY (one test-equivalent); the rest is AMPLIFICATION.
  - Judge R1, R4, R5, R6, R7 and R8 (22 pts) are M1 again. They are AMPLIFICATION: the agent's what-if *method* was right, and its own commands on the patched base print the right figures (regrade.txt, "What-if re-run").
  - R10 (1 pt) is CONDUCT and fair: `eligible_set` is dead at agent derive_survey.py:1226, and write_reports is a 427-line function at :1569.
  - JUDGE ERROR: none. I checked every score.json reason against the agent's actual figures. ARTEFACT: none.
  - The right answer is settled, on the oracle's reading, by HAS-7-standard.md:236-239: "The band of a unit at a wave follows from its hours through the band register … Where hours are absent the band carries forward. For the reference wave it is the band of the unit's wave two interview hours; …". The first sentence applies to every wave; the reference-wave clause describes the carry-forward. The agent took that clause as overriding.
- **4.3 Bug count: 2 distinct mistakes.**
  - M1: 75 test pts over 15 tests plus 22 judge pts over 6 criteria. Proven by patch: tests come back 75/75, and all 6 judge figures are recovered.
  - M2: 1 judge pt (R10).
- **4.4 Did it read the saving line?** Yes. Step 4's observation contains HAS-7-standard.md:236-244 in full, and step 44 edits the same block without changing the rule. Nothing in the data would show the error: the pilot covers raking only, and the band affects only cell membership.

## Phase 5: design anatomy
1. **Instruction: 24 lines, 608 words.**
   - It defines the deliverable contract: the program path and CLI, stdlib only, 120 s, the 22 report names, exact match, determinism, independence from directory name and row order (:3-7).
   - It states the rules only by reference: "the standard is the contract" (:1).
   - It withholds two settings and points to the pilot to settle them (:9).
   - It gives the conduct rules (:11) and eight what-if questions (:15-22).
   - It deliberately leaves out every computation rule, every trap, and the hidden extracts' parameters. It says only that the program "will be run again … on other extracts … with different households, benchmarks, settings and sampling structure" (:3).
2. **Data: 47 files, 4.6 MB, 15 formats.**
   - Format counts: csv 11, jsonl 5, tsv 4, toml 4, psv 4, json 4, fwf 3, properties 2, logfmt 2, ini 2, conf 2, sexp, rfc822, rfc5424, md.
   - UTF-8 non-ASCII is used for the NFC "Westföld" trap. There is no xlsx, pdf, parquet, sqlite or Latin-1.
   - The standard is 508 lines / 4201 words in 16 sections.
   - Traps (TRUTH.md:14-49) sit in the data: contact corrections, a contact-band decoy (ref__contact-bands.sexp), gated trimming, replicate replay chains, benchmark ties, reissue PSU, a stale wave-2 prior against the wave-2 interview (trap 10), a zero dwelling, NFC names, and the shipped raking stopping unconverged at 13 iterations.
   - Hidden tiers are generated inside the verifier (build_case, test_output.py:1018). Challenge: 420 households, 5 areas. Second: 560 households, 4 regions. Third: 480 households. Each tier has its own margin order, rounding point, collapse cap, cascade cap and iteration limit (test_output.py:98-107; TRUTH.md:96-101).
3. **Tests: 35.**
   - 3 gates at w1; 4 shipped groups at w5 (20); 21 hidden groups at w5 (7 groups × 3 tiers = 105, 82% of the positive weight).
   - 7 negatives: hardcoded −5, reuses_shipped_margin_order −5; nondeterministic, filename, row order, writes_outside and third_party −3 each (test_output.py:3467-3590).
   - Whole-population grading: the expected output is built by a reference implementation inside the verifier (`expected()` :2613), and a group passes only if every file in it is byte-equal (`_group_on` :3281-3284).
   - One concept touches up to 15 tests: the band rule feeds adjustment, trimming, estimates and disclosure in all 4 corpora.
   - Anti-hardcode: the challenge output must not reuse ≥11 shipped bytes, the challenge raking_trace must not reuse the shipped margin order, and an AST import scan blocks third-party libraries.
   - Runs: 120 s per run, as nobody, in its own session, serialized (:3134-3153).
   - There is no isolated-input test.
4. **Judge: 18 criteria.**
   - 8 output-figure criteria (R1-R8, 32 pts; judge.toml:13-107) and 3 trajectory/conduct positives (R9 w3, R10 w1, R16 w3).
   - 7 negatives: R11 −5 edits data, R12 −1 stray file, R13 −3 unchecked pilot claim, R14 −3 false pass, R15 −3 answer differs from own output, R17 −1 repeats a failing command, R18 −1 cites an unread source.
   - The oracle has no trajectory ("The judged channel has no oracle score", TRUTH.md:137). Its figures would pass R1-R8 by construction (`disclosure_facts`, test_output.py:2776). R9, R10 and R16 depend on agent conduct.
5. **Solution:** solve.py has 1032 lines (47.5 KB), stdlib only, one pass, with the settings hard-coded as recovered from the pilot. Runtime is 7.28 s wall including container start (regrade.txt).
6. **Robustness.**
   - The band reading is one yes/no decision worth 97 raw points, about 57.5 combined. On the oracle's reading a run scores about tests 100 / judge 38-39 of 39, about 98.7 combined. On the agent's reading it scores about 41.
   - The other single decisions (pilot order and rounding, which the agent got 26/26; collapse and cascade caps, which pass on hidden tiers; trap 10, which passes) were all solved by this run, so this run gives no estimate of how much they spread.
   - Expected spread: bimodal, about 41 or about 98. I cannot estimate the probability from one run (UNVERIFIED).

## Phase 6: what we take from it

| design choice | evidence (file:line, points produced) | kit check that allows it | our v3 templates | decision |
|---|---|---|---|---|
| Every rule lives in one long standard; the instruction is only a contract (608 words) | instruction.md:1,3-7; HAS-7-standard.md 508 lines; kit instruction 5/5 pass | IN-15 | P2_build_v3.md:41 (rule must be in a visible file): allowed | adopt |
| Hidden extracts generated in the verifier with different settings per tier, reference implementation in the verifier, no stored answers | test_output.py:98-107, :1018, :2613; 105/128 weight; 70 of the 75 lost test pts | DS-21, TS-30, LEVER_COMPAT.md:24 (c) LEGAL | P2_build_v3.md:55, :81 G1 "reseeded hidden inputs": allowed | adopt |
| Two settings withheld and recoverable from a shipped pilot, plus a negative for reusing the shipped value | instruction.md:9; calib__pilot-round.json; test_output.py negative_reuses_shipped_margin_order −5; agent solved it (R2, R9 pass), 0 pts lost | LEVER_COMPAT.md:22 (a) CONDITIONAL; IN-9 | _COMMON_RULES_v3.md:25 allows when the data settles it and a test grades it | adapt (cheap anti-hardcode; not hard for Opus) |
| Grouped whole-set asserts on raw-data chains with no isolated-input tests, so one upstream slip fails every downstream group | test_output.py:3194-3206, :3281; M1 = 75 pts / 15 tests | kit passed CL-4 (QC :216), TS-13 is minor only (by_check.json: 14 minor) | P2_build_v3.md:81 forbids whole-set asserts and asks for isolated checks | avoid (it is the amplifier; a QL who reads CL-4 against a real run will flag it) |
| What-if figure criteria ("The response states … N") on counterfactuals not in any report | judge.toml:13-107; 32 pts; 22 lost to the same M1 | judge_qc 19/19 pass; JD-8 passed (QC :194) | P2_build_v3.md:91 J1 and _COMMON_RULES_v3.md:48 forbid | adapt: allow at most 2 counterfactual-rerun criteria whose figure is in no report, paired with R16-style conduct |
| Conduct criteria tied to the lever (R9 compares candidates; R16 reruns under a changed setting) and honesty negatives (R13, R14, R15, R18) | judge.toml:117,208,169-237; the agent kept 6 pts, no negative fired | JD-18 / JD-15 pass | P2_build_v3.md:91 J2 and J3: allowed | adopt |
| Key rule written in one dense sentence with an unqualified "it" | HAS-7-standard.md:239-244; 97 raw pts ride on it | IN-16 passed (QC :113) | P2_build_v3.md:41 forbids two readings | avoid |
| Accepted warn plus a single run plus a judge re-grade after the run | QC :3, :47-52; pass_summary runs 1 | Final_checklist.md:448 allows accepted warns | _COMMON_RULES_v3.md:55-56 forbid | avoid (our bar is stricter on purpose) |

### Template edits (proposed; none made)
1. **P2_build_v3.md:82 (G3).** Add a "single-slip" measurement: for each rule an upstream stage depends on, run its one-rule mutation and record the tests it fails. More than 3 downstream tests failing on one rule = rebuild with isolated inputs. Evidence: the grouped-asserts row (M1 = 75/128 over 15 tests, while the team's CL-4 claimed 68-118).
2. **_COMMON_RULES_v3.md:48 (J1).** Add a narrow exception: a counterfactual figure that appears in no output and needs a rerun under a changed setting may be graded, at most 2 such criteria per task, each at w ≤ 3, and only alongside a rerun-conduct criterion. Evidence: the what-if row (R1-R8 passed the kit; the method can be graded separately from the base, as R16 shows).
3. **P2_build_v3.md:41 (IN-16).** Add a self-check: any sentence in the standard that contains a pronoun or "it" and gives a wave-specific or exception rule must restate its condition ("where the reference-wave interview carries no hours"). Evidence: the dense-sentence row (HAS-7-standard.md:239, 97 pts).
4. **QC_FIX_PLAYBOOK_v2.md** (new row near :29). AL-18 fix recipe: grep every judge figure against the oracle's own reports before saying "not in any report". Evidence: the team QC's AL-18 (replicate_summary.csv NR1::NR1P2).
5. **P2_build_v3.md:55 (test plan).** Add an optional anti-hardcode negative for each withheld setting: assert the hidden-tier trace does not echo the shipped value. Evidence: the withheld-settings row (test_output.py negative_reuses_shipped_margin_order).
6. **precheck FC-S24 (our extra check) / _COMMON_RULES_v3.md:38.** Decide "first lines" against the kit's DS-30: the kit passes ENV HOME at line 6 (QC :131), while we flag it. Either tighten the wording to "lines 2-3" or loosen the check to "before the first RUN". Evidence: precheck.txt FC-S24.

### Against the earlier peer mining (G3 A and B)
- **Agree with A.**
  - The root cause is the reference-wave band (agent :1242-1251 against oracle solve.py:463-476).
  - A one-branch patch reproduces all 22 oracle reports. I reproduced it, and add 128/128 on the tests.
  - Eight reports were already byte-identical. My count is 14 of 22 differing, which agrees.
  - The verdict is PARTLY, because of the IN-16 risk.
  - The raking figures match: 13 iterations at 5,393,296 against the agent's 4 at 867,448.
- **Agree with B.** 82% of the weight is on hidden tiers, and the judge what-ifs double-charge the one error (JD-8 risk). I quantify it: 22 of the 23 lost judge points are M1.
- **Where my figures differ from A/B.** Their scores (36.88 / 32.35) came from the pre-fix judge; the delivered judge is 39-point. Their bug count (one) leaves out R10's dead code, a separate 1-pt CONDUCT loss.
- **Addition.** The team QC's CL-4 claim ("68-118 of 128 per single-rule slip") is falsified by this run: 53/128.

## UNVERIFIED
- Whether the kit's AL-18 is an automated or a reading check: today's precheck reports 0 warns.
- The judge.toml text from before the QC fix is not available locally. The 34-point composition is inferred from the QC change table (:47-52).
- Which TRUTH.md mutation (:129-137) equals the agent's exact bug. The agent's 0.414 equals the "wrong final band fallback" figure, but that is not proven to be the same bug.
- How likely a second Opus run is to choose the oracle's band reading.
