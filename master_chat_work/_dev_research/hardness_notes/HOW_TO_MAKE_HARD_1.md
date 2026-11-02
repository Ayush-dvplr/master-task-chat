CATEGORY_KEY = data-science
(The category name is this and archetype come from the table below.)

| CATEGORY_KEY         | Category name         | Archetype           |
|----------------------|-----------------------|---------------------|
| software-engineering | Software Engineering  | repo-patch          |
| system-admin         | System Administration | service-interaction |
| data-science         | Data Science          | data-pipeline       |
| security             | Security              | cli-config          |
| scientific-computing | Scientific Computing  | domain-calculation  |
| file-operations      | File Operations       | cli-config          |
| debugging            | Debugging             | build-repair        |
| data-processing      | Data Processing       | data-pipeline       |
| model-training       | Model Training        | performance         |
| mathematics          | Mathematics           | domain-calculation  |
| machine-learning     | Machine Learning      | domain-calculation  |
| games                | Games                 | service-interaction |
| video-processing     | Video Processing      | performance         |
| data-querying        | Data Querying         | domain-calculation  |
| optimization         | Optimization          | domain-calculation  |
| personal-assistant   | Personal Assistant    | service-interaction |

• Category: the Category name for CATEGORY_KEY (category key: CATEGORY_KEY)
• Archetype: the Archetype for CATEGORY_KEY (explicitly chosen; pass --archetype <ARCHETYPE> everywhere; never let the generator auto-select; never switch archetype mid-generation)
• From Input Bundle Generator New/templates/<ARCHETYPE>/archetype.toml take: ARTIFACTS (artifacts list), ABLATION_MAX (ablation_max), and any source archives the archetype ships.
• Author: <Shubhi Goyal> <shubhi.goyal.int@ethara.ai>

• Paths
- Generator: /home/shubhi-goyal-int/instance-restore/Terminal_2.0_Harbor_Harness/Input Bundle Generator New
- Output: /home/shubhi-goyal-int/instance-restore/Terminal_2.0_Harbor_Harness/Tasks_INPUT/new_tasks
- QC instructions: /home/shubhi-goyal-int/instance-restore/Terminal_2.0_Harbor_Harness/Input_Bundle_QC/Starter.md (authority: Input_Bundle_QC/Final_checklist.md)
- Hardening guide (primary difficulty source): /home/shubhi-goyal-int/instance-restore/Terminal_2.0_Harbor_Harness/Tasks_INPUT/HARD_TASK_HARDENING_0.24.md
- Archetype map: /home/shubhi-goyal-int/instance-restore/Terminal_2.0_Harbor_Harness/Input Bundle Generator New/ARCHETYPE_SELECTION.md
- Archetype manifest: Input Bundle Generator New/templates/<ARCHETYPE>/archetype.toml
- Trap ideas: Input Bundle Generator New/GENERATOR_TRAP_RECIPE.md (superseded for 0.24 format; use for trap IDEAS only, never for format)
- Format reference only: /home/shubhi-goyal-int/instance-restore/Terminal_2.0_Harbor_Harness/Tasks_INPUT/07d51b69-db0c-57ed-9208-bcb7a5a3fd47

• Precedence (highest first): Final_checklist.md → the four QC scripts (structure_qc, instruction_qc, tests_qc, judge_qc) and the five QC gates (01–05) → HARD_TASK_HARDENING_0.24.md → HARD_TASK_BLUEPRINT.md → generator docs. Where any lower source conflicts with a higher one, the higher one wins.

• Reference disclaimer: the reference task may be a different category. Use it ONLY to see the Harbor 0.24 bundle layout. Copy no idea, data, wording, trap, check or criterion from it. The new task must also differ in core concept from every existing bundle in Tasks_INPUT (eventforge-scale, gop-slice-recovery, gop-vbv-conformance-audit, governing-coefficient-recovery, marrowgate-maintenance-orchestration, ml-drift-cohort-recalibration-forge, observatory-semester-block-allocation, omnichannel-ledger-reconciliation, optimization-mincost-optctl-a1, pa-envelope-budget-ledger-repair, pa-household-ledger-reconciliation-forge, plugin-loader-tls-arbiter, snapshot-index-recovery, telemetry-codec-recovery, 07d51b69..., af406434...). Renaming, resizing or reformatting an earlier task is not novelty.

