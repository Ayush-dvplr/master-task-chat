# GROUP SUMMARY: dinshi (board 5a44fec)

Repo HEAD `2dfb1f8f7b86db305b1f6afa63279873e6e918e4`. Read-only study: 9 A files, 7 C cards (no cards for the 2 ARTEFACT tasks). Session rename: `name_session.py 5a44fec` printed `codex: no match` / `opencode: ['ses_e8e7eb093ffeRdc1rrmDhZtPx0']`. The list did not show "5a44fec" literally; I did not retry.

Key caveat: the recorded score.json for every QC'd task came from the **pre-fix** verifier. The QC reports re-graded the stored artifacts against the fixed tests (all dated 2026-10-24). I count genuine points from evidence and quote the re-grade wherever one exists.

## 1 Table

| task | verdict | overall / tests / rubric | genuine test pts lost | main lever shape |
|---|---|---|---|---|
| chainfold-resume-repair | GENUINE | 62.93 / 78.49 / 47.37 | 20 / 87 (QC re-grade 77.01%) | hidden regimes from an in-test generator; graded empty value of a string field that no file states (HIDDEN RULE); 2 of the 4 roots undetermined |
| h3-fleet-migration-scheduler-nk-20260907 | GENUINE | 64.77 / 70.71 / 58.82 | 29 / 99 | overloaded term ("admitted"), graded meaning implied only by a computation clause; seals do not separate the readings (HIDDEN RULE) |
| inference-gate-replay | GENUINE | 21.77 / 36.56 / 6.98 | 59 / 93 | withheld constants, no candidate list, all-or-nothing digest as the only signal; plus reset timing split across sections |
| keyframe-interval-basis-reconcile-hk-67 | PARTLY | 56.2 / 26.85 / 85.56 | 79 / 108 (57 value + 22 value-gate only; QC re-grade 30/109) | "decide from the evidence" tie rule witnessed by one shipped pair (HIDDEN RULE), amplified by positional rollback and a value gate |
| registry-lock-footprint-resolution | ARTEFACT | 48.81 / 2.88 / 94.74 | 0 (QC re-grade 139/139) | none; verifier could not read the program (H6) |
| restoration-cadence-settlement | GENUINE | 53.38 / 25.62 / 81.13 | 90 / 121 (QC re-grade 31/124) | unwritten convention recovered by a calibration fit; "exactly one combination fits" holds only inside an unstated candidate set; Opus found an outside model that also fits |
| tollgate-settlement-repair | GENUINE | 72.89 / 91.55 / 54.24 | 3 (+3 contested) / 71 | judgement field (root-cause chain) graded exact; contested `.py` scope contradiction |
| vault-relink-correction | ARTEFACT | 62.7 / 85.39 / 40.0 | 0 proven (13 lost to a contradiction) | expected value (last-wins map) contradicts the literal prose rule ("prior_path column"); agent followed the prose |
| yard-rehandle-ledger-recompute | PARTLY | 48.91 / 16.42 / 81.4 | 21 / 68 (QC re-grade 47/68) | 35 points lost to the H6 artefact; genuine error in one vessel family repeated over 3 minted seeds (exact field undetermined) |

Genuine total about 301 points across 7 tasks. Restoration, inference and keyframe account for 228 of them.

## 2 Test-design patterns, ranked by genuine points lost

