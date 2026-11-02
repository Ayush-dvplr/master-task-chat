# VARIANCE: same text, different verdict (board ef7d851)

A case is listed only when the text the finding cites did not change between the two rounds, shown one of three ways:
**D** = `diff -ru QC/copies/<shaA>/<slug> QC/copies/<shaB>/<slug>` has no hunk at the cited line (copies survive);
**R** = the later reviewer says in its own "Compared with" section that the text is unchanged (copies pruned);
**F** = the fix record between the rounds lists the files it changed and the cited file is not among them.
Paths: reports are `QC/reports/<slug>/vN.md`; fix records are `master_chat_work/<date>_<slug>/<round>/RECHECK_FIX.md`.

Totals: 38 of 101 new findings (38%) are reviewer-variance (`cascades.json` cause = reviewer-variance). Of those, 30 are pass -> fire on unchanged text (A, B), 6 are counting changes (C). Section D adds 7 fire -> pass reversals on unchanged text (findings that "went away" with no edit, `fires.json` next_round_status = kept-accepted plus the two STEP10 rows). So 45 verdict flips in 42 reports had no bundle change behind them.

## A. Passed in round N, fired in round N+1, cited text byte-identical (proof D)

| task | id | round N verdict (quote) | round N+1 verdict (quote) | proof |
|---|---|---|---|---|
| dispatch | JD-7 | v4.md:215 "JD-7 ✅ R1-R5 literals equal the oracle golden" | v5.md:42 "R9 (solver code quality) is put at risk by dead stores in the oracle: `ctx.out_of_scope += 1` (solve.py:703)" | D: 3a23fca -> 2966bb2 changed only tests/judge.toml (R9 text unchanged; solve.py unchanged) |
| dispatch | DS-20 | v4.md:155 "DS-20 ✅ walked against handbook" | v5.md:50 "the oracle hard-codes the sentinel set at solve.py:21" | D: solve.py unchanged |
| district | AL-18 (x2) | v4.md:236 "AL-18 ✅ no stale counts (TRUTH 38 checks/113/-13 verified)" | v5.md:34 "the test module docstring states a stale extract count"; v5.md:36 "TRUTH.md claims no shipped file states a report figure, but export_manifest.tsv restates every `data_quality.json` `rows` count" | D: 53c71e3 -> 2fd95f2 diff has no hunk at test_output.py:8, TRUTH.md:103 or export_manifest.tsv |
| emberforge | DS-27 | v6.md:288 "DS-27 ✅ `TRUTH.md:3-227` describes defect, verification, root cause, solution and provenance digests without authoring/process attribution." | v7.md:35 "TRUTH.md carries process narration about earlier revision rounds and internal lever-catalogue codes"; v7.md:429 "not reported in v6" | D: d9fa93e -> 6ec5e57, cited TRUTH.md:14 not in a hunk |
| emberforge | JD-18 | v6.md:367 "JD-18 ✅ R4 (`judge.toml:53`) assesses typed and reported exception handling in authored Python code." | v7.md:45 "R4 ... is met trivially by any program with no `except` clause, including an empty file." | D: judge.toml:53 not in a hunk |
| match | TS-20 | v1.md:174 "TS-20 ✅ weights 7x1 shipped-instance + 30x5 general" | v2.md:54 "record_derivation_matches carries weight 1 although the record is a named deliverable" | D: `criteria.record_derivation_matches(weight=1)` in ebf2870 test_output.py:2693 and fba1605 :2782 |
| match | IN-L2 | v1.md:103 "IN-L2 ✅ grammar and spelling clean" | v2.md:58 "Compound modifiers written open." | D: 'turn based', 'space saving', 'read only for this run' each present once in both instruction.md copies |
| schema | TS-14 | v6.md:169 "TS-14 ✅ names state properties" | v7.md:45 "four check descriptions understate what their bodies test"; v7.md:443 "say \"lists only\" while the body also requires completeness" | D: e50ca11 -> 8f891ea changed TRUTH, judge, reward only; test_output.py:9666 unchanged |
| sensor | DS-27 | v1.md:182 "DS-27 ✅ TRUTH.md describes the task; provenance block has ids/hashes only" | v2.md:405 "\"the round's levers\" is authoring-round process vocabulary" | D: 84dd742 -> c3824bc, TRUTH.md:15-16 not in a hunk |
| sentinel | TS-26 (warn) | v1.md:213 "TS-26 ✅ no pair pays twice: hidden policy / curve / trace / config rebuild grade different documents" | v2.md:44 "hidden_config_document_rebuilt_by_cli_matches (weight 5) feeds `set` from the delivered policy_resolved.json" | D: 8e66159 -> 1d97a1e, test_output.py:515-527 not in a hunk |
| sentinel | JD-2 | v1.md:244 "JD-2 ✅ no banned token (R10 \"has no except clause\" is a positive-weight absence; no listed token)" | v2.md:45 "R10 is a positive (+1) phrased as an absence" | D: judge.toml:129-131 identical. Same observation, opposite verdict. |
| sentinel | IN-2 | v1.md:115 "IN-2 ✅ ... instruction.md:5 \"graded whole against the authoritative policy of that corpus\" states what is judged, not how" | v2.md:47 "instruction.md:5 \"Your delivered `/app/out/tool.zip` is extracted and its `resolve` subcommand is run ..." | D: instruction.md:5 not in a hunk |
| sentinel | STEP11 | v1 Step 11 did not list resolution_order | v2.md:432 "Step 11 resolution_order ungraded" | D: instruction.md:7 not in a hunk |
| sentinel | JD-11 | v2.md:232 "JD-11 ✅ negatives hit the real cheat surface: ... R3 tampering with inputs" | v3.md:39 "R3 (-3) penalises changing /app/data, which uid 1000 cannot do in this image." | D: 1d97a1e -> f06feb3, judge.toml:40 not in a hunk |
| vendor | DS-24 | v5.md:247 "DS-24 ✅ own names and structure ... tests_qc O1 overlap 10%" | v6.md:42 "The oracle is a renamed line-by-line paraphrase of the verifier's reference codec" | D: bddf20b -> 9bc33e6 changed capture_catalog.jsonl, judge.toml, test_output.py; solve.py:193-229 unchanged |
| vendor | TS-17 | v5.md:287 "TS-17 ✅ `_diff` demands exact int/bool/None types and list lengths" | v6.md:43 "Six positive checks compare decoded values with plain `==`" | D: test_output.py:1986 not in a hunk. Direct contradiction about the same comparator. |
| vendor | JD-6 | v5.md:314 "JD-6 ✅ all decidable from trajectory/final answer/the two program files" | v6.md:44 "R1's machine key says count unit while its description asks for a non-count unit" | D: judge.toml:13 not in a hunk |

