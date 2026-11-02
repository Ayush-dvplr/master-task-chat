# L4: Docker on this Mac: what is stored, why it rebuilds/pulls/polls, how much can run at once, what to clean
OUT: `/Users/mac/Desktop/Terminal Bench/master_chat_work/20261031_learning/L4_docker/`

The master already saved the Docker state at 01:20 IST in `OUT/inventory/` (images.txt = repo|tag|id|size|created, containers.txt, system_df_v.txt, buildx_du_verbose.txt, docker_info.txt, daemon.json). Work from those files. Do NOT run any docker command (your sandbox may not reach Docker anyway).
Ayush: "it always keeps pulling and polling although we have an M1 Max; there are a lot of docker images not needed; clean what can be cleaned."
1. Inventory: 552 images (8.5 GB), 612 build-cache entries (18.7 GB, ~10 GB reclaimable, all used in the last 7 days). Map images to tasks (`hb__<hash>` names, Tasks_INPUT slugs, QC copies), mark each: in use by a live task (Tasks_INPUT / registry stage not dropped), pushed task, parked/dropped task, dangling, base image. `IMAGES.csv`.
2. Why rebuilds/pulls: from QC/fix/gate logs (`/tmp/opencode-logs/*`, `~/tb_runs` if any, `master_chat_work/*/p12_fix_*`, QC reports Step 10) find how often an image was built cold, how long builds took, why (new copy path changes the image name? `--delete`? cache miss?), and what would make builds warm (stable image names, pre-warm once per tree).
3. Capacity: Docker VM 8 vCPU / 15.6 GiB; measured verifier ~1 vCPU, ~330 MiB (MEASURE.md). How many verifier/oracle containers fit at once per task (task.toml memory_mb/cpus); where today's rules (max 2-3 Docker-heavy, serial chains) are stricter than needed.
4. Polling: where our rules make workers sleep-poll Docker (`_COMMON_RULES_v5.md` rules 3/16/18, QC prompts Override 4) and the event-based alternative (`docker events --filter event=die`).
5. Cleanup proposal `CLEANUP.md`: exact commands (NOT run) in safe order with GB freed each: dangling images, images of dropped/parked tasks, old build cache by size limit (`docker builder prune --max-used-space` / `--reserved-space`), what must never be removed (images of live/pushed tasks, base images), and the daemon gc policy already set (`~/.docker/daemon.json`).
Extra: IMAGES.csv, CLEANUP.md.
