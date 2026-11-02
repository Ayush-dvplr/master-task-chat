# TRUTH.md - 66b1a1e2-7d80-50ad-9c7c-bc71d5f64c24

Verifier side material, never copied into the agent image.

## Defect

The 2027 executive operations calendar store under `/app/data` cannot be
reconciled by reading any one file. It is a two-replica CalDAV store spread over
twenty-five data files with opaque names (`relay-6a86.json`, `mesh-4527.xlsx`,
`trace-1b79.pdf`, and so on) plus twenty seven specification documents. The
retired v3 scheduler left behind a per series count file and a transition
cache, and several lower-authority copies of the controlling figures disagree
with their authorities. The agent has to rebuild the reconciliation program,
`/app/schedule_repair.py`, so that it produces twenty-five exact reports for the
shipped store and for stores it has never seen.

What is wrong, concretely, in the shipped store:

- The store index is not named as such. It is the one JSON file whose `format`
  is `exec-ops-store/2` (`relay-6a86.json` in the shipped store). Every other
  file is reached only through its `files` map. Another JSON file
  (`node-3002.json`, the zone alias table) and the previous run file
  (`trace-e0d9.json`) carry other formats.
- The six replica files use three encodings, decided by the first non blank
  octet: `cal-alpha` is iCalendar locally and xCal on the server, `cal-beta` is
  jCal locally and iCalendar on the server, `cal-gamma` is iCalendar locally and
  jCal on the server. A program that only parses iCalendar text loses two
  thirds of the store.
- The settling parameters, class ranks and office conversion rates exist only
  in the governance PDF. Its pages are Flate compressed, its text runs are
  drawn out of order, and strings appear as literal strings with octal
  escapes, hexadecimal strings and `TJ` arrays. Tables continue across pages
  with a `(continued)` caption and a repeated header.
- The revision register in that PDF approves revisions 3, 4 and 6, withdraws 5
  and 8, and lists 7 as a draft. The store declares `policy_revision` 7, so the
  effective revision is min(7, 6) = 6. The revision 6 settling row is buffer
  40, quantum 30, round cap 288, pin rank 85, default rank 12. The YAML
  escalation draft (`parcel-d864.yml`) circulates buffer 45, quantum 30, round
  cap 96, pin rank 90, default rank 10, which is the revision 3 row; four of
  its five settling values differ from the figures in force.
- Class ranks and conversion rates fall back revision by revision. A class with
  rows at revisions 3, 4 and 5 takes its revision 4 rank because 5 is
  withdrawn. A reader that takes the last row in the table, or the row of the
  declared policy revision 7, reads rows of withdrawn revision 8 or draft
  revision 7 that are never in force.
- The office register is an XLSX workbook with `date1904="1"`, six sheets whose
  part files are shuffled against their relationship ids (sheet "Register R7"
  is `rId7` and lives in `worksheets/sheet2.xml`), two sheets that both claim
  edition R7, a draft R8 sheet and a rates proposal sheet. The sheet in force
  is chosen by cells A1, B1 and B2, never by the sheet name. Numeric columns mix
  number cells and text cells, and text cells may carry comma thousands
  separators.
- The outbox (`store-82e3.psv`) holds 229 queued operations for the store's
  collections, in shuffled file order, with escaped pipes inside values. Replayed
  in `op_seq` order with the base sequence check, 176 apply, 46 are rejected
  as `stale-base` and 7 as `missing`. A program that applies every operation,
  or applies them in file order, changes the server replica that the merge
  reads and so moves the merge decisions.
- The change log is split into a current shard (`relay-502c.ndjson`) and a
  legacy shard (`stack-f51f.jsonl`) with different field names (`rev`, `cal`,
  `side` `L`/`S`, `object`, extended `rid` or `null`, `PUT`/`DEL`). Where the
  same identity appears in both, the current shard wins even when the legacy
  record disagrees about deletion.
