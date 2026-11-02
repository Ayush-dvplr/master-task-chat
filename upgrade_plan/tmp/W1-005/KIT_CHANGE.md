KIT CHANGE REPORT, HELPER W1-005

Scope: the 2 QC kit files that changed between the user's 25 Oct 2026 snapshot (master_chat_tasks/knowledge/fingerprints/qc.json, kit git head 5574d77e) and the new kit on origin/main (commit 57c22748 'Latest imput Bundle QC', path Input_Bundle_QC/). Classification uses README 8b in upgrade_plan/README.md.

STEP 1. WHERE THE OLD VERSIONS CAME FROM

1. No stored copy of either old file exists. Searched: every file in the working tree (sha256 of every file over 10 KB and every file named like the kit files), every .md blob on origin/main, every commit in git log --all (the kit files appear in one commit only, 57c22748, which is the new kit), QC/ on origin/main (task copies and migration backups, no kit copy), master_chat_tasks/knowledge/fingerprints/archive_* (hash lists only, no file bodies), master_chat_work/20261024_process/qc_reverse (check inventories, not the files).
2. The old files were rebuilt exactly from numbered excerpts that Codex learning sessions printed with nl -ba while reading the live kit on 30 to 31 Oct 2026, when the kit was still at 5574d77e. Sources: master_chat_work/20261031_learning/L2_qc_kit_map/codex.log, L6_web_ideas/codex.log, L7_synthesis/codex.log, and master_chat_work/20261031_stage2_calib/cause_draft/codex.log. Every non blank line of both files is covered by at least one excerpt.
3. Method: take the new file; at every line number where an excerpt differs from the new text, put the excerpt text in. Only 4 lines of 05 and 5 lines of Final_checklist differ, each with a single consistent old variant.
4. Proof it is exact: the rebuilt 05_Alignment_Integrity_QC.md has sha256 5e81d67ceb873bfa0154e040dc0ed6ae12b6299e0713b80dfa5bdaba7ae79171, equal to qc.json. The rebuilt Final_checklist.md has sha256 aff7b002e7f6478262929be600825a77ccfef92996f6ffb3a7aa5c089bfd91f9, equal to qc.json. So these are byte exact copies of the 5574d77e versions, not a closest version.
5. New versions: git show origin/main:Input_Bundle_QC/<file>. sha256 05 = c3860c071fc4707b5d10232e5aaa0bd3ddf2b39ae3d111251532355660d22d5b (blob 458f53a215e67372fb3ffb097e6f8238c5fa8fbe); sha256 Final_checklist = 99a8b460b9cc190994151303e63a4b61ff27653eb6279140018a173642707ba6 (blob 35c07f8f07482025b09354c1bcb2ad3f883a0978).
6. Line counts are unchanged (128 and 523 lines). Every change sits inside an existing line; no line was added, removed or moved. So every record citation by line number (05:33, 05:38, FC:428, FC:491, FC:492 and so on) still points at the same item.
7. Lineage from the records, for context: archives 9b8229f6 (21 Oct), bfe40804, a74bda85, c9e3454a, f3765e67, 3fb1650b (22 Oct); decisions.jsonl line 119 records 71a653b2 to 976c1666 (no kit byte change); qc.json reconciled 976c1666 to 5574d77e on 25 Oct (7 md files changed). The current change is 5574d77e to the 57c22748 push.

STEP 2. EVERY CHANGE, OLD AGAINST NEW

Counts: 05_Alignment_Integrity_QC.md has 4 changed lines (4 changes: C1 to C4). Final_checklist.md has 5 changed lines (5 changes: C5 to C9). No rule was removed; no check id was added or removed. All changes add text except two short rewordings (AL-27 checklist 'stated' to 'graded'; CL-4 'Two' to 'Three') and the AL-27 report line.

