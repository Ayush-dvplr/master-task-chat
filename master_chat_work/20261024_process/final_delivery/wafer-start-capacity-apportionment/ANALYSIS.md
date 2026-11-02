# e841c43: wafer-start-capacity-apportionment (masked aa314fee-a873-5778-9d55-e8892e6d7cda)

Delivered folder: `Anubis_Tasks_Samples/Final_Delivery/aa314fee-a873-5778-9d55-e8892e6d7cda/` (T). Scratch: `/tmp/fd-wafer-start-capacity-apportionment-20261024T1157` ($S). Run: `trajectories/claude-opus-5/run_1`.
Companion files: `loss_table.md` (every test and criterion), `regrade.txt` (commands, outputs, injection proofs), `precheck.txt`, `result.json`, `LOG.md`.

## Verdict

**PARTLY.** The 3.03 test score is not mainly a measure of Opus's skill. The answer key contradicts the written contract in three places: the status instant (identity_rules.md:39-43 against solve.py:1203), the hops of a failed walk (output_contract.md:28-29 against solve.py:511,518) and stale counting for duplicate versions (state_machine.md:9-12 against solve.py:1129-1132). Opus followed the text at all three. If the oracle is patched to the literal reading of all three, it scores only **8/66** on its own tests (regrade.txt, `oc_status_hops_stale`). The status reading alone takes it to 13/66. Gating multiplies the damage: five tests require the summary `granted_equiv` total to match exactly, three require `ledger_rows` to match, and the hidden-extract tests compare digests against the key. So one ledger-moving reading costs 53 of 66. Judge R1-R8 (40 of 62 judge points) then bill the same ledger again as eight exact counterfactual figures. Opus does also make genuine mistakes. After the oracle is aligned to the agent's five readings, 1,682 ledger rows still differ in granted: duplicate-row and node-source handling, 5 membership rows, lot and floor counts. Opus would therefore have lost most ledger tests even against a correct key. That is why the verdict is PARTLY and not ARTEFACT. The two "absent rules" that the instruction presents as the designed levers did not cost Opus anything: it settled both correctly (score.json R9 and R10 passed; trajectory steps 11-12 and 62).

## Phase 1: identity, provenance, integrity

| item | finding | evidence |
|---|---|---|
| mapping | aa314fee-a873-5778-9d55-e8892e6d7cda = wafer-start-capacity-apportionment | `Final_Delivery_Internal/mask_map.json` mappings entry (identifier, slug, rewritten_files 7, replacements 30, binary_leaks []) |
| author / category / QL | Anjali Kumari; Optimization; QL Sugam_Agrawal | T/task.toml:9 authors, :12 category; git path `Perfect_for_Delivery/Sugam_Agrawal/...` |
| older copies | **They exist**, contrary to the task block: they are in the git history of Anubis_Tasks_Samples | commit 6591f7ab (Anjali Kumari, 2026-10-23 05:25 UTC, "add two task by anjali in pass@1", `Pass@1_New/Sugam_Agrawal/Anjali kumari/...`); 52a1e9f1 (Sugam Agrawal, 12:54 IST, "Accepted ... (pass 17.64%)", to `Perfect_for_Delivery/...`); 8e01a082 (Shreeyank Doliya, 17:41 IST, "Deliver ... as UUIDv5 bundle") |
| diff pass@1 vs PfD | only `solution/TRUTH.md`. The pitfalls column was renamed from "Share of the test total" to "Weight of the checks it defeats directly", and a paragraph was added: "A reference program carrying one of them on its own and nothing else earns between 2 and 13 of the 66 positive points". This is a documentation fix made at QL acceptance; no test, instruction or environment changed | `diff -rq $S/old_pass1 $S/old_pfd` |
| diff PfD vs delivered | masking only: Dockerfile:1 bundle comment, TRUTH.md:1 and :136-138 (uuid, instance_id, task_name), solve.py:2 docstring, task.toml:5 name. Delivered trajectories add synthesized trajectory_usage.json, reward-details.json and reward_raw.json, plus path rewrites in config.json and result.json | `diff -rq` excluding trajectories; mask_map host_path_rewrites |
| team QC report | **none exists** for this task. The only QC reports in Perfect_for_Delivery cover 4 other tasks. The pass@1 commit went to acceptance in about 2 h | grep for wafer-start / aa314fee over QC/, QC assigned/, master_chat_*, Anubis_Tasks_Samples: no hits |
| masking residue | none. The only hit is task.toml:9 authors (metadata, by design). The words "wafer start" and "apportionment" appear only as topic words | grep for slug forms, author names, /Users/, .kiro, macbook, ec2-user, old uuid 8f3c6d2a |
| env leaks | none. Zero hits for TRAP, LEVER, grader, hidden test, answer key, expected value, TRUTH, solve.py, test_output, pitfall, canary. None of the key or judge figures (2628151, 2639801, 1853621, 1697490, 2626670, 49249, 2639795, 1690162, 4329957, 23022, 14832, 3221) appears under environment/ | grep -r over T/environment |

