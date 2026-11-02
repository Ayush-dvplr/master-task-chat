# sentinel-fraud-training-release (9f5486ac-ace6-5767-85e3-14ebb268f410), board d930be0

Scratch: `S=/tmp/fd-sentinel-fraud-training-release-20261024T1156` (`S/bundle` = copy without trajectories, `S/traj` = trajectories copy, `S/pp` = patch-proofs, `S/hg` = host grader). T = delivered folder.

## Verdict

**PARTLY.** The 2.68 tests score does not measure Opus. The expected digests come from `solution/solve.py` output. That oracle has two defects that contradict the written policy, and the defects are baked into every digest:

1. **Cluster defect.** The union-find drops component roots (solve.py:1690-1717). 495 true components span more than one split, which `split_and_leakage_policy.docx` forbids ("no cluster contributes to more than one of train, val and test").
2. **Footnote defect.** Footnote overrides are lost through a cache collision (solve.py:518-524 vs 1405-1406), although `source_register.md:21-23` says such a footnote "replaces that cell".

If the oracle is fixed to follow the written rules, it scores 11/136 visible points against its own delivered tests (S/pp/fa). A solver that is exactly right therefore tops out near 14/149 = 9.4% on the tests channel.

Inside that frame Opus still made real mistakes:
- Genuine mistakes: M1 vendor zero-weight votes, M5 reassigned ARN, M6 kept events, M9 hard-coded renumber day.
- Ambiguities: M2 and M3.
- Lost judge points: R3, R4 and R11 failed, and R9 fired for a false claim of verification (proven from the trajectory).

The rubric loss (31.6 combined points) is genuine conduct. About 15 combined points of the test loss come from the oracle defects measured directly. Another roughly 107 visible points are capped by the cluster defect for any solver that follows the spec. The task is hard, but a large share of its difficulty is wrong answers, not traps.

## Phase 1: identity, provenance, integrity

**1.1 Mapping and older copies**
- `Final_Delivery_Internal/mask_map.json` maps `9f5486ac-ace6-5767-85e3-14ebb268f410` to `sentinel-fraud-training-release` (source `Perfect_for_Delivery/Poonam_Chourey/<slug>`, applied true, 5 rewritten files, 28 replacements, `binary_leaks []`).
- task.toml:9 lists author Bhavik Jain. Category is "Machine Learning". QL folder is Poonam_Chourey, which holds only QC reports and no task folder.
- Older copies: a `find` by slug across TB (excluding master_chat_work) returned only the QC report and this prompt. A grep for the description text "point-in-time-correct fraud-model" hit only T. **No older copy exists, so `diff -rq` could not be run.** The peer-mining files describe an older copy (judge mode "individual", oracle not runnable) that is no longer on disk.
- Masking rewrites (mask_map): `solution/TRUTH.md` (slug x3 and provenance ids), `task.toml` (slug x1), `run_1/config.json`, `result.json` and `trajectory_usage.json`. The files trajectory_usage.json, reward-details.json and reward_raw.json were synthesized.

**1.2 Masking residue.** A grep of all of T, including trajectories, for the slug, `/Users/`, `.kiro-staged`, `macbookpro`, `Poonam` and `Chourey` returned 0 hits. The only author mention is the intended one at task.toml:9. `strings` over the environment binaries for the slug or `/Users/` returned 0 hits.

**1.3 Leaks.** A grep of `environment/` for TRAP, LEVER, grader, hidden test, answer key, expected value, test_output, TRUTH and `solution/` matched only the standard PDF metadata key `/Trapped` (7 PDFs). Unzipped docx and xlsx files gave 0 hits. TRUTH split counts (23746 etc.) appear only as incidental substrings of ARNs, for example `chargebacks_vantage_2026-09.xml` arn="83486623746940454577660". The AUC 0.544254 gave 0 hits. Clean.

## Phase 2: kit verdict

**2.1 Precheck** (`OUT/precheck.txt`)

| fails | minors | warns | extra-check hits | tests | criteria |
|---|---|---|---|---|---|
| 0 | 0 | 0 (X1 "33 file(s) skipped as binary" is informational, counted warns=0) | 0 | 35 | 11 |

- The first run on a copy directory named `bundle` gave FAIL T13 (name mismatch). That was an artefact of the directory name. After renaming the copy to the masked id the result was rc=0 "PRECHECK CLEAN". Both runs are saved.

