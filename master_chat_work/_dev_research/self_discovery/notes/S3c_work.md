# S3c bundles/_work/<slug>/{LEVERS,QC_DEFENCE,DESIGN}.md (grep + targeted reads)

Base: master_chat_work/bundles/_work/ (prompt said bundles/_work; actual path is under master_chat_work).

## Self-labelled HIDDEN-ONLY vs outcome
- district LEVERS_r1.md:57-66 every r1 lever HIDDEN-ONLY except H04/DH-3; DESIGN.md:312 "S2 0.592, S4 1.0, every lever HIDDEN-ONLY on the data" — and real a-runs: v1 timeouts, a4 100/100. HIDDEN-ONLY label did not predict failure.
- district LEVERS.md:36-55 lp1 table: HIDDEN-ONLY / DERIVABLE per flag; weights lost 20-63 of 100 per single misread (self-measured, not a real run).
- vendor LEVERS.md:75 "Each counted lever is HIDDEN-ONLY"; DESIGN_SUMMARY.md:12 same — HARDNESS VH:73 later found W-VA2 DERIVABLE (4688 visible captures); a2 real run 100/100.
- vendor DESIGN.md:153-158 "Hidden-only is necessary but NOT sufficient. district-heat: every lever was hidden-only yet a solver right on each documented rule in its own one-rule case scored 1.0. So each lever below names the NATURAL CODE STRUCTURE that produces the reflex ... EVERY hidden separating case combines the lever with at least one other rule whose text lives in a DIFFERENT spec file ... Rules stay stated plainly". Outcome: vendor v0 real tests 88.97, a2 100. Cross-file conjunction of plainly stated rules leaked.
- vendor DESIGN.md:150 "The instruction says the contract has N rules to apply" (= study rule 1 violation, confirmed by SYNTHESIS :41 "fifteen rules").
- emberforge LEVERS.md:17-18 isolated rules + structure "paid to S4" (23 pts); :22 every LV-EF-1..4 HIDDEN-ONLY; no real run after r2.
- cohort LEVERS.md:81 "a2 program 0.0563, S2 0.0563, S4 0.1690 ... S3: L1a 0.85, L1b 0.89, L2none 0.24 ... L4b 0.77" — only L2 (make-it-match) costs much single.
- Targets in DESIGN files: dispatch DESIGN.md:21 "careful solver 0.10 to 0.20"; schema DESIGN.md:192 "careful agent aim 0.10 to 0.20 rests on missing two or more"; sensor DESIGN.md:17 "careful solver missing one lever about 0.08-0.13"; vendor DESIGN.md:4. No real trajectory ever landed in 0.10-0.20 (the only real sub-0.5 tests results are permission artefacts or dispatch 0.30 tests with chmod artefact).

## QC_DEFENCE patterns
- Every lever entry carries a pre-written "Safe fix" that weakens the lever if QC insists (e.g. district N1 "add 'it does not check any reading rule' to its header", N3 "add the sum ... to section 6. That weakens W2", vendor H1 "add '(see Field names for count fields)'", H4 "add 'a string is never a JSON boolean'... loses some bite"). Pattern: each defended lever is one QC finding away from becoming an explicit sentence beside its use — the exact leak mechanism (DIAG C3:57, VD:36).
- district D1 (QC_DEFENCE:60-63) instruction names no rule, size, time limit; schema.md authority — IN-8 risk defended by "a specification the instruction points to".
- district N5 (:124-126) rules in data-file comments, made binding by schema.md:4-6 — IN-8 defended.
- district N6 / vendor H5 (:193-199) conduct judge criteria R1-R4 "builds its own ... and compares", w3, accepted by Ayush under JD-7. CONFLICT with goal: these pay exactly the careful-agent habit (synthetic extract self-tests, step 14-16 cohort, 25-32 vendor, 22-24 district). They raise rubric for careful agents -> rubric<100 gate harder to hit. UNVERIFIED (judge not run after lp1).
- district N7 / vendor H6 (:201-204) G7 failure messages must go in ctrf vs rewardkit 0.2.1 Score has no message field + normalize_ctrf.py drops message + tests_qc B4 forbids /logs/verifier -> printed [check] lines. Kit-vs-tooling conflict.
- district P12 r2 D10 (:136) TS-23 warn (38 checks) vs TS-13 (fold = 4 properties in one check) -> kept.
- district D11 (:137) JD-18 positive code quality vs QC proposal compound w3 'no dead blocks, bare except, debug prints' = absence-shaped (JD-15) + multi-property (JD-5).
- district D6 (:84-85) R7 'names specific exception type in every except' pays a program with no except = absence (04_Judge_QC.md:54) -> made negative.
- district D3 (:72-73) TS-25 canonical check passed on `{}` -> fixed (also cohort C2:119 stub 0.0333 same bug class).
- district D9 (:95) DS-27 "The judge was not run here" process narrative in TRUTH.md -> removed.
- dispatch QC_DEFENCE sections: "validate_bundle advisory fails left as is" (:34), "Handbook line count is a graded value (P12 lesson)" (:49), "Lot tie wording" (:20).
- schema QC_DEFENCE :51 "No fault list in agent-visible files"; :56 46 checks above 35; :61 tests carry own reference pipeline; :78 verifier network allowlist OpenAI only.
- sensor QC_DEFENCE: 1 H1 rule split schema.md + station_registry.csv; 2 H1 omits angles (scope by omission); 3 H2 differs on 1-3 rows; 6 almost all weight hidden; 7 judge figures absent from all files; 8 grader kills by uid.

## Derived
- 3c-a: Our own HIDDEN-ONLY/DERIVABLE label is computed on shipped data vs reflex code we imagine; agents beat HIDDEN-ONLY levers by synthesising extracts from the stated rules. The label measures data, not text; text is what the agent reads.
- 3c-b: "Rules stay stated plainly" (vendor DESIGN:158, IN-15/DS-21/DS-25) + "hidden composition" is the central tension: whenever a composition was stated as a sentence, it leaked (emberforge LV-EF-1, vendor, cohort CR-5); the one that held (EF L7) was the composition that was NOT written as a sentence (only implied by two rules in different files).
- 3c-c: Conduct judge criteria reward careful-agent habits; if aim is rubric<100 they work against it.