## Phase 2: kit verdict

`precheck.sh` was run on a copy without `trajectories/` (`$S/pc/aa314fee-...`), and the output is saved as `precheck.txt`. Last line: `PRECHECK: 1 finding(s)`, exit 1.

| fails | minors | warns | our extra checks | tests | criteria |
|---|---|---|---|---|---|
| 0 | 0 | 14 (tests_qc A5) | 0 (gaps, author notes and caps sections empty) | 27 | 29 |

- All 14 warns read `WARN [A5] check <name> (line N) reads agent output with no try/except` (lines 326 ... 631). This is a **kit false positive**: every check body is `return _safe(body)` (test_output.py:322,336,...,653), and `_safe` wraps the body in try/except and returns False (test_output.py:82). A static lint does not see the wrapper.
- My first run used a copy dir named `bundle` and got an extra `FAIL [T13] name must be 'terminal-bench/bundle'`. That is an artefact of the copy's directory name, not a bundle defect ($S/precheck_bundle_dirname.txt).
- There is no team QC report, so there is nothing to compare finding by finding. The tasker accepted nothing on record; the QL accepted on the strength of one run.

**Where the delivered task breaks OUR rules but was still delivered:**

| # | break | our rule |
|---|---|---|
| 1 | 14 kit warns (false positives, but still findings) | _COMMON_RULES_v3.md:56 "The PL accepts zero findings, warns included (dec 101)" |
| 2 | judge R1-R8 (w5 each, 40 pts): "The response states that ... 2628151 ... 851" | _COMMON_RULES_v3.md:48 J1 "no criterion whose only content is a number from TRUTH.md or the agent's own figure"; P2_build_v3.md:91 J1; QC_FIX_PLAYBOOK_v2.md:29 NEVER "states figure X" |
| 3 | R9-R16 are trajectory conduct criteria; the oracle (solve.sh, which leaves no trajectory) cannot show them | _COMMON_RULES_v3.md:49 conduct criterion only if the oracle trajectory can show it (JD-7) |
| 4 | gated cascades: 5 tests gated on summary granted_equiv (test_output.py:464,477,521,599,616), 3 on ledger_rows (:493,:551,:570), T6 compares totals to the key (:383) | P2_build_v3.md:81 G1/G2 "each asserting only its own document", no whole-set asserts |
| 5 | hidden extracts are fixed, embedded as zlib tar (test_output.py:22-23), not seeded | P2_build_v3.md:80 "Generate the hidden inputs verifier-side from a seed that lives only in `tests/`" |
| 6 | key contradicts 3 written rules (Phase 4) | _COMMON_RULES_v3.md:25 Never 6 (rules stated in a visible file; outcome derivable only if shipped data settles it) |
| 7 | instruction.md is 6007 B | P2_build_v3.md:101 "under 6000 characters" |
| 8 | accepted on 1 run (pass_summary.json runs 1) | _COMMON_RULES_v3.md:55 gate "on 2 runs" |

Within our bar: 27 tests and 29 criteria (caps 35/35, COMMON:56); combined 17.64 < 70 (COMMON:55); negatives 27 ≤ positives 66 in both channels (KNOWLEDGE.md:8).

## Phase 3: scores, re-graded

