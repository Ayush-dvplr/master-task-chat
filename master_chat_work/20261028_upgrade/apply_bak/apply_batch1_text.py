"""Batch 1 text edits (C1 gate, C2 aims, C3 lever table, A7 regrade exception, A3 freeze rule). Each replacement must match exactly once."""
import pathlib, sys
T = pathlib.Path("/Users/mac/Desktop/Terminal Bench"); MT = T/"master_chat_tasks"
LR = MT/"knowledge/LEVER_RULES_v3.md"; KN = MT/"knowledge/KNOWLEDGE.md"; CR = MT/"prompts/templates/_COMMON_RULES_v5.md"
PV = T/"master_chat_work/_dev_research/pipeline_v4/PLAN.md"; AP = MT/"auto/AUTO_POLICY.md"; GO = MT/"GOALS.md"
TAG = '[v3.7 Ayush 28 Oct "Target <40 now"]'
OLD36 = ('[v3.6: Ayush 27 Oct 22:30, new gate tests < 85, rubric < 85, final < 50] See LEVER_RULES_v3 1C v3.6 bullet: a test lever now costs 25-40% of positive test points, and a plain first-write program and the all-but-one program aim at tests <= 75. Blind bar: each of the 3 fresh blind reads scores tests <= 80, its losses WRONG output or v3.5 hidden-scale loss. Judge: probe band with predicted probe mid 15-20. Overnight auto runs: the master may send "go" at DESIGN READY when the kill table passes (every generic solver and every blind program loses >= 15% of lever points, shipped inputs fast, reference <= 1/4 of the stated limit); otherwise Needs Ayush.')
AIMS37 = ('[v3.7 Ayush 28 Oct "Target <40 now", gate tests < 85, rubric < 85, final < 40; replaces the v3.6 bracket] See LEVER_RULES_v3 1C v3.7 bullet: plain first-write and all-but-one programs aim at tests <= 60. Blind bar: each of the 3 fresh blind reads scores tests <= 65 (none above 70), its losses WRONG output or v3.5 hidden-scale loss. Judge: probe band, predicted probe mid <= 20. DESIGN READY needs, in DESIGN.md: (a) predicted final = (predicted first-write tests + predicted judge mid)/2 <= 35; (b) lever share >= 40% of positive test weight (held-out w5 tier >= 50% in the N2 shape); (c) no blind program above tests 65; (d) verifier worst case <= 90% of the stated verifier limit; (e) kill table unchanged: every generic solver and every blind program loses >= 15% of lever points by WRONG output (or v3.5 hidden-scale loss), shipped inputs fast, reference <= 1/4 of the stated limit. Overnight auto runs: the master may send "go" at DESIGN READY; otherwise Needs Ayush.')
LR37_BULLET = ('- [v3.7: Ayush 28 Oct "Target <40 now"; upgrade plan v2 C2, 29 Oct] Replaces the v3.6 bullet above. Plain first-write and all-but-one programs aim at tests <= 60. Blind bar: each of the 3 fresh blind reads scores tests <= 65 (none above 70), its losses WRONG output or v3.5 hidden-scale loss. Judge: probe band, predicted probe mid <= 20. DESIGN READY needs, in DESIGN.md: (a) predicted final = (predicted first-write tests + predicted judge mid)/2 <= 35 (5 points margin for the final spread; same-bytes spread, section 6 v3.4 bullet); (b) lever share >= 40% of positive test weight (if the lever is fully lost and all else passes, tests <= 60), with the held-out w5 tier >= 50% when the N2 shape is used; (c) blind ceiling: no blind program above tests 65; (d) verifier worst case <= 90% of the stated verifier limit; (e) the kill table rule (every generic solver and every blind program loses >= 15% of lever points by WRONG output, or v3.5 hidden-scale loss; shipped inputs fast; reference <= 1/4 of the stated limit) unchanged. Overnight go at DESIGN READY unchanged. Evidence: final < 40 needs tests + rubric < 80; our 10 valid gate runs mean tests 78.7, rubric 23.5, 1 below 40 (upgrade R3 FINDINGS:137).')
GATE37 = ('tests < 85 AND rubric < 85 AND final reward < 40 on 1 valid run of the frozen QC-passed bytes before push (v3.7, Ayush 28 Oct "Target <40 now"; was 50 under v3.6, Ayush 27 Oct 22:20; was tests < 100 AND final < 70 before). Final = (tests + rubric)/2, so final < 40 needs rubric < 80 - tests; design for tests <= 60 and rubric <= 20.')
REGRADE_EXC = ('[v3.7 regrade exception, Ayush 28 Oct Q1] A regrade counts as push evidence only when the edit touches judge files only (no tests/, no instruction, no environment), the run was valid, Ayush wrote OK for this regrade (verbatim in decisions.jsonl), and the regraded run is repackaged with `master_chat_tasks/tools/repackage_one.py` (A4). Otherwise diagnostic only, never packaged.')
LEVER_TABLE = '''### 1D. v3.7 lever status table (29 Oct; upgrade plan v2 C3, Ayush 28 Oct Q10; evidence: upgrade R3 hardness.md check + R4 teammate repo mining, numbers re-run by V1)

| Lever | v3.7 status | Evidence | How to use |
|---|---|---|---|
| L2 held-out instances (Shape D, 1C) | PROVEN | shipped 62% vs held-out 42% pass, at w5 43% vs 23%; within-author r_tests -0.43 (R3); Hard/Expert hidden share 0.68 vs 0.16-0.18, hidden pass 0.01 (R4 contrast) | default test lever; G3/G5, 0b, W5 BRANCH_FIRE |
| L6 process criteria / probe band (J2, P-a..P-h) | PROVEN | verify criteria 52% vs read 24%; our gate runs mean rubric 23.5 (R3) | every judge; mid <= 20 |
| N2 held-out w5 tier >= 50% of positive test weight | PROMISING (pilot) | 8 tasks mean 34.8, 5 < 40; cur90 9 tasks mean 32.8 (R3); R4 hidden share >= 0.5 median 35.7 vs 56.5 | default shape for the next new build (C4 pilot) |
| N1 pair channels (held-out w5 tier + probe band) | PROMISING (pilot) | halves anti-correlated r -0.40, -0.32 within author (R3) | same pilot as N2 |
| L1 / LC2 weight on w5 (shipped w1, hidden w5) | PROMISING, amplifier only | within-task 73/83 but r weakens within author (R3); R4 top1 share no signal | only on a held-out core via TS-20; never reweight after a run |
| L4 exact published contract | PROMISING, multiplier | R3 | with G1 + CL-4 |
| LC1 bounded induction (finite stated domain, unique fit per hidden instance) | PROMISING (second pilot) | 59417607, aa314fee (R4 cards) | legal only if the domain is stated and EVIDENCE_MAP lists it (Never 6); one unlabelled witness max (Never 11) |
| LC3 counterfactual what-if figures in judge (J11) | PROMISING | 59417607 7/8 wrong, aa314fee 8/8 (R4) | questions stated in instruction, 4-8 what-ifs; headline figures leak (LEAK_LIBRARY) |
| LC5 per-field-class authority order | PROMISING (needs pilot) | df8f123b only (R4) | each class order written once (Never 8) |
| LC6 hazard-slice tests (T1) | PROMISING | 80202e15, 9f5486ac (R4) | avoid a global HELD gate |
| L3 interlocking inputs / LC4 never-healing state | WEAK | regex-only signal; our L4 multi-doc leaked (CR-5, 1C) (R3); R4 LC4 from 2 tasks | only inside a held-out tier |
| L5 trap tiers | WEAK | 92-96% from 6-10 tasks; habit levers leaked (R3) | hidden-only fixtures (S6) |
| L7 honesty negatives as hardness | WEAK (keep as integrity) | 5.4% of judge points (R3) | keep J3a-c, do not budget points |
| L8 determinism, L9 reward geometry, N3 small judge total | WEAK | 0.9% / structural (R3) | G6 minimum only |
| Unbounded induction (forms/meanings unstated) | FALSE | flagged 5b2b0901, 8defd7be, d49e259f (R4 genuineness.md); breaks Never 6 | never |
| Instructed effort caps (e.g. "stop at 1500 s") | FALSE | 5b2b0901 instruction.md:36 (R4); agents used median 23% of budget | never |
| Judge-only band (tests near 100, judge negatives) | FALSE | 725e575c tests 96.55, judge -25 (R4); blocked by tests < 85 | never |
| Weight concentration (top-1 check share) | FALSE as a standalone lever | R4 top1 ~0.05 no signal | amplifier only via L1 |

Sources: `master_chat_work/20261028_upgrade/R3_hardness_md/{FINDINGS.md,claims.csv,levers.csv}`, `R4_teammate_repo/{FINDINGS.md,contrast.md,genuineness.md,cards/}`. Promotion rule: PROMISING -> PROVEN needs 2 of our tasks meeting the proof bar on frozen bytes (C4: tests <= 60 and rubric <= 20 on 1 valid run, and 2 of 3 blind reads lose >= 40% of positive test weight on the held-out tier while passing shipped checks). R3 and R4 disagree on interlocking: WEAK (R4 support 2 tasks; our L4 multi-doc leaked); LC4 may be tried only inside the N2 pilot's held-out tier.

'''
FREEZE = ('Freeze (v3.7, upgrade A3): at every freeze the master runs `python3 master_chat_tasks/tools/status.py set <slug> tree_sha=<12 hex>`, tree sha = in the bundle dir `find . -type f | LC_ALL=C sort | xargs -I{} shasum -a 256 "{}" | shasum -a 256 | cut -c1-12`; intake.py refuses `gate_run`/`ql_rerun` rows when the bundle sha differs from the registry or the field is empty.')

