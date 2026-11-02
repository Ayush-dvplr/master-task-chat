# S3a emberforge-vault-settlement round outputs (read 23 Oct 11:52 IST)
Base: master_chat_work/20261021_emberforge-vault-settlement/ (E1) and 20261022_emberforge-vault-settlement/ (E2)

## harden_r1 DIAGNOSIS (E1/harden_r1/DIAGNOSIS.md)
- :19 only HELD lever L7 "every condition is a finding, cap and floor at one forge (N3 x A4 x V4) | 11 | 1 | HELD"; all others LEAKED.
- :42 answer key: `calibration_reference_bundle.json` held full settled slice output; "Step 8 printed the whole bundle. Step 22 compared record shapes against it". Controls+example report alone leave exactly 1 draw.
- :43 "Isolated rules stated next to their use. The agent's first engine was right everywhere but L7. Step 18 was its first run and already found exactly one draw". L1 HIDDEN-ONLY yet V8 spells it out; E3 "signposted in bold ("**not**", "This is deliberate")"; step 12 `od -c` to check trailing newline.
- :44 "80 of 125 points read the shipped season, which a careful implementer settles correctly."
- :47 held cause: if/elif with early return; "N3 sits in `invariants.md`, away from A4 and V4. The slice raises no STOCK_FLOOR ... nothing visible separated the two readings. A composition that is HIDDEN-ONLY and spread across files is the mechanism that works."
- :54-56 agent never ran program on any other corpus; auditor never looked for entry with two+ findings; R6 pays presence not value.
- :33-37 judge R6-R10 "effort-based" — paid for presence (JD-7-like).
- :78 playground A5 volume check (20k lines) — waived later as "volume is not the difficulty" (HARDEN :74).