- Recompute: ctrf.json gives 2 of 27 passed, both w1 (`artifacts_present_and_parse`, `program_runs_and_exits_clean`), so tests = 2/66 = 3.03 %. score.json gives judge kept 20/62 = 32.26 %. reward.toml weights are test_output 1/132 and judge 1/124, so each channel counts 50 %: 0.5·3.03 + 0.5·32.26 = 17.645, recorded as **17.64**. This matches `pass_summary.json` (combined 17.64, tests 3.03, rubric 32.26), `verifier/reward.json` {"reward": 17.64}, `reward_raw.json` 0.1764, `result.json` verifier_result 0.1764 and `test-stdout.txt` "reward: 0.1764". No mismatch. `reward-details.json` is `synthesized: true` and holds no detail, so the table was built from ctrf.json and score.json.
- Loss table: see `loss_table.md` (27 tests, 29 criteria, with weight, kept, lost, fired and class for each).
- Re-grade in Docker, using my own image `fdwafer-verifier:e841c43` built from a copy of tests/ with judge.toml removed. Full commands are in regrade.txt:

| workspace | points | test % | negatives fired | matches record |
|---|---|---|---|---|
| agent artifacts (run_1/artifacts/app/out) | 2/66 | 3.03 | none | **yes** (same 2 passes) |
| oracle (solve.sh semantics, 5.2 s) | 66/66 | 100 | none | — |
| nop (empty /app/out) | 0/66 | 0 | none | — |

## Phase 4: where Opus lost

### Timeline (trajectory.json, 62 steps; trajectory_usage.json total_steps 62)
Agent execution ran 02:17:36→02:45:44Z, about 28 min of the 10800 s budget (result.json). Tokens: 6,358,682 in (6,094,329 cached), 125,419 out, $7.83 (final_metrics). Order of work:
- step 3: `ls` and `wc` of /app/data.
- step 4: corpus_index.md.
- steps 5-8: **every** rule document, the ini files, the properties file, reason_codes.json and output_contract.md, all by 02:18:04.
- steps 9-29: data profiling. Step 11 read the governance log `governed_by` tally, step 12 the deficit log lot_age × state, steps 13-14 the DST clock marks, step 22 the approval audit continuation lines, steps 27-28 the order-book duplicate refs.
- step 30 (02:30:26): first write of /app/out/derive_report.py. Step 32: full rewrite. Step 33: first run.
- steps 34-51: self-checks through internal identities only.
- step 52: counterfactual runs (/tmp/cf.py).
- step 56: determinism double-run md5sum.
- step 60: final regenerate. Step 61: chmod and rm /tmp/cf.py. Step 62: final message.
It never touched /tests, /logs/verifier, solution/ or TRUTH (grep over all steps after step 2: no hits). It tested its own work for internal consistency and determinism only; it had no external count to test against, which is what the instruction intends (instruction.md L5: "there is no count to check yourself against").

### Distinct mistakes (agent against key)

