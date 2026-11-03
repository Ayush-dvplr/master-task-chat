CARD SUMMARY (3 Nov 2026; master, from the 55 light cards plus 3 pilot cards; verdicts as written by the helpers, each batch spot checked)

TALLY (58 cards): DESIGN 30, DEFECT 20, MIXED 8. Plus 10 tasks studied on 2 Nov (master_chat_work/20261102_test_design_study/deep2). Total 68 of 108 teammate tasks studied.

DESIGN FAMILIES (what makes Opus lose points in a solvable task)
D1. A documented case that only the hidden data triggers (kind b): 8eae0f87 clock resets, 4da82574 a rule split across a doc line, 6285fcad, 9d1784a5, ceadc676, b42c61b9 (held out corpora with cases the sample never shows), 7e0d8feb (one unfired branch).
D2. Format or encoding variation inside a named standard (kind a): f348165e (OOXML, PDF), 43986de8 (WordprocessingML), e08c051f (quoted integers the schema forbids), ceadc676.
D3. A documented rule misread or over applied, feeding an exact gate (kind d): df8f123b, 4a5f9738, b6237098 (newer normative note over older spec), d4e8c327, f5fe93be, 7c2e77a1, 9cc598a9, 9125255a, 71a3ecf5.
D4. A stated runtime on a large hidden input (kind c): fd7a2544, f5fe93be.
D5. One detail buried in a very large document (kind e): 43249294.
D6. Many interacting seeded faults with layered gates (kind e): cd6a3a55.
D7. FLAGGED for review: unwritten constants or bit meanings that only examples or digests confirm (kind e): 8defd7be, 28a29cf0, 816cdd80, 4a9d67f2, 2b00e081, d7ab7d6c. Open question in each: do the shipped examples pin a single answer?

DEFECT FAMILIES (recorded for case by case review; G2)
F1. The docs contradict the reference: 6d12f970 and 91f5740c (net definition), 9f5486ac (cluster id), 98ed74c1 (clock offset), b51a883e (errata).
F2. A rule stated nowhere in the shipped files: 3f39299a, b625f36e, 4ee62df1 and 9e96e588 (which journal entries feed the base), d7898e6d and eab391b0 (mode bits).
F3. Graded names, ids, fields or case the contract never fixes: 8956ff8b, 75407a55, 9bb234eb, fa7c65bd, 80877080.
F4. Amended field type left open: 058cbab3, 88ee425d, af780bef (decided: CR6, allowed only with one doc sentence).
F5. Situations the instruction itself calls unsettled, graded against one fixed answer: 11750b7a, 4ef4340d.
F6. Environment: cf9b2067 (agent program unreadable for the grader user).

SHARED DESIGN SHAPE (many tasks, both families)
1. A seeded generator inside tests/test_output.py makes several held out corpora.
2. A full core gate: every core report must be exact on the shipped data AND every held out corpus before leaf checks score.
3. Amplification: one hash or whole document compare per bundle, so one small miss fails many checks.
4. Rubric: rewards self tests on changed inputs, independent checks, and one concrete worked example (often not asked for by the instruction, Q105 and Q106).

COST: light cards about 35k to 58k tokens each (about 175k per batch of 4).
