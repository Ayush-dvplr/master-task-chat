# claude-opus-5 playbook (what it does, and what legitimately defeats it)

Evidence base: 19 real trajectories in `Terminal_2.0_Harbor_Harness/jobs/` (newer tree), the round DIAGNOSIS files, and the peer low-score study. Paths are shortened as follows:
- C3 = `master_chat_work/20261023_cohort-retention-reconciliation/harden_r2/DIAGNOSIS.md`
- VD = `master_chat_work/20261023_vendor-archive-roundtrip-recovery/harden_lp1_r1/DIAGNOSIS.md`
- DHL = `master_chat_work/20261023_district-heat-flex-procurement/harden_lp1_r1/DIAGNOSIS.md`
- DH2 = `master_chat_work/20261022_district-heat-flex-procurement/harden_r2/DIAGNOSIS.md`
- EF1/EF2 = `master_chat_work/20261021|20261022_emberforge-vault-settlement/harden_r1|harden_r2/DIAGNOSIS.md`
- D1 = `master_chat_work/20261022_dispatch-plan-reoptimization/harden_r1/DIAGNOSIS.md`
- SYN = `master_chat_work/20261022_lowscore-study/SYNTHESIS.md`

The run tables are in `notes/S5_trajectories.md`. Findings ids refer to `FINDINGS.jsonl`.

## H1. It reads every spec file in full before it writes any code
- Vendor a2: it "read every spec in full steps 2-7 (first 30 s)", plus `xxd` (VD:12-18). Cohort a2: `cat` schema at step 4, audit_policy at step 5, all data at step 6 (C3:35-39). District a4: `cat` the whole schema at step 3 (DHL). Emberforge: it dumped all docs in steps 3-9 (EF2:7-10).
- **Consequence:** a rule written anywhere in the bundle counts as read. Placing a rule far from where it is used does not hide it (F-12).
- **What defeats it legitimately:** nothing about where a rule is placed. Hardness has to come from how the stated rules *interact* on inputs the shipped data never shows (F-01, F-03, F-55).

## H2. It writes the program once and never changes the graded logic afterwards
- Vendor: "After the first write it never changed the logic that the grader checks" (VD:12-18). Cohort: "It never edited the logic after the first write" (C3:35-39). Emberforge: "wrote the whole program in two edits. No exploratory runs before writing it" (EF2:7-10). Pcggc: a single write at step 11.
- **Consequence:** its first reading of each rule is its final one. A rule with a reflex-plausible misreading stays wrong unless something shipped visibly contradicts it.
- **What defeats it legitimately:** rules whose natural code shape is wrong only in a composition, such as an if/elif early return when two refusals apply to the same item (EF L7, EF1:47, F-28), or a DP that keeps the later tie (D1:21, F-25). The shipped data must not contain the separating case.

## H3. It self-tests thoroughly, but only against its own reading
- Vendor: full catalog round trip, injected damage, a hand-built stream, and a fuzz of 6000 cases (VD:12-18). Cohort: a synthetic extract "covering all hidden-case families" plus a determinism diff (C3:35-39). District: brute-forced 2000 groups, "bad 0" (DHL). The judgement was "It made no mistakes. It verified more than the grader requires" (C3:147).
- **Consequence:** any lever that a self-roundtrip, a fuzz run or an internal identity can derive leaks (F-17, F-21; vendor W-VA2 was derivable via self-roundtrip, VH:73).
- **What defeats it legitimately:** separating cases where the program's internal consistency still holds under the wrong reading. Both readings must produce valid, balanced, round-trippable output, and differ only on a rule interaction (F-27; SYN:89-91 "validates by internal consistency").

## H4. It treats reproducing a shipped example as proof, then stops
- Season-ladder: "with it my program regenerates `example_division_report.json` byte for byte". Caldermoor: "A second run is byte-for-byte identical ... All five identity residuals are zero". Emberforge: the single surviving draw "told the agent that its engine reproduced a whole settled season" (EF2:12).
- **Consequence:** a full-answer confirmer (PASS band, answer key, calibration bundle, assumptions block) turns every lever into a free check (F-15, F-22). The emberforge answer key was printed at step 8 and compared at step 22 (EF1:42). The dispatch assumptions block was read as a checklist at step 21 (D1:28). The sensor PASS band confirmed everything (N1:13).
- **What defeats it legitimately:** ship no artefact that confirms the full answer. Shipped examples should exercise only the common path, so that reproducing them proves nothing about the rare interactions (study rule 7).

