A speculative decoding fleet ran for one accounting period and the arbiter that
supervised it kept a recording. The draft service proposed candidate tokens in
batches, the target engine returned a verdict on each batch some time later,
shared buffer slots were leased and sometimes taken away, and a number of
client conversations were cancelled part way through. The recording survived.
The accounting the operator owes its tenants did not, and you are going to
rebuild it.

The recording sits in `/app/data`. It is spread across many files in several
formats, none of which is described here. Working out what each file holds,
which files matter and how they join is part of the job.

Every rule the replay follows is written down in `/app/data/SPEC-SDA.md`. That
document is the authority on identifiers, repairs, token equivalence, the
policy value of K and how it settles, leases and preemption, cancellation, the
five terminal token classes, the conservation identity, bands, service unit
accounting, rounding and file mechanics. Three companion documents sit beside
it and carry worked examples and definitions that the specification refers to.
Read all of them before you write any code. Where a recorded file and the
specification disagree, the specification wins.

The exact shape of every file you produce, meaning its columns, its column
order, its delimiter, whether it carries a header and the order of its rows, is
given in `/app/data/sda-output-formats.md`. Perfect figures in the wrong shape
are wrong, so treat that document as binding rather than advisory.

A local service also ships inside the recording, as `arbiter_service.py`. Its
contract is written in `/app/data/api_contract.md`. The service is the control
plane the run acts against. Start it, and enact the admission, cancellation and
lease decisions your replay reaches by driving it through both of the channels
that contract describes, making at least one state change through its command
line channel and at least one through its HTTP interface. The service computes
nothing and grades nothing. It is where the decisions are recorded, not where
they are made.

Produce exactly these files and nothing else in the output directory.

```
/app/out/stream_registry.csv
/app/out/token_classes.json
/app/out/window_index.tsv
/app/out/lease_grants.psv
/app/out/cancel_timeline.jsonl
/app/out/k_schedule.tsv
/app/out/acceptance_ledger.csv
/app/out/lease_conflicts.tsv
/app/out/reclaim_ledger.csv
/app/out/malformed_repairs.jsonl
/app/out/window_disposition.csv
/app/out/token_accounting.tsv
/app/out/stream_metrics.json
/app/out/tenant_cost.csv
/app/out/inversion_report.tsv
/app/out/nonconvergence_report.jsonl
/app/out/slot_occupancy.tsv
/app/out/conservation_ledger.json
/app/out/reconciliation.tsv
/app/out/arbiter_driver.py
/app/out/run_manifest.json
```

What each of those holds follows from what its values mean, and the meanings
are what this section gives you. The registry carries one row for every stream
the recording knows about, under the canonical identifier form, with the tenant
that is answerable for it, its lane and rank, the seed value of K the recording
holds, its admission window and its status. A stream whose status is retired or
superseded is a stream like any other for every purpose here.

The token class map carries the equivalence the replay compares tokens under.
Two tokens agree when their classes agree, which is not the same as the two
tokens being equal, and one class agrees with nothing at all.

The window index carries one row for every recorded window under its window
identifier, with the value of K the recording asked for after repair, how many
tokens the repaired batch actually held, the slot it leased, the ticks its
lease was granted and recorded to expire at, which repairs applied to it, and
the band its stream ends the period in.

The lease grants file carries, for every window, the expiry the recording held,
the expiry that survived every revocation that took effect, which stream took
the slot away where one did, and how many ticks the lease was good for.

The cancellation timeline carries one entry per cancelled stream with the tick
it was cancelled at, where the cancellation came from, how many of its windows
were granted at or after that tick, and how many were granted before it and
were still holding their slot when it arrived.

The schedule file carries, for every stream, the seed value of K the recording
held, the seed value the replay settled on, how many passes it took to settle,
whether it settled at all, and the value of K each of its windows was replayed
at in sequence order.

The acceptance ledger carries, for every window, the value of K it was replayed
at, how many tokens it drafted at that value, how long its agreed prefix ran,
and how those drafted tokens divided across the five terminal classes.

The lease conflict file carries every recorded revocation with both ranks
involved, the tick it was issued at and whether it took effect. The inversion
report carries the subset that did not take effect, together with the tokens
each one left in place by failing to.

The reclaim ledger carries, for every cancelled stream, how many of its windows
and how many of its tokens the cancellation took back and how many distinct
slots that released. The repairs file carries one entry for every documented
repair code, including any code that no window needed.

The disposition file carries one row per window with its band, its drafted
count, its five terminal figures and the single class that holds the most of
its tokens. The accounting file carries the same five figures totalled per
stream, beside that stream's drafted count and the amount by which the two
fail to agree. The metrics file carries, per stream, its pooled acceptance
ratio, the band that ratio puts it in, the value its moving average finished
at, how many windows it holds, how many passes it took and whether it settled.

The tenant cost file carries, for every tenant the recording knows about, the
service units its streams ran up, the amount it is actually billed once its
allowance has been applied to that total, the allowance itself, and whether the
allowance bound. The occupancy file carries, for every slot, how many windows
held it, how many ticks were granted on it, how many survived, and the largest
number of live leases it ever carried at one tick.

The streams that never settled are listed on their own with the schedule they
were stopped at. The conservation ledger carries the run wide drafted count,
the run wide total of each terminal class, and the amount by which those two
fail to agree. The reconciliation file states each of those six figures twice,
once aggregated from the per window ledger and once aggregated from the per
stream accounting, together with the difference between the two derivations.
Neither derivation may be copied from the other, because a copy would carry an
error across rather than catch it.

The driver is the program that performed the replay, delivered as a single
Python source file that runs on the standard library alone. Pointed at a
recording directory and an output directory with the two arguments the output
format document names, it must read that recording, write every other file
listed above into that output directory and exit cleanly. It must hold no
figure from this particular recording, because it will be pointed at recordings
it has never seen and is expected to produce their figures rather than these.