## harden_r1 HARDEN_REPORT (E1/harden_r1/HARDEN_REPORT.md)
- :7 "A4 states that the cap is judged on the charge a forge would carry, so a forge the floor or a retired reagent also refuses still closes its workshop. V9 adds retired reagents ... The register defines `consumed` ..." => r1 WROTE the held composition into one explicit sentence each (this is what leaked in v0 real run, see E2 DIAG :18-20).
- :9 34 -> 50 checks; every value check on reseeded season under own draw.
- :35 isolation: "Each S3_k loses exactly its own lever's checks, and the pairs lose additively".
- :65 "Estimate for a run like this one (not measured): judge 6/19 = 0.32, tests 0.168, overall 0.24."
- :84 S4 careful round1 0.1677; S4 = run 0 program minus reference bundle.
- :104 hardcoded-draw solver once scored 0.2516 (7 observables didn't move with draw) — fixed.
- No judge run (no OPENAI_API_KEY) :3.

## harden_r2 DIAGNOSIS (E2/harden_r2/DIAGNOSIS.md) — real v0 run 21 Oct 18:47-19:34, 23 steps
- :3 corrected tests 146/155 = 0.9419, rubric 84.21.
- :7-10 agent: dumped every document steps 3-9; "wrote the whole program in two edits. No exploratory runs before writing it" (steps 10-14); step 15 first run, recover_draw over 840 draws -> exactly one survived; steps 16-22 "internal identities only"; step 17 caught a real Q6 bug via own audit; step 20 timed own 48-req stress season 6.3 s vs 38 s; finished ~47 min into 7200 s.
- :12 "The one self-check that touched the answer was the slice: a unique surviving draw told the agent that its engine reproduced a whole settled season. Everything else it checked was an identity that holds under any reading."
- :18 LV-EF-1 LEAKED: "Round 1 stated the composition in one sentence."; 5 points lost were S6 ambiguity IN-16, "Not the lever".
- :19-20 LV-EF-2/-3 LEAKED "the composition is written out in V9"; "The register defines exactly which forges count."
- :21 LV-EF-4 size lever LEAKED: "Round 1 priced the exhaustive DFS of the round 0 run; this agent never wrote one. A size lever does not bind an agent that picks a bounded search first." (branch and bound + max-flow bound).
- :23 isolated quiet_rules lost via crash on salvage with missing forge ref: "HELD by an untested branch, not by a lever."
- :30 "The prediction priced the round 0 program, not a fresh reader. ... A reader who follows those sentences literally gets all three right, and this one did."
- :31 slice search "doubled as an end-to-end test of the engine (study rule 7)".
- :32 "Grading isolated one lever per season ... 40 of 45 positive checks".
- :33 final-reply ask told agent which facts mattered ("four conventions" ...); judge read visible values the program printed at step 15.
- :48 caveat: "rules stay documented (common rule Never 6), so a literal reader can still get every lever right".

## harden_r2 HARDEN_REPORT (E2/harden_r2/HARDEN_REPORT.md)
- :22 removed confirming oracle (calibration tables); council_rulings.json = isolated reductions pinning draw uniquely, "No ruling is a figure of any season".
- :23 "Four conventions" sentence gone; final ask = computed figures only.
- :24-34 composition: five mixed seasons, 3 whole-document checks w5 each.
- :35 decoy LV-EF-5 `clerks_digest.md` 5 desk notes, 4 exact, 5th counts same-day forge; instruction says rulebooks govern over any other note (CL-6 signpost).
- :36 rule by omission: cap+floor composition moved to N3 scope sentence.
- :37 judge one shipped-season figure each (130027 etc.).
- :44 lever table "differential design check, not a solver run".
- :53 decoy wrong reading loses 78/101; hardcoded draw loses 96.
- :62-66 74.3% whole-doc, isolated+structure 25.7%, shipped-only 2%.
- :84 judge not run (no API key).
- :97 "The oracle now settles a 48-requisition season in about 0.1 s locally, so the round 1 '10x slowest oracle' derivation no longer applies; the limit is still stated and enforced."
- :100 three harbor processes overlapped ~15 s (Docker max 2 breach).
- :101 "how often a frontier agent misses is unmeasured."

## P12 r1-r3 PL_NOTEs (E2/p12_r*/PL_NOTE.md, result_*.json)
- r1: real 6 FP 1 (W-01-1 short lead lines flagged as slop; kit says layout author's choice 01_Instruction_QC.md:19). TS-19 kept minor: shipped season presence/form only "on purpose ... A full value check on the shipped season would put that answer in the grader". JD-16 network criterion kept.
- r2: real 2: key order promised but ungraded; A2/A4 edges (workshop exactly on cap, open first/close last day) not in any graded season. FP JD-16 on R9 /app/data write (judge owns undeclared paths 04_Judge_QC.md:97).
- r3: real 4: ORACLE BUG "a workshop's allocated units are now the sum over all its requisitions ... Before, it kept only the last one." and "no graded season had a workshop with two requisitions, so the wrong oracle still scored 1.0" => fixture-coverage gap; oracle 1.0 is not proof of correctness.
- QC fmw sequence (scores.jsonl l27,31,36,41): 1/2/4 -> 2/0/1 -> 2/1/1 -> 0/0/1; each P12 round QC found NEW real issues (whack-a-mole).
- No real trajectory after r2 redesign recorded in scores.jsonl (lines 12-41) => r2 levers UNMEASURED.

## Derived points
- E-a lever_leaked: writing the held composition into one explicit sentence (r1 fix) converted the only HELD lever into LEAKED (0.942 real). Strong evidence for study rules 3/4 and P4 "never state the trap".
- E-b agent_behaviour: writes whole program before any exploratory run; validates only by internal identities + a uniqueness search; stops at ~47 of 120 min.
- E-c process_failure: build-time S4 = previous run's program; predicting a fresh agent from one prior program's mistakes underestimates by 0.77.
- E-d lever_leaked (size): time/size lever doesn't bind an agent that picks bounded search; derivation of limit from oracle speed went stale (0.1 s).
- E-e bundle_bug: oracle wrong on untested fixture shape; QC caught it in r3 only.
- E-f agent_behaviour: crash on input shape absent from shipped data (missing forge ref) — "held by an untested branch"; hidden fixtures with edge shapes absent from visible data cost points legitimately.
