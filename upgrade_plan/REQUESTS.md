REQUESTS FROM CLAUDE TO AYUSH

Things Claude cannot see in this repo. Ayush adds them, pushes, and tells Claude. Status: OPEN, DONE, NOT NEEDED.

RQ1. Harness repo (OPEN)
Terminal_2.0_Harbor_Harness, at least scripts/master_queue.py and anything it imports. Either copy it into upgrade_plan/inputs/harness/ or tell Claude the GitHub owner/repo so it can be added read only.

RQ2. QC kit (OPEN)
Input_Bundle_QC (the live kit you QC against). Needed for P2. Copy into upgrade_plan/inputs/qc_kit/.

RQ3. Docker settings (OPEN)
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

RQ4. opencode settings (OPEN)
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

RQ5. One example of a compaction loss (OPEN)
A screenshot or pasted text of a moment after compaction where the master got something wrong. Put it in upgrade_plan/inputs/examples/.

RQ6. One example of a QC fix that lost a lever or added errors (OPEN)
Name the task and the board sha; Claude reads the rest from the repo if it is there.

RQ7. One example of Docker waiting (OPEN)
The line a waiting session printed (for example a dockfree START=no line or a queue message).
