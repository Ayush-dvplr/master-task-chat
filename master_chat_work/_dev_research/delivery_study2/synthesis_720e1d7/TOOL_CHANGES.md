# TOOL_CHANGES (draft, board 720e1d7). Do not edit the tools from this file; the master applies.

Tools: `master_chat_tasks/tools/stacking_check.py` (314 lines) and `master_chat_tasks/tools/precheck.sh` (162 lines).
Short version: stacking_check guesses a check's class from its name. On seeded, gated or combined designs the guess is wrong, so its hidden share, its duplicate hints and its stacking verdict mislead. precheck has no gate for the new v3 design files (BRANCH_FIRE, RULE_TRACE, JUDGE_MAP probe band), for the stated invocation, or for rc-sensitive negatives.

## A. stacking_check.py

### A1. Hidden share is computed from names, not from what the test runs
- What it does: `classify()` (:171-189) labels a check `hidden_rows` only if its name ends in `_hard`, starts with `trap_|general_|damage_`, ends in `_probe`, or its description says fresh/hidden/unseen/seeded. Anything with `artifact|exists|shipped|keys_match_schema` becomes `shipped_only`. The share at :266-267 sums those labels.
- Measured misreads:
  - 37a0c3d6 tool hidden 8.6%, true 57.1% (`g2_aee9e0a/C_37a0c3d6.md:23`).
  - 3def42a3 tool hidden 3.4%, true 100% gated (`g2_aee9e0a/GROUP_SUMMARY.md:84`, `C_3def42a3.md:59`).
  - 80877080 tool shipped_only 47.8%, real 9% (`g4_af78147/C_80877080.md:25`).
  - 4e2f6925 tool hidden 27%, real 81% (`g4_af78147/C_4e2f6925.md:21`).
  - 0b27b9dc: 24 artifact checks assert the shipped artifact AND a rebuild on the unseen corpus; tool says shipped_only (`g3_bffecb6/C_0b27b9dc.md:23`). Same for 7e0d8feb and 56fe3bdd (`C_7e0d8feb.md:20`, `C_56fe3bdd.md:32`).
  - 7c2e77a1 tool "isolated 98.4%, hidden 0%", true 11 held-out pts (`g1_be971df/C_7c2e77a1.md:37`).
  - False positive the other way: 8d3e20fb `trailer_once` classed hidden, but grading is 100% shipped (`g4_af78147/C_8d3e20fb.md:38`).
- Change: classify by call graph, not by name.
  ```
  SEED_SOURCES = calls to any function that (a) takes a seed / rng / random.Random, or
                 (b) writes a corpus dir then runs the delivered program (subprocess with out/<program>)
  for each test t:
      reach = transitive_callees(t, depth=6)          # follow nested calls, lambdas, partial(), dict-of-callables
      runs_program = any(subprocess/run_module call in reach whose argv names an out/ program)
      on_generated = runs_program and any(f in SEED_SOURCES for f in reach)
      on_shipped   = reads environment/data or /app/out files without regenerating
      label = "hidden" if on_generated and not on_shipped
              "combined" if on_generated and on_shipped     # 0b27b9dc check_artifact shape
              "shipped" otherwise
  share_hidden = sum(w for hidden) + sum(w for combined)  -> report both numbers separately
  ```
  Keep the name heuristic only as a fallback label, printed as `GUESS`.

### A2. Blind to gates (one helper that zeroes many checks)
- What it misses: `_full_core` (b42c61b9 :2458, 37a0c3d6 T:3812-3817, 80877080), `_finish` / `_reweigh` (3f39299a :1630/:1690), `_pass(_all(...))` (6d12f970), `_leaf`/`_held_out_exact` (80877080 :2524-2531). Evidence `g1_be971df/GROUP_SUMMARY.md:76`, `C_b42c61b9.md:28`, `C_3f39299a.md:28`, `C_6d12f970.md:25`, `g4_af78147/C_80877080.md:25-26`.
- Change: detect shared failure causes and report them as a gate.
  ```
  for each helper h called (transitively) by >= 3 positive tests:
      if h's body asserts / returns False over a loop of corpora or calls every corpus (all(...), for c in CORPORA: ... return False)
         or h is called before the test's own comparison and its failure short-circuits it:
          GATE[h] = tests reaching h
  print "GATE <h>: <n> checks, <w>% of positive weight depend on it"
  if any GATE covers > 50% of positive weight: print "WARN GATE: stated in instruction? (LEVER_RULES_v3 G1, CL-4 FC:491; pending QL Q3)"
  ```
  The cost table (G10) must then treat a gated group as one lever cost, not N independent ones.

