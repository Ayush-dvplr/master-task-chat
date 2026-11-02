# Proposed rules (22), ranked by evidence

The evidence weight puts real-trajectory results above replays and mutants, which sit above design claims. Each rule lists its findings (F-NN in `FINDINGS.jsonl`) and its target template:
- P2 = lever design
- P4 = build / data
- P9 = harden / diagnose
- P11 = QC run
- P12 = QC fix
- round_notes
- QC_DEFENCE

## Tier 1: backed by real runs
**1. A lever is an interaction, not a sentence.**
- Rule: every counted lever must be a situation where two or more plainly stated rules combine (or a stated rule meets a rare exact tie or boundary), and where the natural code shape gives a wrong answer that is still internally consistent. Example shapes: an if/elif early return, a DP keeping the later tie, a single cumulator.
- Never write the composition itself as a sentence. Each component rule stays explicit, which satisfies IN-9 and AL-4.
- Findings: F-01, F-02, F-11, F-28, F-25, F-55, F-58. Target: **P2 §lever definition**; QC_DEFENCE (cite IN-9: each component is discoverable).

**2. Do not ship the separating situation class.**
- Rule: for each lever, list the situation classes it needs (two refusals on one item, an exact tie, an empty run, a label-only set). The shipped data and examples must contain none of them, but must exercise each component rule on its own.
- Hidden worlds are drawn to contain them.
- Findings: F-03, F-01, F-17, F-29. Target: **P4 §data generator**; P2.

**3. Nothing shipped may confirm the full answer.**
- Rule: no answer key, PASS band, calibration bundle, assumptions block, or "unique surviving draw".
- Shipped examples cover the common path only, so that reproducing them byte for byte proves nothing about the levers.
- Findings: F-15, F-22, F-24. Study rule 7. Target: **P4 §shipped artefacts**; P11 check.

**4. Stop calling a lever "held" or "HIDDEN-ONLY" without a real trajectory.**
- Rule: a status of held requires a claude-opus-5 run in `jobs/` with ctrf plus reward-details. Replays of old programs, S4 solvers and mutants are labelled "replay" and never quoted as difficulty.
- Update `registry/levers.json` after every real run.
- Findings: F-13, F-30, F-31, F-34, F-19. Target: **P9 §verdict**; round_notes.

**5. Measure difficulty before QC polish, and after every harden round.**
- Rule: order the work as harden → real trajectory → QC → fix → one confirming trajectory.
- A harden round that has no real run is not finished.
- Findings: F-32, F-34, F-38, F-40. Target: **P9 §round order**; round_notes. (Conflicts with d55; needs a PL decision.)

**6. The grader must work on owner-only files and run as any uid. Prove it with an owner-only gate run.**
- Findings: F-41, F-46, F-33. Study rule 9. Target: **P4 §verifier**; P11 gate list.

**7. Never put counts, trap topics or evidence file names in the instruction or the final ask.**
- Do not promise any size or latency that you do not grade.
- Findings: F-16, F-14, F-26. Study rules 1, 2, 3. Target: **P2 §instruction**; P11.

**8. A decoy may only be contradicted on a boundary the shipped data does not exercise. Never refute it on the same page as its use.**
- An omission must not get its own exception sentence.
- Findings: F-09, F-10. Study rules 4 and 5 weakened. Target: **P2 §decoy/omission**; QC_DEFENCE.

**9. Judge criteria must not pay figures computable from shipped files, or the agent's routine habits.**
- Allowed: figures that depend on a hidden-world interaction, and one honesty criterion (the agent states which rule interactions it did *not* verify).
- At most one conduct criterion.
- Findings: F-18, F-07, F-57, F-24. Study rule 12. Target: **P2 §judge**; QC_DEFENCE (JD-7, JD-9).

**10. Keep shipped-only checks at or below 5%, and route weight through a chain fed by the oracle's upstream output.**
- One miss upstream should cost many downstream checks. Grade later stages on oracle-fed inputs, so that QC TS-26 does not see double payment.
- Findings: F-02, F-04, F-64. Study rules 6 and 11. Target: **P2 §weights**; P4.

**11. Build an internal-consistency trap for the self-tester.**
- Rule: under the wrong reading, the agent's roundtrips, identities, fuzz and determinism checks must all still pass.
- If any shipped invariant (a residual, a checksum, a roundtrip) would expose the wrong reading, the lever is DERIVABLE. Drop it.
- Findings: F-21, F-17, F-27. Target: **P2 §lever acceptance test**.

## Tier 2: process and bundle hygiene backed by repeated failures
**12. Run the oracle and gates in Docker, under parallel rewardkit, before any score is trusted.**
- No process-group or uid kill without a lock.
- Every check must handle `{}` and a missing file without aborting the reward.
- Findings: F-42, F-45, F-67. Target: **P4 §verifier**; P11.