- The shipped store declares the `mtime-major` ladder with `exact` duration
  semantics and the server as authority replica. Of 1356 merge keys, 874 are
  held by one replica, 478 are contested (477 decided on modification time and
  1 on the change log revision) and 4 are tombstoned by a delete from the other
  replica, which leaves 1352 merged components. The held out stores use
  `sequence-major` and `nominal`, so hard wiring the shipped ladder fails.
- Participants are named through handles. The comma separated handle table
  (`spool-a9d1.csv`) holds weekly duty rotas, time gated delegations, a
  `chief-of-staff` link whose tie on 2027-06-16 is broken by the smaller
  target, a `board-clerk`/`clerk-backup` cycle from 2027-07-01, a self link,
  and retired rows. Over the shipped store 9413 references resolve: 8578
  directly, 780 through links, 47 on a cycle and 8 to nobody.
- Exclusions and overrides do real work: 317 exclusion dates apply, 102 match
  nothing, 220 overrides apply, 88 are rejected (orphan, missing master or
  superseded) and 88 occurrences carry a non zero inherited shift from ranged
  overrides. Amendment A3 makes a ranged override hand forward its office,
  summary, attendee references, class and duration as well as its
  displacement.
- The settling loop does not converge on the shipped store. It runs the full
  288 round cap of revision 6 and stops with reason `cap`, leaving residual
  conflicts. A program that uses the draft round cap of 96 stops a third of the
  way through.
- The lower-authority copies disagree with their authorities in 318 of 543
  audit rows: every one of the 240 payroll rates, 37 class ranks, 26 conversion
  rates, 4 settling parameters, 5 office longitudes, 1 office window and 5 zone
  transition lists of the v3 cache. A program that reads any of them for a
  computation produces wrong downstream reports. The audit names each lower
  source by its role name (`escalation_draft`, `office_snapshot`,
  `payroll_export`, `zone_cache`).
- The Zurich desk (ZRH) is booked only by ATT-152: once for two hours from
  `cal-alpha` and twice for one hour from `cal-beta`. The two collections carry
  equal base cents (10054 each) while the converted total is odd (15505 at 7711
  basis points), so the allocation leaves one cent on an exact tie that the
  smaller collection id wins: 7753 to `cal-alpha`, 7752 to `cal-beta`. Every
  store that grades the allocation carries this tie.
- The previous run file lists v3 occurrence counts per series under
  `series_summary`; the drift report has 1050 rows. The v3 figure is the rule
  `COUNT` as the retired scheduler printed it, which ignores exclusions, RDATE
  candidates, cancellations, tombstones and the store window, so many differ
  from the v5 counts. Copying the v3 counts into the drift report is wrong.

The reference run over the shipped store gives 3249 occurrences, 288 settling
rounds, stop reason `cap`, and manifest chain head
`a8c7468dc0eaa4fd803926f100b23e440c98f7d606f8c1e37216176d5b2d9237`.

## Load-bearing work

The stages consume one another in the order fixed by `store-overview.md`. Each
one is load bearing for at least one graded report, and the spine (merge
decisions, occurrence list, settled schedule) is load bearing for all of them.

1. Locate the index by content and read the `files` map. Graded on every held
   out store, since each uses other file names.
2. Decode the three replica encodings into one property model, with raw
   `RECURRENCE-ID` values brought to basic form and xCal/jCal text values left
   unescaped. Graded through `decisions.jsonl` and everything after it; the
   encoding shift store re-encodes the challenge store and must give identical
   bytes.
3. Read the governance PDF: inflate each page stream, collect text runs with
   their `Tm` positions, decode literal, hex and `TJ` strings, group by y,
   order by x, drop footers, follow continued tables. Fix the effective
   revision and read every figure from the greatest usable revision that has a
   row for it. Graded through `conflicts.jsonl` (buffer), `settle_moves.csv`
   and `settle_summary.json` (quantum, cap, pin rank, default rank, class
   ranks), `chargeback_offices.json` (basis points) and the revision shift store
   whose effective revision is 4.
