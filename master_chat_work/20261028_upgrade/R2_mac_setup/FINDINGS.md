# R2 Findings: Mac, Docker, VS Code, opencode (board 151aac5, 28 Oct 2026 IST)

Read-only audit. Nothing was changed. Evidence for each item is in LOG.md.

## 1. Current state

| Component | Setting | Current value | Source |
|---|---|---|---|
| Mac | Model / OS | M1 Max, 10 cores (8P+2E), 32 GiB, macOS 27.0.1 (26A434) | sw_vers, sysctl hw.* |
| Mac | Memory | PhysMem 31G used, compressor 4.3G, swap 910/2048 MB, load 4.57 | top, vm.swapusage |
| Mac | Disk | Data vol 262/926 GiB used, 623 GiB free | df -h |
| Mac | Battery profile | sleep 1, displaysleep 2, powermode 1 (low power), powernap 1 | pmset -g custom |
| Mac | AC profile | sleep 0, displaysleep 3, powermode 2 (high) | pmset -g custom |
| Mac | Sleep events today | clamshell sleep 19:32-20:43 (unplugged + lid closed), about 71 min frozen; also 10:30-11:38 on battery | pmset -g log |
| Mac | Spotlight | indexing on for Data volume, so Terminal Bench tree (10G, ~120k+ files) is indexed | mdutil -s |
| Mac | Time Machine | no destination configured, so exclusions do not matter | tmutil |
| Mac | File limits | shell ulimit -n 1048576; launchctl maxfiles soft 256; kern.maxfilesperproc 122880 | ulimit, launchctl |
| Mac | Folder sizes | harness 2.4G/67.7k files, Anubis_Tasks_Samples 4.1G/33k, anubis-stage-1 2.1G, master_chat_work 1.3G/21.8k, harness/jobs 139M, QC/copies 168M, /tmp/opencode-logs 849M | du -sh |
| Docker | CPUs / memory | Cpus 8, MemoryMiB 12288 (docker info: 8 CPU, 12.53 GB) | settings-store.json, docker info |
| Docker | Swap / disk | SwapMiB and DiskSizeMiB not set, so defaults apply (swap 1 GiB INFERRED); Docker.raw 926G logical, 35G on disk | settings-store.json, ls -ls/du |
| Docker | VM / sharing | Virtualization framework on (VirtioFS is the default with it, INFERRED), Rosetta on, containerd snapshotter on, overlayfs, cgroup v2 | settings-store.json, docker info |
| Docker | Autostart / analytics | AutoStart false, AnalyticsEnabled false | settings-store.json |
| Docker | Storage use | images 8.01 GB (2.69 reclaimable), build cache 28.81 GB across 992 entries (20.82 reclaimable) | docker system df |
| Docker | Build GC | enabled, defaultKeepStorage 20GB, no age policy (cache is 28.8 GB, over the limit) | ~/.docker/daemon.json |
| VS Code | User settings | only 4 keys (theme, paste warning, 2 confirms); no watcher/search/files exclude, git, terminal or telemetry keys | settings.json |
| VS Code | Workspace / repos | workspace = whole Terminal Bench root; 4 git repos inside (harness, Anubis_Tasks_Samples, anubis-stage-1, beta-task-generator) | workspace.json, ls |
| VS Code | Extensions | anthropic.claude-code, remote-ssh, remote-ssh-edit, remote-explorer (no Python/Pylance/Docker) | code --list-extensions |
| VS Code | Load | renderer 14% CPU / 689 MB (43% at 20:52, while it was drawing 7 opencode TUIs); plugin host 269 MB; up 5 days | ps |
| opencode | Plugins | dcp@latest (3.2.0), oh-my-openagent@latest (5.1.33), opencode-anthropic-console (unpinned), opencode-kiro@0.4.0 | opencode.jsonc, tui.json, ~/.cache/opencode/packages |
| opencode | Compaction / DCP | compaction.auto false; dcp.jsonc only has the schema (defaults) | opencode.jsonc, dcp.jsonc |
| opencode | Processes | 7 opencode: 5 workers 1.0-1.15 GB, 24-52% CPU each; 23171 791 MB (4h45m); 15335 `opencode --port 53366 -s` 864 MB (5h53m, parent zsh -il); each has an lsp-daemon (~45 MB) and per turn a kiro-cli-chat (~265 MB) | ps |
| opencode | Database | ~/.local/share/opencode 4.4G; opencode.db 4.0 GB: event table 2.7 GB, part 1.1 GB, message 89 MB; all 7 processes share it | du, sqlite3 -readonly dbstat |
| opencode | Logs | ~/.local/share/opencode/log 144M; /tmp/opencode-logs 849M; /tmp 11,771 entries | du, ls |
| auto.py | Server start | `opencode serve --port 0 --hostname 127.0.0.1` (random port, not 4096) | auto.py:597 |
| auto.py | Health check | `healthy()` timeout 5 s, one miss counts as down (no strike count) | auto.py:271-273 |
| auto.py | caffeinate | `caffeinate -i -s -w <watcher>` only while auto mode is on; none active now | auto.py:621, pmset -g assertions |
| Shell | Startup | `zsh -i -c exit` 0.042 s; PATH has duplicates (.opencode/bin x3, .local/bin x3, Docker bin x3, .docker/bin x2) | time, echo $PATH |
| Git | Status cost | harness `git status` 0.076 s, 38 lines | time git status |

