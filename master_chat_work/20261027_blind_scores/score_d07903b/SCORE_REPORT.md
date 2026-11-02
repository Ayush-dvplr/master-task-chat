# SCORE_REPORT: metered-usage-rating-pipeline blind scores (board d07903b)

Bundle (read only): `/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/metered-usage-rating-pipeline` (after harden 09963d3). Session rename: `name_session.py d07903b` printed `codex: no match` / `opencode: ['ses_e81fde296ffeZ6HDoGFcOG4Izs']`; d07903b not shown, not retried.

## Method
- Tests read `/app/out/transform.py` (rerun on hidden, mutated and long fresh months as `nobody`, `python -I`, foreign cwd, 15 s subprocess timeout `RUN_LIMIT_SEC`) and the 13 delivered documents in `/app/out/`.
- Four tests-only copies built with the kit `exe_copy.py` into `/tmp/score_d07903b/{oracle,6f5046a,204228e,ebaba1c}` (logs `logs/exe_copy_*.log`): judge.toml deleted, reward.toml `test_output = 1/295`, network public, OpenHands venv layer dropped. In each blind copy only `solution/solve.sh` was replaced (kept as `logs/job_<sha>/solve.sh.blind`) and the blind files were staged under `solution/blind/{app,out}`.
- Runs: `export OPENAI_API_KEY=unused; yes | harbor run --path <copy> --agent oracle --env docker --job-name d07903b-<s> -y`, one nohup chain, sequential (one Docker job of mine at a time), lock `/tmp/opencode-logs/locks/metered-usage-rating-pipeline.lock` taken and removed, chain ended `ALL_DONE` (`logs/chain.log`).
- Measured seconds: the verifier kills a run at 15 s and records no time, so each delivered program was also timed in Docker (`python:3.12-slim`, `--cpus 2 --memory 4g`, `logs/measure.py`) on the same three long corpora built by the bundle's own generator (`_long_files(k)`), 180 s cap, foreign cwd, `-I`; documents compared with the tests' own `_first_diff` against `ref_compute` (`logs/timing.jsonl`, ended `rc=0`, `ALL_DONE`).
- tests% = (positive points passed - fired negatives) / 295, as reward.toml (`weighted-sum`, 1/295 in the copy).

## Oracle sanity
Bundle oracle (unchanged solve.sh) on the same copy recipe: reward **1.0** = 295/295, 0 failed, negative `negative_hardcoded_sample_answers` not fired (`logs/job_oracle/`). Oracle long-month times: 2.12 / 2.19 / 2.78 s.

## Lever checks (from HARDEN_REPORT 09963d3)
P-3 billing group on long fresh months within the stated 15 s: the 12 checks `long_k_finishes` (3), `long_k_normalized` (5), `long_k_summary` (5), `long_k_product_summary` (3), k = 1..3; 48 of 295 positive points (16.3%).

## Pair 6f5046a: blind `/tmp/blind/metered-usage-rating-pipeline-20261027T202450-d576`

