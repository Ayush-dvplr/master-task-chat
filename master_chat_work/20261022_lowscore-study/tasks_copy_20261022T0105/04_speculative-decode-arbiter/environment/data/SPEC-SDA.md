# SDA arbiter replay specification, version 1.4

This document defines every rule the Speculative Decode Arbiter applies when it
replays a recorded run. It is the authority. Where a recorded file and this
document disagree, this document wins.

Nothing in this replay is measured against a clock. Every quantity below is a
whole number of ticks or a whole number of service units, both of which are
recorded in the corpus. A replay performed twice over the same corpus produces
the same figures.

## 1. Vocabulary

A **stream** is one client conversation. A stream issues **windows** in
ascending sequence order. A window is one speculative attempt: the draft
service proposed a vector of candidate tokens, and the target engine later
returned a verdict vector over the same positions.

A **slot** is one shared buffer position. A window holds a **lease** on a slot
for a range of ticks. A **tenant** owns streams and is billed for them.

The slot registry is exactly S00, S01, S02, S03, S04, S05, S06, S07, S08, S09,
S10, S11, S12, S13, S14 and S15.

The tenant registry is exactly T01, T02, T03, T04, T05, T06, T07, T08, T09 and
T10.

## 2. Identifiers and canonical forms

Stream references arrive in the corpus in the form the recording gateway wrote
them, which is lower case or title case with an underscore separator. The
canonical stream identifier is that reference upper cased with every underscore
replaced by a hyphen. A canonical stream identifier looks like `SDA-T07-0143`.
Every emitted artifact uses the canonical form and never the recorded form.

A **window identifier** is the canonical stream identifier, then the single
character `#`, then the window sequence number rendered as a decimal integer
padded with leading zeros to a width of four. Window five of stream
`SDA-T07-0143` is written `SDA-T07-0143#0005`. The sequence number is a
fixed width code in every artifact that carries it, so the leading zeros are
part of the value and are never stripped.

A **class identifier** is three characters. Token class identifiers appear in
the shipped alias table.

## 3. Which recorded field wins

Two files record a tenant for each stream. The tenant recorded alongside the
master stream record is advisory and is present only because the recording
gateway copied it forward. The tenant recorded in the dedicated stream to
tenant table is authoritative. Where the two disagree, the dedicated table
wins, for billing and for every other purpose.

Stream status is recorded as `active`, `retired` or `superseded`. A stream
whose status is `retired` or `superseded` still contributes every one of its
windows to every ledger and to the conservation identity. Status changes
nothing about the accounting and is carried through to the registry unchanged.

## 4. Repairs

Some recorded windows violate the recording schema. Each violation has one
repair and none of them is a rejection. Repairs are evaluated in code order and
a window may carry more than one. The set of codes that applied to a window is
recorded against it.

`R01` The recorded `k_requested` is below 1. Replace it with 1.

`R02` The recorded `k_requested` is above 8. Replace it with 8.

`R03` The recorded draft vector holds more tokens than the repaired
`k_requested`. Truncate the draft vector to that many tokens, keeping the
leading tokens.

`R04` The recorded verdict vector holds fewer tokens than the repaired draft
vector. Extend the verdict vector with the void token `TKFF` until the two
vectors are the same length. The positions that extension covers are positions
the target engine never answered, and section 10 gives them a terminal class of
their own rather than treating them as disagreements. A verdict vector longer
than the draft vector is truncated to the draft length, and that truncation is
not a repair and carries no code.

`R05` The recorded lease expiry tick is at or before the lease grant tick. The
window is void. A void window contributes all of its drafted tokens to the
voided class and contributes nothing to any other terminal class.

`R06` The recorded draft vector holds a token identifier that does not appear
in the shipped alias table. That token resolves to the void class `CZZ`.

## 5. Token equivalence

Every token identifier in the shipped alias table maps to a class identifier.
Two tokens are equivalent when their class identifiers are equal. Tokens are
compared by class and never by identifier, so a draft token and a verdict token
may agree without being the same token.

The void class `CZZ` never agrees with anything, including with itself. A
position where either side resolves to `CZZ` is a disagreement.

## 6. The policy value of K

Each window is replayed at a **policy K**, which may differ from the repaired
`k_requested` the corpus recorded. The policy K truncates the window: only the
leading policy K tokens of the repaired draft vector and of the repaired
verdict vector take part, and the number of tokens the window drafted is the
length of that truncated draft vector.

