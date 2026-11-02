# RECHECK_FIX sentinel-policy-recompute (P12 r1, board aa5e389)

QC report: `/Users/mac/Desktop/Terminal Bench/QC/reports/sentinel-policy-recompute/v1.md` (kit 71a653b2; live kit HEAD 71a653b23fc2, same, no rule change). Bundle tree at start e0ef9c52a757.

Status: PAUSED. Thirteen of fourteen rows are settled (12 fixed, 1 kept). G03-1 and G03-3 (the shipped-artifact split) are PAUSED under playbook 3.4: two measured tries both fail trap survival (details below). The merged shipped check stays at weight 1 until the master rules.

Levers (LEVERS.md): L1 ledger controls, L2 rev 1 seconds, L3 allowance, L7 per-term risk rounding, C = carried-over levers (half-open window, version gate, B9 vs B7, client v205, seconds base, tier index, convergence).

## Findings

| ID | label | rule quote (live kit file:line) | evidence (file:line) | decision | playbook row | effect per lever | compensation | files changed |
|---|---|---|---|---|---|---|---|---|
| G02-1 DS-27 | REAL | 02_Data_Solution_QC.md:80 "TRUTH.md describes the task, not how the task was made. ... What does not belong is any narrative of the production process" | solution/TRUTH.md:46-47 "The worked example that used to sit in this file was removed."; :56-57 "Repair faults carried over from the original task (each now stated once ...)" | FIX as directed: sentence deleted; line now "Repair faults, each stated in the file that governs its data:". Sweep of TRUTH, instruction, judge, task.toml, test docstrings, data: other hits are ordering words ("passes earlier", R13 "earlier seq"), a Python fact ("removed in Python 3.12"), data ids (OV-K042-old, WIN-OLD): kept | DS-27 (rewrite TRUTH) | all none | none | solution/TRUTH.md |
| G03-1 TS-20 | REAL | 03_Tests_QC.md:51 "5 = a core outcome ... 1 = a minor detail or existence check ... a core-deliverable test carrying weight 1 ... is wrong" | tests/test_output.py shipped_artifacts_follow_field_specs registered weight 1; it is the only check on the shipped config.json | PAUSED (playbook 3.4): split measured twice, both fail trap survival; merged w1 check kept. The core config property is graded at 5 on hidden-a/b/c by hidden_config_document_rebuilt_by_cli_matches | TS-20 / TS-13 | split would make L1, L3, C (inclusive window) easier (measured, table below); merged: none | tried shipped weights down to 1 (try 2); still FAIL | none (reverted) |
| G03-3 TS-13 | REAL | 03_Tests_QC.md:44 "One property per test. A test asserting two unrelated properties hides which one failed and skews the weight; flag it." | test_output.py shipped check asserts presence, canonical form, forbidden keys, config, report, profiles, validation_report, summary, tool.zip layout and the config rebuild | PAUSED with G03-1 (same split) | TS-13 | as G03-1 | as G03-1 | none (reverted) |
| G03-2 TS-19 | REAL | 03_Tests_QC.md:50 TS-19 (every graded behaviour learnable; no contract/test contradiction) | old rerun check: `resolved("hidden-a")` and `run_resolve("hidden-a")` each built a fresh mkdtemp corpus, docstring said "same reseeded hidden corpus"; resolution_order (paths) differed | FIX as directed: corpus built once (`write_corpus`), resolve run twice on that dir into two fresh out dirs; first run must equal the hidden-a reference (policy_resolved and threshold_curve whole, trace on TRACE_GRADED_KEYS, assert_document), then byte identity and canonical form. Docstring updated. output_field_spec.txt untouched | TS-19 | L2, L3, L7, C harder (rerun now fails every variant wrong on hidden-a); L1 none | none | WORK/test_body.py, tests/test_output.py (regenerated), TRUTH.md |
| G04-1 JD-15 | REAL | 04_Judge_QC.md:92 "What a criterion may require, and where that requirement comes from." (constraint label needs an instruction sentence; QC_RULINGS JD-15) | judge.toml R7 type "instruction following"; no instruction sentence asks to edit cli.py computation | FIX: R7 type "agent behavior" | JD-15 (re-label) | all none | none | tests/judge.toml |
| G01-1 IN-L2 | REAL (minor) | 01_Instruction_QC.md:68 "IN-L2 grammar and spelling clean" | instruction.md:1 run-on "... and a request corpus, and several of those files are superseded ..." | FIX as directed: split into two sentences; nothing else changed. Suggestion test: one sentence per clause, read aloud | IN-L2 | all none | none | instruction.md |
| G01-2 IN-16 | REAL (minor) | 01_Instruction_QC.md:46 "No significant ambiguity in anything that is graded." | override_precedence.conf "match_version = effective version from policy_version_map" (row or window?); tests require both; solve.py checked only window version | FIX: conf line 4 now "match_version = the override row and the window containing effective_instant both carry the effective version from policy_version_map" (gen_data.py source line changed to the same text; gen_data not rerun, pyarrow differs); oracle checks row version too (`row-version-` reason). Oracle bytes identical on shipped and hidden-a/b/c (9/9 docs) | IN-16 (settling clause in governing file) | L1 none, L2 none, L3 none, L7 none, C none (no hidden row has a row/window version mismatch inside a containing window) | none | environment/data/override_precedence.conf, WORK/gen_data.py, solution/solve.py, tests/test_output.py (re-embedded corpus) |
| G02-2 DS-22 | REAL (minor) | 02_Data_Solution_QC.md:78 "TRUTH.md describes the bundle that actually shipped." | TRUTH.md:87 "616 lines" vs wc -l 672 | FIX: wc -l run last after every solve.py edit: 674; counts 12 checks / 31 / -11, 0.5/31, 0.5/37 and sha256 of solve.py and test_output.py rechecked and updated | DS-22 (rewrite TRUTH) | all none | none | solution/TRUTH.md |
| G02-3 DS-20 | REAL (minor) | 02_Data_Solution_QC.md:68 "The oracle obeys the contract, independently of the tests." | output_field_spec.txt:16 "client_version_ignored (true when the client-claimed version was not used)"; solve.py:347 `client_claimed_version != version` | FIX: `"client_version_ignored": True,`. Oracle bytes unchanged (shipped claim v205 differs, so it was already true) | DS-20 (fix oracle) | all none | none | solution/solve.py |
| G04-2 JD-5 | REAL (minor) | 04_Judge_QC.md:71 "Each criterion names ONE observable behaviour ... a borderline case (two facets of one act) is a minor." | R7 joined four computations | FIX: R7 is not a J2 conduct criterion (DESIGN.md: J2 = R12-R15), so reworded to "The agent edits the code in /app/tool/cli.py that computes the resolved policy values." type "agent behavior", weight 5 | JD-5 | all none | none | tests/judge.toml |
| G04-3 JD-16 | KEPT (warn) | 04_Judge_QC.md:93 "What makes a valid constraint criterion. All four must hold" | judge.toml R4 "writes a file under /app/out other than the seven declared artifacts" | KEEP (Ayush approved); not edited | SUGGEST (KEEP) | all none | none | none |
| G04-4 JD-11 | REAL (warn) | 04_Judge_QC.md:88 "Negative-weight criteria should cover the real cheat surface of THIS task ... Generic negatives ... that cannot occur here are residue" | R3 package install and R8 outside retrieval cannot occur under network_mode "no-network" | FIX: R3 (-3) "The agent modifies, deletes, or replaces a file under /app/data." as directed. R8 (-5) DEVIATION: "The agent passes the set command a value for /app/out/config.json that differs from the value its repaired resolve printed for that key in the same run." Both type "agent behavior", target "trajectory" | JD-11 / row NEW (cheat choice) | all none | none | tests/judge.toml, TRUTH.md, QC_DEFENCE.md |
| G05-1 CL-5 | REAL | 05_Alignment_Integrity_QC.md:78 CL-5 (every exact comparison's silent requirements stated or compared insensitively) | same root as G03-2: byte identity across two corpus dirs required equal paths | FIX with G03-2 (one corpus dir) | TS-19 shared | as G03-2 | none | as G03-2 |
| G05-2 CL-2 | REAL (warn) | 05_Alignment_Integrity_QC.md:75 CL-2 (price of the cheapest non-solving tool) | rerun paid 1 to a constant `{"a": 1}` resolve; price 4/31 | FIX with G03-2: rerun now reference-first. Rerun of CL-2: constant tool scores 3/31 (validate only; rerun fails "hidden-a policy_resolved.json: $.a unexpected"), was 4/31 | TS-19 shared | as G03-2 | none | as G03-2 |

Counts: REAL 13, FALSE_POSITIVE 0, UNSURE 0, KEPT 1 (G04-3). Fixed 11 (G02-1, G03-2, G04-1, G01-1, G01-2, G02-2, G02-3, G04-2, G04-4, G05-1, G05-2). PAUSED 2 (G03-1, G03-3).

## Deviations from master directions

1. G03-1/G03-3 split. Master weights config 3, profiles 2, validation_report 2, report 1, summary 1, tool.zip 1 (P 40) are not legal: tests_qc.py:154 `ALLOWED_WEIGHTS = {5, 3, 1, -1, -3, -5}`. Legal forms measured on the fixed tests:
   - try 1, weights 3,1,1,1,1,1 (P 38): reflex 11/38 = 0.2895 (FAIL, gate 0.20); controls lever ratio 0.816, no allowance 0.851, per principal 0.851, first-only 0.857, raw timeout 0.870, abs(v) 0.870 (all FAIL, gate 0.90).
   - try 2, all weights 1 (P 36): reflex 9/36 = 0.2500 (FAIL); controls 0.861, no allowance 0.899, per principal 0.899, inclusive window 0.893 (FAIL).
   - Bound: reflex passes validate 3 plus every shipped check, so (3 + S)/(30 + S) <= 0.20 needs S <= 3.75; the controls lever needs S <= 4.4. Six one-property checks cannot fit at any legal weight, and two or more shipped-only checks also break G3 shipped-only <= 5% (2/32 = 6.25%). Per playbook 3.4 (two tries) the split is stopped: `PAUSED: trap reflex 0.1613 -> 0.2500 (best try), L1 controls 0.161 -> 0.139`. Merged w1 check restored; other fixes kept.
   - Options for the master: (a) accept the merged w1 check with a TS-13/TS-20 defence (core config graded at 5 on hidden data; shipped check is presentation of the shipped instance); (b) split into at most three w1 checks and accept a G3 shipped-only breach (3/33 = 9.1%) with reflex 7/33 = 0.212 (still above 0.20), so (b) also needs a new hidden case; (c) move shipped config/profiles grading onto hidden-corpus rebuilds instead of shipped files.
2. G04-4 R8. Master text "writes an artifact under /app/out with a hand-written command (a heredoc, echo, or inline json.dump) instead of producing it with the repaired tool" fails JD-7 and AL-28: the oracle writes summary.json and validation_report.json with `json.dumps` in solve.py (dump_json, used at :639 and :660) because the tool has no subcommand for them, so the criterion would fire on the oracle; hand-writing config.json or profiles is the mirror of positives R2 and R11; hand-writing report.json is the forged-transcript act already priced by negative_transcript_disagrees_with_config (-3), stacking to -8. Replacement is reachable offline, the oracle avoids it (solve.py:611-619 sets `str(resolved[key])` from the resolve stdout of the same run), and no test or criterion grades it.
3. R3 note: instruction does not forbid editing /app/data; R3 is graded as conduct ("agent behavior"), not as an instruction constraint, so JD-15 holds. No instruction change (out of scope).

## Gate results

- xref_check: 20 entries, 0 findings (start: 16 entries, 0 findings).
- QC scripts (live kit, OUT/qc_*.txt): structure 17 pass 1 warn (X1 binary skip, same false positive as v1) 0 fail; instruction 5/0/0; tests 37/0/0; judge 19/0/0 (15 criteria, positive 37, negative 16). Exit 0 each.
- Manual: DS-27 grep clean (only ordering words, Python fact, data ids); TS-19/CL-5 rerun on one corpus dir, reference first; CL-2 constant tool 3/31; JD-5/11/15 on R3, R7, R8 (one observable each, all "agent behavior", R3/R8 avoided by solve.sh); IN-L2 split; IN-16 conf names row and window; DS-20 True; DS-22 674 lines.
- Oracle bytes: shipped artifacts identical except report.json local paths and tool.zip (cli.py changed by design); shipped and hidden-a/b/c resolve documents 9/9 identical.
- Stacking: OUT/STACKING_CHECK.md, STACKING PASS.
- Docker (tests-only, exe_copy copies plain and --owner-only): see result JSON and PL_NOTE.md.

## Agent program (harden_r1, build replay)

Before 0.1613 (5/31: validate 3, rerun 1, shipped 1). After 0.1290 (4/31: validate 3, shipped 1; rerun now fails on the reference).

## Trap survival

Final bundle (merged shipped check, P 31). Loss of P = (P - earned) / P.

| variant | before loss of P | after loss of P | ratio | separating cases kept | verdict |
|---|---|---|---|---|---|
| first-only | 0.645 | 0.677 | 1.05 | y | PASS |
| no allowance | 0.742 | 0.774 | 1.04 | y | PASS |
| allowance per principal | 0.742 | 0.774 | 1.04 | y | PASS |
| raw timeout | 0.484 | 0.516 | 1.07 | y | PASS |
| abs(v) < 100 heuristic | 0.484 | 0.516 | 1.07 | y | PASS |
| sum rounding | 0.258 | 0.290 | 1.12 | y | PASS |
| controls never recomputed | 0.161 | 0.161 | 1.00 | y | PASS |
| inclusive window end | 0.871 | 0.903 | 1.04 | y | PASS |
| agent program (score) | 0.1613 | 0.1290 | n/a | n/a | PASS (<= 0.20) |

nop share of P: 0/31 before, 0/31 after. Stub (empty artifacts, empty tool.zip): 0/31 before, 0/31 after. No hidden case removed. The split tries (Deviations 1) are the FAIL measurements.

## QC_RULINGS rows

- G02-1 DS-27: TRUTH describes the task only; our design carried production history; QC FAIL; REAL; history sentences removed.
- G03-1 TS-20: core never weight 1; our design graded shipped config inside a w1 group, core config at 5 on hidden; QC FAIL; REAL; split breaks trap survival, PAUSED.
- G03-3 TS-13: one property per test; our design used one shipped-artifact check; QC MINOR; REAL; PAUSED with G03-1.
- G03-2 TS-19: docstring promise and test must agree; our rerun used two corpus dirs; QC FAIL; REAL; one corpus dir, reference first.
- G04-1 JD-15: constraint label needs an instruction sentence; R7 labelled instruction following; QC FAIL; REAL; relabelled agent behavior.
- G01-1 IN-L2: grammar clean; one run-on sentence; QC MINOR; REAL; split.
- G01-2 IN-16: one reading for graded rules; conf did not say row version; QC MINOR; REAL; conf and oracle state both.
- G02-2 DS-22: TRUTH matches shipped bundle; stale line count; QC MINOR; REAL; recounted last.
- G02-3 DS-20: oracle obeys contract on its own; computed flag instead of spec value; QC MINOR; REAL; constant True.
- G04-2 JD-5: one observable per criterion; R7 listed four computations; QC MINOR; REAL; one observable.
- G04-3 JD-16: constraint criterion validity; R4 undeclared out file; QC WARN; KEPT (Ayush approved).
- G04-4 JD-11: negatives cover this task's cheat surface; R3/R8 unreachable offline; QC WARN; REAL; R3 data edit, R8 set value not printed by resolve.
- G05-1 CL-5: silent requirements of exact comparisons; rerun byte compare across corpus dirs; QC FAIL; REAL; fixed with G03-2.
- G05-2 CL-2: forgery price; constant resolve earned rerun point; QC WARN; REAL; price now 3/31.

## Lessons for the master

- A split direction should be checked against the reflex bound first: (isolated + shipped) / P <= 0.20 caps total shipped weight at about 3.75 here.
- Weight 2 is not in tests_qc.py ALLOWED_WEIGHTS; directions should use 1, 3 or 5.
- "Hand-written artifact" negatives collide with oracles that write report files the tool cannot produce; check solve.py before wording.
- Rerun checks should be reference-first by default; it fixes TS-19, CL-5 and CL-2 in one move.
- harbor run needs `-y --env docker` in nohup chains or it aborts at the env prompt.
