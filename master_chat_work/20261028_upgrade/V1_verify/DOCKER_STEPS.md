# Docker and Mac steps for Ayush (Q6, Q7, Q8 N9)

Do these after the upgrade session ends (after Batch 4), when the master says "no Docker job running". Docker Desktop 4.95.0, current values read 29 Oct 00:30 IST: memory 12 GiB (`MemoryMiB 12288` in `~/Library/Group Containers/group.com.docker/settings-store.json`), swap not set (default 1 GiB), `~/.docker/daemon.json` = `{"builder": {"gc": {"defaultKeepStorage": "20GB", "enabled": true}}, "experimental": false}`.

## 1. Pre-check (Terminal.app)

1. `docker ps --format '{{.Names}}'` -> must print nothing. If anything prints, stop and tell the master.
2. `python3 "/Users/mac/Desktop/Terminal Bench/master_chat_tasks/auto/auto.py" status` -> no worker busy, no harness running.
3. Save the old engine JSON: `cp ~/.docker/daemon.json ~/.docker/daemon.json.bak-20261029`.

## 2. Memory 12 -> 16 GiB and swap 1 -> 2 GiB (B-N2, B-N3)

1. Docker Desktop -> Settings (gear, top right) -> Resources -> Advanced.
2. Memory limit slider: 16 GB. Swap: 2 GB. Leave CPUs (8) and disk as they are.
3. Do not press Apply yet if you also do step 3 below; one restart covers both. Otherwise press "Apply & restart".

## 3. Builder cache cleanup policy (B-N4)

1. Settings -> Docker Engine (left list). The box shows the same JSON as `~/.docker/daemon.json`.
2. Replace the whole box with this (old keys kept, policy added; keeps cache used in the last 7 days down to 10 GB, hard cap 20 GB):

```json
{
  "builder": {
    "gc": {
      "enabled": true,
      "defaultKeepStorage": "20GB",
      "policy": [
        { "reservedSpace": "10GB", "keepDuration": ["168h"] },
        { "reservedSpace": "20GB", "all": true }
      ]
    }
  },
  "experimental": false
}
```

3. Press "Apply & restart" (one restart for steps 2 and 3).
4. If Docker shows a config error and will not start: paste the older-format policy instead (R2 version, works on older engines): replace the two policy lines with `{ "keepStorage": "10GB", "filter": ["unused-for=168h"] }, { "keepStorage": "20GB", "all": true }`, Apply & restart again.

The engine version could not be checked in the verify session (no docker commands allowed); the first JSON follows the current Docker docs (build/cache/garbage-collection).

## 4. Post-restart check

1. `docker info --format '{{.MemTotal}} {{.ServerVersion}}'` -> MemTotal about 16.7 billion bytes (16 GiB minus VM overhead, roughly 16.0-16.8e9).
2. `cat ~/.docker/daemon.json` -> shows the `policy` list.
3. `docker buildx du | tail -3` -> runs without error.
4. Tell the master "Docker steps done"; the master runs `docker info` once (G4) and logs it.

## 5. Rollback

- Memory/swap: Settings -> Resources -> Advanced -> 12 GB / 1 GB -> Apply & restart.
- Engine JSON: Settings -> Docker Engine -> paste the old JSON `{"builder": {"gc": {"defaultKeepStorage": "20GB", "enabled": true}}, "experimental": false}` -> Apply & restart (or `cp ~/.docker/daemon.json.bak-20261029 ~/.docker/daemon.json` with Docker quit, then start Docker).

## Q7 — pmset on battery (B-N1)

1. Terminal.app: `pmset -g custom` (note the Battery Power values; R2 found sleep 1, displaysleep 2, powermode 1).
2. `sudo pmset -b sleep 0 displaysleep 10 powermode 0`
3. Check: `pmset -g custom` -> Battery Power shows sleep 0, displaysleep 10, powermode 0.
4. Habit during auto runs: charger in, lid open (closing the lid still sleeps the Mac).
5. Rollback: `sudo pmset -b sleep 1 displaysleep 2 powermode 1`.
Optional (R2 section 4): System Settings -> Battery -> Low Power Mode "Never"; Battery -> Options -> "Prevent automatic sleeping on power adapter when the display is off" on.

## Q8 N9 — Spotlight privacy

1. System Settings -> Spotlight -> "Search Privacy..." (bottom).
2. Press "+", choose `~/Desktop/Terminal Bench`, press Choose, then Done.
3. Rollback: same window, select the folder, press "−".

## Q8 N5 — opencode.db VACUUM (end of day, every opencode window quit)

1. Quit every opencode / VS Code opencode window; `pgrep -fl opencode` -> nothing.
2. `cp ~/.local/share/opencode/opencode.db ~/opencode.db.bak-$(date +%Y%m%d)`
3. `sqlite3 ~/.local/share/opencode/opencode.db 'PRAGMA integrity_check; VACUUM;'` -> prints `ok`; file drops below 4.04 GiB.
Rollback: copy the backup back over `opencode.db` with opencode quit.
