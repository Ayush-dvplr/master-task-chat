# TRUTH.md - grain-intake-settlement

Author side golden trajectory. This file never reaches the agent. It records the
screening rules, the thirteen mode bits, how both grading channels score them, and
where a plausible attempt goes wrong.

## Defect

The scale house was recabled and the settlement engine went with it. The agent is
handed the engine's file shapes, its screening rules and its stage order, two worked
intakes at mode zero that pin the plain chain, and one graded intake whose mode word
is `0x1fff` and which ships no output. The work is to recover the plain chain
constants, implement screening exactly as documented, recover the thirteen mode bits
and ship the engine.

1. `(focal)` The thirteen mode bits are undocumented and carry most of the weight.
   Each alters exactly one thing: the tare level chains from the previous bin on
   the same dryer; a weigh charge lands one ticket late; the role tolerance comes
   from the previous ticket's grader; the band edges lift by twenty times the bin
   tier; normalisation uses the bin's smallest testweight; a haul by a custom class
   outfit carries no dockage charge; the last sorting dryer that carries a bin
   stores its tare base as a delta; tickets resolve in ascending testweight then
   seq; a void cancels one strike; the last three screened tickets by seq are
   excluded; the written commodity is an alias for the one `tier + 5` places later
   in the documented commodity order; embargo adds the previous bin on the same
   dryer's strikes; and a scrap banded ticket forces the next ticket on that bin
   off `clear`.
2. `(focal)` Intake screening. `tickets.jsonl` carries retransmitted, conflicting,
   re-entered and damaged lines. `engine.md` states every rule: pass one sets aside
   a line on its own (bad UTF-8, not a JSON object, a key named twice, missing key,
   wrong JSON type, `true`, a quoted number or a whole number written with a
   fraction or exponent where an integer belongs, out of range integer, unknown
   action, unknown bin, grader or hauler); pass two groups the survivors by `seq`,
   compares parsed values (so a copy whose card is spelled in `\u` escapes is a
   retransmission), collapses identical copies into one ticket and sets aside every
   copy of a `seq` whose copies disagree; pass three walks the surviving groups in
   ascending `seq`, lets the first group carrying a `bin` and `card` pair claim it,
   and sets aside every line of a later group carrying a claimed pair. A `seq` in
   conflict claims nothing. `elevator.json` reports the four counts under
   `screened`.
3. `(focal)` The plain chain's constants are missing but learnable from the two mode
   zero intakes, which ship with all three of their output files and which carry
   screening noise of their own, so the screening rules are checkable there too.
4. `(drift)` The obvious move is to read the mode word, find nothing about it in
   the notes, and build the plain chain anyway. That is the trap blind solver and it
   scores 0.0638 on the test channel (delivery, two clean mode zero intakes and the
   screened mode zero intake).
5. `(drift)` `declared_tickets` equals the line count of `tickets.jsonl` (228 on the
   graded intake, the whitespace only line included). Screening keeps 192 tickets
   and the count bias drops three more, so 189 resolve. Neither number is announced
   anywhere except by the digests.
6. `(drift)` `haulers.csv` and the `hauler` column feed screening (an unknown hauler
   is damage) and exactly one mode bit; a solver treating them as audit metadata
   loses both.
7. `(trap)` Interacting traps. Screening runs first and no bit changes it, so the
   count bias trims the tail of the screened tickets, not of the raw lines: every
   fresh damaged or re-entered line in the shipped intakes sits above the last real
   `seq`, so a raw tail reading drops only noise and resolves three tickets too many,
   and an engine without pass three keeps two re-entries that then fill the dropped
   tail in place of real tickets. The re-entry of the conflicted ticket's card is the
   one fresh `seq` that resolves; on the graded intake it and the two light voids
   that close `BIN-01` are the dropped tail, so a testweight floor read before the
   count bias moves the `BIN-01` digest. A floor scan over raw lines meets a zero
   testweight and divides by zero.
