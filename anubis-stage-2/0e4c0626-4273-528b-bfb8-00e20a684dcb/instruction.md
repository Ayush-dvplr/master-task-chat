Platform finance is closing October 2025 for the Kestrel monorepo CI fleets and needs the build-minute chargeback settled from the exports the fleets, the cache, the artifact store, the vendor and the ledger left behind. Everything you need is under `/app/data`: logs, registries, spreadsheets, databases, calendars, mail and the written policy documents. The sources overlap and disagree. Some of them are mirrors, drafts or working copies, some exported values are wrong or superseded by design, and several exports write the same kind of value in different conventions. The documents in `/app/data` define authority, scope, amendment, precedence and the conventions in force, and those written rules decide every conflict. `/app/data/settlement_authority.md` is the place to start.

## Deliverables

Write a reusable program and run it on `/app/data` so that these files exist:

- `/app/out/settle.py`: the program that produces every artifact below.
- `/app/out/attempts.jsonl`: one row per CI attempt with its settlement.
- `/app/out/lookups.jsonl`: one row per cache lookup with its outcome.
- `/app/out/targets.jsonl`: one row per build target with resolution, invalidation and ownership.
- `/app/out/actions.jsonl`: one row per cached action with hermeticity.
- `/app/out/artifacts.jsonl`: one row per stored artifact with its storage charge.
- `/app/out/invoice_reconciliation.jsonl`: one row per vendor invoice line with its reconciliation.
- `/app/out/team_chargeback.json`: charges per team.
- `/app/out/cost_center_ledger.json`: the ledger roll-forward per cost center.
- `/app/out/rate_resolution.json`: the rate windows in force per instance class and region.
- `/app/out/cache_effectiveness.json`: cache outcome counts per team.
- `/app/out/control_reconciliation.json`: every published block control with your recomputed figures.
- `/app/out/source_audit.json`: distinct record counts per input file.
- `/app/out/close_summary.json`: the close totals.

## Format

Every `.jsonl` artifact holds one compact JSON object per line. Money is an integer number of micro-dollars, durations are integer milliseconds unless the field name says seconds, instants are strings of the form `2025-10-03T04:05:06Z`, and a missing value is JSON `null`. Values are compared exactly at these units, including JSON types; key order inside an object does not matter.

## attempts.jsonl (row key `attempt_id`)

Each row has exactly the keys `attempt_id`, `job_id`, `attempt_no`, `fleet`, `runner`, `runner_rev`, `region`, `sku`, `instance_class`, `target`, `started_at`, `duration_ms`, `status`, `exclusion`, `billable_seconds`, `rate_micro_per_min`, `billing_class`, `reserved`, `cost_micro`, `owner_handle`, `team`, `cost_center`, and covers every attempt of the four fleets, including attempts outside the period.

1. `started_at` is the corrected start instant of the attempt.
2. `duration_ms` is the attempt duration as the documents define it.
3. `runner_rev`, `region`, `sku` and `instance_class` describe the runner revision in force at the corrected start.
4. `status` is the final status after errata that took effect.
5. `exclusion` is the documented exclusion reason that applies, or `null` for a billable attempt.
6. `billable_seconds` is the integer billable seconds, `0` for an excluded attempt.
7. `rate_micro_per_min` is the integer rate applicable to the attempt.
8. `billing_class` is the class the attempt bills under and `reserved` is a boolean telling whether a reservation applies.
9. `cost_micro` is the integer cost, `0` for an excluded attempt.
10. `owner_handle` is the handle charged for the attempt and `team` is that handle's team at the corrected start.
11. `cost_center` is the cost center charged at the corrected start.

## lookups.jsonl (row key `lookup_id`)

Keys: `lookup_id`, `attempt_id`, `action_key`, `shard`, `at`, `bytes`, `outcome`, `eviction_id`, one row per lookup in the three shard logs.

12. `outcome` is one of `hit`, `miss`, `stale_hit`, `evicted_hit`, `nonhermetic_hit`, `replay` under the cache rules.
13. `eviction_id` names the qualifying eviction for an `evicted_hit` and is `null` otherwise.

## targets.jsonl (row key `target`)

Keys: `target`, `kind`, `language`, `toolchain`, `constraint`, `version_at_open`, `version_at_close`, `invalidated`, `scope`, `owner_handle`, `team`.

14. `version_at_open` and `version_at_close` are the resolved toolchain versions at the period start and at its last second, `null` when nothing resolves.
15. `invalidated` is the boolean invalidation verdict for the target.
16. `owner_handle` is the owner from the ownership registry, `null` for an unowned target, and `team` is that owner's team at the period's last second.

## actions.jsonl (row key `action_key`)

Keys: `action_key`, `target`, `home_shard`, `hermetic`, `undeclared_inputs`, `input_bytes`, `disallowed_env`, `toolchain_version`.