C1. 05_Alignment_Integrity_QC.md line 33, check AL-2 (body text, gate 05 cross-walk): added sentences (leniency).
   1. ADDED TEXT: A set the delegation invokes uniformly is one promise, not one promise per member: where a single sentence binds forty key spellings, the promise is that the output conforms, and one check whose comparison spans all forty covers it, so ask whether the comparison really reaches the whole set rather than asking for a check per field. Enumerate a member on its own only where the prompt singles it out, or where it carries its own branch or edge case.

C2. 05_Alignment_Integrity_QC.md line 96, check AL-2 (checklist line): reworded checklist line (mirror of C1).
   1. OLD TEXT: - [ ] AL-2 every promise enumerated from `instruction.md` alone, delegating sentences expanded into the rules they invoke, each graded by a test or a criterion
   2. NEW TEXT: - [ ] AL-2 every promise enumerated from `instruction.md` alone, delegating sentences expanded into the rules they invoke, a uniformly bound set counting as one promise, each graded by a test or a criterion

C3. 05_Alignment_Integrity_QC.md line 38, check AL-27 (body text, trigger depth): added sentences (scope narrowed, inert rule carve out) and one reworded report instruction.
   1. ADDED TEXT: Scope this to rules the bundle actually grades or the prompt actually promises. A rule a shipped spec documents while nothing grades it and no graded input triggers it is inert rather than ungraded: the contract describes a general system and this corpus exercises part of it, which is the same spare detail AL-2 declines to count as a promise, and a solver scoring full marks while ignoring that rule is scoring correctly, because the rule never applied to the data it was given. The fail is for a rule something claims to grade, a check named after it or a criterion asserting it, where no fixture constructs the triggering case, because then the check is decoration and the reward cannot see the rule at all. Where the prompt itself singles out a rule no graded input triggers, report that the data does not support what the prompt emphasises rather than that the rule is ungraded.
   2. OLD TEXT: Fail; name the rule and the missing fixture.
   3. NEW TEXT: Fail; name the rule, the check that claims it, and the missing fixture.

C4. 05_Alignment_Integrity_QC.md line 101, check AL-27 (checklist line): reworded checklist line (mirror of C3).
   1. OLD TEXT: - [ ] AL-27 every stated rule has a fixture that actually triggers it (precedence pairs traced)
   2. NEW TEXT: - [ ] AL-27 every graded rule has a fixture that actually triggers it (precedence pairs traced; a rule only a shipped spec documents, that nothing grades, is inert)

C5. Final_checklist.md line 428, check Coverage, both directions (sign-off item 1; the AL-2 / AL-1 cross-walk in Final_checklist): added sentence (mirror of C1).
   1. ADDED TEXT: A set the delegation invokes uniformly is one promise rather than one per member: where a single sentence binds forty key spellings, the promise is that the output conforms, and one check whose comparison spans all forty covers it, so ask whether the comparison reaches the whole set rather than asking for a check per field, and enumerate a member on its own only where the prompt singles it out or where it carries its own branch or edge case.

C6. Final_checklist.md line 459, check Output format (all gates), Findings section: how a finding is labelled with a check id: added reporting rule.
   1. ADDED TEXT: the check id (one: the check that names the defect most precisely)
   2. ADDED TEXT: Several gates often describe the same condition from different angles; that is one finding under one id, not one finding per id, so do not list every check that would also have caught it.

C7. Final_checklist.md line 490, check CL-3 (graded answer is earned, not copied): added sentence (leniency: coincidence is not a copy).
   1. ADDED TEXT: Present means identifiable as the answer: a value the agent could only recognise as the answer by first doing the work is a coincidence rather than a copy, and small integers will collide across unrelated fields routinely, so if you cannot say how the agent would know which value to lift there is nothing here.