• Task idea
Create exactly one genuinely novel, expert-level <ARCHETYPE> task for the selected category. The agent receives what the <ARCHETYPE> archetype ships (per its archetype.toml), plus a dense corpus of evidence. A senior engineer must investigate the shipped material and corpus, then produce the archetype's deliverables so they implement the documented semantics. Difficulty must come from the genuine interaction of: entity resolution + temporal reasoning (effective vs recorded time, boundaries, timezones) + provenance (which source is authoritative when) + dependency graphs + state transitions + conflicting evidence + recurring commitments + deterministic reconciliation. You may invent the concrete domain, but it must be unique and fit the selected category / <ARCHETYPE>.
Forbidden mechanisms: data recovery, encoding/decoding, cryptography, corrupted-data reconstruction, shard recovery, reverse-engineering, pattern-matching puzzles, artificial ambiguity, hidden or unstated rules. Wrong handling must stay silent and plausible (hardening guide §5.10): a wrong solution still produces well-formed, believable output.
• Difficulty target
The goal is a low pass rate for Opus 5 and GLM-5.3, earned through real difficulty. Target an empirical pass rate around 5–15% (below 10% per channel per the hardening guide), never engineered to 0, and with meaningful partial credit (CL-4, guide §8.5). Do not make tests or rubrics adversarial to force failure; the real rate comes from blind evaluation. The task must stay fully solvable by a senior engineer in the declared expert time. Apply the hardening guide in full: §5 levers (at least 12 trap types across the bundle, 18 preferred; chained and implicit dependencies; at least five evidence/state levers; withheld-but-derivable rules; silent plausibility; no answer key and no self-verification path; long horizon; simultaneous constraint load), the §5.4 legitimate-trap test, and the §10 calibration gates (pass@8 arithmetic, near-miss ladder, five solver profiles each defeated for its own reason). Every trap must be a realistic consequence of the domain and derivable from the instruction plus the corpus.
• Bundle contract (Harbor 0.24; violations fail QC)
- Tree exactly as in guide §1: task.toml, instruction.md, environment/Dockerfile, environment/data/, solution/solve.sh (+ solve.py), solution/TRUTH.md, tests/Dockerfile, tests/test.sh, tests/reward.toml, tests/test_output.py, tests/judge.toml. No README.md. No rubric.json. No test_weights.json. No draft or reference solution outside solution/.
- task.toml: schema_version = "1.4"; no allow_internet anywhere; no difficulty key; per-role network_mode exactly as guide §2.1 (environment "no-network"); category truthfully names the work; authors = real full name + @ethara.ai email; artifacts list exactly equal to ARTIFACTS from the <ARCHETYPE> manifest.
- tests/test.sh byte-for-byte the template (guide §2.4); ends with exec rewardkit; no exit, return or ||.
- Reward = 0.5 × test fraction + 0.5 × judge fraction, no clamp.
• Inputs (environment/data/, flat)
- 50–60 files, each a distinct source of evidence (independent source, period with its own corrections, reference table, config layer, exceptions file, spec document). Split by concern, never by size; no filler.
- Spread across many realistic formats (csv, tsv, jsonl, json, log, txt, yaml-like config, ini, md specs, plus any archive the archetype ships). Every record file (.csv/.tsv/.jsonl/.txt/.log) has ≥2,000 lines; inputs total ≥20,000 lines; no file over 100 MB.
- Every file is named by the instruction or a spec document (A4). Index specs are fine; route maps ("file X solves deliverable Y") are not.
- At least 12 trap instances per data file, kept out of the first 50 rows, plus decoys (duplicates with no conflict, annotated look-alike units, records one second inside a boundary), at least one same-name-different-unit pair, and at least one join that works only after documented normalization. Over-applying a rule must cost as much as under-applying it.
- Ablation: deleting any one data file must drop the oracle score to ≤ ABLATION_MAX (from the <ARCHETYPE> manifest). Every file must feed the spine or a weight-5 check.
- Generate from a fixed seed and commit only the generated bytes, never the generator.
• instruction.md
- Under 6,000 characters (validate §2.2), plain prose, no dashes (P1), no banned words (P2), no AI-tell phrases (P3). Includes an absolute path in backticks, a time budget in seconds, and a ban on online lookup.
- At least 20 interlocking requirements, chained so later asks depend on earlier results, and including multiple deliverables across every artifact in ARTIFACTS plus a closing message. State WHAT must be achieved and exactly which contract literals (keys, columns, enums, file names, ordering, path forms) are required (DS-25, CL-5). Never reveal the method, algorithm or procedure. Say out loud any exactness bar ("an artifact counts only if every unit is exact") so CL-4 is satisfied.
- Require the closing message to state 8–10 counterfactual figures that appear in no artifact (guide §9.3).
- Self-contained, unambiguous and non-contradictory; every requirement is graded and nothing graded is unstated.
• Test channel (tests/test_output.py, rewardkit @criterion checks)
- About 30 checks per guide §8.7: 6–8 at weight 5, 8–10 at weight 3, at most 2 parse/shape checks at weight 1, and 8–10 negative_ checks (one shortcut each, inline comment, False when the artifact is missing).
- Grade what the <ARCHETYPE> archetype delivers; where it delivers code, a tool, a transform or a service, run it on verifier-generated inputs the agent never saw (§8.3), plus cross-component identities (the identity triangle), boundaries, determinism and final state. Absences ("inputs unmodified", "no extra files") are negative_ checks only (TS-25). One check per comparison; weights track importance (TS-20). Embed any needed shipped input as a zlib constant (the verifier has no /app/data).
• Judge channel (tests/judge.toml)
- 25–32 criteria (QC allows 8–35), schema exactly as guide §9.1 (id/name/description/type="binary"/weight in {5,3,1,-1,-3,-5}, plus a full criterion.annotations table).
- Slots per guide §9.4: 8–10 counterfactual-figure criteria (3–4 facts each, weight 5), 8–10 derivation-evidence criteria naming specific evidence, trajectory-only constraint criteria only for rules the instruction really states (no invented instruction-following filler), 1–2 honest-reporting criteria, 1 code-quality criterion (JD-18), and 8–10 negatives.
- Zero overlap with tests: tests read artifact bytes, the judge reads trajectory and closing message (JD-8, JD-16). No two criteria grade symptoms of the same behaviour. AL-28: no single agent action fires more than one -5 across both channels, and the summed penalty per action is ≤5.
• Solution
- solve.sh/solve.py produce every artifact in ARTIFACTS. The oracle must score exactly 1.000 five times, nop exactly 0.000.
- solution/TRUTH.md: rule derivations, a trap record-incidence table (trap → firing records → graded value that changes), and no authored_by or provenance leaks (DS-27).
- No answer key, worked-example outputs, or self-check oracle anywhere agent-visible.
• Generation
python3 "Input Bundle Generator New/generate_bundle.py" --out Tasks_INPUT/ --category <CATEGORY_KEY> --archetype <ARCHETYPE> --seed <int> --name <task-name> --author "<Your Full Name> <first.last@ethara.ai>"
Then author the content in one pass, following the guide's §4 build order.
• Final consistency review (before declaring done)
Trace instruction → inputs → solve.py → artifacts → tests → judge → closing message. Confirm: category and archetype unchanged; every requirement graded; nothing graded is unstated; no test/judge overlap; every file necessary (ablation); deterministic and reproducible; stdlib only; offline; contract literals visible to the agent; difficulty genuine, not just long.
• Generation-only mode
Do not execute, repair or iterate after generation. Report only these commands:
python3 "Input Bundle Generator New/validate_bundle.py" Tasks_INPUT/<task-name>/ --archetype <ARCHETYPE>
then the QC process in Input_Bundle_QC/Starter.md, then Final_checklist Step 10 (requires harbor --version ≥ 0.24.0).
• Do not push anything, do not change anything on remote. Do not edit files outside Tasks_INPUT/new_tasks/<task-name>/.

first analysis the repo and use different idea from other tasks and the task has to be more harder and complexity high
don't edit any other file except the task you will genertae and don't push anything and don't do remotly anything