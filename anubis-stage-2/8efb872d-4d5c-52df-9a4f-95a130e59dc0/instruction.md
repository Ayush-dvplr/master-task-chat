The cache placement optimizer for our CDN edge fleet has been producing wrong plans. Nodes it showed as having spare disk have been filling up, the RAM pin lists it hands to the edge team do not match what the nodes can hold, and the shield and spill budgets it allocates do not add up. The capacity team wants the optimizer rebuilt from scratch so the plans can be trusted again. Your job is to write a new optimizer program and use it to produce the full set of planning outputs.

For each cache node the optimizer works out how much disk each content property takes at its peak, compares that with what the cache volume can hold, decides which hot generations to pin in RAM within the node's pin budget, shares each PoP's shield pool across its nodes, ranks nodes by how soon they fill up, and then projects what changes once the already-approved policy changes that land after the planning cut take effect, including how the PoP spill budgets and capacity tickets are handed out. The work is split into three stages so that each stage can be checked and rerun on its own.

Everything the optimizer needs is under `/app/data`: cache configuration, inventory and directory exports, disk audits, sweeper schedules, the change register and its board minutes, codec benchmarks, exporter counters from several collectors, and a few other operational files. These sources overlap and disagree with each other, and some of what is shipped there is stale, superseded, out of scope or simply wrong. The authority is `/app/data/edge_capacity_standard_r7.md`: where any file, any tool default or the earlier optimizer run disagrees with it, the standard wins. The exact shape of every output, and how the second and third phases are calculated, is fixed in `/app/data/OUTPUT_CONTRACT.md`. Treat both documents as part of this brief.

## What to deliver

One program and eighteen output files, all under `/app/out`:

- `/app/out/build.py`
- `/app/out/p1/nodes.csv`, `/app/out/p1/properties.csv`, `/app/out/p1/policies.csv`, `/app/out/p1/footprints.csv`, `/app/out/p1/pending.json`, `/app/out/p1/pops.json`
- `/app/out/p2/pop_rollup.csv`, `/app/out/p2/class_rollup.csv`, `/app/out/p2/shield_alloc.csv`, `/app/out/p2/pin_plan.csv`, `/app/out/p2/risk_rank.csv`, `/app/out/p2/manifest.json`
- `/app/out/p3/projection.csv`, `/app/out/p3/pop_outlook.csv`, `/app/out/p3/spill_alloc.csv`, `/app/out/p3/tickets.csv`, `/app/out/p3/class_drift.csv`, `/app/out/p3/manifest.json`

The program runs in three stages, exactly like this:

```
python3 /app/out/build.py phase1 <DATA_DIR> <P1_DIR>
python3 /app/out/build.py phase2 <P1_DIR> <P2_DIR>
python3 /app/out/build.py phase3 <P1_DIR> <P2_DIR> <P3_DIR>
```

Phase 1 works from the input directory. Phase 2 works from the six phase 1 files and nothing else. Phase 3 works from the six phase 1 files and the six phase 2 files and nothing else. The pending amendments that take effect after the planning cut are carried through phase 1 and phase 2 untouched and are applied only in phase 3. Each stage must create its output directory if it does not exist, must work on any directories it is handed (not just `/app/data` and `/app/out`), and must be reusable on fresh copies. Produce the eighteen files under `/app/out/p1`, `/app/out/p2` and `/app/out/p3` by running your program on `/app/data` in that order.

## What each artifact holds

