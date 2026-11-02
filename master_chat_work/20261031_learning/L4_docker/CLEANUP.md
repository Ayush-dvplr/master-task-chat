# Docker cleanup plan (commands for a later idle window; none run tonight)

Snapshot: 31 Oct 2026 01:20 IST. `inventory/images.txt` has 552 IDs; `inventory/buildx_du_verbose.txt:7914-7917` has 18.73 GB of cache (8.517 GB shared, 10.22 GB private). `IMAGES.csv` is the ID allowlist from `python3 scripts/image_inventory.py`. **Run the commands below only after the ongoing task pipeline has finished, and recheck current state first.** The saved snapshot had one exited container (`inventory/system_df_v.txt:557-560`), but says nothing about later activity.

## 0. Recheck before removal

From this OUT directory:

```sh
docker ps --format '{{.ID}} {{.Image}} {{.Names}}'
docker system df -v
python3 scripts/list_cleanup_ids.py 'parked/dropped task' | wc -l
python3 scripts/list_cleanup_ids.py dangling | wc -l
```

Proceed only when `docker ps` has no task containers, the task registry has not revived one of the candidate tasks, and no job is building an image. The selector rereads `master_chat_tasks/registry/tasks.json` and skips any parked/dropped candidate whose stage has changed (`scripts/list_cleanup_ids.py:1-19`); compare the output count with the saved 60 and 24. If counts or IDs differ, regenerate `IMAGES.csv` from a **new read-only Docker inventory** first. Do not remove the one exited container automatically; it may hold debugging evidence.

## 1. Dangling images

```sh
python3 scripts/list_cleanup_ids.py dangling | while IFS= read -r id; do docker image rm "$id"; done
docker system df -v
```

Saved candidates: 24 IDs with zero container references and 0.012 GB image-unique size (`IMAGES.csv` category `dangling`; `python3 scripts/image_inventory.py`). Expected image-accounting reduction: **up to 0.012 GB of unique size**, with actual host disk saving **UNVERIFIED** because cache can retain layers. Failure on an image that gained a reference means stop and investigate, not force removal.

## 2. Parked, dropped and killed task images

```sh
python3 scripts/list_cleanup_ids.py 'parked/dropped task' | while IFS= read -r id; do docker image rm "$id"; done
docker system df -v
```

Saved candidates: 60 IDs, 1.634 GB image-unique size (`IMAGES.csv`; `python3 scripts/image_inventory.py`). Expected image-accounting reduction: **up to 1.634 GB of unique size**, with actual host disk saving **UNVERIFIED** because cache can retain layers. Reusing a parked task later may cost a rebuild. Do not use `docker image prune -a`: that can delete the 342 pushed-task and 83 live-task entries simply because no container currently references them. The 38 unresolved generic trial images and five base/support images are excluded. Two pushed-task images are referenced by the saved exited container (`IMAGES.csv` `containers=1`) and must be left in place.

## 3. Cap build cache

Recommended first pass:

```sh
docker builder prune --max-used-space 15gb --reserved-space 10gb --force
docker system df -v
docker buildx du
```

The saved 18.73 GB cache could fall by about **3.73 GB of Buildx accounting size** to 15 GB (`inventory/buildx_du_verbose.txt:7914-7917`). Host disk freed is **UNVERIFIED** because 8.517 GB of cache is shared with images; the command's exact result depends on cache references, current usage and Docker's eviction selection. If disk pressure still requires more, the more aggressive, separately decided option is:

```sh
docker builder prune --max-used-space 10gb --reserved-space 10gb --force
```

This could remove up to **8.73 GB of accounted cache** from the snapshot, but can make future dependency builds cold. The 128 entries last used eight or more days ago total 7.475 GB of cache accounting (`python3 scripts/build_evidence.py` output `cache_last_used_8plus_days 128 accounted_GB 7.475`); their physical savings and the exact entries evicted by the size cap are **UNVERIFIED**. Current daemon GC is already enabled with `defaultKeepStorage=20GB`, a 168h/10GB reserved policy, and an all/20GB reserved policy (`inventory/daemon.json:2-16`), so an 18.73 GB cache may sit below its effective trim threshold.

## Never remove in this plan

- Live QC and pushed task images (`IMAGES.csv` 83 + 342), including all currently active `Tasks_INPUT` bundles.
- Python/Alpine/curl and Harbor sidecar base/support images (`IMAGES.csv` five rows).
- The 38 generic trial images whose task cannot be assigned safely from the saved names.
- Containers, volumes, task trees, QC copies, run logs or build cache by an unrestricted `docker system prune`.

Check success by comparing `docker system df -v` before/after, then run one frozen-tree verifier build later and confirm its BuildKit log uses cached dependency steps and returns the same gate score. Any image deletion or cache prune changes only Docker storage, not task bundle bytes; the next task use is the operational check.
