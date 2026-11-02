The flat files in `/app/data` are the October 2025 monthly retail
settlement extract of a mid-size electric utility operating across the
four regions of the Meridian Interstate Grid Compact (MIGC). The extract
ships alongside a written data contract at `/app/data/schema.md` that
defines every input file, every reference table, every rate class, every
time-of-use window, every rounding rule, every net-metering rule and every
output artifact shape. Read that contract in full and work out from it how
the customers, premises, tariff schedule, fuel adjustment index, holiday
and DST calendars, currency table, regulator orders, net-metering banks,
service tickets, meter reads and demand intervals fit together. Deciding
which inputs feed which figure is part of the task. Produce the exact
reconciled settlement report the contract describes, deriving every
figure from the data rather than handwriting sample answers.

Deliver a single reusable program at `/app/out/reconcile.py`. Its one-shot
mode is `python3 /app/out/reconcile.py DATA_DIR OUT_DIR`: it reads one
complete extract from `DATA_DIR` and writes the report set into `OUT_DIR`.
Run that mode on the shipped extract so that the whole-corpus
settlement report lands at `/app/out/summary.json`, the applied-rule
audit at `/app/out/policy_audit.json`, and the count and threshold checks
at `/app/out/data_quality.json`. Write the three rate-class rollups to
`/app/out/rate_class_residential.json`,
`/app/out/rate_class_commercial.json`, and
`/app/out/rate_class_industrial.json`. Write the three regional rollups
to `/app/out/region_meridian_north.json`,
`/app/out/region_meridian_south.json`, and
`/app/out/region_meridian_east.json`. Serialise every JSON deterministically
with sorted keys, two-space indentation and a trailing newline, and use
integer Meridian-credit-cents (mrcc) or integer Foreign-Trade-Unit-cents
(ftuc) throughout as the contract requires. No floating-point value
appears anywhere in the artifacts.

The same program must also support a long-lived mode invoked as
`python3 /app/out/reconcile.py --session OUT_DIR`. In this mode, read one
newline-delimited JSON command from standard input at a time. Every command
has exactly two string fields: `turn_id` and `data_dir`. The named directory
is a complete, independent twelve-file snapshot. Fully recompute and replace
all nine JSON reports in the shared `OUT_DIR`, then write exactly one JSON
acknowledgement line `{"status":"ok","turn_id":"<same turn_id>"}` to
standard output and flush it. Continue accepting commands until standard
input reaches EOF, then exit with status zero. Do not carry any derived value,
cache entry, open input, or prior report content from one turn into the next.
If the same snapshot returns later in a session, its artifacts must be
byte-identical to the earlier turn.

The reusable program is judged on multiple extracts you have not seen, both
as independent one-shot inputs and as consecutive turns of one session.
Every unseen snapshot follows the same schema, but any of the twelve data
files may differ: reference rows, effective windows, rates, signs, balances,
calendar treatments, currencies, regions, row order, and transaction rows
are all snapshot data rather than constants. File names, columns, JSON
shapes, allowed values, and the October 2025 period remain as specified by
the contract. Row order has no meaning unless the contract explicitly gives
an ordering rule. Each turn must acknowledge within five minutes. Only the
ten artifact paths named above are collected.

Your delivered script must use only the Python standard library and must
not initiate any network activity of its own. In one-shot mode it must not
read outside `DATA_DIR`; in session mode it may read only the `data_dir`
named by the current command. In both modes it must not write outside
`OUT_DIR`. Do not cheat by using online solutions or hints specific to this
task.

You have 7200 seconds to complete this task.
