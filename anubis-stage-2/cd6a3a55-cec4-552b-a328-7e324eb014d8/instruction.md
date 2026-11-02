The model training platform team owns the Helios close program, which produces the quarterly training-component exposure close. Its source is the repository at `/app/repo` and the fifty exports of the Q3 2025 close are in `/app/data`. The Q3 dry run disagreed with the published control figures, so the program is known to be wrong in several places. Repair it and produce the close.

The sources overlap and conflict, and some shipped values are wrong or superseded by design. `/app/data/close_contract.md` is the authority: it and the documents it names define which source governs each fact, how amendments, errata, approvals and the cut apply, and the exact layout of every deliverable. Values are compared exactly at the documented precision, keys, types, row order and line endings.

This is a faulty-computation repair, not a report-writing exercise. The repository already contains the readers, normalisers, close rules, reconciliation logic and command entry point. Several interacting defects make that implementation disagree with the source authority. The finished repository must continue to derive results from any compatible input directory. A program that happens to reproduce this quarter's figures but does not apply the documented rules to another compatible corpus is not finished.

The term source layer below means the six record-oriented logical values resolved from the exports. Risk layer means the six population and allocation values derived from the source layer. Close layer means the six certification and reconciliation values derived from both earlier layers. These are dependencies inside one run, not files that may be used as scratch input. The evidence layer is another set of six outputs from those same in-memory values. The program may construct ordinary Python values while working, but an artifact written to disk is a final output and must never become input to another artifact.

All twenty-four outputs form one close. Shared facts must agree everywhere they appear. This includes identifiers, counts, risk amounts, capacity and allocation values, null state, sequence position, authority digests, freeze state and amendment impact. Agreement is at the precision of the field as written. It is not enough for independently rounded values to be merely close. The order of folding, capping, rounding and applying an adjustment is part of the result whenever the contract gives that order.

## One complete run

The close has three logical layers, but they are resolved in memory during one invocation. Run `python3 /app/out/build.py <DATA_DIR> <OUT_DIR>`. The program reads only the input directory it is handed, computes the complete reconciled set without reading back any file it writes, and writes all twenty-four files directly in its output directory. There are no phase directories and no separate phase commands.

## Deliverables

Source layer: `/app/out/packages.jsonl`, `/app/out/pins.jsonl`, `/app/out/exposures.jsonl`, `/app/out/services.jsonl`, `/app/out/teams.csv`, `/app/out/ledger.jsonl`.

Risk layer: `/app/out/package_risk.json`, `/app/out/service_risk.json`, `/app/out/remediation_plan.json`, `/app/out/team_rollup.json`, `/app/out/license_summary.json`, `/app/out/sla_metrics.json`.

Close layer: `/app/out/release_gates.json`, `/app/out/control_reconciliation.json`, `/app/out/deferred_amendments.json`, `/app/out/team_scorecard.json`, `/app/out/certification.json`, `/app/out/chain_audit.json`.

Evidence layer: `/app/out/authority-trace.xml`, `/app/out/rollup-ledger.tsv`, `/app/out/reconciliation-map.yaml`, `/app/out/dependency-matrix.ini`, `/app/out/freeze-register.log`, `/app/out/training-closure.md`.

Program: `/app/out/build.py`, the repaired program as one self-contained file.

Every field, type, precision, rounding step, ordering rule and null form of these files is defined in sections 9 to 12 of the contract; the requirements below name what must hold.

Sections 9 to 13 of the contract are part of this output contract. A rule for an artifact applies to that artifact in full: its literal file name, top-level shape, nested paths, scalar types, units, decimal places, ordering, character encoding, line ending, final newline and null form. Do not replace a delegated rule with a similar local convention.

The six evidence formats present the same evidence identities through different container shapes. Their purpose is to make the cross-artifact close inspectable without weakening the source-of-truth rules. They do not authorise a second computation. Each evidence value must come from the same in-memory object used for the JSON or line-oriented artifact it describes. A repeated digest is therefore a binding to a computed byte string, not permission to read that byte string back from disk.

## Source layer requirements

1. `packages.jsonl` gives every package its release count and its yanked count as of the cut.
2. `packages.jsonl` gives every package its latest release, that release's licence and obligation, and its owning team.
3. `pins.jsonl` has one row per in-force declaration from the authoritative source, with the canonical constraint and the source file.
4. `pins.jsonl` gives every declaration its pinned version and disposition.
5. `pins.jsonl` gives every runtime pin the licence and obligation of its pinned release.
6. `exposures.jsonl` lists exactly the affected runtime pins of active services, with the pinned version.
7. `exposures.jsonl` gives every exposure its base score and severity.
8. `exposures.jsonl` gives every exposure its status: open, waived or not_affected.
9. `exposures.jsonl` gives every exposure its publication date and business days open.
10. `exposures.jsonl` gives every exposure its SLA target and breach flag.
11. `exposures.jsonl` gives every exposure its remediation estimate and fixed version.
12. `services.jsonl` gives every service its team, tier, region and status at the cut.
13. `services.jsonl` gives every service its deploy count and weight.
14. `teams.csv` gives every team its model, capacity hours and engineer count.
15. `ledger.jsonl` carries every opening and entry row, in the documented order, with its EUR cent amount.
16. `ledger.jsonl` carries the closing balance of every team.
17. `ledger.jsonl` carries every in-force published control figure.
18. `ledger.jsonl` carries one custody row per export with its counts and checksums.
19. `ledger.jsonl` carries the deferred register: every amendment recorded at or after the cut, reported and not applied.
20. The source-layer files use the documented keys in the documented order, LF line endings, a final newline and the documented row order.

