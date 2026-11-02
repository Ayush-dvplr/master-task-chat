# SDA glossary

Terms this project uses with a narrower meaning than ordinary usage. Each is
defined once here and used throughout the specification and the appendices. The
ordinary reading of several of them is close enough to look right and is wrong
on part of the corpus, so read each definition rather than assuming it.

**accepted** A drafted token that both agreed with the verdict at its position
within the agreed prefix and fell inside what the lease span permitted. A token
that agreed but sat beyond the span is expired, not accepted, so accepted is
narrower than agreed.

**agreed prefix** The length of the longest leading run of positions at which
the draft token and the verdict token resolve to the same class. It stops at
the first disagreement and never resumes, so a later agreeing position does not
extend it.

**band** A property of a whole stream, taken from its pooled acceptance ratio
once its schedule has settled. `high` at 0.85 and above, `mid` from 0.30 up to
but not including 0.85, and `low` below 0.30. Both boundaries are closed from
below. A band is never a property of one window; a window carries the band of
the stream it belongs to.

**cancelled** A stream named by a journal record whose message identifier is
`STREAM_CANCEL`. No other message identifier cancels anything. A stream is
cancelled at most once.

**converged** A stream whose pass produced a schedule identical to the schedule
its previous pass produced. A stream that stopped at the sixth pass without
that happening is not converged, and its recorded pass count is still 6.

**drafted** The number of tokens a window put forward under its policy K, which
is the length of its repaired draft vector truncated to the policy K. It is not
the recorded `k_requested` and it is not the length of the recorded draft
vector.

**effective expiry** The expiry after every revocation that took effect has
been applied. Only a revocation moves it, so it is the figure the lease grants
artifact reports and the figure the cancellation timeline compares a grant
against. A cancellation shortens what the window is scored against without
changing this figure. The recorded expiry is what the corpus holds and is
reported separately.

**expired** A drafted token inside the agreed prefix that the lease span did
not permit. An expired token agreed with the verdict; it simply did not leave
the buffer in time.

**gross cost** A stream's or tenant's service unit total before any cap is
applied. The capped figure is reported alongside it and never replaces it.

**inversion** A recorded revocation whose issuing stream's rank is equal to or
lower than the holding stream's rank. It changes no lease. Equal ranks invert;
only a strictly greater rank preempts.

**policy K** The value of K at which one window is actually replayed. It is
produced by the schedule and is usually not the repaired `k_requested` the
corpus recorded.

**pooled acceptance ratio** A stream's total agreed prefix length divided by
its total drafted count, over all of its windows at the settled schedule. It is
not the mean of the per window ratios and the two differ whenever windows draft
different numbers of tokens.

**reclaimed** Every drafted token of a window of a cancelled stream whose grant
tick is at or after the cancellation tick. A window granted before the
cancellation tick is never reclaimed, however much of its lease the
cancellation cut short.

**rejected** A drafted token at or after the position where the agreed prefix
ended. Whether the lease had span left is irrelevant to it.

**repaired** A recorded value after the documented repairs of specification
section 4 have been applied to it. Every repair is a correction and none is a
rejection, so no window is ever dropped for being malformed.

**residual** A drafted count minus the sum of the five terminal classes over
the same set of windows. A correct replay reports 0 everywhere it reports a
residual.

**seed K** The value of K the first window of a stream is replayed at. The
corpus records one and the arbiter recalibrates it, so the recorded seed and
the final seed are two different figures and both are reported.

**span** The effective expiry minus the grant tick, floored at 0. It counts
ticks, and because the lease interval is open at its expiry end, a lease from
tick 12 to tick 15 has a span of 3. That is the span the lease grants artifact
reports. When the holding stream was cancelled after the window was granted,
the span that bounds how many agreed tokens are accepted is measured to the
cancellation tick instead, and the reported span is left alone.

**stream reference** A stream identifier in the form the recording gateway
wrote it, which is lower case or title case with underscores. It is never
emitted. The canonical identifier is its upper case form with hyphens.

**superseded** A stream status. It changes nothing about the accounting. A
superseded stream contributes all of its windows to every ledger exactly as an
active one does.

**void** A window whose recorded expiry is at or before its grant tick. Every
token it drafted is voided and it contributes to no other terminal class. Void
describes a window; the void class `CZZ` describes a token that resolves to
nothing and agrees with nothing, and the two are separate ideas that happen to
share a word.

**voided** A drafted token that reached no verdict. Two separate situations put
a token here. Every token of a void window is voided, and so is every token
sitting at a position the recorded verdict vector never reached, which is a
position repair `R04` had to extend the verdict over. A voided token of the
second kind is never counted as a rejection, because the target engine returned
no opinion at that position rather than a disagreeing one.