| M | mistake | what the agent did | what the text says | class | points it alone costs (oracle injection) |
|---|---|---|---|---|---|
| M1 | failed substitution walk | hops 0, quantity unconverted (derive_report.py:716,724,726) | output_contract.md:28-29 "Where the walk found no served node, `served_node` is an empty string and `hops` is zero." Oracle emits hops > 0 on 591 rows and converts by the failed walk's factors (e.g. North C02 REG-0001098: hops 3, qty 413 against the agent's 0 and 257) | HIDDEN RULE (key contradicts text) | 5 (hops only, `oc_hops0` 61/66); 25 (hops and no conversion, `oc_contract` 41/66) |
| M2 | status instant | master row at or before the **cycle start** (derive_report.py:1024) | identity_rules.md:39-43 "with the greatest `effective_utc` at or before the start of its cycle". Oracle uses request.effective (solve.py:1203); 99 reason flips (e.g. CUS-5425 / REG-0000341 C01) | HIDDEN RULE | 53 (`oc_status` 13/66) |
| M3 | duplicate version also stale | counted both (derive_report.py:969-972); stale 799 | state_machine.md:9-12 "since the first of them sets the highest version applied, the second is stale". Oracle `continue`s before the stale tally (solve.py:1129-1132); stale 26 | HIDDEN RULE | 3 (`oc_stale` 63/66) |
| M4 | new carry lot | q − current grant, so the ceiling-cut current quantity is kept | carry_forward_rules.md:38-39 "An amount a ceiling keeps out of the claim stays in its lot and is not lost"; :43-45 "The part of the current quantity the grant does not reach becomes a new lot". Oracle uses min(q, claim) − grant (solve.py:1374) | AMBIGUITY (text leans to the agent) | 53 (`oc_carry` 13/66) |
| M5 | move_to into an already-due cycle | two obligations (floor 328 for AGR-04145 C10) | commitment_rules.md:37-39 "adds the same obligation to `target_cycle`, whether or not the recurrence would have made it due there". Oracle's set collapses it to 164 (solve.py:1247) | AMBIGUITY | 53 (`oc_floor` 13/66) |
| M6 | duplicate-row / node-source handling | raw-line duplicate key (derive_report.py:464-477); takes N90 for REG-0000441 | provenance_rules.md:16-20 "identical payload" (payload undefined). Oracle compares shape (solve.py:934-951); dup identical/conflicting 54/593 against 359/284; 15 node rows | GENUINE / AMBIGUITY | UNVERIFIED alone |
| M7 | membership / out-of-scope | 5 ledger rows, 4 oos rows differ (23017/143 against 23022/147) | output_contract.md out_of_scope rules | GENUINE | UNVERIFIED alone |
| M8 | AUT source rows | counted `.files` only, 2088 | source_declarations.properties:23-24 lists `.files` **and** `.audit`. Oracle counts the audit logs too (12512) | AMBIGUITY | 3 directly (T13), also gated |
| M9 | no_qualified_node tally | 178 (rows with that reason) | output_contract.md:89 names the key only. Oracle counts walk errors whatever the winning reason, 740 | AMBIGUITY | inside T12 (gated) |
| M10 | residual lot and floor counts | lots_expired 3716 / cleared 71, floors 7673/139/7386 | remain after M1-M5 alignment (oracle 3485/105, 7475/101/7157) | GENUINE | UNVERIFIED alone |

- **Proof from the agent side**: patching only M2, only M3, or both in the agent's own program returns **0 points** in each case (2/66 → 2/66, regrade.txt `ag_*`). Every ledger-moving mistake is billed through every gated test, so no single fix gives points back.
- **Proof from the oracle side**: all three text-literal readings (M1-M3) together take the oracle to 8/66. Adding M4 and M5 leaves it at 8/66. After those five alignments, agent against oracle still differs on 1,682 of 23,011 common rows in granted (6,165 before), so M6, M7 and M10 are real.
- **Judge**: R1-R8 (40) were lost because the counterfactual figures inherit the ledger (e.g. R1 2628042/910 against 2628151/851): AMPLIFICATION. R17 (1) failed because the final message did not name the run or artifact behind each figure; R18 (1) failed because one run function was over 1000 lines. Both are CONDUCT. No JUDGE ERROR found: the justifications in score.json match the figures in the step 62 message.

Loss by class, in combined points (loss_table.md): **AMPLIFICATION 43.62** (tests 11.36 + judge 32.26), **HIDDEN RULE 32.58**, AMBIGUITY 2.27, GENUINE 2.27, CONDUCT 1.61; total 82.36 = 100 − 17.64. Each test is billed to one primary class, but most are double-caused (see M6/M7/M10).

### Did it read the saving line?
For M1-M3 the saving line does not exist: the agent read output_contract.md, state_machine.md and identity_rules.md at steps 5-8 and implemented them literally. For M8 it read source_declarations.properties at step 8 and the approval audit logs at step 22, but did not count the audit logs as AUT source rows. For M6 it read provenance_rules.md at step 5 and probed duplicates at steps 27-28. For M4 and M5 it read carry_forward_rules.md and commitment_rules.md at steps 6-7; the text supports its reading.

## Phase 5: design anatomy