## B. Same, but proof R or F (copies pruned)

| task | id | round N | round N+1 | proof |
|---|---|---|---|---|
| cohort | IN-16 | v3.md:122 "Unspecified tie (two merge rows with equal effective_from for one account ...) ... never generated ... so no graded turn; no finding." | v4.md:35 "leaves two rows with the same `effective_from` open; the generator never makes such a pair" | F: p12_r2 changed solve.py, TRUTH, instruction, tests, not schema.md. Same reasoning, opposite verdict. |
| dispatch | AL-28 | v1 gate 05 pass | v2.md:398 "input-dir write costs -3 test + -3 R8 = 6" | F: 20261022 p12_r2:14 "Latent under root grading"; cited test_output.py:16295-16318 not in v1->v2 hunks |
| emberforge | AL-27 | v2.md:368 "- [x] AL-27 every stated rule has a triggering fixture ✅" | v3.md:406 "A4 at-cap and A2 first-day / last-day equality boundaries triggered by no graded input" | F (UNVERIFIED): 20261022 p12_r1:11-17 rows touch AL-2, TS-19, JD-6, W-03, W-01, JD-16 only |
| emberforge | DS-20 | v3.md:172 "DS-20 ✅ walked every rulebook rule pairwise against solve.py" | v4.md:376 "solve.py:824-826 overwrites workshop `allocated_units` ... (v3 gate 02 passed this)" | F: 20261022 p12_r2:9-10 changed tests/test_output.py and TRUTH.md only |
| schema | IN-16, AL-27, DS-15, CL-5 (v3) | v2 passed | v3.md:353 "IN-16 float cast of padded decimal strings ... AL-27 M5 boolean rule untriggered ... DS-15 ... CL-5/AL-4 completed_steps 0 convention" | F (UNVERIFIED): 20261022 p12_r1 did not touch migration_semantics.md or repository_contract.md |
| schema | IN-16/CL-5 (v5) | v4 passed | v5.md:38 module reports' unstated meaning of "changed" | D: 20508e3 copy vs d3c6a83, repository_contract.md:130-132 not in a hunk (latent since p12_r2:13 made "changed" graded) |
| vendor | TS-26, AL-28, TS-16 (v3) | v2 listed the five negatives without these faults | v3.md:412-413 negatives stack -6 / cannot fire | F (UNVERIFIED): p12_r1 rows :9-16 added no negative |
| vendor | DS-4 | v3.md:134 "DS-4 ✅ grep for the judged answers ... found nothing" | v4.md:37 "the catalog's capture ids label exactly which captures are rejected" | F: 20261022 p12_r2:15 "Weights, reward.toml, judge.toml, instruction.md, task.toml, environment/ unchanged" |
| vendor | JD-15, DS-6 (v5) | v4 passed | v5.md:447 "JD-15-1 🟡 (R5 labelled \"task completion\"); DS-6-1 🟡" | UNVERIFIED (harden_lp1_r1 52dbb3c between, copies pruned) |