## H5. It stops far inside the budget, by choice
- Cohort a2 took 282 s, district a4 703 s, vendor a2 659 s. Emberforge finished in about 47 minutes of a 120-minute (7200 s) budget (EF2:7-10). Every run stopped below 45% of its budget (S5). SYN:86: "agents stop early by choice", and time levers add 0 pp.
- **Consequence:** time and size pressure do not bind (F-14).
- **What defeats it legitimately:** nothing in the time dimension. The only exception is H6, which is a defect, not a lever.

## H6. It strengthens any bound it is promised, and that causes timeouts
- District r1/r2: "the schema explicitly promises 10^15-portfolio groups within 30s, so I'll strengthen the bound". Both runs reached 7200 s timeouts (DH2:17, :20).
- **Consequence:** a size or performance promise in the instruction becomes a self-inflicted timeout, which is a process failure, not a held lever (F-14, F-26).
- **Rule:** never promise sizes or latencies that you do not grade.

## H7. When it can, it brute-forces withheld constants against published digests
- Match-replay: in steps 9-93 it probed 11 constants one at a time (CTRL-A..K) with `_probe.py`, and wrote `optimize.py` only at step 94. Judge R1/R2 paid it for doing this (F-24).
- **What defeats it legitimately:** do not publish digests of hidden values. This template is not QC-usable (SYN rank-1 template excluded; IN-9).

## H8. It reverse-engineers generator patterns from the visible data
- Vendor steps 8-11 profiled the tables and found `<prefix>_%04d`, `name@s<id%40+1>` and baked tables (VD:12-18).
- **What defeats it legitimately:** use neutral ids (`cap-00001`, as in the DS-4 fix) and draw hidden worlds from a different distribution than the shipped one (F-29).

## H9. It follows explicit precedence text literally, including "X overrides Y"
- Vendor final reply: "Per the contract (which overrides loader_notes.md)" (VD:26). The cohort decoy was "contradicted in plain words" (C3:44).
- **Consequence:** a decoy that is refuted on the same page leaks. An omission leaks once the exception gets its own sentence (F-09, F-10).
- **What defeats it legitimately:** UNVERIFIED in our tasks. The only held decoy in the peer study (05) was contradicted only on a rare boundary that the shipped data does not exercise.

## H10. It answers "response states X" judge criteria by printing X
- Judge channels came back full whenever the criteria were figures computed from shipped files: vendor R1-R4 gave 20 of 24 points from shipped streams (VD:34), season-ladder R1 "states three season constants", and cohort "states figure X" (C3:149).
- **What defeats it legitimately:** use judge figures that depend on the hidden-world-only interaction, or on the agent's honesty about what it did not verify. Sensor and sentinel lost only judge points, and only on figures the agent never reported (F-07, F-18).

## Where it actually lost points (genuine, not artefacts)
| Run | Lost | Mechanism |
|---|---|---|
| emberforge v0 (corrected) | L7, 10 of 11 points | composition of two refusals, hidden-only, rules in different files (EF1:19,47) |
| dispatch v0 | K13 tie, 14 chained checks | DP reflex keeps the later tie against a stated rule. The docstring said otherwise (D1:21) |
| season-ladder | 10 `generalisation_*` checks plus determinism | hidden worlds build situation classes absent from the shipped data (mechanism UNVERIFIED) |
| caldermoor | 8 unseen/cadence checks | a waiver suppresses a period and leaves the streak standing, unseen in the shipped data |
| match-replay | 12 `trap_*_inverse` checks | label-mask-only capture sets, absent from the shipped data |
| old emberforge | 8 `gen_*` checks | draw shift, priority tie flip, temporal boundary, identity merge chain |

The common property: a correct-looking program that is internally consistent, built from plainly stated rules, meets a *situation class* (an interaction, a tie, or a boundary) that no shipped file contains, and a chain carries that one miss into many checks.
