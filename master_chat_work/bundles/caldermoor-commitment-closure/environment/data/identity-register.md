# Identity register

How a surface string naming a principal becomes a canonical handle, and when it
refuses to become one.

## 1. The comparison fold

Two principal references compare equal only after both have been folded. The
fold is applied in this order and nothing else is applied:

```
1. Unicode normalization to NFC
2. strip leading and trailing whitespace
3. case fold
4. delete every occurrence of . - _ and '
5. collapse each run of whitespace to one space
6. strip leading and trailing whitespace again
```

`Gowan.Pyrford`, `gowan_pyrford` and `GOWAN-PYRFORD` fold to the same string and
are the same reference. Nothing else about two references makes them equal.

Every comparison in this document, every join onto a roster line, and every
lookup of an alias surface uses the folded form on both sides.

## 2. The roster

`roster_desk.csv`, `roster_mirror.tsv` and `roster_vault.jsonl` each carry the
roster. A canonical handle is any `canonical_handle` appearing on a roster line,
and the `actor_id` on that line is the principal identifier that every
deliverable states. The three files agree on the pairing and a handle appearing
on more than one line is one principal.

A reference that folds to a canonical handle resolves to that principal at every
instant, with no hop.

## 3. Alias assertions

`aliases_desk.csv`, `aliases_import.jsonl`, `aliases_mirror.tsv`,
`aliases_partner.psv` and `aliases_vault.kv` each carry alias assertions. One
assertion states that a `surface` stands for a `target` throughout the half open
interval `[scope_start, scope_end)` and states nothing at all outside it.

Two assertions carrying the same folded surface, the same folded target and the
same interval are one assertion however many files repeat them.

An interval whose start equals its end contains no instant, so an assertion
carrying one holds nowhere. An interval lying wholly outside the window holds at
no instant any row in this extract carries. Both kinds are recorded history and
neither resolves anything.

## 4. Resolution

Resolution takes a surface and an instant. The instant is the one the rule using
the resolution names, and it is never a different instant.

Start from the folded surface. Follow every alias assertion whose folded surface
equals the string reached and whose interval contains the instant, and repeat.
Membership of the interval is tested at the same instant at every hop, so an
assertion is followed only when it holds at that one instant, and a path through
an assertion that lapsed earlier or begins later is not a path.

A path that revisits a string it already reached is abandoned at that point.

Collect the canonical handles reached by any surviving path. The outcome is:

```
exactly one canonical handle    that principal, resolved
two or more distinct handles    AMBIGUOUS_IDENTITY
none                            UNKNOWN_PRINCIPAL
```

The hop count of a resolution is the fewest alias assertions on any surviving
path that reaches the one canonical handle. A reference that folds directly to
a canonical handle has a hop count of zero.

## 5. What this rule refuses to do

The alias assertions do not describe one partition of the surfaces. A surface
stands for one principal at one instant and may stand for a different principal
at another instant, because the two assertions carrying it hold over intervals
that do not meet. Both assertions are true and neither supersedes the other.

A surface carried by two assertions whose intervals do overlap, naming two
different principals, resolves to `AMBIGUOUS_IDENTITY` at every instant inside
the overlap and resolves normally at every instant outside it. No rule in this
directory chooses between the two, and none is to be invented.

An alias whose target is itself only an alias resolves through the target, and
the interval of every assertion on that path is tested at the same instant.