8. `(trap)` Screening details that a hand rolled reader gets wrong: Python's
   `isinstance(True, int)` accepts `true` as a testweight of 1; `int("412")`
   accepts a quoted gross; a reader that accepts whole floats takes a relayed copy
   carrying `"gross":412.0` or `"testweight":1000e0`, and because Python compares
   `412.0 == 412` that copy then counts as a retransmission instead of damage, so
   `screened` is off by one in both counts while every settlement line still
   agrees; plain `json.loads` keeps the last value of a repeated key, so a copy
   repeating `gross` with the same value reads as a retransmission and a copy
   repeating `testweight` with a new value reads as a conflict that sets the real
   ticket aside, and a check confined to the eight keys lets a copy that repeats
   `relay` through as a retransmission; byte equality treats a reordered, respaced or `\u` escaped
   retransmission as a conflict; comparing every key treats a copy with an extra
   `relay` key as a conflict; grouping before vetting lets a damaged copy put a good
   `seq` in conflict; keeping the agreeing majority of a conflict resolves a ticket
   the rules set aside; running pass three in file order lets a shuffled re-entry
   take the card from the real ticket; letting a conflicted `seq` claim its card
   sets aside the one re-entry that should resolve; reading the file as text with
   strict UTF-8 crashes on the damaged bytes line.
9. `(trap)` Unbounded integers. Every corpus built with extra bins (both worked
   intakes and every graded corpus) carries one voided bulk load whose gross sits
   past `2**60`. Normalising it with float division (`int(a * 1000 / b)`) loses the
   low digits of its `bushels`; floor division on Python integers is exact. The
   load is a void, so it never enters a bin total and leaves the `top_bin` tie break
   on the worked intakes observable.
10. `(trap)` Five bits are stateful, so they cannot be read off one record. The tare
   chain, the echoed charge, the role lookback, the embargo span and the scrap carry
   all need the intake walked in resolution order with per dryer carry. Two bits
   (void absolution, embargo span) show only in `binroll.json`. The testweight order
   bit changes which ticket resolves first, which moves every carried value under it.

### Trap cards

| Flag | Scope | Forward when the bit is set | Inverse | Dedicated check |
|---|---|---|---|---|
| `0x0001` chain tare | cross-bin | a bin's tare level starts at the current tare level of the bin started before it on the same dryer | carry an ending tare level per dryer while walking the intake in resolution order | `mode_bit_chain_tare` |
| `0x0002` dockage echo | cross-record | a weigh ticket's dockage charge is applied when the next ticket on that bin resolves | hold one charge per bin and release it on the following ticket | `mode_bit_dockage_echo` |
| `0x0004` role lookback | record | the dockage tolerance is the one belonging to the previous ticket's grader, the bin's first ticket using its own | track the previous ticket's grader per bin | `mode_bit_role_lookback` |
| `0x0008` band tier shift | block | the three band edges are each raised by twenty times the bin's tier | recompute the edges per bin before banding | `mode_bit_band_tier_shift` |
| `0x0010` testweight floor | block | normalisation divides by the bin's smallest testweight over the tickets that resolve | pre-scan each bin's resolving tickets for the minimum | `mode_bit_testweight_floor` |
| `0x0020` custom haul | cross-file | a ticket whose hauler is of the custom class adds no dockage charge | join the hauler column against `haulers.csv` before charging | `mode_bit_custom_haul` |
| `0x0040` tare delta | metadata | the last sorting dryer that carries a bin stores its tare base as a delta from the smallest other tare base | add the smallest other tare base back for that one dryer | `mode_bit_tare_delta` |
| `0x0080` testweight order | ordering | tickets resolve in ascending testweight, then ascending seq | sort on the pair before walking, after the count bias | `mode_bit_testweight_order` |
| `0x0100` void absolves | stateful | a void ticket removes one strike from its bin, floored at zero | apply on void tickets after the settlement is emitted | `mode_bit_void_absolves` |
| `0x0200` count bias | cursor | the last three screened tickets by seq are excluded | drop that tail after screening, before resolving | `mode_bit_count_bias` |
| `0x0400` commodity alias | cross-file | the written commodity is an alias for the one `tier + 5` places later in the documented commodity order | shift the written commodity along the documented order before adjusting | `mode_bit_commodity_alias` |
| `0x0800` embargo span | corpus | embargo weighs a bin's strikes plus those of the bin started before it on the same dryer | track the previous bin per dryer to the rollup | `mode_bit_embargo_span` |
| `0x1000` scrap carry | stateful | a ticket that lands in the scrap band forces the next ticket resolved on that bin off `clear` and onto `flagged` | carry a scrap marker per bin and apply it after the status ladder | `mode_bit_scrap_carry` |

