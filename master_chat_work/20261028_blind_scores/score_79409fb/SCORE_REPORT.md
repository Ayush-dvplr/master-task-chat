# Blind score report: metered-usage-rating-pipeline (board 79409fb)

Bundle `master_chat_work/bundles/metered-usage-rating-pipeline` after redesign 361674d (task.toml: memory_mb 8192, cpus 2, verifier timeout_sec 2700). Bundle and blind folders unchanged; all program runs in Docker.

Session rename: `name_session.py 79409fb` printed `codex: no match` / `opencode: ['ses_e7ea86dd8ffexO9WQTstDo33bz']`; it did not show 79409fb. Not retried.

## Summary

| blind | tests% | points | LV-MU-9 lost (harden round) | LV-MU-8 lost (earlier lever) | loss kind | non-lever lost | loses >=10% | gate v3.6 (<=80) | verifier peak (cgroup memory.peak / docker-stats usage) | verifier wall |
|---|---|---|---|---|---|---|---|---|---|---|
| d5c7b9d | 60.69 | 247/407 | 32/32 (112 pts) | 12/12 (48 pts) | TIMEOUT | 0 | yes (39.3%) | pass | 7.693 GiB / 6.32 GiB | 1038 s |
| f4f4ff5 | 60.69 | 247/407 | 32/32 (112 pts) | 12/12 (48 pts) | TIMEOUT | 0 | yes (39.3%) | pass | 6.867 GiB / 5.743 GiB | 1042 s |
| 4d36b26 | 72.48 | 295/407 | 32/32 (112 pts) | 0/12 (0 pts) | TIMEOUT | 0 | yes (27.5%) | pass | 8.000 GiB / 6.74 GiB | 1058 s |

Oracle sanity (bundle's own solve.sh on the same copy recipe): reward 1.0, 407/407, negative not fired; verifier 1179 s; memory.peak 6.851 GiB, usage max 5.947 GiB.

All four verifier wall times are under timeout_sec 2700 (max 1179 s). All peaks are at or under memory_mb 8192 (8.000 GiB). No crash or OOM: every failure message is a 15 s timeout, every verifier finished and wrote reward.json.

## Method

- Copies: `exe_copy.py <bundle> /tmp/score_79409fb/<name>` for oracle and each blind (rc 0): judge.toml dropped, reward.toml test weight 1/407, network public, OpenHands venv dropped. Tests unchanged.
- Blind copies only: `solution/blind/{app,out}` = blind `app/` and `out/` (cp -Rp); `solution/solve.sh` replaced by the install script in `logs/<run>/solve.sh` (`cp -Rp blind/app/. /app/`, `cp -Rp blind/out/. /app/out/`, then diff/cmp/sha256 printout).
- Run: `OPENAI_API_KEY=unused yes | harbor run --path <copy> --agent oracle --env docker -y`, one nohup chain (`logs/chain.sh`, `logs/runs.log`), sequential, ended ALL_DONE; lock `/tmp/opencode-logs/locks/metered-usage-rating-pipeline.lock`.
- tests% = (positive points earned - fired negatives) / 407 positive total, the same as reward.toml (one negative check, `negative_hardcoded_sample_answers` w-5; it did not fire in any run).
- Memory: harbor started verifier containers with **no memory limit** (HostConfig.Memory 0, 11.67 GiB visible). `logs/enforce.sh` applied the declared limit with `docker update --memory 8192m --memory-swap 8192m --cpus 2` every 3 s (`logs/enforce.log`). The cap was applied at verifier start for d5c7b9d and f4f4ff5, ~15 s in for 4d36b26, and ~5 min late for the oracle run, which was already at 4.27 GB peak. A sampler logged `docker stats` usage and cgroup `memory.peak` every 10 s (`logs/mem.log`). memory.peak counts page cache, so 4d36b26 reaching exactly 8.000 GiB means the cgroup filled to the limit and reclaimed cache. Its anonymous usage peaked at 6.74 GiB with no OOM kill (an OOM-killed child would show `failed: ... rc -9`, and none did).
- Timing follow-up (Docker, tests image built from `tests/Dockerfile`, `--memory 8192m --cpus 2`, `scripts/time_ladder.py`, `logs/time.log`): each blind's transform.py ran on ladder month 1 and long month 1 (rebuilt by the bundle's own `_ladder_files`/`_long_files`), with a 100 s cap, and the output was compared to `ref_compute`.

## Pair d5c7b9d

Blind folder `/tmp/blind/metered-usage-rating-pipeline-20261028T120151-de51`.

Install map:

| blind path | /app path |
|---|---|
| app/transform.py (sha256 fc78d0bbd1be42fe...) | /app/transform.py |
| out/transform.py (byte-identical to app/transform.py) | /app/out/transform.py (the program the tests run) |
| out/{normalized.jsonl, summary.json, data_quality.json, product_summary.json, region_{central,east,north,south,west}.json, segment_{consumer,corporate,enterprise,smb}.json} | /app/out/<same name> |

