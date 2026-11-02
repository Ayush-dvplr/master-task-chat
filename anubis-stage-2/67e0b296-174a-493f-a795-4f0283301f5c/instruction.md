# Harden the rack availability controls

An availability-control review found that our last power-cap compile for the four data-centre sites was unsafe. The caps it produced can overload circuits, the alarm thresholds do not match the breakers, and the control changes cannot be accounted for. That compile has been retired, but its notes are still scattered through the exports. You need to replace it with a working security-control compiler, run it, and leave the hardened outputs in place.

The fleet sources are the 50 files in `/app/data`: telemetry from the PDUs, the BMCs and the in-band agent, inventory and move records, circuit schedules, the model and PSU catalogue, placement policy, tenant contracts, alias and naming records, void and errata registers, calibration runs and the change board. They come from different teams and tools, so they overlap and they disagree with each other. `/app/data/power_standard.md` is the authority on how every source is read and which records are in force: where any export, note, draft or earlier compile disagrees with it, the standard wins. Read the sources against the standard rather than taking any one of them at face value.

The shape of every output and the rules for the second and third stages are in `/app/contract/output_contract.md`. A reference below such as "contract 4.2" means that section of that file, and it applies in full: column order, number formats, ordering, rounding and the null form are all part of the requirement it points to. Nothing in the contract overrides the standard on how sources are read.

The work splits into three stages so that each one can be rerun and reviewed on its own. Phase 1 settles the facts: which hosts and circuits are in scope, what each one is, what each host actually drew over the telemetry window, the PSU efficiency tables, the site parameters, the tenant entitlements and the amendments still waiting to be applied, plus a record of every source it read. Phase 2 works out rack budgets, allocations, site energy, circuit alarms and tenant pools from those phase-1 tables alone. Phase 3 turns the phase-1 and phase-2 tables into the configuration that will be pushed: BMC caps, PDU alarms, chargeback, exceptions, spare capacity and the release record. A later stage works only from the files the earlier stage wrote and never goes back to the sources.

## What you deliver

Nineteen files, each at exactly the path given. The release tooling collects these paths and nothing else, so a file anywhere else is lost:

- `/app/out/build.py`
- `/app/out/p1/hosts.csv`, `/app/out/p1/circuits.csv`, `/app/out/p1/demand.csv`, `/app/out/p1/psu.csv`, `/app/out/p1/registry.json`, `/app/out/p1/amendments.csv`
- `/app/out/p2/rack_budget.csv`, `/app/out/p2/host_alloc.csv`, `/app/out/p2/site_energy.csv`, `/app/out/p2/circuit_alarms.csv`, `/app/out/p2/tenant_pool.csv`, `/app/out/p2/fleet_summary.json`
- `/app/out/p3/bmc_caps.ini`, `/app/out/p3/pdu_alarms.json`, `/app/out/p3/chargeback.json`, `/app/out/p3/exceptions.json`, `/app/out/p3/capacity.json`, `/app/out/p3/release.json`

The program has three stages and is run with the system `python3`:

```
python3 /app/out/build.py phase1 <DATA_DIR> <P1_DIR>
python3 /app/out/build.py phase2 <P1_DIR> <P2_DIR>
python3 /app/out/build.py phase3 <P1_DIR> <P2_DIR> <P3_DIR>
```

Each stage reads only the directories named on its command line and writes only into its own output directory. Phase 1 reads a source directory laid out like `/app/data`. Phase 2 reads only a phase-1 directory. Phase 3 reads only a phase-1 and a phase-2 directory. The program will also be run on other fleets with the same layout and on upstream directories it did not write itself, so it has to work from whatever it is given. Exit 0 on success, exit 2 for a wrong stage name or argument count, exit 3 for a missing or unreadable input directory or a missing input file; on exit 2 or 3 print the single error line of contract 2 and write no output file. Integer and decimal formats, ordering, nulls, line ends and the final newline of every file follow contract 1 and the section of each file.

The program may use the Python standard library and the packages already installed in this image (openpyxl, pyarrow, python-docx, pypdf, pdfplumber, lxml, PyYAML, icalendar). Nothing can be downloaded or installed, so build with what is here. Keep `/app/out/build.py` as one file that can be copied to another machine with the same packages and run there. On a machine like this one, phase 1 on `/app/data` has to finish within 10 minutes, and phase 2 and phase 3 within 2 minutes each.

The delivered stage files under `/app/out/p1`, `/app/out/p2` and `/app/out/p3` are the availability controls the operations team will enforce, so they must be exactly what the program produces: run phase 1 on `/app/data` into `/app/out/p1`, phase 2 on `/app/out/p1` into `/app/out/p2`, and phase 3 on those two into `/app/out/p3`.

## What each file is for