1. **Withheld constant or convention, recovered from evidence, with the candidate space unstated** (RISKY). 149 pts: restoration 90, inference 59. Mechanism: a rulebook sentence says the value "is not written down here" (restoration rulebook_cadence.md:30-31, :71-72; inference gate.md:150-155). The evidence is one calibration page, or a sha256 digest over whole reports. Grading uses the reference inside the tests plus a mutation or reseeded tier, so a wrong constant spreads to every downstream check. QC passed restoration (IN-15/16 ✅, QC :124-125) because "exactly one combination" is true inside the author's candidate set. Inference has no QC. Contrast: h3 lists the candidates (README :187-197) and pins each with a single-feature seal; Opus recovered all four (0 lost there). **A listed candidate set is not a lever; an unlisted one is.**
2. **Rule stated as a question, answered only by one shipped witness, then amplified** (RISKY). 79 pts: keyframe (instruction.md:9 "decide from the evidence ... their recorded order settles nothing"; oracle precedence solve.py:94-96). Graded through the reproducer on single-dimension perturbations plus a value gate `_replay_landed` (test 298-305, 36/109). QC passed it as anti-forgery coupling (QC :50) and deferred 3 warns because fixing them needed an instruction sentence (QC :26).
3. **Overloaded term whose graded meaning is implied by a computation clause, with shipped controls green under both readings** (RISKY). 29 pts: h3 (README :58, :79, :90, :110-111). Graded against golden results embedded by input fingerprint, plus 4 seeded regimes. No QC report; our IN-16 would flag it.
4. **Hidden-regime archives from one in-test generator, each plan planting a branch that sits idle in the shipped run** (SAFE as a mechanism). 20 pts: chainfold (PLANS test 350-593; `_mirror` 988). The yield came from an unstated empty value (`pick = ""` test 1174 vs agent "none"), which is RISKY (on our never-used list). QC passed it (TS-19 ✅ QC :229).
5. **Families graded byte-exact, repeated across N reseeded or minted corpora** (SAFE amplifier). Yard: one genuine error = 3 + 3 + 3x5 = 21; h3 hidden 4x5; vault would have cost 13 for one figure. QC accepts this as a natural cascade (CL-4 ✅ yard QC :247, :107).
6. **Whole-report equality in every mutation check** (RISKY amplifier; restoration `_generalises` 1626 = 55/124 with no partial credit). QC W3 (:52) warned but accepted it.
7. **Judgement field graded by exact match** (RISKY, low yield). 3 pts: tollgate root_cause_chain.

