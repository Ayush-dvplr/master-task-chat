# Precedence charter

Which assertion governs when several disagree, and how a run of state
assertions becomes one resolved state.

## 1. Source classes

Every feed file belongs to one source class, named by `source_class` in
`feed_manifest.csv` and visible in the file name. The eight classes and their
ranks are:

```
rank 6   vault
rank 5   desk
rank 4   bridge
rank 3   partner
rank 2   mirror
rank 1   import
rank 1   relay
rank 0   legacy
```

`import` and `relay` share rank one on purpose, and nothing about the class
name separates them.

## 2. The ordering key

Competing rows for one subject are put in one order, and the two rules that
consume that order are section 3 and section 4. Read the order first and each
rule afterwards, because they consume it differently.

The order is by ascending rank. Inside one rank the order is by ascending
`observed_at`, with two exceptions, and the two do not reach as far as each
other.

Rows of class `desk` are journal lines written at the moment the decision was
taken rather than at the moment it was filed, so inside rank five the order is
by **descending** `observed_at`. This inversion applies to `desk` rows wherever
they compete, both for commitment assertions and for state assertions.

Rows of class `bridge` are handed over by a nightly sweep that walks its spool
from the newest entry backwards, and only its state entries carry the instant
the sweep read them. So inside rank four the order is by **descending**
`observed_at` for state assertions, and by ascending `observed_at` for
commitment assertions. A `bridge` commitment assertion is ordered like every
other class.

No third class carries an inversion.

Where two rows are still level, the order is by ascending row identifier, which
is `assertion_id` for a commitment assertion and `state_id` for a state
assertion.

## 3. Winning assertion

Among the accepted assertions naming one commitment key, the **last** under
section 2 is the winning assertion. Every field of the commitment is taken from
that one row and no field is taken from any other. Where the losing rows carry
a different effort, a different due instant or a different project, those values
do not reach the ledger. Taking the last means the highest rank wins, the later
instant wins inside a rank, and the earlier instant wins inside rank five.

## 4. Resolved state

The resolved state is not read off one row. It is what a walk over every
accepted state row arrives at, and the walk consumes the order of section 2
from its **first** row rather than its last.

Every commitment begins `OPEN`.

Take the accepted state rows naming that commitment and put them in the order of
section 2. Walk them from the first to the last. A row is applied when the
transition from the state currently held to the row's `to_state` is one of

```
OPEN      -> SETTLED
OPEN      -> DEFERRED
OPEN      -> WITHDRAWN
DEFERRED  -> OPEN
DEFERRED  -> WITHDRAWN
```

and the state held becomes the row's `to_state`. A row whose transition is not
one of those five is rejected with `ILLEGAL_TRANSITION`, changes nothing, and
the walk continues with the next row.

`SETTLED` and `WITHDRAWN` are terminal, so no transition leaves either of them.
The consequence is the part worth reading twice: the first row in the order that
reaches a terminal state fixes the resolved state, and every row after it is
rejected however high its rank. A low ranked row that settles a commitment
therefore stands, and a vault row arriving later in the order is rejected rather
than overriding it. Rank decides where a row sits in the order, and it does not
license a row to overwrite a terminal state.

The state held after the walk is the resolved state. A commitment with no
accepted state row is `OPEN`.

`OPEN`, `SETTLED`, `DEFERRED` and `WITHDRAWN` are the only four states. A
`to_state` outside those four, in any spelling or any case, is `MALFORMED_ROW`.

The governing class of a commitment is the source class of the last state row
that was applied to it, and is empty when no row was applied.