1. **Instruction**: 6007 B, 11 lines (6 paragraphs). It points to a contract and states no rules itself: "read corpus_index.md first", "one doc withdrawn" (L1). It declares the hidden tier openly: "Your program will also be run against extracts of this corpus that nobody has seen, at other scales and with other declarations in force" (L3). It denies self-checks: "Nobody recorded how many records disagree with each other, so there is no count to check yourself against" (L5). It fixes the stage order and declares two absent rules: "Two rules are deliberately absent from the contract. The settlement logs settle them, and policy_audit.json is where you report the reading"; "A reading that fits only some of the observations is the wrong reading"; "apply each rule no more widely than it is written" (L7). It asks for eight counterfactual pairs in the final message (L9). It leaves out every count, every trap and every mention of the tests.
2. **Data**: 59 files, 11 MB, about 101k lines. 17 md rule docs, 19 csv, 8 jsonl, 4 tsv, 3 logs (+.1/.2 rotations), 2 ini, 2 fixed-width txt, 1 properties file (colon separators, backslash continuations, properties:6-9) and reason_codes.json. All ASCII; no xlsx, pdf or Latin-1. Decoy: legacy_runbook.md, "# Practice note, withdrawn" (corpus_index.md:21). Traps sit in the rule docs (status instant, carry, move_to, DST clock marks, errata over the rounding doc) and in data quirks (duplicate order-book quantity titles, continuation lines in the audit log, aliases, fixed-width gaps, fold disambiguation). The two absent rules are settled only by governance_observations.log and deficit_observations.log.
3. **Tests**: 27 (16 positive totalling 66: eight w5, eight w3, two w1; 9 negatives totalling −27). They grade whole populations by sha256 digest over 7 row views (test_output.py:113-179) against an 11.6 KB embedded key (:20). Hidden tier: two fixed extracts A and B at other scales, embedded as zlib tar (:22-23), plus variants: rotated rows (perm), renamed dir, deleted registry_q3.tsv (missing). The program runs from a temp room as `nobody` with `python -I`, PYTHONHASHSEED=0 and a 900 s timeout (:229-283). Weight on hidden extracts: alpha, beta and perm, 15/66. One concept (the ledger) touches 14 of 16 positive tests through digests and the gates at :464-616. Anti-hardcode negatives: int literals of shipped totals, embedded corpus rows, fixed corpus path, output independent of corpus, silent recovery from a missing source.
4. **Judge**: 29 criteria, positive 62, negative −27. R1-R8 (w5, 40 pts) target the user_facing_message with exact figures. R9-R13 (w3) and R14-R16 (w1) target the trajectory (conduct and reading of the evidence). R17 factuality, R18 code structure, R28-R29 name the evidence logs. Negatives R19-R27 cover figure mismatch, presenting the withdrawn practice as governing, claiming no run happened, ranges, opening the grading dir, illustrative values copied, a failing command repeated 3 times, and editing the corpus. Would the oracle pass? R1-R8 and R17 only if someone runs counterfactuals by hand (TRUTH.md:114 holds the reference message). R9-R16 cannot be shown by solve.sh, which leaves no trajectory, so they fail COMMON:49 / JD-7.
5. **Solution**: solve.py, 1722 lines (73 KB), stdlib, one pass per stage; runs in 5.2 s. Clock constants are hardcoded for 2031 (solve.py:179-230), while the agent derived them from the ini; both give identical capacities and cycle starts (probe: "diff starts 0 qualified 0 capacity 0").
6. **Robustness**: a second Opus run would almost surely score close to this one. Because of M1-M3, any text-literal solver is capped near 8/66 tests, and each ledger-moving yes/no reading (status instant, carry new lot, move_to) moves 53 test points at once. R1-R8 (40 judge pts) are all-or-nothing on an exact ledger. R9-R10 (6 pts) ride on the absent-rule readings, which Opus got right. Estimate: tests 0-13 % (2-8 of 66), judge 25-45 %, combined 12-28; for every run the score sits far below the 70 gate. One run only, so the spread is UNVERIFIED by data.

## Phase 6: what we take from it