Diff proof:
```
host: diff -r /tmp/blind/metered-usage-rating-pipeline-20261028T120151-de51/app  solution/blind/app  -> identical
host: diff -r /tmp/blind/metered-usage-rating-pipeline-20261028T120151-de51/out  solution/blind/out  -> identical
container (agent/oracle.txt): diff out: identical ; cmp transform.py: identical
container sha256 /app/transform.py == /app/out/transform.py == fc78d0bbd1be42fe...
```
No `/tmp/blind` path in any delivered file.

Score: 247/407 = **60.69%** (reward 0.6069); negative not fired. Oracle sanity on the same recipe 1.0. Verifier 07:31:34Z-07:48:52Z = 1038 s; cgroup memory.peak 7.693 GiB, docker-stats usage max 6.32 GiB (limit 8 GiB; cap applied at verifier start).

Lever checks lost: LV-MU-9 (the harden round's `ladder_1..4_*`, 32 checks, 112 pts): **32/32 lost, all TIMEOUT** (`long-card month k: no result within 15 seconds` / `no documents for long-card month k within 15 seconds`). Measured: ladder month 1 >100 s (killed at 100 s cap); test limit 15 s.
LV-MU-8 (earlier lever, `long_1..3_*`, 12 checks, 48 pts): **12/12 lost, all TIMEOUT** (`long fresh month k: no result within 15 seconds`). Measured: long month 1 77.50 s, all 13 documents equal to reference, so the documents are correct and the loss is speed only.
Non-lever checks lost: **0** (all 63 non-lever positive checks pass). The timeout loss is confined to lever checks (Law-1 v3.5 holds). Loses >= 10% of positive points: yes (39.3%). Gate v3.6 blind bar (<= 80): pass.

Per-check table:

| check | weight | lever | result | failure kind | first assertion line |
|---|---|---|---|---|---|
| accepted_lines | 3 |  | PASS | | |
| accepted_lines_hard | 5 |  | PASS | | |
| rating_central | 3 |  | PASS | | |
| rating_central_hard | 5 |  | PASS | | |
| rating_east | 3 |  | PASS | | |
| rating_east_hard | 5 |  | PASS | | |
| rating_north | 3 |  | PASS | | |
| rating_north_hard | 5 |  | PASS | | |
| rating_south | 3 |  | PASS | | |
| rating_south_hard | 5 |  | PASS | | |
| rating_west | 3 |  | PASS | | |
| rating_west_hard | 5 |  | PASS | | |
| credit_central | 3 |  | PASS | | |
| credit_central_hard | 5 |  | PASS | | |
| credit_east | 3 |  | PASS | | |
| credit_east_hard | 5 |  | PASS | | |
| credit_north | 3 |  | PASS | | |
| credit_north_hard | 5 |  | PASS | | |
| credit_south | 3 |  | PASS | | |
| credit_south_hard | 5 |  | PASS | | |
| credit_west | 3 |  | PASS | | |
| credit_west_hard | 5 |  | PASS | | |
| true_up_central | 3 |  | PASS | | |
| true_up_central_hard | 5 |  | PASS | | |
| true_up_east | 3 |  | PASS | | |
| true_up_east_hard | 5 |  | PASS | | |
| true_up_north | 3 |  | PASS | | |
| true_up_north_hard | 5 |  | PASS | | |
| true_up_south | 3 |  | PASS | | |
| true_up_south_hard | 5 |  | PASS | | |
| true_up_west | 3 |  | PASS | | |
| true_up_west_hard | 5 |  | PASS | | |
| region_central | 3 |  | PASS | | |
| region_central_hard | 5 |  | PASS | | |
| region_east | 3 |  | PASS | | |
| region_east_hard | 5 |  | PASS | | |
| region_north | 3 |  | PASS | | |
| region_north_hard | 5 |  | PASS | | |
| region_south | 3 |  | PASS | | |
| region_south_hard | 5 |  | PASS | | |
| region_west | 3 |  | PASS | | |
| region_west_hard | 5 |  | PASS | | |
| segment_consumer | 3 |  | PASS | | |
| segment_consumer_hard | 5 |  | PASS | | |
| segment_corporate | 3 |  | PASS | | |
| segment_corporate_hard | 5 |  | PASS | | |
| segment_enterprise | 3 |  | PASS | | |
| segment_enterprise_hard | 5 |  | PASS | | |
| segment_smb | 3 |  | PASS | | |
| segment_smb_hard | 5 |  | PASS | | |
| product_summary | 3 |  | PASS | | |
| product_summary_hard | 5 |  | PASS | | |
| summary | 3 |  | PASS | | |
| summary_hard | 5 |  | PASS | | |
| data_quality | 3 |  | PASS | | |
| data_quality_hard | 5 |  | PASS | | |
| mutation_tier_scale | 5 |  | PASS | | |
| mutation_small_commitment | 3 |  | PASS | | |
| mutation_near_base_pool | 5 |  | PASS | | |
| missing_collector | 3 |  | PASS | | |
| control_mismatch | 3 |  | PASS | | |
| determinism | 3 |  | PASS | | |
| transform_exists | 1 |  | PASS | | |
| negative_hardcoded_sample_answers | -5 | | not fired | | |
| long_1_finishes | 3 | LV-MU-8 | FAIL | TIMEOUT | `long fresh month 1: no result within 15 seconds` |
| long_1_normalized | 5 | LV-MU-8 | FAIL | TIMEOUT | `no documents for long fresh month 1 within 15 seconds` |
| long_1_summary | 5 | LV-MU-8 | FAIL | TIMEOUT | `no documents for long fresh month 1 within 15 seconds` |
| long_1_product_summary | 3 | LV-MU-8 | FAIL | TIMEOUT | `no documents for long fresh month 1 within 15 seconds` |
| long_2_finishes | 3 | LV-MU-8 | FAIL | TIMEOUT | `long fresh month 2: no result within 15 seconds` |
| long_2_normalized | 5 | LV-MU-8 | FAIL | TIMEOUT | `no documents for long fresh month 2 within 15 seconds` |
| long_2_summary | 5 | LV-MU-8 | FAIL | TIMEOUT | `no documents for long fresh month 2 within 15 seconds` |
| long_2_product_summary | 3 | LV-MU-8 | FAIL | TIMEOUT | `no documents for long fresh month 2 within 15 seconds` |
| long_3_finishes | 3 | LV-MU-8 | FAIL | TIMEOUT | `long fresh month 3: no result within 15 seconds` |
| long_3_normalized | 5 | LV-MU-8 | FAIL | TIMEOUT | `no documents for long fresh month 3 within 15 seconds` |
| long_3_summary | 5 | LV-MU-8 | FAIL | TIMEOUT | `no documents for long fresh month 3 within 15 seconds` |
| long_3_product_summary | 3 | LV-MU-8 | FAIL | TIMEOUT | `no documents for long fresh month 3 within 15 seconds` |
| ladder_1_finishes | 3 | LV-MU-9 | FAIL | TIMEOUT | `long-card month 1: no result within 15 seconds` |
| ladder_1_normalized | 5 | LV-MU-9 | FAIL | TIMEOUT | `no documents for long-card month 1 within 15 seconds` |
| ladder_1_summary | 5 | LV-MU-9 | FAIL | TIMEOUT | `no documents for long-card month 1 within 15 seconds` |
| ladder_1_product_summary | 3 | LV-MU-9 | FAIL | TIMEOUT | `no documents for long-card month 1 within 15 seconds` |
| ladder_1_segment_consumer | 3 | LV-MU-9 | FAIL | TIMEOUT | `no documents for long-card month 1 within 15 seconds` |
| ladder_1_segment_corporate | 3 | LV-MU-9 | FAIL | TIMEOUT | `no documents for long-card month 1 within 15 seconds` |
| ladder_1_segment_enterprise | 3 | LV-MU-9 | FAIL | TIMEOUT | `no documents for long-card month 1 within 15 seconds` |
| ladder_1_segment_smb | 3 | LV-MU-9 | FAIL | TIMEOUT | `no documents for long-card month 1 within 15 seconds` |
| ladder_2_finishes | 3 | LV-MU-9 | FAIL | TIMEOUT | `long-card month 2: no result within 15 seconds` |
| ladder_2_normalized | 5 | LV-MU-9 | FAIL | TIMEOUT | `no documents for long-card month 2 within 15 seconds` |
| ladder_2_summary | 5 | LV-MU-9 | FAIL | TIMEOUT | `no documents for long-card month 2 within 15 seconds` |
| ladder_2_product_summary | 3 | LV-MU-9 | FAIL | TIMEOUT | `no documents for long-card month 2 within 15 seconds` |
| ladder_2_segment_consumer | 3 | LV-MU-9 | FAIL | TIMEOUT | `no documents for long-card month 2 within 15 seconds` |
| ladder_2_segment_corporate | 3 | LV-MU-9 | FAIL | TIMEOUT | `no documents for long-card month 2 within 15 seconds` |
| ladder_2_segment_enterprise | 3 | LV-MU-9 | FAIL | TIMEOUT | `no documents for long-card month 2 within 15 seconds` |
| ladder_2_segment_smb | 3 | LV-MU-9 | FAIL | TIMEOUT | `no documents for long-card month 2 within 15 seconds` |
| ladder_3_finishes | 3 | LV-MU-9 | FAIL | TIMEOUT | `long-card month 3: no result within 15 seconds` |
| ladder_3_normalized | 5 | LV-MU-9 | FAIL | TIMEOUT | `no documents for long-card month 3 within 15 seconds` |
| ladder_3_summary | 5 | LV-MU-9 | FAIL | TIMEOUT | `no documents for long-card month 3 within 15 seconds` |
| ladder_3_product_summary | 3 | LV-MU-9 | FAIL | TIMEOUT | `no documents for long-card month 3 within 15 seconds` |
| ladder_3_segment_consumer | 3 | LV-MU-9 | FAIL | TIMEOUT | `no documents for long-card month 3 within 15 seconds` |
| ladder_3_segment_corporate | 3 | LV-MU-9 | FAIL | TIMEOUT | `no documents for long-card month 3 within 15 seconds` |
| ladder_3_segment_enterprise | 3 | LV-MU-9 | FAIL | TIMEOUT | `no documents for long-card month 3 within 15 seconds` |
| ladder_3_segment_smb | 3 | LV-MU-9 | FAIL | TIMEOUT | `no documents for long-card month 3 within 15 seconds` |
| ladder_4_finishes | 3 | LV-MU-9 | FAIL | TIMEOUT | `long-card month 4: no result within 15 seconds` |
| ladder_4_normalized | 5 | LV-MU-9 | FAIL | TIMEOUT | `no documents for long-card month 4 within 15 seconds` |
| ladder_4_summary | 5 | LV-MU-9 | FAIL | TIMEOUT | `no documents for long-card month 4 within 15 seconds` |
| ladder_4_product_summary | 3 | LV-MU-9 | FAIL | TIMEOUT | `no documents for long-card month 4 within 15 seconds` |
| ladder_4_segment_consumer | 3 | LV-MU-9 | FAIL | TIMEOUT | `no documents for long-card month 4 within 15 seconds` |
| ladder_4_segment_corporate | 3 | LV-MU-9 | FAIL | TIMEOUT | `no documents for long-card month 4 within 15 seconds` |
| ladder_4_segment_enterprise | 3 | LV-MU-9 | FAIL | TIMEOUT | `no documents for long-card month 4 within 15 seconds` |
| ladder_4_segment_smb | 3 | LV-MU-9 | FAIL | TIMEOUT | `no documents for long-card month 4 within 15 seconds` |


## Pair f4f4ff5

Blind folder `/tmp/blind/metered-usage-rating-pipeline-20261028T120252-1626`.

Install map:

| blind path | /app path |
|---|---|
| app/transform.py (sha256 a2d2f31af28cab32...) | /app/transform.py |
| out/transform.py (byte-identical to app/transform.py) | /app/out/transform.py (the program the tests run) |
| out/{normalized.jsonl, summary.json, data_quality.json, product_summary.json, region_{central,east,north,south,west}.json, segment_{consumer,corporate,enterprise,smb}.json} | /app/out/<same name> |

Diff proof:
```
host: diff -r /tmp/blind/metered-usage-rating-pipeline-20261028T120252-1626/app  solution/blind/app  -> identical
host: diff -r /tmp/blind/metered-usage-rating-pipeline-20261028T120252-1626/out  solution/blind/out  -> identical
container (agent/oracle.txt): diff out: identical ; cmp transform.py: identical
container sha256 /app/transform.py == /app/out/transform.py == a2d2f31af28cab32...
```
No `/tmp/blind` path in any delivered file.

Score: 247/407 = **60.69%** (reward 0.6069); negative not fired. Oracle sanity on the same recipe 1.0. Verifier 07:49:06Z-08:06:28Z = 1042 s; cgroup memory.peak 6.867 GiB, docker-stats usage max 5.743 GiB (limit 8 GiB; cap applied at verifier start).

Lever checks lost: LV-MU-9 (the harden round's `ladder_1..4_*`, 32 checks, 112 pts): **32/32 lost, all TIMEOUT** (`long-card month k: no result within 15 seconds` / `no documents for long-card month k within 15 seconds`). Measured: ladder month 1 >100 s (killed at 100 s cap); test limit 15 s.
LV-MU-8 (earlier lever, `long_1..3_*`, 12 checks, 48 pts): **12/12 lost, all TIMEOUT** (`long fresh month k: no result within 15 seconds`). Measured: long month 1 86.24 s, all 13 documents equal to reference, so the documents are correct and the loss is speed only.
Non-lever checks lost: **0** (all 63 non-lever positive checks pass). The timeout loss is confined to lever checks (Law-1 v3.5 holds). Loses >= 10% of positive points: yes (39.3%). Gate v3.6 blind bar (<= 80): pass.

Per-check table:

| check | weight | lever | result | failure kind | first assertion line |
|---|---|---|---|---|---|
| accepted_lines | 3 |  | PASS | | |
| accepted_lines_hard | 5 |  | PASS | | |
| rating_central | 3 |  | PASS | | |
| rating_central_hard | 5 |  | PASS | | |
| rating_east | 3 |  | PASS | | |
| rating_east_hard | 5 |  | PASS | | |
| rating_north | 3 |  | PASS | | |
| rating_north_hard | 5 |  | PASS | | |
| rating_south | 3 |  | PASS | | |
| rating_south_hard | 5 |  | PASS | | |
| rating_west | 3 |  | PASS | | |
| rating_west_hard | 5 |  | PASS | | |
| credit_central | 3 |  | PASS | | |
| credit_central_hard | 5 |  | PASS | | |
| credit_east | 3 |  | PASS | | |
| credit_east_hard | 5 |  | PASS | | |
| credit_north | 3 |  | PASS | | |
| credit_north_hard | 5 |  | PASS | | |
| credit_south | 3 |  | PASS | | |
| credit_south_hard | 5 |  | PASS | | |
| credit_west | 3 |  | PASS | | |
| credit_west_hard | 5 |  | PASS | | |
| true_up_central | 3 |  | PASS | | |
| true_up_central_hard | 5 |  | PASS | | |
| true_up_east | 3 |  | PASS | | |
| true_up_east_hard | 5 |  | PASS | | |
| true_up_north | 3 |  | PASS | | |
| true_up_north_hard | 5 |  | PASS | | |
| true_up_south | 3 |  | PASS | | |
| true_up_south_hard | 5 |  | PASS | | |
| true_up_west | 3 |  | PASS | | |
| true_up_west_hard | 5 |  | PASS | | |
| region_central | 3 |  | PASS | | |
| region_central_hard | 5 |  | PASS | | |
| region_east | 3 |  | PASS | | |
| region_east_hard | 5 |  | PASS | | |
| region_north | 3 |  | PASS | | |
| region_north_hard | 5 |  | PASS | | |
| region_south | 3 |  | PASS | | |
| region_south_hard | 5 |  | PASS | | |
| region_west | 3 |  | PASS | | |
| region_west_hard | 5 |  | PASS | | |
| segment_consumer | 3 |  | PASS | | |
| segment_consumer_hard | 5 |  | PASS | | |
| segment_corporate | 3 |  | PASS | | |
| segment_corporate_hard | 5 |  | PASS | | |
| segment_enterprise | 3 |  | PASS | | |
| segment_enterprise_hard | 5 |  | PASS | | |
| segment_smb | 3 |  | PASS | | |
| segment_smb_hard | 5 |  | PASS | | |
| product_summary | 3 |  | PASS | | |
| product_summary_hard | 5 |  | PASS | | |
| summary | 3 |  | PASS | | |
| summary_hard | 5 |  | PASS | | |
| data_quality | 3 |  | PASS | | |
| data_quality_hard | 5 |  | PASS | | |
| mutation_tier_scale | 5 |  | PASS | | |
| mutation_small_commitment | 3 |  | PASS | | |
| mutation_near_base_pool | 5 |  | PASS | | |
| missing_collector | 3 |  | PASS | | |
| control_mismatch | 3 |  | PASS | | |
| determinism | 3 |  | PASS | | |
| transform_exists | 1 |  | PASS | | |
| negative_hardcoded_sample_answers | -5 | | not fired | | |
| long_1_finishes | 3 | LV-MU-8 | FAIL | TIMEOUT | `long fresh month 1: no result within 15 seconds` |
| long_1_normalized | 5 | LV-MU-8 | FAIL | TIMEOUT | `no documents for long fresh month 1 within 15 seconds` |
| long_1_summary | 5 | LV-MU-8 | FAIL | TIMEOUT | `no documents for long fresh month 1 within 15 seconds` |
| long_1_product_summary | 3 | LV-MU-8 | FAIL | TIMEOUT | `no documents for long fresh month 1 within 15 seconds` |
| long_2_finishes | 3 | LV-MU-8 | FAIL | TIMEOUT | `long fresh month 2: no result within 15 seconds` |
| long_2_normalized | 5 | LV-MU-8 | FAIL | TIMEOUT | `no documents for long fresh month 2 within 15 seconds` |
| long_2_summary | 5 | LV-MU-8 | FAIL | TIMEOUT | `no documents for long fresh month 2 within 15 seconds` |
| long_2_product_summary | 3 | LV-MU-8 | FAIL | TIMEOUT | `no documents for long fresh month 2 within 15 seconds` |
| long_3_finishes | 3 | LV-MU-8 | FAIL | TIMEOUT | `long fresh month 3: no result within 15 seconds` |
| long_3_normalized | 5 | LV-MU-8 | FAIL | TIMEOUT | `no documents for long fresh month 3 within 15 seconds` |
| long_3_summary | 5 | LV-MU-8 | FAIL | TIMEOUT | `no documents for long fresh month 3 within 15 seconds` |
| long_3_product_summary | 3 | LV-MU-8 | FAIL | TIMEOUT | `no documents for long fresh month 3 within 15 seconds` |
| ladder_1_finishes | 3 | LV-MU-9 | FAIL | TIMEOUT | `long-card month 1: no result within 15 seconds` |
| ladder_1_normalized | 5 | LV-MU-9 | FAIL | TIMEOUT | `no documents for long-card month 1 within 15 seconds` |
| ladder_1_summary | 5 | LV-MU-9 | FAIL | TIMEOUT | `no documents for long-card month 1 within 15 seconds` |
| ladder_1_product_summary | 3 | LV-MU-9 | FAIL | TIMEOUT | `no documents for long-card month 1 within 15 seconds` |
| ladder_1_segment_consumer | 3 | LV-MU-9 | FAIL | TIMEOUT | `no documents for long-card month 1 within 15 seconds` |
| ladder_1_segment_corporate | 3 | LV-MU-9 | FAIL | TIMEOUT | `no documents for long-card month 1 within 15 seconds` |
| ladder_1_segment_enterprise | 3 | LV-MU-9 | FAIL | TIMEOUT | `no documents for long-card month 1 within 15 seconds` |
| ladder_1_segment_smb | 3 | LV-MU-9 | FAIL | TIMEOUT | `no documents for long-card month 1 within 15 seconds` |
| ladder_2_finishes | 3 | LV-MU-9 | FAIL | TIMEOUT | `long-card month 2: no result within 15 seconds` |
| ladder_2_normalized | 5 | LV-MU-9 | FAIL | TIMEOUT | `no documents for long-card month 2 within 15 seconds` |
| ladder_2_summary | 5 | LV-MU-9 | FAIL | TIMEOUT | `no documents for long-card month 2 within 15 seconds` |
| ladder_2_product_summary | 3 | LV-MU-9 | FAIL | TIMEOUT | `no documents for long-card month 2 within 15 seconds` |
| ladder_2_segment_consumer | 3 | LV-MU-9 | FAIL | TIMEOUT | `no documents for long-card month 2 within 15 seconds` |
| ladder_2_segment_corporate | 3 | LV-MU-9 | FAIL | TIMEOUT | `no documents for long-card month 2 within 15 seconds` |
| ladder_2_segment_enterprise | 3 | LV-MU-9 | FAIL | TIMEOUT | `no documents for long-card month 2 within 15 seconds` |
| ladder_2_segment_smb | 3 | LV-MU-9 | FAIL | TIMEOUT | `no documents for long-card month 2 within 15 seconds` |
| ladder_3_finishes | 3 | LV-MU-9 | FAIL | TIMEOUT | `long-card month 3: no result within 15 seconds` |
| ladder_3_normalized | 5 | LV-MU-9 | FAIL | TIMEOUT | `no documents for long-card month 3 within 15 seconds` |
| ladder_3_summary | 5 | LV-MU-9 | FAIL | TIMEOUT | `no documents for long-card month 3 within 15 seconds` |
| ladder_3_product_summary | 3 | LV-MU-9 | FAIL | TIMEOUT | `no documents for long-card month 3 within 15 seconds` |
| ladder_3_segment_consumer | 3 | LV-MU-9 | FAIL | TIMEOUT | `no documents for long-card month 3 within 15 seconds` |
| ladder_3_segment_corporate | 3 | LV-MU-9 | FAIL | TIMEOUT | `no documents for long-card month 3 within 15 seconds` |
| ladder_3_segment_enterprise | 3 | LV-MU-9 | FAIL | TIMEOUT | `no documents for long-card month 3 within 15 seconds` |
| ladder_3_segment_smb | 3 | LV-MU-9 | FAIL | TIMEOUT | `no documents for long-card month 3 within 15 seconds` |
| ladder_4_finishes | 3 | LV-MU-9 | FAIL | TIMEOUT | `long-card month 4: no result within 15 seconds` |
| ladder_4_normalized | 5 | LV-MU-9 | FAIL | TIMEOUT | `no documents for long-card month 4 within 15 seconds` |
| ladder_4_summary | 5 | LV-MU-9 | FAIL | TIMEOUT | `no documents for long-card month 4 within 15 seconds` |
| ladder_4_product_summary | 3 | LV-MU-9 | FAIL | TIMEOUT | `no documents for long-card month 4 within 15 seconds` |
| ladder_4_segment_consumer | 3 | LV-MU-9 | FAIL | TIMEOUT | `no documents for long-card month 4 within 15 seconds` |
| ladder_4_segment_corporate | 3 | LV-MU-9 | FAIL | TIMEOUT | `no documents for long-card month 4 within 15 seconds` |
| ladder_4_segment_enterprise | 3 | LV-MU-9 | FAIL | TIMEOUT | `no documents for long-card month 4 within 15 seconds` |
| ladder_4_segment_smb | 3 | LV-MU-9 | FAIL | TIMEOUT | `no documents for long-card month 4 within 15 seconds` |


## Pair 4d36b26

Blind folder `/tmp/blind/metered-usage-rating-pipeline-20261028T120354-f05d`.

Install map:

| blind path | /app path |
|---|---|
| app/transform.py (sha256 6588526e821d26fb...) | /app/transform.py |
| out/transform.py (byte-identical to app/transform.py) | /app/out/transform.py (the program the tests run) |
| out/{normalized.jsonl, summary.json, data_quality.json, product_summary.json, region_{central,east,north,south,west}.json, segment_{consumer,corporate,enterprise,smb}.json} | /app/out/<same name> |

Diff proof:
```
host: diff -r /tmp/blind/metered-usage-rating-pipeline-20261028T120354-f05d/app  solution/blind/app  -> identical
host: diff -r /tmp/blind/metered-usage-rating-pipeline-20261028T120354-f05d/out  solution/blind/out  -> identical
container (agent/oracle.txt): diff out: identical ; cmp transform.py: identical
container sha256 /app/transform.py == /app/out/transform.py == 6588526e821d26fb...
```
No `/tmp/blind` path in any delivered file.

Score: 295/407 = **72.48%** (reward 0.7248); negative not fired. Oracle sanity on the same recipe 1.0. Verifier 08:06:42Z-08:24:20Z = 1058 s; cgroup memory.peak 8.000 GiB, docker-stats usage max 6.74 GiB (limit 8 GiB; cap applied 13:36:45, ~15 s after start).

Lever checks lost: LV-MU-9 (the harden round's `ladder_1..4_*`, 32 checks, 112 pts): **32/32 lost, all TIMEOUT** (`long-card month k: no result within 15 seconds` / `no documents for long-card month k within 15 seconds`). Measured: ladder month 1 >100 s (killed at 100 s cap); test limit 15 s.
LV-MU-8 (`long_1..3_*`, 48 pts): all 12 PASS (long month 1 2.27 s, all 13 documents equal to reference).
Non-lever checks lost: **0** (all 63 non-lever positive checks pass). The timeout loss is confined to lever checks (Law-1 v3.5 holds). Loses >= 10% of positive points: yes (27.5%). Gate v3.6 blind bar (<= 80): pass.

Per-check table:

| check | weight | lever | result | failure kind | first assertion line |
|---|---|---|---|---|---|
| accepted_lines | 3 |  | PASS | | |
| accepted_lines_hard | 5 |  | PASS | | |
| rating_central | 3 |  | PASS | | |
| rating_central_hard | 5 |  | PASS | | |
| rating_east | 3 |  | PASS | | |
| rating_east_hard | 5 |  | PASS | | |
| rating_north | 3 |  | PASS | | |
| rating_north_hard | 5 |  | PASS | | |
| rating_south | 3 |  | PASS | | |
| rating_south_hard | 5 |  | PASS | | |
| rating_west | 3 |  | PASS | | |
| rating_west_hard | 5 |  | PASS | | |
| credit_central | 3 |  | PASS | | |
| credit_central_hard | 5 |  | PASS | | |
| credit_east | 3 |  | PASS | | |
| credit_east_hard | 5 |  | PASS | | |
| credit_north | 3 |  | PASS | | |
| credit_north_hard | 5 |  | PASS | | |
| credit_south | 3 |  | PASS | | |
| credit_south_hard | 5 |  | PASS | | |
| credit_west | 3 |  | PASS | | |
| credit_west_hard | 5 |  | PASS | | |
| true_up_central | 3 |  | PASS | | |
| true_up_central_hard | 5 |  | PASS | | |
| true_up_east | 3 |  | PASS | | |
| true_up_east_hard | 5 |  | PASS | | |
| true_up_north | 3 |  | PASS | | |
| true_up_north_hard | 5 |  | PASS | | |
| true_up_south | 3 |  | PASS | | |
| true_up_south_hard | 5 |  | PASS | | |
| true_up_west | 3 |  | PASS | | |
| true_up_west_hard | 5 |  | PASS | | |
| region_central | 3 |  | PASS | | |
| region_central_hard | 5 |  | PASS | | |
| region_east | 3 |  | PASS | | |
| region_east_hard | 5 |  | PASS | | |
| region_north | 3 |  | PASS | | |
| region_north_hard | 5 |  | PASS | | |
| region_south | 3 |  | PASS | | |
| region_south_hard | 5 |  | PASS | | |
| region_west | 3 |  | PASS | | |
| region_west_hard | 5 |  | PASS | | |
| segment_consumer | 3 |  | PASS | | |
| segment_consumer_hard | 5 |  | PASS | | |
| segment_corporate | 3 |  | PASS | | |
| segment_corporate_hard | 5 |  | PASS | | |
| segment_enterprise | 3 |  | PASS | | |
| segment_enterprise_hard | 5 |  | PASS | | |
| segment_smb | 3 |  | PASS | | |
| segment_smb_hard | 5 |  | PASS | | |
| product_summary | 3 |  | PASS | | |
| product_summary_hard | 5 |  | PASS | | |
| summary | 3 |  | PASS | | |
| summary_hard | 5 |  | PASS | | |
| data_quality | 3 |  | PASS | | |
| data_quality_hard | 5 |  | PASS | | |
| mutation_tier_scale | 5 |  | PASS | | |
| mutation_small_commitment | 3 |  | PASS | | |
| mutation_near_base_pool | 5 |  | PASS | | |
| missing_collector | 3 |  | PASS | | |
| control_mismatch | 3 |  | PASS | | |
| determinism | 3 |  | PASS | | |
| transform_exists | 1 |  | PASS | | |
| negative_hardcoded_sample_answers | -5 | | not fired | | |
| long_1_finishes | 3 | LV-MU-8 | PASS | | |
| long_1_normalized | 5 | LV-MU-8 | PASS | | |
| long_1_summary | 5 | LV-MU-8 | PASS | | |
| long_1_product_summary | 3 | LV-MU-8 | PASS | | |
| long_2_finishes | 3 | LV-MU-8 | PASS | | |
| long_2_normalized | 5 | LV-MU-8 | PASS | | |
| long_2_summary | 5 | LV-MU-8 | PASS | | |
| long_2_product_summary | 3 | LV-MU-8 | PASS | | |
| long_3_finishes | 3 | LV-MU-8 | PASS | | |
| long_3_normalized | 5 | LV-MU-8 | PASS | | |
| long_3_summary | 5 | LV-MU-8 | PASS | | |
| long_3_product_summary | 3 | LV-MU-8 | PASS | | |
| ladder_1_finishes | 3 | LV-MU-9 | FAIL | TIMEOUT | `long-card month 1: no result within 15 seconds` |
| ladder_1_normalized | 5 | LV-MU-9 | FAIL | TIMEOUT | `no documents for long-card month 1 within 15 seconds` |
| ladder_1_summary | 5 | LV-MU-9 | FAIL | TIMEOUT | `no documents for long-card month 1 within 15 seconds` |
| ladder_1_product_summary | 3 | LV-MU-9 | FAIL | TIMEOUT | `no documents for long-card month 1 within 15 seconds` |
| ladder_1_segment_consumer | 3 | LV-MU-9 | FAIL | TIMEOUT | `no documents for long-card month 1 within 15 seconds` |
| ladder_1_segment_corporate | 3 | LV-MU-9 | FAIL | TIMEOUT | `no documents for long-card month 1 within 15 seconds` |
| ladder_1_segment_enterprise | 3 | LV-MU-9 | FAIL | TIMEOUT | `no documents for long-card month 1 within 15 seconds` |
| ladder_1_segment_smb | 3 | LV-MU-9 | FAIL | TIMEOUT | `no documents for long-card month 1 within 15 seconds` |
| ladder_2_finishes | 3 | LV-MU-9 | FAIL | TIMEOUT | `long-card month 2: no result within 15 seconds` |
| ladder_2_normalized | 5 | LV-MU-9 | FAIL | TIMEOUT | `no documents for long-card month 2 within 15 seconds` |
| ladder_2_summary | 5 | LV-MU-9 | FAIL | TIMEOUT | `no documents for long-card month 2 within 15 seconds` |
| ladder_2_product_summary | 3 | LV-MU-9 | FAIL | TIMEOUT | `no documents for long-card month 2 within 15 seconds` |
| ladder_2_segment_consumer | 3 | LV-MU-9 | FAIL | TIMEOUT | `no documents for long-card month 2 within 15 seconds` |
| ladder_2_segment_corporate | 3 | LV-MU-9 | FAIL | TIMEOUT | `no documents for long-card month 2 within 15 seconds` |
| ladder_2_segment_enterprise | 3 | LV-MU-9 | FAIL | TIMEOUT | `no documents for long-card month 2 within 15 seconds` |
| ladder_2_segment_smb | 3 | LV-MU-9 | FAIL | TIMEOUT | `no documents for long-card month 2 within 15 seconds` |
| ladder_3_finishes | 3 | LV-MU-9 | FAIL | TIMEOUT | `long-card month 3: no result within 15 seconds` |
| ladder_3_normalized | 5 | LV-MU-9 | FAIL | TIMEOUT | `no documents for long-card month 3 within 15 seconds` |
| ladder_3_summary | 5 | LV-MU-9 | FAIL | TIMEOUT | `no documents for long-card month 3 within 15 seconds` |
| ladder_3_product_summary | 3 | LV-MU-9 | FAIL | TIMEOUT | `no documents for long-card month 3 within 15 seconds` |
| ladder_3_segment_consumer | 3 | LV-MU-9 | FAIL | TIMEOUT | `no documents for long-card month 3 within 15 seconds` |
| ladder_3_segment_corporate | 3 | LV-MU-9 | FAIL | TIMEOUT | `no documents for long-card month 3 within 15 seconds` |
| ladder_3_segment_enterprise | 3 | LV-MU-9 | FAIL | TIMEOUT | `no documents for long-card month 3 within 15 seconds` |
| ladder_3_segment_smb | 3 | LV-MU-9 | FAIL | TIMEOUT | `no documents for long-card month 3 within 15 seconds` |
| ladder_4_finishes | 3 | LV-MU-9 | FAIL | TIMEOUT | `long-card month 4: no result within 15 seconds` |
| ladder_4_normalized | 5 | LV-MU-9 | FAIL | TIMEOUT | `no documents for long-card month 4 within 15 seconds` |
| ladder_4_summary | 5 | LV-MU-9 | FAIL | TIMEOUT | `no documents for long-card month 4 within 15 seconds` |
| ladder_4_product_summary | 3 | LV-MU-9 | FAIL | TIMEOUT | `no documents for long-card month 4 within 15 seconds` |
| ladder_4_segment_consumer | 3 | LV-MU-9 | FAIL | TIMEOUT | `no documents for long-card month 4 within 15 seconds` |
| ladder_4_segment_corporate | 3 | LV-MU-9 | FAIL | TIMEOUT | `no documents for long-card month 4 within 15 seconds` |
| ladder_4_segment_enterprise | 3 | LV-MU-9 | FAIL | TIMEOUT | `no documents for long-card month 4 within 15 seconds` |
| ladder_4_segment_smb | 3 | LV-MU-9 | FAIL | TIMEOUT | `no documents for long-card month 4 within 15 seconds` |