## 2. Recommendations

| id | component | setting | current -> recommended | why (evidence) | class | apply step | rollback | expected effect |
|---|---|---|---|---|---|---|---|---|
| S1 | VS Code | files.watcherExclude | none -> exclude big folders | workspace root holds ~120k+ files in 4 repos plus jobs/copies; nothing excluded | SAFE | add to settings.json: `"files.watcherExclude": {"**/.git/objects/**":true,"**/node_modules/**":true,"**/Terminal_2.0_Harbor_Harness/jobs/**":true,"**/QC/copies/**":true,"**/Anubis_Tasks_Samples/**":true,"**/anubis-stage-1/**":true,"**/master_chat_work/**":true,"**/converted tasks backup/**":true,"**/_tmp_master_tasks_*/**":true}` | restore settings.json backup | fewer fs events and less file-watcher CPU while agents write files (INFERRED size) |
| S2 | VS Code | search.exclude | none -> same folders | same as S1; a search over the root walks 10G | SAFE | `"search.exclude": {` same keys as S1 `}` | backup | faster searches, less ripgrep CPU |
| S3 | VS Code | git repo detection | default (scans all 4 repos, autorefresh each) -> `"git.autoRepositoryDetection": "openEditors"`, `"git.autofetch": false` | 4 repos in root; agents commit/churn files, each change triggers git refresh | SAFE | add the 2 keys | backup | fewer background git status runs (INFERRED) |
| S4 | VS Code | terminal | gpuAcceleration auto, scrollback 1000 -> `"terminal.integrated.gpuAcceleration": "on"`, `"terminal.integrated.scrollback": 5000` | renderer 14-43% CPU drawing 7 TUIs | SAFE | add 2 keys | backup | lower renderer CPU (INFERRED); longer history for non-TUI shells |
| S5 | VS Code | telemetry and auto updates | default -> `"telemetry.telemetryLevel": "off"`, `"extensions.autoUpdate": false`, `"update.mode": "manual"` | 5-day uptime; an update mid-run restarts the extension host or the app | SAFE | add 3 keys | backup | no surprise restarts during runs |
| S6 | opencode | plugin pins | `@latest` x2 + 1 unpinned -> `@tarquinen/opencode-dcp@3.2.0`, `oh-my-openagent@5.1.33` (in opencode.jsonc and tui.json) | 7 processes start with `@latest`, so each start can check npm and a new version can change behavior mid-batch | SAFE (takes effect at next opencode start) | edit the plugin arrays | restore backups | stable starts, no version drift between master and workers |
| S7 | Power | caffeinate for interactive work | caffeinate only runs inside auto mode -> run `caffeinate -i -s -w <master opencode pid> &` when starting a work block | slept 19:32-20:43 with sessions running, and no caffeinate assertion is active now | SAFE | command in apply_safe.md | `kill` that caffeinate pid | stops idle sleep on AC; does NOT stop lid-close sleep on battery (see N1) |
| S8 | Shell | PATH dedupe | 4 duplicated entries -> add `typeset -U path PATH` to the top of ~/.zshrc | duplicates seen in `echo $PATH`; startup already fast (0.042 s) | SAFE | append line to ~/.zshrc | backup | cleaner PATH, effect small |
| N1 | Power | battery sleep / lid | battery sleep 1, displaysleep 2, low power mode -> `sudo pmset -b sleep 0 displaysleep 10 powermode 0`; habit: keep charger in, lid open | 71 min frozen at 19:32 after unplug + lid close; low power mode slows the CPU on battery | NEEDS OK (sudo) | `sudo pmset -b sleep 0 displaysleep 10 powermode 0` | `sudo pmset -b sleep 1 displaysleep 2 powermode 1` | no idle sleep on battery; lid close still sleeps unless `sudo pmset -a disablesleep 1` (not recommended: heat in a bag) |
| N2 | Docker | memory | 12288 -> 16384 MiB, CPUs stay 8 | VM sat at 7.9-11.7 of 12.5 GB with swap use; need: metered 8 GiB + 1 heavy job ~2-3 GiB + harness 2 containers ~1-2 GiB + VM ~1 GiB, about 13-14 GiB (INFERRED); 3 heavy QC jobs without metered already fit in 12 | NEEDS OK (Docker restart) | Docker Desktop > Settings > Resources > Memory 16 GB > Apply & restart | set back to 12 GB | metered run does not swap or get OOM-killed; host keeps 16 GiB |
| N3 | Docker | swap | default 1 GiB -> 2 GiB | swap used during 28 Oct runs | NEEDS OK (restart) | Resources > Swap 2 GB | back to 1 GB | a buffer against OOM spikes |
| N4 | Docker | build cache GC | keep 20GB, no age rule -> age policy | cache 28.8 GB, 20.8 reclaimable, over the 20GB limit | NEEDS OK (daemon restart) | daemon.json `"builder":{"gc":{"enabled":true,"defaultKeepStorage":"20GB","policy":[{"keepStorage":"10GB","filter":["unused-for=168h"]},{"keepStorage":"20GB","all":true}]}}` (Docker Desktop > Settings > Docker Engine) | restore old JSON | about 10-18 GB less disk over time without a manual prune |
| N5 | opencode | DB size | 4.0 GB (event table 2.7 GB) -> back up, then VACUUM / trim old events with all opencode stopped | all 7 processes share the DB; a server at ~100% CPU missed the 17:36 health check (link INFERRED) | NEEDS OK (stop all opencode) | `cp opencode.db opencode.db.bak-YYYYMMDD` then `sqlite3 opencode.db 'VACUUM;'`; trimming events needs an opencode-supported method (unknown, ask) | restore the .bak | smaller DB, faster queries (INFERRED) |
| N6 | auto.py | health check | timeout 5 s, 1 miss = down -> 15 s and 2 misses in a row | 17:36 miss while the server was at ~100% CPU | NEEDS OK (code change + watcher restart) | auto.py:273 `timeout=15` and add a 2-strike counter where watch acts on `healthy()` | git/backup revert | fewer false "server down" events and needless respawns/retries |
| N7 | opencode | stale processes | 15335 (`--port 53366 -s`, 5h53m, 864 MB) and 23171 (4h45m, 791 MB) -> confirm they are still needed, close if not | about 1.6 GB RSS + CPU; 15335 is not on 4096 and its parent is a login shell | NEEDS OK (kill) | close their terminal tabs | start again | about 1.6 GB RAM back |
| N8 | logs | /tmp/opencode-logs | 849M -> delete logs older than 7 days | grows each run | NEEDS OK (delete) | `find /tmp/opencode-logs -type f -mtime +7 -delete` | none (deleted) | about several hundred MB back (INFERRED) |
| N9 | Spotlight | index scope | Terminal Bench indexed -> add Terminal Bench and Docker data to Privacy | ~120k+ files churned by agents and QC copies | NEEDS OK (GUI) | see section 4 | remove from list | less mds/mdworker CPU during QC runs (INFERRED) |