Within one stream the policy K evolves across windows in ascending sequence
order. The first window of a stream is replayed at the stream's **seed K**. The
value carried forward to the next window is decided by an exponential moving
average of acceptance.

The moving average is written alpha. Before the first window of a stream alpha
is 0.5. After each window alpha becomes

    alpha = (1 - L) * alpha + L * r

where `L` is `2 / (W + 1)`, `W` is 25, and `r` is that window's agreement
ratio, meaning its agreed prefix length divided by the number of tokens it
drafted. A window that drafted no tokens contributes an agreement ratio of 0.

After alpha is updated, the policy K carried to the next window of the same
stream is decided as follows. When alpha is strictly greater than 0.85, the
policy K increases by 1 and is held at 8 when it would exceed 8. When alpha is
strictly less than 0.30, the policy K becomes 1. Otherwise the policy K is
unchanged. An alpha of exactly 0.85 or exactly 0.30 leaves the policy K alone.

## 7. Seed recalibration and its fixed point

The seed K is not simply the recorded seed. The arbiter recalibrates it against
the behaviour the stream actually showed, and because the schedule decides that
behaviour and the behaviour decides the schedule, the two are solved together.

One **pass** over a stream replays every one of its windows in ascending
sequence order at the policy K that section 6 produces from the current seed K,
and yields the schedule of policy K values, one per window.

After a pass, the stream's **pooled acceptance ratio** is the total agreed
prefix length over all of its windows divided by the total number of tokens
those windows drafted, with a stream that drafted no tokens taking a pooled
ratio of 0. When the pooled ratio is strictly greater than 0.85 the seed K
increases by 1 and is held at 8. When the pooled ratio is strictly less than
0.30 the seed K becomes 1. Otherwise the seed K is unchanged, and because an
unchanged seed reproduces the same schedule, the stream has converged.

Passes continue until the schedule a pass produces is identical to the schedule
the previous pass produced, at which point the stream has converged and the
number of passes performed is recorded. A stream that has not converged after 6
passes stops there. It is recorded as not converged, the pass count recorded is
6, and the schedule emitted is the one the sixth pass produced.

## 8. Leases, preemption and priority inversion

A lease covers the tick range that begins at its grant tick and ends before its
expiry tick. The range is closed at the grant tick and open at the expiry tick,
so a lease granted at tick 12 and expiring at tick 15 covers ticks 12, 13 and
14, and its **span** is 3 ticks. A span computed as a negative number is 0.

Each priority class carries a rank. The ranks are `bulk` 1, `standard` 2,
`interactive` 3 and `realtime` 4.

A recorded revocation names a slot, a tick, the stream that issued it and the
window that held the slot. A revocation takes effect only when the issuing
stream's rank is **strictly greater** than the holding stream's rank. When it
takes effect and its tick falls before the lease expiry, the lease expiry
becomes the revocation tick.

A revocation issued by a stream whose rank is equal to or lower than the
holder's rank does not take effect. The lease is unchanged and the event is a
**priority inversion**, which is recorded. A window may carry more than one
recorded revocation.

## 9. Cancellation

A cancellation names a stream and a tick. A stream is cancelled at most once.
Only journal records whose message identifier is `STREAM_CANCEL` are
cancellations. Records carrying any other message identifier, including
`STREAM_ADMIT` and `LANE_HEARTBEAT`, carry no cancellation meaning and are
ignored for this purpose.

A window of a cancelled stream whose lease grant tick is at or after the
cancellation tick is **reclaimed**. All of its drafted tokens go to the
reclaimed class and it contributes nothing to any other terminal class.

A window of a cancelled stream whose lease grant tick falls before the
cancellation tick is not reclaimed. Instead its lease expiry is brought forward
to the cancellation tick when the cancellation tick is earlier, which shortens
its span.

## 10. Terminal token classes

Every token a window drafted under its policy K ends in exactly one of five
terminal classes: `accepted`, `rejected`, `expired`, `reclaimed` or `voided`.

For a void window, every drafted token is `voided`.

For a reclaimed window, every drafted token is `reclaimed`.