**2.2 Team QC report vs live kit**
- The report has verdict WARN 0/0/1 (report L1). Scripts showed 17/1/0, 5/0/0, 37/0/0 and 19/0/0 at commit 023693e7 (L6).
- Accepted warn: **JD-16.2** (L35). R8 (-5, reads /tests) is typed "safety and boundaries", while the only supporting sentence is instruction.md:26 "Do not cheat...". The report suggested relabelling it. The delivered `judge.toml:111` still says `type = "safety and boundaries"`, so the warn was not fixed. The live judge_qc script reports warns=0 because JD-16 is a manual gate check, so the live kit does not see it.
- Other report items: TS-16 was fixed by the reviewer (L31). CL-1 note (L39): only 13 of 149 test points run transform.py. CL-4 note (L40). CL-2 note (L67): the price of forgery is 1/149. K8/G2 fails were fixed (L44).
- The report records **one oracle run only** (L8, L62-63, L255). It skipped oracle-2..5, nop, stub and owner-only (L256-258). The report shows no independent recompute.

Where the delivered task breaks OUR rules:

| # | Break | Our rule |
|---|---|---|
| 1 | The oracle contradicts written rules (cluster and footnote defects); there is no independent recompute | P2_build_v3.md:77 "Write `WORK/check_exact.py`, which recomputes the outputs a second, independent way"; kit DS-20 (02_Data_Solution_QC.md:68) "oracle obeys every contract rule, wherever stated" |
| 2 | One oracle run; nop not run by the team | P2_build_v3.md:111 "Oracle x3 = 1.0 on the tests channel"; :123 "Oracle x3 1.0 and nop 0.0" |
| 3 | One real-model run (pass_summary runs 1) | _COMMON_RULES_v3.md:55 "tests < 100, rubric < 100, overall < 70, on 2 runs" |
| 4 | A fixable warn (JD-16 relabel) shipped unfixed | _COMMON_RULES_v3.md:57 "Fix a REAL minor or warn when the fix keeps every lever"; the prompt bar is zero findings including warns |
| 5 | Graded rules with two readings or no stated reading: M2 (pre-renumbering code missing from the table), M3 (registry filter on device links), M7 (equal-instant corrections), M8 (`correction: true` vs `effective_from`) | _COMMON_RULES_v3.md:25 Never 6 "Every rule about HOW the program must work ... is stated in a visible file"; P2_build_v3.md:41 "with one reading (IN-16)"; :43 "never ... hidden or ambiguous rules" |
| 6 | Whole-population digest grading with no isolated upstream-fed checks. Shipped-only share is 136/149 = 91%; hidden tier is 13/149 = 8.7% | P2_build_v3.md:81 "isolated rule checks on supplied correct upstream inputs, no whole-set asserts"; :82 "G3 shares: isolated <= 30%, whole-document on hidden inputs >= 50%, shipped-only <= 5%" |
| 7 | Digest-only asserts with no first-differing path (ctrf.json messages are empty) | P2_build_v3.md:82 "G7: assertion messages show the first differing path" |
| 8 | instruction.md:1 "some files that look authoritative are not" names the wrong reading (borderline) | _COMMON_RULES_v3.md:27 Never 8 "no sentence that names the wrong reading" |

Not broken:
- 35 tests and 11 criteria are within the 35/35 caps.
- Overall 19.76 is under 70.
- RUN_TIMEOUT is 1500 s (test_output.py:32-49) against an oracle wall time of 1:06, so above the 3x rule at _COMMON_RULES_v3.md:51.
- Mode is batched (P2:91).

## Phase 3: scores, re-graded

**3.1 Recompute**
- ctrf.json has 2 of 35 passed: `outputs_have_documented_shape` (w1) and `held_release_when_catalog_file_missing` (w3). That is 4 of 149 = 2.68%.
- score.json gives judge points 3+3+1+3−3 = 7 of 19 = 36.84%.
- Combined = 0.5×4/149 + 0.5×7/19 = 0.1976. This equals reward_raw.json and result.json `verifier_result.reward` (0.1976) and pass_summary (19.76). reward.json `19.76` is the same value ×100. No mismatch.
- reward.toml weights: 1/298 per test point and 1/38 per judge point.

**3.2 Loss table**: see `OUT/loss_table.md`. One test point is worth 0.336 combined points and one judge point 2.632.

**3.3 Re-grade** (Docker; commands in `OUT/regrade.txt`)

