# Brassmoor Skirmish: rule book and replay reference (season 5 edition)

This book describes how a Brassmoor Skirmish match is played and how the
studio replay logs record it. A replay engine that follows this book, the
errata file and the JSON tables exactly will reproduce every state digest
the studio expects.

Read this book together with `/app/data/errata.md`. Where a section of this
book carries an errata marker such as "(errata E-2)", the errata entry
replaces the printed text. Where this book and a JSON table disagree on a
number, the JSON table wins.

Files in the data directory:

| File | What it holds |
|------|---------------|
| `brassmoor_rules.md` | this book |
| `errata.md` | season 5 corrections to this book |
| `units.json` | unit types and their stats |
| `terrain.json` | terrain symbols, move costs, defence and sight rules |
| `advantage.json` | damage multipliers for attacker and defender type pairs |
| `rulesets.json` | dice stream, combat, status, scoring, ladder and balance numbers |
| `players.json` | ladder players and their starting ratings |
| `maps.txt` | the map atlas |
| `replays_visible.log` | replay export, scenario `visible` |
| `replays_peak.log` | replay export, scenario `peak` |
| `replays_steady.log` | replay export, scenario `steady` |
| `replays_burst.log` | replay export, scenario `burst` |
| `replays_latency.log` | replay export, scenario `latency` |

The `visible` export only uses the simple part of the grammar: format 1,
ruleset 1, no lagged orders, no malformed lines and keyframes that always
agree with the engine. The other four exports use everything in this book.


## 1. The game in one page

Two sides fight on a rectangular grid. Side A (unit ids `A1`, `A2`, ...)
belongs to player `p0`, side B (unit ids `B1`, `B2`, ...) belongs to player
`p1`. Each turn every living unit may carry one effective order: move along
a path, attack one enemy unit, hold (brace) or ready (wait to strike a unit
that moves). Units act one at a time in initiative order. Dice come from a
single deterministic stream seeded per match, so a replay of the same orders
always gives the same result. At the end of every turn poison ticks,
objective cells are scored and a digest of the full state is recorded.

A match ends when the log says `END`. The engine never stops early: every
turn block present in the log is played, even after one side has no units
left (such a turn still produces a digest).


## 2. Board, coordinates and the map atlas

### 2.1 Atlas format

`maps.txt` holds one block per map:

```
MAP <name> <width> <height>
<row 0>
<row 1>
...
<row height-1>
ENDMAP
```

Lines starting with `#` and blank lines outside blocks are comments. Each
row has exactly `width` terrain symbols. Rows are listed top row first.

### 2.2 Canonical coordinates

A cell is written `x,y`. `x` is the column, counted from 0 at the left edge.
`y` is the row, counted from 0 at the top row (the first row printed in the
atlas). These are the canonical coordinates. The engine, the digests and
every report use canonical coordinates only.

Replay logs written in format 1 use canonical coordinates directly. Logs in
format 2 use a different origin (errata E-2).

### 2.3 Distance and adjacency

Two cells are adjacent when they share an edge (the four orthogonal
neighbours). Diagonal cells are not adjacent. Distance is the Manhattan
distance `|x1 - x2| + |y1 - y2|`.

### 2.4 Occupancy

At most one living unit stands on a cell. Dead units are removed from the
board at once and no longer block anything.


## 3. Units

### 3.1 Stat fields

Every entry in `units.json` has these fields:

| Field | Meaning |
|-------|---------|
| `class` | `foot` or `horse`; selects the move cost column in `terrain.json` |
| `hp` | starting and maximum hit points |
| `atk` | attack bonus added to the hit roll |
| `def` | base defence |
| `move` | movement points per turn |
| `range` | maximum shooting distance (only used by units tagged `ranged`) |
| `dice` | damage dice as `[count, sides, bonus]` |
| `armour` | subtracted from every hit this unit takes |
| `init` | base initiative |
| `cost` | points value, used for scoring and balance |
| `tags` | any of `pike`, `ranged`, `skirmisher`, `poison` |

Tag meanings:

* `pike`: takes part in a shield wall (section 9.4).
* `ranged`: may shoot at distance 2 or more (section 9.1); at distance 1 it
  fights pinned.
* `skirmisher`: ignores zones of control (section 8.3).
* `poison`: every hit that does not kill poisons the target (section 9.6).

### 3.2 Printed roster (season 4 values, errata E-1)

The table below is the roster as printed for season 4. Season 5 changed
several numbers; the stats in `units.json` are the ones to use (errata E-1).
It is kept here because older match notes refer to it.

| Type | Class | HP | Atk | Def | Move | Range | Dice | Armour | Init | Cost | Tags |
|------|-------|----|-----|-----|------|-------|------|--------|------|------|------|
| pikeman | foot | 14 | 3 | 3 | 3 | 1 | 1d8+1 | 2 | 3 | 4 | pike |
| swordsman | foot | 16 | 4 | 3 | 3 | 1 | 1d10+1 | 1 | 4 | 5 | |
| archer | foot | 10 | 3 | 1 | 3 | 4 | 1d6+1 | 0 | 5 | 4 | ranged |
| crossbow | foot | 11 | 5 | 2 | 2 | 6 | 1d12 | 1 | 2 | 6 | ranged |
| lancer | horse | 15 | 5 | 2 | 6 | 1 | 2d6 | 1 | 6 | 7 | |
| outrider | horse | 10 | 3 | 2 | 6 | 1 | 1d6+1 | 0 | 7 | 4 | skirmisher |
| fenrunner | foot | 8 | 3 | 2 | 4 | 1 | 1d4+1 | 0 | 6 | 4 | skirmisher, poison |