17. `hermetic` is the boolean verdict, `undeclared_inputs` lists the undeclared input paths and `disallowed_env` lists the variables outside the allowed list, both sorted.
18. `toolchain_version` is the version named by the action's toolchain digest, or `null`.

## artifacts.jsonl (row key `artifact_id`)

Keys: `artifact_id`, `target`, `bytes`, `retained_seconds`, `storage_cost_micro`, `team`, `cost_center`.

19. `retained_seconds` counts retention inside the period only.
20. `storage_cost_micro` is the integer storage charge of the artifact.

## invoice_reconciliation.jsonl (row key `line_id`)

Keys: `line_id`, `runner`, `week`, `billed_micro`, `credit_micro`, `computed_micro`, `status`, where `week` is the 0-based position of the line's week in the period.

21. `status` is one of `closed`, `match`, `credited`, `mismatch` under the invoice rules.
22. `computed_micro` is the cost of the billable attempts the line covers.

## cost_center_ledger.json

An object keyed by cost center, each value with `opening_micro`, `postings_micro`, `charges_micro`, `closing_micro`, covering every cost center with an opening balance.

23. `postings_micro` sums only the postings that count for the period.
24. `closing_micro` is the closing balance of the cost center.

## Other aggregates

25. `rate_resolution.json` maps `"<instance_class>|<region>"` for every class and region in the rate card to a list of `[effective_instant, micro_per_min]` pairs: the row in force at the period start, dated at the period start, followed by each later row taking effect inside the period, in time order.
26. `control_reconciliation.json` maps every control id published in `/app/data/audit_annex.pdf`, plus the annex block figures published elsewhere, to `file`, `block`, `expected_records`, `expected_sum`, `records`, `sum` and `match`, where the last three are your recomputation and whether both figures agree.
27. `team_chargeback.json` maps every team that appears on an attempt or artifact to `attempts_billed`, `compute_micro`, `storage_micro`, `cache_credit_micro` and `net_micro`.
28. `cache_effectiveness.json` maps every team of a lookup's attempt to its count of each of the six outcomes plus `valid_hit_permille`, the integer floor of 1000 times hits over all lookups that are not replays, `0` when there are none.
29. `close_summary.json` holds `attempts_listed`, `attempts_billed`, `compute_micro`, `storage_micro`, `cache_credit_micro`, `net_micro`, `invoice_mismatches`, `controls_mismatched` and `closing_micro`, each summing or counting the matching artifact.
30. `source_audit.json` maps every input file name to `{"records": n}`, the number of distinct records in its primary table.
31. The artifacts use exactly the keys listed above, `.jsonl` rows sorted ascending by their row key compared as strings, UTF-8, LF line endings and a final newline.

## The program

32. `python3 /app/out/settle.py DATA_DIR OUT_DIR` reads only `DATA_DIR`, writes the thirteen data artifacts into `OUT_DIR`, creating it when needed, and exits 0. On a close of this size the program finishes within 15 minutes.
33. Run on a different close exported under the same documented layout, with fresh identifiers, values and convention placements, the program produces that close's correct attempt costs.
34. On such a close it produces the correct team and cost center of every attempt.
35. On such a close it produces the correct outcome and eviction of every lookup.
36. On such a close it produces the correct invalidation verdict of every target.
37. On such a close it produces the correct hermeticity and toolchain version of every action.
38. On such a close it produces the correct storage cost of every artifact.
39. On such a close it produces the correct status of every invoice line.
40. On such a close it produces the correct closing balance of every cost center.
41. On such a close it produces the correct rate windows.
42. On such a close it produces the correct control figures and verdicts.
43. Nothing in the program depends on identifiers or values of the shipped sample.
44. The output depends only on the contents of `DATA_DIR`, never on where that directory sits.
45. The program reads no input location other than the directory it was given.
46. Two runs on the same input produce byte-identical artifacts.
47. The program creates files only inside `OUT_DIR`.
48. The program leaves `DATA_DIR` unchanged.

## How to work

49. Before treating your decoding as final, reconcile it against the block control figures the documents publish.
50. Read every document that publishes field conventions before you write the decoders that depend on them.
51. Exercise your program on a copy of the corpus in another directory during the session and compare the artifacts with those of a run on `/app/data`.
52. When two sources disagree, settle it by the written precedence and amendment rules, never by which file looks newer or cleaner.
53. Keep reading, decoding, settlement rules and writing in separate functions of `settle.py` so each part can be checked alone.
54. Leave every file under `/app/data` unchanged.
55. Never copy a figure from a draft or mirror export into an artifact.
56. Your final message names each export you treated as a mirror, draft or working copy and the written rule behind each decision.
57. Work offline with Python 3 and its standard library only; nothing installed at run time is available later, and outputs go only under `/app/out`.

You have 14400 seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.
