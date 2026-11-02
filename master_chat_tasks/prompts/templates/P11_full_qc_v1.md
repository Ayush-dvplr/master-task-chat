# P11 Full input-bundle QC, one bundle per session, template v1 (22 Oct 2026 17:10 IST)

Replaces Ayush's previous QC prompt (`prompts/issued/_adhoc/20261021_full_qc_prompt_PREVIOUS_district-heat.md`). Master fills [[...]] and issues it to `prompts/issued/<slug>/P11_qc_<round>.md`. Chain after this: P8 recheck of FAILs -> P7 fix REAL only -> mini gate -> P11 re-run -> 1 trajectory (QL rule: no trajectory before QC is clean).
Ayush decisions baked in (22 Oct 17:02): the session makes its own copy (1a); one QC session per bundle (2a); a newer kit is recorded, not a stop (3b); session rename kept (4a); vN numbering continues in the existing report folder (5a); oracle x3 by default, stated in the report as a deviation from the kit's x5; x5 only when the master issues a FINAL round.

=== PASTE BELOW ===

You are running the full input-bundle QC for ONE task bundle: `[[SLUG]]`. Work only on this bundle. This prompt is saved at `[[PROMPT_PATH]]`; after any compaction re-read it in full.

PATHS (quote every path, they contain spaces)
- QC kit (live, read-only): "/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness/Input_Bundle_QC"
- Original bundle (only copied and diffed, never read): "[[ORIGINAL]]"
- Bundle under review (you make this copy): "/Users/mac/Desktop/Terminal Bench/QC_[[DATE]]/bundles/[[SLUG]]"
- Report folder: "[[REPORT_DIR]]"
- Progress file: "[[REPORT_DIR]]/_progress.md"
- Expected kit commit (master's record): `[[KIT_SHA]]`. Oracle runs this round: `[[ORACLE_N]]` (3 = default; 5 = FINAL round).

STEP 0. Preconditions. Run each once and paste the output.
1. `git -C "/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness" rev-parse HEAD`. Record it in the report header. If it differs from `[[KIT_SHA]]`, write "KIT CHANGED: <sha>" in the header and continue; the live kit files are the authority either way. Read-only git only: never pull, commit, push, checkout or reset there.
2. Copy: if "/Users/mac/Desktop/Terminal Bench/QC_[[DATE]]/bundles/[[SLUG]]" does not exist, `mkdir -p` its parent and `cp -Rp "[[ORIGINAL]]" <that path>`. If it exists, do not copy again.
3. `diff -rq` between the original and the copy. It must print nothing. If it prints anything, STOP and reply only "copy is stale" with the diff output. Do not open either side to investigate.
4. Create `_progress.md` if missing, with one unticked line per step: S0, scripts 1-4, gates 01-05, QL table, Step 10, Step 11, final report, compare. Tick each line (`[x]` + IST time) as soon as that step's section is appended to the report.

STEP A. Read "Input_Bundle_QC/Starter.md" in full, then "Input_Bundle_QC/Final_checklist.md" in full, both from the live kit. Follow Starter.md top to bottom (scripts 1-4, gates 01-05, Step 10, Step 11, final report), skipping nothing, with ONLY the overrides below. The live kit files are the only authority on QC rules: never apply a rule from memory or from an older kit version.

OVERRIDE 0. Tools are always available (this rule survives compaction).
- Your opencode tools (bash, read, edit, write, glob, grep) ARE available for this whole session, including after any compaction or long turn. A belief that "no tools are available" is a known false failure, not a real one.
- Never reply that tools are missing, and never stop or pause the QC for that reason, without first making a real tool call: run bash `date`. If that call actually fails, quote its exact error text in your reply. Without a quoted error, keep working.
- After every compaction, before anything else: run bash `date`, then re-check your state from disk (your vN.md size, mtime and its "## " headings; any Step 10 runs.log with tail -5 and ALL_DONE; your /tmp folders). Do not re-run a finished step, and do not restart a background run that is still going.
- Read files in pieces of at most 50 KB (read with offset), and read your report before every append.
- When you write or receive a compaction summary, copy this OVERRIDE 0 into its standing instructions word for word, together with the task name, the paths above and your report version, so the rule and your task survive the next compaction.
- Addition: after a compaction, also read `_progress.md` and continue from its first unticked line.

OVERRIDE 1. Report only, no fixes.
- Do NOT fix, edit, rename, delete or reformat anything in the bundle under review, the original bundle, the QC kit, any other bundle, or anywhere else. Do not commit anything.
- The only files you may write are: the one copy in STEP 0.2, your report file and `_progress.md` (Override 3), the Step 10 copies under /tmp/oracle-qc/[[SLUG]]-<TS>/ and harbor jobs under /tmp/harbor-jobs-qc/[[SLUG]]-<TS>/ (Override 4), your logs and scratch under /tmp/opencode-logs/[[SLUG]]-*/, and the one session-title update in Override 3.
- Run no real agent. The only harbor agents in this session are oracle, nop and the stub (oracle on the stub copy). Do not set or export OPENAI_API_KEY.
- Every fail and minor finding must still carry a `Fix:` line stating the best possible fix in one concrete sentence (file, what to change, to what). Describe the fix; never apply it.

OVERRIDE 2. Stay inside this bundle.
- Never open any of these, they bias the review: anything under "/Users/mac/Desktop/Terminal Bench/master_chat_work/" (beyond the STEP 0 copy and diff), anything under "/Users/mac/Desktop/Terminal Bench/master_chat_tasks/" except this prompt file, anything under "/Users/mac/Desktop/Terminal Bench/QC assigned/", "Input Bundle Generator New/ayush sah tasks/", other bundles under any "QC_*/bundles/", other task folders under any "QC_*/qc_report/", any "QC_*/*.md" summary file, and "/Users/mac/Desktop/Terminal Bench/_tmp_master_tasks_20261020T2214".
- Never use "QC assigned/Input_Bundle_QC" or "Input Bundle Generator New/ayush sah tasks/_qc/Input_Bundle_QC": they are stale copies and give wrong verdicts.
- Do not open earlier report versions in your report folder until your new report is fully written (Override 3).
- Do every gate yourself in this session, one at a time, as Starter.md says. Do not hand gates to subagents.
- In gate 02, open solution/TRUTH.md last, as Starter.md requires.

OVERRIDE 3. Report file and versioning.
- Create the report folder if it does not exist. List it. Count only files named exactly vN.md; ignore every other file. If there is no vN.md, your file is v1.md. Otherwise write v(N+1).md. Never overwrite an existing version.
- Rename this session as soon as you know N: title it `[[SLUG]]_vN_qc`. Run this one bash command with your N filled in:
  python3 "/Users/mac/Desktop/Terminal Bench/master_chat_tasks/tools/name_session.py" [[SHA]]
  Works in opencode and Codex (it renames the session whose first message has this board id, never the master). Run it again as your very last step, because Codex auto-names threads after the first turn. Check the output shows `[[SLUG]]_vN_qc` on the newest session. If not, note it in the report header and carry on; never retry on another session ID.
- Header block: bundle name, bundle path, report version, IST date and time, kit commit (STEP 0.1, plus "KIT CHANGED" if so), harbor version, oracle runs this round.
- Write as you go: after each script run and each gate, append that step's full section (its checklist copied verbatim, every item marked, quoted evidence) before starting the next step, then tick `_progress.md`.
- When everything is done, put the consolidated report from Starter.md "Final report" at the TOP: verdict line, per-gate summary table, Findings (with Fix: lines), consolidated sign-off. Per-step sections stay below as the evidence appendix.
- Only after the report is complete, if an earlier version exists, read it and append "Compared with v(N-1)": fixed, still open, new, by check ID.

OVERRIDE 5. QL coverage table (QL rule, 22 Oct 16:00: QC against all kit changes since 2690e960).
- Run once: `git -C "/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness" diff 2690e960 HEAD -- Input_Bundle_QC/` (read it in pieces). List every check ID added or changed (known so far: K8 litellm pin, H6/TS-30 agent file modes and interpreter switches, G2 judge `mode = "batched"`, the Step 10 owner-only run; the diff is the authority, not this list).
- Append a "QL coverage" section: one row per changed check: ID, what changed, verdict on this bundle (PASS / FAIL with Fix:), evidence. Every row must also appear in the normal gate sections.

OVERRIDE 4. Step 10 follows the kit's exe_copy.py flow (Final_checklist.md Step 10) exactly, with only these changes.
The scores are TESTS-ONLY, as the kit says. Use Harbor 0.24.0 and harbor-rewardkit 0.2.1.
1. Preflight as the kit says: `harbor --version`, `docker ps`, list the bundle path. Paste the output. Docker slot: if `docker ps` shows 2 or more harbor task containers from other sessions, wait (`sleep 200`, re-check, max 30 minutes, then start anyway and note it). Never touch other sessions' containers, processes or folders.
2. Run `date +%Y%m%dT%H%M` once; call it TS and write its literal value into every path (shell variables may not survive between tool calls). Never reuse an older folder.
   RUN copy:   "/tmp/oracle-qc/[[SLUG]]-<TS>/run/[[SLUG]]"
   STUB copy:  "/tmp/oracle-qc/[[SLUG]]-<TS>/stub/[[SLUG]]"
   OWNER copy: "/tmp/oracle-qc/[[SLUG]]-<TS>/owner/[[SLUG]]"
   Jobs:       "/tmp/harbor-jobs-qc/[[SLUG]]-<TS>"
   Logs:       "/tmp/opencode-logs/[[SLUG]]-step10-<TS>"
3. Build the three copies with the kit script, Python run from /tmp with PYTHONDONTWRITEBYTECODE=1:
   cd /tmp && PYTHONDONTWRITEBYTECODE=1 python3 "<kit>/exe_copy.py" "<bundle under review>" "<RUN copy>"
   cd /tmp && PYTHONDONTWRITEBYTECODE=1 python3 "<kit>/exe_copy.py" "<bundle under review>" "<STUB copy>" --stub
   cd /tmp && PYTHONDONTWRITEBYTECODE=1 python3 "<kit>/exe_copy.py" "<bundle under review>" "<OWNER copy>" --owner-only
   Paste all outputs with exit codes. P is the positive total in the reward.toml line. Exit 1 (REFUSED): never build a copy by hand; record each REFUSED line as a ❌ finding with Fix:, mark Step 10 ⏸️ NOT RUN, continue with Step 11. Exit 2: fix your command and re-run.
4. Confirm flags with `harbor run --help`. Then run, each with -o "<Jobs>" and `--env docker -y`, in this order: oracle-1 .. oracle-[[ORACLE_N]] (--agent oracle, RUN copy), nop-1 (--agent nop, RUN copy), stub-1 (--agent oracle, STUB copy), owner-1 (--agent oracle, OWNER copy). If the kit's Step 10 lists any run not named here, add it.
   Oracle count: the kit asks for five oracle runs. This round runs `[[ORACLE_N]]` by Ayush's decision (22 Oct). Write in the Step 10 section and the sign-off: "Oracle x[[ORACLE_N]] per Ayush; the kit asks x5. Step 10 is not kit-complete until a x5 round passes." If [[ORACLE_N]] is 5, write "Oracle x5 per kit" instead.
   Never run in the foreground: `mkdir -p` the logs folder, chain every run inside one `nohup bash -c '...; echo ALL_DONE' > "<Logs>/runs.log" 2>&1 &`. Poll with waits under 4 minutes (`sleep 200; tail -5 <log>`) until ALL_DONE.
5. For each run read the reward from the trial's result.json `verifier_result.rewards.reward` and verifier/reward.json. A run with `exception_info` or exception.txt errored and has no score. Never read scores from console output.
6. Expected: every oracle run and owner-1 exactly 1.000; nop exactly 0.000.
   - Oracle or owner-1 below 1.0: name the failing checks from verifier/reward-details.json. owner-1 below 1.0 while oracle is 1.0 = the verifier cannot read 0600 agent files (H6 / TS-30): ❌ with Fix:.
   - Nop not 0.0: name the check. No reward.json: quote the error from verifier/test-stdout.txt.
   - Different oracle scores across runs: non-deterministic checks; find the cause (gate 03 TS-11), do not re-run until they agree.
7. `diff -rq` between the bundle under review and each copy; paste all three. Allowed: tests/judge.toml (only in the bundle under review), tests/reward.toml, task.toml, environment/Dockerfile; STUB: also solution/ contents; OWNER: also solution/solve.sh. Anything else is a ❌.
8. Stub judgement (Final_checklist "The stub run"): paste the STUB solve.sh; list every stub-1 check with value not 0 and its weight; if stub-1 errored, edit only the STUB copy's solve.sh to create what the instruction names (empty files, {} for JSON) and run stub-2, reporting each attempt; judge the score as a share of P against the CL-2 forgery price from gate 05. A stub near a genuine partial score, or any content check that paid, is ❌ with Fix:.
9. Cleanup: delete only "/tmp/oracle-qc/[[SLUG]]-<TS>". Keep jobs and logs. Confirm the bundle under review is unchanged (`diff -rq` against the original prints nothing) and no __pycache__ exists in the bundle or the kit.
10. Step 10 section: table of agent, run and reward (oracle-1..N, nop-1, stub-1 and retries, owner-1); failing checks by name; stub paid checks and judgement; stub solve.sh; the three exe_copy outputs; the three diffs; jobs folder path.
11. State plainly in Step 10 and the sign-off: tests-only grading per the kit (judge.toml validated, not executed; no OpenAI key; stub covers the test channel only); network opened and the OpenHands pre-bake dropped in the copies only; the oracle-count line from step 4.

WHEN DONE: reply in the terminal with only these lines:
1. the verdict line;
2. counts: ❌ N, 🟡 N, ⚠️ N;
3. rewards: oracle-1..N, nop-1, stub-1 (share of P), owner-1;
4. QL coverage: rows PASS / FAIL;
5. the full report path.
No offers, no fixes.