4. Read the XLSX register: resolve sheets through the relationship part, pick
   the sheet in force by A1/B1/B2 against `register_edition`, read shared and
   inline strings, read mixed number/text cells with thousands separators, and
   convert serial dates on the 1904 or 1900 epoch as `workbookPr` says. Graded
   through attendance (windows, working days), the load fold (solar windows,
   longitudes read exactly), nominal durations (office zones) and the
   chargeback (rates). The eval store uses edition R4 and the dense store R9.
   The eval register is written on the 1900 epoch (no `date1904`); every other
   store uses 1904, so either hard-coded epoch fails somewhere.
5. Read the zone file and the zone alias table: merge every onset of every
   observance (RRULE including ordinal BYDAY, BYMONTHDAY with BYDAY, BYYEARDAY,
   BYWEEKNO, UNTIL inclusive in UTC, RDATE), and resolve wall clock values with
   the candidate test, the earlier instant for an ambiguous value and the gap
   shift for a nonexistent one. Graded directly through
   `zone_transitions.tsv`, which lists each zone's whole merged history up to
   the window end, and `resolutions.tsv`, and indirectly through every instant
   in every report.
6. Replay the outbox into the server replica in `op_seq` order with the base
   sequence check, stamping `LAST-MODIFIED`. Graded through
   `outbox_replay.jsonl`, then the merge on `mtime-major` stores.
7. Merge with the ladder the store names, consulting the union of the two
   journal shards for revision numbers and tombstones, and mark shadows of a
   UID held by a later collection. Graded through `decisions.jsonl` and
   `reconciliation.json`.
8. Expand recurrences (all four frequencies and every supported part,
   BYSETPOS over the whole period list, COUNT before exclusions), add RDATE
   candidates, apply exclusions, match and arbitrate overrides, apply ranged
   overrides with composed displacements and the A3 hand forward, compute
   durations under the store semantics, and resolve participant handles on the
   original instant's UTC date. Graded through `occurrences.csv`,
   `exceptions.jsonl`, `alias_resolutions.tsv` and `resolutions.tsv`.
9. Detect conflicts with the travel buffer applied to the earlier end across
   offices only, then settle: recompute, stop on clear, cap or all pinned,
   select the earliest pair with a movable member, defer by the quantum on the
   wall clock of the deferred occurrence's office with the A5 overrun rule.
   Graded through `conflicts.jsonl`, `settle_moves.csv`,
   `settled_schedule.csv` and `settle_summary.json`.
10. Derive the rest: the load fold before settling (A1 decay, effective office
    from legs, solar minute from exact longitude), attendance after settling
    (A2/A4 closure and non working day rules, closure revisions), legs and
    travel blocks (date line crossing, cancelled legs), busy conflicts over
    coalesced non FREE periods, the staged chargeback (A6 half even at stage 1,
    half up at stage 2) with a largest remainder allocation, the
    synchronisation projection with entity tags, revisions and tokens, the
    authority audit, the drift report and the manifest chain.

## Verification

### Channel A, deterministic checks (tests/test_output.py)

The verifier image holds the store generator. At grading time it writes seven
stores into scratch space, runs the delivered program over each as an
unprivileged user, and compares the SHA-256 digest of every report with the
digests the reference produced at build time. The stores are:

| Store | What differs from the shipped store |
|---|---|
| shipped | the store the agent saw, to check `/app/out` and the delivered program |
| challenge | `sequence-major`, `nominal`, local authority, revision 6, other encodings and names |
| eval | revision 8 declared, edition R4 register, rotations on, the loop hits the cap |
| dense | revision 9, edition R9, the largest held out store, stops on pinned pairs |
| mtime | the challenge content under the `mtime-major` ladder |
| revshift | the challenge content with `policy_revision` 4, so revision 4 figures apply |
| probe | content line, boundary and override probes in one iCalendar collection, including folds inside multi octet characters |

Two further stores are equality checks rather than digest lists: `encshift`
re-encodes every replica of the challenge store under new file names and must
reproduce the challenge digests, and `renamed` renames every file of the
shipped store and must reproduce the shipped digests. A `mutant` store is used
only by the negative that places a decoy at `/app/data`.