## 3 Leak-avoidance patterns (and the LEAK_LIBRARY row each would fix)
- **"The value is missing" sentence placed where the value is used, with no list and no explanation** (inference gate.md:71-73 "Which accelerator and what scale are missing constants"; restoration rulebook_cadence.md:30-31). The rule's existence is stated but the trap is not explained. Fixes ESC/EXT/SALV (W1, explaining the trap).
- **One instruction line saying idle rules are live elsewhere, with shipped data that never fires them** (chainfold instruction.md:37 "The run you can see is a quiet one. Rules that sit idle in it are live in other runs"). Fixes RUN ("shipped stream separates") and the common cause "shipped boundary rows let the agent watch rules fire".
- **Worked example on an invented case that disowns the shipped data** (chainfold worked_examples.md:3-5; yard worked_examples.md). Fixes CR-2/REV ("decoy refuted beside use") and follows W6.
- **Controls green under the wrong reading** (h3 seals have zero preemptions; restoration calibration also fits the agent's model). Opus's self-tests pass, so it never revisits (L1/W7). Fixes ENC ("caught by self-test").
- **One neutral line naming the winning document or the decoy surplus** (tollgate "Where two sources disagree, the runbook settles it"; "The vocabulary is wider than this job needs"). Fixes REV and CR-2.
- Counter-evidence (confirms our W1): yard's spec names each wrong reading outright ("... is wrong and gives different shares", y13 :60-61, :72-74, :82-86, :107-108) and ships known_traps_and_footguns.md. All 8 matching wrong-reading negatives stayed silent, and Opus passed every such stage. Zero yield, as LEAK_LIBRARY ESC/SALV predicts.

## 4 Differences from our LEVER_RULES (with evidence)
- **Withheld-constant recovery** is their main lever and is absent from our L1-L10. Inference's version (no list, digest only) sits close to our "shipped-slice promise" ban. Restoration's version passed QC.
- **Hidden rules from our never-used list passed QC**: an unstated empty value (chainfold, QC IN-15 ✅ :171) and "decide from the evidence" with one witness (keyframe; QC warn deferred :26). An overloaded term (h3) had no QC.
- **Wrong-reading negatives** (yard `_matches_variant`, a hook-swapped reference matched exactly) contradict our G4/TS-16 "negatives only for cheating acts". QC accepted them: "mutually exclusive by exact-match construction" (yard QC :117).
- **Value gate** across about a third of the weight (keyframe `_replay_landed`) goes against our G1/G2 own-rows rule. QC accepted it as coupling.
- **G3 hidden share**: chainfold 55%, h3 60%, yard 73.5%, restoration 44% (mutation tier) all exceed our 30%; keyframe 13.8% would fail our bar but passed QC.
- **Expected-value sources** we do not list: golden results embedded by input fingerprint (h3 `_GOLDEN_RESULTS_B64` 417), and full corpus generators plus office-file writers inside the tests (yard 279-3830; vault `build` 17404). These satisfy G9 in a different way.
- **Same as ours**: weights 1/3/5, privilege-dropped execution (setpriv nobody), negatives -5/-3/-1, batched judge. Opus behaviour matches sec0: first full program at minute ~1 (h3), 5.5 (chainfold), 6.5 (keyframe), 14 (yard), 15 (inference), 25 (restoration). Graded logic was not changed after it, and self-tests were circular (h3 audit step 20 asserted its own reading; inference checked 32 self-derived targets).

## 5 Anti-patterns and artefacts
- **H6 permission bug** in pre-fix verifiers: registry-lock lost 136/139 (QC re-grade 1.000) and yard lost 35/68. Recorded scores for these tasks are not measurements.
- **Expected value contradicts the stated rule**: vault orphan_prior_entries (prior_run_notes.md:60-62 vs Mirror last-wins `self.was`, test 18144-18147, 18615; shipped TSV has 40 duplicate refs despite ":21-22 The reference is unique in the file"); tollgate `.py` sentence (runbook.md:182-185) vs bare names. QC missed both.
- Self-contradicting worked example (chainfold worked_examples.md:21-24); it cost 0 because the test follows the prose.
- Score inconsistencies between result.json, stdout and score.json (chainfold 0.853, vault 0.907 / 0.6598).
- stacking_check.py labels generator and mutation tiers "isolated" (yard, restoration), and groups different wrong-reading negatives as one act. Read the code before trusting its shares.

## 6 Open questions for the master
1. Inference: 8 per-decision ledger scores recorded near 0 although the program ran (`program_writes...` passed). Was it binarised or a timeout? Needs a re-run, which this read-only study cannot do.
2. Yard vessel field and chainfold beta/delta roots are undetermined statically. Should a run-permitted session diff them against the reference?
3. Do we admit withheld constants with an unlisted candidate space (restoration passed QC) despite IN-16/TS-19 learnability, or only listed-candidate recovery (h3), which yielded 0?
4. Do our rulings accept wrong-reading negatives when they are exact-match exclusive (yard QC :117)?
5. Should recorded scores from pre-fix verifiers be replaced by the QC re-grades in delivery stats?

## Lessons for the master
- Their losses come from values or meanings that are not fully stated (withheld constants with an unlisted candidate space, a single-witness rule, an overloaded term, an unstated empty value), not from stated levers. QC passed most of them.
- Stated traps yield nothing: yard spelled out 8 wrong readings and Opus avoided all of them. This confirms W1.
- Amplifiers turned single misreadings into 20-90 points: generators reseeded N times, whole-report mutation checks, value gates.
- Two of nine recorded scores are artefacts (H6 read permission) and one is an answer-key contradiction. Check `_grant_read` and expected-vs-prose before trusting any score.
- A listed candidate set with single-feature seals (h3) gave Opus 0 losses on those constants. Recovery only bites when the space is open or the controls are green under the wrong model.
