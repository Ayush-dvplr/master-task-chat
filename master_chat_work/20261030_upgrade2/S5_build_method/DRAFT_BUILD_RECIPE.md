# Draft build recipe (research proposal; no pipeline edits)

## 0. Choose an idea before authoring

Choose a documented task with a held-out behavior that changes the *answer*: an exact optimum on larger legal instances, a held-out convention inferable from shipped evidence, or a hazard slice with a unique observable. Put at least half of positive test weight on held-out w5 checks and add a distinct judge probe band. This is a pilot design, not a proven guarantee: `master_chat_tasks/knowledge/LEVER_RULES_v3.md:96-119`; `S4_task_study/LEVER_WEIGHTS.csv` counts 657.51 of 2,134.52 classified lost final points (30.8%) on held-out/scenario exact, but its labels are INFERRED from check names.

Write one page: governing sentences, shipped versus held-out distribution, oracle algorithm and bound, strongest plausible solver, a valid-but-wrong failure stage, test points it will lose, judge probes, reference runtime, verifier runtime. Require a rule-to-branch-to-check trace. Reject an idea if its only separating case is an unstated rule, an impossible optimum, or an agent timeout. Evidence: `LEVER_RULES_v3.md:81-87,96-119`; `beta-task-generator/references/curated/design-guide.md:10-20,65-97`.

## 1. Kill test before a bundle exists

Prototype only the core data, oracle, and one strongest generic solver. Run three independent design-blind reads on the *published* contract. Score their programs on three held-out seeds each, preserving WRONG / TIMEOUT / CRASH separately and checking shipped behavior. Continue only if at least 2/3 blinds lose >=40% of positive held-out test weight and at least one strong plausible implementation loses through a valid wrong answer. If blinds are exact, mark NO CORE and stop. If wrong loss disappears after a stronger generic solver, mark NO CORE. These are proposed gates aligned to the promotion bar in `LEVER_RULES_v3.md:119`; the 7 parked builds in `BUILDS.csv` show why the test is early. No paid run yet.

## 2. Author the minimum complete bundle

Write the contract once, then independent oracle and hidden seeded generator, then tests and judge. Every hidden branch must have a published rule; every promised branch must be planted and graded. Make shipped examples small enough to inspect, hidden instances within stated bounds, and no example that walks through the separating algorithm. Keep an exact-match rule only when its one-fact-wrong score is justified. Use outcome checks for output and judge probes for different conduct/verification observables. Require oracle 1.0, nop 0, stub inspection, cross-reference/precheck, and a mutant for each core lever. `LEVER_RULES_v3.md:96-119`; `beta-task-generator/references/curated/design-guide.md:65-123`.

## 3. Fresh blinds before full QC

Three fresh P13 reads on frozen candidate bytes. Score each program against shipped checks and new hidden seeds. Proposed bar: each <=65 tests, none >70, at least 2/3 lose >=40% held-out positive weight, and all losses classified. Require predicted final <=30-32 if the needed delivery gate is <35, leaving room for judge variance. A high score or timeout-only separation triggers one core redesign, then repeat the kill test. At second NO CORE, park; do not spend QC or a paid run. Current v3.7 aims are tests <=60, blind <=65 none >70, judge mid <=20 (`LEVER_RULES_v3.md:1,96-119`).

## 4. QC, freeze, one paid run, trajectory decision

Full P11 QC; fix only REAL findings, use recheck with carry-over, then freeze exact tree. Run one paid harness attempt. Require tests <85, rubric <85, and final <35 when Ayush chooses that target (current general rule is final <40). If it misses, inspect per-check trajectory; allow one new design only if it adds a valid WRONG failure and survives fresh blinds and QC. Do not use a regrade as push evidence. `decisions.jsonl:336-337`; `LEVER_RULES_v3.md:1,96-119`. Exception requests should show the loss table and why a legal design change cannot produce WRONG losses; routine timeout share is a design failure, not an automatic rule change.

## Budget and token control

These are planning ceilings around *clean board-row medians*, not measured active work or guarantees: design/kill 90 min (INFERRED; no direct median), P2 build 374 min (n=2), P9 redesign 180 min (n=22), P13 read 32 min each (n=44), blind scoring 66 min (n=7), full P11 QC 52 min (n=7), P12 fix 90 min (n=18), recheck 43 min (n=27), paid run 26.5 min (n=23 DONE). Source and definitions: `master_chat_work/20261030_speed_measure/MEASURE.md:37-76,176`. Stop budgets at two failed core designs and two QC cycles absent a concrete fix.

To reduce tokens without lowering task quality, carry one short idea/core evidence card forward; each worker reads only the current contract, changed-file diff, and a compact prior finding table. Reuse a byte-bound gate result in a QC recheck when the exact tree and checker profile match, per Ayush's 30 Oct speed decision (`decisions.jsonl:550`); still run full gates for full QC. The measured duplicate same-tree outage gate cost ~10 min (`MEASURE.md:194`). Token saving is **UNVERIFIED**: `MEASURE.md:216` says LLM token cost per step was not extracted. Record tokens and phase wall time in the pilot before making a savings claim.