### 3.3 Unit ids

A unit id is the side letter `A` or `B` followed by a unit number written
without leading zeros (`A1`, `B12`; never `A0` or `A01`). The unit number is
a whole number and compares as a number: `A2` comes before `A10`.

The standard roster order used everywhere in this book is: side A before
side B, then unit number ascending (numeric).


## 4. Terrain

`terrain.json` maps each map symbol to a terrain entry:

| Field | Meaning |
|-------|---------|
| `name` | display name |
| `cost.foot`, `cost.horse` | movement points to enter the cell; `null` means the class cannot enter |
| `def` | added to the defence of a unit standing on the cell (may be negative) |
| `blocks_los` | the cell blocks lines of sight |
| `range_bonus` | added to the shooting range of a ranged unit standing on the cell |
| `objective` | the cell is an objective (section 10.2) |

The cost of a step is always looked up in the column of the moving unit's
class. A foot unit and a horse unit can pay different amounts for the same
cell, and a cell can be open to one class and closed to the other.


## 5. The dice stream

### 5.1 Generator

Every match owns one 32 bit state. At deployment the state equals the match
`seed` from the header. One step of the generator is

```
state = (state * multiplier + increment) mod 2^modulus_bits
```

with `multiplier`, `increment` and `modulus_bits` from the `dice` block of
`rulesets.json`.

### 5.2 Rolling a die with S sides

A roll of a die with `S` sides takes one or more generator steps. After each
step the engine takes a sample from the state. The printed season 4 sample
rule is:

```
sample = (state >> 20) & 0xFFF          # 12 bits, span 4096
```

Season 5 uses a different sample width (errata E-3).

Rejection rule: let `span` be the number of possible sample values and
`limit = span - (span mod S)`. If `sample < limit` the roll is
`1 + (sample mod S)`. Otherwise the sample is rejected, the engine takes
another generator step and samples again, until a sample is accepted. This
keeps every face equally likely.

### 5.3 Draws and phases

Every generator step is one draw, including steps whose sample was rejected.
Draws are counted per match in three phases:

* `attack`: the d20 hit roll of an ordinary attack.
* `damage`: the damage dice of an ordinary attack that hit.
* `reaction`: every draw made during a reaction strike (section 8.4), both
  the d20 and the damage dice.

The draw counts feed `bottleneck_analysis.json` (section 13.3).

### 5.4 Rulesets

The header field `rules` names a ruleset in `rulesets.json`. Ruleset 1 keeps
one stream for the whole match. Ruleset 2 changes how the stream is seeded
at the start of each turn (errata E-4).


## 6. Replay log grammar

### 6.1 Lines

A log is plain text with one record per line. Before anything else, each line
is stripped of leading and trailing whitespace. Then:

* an empty line is ignored;
* a line whose first character is `#` is a comment and is ignored;
* every other line is split into tokens on single space characters. Two
  spaces in a row produce an empty token, which makes the line malformed.

Every non blank, non comment line is either accepted or counted as one
malformed line. Malformed lines are skipped and have no other effect.

### 6.2 Records

```
MATCH <id> v=<format> rules=<ruleset> map=<map> seed=<hex8> p0=<player> p1=<player> turns=<n>
U <uid> <type> <x> <y>
T <n>
K <n> rng=<hex8> cp=<c0>,<c1> <uid>@<x>,<y>,<hp>,<poison>,<routed> ...
O <uid> <verb> ...
O~<lag> <uid> <verb> ...
END <id>
```

A whole number is written in decimal without leading zeros (`0` itself is
allowed). `hex8` is exactly 8 lowercase hexadecimal digits.

`MATCH` opens a match. It is accepted only when no match is open, it has
exactly 9 tokens, and the seven tokens after the id are `key=value` pairs
with exactly the keys `v`, `rules`, `map`, `seed`, `p0`, `p1`, `turns` (any
order, each once). `v` is `1` or `2`, `rules` is `1` or `2`, `seed` is hex8,
`turns` is a whole number. The `turns` field is informational only; the
engine plays the turn blocks that are actually present.

`U` deploys a unit. It is accepted only inside an open match, before the
first `T` of that match, with exactly 5 tokens, a valid unit id, a type that
exists in `units.json`, and whole number coordinates. Deployment coordinates
use the format of the match (errata E-2).

`T <n>` opens turn block `n` inside an open match (exactly 2 tokens, `n` a
whole number). The turn number used by the rules (side rotation, reseeding,
the digest) is this `n`. Turn numbers need not be consecutive; turn ordinals
used by amendments count accepted blocks in file order instead.

`K` is a keyframe (section 7). It is accepted only inside a turn block,
before the first accepted order of that block, at most once per block, and
only when every field parses: `K`, a whole number (it repeats the turn
number and is not otherwise used), `rng=` with hex8, `cp=` with two whole
numbers, then zero or more unit entries `uid@x,y,hp,poison,routed` where all
five fields are whole numbers and `routed` is `0` or `1`.