| design choice | evidence (file:line, points) | kit check that allows it | our v3 templates | decision |
|---|---|---|---|---|
| Declare the hidden tier in the instruction ("extracts ... nobody has seen, at other scales and with other declarations in force") | instruction.md L3; alpha, beta, perm 15/66 | AL-13 answer-in-reach satisfied; TS-19 learnable | P2_build_v3.md:80 wants hidden inputs, seeded | **adopt** the wording; keep our seeded generator |
| Variant reruns of the delivered program: rotated rows, renamed dir, missing source file, non-root, `python -I`, own temp room | test_output.py:210-283; perm 5, negatives silent_recovery −3, fixed path −3 | AL-28 one act per negative; TS-29 guarded | P2_build_v3.md:82 G6 ≥ 2 mutation tests | **adopt** as concrete G6 recipes |
| Two rules deliberately left absent, each settled by an observation log, reported in an audit doc | instruction.md L7; governance/deficit logs; R9/R10 6 pts; Opus got both right (steps 11-12) | IN-8 (learnable from visible files) | _COMMON_RULES_v3.md:25 allows derive-from-data when data settles it and a test grades it | **adapt**: it is legal but did not discriminate; need more than one consistent reading per log |
| "No count to check yourself against" | instruction.md L5; agent self-checks only internal (steps 37-51) | none against | P2_build_v3.md:99 (no rule counts) agrees | **adopt** |
| Withdrawn decoy rule doc + negative for presenting it as governing | legacy_runbook.md:1, judge R20/R26; did not fire | AL-4 n/a | not forbidden | adapt (cheap, 0 points here) |
| Exact-figure judge criteria (counterfactual pairs) | judge R1-R8, 40 of 42 judge pts lost | JD-15 lets outcome criteria require figures; JD-7 only partly | forbidden: _COMMON_RULES_v3.md:48, P2_build_v3.md:91 J1, QC_FIX_PLAYBOOK_v2.md:29 | **avoid**; if the counterfactual idea is wanted, grade it as a program flag on a hidden extract |
| Tests gated on summary scalars / ledger_rows (whole-set cascade) | test_output.py:464,477,493,521,551,570,599,616; fixing any one agent mistake returns 0 points (ag_status, ag_stale) | no kit check on cascades (search of checks.json: none) | forbidden: P2_build_v3.md:81 G1/G2; QC_FIX_PLAYBOOK_v2.md:17 | **avoid** |
| Key that contradicts the written contract | output_contract.md:28-29, state_machine.md:9-12, identity_rules.md:39-43 vs solve.py:511/1129/1203; literal oracle 8/66 | AL-4 and TS-19 should fail it; no QC was run | _COMMON_RULES_v3.md:25 | **avoid**; add a literal-reading self-test |
| Trajectory conduct criteria the oracle cannot show | judge R9-R16 (18 pts kept) | JD-7 should flag | _COMMON_RULES_v3.md:49 forbids | avoid |
| Whole-population digests over row views (several views per row) | test_output.py:113-179 | TS-13 (each view is one property) | P2_build_v3.md:81 G1 one test per downstream doc | **adapt**: per-view digests are fine without the gates |

### Template edits (proposed, not made)
1. `P2_build_v3.md:83` (write the wrong implementation per lever): add "and, for every rule sentence the key depends on, write the **literal** reading and confirm the oracle scores 100 with it; a literal reading that loses points is an AL-4 fail." Evidence: the oc_status, oc_hops0 and oc_stale rows (8/66).
2. `P2_build_v3.md:82` G6: name the concrete mutation recipes: rows rotated, corpus dir renamed, one declared source deleted (must exit non-zero), run as non-root with `python -I` from a foreign temp dir. Evidence: test_output.py:210-283.
3. `P2_build_v3.md:101` / instruction template: add the two sentences "Your program will also be run against extracts of this corpus that nobody has seen, at other scales ..." and "there is no count to check yourself against". Evidence: instruction.md L3 and L5.
4. `P2_build_v3.md:81` G1: add the lint "no test may early-return False on a scalar from another document (e.g. summary totals)". Evidence: test_output.py:464-616; agent single fixes return 0 points.
5. `QC_FIX_PLAYBOOK_v2.md:29` (AL-2/CL-1 row): add "counterfactual figures requested in the final reply → move them to a `--override` run on a hidden extract graded by a test". Evidence: judge R1-R8, 40 pts.
6. `knowledge/KNOWLEDGE.md:6` (flow): note that peer acceptance came from 1 run with no QC report, about 2 h after the pass@1 commit (52a1e9f1), and that its low score is partly key/spec conflict, so do not calibrate our difficulty bar against it. Evidence: Phase 1, Verdict.

Earlier peer mining: none listed in the task block; nothing to agree or disagree with.

## UNVERIFIED
- The points M6, M7 and M10 cost on their own (no isolated injection built).
- Second-run spread (only 1 run exists).
- Whether the oracle would pass R1-R8/R17 (no LLM judge was run, by rule).