C8. Final_checklist.md line 491, check CL-4 (partial credit tracks partial correctness): reworded count and added exemption (leniency: genuine dependency cascade).
   1. OLD TEXT: Two things are not this defect.
   2. NEW TEXT: Three things are not this defect.
   3. ADDED TEXT: A fact that genuinely feeds the rest of the work costs what it costs: where an early value flows into every downstream artifact, getting it wrong really does leave the deliverable wrong in every one of those places, so charging for each is accurate measurement rather than a cliff. The discriminator is whether the output actually differs everywhere you charged. One wrong value that leaves the deliverable wrong in a single place while several weighted checks all re-read that same place is the double-charging this check exists for; a deliverable genuinely wrong in all of them is the curve doing its job, and that cost belongs to the dependency rather than to the grading.

C9. Final_checklist.md line 492, check CL-5 (no hidden conventions): added ground (leniency: a convention may be stated as a rule in a shipped file).
   1. OLD TEXT: Each of those must either be stated in the instruction, or be established by an example the agent is actually given in the copied input, or be compared in a way that does not care.
   2. NEW TEXT: Each of those must either be stated in the instruction, or be stated as a rule in a file the agent is given, or be established by an example the agent is actually given in the copied input, or be compared in a way that does not care.

STEP 3. CLASSIFICATION AND RECORDS TO UPDATE

Definition used (README 8b): MINOR = a leniency, or a lenient new rule, that does not affect how fixes map to QC checks, how hidden information stays hidden, or how traps stay hidden. MAJOR = anything that does affect those.

C1. AL-2 (body text, gate 05 cross-walk) (05_Alignment_Integrity_QC.md:33): MINOR.
   1. Reason: It lowers the coverage burden: a delegated set bound by one sentence (for example forty key spellings in schema.json) now counts as one promise that one whole-set comparison covers, instead of forty rows. A bundle that already grades each member still passes. The fix for an AL-2 finding is unchanged (grade the promise with a test or criterion); nothing about hidden information or trap concealment moves.
   2. Records: Optional, not blocking: P2_build_v5.md:101 (G11 'one row per AL-2 unit (each instruction.md promise plus each delegated rule it invokes, 05:33)') and LEVER_RULES_v3.md:173 (G11) may count a uniformly bound set as one row; QC_FIX_PLAYBOOK_v3.md AL-2 rows (lines 66, 78) may add a REBUT 'one comparison spans the whole uniformly bound set' quoting 05:33. Line 33 still holds AL-2, so all 05:33 citations stay valid.

C2. AL-2 (checklist line) (05_Alignment_Integrity_QC.md:96): MINOR.
   1. Reason: Same leniency as C1, written into the checklist item that reviewers copy verbatim into reports.
   2. Records: None beyond C1. Templates that copy the 05 checklist verbatim would pick it up from the live kit.

C3. AL-27 (body text, trigger depth) (05_Alignment_Integrity_QC.md:38): MINOR.
   1. Reason: It is a leniency: before, every rule a shipped spec documented could be failed for having no triggering fixture; now a documented rule that nothing grades and no graded input triggers is inert and passes. The existing fix (add a hidden triggering fixture, playbook row AL-27) still clears every AL-27 fail that remains. It does not require revealing anything: decoy or general rules in a shipped spec become safer, not riskier, so trap concealment is unaffected. The two wording changes only alter the finding text (name the claiming check; for a prompt-emphasised untriggered rule, report that the data does not support the emphasis). Caution: that last case is still under 'Fail', so a prompt that singles out a rule still needs a triggering fixture or a softer prompt.
   2. Records: QC_FIX_PLAYBOOK_v3.md row AL-27 (line 79 example and the AL-27 table row): add a REBUT 'inert: nothing grades it and no graded input triggers it' quoting 05:38, and add the de-emphasise option for the prompt-singled-out case. Optional: LEVER_RULES_v3.md:173 G11 and P2_build_v5.md:101 G11 could drop mutant rows for inert spec rules (keeping them is stricter and still passes). QC_RULINGS.md:131 (cohort AL-27 FAIL) stays valid because those rules were stated in the instruction (v3:44).