## Risk layer requirements

Items 21 to 35 must hold for the risk files computed from the source layer in the same run, including when the program is run over another corpus of the documented layout.

21. `package_risk.json` gives every package with an open exposure its open count, maximum score and risk.
22. `package_risk.json` gives every row its share, percent rank and dense rank over the whole list, and carries the totals.
23. `service_risk.json` gives every active service its team, open count, risk and share.
24. `service_risk.json` gives every active service its dense rank and breach count, and carries the totals.
25. `remediation_plan.json` allocates team hours and pool hours to the open exposures in source-layer sequence order (the stage-1 sequence of contract section 9) under the documented caps.
26. `remediation_plan.json` gives every row the remaining team and pool hours after it.
27. `remediation_plan.json` carries the allocation totals and the pool cap.
28. `team_rollup.json` gives every team its services, open count, risk, share and rank.
29. `team_rollup.json` gives every team its ledger fold balance, held amount and held entries.
30. `license_summary.json` gives the pins, packages and share of every obligation class.
31. `license_summary.json` gives every team its strong-obligation count and rank.
32. `sla_metrics.json` counts, per severity, open rows, rows with days, nulls, zeros and breaches.
33. `sla_metrics.json` gives, per severity, the mean, the two nearest-rank percentiles and the maximum of days open.
34. Every risk-layer file is the documented function of the six source-layer values held in the same run.
35. Every risk-layer file carries in `upstream` the SHA-256 of the six source-layer byte strings that the run will publish.

## Close layer requirements

Items 36 to 49 must hold for the close files computed from the source and risk layers held in memory during that run.

36. `release_gates.json` gives every active service its team and verdict and carries the totals.
37. `release_gates.json` gives every verdict its reasons in the documented order.
38. `control_reconciliation.json` recomputes every published control from the source and risk layers.
39. `control_reconciliation.json` states whether each control agrees with both layers and carries the totals.
40. `deferred_amendments.json` gives every deferred amendment its impact and after value.
41. `deferred_amendments.json` carries the amendment totals.
42. `team_scorecard.json` gives every team its allocated hours, utilisation and breaches.
43. `team_scorecard.json` gives every team its score and rank.
44. `certification.json` carries the closure risk figures, gaps, pool use and unallocated hours.
45. `certification.json` carries the closure counts and the verdict.
46. `chain_audit.json` lists the twelve upstream files with their rows and bytes.
47. `chain_audit.json` carries the eight consistency checks.
48. Every close-layer file is the documented function of the twelve upstream values held in memory.
49. Every close-layer file carries in `upstream` the SHA-256 of the twelve upstream byte strings that the run will publish.

## The program

`/app/out/build.py` runs as `python3 /app/out/build.py DATA_DIR OUT_DIR`, as section 13 of the contract defines.

The invocation is the entire production run. With two valid arguments it creates the output directory when required, prepares every byte, and publishes the full set. It must not expose a half-written set if parsing, reconciliation or serialisation fails. Repeating the command may replace an earlier complete set, but the resulting bytes must be identical for identical input. The executable may use temporary storage only as private write staging for the final all-or-nothing publish; it must not use a written artifact as an upstream data source.

Exit status 2 is reserved for an argument-count error. Exit status 3 covers an input directory that does not exist, cannot be read, lacks a required export or contains a value that cannot be parsed under the contract. Either error prints exactly one diagnostic line to standard error, beginning with `error: `, and leaves no newly written artifact. Successful operation prints no data to standard output and exits 0.

Directory names carry no meaning. Renaming the supplied input directory or choosing another output directory must not alter the bytes. The implementation must discover the required exports from the contents and the fixed contract names inside the supplied directory, and it must never consult another copy of the corpus. No wall clock, process identifier, random draw, locale default, host path or unordered filesystem walk may affect output.

