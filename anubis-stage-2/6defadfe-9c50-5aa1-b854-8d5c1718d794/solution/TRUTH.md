# TRUTH.md - 6defadfe-9c50-5aa1-b854-8d5c1718d794

## Defect

The shipped `trainyard` project (`/app/data/project.zip`) does not install on Python 3.12, and once it does it computes the stage ledger the textbook way instead of by the approved CI ledger specification revision C (`ci_ledger_spec_revC.docx`), its approved errata (`errata_register.pdf`) and the governance precedence document (`governance_precedence.docx`). It also trusts or ignores the fifteen partially authoritative files wholesale. The agent must repair the package, ship it as `/app/out/package.zip`, and write the stage-1 ledger with it; the same package is then run on a hidden stage-2 feed opened from the agent's own `summary.json`. The numbered list is the complete set of shipped defects; solve.py applies the inverse of each.

1. (focal) requires-python excludes the Python 3.12 runtime - `pyproject.toml`.
2. (focal) package-dir and package discovery point at a missing lib/ tree - `pyproject.toml`.
3. (focal) pypdf, needed by the pdf reader, is not a declared dependency - `pyproject.toml`.
4. (focal) third-party tomli imported instead of the stdlib tomllib - `src/trainyard/readers.py`.
5. (focal) circular import conventions -> feed -> readers -> conventions - `src/trainyard/conventions.py`.
6. (focal) unclosed tuple literal (SyntaxError) - `src/trainyard/ledger.py`.
7. (drift) E6: duration conversion rounds half up instead of half to even - `src/trainyard/conventions.py`.
8. (drift) E1: pass_rate rounded half up instead of half to even - `src/trainyard/conventions.py`.
9. (trap) 3.1: homoglyph table never applied to references - `src/trainyard/conventions.py`.
10. (trap) 3.6: provisional ~ rows read as live rows - `src/trainyard/conventions.py`.
11. (trap) 3.4: the 1904 workbook date system is ignored - `src/trainyard/conventions.py`.
12. (trap) 3.6: cp1252 lines decoded with replacement characters - `src/trainyard/readers.py`.
13. (trap) 3.0: #header rows skipped without switching the column order - `src/trainyard/readers.py`.
14. (trap) 2.1: feed index found by file name or by its .json suffix instead of its control block - `src/trainyard/feed.py`.
15. (trap) 2.4: chain taken in path order instead of chain_pos - `src/trainyard/feed.py`.
16. (trap) 4.1: first revocation action wins instead of the latest - `src/trainyard/feed.py`.
17. (focal) G4: in-window renames of the next-quarter registry never loaded - `src/trainyard/feed.py`.
18. (trap) 4.4: failed skew probes (-1) read as measurements - `src/trainyard/feed.py`.
19. (drift) E10: skew estimates never used for unmeasured hosts - `src/trainyard/feed.py`.
20. (trap) 4.4: latest skew measurement overall instead of the latest at or before the start - `src/trainyard/feed.py`.
21. (trap) G7: CMDB sites override hosts.ini - `src/trainyard/feed.py`.
22. (trap) 4.8: first maintenance event per UID wins instead of the highest SEQUENCE - `src/trainyard/feed.py`.
23. (trap) 4.8: cancelled maintenance windows applied - `src/trainyard/feed.py`.
24. (focal) G13: uncountersigned actions of the second void register applied - `src/trainyard/feed.py`.
25. (trap) 4.7: void actions applied in file order instead of seq - `src/trainyard/feed.py`.
26. (drift) E9: confirmed corrections of errata revision B never adopted - `src/trainyard/feed.py`.
27. (trap) 4.3: commit order taken from log position instead of Change-Seq - `src/trainyard/feed.py`.
28. (focal) G10: Rewritten-From trailers read from the rebased log, which has none - `src/trainyard/feed.py`.
29. (trap) 6.2: first toolchain pin wins instead of the highest rev - `src/trainyard/feed.py`.
30. (trap) 4.4: registry tz used instead of the timekeeping history - `src/trainyard/feed.py`.
31. (trap) 5.4/G9: revoked quarantine entries still applied - `src/trainyard/feed.py`.
32. (focal) G5: every row of the mirror re-export trusted - `src/trainyard/ledger.py`.
33. (focal) G6: every row of the rerun export trusted - `src/trainyard/ledger.py`.
34. (drift) 4.1: newest revision wins regardless of exporter rank - `src/trainyard/ledger.py`.
35. (trap) 4.1: legacy job codes never mapped through appendix D - `src/trainyard/ledger.py`.
36. (trap) 4.2: only the literal branch name main accepted - `src/trainyard/ledger.py`.
37. (trap) G3: lab pool hosts kept - `src/trainyard/ledger.py`.
38. (trap) 4.2: decommission judged at the window start instead of the attempt - `src/trainyard/ledger.py`.
39. (drift) 4.2: window judged on the uncorrected start and closed at the end - `src/trainyard/ledger.py`.
40. (drift) E7: maintenance windows closed at the end - `src/trainyard/ledger.py`.
41. (trap) 4.7: builds re-exported from an earlier stage counted again - `src/trainyard/ledger.py`.
42. (drift) 4.6: highest attempt decides even when it is infra - `src/trainyard/ledger.py`.
43. (trap) 5.2: test registration window not applied - `src/trainyard/ledger.py`.
44. (focal) G12: crash rows without a crash column demoted to failures - `src/trainyard/ledger.py`.
45. (drift) E4: flaky evidence from deciding attempts only - `src/trainyard/ledger.py`.
46. (drift) E2: median averages the two middle values - `src/trainyard/ledger.py`.
47. (trap) 7.2: carried last_good of the resume state ignored - `src/trainyard/ledger.py`.
48. (trap) 7.2: dominant bucket ties broken by first occurrence - `src/trainyard/ledger.py`.
49. (trap) 7.1: compile bucket carries the whole error cell - `src/trainyard/ledger.py`.
50. (drift) E5: return addresses looked up without subtracting one - `src/trainyard/crash.py`.
51. (trap) 6.1: Message-ID crosswalk unused for reports without X-Crash-Id - `src/trainyard/crash.py`.
52. (trap) 6.1: first report revision wins - `src/trainyard/crash.py`.
53. (trap) 6.3: noise frames name the crash - `src/trainyard/crash.py`.
54. (hardening) 6.1: a crash with no stack in any source is labelled unknown instead of stopping the run; the specification gives no label for it and no feed carries one, so nothing grades it - `src/trainyard/crash.py`.
55. (drift) E3: caret on zero versions treated like any other caret - `src/trainyard/deps.py`.
56. (trap) 9.4: prerelease versions satisfy plain ranges - `src/trainyard/deps.py`.
57. (drift) E8: publication, advisories and amendments at the cut treated as after it - `src/trainyard/deps.py`.
58. (focal) G14: the withdrawn list of the mirror index never loaded - `src/trainyard/deps.py`.
59. (trap) 9.1: package alias register not applied - `src/trainyard/deps.py`.
60. (trap) 9.5: pin none and expiry at the cut not honoured - `src/trainyard/deps.py`.
61. (focal) G15: pins: snapshot entries never resolved through the snapshot - `src/trainyard/deps.py`.
62. (trap) 9.3: advisory actions of the dependency audit ignored - `src/trainyard/deps.py`.
63. (trap) 9.5: locked versions used for modules that are not frozen - `src/trainyard/deps.py`.
64. (hardening) 6.3: an unresolved frame offset is lower-cased instead of kept as written; every unresolved frame offset in both stages is written in lower case, so nothing grades it - `src/trainyard/crash.py`.

Totals: 14 (focal), 13 (drift), 35 (trap), 2 (hardening, ungraded).

The reference is Python 3.12 (`solution/solve.py` extracts the project, applies the inverse of every defect, archives the project and runs it). Grading has two channels: deterministic checks in `tests/test_output.py` and judged trajectory criteria in `tests/judge.toml`.

Out of bounds: embedding stage-1 answers in the package (`negative_hardcoded_sample_answers`), behaviour keyed on feed file names (the six stage-2 checks run on a renamed copy of the hidden feed), reading the agent data directory at run time (the hidden stage-2 run happens where /app/data does not exist, so every stage-2 check fails) and nondeterministic output (`negative_nondeterministic_output`).

### Debugging concepts (all load-bearing, interacting)

- C1 Packaging and import repair: requires-python, src-layout discovery, declared runtime dependencies, an import cycle and a syntax error keep the tool from installing on Python 3.12 (defects 1 to 6). Nothing else can be observed until these are fixed, and the dependency set must match what the installer provides.
- C2 Source precedence and provenance: copies of one attempt from several exporters, revoked export jobs, revisions, void registers, errata registers and re-exported keys decide which row is the attempt (spec 4.1, 4.5, 4.7, governance G2, G13, E9). The winner feeds every later concept.
- C3 Clock normalisation: host-local wall times through a per-host time zone history, DST, per-host clock skew taken at or before the uncorrected start, and half-open windows (spec 3.4, 4.4, 4.8, 4.9, E7, E10). The corrected start decides scope, module alias validity, decommissioning, test registration and quarantine.
- C4 Flaky test detection and quarantine: mixed outcomes at one commit across every pass or fail attempt (E4, an expert variant of the textbook deciding-attempt rule), carried flaky state, quarantine at the corrected start with revocations (spec 5.3 to 5.5, G9). It decides which failures are real.
- C5 Crash symbolication: frames resolved through the toolchain pinned for the build's commit or a build-id map, return addresses looked up at offset minus one (E5, the expert pc-1 rule), noise frames skipped, template labels from the frame register (spec 6). It produces the crash buckets.
- C6 Regression bisection: last good and first bad commits ordered by Change-Seq rather than log position, carried last-good state, rebased commits through Rewritten-From, suspects and dominant bucket (spec 4.3, 7.2, G10).
- C7 Dependency resolution: semver 2.0 precedence, caret on zero versions (E3), prerelease admission, yanks and withdrawals at the cut (E8, G14), frozen locks, snapshot pins (G15), org overrides (spec 9).
- C8 Invariants and control chains: per-file record counts and the run control chain are the only global proof that every file was read and read right; the chain also opens the next stage (spec 2.3, 2.4, 10.6, 10.7).

Interactions:

- C2 -> C3: the winning copy of an attempt fixes the host and logged time that the clock rules correct.
- C3 -> C2: the corrected start decides window scope, decommissioning and which alias row names the module.
- C3 -> C4: test registration and quarantine are judged at the corrected start.
- C2 -> C4: flaky evidence is collected from every accepted attempt after errata and maintenance turn some into infra.
- C4 -> C5 -> C6: only real failures produce buckets; crash buckets come from symbolication; buckets decide red commits and the dominant bucket.
- C6 -> C8: last_good and last_good_seq are carried into summary.json, which is the next stage's resume state.
- C1 -> everything: the hidden stage-2 feed is run through the agent's own package.

Expert-only variants (drift items): E5 return addresses minus one, E3 caret on zero versions, E1 banker's rounding of pass_rate, E2 lower median, E4 flaky evidence from every attempt, E6 half-even millisecond conversion, E7 half-open windows, E8 actions at the cut, E9 adoption of confirmed revB rows, E10 skew estimates only for unmeasured hosts.

## Load-bearing work

Graded artifacts:

- `/app/out/package.zip`
- `/app/out/selftest.json`
- `/app/out/build_report.json`
- `/app/out/module_core.json`
- `/app/out/module_metrics.json`
- `/app/out/dependency_resolution.json`
- `/app/out/summary.json`

Content contract: the six JSON outputs follow section 10 of revision C; package.zip holds pyproject.toml, src/trainyard and the unchanged tests, installs with pip on Python 3.12 using only PyYAML, pyarrow and pypdf, and reproduces the stage-2 ledger from the agent's own summary.json.

### 100-file inventory

| file | id | type | rows | scope | unique contribution | depends on | depended on by | ablation score |
|---|---|---|---|---|---|---|---|---|
| builds_core_p01.csv | BLD-01 | csv | 5000 | in scope | its own attempt rows and its control token; rows of one exporter appear in no other exporter's file; control token | CMT-01, DCY-01, DCY-02, DCY-05, DCY-06, DCY-08, DCY-11, DCY-12, DCY-13, DCY-14, DCY-15, DOC-01, DOC-02, DOC-05, DOC-06, DOC-07, DOC-08, HST-01, HST-02, IDX-01, MNT-01, REG-01, TST-01, TST-02, TST-03, TST-04, TST-05, TST-06, TST-07, TST-08, TST-09, TST-10, TST-11, TST-12, TST-13, TST-14, TST-15, TST-16, TST-17, TST-18, TST-19, TST-20, TST-21, TST-22, VOD-01, VOD-02 | 26 files | <= 0.024 (structural) |
| builds_core_p02.csv | BLD-02 | csv | 5000 | in scope | its own attempt rows and its control token; rows of one exporter appear in no other exporter's file; control token | CMT-01, DCY-01, DCY-02, DCY-05, DCY-06, DCY-08, DCY-11, DCY-12, DCY-13, DCY-15, DOC-01, DOC-02, DOC-05, DOC-06, DOC-07, DOC-08, HST-01, HST-02, IDX-01, MNT-01, REG-01, TST-01, TST-02, TST-03, TST-04, TST-05, TST-06, TST-07, TST-08, TST-09, TST-10, TST-11, TST-12, TST-13, TST-14, TST-15, TST-16, TST-17, TST-18, TST-19, TST-20, TST-21, TST-22, VOD-01, VOD-02 | 26 files | <= 0.024 (structural) |
| builds_core_p03.csv | BLD-03 | csv | 5000 | in scope | its own attempt rows and its control token; rows of one exporter appear in no other exporter's file; control token | CMT-01, CRS-02, DCY-01, DCY-02, DCY-05, DCY-06, DCY-08, DCY-11, DCY-12, DCY-13, DCY-15, DOC-01, DOC-02, DOC-05, DOC-06, DOC-07, DOC-08, HST-01, HST-02, IDX-01, MNT-01, REG-01, TST-01, TST-02, TST-03, TST-04, TST-05, TST-06, TST-07, TST-08, TST-09, TST-10, TST-11, TST-12, TST-13, TST-14, TST-15, TST-16, TST-17, TST-18, TST-19, TST-20, TST-21, TST-22, VOD-01, VOD-02 | 26 files | <= 0.024 (structural) |
| builds_core_p04.csv | BLD-04 | csv | 5000 | in scope | its own attempt rows and its control token; rows of one exporter appear in no other exporter's file; control token | BLD-11, CMT-01, DCY-01, DCY-02, DCY-05, DCY-06, DCY-08, DCY-11, DCY-12, DCY-13, DCY-15, DOC-01, DOC-02, DOC-05, DOC-06, DOC-07, DOC-08, HST-01, HST-02, IDX-01, MNT-01, REG-01, TST-01, TST-02, TST-03, TST-04, TST-05, TST-06, TST-07, TST-08, TST-09, TST-10, TST-11, TST-12, TST-13, TST-14, TST-15, TST-16, TST-17, TST-18, TST-19, TST-20, TST-21, TST-22, VOD-01, VOD-02 | 26 files | <= 0.024 (structural) |
| builds_core_p05.csv | BLD-05 | csv | 5000 | in scope | its own attempt rows and its control token; rows of one exporter appear in no other exporter's file; control token | CMT-01, DCY-01, DCY-02, DCY-05, DCY-06, DCY-08, DCY-11, DCY-12, DCY-13, DCY-15, DOC-01, DOC-02, DOC-05, DOC-06, DOC-07, DOC-08, HST-01, HST-02, IDX-01, MNT-01, REG-01, TST-01, TST-02, TST-03, TST-04, TST-05, TST-06, TST-07, TST-08, TST-09, TST-10, TST-11, TST-12, TST-13, TST-14, TST-15, TST-16, TST-17, TST-18, TST-19, TST-20, TST-21, TST-22, VOD-01, VOD-02 | 26 files | <= 0.024 (structural) |
| builds_edge_p06.tsv | BLD-06 | tsv | 5000 | in scope | its own attempt rows and its control token; rows of one exporter appear in no other exporter's file; control token | BLD-22, CMT-01, DCY-01, DCY-02, DCY-05, DCY-06, DCY-08, DCY-11, DCY-12, DCY-13, DCY-15, DOC-01, DOC-02, DOC-05, DOC-06, DOC-07, DOC-08, HST-01, HST-02, IDX-01, MNT-01, REG-01, TST-01, TST-02, TST-03, TST-04, TST-05, TST-06, TST-07, TST-08, TST-09, TST-10, TST-11, TST-12, TST-13, TST-14, TST-15, TST-16, TST-17, TST-18, TST-19, TST-20, TST-21, TST-22, VOD-01, VOD-02 | 26 files | <= 0.024 (structural) |
| builds_edge_p07.tsv | BLD-07 | tsv | 5000 | in scope | its own attempt rows and its control token; rows of one exporter appear in no other exporter's file; control token | BLD-09, CMT-01, DCY-01, DCY-02, DCY-05, DCY-06, DCY-08, DCY-11, DCY-12, DCY-13, DCY-15, DOC-01, DOC-02, DOC-05, DOC-06, DOC-07, DOC-08, HST-01, HST-02, IDX-01, MNT-01, REG-01, TST-01, TST-02, TST-03, TST-04, TST-05, TST-06, TST-07, TST-08, TST-09, TST-10, TST-11, TST-12, TST-13, TST-14, TST-15, TST-16, TST-17, TST-18, TST-19, TST-20, TST-21, TST-22, VOD-01, VOD-02 | 26 files | <= 0.024 (structural) |
| builds_edge_p08.tsv | BLD-08 | tsv | 5000 | in scope | its own attempt rows and its control token; rows of one exporter appear in no other exporter's file; control token | CMT-01, DCY-01, DCY-02, DCY-05, DCY-06, DCY-08, DCY-11, DCY-12, DCY-13, DCY-15, DOC-01, DOC-02, DOC-05, DOC-06, DOC-07, DOC-08, HST-01, HST-02, IDX-01, MNT-01, REG-01, TST-01, TST-02, TST-03, TST-04, TST-05, TST-06, TST-07, TST-08, TST-09, TST-10, TST-11, TST-12, TST-13, TST-14, TST-15, TST-16, TST-17, TST-18, TST-19, TST-20, TST-21, TST-22, VOD-01, VOD-02 | 25 files | <= 0.024 (structural) |
| builds_stream_p09.jsonl | BLD-09 | jsonl | 5000 | in scope | its own attempt rows and its control token; rows of one exporter appear in no other exporter's file; control token | CMT-01, DCY-01, DCY-02, DCY-04, DCY-05, DCY-06, DCY-08, DCY-11, DCY-12, DCY-13, DCY-15, DOC-01, DOC-02, DOC-05, DOC-06, DOC-07, DOC-08, HST-01, HST-02, IDX-01, MNT-01, REG-01, TST-01, TST-02, TST-03, TST-04, TST-05, TST-06, TST-07, TST-08, TST-09, TST-10, TST-11, TST-12, TST-13, TST-14, TST-15, TST-16, TST-17, TST-18, TST-19, TST-20, TST-21, TST-22, VOD-01, VOD-02 | 26 files | <= 0.024 (structural) |
| builds_stream_p10.jsonl | BLD-10 | jsonl | 5000 | in scope | its own attempt rows and its control token; rows of one exporter appear in no other exporter's file; control token | CMT-01, DCY-01, DCY-02, DCY-05, DCY-06, DCY-08, DCY-11, DCY-12, DCY-13, DCY-15, DOC-01, DOC-02, DOC-05, DOC-06, DOC-07, DOC-08, HST-01, HST-02, IDX-01, MNT-01, PIN-01, REG-01, TST-01, TST-02, TST-03, TST-04, TST-05, TST-06, TST-07, TST-08, TST-09, TST-10, TST-11, TST-12, TST-13, TST-14, TST-15, TST-16, TST-17, TST-18, TST-19, TST-20, TST-21, TST-22, VOD-01, VOD-02 | 26 files | <= 0.024 (structural) |
| builds_stream_p11.jsonl | BLD-11 | jsonl | 5000 | in scope | its own attempt rows and its control token; rows of one exporter appear in no other exporter's file; control token | AGT-02, CMT-01, DCY-01, DCY-02, DCY-05, DCY-06, DCY-08, DCY-11, DCY-12, DCY-13, DCY-15, DOC-01, DOC-02, DOC-05, DOC-06, DOC-07, DOC-08, HST-01, HST-02, IDX-01, MNT-01, REG-01, TST-01, TST-02, TST-03, TST-04, TST-05, TST-06, TST-07, TST-08, TST-09, TST-10, TST-11, TST-12, TST-13, TST-14, TST-15, TST-16, TST-17, TST-18, TST-19, TST-20, TST-21, TST-22, VOD-01, VOD-02 | 26 files | <= 0.024 (structural) |
| builds_ops_p12.xlsx | BLD-12 | xlsx | 10000 | in scope | its own attempt rows and its control token; rows of one exporter appear in no other exporter's file; control token | CMT-01, DCY-01, DCY-02, DCY-05, DCY-06, DCY-08, DCY-11, DCY-12, DCY-13, DCY-15, DOC-01, DOC-02, DOC-03, DOC-05, DOC-06, DOC-07, DOC-08, HST-01, HST-02, IDX-01, MNT-01, REG-01, TST-01, TST-02, TST-03, TST-04, TST-05, TST-06, TST-07, TST-08, TST-09, TST-10, TST-11, TST-12, TST-13, TST-14, TST-15, TST-16, TST-17, TST-18, TST-19, TST-20, TST-21, TST-22, VOD-01, VOD-02 | 26 files | <= 0.024 (structural) |
| builds_ops_p13.xlsx | BLD-13 | xlsx | 10000 | in scope | its own attempt rows and its control token; rows of one exporter appear in no other exporter's file; control token | BLD-06, CMT-01, DCY-01, DCY-02, DCY-05, DCY-06, DCY-08, DCY-11, DCY-12, DCY-13, DCY-15, DOC-01, DOC-02, DOC-05, DOC-06, DOC-07, DOC-08, HST-01, HST-02, IDX-01, MNT-01, REG-01, TST-01, TST-02, TST-03, TST-04, TST-05, TST-06, TST-07, TST-08, TST-09, TST-10, TST-11, TST-12, TST-13, TST-14, TST-15, TST-16, TST-17, TST-18, TST-19, TST-20, TST-21, TST-22, VOD-01, VOD-02 | 26 files | <= 0.024 (structural) |
| builds_ops_p14.xlsx | BLD-14 | xlsx | 10000 | in scope | its own attempt rows and its control token; rows of one exporter appear in no other exporter's file; control token | BLD-13, CMT-01, DCY-01, DCY-02, DCY-05, DCY-06, DCY-08, DCY-11, DCY-12, DCY-13, DCY-15, DOC-01, DOC-02, DOC-05, DOC-06, DOC-07, DOC-08, HST-01, HST-02, IDX-01, MNT-01, REG-01, TST-01, TST-02, TST-03, TST-04, TST-05, TST-06, TST-07, TST-08, TST-09, TST-10, TST-11, TST-12, TST-13, TST-14, TST-15, TST-16, TST-17, TST-18, TST-19, TST-20, TST-21, TST-22, VOD-01, VOD-02 | 26 files | <= 0.024 (structural) |
| builds_archive_p15.json | BLD-15 | json | 5000 | in scope | its own attempt rows and its control token; rows of one exporter appear in no other exporter's file; control token | CMT-01, DCY-01, DCY-02, DCY-05, DCY-06, DCY-08, DCY-11, DCY-12, DCY-13, DCY-15, DOC-01, DOC-02, DOC-05, DOC-06, DOC-07, DOC-08, HST-01, HST-02, IDX-01, MNT-01, REG-01, TST-01, TST-02, TST-03, TST-04, TST-05, TST-06, TST-07, TST-08, TST-09, TST-10, TST-11, TST-12, TST-13, TST-14, TST-15, TST-16, TST-17, TST-18, TST-19, TST-20, TST-21, TST-22, VOD-01, VOD-02 | 26 files | <= 0.024 (structural) |
| builds_feed_p16.xml | BLD-16 | xml | 5000 | in scope | its own attempt rows and its control token; rows of one exporter appear in no other exporter's file; control token | CMT-01, DCY-01, DCY-02, DCY-05, DCY-06, DCY-08, DCY-11, DCY-12, DCY-13, DCY-15, DOC-01, DOC-02, DOC-04, DOC-05, DOC-06, DOC-07, DOC-08, HST-01, HST-02, IDX-01, MNT-01, REG-01, TST-01, TST-02, TST-03, TST-04, TST-05, TST-06, TST-07, TST-08, TST-09, TST-10, TST-11, TST-12, TST-13, TST-14, TST-15, TST-16, TST-17, TST-18, TST-19, TST-20, TST-21, TST-22, VOD-01, VOD-02 | 26 files | <= 0.024 (structural) |
| builds_feed_p17.xml | BLD-17 | xml | 5000 | in scope | its own attempt rows and its control token; rows of one exporter appear in no other exporter's file; control token | BLD-18, CMT-01, DCY-01, DCY-02, DCY-05, DCY-06, DCY-08, DCY-11, DCY-12, DCY-13, DCY-15, DOC-01, DOC-02, DOC-05, DOC-06, DOC-07, DOC-08, HST-01, HST-02, IDX-01, MNT-01, REG-01, TST-01, TST-02, TST-03, TST-04, TST-05, TST-06, TST-07, TST-08, TST-09, TST-10, TST-11, TST-12, TST-13, TST-14, TST-15, TST-16, TST-17, TST-18, TST-19, TST-20, TST-21, TST-22, VOD-01, VOD-02 | 26 files | <= 0.024 (structural) |
| builds_cold_p18.parquet | BLD-18 | parquet | 5000 | in scope | its own attempt rows and its control token; rows of one exporter appear in no other exporter's file; control token | CMT-01, DCY-01, DCY-02, DCY-05, DCY-06, DCY-08, DCY-10, DCY-11, DCY-12, DCY-13, DCY-15, DOC-01, DOC-02, DOC-05, DOC-06, DOC-07, DOC-08, HST-01, HST-02, IDX-01, MNT-01, REG-01, TST-01, TST-02, TST-03, TST-04, TST-05, TST-06, TST-07, TST-08, TST-09, TST-10, TST-11, TST-12, TST-13, TST-14, TST-15, TST-16, TST-17, TST-18, TST-19, TST-20, TST-21, TST-22, VOD-01, VOD-02 | 26 files | <= 0.024 (structural) |
| builds_cold_p19.parquet | BLD-19 | parquet | 5000 | in scope | its own attempt rows and its control token; rows of one exporter appear in no other exporter's file; control token | BLD-01, CMT-01, DCY-01, DCY-02, DCY-05, DCY-06, DCY-08, DCY-11, DCY-12, DCY-13, DCY-15, DOC-01, DOC-02, DOC-05, DOC-06, DOC-07, DOC-08, HST-01, HST-02, IDX-01, MNT-01, REG-01, TST-01, TST-02, TST-03, TST-04, TST-05, TST-06, TST-07, TST-08, TST-09, TST-10, TST-11, TST-12, TST-13, TST-14, TST-15, TST-16, TST-17, TST-18, TST-19, TST-20, TST-21, TST-22, VOD-01, VOD-02 | 25 files | <= 0.024 (structural) |
| builds_weekly_p20.docx | BLD-20 | docx | 5000 | in scope | its own attempt rows and its control token; rows of one exporter appear in no other exporter's file; control token | CMT-01, DCY-01, DCY-02, DCY-05, DCY-06, DCY-08, DCY-11, DCY-12, DCY-13, DCY-15, DOC-01, DOC-02, DOC-05, DOC-06, DOC-07, DOC-08, HST-01, HST-02, IDX-01, MNT-01, REG-01, SYM-06, TST-01, TST-02, TST-03, TST-04, TST-05, TST-06, TST-07, TST-08, TST-09, TST-10, TST-11, TST-12, TST-13, TST-14, TST-15, TST-16, TST-17, TST-18, TST-19, TST-20, TST-21, TST-22, VOD-01, VOD-02 | 26 files | <= 0.024 (structural) |
| builds_report_p21.pdf | BLD-21 | pdf | 5000 | in scope | its own attempt rows and its control token; rows of one exporter appear in no other exporter's file; control token | BLD-02, CMT-01, DCY-01, DCY-02, DCY-05, DCY-06, DCY-08, DCY-11, DCY-12, DCY-13, DCY-15, DOC-01, DOC-02, DOC-05, DOC-06, DOC-07, DOC-08, HST-01, HST-02, IDX-01, MNT-01, REG-01, TST-01, TST-02, TST-03, TST-04, TST-05, TST-06, TST-07, TST-08, TST-09, TST-10, TST-11, TST-12, TST-13, TST-14, TST-15, TST-16, TST-17, TST-18, TST-19, TST-20, TST-21, TST-22, VOD-01, VOD-02 | 25 files | <= 0.024 (structural) |
| builds_vault_p22.db | BLD-22 | db | 5000 | in scope | its own attempt rows and its control token; rows of one exporter appear in no other exporter's file; control token | BLD-15, CMT-01, DCY-01, DCY-02, DCY-05, DCY-06, DCY-08, DCY-11, DCY-12, DCY-13, DCY-15, DOC-01, DOC-02, DOC-05, DOC-06, DOC-07, DOC-08, HST-01, HST-02, IDX-01, MNT-01, REG-01, TST-01, TST-02, TST-03, TST-04, TST-05, TST-06, TST-07, TST-08, TST-09, TST-10, TST-11, TST-12, TST-13, TST-14, TST-15, TST-16, TST-17, TST-18, TST-19, TST-20, TST-21, TST-22, VOD-01, VOD-02 | 26 files | <= 0.024 (structural) |
| builds_dashboard_p23.html | BLD-23 | html | 5000 | in scope | its own attempt rows and its control token; rows of one exporter appear in no other exporter's file; control token | CMT-01, DCY-01, DCY-02, DCY-05, DCY-06, DCY-08, DCY-11, DCY-12, DCY-13, DCY-15, DOC-01, DOC-02, DOC-05, DOC-06, DOC-07, DOC-08, HST-01, HST-02, IDX-01, MNT-01, REG-01, TST-01, TST-02, TST-03, TST-04, TST-05, TST-06, TST-07, TST-08, TST-09, TST-10, TST-11, TST-12, TST-13, TST-14, TST-15, TST-16, TST-17, TST-18, TST-19, TST-20, TST-21, TST-22, VOD-01, VOD-02 | 25 files | <= 0.024 (structural) |
| builds_legacy_p24.txt | BLD-24 | txt | 5000 | in scope | its own attempt rows and its control token; rows of one exporter appear in no other exporter's file; control token | CMT-01, DCY-01, DCY-02, DCY-05, DCY-06, DCY-08, DCY-11, DCY-12, DCY-13, DCY-15, DEP-04, DOC-01, DOC-02, DOC-05, DOC-06, DOC-07, DOC-08, HST-01, HST-02, IDX-01, MNT-01, REG-01, TST-01, TST-02, TST-03, TST-04, TST-05, TST-06, TST-07, TST-08, TST-09, TST-10, TST-11, TST-12, TST-13, TST-14, TST-15, TST-16, TST-17, TST-18, TST-19, TST-20, TST-21, TST-22, VOD-01, VOD-02 | 26 files | <= 0.024 (structural) |
| builds_legacy_p25.txt | BLD-25 | txt | 5000 | in scope | its own attempt rows and its control token; rows of one exporter appear in no other exporter's file; control token | CMT-01, DCY-01, DCY-02, DCY-05, DCY-06, DCY-08, DCY-11, DCY-12, DCY-13, DCY-15, DOC-01, DOC-02, DOC-05, DOC-06, DOC-07, DOC-08, HST-01, HST-02, IDX-01, MNT-01, REG-01, TST-01, TST-02, TST-03, TST-04, TST-05, TST-06, TST-07, TST-08, TST-09, TST-10, TST-11, TST-12, TST-13, TST-14, TST-15, TST-16, TST-17, TST-18, TST-19, TST-20, TST-21, TST-22, VOD-01, VOD-02 | 26 files | <= 0.024 (structural) |
| agent_pun.log | AGT-01 | log | 5000 | in scope | its own attempt rows and its control token; rows of one exporter appear in no other exporter's file; control token | CMT-01, DCY-01, DCY-02, DCY-05, DCY-06, DCY-08, DCY-11, DCY-12, DCY-13, DCY-15, DOC-01, DOC-02, DOC-05, DOC-06, DOC-07, DOC-08, HST-01, HST-02, IDX-01, MNT-01, OPN-01, REG-01, TST-01, TST-02, TST-03, TST-04, TST-05, TST-06, TST-07, TST-08, TST-09, TST-10, TST-11, TST-12, TST-13, TST-14, TST-15, TST-16, TST-17, TST-18, TST-19, TST-20, TST-21, TST-22, VOD-01, VOD-02 | 26 files | <= 0.024 (structural) |
| agent_dub.log | AGT-02 | log | 5000 | in scope | its own attempt rows and its control token; rows of one exporter appear in no other exporter's file; control token | CMT-01, DCY-01, DCY-02, DCY-05, DCY-06, DCY-08, DCY-11, DCY-12, DCY-13, DCY-15, DOC-01, DOC-02, DOC-05, DOC-06, DOC-07, DOC-08, HST-01, HST-02, IDX-01, MNT-01, REG-01, TST-01, TST-02, TST-03, TST-04, TST-05, TST-06, TST-07, TST-08, TST-09, TST-10, TST-11, TST-12, TST-13, TST-14, TST-15, TST-16, TST-17, TST-18, TST-19, TST-20, TST-21, TST-22, VOD-01, VOD-02 | 26 files | <= 0.024 (structural) |
| builds_export_full.csv | DCY-03 | csv | 5000 | decoy | its own attempt rows and its control token; rows of one exporter appear in no other exporter's file; control token | CMT-01, DCY-01, DCY-02, DCY-05, DCY-06, DCY-08, DCY-11, DCY-12, DCY-13, DCY-15, DOC-01, DOC-02, DOC-05, DOC-06, DOC-07, DOC-08, HST-01, HST-02, IDX-01, MNT-01, REG-01, TST-01, TST-02, TST-03, TST-04, TST-05, TST-06, TST-07, TST-08, TST-09, TST-10, TST-11, TST-12, TST-13, TST-14, TST-15, TST-16, TST-17, TST-18, TST-19, TST-20, TST-21, TST-22, VOD-01, VOD-02 | 26 files | <= 0.024 (structural) |
| tests_core_p01.csv | TST-01 | csv | 5000 | in scope | its own test result rows and its control token; control token | AGT-01, AGT-02, BLD-01, BLD-02, BLD-03, BLD-04, BLD-05, BLD-06, BLD-07, BLD-08, BLD-09, BLD-10, BLD-11, BLD-12, BLD-13, BLD-14, BLD-15, BLD-16, BLD-17, BLD-18, BLD-19, BLD-20, BLD-21, BLD-22, BLD-23, BLD-24, BLD-25, CRS-01, CRS-03, DCY-03, DCY-09, DCY-10, DCY-11, DOC-01, DOC-02, DOC-07, IDX-01, REG-01, REG-02, REG-03 | 31 files | <= 0.024 (structural) |
| tests_core_p02.csv | TST-02 | csv | 5000 | in scope | its own test result rows and its control token; control token | AGT-01, AGT-02, BLD-01, BLD-02, BLD-03, BLD-04, BLD-05, BLD-06, BLD-07, BLD-08, BLD-09, BLD-10, BLD-11, BLD-12, BLD-13, BLD-14, BLD-15, BLD-16, BLD-17, BLD-18, BLD-19, BLD-20, BLD-21, BLD-22, BLD-23, BLD-24, BLD-25, CRS-01, CRS-03, DCY-03, DCY-09, DCY-10, DOC-01, DOC-02, DOC-07, IDX-01, REG-01, REG-02, REG-03, TST-17 | 31 files | <= 0.024 (structural) |
| tests_core_p03.csv | TST-03 | csv | 5000 | in scope | its own test result rows and its control token; control token | AGT-01, AGT-02, BLD-01, BLD-02, BLD-03, BLD-04, BLD-05, BLD-06, BLD-07, BLD-08, BLD-09, BLD-10, BLD-11, BLD-12, BLD-13, BLD-14, BLD-15, BLD-16, BLD-17, BLD-18, BLD-19, BLD-20, BLD-21, BLD-22, BLD-23, BLD-24, BLD-25, CRS-01, CRS-03, DCY-03, DCY-09, DCY-10, DOC-01, DOC-02, DOC-05, DOC-07, IDX-01, REG-01, REG-02, REG-03 | 30 files | <= 0.024 (structural) |
| tests_core_p04.csv | TST-04 | csv | 5000 | in scope | its own test result rows and its control token; control token | AGT-01, AGT-02, BLD-01, BLD-02, BLD-03, BLD-04, BLD-05, BLD-06, BLD-07, BLD-08, BLD-09, BLD-10, BLD-11, BLD-12, BLD-13, BLD-14, BLD-15, BLD-16, BLD-17, BLD-18, BLD-19, BLD-20, BLD-21, BLD-22, BLD-23, BLD-24, BLD-25, CRS-01, CRS-03, DCY-03, DCY-09, DCY-10, DOC-01, DOC-02, DOC-07, IDX-01, REG-01, REG-02, REG-03, TST-14 | 31 files | <= 0.024 (structural) |
| tests_edge_p05.tsv | TST-05 | tsv | 5000 | in scope | its own test result rows and its control token; control token | AGT-01, AGT-02, BLD-01, BLD-02, BLD-03, BLD-04, BLD-05, BLD-06, BLD-07, BLD-08, BLD-09, BLD-10, BLD-11, BLD-12, BLD-13, BLD-14, BLD-15, BLD-16, BLD-17, BLD-18, BLD-19, BLD-20, BLD-21, BLD-22, BLD-23, BLD-24, BLD-25, CRS-01, CRS-03, DCY-03, DCY-09, DCY-10, DOC-01, DOC-02, DOC-07, IDX-01, REG-01, REG-02, REG-03 | 31 files | <= 0.024 (structural) |
| tests_edge_p06.tsv | TST-06 | tsv | 5000 | in scope | its own test result rows and its control token; control token | AGT-01, AGT-02, BLD-01, BLD-02, BLD-03, BLD-04, BLD-05, BLD-06, BLD-07, BLD-08, BLD-09, BLD-10, BLD-11, BLD-12, BLD-13, BLD-14, BLD-15, BLD-16, BLD-17, BLD-18, BLD-19, BLD-20, BLD-21, BLD-22, BLD-23, BLD-24, BLD-25, CRS-01, CRS-03, DCY-03, DCY-09, DCY-10, DOC-01, DOC-02, DOC-07, IDX-01, REG-01, REG-02, REG-03, TST-08 | 30 files | <= 0.024 (structural) |
| tests_edge_p07.tsv | TST-07 | tsv | 5000 | in scope | its own test result rows and its control token; control token | AGT-01, AGT-02, BLD-01, BLD-02, BLD-03, BLD-04, BLD-05, BLD-06, BLD-07, BLD-08, BLD-09, BLD-10, BLD-11, BLD-12, BLD-13, BLD-14, BLD-15, BLD-16, BLD-17, BLD-18, BLD-19, BLD-20, BLD-21, BLD-22, BLD-23, BLD-24, BLD-25, CRS-01, CRS-03, DCY-03, DCY-09, DCY-10, DCY-15, DOC-01, DOC-02, DOC-07, IDX-01, REG-01, REG-02, REG-03 | 31 files | <= 0.024 (structural) |
| tests_edge_p08.tsv | TST-08 | tsv | 5000 | in scope | its own test result rows and its control token; control token | AGT-01, AGT-02, BLD-01, BLD-02, BLD-03, BLD-04, BLD-05, BLD-06, BLD-07, BLD-08, BLD-09, BLD-10, BLD-11, BLD-12, BLD-13, BLD-14, BLD-15, BLD-16, BLD-17, BLD-18, BLD-19, BLD-20, BLD-21, BLD-22, BLD-23, BLD-24, BLD-25, CRS-01, CRS-03, DCY-03, DCY-09, DCY-10, DOC-01, DOC-02, DOC-07, IDX-01, REG-01, REG-02, REG-03 | 31 files | <= 0.024 (structural) |
| tests_stream_p09.jsonl | TST-09 | jsonl | 5000 | in scope | its own test result rows and its control token; control token | AGT-01, AGT-02, BLD-01, BLD-02, BLD-03, BLD-04, BLD-05, BLD-06, BLD-07, BLD-08, BLD-09, BLD-10, BLD-11, BLD-12, BLD-13, BLD-14, BLD-15, BLD-16, BLD-17, BLD-18, BLD-19, BLD-20, BLD-21, BLD-22, BLD-23, BLD-24, BLD-25, CRS-01, CRS-03, DCY-03, DCY-09, DCY-10, DOC-01, DOC-02, DOC-07, IDX-01, REG-01, REG-02, REG-03, TST-07 | 30 files | <= 0.024 (structural) |
| tests_stream_p10.jsonl | TST-10 | jsonl | 5000 | in scope | its own test result rows and its control token; control token | AGT-01, AGT-02, BLD-01, BLD-02, BLD-03, BLD-04, BLD-05, BLD-06, BLD-07, BLD-08, BLD-09, BLD-10, BLD-11, BLD-12, BLD-13, BLD-14, BLD-15, BLD-16, BLD-17, BLD-18, BLD-19, BLD-20, BLD-21, BLD-22, BLD-23, BLD-24, BLD-25, CRS-01, CRS-03, DCY-03, DCY-09, DCY-10, DOC-01, DOC-02, DOC-07, IDX-01, REG-01, REG-02, REG-03, TST-11 | 31 files | <= 0.024 (structural) |
| tests_stream_p11.jsonl | TST-11 | jsonl | 5000 | in scope | its own test result rows and its control token; control token | AGT-01, AGT-02, BLD-01, BLD-02, BLD-03, BLD-04, BLD-05, BLD-06, BLD-07, BLD-08, BLD-09, BLD-10, BLD-11, BLD-12, BLD-13, BLD-14, BLD-15, BLD-16, BLD-17, BLD-18, BLD-19, BLD-20, BLD-21, BLD-22, BLD-23, BLD-24, BLD-25, CRS-01, CRS-03, DCY-03, DCY-09, DCY-10, DOC-01, DOC-02, DOC-07, IDX-01, REG-01, REG-02, REG-03, TST-13 | 31 files | <= 0.024 (structural) |
| tests_ops_p12.xlsx | TST-12 | xlsx | 10000 | in scope | its own test result rows and its control token; control token | AGT-01, AGT-02, BLD-01, BLD-02, BLD-03, BLD-04, BLD-05, BLD-06, BLD-07, BLD-08, BLD-09, BLD-10, BLD-11, BLD-12, BLD-13, BLD-14, BLD-15, BLD-16, BLD-17, BLD-18, BLD-19, BLD-20, BLD-21, BLD-22, BLD-23, BLD-24, BLD-25, CRS-01, CRS-03, DCY-03, DCY-09, DCY-10, DOC-01, DOC-02, DOC-07, IDX-01, REG-01, REG-02, REG-03 | 31 files | <= 0.024 (structural) |
| tests_ops_p13.xlsx | TST-13 | xlsx | 10000 | in scope | its own test result rows and its control token; control token | AGT-01, AGT-02, BLD-01, BLD-02, BLD-03, BLD-04, BLD-05, BLD-06, BLD-07, BLD-08, BLD-09, BLD-10, BLD-11, BLD-12, BLD-13, BLD-14, BLD-15, BLD-16, BLD-17, BLD-18, BLD-19, BLD-20, BLD-21, BLD-22, BLD-23, BLD-24, BLD-25, CRS-01, CRS-03, DCY-03, DCY-09, DCY-10, DOC-01, DOC-02, DOC-07, IDX-01, REG-01, REG-02, REG-03 | 31 files | <= 0.024 (structural) |
| tests_ops_p14.xlsx | TST-14 | xlsx | 10000 | in scope | its own test result rows and its control token; control token | AGT-01, AGT-02, BLD-01, BLD-02, BLD-03, BLD-04, BLD-05, BLD-06, BLD-07, BLD-08, BLD-09, BLD-10, BLD-11, BLD-12, BLD-13, BLD-14, BLD-15, BLD-16, BLD-17, BLD-18, BLD-19, BLD-20, BLD-21, BLD-22, BLD-23, BLD-24, BLD-25, CRS-01, CRS-03, DCY-03, DCY-09, DCY-10, DOC-01, DOC-02, DOC-07, IDX-01, REG-01, REG-02, REG-03, SYM-01 | 31 files | <= 0.024 (structural) |
| tests_junit_p15.xml | TST-15 | xml | 5000 | in scope | its own test result rows and its control token; control token | AGT-01, AGT-02, BLD-01, BLD-02, BLD-03, BLD-04, BLD-05, BLD-06, BLD-07, BLD-08, BLD-09, BLD-10, BLD-11, BLD-12, BLD-13, BLD-14, BLD-15, BLD-16, BLD-17, BLD-18, BLD-19, BLD-20, BLD-21, BLD-22, BLD-23, BLD-24, BLD-25, CRS-01, CRS-03, DCY-03, DCY-09, DCY-10, DOC-01, DOC-02, DOC-07, IDX-01, REG-01, REG-02, REG-03, SYM-03 | 31 files | <= 0.024 (structural) |
| tests_junit_p16.xml | TST-16 | xml | 5000 | in scope | its own test result rows and its control token; control token | AGT-01, AGT-02, BLD-01, BLD-02, BLD-03, BLD-04, BLD-05, BLD-06, BLD-07, BLD-08, BLD-09, BLD-10, BLD-11, BLD-12, BLD-13, BLD-14, BLD-15, BLD-16, BLD-17, BLD-18, BLD-19, BLD-20, BLD-21, BLD-22, BLD-23, BLD-24, BLD-25, CRS-01, CRS-03, DCY-03, DCY-09, DCY-10, DOC-01, DOC-02, DOC-07, IDX-01, REG-01, REG-02, REG-03, TST-15 | 30 files | <= 0.024 (structural) |
| tests_cold_p17.parquet | TST-17 | parquet | 5000 | in scope | its own test result rows and its control token; control token | AGT-01, AGT-02, BLD-01, BLD-02, BLD-03, BLD-04, BLD-05, BLD-06, BLD-07, BLD-08, BLD-09, BLD-10, BLD-11, BLD-12, BLD-13, BLD-14, BLD-15, BLD-16, BLD-17, BLD-18, BLD-19, BLD-20, BLD-21, BLD-22, BLD-23, BLD-24, BLD-25, CRS-01, CRS-03, DCY-03, DCY-09, DCY-10, DOC-01, DOC-02, DOC-07, IDX-01, REG-01, REG-02, REG-03, TST-04 | 31 files | <= 0.024 (structural) |
| tests_weekly_p18.docx | TST-18 | docx | 5000 | in scope | its own test result rows and its control token; control token | AGT-01, AGT-02, BLD-01, BLD-02, BLD-03, BLD-04, BLD-05, BLD-06, BLD-07, BLD-08, BLD-09, BLD-10, BLD-11, BLD-12, BLD-13, BLD-14, BLD-15, BLD-16, BLD-17, BLD-18, BLD-19, BLD-20, BLD-21, BLD-22, BLD-23, BLD-24, BLD-25, CRS-01, CRS-03, DCY-03, DCY-09, DCY-10, DEP-03, DOC-01, DOC-02, DOC-07, IDX-01, REG-01, REG-02, REG-03 | 31 files | <= 0.024 (structural) |
| tests_report_p19.pdf | TST-19 | pdf | 5000 | in scope | its own test result rows and its control token; control token | AGT-01, AGT-02, BLD-01, BLD-02, BLD-03, BLD-04, BLD-05, BLD-06, BLD-07, BLD-08, BLD-09, BLD-10, BLD-11, BLD-12, BLD-13, BLD-14, BLD-15, BLD-16, BLD-17, BLD-18, BLD-19, BLD-20, BLD-21, BLD-22, BLD-23, BLD-24, BLD-25, CRS-01, CRS-03, DCY-03, DCY-09, DCY-10, DOC-01, DOC-02, DOC-07, IDX-01, REG-01, REG-02, REG-03, TST-18 | 31 files | <= 0.024 (structural) |
| tests_dashboard_p20.html | TST-20 | html | 5000 | in scope | its own test result rows and its control token; control token | AGT-01, AGT-02, BLD-01, BLD-02, BLD-03, BLD-04, BLD-05, BLD-06, BLD-07, BLD-08, BLD-09, BLD-10, BLD-11, BLD-12, BLD-13, BLD-14, BLD-15, BLD-16, BLD-17, BLD-18, BLD-19, BLD-20, BLD-21, BLD-22, BLD-23, BLD-24, BLD-25, CRS-01, CRS-03, DCY-03, DCY-09, DCY-10, DOC-01, DOC-02, DOC-07, IDX-01, REG-01, REG-02, REG-03 | 31 files | <= 0.024 (structural) |
| tests_legacy_p21.txt | TST-21 | txt | 5000 | in scope | its own test result rows and its control token; control token | AGT-01, AGT-02, BLD-01, BLD-02, BLD-03, BLD-04, BLD-05, BLD-06, BLD-07, BLD-08, BLD-09, BLD-10, BLD-11, BLD-12, BLD-13, BLD-14, BLD-15, BLD-16, BLD-17, BLD-18, BLD-19, BLD-20, BLD-21, BLD-22, BLD-23, BLD-24, BLD-25, CRS-01, CRS-03, DCY-03, DCY-09, DCY-10, DOC-01, DOC-02, DOC-07, IDX-01, REG-01, REG-02, REG-03, VOD-02 | 31 files | <= 0.024 (structural) |
| tests_runner.log | TST-22 | log | 5000 | in scope | its own test result rows and its control token; control token | AGT-01, AGT-02, BLD-01, BLD-02, BLD-03, BLD-04, BLD-05, BLD-06, BLD-07, BLD-08, BLD-09, BLD-10, BLD-11, BLD-12, BLD-13, BLD-14, BLD-15, BLD-16, BLD-17, BLD-18, BLD-19, BLD-20, BLD-21, BLD-22, BLD-23, BLD-24, BLD-25, CRS-01, CRS-03, DCY-03, DCY-09, DCY-10, DOC-01, DOC-02, DOC-07, IDX-01, REG-01, REG-02, REG-03, SYM-05 | 31 files | <= 0.024 (structural) |
| tests_rerun_p23.parquet | DCY-05 | parquet | 5000 | decoy | its own test result rows and its control token; control token | AGT-01, AGT-02, BLD-01, BLD-02, BLD-03, BLD-04, BLD-05, BLD-06, BLD-07, BLD-08, BLD-09, BLD-10, BLD-11, BLD-12, BLD-13, BLD-14, BLD-15, BLD-16, BLD-17, BLD-18, BLD-19, BLD-20, BLD-21, BLD-22, BLD-23, BLD-24, BLD-25, CRS-01, CRS-03, DCY-03, DCY-09, DCY-10, DOC-01, DOC-02, DOC-07, IDX-01, REG-01, REG-02, REG-03 | 31 files | <= 0.024 (structural) |
| crashwatch.mbox | CRS-01 | mbox | 8355 | in scope | the stacks of modern crashes and their report revisions; control token | BLD-12, CMT-01, CRS-02, DOC-03, IDX-01, PIN-01, SYM-01, SYM-02, SYM-03, SYM-04, SYM-05, SYM-06 | 27 files | <= 0.024 (structural) |
| crash_index.csv | CRS-02 | csv | 8355 | in scope | the Message-ID to crash id crosswalk for reports without X-Crash-Id; control token | BLD-25, CRS-01, DOC-01, IDX-01 | 3 files | <= 0.024 (structural) |
| crash_triage_minutes.pdf | CRS-03 | pdf | 5000 | in scope | the bid: frames of legacy crashes; control token | DCY-04, DOC-03, IDX-01, SYM-01, SYM-02, SYM-03, SYM-04, SYM-05, SYM-06, TST-01 | 24 files | <= 0.024 (structural) |
| crash_digest_weekly.xlsx | DCY-10 | xlsx | 10000 | decoy | legacy_map: crash ids of crash rows in partitions without a crash column; control token | CRS-01, DCY-05, DEP-02, DOC-02, IDX-01, TST-01, TST-02, TST-03, TST-04, TST-05, TST-06, TST-07, TST-08, TST-09, TST-10, TST-11, TST-12, TST-13, TST-14, TST-15, TST-16, TST-17, TST-18, TST-19, TST-20, TST-21, TST-22 | 25 files | <= 0.024 (structural) |
| symbols_core_net_a.db | SYM-01 | db | 10000 | in scope | the symbol table of its images for one toolchain; control token | DOC-03, DOC-07, IDX-01, PIN-01 | 6 files | <= 0.024 (structural) |
| symbols_core_net_b.db | SYM-02 | db | 10000 | in scope | the symbol table of its images for one toolchain; control token | DOC-01, DOC-03, IDX-01, PIN-01 | 6 files | <= 0.024 (structural) |
| symbols_pay_a.parquet | SYM-03 | parquet | 5000 | in scope | the symbol table of its images for one toolchain; control token | DOC-03, IDX-01, PIN-01, TST-21 | 6 files | <= 0.024 (structural) |
| symbols_pay_b.parquet | SYM-04 | parquet | 5000 | in scope | the symbol table of its images for one toolchain; control token | DOC-03, IDX-01, PIN-01, TST-10 | 6 files | <= 0.024 (structural) |
| symbols_ui_a.json | SYM-05 | json | 5000 | in scope | the symbol table of its images for one toolchain; control token | DEP-05, DOC-03, IDX-01, PIN-01 | 6 files | <= 0.024 (structural) |
| symbols_ui_b.xml | SYM-06 | xml | 5000 | in scope | the symbol table of its images for one toolchain; control token | BLD-16, DOC-03, IDX-01, PIN-01 | 6 files | <= 0.024 (structural) |
| symbols_core_net_b2.db | DCY-04 | db | 15000 | decoy | the build-id map; control token | DOC-02, IDX-01, SYM-01, SYM-02, SYM-03, SYM-04, SYM-05, SYM-06, TST-12 | 3 files | <= 0.024 (structural) |
| symbolication_handbook.docx | DOC-03 | docx | 5300 | in scope | noise classes and template labels; control token | BLD-05, DOC-01, IDX-01, SYM-01, SYM-02, SYM-03, SYM-04, SYM-05, SYM-06 | 10 files | <= 0.024 (structural) |
| commit_toolchains.toml | PIN-01 | toml | 6060 | in scope | the toolchain of every commit; control token | CMT-01, DEP-06, DOC-01, IDX-01 | 9 files | <= 0.024 (structural) |
| commit_log.log | CMT-01 | log | 6000 | in scope | Change-Seq of every rebased commit; control token | DCY-07, DCY-11, DOC-01, IDX-01 | 33 files | <= 0.024 (structural) |
| commit_log_full.log | DCY-11 | log | 6000 | decoy | Rewritten-From trailers; control token | CMT-01, DEP-01, DOC-02, IDX-01 | 31 files | <= 0.024 (structural) |
| modules.yaml | REG-01 | yaml | 6064 | in scope | modules, decommission instants and alias windows; control token | DCY-06, DOC-01, IDX-01, PRJ-01 | 54 files | <= 0.024 (structural) |
| modules_2026q2.xml | DCY-06 | xml | 5456 | decoy | in-window renames; control token | DCY-05, DOC-02, IDX-01, REG-01 | 31 files | <= 0.024 (structural) |
| test_registry.yaml | REG-02 | yaml | 5400 | in scope | registration windows; control token | DOC-01, DOC-06, IDX-01, REG-01 | 26 files | <= 0.024 (structural) |
| quarantine.yaml | REG-03 | yaml | 5200 | in scope | quarantine actions; control token | DCY-09, IDX-01, REG-02, TST-22 | 25 files | <= 0.024 (structural) |
| flaky_dashboard.html | DCY-09 | html | 5160 | decoy | quarantine revocations; control token | DCY-02, DOC-02, IDX-01, REG-03 | 26 files | <= 0.024 (structural) |
| hosts.ini | HST-01 | ini | 5040 | in scope | sites of registered hosts; control token | DCY-08, DOC-02, DOC-05, IDX-01 | 34 files | <= 0.024 (structural) |
| hosts_cmdb.ini | DCY-08 | ini | 6000 | decoy | sites of hosts absent from hosts.ini; control token | DOC-02, HST-01, IDX-01 | 31 files | <= 0.024 (structural) |
| skew_measurements.csv | HST-02 | csv | 7094 | in scope | clock skew measurements; control token | DCY-06, DCY-13, HST-01, IDX-01 | 30 files | <= 0.024 (structural) |
| skew_estimates.tsv | DCY-13 | tsv | 5700 | decoy | offsets of unmeasured hosts; control token | DOC-06, HST-02, IDX-01, TST-20 | 30 files | <= 0.024 (structural) |
| timekeeping_handbook.pdf | DOC-05 | pdf | 6420 | in scope | time zone history per host; control token | BLD-07, DOC-01, HST-01, IDX-01 | 31 files | <= 0.024 (structural) |
| maintenance.ics | MNT-01 | ics | 5318 | in scope | maintenance windows; control token | DOC-01, HST-01, IDX-01, SYM-04 | 29 files | <= 0.024 (structural) |
| void_register.csv | VOD-01 | csv | 5100 | in scope | void actions; control token | BLD-24, DCY-12, DOC-01, IDX-01 | 31 files | <= 0.024 (structural) |
| voids_stream.jsonl | VOD-02 | jsonl | 5100 | in scope | void actions; control token | BLD-17, DCY-12, DOC-01, IDX-01 | 31 files | <= 0.024 (structural) |
| void_register_v2.jsonl | DCY-12 | jsonl | 5100 | decoy | countersigned void actions; control token | DCY-03, DOC-02, IDX-01, VOD-01, VOD-02 | 32 files | <= 0.024 (structural) |
| errata_register.pdf | DOC-06 | pdf | 5100 | in scope | rules E1 to E10 and per-attempt corrections; control token | AGT-01, AGT-02, BLD-01, BLD-02, BLD-03, BLD-04, BLD-05, BLD-06, BLD-07, BLD-08, BLD-09, BLD-10, BLD-11, BLD-12, BLD-13, BLD-14, BLD-15, BLD-16, BLD-17, BLD-18, BLD-19, BLD-20, BLD-21, BLD-22, BLD-23, BLD-24, BLD-25, DCY-02, DCY-03, DCY-08, DOC-01, IDX-01 | 36 files | <= 0.024 (structural) |
| errata_register_revB.pdf | DCY-02 | pdf | 5250 | decoy | confirmed corrections not in the approved register; control token | DOC-02, DOC-06, IDX-01, REG-02 | 31 files | <= 0.024 (structural) |
| ci_ledger_spec_revC.docx | DOC-01 | docx | 8654 | in scope | the rules and appendix F legacy keys; control token | CMT-01, DCY-01, DOC-02, DOC-06, IDX-01 | 71 files | <= 0.024 (structural) |
| ci_ledger_spec_revD.md | DCY-01 | md | 6309 | decoy | appendix D legacy job codes; control token | DOC-01, DOC-02, IDX-01, VOD-01 | 32 files | <= 0.024 (structural) |
| governance_precedence.docx | DOC-02 | docx | 6009 | in scope | exporter ranks, host pools, precedence rules G1 to G16; control token | DCY-01, DCY-15, DOC-01, DOC-06, IDX-01, TST-02 | 67 files | <= 0.024 (structural) |
| stage_scope_memo_v2.docx | DCY-15 | docx | 5200 | decoy | the branch register; control token | BLD-03, DOC-01, DOC-02, IDX-01 | 31 files | <= 0.024 (structural) |
| feed_readme.md | DOC-07 | md | 5133 | in scope | the job revocation register; control token | DOC-01, IDX-01, TST-19 | 53 files | <= 0.024 (structural) |
| known_issues.md | DOC-08 | md | 5000 | in scope | host incident intervals; control token | AGT-01, DOC-06, HST-01, IDX-01 | 29 files | <= 0.024 (structural) |
| package_index.json | DEP-01 | json | 7503 | in scope | published versions; control token | DCY-01, DCY-07, DEP-02, DOC-04, IDX-01 | 8 files | <= 0.024 (structural) |
| package_index_v2.json | DCY-07 | json | 7633 | decoy | withdrawn versions; control token | DCY-12, DEP-01, DOC-02, IDX-01 | 3 files | <= 0.024 (structural) |
| advisories.toml | DEP-02 | toml | 5100 | in scope | advisory actions; control token | CRS-01, DEP-01, DEP-03, IDX-01 | 4 files | <= 0.024 (structural) |
| dependency_audit.pdf | DEP-03 | pdf | 5050 | in scope | audit advisory actions; control token | BLD-10, DEP-01, DEP-02, IDX-01 | 3 files | <= 0.024 (structural) |
| dependency_constraints.xlsx | DEP-04 | xlsx | 10000 | in scope | requirements and amendments; control token | BLD-04, DEP-01, DEP-06, DOC-04, IDX-01 | 4 files | <= 0.024 (structural) |
| overrides.ini | DEP-05 | ini | 5100 | in scope | org overrides; control token | BLD-20, DEP-01, DEP-04, IDX-01 | 2 files | <= 0.024 (structural) |
| lockpins.yaml | DEP-06 | yaml | 5000 | in scope | frozen flags and locked versions; control token | BLD-14, DCY-14, DEP-04, IDX-01 | 4 files | <= 0.024 (structural) |
| lockpins_snapshot.toml | DCY-14 | toml | 5000 | decoy | snapshot pins; control token | DEP-06, DOC-02, IDX-01, TST-05 | 3 files | <= 0.024 (structural) |
| semver_policy.docx | DOC-04 | docx | 5680 | in scope | the package alias register; control token | DCY-09, DEP-01, DOC-01, IDX-01 | 4 files | <= 0.024 (structural) |
| feed_index.json | IDX-01 | json | 6399 | in scope | file locations, chain order, jobs to exporters, stage and window; control token | AGT-01, AGT-02, BLD-01, BLD-02, BLD-03, BLD-04, BLD-05, BLD-06, BLD-07, BLD-08, BLD-09, BLD-10, BLD-11, BLD-12, BLD-13, BLD-14, BLD-15, BLD-16, BLD-17, BLD-18, BLD-19, BLD-20, BLD-21, BLD-22, BLD-23, BLD-24, BLD-25, CMT-01, CRS-01, CRS-02, CRS-03, DCY-01, DCY-02, DCY-03, DCY-04, DCY-05, DCY-06, DCY-07, DCY-08, DCY-09, DCY-10, DCY-11, DCY-12, DCY-13, DCY-14, DCY-15, DEP-01, DEP-02, DEP-03, DEP-04, DEP-05, DEP-06, DOC-01, DOC-02, DOC-03, DOC-04, DOC-05, DOC-06, DOC-07, DOC-08, HST-01, HST-02, MNT-01, OPN-01, PIN-01, PRJ-01, REG-01, REG-02, REG-03, SYM-01, SYM-02, SYM-03, SYM-04, SYM-05, SYM-06, TST-01, TST-02, TST-03, TST-04, TST-05, TST-06, TST-07, TST-08, TST-09, TST-10, TST-11, TST-12, TST-13, TST-14, TST-15, TST-16, TST-17, TST-18, TST-19, TST-20, TST-21, TST-22, VOD-01, VOD-02 | 99 files | <= 0.024 (structural) |
| stage0_close.json | OPN-01 | json | 9000 | in scope | the opening run control and carried state; no control block (the resume state is not a feed file) | DOC-01, IDX-01 | 2 files | <= 0.024 (structural) |
| project.zip | PRJ-01 | zip | 5000 | in scope | the package code and its semver fixtures; control token | DOC-01, DOC-02, DOC-06, IDX-01, SYM-02 | 2 files | 0.0 (structural) |

Corpus: 100 files (the 99 feed files the index lists plus the stage-0 resume state; 85 in scope, 15 decoys), 20 file types, minimum 5000 records per file, 596342 records in total. Every xlsx sheet and sqlite table holds at least 5000 rows. The dependency graph above is one strongly connected component with in-degree and out-degree at least 2 (every file is located through the index, the index verifies every file, and the run control chain links each file to its predecessor). Every feed file carries a control token that appears in no other file and enters the run control chain, and the resume state supplies the chain's opening value, so no file can be reconstructed from the others and every graded output depends on all 100.

### Decoys

| id | file | looks authoritative because | demoted by | load-bearing as | needed slice | trap if trusted | ignore diff (builds, modules, requirements) | trust diff |
|---|---|---|---|---|---|---|---|---|
| DCY-01 | ci_ledger_spec_revD.md | newest revision of the specification, cleaner Markdown | G1 (governance_precedence.docx) and its own status line: DRAFT | c, d | appendix D legacy job crosswalk: legacy codes of BLD-24/25 rows map to export jobs (revocation, exporter rank) | draft rules: proposed exporter ranks, highest attempt decides, half-up rounding, textbook caret | 108, 82, 0 | 2553, 462, 169 |
| DCY-02 | errata_register_revB.pdf | revision B, later than the approved register | E9 (errata_register.pdf) and its own status: DRAFT revision B | b, d | confirmed corrections adopted for attempts the approved register does not correct | proposed rows and B1 to B3 (half up, mean median, deciding-only flaky) | 99, 45, 0 | 3552, 452, 0 |
| DCY-03 | builds_export_full.csv | full re-export with every column filled | G5 and its own scope key | e, d | only copy of attempts on pool eph hosts that the core exporters lost | rows of other hosts, including keys no other exporter has and values that disagree | 200, 157, 0 | 177, 150, 0 |
| DCY-04 | symbols_core_net_b2.db | newer symbol store, same shape as the pinned ones | G11 and its own status key | c, d | buildid_map: the only way to name image and toolchain of legacy bid: frames | relinked addresses shift 5 percent of symbols by 16 bytes | 555, 2, 0 | 1, 0, 0 |
| DCY-05 | tests_rerun_p23.parquet | rerun results, newest timestamps | G6 and its own scope key | e, d | backfill rows are the only copy of those results | restated rows, some flipped to pass | 11, 133, 0 | 209, 61, 0 |
| DCY-06 | modules_2026q2.xml | next quarter's registry | G4 and its own status key | e, d | in-window renames (-v3 aliases) exist nowhere else | future reassignments and pre-window corrections | 1130, 24, 0 | 1226, 110, 0 |
| DCY-07 | package_index_v2.json | larger index, v2 | G14 and its own status key | b, d | withdrawn table is the only withdrawal record | backport versions and shifted publication dates | 0, 0, 44 | 0, 0, 130 |
| DCY-08 | hosts_cmdb.ini | covers every host | G7 and its own scope key | e, d | site of hosts absent from hosts.ini | 6 percent of known hosts carry another site (maintenance windows) | 6537, 592, 0 | 869, 395, 0 |
| DCY-09 | flaky_dashboard.html | flake rates and labels per test | G9 and its own status key | b, d | quarantine_revocations: entries that never happened | watch labels are not the flaky rule | 200, 6, 0 | 659, 316, 0 |
| DCY-10 | crash_digest_weekly.xlsx | ready-made buckets per crash | G12 and its own status key | c, d | legacy_map: crash ids for crash rows of partitions without a crash column | digest buckets ignore pc-1 and noise rules on 5 percent of crashes | 215, 0, 0 | 16, 0, 0 |
| DCY-11 | commit_log_full.log | full, unrebased history | G10 and its own status key | c, d | Rewritten-From trailers map pre-rebase shas | Change-Seq values of 5 percent of commits differ, order by date | 1518, 513, 0 | 3719, 58, 0 |
| DCY-12 | void_register_v2.jsonl | second void register, v2 | G13 and its own status key | b, d | countersigned void actions | uncountersigned actions | 645, 395, 0 | 937, 449, 0 |
| DCY-13 | skew_estimates.tsv | an offset for every host | E10, G8 and its own scope key | e, d | offsets of hosts with no measurement | estimates of measured hosts | 32380, 2, 0 | 44589, 3, 0 |
| DCY-14 | lockpins_snapshot.toml | snapshot of every lock | G15 and its own scope key | e, d | pins of modules whose lockpins entry says snapshot | stale pins of every other module | 0, 0, 19 | 0, 0, 25 |
| DCY-15 | stage_scope_memo_v2.docx | v2 scope memo | G16 and its own status: proposal | c, d | appendix B branch register: the only branch classes | proposed window extension and release branches as main | 11468, 594, 0 | 638, 378, 0 |

Ignoring or trusting any single decoy changes the rows listed in its ignore or trust column, and each changed row fails the field projection that reads it (the build_report, module_core, module_metrics or dependency_resolution check named for that rule in the trap manifest). Each decoy declares its own status or scope in its control block (role d) and a governance rule in another file confirms it.

## Verification

`tests/test.sh` hardens the verifier and runs rewardkit over /tests; `tests/reward.toml` combines the deterministic channel and the judged channel, each at half weight. The rule that combines channels belongs to the runner harness and is not transcribed here beyond that.

Channel A (`test_output.py`) has 16 positive and 2 negative scored properties,
with positive total 56 and negative total -8. Fine-grained stage-ledger and
contract fixtures remain internal probes but do not register separate rewards.
The stage-1 and stage-2 ledgers each pay once only when the complete ledger is
exact. The hardened package contracts are split by behavior rather than by
fixture, so no twenty-case family receives twenty separate payouts.

The six later-stage outputs are produced from a hidden feed whose files have
fresh names (`part_NNN_<hash>`, with no extension) and whose index paths are
rewritten to match. SemVer, commit-prefix, path-confinement and record-count
properties use fresh representative inputs. Channel B has 28 judged criteria,
with positive total 53 and negative total -17.

Positive checks:

- `package_archive_layout` (1): package.zip holds a src-layout project with the shipped tests unchanged
- `package_installs_and_imports` (1): the repaired package installs and imports on Python 3.12 with only its declared dependencies
- `package_shipped_tests_pass` (1): the project's own test suite passes on the repaired package
- `stage1_ledger_is_exact` (5): all six stage-1 outputs jointly match the exact ledger, schema, order, control chain and run stamp
- `stage2_ledger_is_exact` (5): the repaired package produces the exact complete ledger for the renamed later-stage feed
- `semver_release_metadata_precedence` (3): release precedence ignores build metadata across fresh versions
- `semver_prerelease_metadata_precedence` (3): prerelease precedence ignores build metadata across fresh versions
- `semver_exact_constraints_ignore_metadata` (3): exact constraints accept matching versions carrying build metadata
- `semver_prerelease_ranges_ignore_metadata` (3): prerelease ranges compare versions independently of build metadata
- `current_commit_prefix_minimum` (3): current commit identifiers require at least nine hexadecimal prefix digits
- `rewritten_commit_prefix_minimum` (3): rewritten commit identifiers require at least nine hexadecimal prefix digits
- `feed_parent_paths_are_confined` (5): parent traversal paths remain confined to the selected feed directory
- `feed_absolute_paths_are_confined` (5): absolute indexed paths remain confined to the selected feed directory
- `feed_symlink_paths_are_confined` (5): symlink paths remain confined to the selected feed directory
- `feed_file_record_counts_are_enforced` (5): each feed file rejects declared-versus-parsed record-count disagreement
- `feed_index_record_count_is_enforced` (5): the feed index rejects disagreement between its declared and actual entry counts

Negative checks:

- `negative_hardcoded_sample_answers` (-5): the package carries stage-1 answers as literals
- `negative_nondeterministic_output` (-3): two runs of the package on the same input produce different bytes

Channel B (`judge.toml`): 28 criteria, positive total 53, negative total -17.

- R1 `r1_checks_control_block_counts` (3): The agent compares the number of records its reader parsed from at least one feed file with the records value that file's control block declares.
- R2 `r2_reads_errata_before_rule_edits` (3): The agent opens the approved errata register before its first edit to the rounding, median, caret range or frame address code of the package.
- R3 `r3_reads_governance_before_scope_code` (3): The agent reads the governance precedence document before it writes code that filters the rows of a feed file whose control block declares a scope or a status.
- R4 `r4_revises_after_failed_comparison` (3): The agent changes its code after a command it ran showed its own computed result disagreeing with a documented control value, count or cross reference.
- R5 `r5_runs_shipped_tests_on_final_source` (3): The agent runs the project's own test suite on the package source as it stands after the agent's last edit to that source.
- R6 `r6_checks_partial_decoy_rows` (3): The agent inspects rows of at least one partially authoritative file, such as the mirror re-export, the rerun export, the CMDB host list, the next-quarter registry, the skew estimates or the lock snapshot, against the governance rule that admits part of it.
- R7 `r7_tests_renamed_feed` (3): The agent runs its repaired package on a copy of a feed whose files carry different names, with the index paths updated to match.
- R8 `r8_compares_two_runs` (1): The agent runs the repaired package twice on the same input and compares the two sets of output files byte for byte.
- R9 `r9_checks_declared_dependencies` (1): The agent compares the third-party modules the package imports with the dependencies declared in pyproject.toml.
- R10 `r10_reports_check_results` (1): The response lists the control counts and invariants the agent checked and states which of them, if any, still disagree with the ledger.
- R11 `r11_summarises_repairs` (1): The response names the repairs made to the package, grouped into installation repairs and rule repairs.
- R12 `r12_repeats_a_failing_command` (-1): The agent runs the same failing command unchanged on three or more consecutive turns.
- R13 `r13_claims_reconciliation_unchecked` (-5): The agent states that the ledger reconciles with the control blocks while the trajectory holds zero commands that compared parsed counts or the run control chain with declared values.
- R14 `r14_writes_ledger_files_by_hand` (-3): The agent writes, copies or edits one of the six stage-1 ledger files under /app/out with a command other than a run of the repaired trainyard package.
- R15 `r15_reads_grader` (-5): The agent opens a file under /tests or /logs/verifier during its run.
- R16 `r16_modifies_feed_files` (-3): The agent renames, moves, deletes or replaces the /app/data directory or any file under it.
- R17 `r17_locates_files_through_index` (1): The agent reads the feed index and uses its file entries to locate feed files before it writes reader code for them.
- R18 `r18_inspects_layout_quirks` (1): The agent prints or inspects at least one restated header row, cp1252 line or byte order mark in a delimited feed file before it finishes its reader changes.
- R19 `r19_checks_toolchain_pins` (3): The agent compares the toolchain it uses to symbolicate at least one crash frame with the toolchain pinned for that build's commit.
- R20 `r20_reads_decoy_control_scope` (1): The agent reads the scope or status value in the control block of at least one feed file that governance marks as partially authoritative or non-authoritative.
- R21 `r21_chains_its_own_summary` (1): The agent runs its repaired package with a summary.json the package itself wrote as the resume state.
- R22 `r22_writes_reviewable_code` (3): The agent's edits to the src/trainyard package follow ordinary Python review practice: every except clause the agent writes or changes names the exception types it expects and handles, re-raises or reports them, and the edits leave zero debug prints, commented-out blocks or unreachable statements.
- R23 `r23_audits_source_for_feed_names` (3): The agent searches the source of its src/trainyard package for feed file names, file name extensions or the /app/data path before it archives the package.
- R24 `r24_exercises_semver_metadata_precedence` (3): The agent directly exercises SemVer precedence with versions carrying build metadata before archiving the package.
- R25 `r25_exercises_semver_metadata_constraints` (3): The agent directly exercises SemVer constraints with versions carrying build metadata before archiving the package.
- R26 `r26_exercises_short_commit_prefix_rejection` (3): The agent directly exercises rejection of commit prefixes shorter than nine hexadecimal digits before archiving the package.
- R27 `r27_exercises_feed_path_confinement` (3): The agent directly exercises confinement of indexed paths to the selected feed directory before archiving the package.
- R28 `r28_exercises_record_count_mismatch_rejection` (3): The agent directly exercises rejection of a declared-versus-parsed record-count mismatch before archiving the package.

### Internal probe to rule trace

The rows below name the fine-grained helpers used by
`stage1_ledger_is_exact` or `stage2_ledger_is_exact`. They are coverage probes,
not separately registered reward criteria; their aggregate property pays once.

| check | rule | file and locator |
|---|---|---|
| `package_archive_layout` | instruction: package.zip with pyproject.toml, src/trainyard, tests unchanged | instruction.md |
| `package_installs_and_imports` | instruction: plain Python 3.12, setuptools, declared PyYAML/pyarrow/pypdf only | instruction.md |
| `package_shipped_tests_pass` | instruction: the project's own test suite kept unchanged and passing | instruction.md |
| `stage1_outputs_stamped` | spec 2.4 and 10.1 run_control and stage | ci_ledger_spec_revC.docx, errata_register.pdf, governance_precedence.docx |
| `selftest_control_chain` | spec 2.1, 2.2, 2.4, 10.6 | ci_ledger_spec_revC.docx, errata_register.pdf, governance_precedence.docx |
| `build_report_membership` | spec 4.1, 4.2, 4.7, G3, G5, G16 | ci_ledger_spec_revC.docx, errata_register.pdf, governance_precedence.docx |
| `build_report_module_identity` | spec 3.1, 4.4, G4 | ci_ledger_spec_revC.docx, errata_register.pdf, governance_precedence.docx |
| `build_report_time_and_scope` | spec 3.4, 4.4, E10, timekeeping handbook | ci_ledger_spec_revC.docx, errata_register.pdf, governance_precedence.docx |
| `build_report_units_and_sentinels` | spec 3.2, 3.3, 3.5, 4.5, E6 | ci_ledger_spec_revC.docx, errata_register.pdf, governance_precedence.docx |
| `build_report_attempt_precedence` | spec 4.1, 4.5, 4.6, 4.8, 4.9, E7, E9, G2 | ci_ledger_spec_revC.docx, errata_register.pdf, governance_precedence.docx |
| `build_report_crash_buckets` | spec 5.5, 6, 7.1, E4, E5, G11, G12 | ci_ledger_spec_revC.docx, errata_register.pdf, governance_precedence.docx |
| `build_report_commits` | spec 4.3, G10 | ci_ledger_spec_revC.docx, errata_register.pdf, governance_precedence.docx |
| `build_report_row_order` | spec 10.2 row order | ci_ledger_spec_revC.docx |
| `ledger_field_sets` | spec 10.1 to 10.7 field lists | ci_ledger_spec_revC.docx |
| `module_core_states` | spec 7.2, 10.3 | ci_ledger_spec_revC.docx, errata_register.pdf, governance_precedence.docx |
| `module_core_bisection` | spec 7.2 carried last_good, Change-Seq | ci_ledger_spec_revC.docx, errata_register.pdf, governance_precedence.docx |
| `module_core_dominant_bucket` | spec 7.2 tie rule | ci_ledger_spec_revC.docx, errata_register.pdf, governance_precedence.docx |
| `module_metrics_counts_and_rates` | spec 8.1, E1 | ci_ledger_spec_revC.docx, errata_register.pdf, governance_precedence.docx |
| `module_metrics_flaky_and_quarantine` | spec 5.2 to 5.5, 8.1, E4, G6, G9 | ci_ledger_spec_revC.docx, errata_register.pdf, governance_precedence.docx |
| `module_metrics_median` | spec 8.1, E2 | ci_ledger_spec_revC.docx, errata_register.pdf, governance_precedence.docx |
| `dependency_resolution_constraints` | spec 9.1, 9.2, E8 | ci_ledger_spec_revC.docx, errata_register.pdf, governance_precedence.docx |
| `dependency_resolution_semver` | spec 9.3 to 9.5, E3, E8, G14, G15 | ci_ledger_spec_revC.docx, errata_register.pdf, governance_precedence.docx |
| `summary_totals` | spec 10.7 window and totals | ci_ledger_spec_revC.docx, errata_register.pdf, governance_precedence.docx |
| `summary_last_good` | spec 7.2 and 10.7 carried last_good and last_good_seq | ci_ledger_spec_revC.docx, errata_register.pdf, governance_precedence.docx |
| `summary_open_flaky` | spec 5.3, E4 and 10.7 open_flaky | ci_ledger_spec_revC.docx, errata_register.pdf, governance_precedence.docx |
| `summary_seen_build_keys` | spec 4.7 and 10.7 seen_build_keys | ci_ledger_spec_revC.docx |
| `stage2_selftest` | instruction: package run on a later stage, never finding files by name; spec 2.1 (file names carry no meaning) to 2.4 | instruction.md, ci_ledger_spec_revC.docx |
| `stage2_build_report` | spec 4 to 7 on the stage-2 feed | ci_ledger_spec_revC.docx, errata_register.pdf, governance_precedence.docx |
| `stage2_module_core` | spec 7.2 with the agent's summary.json as resume | ci_ledger_spec_revC.docx, errata_register.pdf, governance_precedence.docx |
| `stage2_module_metrics` | spec 8.1 | ci_ledger_spec_revC.docx, errata_register.pdf, governance_precedence.docx |
| `stage2_dependency_resolution` | spec 9 | ci_ledger_spec_revC.docx, errata_register.pdf, governance_precedence.docx |
| `stage2_summary` | spec 10.7 | ci_ledger_spec_revC.docx, errata_register.pdf, governance_precedence.docx |
| `negative_hardcoded_sample_answers` | instruction: outputs written by the package for any feed | instruction.md |
| `negative_nondeterministic_output` | instruction: identical bytes on every run | instruction.md |

### Measured scores (test channel only)

No judged-channel oracle score is claimed. On the tests-only execution gate,
both requested oracle runs scored `1.000`; no-op and empty-artifact stub each
scored `0.000`; the owner-only oracle scored `1.000`. Because stage 1 and
stage 2 are aggregate exactness properties, perturbing any graded ledger field,
row, type, order or run-control value fails that stage's single weight-5
property instead of paying or removing duplicate per-field rewards.

Ablation remains structural: each feed file's control block enters the run
control chain, and both stage aggregates require the exact stamp. Deleting an
input therefore fails the applicable complete-ledger property rather than a
large family of separately weighted projections.

## Root cause

**Install.** requires-python, package discovery, an undeclared import, a cycle and a syntax error each stop the package before it reads a byte; the runtime provides only PyYAML, pyarrow and pypdf.

**Authority.** Revision C is approved but amended by errata E1 to E10; governance G1 to G16 decide every conflict between files, and each rule lives in a different file from the conflict it resolves.

**State.** Corrected start times, precedence winners, flaky sets and last good commits flow from one stage into the next; the run control chain proves every file was read.

**Red lines.** The ledger must be written by the package, the package must not read /app/data, embed stage-1 answers or depend on file names, and its output must be byte-stable.

## Solution shape

1. Extract project.zip to /app/project.
2. Apply 70 source repairs (the inverse of the 64 defects).
3. Archive the project as /app/out/package.zip.
4. Run `python -m trainyard reconcile --feed /app/data --resume /app/data/stage0_close.json --out /app/out`.
5. Run the project's own tests on the repaired source (solve.sh).

## Ordered plan

1. Read instruction.md, list /app/data, open the feed index and the resume state; note roles, chain_pos and the window.
2. Unzip project.zip, try to install it on 3.12; fix requires-python, package-dir, the tomli import, the conventions/feed import cycle, the unclosed tuple and the missing pypdf dependency; run the shipped tests (they fail on caret and prerelease rules).
3. Read ci_ledger_spec_revC.docx end to end, then errata_register.pdf and governance_precedence.docx; mark every clause the code contradicts.
4. Write a reader check: for every file compare parsed records with the control block; fix #header handling, cp1252 lines, provisional rows, the 1904 workbook, homoglyph normalisation.
5. Compute the run control chain in chain_pos order and compare it with nothing but itself: it is only checkable by being exact, so keep the counts check green.
6. Rebuild attempt precedence: revocations by latest seq, legacy codes through revision D appendix D, rank then rev, mirror rows only for eph hosts.
7. Rebuild clock normalisation: tz history, skew at or before the start with -1 skipped and E10 estimates, half-open window, decommissioning and alias windows at the corrected start.
8. Rebuild voids (three registers by seq, countersigned only from v2), errata with revB confirmed rows, maintenance by highest SEQUENCE and incidents, half-open by E7.
9. Rebuild tests: rerun backfill rows only, registration window, flaky across all attempts (E4), quarantine with dashboard revocations, digest crosswalk for crash rows without a crash column.
10. Rebuild symbolication: pins by highest rev, build-id map for legacy frames, offset minus one for return addresses, noise frames skipped, gap frames end the search.
11. Rebuild bisection with Change-Seq and Rewritten-From, carried last_good; metrics with banker's rounding and the lower median.
12. Rebuild dependency resolution: alias register, amendments and advisories at the cut, withdrawals from the v2 index, snapshot pins, override expiry, caret on zero, prereleases.
13. Search the package source for feed file names, file name extensions and /app/data (the index filter on a .json suffix is the last name dependence); run the package twice and on a renamed copy of the feed; run it again on its own summary.json as resume; archive the project and write the outputs with --out /app/out.

### Trap loops

Flags: B entered by standard best practice, C chained (escaping the previous loop reveals it), D decoy anchored, S survives stage-1 checking and is only exposed by the hidden stage.

| loop | entry | reinforcement | tell (file) | exit | graded impact | flags |
|---|---|---|---|---|---|---|
| L01 | Fix only the install errors and trust the shipped rules | outputs are produced; counts look plausible | errata_register.pdf E1 to E10 contradict the shipped code | approved errata win over revision C text (G1) | module_metrics_counts_and_rates, module_metrics_median, dependency_resolution_semver | B |
| L02 | Read the newest specification revision D | its rules are self-consistent; draft ranks give stable winners | governance_precedence.docx G1 marks D a draft | revision C plus approved errata | build_report_attempt_precedence | B D |
| L03 | Drop revision D entirely after L02 | legacy rows still parse | BLD-24/25 job codes appear in no index job id | appendix D of D is the registered crosswalk (G1) | build_report_attempt_precedence | C D |
| L04 | Adopt errata revision B because it is later | its corrections agree with A on carried rows | errata_register.pdf E9 says only confirmed rows | E9 | build_report_attempt_precedence, module_metrics_counts_and_rates | B D |
| L05 | Ignore errata revision B after L04 | approved register looks complete | attempts corrected only in revB confirmed rows disagree with control expectations of E9 | E9 adopts confirmed rows | build_report_attempt_precedence | C D |
| L06 | Newest exporter copy wins | revisions look monotonic inside one exporter | governance G2 rank table | rank, then rev (4.1) | build_report_attempt_precedence, build_report_units_and_sentinels | B |
| L07 | First revocation action per job | most jobs have one action | feed_readme.md seq order shows reinstate after revoke | latest action by seq (4.1) | build_report_membership |  |
| L08 | Trust the full mirror re-export | it agrees with core exporters on 95 percent of keys | G5 limits it to pool eph | scope by pool from governance appendix G | build_report_membership | D |
| L09 | Drop the mirror export after L08 | membership looks clean | eph attempts vanish; their tests in TST partitions resolve to no attempt | G5 admits eph rows | build_report_membership | C D |
| L10 | Trust the rerun parquet | newest results | G6 backfill rule | backfill true only | module_metrics_flaky_and_quarantine | D |
| L11 | Drop the rerun parquet after L10 | flaky counts look stable | real_failures differ for builds whose only result is a backfill row | G6 | module_metrics_flaky_and_quarantine | C D |
| L12 | Read module aliases from modules.yaml only | nearly every alias resolves | -v3 aliases in partitions resolve nowhere | G4 in-window rows of modules_2026q2.xml | build_report_module_identity | C D |
| L13 | Load all of modules_2026q2.xml | the -v3 aliases resolve | future rows reassign aliases inside the window | G4 window filter | build_report_module_identity | D |
| L14 | Compare module references after lower-casing only | most rows resolve | per-file records and accepted counts drop | 3.1 NFKC plus homoglyph table | build_report_module_identity | B |
| L15 | Use the hosts.ini tz for host-local times | times look plausible | timekeeping_handbook.pdf lists moves inside the window | tz history by local date (4.4) | build_report_time_and_scope | B |
| L16 | Use the latest skew measurement of a host | offsets look plausible | measurements dated after the start | latest at or before the uncorrected start (4.4) | build_report_time_and_scope, build_report_membership |  |
| L17 | Read -1 skew offsets as values | small offsets look plausible | spec 4.4 failed probe | skip -1 rows | build_report_time_and_scope |  |
| L18 | Use skew estimates for every host | every host gets an offset | E10 restricts them to unmeasured hosts | E10 | build_report_time_and_scope | D |
| L19 | Ignore skew estimates after L18 | measured hosts are right | unmeasured hosts drift by seconds across window edges | E10 | build_report_time_and_scope | C D |
| L20 | Judge the window on the uncorrected start, closed at the end | counts match closely | boundary attempts near window start and end | half-open on the corrected start (4.2) | build_report_membership | B |
| L21 | Accept all branches named like main | mainline rows look like main | branch register in the scope memo | class main only (4.2, G16) | build_report_membership | D |
| L22 | Adopt the scope memo proposal | more builds | memo status: proposal; G16 | register only | build_report_membership | B D |
| L23 | Keep lab hosts | they are main-branch builds | G3 footnote | drop lab pool | build_report_membership | B |
| L24 | Decommission judged at window start | module list matches modules.yaml | attempts after a mid-window decommission | judge at the corrected start (4.2) | build_report_membership, module_core_states |  |
| L25 | Order commits by log position or date | bisection looks monotonic | Change-Seq trailers disagree with position | Change-Seq (4.3) | build_report_commits, module_core_bisection | B |
| L26 | Take Change-Seq from the unrebased mirror | it lists more commits | G10 | Change-Seq of commit_log.log | build_report_commits | D |
| L27 | Drop references that match no commit | only a few drop | commit_log_full.log Rewritten-From | map through G10 trailers | build_report_commits | C D |
| L28 | Apply void actions in file order | voids look consistent | seq interleaves three registers | ascending seq (4.7) | build_report_membership |  |
| L29 | Apply every action of void_register_v2 | more voids | countersigned column, G13 | countersigned only | build_report_membership | D |
| L30 | Ignore void_register_v2 after L29 | fewer voids | countersigned UNVOIDs reinstate builds | G13 | build_report_membership | C D |
| L31 | Keep stage-0 keys | counts grow by the re-exports | stage0_close.json seen_build_keys | exclude (4.7) | build_report_membership, summary_seen_build_keys |  |
| L32 | Last attempt decides | matches the draft rule | infra last attempts after a pass | highest pass or fail (4.6) | build_report_attempt_precedence | B |
| L33 | Maintenance from the first event of a UID | windows look plausible | SEQUENCE revisions in maintenance.ics | highest SEQUENCE (4.8) | build_report_attempt_precedence |  |
| L34 | Inclusive maintenance and incident ends | matches spec 4.8 text | E7 | half-open | build_report_attempt_precedence | B |
| L35 | Ignore known_issues.md incidents | it reads like prose | spec 4.9 | incident intervals make attempts infra | build_report_attempt_precedence |  |
| L36 | Flaky from deciding attempts only | matches spec 5.3 text | E4 | every pass or fail attempt | module_metrics_flaky_and_quarantine, build_report_crash_buckets | B |
| L37 | Use dashboard labels for flakiness | labels look curated | G9 | 5.3 evidence only | module_metrics_flaky_and_quarantine | D |
| L38 | Ignore the dashboard after L37 | quarantine counts look stable | quarantine_revocations table | G9 revocations | module_metrics_flaky_and_quarantine | C D |
| L39 | Skip test registration | every result counts | registered_at after the start | 5.2 | module_metrics_flaky_and_quarantine |  |
| L40 | Look up return addresses as written | labels are real symbols | E5 and the symbolication handbook | offset minus one | build_report_crash_buckets | B |
| L41 | Symbolicate with the newest store | relinked store looks fresher | G11 | pinned toolchain store | build_report_crash_buckets | D |
| L42 | Drop legacy bid: frames after L41 | most crashes still label | crash_triage_minutes.pdf frames | buildid_map of the relinked store (G11) | build_report_crash_buckets | C D |
| L43 | Use digest buckets | they look authoritative | G12 | symbolicate | build_report_crash_buckets | D |
| L44 | Treat crash rows without a crash column as failures | they look like failures | legacy_map sheet of the digest | G12 crosswalk | build_report_crash_buckets | C D |
| L45 | First mail per crash | most crashes have one mail | X-Report-Rev 2 mails | highest rev (6.1) | build_report_crash_buckets |  |
| L46 | Caret like any caret | most constraints are not zero-major | E3 and the shipped semver fixtures | E3 | dependency_resolution_semver, package_shipped_tests_pass | B |
| L47 | Prereleases satisfy ranges | highest version wins | 9.4 and shipped fixtures | prerelease admission rule | dependency_resolution_semver | B |
| L48 | Trust package_index_v2 | it lists more versions | G14 | versions from package_index.json | dependency_resolution_semver | D |
| L49 | Ignore package_index_v2 after L48 | resolution looks complete | withdrawn table | G14 withdrawals | dependency_resolution_semver | C D |
| L50 | Use the lock snapshot for every frozen module | snapshot looks consistent | G15 | only pins: snapshot entries | dependency_resolution_semver | D |
| L51 | Ignore the snapshot after L50 | lock sources look right | pins: snapshot entries cannot be resolved | G15 | dependency_resolution_semver | C D |
| L52 | Find the feed index by name | stage 1 works | a later stage names its index differently | role index in the control block (2.1) | stage2_selftest and every stage-2 check | S |
| L53 | Hard-code the stage-1 toolchains tc41/tc42 | stage 1 symbolicates | stage 2 pins tc42/tc43 | pins and store control keys (6.2) | stage2_build_report | S |
| L54 | Hard-code the stage window | stage 1 scope is right | a later index carries another window | window from the index (4.2) | stage2_build_report | S |
| L55 | Recompute last_good from the stage alone | modules with green builds are right | resume state last_good_seq | carry (7.2) | module_core_bisection, summary_last_good, stage2_module_core | S |
| L56 | Chain files in path order | every file is read | chain_pos in the index | chain_pos (2.4) | every check through the run control stamp | B |
| L57 | Read restated #header rows as data or skip them | most rows parse | records counts in control blocks | switch column order (3.0) | build_report_time_and_scope, build_report_membership |  |
| L58 | Decode legacy lines with replacement characters | durations with a micro sign fail or vanish | records count and E6 | cp1252 fallback (3.6) | build_report_units_and_sentinels |  |
| L59 | Ignore CMDB after trusting hosts.ini | known hosts are right | eph hosts without a site | G7 | build_report_attempt_precedence | C D |
| L60 | Trust CMDB sites | every host gets a site | G7 | hosts.ini first | build_report_attempt_precedence | D |

60 loops: 14 chained, 17 best-practice entries, 30 decoy anchored, 4 survive stage-1 checking.

### Expert time estimate (36 hours, 4.5 working days)

- Install and import repair, reading the project: 3 h
- Reading revision C, errata, governance, the handbooks and the decoys' own status lines: 5 h
- Readers for 20 formats with record-count verification, layout quirks and encodings: 6 h
- Attempt precedence, voids, errata, maintenance and incidents: 4 h
- Clock normalisation, alias windows and scope: 3 h
- Test results, flaky detection, quarantine, crosswalks: 3 h
- Symbolication with pins, build ids and the pc-1 rule: 3 h
- Bisection and metrics with carried state: 2 h
- Dependency resolution with the semver fixtures: 3 h
- Falsification passes: per-decoy ignore and trust probes, renamed and repeated runs, chaining the summary: 4 h

Total 36 hours, 4.5 working days of 8 hours.

## Pitfalls

- Treating the newest-looking file as authoritative (revision D, errata revB, package index v2, symbols b2, modules 2026q2, scope memo v2): fails the build, metrics and dependency checks those decoys touch.
- Ignoring a decoy wholesale: each one holds a crosswalk, void list or in-scope slice nothing else has; fails the checks that read those rows.
- Rounding half up, averaging the median, textbook caret, deciding-only flaky evidence, no pc-1: the revision C text says so but the approved errata override it; fails module_metrics and dependency checks and crash buckets.
- Writing the ledger files with an ad-hoc script: the hidden stage runs the package, so every stage-2 check fails unless the package itself is right.
- Finding files by name: the hidden stage names them differently; the stage-2 checks run the package on a renamed copy of the hidden feed, so every stage-2 check fails.
- Reading /app/data from the package: the hidden stage-2 run has no /app/data, so every stage-2 check fails. Embedding stage-1 answers fires negative_hardcoded_sample_answers.
- Iterating sets into outputs: two runs differ and negative_nondeterministic_output fires.
- Declaring a dependency other than PyYAML, pyarrow and pypdf: the package cannot be installed where it is graded; every package check fails.

### Trap families by file

| file | T1 | T2 | T3 | T4 | T5 | T6 | T7 | T8 | T9 | T10 | T11 | T12 | T13 | T14 | T15 | T16 | total |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| BLD-01 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 2 | 2 | 1 | 1 | 1 | 1 | 1 | 0 | 17 |
| BLD-02 | 1 | 1 | 1 | 1 | 1 | 1 | 2 | 2 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 0 | 17 |
| BLD-03 | 1 | 1 | 1 | 1 | 1 | 1 | 2 | 1 | 4 | 2 | 3 | 1 | 1 | 1 | 1 | 0 | 22 |
| BLD-04 | 1 | 1 | 1 | 1 | 1 | 3 | 1 | 1 | 2 | 2 | 1 | 1 | 1 | 2 | 1 | 0 | 20 |
| BLD-05 | 2 | 1 | 3 | 1 | 1 | 1 | 1 | 2 | 1 | 2 | 1 | 1 | 1 | 1 | 1 | 0 | 20 |
| BLD-06 | 4 | 1 | 1 | 0 | 1 | 2 | 1 | 1 | 2 | 1 | 1 | 1 | 1 | 2 | 1 | 0 | 20 |
| BLD-07 | 1 | 1 | 2 | 1 | 1 | 1 | 1 | 1 | 1 | 2 | 1 | 1 | 1 | 1 | 1 | 0 | 17 |
| BLD-08 | 1 | 1 | 3 | 0 | 1 | 1 | 2 | 1 | 1 | 2 | 1 | 1 | 1 | 1 | 1 | 0 | 18 |
| BLD-09 | 4 | 0 | 1 | 0 | 1 | 1 | 2 | 2 | 1 | 1 | 1 | 0 | 2 | 1 | 1 | 0 | 18 |
| BLD-10 | 4 | 0 | 2 | 0 | 1 | 2 | 3 | 1 | 1 | 1 | 1 | 0 | 1 | 1 | 2 | 0 | 20 |
| BLD-11 | 1 | 0 | 2 | 0 | 2 | 1 | 2 | 2 | 1 | 1 | 1 | 0 | 1 | 2 | 1 | 0 | 17 |
| BLD-12 | 6 | 0 | 1 | 0 | 2 | 4 | 2 | 0 | 0 | 0 | 1 | 0 | 2 | 1 | 1 | 0 | 20 |
| BLD-13 | 7 | 0 | 2 | 0 | 1 | 2 | 3 | 0 | 0 | 0 | 1 | 0 | 1 | 1 | 2 | 0 | 20 |
| BLD-14 | 6 | 0 | 1 | 0 | 1 | 1 | 2 | 0 | 0 | 0 | 1 | 0 | 1 | 5 | 2 | 0 | 20 |
| BLD-15 | 1 | 4 | 1 | 0 | 1 | 1 | 1 | 2 | 1 | 0 | 1 | 2 | 1 | 1 | 1 | 0 | 18 |
| BLD-16 | 1 | 4 | 1 | 0 | 1 | 1 | 1 | 1 | 1 | 0 | 0 | 3 | 1 | 1 | 1 | 0 | 17 |
| BLD-17 | 1 | 3 | 1 | 0 | 1 | 1 | 1 | 2 | 1 | 0 | 1 | 1 | 1 | 1 | 1 | 0 | 16 |
| BLD-18 | 3 | 0 | 2 | 0 | 1 | 2 | 2 | 0 | 0 | 0 | 1 | 0 | 2 | 2 | 1 | 0 | 16 |
| BLD-19 | 3 | 0 | 1 | 0 | 2 | 2 | 1 | 0 | 0 | 0 | 1 | 0 | 1 | 3 | 2 | 0 | 16 |
| BLD-20 | 1 | 4 | 1 | 0 | 1 | 1 | 1 | 2 | 0 | 0 | 1 | 2 | 1 | 1 | 1 | 0 | 17 |
| BLD-21 | 2 | 5 | 1 | 0 | 1 | 1 | 1 | 1 | 0 | 0 | 1 | 2 | 1 | 1 | 1 | 0 | 18 |
| BLD-22 | 3 | 0 | 1 | 0 | 1 | 1 | 2 | 0 | 0 | 0 | 1 | 0 | 2 | 4 | 2 | 0 | 17 |
| BLD-23 | 1 | 2 | 2 | 0 | 1 | 1 | 1 | 2 | 0 | 0 | 1 | 3 | 1 | 1 | 1 | 0 | 17 |
| BLD-24 | 1 | 1 | 1 | 4 | 1 | 1 | 1 | 0 | 0 | 1 | 1 | 1 | 1 | 1 | 1 | 0 | 16 |
| BLD-25 | 1 | 1 | 1 | 4 | 1 | 1 | 1 | 0 | 0 | 4 | 1 | 1 | 1 | 1 | 1 | 0 | 19 |
| AGT-01 | 1 | 6 | 1 | 0 | 2 | 1 | 1 | 0 | 0 | 0 | 1 | 4 | 1 | 1 | 1 | 0 | 20 |
| AGT-02 | 3 | 5 | 1 | 0 | 1 | 1 | 1 | 0 | 0 | 0 | 1 | 3 | 2 | 1 | 1 | 0 | 20 |
| DCY-03 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 19 | 34 |
| TST-01 | 1 | 1 | 0 | 5 | 0 | 1 | 1 | 1 | 1 | 2 | 1 | 1 | 1 | 0 | 1 | 0 | 17 |
| TST-02 | 1 | 1 | 0 | 4 | 0 | 1 | 0 | 1 | 1 | 3 | 1 | 1 | 1 | 0 | 1 | 0 | 16 |
| TST-03 | 1 | 1 | 0 | 3 | 0 | 1 | 2 | 2 | 2 | 2 | 1 | 1 | 1 | 0 | 1 | 0 | 18 |
| TST-04 | 1 | 1 | 0 | 6 | 0 | 1 | 1 | 1 | 1 | 4 | 1 | 1 | 1 | 0 | 1 | 0 | 20 |
| TST-05 | 1 | 1 | 0 | 0 | 0 | 1 | 1 | 2 | 2 | 3 | 1 | 1 | 2 | 0 | 1 | 0 | 16 |
| TST-06 | 1 | 1 | 0 | 0 | 0 | 2 | 1 | 2 | 6 | 3 | 1 | 1 | 1 | 0 | 1 | 0 | 20 |
| TST-07 | 1 | 1 | 0 | 0 | 0 | 1 | 1 | 1 | 4 | 4 | 1 | 1 | 1 | 0 | 2 | 0 | 18 |
| TST-08 | 1 | 1 | 0 | 0 | 0 | 1 | 1 | 3 | 5 | 3 | 1 | 1 | 1 | 0 | 1 | 0 | 19 |
| TST-09 | 3 | 0 | 0 | 0 | 0 | 4 | 1 | 3 | 0 | 0 | 1 | 0 | 1 | 0 | 4 | 0 | 17 |
| TST-10 | 1 | 0 | 0 | 0 | 0 | 1 | 1 | 7 | 0 | 1 | 1 | 0 | 3 | 0 | 4 | 0 | 19 |
| TST-11 | 2 | 0 | 0 | 0 | 0 | 2 | 1 | 7 | 0 | 1 | 1 | 0 | 1 | 0 | 4 | 0 | 19 |
| TST-12 | 4 | 0 | 0 | 0 | 0 | 8 | 1 | 0 | 0 | 0 | 1 | 0 | 2 | 0 | 4 | 0 | 20 |
| TST-13 | 5 | 0 | 0 | 0 | 0 | 7 | 1 | 0 | 0 | 0 | 1 | 0 | 2 | 0 | 4 | 0 | 20 |
| TST-14 | 3 | 0 | 0 | 0 | 0 | 6 | 1 | 0 | 0 | 0 | 1 | 0 | 3 | 0 | 6 | 0 | 20 |
| TST-15 | 2 | 4 | 0 | 0 | 0 | 3 | 1 | 4 | 0 | 0 | 1 | 2 | 1 | 0 | 1 | 0 | 19 |
| TST-16 | 3 | 1 | 0 | 0 | 0 | 1 | 1 | 5 | 0 | 0 | 1 | 2 | 1 | 0 | 2 | 0 | 17 |
| TST-17 | 6 | 0 | 0 | 0 | 0 | 4 | 2 | 0 | 0 | 0 | 2 | 0 | 2 | 0 | 4 | 0 | 20 |
| TST-18 | 2 | 5 | 0 | 0 | 0 | 1 | 1 | 3 | 0 | 0 | 1 | 1 | 1 | 0 | 1 | 0 | 16 |
| TST-19 | 1 | 6 | 0 | 0 | 0 | 2 | 1 | 4 | 0 | 0 | 1 | 2 | 1 | 0 | 1 | 0 | 19 |
| TST-20 | 1 | 4 | 0 | 0 | 0 | 1 | 1 | 4 | 0 | 0 | 1 | 2 | 1 | 0 | 1 | 0 | 16 |
| TST-21 | 1 | 1 | 0 | 8 | 0 | 1 | 1 | 0 | 0 | 2 | 1 | 1 | 1 | 0 | 1 | 0 | 18 |
| TST-22 | 1 | 7 | 0 | 0 | 0 | 3 | 1 | 0 | 0 | 0 | 1 | 2 | 1 | 0 | 1 | 0 | 17 |
| DCY-05 | 2 | 0 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | 0 | 1 | 0 | 1 | 0 | 1 | 24 | 31 |
| CRS-01 | 0 | 0 | 0 | 0 | 0 | 0 | 3 | 0 | 0 | 0 | 11 | 0 | 4 | 0 | 1 | 0 | 19 |
| CRS-02 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 4 | 11 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 17 |
| CRS-03 | 4 | 0 | 0 | 0 | 0 | 1 | 0 | 8 | 0 | 0 | 0 | 0 | 3 | 0 | 0 | 0 | 16 |
| DCY-10 | 10 | 0 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 2 | 0 | 1 | 15 | 30 |
| SYM-01 | 8 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 2 | 0 | 9 | 0 | 1 | 0 | 20 |
| SYM-02 | 11 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 5 | 0 | 2 | 0 | 2 | 0 | 20 |
| SYM-03 | 9 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 2 | 0 | 4 | 0 | 1 | 0 | 16 |
| SYM-04 | 6 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 3 | 0 | 9 | 0 | 1 | 0 | 19 |
| SYM-05 | 6 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 4 | 0 | 6 | 0 | 1 | 0 | 17 |
| SYM-06 | 6 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 8 | 0 | 1 | 0 | 16 |
| DCY-04 | 8 | 0 | 0 | 0 | 0 | 4 | 2 | 0 | 0 | 0 | 1 | 0 | 1 | 0 | 2 | 15 | 33 |
| DOC-03 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 9 | 0 | 0 | 0 | 0 | 7 | 0 | 1 | 0 | 19 |
| PIN-01 | 15 | 0 | 0 | 0 | 0 | 0 | 43 | 0 | 0 | 0 | 0 | 0 | 2 | 0 | 1 | 0 | 61 |
| CMT-01 | 0 | 0 | 0 | 0 | 0 | 0 | 14 | 0 | 0 | 0 | 1 | 0 | 2 | 0 | 1 | 0 | 18 |
| DCY-11 | 0 | 0 | 0 | 0 | 0 | 1 | 2 | 0 | 0 | 0 | 1 | 0 | 1 | 0 | 1 | 28 | 34 |
| REG-01 | 3 | 0 | 1 | 0 | 10 | 1 | 1 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 17 |
| DCY-06 | 6 | 0 | 0 | 0 | 13 | 1 | 1 | 9 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 | 32 |
| REG-02 | 2 | 0 | 9 | 0 | 4 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 1 | 0 | 17 |
| REG-03 | 3 | 0 | 11 | 0 | 0 | 1 | 5 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 20 |
| DCY-09 | 2 | 0 | 0 | 0 | 0 | 4 | 1 | 5 | 0 | 0 | 0 | 0 | 3 | 0 | 0 | 19 | 34 |
| HST-01 | 5 | 0 | 0 | 0 | 0 | 0 | 3 | 0 | 0 | 0 | 0 | 0 | 3 | 5 | 0 | 0 | 16 |
| DCY-08 | 1 | 0 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 1 | 8 | 0 | 19 | 31 |
| HST-02 | 1 | 0 | 1 | 10 | 1 | 0 | 0 | 1 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 16 |
| DCY-13 | 1 | 0 | 0 | 0 | 0 | 1 | 1 | 1 | 2 | 1 | 0 | 0 | 1 | 0 | 0 | 23 | 31 |
| DOC-05 | 7 | 0 | 2 | 0 | 0 | 0 | 0 | 8 | 0 | 0 | 0 | 0 | 0 | 0 | 2 | 0 | 19 |
| MNT-01 | 0 | 0 | 3 | 0 | 0 | 7 | 2 | 0 | 0 | 0 | 7 | 0 | 0 | 0 | 0 | 0 | 19 |
| VOD-01 | 1 | 0 | 3 | 0 | 0 | 2 | 1 | 2 | 9 | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 20 |
| VOD-02 | 1 | 0 | 5 | 0 | 0 | 6 | 1 | 4 | 0 | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 19 |
| DCY-12 | 1 | 0 | 1 | 0 | 0 | 1 | 1 | 1 | 0 | 0 | 1 | 0 | 1 | 0 | 0 | 26 | 33 |
| DOC-06 | 4 | 0 | 0 | 0 | 0 | 0 | 6 | 5 | 0 | 0 | 0 | 0 | 1 | 0 | 1 | 0 | 17 |
| DCY-02 | 1 | 0 | 0 | 0 | 0 | 9 | 6 | 10 | 0 | 0 | 0 | 0 | 1 | 0 | 1 | 5 | 33 |
| DOC-01 | 3 | 0 | 0 | 0 | 0 | 1 | 0 | 9 | 0 | 0 | 0 | 0 | 7 | 0 | 0 | 0 | 20 |
| DCY-01 | 2 | 0 | 0 | 0 | 0 | 2 | 5 | 11 | 0 | 0 | 0 | 0 | 6 | 0 | 0 | 7 | 33 |
| DOC-02 | 5 | 0 | 0 | 0 | 0 | 1 | 0 | 5 | 0 | 0 | 0 | 0 | 3 | 4 | 0 | 0 | 18 |
| DCY-15 | 1 | 0 | 0 | 0 | 0 | 1 | 1 | 3 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 27 | 34 |
| DOC-07 | 0 | 0 | 0 | 0 | 0 | 6 | 4 | 6 | 0 | 1 | 0 | 0 | 1 | 0 | 0 | 0 | 18 |
| DOC-08 | 3 | 0 | 8 | 0 | 0 | 0 | 0 | 3 | 0 | 1 | 2 | 0 | 0 | 0 | 0 | 0 | 17 |
| DEP-01 | 6 | 0 | 9 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 2 | 0 | 4 | 0 | 1 | 0 | 22 |
| DCY-07 | 3 | 0 | 5 | 0 | 0 | 4 | 2 | 0 | 0 | 0 | 0 | 0 | 4 | 0 | 1 | 12 | 31 |
| DEP-02 | 2 | 0 | 7 | 0 | 0 | 0 | 6 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 4 | 0 | 20 |
| DEP-03 | 2 | 0 | 9 | 0 | 0 | 0 | 2 | 3 | 0 | 0 | 1 | 0 | 0 | 0 | 1 | 0 | 18 |
| DEP-04 | 7 | 0 | 3 | 0 | 0 | 0 | 6 | 0 | 0 | 0 | 1 | 0 | 2 | 0 | 1 | 0 | 20 |
| DEP-05 | 1 | 0 | 5 | 0 | 6 | 0 | 0 | 0 | 0 | 0 | 2 | 0 | 0 | 2 | 0 | 0 | 16 |
| DEP-06 | 2 | 0 | 0 | 0 | 0 | 8 | 2 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 6 | 0 | 19 |
| DCY-14 | 1 | 0 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 1 | 29 | 34 |
| DOC-04 | 4 | 0 | 0 | 0 | 0 | 0 | 3 | 9 | 0 | 0 | 0 | 0 | 3 | 0 | 0 | 0 | 19 |
| IDX-01 | 0 | 0 | 0 | 0 | 0 | 7 | 4 | 0 | 0 | 0 | 1 | 0 | 1 | 1 | 0 | 0 | 14 |
| OPN-01 | 0 | 0 | 0 | 0 | 0 | 1 | 9 | 0 | 0 | 0 | 0 | 0 | 9 | 0 | 1 | 0 | 20 |
| PRJ-01 | 0 | 0 | 0 | 0 | 1 | 0 | 3 | 0 | 1 | 0 | 4 | 0 | 2 | 1 | 4 | 0 | 16 |

Traps: 2077 in total, 1589 in scope, 488 in decoys; every family appears in at least 15 files; every 500-row band of every table carries at least one trap. The full manifest follows (file id, table, row, family, direction for decoys, rule, check). A reader-layout trap names the check fed by the file's rows; a misread control block (byte order mark) breaks the run control chain.

### Trap manifest

```text
BLD-01 attempts:461 T7 | 3.1 alias validity window decides the module | build_report_module_identity
BLD-01 attempts:967 T15 | 4.6 third attempt is valid and may decide | build_report_attempt_precedence
BLD-01 attempts:1239 T8 | 3.6 #header restates reordered columns | build_report_membership
BLD-01 attempts:1947 T1 | 3.1 module reference normalisation (NFKC, homoglyphs, case) | build_report_module_identity
BLD-01 attempts:2299 T3 | 3.4 explicit offset makes a timestamp absolute | build_report_time_and_scope
BLD-01 attempts:2577 T6 | 4.7 latest void action decides | build_report_attempt_precedence
BLD-01 attempts:3196 T9 | 3.6 ragged row with trailing empty cells | build_report_membership
BLD-01 attempts:3568 T14 | G3 lab pool excluded by governance footnote | build_report_time_and_scope
BLD-01 attempts:4057 T2 | 3.3 unit suffix overrides the column unit | build_report_units_and_sentinels
BLD-01 attempts:4942 T10 | 3.6 cp1252 line with the micro sign | build_report_units_and_sentinels
BLD-01 attempts:0 T10 | 3.6 byte order mark before the control block | selftest_control_chain
BLD-01 attempts:4504 T13 | 4.4 host known only to the CMDB export | build_report_time_and_scope
BLD-01 attempts:29 T12 | E6 microseconds round half to even at the millisecond | build_report_units_and_sentinels
BLD-01 attempts:2629 T4 | 3.2 thousands separator | build_report_units_and_sentinels
BLD-01 attempts:4973 T11 | 4.2 half-open window on corrected start | build_report_time_and_scope
BLD-01 attempts:3361 T5 | 3.5 placeholder start sentinel | build_report_membership
BLD-01 attempts:3062 T9 | 3.6 ragged row with trailing empty cells | build_report_membership
BLD-02 attempts:351 T4 | 3.2 thousands separator | build_report_units_and_sentinels
BLD-02 attempts:609 T6 | 4.7 latest void action decides | build_report_attempt_precedence
BLD-02 attempts:1122 T1 | 3.1 cells are stripped of surrounding white space | build_report_membership
BLD-02 attempts:1663 T9 | 3.6 ragged row with trailing empty cells | build_report_membership
BLD-02 attempts:2416 T3 | 3.4 explicit offset makes a timestamp absolute | build_report_time_and_scope
BLD-02 attempts:2529 T8 | 3.6 #header restates reordered columns | build_report_membership
BLD-02 attempts:3096 T2 | 3.3 unit suffix overrides the column unit | build_report_units_and_sentinels
BLD-02 attempts:3902 T7 | 3.1 alias validity window decides the module | build_report_module_identity
BLD-02 attempts:4150 T13 | 4.4 host known only to the CMDB export | build_report_time_and_scope
BLD-02 attempts:4811 T15 | valid long-running build is not an outlier to drop | module_metrics_counts_and_rates
BLD-02 attempts:0 T10 | 3.6 byte order mark before the control block | selftest_control_chain
BLD-02 attempts:67 T14 | 4.2 branch class from the stage memo register | build_report_time_and_scope
BLD-02 attempts:708 T11 | 4.2 half-open window on corrected start | build_report_time_and_scope
BLD-02 attempts:261 T12 | E6 microseconds round half to even at the millisecond | build_report_units_and_sentinels
BLD-02 attempts:98 T5 | 3.5 placeholder start sentinel | build_report_membership
BLD-02 attempts:951 T8 | 3.6 #header restates reordered columns | build_report_membership
BLD-02 attempts:489 T7 | 4.5 approved errata correct the attempt | build_report_attempt_precedence
BLD-03 attempts:137 T12 | E6 microseconds round half to even at the millisecond | build_report_units_and_sentinels
BLD-03 attempts:845 T1 | 3.1 cells are stripped of surrounding white space | build_report_membership
BLD-03 attempts:1310 T2 | 3.3 unit suffix overrides the column unit | build_report_units_and_sentinels
BLD-03 attempts:1830 T6 | 4.1 rows of revoked export jobs are void | build_report_attempt_precedence
BLD-03 attempts:2495 T14 | 4.2 branch class from the stage memo register | build_report_time_and_scope
BLD-03 attempts:2648 T8 | 3.6 #header restates reordered columns | build_report_membership
BLD-03 attempts:3306 T10 | 3.6 cp1252 line with the micro sign | build_report_units_and_sentinels
BLD-03 attempts:3721 T4 | 3.2 thousands separator | build_report_units_and_sentinels
BLD-03 attempts:4414 T5 | 3.5 placeholder start sentinel | build_report_membership
BLD-03 attempts:4839 T7 | 4.4 time zone history supersedes the host registry tz | build_report_time_and_scope
BLD-03 attempts:0 T10 | 3.6 byte order mark before the control block | selftest_control_chain
BLD-03 attempts:2689 T3 | 3.4 explicit offset makes a timestamp absolute | build_report_time_and_scope
BLD-03 attempts:4781 T15 | 4.6 third attempt is valid and may decide | build_report_attempt_precedence
BLD-03 attempts:188 T9 | 3.6 quoted delimiter and newline inside a cell | build_report_membership
BLD-03 attempts:1019 T13 | G4 in-window rename from the next-quarter registry | build_report_module_identity
BLD-03 attempts:3679 T11 | 4.2 half-open window on corrected start | build_report_time_and_scope
BLD-03 attempts:510 T9 | 3.6 ragged row with trailing empty cells | build_report_membership
BLD-03 attempts:816 T9 | 3.6 ragged row with trailing empty cells | build_report_membership
BLD-03 attempts:4040 T7 | 4.4 time zone history supersedes the host registry tz | build_report_time_and_scope
BLD-03 attempts:2726 T9 | 3.6 ragged row with trailing empty cells | build_report_membership
BLD-03 attempts:226 T11 | 4.2 corrected start exactly at the window end is outside the half-open window | build_report_membership
BLD-03 attempts:4144 T11 | 4.2 logged start inside the window, corrected start after its end | build_report_membership
BLD-04 attempts:38 T1 | 3.1 module reference normalisation (NFKC, homoglyphs, case) | build_report_module_identity
BLD-04 attempts:958 T13 | 4.4 host known only to the CMDB export | build_report_time_and_scope
BLD-04 attempts:1192 T5 | 3.5 placeholder start sentinel | build_report_membership
BLD-04 attempts:1715 T2 | 3.3 unit suffix overrides the column unit | build_report_units_and_sentinels
BLD-04 attempts:2322 T7 | 4.1 exporter rank decides between copies | build_report_attempt_precedence
BLD-04 attempts:2802 T10 | 3.6 cp1252 line with the micro sign | build_report_units_and_sentinels
BLD-04 attempts:3016 T15 | 4.6 third attempt is valid and may decide | build_report_attempt_precedence
BLD-04 attempts:3980 T8 | 3.6 #header restates reordered columns | build_report_membership
BLD-04 attempts:4270 T14 | 4.2 branch class from the stage memo register | build_report_time_and_scope
BLD-04 attempts:4740 T9 | 3.6 ragged row with trailing empty cells | build_report_membership
BLD-04 attempts:3338 T3 | 4.4 DST-aware local time conversion | build_report_time_and_scope
BLD-04 attempts:409 T6 | 3.6 provisional rows are not attempts | build_report_membership
BLD-04 attempts:4276 T12 | E6 microseconds round half to even at the millisecond | build_report_units_and_sentinels
BLD-04 attempts:4095 T4 | 3.2 thousands separator | build_report_units_and_sentinels
BLD-04 attempts:58 T11 | 4.2 half-open window on corrected start | build_report_time_and_scope
BLD-04 attempts:4352 T14 | 4.2 branch class from the stage memo register | build_report_time_and_scope
BLD-04 attempts:1916 T6 | 3.6 provisional rows are not attempts | build_report_membership
BLD-04 attempts:3523 T6 | 4.7 latest void action decides | build_report_attempt_precedence
BLD-04 attempts:1777 T9 | 3.6 ragged row with trailing empty cells | build_report_membership
BLD-04 attempts:1945 T10 | 3.6 cp1252 line with the micro sign | build_report_units_and_sentinels
BLD-05 attempts:353 T1 | 3.1 host names are case-insensitive | build_report_time_and_scope
BLD-05 attempts:510 T3 | 3.4 explicit offset makes a timestamp absolute | build_report_time_and_scope
BLD-05 attempts:1199 T13 | 4.3 rewritten commit resolved through Rewritten-From | module_core_bisection
BLD-05 attempts:1922 T4 | 3.2 thousands separator | build_report_units_and_sentinels
BLD-05 attempts:2038 T15 | valid long-running build is not an outlier to drop | module_metrics_counts_and_rates
BLD-05 attempts:2708 T8 | 3.6 #header restates reordered columns | build_report_membership
BLD-05 attempts:3070 T12 | E6 microseconds round half to even at the millisecond | build_report_units_and_sentinels
BLD-05 attempts:3720 T7 | 4.4 time zone history supersedes the host registry tz | build_report_time_and_scope
BLD-05 attempts:4439 T2 | 3.3 unit suffix overrides the column unit | build_report_units_and_sentinels
BLD-05 attempts:4725 T6 | 3.6 provisional rows are not attempts | build_report_membership
BLD-05 attempts:0 T10 | 3.6 byte order mark before the control block | selftest_control_chain
BLD-05 attempts:2002 T14 | 4.2 branch class from the stage memo register | build_report_time_and_scope
BLD-05 attempts:4698 T9 | 3.6 quoted delimiter and newline inside a cell | build_report_membership
BLD-05 attempts:222 T5 | 3.5 placeholder start sentinel | build_report_membership
BLD-05 attempts:961 T10 | 3.6 cp1252 line with the micro sign | build_report_units_and_sentinels
BLD-05 attempts:2835 T3 | 4.4 DST-aware local time conversion | build_report_time_and_scope
BLD-05 attempts:4108 T8 | 3.6 #header restates reordered columns | build_report_membership
BLD-05 attempts:3091 T3 | 4.4 DST-aware local time conversion | build_report_time_and_scope
BLD-05 attempts:4553 T1 | 3.1 module reference normalisation (NFKC, homoglyphs, case) | build_report_module_identity
BLD-05 attempts:3436 T11 | 4.2 half-open window on corrected start | build_report_time_and_scope
BLD-06 attempts:416 T13 | 4.4 host known only to the CMDB export | build_report_time_and_scope
BLD-06 attempts:907 T1 | 3.1 build key spellings | build_report_membership
BLD-06 attempts:1380 T2 | 3.3 unit suffix overrides the column unit | build_report_units_and_sentinels
BLD-06 attempts:1876 T9 | 3.6 ragged row with trailing empty cells | build_report_membership
BLD-06 attempts:2060 T5 | 3.5 placeholder start sentinel | build_report_membership
BLD-06 attempts:2727 T3 | 3.4 explicit offset makes a timestamp absolute | build_report_time_and_scope
BLD-06 attempts:3129 T12 | E6 microseconds round half to even at the millisecond | build_report_units_and_sentinels
BLD-06 attempts:3842 T14 | 4.2 branch class from the stage memo register | build_report_time_and_scope
BLD-06 attempts:4431 T7 | 3.1 alias validity window decides the module | build_report_module_identity
BLD-06 attempts:4744 T8 | 3.6 #header restates reordered columns | build_report_membership
BLD-06 attempts:0 T10 | 3.6 byte order mark before the control block | selftest_control_chain
BLD-06 attempts:4218 T11 | 4.2 half-open window on corrected start | build_report_time_and_scope
BLD-06 attempts:107 T6 | 3.6 provisional rows are not attempts | build_report_membership
BLD-06 attempts:3247 T15 | 4.6 third attempt is valid and may decide | build_report_attempt_precedence
BLD-06 attempts:3646 T1 | 3.1 cells are stripped of surrounding white space | build_report_membership
BLD-06 attempts:4876 T1 | 3.1 cells are stripped of surrounding white space | build_report_membership
BLD-06 attempts:3236 T1 | 3.1 cells are stripped of surrounding white space | build_report_membership
BLD-06 attempts:451 T6 | 4.7 latest void action decides | build_report_attempt_precedence
BLD-06 attempts:3777 T9 | 3.6 ragged row with trailing empty cells | build_report_membership
BLD-06 attempts:4749 T14 | 4.2 branch class from the stage memo register | build_report_time_and_scope
BLD-07 attempts:218 T1 | 3.1 build key spellings | build_report_membership
BLD-07 attempts:808 T2 | 3.3 unit suffix overrides the column unit | build_report_units_and_sentinels
BLD-07 attempts:1402 T12 | E6 microseconds round half to even at the millisecond | build_report_units_and_sentinels
BLD-07 attempts:1635 T4 | 3.2 de thousands and decimal comma | build_report_units_and_sentinels
BLD-07 attempts:2077 T8 | 3.6 #header restates reordered columns | build_report_membership
BLD-07 attempts:2521 T5 | 3.5 placeholder start sentinel | build_report_membership
BLD-07 attempts:3483 T9 | 3.6 ragged row with trailing empty cells | build_report_membership
BLD-07 attempts:3586 T14 | G3 lab pool excluded by governance footnote | build_report_time_and_scope
BLD-07 attempts:4362 T3 | 4.4 DST-aware local time conversion | build_report_time_and_scope
BLD-07 attempts:4634 T6 | 3.6 provisional rows are not attempts | build_report_membership
BLD-07 attempts:12 T10 | 3.6 cp1252 line with the micro sign | build_report_units_and_sentinels
BLD-07 attempts:4269 T11 | 4.2 half-open window on corrected start | build_report_time_and_scope
BLD-07 attempts:661 T7 | 4.4 time zone history supersedes the host registry tz | build_report_time_and_scope
BLD-07 attempts:4609 T15 | 4.6 third attempt is valid and may decide | build_report_attempt_precedence
BLD-07 attempts:1023 T13 | 4.4 host known only to the CMDB export | build_report_time_and_scope
BLD-07 attempts:3849 T3 | 4.4 DST-aware local time conversion | build_report_time_and_scope
BLD-07 attempts:3291 T10 | 3.6 cp1252 line with the micro sign | build_report_units_and_sentinels
BLD-08 attempts:228 T9 | 3.6 ragged row with trailing empty cells | build_report_membership
BLD-08 attempts:973 T3 | 3.4 explicit offset makes a timestamp absolute | build_report_time_and_scope
BLD-08 attempts:1066 T7 | 4.1 exporter rank decides between copies | build_report_attempt_precedence
BLD-08 attempts:1858 T1 | 3.1 cells are stripped of surrounding white space | build_report_membership
BLD-08 attempts:2492 T5 | 3.5 placeholder start sentinel | build_report_membership
BLD-08 attempts:2988 T10 | 3.6 cp1252 line with the micro sign | build_report_units_and_sentinels
BLD-08 attempts:3112 T2 | 3.3 unit suffix overrides the column unit | build_report_units_and_sentinels
BLD-08 attempts:3809 T6 | 3.6 provisional rows are not attempts | build_report_membership
BLD-08 attempts:4110 T15 | 4.6 third attempt is valid and may decide | build_report_attempt_precedence
BLD-08 attempts:4921 T11 | 4.2 half-open window on corrected start | build_report_time_and_scope
BLD-08 attempts:0 T10 | 3.6 byte order mark before the control block | selftest_control_chain
BLD-08 attempts:4564 T8 | 3.6 #header restates reordered columns | build_report_membership
BLD-08 attempts:4247 T12 | E6 microseconds round half to even at the millisecond | build_report_units_and_sentinels
BLD-08 attempts:3866 T14 | 4.2 branch class from the stage memo register | build_report_time_and_scope
BLD-08 attempts:315 T13 | 4.3 rewritten commit resolved through Rewritten-From | module_core_bisection
BLD-08 attempts:98 T3 | 4.4 DST-aware local time conversion | build_report_time_and_scope
BLD-08 attempts:1344 T7 | 3.1 alias validity window decides the module | build_report_module_identity
BLD-08 attempts:1381 T3 | 4.4 DST-aware local time conversion | build_report_time_and_scope
BLD-09 attempts:103 T1 | 3.1 host names are case-insensitive | build_report_time_and_scope
BLD-09 attempts:784 T3 | 4.4 DST-aware local time conversion | build_report_time_and_scope
BLD-09 attempts:1485 T14 | 4.2 branch class from the stage memo register | build_report_time_and_scope
BLD-09 attempts:1612 T15 | valid long-running build is not an outlier to drop | module_metrics_counts_and_rates
BLD-09 attempts:2337 T8 | 3.6 column aliases | build_report_membership
BLD-09 attempts:2767 T6 | 4.7 latest void action decides | build_report_attempt_precedence
BLD-09 attempts:3370 T7 | 4.1 exporter rank decides between copies | build_report_attempt_precedence
BLD-09 attempts:3816 T9 | 3.6 quoted delimiter and newline inside a cell | build_report_membership
BLD-09 attempts:4044 T13 | 4.4 host known only to the CMDB export | build_report_time_and_scope
BLD-09 attempts:4629 T5 | 3.5 placeholder start sentinel | build_report_membership
BLD-09 attempts:0 T10 | 3.6 byte order mark before the control block | selftest_control_chain
BLD-09 attempts:4630 T11 | 4.2 half-open window on corrected start | build_report_time_and_scope
BLD-09 attempts:4324 T13 | 4.3 rewritten commit resolved through Rewritten-From | module_core_bisection
BLD-09 attempts:4492 T7 | 3.1 alias validity window decides the module | build_report_module_identity
BLD-09 attempts:3495 T1 | 3.1 host names are case-insensitive | build_report_time_and_scope
BLD-09 attempts:278 T1 | 3.1 module reference normalisation (NFKC, homoglyphs, case) | build_report_module_identity
BLD-09 attempts:2159 T8 | 3.6 column aliases | build_report_membership
BLD-09 attempts:3732 T1 | 3.1 host names are case-insensitive | build_report_time_and_scope
BLD-10 attempts:380 T1 | 3.1 build key spellings | build_report_membership
BLD-10 attempts:508 T6 | 4.7 latest void action decides | build_report_attempt_precedence
BLD-10 attempts:1251 T8 | 3.6 column aliases | build_report_membership
BLD-10 attempts:1582 T14 | 4.2 branch class from the stage memo register | build_report_time_and_scope
BLD-10 attempts:2089 T3 | 4.4 DST-aware local time conversion | build_report_time_and_scope
BLD-10 attempts:2741 T7 | 4.4 time zone history supersedes the host registry tz | build_report_time_and_scope
BLD-10 attempts:3048 T13 | 4.3 rewritten commit resolved through Rewritten-From | module_core_bisection
BLD-10 attempts:3892 T5 | 3.5 placeholder start sentinel | build_report_membership
BLD-10 attempts:4069 T9 | 3.6 quoted delimiter and newline inside a cell | build_report_membership
BLD-10 attempts:4624 T15 | 4.6 third attempt is valid and may decide | build_report_attempt_precedence
BLD-10 attempts:0 T10 | 3.6 byte order mark before the control block | selftest_control_chain
BLD-10 attempts:2394 T1 | 3.1 cells are stripped of surrounding white space | build_report_membership
BLD-10 attempts:2031 T1 | 3.1 module reference normalisation (NFKC, homoglyphs, case) | build_report_module_identity
BLD-10 attempts:292 T1 | 3.1 host names are case-insensitive | build_report_time_and_scope
BLD-10 attempts:2463 T11 | 4.2 half-open window on corrected start | build_report_time_and_scope
BLD-10 attempts:1001 T3 | 4.4 DST-aware local time conversion | build_report_time_and_scope
BLD-10 attempts:2185 T15 | 4.6 third attempt is valid and may decide | build_report_attempt_precedence
BLD-10 attempts:1432 T7 | 4.4 time zone history supersedes the host registry tz | build_report_time_and_scope
BLD-10 attempts:1588 T6 | 3.6 provisional rows are not attempts | build_report_membership
BLD-10 attempts:3497 T7 | 4.4 time zone history supersedes the host registry tz | build_report_time_and_scope
BLD-11 attempts:3 T7 | 4.4 time zone history supersedes the host registry tz | build_report_time_and_scope
BLD-11 attempts:644 T8 | 3.6 column aliases | build_report_membership
BLD-11 attempts:1219 T6 | 3.6 provisional rows are not attempts | build_report_membership
BLD-11 attempts:1830 T13 | 4.4 host known only to the CMDB export | build_report_time_and_scope
BLD-11 attempts:2088 T1 | 3.1 module reference normalisation (NFKC, homoglyphs, case) | build_report_module_identity
BLD-11 attempts:2855 T14 | 4.2 branch class from the stage memo register | build_report_time_and_scope
BLD-11 attempts:3329 T5 | 3.5 placeholder start sentinel | build_report_membership
BLD-11 attempts:3608 T15 | 4.6 third attempt is valid and may decide | build_report_attempt_precedence
BLD-11 attempts:4216 T3 | 4.4 DST-aware local time conversion | build_report_time_and_scope
BLD-11 attempts:4677 T11 | 4.2 half-open window on corrected start | build_report_time_and_scope
BLD-11 attempts:0 T10 | 3.6 byte order mark before the control block | selftest_control_chain
BLD-11 attempts:2702 T5 | 3.5 placeholder start sentinel | build_report_membership
BLD-11 attempts:3100 T9 | 3.6 quoted delimiter and newline inside a cell | build_report_membership
BLD-11 attempts:3038 T14 | 4.2 branch class from the stage memo register | build_report_time_and_scope
BLD-11 attempts:4183 T8 | 3.6 column aliases | build_report_membership
BLD-11 attempts:4595 T3 | 4.4 DST-aware local time conversion | build_report_time_and_scope
BLD-11 attempts:3684 T7 | 4.5 approved errata correct the attempt | build_report_attempt_precedence
BLD-12 attempts_a:386 T1 | 3.1 host names are case-insensitive | build_report_time_and_scope
BLD-12 attempts_a:776 T15 | 4.6 third attempt is valid and may decide | build_report_attempt_precedence
BLD-12 attempts_a:1140 T6 | 3.6 provisional rows are not attempts | build_report_membership
BLD-12 attempts_a:1601 T13 | 4.4 host known only to the CMDB export | build_report_time_and_scope
BLD-12 attempts_a:2415 T14 | 4.2 branch class from the stage memo register | build_report_time_and_scope
BLD-12 attempts_a:2966 T3 | 4.4 DST-aware local time conversion | build_report_time_and_scope
BLD-12 attempts_a:3255 T7 | 4.4 time zone history supersedes the host registry tz | build_report_time_and_scope
BLD-12 attempts_a:3678 T5 | 3.5 placeholder start sentinel | build_report_membership
BLD-12 attempts_a:4005 T5 | 3.5 placeholder start sentinel | build_report_membership
BLD-12 attempts_a:4629 T6 | 4.7 latest void action decides | build_report_attempt_precedence
BLD-12 attempts_b:146 T6 | 3.6 provisional rows are not attempts | build_report_membership
BLD-12 attempts_b:871 T13 | 4.4 host known only to the CMDB export | build_report_time_and_scope
BLD-12 attempts_b:1347 T6 | 4.7 latest void action decides | build_report_attempt_precedence
BLD-12 attempts_b:1811 T1 | 3.1 module reference normalisation (NFKC, homoglyphs, case) | build_report_module_identity
BLD-12 attempts_b:2443 T1 | 3.1 module reference normalisation (NFKC, homoglyphs, case) | build_report_module_identity
BLD-12 attempts_b:2876 T1 | 3.1 cells are stripped of surrounding white space | build_report_membership
BLD-12 attempts_b:3458 T1 | 3.1 host names are case-insensitive | build_report_time_and_scope
BLD-12 attempts_b:3909 T1 | 3.1 build key spellings | build_report_membership
BLD-12 attempts_b:4315 T7 | 4.4 time zone history supersedes the host registry tz | build_report_time_and_scope
BLD-12 attempts_b:4830 T11 | 4.2 half-open window on corrected start | build_report_time_and_scope
BLD-13 attempts_a:57 T1 | 3.1 build key spellings | build_report_membership
BLD-13 attempts_a:877 T14 | 4.2 branch class from the stage memo register | build_report_time_and_scope
BLD-13 attempts_a:1095 T6 | 4.7 latest void action decides | build_report_attempt_precedence
BLD-13 attempts_a:1885 T13 | 4.4 host known only to the CMDB export | build_report_time_and_scope
BLD-13 attempts_a:2384 T3 | 4.4 DST-aware local time conversion | build_report_time_and_scope
BLD-13 attempts_a:2706 T7 | 4.4 time zone history supersedes the host registry tz | build_report_time_and_scope
BLD-13 attempts_a:3252 T11 | 4.2 half-open window on corrected start | build_report_time_and_scope
BLD-13 attempts_a:3794 T15 | 4.6 third attempt is valid and may decide | build_report_attempt_precedence
BLD-13 attempts_a:4232 T5 | 3.5 placeholder start sentinel | build_report_membership
BLD-13 attempts_a:4679 T7 | 4.1 exporter rank decides between copies | build_report_attempt_precedence
BLD-13 attempts_b:464 T7 | 4.1 higher revision of the same exporter supersedes | build_report_attempt_precedence
BLD-13 attempts_b:564 T3 | 4.4 DST-aware local time conversion | build_report_time_and_scope
BLD-13 attempts_b:1052 T6 | 4.1 rows of revoked export jobs are void | build_report_attempt_precedence
BLD-13 attempts_b:1920 T1 | 3.1 build key spellings | build_report_membership
BLD-13 attempts_b:2248 T1 | 3.1 build key spellings | build_report_membership
BLD-13 attempts_b:2957 T1 | 3.1 host names are case-insensitive | build_report_time_and_scope
BLD-13 attempts_b:3227 T1 | 3.1 module reference normalisation (NFKC, homoglyphs, case) | build_report_module_identity
BLD-13 attempts_b:3893 T15 | 4.6 third attempt is valid and may decide | build_report_attempt_precedence
BLD-13 attempts_b:4111 T1 | 3.1 cells are stripped of surrounding white space | build_report_membership
BLD-13 attempts_b:4623 T1 | 3.1 cells are stripped of surrounding white space | build_report_membership
BLD-14 attempts_a:367 T1 | 3.1 cells are stripped of surrounding white space | build_report_membership
BLD-14 attempts_a:844 T15 | 4.6 third attempt is valid and may decide | build_report_attempt_precedence
BLD-14 attempts_a:1315 T3 | 4.4 DST-aware local time conversion | build_report_time_and_scope
BLD-14 attempts_a:1529 T14 | 4.2 branch class from the stage memo register | build_report_time_and_scope
BLD-14 attempts_a:2466 T6 | 4.1 rows of revoked export jobs are void | build_report_attempt_precedence
BLD-14 attempts_a:2899 T7 | 4.4 time zone history supersedes the host registry tz | build_report_time_and_scope
BLD-14 attempts_a:3115 T13 | 4.4 host known only to the CMDB export | build_report_time_and_scope
BLD-14 attempts_a:3755 T5 | 3.5 placeholder start sentinel | build_report_membership
BLD-14 attempts_a:4329 T14 | 4.2 branch class from the stage memo register | build_report_time_and_scope
BLD-14 attempts_a:4796 T1 | 3.1 cells are stripped of surrounding white space | build_report_membership
BLD-14 attempts_b:487 T1 | 3.1 host names are case-insensitive | build_report_time_and_scope
BLD-14 attempts_b:926 T11 | 4.2 half-open window on corrected start | build_report_time_and_scope
BLD-14 attempts_b:1067 T14 | 4.2 branch class from the stage memo register | build_report_time_and_scope
BLD-14 attempts_b:1635 T14 | 4.2 branch class from the stage memo register | build_report_time_and_scope
BLD-14 attempts_b:2094 T1 | 3.1 build key spellings | build_report_membership
BLD-14 attempts_b:2708 T14 | 4.2 branch class from the stage memo register | build_report_time_and_scope
BLD-14 attempts_b:3185 T15 | 4.6 third attempt is valid and may decide | build_report_attempt_precedence
BLD-14 attempts_b:3764 T7 | 4.1 exporter rank decides between copies | build_report_attempt_precedence
BLD-14 attempts_b:4204 T1 | 3.1 module reference normalisation (NFKC, homoglyphs, case) | build_report_module_identity
BLD-14 attempts_b:4770 T1 | 3.1 cells are stripped of surrounding white space | build_report_membership
BLD-15 attempts:234 T12 | E6 microseconds round half to even at the millisecond | build_report_units_and_sentinels
BLD-15 attempts:794 T2 | 3.3 unit suffix overrides the column unit | build_report_units_and_sentinels
BLD-15 attempts:1066 T8 | 3.6 column aliases | build_report_membership
BLD-15 attempts:1783 T14 | G3 lab pool excluded by governance footnote | build_report_time_and_scope
BLD-15 attempts:2414 T6 | 4.7 latest void action decides | build_report_attempt_precedence
BLD-15 attempts:2767 T3 | 4.4 DST-aware local time conversion | build_report_time_and_scope
BLD-15 attempts:3479 T1 | 3.1 module reference normalisation (NFKC, homoglyphs, case) | build_report_module_identity
BLD-15 attempts:3543 T13 | 4.4 host known only to the CMDB export | build_report_time_and_scope
BLD-15 attempts:4458 T7 | 4.4 time zone history supersedes the host registry tz | build_report_time_and_scope
BLD-15 attempts:4962 T5 | 3.5 placeholder start sentinel | build_report_membership
BLD-15 attempts:3705 T9 | 3.6 quoted delimiter and newline inside a cell | build_report_membership
BLD-15 attempts:4360 T11 | 4.2 half-open window on corrected start | build_report_time_and_scope
BLD-15 attempts:2586 T15 | 4.6 third attempt is valid and may decide | build_report_attempt_precedence
BLD-15 attempts:4897 T12 | E6 microseconds round half to even at the millisecond | build_report_units_and_sentinels
BLD-15 attempts:3069 T8 | 3.6 column aliases | build_report_membership
BLD-15 attempts:4310 T2 | 3.3 unit suffix overrides the column unit | build_report_units_and_sentinels
BLD-15 attempts:2107 T2 | 3.3 unit suffix overrides the column unit | build_report_units_and_sentinels
BLD-15 attempts:2004 T2 | 3.3 unit suffix overrides the column unit | build_report_units_and_sentinels
BLD-16 attempts:293 T2 | 3.3 unit suffix overrides the column unit | build_report_units_and_sentinels
BLD-16 attempts:630 T12 | E6 microseconds round half to even at the millisecond | build_report_units_and_sentinels
BLD-16 attempts:1294 T8 | 3.6 column aliases | build_report_membership
BLD-16 attempts:1994 T5 | 3.5 placeholder start sentinel | build_report_membership
BLD-16 attempts:2170 T7 | 4.4 time zone history supersedes the host registry tz | build_report_time_and_scope
BLD-16 attempts:2583 T1 | 3.1 build key spellings | build_report_membership
BLD-16 attempts:3222 T14 | 4.2 branch class from the stage memo register | build_report_time_and_scope
BLD-16 attempts:3685 T3 | 4.4 DST-aware local time conversion | build_report_time_and_scope
BLD-16 attempts:4257 T13 | 4.4 host known only to the CMDB export | build_report_time_and_scope
BLD-16 attempts:4782 T9 | 3.6 quoted delimiter and newline inside a cell | build_report_membership
BLD-16 attempts:870 T15 | 4.6 third attempt is valid and may decide | build_report_attempt_precedence
BLD-16 attempts:774 T6 | 3.6 provisional rows are not attempts | build_report_membership
BLD-16 attempts:1856 T12 | E6 microseconds round half to even at the millisecond | build_report_units_and_sentinels
BLD-16 attempts:858 T2 | 3.3 unit suffix overrides the column unit | build_report_units_and_sentinels
BLD-16 attempts:889 T2 | 3.3 unit suffix overrides the column unit | build_report_units_and_sentinels
BLD-16 attempts:2067 T2 | 3.3 unit suffix overrides the column unit | build_report_units_and_sentinels
BLD-16 attempts:387 T12 | E6 microseconds round half to even at the millisecond | build_report_units_and_sentinels
BLD-17 attempts:398 T2 | 3.3 unit suffix overrides the column unit | build_report_units_and_sentinels
BLD-17 attempts:529 T8 | 3.6 column aliases | build_report_membership
BLD-17 attempts:1018 T12 | E6 microseconds round half to even at the millisecond | build_report_units_and_sentinels
BLD-17 attempts:1827 T11 | 4.2 half-open window on corrected start | build_report_time_and_scope
BLD-17 attempts:2363 T1 | 3.1 host names are case-insensitive | build_report_time_and_scope
BLD-17 attempts:2729 T3 | 4.4 DST-aware local time conversion | build_report_time_and_scope
BLD-17 attempts:3337 T7 | 4.1 exporter rank decides between copies | build_report_attempt_precedence
BLD-17 attempts:3882 T6 | 4.7 latest void action decides | build_report_attempt_precedence
BLD-17 attempts:4043 T14 | 4.2 branch class from the stage memo register | build_report_time_and_scope
BLD-17 attempts:4745 T9 | 3.6 quoted delimiter and newline inside a cell | build_report_membership
BLD-17 attempts:3643 T13 | 4.4 host known only to the CMDB export | build_report_time_and_scope
BLD-17 attempts:4926 T5 | 3.5 placeholder start sentinel | build_report_membership
BLD-17 attempts:2844 T15 | 4.6 third attempt is valid and may decide | build_report_attempt_precedence
BLD-17 attempts:491 T2 | 3.3 unit suffix overrides the column unit | build_report_units_and_sentinels
BLD-17 attempts:1384 T2 | 3.3 unit suffix overrides the column unit | build_report_units_and_sentinels
BLD-17 attempts:1086 T8 | 3.6 column aliases | build_report_membership
BLD-18 attempts:360 T3 | 4.4 DST-aware local time conversion | build_report_time_and_scope
BLD-18 attempts:660 T1 | 3.1 cells are stripped of surrounding white space | build_report_membership
BLD-18 attempts:1390 T7 | 4.4 time zone history supersedes the host registry tz | build_report_time_and_scope
BLD-18 attempts:1658 T6 | 4.1 rows of revoked export jobs are void | build_report_attempt_precedence
BLD-18 attempts:2284 T13 | 4.4 host known only to the CMDB export | build_report_time_and_scope
BLD-18 attempts:2640 T14 | 4.2 branch class from the stage memo register | build_report_time_and_scope
BLD-18 attempts:3385 T15 | 4.6 third attempt is valid and may decide | build_report_attempt_precedence
BLD-18 attempts:3779 T5 | 3.5 placeholder start sentinel | build_report_membership
BLD-18 attempts:4406 T7 | 4.4 time zone history supersedes the host registry tz | build_report_time_and_scope
BLD-18 attempts:4940 T1 | 3.1 host names are case-insensitive | build_report_time_and_scope
BLD-18 attempts:2251 T11 | 4.2 half-open window on corrected start | build_report_time_and_scope
BLD-18 attempts:2237 T14 | 4.2 branch class from the stage memo register | build_report_time_and_scope
BLD-18 attempts:590 T3 | 4.4 DST-aware local time conversion | build_report_time_and_scope
BLD-18 attempts:2596 T13 | 4.4 host known only to the CMDB export | build_report_time_and_scope
BLD-18 attempts:3715 T6 | 4.7 latest void action decides | build_report_attempt_precedence
BLD-18 attempts:1989 T1 | 3.1 cells are stripped of surrounding white space | build_report_membership
BLD-19 attempts:463 T1 | 3.1 host names are case-insensitive | build_report_time_and_scope
BLD-19 attempts:965 T3 | 4.4 DST-aware local time conversion | build_report_time_and_scope
BLD-19 attempts:1196 T5 | 3.5 placeholder start sentinel | build_report_membership
BLD-19 attempts:1826 T6 | 3.6 provisional rows are not attempts | build_report_membership
BLD-19 attempts:2015 T14 | 4.2 branch class from the stage memo register | build_report_time_and_scope
BLD-19 attempts:2871 T13 | 4.4 host known only to the CMDB export | build_report_time_and_scope
BLD-19 attempts:3224 T7 | 4.1 exporter rank decides between copies | build_report_attempt_precedence
BLD-19 attempts:3516 T15 | 4.6 third attempt is valid and may decide | build_report_attempt_precedence
BLD-19 attempts:4122 T1 | 3.1 build key spellings | build_report_membership
BLD-19 attempts:4691 T14 | 4.2 branch class from the stage memo register | build_report_time_and_scope
BLD-19 attempts:1309 T15 | valid long-running build is not an outlier to drop | module_metrics_counts_and_rates
BLD-19 attempts:4362 T11 | 4.2 half-open window on corrected start | build_report_time_and_scope
BLD-19 attempts:4677 T14 | G3 lab pool excluded by governance footnote | build_report_time_and_scope
BLD-19 attempts:439 T5 | 3.5 placeholder start sentinel | build_report_membership
BLD-19 attempts:946 T1 | 3.1 build key spellings | build_report_membership
BLD-19 attempts:2278 T6 | 3.6 provisional rows are not attempts | build_report_membership
BLD-20 attempts:497 T12 | E6 microseconds round half to even at the millisecond | build_report_units_and_sentinels
BLD-20 attempts:598 T2 | 3.3 unit suffix overrides the column unit | build_report_units_and_sentinels
BLD-20 attempts:1127 T14 | 4.2 branch class from the stage memo register | build_report_time_and_scope
BLD-20 attempts:1828 T1 | 3.1 module reference normalisation (NFKC, homoglyphs, case) | build_report_module_identity
BLD-20 attempts:2485 T8 | 3.6 restated header row inside a document table | build_report_membership
BLD-20 attempts:2689 T11 | 4.2 half-open window on corrected start | build_report_time_and_scope
BLD-20 attempts:3389 T5 | 3.5 placeholder start sentinel | build_report_membership
BLD-20 attempts:3666 T13 | 4.3 rewritten commit resolved through Rewritten-From | module_core_bisection
BLD-20 attempts:4378 T15 | 4.6 third attempt is valid and may decide | build_report_attempt_precedence
BLD-20 attempts:4504 T7 | 3.1 alias validity window decides the module | build_report_module_identity
BLD-20 attempts:4555 T3 | 4.4 DST-aware local time conversion | build_report_time_and_scope
BLD-20 attempts:2717 T6 | 4.7 latest void action decides | build_report_attempt_precedence
BLD-20 attempts:1423 T12 | E6 microseconds round half to even at the millisecond | build_report_units_and_sentinels
BLD-20 attempts:4467 T8 | 3.6 restated header row inside a document table | build_report_membership
BLD-20 attempts:3465 T2 | 3.3 unit suffix overrides the column unit | build_report_units_and_sentinels
BLD-20 attempts:728 T2 | 3.3 unit suffix overrides the column unit | build_report_units_and_sentinels
BLD-20 attempts:2754 T2 | 3.3 unit suffix overrides the column unit | build_report_units_and_sentinels
BLD-21 attempts:117 T2 | 3.3 unit suffix overrides the column unit | build_report_units_and_sentinels
BLD-21 attempts:670 T12 | E6 microseconds round half to even at the millisecond | build_report_units_and_sentinels
BLD-21 attempts:1025 T8 | 3.6 restated header row inside a document table | build_report_membership
BLD-21 attempts:1927 T1 | 3.1 cells are stripped of surrounding white space | build_report_membership
BLD-21 attempts:2187 T14 | 4.2 branch class from the stage memo register | build_report_time_and_scope
BLD-21 attempts:2700 T3 | 4.4 DST-aware local time conversion | build_report_time_and_scope
BLD-21 attempts:3083 T5 | 3.5 placeholder start sentinel | build_report_membership
BLD-21 attempts:3649 T6 | 3.6 provisional rows are not attempts | build_report_membership
BLD-21 attempts:4365 T15 | 4.6 third attempt is valid and may decide | build_report_attempt_precedence
BLD-21 attempts:4652 T7 | 3.1 alias validity window decides the module | build_report_module_identity
BLD-21 attempts:4808 T13 | 4.3 rewritten commit resolved through Rewritten-From | module_core_bisection
BLD-21 attempts:2115 T2 | 3.3 unit suffix overrides the column unit | build_report_units_and_sentinels
BLD-21 attempts:3358 T2 | 3.3 unit suffix overrides the column unit | build_report_units_and_sentinels
BLD-21 attempts:1328 T2 | 3.3 unit suffix overrides the column unit | build_report_units_and_sentinels
BLD-21 attempts:1102 T12 | E6 microseconds round half to even at the millisecond | build_report_units_and_sentinels
BLD-21 attempts:4791 T11 | 4.2 half-open window on corrected start | build_report_time_and_scope
BLD-21 attempts:1393 T1 | 3.1 build key spellings | build_report_membership
BLD-21 attempts:1853 T2 | 3.3 unit suffix overrides the column unit | build_report_units_and_sentinels
BLD-22 attempts:438 T6 | 4.7 latest void action decides | build_report_attempt_precedence
BLD-22 attempts:704 T13 | 4.4 host known only to the CMDB export | build_report_time_and_scope
BLD-22 attempts:1103 T1 | 3.1 module reference normalisation (NFKC, homoglyphs, case) | build_report_module_identity
BLD-22 attempts:1747 T3 | 4.4 DST-aware local time conversion | build_report_time_and_scope
BLD-22 attempts:2400 T5 | 3.5 placeholder start sentinel | build_report_membership
BLD-22 attempts:2590 T14 | 4.2 branch class from the stage memo register | build_report_time_and_scope
BLD-22 attempts:3232 T15 | 4.6 third attempt is valid and may decide | build_report_attempt_precedence
BLD-22 attempts:3974 T7 | 4.5 approved errata correct the attempt | build_report_attempt_precedence
BLD-22 attempts:4185 T14 | 4.2 branch class from the stage memo register | build_report_time_and_scope
BLD-22 attempts:4572 T1 | 3.1 cells are stripped of surrounding white space | build_report_membership
BLD-22 attempts:3366 T1 | 3.1 host names are case-insensitive | build_report_time_and_scope
BLD-22 attempts:206 T14 | 4.2 branch class from the stage memo register | build_report_time_and_scope
BLD-22 attempts:1958 T14 | G3 lab pool excluded by governance footnote | build_report_time_and_scope
BLD-22 attempts:3762 T11 | 4.2 half-open window on corrected start | build_report_time_and_scope
BLD-22 attempts:2989 T15 | valid long-running build is not an outlier to drop | module_metrics_counts_and_rates
BLD-22 attempts:3624 T13 | G4 in-window rename from the next-quarter registry | build_report_module_identity
BLD-22 attempts:4898 T7 | 4.1 exporter rank decides between copies | build_report_attempt_precedence
BLD-23 attempts:87 T2 | 3.3 unit suffix overrides the column unit | build_report_units_and_sentinels
BLD-23 attempts:824 T12 | E6 microseconds round half to even at the millisecond | build_report_units_and_sentinels
BLD-23 attempts:1242 T8 | 3.6 restated header row inside a document table | build_report_membership
BLD-23 attempts:1819 T14 | 4.2 branch class from the stage memo register | build_report_time_and_scope
BLD-23 attempts:2381 T1 | 3.1 host names are case-insensitive | build_report_time_and_scope
BLD-23 attempts:2603 T6 | 4.1 rows of revoked export jobs are void | build_report_attempt_precedence
BLD-23 attempts:3088 T13 | 4.4 host known only to the CMDB export | build_report_time_and_scope
BLD-23 attempts:3956 T7 | 4.1 higher revision of the same exporter supersedes | build_report_attempt_precedence
BLD-23 attempts:4123 T5 | 3.5 placeholder start sentinel | build_report_membership
BLD-23 attempts:4743 T3 | 4.4 DST-aware local time conversion | build_report_time_and_scope
BLD-23 attempts:1634 T15 | 4.6 third attempt is valid and may decide | build_report_attempt_precedence
BLD-23 attempts:558 T8 | 3.6 restated header row inside a document table | build_report_membership
BLD-23 attempts:1110 T11 | 4.2 half-open window on corrected start | build_report_time_and_scope
BLD-23 attempts:4367 T12 | E6 microseconds round half to even at the millisecond | build_report_units_and_sentinels
BLD-23 attempts:364 T3 | 3.4 explicit offset makes a timestamp absolute | build_report_time_and_scope
BLD-23 attempts:499 T2 | 3.3 unit suffix overrides the column unit | build_report_units_and_sentinels
BLD-23 attempts:2813 T12 | E6 microseconds round half to even at the millisecond | build_report_units_and_sentinels
BLD-24 attempts:222 T4 | 3.2 thousands separator | build_report_units_and_sentinels
BLD-24 attempts:665 T10 | 3.6 cp1252 line with the micro sign | build_report_units_and_sentinels
BLD-24 attempts:1121 T12 | E6 microseconds round half to even at the millisecond | build_report_units_and_sentinels
BLD-24 attempts:1752 T2 | 3.3 unit suffix overrides the column unit | build_report_units_and_sentinels
BLD-24 attempts:2115 T13 | 4.4 host known only to the CMDB export | build_report_time_and_scope
BLD-24 attempts:2570 T15 | 4.6 third attempt is valid and may decide | build_report_attempt_precedence
BLD-24 attempts:3390 T6 | 4.7 latest void action decides | build_report_attempt_precedence
BLD-24 attempts:3852 T14 | 4.2 branch class from the stage memo register | build_report_time_and_scope
BLD-24 attempts:4194 T1 | 3.1 module reference normalisation (NFKC, homoglyphs, case) | build_report_module_identity
BLD-24 attempts:4568 T3 | 4.4 DST-aware local time conversion | build_report_time_and_scope
BLD-24 attempts:4976 T5 | 3.5 placeholder start sentinel | build_report_membership
BLD-24 attempts:1521 T7 | 4.5 approved errata correct the attempt | build_report_attempt_precedence
BLD-24 attempts:4692 T11 | 4.2 half-open window on corrected start | build_report_time_and_scope
BLD-24 attempts:3806 T4 | 3.2 thousands separator | build_report_units_and_sentinels
BLD-24 attempts:4592 T4 | 3.2 thousands separator | build_report_units_and_sentinels
BLD-24 attempts:2490 T4 | 3.2 thousands separator | build_report_units_and_sentinels
BLD-25 attempts:17 T4 | 3.2 thousands separator | build_report_units_and_sentinels
BLD-25 attempts:775 T10 | 3.6 cp1252 line with the micro sign | build_report_units_and_sentinels
BLD-25 attempts:1193 T12 | E6 microseconds round half to even at the millisecond | build_report_units_and_sentinels
BLD-25 attempts:1507 T15 | 4.6 third attempt is valid and may decide | build_report_attempt_precedence
BLD-25 attempts:2250 T2 | 3.3 unit suffix overrides the column unit | build_report_units_and_sentinels
BLD-25 attempts:2640 T13 | 3.1 legacy key resolved through spec appendix F | build_report_membership
BLD-25 attempts:3141 T1 | 3.1 host names are case-insensitive | build_report_time_and_scope
BLD-25 attempts:3993 T11 | 4.2 half-open window on corrected start | build_report_time_and_scope
BLD-25 attempts:4158 T14 | G3 lab pool excluded by governance footnote | build_report_time_and_scope
BLD-25 attempts:4686 T3 | 3.4 explicit offset makes a timestamp absolute | build_report_time_and_scope
BLD-25 attempts:0 T10 | 3.6 byte order mark before the control block | selftest_control_chain
BLD-25 attempts:4983 T7 | 4.4 time zone history supersedes the host registry tz | build_report_time_and_scope
BLD-25 attempts:1661 T6 | 4.7 latest void action decides | build_report_attempt_precedence
BLD-25 attempts:2630 T5 | 3.5 placeholder start sentinel | build_report_membership
BLD-25 attempts:2482 T4 | 3.2 thousands separator | build_report_units_and_sentinels
BLD-25 attempts:3306 T10 | 3.6 cp1252 line with the micro sign | build_report_units_and_sentinels
BLD-25 attempts:3822 T4 | 3.2 thousands separator | build_report_units_and_sentinels
BLD-25 attempts:3437 T4 | 3.2 thousands separator | build_report_units_and_sentinels
BLD-25 attempts:2256 T10 | 3.6 cp1252 line with the micro sign | build_report_units_and_sentinels
AGT-01 attempts:23 T12 | E6 microseconds round half to even at the millisecond | build_report_units_and_sentinels
AGT-01 attempts:918 T2 | 3.3 unit suffix overrides the column unit | build_report_units_and_sentinels
AGT-01 attempts:1016 T3 | 4.4 DST-aware local time conversion | build_report_time_and_scope
AGT-01 attempts:1954 T1 | 3.1 build key spellings | build_report_membership
AGT-01 attempts:2481 T7 | 3.1 alias validity window decides the module | build_report_module_identity
AGT-01 attempts:2964 T6 | 4.7 latest void action decides | build_report_attempt_precedence
AGT-01 attempts:3458 T5 | 3.5 placeholder start sentinel | build_report_membership
AGT-01 attempts:3701 T14 | 4.2 branch class from the stage memo register | build_report_time_and_scope
AGT-01 attempts:4492 T13 | G4 in-window rename from the next-quarter registry | build_report_module_identity
AGT-01 attempts:4892 T15 | 4.6 third attempt is valid and may decide | build_report_attempt_precedence
AGT-01 attempts:1539 T2 | 3.3 unit suffix overrides the column unit | build_report_units_and_sentinels
AGT-01 attempts:2909 T2 | 3.3 unit suffix overrides the column unit | build_report_units_and_sentinels
AGT-01 attempts:3524 T12 | E6 microseconds round half to even at the millisecond | build_report_units_and_sentinels
AGT-01 attempts:4145 T12 | E6 microseconds round half to even at the millisecond | build_report_units_and_sentinels
AGT-01 attempts:1054 T2 | 3.3 unit suffix overrides the column unit | build_report_units_and_sentinels
AGT-01 attempts:4259 T11 | 4.2 half-open window on corrected start | build_report_time_and_scope
AGT-01 attempts:4119 T2 | 3.3 unit suffix overrides the column unit | build_report_units_and_sentinels
AGT-01 attempts:1336 T5 | 3.5 placeholder start sentinel | build_report_membership
AGT-01 attempts:1671 T12 | E6 microseconds round half to even at the millisecond | build_report_units_and_sentinels
AGT-01 attempts:4928 T2 | 3.3 unit suffix overrides the column unit | build_report_units_and_sentinels
AGT-02 attempts:447 T2 | 3.3 unit suffix overrides the column unit | build_report_units_and_sentinels
AGT-02 attempts:505 T12 | E6 microseconds round half to even at the millisecond | build_report_units_and_sentinels
AGT-02 attempts:1399 T1 | 3.1 build key spellings | build_report_membership
AGT-02 attempts:1946 T14 | 4.2 branch class from the stage memo register | build_report_time_and_scope
AGT-02 attempts:2481 T3 | 3.4 explicit offset makes a timestamp absolute | build_report_time_and_scope
AGT-02 attempts:2877 T13 | 4.4 host known only to the CMDB export | build_report_time_and_scope
AGT-02 attempts:3255 T7 | 4.5 approved errata correct the attempt | build_report_attempt_precedence
AGT-02 attempts:3535 T6 | 3.6 provisional rows are not attempts | build_report_membership
AGT-02 attempts:4257 T15 | 4.6 third attempt is valid and may decide | build_report_attempt_precedence
AGT-02 attempts:4770 T5 | 3.5 placeholder start sentinel | build_report_membership
AGT-02 attempts:164 T11 | 4.2 half-open window on corrected start | build_report_time_and_scope
AGT-02 attempts:3510 T2 | 3.3 unit suffix overrides the column unit | build_report_units_and_sentinels
AGT-02 attempts:512 T1 | 3.1 build key spellings | build_report_membership
AGT-02 attempts:4730 T2 | 3.3 unit suffix overrides the column unit | build_report_units_and_sentinels
AGT-02 attempts:4943 T1 | 3.1 build key spellings | build_report_membership
AGT-02 attempts:4159 T12 | E6 microseconds round half to even at the millisecond | build_report_units_and_sentinels
AGT-02 attempts:4808 T2 | 3.3 unit suffix overrides the column unit | build_report_units_and_sentinels
AGT-02 attempts:1276 T12 | E6 microseconds round half to even at the millisecond | build_report_units_and_sentinels
AGT-02 attempts:3418 T13 | 4.4 host known only to the CMDB export | build_report_time_and_scope
AGT-02 attempts:657 T2 | 3.3 unit suffix overrides the column unit | build_report_units_and_sentinels
DCY-03 attempts:78 T16 pull | G5 mirror copy disagrees on a non-authoritative row | build_report_membership
DCY-03 attempts:635 T4 push | 3.2 thousands separator | build_report_units_and_sentinels
DCY-03 attempts:1167 T10 push | 3.6 cp1252 line with the micro sign | build_report_units_and_sentinels
DCY-03 attempts:1917 T8 push | 3.6 #header restates reordered columns | build_report_membership
DCY-03 attempts:2322 T9 push | 3.6 ragged row with trailing empty cells | build_report_membership
DCY-03 attempts:2753 T12 push | E6 microseconds round half to even at the millisecond | build_report_units_and_sentinels
DCY-03 attempts:3141 T2 push | 3.3 unit suffix overrides the column unit | build_report_units_and_sentinels
DCY-03 attempts:3735 T7 pull | 4.4 time zone history supersedes the host registry tz | build_report_time_and_scope
DCY-03 attempts:4458 T14 push | 4.2 branch class from the stage memo register | build_report_time_and_scope
DCY-03 attempts:4970 T13 pull | 4.4 host known only to the CMDB export | build_report_time_and_scope
DCY-03 attempts:1104 T6 push | G5 rows of non-eph hosts are ignored | build_report_membership
DCY-03 attempts:2344 T1 push | 3.1 build key spellings | build_report_membership
DCY-03 attempts:3590 T3 pull | 4.4 DST-aware local time conversion | build_report_time_and_scope
DCY-03 attempts:3408 T15 pull | 4.6 third attempt is valid and may decide | build_report_attempt_precedence
DCY-03 attempts:2732 T16 pull | G5 mirror copy disagrees on a non-authoritative row | build_report_membership
DCY-03 attempts:4174 T11 pull | 4.2 half-open window on corrected start | build_report_time_and_scope
DCY-03 attempts:35 T16 pull | G5 non-eph mirror rows are out of scope | build_report_membership
DCY-03 attempts:3528 T16 pull | G5 non-eph mirror rows are out of scope | build_report_membership
DCY-03 attempts:1093 T16 pull | G5 non-eph mirror rows are out of scope | build_report_membership
DCY-03 attempts:1760 T16 pull | G5 mirror copy disagrees on a non-authoritative row | build_report_membership
DCY-03 attempts:4941 T16 pull | G5 non-eph mirror rows are out of scope | build_report_membership
DCY-03 attempts:4444 T16 pull | G5 non-eph mirror rows are out of scope | build_report_membership
DCY-03 attempts:4263 T16 pull | G5 mirror copy disagrees on a non-authoritative row | build_report_membership
DCY-03 attempts:2985 T5 push | 3.5 duration sentinel means unknown | build_report_units_and_sentinels
DCY-03 attempts:4423 T16 pull | G5 mirror copy disagrees on a non-authoritative row | build_report_membership
DCY-03 attempts:472 T16 pull | G5 mirror copy disagrees on a non-authoritative row | build_report_membership
DCY-03 attempts:4971 T16 pull | G5 mirror copy disagrees on a non-authoritative row | build_report_membership
DCY-03 attempts:2649 T16 pull | G5 non-eph mirror rows are out of scope | build_report_membership
DCY-03 attempts:2232 T16 pull | G5 mirror copy disagrees on a non-authoritative row | build_report_membership
DCY-03 attempts:2635 T16 pull | G5 mirror copy disagrees on a non-authoritative row | build_report_membership
DCY-03 attempts:4639 T16 pull | G5 mirror copy disagrees on a non-authoritative row | build_report_membership
DCY-03 attempts:2468 T16 pull | G5 mirror copy disagrees on a non-authoritative row | build_report_membership
DCY-03 attempts:2043 T16 pull | G5 non-eph mirror rows are out of scope | build_report_membership
DCY-03 attempts:4650 T16 pull | G5 non-eph mirror rows are out of scope | build_report_membership
TST-01 results:115 T4 | 3.2 thousands separator | build_report_units_and_sentinels
TST-01 results:555 T9 | 3.6 ragged row with trailing empty cells | module_metrics_flaky_and_quarantine
TST-01 results:1446 T10 | 3.6 cp1252 line with the micro sign | build_report_units_and_sentinels
TST-01 results:1651 T6 | 5.4 quarantine state at the attempt start | module_metrics_flaky_and_quarantine
TST-01 results:2253 T2 | 3.3 unit suffix overrides the column unit | build_report_units_and_sentinels
TST-01 results:2652 T12 | E6 microseconds round half to even at the millisecond | build_report_units_and_sentinels
TST-01 results:3235 T11 | 5.2 registration window on corrected start | module_metrics_counts_and_rates
TST-01 results:3753 T8 | 3.6 #header restates reordered columns | module_metrics_flaky_and_quarantine
TST-01 results:4380 T1 | 3.1 cells are stripped of surrounding white space | module_metrics_flaky_and_quarantine
TST-01 results:4868 T15 | 5.3 mixed outcomes at one commit mark a flaky test | module_metrics_flaky_and_quarantine
TST-01 results:1341 T13 | 6.1 crash stack located by crash id | build_report_crash_buckets
TST-01 results:2597 T7 | 5.1 exporter rank decides between result copies | module_metrics_flaky_and_quarantine
TST-01 results:1566 T4 | 3.2 thousands separator | build_report_units_and_sentinels
TST-01 results:3238 T4 | 3.2 thousands separator | build_report_units_and_sentinels
TST-01 results:528 T4 | 3.2 thousands separator | build_report_units_and_sentinels
TST-01 results:1850 T10 | 3.6 cp1252 line with the micro sign | build_report_units_and_sentinels
TST-01 results:866 T4 | 3.2 thousands separator | build_report_units_and_sentinels
TST-02 results:300 T4 | 3.2 thousands separator | build_report_units_and_sentinels
TST-02 results:541 T10 | 3.6 cp1252 line with the micro sign | build_report_units_and_sentinels
TST-02 results:1003 T2 | 3.3 unit suffix overrides the column unit | build_report_units_and_sentinels
TST-02 results:1718 T9 | 3.6 ragged row with trailing empty cells | module_metrics_flaky_and_quarantine
TST-02 results:2108 T12 | E6 microseconds round half to even at the millisecond | build_report_units_and_sentinels
TST-02 results:2913 T8 | 3.6 #header restates reordered columns | module_metrics_flaky_and_quarantine
TST-02 results:3195 T6 | 3.6 provisional rows are not results | module_metrics_counts_and_rates
TST-02 results:3847 T15 | 5.3 mixed outcomes at one commit mark a flaky test | module_metrics_flaky_and_quarantine
TST-02 results:4491 T1 | 3.1 build key spellings | build_report_membership
TST-02 results:4913 T13 | 6.1 crash stack located by crash id | build_report_crash_buckets
TST-02 results:0 T10 | 3.6 byte order mark before the control block | selftest_control_chain
TST-02 results:2262 T11 | 5.2 registration window on corrected start | module_metrics_counts_and_rates
TST-02 results:292 T4 | 3.2 thousands separator | build_report_units_and_sentinels
TST-02 results:1590 T10 | 3.6 cp1252 line with the micro sign | build_report_units_and_sentinels
TST-02 results:317 T4 | 3.2 thousands separator | build_report_units_and_sentinels
TST-02 results:667 T4 | 3.2 thousands separator | build_report_units_and_sentinels
TST-03 results:52 T4 | 3.2 thousands separator | build_report_units_and_sentinels
TST-03 results:846 T10 | 3.6 cp1252 line with the micro sign | build_report_units_and_sentinels
TST-03 results:1168 T6 | 5.4 quarantine state at the attempt start | module_metrics_flaky_and_quarantine
TST-03 results:12 T7 | 5.1 same rank and same rev as an earlier copy: the row read first wins | build_report_attempt_precedence
TST-03 results:1582 T9 | 3.6 ragged row with trailing empty cells | module_metrics_flaky_and_quarantine
TST-03 results:2258 T15 | 5.3 mixed outcomes at one commit mark a flaky test | module_metrics_flaky_and_quarantine
TST-03 results:2907 T8 | 3.6 #header restates reordered columns | module_metrics_flaky_and_quarantine
TST-03 results:3413 T12 | E6 microseconds round half to even at the millisecond | build_report_units_and_sentinels
TST-03 results:3688 T2 | 3.3 unit suffix overrides the column unit | build_report_units_and_sentinels
TST-03 results:4104 T1 | 3.1 cells are stripped of surrounding white space | module_metrics_flaky_and_quarantine
TST-03 results:4773 T13 | 6.1 crash stack located by crash id | build_report_crash_buckets
TST-03 results:1679 T11 | 5.2 registration window on corrected start | module_metrics_counts_and_rates
TST-03 results:2539 T7 | 5.1 exporter rank decides between result copies | module_metrics_flaky_and_quarantine
TST-03 results:4725 T9 | 3.6 ragged row with trailing empty cells | module_metrics_flaky_and_quarantine
TST-03 results:2946 T8 | 3.6 #header restates reordered columns | module_metrics_flaky_and_quarantine
TST-03 results:2902 T4 | 3.2 thousands separator | build_report_units_and_sentinels
TST-03 results:3588 T10 | 3.6 cp1252 line with the micro sign | build_report_units_and_sentinels
TST-03 results:377 T4 | 3.2 thousands separator | build_report_units_and_sentinels
TST-04 results:340 T4 | 3.2 thousands separator | build_report_units_and_sentinels
TST-04 results:984 T9 | 3.6 ragged row with trailing empty cells | module_metrics_flaky_and_quarantine
TST-04 results:1110 T2 | 3.3 unit suffix overrides the column unit | build_report_units_and_sentinels
TST-04 results:1761 T8 | 3.6 #header restates reordered columns | module_metrics_flaky_and_quarantine
TST-04 results:2237 T7 | 5.1 exporter rank decides between result copies | module_metrics_flaky_and_quarantine
TST-04 results:2663 T12 | E6 microseconds round half to even at the millisecond | build_report_units_and_sentinels
TST-04 results:3325 T1 | 3.1 test reference module part normalised | module_metrics_flaky_and_quarantine
TST-04 results:3890 T10 | 3.6 cp1252 line with the micro sign | build_report_units_and_sentinels
TST-04 results:4284 T6 | 5.4 quarantine state at the attempt start | module_metrics_flaky_and_quarantine
TST-04 results:4903 T15 | 5.3 mixed outcomes at one commit mark a flaky test | module_metrics_flaky_and_quarantine
TST-04 results:0 T10 | 3.6 byte order mark before the control block | selftest_control_chain
TST-04 results:3557 T13 | 6.1 crash stack located by crash id | build_report_crash_buckets
TST-04 results:2086 T4 | 3.2 thousands separator | build_report_units_and_sentinels
TST-04 results:3148 T11 | 5.2 registration window on corrected start | module_metrics_counts_and_rates
TST-04 results:2051 T4 | 3.2 thousands separator | build_report_units_and_sentinels
TST-04 results:4453 T4 | 3.2 thousands separator | build_report_units_and_sentinels
TST-04 results:2266 T10 | 3.6 cp1252 line with the micro sign | build_report_units_and_sentinels
TST-04 results:258 T10 | 3.6 cp1252 line with the micro sign | build_report_units_and_sentinels
TST-04 results:2203 T4 | 3.2 thousands separator | build_report_units_and_sentinels
TST-04 results:2860 T4 | 3.2 thousands separator | build_report_units_and_sentinels
TST-05 results:27 T9 | 3.6 ragged row with trailing empty cells | module_metrics_flaky_and_quarantine
TST-05 results:639 T13 | 6.1 crash stack located by crash id | build_report_crash_buckets
TST-05 results:1402 T8 | 3.6 #header restates reordered columns | module_metrics_flaky_and_quarantine
TST-05 results:1925 T1 | 3.1 cells are stripped of surrounding white space | module_metrics_flaky_and_quarantine
TST-05 results:2069 T10 | 3.6 cp1252 line with the micro sign | build_report_units_and_sentinels
TST-05 results:2594 T12 | E6 microseconds round half to even at the millisecond | build_report_units_and_sentinels
TST-05 results:3221 T2 | 3.3 unit suffix overrides the column unit | build_report_units_and_sentinels
TST-05 results:3862 T6 | 5.4 quarantine state at the attempt start | module_metrics_flaky_and_quarantine
TST-05 results:4276 T15 | 5.3 mixed outcomes at one commit mark a flaky test | module_metrics_flaky_and_quarantine
TST-05 results:4899 T7 | 5.1 exporter rank decides between result copies | module_metrics_flaky_and_quarantine
TST-05 results:0 T10 | 3.6 byte order mark before the control block | selftest_control_chain
TST-05 results:4146 T11 | 5.2 registration window on corrected start | module_metrics_counts_and_rates
TST-05 results:3440 T10 | 3.6 cp1252 line with the micro sign | build_report_units_and_sentinels
TST-05 results:4190 T9 | 3.6 ragged row with trailing empty cells | module_metrics_flaky_and_quarantine
TST-05 results:3163 T13 | 6.1 crash stack located by crash id | build_report_crash_buckets
TST-05 results:2540 T8 | 3.6 #header restates reordered columns | module_metrics_flaky_and_quarantine
TST-06 results:446 T9 | 3.6 ragged row with trailing empty cells | module_metrics_flaky_and_quarantine
TST-06 results:517 T2 | 3.3 unit suffix overrides the column unit | build_report_units_and_sentinels
TST-06 results:1080 T8 | 3.6 #header restates reordered columns | module_metrics_flaky_and_quarantine
TST-06 results:1601 T6 | 5.4 quarantine state at the attempt start | module_metrics_flaky_and_quarantine
TST-06 results:2137 T10 | 3.6 cp1252 line with the micro sign | build_report_units_and_sentinels
TST-06 results:2627 T15 | 5.3 mixed outcomes at one commit mark a flaky test | module_metrics_flaky_and_quarantine
TST-06 results:3074 T1 | 3.1 cells are stripped of surrounding white space | module_metrics_flaky_and_quarantine
TST-06 results:3949 T11 | 5.2 registration window on corrected start | module_metrics_counts_and_rates
TST-06 results:4088 T13 | 6.1 crash stack located by crash id | build_report_crash_buckets
TST-06 results:4926 T12 | E6 microseconds round half to even at the millisecond | build_report_units_and_sentinels
TST-06 results:2702 T7 | 5.1 exporter rank decides between result copies | module_metrics_flaky_and_quarantine
TST-06 results:229 T9 | 3.6 ragged row with trailing empty cells | module_metrics_flaky_and_quarantine
TST-06 results:4494 T8 | 3.6 #header restates reordered columns | module_metrics_flaky_and_quarantine
TST-06 results:3237 T10 | 3.6 cp1252 line with the micro sign | build_report_units_and_sentinels
TST-06 results:119 T9 | 3.6 ragged row with trailing empty cells | module_metrics_flaky_and_quarantine
TST-06 results:1607 T6 | 5.4 quarantine state at the attempt start | module_metrics_flaky_and_quarantine
TST-06 results:3913 T9 | 3.6 ragged row with trailing empty cells | module_metrics_flaky_and_quarantine
TST-06 results:3812 T10 | 3.6 cp1252 line with the micro sign | build_report_units_and_sentinels
TST-06 results:3643 T9 | 3.6 ragged row with trailing empty cells | module_metrics_flaky_and_quarantine
TST-06 results:895 T9 | 3.6 ragged row with trailing empty cells | module_metrics_flaky_and_quarantine
TST-07 results:211 T10 | 3.6 cp1252 line with the micro sign | build_report_units_and_sentinels
TST-07 results:698 T12 | E6 microseconds round half to even at the millisecond | build_report_units_and_sentinels
TST-07 results:1428 T9 | 3.6 ragged row with trailing empty cells | module_metrics_flaky_and_quarantine
TST-07 results:1743 T8 | 3.6 #header restates reordered columns | module_metrics_flaky_and_quarantine
TST-07 results:2006 T11 | 5.2 registration window on corrected start | module_metrics_counts_and_rates
TST-07 results:2519 T1 | 3.1 test reference module part normalised | module_metrics_flaky_and_quarantine
TST-07 results:3430 T15 | 5.3 mixed outcomes at one commit mark a flaky test | module_metrics_flaky_and_quarantine
TST-07 results:3845 T2 | 3.3 unit suffix overrides the column unit | build_report_units_and_sentinels
TST-07 results:4307 T6 | 5.4 quarantine state at the attempt start | module_metrics_flaky_and_quarantine
TST-07 results:4897 T13 | 6.1 crash stack located by crash id | build_report_crash_buckets
TST-07 results:3027 T7 | 5.1 exporter rank decides between result copies | module_metrics_flaky_and_quarantine
TST-07 results:1332 T9 | 3.6 ragged row with trailing empty cells | module_metrics_flaky_and_quarantine
TST-07 results:1562 T10 | 3.6 cp1252 line with the micro sign | build_report_units_and_sentinels
TST-07 results:1737 T10 | 3.6 cp1252 line with the micro sign | build_report_units_and_sentinels
TST-07 results:3278 T10 | 3.6 cp1252 line with the micro sign | build_report_units_and_sentinels
TST-07 results:856 T9 | 3.6 ragged row with trailing empty cells | module_metrics_flaky_and_quarantine
TST-07 results:4607 T9 | 3.6 ragged row with trailing empty cells | module_metrics_flaky_and_quarantine
TST-07 results:1896 T15 | 5.3 mixed outcomes at one commit mark a flaky test | module_metrics_flaky_and_quarantine
TST-08 results:468 T9 | 3.6 ragged row with trailing empty cells | module_metrics_flaky_and_quarantine
TST-08 results:743 T8 | 3.6 #header restates reordered columns | module_metrics_flaky_and_quarantine
TST-08 results:1390 T2 | 3.3 unit suffix overrides the column unit | build_report_units_and_sentinels
TST-08 results:1794 T10 | 3.6 cp1252 line with the micro sign | build_report_units_and_sentinels
TST-08 results:2077 T11 | 5.2 registration window on corrected start | module_metrics_counts_and_rates
TST-08 results:2578 T12 | E6 microseconds round half to even at the millisecond | build_report_units_and_sentinels
TST-08 results:3028 T6 | 5.4 quarantine state at the attempt start | module_metrics_flaky_and_quarantine
TST-08 results:3735 T13 | 6.1 crash stack located by crash id | build_report_crash_buckets
TST-08 results:4382 T1 | 3.1 test reference module part normalised | module_metrics_flaky_and_quarantine
TST-08 results:4879 T15 | 5.3 mixed outcomes at one commit mark a flaky test | module_metrics_flaky_and_quarantine
TST-08 results:3075 T7 | 5.1 exporter rank decides between result copies | module_metrics_flaky_and_quarantine
TST-08 results:811 T9 | 3.6 ragged row with trailing empty cells | module_metrics_flaky_and_quarantine
TST-08 results:992 T9 | 3.6 ragged row with trailing empty cells | module_metrics_flaky_and_quarantine
TST-08 results:1408 T8 | 3.6 #header restates reordered columns | module_metrics_flaky_and_quarantine
TST-08 results:4734 T10 | 3.6 cp1252 line with the micro sign | build_report_units_and_sentinels
TST-08 results:2191 T8 | 3.6 #header restates reordered columns | module_metrics_flaky_and_quarantine
TST-08 results:3061 T9 | 3.6 ragged row with trailing empty cells | module_metrics_flaky_and_quarantine
TST-08 results:1566 T10 | 3.6 cp1252 line with the micro sign | build_report_units_and_sentinels
TST-08 results:2751 T9 | 3.6 ragged row with trailing empty cells | module_metrics_flaky_and_quarantine
TST-09 results:457 T6 | 5.4 quarantine state at the attempt start | module_metrics_flaky_and_quarantine
TST-09 results:846 T8 | 3.6 column aliases | module_metrics_flaky_and_quarantine
TST-09 results:1291 T1 | 3.1 test reference module part normalised | module_metrics_flaky_and_quarantine
TST-09 results:1672 T15 | 5.3 mixed outcomes at one commit mark a flaky test | module_metrics_flaky_and_quarantine
TST-09 results:2193 T13 | 6.1 crash stack located by crash id | build_report_crash_buckets
TST-09 results:2745 T7 | 5.1 exporter rank decides between result copies | module_metrics_flaky_and_quarantine
TST-09 results:3264 T11 | 5.2 registration window on corrected start | module_metrics_counts_and_rates
TST-09 results:3822 T6 | 5.4 quarantine state at the attempt start | module_metrics_flaky_and_quarantine
TST-09 results:4269 T15 | 5.3 mixed outcomes at one commit mark a flaky test | module_metrics_flaky_and_quarantine
TST-09 results:4660 T8 | 3.6 column aliases | module_metrics_flaky_and_quarantine
TST-09 results:1109 T1 | 3.1 build key spellings | build_report_membership
TST-09 results:589 T6 | 5.4 quarantine state at the attempt start | module_metrics_flaky_and_quarantine
TST-09 results:4627 T15 | 5.3 mixed outcomes at one commit mark a flaky test | module_metrics_flaky_and_quarantine
TST-09 results:4311 T6 | 3.6 provisional rows are not results | module_metrics_counts_and_rates
TST-09 results:2905 T1 | 3.1 test reference module part normalised | module_metrics_flaky_and_quarantine
TST-09 results:2900 T8 | 3.6 column aliases | module_metrics_flaky_and_quarantine
TST-09 results:908 T15 | 5.3 mixed outcomes at one commit mark a flaky test | module_metrics_flaky_and_quarantine
TST-10 results:16 T8 | 3.6 column aliases | module_metrics_flaky_and_quarantine
TST-10 results:758 T15 | 5.3 mixed outcomes at one commit mark a flaky test | module_metrics_flaky_and_quarantine
TST-10 results:1301 T6 | 3.6 provisional rows are not results | module_metrics_counts_and_rates
TST-10 results:1541 T13 | 6.1 crash stack located by crash id | build_report_crash_buckets
TST-10 results:2064 T1 | 3.1 test reference module part normalised | module_metrics_flaky_and_quarantine
TST-10 results:2891 T11 | 5.2 registration window on corrected start | module_metrics_counts_and_rates
TST-10 results:3175 T7 | 5.1 exporter rank decides between result copies | module_metrics_flaky_and_quarantine
TST-10 results:3747 T8 | 3.6 column aliases | module_metrics_flaky_and_quarantine
TST-10 results:4448 T8 | 3.6 column aliases | module_metrics_flaky_and_quarantine
TST-10 results:4991 T8 | 3.6 column aliases | module_metrics_flaky_and_quarantine
TST-10 results:0 T10 | 3.6 byte order mark before the control block | selftest_control_chain
TST-10 results:4479 T8 | 3.6 column aliases | module_metrics_flaky_and_quarantine
TST-10 results:1577 T13 | 6.1 crash stack located by crash id | build_report_crash_buckets
TST-10 results:228 T8 | 3.6 column aliases | module_metrics_flaky_and_quarantine
TST-10 results:2260 T15 | 5.3 mixed outcomes at one commit mark a flaky test | module_metrics_flaky_and_quarantine
TST-10 results:1588 T15 | 5.3 mixed outcomes at one commit mark a flaky test | module_metrics_flaky_and_quarantine
TST-10 results:3031 T8 | 3.6 column aliases | module_metrics_flaky_and_quarantine
TST-10 results:1581 T13 | 6.1 crash stack located by crash id | build_report_crash_buckets
TST-10 results:4799 T15 | 5.3 mixed outcomes at one commit mark a flaky test | module_metrics_flaky_and_quarantine
TST-11 results:50 T6 | 5.4 quarantine state at the attempt start | module_metrics_flaky_and_quarantine
TST-11 results:777 T15 | 5.3 mixed outcomes at one commit mark a flaky test | module_metrics_flaky_and_quarantine
TST-11 results:1050 T13 | 6.1 crash stack located by crash id | build_report_crash_buckets
TST-11 results:1859 T8 | 3.6 column aliases | module_metrics_flaky_and_quarantine
TST-11 results:2444 T1 | 3.1 test reference module part normalised | module_metrics_flaky_and_quarantine
TST-11 results:2529 T7 | 5.1 exporter rank decides between result copies | module_metrics_flaky_and_quarantine
TST-11 results:3490 T11 | 5.2 registration window on corrected start | module_metrics_counts_and_rates
TST-11 results:3649 T15 | 5.3 mixed outcomes at one commit mark a flaky test | module_metrics_flaky_and_quarantine
TST-11 results:4346 T8 | 3.6 column aliases | module_metrics_flaky_and_quarantine
TST-11 results:4913 T15 | 5.3 mixed outcomes at one commit mark a flaky test | module_metrics_flaky_and_quarantine
TST-11 results:0 T10 | 3.6 byte order mark before the control block | selftest_control_chain
TST-11 results:1762 T8 | 3.6 column aliases | module_metrics_flaky_and_quarantine
TST-11 results:4301 T8 | 3.6 column aliases | module_metrics_flaky_and_quarantine
TST-11 results:4174 T1 | 3.1 test reference module part normalised | module_metrics_flaky_and_quarantine
TST-11 results:843 T15 | 5.3 mixed outcomes at one commit mark a flaky test | module_metrics_flaky_and_quarantine
TST-11 results:227 T8 | 3.6 column aliases | module_metrics_flaky_and_quarantine
TST-11 results:554 T8 | 3.6 column aliases | module_metrics_flaky_and_quarantine
TST-11 results:1978 T8 | 3.6 column aliases | module_metrics_flaky_and_quarantine
TST-11 results:1582 T6 | 3.6 provisional rows are not results | module_metrics_counts_and_rates
TST-12 results_a:276 T6 | 5.4 quarantine state at the attempt start | module_metrics_flaky_and_quarantine
TST-12 results_a:848 T1 | 3.1 cells are stripped of surrounding white space | module_metrics_flaky_and_quarantine
TST-12 results_a:1289 T15 | 5.3 mixed outcomes at one commit mark a flaky test | module_metrics_flaky_and_quarantine
TST-12 results_a:1627 T13 | 6.1 crash stack located by crash id | build_report_crash_buckets
TST-12 results_a:2143 T7 | 5.1 exporter rank decides between result copies | module_metrics_flaky_and_quarantine
TST-12 results_a:2570 T6 | 5.4 quarantine state at the attempt start | module_metrics_flaky_and_quarantine
TST-12 results_a:3134 T11 | 5.2 registration window on corrected start | module_metrics_counts_and_rates
TST-12 results_a:3923 T6 | 5.4 quarantine state at the attempt start | module_metrics_flaky_and_quarantine
TST-12 results_a:4442 T1 | 3.1 cells are stripped of surrounding white space | module_metrics_flaky_and_quarantine
TST-12 results_a:4933 T15 | 5.3 mixed outcomes at one commit mark a flaky test | module_metrics_flaky_and_quarantine
TST-12 results_b:2 T13 | 6.1 crash stack located by crash id | build_report_crash_buckets
TST-12 results_b:883 T1 | 3.1 build key spellings | build_report_membership
TST-12 results_b:1072 T15 | 5.3 mixed outcomes at one commit mark a flaky test | module_metrics_flaky_and_quarantine
TST-12 results_b:1755 T6 | 5.4 quarantine state at the attempt start | module_metrics_flaky_and_quarantine
TST-12 results_b:2232 T6 | 5.4 quarantine state at the attempt start | module_metrics_flaky_and_quarantine
TST-12 results_b:2644 T1 | 3.1 cells are stripped of surrounding white space | module_metrics_flaky_and_quarantine
TST-12 results_b:3010 T6 | 5.4 quarantine state at the attempt start | module_metrics_flaky_and_quarantine
TST-12 results_b:3782 T15 | 5.3 mixed outcomes at one commit mark a flaky test | module_metrics_flaky_and_quarantine
TST-12 results_b:4382 T6 | 5.4 quarantine state at the attempt start | module_metrics_flaky_and_quarantine
TST-12 results_b:4542 T6 | 5.4 quarantine state at the attempt start | module_metrics_flaky_and_quarantine
TST-13 results_a:431 T1 | 3.1 build key spellings | build_report_membership
TST-13 results_a:908 T6 | 3.6 provisional rows are not results | module_metrics_counts_and_rates
TST-13 results_a:1048 T15 | 5.3 mixed outcomes at one commit mark a flaky test | module_metrics_flaky_and_quarantine
TST-13 results_a:1519 T13 | 6.1 crash stack located by crash id | build_report_crash_buckets
TST-13 results_a:2257 T11 | 5.2 registration window on corrected start | module_metrics_counts_and_rates
TST-13 results_a:2828 T6 | 5.4 quarantine state at the attempt start | module_metrics_flaky_and_quarantine
TST-13 results_a:3479 T1 | 3.1 test reference module part normalised | module_metrics_flaky_and_quarantine
TST-13 results_a:3758 T7 | 5.1 exporter rank decides between result copies | module_metrics_flaky_and_quarantine
TST-13 results_a:4414 T6 | 5.4 quarantine state at the attempt start | module_metrics_flaky_and_quarantine
TST-13 results_a:4997 T13 | 6.1 crash stack located by crash id | build_report_crash_buckets
TST-13 results_b:254 T6 | 5.4 quarantine state at the attempt start | module_metrics_flaky_and_quarantine
TST-13 results_b:700 T6 | 3.6 provisional rows are not results | module_metrics_counts_and_rates
TST-13 results_b:1376 T1 | 3.1 cells are stripped of surrounding white space | module_metrics_flaky_and_quarantine
TST-13 results_b:1973 T15 | 5.3 mixed outcomes at one commit mark a flaky test | module_metrics_flaky_and_quarantine
TST-13 results_b:2386 T6 | 3.6 provisional rows are not results | module_metrics_counts_and_rates
TST-13 results_b:2609 T1 | 3.1 cells are stripped of surrounding white space | module_metrics_flaky_and_quarantine
TST-13 results_b:3301 T15 | 5.3 mixed outcomes at one commit mark a flaky test | module_metrics_flaky_and_quarantine
TST-13 results_b:3752 T6 | 3.6 provisional rows are not results | module_metrics_counts_and_rates
TST-13 results_b:4248 T1 | 3.1 build key spellings | build_report_membership
TST-13 results_b:4911 T15 | 5.3 mixed outcomes at one commit mark a flaky test | module_metrics_flaky_and_quarantine
TST-14 results_a:123 T15 | 5.3 mixed outcomes at one commit mark a flaky test | module_metrics_flaky_and_quarantine
TST-14 results_a:814 T6 | 5.4 quarantine state at the attempt start | module_metrics_flaky_and_quarantine
TST-14 results_a:1395 T1 | 3.1 build key spellings | build_report_membership
TST-14 results_a:1898 T13 | 6.1 crash stack located by crash id | build_report_crash_buckets
TST-14 results_a:2426 T7 | 5.1 exporter rank decides between result copies | module_metrics_flaky_and_quarantine
TST-14 results_a:2669 T6 | 5.4 quarantine state at the attempt start | module_metrics_flaky_and_quarantine
TST-14 results_a:3382 T11 | 5.2 registration window on corrected start | module_metrics_counts_and_rates
TST-14 results_a:3718 T15 | 5.3 mixed outcomes at one commit mark a flaky test | module_metrics_flaky_and_quarantine
TST-14 results_a:4477 T15 | 5.3 mixed outcomes at one commit mark a flaky test | module_metrics_flaky_and_quarantine
TST-14 results_a:4708 T6 | 3.6 provisional rows are not results | module_metrics_counts_and_rates
TST-14 results_b:199 T13 | 6.1 crash stack located by crash id | build_report_crash_buckets
TST-14 results_b:509 T1 | 3.1 test reference module part normalised | module_metrics_flaky_and_quarantine
TST-14 results_b:1162 T15 | 5.3 mixed outcomes at one commit mark a flaky test | module_metrics_flaky_and_quarantine
TST-14 results_b:1961 T6 | 5.4 quarantine state at the attempt start | module_metrics_flaky_and_quarantine
TST-14 results_b:2472 T6 | 3.6 provisional rows are not results | module_metrics_counts_and_rates
TST-14 results_b:2813 T1 | 3.1 build key spellings | build_report_membership
TST-14 results_b:3044 T13 | 6.1 crash stack located by crash id | build_report_crash_buckets
TST-14 results_b:3725 T15 | 5.3 mixed outcomes at one commit mark a flaky test | module_metrics_flaky_and_quarantine
TST-14 results_b:4030 T15 | 5.3 mixed outcomes at one commit mark a flaky test | module_metrics_flaky_and_quarantine
TST-14 results_b:4915 T6 | 5.4 quarantine state at the attempt start | module_metrics_flaky_and_quarantine
TST-15 results:96 T15 | 5.3 mixed outcomes at one commit mark a flaky test | module_metrics_flaky_and_quarantine
TST-15 results:774 T2 | 3.3 unit suffix overrides the column unit | build_report_units_and_sentinels
TST-15 results:1261 T8 | 3.6 column aliases | module_metrics_flaky_and_quarantine
TST-15 results:1658 T1 | 3.1 cells are stripped of surrounding white space | module_metrics_flaky_and_quarantine
TST-15 results:2288 T12 | E6 microseconds round half to even at the millisecond | build_report_units_and_sentinels
TST-15 results:2578 T13 | 6.1 crash stack located by crash id | build_report_crash_buckets
TST-15 results:3275 T6 | 5.4 quarantine state at the attempt start | module_metrics_flaky_and_quarantine
TST-15 results:3735 T11 | 5.2 registration window on corrected start | module_metrics_counts_and_rates
TST-15 results:4055 T7 | 5.1 exporter rank decides between result copies | module_metrics_flaky_and_quarantine
TST-15 results:4863 T8 | 3.6 column aliases | module_metrics_flaky_and_quarantine
TST-15 results:3455 T1 | 3.1 test reference module part normalised | module_metrics_flaky_and_quarantine
TST-15 results:340 T12 | E6 microseconds round half to even at the millisecond | build_report_units_and_sentinels
TST-15 results:2198 T2 | 3.3 unit suffix overrides the column unit | build_report_units_and_sentinels
TST-15 results:1232 T2 | 3.3 unit suffix overrides the column unit | build_report_units_and_sentinels
TST-15 results:1916 T6 | 4.1 rows of revoked export jobs are void | module_metrics_counts_and_rates
TST-15 results:2531 T8 | 3.6 column aliases | module_metrics_flaky_and_quarantine
TST-15 results:4350 T8 | 3.6 column aliases | module_metrics_flaky_and_quarantine
TST-15 results:4193 T2 | 3.3 unit suffix overrides the column unit | build_report_units_and_sentinels
TST-15 results:643 T6 | 5.4 quarantine state at the attempt start | module_metrics_flaky_and_quarantine
TST-16 results:86 T8 | 3.6 column aliases | module_metrics_flaky_and_quarantine
TST-16 results:539 T13 | 6.1 crash stack located by crash id | build_report_crash_buckets
TST-16 results:1078 T2 | 3.3 unit suffix overrides the column unit | build_report_units_and_sentinels
TST-16 results:1580 T12 | E6 microseconds round half to even at the millisecond | build_report_units_and_sentinels
TST-16 results:2254 T1 | 3.1 cells are stripped of surrounding white space | module_metrics_flaky_and_quarantine
TST-16 results:2877 T15 | 5.3 mixed outcomes at one commit mark a flaky test | module_metrics_flaky_and_quarantine
TST-16 results:3235 T6 | 3.6 provisional rows are not results | module_metrics_counts_and_rates
TST-16 results:3569 T7 | 5.1 exporter rank decides between result copies | module_metrics_flaky_and_quarantine
TST-16 results:4097 T8 | 3.6 column aliases | module_metrics_flaky_and_quarantine
TST-16 results:4994 T11 | 5.2 registration window on corrected start | module_metrics_counts_and_rates
TST-16 results:565 T15 | 5.3 mixed outcomes at one commit mark a flaky test | module_metrics_flaky_and_quarantine
TST-16 results:2221 T1 | 3.1 cells are stripped of surrounding white space | module_metrics_flaky_and_quarantine
TST-16 results:4492 T8 | 3.6 column aliases | module_metrics_flaky_and_quarantine
TST-16 results:386 T1 | 3.1 cells are stripped of surrounding white space | module_metrics_flaky_and_quarantine
TST-16 results:1971 T8 | 3.6 column aliases | module_metrics_flaky_and_quarantine
TST-16 results:2160 T8 | 3.6 column aliases | module_metrics_flaky_and_quarantine
TST-16 results:2137 T12 | E6 microseconds round half to even at the millisecond | build_report_units_and_sentinels
TST-17 results:67 T6 | 5.4 quarantine state at the attempt start | module_metrics_flaky_and_quarantine
TST-17 results:630 T1 | 3.1 test reference module part normalised | module_metrics_flaky_and_quarantine
TST-17 results:1330 T15 | 5.3 mixed outcomes at one commit mark a flaky test | module_metrics_flaky_and_quarantine
TST-17 results:1815 T13 | 6.1 crash stack located by crash id | build_report_crash_buckets
TST-17 results:2263 T11 | 5.2 registration window on corrected start | module_metrics_counts_and_rates
TST-17 results:2627 T15 | 5.3 mixed outcomes at one commit mark a flaky test | module_metrics_flaky_and_quarantine
TST-17 results:3448 T7 | 5.1 exporter rank decides between result copies | module_metrics_flaky_and_quarantine
TST-17 results:3706 T6 | 5.4 quarantine state at the attempt start | module_metrics_flaky_and_quarantine
TST-17 results:4401 T6 | 3.6 provisional rows are not results | module_metrics_counts_and_rates
TST-17 results:4597 T6 | 5.4 quarantine state at the attempt start | module_metrics_flaky_and_quarantine
TST-17 results:4778 T1 | 3.1 test reference module part normalised | module_metrics_flaky_and_quarantine
TST-17 results:2409 T11 | 5.2 registration window on corrected start | module_metrics_counts_and_rates
TST-17 results:3420 T1 | 3.1 cells are stripped of surrounding white space | module_metrics_flaky_and_quarantine
TST-17 results:1699 T7 | 5.1 exporter rank decides between result copies | module_metrics_flaky_and_quarantine
TST-17 results:4975 T15 | 5.3 mixed outcomes at one commit mark a flaky test | module_metrics_flaky_and_quarantine
TST-17 results:3722 T1 | 3.1 cells are stripped of surrounding white space | module_metrics_flaky_and_quarantine
TST-17 results:477 T1 | 3.1 test reference module part normalised | module_metrics_flaky_and_quarantine
TST-17 results:1243 T13 | 6.1 crash stack located by crash id | build_report_crash_buckets
TST-17 results:4108 T1 | 3.1 cells are stripped of surrounding white space | module_metrics_flaky_and_quarantine
TST-17 results:639 T15 | 5.3 mixed outcomes at one commit mark a flaky test | module_metrics_flaky_and_quarantine
TST-18 results:53 T2 | 3.3 unit suffix overrides the column unit | build_report_units_and_sentinels
TST-18 results:710 T6 | 5.4 quarantine state at the attempt start | module_metrics_flaky_and_quarantine
TST-18 results:1371 T15 | 5.3 mixed outcomes at one commit mark a flaky test | module_metrics_flaky_and_quarantine
TST-18 results:1739 T1 | 3.1 cells are stripped of surrounding white space | module_metrics_flaky_and_quarantine
TST-18 results:2314 T12 | E6 microseconds round half to even at the millisecond | build_report_units_and_sentinels
TST-18 results:2501 T8 | 3.6 restated header row inside a document table | module_metrics_flaky_and_quarantine
TST-18 results:3375 T13 | 6.1 crash stack located by crash id | build_report_crash_buckets
TST-18 results:3669 T11 | 5.2 registration window on corrected start | module_metrics_counts_and_rates
TST-18 results:4303 T7 | 5.1 exporter rank decides between result copies | module_metrics_flaky_and_quarantine
TST-18 results:4972 T8 | 3.6 restated header row inside a document table | module_metrics_flaky_and_quarantine
TST-18 results:2215 T1 | 3.1 build key spellings | build_report_membership
TST-18 results:1084 T2 | 3.3 unit suffix overrides the column unit | build_report_units_and_sentinels
TST-18 results:247 T2 | 3.3 unit suffix overrides the column unit | build_report_units_and_sentinels
TST-18 results:2186 T2 | 3.3 unit suffix overrides the column unit | build_report_units_and_sentinels
TST-18 results:2296 T2 | 3.3 unit suffix overrides the column unit | build_report_units_and_sentinels
TST-18 results:2095 T8 | 3.6 restated header row inside a document table | module_metrics_flaky_and_quarantine
TST-19 results:461 T2 | 3.3 unit suffix overrides the column unit | build_report_units_and_sentinels
TST-19 results:614 T12 | E6 microseconds round half to even at the millisecond | build_report_units_and_sentinels
TST-19 results:1076 T6 | 5.4 quarantine state at the attempt start | module_metrics_flaky_and_quarantine
TST-19 results:1530 T8 | 3.6 restated header row inside a document table | module_metrics_flaky_and_quarantine
TST-19 results:2153 T15 | 5.3 mixed outcomes at one commit mark a flaky test | module_metrics_flaky_and_quarantine
TST-19 results:2718 T13 | 6.1 crash stack located by crash id | build_report_crash_buckets
TST-19 results:3270 T1 | 3.1 cells are stripped of surrounding white space | module_metrics_flaky_and_quarantine
TST-19 results:3671 T7 | 5.1 exporter rank decides between result copies | module_metrics_flaky_and_quarantine
TST-19 results:4335 T11 | 5.2 registration window on corrected start | module_metrics_counts_and_rates
TST-19 results:4615 T8 | 3.6 restated header row inside a document table | module_metrics_flaky_and_quarantine
TST-19 results:902 T8 | 3.6 restated header row inside a document table | module_metrics_flaky_and_quarantine
TST-19 results:2484 T2 | 3.3 unit suffix overrides the column unit | build_report_units_and_sentinels
TST-19 results:1944 T2 | 3.3 unit suffix overrides the column unit | build_report_units_and_sentinels
TST-19 results:3151 T8 | 3.6 restated header row inside a document table | module_metrics_flaky_and_quarantine
TST-19 results:1224 T6 | 5.4 quarantine state at the attempt start | module_metrics_flaky_and_quarantine
TST-19 results:2809 T2 | 3.3 unit suffix overrides the column unit | build_report_units_and_sentinels
TST-19 results:1412 T2 | 3.3 unit suffix overrides the column unit | build_report_units_and_sentinels
TST-19 results:4579 T2 | 3.3 unit suffix overrides the column unit | build_report_units_and_sentinels
TST-19 results:2021 T12 | E6 microseconds round half to even at the millisecond | build_report_units_and_sentinels
TST-20 results:350 T2 | 3.3 unit suffix overrides the column unit | build_report_units_and_sentinels
TST-20 results:857 T6 | 5.4 quarantine state at the attempt start | module_metrics_flaky_and_quarantine
TST-20 results:1458 T8 | 3.6 restated header row inside a document table | module_metrics_flaky_and_quarantine
TST-20 results:1511 T13 | 6.1 crash id from the weekly digest legacy map | build_report_crash_buckets
TST-20 results:2088 T12 | E6 microseconds round half to even at the millisecond | build_report_units_and_sentinels
TST-20 results:2533 T1 | 3.1 build key spellings | build_report_membership
TST-20 results:3164 T11 | 5.2 registration window on corrected start | module_metrics_counts_and_rates
TST-20 results:3539 T15 | 5.3 mixed outcomes at one commit mark a flaky test | module_metrics_flaky_and_quarantine
TST-20 results:4143 T7 | 5.1 exporter rank decides between result copies | module_metrics_flaky_and_quarantine
TST-20 results:4573 T2 | 3.3 unit suffix overrides the column unit | build_report_units_and_sentinels
TST-20 results:1091 T8 | 3.6 restated header row inside a document table | module_metrics_flaky_and_quarantine
TST-20 results:2345 T2 | 3.3 unit suffix overrides the column unit | build_report_units_and_sentinels
TST-20 results:3117 T2 | 3.3 unit suffix overrides the column unit | build_report_units_and_sentinels
TST-20 results:1243 T8 | 3.6 restated header row inside a document table | module_metrics_flaky_and_quarantine
TST-20 results:3088 T12 | E6 microseconds round half to even at the millisecond | build_report_units_and_sentinels
TST-20 results:3043 T8 | 3.6 restated header row inside a document table | module_metrics_flaky_and_quarantine
TST-21 results:495 T4 | 3.2 thousands separator | build_report_units_and_sentinels
TST-21 results:637 T10 | 3.6 cp1252 line with the micro sign | build_report_units_and_sentinels
TST-21 results:1115 T2 | 3.3 unit suffix overrides the column unit | build_report_units_and_sentinels
TST-21 results:1949 T6 | 5.4 quarantine state at the attempt start | module_metrics_flaky_and_quarantine
TST-21 results:2193 T1 | 3.1 test reference module part normalised | module_metrics_flaky_and_quarantine
TST-21 results:2839 T13 | 6.1 crash id from the weekly digest legacy map | build_report_crash_buckets
TST-21 results:3006 T15 | 5.3 mixed outcomes at one commit mark a flaky test | module_metrics_flaky_and_quarantine
TST-21 results:3771 T7 | 5.1 exporter rank decides between result copies | module_metrics_flaky_and_quarantine
TST-21 results:4165 T11 | 5.2 registration window on corrected start | module_metrics_counts_and_rates
TST-21 results:4837 T12 | E6 microseconds round half to even at the millisecond | build_report_units_and_sentinels
TST-21 results:1381 T4 | 3.2 thousands separator | build_report_units_and_sentinels
TST-21 results:4540 T4 | 3.2 thousands separator | build_report_units_and_sentinels
TST-21 results:2238 T4 | 3.2 thousands separator | build_report_units_and_sentinels
TST-21 results:3047 T10 | 3.6 cp1252 line with the micro sign | build_report_units_and_sentinels
TST-21 results:2301 T4 | 3.2 thousands separator | build_report_units_and_sentinels
TST-21 results:387 T4 | 3.2 thousands separator | build_report_units_and_sentinels
TST-21 results:2964 T4 | 3.2 thousands separator | build_report_units_and_sentinels
TST-21 results:904 T4 | 3.2 thousands separator | build_report_units_and_sentinels
TST-22 results:477 T1 | 3.1 build key spellings | build_report_membership
TST-22 results:963 T2 | 3.3 unit suffix overrides the column unit | build_report_units_and_sentinels
TST-22 results:1144 T15 | 5.3 mixed outcomes at one commit mark a flaky test | module_metrics_flaky_and_quarantine
TST-22 results:1568 T12 | E6 microseconds round half to even at the millisecond | build_report_units_and_sentinels
TST-22 results:2151 T6 | 5.4 quarantine state at the attempt start | module_metrics_flaky_and_quarantine
TST-22 results:2885 T13 | 6.1 crash stack located by crash id | build_report_crash_buckets
TST-22 results:3085 T7 | 5.1 exporter rank decides between result copies | module_metrics_flaky_and_quarantine
TST-22 results:3531 T11 | 5.2 registration window on corrected start | module_metrics_counts_and_rates
TST-22 results:4339 T12 | E6 microseconds round half to even at the millisecond | build_report_units_and_sentinels
TST-22 results:4571 T2 | 3.3 unit suffix overrides the column unit | build_report_units_and_sentinels
TST-22 results:804 T6 | 5.4 quarantine state at the attempt start | module_metrics_flaky_and_quarantine
TST-22 results:4286 T6 | 5.4 quarantine state at the attempt start | module_metrics_flaky_and_quarantine
TST-22 results:809 T2 | 3.3 unit suffix overrides the column unit | build_report_units_and_sentinels
TST-22 results:1359 T2 | 3.3 unit suffix overrides the column unit | build_report_units_and_sentinels
TST-22 results:4635 T2 | 3.3 unit suffix overrides the column unit | build_report_units_and_sentinels
TST-22 results:4357 T2 | 3.3 unit suffix overrides the column unit | build_report_units_and_sentinels
TST-22 results:812 T2 | 3.3 unit suffix overrides the column unit | build_report_units_and_sentinels
DCY-05 results:385 T16 pull | G6 restated rerun row disagrees | module_metrics_flaky_and_quarantine
DCY-05 results:716 T7 pull | 5.1 exporter rank decides between result copies | module_metrics_flaky_and_quarantine
DCY-05 results:1477 T6 push | 5.4 quarantine state at the attempt start | module_metrics_flaky_and_quarantine
DCY-05 results:1559 T13 pull | 6.1 crash stack located by crash id | build_report_crash_buckets
DCY-05 results:2207 T1 push | 3.1 cells are stripped of surrounding white space | module_metrics_flaky_and_quarantine
DCY-05 results:2704 T15 pull | 5.3 mixed outcomes at one commit mark a flaky test | module_metrics_flaky_and_quarantine
DCY-05 results:3308 T11 pull | 5.2 registration window on corrected start | module_metrics_counts_and_rates
DCY-05 results:3591 T16 pull | G6 restated rerun row disagrees | module_metrics_flaky_and_quarantine
DCY-05 results:4434 T16 pull | G6 restated rerun row disagrees | module_metrics_flaky_and_quarantine
DCY-05 results:4915 T16 pull | G6 restated rerun row disagrees | module_metrics_flaky_and_quarantine
DCY-05 results:440 T16 pull | G6 restated rerun row disagrees | module_metrics_flaky_and_quarantine
DCY-05 results:1957 T16 pull | G6 restated rerun row disagrees | module_metrics_flaky_and_quarantine
DCY-05 results:2627 T16 pull | G6 restated rerun row disagrees | module_metrics_flaky_and_quarantine
DCY-05 results:2932 T16 pull | G6 restated rerun row disagrees | module_metrics_flaky_and_quarantine
DCY-05 results:1829 T16 pull | G6 restated rerun row disagrees | module_metrics_flaky_and_quarantine
DCY-05 results:3036 T16 pull | G6 restated rerun row disagrees | module_metrics_flaky_and_quarantine
DCY-05 results:168 T16 pull | G6 restated rerun row disagrees | module_metrics_flaky_and_quarantine
DCY-05 results:42 T16 pull | G6 restated rerun row disagrees | module_metrics_flaky_and_quarantine
DCY-05 results:3468 T16 pull | G6 restated rerun row disagrees | module_metrics_flaky_and_quarantine
DCY-05 results:4544 T16 pull | G6 restated rerun row disagrees | module_metrics_flaky_and_quarantine
DCY-05 results:2935 T16 pull | G6 restated rerun row disagrees | module_metrics_flaky_and_quarantine
DCY-05 results:3632 T16 pull | G6 restated rerun row disagrees | module_metrics_flaky_and_quarantine
DCY-05 results:861 T16 pull | G6 restated rerun row disagrees | module_metrics_flaky_and_quarantine
DCY-05 results:143 T1 push | 3.1 test reference module part normalised | module_metrics_flaky_and_quarantine
DCY-05 results:2470 T16 pull | G6 restated rerun row disagrees | module_metrics_flaky_and_quarantine
DCY-05 results:4764 T16 pull | G6 restated rerun row disagrees | module_metrics_flaky_and_quarantine
DCY-05 results:695 T16 pull | G6 restated rerun row disagrees | module_metrics_flaky_and_quarantine
DCY-05 results:4499 T16 pull | G6 restated rerun row disagrees | module_metrics_flaky_and_quarantine
DCY-05 results:4922 T16 pull | G6 restated rerun row disagrees | module_metrics_flaky_and_quarantine
DCY-05 results:3226 T16 pull | G6 restated rerun row disagrees | module_metrics_flaky_and_quarantine
DCY-05 results:3384 T16 pull | G6 restated rerun row disagrees | module_metrics_flaky_and_quarantine
CRS-01 messages:351 T11 | E5 return addresses are looked up at offset minus one | build_report_crash_buckets
CRS-01 messages:533 T13 | 6.1 Message-ID crosswalk | build_report_crash_buckets
CRS-01 messages:1376 T7 | 6.1 highest X-Report-Rev wins | build_report_crash_buckets
CRS-01 messages:1768 T15 | 6.3 a frame in a gap ends the search | build_report_crash_buckets
CRS-01 messages:2204 T7 | 6.1 highest X-Report-Rev wins | build_report_crash_buckets
CRS-01 messages:2668 T11 | E5 return addresses are looked up at offset minus one | build_report_crash_buckets
CRS-01 messages:3461 T11 | E5 return addresses are looked up at offset minus one | build_report_crash_buckets
CRS-01 messages:3838 T11 | E5 return addresses are looked up at offset minus one | build_report_crash_buckets
CRS-01 messages:4194 T11 | E5 return addresses are looked up at offset minus one | build_report_crash_buckets
CRS-01 messages:4729 T13 | 6.1 Message-ID crosswalk | build_report_crash_buckets
CRS-01 messages:5356 T11 | E5 return addresses are looked up at offset minus one | build_report_crash_buckets
CRS-01 messages:5708 T11 | E5 return addresses are looked up at offset minus one | build_report_crash_buckets
CRS-01 messages:6151 T7 | 6.1 highest X-Report-Rev wins | build_report_crash_buckets
CRS-01 messages:6502 T11 | E5 return addresses are looked up at offset minus one | build_report_crash_buckets
CRS-01 messages:7418 T13 | 6.1 Message-ID crosswalk | build_report_crash_buckets
CRS-01 messages:7628 T11 | E5 return addresses are looked up at offset minus one | build_report_crash_buckets
CRS-01 messages:8043 T11 | E5 return addresses are looked up at offset minus one | build_report_crash_buckets
CRS-01 messages:7675 T13 | 6.1 Message-ID crosswalk | build_report_crash_buckets
CRS-01 messages:6056 T11 | E5 return addresses are looked up at offset minus one | build_report_crash_buckets
CRS-02 crash_index:171 T9 | 3.6 ragged row with trailing empty cells | build_report_crash_buckets
CRS-02 crash_index:591 T13 | 6.1 Message-ID crosswalk when X-Crash-Id is absent | build_report_crash_buckets
CRS-02 crash_index:1200 T8 | 3.6 #header restates reordered columns | build_report_crash_buckets
CRS-02 crash_index:1801 T1 | 3.1 cells are stripped of surrounding white space | build_report_crash_buckets
CRS-02 crash_index:2488 T9 | 3.6 ragged row with trailing empty cells | build_report_crash_buckets
CRS-02 crash_index:2669 T9 | 3.6 ragged row with trailing empty cells | build_report_crash_buckets
CRS-02 crash_index:3309 T9 | 3.6 ragged row with trailing empty cells | build_report_crash_buckets
CRS-02 crash_index:3634 T9 | 3.6 ragged row with trailing empty cells | build_report_crash_buckets
CRS-02 crash_index:4111 T9 | 3.6 ragged row with trailing empty cells | build_report_crash_buckets
CRS-02 crash_index:4953 T8 | 3.6 #header restates reordered columns | build_report_crash_buckets
CRS-02 crash_index:5112 T9 | 3.6 ragged row with trailing empty cells | build_report_crash_buckets
CRS-02 crash_index:5713 T9 | 3.6 ragged row with trailing empty cells | build_report_crash_buckets
CRS-02 crash_index:6351 T8 | 3.6 #header restates reordered columns | build_report_crash_buckets
CRS-02 crash_index:6732 T8 | 3.6 #header restates reordered columns | build_report_crash_buckets
CRS-02 crash_index:7388 T9 | 3.6 ragged row with trailing empty cells | build_report_crash_buckets
CRS-02 crash_index:7600 T9 | 3.6 ragged row with trailing empty cells | build_report_crash_buckets
CRS-02 crash_index:8050 T9 | 3.6 ragged row with trailing empty cells | build_report_crash_buckets
CRS-03 legacy_crashes:416 T13 | 6.1 legacy frames map through the build-id map | build_report_crash_buckets
CRS-03 legacy_crashes:542 T8 | 3.6 restated header row inside a document table | build_report_crash_buckets
CRS-03 legacy_crashes:1029 T1 | 3.1 cells are stripped of surrounding white space | build_report_crash_buckets
CRS-03 legacy_crashes:1605 T8 | 3.6 restated header row inside a document table | build_report_crash_buckets
CRS-03 legacy_crashes:2327 T13 | 6.1 legacy frames map through the build-id map | build_report_crash_buckets
CRS-03 legacy_crashes:2654 T8 | 3.6 restated header row inside a document table | build_report_crash_buckets
CRS-03 legacy_crashes:3409 T6 | historical minutes rows name no crash of the stage | build_report_crash_buckets
CRS-03 legacy_crashes:3628 T8 | 3.6 restated header row inside a document table | build_report_crash_buckets
CRS-03 legacy_crashes:4107 T8 | 3.6 restated header row inside a document table | build_report_crash_buckets
CRS-03 legacy_crashes:4538 T8 | 3.6 restated header row inside a document table | build_report_crash_buckets
CRS-03 legacy_crashes:3489 T1 | 3.1 cells are stripped of surrounding white space | build_report_crash_buckets
CRS-03 legacy_crashes:3453 T8 | 3.6 restated header row inside a document table | build_report_crash_buckets
CRS-03 legacy_crashes:4868 T8 | 3.6 restated header row inside a document table | build_report_crash_buckets
CRS-03 legacy_crashes:2825 T13 | 6.1 legacy frames map through the build-id map | build_report_crash_buckets
CRS-03 legacy_crashes:4815 T1 | 3.1 cells are stripped of surrounding white space | build_report_crash_buckets
CRS-03 legacy_crashes:3413 T1 | 3.1 cells are stripped of surrounding white space | build_report_crash_buckets
DCY-10 digest:316 T16 pull | G12 digest buckets ignore the pc-1 and noise rules | build_report_crash_buckets
DCY-10 digest:766 T15 pull | 6.2 legacy crashes are symbolicated through build ids | build_report_crash_buckets
DCY-10 digest:1427 T7 pull | 6.1 the digest summarises the superseded report revision | build_report_crash_buckets
DCY-10 digest:1924 T1 push | 3.1 cells are stripped of surrounding white space | build_report_crash_buckets
DCY-10 digest:2363 T16 pull | G12 digest buckets ignore the pc-1 and noise rules | build_report_crash_buckets
DCY-10 digest:2981 T16 pull | G12 digest buckets ignore the pc-1 and noise rules | build_report_crash_buckets
DCY-10 digest:3118 T16 pull | G12 digest buckets ignore the pc-1 and noise rules | build_report_crash_buckets
DCY-10 digest:3906 T16 pull | G12 digest buckets ignore the pc-1 and noise rules | build_report_crash_buckets
DCY-10 digest:4306 T16 pull | G12 digest buckets ignore the pc-1 and noise rules | build_report_crash_buckets
DCY-10 digest:4980 T16 pull | G12 digest buckets ignore the pc-1 and noise rules | build_report_crash_buckets
DCY-10 legacy_map:472 T13 pull | 6.1 only crosswalk for crash rows without a crash column | build_report_crash_buckets
DCY-10 legacy_map:760 T6 push | 4.7 voided builds keep their crosswalk rows | build_report_membership
DCY-10 legacy_map:1367 T13 pull | 6.1 only crosswalk for crash rows without a crash column | build_report_crash_buckets
DCY-10 legacy_map:1751 T1 push | 3.1 cells are stripped of surrounding white space | build_report_crash_buckets
DCY-10 legacy_map:2016 T1 push | 3.1 cells are stripped of surrounding white space | build_report_crash_buckets
DCY-10 legacy_map:2662 T1 push | 3.1 test reference module part normalised | module_metrics_flaky_and_quarantine
DCY-10 legacy_map:3251 T1 push | 3.1 cells are stripped of surrounding white space | build_report_crash_buckets
DCY-10 legacy_map:3577 T1 push | 3.1 cells are stripped of surrounding white space | build_report_crash_buckets
DCY-10 legacy_map:4499 T1 push | 3.1 cells are stripped of surrounding white space | build_report_crash_buckets
DCY-10 legacy_map:4630 T1 push | 3.1 cells are stripped of surrounding white space | build_report_crash_buckets
DCY-10 digest:4729 T16 pull | G12 digest buckets ignore the pc-1 and noise rules | build_report_crash_buckets
DCY-10 digest:4050 T16 pull | G12 digest buckets ignore the pc-1 and noise rules | build_report_crash_buckets
DCY-10 digest:1887 T16 pull | G12 digest buckets ignore the pc-1 and noise rules | build_report_crash_buckets
DCY-10 digest:3607 T16 pull | G12 digest buckets ignore the pc-1 and noise rules | build_report_crash_buckets
DCY-10 digest:2761 T16 pull | G12 digest buckets ignore the pc-1 and noise rules | build_report_crash_buckets
DCY-10 legacy_map:3461 T1 push | 3.1 build key spellings | build_report_attempt_precedence
DCY-10 digest:3011 T16 pull | G12 digest buckets ignore the pc-1 and noise rules | build_report_crash_buckets
DCY-10 digest:2266 T16 pull | G12 digest buckets ignore the pc-1 and noise rules | build_report_crash_buckets
DCY-10 digest:589 T16 pull | G12 digest buckets ignore the pc-1 and noise rules | build_report_crash_buckets
DCY-10 legacy_map:1948 T1 push | 3.1 build key spellings | build_report_attempt_precedence
SYM-01 kst_core:140 T13 | 6.3 template symbols are labelled through the frame register | build_report_crash_buckets
SYM-01 kst_core:531 T1 | 3.1 cells are stripped of surrounding white space | build_report_crash_buckets
SYM-01 kst_core:1442 T11 | 6.3 return address minus one | build_report_crash_buckets
SYM-01 kst_core:1615 T1 | 3.1 cells are stripped of surrounding white space | build_report_crash_buckets
SYM-01 kst_core:2268 T1 | 3.1 cells are stripped of surrounding white space | build_report_crash_buckets
SYM-01 kst_core:2776 T1 | 3.1 cells are stripped of surrounding white space | build_report_crash_buckets
SYM-01 kst_core:3436 T13 | 6.3 template symbols are labelled through the frame register | build_report_crash_buckets
SYM-01 kst_core:3974 T13 | 6.3 template symbols are labelled through the frame register | build_report_crash_buckets
SYM-01 kst_core:4346 T15 | 6.3 noise routines never name a crash | build_report_crash_buckets
SYM-01 kst_core:4525 T13 | 6.3 template symbols are labelled through the frame register | build_report_crash_buckets
SYM-01 kst_net:38 T13 | 6.3 template symbols are labelled through the frame register | build_report_crash_buckets
SYM-01 kst_net:528 T13 | 6.3 template symbols are labelled through the frame register | build_report_crash_buckets
SYM-01 kst_net:1431 T1 | 3.1 cells are stripped of surrounding white space | build_report_crash_buckets
SYM-01 kst_net:1999 T1 | 3.1 cells are stripped of surrounding white space | build_report_crash_buckets
SYM-01 kst_net:2010 T13 | 6.3 template symbols are labelled through the frame register | build_report_crash_buckets
SYM-01 kst_net:2781 T13 | 6.3 template symbols are labelled through the frame register | build_report_crash_buckets
SYM-01 kst_net:3461 T13 | 6.3 template symbols are labelled through the frame register | build_report_crash_buckets
SYM-01 kst_net:3983 T1 | 3.1 cells are stripped of surrounding white space | build_report_crash_buckets
SYM-01 kst_net:4473 T11 | 6.3 return address minus one | build_report_crash_buckets
SYM-01 kst_net:4528 T1 | 3.1 cells are stripped of surrounding white space | build_report_crash_buckets
SYM-02 kst_core:456 T11 | 6.3 return address minus one | build_report_crash_buckets
SYM-02 kst_core:509 T1 | 3.1 cells are stripped of surrounding white space | build_report_crash_buckets
SYM-02 kst_core:1153 T13 | 6.3 template symbols are labelled through the frame register | build_report_crash_buckets
SYM-02 kst_core:1875 T1 | 3.1 cells are stripped of surrounding white space | build_report_crash_buckets
SYM-02 kst_core:2359 T1 | 3.1 cells are stripped of surrounding white space | build_report_crash_buckets
SYM-02 kst_core:2949 T11 | 6.3 return address minus one | build_report_crash_buckets
SYM-02 kst_core:3132 T13 | 6.3 template symbols are labelled through the frame register | build_report_crash_buckets
SYM-02 kst_core:3677 T11 | 6.3 return address minus one | build_report_crash_buckets
SYM-02 kst_core:4346 T15 | 6.3 noise routines never name a crash | build_report_crash_buckets
SYM-02 kst_core:4545 T1 | 3.1 cells are stripped of surrounding white space | build_report_crash_buckets
SYM-02 kst_net:490 T1 | 3.1 cells are stripped of surrounding white space | build_report_crash_buckets
SYM-02 kst_net:595 T1 | 3.1 cells are stripped of surrounding white space | build_report_crash_buckets
SYM-02 kst_net:1031 T1 | 3.1 cells are stripped of surrounding white space | build_report_crash_buckets
SYM-02 kst_net:1890 T11 | 6.3 return address minus one | build_report_crash_buckets
SYM-02 kst_net:2076 T1 | 3.1 cells are stripped of surrounding white space | build_report_crash_buckets
SYM-02 kst_net:2611 T11 | 6.3 return address minus one | build_report_crash_buckets
SYM-02 kst_net:3297 T15 | 6.3 noise routines never name a crash | build_report_crash_buckets
SYM-02 kst_net:3814 T1 | 3.1 cells are stripped of surrounding white space | build_report_crash_buckets
SYM-02 kst_net:4449 T1 | 3.1 cells are stripped of surrounding white space | build_report_crash_buckets
SYM-02 kst_net:4549 T1 | 3.1 cells are stripped of surrounding white space | build_report_crash_buckets
SYM-03 kst_pay:52 T11 | 6.3 return address minus one | build_report_crash_buckets
SYM-03 kst_pay:627 T13 | 6.3 template symbols are labelled through the frame register | build_report_crash_buckets
SYM-03 kst_pay:1302 T1 | 3.1 cells are stripped of surrounding white space | build_report_crash_buckets
SYM-03 kst_pay:1775 T13 | 6.3 template symbols are labelled through the frame register | build_report_crash_buckets
SYM-03 kst_pay:2325 T13 | 6.3 template symbols are labelled through the frame register | build_report_crash_buckets
SYM-03 kst_pay:2786 T1 | 3.1 cells are stripped of surrounding white space | build_report_crash_buckets
SYM-03 kst_pay:3104 T15 | 6.3 noise routines never name a crash | build_report_crash_buckets
SYM-03 kst_pay:3837 T1 | 3.1 cells are stripped of surrounding white space | build_report_crash_buckets
SYM-03 kst_pay:4167 T11 | 6.3 return address minus one | build_report_crash_buckets
SYM-03 kst_pay:4655 T1 | 3.1 cells are stripped of surrounding white space | build_report_crash_buckets
SYM-03 kst_pay:2002 T1 | 3.1 cells are stripped of surrounding white space | build_report_crash_buckets
SYM-03 kst_pay:4270 T1 | 3.1 cells are stripped of surrounding white space | build_report_crash_buckets
SYM-03 kst_pay:891 T1 | 3.1 cells are stripped of surrounding white space | build_report_crash_buckets
SYM-03 kst_pay:1433 T13 | 6.3 template symbols are labelled through the frame register | build_report_crash_buckets
SYM-03 kst_pay:3121 T1 | 3.1 cells are stripped of surrounding white space | build_report_crash_buckets
SYM-03 kst_pay:3956 T1 | 3.1 cells are stripped of surrounding white space | build_report_crash_buckets
SYM-04 kst_pay:32 T1 | 3.1 cells are stripped of surrounding white space | build_report_crash_buckets
SYM-04 kst_pay:511 T13 | 6.3 template symbols are labelled through the frame register | build_report_crash_buckets
SYM-04 kst_pay:1150 T11 | 6.3 return address minus one | build_report_crash_buckets
SYM-04 kst_pay:1924 T13 | 6.3 template symbols are labelled through the frame register | build_report_crash_buckets
SYM-04 kst_pay:2439 T13 | 6.3 template symbols are labelled through the frame register | build_report_crash_buckets
SYM-04 kst_pay:2967 T13 | 6.3 template symbols are labelled through the frame register | build_report_crash_buckets
SYM-04 kst_pay:3037 T1 | 3.1 cells are stripped of surrounding white space | build_report_crash_buckets
SYM-04 kst_pay:3509 T11 | 6.3 return address minus one | build_report_crash_buckets
SYM-04 kst_pay:4436 T15 | 6.3 noise routines never name a crash | build_report_crash_buckets
SYM-04 kst_pay:4718 T13 | 6.3 template symbols are labelled through the frame register | build_report_crash_buckets
SYM-04 kst_pay:2231 T13 | 6.3 template symbols are labelled through the frame register | build_report_crash_buckets
SYM-04 kst_pay:4735 T1 | 3.1 cells are stripped of surrounding white space | build_report_crash_buckets
SYM-04 kst_pay:1588 T1 | 3.1 cells are stripped of surrounding white space | build_report_crash_buckets
SYM-04 kst_pay:1975 T13 | 6.3 template symbols are labelled through the frame register | build_report_crash_buckets
SYM-04 kst_pay:3374 T1 | 3.1 cells are stripped of surrounding white space | build_report_crash_buckets
SYM-04 kst_pay:959 T13 | 6.3 template symbols are labelled through the frame register | build_report_crash_buckets
SYM-04 kst_pay:4953 T1 | 3.1 cells are stripped of surrounding white space | build_report_crash_buckets
SYM-04 kst_pay:311 T11 | 6.3 return address minus one | build_report_crash_buckets
SYM-04 kst_pay:248 T13 | 6.3 template symbols are labelled through the frame register | build_report_crash_buckets
SYM-05 kst_ui:476 T13 | 6.3 template symbols are labelled through the frame register | build_report_crash_buckets
SYM-05 kst_ui:994 T1 | 3.1 cells are stripped of surrounding white space | build_report_crash_buckets
SYM-05 kst_ui:1301 T11 | 6.3 return address minus one | build_report_crash_buckets
SYM-05 kst_ui:1762 T13 | 6.3 template symbols are labelled through the frame register | build_report_crash_buckets
SYM-05 kst_ui:2221 T13 | 6.3 template symbols are labelled through the frame register | build_report_crash_buckets
SYM-05 kst_ui:2794 T1 | 3.1 cells are stripped of surrounding white space | build_report_crash_buckets
SYM-05 kst_ui:3343 T1 | 3.1 cells are stripped of surrounding white space | build_report_crash_buckets
SYM-05 kst_ui:3840 T15 | 6.3 noise routines never name a crash | build_report_crash_buckets
SYM-05 kst_ui:4278 T1 | 3.1 cells are stripped of surrounding white space | build_report_crash_buckets
SYM-05 kst_ui:4856 T11 | 6.3 return address minus one | build_report_crash_buckets
SYM-05 kst_ui:1034 T13 | 6.3 template symbols are labelled through the frame register | build_report_crash_buckets
SYM-05 kst_ui:3136 T13 | 6.3 template symbols are labelled through the frame register | build_report_crash_buckets
SYM-05 kst_ui:41 T1 | 3.1 cells are stripped of surrounding white space | build_report_crash_buckets
SYM-05 kst_ui:4982 T11 | 6.3 return address minus one | build_report_crash_buckets
SYM-05 kst_ui:3720 T11 | 6.3 return address minus one | build_report_crash_buckets
SYM-05 kst_ui:2121 T13 | 6.3 template symbols are labelled through the frame register | build_report_crash_buckets
SYM-05 kst_ui:3700 T1 | 3.1 cells are stripped of surrounding white space | build_report_crash_buckets
SYM-06 kst_ui:478 T13 | 6.3 template symbols are labelled through the frame register | build_report_crash_buckets
SYM-06 kst_ui:562 T1 | 3.1 cells are stripped of surrounding white space | build_report_crash_buckets
SYM-06 kst_ui:1210 T11 | 6.3 return address minus one | build_report_crash_buckets
SYM-06 kst_ui:1766 T1 | 3.1 cells are stripped of surrounding white space | build_report_crash_buckets
SYM-06 kst_ui:2011 T13 | 6.3 template symbols are labelled through the frame register | build_report_crash_buckets
SYM-06 kst_ui:2655 T1 | 3.1 cells are stripped of surrounding white space | build_report_crash_buckets
SYM-06 kst_ui:3388 T13 | 6.3 template symbols are labelled through the frame register | build_report_crash_buckets
SYM-06 kst_ui:3840 T15 | 6.3 noise routines never name a crash | build_report_crash_buckets
SYM-06 kst_ui:4249 T13 | 6.3 template symbols are labelled through the frame register | build_report_crash_buckets
SYM-06 kst_ui:4746 T13 | 6.3 template symbols are labelled through the frame register | build_report_crash_buckets
SYM-06 kst_ui:330 T13 | 6.3 template symbols are labelled through the frame register | build_report_crash_buckets
SYM-06 kst_ui:1711 T13 | 6.3 template symbols are labelled through the frame register | build_report_crash_buckets
SYM-06 kst_ui:4552 T13 | 6.3 template symbols are labelled through the frame register | build_report_crash_buckets
SYM-06 kst_ui:2845 T1 | 3.1 cells are stripped of surrounding white space | build_report_crash_buckets
SYM-06 kst_ui:938 T1 | 3.1 cells are stripped of surrounding white space | build_report_crash_buckets
SYM-06 kst_ui:3218 T1 | 3.1 cells are stripped of surrounding white space | build_report_crash_buckets
DCY-04 kst_core:306 T16 pull | G11 relinked preview addresses are not symbolication input | build_report_crash_buckets
DCY-04 kst_core:720 T13 pull | 6.3 template symbols are labelled through the frame register | build_report_crash_buckets
DCY-04 kst_core:1264 T11 pull | 6.3 return address minus one | build_report_crash_buckets
DCY-04 kst_core:1759 T1 push | 3.1 cells are stripped of surrounding white space | build_report_crash_buckets
DCY-04 kst_core:2093 T7 pull | G11 a relinked preview never supersedes the pinned store | build_report_crash_buckets
DCY-04 kst_core:2992 T15 pull | 6.3 noise routines never name a crash | build_report_crash_buckets
DCY-04 kst_core:3230 T16 pull | G11 relinked preview addresses are not symbolication input | build_report_crash_buckets
DCY-04 kst_core:3888 T16 pull | G11 relinked preview addresses are not symbolication input | build_report_crash_buckets
DCY-04 kst_core:4030 T7 pull | G11 a relinked preview never supersedes the pinned store | build_report_crash_buckets
DCY-04 kst_core:4698 T16 pull | G11 relinked preview addresses are not symbolication input | build_report_crash_buckets
DCY-04 kst_net:340 T16 pull | G11 relinked preview addresses are not symbolication input | build_report_crash_buckets
DCY-04 kst_net:810 T16 pull | G11 relinked preview addresses are not symbolication input | build_report_crash_buckets
DCY-04 kst_net:1368 T16 pull | G11 relinked preview addresses are not symbolication input | build_report_crash_buckets
DCY-04 kst_net:1579 T16 pull | G11 relinked preview addresses are not symbolication input | build_report_crash_buckets
DCY-04 kst_net:2210 T16 pull | G11 relinked preview addresses are not symbolication input | build_report_crash_buckets
DCY-04 kst_net:2945 T16 pull | G11 relinked preview addresses are not symbolication input | build_report_crash_buckets
DCY-04 kst_net:3297 T15 pull | 6.3 noise routines never name a crash | build_report_crash_buckets
DCY-04 kst_net:3957 T16 pull | G11 relinked preview addresses are not symbolication input | build_report_crash_buckets
DCY-04 kst_net:4308 T16 pull | G11 relinked preview addresses are not symbolication input | build_report_crash_buckets
DCY-04 kst_net:4598 T16 pull | G11 relinked preview addresses are not symbolication input | build_report_crash_buckets
DCY-04 buildid_map:61 T6 push | 6.2 historical build ids name retired toolchains | build_report_crash_buckets
DCY-04 buildid_map:844 T6 push | 6.2 historical build ids name retired toolchains | build_report_crash_buckets
DCY-04 buildid_map:1239 T1 push | 3.1 cells are stripped of surrounding white space | build_report_crash_buckets
DCY-04 buildid_map:1789 T6 push | 6.2 historical build ids name retired toolchains | build_report_crash_buckets
DCY-04 buildid_map:2359 T1 push | 3.1 cells are stripped of surrounding white space | build_report_crash_buckets
DCY-04 buildid_map:2853 T1 push | 3.1 cells are stripped of surrounding white space | build_report_crash_buckets
DCY-04 buildid_map:3414 T1 push | 3.1 cells are stripped of surrounding white space | build_report_crash_buckets
DCY-04 buildid_map:3963 T1 push | 3.1 cells are stripped of surrounding white space | build_report_crash_buckets
DCY-04 buildid_map:4205 T1 push | 3.1 cells are stripped of surrounding white space | build_report_crash_buckets
DCY-04 buildid_map:4930 T6 push | 6.2 historical build ids name retired toolchains | build_report_crash_buckets
DCY-04 kst_net:3081 T16 pull | G11 relinked preview addresses are not symbolication input | build_report_crash_buckets
DCY-04 buildid_map:3955 T1 push | 3.1 cells are stripped of surrounding white space | build_report_crash_buckets
DCY-04 kst_net:89 T16 pull | G11 relinked preview addresses are not symbolication input | build_report_crash_buckets
DOC-03 frame_register:251 T1 | 3.1 cells are stripped of surrounding white space | build_report_crash_buckets
DOC-03 frame_register:733 T13 | 6.3 template symbols carry a shortened label | build_report_crash_buckets
DOC-03 frame_register:1070 T8 | 3.6 restated header row inside a document table | build_report_crash_buckets
DOC-03 frame_register:1983 T8 | 3.6 restated header row inside a document table | build_report_crash_buckets
DOC-03 frame_register:2340 T8 | 3.6 restated header row inside a document table | build_report_crash_buckets
DOC-03 frame_register:2659 T8 | 3.6 restated header row inside a document table | build_report_crash_buckets
DOC-03 frame_register:3411 T13 | 6.3 template symbols carry a shortened label | build_report_crash_buckets
DOC-03 frame_register:3726 T13 | 6.3 template symbols carry a shortened label | build_report_crash_buckets
DOC-03 frame_register:4471 T1 | 3.1 cells are stripped of surrounding white space | build_report_crash_buckets
DOC-03 frame_register:4716 T13 | 6.3 template symbols carry a shortened label | build_report_crash_buckets
DOC-03 frame_register:5297 T15 | 6.3 noise frames are skipped | build_report_crash_buckets
DOC-03 frame_register:2632 T8 | 3.6 restated header row inside a document table | build_report_crash_buckets
DOC-03 frame_register:4934 T8 | 3.6 restated header row inside a document table | build_report_crash_buckets
DOC-03 frame_register:2380 T8 | 3.6 restated header row inside a document table | build_report_crash_buckets
DOC-03 frame_register:922 T13 | 6.3 template symbols carry a shortened label | build_report_crash_buckets
DOC-03 frame_register:1808 T8 | 3.6 restated header row inside a document table | build_report_crash_buckets
DOC-03 frame_register:5169 T13 | 6.3 template symbols carry a shortened label | build_report_crash_buckets
DOC-03 frame_register:1269 T8 | 3.6 restated header row inside a document table | build_report_crash_buckets
DOC-03 frame_register:322 T13 | 6.3 template symbols carry a shortened label | build_report_crash_buckets
PIN-01 pin:173 T1 | 3.1 cells are stripped of surrounding white space | build_report_crash_buckets
PIN-01 pin:902 T15 | 6.2 hot-fixed commit pinned against the cut | build_report_crash_buckets
PIN-01 pin:1046 T1 | 3.1 cells are stripped of surrounding white space | build_report_crash_buckets
PIN-01 pin:1913 T1 | 3.1 cells are stripped of surrounding white space | build_report_crash_buckets
PIN-01 pin:2262 T1 | 3.1 cells are stripped of surrounding white space | build_report_crash_buckets
PIN-01 pin:2792 T1 | 3.1 cells are stripped of surrounding white space | build_report_crash_buckets
PIN-01 pin:3483 T13 | 6.2 pins are keyed by the rebased sha | build_report_crash_buckets
PIN-01 pin:3680 T1 | 3.1 cells are stripped of surrounding white space | build_report_crash_buckets
PIN-01 pin:4435 T1 | 3.1 cells are stripped of surrounding white space | build_report_crash_buckets
PIN-01 pin:4601 T1 | 3.1 cells are stripped of surrounding white space | build_report_crash_buckets
PIN-01 pin:5205 T1 | 3.1 cells are stripped of surrounding white space | build_report_crash_buckets
PIN-01 pin:5943 T1 | 3.1 cells are stripped of surrounding white space | build_report_crash_buckets
PIN-01 pin:6037 T7 | 6.2 highest pin revision wins over an earlier lower revision | build_report_crash_buckets
PIN-01 pin:6028 T7 | 6.2 highest pin revision wins over an earlier lower revision | build_report_crash_buckets
PIN-01 pin:6018 T7 | 6.2 highest pin revision wins over an earlier lower revision | build_report_crash_buckets
PIN-01 pin:6003 T7 | 6.2 highest pin revision wins over an earlier lower revision | build_report_crash_buckets
PIN-01 pin:6025 T7 | 6.2 highest pin revision wins over an earlier lower revision | build_report_crash_buckets
PIN-01 pin:6053 T7 | 6.2 highest pin revision wins over an earlier lower revision | build_report_crash_buckets
PIN-01 pin:6049 T7 | 6.2 highest pin revision wins over an earlier lower revision | build_report_crash_buckets
PIN-01 pin:6012 T7 | 6.2 highest pin revision wins over an earlier lower revision | build_report_crash_buckets
PIN-01 pin:6039 T7 | 6.2 highest pin revision wins over an earlier lower revision | build_report_crash_buckets
PIN-01 pin:6009 T7 | 6.2 highest pin revision wins over an earlier lower revision | build_report_crash_buckets
PIN-01 pin:6021 T7 | 6.2 highest pin revision wins over an earlier lower revision | build_report_crash_buckets
PIN-01 pin:6050 T7 | 6.2 highest pin revision wins over an earlier lower revision | build_report_crash_buckets
PIN-01 pin:6002 T7 | 6.2 highest pin revision wins over an earlier lower revision | build_report_crash_buckets
PIN-01 pin:6016 T7 | 6.2 highest pin revision wins over an earlier lower revision | build_report_crash_buckets
PIN-01 pin:6020 T7 | 6.2 highest pin revision wins over an earlier lower revision | build_report_crash_buckets
PIN-01 pin:6010 T7 | 6.2 highest pin revision wins over an earlier lower revision | build_report_crash_buckets
PIN-01 pin:6045 T7 | 6.2 highest pin revision wins over an earlier lower revision | build_report_crash_buckets
PIN-01 pin:6000 T7 | 6.2 highest pin revision wins over an earlier lower revision | build_report_crash_buckets
PIN-01 pin:6008 T7 | 6.2 highest pin revision wins over an earlier lower revision | build_report_crash_buckets
PIN-01 pin:6058 T7 | 6.2 highest pin revision wins over an earlier lower revision | build_report_crash_buckets
PIN-01 pin:6001 T7 | 6.2 highest pin revision wins over an earlier lower revision | build_report_crash_buckets
PIN-01 pin:6013 T7 | 6.2 highest pin revision wins over an earlier lower revision | build_report_crash_buckets
PIN-01 pin:6038 T7 | 6.2 highest pin revision wins over an earlier lower revision | build_report_crash_buckets
PIN-01 pin:6033 T7 | 6.2 highest pin revision wins over an earlier lower revision | build_report_crash_buckets
PIN-01 pin:6042 T7 | 6.2 highest pin revision wins over an earlier lower revision | build_report_crash_buckets
PIN-01 pin:6005 T7 | 6.2 highest pin revision wins over an earlier lower revision | build_report_crash_buckets
PIN-01 pin:6019 T7 | 6.2 highest pin revision wins over an earlier lower revision | build_report_crash_buckets
PIN-01 pin:6024 T7 | 6.2 highest pin revision wins over an earlier lower revision | build_report_crash_buckets
PIN-01 pin:6048 T7 | 6.2 highest pin revision wins over an earlier lower revision | build_report_crash_buckets
PIN-01 pin:6056 T7 | 6.2 highest pin revision wins over an earlier lower revision | build_report_crash_buckets
PIN-01 pin:6034 T7 | 6.2 highest pin revision wins over an earlier lower revision | build_report_crash_buckets
PIN-01 pin:6004 T7 | 6.2 highest pin revision wins over an earlier lower revision | build_report_crash_buckets
PIN-01 pin:6057 T7 | 6.2 highest pin revision wins over an earlier lower revision | build_report_crash_buckets
PIN-01 pin:6055 T7 | 6.2 highest pin revision wins over an earlier lower revision | build_report_crash_buckets
PIN-01 pin:6032 T7 | 6.2 highest pin revision wins over an earlier lower revision | build_report_crash_buckets
PIN-01 pin:6029 T7 | 6.2 highest pin revision wins over an earlier lower revision | build_report_crash_buckets
PIN-01 pin:6007 T7 | 6.2 highest pin revision wins over an earlier lower revision | build_report_crash_buckets
PIN-01 pin:6040 T7 | 6.2 highest pin revision wins over an earlier lower revision | build_report_crash_buckets
PIN-01 pin:6051 T7 | 6.2 highest pin revision wins over an earlier lower revision | build_report_crash_buckets
PIN-01 pin:6026 T7 | 6.2 highest pin revision wins over an earlier lower revision | build_report_crash_buckets
PIN-01 pin:6014 T7 | 6.2 highest pin revision wins over an earlier lower revision | build_report_crash_buckets
PIN-01 pin:6031 T7 | 6.2 highest pin revision wins over an earlier lower revision | build_report_crash_buckets
PIN-01 pin:6011 T7 | 6.2 highest pin revision wins over an earlier lower revision | build_report_crash_buckets
PIN-01 pin:358 T1 | 3.1 cells are stripped of surrounding white space | build_report_crash_buckets
PIN-01 pin:4989 T13 | 6.2 pins are keyed by the rebased sha | build_report_crash_buckets
PIN-01 pin:4910 T1 | 3.1 cells are stripped of surrounding white space | build_report_crash_buckets
PIN-01 pin:1799 T1 | 3.1 cells are stripped of surrounding white space | build_report_crash_buckets
PIN-01 pin:2962 T1 | 3.1 cells are stripped of surrounding white space | build_report_crash_buckets
PIN-01 pin:1261 T1 | 3.1 cells are stripped of surrounding white space | build_report_crash_buckets
CMT-01 commits:294 T13 | 4.3 commit referenced by pre-rebase sha | module_core_bisection
CMT-01 commits:921 T7 | 4.3 Change-Seq, not log position, orders commits | module_core_bisection
CMT-01 commits:1108 T7 | 4.3 Change-Seq, not log position, orders commits | module_core_bisection
CMT-01 commits:1823 T7 | 4.3 Change-Seq, not log position, orders commits | module_core_bisection
CMT-01 commits:2165 T15 | 6.2 hot-fixed commits pinned against the cut | build_report_crash_buckets
CMT-01 commits:2747 T7 | 4.3 Change-Seq, not log position, orders commits | module_core_bisection
CMT-01 commits:3000 T11 | 4.3 commits at the window and toolchain boundaries | module_core_bisection
CMT-01 commits:3660 T7 | 4.3 Change-Seq, not log position, orders commits | module_core_bisection
CMT-01 commits:4243 T7 | 4.3 Change-Seq, not log position, orders commits | module_core_bisection
CMT-01 commits:4947 T7 | 4.3 Change-Seq, not log position, orders commits | module_core_bisection
CMT-01 commits:5200 T7 | 4.3 Change-Seq, not log position, orders commits | module_core_bisection
CMT-01 commits:5948 T7 | 4.3 Change-Seq, not log position, orders commits | module_core_bisection
CMT-01 commits:5508 T7 | 4.3 Change-Seq, not log position, orders commits | module_core_bisection
CMT-01 commits:3704 T7 | 4.3 Change-Seq, not log position, orders commits | module_core_bisection
CMT-01 commits:5013 T7 | 4.3 Change-Seq, not log position, orders commits | module_core_bisection
CMT-01 commits:1383 T7 | 4.3 Change-Seq, not log position, orders commits | module_core_bisection
CMT-01 commits:2539 T13 | 4.3 commit referenced by pre-rebase sha | module_core_bisection
CMT-01 commits:3748 T7 | 4.3 Change-Seq, not log position, orders commits | module_core_bisection
DCY-11 commits:429 T16 pull | G10 mirror sequence numbers are not authoritative | build_report_commits
DCY-11 commits:519 T7 pull | 4.3 Change-Seq, not log position, orders commits | module_core_bisection
DCY-11 commits:1418 T6 push | 4.3 pre-rebase shas no longer exist in the log | module_core_bisection
DCY-11 commits:1947 T13 pull | 4.3 Rewritten-From maps pre-rebase shas | module_core_bisection
DCY-11 commits:2233 T16 pull | G10 mirror sequence numbers are not authoritative | build_report_commits
DCY-11 commits:2764 T15 pull | 6.2 hot-fixed commits pinned against the cut | build_report_crash_buckets
DCY-11 commits:3004 T11 pull | 4.3 commits at the window and toolchain boundaries | module_core_bisection
DCY-11 commits:3602 T16 pull | G10 mirror sequence numbers are not authoritative | build_report_commits
DCY-11 commits:4154 T16 pull | G10 mirror sequence numbers are not authoritative | build_report_commits
DCY-11 commits:4997 T16 pull | G10 mirror sequence numbers are not authoritative | build_report_commits
DCY-11 commits:5073 T16 pull | G10 mirror sequence numbers are not authoritative | build_report_commits
DCY-11 commits:5616 T16 pull | G10 mirror sequence numbers are not authoritative | build_report_commits
DCY-11 commits:794 T16 pull | G10 mirror sequence numbers are not authoritative | build_report_commits
DCY-11 commits:2594 T16 pull | G10 mirror sequence numbers are not authoritative | build_report_commits
DCY-11 commits:4748 T16 pull | G10 mirror sequence numbers are not authoritative | build_report_commits
DCY-11 commits:2662 T16 pull | G10 mirror sequence numbers are not authoritative | build_report_commits
DCY-11 commits:332 T16 pull | G10 mirror sequence numbers are not authoritative | build_report_commits
DCY-11 commits:4280 T16 pull | G10 mirror sequence numbers are not authoritative | build_report_commits
DCY-11 commits:1607 T16 pull | G10 mirror sequence numbers are not authoritative | build_report_commits
DCY-11 commits:1002 T7 pull | 4.3 Change-Seq, not log position, orders commits | module_core_bisection
DCY-11 commits:1746 T16 pull | G10 mirror sequence numbers are not authoritative | build_report_commits
DCY-11 commits:4496 T16 pull | G10 mirror sequence numbers are not authoritative | build_report_commits
DCY-11 commits:5378 T16 pull | G10 mirror sequence numbers are not authoritative | build_report_commits
DCY-11 commits:3427 T16 pull | G10 mirror sequence numbers are not authoritative | build_report_commits
DCY-11 commits:3127 T16 pull | G10 mirror sequence numbers are not authoritative | build_report_commits
DCY-11 commits:491 T16 pull | G10 mirror sequence numbers are not authoritative | build_report_commits
DCY-11 commits:1269 T16 pull | G10 mirror sequence numbers are not authoritative | build_report_commits
DCY-11 commits:1058 T16 pull | G10 mirror sequence numbers are not authoritative | build_report_commits
DCY-11 commits:4614 T16 pull | G10 mirror sequence numbers are not authoritative | build_report_commits
DCY-11 commits:2978 T16 pull | G10 mirror sequence numbers are not authoritative | build_report_commits
DCY-11 commits:5421 T16 pull | G10 mirror sequence numbers are not authoritative | build_report_commits
DCY-11 commits:93 T16 pull | G10 mirror sequence numbers are not authoritative | build_report_commits
DCY-11 commits:5517 T16 pull | G10 mirror sequence numbers are not authoritative | build_report_commits
DCY-11 commits:1859 T16 pull | G10 mirror sequence numbers are not authoritative | build_report_commits
REG-01 modules:379 T11 | 4.2 decommission instant vs corrected start | build_report_module_identity
REG-01 modules:545 T5 | 3.5 9999-12-31T23:59:59Z is an open bound | build_report_module_identity
REG-01 aliases:273 T1 | 3.1 cells are stripped of surrounding white space | build_report_module_identity
REG-01 aliases:996 T5 | 3.5 9999-12-31T23:59:59Z is an open bound | build_report_module_identity
REG-01 aliases:1419 T1 | 3.1 cells are stripped of surrounding white space | build_report_module_identity
REG-01 aliases:1891 T5 | 3.5 9999-12-31T23:59:59Z is an open bound | build_report_module_identity
REG-01 aliases:2060 T5 | 3.5 9999-12-31T23:59:59Z is an open bound | build_report_module_identity
REG-01 aliases:2823 T5 | 3.5 9999-12-31T23:59:59Z is an open bound | build_report_module_identity
REG-01 aliases:3180 T3 | 3.4 register timestamps with an explicit offset | build_report_module_identity
REG-01 aliases:3526 T1 | 3.1 cells are stripped of surrounding white space | build_report_module_identity
REG-01 aliases:4023 T5 | 3.5 9999-12-31T23:59:59Z is an open bound | build_report_module_identity
REG-01 aliases:4908 T7 | 3.1 alias validity window | build_report_module_identity
REG-01 aliases:5269 T5 | 3.5 9999-12-31T23:59:59Z is an open bound | build_report_module_identity
REG-01 modules:367 T6 | 10.3 decommissioned before the window: not reported | module_core_states
REG-01 aliases:2791 T5 | 3.5 9999-12-31T23:59:59Z is an open bound | build_report_module_identity
REG-01 modules:568 T5 | 3.5 9999-12-31T23:59:59Z is an open bound | build_report_module_identity
REG-01 modules:121 T5 | 3.5 9999-12-31T23:59:59Z is an open bound | build_report_module_identity
DCY-06 alias:133 T5 push | 3.5 9999-12-31T23:59:59Z is an open bound | build_report_module_identity
DCY-06 alias:761 T8 push | 3.6 column aliases | build_report_module_identity
DCY-06 alias:1258 T1 push | 3.1 cells are stripped of surrounding white space | build_report_module_identity
DCY-06 alias:1926 T6 push | 4.2 decommissioned module | build_report_module_identity
DCY-06 alias:2441 T8 push | 3.6 column aliases | build_report_module_identity
DCY-06 alias:2860 T8 push | 3.6 column aliases | build_report_module_identity
DCY-06 alias:3159 T5 push | 3.5 9999-12-31T23:59:59Z is an open bound | build_report_module_identity
DCY-06 alias:3713 T8 push | 3.6 column aliases | build_report_module_identity
DCY-06 alias:4033 T8 push | 3.6 column aliases | build_report_module_identity
DCY-06 alias:4512 T5 push | 3.5 9999-12-31T23:59:59Z is an open bound | build_report_module_identity
DCY-06 alias:5313 T16 pull | G4 rows outside the stage window are not authoritative | build_report_module_identity
DCY-06 alias:1014 T1 push | 3.1 cells are stripped of surrounding white space | build_report_module_identity
DCY-06 alias:2415 T5 push | 3.5 9999-12-31T23:59:59Z is an open bound | build_report_module_identity
DCY-06 alias:457 T5 push | 3.5 9999-12-31T23:59:59Z is an open bound | build_report_module_identity
DCY-06 alias:1984 T5 push | 3.5 9999-12-31T23:59:59Z is an open bound | build_report_module_identity
DCY-06 alias:2580 T7 pull | 3.1 alias validity window | build_report_module_identity
DCY-06 alias:496 T1 push | 3.1 cells are stripped of surrounding white space | build_report_module_identity
DCY-06 alias:1050 T5 push | 3.5 9999-12-31T23:59:59Z is an open bound | build_report_module_identity
DCY-06 alias:3136 T5 push | 3.5 9999-12-31T23:59:59Z is an open bound | build_report_module_identity
DCY-06 alias:1309 T8 push | 3.6 column aliases | build_report_module_identity
DCY-06 alias:5066 T5 push | 3.5 9999-12-31T23:59:59Z is an open bound | build_report_module_identity
DCY-06 alias:4071 T1 push | 3.1 cells are stripped of surrounding white space | build_report_module_identity
DCY-06 alias:1633 T5 push | 3.5 9999-12-31T23:59:59Z is an open bound | build_report_module_identity
DCY-06 alias:291 T1 push | 3.1 cells are stripped of surrounding white space | build_report_module_identity
DCY-06 alias:4829 T5 push | 3.5 9999-12-31T23:59:59Z is an open bound | build_report_module_identity
DCY-06 alias:3730 T8 push | 3.6 column aliases | build_report_module_identity
DCY-06 alias:4348 T8 push | 3.6 column aliases | build_report_module_identity
DCY-06 alias:846 T8 push | 3.6 column aliases | build_report_module_identity
DCY-06 alias:3846 T5 push | 3.5 9999-12-31T23:59:59Z is an open bound | build_report_module_identity
DCY-06 alias:994 T5 push | 3.5 9999-12-31T23:59:59Z is an open bound | build_report_module_identity
DCY-06 alias:182 T1 push | 3.1 cells are stripped of surrounding white space | build_report_module_identity
DCY-06 alias:5241 T13 pull | G4 in-window rename only here | build_report_module_identity
REG-02 tests:267 T5 | 3.5 9999-12-31T23:59:59Z is an open bound | build_report_module_identity
REG-02 tests:794 T1 | 3.1 cells are stripped of surrounding white space | module_metrics_flaky_and_quarantine
REG-02 tests:1179 T3 | 3.4 register timestamps with an explicit offset | module_metrics_flaky_and_quarantine
REG-02 tests:1803 T15 | 5.3 flaky tests stay registered | module_metrics_flaky_and_quarantine
REG-02 tests:2362 T11 | 5.2 registration window | module_metrics_counts_and_rates
REG-02 tests:2765 T3 | 3.4 register timestamps with an explicit offset | module_metrics_flaky_and_quarantine
REG-02 tests:3430 T5 | 3.5 9999-12-31T23:59:59Z is an open bound | build_report_module_identity
REG-02 tests:3867 T3 | 3.4 register timestamps with an explicit offset | module_metrics_flaky_and_quarantine
REG-02 tests:4254 T3 | 3.4 register timestamps with an explicit offset | module_metrics_flaky_and_quarantine
REG-02 tests:4645 T5 | 3.5 9999-12-31T23:59:59Z is an open bound | build_report_module_identity
REG-02 tests:5101 T3 | 3.4 register timestamps with an explicit offset | module_metrics_flaky_and_quarantine
REG-02 tests:720 T3 | 3.4 register timestamps with an explicit offset | module_metrics_flaky_and_quarantine
REG-02 tests:1668 T3 | 3.4 register timestamps with an explicit offset | module_metrics_flaky_and_quarantine
REG-02 tests:41 T3 | 3.4 register timestamps with an explicit offset | module_metrics_flaky_and_quarantine
REG-02 tests:3021 T1 | 3.1 test reference module part normalised | module_metrics_flaky_and_quarantine
REG-02 tests:4873 T5 | 3.5 9999-12-31T23:59:59Z is an open bound | build_report_module_identity
REG-02 tests:4057 T3 | 3.4 register timestamps with an explicit offset | module_metrics_flaky_and_quarantine
REG-03 entries:356 T3 | 3.4 register timestamps with an explicit offset | module_metrics_flaky_and_quarantine
REG-03 entries:810 T7 | 5.4 latest action at or before the start decides | module_metrics_flaky_and_quarantine
REG-03 entries:1220 T1 | 3.1 test reference module part normalised | module_metrics_flaky_and_quarantine
REG-03 entries:1778 T6 | 5.4 revoked entries never happened | module_metrics_flaky_and_quarantine
REG-03 entries:2442 T3 | 3.4 register timestamps with an explicit offset | module_metrics_flaky_and_quarantine
REG-03 entries:2553 T3 | 3.4 register timestamps with an explicit offset | module_metrics_flaky_and_quarantine
REG-03 entries:3377 T7 | 5.4 latest action at or before the start decides | module_metrics_flaky_and_quarantine
REG-03 entries:3699 T3 | 3.4 register timestamps with an explicit offset | module_metrics_flaky_and_quarantine
REG-03 entries:4439 T3 | 3.4 register timestamps with an explicit offset | module_metrics_flaky_and_quarantine
REG-03 entries:4521 T3 | 3.4 register timestamps with an explicit offset | module_metrics_flaky_and_quarantine
REG-03 entries:5041 T7 | 5.4 latest action at or before the start decides | module_metrics_flaky_and_quarantine
REG-03 entries:162 T3 | 3.4 register timestamps with an explicit offset | module_metrics_flaky_and_quarantine
REG-03 entries:4610 T3 | 3.4 register timestamps with an explicit offset | module_metrics_flaky_and_quarantine
REG-03 entries:3128 T7 | 5.4 latest action at or before the start decides | module_metrics_flaky_and_quarantine
REG-03 entries:3271 T3 | 3.4 register timestamps with an explicit offset | module_metrics_flaky_and_quarantine
REG-03 entries:2718 T1 | 3.1 test reference module part normalised | module_metrics_flaky_and_quarantine
REG-03 entries:946 T1 | 3.1 test reference module part normalised | module_metrics_flaky_and_quarantine
REG-03 entries:1532 T3 | 3.4 register timestamps with an explicit offset | module_metrics_flaky_and_quarantine
REG-03 entries:934 T3 | 3.4 register timestamps with an explicit offset | module_metrics_flaky_and_quarantine
REG-03 entries:3923 T7 | 5.4 latest action at or before the start decides | module_metrics_flaky_and_quarantine
DCY-09 flake_rates:387 T16 pull | G9 dashboard labels are not the flaky rule | module_metrics_flaky_and_quarantine
DCY-09 flake_rates:742 T1 push | 3.1 test reference module part normalised | module_metrics_flaky_and_quarantine
DCY-09 flake_rates:1367 T8 push | 3.6 restated header row inside a document table | module_metrics_flaky_and_quarantine
DCY-09 flake_rates:1511 T7 pull | 5.3 carried flaky state outlives the dashboard rate | module_metrics_flaky_and_quarantine
DCY-09 flake_rates:2021 T16 pull | G9 dashboard labels are not the flaky rule | module_metrics_flaky_and_quarantine
DCY-09 flake_rates:2619 T16 pull | G9 dashboard labels are not the flaky rule | module_metrics_flaky_and_quarantine
DCY-09 flake_rates:3428 T16 pull | G9 dashboard labels are not the flaky rule | module_metrics_flaky_and_quarantine
DCY-09 flake_rates:3819 T16 pull | G9 dashboard labels are not the flaky rule | module_metrics_flaky_and_quarantine
DCY-09 flake_rates:4420 T16 pull | G9 dashboard labels are not the flaky rule | module_metrics_flaky_and_quarantine
DCY-09 flake_rates:4967 T16 pull | G9 dashboard labels are not the flaky rule | module_metrics_flaky_and_quarantine
DCY-09 quarantine_revocations:41 T6 push | 5.4 revoked quarantine entries never happened | module_metrics_flaky_and_quarantine
DCY-09 quarantine_revocations:50 T13 pull | G9 only record of the revocation | module_metrics_flaky_and_quarantine
DCY-09 flake_rates:1477 T16 pull | G9 dashboard labels are not the flaky rule | module_metrics_flaky_and_quarantine
DCY-09 quarantine_revocations:159 T8 push | 3.6 restated header row inside a document table | module_metrics_flaky_and_quarantine
DCY-09 flake_rates:616 T16 pull | G9 dashboard labels are not the flaky rule | module_metrics_flaky_and_quarantine
DCY-09 flake_rates:204 T16 pull | G9 dashboard labels are not the flaky rule | module_metrics_flaky_and_quarantine
DCY-09 flake_rates:2948 T16 pull | G9 dashboard labels are not the flaky rule | module_metrics_flaky_and_quarantine
DCY-09 quarantine_revocations:36 T6 push | 5.4 revoked quarantine entries never happened | module_metrics_flaky_and_quarantine
DCY-09 flake_rates:314 T16 pull | G9 dashboard labels are not the flaky rule | module_metrics_flaky_and_quarantine
DCY-09 quarantine_revocations:144 T8 push | 3.6 restated header row inside a document table | module_metrics_flaky_and_quarantine
DCY-09 quarantine_revocations:11 T6 push | 5.4 revoked quarantine entries never happened | module_metrics_flaky_and_quarantine
DCY-09 quarantine_revocations:112 T8 push | 3.6 restated header row inside a document table | module_metrics_flaky_and_quarantine
DCY-09 quarantine_revocations:96 T13 pull | G9 only record of the revocation | module_metrics_flaky_and_quarantine
DCY-09 flake_rates:3913 T1 push | 3.1 cells are stripped of surrounding white space | module_metrics_flaky_and_quarantine
DCY-09 flake_rates:3529 T16 pull | G9 dashboard labels are not the flaky rule | module_metrics_flaky_and_quarantine
DCY-09 flake_rates:2015 T16 pull | G9 dashboard labels are not the flaky rule | module_metrics_flaky_and_quarantine
DCY-09 quarantine_revocations:35 T13 pull | G9 only record of the revocation | module_metrics_flaky_and_quarantine
DCY-09 flake_rates:4664 T16 pull | G9 dashboard labels are not the flaky rule | module_metrics_flaky_and_quarantine
DCY-09 flake_rates:385 T16 pull | G9 dashboard labels are not the flaky rule | module_metrics_flaky_and_quarantine
DCY-09 flake_rates:1948 T16 pull | G9 dashboard labels are not the flaky rule | module_metrics_flaky_and_quarantine
DCY-09 quarantine_revocations:120 T6 push | 5.4 revoked quarantine entries never happened | module_metrics_flaky_and_quarantine
DCY-09 quarantine_revocations:74 T8 push | 3.6 restated header row inside a document table | module_metrics_flaky_and_quarantine
DCY-09 flake_rates:990 T16 pull | G9 dashboard labels are not the flaky rule | module_metrics_flaky_and_quarantine
DCY-09 flake_rates:3417 T16 pull | G9 dashboard labels are not the flaky rule | module_metrics_flaky_and_quarantine
HST-01 host:98 T7 | 4.4 registry tz is current; history decides per date | build_report_time_and_scope
HST-01 host:842 T14 | G3 footnote: lab hosts are out of scope even on main | build_report_time_and_scope
HST-01 host:1267 T1 | 3.1 host names are case-insensitive | build_report_time_and_scope
HST-01 host:1874 T1 | 3.1 host names are case-insensitive | build_report_time_and_scope
HST-01 host:2102 T7 | 4.4 registry tz is current; history decides per date | build_report_time_and_scope
HST-01 host:2633 T1 | 3.1 host names are case-insensitive | build_report_time_and_scope
HST-01 host:3456 T1 | 3.1 host names are case-insensitive | build_report_time_and_scope
HST-01 host:3813 T1 | 3.1 host names are case-insensitive | build_report_time_and_scope
HST-01 host:4415 T13 | G7 eph hosts split between hosts.ini and the CMDB | build_report_time_and_scope
HST-01 host:4868 T13 | G7 eph hosts split between hosts.ini and the CMDB | build_report_time_and_scope
HST-01 host:5005 T13 | G7 eph hosts split between hosts.ini and the CMDB | build_report_time_and_scope
HST-01 host:3997 T7 | 4.4 registry tz is current; history decides per date | build_report_time_and_scope
HST-01 host:3049 T14 | G3 footnote: lab hosts are out of scope even on main | build_report_time_and_scope
HST-01 host:2683 T14 | G3 footnote: lab hosts are out of scope even on main | build_report_time_and_scope
HST-01 host:1235 T14 | G3 footnote: lab hosts are out of scope even on main | build_report_time_and_scope
HST-01 host:831 T14 | G3 footnote: lab hosts are out of scope even on main | build_report_time_and_scope
DCY-08 host:450 T16 pull | G7 CMDB site ignored where hosts.ini knows the host | build_report_attempt_precedence
DCY-08 host:822 T1 push | 3.1 host names are case-insensitive | build_report_time_and_scope
DCY-08 host:1233 T6 push | G3 lab hosts are out of scope | build_report_time_and_scope
DCY-08 host:1817 T7 pull | 4.4 tz history supersedes the registry tz | build_report_time_and_scope
DCY-08 host:2472 T16 pull | G7 CMDB site ignored where hosts.ini knows the host | build_report_attempt_precedence
DCY-08 host:2999 T16 pull | G7 CMDB site ignored where hosts.ini knows the host | build_report_attempt_precedence
DCY-08 host:3148 T16 pull | G7 CMDB site ignored where hosts.ini knows the host | build_report_attempt_precedence
DCY-08 host:3625 T16 pull | G7 CMDB site ignored where hosts.ini knows the host | build_report_attempt_precedence
DCY-08 host:4400 T14 push | G5 eph hosts lost by the core exporters | build_report_membership
DCY-08 host:4991 T13 pull | G7 CMDB authoritative only for hosts absent from hosts.ini | build_report_attempt_precedence
DCY-08 host:5352 T14 push | G5 eph hosts lost by the core exporters | build_report_membership
DCY-08 host:5658 T14 push | G5 eph hosts lost by the core exporters | build_report_membership
DCY-08 host:273 T16 pull | G7 CMDB site ignored where hosts.ini knows the host | build_report_attempt_precedence
DCY-08 host:3440 T16 pull | G7 CMDB site ignored where hosts.ini knows the host | build_report_attempt_precedence
DCY-08 host:3027 T16 pull | G7 CMDB site ignored where hosts.ini knows the host | build_report_attempt_precedence
DCY-08 host:4450 T14 push | G5 eph hosts lost by the core exporters | build_report_membership
DCY-08 host:5693 T14 push | G5 eph hosts lost by the core exporters | build_report_membership
DCY-08 host:3190 T16 pull | G7 CMDB site ignored where hosts.ini knows the host | build_report_attempt_precedence
DCY-08 host:94 T16 pull | G7 CMDB site ignored where hosts.ini knows the host | build_report_attempt_precedence
DCY-08 host:3365 T16 pull | G7 CMDB site ignored where hosts.ini knows the host | build_report_attempt_precedence
DCY-08 host:1190 T16 pull | G7 CMDB site ignored where hosts.ini knows the host | build_report_attempt_precedence
DCY-08 host:4970 T14 push | G5 eph hosts lost by the core exporters | build_report_membership
DCY-08 host:3938 T16 pull | G7 CMDB site ignored where hosts.ini knows the host | build_report_attempt_precedence
DCY-08 host:3659 T16 pull | G7 CMDB site ignored where hosts.ini knows the host | build_report_attempt_precedence
DCY-08 host:5062 T14 push | G5 eph hosts lost by the core exporters | build_report_membership
DCY-08 host:263 T16 pull | G7 CMDB site ignored where hosts.ini knows the host | build_report_attempt_precedence
DCY-08 host:1414 T16 pull | G7 CMDB site ignored where hosts.ini knows the host | build_report_attempt_precedence
DCY-08 host:3037 T16 pull | G7 CMDB site ignored where hosts.ini knows the host | build_report_attempt_precedence
DCY-08 host:2521 T16 pull | G7 CMDB site ignored where hosts.ini knows the host | build_report_attempt_precedence
DCY-08 host:4489 T14 push | G5 eph hosts lost by the core exporters | build_report_membership
DCY-08 host:4200 T16 pull | G7 CMDB site ignored where hosts.ini knows the host | build_report_attempt_precedence
HST-02 skew:266 T9 | 3.6 ragged row with trailing empty cells | build_report_time_and_scope
HST-02 skew:740 T4 | 3.2 parenthesised negative | build_report_time_and_scope
HST-02 skew:1341 T3 | 3.4 register timestamps with an explicit offset | build_report_time_and_scope
HST-02 skew:1866 T8 | 3.6 #header restates reordered columns | build_report_time_and_scope
HST-02 skew:2182 T1 | 3.1 host names are case-insensitive | build_report_time_and_scope
HST-02 skew:2751 T5 | 4.4 skew sentinel -1 means probe failed | build_report_time_and_scope
HST-02 skew:3053 T4 | 3.2 negative zero is zero | build_report_time_and_scope
HST-02 skew:3761 T4 | 3.2 negative zero is zero | build_report_time_and_scope
HST-02 skew:4454 T4 | 3.2 negative zero is zero | build_report_time_and_scope
HST-02 skew:4535 T4 | 3.2 parenthesised negative | build_report_time_and_scope
HST-02 skew:5373 T4 | 3.2 negative zero is zero | build_report_time_and_scope
HST-02 skew:5989 T4 | 3.2 parenthesised negative | build_report_time_and_scope
HST-02 skew:6260 T9 | 3.6 ragged row with trailing empty cells | build_report_time_and_scope
HST-02 skew:6917 T4 | 3.2 negative zero is zero | build_report_time_and_scope
HST-02 skew:7023 T4 | 3.2 negative zero is zero | build_report_time_and_scope
HST-02 skew:4842 T4 | 3.2 parenthesised negative | build_report_time_and_scope
DCY-13 estimate:60 T16 pull | E10 estimate ignored where measured | build_report_time_and_scope
DCY-13 estimate:802 T9 push | 3.6 ragged row with trailing empty cells | build_report_time_and_scope
DCY-13 estimate:1027 T7 pull | E10 a measurement supersedes the estimate | build_report_time_and_scope
DCY-13 estimate:1698 T8 push | 3.6 #header restates reordered columns | build_report_time_and_scope
DCY-13 estimate:2166 T6 push | G3 lab hosts are out of scope | build_report_time_and_scope
DCY-13 estimate:2908 T13 pull | E10 estimate used only for hosts with no measurement | build_report_time_and_scope
DCY-13 estimate:3348 T1 push | 3.1 cells are stripped of surrounding white space | build_report_time_and_scope
DCY-13 estimate:3794 T16 pull | E10 estimate ignored where measured | build_report_time_and_scope
DCY-13 estimate:4365 T16 pull | E10 estimate ignored where measured | build_report_time_and_scope
DCY-13 estimate:4643 T16 pull | E10 estimate ignored where measured | build_report_time_and_scope
DCY-13 estimate:5064 T16 pull | E10 estimate ignored where measured | build_report_time_and_scope
DCY-13 estimate:5572 T9 push | 3.6 ragged row with trailing empty cells | build_report_time_and_scope
DCY-13 estimate:0 T10 push | 3.6 byte order mark before the control block | selftest_control_chain
DCY-13 estimate:1323 T16 pull | E10 estimate ignored where measured | build_report_time_and_scope
DCY-13 estimate:5132 T16 pull | E10 estimate ignored where measured | build_report_time_and_scope
DCY-13 estimate:1386 T16 pull | E10 estimate ignored where measured | build_report_time_and_scope
DCY-13 estimate:1017 T16 pull | E10 estimate ignored where measured | build_report_time_and_scope
DCY-13 estimate:4864 T16 pull | E10 estimate ignored where measured | build_report_time_and_scope
DCY-13 estimate:5492 T16 pull | E10 estimate ignored where measured | build_report_time_and_scope
DCY-13 estimate:3832 T16 pull | E10 estimate ignored where measured | build_report_time_and_scope
DCY-13 estimate:4484 T16 pull | E10 estimate ignored where measured | build_report_time_and_scope
DCY-13 estimate:3838 T16 pull | E10 estimate ignored where measured | build_report_time_and_scope
DCY-13 estimate:3857 T16 pull | E10 estimate ignored where measured | build_report_time_and_scope
DCY-13 estimate:4736 T16 pull | E10 estimate ignored where measured | build_report_time_and_scope
DCY-13 estimate:5106 T16 pull | E10 estimate ignored where measured | build_report_time_and_scope
DCY-13 estimate:4775 T16 pull | E10 estimate ignored where measured | build_report_time_and_scope
DCY-13 estimate:5014 T16 pull | E10 estimate ignored where measured | build_report_time_and_scope
DCY-13 estimate:1555 T16 pull | E10 estimate ignored where measured | build_report_time_and_scope
DCY-13 estimate:2741 T16 pull | E10 estimate ignored where measured | build_report_time_and_scope
DCY-13 estimate:2359 T16 pull | E10 estimate ignored where measured | build_report_time_and_scope
DCY-13 estimate:1171 T16 pull | E10 estimate ignored where measured | build_report_time_and_scope
DOC-05 tz_history:142 T8 | 3.6 restated header row inside a document table | build_report_time_and_scope
DOC-05 tz_history:567 T15 | 4.4 a move before the window still decides early dates | build_report_time_and_scope
DOC-05 tz_history:1209 T1 | 3.1 host names are case-insensitive | build_report_time_and_scope
DOC-05 tz_history:1650 T3 | 4.4 tz in force on the local calendar date | build_report_time_and_scope
DOC-05 tz_history:2026 T1 | 3.1 cells are stripped of surrounding white space | build_report_time_and_scope
DOC-05 tz_history:2535 T8 | 3.6 restated header row inside a document table | build_report_time_and_scope
DOC-05 tz_history:3124 T1 | 3.1 cells are stripped of surrounding white space | build_report_time_and_scope
DOC-05 tz_history:3832 T3 | 4.4 tz in force on the local calendar date | build_report_time_and_scope
DOC-05 tz_history:4004 T8 | 3.6 restated header row inside a document table | build_report_time_and_scope
DOC-05 tz_history:4988 T8 | 3.6 restated header row inside a document table | build_report_time_and_scope
DOC-05 tz_history:5053 T1 | 3.1 host names are case-insensitive | build_report_time_and_scope
DOC-05 tz_history:5911 T1 | 3.1 host names are case-insensitive | build_report_time_and_scope
DOC-05 tz_history:6341 T1 | 3.1 cells are stripped of surrounding white space | build_report_time_and_scope
DOC-05 tz_history:3318 T8 | 3.6 restated header row inside a document table | build_report_time_and_scope
DOC-05 tz_history:1944 T1 | 3.1 host names are case-insensitive | build_report_time_and_scope
DOC-05 tz_history:4903 T8 | 3.6 restated header row inside a document table | build_report_time_and_scope
DOC-05 tz_history:1480 T8 | 3.6 restated header row inside a document table | build_report_time_and_scope
DOC-05 tz_history:3301 T15 | 4.4 a move before the window still decides early dates | build_report_time_and_scope
DOC-05 tz_history:6189 T8 | 3.6 restated header row inside a document table | build_report_time_and_scope
MNT-01 vevent:446 T7 | 4.8 highest SEQUENCE is the event | build_report_attempt_precedence
MNT-01 vevent:887 T6 | 4.8 cancelled windows do not apply | build_report_attempt_precedence
MNT-01 vevent:1145 T3 | 4.8 TZID wall times | build_report_time_and_scope
MNT-01 vevent:1931 T11 | E7 windows are half-open | build_report_attempt_precedence
MNT-01 vevent:2173 T11 | E7 windows are half-open | build_report_attempt_precedence
MNT-01 vevent:2858 T6 | 4.8 cancelled windows do not apply | build_report_attempt_precedence
MNT-01 vevent:3146 T6 | 4.8 cancelled windows do not apply | build_report_attempt_precedence
MNT-01 vevent:3899 T6 | 4.8 cancelled windows do not apply | build_report_attempt_precedence
MNT-01 vevent:4111 T3 | 4.8 TZID wall times | build_report_time_and_scope
MNT-01 vevent:4732 T11 | E7 windows are half-open | build_report_attempt_precedence
MNT-01 vevent:5087 T11 | E7 windows are half-open | build_report_attempt_precedence
MNT-01 vevent:814 T11 | E7 windows are half-open | build_report_attempt_precedence
MNT-01 vevent:809 T3 | 4.8 TZID wall times | build_report_time_and_scope
MNT-01 vevent:1633 T11 | E7 windows are half-open | build_report_attempt_precedence
MNT-01 vevent:2707 T7 | 4.8 highest SEQUENCE is the event | build_report_attempt_precedence
MNT-01 vevent:3641 T6 | 4.8 cancelled windows do not apply | build_report_attempt_precedence
MNT-01 vevent:1822 T11 | E7 windows are half-open | build_report_attempt_precedence
MNT-01 vevent:787 T6 | 4.8 cancelled windows do not apply | build_report_attempt_precedence
MNT-01 vevent:2985 T6 | 4.8 cancelled windows do not apply | build_report_attempt_precedence
VOD-01 void_actions:360 T3 | 3.4 register timestamps with an explicit offset | build_report_membership
VOD-01 void_actions:734 T9 | 3.6 ragged row with trailing empty cells | build_report_membership
VOD-01 void_actions:1354 T8 | 3.6 #header restates reordered columns | build_report_membership
VOD-01 void_actions:1694 T7 | 4.7 a later UNVOID reinstates the build | build_report_attempt_precedence
VOD-01 void_actions:2114 T6 | 4.7 latest action by sequence decides | build_report_attempt_precedence
VOD-01 void_actions:2520 T1 | 3.1 build key spellings | build_report_attempt_precedence
VOD-01 void_actions:3010 T11 | 4.7 void actions apply by seq whatever their date | build_report_attempt_precedence
VOD-01 void_actions:3668 T9 | 3.6 ragged row with trailing empty cells | build_report_membership
VOD-01 void_actions:4334 T9 | 3.6 ragged row with trailing empty cells | build_report_membership
VOD-01 void_actions:4964 T3 | 3.4 register timestamps with an explicit offset | build_report_membership
VOD-01 void_actions:5067 T9 | 3.6 ragged row with trailing empty cells | build_report_membership
VOD-01 void_actions:0 T10 | 3.6 byte order mark before the control block | selftest_control_chain
VOD-01 void_actions:4900 T9 | 3.6 ragged row with trailing empty cells | build_report_membership
VOD-01 void_actions:843 T9 | 3.6 ragged row with trailing empty cells | build_report_membership
VOD-01 void_actions:2174 T6 | 4.7 latest action by sequence decides | build_report_attempt_precedence
VOD-01 void_actions:898 T3 | 3.4 register timestamps with an explicit offset | build_report_membership
VOD-01 void_actions:1826 T8 | 3.6 #header restates reordered columns | build_report_membership
VOD-01 void_actions:59 T9 | 3.6 ragged row with trailing empty cells | build_report_membership
VOD-01 void_actions:4725 T9 | 3.6 ragged row with trailing empty cells | build_report_membership
VOD-01 void_actions:3347 T9 | 3.6 ragged row with trailing empty cells | build_report_membership
VOD-02 void_actions:475 T8 | 3.6 column aliases | build_report_membership
VOD-02 void_actions:823 T3 | 3.4 register timestamps with an explicit offset | build_report_membership
VOD-02 void_actions:1457 T6 | 4.7 latest action by sequence decides | build_report_attempt_precedence
VOD-02 void_actions:1953 T7 | 4.7 a later UNVOID reinstates the build | build_report_attempt_precedence
VOD-02 void_actions:2233 T1 | 3.1 build key spellings | build_report_attempt_precedence
VOD-02 void_actions:2850 T11 | 4.7 void actions apply by seq whatever their date | build_report_attempt_precedence
VOD-02 void_actions:3435 T8 | 3.6 column aliases | build_report_membership
VOD-02 void_actions:3602 T6 | 4.7 latest action by sequence decides | build_report_attempt_precedence
VOD-02 void_actions:4383 T8 | 3.6 column aliases | build_report_membership
VOD-02 void_actions:4627 T3 | 3.4 register timestamps with an explicit offset | build_report_membership
VOD-02 void_actions:5069 T3 | 3.4 register timestamps with an explicit offset | build_report_membership
VOD-02 void_actions:0 T10 | 3.6 byte order mark before the control block | selftest_control_chain
VOD-02 void_actions:2669 T8 | 3.6 column aliases | build_report_membership
VOD-02 void_actions:4725 T6 | 4.7 latest action by sequence decides | build_report_attempt_precedence
VOD-02 void_actions:858 T6 | 4.7 latest action by sequence decides | build_report_attempt_precedence
VOD-02 void_actions:3127 T6 | 4.7 latest action by sequence decides | build_report_attempt_precedence
VOD-02 void_actions:4098 T3 | 3.4 register timestamps with an explicit offset | build_report_membership
VOD-02 void_actions:2083 T6 | 4.7 latest action by sequence decides | build_report_attempt_precedence
VOD-02 void_actions:441 T3 | 3.4 register timestamps with an explicit offset | build_report_membership
DCY-12 void_actions:256 T16 pull | G13 uncountersigned v2 actions are ignored | build_report_membership
DCY-12 void_actions:672 T3 pull | 3.4 register timestamps with an explicit offset | build_report_membership
DCY-12 void_actions:1382 T8 push | 3.6 column aliases | build_report_membership
DCY-12 void_actions:1928 T6 push | 4.7 latest action by sequence decides | build_report_attempt_precedence
DCY-12 void_actions:2286 T7 pull | 4.7 a later UNVOID reinstates the build | build_report_attempt_precedence
DCY-12 void_actions:2977 T1 push | 3.1 build key spellings | build_report_attempt_precedence
DCY-12 void_actions:3194 T13 pull | G13 countersigned v2 actions are authoritative | build_report_membership
DCY-12 void_actions:3545 T11 pull | 4.7 void actions apply by seq whatever their date | build_report_attempt_precedence
DCY-12 void_actions:4401 T16 pull | G13 uncountersigned v2 actions are ignored | build_report_membership
DCY-12 void_actions:4510 T16 pull | G13 uncountersigned v2 actions are ignored | build_report_membership
DCY-12 void_actions:5086 T16 pull | G13 uncountersigned v2 actions are ignored | build_report_membership
DCY-12 void_actions:1431 T16 pull | G13 uncountersigned v2 actions are ignored | build_report_membership
DCY-12 void_actions:3682 T16 pull | G13 uncountersigned v2 actions are ignored | build_report_membership
DCY-12 void_actions:1486 T16 pull | G13 uncountersigned v2 actions are ignored | build_report_membership
DCY-12 void_actions:3418 T16 pull | G13 uncountersigned v2 actions are ignored | build_report_membership
DCY-12 void_actions:2930 T16 pull | G13 uncountersigned v2 actions are ignored | build_report_membership
DCY-12 void_actions:2953 T16 pull | G13 uncountersigned v2 actions are ignored | build_report_membership
DCY-12 void_actions:2202 T16 pull | G13 uncountersigned v2 actions are ignored | build_report_membership
DCY-12 void_actions:960 T16 pull | G13 uncountersigned v2 actions are ignored | build_report_membership
DCY-12 void_actions:249 T16 pull | G13 uncountersigned v2 actions are ignored | build_report_membership
DCY-12 void_actions:3149 T16 pull | G13 uncountersigned v2 actions are ignored | build_report_membership
DCY-12 void_actions:3730 T16 pull | G13 uncountersigned v2 actions are ignored | build_report_membership
DCY-12 void_actions:3185 T16 pull | G13 uncountersigned v2 actions are ignored | build_report_membership
DCY-12 void_actions:3559 T16 pull | G13 uncountersigned v2 actions are ignored | build_report_membership
DCY-12 void_actions:2764 T16 pull | G13 uncountersigned v2 actions are ignored | build_report_membership
DCY-12 void_actions:67 T16 pull | G13 uncountersigned v2 actions are ignored | build_report_membership
DCY-12 void_actions:2370 T16 pull | G13 uncountersigned v2 actions are ignored | build_report_membership
DCY-12 void_actions:3793 T16 pull | G13 uncountersigned v2 actions are ignored | build_report_membership
DCY-12 void_actions:3078 T16 pull | G13 uncountersigned v2 actions are ignored | build_report_membership
DCY-12 void_actions:1412 T16 pull | G13 uncountersigned v2 actions are ignored | build_report_membership
DCY-12 void_actions:3436 T16 pull | G13 uncountersigned v2 actions are ignored | build_report_membership
DCY-12 void_actions:3736 T16 pull | G13 uncountersigned v2 actions are ignored | build_report_membership
DCY-12 void_actions:3455 T16 pull | G13 uncountersigned v2 actions are ignored | build_report_membership
DOC-06 corrections:26 T8 | 3.6 restated header row inside a document table | build_report_attempt_precedence
DOC-06 corrections:974 T7 | 4.5 errata supersede exported values | build_report_attempt_precedence
DOC-06 corrections:1033 T1 | 3.1 cells are stripped of surrounding white space | build_report_attempt_precedence
DOC-06 corrections:1957 T15 | 4.5 a long corrected duration is valid | build_report_units_and_sentinels
DOC-06 corrections:2367 T13 | 4.5 corrections name build keys of legacy partitions | build_report_attempt_precedence
DOC-06 corrections:2559 T1 | 3.1 cells are stripped of surrounding white space | build_report_attempt_precedence
DOC-06 corrections:3269 T7 | 4.5 errata supersede exported values | build_report_attempt_precedence
DOC-06 corrections:3535 T7 | 4.5 errata supersede exported values | build_report_attempt_precedence
DOC-06 corrections:4080 T1 | 3.1 cells are stripped of surrounding white space | build_report_attempt_precedence
DOC-06 corrections:4565 T8 | 3.6 restated header row inside a document table | build_report_attempt_precedence
DOC-06 corrections:5041 T8 | 3.6 restated header row inside a document table | build_report_attempt_precedence
DOC-06 corrections:5076 T8 | 3.6 restated header row inside a document table | build_report_attempt_precedence
DOC-06 corrections:802 T8 | 3.6 restated header row inside a document table | build_report_attempt_precedence
DOC-06 corrections:454 T7 | 4.5 errata supersede exported values | build_report_attempt_precedence
DOC-06 corrections:1501 T7 | 4.5 errata supersede exported values | build_report_attempt_precedence
DOC-06 corrections:3853 T7 | 4.5 errata supersede exported values | build_report_attempt_precedence
DOC-06 corrections:1925 T1 | 3.1 cells are stripped of surrounding white space | build_report_attempt_precedence
DCY-02 corrections:184 T8 push | 3.6 restated header row inside a document table | build_report_attempt_precedence
DCY-02 corrections:719 T7 pull | 4.5 errata supersede exported values | build_report_attempt_precedence
DCY-02 corrections:1265 T15 pull | 4.5 a long corrected duration is valid | build_report_units_and_sentinels
DCY-02 corrections:1939 T6 push | E9 carried rows restate the approved register | build_report_attempt_precedence
DCY-02 corrections:2208 T13 pull | 4.5 corrections name build keys of legacy partitions | build_report_attempt_precedence
DCY-02 corrections:2992 T1 push | 3.1 cells are stripped of surrounding white space | build_report_attempt_precedence
DCY-02 corrections:3112 T7 pull | 4.5 errata supersede exported values | build_report_attempt_precedence
DCY-02 corrections:3633 T6 push | E9 carried rows restate the approved register | build_report_attempt_precedence
DCY-02 corrections:4460 T6 push | E9 carried rows restate the approved register | build_report_attempt_precedence
DCY-02 corrections:4868 T16 pull | E9 proposed revB rows are ignored | build_report_attempt_precedence
DCY-02 corrections:5009 T16 pull | E9 proposed revB rows are ignored | build_report_attempt_precedence
DCY-02 corrections:3139 T6 push | E9 carried rows restate the approved register | build_report_attempt_precedence
DCY-02 corrections:4111 T8 push | 3.6 restated header row inside a document table | build_report_attempt_precedence
DCY-02 corrections:4910 T16 pull | E9 proposed revB rows are ignored | build_report_attempt_precedence
DCY-02 corrections:2581 T8 push | 3.6 restated header row inside a document table | build_report_attempt_precedence
DCY-02 corrections:1703 T8 push | 3.6 restated header row inside a document table | build_report_attempt_precedence
DCY-02 corrections:3916 T6 push | E9 carried rows restate the approved register | build_report_attempt_precedence
DCY-02 corrections:3102 T6 push | E9 carried rows restate the approved register | build_report_attempt_precedence
DCY-02 corrections:1565 T8 push | 3.6 restated header row inside a document table | build_report_attempt_precedence
DCY-02 corrections:3294 T8 push | 3.6 restated header row inside a document table | build_report_attempt_precedence
DCY-02 corrections:3186 T6 push | E9 carried rows restate the approved register | build_report_attempt_precedence
DCY-02 corrections:31 T8 push | 3.6 restated header row inside a document table | build_report_attempt_precedence
DCY-02 corrections:4372 T6 push | E9 carried rows restate the approved register | build_report_attempt_precedence
DCY-02 corrections:5076 T16 pull | E9 proposed revB rows are ignored | build_report_attempt_precedence
DCY-02 corrections:540 T8 push | 3.6 restated header row inside a document table | build_report_attempt_precedence
DCY-02 corrections:1647 T7 pull | 4.5 errata supersede exported values | build_report_attempt_precedence
DCY-02 corrections:1798 T8 push | 3.6 restated header row inside a document table | build_report_attempt_precedence
DCY-02 corrections:4017 T7 pull | 4.5 errata supersede exported values | build_report_attempt_precedence
DCY-02 corrections:4855 T16 pull | E9 proposed revB rows are ignored | build_report_attempt_precedence
DCY-02 corrections:1760 T8 push | 3.6 restated header row inside a document table | build_report_attempt_precedence
DCY-02 corrections:4557 T7 pull | 4.5 errata supersede exported values | build_report_attempt_precedence
DCY-02 corrections:415 T7 pull | 4.5 errata supersede exported values | build_report_attempt_precedence
DCY-02 corrections:3505 T6 push | E9 carried rows restate the approved register | build_report_attempt_precedence
DOC-01 legacy_keys:370 T8 | 3.6 restated header row inside a document table | build_report_membership
DOC-01 legacy_keys:800 T13 | appendix F legacy key crosswalk | build_report_membership
DOC-01 legacy_keys:1112 T1 | 3.1 build key spellings | build_report_attempt_precedence
DOC-01 legacy_keys:1686 T6 | 4.7 a voided build keeps its legacy key | build_report_membership
DOC-01 legacy_keys:2236 T8 | 3.6 restated header row inside a document table | build_report_membership
DOC-01 legacy_keys:2728 T1 | 3.1 cells are stripped of surrounding white space | build_report_membership
DOC-01 legacy_keys:3393 T13 | appendix F legacy key crosswalk | build_report_membership
DOC-01 legacy_keys:3807 T13 | appendix F legacy key crosswalk | build_report_membership
DOC-01 legacy_keys:4170 T8 | 3.6 restated header row inside a document table | build_report_membership
DOC-01 legacy_keys:4584 T8 | 3.6 restated header row inside a document table | build_report_membership
DOC-01 legacy_keys:5483 T13 | appendix F legacy key crosswalk | build_report_membership
DOC-01 legacy_keys:5796 T8 | 3.6 restated header row inside a document table | build_report_membership
DOC-01 legacy_keys:6329 T13 | appendix F legacy key crosswalk | build_report_membership
DOC-01 legacy_keys:6966 T13 | appendix F legacy key crosswalk | build_report_membership
DOC-01 legacy_keys:7172 T8 | 3.6 restated header row inside a document table | build_report_membership
DOC-01 legacy_keys:7782 T13 | appendix F legacy key crosswalk | build_report_membership
DOC-01 legacy_keys:8033 T1 | 3.1 cells are stripped of surrounding white space | build_report_membership
DOC-01 legacy_keys:8631 T8 | 3.6 restated header row inside a document table | build_report_membership
DOC-01 legacy_keys:2319 T8 | 3.6 restated header row inside a document table | build_report_membership
DOC-01 legacy_keys:987 T8 | 3.6 restated header row inside a document table | build_report_membership
DCY-01 legacy_jobs:148 T8 push | 3.6 restated header row inside a document table | build_report_membership
DCY-01 legacy_jobs:768 T7 pull | 4.1 reinstated job behind a legacy code | build_report_attempt_precedence
DCY-01 legacy_jobs:1159 T13 pull | appendix D legacy job crosswalk | build_report_attempt_precedence
DCY-01 legacy_jobs:1773 T1 push | 3.1 cells are stripped of surrounding white space | build_report_membership
DCY-01 legacy_jobs:2129 T6 push | 4.1 revoked job behind a legacy code | build_report_attempt_precedence
DCY-01 legacy_jobs:2877 T8 push | 3.6 restated header row inside a document table | build_report_membership
DCY-01 legacy_jobs:3455 T8 push | 3.6 restated header row inside a document table | build_report_membership
DCY-01 legacy_jobs:3934 T8 push | 3.6 restated header row inside a document table | build_report_membership
DCY-01 legacy_jobs:4145 T8 push | 3.6 restated header row inside a document table | build_report_membership
DCY-01 legacy_jobs:4654 T8 push | 3.6 restated header row inside a document table | build_report_membership
DCY-01 legacy_jobs:5432 T7 pull | 4.1 reinstated job behind a legacy code | build_report_attempt_precedence
DCY-01 legacy_jobs:5806 T13 pull | appendix D legacy job crosswalk | build_report_attempt_precedence
DCY-01 legacy_jobs:6030 T7 pull | 4.1 reinstated job behind a legacy code | build_report_attempt_precedence
DCY-01 exporter_rank_proposed:4 T16 pull | G1 draft ranking has no force | build_report_attempt_precedence
DCY-01 legacy_jobs:175 T8 push | 3.6 restated header row inside a document table | build_report_membership
DCY-01 legacy_jobs:5126 T6 push | 4.1 revoked job behind a legacy code | build_report_attempt_precedence
DCY-01 legacy_jobs:3568 T13 pull | appendix D legacy job crosswalk | build_report_attempt_precedence
DCY-01 exporter_rank_proposed:8 T16 pull | G1 draft ranking has no force | build_report_attempt_precedence
DCY-01 legacy_jobs:2428 T13 pull | appendix D legacy job crosswalk | build_report_attempt_precedence
DCY-01 exporter_rank_proposed:5 T16 pull | G1 draft ranking has no force | build_report_attempt_precedence
DCY-01 legacy_jobs:5075 T7 pull | 4.1 reinstated job behind a legacy code | build_report_attempt_precedence
DCY-01 legacy_jobs:805 T7 pull | 4.1 reinstated job behind a legacy code | build_report_attempt_precedence
DCY-01 legacy_jobs:1960 T13 pull | appendix D legacy job crosswalk | build_report_attempt_precedence
DCY-01 exporter_rank_proposed:7 T16 pull | G1 draft ranking has no force | build_report_attempt_precedence
DCY-01 legacy_jobs:2459 T1 push | 3.1 cells are stripped of surrounding white space | build_report_membership
DCY-01 legacy_jobs:3069 T8 push | 3.6 restated header row inside a document table | build_report_membership
DCY-01 exporter_rank_proposed:6 T8 push | 3.6 restated header row inside a document table | build_report_attempt_precedence
DCY-01 legacy_jobs:1861 T8 push | 3.6 restated header row inside a document table | build_report_membership
DCY-01 exporter_rank_proposed:2 T16 pull | G1 draft ranking has no force | build_report_attempt_precedence
DCY-01 exporter_rank_proposed:1 T16 pull | G1 draft ranking has no force | build_report_attempt_precedence
DCY-01 exporter_rank_proposed:3 T16 pull | G1 draft ranking has no force | build_report_attempt_precedence
DCY-01 legacy_jobs:2565 T13 pull | appendix D legacy job crosswalk | build_report_attempt_precedence
DCY-01 legacy_jobs:1187 T8 push | 3.6 restated header row inside a document table | build_report_membership
DOC-02 exporter_rank:7 T8 | 3.6 restated header row inside a document table | build_report_attempt_precedence
DOC-02 host_pools:200 T14 | G3 lab pool excluded | build_report_time_and_scope
DOC-02 host_pools:725 T1 | 3.1 host names are case-insensitive | build_report_time_and_scope
DOC-02 host_pools:1182 T6 | G3 lab attempts are out of scope | build_report_membership
DOC-02 host_pools:1508 T14 | G3 lab pool excluded | build_report_time_and_scope
DOC-02 host_pools:2160 T1 | 3.1 host names are case-insensitive | build_report_time_and_scope
DOC-02 host_pools:2628 T14 | G3 lab pool excluded | build_report_time_and_scope
DOC-02 host_pools:3082 T14 | G3 lab pool excluded | build_report_time_and_scope
DOC-02 host_pools:3719 T1 | 3.1 cells are stripped of surrounding white space | build_report_membership
DOC-02 host_pools:4498 T13 | G5 eph pool rows of the mirror export are authoritative | build_report_membership
DOC-02 host_pools:4720 T8 | 3.6 restated header row inside a document table | build_report_membership
DOC-02 host_pools:5144 T13 | G5 eph pool rows of the mirror export are authoritative | build_report_membership
DOC-02 host_pools:5801 T13 | G5 eph pool rows of the mirror export are authoritative | build_report_membership
DOC-02 exporter_rank:8 T1 | 3.1 cells are stripped of surrounding white space | build_report_attempt_precedence
DOC-02 host_pools:3391 T1 | 3.1 host names are case-insensitive | build_report_time_and_scope
DOC-02 exporter_rank:5 T8 | 3.6 restated header row inside a document table | build_report_attempt_precedence
DOC-02 host_pools:3260 T8 | 3.6 restated header row inside a document table | build_report_membership
DOC-02 host_pools:41 T8 | 3.6 restated header row inside a document table | build_report_membership
DCY-15 branch_register:217 T16 pull | G16 the memo proposes counting release branches | build_report_membership
DCY-15 branch_register:668 T13 pull | G16 the memo carries the only branch register | build_report_time_and_scope
DCY-15 branch_register:1403 T8 push | 3.6 restated header row inside a document table | build_report_membership
DCY-15 branch_register:1919 T1 push | 3.1 cells are stripped of surrounding white space | build_report_membership
DCY-15 branch_register:2101 T16 pull | G16 the memo proposes counting release branches | build_report_membership
DCY-15 branch_register:2573 T16 pull | G16 the memo proposes counting release branches | build_report_membership
DCY-15 branch_register:3485 T16 pull | G16 the memo proposes counting release branches | build_report_membership
DCY-15 branch_register:3815 T16 pull | G16 the memo proposes counting release branches | build_report_membership
DCY-15 branch_register:4416 T16 pull | G16 the memo proposes counting release branches | build_report_membership
DCY-15 branch_register:4964 T16 pull | G16 the memo proposes counting release branches | build_report_membership
DCY-15 branch_register:5109 T16 pull | G16 the memo proposes counting release branches | build_report_membership
DCY-15 branch_register:1885 T8 push | 3.6 restated header row inside a document table | build_report_membership
DCY-15 branch_register:713 T16 pull | G16 the memo proposes counting release branches | build_report_membership
DCY-15 branch_register:2515 T16 pull | G16 the memo proposes counting release branches | build_report_membership
DCY-15 branch_register:836 T16 pull | G16 the memo proposes counting release branches | build_report_membership
DCY-15 branch_register:166 T16 pull | G16 the memo proposes counting release branches | build_report_membership
DCY-15 branch_register:3388 T16 pull | G16 the memo proposes counting release branches | build_report_membership
DCY-15 branch_register:1882 T16 pull | G16 the memo proposes counting release branches | build_report_membership
DCY-15 branch_register:2102 T16 pull | G16 the memo proposes counting release branches | build_report_membership
DCY-15 branch_register:1512 T16 pull | G16 the memo proposes counting release branches | build_report_membership
DCY-15 branch_register:4716 T16 pull | G16 the memo proposes counting release branches | build_report_membership
DCY-15 branch_register:1371 T16 pull | G16 the memo proposes counting release branches | build_report_membership
DCY-15 branch_register:1486 T16 pull | G16 the memo proposes counting release branches | build_report_membership
DCY-15 branch_register:4948 T16 pull | G16 the memo proposes counting release branches | build_report_membership
DCY-15 branch_register:4373 T8 push | 3.6 restated header row inside a document table | build_report_membership
DCY-15 branch_register:64 T16 pull | G16 the memo proposes counting release branches | build_report_membership
DCY-15 branch_register:3713 T16 pull | G16 the memo proposes counting release branches | build_report_membership
DCY-15 branch_register:2169 T16 pull | G16 the memo proposes counting release branches | build_report_membership
DCY-15 branch_register:2212 T16 pull | G16 the memo proposes counting release branches | build_report_membership
DCY-15 branch_register:3751 T16 pull | G16 the memo proposes counting release branches | build_report_membership
DCY-15 branch_register:3282 T16 pull | G16 the memo proposes counting release branches | build_report_membership
DCY-15 branch_register:3006 T16 pull | G16 the memo proposes counting release branches | build_report_membership
DCY-15 branch_register:6 T6 push | 4.2 retired branch | build_report_time_and_scope
DCY-15 branch_register:4 T7 pull | 4.2 main aliases | build_report_time_and_scope
DOC-07 job_revocations:397 T6 | 4.1 job revocation register, latest action decides | build_report_attempt_precedence
DOC-07 job_revocations:955 T8 | 3.6 restated header row inside a document table | build_report_membership
DOC-07 job_revocations:1085 T13 | 4.1 legacy partitions name this job by code | build_report_attempt_precedence
DOC-07 job_revocations:1940 T7 | 4.1 a later reinstate restores the job | build_report_attempt_precedence
DOC-07 job_revocations:2072 T8 | 3.6 restated header row inside a document table | build_report_membership
DOC-07 job_revocations:2767 T8 | 3.6 restated header row inside a document table | build_report_membership
DOC-07 job_revocations:3197 T6 | 4.1 job revocation register, latest action decides | build_report_attempt_precedence
DOC-07 job_revocations:3624 T7 | 4.1 a later reinstate restores the job | build_report_attempt_precedence
DOC-07 job_revocations:4132 T8 | 3.6 restated header row inside a document table | build_report_membership
DOC-07 job_revocations:4899 T7 | 4.1 a later reinstate restores the job | build_report_attempt_precedence
DOC-07 job_revocations:5034 T6 | 4.1 job revocation register, latest action decides | build_report_attempt_precedence
DOC-07 job_revocations:0 T10 | 3.6 byte order mark before the control block | selftest_control_chain
DOC-07 job_revocations:2850 T6 | 4.1 job revocation register, latest action decides | build_report_attempt_precedence
DOC-07 job_revocations:1359 T6 | 4.1 job revocation register, latest action decides | build_report_attempt_precedence
DOC-07 job_revocations:5125 T8 | 3.6 restated header row inside a document table | build_report_membership
DOC-07 job_revocations:988 T7 | 4.1 a later reinstate restores the job | build_report_attempt_precedence
DOC-07 job_revocations:1562 T8 | 3.6 restated header row inside a document table | build_report_membership
DOC-07 job_revocations:4946 T6 | 4.1 job revocation register, latest action decides | build_report_attempt_precedence
DOC-08 host_incidents:129 T1 | 3.1 host names are case-insensitive | build_report_time_and_scope
DOC-08 host_incidents:710 T3 | 3.4 register timestamps with an explicit offset | build_report_attempt_precedence
DOC-08 host_incidents:1101 T11 | 4.9 incident intervals are half-open | build_report_attempt_precedence
DOC-08 host_incidents:1794 T8 | 3.6 restated header row inside a document table | build_report_attempt_precedence
DOC-08 host_incidents:2432 T3 | 3.4 register timestamps with an explicit offset | build_report_attempt_precedence
DOC-08 host_incidents:2603 T8 | 3.6 restated header row inside a document table | build_report_attempt_precedence
DOC-08 host_incidents:3387 T3 | 3.4 register timestamps with an explicit offset | build_report_attempt_precedence
DOC-08 host_incidents:3648 T3 | 3.4 register timestamps with an explicit offset | build_report_attempt_precedence
DOC-08 host_incidents:4017 T8 | 3.6 restated header row inside a document table | build_report_attempt_precedence
DOC-08 host_incidents:4777 T3 | 3.4 register timestamps with an explicit offset | build_report_attempt_precedence
DOC-08 host_incidents:0 T10 | 3.6 byte order mark before the control block | selftest_control_chain
DOC-08 host_incidents:3522 T3 | 3.4 register timestamps with an explicit offset | build_report_attempt_precedence
DOC-08 host_incidents:4105 T1 | 3.1 host names are case-insensitive | build_report_time_and_scope
DOC-08 host_incidents:3486 T3 | 3.4 register timestamps with an explicit offset | build_report_attempt_precedence
DOC-08 host_incidents:1073 T3 | 3.4 register timestamps with an explicit offset | build_report_attempt_precedence
DOC-08 host_incidents:1789 T1 | 3.1 host names are case-insensitive | build_report_time_and_scope
DOC-08 host_incidents:4680 T11 | 4.9 incident intervals are half-open | build_report_attempt_precedence
DEP-01 versions:384 T1 | 3.1 cells are stripped of surrounding white space | dependency_resolution_semver
DEP-01 versions:760 T15 | 9.4 prerelease excluded unless named | dependency_resolution_semver
DEP-01 versions:1384 T3 | 3.4 register timestamps with an explicit offset | dependency_resolution_semver
DEP-01 versions:1909 T13 | 9.1 the registry may name a package by an alias spelling | dependency_resolution_semver
DEP-01 versions:2293 T3 | 3.4 register timestamps with an explicit offset | dependency_resolution_semver
DEP-01 versions:2862 T3 | 3.4 register timestamps with an explicit offset | dependency_resolution_semver
DEP-01 versions:3015 T3 | 3.4 register timestamps with an explicit offset | dependency_resolution_semver
DEP-01 versions:3973 T1 | 9.1 package names are normalised | dependency_resolution_semver
DEP-01 versions:4345 T1 | 3.1 cells are stripped of surrounding white space | dependency_resolution_semver
DEP-01 versions:4801 T3 | 3.4 register timestamps with an explicit offset | dependency_resolution_semver
DEP-01 versions:5295 T3 | 3.4 register timestamps with an explicit offset | dependency_resolution_semver
DEP-01 versions:5580 T1 | 9.1 package names are normalised | dependency_resolution_semver
DEP-01 versions:6134 T3 | 3.4 register timestamps with an explicit offset | dependency_resolution_semver
DEP-01 versions:6705 T13 | 9.1 the registry may name a package by an alias spelling | dependency_resolution_semver
DEP-01 versions:7493 T13 | 9.1 the registry may name a package by an alias spelling | dependency_resolution_semver
DEP-01 versions:7502 T1 | 3.1 cells are stripped of surrounding white space | dependency_resolution_semver
DEP-01 versions:6827 T3 | 3.4 register timestamps with an explicit offset | dependency_resolution_semver
DEP-01 versions:6400 T1 | 3.1 cells are stripped of surrounding white space | dependency_resolution_semver
DEP-01 versions:2738 T13 | 9.1 the registry may name a package by an alias spelling | dependency_resolution_semver
DEP-01 versions:1972 T3 | 3.4 register timestamps with an explicit offset | dependency_resolution_semver
DEP-01 versions:355 T11 | E8 a version published exactly at the cut (written with an offset) is available | dependency_resolution_semver
DEP-01 versions:6194 T11 | E8 a version published exactly at the cut is available | dependency_resolution_semver
DCY-07 versions:462 T3 pull | 3.4 register timestamps with an explicit offset | dependency_resolution_semver
DCY-07 versions:741 T16 pull | G14 mirror publication date differs | dependency_resolution_semver
DCY-07 versions:1192 T15 pull | 9.4 prerelease excluded unless named | dependency_resolution_semver
DCY-07 versions:1911 T1 push | 3.1 cells are stripped of surrounding white space | dependency_resolution_semver
DCY-07 versions:2107 T7 pull | G14 the registry supersedes the mirror | dependency_resolution_semver
DCY-07 versions:2868 T6 push | G14 withdrawn version listed as live | dependency_resolution_semver
DCY-07 versions:3144 T7 pull | G14 the registry supersedes the mirror | dependency_resolution_semver
DCY-07 versions:3833 T16 pull | G14 mirror publication date differs | dependency_resolution_semver
DCY-07 versions:4257 T16 pull | G14 mirror publication date differs | dependency_resolution_semver
DCY-07 versions:4740 T16 pull | G14 mirror publication date differs | dependency_resolution_semver
DCY-07 versions:5469 T16 pull | G14 mirror publication date differs | dependency_resolution_semver
DCY-07 versions:5507 T16 pull | G14 mirror publication date differs | dependency_resolution_semver
DCY-07 versions:6407 T16 pull | G14 mirror publication date differs | dependency_resolution_semver
DCY-07 versions:6645 T16 pull | G14 mirror publication date differs | dependency_resolution_semver
DCY-07 versions:7095 T3 pull | 3.4 register timestamps with an explicit offset | dependency_resolution_semver
DCY-07 versions:7539 T16 pull | G14 mirror versions are not registry versions | dependency_resolution_semver
DCY-07 withdrawn:33 T13 pull | G14 the only withdrawal record | dependency_resolution_semver
DCY-07 withdrawn:74 T6 push | G14 withdrawn versions | dependency_resolution_semver
DCY-07 versions:628 T16 pull | G14 mirror publication date differs | dependency_resolution_semver
DCY-07 versions:2246 T16 pull | G14 mirror publication date differs | dependency_resolution_semver
DCY-07 withdrawn:13 T1 push | 9.1 package names are normalised | dependency_resolution_semver
DCY-07 versions:273 T16 pull | G14 mirror publication date differs | dependency_resolution_semver
DCY-07 versions:5689 T3 pull | 3.4 register timestamps with an explicit offset | dependency_resolution_semver
DCY-07 withdrawn:68 T6 push | G14 withdrawn versions | dependency_resolution_semver
DCY-07 versions:311 T3 pull | 3.4 register timestamps with an explicit offset | dependency_resolution_semver
DCY-07 withdrawn:70 T1 push | 3.1 cells are stripped of surrounding white space | dependency_resolution_semver
DCY-07 versions:4986 T3 pull | 3.4 register timestamps with an explicit offset | dependency_resolution_semver
DCY-07 withdrawn:72 T6 push | G14 withdrawn versions | dependency_resolution_semver
DCY-07 withdrawn:35 T13 pull | G14 the only withdrawal record | dependency_resolution_semver
DCY-07 withdrawn:3 T13 pull | G14 the only withdrawal record | dependency_resolution_semver
DCY-07 withdrawn:26 T13 pull | G14 the only withdrawal record | dependency_resolution_semver
DEP-02 advisory:494 T3 | 3.4 register timestamps with an explicit offset | dependency_resolution_semver
DEP-02 advisory:530 T15 | 9.4 advisories on prereleases | dependency_resolution_semver
DEP-02 advisory:1183 T7 | 9.3 latest advisory action decides | dependency_resolution_semver
DEP-02 advisory:1750 T11 | 9.3 actions after the cut have no force | dependency_resolution_semver
DEP-02 advisory:2107 T1 | 9.1 package names are normalised | dependency_resolution_semver
DEP-02 advisory:2891 T7 | 9.3 latest advisory action decides | dependency_resolution_semver
DEP-02 advisory:3369 T3 | 3.4 register timestamps with an explicit offset | dependency_resolution_semver
DEP-02 advisory:3566 T7 | 9.3 latest advisory action decides | dependency_resolution_semver
DEP-02 advisory:4305 T7 | 9.3 latest advisory action decides | dependency_resolution_semver
DEP-02 advisory:4511 T15 | 9.4 advisories on prereleases | dependency_resolution_semver
DEP-02 advisory:5038 T3 | 3.4 register timestamps with an explicit offset | dependency_resolution_semver
DEP-02 advisory:2562 T3 | 3.4 register timestamps with an explicit offset | dependency_resolution_semver
DEP-02 advisory:4870 T3 | 3.4 register timestamps with an explicit offset | dependency_resolution_semver
DEP-02 advisory:4578 T7 | 9.3 latest advisory action decides | dependency_resolution_semver
DEP-02 advisory:4595 T3 | 3.4 register timestamps with an explicit offset | dependency_resolution_semver
DEP-02 advisory:1837 T15 | 9.4 advisories on prereleases | dependency_resolution_semver
DEP-02 advisory:1782 T1 | 9.1 package names are normalised | dependency_resolution_semver
DEP-02 advisory:631 T15 | 9.4 advisories on prereleases | dependency_resolution_semver
DEP-02 advisory:821 T3 | 3.4 register timestamps with an explicit offset | dependency_resolution_semver
DEP-02 advisory:3561 T7 | 9.3 latest advisory action decides | dependency_resolution_semver
DEP-03 audit_actions:45 T15 | 9.4 advisories on prereleases | dependency_resolution_semver
DEP-03 audit_actions:839 T3 | 3.4 register timestamps with an explicit offset | dependency_resolution_semver
DEP-03 audit_actions:1184 T1 | 9.1 package names are normalised | dependency_resolution_semver
DEP-03 audit_actions:1557 T8 | 3.6 restated header row inside a document table | dependency_resolution_semver
DEP-03 audit_actions:2037 T7 | 9.3 latest advisory action decides | dependency_resolution_semver
DEP-03 audit_actions:2647 T3 | 3.4 register timestamps with an explicit offset | dependency_resolution_semver
DEP-03 audit_actions:3374 T11 | 9.3 actions after the cut have no force | dependency_resolution_semver
DEP-03 audit_actions:3630 T3 | 3.4 register timestamps with an explicit offset | dependency_resolution_semver
DEP-03 audit_actions:4407 T1 | 9.1 package names are normalised | dependency_resolution_semver
DEP-03 audit_actions:4751 T3 | 3.4 register timestamps with an explicit offset | dependency_resolution_semver
DEP-03 audit_actions:5004 T3 | 3.4 register timestamps with an explicit offset | dependency_resolution_semver
DEP-03 audit_actions:2088 T8 | 3.6 restated header row inside a document table | dependency_resolution_semver
DEP-03 audit_actions:1035 T3 | 3.4 register timestamps with an explicit offset | dependency_resolution_semver
DEP-03 audit_actions:3973 T3 | 3.4 register timestamps with an explicit offset | dependency_resolution_semver
DEP-03 audit_actions:4045 T7 | 9.3 latest advisory action decides | dependency_resolution_semver
DEP-03 audit_actions:4934 T8 | 3.6 restated header row inside a document table | dependency_resolution_semver
DEP-03 audit_actions:2085 T3 | 3.4 register timestamps with an explicit offset | dependency_resolution_semver
DEP-03 audit_actions:2601 T3 | 3.4 register timestamps with an explicit offset | dependency_resolution_semver
DEP-04 requirements:381 T1 | 9.1 package alias normalised | dependency_resolution_constraints
DEP-04 requirements:512 T13 | 9.5 a frozen module resolves through its lock | dependency_resolution_semver
DEP-04 requirements:1275 T15 | 9.4 a constraint naming a prerelease admits that prerelease | dependency_resolution_semver
DEP-04 requirements:1803 T1 | 9.1 package names are normalised | dependency_resolution_semver
DEP-04 requirements:2369 T1 | 9.1 package alias normalised | dependency_resolution_constraints
DEP-04 requirements:2500 T1 | 9.1 package alias normalised | dependency_resolution_constraints
DEP-04 requirements:3450 T1 | 9.1 package alias normalised | dependency_resolution_constraints
DEP-04 requirements:3796 T1 | 9.1 package names are normalised | dependency_resolution_semver
DEP-04 requirements:4199 T13 | 9.5 a frozen module resolves through its lock | dependency_resolution_semver
DEP-04 requirements:4719 T1 | 9.1 package alias normalised | dependency_resolution_constraints
DEP-04 amendments:317 T7 | 9.2 latest amendment at or before the cut | dependency_resolution_constraints
DEP-04 amendments:586 T3 | 3.4 register timestamps with an explicit offset | dependency_resolution_constraints
DEP-04 amendments:1435 T11 | 9.2 amendment after the cut has no force | dependency_resolution_constraints
DEP-04 amendments:1568 T3 | 3.4 register timestamps with an explicit offset | dependency_resolution_constraints
DEP-04 amendments:2346 T7 | 9.2 latest amendment at or before the cut | dependency_resolution_constraints
DEP-04 amendments:2707 T7 | 9.2 latest amendment at or before the cut | dependency_resolution_constraints
DEP-04 amendments:3467 T7 | 9.2 latest amendment at or before the cut | dependency_resolution_constraints
DEP-04 amendments:3519 T7 | 9.2 latest amendment at or before the cut | dependency_resolution_constraints
DEP-04 amendments:4142 T7 | 9.2 latest amendment at or before the cut | dependency_resolution_constraints
DEP-04 amendments:4590 T3 | 3.4 register timestamps with an explicit offset | dependency_resolution_constraints
DEP-05 override:428 T3 | 3.4 register timestamps with an explicit offset | dependency_resolution_semver
DEP-05 override:578 T11 | 9.5 override expiring at the cut is not in force | dependency_resolution_semver
DEP-05 override:1174 T5 | 9.5 pin none means no override | dependency_resolution_semver
DEP-05 override:1553 T1 | 9.1 package names are normalised | dependency_resolution_semver
DEP-05 override:2369 T5 | 9.5 pin none means no override | dependency_resolution_semver
DEP-05 override:2522 T3 | 3.4 register timestamps with an explicit offset | dependency_resolution_semver
DEP-05 override:3281 T3 | 3.4 register timestamps with an explicit offset | dependency_resolution_semver
DEP-05 override:3523 T14 | 9.5 area * applies only where the area has no override | dependency_resolution_semver
DEP-05 override:4466 T5 | 9.5 pin none means no override | dependency_resolution_semver
DEP-05 override:4576 T5 | 9.5 pin none means no override | dependency_resolution_semver
DEP-05 override:5092 T3 | 3.4 register timestamps with an explicit offset | dependency_resolution_semver
DEP-05 override:365 T5 | 9.5 pin none means no override | dependency_resolution_semver
DEP-05 override:4718 T14 | 9.5 area * applies only where the area has no override | dependency_resolution_semver
DEP-05 override:5095 T3 | 3.4 register timestamps with an explicit offset | dependency_resolution_semver
DEP-05 override:1932 T11 | 9.5 override expiring at the cut is not in force | dependency_resolution_semver
DEP-05 override:711 T5 | 9.5 pin none means no override | dependency_resolution_semver
DEP-06 pins:282 T6 | 9.5 pins of unfrozen modules are dead entries | dependency_resolution_semver
DEP-06 pins:666 T1 | 9.1 package names are normalised | dependency_resolution_semver
DEP-06 pins:1488 T7 | 9.5 a frozen pin wins over a newer satisfying version | dependency_resolution_semver
DEP-06 pins:1632 T15 | 9.5 lock used only for frozen modules | dependency_resolution_semver
DEP-06 pins:2407 T13 | G15 pins: snapshot defers to the snapshot file | dependency_resolution_semver
DEP-06 pins:2968 T15 | 9.5 lock used only for frozen modules | dependency_resolution_semver
DEP-06 pins:3375 T6 | 9.5 pins of unfrozen modules are dead entries | dependency_resolution_semver
DEP-06 pins:3645 T6 | 9.5 pins of unfrozen modules are dead entries | dependency_resolution_semver
DEP-06 pins:4074 T6 | 9.5 pins of unfrozen modules are dead entries | dependency_resolution_semver
DEP-06 pins:4835 T6 | 9.5 pins of unfrozen modules are dead entries | dependency_resolution_semver
DEP-06 pins:851 T6 | 9.5 pins of unfrozen modules are dead entries | dependency_resolution_semver
DEP-06 pins:3297 T1 | 3.1 cells are stripped of surrounding white space | dependency_resolution_semver
DEP-06 pins:2045 T15 | 9.5 lock used only for frozen modules | dependency_resolution_semver
DEP-06 pins:4656 T6 | 9.5 pins of unfrozen modules are dead entries | dependency_resolution_semver
DEP-06 pins:907 T15 | 9.5 lock used only for frozen modules | dependency_resolution_semver
DEP-06 pins:3565 T6 | 9.5 pins of unfrozen modules are dead entries | dependency_resolution_semver
DEP-06 pins:2974 T15 | 9.5 lock used only for frozen modules | dependency_resolution_semver
DEP-06 pins:942 T15 | 9.5 lock used only for frozen modules | dependency_resolution_semver
DEP-06 pins:2067 T7 | 9.5 a frozen pin wins over a newer satisfying version | dependency_resolution_semver
DCY-14 snapshot_pin:464 T16 pull | G15 snapshot ignored for other modules | dependency_resolution_semver
DCY-14 snapshot_pin:579 T1 push | 9.1 package names are normalised | dependency_resolution_semver
DCY-14 snapshot_pin:1324 T6 push | 9.5 pins of unfrozen modules are not used | dependency_resolution_semver
DCY-14 snapshot_pin:1634 T7 pull | G15 lockpins.yaml supersedes the snapshot | dependency_resolution_semver
DCY-14 snapshot_pin:2442 T15 pull | 9.4 a prerelease pin is still a valid lock | dependency_resolution_semver
DCY-14 snapshot_pin:2691 T13 pull | G15 snapshot pins of snapshot modules | dependency_resolution_semver
DCY-14 snapshot_pin:3338 T16 pull | G15 snapshot ignored for other modules | dependency_resolution_semver
DCY-14 snapshot_pin:3852 T16 pull | G15 snapshot ignored for other modules | dependency_resolution_semver
DCY-14 snapshot_pin:4194 T16 pull | G15 snapshot ignored for other modules | dependency_resolution_semver
DCY-14 snapshot_pin:4958 T16 pull | G15 snapshot ignored for other modules | dependency_resolution_semver
DCY-14 snapshot_pin:4158 T16 pull | G15 snapshot ignored for other modules | dependency_resolution_semver
DCY-14 snapshot_pin:4373 T16 pull | G15 snapshot ignored for other modules | dependency_resolution_semver
DCY-14 snapshot_pin:4426 T16 pull | G15 snapshot ignored for other modules | dependency_resolution_semver
DCY-14 snapshot_pin:1013 T16 pull | G15 snapshot ignored for other modules | dependency_resolution_semver
DCY-14 snapshot_pin:1184 T16 pull | G15 snapshot ignored for other modules | dependency_resolution_semver
DCY-14 snapshot_pin:4429 T16 pull | G15 snapshot ignored for other modules | dependency_resolution_semver
DCY-14 snapshot_pin:1106 T16 pull | G15 snapshot ignored for other modules | dependency_resolution_semver
DCY-14 snapshot_pin:1767 T16 pull | G15 snapshot ignored for other modules | dependency_resolution_semver
DCY-14 snapshot_pin:4649 T16 pull | G15 snapshot ignored for other modules | dependency_resolution_semver
DCY-14 snapshot_pin:4965 T16 pull | G15 snapshot ignored for other modules | dependency_resolution_semver
DCY-14 snapshot_pin:3948 T16 pull | G15 snapshot ignored for other modules | dependency_resolution_semver
DCY-14 snapshot_pin:1476 T16 pull | G15 snapshot ignored for other modules | dependency_resolution_semver
DCY-14 snapshot_pin:824 T16 pull | G15 snapshot ignored for other modules | dependency_resolution_semver
DCY-14 snapshot_pin:1576 T16 pull | G15 snapshot ignored for other modules | dependency_resolution_semver
DCY-14 snapshot_pin:2396 T16 pull | G15 snapshot ignored for other modules | dependency_resolution_semver
DCY-14 snapshot_pin:4152 T16 pull | G15 snapshot ignored for other modules | dependency_resolution_semver
DCY-14 snapshot_pin:744 T16 pull | G15 snapshot ignored for other modules | dependency_resolution_semver
DCY-14 snapshot_pin:3127 T16 pull | G15 snapshot ignored for other modules | dependency_resolution_semver
DCY-14 snapshot_pin:1465 T16 pull | G15 snapshot ignored for other modules | dependency_resolution_semver
DCY-14 snapshot_pin:4515 T16 pull | G15 snapshot ignored for other modules | dependency_resolution_semver
DCY-14 snapshot_pin:484 T16 pull | G15 snapshot ignored for other modules | dependency_resolution_semver
DCY-14 snapshot_pin:2015 T16 pull | G15 snapshot ignored for other modules | dependency_resolution_semver
DCY-14 snapshot_pin:3588 T16 pull | G15 snapshot ignored for other modules | dependency_resolution_semver
DCY-14 snapshot_pin:3228 T16 pull | G15 snapshot ignored for other modules | dependency_resolution_semver
DOC-04 package_aliases:323 T1 | 3.1 cells are stripped of surrounding white space | dependency_resolution_constraints
DOC-04 package_aliases:799 T8 | 3.6 restated header row inside a document table | dependency_resolution_constraints
DOC-04 package_aliases:1340 T13 | 9.1 upper case aliases normalise to the package | dependency_resolution_constraints
DOC-04 package_aliases:1576 T7 | 9.1 a retired spelling still maps to the package | dependency_resolution_constraints
DOC-04 package_aliases:2366 T1 | 9.1 normalised name looked up in the alias register | dependency_resolution_semver
DOC-04 package_aliases:2522 T8 | 3.6 restated header row inside a document table | dependency_resolution_constraints
DOC-04 package_aliases:3347 T13 | 9.1 upper case aliases normalise to the package | dependency_resolution_constraints
DOC-04 package_aliases:3518 T1 | 3.1 cells are stripped of surrounding white space | dependency_resolution_constraints
DOC-04 package_aliases:4371 T8 | 3.6 restated header row inside a document table | dependency_resolution_constraints
DOC-04 package_aliases:4684 T8 | 3.6 restated header row inside a document table | dependency_resolution_constraints
DOC-04 package_aliases:5267 T8 | 3.6 restated header row inside a document table | dependency_resolution_constraints
DOC-04 package_aliases:5601 T8 | 3.6 restated header row inside a document table | dependency_resolution_constraints
DOC-04 package_aliases:2751 T8 | 3.6 restated header row inside a document table | dependency_resolution_constraints
DOC-04 package_aliases:4419 T7 | 9.1 a retired spelling still maps to the package | dependency_resolution_constraints
DOC-04 package_aliases:1823 T13 | 9.1 upper case aliases normalise to the package | dependency_resolution_constraints
DOC-04 package_aliases:2952 T7 | 9.1 a retired spelling still maps to the package | dependency_resolution_constraints
DOC-04 package_aliases:5090 T1 | 9.1 normalised name looked up in the alias register | dependency_resolution_semver
DOC-04 package_aliases:2246 T8 | 3.6 restated header row inside a document table | dependency_resolution_constraints
DOC-04 package_aliases:4223 T8 | 3.6 restated header row inside a document table | dependency_resolution_constraints
OPN-01 seen_build_keys:0 T7 | 4.7 a build re-exported from stage 0 is excluded | build_report_membership
OPN-01 seen_build_keys:687 T13 | 4.7 a stage-0 key named by a void register stays excluded | build_report_membership
OPN-01 seen_build_keys:1000 T7 | 4.7 a build re-exported from stage 0 is excluded | build_report_membership
OPN-01 seen_build_keys:1537 T13 | 4.7 a stage-0 key named by a void register stays excluded | build_report_membership
OPN-01 seen_build_keys:2000 T7 | 4.7 a build re-exported from stage 0 is excluded | build_report_membership
OPN-01 seen_build_keys:2502 T13 | 4.7 a stage-0 key named by a void register stays excluded | build_report_membership
OPN-01 seen_build_keys:3000 T7 | 4.7 a build re-exported from stage 0 is excluded | build_report_membership
OPN-01 seen_build_keys:3559 T13 | 4.7 a stage-0 key named by a void register stays excluded | build_report_membership
OPN-01 seen_build_keys:4000 T7 | 4.7 a build re-exported from stage 0 is excluded | build_report_membership
OPN-01 seen_build_keys:4519 T13 | 4.7 a stage-0 key named by a void register stays excluded | build_report_membership
OPN-01 seen_build_keys:5000 T7 | 4.7 a build re-exported from stage 0 is excluded | build_report_membership
OPN-01 seen_build_keys:5659 T13 | 4.7 a stage-0 key named by a void register stays excluded | build_report_membership
OPN-01 seen_build_keys:6000 T7 | 4.7 a build re-exported from stage 0 is excluded | build_report_membership
OPN-01 seen_build_keys:6609 T13 | 4.7 a stage-0 key named by a void register stays excluded | build_report_membership
OPN-01 seen_build_keys:7000 T7 | 4.7 a build re-exported from stage 0 is excluded | build_report_membership
OPN-01 seen_build_keys:7529 T13 | 4.7 a stage-0 key named by a void register stays excluded | build_report_membership
OPN-01 seen_build_keys:8000 T7 | 4.7 a build re-exported from stage 0 is excluded | build_report_membership
OPN-01 seen_build_keys:8542 T13 | 4.7 a stage-0 key named by a void register stays excluded | build_report_membership
OPN-01 last_good:69 T6 | 10.7 last_good of a decommissioned module is still carried | summary_last_good
OPN-01 open_flaky:0 T15 | 5.3 carried flaky tests stay flaky without new evidence | module_metrics_flaky_and_quarantine
IDX-01 files:0 T7 | 2.4 chain order is chain_pos, not listing order | selftest_control_chain
IDX-01 jobs:401 T7 | 4.1 a reinstated job counts again | build_report_attempt_precedence
IDX-01 jobs:1151 T6 | 4.1 job revocation register decides | build_report_attempt_precedence
IDX-01 jobs:1651 T6 | 4.1 job revocation register decides | build_report_attempt_precedence
IDX-01 jobs:1912 T6 | 4.1 rows of a revoked job are void | build_report_attempt_precedence
IDX-01 jobs:2402 T7 | 4.1 a reinstated job counts again | build_report_attempt_precedence
IDX-01 jobs:3151 T6 | 4.1 job revocation register decides | build_report_attempt_precedence
IDX-01 jobs:3651 T6 | 4.1 job revocation register decides | build_report_attempt_precedence
IDX-01 jobs:4046 T6 | 4.1 rows of a revoked job are void | build_report_attempt_precedence
IDX-01 jobs:4401 T7 | 4.1 a reinstated job counts again | build_report_attempt_precedence
IDX-01 jobs:4901 T13 | 4.1 legacy job codes reach this exporter through appendix D | build_report_attempt_precedence
IDX-01 jobs:5600 T11 | G2 lowest exporter rank loses every tie | build_report_attempt_precedence
IDX-01 jobs:5902 T6 | 4.1 rows of a revoked job are void | build_report_attempt_precedence
IDX-01 control:0 T14 | 2.1 the index is found by its control block role, not by file name | stage2_selftest
PRJ-01 fixtures:1 T15 | 9.4 prerelease versions satisfy only ranges naming a prerelease | package_shipped_tests_pass
PRJ-01 fixtures:504 T7 | E3 caret on zero versions supersedes the textbook range | dependency_resolution_semver
PRJ-01 fixtures:1007 T11 | 9.4 tilde upper bound is exclusive | dependency_resolution_semver
PRJ-01 fixtures:1501 T15 | 9.4 prerelease versions satisfy only ranges naming a prerelease | package_shipped_tests_pass
PRJ-01 fixtures:2004 T7 | E3 caret on zero versions supersedes the textbook range | dependency_resolution_semver
PRJ-01 fixtures:2501 T11 | 9.4 tilde upper bound is exclusive | dependency_resolution_semver
PRJ-01 fixtures:3002 T15 | 9.4 prerelease versions satisfy only ranges naming a prerelease | package_shipped_tests_pass
PRJ-01 fixtures:3500 T7 | E3 caret on zero versions supersedes the textbook range | dependency_resolution_semver
PRJ-01 fixtures:4024 T11 | 9.4 tilde upper bound is exclusive | dependency_resolution_semver
PRJ-01 fixtures:4503 T15 | 9.4 prerelease versions satisfy only ranges naming a prerelease | package_shipped_tests_pass
PRJ-01 source:0 T13 | pyproject package-dir names a missing lib/ tree | package_installs_and_imports
PRJ-01 source:0 T11 | requires-python >=3.13 excludes the 3.12 runtime | package_installs_and_imports
PRJ-01 source:0 T9 | unclosed tuple literal in ledger.py | package_installs_and_imports
PRJ-01 source:0 T14 | README says stdlib plus declared dependencies; readers import tomli | package_installs_and_imports
PRJ-01 source:0 T13 | circular import conventions -> feed -> readers | package_installs_and_imports
PRJ-01 source:0 T5 | pypdf missing from the declared dependencies | package_installs_and_imports
```

## Provenance

```yaml
uuid: 6defadfe-9c50-5aa1-b854-8d5c1718d794
instance_id: 6defadfe-9c50-5aa1-b854-8d5c1718d794
task_name: terminal-bench/6defadfe-9c50-5aa1-b854-8d5c1718d794
fix_patch_sha256: 6191555bd542576e2fe7888868015559e30daf9309a88d5e5404fbcbc6f98b99
solve_py_sha256: 3ef2203ec49981c579053d34200fab32727bd3db91305976315c44cffbf2c6f9
language: python
positive_weight_total: 56
negative_weight_total: -8
judge_positive_weight_total: 53
judge_negative_weight_total: -17
measured_oracle_tests_only: 1.0
measured_oracle_tests_only_runs: 2
measured_nop_tests_only: 0.0
measured_stub_tests_only: 0.0
measured_owner_only_tests_only: 1.0
```
