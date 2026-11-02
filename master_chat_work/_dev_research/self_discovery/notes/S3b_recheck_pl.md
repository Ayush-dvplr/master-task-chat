# S3b RECHECK / RECHECK_FIX / PL_NOTE / STACKING_CHECK (grep-based)

Paths relative to master_chat_work/.

## RECHECK r1 counts (20261021/*/recheck_r1/RECHECK.md)
- district :5 "18 REAL, 1 FALSE POSITIVE (CL-2), 2 UNSURE" — row16 JD-15 R4 restate-before-coding preference (04_Judge_QC.md:92); row20 TS-20 weight ordering (03_Tests_QC.md:51).
- emberforge :5 "12 REAL, 0 FP, 0 UNSURE".
- schema :6 "REAL 9, FP 0, UNSURE 1" — row3 AL-27 untriggered precedence rules (05_Alignment_Integrity_QC.md:27); row4 Step 11 seven contract clauses no checker (Final_checklist.md:421); row10 JD-5 compound vs JD-18 multi-facet (04_Judge_QC.md:71 vs :99) = QC rule-internal tension.
- vendor :7 "REAL 26, FP 0, UNSURE 1" — row6 JD-13 weights (04_Judge_QC.md:90).
- Takeaway: first-round QC on our own bundles was ~95% REAL (65 REAL / 2 FP / 4 UNSURE). QC is mostly right; FPs are rare.

## P12 RECHECK_FIX / PL_NOTE
- emberforge p12_r1 RECHECK_FIX:14 W-01-1 FALSE_POSITIVE, cites 01_Instruction_QC.md:19 "Layout is the author's choice..." -> REBUT. :19 "REAL 6, FALSE_POSITIVE 1". TS-19 kept (shipped season presence-only on purpose so answer not in grader); JD-16 R10 network warn kept.
- emberforge p12_r2 RECHECK_FIX:11 JD-16 R9 FALSE_POSITIVE citing 04_Judge_QC.md:97 "Scope over undeclared paths is invisible to the verifier, so the judged channel owns it ... Warn rather than fail". :13 "REAL 2, FALSE_POSITIVE 1". Fixed key order promised ungraded, A2/A4 edges missing.
- emberforge p12_r3: ORACLE BUG — allocated units kept only last requisition; "no graded season had a workshop with two requisitions, so the wrong oracle still scored 1.0"; engine dropping sum loses 10/101.
- schema p12_r1: TS-13 split makes tests "marginally easier (+2/137)"; TS-23 45 checks warn kept.
- schema p12_r2: 9 REAL (regressed from 1 fail to 5), AL-27 bool cast, M5 IN-16.
- schema p12_r3 RECHECK_FIX:9 AL-27 REAL: before fix one-rule-broken variants scored 0.9926-1.0; after triggers added inside composed gadgets, 0.66-0.74 ("harder (each rule now costs whole worlds)"); isolated share 22.6%. Weights only 1/3/5 ("kit allows weights 1, 3 and 5 only").
  -> AL-27 (QC) is the one QC rule that directly made the task HARDER: it forces every stated rule to have a graded trigger.
- vendor p12_r1: 8 real; AL-2 "one line saying how you got it" promise -> new w1 criterion; kept instruction clause because deleting it leaves 7 criteria, below minimum 8; AL-27 reserved bytes fixture.
- vendor p12_r2: TS-16 dead negative kept because validate_bundle 11.5 strict fails without it (CONFLICT kit validator vs QC TS-16); oracle x5 (kit) vs x3 (Ayush).
- vendor p12_r3: DS-4-1 neutral ids cap-00001, JD-15-1, TS-16-1 fixed; DS-20-1, DS-6-1, X1 kept.
- cohort p12_r1 PL_NOTE: 9 real; oracle rewritten as own implementation (shares 2% lines with verifier vs 16%); R4 13->14 (judge figure was wrong vs oracle).
- cohort p12_r2: TS-13 KEEP (fixing pays 6/71 to programs with no cohort right); TS-29. PL_NOTE lesson: "Minor findings that only ask for a written note are cheaper to fix than to defend".
- dispatch p12_r1 PL_NOTE: W9 X1 binary info-only; JSON compared by value+type; R9 code quality.
- dispatch p12_r2 PL_NOTE: TS-19 rebut citing 03_Tests_QC.md:50 "a promise may legitimately be graded by a judged criterion"; IN-15 __import__ negative narrowed; JD-7 reference solver split (functions 423/334 lines -> 40); AL-28 writes-outside negative narrowed; oracle x5 vs x3.
- district p12_r1: DS-27, TS-25 canonical check passed on {} (fixed); JD-18 R7 -> -1 penalty.
- district p12_r2: TS-23 38 checks kept; merging would violate TS-13 (QC TS-23 vs TS-13 conflict); JD-18 R9 weight 1 vs QC proposal weight 3 compound (JD-5 vs JD-18).

## STACKING_CHECK (20261023)
- cohort p12_r2 STACKING:58/71-73 "G3: isolated+mutation 29.6% (<= 30%), whole-document 60.6% (>= 50%), shipped-only 1.4% (<= 5%)" — the gate counts isolated+mutation together (d87 notes LEVER_RULES G3 says isolated-only; no change decided). All three cohort/district/vendor sit just under 30% (29.6, 26.5, 28.0) = designed to the threshold.
- district p12_r2 STACKING:62 reflex a4 program "earned 20 of 113 = 0.1770"; :118 whole 69.9%, isolated+mutation 26.5%, shipped 3.5%; tests 38 (QC warn >35 kept); :120 "STACKING PASS".
- vendor lp1 STACKING:55 isolated+mutation 28.0%; :92 L2s signed everywhere single-misread 0.6636.
- cohort harden_r2 STACKING:55 "S4 careful (L2a + L2b + L3b + L4b) | 0.1690 (12/71)" — S4 is a self-built guess of careful agent, the same instrument that under-predicted by 0.25-0.77 earlier.
- Note: reflex scores (0.0563/0.1682/0.177) replay the PREVIOUS agent's program (written against old docs) on NEW tests; they measure that the tests changed, not that a fresh agent reading new docs fails. UNVERIFIED as a difficulty predictor; same class as S4.

## Derived
- 3b-a: QC is ~95% REAL on first pass; total FPs across all P12 rounds found = 3 explicit (W-01-1, JD-16 R9, CL-2) + UNSURE handful. Defending is cheaper only with exact kit line quote.
- 3b-b: QC rule-vs-rule tensions: TS-13 (one property per test) vs TS-23 (too many tests) vs rule 6 whole-doc; JD-5 compound vs JD-18; kit validator 11.2/11.3/11.5 vs TS-16 dead negatives; criteria minimum 8 vs AL-2.
- 3b-c: oracle bugs survive when the graded data never exercises the case (emberforge p12_r3) — same mechanism that lets agent bugs survive: coverage, not levers.
- 3b-d: AL-27 trigger requirement measurably raises per-rule cost (0.97-1.00 -> 0.66-0.74).