C4. AL-27 (checklist line) (05_Alignment_Integrity_QC.md:101): MINOR.
   1. Reason: 'stated rule' becomes 'graded rule' plus the inert carve out; same leniency as C3.
   2. Records: None beyond C3.

C5. Coverage, both directions (sign-off item 1; the AL-2 / AL-1 cross-walk in Final_checklist) (Final_checklist.md:428): MINOR.
   1. Reason: Same leniency as C1 in the Final_checklist copy of the coverage rule.
   2. Records: None beyond C1. LEVER_RULES_v3.md:36 quotes FC:428 'name either the sentence it enforces or the shipped fact it reads', which is still present at line 428.

C6. Output format (all gates), Findings section: how a finding is labelled with a check id (Final_checklist.md:459): MAJOR.
   1. Reason: It changes nothing a bundle must satisfy, but it changes how a QC finding arrives: one id per defect, the most precise one, instead of every overlapping id. The user's fix mapping is keyed on that id (QC_FIX_PLAYBOOK_v3.md line 7: every [[FIX_DIRECTIONS]] line cites a row id; line 75: one line per finding; line 78 even uses a combined id 'AL-2/CL-1'). A defect formerly reported as, for example, CL-5 and AL-3 now arrives under one of them only, so the master must find the fix under whichever id QC chose, and a defect can arrive under an id that has no playbook row. That is a change in how fixes map to QC checks, which is MAJOR by README 8b. It also creates an open conflict inside the kit: 05:13 (unchanged) still says 'when one fires, report it under its CL id too', which FC:459 now forbids.
   2. Records: QC_FIX_PLAYBOOK_v3.md section 2 (lines 73 to 79): add a rule that a finding carries one id, and that the master looks up the row for that id and for its overlap partners (05:13 list: AL-F0c, DS-21, TS-12, TS-27, AL-4 against CL-1 to CL-10); retire combined ids like 'AL-2/CL-1'. QC_RULINGS.md: new note on the 05:13 versus FC:459 conflict (ask QL which wins; queue in QL_QUESTIONS.md). P12_recheck_fix_v5.md line 9 and line 36 (one direction line per finding) and P11_full_qc_v3.md line 67 (report format comes from the kit) need no text change but any finding-count comparison against older reports (registry, LOSS_TABLE, qc_fail counts) must expect fewer duplicate findings.

C7. CL-3 (graded answer is earned, not copied) (Final_checklist.md:490): MINOR.
   1. Reason: It removes false positives: a graded value that also appears somewhere in shipped data only fails if the agent could tell it is the answer without doing the work. The user's stricter W11 'no visible answers' practice still passes. The fix for a real CL-3 fail is unchanged. Hidden answers stay hidden exactly as before; the change only stops QC from flagging accidental collisions.
   2. Records: QC_FIX_PLAYBOOK_v3.md CL-3 row: add a REBUT 'coincidence, not identifiable without the work' quoting FC:490. No line number moved.

C8. CL-4 (partial credit tracks partial correctness) (Final_checklist.md:491): MINOR.
   1. Reason: A new exemption: an early fact that really changes every downstream output may cost in each place. Existing CL-4 defences (the exact-match sentence exemption, FC:491 'An instruction that states out loud that only an exact match counts has set that bar deliberately', still present) keep working, and the existing fixes (partition, per-rule hidden tests) still clear any CL-4 fail. Nothing about hidden information or trap concealment changes; it only widens what QC accepts for cascades.
   2. Records: QC_FIX_PLAYBOOK_v3.md:55 (CL-4 row): add the dependency REBUT ('output differs everywhere charged', quoting FC:491) next to the exact-match REBUT; its FC:491 quote is still verbatim. LEVER_RULES_v3.md:73 (S7 digest cascade, rated RISKY for CL-4 exposure, 'Use S7 only with a CL-4 sentence' at line 95) and :161 (G1, 'A COUPLING quantity still multiplies a slip legitimately') can cite the new exemption; optional. P2_build_v5.md:97 cites FC:491 for the exact-match exemption, still valid.