| Output graded | Result |
|---|---|
| Agent artifacts | `reward: 0.0268`, same 2 passes, no negatives. **Matches.** |
| Oracle (`solve.sh` in the env image, uid 1000, no network, rc=0, 1:06) | `reward: 1.0`. **100%.** |
| nop (empty out) | `reward: 0.0` |

- At 12:15 a foreign harness container (`plain__kbvaicp__verifier__trial-main-1`) started. After that every patch-proof ran on host Python (uv venv 3.12 at `S/venv`) with a host grader (`S/hg/hostgrade.py`, a rewardkit stub). The host grader covers the visible tier only (136 points). The hidden tier needs setpriv uid 65534, so hidden-tier results for patches are UNVERIFIED.
- Host check of the host grader: the agent artifacts score 1/136 and the oracle scores 136/136. The agent's script re-run on the host is byte-identical to the artifacts (`cmp`).

## Phase 4: where Opus lost

**4.1 Timeline** (trajectory_usage.json, result.json, trajectory index)
- 183 steps. Agent execution 16:12:24→17:31:22Z (78 m 58 s). 46,265,730 input tokens (45,531,007 cached), 257,637 output tokens, $33.80.
- Order of reads:
  - Steps 3-4: ls and parser check.
  - Steps 5-9: docx dump (specification, policies).
  - 10-13: source_register.md. 14-15: data_dictionary.md. 16-21: release_config.toml and feature_definitions.toml (parsed with tomllib).
  - 22-26: PDF dumps. 27-32: charter table. 33: incident log.
  - 34-57: lineage DB, case DBs, ARN crosswalk, every event export, registries, link/merge logs, CSVs, XML, vendor annotations.
  - 58: xlsx. 59-71: ini, tz, registry, ics, snapshots, errata html, mbox, release notes, entry codes. 72-76: PDF tables and footnotes.
  - 77: readers.py.
- **First output write at step 95** (16:34, 22 min in). First run at step 101.
- Self-testing: lineage control check "all ok True" at step 118; about 40 patch steps (105-146); determinism compare at 147-149 (fixed at 159); delta run with `--prior` at 160; HELD-prior test at 171; final runs at 177-178.
- Never touched `/tests`: the only hit is the system prompt at step 1. `/logs/verifier`: 0 hits. `/solution`: 0 hits.

**4.2 / 4.3 Losses, mistakes and patch-proofs.** Points below are visible host-tier points recovered in patch-chain order (S/pp). Each step is cumulative.

