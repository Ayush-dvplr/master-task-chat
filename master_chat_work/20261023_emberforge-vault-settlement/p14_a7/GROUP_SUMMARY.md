# GROUP SUMMARY: emberforge-a7 (5af6646)

Bundle fingerprint 4bbe6df3514c9a1842ed8eba9f4e70010dc484f1 (repo_head n/a). Details: [A_emberforge-vault-settlement.md](A_emberforge-vault-settlement.md), [B_emberforge-vault-settlement.md](B_emberforge-vault-settlement.md). Local evidence lives in `work/`.

## 1. Table

| task | verdict | overall | tests | rubric | genuine tests lost | genuine judge lost | artefact pts |
|---|---|---|---|---|---|---|---|
| emberforge-vault-settlement (a7, claude-opus-5) | PARTLY | 27.31 | 29.63 (16/54) | 25.0 (3/12) | 20/54 raw (37.0 tests pts) | 9/12 raw (R1, R2, R3) | 0 |

The other 18/54 raw test points (33.3 tests pts) are lost to a graded ambiguity (IN-16). They are not genuine and they are not a run artefact.

Reproduction: `work/score_prog.py` runs the grader's own check functions on the delivered program and gives 16/54 = 0.2963, which matches report.json exactly. A one-line forge-day variant scores 34/54 and the oracle scores 54/54.

## 2. Root cause

Two independent defects. Neither one is L7, L3 or L6.

1. **Salvage-window identity day (18 pts, ambiguity).** `agent_settle.py:733-735` re-resolves each window forge's handle on the salvage day: `identity.canonical(cand["smith_ref"], day) == canon`. The grader (and `solution/solve.py:514, 581-614`) keys each forge by the canonical smith on the forge's own filing day. Changing that one argument to `cand["day"]` makes the program match the grader on 9 of the 10 hidden seasons and on the shipped season (`diff -rq` clean). The 18 points come from 5 whole_* docs and test_live_window_refusals. Example: iso_live_window L0026 (salvage, day 165) names L0016 (forge, day 117, S008). The identity events are merge S008->S030 on day 100 and rename S030->S030-x on day 129. The agent credits the salvage and the grader returns UNCREDITED_SALVAGE.
   - Text the agent followed, rulebook_salvage.md:14-19 (S2): "The canonical smith is the one the salvage's own handle resolves to on the salvage day, and the forge entries are read against that canonical smith whatever handles they were filed under." Together with rulebook_identity.md:14-15 (I1: a rename means the same smith "is known by another from that day forward").
   - Text the grader follows, rulebook_identity.md:32-34 (I3): "A handle filed before a rename or a merge takes effect resolves to whatever it resolved to on that earlier day..."
   - The tiebreak was deleted in harden lp1 r1. Older copies of I3 end: "Two entries filed under the same handle on either side of a rename or merge therefore belong to different canonical smiths." Its removal is recorded at LEVERS.md 'Harden lp1 r1', DESIGN.md:66 and QC_DEFENCE.md:100.
   - The agent saw the fork. Step 22 found "candidate pairs where the two readings disagree: 38". Step 24 built the own-day variant, which reproduces the oracle's shipped figures (credited 37, UNCREDITED 33). Steps 91 and 93 then chose the salvage-day reading on purpose, quoting "whatever handles they were filed under".
2. **Allocator Q5 leak (20 pts, genuine).** This hits forge_a only: allocation total 160 vs 92, and summary/allocation/workshop/guild docs fail. The agent's max-flow `_capacity` lets scarce R02 flow leave through the guild's non-scarce out->sink edge, which breaks rulebook_requisitions.md:26-30 (Q5, "the units granted for that reagent across every requisition may not exceed the vault's closing balance"). For example `_capacity` returns 51 where the true maximum is 48. Then `solve()` fixes RQ05 on a bound that is too high and never checks that the final sum equals the target. The agent's brute-force checks (steps 30 and 63) used shipped balances of about 50000, which never bind Q5 (INFERRED).

