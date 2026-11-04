REQUESTS FROM CLAUDE TO AYUSH

Things Claude cannot see in this repo. Ayush adds them, pushes, and tells Claude. Status: OPEN, DONE, NOT NEEDED.

RQ1. Harness repo (DONE 3 Nov: master_queue.py and state.json pushed to main under "harness queue/")
Terminal_2.0_Harbor_Harness, at least scripts/master_queue.py and anything it imports. Either copy it into upgrade_plan/inputs/harness/ or tell Claude the GitHub owner/repo so it can be added read only.

RQ2. QC kit (DONE 3 Nov: pushed to main under Input_Bundle_QC/)
Input_Bundle_QC (the live kit you QC against). Needed for P2. Copy into upgrade_plan/inputs/qc_kit/.

RQ3. Docker settings (DONE 3 Nov, saved in inputs/mac_docker_20261103.txt)
Run these in Terminal on the Mac and paste the output into chat:

```bash
sysctl hw.memsize hw.ncpu
```

```bash
docker info --format 'mem={{.MemTotal}} cpus={{.NCPU}} os={{.OperatingSystem}} version={{.ServerVersion}}'
```

```bash
docker context ls
```

RQ4. opencode settings (DONE 3 Nov, saved in inputs/opencode_settings_20261103.md)
Paste this prompt into a NEW opencode session and bring back its reply:

```text
Read only. Do not change any file. Report, as plain text:
1. The opencode version (run: opencode --version).
2. The full contents of every opencode config file that exists: ~/.config/opencode/opencode.json, ~/.config/opencode/opencode.jsonc, and opencode.json or opencode.jsonc in "/Users/mac/Desktop/Terminal Bench". Replace any API key or token value with REDACTED.
3. Any agent or command files under ~/.config/opencode/agent, ~/.config/opencode/agents, ~/.config/opencode/command and the same folders under "/Users/mac/Desktop/Terminal Bench/.opencode". List names and paste contents.
4. Whether auto compaction is on, and any compaction settings or custom compaction prompt.
5. The providers and models configured, and which model is the default.
6. The shell alias or function "oc" if it exists (run: type oc; grep -n "oc" ~/.zshrc).
Do not run subagents. Do all work in this chat.
```

RQ1 and RQ2 are part of the W1-003 MUST list (Q64). Full list with counts and reasons: tmp/W1-003/MISSING.md.

RQ5. One example of a compaction loss (OPEN)
A screenshot or pasted text of a moment after compaction where the master got something wrong. Put it in upgrade_plan/inputs/examples/.

RQ6. One example of a QC fix that lost a lever or added errors (OPEN)
Name the task and the board sha; Claude reads the rest from the repo if it is there.

RQ7. One example of Docker waiting (OPEN)
The line a waiting session printed (for example a dockfree START=no line or a queue message).

RQ8. Teammate tasks (DONE 3 Nov: anubis-stage-2/ on main)
Push to main under teammate_tasks/<task name>/: the full bundle (instruction.md, task.toml, environment/, solution/, tests/) and, if you have them, each task's harness scores and QC result. Include the 10 tasks already studied in master_chat_work/20261102_test_design_study if possible, plus any others that scored under the gate. No personal data (emails, keys).

RQ9. Installed DCP 3.2.0 options (DONE 3 Nov, inputs/dcp/RQ9_dcp_3.2.0_summary.md). Paste into opencode GPT Sol 6.1, bring back the reply. Prompt saved in prompts/RQ9_dcp_options.md.
RQ10 (4 Nov, ENTRY 82). Push the updated QC kit to origin/main in the same folder as before (Input_Bundle_QC/, all files including Final_checklist.md and any scripts), and tell Claude the PL's kit commit hash and date if you have them. Status: DONE (487b4697, ENTRY 83).
RQ11 (4 Nov, ENTRY 82). Paste the PL and QL answers to PL_QUESTIONS.md (PL1 to PL30) when they come back. Status: OPEN.