## C. Counting variance (same finding, counted or not)

| task | id | round N | round N+1 |
|---|---|---|---|
| dispatch | X1 | v2.md:393 "informational (not counted in v2)" | v3 counts it as a warn (v3.md:43) |
| dispatch | STEP10/EXEC-5 | v2 process row | v3.md:44 warn; then v4.md:409 "carried as ⏸️ in the sign-off, not counted as a finding" |
| emberforge | STEP10 | not counted in v5 | v6.md:52 warn (UNVERIFIED which row) |
| sentinel | X1 | v1 "not counted in v1 totals" | v2.md:426 "8 binary files skipped (present in v1, not counted in v1 totals)" counted |
| vendor | X1 | v4 "verified false positive pass" | v5.md:447 "X1 ⚠️ kept as a warn" ; v6.md:405 "verified false positive with no count" |

X1 alone flipped counted/uncounted 6 times over 4 tasks. The structure_qc.py rule never changed (`structure_qc.py:71` "X1  no em/en dash in any text file; binary-skipped files warn.").

## D. Fired in round N, passed in N+1, text unchanged (reviewer reversal)

| task | id | round N | round N+1 |
|---|---|---|---|
| sensor | DS-6 | v1.md:42 "🟡 DS-6 ... header claims an \"EXACT two-sided acceptance interval\"" | v2.md:401 "chi_square_bounds_table.csv is unchanged ... This round I judged it a declared data convention" |
| sentinel | JD-16 | v1.md:48 "R4 grades a rule a test could check (/app/out listing) and no test does" | v2.md:421 "closed on re-judgement, the verifier receives only the seven declared artifacts" |
| sentinel | TS-20 | v2.md:41 "🟡 minor ... the main configuration ... paid on" | v3.md:468 "bundle weights unchanged (test_output.py:779-790); v3 re-judged it ✅" |
| dispatch | AL-28 | v4.md:50 "⚠️ ... fires `negative_writes_outside_output_dir` (-3 ...) and judge R8 (-3" | v5.md:383 "v5 rated AL-28 ✅ because the test fires on the grader-staged run and R8 on the agent's own session act; a reviewer who treats them as one act would keep the v4 warn." |
| emberforge | IN-L3 | v2.md:49 "heading fragments run into prose" | v3.md:400 "text unchanged; v3 gate 01 did not raise it" |
| schema | DS-20 | v1.md:52 "the M5 decimal edge case \".5\"" | v2.md:721 "unchanged; v2 did not re-raise it as a finding" |

## What drives the variance

1. Absence-shaped judge criteria and "is this a cheat surface" calls flip most (JD-2, JD-11, JD-18, AL-28): the observation is identical, the ruling differs (sentinel v1.md:244 vs v2.md:45 name the same fact).
2. Gate 02 deep walks (DS-20, DS-24, DS-27, AL-27) find new things on a second read of an unchanged oracle or TRUTH.md; a pass in round N is not evidence the file is clean.
3. Counting rules for X1 and STEP10 are not fixed in the kit text; each reviewer decides whether a process row counts.
4. dispatch v5.md:383 states the rule outright: "a reviewer who treats them as one act would keep the v4 warn."

## E. Within-round self-corrections (the same reviewer, the same bytes, two verdicts in one report)

- schema v7.md:439 "TS-13 🟡: tests/test_output.py:9792 still asserts receipt mismatches and null fingerprints together. (My first v7 pass missed it; corrected in Gate 03 after re-reading the bytes.)"
- schema v7.md:441 "TS-15 ⚠️ ... still has no inline inversion comment. (My first v7 pass missed it; corrected in Gate 03.)"
- vendor v6.md:400 "DS-20-1 ...: STILL OPEN ... My first v6 pass missed it; re-opened and counted in v6."; v6.md:402 DS-6-1 same; v6.md:410 "Comparing with the previous version caught two still-open minors (DS-6-1, DS-20-1) that my own first pass skipped"
- emberforge v5.md:377 "I passed it in my first gate 04 pass and revised it to warn after re-reading 04_Judge_QC.md:97 during this compare"

So a first pass misses some still-open items, and the "Compared with" step puts them back. A finding missing from a report's first pass is weak evidence that it was fixed.