The manifest closes the set by naming every other file you produced, in the
order listed above, with the digest and byte length of each.

Several things about this recording are easier to get wrong than to get right,
and all of them are written down. Some recorded windows violate the recording
schema, and every violation has a repair rather than a rejection, so no window
is ever dropped for being malformed. The value of K a window is replayed at is
usually not the value the recording asked for, and it moves as the stream
progresses. The seed that schedule starts from is itself recalibrated against
the behaviour the schedule produces, so the two settle together rather than one
following the other, and a stream that never settles is stopped at the
documented limit and reported. A revocation only takes effect when the stream
issuing it outranks the stream holding the slot, and equal ranks do not
outrank. A cancellation reclaims a window whole or shortens its lease depending
on which side of it the window was granted, and those two outcomes are counted
separately and never both. The order in which the agreed prefix and the lease
span are applied changes the answer, and only one order is the one this
specification describes. An allowance applies to a tenant total after that
total has been formed, never to a stream before it. Two files record a tenant
for each stream and only one of them is authoritative.

Every group the specification defines produces its row even when it is empty,
carrying zeros or the empty string as that document states, so a tenant that
owns no stream, a slot no window ever held and a repair code no window needed
all still appear. Identifiers are emitted in the canonical form the
specification defines and never in the form the recording wrote them. A
sequence number is a fixed width code and keeps its leading zeros.

A column that reports a condition is present on every row of its file whether
or not the condition applied, carrying the empty string where it did not, so no
row is ever shortened and no column is ever dropped. One of the files is
ordered on a different key from all the others, and that ordering is stated
where that file is described rather than here. Where a value is decided by a
comparison that can tie, the specification gives the order the tie is broken
in, and every one of those chains has to be followed to its end because the
recording contains ties that the first level alone does not separate.

A cancelled stream that turns out to have reclaimed nothing still carries its
entry in the reclaim ledger, with zero in each of its count columns, and this
recording contains sixteen such streams. A window that a repair marked void
still carries its row in every file that lists windows, still counts toward the
window total of the slot it held, and contributes nothing to that slot's live
ticks. None of these are filtered away.

The control plane holds admitted streams, cancelled streams, slot holders and
free text notes, and it stores identifiers exactly as they are sent, so send the
canonical form. Repeating an operation that has already been recorded leaves its
list unchanged rather than duplicating an entry.

Two of the files above are stated twice over. The conservation ledger states the
run wide figures once, and the reconciliation file states the same six figures
again from a second derivation that begins at the per stream accounting rather
than at the per window ledger. Both derivations have to be built, because the
difference column is the only place a mistake upstream becomes visible, and a
difference column computed by subtracting a figure from itself reports zero
whatever went wrong.

Every file you write is UTF-8 with no byte order mark, uses a line feed as its
line terminator, and ends with exactly one trailing line feed. Whole numbers
carry no decimal point and no thousands separator. A boolean is the bare lower
case word true or false. A ratio carries exactly four digits after the decimal
point and is rounded half to even at the moment it is written, so no value is
ever rounded on its way between two stages.

The replay is deterministic. Running it twice over the same recording into two
clean directories must produce the same bytes both times, so nothing in it may
depend on the wall clock, on a random draw, on the iteration order of a hash
container, on an environment variable or on the order the recording happens to
list its rows in. Reordering the rows inside any recorded file changes nothing
about the answer.

The driver takes its recording directory and its output directory as the two
named arguments the output format document gives, defaults to the paths used
here when they are absent, and exits with status 0 on success. It reads every
figure it needs from the recording it was pointed at. A driver that carries any
figure from this particular recording inside it has failed the one thing the
driver exists to demonstrate.

Leave `/app/data` exactly as you found it. Read it as much as you like and
change nothing in it. Write nothing into `/app/out` except the files listed
above, so no scratch copies, no working notes and no intermediate dumps beside
the deliverables. The driver you hand over has to run on the Python standard
library alone.

Do not cheat by using online solutions or hints specific to this task.
You have 7200 seconds to complete this task.

When the work is done, finish with a short written summary that states each of
the following closing figures by name and value: `windows_at_k8`, the number
of windows whose policy value of K came out at 8; `mean_pooled_ratio`, the
mean of the pooled acceptance ratios across every stream, to four decimal
places; `high_band_streams`, the number of streams whose band is high;
`low_band_windows`, the number of windows whose band is low;
`lease_limited_windows`, the number of windows where the accepted count came
out below the agreed prefix; `multi_repair_windows`, the number of windows
that carry two or more repair codes; `recalibrated_streams`, the number of
streams whose settled seed differs from the seed the recording held;
`max_schedule_stream`, the identifier of the stream whose schedule reaches the
highest value of K, taking the lowest identifier if several tie;
`distinct_schedules`, the number of distinct schedules across every stream,
counting two streams as sharing a schedule when their sequences of policy K
values are identical; `total_billed_units`, the sum of the billed figures
across every tenant; `max_peak_concurrent`, the highest peak concurrency
reached on any slot; `nonconverged_drafted`, the number of tokens drafted by
the streams that never settled; `capped_tenant_drafted`, the number of tokens
drafted by the streams of every tenant that was billed its cap;
`high_band_drafted`, the number of tokens drafted by the streams whose band is
high; `empty_reclaim_streams`, the number of cancelled streams that reclaimed
no window at all; `over_cap_tenants`, the number of tenants whose service unit
total came out above their allowance; and `void_disposition_windows`, the
number of windows whose dominant class is the voided one. State every one of
those seventeen figures, and state which of the two service channels you used
for each state change you made.