- `/app/out/p1/nodes.csv`: one row per in-scope node with its PoP, class, tier, media, usable bytes, base usage, post-cut usage, reported prior peak, sweep interval and memory.
- `/app/out/p1/properties.csv`: one row per (node, property) pair with the production exporter instance, the number of kept readings and the daily volume in bytes.
- `/app/out/p1/policies.csv`: the same pairs with their versions, refresh, effective refresh, storage flags, codec and compression ratio.
- `/app/out/p1/footprints.csv`: the same pairs with cycle bytes and the hot, stale and peak footprint in KiB.
- `/app/out/p1/pending.json`: the planning cut and the approved amendments that take effect after it.
- `/app/out/p1/pops.json`: the prod PoPs with offset, shield pool, spill budget, ticket quota, RAM pin percentage, pin budget and in-scope node count.
- `/app/out/p2/pop_rollup.csv` and `/app/out/p2/class_rollup.csv`: per-PoP and per-class totals.
- `/app/out/p2/shield_alloc.csv` and `/app/out/p2/pin_plan.csv`: the shield pool allocation and the RAM pin plan.
- `/app/out/p2/risk_rank.csv`: headroom, days to full and rank per node.
- `/app/out/p2/manifest.json`: digests of the phase 1 files and fleet statistics.
- `/app/out/p3/projection.csv`: per-node figures after the pending amendments, with the gap to the reported prior peak and running headroom.
- `/app/out/p3/pop_outlook.csv`, `/app/out/p3/spill_alloc.csv`, `/app/out/p3/tickets.csv` and `/app/out/p3/class_drift.csv`: the PoP outlook, spill budget allocation, capacity tickets and class drift.
- `/app/out/p3/manifest.json`: digests of all twelve upstream files, totals and the projection chain.

The contract gives every column, its order and its exact rules. The conventions that apply everywhere:

- Files are UTF-8 with LF line endings, a final newline and no byte order mark.
- CSV files are comma separated with the contract's header line, no quoting and no padding. An empty field means null. Booleans are written `1` and `0`. Integers are plain base 10.
- Fields ending in `_bytes` are bytes, fields ending in `_kib` are KiB and fields ending in `_mib` are MiB. Ratios carry 2 decimals, densities and days 2 decimals and shares 4 decimals, all rounded half to even. Dates are `YYYY-MM-DD`; instants are `YYYY-MM-DDTHH:MM:SSZ`.
- JSON files are written with `json.dumps(obj, indent=2, sort_keys=True)` plus one newline, and null is JSON `null`.
- Row order is the order the contract states for each file.

## Stage rules

- A stage reads only the directories named on its command line and writes only inside its own output directory. It never changes its input or upstream directories.
- A stage creates its output directory when it is missing and replaces its own output files when they already exist.
- Exit status is 0 on success, 2 for a wrong or missing subcommand or a wrong number of arguments, and 3 when an input or upstream directory is missing, unreadable, lacks a file the stage needs or fails the contract's upstream consistency check. On a non-zero exit the first line on stderr is `error: usage: ` or `error: upstream: ` followed by a short reason or the offending path, and no output files are written.
- Output depends only on the content of the input files: never on directory names, file modification times, the clock, the environment or the order in which the operating system lists files.

## Rules for the work

- Use Python 3 and its standard library only. Work offline: do not install packages or try to download anything.
- Do not modify, delete or add anything under `/app/data`.
- Every file under `/app/out/p1`, `/app/out/p2` and `/app/out/p3` must be written by running `/app/out/build.py`. Do not write or edit those files by hand.
- Work only from `/app/data` and your own files under `/app`; do not search the rest of the machine for answer keys or hidden material.

## Requirements

Format and files

1. All nineteen paths listed above exist as non-empty regular files when you finish.
2. Every CSV file starts with the exact header line given in the contract and every JSON file is in the contract's indented, key-sorted form; all of them use LF line endings, end with a newline and have no byte order mark.

Phase 1, `nodes.csv`