For every other window, the **agreed prefix** is the length of the longest
leading run of positions at which the draft token and the verdict token share a
class, under section 5. The tokens of that prefix that the lease span permitted
are `accepted`, and the number permitted is the smaller of the agreed prefix
and the span. The tokens of the agreed prefix beyond what the span permitted
are `expired`.

A drafted token sitting at a position the recorded verdict vector never reached,
meaning a position that repair `R04` had to extend the verdict over, is
`voided`. The target engine returned no opinion there, so such a token is not a
disagreement and is never counted as one. Every remaining drafted token after
the agreed prefix is `rejected`.

The order of these two operations is load bearing. The agreed prefix is
resolved first, over the policy truncated vectors, and only then does the span
bound how many of those agreed tokens are accepted. A replay that applies the
span first reports different figures.

## 11. The conservation identity

For any set of windows, the number of tokens drafted equals the sum of the five
terminal classes over the same set. The **residual** is the number drafted
minus that sum, and a correct replay reports a residual of 0 at every level at
which it is reported.

## 12. Bands

A stream's band follows from its pooled acceptance ratio at the schedule the
stream converged on, or at the schedule of the sixth pass when it did not
converge. The band is `high` when the pooled ratio is greater than or equal to
0.85, `mid` when it is greater than or equal to 0.30 and below 0.85, and `low`
otherwise. Both boundaries are closed from below.

The band is a property of the whole stream and is therefore only known once
that stream's schedule has settled. Artifacts that carry a band against a
window carry the band of the stream that window belongs to.

## 13. Service unit accounting

Costs are whole numbers of service units. The unit costs are

    draft_unit      3    per token drafted
    verify_unit     7    per window replayed
    emit_unit       2    per token accepted
    reclaim_unit    5    per token reclaimed
    expire_unit     4    per token expired
    void_unit      11    per token voided
    inversion_unit 13    per recorded priority inversion

A stream's gross cost is the sum of those seven terms over that stream. A
tenant's gross cost is the sum of the gross costs of the streams the
authoritative stream to tenant table assigns to it.

A tenant's **cap** is the sum of the allocated units of the streams that table
assigns to it. The cap is applied to the tenant total **after** that total has
been aggregated, never to a stream before aggregation. A tenant whose gross
cost exceeds its cap is billed its cap and is marked as over cap. A tenant
whose gross cost is at or below its cap is billed its gross cost and is not
marked as over cap.

Every tenant in the registry appears in the cost artifact, including a tenant
that owns no stream, which carries zero in every numeric column.

## 14. Rounding and number rendering

Every ratio that an artifact carries is rendered with exactly four digits after
the decimal point, rounded half to even. Rounding happens only when a value is
rendered. No intermediate value is ever rounded, and a ratio carried from one
stage to the next carries its full precision.

Whole numbers are rendered without a decimal point and without thousands
separators. A boolean is rendered as the bare lower case word `true` or
`false`.

## 15. Text encoding and file mechanics

Every file the replay writes is UTF-8 without a byte order mark, uses a line
feed as its line terminator, and ends with exactly one trailing line feed.

The exact column set, column order, delimiter, header rule and row order of
every emitted artifact is given in the output format reference that ships
beside this document.

## 16. Recorded corpus formats

The recorded corpus is spread across many files and several formats. Each
format below appears in the corpus and each is parseable with the standard
library alone.

Comma separated, tab separated, pipe separated and space separated files carry
one record per line. Those that carry a header line say so by naming their
columns on the first line; a file whose first line is already a data record has
no header.

JSON Lines files carry one JSON object per line.

Properties files carry `key = value` pairs, one per line, and lines beginning
with `#` are comments.

Logfmt files carry unquoted `key=value` pairs separated by single spaces, one
record per line, with no header.

RFC822 style files carry records of `Field: value` lines, with records
separated by a blank line.

RFC5424 style journal lines carry a priority in angle brackets, a version, a
timestamp, a host, an application, a process identifier, a message identifier,
one bracketed structured data block of `key="value"` pairs, and a free text
message.

Fixed width files place each field at a documented column range. In the token
width table the token identifier occupies columns 1 to 4, the class identifier
occupies columns 6 to 10, and the emit width occupies columns 12 to 14, where
column numbers begin at 1 and trailing spaces inside a field are padding.

Window records are sharded across several files of the same format. A shard
boundary carries no meaning: the records of one stream may fall in more than
one shard, and a replay must read every shard of a family before it can treat
that family as complete.
