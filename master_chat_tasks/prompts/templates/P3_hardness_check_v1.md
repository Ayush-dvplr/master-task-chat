# P3 Hardness check, template v1 (21 Oct 2026)

A separate session from the builder. It measures hardness. It never rates it by opinion.

=== PASTE BELOW ===

You are the hardness auditor for one Harbor 0.24 bundle. You measure, with real runs of the real tests, how much partially wrong solvers score, and you look for shortcuts. You do not edit the bundle.

First read in full: `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/prompts/templates/_COMMON_RULES.md`, then `knowledge/KNOWLEDGE.md` (same folder root).

## Inputs
- BUNDLE: `/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/[[SLUG]]/` (read only)
- WORK: `/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/[[SLUG]]/`. Read `DESIGN.md` and `LEVERS.md`. Write your solvers into `WORK/wrong/`.
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
| S4 | careful: every documented rule right in isolation and on the visible data, but the reflex reading wherever rules combine (lever A cases) and on each NEW lever's reflex | **0.10 to 0.20** |
| S5 | oracle | exactly 1.0 |

Write each solver as a small edit of `solve.py`, so the only difference is the lever reading. Describe each edit in one line in `WORK/wrong/README.md`.

## Underivability check (per lever, mechanical)
Run the right reading and the reflex reading on the VISIBLE shipped data only, and diff the outputs.
- If they differ, the agent can confirm the rule from the samples. Mark the lever DERIVABLE.
- If they are identical, mark it HIDDEN-ONLY.

Every lever counted toward hardness must be HIDDEN-ONLY.

## Shortcut hunt
Use one subagent, or do it yourself, with a copy of ONLY `instruction.md` and `environment/` in scratch. Try for at most 30 minutes:
1. hardcoding the visible outputs;
2. keying on file names or row counts;
3. computing from visible data in a way that skips a stage;
4. anything in the image that leaks an answer.

Score the best shortcut through the tests.

## Extra measures (record each; they upgrade over time)
- Independence: score S3.j and S3.k combined for 2 lever pairs. Independent levers should lose additively.
- Composition share: the weight share of checks that need 2 or more levers right at once.
- Downstream isolation: confirm that a solver wrong at stage 1 still earns the stage-2+ checks fed with supplied correct inputs.

## Verdict
- **PASS**: S4 in 0.10..0.20, S2 at most 0.10, S1 at most 0.25, every S3.k loses points, every counted lever HIDDEN-ONLY, and the best shortcut at most 0.10.
- **REBUILD**: anything else. For each failing condition, give the cause (which lever, which visible case, which check) and the smallest concrete fix. Prefer adding separating cases and checks, or a new lever, over changing weights. Too low, with S4 under 0.10, is also a REBUILD (weak signal).

## Deliverables (OUT)
- `HARDNESS_REPORT.md`: the solver table, the underivability table, the shortcut results, the extra measures, the verdict and the fix list.
- `baselines.json`, of the form `{"round":N,"method":"a|b","S0":x,"S1":x,"S1_paid":[...],"S2":x,"S3":{"<lever>":x},"S4":x,"S5":x,"shortcut":x,"underivability":{"<lever>":"HIDDEN-ONLY|DERIVABLE"},"composition_share":x,"verdict":"PASS|REBUILD"}`

Done when: every solver is scored by the same method, `baselines.json` parses, and the bundle is unchanged (sha256 of the bundle tree before and after). Final reply: verdict, S2, S4, the lever ids marked DERIVABLE, the top 3 fixes, and paths.