`O` and `O~<lag>` are orders, accepted only inside a turn block. `O` has lag
0. `O~<lag>` has a lag of one digit `1` to `9` (`O~0` and `O~x` are
malformed). The verbs are:

| Form | Tokens |
|------|--------|
| `O <uid> HOLD` | exactly 3 |
| `O <uid> READY` | exactly 3 |
| `O <uid> ATTACK <target>` | exactly 4, target a valid unit id |
| `O <uid> MOVE x,y x,y ...` | 4 or more, each waypoint two whole numbers joined by one comma |

`END <id>` closes the open match when `id` equals the open match id. Only a
closed match is played and reported. A match still open when the file ends
is dropped. Its lines still count toward `orders_total`, `malformed_lines`
and `unknown_unit_orders`, but its `U` lines do not count as deployed.

Anything else is malformed: an unknown record word, a record in the wrong
place (an order before the first `T`, a `U` after a `T`, any record outside
an open match, a second `MATCH` while one is open), a wrong token count, or a
field that does not parse.

### 6.3 Orders naming units that are not in the match

An order that parses but whose issuer, or whose ATTACK target, is not one of
the unit ids deployed by the `U` lines of this match is an unknown unit
order. It is counted in `unknown_unit_orders`, it is not malformed and it is
discarded. A discarded unknown unit order does not count as the first
accepted order of its block for the `K` placement rule of section 6.2, so a
`K` that follows only unknown unit orders in its block is still accepted.
Orders for deployed units that have since died are normal orders: they are
counted and resolved, they just do nothing when the unit is dead.

### 6.4 Lag, superseded and late orders

Network lag in the studio client means an order can arrive in the log after
the turn it was meant for. The `O~<lag>` form records how many turns late it
arrived. Within one turn block, orders are grouped by issuer and resolved as
follows:

1. Orders with lag 2 or more are late. They are counted in `orders_late` and
   ignored.
2. If the unit has one or more lag 0 orders, its effective order is the last
   lag 0 order listed in the block.
3. Otherwise, if it has one or more lag 1 orders, its effective order is the
   last lag 1 order listed.
4. Every lag 0 or lag 1 order of the unit other than the effective one is
   superseded and counted in `orders_superseded`. In other words the unit
   adds (number of its lag 0 and lag 1 orders) minus 1, when it has any.

A unit with no effective order does nothing this turn. These counts are
syntactic: they are taken for every unit with orders in the block, alive or
not.


## 7. Keyframes

The client writes a keyframe every few turns so a viewer can jump into the
middle of a match. `K` inside turn block `n` holds the full state at the end
of turn `n - 1`: the dice state, both control point totals and every living
unit with its position, hit points, poison counter and routed flag. Unit
coordinates in a keyframe use the match format (errata E-2).

When turn block `n` has a keyframe, the engine does this before anything
else in the turn (errata E-6 for its place relative to reseeding):

1. Compare. Build the engine state at that moment: the dice state, the two
   control totals, and the list of living units in standard roster order as
   `(uid, x, y, hp, poison, routed)` in canonical coordinates. Build the same
   from the keyframe (units in the order listed, coordinates converted to
   canonical). If any part differs, record a divergence `[match id, n]`.
2. Adopt. The keyframe becomes the state, whether or not it differed: the
   dice state and control totals are copied; every listed unit takes the
   listed position, hp, poison and routed values; a listed unit that the
   engine had removed comes back (its type is taken from its `U` line);
   every living unit that is not listed is removed.

Keyframes in the exports are written in standard roster order, so a correct
engine sees no difference on an honest keyframe. Some keyframes in the
exports were edited by hand during a support investigation; those are the
divergences to report, and after adopting them the engine continues from the
edited state.


## 8. Turn sequence

Each turn block `n` is played in this order:

1. Keyframe compare and adopt, if the block has one (section 7).
2. Ruleset reseed, if the ruleset asks for it (errata E-4).
3. Initiative snapshot (section 8.1).
4. Resolve effective orders (section 6.4). Every living unit whose effective
   order is HOLD is braced for the whole turn. Every living unit whose
   effective order is READY is armed for the whole turn.
5. Units act in execution order (section 8.1). A unit that is dead when its
   slot comes up is skipped. MOVE runs section 8.2 and then reactions
   (section 8.4); ATTACK runs section 9 against the named target if the
   target is alive and the attack is legal; HOLD and READY take no action
   in the unit's own slot.
6. End of turn (section 10): poison ticks, objective control.
7. Braced, armed and reacted marks are cleared. The digest for turn `n` is
   recorded (section 11).

### 8.1 Initiative and execution order

At step 3 every living unit gets an effective initiative

```
eff_init = init - (max_hp - hp) // 3
```

using hit points at the start of the turn. This value holds for the whole
turn, even if the unit is wounded later in the turn.

Execution order sorts the living units by:

1. `eff_init`, highest first;
2. side: on odd turns side A goes first, on even turns side B goes first;
3. unit number, lowest first, compared as a number.

The same list is the reaction order (section 8.4).

### 8.2 Movement

A MOVE order lists waypoints. The unit starts with `move` movement points
and walks the waypoints in order. Waypoint coordinates use the match format
(errata E-2). For each waypoint the step is taken only when all of these
hold:

* the waypoint is adjacent to the unit's current cell;
* the waypoint is inside the map;
* the terrain cost for the unit's class is not `null`;
* no living unit stands on the waypoint;
* the cost is not more than the remaining movement points.