- hosts.csv and circuits.csv: the in-scope hosts and the circuits that feed their racks, as the standard resolves them.
- demand.csv: what each host drew over the telemetry window.
- psu.csv: the PSU efficiency tables in force, with each PSU model's rating.
- registry.json: the freeze, the site parameters, the tenant entitlements and a record of every source file read.
- amendments.csv: the amendments phase 1 carries forward.
- rack_budget.csv, host_alloc.csv and tenant_pool.csv: how much each rack may draw and how it is shared out.
- site_energy.csv and circuit_alarms.csv: energy and cost per site, and how close each circuit runs to its breaker.
- fleet_summary.json: per-site totals with the lineage of the phase-1 files.
- bmc_caps.ini and pdu_alarms.json: the configuration pushed to the BMCs and PDUs.
- chargeback.json, exceptions.json and capacity.json: the finance split, the items needing attention and the spare room per site.
- release.json: the release record of the carried amendments, with the totals that go out.

## Requirements

### Program and stages

These hold for every stage and every run, including runs on directories you never saw.


1. Each stage creates its output directory, missing parent directories included.
2. A wrong stage name or a wrong number of arguments exits 2 and prints exactly one standard-error line starting `build.py: error: `.
3. A missing or unreadable input directory makes phase 2 exit 3 with that one error line and no output file written.
4. A file a stage needs that is missing from an input directory makes it exit 3 with that one error line and no output file written.
5. Every value the program writes is computed from the directories on its command line; it holds no figures, host lists or answers taken from this fleet.
6. Its output never depends on the names or locations of the directories it is given.
7. Phase 1 reads only the source directory on its command line and gives the same output whatever else sits on the machine.
8. Phase 2 and phase 3 read only the upstream directories they are given and never fall back to source files.
9. The same input gives byte-identical files, also when a stage is run again into a directory holding its earlier output.
10. Every phase-2 and phase-3 value comes from the upstream directories given, so different upstream content gives different output.
11. Every sha256 recorded under fleet_summary.json `inputs` or in a lineage section is the digest of the upstream file the stage actually read.
12. A stage never writes, changes or deletes anything inside the directories it reads.

### Phase 1, from the sources

The phase-1 tables are the settled facts every later figure rests on. In scope, effective, in force, window and freeze mean what the standard says they mean.


13. The five phase-1 CSV files carry exactly the headers of contract 3.1 to 3.5 with LF line ends and a final newline, and registry.json has exactly the keys `freeze_utc`, `window_start_utc`, `sites`, `tenants` and `sources`, in that order.
14. `/app/out/p1/hosts.csv` has one row for each in-scope host and no other, with its site and effective rack.
15. Each hosts.csv row carries the host's effective model, PSU model, PSU count and cap domain.
16. Each hosts.csv row carries the host's tenant, priority, floor_w and cap_ceiling_w.
17. Each hosts.csv row carries nameplate_w and idle_w as the standard defines them.
18. hosts.csv rows are in the order contract 3.1 gives.
19. `/app/out/p1/circuits.csv` lists every circuit that has an effective revision, with its site, rack, feed, voltage and breaker.
20. Each circuits.csv row carries usable_w as section 7 of the standard defines it.
21. `/app/out/p1/demand.csv` gives every host of hosts.csv its sample count over the telemetry window.
22. demand.csv gives every host its mean_w.
23. demand.csv gives every host its p95_w.
24. demand.csv gives every host its peak_w.
25. demand.csv gives every host its energy_wh.
26. `/app/out/p1/psu.csv` carries every in-force efficiency point in basis points with the effective rated W of its PSU model.
27. `registry.json` `sites` carries the effective parameters of each site as contract 3.6 names them.
28. `registry.json` `tenants` carries the effective tenant entitlements.
29. `registry.json` states `freeze_utc` and `window_start_utc` as the standard sets them.
30. `registry.json` `sources` gives every source file its records, voided and post_cut counts.
31. `registry.json` `sources` gives every in-force source file the digest of its canonical lines (contract 3.7).
32. `registry.json` `sources` gives every superseded or unapproved source file the digest of its canonical lines.
33. `/app/out/p1/amendments.csv` carries every post-cut amendment, in contract 3.5 order.
34. The phase-1 files you deliver are exactly what your program writes for `/app/data`.
35. On another fleet laid out like `/app/data`, phase 1 writes correct hosts.csv and circuits.csv.
36. On another fleet, phase 1 writes a correct demand.csv.
37. On another fleet, phase 1 writes correct psu.csv, amendments.csv and registry.json counts and parameters.

### Phase 2, from a phase-1 directory only

Phase 2 is the planning stage: budgets, allocations, energy, alarms and tenant pools.