**Install map**: `/tmp/blind/metered-usage-rating-pipeline-20261027T202450-d576/app/transform.py` -> `/app/out/transform.py` (byte-identical to the blind's `out/transform.py`); `/tmp/blind/metered-usage-rating-pipeline-20261027T202450-d576/out/*` (14 files) -> `/app/out/*`. No other file placed; `/app/data` untouched. No `/tmp/blind`, `/Users/` or `environment/data` path in any delivered file.

**Diff proof**: host `diff -r` of blind `app/` and `out/` vs the staged `solution/blind/` copy: identical. Inside the container after install (solve.sh stdout, `logs/job_6f5046a/oracle.txt`):
```
INSTALLED:
ee57cf351dcd5b0570da0f05f0be8dcf4b48ad46370ae85ca061fff2523cc7e9  data_quality.json
e3976291d8ba820d482b358a142a7f8ef3d5600b79286ca66f2af9ccf08dad2b  normalized.jsonl
f63d0b00c612dd1a3bdd5007a9f5168c800a82a17e14130ccfa0f3321e417b28  product_summary.json
ffecc8111fa928135b66131a3ea44a90af6f397eb52776b8818945a9229784d2  region_central.json
51c41b203d7241bfded8ea6586686a60a337b0e57b5451175fa432c5bcc68c45  region_east.json
d3bed28aa4b2f34752f25e8d0e36431d7529d2398041c943b7c3deaaddb8702d  region_north.json
7ec9589bd40c2c137294694a7a4c41c0a77a9865c68d80e3b538a4750168bebb  region_south.json
d249d7216e60479f558f0582a4317f81bf538ac525098a8002f81db7b75cef6a  region_west.json
a93f821c4ec7d5027f6dd02d7ece6773aa8fde0cd88c4a1366f443a9616af399  segment_consumer.json
6a9e6c64d25ae70150fb506b6dab8e9a387c761837f52fd23a0c6b5d9629a50d  segment_corporate.json
cde1c32eaa18f0147f0f0adebce3d3014c2d623b9d4f13b9eeab0c4f4f7bba13  segment_enterprise.json
ad1bca90a525ef01c35cb33a11cdd1da1bb1bf89df6fe918c3f2eb740cc31dbc  segment_smb.json
6211cb51cc54981e77b04c240d7debc7ad5a34edc9152ebcd8345362598122d4  summary.json
942db97434d683e6f3e83b359d85175eeaa8436bf64abb2a326971d16cacb4f1  transform.py
DIFF app/transform.py vs /app/out/transform.py:
identical
DIFF -r blind out vs /app/out:
identical
```
Host sha256 of the blind `out/` files (`logs/host_sha_6f5046a.txt`) matches the INSTALLED list line for line:
```
ee57cf351dcd5b0570da0f05f0be8dcf4b48ad46370ae85ca061fff2523cc7e9  data_quality.json
e3976291d8ba820d482b358a142a7f8ef3d5600b79286ca66f2af9ccf08dad2b  normalized.jsonl
f63d0b00c612dd1a3bdd5007a9f5168c800a82a17e14130ccfa0f3321e417b28  product_summary.json
ffecc8111fa928135b66131a3ea44a90af6f397eb52776b8818945a9229784d2  region_central.json
51c41b203d7241bfded8ea6586686a60a337b0e57b5451175fa432c5bcc68c45  region_east.json
d3bed28aa4b2f34752f25e8d0e36431d7529d2398041c943b7c3deaaddb8702d  region_north.json
7ec9589bd40c2c137294694a7a4c41c0a77a9865c68d80e3b538a4750168bebb  region_south.json
d249d7216e60479f558f0582a4317f81bf538ac525098a8002f81db7b75cef6a  region_west.json
a93f821c4ec7d5027f6dd02d7ece6773aa8fde0cd88c4a1366f443a9616af399  segment_consumer.json
6a9e6c64d25ae70150fb506b6dab8e9a387c761837f52fd23a0c6b5d9629a50d  segment_corporate.json
cde1c32eaa18f0147f0f0adebce3d3014c2d623b9d4f13b9eeab0c4f4f7bba13  segment_enterprise.json
ad1bca90a525ef01c35cb33a11cdd1da1bb1bf89df6fe918c3f2eb740cc31dbc  segment_smb.json
6211cb51cc54981e77b04c240d7debc7ad5a34edc9152ebcd8345362598122d4  summary.json
942db97434d683e6f3e83b359d85175eeaa8436bf64abb2a326971d16cacb4f1  transform.py
```

**Result**: reward 0.8373 -> tests% = (247 - 0) / 295 = **83.73%**. Points lost: 48/295 (16.3%) -> loses >= 10% of positive points: **YES**. Lever points lost: 48/48 (12/12 checks). Non-lever checks lost: 0 (0 pts). Negative check fired: no.

**Lever loss kind: TIMEOUT** (all 12 lost lever checks). In the verifier every long month hit the 15 s subprocess timeout (`returncode None`, no documents). Measured in Docker without the cap: long-1 83.04 s, long-2 112.32 s, long-3 133.62 s, exit 0, and normalized.jsonl, summary.json and product_summary.json are all **exact** on all three months, so the loss is purely the time limit, not a wrong document and not a crash. The loss is confined to lever checks (no non-lever loss), so under Law-1 v3.5 it counts.

| check | weight | result | failure kind | first assertion line |
|---|---|---|---|---|
| accepted_lines | 3 | pass | - | - |
| accepted_lines_hard | 5 | pass | - | - |
| rating_central | 3 | pass | - | - |
| rating_central_hard | 5 | pass | - | - |
| rating_east | 3 | pass | - | - |
| rating_east_hard | 5 | pass | - | - |
| rating_north | 3 | pass | - | - |
| rating_north_hard | 5 | pass | - | - |
| rating_south | 3 | pass | - | - |
| rating_south_hard | 5 | pass | - | - |
| rating_west | 3 | pass | - | - |
| rating_west_hard | 5 | pass | - | - |
| credit_central | 3 | pass | - | - |
| credit_central_hard | 5 | pass | - | - |
| credit_east | 3 | pass | - | - |
| credit_east_hard | 5 | pass | - | - |
| credit_north | 3 | pass | - | - |
| credit_north_hard | 5 | pass | - | - |
| credit_south | 3 | pass | - | - |
| credit_south_hard | 5 | pass | - | - |
| credit_west | 3 | pass | - | - |
| credit_west_hard | 5 | pass | - | - |
| true_up_central | 3 | pass | - | - |
| true_up_central_hard | 5 | pass | - | - |
| true_up_east | 3 | pass | - | - |
| true_up_east_hard | 5 | pass | - | - |
| true_up_north | 3 | pass | - | - |
| true_up_north_hard | 5 | pass | - | - |
| true_up_south | 3 | pass | - | - |
| true_up_south_hard | 5 | pass | - | - |
| true_up_west | 3 | pass | - | - |
| true_up_west_hard | 5 | pass | - | - |
| region_central | 3 | pass | - | - |
| region_central_hard | 5 | pass | - | - |
| region_east | 3 | pass | - | - |
| region_east_hard | 5 | pass | - | - |
| region_north | 3 | pass | - | - |
| region_north_hard | 5 | pass | - | - |
| region_south | 3 | pass | - | - |
| region_south_hard | 5 | pass | - | - |
| region_west | 3 | pass | - | - |
| region_west_hard | 5 | pass | - | - |
| segment_consumer | 3 | pass | - | - |
| segment_consumer_hard | 5 | pass | - | - |
| segment_corporate | 3 | pass | - | - |
| segment_corporate_hard | 5 | pass | - | - |
| segment_enterprise | 3 | pass | - | - |
| segment_enterprise_hard | 5 | pass | - | - |
| segment_smb | 3 | pass | - | - |
| segment_smb_hard | 5 | pass | - | - |
| product_summary | 3 | pass | - | - |
| product_summary_hard | 5 | pass | - | - |
| summary | 3 | pass | - | - |
| summary_hard | 5 | pass | - | - |
| data_quality | 3 | pass | - | - |
| data_quality_hard | 5 | pass | - | - |
| mutation_tier_scale | 5 | pass | - | - |
| mutation_small_commitment | 3 | pass | - | - |
| mutation_near_base_pool | 5 | pass | - | - |
| missing_collector | 3 | pass | - | - |
| control_mismatch | 3 | pass | - | - |
| determinism | 3 | pass | - | - |
| transform_exists | 1 | pass | - | - |
| negative_hardcoded_sample_answers | -5 | not fired | - | - |
| long_1_finishes (lever) | 3 | FAIL | TIMEOUT | long fresh month 1: no result within 15 seconds |
| long_1_normalized (lever) | 5 | FAIL | TIMEOUT | no documents for long fresh month 1 within 15 seconds |
| long_1_summary (lever) | 5 | FAIL | TIMEOUT | no documents for long fresh month 1 within 15 seconds |
| long_1_product_summary (lever) | 3 | FAIL | TIMEOUT | no documents for long fresh month 1 within 15 seconds |
| long_2_finishes (lever) | 3 | FAIL | TIMEOUT | long fresh month 2: no result within 15 seconds |
| long_2_normalized (lever) | 5 | FAIL | TIMEOUT | no documents for long fresh month 2 within 15 seconds |
| long_2_summary (lever) | 5 | FAIL | TIMEOUT | no documents for long fresh month 2 within 15 seconds |
| long_2_product_summary (lever) | 3 | FAIL | TIMEOUT | no documents for long fresh month 2 within 15 seconds |
| long_3_finishes (lever) | 3 | FAIL | TIMEOUT | long fresh month 3: no result within 15 seconds |
| long_3_normalized (lever) | 5 | FAIL | TIMEOUT | no documents for long fresh month 3 within 15 seconds |
| long_3_summary (lever) | 5 | FAIL | TIMEOUT | no documents for long fresh month 3 within 15 seconds |
| long_3_product_summary (lever) | 3 | FAIL | TIMEOUT | no documents for long fresh month 3 within 15 seconds |

## Pair 204228e: blind `/tmp/blind/metered-usage-rating-pipeline-20261027T203846-c60b`

**Install map**: `/tmp/blind/metered-usage-rating-pipeline-20261027T203846-c60b/app/transform.py` -> `/app/out/transform.py` (byte-identical to the blind's `out/transform.py`); `/tmp/blind/metered-usage-rating-pipeline-20261027T203846-c60b/out/*` (14 files) -> `/app/out/*`. No other file placed; `/app/data` untouched. No `/tmp/blind`, `/Users/` or `environment/data` path in any delivered file.

**Diff proof**: host `diff -r` of blind `app/` and `out/` vs the staged `solution/blind/` copy: identical. Inside the container after install (solve.sh stdout, `logs/job_204228e/oracle.txt`):
```
INSTALLED:
ee57cf351dcd5b0570da0f05f0be8dcf4b48ad46370ae85ca061fff2523cc7e9  data_quality.json
e3976291d8ba820d482b358a142a7f8ef3d5600b79286ca66f2af9ccf08dad2b  normalized.jsonl
f63d0b00c612dd1a3bdd5007a9f5168c800a82a17e14130ccfa0f3321e417b28  product_summary.json
ffecc8111fa928135b66131a3ea44a90af6f397eb52776b8818945a9229784d2  region_central.json
51c41b203d7241bfded8ea6586686a60a337b0e57b5451175fa432c5bcc68c45  region_east.json
d3bed28aa4b2f34752f25e8d0e36431d7529d2398041c943b7c3deaaddb8702d  region_north.json
7ec9589bd40c2c137294694a7a4c41c0a77a9865c68d80e3b538a4750168bebb  region_south.json
d249d7216e60479f558f0582a4317f81bf538ac525098a8002f81db7b75cef6a  region_west.json
a93f821c4ec7d5027f6dd02d7ece6773aa8fde0cd88c4a1366f443a9616af399  segment_consumer.json
6a9e6c64d25ae70150fb506b6dab8e9a387c761837f52fd23a0c6b5d9629a50d  segment_corporate.json
cde1c32eaa18f0147f0f0adebce3d3014c2d623b9d4f13b9eeab0c4f4f7bba13  segment_enterprise.json
ad1bca90a525ef01c35cb33a11cdd1da1bb1bf89df6fe918c3f2eb740cc31dbc  segment_smb.json
6211cb51cc54981e77b04c240d7debc7ad5a34edc9152ebcd8345362598122d4  summary.json
59701bda3809f694845cc40061cd5ef02073c1ee8cea27eb6eb5df6293ab5dfe  transform.py
DIFF app/transform.py vs /app/out/transform.py:
identical
DIFF -r blind out vs /app/out:
identical
```
Host sha256 of the blind `out/` files (`logs/host_sha_204228e.txt`) matches the INSTALLED list line for line:
```
ee57cf351dcd5b0570da0f05f0be8dcf4b48ad46370ae85ca061fff2523cc7e9  data_quality.json
e3976291d8ba820d482b358a142a7f8ef3d5600b79286ca66f2af9ccf08dad2b  normalized.jsonl
f63d0b00c612dd1a3bdd5007a9f5168c800a82a17e14130ccfa0f3321e417b28  product_summary.json
ffecc8111fa928135b66131a3ea44a90af6f397eb52776b8818945a9229784d2  region_central.json
51c41b203d7241bfded8ea6586686a60a337b0e57b5451175fa432c5bcc68c45  region_east.json
d3bed28aa4b2f34752f25e8d0e36431d7529d2398041c943b7c3deaaddb8702d  region_north.json
7ec9589bd40c2c137294694a7a4c41c0a77a9865c68d80e3b538a4750168bebb  region_south.json
d249d7216e60479f558f0582a4317f81bf538ac525098a8002f81db7b75cef6a  region_west.json
a93f821c4ec7d5027f6dd02d7ece6773aa8fde0cd88c4a1366f443a9616af399  segment_consumer.json
6a9e6c64d25ae70150fb506b6dab8e9a387c761837f52fd23a0c6b5d9629a50d  segment_corporate.json
cde1c32eaa18f0147f0f0adebce3d3014c2d623b9d4f13b9eeab0c4f4f7bba13  segment_enterprise.json
ad1bca90a525ef01c35cb33a11cdd1da1bb1bf89df6fe918c3f2eb740cc31dbc  segment_smb.json
6211cb51cc54981e77b04c240d7debc7ad5a34edc9152ebcd8345362598122d4  summary.json
59701bda3809f694845cc40061cd5ef02073c1ee8cea27eb6eb5df6293ab5dfe  transform.py
```

**Result**: reward 1.0 -> tests% = (295 - 0) / 295 = **100.0%**. Points lost: 0/295 (0.0%) -> loses >= 10% of positive points: **NO**. Lever points lost: 0/48 (0/12 checks). Non-lever checks lost: 0 (0 pts). Negative check fired: no.

**Lever checks**: all 12 pass. Measured long-month times: 2.21 / 2.9 / 2.36 s, all documents exact.

| check | weight | result | failure kind | first assertion line |
|---|---|---|---|---|
| accepted_lines | 3 | pass | - | - |
| accepted_lines_hard | 5 | pass | - | - |
| rating_central | 3 | pass | - | - |
| rating_central_hard | 5 | pass | - | - |
| rating_east | 3 | pass | - | - |
| rating_east_hard | 5 | pass | - | - |
| rating_north | 3 | pass | - | - |
| rating_north_hard | 5 | pass | - | - |
| rating_south | 3 | pass | - | - |
| rating_south_hard | 5 | pass | - | - |
| rating_west | 3 | pass | - | - |
| rating_west_hard | 5 | pass | - | - |
| credit_central | 3 | pass | - | - |
| credit_central_hard | 5 | pass | - | - |
| credit_east | 3 | pass | - | - |
| credit_east_hard | 5 | pass | - | - |
| credit_north | 3 | pass | - | - |
| credit_north_hard | 5 | pass | - | - |
| credit_south | 3 | pass | - | - |
| credit_south_hard | 5 | pass | - | - |
| credit_west | 3 | pass | - | - |
| credit_west_hard | 5 | pass | - | - |
| true_up_central | 3 | pass | - | - |
| true_up_central_hard | 5 | pass | - | - |
| true_up_east | 3 | pass | - | - |
| true_up_east_hard | 5 | pass | - | - |
| true_up_north | 3 | pass | - | - |
| true_up_north_hard | 5 | pass | - | - |
| true_up_south | 3 | pass | - | - |
| true_up_south_hard | 5 | pass | - | - |
| true_up_west | 3 | pass | - | - |
| true_up_west_hard | 5 | pass | - | - |
| region_central | 3 | pass | - | - |
| region_central_hard | 5 | pass | - | - |
| region_east | 3 | pass | - | - |
| region_east_hard | 5 | pass | - | - |
| region_north | 3 | pass | - | - |
| region_north_hard | 5 | pass | - | - |
| region_south | 3 | pass | - | - |
| region_south_hard | 5 | pass | - | - |
| region_west | 3 | pass | - | - |
| region_west_hard | 5 | pass | - | - |
| segment_consumer | 3 | pass | - | - |
| segment_consumer_hard | 5 | pass | - | - |
| segment_corporate | 3 | pass | - | - |
| segment_corporate_hard | 5 | pass | - | - |
| segment_enterprise | 3 | pass | - | - |
| segment_enterprise_hard | 5 | pass | - | - |
| segment_smb | 3 | pass | - | - |
| segment_smb_hard | 5 | pass | - | - |
| product_summary | 3 | pass | - | - |
| product_summary_hard | 5 | pass | - | - |
| summary | 3 | pass | - | - |
| summary_hard | 5 | pass | - | - |
| data_quality | 3 | pass | - | - |
| data_quality_hard | 5 | pass | - | - |
| mutation_tier_scale | 5 | pass | - | - |
| mutation_small_commitment | 3 | pass | - | - |
| mutation_near_base_pool | 5 | pass | - | - |
| missing_collector | 3 | pass | - | - |
| control_mismatch | 3 | pass | - | - |
| determinism | 3 | pass | - | - |
| transform_exists | 1 | pass | - | - |
| negative_hardcoded_sample_answers | -5 | not fired | - | - |
| long_1_finishes (lever) | 3 | pass | - | - |
| long_1_normalized (lever) | 5 | pass | - | - |
| long_1_summary (lever) | 5 | pass | - | - |
| long_1_product_summary (lever) | 3 | pass | - | - |
| long_2_finishes (lever) | 3 | pass | - | - |
| long_2_normalized (lever) | 5 | pass | - | - |
| long_2_summary (lever) | 5 | pass | - | - |
| long_2_product_summary (lever) | 3 | pass | - | - |
| long_3_finishes (lever) | 3 | pass | - | - |
| long_3_normalized (lever) | 5 | pass | - | - |
| long_3_summary (lever) | 5 | pass | - | - |
| long_3_product_summary (lever) | 3 | pass | - | - |

## Pair ebaba1c: blind `/tmp/blind/metered-usage-rating-pipeline-20261027T205024-9d66`

**Install map**: `/tmp/blind/metered-usage-rating-pipeline-20261027T205024-9d66/app/transform.py` -> `/app/out/transform.py` (byte-identical to the blind's `out/transform.py`); `/tmp/blind/metered-usage-rating-pipeline-20261027T205024-9d66/out/*` (14 files) -> `/app/out/*`. No other file placed; `/app/data` untouched. No `/tmp/blind`, `/Users/` or `environment/data` path in any delivered file.

**Diff proof**: host `diff -r` of blind `app/` and `out/` vs the staged `solution/blind/` copy: identical. Inside the container after install (solve.sh stdout, `logs/job_ebaba1c/oracle.txt`):
```
INSTALLED:
ee57cf351dcd5b0570da0f05f0be8dcf4b48ad46370ae85ca061fff2523cc7e9  data_quality.json
e3976291d8ba820d482b358a142a7f8ef3d5600b79286ca66f2af9ccf08dad2b  normalized.jsonl
f63d0b00c612dd1a3bdd5007a9f5168c800a82a17e14130ccfa0f3321e417b28  product_summary.json
ffecc8111fa928135b66131a3ea44a90af6f397eb52776b8818945a9229784d2  region_central.json
51c41b203d7241bfded8ea6586686a60a337b0e57b5451175fa432c5bcc68c45  region_east.json
d3bed28aa4b2f34752f25e8d0e36431d7529d2398041c943b7c3deaaddb8702d  region_north.json
7ec9589bd40c2c137294694a7a4c41c0a77a9865c68d80e3b538a4750168bebb  region_south.json
d249d7216e60479f558f0582a4317f81bf538ac525098a8002f81db7b75cef6a  region_west.json
a93f821c4ec7d5027f6dd02d7ece6773aa8fde0cd88c4a1366f443a9616af399  segment_consumer.json
6a9e6c64d25ae70150fb506b6dab8e9a387c761837f52fd23a0c6b5d9629a50d  segment_corporate.json
cde1c32eaa18f0147f0f0adebce3d3014c2d623b9d4f13b9eeab0c4f4f7bba13  segment_enterprise.json
ad1bca90a525ef01c35cb33a11cdd1da1bb1bf89df6fe918c3f2eb740cc31dbc  segment_smb.json
6211cb51cc54981e77b04c240d7debc7ad5a34edc9152ebcd8345362598122d4  summary.json
2247b7a36da94b24312264d19236d4d81d90c6b690f7425fd6da4732834c1ba1  transform.py
DIFF app/transform.py vs /app/out/transform.py:
identical
DIFF -r blind out vs /app/out:
identical
```
Host sha256 of the blind `out/` files (`logs/host_sha_ebaba1c.txt`) matches the INSTALLED list line for line:
```
ee57cf351dcd5b0570da0f05f0be8dcf4b48ad46370ae85ca061fff2523cc7e9  data_quality.json
e3976291d8ba820d482b358a142a7f8ef3d5600b79286ca66f2af9ccf08dad2b  normalized.jsonl
f63d0b00c612dd1a3bdd5007a9f5168c800a82a17e14130ccfa0f3321e417b28  product_summary.json
ffecc8111fa928135b66131a3ea44a90af6f397eb52776b8818945a9229784d2  region_central.json
51c41b203d7241bfded8ea6586686a60a337b0e57b5451175fa432c5bcc68c45  region_east.json
d3bed28aa4b2f34752f25e8d0e36431d7529d2398041c943b7c3deaaddb8702d  region_north.json
7ec9589bd40c2c137294694a7a4c41c0a77a9865c68d80e3b538a4750168bebb  region_south.json
d249d7216e60479f558f0582a4317f81bf538ac525098a8002f81db7b75cef6a  region_west.json
a93f821c4ec7d5027f6dd02d7ece6773aa8fde0cd88c4a1366f443a9616af399  segment_consumer.json
6a9e6c64d25ae70150fb506b6dab8e9a387c761837f52fd23a0c6b5d9629a50d  segment_corporate.json
cde1c32eaa18f0147f0f0adebce3d3014c2d623b9d4f13b9eeab0c4f4f7bba13  segment_enterprise.json
ad1bca90a525ef01c35cb33a11cdd1da1bb1bf89df6fe918c3f2eb740cc31dbc  segment_smb.json
6211cb51cc54981e77b04c240d7debc7ad5a34edc9152ebcd8345362598122d4  summary.json
2247b7a36da94b24312264d19236d4d81d90c6b690f7425fd6da4732834c1ba1  transform.py
```

**Result**: reward 1.0 -> tests% = (295 - 0) / 295 = **100.0%**. Points lost: 0/295 (0.0%) -> loses >= 10% of positive points: **NO**. Lever points lost: 0/48 (0/12 checks). Non-lever checks lost: 0 (0 pts). Negative check fired: no.

**Lever checks**: all 12 pass. Measured long-month times: 2.2 / 2.51 / 2.42 s, all documents exact.

| check | weight | result | failure kind | first assertion line |
|---|---|---|---|---|
| accepted_lines | 3 | pass | - | - |
| accepted_lines_hard | 5 | pass | - | - |
| rating_central | 3 | pass | - | - |
| rating_central_hard | 5 | pass | - | - |
| rating_east | 3 | pass | - | - |
| rating_east_hard | 5 | pass | - | - |
| rating_north | 3 | pass | - | - |
| rating_north_hard | 5 | pass | - | - |
| rating_south | 3 | pass | - | - |
| rating_south_hard | 5 | pass | - | - |
| rating_west | 3 | pass | - | - |
| rating_west_hard | 5 | pass | - | - |
| credit_central | 3 | pass | - | - |
| credit_central_hard | 5 | pass | - | - |
| credit_east | 3 | pass | - | - |
| credit_east_hard | 5 | pass | - | - |
| credit_north | 3 | pass | - | - |
| credit_north_hard | 5 | pass | - | - |
| credit_south | 3 | pass | - | - |
| credit_south_hard | 5 | pass | - | - |
| credit_west | 3 | pass | - | - |
| credit_west_hard | 5 | pass | - | - |
| true_up_central | 3 | pass | - | - |
| true_up_central_hard | 5 | pass | - | - |
| true_up_east | 3 | pass | - | - |
| true_up_east_hard | 5 | pass | - | - |
| true_up_north | 3 | pass | - | - |
| true_up_north_hard | 5 | pass | - | - |
| true_up_south | 3 | pass | - | - |
| true_up_south_hard | 5 | pass | - | - |
| true_up_west | 3 | pass | - | - |
| true_up_west_hard | 5 | pass | - | - |
| region_central | 3 | pass | - | - |
| region_central_hard | 5 | pass | - | - |
| region_east | 3 | pass | - | - |
| region_east_hard | 5 | pass | - | - |
| region_north | 3 | pass | - | - |
| region_north_hard | 5 | pass | - | - |
| region_south | 3 | pass | - | - |
| region_south_hard | 5 | pass | - | - |
| region_west | 3 | pass | - | - |
| region_west_hard | 5 | pass | - | - |
| segment_consumer | 3 | pass | - | - |
| segment_consumer_hard | 5 | pass | - | - |
| segment_corporate | 3 | pass | - | - |
| segment_corporate_hard | 5 | pass | - | - |
| segment_enterprise | 3 | pass | - | - |
| segment_enterprise_hard | 5 | pass | - | - |
| segment_smb | 3 | pass | - | - |
| segment_smb_hard | 5 | pass | - | - |
| product_summary | 3 | pass | - | - |
| product_summary_hard | 5 | pass | - | - |
| summary | 3 | pass | - | - |
| summary_hard | 5 | pass | - | - |
| data_quality | 3 | pass | - | - |
| data_quality_hard | 5 | pass | - | - |
| mutation_tier_scale | 5 | pass | - | - |
| mutation_small_commitment | 3 | pass | - | - |
| mutation_near_base_pool | 5 | pass | - | - |
| missing_collector | 3 | pass | - | - |
| control_mismatch | 3 | pass | - | - |
| determinism | 3 | pass | - | - |
| transform_exists | 1 | pass | - | - |
| negative_hardcoded_sample_answers | -5 | not fired | - | - |
| long_1_finishes (lever) | 3 | pass | - | - |
| long_1_normalized (lever) | 5 | pass | - | - |
| long_1_summary (lever) | 5 | pass | - | - |
| long_1_product_summary (lever) | 3 | pass | - | - |
| long_2_finishes (lever) | 3 | pass | - | - |
| long_2_normalized (lever) | 5 | pass | - | - |
| long_2_summary (lever) | 5 | pass | - | - |
| long_2_product_summary (lever) | 3 | pass | - | - |
| long_3_finishes (lever) | 3 | pass | - | - |
| long_3_normalized (lever) | 5 | pass | - | - |
| long_3_summary (lever) | 5 | pass | - | - |
| long_3_product_summary (lever) | 3 | pass | - | - |

## Summary
| blind | tests% | lever lost | loss kind | measured long s (1/2/3) | non-lever lost | >=10% lost |
|---|---|---|---|---|---|---|
| 6f5046a | 83.73 | 48.0/48 | TIMEOUT | 83.04 / 112.32 / 133.62 | 0 | YES |
| 204228e | 100.0 | 0/48 | none | 2.21 / 2.9 / 2.36 | 0 | NO |
| ebaba1c | 100.0 | 0/48 | none | 2.2 / 2.51 / 2.42 | 0 | NO |

Only 6f5046a loses the lever (16.3%, TIMEOUT only, exact documents at 83-134 s); 204228e and ebaba1c finish every long month in under 3 s with exact documents and score 100% of the test channel, so the lever kills 1 of 3 blinds.

## Cleanup
Copies under `/tmp/score_d07903b/` removed after this report; logs kept in `logs/`. No bundle, blind folder, Tasks_INPUT, harness or kit file was edited.