Not recommended: `files.autoSave` (agents edit the same files; an auto-saved editor buffer could overwrite an agent edit), switching Docker engines (out of scope), raising launchctl maxfiles (shells already get 1048576).

## 3. Top 5 by impact, in apply order
1. N1 + habit: charger in, lid open (the only measured outage today: 71 min).
2. N2 + N3: Docker 16 GiB memory, 2 GiB swap (needed for the metered 8 GiB job alongside others).
3. S1-S5: VS Code excludes, git detection, terminal, no auto updates (one settings.json edit).
4. N6: health timeout 15 s + 2 strikes in auto.py (stops false restarts).
5. N5 + N7: DB vacuum and close stale opencode processes (one maintenance window with all opencode stopped).

## 4. GUI steps for Ayush
- Docker memory/swap (N2, N3): Docker Desktop > Settings (gear) > Resources > Advanced > Memory 16 GB, Swap 2 GB > Apply & restart. Do it only when no QC/harness container is running.
- Docker GC (N4): Docker Desktop > Settings > Docker Engine > paste the JSON from N4 > Apply & restart.
- Spotlight (N9): System Settings > Spotlight > Search Privacy... > + > add `~/Desktop/Terminal Bench` > Done.
- Power (part of N1 without sudo): System Settings > Battery > Options > "Prevent automatic sleeping on power adapter when the display is off" on (AC only); Battery > Low Power Mode: "Only on battery" -> "Never".

## 5. Questions for Ayush
1. Raise Docker to 16 GiB memory + 2 GiB swap? Recommended: yes.
2. Change the battery profile with sudo (N1), or only follow the "charger in, lid open" habit? Recommended: do both.
3. Are opencode pids 15335 (`--port 53366`) and 23171 still in use? Recommended: close them if not.
4. May the master change auto.py's health check (15 s, 2 strikes)? Recommended: yes.
5. Plan a 10-minute window with all opencode stopped to back up and VACUUM opencode.db? Recommended: yes, at the end of a day.
6. Delete /tmp/opencode-logs files older than 7 days? Recommended: yes.

## Lessons for the master
- The biggest loss today was sleep (19:32-20:43), not a setting: give every session the rule "charger in, lid open", plus caffeinate.
- Workers run inside VS Code terminals, so VS Code settings matter for opencode load.
- opencode.db is 4 GB and shared by 7 processes; schedule maintenance before adding more workers.
- auto.py uses a random port (`--port 0`), not 4096; prompts that say 4096 are stale.
- Chained shell pipes can run a forbidden command; in audit sessions run each read-only command on its own.
