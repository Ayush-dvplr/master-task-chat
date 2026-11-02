# QC-safe authoring checklist (Input_Bundle_QC at e4054885 / HEAD 1096b244)

Before you start, compare the live QC against `fingerprint.json`. If any hash differs, re-read the changed file. IDs get renumbered between versions, so match each item on its ID and its wording. Work through the items in order. Each item names the check IDs it satisfies.

1. **Scaffold.** Run `generate_bundle.py --out <dir> --author "First Last <first.last@ethara.ai>"`. The author must be a real full name in capitalised words, with the email built from that name and ending in @ethara.ai. Name the bundle in lowercase kebab-case, 3-64 chars. [T14, FC-S18, S1, FC-S1]

2. **Tree.**
   - Keep only `instruction.md`, `task.toml`, `environment/{Dockerfile,data/}`, `solution/{solve.sh,solve.py?,TRUTH.md}` and `tests/{Dockerfile,test.sh,test_output.py,judge.toml,reward.toml}`.
   - Do not create `cheat/`, `test_weights.json`, `rubric.json`, reward/ctrf files, `__pycache__` or `.DS_Store`.
   - Use LF line endings everywhere and keep every file at or under 100 MB.
   - Keep environment/data flat; validate_bundle requires it.

   [S2-S6, X3, FC-S2..S5, FC-S15, FC-S16, VB §1.7]

3. **task.toml.**
   - Copy the FC template byte for byte, with tables and keys in template order.
   - Change only the `<angle>` values.
   - `[task] name = "terminal-bench/<dir>"`.
   - Description: one paragraph, at most 100 words, honest.
   - Category: names the dominant work.
   - Keywords and tags: at least one each, on-topic.
   - All times positive, junior > expert.
   - Artifacts are absolute `/app/...` paths.
   - `[verifier.env]` stays exactly as the template has it.
   - Do not add `docker_image`, `allow_internet` or any extra table.

   [T1-T15, FC-S6..S12, FC-S19..S21, IN-12, AL-26, AL-8]

4. **environment/Dockerfile.**
   - Right after FROM, create the uid 1000 `agent` account with `-m` and set `ENV HOME`.
   - Pre-bake `/opt/openhands-sdk-venv` with `openhands-sdk==1.55.1 openhands-tools==1.55.1 litellm==1.105.0 fastapi`, a build-time `import openhands.sdk`, and `chmod -R a+rX`.
   - apt-install `curl ca-certificates tmux` plus every tool the task or oracle needs.
   - `RUN mkdir -p /app && chown 1000:1000 /app`, and chown every artifact dir to 1000 after the last COPY into it.
   - The only COPY is `COPY data /app/data`; never `.`, `..`, solution, tests or TRUTH.md.
   - No runtime fetches; the only piped download allowed is the uv installer.
   - Leave no answer anywhere in the image.

   [S7-S10, DS-8..DS-12, DS-26, DS-28..DS-30, FC-S17, FC-S22..S24, AL-15, AL-20, VB §5.4-5.5]

5. **Data.** Curate it for this task. It must be necessary and sufficient, with no answer keys, `*.solution.*` files or worked graded values. Any wrong value you plant on purpose must be signposted as suspect. Every output literal the tests require (keys, columns, error strings, order) must appear in a visible spec or in the data. No dashes, no placeholders, no injection text. [DS-2..DS-7, DS-21, DS-25, CL-3, CL-6, CL-7, CL-10, AL-F0a, AL-F0b, AL-F0e, AL-13, AL-23, X1, X2]

6. **instruction.md.**
   - Plain everyday English: no dashes, no listed or same-kind inflated words, no AI-tells.
   - Exactly "You have N seconds to complete this task." with N == `[agent] timeout_sec`.
   - One unambiguous full path per declared artifact.
   - State every graded rule of engagement, tolerance and tie-break, or point to the spec file that holds them.
   - Never mention tests, the grader, the checker or the verifier, test names, negative checks, weights, the judge, "reward", /logs, or TRUTH.md.
   - Never say download, fetch or install, and never give a URL as a source.
   - Describe the end state and the constraints, never the recipe or the answer.
   - Keep it under 6000 chars (validate_bundle only).
   - The online-lookup sentence is optional for QC but required by validate_bundle; keep it.

   [P1-P3, C1-C6, IN-1..IN-16, IN-L1..L3, IN-S1..S7, DS-23, VB §2.2-2.5]

