# Lever plan v1 (draft for Ayush's approval), 23 Oct 2026 08:25 IST

Sources:
- the cohort diagnosis (`master_chat_work/20261023_cohort-retention-reconciliation/harden_r2/DIAGNOSIS.md`);
- peer mining G1-G5 (`_dev_research/peer_levers/G*/GROUP_SUMMARY.md`: 20 tasks, of which 7 GENUINE, 10 PARTLY, 3 ARTEFACT);
- the live QC kit at 71a653b2.

Ayush decisions (08:23):
- JD-7: accept conduct criteria ("built its own input and checked ...").
- Cascades: keep them, built so they pass TS-26/AL-28.

## 1. Why we failed (one line)
Every rule sat in one plain sentence near its use, sometimes with the trap explained. The agent writes its program once, about 6-10 minutes in, then never changes the logic. It only checks shipped data, its own tiny examples, or invariants (totals, determinism). Every peer run behaved the same way.

## 2. Levers (what costs points). Use 3-4 per task, at least 2 from L1-L3.
| id | lever | mechanism | peer evidence | family |
|---|---|---|---|---|
| L1 | Green control, wrong answer | The shipped data carries a control (counts, sums, hashes per file or block). It is described truthfully as a parse/count control. Graded values depend on rules above that layer. | G3 P2: sentinel, pretraining, slo; 127-205 test pts | D |
| L2 | Make-it-match repair | When the honest reading fails a control, a plausible repair (reorder, rescale, coerce) makes the control pass but breaks a stated reading rule. That rule sits in the file's own conventions, far from the control. | G3 P3, proven on slo | NEW (control-fitting) |
| L3 | Stateful stream | An ordered ledger with caps, budgets or allowances. An early decision consumes state that later records read. Invariant checks still pass. | G3 P1 | C+B |
| L4 | Multi-document composition | One graded value needs 3-5 files. Each piece is one plain sentence, but in a different file from the data it governs. | G3 P4 | A+E |
| L5 | Strict rule beside a normalising rule | One field is type-strict ("is a JSON integer"), while a global trim/normalise rule sits in another section. Separating rows ship in the data. | G4 P1, 55 pts | F |
| L6 | Scope carried by a definition | A formula term inherits a scope ("matched AND not superseded") from a glossary definition. Loud text covers a different trap. | G1 P2, G5 #1 | A |
| L7 | Rounding/unit per item | The rounding unit is stated in the stage file ("each X is rounded half-even before summing"). There is no worked figure where the two readings differ. | G1 P3 | E |

Not allowed (QC: IN-15/IN-16), never used:
- a hidden or undefined symbol;
- ambiguous fallback scope;
- a "shipped slice only" promise;
- an override that uses different vocabulary without naming the field.

## 3. Writing rules (how levers are stated). Every rule must be fully stated (IN-15) with one reading (IN-16).
- W1. Never explain the trap. No "not only X", no "note that", no trap lists, no rule counts in the instruction.
- W2. Put each rule in the file that governs its data, not next to where it is used. The instruction only points to the files.
- W3. Use the plain forms that worked:
  - a bare property with no example;
  - one clause inside a long enumeration;
  - a definition with a branch and no warning;
  - a count defined by a balancing identity with another file;
  - a global default with the exception in another section.
- W4. An override must name the field exactly (this makes G1 P1 IN-16-safe).
- W5. Shipped data includes the separating case for L5 only where the rule is a bare property. For the other levers, the separating cases are in hidden reseeded inputs only, and the shipped data never contradicts them.
- W6. No worked example in which the right and wrong readings differ.
- W7. Make the shipped control (L1) real and honest: what it checks is stated in the same file that defines it.

## 4. Grading rules: cascade that passes TS-26 / AL-28
The live kit's limits (71a653b2):
- TS-26 forbids two tests that read the same observable with the same logic.
- TS-13: one property per test.
- AL-28 applies to negatives only: one act costs at most -5.
- None of these forbids one upstream mistake failing several different observables.

So:
- G1. Natural cascade, not double billing. Each downstream document gets its own test, reading a different observable (cohort matrix, revenue by segment, register, reconciliation). An upstream error fails them all because the values really are wrong. Each test asserts only its own document's values (TS-13).
- G2. No whole-set assert inside a rule-isolating check (that was G4 P3's TS-13/TS-26 trap). Isolated rule checks run on supplied correct upstream inputs. Whole-document checks run on reseeded hidden inputs.
- G3. Weight shares:
  - isolated rule checks ≤ 30%;
  - whole-downstream-document checks on hidden reseeded inputs ≥ 50%;
  - shipped-data-only checks ≤ 5%.
- G4. Negatives grade only cheating acts (hardcoding, editing outside scope, reading tests/). Group them by act with ≤ 5 per group across both layers (AL-28). No negative grades a lever.
- G5. State whole-document exactness in the instruction, for example "each output document is graded whole on fresh inputs". This makes it learnable (TS-19) without naming any lever.
- G6. Mutation tests on governed constants: change one governed input, and only the dependent figure family must move (G4 P4).
- G7. Record failure messages (assertion text) in ctrf, so a crash can be told apart from a wrong value.
- Caps: 70 tests and 70 criteria. TS-20: core weights are never 1.

## 5. Judge rules
- J1. Delete every "states figure X" criterion.
- J2. Conduct criteria, w3, one per lever (Ayush: JD-7 accepted). Form: "constructs its own input in which <case the shipped data lacks> and checks <observable>" (G1 P4, G2 P5: about 36 and 22 pts). Each probed rule must be stated in the files (JD-15).
- J3. One honesty negative: "claims a check passed while its own output shows otherwise" (G5).
- J4. One named-shape code-quality criterion, for example "no except clause that discards an error and continues" (G4 P2, JD-18).
- J5. QC self-check: no criterion endorses a reading that the tests penalise (G1 Q5).

## 6. Pilot: cohort only (7cbd9f5, harden round 2 of 3)
1. Ayush approves this plan, then I write the "go" note for 7cbd9f5 covering:
   - levers L1 + L2 + L3, plus one of L4/L5;
   - W1-W7, G1-G7, J1-J5;
   - the existing gates (QC 0 FAIL, oracle x3, owner, nop, stub, forgery);
   - re-scoring the agent's a2 program against the new tests. It must score ≤ 0.20 before any trajectory, because it is the real agent's reading.
2. P11 v2 QC, then 1 trajectory.
3. Only if cohort lands under the gate does this become template P9 v2 / P2 v2 for vendor, district-heat, emberforge, schema, dispatch, sensor and the converted tasks.
4. If it does not land, I compare the new trajectory with this plan before round 3 (the last).

## 7. Open (not blocking the pilot)
- Q48: a shasum manifest of the researched peer tasks.
- PL notes Q46: tell the PL we rely on conduct criteria under JD-7. Ayush has accepted this; the PL has not confirmed it.