If any condition fails the unit stops where it is and the rest of the path
is dropped. Otherwise the unit enters the cell and pays the cost.

### 8.3 Zone of control

After entering a cell, a unit that is not tagged `skirmisher` and is now
adjacent to at least one enemy unit stops; the rest of the path is dropped.
Skirmishers keep walking.

### 8.4 Reactions

When a MOVE order made at least one step, armed enemy units get a chance to
strike the mover. Go through the execution order of this turn from the
start. A unit reacts when it is alive, belongs to the other side, is armed,
has not reacted yet this turn, and has a legal attack on the mover from where
both stand now (section 9.1, including range and line of sight for ranged
units). A reacting unit makes one strike (section 9) with all its draws in
the `reaction` phase and is marked as reacted. Stop as soon as the mover is
dead. Each unit reacts at most once per turn. Reacting does not use up the
unit's slot (its own READY order does nothing in its slot anyway).


## 9. Attacks

### 9.1 Legality

An attack by `a` on target `b` is legal when:

* both are alive and on different sides;
* `a` is not routed;
* and one of these holds:
  * distance 1: a melee attack, or a pinned attack when `a` is tagged
    `ranged`;
  * `a` is tagged `ranged`, distance is 2 or more, distance is not more than
    `a.range` plus the `range_bonus` of the terrain under `a`, and the line
    of sight from `a` to `b` is clear: a ranged attack.

An illegal attack does nothing and makes no draws.

Line of sight is traced with the integer line routine in Appendix B from the
attacker's cell to the target's cell. Only the cells strictly between the two
ends are checked. A checked cell blocks the line when its terrain has
`blocks_los` true or when any living unit (either side) stands on it.

### 9.2 Hit roll

Roll a d20 (phase `attack`, or `reaction` for a reaction strike).

* A roll equal to `crit_roll` (20) hits and is a critical hit.
* Otherwise the attack hits when

```
roll + attack + flank >= hit_target + defence
```

`attack` is `a.atk`, minus `pinned_penalty` for a pinned attack. `flank` is
used for melee and pinned attacks only (0 for ranged): the number of units of
the attacker's side, other than the attacker, adjacent to the target, capped
at `flank_cap`.

### 9.3 Defence

```
defence = b.def + terrain def of b's cell
          + shield_wall_bonus   if the shield wall applies
          + brace_bonus         if b is braced this turn
          - rout_penalty        if b is routed
```

### 9.4 Shield wall

The shield wall applies when the target is tagged `pike` and at least one
other living unit of the target's own side, also tagged `pike`, is adjacent
to the target. The bonus is added once no matter how many pike neighbours
there are.

### 9.5 Damage

On a hit roll the damage dice `[count, sides, bonus]` of the attacker. A
critical hit doubles `count`. The dice are drawn in phase `damage` for an
ordinary attack and in phase `reaction` for a reaction strike.

```
total  = bonus + sum of the dice
ratio  = num / den from advantage.json for (attacker type, defender type),
         or the default pair when the combination is not listed
damage = max(min_damage, (total * num) // den - b.armour)
```

The multiplier is applied to the dice total first, rounded down with integer
division, and the armour is taken off after that. The full damage value is
taken off the target's hit points and is credited to the attacker's unit
type as damage dealt, even when it is more than the target had left.

### 9.6 After the damage

1. If the target's hp is 0 or less it is removed at once and the kill is
   credited to the attacker's unit type. Nothing else happens.
2. Otherwise, if the attacker is tagged `poison`, the target's poison counter
   is set to `poison_turns`. A second poisoning resets the counter to
   `poison_turns`; it does not add to what is left.
3. Otherwise (and also after step 2) the rout check runs on the target.

### 9.7 Rout

A unit that is not yet routed routs when its hit points fall to a third of
its maximum or less. The printed rule is `hp * 3 <= max_hp` (errata E-5).
The check runs after every loss of hit points that the unit survives: after
damage from an attack and after a poison tick. Routing is permanent for the
match. A routed unit:

* takes `rout_penalty` off its defence;
* cannot attack and cannot react (its attacks are illegal);
* can still move, hold and ready.


## 10. End of turn

### 10.1 Poison

Go through the living units in standard roster order. Each unit with a
poison counter above 0 loses 1 hp and its counter drops by 1. A unit that
reaches 0 hp is removed; poison deaths are not credited to anyone as kills
and add no damage dealt. A unit that survives the tick gets the rout check.

### 10.2 Objective control

Go through the objective cells in row major order (top row first, left to
right). For each objective look at the cell itself and its four adjacent
cells. If living units of exactly one side are present there (one or more of
that side, none of the other), that side gains 1 control point. If both sides
are present, or neither, nobody scores for that objective. Units removed by
poison earlier in the same end of turn are already gone when control is
counted.


## 11. State digest

After every turn the engine records an 8 digit lowercase hexadecimal digest.
A digest is also taken once before turn 1, right after deployment, with the
dice state equal to the seed and control `0,0`; this is digest index 0. The
digest of turn block number `k` in file order is at index `k`.

The digest text is

```
t=<turn>;rng=<state as 8 lowercase hex>;cp=<c0>,<c1>;
```

followed by one entry per living unit in standard roster order:

```
<uid>@<x>,<y>,<hp>,<poison>,<routed>;
```