The thirteen single bit corpora carry no screening noise, so a solver who has the
bits but trips on screening still earns those 65 points. The thirteen all but one
corpora (one per bit), the two full mode corpora, the screened mode zero corpus and
the repeat corpus all carry noise, so screening and its interaction with the count
bias and the floor are graded in every multi bit corpus. Each all but one corpus
is the only multi bit corpus an engine with exactly that one bit wrong can still
pass, so a near miss on one bit keeps its other twelve single bit checks and one
all but one check.

The reference engine in `solution/solve.py` is written independently of the one in
`tests/test_output.py`, sharing about 5% of its substantive lines. Cross checked
over 40 seeds, clean and noisy, with and without extra bins, at 40 mode words each
(zero, full, every single bit, every all but one word and twelve random words):
6400 corpus and mode pairs, all byte identical.

Out of bounds: nothing asks the agent to change the report shapes beyond what
`reports.md` documents, to touch `/app/data`, or to reach past the Python standard
library. Report files written by hand earn nothing, because only the program is
collected.

## Load-bearing work

One artifact is collected:

- `/app/out/settle.py`

Its content contract: a standard library only Python program taking an input
directory and an output directory as its first two arguments. It reads
`manifest.json`, `dryers.csv`, `contracts.csv`, `graders.csv`, `haulers.csv`,
`bins.csv` and `tickets.jsonl` from the input directory, screens the ticket lines,
honours the `mode` word, and writes `settlements.jsonl`, `binroll.json` and
`elevator.json` (eight keys, `screened` with its four counts included) into the output directory in the
documented byte forms. Repeated runs over one input write identical bytes.

The final message carries eleven named figures measured over the shipped intake,
the count of bins and resolved tickets, which mode bits were settled, and whether
the digests agree. None of that appears in a shipped file and it is graded by the
judged channel alone.

## Verification

`tests/test.sh` clears stale reward files, locks `/logs/verifier` to root,
restricts `/tests`, and hands over to `rewardkit /tests --workspace /app`.
rewardkit scores `tests/test_output.py` (deterministic) and `tests/judge.toml`
(judged) and `tests/reward.toml` gives each channel half: test channel weight
`0.5 / 94`, judged channel weight `0.5 / 77`.

Test channel: 35 checks, 32 positive and 3 negative, positive total 94 and negative
total 11.

- weight 1: `reusable_program_is_delivered`, `untrapped_run_alpha_resolves`,
  `untrapped_run_beta_resolves`, and the thirteen `every_bit_except_*` checks
- weight 3: `screened_intake_mode_zero_resolves`
- weight 5: the thirteen `mode_bit_*` checks and the two `full_mode_intake_*`
  checks
- negatives: `negative_hardcoded_sample_answers` -5,
  `negative_third_party_dependency` -3, `negative_nondeterministic_output` -3

Every graded corpus is built inside the verifier from its own seed, the program
is run demoted to `nobody` in a fresh temporary directory, and all three reports are
compared byte for byte. Every check returns False rather than raising.

