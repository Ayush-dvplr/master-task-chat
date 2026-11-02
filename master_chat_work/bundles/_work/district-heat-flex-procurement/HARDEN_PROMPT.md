# HARDEN pass v2 - district-heat-flex-procurement

You are continuing work on an EXISTING, already-validated Harbor input bundle. An
independent solve (a strong model, one pass, ~15 min, full marks expected) showed the task
is too easy. Your job is to make it genuinely harder WITHOUT breaking QC, fairness or
solvability, then re-measure everything. Work in small verified steps.

## Paths

- Bundle (edit in place): `/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness/Input Bundle Generator New/ayush sah tasks/district-heat-flex-procurement/`
- Work folder (sources, notes): `/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness/Input Bundle Generator New/ayush sah tasks/_work/district-heat-flex-procurement/`
  (DESIGN.md, PLAN.md, TODO.md, LOG.md, datagen.py, test_output.src.py, TRUTH.src.md,
  embed.py, grade.py, judge_build.py, wrong/, stub/)
- QC authority: `/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness/Input Bundle Generator New/ayush sah tasks/_qc/Input_Bundle_QC/`
- Generator folder (READ-ONLY, never edit): `/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness/Input Bundle Generator New/`

## RULE 0 - plan in files

1. Read LOG.md, TODO.md, PLAN.md, DESIGN.md first. They describe the current build.
2. Append a `## v2 HARDEN` section to TODO.md (checkbox list of H-steps below) and to
   PLAN.md (your concrete plan). Log every run, failure and fix in LOG.md with IST times.
3. Do not regenerate the bundle with generate_bundle.py and never use `--force`.
4. Stop after step V0 and wait for Ayush's approval. Then do V1 to V9 without stopping
   unless a QC gate cannot be met.

## RULE 1 - hard limits (unchanged)

No edits to the generator folder or the QC folder (record sha256 of generator files at
start and end, compare). Stdlib only. Archetype stays `domain-calculation` with exactly the
10 artifacts. No em/en dashes anywhere. All QC rules from the first build still apply
(DS-21/CL-10 solvable from visible files, DS-25, DS-27, CL-4 partial credit, IN rules,
JD rules, TS rules, A5 line counts). No unmeasured claims: every number you report comes
from a run you made and logged.

## Diagnosis you must address (from the independent solve)

- Every rule is written in schema.md and maps straight to code. A careful reader implements
  all of them. Placing a rule in a far section does not trip a frontier model.
- The optimiser is `itertools.product` over at most 162 portfolios per event-region. No
  algorithmic difficulty.
- Every output is one hop from the inputs. A wrong portfolio does not propagate.
- The solver had to GUESS in 4 places. These are fairness bugs, fix them in schema.md:
  1. how "greatest set of ids" is compared (sorted-tuple order? state it with an example
     where tuple order and largest-element order disagree, e.g. {A,Z} vs {B,C});
  2. whether credit rounding is per offer or per site;
  3. whether blank lines in jsonl files are skipped or counted;
  4. that every region code (targets, limits, floors, pools) maps to a region name via
     program.ini before use as a key.

Keep (already correct, do not undo): shipped data keeps the hard rules inert (that is the
underivability guarantee), and the constructed hidden cases test them. The reviewer did not
see tests/; the hidden cases already exist.

## Levers to implement (in this priority)

### L1 - exact optimisation that brute force cannot do (main lever)
- Add "large" event-regions: about 10 in the shipped data and at least 2 in hidden extracts,
  each with 18 to 22 sites and 3 to 4 modes per site (product ~10^11 to 10^13).
- Keep 12 ceilings (6 intervals x relief, recovery) and the existing lexicographic objective.
  Make most ceilings slack and a few tight so bound-based pruning works for a correct
  exact method (branch-and-bound or meet-in-the-middle).
- Add an output field `tied_portfolio_count` per event-region (exact count of portfolios
  that equal the optimum on the full objective before the id tie-break). State in schema.md
  precisely what is counted. The natural trap: pruning on `>=` instead of `>` undercounts
  ties. Construct hidden large groups with 2 to 5 tied optima spread across branches.
- Determinism: the chosen portfolio must not depend on search order (the id tie-break
  already ensures this; verify it with a shuffled-input hidden case).