**13. Every hidden fixture family must exercise each oracle branch.**
- A wrong oracle that still scores 1.0 is a build failure.
- Findings: F-44, F-43. Target: **P4 §oracle**.

**14. Shipped code and docstring edits must earn 0.**
- Run a stub, a docstring-only edit and a shipped-code run as gates.
- Findings: F-47. Target: **P4 gate list**.

**15. Default every QC finding to FIX.**
- About 95% are real (65 REAL / 2 FP / 4 UNSURE).
- Rebut only with a quoted kit line (examples: 01:19 layout, 04:97 JD-16).
- Before applying a fix, record its effect on each lever. Refuse any fix that states a composition.
- Findings: F-50, F-48, F-49, F-56. Target: **P12 §per-finding FIX/KEEP/REBUT**.

**16. Pre-written "safe fix" concessions in QC_DEFENCE must not restate a lever.**
- A safe fix that turns an interaction into a sentence counts as retiring the lever, and must be logged as such.
- Findings: F-56, F-11. Target: **QC_DEFENCE template**.

**17. Known QC rule traps get a standing note: TS-13 vs TS-23, JD-5 vs JD-18, JD-9 vs F1/F3, AL-20/B4 vs DS-29, G7 vs rewardkit.**
- The note cites both kit lines, so the trap is not re-litigated every round.
- Findings: F-52, F-53, F-54, F-51, F-61. Target: **round_notes §QC traps**; QC_DEFENCE.

**18. A single source of truth for gates and constants.**
- Gate: tests <100, rubric <100, overall <70.
- chmod 755. Oracle reps (pending a decision between ×3 and ×5). Stacking definition (one of the two).
- Stale copies must be deleted from batch notes.
- Findings: F-35, F-36, F-59, F-63. Target: **round_notes header**.

**19. Prompts state facts only after reading the bundle (judge key present or absent, file list).**
- Findings: F-37. Target: **round_notes §prompt checklist**.

**20. Read `verifier/reward-details.json`, not ctrf (ctrf carries status only).**
- Record the uid, the permissions and any error before counting a score.
- Findings: F-68, F-71, F-33. Target: **P9 §diagnosis inputs**.

**21. Use neutral ids, and draw hidden worlds from a different distribution than the shipped ones.**
- Findings: F-29. Target: **P4 §generator** (DS-4).

**22. Warm the verifier image and pin litellm. One harbor process at a time per host unless the image is warm.**
- Findings: F-66, F-70, F-69. Target: **round_notes §infra**.

## Status of the 13 study rules (SYNTHESIS / round_notes l13-26)
| # | Study rule | Verdict | Evidence |
|---|---|---|---|
| 1 | Never state counts | **confirmed** | F-16 (vendor "fifteen rules", schema "54 numbered rules", cohort "three residuals" all leaked) |
| 2 | No trap topics in final ask | **confirmed** | F-16, F-18 (D1:29, EF2:33) |
| 3 | Don't name evidence files | **confirmed (medium)** | F-16; few direct cases |
| 4 | Scope by omission / split across files | **weakened** | F-10, F-12: cohort CR-5 split across 2 files leaked; vendor STATE omission leaked once its exception got a sentence (VD:28). The agent reads every file (H1) |
| 5 | Decoy default contradicted on rare boundary | **weakened** (holds only if the contradiction sits on an unexercised boundary) | F-09: district SIGNEDY, vendor REV and cohort CR-2 decoys, all refuted beside their use, leaked; peer 05 held |
| 6 | Dependent chain + whole-doc on hidden inputs, isolating ≤30% | **weakened as a cause, confirmed as an amplifier** | district a4 at 72% whole-doc still scored 100 (DHL:43-49); held cases (F-02, F-03) all had chains |
| 7 | Nothing confirms full answer | **confirmed** | F-15, F-22 (EF answer key step 8/22, sensor PASS band, dispatch assumptions) |
| 8 | Every graded unit identifiable | **unchanged** (hygiene; no counter-evidence) | — |
| 9 | Grader works on 0600 | **confirmed (strongest)** | F-41: 4 of 19 rewards were permission artefacts |
| 10 | Cheat detectors stand down on unclean run | **confirmed** | peer 09; sensor N2:54 |
| 11 | Shipped-only checks ≤5% | **confirmed** | cohort v0 45.9%, dispatch 94.5%, sensor 84.4% shipped-only, all high scores |
| 12 | Judge one figure per criterion + honesty negative | **partly confirmed** (one figure is not enough if the figure is computable from shipped files) | F-18, F-07 |
| 13 | No byte-compare of unstated serialization | **unchanged** (no new evidence) | — |

**Missing from the study rules, now Rules 1, 2 and 11:** in our tasks the only real holds came from interactions and rare ties that the shipped data never shows, and that the agent's self-tests cannot expose. Clean wording alone (rules 1-3) did not push any of our corrected real tests scores below 88% (vendor 88.97, emberforge 94.19, schema 99.3, district/cohort 100).