7. **solution/.**
   - solve.sh is the entrypoint and solve.py computes from /app/data.
   - It writes every declared artifact itself, as uid 1000, offline.
   - Never read tests/, and keep no hardcoded fallback branches.
   - Obey every contract rule in the stated precedence order.
   - Write it independently of test_output.py: overlap well under 20%, and keep solve.py at 30 or more substantive lines to avoid the O1 small-file WARN.

   [DS-13..DS-20, DS-24, O1, CL-8, AL-5]

8. **TRUTH.md.**
   - Eight sections in order: Defect, Load-bearing work, Verification, Root cause, Solution shape, Ordered plan, Pitfalls, Provenance.
   - It must match the shipped solve.py, the real weights and positive total, and the named negatives.
   - Every focal, drift and trap item must be real.
   - No production narration: no generator, archetype, seed, playground, tooling or "authored_by" attribution.
   - Conflict: validate_bundle §15.5 requires `authored_by`/`status`. Raise it with the tasker; do not choose silently.

   [DS-22, DS-23, DS-27, AL-7, AL-9, AL-18, FC-STEP10-SCOPE, VB §15]

9. **tests/Dockerfile and test.sh.**
   - Copy the FC templates: `python:3.12-slim`, util-linux, `harbor-rewardkit==0.2.1`, `ENV LITELLM_LOCAL_MODEL_COST_MAP=True`, `COPY . /tests/`, `mkdir -p /app`, and every third-party import installed.
   - test.sh does `rm -f` of the reward files, `chown root:root` plus `chmod 700 /logs/verifier`, `chmod -R go-rwx /tests`, and ends with the exact `exec rewardkit ...` line.
   - No exit, return, `||`, SKIP switches or sourcing.

   [K1-K7, B1-B5, H1, H3-H5, TS-2..TS-9, TS-28, AL-14]

10. **test_output.py.**
    - 10 or more checks (more than 35 is only a WARN), each a top-level `@criterion(description=...)` with no braces in the description, taking only `workspace`, returning a bool, and never raising: guard every read and subprocess.
    - Register each check exactly once as `criteria.<name>(weight=W)` with W ∈ {±1, ±3, ±5}.
    - At least one positive and one negative, weights not all identical, Σ|neg| ≤ Σpos.
    - `negative_` prefix if and only if the weight is negative, with inverted polarity and an inline comment.
    - Weights follow the semantics: 5 core, 3 sub-goal, 1 existence.
    - One property per check. No positive check that passes on an absence, no pair reading the same observable, no source-token grading, no /app/data reads, no clock, randomness or unsorted listing.
    - Run agent code only as a subprocess with a timeout and kill its process group.
    - Every stated rule needs a fixture that triggers it, including both halves of each precedence pair.
    - No penalty stack above 5 for one action.

    [A1-A5, W1-W7, D1, TS-1, TS-10..TS-29, AL-10..AL-12, AL-24, AL-25, AL-27, AL-28, CL-1, CL-4, CL-5, CL-9]

11. **judge.toml.**
    - Pinned five-key `[judge]` plus `[scoring]`.
    - 8 or more criteria with ids R1..Rn, unique names, binary, weights ∈ {±1, ±3, ±5}, the full annotations block in order, `contract_sentence`/`contract_file` on constraint criteria, `serves` on conduct criteria.
    - Importance pairing: critically_important |w| 3/5, important |w| 1/3.
    - Start each description with "The agent" or "The response" according to `evaluation_target`.
    - Positive grammar only: no not, without, fails to, cannot, instead of, vague words or quantifiers. Write counts.
    - One observable per criterion, true of the oracle, with no overlap with any test and no double payment between criteria.
    - Negatives aimed at this task's real cheats.
    - At least one code-quality criterion.
    - Constraints quote their source sentence and do not carry the task alone.

    [G1-G6, J1-J13, JD-1..JD-18, JD-S1..S12, AL-6, AL-F0d]

12. **reward.toml.** `weights = { test_output = repr(0.5/P_tests), judge = repr(0.5/P_judge) }` plus `[scoring.test_output] aggregation = "weighted-sum"`. Recompute after every weight change. [R1-R5, TS-10, JD-S13]

13. **Self-check.**
    - Run all four scripts and fix every FAIL.
    - Clear WARN C6 by removing grader, checker and verifier wording.
    - Run validate_bundle.
    - Compute the CL-2 forgery share and the CL-4 one-fact-wrong score.
    - Redo the Step 11 coverage and overlap maps.

    [IN-0, TS-0, JD-0, CL-2, CL-4, FC-STEP11-*]

14. **Step 10.** On harbor 0.24.0 or newer, run exe_copy, then oracle ×5 (each exactly 1.000), nop (0.000) and the stub (near 0 or negative; name the tests that paid). Fix the defect and rerun if needed. Delete the copies. [FC-STEP10-*, EXE-R1..R4]