with canonical coordinates and `routed` as 0 or 1. `<turn>` is 0 for the
deployment digest and the turn number `n` otherwise. The digest is the 32 bit
FNV-1a hash of the ASCII bytes of that text (Appendix C), written as 8
lowercase hex digits.


## 12. Match result and ladder

### 12.1 Result

At the end of the last turn block:

* if exactly one side still has living units, that side's player wins;
* if no units are left at all, the match is a draw;
* otherwise each side scores `control * control_points` plus the sum of the
  `cost` of its living units. The higher score wins; equal scores are a
  draw.

### 12.2 Ladder

Each scenario file is its own ladder. Start every player at the rating in
`players.json` and apply the matches of that file in file order. With `R_w`
and `R_l` the current ratings of winner and loser, and the numbers from the
`ladder` block of `rulesets.json`:

```
delta = win_base + floor((R_l - R_w) / win_divisor)
delta = clamp(delta, win_min, win_max)
winner gains delta, loser loses delta
```

`floor` rounds toward negative infinity, so `floor(-120 / 25)` is `-5`.

For a draw, the higher rated player of the two is `p0` when the ratings are
equal, otherwise whoever is higher:

```
gift = min(draw_cap, floor((R_high - R_low) / draw_divisor))
higher rated player loses gift, lower rated player gains gift
```

Standings list every player who played at least one match in that file,
sorted by final rating, highest first, ties by player id ascending. Each row
counts played, won, drawn and lost matches.


## 13. The nine reports

The engine writes nine JSON files into the output directory. Key order and
whitespace do not matter; key names, nesting, list order and values do. All
numbers are integers.

### 13.1 `scenario_<name>.json` (one per scenario)

For each of `visible`, `peak`, `steady`, `burst`, `latency`:

```
{
  "scenario": "<name>",
  "source": "replays_<name>.log",
  "matches": [ <one entry per closed match, in file order> ],
  "standings": [ <ladder rows, section 12.2> ]
}
```

A match entry:

| Key | Value |
|-----|-------|
| `id` | match id |
| `map` | map name |
| `players` | `[p0, p1]` |
| `turns` | number of turn blocks played |
| `digests` | list of digests, index 0 is deployment, then one per turn block |
| `control` | `[c0, c1]` final control totals |
| `survivors` | `[[uid, x, y, hp], ...]` living units at the end, standard roster order, canonical coordinates |
| `score` | `[s0, s1]` as defined in section 12.1, always filled in |
| `winner` | the winning player id, or `null` for a draw |
| `amendments` | recovery audit entries in accepted revision order (section 16); `[]` when none apply |

A standings row: `{"player", "rating", "played", "won", "drawn", "lost"}`.

### 13.2 `perf_report.json`

```
{"scenarios": {"<name>": {"matches": M, "turns": T, "orders_total": O,
                          "orders_late": L, "orders_superseded": S}, ...}}
```

`matches` is the number of closed matches, `turns` the total number of turn
blocks in them, `orders_total` the number of accepted orders for deployed
units (any lag, including late ones), `orders_late` and `orders_superseded`
as in section 6.4. Orders inside a match that is never closed are still
counted. Section 16 leaves `orders_total` as the original transport count;
late and superseded counts use only the final corrected slots of closed matches.

### 13.3 `bottleneck_analysis.json`

```
{"scenarios": {"<name>": {"draws_by_phase": {"attack": a, "damage": d, "reaction": r},
                          "dominant_phase": "<phase>"}, ...}}
```

Draw counts are summed over all closed matches of the file (section 5.3).
`dominant_phase` is the phase with the highest count; on a tie the
alphabetically first phase name wins.

### 13.4 `recommendations.json`

One entry per unit type, for every type in `units.json`, summed over all
five scenario files:

```
{"units": {"<type>": {"deployed": D, "damage_dealt": X, "kills": K,
                      "per_cost_permille": P, "verdict": "<verdict>"}, ...}}
```

`deployed` counts the `U` lines of that type in closed matches.
`damage_dealt` and `kills` are the credits from section 9 (ordinary and
reaction strikes both count). `per_cost_permille = damage_dealt * 1000 //
(deployed * cost)`, or 0 when the type was never deployed. The verdict uses
the `balance` block of `rulesets.json`: `nerf` when `per_cost_permille >=
nerf_at`, else `buff` when `per_cost_permille <= buff_at`, else `hold`.

### 13.5 `data_quality.json`

```
{"scenarios": {"<name>": {"malformed_lines": N, "unknown_unit_orders": U,
                          "divergences": [[match_id, turn], ...],
                          "amendments": {"applied": A, "stale": S, "unknown": X}}, ...}}
```

`divergences` lists every keyframe that disagreed with the engine (section
7), in file order, from the final corrected replay only. The amendment counters
are defined in section 16 and sum over closed matches only.

### 13.6 Running the engine

The engine is one Python file run as

```
python3 optimize.py <data_dir> <out_dir>
```

It reads the tables and the five logs from `<data_dir>` by the file names in
the table at the top of this book, creates `<out_dir>` when it is missing and
writes the nine reports there.


## 14. Worked example: a three turn demo match

This demo uses a small map that is not in the atlas. It walks through most
rules once. All numbers below come from the season 5 tables and errata.

Map `demo-1`, width 6, height 4:

```
..f...
..O.h.
rrrrrr
.m....
```

