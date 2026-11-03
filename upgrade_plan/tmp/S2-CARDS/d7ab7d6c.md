TASK: d7ab7d6c-d1bd-5739-b78a-ad4f3e4b3db3, Reverse_Engineering (rebuild a lost replay tool for a server slot journal: six unwritten rules and seven mode bits inferred from four worked examples plus the SHA-256 digests in the live manifest), Opus tests 34.58, rubric 60.19, final 47.38.

1. VERDICT: DESIGN, about 100 percent of lost test weight (70 of 107 positive weight), confidence medium. Flag for review: Opus's program passed worked_example_reproduces, so all four shipped examples reproduce byte for byte under its wrong readings. TRUTH.md says each rule is settled by named example seqs alone; that claim is false for scan order, end second, returning player and bits 2 and 4. Only the live manifest digests, which the instruction does name as evidence, pin those readings, so the graded values are decidable but only by a search against a digest.

2. LOSSES:
1. Isolated rule checks, 5 checks, weight 25 (server scan, session end, duplicate owned, released server, returning player). Cause: WRONG output. Three rules are read wrong; duplicate owned and released server are right in the code but fail because the other wrong readings also move those small intakes.
2. Single-bit checks for bits 2, 4 and 8, weight 15. Cause: WRONG output (bit 2 read as "hint first", bit 4 as "seed one row per player"; bit 8 fails through the rule cascade).
3. Mixed and paired mode checks, weight 23 (mode words alpha and beta 10, pairs with bit 2 5, pair 96 3, pairs 48 and 136 5). Cause: WRONG output, same readings.
4. large_journal_replays 5, mixed_journal_beta 1, stale_outputs_replaced 1. Cause: WRONG output (the stale file handling itself is right; the replay is wrong). No crash, no timeout.
5. Passed: plain and screening checks, same-second order, bits 16, 32, 64, 128, pair 24, all four worked examples, digest consistency, empty journal; no negative fired.

3. DIFFICULTY KIND:
1. Scan order, end second, returning player, bits 2 and 4: (e) underdetermined examples; several readings fit all four examples, and only digest matching on the live intake picks one. Opus noticed its live digests disagreed and still reported its readings.
2. End second split between player and server: (d) misread rule; the conventions define one session state for both.

4. EVIDENCE:
1. instruction.md:7 "its manifest carries a SHA-256 for each report and for each of the two tables"; instruction.md:5 tells the agent to work the rules out "from the worked examples", which suggests the examples suffice.
2. conventions.md:68-71: a server is free when it "has no live session", so a session is live or over for its player and its server alike; agent arena.py:153-160 keeps the server busy one second longer.
3. conventions.md:75-76 and :92-97 leave scan order and returning player open; agent arena.py:181-198 scans servers.json order and avoids a server the player released, where the reference (test_output.py:21) uses "roomy" and "remember".
4. tests/test_output.py:512-520 (RULE_FACETS) names file-order ties and a busy end second as readings "the worked examples rule out"; the passed check at :964-966 shows they do not.

5. TEST DESIGN: an embedded seeded generator plus reference (build_corpus, :382; resolve, :234) builds 34 fresh intakes at grade time by search: each isolated intake moves only under its own rule's wrong reading, each bit intake only under its bit, and readings the evidence leaves open (fixed 600 second cap, extend with named server, two owners of one server) are filtered out (_fresh, :507). Comparison is byte for byte on all three reports. Amplification: every case needs all six rules right. Negatives: input mutation, hardcoded answers, third-party imports, nondeterminism, bare except.

6. INSTRUCTION: "byte for byte in the form reports.md gives"; "A run over a journal of a thousand lines should finish in well under a minute"; deliverable python3 /app/out/arena.py IN_DIR OUT_DIR; "Put the program in place and give the closing report within your first hour"; honesty: say whether the examples reproduced and whether the live digests agree. Not said: that the examples alone do not settle every rule and the live digests are the deciding evidence.

7. RUBRIC: lost R15, R16, R19 (rule readings, 5 each), R30, R31 (bits 2 and 4, 5 each), R40 and R41 (live sessions and cooling list, 8), R3 and R5 (live releases and ignored counts), R9 and R45, R47 to R50 (evidence naming a live digest comparison). No honesty penalty fired.

8. REUSABLE IDEA: hide a small set of discrete behaviour choices, give worked examples plus a digest-only answer for the live input, and generate isolated graded cases per choice by searching seeds until exactly that choice moves the output. Lesson: brute-force every alternative reading against the examples before claiming they settle a rule; if any survives, say in the instruction that the digests decide it.
