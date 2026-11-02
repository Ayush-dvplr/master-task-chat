The Meridian corridor authority runs four industrial sites. Each site owns a small set of
lanes, and every accepted work order has to be placed on exactly one lane. The authority
has handed you its written rule set, its directories, and a stream of encoded work-order
packets, and it wants the season settled: which orders run, where they run, and what they
cost.

Everything you need is under `/app/data`. Survey all of it before you start. The rules
live across several policy documents, the directories and the packet stream live in
tabular and encoded form, and no single file carries the whole picture. The documents
state each rule precisely and state the invariants the finished settlement has to satisfy,
but they deliberately stop short of telling you the order in which the rules bind or the
values of the constants the packet stream was written with. Those you recover.

The packet stream travels in an encoded wire form. The encoding document names every
transform the stream may carry and names the constant each transform depends on, but the
value of each of those constants is withheld. A held-out calibration population ships
alongside the field population, together with a short list of published control figures
computed from it. Exactly one assignment of the withheld constants reproduces every
control figure at once. Recover that assignment.

With the constants settled, decode the field population, resolve each order to its
governing client and its governing programme revision, decide which orders the sites can
admit, place every admitted order on a lane so that no lane rule is broken and the total
lane cost of each site is as low as any feasible placement allows, and settle the money.

Deliver a reusable program at `/app/out/derive_report.py`. It must take an input
directory as its first argument and an output directory as its second, and it must derive
everything it writes from the files in the directory it is given. Running it against a
different corpus laid out the same way must produce that corpus's settlement, so no figure
recovered from the supplied corpus may appear in it as a fixed literal. Allow it a few
minutes per corpus at most: a corpus roughly twice the size of the supplied one has to
settle well inside ten minutes on one core.

Write the season summary to `/app/out/summary.json`, the reconciliation report to
`/app/out/data_quality.json`, and one rollup per region to `/app/out/region_North.json`,
`/app/out/region_South.json`, `/app/out/region_West.json` and `/app/out/region_East.json`.
Write one rollup per service segment to `/app/out/segment_commercial.json` and
`/app/out/segment_public.json`. Every placed order belongs to exactly one region rollup and
exactly one segment rollup, the two partitions cover the same orders, and the money in the
rollups has to add back to the money in the summary with nothing left over. The
reconciliation report carries the residuals of those conservation checks and the verdict
on each invariant the rule set names.

One fully-formed rollup for a small probe population ships with the corpus. Take the shape
of your region and segment rollups from it. A labelled decode of that same probe population
ships too; it is the untrapped tier and its constants are its own.

The field names and value types of the season summary, the reconciliation report and the
derivation record are fixed in `report_schema.md`, which ships with the corpus. It names the
fields and none of the values, so follow it exactly and work every value out yourself. The
probe rollup and the labelled probe decode are there for you to read, not for your program to
read; it has to run against a corpus that carries neither.

Write your derivation record to `/app/out/policy_audit.json`. It records the work rather
than the answer: the candidate space you enumerated for each withheld constant, the
verdict you reached on every candidate value, the control figure that eliminated each
rejected value, the comparison of your recovered assignment against every published
control, the number of passes your admission settlement took to reach a stable state with
the congestion figure it settled at for each site, and the shape of your placement search.

Work in this order and record it. Settle every withheld constant against the calibration
population before you derive any figure for the field population. Record a verdict for
every candidate value in a constant's domain before you select the value for that
constant. After you settle the final constant, re-run your complete derivation from
scratch so that every report you leave behind is written by that final run and no report
carries a figure from an earlier attempt. Carry every monetary figure as a whole number of
micro units from end to end. Resolve each order's client to its governing form before you
select any governing programme revision.

Do no editing of anything under `/app/data`; treat it as read-only. Do not embed values
recovered from the supplied corpus in your program as fixed literals. Your program must read
only the directory it is handed, never a path written into its own source. This container has
no network access, so work entirely from what is already on it: do not install third-party
packages and do not expect to fetch anything. The Python standard library is sufficient for
this work.

You have 21600 seconds to complete this task.