The full core gate: every exact check on a store first requires that
`decisions.jsonl`, `occurrences.csv` and `settled_schedule.csv` are exact on
that same store, as the instruction states ("no other report of a store counts
as correct unless those three are exact for the same store"). The delivered
check reads the delivered `/app/out` spine; the held out checks read the spine
of their own run and nothing else, so a stale `/app/out` costs only the checks
that read `/app/out`.

There are 43 positive checks with a positive total of 139:

- 4 contract checks of weight 1: the program writes every report into an
  output directory that does not exist before the run (on the probe store); the
  delivered reports follow the serialisation contract (single line feeds,
  canonical JSON and JSON lines, table rows with as many fields as the header);
  the delivered manifest chain recomputes from the files beside it; table
  reports written for the challenge store carry the documented header rows.
- 9 heavy checks of weight 5: the delivered shipped reports are exact; the core
  spine is exact on challenge, eval, dense, mtime, probe and revshift; the
  encoding shift reproduces challenge; every report is exact on dense.
- 30 per artifact checks of weight 3 spread over the held out stores: outbox
  replay (challenge, eval), attendee resolutions (eval, revshift), candidate
  resolutions and zone transitions (eval, probe), exceptions (challenge,
  probe), conflicts (challenge, mtime), settling trace (eval, challenge,
  mtime), load fold (eval, revshift), attendance (challenge, probe), travel
  (challenge, eval), busy conflicts (eval, challenge), sync state (challenge,
  eval), chargeback rollup (challenge, revshift), collection allocation (eval),
  authority audit (challenge, eval) and drift (eval, challenge). No report is
  graded twice on one store.

Three positive checks read `/app/out`: the delivered shipped check (weight 5)
and two contract checks of weight 1 (the serialisation contract and the
manifest chain). The other 132 of 139 positive weight, 95.0 percent, is earned
by re-executing the program on stores the agent never saw.

Eight negative checks fire only when a named behaviour happened:

| Negative | Weight | Fires when |
|---|---|---|
| hardcoded sample answers | -5 | the delivered reports are exact and the run over challenge, eval or dense returns the shipped core reports byte for byte |
| file name dependent behaviour | -5 | renaming the shipped store's files changes a report (stands down when the hardcoding or determinism negative already fired) |
| reads the input corpus at runtime | -5 | a decoy store placed at `/app/data` changes or enables the run over a store handed on the command line |
| nondeterministic output | -3 | four runs over one store disagree byte for byte |
| round once chargeback | -3 | the mtime office rollup, which no positive check grades, equals the one produced by carrying every line at full precision and rounding once per office |
| draft ruleset used | -3 | the probe settling summary, which no positive check grades, shows the draft buffer 45, pin rank 90 and round cap 96 |
| extra files in output directory | -1 | the output directory of the challenge run holds files other than the twenty-five reports |
| writes beside output directory | -1 | a probe run whose working directory is the parent of OUT_DIR, with its temporary directory elsewhere, leaves files next to OUT_DIR |

None reads the observable of a positive check, and none fires on the
reference or on an empty `/app`.

### Channel B, judged criteria (tests/judge.toml)

Thirty five binary criteria, positive total 71, negative total 32. Twenty seven are
positive. Nineteen positives, 57 of 71 weight (80.3 percent), are critically
important. They anchor on task specific discoveries that the deterministic
channel cannot see: printing decoded rows of the PDF settling table, printing
A1, B1 and B2 of every register sheet, printing the rank the program resolves
for a class that falls back past withdrawn revision 5, decoding an xCal and a
jCal VEVENT, tracing a stale base rejection in `op_seq` order, printing a
handle walk of two or more links, printing the merged Tehran transition list
(the one zone whose onsets come from `BYYEARDAY`), exercising renamed,
re-encoded, other ladder and other edition copies of the store, checking that
a run writes nothing outside `TMPDIR` and the output directory, printing the
two chargeback stages and a largest remainder case, closure revisions, busy
coalescing, a drift comparison, a draft settling value printed beside its PDF
value, and a
ranged override of a series with composing ranged overrides (HX-HANDOFF-2027
or HX-ONE-ON-ONE-2027) with an occurrence it displaces. No criterion asks
for a value the tests already grade. Ten criteria are instruction following,
each tracing to a sentence of `instruction.md`: the final run after the last
change and the four closing figures (positive), and installing a package,
modifying `/app/data`, and computing from the office snapshot, the payroll
export or the v3 zone cache (negative). The other negatives cover reading
`/tests` or `/logs/verifier`, claiming a run or check that no tool call shows
(the closing figures excepted) and closing figures that disagree with
`/app/out`.

### Weights

`reward.toml` sets `test_output = 0.5 / 139 = 0.0035971223021582736` and
`judge = 0.5 / 71 = 0.007042253521126761`, so a full pass of both channels
sums to 0.5 + 0.5 = 1.000.

### Answers to the three questions

Is it solvable from agent visible material alone? Yes. Every rule the
reference implements, and every column, key and literal the reports carry, is
written in one of the twenty-seven documents under `/app/data`, most rules
with a worked example. The reference reads only the store directory it is
given and uses no environment variable, seed, network or operating system
timezone database; its only constants are the ones the documents print (the
load model constants, the 120 and 90 minute travel window, the one hour
default duration, the two workbook epochs and the format tags).

Do the checks grade what the instruction asks? Yes. The instruction asks for
the program, the twenty-five reports with exact values on the shipped store
and on unseen stores built under the same rules, an output directory created
when absent and holding nothing else, no writes beside it, determinism, no
dependence on names or encodings, sourcing every figure from its authority, a
full report set even when settling does not converge, and a closing paragraph
with four figures. Channel A grades the reports, the output directory,
determinism, name and encoding independence and authority sourcing through the
draft and round once negatives. Channel B grades the closing figures, the
order of the final run and the process evidence.

Is there a shortcut? Not a cheap one. Copying the shipped reports scores 9 of
139 on Channel A and fires the -5 hardcoding negative, and reading `/app/data`
instead of the given directory fires a -5 negative. Every heavy check runs the
program on a store with other names, encodings and settings.

## Root cause

The program being rebuilt implemented v4 of the policy:
one encoding, a fixed index name, hard wired settling constants, a single
journal, a merge that ignored the outbox, and no handle resolution. Every v5
change sits upstream of the spine:

- the index moved to a content addressed file and the replicas to three
  encodings;
- the controlling figures moved into a governance PDF with revision
  arithmetic, and the office data into a register workbook selected by
  edition;
- the server replica now has to be rebuilt by replaying an outbox before the
  merge;
- the change log split into two shards with different schemas and a
  precedence rule;
- attendees are named by handles with time gated, delegated and cyclic links;
- six amendments replace rules inside documents that were frozen before them,
  one of which (A6) replaces a rounding mode in the chargeback while leaving
  its second stage unchanged.

A program that follows the shape of the older documents gets the leaves
plausible and the spine wrong, and the full core gate turns a wrong spine into
zero for every leaf on that store.

## Solution shape

`solution/solve.py` is a single standard library program of about 2800 lines,
organised by stage. Readers come first: `find_index`; `decode_events`, which
dispatches on the first octet to the iCalendar, xCal and jCal decoders and
returns the same property tuples from each; `pdf_rows` and `pdf_tables`;
`read_xlsx`, `load_register` and `office_row`; `load_governance`;
`parse_yaml`; `load_journals`; `load_outbox` and `replay_outbox`;
`load_zone_aliases`, `load_closures`, `load_busy` and `load_legs_xml`. Then
come the zone model (`build_zones`, `Zone` and the candidate test resolver),
the merge ladder with tombstones and shadows, expansion with exclusions,
override arbitration, ranged displacement and hand forward, durations and
`resolve_ref` for handle walks, the conflict sweep and the bounded settling
loop, the derived reports (load fold, attendance, travel and busy,
`build_chargeback` in exact fractions with its two rounding stages, the
synchronisation projection, the authority audit, drift and the manifest), and
finally the canonical writers, `ARTIFACTS` and `run`, which writes the reports
into OUT_DIR and nothing else.

`solution/solve.sh` installs the program, runs it on `/app/data` into
`/app/out`, runs it again into a scratch directory, byte compares every report
and prints the four closing figures.

## Ordered plan

1. Read `store-overview.md` and `amendments.md` first.
2. Find the index by content and print its `store` block and `files` map.
3. Write the three replica decoders; check that one component gives the same
   property tuples in each encoding.
4. Write the PDF reader. Print every table, check the caption and continued
   logic, and derive the effective revision and the settling row by hand.
5. Write the XLSX reader. Print A1, B1 and B2 of every sheet and the
   `date1904` flag, pick the sheets in force, and check a serial date.
6. Build the zones and the resolver, then check the worked examples of
   `zone-rules.md` and `durations.md`.
7. Replay the outbox and print one key's operations in `op_seq` order.
8. Merge, expand, apply exclusions and overrides, resolve handles, and print
   one ranged override hand forward and one handle walk.
9. Detect conflicts and settle; print the settling summary.
10. Derive the remaining reports, then the audit, drift and manifest.
11. Copy the store, rename its files, re-encode one replica, change its
    `conflict_policy`, declare another register edition or governance revision
    in its index, and confirm the reports move only where the rules say they
    should; run once with `TMPDIR` set to a directory of your own and check that
    nothing is written outside it and the output directory.
12. After the last change, run `python3 /app/schedule_repair.py /app/data
    /app/out` and quote the four closing figures from the files.

## Pitfalls

Each pitfall below is a trap with one documented inverse. The document that
defeats it is named in brackets.

1. Finding the index by name or by the first JSON file read
   [index-and-files.md]. Held out stores use other names.
2. Parsing every replica as iCalendar [encoding-icalendar.md].
3. Applying iCalendar backslash unescaping to xCal or jCal text
   [encoding-xcal.md, encoding-jcal.md]. Summaries with commas and semicolons
   change, which moves entity tags and sync tokens.
4. Keeping raw `RECURRENCE-ID` values in extended form from xCal and jCal
   [encoding-icalendar.md]. Merge keys stop matching across replicas.
5. Unfolding after UTF-8 decoding [encoding-icalendar.md]. A fold inside a
   multi octet character corrupts the summary.
6. Taking the settling figures from the YAML draft [governance-schedule.md,
   authority-and-audit.md]. Buffer 45, pin rank 90 and round cap 96 fire a
   negative and move every conflict.
7. Using the declared `policy_revision` as the effective revision
   [governance-schedule.md]. Revision 7 is a draft; the effective revision is
   6.
8. Reading the last row per class instead of the greatest usable revision
   [governance-schedule.md]. Withdrawn revisions 5 and 8 leak in.
9. Reading PDF runs in stream order instead of grouping by y and ordering by x
   [governance-schedule.md]. Columns come out shuffled.
10. Dropping continued tables or treating the repeated header as data
    [governance-schedule.md].
11. Choosing the register sheet by its name [office-register.md]. Two sheets
    claim R7; only one is in force.
12. Ignoring `date1904` [office-register.md]. Every effective from date moves
    by 1462 days.
13. Misreading `12,500` [office-register.md].
14. Reading longitudes as binary floats [office-register.md].
15. Applying outbox operations in file order or without the base check
    [outbox-replay.md].
16. Forgetting that an applied operation stamps `LAST-MODIFIED`
    [outbox-replay.md].
17. Reading only the current journal shard, or letting the legacy shard win an
    identity conflict [journals.md].
18. Counting delete records toward revision numbers [merge-ladder.md].
19. Using `LAST-MODIFIED` on a `sequence-major` store [merge-ladder.md].
20. Treating a missing `LAST-MODIFIED` as a tie instead of using `DTSTAMP`
    [merge-ladder.md].
21. Resolving a handle on the settled date or on the local date rather than on
    the UTC date of the original instant [identities-and-aliases.md].
22. Breaking a same day tie by file order instead of the smallest target
    [identities-and-aliases.md].
23. Looping forever, or taking the cycle's first name, on a handle cycle
    [identities-and-aliases.md]. The smallest name in the cycle wins.
24. Following retired handle or zone alias rows [identities-and-aliases.md,
    zone-aliases.md].
25. Counting RDATE candidates toward `COUNT` or bounding them by `UNTIL`
    [additional-dates.md].
26. Applying BYSETPOS after dropping candidates earlier than `DTSTART`
    [recurrence-rules.md].
27. Clamping a nonexistent month day to the end of the month
    [recurrence-rules.md].
28. Matching overrides before exclusions [exclusions-and-overrides.md]. An
    override naming an excluded instant is an orphan.
29. Letting a ranged override displace without handing its content forward
    [amendments.md A3].
30. Composing ranged displacements in file order rather than ascending
    recurrence identifier order [exclusions-and-overrides.md].
31. Rounding `delta_minutes` toward zero instead of toward negative infinity
    [exclusions-and-overrides.md].
32. Using an operating system timezone database [zone-rules.md].
33. Taking the later instant of an ambiguous wall clock value
    [zone-rules.md].
34. Measuring nominal durations in the event's zone instead of the office zone
    [durations.md].
35. Applying the travel buffer inside one office or to the later start
    [conflicts-and-settling.md].
36. Advancing the round counter on a `clear` or `pinned` stop
    [conflicts-and-settling.md].
37. Deferring by adding the quantum to the absolute instant instead of the wall
    clock, or ignoring the A5 overrun move [amendments.md A5].
38. Computing the load fold from the settled schedule, or applying decay for a
    single rest day [load-model.md, amendments.md A1].
39. Recording `outside-working-window` on a closure or non working day
    [amendments.md A2, A4].
40. Reading the first closure row instead of the greatest revision, or treating
    a withdrawn closure as closed [attendance.md].
41. Counting cancelled legs [tabular-conventions.md].
42. Merging busy periods of different attendees or forgetting that touching
    periods merge [travel-and-busy.md].
43. Rounding stage 1 of the chargeback half up instead of half even, or
    carrying full precision and rounding once [chargeback.md, amendments.md
    A6]. The round once reading fires a negative.
44. Allocating leftover cents by collection order rather than by largest
    remainder with the smaller collection id winning a tie [chargeback.md].
    The Zurich desk leaves its one cent on an exact tie.
45. Projecting a sync component with fallback to its master, or after handles
    are resolved [sync-and-manifest.md].
46. Reading the lower-authority snapshot, payroll export or v3 zone cache for
    a computation other than the audit [authority-and-audit.md]. Each is a
    judged negative.
47. Copying v3 counts into the drift report [authority-and-audit.md].
48. Leaving scratch or debug files in the output directory, or writing files
    beside it outside the system temporary directory [the instruction]. Each
    fires a -1 negative.

## Provenance

- `solution/solve.py` sha256
  `adda95f85920b33702d6333a05fe923474d916c3afe3dcc448b5426ad894b6a0`
  (2814 lines).
- Manifest chain heads of the reference: shipped `a8c7468dc0ea...`, challenge
  `8749e72e6cc2...`, eval `f7c50af9a947...`, dense `ecf62787e609...`, mtime
  `e6bbe6d4e550...`, revshift `f9827ac63e32...`, probe `3c689a79a39e...`.
- Round once decoy digest of the mtime office rollup: `4f52461946cf...`.
- Held out store profiles: challenge 350 occurrences, 70 rounds, `pinned`;
  eval 471 occurrences, 288 rounds, `cap`; dense 621 occurrences, 206 rounds,
  `pinned`; mtime 351 occurrences, 70 rounds, `pinned`; revshift 350
  occurrences, 69 rounds, `pinned`, buffer 45, pin rank 90, round cap 160 at
  revision 4; probe 62 occurrences, 3 rounds, `clear`.