Measured with harbor-rewardkit 0.2.1 on a tests-only copy (reward = test channel at
`1 / 94`), in a root holding `out/` and no `data/`: the reference engine 1.0, an
empty workspace 0.0, trap blind at mode zero 0.0638, an engine missing exactly one
mode bit 0.7128 (count bias, scrap carry and dockage echo each measured), and an
engine with one screening rule wrong 0.7234 (bool as integer, whole float as
integer, plain `json.loads` on a repeated key, a repeated key checked only among
the eight, no pass three, a conflicted `seq` claiming its card), pass three walked
in file order 0.7447, and float division in
normalisation 0.2979 (every graded corpus carries a bulk load, and the float
result lands on the right integer on only a few of them). So one wrong screening
fact costs about a quarter of the channel rather than four fifths of it; wrong
arithmetic in the chain itself costs most of it, as a wrong plain chain constant
does. These are test channel scores only;
no judged channel score exists for the oracle, because the oracle leaves no
trajectory.

Judged channel `tests/judge.toml`: 30 criteria, positive total 77, negative total 9.

- Outcome, final message (55): `R1`-`R11` the eleven figures, `scrap_rejects` 24,
  `weighman_flags` 33, `off_role_flags` 14, `hold_bins` 30, `capped_tickets` 10,
  `light_grain_total` 5499, `heavy_grain_total` 3219, `hedge_clear_total` 4565,
  `prime_tickets` 90, `tare_end_total` 5760, `set_aside_lines` 26; `R12` every bin
  digest agrees; `R13` the run digest agrees; `R14` 49 bins; `R15` 189 resolved
  tickets.
- Constraint (11 positive, -6): `R16`-`R18` from "State each of these eleven
  figures, using these names, as plain whole numbers measured over the unprefixed
  intake"; `R19`, `R20` from "say in the closing report how many of the thirteen mode
  bits you settled and which ones are still open"; `R21` from "Run your finished
  program over `/app/data`"; `R22` from "put the program in place and give the
  closing report before you spend whatever time is left on the bits you are still
  unsure of"; `R23` (-5) and `R24` (-1) from "Treat everything in `/app/data` as read
  only input and leave it unchanged."
- Conduct (11 positive, -3): `R25` recomputes the manifest digests, `R26` reproduces
  both worked intakes byte for byte, `R27` settles bits one at a time, `R28` reads
  both notes before writing the program, `R29` (-3) presents a bit meaning as
  documented, `R30` (3) judges the delivered program's code quality: named stages,
  named constants and bit flags, specific exception handling, no debug residue.

No test reads the shipped intake or a trajectory, and no judged criterion reads the
program's output on a generated corpus, so the two channels never grade the same
observable. A trap blind engine reports a wrong number for all ten mode dependent
figures; `set_aside_lines` and the bin count do not depend on the mode word, and the
resolved ticket count depends only on the count bias.

## Root cause

**The mode word was never documented.** `engine.md` states that the word exists,
that each of its thirteen bits alters one step, and that the firmware holding the
meanings is gone.

**The worked intakes teach the base tier and screening and nothing else.** Both ship
at mode zero, so no shipped output exercises a single bit.

**The digest is what makes it fair rather than a guess.** Both digests are taken over
the resolved reports, so a candidate reading can be tested against the shipped file
bin by bin. Identifiability sweep on the shipped data: clearing any one of the
thirteen bits leaves between 2 and 47 of the 49 bin digests agreeing; each of 54
plain chain constant near misses (every integer in the constant block moved up and
down by one: band edges, tolerances, charge, tier, cap, thresholds, adjustments),
the two counted set near misses, both tie break flips, and each of the six new
screening and arithmetic near misses (repeated key, repeated key checked only among
the eight, no pass three, conflicted claim, pass three in file order, float
division) breaks a worked output; the three
interaction near misses (count bias on the raw tail 48 of 49, floor before the count
bias 48 of 49, count bias after the testweight sort 45 of 49) each break at least
one shipped bin digest and the run digest, and so do the repeated key, no pass three
and conflicted claim near misses (48 of 49 each).

**Carried state couples the bits.** Tare level, dockage, strikes and the scrap marker
run forward per bin and, under three of the bits, per dryer across bins. Screening
decides which tickets exist at all, so a screening error moves every carried value
after it.

