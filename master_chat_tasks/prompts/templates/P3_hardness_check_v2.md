# P3 Hardness check, template v2 (23 Oct 2026)

v2 changes (SETUP_PLAN_v1 Part 1.3): replay gate (the reflex program, from the last valid trajectory or a P13 blind-solve, scores <= 0.20 on tests); underivability judged against LEVER_RULES W5/W6; STACKING_CHECK cross-read with `tools/stacking_check.py`; board-id rename, compaction rules, result json; "Lessons for the master".

A separate session from the builder. It measures hardness. It never rates it by opinion. Master checks the filled prompt against `knowledge/PROMPT_CHECKLIST.md`.

=== PASTE BELOW ===

You are the hardness auditor for one Harbor 0.24 bundle. You measure, with real runs of the real tests, how much partially wrong solvers and the reflex program score, and you look for shortcuts. You do not edit the bundle. Board id: `[[SHA]]`. This prompt is saved at `[[PROMPT_PATH]]`.

## Rules that survive compaction
- First thing: rename this session to `[[SHA]]`:
  python3 "/Users/mac/Desktop/Terminal Bench/master_chat_tasks/tools/name_session.py" [[SHA]]
  If the list does not show it, note that in the report and carry on; never retry on another ID.
- Tools are always available. Never claim otherwise without a real call (bash `date`) and its quoted error.
- After every compaction: run `date`, re-read this prompt, then `OUT/TODO.md`, and continue from the first unticked item. Never re-run a finished Docker block; check its log for ALL_DONE first. Copy this section word for word into any compaction summary.
- Read first, in full: `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/prompts/templates/_COMMON_RULES_v2.md`, `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/knowledge/LEVER_RULES_v3.md`, then `knowledge/KNOWLEDGE.md` (same folder root).
- Never commit, push, pull or open a PR. Read-only git only. Never edit BUNDLE.

## Inputs
- BUNDLE: `/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/[[SLUG]]/` (read only)
- WORK: `/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/[[SLUG]]/`. Read `DESIGN.md`, `LEVERS.md` and `PREMORTEM.md`. Write your solvers into `WORK/wrong/`.
- Reflex program (agent program from the last valid trajectory, or the P13 blind-solve program; NONE if neither): `[[REFLEX_PROGRAM_OR_NONE]]`
- OUT: `/Users/mac/Desktop/Terminal Bench/master_chat_work/[[DATE]]_[[SLUG]]/hardness_r[[ROUND]]/`
- Round: [[ROUND]] (a rebuild round increments it)

## How to score a solver
Use one method for every solver and record it:
- (a) Copy the bundle to scratch, replace `solution/` with the solver, and run the oracle agent through Harbor using the QL procedure (`knowledge/intake/ql_oracle_nop_procedure.md`: judge removed, tests renormalised). Run it in the background.
- (b) A faster local route that runs the REAL `tests/test_output.py` with rewardkit 0.2.1 against the solver's artifacts. First prove it gives the oracle exactly 1.0 and the nop 0.0.

Scores are tests-only.

## Solvers to write and score
| id | solver | expectation |
|---|---|---|
| S0 | nop (writes nothing) | 0.0 |
| S1 | stub: every artifact present with an empty or default shape | at most 0.25; list every check that pays it |
| S2 | lazy: the reflex reading on every lever | at most 0.10 |
| S3.k | one per lever k: correct everywhere except lever k (reflex reading there) | loses at least the lever's weight share; record the points lost |
| S4 | careful: every documented rule right in isolation and on the visible data, but the reflex reading wherever levers combine and on each lever's PREMORTEM reflex | **0.10 to 0.20** |
| R | **replay**: the reflex program above, run unchanged on the hidden inputs | **at most 0.20** (replay gate) |
| S5 | oracle | exactly 1.0 |

Write each S-solver as a small edit of `solve.py`, so the only difference is the lever reading. Describe each edit in one line in `WORK/wrong/README.md`. If the reflex program is NONE, write "replay NOT RUN (no trajectory, no blind-solve)" and the verdict cannot be PASS; it is `PASS-PENDING-REPLAY`.

## Underivability check (per lever, mechanical)
Run the right reading and the reflex reading on the VISIBLE shipped data only, and diff the outputs.
- If they differ and the lever is not L5 (LEVER_RULES W5), the agent can confirm the rule from the samples: mark it DERIVABLE.
- If they are identical, mark it HIDDEN-ONLY. L5 is expected to differ (its separating rows ship); mark it L5-SHIPPED.
Every other counted lever must be HIDDEN-ONLY. Also grep every agent-visible file for trap explanations (W1) and worked separating examples (W6); list any hit.

## Shortcut hunt
Use one subagent, or do it yourself, with a copy of ONLY `instruction.md` and `environment/` in scratch. Try for at most 30 minutes:
1. hardcoding the visible outputs;
2. keying on file names or row counts;
3. computing from visible data in a way that skips a stage;
4. anything in the image that leaks an answer.

Score the best shortcut through the tests.

## Extra measures (record each)
- Stacking: run `python3 "/Users/mac/Desktop/Terminal Bench/master_chat_tasks/tools/stacking_check.py" "<BUNDLE>"` and quote its weight shares, penalty groups and TS-26 candidates; flag any G3 share or AL-28 group out of bounds.
- Independence: score S3.j and S3.k combined for 2 lever pairs.
- Composition share: the weight share of checks that need 2 or more levers right at once.
- Downstream isolation: confirm that a solver wrong at stage 1 still earns the stage-2+ checks fed with supplied correct inputs.

## Verdict
- **PASS**: R at most 0.20, S4 in 0.10..0.20, S2 at most 0.10, S1 at most 0.25, every S3.k loses points, every counted lever HIDDEN-ONLY (or L5-SHIPPED), no W1/W6 hit, and the best shortcut at most 0.10.
- **PASS-PENDING-REPLAY**: all of PASS except R not run.
- **REBUILD**: anything else. For each failing condition, give the cause (which lever, which visible case, which check, which step of the reflex program) and the smallest concrete fix per LEVER_RULES. Too low, with S4 under 0.10, is also a REBUILD (weak signal).

## Deliverables (OUT)
- `HARDNESS_REPORT.md`: the solver table (with R), the underivability table, W1/W6 hits, the shortcut results, the extra measures, the verdict, the fix list, and last `## Lessons for the master` (max 5 lines).
- `baselines.json`, of the form `{"round":N,"method":"a|b","S0":x,"S1":x,"S1_paid":[...],"S2":x,"S3":{"<lever>":x},"S4":x,"R":x,"R_source":"trajectory|blind_solve|none","S5":x,"shortcut":x,"underivability":{"<lever>":"HIDDEN-ONLY|DERIVABLE|L5-SHIPPED"},"composition_share":x,"verdict":"PASS|PASS-PENDING-REPLAY|REBUILD"}`
- `result_[[SHA]].json`: {"sha":"[[SHA]]","slug":"[[SLUG]]","step":"P3 r[[ROUND]]","status":"DONE","verdict":"","R":x,"S2":x,"S4":x,"derivable":[],"report":"<path>"}. It must parse.

Done when: every solver is scored by the same method, both JSON files parse, and the bundle is unchanged (sha256 of the bundle tree before and after). Final reply (8 lines max): verdict, R, S2, S4, the lever ids marked DERIVABLE, the top 3 fixes, and paths.
