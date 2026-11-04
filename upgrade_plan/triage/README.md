TRIAGE OF OLD TEAMMATE OR ASSIGNED TASKS (P19, W1-050, 4 Nov 2026)

WHAT IT DOES

triage_tasks.py reads a folder of old Harbor tasks and tells you which ones are worth working on, ranked. It is read only: no Docker, no network, no model calls, no AI tokens. It never writes inside the task folders and refuses an output folder that sits inside one.

For every task it reports:
1. Inventory: which bundle parts exist (instruction.md, task.toml, environment/, solution/, tests/, trajectories/) and structure problems against the kit layout (the S2, S3, S4, S5, S6, X1 and X3 ids of Input_Bundle_QC/structure_qc.py).
2. Runs: every run folder it finds (trajectories/, jobs/, any folder with reward-details.json, ctrf.json, reward.json, test-stdout.txt or a Harbor result.json) with tests, rubric and final, every check with pass or fail, and a class: TRUSTED, BROKEN with its sign, or UNSURE, each with the evidence file and line. Broken and unsure runs never count toward the real score.
3. Levers and traps: the likely design families D1 to D9 from upgrade_plan/knowledge/PATTERNS.md (plus decoys), each with the doc or test line that suggests it, the checks the paid model lost with their share of positive test points, and the largest share one slip took against slip_cap_pct.
4. QC risk hints tied to kit check ids: step lists in docs, announced traps, no exact bar sentence, whole document only grading, TRUTH.md stating run scores, test and judge criteria counts, what if figure criteria, a uid drop with no read grant, slip over the cap, very low scores that need a solvability check. Each is a hint with a file and line, never a verdict.
5. A score from 0 to 100 with its parts, and one recommendation with one line why.

HOW TO RUN

  python3 upgrade_plan/triage/triage_tasks.py \
      --tasks-dir "TASKS_DIR" \
      --settings upgrade_plan/drafts/P1/settings.json \
      --kit Input_Bundle_QC \
      --out upgrade_plan/tmp/TRIAGE_<date>

1. --tasks-dir DIR: the folder that holds the tasks. Repeat it for more folders. Bundles are found at any depth; one task may have many run folders. Runs that sit outside a bundle are joined to it by the task name in result.json (terminal-bench/<name>) or by a folder name; runs that match no bundle become a runs only task named after their top folder.
2. --settings PATH (optional): reads gate.tests, gate.rubric, gate.final, slip_cap_pct, what_if_max and models.paid_run. Without it: tests 85, rubric 85, final 40, slip cap 50, paid model claude-opus-5.
3. --kit DIR (optional): the Input_Bundle_QC folder. Only used to print the kit file and line of each check id. Without it the ids are printed alone.
4. --out DIR: gets TRIAGE.md, triage.csv and triage.json. Must be outside every tasks folder.
Python 3.9 or later, standard library only. A folder of 20 tasks with their runs takes a few seconds.

WHAT THE CLASSES MEAN

1. TRUSTED: a run of the paid model with a score and no sign below. Only these make the real score.
2. BROKEN, with the sign:
   a. permission denied: the verifier output says Permission denied, Errno 13, EACCES or PermissionError.
   b. permission denied (inferred): the tests drop to another uid (setpriv, nobody, uid 65532), nothing in the tests grants read access to the delivered program, the agent's own ls shows the delivered file as -rw-------, and the shipped or interface checks passed while every other positive check failed. This is the pattern of the low score study tasks 07 and 08 (an editor written file is 0600).
   c. grader crash: a Harbor exception in result.json, or a verifier that ran no check (ctrf with 0 tests, a collection error).
   d. grader timeout: a verifier or environment timeout in result.json or the verifier log. A per check timeout of the agent's program is not a broken grade (that is family D4) and stays TRUSTED.
   e. judge or API error: judge reasoning or judge output with a rate limit, API error, status 4xx or 5xx or an authentication error.
   f. missing outputs: a run folder with no verifier score file, or RewardFileNotFoundError.
   g. all zero with errors: tests 0 and rubric 0 next to any of the above.