## Solution shape

1. Read `engine.md` and `reports.md`; write down the screening rules, stage order and
   digest definitions.
2. Implement screening and the plain chain; reproduce both mode zero intakes until
   all three outputs, `screened` included, agree byte for byte.
3. Implement the two digests and confirm them against the example manifests.
4. On the graded intake, set a candidate reading of one bit, resolve, and compare bin
   digests against `manifest.json`; keep the readings that raise the count.
5. Check `binroll.json` as well as `settlements.jsonl`, since two bits move only the
   rollup; decide whether the count bias and the floor act before or after screening
   and the tail trim by the digests.
6. Write the engine to `/app/out/settle.py`, run it over `/app/data`, and report the
   eleven figures, the bin and ticket counts and the bit tally.

## Ordered plan

1. Read both notes and list the screening rules, the stage order, the report keys and
   the digest definitions before writing any code.
2. Build screening first and check its four counts against `screened` in both worked
   `elevator.json` files, since every later number depends on which tickets exist.
3. Fit the plain chain on `example_a_` and confirm it on `example_b_`, so a later
   disagreement is a mode bit rather than a constant.
4. Build the digest routine and validate it against both example manifests.
5. Resolve the graded intake at mode zero and count matching bin digests as the
   baseline for the search.
6. Attack the bits that move a single bin first, then the stateful ones, then the
   ordering and cursor bits, checking `binroll.json` as well as the settlement lines.
7. Settle where the count bias and the floor sit relative to screening by the digests
   rather than by assumption.
8. Deliver the program early, run it over `/app/data`, then keep refining with the
   time left.
9. Report the eleven figures, the counts and the bit tally.

## Pitfalls

- Building the plain chain, finding nothing about the mode word, and shipping
  (0.0638).
- Parsing `tickets.jsonl` with `int()` coercion or `isinstance(x, int)`, or accepting
  a whole float such as `412.0` where an integer belongs.
- Deduplicating on raw line bytes, or comparing extra keys.
- Grouping by `seq` before setting damaged lines aside.
- Parsing with plain `json.loads`, which hides a repeated key.
- Skipping pass three, walking it in file order, or letting a conflicted `seq`
  claim its card.
- Normalising with float division, which loses the bulk load's low digits.
- Trimming the count bias tail from the raw lines, or taking the testweight floor
  before the count bias.
- Opening `tickets.jsonl` as strict UTF-8 text and crashing on the damaged line.
- Digesting only `settlements.jsonl` and calling the void absolution and embargo span
  bits free.
- Iterating `tickets.jsonl` in file order rather than by `seq`.
- Embedding the shipped intake's bin identifiers as literals (-5), importing outside
  the standard library (-3), or emitting anything order or time dependent (-3).

## Provenance

```yaml
instance_id: grain-intake-settlement
task_name: terminal-bench/grain-intake-settlement
solve_sh_sha256: 506c48d5e58f92d657e48e96f92d49b1457aaa09d503b7fed85a0451de86a7c7
solve_py_sha256: 5a2646dd05c11063eafcff1551462d3bee5f1a4ab468f9ffe7a3d38bb42c9a1a
language: python
category: Data Processing
mode_bits: 13
data_files: 29
shipped_intake:
  mode: 8191
  ticket_lines: 228
  screened_tickets: 192
  resolved_tickets: 189
  screened: {conflicted: 3, malformed: 20, reentered: 3, retransmitted: 9}
  bins: 49
  embargoed: [BIN-17, BIN-20, BIN-32, BIN-37, BIN-49]
  bushel_total: 65452
test_channel:
  checks: 35
  positive_total: 94
  negative_total: 11
  trap_blind: 0.0638
judged_channel:
  criteria: 30
  positive_total: 77
  negative_total: 9
oracle_test_channel_local: 1.0   # rewardkit 0.2.1, tests-only copy, not a harbor run
empty_test_channel_local: 0.0
```