Log (format 1, ruleset 1):

```
MATCH demo-01 v=1 rules=1 map=demo-1 seed=13572468 p0=P0001 p1=P0002 turns=3
U A1 pikeman 0 1
U A2 archer 0 2
U B1 lancer 5 1
U B2 fenrunner 5 2
T 1
O A1 MOVE 1,1 2,1
O A2 MOVE 1,2 2,2
O B1 MOVE 4,1 3,1
O B2 READY
O~1 B2 HOLD
T 2
O A2 ATTACK B1
O A1 ATTACK B1
O B1 ATTACK A1
O~3 B2 HOLD
O B2 MOVE 4,2
T 3
O A1 ATTACK B1
O B1 READY
O~1 B1 ATTACK A1
O A2 MOVE 3,2
O B2 READY
END demo-01
```

Deployment digest text:
`t=0;rng=13572468;cp=0,0;A1@0,1,14,0,0;A2@0,2,10,0,0;B1@5,1,15,0,0;B2@5,2,9,0,0;`
which hashes to `2b712f74`.

**Turn 1** (odd, side A wins initiative ties). Orders: B2 has a lag 0 READY
and a lag 1 HOLD, so READY is effective and one order is superseded.
Initiative: B1 6, B2 6, A2 5, A1 3, so the execution order is B1, B2, A2,
A1. B1 steps onto the hill at 4,1 (horse cost 2) and then 3,1 (cost 1), 3 of
its 5 points. A2 walks 1,2 then 2,2 on the road. A1 walks 1,1 then 2,1 and
stops there, next to B1 (zone of control; it was the last waypoint anyway).
The armed B2 at 5,2 is at distance 3 from A2 and 4 from A1, too far for a
melee unit, so no reaction. No draws. Objective 2,1: A1 stands on it and B1
is adjacent, both sides present, nobody scores. Digest `815835d9`.

**Turn 2** (even, side B wins ties). B2 has a late `O~3` order (ignored,
counted late) and a fresh MOVE. Execution order B1, B2, A2, A1.

* B1 attacks A1 (melee, distance 1). Draw 1: state `59a26081`, sample 179,
  d20 = 20, a critical hit. Lancer dice 2d6 doubled to 4d6: samples 16, 50,
  457 and one more give 5, 3, 2, 5, total 15. No advantage pair for
  lancer on pikeman, so 15 * 1 // 1 = 15, minus pikeman armour 2 = 13.
  A1 drops to 1 hp. 1 * 4 <= 14, so A1 routs.
* B2 moves to 4,2.
* A2 shoots B1 at distance 2: the line from 2,2 to 3,1 has no cell strictly
  between, so sight is clear. d20 = 18, hit. 1d6+1 = 4 + 1 = 5, minus
  lancer armour 1 = 4. B1 drops to 11.
* A1 is routed, so its attack is illegal: no draws.

Phase counts so far: attack 2, damage 5. Digest `efb2ab13`.

**Turn 3** (odd). B1 has a fresh READY and a lag 1 ATTACK: READY is
effective, one superseded. Initiative at the start of the turn: B1 is
wounded by 4, so 6 - 4 // 3 = 5; B2 6; A2 5; A1 3. Execution order: B2 (6),
then B1 and A2 at 5 with side A first on an odd turn, so A2, then B1, then
A1.

* B2 is READY: nothing in its slot.
* A2 moves to 3,2 and stops (adjacent to B1 and B2). It made a step, so
  reactions run in execution order: B2 first (armed, enemy, melee distance
  1): d20 = 12, flank 1 (B1 stands next to A2), 12 + 3 + 1 >= 10 + 1
  (archer def 1, road def 0), hit; 1d4+1 = 3 + 1 = 4, no advantage pair for
  fenrunner on archer, minus armour 0 = 4.
  A2 at 6 hp, poisoned for 3 turns. Then B1: d20 = 3, miss. All three of
  these draws are in phase `reaction`.
* B1 READY: nothing in its slot.
* A1 is routed: its attack is illegal.

End of turn: A2 takes 1 poison damage (5 hp, counter 2); 5 * 4 > 10, no
rout. Objective 2,1 is still contested. Digest `78d4f058`.

Result: both sides alive. Scores: A has pikeman 4 + archer 4 = 8, B has
lancer 7 + fenrunner 4 = 11, no control points. B wins, so the winner is
`P0002`.

The match entry for this demo would be:

```
{"id": "demo-01", "map": "demo-1", "players": ["P0001", "P0002"], "turns": 3,
 "digests": ["2b712f74", "815835d9", "efb2ab13", "78d4f058"],
 "control": [0, 0],
 "survivors": [["A1", 2, 1, 1], ["A2", 3, 2, 5], ["B1", 3, 1, 11], ["B2", 4, 2, 9]],
 "score": [8, 11], "winner": "P0002", "amendments": []}
```

Its counters: 15 orders, 1 late, 2 superseded, draws attack 2, damage 5,
reaction 3.


## 15. More small examples

### 15.1 Dice with a rejection

Seed `00001000`, rolling d20 three times with the season 5 sample width
(errata E-3: span 512, so limit = 512 - 12 = 500):

| Step | State | Sample | Result |
|------|-------|--------|--------|
| 1 | `64e70039` | 201 | d20 = 2 |
| 2 | `fd82a67e` | 507 | rejected (507 >= 500) |
| 3 | `82cf77df` | 261 | d20 = 2 |
| 4 | `3e562c2c` | 124 | d20 = 5 |