C9. CL-5 (no hidden conventions) (Final_checklist.md:492): MINOR.
   1. Reason: A third ground: a silent requirement (order, keys, path form, casing) may now be stated as a rule in any file the agent is given, not only in instruction.md or by a shipped example. It matches the user's 25 Oct locus ruling (QC_RULINGS.md:10, instruction or any copied input file). It lets conventions live in a shipped spec instead of the prompt, which does not expose anything hidden. Existing fixes (state it, ship an example, compare insensitively) remain valid. Note: the 05 checklist line 89 for CL-5 ('either stated in the contract or compared insensitively') was not updated in this push, so the QL ruling at QC_RULINGS.md:41 (05:89 lacks the example option) is still open.
   2. Records: QC_RULINGS.md:41 and :65 and :24 (CL-5 AVOID/ruling text): add the new 'stated as a rule in a file the agent is given' option citing FC:492; keep the dispute note on 05:89. LEVER_RULES_v3.md:31 and :35 (FC:492 as example ground) may add the shipped rule-file ground. No line number moved.

STEP 4. OVERALL VERDICT

1. Overall: MAJOR, because of C6 only. The other 8 changes (C1 to C5, C7 to C9) are MINOR leniencies: each one lets more bundles pass, none adds a new fail condition for an existing bundle, every existing playbook fix still clears its check, and none touches how hidden information or traps stay hidden.
2. C6 is MAJOR by the letter of README 8b: it changes the id under which a QC defect is reported (one id, the most precise, instead of every overlapping id), and the user's fix mapping (QC_FIX_PLAYBOOK_v3 rows, [[FIX_DIRECTIONS]] lines) is keyed on that id. No bundle needs rework because of it; only the mapping step needs an update.
3. If the user reads 'how fixes map to QC checks' as 'which bundle change clears which defect' (not the label QC prints), C6 would also be MINOR and the whole update MINOR. This report keeps MAJOR because PLAN.md R_QC_UPSTREAM stops issuing on MAJOR until the mapping is updated, and the C6 mapping update is small (one playbook rule and one QC_RULINGS note).
4. No change affects hidden information or trap concealment. C3 (inert spec rules), C7 (coincidence is not a copy), C8 (dependency cascade) and C9 (rule stated in a shipped file) make hidden traps and decoys safer under QC, not riskier.
5. Open kit conflict to raise with QL: 05_Alignment_Integrity_QC.md:13 'when one fires, report it under its CL id too' against the new Final_checklist.md:459 'one finding under one id'. Also still open from before: 05:89 CL-5 checklist line does not carry the FC:492 example option (QC_RULINGS.md:41), and now not the new shipped rule file option either.

RECORDS TO UPDATE, ONE LIST

1. QC_FIX_PLAYBOOK_v3.md section 2 (lines 73 to 79): one id per finding, look up overlap partners, retire combined ids like 'AL-2/CL-1' (C6, required before issuing).
2. QC_RULINGS.md: new note on 05:13 versus FC:459 (C6); CL-5 lines 24, 41, 65 add the shipped rule file ground (C9).
3. QL_QUESTIONS.md (upgrade_plan): ask which wins, 05:13 or FC:459 (C6).
4. QC_FIX_PLAYBOOK_v3.md rows AL-27 (inert REBUT, C3), CL-3 (coincidence REBUT, C7), CL-4 line 55 (dependency REBUT, C8), AL-2 rows (uniform set REBUT, C1): optional, they add defences, existing fixes stay correct.
5. LEVER_RULES_v3.md :31, :35 (C9), :73, :95, :161 (C8), :173 (C1, C3); P2_build_v5.md:97 (still valid), :101 (C1, C3): optional.
6. Line number citations: none need an update. FC:491 quote in QC_FIX_PLAYBOOK_v3.md:55 and P2_build_v5.md:97 and FC:428 quote in LEVER_RULES_v3.md:36 are still verbatim in the new kit.