### A3. TS-26 duplicate hints are false positives on seeded families
- What it does: :227-232 groups tests by (observable literals, logic callees). A shared assertion helper called with a different seed or family looks like a duplicate.
- Measured: false in 3def42a3 (`C_3def42a3.md:77`), 7e0d8feb `_assert_case_core` / `_assert_case_family` (`C_7e0d8feb.md:21`), 8d3e20fb `_holds` (`C_8d3e20fb.md:50`), 6d12f970 (`C_6d12f970.md:25`), 18b5d99f (`C_18b5d99f.md:25`), 8764bfdd (`C_8764bfdd.md:27`).
- Change: include the constant arguments of the call into the shared helper (seed, corpus name, family name, file name) in the grouping key. Two tests are duplicate candidates only when helper AND those arguments match.
  ```
  key = (observable_literals, logic_callees, tuple(const_args_of_calls_into_shared_helpers))
  ```

### A4. AL-28 "UNMATCHED" lumps unrelated negatives into one false FAIL
- What it does: `act_of` (:44-48) maps a negative to an act by regex; anything unmatched goes to one `UNMATCHED` group; :265 fails any group above 5.
- Measured false FAILs: 4e2f6925 "UNMATCHED 53" (`C_4e2f6925.md:50`), 80877080 "UNMATCHED 51" (`C_80877080.md:56`), 8d3e20fb "-3 + -5 = 8" across different acts (`C_8d3e20fb.md:50`), 3def42a3 sum 11 = three acts (`C_3def42a3.md:140`), 6d12f970 (`C_6d12f970.md:42`). One true positive it caught: 37a0c3d6 grader act -5 in tests and -5 in judge (`C_37a0c3d6.md:47`), which our AL-28 reading rejects.
- Change: each unmatched negative is its own group, printed `NAME BY HAND`, and never contributes to the FAIL verdict. FAIL only for matched acts summing above 5 across tests and judge.
  ```
  groups = {act: [...] for matched}; for n in unmatched: groups[f"UNMATCHED:{n.name}"] = [n]
  verdict FAIL iff any matched group sum > 5
  print "HAND-CHECK" list for unmatched
  ```

### A5. New: probe-band share and figure criteria (judge side)
- What it does now: j1 hint flags any 2-digit number (:256); j2 regex looks for "constructs/builds its own" (:257).
- Change for draft J1/J2 (LEVER_RULES_v3_DRAFT section 4):
  ```
  probes = [c for c in judge if c.weight > 0 and c.evaluation_target == "trajectory"
            and re.search(r"runs its program on|shows one|outside its program|copy of the data|before its first edit|working directory other than", c.description)]
  share = sum(probes.weight) / sum(positive weights)
  print "PROBE BAND n=<len> share=<share>"; WARN if n < 8 or share < 0.55 or any probe weight == 5 (JD-15 minor at w5, 04:92)
  for each probe: require a JUDGE_MAP.md row with an oracle-shows line ("check <id> ok"), else FIND (JD-7, 04:76)
  J1: FIND any positive criterion whose description names an out/ file AND a number (figure restated from a file; JD-8 04:77)
  ```

## B. precheck.sh

### B1. No check that the shipped instance is quiet on purpose (degenerate instance)
- Gap: nothing reads `WORK/BRANCH_FIRE.md`. A design can claim a quiet shipped instance while the shipped data fires the hard branch (then Opus sees it), or the opposite: a branch fires nowhere visible and has no sentence (hidden rule, 3f39299a; `g1_be971df/C_3f39299a.md:34`).
- Change:
  ```
  require WORK/BRANCH_FIRE.md rows: | rule id | sentence file:line | fires on shipped (y/n) | fires in hidden corpora (count over 300 seeds) | toy example file:line |
  FIND if any row has no sentence file:line                     # hidden rule
  FIND if fires-on-shipped == n and hidden count == 0           # dead rule (AL-27)
  WARN if fires-on-shipped == n and no toy example               # W6 v3 expects one toy example per quiet rule
  FIND if a toy example's numbers appear in any environment/data file  (grep the literal values)
  ```