The second d20 took two draws. A d8 never rejects (512 is a multiple of 8);
a d6 rejects samples 510 and 511; a d12 rejects 504 to 511.

### 15.2 Digest

Text `t=0;rng=0000beef;cp=0,0;A1@0,1,14,0,0;B1@5,1,10,0,0;` hashes to
`4e4bcf91`. The empty text hashes to `811c9dc5` (the FNV offset basis).

### 15.3 Line of sight cells

Cells checked strictly between the ends (Appendix B):

| From | To | Cells checked |
|------|----|---------------|
| 1,1 | 5,3 | 2,2 then 3,2 then 4,3 |
| 6,2 | 3,4 | 5,3 then 4,3 |
| 2,2 | 2,5 | 2,3 then 2,4 |
| 0,0 | 3,3 | 1,1 then 2,2 |

### 15.4 Damage order

A pikeman hits a lancer and rolls 7 on its d8, total 8. The pair
pikeman on lancer is 3/2. Damage is 8 * 3 // 2 = 12, minus lancer armour 1,
so 11. Taking the armour off before the multiplier would give a different
number, which is wrong.

### 15.5 Ladder

Winner rated 1500 beats a loser rated 1580: 16 + floor(80 / 25) = 19.
Winner rated 1600 beats a loser rated 1480: 16 + floor(-120 / 25) = 16 - 5
= 11. A draw between 1610 and 1500: the 1610 player gives min(8, floor(110
/ 50)) = 2 points to the 1500 player.

### 15.6 Ruleset 2 reseed

For seed `0000beef` under ruleset 2 the state at the start of turn 3 (after
any keyframe of turn 3 has been adopted) is `0000beef XOR (3 * 2654435761
mod 2^32)` = `daa6d3fc` (errata E-4).


## Glossary

* **armed**: a living unit whose effective order this turn is READY.
* **braced**: a living unit whose effective order this turn is HOLD; it gets
  `brace_bonus` defence for the whole turn.
* **canonical coordinates**: column from the left, row from the top row of
  the atlas, both from 0.
* **closed match**: a match whose `END` line was accepted.
* **control point**: one point per objective per turn held by one side
  alone.
* **critical hit**: a natural 20 on the hit roll; always hits and doubles the
  damage dice count.
* **digest**: FNV-1a hash of the state text at the end of a turn.
* **divergence**: a keyframe that did not match the engine state.
* **draw (dice)**: one generator step.
* **draw (match)**: a result with no winner.
* **effective order**: the one order per unit per turn that is executed.
* **execution order**: the per turn sorting of living units (section 8.1).
* **flank**: friendly units other than the attacker adjacent to the target.
* **format**: the header `v` field; it controls the coordinate origin.
* **keyframe**: a `K` record holding the state at the end of the previous
  turn.
* **lag**: how many turns late an order arrived.
* **late order**: lag 2 or more; ignored.
* **pinned**: a ranged unit attacking at distance 1, with `pinned_penalty`.
* **reaction**: a strike by an armed unit on an enemy that has just moved.
* **routed**: permanently shaken; lower defence and no attacks.
* **ruleset**: the header `rules` field; it controls reseeding.
* **shield wall**: defence bonus for a pike unit next to another friendly
  pike unit.
* **standard roster order**: side A before B, then unit number ascending.
* **superseded order**: a lag 0 or lag 1 order that is not the effective
  one.
* **zone of control**: the rule that stops non skirmishers when they step
  next to an enemy.


## 16. Historical order recovery

### 16.1 Amendment tail and immutable addresses

Some exports finish each match with a correction tail, before its `END` line:

```
R <turn_ordinal> <slot> <expected_revision> DROP
R <turn_ordinal> <slot> <expected_revision> <complete_order>
```

`complete_order` is a full `O` or `O~1` through `O~9` order using section 6's
grammar, including its issuer. All three address/revision tokens are canonical
natural numbers (no sign or leading zeros). Ordinal and slot must be positive.
Turn ordinal is the one based position of a `T` block in the match, not its
printed turn number. Slot is the one based position among that block's original
syntactically valid orders whose issuer and ATTACK target are in its deployment
roster. Unknown orders, malformed lines, comments and keyframes take no slot.
Late and superseded orders do take slots. Slots never move or disappear.

Each slot starts at revision 0 with its original order. `DROP` leaves a
tombstone, not a shorter slot list. A later replacement may restore a tombstone,
change its issuer, verb, path, target or lag. A replacement MOVE uses the match's
logged coordinate frame, including E-2's format 2 flip; it is never flipped twice.
The original deployment roster, not current survivors, defines known unit ids.

A structurally valid `R` needs an existing original address and a valid payload
grammar. Any other `R` is one malformed line, with no other effect. The first
structurally valid `R` starts the tail, even if it is stale or unknown. After
that, only further `R` lines, comments, blank lines and the matching `END` are
accepted. An ordinary U, T, K or O line in the tail is malformed and has no
effect. A malformed `R` does not start the tail. Matches without R have an empty
tail. An unclosed match contributes its syntactic malformed/ordinary-order
counters as before, but contributes no recovery audit or amendment counters.

### 16.2 Compare and swap precedence

For each structurally valid R in file order:

1. If the replacement issuer or ATTACK target is absent from the deployment
   roster, count one `unknown` amendment and stop processing this R. This takes
   precedence over a stale revision. DROP has no unit ids to check.
2. Otherwise compare expected_revision with that slot's current revision. If
   different, count one `stale` amendment and leave everything unchanged.
3. Otherwise replace or drop the slot and increment its revision by exactly 1.
   Count one `applied` amendment and append one audit entry. Even writing the
   same order again, or dropping an already dropped slot, is an applied revision.

Malformed R lines do not count as unknown or stale. R payloads never increment
`unknown_unit_orders` or `orders_total`. That transport count still counts the
original accepted ordinary orders, including those in unclosed matches. Late
and superseded totals, however, are computed from the final non-tombstone slots
of closed matches, grouped in their unchanged original slot order.

### 16.3 Recovery semantics and accounting

First replay the whole original match, without applying any R, including every
turn and every absolute K snapshot. This is history version 0. After each
applied amendment replay the entire match under the updated slot contents. The
new history is the baseline for the next R; rejected R lines produce no history.
The last version supplies the ordinary digests, final result, ladder, phase
draw totals, balance totals and top level divergences. No intermediate version
contributes extra deployments, match results, damage, kills or draws to totals.

Keyframes are immutable observations, NOT rewritten to agree with a corrected
prefix. At each version compare and adopt them as section 7 and E-6 require.
Consequently a correction can create or remove a divergence, and its state
changes can disappear at a later keyframe while its damage, kill and draw
adjustments remain. Keyframes do not reset those cumulative credits. Ruleset 2
reseeds on every replayed turn, after comparison/adoption. Poison, rout, READY
marks, occupancy and initiative must belong to the history being replayed.

### 16.4 Audit schema

Every match entry has `amendments`, a list in applied R order. Each entry has
exactly these fields:

```
{"turn": Q, "slot": S, "revision": V,
 "before": "hhhhhhhh", "after": "hhhhhhhh", "changed": [I, ...],
 "draws_delta": {"attack": A, "damage": D, "reaction": R},
 "damage_delta": {"<unit_type>": X, ...},
 "kills_delta": {"<unit_type>": K, ...},
 "divergences_before": [N, ...], "divergences_after": [N, ...]}
```

Q and S are the R address, V is the new revision. Before/after are timeline
fingerprints, not just the last turn digest. To fingerprint a digest vector d,
form the ASCII text `0:d[0];1:d[1];...` with each index written as decimal and
each d[i] replaced by its lowercase eight digit digest, then apply FNV-1a 32
(appendix C). Include deployment and every turn, with a trailing semicolon and
no whitespace. For example the vector `["00000000", "1234abcd"]` fingerprints
the text `0:00000000;1:1234abcd;`.

`changed` lists all digest indices whose before and after values differ,
ascending. These are ordinal indices, not printed turn numbers. The deployment
index is included in the comparison (an order correction cannot change it).
Each delta is the new full-history cumulative credit minus the previous
full-history credit. Deltas are signed integers, without clamping or wrapping.
The damage and kill objects include EVERY unit type in units.json, even at 0;
ordinary and reaction strikes contribute, poison deaths do not. The divergence
lists contain that version's divergent printed turn numbers in block order,
not match ids. A no-op can have equal fingerprints, `changed: []`, all deltas 0
and unchanged divergence lists, but still increments revision and emits an entry.

The `amendments` object in each data_quality scenario has exactly `applied`,
`stale`, `unknown`, each a nonnegative integer summed over closed matches.
Scenario match amendment lists are `[]` and these counters are 0 when absent.

### 16.5 Address and precedence example

Suppose turn ordinal 2 originally contains `O A1 HOLD`, an unknown `O B99 HOLD`,
then `O~3 A1 READY`. Only the first and third lines have slots (1 and 2).
After all turn blocks:

```
R 2 1 0 DROP
R 2 1 0 O A1 READY
R 2 1 77 O B99 HOLD
R 2 1 1 O~1 A1 READY
R 2 2 0 DROP
R 2 2 1 DROP
R 2 2 2 O~3 A1 READY
```

With B99 absent from deployment this produces five applied entries, one stale
and one unknown. The unknown R does not change revision, despite expected 77.
Both slots finish at revisions 2 and 3 respectively. The final live orders are
lag 1 READY in slot 1 and lag 3 READY in slot 2: one late, none superseded.
Dropping slot 2 did not shift slot 1, and dropping it twice was not stale.


## Appendix A. Dice roll routine

```
def roll(sides):
    span = 1 << output_bits                      # errata E-3
    limit = span - span % sides
    while True:
        state = (state * multiplier + increment) & ((1 << modulus_bits) - 1)
        count one draw in the current phase
        sample = (state >> output_shift) & (span - 1)
        if sample < limit:
            return 1 + sample % sides
```

## Appendix B. Line routine

```
def cells_between(x0, y0, x1, y1):
    dx = abs(x1 - x0)
    dy = -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    while True:
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy
        if (x0, y0) == (x1, y1):
            return
        yield (x0, y0)
```

## Appendix C. FNV-1a 32

```
def fnv1a(text):
    h = 0x811c9dc5
    for byte in text.encode("ascii"):
        h = ((h ^ byte) * 0x01000193) & 0xffffffff
    return "%08x" % h
```