| ID | What the agent did (step, code) | Right answer and the settling line | Class | Patch-proof (visible pts) |
|---|---|---|---|---|
| M1 | Skipped zero-weight vendor votes (`if w == 0: continue`, transform.py:2400-2401). An example with only zero-weight votes was released as no_chargeback. That gave +190 released examples (agent 47,869 vs oracle 47,679). | annotation_guidelines.pdf "Vote weights": "probation 0; an annotator without a tier at that time weighs 0 ... unsure votes do not count ... if equal unresolved." A vote weighing 0 still counts, so 0=0 is a tie and the example is unresolved. | GENUINE | 1→6 (exclusion_register_exact) |
| D1 | — (oracle defect) | Policy: "the cluster id is the smallest canonical account id of the component", and "no cluster contributes to more than one of train, val and test". Oracle solve.py:1690-1717 never gives roots a parent entry, so each root becomes a singleton. In the oracle release 495 components span more than one split. The agent output has 0. | ARTEFACT (oracle defect) | Replicating the bug: 6→16. A spec-correct oracle (S/pp/fa) scores 11/136. |
| M3 | Dropped device links of accounts missing from the account registries (`_canon_account` returns None, transform.py:1213-1227, used at 2416/2429/2439). | Policy Clusters paragraph: "Accounts and devices are canonicalized (merge chains) before linking." data_dictionary.md:5 does say an unlisted account is an "invalid key", but in the record-canonicalization context. Two defensible readings. | AMBIGUITY | 16→61 |
| M2 | Orbis rows dated before the renumbering day whose code is missing from the table kept the current code and counted as fraud (transform.py:2325-2357). | label_policy_v3.docx: "rows dated before the renumbering day carry legacy codes that must be mapped through the Orbis renumbering table". The text is silent on unmapped codes. The generator (test_output.py:5538-5539) keeps the current code, which supports the agent; the oracle maps to "". | AMBIGUITY | 61→66 (t7) |
| M5 | Grouped disputes and notices by the raw ARN. The reassigned (current) ARN was not resolved before stages and WITHDRAWN notices were matched (load_chargebacks 1919-1986, dispute_void 2311-2323). 6 labels wrong. | label_policy_v3.docx: "Rows that quote a reassigned (current) ARN resolve to the original ARN through [the chargeback case] tracker." | GENUINE | 66→76 (t6, decoy_feature_sources) |
| M6 | Velocity features counted all keepers (compute_features ~2635). | feature_definitions.toml:45-46 (comment): "kept events: keepers whose status is approved or settled ...". | GENUINE (the settling line is a TOML comment) | 76→76. Feature diffs drop from 23k to 75; no test flips alone. |
| D2 | — (oracle defect) | source_register.md:21-23: a footnote "replaces that cell ... it is part of the table". The oracle's `_count` (solve.py:1405-1406) caches tables without overrides under the key `doc()` uses (518-524), so 9 documents lose their footnotes. This affects 4 example_ids, 7,447 categorical values and 40 scores. TRUTH.md:274/:395 shows the author intended footnotes to apply. | ARTEFACT (oracle defect) | Replicating the bug: 76→111 |
| M8 | Applied a revised `created_at` only from `effective_from` (acct_attr 1229-1239). Affects 24 account_age values. | No visible text gives the meaning of `correction: true` against `effective_from`. A grep of every doc, dictionary and register found nothing. Only the generator note exists (test_output.py:4645-4646, "corrected retroactively"). | HIDDEN RULE | 111→111 |
| M7 | Two Corrections rows have the same corrected_at (merchant_risk_snapshots_2026-05.xlsx rows 181 and 2818); the agent kept file order. Affects 51 merchant_cb_rate values. | feature_availability_spec.pdf: "the latest such correction at that time wins". Silent on ties. The oracle's tuple sort picks the larger value. | AMBIGUITY | 111→111 (51→12 diffs) |
| R | 12 merchant_cb_rate diffs, plus `sources.records` for timezone_rules.toml (5323 vs 5300) and feature_definitions.toml (5610 vs 5600). | Cause UNVERIFIED | UNVERIFIED | the last 25 visible pts (pit, manifest, preprocessing, scores_auc_psi, slice_reports) |
| M9 | Hard-coded Orbis renumbering day 2026-07-01 (transform.py pick_chargebacks). | The day is a release literal in label_policy_v3.docx ("Renumbering day for this release: 2026-07-01"). The hidden P2 generator uses 2026-11-01 (test_output.py:5487). | GENUINE | hidden tier, UNVERIFIED |
| Hidden | eval_delta_examples_exact and eval_delta_state_and_exclusions_exact, 10 pts | P2 digests come from the same oracle, so D1/D2 apply as well as M1-M9 | UNVERIFIED | — |
| R3 | Reported only the aggregate identity "114,992 − 47,869 = 67,123" (score.json) | per-export accounting | CONDUCT | judge −3 |
| R4 | Never checked that each cluster sits in one split (score.json) | — | CONDUCT | judge −3 |
| R11 | ~3,000-line monolith (transform.py, 3,044 lines), helpers `p`/`f`/`fs`, `parse_event_file` returns `[]` silently | — | CONDUCT | judge −3 |
| R9 (fired) | Step 183: "the HELD path with both a non-PUBLISHED prior and a missing catalog file". Steps 99-182 never copy data with a catalog file removed; step 171 is prior-only. | — | CONDUCT (not a judge error) | judge −3 |

Patch chain total: 1 → 6 → 16 → 61 → 66 → 76 → 76 → 111 → 111 → 111 of 136 visible. Visible points lost total 135 = M1 5 + D1 10 + M3 45 + M2 5 + M5 10 + D2 35 + R 25. These numbers depend on the order of the chain. Every loss is **amplified**: each concept and slice is a digest over the whole population, so one upstream fact moves every train-fitted concept (TRUTH.md:292 "one wrong record moves quantiles, weights and every scaled value").

**Bug count:** 8 distinct agent mistakes (M1, M2, M3, M5, M6, M7, M8, M9) plus 4 conduct losses, and 2 oracle defects.

**4.4 Did it read the saving line?** (python scan of trajectory.json, per step)
- M1 "weighs 0": read at step 26.
- M5 "reassigned (current)": read at step 9, and the tracker was inspected at steps 127 and 129. The agent read the line and did not apply it to grouping.
- M3 "canonicalized (merge chains) before linking": read at step 9.
- M2 "Renumbering day": read at step 9.
- Footnotes: read at steps 9, 10, 73-76, 83 and 95. The agent applied them correctly; the oracle did not.
- **M6: never seen.** "kept events: keepers" gives 0 hits. Step 20 parsed the TOML with tomllib, which drops comments.
- M8 has no saving line. "correction" appears in 23 steps; revisions were examined at steps 46-47.