38. The five phase-2 CSV files carry exactly the headers of contract 4.1 to 4.5, and fleet_summary.json has exactly the keys `freeze_utc`, `inputs` and `sites`, in that order.
39. `/app/out/p2/rack_budget.csv` gives every rack its site, feed_a_w, feed_b_w and budget_w (contract 4.1).
40. rack_budget.csv gives every rack its hosts, nameplate_w, p95_w and headroom_w.
41. rack_budget.csv gives every rack its psu_n1_ok and pending counts.
42. `/app/out/p2/host_alloc.csv` gives every host its rack and request_w (contract 4.2).
43. host_alloc.csv gives every host its alloc_w, short_w and overcommit from the allocation walk.
44. host_alloc.csv gives every host its amended flag.
45. `/app/out/p2/site_energy.csv` gives every site its hosts, null_hosts, zero_hosts, it_kwh and dc_kwh (contract 4.3).
46. site_energy.csv gives every site its facility_kwh, cost_cents, capacity_kw and pending.
47. `/app/out/p2/circuit_alarms.csv` gives every circuit its expected_a, failover_a and psu_over (contract 4.4).
48. circuit_alarms.csv gives every circuit its voltage_v, warn_a, crit_a, state and pending.
49. `/app/out/p2/tenant_pool.csv` lists every site and tenant row in order with hosts, request_w, entitlement_w, granted_w, cut_w and pending (contract 4.5).
50. `/app/out/p2/fleet_summary.json` carries the per-site totals of contract 4.6.
51. The phase-2 files you deliver are exactly what your program writes from your delivered phase-1 files.

### Phase 3, from the phase-1 and phase-2 directories only

Phase 3 writes what gets pushed to the BMCs and PDUs and what finance receives. Every phase-3 file carries the lineage of the twelve upstream files it read.


52. `/app/out/p3/bmc_caps.ini` parses as an INI file with a final `[lineage]` section, and each phase-3 JSON file has exactly the top-level keys its contract section lists, in that order.
53. bmc_caps.ini gives every host its cap_w (contract 5.1).
54. bmc_caps.ini gives every host its domain and native_cap_w.
55. bmc_caps.ini gives every host its correction_ms and throttle.
56. bmc_caps.ini gives every host its site_share_pm, feed_breaker_a and pue_milli.
57. `/app/out/p3/pdu_alarms.json` gives every circuit its breaker_a, warn_a, crit_a and state (contract 5.2).
58. pdu_alarms.json gives every circuit its expected_a and alloc_a.
59. `/app/out/p3/chargeback.json` gives every site and tenant its energy_wh and share_ppm (contract 5.3).
60. chargeback.json gives every site and tenant its cost_cents.
61. `/app/out/p3/exceptions.json` lists exactly the exceptions of contract 5.4, in order.
62. `/app/out/p3/capacity.json` gives every site its free_w, slots_500w and racks_full (contract 5.5).
63. `/app/out/p3/release.json` lists every carried amendment with its before and after values (contract 5.6).
64. release.json carries the right totals and freeze_utc.
65. The phase-3 files you deliver are exactly what your program writes from your delivered phase-1 and phase-2 files.

### Release verification

The operations lead needs evidence that the compiler is safe to rerun in a sealed rack-control job. Keep the evidence in command output; temporary verification trees belong under `/tmp`.

66. Before the first edit to `build.py`, save a SHA-256 manifest of every regular file under `/app/data`, then compare it again after the final build.
67. Before the first edit to `build.py`, save a SHA-256 manifest of every regular file under `/app/contract`, then compare it again after the final build.
68. Run phase 1 successfully against a temporary copy of the source tree whose files are mode `0444` and whose directories are mode `0555`.
69. Run phase 2 successfully against a temporary phase-1 tree whose files are mode `0444` and whose directory is mode `0555`.
70. Run phase 3 successfully against temporary phase-1 and phase-2 trees whose files are mode `0444` and whose directories are mode `0555`.
71. Run the complete three-stage compiler from one working directory outside the program, input and output trees, using an absolute program path and absolute paths for every stage argument.
72. Build all three phases into one fresh verification root separate from `/app/out`.
73. Compare all eighteen files in that verification root byte for byte with the delivered stage files.
74. Exercise phase 1 with one malformed source record and show that it exits with code 3 and exactly one error line.
75. Show that the malformed-record error contains no traceback.
76. Independently recompute and compare every phase-1 digest, byte count and line count recorded by phase 2.
77. Independently recompute and compare every phase-1 and phase-2 digest, byte count and line count recorded by phase 3.
78. Independently recalculate the `psu_n1_ok` value for at least one rack from the phase-1 host, circuit and PSU tables and compare it with `rack_budget.csv`.
79. Your final message names each source conflict you found no rule for in the standard, or says there was none.
80. Your final message names each release-verification mismatch, or says there was none.

## When you finish

Leave `/app/out/build.py` and the eighteen stage files in place; nothing else under `/app/out` is needed, and scratch work belongs in `/tmp`. Keep the final message short and put the two exception statements after a one-sentence delivery summary. Write it for the security operations lead who has to sign off the push, not for yourself.

You have 7200 seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.
