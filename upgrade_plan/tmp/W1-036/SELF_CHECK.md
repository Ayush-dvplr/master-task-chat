SELF CHECK (W1-036, 3 Nov 2026)

Method. 38 cites from PL_CHECKLIST.md were put in a list and 8 were drawn by Python random.sample with seed 36. Each line was opened again fresh (kit lines with git show origin/main:Input_Bundle_QC/<file>, our rules with sed on the draft file) and compared with what the checklist says.

1. RIF:11 (used in PL3). Line reads "CAPS (R15): no round caps (issue.py warns, never refuses); tests and rubric criteria each at least the QC minimum, soft 70, hard 100." Matches "our soft cap 70 and hard cap 100". CONFIRMED.
2. 03:62 TS-23 (used in PL3). Line reads "at least 10 checks (fail), at most 35 (warn)". Matches the quote. CONFIRMED.
3. 01:32 IN-2 (used in PL20). Line holds "no \"the grader\" or \"the checker\"" and later "The agent must not learn how it is scored from the prompt." Matches. CONFIRMED.
4. Starter:9 (used in PL5). Line reads "no checks skipped because the bundle looks clean, comes from a trusted author, or resembles a bundle that passed before." The checklist quote shortens the middle with "..." and keeps the meaning. CONFIRMED.
5. 04:99 JD-18 (used in PL11 and PL12). Line holds "Nothing about this has to appear in `instruction.md`. It is a CONDUCT criterion under JD-15" and lists names, errors handled, dead or duplicated blocks, debug residue, readable functions. Matches both items. CONFIRMED.
6. 01:47 IN-17 (used in PL16 and PL17). Line holds "The instruction must not pre-announce what the agent is supposed to discover.", "ALREADY establishes" and "That sentence is a requirement and it stays". Matches. CONFIRMED.
7. FC:447 (used in PL1). Line reads "| minor | Real defect, low blast radius (typo in TRUTH.md prose, slightly awkward phrasing). Fix quickly. |". Matches. CONFIRMED.
8. 04:21 (used in PL15). Line reads description = "The agent opens a file under /tests or /logs/verifier during its run." Matches. CONFIRMED.

Result: 8 of 8 confirmed, no correction needed.

Other checks done while writing (not part of the 8):
Old generator bugs rechecked at origin/main: GEN/generate_bundle.py:1851 to 1852 still set both fields to "", GEN/CATEGORIES.md:34 to 35 still names two archetypes, so Q21 items 5a and 5c stay live.
Old chmod question: FC:232 now reads "chmod 755 /logs/verifier", so Q33 is settled.
Old IN-15 question: 01:45 now uses type = "instruction following", so pending.db Q37 is settled.
Old Q56: 04:21, 04:58 and FC:140 still use the unanchored "/tests" wording, so it stays live.
Style: no dash punctuation, no bold, no headings, no contractions (grep), 33 items counted.