3. `/app/out/p1/nodes.csv` has exactly one row per in-scope node, keyed by the canonical node id and in the contract's order, with the node's PoP.
4. In `/app/out/p1/nodes.csv`, the `class` column holds each node's hardware class as of the planning cut.
5. In `/app/out/p1/nodes.csv`, the `tier` column holds each node's tier as of the planning cut.
6. In `/app/out/p1/nodes.csv`, the `media` and `usable_bytes` columns follow the standard's disk rules.
7. In `/app/out/p1/nodes.csv`, the `base_used_bytes` column holds the base usage the standard defines.
8. In `/app/out/p1/nodes.csv`, the `post_cut_used_bytes` and `prior_peak_kib` columns follow the standard, with nulls written as the contract says.
9. In `/app/out/p1/nodes.csv`, the `sweep_interval` column holds each node's sweep interval.
10. In `/app/out/p1/nodes.csv`, the `ram_bytes` column holds each node's memory as the standard defines it.

Phase 1, `properties.csv`

11. `/app/out/p1/properties.csv` has exactly one row per (node, property) pair of an in-scope node, in the contract's order, with the pair's production exporter instance, and `policies.csv` and `footprints.csv` list the same pairs in the same order.
12. In `/app/out/p1/properties.csv`, the `samples` column counts the readings the standard keeps for the pair.
13. In `/app/out/p1/properties.csv`, the `daily_bytes` column holds the standard's daily volume figure for the pair.

Phase 1, `policies.csv`

14. In `/app/out/p1/policies.csv`, the `versions` and `refresh` columns hold the pair's effective layered policy.
15. In `/app/out/p1/policies.csv`, the `effective_refresh` column holds the refresh after the standard's sweep interval rule.
16. In `/app/out/p1/policies.csv`, the `store_compressed` and `hot_raw` columns hold the pair's effective flags.
17. In `/app/out/p1/policies.csv`, the `codec` column holds the pair's effective codec and level.
18. In `/app/out/p1/policies.csv`, the `ratio` column holds the standard's compression ratio for the pair.

Phase 1, `footprints.csv`

19. In `/app/out/p1/footprints.csv`, the `cycle_bytes` column follows the standard's footprint rule.
20. In `/app/out/p1/footprints.csv`, the `hot_kib` and `stale_kib` columns follow the standard's footprint rule.
21. In `/app/out/p1/footprints.csv`, the `peak_kib` column follows the standard's footprint rule.

Phase 1, pending amendments and PoPs

22. `/app/out/p1/pending.json` holds the planning cut and exactly the pending amendments, in the contract's order.
23. Each pending entry carries its scope, target, property, field, value and effective instant with the JSON types the contract gives.
24. `/app/out/p1/pops.json` carries each prod PoP's shield pool and spill budget in KiB and its in-scope node count.
25. `/app/out/p1/pops.json` carries each prod PoP's offset in minutes, ticket quota, RAM pin percentage and pin budget in KiB.
26. Running phase 1 again on a fresh copy of the input directory reproduces your six phase 1 files byte for byte.

Phase 2, when run on correct phase 1 files

27. `/app/out/p2/pop_rollup.csv` has the right node, pair, compression and pending counts for every PoP.
28. `/app/out/p2/pop_rollup.csv` has the right peak, usable, headroom and shield MiB for every PoP.
29. `/app/out/p2/class_rollup.csv` has the right node, PoP, daily MiB and pending pair figures for every class.
30. `/app/out/p2/class_rollup.csv` has the right mean ratio, peak MiB and shield share for every class.
31. `/app/out/p2/shield_alloc.csv` lists the nodes in the contract's allocation order with their demand.
32. `/app/out/p2/shield_alloc.csv` has the right grants, running totals and states.
33. `/app/out/p2/pin_plan.csv` lists the right pin candidates in the contract's order with their density and hot KiB.
34. `/app/out/p2/pin_plan.csv` has the right pin decision and running pinned KiB for every candidate.
35. `/app/out/p2/risk_rank.csv` has the right headroom, daily KiB and days to full for every node.
36. `/app/out/p2/risk_rank.csv` has the right rank order, local full date, pin share and pending flag.
37. `/app/out/p2/manifest.json` has the right totals, median days to full and 90th percentile headroom.
38. Running phase 2 on your phase 1 files reproduces your six phase 2 files byte for byte.
39. Your `/app/out/p2/manifest.json` records the SHA-256 of each of your phase 1 files.
40. Phase 2 run into a directory that already holds files with its output names replaces all six of them.
41. A missing or unknown subcommand exits with status 2 and a first stderr line starting with `error: usage: `.