3. UNSURE, with the sign: permission risk (the uid drop with no read grant and the score shows the split or nothing rules it out), recorded score that differs from its own checks by more than one point, judge with no reasoning and no points, judge criteria missing from a paid run, every failed check with the same message, fewer than 3 agent steps, a pass_summary.json with no run folder, no score at all.
4. A run of another model (glm, gpt) or an oracle or nop agent is shown with its class but never counts as the real score.
A permission hazard is ruled out when the tests grant read access (an OR of read bits into st_mode, a staged copy of the program, a fresh extraction) and the score does not show the split, or when a check whose name says it ran the program on hidden input passed.

WHAT EACH COLUMN MEANS (TRIAGE.md table; the same values in triage.csv)

1. rank, task: order by score; task is the bundle folder name (or the top folder of a runs only task).
2. score: gate part plus levers part plus QC part plus effort part (below).
3. recommendation: FIX AND PUSH (trusted run under the gate: QC with the fix map through the P13 intake, keep the owner's design and author), HARDEN WITH OWNER (trusted run over the gate but within 35 points: hardening changes the design, so the owner agrees first), RE RUN FIRST (no trusted paid run: scores broken, unsure or missing), REGRADE (the current tests or judge differ from what the trusted run was graded with: K2 says regrade the last valid run), DROP (trusted tests at or over 95, more than 35 points over the gate, or nothing to triage).
4. trusted T / R / F: mean tests, rubric and final percent of the trusted paid runs. recorded T / R / F: the same over every paid run, broken ones included, so you see the broken score next to the real one.
5. paid runs T B U: how many paid runs are TRUSTED, BROKEN, UNSURE.
6. sign: the broken or unsure signs of the paid runs.
7. to gate: the largest of (tests minus gate tests, rubric minus gate rubric, final minus gate final); negative means under the gate on all three.
8. families: likely D1 to D9 and decoy, each with evidence lines in the task section.
9. slip pct: the largest share of positive test points one slip took in the basis runs, read as one check, or one property across hidden inputs (check names equal except in one name part), or one hidden input token (h1, seed3, hidden_x). Compare with slip_cap_pct.
10. QC hints: how many QC risk hints; the list is in the task section.
11. why: one line for the recommendation.
triage.csv adds trusted_runs, broken_runs, unsure_runs, slip_check, hidden_lost_pct (all lost hidden input checks together), structure_problems, regrade, the four score parts, data_kb and the path. triage.json holds everything, including every check of every run and every signal with its evidence.

SCORE PARTS

1. gate 0 to 40: 40 when the trusted run is under the gate on tests, rubric and final; falls by 0.8 per point over the gate; 15 when no trusted score exists.
2. levers 0 to 30: 0.2 per lost test percent in the trusted runs (at most 20) plus 2 per family with evidence (at most 10).
3. QC 0 to 20: 20 minus 3 per QC hint and 2 per structure fail (a warn does not count).
4. effort 0 to 10: minus 6 with no bundle, 3 with no trusted run, 3 when one slip is over the cap, 3 when trusted tests are under 10 percent (a solvability check comes first), 2 when a regrade is needed, 1 when the input data is over 50 MB.

LIMITS

1. Every family, slip and QC line is a pattern match on file text and check names. It points at a line to read; it does not decide anything. The deep read is the opencode step in TRIAGE_PROMPT.md.
2. Ctrf files carry no messages in most runs, so the permission inference rests on the uid drop in the tests, the agent's own ls listing and the pass or fail split by check name. A run whose agent never listed its program stays UNSURE (low score study task 09) even when the grade was in fact broken; a task whose tests drop the uid while its own program is also wrong stays UNSURE too (task 10, judged genuine by the study).
3. The split test reads check names (shipped, visible, exists, parse, schema against the rest). A bundle with unusual check names can hide or fake the split.
4. A tests or judge change after the run is found by comparing check names and weights (criteria.NAME(weight=W) lines) and judge criteria names or texts with the run. A change inside a check body with the same name and weight is not seen.
5. The slip estimate sees only what the run lost. A slip that did not happen in this run is not measured; the CL-4 whole document hint covers the structure.
6. Model names are read from pass_summary.json, result.json, config.json or the folder name; a run with none of them shows model unknown and does not count.
7. Text files over 8 MB are read in part; trajectories up to 40 MB.
8. Run folders inside artifacts/, agent/, verifier/ or logs/ are not searched, and a bundle found inside a run folder is ignored.
9. Secrets and emails found in evidence lines are masked; author fields of task.toml are never read into the output. Folder names are printed as given, so a folder named after a person shows that name in TRIAGE.md: keep the output folder private.
