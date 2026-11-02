# Brassmoor Skirmish: season 5 errata

This sheet corrects the printed rule book `/app/data/brassmoor_rules.md`.
Each entry names the book section it changes. Where an entry and the book
disagree, the entry wins. Where an entry and a JSON table disagree, the JSON
table wins. Entries are listed in the order they were issued.

| Entry | Book section | Topic |
| --- | --- | --- |
| E-1 | 3.2 | printed roster table is from season 4 |
| E-2 | 2, 6, 7, 8.2 | format 2 logs use a bottom left origin |
| E-3 | 5.2, appendix A | season 5 dice sample width |
| E-4 | 5.4, 8 | ruleset 2 reseeds the stream every turn |
| E-5 | 9.7 | rout threshold |
| E-6 | 7, 8 | keyframe adoption comes before the reseed |
| E-7 | 3.2, 12.1, 13.4 | outrider points value |


## E-1. Roster table (book section 3.2)

The roster table printed in section 3.2 was copied from the season 4 book.
These four numbers changed for season 5, among others:

| Unit | Field | Printed (season 4) | Season 5 |
| --- | --- | --- | --- |
| pikeman | def | 3 | 4 |
| crossbow | range | 6 | 5 |
| lancer | move | 6 | 5 |
| fenrunner | hp | 8 | 9 |

Always read unit stats from `/app/data/units.json`. That file is the season 5
roster and every replay in the export was played with it. The printed table is
kept in the book only so that old tournament sheets can be read.


## E-2. Format 2 coordinates (book sections 2, 6, 7 and 8.2)

The header field `v` gives the log format. Format 1 logs write coordinates in
the canonical frame of section 2: origin at the top left cell, `x` grows to
the right, `y` grows downwards.

Format 2 logs were written by the season 5 client, which puts the origin at the
bottom left cell. `x` is the same in both formats. A format 2 `y` value must be
turned into the canonical frame with

```
y_canonical = height - 1 - y_logged
```

where `height` is the map height from `maps.txt`. The flip applies to every
coordinate a format 2 log carries:

* the `x y` pair of every `U` line,
* every `x,y` waypoint of every `MOVE` order (fresh or lagged), including
  replacement orders inside section 16 `R` lines,
* every `uid@x,y,...` entry of every `K` line.

Nothing else in the log holds a coordinate. The engine works only in the
canonical frame after this conversion. Digests, survivor positions and every
report value are always written in the canonical frame, whatever the format
of the log they came from.

Worked example. Map height 11, format 2 line `U B3 archer 13 2`. The archer
stands at canonical `(13, 8)`, because `11 - 1 - 2 = 8`. A format 2 waypoint
`13,3` is canonical `(13, 7)`, one cell up from the archer.


## E-3. Dice sample width (book section 5.2 and appendix A)

Season 5 narrowed the sample taken from the generator state. The width and
the shift are stored in `rulesets.json` under `dice`:

```
sample = (state >> output_shift) & ((1 << output_bits) - 1)
span   = 1 << output_bits
```

With the season 5 values `output_shift = 23` and `output_bits = 9`, the sample
is the top 9 bits of the 32 bit state and `span = 512`. The rejection rule of
section 5.2 is unchanged in form but uses this span: `limit = 512 - (512 mod S)`.
For a d20 that is `limit = 500`, so samples 500 to 511 are rejected and drawn
again. For a d6 it is `limit = 510`. For a d8 there is no rejection at all,
because 512 is a multiple of 8.

The generator step itself (multiplier, increment, modulus) did not change.


## E-4. Ruleset 2 reseeding (book sections 5.4 and 8)

A match whose header says `rules=2` uses ruleset 2 of `rulesets.json`, which
has `reseed = true`. At the start of every turn `n` (every `T n` block, `n`
starting at 1) the generator state is replaced by

```
state = seed XOR ((n * reseed_multiplier) mod 2^32)
```

where `seed` is the header seed of the match read as a 32 bit number and
`reseed_multiplier` comes from `rulesets.json` (2654435761). The stream then
runs on from that state for the rest of the turn as usual. The turn 0 digest
is taken before any turn starts, so it always shows the header seed.

A match with `rules=1` never reseeds. Its single stream starts from the header
seed and runs through every turn.

The ruleset and the log format are independent. A log can be format 1 with
ruleset 2, format 2 with ruleset 1, and so on. Read both fields from the
header of every match.

Worked example: seed `0000beef`, turn 3. `3 * 2654435761 = 7963307283`,
mod 2^32 that is `3668339987` = `daa66d13`, and `0000beef XOR daa66d13` =
`daa6d3fc`. The first draw of turn 3 is the generator step from `daa6d3fc`.


## E-5. Rout threshold (book section 9.7)

The book prints the rout check as `hp * 3 <= max_hp` (a third of the
maximum). That was the season 4 threshold. Season 5 routs a unit only when it
is down to a quarter of its maximum or less:

```
routed when hp * 4 <= max_hp
```

The check is made, as before, every time a living unit that is not yet routed
loses hit points (after a hit and after a poison tick). A unit that dies is
removed and never routs. Rout stays for the rest of the match.

Example: a swordsman (max_hp 16) at 4 hp routs, because `4 * 4 = 16 <= 16`.
At 5 hp it does not, because `5 * 4 = 20 > 16`, although the printed season 4
rule would have routed it (`5 * 3 = 15 <= 16`). A pikeman (max_hp 14) at 3 hp
routs under both rules; at 4 hp it routs only under the old rule. Use the
season 5 rule.


## E-6. Keyframe adoption and the reseed (book sections 7 and 8)

The `K` line written right after `T n` holds the state at the end of turn
`n - 1`: the generator state as it stood when turn `n - 1` finished, the
control points, and every living unit. It is not the state after the turn `n`
reseed.

So the first two steps of turn `n` are, in this order:

1. If the block has a `K` line, compare the engine state with it, record a
   divergence when anything differs, and adopt the keyframe.
2. If the ruleset reseeds (E-4), replace the generator state with the turn `n`
   reseed value.

For a ruleset 2 match the adopted `rng` value is therefore overwritten in
step 2 straight away, but the comparison in step 1 still uses it: a keyframe
whose `rng` field differs from the engine state is a divergence even in a
ruleset 2 match.


## E-7. Outrider points value (book sections 3.2, 12.1 and 13.4)

The season 5 price list raises the outrider from 4 points to 5 points. The
points value is the `cost` used for the match score in section 12.1 and for
`per_cost_permille` in section 13.4.
