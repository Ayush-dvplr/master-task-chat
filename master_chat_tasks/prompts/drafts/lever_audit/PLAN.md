DRAFT 27 Oct 2026 (Ayush: "make the plan and draft draft we will do it later"). Not issued. Issue only on Ayush's go.

# Lever audit plan

Goal: decide, lever by lever, whether it really cost Opus points in delivered tasks, and how the peers who used it built it. Outcome: a verdict per lever in `LEVER_RULES_v3.md` section 1C (HELPFUL stays, NOT HELPFUL is marked DISABLED with evidence; nothing deleted).

## Answers recorded (Ayush 27 Oct)
1. (a) Reuse the existing study notes, and check each lever against the real trajectories (`verifier/ctrf.json`, `reward-details.json`, `score.json`, agent logs).
2. HELPFUL = Opus genuinely lost that lever's checks (not a grader artefact or a hidden-rule hole from LEVER_RULES section 8), the task passed QC, and this happened in at least 2 tasks.
3. Our own blind reads and probes count as evidence (registry/tasks.json, registry/scores.jsonl, harden and blind reports).
4. Disable = mark DISABLED in LEVER_RULES with the evidence line; never delete.
5. (a) Sibling builds on proven levers (P-1 to P-5) may run while the audit runs; stated-rule hardening waits for the verdicts.
6. 4 read-only study sessions (one per lever group) plus 1 synthesis session. Ayush pastes them.

## Sessions
| id | file | scope |
|---|---|---|
| A1 | `A1_stated_writing.md` | L1-L11, S1 breadth, S3 unique fit, S5 partial-authority decoy, S6 buried hidden-only fixtures, H1-H9 habits |
| A2 | `A2_data_instance.md` | S2 degenerate shipped instance, S4 authority chain, S8 rare-branch hidden seed, T4 rare hidden fixtures, derived state carried across records |
| A3 | `A3_grading.md` | whole-doc grading and per-row ownership (G1/G1a), the gate, S7 digest cascade, S9 self-referential artifact, S10 provenance gate, S11 scoped-exception decoy, negatives, mutation tiers, metamorphic checks |
| A4 | `A4_core_behaviour_judge.md` | P-1 computational core, P-2 long stateful replay, P-3 exact optimum on larger hidden instances, P-4 behaviour and robustness checks, P-5 judge probe band |
| A5 | `A5_synthesis.md` | merge A1-A4 into `LEVER_VERDICTS.md`; propose LEVER_RULES edits (not applied) |

A1-A4 are independent and can run in parallel. A5 runs after all four have written their outputs.

## Evidence sources (all read-only)
- Delivered tasks: `/Users/mac/Desktop/Terminal Bench/Anubis_Tasks_Samples/Final_Delivery/<uuid>/` (47 tasks; trajectories under `trajectories/claude-opus-5/run_1/` with `verifier/score.json`, `verifier/ctrf.json`, `verifier/reward-details.json`).
- Study 1: `master_chat_work/_dev_research/delivery_study/{dinshi_5a44fec,poonam_f2e6166,sugam_a_3bfed9f,sugam_b_bd5de18}/` and `synthesis_6c6fcf3/DELIVERY_LEARNINGS.md`.
- Study 2: `master_chat_work/_dev_research/delivery_study2/{g1_be971df,g2_aee9e0a,g3_bffecb6,g4_af78147}/` (GROUP_SUMMARY.md, C_ and A_ cards) and `synthesis_720e1d7/`.
- 24 Oct synthesis: `master_chat_work/20261024_process/final_delivery/SYNTHESIS.md`.
- Our runs: `master_chat_tasks/registry/tasks.json`, `registry/scores.jsonl` (valid lines only), harden and blind reports named there, `board.json`.
- Rules under audit: `master_chat_tasks/knowledge/LEVER_RULES_v3.md` sections 1, 1A, 1b, 1C, 3, 4.

## Outputs
- A1-A4: `master_chat_work/_dev_research/lever_audit/<id>/VERDICTS.md` plus one `L_<lever>.md` card per lever.
- A5: `master_chat_work/_dev_research/lever_audit/LEVER_VERDICTS.md` and `PROPOSED_EDITS.md`.

## After the audit (master, with Ayush)
1. Review LEVER_VERDICTS.md with Ayush.
2. Apply the agreed edits to LEVER_RULES (DISABLED marks, HELPFUL recipes), log them in decisions.jsonl.
3. Unpause stated-rule hardening only for levers marked HELPFUL.

## Placeholders to fill at issue time
`<SHA>` board commit; `<PROMPT_PATH>` issued path under `prompts/issued/lever-audit/`.
