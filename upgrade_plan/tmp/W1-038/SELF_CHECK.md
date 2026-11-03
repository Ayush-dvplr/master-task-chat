SELF CHECK for PL_QUESTIONS.md (W1-038, 3 Nov 2026)

1. Items present. All 33 items PL1 to PL33 are present once each, under the same 7 themes as the source checklist (A 8 items, B 2, C 5, D 6, E 3, F 5, G 4), each with Question, What this means, Example and What Ayush does today, and with Follow up questions in 32 of 33 (PL27 has none, as it needs none). The answer table at the end has 33 lines, PL1 to PL33. No item was dropped and no new topic was added.

2. Length. Each item is between about 100 and 225 words (counted by script); the whole file is about 6,250 words.

3. Internal ids. A grep for RIF, BR:, ENTRY, FIX_MAP, LEVER_RULES, settings, NOT_CARRIED, KWT, QR:, ANS:, FD:, pending, W1 numbers, QL1 and QL2, bare Q numbers (Q21, Q46 and so on), bare T, R and D numbers, J3 criterion names and S numbers returned 0 lines. Where the source cited one of these, the text says in plain words what Ayush does instead.

4. Names. No person's name and no email address appear (a grep for the at sign returned 0 lines). The reader is "you", the task author is "Ayush". "Opus 5" in PL24 is a model name, not a person.

5. Style. A grep for long dashes, a spaced hyphen, dash or star list markers, double stars and # headings returned 0 lines, and no contractions were found. Hyphens remain only inside fixed names such as build-repair, format-recovery and maximum-severity, which are quoted from the kit or the generator.

6. Kit quotes rechecked against the kit at origin/main (kit commit 57c22748), six picked at random from the 42 quotes checked by script (all 42 matched their cited line):
   a. 03_Tests_QC.md:62 "at most 35 (warn)": matches.
   b. 05_Alignment_Integrity_QC.md:13 "when one fires, report it under its CL id too": matches.
   c. Final_checklist.md:408 "the evidence in the sign-off must come from the final shipped version of the bundle": matches.
   d. 01_Instruction_QC.md:47 "If the input does not establish it, the sentence is the only ground": matches.
   e. 05_Alignment_Integrity_QC.md:38 "find the graded input with both conditions present and the assertion that the earlier one wins": matches.
   f. Final_checklist.md:491 "do not go looking for a percentage": matches.
   Generator quotes also checked: generate_bundle.py:1851 to 1852 set container_noun and producer_system to "", templates/build-repair/instruction.md:1 uses both placeholders, CATEGORIES.md:34 to 35, README.md:22 and README.md:113 to 115 match, and templates/ holds 8 folders.

7. Small differences noted. In PL11 and PL16 the kit writes instruction.md in code marks; the quotes drop the marks. In PL4 the quote "no fail findings" stands for the five gate lines Final_checklist.md:507 to 511, which each end with those words. 03_Tests_QC.md:135 holds both the fail list and the warn list on one line; "TS-23 cap above 35" sits in its warn part.
