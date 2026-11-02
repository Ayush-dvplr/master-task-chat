# apply_safe (board 151aac5): run only after Ayush says "proceed"

SAFE items only (user-level, no sudo, no restart). Back up first at each step.

## S1-S5 VS Code settings
1. Backup: `cp "$HOME/Library/Application Support/Code/User/settings.json" "$HOME/Library/Application Support/Code/User/settings.json.bak-20261028-r2"`
2. Add these keys to settings.json, keeping the 4 existing keys:
```json
"files.watcherExclude": {
  "**/.git/objects/**": true, "**/node_modules/**": true,
  "**/Terminal_2.0_Harbor_Harness/jobs/**": true, "**/QC/copies/**": true,
  "**/Anubis_Tasks_Samples/**": true, "**/anubis-stage-1/**": true,
  "**/master_chat_work/**": true, "**/converted tasks backup/**": true,
  "**/_tmp_master_tasks_*/**": true
},
"search.exclude": {
  "**/Terminal_2.0_Harbor_Harness/jobs/**": true, "**/QC/copies/**": true,
  "**/Anubis_Tasks_Samples/**": true, "**/anubis-stage-1/**": true,
  "**/master_chat_work/**": true, "**/converted tasks backup/**": true,
  "**/_tmp_master_tasks_*/**": true
},
"git.autoRepositoryDetection": "openEditors",
"git.autofetch": false,
"terminal.integrated.gpuAcceleration": "on",
"terminal.integrated.scrollback": 5000,
"telemetry.telemetryLevel": "off",
"extensions.autoUpdate": false,
"update.mode": "manual"
```
3. Check: `python3 -c "import json,sys;json.load(open(sys.argv[1]))" "$HOME/Library/Application Support/Code/User/settings.json"` (the file has no comments now, so plain JSON must parse). VS Code applies these live.
4. Rollback: copy the .bak back.

## S6 opencode plugin pins (effect at next opencode start; do not restart running sessions)
1. Backup: `cp ~/.config/opencode/opencode.jsonc ~/.config/opencode/opencode.jsonc.bak-20261028-r2pins; cp ~/.config/opencode/tui.json ~/.config/opencode/tui.json.bak-20261028-r2pins`
2. In both files replace `"@tarquinen/opencode-dcp@latest"` with `"@tarquinen/opencode-dcp@3.2.0"` and `"oh-my-openagent@latest"` with `"oh-my-openagent@5.1.33"` (versions in ~/.cache/opencode/packages today). Leave models, providers and permissions as they are.
3. Rollback: copy the .bak files back.

## S7 caffeinate for interactive work blocks
1. Backup: none needed (no file change).
2. `caffeinate -i -s -w <master opencode pid> >/dev/null 2>&1 &` (find the pid with `ps -axo pid,etime,command | grep '[o]pencode$'`).
3. Check: `pmset -g assertions | grep caffeinate`.
4. Rollback: `kill <caffeinate pid>`. Note: `-s` works on AC only; lid close on battery still sleeps.

## S8 PATH dedupe
1. Backup: `cp ~/.zshrc ~/.zshrc.bak-20261028-r2`
2. Insert `typeset -U path PATH` as the first line of ~/.zshrc.
3. Check: `zsh -i -c 'echo $PATH' | tr ':' '\n' | sort | uniq -d` prints nothing.
4. Rollback: copy the .bak back.