edits = [
 (MT/"tools/lever_dose.md", "overall < 50 on a real trajectory; gate v3.6 27 Oct 22:20", "final < 40 on a real trajectory; gate v3.7, Ayush 28 Oct \"Target <40 now\""),
 (KN, '4. Next step (gate v3.6, Ayush 27 Oct 22:20 "new gate is test < 85 , rubrics < 85 and overall < 50"): ', '4. Next step (gate v3.7, Ayush 28 Oct "Target <40 now": tests < 85, rubric < 85, final < 40): '),
 (KN, "but rubric >= 85 or final >= 50 -> judge probe band (mid 15-20) + penalties, and more test lever if rubric alone cannot reach final < 50 (final", "but rubric >= 85 or final >= 40 -> judge probe band (mid <= 20) + penalties, and more test lever if rubric alone cannot reach final < 40 (final"),
 (KN, "Regrade (`harbor trials regrade SOURCE -p TASK`) is diagnostic only, run when Ayush asks; never push evidence, never packaged (package_rfp_bundles.py:73 copies scores).", "Regrade (`harbor trials regrade SOURCE -p TASK`) is diagnostic only, run when Ayush asks; never push evidence, never packaged (package_rfp_bundles.py:73 copies scores). " + REGRADE_EXC + "\n" + FREEZE),
 (MT/"knowledge/INDEX.md", "| v3.6 27 Oct 22:30: gate tests<85/rubric<85/final<50, lever 25-40%, blind <=80, judge mid 15-20.", "| v3.6 27 Oct 22:30: gate tests<85/rubric<85/final<50 (history), lever 25-40%, blind <=80, judge mid 15-20. v3.7 29 Oct (Ayush 28 Oct \"Target <40 now\"): gate final<40, aims tests<=60, blind<=65, judge mid<=20, DESIGN READY (a)-(e), section 1D lever table, regrade exception; old text LEVER_RULES_v3.6_snapshot.md."),
 (LR, "Lever cost 25-40%, first-write aim tests <= 75, blind bar tests <= 80, judge mid 15-20, master go overnight (1C v3.6 bullet).", "Lever cost 25-40%, first-write aim tests <= 75, blind bar tests <= 80, judge mid 15-20, master go overnight (1C v3.6 bullet). v3.7 29 Oct (Ayush 28 Oct \"Target <40 now\", upgrade plan v2): final gate tests < 85 AND rubric < 85 AND final < 40 (section 6); aims tests <= 60, blind <= 65 (none > 70), judge mid <= 20, DESIGN READY (a)-(e) (1C v3.7 bullet); lever status table 1D; regrade exception (section 6). Old text: LEVER_RULES_v3.6_snapshot.md."),
 (LR, "- [v3.6: Ayush 27 Oct 22:30, new gate tests < 85, rubric < 85, final < 50] Overrides", "- [v3.6: Ayush 27 Oct 22:30, new gate tests < 85, rubric < 85, final < 50; SUPERSEDED by the v3.7 bullet below] Overrides"),
 (LR, "reference <= 1/4 of the stated limit); otherwise Needs Ayush.\n", "reference <= 1/4 of the stated limit); otherwise Needs Ayush.\n" + LR37_BULLET + "\n"),
 (LR, "\n### 1b. Opus-habit bank", "\n" + LEVER_TABLE + "### 1b. Opus-habit bank"),
 (LR, "tests 80 needs rubric < 20). Tasks that met the old gate", "tests 80 needs rubric < 20). [v3.7: Ayush 28 Oct \"Target <40 now\"] REPLACED again: the final gate is " + GATE37 + " Tasks that met the old gate"),
 (LR, "`harbor trials regrade` of a saved run is a diagnostic Ayush may run; it is never push evidence and never packaged.", "`harbor trials regrade` of a saved run is a diagnostic Ayush may run; it is never push evidence and never packaged. " + REGRADE_EXC),
 (CR, OLD36, AIMS37),
 (CR, "- Gate for real model runs (QL 26 Oct 18:55, D2 reverted; Ayush 27 Oct 17:17): tests < 85 AND rubric < 85 AND final reward < 50 on 1 valid run of the frozen QC-passed bytes before push (gate v3.6, Ayush 27 Oct 22:20 \"new gate is test < 85 , rubrics < 85 and overall < 50\"; was tests < 100 AND final < 70). Final = (tests + rubric) / 2, so final < 50 needs rubric < 100 - tests (tests 80 needs rubric < 20; tests 70 needs rubric < 30).", "- Gate for real model runs (QL 26 Oct 18:55, D2 reverted; Ayush 27 Oct 17:17): " + GATE37),
 (CR, "`harbor trials regrade` is a diagnostic only, never push evidence.", "`harbor trials regrade` is a diagnostic only, never push evidence. " + REGRADE_EXC),
 (CR, "never package a regrade).", "never package a regrade, except under the v3.7 regrade exception above)."),
 (MT/"prompts/templates/P2_build_v5.md", OLD36, AIMS37),
 (MT/"prompts/templates/P9_harden_from_results_v4.md", OLD36, AIMS37),
 (AP, "| Accept minors as PL notes, freeze (record tree sha), then", "| Accept minors as PL notes, freeze (record tree sha: `status.py set <slug> tree_sha=<12 hex>`, v3.7 A3), then"),
 (AP, "| Run: tests < 85 AND rubric < 85 AND final < 50 (gate v3.6, Ayush 27 Oct 22:20) |", "| Run: tests < 85 AND rubric < 85 AND final < 40 (gate v3.7, Ayush 28 Oct \"Target <40 now\") |"),
 (GO, OLD36, AIMS37),
 (GO, "tests < 85, rubric < 85, overall < 50 (gate v3.6, Ayush 27 Oct 22:20 \"new gate is test < 85 , rubrics < 85 and overall < 50\"; was tests < 100, rubric < 100, overall < 70).", "tests < 85, rubric < 85, final < 40 (gate v3.7, Ayush 28 Oct \"Target <40 now\"; was 50 under v3.6 27 Oct; was tests < 100, rubric < 100, final 70 before)."),
 (MT/"state.json", '"test_phase_gate": "tests<85, rubric<85, overall<50% (Ayush 27 Oct 22:20; was tests<100, rubric<100, overall<70)"', '"test_phase_gate": "tests<85, rubric<85, final<40 (v3.7 Ayush 28 Oct \\"Target <40 now\\"; was 50 under v3.6 27 Oct; was tests<100, rubric<100, 70 before)"'),
 (PV, OLD36, AIMS37),
 (PV, "Gate (v3.6 27 Oct 22:20: tests < 85 AND rubric < 85 AND final < 50) met", "Gate (v3.7 Ayush 28 Oct \"Target <40 now\": tests < 85 AND rubric < 85 AND final < 40) met"),
 (PV, "tests < 85, rubric >= 85 or final >= 50 -> judge band (mid 15-20) + honesty negative, plus more test lever if needed (gate v3.6).", "tests < 85, rubric >= 85 or final >= 40 -> judge band (mid <= 20) + honesty negative, plus more test lever if needed (gate v3.7)."),
 (PV, "3. **Next step (gate v3.6):** tests >= 85 -> new test lever; tests < 85 and (rubric >= 85 or final >= 50)", "3. **Next step (gate v3.7):** tests >= 85 -> new test lever; tests < 85 and (rubric >= 85 or final >= 40)"),
 (PV, "| 5 | Way A (harbor trials regrade of a saved run) = diagnostic only, never push evidence. |", "| 5 | Way A (harbor trials regrade of a saved run) = diagnostic only, never push evidence. " + REGRADE_EXC + " |"),
 (PV, "Regrade (`harbor trials regrade`) is optional, run by Ayush when he wants to see a change on the old run; never push evidence.", "Regrade (`harbor trials regrade`) is optional, run by Ayush when he wants to see a change on the old run; never push evidence. " + REGRADE_EXC),
 (PV, "does not know regrade output: never package a regrade.", "does not know regrade output: never package a regrade, except under the v3.7 regrade exception (decision 5) via `master_chat_tasks/tools/repackage_one.py`."),
]
texts = {}
for f, old, new in edits:
    s = texts.get(f) or f.read_text()
    n = s.count(old)
    if n != 1:
        print(f"FAIL count={n} in {f}: {old[:90]!r}"); sys.exit(1)
    texts[f] = s.replace(old, new)
for f, s in texts.items():
    f.write_text(s); print("wrote", f.relative_to(T))