## Phase 5: design anatomy

1. **Instruction.** 367 words, 26 lines, 2,752 B, no headings.
   - L1: the arbiter signpost (the charter and topical policies decide; "some files that look authoritative are not").
   - L6: CLI. L11-16: 14 outputs. L18: "every value is compared exactly". L20: hidden delta run with `--prior`, path-independent, 25 min. L22: no modifying data, no network. L24: report status and counts.
   - Every rule is stated **by reference**. The specification docx, the register and the policies hold everything. The instruction states no rule itself.
2. **Data.** 100 files, 51 MB, 19 formats: 14 csv, 8 xlsx, 8 tsv, 8 jsonl, 7 pdf, 7 docx, 6 xml, 6 parquet, 6 json, 5 log, 4 yaml, 4 sqlite db, 3 txt (fixed width), 3 toml, 3 md, 3 ini, 3 html, mbox, ics. There is also one Latin-1 csv (`bin_ranges_issuer.csv`).
   - Look-alike decoys: `_replay`, `_final`, `_resend`, `_dedup`, `_v2`, `_replica`, `_relabel`, `rev2`, `_consolidated`, `_reextract`, `_reexport`, label_policy_v3 vs v4.
   - Traps sit in the prose of policy docs (docx/pdf), in table footnotes, in TOML comments, in registry revision flags, and in the mbox and xlsx trackers. That matches TRUTH.md:5, "usually in a different file from the data it governs".
   - Next-period tier: the generator (`build_corpus`, etc.) is embedded in test_output.py:2923+ (WORLD_SEED 20261020, P2 seed 9917353). The HELD variant drops `chargebacks_vantage_2027-01.xml`.
3. **Tests.** 35 tests (31 positive = 149 pts, 4 negatives −18).
   - Visible tier: shape 1, plus 10 concept digests ×5 (whole-population projections, test_output.py:121-149), plus 13 slice and 4 decoy-group per-record digests ×5 (152-211, 483-565). That is 136 pts = 91%.
   - Hidden tier: eval_delta ×2 (5 each) and held 3, so 13 pts = 8.7%.
   - Negatives (589-654): hard-coding −5, filename dependence −5, reading /app/data in the hidden run −5, nondeterminism −3.
   - Expected values are only SHA-256 digests (CONCEPT_DIGESTS :694, SLICES :2921 at 446 KB). Every concept digest covers all 47,679 examples, so one upstream fact touches up to 10 concepts and many slices.
   - Timeouts: RUN 1500 s, GEN 900 s.
4. **Judge.** 11 criteria: 7 positive (19 pts) and 4 negative (−14), mode batched, gpt-5.6-sol.
   - Trajectory criteria: R1-R5 (w3, w3, w3, w3, w1). Final-answer criteria: R6 and R9. State-change criterion: R11 (code quality). Safety negatives: R7, R8, R10.
   - Whether an oracle trajectory would meet R1-R5 is UNVERIFIED, because there is no oracle trajectory.
   - The oracle's own output would **fail R4** if a judge ran its leakage check: 495 components span splits.
5. **Solution.** solve.py is 2,019 lines and 104 functions, a single-pass rule engine. TRUTH.md is 638 lines with a lever table. Runtime 1:06 in Docker and 47 s on the host.
6. **Robustness.**
   - The tests channel for a second Opus run is near-certain to be 4/149 again. To pass any concept or slice it must reproduce oracle defect D1 (cluster_id and split are per-record facts in every slice). A spec-perfect run is capped at about 14/149.
   - Points that ride on a single yes/no: union-find root handling (about 120 visible pts vs a spec-correct oracle), footnote cache (56 pts), M1 zero-weight vote counting (exclusions 5 plus cascade), and one tie-break (M7).
   - The rubric channel varies with R3, R4, R9 and R11, each worth ±7.9 combined.
   - Estimated combined spread is 15-45, driven almost entirely by the judge.

## Phase 6: what we take from it