50. The program gives the right packages and pins on another corpus of the same layout.
51. The program gives the right exposures on another corpus of the same layout.
52. The program gives the right services, teams and ledger on another corpus of the same layout.
53. An incomplete or unreadable input directory exits with status 3, prints one line starting with `error: ` and writes nothing; wrong arguments exit with status 2.
54. Running the program again over the same input writes a byte-identical complete set.
55. The program never embeds answers of the shipped corpus; on another corpus it computes that corpus's close.
56. Output does not depend on the names or locations of the input and output directories.
57. The program reads only the input directory it is handed, never `/app/data` unless that is the directory it is handed.
58. The full build is deterministic.
59. The run computes every layer before publishing any file and never reads an artifact back as input.
60. Values shared by two or more artifacts are carried in memory and are serialised from the same resolved value.
61. The `upstream` digests always describe the bytes actually delivered beside them.
62. The program writes only inside its own output directory, apart from the private staging described above, creates that directory when needed and leaves entries there that are not artifacts of the close (such as the program itself) in place.

## Evidence layer requirements

The evidence files are part of the close and carry real values. Every entry, and every audit row of the other artifacts, is defined by section 12.7 of the contract: its field order, nesting, units, precision, null representation and sort order. Follow that section exactly.

63. `authority-trace.xml` contains the complete ordered authority trace and its values agree with the JSON close.
64. `rollup-ledger.tsv` contains the ordered reconciliation ledger with its parent and lineage columns.
65. `reconciliation-map.yaml` carries the same logical entries at the documented nested paths.
66. `dependency-matrix.ini` carries the same entries in dotted sections with the documented keys; its first 216 entries also carry the dependent artifact, prerequisite artifact and three locator keys defined by contract section 12.7.
67. `freeze-register.log` carries one correlated span per entry in the documented written order.
68. `training-closure.md` carries the complete evidence table, including every labelled numeric value.
69. All six evidence files contain exactly the documented set of logical evidence identities.
70. The digest, fold, open-count and risk values for one evidence identity agree across all six formats.
71. Every evidence identity resolves to the source, risk and close values named by its lineage.
72. The evidence sequence is stable across repeat runs and does not depend on directory names.
73. XML is UTF-8, begins with the documented declaration, has one root element and ends with LF.
74. TSV uses a single header, tab separators, no quoting, LF endings and a final newline.
75. YAML uses two-space indentation, plain decimal scalars, no document marker, LF endings and a final newline.
76. INI uses the documented dotted section names, lower-case keys, LF endings and a final newline.
77. LOG writes the documented key-value fields in the documented order, one entry per line, with LF and a final newline.
78. Markdown uses the documented heading and table columns, with LF endings and a final newline.
79. Every one of the twenty-four artifacts has at least 800 physical lines and at least 400 addressable leaf values.
80. No more than four artifacts have fewer than 1,000 physical lines.
81. Nested formats keep the documented five-level lineage, and tabular formats carry the matching parent and path columns.
82. The output set contains the documented 216 dependency edges and every edge carries its three locator keys.
83. The as-of freeze reports the later amendments recorded in the six exports named in contract section 8.6 and applies them only in the deferred impact view.
84. Null remains distinct from numeric zero in capacity and elapsed-day fields.

## Reading the corpus

85. Every cell of every export is read under its registered convention. A cell that is neither empty, nor a registered sentinel token, nor a value in the documented form of its convention makes the input invalid: the program exits with status 3 as section 13 of the contract defines, and it never reads such a cell as an absent value.
86. The policy documents in the input directory state the figures they govern: SLA targets by severity and tier, holidays by region, base hours by severity and tier weights. The program reads those figures from the documents of the directory it is handed, because another corpus may state different figures.
87. The published control figures cover teams, exports and global totals only. Package, pin, exposure and service values have no published figure of their own, so they must come from the documented rules, and a value that merely matches this quarter's exports is no proof that the rule behind it is implemented.

## How to work

88. Read the contract and the documents it names before you change the program.
89. Check each suspected defect against the published control figures, the custody counts or the documented rules before you change the code for it.
90. Decide every conflict between sources by the authority rules of the contract, not by which source looks newer, cleaner or more complete.
91. When two plausible readings of a rule each break a different control figure, use the documented rule that satisfies both.
92. Resolve the three logical layers in their documented order while retaining their shared values in memory.
93. Use the repository's own validation command and its amalgamation tool while you work.
94. Work offline, using only what the image provides; fetching code, data or answers from anywhere else is forbidden.
95. Leave the files in /app/data unmodified and produce every deliverable by running the program rather than writing values by hand. Keep notes, scratch programs and trial outputs out of `/app/repo`; the repository holds only the program, its tests and its tools.
96. In your final message, list every repair you made with the module you changed, the contract section or named document rule that the repair restores, and the control figure, custody count or documented rule that confirmed it. Then give the agreeing and total control counts of your final build and name the output directory. Also name each rule whose two plausible readings each broke a different control figure, with the documented rule you applied, or say that you met none.

Use only the Python standard library and the packages already installed in the image. Write outputs only at the declared paths.

You have 7200 seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.