- Runtime budget: the reference must solve every large group in the shipped data in under
  60 s total on 2 CPUs, measured inside the agent Docker image. State the budget in
  instruction.md in one plain sentence (e.g. "Each run of the program on an extract must
  finish within N seconds."), and enforce it in the verifier with a per-run timeout of
  about 3x the oracle time. Verifier total time must stay well under 2700 s, so measure it.
- Prove the reference is exact: write `_work/.../check_exact.py` that, for 200 random small
  groups (<= 8 sites), compares the reference against plain enumeration, and for the large
  groups compares against an independent second exact method. Log the result.

### L2 - one coupling hop (moderate)
- Fund each grant pool as `pool_cents - credits_paid_in_that_event_region` (floored at 0,
  state that). Grants now depend on the chosen portfolio and settlement.
- State the calculation order explicitly in schema.md (portfolio, then credits, then
  grant funding, then apportionment).
- Keep CL-4 partial credit: grade portfolios, credits and grants as SEPARATE checks, and add
  one hidden case where portfolios are given trivially (one site, one mode) so a correct
  grant implementation scores even if the optimiser is wrong.

### L3 - spec-compliant parsing traps (cheap)
- Fixed-width files: some event ids fill all 10 columns and some ceilings fill all 10
  digits, so fields touch and `str.split()` fails. schema.md already gives column spans; check.
- `offers.csv`: some `mode_label` values contain commas and are quoted (RFC 4180).
- `rate_cards.xml`: in some cards `<cap>` comes before `<base>`; some numbers have
  surrounding whitespace (state in schema.md that whitespace around numbers is ignored).
- Some orphan profile rows point at offers that exist but are ineligible, so the orphan
  and ineligible counts must be kept apart (state both definitions precisely).

### Do NOT add (unfair, breaks the spec)
BOM in CSV headers; booleans as strings where the spec says JSON booleans; intervals above
interval_count; duplicate target rows under two codes of one region; case or whitespace
variants of waiver_status.

## Steps

- V0 Plan: write the v2 sections of TODO.md and PLAN.md, including the exact schema.md
  sections you will change, the new output field(s), the new hidden cases (name, rule
  stressed, expected lazy failure), the new check list with weights, and the runtime plan.
  STOP for approval.
- V1 schema.md: fix the 4 ambiguities, add L1/L2/L3 text. Keep rules stated once.
- V2 datagen.py: add large groups, L3 traps, keep inert-rule guarantees and A5 line counts.
  Re-run with seed 731904. Record line counts and file sha256 in LOG.md.
- V3 reference + solve.py: implement the exact method and coupling; run check_exact.py.
  Measure oracle runtime in the agent image.
- V4 tests: add hidden cases and checks (weights only 5/3/1, negatives -1/-3/-5), per-run
  timeouts, re-embed `_SHIPPED_DATA` with embed.py, rewrite reward.toml totals.
- V5 wrong/ and baselines: add lazy variants at least for (a) brute force with a time cap
  or greedy for large groups, (b) pruning on `>=` (undercounts ties), (c) no coupling
  (grants funded from raw pool), (d) `str.split()` fixed-width parsing, plus the existing
  H1 to H5 variants and all-lazy. Measure each with grade.py. Target: oracle 1.0, empty 0,
  at least one realistic row in 0.40 to 0.60, all-lazy below 0.50. Tune weights or cases
  until true; log every iteration.
- V6 instruction.md: add the runtime sentence and any new output property (one line each,
  WHAT not HOW, no grader mention, plain English, no dashes). Run instruction_qc.py.
- V7 judge.toml: update criteria that mention the optimiser (e.g. "measured runtime on the
  large groups", "verified exactness against enumeration on small groups", "checked tie
  counting"). Process only. Run judge_qc.py.
- V8 TRUTH.md and DESIGN.md: update TRUTH (defect labels for the new traps, no process
  narrative, DS-27). Append a `## v2` section to DESIGN.md listing every change.
- V9 Gates: structure_qc, instruction_qc, tests_qc, judge_qc (from the _qc copy),
  `validate_bundle.py --archetype domain-calculation`, playground.py (D1 oracle 1.0, D2 nop 0,
  D3 stub <= 0.25, D4 ablations <= 0.5). Compare generator checksums. Write the final report:
  what changed, measured baseline table, oracle and verifier runtimes, every QC result,
  anything you could not verify.