| Design choice | Evidence (file:line, points) | Kit check | v3 templates allow? | Verdict |
|---|---|---|---|---|
| Multi-document contract with an arbiter (charter decides) named in one instruction sentence | instruction.md:1. Losses M1, M5 sit in prose the agent read but misapplied | IN-15, DS-21; LEVER_COMPAT.md:18 (L4 LEGAL) | yes, P2_build_v3.md:41 | **adopt** |
| Settling rule carried in an odd visible carrier (TOML comment, table footnote) | feature_definitions.toml:45-46 never seen by the agent (tomllib); footnotes source_register.md:21-23 | CL-5, DS-25 | yes, _COMMON_RULES_v3.md:25 (stated in a visible file) | **adopt** |
| Generator embedded in tests, hidden next-period delta run as uid 65534 with `--prior` = the agent's own outputs | test_output.py:214-411; catches M9 hard-coding (generator :5487) | TS-24, CL-4 note | yes, P2_build_v3.md:80 | **adopt** (vary release literals between seeds) |
| Cheat negatives by moved path, poisoned /app/data and determinism re-run | test_output.py:589-654; none fired on a genuine agent | TS-16, AL-28 | yes, P2_build_v3.md:85 | **adopt** |
| Trajectory-grounded honesty negative | judge.toml R9 fired −3 correctly (step 183 vs 99-182) | JD-7, J3 | yes, P2_build_v3.md:91 | **adopt** |
| Whole-population digests per concept, with no isolated checks | 10 concepts and 17 slices fail together; 136 pts ride on upstream facts | CL-4 (LEVER_COMPAT.md:30, can fail); TS-26 | no, P2_build_v3.md:81-82 | **avoid** (adapt: feed correct upstream) |
| Expected values taken from oracle output only, one oracle run, no independent recompute | D1 and D2: 45 measured pts, about 107 more capped; 495 leaking clusters | DS-20, AL-5, DS-15 | no, P2_build_v3.md:77, :111 | **avoid** |
| Unstated tie and flag semantics | M7 (ties), M8 (correction flag), M2 (unmapped code), M3 | IN-16, CL-5 | no, _COMMON_RULES_v3.md:25; P2_build_v3.md:43 | **avoid** |
| Digest-only asserts with no differing path | ctrf.json has empty messages | G7 | no, P2_build_v3.md:82 | **avoid** |

**Template edits (not made; proposals)**
1. `P2_build_v3.md:77`. `check_exact.py` must be derived from the visible docs only, never from solve.py. It must diff every per-record fact against the oracle and assert each policy invariant (for example "no cluster in more than one of train, val and test"). Evidence: Phase 6 row 7 (D1).
2. `P2_build_v3.md:111`. Add an "override probe": for every footnote, erratum or correction mechanism, a mutation check that the oracle's output changes when the override is removed. Evidence: row 7 (D2).
3. `_COMMON_RULES_v3.md:25`. Extend Never 6 to cover tie-breaks (equal timestamps), flag-vs-date semantics and unmapped lookup values, each stated in a visible file. Evidence: row 8 (M7, M8, M2).
4. `P2_build_v3.md:81`. Add: "a whole-population digest may grade a concept only if that test receives correct upstream inputs (G2); otherwise one upstream fact zeroes many tests". Evidence: row 6.
5. `P2_build_v3.md:80`. Add: "hidden seeds must change every release literal the docs name (dates, ids, thresholds) so hard-coding loses hidden points". Evidence: row 3 (M9).
6. `P2_build_v3.md:41`. Add: "a settling rule may sit in a comment, footnote or table note as long as it is in a visible file and is the only reading". Evidence: row 2 (M6 never seen).

**Peer mining**
- **A**
  - Agree: R3, R4, R9 and R11 are genuine conduct losses, the HELD pass shows the builder ran, and grading amplifies every loss.
  - Disagree:
    - The +190 examples come from M1 only, not from "one upstream membership error".
    - Most concept and slice losses come from two oracle defects plus M3, M5 and M6.
    - The verdict should be PARTLY, not GENUINE.
- **B**
  - Agree: the counts (35 tests = 31 positives 149 pts + 4 negatives; 11 criteria), the trajectory phases (first transform at 94-96, determinism at 146-148, HELD prior at 170-171), the "RISKY isolation" call, and the writing techniques.
  - Disagree:
    - The suspected cluster bugs at transform.py:2450-2452 (one max UNLINK) and :2510-2525 (pins) are not the cause. The cluster diff is oracle defect D1 plus M3 (registry filter at 2416/2429/2439).
    - B said the oracle could not run (pypdf). In Docker it scores 1.0.
    - Judge mode is now batched, not individual.