### B2. No check that the test runs the program the way the instruction says
- Gap: 8d3e20fb tests ran `python3 -I cli.py` from cwd /tmp, never stated; 16 pts lost plus a -3 negative fired on an honest run (`g4_af78147/C_8d3e20fb.md:11,40,57`).
- Change:
  ```
  inv_ins  = commands in instruction.md matching r"python3? [^`]*out/\S+\.py[^`]*"
  inv_test = argv lists in tests/*.py passed to subprocess.* (resolve list literals and cwd= args)
  FIND INVOCATION if a test argv uses a flag (-I, -E, -S, -B, env= stripping PATH/PYTHONPATH) or a cwd that the instruction never states
  ```

### B3. No check for rc-sensitive or run-shape negatives
- Gap: a negative that fires on an exit code or on the presence of stderr text fired on honest runs (8d3e20fb negative_fake_report; `g4_af78147/GROUP_SUMMARY.md:102-105`).
- Change:
  ```
  for each negative test: if its body reads returncode / stderr and does not also compare a claimed value against a recomputed one:
      FIND RC-NEGATIVE (LEVER_RULES_v3 G4)
  ```

### B4. No check for unstated output conventions (silent value forms)
- Gap: 80877080 graded upper-cased `project_status` that no file stated (:1886-1895 vs output_contract.md:85-87), 43 pts (`g4_af78147/C_80877080.md:7`). CL-5 (FC:492) says such a form must be stated, shown by an example, or compared insensitively.
- Change (heuristic, warn-only):
  ```
  for each string literal the tests compare an output field against (== or in {...}):
      if the literal (case-sensitive) appears in no environment/ file and not in instruction.md:
          WARN SILENT-FORM <literal> (CL-5 FC:492)
  for each .upper()/.lower()/.strip()/round(...) applied to the EXPECTED side only: WARN
  ```

### B5. No check for the v3 judge guards
- Gap: shapes that fired on honest agents in peers: a negative on a hand-made file in out/ when the program is itself the out/ deliverable (0b R6), a confinement clause widened to "the agent's session" (e13 R1), an and-bundle that adds an unrequested deliverable (e13 R2), a process criterion that re-charges a trap a test grades (56 R5), a self-consistency negative (9125 R3). Evidence `g3_bffecb6/GROUP_SUMMARY.md:54-58`, `g2_aee9e0a/GROUP_SUMMARY.md:33-36`.
- Change (warn-only lints on judge.toml descriptions):
  ```
  WARN J2b-SESSION   r"during (the|its) session|at any point in the session"
  WARN J2b-AND       positive criterion with " and also " / " and writes " naming a file not in the instruction's output list
  WARN J2b-SELFCONS  negative with r"inconsistent|contradicts itself|self-consisten"
  WARN J2b-OUTFILE   negative mentioning "creates|writes" + "out/" when the instruction names a program under out/
  ```

### B6. New gate: rule register present and complete (breadth designs)
- Change:
  ```
  if WORK/RULE_TRACE.md exists: every generator branch name in tests (functions named _plant_*, branch tags) must appear in a row with a sentence file:line, else FIND (IN-15 01:45, TS-19 03:50)
  count rules; print "RULES <n> over <files> files, <formats> formats" so the master can check the Shape B target
  ```

### B7. Keep as is
- W1 lints at :43-47 (trap words, trap file names, footgun phrases): keep. Peer 4e2f6925 shipped a numbered footgun list and passed QC, but lost no extra points for it and it is our hard rule (CONFLICTS C6).
- IN17-PHRASE / SELF-CHECK-INVITE lints on instruction.md (:110-121): keep. They stop probe wording leaking into the instruction (draft J2: probe wording never in instruction.md). Note: the lint only reads instruction.md, so a unique-fit rule written "exactly one combination" in a data file (BUILD_RECIPES B) is not flagged; that is intended.
- J1 figure NOTE (:150): change wording to FIND when a figure criterion names an out/ file (draft J1 drops figure criteria).