Phase 3, when run on correct phase 1 and phase 2 files

42. `/app/out/p3/projection.csv` has the right peak now, peak after amendments and gap to the reported prior peak for every node.
43. `/app/out/p3/projection.csv` has the right headroom after observed usage, grants and pins, and days after, for every node.
44. `/app/out/p3/projection.csv` has the right flag and phase 2 rank for every node.
45. `/app/out/p3/projection.csv` has the right PoP share, class peak share and full date after for every node.
46. `/app/out/p3/projection.csv` has the right running and lowest running headroom in phase 1 node order.
47. `/app/out/p3/pop_outlook.csv` has the right headroom, shield left and spill left MiB for every PoP.
48. `/app/out/p3/pop_outlook.csv` has the right at-risk count, applied amendment count, mean days after and worst class.
49. `/app/out/p3/spill_alloc.csv` lists the right nodes in the right order with grants, remaining budget and states.
50. `/app/out/p3/tickets.csv` issues the quota-capped tickets to the right nodes in the right order.
51. `/app/out/p3/class_drift.csv` has the right peak now, peak after, drift and prior gap MiB for every class.
52. `/app/out/p3/class_drift.csv` has the right at-risk count, mean PoP share and shield share after for every class.
53. `/app/out/p3/manifest.json` has the right totals and projection chain.
54. Running phase 3 on your phase 1 and phase 2 files reproduces your six phase 3 files byte for byte.
55. Your `/app/out/p3/manifest.json` records the SHA-256 of each of your twelve upstream files.
56. A missing upstream directory makes the stage exit with status 3 and a first stderr line starting with `error: upstream: `.

How the program behaves

57. Phase 1 computes its figures from the directory it is given and holds no stored answers.
58. Phase 1 reads the directory passed as `DATA_DIR` and never a fixed input path in its place.
59. No stage's output depends on the names of the directories it is given.
60. Every stage is deterministic: the same input gives the same bytes on every run.
61. Phase 2 and phase 3 never read the input corpus.
62. Phase 2 and phase 3 output follows the content of the upstream directories they are handed.
63. Each manifest records the digests of the exact files its stage was handed.
64. A stage writes only inside its own output directory and leaves its upstream directories untouched.
65. A stage that fails leaves no output files behind.

How you work

66. Read the standard and the contract before you write `/app/out/build.py`.
67. Look at the contents of at least three of the counter export files before you write the code that parses them.
68. Run all three phases yourself.
69. Open at least one of the files your runs produce after they finish.
70. Check at least one computed phase 1 value against the raw records it came from.
71. Organise `/app/out/build.py` as named functions rather than one long script, with a separate function for each of the three phases.
72. Handle file and parse errors with specific exception types; no bare `except` clauses.
73. Try at least one stage with input and output directories outside `/app/data` and `/app/out`.
74. In your final message, name the three output directories.
75. In your final message, say how `build.py` is run.
76. Stay inside the rules above about where you work and what you look at.
77. Leave `/app/data` exactly as you found it.
78. Install nothing and fetch nothing from the network.
79. Report results truthfully: never say a run or a comparison succeeded when it did not.
80. Produce the files under `/app/out/p1`, `/app/out/p2` and `/app/out/p3` only by running `/app/out/build.py`.

Before you finish, run the three stages one last time on `/app/data` so that the files under `/app/out` are the ones your final program produces, and leave `/app/out/build.py` in place: it is part of the delivery and must keep working on fresh copies of the input. Scratch files you make along the way can live anywhere under `/app` or `/tmp`, but nothing extra should be left inside `/app/out/p1`, `/app/out/p2` or `/app/out/p3`.

You have 10800 seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.