## 3. Fairness, per lost item

- **L7 per-unit charge, L3 cap ledger, L6 live window:** 0 points lost. All three were coded correctly at step 15 (lines 592-594, 755, 752) and held in every hidden season. The same is true in both blind solves (blind_r1_settle.py:449-450 and blind_r2_settle.py:362-364 also drop credited forges). The blind-solve note "L6 live window lever caught" is a mis-attribution.
- **Identity day in the S2 window (18 pts):** not fair. All three IN-16 parts hold. (a) It is graded by whole_summary, data_quality, reconciliation, vault_audit, workshop/guild docs and live_window_refusals. (b) Both readings are defensible, and all 3 independent solves (a7 Opus, blind Opus, blind Codex) chose the salvage-day reading. (c) Once the I3 closing sentence is gone, no visible file picks between them, and clerks_digest.md:10-12 even leans towards the salvage-day reading. Precedent: QC_RULINGS IN-16 emberforge v1 salvage FAIL. This rule is also not one of the focal levers; WORK/wrong never measured it (its L4 solver is a different misreading).
- **Allocator (20 pts):** fair. Q5 is stated plainly, the oracle meets it, and the hidden forge_a caps bind the way a real season can.
- **Judge R1-R3 (9 raw pts):** fair as written, because solve.sh:102-132 meets them with built seasons (JD-7). But these criteria reward probing the three levers the agent already got right, and they say nothing about the two rules that actually cost points. The JD-15 ruling on conduct criteria is still pending (PL Q46).

## 4. Score artefacts

None. The program was 0600 at step 16 and the agent ran chmod 644 at step 17. The grader `_stage_program` (test_output.py:2299-2310) runs a 0644 copy as uid 4001 in any case. Every stdout note says "differs", never "settled nothing". There are no tracebacks, timeouts or permission errors, and exception_info is null. The attempt-4 artefact is ruled out.

## 5. Recommendation: FIX, then RERUN

Do not COUNT a7 as lever evidence. Smallest fix: restore one settling sentence for the window identity day, for example the old I3 sentence or an S2 clause like "each forge entry belongs to the canonical smith its handle resolved to on the forge's own day". This is a tiebreak, not a lever explanation. Then rerun the blind solves. The other option is to change the grader to the salvage-day reading, which is a bigger change and removes the fork. Whichever fix is chosen, add the salvage-day window solver to WORK/wrong so that it is measured. Expected effect: 3 solves currently at 16/54 would score about 34/54 (a7) or 15/50 value (blind r1). So the levers L7/L3/L6 are currently worth 0 lost points, and the task's remaining hardness is the allocator plus unrelated slips (INFERRED from the variant runs).

## 6. Open questions

- Fix direction: restore the I3/S2 tiebreak, or rewrite the grader to the reading all 3 solvers chose?
- Should R1-R3 keep probing levers that no solver misses, or point at the rules that actually separate solvers (window identity day, Q5 under binding caps)? This waits on PL Q46 / JD-15.
- Did a7 run on the post-P12 r4/r5 bundle? INFERRED yes from timestamps (test_output.py mtime 23 Oct 17:20 IST; agent start 20:30 IST).
- stacking_check counts structure_* as isolated (31.5% FAIL hint; the corrected figure is 27.8% PASS) and reports "J2 conduct criteria: none" as a false negative. The tool needs a fix.

## Lessons for the master
- A harden pass that removes "giveaway" sentences must be diffed against the graded forks (IN-16). Here the I3 deletion created an 18-point ambiguity.
- Attribute a lost check to a lever only after a one-line variant flips it. The "L6 caught" note was wrong in both blinds.
- Three solvers agreeing on a non-oracle reading is an ambiguity signal, not a hardness signal.
- Hidden seasons with binding scarce caps are what expose allocator bugs. Shipped balances never bind Q5.
- Conduct criteria aimed at levers that every solver holds measure nothing about the real hardness.
